import os
import secrets
import sqlite3
import unicodedata
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path

from fixtures import GROUP_FIXTURES
from phase_bonus import compute_pool_phase_bonuses
from scoring import bold_day_key, calculate_points, calculate_tournament_points

_default_db = Path(__file__).parent / "predictions.db"
DB_PATH = Path(os.environ.get("DATABASE_PATH", _default_db))
FIXED_ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "Ducati1098R!")
MAX_USERS_PER_POOL = 100


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS pools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                invite_code TEXT NOT NULL UNIQUE,
                admin_secret TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(pool_id, display_name)
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage TEXT NOT NULL DEFAULT 'group',
                matchday INTEGER,
                group_name TEXT,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_date TEXT NOT NULL,
                match_time TEXT NOT NULL,
                venue TEXT,
                actual_home INTEGER,
                actual_away INTEGER,
                status TEXT DEFAULT 'scheduled',
                live_minute INTEGER,
                live_home INTEGER,
                live_away INTEGER,
                sort_order INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                home_score INTEGER NOT NULL,
                away_score INTEGER NOT NULL,
                points INTEGER,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(user_id, match_id)
            );

            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pool_id INTEGER NOT NULL REFERENCES pools(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT
            );

            CREATE TABLE IF NOT EXISTS tournament_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                top_scorer TEXT NOT NULL,
                winner TEXT NOT NULL,
                second_place TEXT NOT NULL,
                third_place TEXT NOT NULL,
                submitted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS tournament_results (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                top_scorer TEXT,
                winner TEXT,
                second_place TEXT,
                third_place TEXT,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS match_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                team_side TEXT NOT NULL CHECK (team_side IN ('home', 'away')),
                scorer_name TEXT NOT NULL,
                minute INTEGER NOT NULL,
                injury_minute INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS player_cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                player_name TEXT NOT NULL,
                team TEXT NOT NULL,
                card_type TEXT NOT NULL CHECK (card_type IN ('yellow', 'red')),
                minute INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS match_penalties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
                taker_team TEXT NOT NULL,
                taker_name TEXT,
                goalkeeper_name TEXT,
                outcome TEXT NOT NULL CHECK (outcome IN ('scored', 'saved', 'missed')),
                minute INTEGER NOT NULL,
                injury_minute INTEGER,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        cols = {row[1] for row in conn.execute("PRAGMA table_info(comments)").fetchall()}
        if cols and "updated_at" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN updated_at TEXT")
        if cols and "match_id" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN match_id INTEGER REFERENCES matches(id) ON DELETE CASCADE")

        pred_cols = {row[1] for row in conn.execute("PRAGMA table_info(predictions)").fetchall()}
        if pred_cols and "is_bold" not in pred_cols:
            conn.execute("ALTER TABLE predictions ADD COLUMN is_bold INTEGER NOT NULL DEFAULT 0")
        if pred_cols and "points_excluded" not in pred_cols:
            conn.execute(
                "ALTER TABLE predictions ADD COLUMN points_excluded INTEGER NOT NULL DEFAULT 0"
            )

        match_cols = {row[1] for row in conn.execute("PRAGMA table_info(matches)").fetchall()}
        if match_cols:
            for col, typedef in [
                ("status", "TEXT DEFAULT 'scheduled'"),
                ("live_minute", "INTEGER"),
                ("live_injury_minute", "INTEGER"),
                ("live_home", "INTEGER"),
                ("live_away", "INTEGER"),
                ("match_number", "INTEGER"),
            ]:
                if col not in match_cols:
                    conn.execute(f"ALTER TABLE matches ADD COLUMN {col} {typedef}")

        goal_cols = {row[1] for row in conn.execute("PRAGMA table_info(match_goals)").fetchall()}
        if goal_cols and "is_penalty" not in goal_cols:
            conn.execute("ALTER TABLE match_goals ADD COLUMN is_penalty INTEGER NOT NULL DEFAULT 0")
        if goal_cols and "goal_source" not in goal_cols:
            conn.execute(
                "ALTER TABLE match_goals ADD COLUMN goal_source TEXT NOT NULL DEFAULT 'sync'"
            )

        card_cols = {row[1] for row in conn.execute("PRAGMA table_info(player_cards)").fetchall()}
        if card_cols and "card_source" not in card_cols:
            conn.execute(
                "ALTER TABLE player_cards ADD COLUMN card_source TEXT NOT NULL DEFAULT 'admin'"
            )

        user_cols = {row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()}
        if user_cols and "photo_updated_at" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN photo_updated_at TEXT")
        if user_cols and "ai_agent_key" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN ai_agent_key TEXT")
        if user_cols and "password_hash" not in user_cols:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if user_cols and "password_must_set" not in user_cols:
            conn.execute(
                "ALTER TABLE users ADD COLUMN password_must_set INTEGER NOT NULL DEFAULT 0"
            )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

        count = conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        if count == 0:
            for i, f in enumerate(GROUP_FIXTURES):
                conn.execute(
                    """
                    INSERT INTO matches (stage, matchday, group_name, home_team, away_team,
                                         match_date, match_time, venue, sort_order)
                    VALUES ('group', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f["matchday"],
                        f["group"],
                        f["home"],
                        f["away"],
                        f["date"],
                        f["time"],
                        f["venue"],
                        i + 1,
                    ),
                )

    sync_knockout_stage()
    repair_fixture_schedules()
    repair_premature_results()
    repair_live_display_data()
    merge_canonical_player_accounts()
    merge_users_named("QueenOfPredictions")
    merge_duplicate_users()
    repair_canonical_player_scores()
    repair_rescinded_var_cards()
    repair_bogus_shootout_penalties()
    repair_backfill_ai_agent_keys()
    repair_split_merged_cursor_ai_accounts()
    repair_rename_ir_iran_team()
    ensure_admin_secrets()


def repair_rename_ir_iran_team() -> None:
    """Display name Iran (was IR Iran) across stored picks and match rows."""
    with db() as conn:
        conn.execute("UPDATE matches SET home_team = 'Iran' WHERE home_team = 'IR Iran'")
        conn.execute("UPDATE matches SET away_team = 'Iran' WHERE away_team = 'IR Iran'")
        for col in ("winner", "second_place", "third_place"):
            conn.execute(
                f"UPDATE tournament_votes SET {col} = 'Iran' WHERE {col} = 'IR Iran'"
            )
            conn.execute(
                f"UPDATE tournament_results SET {col} = 'Iran' WHERE {col} = 'IR Iran'"
            )
        conn.execute("UPDATE player_cards SET team = 'Iran' WHERE team = 'IR Iran'")
        conn.execute(
            "UPDATE match_penalties SET taker_team = 'Iran' WHERE taker_team = 'IR Iran'"
        )


def repair_backfill_ai_agent_keys() -> None:
    """Tag synced AI pool users so renames do not break pick sync."""
    from ai_predictor import (
        AI_AGENTS,
        CURSOR_LEGACY_DISPLAY_NAMES,
        LEGACY_PREDICTIONS_AGENT_KEY,
        RENAMED_LEGACY_AI_NAMES,
        REMOVED_SYNC_AGENTS,
        infer_ai_agent_key,
    )

    with db() as conn:
        for agent in AI_AGENTS:
            if agent["key"] in REMOVED_SYNC_AGENTS:
                continue
            conn.execute(
                """
                UPDATE users
                SET ai_agent_key = ?
                WHERE display_name = ? AND (ai_agent_key IS NULL OR ai_agent_key = '')
                """,
                (agent["key"], agent["display_name"]),
            )
        for legacy_name in RENAMED_LEGACY_AI_NAMES | frozenset({"Cursor AI Predictions"}):
            conn.execute(
                """
                UPDATE users
                SET ai_agent_key = ?
                WHERE display_name = ? AND ai_agent_key != ?
                """,
                (LEGACY_PREDICTIONS_AGENT_KEY, legacy_name, LEGACY_PREDICTIONS_AGENT_KEY),
            )
        for legacy_name in CURSOR_LEGACY_DISPLAY_NAMES:
            conn.execute(
                """
                UPDATE users
                SET ai_agent_key = ?
                WHERE display_name = ? AND (ai_agent_key IS NULL OR ai_agent_key = '' OR ai_agent_key = 'cursor')
                """,
                (LEGACY_PREDICTIONS_AGENT_KEY, legacy_name),
            )
        rows = conn.execute(
            "SELECT id, display_name, ai_agent_key FROM users"
        ).fetchall()
        for row in rows:
            if row["ai_agent_key"] in (LEGACY_PREDICTIONS_AGENT_KEY, *REMOVED_SYNC_AGENTS):
                continue
            key = infer_ai_agent_key(row["display_name"])
            if key and key not in REMOVED_SYNC_AGENTS:
                conn.execute(
                    "UPDATE users SET ai_agent_key = ? WHERE id = ?",
                    (key, row["id"]),
                )


def _find_nostradamus_keeper(conn, pool_id: int):
    from ai_predictor import LEGACY_PREDICTIONS_AGENT_KEY, RENAMED_LEGACY_AI_NAMES

    legacy_names = tuple(RENAMED_LEGACY_AI_NAMES | frozenset({"Cursor AI Predictions"}))
    placeholders = ", ".join("?" * len(legacy_names))
    rows = conn.execute(
        f"""
        SELECT id, display_name, ai_agent_key FROM users
        WHERE pool_id = ? AND display_name != 'Cursor AI' AND (
            display_name IN ({placeholders})
            OR ai_agent_key = ?
        )
        """,
        (pool_id, *legacy_names, LEGACY_PREDICTIONS_AGENT_KEY),
    ).fetchall()
    if not rows:
        return None

    def keeper_score(user) -> tuple:
        return (
            user["display_name"] in RENAMED_LEGACY_AI_NAMES,
            user["display_name"] == "Cursor AI Predictions",
            _user_prediction_count(conn, user["id"]),
            _user_match_points(conn, user["id"]),
            -user["id"],
        )

    return max(rows, key=keeper_score)


def _find_cursor_ai_user(conn, pool_id: int, exclude_id: int | None):
    rows = conn.execute(
        """
        SELECT id, display_name, ai_agent_key FROM users
        WHERE pool_id = ?
          AND (? IS NULL OR id != ?)
          AND (
            display_name = 'Cursor AI'
            OR (ai_agent_key = 'cursor' AND display_name NOT IN ('Nostradamus', 'Cursor AI Predictions', 'Cursor AI Prediction'))
          )
        """,
        (pool_id, exclude_id, exclude_id),
    ).fetchall()
    if not rows:
        return None

    def cursor_score(user) -> tuple:
        return (
            user["display_name"] == "Cursor AI",
            user["ai_agent_key"] == "cursor",
            user["display_name"] != "Nostradamus",
            _user_prediction_count(conn, user["id"]),
            -user["id"],
        )

    candidates = [u for u in rows if u["id"] != exclude_id]
    if not candidates:
        return None
    return max(candidates, key=cursor_score)


def fill_nostradamus_cursor_picks(pool_id: int) -> str:
    """Generate Cursor AI picks for remaining fixtures and assign them to Nostradamus."""
    from ai_predictor import LEGACY_PREDICTIONS_AGENT_KEY, predict_score
    from scoring import is_prediction_open, match_teams_known

    with db() as conn:
        keeper = _find_nostradamus_keeper(conn, pool_id)
        if not keeper:
            return "Nostradamus not found in this pool."

        keeper_id = keeper["id"]
        conn.execute(
            "UPDATE users SET ai_agent_key = ? WHERE id = ?",
            (LEGACY_PREDICTIONS_AGENT_KEY, keeper_id),
        )

        cursor_user = _find_cursor_ai_user(conn, pool_id, keeper_id)
        if cursor_user:
            conn.execute("DELETE FROM users WHERE id = ?", (cursor_user["id"],))

        matches = conn.execute(
            """
            SELECT id, home_team, away_team, match_date, match_time
            FROM matches
            WHERE actual_home IS NULL
            ORDER BY sort_order, id
            """
        ).fetchall()

        assigned = 0
        updated = 0
        skipped = 0
        tbd_skipped = 0
        for match in matches:
            if not match_teams_known(match["home_team"], match["away_team"]):
                tbd_skipped += 1
                continue
            if not is_prediction_open(match["match_date"], match["match_time"]):
                skipped += 1
                continue

            home, away = predict_score(
                match["home_team"], match["away_team"], match["id"], "cursor"
            )
            existing = conn.execute(
                "SELECT home_score, away_score FROM predictions WHERE user_id = ? AND match_id = ?",
                (keeper_id, match["id"]),
            ).fetchone()
            if existing:
                if existing["home_score"] == home and existing["away_score"] == away:
                    skipped += 1
                    continue
                conn.execute(
                    """
                    UPDATE predictions
                    SET home_score = ?, away_score = ?, points = NULL
                    WHERE user_id = ? AND match_id = ?
                    """,
                    (home, away, keeper_id, match["id"]),
                )
                updated += 1
                continue

            conn.execute(
                """
                INSERT INTO predictions (
                    user_id, match_id, home_score, away_score, points, is_bold, points_excluded
                )
                VALUES (?, ?, ?, ?, NULL, 0, 0)
                """,
                (keeper_id, match["id"], home, away),
            )
            assigned += 1

        recalculate_user_match_points(keeper_id, conn=conn)

        keeper_name = keeper["display_name"]
        cursor_name = cursor_user["display_name"] if cursor_user else None

    removed = f' Removed synced account "{cursor_name}".' if cursor_name else ""
    tbd_note = f" {tbd_skipped} TBD fixture(s) skipped." if tbd_skipped else ""
    update_note = f" Updated {updated} open pick(s)." if updated else ""
    return (
        f"Added {assigned} Cursor pick(s) to {keeper_name} for remaining open matches"
        f" ({skipped} unchanged or closed).{update_note}{tbd_note}{removed}"
    )


def repair_split_merged_cursor_ai_accounts() -> None:
    """
    Undo mistaken merge of synced Cursor AI + legacy Cursor AI Predictions.

    Legacy / Nostradamus keeps picks that differ from the Cursor algorithm.
    Synced Cursor AI is no longer maintained (see REMOVED_SYNC_AGENTS).
    """
    from ai_predictor import (
        LEGACY_PREDICTIONS_AGENT_KEY,
        RENAMED_LEGACY_AI_NAMES,
        REMOVED_SYNC_AGENTS,
        predict_score,
        predict_tournament_picks,
    )

    if "cursor" in REMOVED_SYNC_AGENTS:
        return

    legacy_names = (*RENAMED_LEGACY_AI_NAMES, "Cursor AI Predictions", "Cursor AI Prediction")
    cursor_agent = next(a for a in AI_AGENTS if a["key"] == "cursor")
    legacy_placeholders = ", ".join("?" * len(legacy_names))

    with db() as conn:
        pool_ids = [row["id"] for row in conn.execute("SELECT id FROM pools").fetchall()]
        matches = conn.execute(
            "SELECT id, home_team, away_team, actual_home, actual_away FROM matches ORDER BY sort_order, id"
        ).fetchall()

        for pool_id in pool_ids:
            legacy = conn.execute(
                f"""
                SELECT id, display_name FROM users
                WHERE pool_id = ? AND display_name IN ({legacy_placeholders})
                ORDER BY id
                LIMIT 1
                """,
                (pool_id, *legacy_names),
            ).fetchone()
            if not legacy:
                continue

            legacy_id = legacy["id"]
            cursor_row = conn.execute(
                """
                SELECT id FROM users
                WHERE pool_id = ? AND ai_agent_key = 'cursor'
                LIMIT 1
                """,
                (pool_id,),
            ).fetchone()

            if cursor_row and cursor_row["id"] != legacy_id:
                cursor_id = cursor_row["id"]
            else:
                if cursor_row and cursor_row["id"] == legacy_id:
                    conn.execute(
                        "UPDATE users SET ai_agent_key = NULL WHERE id = ?",
                        (legacy_id,),
                    )
                cursor_id = conn.execute(
                    """
                    INSERT INTO users (pool_id, display_name, ai_agent_key)
                    VALUES (?, ?, 'cursor')
                    """,
                    (pool_id, cursor_agent["display_name"]),
                ).lastrowid

            for match in matches:
                exp_home, exp_away = predict_score(
                    match["home_team"], match["away_team"], match["id"], "cursor"
                )
                legacy_pred = conn.execute(
                    """
                    SELECT id, home_score, away_score, is_bold
                    FROM predictions WHERE user_id = ? AND match_id = ?
                    """,
                    (legacy_id, match["id"]),
                ).fetchone()
                cursor_pred = conn.execute(
                    """
                    SELECT id, is_bold FROM predictions
                    WHERE user_id = ? AND match_id = ?
                    """,
                    (cursor_id, match["id"]),
                ).fetchone()

                bold = bool(cursor_pred["is_bold"]) if cursor_pred else False
                if (
                    legacy_pred
                    and legacy_pred["home_score"] == exp_home
                    and legacy_pred["away_score"] == exp_away
                ):
                    bold = bold or bool(legacy_pred["is_bold"])
                    conn.execute("DELETE FROM predictions WHERE id = ?", (legacy_pred["id"],))

                points = calculate_points(
                    exp_home,
                    exp_away,
                    match["actual_home"],
                    match["actual_away"],
                    bold,
                )
                conn.execute(
                    """
                    INSERT INTO predictions (user_id, match_id, home_score, away_score, points, is_bold)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id, match_id) DO UPDATE SET
                        home_score = excluded.home_score,
                        away_score = excluded.away_score,
                        points = excluded.points,
                        is_bold = excluded.is_bold,
                        submitted_at = datetime('now')
                    """,
                    (cursor_id, match["id"], exp_home, exp_away, points, 1 if bold else 0),
                )

            cursor_picks = predict_tournament_picks(pool_id, "cursor")
            legacy_vote = conn.execute(
                "SELECT * FROM tournament_votes WHERE user_id = ?",
                (legacy_id,),
            ).fetchone()
            cursor_vote = conn.execute(
                "SELECT id FROM tournament_votes WHERE user_id = ?",
                (cursor_id,),
            ).fetchone()
            if legacy_vote and not cursor_vote:
                lv = dict(legacy_vote)
                if (
                    lv.get("top_scorer") == cursor_picks["top_scorer"]
                    and lv.get("winner") == cursor_picks["winner"]
                    and lv.get("second_place") == cursor_picks["second_place"]
                    and lv.get("third_place") == cursor_picks["third_place"]
                ):
                    conn.execute(
                        "UPDATE tournament_votes SET user_id = ? WHERE user_id = ?",
                        (cursor_id, legacy_id),
                    )

            recalculate_user_match_points(legacy_id, conn=conn)
            recalculate_user_match_points(cursor_id, conn=conn)


def repair_canonical_player_scores() -> None:
    """Recalculate match points for merged canonical players (fixes stale totals)."""
    with db() as conn:
        for canonical in PLAYER_ACCOUNT_ALIASES:
            rows = conn.execute(
                "SELECT id FROM users WHERE display_name = ?",
                (canonical,),
            ).fetchall()
            for row in rows:
                recalculate_user_match_points(row["id"], conn=conn)


def normalize_display_name(name: str) -> str:
    """Case/whitespace/unicode-normalized key for matching pool members."""
    text = unicodedata.normalize("NFKC", name or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return " ".join(text.strip().split()).casefold()


def repair_fixture_schedules() -> int:
    """Align stored group-stage kickoffs with fixtures.py (fixes late-night date drift)."""
    updated = 0
    with db() as conn:
        for f in GROUP_FIXTURES:
            cur = conn.execute(
                """
                UPDATE matches
                SET match_date = ?, match_time = ?
                WHERE stage = 'group'
                  AND home_team = ?
                  AND away_team = ?
                  AND (match_date != ? OR match_time != ?)
                """,
                (f["date"], f["time"], f["home"], f["away"], f["date"], f["time"]),
            )
            updated += cur.rowcount
    return updated


def repair_premature_results() -> int:
    """Clear results recorded before the scheduled kickoff (bad sync / wrong dates)."""
    from datetime import datetime

    from scoring import TIMEZONE, parse_match_datetime

    now = datetime.now(TIMEZONE)
    cleared = 0
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id, match_date, match_time
            FROM matches
            WHERE actual_home IS NOT NULL
            """
        ).fetchall()
        for row in rows:
            kickoff = parse_match_datetime(row["match_date"], row["match_time"])
            if now >= kickoff:
                continue
            clear_match_result(row["id"], conn=conn)
            cleared += 1
    return cleared


def clear_match_result(match_id: int, *, conn=None) -> None:
    """Reset a finished match back to scheduled and clear prediction points."""
    if conn is None:
        with db() as owned:
            clear_match_result(match_id, conn=owned)
        return
    conn.execute(
        """
        UPDATE matches
        SET actual_home = NULL, actual_away = NULL, status = 'scheduled',
            live_home = NULL, live_away = NULL, live_minute = NULL, live_injury_minute = NULL
        WHERE id = ?
        """,
        (match_id,),
    )
    conn.execute(
        "UPDATE predictions SET points = NULL WHERE match_id = ?",
        (match_id,),
    )


def _user_match_points(conn, user_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(SUM(points), 0) AS pts FROM predictions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["pts"] or 0)


def _user_prediction_count(conn, user_id: int) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM predictions WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    return int(row["c"] or 0)


# Same person, different typo when re-joining (normalized names differ).
PLAYER_ACCOUNT_ALIASES: dict[str, frozenset[str]] = {
    "QueenOfPredictions": frozenset({
        "QueenOfPredictions",
        "QueenofPredictions",
        "QueenofPreditions",
        "QureenOfPredictions",
        "QureenOfPreditions",
        "queenofpredictions",
        "queenofpreditions",
    }),
}


def _user_matches_alias(display_name: str, aliases: frozenset[str]) -> bool:
    name = display_name.strip()
    if not name:
        return False
    alias_keys = {normalize_display_name(alias) for alias in aliases}
    alias_keys.add(name)
    return normalize_display_name(name) in alias_keys or name in aliases


def _prediction_points(conn, pred_id: int) -> int:
    row = conn.execute(
        "SELECT COALESCE(points, 0) AS pts FROM predictions WHERE id = ?",
        (pred_id,),
    ).fetchone()
    return int(row["pts"] if row else 0)


def _resolve_prediction_clash(
    conn,
    keeper_id: int,
    keeper_pred_id: int,
    dup_pred_id: int,
) -> None:
    """Keep the better pick when both accounts predicted the same match."""
    keeper_pts = _prediction_points(conn, keeper_pred_id)
    dup_pts = _prediction_points(conn, dup_pred_id)
    if dup_pts > keeper_pts:
        conn.execute("DELETE FROM predictions WHERE id = ?", (keeper_pred_id,))
        conn.execute(
            "UPDATE predictions SET user_id = ? WHERE id = ?",
            (keeper_id, dup_pred_id),
        )
    else:
        conn.execute("DELETE FROM predictions WHERE id = ?", (dup_pred_id,))


def recalculate_user_match_points(user_id: int, *, conn=None) -> None:
    """Refresh stored points from current picks and entered results."""
    if conn is None:
        with db() as owned:
            recalculate_user_match_points(user_id, conn=owned)
        return
    preds = conn.execute(
        """
        SELECT p.id, p.home_score, p.away_score, p.is_bold, p.points_excluded,
               m.actual_home, m.actual_away
        FROM predictions p
        JOIN matches m ON m.id = p.match_id
        WHERE p.user_id = ?
        """,
        (user_id,),
    ).fetchall()
    for pred in preds:
        if pred["points_excluded"]:
            conn.execute("UPDATE predictions SET points = NULL WHERE id = ?", (pred["id"],))
            continue
        if pred["actual_home"] is None or pred["actual_away"] is None:
            continue
        points = calculate_points(
            pred["home_score"],
            pred["away_score"],
            pred["actual_home"],
            pred["actual_away"],
            bool(pred["is_bold"]),
        )
        conn.execute(
            "UPDATE predictions SET points = ? WHERE id = ?",
            (points, pred["id"]),
        )


def _merge_user_records(
    conn,
    keeper_id: int,
    dup_id: int,
    *,
    keeper_label: str,
    dup_label: str,
    pool_id: int,
) -> str | None:
    if keeper_id == dup_id:
        return None
    preds = conn.execute(
        "SELECT id, match_id FROM predictions WHERE user_id = ?",
        (dup_id,),
    ).fetchall()
    for pred in preds:
        clash = conn.execute(
            "SELECT id FROM predictions WHERE user_id = ? AND match_id = ?",
            (keeper_id, pred["match_id"]),
        ).fetchone()
        if clash:
            _resolve_prediction_clash(conn, keeper_id, clash["id"], pred["id"])
        else:
            conn.execute(
                "UPDATE predictions SET user_id = ? WHERE id = ?",
                (keeper_id, pred["id"]),
            )

    dup_vote = conn.execute(
        "SELECT id FROM tournament_votes WHERE user_id = ?",
        (dup_id,),
    ).fetchone()
    if dup_vote:
        keeper_vote = conn.execute(
            "SELECT id FROM tournament_votes WHERE user_id = ?",
            (keeper_id,),
        ).fetchone()
        if keeper_vote:
            conn.execute("DELETE FROM tournament_votes WHERE user_id = ?", (dup_id,))
        else:
            conn.execute(
                "UPDATE tournament_votes SET user_id = ? WHERE user_id = ?",
                (keeper_id, dup_id),
            )

    conn.execute(
        "UPDATE comments SET user_id = ? WHERE user_id = ?",
        (keeper_id, dup_id),
    )
    conn.execute("DELETE FROM users WHERE id = ?", (dup_id,))
    recalculate_user_match_points(keeper_id, conn=conn)
    return f"{dup_label} (id {dup_id}) → {keeper_label} (id {keeper_id}, pool {pool_id})"


def merge_canonical_player_accounts(pool_id: int | None = None) -> list[str]:
    """Merge known typo accounts into one canonical player name per pool."""
    from ai_predictor import is_agent_badge

    merged: list[str] = []
    with db() as conn:
        pool_ids = (
            [pool_id]
            if pool_id is not None
            else [row["id"] for row in conn.execute("SELECT id FROM pools").fetchall()]
        )
        for pid in pool_ids:
            users = conn.execute(
                "SELECT id, display_name, ai_agent_key FROM users WHERE pool_id = ? ORDER BY id",
                (pid,),
            ).fetchall()
            for canonical, aliases in PLAYER_ACCOUNT_ALIASES.items():
                group = [
                    user
                    for user in users
                    if not is_agent_badge(user["display_name"], user["ai_agent_key"])
                    and _user_matches_alias(user["display_name"], aliases)
                ]
                if len(group) < 2:
                    continue
                keeper = max(
                    group,
                    key=lambda u: (
                        normalize_display_name(u["display_name"])
                        == normalize_display_name(canonical),
                        _user_match_points(conn, u["id"]),
                        -u["id"],
                    ),
                )
                keeper_id = keeper["id"]
                for dup in group:
                    if dup["id"] == keeper_id:
                        continue
                    line = _merge_user_records(
                        conn,
                        keeper_id,
                        dup["id"],
                        keeper_label=keeper["display_name"],
                        dup_label=dup["display_name"],
                        pool_id=pid,
                    )
                    if line:
                        merged.append(line)
                conn.execute(
                    "UPDATE users SET display_name = ? WHERE id = ?",
                    (canonical, keeper_id),
                )
    return merged


def merge_user_ids(
    keeper_id: int,
    dup_id: int,
    pool_id: int,
    *,
    canonical_name: str | None = None,
) -> str | None:
    """Merge one user account into another (admin tool)."""
    with db() as conn:
        keeper = conn.execute(
            "SELECT id, display_name FROM users WHERE id = ? AND pool_id = ?",
            (keeper_id, pool_id),
        ).fetchone()
        dup = conn.execute(
            "SELECT id, display_name FROM users WHERE id = ? AND pool_id = ?",
            (dup_id, pool_id),
        ).fetchone()
        if not keeper or not dup:
            return "One or both users not found in this pool."
        line = _merge_user_records(
            conn,
            keeper_id,
            dup_id,
            keeper_label=keeper["display_name"],
            dup_label=dup["display_name"],
            pool_id=pool_id,
        )
        if canonical_name:
            conn.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (canonical_name.strip(), keeper_id),
            )
    return line


def merge_users_named(display_name: str, pool_id: int | None = None) -> list[str]:
    """Merge every duplicate account matching this display name (normalized)."""
    key = normalize_display_name(display_name)
    if not key:
        return []
    merged: list[str] = []
    with db() as conn:
        pool_ids = (
            [pool_id]
            if pool_id is not None
            else [row["id"] for row in conn.execute("SELECT id FROM pools").fetchall()]
        )
        for pid in pool_ids:
            users = conn.execute(
                "SELECT id, display_name FROM users WHERE pool_id = ? ORDER BY id",
                (pid,),
            ).fetchall()
            group = [
                user
                for user in users
                if normalize_display_name(user["display_name"]) == key
            ]
            if len(group) < 2:
                continue
            keeper = max(group, key=lambda u: (_user_match_points(conn, u["id"]), -u["id"]))
            keeper_id = keeper["id"]
            for dup in group:
                if dup["id"] == keeper_id:
                    continue
                line = _merge_user_records(
                    conn,
                    keeper_id,
                    dup["id"],
                    keeper_label=keeper["display_name"],
                    dup_label=dup["display_name"],
                    pool_id=pid,
                )
                if line:
                    merged.append(line)

            conn.execute(
                "UPDATE users SET display_name = ? WHERE id = ?",
                (display_name.strip(), keeper_id),
            )
    return merged


def merge_duplicate_users(pool_id: int | None = None) -> list[str]:
    """Merge pool members that share the same normalized display name."""
    from ai_predictor import is_agent_badge

    merged: list[str] = []
    with db() as conn:
        if pool_id is None:
            pool_ids = [row["id"] for row in conn.execute("SELECT id FROM pools").fetchall()]
        else:
            pool_ids = [pool_id]

        for pid in pool_ids:
            users = conn.execute(
                "SELECT id, display_name, ai_agent_key FROM users WHERE pool_id = ? ORDER BY id",
                (pid,),
            ).fetchall()
            groups: dict[str, list] = defaultdict(list)
            for user in users:
                if is_agent_badge(user["display_name"], user["ai_agent_key"]):
                    continue
                groups[normalize_display_name(user["display_name"])].append(user)

            for group in groups.values():
                if len(group) < 2:
                    continue
                keeper = max(group, key=lambda u: (_user_match_points(conn, u["id"]), -u["id"]))
                keeper_id = keeper["id"]
                keeper_name = keeper["display_name"]
                for dup in group:
                    if dup["id"] == keeper_id:
                        continue
                    line = _merge_user_records(
                        conn,
                        keeper_id,
                        dup["id"],
                        keeper_label=keeper_name,
                        dup_label=dup["display_name"],
                        pool_id=pid,
                    )
                    if line:
                        merged.append(line)

    return merged


def align_match_schedule(match_id: int, kickoff_et) -> bool:
    """Update stored kickoff when the live feed disagrees by more than a few hours."""
    from scoring import parse_match_datetime

    new_date = kickoff_et.strftime("%Y-%m-%d")
    new_time = kickoff_et.strftime("%H:%M")
    with db() as conn:
        row = conn.execute(
            "SELECT match_date, match_time FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if not row:
            return False
        current = parse_match_datetime(row["match_date"], row["match_time"])
        if abs((kickoff_et - current).total_seconds()) <= 6 * 3600:
            return False
        conn.execute(
            "UPDATE matches SET match_date = ?, match_time = ? WHERE id = ?",
            (new_date, new_time, match_id),
        )
    return True


def _goal_event_key(team_side: str, minute: int, injury_minute: int | None) -> tuple[str, int, int]:
    return (team_side, minute, 0 if injury_minute is None else int(injury_minute))


def reconcile_synced_goals(
    match_id: int,
    expected: list[tuple[str, int, int | None]],
    *,
    authoritative: bool = False,
) -> int:
    """Drop feed-synced goals removed by the API (e.g. VAR offside)."""
    normalized = {_goal_event_key(side, minute, injury) for side, minute, injury in expected}
    removed = 0
    with db() as conn:
        if authoritative:
            rows = conn.execute(
                """
                SELECT id, team_side, minute, injury_minute
                FROM match_goals
                WHERE match_id = ?
                """,
                (match_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, team_side, minute, injury_minute
                FROM match_goals
                WHERE match_id = ? AND COALESCE(goal_source, 'sync') = 'sync'
                """,
                (match_id,),
            ).fetchall()
        for row in rows:
            key = _goal_event_key(row["team_side"], row["minute"], row["injury_minute"])
            if key not in normalized:
                conn.execute("DELETE FROM match_goals WHERE id = ?", (row["id"],))
                removed += 1
    return removed


def reconcile_synced_cards(
    match_id: int,
    expected: list[tuple[str, str, str]],
    *,
    authoritative: bool = False,
) -> int:
    """Drop cards removed by the feed (e.g. VAR overturn). Returns deletions."""
    normalized = {
        (player.strip(), team.strip(), card_type)
        for player, team, card_type in expected
        if player.strip() and team.strip() and card_type in ("yellow", "red")
    }
    removed = 0
    with db() as conn:
        if authoritative:
            rows = conn.execute(
                """
                SELECT id, player_name, team, card_type
                FROM player_cards
                WHERE match_id = ?
                """,
                (match_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, player_name, team, card_type
                FROM player_cards
                WHERE match_id = ? AND card_source = 'sync'
                """,
                (match_id,),
            ).fetchall()
        for row in rows:
            key = (row["player_name"], row["team"], row["card_type"])
            if key not in normalized:
                conn.execute("DELETE FROM player_cards WHERE id = ?", (row["id"],))
                removed += 1
    return removed


def match_dates_with_synced_cards() -> list[str]:
    """Distinct kickoff dates that still have cards on the board (for VAR reconciliation)."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT m.match_date
            FROM player_cards c
            JOIN matches m ON m.id = c.match_id
            ORDER BY m.match_date DESC
            """
        ).fetchall()
    return [row["match_date"] for row in rows]


# Cards overturned by VAR after being briefly shown in a live feed.
RESCINDED_VAR_CARDS = (
    {"player": "Tim Ream", "team": "USA", "card_type": "yellow", "home": "USA", "away": "Paraguay"},
)


def repair_rescinded_var_cards() -> int:
    """Remove known VAR-rescinded bookings that stale feeds left in the database."""
    removed = 0
    with db() as conn:
        for item in RESCINDED_VAR_CARDS:
            row = conn.execute(
                """
                SELECT c.id
                FROM player_cards c
                JOIN matches m ON m.id = c.match_id
                WHERE c.player_name = ? AND c.team = ? AND c.card_type = ?
                  AND m.home_team = ? AND m.away_team = ?
                """,
                (
                    item["player"],
                    item["team"],
                    item["card_type"],
                    item["home"],
                    item["away"],
                ),
            ).fetchone()
            if row:
                conn.execute("DELETE FROM player_cards WHERE id = ?", (row["id"],))
                removed += 1
    return removed


def repair_bogus_shootout_penalties() -> int:
    """Remove shootout rows wrongly synced from regular-time penalty goals."""
    removed = 0
    with db() as conn:
        cur = conn.execute(
            """
            DELETE FROM match_penalties
            WHERE minute > 120
              AND match_id IN (
                SELECT id FROM matches
                WHERE actual_home IS NOT NULL
                  AND actual_away IS NOT NULL
                  AND actual_home != actual_away
              )
            """
        )
        removed += cur.rowcount

        groups = conn.execute(
            """
            SELECT match_id, taker_team, COALESCE(taker_name, '') AS taker_name, outcome,
                   MIN(id) AS keep_id, COUNT(*) AS n
            FROM match_penalties
            WHERE minute > 120
            GROUP BY match_id, taker_team, taker_name, outcome
            HAVING n > 1
            """
        ).fetchall()
        for row in groups:
            cur = conn.execute(
                """
                DELETE FROM match_penalties
                WHERE match_id = ? AND taker_team = ?
                  AND COALESCE(taker_name, '') = ? AND outcome = ?
                  AND minute > 120 AND id != ?
                """,
                (
                    row["match_id"],
                    row["taker_team"],
                    row["taker_name"],
                    row["outcome"],
                    row["keep_id"],
                ),
            )
            removed += cur.rowcount
    return removed


def clear_match_live_state(match_id: int) -> None:
    """Reset a fixture to scheduled when it was wrongly marked live before kickoff."""
    with db() as conn:
        conn.execute(
            """
            UPDATE matches
            SET status = 'scheduled', live_home = NULL, live_away = NULL,
                live_minute = NULL, live_injury_minute = NULL
            WHERE id = ? AND actual_home IS NULL
            """,
            (match_id,),
        )


def repair_live_display_data() -> None:
    """Clear bogus live state left by bad API imports."""
    from datetime import datetime

    from scoring import TIMEZONE, parse_match_datetime

    now = datetime.now(TIMEZONE)
    with db() as conn:
        conn.execute("UPDATE matches SET live_minute = NULL WHERE live_minute = 0")
        conn.execute("DELETE FROM match_goals WHERE minute = 0")
        conn.execute(
            """
            UPDATE matches
            SET status = 'live', live_injury_minute = NULL
            WHERE status = 'halftime' AND live_minute > 45 AND actual_home IS NULL
            """
        )
        conn.execute(
            """
            UPDATE matches
            SET status = 'scheduled', live_home = NULL, live_away = NULL,
                live_minute = NULL, live_injury_minute = NULL
            WHERE actual_home IS NULL
              AND status IN ('live', 'halftime', 'hydration_break')
              AND COALESCE(live_home, 0) = 0
              AND COALESCE(live_away, 0) = 0
              AND id NOT IN (SELECT DISTINCT match_id FROM match_goals)
              AND id NOT IN (SELECT DISTINCT match_id FROM player_cards)
            """
        )
        rows = conn.execute(
            """
            SELECT id, match_date, match_time
            FROM matches
            WHERE actual_home IS NULL AND status IN ('live', 'halftime', 'hydration_break')
            """
        ).fetchall()
        from live_scores import LIVE_SYNC_MAX

        for row in rows:
            kickoff = parse_match_datetime(row["match_date"], row["match_time"])
            if now < kickoff or now >= kickoff + LIVE_SYNC_MAX:
                conn.execute(
                    """
                    UPDATE matches
                    SET status = 'scheduled', live_home = NULL, live_away = NULL,
                        live_minute = NULL, live_injury_minute = NULL
                    WHERE id = ? AND actual_home IS NULL
                    """,
                    (row["id"],),
                )


def sync_knockout_stage() -> dict:
    from knockout_sync import sync_knockout_stage as _sync

    return _sync()


def generate_invite_code() -> str:
    return secrets.token_urlsafe(6)


def ensure_admin_secrets() -> None:
    """Keep every pool on the configured admin password (survives redeploys)."""
    secret = FIXED_ADMIN_SECRET.strip()
    if not secret:
        return
    with db() as conn:
        conn.execute("UPDATE pools SET admin_secret = ?", (secret,))


def generate_admin_secret() -> str:
    return FIXED_ADMIN_SECRET


def create_pool(name: str) -> dict:
    invite_code = generate_invite_code()
    admin_secret = generate_admin_secret()
    with db() as conn:
        cur = conn.execute(
            "INSERT INTO pools (name, invite_code, admin_secret) VALUES (?, ?, ?)",
            (name.strip(), invite_code, admin_secret),
        )
        pool_id = cur.lastrowid
    return {"id": pool_id, "name": name.strip(), "invite_code": invite_code, "admin_secret": admin_secret}


def get_pool_by_code(invite_code: str) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM pools WHERE invite_code = ?", (invite_code,)).fetchone()


def get_pool_by_id(pool_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM pools WHERE id = ?", (pool_id,)).fetchone()


def update_admin_secret(new_secret: str, invite_code: str | None = None) -> list[str]:
    """Update admin_secret for one pool (by invite code) or all pools. Returns updated pool names."""
    secret = new_secret.strip()
    if not secret:
        raise ValueError("Admin secret cannot be empty.")
    with db() as conn:
        if invite_code:
            row = conn.execute(
                "SELECT id, name FROM pools WHERE invite_code = ?", (invite_code.strip(),)
            ).fetchone()
            if not row:
                raise ValueError(f"No pool found for invite code {invite_code!r}.")
            conn.execute(
                "UPDATE pools SET admin_secret = ? WHERE id = ?", (secret, row["id"])
            )
            return [row["name"]]
        rows = conn.execute("SELECT id, name FROM pools").fetchall()
        conn.execute("UPDATE pools SET admin_secret = ?", (secret,))
        return [row["name"] for row in rows]


def count_pool_users(pool_id: int) -> int:
    with db() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE pool_id = ?", (pool_id,)).fetchone()[0]


def add_user(pool_id: int, display_name: str) -> dict | str:
    name = display_name.strip()
    if not name:
        return "Display name is required."
    if len(name) > 40:
        return "Display name must be 40 characters or fewer."

    name_key = normalize_display_name(name)
    with db() as conn:
        rows = conn.execute(
            "SELECT id, display_name FROM users WHERE pool_id = ?",
            (pool_id,),
        ).fetchall()
        for existing in rows:
            if normalize_display_name(existing["display_name"]) == name_key:
                return {
                    "id": existing["id"],
                    "pool_id": pool_id,
                    "display_name": existing["display_name"],
                    "resumed": True,
                }

        user_count = conn.execute("SELECT COUNT(*) FROM users WHERE pool_id = ?", (pool_id,)).fetchone()[0]
        if user_count >= MAX_USERS_PER_POOL:
            return f"This pool is full ({MAX_USERS_PER_POOL} users max)."

        cur = conn.execute(
            "INSERT INTO users (pool_id, display_name) VALUES (?, ?)",
            (pool_id, name),
        )
        return {"id": cur.lastrowid, "pool_id": pool_id, "display_name": name, "resumed": False}


def get_pool_users(pool_id: int) -> list[sqlite3.Row]:
    with db() as conn:
        return conn.execute(
            "SELECT display_name FROM users WHERE pool_id = ? ORDER BY display_name",
            (pool_id,),
        ).fetchall()


def get_user(user_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def user_needs_password_setup(user: sqlite3.Row | dict) -> bool:
    from user_passwords import user_requires_password

    row = dict(user)
    if not user_requires_password(row["display_name"], row.get("ai_agent_key")):
        return False
    if row.get("password_must_set"):
        return True
    return not row.get("password_hash")


def set_user_password(user_id: int, plain_password: str) -> None:
    from user_passwords import hash_password

    with db() as conn:
        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, password_must_set = 0
            WHERE id = ?
            """,
            (hash_password(plain_password), user_id),
        )


def verify_user_password(user_id: int, plain_password: str) -> bool:
    from user_passwords import passwords_match

    with db() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        return False
    return passwords_match(plain_password, row["password_hash"])


def reset_user_password(user_id: int, pool_id: int) -> str | None:
    from ai_predictor import is_synced_ai_agent
    from media_predictors import is_media_agent
    from user_passwords import user_requires_password

    with db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND pool_id = ?",
            (user_id, pool_id),
        ).fetchone()
        if not user:
            return "User not found in this pool."
        if is_synced_ai_agent(user["display_name"], user["ai_agent_key"]):
            return "AI pool members do not use passwords."
        if is_media_agent(user["display_name"], user["ai_agent_key"]):
            return "Media pundit accounts do not use passwords."
        if not user_requires_password(user["display_name"], user["ai_agent_key"]):
            return "This account does not use a password."
        conn.execute(
            """
            UPDATE users
            SET password_hash = NULL, password_must_set = 1
            WHERE id = ?
            """,
            (user_id,),
        )
    return None


def mark_user_photo_updated(user_id: int) -> None:
    with db() as conn:
        conn.execute(
            "UPDATE users SET photo_updated_at = datetime('now') WHERE id = ?",
            (user_id,),
        )


def clear_user_photo(user_id: int) -> None:
    from user_avatars import delete_avatar_file

    delete_avatar_file(user_id)
    with db() as conn:
        conn.execute("UPDATE users SET photo_updated_at = NULL WHERE id = ?", (user_id,))


def get_distinct_teams() -> list[str]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT home_team AS team FROM matches
            UNION
            SELECT away_team AS team FROM matches
            ORDER BY team
            """
        ).fetchall()
    return [r["team"] for r in rows]


def get_sync_meta(key: str) -> str | None:
    with db() as conn:
        row = conn.execute("SELECT value FROM sync_meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_sync_meta(key: str, value: str) -> None:
    with db() as conn:
        conn.execute(
            "INSERT INTO sync_meta (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def try_begin_live_sync(cooldown_seconds: int) -> bool:
    import time

    now = time.time()
    with db() as conn:
        row = conn.execute("SELECT value FROM sync_meta WHERE key = 'live_sync_at'").fetchone()
        if row:
            try:
                if now - float(row["value"]) < cooldown_seconds:
                    return False
            except ValueError:
                pass
        conn.execute(
            "INSERT INTO sync_meta (key, value) VALUES ('live_sync_at', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (str(now),),
        )
    return True


def upsert_player_card(
    match_id: int,
    player_name: str,
    team: str,
    card_type: str,
    minute: int | None = None,
) -> bool:
    """Insert or refresh a card from the live API feed."""
    name = player_name.strip()
    team_name = team.strip()
    if not name or not team_name or card_type not in ("yellow", "red"):
        return False
    with db() as conn:
        existing = conn.execute(
            """
            SELECT id, minute FROM player_cards
            WHERE match_id = ? AND player_name = ? AND team = ? AND card_type = ?
            """,
            (match_id, name, team_name, card_type),
        ).fetchone()
        if existing:
            if minute is not None and existing["minute"] is None:
                conn.execute(
                    "UPDATE player_cards SET minute = ?, card_source = 'sync' WHERE id = ?",
                    (minute, existing["id"]),
                )
                return True
            return False
        conn.execute(
            """
            INSERT INTO player_cards (match_id, player_name, team, card_type, minute, card_source)
            VALUES (?, ?, ?, ?, ?, 'sync')
            """,
            (match_id, name, team_name, card_type, minute),
        )
    return True


def import_player_card(
    match_id: int,
    player_name: str,
    team: str,
    card_type: str,
    minute: int | None = None,
) -> bool:
    """Insert a card from an external feed if not already recorded."""
    return upsert_player_card(match_id, player_name, team, card_type, minute)


def import_match_penalty(
    match_id: int,
    taker_team: str,
    outcome: str,
    minute: int,
    taker_name: str | None = None,
    injury_minute: int | None = None,
) -> bool:
    """Insert a penalty event from an external feed if not already recorded. Does not bump score."""
    team = taker_team.strip()
    taker = (taker_name or "").strip() or None
    if not team or outcome not in ("scored", "saved", "missed"):
        return False
    with db() as conn:
        match = conn.execute("SELECT home_team, away_team FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match or team not in (match["home_team"], match["away_team"]):
            return False
        existing = conn.execute(
            """
            SELECT id FROM match_penalties
            WHERE match_id = ? AND taker_team = ? AND outcome = ? AND minute = ?
                  AND COALESCE(injury_minute, 0) = COALESCE(?, 0)
                  AND COALESCE(taker_name, '') = COALESCE(?, '')
            """,
            (match_id, team, outcome, minute, injury_minute, taker or ""),
        ).fetchone()
        if existing:
            return False
        conn.execute(
            """
            INSERT INTO match_penalties
            (match_id, taker_team, taker_name, goalkeeper_name, outcome, minute, injury_minute)
            VALUES (?, ?, ?, NULL, ?, ?, ?)
            """,
            (match_id, team, taker, outcome, minute, injury_minute),
        )
    return True


def upsert_match_goal(
    match_id: int,
    team_side: str,
    scorer_name: str,
    minute: int,
    injury_minute: int | None = None,
    is_penalty: bool = False,
) -> bool:
    """Insert or refresh a goal from the live API feed."""
    name = scorer_name.strip() or "Unknown scorer"
    if team_side not in ("home", "away") or minute < 1:
        return False
    with db() as conn:
        existing = conn.execute(
            """
            SELECT id, scorer_name, is_penalty FROM match_goals
            WHERE match_id = ? AND team_side = ? AND minute = ?
                  AND COALESCE(injury_minute, 0) = COALESCE(?, 0)
            """,
            (match_id, team_side, minute, injury_minute),
        ).fetchone()
        if existing:
            old_name = (existing["scorer_name"] or "").strip()
            penalty_flag = 1 if is_penalty else 0
            if (
                name != "Unknown scorer"
                and old_name in {"", "Unknown scorer"}
            ):
                conn.execute(
                    """
                    UPDATE match_goals
                    SET scorer_name = ?, is_penalty = ?
                    WHERE id = ?
                    """,
                    (name, penalty_flag, existing["id"]),
                )
                return True
            if is_penalty and not bool(existing["is_penalty"]):
                conn.execute(
                    "UPDATE match_goals SET is_penalty = 1 WHERE id = ?",
                    (existing["id"],),
                )
                return True
            return False

        placeholder = conn.execute(
            """
            SELECT id FROM match_goals
            WHERE match_id = ? AND team_side = ? AND minute = 0
            ORDER BY id ASC LIMIT 1
            """,
            (match_id, team_side),
        ).fetchone()
        if placeholder:
            conn.execute(
                """
                UPDATE match_goals
                SET scorer_name = ?, minute = ?, injury_minute = ?, is_penalty = ?
                WHERE id = ?
                """,
                (name, minute, injury_minute, 1 if is_penalty else 0, placeholder["id"]),
            )
            return True

        conn.execute(
            """
            INSERT INTO match_goals (match_id, team_side, scorer_name, minute, injury_minute, is_penalty, goal_source)
            VALUES (?, ?, ?, ?, ?, ?, 'sync')
            """,
            (match_id, team_side, name, minute, injury_minute, 1 if is_penalty else 0),
        )
    return True


def import_match_goal(
    match_id: int,
    team_side: str,
    scorer_name: str,
    minute: int,
    injury_minute: int | None = None,
    is_penalty: bool = False,
) -> bool:
    """Insert a goal from an external feed if not already recorded. Does not bump live score."""
    return upsert_match_goal(
        match_id, team_side, scorer_name, minute, injury_minute, is_penalty
    )


def get_all_matches(stage: str | None = None) -> list[sqlite3.Row]:
    with db() as conn:
        if stage:
            return conn.execute(
                "SELECT * FROM matches WHERE stage = ? ORDER BY sort_order, match_date, match_time",
                (stage,),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM matches ORDER BY sort_order, match_date, match_time"
        ).fetchall()


def get_prediction(user_id: int, match_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM predictions WHERE user_id = ? AND match_id = ?",
            (user_id, match_id),
        ).fetchone()


def upsert_prediction(
    user_id: int,
    match_id: int,
    home_score: int,
    away_score: int,
    is_bold: bool | None = None,
) -> None:
    with db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            raise ValueError("Match not found")

        existing = conn.execute(
            "SELECT is_bold, points_excluded FROM predictions WHERE user_id = ? AND match_id = ?",
            (user_id, match_id),
        ).fetchone()
        if is_bold is None:
            bold = bool(existing["is_bold"]) if existing else False
        else:
            bold = bool(is_bold)
        excluded = bool(existing and existing["points_excluded"])
        if excluded:
            points = None
        else:
            points = calculate_points(
                home_score, away_score, match["actual_home"], match["actual_away"], bool(bold)
            )
        conn.execute(
            """
            INSERT INTO predictions (user_id, match_id, home_score, away_score, points, is_bold)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, match_id) DO UPDATE SET
                home_score = excluded.home_score,
                away_score = excluded.away_score,
                points = excluded.points,
                is_bold = excluded.is_bold,
                submitted_at = datetime('now')
            """,
            (user_id, match_id, home_score, away_score, points, 1 if bold else 0),
        )


def set_bold_pick(user_id: int, match_id: int, *, admin_bypass: bool = False) -> str | None:
    from scoring import bold_day_key, bold_pick_change_allowed, is_prediction_open

    with db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            return "Match not found."
        pred = conn.execute(
            "SELECT * FROM predictions WHERE user_id = ? AND match_id = ?",
            (user_id, match_id),
        ).fetchone()
        if not pred:
            return "Save a prediction for this match first."

        if not admin_bypass and not is_prediction_open(match["match_date"], match["match_time"]):
            return "Bold picks are locked — the prediction deadline has passed."

        key = bold_day_key(dict(match))
        existing_bold_match = None
        siblings = conn.execute(
            """
            SELECT p.id, p.match_id, p.home_score, p.away_score, p.is_bold, p.points_excluded,
                   m.actual_home, m.actual_away, m.match_date, m.match_time, m.matchday, m.stage
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.user_id = ?
            """,
            (user_id,),
        ).fetchall()

        for row in siblings:
            if bold_day_key(dict(row)) == key and row["is_bold"] and row["match_id"] != match_id:
                existing_bold_match = conn.execute(
                    "SELECT * FROM matches WHERE id = ?", (row["match_id"],)
                ).fetchone()
                break

        if not admin_bypass and not bold_pick_change_allowed(
            dict(match), dict(existing_bold_match) if existing_bold_match else None
        ):
            return "Bold pick is locked — your bold match deadline has passed."

        for row in siblings:
            if bold_day_key(dict(row)) != key:
                continue
            new_bold = 1 if row["match_id"] == match_id else 0
            if row["points_excluded"]:
                pts = 0
            else:
                pts = calculate_points(
                    row["home_score"],
                    row["away_score"],
                    row["actual_home"],
                    row["actual_away"],
                    bool(new_bold),
                )
            conn.execute(
                "UPDATE predictions SET is_bold = ?, points = ? WHERE id = ?",
                (new_bold, pts, row["id"]),
            )
    return None


def get_user_bold_by_day(user_id: int) -> dict[str, int]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.match_id, p.is_bold, m.match_date, m.matchday, m.stage
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            WHERE p.user_id = ? AND p.is_bold = 1
            """,
            (user_id,),
        ).fetchall()
    return {bold_day_key(dict(r)): r["match_id"] for r in rows}


def update_match_result(match_id: int, actual_home: int, actual_away: int) -> bool:
    from datetime import datetime

    from scoring import TIMEZONE, parse_match_datetime

    with db() as conn:
        match = conn.execute(
            "SELECT match_date, match_time FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if not match:
            return False
        kickoff = parse_match_datetime(match["match_date"], match["match_time"])
        if datetime.now(TIMEZONE) < kickoff:
            return False

        conn.execute(
            """
            UPDATE matches SET actual_home = ?, actual_away = ?, status = 'finished',
                   live_home = ?, live_away = ?, live_minute = 90
            WHERE id = ?
            """,
            (actual_home, actual_away, actual_home, actual_away, match_id),
        )
        predictions = conn.execute(
            "SELECT id, home_score, away_score, points_excluded FROM predictions WHERE match_id = ?",
            (match_id,),
        ).fetchall()
        for pred in predictions:
            if pred["points_excluded"]:
                conn.execute("UPDATE predictions SET points = NULL WHERE id = ?", (pred["id"],))
                continue
            row = conn.execute(
                "SELECT is_bold FROM predictions WHERE id = ?",
                (pred["id"],),
            ).fetchone()
            points = calculate_points(
                pred["home_score"],
                pred["away_score"],
                actual_home,
                actual_away,
                bool(row["is_bold"]) if row else False,
            )
            conn.execute("UPDATE predictions SET points = ? WHERE id = ?", (points, pred["id"]))
    return True


def format_goal_minute(minute: int, injury_minute: int | None = None) -> str:
    if minute < 1:
        return "—"
    if injury_minute:
        return f"{minute}+{injury_minute}'"
    return f"{minute}'"


def get_match_cards(match_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.*, m.home_team, m.away_team
            FROM player_cards c
            JOIN matches m ON m.id = c.match_id
            WHERE c.match_id = ?
            ORDER BY COALESCE(c.minute, 0) ASC, c.id ASC
            """,
            (match_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["minute_label"] = format_goal_minute(r["minute"] or 0, None) if r["minute"] is not None else ""
            if r["team"] == r["home_team"]:
                d["team_side"] = "home"
            elif r["team"] == r["away_team"]:
                d["team_side"] = "away"
            else:
                d["team_side"] = None
            result.append(d)
        return result


def get_tournament_cards_by_team() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT team,
                   SUM(CASE WHEN card_type = 'yellow' THEN 1 ELSE 0 END) AS yellow_count,
                   SUM(CASE WHEN card_type = 'red' THEN 1 ELSE 0 END) AS red_count,
                   COUNT(*) AS total_cards
            FROM player_cards
            GROUP BY team
            ORDER BY team ASC
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_tournament_goals_by_team(*, sort_by_team: bool = False) -> list[dict]:
    """Goals scored and conceded per nation from match scorelines."""
    from collections import defaultdict

    from live_scores import apply_live_state

    totals: dict[str, dict[str, int]] = defaultdict(lambda: {"gf": 0, "ga": 0})

    for row in get_all_matches():
        match = apply_live_state(dict(row))
        home = match.get("display_home")
        away = match.get("display_away")
        if home is None or away is None:
            continue
        if not match.get("is_finished") and not match.get("is_live"):
            continue
        home_team = row["home_team"]
        away_team = row["away_team"]
        totals[home_team]["gf"] += int(home)
        totals[home_team]["ga"] += int(away)
        totals[away_team]["gf"] += int(away)
        totals[away_team]["ga"] += int(home)

    teams = sorted(totals.keys()) if sort_by_team else sorted(
        totals.keys(),
        key=lambda t: (-totals[t]["gf"], totals[t]["ga"], t),
    )
    return [
        {
            "team": team,
            "goals": totals[team]["gf"],
            "gf": totals[team]["gf"],
            "ga": totals[team]["ga"],
            "gd": totals[team]["gf"] - totals[team]["ga"],
        }
        for team in teams
        if totals[team]["gf"] or totals[team]["ga"]
    ]


def get_match_goals(match_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT g.*, m.home_team, m.away_team,
                   CASE WHEN g.team_side = 'home' THEN m.home_team ELSE m.away_team END AS team_name
            FROM match_goals g
            JOIN matches m ON m.id = g.match_id
            WHERE g.match_id = ?
            ORDER BY g.minute ASC, COALESCE(g.injury_minute, 0) ASC, g.id ASC
            """,
            (match_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["team_name"] = r["home_team"] if r["team_side"] == "home" else r["away_team"]
            d["minute_label"] = format_goal_minute(r["minute"], r["injury_minute"])
            d["is_penalty"] = bool(r["is_penalty"])
            result.append(d)
        return result


def _bump_live_score(conn, match, team_side: str, delta: int = 1) -> None:
    if match["actual_home"] is not None:
        return
    from datetime import datetime

    from live_scores import is_match_in_progress
    from scoring import TIMEZONE, parse_match_datetime

    kickoff = parse_match_datetime(match["match_date"], match["match_time"])
    in_progress = is_match_in_progress(kickoff, datetime.now(TIMEZONE), dict(match))
    col = "live_home" if team_side == "home" else "live_away"
    current = match[col] if match[col] is not None else 0
    other_col = "live_away" if team_side == "home" else "live_home"
    other = match[other_col] if match[other_col] is not None else 0
    new_status = "live" if in_progress else match["status"] or "scheduled"
    conn.execute(
        f"""
        UPDATE matches SET {col} = ?, {other_col} = ?, status = ?
        WHERE id = ?
        """,
        (current + delta, other, new_status, match["id"]),
    )


def add_match_goal(
    match_id: int,
    team_side: str,
    scorer_name: str,
    minute: int,
    injury_minute: int | None = None,
    is_penalty: bool = False,
) -> dict | str:
    name = scorer_name.strip()
    if not name:
        return "Scorer name is required."
    if len(name) > 60:
        return "Scorer name must be 60 characters or fewer."
    if team_side not in ("home", "away"):
        return "Invalid team."
    if minute < 0 or minute > 120:
        return "Minute must be between 0 and 120."

    with db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            return "Match not found."

        cur = conn.execute(
            """
            INSERT INTO match_goals (match_id, team_side, scorer_name, minute, injury_minute, is_penalty, goal_source)
            VALUES (?, ?, ?, ?, ?, ?, 'admin')
            """,
            (match_id, team_side, name, minute, injury_minute, 1 if is_penalty else 0),
        )

        _bump_live_score(conn, match, team_side)

        return {"id": cur.lastrowid, "scorer_name": name}


def delete_match_goal(goal_id: int) -> str | None:
    with db() as conn:
        goal = conn.execute(
            """
            SELECT g.*, m.actual_home, m.live_home, m.live_away
            FROM match_goals g
            JOIN matches m ON m.id = g.match_id
            WHERE g.id = ?
            """,
            (goal_id,),
        ).fetchone()
        if not goal:
            return "Goal not found."

        conn.execute("DELETE FROM match_goals WHERE id = ?", (goal_id,))

        if goal["actual_home"] is None:
            reconcile_live_score_from_goals(goal["match_id"], goals_removed=1)
        return None


def get_tournament_scorer_leaderboard(*, group_by_team: bool = False) -> list[dict]:
    """Aggregate all match goals into a top-scorers table."""
    with db() as conn:
        order = "team ASC, player_name ASC" if group_by_team else "goals DESC, player_name ASC"
        rows = conn.execute(
            f"""
            SELECT g.scorer_name AS player_name,
                   CASE WHEN g.team_side = 'home' THEN m.home_team ELSE m.away_team END AS team,
                   COUNT(*) AS goals
            FROM match_goals g
            JOIN matches m ON m.id = g.match_id
            GROUP BY lower(g.scorer_name), team
            ORDER BY {order}
            """
        ).fetchall()
        return [dict(r) for r in rows]


def get_tournament_scorer_events() -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT g.id, g.scorer_name AS player_name,
                   CASE WHEN g.team_side = 'home' THEN m.home_team ELSE m.away_team END AS team,
                   g.minute, g.injury_minute, g.is_penalty, m.home_team, m.away_team, m.match_date
            FROM match_goals g
            JOIN matches m ON m.id = g.match_id
            ORDER BY m.match_date ASC, g.minute ASC, g.id ASC
            """
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["minute_label"] = format_goal_minute(r["minute"], r["injury_minute"])
            d["match_label"] = f"{r['home_team']} vs {r['away_team']}"
            d["is_penalty"] = bool(r["is_penalty"])
            result.append(d)
        return result


def add_player_card(
    match_id: int,
    player_name: str,
    team: str,
    card_type: str,
    minute: int | None = None,
) -> dict | str:
    name = player_name.strip()
    team_name = team.strip()
    if not name or not team_name:
        return "Player name and team are required."
    if card_type not in ("yellow", "red"):
        return "Card type must be yellow or red."

    with db() as conn:
        cur = conn.execute(
            """
            INSERT INTO player_cards (match_id, player_name, team, card_type, minute, card_source)
            VALUES (?, ?, ?, ?, ?, 'admin')
            """,
            (match_id, name, team_name, card_type, minute),
        )
        return {"id": cur.lastrowid}


def delete_player_card(card_id: int) -> str | None:
    with db() as conn:
        if not conn.execute("SELECT id FROM player_cards WHERE id = ?", (card_id,)).fetchone():
            return "Card not found."
        conn.execute("DELETE FROM player_cards WHERE id = ?", (card_id,))
        return None


def get_match_penalties(match_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, m.home_team, m.away_team
            FROM match_penalties p
            JOIN matches m ON m.id = p.match_id
            WHERE p.match_id = ?
            ORDER BY p.minute ASC, COALESCE(p.injury_minute, 0) ASC, p.id ASC
            """,
            (match_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["minute_label"] = format_goal_minute(r["minute"], r["injury_minute"])
            result.append(d)
        return result


def add_match_penalty(
    match_id: int,
    taker_team: str,
    outcome: str,
    minute: int,
    taker_name: str | None = None,
    goalkeeper_name: str | None = None,
    injury_minute: int | None = None,
) -> dict | str:
    team = taker_team.strip()
    if not team:
        return "Team is required."
    if outcome not in ("scored", "saved", "missed"):
        return "Outcome must be scored, saved, or missed."
    if minute < 0 or minute > 120:
        return "Minute must be between 0 and 120."

    with db() as conn:
        match = conn.execute("SELECT * FROM matches WHERE id = ?", (match_id,)).fetchone()
        if not match:
            return "Match not found."
        if team not in (match["home_team"], match["away_team"]):
            return "Team must be home or away in this match."

        cur = conn.execute(
            """
            INSERT INTO match_penalties
            (match_id, taker_team, taker_name, goalkeeper_name, outcome, minute, injury_minute)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                match_id,
                team,
                (taker_name or "").strip() or None,
                (goalkeeper_name or "").strip() or None,
                outcome,
                minute,
                injury_minute,
            ),
        )

        if outcome == "scored":
            team_side = "home" if team == match["home_team"] else "away"
            scorer = (taker_name or "").strip() or "Penalty"
            conn.execute(
                """
                INSERT INTO match_goals (match_id, team_side, scorer_name, minute, injury_minute, is_penalty)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (match_id, team_side, scorer, minute, injury_minute),
            )
            _bump_live_score(conn, match, team_side)

        return {"id": cur.lastrowid}


def delete_match_penalty(penalty_id: int) -> str | None:
    with db() as conn:
        row = conn.execute(
            """
            SELECT p.*, m.home_team, m.away_team, m.actual_home, m.live_home, m.live_away
            FROM match_penalties p
            JOIN matches m ON m.id = p.match_id
            WHERE p.id = ?
            """,
            (penalty_id,),
        ).fetchone()
        if not row:
            return "Penalty event not found."

        if row["outcome"] == "scored":
            goal = conn.execute(
                """
                SELECT id FROM match_goals
                WHERE match_id = ? AND is_penalty = 1 AND minute = ?
                  AND team_side = ?
                ORDER BY id DESC LIMIT 1
                """,
                (
                    row["match_id"],
                    row["minute"],
                    "home" if row["taker_team"] == row["home_team"] else "away",
                ),
            ).fetchone()
            if goal:
                conn.execute("DELETE FROM match_goals WHERE id = ?", (goal["id"],))
                if row["actual_home"] is None:
                    team_side = "home" if row["taker_team"] == row["home_team"] else "away"
                    col = "live_home" if team_side == "home" else "live_away"
                    current = row[col] if row[col] is not None else 0
                    conn.execute(
                        f"UPDATE matches SET {col} = ? WHERE id = ?",
                        (max(0, current - 1), row["match_id"]),
                    )

        conn.execute("DELETE FROM match_penalties WHERE id = ?", (penalty_id,))
        return None


def get_player_cards_table() -> list[dict]:
    from player_stats import card_suspension_status

    with db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.player_name, c.team, c.card_type, c.minute,
                   m.home_team, m.away_team, m.match_date
            FROM player_cards c
            JOIN matches m ON m.id = c.match_id
            ORDER BY m.match_date ASC, c.minute ASC, c.id ASC
            """
        ).fetchall()

        by_player: dict[str, dict] = {}
        events = []
        for r in rows:
            d = dict(r)
            d["match_label"] = f"{r['home_team']} vs {r['away_team']}"
            events.append(d)
            key = f"{r['player_name'].lower()}|{r['team']}"
            if key not in by_player:
                by_player[key] = {
                    "player_name": r["player_name"],
                    "team": r["team"],
                    "yellow_count": 0,
                    "red_count": 0,
                    "events": [],
                }
            by_player[key]["events"].append(d)
            if r["card_type"] == "yellow":
                by_player[key]["yellow_count"] += 1
            else:
                by_player[key]["red_count"] += 1

        summary = []
        for p in by_player.values():
            p["status"] = card_suspension_status(p["yellow_count"], p["red_count"])
            p["total_cards"] = p["yellow_count"] + p["red_count"]
            summary.append(p)

        summary.sort(key=lambda x: (x["team"].lower(), x["player_name"].lower()))
        return {"events": events, "summary": summary}


def get_match_goal_counts(match_id: int) -> tuple[int, int]:
    """Return (home_goals, away_goals) from synced match_goals rows."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT team_side, COUNT(*) AS n
            FROM match_goals
            WHERE match_id = ?
            GROUP BY team_side
            """,
            (match_id,),
        ).fetchall()
    home = away = 0
    for row in rows:
        if row["team_side"] == "home":
            home = int(row["n"])
        elif row["team_side"] == "away":
            away = int(row["n"])
    return home, away


def reconcile_live_score_from_goals(
    match_id: int,
    *,
    goals_removed: int = 0,
) -> bool:
    """Adjust live score from goal events without overriding a higher API score.

    After VAR disallows a goal (goals_removed > 0), trust the goal tally.
    When goal events lead the published score, raise to match.
    """
    with db() as conn:
        match = conn.execute(
            "SELECT live_home, live_away, actual_home FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if not match or match["actual_home"] is not None:
            return False
        goal_home, goal_away = get_match_goal_counts(match_id)
        live_home = int(match["live_home"] or 0)
        live_away = int(match["live_away"] or 0)
        if goals_removed > 0:
            new_home, new_away = goal_home, goal_away
        elif goal_home > live_home or goal_away > live_away:
            new_home = max(live_home, goal_home)
            new_away = max(live_away, goal_away)
        else:
            return False
        if new_home == live_home and new_away == live_away:
            return False
        conn.execute(
            """
            UPDATE matches
            SET live_home = ?, live_away = ?
            WHERE id = ? AND actual_home IS NULL
            """,
            (new_home, new_away, match_id),
        )
        return True


def reconcile_all_live_scores_from_goals() -> int:
    """Raise live scores that lag behind recorded goal events."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT id FROM matches
            WHERE actual_home IS NULL
              AND status IN ('live', 'halftime', 'hydration_break', 'extra_time', 'penalty_shootout')
            """
        ).fetchall()
    fixed = 0
    for row in rows:
        if reconcile_live_score_from_goals(row["id"]):
            fixed += 1
    return fixed


def update_match_live(
    match_id: int,
    live_home: int,
    live_away: int,
    live_minute: int | None,
    status: str = "live",
    live_injury_minute: int | None = None,
) -> None:
    from datetime import datetime

    from scoring import TIMEZONE, parse_match_datetime

    with db() as conn:
        row = conn.execute(
            "SELECT match_date, match_time FROM matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if row and status in ("live", "halftime", "hydration_break", "extra_time", "penalty_shootout"):
            kickoff = parse_match_datetime(row["match_date"], row["match_time"])
            if datetime.now(TIMEZONE) < kickoff:
                return
        if live_minute is not None and live_minute > 0:
            if live_injury_minute is not None:
                conn.execute(
                    """
                    UPDATE matches SET live_home = ?, live_away = ?, live_minute = ?,
                           live_injury_minute = ?,
                           status = CASE WHEN ? = 'scheduled' THEN 'scheduled' ELSE ? END
                    WHERE id = ? AND actual_home IS NULL
                    """,
                    (
                        live_home,
                        live_away,
                        live_minute,
                        live_injury_minute,
                        status,
                        status,
                        match_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE matches SET live_home = ?, live_away = ?, live_minute = ?,
                           live_injury_minute = NULL,
                           status = CASE WHEN ? = 'scheduled' THEN 'scheduled' ELSE ? END
                    WHERE id = ? AND actual_home IS NULL
                    """,
                    (live_home, live_away, live_minute, status, status, match_id),
                )
        else:
            conn.execute(
                """
                UPDATE matches SET live_home = ?, live_away = ?,
                       status = CASE WHEN ? = 'scheduled' THEN 'scheduled' ELSE ? END
                WHERE id = ? AND actual_home IS NULL
                """,
                (live_home, live_away, status, status, match_id),
            )


def ensure_ai_user(pool_id: int, display_name: str, agent_key: str | None = None) -> int:
    with db() as conn:
        if agent_key:
            existing = conn.execute(
                "SELECT id FROM users WHERE pool_id = ? AND ai_agent_key = ?",
                (pool_id, agent_key),
            ).fetchone()
            if existing:
                return existing["id"]
        existing = conn.execute(
            "SELECT id FROM users WHERE pool_id = ? AND display_name = ?",
            (pool_id, display_name),
        ).fetchone()
        if existing:
            if agent_key:
                conn.execute(
                    "UPDATE users SET ai_agent_key = ? WHERE id = ?",
                    (agent_key, existing["id"]),
                )
            return existing["id"]
        cur = conn.execute(
            "INSERT INTO users (pool_id, display_name, ai_agent_key) VALUES (?, ?, ?)",
            (pool_id, display_name, agent_key),
        )
        return cur.lastrowid


def ensure_all_ai_users(pool_id: int) -> list[int]:
    from ai_predictor import AI_AGENTS, REMOVED_SYNC_AGENTS

    ids = []
    for agent in AI_AGENTS:
        if agent["key"] in REMOVED_SYNC_AGENTS:
            continue
        ids.append(ensure_ai_user(pool_id, agent["display_name"], agent["key"]))
    return ids


def sync_ai_predictions(pool_id: int) -> int:
    from ai_predictor import AI_AGENTS, REMOVED_SYNC_AGENTS, predict_score
    from scoring import is_prediction_open, match_teams_known

    saved = 0
    matches = get_all_matches()
    for agent in AI_AGENTS:
        if agent["key"] in REMOVED_SYNC_AGENTS:
            continue
        ai_id = ensure_ai_user(pool_id, agent["display_name"], agent["key"])
        for m in matches:
            if not is_prediction_open(m["match_date"], m["match_time"]):
                continue
            pred = get_prediction(ai_id, m["id"])
            if not match_teams_known(m["home_team"], m["away_team"]):
                if pred:
                    with db() as conn:
                        conn.execute(
                            "DELETE FROM predictions WHERE user_id = ? AND match_id = ?",
                            (ai_id, m["id"]),
                        )
                continue
            home, away = predict_score(m["home_team"], m["away_team"], m["id"], agent["key"])
            if pred and pred["home_score"] == home and pred["away_score"] == away:
                continue
            if pred:
                upsert_prediction(ai_id, m["id"], home, away)
                saved += 1
            else:
                upsert_prediction(ai_id, m["id"], home, away)
                saved += 1
    return saved


def sync_nostradamus_predictions(pool_id: int) -> int:
    """Sync Cursor AI algorithm picks onto the Nostradamus pool member."""
    from ai_predictor import LEGACY_PREDICTIONS_AGENT_KEY, predict_score
    from scoring import is_prediction_open, match_teams_known

    with db() as conn:
        keeper = _find_nostradamus_keeper(conn, pool_id)
        if not keeper:
            return 0
        keeper_id = keeper["id"]
        if keeper["ai_agent_key"] != LEGACY_PREDICTIONS_AGENT_KEY:
            conn.execute(
                "UPDATE users SET ai_agent_key = ? WHERE id = ?",
                (LEGACY_PREDICTIONS_AGENT_KEY, keeper_id),
            )

    saved = 0
    matches = get_all_matches()
    for m in matches:
        if not is_prediction_open(m["match_date"], m["match_time"]):
            continue
        pred = get_prediction(keeper_id, m["id"])
        if not match_teams_known(m["home_team"], m["away_team"]):
            if pred:
                with db() as conn:
                    conn.execute(
                        "DELETE FROM predictions WHERE user_id = ? AND match_id = ?",
                        (keeper_id, m["id"]),
                    )
            continue
        home, away = predict_score(m["home_team"], m["away_team"], m["id"], "cursor")
        if pred and pred["home_score"] == home and pred["away_score"] == away:
            continue
        upsert_prediction(keeper_id, m["id"], home, away)
        saved += 1
    return saved


def sync_ai_tournament_vote(pool_id: int) -> bool:
    from ai_predictor import AI_AGENTS, REMOVED_SYNC_AGENTS, predict_tournament_picks
    from scoring import is_tournament_vote_open

    if not is_tournament_vote_open():
        return False

    changed = False
    for agent in AI_AGENTS:
        if agent["key"] in REMOVED_SYNC_AGENTS:
            continue
        ai_id = ensure_ai_user(pool_id, agent["display_name"], agent["key"])
        if get_tournament_vote(ai_id):
            continue
        picks = predict_tournament_picks(pool_id, agent["key"])
        result = upsert_tournament_vote(
            ai_id,
            picks["top_scorer"],
            picks["winner"],
            picks["second_place"],
            picks["third_place"],
        )
        if not isinstance(result, str):
            changed = True
    return changed


def ensure_all_media_users(pool_id: int) -> list[int]:
    from media_predictors import MEDIA_PREDICTORS

    ids = []
    for agent in MEDIA_PREDICTORS:
        ids.append(ensure_ai_user(pool_id, agent["display_name"], agent["key"]))
    return ids


def sync_media_predictions(pool_id: int) -> int:
    from media_predictors import MEDIA_PREDICTORS, get_media_match_predictions

    saved = 0
    matches = get_all_matches()
    for agent in MEDIA_PREDICTORS:
        user_id = ensure_ai_user(pool_id, agent["display_name"], agent["key"])
        picks = get_media_match_predictions(agent["key"])
        if not picks:
            continue
        for match in matches:
            key = (match["home_team"], match["away_team"])
            score = picks.get(key)
            if not score:
                continue
            home, away = score
            pred = get_prediction(user_id, match["id"])
            if pred and pred["home_score"] == home and pred["away_score"] == away:
                continue
            upsert_prediction(user_id, match["id"], home, away)
            saved += 1
    return saved


def sync_media_tournament_vote(pool_id: int) -> bool:
    from media_predictors import MEDIA_PREDICTORS, get_media_tournament_picks

    changed = False
    for agent in MEDIA_PREDICTORS:
        picks = get_media_tournament_picks(agent["key"])
        if not picks:
            continue
        user_id = ensure_ai_user(pool_id, agent["display_name"], agent["key"])
        result = upsert_tournament_vote(
            user_id,
            picks["top_scorer"],
            picks["winner"],
            picks["second_place"],
            picks["third_place"],
        )
        if not isinstance(result, str):
            changed = True
    return changed


def ensure_media_in_all_pools() -> None:
    with db() as conn:
        pools = conn.execute("SELECT id FROM pools").fetchall()
    for pool in pools:
        ensure_all_media_users(pool["id"])
        sync_media_predictions(pool["id"])
        sync_media_tournament_vote(pool["id"])


def ensure_ai_in_all_pools() -> None:
    from ai_predictor import AI_PREDICTOR_VERSION

    version_key = "ai_predictor_version"
    if get_sync_meta(version_key) != str(AI_PREDICTOR_VERSION):
        set_sync_meta(version_key, str(AI_PREDICTOR_VERSION))

    with db() as conn:
        pools = conn.execute("SELECT id FROM pools").fetchall()
    for pool in pools:
        ensure_all_ai_users(pool["id"])
        sync_ai_predictions(pool["id"])
        sync_nostradamus_predictions(pool["id"])
        sync_ai_tournament_vote(pool["id"])
        ensure_all_media_users(pool["id"])
        sync_media_predictions(pool["id"])
        sync_media_tournament_vote(pool["id"])


def add_knockout_match(
    home_team: str,
    away_team: str,
    match_date: str,
    match_time: str,
    venue: str,
    stage: str,
) -> int:
    with db() as conn:
        max_order = conn.execute("SELECT COALESCE(MAX(sort_order), 72) FROM matches").fetchone()[0]
        cur = conn.execute(
            """
            INSERT INTO matches (stage, home_team, away_team, match_date, match_time, venue, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (stage, home_team.strip(), away_team.strip(), match_date, match_time, venue.strip(), max_order + 1),
        )
        return cur.lastrowid


def get_tournament_results() -> dict | None:
    with db() as conn:
        row = conn.execute("SELECT * FROM tournament_results WHERE id = 1").fetchone()
        if not row or not row["winner"]:
            return None
        return dict(row)


def save_tournament_results(top_scorer: str, winner: str, second_place: str, third_place: str) -> None:
    with db() as conn:
        conn.execute(
            """
            INSERT INTO tournament_results (id, top_scorer, winner, second_place, third_place, updated_at)
            VALUES (1, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(id) DO UPDATE SET
                top_scorer = excluded.top_scorer,
                winner = excluded.winner,
                second_place = excluded.second_place,
                third_place = excluded.third_place,
                updated_at = datetime('now')
            """,
            (top_scorer.strip(), winner.strip(), second_place.strip(), third_place.strip()),
        )


def get_leaderboard(pool_id: int) -> list[dict]:
    results = get_tournament_results()
    phase_bonus = compute_pool_phase_bonuses(pool_id)
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, u.photo_updated_at, u.ai_agent_key,
                   COALESCE(SUM(p.points), 0) AS match_points,
                   COUNT(p.id) AS predictions_made,
                   SUM(CASE WHEN p.points >= 5 THEN 1 ELSE 0 END) AS exact_scores,
                   SUM(CASE WHEN p.points IN (2, 4) THEN 1 ELSE 0 END) AS correct_results
            FROM users u
            LEFT JOIN predictions p ON p.user_id = u.id
            WHERE u.pool_id = ?
            GROUP BY u.id
            """,
            (pool_id,),
        ).fetchall()

        leaderboard = []
        for row in rows:
            entry = dict(row)
            vote = conn.execute(
                "SELECT * FROM tournament_votes WHERE user_id = ?",
                (entry["id"],),
            ).fetchone()
            vote_dict = dict(vote) if vote else None
            t_breakdown = calculate_tournament_points(vote_dict, results)
            entry["tournament_points"] = t_breakdown["total"]
            entry["tournament_breakdown"] = t_breakdown
            entry["phase_bonus_points"] = phase_bonus["total_by_user"].get(entry["id"], 0)
            entry["phase_bonus_detail"] = phase_bonus["detail_by_user"].get(entry["id"], [])
            entry["total_points"] = (
                entry["match_points"] + t_breakdown["total"] + entry["phase_bonus_points"]
            )
            leaderboard.append(entry)

        leaderboard.sort(
            key=lambda x: (
                -x["total_points"],
                -x["exact_scores"],
                -x["correct_results"],
                -x["match_points"],
                x["id"],
            ),
        )

        # Dense rank: tied players share a number; next distinct score is always +1 (6, 6, 7 — not 6, 6, 8).
        rank = 0
        prev_points = None
        for entry in leaderboard:
            pts = entry["total_points"]
            if pts <= 0:
                entry["rank"] = None
                continue
            if prev_points is None or pts < prev_points:
                rank += 1
            entry["rank"] = rank
            prev_points = pts

        return leaderboard


def get_pool_phase_bonus_status(pool_id: int) -> dict:
    return compute_pool_phase_bonuses(pool_id)


def get_leader_message(leaderboard: list[dict]) -> str | None:
    if not leaderboard or leaderboard[0]["total_points"] == 0:
        return None

    top_score = leaderboard[0]["total_points"]
    leaders = [e["display_name"] for e in leaderboard if e["total_points"] == top_score]

    if len(leaders) == 1:
        return f"{leaders[0]} leads with {top_score} pts"
    return f"{' · '.join(leaders)} tied for the lead with {top_score} pts"


def get_user_predictions(user_id: int) -> dict[int, sqlite3.Row]:
    with db() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE user_id = ?",
            (user_id,),
        ).fetchall()
        return {r["match_id"]: r for r in rows}


def get_pool_predictions_summary(pool_id: int, match_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.display_name, u.photo_updated_at, u.ai_agent_key,
                   p.home_score, p.away_score,
                   p.points, p.submitted_at, p.is_bold
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            WHERE u.pool_id = ? AND p.match_id = ?
            ORDER BY u.display_name
            """,
            (pool_id, match_id),
        ).fetchall()
        return [dict(r) for r in rows]


def get_pool_members(pool_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            "SELECT id, display_name, photo_updated_at FROM users WHERE pool_id = ? ORDER BY display_name",
            (pool_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_pool_members_with_stats(pool_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, u.photo_updated_at, u.ai_agent_key,
                   u.password_hash, u.password_must_set,
                   (SELECT COUNT(*) FROM predictions WHERE user_id = u.id) AS prediction_count,
                   (SELECT COUNT(*) FROM comments WHERE user_id = u.id) AS comment_count
            FROM users u
            WHERE u.pool_id = ?
            ORDER BY u.display_name
            """,
            (pool_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def delete_user(user_id: int, pool_id: int) -> str | None:
    from ai_predictor import is_synced_ai_agent
    from media_predictors import is_media_agent

    with db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND pool_id = ?",
            (user_id, pool_id),
        ).fetchone()
        if not user:
            return "User not found in this pool."
        if is_synced_ai_agent(user["display_name"], user["ai_agent_key"]):
            return "Cannot delete AI pool members."
        if is_media_agent(user["display_name"], user["ai_agent_key"]):
            return "Cannot delete media pundit pool members."

        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return None


def rename_user(user_id: int, pool_id: int, new_display_name: str) -> dict | str:
    from ai_predictor import infer_ai_agent_key, is_agent_badge, is_ai_agent, is_synced_ai_agent

    name = new_display_name.strip()
    if not name:
        return "Display name is required."
    if len(name) > 40:
        return "Display name must be 40 characters or fewer."

    with db() as conn:
        user = conn.execute(
            "SELECT * FROM users WHERE id = ? AND pool_id = ?",
            (user_id, pool_id),
        ).fetchone()
        if not user:
            return "User not found in this pool."

        conflict = conn.execute(
            "SELECT id, display_name FROM users WHERE pool_id = ? AND id != ?",
            (pool_id, user_id),
        ).fetchall()
        name_key = normalize_display_name(name)
        for row in conflict:
            if normalize_display_name(row["display_name"]) == name_key:
                return f'Another member already uses the name "{row["display_name"]}".'

        agent_key = user["ai_agent_key"] or infer_ai_agent_key(user["display_name"])
        if not agent_key and is_agent_badge(user["display_name"], user["ai_agent_key"]):
            agent_key = infer_ai_agent_key(name)
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?",
            (name, user_id),
        )
        if agent_key and is_agent_badge(user["display_name"], agent_key):
            conn.execute(
                "UPDATE users SET ai_agent_key = ? WHERE id = ?",
                (agent_key, user_id),
            )
    return {
        "id": user_id,
        "display_name": name,
        "old_display_name": user["display_name"],
    }


def admin_delete_comment(comment_id: int, pool_id: int) -> str | None:
    with db() as conn:
        comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not comment:
            return "Comment not found."
        if comment["pool_id"] != pool_id:
            return "Comment not in this pool."

        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    return None


def admin_delete_user_comments(user_id: int, pool_id: int) -> str | None:
    with db() as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE id = ? AND pool_id = ?",
            (user_id, pool_id),
        ).fetchone()
        if not user:
            return "User not found in this pool."

        conn.execute(
            "DELETE FROM comments WHERE user_id = ? AND pool_id = ?",
            (user_id, pool_id),
        )
    return None


def add_comment(pool_id: int, user_id: int, body: str, match_id: int | None = None) -> dict | str:
    text = body.strip()
    if not text:
        return "Comment cannot be empty."
    if len(text) > 500:
        return "Comment must be 500 characters or fewer."

    with db() as conn:
        cur = conn.execute(
            "INSERT INTO comments (pool_id, user_id, body, match_id) VALUES (?, ?, ?, ?)",
            (pool_id, user_id, text, match_id),
        )
        return {"id": cur.lastrowid, "body": text}


def get_pool_comments(pool_id: int, match_id: int | None = None) -> list[dict]:
    with db() as conn:
        if match_id:
            rows = conn.execute(
                """
                SELECT c.id, c.body, c.created_at, c.updated_at, c.match_id,
                       u.display_name, c.user_id, u.photo_updated_at,
                       m.home_team, m.away_team
                FROM comments c
                JOIN users u ON u.id = c.user_id
                LEFT JOIN matches m ON m.id = c.match_id
                WHERE c.pool_id = ? AND c.match_id = ?
                ORDER BY c.created_at DESC
                """,
                (pool_id, match_id),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT c.id, c.body, c.created_at, c.updated_at, c.match_id,
                       u.display_name, c.user_id, u.photo_updated_at,
                       m.home_team, m.away_team
                FROM comments c
                JOIN users u ON u.id = c.user_id
                LEFT JOIN matches m ON m.id = c.match_id
                WHERE c.pool_id = ?
                ORDER BY c.created_at DESC
                """,
                (pool_id,),
            ).fetchall()
        return [dict(r) for r in rows]


def get_comment(comment_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()


def update_comment(comment_id: int, user_id: int, body: str) -> dict | str:
    text = body.strip()
    if not text:
        return "Comment cannot be empty."
    if len(text) > 500:
        return "Comment must be 500 characters or fewer."

    with db() as conn:
        comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not comment:
            return "Comment not found."
        if comment["user_id"] != user_id:
            return "You can only edit your own comments."

        conn.execute(
            "UPDATE comments SET body = ?, updated_at = datetime('now') WHERE id = ?",
            (text, comment_id),
        )
        return {"id": comment_id, "body": text}


def delete_comment(comment_id: int, user_id: int) -> str | None:
    with db() as conn:
        comment = conn.execute("SELECT * FROM comments WHERE id = ?", (comment_id,)).fetchone()
        if not comment:
            return "Comment not found."
        if comment["user_id"] != user_id:
            return "You can only delete your own comments."

        conn.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
        return None


def get_tournament_vote(user_id: int) -> sqlite3.Row | None:
    with db() as conn:
        return conn.execute(
            "SELECT * FROM tournament_votes WHERE user_id = ?",
            (user_id,),
        ).fetchone()


def upsert_tournament_vote(
    user_id: int,
    top_scorer: str,
    winner: str,
    second_place: str,
    third_place: str,
    valid_teams: set[str] | None = None,
) -> dict | str:
    from teams import get_all_teams

    scorer = top_scorer.strip()
    win = winner.strip()
    second = second_place.strip()
    third = third_place.strip()
    allowed = valid_teams or set(get_all_teams())

    if not all([scorer, win, second, third]):
        return "All four picks are required."
    if len(scorer) > 60:
        return "Player name must be 60 characters or fewer."
    if not {win, second, third}.issubset(allowed):
        return "Please select valid teams from the list."
    if len({win, second, third}) < 3:
        return "Winner, 2nd, and 3rd must be three different teams."

    with db() as conn:
        conn.execute(
            """
            INSERT INTO tournament_votes (user_id, top_scorer, winner, second_place, third_place)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                top_scorer = excluded.top_scorer,
                winner = excluded.winner,
                second_place = excluded.second_place,
                third_place = excluded.third_place,
                submitted_at = datetime('now')
            """,
            (user_id, scorer, win, second, third),
        )
    return {"top_scorer": scorer, "winner": win, "second_place": second, "third_place": third}


def get_pool_tournament_votes(pool_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id AS user_id, u.display_name, t.top_scorer, t.winner, t.second_place, t.third_place, t.submitted_at
            FROM users u
            LEFT JOIN tournament_votes t ON t.user_id = u.id
            WHERE u.pool_id = ?
            ORDER BY t.submitted_at DESC, u.display_name ASC
            """,
            (pool_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_recent_pool_predictions(pool_id: int, limit: int = 40, *, active_only: bool = False) -> list[dict]:
    with db() as conn:
        active_clause = "AND m.actual_home IS NULL" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT u.id AS user_id, u.display_name, u.ai_agent_key, p.home_score, p.away_score, p.submitted_at,
                   m.id AS match_id, m.home_team, m.away_team, m.match_date, m.match_time,
                   m.status AS match_status, m.actual_home, m.actual_away
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            JOIN matches m ON m.id = p.match_id
            WHERE u.pool_id = ? {active_clause}
            ORDER BY
                CASE WHEN COALESCE(m.status, '') IN (
                    'live', 'halftime', 'hydration_break', 'extra_time', 'penalty_shootout'
                ) THEN 0 ELSE 1 END,
                m.match_date ASC,
                m.match_time ASC,
                p.submitted_at DESC
            LIMIT ?
            """,
            (pool_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]


def get_ticker_pool_predictions(pool_id: int, limit: int = 40, max_per_user: int = 8) -> list[dict]:
    """Interleave recent picks for upcoming/live matches across predictors."""
    pool = get_recent_pool_predictions(pool_id, limit=limit * 8, active_only=True)
    by_user: dict[int, list[dict]] = {}
    user_order: list[int] = []

    for row in pool:
        uid = row["user_id"]
        bucket = by_user.setdefault(uid, [])
        if len(bucket) >= max_per_user:
            continue
        if uid not in user_order:
            user_order.append(uid)
        bucket.append(row)

    if not user_order:
        return []

    result: list[dict] = []
    while len(result) < limit:
        added = False
        for uid in user_order:
            if by_user[uid]:
                result.append(by_user[uid].pop(0))
                added = True
                if len(result) >= limit:
                    break
        if not added:
            break
    return result


def get_pool_simulation_members(pool_id: int) -> list[dict]:
    """Pool members who have at least one match prediction (for bracket simulation)."""
    with db() as conn:
        rows = conn.execute(
            """
            SELECT u.id, u.display_name, COUNT(p.id) AS prediction_count
            FROM users u
            JOIN predictions p ON p.user_id = u.id
            WHERE u.pool_id = ?
            GROUP BY u.id
            ORDER BY u.display_name COLLATE NOCASE
            """,
            (pool_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_pool_predictors(pool_id: int, *, active_only: bool = False) -> list[dict]:
    """Users who have entered at least one prediction, with counts."""
    with db() as conn:
        join_matches = "JOIN matches m ON m.id = p.match_id" if active_only else ""
        active_clause = "AND m.actual_home IS NULL" if active_only else ""
        rows = conn.execute(
            f"""
            SELECT u.display_name, COUNT(p.id) AS prediction_count,
                   MAX(p.submitted_at) AS last_submitted
            FROM users u
            JOIN predictions p ON p.user_id = u.id
            {join_matches}
            WHERE u.pool_id = ? {active_clause}
            GROUP BY u.id
            ORDER BY last_submitted DESC
            """,
            (pool_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def count_unread_comments(pool_id: int, since: str | None, exclude_user_id: int | None = None) -> int:
    with db() as conn:
        if not since:
            return 0
        if exclude_user_id:
            return conn.execute(
                """
                SELECT COUNT(*) FROM comments
                WHERE pool_id = ? AND created_at > ? AND user_id != ?
                """,
                (pool_id, since, exclude_user_id),
            ).fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM comments WHERE pool_id = ? AND created_at > ?",
            (pool_id, since),
        ).fetchone()[0]

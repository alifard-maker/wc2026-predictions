"""Sync official knockout fixtures and resolved teams into the database."""

from __future__ import annotations

import db
from knockout_bracket import OFFICIAL_R32_PAIRINGS, TBD, resolve_match_teams
from knockout_fixtures import fixture_rows
from tournament_standings import compute_group_standings


def sync_knockout_stage() -> dict:
    """Ensure all 32 knockout matches exist and update teams as results come in."""
    inserted = _ensure_knockout_fixtures()
    updated = _resolve_knockout_teams()
    return {"inserted": inserted, "teams_updated": updated}


def _ensure_knockout_fixtures() -> int:
    inserted = 0
    with db.db() as conn:
        existing = {
            row["match_number"]
            for row in conn.execute(
                "SELECT match_number FROM matches WHERE match_number IS NOT NULL"
            ).fetchall()
        }
        for row in fixture_rows():
            if row["match_number"] in existing:
                conn.execute(
                    """
                    UPDATE matches
                    SET stage = ?, match_date = ?, match_time = ?, venue = ?, sort_order = ?
                    WHERE match_number = ?
                    """,
                    (
                        row["stage"],
                        row["match_date"],
                        row["match_time"],
                        row["venue"],
                        row["sort_order"],
                        row["match_number"],
                    ),
                )
                continue
            conn.execute(
                """
                INSERT INTO matches (
                    stage, home_team, away_team, match_date, match_time, venue,
                    sort_order, match_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["stage"],
                    TBD,
                    TBD,
                    row["match_date"],
                    row["match_time"],
                    row["venue"],
                    row["sort_order"],
                    row["match_number"],
                ),
            )
            inserted += 1
    return inserted


def _resolve_knockout_teams() -> int:
    matches = [dict(m) for m in db.get_all_matches()]
    standings = compute_group_standings(matches)
    updated = 0

    with db.db() as conn:
        knockout_rows = conn.execute(
            """
            SELECT id, match_number, home_team, away_team
            FROM matches
            WHERE match_number IS NOT NULL
            ORDER BY match_number
            """
        ).fetchall()

        for row in knockout_rows:
            match_number = row["match_number"]
            if not match_number:
                continue
            if match_number in OFFICIAL_R32_PAIRINGS:
                home, away = OFFICIAL_R32_PAIRINGS[match_number]
            else:
                home, away = resolve_match_teams(match_number, standings, matches)
            if home == row["home_team"] and away == row["away_team"]:
                continue
            conn.execute(
                "UPDATE matches SET home_team = ?, away_team = ? WHERE id = ?",
                (home, away, row["id"]),
            )
            updated += 1
            for m in matches:
                if m.get("id") == row["id"]:
                    m["home_team"] = home
                    m["away_team"] = away
                    break

    return updated

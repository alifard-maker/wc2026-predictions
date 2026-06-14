"""Pool engagement: player stats, achievements, H2H, matchday recaps, pick consensus."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from ai_predictor import AI_AGENT_NAMES, is_ai_agent
from db import db, get_all_matches, get_leaderboard, get_pool_comments, get_tournament_vote
from live_scores import apply_live_state
from scoring import (
    TIMEZONE,
    is_prediction_open,
    is_tournament_vote_open,
    match_result,
    prediction_deadline,
)

EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


def matchday_key(match: dict) -> str:
    if match.get("matchday"):
        return f"md{match['matchday']}"
    stage = match.get("stage") or "knockout"
    return f"ko_{stage}"


def _picks_group_sort(key: str) -> tuple:
    if key.startswith("md"):
        try:
            return (0, int(key[2:]))
        except ValueError:
            return (0, 99)
    if key.startswith("ko_"):
        stage_order = {
            "round_of_32": 1,
            "round_of_16": 2,
            "quarter_final": 3,
            "semi_final": 4,
            "third_place": 5,
            "final": 6,
        }
        return (1, stage_order.get(key[3:], 99))
    return (2, key)


def _picks_group_label(match: dict) -> str:
    if match.get("matchday"):
        return f"Matchday {match['matchday']}"
    if match.get("group_name"):
        return f"Group {match['group_name']}"
    return (match.get("stage") or "knockout").replace("_", " ").title()


def apply_bold_multiplier(base_points: int | None, is_bold: bool) -> int | None:
    if base_points is None:
        return None
    if is_bold and base_points > 0:
        return base_points * 2
    return base_points


def _finished_matches(matches: list[dict]) -> list[dict]:
    return [m for m in matches if m.get("actual_home") is not None]


def _user_pool_predictions(user_id: int, pool_id: int) -> list[dict]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, m.home_team, m.away_team, m.matchday, m.stage, m.group_name,
                   m.match_date, m.match_time, m.actual_home, m.actual_away
            FROM predictions p
            JOIN matches m ON m.id = p.match_id
            JOIN users u ON u.id = p.user_id
            WHERE p.user_id = ? AND u.pool_id = ?
            ORDER BY m.match_date, m.match_time
            """,
            (user_id, pool_id),
        ).fetchall()
    return [dict(r) for r in rows]


def _pool_member_predictions(pool_id: int) -> dict[int, list[dict]]:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.*, u.display_name, u.id AS user_id,
                   m.home_team, m.away_team, m.matchday, m.stage,
                   m.match_date, m.match_time, m.actual_home, m.actual_away, m.id AS match_id
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            JOIN matches m ON m.id = p.match_id
            WHERE u.pool_id = ?
            """,
            (pool_id,),
        ).fetchall()
    by_user: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_user[r["user_id"]].append(dict(r))
    return by_user


def _ai_beaten_on_match(user_points: int | None, match_preds: list[dict], user_id: int) -> bool:
    if user_points is None or user_points <= 0:
        return False
    ai_points = [
        p["points"]
        for p in match_preds
        if p["display_name"] in AI_AGENT_NAMES and p["points"] is not None
    ]
    if not ai_points:
        return False
    return user_points > max(ai_points)


def compute_achievements(user_id: int, pool_id: int, preds: list[dict] | None = None) -> list[dict]:
    preds = preds or _user_pool_predictions(user_id, pool_id)
    comments = get_pool_comments(pool_id)
    user_comments = [c for c in comments if c["user_id"] == user_id]

    badges: list[dict] = []
    finished = [p for p in preds if p["points"] is not None]

    exact_by_md: Counter = Counter()
    for p in finished:
        if p["points"] >= 5 or (p.get("is_bold") and p["points"] >= 10):
            exact_by_md[matchday_key(p)] += 1
    if any(c >= 3 for c in exact_by_md.values()):
        badges.append({"key": "oracle", "emoji": "🎯", "title": "Oracle", "desc": "3+ exact scores in one matchday"})

    if len(user_comments) >= 10:
        badges.append({"key": "salty", "emoji": "🧂", "title": "Salty", "desc": "10+ pool chat messages"})

    clutch = False
    for p in preds:
        if not p.get("submitted_at"):
            continue
        deadline = prediction_deadline(p["match_date"], p["match_time"])
        try:
            submitted = datetime.strptime(p["submitted_at"][:19], "%Y-%m-%d %H:%M:%S").replace(tzinfo=TIMEZONE)
        except ValueError:
            continue
        if deadline - submitted <= timedelta(minutes=15):
            clutch = True
            break
    if clutch:
        badges.append({"key": "clutch", "emoji": "⏱️", "title": "Clutch", "desc": "Submitted within 15 minutes of deadline"})

    if any(p.get("is_bold") and p["points"] and p["points"] >= 10 for p in finished):
        badges.append({"key": "bold_hero", "emoji": "🎰", "title": "Bold Hero", "desc": "Nailed a 2× bold exact score"})

    if any(p.get("is_bold") and p["points"] and p["points"] >= 4 for p in finished):
        if not any(b["key"] == "bold_hero" for b in badges):
            badges.append({"key": "doubler", "emoji": "💥", "title": "Doubler", "desc": "Bold pick paid off (2× points)"})

    streak = 0
    best_streak = 0
    for p in finished:
        if p["points"] and p["points"] > 0:
            streak += 1
            best_streak = max(best_streak, streak)
        else:
            streak = 0
    if best_streak >= 3:
        badges.append({"key": "hot_streak", "emoji": "🔥", "title": "Hot Streak", "desc": f"{best_streak} correct picks in a row"})

    matches = [dict(m) for m in get_all_matches()]
    match_map = {m["id"]: m for m in matches}

    ai_slayer_days: set[str] = set()
    contrarian_matches: set[int] = set()

    for m in _finished_matches(match_map.values()):
        mid = m["id"]
        with db() as conn:
            rows = conn.execute(
                """
                SELECT p.user_id, p.points, u.display_name
                FROM predictions p
                JOIN users u ON u.id = p.user_id
                WHERE p.match_id = ? AND u.pool_id = ?
                """,
                (mid, pool_id),
            ).fetchall()
        match_preds = [dict(r) for r in rows]
        winners = [r for r in match_preds if r["points"] and r["points"] > 0]
        if len(winners) == 1 and winners[0]["user_id"] == user_id:
            contrarian_matches.add(mid)
        user_row = next((r for r in match_preds if r["user_id"] == user_id), None)
        if user_row and _ai_beaten_on_match(user_row["points"], match_preds, user_id):
            ai_slayer_days.add(matchday_key(m))

    if contrarian_matches:
        badges.append({
            "key": "contrarian",
            "emoji": "🦄",
            "title": "Contrarian",
            "desc": f"Only correct pick on {len(contrarian_matches)} match(es)",
        })

    if ai_slayer_days:
        badges.append({
            "key": "ai_slayer",
            "emoji": "🤖",
            "title": "AI Slayer",
            "desc": f"Outscored every AI on {len(ai_slayer_days)} matchday(s)",
        })

    emoji_heavy = [c for c in user_comments if len(EMOJI_RE.findall(c["body"])) >= 3]
    if emoji_heavy:
        badges.append({"key": "emoji_king", "emoji": "😂", "title": "Emoji King", "desc": "Comments dripping with emojis"})

    if not badges and finished:
        badges.append({"key": "rookie", "emoji": "⚽", "title": "In the Game", "desc": "First predictions on the board"})

    return badges


def build_player_season_stats(user_id: int, pool_id: int, leaderboard: list[dict] | None = None) -> dict:
    from db import get_leaderboard

    preds = _user_pool_predictions(user_id, pool_id)
    finished = [p for p in preds if p["points"] is not None]
    leaderboard = leaderboard or get_leaderboard(pool_id)
    entry = next((e for e in leaderboard if e["id"] == user_id), None)

    team_wrong: Counter = Counter()
    team_right: Counter = Counter()
    for p in finished:
        actual_r = match_result(p["actual_home"], p["actual_away"])
        pred_r = match_result(p["home_score"], p["away_score"])
        for team in (p["home_team"], p["away_team"]):
            if pred_r == actual_r and p["points"] > 0:
                team_right[team] += 1
            elif pred_r != actual_r:
                team_wrong[team] += 1

    points_by_md: dict[str, int] = defaultdict(int)
    for p in finished:
        points_by_md[matchday_key(p)] += p["points"] or 0

    best_md = max(points_by_md.items(), key=lambda x: x[1]) if points_by_md else None
    worst_md = min(points_by_md.items(), key=lambda x: x[1]) if points_by_md else None

    ai_wins = 0
    ai_total = 0
    matches = {m["id"]: dict(m) for m in get_all_matches()}  # noqa: same pattern
    for m in _finished_matches(matches.values()):
        with db() as conn:
            rows = conn.execute(
                """
                SELECT p.user_id, p.points, u.display_name
                FROM predictions p JOIN users u ON u.id = p.user_id
                WHERE p.match_id = ? AND u.pool_id = ?
                """,
                (m["id"], pool_id),
            ).fetchall()
        match_preds = [dict(r) for r in rows]
        user_row = next((r for r in match_preds if r["user_id"] == user_id), None)
        if not user_row or user_row["points"] is None:
            continue
        ai_pts = [r["points"] for r in match_preds if r["display_name"] in AI_AGENT_NAMES and r["points"] is not None]
        if not ai_pts:
            continue
        ai_total += 1
        if user_row["points"] > max(ai_pts):
            ai_wins += 1

    bold_used = sum(1 for p in preds if p.get("is_bold"))
    bold_hits = sum(1 for p in finished if p.get("is_bold") and p["points"] and p["points"] > 0)

    recent = sorted(finished, key=lambda p: (p["match_date"], p["match_time"]))[-5:]
    recent_form = [
        {
            "match": f"{p['home_team']} vs {p['away_team']}",
            "prediction": f"{p['home_score']}–{p['away_score']}",
            "points": p["points"],
            "bold": bool(p.get("is_bold")),
        }
        for p in recent
    ]

    scored = sum(p["points"] or 0 for p in finished)
    exact = sum(1 for p in finished if (p["points"] or 0) >= 5)
    results = sum(1 for p in finished if p["points"] == 2 or (p.get("is_bold") and p["points"] == 4))

    return {
        "user_id": user_id,
        "rank": entry["rank"] if entry else None,
        "total_points": entry["total_points"] if entry else 0,
        "match_points": entry["match_points"] if entry else 0,
        "phase_bonus_points": entry.get("phase_bonus_points", 0) if entry else 0,
        "phase_bonus_detail": entry.get("phase_bonus_detail", []) if entry else [],
        "tournament_points": entry["tournament_points"] if entry else 0,
        "predictions_made": len(preds),
        "finished_predictions": len(finished),
        "exact_scores": exact,
        "correct_results": results,
        "accuracy_pct": round(100 * sum(1 for p in finished if p["points"] and p["points"] > 0) / len(finished), 1) if finished else 0,
        "exact_pct": round(100 * exact / len(finished), 1) if finished else 0,
        "best_matchday": {"key": best_md[0], "points": best_md[1]} if best_md else None,
        "worst_matchday": {"key": worst_md[0], "points": worst_md[1]} if worst_md else None,
        "lucky_team": team_right.most_common(1)[0][0] if team_right else None,
        "nemesis_team": team_wrong.most_common(1)[0][0] if team_wrong else None,
        "ai_record": {"wins": ai_wins, "total": ai_total},
        "bold": {"used": bold_used, "hits": bold_hits},
        "recent_form": recent_form,
        "achievements": compute_achievements(user_id, pool_id, preds),
    }


def build_head_to_head(user_id: int, other_id: int, pool_id: int) -> dict:
    with db() as conn:
        users = conn.execute(
            "SELECT id, display_name FROM users WHERE pool_id = ? AND id IN (?, ?)",
            (pool_id, user_id, other_id),
        ).fetchall()
    user_map = {u["id"]: u["display_name"] for u in users}
    if user_id not in user_map or other_id not in user_map:
        return {}

    preds_a = {p["match_id"]: p for p in _user_pool_predictions(user_id, pool_id)}
    preds_b = {p["match_id"]: p for p in _user_pool_predictions(other_id, pool_id)}
    shared = set(preds_a) & set(preds_b)

    a_wins = b_wins = ties = 0
    matchups = []
    for mid in sorted(shared):
        pa, pb = preds_a[mid], preds_b[mid]
        if pa["points"] is None or pb["points"] is None:
            continue
        if pa["points"] > pb["points"]:
            a_wins += 1
            winner = "a"
        elif pb["points"] > pa["points"]:
            b_wins += 1
            winner = "b"
        else:
            ties += 1
            winner = "tie"
        matchups.append({
            "match": f"{pa['home_team']} vs {pa['away_team']}",
            "a_prediction": f"{pa['home_score']}–{pa['away_score']}",
            "b_prediction": f"{pb['home_score']}–{pb['away_score']}",
            "a_points": pa["points"],
            "b_points": pb["points"],
            "winner": winner,
        })

    lb = {e["id"]: e for e in get_leaderboard(pool_id)}
    return {
        "a": {"id": user_id, "name": user_map[user_id], "total": lb.get(user_id, {}).get("total_points", 0)},
        "b": {"id": other_id, "name": user_map[other_id], "total": lb.get(other_id, {}).get("total_points", 0)},
        "a_match_wins": a_wins,
        "b_match_wins": b_wins,
        "ties": ties,
        "matchups": matchups,
    }


def build_match_consensus(pool_id: int, match_id: int) -> dict:
    with db() as conn:
        rows = conn.execute(
            """
            SELECT p.home_score, p.away_score
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            WHERE p.match_id = ? AND u.pool_id = ?
            """,
            (match_id, pool_id),
        ).fetchall()
    if not rows:
        return {"total": 0, "home_win_pct": 0, "draw_pct": 0, "away_win_pct": 0, "popular_score": None}

    home_w = draw = away_w = 0
    scores: Counter = Counter()
    for r in rows:
        res = match_result(r["home_score"], r["away_score"])
        if res == "home":
            home_w += 1
        elif res == "draw":
            draw += 1
        else:
            away_w += 1
        scores[(r["home_score"], r["away_score"])] += 1

    total = len(rows)
    pop = scores.most_common(1)[0][0]
    return {
        "total": total,
        "home_win_pct": round(100 * home_w / total),
        "draw_pct": round(100 * draw / total),
        "away_win_pct": round(100 * away_w / total),
        "popular_score": f"{pop[0]}–{pop[1]}",
        "popular_count": scores[pop],
    }


def _match_label(match: dict) -> str:
    return f"{match['home_team']} vs {match['away_team']}"


def _consensus_from_preds(preds: list[dict]) -> dict | None:
    if not preds:
        return None
    total = len(preds)
    home_w = draw = away_w = 0
    scores: Counter = Counter()
    for p in preds:
        outcome = match_result(p["home_score"], p["away_score"])
        if outcome == "home":
            home_w += 1
        elif outcome == "draw":
            draw += 1
        else:
            away_w += 1
        scores[(p["home_score"], p["away_score"])] += 1
    pop_score, pop_count = scores.most_common(1)[0]
    return {
        "total": total,
        "home_win_pct": round(100 * home_w / total),
        "draw_pct": round(100 * draw / total),
        "away_win_pct": round(100 * away_w / total),
        "popular_score": f"{pop_score[0]}–{pop_score[1]}",
        "popular_tuple": pop_score,
        "popular_count": pop_count,
        "popular_pct": round(100 * pop_count / total),
    }


def _fetch_matchday_predictions(pool_id: int, match_ids: set[int]) -> list[dict]:
    if not match_ids:
        return []
    with db() as conn:
        preds = conn.execute(
            """
            SELECT p.*, u.display_name, u.id AS user_id,
                   m.home_team, m.away_team, m.id AS match_id
            FROM predictions p
            JOIN users u ON u.id = p.user_id
            JOIN matches m ON m.id = p.match_id
            WHERE u.pool_id = ? AND p.match_id IN ({})
            """.format(",".join("?" * len(match_ids))),
            (pool_id, *match_ids),
        ).fetchall()
    return [dict(r) for r in preds]


def _build_pick_party(
    by_match: dict[int, list[dict]],
    match_map: dict[int, dict],
) -> dict:
    """Fun highlights from revealed picks — before and during matches."""
    hive_mind = None
    split_camp = None
    boldest = None
    lone_wolf = None
    on_track = None

    best_hive_pct = -1
    best_split_balance = 101
    best_bold_score = -1
    best_lone_goals = -1
    best_on_track_pct = -1

    for mid, mp in by_match.items():
        if len(mp) < 2:
            continue
        match = match_map.get(mid)
        if not match:
            continue
        label = _match_label(match)
        consensus = _consensus_from_preds(mp)
        if not consensus:
            continue

        if consensus["popular_pct"] > best_hive_pct:
            best_hive_pct = consensus["popular_pct"]
            hive_mind = {
                "match": label,
                "score": consensus["popular_score"],
                "pct": consensus["popular_pct"],
                "count": consensus["popular_count"],
                "total": consensus["total"],
            }

        balance = max(
            consensus["home_win_pct"],
            consensus["draw_pct"],
            consensus["away_win_pct"],
        )
        if balance < best_split_balance:
            best_split_balance = balance
            split_camp = {
                "match": label,
                "home_pct": consensus["home_win_pct"],
                "draw_pct": consensus["draw_pct"],
                "away_pct": consensus["away_win_pct"],
            }

        pop_h, pop_a = consensus["popular_tuple"]
        for p in mp:
            deviation = abs(p["home_score"] - pop_h) + abs(p["away_score"] - pop_a)
            bold_score = deviation + (3 if p.get("is_bold") else 0)
            if bold_score > best_bold_score:
                best_bold_score = bold_score
                boldest = {
                    "player": p["display_name"],
                    "match": label,
                    "prediction": f"{p['home_score']}–{p['away_score']}",
                    "is_bold": bool(p.get("is_bold")),
                }

        score_counts = Counter((p["home_score"], p["away_score"]) for p in mp)
        for (h, a), count in score_counts.items():
            if count != 1:
                continue
            total_goals = h + a
            if total_goals > best_lone_goals:
                picker = next(p for p in mp if p["home_score"] == h and p["away_score"] == a)
                best_lone_goals = total_goals
                lone_wolf = {
                    "player": picker["display_name"],
                    "match": label,
                    "prediction": f"{h}–{a}",
                }

        if match.get("is_live") or match.get("status") in ("halftime", "hydration_break"):
            live_h = match.get("display_home")
            live_a = match.get("display_away")
            if live_h is not None and live_a is not None:
                live_result = match_result(live_h, live_a)
                tracking = [p for p in mp if match_result(p["home_score"], p["away_score"]) == live_result]
                track_pct = round(100 * len(tracking) / len(mp))
                if track_pct > best_on_track_pct:
                    best_on_track_pct = track_pct
                    on_track = {
                        "match": label,
                        "score": f"{live_h}–{live_a}",
                        "minute": match.get("minute_label") or "LIVE",
                        "pct": track_pct,
                        "count": len(tracking),
                        "total": len(mp),
                    }

    return {
        "hive_mind": hive_mind,
        "split_camp": split_camp,
        "boldest": boldest,
        "lone_wolf": lone_wolf,
        "on_track": on_track,
    }


def _build_results_recap(
    by_match: dict[int, list[dict]],
    finished: list[dict],
    pool_id: int,
) -> dict:
    """Highlights after final whistles."""
    hardest = None
    hardest_rate = 101
    contrarian_pick = None
    worst_call = None
    exact_hero = None
    best_miss = -1
    best_exact_pts = -1

    all_finished_preds: list[dict] = []

    for m in finished:
        mp = by_match.get(m["id"], [])
        if not mp:
            continue
        all_finished_preds.extend(mp)
        correct = sum(1 for p in mp if p["points"] and p["points"] > 0)
        rate = 100 * correct / len(mp)
        if rate < hardest_rate:
            hardest_rate = rate
            hardest = m

        winners = [p for p in mp if p["points"] and p["points"] > 0]
        if len(winners) == 1:
            w = winners[0]
            contrarian_pick = {
                "player": w["display_name"],
                "match": _match_label(m),
                "prediction": f"{w['home_score']}–{w['away_score']}",
                "points": w["points"],
            }

        actual_h, actual_a = m["actual_home"], m["actual_away"]
        for p in mp:
            miss = abs(p["home_score"] - actual_h) + abs(p["away_score"] - actual_a)
            if miss > best_miss:
                best_miss = miss
                worst_call = {
                    "player": p["display_name"],
                    "match": _match_label(m),
                    "prediction": f"{p['home_score']}–{p['away_score']}",
                    "actual": f"{actual_h}–{actual_a}",
                    "miss": miss,
                }
            if p["points"] and p["points"] >= 5 and p["points"] > best_exact_pts:
                best_exact_pts = p["points"]
                exact_hero = {
                    "player": p["display_name"],
                    "match": _match_label(m),
                    "prediction": f"{p['home_score']}–{p['away_score']}",
                    "points": p["points"],
                    "is_bold": bool(p.get("is_bold")),
                }

    points_by_user: Counter = Counter()
    for p in all_finished_preds:
        if p["points"]:
            points_by_user[p["display_name"]] += p["points"]
    top_player = points_by_user.most_common(1)[0] if points_by_user else None

    ai_beaters: Counter = Counter()
    for m in finished:
        mp = by_match.get(m["id"], [])
        for p in mp:
            if p["display_name"] in AI_AGENT_NAMES:
                continue
            if _ai_beaten_on_match(p["points"], mp, p["user_id"]):
                ai_beaters[p["display_name"]] += 1
    ai_hero = ai_beaters.most_common(1)[0] if ai_beaters else None

    dates = sorted({m["match_date"] for m in finished})
    comments = get_pool_comments(pool_id)
    funniest = None
    best_emoji_count = 0
    for c in comments:
        emojis = len(EMOJI_RE.findall(c["body"]))
        if emojis > best_emoji_count:
            best_emoji_count = emojis
            funniest = {"player": c["display_name"], "body": c["body"][:120], "emoji_count": emojis}

    return {
        "hardest_match": {
            "label": _match_label(hardest),
            "correct_rate": round(hardest_rate),
        } if hardest else None,
        "contrarian_pick": contrarian_pick,
        "worst_call": worst_call,
        "exact_hero": exact_hero,
        "top_player": {"name": top_player[0], "points": top_player[1]} if top_player else None,
        "ai_hero": {"name": ai_hero[0], "matches": ai_hero[1]} if ai_hero else None,
        "funniest_comment": funniest,
    }


def build_matchday_recap(pool_id: int, matchday: int, now: datetime | None = None) -> dict | None:
    now = now or datetime.now(TIMEZONE)
    matches = [dict(m) for m in get_all_matches() if m["matchday"] == matchday]
    if not matches:
        return None

    enriched = {m["id"]: apply_live_state(m, now) for m in matches}
    revealed_ids = {m["id"] for m in matches if picks_revealed(m, now)}
    if not revealed_ids:
        return None

    finished = [enriched[m["id"]] for m in matches if enriched[m["id"]].get("actual_home") is not None]
    live_count = sum(
        1 for m in enriched.values()
        if m["id"] in revealed_ids and (m.get("is_live") or m.get("status") in ("halftime", "hydration_break"))
    )
    awaiting_count = sum(
        1 for m in enriched.values()
        if m["id"] in revealed_ids and not m.get("is_finished") and not m.get("is_live")
        and m.get("status") not in ("halftime", "hydration_break")
    )

    all_preds = _fetch_matchday_predictions(pool_id, revealed_ids)
    by_match: dict[int, list[dict]] = defaultdict(list)
    for p in all_preds:
        by_match[p["match_id"]].append(p)

    pick_party = _build_pick_party(by_match, enriched)
    results = _build_results_recap(by_match, finished, pool_id) if finished else {}

    if finished and len(finished) >= len(revealed_ids):
        phase = "complete"
    elif finished or live_count:
        phase = "in_progress"
    else:
        phase = "pre_match"

    return {
        "matchday": matchday,
        "phase": phase,
        "matches_total": len(matches),
        "matches_revealed": len(revealed_ids),
        "matches_played": len(finished),
        "matches_live": live_count,
        "matches_awaiting": awaiting_count,
        "pick_party": pick_party,
        **results,
    }


def list_matchday_recaps(pool_id: int) -> list[dict]:
    matchdays = sorted({m["matchday"] for m in get_all_matches() if m["matchday"]}, reverse=True)
    recaps = []
    for md in matchdays:
        recap = build_matchday_recap(pool_id, md)
        if recap:
            recaps.append(recap)
    return recaps


def picks_revealed(match: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(TIMEZONE)
    return not is_prediction_open(match["match_date"], match["match_time"], now)


def filter_predictions_for_display(
    predictions: list[dict],
    viewer_user_id: int,
    match: dict,
) -> list[dict]:
    if picks_revealed(match):
        return predictions
    return [
        p if p["user_id"] == viewer_user_id
        else {**p, "home_score": None, "away_score": None, "hidden": True}
        for p in predictions
    ]


def filter_ticker_predictions(recent: list[dict]) -> list[dict]:
    """Picks ticker: only revealed matches or AI agents (all humans hidden until deadline)."""
    filtered = []
    for p in recent:
        match = {"match_date": p["match_date"], "match_time": p["match_time"]}
        if picks_revealed(match) or is_ai_agent(p["display_name"]):
            filtered.append(p)
    return filtered


def filter_ticker_predictors(predictors: list[dict]) -> list[dict]:
    """Picks ticker fallback: only AI agents (humans hidden until deadlines pass)."""
    return [p for p in predictors if is_ai_agent(p["display_name"])]


def tournament_picks_revealed(now: datetime | None = None) -> bool:
    now = now or datetime.now(TIMEZONE)
    return not is_tournament_vote_open(now)


def filter_tournament_votes_for_display(
    votes: list[dict],
    viewer_user_id: int,
    now: datetime | None = None,
) -> list[dict]:
    if tournament_picks_revealed(now):
        return votes
    filtered = []
    for vote in votes:
        if (
            vote["user_id"] == viewer_user_id
            or is_ai_agent(vote["display_name"])
            or not vote.get("top_scorer")
        ):
            filtered.append(vote)
            continue
        filtered.append({
            **vote,
            "top_scorer": None,
            "winner": None,
            "second_place": None,
            "third_place": None,
            "hidden": True,
        })
    return filtered


def build_player_picks_summary(
    player_user_id: int,
    pool_id: int,
    viewer_user_id: int,
) -> dict:
    """Full pick sheet for a player — own profile always visible; others respect deadlines."""
    now = datetime.now(TIMEZONE)
    is_own = player_user_id == viewer_user_id
    all_matches = [dict(m) for m in get_all_matches()]
    user_preds = {p["match_id"]: p for p in _user_pool_predictions(player_user_id, pool_id)}

    predicted = 0
    open_to_predict = 0
    closed_missed = 0
    groups_map: dict[str, list] = defaultdict(list)
    group_labels: dict[str, str] = {}

    for m in all_matches:
        pred = user_preds.get(m["id"])
        open_for_pred = is_prediction_open(m["match_date"], m["match_time"], now)
        finished = m["actual_home"] is not None
        revealed = picks_revealed(m, now)
        hide = not is_own and not revealed and pred is not None

        if pred:
            predicted += 1
        elif open_for_pred:
            open_to_predict += 1
        else:
            closed_missed += 1

        gkey = matchday_key(m)
        group_labels[gkey] = _picks_group_label(m)

        row = {
            "match_id": m["id"],
            "home_team": m["home_team"],
            "away_team": m["away_team"],
            "match_date": m["match_date"],
            "matchday": m.get("matchday"),
            "group_name": m.get("group_name"),
            "stage": m.get("stage"),
            "open": open_for_pred,
            "finished": finished,
            "has_prediction": pred is not None,
            "hidden": hide,
            "home_score": None,
            "away_score": None,
            "is_bold": False,
            "points": None,
            "actual_home": m["actual_home"] if finished else None,
            "actual_away": m["actual_away"] if finished else None,
        }
        if pred and not hide:
            row["home_score"] = pred["home_score"]
            row["away_score"] = pred["away_score"]
            row["is_bold"] = bool(pred.get("is_bold"))
            row["points"] = pred["points"]

        groups_map[gkey].append(row)

    groups = [
        {"key": k, "label": group_labels[k], "matches": groups_map[k]}
        for k in sorted(groups_map.keys(), key=_picks_group_sort)
    ]

    vote = get_tournament_vote(player_user_id)
    tournament = None
    tournament_hidden = False
    tournament_submitted = bool(vote and vote["top_scorer"])
    if vote and tournament_submitted:
        if is_own or tournament_picks_revealed(now):
            tournament = {
                "top_scorer": vote["top_scorer"],
                "winner": vote["winner"],
                "second_place": vote["second_place"],
                "third_place": vote["third_place"],
            }
        else:
            tournament_hidden = True

    return {
        "groups": groups,
        "tournament": tournament,
        "tournament_hidden": tournament_hidden,
        "tournament_submitted": tournament_submitted,
        "totals": {
            "total_matches": len(all_matches),
            "predicted": predicted,
            "open_to_predict": open_to_predict,
            "closed_missed": closed_missed,
        },
    }

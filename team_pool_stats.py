"""Pool-specific and live tournament stats for team profile pages."""

from __future__ import annotations

from collections import Counter

from ai_predictor import AI_AGENTS, is_ai_agent
from db import get_all_matches, get_pool_predictions_summary
from scoring import calculate_points


def _team_matches(team_name: str) -> list[dict]:
    return [
        dict(m)
        for m in get_all_matches()
        if m["home_team"] == team_name or m["away_team"] == team_name
    ]


def _perspective(team_name: str, match: dict, home_score: int, away_score: int) -> tuple[int, int, str]:
    """Return (goals_for, goals_against, outcome) from team's perspective."""
    is_home = match["home_team"] == team_name
    gf = home_score if is_home else away_score
    ga = away_score if is_home else home_score
    if gf > ga:
        outcome = "win"
    elif gf < ga:
        outcome = "loss"
    else:
        outcome = "draw"
    return gf, ga, outcome


def get_team_pool_prediction_stats(pool_id: int, team_name: str) -> dict:
    matches = _team_matches(team_name)
    human_preds: list[dict] = []
    scoreline_counts: Counter = Counter()
    outcomes: Counter = Counter()
    goals_for: list[int] = []
    goals_against: list[int] = []

    ai_by_match: list[dict] = []
    ai_agents = {a["display_name"]: a for a in AI_AGENTS}

    for match in matches:
        preds = get_pool_predictions_summary(pool_id, match["id"])
        is_home = match["home_team"] == team_name
        opponent = match["away_team"] if is_home else match["home_team"]
        match_human: list[dict] = []
        match_ai: dict[str, dict] = {}

        for p in preds:
            gf, ga, outcome = _perspective(team_name, match, p["home_score"], p["away_score"])
            entry = {
                "home_score": p["home_score"],
                "away_score": p["away_score"],
                "goals_for": gf,
                "goals_against": ga,
                "outcome": outcome,
            }
            if is_ai_agent(p["display_name"]):
                match_ai[p["display_name"]] = {
                    **entry,
                    "badge": ai_agents.get(p["display_name"], {}).get("badge", "AI"),
                    "display_name": p["display_name"],
                }
            else:
                match_human.append(entry)
                human_preds.append(entry)
                scoreline_counts[f"{gf}–{ga}"] += 1
                outcomes[outcome] += 1
                goals_for.append(gf)
                goals_against.append(ga)

        if match_ai:
            ai_by_match.append(
                {
                    "match_id": match["id"],
                    "opponent": opponent,
                    "match_date": match["match_date"],
                    "is_home": is_home,
                    "agents": list(match_ai.values()),
                }
            )

    total_human = len(human_preds)
    top_scorelines = scoreline_counts.most_common(3)

    return {
        "prediction_count": total_human,
        "avg_goals_for": round(sum(goals_for) / total_human, 2) if total_human else None,
        "avg_goals_against": round(sum(goals_against) / total_human, 2) if total_human else None,
        "pct_win": round(100 * outcomes["win"] / total_human) if total_human else None,
        "pct_draw": round(100 * outcomes["draw"] / total_human) if total_human else None,
        "pct_loss": round(100 * outcomes["loss"] / total_human) if total_human else None,
        "top_scorelines": [{"scoreline": s, "count": c} for s, c in top_scorelines],
        "ai_picks": ai_by_match,
        "matches_with_predictions": len(matches),
    }


def get_team_live_tournament_stats(team_name: str) -> dict:
    from db import db

    with db() as conn:
        goals = conn.execute(
            """
            SELECT g.scorer_name, g.minute, g.injury_minute, g.team_side, g.is_penalty,
                   m.home_team, m.away_team, m.match_date, m.id AS match_id
            FROM match_goals g
            JOIN matches m ON m.id = g.match_id
            WHERE (m.home_team = ? AND g.team_side = 'home')
               OR (m.away_team = ? AND g.team_side = 'away')
            ORDER BY m.match_date, g.minute
            """,
            (team_name, team_name),
        ).fetchall()

        cards = conn.execute(
            """
            SELECT c.player_name, c.card_type, c.minute,
                   m.home_team, m.away_team, m.match_date
            FROM player_cards c
            JOIN matches m ON m.id = c.match_id
            WHERE c.team = ?
            ORDER BY m.match_date, c.minute
            """,
            (team_name,),
        ).fetchall()

        results = conn.execute(
            """
            SELECT id, home_team, away_team, actual_home, actual_away, match_date, group_name
            FROM matches
            WHERE (home_team = ? OR away_team = ?)
              AND actual_home IS NOT NULL
            ORDER BY match_date
            """,
            (team_name, team_name),
        ).fetchall()

        penalties = conn.execute(
            """
            SELECT p.*, m.home_team, m.away_team, m.match_date
            FROM match_penalties p
            JOIN matches m ON m.id = p.match_id
            WHERE m.home_team = ? OR m.away_team = ?
            ORDER BY m.match_date, p.minute
            """,
            (team_name, team_name),
        ).fetchall()

    scorer_counts: Counter = Counter()
    goal_list = []
    for g in goals:
        scorer_counts[g["scorer_name"]] += 1
        team_side = g["team_side"]
        minute = g["minute"]
        if g["injury_minute"]:
            minute_label = f"{minute}+{g['injury_minute']}'"
        else:
            minute_label = f"{minute}'"
        goal_list.append(
            {
                "scorer": g["scorer_name"],
                "minute": minute_label,
                "match": f"{g['home_team']} vs {g['away_team']}",
                "date": g["match_date"],
                "is_penalty": bool(g.get("is_penalty")),
            }
        )

    pen_stats = {
        "scored_for": 0,
        "conceded": 0,
        "saved": 0,
        "missed_against": 0,
        "faced": 0,
        "taken": 0,
    }
    penalty_events = []
    for p in penalties:
        home, away = p["home_team"], p["away_team"]
        defending = away if p["taker_team"] == home else home
        minute_label = f"{p['minute']}'"
        if p.get("injury_minute"):
            minute_label = f"{p['minute']}+{p['injury_minute']}'"
        penalty_events.append(
            {
                "taker": p["taker_name"] or p["taker_team"],
                "taker_team": p["taker_team"],
                "goalkeeper": p["goalkeeper_name"],
                "outcome": p["outcome"],
                "minute": minute_label,
                "match": f"{home} vs {away}",
                "date": p["match_date"],
                "is_for": p["taker_team"] == team_name,
            }
        )
        if p["taker_team"] == team_name:
            pen_stats["taken"] += 1
            if p["outcome"] == "scored":
                pen_stats["scored_for"] += 1
        if defending == team_name:
            pen_stats["faced"] += 1
            if p["outcome"] == "scored":
                pen_stats["conceded"] += 1
            elif p["outcome"] == "saved":
                pen_stats["saved"] += 1
            elif p["outcome"] == "missed":
                pen_stats["missed_against"] += 1

    match_record = {"w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0}
    for m in results:
        is_home = m["home_team"] == team_name
        gf = m["actual_home"] if is_home else m["actual_away"]
        ga = m["actual_away"] if is_home else m["actual_home"]
        match_record["gf"] += gf
        match_record["ga"] += ga
        if gf > ga:
            match_record["w"] += 1
        elif gf < ga:
            match_record["l"] += 1
        else:
            match_record["d"] += 1

    yellow_cards = sum(1 for c in cards if c["card_type"] == "yellow")
    red_cards = sum(1 for c in cards if c["card_type"] == "red")

    return {
        "has_data": bool(goals or cards or results or penalties),
        "goals": goal_list,
        "top_scorers": [{"name": n, "goals": c} for n, c in scorer_counts.most_common(5)],
        "cards": [
            {
                "player": c["player_name"],
                "type": c["card_type"],
                "minute": c["minute"],
                "match": f"{c['home_team']} vs {c['away_team']}",
                "date": c["match_date"],
            }
            for c in cards
        ],
        "yellow_cards": yellow_cards,
        "red_cards": red_cards,
        "penalties": pen_stats,
        "penalty_events": penalty_events,
        "tournament_record": match_record,
        "matches_played": len(results),
    }


def get_team_prediction_accuracy(pool_id: int, team_name: str) -> dict:
    matches = [
        m
        for m in _team_matches(team_name)
        if m.get("actual_home") is not None and m.get("actual_away") is not None
    ]
    if not matches:
        return {
            "finished_matches": 0,
            "total_predictions": 0,
            "exact_score_pct": None,
            "correct_result_pct": None,
            "avg_points": None,
        }

    exact = 0
    correct_result = 0
    total_preds = 0
    total_points = 0

    for match in matches:
        preds = get_pool_predictions_summary(pool_id, match["id"])
        for p in preds:
            if is_ai_agent(p["display_name"]):
                continue
            pts = calculate_points(
                p["home_score"], p["away_score"], match["actual_home"], match["actual_away"]
            )
            if pts is None:
                continue
            total_preds += 1
            total_points += pts
            if pts == 5:
                exact += 1
            if pts >= 2:
                correct_result += 1

    return {
        "finished_matches": len(matches),
        "total_predictions": total_preds,
        "exact_score_pct": round(100 * exact / total_preds) if total_preds else None,
        "correct_result_pct": round(100 * correct_result / total_preds) if total_preds else None,
        "avg_points": round(total_points / total_preds, 2) if total_preds else None,
    }

"""Group-stage preview data for World Cup 2026 teams."""

from __future__ import annotations

from fixtures import GROUP_FIXTURES
from team_data import TEAM_FACTS


def _team_group(team: str) -> str | None:
    for f in GROUP_FIXTURES:
        if f["home"] == team or f["away"] == team:
            return f["group"]
    return None


def _group_teams(group: str) -> list[str]:
    teams: set[str] = set()
    for f in GROUP_FIXTURES:
        if f["group"] == group:
            teams.add(f["home"])
            teams.add(f["away"])
    return sorted(teams)


def _ranking(team: str) -> int:
    rank = TEAM_FACTS.get(team, {}).get("ranking", 50)
    try:
        return int(rank)
    except (TypeError, ValueError):
        return 50


def get_group_preview(team: str) -> dict | None:
    group = _team_group(team)
    if not group:
        return None

    members = _group_teams(group)
    opponents = [t for t in members if t != team]
    ranks = [_ranking(t) for t in members]
    team_rank = _ranking(team)
    avg_opp_rank = round(sum(_ranking(o) for o in opponents) / len(opponents), 1)
    avg_group_rank = round(sum(ranks) / len(ranks), 1)

    if team_rank <= min(ranks) + 3:
        difficulty = "Favourable"
        difficulty_note = "Among the favourites to top the group."
    elif team_rank <= avg_group_rank + 5:
        difficulty = "Balanced"
        difficulty_note = "A competitive group — likely need 4–6 points to advance."
    else:
        difficulty = "Tough"
        difficulty_note = "Underdogs — probably need results against higher-ranked sides."

    return {
        "group": group,
        "members": [
            {
                "name": t,
                "ranking": _ranking(t),
                "is_team": t == team,
            }
            for t in members
        ],
        "opponents": opponents,
        "team_ranking": team_rank,
        "avg_opponent_ranking": avg_opp_rank,
        "difficulty": difficulty,
        "difficulty_note": difficulty_note,
        "advancement_tip": "Top 2 qualify automatically; best third-place teams may also advance.",
    }

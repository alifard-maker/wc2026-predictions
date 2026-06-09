"""Tournament-wide goal scorers and discipline tracking."""

from __future__ import annotations

from scoring import normalize_player
from team_squads import get_team_squad
from teams import get_all_teams


def get_scorer_squads_data(extra_names: list[str] | None = None) -> dict:
    """JSON-friendly squad map for the two-step top-scorer picker."""
    groups, extras = get_scorer_picker_options(extra_names)
    return {
        "teams": [g["team"] for g in groups],
        "players_by_team": {g["team"]: g["players"] for g in groups},
        "extras": extras,
    }


def get_scorer_picker_options(extra_names: list[str] | None = None) -> tuple[list[dict], list[str]]:
    """Squad players grouped by national team (A–Z), alphabetical within each squad."""
    groups: list[dict] = []
    known: set[str] = set()

    for team in sorted(get_all_teams(), key=str.lower):
        squad = get_team_squad(team)
        if not squad:
            continue
        players = sorted({p["name"] for p in squad["players"]}, key=str.lower)
        groups.append({"team": team, "players": players})
        known.update(players)

    extras: list[str] = []
    for name in extra_names or []:
        cleaned = name.strip()
        if not cleaned:
            continue
        if cleaned not in known and cleaned not in extras:
            extras.append(cleaned)
    extras.sort(key=str.lower)
    return groups, extras


def resolve_scorer_pick_value(selected: str, custom: str | None = None) -> str:
    """Use dropdown value, or custom text when 'Other' is chosen."""
    if selected == "__other__":
        return (custom or "").strip()
    return selected.strip()


def get_scorer_status(player_name: str, leaderboard: list[dict]) -> dict | None:
    norm = normalize_player(player_name)
    for i, row in enumerate(leaderboard):
        if normalize_player(row["player_name"]) == norm:
            return {"rank": i + 1, **row}
    return None


def card_suspension_status(yellow_count: int, red_count: int) -> str:
    if red_count >= 1:
        return "Suspended (red card)"
    if yellow_count >= 2:
        return "Suspended (2 yellows)"
    if yellow_count == 1:
        return "At risk (1 yellow)"
    return ""

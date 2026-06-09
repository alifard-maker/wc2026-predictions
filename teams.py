"""All 48 World Cup 2026 teams from the group-stage draw."""

from fixtures import GROUP_FIXTURES


def get_all_teams() -> list[str]:
    teams: set[str] = set()
    for f in GROUP_FIXTURES:
        teams.add(f["home"])
        teams.add(f["away"])
    return sorted(teams)

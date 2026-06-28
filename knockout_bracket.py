"""Official FIFA 2026 knockout bracket structure and team resolution."""

from __future__ import annotations

from functools import lru_cache
from itertools import combinations

from tournament_standings import GROUPS, _group_stage_complete, _third_place_rankings, match_winner

GROUP_LETTERS = list(GROUPS)

# Third-place bracket slots (matches 74, 77, 79, 80, 81, 82, 85, 87).
THIRD_SLOT_ELIGIBLE = [
    set("ABCDF"),
    set("CDFGH"),
    set("CEFHI"),
    set("EHIJK"),
    set("BEFIJ"),
    set("AEHIJ"),
    set("EFGIJ"),
    set("DEIJL"),
]

ROUND_OF_32 = [
    (73, ("2", "A"), ("2", "B")),
    (74, ("1", "E"), ("3", 0)),
    (75, ("1", "F"), ("2", "C")),
    (76, ("1", "C"), ("2", "F")),
    (77, ("1", "I"), ("3", 1)),
    (78, ("2", "E"), ("2", "I")),
    (79, ("1", "A"), ("3", 2)),
    (80, ("1", "L"), ("3", 3)),
    (81, ("1", "D"), ("3", 4)),
    (82, ("1", "G"), ("3", 5)),
    (83, ("2", "K"), ("2", "L")),
    (84, ("1", "H"), ("2", "J")),
    (85, ("1", "B"), ("3", 6)),
    (86, ("1", "J"), ("2", "H")),
    (87, ("1", "K"), ("3", 7)),
    (88, ("2", "D"), ("2", "G")),
]

# FIFA-confirmed Round of 32 pairings after the 2026 group stage (matches 73–88).
# Used once the draw is set; later rounds still resolve from match results.
OFFICIAL_R32_PAIRINGS: dict[int, tuple[str, str]] = {
    73: ("South Africa", "Canada"),
    74: ("Germany", "Paraguay"),
    75: ("Netherlands", "Morocco"),
    76: ("Brazil", "Japan"),
    77: ("France", "Sweden"),
    78: ("Côte d'Ivoire", "Norway"),
    79: ("Mexico", "Ecuador"),
    80: ("England", "Congo DR"),
    81: ("USA", "Bosnia and Herzegovina"),
    82: ("Belgium", "Senegal"),
    83: ("Portugal", "Croatia"),
    84: ("Spain", "Austria"),
    85: ("Switzerland", "Algeria"),
    86: ("Argentina", "Cabo Verde"),
    87: ("Colombia", "Ghana"),
    88: ("Australia", "Egypt"),
}

ROUND_OF_16 = [
    (89, 74, 77),
    (90, 73, 75),
    (91, 76, 78),
    (92, 79, 80),
    (93, 83, 84),
    (94, 81, 82),
    (95, 86, 88),
    (96, 85, 87),
]

QUARTER_FINALS = [
    (97, 89, 90),
    (98, 93, 94),
    (99, 91, 92),
    (100, 95, 96),
]

SEMI_FINALS = [
    (101, 97, 98),
    (102, 99, 100),
]

THIRD_PLACE = (103, 101, 102)
FINAL = (104, 101, 102)

STAGE_BY_MATCH_NUMBER = {
    **{n: "round_of_32" for n, _, _ in ROUND_OF_32},
    **{n: "round_of_16" for n, _, _ in ROUND_OF_16},
    **{n: "quarter_final" for n, _, _ in QUARTER_FINALS},
    **{n: "semi_final" for n, _, _ in SEMI_FINALS},
    THIRD_PLACE[0]: "third_place",
    FINAL[0]: "final",
}

TBD = "TBD"


@lru_cache(maxsize=None)
def _match_thirds(qualifying_groups: tuple[str, ...]) -> tuple[str, ...] | None:
    groups = list(qualifying_groups)
    assignment: list[str | None] = [None] * 8

    slot_options = []
    for slot in range(8):
        opts = [g for g in groups if g in THIRD_SLOT_ELIGIBLE[slot]]
        slot_options.append((len(opts), slot, sorted(opts)))
    slot_options.sort()
    order = [slot for _, slot, _ in slot_options]

    used: set[str] = set()

    def backtrack(k: int) -> bool:
        if k == len(order):
            return True
        slot = order[k]
        for g in sorted(THIRD_SLOT_ELIGIBLE[slot]):
            if g in qualifying_groups and g not in used:
                used.add(g)
                assignment[slot] = g
                if backtrack(k + 1):
                    return True
                used.discard(g)
                assignment[slot] = None
        return False

    if backtrack(0):
        return tuple(g for g in assignment if g is not None)
    return None


def third_slot_assignment(qualifying_groups: tuple[str, ...] | list[str]) -> tuple[str, ...] | None:
    return _match_thirds(tuple(sorted(qualifying_groups)))


def _qualifying_third_groups(
    standings: dict[str, list[dict]],
    matches: list[dict],
    ready_groups: set[str] | None = None,
) -> tuple[str, ...] | None:
    thirds: list[dict] = []
    for g in GROUP_LETTERS:
        if not _group_ready(g, matches, ready_groups):
            continue
        if g in standings and len(standings[g]) >= 3:
            thirds.append({**standings[g][2], "group": g})
    if len(thirds) < 8:
        return None
    thirds.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))
    return tuple(sorted(t["group"] for t in thirds[:8]))


def _group_ready(group: str, matches: list[dict], ready_groups: set[str] | None) -> bool:
    if ready_groups is not None:
        return group in ready_groups
    return _group_stage_complete(group, matches)


def _group_position_team(
    standings: dict[str, list[dict]],
    group: str,
    position: int,
    matches: list[dict],
    ready_groups: set[str] | None = None,
) -> str | None:
    if not _group_ready(group, matches, ready_groups):
        return None
    rows = standings.get(group) or []
    if len(rows) < position:
        return None
    return rows[position - 1]["team"]


def _third_slot_team(
    slot_index: int,
    standings: dict[str, list[dict]],
    matches: list[dict],
    third_assignment: tuple[str, ...] | None,
    ready_groups: set[str] | None = None,
) -> str | None:
    if third_assignment is None:
        return None
    group = third_assignment[slot_index]
    if not _group_ready(group, matches, ready_groups):
        return None
    rows = standings.get(group) or []
    if len(rows) < 3:
        return None
    return rows[2]["team"]


def _feeder_team(
    feeder_kind: str,
    feeder_match: int,
    matches_by_number: dict[int, dict],
) -> str | None:
    match = matches_by_number.get(feeder_match)
    if not match:
        return None
    if feeder_kind == "W":
        return match_winner(match)
    if feeder_kind == "L":
        winner = match_winner(match)
        if not winner:
            return None
        if winner == match.get("home_team"):
            return match.get("away_team")
        return match.get("home_team")
    return None


def resolve_slot(
    slot,
    standings: dict[str, list[dict]],
    matches: list[dict],
    matches_by_number: dict[int, dict],
    third_assignment: tuple[str, ...] | None,
    ready_groups: set[str] | None = None,
) -> str | None:
    kind = slot[0]
    if kind == "1":
        return _group_position_team(standings, slot[1], 1, matches, ready_groups)
    if kind == "2":
        return _group_position_team(standings, slot[1], 2, matches, ready_groups)
    if kind == "3":
        return _third_slot_team(slot[1], standings, matches, third_assignment, ready_groups)
    if kind == "W":
        return _feeder_team("W", slot[1], matches_by_number)
    if kind == "L":
        return _feeder_team("L", slot[1], matches_by_number)
    return None


def resolve_r32_pairings(
    standings: dict[str, list[dict]],
    matches: list[dict],
    ready_groups: set[str] | None = None,
) -> list[tuple[str | None, str | None]]:
    qualifying = _qualifying_third_groups(standings, matches, ready_groups)
    third_assignment = third_slot_assignment(qualifying) if qualifying else None
    matches_by_number = {
        m["match_number"]: m for m in matches if m.get("match_number")
    }
    pairings: list[tuple[str | None, str | None]] = []
    for _, slot_a, slot_b in ROUND_OF_32:
        home = resolve_slot(
            slot_a, standings, matches, matches_by_number, third_assignment, ready_groups
        )
        away = resolve_slot(
            slot_b, standings, matches, matches_by_number, third_assignment, ready_groups
        )
        pairings.append((home, away))
    return pairings


def resolve_match_teams(
    match_number: int,
    standings: dict[str, list[dict]],
    matches: list[dict],
) -> tuple[str, str]:
    matches_by_number = {
        m["match_number"]: m for m in matches if m.get("match_number")
    }
    qualifying = _qualifying_third_groups(standings, matches)
    third_assignment = third_slot_assignment(qualifying) if qualifying else None

    for num, slot_a, slot_b in ROUND_OF_32:
        if num == match_number:
            home = resolve_slot(slot_a, standings, matches, matches_by_number, third_assignment)
            away = resolve_slot(slot_b, standings, matches, matches_by_number, third_assignment)
            return home or TBD, away or TBD

    for num, feeder_a, feeder_b in ROUND_OF_16:
        if num == match_number:
            home = _feeder_team("W", feeder_a, matches_by_number)
            away = _feeder_team("W", feeder_b, matches_by_number)
            return home or TBD, away or TBD

    for num, feeder_a, feeder_b in QUARTER_FINALS:
        if num == match_number:
            home = _feeder_team("W", feeder_a, matches_by_number)
            away = _feeder_team("W", feeder_b, matches_by_number)
            return home or TBD, away or TBD

    for num, feeder_a, feeder_b in SEMI_FINALS:
        if num == match_number:
            home = _feeder_team("W", feeder_a, matches_by_number)
            away = _feeder_team("W", feeder_b, matches_by_number)
            return home or TBD, away or TBD

    if match_number == THIRD_PLACE[0]:
        home = _feeder_team("L", THIRD_PLACE[1], matches_by_number)
        away = _feeder_team("L", THIRD_PLACE[2], matches_by_number)
        return home or TBD, away or TBD

    if match_number == FINAL[0]:
        home = _feeder_team("W", FINAL[1], matches_by_number)
        away = _feeder_team("W", FINAL[2], matches_by_number)
        return home or TBD, away or TBD

    return TBD, TBD


def validate_all_third_combinations() -> int:
    failures = 0
    for combo in combinations(GROUP_LETTERS, 8):
        if third_slot_assignment(combo) is None:
            failures += 1
    return failures

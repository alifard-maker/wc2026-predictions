"""Group tables and knockout bracket tree from match results."""

from __future__ import annotations

from collections import defaultdict

from fixtures import GROUP_FIXTURES

GROUPS = list("ABCDEFGHIJKL")

KNOCKOUT_STAGES: list[tuple[str, str, int]] = [
    ("round_of_32", "Round of 32", 16),
    ("round_of_16", "Round of 16", 8),
    ("quarter_final", "Quarter-finals", 4),
    ("semi_final", "Semi-finals", 2),
    ("final", "Final", 1),
]

STAGE_LABELS = {key: label for key, label, _ in KNOCKOUT_STAGES}
STAGE_LABELS["third_place"] = "Third place"


def _teams_by_group() -> dict[str, list[str]]:
    groups: dict[str, set[str]] = defaultdict(set)
    for f in GROUP_FIXTURES:
        groups[f["group"]].add(f["home"])
        groups[f["group"]].add(f["away"])
    return {g: sorted(groups[g]) for g in GROUPS if g in groups}


def _empty_row(team: str) -> dict:
    return {
        "team": team,
        "played": 0,
        "w": 0,
        "d": 0,
        "l": 0,
        "gf": 0,
        "ga": 0,
        "gd": 0,
        "pts": 0,
    }


def _sort_group_table(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))


def _apply_group_result(hr: dict, ar: dict, hs: int, aws: int) -> None:
    for row in (hr, ar):
        row["played"] += 1
    hr["gf"] += hs
    hr["ga"] += aws
    ar["gf"] += aws
    ar["ga"] += hs
    if hs > aws:
        hr["w"] += 1
        hr["pts"] += 3
        ar["l"] += 1
    elif hs < aws:
        ar["w"] += 1
        ar["pts"] += 3
        hr["l"] += 1
    else:
        hr["d"] += 1
        ar["d"] += 1
        hr["pts"] += 1
        ar["pts"] += 1


def compute_group_standings_scored(
    matches: list[dict],
    score_fn,
) -> dict[str, list[dict]]:
    """Build group tables using score_fn(match) -> (home, away) or None."""
    tables = {g: [_empty_row(t) for t in teams] for g, teams in _teams_by_group().items()}
    index = {g: {r["team"]: r for r in rows} for g, rows in tables.items()}

    for m in matches:
        if m.get("stage") != "group":
            continue
        scores = score_fn(m)
        if scores is None:
            continue
        group = m.get("group_name")
        if not group or group not in index:
            continue
        home = m["home_team"]
        away = m["away_team"]
        if home not in index[group] or away not in index[group]:
            continue
        hs, aws = scores
        _apply_group_result(index[group][home], index[group][away], hs, aws)

    result: dict[str, list[dict]] = {}
    for g, rows in tables.items():
        for row in rows:
            row["gd"] = row["gf"] - row["ga"]
        sorted_rows = _sort_group_table(rows)
        for pos, row in enumerate(sorted_rows, start=1):
            row["position"] = pos
        result[g] = sorted_rows
    return result


def group_match_score(m: dict, *, include_live: bool = False) -> tuple[int, int] | None:
    """Final score when set; otherwise current live score for in-progress group matches."""
    if m.get("stage") != "group":
        return None
    if m.get("actual_home") is not None and m.get("actual_away") is not None:
        return int(m["actual_home"]), int(m["actual_away"])
    if not include_live or not m.get("is_live"):
        return None
    display_home = m.get("display_home")
    display_away = m.get("display_away")
    if display_home is None or display_away is None:
        return None
    return int(display_home), int(display_away)


def compute_group_standings(matches: list[dict], *, include_live: bool = False) -> dict[str, list[dict]]:
    """Build group tables from final results, optionally including live in-progress scores."""

    def score_fn(m: dict):
        return group_match_score(m, include_live=include_live)

    return compute_group_standings_scored(matches, score_fn)


def _live_group_teams(matches: list[dict]) -> set[str]:
    teams: set[str] = set()
    for m in matches:
        if m.get("stage") != "group" or m.get("actual_home") is not None:
            continue
        if not m.get("is_live"):
            continue
        if m.get("home_team"):
            teams.add(m["home_team"])
        if m.get("away_team"):
            teams.add(m["away_team"])
    return teams


def _third_place_rankings(standings: dict[str, list[dict]]) -> dict[str, dict]:
    thirds: list[dict] = []
    for g, rows in standings.items():
        if len(rows) >= 3:
            third = dict(rows[2])
            third["group"] = g
            thirds.append(third)
    thirds.sort(key=lambda r: (-r["pts"], -r["gd"], -r["gf"], r["team"]))
    return {
        t["team"]: {"third_rank": i + 1, "qualifies": i < 8}
        for i, t in enumerate(thirds)
    }


def _group_stage_complete(group: str, matches: list[dict]) -> bool:
    group_matches = [m for m in matches if m.get("stage") == "group" and m.get("group_name") == group]
    if not group_matches:
        return False
    finished = sum(1 for m in group_matches if m.get("actual_home") is not None)
    return finished >= len(group_matches)


def annotate_qualification(
    standings: dict[str, list[dict]],
    matches: list[dict],
    *,
    live_teams: set[str] | None = None,
) -> dict[str, list[dict]]:
    all_groups_done = all(_group_stage_complete(g, matches) for g in standings)
    third_info = _third_place_rankings(standings) if all_groups_done else {}
    live_teams = live_teams or set()
    annotated: dict[str, list[dict]] = {}
    for g, rows in standings.items():
        complete = _group_stage_complete(g, matches)
        group_rows = []
        for row in rows:
            r = dict(row)
            pos = r["position"]
            if r["team"] in live_teams:
                r["in_live_match"] = True
            if complete:
                if pos <= 2:
                    r["status"] = "qualified"
                elif pos == 3:
                    info = third_info.get(r["team"], {})
                    r["status"] = "qualified" if info.get("qualifies") else "eliminated"
                    r["third_rank"] = info.get("third_rank")
                else:
                    r["status"] = "eliminated"
            elif pos <= 2:
                r["status"] = "leading"
            elif pos == 3:
                r["status"] = "contending"
                r["third_rank"] = third_info.get(r["team"], {}).get("third_rank")
            else:
                r["status"] = "bottom"
            group_rows.append(r)
        annotated[g] = group_rows
    return annotated


def match_winner(match: dict | None) -> str | None:
    if not match or match.get("actual_home") is None or match.get("actual_away") is None:
        return None
    if match["actual_home"] > match["actual_away"]:
        return match["home_team"]
    if match["actual_away"] > match["actual_home"]:
        return match["away_team"]
    return None


def _match_slot(match: dict | None, home: str | None, away: str | None) -> dict:
    if match:
        m = dict(match)
        home_team = m.get("home_team") or home
        away_team = m.get("away_team") or away
        winner = match_winner(m)
        is_live = m.get("is_live", False)
        is_finished = m.get("is_finished", False)
        display_home = m.get("display_home")
        display_away = m.get("display_away")
    else:
        m = None
        home_team, away_team = home, away
        winner = None
        is_live = False
        is_finished = False
        display_home = display_away = None

    return {
        "id": m["id"] if m else None,
        "home_team": home_team,
        "away_team": away_team,
        "home_placeholder": home_team is None,
        "away_placeholder": away_team is None,
        "display_home": display_home,
        "display_away": display_away,
        "winner": winner,
        "is_live": is_live,
        "is_finished": is_finished,
        "match_date": m.get("match_date") if m else None,
        "match_time": m.get("match_time") if m else None,
        "venue": m.get("venue") if m else None,
    }


def _stage_matches(matches: list[dict], stage: str) -> list[dict]:
    stage_matches = [m for m in matches if m.get("stage") == stage]
    stage_matches.sort(key=lambda m: (m.get("sort_order") or 0, m["match_date"], m["match_time"]))
    return stage_matches


def build_knockout_bracket(matches: list[dict]) -> dict:
    """Knockout tree with winners propagated into the next round."""
    knockout_matches = [m for m in matches if m.get("stage") != "group"]
    prev_round_slots: list[dict] | None = None
    rounds: list[dict] = []

    for stage_key, label, expected in KNOCKOUT_STAGES:
        db_matches = _stage_matches(knockout_matches, stage_key)
        slots: list[dict] = []
        for i in range(expected):
            db_m = db_matches[i] if i < len(db_matches) else None
            home, away = None, None
            if db_m:
                home, away = db_m.get("home_team"), db_m.get("away_team")
            elif prev_round_slots:
                home = prev_round_slots[i * 2].get("winner") if i * 2 < len(prev_round_slots) else None
                away = (
                    prev_round_slots[i * 2 + 1].get("winner")
                    if i * 2 + 1 < len(prev_round_slots)
                    else None
                )
            slots.append(_match_slot(db_m, home, away))
        rounds.append({"key": stage_key, "label": label, "matches": slots})
        prev_round_slots = slots

    third_db = _stage_matches(knockout_matches, "third_place")
    third_slot = _match_slot(third_db[0] if third_db else None, None, None)

    champion = None
    finalist_home = finalist_away = None
    if rounds:
        final = rounds[-1]["matches"][0]
        champion = final.get("winner")
        finalist_home = final.get("home_team")
        finalist_away = final.get("away_team")

    return {
        "rounds": rounds,
        "third_place": third_slot,
        "champion": champion,
        "finalists": [t for t in (finalist_home, finalist_away) if t],
    }


def build_tournament_view(matches: list[dict]) -> dict:
    group_matches = [m for m in matches if m.get("stage") == "group"]
    finished_groups = sum(
        1 for m in group_matches if m.get("actual_home") is not None and m.get("actual_away") is not None
    )
    live_group_matches = sum(
        1
        for m in group_matches
        if m.get("is_live") and m.get("actual_home") is None
    )
    live_teams = _live_group_teams(matches)
    standings = annotate_qualification(
        compute_group_standings(matches, include_live=True),
        matches,
        live_teams=live_teams,
    )
    bracket = build_knockout_bracket(matches)

    qualified = []
    for g in GROUPS:
        if g not in standings:
            continue
        for row in standings[g]:
            if row.get("status") == "qualified":
                qualified.append({"team": row["team"], "group": g, "position": row["position"]})
            elif row.get("status") == "leading":
                qualified.append({"team": row["team"], "group": g, "position": row["position"], "provisional": True})

    confirmed = [q for q in qualified if not q.get("provisional")]

    return {
        "groups": standings,
        "group_order": GROUPS,
        "bracket": bracket,
        "qualified_count": len(confirmed),
        "leading_count": len(qualified),
        "qualified_teams": qualified,
        "group_matches_total": len(group_matches),
        "group_matches_finished": finished_groups,
        "group_matches_live": live_group_matches,
        "has_live_standings": live_group_matches > 0,
    }


def tournament_view_for_json(view: dict) -> dict:
    return view

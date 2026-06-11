"""Simulate tournament standings and bracket from a user's predictions."""

from __future__ import annotations

from knockout_bracket import resolve_r32_pairings
from tournament_standings import (
    GROUPS,
    KNOCKOUT_STAGES,
    _stage_matches,
    _third_place_rankings,
    compute_group_standings_scored,
)


def _predictions_dict(predictions: dict) -> dict[int, dict]:
    return {
        mid: {"home_score": p["home_score"], "away_score": p["away_score"]}
        for mid, p in predictions.items()
    }


def _group_predictions_complete(group: str, matches: list[dict], predictions: dict[int, dict]) -> bool:
    group_matches = [m for m in matches if m.get("stage") == "group" and m.get("group_name") == group]
    if not group_matches:
        return False
    return all(m["id"] in predictions for m in group_matches)


def annotate_predicted_qualification(
    standings: dict[str, list[dict]],
    matches: list[dict],
    predictions: dict[int, dict],
) -> dict[str, list[dict]]:
    all_groups_done = all(_group_predictions_complete(g, matches, predictions) for g in standings)
    third_info = _third_place_rankings(standings) if all_groups_done else {}
    annotated: dict[str, list[dict]] = {}

    for g, rows in standings.items():
        complete = _group_predictions_complete(g, matches, predictions)
        group_rows = []
        for row in rows:
            r = dict(row)
            pos = r["position"]
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


def predicted_winner(home_score: int, away_score: int, home_team: str, away_team: str) -> str:
    if home_score > away_score:
        return home_team
    if away_score > home_score:
        return away_team
    return home_team


def _r32_pairings(
    standings: dict[str, list[dict]],
    matches: list[dict],
    predictions: dict[int, dict],
) -> list[tuple[str | None, str | None]]:
    ready_groups = {
        g
        for g in GROUPS
        if _group_predictions_complete(g, matches, predictions)
    }
    return resolve_r32_pairings(standings, matches, ready_groups=ready_groups)


def _predicted_slot(
    db_m: dict | None,
    home: str | None,
    away: str | None,
    pred: dict | None,
) -> dict:
    if pred and home and away:
        hs, aws = pred["home_score"], pred["away_score"]
        winner = predicted_winner(hs, aws, home, away)
        finished = True
    else:
        hs = aws = None
        winner = None
        finished = False

    return {
        "id": db_m["id"] if db_m else None,
        "home_team": home,
        "away_team": away,
        "display_home": hs,
        "display_away": aws,
        "winner": winner,
        "is_live": False,
        "is_finished": finished,
        "is_predicted": True,
        "match_date": db_m.get("match_date") if db_m else None,
        "match_time": db_m.get("match_time") if db_m else None,
        "venue": db_m.get("venue") if db_m else None,
    }


def _loser(slot: dict) -> str | None:
    if not slot.get("winner"):
        return None
    if slot["winner"] == slot.get("home_team"):
        return slot.get("away_team")
    return slot.get("home_team")


def build_predicted_knockout_bracket(
    matches: list[dict],
    predictions: dict[int, dict],
    standings: dict[str, list[dict]],
) -> dict:
    knockout_matches = [m for m in matches if m.get("stage") != "group"]
    r32_pairings = _r32_pairings(standings, matches, predictions)
    prev_round_slots: list[dict] | None = None
    rounds: list[dict] = []

    for stage_key, label, expected in KNOCKOUT_STAGES:
        db_matches = _stage_matches(knockout_matches, stage_key)
        slots: list[dict] = []
        for i in range(expected):
            db_m = db_matches[i] if i < len(db_matches) else None
            home, away = None, None
            pred = predictions.get(db_m["id"]) if db_m else None

            if db_m and db_m.get("home_team") and db_m.get("away_team"):
                home, away = db_m["home_team"], db_m["away_team"]
            elif stage_key == "round_of_32" and i < len(r32_pairings):
                home, away = r32_pairings[i]
                if db_m and not home:
                    home = db_m.get("home_team")
                if db_m and not away:
                    away = db_m.get("away_team")
            elif prev_round_slots:
                home = prev_round_slots[i * 2].get("winner") if i * 2 < len(prev_round_slots) else None
                away = (
                    prev_round_slots[i * 2 + 1].get("winner")
                    if i * 2 + 1 < len(prev_round_slots)
                    else None
                )
                if db_m:
                    if not home and db_m.get("home_team"):
                        home = db_m["home_team"]
                    if not away and db_m.get("away_team"):
                        away = db_m["away_team"]

            if db_m and not pred:
                pred = predictions.get(db_m["id"])

            slots.append(_predicted_slot(db_m, home, away, pred))
        rounds.append({"key": stage_key, "label": label, "matches": slots})
        prev_round_slots = slots

    semi_slots = rounds[-2]["matches"] if len(rounds) >= 2 else []
    sf_losers = [_loser(s) for s in semi_slots]
    third_home = sf_losers[0] if len(sf_losers) > 0 else None
    third_away = sf_losers[1] if len(sf_losers) > 1 else None
    third_db = _stage_matches(knockout_matches, "third_place")
    third_db_m = third_db[0] if third_db else None
    third_pred = predictions.get(third_db_m["id"]) if third_db_m else None
    if third_db_m and third_db_m.get("home_team"):
        third_home = third_db_m["home_team"]
    if third_db_m and third_db_m.get("away_team"):
        third_away = third_db_m["away_team"]
    third_slot = _predicted_slot(third_db_m, third_home, third_away, third_pred)

    champion = None
    if rounds:
        final = rounds[-1]["matches"][0]
        champion = final.get("winner")

    return {
        "rounds": rounds,
        "third_place": third_slot,
        "champion": champion,
        "finalists": [],
    }


def build_predicted_tournament_view(
    matches: list[dict],
    predictions: dict,
    display_name: str,
    user_id: int,
) -> dict:
    preds = _predictions_dict(predictions)
    group_matches = [m for m in matches if m.get("stage") == "group"]

    def predicted_scores(m: dict):
        pred = preds.get(m["id"])
        if not pred:
            return None
        return pred["home_score"], pred["away_score"]

    standings = annotate_predicted_qualification(
        compute_group_standings_scored(matches, predicted_scores),
        matches,
        preds,
    )
    bracket = build_predicted_knockout_bracket(matches, preds, standings)

    group_predicted = sum(1 for m in group_matches if m["id"] in preds)
    all_knockout = [m for m in matches if m.get("stage") != "group"]
    knockout_predicted = sum(1 for m in all_knockout if m["id"] in preds)

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
        "mode": "predicted",
        "predictor": {"user_id": user_id, "display_name": display_name},
        "groups": standings,
        "group_order": GROUPS,
        "bracket": bracket,
        "qualified_count": len(confirmed),
        "leading_count": len(qualified),
        "qualified_teams": qualified,
        "group_matches_total": len(group_matches),
        "group_matches_finished": group_predicted,
        "group_matches_predicted": group_predicted,
        "knockout_matches_predicted": knockout_predicted,
        "predictions_total": len(preds),
        "group_stage_complete": group_predicted >= len(group_matches) and len(group_matches) > 0,
    }

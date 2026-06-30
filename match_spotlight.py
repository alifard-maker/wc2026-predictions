"""Highlight correct predictors after a match until the next kickoff."""

from __future__ import annotations

from datetime import datetime

from db import get_pool_predictions_summary
from scoring import TIMEZONE


def get_spotlight_match(enriched_matches: list[dict], now: datetime | None = None) -> dict | None:
    """Most recently finished match still in its post-result spotlight window."""
    now = now or datetime.now(TIMEZONE)
    finished = [m for m in enriched_matches if m.get("is_finished")]
    if not finished:
        return None

    latest = max(finished, key=lambda m: m["kickoff"])
    by_kickoff = sorted(enriched_matches, key=lambda m: m["kickoff"])
    next_kickoff = None
    for m in by_kickoff:
        if m["kickoff"] > latest["kickoff"]:
            next_kickoff = m["kickoff"]
            break

    if next_kickoff is not None and now >= next_kickoff:
        return None
    return latest


def build_pool_spotlight(
    pool_id: int,
    enriched_matches: list[dict],
    now: datetime | None = None,
) -> dict | None:
    now = now or datetime.now(TIMEZONE)
    match = get_spotlight_match(enriched_matches, now)
    if not match:
        return None

    preds = get_pool_predictions_summary(pool_id, match["id"])
    correct = [p for p in preds if p.get("points") is not None and p["points"] >= 2]
    correct.sort(key=lambda p: (-p["points"], p["display_name"].lower()))

    by_kickoff = sorted(enriched_matches, key=lambda m: m["kickoff"])
    expires_at = None
    for m in by_kickoff:
        if m["kickoff"] > match["kickoff"]:
            expires_at = m["kickoff"]
            break

    return {
        "match_id": match["id"],
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "display_home": match["display_home"],
        "display_away": match["display_away"],
        "result_display": match.get("result_display"),
        "outcome_line": (match.get("result_display") or {}).get("score_html_hint"),
        "correct_predictors": correct,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }


def spotlight_for_json(spotlight: dict | None, user_id: int | None = None) -> dict | None:
    if not spotlight:
        return None
    rd = spotlight.get("result_display") or {}
    return {
        "match_id": spotlight["match_id"],
        "home_team": spotlight["home_team"],
        "away_team": spotlight["away_team"],
        "display_home": spotlight["display_home"],
        "display_away": spotlight["display_away"],
        "outcome_line": spotlight.get("outcome_line") or rd.get("score_html_hint"),
        "result_display": (
            {
                "winner_team": rd.get("winner_team"),
                "pens_score": rd.get("pens_score"),
                "badge_text": rd.get("badge_text"),
                "score_html_hint": rd.get("score_html_hint"),
            }
            if rd.get("winner_team")
            else None
        ),
        "expires_at": spotlight.get("expires_at"),
        "predictors": [
            {
                "user_id": p["user_id"],
                "display_name": p["display_name"],
                "home_score": p["home_score"],
                "away_score": p["away_score"],
                "points": p["points"],
                "is_you": p["user_id"] == user_id,
            }
            for p in spotlight["correct_predictors"]
        ],
    }

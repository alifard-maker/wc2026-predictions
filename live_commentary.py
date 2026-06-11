"""Build live match commentary for the top-of-page commentator banner."""

from __future__ import annotations

from datetime import datetime

from live_scores import (
    is_match_in_progress,
    sanitize_goal_minute_label,
    sanitize_minute_label,
)
from scoring import TIMEZONE


def _sort_key(minute: int | None, injury: int | None = None, fallback: int = 0) -> int:
    base = (minute or 0) * 100
    if injury:
        base += injury
    return base or fallback


def _events_for_match(match: dict) -> list[dict]:
    events: list[dict] = []
    home = match["home_team"]
    away = match["away_team"]
    score_home = match.get("display_home")
    score_away = match.get("display_away")

    for goal in match.get("goals") or []:
        team = goal.get("team_name") or (home if goal.get("team_side") == "home" else away)
        scorer = goal.get("scorer_name") or "Unknown"
        minute_label = sanitize_goal_minute_label(goal.get("minute_label"))
        is_pen = bool(goal.get("is_penalty"))
        if is_pen:
            text = (
                f"⚽ {minute_label} Penalty goal — {scorer} ({team})"
                if minute_label != "—"
                else f"⚽ Penalty goal — {scorer} ({team})"
            )
        else:
            text = (
                f"⚽ {minute_label} GOAL! {scorer} ({team})"
                if minute_label != "—"
                else f"⚽ GOAL! {scorer} ({team})"
            )
        events.append(
            {
                "type": "goal",
                "minute_label": minute_label,
                "text": text,
                "sort_key": _sort_key(goal.get("minute"), goal.get("injury_minute"), 1000),
            }
        )

    for card in match.get("cards") or []:
        team = card.get("team") or ""
        player = card.get("player_name") or "Player"
        minute_label = sanitize_goal_minute_label(card.get("minute_label"))
        if card.get("card_type") == "red":
            text = (
                f"🟥 {minute_label} Red card — {player} ({team})"
                if minute_label != "—"
                else f"🟥 Red card — {player} ({team})"
            )
            kind = "red_card"
        else:
            text = (
                f"🟨 {minute_label} Yellow card — {player} ({team})"
                if minute_label != "—"
                else f"🟨 Yellow card — {player} ({team})"
            )
            kind = "yellow_card"
        events.append(
            {
                "type": kind,
                "minute_label": minute_label,
                "text": text,
                "sort_key": _sort_key(card.get("minute"), fallback=500),
            }
        )

    for pen in match.get("penalties") or []:
        team = pen.get("taker_team") or ""
        player = pen.get("taker_name") or team
        minute_label = pen.get("minute_label") or ""
        outcome = pen.get("outcome") or "missed"
        minute_val = pen.get("minute") or 0
        if minute_val > 120:
            if outcome == "scored":
                text = f"🎯 Shootout — {player} scores for {team}"
            elif outcome == "saved":
                text = f"🧤 Shootout — saved! {player} ({team}) denied"
            else:
                text = f"❌ Shootout — {player} misses for {team}"
            kind = "shootout"
        else:
            if outcome == "scored":
                text = f"⚽ {minute_label} Penalty — {player} ({team})"
            else:
                text = f"❌ {minute_label} Penalty missed — {player} ({team})"
            kind = "penalty"
        events.append(
            {
                "type": kind,
                "minute_label": minute_label,
                "text": text,
                "sort_key": _sort_key(minute_val, pen.get("injury_minute"), 1500),
            }
        )

    events.sort(key=lambda e: e["sort_key"])

    if match.get("status") == "halftime":
        events.append(
            {
                "type": "halftime",
                "minute_label": "HT",
                "text": f"⏸ Half time — {home} {score_home}–{score_away} {away}",
                "sort_key": 4500,
            }
        )

    return events


def _scoreline(match: dict) -> str:
    home = match["home_team"]
    away = match["away_team"]
    h = match.get("display_home")
    a = match.get("display_away")
    if h is None or a is None:
        return f"{home} vs {away}"
    return f"{home} {h}–{a} {away}"


def _minute_badge(match: dict) -> str:
    if match.get("status") == "halftime":
        return "HT"
    return sanitize_minute_label(match.get("minute_label"))


def _ticker_items(match: dict, events: list[dict]) -> list[str]:
    scoreline = _scoreline(match)
    minute = _minute_badge(match)
    items: list[str] = []

    if match.get("status") == "halftime":
        items.append(f"⏸ {scoreline} at the break")
    else:
        items.append(f"▶ {minute} — {scoreline}")

    for event in events:
        if event["type"] != "halftime":
            items.append(event["text"])

    if len(items) == 1 and match.get("live_minute") is not None:
        items.append(f"📡 Live from {match.get('venue') or 'the stadium'}")

    return items


def commentary_for_match(match: dict) -> dict:
    events = _events_for_match(match)
    ticker_items = _ticker_items(match, events)
    latest = events[-1]["text"] if events else ticker_items[0]

    return {
        "match_id": match["id"],
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "display_home": match.get("display_home"),
        "display_away": match.get("display_away"),
        "minute_label": _minute_badge(match),
        "status": match.get("status"),
        "venue": match.get("venue"),
        "scoreline": _scoreline(match),
        "headline": f"{_scoreline(match)} · {_minute_badge(match)}",
        "latest": latest,
        "events": events,
        "ticker_items": ticker_items,
    }


def _active_live_matches(enriched_matches: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(TIMEZONE)
    live: list[dict] = []
    seen: set[int] = set()
    for m in enriched_matches:
        if m.get("is_live") and m["id"] not in seen:
            live.append(m)
            seen.add(m["id"])
    if live:
        return live

    for m in enriched_matches:
        if m["id"] in seen or m.get("actual_home") is not None:
            continue
        kickoff = m.get("kickoff")
        if kickoff and is_match_in_progress(kickoff, now):
            row = dict(m)
            row["display_home"] = row.get("display_home")
            if row.get("display_home") is None:
                row["display_home"] = row.get("live_home") if row.get("live_home") is not None else 0
            if row.get("display_away") is None:
                row["display_away"] = row.get("live_away") if row.get("live_away") is not None else 0
            if not row.get("minute_label"):
                row["minute_label"] = "LIVE"
            row["is_live"] = True
            row["status"] = row.get("status") or "live"
            live.append(row)
            seen.add(m["id"])
    return live


def build_live_commentary(enriched_matches: list[dict]) -> dict | None:
    """Primary live match commentary for the top banner."""
    live = _active_live_matches(enriched_matches)
    if not live:
        return None
    live.sort(key=lambda m: m.get("kickoff") or datetime.min.replace(tzinfo=TIMEZONE))
    primary = live[0]
    result = commentary_for_match(primary)
    if len(live) > 1:
        others = [f"{m['home_team']} v {m['away_team']}" for m in live[1:]]
        result["also_live"] = others
        result["ticker_items"] = result["ticker_items"] + [
            f"📺 Also live: {name}" for name in others
        ]
    return result


def commentary_for_json(commentary: dict | None) -> dict | None:
    if not commentary:
        return None
    return {
        "match_id": commentary["match_id"],
        "home_team": commentary["home_team"],
        "away_team": commentary["away_team"],
        "display_home": commentary["display_home"],
        "display_away": commentary["display_away"],
        "minute_label": sanitize_minute_label(commentary["minute_label"]),
        "status": commentary["status"],
        "scoreline": commentary["scoreline"],
        "headline": commentary["headline"],
        "latest": commentary["latest"],
        "ticker_items": commentary["ticker_items"],
        "also_live": commentary.get("also_live") or [],
    }

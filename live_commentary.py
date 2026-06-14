"""Build live match commentary for the top-of-page commentator banner."""

from __future__ import annotations

from datetime import datetime

from engagement import build_match_consensus, picks_revealed
from live_scores import (
    format_halftime_label,
    format_hydration_break_label,
    is_match_in_progress,
    announced_added_time_for_match,
    live_minute_display_parts,
    sanitize_goal_minute_label,
    sanitize_minute_label,
)
from scoring import TIMEZONE, calculate_points


def _sort_key(minute: int | None, injury: int | None = None, fallback: int = 0) -> int:
    base = (minute or 0) * 100
    if injury:
        base += injury
    return base or fallback


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _pool_comment_ticker_items(pool_id: int, match_id: int, limit: int = 2) -> list[str]:
    from db import get_pool_comments

    items: list[str] = []
    for comment in get_pool_comments(pool_id, match_id)[:limit]:
        body = _truncate(comment.get("body", ""), 72)
        if body:
            items.append(f"💬 {comment['display_name']}: {body}")
    return items


def _pool_pick_ticker_items(pool_id: int, match: dict) -> list[str]:
    from ai_predictor import is_ai_agent
    from db import get_pool_predictions_summary

    if not picks_revealed(match):
        return []

    live_home = match.get("display_home")
    live_away = match.get("display_away")
    if live_home is None or live_away is None:
        return []

    preds = get_pool_predictions_summary(pool_id, match["id"])
    exact = 0
    on_points = 0
    for pred in preds:
        if is_ai_agent(pred["display_name"]):
            continue
        if pred["home_score"] == live_home and pred["away_score"] == live_away:
            exact += 1
        pts = calculate_points(
            pred["home_score"],
            pred["away_score"],
            live_home,
            live_away,
            bool(pred.get("is_bold")),
        )
        if pts and pts >= 2:
            on_points += 1

    items: list[str] = []
    if exact:
        items.append(
            f"🎯 {exact} player{'s' if exact != 1 else ''} on track for an exact score"
        )
    elif on_points:
        items.append(
            f"🏆 {on_points} player{'s' if on_points != 1 else ''} on track for points at this score"
        )
    return items


def _pool_consensus_ticker_items(pool_id: int, match: dict) -> list[str]:
    consensus = build_match_consensus(pool_id, match["id"])
    total = consensus.get("total") or 0
    if total < 2:
        return []

    home = match["home_team"]
    away = match["away_team"]
    options = [
        (consensus["home_win_pct"], home),
        (consensus["draw_pct"], "a draw"),
        (consensus["away_win_pct"], away),
    ]
    best_pct, label = max(options, key=lambda row: row[0])
    items: list[str] = []
    if best_pct >= 40:
        items.append(f"📊 {best_pct}% of your pool picked {label}")
    popular = consensus.get("popular_score")
    pop_count = consensus.get("popular_count") or 0
    if popular and pop_count >= 2:
        items.append(f"📋 Popular pick: {popular} ({pop_count} players)")
    return items


def _pool_extras_for_live(pool_id: int, match: dict) -> list[str]:
    extras: list[str] = []
    extras.extend(_pool_consensus_ticker_items(pool_id, match))
    extras.extend(_pool_pick_ticker_items(pool_id, match))
    extras.extend(_pool_comment_ticker_items(pool_id, match["id"]))
    return extras


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
    elif match.get("status") == "hydration_break":
        minute = match.get("live_minute")
        label = format_hydration_break_label(minute)
        events.append(
            {
                "type": "hydration_break",
                "minute_label": label,
                "text": f"💧 Drinks break — {home} {score_home}–{score_away} {away}",
                "sort_key": (minute or 22) * 100 + 5,
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


def _announced_added_time(match_id: int) -> int | None:
    return announced_added_time_for_match(match_id)


def _minute_badge(match: dict) -> str:
    if match.get("status") == "halftime":
        kickoff = match.get("kickoff")
        if kickoff:
            return format_halftime_label(kickoff, datetime.now(TIMEZONE))
        return "HT"
    if match.get("status") == "hydration_break":
        return format_hydration_break_label(match.get("live_minute"))
    return sanitize_minute_label(match.get("minute_label"))


def _ticker_items(match: dict, events: list[dict], extras: list[str] | None = None) -> list[str]:
    scoreline = _scoreline(match)
    minute = _minute_badge(match)
    items: list[str] = []

    if match.get("status") == "halftime":
        items.append(f"⏸ Half-time break — {scoreline}")
        kickoff = match.get("kickoff")
        if kickoff:
            items.append(f"⏱ {format_halftime_label(kickoff, datetime.now(TIMEZONE))}")
    elif match.get("status") == "hydration_break":
        items.append(f"💧 Drinks break — {scoreline}")
        items.append(f"⏱ {format_hydration_break_label(match.get('live_minute'))}")
    else:
        items.append(f"▶ {minute} — {scoreline}")

    for event in events:
        if event["type"] != "halftime":
            items.append(event["text"])

    if len(items) == 1 and match.get("live_minute") is not None:
        items.append(f"📡 Live from {match.get('venue') or 'the stadium'}")

    if extras:
        for line in extras:
            if line not in items:
                items.append(line)

    return items


def commentary_for_match(match: dict, extras: list[str] | None = None) -> dict:
    events = _events_for_match(match)
    ticker_items = _ticker_items(match, events, extras)
    latest = events[-1]["text"] if events else ticker_items[0]

    kickoff = match.get("kickoff")
    display_match = {
        **match,
        "announced_added_time": _announced_added_time(match["id"]),
    }
    minute_base, added_time_label = live_minute_display_parts(display_match)
    return {
        "match_id": match["id"],
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "display_home": match.get("display_home"),
        "display_away": match.get("display_away"),
        "minute_label": _minute_badge(match),
        "minute_base": minute_base,
        "added_time_label": added_time_label,
        "status": match.get("status"),
        "venue": match.get("venue"),
        "kickoff_iso": kickoff.isoformat() if kickoff else None,
        "scoreline": _scoreline(match),
        "headline": f"{_scoreline(match)} · {_minute_badge(match)}",
        "latest": latest,
        "events": events,
        "ticker_items": ticker_items,
        "mode": "live",
    }


def _active_live_matches(enriched_matches: list[dict], now: datetime | None = None) -> list[dict]:
    now = now or datetime.now(TIMEZONE)
    live: list[dict] = []
    for m in enriched_matches:
        if not m.get("is_live") or m.get("actual_home") is not None:
            continue
        kickoff = m.get("kickoff")
        if not kickoff or now < kickoff:
            continue
        if not is_match_in_progress(kickoff, now, m):
            continue
        live.append(m)
    return live


def build_live_commentaries(
    enriched_matches: list[dict],
    pool_id: int | None = None,
) -> list[dict]:
    """One commentary banner per match that is live in parallel."""
    now = datetime.now(TIMEZONE)
    live = _active_live_matches(enriched_matches, now)
    if not live:
        return []

    live.sort(
        key=lambda m: (
            m.get("kickoff") or datetime.min.replace(tzinfo=TIMEZONE),
            m.get("id") or 0,
        ),
    )
    commentaries: list[dict] = []
    for match in live:
        extras = _pool_extras_for_live(pool_id, match) if pool_id else []
        row = commentary_for_match(match, extras)
        row["match_label"] = f"{match['home_team']} vs {match['away_team']}"
        commentaries.append(row)
    return commentaries


def build_live_commentary(
    enriched_matches: list[dict],
    pool_id: int | None = None,
) -> dict | None:
    """First live match commentary (compat)."""
    commentaries = build_live_commentaries(enriched_matches, pool_id)
    return commentaries[0] if commentaries else None


def commentaries_for_json(commentaries: list[dict]) -> list[dict]:
    return [row for row in (commentary_for_json(c) for c in commentaries) if row]


def commentary_for_json(commentary: dict | None) -> dict | None:
    if not commentary:
        return None
    status = commentary.get("status")
    minute_label = commentary["minute_label"]
    if status not in ("halftime", "hydration_break"):
        minute_label = sanitize_minute_label(minute_label)
    return {
        "match_id": commentary["match_id"],
        "home_team": commentary["home_team"],
        "away_team": commentary["away_team"],
        "display_home": commentary["display_home"],
        "display_away": commentary["display_away"],
        "minute_label": minute_label,
        "minute_base": commentary.get("minute_base"),
        "added_time_label": commentary.get("added_time_label"),
        "status": status,
        "kickoff_iso": commentary.get("kickoff_iso"),
        "scoreline": commentary["scoreline"],
        "headline": commentary["headline"],
        "latest": commentary["latest"],
        "ticker_items": commentary["ticker_items"],
        "match_label": commentary.get("match_label"),
        "mode": commentary.get("mode", "live"),
    }

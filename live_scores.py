"""Live match state: status, minute, and score display."""

from __future__ import annotations

from datetime import datetime, timedelta

from scoring import OPENING_MATCH_DATE, OPENING_MATCH_TIME, TIMEZONE, parse_match_datetime

MATCH_DURATION = timedelta(minutes=105)  # 45 + 15 HT + 45


def is_match_in_progress(kickoff: datetime, now: datetime) -> bool:
    """True only while the match is actually being played."""
    return kickoff <= now < kickoff + MATCH_DURATION


def apply_live_state(match: dict, now: datetime | None = None) -> dict:
    """Enrich a match dict with display status, minute label, and live/final score."""
    now = now or datetime.now(TIMEZONE)
    m = dict(match)
    kickoff = parse_match_datetime(m["match_date"], m["match_time"])
    in_progress = is_match_in_progress(kickoff, now)

    db_status = m.get("status") or "scheduled"
    live_home = m.get("live_home")
    live_away = m.get("live_away")
    live_minute = m.get("live_minute")
    actual_home = m.get("actual_home")
    actual_away = m.get("actual_away")

    if actual_home is not None and actual_away is not None:
        status = "finished"
        display_home, display_away = actual_home, actual_away
        minute_label = "FT"
    elif in_progress and actual_home is None:
        if db_status == "halftime":
            status = "halftime"
            display_home = 0 if live_home is None else live_home
            display_away = 0 if live_away is None else live_away
            minute_label = "HT"
        else:
            status = "live"
            display_home = 0 if live_home is None else live_home
            display_away = 0 if live_away is None else live_away
            if live_minute is not None:
                minute_label = format_minute(live_minute, "live")
            else:
                live_minute = estimate_minute(now - kickoff)
                minute_label = format_minute(live_minute, "live")
    else:
        status = "scheduled"
        display_home = display_away = None
        minute_label = None
        live_minute = None

    m["status"] = status
    m["kickoff"] = kickoff
    m["display_home"] = display_home
    m["display_away"] = display_away
    m["minute_label"] = minute_label
    m["live_minute"] = live_minute
    m["is_live"] = status in ("live", "halftime")
    m["is_finished"] = status == "finished"
    return m


def estimate_minute(elapsed: timedelta) -> int:
    mins = int(elapsed.total_seconds() // 60)
    if mins <= 45:
        return max(1, mins)
    if mins <= 60:
        return 45
    return min(90, mins - 15)


def format_minute(minute: int | None, status: str) -> str:
    if status == "halftime":
        return "HT"
    if status == "finished":
        return "FT"
    if minute is None:
        return "LIVE"
    if minute >= 90:
        return f"90+{minute - 90}'"
    return f"{minute}'"


def opening_kickoff_iso() -> str:
    kickoff = parse_match_datetime(OPENING_MATCH_DATE, OPENING_MATCH_TIME)
    return kickoff.isoformat()

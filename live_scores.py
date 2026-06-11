"""Live match state: status, minute, and score display."""

from __future__ import annotations

from datetime import datetime, timedelta

from scoring import OPENING_MATCH_DATE, OPENING_MATCH_TIME, TIMEZONE, parse_match_datetime

MATCH_DURATION = timedelta(minutes=105)  # 45 + 15 HT + 45
FIRST_HALF_MINUTES = 45
HALFTIME_BREAK = timedelta(minutes=15)


def normalize_stored_minute(minute: int | None) -> int | None:
    if minute is None:
        return None
    try:
        value = int(minute)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def sanitize_minute_label(label: str | None) -> str:
    if not label:
        return "LIVE"
    cleaned = label.strip()
    if cleaned in {"0", "0'", "0''"}:
        return "LIVE"
    return cleaned


def sanitize_goal_minute_label(label: str | None) -> str:
    if not label:
        return "—"
    cleaned = label.strip()
    if cleaned in {"0", "0'", "0''", "—"}:
        return "—"
    return cleaned


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
    live_minute = normalize_stored_minute(m.get("live_minute"))
    live_injury_minute = m.get("live_injury_minute")
    if live_injury_minute is not None:
        try:
            live_injury_minute = int(live_injury_minute)
            if live_injury_minute <= 0:
                live_injury_minute = None
        except (TypeError, ValueError):
            live_injury_minute = None
    actual_home = m.get("actual_home")
    actual_away = m.get("actual_away")

    if actual_home is not None and actual_away is not None:
        status = "finished"
        display_home, display_away = actual_home, actual_away
        minute_label = "FT"
    elif in_progress and actual_home is None:
        past_halftime = now >= second_half_kickoff(kickoff)
        if db_status == "halftime" and not past_halftime:
            status = "halftime"
            display_home = 0 if live_home is None else live_home
            display_away = 0 if live_away is None else live_away
            minute_label = format_halftime_label(kickoff, now)
        else:
            status = "live"
            display_home = 0 if live_home is None else live_home
            display_away = 0 if live_away is None else live_away
            live_minute, live_injury_minute = effective_live_minute(
                kickoff, now, live_minute, live_injury_minute
            )
            minute_label = sanitize_minute_label(
                format_minute(
                    live_minute,
                    "live",
                    live_injury_minute,
                    kickoff=kickoff,
                    now=now,
                )
            )
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


def second_half_kickoff(kickoff: datetime) -> datetime:
    """Scheduled second-half restart (45' played + 15' break)."""
    return kickoff + timedelta(minutes=FIRST_HALF_MINUTES) + HALFTIME_BREAK


def derive_second_half_minute(kickoff: datetime, now: datetime) -> int:
    """Wall-clock minute in 2nd half when API clock is stuck at or before 45."""
    elapsed = now - second_half_kickoff(kickoff)
    return min(90, FIRST_HALF_MINUTES + max(1, int(elapsed.total_seconds() // 60)))


def effective_live_minute(
    kickoff: datetime,
    now: datetime,
    stored_minute: int | None,
    stored_injury: int | None = None,
) -> tuple[int | None, int | None]:
    """Prefer API/stored minute; derive 2nd-half clock when API freezes at HT."""
    if now < second_half_kickoff(kickoff):
        return stored_minute, stored_injury
    derived = derive_second_half_minute(kickoff, now)
    if stored_minute is None or stored_minute <= FIRST_HALF_MINUTES:
        return derived, None
    if stored_minute > FIRST_HALF_MINUTES:
        injury = stored_injury if stored_minute >= 90 else None
        return stored_minute, injury
    return derived, None


def format_halftime_label(kickoff: datetime, now: datetime) -> str:
    resume = second_half_kickoff(kickoff)
    remaining = resume - now
    if remaining.total_seconds() <= 0:
        return "HT · Resuming soon"
    mins = max(1, int((remaining.total_seconds() + 59) // 60))
    return f"HT · Resuming in {mins}'"


def format_minute(
    minute: int | None,
    status: str,
    injury_minute: int | None = None,
    *,
    kickoff: datetime | None = None,
    now: datetime | None = None,
) -> str:
    if status == "halftime":
        return "HT"
    if status == "finished":
        return "FT"
    if minute is None or minute <= 0:
        return "LIVE"
    now = now or datetime.now(TIMEZONE)
    in_second_half = kickoff is not None and now >= second_half_kickoff(kickoff)
    if injury_minute and injury_minute > 0:
        return f"{minute}+{injury_minute}'"
    # 1st-half stoppage only (46–49 before the break) — never rewrite 2nd-half minutes.
    if (
        not in_second_half
        and FIRST_HALF_MINUTES < minute < 50
    ):
        return f"{FIRST_HALF_MINUTES}+{minute - FIRST_HALF_MINUTES}'"
    return f"{minute}'"


def opening_kickoff_iso() -> str:
    kickoff = parse_match_datetime(OPENING_MATCH_DATE, OPENING_MATCH_TIME)
    return kickoff.isoformat()

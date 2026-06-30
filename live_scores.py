"""Live match state: status, minute, and score display."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from scoring import OPENING_MATCH_DATE, OPENING_MATCH_TIME, TIMEZONE, parse_match_datetime

MATCH_DURATION = timedelta(minutes=105)  # 45 + 15 HT + 45 (scheduled estimate)
KNOCKOUT_SYNC_MAX = timedelta(hours=3, minutes=30)  # ET + penalty shootout
LIVE_SYNC_MAX = KNOCKOUT_SYNC_MAX
FIRST_HALF_MINUTES = 45
EXTRA_TIME_FIRST_HALF_END = 105
EXTRA_TIME_END = 120
SHOOTOUT_MINUTE_BASE = 121
HALFTIME_BREAK = timedelta(minutes=15)
LIVE_PHASE_STATUSES = frozenset({
    "live",
    "halftime",
    "hydration_break",
    "extra_time",
    "penalty_shootout",
    "suspended",
})
FIFA_HYDRATION_MINUTES_1H = frozenset({22, 23, 24, 25})
FIFA_HYDRATION_MINUTES_2H = frozenset({67, 68, 69, 70})


def in_fifa_hydration_window(
    live_minute: int | None,
    kickoff: datetime,
    now: datetime | None = None,
) -> bool:
    """FIFA 2026 mandates a drinks break ~22' into each half (3 minutes)."""
    now = now or datetime.now(TIMEZONE)
    minute = normalize_stored_minute(live_minute)
    if minute is None or now < kickoff:
        return False
    elapsed = (now - kickoff).total_seconds() / 60
    if minute in FIFA_HYDRATION_MINUTES_1H and 19 <= elapsed <= 30:
        return True
    if minute in FIFA_HYDRATION_MINUTES_2H and elapsed >= 64:
        return True
    return False


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


def normalize_stoppage_minute(
    minute: int | None,
    injury: int | None,
) -> tuple[int | None, int | None]:
    """Split absolute clocks like 47' or 94' into base + stoppage."""
    if minute is None:
        return None, injury
    if injury is not None:
        try:
            injury = int(injury) if int(injury) > 0 else None
        except (TypeError, ValueError):
            injury = None
    if minute > EXTRA_TIME_END:
        return minute, injury
    if minute > EXTRA_TIME_FIRST_HALF_END:
        return EXTRA_TIME_FIRST_HALF_END, injury if injury else minute - EXTRA_TIME_FIRST_HALF_END
    if minute > 90:
        return minute, injury
    if FIRST_HALF_MINUTES < minute < 50:
        return FIRST_HALF_MINUTES, injury if injury else minute - FIRST_HALF_MINUTES
    if injury:
        return minute, injury
    return minute, None


def shootout_tally(penalties: list[dict] | None) -> tuple[int, int] | None:
    """Count scored elimination kicks (minute > 120) per side."""
    if not penalties:
        return None
    home = away = 0
    found = False
    for pen in penalties:
        minute = pen.get("minute") or 0
        if minute <= EXTRA_TIME_END:
            continue
        found = True
        if pen.get("outcome") != "scored":
            continue
        team = pen.get("taker_team") or ""
        if team == pen.get("home_team"):
            home += 1
        elif team == pen.get("away_team"):
            away += 1
    return (home, away) if found else None


def shootout_tally_from_meta(match_id: int | None) -> tuple[int, int] | None:
    """Pens score from live-sync metadata when kick rows are not stored yet."""
    if not match_id:
        return None
    import json

    import db

    raw = db.get_sync_meta(f"shootout_score_{match_id}")
    if not raw:
        return None
    try:
        data = json.loads(raw)
        home = int(data.get("home", data.get("homeTeam")))
        away = int(data.get("away", data.get("awayTeam")))
        return home, away
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def resolve_shootout_tally(
    penalties: list[dict] | None,
    match_id: int | None = None,
) -> tuple[int, int] | None:
    tally = shootout_tally(penalties)
    if tally:
        return tally
    return shootout_tally_from_meta(match_id)


def build_result_presentation(
    *,
    display_home: int | None,
    display_away: int | None,
    home_team: str,
    away_team: str,
    shootout_winner: str | None = None,
    penalties: list[dict] | None = None,
    match_id: int | None = None,
) -> dict:
    """Display fields for knockout results decided on penalties."""
    base = {
        "et_score": None,
        "pens_score": None,
        "winner_side": None,
        "winner_team": None,
        "badge_text": None,
        "score_html_hint": None,
    }
    if display_home is None or display_away is None:
        return base

    et = f"{display_home}–{display_away}"
    if shootout_winner not in ("home", "away"):
        return {**base, "et_score": et, "badge_text": et}

    winner_team = home_team if shootout_winner == "home" else away_team
    tally = resolve_shootout_tally(penalties, match_id)
    if tally:
        pen_home, pen_away = tally
        pens = f"{pen_home}–{pen_away} pens"
        return {
            "et_score": et,
            "pens_score": pens,
            "winner_side": shootout_winner,
            "winner_team": winner_team,
            "badge_text": f"{et} · {pens}",
            "score_html_hint": f"{winner_team} win {pens}",
        }

    return {
        "et_score": et,
        "pens_score": None,
        "winner_side": shootout_winner,
        "winner_team": winner_team,
        "badge_text": f"{et} · {winner_team} on pens",
        "score_html_hint": f"{winner_team} win on pens",
    }


def format_shootout_scoreline(
    home_team: str,
    away_team: str,
    home_goals: int,
    away_goals: int,
    penalties: list[dict] | None,
    *,
    match_id: int | None = None,
) -> str | None:
    tally = resolve_shootout_tally(penalties, match_id)
    if not tally:
        return None
    pen_home, pen_away = tally
    return f"{home_team} {home_goals}–{away_goals} {away_team} ({pen_home}–{pen_away} pens)"


def in_announced_added_time_window(minute: int | None, status: str | None = None) -> bool:
    """Referee announced stoppage is only relevant at the end of each half."""
    if status in ("halftime", "hydration_break", "finished", "penalty_shootout"):
        return False
    if minute is None:
        return False
    if minute >= 90:
        return True
    if FIRST_HALF_MINUTES <= minute < 50:
        return True
    return False


def live_minute_display_parts(match: dict) -> tuple[str, str | None]:
    """Clock label for the banner plus optional red announced-added-time suffix."""
    status = match.get("status")
    if status == "penalty_shootout":
        return "Pens", None
    if status == "extra_time":
        label = sanitize_minute_label(match.get("minute_label"))
        if label and label != "LIVE":
            return f"ET {label}" if not label.startswith("ET ") else label, None
        return "ET", None
    if status == "halftime":
        kickoff = match.get("kickoff")
        if kickoff:
            return format_halftime_label(kickoff, datetime.now(TIMEZONE)), None
        return "HT", None
    if status == "hydration_break":
        return format_hydration_break_label(match.get("live_minute")), None
    if status == "suspended":
        label = sanitize_minute_label(match.get("minute_label"))
        if label and label not in {"LIVE", "—"}:
            return f"Delayed · {label}", None
        return "Delayed", None

    label = sanitize_minute_label(match.get("minute_label"))
    minute = normalize_stored_minute(match.get("live_minute"))
    injury = match.get("live_injury_minute")
    if injury is not None:
        try:
            injury = int(injury) if int(injury) > 0 else None
        except (TypeError, ValueError):
            injury = None

    if re.match(r"^\d+\+\d+'?$", label):
        base = label if label.endswith("'") else f"{label}'"
    elif minute is not None:
        minute, injury = normalize_stoppage_minute(minute, injury)
        if injury:
            base = f"{minute}+{injury}'"
        elif label and label.endswith("'"):
            base = label
        else:
            base = f"{minute}'"
    elif label and label.endswith("'"):
        base = label
    else:
        base = label or "LIVE"

    announced = match.get("announced_added_time")
    added_time_label = None
    if announced is not None and in_announced_added_time_window(minute, status):
        try:
            announced = int(announced)
        except (TypeError, ValueError):
            announced = None
        if announced and announced > 0:
            added_time_label = f"+{announced} min added"

    return base, added_time_label


def sanitize_goal_minute_label(label: str | None) -> str:
    if not label:
        return "—"
    cleaned = label.strip()
    if cleaned in {"0", "0'", "0''", "—"}:
        return "—"
    return cleaned


def is_synced_live(match: dict, now: datetime | None = None) -> bool:
    """True when the live sync feed still has this match in play."""
    now = now or datetime.now(TIMEZONE)
    if match.get("actual_home") is not None:
        return False
    if (match.get("status") or "") not in LIVE_PHASE_STATUSES:
        return False
    kickoff = parse_match_datetime(match["match_date"], match["match_time"])
    return kickoff <= now < kickoff + LIVE_SYNC_MAX


def is_match_in_progress(
    kickoff: datetime,
    now: datetime,
    match: dict | None = None,
) -> bool:
    """True while the match is playing (scheduled window or synced live state)."""
    if match and is_synced_live(match, now):
        return kickoff <= now < kickoff + LIVE_SYNC_MAX
    return kickoff <= now < kickoff + MATCH_DURATION


def apply_live_state(match: dict, now: datetime | None = None) -> dict:
    """Enrich a match dict with display status, minute label, and live/final score."""
    now = now or datetime.now(TIMEZONE)
    m = dict(match)
    kickoff = parse_match_datetime(m["match_date"], m["match_time"])
    actual_home = m.get("actual_home")
    actual_away = m.get("actual_away")

    if actual_home is None and now < kickoff:
        m["status"] = "scheduled"
        m["kickoff"] = kickoff
        m["display_home"] = None
        m["display_away"] = None
        m["minute_label"] = None
        m["live_minute"] = None
        m["is_live"] = False
        m["is_finished"] = False
        return m

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

    if db_status == "live" and m.get("id"):
        from db import get_sync_meta

        raw = get_sync_meta(f"hydration_break_{m['id']}")
        if raw:
            try:
                import json

                meta = json.loads(raw)
                since = datetime.fromisoformat(meta["since"])
                if since.tzinfo is None:
                    since = since.replace(tzinfo=TIMEZONE)
                if (now - since).total_seconds() < 360:
                    db_status = "hydration_break"
                    if live_minute is None and meta.get("minute"):
                        live_minute = normalize_stored_minute(meta.get("minute"))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
        elif in_fifa_hydration_window(live_minute, kickoff, now):
            db_status = "hydration_break"

    synced_live = is_synced_live(m, now)
    in_progress = is_match_in_progress(kickoff, now, m)
    if actual_home is not None and actual_away is not None:
        if now < kickoff:
            m["status"] = "scheduled"
            m["kickoff"] = kickoff
            m["display_home"] = None
            m["display_away"] = None
            m["minute_label"] = None
            m["live_minute"] = None
            m["is_live"] = False
            m["is_finished"] = False
            return m
        status = "finished"
        display_home, display_away = actual_home, actual_away
        minute_label = "FT"
    elif actual_home is None and (synced_live or in_progress):
        display_home = 0 if live_home is None else live_home
        display_away = 0 if live_away is None else live_away
        if db_status == "hydration_break":
            status = "hydration_break"
            live_minute = normalize_stored_minute(live_minute)
            minute_label = format_hydration_break_label(live_minute)
        elif db_status == "penalty_shootout":
            status = "penalty_shootout"
            live_minute = None
            live_injury_minute = None
            minute_label = format_minute(None, "penalty_shootout")
        elif db_status == "extra_time":
            status = "extra_time"
            second_half_start = _second_half_start_for_match(m.get("id"))
            live_minute, live_injury_minute = effective_live_minute(
                kickoff,
                now,
                live_minute,
                live_injury_minute,
                second_half_start,
            )
            live_minute, live_injury_minute = normalize_stoppage_minute(
                live_minute, live_injury_minute
            )
            minute_label = sanitize_minute_label(
                format_minute(
                    live_minute,
                    "extra_time",
                    live_injury_minute,
                    kickoff=kickoff,
                    now=now,
                )
            )
        elif db_status == "halftime" or (
            not synced_live and is_halftime_break(kickoff, now, db_status)
        ):
            status = "halftime"
            minute_label = format_halftime_label(kickoff, now)
        elif db_status == "suspended":
            status = "suspended"
            live_minute = normalize_stored_minute(live_minute)
            minute_label = sanitize_minute_label(
                format_minute(
                    live_minute,
                    "suspended",
                    live_injury_minute,
                    kickoff=kickoff,
                    now=now,
                )
            )
        else:
            status = "live"
            second_half_start = _second_half_start_for_match(m.get("id"))
            live_minute, live_injury_minute = effective_live_minute(
                kickoff,
                now,
                live_minute,
                live_injury_minute,
                second_half_start,
            )
            live_minute, live_injury_minute = normalize_stoppage_minute(
                live_minute, live_injury_minute
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
    m["live_injury_minute"] = live_injury_minute
    m["is_live"] = status in LIVE_PHASE_STATUSES
    m["is_finished"] = status == "finished"
    if m["is_live"]:
        announced = announced_added_time_for_match(m.get("id"))
        minute_base, added_time_label = live_minute_display_parts(
            {**m, "announced_added_time": announced}
        )
        m["minute_base"] = minute_base
        m["added_time_label"] = added_time_label
    else:
        m["minute_base"] = None
        m["added_time_label"] = None
    return m


def announced_added_time_for_match(match_id: int | None) -> int | None:
    if not match_id:
        return None
    from db import get_sync_meta

    raw = get_sync_meta(f"announced_added_time_{match_id}")
    if not raw:
        return None
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


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


def elapsed_wall_minutes(kickoff: datetime, now: datetime) -> int:
    if now < kickoff:
        return 0
    return int((now - kickoff).total_seconds() // 60)


def minute_from_kickoff(kickoff: datetime, now: datetime) -> int | None:
    """Match clock from kickoff wall time (45' + 15' HT break + 2nd half)."""
    elapsed = elapsed_wall_minutes(kickoff, now)
    if elapsed <= 0:
        return None
    if elapsed <= FIRST_HALF_MINUTES:
        return max(1, elapsed)
    if elapsed <= 60:
        return FIRST_HALF_MINUTES
    return min(90, FIRST_HALF_MINUTES + elapsed - 60)


def is_halftime_break(kickoff: datetime, now: datetime, db_status: str) -> bool:
    elapsed = elapsed_wall_minutes(kickoff, now)
    if elapsed > 60:
        return False
    if db_status == "halftime":
        return True
    return 45 < elapsed <= 60


def _second_half_start_for_match(match_id: int | None) -> datetime | None:
    if not match_id:
        return None
    import db

    raw = db.get_sync_meta(f"second_half_start_{match_id}")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def minute_from_second_half_start(second_half_start: datetime, now: datetime) -> int:
    elapsed = int((now - second_half_start).total_seconds() // 60)
    return min(90, FIRST_HALF_MINUTES + max(1, elapsed))


def effective_live_minute(
    kickoff: datetime,
    now: datetime,
    stored_minute: int | None,
    stored_injury: int | None = None,
    second_half_start: datetime | None = None,
) -> tuple[int | None, int | None]:
    """Prefer stored/API minute; derive 2nd half from restart time, not kickoff+15'."""
    elapsed = elapsed_wall_minutes(kickoff, now)

    if stored_minute is not None and stored_minute > FIRST_HALF_MINUTES:
        if stored_minute >= 90 or (stored_minute < 50 and stored_injury):
            injury = stored_injury
        else:
            injury = None
        return stored_minute, injury

    if second_half_start and now >= second_half_start:
        return minute_from_second_half_start(second_half_start, now), None

    if stored_minute is not None and stored_injury and stored_minute <= FIRST_HALF_MINUTES:
        return stored_minute, stored_injury

    if stored_minute is not None and elapsed <= FIRST_HALF_MINUTES:
        kickoff_minute = minute_from_kickoff(kickoff, now)
        if kickoff_minute is None:
            # Sub-minute: API clocks often jump ahead right at kickoff.
            return min(stored_minute, 1), stored_injury
        if stored_minute > kickoff_minute:
            return kickoff_minute, stored_injury
        return stored_minute, stored_injury

    kickoff_minute = minute_from_kickoff(kickoff, now)
    if elapsed <= 60:
        return kickoff_minute, None

    return stored_minute, stored_injury


def format_hydration_break_label(minute: int | None) -> str:
    if minute is not None and minute > 0:
        return f"💧 Drinks break · {minute}'"
    return "💧 Drinks break"


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
    if status == "hydration_break":
        return format_hydration_break_label(minute)
    if status == "penalty_shootout":
        return "Pens"
    if status == "finished":
        return "FT"
    if minute is None or minute <= 0:
        return "ET" if status == "extra_time" else "LIVE"
    now = now or datetime.now(TIMEZONE)
    in_second_half = kickoff is not None and now >= second_half_kickoff(kickoff)
    if injury_minute and injury_minute > 0:
        base = f"{minute}+{injury_minute}'"
        return f"ET {base}" if status == "extra_time" else base
    if status == "extra_time" and minute > 90:
        return f"ET {minute}'"
    if minute is not None and minute > 90 and status != "extra_time":
        return f"90+{minute - 90}'"
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


def _match_row_dict(row) -> dict:
    return dict(row) if not isinstance(row, dict) else row


def next_scheduled_kickoff(matches, now: datetime | None = None) -> dict | None:
    """Soonest fixture that has not kicked off yet."""
    now = now or datetime.now(TIMEZONE)
    best: tuple[datetime, dict] | None = None
    for raw in matches:
        row = _match_row_dict(raw)
        if row.get("actual_home") is not None:
            continue
        kickoff = parse_match_datetime(row["match_date"], row["match_time"])
        if kickoff <= now:
            continue
        if best is None or kickoff < best[0]:
            best = (kickoff, row)
    if not best:
        return None
    kickoff, match = best
    return {
        "match_id": match["id"],
        "home_team": match["home_team"],
        "away_team": match["away_team"],
        "match_date": match["match_date"],
        "match_time": match["match_time"],
        "iso": kickoff.isoformat(),
        "display": (
            f"{match['home_team']} vs {match['away_team']} · "
            f"{kickoff.strftime('%d %b %Y, %H:%M')} ET"
        ),
    }

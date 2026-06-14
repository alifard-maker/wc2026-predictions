"""Supplement live scores, clock, goals, and cards from ESPN's public FIFA API."""

from __future__ import annotations

import json
import logging
import re
import ssl
import urllib.error
import urllib.request
from datetime import datetime

try:
    import certifi
except ImportError:
    certifi = None

import db
from live_score_sync import canonical_team_name, _db_kickoff_et, _kickoffs_align, _match_started
from scoring import TIMEZONE

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
ESPN_SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/summary"

DRINKS_BREAK_MARKERS = (
    "delay in match for a drinks break",
    "delay in match for a drink break",
    "hydration break",
    "water break",
    "drinks break",
    "drink break",
    "cooling break",
    "cooling breaks",
)

DELAY_ONLY_MARKERS = (
    "delay in match",
    "match delayed",
)

PLAY_RESUMED_MARKERS = (
    "play resumes",
    "match resumes",
    "restarts",
    "restart",
    "kick-off",
    "kick off",
    "second half begins",
    "second half kicks",
    "back underway",
)

PLAY_EVENT_MARKERS = (
    "goal!",
    "goal ",
    "yellow card",
    "red card",
    "substitution",
    "corner",
    "offside",
    "free kick",
    "penalty",
    "attempt",
    "shot ",
)

HYDRATION_BREAK_MAX_SECONDS = 360

ADDED_TIME_RE = re.compile(
    r"(?i)(?:indicates|showing|allocate[sd]?)\s+(\d{1,2})\s+minutes?|"
    r"(\d{1,2})\s+minutes?\s+of\s+(?:added|stoppage)\s+time|"
    r"(?:added|stoppage)\s+time\s+(?:of\s+)?(\d{1,2})"
)

ESPN_TEAM_ALIASES: dict[str, str] = {
    "south korea": "Korea Republic",
    "korea republic": "Korea Republic",
    "united states": "USA",
    "usa": "USA",
    "ivory coast": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "turkey": "Türkiye",
    "czech republic": "Czechia",
    "iran": "IR Iran",
    "dr congo": "Congo DR",
    "cape verde": "Cabo Verde",
    "curacao": "Curaçao",
    "republic of ireland": "Ireland",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
}


def is_enabled() -> bool:
    return True


def _fetch_scoreboard(dates: str | None = None) -> dict | None:
    url = ESPN_SCOREBOARD
    if dates:
        url = f"{url}?dates={dates}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "wc2026-predictions/1.0"},
    )
    if certifi is not None:
        ctx = ssl.create_default_context(cafile=certifi.where())
    else:
        ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.warning("ESPN scoreboard request failed: %s", exc)
        db.set_sync_meta("espn_sync_error", str(exc)[:200])
        return None


def _fetch_summary(event_id: str) -> dict | None:
    if not event_id:
        return None
    url = f"{ESPN_SUMMARY}?event={event_id}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "wc2026-predictions/1.0"},
    )
    if certifi is not None:
        ctx = ssl.create_default_context(cafile=certifi.where())
    else:
        ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError) as exc:
        logger.debug("ESPN summary request failed for %s: %s", event_id, exc)
        return None


def _parse_commentary_minute(time_obj: dict | None) -> int | None:
    display = (time_obj or {}).get("displayValue")
    minute, _ = _parse_espn_minute(display)
    return minute


def _commentary_is_drinks_break(text: str) -> bool:
    lowered = text.lower().strip()
    return any(marker in lowered for marker in DRINKS_BREAK_MARKERS)


def _commentary_is_delay_only(text: str) -> bool:
    lowered = text.lower().strip()
    if _commentary_is_drinks_break(lowered):
        return True
    return any(marker in lowered for marker in DELAY_ONLY_MARKERS)


def _commentary_is_play_resumed(text: str) -> bool:
    lowered = text.lower().strip()
    if _commentary_is_drinks_break(text) or _commentary_is_delay_only(text):
        return False
    if any(marker in lowered for marker in PLAY_RESUMED_MARKERS):
        return True
    return any(marker in lowered for marker in PLAY_EVENT_MARKERS)


def _summary_commentary(event_id: str) -> list[dict]:
    payload = _fetch_summary(event_id)
    if not payload:
        return []
    return payload.get("commentary") or []


def _latest_drinks_break(commentary: list[dict]) -> tuple[int | None, int | None]:
    latest_idx = None
    latest_minute = None
    for idx, item in enumerate(commentary):
        text = (item.get("text") or "").strip()
        if text and _commentary_is_drinks_break(text):
            latest_idx = idx
            latest_minute = _parse_commentary_minute(item.get("time"))
    return latest_idx, latest_minute


def _hydration_play_resumed_after_break(event_id: str) -> bool:
    commentary = _summary_commentary(event_id)
    break_idx, _ = _latest_drinks_break(commentary)
    if break_idx is None:
        return False
    for item in commentary[break_idx + 1:]:
        text = (item.get("text") or "").strip()
        if text and _commentary_is_play_resumed(text):
            return True
    return False


def _hydration_break_from_summary(event_id: str) -> tuple[bool, int | None]:
    """True when ESPN commentary shows an active FIFA drinks/hydration break."""
    commentary = _summary_commentary(event_id)
    if not commentary:
        return False, None

    break_idx, break_minute = _latest_drinks_break(commentary)
    if break_idx is None:
        return False, None

    for item in commentary[break_idx + 1:]:
        text = (item.get("text") or "").strip()
        if text and _commentary_is_play_resumed(text):
            return False, None

    return True, break_minute


def _hydration_break_state(event_id: str, match_id: int) -> tuple[bool, int | None]:
    active, minute = _hydration_break_from_summary(event_id) if event_id else (False, None)
    meta_key = f"hydration_break_{match_id}"
    now = datetime.now(TIMEZONE)
    if active:
        db.set_sync_meta(
            meta_key,
            json.dumps(
                {
                    "minute": minute,
                    "since": now.isoformat(),
                }
            ),
        )
        return True, minute

    raw = db.get_sync_meta(meta_key)
    if raw:
        try:
            meta = json.loads(raw)
            since = datetime.fromisoformat(meta["since"])
            age = (now - since).total_seconds()
            if age < HYDRATION_BREAK_MAX_SECONDS:
                if event_id and _hydration_play_resumed_after_break(event_id):
                    db.set_sync_meta(meta_key, "")
                    return False, None
                if event_id and not _summary_commentary(event_id):
                    return True, meta.get("minute")
                return True, meta.get("minute")
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
        db.set_sync_meta(meta_key, "")
    return False, None


def _announced_added_time_from_summary(event_id: str) -> int | None:
    commentary = _summary_commentary(event_id)
    for item in reversed(commentary):
        text = (item.get("text") or "").strip()
        if not text:
            continue
        match = ADDED_TIME_RE.search(text)
        if not match:
            continue
        for group in match.groups():
            if group:
                return int(group)
    return None


def _sync_announced_added_time(event_id: str, match_id: int, db_status: str) -> None:
    meta_key = f"announced_added_time_{match_id}"
    if db_status in ("halftime", "finished"):
        db.set_sync_meta(meta_key, "")
        return
    if not event_id:
        return
    minutes = _announced_added_time_from_summary(event_id)
    if minutes:
        db.set_sync_meta(meta_key, str(minutes))


def _parse_espn_minute(display: str | None) -> tuple[int | None, int | None]:
    if not display:
        return None, None
    text = (
        str(display)
        .strip()
        .replace("′", "'")
        .replace("'", "")
        .strip()
    )
    if not text or text.upper() in {"HT", "HALFTIME"}:
        return 45, None
    match = re.match(r"^(\d+)(?:\+(\d+))?$", text)
    if not match:
        return None, None
    minute = int(match.group(1))
    if minute < 1:
        return None, None
    injury = int(match.group(2)) if match.group(2) else None
    return minute, injury


ESPN_NOT_STARTED = frozenset({
    "STATUS_SCHEDULED",
    "STATUS_PRE",
    "STATUS_DELAYED",
    "STATUS_POSTPONED",
    "STATUS_CANCELED",
    "STATUS_CANCELLED",
})


def _espn_not_started(comp_status: dict | None) -> bool:
    name = ((comp_status or {}).get("type") or {}).get("name") or ""
    return name in ESPN_NOT_STARTED


def _espn_status(comp_status: dict | None) -> str | None:
    type_info = (comp_status or {}).get("type") or {}
    name = type_info.get("name") or ""
    state = type_info.get("state") or ""
    completed = bool(type_info.get("completed"))
    if name in ESPN_NOT_STARTED:
        return None
    if name in {"STATUS_HALFTIME", "STATUS_PAUSE"}:
        return "halftime"
    detail = (type_info.get("detail") or "").strip().upper()
    short_detail = (type_info.get("shortDetail") or "").strip().upper()
    if (
        completed
        or state == "post"
        or name in {"STATUS_FULL_TIME", "STATUS_FINAL", "STATUS_END_PERIOD"}
        or detail in {"FT", "FULL TIME", "FULL-TIME"}
        or short_detail in {"FT", "FULL TIME", "FULL-TIME"}
    ):
        return "finished"
    if state == "in" or name in {
        "STATUS_IN_PROGRESS",
        "STATUS_FIRST_HALF",
        "STATUS_SECOND_HALF",
        "STATUS_EXTRA_TIME",
        "STATUS_PENALTY_SHOOTOUT",
    }:
        return "live"
    display = (comp_status or {}).get("displayClock")
    if display:
        minute, _ = _parse_espn_minute(display)
        if minute and minute > 0:
            return "live"
    return None


def _is_goal_event(type_text: str) -> bool:
    return type_text == "Goal" or type_text.startswith("Goal ")


def _espn_event_kickoff(event: dict) -> datetime | None:
    raw = event.get("date")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(TIMEZONE)
    except ValueError:
        return None


def _find_db_match(
    home_name: str | None,
    away_name: str | None,
    db_matches: list[dict],
    our_teams: set[str],
    kickoff_et: datetime | None = None,
) -> dict | None:
    if not home_name or not away_name:
        return None
    candidates = [
        m
        for m in db_matches
        if m["home_team"] == home_name and m["away_team"] == away_name
    ]
    if not candidates:
        return None
    if len(candidates) == 1:
        only = candidates[0]
        if kickoff_et and not _kickoffs_align(kickoff_et, only):
            db.align_match_schedule(only["id"], kickoff_et)
            only = dict(only)
            only["match_date"] = kickoff_et.strftime("%Y-%m-%d")
            only["match_time"] = kickoff_et.strftime("%H:%M")
        return only
    if kickoff_et:
        for m in candidates:
            if m["match_date"] == kickoff_et.strftime("%Y-%m-%d"):
                return m
        best = min(
            candidates,
            key=lambda m: abs((kickoff_et - _db_kickoff_et(m)).total_seconds()),
        )
        if _kickoffs_align(kickoff_et, best):
            return best
        return None
    return candidates[0]


def find_espn_event_id(db_match: dict, our_teams: set[str] | None = None) -> str | None:
    """Resolve ESPN event id for a database match (cached after live sync)."""
    match_id = db_match["id"]
    cached = db.get_sync_meta(f"espn_event_{match_id}")
    if cached:
        return cached

    our_teams = our_teams or set(db.get_distinct_teams())
    db_matches = [dict(db_match)]
    dates_to_try: list[str | None] = []
    if db_match.get("match_date"):
        dates_to_try.append(db_match["match_date"].replace("-", ""))
    dates_to_try.append(None)

    for dates in dates_to_try:
        payload = _fetch_scoreboard(dates)
        if not payload:
            continue
        for event in payload.get("events") or []:
            competitions = event.get("competitions") or []
            if not competitions:
                continue
            competition = competitions[0]
            home_name, away_name, _ = _competitor_teams(competition, our_teams)
            kickoff_et = _espn_event_kickoff(event)
            matched = _find_db_match(home_name, away_name, db_matches, our_teams, kickoff_et)
            if matched and matched["id"] == match_id:
                event_id = str(event.get("id") or "")
                if event_id:
                    db.set_sync_meta(f"espn_event_{match_id}", event_id)
                return event_id or None
    return None


def _competitor_teams(
    competition: dict,
    our_teams: set[str],
) -> tuple[str | None, str | None, dict[str, str]]:
    home_name = away_name = None
    team_by_id: dict[str, str] = {}
    for competitor in competition.get("competitors") or []:
        raw_name = (competitor.get("team") or {}).get("displayName") or ""
        canonical = canonical_team_name(raw_name, our_teams)
        if not canonical:
            alias = ESPN_TEAM_ALIASES.get(raw_name.lower().strip())
            if alias and alias in our_teams:
                canonical = alias
        team_id = (competitor.get("team") or {}).get("id")
        if team_id is not None and canonical:
            team_by_id[str(team_id)] = canonical
        if competitor.get("homeAway") == "home":
            home_name = canonical
        elif competitor.get("homeAway") == "away":
            away_name = canonical
    return home_name, away_name, team_by_id


def _sync_espn_event(
    event: dict,
    db_matches: list[dict],
    our_teams: set[str],
) -> dict:
    result = {
        "matched": 0,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "cards_removed": 0,
        "espn_minute": None,
    }
    competitions = event.get("competitions") or []
    if not competitions:
        return result

    competition = competitions[0]
    home_name, away_name, team_by_id = _competitor_teams(competition, our_teams)
    kickoff_et = _espn_event_kickoff(event)
    db_match = _find_db_match(home_name, away_name, db_matches, our_teams, kickoff_et)
    if not db_match:
        return result

    match_id = db_match["id"]
    comp_status = competition.get("status") or event.get("status") or {}

    if _espn_not_started(comp_status):
        if (db_match.get("status") or "") in ("live", "halftime", "hydration_break") and db_match.get("actual_home") is None:
            db.clear_match_live_state(match_id)
            db.set_sync_meta(f"espn_live_source_{match_id}", "")
            db.set_sync_meta(f"hydration_break_{match_id}", "")
            result["reset_scheduled"] = 1
        return result

    result["matched"] = 1
    result["match_id"] = match_id
    event_id = str(event.get("id") or "")
    if event_id:
        db.set_sync_meta(f"espn_event_{match_id}", event_id)

    home_score = away_score = 0
    for competitor in competition.get("competitors") or []:
        score = competitor.get("score")
        try:
            value = int(score) if score is not None else 0
        except (TypeError, ValueError):
            value = 0
        if competitor.get("homeAway") == "home":
            home_score = value
        elif competitor.get("homeAway") == "away":
            away_score = value

    db_status = _espn_status(comp_status)

    display_clock = (
        comp_status.get("displayClock")
        or (comp_status.get("type") or {}).get("detail")
        or (comp_status.get("type") or {}).get("shortDetail")
    )
    live_minute, live_injury = _parse_espn_minute(display_clock)
    result["espn_minute"] = live_minute

    if (
        db_status == "finished"
        and db_match.get("actual_home") is None
        and _match_started(db_match)
        and _kickoffs_align(kickoff_et, db_match)
        and db.update_match_result(match_id, home_score, away_score)
    ):
        result["finished"] = 1
    elif db_match.get("actual_home") is None and db_status:
        hydration_active, hydration_minute = (False, None)
        if event_id:
            hydration_active, hydration_minute = _hydration_break_state(event_id, match_id)
        if hydration_active:
            db_status = "hydration_break"
            if hydration_minute is not None:
                live_minute = hydration_minute
                live_injury = None
        elif db_status == "halftime":
            live_minute = 45
            live_injury = None
        if live_minute is not None and live_minute <= 0:
            live_minute = None
        if event_id:
            _sync_announced_added_time(event_id, match_id, db_status)
        db.update_match_live(
            match_id,
            home_score,
            away_score,
            live_minute,
            db_status,
            live_injury,
        )
        result["updated_live"] = 1
        result["live_home"] = home_score
        result["live_away"] = away_score
        db.set_sync_meta(f"espn_live_source_{match_id}", datetime.now(TIMEZONE).isoformat())

    expected_cards: list[tuple[str, str, str]] = []
    for detail in competition.get("details") or []:
        type_text = ((detail.get("type") or {}).get("text") or "").strip()
        player = None
        athletes = detail.get("athletesInvolved") or []
        if athletes:
            player = (athletes[0].get("displayName") or athletes[0].get("fullName") or "").strip()
        if not player:
            continue

        team_id = str((detail.get("team") or {}).get("id") or "")
        team_name = team_by_id.get(team_id)
        if not team_name:
            continue

        minute, injury = _parse_espn_minute((detail.get("clock") or {}).get("displayValue"))
        if _is_goal_event(type_text):
            if minute is None:
                continue
            if team_name == db_match["home_team"]:
                side = "home"
            elif team_name == db_match["away_team"]:
                side = "away"
            else:
                continue
            is_pen = bool(detail.get("penaltyKick"))
            if db.upsert_match_goal(match_id, side, player, minute, injury, is_pen):
                result["goals_added"] += 1
        elif type_text == "Yellow Card":
            expected_cards.append((player, team_name, "yellow"))
            if db.upsert_player_card(match_id, player, team_name, "yellow", minute):
                result["cards_added"] += 1
        elif type_text == "Red Card":
            expected_cards.append((player, team_name, "red"))
            if db.upsert_player_card(match_id, player, team_name, "red", minute):
                result["cards_added"] += 1

    if result["matched"]:
        finished = db_match.get("actual_home") is not None
        removed = db.reconcile_synced_cards(
            match_id,
            expected_cards,
            authoritative=finished,
        )
        if removed:
            result["cards_removed"] = removed

    return result


def sync_historical_cards(
    db_matches: list[dict] | None = None,
    our_teams: set[str] | None = None,
    match_dates: list[str] | None = None,
) -> dict:
    """Re-fetch ESPN events for past match dates to drop rescinded cards (e.g. VAR)."""
    if not match_dates:
        return {"ok": True, "dates": 0, "matched": 0}

    our_teams = our_teams or set(db.get_distinct_teams())
    db_matches = db_matches or [dict(m) for m in db.get_all_matches()]
    totals = {"ok": True, "dates": 0, "matched": 0, "cards_removed": 0, "matched_match_ids": []}

    for date_str in match_dates:
        espn_date = (date_str or "").replace("-", "")
        if len(espn_date) != 8:
            continue
        payload = _fetch_scoreboard(espn_date)
        if not payload:
            continue
        totals["dates"] += 1
        for event in payload.get("events") or []:
            row = _sync_espn_event(event, db_matches, our_teams)
            if row.get("matched"):
                totals["matched"] += 1
                if row.get("match_id") is not None:
                    totals["matched_match_ids"].append(row["match_id"])
                totals["cards_removed"] += row.get("cards_removed") or 0

    return totals


def sync_from_espn(
    db_matches: list[dict] | None = None,
    our_teams: set[str] | None = None,
) -> dict:
    """Pull live events from ESPN and merge into the database."""
    if not is_enabled():
        return {"ok": False, "skipped": True, "reason": "disabled"}

    payload = _fetch_scoreboard()
    if not payload:
        summary = {
            "ok": False,
            "error": "espn_request_failed",
            "synced_at": datetime.now(TIMEZONE).isoformat(),
        }
        db.set_sync_meta("espn_sync_summary", json.dumps(summary))
        return summary

    our_teams = our_teams or set(db.get_distinct_teams())
    db_matches = db_matches or [dict(m) for m in db.get_all_matches()]

    totals = {
        "matched": 0,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "espn_events": len(payload.get("events") or []),
        "matched_match_ids": [],
    }

    for event in payload.get("events") or []:
        row = _sync_espn_event(event, db_matches, our_teams)
        for key in totals:
            if key == "matched_match_ids":
                continue
            value = row.get(key)
            totals[key] += value if isinstance(value, (int, float)) else 0
        if row.get("updated_live") and row.get("match_id"):
            totals["matched_match_ids"].append(row["match_id"])
        if row.get("espn_minute") is not None and row["espn_minute"] > 0:
            totals["espn_minute"] = row["espn_minute"]

    summary = {
        "ok": True,
        **totals,
        "synced_at": datetime.now(TIMEZONE).isoformat(),
    }
    db.set_sync_meta("espn_sync_summary", json.dumps(summary))
    db.set_sync_meta("espn_sync_error", "")
    return summary

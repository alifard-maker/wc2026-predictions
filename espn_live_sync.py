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
from live_score_sync import canonical_team_name
from scoring import TIMEZONE

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

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


def _fetch_scoreboard() -> dict | None:
    req = urllib.request.Request(
        ESPN_SCOREBOARD,
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
    if completed or name in {"STATUS_FULL_TIME", "STATUS_FINAL"}:
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


def _find_db_match(
    home_name: str | None,
    away_name: str | None,
    db_matches: list[dict],
    our_teams: set[str],
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
    return candidates[0] if len(candidates) == 1 else candidates[0]


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
        "espn_minute": None,
    }
    competitions = event.get("competitions") or []
    if not competitions:
        return result

    competition = competitions[0]
    home_name, away_name, team_by_id = _competitor_teams(competition, our_teams)
    db_match = _find_db_match(home_name, away_name, db_matches, our_teams)
    if not db_match:
        return result

    match_id = db_match["id"]
    comp_status = competition.get("status") or event.get("status") or {}

    if _espn_not_started(comp_status):
        if (db_match.get("status") or "") in ("live", "halftime") and db_match.get("actual_home") is None:
            db.clear_match_live_state(match_id)
            db.set_sync_meta(f"espn_live_source_{match_id}", "")
            result["reset_scheduled"] = 1
        return result

    result["matched"] = 1
    result["match_id"] = match_id

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

    if db_status == "finished" and db_match.get("actual_home") is None:
        db.update_match_result(match_id, home_score, away_score)
        result["finished"] = 1
    elif db_match.get("actual_home") is None and db_status:
        if db_status == "halftime":
            live_minute = 45
            live_injury = None
        if live_minute is not None and live_minute <= 0:
            live_minute = None
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
            if db.upsert_player_card(match_id, player, team_name, "yellow", minute):
                result["cards_added"] += 1
        elif type_text == "Red Card":
            if db.upsert_player_card(match_id, player, team_name, "red", minute):
                result["cards_added"] += 1

    return result


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

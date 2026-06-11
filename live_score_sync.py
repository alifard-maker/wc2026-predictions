"""Automatic live score sync from football-data.org (every ~10s)."""

from __future__ import annotations

import json
import logging
import os
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime

import db
from scoring import TIMEZONE

logger = logging.getLogger(__name__)

API_BASE = "https://api.football-data.org/v4"
SYNC_COOLDOWN_SECONDS = int(os.environ.get("LIVE_SYNC_INTERVAL", "10"))

# football-data.org names → our fixture team names
API_TEAM_ALIASES: dict[str, str] = {
    "south korea": "Korea Republic",
    "korea republic": "Korea Republic",
    "united states": "USA",
    "usa": "USA",
    "ivory coast": "Côte d'Ivoire",
    "cote divoire": "Côte d'Ivoire",
    "côte d'ivoire": "Côte d'Ivoire",
    "turkey": "Türkiye",
    "türkiye": "Türkiye",
    "czech republic": "Czechia",
    "czechia": "Czechia",
    "iran": "IR Iran",
    "ir iran": "IR Iran",
    "dr congo": "Congo DR",
    "congo dr": "Congo DR",
    "cape verde": "Cabo Verde",
    "cabo verde": "Cabo Verde",
    "bosnia-herzegovina": "Bosnia and Herzegovina",
    "bosnia and herzegovina": "Bosnia and Herzegovina",
    "curacao": "Curaçao",
    "curaçao": "Curaçao",
    "republic of ireland": "Ireland",
    "north macedonia": "North Macedonia",
    "new zealand": "New Zealand",
    "saudi arabia": "Saudi Arabia",
    "korea dpr": "Korea DPR",
    "uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
}

LIVE_API_STATUSES = frozenset({"IN_PLAY", "LIVE", "PAUSED"})
FINISHED_API_STATUS = "FINISHED"
UNFOLD_HEADERS = {
    "Goals": True,
    "Bookings": True,
}


def is_enabled() -> bool:
    return bool(os.environ.get("FOOTBALL_DATA_API_TOKEN", "").strip())


def _normalize_team_key(name: str) -> str:
    text = unicodedata.normalize("NFKD", name)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().strip().split())


def canonical_team_name(name: str, our_teams: set[str]) -> str | None:
    if not name:
        return None
    if name in our_teams:
        return name
    alias = API_TEAM_ALIASES.get(_normalize_team_key(name))
    if alias and alias in our_teams:
        return alias
    norm = _normalize_team_key(name)
    for team in our_teams:
        if _normalize_team_key(team) == norm:
            return team
    return None


def _api_request(path: str, *, unfold: dict[str, bool] | None = None) -> dict | None:
    token = os.environ.get("FOOTBALL_DATA_API_TOKEN", "").strip()
    if not token:
        return None
    headers = {
        "X-Auth-Token": token,
        "User-Agent": "wc2026-predictions/1.0",
    }
    if unfold:
        for key, enabled in unfold.items():
            if enabled:
                headers[f"X-Unfold-{key}"] = "true"
    req = urllib.request.Request(f"{API_BASE}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        logger.warning("football-data.org HTTP %s: %s", exc.code, body)
        db.set_sync_meta("live_sync_error", f"HTTP {exc.code}")
        return None
    except Exception as exc:
        logger.warning("football-data.org request failed: %s", exc)
        db.set_sync_meta("live_sync_error", str(exc)[:200])
        return None


def _parse_api_kickoff_et(utc_date: str) -> datetime | None:
    if not utc_date:
        return None
    try:
        dt = datetime.fromisoformat(utc_date.replace("Z", "+00:00"))
        return dt.astimezone(TIMEZONE)
    except ValueError:
        return None


def _extract_score(api_match: dict) -> tuple[int | None, int | None]:
    score = api_match.get("score") or {}
    full = score.get("fullTime") or {}
    home = full.get("homeTeam")
    away = full.get("awayTeam")
    if home is None or away is None:
        return None, None
    return int(home), int(away)


def _injury_minute(goal_or_booking: dict) -> int | None:
    raw = goal_or_booking.get("injuryTime")
    if raw is None:
        raw = goal_or_booking.get("extraTime")
    return int(raw) if raw is not None else None


def _db_status(api_status: str) -> str:
    if api_status == "PAUSED":
        return "halftime"
    if api_status in LIVE_API_STATUSES:
        return "live"
    return "scheduled"


def _card_type(api_card: str) -> str | None:
    card = (api_card or "").upper()
    if "RED" in card:
        return "red"
    if "YELLOW" in card:
        return "yellow"
    return None


def _find_db_match(api_match: dict, db_matches: list[dict], our_teams: set[str]) -> dict | None:
    home_raw = (api_match.get("homeTeam") or {}).get("name") or ""
    away_raw = (api_match.get("awayTeam") or {}).get("name") or ""
    home = canonical_team_name(home_raw, our_teams)
    away = canonical_team_name(away_raw, our_teams)
    if not home or not away:
        return None

    kickoff_et = _parse_api_kickoff_et(api_match.get("utcDate", ""))
    api_date = kickoff_et.strftime("%Y-%m-%d") if kickoff_et else None

    candidates = [m for m in db_matches if m["home_team"] == home and m["away_team"] == away]
    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]
    if api_date:
        for m in candidates:
            if m["match_date"] == api_date:
                return m
    return candidates[0]


def _needs_penalty_detail(api_match: dict) -> bool:
    if api_match.get("penalties"):
        return False
    score = api_match.get("score") or {}
    pens = score.get("penalties") or {}
    return pens.get("homeTeam") is not None or pens.get("awayTeam") is not None


def _fetch_match_details(api_ids: list[int]) -> dict[int, dict]:
    if not api_ids:
        return {}
    ids = ",".join(str(i) for i in api_ids[:8])
    payload = _api_request(f"/matches?ids={ids}", unfold=UNFOLD_HEADERS)
    if not payload:
        return {}
    return {m["id"]: m for m in payload.get("matches") or [] if m.get("id")}


def _sync_goals(match_id: int, db_match: dict, api_match: dict, our_teams: set[str]) -> int:
    added = 0
    for goal in api_match.get("goals") or []:
        scorer = (goal.get("scorer") or {}).get("name")
        minute = goal.get("minute")
        if not scorer or minute is None:
            continue
        team_name = canonical_team_name((goal.get("team") or {}).get("name", ""), our_teams)
        if not team_name:
            continue
        if team_name == db_match["home_team"]:
            side = "home"
        elif team_name == db_match["away_team"]:
            side = "away"
        else:
            continue
        injury = _injury_minute(goal)
        is_pen = (goal.get("type") or "").upper() == "PENALTY"
        if db.import_match_goal(match_id, side, scorer, int(minute), injury, is_pen):
            added += 1
    return added


def _sync_bookings(match_id: int, api_match: dict, our_teams: set[str]) -> int:
    added = 0
    for booking in api_match.get("bookings") or []:
        player = (booking.get("player") or {}).get("name")
        minute = booking.get("minute")
        card = _card_type(booking.get("card", ""))
        team_name = canonical_team_name((booking.get("team") or {}).get("name", ""), our_teams)
        if not player or not card or not team_name:
            continue
        if db.import_player_card(match_id, player, team_name, card, int(minute) if minute is not None else None):
            added += 1
    return added


def _sync_penalties(match_id: int, db_match: dict, api_match: dict, our_teams: set[str]) -> int:
    added = 0
    for goal in api_match.get("goals") or []:
        if (goal.get("type") or "").upper() != "PENALTY":
            continue
        scorer = (goal.get("scorer") or {}).get("name")
        minute = goal.get("minute")
        team_name = canonical_team_name((goal.get("team") or {}).get("name", ""), our_teams)
        if not team_name or minute is None:
            continue
        injury = _injury_minute(goal)
        if db.import_match_penalty(match_id, team_name, "scored", int(minute), scorer, injury):
            added += 1

    for i, pen in enumerate(api_match.get("penalties") or []):
        player = (pen.get("player") or {}).get("name")
        team_name = canonical_team_name((pen.get("team") or {}).get("name", ""), our_teams)
        if not player or not team_name:
            continue
        outcome = "scored" if pen.get("scored") else "missed"
        minute = 120 + i + 1
        if db.import_match_penalty(match_id, team_name, outcome, minute, player):
            added += 1
    return added


def _process_api_match(
    api_match: dict,
    db_matches: list[dict],
    our_teams: set[str],
) -> dict:
    status = api_match.get("status") or "SCHEDULED"
    if status not in LIVE_API_STATUSES and status != FINISHED_API_STATUS:
        return {}

    db_match = _find_db_match(api_match, db_matches, our_teams)
    if not db_match:
        return {}

    match_id = db_match["id"]
    home_score, away_score = _extract_score(api_match)
    if home_score is None or away_score is None:
        return {"matched": 1}

    result = {
        "matched": 1,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "penalties_added": 0,
    }

    if status == FINISHED_API_STATUS:
        if db_match["actual_home"] is None:
            db.update_match_result(match_id, home_score, away_score)
            result["finished"] = 1
    elif db_match["actual_home"] is None:
        minute = api_match.get("minute")
        live_minute = int(minute) if minute is not None else 0
        db.update_match_live(match_id, home_score, away_score, live_minute, _db_status(status))
        result["updated_live"] = 1

    result["goals_added"] = _sync_goals(match_id, db_match, api_match, our_teams)
    result["cards_added"] = _sync_bookings(match_id, api_match, our_teams)
    result["penalties_added"] = _sync_penalties(match_id, db_match, api_match, our_teams)
    return result


def sync_live_scores(force: bool = False) -> dict:
    """Pull World Cup scores from football-data.org and update the database."""
    if not is_enabled():
        return {"ok": False, "skipped": True, "reason": "no_api_token"}

    if not force and not db.try_begin_live_sync(SYNC_COOLDOWN_SECONDS):
        return {"ok": True, "skipped": True, "reason": "cooldown"}

    payload = _api_request("/competitions/WC/matches?season=2026", unfold=UNFOLD_HEADERS)
    if payload is None:
        return {"ok": False, "error": "api_request_failed"}

    our_teams = set(db.get_distinct_teams())
    db_matches = [dict(m) for m in db.get_all_matches()]
    api_matches = list(payload.get("matches") or [])

    detail_ids = [
        m["id"]
        for m in api_matches
        if m.get("id") and _needs_penalty_detail(m)
    ]
    details = _fetch_match_details(detail_ids) if detail_ids else {}

    totals = {
        "matched": 0,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "penalties_added": 0,
    }

    for api_match in api_matches:
        enriched = details.get(api_match.get("id"), api_match)
        if enriched is not api_match:
            merged = dict(api_match)
            merged["goals"] = enriched.get("goals") or api_match.get("goals")
            merged["bookings"] = enriched.get("bookings") or api_match.get("bookings")
            merged["penalties"] = enriched.get("penalties") or api_match.get("penalties")
            api_match = merged

        row = _process_api_match(api_match, db_matches, our_teams)
        for key in totals:
            totals[key] += row.get(key, 0)

    knockout = db.sync_knockout_stage()

    summary = {
        "ok": True,
        **totals,
        "knockout": knockout,
        "synced_at": datetime.now(TIMEZONE).isoformat(),
    }
    db.set_sync_meta("live_sync_summary", json.dumps(summary))
    db.set_sync_meta("live_sync_error", "")
    return summary


def get_sync_status() -> dict:
    summary_raw = db.get_sync_meta("live_sync_summary")
    summary = json.loads(summary_raw) if summary_raw else None
    return {
        "enabled": is_enabled(),
        "interval_seconds": SYNC_COOLDOWN_SECONDS,
        "last_summary": summary,
        "last_error": db.get_sync_meta("live_sync_error") or None,
    }

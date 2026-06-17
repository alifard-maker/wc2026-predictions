"""Automatic live score sync from football-data.org (every ~10s)."""

from __future__ import annotations

import json
import logging
import os
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import db
from live_scores import (
    effective_live_minute,
    elapsed_wall_minutes,
    minute_from_kickoff,
    minute_from_second_half_start,
    normalize_stored_minute,
    FIRST_HALF_MINUTES,
)
from scoring import TIMEZONE, parse_match_datetime

MATCH_WINDOW = timedelta(minutes=105)
LIVE_SYNC_MAX = timedelta(hours=3)

logger = logging.getLogger(__name__)

API_BASE = "https://api.football-data.org/v4"
SYNC_COOLDOWN_SECONDS = int(os.environ.get("LIVE_SYNC_INTERVAL", "30"))
WC_COMPETITION = os.environ.get("FOOTBALL_DATA_COMPETITION", "WC").strip() or "WC"

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
    "iran": "Iran",
    "ir iran": "Iran",
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

LIVE_API_STATUSES = frozenset({
    "IN_PLAY",
    "LIVE",
    "PAUSED",
    "EXTRA_TIME",
    "PENALTY_SHOOTOUT",
})
SYNCABLE_STATUSES = LIVE_API_STATUSES | frozenset({"TIMED"})
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


def _score_part(part: dict | None) -> tuple[int | None, int | None]:
    """Read home/away from a score node (v4 uses home/away; v2 used homeTeam/awayTeam)."""
    if not part:
        return None, None
    home = part.get("home")
    away = part.get("away")
    if home is None:
        home = part.get("homeTeam")
    if away is None:
        away = part.get("awayTeam")
    if home is None or away is None:
        return None, None
    return int(home), int(away)


def _score_from_goals(api_match: dict, our_teams: set[str]) -> tuple[int | None, int | None]:
    goals = api_match.get("goals") or []
    if goals:
        home, away = _score_part(goals[-1].get("score"))
        if home is not None and away is not None:
            return home, away

    home_name = canonical_team_name((api_match.get("homeTeam") or {}).get("name", ""), our_teams)
    away_name = canonical_team_name((api_match.get("awayTeam") or {}).get("name", ""), our_teams)
    if not home_name or not away_name:
        return None, None

    home_goals = away_goals = 0
    for goal in goals:
        team_name = canonical_team_name((goal.get("team") or {}).get("name", ""), our_teams)
        if team_name == home_name:
            home_goals += 1
        elif team_name == away_name:
            away_goals += 1
    if goals:
        return home_goals, away_goals
    return None, None


def _extract_score(
    api_match: dict,
    our_teams: set[str],
    db_match: dict | None = None,
) -> tuple[int | None, int | None]:
    status = api_match.get("status") or ""
    score = api_match.get("score") or {}
    if status in {"PENALTY_SHOOTOUT", "EXTRA_TIME", "IN_PLAY", "LIVE", "PAUSED", "FINISHED"}:
        for key in ("extraTime", "regularTime", "fullTime"):
            home, away = _score_part(score.get(key))
            if home is not None and away is not None:
                return home, away
    for key in ("fullTime", "regularTime", "halfTime"):
        home, away = _score_part(score.get(key))
        if home is not None and away is not None:
            return home, away
    from_goals = _score_from_goals(api_match, our_teams)
    if from_goals[0] is not None and from_goals[1] is not None:
        return from_goals
    if db_match is not None:
        lh, la = db_match.get("live_home"), db_match.get("live_away")
        if lh is not None and la is not None:
            return int(lh), int(la)
    return None, None


def _kickoff_in_play_window(kickoff_et: datetime | None, db_match: dict | None = None) -> bool:
    if not kickoff_et:
        return False
    now = datetime.now(TIMEZONE)
    if db_match and db_match.get("actual_home") is None:
        if (db_match.get("status") or "") in ("live", "halftime", "hydration_break", "extra_time", "penalty_shootout"):
            return kickoff_et <= now < kickoff_et + LIVE_SYNC_MAX
        if db.get_sync_meta(f"espn_live_source_{db_match['id']}"):
            return kickoff_et <= now < kickoff_et + LIVE_SYNC_MAX
    return kickoff_et <= now < kickoff_et + MATCH_WINDOW


def _should_sync_match(api_match: dict) -> bool:
    status = api_match.get("status") or "SCHEDULED"
    if status == FINISHED_API_STATUS or status in LIVE_API_STATUSES:
        return True
    kickoff_et = _parse_api_kickoff_et(api_match.get("utcDate", ""))
    if _kickoff_in_play_window(kickoff_et):
        return True
    if status in SYNCABLE_STATUSES and (
        api_match.get("minute") is not None
        or api_match.get("goals")
        or api_match.get("bookings")
    ):
        return True
    return False


def _ingest_api_matches(payload: dict | None, by_id: dict[int, dict]) -> None:
    if not payload:
        return
    for match in payload.get("matches") or []:
        if match.get("id"):
            by_id[match["id"]] = match


def _collect_api_matches() -> list[dict]:
    """Fetch World Cup live and today's matches (goals/bookings unfolded)."""
    today = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    by_id: dict[int, dict] = {}
    comp = WC_COMPETITION

    _ingest_api_matches(
        _api_request(f"/competitions/{comp}/matches?status=LIVE", unfold=UNFOLD_HEADERS),
        by_id,
    )
    _ingest_api_matches(
        _api_request(
            f"/competitions/{comp}/matches?dateFrom={today}&dateTo={today}",
            unfold=UNFOLD_HEADERS,
        ),
        by_id,
    )

    if not by_id:
        _ingest_api_matches(
            _api_request("/matches?status=LIVE", unfold=UNFOLD_HEADERS),
            by_id,
        )
        _ingest_api_matches(
            _api_request(
                f"/matches?dateFrom={today}&dateTo={today}",
                unfold=UNFOLD_HEADERS,
            ),
            by_id,
        )

    return list(by_id.values())


def _match_kickoff_et(api_match: dict, db_match: dict) -> datetime | None:
    kickoff = _parse_api_kickoff_et(api_match.get("utcDate", ""))
    if kickoff:
        return kickoff
    return parse_match_datetime(db_match["match_date"], db_match["match_time"])


def _parse_goal_minute(goal: dict) -> tuple[int, int | None] | None:
    raw = goal.get("minute")
    if raw is None:
        return None
    minute = int(raw)
    if minute < 1:
        return None
    injury = _injury_minute(goal)
    return minute, injury


def _second_half_start(match_id: int) -> datetime | None:
    raw = db.get_sync_meta(f"second_half_start_{match_id}")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _espn_authoritative_for_cards(match_id: int, db_match: dict) -> bool:
    """Finished matches synced live from ESPN keep ESPN as the card source of truth."""
    if db_match.get("actual_home") is None:
        return False
    return bool(db.get_sync_meta(f"espn_live_source_{match_id}"))


def _espn_recently_synced(match_id: int) -> bool:
    return bool(db.get_sync_meta(f"espn_live_source_{match_id}"))


def _crosscheck_live_scores(
    db_match: dict,
    fd_home: int,
    fd_away: int,
) -> tuple[int, int, dict]:
    """Compare football-data.org scores with ESPN-synced DB state; correct on disagreement."""
    match_id = db_match["id"]
    espn_home = db_match.get("live_home")
    espn_away = db_match.get("live_away")
    meta = {
        "match_id": match_id,
        "home_team": db_match.get("home_team"),
        "away_team": db_match.get("away_team"),
        "football_data": [fd_home, fd_away],
    }
    if not _espn_recently_synced(match_id) or espn_home is None or espn_away is None:
        meta["result"] = "football_data_only"
        meta["espn"] = [espn_home, espn_away]
        return fd_home, fd_away, meta

    espn_home = int(espn_home)
    espn_away = int(espn_away)
    meta["espn"] = [espn_home, espn_away]
    if espn_home == fd_home and espn_away == fd_away:
        meta["result"] = "agreed"
        home, away = fd_home, fd_away
    else:
        meta["result"] = "corrected"
        meta["used"] = "football_data"
        db.set_sync_meta(
            f"score_crosscheck_{match_id}",
            json.dumps({**meta, "at": datetime.now(TIMEZONE).isoformat()}),
        )
        home, away = fd_home, fd_away

    from db import floor_live_score_from_goals

    home, away = floor_live_score_from_goals(match_id, home, away)
    if home != fd_home or away != fd_away:
        meta["goal_floor"] = [home, away]
    return home, away, meta


def _track_second_half_start(match_id: int, api_status: str) -> None:
    now = datetime.now(TIMEZONE)
    prev = db.get_sync_meta(f"api_status_{match_id}") or ""
    if prev == "PAUSED" and api_status == "IN_PLAY":
        db.set_sync_meta(f"second_half_start_{match_id}", now.isoformat())
    db.set_sync_meta(f"api_status_{match_id}", api_status)


def _resolve_live_clock(api_match: dict, db_match: dict) -> tuple[int | None, int | None]:
    """API minute when available; derive 2nd-half clock from restart if API freezes at 45."""
    raw = api_match.get("minute")
    kickoff = _match_kickoff_et(api_match, db_match)
    now = datetime.now(TIMEZONE)
    match_id = db_match["id"]
    stored = normalize_stored_minute(db_match.get("live_minute"))
    stored_injury = db_match.get("live_injury_minute")
    if stored_injury is not None:
        try:
            stored_injury = int(stored_injury) if int(stored_injury) > 0 else None
        except (TypeError, ValueError):
            stored_injury = None

    api_minute: int | None = None
    api_injury: int | None = None
    if raw is not None:
        parsed = int(raw)
        if parsed > 0:
            api_minute = parsed
            api_injury = _injury_minute(api_match)
            if api_injury is None and stored_injury and stored == parsed:
                api_injury = stored_injury

    best_minute = api_minute if api_minute is not None else stored
    second_half_start = _second_half_start(match_id)
    if kickoff:
        minute, injury = effective_live_minute(
            kickoff,
            now,
            best_minute,
            api_injury or stored_injury,
            second_half_start,
        )
        elapsed = elapsed_wall_minutes(kickoff, now)
        if (
            api_minute is not None
            and api_minute <= FIRST_HALF_MINUTES
            and elapsed > 60
        ):
            if second_half_start:
                minute = minute_from_second_half_start(second_half_start, now)
            elif stored and stored > FIRST_HALF_MINUTES:
                minute = stored
            else:
                minute = None
        return minute, injury
    return best_minute, api_injury or stored_injury


def _injury_minute(goal_or_booking: dict) -> int | None:
    raw = goal_or_booking.get("injuryTime")
    if raw is None:
        raw = goal_or_booking.get("extraTime")
    return int(raw) if raw is not None else None


def _db_status(api_status: str) -> str:
    if api_status == "PAUSED":
        return "halftime"
    if api_status == "EXTRA_TIME":
        return "extra_time"
    if api_status == "PENALTY_SHOOTOUT":
        return "penalty_shootout"
    if api_status in LIVE_API_STATUSES or api_status == "TIMED":
        return "live"
    return "scheduled"


def _store_shootout_score(match_id: int, api_match: dict) -> None:
    score = api_match.get("score") or {}
    pens = score.get("penalties") or {}
    home = pens.get("home")
    away = pens.get("away")
    if home is None:
        home = pens.get("homeTeam")
    if away is None:
        away = pens.get("awayTeam")
    if home is None or away is None:
        return
    db.set_sync_meta(
        f"shootout_score_{match_id}",
        json.dumps({"home": int(home), "away": int(away)}),
    )


def _freeze_regulation_score(match_id: int, home_score: int, away_score: int) -> tuple[int, int]:
    meta_key = f"regulation_score_{match_id}"
    raw = db.get_sync_meta(meta_key)
    if raw:
        try:
            home, away = raw.split(",", 1)
            return int(home), int(away)
        except (TypeError, ValueError):
            pass
    db.set_sync_meta(meta_key, f"{home_score},{away_score}")
    return home_score, away_score


PHASE_STATUSES = frozenset({"halftime", "hydration_break", "extra_time", "penalty_shootout"})


def _preserve_phase_status(
    match_id: int,
    db_match: dict,
    db_status: str,
    live_minute: int | None,
    live_injury: int | None,
) -> tuple[str, int | None, int | None]:
    """Keep ESPN phase (e.g. HT) when football-data still reports generic live at 45'."""
    prev = db_match.get("status") or ""
    espn_phase = db.get_sync_meta(f"espn_phase_{match_id}") or ""
    phase = prev if prev in PHASE_STATUSES else espn_phase
    if phase not in PHASE_STATUSES or db_status != "live":
        return db_status, live_minute, live_injury

    minute = normalize_stored_minute(live_minute)
    if minute is None:
        minute = normalize_stored_minute(db_match.get("live_minute"))
    if phase == "halftime" and (minute is None or minute <= 45):
        return "halftime", 45, None
    if phase in PHASE_STATUSES - {"halftime"}:
        return phase, db_match.get("live_minute"), db_match.get("live_injury_minute")
    return db_status, live_minute, live_injury


def _live_sync_cooldown(db_matches: list[dict]) -> int:
    base = SYNC_COOLDOWN_SECONDS
    shootout = 5
    extra_time = 10
    for m in db_matches:
        if m.get("actual_home") is not None:
            continue
        status = m.get("status") or ""
        if status == "penalty_shootout":
            return min(base, shootout)
        if status == "extra_time":
            base = min(base, extra_time)
    return base


def _card_type(api_card: str) -> str | None:
    card = (api_card or "").upper()
    if "RED" in card:
        return "red"
    if "YELLOW" in card:
        return "yellow"
    return None


def _db_kickoff_et(db_match: dict) -> datetime:
    return parse_match_datetime(db_match["match_date"], db_match["match_time"])


def _kickoffs_align(api_kickoff: datetime | None, db_match: dict, *, max_hours: int = 30) -> bool:
    if not api_kickoff:
        return True
    delta = abs((api_kickoff - _db_kickoff_et(db_match)).total_seconds())
    return delta <= max_hours * 3600


def _match_started(db_match: dict, now: datetime | None = None) -> bool:
    now = now or datetime.now(TIMEZONE)
    return now >= _db_kickoff_et(db_match)


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
    if api_date:
        for m in candidates:
            if m["match_date"] == api_date:
                return m
    return None


def _needs_penalty_detail(api_match: dict) -> bool:
    if api_match.get("penalties"):
        return False
    score = api_match.get("score") or {}
    pens = score.get("penalties") or {}
    return pens.get("homeTeam") is not None or pens.get("awayTeam") is not None


def _fetch_match_details(api_ids: list[int]) -> dict[int, dict]:
    if not api_ids:
        return {}
    details: dict[int, dict] = {}
    for i in range(0, len(api_ids), 8):
        batch = api_ids[i : i + 8]
        ids = ",".join(str(mid) for mid in batch)
        payload = _api_request(f"/matches?ids={ids}", unfold=UNFOLD_HEADERS)
        if not payload:
            continue
        for match in payload.get("matches") or []:
            if match.get("id"):
                details[match["id"]] = match

    for api_id in api_ids:
        if api_id in details:
            continue
        single = _api_request(f"/matches/{api_id}", unfold=UNFOLD_HEADERS)
        if single and single.get("id"):
            details[api_id] = single
    return details


def _richest_match(api_match: dict, details: dict[int, dict]) -> dict:
    """Prefer batch detail, then per-match fetch, for goals/bookings/minute."""
    api_id = api_match.get("id")
    if not api_id:
        return api_match
    enriched = details.get(api_id) or api_match
    if enriched is api_match or not enriched.get("bookings"):
        single = _api_request(f"/matches/{api_id}", unfold=UNFOLD_HEADERS)
        if single and single.get("id"):
            merged = dict(single)
            if not merged.get("goals") and enriched.get("goals"):
                merged["goals"] = enriched["goals"]
            if not merged.get("bookings") and enriched.get("bookings"):
                merged["bookings"] = enriched["bookings"]
            return merged
    return enriched


def _person_name(person: dict | None) -> str | None:
    if not person:
        return None
    for key in ("name", "shortName", "lastName"):
        value = person.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _goal_scorer_name(goal: dict) -> str:
    scorer = _person_name(goal.get("scorer"))
    if scorer:
        return scorer
    assist = _person_name(goal.get("assist"))
    if assist:
        return assist
    return "Unknown scorer"


def _sync_goals(match_id: int, db_match: dict, api_match: dict, our_teams: set[str]) -> int:
    added = 0
    expected: list[tuple[str, int, int | None]] = []
    for goal in api_match.get("goals") or []:
        parsed = _parse_goal_minute(goal)
        if parsed is None:
            continue
        minute, injury = parsed
        team_name = canonical_team_name((goal.get("team") or {}).get("name", ""), our_teams)
        if not team_name:
            continue
        if team_name == db_match["home_team"]:
            side = "home"
        elif team_name == db_match["away_team"]:
            side = "away"
        else:
            continue
        scorer = _goal_scorer_name(goal)
        is_pen = (goal.get("type") or "").upper() == "PENALTY"
        expected.append((side, minute, injury))
        if db.upsert_match_goal(match_id, side, scorer, minute, injury, is_pen):
            added += 1
    db.reconcile_synced_goals(match_id, expected)
    return added


def _booking_player_name(booking: dict) -> str | None:
    player = _person_name(booking.get("player"))
    if player:
        return player
    for key in ("playerName", "name"):
        value = booking.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return None


def _booking_team_name(
    booking: dict,
    api_match: dict,
    our_teams: set[str],
) -> str | None:
    team_name = canonical_team_name((booking.get("team") or {}).get("name", ""), our_teams)
    if team_name:
        return team_name
    team_id = (booking.get("team") or {}).get("id")
    if team_id:
        for side in ("homeTeam", "awayTeam"):
            side_team = api_match.get(side) or {}
            if side_team.get("id") == team_id:
                return canonical_team_name(side_team.get("name", ""), our_teams)
    return None


def _sync_bookings(
    match_id: int,
    api_match: dict,
    our_teams: set[str],
    *,
    espn_authoritative: bool = False,
) -> int:
    if espn_authoritative:
        return 0
    added = 0
    expected: list[tuple[str, str, str]] = []
    bookings = api_match.get("bookings") or []
    for booking in bookings:
        player = _booking_player_name(booking)
        card = _card_type(booking.get("card", ""))
        team_name = _booking_team_name(booking, api_match, our_teams)
        if not player or not card or not team_name:
            continue
        raw_minute = booking.get("minute")
        minute = None
        if raw_minute is not None:
            try:
                minute_val = int(raw_minute)
                if minute_val > 0:
                    minute = minute_val
            except (TypeError, ValueError):
                minute = None
        expected.append((player, team_name, card))
        if db.upsert_player_card(match_id, player, team_name, card, minute):
            added += 1
    db.reconcile_synced_cards(match_id, expected)
    return added


def _sync_penalties(match_id: int, db_match: dict, api_match: dict, our_teams: set[str]) -> int:
    api_status = (api_match.get("status") or "").upper()
    db_status = (db_match.get("status") or "").lower()
    if api_status != "PENALTY_SHOOTOUT" and db_status != "penalty_shootout":
        return 0

    added = 0
    existing = db.get_match_penalties(match_id)
    shootout_count = sum(1 for pen in existing if (pen.get("minute") or 0) > 120)
    seen: set[tuple[str, str, str]] = {
        (
            pen.get("taker_team") or "",
            pen.get("taker_name") or "",
            pen.get("outcome") or "",
        )
        for pen in existing
        if (pen.get("minute") or 0) > 120
    }

    for pen in api_match.get("penalties") or []:
        player = (pen.get("player") or {}).get("name")
        team_name = canonical_team_name((pen.get("team") or {}).get("name", ""), our_teams)
        if not player or not team_name:
            continue
        outcome = "scored" if pen.get("scored") else "missed"
        key = (team_name, player, outcome)
        if key in seen:
            continue
        minute = 120 + shootout_count + 1
        if db.import_match_penalty(match_id, team_name, outcome, minute, player):
            added += 1
            shootout_count += 1
            seen.add(key)
    return added


def _process_api_match(
    api_match: dict,
    db_matches: list[dict],
    our_teams: set[str],
) -> dict:
    status = api_match.get("status") or "SCHEDULED"
    if not _should_sync_match(api_match):
        return {}

    db_match = _find_db_match(api_match, db_matches, our_teams)
    if not db_match:
        return {}

    match_id = db_match["id"]
    kickoff = _match_kickoff_et(api_match, db_match)
    in_window = _kickoff_in_play_window(kickoff, db_match)
    home_score, away_score = _extract_score(api_match, our_teams, db_match)
    if home_score is None or away_score is None:
        if not in_window:
            return {
                "matched": 1,
                "api_minute": api_match.get("minute"),
            }
        home_score = int(db_match.get("live_home") or 0)
        away_score = int(db_match.get("live_away") or 0)

    result = {
        "matched": 1,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "penalties_added": 0,
        "api_minute": api_match.get("minute"),
    }

    if status == FINISHED_API_STATUS:
        final_home, final_away, check = _crosscheck_live_scores(db_match, home_score, away_score)
        result["crosscheck"] = check
        if (
            db_match["actual_home"] is None
            and _match_started(db_match)
            and _kickoffs_align(kickoff, db_match)
            and db.update_match_result(match_id, final_home, final_away)
        ):
            result["finished"] = 1
            db.set_sync_meta(f"regulation_score_{match_id}", "")
    elif in_window and db_match.get("actual_home") is None:
        _track_second_half_start(match_id, status)
        live_minute, live_injury = _resolve_live_clock(api_match, db_match)
        db_status = _db_status(status)
        if db_status == "penalty_shootout":
            home_score, away_score = _freeze_regulation_score(match_id, home_score, away_score)
            _store_shootout_score(match_id, api_match)
            check = {
                "match_id": match_id,
                "result": "skipped_shootout",
                "football_data": [home_score, away_score],
            }
        else:
            home_score, away_score, check = _crosscheck_live_scores(db_match, home_score, away_score)
        result["crosscheck"] = check
        if db_status == "extra_time" and live_minute is not None and live_minute <= 90:
            live_minute = max(live_minute, 91)
        if db_status == "halftime" and kickoff:
            from live_scores import is_halftime_break

            if not is_halftime_break(kickoff, datetime.now(TIMEZONE), db_status):
                db_status = "live"
        db_status, live_minute, live_injury = _preserve_phase_status(
            match_id, db_match, db_status, live_minute, live_injury
        )
        if live_minute is not None:
            db.update_match_live(
                match_id,
                home_score,
                away_score,
                live_minute,
                db_status,
                live_injury,
            )
            result["updated_live"] = 1
            result["stored_minute"] = live_minute

    result["goals_added"] = _sync_goals(match_id, db_match, api_match, our_teams)
    result["cards_added"] = _sync_bookings(
        match_id,
        api_match,
        our_teams,
        espn_authoritative=_espn_authoritative_for_cards(match_id, db_match),
    )
    result["api_bookings"] = len(api_match.get("bookings") or [])
    result["api_goals"] = len(api_match.get("goals") or [])
    result["penalties_added"] = _sync_penalties(match_id, db_match, api_match, our_teams)
    if db.reconcile_live_score_from_goals(match_id):
        result["score_reconciled"] = 1
    return result


def _run_espn_sync(
    db_matches: list[dict] | None = None,
    our_teams: set[str] | None = None,
) -> dict:
    try:
        import espn_live_sync

        return espn_live_sync.sync_from_espn(db_matches, our_teams)
    except Exception as exc:
        logger.warning("ESPN live sync failed: %s", exc)
        return {"ok": False, "error": str(exc)[:200]}


def reconcile_recorded_match_cards() -> dict:
    """Re-fetch ESPN for past match dates so rescinded cards (e.g. VAR) are dropped."""
    db.repair_rescinded_var_cards()
    dates = db.match_dates_with_synced_cards()
    if not dates:
        return {"ok": True, "dates": 0}

    our_teams = set(db.get_distinct_teams())
    db_matches = [dict(m) for m in db.get_all_matches()]
    result: dict = {"ok": True, "dates": len(dates)}

    try:
        import espn_live_sync

        result["espn"] = espn_live_sync.sync_historical_cards(db_matches, our_teams, dates)
    except Exception as exc:
        logger.warning("Historical ESPN card sync failed: %s", exc)
        result["espn_error"] = str(exc)[:200]

    return result


def sync_live_scores(force: bool = False) -> dict:
    """Pull live scores from ESPN + football-data.org and update the database."""
    our_teams = set(db.get_distinct_teams())
    db_matches = [dict(m) for m in db.get_all_matches()]
    espn = _run_espn_sync(db_matches, our_teams)
    db_matches = [dict(m) for m in db.get_all_matches()]

    if not is_enabled():
        return {"ok": True, "skipped": True, "reason": "no_api_token", "espn": espn}

    cooldown = _live_sync_cooldown(db_matches)
    if db.get_sync_meta("live_sync_error") == "HTTP 429":
        cooldown = max(cooldown, 120)
    if not force and not db.try_begin_live_sync(cooldown):
        return {"ok": True, "skipped": True, "reason": "cooldown", "espn": espn}

    api_matches = _collect_api_matches()
    if not api_matches:
        return {"ok": False, "error": "api_request_failed", "espn": espn}

    detail_ids = {
        m["id"]
        for m in api_matches
        if m.get("id") and (_should_sync_match(m) or _needs_penalty_detail(m))
    }
    details = _fetch_match_details(list(detail_ids)) if detail_ids else {}

    totals = {
        "api_matches": len(api_matches),
        "api_syncable": sum(1 for m in api_matches if _should_sync_match(m)),
        "matched": 0,
        "updated_live": 0,
        "finished": 0,
        "goals_added": 0,
        "cards_added": 0,
        "penalties_added": 0,
        "api_goals_seen": 0,
        "api_bookings_seen": 0,
        "api_minute": None,
        "stored_minute": None,
        "crosscheck_agreed": 0,
        "crosscheck_corrected": 0,
        "crosscheck_football_data_only": 0,
    }
    crosscheck_rows: list[dict] = []

    for api_match in api_matches:
        api_match = _richest_match(api_match, details)

        db_match = _find_db_match(api_match, db_matches, our_teams)
        row = _process_api_match(api_match, db_matches, our_teams)
        check = row.get("crosscheck")
        if check:
            crosscheck_rows.append(check)
            result_key = check.get("result")
            if result_key == "agreed":
                totals["crosscheck_agreed"] += 1
            elif result_key == "corrected":
                totals["crosscheck_corrected"] += 1
            elif result_key == "football_data_only":
                totals["crosscheck_football_data_only"] += 1
        for key in totals:
            totals[key] += row.get(key, 0)

    for key in ("matched", "updated_live", "finished", "goals_added", "cards_added"):
        totals[key] += espn.get(key, 0)
    totals["espn"] = espn

    knockout = db.sync_knockout_stage()
    card_reconcile = reconcile_recorded_match_cards()
    shootout_repair = db.repair_bogus_shootout_penalties()
    goals_reconciled = db.reconcile_all_live_scores_from_goals()

    disagreements = [c for c in crosscheck_rows if c.get("result") == "corrected"]
    summary = {
        "ok": True,
        **totals,
        "crosschecks": crosscheck_rows[-8:],
        "crosscheck_disagreements": disagreements[-5:],
        "knockout": knockout,
        "card_reconcile": card_reconcile,
        "shootout_repair_removed": shootout_repair,
        "goals_reconciled": goals_reconciled,
        "synced_at": datetime.now(TIMEZONE).isoformat(),
        "cooldown_seconds": cooldown,
        "fast_poll": any(
            (m.get("status") or "") == "penalty_shootout" and m.get("actual_home") is None
            for m in db_matches
        ),
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

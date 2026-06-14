"""Live match statistics (possession, shots, passes, etc.) from ESPN summary."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

import db
from espn_live_sync import _fetch_summary, find_espn_event_id
from scoring import TIMEZONE

STATS_CACHE = timedelta(seconds=30)

STAT_ROWS: list[dict] = [
    {"key": "possessionPct", "label": "Ball possession", "kind": "possession"},
    {"key": "totalShots", "label": "Shots"},
    {"key": "shotsOnTarget", "label": "Shots on target"},
    {"key": "blockedShots", "label": "Blocked shots"},
    {
        "key": "totalPasses",
        "label": "Passes",
        "sub_key": "accuratePasses",
        "sub_label": "accurate",
    },
    {"key": "passPct", "label": "Pass accuracy", "kind": "pct"},
    {"key": "wonCorners", "label": "Corner kicks"},
    {"key": "foulsCommitted", "label": "Fouls"},
    {"key": "offsides", "label": "Offsides"},
    {"key": "saves", "label": "Saves"},
    {
        "key": "totalTackles",
        "label": "Tackles",
        "sub_key": "effectiveTackles",
        "sub_label": "won",
    },
    {"key": "interceptions", "label": "Interceptions"},
]


def _stat_map(team_stats: list | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for stat in team_stats or []:
        name = stat.get("name")
        if name:
            out[name] = str(stat.get("displayValue") or "")
    return out


def _format_pct(value: str | None) -> str:
    if not value:
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return value
    if number <= 1:
        return f"{round(number * 100)}%"
    return f"{round(number)}%"


def _format_value(
    value: str | None,
    *,
    kind: str | None = None,
    sub_value: str | None = None,
    sub_label: str | None = None,
) -> str:
    if not value:
        return "—"
    if kind == "pct":
        return _format_pct(value)
    if kind == "possession":
        try:
            return f"{round(float(value))}%"
        except (TypeError, ValueError):
            return value
    if sub_value and sub_label:
        return f"{value} ({sub_value} {sub_label})"
    return value


def parse_boxscore_stats(summary: dict) -> tuple[dict[str, str], dict[str, str]] | None:
    teams = (summary.get("boxscore") or {}).get("teams") or []
    if len(teams) < 2:
        return None

    home_map: dict[str, str] | None = None
    away_map: dict[str, str] | None = None
    for team in teams:
        side = (team.get("homeAway") or "").lower()
        stats = _stat_map(team.get("statistics"))
        if side == "home":
            home_map = stats
        elif side == "away":
            away_map = stats

    if not home_map or not away_map:
        return None
    return home_map, away_map


def build_stat_rows(home_map: dict[str, str], away_map: dict[str, str]) -> list[dict]:
    rows: list[dict] = []
    for spec in STAT_ROWS:
        key = spec["key"]
        sub_key = spec.get("sub_key")
        kind = spec.get("kind")
        row = {
            "label": spec["label"],
            "kind": kind or "count",
            "home": _format_value(
                home_map.get(key),
                kind=kind,
                sub_value=home_map.get(sub_key) if sub_key else None,
                sub_label=spec.get("sub_label"),
            ),
            "away": _format_value(
                away_map.get(key),
                kind=kind,
                sub_value=away_map.get(sub_key) if sub_key else None,
                sub_label=spec.get("sub_label"),
            ),
        }
        if kind == "possession":
            try:
                row["home_pct"] = float(home_map.get(key) or 0)
                row["away_pct"] = float(away_map.get(key) or 0)
            except (TypeError, ValueError):
                row["home_pct"] = 50.0
                row["away_pct"] = 50.0
        rows.append(row)
    return rows


def get_match_game_stats(match: dict) -> dict:
    """Fetch ESPN boxscore stats for a match."""
    match_id = match["id"]
    cache_key = f"game_stats_{match_id}"
    cached_raw = db.get_sync_meta(cache_key)
    if cached_raw:
        try:
            cached = json.loads(cached_raw)
            synced_at = datetime.fromisoformat(cached["synced_at"])
            if datetime.now(TIMEZONE) - synced_at < STATS_CACHE:
                return cached["payload"]
        except (TypeError, ValueError, json.JSONDecodeError, KeyError):
            pass

    payload = _load_match_game_stats(match)
    db.set_sync_meta(
        cache_key,
        json.dumps(
            {
                "synced_at": datetime.now(TIMEZONE).isoformat(),
                "payload": payload,
            }
        ),
    )
    return payload


def _load_match_game_stats(match: dict) -> dict:
    """Fetch ESPN boxscore stats for a match."""
    home_team = match["home_team"]
    away_team = match["away_team"]
    result: dict = {
        "available": False,
        "home_team": home_team,
        "away_team": away_team,
        "rows": [],
        "message": None,
    }

    if not match.get("is_live") and not match.get("is_finished"):
        result["message"] = "Stats appear once the match kicks off."
        return result

    event_id = find_espn_event_id(dict(match))
    if not event_id:
        result["message"] = "Stats not available yet."
        return result

    summary = _fetch_summary(event_id)
    if not summary:
        result["message"] = "Could not load stats right now."
        return result

    parsed = parse_boxscore_stats(summary)
    if not parsed:
        result["message"] = "Stats not available yet."
        return result

    home_map, away_map = parsed
    result["rows"] = build_stat_rows(home_map, away_map)
    result["available"] = bool(result["rows"])
    return result

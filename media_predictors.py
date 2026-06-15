"""Media pundit predictions — static picks from published sources (e.g. BBC Sport)."""

from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

MEDIA_PREDICTORS: list[dict] = [
    {
        "key": "chris_sutton",
        "display_name": "Chris Sutton — BBC Sport",
        "badge": "BBC",
        "avatar": "images/media/bbc-sport.svg",
        "data_file": "chris_sutton_wc2026.json",
    },
]

MEDIA_AGENT_KEYS: set[str] = {p["key"] for p in MEDIA_PREDICTORS}
MEDIA_AGENT_NAMES: set[str] = {p["display_name"] for p in MEDIA_PREDICTORS}

# BBC wording → official FIFA team names used in fixtures.
TEAM_ALIASES: dict[str, str] = {
    "South Korea": "Korea Republic",
    "Czech Republic": "Czechia",
    "Bosnia-Herzegovina": "Bosnia and Herzegovina",
    "Cape Verde": "Cabo Verde",
    "DR Congo": "Congo DR",
    "Curacao": "Curaçao",
    "Ivory Coast": "Côte d'Ivoire",
    "Turkey": "Türkiye",
}


def normalize_team(name: str) -> str:
    return TEAM_ALIASES.get(name, name)


def match_pair_key(home: str, away: str) -> tuple[str, str]:
    return (normalize_team(home), normalize_team(away))


def get_media_predictor(agent_key: str) -> dict | None:
    for predictor in MEDIA_PREDICTORS:
        if predictor["key"] == agent_key:
            return predictor
    return None


def is_media_agent(display_name: str | None = None, ai_agent_key: str | None = None) -> bool:
    if ai_agent_key and ai_agent_key in MEDIA_AGENT_KEYS:
        return True
    return bool(display_name and display_name in MEDIA_AGENT_NAMES)


def infer_media_agent_key(display_name: str | None = None) -> str | None:
    if not display_name:
        return None
    for predictor in MEDIA_PREDICTORS:
        if predictor["display_name"] == display_name:
            return predictor["key"]
    return None


def _load_predictor_data(agent_key: str) -> dict | None:
    predictor = get_media_predictor(agent_key)
    if not predictor:
        return None
    path = DATA_DIR / predictor["data_file"]
    if not path.is_file():
        return None
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def get_media_match_predictions(agent_key: str) -> dict[tuple[str, str], tuple[int, int]]:
    """Map (home, away) team names to (home_score, away_score)."""
    data = _load_predictor_data(agent_key)
    if not data:
        return {}
    out: dict[tuple[str, str], tuple[int, int]] = {}
    for row in data.get("match_predictions", []):
        key = match_pair_key(row["home"], row["away"])
        out[key] = (int(row["home_score"]), int(row["away_score"]))
    return out


def get_media_tournament_picks(agent_key: str) -> dict[str, str] | None:
    data = _load_predictor_data(agent_key)
    if not data:
        return None
    picks = data.get("tournament")
    if not picks:
        return None
    required = ("top_scorer", "winner", "second_place", "third_place")
    if not all(picks.get(k) for k in required):
        return None
    return {k: str(picks[k]).strip() for k in required}

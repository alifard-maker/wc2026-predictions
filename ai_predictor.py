"""AI prediction agents — each pool gets several automated players."""

from __future__ import annotations

import hashlib

from team_data import TEAM_FACTS

AI_DISPLAY_NAME = "Cursor AI Prediction"  # backwards compatibility
CURSOR_LEGACY_DISPLAY_NAMES: frozenset[str] = frozenset({
    "Cursor AI Prediction",
    "Cursor AI Predictions",
})

AI_AGENTS: list[dict] = [
    {"key": "cursor", "display_name": "Cursor AI", "badge": "Cursor", "avatar": "images/ai-agents/cursor.svg"},
    {"key": "chatgpt", "display_name": "ChatGPT", "badge": "GPT", "avatar": "images/ai-agents/chatgpt.svg"},
    {"key": "gemini", "display_name": "Gemini", "badge": "Gemini", "avatar": "images/ai-agents/gemini.svg"},
    {"key": "grok", "display_name": "Grok", "badge": "Grok", "avatar": "images/ai-agents/grok.svg"},
    {"key": "claude", "display_name": "Claude", "badge": "Claude", "avatar": "images/ai-agents/claude.svg"},
]

AI_AGENT_NAMES: set[str] = {a["display_name"] for a in AI_AGENTS}
AI_AGENT_KEYS: set[str] = {a["key"] for a in AI_AGENTS}
# Sync disabled for this agent — legacy pool member replaced by Nostradamus.
REMOVED_SYNC_AGENTS: frozenset[str] = frozenset({"cursor"})
# Ex–Cursor AI Predictions (renamed by admin). Separate from synced Cursor AI.
LEGACY_PREDICTIONS_AGENT_KEY = "cursor_predictions"
LEGACY_AI_AGENT_KEYS: frozenset[str] = frozenset({LEGACY_PREDICTIONS_AGENT_KEY})
RENAMED_LEGACY_AI_NAMES: frozenset[str] = frozenset({"Nostradamus"})

# Bump when predict_score logic changes — triggers refresh of open AI picks on deploy.
AI_PREDICTOR_VERSION = 2

AGENT_DRAW_BIAS = {
    "cursor": 0.35,
    "chatgpt": 0.28,
    "gemini": 0.22,
    "grok": 0.18,
    "claude": 0.32,
}

AGENT_UPSET_BIAS = {
    "cursor": 0.0,
    "chatgpt": 0.06,
    "gemini": 0.10,
    "grok": 0.14,
    "claude": 0.05,
}

# Score pools by strength gap (0 = even match, higher = bigger favourite).
_SCORE_POOLS: list[tuple[float, dict[str, list[tuple[int, int]]]]] = [
    (
        0.12,
        {
            "home": [(1, 0), (2, 1), (1, 0), (2, 0), (2, 1), (1, 0)],
            "away": [(0, 1), (1, 2), (0, 1), (0, 2), (1, 2), (0, 1)],
            "draw": [(1, 1), (0, 0), (2, 2), (1, 1), (0, 0)],
        },
    ),
    (
        0.22,
        {
            "home": [(2, 1), (1, 0), (2, 0), (2, 1), (1, 0), (2, 1)],
            "away": [(1, 2), (0, 1), (0, 2), (1, 2), (0, 1), (1, 2)],
            "draw": [(1, 1), (0, 0), (1, 1)],
        },
    ),
    (
        0.35,
        {
            "home": [(2, 0), (2, 1), (1, 0), (3, 1), (2, 1), (2, 0)],
            "away": [(0, 2), (1, 2), (0, 1), (1, 3), (1, 2), (0, 2)],
            "draw": [(1, 1), (0, 0)],
        },
    ),
    (
        1.0,
        {
            "home": [(2, 0), (3, 0), (3, 1), (2, 0), (2, 1), (3, 0)],
            "away": [(0, 2), (0, 3), (1, 3), (0, 2), (1, 2), (0, 3)],
            "draw": [(1, 1)],
        },
    ),
]


def _team_strength(team: str) -> float:
    fact = TEAM_FACTS.get(team, {})
    rank = fact.get("ranking", 50)
    try:
        return max(1.0, 120.0 - float(rank))
    except (TypeError, ValueError):
        return 50.0


def _seed(agent_key: str, match_id: int, home: str, away: str) -> int:
    raw = f"{agent_key}:{match_id}:{home}:{away}".encode()
    return int(hashlib.md5(raw).hexdigest()[:8], 16)


def _score_pool_for_gap(gap: float) -> dict[str, list[tuple[int, int]]]:
    for threshold, pools in _SCORE_POOLS:
        if gap <= threshold:
            return pools
    return _SCORE_POOLS[-1][1]


def predict_score(home: str, away: str, match_id: int, agent_key: str = "cursor") -> tuple[int, int]:
    """Deterministic AI prediction with realistic score variety."""
    home_s = _team_strength(home)
    away_s = _team_strength(away)
    seed = _seed(agent_key, match_id, home, away)

    closeness = min(home_s, away_s) / max(home_s, away_s)
    gap = 1.0 - closeness
    home_edge = home_s / (home_s + away_s)
    home_edge = min(0.90, max(0.10, home_edge + 0.04))  # slight home advantage

    draw_bias = AGENT_DRAW_BIAS.get(agent_key, 0.25)
    upset_chance = AGENT_UPSET_BIAS.get(agent_key, 0.0) * closeness
    if seed % 100 < int(upset_chance * 100):
        home_edge = 1.0 - home_edge

    draw_threshold = int(draw_bias * closeness * 340)
    if closeness < 0.82:
        draw_threshold = int(draw_threshold * (0.55 + closeness * 0.35))

    roll = seed % 1000
    home_threshold = draw_threshold + int((1000 - draw_threshold) * home_edge)

    if roll < draw_threshold:
        outcome = "draw"
    elif roll < home_threshold:
        outcome = "home"
    else:
        outcome = "away"

    pool = _score_pool_for_gap(gap)[outcome]
    return pool[(seed // 7 + match_id) % len(pool)]


TOP_SCORER_PICKS = [
    "Kylian Mbappé",
    "Lionel Messi",
    "Erling Haaland",
    "Harry Kane",
    "Vinícius Júnior",
    "Lamine Yamal",
    "Mohamed Salah",
    "Cristiano Ronaldo",
]


def predict_tournament_picks(pool_id: int, agent_key: str = "cursor") -> dict[str, str]:
    from teams import get_all_teams

    teams = sorted(get_all_teams(), key=lambda t: -_team_strength(t))
    seed = _seed(agent_key, pool_id, "tournament", "picks")

    contenders = teams[:12]
    winner = contenders[seed % len(contenders)]
    rest = [t for t in contenders if t != winner]
    second = rest[(seed + 3) % len(rest)]
    rest2 = [t for t in rest if t != second]
    third = rest2[(seed + 5) % len(rest2)]
    top_scorer = TOP_SCORER_PICKS[(seed + ord(agent_key[0])) % len(TOP_SCORER_PICKS)]

    return {
        "top_scorer": top_scorer,
        "winner": winner,
        "second_place": second,
        "third_place": third,
    }


def infer_ai_agent_key(display_name: str | None = None) -> str | None:
    from media_predictors import infer_media_agent_key

    if not display_name:
        return None
    if display_name in RENAMED_LEGACY_AI_NAMES or display_name == "Cursor AI Predictions":
        return LEGACY_PREDICTIONS_AGENT_KEY
    if display_name in CURSOR_LEGACY_DISPLAY_NAMES:
        return LEGACY_PREDICTIONS_AGENT_KEY
    media_key = infer_media_agent_key(display_name)
    if media_key:
        return media_key
    for agent in AI_AGENTS:
        if agent["display_name"] == display_name:
            return agent["key"]
    return None


def is_synced_ai_agent(display_name: str | None = None, ai_agent_key: str | None = None) -> bool:
    """True for pool members that receive automated pick sync."""
    from media_predictors import is_media_agent

    if is_media_agent(display_name, ai_agent_key):
        return False
    key = ai_agent_key or infer_ai_agent_key(display_name)
    return bool(key and key in AI_AGENT_KEYS and key not in REMOVED_SYNC_AGENTS)


def _agent_profile(display_name: str | None = None, ai_agent_key: str | None = None) -> dict | None:
    from media_predictors import MEDIA_PREDICTORS

    if ai_agent_key:
        for agent in MEDIA_PREDICTORS:
            if agent["key"] == ai_agent_key:
                return agent
        for agent in AI_AGENTS:
            if agent["key"] == ai_agent_key:
                return agent
    if display_name:
        for agent in MEDIA_PREDICTORS:
            if agent["display_name"] == display_name:
                return agent
        for agent in AI_AGENTS:
            if agent["display_name"] == display_name:
                return agent
        if display_name in CURSOR_LEGACY_DISPLAY_NAMES:
            return {"badge": "AI", "avatar": None}
    if display_name in RENAMED_LEGACY_AI_NAMES:
        return {"badge": "AI", "avatar": None}
    return None


def is_ai_agent(display_name: str | None = None, ai_agent_key: str | None = None) -> bool:
    if ai_agent_key and ai_agent_key in LEGACY_AI_AGENT_KEYS:
        return True
    if ai_agent_key and ai_agent_key in AI_AGENT_KEYS:
        return True
    if display_name in CURSOR_LEGACY_DISPLAY_NAMES:
        return True
    if display_name in RENAMED_LEGACY_AI_NAMES:
        return True
    if display_name in AI_AGENT_NAMES or display_name == AI_DISPLAY_NAME:
        return True
    return False


def is_agent_badge(display_name: str | None = None, ai_agent_key: str | None = None) -> bool:
    """True for AI and media pundits that show a source badge in the UI."""
    from media_predictors import is_media_agent

    return is_ai_agent(display_name, ai_agent_key) or is_media_agent(display_name, ai_agent_key)


def ai_agent_badge(display_name: str | None = None, ai_agent_key: str | None = None) -> str:
    agent = _agent_profile(display_name, ai_agent_key)
    return agent["badge"] if agent else "AI"


def ai_agent_avatar_file(display_name: str | None = None, ai_agent_key: str | None = None) -> str | None:
    """Static image path under /static for this AI agent, if any."""
    agent = _agent_profile(display_name, ai_agent_key)
    return agent.get("avatar") if agent else None

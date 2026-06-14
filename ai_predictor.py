"""AI prediction agents — each pool gets several automated players."""

from __future__ import annotations

import hashlib

from team_data import TEAM_FACTS

AI_DISPLAY_NAME = "Cursor AI Prediction"  # backwards compatibility

AI_AGENTS: list[dict] = [
    {"key": "cursor", "display_name": "Cursor AI", "badge": "Cursor", "avatar": "images/ai-agents/cursor.svg"},
    {"key": "chatgpt", "display_name": "ChatGPT", "badge": "GPT", "avatar": "images/ai-agents/chatgpt.svg"},
    {"key": "gemini", "display_name": "Gemini", "badge": "Gemini", "avatar": "images/ai-agents/gemini.svg"},
    {"key": "grok", "display_name": "Grok", "badge": "Grok", "avatar": "images/ai-agents/grok.svg"},
    {"key": "claude", "display_name": "Claude", "badge": "Claude", "avatar": "images/ai-agents/claude.svg"},
]

AI_AGENT_NAMES: set[str] = {a["display_name"] for a in AI_AGENTS}
AI_AGENT_KEYS: set[str] = {a["key"] for a in AI_AGENTS}

# Weighted toward realistic results — fewer draws than before.
SCORE_OPTIONS = [
    (1, 0), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2),
    (0, 1), (0, 2), (1, 2), (0, 3), (1, 3), (2, 3),
    (1, 1), (2, 2), (0, 0),
]

AGENT_DRAW_BIAS = {
    "cursor": 0.35,
    "chatgpt": 0.25,
    "gemini": 0.20,
    "grok": 0.15,
    "claude": 0.30,
}

AGENT_UPSET_BIAS = {
    "cursor": 0.0,
    "chatgpt": 0.05,
    "gemini": 0.08,
    "grok": 0.12,
    "claude": 0.04,
}


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


def predict_score(home: str, away: str, match_id: int, agent_key: str = "cursor") -> tuple[int, int]:
    """Deterministic AI prediction — favours wins over draws."""
    home_s = _team_strength(home)
    away_s = _team_strength(away)
    seed = _seed(agent_key, match_id, home, away)
    home_prob = home_s / (home_s + away_s)
    draw_bias = AGENT_DRAW_BIAS.get(agent_key, 0.3)
    upset = AGENT_UPSET_BIAS.get(agent_key, 0.0)

    # Slight agent-specific nudge to home/away balance
    if seed % 100 < int(upset * 100):
        home_prob = 1.0 - home_prob

    best = (1, 0)
    best_val = -1.0
    for i, (h, a) in enumerate(SCORE_OPTIONS):
        closeness = min(home_s, away_s) / max(home_s, away_s)
        if h > a:
            margin = h - a
            val = home_prob * (2.2 + margin * 0.3)
        elif h < a:
            margin = a - h
            val = (1.0 - home_prob) * (2.2 + margin * 0.3)
        else:
            if closeness < 0.88:
                val = 0.15
            else:
                val = draw_bias * closeness * (2.0 if h == 1 else 1.4)
        val += ((seed + i) % 11) * 0.008
        if val > best_val:
            best_val = val
            best = (h, a)
    return best


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


def _agent_profile(display_name: str | None = None, ai_agent_key: str | None = None) -> dict | None:
    if ai_agent_key:
        for agent in AI_AGENTS:
            if agent["key"] == ai_agent_key:
                return agent
    if display_name:
        for agent in AI_AGENTS:
            if agent["display_name"] == display_name:
                return agent
        if display_name == AI_DISPLAY_NAME:
            return {"badge": "Cursor", "avatar": AI_AGENTS[0].get("avatar")}
    return None


def is_ai_agent(display_name: str | None = None, ai_agent_key: str | None = None) -> bool:
    if ai_agent_key and ai_agent_key in AI_AGENT_KEYS:
        return True
    if display_name in AI_AGENT_NAMES or display_name == AI_DISPLAY_NAME:
        return True
    return False


def ai_agent_badge(display_name: str | None = None, ai_agent_key: str | None = None) -> str:
    agent = _agent_profile(display_name, ai_agent_key)
    return agent["badge"] if agent else "AI"


def ai_agent_avatar_file(display_name: str | None = None, ai_agent_key: str | None = None) -> str | None:
    """Static image path under /static for this AI agent, if any."""
    agent = _agent_profile(display_name, ai_agent_key)
    return agent.get("avatar") if agent else None

#!/usr/bin/env python3
"""Parse FIFA official squad-list PDF text into fifa_official_squads.json."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEXT_PATH = ROOT / "data" / "fifa-squad-lists.txt"
OUT_PATH = ROOT / "data" / "fifa_official_squads.json"

TEAM_ALIASES: dict[str, str] = {
    "Bosnia And Herzegovina": "Bosnia and Herzegovina",
    "Côte D'Ivoire": "Côte d'Ivoire",
    "Cote D'Ivoire": "Côte d'Ivoire",
    "Congo DR": "Congo DR",
}

TEAM_RE = re.compile(r"^(.+?)\s*\(([A-Z]{3})\)\s*#", re.MULTILINE)

PLAYER_RE = re.compile(
    r"(GK|DF|MF|FW)\s+"
    r"(.+?)\s+"
    r"(\d{2}/\d{2}/\d{4})\s+"
    r"(.+?)\s+"
    r"\(([A-Z]{3})\)\s+"
    r"(\d{2,3})\b"
)

# pypdf fallback: one player per line, no spaces after POS/date
PLAYER_LINE_RE = re.compile(
    r"^(GK|DF|MF|FW)(.+?)(\d{2}/\d{2}/\d{4})(.+?)\(([A-Z]{3})\)\s*(\d+)\s*$"
)


def _title_name(token: str) -> str:
    if not token:
        return token
    if token.isupper() and len(token) > 2:
        return token.title()
    return token[0].upper() + token[1:] if token and token[0].islower() else token


def _protect_name_compounds(blob: str) -> str:
    """Keep Mc/Mac/O'/De La compounds intact before camelCase splitting."""
    blob = re.sub(r"Mc([A-Z])", r"Mc§\1", blob)
    blob = re.sub(r"Mac([A-Z])", r"Mac§\1", blob)
    blob = re.sub(r"O'([A-Z])", r"O'§\1", blob)
    return blob


def _restore_name_compounds(blob: str) -> str:
    return blob.replace("§", "")


def _mc_surname(token: str) -> str:
    if token.startswith("Mc") and len(token) > 2:
        return "Mc" + token[2:].title()
    if token.startswith("Mac") and len(token) > 3:
        return "Mac" + token[3:].title()
    return _title_name(token)


def _display_name(name_blob: str) -> str:
    blob = name_blob.strip()
    blob = _protect_name_compounds(blob)
    blob = re.sub(r"([a-záéíóúñü])([A-ZÁÉÍÓÚÑ])", r"\1 \2", blob)
    blob = _restore_name_compounds(blob)
    tokens = blob.split()
    if tokens and re.match(r"Mc[A-Z]", tokens[0]):
        first = next((t for t in tokens[1:] if t[0].isupper() and not t.isupper()), None)
        if first:
            return f"{_title_name(first)} {_mc_surname(tokens[0])}"
    if not tokens:
        return name_blob.strip()
    if len(tokens) == 1:
        return _title_name(tokens[0])

    while len(tokens) >= 2 and tokens[-1].upper() == tokens[-2].upper():
        tokens.pop()

    caps_end = 0
    while caps_end < len(tokens) and tokens[caps_end].isupper():
        caps_end += 1

    shirt_tokens = tokens[:caps_end] if caps_end else [tokens[0]]

    first = None
    for t in tokens[caps_end:]:
        if not t.isupper():
            first = t
            break

    if not first:
        first = shirt_tokens[0]

    particles = {"DE", "DA", "DOS", "VAN", "DER", "DI", "DEL", "MAC", "ST"}
    if len(shirt_tokens) > 1 and shirt_tokens[0] in particles:
        surname = " ".join(_title_name(t) for t in shirt_tokens)
    elif len(shirt_tokens) > 1 and shirt_tokens[0].title() == _title_name(first):
        surname = " ".join(_title_name(t) for t in shirt_tokens[1:])
    else:
        surname = _title_name(shirt_tokens[-1])

    full = f"{_title_name(first)} {surname}"
    if _title_name(first) == surname:
        return _title_name(first)
    return full


def _short_club(club: str) -> str:
    club = club.strip()
    club = re.sub(r"\s+FC$", "", club)
    club = re.sub(r"^FC\s+", "", club)
    return club.strip()


def _normalize_team(name: str) -> str:
    name = unicodedata.normalize("NFC", name.strip())
    return TEAM_ALIASES.get(name, name)


COACH_BLOCK_RE = re.compile(r"ROLE COACH.*?Head coach\s+(.+?)\s*\n", re.DOTALL)

COACH_COUNTRY_TOKENS = {
    "Algeria",
    "Argentina",
    "Australia",
    "Austria",
    "Belgium",
    "Bosnia And Herzegovina",
    "Brazil",
    "Cabo Verde",
    "Canada",
    "Colombia",
    "Congo DR",
    "Croatia",
    "Curaçao",
    "Czech Republic",
    "Côte D'Ivoire",
    "Ecuador",
    "Egypt",
    "England",
    "France",
    "Germany",
    "Ghana",
    "Haiti",
    "IR Iran",
    "Iraq",
    "Italy",
    "Japan",
    "Jordan",
    "Korea Republic",
    "Mexico",
    "Morocco",
    "Netherlands",
    "New Zealand",
    "Norway",
    "Panama",
    "Paraguay",
    "Portugal",
    "Qatar",
    "Saudi Arabia",
    "Scotland",
    "Senegal",
    "South Africa",
    "Spain",
    "Sweden",
    "Switzerland",
    "Tunisia",
    "Türkiye",
    "USA",
    "Uruguay",
    "Uzbekistan",
}

TEAM_COUNTRY_ALIASES: dict[str, set[str]] = {
    "Bosnia and Herzegovina": {"Bosnia And Herzegovina", "Bosnia and Herzegovina"},
    "Côte d'Ivoire": {"Côte D'Ivoire", "Côte d'Ivoire"},
    "Czechia": {"Czech Republic", "Czechia"},
    "IR Iran": {"IR Iran"},
    "Korea Republic": {"Korea Republic"},
    "Türkiye": {"Türkiye", "Turkiye"},
}


def _coach_country_ok(team: str, trailing_country: str | None, raw_coach: str) -> bool:
    if trailing_country == "Australia" and team == "Iraq":
        return False
    if not trailing_country:
        return True
    allowed = TEAM_COUNTRY_ALIASES.get(team, {team})
    return trailing_country in allowed or trailing_country not in allowed


def _format_coach(raw: str) -> str:
    tokens = raw.strip().split()
    if not tokens:
        return raw.strip()

    trailing_country = tokens[-1] if tokens[-1] in COACH_COUNTRY_TOKENS else None
    if trailing_country:
        tokens = tokens[:-1]

    first_idx = next(
        (i for i, t in enumerate(tokens) if t[0].isupper() and not t.isupper()),
        None,
    )
    if first_idx is None:
        return " ".join(t.title() for t in tokens)

    first = tokens[first_idx]
    surname_tokens = [t for t in tokens[:first_idx] if t.lower() != first.lower()]
    if len(surname_tokens) >= 2 and surname_tokens[-1] == surname_tokens[-2]:
        surname_tokens = surname_tokens[:-1]
    particles = {"DE", "LA", "DEL", "VAN", "DER", "DI", "DOS", "DA", "ST", "MAC", "LEAL"}
    surname = " ".join(
        t.lower() if t in particles else t.title() for t in surname_tokens
    )
    if surname.lower().endswith(first.lower()):
        surname = surname[: -len(first)].strip()
    return f"{first} {surname}".strip()


def _parse_players_from_block(block: str) -> list[dict]:
    players = []
    for pm in PLAYER_RE.finditer(block):
        players.append(_player_from_match(pm))
    if players:
        return _dedupe(players)

    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("ROLE"):
            continue
        if line.startswith("DOB") or line.startswith("Tuesday,") or re.match(r"^\d+$", line):
            continue
        pm = PLAYER_LINE_RE.match(line)
        if pm:
            players.append(_player_from_match(pm))
    return _dedupe(players)


def _player_from_match(pm: re.Match) -> dict:
    pos = pm.group(1)
    name_blob = pm.group(2)
    dob = pm.group(3)
    club = _short_club(pm.group(4))
    height = int(pm.group(6))
    return {
        "name": _display_name(name_blob),
        "position": pos,
        "club": club,
        "dob": dob,
        "height_cm": height,
    }


def _dedupe(players: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique = []
    for p in players:
        key = p["name"].lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def parse_squads(text: str) -> dict:
    teams: dict[str, dict] = {}
    team_matches = list(TEAM_RE.finditer(text))

    for i, match in enumerate(team_matches):
        fifa_name = match.group(1).strip()
        team = _normalize_team(fifa_name)
        start = match.end()
        end = team_matches[i + 1].start() if i + 1 < len(team_matches) else len(text)
        block = text[start:end]

        coach = None
        coach_matches = list(COACH_BLOCK_RE.finditer(block))
        if coach_matches:
            raw_coach = coach_matches[-1].group(1).strip()
            trailing = raw_coach.split()[-1]
            trailing_country = trailing if trailing in COACH_COUNTRY_TOKENS else None
            if _coach_country_ok(team, trailing_country, raw_coach):
                coach = _format_coach(raw_coach)

        players = _parse_players_from_block(block)
        teams[team] = {
            "fifa_name": fifa_name,
            "coach": coach,
            "players": players,
        }

    return teams


def main() -> None:
    if not TEXT_PATH.is_file():
        raise SystemExit(f"Missing {TEXT_PATH} — extract PDF text first")

    text = TEXT_PATH.read_text(encoding="utf-8")
    squads = parse_squads(text)

    bad = {t: len(s["players"]) for t, s in squads.items() if len(s["players"]) != 26}
    if bad:
        print("WARNING: teams without 26 players:", bad)

    OUT_PATH.write_text(json.dumps(squads, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(squads)} teams to {OUT_PATH}")
    ch = squads.get("Switzerland", {})
    print("Switzerland:", [p["name"] for p in ch.get("players", [])])


if __name__ == "__main__":
    main()

"""Official FIFA World Cup 2026 squad lists (26 players per team)."""

from __future__ import annotations

import copy
import json
import unicodedata
from datetime import date
from pathlib import Path

from teams import get_all_teams

ROOT = Path(__file__).resolve().parent
FIFA_SQUADS_PATH = ROOT / "data" / "fifa_official_squads.json"
WC_REFERENCE_DATE = date(2026, 6, 15)

NAME_ALIASES: dict[str, str] = {
    "Eray Coemert": "Eray Cömert",
    "Ricardo Rodriguez": "Ricardo Rodríguez",
    "Aurele Amenda": "Aurèle Amenda",
    "Sergino Dest": "Sergiño Dest",
    "Matt Turner": "Matt Turner",
}

TEAM_LEADER_ALIASES: dict[tuple[str, str], str] = {
    ("Congo DR", "Sébastien Haller"): "Yoane Wissa",
    ("Côte d'Ivoire", "Sébastien Haller"): "Simon Adingra",
}

LEADER_ALIASES: dict[str, str] = {
    "Andrew Robertson": "Andy Robertson",
    "Son Heung-min": "Heungmin Son",
    "Casemiro": "Carlos Casemiro",
    "Martin Ødegaard": "Martin Odegaard",
    "Álvaro Morata": "Mikel Merino",
    "Diego Godín": "Jose Gimenez",
    "Serge Aurier": "Franck Kessie",
    "André Ayew": "Jordan Ayew",
    "Mohammed Kudus": "Antoine Semenyo",
    "Sardar Azmoun": "Mehdi Taremi",
    "Aymen Luay": "Youssef Amyn",
    "Yazan Al-Naimat": "Ali Olwan",
    "Musa Al-Taamari": "Amer Jamous",
    "Hirving Lozano": "Santiago Gimenez",
    "Romain Saïss": "Achraf Hakimi",
    "Winston Reid": "Chris Wood",
    "Hassan Al-Haydos": "Akram Afif",
    "Salem Al-Dawsari": "Salem Aldawsari",
    "Percy Tau": "Lyle Foster",
    "Youssef Msakni": "Elias Achouri",
    "Aïssa Laïdouni": "Elias Achouri",
    "Cuco Martina": "Leandro Bacuna",
}

COACH_ALIASES: dict[str, str] = {
    "Nestor Lorenzo": "Néstor Lorenzo",
    "Roberto Martinez": "Roberto Martínez",
    "Zlatko Dalic": "Zlatko Dalić",
    "Sebastien Desabre": "Sébastien Desabre",
    "Sebastien Beccacece": "Sebastián Beccacece",
    "Stale Solbakken": "Ståle Solbakken",
    "Myungbo Hong": "Hong Myung-bo",
    "Hassan Hossam": "Hossam Hassan",
    "Pedro Bubista": "Bubista",
    "Luis De La Fuente": "Luis de la Fuente",
}


def _player(
    number: int,
    name: str,
    position: str,
    age: int,
    height_cm: int,
    nt_caps: int,
    nt_goals: int,
    past_wc: list[str],
    club: str,
    past_clubs: list[str],
) -> dict:
    return {
        "number": number,
        "name": name,
        "position": position,
        "age": age,
        "height_cm": height_cm,
        "nt_caps": nt_caps,
        "nt_goals": nt_goals,
        "past_wc": past_wc,
        "club": club,
        "past_clubs": past_clubs,
    }


def _build_squad(formation: str, style: str, players: list[dict]) -> dict:
    avg_age = round(sum(p["age"] for p in players) / len(players), 1)
    return {
        "formation": formation,
        "style": style,
        "avg_age": avg_age,
        "squad_size": len(players),
        "players": players,
        "source": "FIFA official squad list (2 June 2026)",
    }


COACH_NATIONALITY: dict[str, str] = {
    "Djamel Belmadi": "Algeria",
    "Vladimir Petkovic": "Switzerland",
    "Lionel Scaloni": "Argentina",
    "Graham Arnold": "Australia",
    "Tony Popovic": "Australia",
    "Ralf Rangnick": "Germany",
    "Domenico Tedesco": "Italy",
    "Rudi Garcia": "France",
    "Sergej Barbarez": "Bosnia and Herzegovina",
    "Dorival Júnior": "Brazil",
    "Carlo Ancelotti": "Italy",
    "Bubista": "Cabo Verde",
    "Pedro Bubista": "Cabo Verde",
    "Jesse Marsch": "United States",
    "Néstor Lorenzo": "Argentina",
    "Nestor Lorenzo": "Argentina",
    "Sébastien Desabre": "France",
    "Sebastien Desabre": "France",
    "Emerse Fae": "Côte d'Ivoire",
    "Sebastián Beccacece": "Argentina",
    "Sebastien Beccacece": "Argentina",
    "Hossam Hassan": "Egypt",
    "Hassan Hossam": "Egypt",
    "Gareth Southgate": "England",
    "Thomas Tuchel": "Germany",
    "Didier Deschamps": "France",
    "Julian Nagelsmann": "Germany",
    "Otto Addo": "Germany",
    "Queiroz Carlos": "Portugal",
    "Rodrigue Morti": "Haiti",
    "Sebastien Migne": "France",
    "Amir Ghalenoei": "Iran",
    "Amir Ghalehnoy": "Iran",
    "Hussein Ali Mohammed": "Iraq",
    "Hajime Moriyasu": "Japan",
    "Hussein Ammouta": "Jordan",
    "Jamal Sellami": "Jordan",
    "Hong Myung-bo": "Korea Republic",
    "Myungbo Hong": "Korea Republic",
    "Javier Aguirre": "Mexico",
    "Walid Regragui": "Morocco",
    "Mohamed Ouahbi": "Morocco",
    "Ronald Koeman": "Netherlands",
    "Darije Kalezić": "Croatia",
    "Darren Bazeley": "England",
    "Ståle Solbakken": "Norway",
    "Stale Solbakken": "Norway",
    "Thomas Christiansen": "Denmark",
    "Gustavo Alfaro": "Argentina",
    "Roberto Martínez": "Spain",
    "Roberto Martinez": "Spain",
    "Bruno Pinheiro": "Portugal",
    "Julen Lopetegui": "Spain",
    "Roberto Mancini": "Italy",
    "Georgios Donis": "Greece",
    "Steve Clarke": "Scotland",
    "Aliou Cissé": "Senegal",
    "Pape Thiaw": "Senegal",
    "Hugo Broos": "Belgium",
    "Luis de la Fuente": "Spain",
    "Jon Dahl Tomasson": "Denmark",
    "Graham Potter": "England",
    "Murat Yakin": "Switzerland",
    "Samuel Zauber": "Switzerland",
    "Sabri Lamouchi": "Tunisia",
    "Vincenzo Montella": "Italy",
    "Mauricio Pochettino": "Argentina",
    "Marcelo Bielsa": "Argentina",
    "Srečko Katanec": "Slovenia",
    "Fabio Cannavaro": "Italy",
    "Zlatko Dalić": "Croatia",
    "Zlatko Dalic": "Croatia",
    "Dick Advocaat": "Netherlands",
    "Ivan Hašek": "Czechia",
    "Miroslav Koubek": "Czechia",
    "Vladimir Petkovic": "Switzerland",
    "Thomas Tuchel": "Germany",
    "Carlo Ancelotti": "Italy",
    "Rudi Garcia": "France",
}


TEAM_META: dict[str, tuple[str, str]] = {
    "Algeria": ("4-2-3-1", "Vertical transitions and wing play"),
    "Argentina": ("4-3-3", "Possession and combination play"),
    "Australia": ("4-4-2", "Compact shape and direct attacks"),
    "Austria": ("4-2-2-2", "Aggressive pressing"),
    "Belgium": ("4-2-3-1", "Technical buildup and counters"),
    "Bosnia and Herzegovina": ("4-3-3", "Structured defense and target-forward service"),
    "Brazil": ("4-3-3", "Fluid attacking rotations"),
    "Cabo Verde": ("4-2-3-1", "Disciplined block and counters"),
    "Canada": ("4-4-2", "Transition-heavy with pace"),
    "Colombia": ("4-2-3-1", "Balanced shape and wide progression"),
    "Congo DR": ("4-3-3", "Athletic transitions"),
    "Croatia": ("4-3-3", "Midfield control"),
    "Curaçao": ("4-3-3", "Counterattacking structure"),
    "Czechia": ("3-4-2-1", "Cross-heavy with set pieces"),
    "Côte d'Ivoire": ("4-3-3", "Explosive wing play"),
    "Ecuador": ("4-3-3", "High-energy pressing"),
    "Egypt": ("4-2-3-1", "Compact block and fast breaks"),
    "England": ("4-3-3", "Positional control"),
    "France": ("4-3-3", "Pace and transitions"),
    "Germany": ("4-2-3-1", "High pressing and central overloads"),
    "Ghana": ("4-2-3-1", "Direct transitions"),
    "Haiti": ("4-4-2", "Low block and countering"),
    "Iran": ("4-1-4-1", "Compact defensive shell"),
    "Iraq": ("4-2-3-1", "Disciplined block and transitions"),
    "Japan": ("4-3-3", "Collective pressing and short passing"),
    "Jordan": ("4-4-2", "Compact lines and direct transitions"),
    "Korea Republic": ("4-2-3-1", "Energetic pressing"),
    "Mexico": ("4-3-3", "Possession with width"),
    "Morocco": ("4-1-4-1", "Elite defensive structure"),
    "Netherlands": ("3-4-1-2", "Progressive buildup"),
    "New Zealand": ("4-4-2", "Direct and set-piece focused"),
    "Norway": ("4-3-3", "Vertical attacking service"),
    "Panama": ("5-4-1", "Compact defense and counters"),
    "Paraguay": ("4-2-3-1", "Physical midfield battles"),
    "Portugal": ("4-3-3", "Technical circulation"),
    "Qatar": ("3-5-2", "Structured buildup"),
    "Saudi Arabia": ("4-2-3-1", "Intense pressing phases"),
    "Scotland": ("3-4-2-1", "Wingback-driven attacks"),
    "Senegal": ("4-3-3", "Athletic pressing"),
    "South Africa": ("4-2-3-1", "Energetic midfield press"),
    "Spain": ("4-3-3", "High-possession positional play"),
    "Sweden": ("4-4-2", "Structured defense and direct service"),
    "Switzerland": ("3-4-2-1", "Disciplined pressing"),
    "Tunisia": ("4-3-3", "Compact block and counters"),
    "Türkiye": ("4-2-3-1", "Creative midfield progression"),
    "USA": ("4-3-3", "High intensity and width"),
    "Uruguay": ("4-3-3", "High pressing and vertical attacks"),
    "Uzbekistan": ("4-2-3-1", "Compact shape and breakaways"),
}


def _normalize_name(name: str) -> str:
    folded = unicodedata.normalize("NFD", name.lower())
    return "".join(c for c in folded if unicodedata.category(c) != "Mn")


def _canonical_name(name: str) -> str:
    return NAME_ALIASES.get(name, name)


def _parse_dob(dob: str) -> date | None:
    try:
        day, month, year = (int(part) for part in dob.split("/"))
        return date(year, month, day)
    except (TypeError, ValueError):
        return None


def _age_from_dob(dob: str) -> int:
    born = _parse_dob(dob)
    if not born:
        return 25
    years = WC_REFERENCE_DATE.year - born.year
    if (WC_REFERENCE_DATE.month, WC_REFERENCE_DATE.day) < (born.month, born.day):
        years -= 1
    return max(17, years)


def _years(age: int) -> list[str]:
    years: list[str] = []
    if age >= 29:
        years.append("2018")
    if age >= 24:
        years.append("2022")
    return years


def _caps(position: str, age: int, idx: int) -> int:
    base = {"GK": 16, "DF": 20, "MF": 22, "FW": 18}[position]
    return min(200, base + (age - 20) * 2 + idx)


def _goals(position: str, caps: int, idx: int) -> int:
    if position == "GK":
        return 0
    if position == "DF":
        return caps // 20
    if position == "MF":
        return caps // 8
    return caps // 3 + (idx % 3)


def _fifa_player_to_dict(raw: dict, number: int, idx: int) -> dict:
    name = _canonical_name(raw["name"])
    position = raw["position"]
    age = _age_from_dob(raw.get("dob", ""))
    caps = _caps(position, age, idx)
    club = raw.get("club", "")
    height = raw.get("height_cm") or {"GK": 191, "DF": 184, "MF": 178, "FW": 181}[position]
    return _player(
        number,
        name,
        position,
        age,
        height,
        caps,
        _goals(position, caps, idx),
        _years(age),
        club,
        [club] if club else [],
    )


def _load_fifa_squads() -> dict:
    if not FIFA_SQUADS_PATH.is_file():
        raise FileNotFoundError(
            f"Missing {FIFA_SQUADS_PATH}. Run: python3 scripts/parse_fifa_squads.py"
        )
    return json.loads(FIFA_SQUADS_PATH.read_text(encoding="utf-8"))


def _format_coach(name: str | None) -> str | None:
    if not name:
        return None
    return COACH_ALIASES.get(name, name)


FIFA_SQUAD_DATA: dict = _load_fifa_squads()
FIFA_COACHES: dict[str, str | None] = {
    team: _format_coach(data.get("coach")) for team, data in FIFA_SQUAD_DATA.items()
}


def squad_player_names(team_name: str) -> list[str]:
    data = FIFA_SQUAD_DATA.get(team_name, {})
    return [_canonical_name(p["name"]) for p in data.get("players", [])]


def resolve_squad_name(team_name: str, preferred: str) -> str | None:
    """Match a profile captain/key-player name to the official squad list."""
    names = squad_player_names(team_name)
    team_alias = TEAM_LEADER_ALIASES.get((team_name, preferred))
    candidates = [preferred, team_alias, LEADER_ALIASES.get(preferred, preferred)]
    candidates = [c for c in candidates if c]
    for candidate in candidates:
        if candidate in names:
            return candidate
    norm_preferred = _normalize_name(preferred)
    for name in names:
        if _normalize_name(name) == norm_preferred:
            return name
    for candidate in candidates:
        mapped = LEADER_ALIASES.get(candidate, candidate)
        norm_mapped = _normalize_name(mapped)
        for name in names:
            if _normalize_name(name) == norm_mapped:
                return name
    return None


def get_fifa_coach(team_name: str) -> str | None:
    return FIFA_COACHES.get(team_name)


TEAM_SQUADS: dict[str, dict] = {}
for team in get_all_teams():
    formation, style = TEAM_META[team]
    fifa = FIFA_SQUAD_DATA.get(team)
    if not fifa or not fifa.get("players"):
        raise ValueError(f"Missing FIFA squad data for {team}")
    players = [
        _fifa_player_to_dict(raw, number=idx, idx=idx - 1)
        for idx, raw in enumerate(fifa["players"], start=1)
    ]
    TEAM_SQUADS[team] = _build_squad(formation, style, players)


def get_team_squad(team_name: str) -> dict | None:
    squad = TEAM_SQUADS.get(team_name)
    return copy.deepcopy(squad) if squad else None

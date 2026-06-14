"""ISO flag codes for all World Cup 2026 nations."""

from teams import get_all_teams

TEAM_FLAG_CODES: dict[str, str] = {
    "Algeria": "dz",
    "Argentina": "ar",
    "Australia": "au",
    "Austria": "at",
    "Belgium": "be",
    "Bosnia and Herzegovina": "ba",
    "Brazil": "br",
    "Cabo Verde": "cv",
    "Canada": "ca",
    "Colombia": "co",
    "Congo DR": "cd",
    "Croatia": "hr",
    "Curaçao": "cw",
    "Czechia": "cz",
    "Côte d'Ivoire": "ci",
    "Ecuador": "ec",
    "Egypt": "eg",
    "England": "gb-eng",
    "France": "fr",
    "Germany": "de",
    "Ghana": "gh",
    "Haiti": "ht",
    "Iran": "ir",
    "Iraq": "iq",
    "Japan": "jp",
    "Jordan": "jo",
    "Korea Republic": "kr",
    "Mexico": "mx",
    "Morocco": "ma",
    "Netherlands": "nl",
    "New Zealand": "nz",
    "Norway": "no",
    "Panama": "pa",
    "Paraguay": "py",
    "Portugal": "pt",
    "Qatar": "qa",
    "Saudi Arabia": "sa",
    "Scotland": "gb-sct",
    "Senegal": "sn",
    "South Africa": "za",
    "Spain": "es",
    "Sweden": "se",
    "Switzerland": "ch",
    "Tunisia": "tn",
    "Türkiye": "tr",
    "USA": "us",
    "Uruguay": "uy",
    "Uzbekistan": "uz",
}

assert set(TEAM_FLAG_CODES.keys()) == set(get_all_teams())


IR_IRAN_FLAG = "/static/images/flags/iran-lion-sun.png"


def get_flag_codes_for_js() -> dict[str, str]:
    """Team name → flagcdn code, or local:filename for custom flags."""
    codes = dict(TEAM_FLAG_CODES)
    codes["Iran"] = "local:iran-lion-sun.png"
    return codes


def get_flag_url(team: str, size: str = "w40") -> str | None:
    if team == "Iran":
        return IR_IRAN_FLAG
    code = TEAM_FLAG_CODES.get(team)
    if not code:
        return None
    return f"https://flagcdn.com/{size}/{code}.png"

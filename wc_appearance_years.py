"""FIFA World Cup finals appearances by year (through 2026).

Year lists follow FIFA successor-nation rules (e.g. Germany incl. West Germany,
Czechia incl. Czechoslovakia). Sources: FIFA / Wikipedia appearance matrix.
"""

from __future__ import annotations

# Every team in WC 2026 — complete list of finals years attended (incl. 2026).
WC_APPEARANCE_YEARS: dict[str, list[int]] = {
    "Algeria": [1982, 1986, 2010, 2014, 2026],
    "Argentina": [
        1930, 1934, 1958, 1962, 1966, 1974, 1978, 1982, 1986, 1990,
        1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026,
    ],
    "Australia": [1974, 2006, 2010, 2014, 2018, 2022, 2026],
    "Austria": [1934, 1954, 1958, 1978, 1982, 1990, 1998, 2026],
    "Belgium": [
        1930, 1934, 1938, 1954, 1970, 1982, 1986, 1990, 1994, 1998,
        2002, 2014, 2018, 2022, 2026,
    ],
    "Bosnia and Herzegovina": [2014, 2026],
    "Brazil": [
        1930, 1934, 1938, 1950, 1954, 1958, 1962, 1966, 1970, 1974,
        1978, 1982, 1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014,
        2018, 2022, 2026,
    ],
    "Cabo Verde": [2026],
    "Canada": [1986, 2022, 2026],
    "Colombia": [1962, 1990, 1994, 1998, 2014, 2018, 2026],
    "Congo DR": [1974, 2026],
    "Croatia": [1998, 2002, 2006, 2014, 2018, 2022, 2026],
    "Curaçao": [2026],
    "Czechia": [1934, 1938, 1954, 1958, 1962, 1970, 1982, 1990, 2006, 2026],
    "Côte d'Ivoire": [2006, 2010, 2014, 2026],
    "Ecuador": [2002, 2006, 2014, 2022, 2026],
    "Egypt": [1934, 1990, 2018, 2026],
    "England": [
        1950, 1954, 1958, 1962, 1966, 1970, 1982, 1986, 1990, 1998,
        2002, 2006, 2010, 2014, 2018, 2022, 2026,
    ],
    "France": [
        1930, 1934, 1938, 1954, 1958, 1966, 1978, 1982, 1986, 1998,
        2002, 2006, 2010, 2014, 2018, 2022, 2026,
    ],
    "Germany": [
        1934, 1938, 1954, 1958, 1962, 1966, 1970, 1974, 1978, 1982,
        1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018, 2022,
        2026,
    ],
    "Ghana": [2006, 2010, 2014, 2022, 2026],
    "Haiti": [1974, 2026],
    "Iran": [1978, 1998, 2006, 2014, 2018, 2022, 2026],
    "Iraq": [1986, 2026],
    "Japan": [1998, 2002, 2006, 2010, 2014, 2018, 2022, 2026],
    "Jordan": [2026],
    "Korea Republic": [
        1954, 1986, 1990, 1994, 1998, 2002, 2006, 2010, 2014, 2018,
        2022, 2026,
    ],
    "Mexico": [
        1930, 1950, 1954, 1958, 1962, 1966, 1970, 1978, 1986, 1998,
        2002, 2006, 2010, 2014, 2018, 2022, 2026,
    ],
    "Morocco": [1970, 1986, 1994, 1998, 2018, 2022, 2026],
    "Netherlands": [
        1934, 1938, 1974, 1978, 1990, 1994, 1998, 2006, 2010, 2014,
        2022, 2026,
    ],
    "New Zealand": [1982, 2010, 2026],
    "Norway": [1938, 1994, 1998, 2026],
    "Panama": [2018, 2026],
    "Paraguay": [1930, 1950, 1986, 1998, 2002, 2006, 2010, 2022, 2026],
    "Portugal": [1966, 1986, 2002, 2006, 2010, 2014, 2018, 2022, 2026],
    "Qatar": [2022, 2026],
    "Saudi Arabia": [1994, 1998, 2002, 2006, 2018, 2022, 2026],
    "Scotland": [1954, 1958, 1974, 1978, 1982, 1986, 1990, 1998, 2026],
    "Senegal": [2002, 2018, 2022, 2026],
    "South Africa": [1998, 2002, 2010, 2026],
    "Spain": [
        1934, 1950, 1962, 1966, 1978, 1982, 1986, 1990, 1994, 1998,
        2002, 2006, 2010, 2014, 2018, 2022, 2026,
    ],
    "Sweden": [
        1934, 1938, 1950, 1958, 1970, 1974, 1978, 1990, 1994, 2002,
        2006, 2018, 2026,
    ],
    "Switzerland": [
        1934, 1938, 1950, 1954, 1962, 1966, 1994, 2006, 2010, 2014,
        2018, 2022, 2026,
    ],
    "Tunisia": [1978, 1998, 2002, 2006, 2018, 2022, 2026],
    "Türkiye": [1954, 2002, 2026],
    "USA": [
        1930, 1934, 1950, 1990, 1994, 1998, 2002, 2006, 2010, 2014,
        2022, 2026,
    ],
    "Uruguay": [
        1930, 1950, 1954, 1962, 1966, 1970, 1974, 1986, 1990, 2002,
        2010, 2014, 2018, 2022, 2026,
    ],
    "Uzbekistan": [2026],
}

# Notable finishes — shown separately from the year list.
WC_APPEARANCE_HIGHLIGHTS: dict[str, list[str]] = {
    "Algeria": ["Round of 16 (2014)"],
    "Argentina": [
        "Runners-up (1930, 1990, 2014)",
        "Champions (1978, 1986, 2022)",
    ],
    "Australia": ["Round of 16 (2006, 2022)"],
    "Austria": ["Third place (1954)", "Fourth place (1934)"],
    "Belgium": ["Third place (2018)", "Fourth place (1986)"],
    "Brazil": ["Champions (1958, 1962, 1970, 1994, 2002)", "Fourth place (2014)"],
    "Canada": ["Co-host 2026"],
    "Colombia": ["Quarter-finals (2014)"],
    "Croatia": ["Runners-up (2018)", "Third place (1998, 2022)"],
    "Czechia": ["Runners-up (1934, 1962 as Czechoslovakia)"],
    "England": ["Champions (1966)", "Fourth place (1990, 2018)"],
    "France": ["Champions (1998, 2018)", "Runners-up (2006, 2022)"],
    "Germany": ["Champions (1954, 1974, 1990, 2014)", "Third place (2010)"],
    "Ghana": ["Quarter-finals (2010)"],
    "Japan": ["Round of 16 (2002, 2010, 2018, 2022)"],
    "Korea Republic": ["Fourth place (2002)"],
    "Mexico": ["Quarter-finals (1970, 1986 as host)", "Co-host 2026"],
    "Morocco": ["Fourth place (2022)"],
    "Netherlands": ["Runners-up (1974, 1978, 2010)", "Third place (2014)"],
    "Paraguay": ["Quarter-finals (2010)"],
    "Portugal": ["Third place (1966)", "Fourth place (2006)"],
    "Qatar": ["Hosts (2022)"],
    "Saudi Arabia": ["Round of 16 (1994)"],
    "Senegal": ["Quarter-finals (2002)"],
    "Spain": ["Champions (2010)", "Fourth place (1950)"],
    "Sweden": ["Runners-up (1958)", "Third place (1950, 1994)"],
    "Switzerland": ["Quarter-finals (1934, 1938, 1954, 2014, 2018)"],
    "Türkiye": ["Third place (2002)"],
    "USA": ["Third place (1930)", "Quarter-finals (2002)", "Co-host 2026"],
    "Uruguay": ["Champions (1930, 1950)", "Fourth place (1954, 1970, 2010)"],
}


def get_wc_appearance_years(team_name: str) -> list[int]:
    return list(WC_APPEARANCE_YEARS.get(team_name, []))


def get_wc_appearance_highlights(team_name: str) -> list[str]:
    return list(WC_APPEARANCE_HIGHLIGHTS.get(team_name, []))


def format_wc_years(years: list[int]) -> str:
    """Comma-separated years for display."""
    return ", ".join(str(y) for y in years)

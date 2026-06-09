"""Team facts, head-to-head history, and match context for fixtures."""

from __future__ import annotations

# FIFA ranking (approx. early 2026) + major honours
TEAM_FACTS: dict[str, dict] = {
    "Algeria": {"ranking": 32, "honour": "AFCON champions 2019 & 1990"},
    "Argentina": {"ranking": 1, "honour": "World Cup champions 2022 & 1978"},
    "Australia": {"ranking": 24, "honour": "AFC Asian Cup runners-up 2011"},
    "Austria": {"ranking": 22, "honour": "Reached WC semi-finals 1954"},
    "Belgium": {"ranking": 8, "honour": "WC third place 2018"},
    "Bosnia and Herzegovina": {"ranking": 75, "honour": "First WC appearance 2014"},
    "Brazil": {"ranking": 5, "honour": "World Cup champions 5 times (1958–2002)"},
    "Cabo Verde": {"ranking": 65, "honour": "First ever World Cup in 2026"},
    "Canada": {"ranking": 41, "honour": "Co-host; first WC since 1986"},
    "Colombia": {"ranking": 14, "honour": "Copa América semi-finalists 2021"},
    "Congo DR": {"ranking": 67, "honour": "AFCON champions 1968 & 1974"},
    "Croatia": {"ranking": 10, "honour": "World Cup runners-up 2018; bronze 2022"},
    "Curaçao": {"ranking": 88, "honour": "First ever World Cup in 2026"},
    "Czechia": {"ranking": 38, "honour": "Euro champions 1976 (as Czechoslovakia)"},
    "Côte d'Ivoire": {"ranking": 36, "honour": "AFCON champions 2023 & 2015"},
    "Ecuador": {"ranking": 29, "honour": "Reached WC round of 16 in 2006"},
    "Egypt": {"ranking": 34, "honour": "AFCON champions 7 times"},
    "England": {"ranking": 4, "honour": "World Cup champions 1966"},
    "France": {"ranking": 2, "honour": "World Cup champions 2018 & 1998"},
    "Germany": {"ranking": 11, "honour": "World Cup champions 4 times"},
    "Ghana": {"ranking": 68, "honour": "Reached WC quarter-finals 2010"},
    "Haiti": {"ranking": 84, "honour": "First WC since 1974"},
    "IR Iran": {"ranking": 21, "honour": "AFC Asian Cup champions 3 times"},
    "Iraq": {"ranking": 58, "honour": "AFC Asian Cup champions 2007"},
    "Japan": {"ranking": 17, "honour": "AFC Asian Cup champions 4 times"},
    "Jordan": {"ranking": 70, "honour": "AFC Asian Cup runners-up 2024"},
    "Korea Republic": {"ranking": 23, "honour": "WC semi-finalists 2002 (co-host)"},
    "Mexico": {"ranking": 15, "honour": "Co-host; Gold Cup champions 12 times"},
    "Morocco": {"ranking": 13, "honour": "WC semi-finalists 2022; AFCON 1976"},
    "Netherlands": {"ranking": 7, "honour": "WC runners-up 3 times"},
    "New Zealand": {"ranking": 93, "honour": "OFC Nations Cup champions 2016"},
    "Norway": {"ranking": 45, "honour": "WC round of 16 in 1998"},
    "Panama": {"ranking": 42, "honour": "First WC in 2018"},
    "Paraguay": {"ranking": 52, "honour": "Copa América champions 1979 & 1953"},
    "Portugal": {"ranking": 6, "honour": "Euro champions 2016"},
    "Qatar": {"ranking": 35, "honour": "AFC Asian Cup champions 2019; WC hosts 2022"},
    "Saudi Arabia": {"ranking": 56, "honour": "AFC Asian Cup champions 3 times"},
    "Scotland": {"ranking": 39, "honour": "First WC since 1998"},
    "Senegal": {"ranking": 18, "honour": "AFCON champions 2021"},
    "South Africa": {"ranking": 59, "honour": "AFCON champions 1996; WC hosts 2010"},
    "Spain": {"ranking": 3, "honour": "World Cup champions 2010; Euro 2008 & 2012"},
    "Sweden": {"ranking": 26, "honour": "WC runners-up 1958"},
    "Switzerland": {"ranking": 19, "honour": "WC quarter-finals 2014 & 2018"},
    "Tunisia": {"ranking": 40, "honour": "AFCON champions 2004"},
    "Türkiye": {"ranking": 37, "honour": "WC third place 2002"},
    "USA": {"ranking": 12, "honour": "Co-host; Gold Cup champions 7 times"},
    "Uruguay": {"ranking": 9, "honour": "World Cup champions 1930 & 1950"},
    "Uzbekistan": {"ranking": 62, "honour": "AFC Asian Cup runners-up 2011"},
}

# Last meetings: (year, home_score, away_score) from home team perspective in each row
# Key is alphabetically sorted pair
H2H_HISTORY: dict[tuple[str, str], list[tuple[int, int, int]]] = {
    ("Mexico", "South Africa"): [(2010, 1, 1), (2005, 2, 0), (1999, 2, 1)],
    ("Czechia", "Korea Republic"): [(1990, 1, 3), (1982, 0, 0)],
    ("Canada", "Bosnia and Herzegovina"): [],
    ("Paraguay", "USA"): [(2011, 0, 1), (2007, 1, 1), (2006, 0, 1), (2003, 1, 0), (2001, 3, 1)],
    ("Australia", "Türkiye"): [(2004, 3, 1), (2001, 0, 3)],
    ("Brazil", "Morocco"): [(1998, 3, 0), (1972, 2, 1)],
    ("Haiti", "Scotland"): [],
    ("Qatar", "Switzerland"): [(2018, 0, 1)],
    ("Côte d'Ivoire", "Ecuador"): [(2014, 1, 2), (2009, 0, 0)],
    ("Curaçao", "Germany"): [],
    ("Japan", "Netherlands"): [(2014, 2, 2), (2010, 0, 1), (2006, 0, 0), (2004, 0, 3), (2000, 1, 3)],
    ("Sweden", "Tunisia"): [(2018, 2, 1), (2002, 1, 1)],
    ("Saudi Arabia", "Uruguay"): [(2018, 0, 1), (2006, 0, 1), (2002, 0, 3)],
    ("Cabo Verde", "Spain"): [],
    ("Belgium", "Egypt"): [(2018, 3, 0)],
    ("IR Iran", "New Zealand"): [(2012, 1, 0)],
    ("France", "Senegal"): [(2002, 0, 1), (1999, 2, 0)],
    ("Iraq", "Norway"): [],
    ("Algeria", "Argentina"): [(2014, 2, 3), (2003, 1, 2)],
    ("Austria", "Jordan"): [],
    ("Croatia", "England"): [(2018, 0, 0), (2008, 1, 2), (2004, 0, 0)],
    ("Colombia", "Portugal"): [(2014, 0, 0), (2003, 1, 0)],
    ("Congo DR", "Uzbekistan"): [],
    ("Ghana", "Panama"): [],
    ("Brazil", "Scotland"): [(1998, 2, 1), (1982, 4, 1)],
    ("Germany", "Côte d'Ivoire"): [(2006, 3, 0)],
    ("Argentina", "Austria"): [(1990, 1, 0), (1982, 2, 2)],
    ("England", "France"): [(2017, 2, 3), (2015, 2, 0), (2012, 1, 2), (2008, 0, 1), (2004, 1, 2)],
    ("Portugal", "Spain"): [(2018, 3, 3), (2012, 0, 0), (2010, 0, 1), (2008, 0, 1), (2006, 0, 0)],
    ("Mexico", "Korea Republic"): [(2018, 0, 2), (2014, 0, 0), (2001, 0, 0)],
    ("USA", "Australia"): [(2014, 2, 0), (2013, 2, 1), (2009, 0, 0)],
    ("Canada", "Qatar"): [],
    ("Netherlands", "Sweden"): [(2018, 0, 0), (2014, 2, 0), (2008, 1, 0)],
    ("Japan", "Tunisia"): [(2006, 0, 0)],
    ("Spain", "Saudi Arabia"): [(2018, 1, 5), (2006, 3, 0)],
    ("Belgium", "IR Iran"): [],
    ("Egypt", "New Zealand"): [],
    ("Norway", "Senegal"): [],
    ("Jordan", "Algeria"): [],
    ("Czechia", "South Africa"): [],
    ("Bosnia and Herzegovina", "Switzerland"): [],
    ("Brazil", "Haiti"): [],
    ("Morocco", "Scotland"): [],
    ("Paraguay", "Türkiye"): [],
    ("Ecuador", "Germany"): [],
    ("Curaçao", "Côte d'Ivoire"): [],
    ("Colombia", "Congo DR"): [],
    ("Panama", "Croatia"): [],
    ("Ghana", "England"): [],
    ("Uzbekistan", "Portugal"): [],
}


def _pair_key(team_a: str, team_b: str) -> tuple[str, str]:
    return tuple(sorted([team_a, team_b]))


def get_team_fact(team: str) -> dict:
    default = {"ranking": "—", "honour": "World Cup 2026 participant"}
    return {**default, **TEAM_FACTS.get(team, {})}


def get_head_to_head(home: str, away: str, limit: int = 5) -> list[dict]:
    key = _pair_key(home, away)
    raw = H2H_HISTORY.get(key, [])
    results = []
    for year, h_score, a_score in raw[:limit]:
        if key[0] == home:
            results.append({"year": year, "home_score": h_score, "away_score": a_score})
        else:
            results.append({"year": year, "home_score": a_score, "away_score": h_score})
    return results[:limit]


def get_match_context(home: str, away: str) -> dict:
    h2h = get_head_to_head(home, away)
    return {
        "has_history": len(h2h) > 0,
        "history": h2h,
        "home_fact": get_team_fact(home),
        "away_fact": get_team_fact(away),
    }

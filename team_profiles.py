"""Full team profiles for World Cup 2026 — history, staff, and key players."""

from __future__ import annotations

from teams import get_all_teams

# WC record = all-time World Cup finals matches (W-D-L, approximate)
TEAM_PROFILES: dict[str, dict] = {
    "Algeria": {"appearances": 5, "first": 1982, "best": "Round of 16 (2014)", "titles": 0, "wc_w": 3, "wc_d": 4, "wc_l": 8, "coach": "Djamel Belmadi", "captain": "Riyad Mahrez", "key_player": "Riyad Mahrez", "history": ["1982, 1986, 2010, 2014, 2026"]},
    "Argentina": {"appearances": 18, "first": 1930, "best": "Champions (1978, 1986, 2022)", "titles": 3, "wc_w": 47, "wc_d": 15, "wc_l": 18, "coach": "Lionel Scaloni", "captain": "Lionel Messi", "key_player": "Lionel Messi", "history": ["1930 runners-up", "1978 champions", "1986 champions", "1990 runners-up", "2014 runners-up", "2022 champions"]},
    "Australia": {"appearances": 6, "first": 1974, "best": "Round of 16 (2006, 2022)", "titles": 0, "wc_w": 3, "wc_d": 4, "wc_l": 9, "coach": "Graham Arnold", "captain": "Mathew Ryan", "key_player": "Harry Souttar", "history": ["1974, 2006, 2010, 2014, 2018, 2022, 2026"]},
    "Austria": {"appearances": 8, "first": 1934, "best": "Third place (1954)", "titles": 0, "wc_w": 9, "wc_d": 2, "wc_l": 7, "coach": "Ralf Rangnick", "captain": "David Alaba", "key_player": "Marko Arnautović", "history": ["1934 fourth", "1954 third", "1958, 1978, 1982, 1990, 1998, 2026"]},
    "Belgium": {"appearances": 14, "first": 1930, "best": "Third place (2018)", "titles": 0, "wc_w": 20, "wc_d": 8, "wc_l": 14, "coach": "Domenico Tedesco", "captain": "Romelu Lukaku", "key_player": "Kevin De Bruyne", "history": ["1986 fourth", "2018 third", "2022 group stage", "2026"]},
    "Bosnia and Herzegovina": {"appearances": 2, "first": 2014, "best": "Group stage (2014)", "titles": 0, "wc_w": 1, "wc_d": 0, "wc_l": 2, "coach": "Sergej Barbarez", "captain": "Edin Džeko", "key_player": "Edin Džeko", "history": ["2014 group stage", "2026"]},
    "Brazil": {"appearances": 22, "first": 1930, "best": "Champions (5 times)", "titles": 5, "wc_w": 76, "wc_d": 17, "wc_l": 19, "coach": "Dorival Júnior", "captain": "Casemiro", "key_player": "Vinícius Júnior", "history": ["1958, 1962, 1970, 1994, 2002 champions", "2014 fourth", "2022 quarter-finals"]},
    "Cabo Verde": {"appearances": 1, "first": 2026, "best": "Debut (2026)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 0, "coach": "Bubista", "captain": "Ryan Mendes", "key_player": "Ryan Mendes", "history": ["2026 debut"]},
    "Canada": {"appearances": 3, "first": 1986, "best": "Group stage", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 6, "coach": "Jesse Marsch", "captain": "Alphonso Davies", "key_player": "Alphonso Davies", "history": ["1986, 2022 group stage", "2026 co-host"]},
    "Colombia": {"appearances": 7, "first": 1962, "best": "Quarter-finals (2014)", "titles": 0, "wc_w": 9, "wc_d": 6, "wc_l": 8, "coach": "Néstor Lorenzo", "captain": "James Rodríguez", "key_player": "Luis Díaz", "history": ["1962, 1990, 1994, 1998, 2014 QF", "2018, 2026"]},
    "Congo DR": {"appearances": 2, "first": 1974, "best": "Group stage", "titles": 0, "wc_w": 1, "wc_d": 0, "wc_l": 2, "coach": "Sébastien Desabre", "captain": "Chancel Mbemba", "key_player": "Sébastien Haller", "history": ["1974 as Zaire", "2026"]},
    "Croatia": {"appearances": 7, "first": 1998, "best": "Runners-up (2018)", "titles": 0, "wc_w": 13, "wc_d": 7, "wc_l": 7, "coach": "Zlatko Dalić", "captain": "Luka Modrić", "key_player": "Luka Modrić", "history": ["1998 third", "2018 runners-up", "2022 third", "2026"]},
    "Curaçao": {"appearances": 1, "first": 2026, "best": "Debut (2026)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 0, "coach": "Dick Advocaat", "captain": "Cuco Martina", "key_player": "Leandro Bacuna", "history": ["2026 debut"]},
    "Czechia": {"appearances": 1, "first": 2006, "best": "Group stage (as Czech Republic)", "titles": 0, "wc_w": 0, "wc_d": 2, "wc_l": 1, "coach": "Ivan Hašek", "captain": "Tomáš Souček", "key_player": "Patrik Schick", "history": ["2006 group stage", "2026"]},
    "Côte d'Ivoire": {"appearances": 4, "first": 2006, "best": "Group stage", "titles": 0, "wc_w": 2, "wc_d": 2, "wc_l": 4, "coach": "Emerse Fae", "captain": "Serge Aurier", "key_player": "Sébastien Haller", "history": ["2006, 2010, 2014, 2026"]},
    "Ecuador": {"appearances": 5, "first": 2002, "best": "Round of 16 (2006)", "titles": 0, "wc_w": 5, "wc_d": 2, "wc_l": 5, "coach": "Sebastián Beccacece", "captain": "Enner Valencia", "key_player": "Moisés Caicedo", "history": ["2002, 2006 R16", "2014, 2022, 2026"]},
    "Egypt": {"appearances": 3, "first": 1934, "best": "Group stage", "titles": 0, "wc_w": 0, "wc_d": 2, "wc_l": 3, "coach": "Hossam Hassan", "captain": "Mohamed Salah", "key_player": "Mohamed Salah", "history": ["1934, 1990, 2018 group stage", "2026"]},
    "England": {"appearances": 16, "first": 1950, "best": "Champions (1966)", "titles": 1, "wc_w": 32, "wc_d": 15, "wc_l": 18, "coach": "Gareth Southgate", "captain": "Harry Kane", "key_player": "Harry Kane", "history": ["1966 champions", "1990, 2018 semi-finals", "2022 quarter-finals"]},
    "France": {"appearances": 16, "first": 1930, "best": "Champions (1998, 2018)", "titles": 2, "wc_w": 39, "wc_d": 12, "wc_l": 16, "coach": "Didier Deschamps", "captain": "Kylian Mbappé", "key_player": "Kylian Mbappé", "history": ["1998, 2018 champions", "2006, 2022 runners-up"]},
    "Germany": {"appearances": 20, "first": 1934, "best": "Champions (4 times)", "titles": 4, "wc_w": 68, "wc_d": 21, "wc_l": 24, "coach": "Julian Nagelsmann", "captain": "Joshua Kimmich", "key_player": "Jamal Musiala", "history": ["1954, 1974, 1990, 2014 champions", "2010 third"]},
    "Ghana": {"appearances": 5, "first": 2006, "best": "Quarter-finals (2010)", "titles": 0, "wc_w": 5, "wc_d": 2, "wc_l": 6, "coach": "Otto Addo", "captain": "André Ayew", "key_player": "Mohammed Kudus", "history": ["2006, 2010 QF", "2014, 2022, 2026"]},
    "Haiti": {"appearances": 2, "first": 1974, "best": "Group stage (1974)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 3, "coach": "Rodrigue Morti", "captain": "Johny Placide", "key_player": "Duckens Nazon", "history": ["1974 group stage", "2026"]},
    "IR Iran": {"appearances": 7, "first": 1978, "best": "Group stage", "titles": 0, "wc_w": 2, "wc_d": 2, "wc_l": 10, "coach": "Amir Ghalenoei", "captain": "Sardar Azmoun", "key_player": "Sardar Azmoun", "history": ["1978, 1998, 2006, 2014, 2018, 2022", "2026"]},
    "Iraq": {"appearances": 1, "first": 1986, "best": "Group stage (1986)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 3, "coach": "Hussein Ali Mohammed", "captain": "Aymen Luay", "key_player": "Aymen Luay", "history": ["1986 group stage", "2026"]},
    "Japan": {"appearances": 8, "first": 1998, "best": "Round of 16 (2002, 2010, 2018, 2022)", "titles": 0, "wc_w": 7, "wc_d": 5, "wc_l": 10, "coach": "Hajime Moriyasu", "captain": "Wataru Endo", "key_player": "Takefusa Kubo", "history": ["1998–2022: four R16", "2026"]},
    "Jordan": {"appearances": 1, "first": 2026, "best": "Debut (2026)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 0, "coach": "Hussein Ammouta", "captain": "Yazan Al-Naimat", "key_player": "Musa Al-Taamari", "history": ["2026 debut"]},
    "Korea Republic": {"appearances": 11, "first": 1954, "best": "Fourth place (2002)", "titles": 0, "wc_w": 7, "wc_d": 6, "wc_l": 16, "coach": "Hong Myung-bo", "captain": "Son Heung-min", "key_player": "Son Heung-min", "history": ["1954, 1986, 1990, 1994, 1998, 2002 fourth", "2006, 2010, 2014, 2018, 2022"]},
    "Mexico": {"appearances": 18, "first": 1930, "best": "Quarter-finals (1970, 1986)", "titles": 0, "wc_w": 16, "wc_d": 14, "wc_l": 25, "coach": "Javier Aguirre", "captain": "Guillermo Ochoa", "key_player": "Hirving Lozano", "history": ["1930–2022: 17 straight", "1970, 1986 QF as host", "2026 co-host"]},
    "Morocco": {"appearances": 7, "first": 1970, "best": "Semi-finals (2022)", "titles": 0, "wc_w": 5, "wc_d": 5, "wc_l": 11, "coach": "Walid Regragui", "captain": "Romain Saïss", "key_player": "Achraf Hakimi", "history": ["1970, 1986, 1994, 1998", "2022 semi-finals", "2026"]},
    "Netherlands": {"appearances": 11, "first": 1934, "best": "Runners-up (3 times)", "titles": 0, "wc_w": 30, "wc_d": 14, "wc_l": 14, "coach": "Ronald Koeman", "captain": "Virgil van Dijk", "key_player": "Cody Gakpo", "history": ["1974, 1978, 2010 runners-up", "2014 third", "2022 QF"]},
    "New Zealand": {"appearances": 3, "first": 1982, "best": "Group stage", "titles": 0, "wc_w": 0, "wc_d": 3, "wc_l": 4, "coach": "Darije Kalezić", "captain": "Winston Reid", "key_player": "Chris Wood", "history": ["1982, 2010, 2026"]},
    "Norway": {"appearances": 4, "first": 1938, "best": "Round of 16 (1998)", "titles": 0, "wc_w": 1, "wc_d": 2, "wc_l": 5, "coach": "Ståle Solbakken", "captain": "Martin Ødegaard", "key_player": "Erling Haaland", "history": ["1938, 1994, 1998", "2026"]},
    "Panama": {"appearances": 2, "first": 2018, "best": "Group stage (2018)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 3, "coach": "Thomas Christiansen", "captain": "Aníbal Godoy", "key_player": "José Fajardo", "history": ["2018 group stage", "2026"]},
    "Paraguay": {"appearances": 9, "first": 1930, "best": "Quarter-finals (2010)", "titles": 0, "wc_w": 7, "wc_d": 7, "wc_l": 13, "coach": "Gustavo Alfaro", "captain": "Gustavo Gómez", "key_player": "Miguel Almirón", "history": ["1930, 1950, 1986, 1998, 2002, 2006, 2010 QF", "2026"]},
    "Portugal": {"appearances": 9, "first": 1966, "best": "Third place (1966)", "titles": 0, "wc_w": 17, "wc_d": 6, "wc_l": 9, "coach": "Roberto Martínez", "captain": "Cristiano Ronaldo", "key_player": "Cristiano Ronaldo", "history": ["1966 third", "2006 fourth", "2022 QF"]},
    "Qatar": {"appearances": 2, "first": 2022, "best": "Group stage (2022)", "titles": 0, "wc_w": 1, "wc_d": 0, "wc_l": 2, "coach": "Bruno Pinheiro", "captain": "Hassan Al-Haydos", "key_player": "Akram Afif", "history": ["2022 hosts", "2026"]},
    "Saudi Arabia": {"appearances": 6, "first": 1994, "best": "Round of 16 (1994)", "titles": 0, "wc_w": 3, "wc_d": 2, "wc_l": 9, "coach": "Roberto Mancini", "captain": "Salem Al-Dawsari", "key_player": "Salem Al-Dawsari", "history": ["1994 R16", "1998, 2002, 2006, 2018, 2022"]},
    "Scotland": {"appearances": 9, "first": 1954, "best": "Group stage", "titles": 0, "wc_w": 0, "wc_d": 4, "wc_l": 12, "coach": "Steve Clarke", "captain": "Andy Robertson", "key_player": "Scott McTominay", "history": ["1954, 1958, 1974, 1978, 1982, 1986, 1990, 1998", "2026"]},
    "Senegal": {"appearances": 4, "first": 2002, "best": "Quarter-finals (2002)", "titles": 0, "wc_w": 3, "wc_d": 4, "wc_l": 3, "coach": "Aliou Cissé", "captain": "Kalidou Koulibaly", "key_player": "Sadio Mané", "history": ["2002 QF", "2018, 2022", "2026"]},
    "South Africa": {"appearances": 4, "first": 1998, "best": "Group stage (2010 hosts)", "titles": 0, "wc_w": 2, "wc_d": 3, "wc_l": 5, "coach": "Hugo Broos", "captain": "Ronwen Williams", "key_player": "Percy Tau", "history": ["1998, 2002, 2010 hosts", "2026"]},
    "Spain": {"appearances": 16, "first": 1934, "best": "Champions (2010)", "titles": 1, "wc_w": 30, "wc_d": 11, "wc_l": 18, "coach": "Luis de la Fuente", "captain": "Álvaro Morata", "key_player": "Lamine Yamal", "history": ["2010 champions", "1950 fourth", "2022 R16"]},
    "Sweden": {"appearances": 12, "first": 1934, "best": "Runners-up (1958)", "titles": 0, "wc_w": 18, "wc_d": 6, "wc_l": 14, "coach": "Jon Dahl Tomasson", "captain": "Victor Lindelöf", "key_player": "Alexander Isak", "history": ["1958 runners-up", "1950 third", "1994 third", "2018 QF"]},
    "Switzerland": {"appearances": 13, "first": 1934, "best": "Quarter-finals (3 times)", "titles": 0, "wc_w": 11, "wc_d": 8, "wc_l": 15, "coach": "Murat Yakin", "captain": "Granit Xhaka", "key_player": "Granit Xhaka", "history": ["1934, 1938, 1950, 1954 QF", "2014, 2018 QF", "2022 R16"]},
    "Tunisia": {"appearances": 6, "first": 1978, "best": "Group stage (1978 winners of group)", "titles": 0, "wc_w": 2, "wc_d": 3, "wc_l": 7, "coach": "Samuel Zauber", "captain": "Youssef Msakni", "key_player": "Aïssa Laïdouni", "history": ["1978, 1998, 2002, 2006, 2018, 2022"]},
    "Türkiye": {"appearances": 3, "first": 1954, "best": "Third place (2002)", "titles": 0, "wc_w": 3, "wc_d": 1, "wc_l": 4, "coach": "Vincenzo Montella", "captain": "Hakan Çalhanoğlu", "key_player": "Arda Güler", "history": ["1954, 2002 third", "2026"]},
    "USA": {"appearances": 11, "first": 1930, "best": "Third place (1930)", "titles": 0, "wc_w": 8, "wc_d": 6, "wc_l": 17, "coach": "Mauricio Pochettino", "captain": "Christian Pulisic", "key_player": "Christian Pulisic", "history": ["1930 semi-finals", "2002 QF", "2026 co-host"]},
    "Uruguay": {"appearances": 14, "first": 1930, "best": "Champions (1930, 1950)", "titles": 2, "wc_w": 24, "wc_d": 8, "wc_l": 14, "coach": "Marcelo Bielsa", "captain": "Diego Godín", "key_player": "Darwin Núñez", "history": ["1930, 1950 champions", "1954, 1970, 2010 fourth"]},
    "Uzbekistan": {"appearances": 1, "first": 2026, "best": "Debut (2026)", "titles": 0, "wc_w": 0, "wc_d": 0, "wc_l": 0, "coach": "Srečko Katanec", "captain": "Eldor Shomurodov", "key_player": "Eldor Shomurodov", "history": ["2026 debut"]},
}

# Merge FIFA rankings from team_data
from team_data import TEAM_FACTS
from team_personnel import enrich_squad_leadership

for team, profile in TEAM_PROFILES.items():
    profile["fifa_ranking"] = TEAM_FACTS.get(team, {}).get("ranking", "—")


def team_slug(name: str) -> str:
    return (
        name.lower()
        .replace("'", "")
        .replace("ô", "o")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ç", "c")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("ä", "a")
        .replace("ž", "z")
        .replace("ć", "c")
        .replace("ğ", "g")
        .replace("ş", "s")
        .replace("ı", "i")
        .replace("ã", "a")
        .replace("á", "a")
        .replace(" ", "-")
    )


_SLUG_TO_TEAM = {team_slug(t): t for t in get_all_teams()}


def team_from_slug(slug: str) -> str | None:
    return _SLUG_TO_TEAM.get(slug)


def get_wc_titles(name: str) -> int:
    profile = TEAM_PROFILES.get(name)
    return profile["titles"] if profile else 0


def get_team_profile(name: str) -> dict | None:
    if name not in TEAM_PROFILES:
        return None
    p = TEAM_PROFILES[name].copy()
    p["name"] = name
    p["slug"] = team_slug(name)
    p["honour"] = TEAM_FACTS.get(name, {}).get("honour", "")
    total = p["wc_w"] + p["wc_d"] + p["wc_l"]
    p["wc_played"] = total
    p["wc_win_pct"] = round(100 * p["wc_w"] / total, 1) if total else 0
    from team_squads import get_fifa_coach, get_team_squad, resolve_squad_name

    fifa_coach = get_fifa_coach(name)
    if fifa_coach:
        p["coach"] = fifa_coach

    for role in ("captain", "key_player"):
        resolved = resolve_squad_name(name, p[role])
        if resolved:
            p[role] = resolved

    p = enrich_squad_leadership(p)

    squad = get_team_squad(name)
    if squad:
        p["squad"] = squad
    return p

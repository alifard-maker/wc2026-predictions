"""Historical World Cup records, rivalries, and coach tournament pedigree."""

from __future__ import annotations

# All-time leading WC goal scorer per nation (finals only).
WC_TOP_SCORER: dict[str, dict] = {
    "Algeria": {"name": "Rabah Madjer", "goals": 2},
    "Argentina": {"name": "Lionel Messi", "goals": 13},
    "Australia": {"name": "Tim Cahill", "goals": 5},
    "Austria": {"name": "Hans Krankl", "goals": 3},
    "Belgium": {"name": "Romelu Lukaku", "goals": 5},
    "Bosnia and Herzegovina": {"name": "Edin Džeko", "goals": 1},
    "Brazil": {"name": "Ronaldo", "goals": 15},
    "Cabo Verde": {"name": "—", "goals": 0, "note": "WC debut"},
    "Canada": {"name": "—", "goals": 0},
    "Colombia": {"name": "James Rodríguez", "goals": 6},
    "Congo DR": {"name": "Mukadi", "goals": 1},
    "Croatia": {"name": "Davor Šuker", "goals": 6},
    "Curaçao": {"name": "—", "goals": 0, "note": "WC debut"},
    "Czechia": {"name": "Jan Koller", "goals": 1},
    "Côte d'Ivoire": {"name": "Gervinho", "goals": 2},
    "Ecuador": {"name": "Enner Valencia", "goals": 5},
    "Egypt": {"name": "Abdelrahman Fawzi", "goals": 2},
    "England": {"name": "Gary Lineker", "goals": 10},
    "France": {"name": "Just Fontaine", "goals": 13},
    "Germany": {"name": "Miroslav Klose", "goals": 16},
    "Ghana": {"name": "Asamoah Gyan", "goals": 6},
    "Haiti": {"name": "Emmanuel Sanon", "goals": 2},
    "IR Iran": {"name": "Ali Daei", "goals": 2},
    "Iraq": {"name": "—", "goals": 0},
    "Japan": {"name": "Keisuke Honda", "goals": 4},
    "Jordan": {"name": "—", "goals": 0, "note": "WC debut"},
    "Korea Republic": {"name": "Park Ji-sung", "goals": 3},
    "Mexico": {"name": "Javier Hernández", "goals": 4},
    "Morocco": {"name": "Salaheddine Chbihi", "goals": 2},
    "Netherlands": {"name": "Robin van Persie", "goals": 6},
    "New Zealand": {"name": "—", "goals": 0},
    "Norway": {"name": "Tore André Flo", "goals": 1},
    "Panama": {"name": "—", "goals": 0},
    "Paraguay": {"name": "Roque Santa Cruz", "goals": 3},
    "Portugal": {"name": "Cristiano Ronaldo", "goals": 8},
    "Qatar": {"name": "Mohammed Muntari", "goals": 1},
    "Saudi Arabia": {"name": "Sami Al-Jaber", "goals": 3},
    "Scotland": {"name": "Denis Law", "goals": 2},
    "Senegal": {"name": "Sadio Mané", "goals": 3},
    "South Africa": {"name": "Benni McCarthy", "goals": 2},
    "Spain": {"name": "David Villa", "goals": 9},
    "Sweden": {"name": "Tomas Brolin", "goals": 3},
    "Switzerland": {"name": "Josef Hügi", "goals": 4},
    "Tunisia": {"name": "Wahbi Khazri", "goals": 2},
    "Türkiye": {"name": "Hakan Şükür", "goals": 5},
    "USA": {"name": "Landon Donovan", "goals": 5},
    "Uruguay": {"name": "Óscar Míguez", "goals": 8},
    "Uzbekistan": {"name": "—", "goals": 0, "note": "WC debut"},
}

# Memorable WC finals results (best win / heaviest defeat).
WC_MEMORABLE: dict[str, dict] = {
    "Algeria": {"best_win": "1982 — 2–1 vs West Germany", "worst_loss": "2014 — 1–4 vs Belgium"},
    "Argentina": {"best_win": "1986 — 3–2 vs England", "worst_loss": "2010 — 0–4 vs Germany"},
    "Australia": {"best_win": "2006 — 2–2 vs Croatia", "worst_loss": "2010 — 0–4 vs Germany"},
    "Austria": {"best_win": "1954 — 3–1 vs Switzerland", "worst_loss": "1954 — 0–6 vs West Germany"},
    "Belgium": {"best_win": "2018 — 5–2 vs Tunisia", "worst_loss": "1986 — 1–3 vs Soviet Union"},
    "Bosnia and Herzegovina": {"best_win": "2014 — 3–1 vs Iran", "worst_loss": "2014 — 1–2 vs Argentina"},
    "Brazil": {"best_win": "1950 — 7–1 vs Sweden", "worst_loss": "2014 — 1–7 vs Germany"},
    "Cabo Verde": {"best_win": "—", "worst_loss": "—", "note": "WC debut"},
    "Canada": {"best_win": "—", "worst_loss": "1986 — 0–3 vs Hungary"},
    "Colombia": {"best_win": "2014 — 4–1 vs Greece", "worst_loss": "2014 — 1–4 vs Brazil"},
    "Congo DR": {"best_win": "1974 — 1–0 vs Brazil", "worst_loss": "1974 — 0–9 vs Yugoslavia"},
    "Croatia": {"best_win": "2018 — 3–0 vs Argentina", "worst_loss": "1998 — 1–3 vs France"},
    "Curaçao": {"best_win": "—", "worst_loss": "—", "note": "WC debut"},
    "Czechia": {"best_win": "2006 — 0–0 vs Italy", "worst_loss": "2006 — 0–2 vs Ghana"},
    "Côte d'Ivoire": {"best_win": "2006 — 2–1 vs Serbia", "worst_loss": "2014 — 1–2 vs Greece"},
    "Ecuador": {"best_win": "2006 — 2–0 vs Poland", "worst_loss": "2002 — 1–2 vs Mexico"},
    "Egypt": {"best_win": "1934 — 3–1 vs Hungary", "worst_loss": "2018 — 0–3 vs Russia"},
    "England": {"best_win": "1966 — 4–2 vs West Germany (final)", "worst_loss": "1950 — 0–1 vs USA"},
    "France": {"best_win": "2018 — 4–2 vs Croatia (final)", "worst_loss": "2010 — 0–2 vs Mexico"},
    "Germany": {"best_win": "2002 — 8–0 vs Saudi Arabia", "worst_loss": "2018 — 0–2 vs South Korea"},
    "Ghana": {"best_win": "2010 — 3–0 vs Serbia", "worst_loss": "2014 — 1–2 vs USA"},
    "Haiti": {"best_win": "1974 — 1–1 vs Italy", "worst_loss": "1974 — 0–7 vs Poland"},
    "IR Iran": {"best_win": "1998 — 2–1 vs USA", "worst_loss": "2018 — 0–5 vs Spain"},
    "Iraq": {"best_win": "—", "worst_loss": "1986 — 0–2 vs Belgium"},
    "Japan": {"best_win": "2018 — 2–1 vs Colombia", "worst_loss": "1998 — 0–1 vs Argentina"},
    "Jordan": {"best_win": "—", "worst_loss": "—", "note": "WC debut"},
    "Korea Republic": {"best_win": "2002 — 2–0 vs Germany", "worst_loss": "1954 — 0–9 vs Hungary"},
    "Mexico": {"best_win": "1986 — 2–0 vs Bulgaria", "worst_loss": "1978 — 1–6 vs West Germany"},
    "Morocco": {"best_win": "2022 — 2–0 vs Belgium", "worst_loss": "1994 — 0–3 vs Belgium"},
    "Netherlands": {"best_win": "1974 — 4–0 vs Argentina", "worst_loss": "2014 — 1–5 vs Brazil"},
    "New Zealand": {"best_win": "2010 — 1–1 vs Slovakia", "worst_loss": "1982 — 0–5 vs USSR"},
    "Norway": {"best_win": "1998 — 2–1 vs Brazil", "worst_loss": "1998 — 0–1 vs Italy"},
    "Panama": {"best_win": "—", "worst_loss": "2018 — 1–6 vs England"},
    "Paraguay": {"best_win": "2010 — 2–0 vs Slovakia", "worst_loss": "1958 — 2–7 vs France"},
    "Portugal": {"best_win": "2010 — 7–0 vs North Korea", "worst_loss": "2014 — 0–4 vs Germany"},
    "Qatar": {"best_win": "2022 — 2–0 vs Ecuador", "worst_loss": "2022 — 0–2 vs Netherlands"},
    "Saudi Arabia": {"best_win": "1994 — 1–0 vs Belgium", "worst_loss": "2018 — 0–5 vs Russia"},
    "Scotland": {"best_win": "1974 — 2–0 vs Zaire", "worst_loss": "1954 — 0–7 vs Uruguay"},
    "Senegal": {"best_win": "2002 — 1–0 vs France", "worst_loss": "2002 — 1–3 vs Turkey"},
    "South Africa": {"best_win": "2010 — 2–1 vs France", "worst_loss": "1998 — 0–3 vs Uruguay"},
    "Spain": {"best_win": "2010 — 1–0 vs Netherlands (final)", "worst_loss": "2014 — 1–5 vs Netherlands"},
    "Sweden": {"best_win": "1958 — 3–1 vs West Germany", "worst_loss": "2018 — 0–2 vs England"},
    "Switzerland": {"best_win": "1954 — 2–1 vs Italy", "worst_loss": "1966 — 0–5 vs West Germany"},
    "Tunisia": {"best_win": "1978 — 3–1 vs Mexico", "worst_loss": "2006 — 0–3 vs Ukraine"},
    "Türkiye": {"best_win": "2002 — 3–0 vs China", "worst_loss": "1954 — 1–7 vs West Germany"},
    "USA": {"best_win": "1950 — 1–0 vs England", "worst_loss": "2006 — 1–3 vs Czech Republic"},
    "Uruguay": {"best_win": "1930 — 4–2 vs Argentina (final)", "worst_loss": "2014 — 0–3 vs Colombia"},
    "Uzbekistan": {"best_win": "—", "worst_loss": "—", "note": "WC debut"},
}

# Coach personal WC record as manager (W-D-L in finals).
COACH_WC_RECORD: dict[str, dict] = {
    "Javier Aguirre": {"w": 3, "d": 2, "l": 4, "tournaments": "2002, 2010, 2026"},
    "Gareth Southgate": {"w": 6, "d": 4, "l": 3, "tournaments": "2018, 2022"},
    "Didier Deschamps": {"w": 9, "d": 2, "l": 2, "tournaments": "2018, 2022"},
    "Lionel Scaloni": {"w": 7, "d": 1, "l": 1, "tournaments": "2022"},
    "Zlatko Dalić": {"w": 6, "d": 3, "l": 2, "tournaments": "2018, 2022"},
    "Walid Regragui": {"w": 3, "d": 1, "l": 1, "tournaments": "2022"},
    "Luis de la Fuente": {"w": 1, "d": 0, "l": 1, "tournaments": "2022"},
    "Roberto Martínez": {"w": 3, "d": 0, "l": 2, "tournaments": "2018, 2022"},
    "Ronald Koeman": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Julian Nagelsmann": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Mauricio Pochettino": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Marcelo Bielsa": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Hajime Moriyasu": {"w": 2, "d": 1, "l": 1, "tournaments": "2022"},
    "Hong Myung-bo": {"w": 1, "d": 1, "l": 1, "tournaments": "2002 (as player-captain)"},
    "Graham Arnold": {"w": 0, "d": 1, "l": 1, "tournaments": "2022"},
    "Roberto Mancini": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Dick Advocaat": {"w": 0, "d": 1, "l": 2, "tournaments": "2006"},
    "Steve Clarke": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Aliou Cissé": {"w": 2, "d": 2, "l": 1, "tournaments": "2018, 2022"},
    "Néstor Lorenzo": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Gustavo Alfaro": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Jesse Marsch": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Ralf Rangnick": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Dorival Júnior": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Vincenzo Montella": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Murat Yakin": {"w": 1, "d": 1, "l": 1, "tournaments": "2022"},
    "Domenico Tedesco": {"w": 0, "d": 0, "l": 0, "tournaments": "WC debut as coach"},
    "Srečko Katanec": {"w": 0, "d": 0, "l": 0, "tournaments": "2002 (Slovenia)"},
}

CLASSIC_RIVALRIES: list[dict] = [
    {"teams": ("England", "Scotland"), "label": "Auld Derby", "icon": "⚔️"},
    {"teams": ("USA", "Mexico"), "label": "North American Derby", "icon": "🌎"},
    {"teams": ("Argentina", "Brazil"), "label": "Superclásico de las Américas", "icon": "🔥"},
    {"teams": ("Germany", "Netherlands"), "label": "European Clásico", "icon": "⚡"},
    {"teams": ("Portugal", "Spain"), "label": "Iberian Derby", "icon": "🇵🇹🇪🇸"},
    {"teams": ("France", "Germany"), "label": "Franco-German rivalry", "icon": "🗡️"},
    {"teams": ("England", "Germany"), "label": "Football's oldest rivalry", "icon": "🏴󠁧󠁢󠁥󠁮󠁧󠁿🇩🇪"},
    {"teams": ("England", "Argentina"), "label": "Hand of God & beyond", "icon": "✋"},
    {"teams": ("Japan", "Korea Republic"), "label": "East Asian derby", "icon": "🌏"},
    {"teams": ("Mexico", "USA"), "label": "CONCACAF grudge match", "icon": "🌮"},
    {"teams": ("Uruguay", "Argentina"), "label": "Río de la Plata derby", "icon": "🧉"},
    {"teams": ("Croatia", "France"), "label": "2018 final rematch", "icon": "🏆"},
    {"teams": ("Morocco", "Spain"), "label": "Mediterranean neighbours", "icon": "🌊"},
    {"teams": ("Senegal", "France"), "label": "2002 shock & colonial ties", "icon": "💥"},
    {"teams": ("Scotland", "Brazil"), "label": "David vs Goliath", "icon": "🏴󠁧󠁢󠁳󠁣󠁴󠁿🇧🇷"},
    {"teams": ("IR Iran", "USA"), "label": "Political football", "icon": "🌍"},
    {"teams": ("Belgium", "Netherlands"), "label": "Low Countries derby", "icon": "🧇"},
    {"teams": ("Colombia", "Brazil"), "label": "South American clash", "icon": "☕"},
    {"teams": ("Ghana", "Portugal"), "label": "2014 thriller", "icon": "⚽"},
    {"teams": ("Australia", "Japan"), "label": "Asia-Pacific rivalry", "icon": "🌏"},
]


def get_wc_top_scorer(team: str) -> dict:
    return WC_TOP_SCORER.get(team, {"name": "—", "goals": 0})


def get_memorable_results(team: str) -> dict:
    return WC_MEMORABLE.get(team, {"best_win": "—", "worst_loss": "—"})


def get_coach_wc_record(coach_name: str) -> dict | None:
    return COACH_WC_RECORD.get(coach_name)


def get_team_rivalries(team: str, group_opponents: list[str] | None = None) -> list[dict]:
    group_opponents = group_opponents or []
    rivalries = []
    for r in CLASSIC_RIVALRIES:
        a, b = r["teams"]
        if team not in (a, b):
            continue
        opponent = b if team == a else a
        meets_2026 = opponent in group_opponents
        rivalries.append(
            {
                "opponent": opponent,
                "label": r["label"],
                "icon": r["icon"],
                "meets_in_2026": meets_2026,
            }
        )
    rivalries.sort(key=lambda x: (not x["meets_in_2026"], x["label"]))
    return rivalries


def get_team_history_bundle(team: str, group_opponents: list[str] | None = None) -> dict:
    return {
        "top_scorer": get_wc_top_scorer(team),
        "memorable": get_memorable_results(team),
        "rivalries": get_team_rivalries(team, group_opponents),
    }

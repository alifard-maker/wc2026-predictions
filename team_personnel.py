"""Coach, captain, and key-player details for team profile pages."""

from __future__ import annotations

from pathlib import Path

PERSONNEL_IMG_DIR = Path(__file__).parent / "static" / "images" / "personnel"


def person_slug(name: str) -> str:
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


def local_person_photo(name: str) -> str | None:
    path = PERSONNEL_IMG_DIR / f"{person_slug(name)}.jpg"
    if not path.is_file() or path.stat().st_size <= 500:
        return None
    with path.open("rb") as fh:
        head = fh.read(16)
    if head.startswith((b"<!", b"<html", b"<?xml", b"{")):
        return None
    return f"/static/images/personnel/{path.name}"

# Ages as of Jun 2026; NT goals are career totals for the national team (approximate).
PEOPLE: dict[str, dict] = {
    "Achraf Hakimi": {"age": 27, "nt_goals": 15, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Achraf_Hakimi_2018.jpg/120px-Achraf_Hakimi_2018.jpg"},
    "Akram Afif": {"age": 29, "nt_goals": 26},
    "Alexander Isak": {"age": 27, "nt_goals": 18, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6e/Alexander_Isak_2023.jpg/120px-Alexander_Isak_2023.jpg"},
    "Aliou Cissé": {"age": 49, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Aliou_Ciss%C3%A9_2018.jpg/120px-Aliou_Ciss%C3%A9_2018.jpg"},
    "Alphonso Davies": {"age": 25, "nt_goals": 6, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Alphonso_Davies_2019.jpg/120px-Alphonso_Davies_2019.jpg"},
    "Amir Ghalenoei": {"age": 61, "nt_goals": None},
    "Andrew Robertson": {"age": 32, "nt_goals": 3, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Andrew_Robertson_2018.jpg/120px-Andrew_Robertson_2018.jpg"},
    "André Ayew": {"age": 36, "nt_goals": 24, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Andr%C3%A9_Ayew_2018.jpg/120px-Andr%C3%A9_Ayew_2018.jpg"},
    "Aníbal Godoy": {"age": 35, "nt_goals": 2},
    "Arda Güler": {"age": 21, "nt_goals": 4, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Arda_G%C3%BCler_2023.jpg/120px-Arda_G%C3%BCler_2023.jpg"},
    "Aymen Luay": {"age": 24, "nt_goals": 3},
    "Aïssa Laïdouni": {"age": 28, "nt_goals": 1},
    "Bruno Pinheiro": {"age": 38, "nt_goals": None},
    "Bubista": {"age": 49, "nt_goals": None},
    "Casemiro": {"age": 34, "nt_goals": 7, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Casemiro_2018.jpg/120px-Casemiro_2018.jpg"},
    "Chancel Mbemba": {"age": 31, "nt_goals": 5},
    "Chris Wood": {"age": 34, "nt_goals": 32, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Chris_Wood_2018.jpg/120px-Chris_Wood_2018.jpg"},
    "Christian Pulisic": {"age": 27, "nt_goals": 30, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Christian_Pulisic_2019.jpg/120px-Christian_Pulisic_2019.jpg"},
    "Cody Gakpo": {"age": 26, "nt_goals": 14, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Cody_Gakpo_2022.jpg/120px-Cody_Gakpo_2022.jpg"},
    "Cristiano Ronaldo": {"age": 41, "nt_goals": 136, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Cristiano_Ronaldo_2018.jpg/120px-Cristiano_Ronaldo_2018.jpg"},
    "Cuco Martina": {"age": 36, "nt_goals": 1},
    "Darije Kalezić": {"age": 44, "nt_goals": None},
    "Darwin Núñez": {"age": 27, "nt_goals": 18, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Darwin_N%C3%BA%C3%B1ez_2022.jpg/120px-Darwin_N%C3%BA%C3%B1ez_2022.jpg"},
    "David Alaba": {"age": 34, "nt_goals": 41, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/David_Alaba_2019.jpg/120px-David_Alaba_2019.jpg"},
    "Dick Advocaat": {"age": 73, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Dick_Advocaat_2017.jpg/120px-Dick_Advocaat_2017.jpg"},
    "Didier Deschamps": {"age": 58, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1e/Didier_Deschamps_2018.jpg/120px-Didier_Deschamps_2018.jpg"},
    "Diego Godín": {"age": 39, "nt_goals": 8, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Diego_God%C3%ADn_2018.jpg/120px-Diego_God%C3%ADn_2018.jpg"},
    "Djamel Belmadi": {"age": 59, "nt_goals": None},
    "Domenico Tedesco": {"age": 39, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Domenico_Tedesco_2018.jpg/120px-Domenico_Tedesco_2018.jpg"},
    "Dorival Júnior": {"age": 62, "nt_goals": None},
    "Duckens Nazon": {"age": 28, "nt_goals": 8},
    "Edin Džeko": {"age": 39, "nt_goals": 47, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9e/Edin_D%C5%BEeko_2018.jpg/120px-Edin_D%C5%BEeko_2018.jpg"},
    "Eldor Shomurodov": {"age": 30, "nt_goals": 16},
    "Emerse Fae": {"age": 40, "nt_goals": None},
    "Enner Valencia": {"age": 36, "nt_goals": 39, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Enner_Valencia_2014.jpg/120px-Enner_Valencia_2014.jpg"},
    "Erling Haaland": {"age": 26, "nt_goals": 39, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/07/Erling_Haaland_2023.jpg/120px-Erling_Haaland_2023.jpg"},
    "Gareth Southgate": {"age": 56, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Gareth_Southgate_2018.jpg/120px-Gareth_Southgate_2018.jpg"},
    "Graham Arnold": {"age": 62, "nt_goals": None},
    "Granit Xhaka": {"age": 33, "nt_goals": 14, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Granit_Xhaka_2018.jpg/120px-Granit_Xhaka_2018.jpg"},
    "Guillermo Ochoa": {"age": 40, "nt_goals": 0, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Guillermo_Ochoa_2018.jpg/120px-Guillermo_Ochoa_2018.jpg"},
    "Gustavo Alfaro": {"age": 62, "nt_goals": None},
    "Gustavo Gómez": {"age": 32, "nt_goals": 5},
    "Hajime Moriyasu": {"age": 66, "nt_goals": None},
    "Hakan Çalhanoğlu": {"age": 32, "nt_goals": 17, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Hakan_%C3%87alhano%C4%9Flu_2019.jpg/120px-Hakan_%C3%87alhano%C4%9Flu_2019.jpg"},
    "Harry Kane": {"age": 33, "nt_goals": 69, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6d/Harry_Kane_2018.jpg/120px-Harry_Kane_2018.jpg"},
    "Harry Souttar": {"age": 27, "nt_goals": 1},
    "Hassan Al-Haydos": {"age": 34, "nt_goals": 19},
    "Hirving Lozano": {"age": 30, "nt_goals": 18, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Hirving_Lozano_2018.jpg/120px-Hirving_Lozano_2018.jpg"},
    "Hong Myung-bo": {"age": 56, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Hong_Myung-bo_2010.jpg/120px-Hong_Myung-bo_2010.jpg"},
    "Hossam Hassan": {"age": 59, "nt_goals": None},
    "Hugo Broos": {"age": 73, "nt_goals": None},
    "Hussein Ali Mohammed": {"age": 45, "nt_goals": None},
    "Hussein Ammouta": {"age": 55, "nt_goals": None},
    "Ivan Hašek": {"age": 60, "nt_goals": None},
    "Jamal Musiala": {"age": 23, "nt_goals": 4, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Jamal_Musiala_2022.jpg/120px-Jamal_Musiala_2022.jpg"},
    "James Rodríguez": {"age": 34, "nt_goals": 28, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/James_Rodr%C3%ADguez_2018.jpg/120px-James_Rodr%C3%ADguez_2018.jpg"},
    "Javier Aguirre": {"age": 67, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Javier_Aguirre_2010.jpg/120px-Javier_Aguirre_2010.jpg"},
    "Jesse Marsch": {"age": 52, "nt_goals": None},
    "Johny Placide": {"age": 38, "nt_goals": 0},
    "Jon Dahl Tomasson": {"age": 48, "nt_goals": None},
    "Joshua Kimmich": {"age": 31, "nt_goals": 4, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Joshua_Kimmich_2019.jpg/120px-Joshua_Kimmich_2019.jpg"},
    "José Fajardo": {"age": 26, "nt_goals": 3},
    "Julian Nagelsmann": {"age": 38, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Julian_Nagelsmann_2019.jpg/120px-Julian_Nagelsmann_2019.jpg"},
    "Kalidou Koulibaly": {"age": 34, "nt_goals": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Kalidou_Koulibaly_2018.jpg/120px-Kalidou_Koulibaly_2018.jpg"},
    "Kevin De Bruyne": {"age": 34, "nt_goals": 36, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Kevin_De_Bruyne_201807091.jpg/120px-Kevin_De_Bruyne_201807091.jpg"},
    "Kylian Mbappé": {"age": 27, "nt_goals": 48, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Kylian_Mbapp%C3%A9_2018.jpg/120px-Kylian_Mbapp%C3%A9_2018.jpg"},
    "Lamine Yamal": {"age": 19, "nt_goals": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Lamine_Yamal_2024.jpg/120px-Lamine_Yamal_2024.jpg"},
    "Leandro Bacuna": {"age": 34, "nt_goals": 7},
    "Lionel Messi": {"age": 39, "nt_goals": 112, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/Lionel-Messi-Argentina-2022-FIFA-World-Cup_%28cropped%29.jpg/120px-Lionel-Messi-Argentina-2022-FIFA-World-Cup_%28cropped%29.jpg"},
    "Lionel Scaloni": {"age": 48, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Lionel_Scaloni_2019.jpg/120px-Lionel_Scaloni_2019.jpg"},
    "Luis Díaz": {"age": 28, "nt_goals": 12, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Luis_D%C3%ADaz_2022.jpg/120px-Luis_D%C3%ADaz_2022.jpg"},
    "Luis de la Fuente": {"age": 63, "nt_goals": None},
    "Luka Modrić": {"age": 40, "nt_goals": 25, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3f/Luka_Modri%C4%87_2018.jpg/120px-Luka_Modri%C4%87_2018.jpg"},
    "Marcelo Bielsa": {"age": 70, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Marcelo_Bielsa_2018.jpg/120px-Marcelo_Bielsa_2018.jpg"},
    "Marko Arnautović": {"age": 36, "nt_goals": 41, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Marko_Arnautovi%C4%87_2018.jpg/120px-Marko_Arnautovi%C4%87_2018.jpg"},
    "Martin Ødegaard": {"age": 27, "nt_goals": 10, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Martin_%C3%98degaard_2019.jpg/120px-Martin_%C3%98degaard_2019.jpg"},
    "Mathew Ryan": {"age": 33, "nt_goals": 0, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Mathew_Ryan_2018.jpg/120px-Mathew_Ryan_2018.jpg"},
    "Mauricio Pochettino": {"age": 54, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Mauricio_Pochettino_2019.jpg/120px-Mauricio_Pochettino_2019.jpg"},
    "Miguel Almirón": {"age": 31, "nt_goals": 7, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Miguel_Almir%C3%B3n_2019.jpg/120px-Miguel_Almir%C3%B3n_2019.jpg"},
    "Mohamed Salah": {"age": 34, "nt_goals": 58, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7d/Mohamed_Salah_2018.jpg/120px-Mohamed_Salah_2018.jpg"},
    "Mohammed Kudus": {"age": 25, "nt_goals": 10, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Mohammed_Kudus_2022.jpg/120px-Mohammed_Kudus_2022.jpg"},
    "Moisés Caicedo": {"age": 24, "nt_goals": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Mois%C3%A9s_Caicedo_2022.jpg/120px-Mois%C3%A9s_Caicedo_2022.jpg"},
    "Murat Yakin": {"age": 50, "nt_goals": None},
    "Musa Al-Taamari": {"age": 28, "nt_goals": 8},
    "Néstor Lorenzo": {"age": 57, "nt_goals": None},
    "Otto Addo": {"age": 49, "nt_goals": None},
    "Patrik Schick": {"age": 30, "nt_goals": 21, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Patrik_Schick_2018.jpg/120px-Patrik_Schick_2018.jpg"},
    "Percy Tau": {"age": 31, "nt_goals": 8},
    "Ralf Rangnick": {"age": 67, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Ralf_Rangnick_2016.jpg/120px-Ralf_Rangnick_2016.jpg"},
    "Riyad Mahrez": {"age": 34, "nt_goals": 31, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Riyad_Mahrez_2018.jpg/120px-Riyad_Mahrez_2018.jpg"},
    "Roberto Mancini": {"age": 60, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Roberto_Mancini_2018.jpg/120px-Roberto_Mancini_2018.jpg"},
    "Roberto Martínez": {"age": 51, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Roberto_Mart%C3%ADnez_2018.jpg/120px-Roberto_Mart%C3%ADnez_2018.jpg"},
    "Rodrigue Morti": {"age": 45, "nt_goals": None},
    "Romain Saïss": {"age": 35, "nt_goals": 2, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Romain_Sa%C3%AFss_2018.jpg/120px-Romain_Sa%C3%AFss_2018.jpg"},
    "Romelu Lukaku": {"age": 32, "nt_goals": 72, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Romelu_Lukaku_2018.jpg/120px-Romelu_Lukaku_2018.jpg"},
    "Ronald Koeman": {"age": 61, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Ronald_Koeman_2018.jpg/120px-Ronald_Koeman_2018.jpg"},
    "Ronwen Williams": {"age": 33, "nt_goals": 0},
    "Ryan Mendes": {"age": 35, "nt_goals": 13},
    "Sadio Mané": {"age": 34, "nt_goals": 41, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Sadio_Man%C3%A9_2018.jpg/120px-Sadio_Man%C3%A9_2018.jpg"},
    "Salem Al-Dawsari": {"age": 34, "nt_goals": 23, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Salem_Al-Dawsari_2018.jpg/120px-Salem_Al-Dawsari_2018.jpg"},
    "Samuel Zauber": {"age": 50, "nt_goals": None},
    "Sardar Azmoun": {"age": 31, "nt_goals": 46, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Sardar_Azmoun_2018.jpg/120px-Sardar_Azmoun_2018.jpg"},
    "Scott McTominay": {"age": 29, "nt_goals": 12, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Scott_McTominay_2019.jpg/120px-Scott_McTominay_2019.jpg"},
    "Sebastián Beccacece": {"age": 44, "nt_goals": None},
    "Serge Aurier": {"age": 32, "nt_goals": 3, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Serge_Aurier_2018.jpg/120px-Serge_Aurier_2018.jpg"},
    "Sergej Barbarez": {"age": 49, "nt_goals": None},
    "Son Heung-min": {"age": 34, "nt_goals": 42, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Son_Heung-min_2018.jpg/120px-Son_Heung-min_2018.jpg"},
    "Srečko Katanec": {"age": 62, "nt_goals": None},
    "Steve Clarke": {"age": 62, "nt_goals": None},
    "Ståle Solbakken": {"age": 56, "nt_goals": None},
    "Sébastien Desabre": {"age": 51, "nt_goals": None},
    "Sébastien Haller": {"age": 31, "nt_goals": 15, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/S%C3%A9bastien_Haller_2019.jpg/120px-S%C3%A9bastien_Haller_2019.jpg"},
    "Takefusa Kubo": {"age": 24, "nt_goals": 4, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Takefusa_Kubo_2019.jpg/120px-Takefusa_Kubo_2019.jpg"},
    "Thomas Christiansen": {"age": 53, "nt_goals": None},
    "Tomáš Souček": {"age": 30, "nt_goals": 12, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Tom%C3%A1%C5%A1_Sou%C4%8Dek_2019.jpg/120px-Tom%C3%A1%C5%A1_Sou%C4%8Dek_2019.jpg"},
    "Victor Lindelöf": {"age": 31, "nt_goals": 4, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Victor_Lindel%C3%B6f_2018.jpg/120px-Victor_Lindel%C3%B6f_2018.jpg"},
    "Vincenzo Montella": {"age": 51, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Vincenzo_Montella_2018.jpg/120px-Vincenzo_Montella_2018.jpg"},
    "Vinícius Júnior": {"age": 26, "nt_goals": 5, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Vin%C3%ADcius_J%C3%BAnior_2018.jpg/120px-Vin%C3%ADcius_J%C3%BAnior_2018.jpg"},
    "Virgil van Dijk": {"age": 35, "nt_goals": 9, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Virgil_van_Dijk_2019.jpg/120px-Virgil_van_Dijk_2019.jpg"},
    "Walid Regragui": {"age": 50, "nt_goals": None},
    "Wataru Endo": {"age": 32, "nt_goals": 3, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Wataru_Endo_2019.jpg/120px-Wataru_Endo_2019.jpg"},
    "Winston Reid": {"age": 37, "nt_goals": 3},
    "Yazan Al-Naimat": {"age": 24, "nt_goals": 6},
    "Youssef Msakni": {"age": 35, "nt_goals": 18},
    "Zlatko Dalić": {"age": 59, "nt_goals": None, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Zlatko_Dali%C4%87_2018.jpg/120px-Zlatko_Dali%C4%87_2018.jpg"},
    "Álvaro Morata": {"age": 33, "nt_goals": 40, "photo": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/%C3%81lvaro_Morata_2018.jpg/120px-%C3%81lvaro_Morata_2018.jpg"},
}


def person_initial(name: str) -> str:
    for ch in name:
        if ch.isalpha():
            return ch.upper()
    return "?"


def person_info(name: str, role: str) -> dict:
    from team_squads import COACH_NATIONALITY

    data = PEOPLE.get(name, {})
    is_coach = role == "coach"
    return {
        "name": name,
        "age": data.get("age"),
        "nt_goals": None if is_coach else data.get("nt_goals", 0),
        "photo": local_person_photo(name),
        "initial": person_initial(name),
        "nationality": COACH_NATIONALITY.get(name) if is_coach else None,
        "role": role,
    }


def enrich_squad_leadership(profile: dict) -> dict:
    profile["coach_info"] = person_info(profile["coach"], "coach")
    profile["captain_info"] = person_info(profile["captain"], "captain")
    profile["key_player_info"] = person_info(profile["key_player"], "key_player")
    return profile

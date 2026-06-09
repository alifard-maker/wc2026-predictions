#!/usr/bin/env python3
"""Download Wikipedia thumbnails for squad personnel into static/images/personnel/."""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from team_profiles import TEAM_PROFILES, team_slug

OUT_DIR = ROOT / "static" / "images" / "personnel"
UA = "WC2026Predictions/1.0 (local dev)"
BATCH_SIZE = 5


def curl_json(url: str) -> dict | None:
    result = subprocess.run(
        ["curl", "-s", "-A", UA, url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def curl_bytes(url: str) -> bytes | None:
    result = subprocess.run(
        ["curl", "-sL", "-A", UA, url],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    return result.stdout


def batch_thumbs(titles: list[str]) -> dict[str, str]:
    if not titles:
        return {}
    params = urllib.parse.urlencode(
        {
            "action": "query",
            "titles": "|".join(titles),
            "prop": "pageimages",
            "format": "json",
            "pithumbsize": 120,
            "redirects": 1,
        },
        safe="|",
    )
    data = curl_json(f"https://en.wikipedia.org/w/api.php?{params}")
    out: dict[str, str] = {}
    if not data:
        return out
    for page in data.get("query", {}).get("pages", {}).values():
        title = page.get("title")
        thumb = page.get("thumbnail", {}).get("source")
        if title and thumb:
            out[title] = thumb
    return out


def opensearch_best(name: str) -> str | None:
    first = name.split()[0].lower()
    for query in (name, f"{name} footballer", f"{name} football manager", f"{name} football"):
        params = urllib.parse.urlencode(
            {"action": "opensearch", "search": query, "limit": 5, "format": "json"}
        )
        data = curl_json(f"https://en.wikipedia.org/w/api.php?{params}")
        if not data or len(data) < 2:
            continue
        for title in data[1]:
            if first in title.lower():
                return title
        if data[1]:
            return data[1][0]
    return None


# Exact Wikipedia article titles when search/batch lookup fails.
WIKI_TITLE_OVERRIDES: dict[str, str] = {
    "Andrew Robertson": "Andrew Robertson",
    "Aymen Luay": "Aymen Luay",
    "Bruno Pinheiro": "Bruno Pinheiro (football manager)",
    "Bubista": "Bubista (football manager)",
    "Darije Kalezić": "Darije Kalezić",
    "Emerse Fae": "Emerse Faé",
    "Hussein Ali Mohammed": "Hussein Ali Mohammed",
    "José Fajardo": "José Fajardo (footballer)",
    "Luis Díaz": "Luis Díaz (footballer, born 1997)",
    "Marko Arnautović": "Marko Arnautović",
    "Martin Ødegaard": "Martin Ødegaard",
    "Mathew Ryan": "Mathew Ryan",
    "Mauricio Pochettino": "Mauricio Pochettino",
    "Miguel Almirón": "Miguel Almirón",
    "Mohamed Salah": "Mohamed Salah",
    "Mohammed Kudus": "Mohammed Kudus",
    "Moisés Caicedo": "Moisés Caicedo",
    "Murat Yakin": "Murat Yakin",
    "Musa Al-Taamari": "Musa Al-Taamari",
    "Néstor Lorenzo": "Néstor Lorenzo",
    "Otto Addo": "Otto Addo",
    "Patrik Schick": "Patrik Schick",
    "Percy Tau": "Percy Tau",
    "Ralf Rangnick": "Ralf Rangnick",
    "Riyad Mahrez": "Riyad Mahrez",
    "Rodrigue Morti": "Rodrigue Morti",
    "Romain Saïss": "Romain Saïss",
    "Romelu Lukaku": "Romelu Lukaku",
    "Ronald Koeman": "Ronald Koeman",
    "Ronwen Williams": "Ronwen Williams",
    "Ryan Mendes": "Ryan Mendes",
    "Samuel Zauber": "Samuel Zauber",
}

COACHES = {
    "Djamel Belmadi", "Lionel Scaloni", "Graham Arnold", "Ralf Rangnick", "Domenico Tedesco",
    "Sergej Barbarez", "Dorival Júnior", "Bubista", "Jesse Marsch", "Néstor Lorenzo",
    "Sébastien Desabre", "Dick Advocaat", "Ivan Hašek", "Emerse Fae", "Sebastián Beccacece",
    "Hossam Hassan", "Gareth Southgate", "Didier Deschamps", "Julian Nagelsmann", "Otto Addo",
    "Rodrigue Morti", "Amir Ghalenoei", "Hussein Ali Mohammed", "Hajime Moriyasu", "Hussein Ammouta",
    "Hong Myung-bo", "Javier Aguirre", "Walid Regragui", "Ronald Koeman", "Darije Kalezić",
    "Ståle Solbakken", "Thomas Christiansen", "Gustavo Alfaro", "Roberto Martínez", "Bruno Pinheiro",
    "Roberto Mancini", "Steve Clarke", "Aliou Cissé", "Hugo Broos", "Luis de la Fuente",
    "Jon Dahl Tomasson", "Murat Yakin", "Samuel Zauber", "Vincenzo Montella", "Mauricio Pochettino",
    "Marcelo Bielsa", "Srečko Katanec",
}


def resolve_thumb_urls(names: list[str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    pending = list(names)

    for name in list(pending):
        override = WIKI_TITLE_OVERRIDES.get(name)
        if not override:
            continue
        thumbs = batch_thumbs([override])
        if override in thumbs:
            resolved[name] = thumbs[override]
        time.sleep(0.4)

    pending = [n for n in pending if n not in resolved]

    for i in range(0, len(pending), BATCH_SIZE):
        chunk = pending[i : i + BATCH_SIZE]
        titles = list(chunk)
        for name in chunk:
            if name in COACHES:
                titles.append(f"{name} (football manager)")
        thumbs = batch_thumbs(titles)
        for name in chunk:
            for candidate in (name, f"{name} (football manager)", f"{name} (footballer)"):
                if candidate in thumbs:
                    resolved[name] = thumbs[candidate]
                    break
        time.sleep(0.5)

    still_missing = [n for n in names if n not in resolved]
    for name in still_missing:
        title = opensearch_best(name)
        if not title:
            print(f"lookup miss {name}")
            time.sleep(0.5)
            continue
        thumbs = batch_thumbs([title])
        if title in thumbs:
            resolved[name] = thumbs[title]
            print(f"lookup ok {name} -> {title}")
        else:
            print(f"lookup miss {name}")
        time.sleep(0.5)

    return resolved


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    names = sorted({p[k] for p in TEAM_PROFILES.values() for k in ("coach", "captain", "key_player")})
    existing = sum(
        1 for n in names if (OUT_DIR / f"{team_slug(n)}.jpg").exists() and (OUT_DIR / f"{team_slug(n)}.jpg").stat().st_size > 500
    )
    to_fetch = [n for n in names if not ((OUT_DIR / f"{team_slug(n)}.jpg").exists() and (OUT_DIR / f"{team_slug(n)}.jpg").stat().st_size > 500)]

    print(f"resolving {len(to_fetch)} missing thumbnails via Wikipedia…")
    thumbs = resolve_thumb_urls(to_fetch)

    saved = existing
    for name, url in thumbs.items():
        out = OUT_DIR / f"{team_slug(name)}.jpg"
        data = curl_bytes(url)
        if not data or len(data) < 500:
            print(f"download fail {name}")
            continue
        out.write_bytes(data)
        saved += 1
        print(f"saved {name}")
        time.sleep(0.15)

    print(f"done: {saved}/{len(names)} photos on disk")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Crawl app pages and verify internal links return 200."""
from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
from app import app  # noqa: E402


class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        for name, value in attrs:
            if name == "href" and value:
                self.hrefs.append(value)


def extract_hrefs(html: str) -> list[str]:
    parser = LinkParser()
    parser.feed(html)
    return parser.hrefs


def is_internal(href: str) -> bool:
    if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
        return False
    parsed = urlparse(href)
    return not parsed.netloc or parsed.netloc in ("localhost", "127.0.0.1")


def normalize_path(href: str, base: str) -> str:
    full = urljoin(base, href)
    parsed = urlparse(full)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    return path


def main() -> int:
    db.init_db()
    with db.db() as conn:
        pool = conn.execute("SELECT * FROM pools LIMIT 1").fetchone()
        user = conn.execute(
            "SELECT * FROM users WHERE pool_id = ? LIMIT 1", (pool["id"],)
        ).fetchone()
    if not pool or not user:
        pool = db.create_pool("CI smoke pool")
        joined = db.add_user(pool["id"], "CI smoke tester")
        if isinstance(joined, str):
            print(f"Could not create CI user: {joined}")
            return 1
        user = db.get_user(joined["id"])
    if not pool or not user:
        print("No pool/user in database.")
        return 1

    invite = pool["invite_code"]
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["user_id"] = user["id"]
        sess["pool_id"] = pool["id"]
        sess["invite_code"] = invite
        sess["display_name"] = user["display_name"]

    seed_paths = [
        "/",
        f"/pool/{invite}",
        f"/pool/{invite}/standings",
        f"/pool/{invite}/tournament",
        f"/pool/{invite}/scorers",
        f"/pool/{invite}/cards",
        f"/pool/{invite}/leaderboard",
        f"/pool/{invite}/recaps",
        f"/pool/{invite}/guide",
        f"/pool/{invite}/player/{user['id']}",
        f"/pool/{invite}/comments",
        f"/pool/{invite}/admin",
    ]
    for mid in range(1, 73):
        seed_paths.append(f"/pool/{invite}/match/{mid}")
    for team in ("brazil", "england", "mexico"):
        seed_paths.append(f"/pool/{invite}/team/{team}")

    visited: set[str] = set()
    queue = list(seed_paths)
    broken: list[tuple[str, str, int]] = []

    while queue:
        path = queue.pop(0)
        if path in visited:
            continue
        visited.add(path)

        res = client.get(path, follow_redirects=True)
        if res.status_code >= 400:
            broken.append(("page", path, res.status_code))
            continue

        if "text/html" not in (res.content_type or ""):
            continue

        html = res.get_data(as_text=True)
        for href in extract_hrefs(html):
            if not is_internal(href):
                continue
            link_path = normalize_path(href, f"http://localhost{path}")
            if link_path in visited:
                continue
            link_res = client.get(link_path, follow_redirects=True)
            if link_res.status_code >= 400:
                broken.append((path, link_path, link_res.status_code))
            elif link_path.startswith(f"/pool/{invite}") and link_res.content_type and "html" in link_res.content_type:
                if link_path not in visited and link_path not in queue:
                    queue.append(link_path)

    print(f"Checked {len(visited)} pages.")
    if broken:
        print(f"BROKEN ({len(broken)}):")
        for source, target, code in sorted(broken):
            print(f"  [{code}] {target}  (from {source})")
        return 1

    print("All internal links OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

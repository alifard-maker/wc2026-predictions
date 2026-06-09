"""Fetch latest FIFA / World Cup 2026 headlines from public RSS feeds."""

from __future__ import annotations

import re
import ssl
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

import certifi

from zoneinfo import ZoneInfo

TIMEZONE = ZoneInfo("America/New_York")
MAX_ITEMS = 4
CACHE_SECONDS = 600

RSS_FEEDS = (
    ("https://news.google.com/rss/search?q=FIFA+World+Cup+2026&hl=en-US&gl=US&ceid=US:en", False),
    ("https://news.google.com/rss/search?q=World+Cup+2026+qualifiers&hl=en-US&gl=US&ceid=US:en", False),
    ("https://feeds.bbci.co.uk/sport/football/rss.xml", True),
)

WC_KEYWORDS = ("world cup", "fifa", "2026")

_cache: dict = {"at": 0.0, "items": []}


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_pub_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(TIMEZONE)
    except (TypeError, ValueError, OverflowError):
        return None


def _parse_rss(xml_text: str, source_label: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    channel = root.find("channel")
    if channel is None:
        return []

    items: list[dict] = []
    for item in channel.findall("item"):
        title = _strip_html(item.findtext("title", ""))
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        published = _parse_pub_date(item.findtext("pubDate"))
        source = _strip_html(item.findtext("source", "")) or source_label
        items.append({
            "title": title,
            "url": link,
            "source": source,
            "published_at": published.isoformat() if published else None,
            "published_display": _format_published(published),
        })
    return items


def _format_published(dt: datetime | None) -> str:
    if not dt:
        return ""
    now = datetime.now(TIMEZONE)
    delta = now - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "Just now"
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 48:
        return f"{hours}h ago"
    return dt.strftime("%d %b %Y")


def _wc_related(title: str) -> bool:
    lowered = title.lower()
    return any(keyword in lowered for keyword in WC_KEYWORDS)


def _fetch_feed(url: str, filter_wc_only: bool = False) -> list[dict]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; WC2026-Predictions/1.0)"})
    ctx = ssl.create_default_context(cafile=certifi.where())
    with urlopen(req, timeout=12, context=ctx) as resp:
        xml_text = resp.read().decode("utf-8", errors="replace")
    label = "BBC Sport" if "bbc.co.uk" in url else "Google News"
    items = _parse_rss(xml_text, label)
    if filter_wc_only:
        items = [item for item in items if _wc_related(item["title"])]
    return items


def get_wc_news(force_refresh: bool = False) -> list[dict]:
    """Return up to MAX_ITEMS recent headlines; cache for CACHE_SECONDS."""
    now = time.time()
    if not force_refresh and _cache["items"] and now - _cache["at"] < CACHE_SECONDS:
        return _cache["items"]

    collected: list[dict] = []
    seen_urls: set[str] = set()

    for feed_url, filter_wc_only in RSS_FEEDS:
        try:
            for item in _fetch_feed(feed_url, filter_wc_only):
                if item["url"] in seen_urls:
                    continue
                seen_urls.add(item["url"])
                collected.append(item)
        except (URLError, ET.ParseError, TimeoutError, OSError):
            continue

    collected.sort(
        key=lambda x: x.get("published_at") or "",
        reverse=True,
    )
    items = collected[:MAX_ITEMS]
    if items:
        _cache["at"] = now
        _cache["items"] = items
    elif _cache["items"]:
        return _cache["items"]

    return items


def news_for_json(items: list[dict]) -> dict:
    return {
        "items": items,
        "fetched_at": datetime.fromtimestamp(_cache["at"], TIMEZONE).isoformat()
        if _cache["at"]
        else None,
        "refresh_seconds": CACHE_SECONDS,
    }

#!/usr/bin/env python3
"""Ping production /health and fail on match-window invariant violations.

Run locally:
  WATCHDOG_URL=https://wc2026-predictions.up.railway.app python3 scripts/match_watchdog.py

In CI (GitHub Actions), set WATCHDOG_URL to your Railway app URL.
On failure, paste the output into a Cursor agent to triage.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def main() -> int:
    base = os.environ.get(
        "WATCHDOG_URL", "https://wc2026-predictions.up.railway.app"
    ).rstrip("/")
    url = f"{base}/health"
    req = urllib.request.Request(url, headers={"User-Agent": "wc2026-match-watchdog/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            status = resp.status
    except urllib.error.HTTPError as exc:
        print(f"HTTP {exc.code} from {url}")
        try:
            print(exc.read().decode("utf-8", errors="replace"))
        except Exception:
            pass
        return 1
    except urllib.error.URLError as exc:
        print(f"Could not reach {url}: {exc}")
        return 1

    if status != 200:
        print(f"Unexpected HTTP {status} from {url}")
        print(body)
        return 1

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        print(f"Non-JSON response from {url}")
        print(body[:500])
        return 1

    print(f"OK  version={data.get('version')}  url={url}")

    match_checks = data.get("match_checks") or {}
    live = match_checks.get("live_count", 0)
    soon = match_checks.get("kickoff_within_hour", 0)
    print(f"live={live}  kickoff_within_hour={soon}")

    live_sync = data.get("live_sync") or {}
    if live_sync.get("last_error"):
        print(f"live_sync_error={live_sync['last_error']}")

    espn_err = data.get("espn_sync_error")
    if espn_err:
        print(f"espn_sync_error={espn_err}")

    issues = match_checks.get("issues") or []
    if issues:
        print(f"MATCH CHECK FAILED ({len(issues)} issue(s)):")
        for item in issues:
            print(f"  - {item}")
        print()
        print("Triage: open Cursor on wc2026-predictions and ask the agent to")
        print("investigate these /health match_checks issues and fix the root cause.")
        return 1

    if data.get("status") != "ok":
        print(f"Health status not ok: {data.get('status')}")
        return 1

    print("All match health checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

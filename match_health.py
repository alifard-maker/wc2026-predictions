"""Server-side invariants for live / finished match display and sync."""

from __future__ import annotations

from datetime import datetime, timedelta

from live_scores import apply_live_state, parse_match_datetime
from scoring import TIMEZONE


def run_match_health_checks(now: datetime | None = None) -> dict:
    """Return structured checks used by /health and the match watchdog."""
    import db
    import live_score_sync

    now = now or datetime.now(TIMEZONE)
    issues: list[str] = []
    live_count = 0
    finished_count = 0
    kickoff_soon = 0

    for row in db.get_all_matches():
        raw = dict(row)
        enriched = apply_live_state(raw, now)
        kickoff = enriched.get("kickoff") or parse_match_datetime(
            raw["match_date"], raw["match_time"]
        )
        label = f"{raw['home_team']} vs {raw['away_team']} (id={raw['id']})"

        if enriched.get("is_live"):
            live_count += 1
            if enriched.get("display_home") is None or enriched.get("display_away") is None:
                issues.append(f"Live match missing display score: {label}")

        if enriched.get("is_finished"):
            finished_count += 1
            if raw.get("actual_home") is None or raw.get("actual_away") is None:
                issues.append(f"Finished match missing final score in DB: {label}")

        if now < kickoff <= now + timedelta(hours=1):
            kickoff_soon += 1

        if enriched.get("is_live") and now < kickoff - timedelta(minutes=5):
            issues.append(f"Match marked live before kickoff window: {label}")

        if raw.get("actual_home") is not None and raw.get("actual_away") is not None:
            if enriched.get("is_live"):
                issues.append(f"Match has final score but still live: {label}")

    sync = live_score_sync.get_sync_status()
    if live_count and sync.get("enabled"):
        summary = sync.get("last_summary") or {}
        synced_at = summary.get("synced_at")
        if not synced_at:
            issues.append("Live matches in progress but live sync has never run.")
        else:
            try:
                last = datetime.fromisoformat(synced_at)
                if last.tzinfo is None:
                    last = last.replace(tzinfo=TIMEZONE)
                stale_after = timedelta(
                    seconds=max(120, int(sync.get("interval_seconds") or 30) * 4)
                )
                if now - last > stale_after:
                    issues.append(
                        f"Live sync stale (last run {synced_at}, threshold {int(stale_after.total_seconds())}s)."
                    )
            except (TypeError, ValueError):
                issues.append(f"Live sync timestamp unreadable: {synced_at!r}")

        if sync.get("last_error"):
            issues.append(f"Live sync error: {sync['last_error']}")

    espn_error = db.get_sync_meta("espn_sync_error") or ""
    if espn_error.strip() and (live_count or kickoff_soon):
        issues.append(f"ESPN sync error during active window: {espn_error.strip()}")

    return {
        "ok": not issues,
        "checked_at": now.isoformat(),
        "live_count": live_count,
        "finished_count": finished_count,
        "kickoff_within_hour": kickoff_soon,
        "issues": issues,
    }

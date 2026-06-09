"""Bonus points for best predictions across each World Cup phase."""

from __future__ import annotations

from scoring import PHASE_BONUS_PTS

PHASE_BONUS_ROUNDS: list[tuple[str, str, int]] = [
    ("group", "Group stage", 72),
    ("round_of_32", "Round of 32", 16),
    ("round_of_16", "Round of 16", 8),
    ("quarter_final", "Quarter-finals", 4),
    ("semi_final", "Semi-finals", 2),
]


def _phase_matches(matches: list[dict], phase_key: str) -> list[dict]:
    return [m for m in matches if m.get("stage") == phase_key]


def _phase_complete(phase_matches: list[dict]) -> bool:
    if not phase_matches:
        return False
    return all(
        m.get("actual_home") is not None and m.get("actual_away") is not None
        for m in phase_matches
    )


def _user_phase_points(pool_id: int, match_ids: list[int]) -> list[dict]:
    if not match_ids:
        return []

    from db import db

    placeholders = ",".join("?" * len(match_ids))
    with db() as conn:
        rows = conn.execute(
            f"""
            SELECT u.id, u.display_name, COALESCE(SUM(p.points), 0) AS phase_points
            FROM users u
            LEFT JOIN predictions p ON p.user_id = u.id AND p.match_id IN ({placeholders})
            WHERE u.pool_id = ?
            GROUP BY u.id
            """,
            (*match_ids, pool_id),
        ).fetchall()
    return [dict(r) for r in rows]


def _phase_winners(scores: list[dict]) -> list[dict]:
    if not scores:
        return []
    best = max(s["phase_points"] for s in scores)
    if best <= 0:
        return []
    return [s for s in scores if s["phase_points"] == best]


def compute_pool_phase_bonuses(pool_id: int, matches: list[dict] | None = None) -> dict:
    """Return phase bonus totals per user and status for each awardable phase."""
    from db import get_all_matches

    matches = matches or [dict(m) for m in get_all_matches()]
    total_by_user: dict[int, int] = {}
    detail_by_user: dict[int, list[dict]] = {}
    phases: list[dict] = []

    for phase_key, label, expected_count in PHASE_BONUS_ROUNDS:
        phase_matches = _phase_matches(matches, phase_key)
        finished = sum(
            1
            for m in phase_matches
            if m.get("actual_home") is not None and m.get("actual_away") is not None
        )
        complete = _phase_complete(phase_matches)
        match_ids = [m["id"] for m in phase_matches]
        scores = _user_phase_points(pool_id, match_ids) if complete else []
        winners = _phase_winners(scores)

        for winner in winners:
            uid = winner["id"]
            total_by_user[uid] = total_by_user.get(uid, 0) + PHASE_BONUS_PTS
            detail_by_user.setdefault(uid, []).append(
                {
                    "key": phase_key,
                    "label": label,
                    "points": PHASE_BONUS_PTS,
                    "phase_points": winner["phase_points"],
                }
            )

        phases.append(
            {
                "key": phase_key,
                "label": label,
                "expected_count": expected_count,
                "match_count": len(phase_matches),
                "finished_count": finished,
                "complete": complete,
                "bonus_pts": PHASE_BONUS_PTS,
                "winners": [
                    {
                        "user_id": w["id"],
                        "display_name": w["display_name"],
                        "phase_points": w["phase_points"],
                    }
                    for w in winners
                ],
            }
        )

    return {
        "total_by_user": total_by_user,
        "detail_by_user": detail_by_user,
        "phases": phases,
    }

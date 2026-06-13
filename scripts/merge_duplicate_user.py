#!/usr/bin/env python3
"""Merge duplicate pool accounts that share a display name (e.g. QueenOfPredictions)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge duplicate users by display name.")
    parser.add_argument("display_name", help="Player name to merge (e.g. QueenOfPredictions)")
    parser.add_argument("--invite-code", help="Limit to one pool")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Merge all duplicate names in the pool(s), not just one name",
    )
    args = parser.parse_args()

    pool_id = None
    if args.invite_code:
        pool = db.get_pool_by_code(args.invite_code.strip())
        if not pool:
            print(f"Error: no pool for invite code {args.invite_code!r}", file=sys.stderr)
            return 1
        pool_id = pool["id"]

    db.init_db()
    if args.all:
        merged = db.merge_duplicate_users(pool_id)
    else:
        merged = db.merge_users_named(args.display_name, pool_id=pool_id)

    if not merged:
        print("No duplicate accounts found to merge.")
        return 0
    print("Merged:")
    for line in merged:
        print(f"  - {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

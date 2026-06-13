#!/usr/bin/env python3
"""Set pool admin password(s). Run locally or via `railway run python scripts/set_admin_secret.py ...`."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import db  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Update pool admin secret(s).")
    parser.add_argument("secret", help="New admin password")
    parser.add_argument(
        "--invite-code",
        help="Only update this pool (default: all pools in the database)",
    )
    args = parser.parse_args()
    try:
        names = db.update_admin_secret(args.secret, invite_code=args.invite_code)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    scope = f"pool {args.invite_code}" if args.invite_code else f"{len(names)} pool(s)"
    print(f"Updated admin secret for {scope}: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

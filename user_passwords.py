"""Optional per-user passwords (pilot rollout).

Only display names listed in PASSWORD_PILOT_USERS require a password.
Expand the pilot list (or env var) when ready for all human players.
"""

from __future__ import annotations

import os
import re

from werkzeug.security import check_password_hash, generate_password_hash

from db import normalize_display_name

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128

# Comma-separated names in env override this default pilot list.
_DEFAULT_PILOT_USERS = ("Morpheus",)


def password_pilot_users() -> frozenset[str]:
    raw = os.environ.get("PASSWORD_PILOT_USERS", "").strip()
    if raw:
        names = [part.strip() for part in raw.split(",") if part.strip()]
    else:
        names = list(_DEFAULT_PILOT_USERS)
    return frozenset(normalize_display_name(name) for name in names)


def user_requires_password(display_name: str) -> bool:
    return normalize_display_name(display_name) in password_pilot_users()


def hash_password(plain: str) -> str:
    return generate_password_hash(plain)


def passwords_match(plain: str, password_hash: str | None) -> bool:
    if not plain or not password_hash:
        return False
    return check_password_hash(password_hash, plain)


def validate_new_password(plain: str, confirm: str) -> str | None:
    if not plain:
        return "Password is required."
    if len(plain) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(plain) > MAX_PASSWORD_LENGTH:
        return f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer."
    if plain != confirm:
        return "Passwords do not match."
    if plain.strip() != plain:
        return "Password cannot start or end with spaces."
    if not re.search(r"[A-Za-z]", plain) or not re.search(r"\d", plain):
        return "Password must include at least one letter and one number."
    return None

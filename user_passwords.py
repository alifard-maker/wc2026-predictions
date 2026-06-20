"""Per-user passwords for human pool members.

All human players must set a password; synced AI agents and media pundits are exempt.
Set PASSWORD_REQUIRED=0 to disable (emergency rollback).
"""

from __future__ import annotations

import os
import re

from werkzeug.security import check_password_hash, generate_password_hash

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128


def passwords_enabled() -> bool:
    return os.environ.get("PASSWORD_REQUIRED", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def user_requires_password(
    display_name: str | None,
    ai_agent_key: str | None = None,
) -> bool:
    """True for human pool members who must authenticate with a password."""
    if not passwords_enabled():
        return False
    if not display_name:
        return False
    from ai_predictor import is_agent_badge

    return not is_agent_badge(display_name, ai_agent_key)


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

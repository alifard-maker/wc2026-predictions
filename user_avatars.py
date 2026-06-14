"""Pool member profile photos (stored beside the database on disk)."""

from __future__ import annotations

import io
import os
from pathlib import Path

from db import DB_PATH

MAX_AVATAR_BYTES = 2 * 1024 * 1024
AVATAR_PIXEL_SIZE = 128

AVATAR_DIR = Path(os.environ.get("UPLOADS_PATH", DB_PATH.parent / "uploads")) / "avatars"


def avatar_path(user_id: int) -> Path:
    return AVATAR_DIR / f"{user_id}.jpg"


def avatar_exists_for_user(user_id: int, photo_updated_at: str | None) -> bool:
    return bool(photo_updated_at) and avatar_exists(user_id)


def user_initial(display_name: str) -> str:
    for ch in (display_name or "").strip():
        if ch.isalnum():
            return ch.upper()
    return "?"


def avatar_exists(user_id: int) -> bool:
    return avatar_path(user_id).is_file()


def delete_avatar_file(user_id: int) -> None:
    path = avatar_path(user_id)
    if path.is_file():
        path.unlink()


def save_avatar(user_id: int, raw: bytes) -> str | None:
    """Resize and store a JPEG avatar. Returns None on success, or an error message."""
    if not raw:
        return "No image received."
    if len(raw) > MAX_AVATAR_BYTES:
        return "Photo must be 2 MB or smaller."

    try:
        from PIL import Image
    except ImportError:
        return "Image processing is not available on this server."

    try:
        img = Image.open(io.BytesIO(raw))
        img.load()
    except OSError:
        return "Could not read that image — use JPEG, PNG, WebP, or GIF."

    if img.format not in {"JPEG", "PNG", "WEBP", "GIF"}:
        return "Use a JPEG, PNG, WebP, or GIF photo."

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    else:
        img = img.convert("RGB")

    img.thumbnail((AVATAR_PIXEL_SIZE, AVATAR_PIXEL_SIZE), Image.Resampling.LANCZOS)

    AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    path = avatar_path(user_id)
    img.save(path, format="JPEG", quality=85, optimize=True)
    return None

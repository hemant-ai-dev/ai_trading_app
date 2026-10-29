"""Validate and shrink chat uploads. Images are not executed and not kept as original files."""

from __future__ import annotations

import base64
import io
from typing import Any

from PIL import Image, UnidentifiedImageError

ALLOWED = frozenset({"image/png", "image/jpeg", "image/jpg", "image/webp", "png", "jpeg", "jpg", "webp"})
MAX_BYTES = 6 * 1024 * 1024
MAX_SIDE = 1600
THUMB_SIDE = 480


class MediaError(ValueError):
    pass


def _kind(name: str | None, mime: str | None) -> str:
    mime = (mime or "").lower().split(";")[0].strip()
    ext = (name or "").rsplit(".", 1)[-1].lower() if name and "." in name else ""
    if mime in ("image/png",) or ext == "png":
        return "png"
    if mime in ("image/jpeg", "image/jpg") or ext in ("jpg", "jpeg"):
        return "jpeg"
    if mime in ("image/webp",) or ext == "webp":
        return "webp"
    return ""


def load_image(data: bytes, *, name: str | None = None, mime: str | None = None) -> tuple[Image.Image, dict[str, Any]]:
    if not data:
        raise MediaError("The attachment is empty.")
    if len(data) > MAX_BYTES:
        raise MediaError(f"Image is too large ({len(data) // 1024} KB). Maximum is {MAX_BYTES // 1024} KB.")
    kind = _kind(name, mime)
    if not kind:
        raise MediaError("Use PNG, JPG, or WEBP only. Other files are rejected.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise MediaError("That file is not a readable image (corrupt or unsupported).") from exc
    img = img.convert("RGB") if img.mode in ("RGBA", "P", "LA") else img.convert("RGB")
    w, h = img.size
    if max(w, h) > MAX_SIDE:
        img.thumbnail((MAX_SIDE, MAX_SIDE))
    meta = {
        "name": name or "upload",
        "original_bytes": len(data),
        "width": img.size[0],
        "height": img.size[1],
        "format": kind,
        "note": "Session preview only — originals are not stored as trading records.",
    }
    return img, meta


def jpeg_bytes(img: Image.Image, *, quality: int = 85) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def thumbnail_data_url(img: Image.Image) -> str:
    thumb = img.copy()
    thumb.thumbnail((THUMB_SIDE, THUMB_SIDE))
    raw = jpeg_bytes(thumb, quality=70)
    if len(raw) > 80_000:
        raw = jpeg_bytes(thumb, quality=45)
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode("ascii")

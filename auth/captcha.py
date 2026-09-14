"""Six-character alphanumeric CAPTCHA for login and signup."""

from __future__ import annotations

import html
import random
import string

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_captcha_text(length: int = 6) -> str:
    rng = random.SystemRandom()
    letters = [rng.choice(string.ascii_uppercase.replace("O", "").replace("I", "")) for _ in range(3)]
    digits = [rng.choice("23456789") for _ in range(3)]
    chars = letters + digits
    rng.shuffle(chars)
    while len(chars) < length:
        chars.append(rng.choice(_ALPHABET))
    return "".join(chars[:length])


def captcha_matches(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    a = "".join(ch for ch in provided.upper() if ch.isalnum())
    b = "".join(ch for ch in expected.upper() if ch.isalnum())
    return a == b and len(b) == 6


def captcha_svg(text: str) -> str:
    """Larger SVG so the code stays readable on phones."""
    rng = random.Random(text)
    glyphs = []
    for i, ch in enumerate(text):
        x = 28 + i * 42
        y = rng.randint(42, 58)
        rot = rng.randint(-14, 14)
        fill = rng.choice(["#7dd3fc", "#fbbf24", "#c4b5fd", "#34d399", "#fb7185", "#f8fafc"])
        safe = html.escape(ch)
        glyphs.append(
            f'<text x="{x}" y="{y}" fill="{fill}" font-size="36" '
            f'font-family="Courier New, ui-monospace, monospace" font-weight="700" '
            f'transform="rotate({rot} {x} {y})">{safe}</text>'
        )
    lines = []
    for _ in range(4):
        x1, y1 = rng.randint(0, 50), rng.randint(12, 68)
        x2, y2 = rng.randint(220, 280), rng.randint(12, 68)
        color = rng.choice(["#334155", "#475569", "#1e293b"])
        lines.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.2"/>'
        )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="290" height="76" viewBox="0 0 290 76" '
        'role="img" aria-label="CAPTCHA" style="max-width:100%;height:auto">'
        '<rect width="290" height="76" rx="10" fill="#0f172a"/>'
        + "".join(lines)
        + "".join(glyphs)
        + "</svg>"
    )

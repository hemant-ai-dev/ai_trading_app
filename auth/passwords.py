"""bcrypt password hashing — original passwords are never stored or recoverable."""

from __future__ import annotations

import hmac
import hashlib
import re

import bcrypt

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))
    return hashed.decode("ascii")


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    raw = stored.encode("ascii") if isinstance(stored, str) else stored
    if stored.startswith("$2"):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), raw)
        except ValueError:
            return False
    # Legacy PBKDF2 hashes (if a row was migrated); still never reversible.
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, iter_s, salt_hex, digest_hex = stored.split("$", 3)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                bytes.fromhex(salt_hex),
                int(iter_s),
            )
            return hmac.compare_digest(candidate, bytes.fromhex(digest_hex))
        except (ValueError, TypeError):
            return False
    return False


def validate_signup(username: str, email: str, password: str) -> str | None:
    username = (username or "").strip()
    email = (email or "").strip()
    if not USERNAME_RE.match(username):
        return "Username must be 3–32 characters (letters, numbers, . _ -)."
    if not EMAIL_RE.match(email):
        return "Enter a valid email address."
    strength = validate_password_strength(password, username, email)
    if strength:
        return strength
    return None


def validate_password_strength(password: str, username: str = "", email: str = "") -> str | None:
    if len(password) < 8:
        return "Password must be at least 8 characters."
    if not re.search(r"[A-Za-z]", password) or not re.search(r"[0-9]", password):
        return "Password must include at least one letter and one number."
    if username and password.lower() == username.lower():
        return "Password cannot match your username or email."
    if email and password.lower() == email.lower():
        return "Password cannot match your username or email."
    return None

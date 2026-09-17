"""Excel workbook user store. Passwords are hashed; never stored in plain text."""

from __future__ import annotations

import os
import time
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from utils.logging import get_logger

logger = get_logger(__name__)

COLUMNS = [
    "UserId",
    "Username",
    "Email",
    "PasswordHash",
    "Role",
    "IsActive",
    "MustChangePassword",
    "CreatedAt",
    "UpdatedAt",
    "LastLoginAt",
    "ResetPending",
]

_lock = threading.Lock()
_memory: list[dict[str, Any]] | None = None
_active_path: Path | None = None


def workbook_path() -> Path:
    if _active_path is not None:
        return _active_path
    raw = os.getenv("ANGAD_USERS_XLSX")
    if raw:
        path = Path(raw)
    else:
        path = Path(__file__).resolve().parent.parent / "data" / "users.xlsx"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=COLUMNS)


def _normalize(df: pd.DataFrame) -> pd.DataFrame:
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = 0 if col in ("IsActive", "MustChangePassword", "ResetPending", "UserId") else ""
    df = df[COLUMNS]
    if df.empty:
        return df
    df["UserId"] = pd.to_numeric(df["UserId"], errors="coerce").fillna(0).astype(int)
    df["IsActive"] = pd.to_numeric(df["IsActive"], errors="coerce").fillna(1).astype(int)
    df["MustChangePassword"] = pd.to_numeric(df["MustChangePassword"], errors="coerce").fillna(0).astype(int)
    df["ResetPending"] = pd.to_numeric(df["ResetPending"], errors="coerce").fillna(0).astype(int)
    for col in ("Username", "Email", "PasswordHash", "Role", "CreatedAt", "UpdatedAt", "LastLoginAt"):
        df[col] = df[col].fillna("").astype(str)
        df[col] = df[col].replace({"nan": "", "None": "", "NaT": ""})
    df["Email"] = df["Email"].str.strip().str.lower()
    df["Username"] = df["Username"].str.strip()
    return df


def _read() -> pd.DataFrame:
    global _memory
    path = workbook_path()
    if not path.is_file():
        df = _empty()
        _memory = []
        try:
            _write(df)
        except OSError as exc:
            logger.warning("Could not create user workbook yet: %s", exc)
        return df
    try:
        df = _normalize(pd.read_excel(path, engine="openpyxl"))
        _memory = df.to_dict(orient="records") if not df.empty else []
        return df
    except OSError as exc:
        logger.warning("Could not read %s (%s); using in-memory users if available.", path, exc)
        if _memory is not None:
            return pd.DataFrame(_memory, columns=COLUMNS) if _memory else _empty()
        raise PermissionError(
            f"Cannot open {path}. Close it in Excel if it is open, then try again."
        ) from exc


def _write(df: pd.DataFrame) -> None:
    global _active_path, _memory
    path = workbook_path()
    out = df[COLUMNS] if not df.empty else _empty()
    _memory = out.to_dict(orient="records") if not out.empty else []
    tmp = path.with_name(path.stem + ".tmp.xlsx")
    last_exc: OSError | None = None
    for attempt in range(8):
        try:
            out.to_excel(tmp, index=False, engine="openpyxl")
            os.replace(tmp, path)
            return
        except OSError as exc:
            last_exc = exc
            time.sleep(0.15 * (attempt + 1))
            try:
                if tmp.exists():
                    tmp.unlink(missing_ok=True)
            except OSError:
                pass
    fallback = path.with_name("users_runtime.xlsx")
    try:
        out.to_excel(fallback, index=False, engine="openpyxl")
        _active_path = fallback
        logger.warning(
            "Could not write %s (%s). Using %s for this session. Close Excel if the original file is open.",
            path,
            last_exc,
            fallback,
        )
        return
    except OSError:
        logger.warning("User workbook is locked; keeping accounts in memory for this session only.")
        if last_exc and _memory is None:
            raise last_exc


def load_rows() -> list[dict[str, Any]]:
    with _lock:
        df = _read()
    if df.empty:
        return list(_memory or [])
    return df.to_dict(orient="records")


def save_rows(rows: list[dict[str, Any]]) -> None:
    with _lock:
        df = pd.DataFrame(rows, columns=COLUMNS) if rows else _empty()
        _write(df)


def find_user(identifier: str) -> dict[str, Any] | None:
    ident = (identifier or "").strip()
    if not ident:
        return None
    ident_l = ident.lower()
    for row in load_rows():
        if str(row.get("Username", "")).lower() == ident_l or str(row.get("Email", "")).lower() == ident_l:
            return dict(row)
    return None


def find_by_id(user_id: int) -> dict[str, Any] | None:
    for row in load_rows():
        if int(row.get("UserId") or 0) == int(user_id):
            return dict(row)
    return None


def upsert_user(row: dict[str, Any]) -> dict[str, Any]:
    rows = load_rows()
    uid = int(row.get("UserId") or 0)
    now = _now()
    if uid:
        replaced = False
        for i, existing in enumerate(rows):
            if int(existing.get("UserId") or 0) == uid:
                existing.update(row)
                existing["UpdatedAt"] = now
                rows[i] = existing
                replaced = True
                saved = existing
                break
        if not replaced:
            row["CreatedAt"] = row.get("CreatedAt") or now
            row["UpdatedAt"] = now
            rows.append(row)
            saved = row
    else:
        next_id = max((int(r.get("UserId") or 0) for r in rows), default=0) + 1
        row["UserId"] = next_id
        row["CreatedAt"] = now
        row["UpdatedAt"] = now
        rows.append(row)
        saved = row
    save_rows(rows)
    return dict(saved)


def count_users() -> int:
    return len(load_rows())


def count_admins() -> int:
    return sum(1 for r in load_rows() if str(r.get("Role")) == "Admin")

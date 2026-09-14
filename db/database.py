"""SQLite connection helpers. No SQL Server dependency."""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from utils.logging import get_logger

logger = get_logger(__name__)

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "storage" / "trading_tool.db"


class DatabaseError(Exception):
    """Raised when SQLite cannot be opened or a statement fails."""


def db_path() -> Path:
    raw = os.getenv("ANGAD_SQLITE_PATH")
    if not raw:
        try:
            import streamlit as st

            secrets = getattr(st, "secrets", None)
            if secrets is not None:
                sqlite = secrets.get("sqlite") if hasattr(secrets, "get") else None
                if isinstance(sqlite, dict) and sqlite.get("path"):
                    raw = str(sqlite["path"])
        except Exception:
            raw = None
    path = Path(raw) if raw else DEFAULT_DB_PATH
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def connect(*, readonly: bool = False) -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    uri = path.as_uri()
    try:
        if readonly and path.exists():
            cn = sqlite3.connect(f"{uri}?mode=ro", uri=True, timeout=15)
        else:
            cn = sqlite3.connect(str(path), timeout=15)
    except sqlite3.Error as exc:
        raise DatabaseError(f"Cannot open SQLite database at {path}: {exc}") from exc
    cn.row_factory = sqlite3.Row
    cn.execute("PRAGMA foreign_keys = ON")
    cn.execute("PRAGMA journal_mode = WAL")
    return cn


@contextmanager
def get_connection(*, commit: bool = True) -> Iterator[sqlite3.Connection]:
    cn = connect()
    try:
        yield cn
        if commit:
            cn.commit()
    except DatabaseError:
        cn.rollback()
        raise
    except sqlite3.Error as exc:
        cn.rollback()
        raise DatabaseError(str(exc)) from exc
    except Exception:
        cn.rollback()
        raise
    finally:
        cn.close()


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with get_connection(commit=False) as cn:
        cur = cn.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params: tuple = ()) -> int:
    with get_connection(commit=True) as cn:
        cur = cn.execute(sql, params)
        return int(cur.lastrowid or 0)

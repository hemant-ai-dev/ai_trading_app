"""Load all API keys and app settings from SQL Server (single source of truth)."""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from db.sql_store import SqlStore


def _set_nested(cfg: dict, dotted_key: str, value: str) -> None:
    """Map llm.openai.api_key → cfg['llm']['openai']['api_key']."""
    parts = dotted_key.split(".")
    cur = cfg
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value


def _parse_value(raw: str):
    if raw is None:
        return None
    s = str(raw).strip()
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        if "." in s:
            return float(s)
        return int(s)
    except ValueError:
        pass
    if s.startswith("[") or s.startswith("{"):
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
    return s


class SqlConfigLoader:
    def __init__(self, store: SqlStore | None = None) -> None:
        self._store = store

    def _store_instance(self) -> SqlStore:
        if self._store is None:
            from config.loader import load_bootstrap_config

            self._store = SqlStore(load_bootstrap_config())
        return self._store

    def ensure_tables(self) -> None:
        store = self._store_instance()
        store.ensure_database()
        conn = store._open_connection()
        cur = conn.cursor()
        cur.execute(
            """
            IF OBJECT_ID('dbo.api_providers', 'U') IS NULL
            CREATE TABLE dbo.api_providers (
                provider_id INT IDENTITY(1,1) PRIMARY KEY,
                provider_code NVARCHAR(64) NOT NULL UNIQUE,
                display_name NVARCHAR(128) NOT NULL,
                provider_type NVARCHAR(32) NOT NULL,
                is_enabled BIT NOT NULL DEFAULT 1,
                description NVARCHAR(512) NULL,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );

            IF OBJECT_ID('dbo.api_config', 'U') IS NULL
            CREATE TABLE dbo.api_config (
                config_id INT IDENTITY(1,1) PRIMARY KEY,
                provider_code NVARCHAR(64) NOT NULL,
                config_key NVARCHAR(128) NOT NULL,
                config_value NVARCHAR(MAX) NULL,
                is_secret BIT NOT NULL DEFAULT 0,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_api_cfg UNIQUE (provider_code, config_key)
            );

            IF OBJECT_ID('dbo.app_settings', 'U') IS NULL
            CREATE TABLE dbo.app_settings (
                setting_key NVARCHAR(128) PRIMARY KEY,
                setting_value NVARCHAR(MAX) NULL,
                category NVARCHAR(64) NULL,
                description NVARCHAR(512) NULL,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
            """
        )
        conn.commit()
        cur.close()
        conn.close()

    def load_flat(self) -> dict[str, str]:
        self.ensure_tables()
        store = self._store_instance()
        conn = store._open_connection()
        cur = conn.cursor()
        out: dict[str, str] = {}

        cur.execute(
            """
            SELECT p.provider_code, c.config_key, c.config_value
            FROM dbo.api_config c
            INNER JOIN dbo.api_providers p ON p.provider_code = c.provider_code
            WHERE p.is_enabled = 1
            """
        )
        for pcode, ckey, cval in cur.fetchall():
            if cval is not None:
                out[f"{pcode}.{ckey}"] = str(cval)

        cur.execute(
            "SELECT setting_key, setting_value FROM dbo.app_settings WHERE setting_value IS NOT NULL"
        )
        for skey, sval in cur.fetchall():
            out[str(skey)] = str(sval)

        cur.close()
        conn.close()
        return out

    def merge_into_settings(self, base: dict[str, Any]) -> dict[str, Any]:
        cfg = deepcopy(base)
        flat = self.load_flat()

        # Provider-level keys → nested settings
        mapping = {
            "openai": "llm.openai",
            "yfinance": "market_data.yfinance",
            "yahoo_rss": "news.yahoo_rss",
        }
        for full_key, val in flat.items():
            if "." not in full_key:
                _set_nested(cfg, full_key, _parse_value(val))
                continue
            pcode, rest = full_key.split(".", 1)
            prefix = mapping.get(pcode)
            if prefix:
                _set_nested(cfg, f"{prefix}.{rest}", _parse_value(val))
            else:
                _set_nested(cfg, full_key, _parse_value(val))

        return cfg

    def health(self) -> dict[str, Any]:
        try:
            flat = self.load_flat()
            store = self._store_instance()
            return {
                "ok": True,
                "database": store.database,
                "config_keys": len(flat),
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def upsert_config(self, provider_code: str, config_key: str, value: str, is_secret: bool = False) -> None:
        self.ensure_tables()
        store = self._store_instance()
        conn = store._open_connection()
        cur = conn.cursor()
        cur.execute(
            """
            MERGE dbo.api_config AS t
            USING (SELECT ? AS provider_code, ? AS config_key) AS s
            ON t.provider_code = s.provider_code AND t.config_key = s.config_key
            WHEN MATCHED THEN UPDATE SET config_value = ?, is_secret = ?, updated_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (provider_code, config_key, config_value, is_secret)
                VALUES (?, ?, ?, ?);
            """,
            (provider_code, config_key, value, 1 if is_secret else 0, provider_code, config_key, value, 1 if is_secret else 0),
        )
        conn.commit()
        cur.close()
        conn.close()


def clear_settings_cache() -> None:
    from config.loader import load_settings

    load_settings.cache_clear()

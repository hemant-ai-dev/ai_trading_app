"""Bootstrap from JSON files; all API keys and app settings from SQL Server."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from functools import lru_cache
from pathlib import Path

_CONFIG_ROOT = Path(__file__).resolve().parent


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if k.startswith("_"):
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=2)
def load_bootstrap_config(config_path: str | None = None) -> dict:
    """
    Minimal JSON: defaults + local.json (SQL connection only recommended in local).
    No API secrets required in files when SQL is seeded.
    """
    cfg = _load_json(_CONFIG_ROOT / "defaults.json")
    cfg = _deep_merge(cfg, _load_json(_CONFIG_ROOT / "local.json"))

    extra = config_path or os.getenv("TRADING_CONFIG_PATH")
    if extra:
        p = Path(extra)
        if not p.is_absolute():
            p = Path.cwd() / p
        cfg = _deep_merge(cfg, _load_json(p))

    return cfg


@lru_cache(maxsize=2)
def load_settings(config_path: str | None = None) -> dict:
    """
    Full settings: bootstrap JSON + SQL api_config + app_settings tables.
    Change APIs only in SQL after seeding (see scripts/seed_sql_apis.py).
    """
    cfg = load_bootstrap_config(config_path)
    try:
        from db.sql_config import SqlConfigLoader
        from db.sql_store import SqlStore

        cfg = SqlConfigLoader(SqlStore(cfg)).merge_into_settings(cfg)
    except Exception:
        pass  # deployment without SQL falls back to JSON only

    if prov := os.getenv("TRADING_LLM_PROVIDER"):
        cfg.setdefault("llm", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_MARKET_DATA_PROVIDER"):
        cfg.setdefault("market_data", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_NEWS_PROVIDER"):
        cfg.setdefault("news", {})["provider"] = prov.strip()

    return cfg


def get_settings() -> dict:
    return load_settings()


def reload_settings() -> dict:
    load_bootstrap_config.cache_clear()
    load_settings.cache_clear()
    try:
        from db.sql_config import clear_settings_cache

        clear_settings_cache()
    except Exception:
        pass
    return load_settings()

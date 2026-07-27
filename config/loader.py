"""Bootstrap settings from JSON files and environment variables."""

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


def _apply_env_overrides(cfg: dict) -> dict:
    """Apply environment variable overrides for secrets and providers."""
    if key := os.getenv("OPENAI_API_KEY"):
        cfg.setdefault("llm", {}).setdefault("openai", {})["api_key"] = key.strip()
    if prov := os.getenv("TRADING_LLM_PROVIDER"):
        cfg.setdefault("llm", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_MARKET_DATA_PROVIDER"):
        cfg.setdefault("market_data", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_NEWS_PROVIDER"):
        cfg.setdefault("news", {})["provider"] = prov.strip()
    return cfg


@lru_cache(maxsize=2)
def load_settings(config_path: str | None = None) -> dict:
    """Load application settings from defaults.json, local.json, and environment."""
    cfg = _load_json(_CONFIG_ROOT / "defaults.json")
    cfg = _deep_merge(cfg, _load_json(_CONFIG_ROOT / "local.json"))

    extra = config_path or os.getenv("TRADING_CONFIG_PATH")
    if extra:
        p = Path(extra)
        if not p.is_absolute():
            p = Path.cwd() / p
        cfg = _deep_merge(cfg, _load_json(p))

    return _apply_env_overrides(cfg)


def get_settings() -> dict:
    return load_settings()


def reload_settings() -> dict:
    load_settings.cache_clear()
    return load_settings()

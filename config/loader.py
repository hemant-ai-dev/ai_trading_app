"""Load merged configuration: defaults.json + optional local.json + env overrides."""

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


@lru_cache(maxsize=4)
def load_settings(config_path: str | None = None) -> dict:
    """
    Merge order: config/defaults.json < config/local.json < optional path from TRADING_CONFIG_PATH < TRADING_* flat overrides.

    Env:
      TRADING_CONFIG_PATH - absolute or relative path to an extra JSON file merged last (for CI/deploy).
      TRADING_LLM_PROVIDER - e.g. openai
      TRADING_MARKET_DATA_PROVIDER - e.g. yfinance
      TRADING_NEWS_PROVIDER - e.g. yahoo_rss
    """
    defaults_path = _CONFIG_ROOT / "defaults.json"
    local_path = _CONFIG_ROOT / "local.json"

    cfg = _load_json(defaults_path)
    cfg = _deep_merge(cfg, _load_json(local_path))

    extra = config_path or os.getenv("TRADING_CONFIG_PATH")
    if extra:
        p = Path(extra)
        if not p.is_absolute():
            p = Path.cwd() / p
        cfg = _deep_merge(cfg, _load_json(p))

    if prov := os.getenv("TRADING_LLM_PROVIDER"):
        cfg.setdefault("llm", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_MARKET_DATA_PROVIDER"):
        cfg.setdefault("market_data", {})["provider"] = prov.strip()
    if prov := os.getenv("TRADING_NEWS_PROVIDER"):
        cfg.setdefault("news", {})["provider"] = prov.strip()

    return cfg


def get_settings() -> dict:
    """Non-cached alias if you need reload after editing files (restart Streamlit)."""
    return load_settings()

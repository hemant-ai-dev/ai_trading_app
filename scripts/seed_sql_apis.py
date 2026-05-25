"""Seed api_providers, api_config, app_settings from defaults + local.json."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config.loader import load_bootstrap_config
from db.sql_config import SqlConfigLoader
from db.sql_store import SqlStore

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = json.loads((ROOT / "config" / "defaults.json").read_text(encoding="utf-8"))
LOCAL = {}
local_path = ROOT / "config" / "local.json"
if local_path.is_file():
    LOCAL = json.loads(local_path.read_text(encoding="utf-8"))


def main():
    cfg = load_bootstrap_config()
    store = SqlStore(cfg)
    loader = SqlConfigLoader(store)
    loader.ensure_tables()

    conn = store._open_connection()
    cur = conn.cursor()

    providers = [
        ("openai", "OpenAI LLM", "llm", "Gen AI brain — set api_key in api_config"),
        ("yfinance", "Yahoo Finance", "market_data", "Live OHLCV market data"),
        ("yahoo_rss", "Yahoo RSS News", "news", "Headlines for Gen AI context"),
    ]
    for code, name, ptype, desc in providers:
        cur.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM dbo.api_providers WHERE provider_code = ?)
            INSERT INTO dbo.api_providers (provider_code, display_name, provider_type, description)
            VALUES (?, ?, ?, ?)
            """,
            (code, code, name, ptype, desc),
        )

    conn.commit()

    openai = DEFAULTS.get("llm", {}).get("openai", {})
    local_openai = LOCAL.get("llm", {}).get("openai", {})
    api_key = local_openai.get("api_key") or ""

    configs = [
        ("openai", "api_key", api_key, True),
        ("openai", "base_url", openai.get("base_url") or "", False),
        ("openai", "model_chat", openai.get("model_chat", "gpt-4o-mini"), False),
        ("openai", "model_json", openai.get("model_json", "gpt-4o-mini"), False),
        ("openai", "max_tokens_genai_predict", str(openai.get("max_tokens_genai_predict", 2800)), False),
        ("openai", "temperature_genai_predict", str(openai.get("temperature_genai_predict", 0.45)), False),
        ("openai", "max_tokens_json", str(openai.get("max_tokens_json", 2400)), False),
        ("openai", "temperature_json", str(openai.get("temperature_json", 0.35)), False),
        ("yfinance", "cache_ttl_seconds", str(DEFAULTS.get("market_data", {}).get("yfinance", {}).get("cache_ttl_seconds", 25)), False),
        ("yfinance", "auto_adjust", "true", False),
        ("yahoo_rss", "intel_cache_ttl_seconds", str(DEFAULTS.get("news", {}).get("yahoo_rss", {}).get("intel_cache_ttl_seconds", 600)), False),
        ("yahoo_rss", "rss_max_items_per_feed", str(DEFAULTS.get("news", {}).get("yahoo_rss", {}).get("rss_max_items_per_feed", 4)), False),
    ]
    for pcode, key, val, secret in configs:
        if val is None:
            val = ""
        loader.upsert_config(pcode, key, str(val), is_secret=secret)

    app_rows = [
        ("app.title", DEFAULTS.get("app", {}).get("title", "Angad Gen AI Desk"), "app"),
        ("app.auto_refresh_seconds", "60", "app"),
        ("llm.provider", DEFAULTS.get("llm", {}).get("provider", "openai"), "llm"),
        ("market_data.provider", DEFAULTS.get("market_data", {}).get("provider", "yfinance"), "market_data"),
        ("news.provider", DEFAULTS.get("news", {}).get("provider", "yahoo_rss"), "news"),
    ]
    for key, val, cat in app_rows:
        cur.execute(
            """
            MERGE dbo.app_settings AS t
            USING (SELECT ? AS setting_key) AS s
            ON t.setting_key = s.setting_key
            WHEN MATCHED THEN UPDATE SET setting_value = ?, category = ?, updated_at = SYSUTCDATETIME()
            WHEN NOT MATCHED THEN INSERT (setting_key, setting_value, category) VALUES (?, ?, ?);
            """,
            (key, val, cat, key, val, cat),
        )

    conn.commit()
    cur.close()
    conn.close()
    print("OK: Seeded api_providers, api_config, app_settings.")
    print("Edit OPENAI key: UPDATE api_config SET config_value='your-key' WHERE provider_code='openai' AND config_key='api_key'")


if __name__ == "__main__":
    main()

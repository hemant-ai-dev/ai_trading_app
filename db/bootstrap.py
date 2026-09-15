"""Create SQLite tables if missing and seed the free-API catalog. Never drops data."""

from __future__ import annotations

from db.database import DatabaseError, db_path, get_connection
from db.schema import API_SEED, SCHEMA_STATEMENTS
from utils.logging import get_logger

logger = get_logger(__name__)
SCHEMA_VERSION = 2


def initialize() -> None:
    path = db_path()
    logger.info("Initializing SQLite at %s", path)
    try:
        with get_connection(commit=True) as cn:
            for stmt in SCHEMA_STATEMENTS:
                cn.execute(stmt)
            cn.execute(
                "INSERT OR IGNORE INTO TSchemaVersion (Version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            cn.executemany(
                """
                INSERT OR IGNORE INTO TApiProvider (
                    ApiCode, ApiName, Purpose, Category, Endpoint, IsFree,
                    PricingNote, FreeUsageLimit, RequiresApiKey, IsEnabled,
                    FallbackApiCode, SortOrder
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                API_SEED,
            )
    except DatabaseError:
        raise
    except Exception as exc:
        raise DatabaseError(f"Failed to initialize SQLite schema: {exc}") from exc

"""Create SQLite tables if missing and seed the free-API catalog. Never drops data."""

from __future__ import annotations

from db.database import DatabaseError, db_path, get_connection
from db.schema import API_SEED, SCHEMA_STATEMENTS
from utils.logging import get_logger

logger = get_logger(__name__)
SCHEMA_VERSION = 3


def _ensure_column(cn, table: str, column: str, ddl: str) -> None:
    names = [row[1] for row in cn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in names:
        cn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def initialize() -> None:
    path = db_path()
    logger.info("Initializing SQLite at %s", path)
    try:
        with get_connection(commit=True) as cn:
            for stmt in SCHEMA_STATEMENTS:
                cn.execute(stmt)
            _ensure_column(cn, "TApiProvider", "ApiType", "ApiType TEXT NOT NULL DEFAULT 'external'")
            _ensure_column(cn, "TChatMessage", "ConversationId", "ConversationId TEXT DEFAULT 'desk'")
            _ensure_column(cn, "TChatMessage", "ToolsJson", "ToolsJson TEXT")
            _ensure_column(cn, "TChatMessage", "CitationsJson", "CitationsJson TEXT")
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
            cn.execute(
                "UPDATE TApiProvider SET ApiType = 'internal' WHERE ApiCode IN ('angad_internal', 'angad_knowledge', 'local_ta')"
            )
            cn.execute(
                "UPDATE TApiProvider SET ApiType = 'external' WHERE ApiType IS NULL OR ApiType = ''"
            )
    except DatabaseError:
        raise
    except Exception as exc:
        raise DatabaseError(f"Failed to initialize SQLite schema: {exc}") from exc

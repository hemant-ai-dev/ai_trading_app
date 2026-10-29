"""Create SQLite tables if missing and seed the free-API catalog. Never drops data."""

from __future__ import annotations

from db.database import DatabaseError, db_path, get_connection
from db.schema import API_SEED, SCHEMA_STATEMENTS
from utils.logging import get_logger

logger = get_logger(__name__)
SCHEMA_VERSION = 6


def _ensure_column(cn, table: str, column: str, ddl: str) -> None:
    names = [row[1] for row in cn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in names:
        cn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


_PREDICTION_MIGRATIONS = [
    ("Timeframe", "Timeframe TEXT NOT NULL DEFAULT '1d'"),
    ("TargetTime", "TargetTime TEXT"),
    ("Status", "Status TEXT NOT NULL DEFAULT 'pending'"),
    ("ModelVersion", "ModelVersion TEXT"),
    ("ProbUp", "ProbUp REAL"),
    ("ProbSideways", "ProbSideways REAL"),
    ("ProbDown", "ProbDown REAL"),
    ("SignedError", "SignedError REAL"),
    ("AbsError", "AbsError REAL"),
    ("ErrorPct", "ErrorPct REAL"),
    ("DirectionOk", "DirectionOk INTEGER"),
    ("RangeOk", "RangeOk INTEGER"),
    ("ActualTime", "ActualTime TEXT"),
    ("ActualHigh", "ActualHigh REAL"),
    ("ActualLow", "ActualLow REAL"),
    ("EvaluatedAt", "EvaluatedAt TEXT"),
    ("ScheduledKey", "ScheduledKey TEXT"),
]

_OPTION_PREDICTION_MIGRATIONS = [
    ("TargetTime", "TargetTime TEXT"),
    ("Status", "Status TEXT NOT NULL DEFAULT 'pending'"),
    ("AbsError", "AbsError REAL"),
    ("ErrorPct", "ErrorPct REAL"),
    ("DirectionOk", "DirectionOk INTEGER"),
    ("ActualUnderlying", "ActualUnderlying REAL"),
    ("EvaluatedAt", "EvaluatedAt TEXT"),
]


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
            for column, ddl in _PREDICTION_MIGRATIONS:
                _ensure_column(cn, "TPrediction", column, ddl)
            for column, ddl in _OPTION_PREDICTION_MIGRATIONS:
                _ensure_column(cn, "TOptionPrediction", column, ddl)
            cn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS UX_TPrediction_ScheduledKey "
                "ON TPrediction (ScheduledKey) WHERE ScheduledKey IS NOT NULL"
            )
            cn.execute(
                "CREATE INDEX IF NOT EXISTS IX_TPrediction_DueEval "
                "ON TPrediction (Symbol, Status, TargetTime)"
            )
            cn.execute(
                "CREATE INDEX IF NOT EXISTS IX_TOptionPrediction_Due "
                "ON TOptionPrediction (Underlying, Status, TargetTime)"
            )
            # Legacy rows already carrying an actual price are treated as evaluated.
            cn.execute(
                "UPDATE TPrediction SET Status = 'evaluated' "
                "WHERE ActualPrice IS NOT NULL AND (Status IS NULL OR Status = 'pending')"
            )
            cn.execute(
                "INSERT OR IGNORE INTO TSchemaVersion (Version) VALUES (?)",
                (SCHEMA_VERSION,),
            )
            cn.execute(
                """
                INSERT OR IGNORE INTO TModelVersion (ModelVersion, Description, ConfigJson, Status)
                VALUES (
                    'angad-horizon-v1',
                    'ATR sqrt-time drift with uncalibrated up/sideways/down scores. Not auto-promoted.',
                    '{"drift":"0.5*sigma*score/6","band":"1.2816*sigma","prob_source":"score_derived_uncalibrated","min_bars":40}',
                    'active'
                )
                """
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

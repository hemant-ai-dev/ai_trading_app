"""Record outbound free-API calls in SQLite."""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from db.bootstrap import initialize
from db.database import DatabaseError, fetch_all, fetch_one, get_connection
from utils.logging import get_logger

logger = get_logger(__name__)

NOT_PROVIDED = "Not provided by API"


def _api_id(code: str) -> int | None:
    initialize()
    row = fetch_one("SELECT ApiId FROM TApiProvider WHERE ApiCode = ?", (code,))
    return int(row["ApiId"]) if row else None


def log_usage(
    api_code: str,
    *,
    operation: str,
    success: bool,
    endpoint: str | None = None,
    http_status: int | None = None,
    response_ms: int | None = None,
    error: str | None = None,
    rate_limit_remaining: str | None = None,
    quota_remaining: str | None = None,
) -> None:
    quota = quota_remaining or NOT_PROVIDED
    remaining = rate_limit_remaining or NOT_PROVIDED
    err = (error or "")[:1000] or None
    try:
        api_id = _api_id(api_code)
        if api_id is None:
            return
        with get_connection() as cn:
            cn.execute(
                """
                INSERT INTO TApiUsageLog (
                    ApiId, Endpoint, Operation, Success, HttpStatus, ResponseMs,
                    ErrorMessage, RateLimitRemaining, QuotaRemaining
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    api_id,
                    (endpoint or "")[:400],
                    operation[:80],
                    1 if success else 0,
                    http_status,
                    response_ms,
                    err,
                    remaining[:80],
                    quota[:80],
                ),
            )
            today = cn.execute("SELECT strftime('%Y-%m-%d', 'now') AS d").fetchone()["d"]
            now = cn.execute("SELECT strftime('%Y-%m-%dT%H:%M:%fZ', 'now') AS t").fetchone()["t"]
            row = cn.execute(
                "SELECT ApiId FROM TApiDailyUsage WHERE ApiId = ? AND UsageDate = ?",
                (api_id, today),
            ).fetchone()
            if row:
                if success:
                    cn.execute(
                        """
                        UPDATE TApiDailyUsage
                        SET SuccessCount = SuccessCount + 1,
                            LastSuccessUtc = ?,
                            LastHttpStatus = ?
                        WHERE ApiId = ? AND UsageDate = ?
                        """,
                        (now, http_status, api_id, today),
                    )
                else:
                    cn.execute(
                        """
                        UPDATE TApiDailyUsage
                        SET FailureCount = FailureCount + 1,
                            LastFailureUtc = ?,
                            LastError = ?,
                            LastHttpStatus = ?
                        WHERE ApiId = ? AND UsageDate = ?
                        """,
                        (now, err, http_status, api_id, today),
                    )
            else:
                cn.execute(
                    """
                    INSERT INTO TApiDailyUsage (
                        ApiId, UsageDate, SuccessCount, FailureCount,
                        LastSuccessUtc, LastFailureUtc, LastError, LastHttpStatus
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        api_id,
                        today,
                        1 if success else 0,
                        0 if success else 1,
                        now if success else None,
                        None if success else now,
                        None if success else err,
                        http_status,
                    ),
                )
    except DatabaseError as exc:
        logger.warning("Could not persist API usage for %s: %s", api_code, exc)


@contextmanager
def track_call(api_code: str, operation: str, endpoint: str | None = None) -> Iterator[dict[str, Any]]:
    meta: dict[str, Any] = {
        "success": False,
        "http_status": None,
        "error": None,
        "endpoint": endpoint,
    }
    t0 = time.perf_counter()
    try:
        yield meta
        if meta.get("success") is False and meta.get("error") is None:
            meta["success"] = True
    except Exception as exc:
        meta["success"] = False
        meta["error"] = str(exc)[:1000]
        raise
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        log_usage(
            api_code,
            operation=operation,
            success=bool(meta.get("success")),
            endpoint=str(meta.get("endpoint") or endpoint or ""),
            http_status=meta.get("http_status"),
            response_ms=ms,
            error=meta.get("error"),
            rate_limit_remaining=meta.get("rate_limit_remaining") or NOT_PROVIDED,
            quota_remaining=meta.get("quota_remaining") or NOT_PROVIDED,
        )


def usage_summary() -> list[dict[str, Any]]:
    initialize()
    return fetch_all(
        """
        SELECT
            p.ApiId, p.ApiCode, p.ApiName, p.Purpose, p.Category, p.Endpoint,
            p.IsFree, p.PricingNote, p.FreeUsageLimit, p.RequiresApiKey, p.IsEnabled,
            p.FallbackApiCode,
            IFNULL(d.SuccessCount, 0) AS TodaySuccess,
            IFNULL(d.FailureCount, 0) AS TodayFailure,
            IFNULL(d.SuccessCount, 0) + IFNULL(d.FailureCount, 0) AS TodayUsage,
            d.LastSuccessUtc, d.LastFailureUtc, d.LastError, d.LastHttpStatus
        FROM TApiProvider p
        LEFT JOIN TApiDailyUsage d
            ON d.ApiId = p.ApiId AND d.UsageDate = strftime('%Y-%m-%d', 'now')
        ORDER BY p.SortOrder, p.ApiName
        """
    )


def usage_recent(api_code: str | None = None, take: int = 25) -> list[dict[str, Any]]:
    initialize()
    take = max(1, min(int(take), 200))
    if api_code:
        return fetch_all(
            """
            SELECT l.UsageId, p.ApiCode, p.ApiName, l.RequestUtc, l.Endpoint, l.Operation,
                   l.Success, l.HttpStatus, l.ResponseMs, l.ErrorMessage,
                   l.RateLimitRemaining, l.QuotaRemaining
            FROM TApiUsageLog l
            JOIN TApiProvider p ON p.ApiId = l.ApiId
            WHERE p.ApiCode = ?
            ORDER BY l.RequestUtc DESC
            LIMIT ?
            """,
            (api_code, take),
        )
    return fetch_all(
        """
        SELECT l.UsageId, p.ApiCode, p.ApiName, l.RequestUtc, l.Endpoint, l.Operation,
               l.Success, l.HttpStatus, l.ResponseMs, l.ErrorMessage,
               l.RateLimitRemaining, l.QuotaRemaining
        FROM TApiUsageLog l
        JOIN TApiProvider p ON p.ApiId = l.ApiId
        ORDER BY l.RequestUtc DESC
        LIMIT ?
        """,
        (take,),
    )


def set_provider_enabled(api_code: str, enabled: bool) -> None:
    with get_connection() as cn:
        cn.execute(
            """
            UPDATE TApiProvider
            SET IsEnabled = ?, UpdatedAt = strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            WHERE ApiCode = ?
            """,
            (1 if enabled else 0, api_code),
        )


def derive_status(row: dict[str, Any]) -> str:
    if not row.get("IsEnabled"):
        return "inactive"
    fails = int(row.get("TodayFailure") or 0)
    oks = int(row.get("TodaySuccess") or 0)
    if fails and not row.get("LastSuccessUtc") and oks == 0:
        return "failed"
    if row.get("LastError") and fails >= 3 and fails >= oks:
        return "failed"
    return "active"

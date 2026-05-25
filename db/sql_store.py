"""SQL Server — real-time bars, Gen AI + rule predictions, logic audit trail."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
import pyodbc

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_DB = "AngadTrading"
SOURCE_RULE = "RULE"
SOURCE_GENAI = "GENAI"


def _pick_driver() -> str:
    for name in ("ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server"):
        try:
            if name in pyodbc.drivers():
                return name
        except Exception:
            continue
    return "ODBC Driver 17 for SQL Server"


def _ts_ist_naive(ts) -> datetime:
    t = pd.Timestamp(ts)
    if t.tzinfo is not None:
        t = t.tz_convert(IST).tz_localize(None)
    else:
        t = t.tz_localize(IST).tz_convert(IST).tz_localize(None)
    return t.to_pydatetime()


class SqlStore:
    def __init__(self, cfg: dict | None = None) -> None:
        cfg = cfg or {}
        sql = cfg.get("database", {}).get("sql_server", {})
        self.server = sql.get("server") or os.getenv("SQL_SERVER", r"localhost\SQLEXPRESS")
        self.database = sql.get("database") or os.getenv("SQL_DATABASE", DEFAULT_DB)
        self.user = sql.get("username") or os.getenv("SQL_USER", "")
        self.password = sql.get("password") or os.getenv("SQL_PASSWORD", "")
        self.driver = sql.get("odbc_driver") or _pick_driver()
        self.enabled = bool(sql.get("enabled", True))
        self._ensured = False

    def _conn_str(self, database: str | None = None) -> str:
        db = database or self.database
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={db}",
            "TrustServerCertificate=yes",
        ]
        if self.user:
            parts.extend([f"UID={self.user}", f"PWD={self.password}"])
        else:
            parts.append("Trusted_Connection=yes")
        return ";".join(parts)

    def _connect(self, database: str | None = None):
        return pyodbc.connect(self._conn_str(database), timeout=15)

    def _open_connection(self):
        from config.loader import load_settings

        sql_cfg = load_settings().get("database", {}).get("sql_server", {})
        fallback = sql_cfg.get("fallback_database")
        try:
            return self._connect(self.database)
        except pyodbc.Error:
            if fallback and fallback != self.database:
                self.database = fallback
                return self._connect(self.database)
            raise

    def _migrate_column(self, cur, table: str, column: str, ddl: str) -> None:
        cur.execute(
            f"""
            IF NOT EXISTS (
                SELECT 1 FROM sys.columns
                WHERE object_id = OBJECT_ID('dbo.{table}') AND name = '{column}'
            )
            ALTER TABLE dbo.{table} ADD {ddl};
            """
        )

    def ensure_database(self) -> None:
        if not self.enabled or self._ensured:
            return
        try:
            master = self._connect("master")
            master.autocommit = True
            cur = master.cursor()
            cur.execute(
                f"""
                IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{self.database}')
                CREATE DATABASE [{self.database}];
                """
            )
            cur.close()
            master.close()
        except pyodbc.Error:
            pass

        conn = self._open_connection()
        cur = conn.cursor()

        cur.execute(
            """
            IF OBJECT_ID('dbo.prediction_runs', 'U') IS NULL
            CREATE TABLE dbo.prediction_runs (
                run_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                stock NVARCHAR(64) NOT NULL,
                run_time_ist DATETIME2 NOT NULL,
                source_type NVARCHAR(16) NOT NULL DEFAULT 'RULE',
                is_primary BIT NOT NULL DEFAULT 0,
                model_name NVARCHAR(64) NULL,
                signal NVARCHAR(16) NOT NULL,
                confidence_pct DECIMAL(6,2) NOT NULL,
                score DECIMAL(8,3) NULL,
                stop_loss DECIMAL(18,4) NULL,
                target_price DECIMAL(18,4) NULL,
                reason_tags NVARCHAR(MAX) NULL,
                market_phase NVARCHAR(32) NULL,
                period NVARCHAR(16) NULL,
                interval_label NVARCHAR(16) NULL,
                last_close DECIMAL(18,4) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );
            """
        )
        self._migrate_column(cur, "prediction_runs", "source_type", "source_type NVARCHAR(16) NOT NULL DEFAULT 'RULE'")
        self._migrate_column(cur, "prediction_runs", "is_primary", "is_primary BIT NOT NULL DEFAULT 0")
        self._migrate_column(cur, "prediction_runs", "model_name", "model_name NVARCHAR(64) NULL")

        cur.execute(
            """
            IF OBJECT_ID('dbo.prediction_points', 'U') IS NULL
            CREATE TABLE dbo.prediction_points (
                point_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                run_id BIGINT NOT NULL,
                stock NVARCHAR(64) NOT NULL,
                target_time_ist DATETIME2 NOT NULL,
                predicted_price DECIMAL(18,4) NOT NULL,
                sequence_no INT NOT NULL,
                CONSTRAINT FK_pp_run FOREIGN KEY (run_id) REFERENCES dbo.prediction_runs(run_id)
            );

            IF OBJECT_ID('dbo.market_bars', 'U') IS NULL
            CREATE TABLE dbo.market_bars (
                bar_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                stock NVARCHAR(64) NOT NULL,
                bar_time_ist DATETIME2 NOT NULL,
                open_price DECIMAL(18,4) NOT NULL,
                high_price DECIMAL(18,4) NOT NULL,
                low_price DECIMAL(18,4) NOT NULL,
                close_price DECIMAL(18,4) NOT NULL,
                volume BIGINT NULL,
                interval_label NVARCHAR(16) NULL,
                ingested_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_market_bars UNIQUE (stock, bar_time_ist, interval_label)
            );

            IF OBJECT_ID('dbo.live_bars', 'U') IS NULL
            CREATE TABLE dbo.live_bars (
                bar_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                stock NVARCHAR(64) NOT NULL,
                bar_time_ist DATETIME2 NOT NULL,
                close_price DECIMAL(18,4) NOT NULL,
                source NVARCHAR(32) NOT NULL DEFAULT 'yfinance',
                ingested_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT UQ_live_bars UNIQUE (stock, bar_time_ist)
            );

            IF OBJECT_ID('dbo.prediction_logic', 'U') IS NULL
            CREATE TABLE dbo.prediction_logic (
                logic_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                run_id BIGINT NOT NULL UNIQUE,
                stock NVARCHAR(64) NOT NULL,
                source_type NVARCHAR(16) NOT NULL,
                indicators_json NVARCHAR(MAX) NULL,
                rule_snapshot_json NVARCHAR(MAX) NULL,
                genai_input_json NVARCHAR(MAX) NULL,
                genai_output_json NVARCHAR(MAX) NULL,
                prompt_digest NVARCHAR(64) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_logic_run FOREIGN KEY (run_id) REFERENCES dbo.prediction_runs(run_id)
            );

            IF OBJECT_ID('dbo.genai_reasoning', 'U') IS NULL
            CREATE TABLE dbo.genai_reasoning (
                reasoning_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                run_id BIGINT NOT NULL UNIQUE,
                stock NVARCHAR(64) NOT NULL,
                market_read NVARCHAR(MAX) NULL,
                reasoning_steps_json NVARCHAR(MAX) NULL,
                news_cited_json NVARCHAR(MAX) NULL,
                risks NVARCHAR(MAX) NULL,
                limitations NVARCHAR(MAX) NULL,
                created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_reason_run FOREIGN KEY (run_id) REFERENCES dbo.prediction_runs(run_id)
            );

            IF OBJECT_ID('dbo.accuracy_evaluations', 'U') IS NULL
            CREATE TABLE dbo.accuracy_evaluations (
                eval_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                run_id BIGINT NOT NULL,
                point_id BIGINT NOT NULL,
                stock NVARCHAR(64) NOT NULL,
                source_type NVARCHAR(16) NOT NULL,
                target_time_ist DATETIME2 NOT NULL,
                predicted_price DECIMAL(18,4) NOT NULL,
                actual_price DECIMAL(18,4) NULL,
                error_abs DECIMAL(18,4) NULL,
                error_pct DECIMAL(8,4) NULL,
                within_1pct BIT NULL,
                evaluated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                CONSTRAINT FK_acc_run FOREIGN KEY (run_id) REFERENCES dbo.prediction_runs(run_id),
                CONSTRAINT FK_acc_point FOREIGN KEY (point_id) REFERENCES dbo.prediction_points(point_id)
            );
            """
        )
        self._migrate_column(cur, "accuracy_evaluations", "source_type", "source_type NVARCHAR(16) NOT NULL DEFAULT 'RULE'")

        cur.execute(
            """
            IF OBJECT_ID('dbo.data_retention_policy', 'U') IS NULL
            CREATE TABLE dbo.data_retention_policy (
                policy_key NVARCHAR(64) PRIMARY KEY,
                retention_months INT NOT NULL DEFAULT 6,
                is_enabled BIT NOT NULL DEFAULT 1,
                description NVARCHAR(512) NULL,
                last_purge_at DATETIME2 NULL,
                updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
            );

            IF OBJECT_ID('dbo.maintenance_purge_log', 'U') IS NULL
            CREATE TABLE dbo.maintenance_purge_log (
                log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
                ran_at_ist DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                retention_months INT NOT NULL,
                cutoff_ist DATETIME2 NOT NULL,
                total_rows_deleted BIGINT NOT NULL DEFAULT 0,
                details NVARCHAR(MAX) NULL
            );
            """
        )

        cur.execute(
            """
            IF NOT EXISTS (SELECT 1 FROM dbo.data_retention_policy WHERE policy_key = 'default')
            INSERT INTO dbo.data_retention_policy (policy_key, retention_months, description)
            VALUES (
                'default', 6,
                'Auto-delete predictions, bars, and accuracy rows older than 6 months'
            );
            """
        )

        cur.execute(
            """
            EXEC('
            CREATE OR ALTER PROCEDURE dbo.usp_purge_data_older_than_months
                @months INT = 6
            AS
            BEGIN
                SET NOCOUNT ON;
                DECLARE @cutoff DATETIME2 = DATEADD(MONTH, -@months, SYSUTCDATETIME());
                DECLARE @n BIGINT = 0, @d BIGINT;

                DELETE FROM dbo.accuracy_evaluations
                WHERE target_time_ist < @cutoff OR evaluated_at < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE p FROM dbo.prediction_points p
                INNER JOIN dbo.prediction_runs r ON r.run_id = p.run_id
                WHERE r.run_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE l FROM dbo.prediction_logic l
                INNER JOIN dbo.prediction_runs r ON r.run_id = l.run_id
                WHERE r.run_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE g FROM dbo.genai_reasoning g
                INNER JOIN dbo.prediction_runs r ON r.run_id = g.run_id
                WHERE r.run_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE FROM dbo.prediction_runs WHERE run_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE FROM dbo.market_bars WHERE bar_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                DELETE FROM dbo.live_bars WHERE bar_time_ist < @cutoff;
                SET @d = @@ROWCOUNT; SET @n = @n + @d;

                UPDATE dbo.data_retention_policy
                SET last_purge_at = SYSUTCDATETIME(), updated_at = SYSUTCDATETIME()
                WHERE policy_key = ''default'';

                INSERT INTO dbo.maintenance_purge_log (retention_months, cutoff_ist, total_rows_deleted, details)
                VALUES (@months, @cutoff, @n, ''Scheduled retention purge'');

                SELECT @n AS total_rows_deleted, @cutoff AS cutoff_utc;
            END
            ');
            """
        )

        conn.commit()
        cur.close()
        conn.close()
        self._ensured = True

    def upsert_market_bars(self, stock: str, df: pd.DataFrame, interval: str) -> int:
        """Auto-save full OHLCV real-time window."""
        if not self.enabled or df is None or df.empty:
            return 0
        self.ensure_database()
        n = 0
        conn = self._open_connection()
        cur = conn.cursor()
        for ts, row in df.iterrows():
            t = _ts_ist_naive(ts)
            o, h, l, c = float(row["Open"]), float(row["High"]), float(row["Low"]), float(row["Close"])
            vol = int(row.get("Volume", 0) or 0)
            cur.execute(
                """
                MERGE dbo.market_bars AS t
                USING (SELECT ? AS stock, ? AS bar_time_ist, ? AS interval_label) AS s
                ON t.stock = s.stock AND t.bar_time_ist = s.bar_time_ist
                   AND ISNULL(t.interval_label,'') = ISNULL(s.interval_label,'')
                WHEN MATCHED THEN UPDATE SET
                    open_price=?, high_price=?, low_price=?, close_price=?, volume=?, ingested_at=SYSUTCDATETIME()
                WHEN NOT MATCHED THEN INSERT
                    (stock, bar_time_ist, open_price, high_price, low_price, close_price, volume, interval_label)
                    VALUES (s.stock, s.bar_time_ist, ?, ?, ?, ?, ?, s.interval_label);
                """,
                (stock, t, interval, o, h, l, c, vol, o, h, l, c, vol),
            )
            n += 1
        conn.commit()
        cur.close()
        conn.close()
        return n

    def upsert_live_bars(self, stock: str, series: pd.Series) -> None:
        if not self.enabled or series is None or len(series) == 0:
            return
        self.ensure_database()
        conn = self._open_connection()
        cur = conn.cursor()
        for ts, px in series.items():
            t = _ts_ist_naive(ts)
            cur.execute(
                """
                MERGE dbo.live_bars AS t
                USING (SELECT ? AS stock, ? AS bar_time_ist, ? AS close_price) AS s
                ON t.stock = s.stock AND t.bar_time_ist = s.bar_time_ist
                WHEN MATCHED THEN UPDATE SET close_price = s.close_price, ingested_at = SYSUTCDATETIME()
                WHEN NOT MATCHED THEN INSERT (stock, bar_time_ist, close_price) VALUES (s.stock, s.bar_time_ist, s.close_price);
                """,
                (stock, t, float(px)),
            )
        conn.commit()
        cur.close()
        conn.close()

    def save_prediction(
        self,
        *,
        stock: str,
        source_type: str,
        signal: str,
        confidence: float,
        stop_loss: float,
        target: float,
        reason: str,
        market_phase: str,
        period: str,
        interval: str,
        last_close: float,
        proj_series: pd.Series,
        score: float | None = None,
        is_primary: bool = False,
        model_name: str | None = None,
        logic_snapshot: dict | None = None,
        genai_brain: dict | None = None,
    ) -> int | None:
        if not self.enabled or proj_series is None or len(proj_series) == 0:
            return None
        self.ensure_database()
        now_ist = datetime.now(IST).replace(tzinfo=None)
        conn = self._open_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO dbo.prediction_runs
            (stock, run_time_ist, source_type, is_primary, model_name, signal, confidence_pct,
             score, stop_loss, target_price, reason_tags, market_phase, period, interval_label, last_close)
            OUTPUT INSERTED.run_id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                stock,
                now_ist,
                source_type,
                1 if is_primary else 0,
                model_name,
                signal,
                float(confidence),
                score,
                float(stop_loss),
                float(target),
                (reason or "")[:4000],
                market_phase,
                period,
                interval,
                float(last_close),
            ),
        )
        run_id = int(cur.fetchone()[0])

        rows = []
        for i, (ts, px) in enumerate(proj_series.items()):
            rows.append((run_id, stock, _ts_ist_naive(ts), float(px), i))
        cur.executemany(
            """
            INSERT INTO dbo.prediction_points (run_id, stock, target_time_ist, predicted_price, sequence_no)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )

        if logic_snapshot:
            cur.execute(
                """
                INSERT INTO dbo.prediction_logic
                (run_id, stock, source_type, indicators_json, rule_snapshot_json, genai_input_json, genai_output_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stock,
                    source_type,
                    json.dumps(logic_snapshot.get("indicators", logic_snapshot), default=str)[:8000],
                    json.dumps(logic_snapshot.get("rule_engine_reference", {}), default=str)[:8000],
                    json.dumps(logic_snapshot.get("genai_input"), default=str)[:8000] if logic_snapshot.get("genai_input") else None,
                    json.dumps(logic_snapshot.get("genai_output"), default=str)[:12000] if logic_snapshot.get("genai_output") else None,
                ),
            )

        if genai_brain and source_type == SOURCE_GENAI:
            cur.execute(
                """
                INSERT INTO dbo.genai_reasoning
                (run_id, stock, market_read, reasoning_steps_json, news_cited_json, risks, limitations)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stock,
                    (genai_brain.get("market_read") or "")[:8000],
                    json.dumps(genai_brain.get("reasoning_steps") or [], ensure_ascii=False),
                    json.dumps(genai_brain.get("news_cited") or [], ensure_ascii=False),
                    (genai_brain.get("risks") or "")[:4000],
                    (genai_brain.get("limitations") or "")[:4000],
                ),
            )

        conn.commit()
        cur.close()
        conn.close()
        return run_id

    def save_run(self, **kwargs) -> int | None:
        """Backward-compatible rule-only save."""
        kwargs.setdefault("source_type", SOURCE_RULE)
        kwargs.setdefault("is_primary", False)
        return self.save_prediction(**kwargs)

    def evaluate_accuracy(self, stock: str, actual_lookup: dict | None = None) -> int:
        if not self.enabled:
            return 0
        self.ensure_database()
        conn = self._open_connection()
        cur = conn.cursor()
        cur.execute(
            """
            SELECT p.point_id, p.run_id, p.stock, p.target_time_ist, p.predicted_price, r.source_type
            FROM dbo.prediction_points p
            INNER JOIN dbo.prediction_runs r ON r.run_id = p.run_id
            LEFT JOIN dbo.accuracy_evaluations e ON e.point_id = p.point_id
            WHERE p.stock = ? AND p.target_time_ist <= SYSUTCDATETIME() AND e.eval_id IS NULL
            """,
            (stock,),
        )
        updated = 0
        for point_id, run_id, sym, target_time, predicted, src in cur.fetchall():
            actual = None
            if actual_lookup:
                for k, v in actual_lookup.items():
                    if abs((k - target_time).total_seconds()) < 300:
                        actual = v
                        break
            if actual is None:
                cur.execute(
                    """
                    SELECT TOP 1 close_price FROM dbo.market_bars
                    WHERE stock = ? AND bar_time_ist <= ?
                    ORDER BY bar_time_ist DESC
                    """,
                    (sym, target_time),
                )
                row = cur.fetchone()
                if not row:
                    cur.execute(
                        """
                        SELECT TOP 1 close_price FROM dbo.live_bars
                        WHERE stock = ? AND bar_time_ist <= ?
                        ORDER BY bar_time_ist DESC
                        """,
                        (sym, target_time),
                    )
                    row = cur.fetchone()
                if row:
                    actual = float(row[0])
            if actual is None:
                continue
            err = abs(float(predicted) - actual)
            err_pct = (err / actual * 100) if actual else None
            within = 1 if err_pct is not None and err_pct <= 1.0 else 0
            cur.execute(
                """
                INSERT INTO dbo.accuracy_evaluations
                (run_id, point_id, stock, source_type, target_time_ist, predicted_price,
                 actual_price, error_abs, error_pct, within_1pct)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (run_id, point_id, sym, src, target_time, float(predicted), actual, err, err_pct, within),
            )
            updated += 1
        conn.commit()
        cur.close()
        conn.close()
        return updated

    def load_historical_predictions(self, stock: str, source_type: str | None = None, limit_runs: int = 50) -> pd.DataFrame:
        if not self.enabled:
            return pd.DataFrame()
        try:
            self.ensure_database()
            conn = self._open_connection()
            q = """
                SELECT TOP (?)
                    r.run_time_ist AS run_time,
                    p.target_time_ist AS target_time,
                    p.predicted_price,
                    r.signal,
                    r.confidence_pct,
                    r.source_type
                FROM dbo.prediction_points p
                INNER JOIN dbo.prediction_runs r ON r.run_id = p.run_id
                WHERE p.stock = ?
            """
            params: list = [limit_runs * 80, stock]
            if source_type:
                q += " AND r.source_type = ?"
                params.append(source_type)
            q += " ORDER BY r.run_id DESC, p.sequence_no"
            df = pd.read_sql(q, conn, params=params)
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    def load_accuracy_summary(self, stock: str, source_type: str | None = None) -> dict[str, Any]:
        if not self.enabled:
            return {"evaluated": 0}
        try:
            self.ensure_database()
            conn = self._open_connection()
            cur = conn.cursor()
            q = """
                SELECT COUNT(*), AVG(error_pct), SUM(CASE WHEN within_1pct = 1 THEN 1 ELSE 0 END)
                FROM dbo.accuracy_evaluations WHERE stock = ? AND actual_price IS NOT NULL
            """
            params: list = [stock]
            if source_type:
                q += " AND source_type = ?"
                params.append(source_type)
            cur.execute(q, params)
            row = cur.fetchone()
            conn.close()
            if not row or row[0] == 0:
                return {"evaluated": 0, "source_type": source_type or "ALL"}
            n, avg_err, hits = row
            return {
                "evaluated": int(n),
                "avg_error_pct": round(float(avg_err or 0), 3),
                "within_1pct": int(hits or 0),
                "hit_rate_pct": round(100.0 * (hits or 0) / n, 1),
                "source_type": source_type or "ALL",
            }
        except Exception:
            return {"evaluated": 0}

    def load_audit_trail(self, stock: str, limit: int = 15) -> pd.DataFrame:
        """Runs with logic + Gen AI reasoning for monitor / back-check."""
        if not self.enabled:
            return pd.DataFrame()
        try:
            self.ensure_database()
            conn = self._open_connection()
            df = pd.read_sql(
                """
                SELECT TOP (?)
                    r.run_id, r.run_time_ist, r.source_type, r.is_primary, r.signal,
                    r.confidence_pct, r.target_price, r.stop_loss, r.reason_tags,
                    l.indicators_json, l.rule_snapshot_json, l.genai_output_json,
                    g.market_read, g.reasoning_steps_json, g.news_cited_json
                FROM dbo.prediction_runs r
                LEFT JOIN dbo.prediction_logic l ON l.run_id = r.run_id
                LEFT JOIN dbo.genai_reasoning g ON g.run_id = r.run_id
                WHERE r.stock = ?
                ORDER BY r.run_id DESC
                """,
                conn,
                params=(limit, stock),
            )
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    def get_retention_months(self) -> int:
        """Read retention from data_retention_policy (default 6)."""
        if not self.enabled:
            return 6
        try:
            self.ensure_database()
            conn = self._open_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT retention_months FROM dbo.data_retention_policy
                WHERE policy_key = 'default' AND is_enabled = 1
                """
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            return int(row[0]) if row else 6
        except Exception:
            return 6

    def purge_data_older_than_months(self, months: int | None = None) -> dict[str, Any]:
        """
        Delete rows older than N months from all transactional tables.
        Does NOT touch api_config, api_providers, or app_settings.
        """
        if not self.enabled:
            return {"deleted": 0, "skipped": True}
        months = months if months is not None else self.get_retention_months()
        self.ensure_database()
        conn = self._open_connection()
        cur = conn.cursor()
        cur.execute("EXEC dbo.usp_purge_data_older_than_months @months = ?", (months,))
        row = cur.fetchone()
        conn.commit()
        cur.close()
        conn.close()
        deleted = int(row[0]) if row else 0
        cutoff = row[1] if row and len(row) > 1 else None
        return {
            "deleted": deleted,
            "retention_months": months,
            "cutoff": str(cutoff) if cutoff else None,
        }

    def run_retention_purge_if_due(self, min_hours_between: int = 24) -> dict[str, Any] | None:
        """Run purge at most once per min_hours (app calls this on refresh)."""
        if not self.enabled:
            return None
        try:
            from datetime import datetime, timedelta

            self.ensure_database()
            conn = self._open_connection()
            cur = conn.cursor()
            cur.execute(
                """
                SELECT last_purge_at, is_enabled FROM dbo.data_retention_policy
                WHERE policy_key = 'default'
                """
            )
            row = cur.fetchone()
            cur.close()
            conn.close()
            if row and not row[1]:
                return None
            if row and row[0]:
                last = row[0]
                if hasattr(last, "replace"):
                    age = datetime.utcnow() - last.replace(tzinfo=None)
                    if age < timedelta(hours=min_hours_between):
                        return None
        except Exception:
            pass
        return self.purge_data_older_than_months()

    def load_purge_history(self, limit: int = 10) -> pd.DataFrame:
        if not self.enabled:
            return pd.DataFrame()
        try:
            self.ensure_database()
            conn = self._open_connection()
            df = pd.read_sql(
                """
                SELECT TOP (?) ran_at_ist, retention_months, cutoff_ist, total_rows_deleted
                FROM dbo.maintenance_purge_log ORDER BY log_id DESC
                """,
                conn,
                params=(limit,),
            )
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

    def query_recent_bars(self, stock: str, limit: int = 20) -> pd.DataFrame:
        if not self.enabled:
            return pd.DataFrame()
        try:
            self.ensure_database()
            conn = self._open_connection()
            df = pd.read_sql(
                """
                SELECT TOP (?) bar_time_ist, open_price, high_price, low_price, close_price, volume
                FROM dbo.market_bars WHERE stock = ? ORDER BY bar_time_ist DESC
                """,
                conn,
                params=(limit, stock),
            )
            conn.close()
            return df
        except Exception:
            return pd.DataFrame()

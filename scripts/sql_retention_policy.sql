-- Data retention: auto-delete transactional data older than 6 months
USE AngadTrading;
GO

-- Policy table (change months here)
IF OBJECT_ID('dbo.data_retention_policy', 'U') IS NULL
CREATE TABLE dbo.data_retention_policy (
    policy_key NVARCHAR(64) PRIMARY KEY,
    retention_months INT NOT NULL DEFAULT 6,
    is_enabled BIT NOT NULL DEFAULT 1,
    description NVARCHAR(512) NULL,
    last_purge_at DATETIME2 NULL,
    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
);
GO

-- Change retention to 3 months example:
-- UPDATE dbo.data_retention_policy SET retention_months = 3 WHERE policy_key = 'default';

IF OBJECT_ID('dbo.maintenance_purge_log', 'U') IS NULL
CREATE TABLE dbo.maintenance_purge_log (
    log_id BIGINT IDENTITY(1,1) PRIMARY KEY,
    ran_at_ist DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
    retention_months INT NOT NULL,
    cutoff_ist DATETIME2 NOT NULL,
    total_rows_deleted BIGINT NOT NULL DEFAULT 0,
    details NVARCHAR(MAX) NULL
);
GO

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
    WHERE policy_key = 'default';

    INSERT INTO dbo.maintenance_purge_log (retention_months, cutoff_ist, total_rows_deleted, details)
    VALUES (@months, @cutoff, @n, N'Manual or scheduled purge');

    SELECT @n AS total_rows_deleted, @cutoff AS cutoff_utc;
END;
GO

-- Run once manually:
-- EXEC dbo.usp_purge_data_older_than_months @months = 6;

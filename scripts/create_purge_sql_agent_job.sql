-- Optional: SQL Server Agent job — purge monthly (requires SQL Server Agent running)
USE msdb;
GO

DECLARE @job_name NVARCHAR(128) = N'AngadTrading_Purge_Older_Than_6_Months';

IF EXISTS (SELECT 1 FROM msdb.dbo.sysjobs WHERE name = @job_name)
    EXEC msdb.dbo.sp_delete_job @job_name = @job_name, @delete_unused_schedule = 1;

EXEC msdb.dbo.sp_add_job
    @job_name = @job_name,
    @description = N'Delete AngadTrading data older than 6 months',
    @enabled = 1;

EXEC msdb.dbo.sp_add_jobstep
    @job_name = @job_name,
    @step_name = N'Purge',
    @subsystem = N'TSQL',
    @database_name = N'AngadTrading',
    @command = N'EXEC dbo.usp_purge_data_older_than_months @months = 6;',
    @on_success_action = 1;

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'Angad_Monthly_Purge',
    @freq_type = 16,
    @freq_interval = 1,
    @freq_recurrence_factor = 1,
    @active_start_time = 20000;

EXEC msdb.dbo.sp_attach_schedule @job_name = @job_name, @schedule_name = N'Angad_Monthly_Purge';
EXEC msdb.dbo.sp_add_jobserver @job_name = @job_name;
GO

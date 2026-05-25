-- Run in SSMS as sysadmin (sa or Windows admin) once.
-- Grants Hemant access to dedicated AngadTrading database.

IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'AngadTrading')
BEGIN
    CREATE DATABASE [AngadTrading];
END
GO

USE [AngadTrading];
GO

IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = N'Hemant')
BEGIN
    CREATE USER [Hemant] FOR LOGIN [Hemant];
END
GO

ALTER ROLE db_owner ADD MEMBER [Hemant];
GO

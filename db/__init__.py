"""Angad SQLite package — portable file database, no SQL Server."""

from db.bootstrap import initialize
from db.database import DatabaseError, db_path, get_connection

__all__ = ["DatabaseError", "db_path", "get_connection", "initialize"]

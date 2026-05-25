"""
Create AngadTrading database (needs admin) and all tables.
Run: py -3 scripts/setup_database.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pyodbc
from config.loader import load_bootstrap_config, load_settings
from db.sql_store import SqlStore

DB_NAME = "AngadTrading"


def _conn(server: str, database: str, user: str, pwd: str, driver: str) -> pyodbc.Connection:
    cs = (
        f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};"
        f"UID={user};PWD={pwd};TrustServerCertificate=yes;"
    )
    return pyodbc.connect(cs, timeout=20)


def create_database_as_admin(server: str) -> bool:
    """Try Windows integrated auth on master (local admin)."""
    for driver in ("ODBC Driver 17 for SQL Server", "ODBC Driver 18 for SQL Server"):
        if driver not in pyodbc.drivers():
            continue
        try:
            cs = f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;Trusted_Connection=yes;TrustServerCertificate=yes;"
            conn = pyodbc.connect(cs, timeout=15, autocommit=True)
            cur = conn.cursor()
            cur.execute(
                f"""
                IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'{DB_NAME}')
                CREATE DATABASE [{DB_NAME}];
                """
            )
            cur.close()
            conn.close()
            print(f"OK: database [{DB_NAME}] created (or already exists) via Windows auth.")
            return True
        except pyodbc.Error as e:
            print(f"Windows auth create DB ({driver}): {e}")
    return False


def grant_user(server: str, user: str, pwd: str) -> None:
    """Grant Hemant db_owner on AngadTrading (run as admin on that DB)."""
    for driver in ("ODBC Driver 17 for SQL Server",):
        try:
            cs = f"DRIVER={{{driver}}};SERVER={server};DATABASE={DB_NAME};Trusted_Connection=yes;TrustServerCertificate=yes;"
            conn = pyodbc.connect(cs, timeout=15, autocommit=True)
            cur = conn.cursor()
            cur.execute(
                f"""
                IF NOT EXISTS (SELECT name FROM sys.database_principals WHERE name = N'{user}')
                    CREATE USER [{user}] FOR LOGIN [{user}];
                IF IS_ROLEMEMBER('db_owner', '{user}') = 0
                    ALTER ROLE db_owner ADD MEMBER [{user}];
                """
            )
            cur.close()
            conn.close()
            print(f"OK: granted db_owner to [{user}] on [{DB_NAME}].")
            return
        except pyodbc.Error as e:
            print(f"Grant user: {e}")


def main():
    cfg = load_settings()["database"]["sql_server"]
    server = cfg["server"]
    user = cfg.get("username", "")
    pwd = cfg.get("password", "")

    create_database_as_admin(server)
    grant_user(server, user, pwd)

    # Test login as Hemant
    try:
        _conn(server, DB_NAME, user, pwd, "ODBC Driver 17 for SQL Server").close()
        print(f"OK: login [{user}] can connect to [{DB_NAME}].")
    except pyodbc.Error as e:
        print(f"WARN: cannot connect to [{DB_NAME}] as [{user}]: {e}")
        print("Using fallback_database until admin runs create_angad_database.sql")

    store = SqlStore(load_settings())
    store.database = DB_NAME
    store.ensure_database()
    print(f"OK: tables ready in [{store.database}] on {server}.")

    # Smoke insert
    import pandas as pd

    ts = pd.date_range("2026-05-25 09:15", periods=2, freq="5min", tz="Asia/Kolkata")
    s = pd.Series([100.0, 100.5], index=ts)
    rid = store.save_prediction(
        stock="TEST",
        source_type="RULE",
        signal="HOLD",
        confidence=50,
        stop_loss=99,
        target=101,
        reason="setup test",
        market_phase="test",
        period="5d",
        interval="5m",
        last_close=100,
        proj_series=s,
        logic_snapshot={"test": True},
    )
    print(f"OK: test prediction run_id={rid}")

    import subprocess

    subprocess.run([sys.executable, str(Path(__file__).parent / "seed_sql_apis.py")], check=False)


if __name__ == "__main__":
    main()

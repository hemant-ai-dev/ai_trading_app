"""Explicit SQLite reset — never called on application start."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.database import db_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete the SQLite database file. Requires explicit confirmation."
    )
    parser.add_argument(
        "--yes-delete-all-data",
        action="store_true",
        help="Required flag. Without it the file is not deleted.",
    )
    parser.add_argument(
        "--confirm",
        default="",
        help='Must be exactly DELETE to proceed.',
    )
    args = parser.parse_args()
    path = db_path()
    print(f"Target: {path}")
    if not args.yes_delete_all_data or args.confirm != "DELETE":
        print("Aborted. This utility is destructive and is not run by the app.")
        print('Usage: python scripts/reset_sqlite_db.py --yes-delete-all-data --confirm DELETE')
        sys.exit(1)
    if path.exists():
        path.unlink()
        wal = Path(str(path) + "-wal")
        shm = Path(str(path) + "-shm")
        if wal.exists():
            wal.unlink()
        if shm.exists():
            shm.unlink()
        print("Deleted.")
    else:
        print("File did not exist.")


if __name__ == "__main__":
    main()

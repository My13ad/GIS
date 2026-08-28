"""Explicitly migrate the current CSV snapshot into local SQLite once."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from sqlite_store import SqliteRowStore, SqliteStoreError, migrate_csv_to_sqlite  # noqa: E402


def main() -> int:
    """Migrate the canonical CSV and report only the row count."""
    store = SqliteRowStore(ROOT / "data" / "gis.sqlite3")
    try:
        count = migrate_csv_to_sqlite(store, ROOT / "data" / "blind_path_issues.csv")
    except SqliteStoreError as error:
        print(f"ERROR: SQLite migration failed ({error.code})")
        return 1
    print(f"migrated rows: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

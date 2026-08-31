"""Canonical local SQLite persistence for validated GIS rows."""

from __future__ import annotations

import csv
import io
import sqlite3
from pathlib import Path
from typing import Final

from csv_store import _serialize_rows, read_seed_snapshot
from gis_data import Dataset, GisRow
from pydantic import ValidationError

TABLE: Final = "gis_rows"
COLUMNS: Final = (
    "id", "city", "district", "street", "longitude", "latitude",
    "problem_type", "description",
    "detected_at", "data_source",
)
CREATE_TABLE: Final = """CREATE TABLE IF NOT EXISTS gis_rows (
    id TEXT PRIMARY KEY, city TEXT NOT NULL, district TEXT NOT NULL,
    street TEXT NOT NULL, longitude REAL NOT NULL, latitude REAL NOT NULL,
    problem_type TEXT NOT NULL, description TEXT NOT NULL, detected_at TEXT NOT NULL,
    data_source TEXT NOT NULL, position INTEGER NOT NULL UNIQUE
)"""


class SqliteStoreError(Exception):
    """A typed local SQLite storage failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class SqliteRowStore:
    """Persist validated rows in one ordered SQLite table."""

    def __init__(self, database: Path) -> None:
        self.database = database
        self.database.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            self._ensure_schema(connection)

    @staticmethod
    def _ensure_schema(connection: sqlite3.Connection) -> None:
        """Create the current table or migrate the pre-10-column schema."""
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)
        ).fetchone()
        if table is None:
            connection.execute(CREATE_TABLE)
            return

        existing = {
            str(row[1])
            for row in connection.execute(f"PRAGMA table_info({TABLE})").fetchall()
        }
        expected = set(COLUMNS) | {"position"}
        if existing == expected:
            return

        # Rebuild the table so old subtype/severity/confidence columns are
        # dropped while preserving all fields that remain in the contract.
        legacy_table = f"{TABLE}_legacy"
        connection.execute(f"DROP TABLE IF EXISTS {legacy_table}")
        connection.execute(f"ALTER TABLE {TABLE} RENAME TO {legacy_table}")
        connection.execute(CREATE_TABLE)
        source_columns = [column for column in COLUMNS if column in existing]
        if "position" in existing:
            source_columns.append("position")
            select_columns = ", ".join(source_columns)
            order_clause = "position"
        else:
            source_columns.append("position")
            select_columns = ", ".join(source_columns[:-1]) + ", rowid - 1"
            order_clause = "rowid"
        target_columns = ", ".join(source_columns)
        connection.execute(
            f"INSERT INTO {TABLE} ({target_columns}) SELECT {select_columns} "
            f"FROM {legacy_table} ORDER BY {order_clause}"
        )
        connection.execute(f"DROP TABLE {legacy_table}")

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def is_empty(self) -> bool:
        """Return whether the canonical table contains no rows."""
        with self._connect() as connection:
            return connection.execute("SELECT 1 FROM gis_rows LIMIT 1").fetchone() is None

    def read(self) -> Dataset:
        """Read and validate rows in their stable insertion order."""
        with self._connect() as connection:
            records = connection.execute("SELECT * FROM gis_rows ORDER BY position").fetchall()
        try:
            return Dataset(tuple(GisRow.model_validate(dict(record)) for record in records))
        except (ValidationError, ValueError, TypeError) as error:
            raise SqliteStoreError("invalid_row", "invalid SQLite row") from error

    def append(self, rows: tuple[GisRow, ...]) -> None:
        """Append rows atomically, rejecting duplicate stable IDs."""
        current = self.read().rows
        self._validate_unique((*current, *rows))
        self._replace((*current, *rows))

    def update(self, row_id: str, replacement: GisRow) -> None:
        """Update one row while preserving its stable position."""
        if replacement.id != row_id:
            raise SqliteStoreError("stable_id", "replacement stable ID must match target")
        rows = self.read().rows
        if row_id not in {row.id for row in rows}:
            raise SqliteStoreError("not_found", f"stable ID not found: {row_id}")
        self._replace(tuple(replacement if row.id == row_id else row for row in rows))

    def delete(self, row_id: str) -> None:
        """Delete one row atomically."""
        rows = self.read().rows
        kept = tuple(row for row in rows if row.id != row_id)
        if len(kept) == len(rows):
            raise SqliteStoreError("not_found", f"stable ID not found: {row_id}")
        self._replace(kept)

    def replace(self, rows: tuple[GisRow, ...]) -> None:
        """Replace all rows in one SQLite transaction."""
        self._validate_unique(rows)
        self._replace(rows)

    @staticmethod
    def _validate_unique(rows: tuple[GisRow, ...]) -> None:
        ids = [row.id for row in rows]
        if len(ids) != len(set(ids)):
            raise SqliteStoreError("duplicate_id", "duplicate stable ID")

    def _replace(self, rows: tuple[GisRow, ...]) -> None:
        values = [
            (
                row.id,
                row.city.value,
                row.district,
                row.street,
                row.longitude,
                row.latitude,
                row.problem_type,
                row.description,
                row.detected_at,
                row.data_source,
                index,
            )
            for index, row in enumerate(rows)
        ]
        with self._connect() as connection:
            connection.execute("DELETE FROM gis_rows")
            if values:
                connection.executemany(
                    "INSERT INTO gis_rows (id, city, district, street, longitude, latitude, problem_type, description, detected_at, data_source, position) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    values,
                )


def migrate_csv_to_sqlite(store: SqliteRowStore, csv_path: Path) -> int:
    """Seed SQLite from the explicit CSV only when the database is empty."""
    if not store.is_empty():
        return 0
    dataset = read_seed_snapshot(csv_path)
    store.replace(dataset.rows)
    return len(dataset.rows)


def rows_to_csv_bytes(rows: tuple[GisRow, ...]) -> bytes:
    """Serialize SQLite rows for explicit CSV download."""
    return _serialize_rows(rows)

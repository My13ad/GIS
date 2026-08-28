"""Canonical PostgreSQL persistence for validated GIS rows."""

from __future__ import annotations

from pathlib import Path
from typing import Final

from csv_store import _serialize_rows, read_snapshot
from gis_data import Dataset, GisRow
from pydantic import ValidationError

TABLE: Final = "gis_rows"
COLUMNS: Final = (
    "id", "city", "district", "street", "longitude", "latitude",
    "problem_type", "subtype", "severity", "confidence", "description",
    "detected_at", "data_source",
)
CREATE_TABLE: Final = """CREATE TABLE IF NOT EXISTS gis_rows (
    id TEXT PRIMARY KEY, city TEXT NOT NULL, district TEXT NOT NULL,
    street TEXT NOT NULL, longitude DOUBLE PRECISION NOT NULL,
    latitude DOUBLE PRECISION NOT NULL, problem_type TEXT NOT NULL,
    subtype TEXT NOT NULL, severity TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL, description TEXT NOT NULL,
    detected_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, data_source TEXT NOT NULL,
    position INTEGER NOT NULL UNIQUE
)"""


class PostgresStoreError(Exception):
    """A typed PostgreSQL storage failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class PostgresRowStore:
    """Persist validated rows in a shared PostgreSQL table."""

    def __init__(self, database_url: str, *, sslmode: str = "require") -> None:
        if not database_url.strip():
            raise PostgresStoreError("config", "DATABASE_URL is empty")
        self.database_url = database_url
        self.sslmode = sslmode
        try:
            with self._connect() as connection:
                connection.execute(CREATE_TABLE)
        except PostgresStoreError:
            raise
        except Exception as error:
            raise self._wrap_error("connect", error) from error

    def _connect(self):
        try:
            import psycopg
        except ImportError as error:
            raise PostgresStoreError(
                "dependency", "psycopg is required when DATABASE_URL is configured"
            ) from error
        try:
            return psycopg.connect(
                self.database_url,
                sslmode=self.sslmode,
                connect_timeout=10,
                # Supabase transaction poolers may route each transaction to a
                # different backend, so server-side prepared statements are unsafe.
                prepare_threshold=None,
            )
        except Exception as error:
            raise self._wrap_error("connect", error) from error

    @staticmethod
    def _wrap_error(code: str, error: Exception) -> PostgresStoreError:
        detail = str(error).replace("\n", " ")
        return PostgresStoreError(code, detail[:500])

    def is_empty(self) -> bool:
        try:
            with self._connect() as connection:
                return connection.execute("SELECT 1 FROM gis_rows LIMIT 1").fetchone() is None
        except PostgresStoreError:
            raise
        except Exception as error:
            raise self._wrap_error("read", error) from error

    def read(self) -> Dataset:
        try:
            with self._connect() as connection:
                records = connection.execute(
                    "SELECT id, city, district, street, longitude, latitude, "
                    "problem_type, subtype, severity, confidence, description, "
                    "detected_at, data_source FROM gis_rows ORDER BY position"
                ).fetchall()
        except PostgresStoreError:
            raise
        except Exception as error:
            raise self._wrap_error("read", error) from error
        try:
            rows = tuple(
                GisRow.model_validate(dict(zip(COLUMNS, record, strict=True)))
                for record in records
            )
            return Dataset(rows)
        except (ValidationError, ValueError, TypeError) as error:
            raise PostgresStoreError("invalid_row", "invalid PostgreSQL row") from error

    def append(self, rows: tuple[GisRow, ...]) -> None:
        current = self.read().rows
        self._validate_unique((*current, *rows))
        self._replace((*current, *rows))

    def update(self, row_id: str, replacement: GisRow) -> None:
        if replacement.id != row_id:
            raise PostgresStoreError("stable_id", "replacement stable ID must match target")
        rows = self.read().rows
        if row_id not in {row.id for row in rows}:
            raise PostgresStoreError("not_found", f"stable ID not found: {row_id}")
        self._replace(tuple(replacement if row.id == row_id else row for row in rows))

    def delete(self, row_id: str) -> None:
        rows = self.read().rows
        kept = tuple(row for row in rows if row.id != row_id)
        if len(kept) == len(rows):
            raise PostgresStoreError("not_found", f"stable ID not found: {row_id}")
        self._replace(kept)

    def replace(self, rows: tuple[GisRow, ...]) -> None:
        self._validate_unique(rows)
        self._replace(rows)

    @staticmethod
    def _validate_unique(rows: tuple[GisRow, ...]) -> None:
        ids = [row.id for row in rows]
        if len(ids) != len(set(ids)):
            raise PostgresStoreError("duplicate_id", "duplicate stable ID")

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
                row.subtype,
                row.severity,
                row.confidence,
                row.description,
                row.detected_at,
                row.data_source,
                index,
            )
            for index, row in enumerate(rows)
        ]
        try:
            with self._connect() as connection:
                connection.execute("DELETE FROM gis_rows")
                if values:
                    with connection.cursor() as cursor:
                        cursor.executemany(
                            "INSERT INTO gis_rows (id, city, district, street, longitude, latitude, "
                            "problem_type, subtype, severity, confidence, description, detected_at, "
                            "data_source, position) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            values,
                        )
        except PostgresStoreError:
            raise
        except Exception as error:
            raise self._wrap_error("write", error) from error


def migrate_csv_to_postgres(store: PostgresRowStore, csv_path: Path) -> int:
    """Seed PostgreSQL once from the explicit CSV when the table is empty."""
    if not store.is_empty():
        return 0
    dataset = read_snapshot(csv_path)
    store.replace(dataset.rows)
    return len(dataset.rows)


def rows_to_csv_bytes(rows: tuple[GisRow, ...]) -> bytes:
    """Serialize PostgreSQL rows for explicit CSV download."""
    return _serialize_rows(rows)

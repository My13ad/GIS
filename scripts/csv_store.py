"""Atomic persistence for the canonical blind-path CSV."""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path
from typing import Final, Iterable

from gis_common import COLUMNS
from gis_data import Dataset, GisRow
from pydantic import ValidationError

EXPECTED_COLUMNS: Final = tuple(COLUMNS)
LEGACY_COLUMNS: Final = (
    "id", "city", "district", "street", "longitude", "latitude",
    "problem_type", "subtype", "severity", "confidence", "description",
    "detected_at", "data_source",
)


class CsvStoreError(Exception):
    """A local CSV storage contract failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def read_snapshot(path: Path) -> Dataset:
    """Read and validate one immutable CSV snapshot."""
    try:
        payload = path.read_bytes()
    except FileNotFoundError:
        return Dataset(())
    try:
        return Dataset(_read_rows_for_store(path))
    except (UnicodeDecodeError, ValidationError, ValueError, csv.Error) as error:
        raise CsvStoreError("invalid_csv", str(error)) from error


def read_seed_snapshot(path: Path) -> Dataset:
    """Read the seed CSV, migrating the previous 13-column template if needed.

    User uploads remain strict through :func:`gis_data.parse_csv_bytes`; this
    compatibility path only prevents an old bundled/ephemeral seed file from
    blocking first-time database initialization after a schema upgrade.
    """
    try:
        return read_snapshot(path)
    except CsvStoreError as error:
        if error.code != "columns" or not path.exists():
            raise
    try:
        text = path.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvStoreError("invalid_csv", "CSV must be UTF-8 or UTF-8 with BOM") from error
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != LEGACY_COLUMNS:
        raise CsvStoreError("columns", "CSV must contain the exact 10 columns in order")
    rows: list[GisRow] = []
    for row_number, raw_row in enumerate(reader, start=2):
        if None in raw_row:
            raise CsvStoreError("row", "CSV row contains more values than the legacy schema", row_number)
        values = {key: value for key, value in raw_row.items() if key in EXPECTED_COLUMNS}
        try:
            rows.append(GisRow.model_validate(values))
        except ValidationError as error:
            raise CsvStoreError("row", f"invalid row {row_number}: {error}") from error
    return Dataset(tuple(rows))


def append_rows(path: Path, rows: Iterable[GisRow]) -> None:
    """Append validated rows atomically, rejecting every existing ID duplicate."""
    incoming = tuple(rows)
    existing = _read_rows_for_store(path)
    identifiers = {item.id for item in existing}
    duplicate = next((item.id for item in incoming if item.id in identifiers), None)
    if duplicate is not None:
        raise CsvStoreError("duplicate_id", f"duplicate stable ID: {duplicate}")
    incoming_ids = [item.id for item in incoming]
    if len(set(incoming_ids)) != len(incoming_ids):
        raise CsvStoreError("duplicate_id", "duplicate stable ID in appended rows")
    _atomic_write(path, _serialize_rows((*existing, *incoming)))


def replace_rows(path: Path, rows: Iterable[GisRow]) -> None:
    """Replace the canonical snapshot with already validated rows atomically."""
    incoming = tuple(rows)
    identifiers = [item.id for item in incoming]
    if len(set(identifiers)) != len(identifiers):
        raise CsvStoreError("duplicate_id", "duplicate stable ID in replacement rows")
    _atomic_write(path, _serialize_rows(incoming))


def delete_row(path: Path, row_id: str) -> None:
    """Delete one stable ID atomically; missing IDs are a storage error."""
    rows = _read_rows_for_store(path)
    kept = tuple(item for item in rows if item.id != row_id)
    if len(kept) == len(rows):
        raise CsvStoreError("not_found", f"stable ID not found: {row_id}")
    _atomic_write(path, _serialize_rows(kept))


def update_row(path: Path, row_id: str, replacement: GisRow) -> None:
    """Replace one validated row while preserving its stable ID and order."""
    rows = _read_rows_for_store(path)
    if not any(item.id == row_id for item in rows):
        raise CsvStoreError("not_found", f"stable ID not found: {row_id}")
    if replacement.id != row_id:
        raise CsvStoreError("stable_id", "replacement stable ID must match target")
    updated = tuple(replacement if item.id == row_id else item for item in rows)
    _atomic_write(path, _serialize_rows(updated))


def _read_rows_for_store(path: Path) -> tuple[GisRow, ...]:
    if not path.exists():
        return ()
    text = path.read_bytes().decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise CsvStoreError("columns", "CSV must contain the exact 10 columns in order")
    rows: list[GisRow] = []
    for row_number, raw_row in enumerate(reader, start=2):
        try:
            rows.append(GisRow.model_validate(raw_row))
        except ValidationError as error:
            raise CsvStoreError("row", f"invalid row {row_number}: {error}") from error
    return tuple(rows)


def _serialize_rows(rows: tuple[GisRow, ...]) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=EXPECTED_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in rows:
        values = row.model_dump(mode="json")
        values["detected_at"] = row.detected_at.isoformat(sep=" ")
        writer.writerow(values)
    return stream.getvalue().encode("utf-8-sig")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)

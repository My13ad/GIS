from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from gis_data import GisRow
from sqlite_store import SqliteRowStore, migrate_csv_to_sqlite


def make_row(row_id: str, street: str = "五四大街") -> GisRow:
    return GisRow.model_validate(
        {
            "id": row_id,
            "city": "西宁",
            "district": "城西区",
            "street": street,
            "longitude": 101.77,
            "latitude": 36.62,
            "problem_type": "自定义类型",
            "description": "测试记录",
            "detected_at": "2026-07-01 03:07:11",
            "data_source": "测试",
        }
    )


def test_sqlite_store_preserves_order_and_mutations(tmp_path: Path) -> None:
    store = SqliteRowStore(tmp_path / "gis.sqlite3")
    first = make_row("XN-1")
    second = make_row("XN-2")

    store.append((first, second))
    assert store.read().rows == (first, second)
    store.update("XN-1", first.model_copy(update={"street": "长江路"}))
    store.delete("XN-2")
    assert store.read().rows[0].street == "长江路"


def test_sqlite_store_replace_is_atomic_and_rejects_duplicate_ids(tmp_path: Path) -> None:
    store = SqliteRowStore(tmp_path / "gis.sqlite3")
    store.append((make_row("XN-1"),))

    with pytest.raises(Exception):
        store.replace((make_row("A"), make_row("A")))

    assert tuple(row.id for row in store.read().rows) == ("XN-1",)


def test_migrate_csv_to_sqlite_only_when_database_is_empty(tmp_path: Path) -> None:
    database = tmp_path / "gis.sqlite3"
    csv_path = tmp_path / "issues.csv"
    csv_path.write_bytes(
        b"\xef\xbb\xbfid,city,district,street,longitude,latitude,problem_type,description,detected_at,data_source\n"
    )
    store = SqliteRowStore(database)

    assert migrate_csv_to_sqlite(store, csv_path) == 0
    assert migrate_csv_to_sqlite(store, csv_path) == 0


def test_sqlite_store_persists_rows_across_reopen(tmp_path: Path) -> None:
    database = tmp_path / "gis.sqlite3"
    SqliteRowStore(database).append((make_row("XN-1"),))

    reopened = SqliteRowStore(database)

    assert reopened.read().rows == (make_row("XN-1"),)


def test_sqlite_store_migrates_legacy_columns(tmp_path: Path) -> None:
    database = tmp_path / "gis.sqlite3"
    import sqlite3

    with sqlite3.connect(database) as connection:
        connection.execute(
            """CREATE TABLE gis_rows (
                id TEXT PRIMARY KEY, city TEXT NOT NULL, district TEXT NOT NULL,
                street TEXT NOT NULL, longitude REAL NOT NULL, latitude REAL NOT NULL,
                problem_type TEXT NOT NULL, subtype TEXT NOT NULL, severity TEXT NOT NULL,
                confidence REAL NOT NULL, description TEXT NOT NULL, detected_at TEXT NOT NULL,
                data_source TEXT NOT NULL, position INTEGER NOT NULL UNIQUE
            )"""
        )
        connection.execute(
            "INSERT INTO gis_rows VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("XN-1", "西宁", "城西区", "五四大街", 101.77, 36.62, "盲道占用", "旧", "中", 0.9, "", "2026-07-01 03:07:11", "测试", 0),
        )
    store = SqliteRowStore(database)
    migrated = store.read().rows
    assert migrated[0].id == "XN-1"
    assert migrated[0].description == ""
    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(gis_rows)")}
    assert columns.isdisjoint({"subtype", "severity", "confidence"})

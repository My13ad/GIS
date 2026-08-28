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
            "subtype": "自定义子类",
            "severity": "紧急",
            "confidence": 0.9,
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
        b"\xef\xbb\xbfid,city,district,street,longitude,latitude,problem_type,subtype,severity,confidence,description,detected_at,data_source\n"
    )
    store = SqliteRowStore(database)

    assert migrate_csv_to_sqlite(store, csv_path) == 0
    assert migrate_csv_to_sqlite(store, csv_path) == 0


def test_sqlite_store_persists_rows_across_reopen(tmp_path: Path) -> None:
    database = tmp_path / "gis.sqlite3"
    SqliteRowStore(database).append((make_row("XN-1"),))

    reopened = SqliteRowStore(database)

    assert reopened.read().rows == (make_row("XN-1"),)

from __future__ import annotations

import csv
import io
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from gis_data import GisRow
from gis_common import COLUMNS
from csv_store import CsvStoreError, append_rows, delete_row, read_snapshot, update_row


def row(row_id: str, city: str, longitude: float, latitude: float) -> GisRow:
    return GisRow.model_validate({
        "id": row_id,
        "city": city,
        "district": "城西区" if city == "西宁" else "昆仑路街道",
        "street": "五四大街" if city == "西宁" else "昆仑路",
        "longitude": longitude,
        "latitude": latitude,
        "problem_type": "盲道占用",
        "description": "测试记录",
        "detected_at": "2026-07-01 03:07:11",
        "data_source": "测试",
    })


def test_append_rows_writes_canonical_bom_and_roundtrips(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "issues.csv"
    rows = (row("XN-1", "西宁", 101.77, 36.62), row("GL-1", "格尔木", 94.90, 36.40))
    # When
    append_rows(path, rows)
    snapshot = read_snapshot(path)
    # Then
    assert snapshot.rows == rows
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    assert next(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig")))) == list(COLUMNS)


def test_append_rows_rejects_duplicate_stable_id(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "issues.csv"
    append_rows(path, (row("XN-1", "西宁", 101.77, 36.62),))
    # When / Then
    with pytest.raises(CsvStoreError, match="duplicate"):
        append_rows(path, (row("XN-1", "西宁", 101.77, 36.62),))


def test_delete_row_removes_only_stable_id(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "issues.csv"
    rows = (row("XN-1", "西宁", 101.77, 36.62), row("GL-1", "格尔木", 94.90, 36.40))
    append_rows(path, rows)
    # When
    delete_row(path, "XN-1")
    # Then
    assert tuple(item.id for item in read_snapshot(path).rows) == ("GL-1",)


def test_update_row_replaces_target_without_changing_stable_id(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "issues.csv"
    original = row("XN-1", "西宁", 101.77, 36.62)
    other = row("GL-1", "格尔木", 94.90, 36.40)
    append_rows(path, (original, other))
    replacement = original.model_copy(update={"street": "长江路", "description": "已编辑"})
    # When
    update_row(path, "XN-1", replacement)
    # Then
    updated = read_snapshot(path).rows
    assert updated[0].id == "XN-1"
    assert updated[0].street == "长江路"
    assert updated[0].description == "已编辑"
    assert updated[1] == other
    assert path.read_bytes().startswith(b"\xef\xbb\xbf")


def test_update_row_rejects_missing_or_changed_stable_id(tmp_path: Path) -> None:
    # Given
    path = tmp_path / "issues.csv"
    original = row("XN-1", "西宁", 101.77, 36.62)
    append_rows(path, (original,))
    # When / Then
    with pytest.raises(CsvStoreError, match="not_found"):
        update_row(path, "missing", original)
    with pytest.raises(CsvStoreError, match="stable ID"):
        update_row(path, "XN-1", row("other", "西宁", 101.77, 36.62))

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

from gis_data import CsvDatasetError, Dataset, GisRow, parse_csv_bytes

COLUMNS = (
    "id", "city", "district", "street", "longitude", "latitude",
    "problem_type", "description",
    "detected_at", "data_source",
)


def csv_bytes(*rows: tuple[str, ...], bom: bool = False) -> bytes:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(COLUMNS)
    writer.writerows(rows)
    payload = stream.getvalue().encode()
    return b"\xef\xbb\xbf" + payload if bom else payload


def valid_rows() -> tuple[tuple[str, ...], tuple[str, ...]]:
    return (
        ("XN-1", "西宁", "城西区", "五四大街", "101.77", "36.62", "盲道占用", "占用盲道", "2026-07-01T03:07:11", "上传数据"),
        ("GL-1", "格尔木", "昆仑路街道", "昆仑路", "94.90", "36.40", "规划问题", "线路中断", "2026-07-02 10:20:16", "上传数据"),
    )


def replace(row: tuple[str, ...], field: str, value: str) -> tuple[str, ...]:
    values = list(row)
    values[COLUMNS.index(field)] = value
    return tuple(values)


def too_many_rows() -> bytes:
    first, second = valid_rows()
    rows = tuple(
        replace(first if index % 2 == 0 else second, "id", f"ID-{index}")
        for index in range(5001)
    )
    return csv_bytes(*rows)


def test_empty_csv_with_schema_is_a_valid_empty_dataset() -> None:
    # Given
    payload = csv_bytes(bom=True)
    # When
    dataset = parse_csv_bytes(payload, require_both_cities=False)
    # Then
    assert dataset.rows == ()


def test_parse_accepts_utf8_and_bom_when_dataset_is_valid() -> None:
    # Given
    plain = csv_bytes(*valid_rows())
    with_bom = csv_bytes(*valid_rows(), bom=True)
    # When
    datasets = (parse_csv_bytes(plain), parse_csv_bytes(with_bom))
    # Then
    assert all(isinstance(dataset, Dataset) for dataset in datasets)
    assert datasets[0].rows == datasets[1].rows
    assert datasets[0].rows[0].longitude == 101.77


def test_parse_trims_and_accepts_unknown_taxonomy_values() -> None:
    # Given
    row = valid_rows()[0]
    payload = csv_bytes(
        replace(row, "problem_type", "  路口遮挡  "),
        valid_rows()[1],
    )
    # When
    parsed = parse_csv_bytes(payload)
    # Then
    assert parsed.rows[0].problem_type == "路口遮挡"
    assert parsed.rows[0].description == "占用盲道"


def test_parse_accepts_empty_description() -> None:
    first, second = valid_rows()
    parsed = parse_csv_bytes(csv_bytes(replace(first, "description", ""), second))
    assert parsed.rows[0].description == ""


def test_row_schema_contains_only_current_fields() -> None:
    assert tuple(GisRow.model_fields) == COLUMNS


@pytest.mark.parametrize(
    ("payload", "code"),
    [
        (csv_bytes(*valid_rows()).replace(b"data_source", b"source"), "columns"),
        (b"x" * (5 * 1024 * 1024 + 1), "file_size"),
        (too_many_rows(), "row_count"),
        (csv_bytes(valid_rows()[0]), "cities"),
        (csv_bytes(valid_rows()[0], replace(valid_rows()[1], "id", "XN-1")), "duplicate_id"),
        (csv_bytes(replace(valid_rows()[0], "city", "北京"), valid_rows()[1]), "row"),
        (csv_bytes(replace(valid_rows()[0], "problem_type", "   "), valid_rows()[1]), "row"),
        (csv_bytes(replace(valid_rows()[0], "longitude", "nan"), valid_rows()[1]), "row"),
        (csv_bytes(replace(valid_rows()[0], "latitude", "91"), valid_rows()[1]), "row"),
        (csv_bytes(replace(valid_rows()[0], "longitude", "100"), valid_rows()[1]), "row"),
        (csv_bytes(replace(valid_rows()[0], "detected_at", "yesterday"), valid_rows()[1]), "row"),
    ],
    ids=(
        "columns", "file-size", "row-count", "both-cities", "duplicate-id",
        "city-enum", "problem-empty", "finite-coordinate", "wgs84-coordinate",
        "city-coordinate", "iso-timestamp",
    ),
)
def test_parse_rejects_invalid_uploads_with_specific_error(payload: bytes, code: str) -> None:
    # Given / When
    with pytest.raises(CsvDatasetError) as captured:
        parse_csv_bytes(payload)
    # Then
    assert captured.value.code == code


def test_parse_rejects_rows_with_extra_values() -> None:
    # Given
    lines = csv_bytes(*valid_rows()).splitlines(keepends=True)
    payload = lines[0] + lines[1].rstrip(b"\r\n") + b",unexpected\n" + b"".join(lines[2:])
    # When / Then
    with pytest.raises(CsvDatasetError) as captured:
        parse_csv_bytes(payload)
    assert captured.value.code == "row"

"""Typed CSV boundary and immutable GIS dataset values."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from pydantic_core import PydanticCustomError

from gis_common import CITY_BOUNDS, COLUMNS

MAX_CSV_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 5_000
EXPECTED_COLUMNS: Final = tuple(COLUMNS)


class City(StrEnum):
    XINING = "西宁"
    GOLMUD = "格尔木"


class ProblemType(StrEnum):
    OCCUPIED = "盲道占用"
    DAMAGED = "盲道破损"
    PLANNING = "规划问题"


Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
NonEmpty = Annotated[str, Field(min_length=1)]


class GisRow(BaseModel):
    """One parsed GIS issue row from an untrusted CSV."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: NonEmpty
    city: City
    district: NonEmpty
    street: NonEmpty
    longitude: Longitude
    latitude: Latitude
    problem_type: NonEmpty
    description: str = ""
    detected_at: datetime
    data_source: NonEmpty

    @model_validator(mode="after")
    def validate_row_contract(self) -> GisRow:
        bounds = CITY_BOUNDS[self.city.value]
        longitude_min, longitude_max = bounds["lon"]
        latitude_min, latitude_max = bounds["lat"]
        if not longitude_min <= self.longitude <= longitude_max:
            raise PydanticCustomError("city_bounds", "longitude is outside the selected city")
        if not latitude_min <= self.latitude <= latitude_max:
            raise PydanticCustomError("city_bounds", "latitude is outside the selected city")
        return self


@dataclass(frozen=True, slots=True)
class Dataset:
    """Validated immutable GIS records."""

    rows: tuple[GisRow, ...]


@dataclass(frozen=True, slots=True)
class CsvDatasetError(Exception):
    """A specific upload contract failure."""

    code: str
    detail: str
    row_number: int | None = None

    def __str__(self) -> str:
        location = "" if self.row_number is None else f" at row {self.row_number}"
        return f"{self.code}{location}: {self.detail}"


def parse_csv_bytes(payload: bytes, *, require_both_cities: bool = True) -> Dataset:
    """Parse untrusted UTF-8 CSV bytes into a fully validated dataset."""
    if len(payload) > MAX_CSV_BYTES:
        raise CsvDatasetError("file_size", f"maximum is {MAX_CSV_BYTES} bytes")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise CsvDatasetError("encoding", "CSV must be UTF-8 or UTF-8 with BOM") from error

    reader = csv.DictReader(io.StringIO(text, newline=""))
    if tuple(reader.fieldnames or ()) != EXPECTED_COLUMNS:
        raise CsvDatasetError("columns", "CSV must contain the exact 10 columns in order")

    rows: list[GisRow] = []
    identifiers: set[str] = set()
    try:
        for row_number, raw_row in enumerate(reader, start=2):
            if row_number > MAX_ROWS + 1:
                raise CsvDatasetError("row_count", f"maximum is {MAX_ROWS} rows")
            if None in raw_row:
                raise CsvDatasetError("row", "CSV row contains more values than the 10-column schema", row_number)
            try:
                row = GisRow.model_validate(raw_row)
            except ValidationError as error:
                raise CsvDatasetError("row", str(error), row_number) from error
            if row.id in identifiers:
                raise CsvDatasetError("duplicate_id", row.id, row_number)
            identifiers.add(row.id)
            rows.append(row)
    except csv.Error as error:
        raise CsvDatasetError("csv", str(error)) from error

    if not rows:
        return Dataset(())
    if require_both_cities and {row.city for row in rows} != {City.XINING, City.GOLMUD}:
        raise CsvDatasetError("cities", "dataset must contain both 西宁 and 格尔木")
    return Dataset(tuple(rows))

"""Typed GCJ-02 coordinate values and explicit legacy WGS84 conversion."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from gis_common import CITY_BOUNDS, CITY_STREETS

PI = math.pi
AXIS = 6378245.0
ECCENTRICITY = 0.00669342162296594323


class InputCrs(StrEnum):
    """Supported coordinate reference systems at the workflow boundary."""

    GCJ02 = "gcj02"
    WGS84 = "wgs84"


@dataclass(frozen=True, slots=True)
class Coordinate:
    """Immutable longitude/latitude pair in the named input CRS."""

    longitude: float
    latitude: float


@dataclass(frozen=True, slots=True)
class LocationSuggestion:
    """Coordinate-derived city and street hints; district is intentionally absent."""

    city: str | None
    street: str | None
    district: None = None


CITY_DISTANCE_SCALE: Final = 111.0


def suggest_location(longitude: float, latitude: float) -> LocationSuggestion:
    """Suggest a bounded city and nearest configured street anchor."""
    for city, bounds in CITY_BOUNDS.items():
        longitude_min, longitude_max = bounds["lon"]
        latitude_min, latitude_max = bounds["lat"]
        if longitude_min <= longitude <= longitude_max and latitude_min <= latitude <= latitude_max:
            street = min(
                CITY_STREETS[city],
                key=lambda anchor: ((anchor["lon"] - longitude) * CITY_DISTANCE_SCALE) ** 2
                + (anchor["lat"] - latitude) ** 2,
            )
            return LocationSuggestion(city, str(street["name"]))
    return LocationSuggestion(None, None)


def _transform_latitude(x: float, y: float) -> float:
    return (-100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))) + (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0 + (20.0 * math.sin(y * PI) + 40.0 * math.sin(y / 3.0 * PI)) * 2.0 / 3.0 + (160.0 * math.sin(y / 12.0 * PI) + 320 * math.sin(y * PI / 30.0)) * 2.0 / 3.0


def _transform_longitude(x: float, y: float) -> float:
    return 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x)) + (20.0 * math.sin(6.0 * x * PI) + 20.0 * math.sin(2.0 * x * PI)) * 2.0 / 3.0 + (20.0 * math.sin(x * PI) + 40.0 * math.sin(x / 3.0 * PI)) * 2.0 / 3.0 + (150.0 * math.sin(x / 12.0 * PI) + 300.0 * math.sin(x / 30.0 * PI)) * 2.0 / 3.0


def _outside_china(coordinate: Coordinate) -> bool:
    return not (73.66 < coordinate.longitude < 135.05 and 3.86 < coordinate.latitude < 53.55)


def wgs84_to_gcj02(coordinate: Coordinate) -> Coordinate:
    """Convert one WGS84 coordinate to GCJ-02 using the canonical formula."""
    if _outside_china(coordinate):
        return coordinate
    d_lat = _transform_latitude(coordinate.longitude - 105.0, coordinate.latitude - 35.0)
    d_lon = _transform_longitude(coordinate.longitude - 105.0, coordinate.latitude - 35.0)
    rad_lat = coordinate.latitude / 180.0 * PI
    magic = 1.0 - ECCENTRICITY * math.sin(rad_lat) ** 2
    sqrt_magic = math.sqrt(magic)
    latitude_delta = d_lat * 180.0 / ((AXIS * (1.0 - ECCENTRICITY)) / (magic * sqrt_magic) * PI)
    longitude_delta = d_lon * 180.0 / (AXIS / sqrt_magic * math.cos(rad_lat) * PI)
    return Coordinate(coordinate.longitude + longitude_delta, coordinate.latitude + latitude_delta)

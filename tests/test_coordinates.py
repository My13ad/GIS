from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from coordinates import Coordinate, InputCrs, suggest_location, wgs84_to_gcj02


def test_wgs84_to_gcj02_matches_canonical_reference() -> None:
    # Given
    source = Coordinate(116.397, 39.908)
    # When
    converted = wgs84_to_gcj02(source)
    # Then
    assert converted.longitude == pytest.approx(116.40324337854781)
    assert converted.latitude == pytest.approx(39.90940335390724)


def test_coordinate_is_immutable_and_input_crs_is_explicit() -> None:
    # Given
    coordinate = Coordinate(101.778, 36.617)
    # When / Then
    with pytest.raises(AttributeError):
        coordinate.longitude = 1.0  # type: ignore[misc]
    assert InputCrs.GCJ02.value == "gcj02"


def test_suggest_location_returns_city_and_nearest_street() -> None:
    # Given
    # The point is exactly on the 西宁 street anchor for deterministic matching.
    # When
    suggestion = suggest_location(101.770, 36.620)
    # Then
    assert suggestion.city == "西宁"
    assert suggestion.street == "五四大街"
    assert suggestion.district is None


def test_suggest_location_returns_no_city_for_coordinates_outside_known_bounds() -> None:
    # Given
    # When
    suggestion = suggest_location(120.0, 30.0)
    # Then
    assert suggestion.city is None
    assert suggestion.street is None
    assert suggestion.district is None

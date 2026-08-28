from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from build_map import build_map, render_map_html
from export_png import (
    CityExport,
    ExportEngineError,
    ExportRequest,
    Renderers,
    export_artifacts,
    export_with_matplotlib,
)
from web_workflow import prepare_demo, prepare_upload
from test_gis_data import csv_bytes, valid_rows


VALID_FIXTURE = csv_bytes(*valid_rows(), bom=True)


def test_map_builder_renders_dataset_without_filesystem_output() -> None:
    # Given
    prepared = prepare_upload(VALID_FIXTURE)
    # When
    html = render_map_html(build_map(prepared.dataset))
    # Then
    assert html.startswith(b"<!DOCTYPE html>")
    assert b"new AMap.MarkerCluster" in html
    assert html.count(b'"id"') == 2


def test_upload_workflow_returns_typed_dataset_and_html_bytes() -> None:
    # Given
    payload = VALID_FIXTURE
    # When
    prepared = prepare_upload(payload)
    # Then
    assert len(prepared.dataset.rows) == 2
    assert b"new AMap.MarkerCluster" in prepared.html_bytes
    assert prepared.html_bytes.count(b'"id"') == 2


def test_upload_workflow_can_render_a_partial_city_dataset_for_canonical_storage() -> None:
    # Given / When
    lines = VALID_FIXTURE.splitlines(keepends=True)
    prepared = prepare_upload(lines[0] + lines[1], require_both_cities=False)
    # Then
    assert len(prepared.dataset.rows) == 1


def test_matplotlib_export_handles_a_city_without_records(tmp_path: Path) -> None:
    # Given
    request = ExportRequest(tmp_path / "map.html", tmp_path / "issues.csv", tmp_path)
    request.csv_path.write_bytes(VALID_FIXTURE.splitlines(keepends=True)[0] + VALID_FIXTURE.splitlines(keepends=True)[1])
    exports = (
        CityExport("西宁", 36.617, 101.778, tmp_path / "xining.png"),
        CityExport("格尔木", 36.407, 94.903, tmp_path / "golmud.png"),
    )
    # When / Then
    export_with_matplotlib(request, exports)
    assert all(item.path.stat().st_size > 10 * 1024 for item in exports)


def test_map_canvas_contains_only_leaflet_layer_controls() -> None:
    # Given / When
    html = prepare_upload(VALID_FIXTURE).html_bytes.decode()
    # Then
    assert "gis-title" not in html
    assert "gis-legend" not in html
    assert "gis-source" not in html
    assert "new AMap.MapType" in html


def test_export_artifacts_prefers_playwright_and_returns_static_bytes(tmp_path: Path) -> None:
    # Given
    calls: list[tuple[str, Path, Path]] = []

    def playwright(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
        calls.append(("playwright", request.html_path, request.csv_path))
        for name in ("西宁市_盲道问题GIS图.png", "格尔木市_盲道问题GIS图.png"):
            (request.output_dir / name).write_bytes(b"png")

    def fallback(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
        calls.append(("fallback", request.html_path, request.csv_path))

    html_path = tmp_path / "map.html"
    csv_path = tmp_path / "issues.csv"
    html_path.write_bytes(b"html")
    csv_path.write_bytes(b"csv")
    # When
    artifacts = export_artifacts(ExportRequest(html_path, csv_path, tmp_path), Renderers(playwright, fallback))
    # Then
    assert calls == [("playwright", html_path, csv_path)]
    assert tuple(artifact.content for artifact in artifacts) == (b"png", b"png")


def test_export_artifacts_falls_back_when_playwright_fails(tmp_path: Path) -> None:
    # Given
    calls: list[str] = []

    def playwright(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
        calls.append("playwright")
        raise ExportEngineError("playwright", "browser unavailable")

    def fallback(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
        calls.append("fallback")
        for name in ("西宁市_盲道问题GIS图.png", "格尔木市_盲道问题GIS图.png"):
            (request.output_dir / name).write_bytes(b"fallback")

    # When
    request = ExportRequest(tmp_path / "map.html", tmp_path / "issues.csv", tmp_path)
    artifacts = export_artifacts(request, Renderers(playwright, fallback))
    # Then
    assert calls == ["playwright", "fallback"]
    assert tuple(artifact.content for artifact in artifacts) == (b"fallback", b"fallback")

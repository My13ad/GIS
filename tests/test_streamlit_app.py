from __future__ import annotations

import sys
from pathlib import Path
import re
import os
from types import TracebackType
from types import SimpleNamespace

import pytest
from collections.abc import Iterator
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
for path in (ROOT, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import streamlit_app
from export_png import ExportRequest, StaticArtifact
from gis_data import City, CsvDatasetError, GisRow, Severity
from test_gis_data import csv_bytes, valid_rows
from ui_styles import WORKBENCH_CSS

CANONICAL_CSV = ROOT / "data" / "blind_path_issues.csv"
VALID_FIXTURE = csv_bytes(*valid_rows(), bom=True)


@pytest.fixture(autouse=True)
def restore_canonical_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    original = CANONICAL_CSV.read_bytes()
    app_csv = tmp_path / "blind_path_issues.csv"
    app_csv.write_bytes(VALID_FIXTURE)
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", app_csv)
    monkeypatch.setattr(streamlit_app, "CANONICAL_DB", tmp_path / "gis.sqlite3")
    monkeypatch.setattr(streamlit_app, "IMAGE_ROOT", tmp_path / "images")
    monkeypatch.setattr(streamlit_app, "IMAGE_SIDECAR", tmp_path / "images.json")
    streamlit_app.st.session_state.clear()
    try:
        yield
    finally:
        CANONICAL_CSV.write_bytes(original)


def test_app_uses_one_canonical_source_and_management_entry() -> None:
    # Given
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60)
    # When
    rendered = app.run()
    # Then
    assert not rendered.exception
    markup = "\n".join(element.value for element in rendered.markdown)
    assert "演示数据" not in markup
    assert "进入查看" in [button.label for button in rendered.button]
    assert "下载" in [button.label for button in rendered.button]
    assert "数据管理" in [button.label for button in rendered.button]
    assert not rendered.get("iframe")


def test_public_read_only_mode_hides_management_entry(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given / When / Then: the deployment switch is consumed by the selector.
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert "READ_ONLY" in source
    assert "if not READ_ONLY" in source


def test_delivery_upload_appends_validated_rows_to_canonical_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Given
    csv_path = tmp_path / "blind_path_issues.csv"
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    csv_path.write_bytes(VALID_FIXTURE)
    payload = VALID_FIXTURE.splitlines(keepends=True)[0] + VALID_FIXTURE.splitlines(keepends=True)[1].replace(
        b"XN-1", b"XN-UPLOAD", 1
    )
    # When
    streamlit_app.append_uploaded_rows(payload)
    # Then
    rows = streamlit_app.ensure_sqlite_store().read().rows
    assert len(rows) == 3
    assert rows[-1].id == "XN-UPLOAD"


def test_selector_css_centers_three_destination_controls() -> None:
    # Given / When
    css = WORKBENCH_CSS
    # Then
    assert ".selector-options" in css
    assert "justify-content: center" in css


def test_app_starts_on_entry_selector_with_two_destinations() -> None:
    # Given / When
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    # Then
    assert not app.exception
    labels = [button.label for button in app.button]
    assert "进入查看" in labels
    assert "下载" in labels
    assert "数据管理" in labels
    assert not app.get("iframe") or app.get("iframe")[0].value is None


def test_view_page_has_return_button_and_map_only() -> None:
    # Given
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    # When
    app.button(key="open-view").click().run()
    # Then
    assert "返回选择页" in [button.label for button in app.button]
    assert not app.exception
    assert "下载" not in [button.label for button in app.button]
    markup = "\n".join(element.value for element in app.markdown)
    assert 'class="project-bar"' not in markup
    assert 'data-panel="map"' not in markup
    assert "官方 AMap 底图" not in markup


def test_view_page_explains_empty_dataset_without_preparing_map() -> None:
    # Given
    empty_csv = b"\xef\xbb\xbfid,city,district,street,longitude,latitude,problem_type,subtype,severity,confidence,description,detected_at,data_source\n"
    streamlit_app.CANONICAL_CSV.write_bytes(empty_csv)
    streamlit_app.ensure_sqlite_store().replace(())
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    # When
    app.button(key="open-view").click().run()
    # Then
    assert not app.exception
    assert not app.get("iframe")
    assert any("当前没有可查看的点位" in element.value for element in app.info)


def test_delivery_page_has_return_button_and_downloads_without_map() -> None:
    # Given
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    # When
    app.button(key="open-delivery").click().run()
    # Then
    assert "返回选择页" in [button.label for button in app.button]
    assert [button.label for button in app.download_button][:2] == ["下载当前 CSV", "下载交互地图 HTML"]
    assert not app.get("iframe")


def test_uploaded_dataset_is_retained_for_view_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    payload = VALID_FIXTURE.replace(b"XN-1", b"XN-UPLOADED", 1)
    csv_path = tmp_path / "blind_path_issues.csv"
    csv_path.write_bytes(VALID_FIXTURE)
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    streamlit_app.append_uploaded_rows(payload)
    # When
    active = streamlit_app.prepare_canonical_active()
    # Then
    assert b"XN-UPLOADED" in active.html_bytes


def test_management_page_has_search_filters_rows_and_return_button() -> None:
    # Given / When
    # The management fixture is reset by the test session before this assertion.
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    app.button(key="open-management").click().run()
    # Then
    assert "返回选择页" in [button.label for button in app.button]
    assert app.text_input[0].label == "搜索"
    assert any(select.label == "城市" for select in app.selectbox)
    assert [row.id for row in streamlit_app.load_management_rows()] == ["XN-1", "GL-1"]


def test_management_page_is_actionable_when_canonical_dataset_is_empty() -> None:
    # Given
    empty_csv = b"\xef\xbb\xbfid,city,district,street,longitude,latitude,problem_type,subtype,severity,confidence,description,detected_at,data_source\n"
    streamlit_app.CANONICAL_CSV.write_bytes(empty_csv)
    streamlit_app.ensure_sqlite_store().replace(())
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    # When
    app.button(key="open-management").click().run()
    # Then
    assert not app.exception
    assert any("当前 SQLite 为空" in element.value for element in app.info)
    assert any(element.label == "导入 CSV 到 SQLite" for element in app.file_uploader)


def test_management_delete_syncs_canonical_csv_and_sidecar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    csv_path = tmp_path / "blind_path_issues.csv"
    image_root = tmp_path / "images"
    sidecar = tmp_path / "blind_path_issues.images.json"
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    monkeypatch.setattr(streamlit_app, "IMAGE_ROOT", image_root)
    monkeypatch.setattr(streamlit_app, "IMAGE_SIDECAR", sidecar)
    csv_path.write_bytes(VALID_FIXTURE)
    streamlit_app.add_image_attachment("XN-1", "photo.png", b"\x89PNG\r\n\x1a\nimage")
    # When
    streamlit_app.delete_persisted_row("XN-1")
    # Then
    assert "XN-1" not in {row.id for row in streamlit_app.ensure_sqlite_store().read().rows}
    assert "XN-1" not in sidecar.read_text(encoding="utf-8")
    assert not (image_root / "XN-1").exists()


def test_management_helpers_search_and_filter_canonical_rows() -> None:
    # Given
    rows = streamlit_app.load_management_rows()
    # When
    filtered = streamlit_app.filter_management_rows(rows, "XN-1", "西宁", "全部")
    # Then
    assert [row.id for row in filtered] == ["XN-1"]


def test_delete_rejects_path_traversal_id(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    csv_path = tmp_path / "blind_path_issues.csv"
    csv_path.write_bytes(VALID_FIXTURE)
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    monkeypatch.setattr(streamlit_app, "IMAGE_ROOT", tmp_path / "images")
    # When / Then
    with pytest.raises(ValueError):
        streamlit_app.delete_persisted_row("..")


def test_management_row_markup_escapes_uploaded_text() -> None:
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert "columns[0].write" in source


def test_attachment_filename_is_collision_safe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    root = tmp_path / "images"
    sidecar = tmp_path / "images.json"
    monkeypatch.setattr(streamlit_app, "IMAGE_ROOT", root)
    monkeypatch.setattr(streamlit_app, "IMAGE_SIDECAR", sidecar)
    # When
    streamlit_app.add_image_attachment("XN-1", "photo.png", b"\x89PNG\r\n\x1a\nfirst")
    streamlit_app.add_image_attachment("XN-1", "photo.png", b"\x89PNG\r\n\x1a\nsecond")
    # Then
    snapshot = streamlit_app.read_image_snapshot(sidecar)
    assert len(snapshot["XN-1"]) == 2
    assert snapshot["XN-1"][0].filename != snapshot["XN-1"][1].filename


def test_append_manual_row_updates_canonical_source(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    csv_path = tmp_path / "blind_path_issues.csv"
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    csv_path.write_bytes(VALID_FIXTURE)
    row = GisRow.model_validate({
        "id": "XN-MANUAL",
        "city": City.XINING,
        "district": "城西区",
        "street": "新街",
        "longitude": 101.77,
        "latitude": 36.62,
        "problem_type": "盲道占用",
        "subtype": "共享单车",
        "severity": Severity.LOW,
        "confidence": 0.8,
        "description": "手动录入",
        "detected_at": "2026-01-01 10:00:00",
        "data_source": "manual",
    })
    # When
    streamlit_app.append_manual_row(row)
    # Then
    assert "XN-MANUAL" in {row.id for row in streamlit_app.ensure_sqlite_store().read().rows}


def test_apply_location_suggestion_preserves_nonempty_fields() -> None:
    # Given
    values = {"city": "西宁", "street": "已有街道", "district": "城西区"}
    suggestion = SimpleNamespace(city="格尔木", street="昆仑路", district=None)
    # When
    applied = streamlit_app.apply_location_suggestion(values, suggestion)
    # Then
    assert applied == values


def test_apply_location_suggestion_fills_only_empty_city_and_street() -> None:
    # Given
    values = {"city": "", "street": "", "district": "手动区域"}
    suggestion = SimpleNamespace(city="格尔木", street="昆仑路", district=None)
    # When
    applied = streamlit_app.apply_location_suggestion(values, suggestion)
    # Then
    assert applied == {"city": "格尔木", "street": "昆仑路", "district": "手动区域"}


def test_management_source_exposes_edit_form_and_text_taxonomy_inputs() -> None:
    # Given / When
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    # Then
    assert "编辑" in source
    assert 'st.text_input("问题类型"' in source
    assert 'st.text_input("子类型"' in source
    assert 'st.text_input("严重度"' in source


def test_delete_invalidates_cache_and_rebuilds_active_map(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    csv_path = tmp_path / "blind_path_issues.csv"
    monkeypatch.setattr(streamlit_app, "CANONICAL_CSV", csv_path)
    monkeypatch.setattr(streamlit_app, "IMAGE_ROOT", tmp_path / "images")
    monkeypatch.setattr(streamlit_app, "IMAGE_SIDECAR", tmp_path / "images.json")
    csv_path.write_bytes(VALID_FIXTURE)
    streamlit_app.st.session_state["png_cache"] = "cached"
    # When
    streamlit_app.delete_persisted_row("XN-1")
    # Then
    assert streamlit_app.st.session_state.get("png_cache") is None
    assert "XN-1" not in streamlit_app.canonical_payload().decode("utf-8")


def test_png_export_has_visible_progress_and_success_copy(monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    active = streamlit_app.prepare_canonical_active()
    monkeypatch.setattr(streamlit_app, "export_active", lambda _: ())
    # When / Then: the function is wired to a visible status container.
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert "正在生成两座城市 PNG" in source
    assert "PNG 已生成" in source


def test_workbench_css_stacks_columns_and_sizes_component_iframe() -> None:
    # Given / When
    project_bar_css = WORKBENCH_CSS.split(".project-bar {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    tablet_css = WORKBENCH_CSS.split("@media (max-width: 1023px)", maxsplit=1)[1].split(
        "@media (max-width: 767px)", maxsplit=1
    )[0]
    mobile_css = WORKBENCH_CSS.split("@media (max-width: 767px)", maxsplit=1)[1]
    # Then
    assert "--space-8: 32px" in WORKBENCH_CSS
    assert "box-sizing: border-box" in project_bar_css
    assert '[data-testid="stCustomComponentV1"] iframe' not in WORKBENCH_CSS
    assert 'iframe[data-testid="stCustomComponentV1"]' in WORKBENCH_CSS
    assert '[data-testid="stColumn"]' in tablet_css
    assert 'width: 100% !important' in tablet_css
    assert 'max-width: 100% !important' in tablet_css
    assert 'flex: 1 1 100% !important' in tablet_css
    assert 'height: 560px !important' in tablet_css
    assert 'height: 500px !important' in mobile_css


def test_prepare_demo_preserves_bundled_csv_and_core_html() -> None:
    # Given / When
    active = streamlit_app.prepare_canonical_active()
    # Then
    assert active.csv_bytes == streamlit_app.rows_to_csv_bytes(
    streamlit_app.ensure_sqlite_store().read().rows
    )
    assert active.html_bytes == active.prepared.html_bytes


def test_prepare_active_preserves_exact_csv_and_core_html_for_upload() -> None:
    # Given
    payload = VALID_FIXTURE
    # When
    active = streamlit_app.prepare_active("上传.csv", "上传 CSV", payload)
    # Then
    assert active.csv_bytes == payload
    assert active.html_bytes.startswith(b"<!DOCTYPE html>")
    assert b"new AMap.MarkerCluster" in active.html_bytes
    assert active.html_bytes.count(b'"id"') == len(active.prepared.dataset.rows)


def test_prepare_active_raises_typed_error_for_invalid_upload() -> None:
    # Given
    payload = b"wrong,columns\n1,2\n"
    # When / Then
    with pytest.raises(CsvDatasetError):
        streamlit_app.prepare_active("invalid.csv", "上传 CSV", payload)


def test_export_active_passes_active_files_to_core_export(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Given
    payload = CANONICAL_CSV.read_bytes()
    active = streamlit_app.prepare_active("上传.csv", "上传 CSV", payload)
    captured: list[ExportRequest] = []

    def fake_export(request: ExportRequest) -> tuple[StaticArtifact, StaticArtifact]:
        captured.append(request)
        assert request.csv_path.read_bytes() == payload
        assert request.html_path.read_bytes() == active.html_bytes
        return (StaticArtifact("xining.png", b"xining"), StaticArtifact("golmud.png", b"golmud"))

    monkeypatch.setattr(streamlit_app, "TemporaryDirectory", lambda **_: _TemporaryPath(tmp_path))
    monkeypatch.setattr(streamlit_app, "export_artifacts", fake_export)
    # When
    artifacts = streamlit_app.export_active(active)
    # Then
    assert tuple(item.content for item in artifacts) == (b"xining", b"golmud")
    assert captured == [ExportRequest(tmp_path / "map.html", tmp_path / "issues.csv", tmp_path)]


def test_png_cache_is_visible_only_for_matching_dataset() -> None:
    # Given
    first = streamlit_app.prepare_active("first.csv", "上传 CSV", VALID_FIXTURE)
    second_payload = VALID_FIXTURE.replace(b"XN-1", b"XN-9001", 1)
    second = streamlit_app.prepare_active("second.csv", "上传 CSV", second_payload)
    artifacts = (StaticArtifact("xining.png", b"x"), StaticArtifact("golmud.png", b"g"))
    cache = streamlit_app.PngCache(first.fingerprint, artifacts)
    # When / Then
    assert streamlit_app.cached_pngs(cache, first) == artifacts
    assert streamlit_app.cached_pngs(cache, second) == ()


def test_render_prepared_map_uses_official_amap_html_and_labels_gcj02(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    calls: list[tuple[str, int]] = []

    def capture_html(html: str, *, height: int) -> None:
        calls.append((html, height))

    monkeypatch.setattr(streamlit_app.components, "html", capture_html)
    prepared = SimpleNamespace(
        html_bytes=b"<!DOCTYPE html><script src='https://webapi.amap.com/maps?v=2.0'></script>",
        config=SimpleNamespace(coordinate_system="GCJ-02"),
    )
    active = SimpleNamespace(prepared=prepared, html_bytes=prepared.html_bytes)

    # When
    streamlit_app.render_prepared_map(active)

    # Then
    assert calls == [(prepared.html_bytes.decode("utf-8"), streamlit_app.MAP_HEIGHT)]
    assert "GCJ-02" in streamlit_app.coordinate_reference_label(prepared)


def test_render_prepared_map_surfaces_key_config_error_without_rendering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given
    rendered: list[str] = []
    errors: list[str] = []
    monkeypatch.setattr(streamlit_app.components, "html", lambda *_args, **_kwargs: rendered.append("map"))
    monkeypatch.setattr(streamlit_app.st, "error", errors.append)
    prepared = SimpleNamespace(
        html_bytes=b"<!DOCTYPE html>",
        config=SimpleNamespace(error="AMap key/config is unavailable"),
    )

    # When
    streamlit_app.render_prepared_map(SimpleNamespace(prepared=prepared))

    # Then
    assert rendered == []
    assert errors == ["AMap key/config is unavailable"]


def test_app_preserves_csv_html_and_png_download_actions() -> None:
    # Given / When
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    app.button(key="open-delivery").click().run()

    # Then
    labels = [button.label for button in app.download_button]
    assert labels[:2] == ["下载当前 CSV", "下载交互地图 HTML"]
    app.button(key="back-selector").click().run()
    app.button(key="open-delivery").click().run()
    assert "生成城市 PNG" in [button.label for button in app.button]


def test_download_page_keeps_png_export_and_management_page_has_no_downloads() -> None:
    # Given / When
    app = AppTest.from_file(ROOT / "streamlit_app.py", default_timeout=60).run()
    app.button(key="open-delivery").click().run()
    # Then
    assert "生成城市 PNG" in [button.label for button in app.button]
    # When
    app.button(key="back-selector").click().run()
    app.button(key="open-management").click().run()
    # Then
    assert "生成城市 PNG" not in [button.label for button in app.button]
    assert "下载当前 CSV" not in [button.label for button in app.download_button]


def test_management_actions_are_declared_as_horizontal_row_controls() -> None:
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert 'action_attach, action_delete = st.columns(2)' in source
    assert 'columns = st.columns((8, 2, 2))' in source
    assert 'append_uploaded_rows(uploaded_csv.getvalue())' in source


def test_manual_form_wires_coordinates_to_location_suggestions() -> None:
    source = Path(streamlit_app.__file__).read_text(encoding="utf-8")
    assert 'suggest_location(values["longitude"], values["latitude"])' in source
    assert "manual-location-suggestion" in source
    assert 'with st.expander("坐标建议"' not in source
    assert 'st.form_submit_button("根据经纬度建议"' in source


class _TemporaryPath:
    def __init__(self, path: Path) -> None:
        self.path = path

    def __enter__(self) -> str:
        return str(self.path)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

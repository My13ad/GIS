from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from amap_html import build_amap_html
from amap_config import AMapConfig
from gis_data import Dataset, GisRow, parse_csv_bytes
from image_store import ImageMetadata
from test_gis_data import csv_bytes, valid_rows

VALID_DATASET = parse_csv_bytes(csv_bytes(*valid_rows(), bom=True))


def test_build_amap_html_uses_official_amap_runtime_and_json_payload() -> None:
    # Given
    dataset = VALID_DATASET
    # When
    html = build_amap_html(dataset, AMapConfig("public-key", "security-code"))
    # Then
    assert '<div id="amap-map"></div>' in html
    assert "https://webapi.amap.com/maps?v=2.0" in html
    assert "new AMap.Map" in html
    assert "new AMap.MarkerCluster" in html
    assert "window.__AMAP_DATA__=clusterData" in html
    assert "const clusterData=AMAP_DATA.map(item=>({lnglat:[item.longitude,item.latitude],count:item.weight,data:item}))" in html
    assert "gridSize:60" in html
    assert "maxZoom:20" in html
    assert "zoomOnClick:true" in html
    assert "averageCenter:true" in html
    assert "CLUSTER_EXPAND_ZOOM" not in html
    assert "cluster.setMap(null)" not in html
    assert "map.add(individualMarkers)" not in html
    assert "window.__AMAP_MAP__" in html
    assert "window.__AMAP_CLUSTER__" in html
    assert "zoom:11,center:[101.778,36.617]" in html
    assert "new AMap.InfoWindow" in html
    assert "context.marker.on('click'" in html
    assert "Array.isArray(context.data)?context.data[0]?.data" in html
    assert "new AMap.HeatMap" in html
    assert "new AMap.ToolBar" in html
    assert "new AMap.Scale" in html
    assert "new AMap.MapType" in html
    assert "window.__AMAP_READY__" in html
    assert "window.__AMAP_ERROR__" in html
    assert "window.__setExportView" in html
    assert html.count('"id"') == 2


def test_build_amap_html_escapes_popup_data() -> None:
    # Given
    dataset = VALID_DATASET
    # When
    html = build_amap_html(dataset, AMapConfig("public-key", "security-code"))
    # Then
    assert "L.marker" not in html
    assert "<script>" in html


def test_build_amap_html_escapes_script_terminators_in_row_text() -> None:
    # Given
    row = VALID_DATASET.rows[0].model_copy(update={"description": "</script><script>alert(1)</script>"})
    # When
    html = build_amap_html(Dataset((row,)), AMapConfig("public-key", "security-code"))
    # Then
    assert "</script><script>alert(1)</script>" not in html
    assert "&lt;/script&gt;&lt;script&gt;" in html


def test_build_amap_html_embeds_attached_image_in_popup(tmp_path: Path) -> None:
    # Given
    dataset = VALID_DATASET
    image_root = tmp_path / "images"
    image_path = image_root / "XN-1" / "photo.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"\x89PNG\r\n\x1a\nimage")
    metadata = ImageMetadata("XN-1", "photo.png", "image/png", image_path.stat().st_size, "0" * 64, "XN-1/photo.png")
    # When
    html = build_amap_html(
        dataset,
        AMapConfig("public-key", "security-code"),
        {"XN-1": (metadata,)},
        image_root,
    )
    # Then
    assert "data:image/png;base64" in html


def test_build_amap_html_uses_payload_values_and_deterministic_unknown_fallbacks() -> None:
    # Given
    row = GisRow.model_validate({
        "id": "XN-CUSTOM",
        "city": "西宁",
        "district": "城西区",
        "street": "新街",
        "longitude": 101.77,
        "latitude": 36.62,
        "problem_type": "路口遮挡",
        "subtype": "临时施工",
        "severity": "紧急",
        "confidence": 0.8,
        "description": "自定义分类",
        "detected_at": "2026-01-01 10:00:00",
        "data_source": "manual",
    })
    # When
    html = build_amap_html(Dataset((row,)), AMapConfig("public-key", "security-code"))
    # Then
    assert '"problem_type":"路口遮挡"' in html
    assert '"subtype":"临时施工"' in html
    assert '"severity":"紧急"' in html
    assert '"color":"gray"' in html
    assert '"weight":0.5' in html
    assert "count:item.weight" in html
    assert "background:${item.color}" in html

#!/usr/bin/env python3
"""Build the interactive official AMap JS map for blind-path issues.

Reads ``data/blind_path_issues.csv`` (frozen demo dataset, utf-8-sig) and
renders ``output/<Chinese-named>.html``:

- explicit OSM (default) + Esri World Imagery (toggleable) base tiles
- one Marker per CSV row, colored by problem_type, grouped per city inside
  FeatureGroup -> MarkerCluster so city toggling and clustering both work
- rich Chinese HTML popups with every CSV field
- a severity-weighted HeatMap overlay (hidden by default, toggleable)
- expanded LayerControl + fixed title / legend / disclaimer overlays

Console output is ASCII-only (GBK console); Chinese lives in the HTML file.
"""

import sys
from html import escape
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = _ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

from gis_common import CITY_BOUNDS, SEVERITY_WEIGHT  # noqa: E402
from gis_data import Dataset, GisRow, parse_csv_bytes  # noqa: E402
from amap_config import AMapConfig, load_amap_config  # noqa: E402
from amap_html import build_amap_html  # noqa: E402
from image_store import ImageMetadata  # noqa: E402

DATA_CSV = _ROOT / "data" / "blind_path_issues.csv"
OUTPUT_DIR = _ROOT / "output"
OUTPUT_HTML = OUTPUT_DIR / "盲道问题GIS标注图.html"

PROBLEM_COLORS = {"盲道占用": "orange", "盲道破损": "red", "规划问题": "purple"}

POPUP_FIELDS = [
    ("编号", "id"),
    ("城市", "city"),
    ("区域", "district"),
    ("街道", "street"),
    ("问题类型", "problem_type"),
    ("子类型", "subtype"),
    ("严重程度", "severity"),
    ("置信度", "confidence"),
    ("描述", "description"),
    ("检测时间", "detected_at"),
    ("数据来源", "data_source"),
]

def load_dataset(path: Path = DATA_CSV) -> Dataset:
    """Load and validate a CSV dataset for the legacy CLI."""
    if not path.exists():
        raise SystemExit(f"ERROR: input CSV not found: {path}")
    return parse_csv_bytes(path.read_bytes())


def build_popup_html(row: GisRow) -> str:
    """Rich Chinese popup: every CSV field with a bold label."""
    lines = "".join(
        "<tr>"
        f'<td style="padding:1px 10px 1px 0;color:#5a6b7b;white-space:nowrap;'
        f'vertical-align:top;"><b>{label}</b></td>'
        f'<td style="color:#22303c;">{escape(str(value))}</td>'
        "</tr>"
        for label, key in POPUP_FIELDS
        for value in (getattr(row, key),)
    )
    return (
        "<div style=\"font-family:'Microsoft YaHei','SimHei',sans-serif;"
        'font-size:13px;line-height:1.6;min-width:240px;">'
        f'<table style="border-collapse:collapse;">{lines}</table>'
        "</div>"
    )


def build_map(
    dataset: Dataset,
    config: AMapConfig | None = None,
    attachments: dict[str, tuple[ImageMetadata, ...]] | None = None,
    image_root: Path | None = None,
) -> str:
    """Build the official AMap document from already validated GCJ-02 rows."""
    return build_amap_html(dataset, config or load_amap_config(_ROOT), attachments, image_root)


def render_map_html(html: str) -> bytes:
    """Encode an official AMap document as standalone UTF-8 HTML bytes."""
    return html.encode("utf-8")


def main() -> None:
    dataset = load_dataset()
    html_bytes = render_map_html(build_map(dataset))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_HTML.write_bytes(html_bytes)
    safe_name = OUTPUT_HTML.name.encode("unicode_escape").decode("ascii")
    print(f"[build_map] rows loaded: {len(dataset.rows)}")
    print(f"[build_map] wrote: output/{safe_name}")
    print(f"[build_map] size: {OUTPUT_HTML.stat().st_size} bytes")
    print(f"[build_map] AMap payload rows: {len(dataset.rows)}")
    print("[build_map] OK")


if __name__ == "__main__":
    main()

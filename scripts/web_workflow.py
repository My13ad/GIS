"""Reusable preparation workflow for the future Streamlit adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from build_map import build_map, render_map_html
from gis_data import Dataset, parse_csv_bytes
from coordinates import InputCrs
from amap_config import AMapConfig, load_amap_config
from image_store import ImageMetadata, read_image_snapshot


@dataclass(frozen=True, slots=True)
class PreparedMap:
    """Validated data and its standalone rendered map."""

    dataset: Dataset
    html_bytes: bytes
    config: AMapConfig | None = None


def prepare_upload(
    payload: bytes,
    input_crs: InputCrs = InputCrs.GCJ02,
    attachments: dict[str, tuple[ImageMetadata, ...]] | None = None,
    image_root: Path | None = None,
    require_both_cities: bool = True,
) -> PreparedMap:
    """Validate CSV bytes with an explicit CRS and render the corresponding map."""
    if input_crs is not InputCrs.GCJ02:
        raise ValueError("WGS84 upload conversion is not implicit; convert before CSV validation")
    dataset = parse_csv_bytes(payload, require_both_cities=require_both_cities)
    config = load_amap_config(Path(__file__).resolve().parents[1])
    return PreparedMap(dataset, render_map_html(build_map(dataset, config, attachments, image_root)), config)


def prepare_demo(csv_path: Path) -> PreparedMap:
    """Prepare the bundled demo CSV through the same trusted workflow."""
    return prepare_upload(csv_path.read_bytes())

"""Export city map PNGs through Playwright with a matplotlib fallback."""

from __future__ import annotations

import argparse
import csv
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from PIL import Image, ImageStat, UnidentifiedImageError

from gis_common import CITY_CENTERS

ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_HTML_PATH: Final = ROOT / "output" / "盲道问题GIS标注图.html"
DEFAULT_CSV_PATH: Final = ROOT / "data" / "blind_path_issues.csv"
DEFAULT_OUTPUT_DIR: Final = ROOT / "output"
VIEWPORT: Final = {"width": 1600, "height": 1000}
PNG_MINIMUM_BYTES: Final = 10 * 1024


@dataclass(frozen=True, slots=True)
class CityExport:
    city: str
    latitude: float
    longitude: float
    path: Path


@dataclass(frozen=True, slots=True)
class ExportRequest:
    html_path: Path
    csv_path: Path
    output_dir: Path


@dataclass(frozen=True, slots=True)
class StaticArtifact:
    filename: str
    content: bytes


class ExportEngineError(RuntimeError):
    """A typed static export failure."""

    def __init__(self, engine: str, detail: str) -> None:
        super().__init__(detail)
        self.engine = engine
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.engine}: {self.detail}"


class Renderer(Protocol):
    def __call__(self, request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None: ...


@dataclass(frozen=True, slots=True)
class Renderers:
    playwright: Renderer
    fallback: Renderer


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    """Serve a temporary map directory on localhost for browser loading."""
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def city_exports(output_dir: Path) -> tuple[CityExport, CityExport]:
    xining = CITY_CENTERS["西宁"]
    golmud = CITY_CENTERS["格尔木"]
    return (
        CityExport("西宁", *xining, output_dir / "西宁市_盲道问题GIS图.png"),
        CityExport("格尔木", *golmud, output_dir / "格尔木市_盲道问题GIS图.png"),
    )


def validate_png(path: Path) -> None:
    if path.stat().st_size <= PNG_MINIMUM_BYTES:
        raise ExportEngineError("validation", f"PNG below minimum size: {path}")
    try:
        with Image.open(path) as image:
            deviation = ImageStat.Stat(image.convert("L")).stddev[0]
            colors = image.convert("RGB").getcolors(maxcolors=10_000)
    except (OSError, UnidentifiedImageError) as error:
        raise ExportEngineError("validation", f"PNG cannot be read: {path}") from error
    distinct = 10_000 if colors is None else len(colors)
    if deviation <= 0 or distinct <= 3:
        raise ExportEngineError("validation", f"PNG appears blank: {path}")


def export_with_playwright(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
    """Render the supplied AMap HTML in Chromium at retina scale."""
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright

    if not request.html_path.exists():
        raise ExportEngineError("playwright", f"map HTML missing: {request.html_path}")
    server, server_thread = _serve_directory(request.output_dir)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport=VIEWPORT, device_scale_factor=2)
                page = context.new_page()
                url = f"http://127.0.0.1:{server.server_port}/{request.html_path.name}"
                page.goto(url, wait_until="networkidle", timeout=60_000)
                page.wait_for_function("() => window.__AMAP_READY__ === true", timeout=60_000)
                for city in exports:
                    page.evaluate("city => window.__setExportView(city)", city.city)
                    page.wait_for_timeout(5_000)
                    page.screenshot(path=str(city.path), full_page=False, scale="device")
                    validate_png(city.path)
            finally:
                browser.close()
    except (PlaywrightError, OSError, ExportEngineError) as error:
        raise ExportEngineError("playwright", str(error)) from error
    finally:
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=5)


def export_with_matplotlib(request: ExportRequest, exports: tuple[CityExport, CityExport]) -> None:
    """Render degraded static point plots from the parameterized CSV path."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as pyplot

    pyplot.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "DejaVu Sans"]
    pyplot.rcParams["axes.unicode_minus"] = False

    coordinates: dict[str, list[tuple[float, float]]] = {item.city: [] for item in exports}
    with request.csv_path.open(encoding="utf-8-sig", newline="") as csv_file:
        for row in csv.DictReader(csv_file):
            city_rows = coordinates.get(row["city"])
            if city_rows is not None:
                city_rows.append((float(row["longitude"]), float(row["latitude"])))
    for city in exports:
        figure, axis = pyplot.subplots(figsize=(8, 5), dpi=200)
        points = coordinates[city.city]
        if points:
            longitudes, latitudes = zip(*points, strict=True)
            axis.scatter(longitudes, latitudes, c="#d63031", alpha=0.7, s=45)
        else:
            axis.text(0.5, 0.5, "No records", ha="center", va="center", transform=axis.transAxes)
        axis.set(title=f"{city.city} City GIS Issue Distribution", xlabel="Longitude", ylabel="Latitude")
        axis.grid(alpha=0.25)
        figure.tight_layout()
        figure.savefig(city.path)
        pyplot.close(figure)
        validate_png(city.path)


def export_artifacts(request: ExportRequest, renderers: Renderers | None = None) -> tuple[StaticArtifact, StaticArtifact]:
    """Export both cities Playwright-first and return static artifact bytes."""
    request.output_dir.mkdir(parents=True, exist_ok=True)
    exports = city_exports(request.output_dir)
    selected = renderers or Renderers(export_with_playwright, export_with_matplotlib)
    try:
        selected.playwright(request, exports)
    except ExportEngineError:
        selected.fallback(request, exports)
    return tuple(StaticArtifact(item.path.name, item.path.read_bytes()) for item in exports)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export GIS map PNGs.")
    parser.add_argument("--engine", choices=("playwright", "matplotlib"), default="playwright")
    parser.add_argument("--html-path", type=Path, default=DEFAULT_HTML_PATH)
    parser.add_argument("--csv-path", type=Path, default=DEFAULT_CSV_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()
    request = ExportRequest(arguments.html_path, arguments.csv_path, arguments.output_dir)
    renderers = Renderers(export_with_playwright, export_with_matplotlib)
    if arguments.engine == "matplotlib":
        renderers = Renderers(export_with_matplotlib, export_with_matplotlib)
    artifacts = export_artifacts(request, renderers)
    print(f"engine: {arguments.engine}")
    for artifact in artifacts:
        print(f"png: {artifact.filename} {len(artifact.content)} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Operational Streamlit adapter for the reusable GIS core."""

from __future__ import annotations

import sys
import os
import shutil
import re
import hmac
from datetime import datetime
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Final

import streamlit as st
import streamlit.components.v1 as components


def _runtime_value(name: str) -> str:
    """Read deployment configuration from environment or Streamlit secrets."""
    value = os.environ.get(name)
    if value:
        return value
    try:
        secret = st.secrets.get(name, "")
    except Exception:
        return ""
    return "" if secret is None else str(secret)


for _secret_name in ("AMAP_KEY", "AMAP_SECURITY_CODE", "AMAP_JS_KEY", "AMAP_SECURITY_JS_CODE"):
    if not os.environ.get(_secret_name):
        _secret_value = _runtime_value(_secret_name)
        if _secret_value:
            os.environ[_secret_name] = _secret_value

ROOT: Final = Path(__file__).resolve().parent
SCRIPTS: Final = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from export_png import (  # noqa: E402
    ExportEngineError,
    ExportRequest,
    StaticArtifact,
    export_artifacts,
)
from coordinates import LocationSuggestion, suggest_location  # noqa: E402
from gis_data import City, CsvDatasetError, GisRow, parse_csv_bytes  # noqa: E402
from amap_config import AMapConfigError  # noqa: E402
from sqlite_store import SqliteRowStore, SqliteStoreError, migrate_csv_to_sqlite, rows_to_csv_bytes  # noqa: E402
from postgres_store import (  # noqa: E402
    PostgresRowStore,
    PostgresStoreError,
    migrate_csv_to_postgres,
)
from image_store import (  # noqa: E402
    ImageStoreError,
    read_image_snapshot,
    stage_image,
    write_image_snapshot,
)
from web_workflow import PreparedMap, prepare_upload  # noqa: E402
from ui_styles import render_styles  # noqa: E402

DATA_DIR: Final = Path(_runtime_value("GIS_DATA_DIR") or str(ROOT / "data"))
CANONICAL_CSV: Final = DATA_DIR / "blind_path_issues.csv"
CANONICAL_DB: Final = DATA_DIR / "gis.sqlite3"
READ_ONLY: Final = _runtime_value("GIS_READ_ONLY") == "1"
DATABASE_URL: Final = (_runtime_value("DATABASE_URL") or _runtime_value("SUPABASE_DB_URL")).strip()
ADMIN_CODE: Final = _runtime_value("GIS_ADMIN_CODE").strip()
IMAGE_ROOT: Final = DATA_DIR / "blind_path_issues.images"
IMAGE_SIDECAR: Final = DATA_DIR / "blind_path_issues.images.json"
MAP_HEIGHT: Final = 680
GCJ02_LABEL: Final = "GCJ-02"


@dataclass(frozen=True, slots=True)
class ActiveMap:
    """Exact source bytes paired with core-prepared typed data and HTML."""

    name: str
    source: str
    csv_bytes: bytes
    prepared: PreparedMap
    fingerprint: str

    @property
    def html_bytes(self) -> bytes:
        """Expose the exact core-rendered standalone HTML artifact."""
        return self.prepared.html_bytes


@dataclass(frozen=True, slots=True)
class PngCache:
    """Static artifacts scoped to one exact active dataset."""

    fingerprint: str
    artifacts: tuple[StaticArtifact, StaticArtifact]


def prepare_active(name: str, source: str, payload: bytes) -> ActiveMap:
    """Prepare uploaded bytes through the final reusable web workflow."""
    return ActiveMap(name, source, payload, prepare_upload(payload), sha256(payload).hexdigest())


RowStore = SqliteRowStore | PostgresRowStore
STORE_ERRORS = (SqliteStoreError, PostgresStoreError)
CSV_STORE_ERRORS = (CsvDatasetError, SqliteStoreError, PostgresStoreError)
MUTATION_ERRORS = (SqliteStoreError, PostgresStoreError, ValueError)


def sqlite_store() -> SqliteRowStore:
    """Build the canonical local SQLite store."""
    return SqliteRowStore(CANONICAL_DB)


def postgres_store() -> PostgresRowStore:
    """Build the shared PostgreSQL store configured for deployment."""
    if not DATABASE_URL:
        raise PostgresStoreError("config", "DATABASE_URL is not configured")
    return PostgresRowStore(DATABASE_URL)


def storage_backend_name() -> str:
    """Return the configured persistence backend name for UI copy."""
    return "PostgreSQL" if DATABASE_URL else "SQLite"


def data_store() -> RowStore:
    """Select shared PostgreSQL in deployment and SQLite for local development."""
    return postgres_store() if DATABASE_URL else sqlite_store()


def ensure_data_store() -> RowStore:
    """Create the configured store and seed it once from the explicit CSV."""
    if DATABASE_URL:
        store = postgres_store()
        migrate_csv_to_postgres(store, CANONICAL_CSV)
    else:
        store = sqlite_store()
        migrate_csv_to_sqlite(store, CANONICAL_CSV)
    return store


def ensure_sqlite_store() -> RowStore:
    """Backward-compatible name for the canonical configured row store."""
    return ensure_data_store()


def canonical_payload() -> bytes:
    """Return the canonical snapshot in explicit CSV format."""
    return rows_to_csv_bytes(ensure_sqlite_store().read().rows)


def prepare_canonical_active() -> ActiveMap:
    """Prepare the configured canonical snapshot through the reusable map workflow."""
    payload = canonical_payload()
    attachments = read_image_snapshot(IMAGE_SIDECAR)
    return ActiveMap(
        CANONICAL_CSV.name,
        "本地数据",
        payload,
        prepare_upload(
            payload,
            attachments=attachments,
            image_root=IMAGE_ROOT,
            require_both_cities=False,
        ),
        sha256(payload).hexdigest(),
    )


def invalidate_render_cache() -> None:
    """Forget derived map and PNG artifacts after a local mutation."""
    st.session_state.pop("png_cache", None)
    st.session_state.pop("active_map", None)


def load_management_rows() -> tuple[GisRow, ...]:
    """Read rows from the configured canonical storage."""
    return ensure_sqlite_store().read().rows


def filter_management_rows(
    rows: tuple[GisRow, ...], search: str, city: str, severity: str
) -> tuple[GisRow, ...]:
    """Filter rows while preserving their stable source order."""
    needle = search.strip().lower()
    return tuple(
        row for row in rows
        if (not needle or needle in row.model_dump_json().lower())
        and (city == "全部" or row.city.value == city)
        and (severity == "全部" or row.severity == severity)
    )


def append_manual_row(row: GisRow) -> None:
    """Append one validated manual row to the canonical source."""
    ensure_sqlite_store().append((row,))
    invalidate_render_cache()


def update_manual_row(row_id: str, replacement: GisRow) -> None:
    """Update one canonical row without changing its attachment key."""
    ensure_sqlite_store().update(row_id, replacement)
    invalidate_render_cache()


def apply_location_suggestion(values: dict[str, str], suggestion: LocationSuggestion) -> dict[str, str]:
    """Fill only blank city and street values from a coordinate suggestion."""
    updated = dict(values)
    if not updated.get("city") and suggestion.city:
        updated["city"] = suggestion.city
    if not updated.get("street") and suggestion.street:
        updated["street"] = suggestion.street
    return updated


def replace_canonical_rows(rows: tuple[GisRow, ...]) -> None:
    """Replace the canonical source with validated upload rows."""
    ensure_sqlite_store().replace(rows)
    invalidate_render_cache()


def append_uploaded_rows(payload: bytes) -> None:
    """Merge uploaded rows into the canonical source by stable ID."""
    dataset = parse_csv_bytes(payload, require_both_cities=False)
    store = ensure_data_store()
    existing = {row.id: row for row in store.read().rows}
    existing.update({row.id: row for row in dataset.rows})
    store.replace(tuple(existing.values()))
    invalidate_render_cache()


def delete_persisted_row(row_id: str) -> None:
    """Delete a row, its sidecar metadata, and its image directory as one UI action."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", row_id):
        raise ValueError("invalid stable ID")
    ensure_sqlite_store().delete(row_id)
    snapshot = read_image_snapshot(IMAGE_SIDECAR)
    snapshot.pop(row_id, None)
    write_image_snapshot(IMAGE_SIDECAR, snapshot)
    shutil.rmtree(IMAGE_ROOT / row_id, ignore_errors=True)
    invalidate_render_cache()


def add_image_attachment(row_id: str, filename: str, payload: bytes) -> None:
    """Persist an uploaded image and its validated sidecar metadata."""
    snapshot = read_image_snapshot(IMAGE_SIDECAR)
    existing = {item.filename for item in snapshot.get(row_id, ())}
    candidate = filename
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while candidate in existing:
        candidate = f"{stem}-{counter}{suffix}"
        counter += 1
    staged = stage_image(IMAGE_ROOT, row_id, candidate, payload)
    snapshot[row_id] = (*snapshot.get(row_id, ()), staged.metadata)
    write_image_snapshot(IMAGE_SIDECAR, snapshot)


def export_active(active: ActiveMap) -> tuple[StaticArtifact, StaticArtifact]:
    """Export the active CSV and HTML through the parameterized core API."""
    with TemporaryDirectory(prefix="gis-export-") as directory:
        output_dir = Path(directory)
        html_path = output_dir / "map.html"
        csv_path = output_dir / "issues.csv"
        html_path.write_bytes(active.prepared.html_bytes)
        csv_path.write_bytes(active.csv_bytes)
        return export_artifacts(ExportRequest(html_path, csv_path, output_dir))


def cached_pngs(cache: PngCache | None, active: ActiveMap) -> tuple[StaticArtifact, ...]:
    """Return artifacts only when they belong to the current dataset."""
    if cache is None or cache.fingerprint != active.fingerprint:
        return ()
    return cache.artifacts


def load_active() -> ActiveMap:
    """Prepare the canonical dataset, appending each upload once."""
    upload = st.file_uploader(
        f"导入 CSV 到 {storage_backend_name()}",
        type=("csv",),
        help="UTF-8 编码，最大 5 MiB，列名和顺序须符合 13 列契约。",
        key="delivery-csv",
    )
    if upload is not None:
        payload = upload.getvalue()
        fingerprint = sha256(payload).hexdigest()
        if st.session_state.get("delivery-upload-fingerprint") != fingerprint:
            append_uploaded_rows(payload)
            st.session_state["delivery-upload-fingerprint"] = fingerprint
    active = prepare_canonical_active()
    st.session_state["active_map"] = active
    return active


def panel_header(index: str, title: str, panel: str, state: str = "") -> None:
    """Render a stable structural label for one workbench region."""
    state_markup = f'<span class="panel-state">{state}</span>' if state else ""
    st.markdown(
        f'<div class="workbench-panel-header" data-panel="{panel}">'
        f'<span class="panel-index">{index}</span><span class="panel-title">{title}</span>'
        f"{state_markup}</div>",
        unsafe_allow_html=True,
    )


def render_project_bar(active: ActiveMap) -> None:
    """Render project identity, workflow stages, and active dataset status."""
    st.markdown(
        '<header class="project-bar">'
        '<div class="project-identity">优路元航 <span>/ GIS 工作台</span></div>'
        '<div class="stage-rail"><span>01 数据</span><span>02 校验</span>'
        '<span>03 地图</span><span>04 交付</span></div>'
        f'<div class="project-status"><span class="status-dot"></span><strong>数据有效</strong>'
        f" · {active.source} · {active.name} · {len(active.prepared.dataset.rows)} 条记录</div>"
        "</header>",
        unsafe_allow_html=True,
    )


def render_inspection(active: ActiveMap) -> None:
    """Render compact inspection rows instead of presentation metric cards."""
    rows = active.prepared.dataset.rows
    cities = sorted({row.city.value for row in rows})
    high_severity = sum(row.severity == "高" for row in rows)
    st.markdown(
        '<div class="inspection-list">'
        f'<div class="inspection-row"><span>记录数</span><strong>{len(rows)}</strong></div>'
        f'<div class="inspection-row"><span>覆盖城市</span><strong>{len(cities)}</strong></div>'
        f'<div class="inspection-row"><span>高严重度</span><strong>{high_severity}</strong></div>'
        f'<div class="inspection-row"><span>坐标参考</span><strong>{GCJ02_LABEL}</strong></div>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.table([{"城市": city, "记录数": sum(row.city.value == city for row in rows)} for city in cities])


def coordinate_reference_label(prepared: PreparedMap) -> str:
    """Return the core-declared coordinate reference label without inference."""
    config = getattr(prepared, "config", None)
    coordinate_system = getattr(config, "coordinate_system", GCJ02_LABEL)
    return str(coordinate_system)


def render_prepared_map(active: ActiveMap) -> None:
    """Embed the exact core-prepared official AMap HTML artifact."""
    config = getattr(active.prepared, "config", None)
    config_error = getattr(config, "error", None)
    if config_error:
        st.error(str(config_error))
        return
    components.html(active.html_bytes.decode("utf-8"), height=MAP_HEIGHT)


def render_png_exports(active: ActiveMap) -> None:
    """Generate and expose dataset-scoped static exports."""
    st.caption("城市 PNG 由当前数据与地图生成，生成后可分别下载。")
    existing = st.session_state.get("png_cache")
    cache = existing if isinstance(existing, PngCache) else None
    artifacts = cached_pngs(cache, active)
    if cache is not None and not artifacts:
        del st.session_state["png_cache"]
    if st.button("生成城市 PNG", type="primary", use_container_width=True):
        try:
            with st.status("正在生成两座城市 PNG…", expanded=False) as status:
                generated = export_active(active)
                status.update(label="PNG 已生成", state="complete")
        except (ExportEngineError, OSError) as error:
            st.error(f"静态导出失败：{error}")
        else:
            st.session_state["png_cache"] = PngCache(active.fingerprint, generated)
            artifacts = generated
    if artifacts:
        for column, artifact in zip(st.columns(2), artifacts, strict=True):
            column.download_button(
                artifact.filename,
                artifact.content,
                file_name=artifact.filename,
                mime="image/png",
                use_container_width=True,
            )


def navigate(page: str) -> None:
    """Store the requested page so Streamlit reruns keep the current route."""
    st.session_state["page"] = page


def editor_auth_required() -> bool:
    """Return whether this deployment requires the configured editor code."""
    return bool(DATABASE_URL or ADMIN_CODE)


def management_available() -> bool:
    """Return whether a safe management entry point can be exposed."""
    if not READ_ONLY:
        return not DATABASE_URL or bool(ADMIN_CODE)
    return False


def editor_authenticated() -> bool:
    """Check the current session's editor authorization state."""
    if not management_available():
        return False
    if not editor_auth_required():
        return True
    return st.session_state.get("editor_authenticated") is True


def render_editor_login() -> bool:
    """Render the fixed-code gate and return whether editing may continue."""
    if not editor_auth_required():
        return True
    if st.session_state.get("editor_authenticated") is True:
        if st.button("退出编辑", key="logout-editor"):
            st.session_state.pop("editor_authenticated", None)
            st.session_state.pop("edit-row", None)
            st.session_state.pop("attach-row", None)
            navigate("selector")
            st.rerun()
        return True

    st.info("请输入编辑口令后继续。")
    with st.form("editor-login"):
        code = st.text_input("编辑口令", type="password", max_chars=128)
        submitted = st.form_submit_button("验证口令", type="primary")
    if submitted:
        if hmac.compare_digest(code, ADMIN_CODE):
            st.session_state["editor_authenticated"] = True
            st.rerun()
        st.error("编辑口令不正确。")
    return False


def render_return_button() -> None:
    """Render the shared route-back control."""
    st.markdown('<div class="route-back-space"></div>', unsafe_allow_html=True)
    if st.button("返回选择页", key="back-selector"):
        navigate("selector")
        st.rerun()


def render_selector() -> None:
    """Render the landing selector without loading any workbench artifacts."""
    st.markdown(
        '<header class="project-bar"><div class="project-identity">优路元航 '
        '<span>/ GIS 工作台</span></div><div class="project-status">本地工作台</div></header>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="selector-options">', unsafe_allow_html=True)
    can_manage = management_available()
    columns = st.columns(3 if can_manage else 2)
    left, right = columns[:2]
    with left:
        if st.button("进入查看", key="open-view", type="primary", use_container_width=True):
            navigate("view")
            st.rerun()
    with right:
        if st.button("下载", key="open-delivery", use_container_width=True):
            navigate("delivery")
            st.rerun()
    if can_manage:
        with columns[2]:
            if st.button("数据管理", key="open-management", use_container_width=True):
                navigate("management")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_management_page() -> None:
    """Render local row management, manual entry, and image attachment controls."""
    if not management_available():
        st.error("数据管理未开放，请检查 GIS_READ_ONLY 与 GIS_ADMIN_CODE 配置。")
        return
    render_return_button()
    if not render_editor_login():
        return
    backend_label = storage_backend_name()
    panel_header("01", "数据管理", "management", f"{backend_label} 数据")
    st.caption(f"Storage backend: {backend_label}")
    if DATABASE_URL:
        st.caption("表格数据会持久化到 Postgres；图片附件仍需对象存储才能跨重启保存。")
    search = st.text_input("搜索", placeholder="ID、街道、描述")
    city = st.selectbox("城市", ["全部", "西宁", "格尔木"])
    severity = st.selectbox("严重度", ["全部", "低", "中", "高"])
    uploaded_csv = st.file_uploader(
        f"导入 CSV 到 {backend_label}", type=("csv",), key="management-csv"
    )
    if uploaded_csv is not None and st.button("导入 CSV", key="save-management-csv"):
        try:
            append_uploaded_rows(uploaded_csv.getvalue())
        except CSV_STORE_ERRORS as error:
            st.error(f"CSV 校验失败：{error}")
        else:
            st.success(f"CSV 已导入 {backend_label}，已有 ID 已更新。地图将在下一次访问时重建。")
            st.rerun()
    with st.expander("新增记录", expanded=False):
        with st.form("manual-row"):
            values = {
                "id": st.text_input("稳定 ID"),
                "city": st.text_input("城市", key="manual-city"),
                "district": st.text_input("区域", key="manual-district"),
                "street": st.text_input("街道", key="manual-street"),
                "longitude": st.number_input("经度", value=101.77, format="%.6f", key="manual-longitude"),
                "latitude": st.number_input("纬度", value=36.62, format="%.6f", key="manual-latitude"),
                "problem_type": st.text_input("问题类型"),
                "subtype": st.text_input("子类型"),
                "severity": st.text_input("严重度"),
                "confidence": st.number_input("置信度", min_value=0.75, max_value=0.99, value=0.8, step=0.01),
                "description": st.text_input("描述"),
                "detected_at": st.text_input("检测时间", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                "data_source": st.text_input("数据来源", value="manual"),
            }
            if st.form_submit_button("保存记录"):
                try:
                    append_manual_row(GisRow.model_validate(values))
                except MUTATION_ERRORS as error:
                    st.error(f"记录保存失败：{error}")
                else:
                    st.session_state.pop("manual-city", None)
                    st.session_state.pop("manual-district", None)
                    st.session_state.pop("manual-street", None)
                    st.success("记录已保存，地图将在下一次访问时重建。")
                    st.rerun()
            if st.form_submit_button("根据经纬度建议", key="manual-location-suggestion"):
                suggestion = suggest_location(values["longitude"], values["latitude"])
                applied = apply_location_suggestion(
                    {"city": values["city"], "street": values["street"]}, suggestion
                )
                if not values["city"]:
                    st.session_state["manual-city"] = applied["city"]
                if not values["street"]:
                    st.session_state["manual-street"] = applied["street"]
                st.session_state["manual-location-suggestion-result"] = suggestion
                st.rerun()
        suggestion = st.session_state.get("manual-location-suggestion-result")
        if isinstance(suggestion, LocationSuggestion):
            st.caption(f"城市建议：{suggestion.city or '无'}；街道建议：{suggestion.street or '无'}；区域请手动填写")
    try:
        rows = load_management_rows()
    except STORE_ERRORS as error:
        st.error(f"读取数据失败：{error}")
        return
    filtered = filter_management_rows(rows, search, city, severity)
    if not rows:
        st.info(
            f"当前 {backend_label} 为空。请导入符合 13 列契约的 CSV，或展开“新增记录”手动录入第一条数据。"
        )
        return
    st.markdown('<div class="library-header"><span>记录</span><span>严重度</span><span>操作</span></div>', unsafe_allow_html=True)
    for row in filtered:
        columns = st.columns((8, 2, 2))
        columns[0].write(f"{row.id} · {row.city.value} · {row.street}\n{row.description}")
        columns[1].caption(row.severity)
        with columns[2]:
            action_attach, action_delete = st.columns(2)
            with action_attach:
                attach_button, edit_button = st.columns(2)
                with attach_button:
                    if st.button("附件", key=f"image-{row.id}"):
                        st.session_state[f"attach-row"] = row.id
                with edit_button:
                    if st.button("编辑", key=f"edit-{row.id}"):
                        st.session_state["edit-row"] = row.id
            with action_delete:
                if st.button("删除", key=f"delete-{row.id}", type="secondary"):
                    try:
                        delete_persisted_row(row.id)
                    except STORE_ERRORS as error:
                        st.error(f"删除失败：{error}")
                    else:
                        st.rerun()
        if st.session_state.get("edit-row") == row.id:
            with st.form(f"edit-row-{row.id}"):
                edited = {
                    "id": st.text_input("稳定 ID", value=row.id, disabled=True),
                    "city": st.text_input("城市", value=row.city.value),
                    "district": st.text_input("区域", value=row.district),
                    "street": st.text_input("街道", value=row.street),
                    "longitude": st.number_input("经度", value=row.longitude, format="%.6f"),
                    "latitude": st.number_input("纬度", value=row.latitude, format="%.6f"),
                    "problem_type": st.text_input("问题类型", value=row.problem_type),
                    "subtype": st.text_input("子类型", value=row.subtype),
                    "severity": st.text_input("严重度", value=row.severity),
                    "confidence": st.number_input("置信度", min_value=0.75, max_value=0.99, value=row.confidence, step=0.01),
                    "description": st.text_input("描述", value=row.description),
                    "detected_at": st.text_input("检测时间", value=row.detected_at.strftime("%Y-%m-%d %H:%M:%S")),
                    "data_source": st.text_input("数据来源", value=row.data_source),
                }
                if st.form_submit_button("保存编辑"):
                    try:
                        update_manual_row(row.id, GisRow.model_validate(edited))
                    except MUTATION_ERRORS as error:
                        st.error(f"记录保存失败：{error}")
                    else:
                        st.session_state.pop("edit-row", None)
                        st.success("记录已更新。")
                        st.rerun()
        if st.session_state.get("attach-row") == row.id:
            uploaded_image = st.file_uploader("选择图片附件", type=("png", "jpg", "jpeg", "gif", "webp"), key=f"image-upload-{row.id}")
            if uploaded_image is not None and st.button("保存附件", key=f"save-image-{row.id}"):
                try:
                    add_image_attachment(row.id, uploaded_image.name, uploaded_image.getvalue())
                except ImageStoreError as error:
                    st.error(f"附件保存失败：{error}")
                else:
                    st.session_state.pop("attach-row", None)
                    invalidate_render_cache()
                    st.rerun()


def render_view_page() -> None:
    """Render only the current map and the route-back control."""
    render_return_button()
    active = st.session_state.get("active_map")
    try:
        if not isinstance(active, ActiveMap):
            payload = st.session_state.get("uploaded_payload")
            if isinstance(payload, bytes):
                active = prepare_active(
                    str(st.session_state.get("uploaded_name", "上传数据.csv")),
                    "上传 CSV",
                    payload,
                )
        if not isinstance(active, ActiveMap):
            rows = load_management_rows()
            if not rows:
                st.info("当前没有可查看的点位。请返回选择页进入“数据管理”，导入 CSV 或新增记录。")
                return
            active = prepare_canonical_active()
            st.session_state["active_map"] = active
    except (AMapConfigError, CsvDatasetError, SqliteStoreError, PostgresStoreError) as error:
        st.error(f"地图暂不可用：{error}")
        return
    render_prepared_map(active)


def render_delivery_page() -> None:
    """Render only downloadable artifacts from the canonical dataset."""
    render_return_button()
    try:
        active = prepare_canonical_active()
    except (AMapConfigError, CsvDatasetError, SqliteStoreError, PostgresStoreError) as error:
        st.error(f"交付文件暂不可用：{error}")
        st.stop()
    panel_header("04", "交付文件", "deliver", "当前数据集")
    st.markdown(
        '<p class="delivery-note">下载原始数据、独立交互地图，或生成城市静态图。</p>',
        unsafe_allow_html=True,
    )
    st.download_button("下载当前 CSV", active.csv_bytes, file_name=active.name, mime="text/csv", use_container_width=True)
    st.download_button("下载交互地图 HTML", active.prepared.html_bytes, file_name="盲道问题GIS标注图.html", mime="text/html", use_container_width=True)
    render_png_exports(active)


def main() -> None:
    """Render the selector and its two isolated workbench pages."""
    st.set_page_config(page_title="优路元航 GIS 工作台", layout="wide")
    render_styles()
    try:
        ensure_data_store()
    except STORE_ERRORS as error:
        st.error(f"数据存储连接失败：{error}")
        st.stop()
    page = st.session_state.setdefault("page", "selector")
    if page == "selector":
        render_selector()
    elif page == "view":
        render_view_page()
    elif page == "management":
        if management_available():
            render_management_page()
        else:
            st.error("数据管理未开放，请检查 GIS_READ_ONLY 与 GIS_ADMIN_CODE 配置。")
            if st.button("返回选择页", key="management-disabled-back"):
                navigate("selector")
                st.rerun()
    else:
        render_delivery_page()


if __name__ == "__main__":
    main()

"""Load official AMap browser configuration without exposing secrets."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AMapConfigError(Exception):
    """A typed configuration loading failure."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True, slots=True)
class AMapConfig:
    """Public AMap JS key and optional security code."""

    js_key: str
    security_js_code: str


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_amap_config(project_dir: Path) -> AMapConfig:
    """Read deployment environment or local ``.env`` without printing values."""
    values = _parse_env(project_dir.parent / ".env")
    js_key = os.environ.get("AMAP_KEY") or os.environ.get("AMAP_JS_KEY") or values.get("AMAP_JS_KEY") or values.get("AMAP_KEY")
    if not js_key:
        raise AMapConfigError("missing_js_key", "AMAP_JS_KEY is required in the parent .env")
    security_js_code = os.environ.get("AMAP_SECURITY_CODE") or os.environ.get("AMAP_SECURITY_JS_CODE") or values.get("AMAP_SECURITY_CODE") or values.get("AMAP_SECURITY_JS_CODE")
    if not security_js_code:
        raise AMapConfigError("missing_security_code", "AMAP_SECURITY_CODE is required in the parent .env")
    return AMapConfig(js_key, security_js_code)

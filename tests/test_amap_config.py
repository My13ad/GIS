from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from amap_config import AMapConfigError, load_amap_config


def test_load_amap_config_reads_parent_env_without_printing_secret(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Given
    env_file = tmp_path / ".env"
    env_file.write_text("AMAP_JS_KEY=secret-key\nAMAP_SECURITY_JS_CODE=secret-code\n", encoding="utf-8")
    # When
    config = load_amap_config(tmp_path / "GIS可视化")
    # Then
    assert config.js_key == "secret-key"
    assert config.security_js_code == "secret-code"
    assert "secret-key" not in capsys.readouterr().out
    assert "secret-code" not in capsys.readouterr().out


def test_load_amap_config_reports_typed_missing_key(tmp_path: Path) -> None:
    # Given
    (tmp_path / ".env").write_text("AMAP_SECURITY_JS_CODE=code\n", encoding="utf-8")
    # When / Then
    with pytest.raises(AMapConfigError) as captured:
        load_amap_config(tmp_path / "GIS可视化")
    assert captured.value.code == "missing_js_key"

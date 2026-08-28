from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from image_store import (
    ImageStoreError,
    cleanup_staged_image,
    read_image_snapshot,
    stage_image,
    validate_image_bytes,
    validate_image_metadata,
)


PNG = b"\x89PNG\r\n\x1a\n" + b"valid-payload"


def test_sidecar_rejects_path_traversal() -> None:
    # Given / When / Then
    with pytest.raises(ImageStoreError, match="relative path"):
        validate_image_metadata({
            "id": "XN-1",
            "filename": "../secret.png",
            "content_type": "image/png",
            "size_bytes": len(PNG),
            "sha256": "0" * 64,
            "path": "../secret.png",
        })


def test_validate_image_bytes_accepts_png_and_rejects_invalid_bytes() -> None:
    # Given / When / Then
    assert validate_image_bytes(PNG) == "image/png"
    with pytest.raises(ImageStoreError, match="image bytes"):
        validate_image_bytes(b"not-an-image")


def test_stage_image_and_cleanup_leaves_no_staged_file(tmp_path: Path) -> None:
    # Given / When
    staged = stage_image(tmp_path / "images", "XN-1", "photo.png", PNG)
    staged_path = staged.staged_path
    # Then
    assert staged_path.exists()
    assert staged.metadata.path == "XN-1/photo.png"
    cleanup_staged_image(staged)
    assert not staged_path.exists()


def test_image_snapshot_has_typed_metadata(tmp_path: Path) -> None:
    # Given
    sidecar = tmp_path / "blind_path_issues.images.json"
    sidecar.write_text(json.dumps({"XN-1": []}), encoding="utf-8")
    # When / Then
    assert read_image_snapshot(sidecar) == {"XN-1": ()}

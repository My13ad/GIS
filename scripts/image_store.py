"""Validated image sidecar metadata and atomic local image staging."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from dataclasses import asdict
from pathlib import Path
from typing import Final, Mapping, TypeGuard

SAFE_NAME: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
IMAGE_TYPES: Final = {
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/gif": (b"GIF87a", b"GIF89a"),
    "image/webp": (b"RIFF",),
}


class ImageStoreError(Exception):
    """An image sidecar or byte validation failure."""

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass(frozen=True, slots=True)
class ImageMetadata:
    """Immutable metadata recorded in the sidecar JSON."""

    id: str
    filename: str
    content_type: str
    size_bytes: int
    sha256: str
    path: str


@dataclass(frozen=True, slots=True)
class StagedImage:
    """An image staged under its final relative sidecar path."""

    staged_path: Path
    metadata: ImageMetadata


def validate_image_bytes(payload: bytes) -> str:
    """Return the supported MIME type for valid image bytes."""
    for content_type, signatures in IMAGE_TYPES.items():
        if any(payload.startswith(signature) for signature in signatures):
            if content_type == "image/webp" and payload[8:12] != b"WEBP":
                continue
            return content_type
    raise ImageStoreError("invalid_bytes", "unsupported or invalid image bytes")


def validate_image_metadata(raw: Mapping[str, str | int]) -> ImageMetadata:
    """Parse sidecar metadata and reject unsafe names or relative paths."""
    values = {key: raw[key] for key in ("id", "filename", "content_type", "size_bytes", "sha256", "path")}
    identifier, filename, content_type, size_bytes, digest, relative_path = values.values()
    if not all(isinstance(value, str) for value in (identifier, filename, content_type, digest, relative_path)):
        raise ImageStoreError("metadata", "metadata text fields must be strings")
    if not isinstance(size_bytes, int) or size_bytes < 1:
        raise ImageStoreError("metadata", "size_bytes must be positive")
    safe_path = Path(relative_path)
    if safe_path.is_absolute() or ".." in safe_path.parts or safe_path.parts != (identifier, filename):
        raise ImageStoreError("metadata", "path must be a safe relative path")
    if not SAFE_NAME.fullmatch(identifier) or not SAFE_NAME.fullmatch(filename):
        raise ImageStoreError("metadata", "unsafe image ID or filename")
    if content_type not in IMAGE_TYPES or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ImageStoreError("metadata", "invalid content type or sha256")
    return ImageMetadata(identifier, filename, content_type, size_bytes, digest, relative_path)


def stage_image(image_root: Path, row_id: str, filename: str, payload: bytes) -> StagedImage:
    """Validate and atomically stage bytes in ``image_root/<row_id>/``."""
    content_type = validate_image_bytes(payload)
    metadata = validate_image_metadata({
        "id": row_id,
        "filename": filename,
        "content_type": content_type,
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "path": f"{row_id}/{filename}",
    })
    target = image_root / metadata.path
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, target)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)
    return StagedImage(target, metadata)


def cleanup_staged_image(staged: StagedImage) -> None:
    """Remove a staged image without touching other row assets."""
    staged.staged_path.unlink(missing_ok=True)


def read_image_snapshot(path: Path) -> dict[str, tuple[ImageMetadata, ...]]:
    """Read and validate the image sidecar mapping."""
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not _is_json_mapping(raw):
        raise ImageStoreError("sidecar", "sidecar root must be an object")
    result: dict[str, tuple[ImageMetadata, ...]] = {}
    for row_id, entries in raw.items():
        if not isinstance(row_id, str) or not isinstance(entries, list):
            raise ImageStoreError("sidecar", "sidecar entries are malformed")
        result[row_id] = tuple(validate_image_metadata(entry) for entry in entries)
    return result


def write_image_snapshot(path: Path, snapshot: Mapping[str, tuple[ImageMetadata, ...]]) -> None:
    """Write validated image metadata atomically beside the canonical CSV."""
    payload = json.dumps(
        {row_id: [asdict(metadata) for metadata in entries] for row_id, entries in snapshot.items()},
        ensure_ascii=False,
        indent=2,
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as temporary:
            temporary_name = temporary.name
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def _is_json_mapping(value: Mapping[str, list[Mapping[str, str | int]]] | list[object] | str | int) -> TypeGuard[dict[str, list[Mapping[str, str | int]]]]:
    return isinstance(value, dict)

#!/usr/bin/env python3
"""Shared deterministic rules for the company/product asset library."""

from __future__ import annotations

import json
import os
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Optional


DEFAULT_LIBRARY_ROOT = Path(os.environ.get("VIDEO_PRODUCT_LIBRARY_ROOT", str(Path.home() / "Documents" / "인코어")))

SCHEMA_NAME = "incore.product-assets"
SCHEMA_VERSION = 1
MATCH_MODE = "unicode_nfc_trim_collapse_spaces_casefold_exact"

CANONICAL_DIRECTORIES = {
    "detail_page_originals": "상세페이지 원본",
    "product_master_images": "제품 마스터 이미지",
    "product_expression_images": "제품 표현 이미지",
    "existing_video_expressions": "기존 영상 표현",
    "product_information": "제품 정보",
    "generated_outputs": "생성 결과물",
}
COMPANY_COMMON_DIRECTORY = "_공용 표현"
MANIFEST_RELATIVE_PATH = "제품 정보/product-assets.json"


class AssetLibraryError(Exception):
    """Base class for deterministic library failures."""

    exit_code = 5
    error_code = "asset_library_error"

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "ok": False,
            "error": self.error_code,
            "message": self.message,
        }
        result.update(self.details)
        return result


class InvalidIdentityError(AssetLibraryError):
    exit_code = 2
    error_code = "invalid_identity"


class AmbiguousMatchError(AssetLibraryError):
    exit_code = 4
    error_code = "ambiguous"


class FilesystemConflictError(AssetLibraryError):
    exit_code = 5
    error_code = "filesystem_conflict"


def normalize_display_name(value: str) -> str:
    """NFC-normalize and trim/collapse every Unicode whitespace run."""

    return " ".join(unicodedata.normalize("NFC", value).split())


def normalized_match_key(value: str) -> str:
    """Return the only key permitted for identity matching."""

    return normalize_display_name(value).casefold()


def validate_requested_name(value: str, field_name: str) -> str:
    cleaned = normalize_display_name(value)
    if not cleaned:
        raise InvalidIdentityError(f"{field_name} must not be empty", field=field_name)
    if cleaned in {".", ".."}:
        raise InvalidIdentityError(
            f"{field_name} cannot be '.' or '..'", field=field_name
        )
    if "/" in cleaned or "\\" in cleaned:
        raise InvalidIdentityError(
            f"{field_name} cannot contain path separators", field=field_name
        )
    if any(unicodedata.category(char) == "Cc" for char in cleaned):
        raise InvalidIdentityError(
            f"{field_name} cannot contain control characters", field=field_name
        )
    return cleaned


def validate_root(root: Path) -> Path:
    if not root.is_absolute():
        raise InvalidIdentityError("library root must be an absolute path", field="root")
    if root.is_symlink():
        raise FilesystemConflictError(
            "library root cannot be a symbolic link", path=str(root)
        )
    if root.exists() and not root.is_dir():
        raise FilesystemConflictError(
            "library root exists but is not a directory", path=str(root)
        )
    return root


def _matching_entries(parent: Path, key: str) -> tuple[list[Path], list[Path]]:
    directories: list[Path] = []
    conflicts: list[Path] = []
    if not parent.is_dir():
        return directories, conflicts

    try:
        entries = list(os.scandir(parent))
    except OSError as exc:
        raise FilesystemConflictError(
            "could not inspect asset library directory",
            path=str(parent),
            os_error=str(exc),
        ) from exc

    for entry in entries:
        if normalized_match_key(entry.name) != key:
            continue
        entry_path = Path(entry.path)
        if entry.is_symlink():
            conflicts.append(entry_path)
        elif entry.is_dir(follow_symlinks=False):
            directories.append(entry_path)
        else:
            conflicts.append(entry_path)

    order = lambda path: (normalized_match_key(path.name), path.name)
    directories.sort(key=order)
    conflicts.sort(key=order)
    return directories, conflicts


def find_single_exact_directory(
    parent: Path, key: str, entity: str
) -> Optional[Path]:
    matches, conflicts = _matching_entries(parent, key)
    if conflicts:
        raise FilesystemConflictError(
            f"{entity} exact-match identity is occupied by a non-directory or symlink",
            entity=entity,
            candidates=[str(path) for path in conflicts],
        )
    if len(matches) > 1:
        raise AmbiguousMatchError(
            f"multiple {entity} directories share the same normalized exact-match key",
            entity=entity,
            match_key=key,
            candidates=[str(path) for path in matches],
        )
    return matches[0] if matches else None


def create_directory_exclusive(path: Path, entity: str) -> bool:
    """Create one directory without reusing or overwriting a colliding entry."""

    try:
        path.mkdir(mode=0o755, exist_ok=False)
        return True
    except FileExistsError as exc:
        raise FilesystemConflictError(
            f"refused to overwrite an existing {entity} path",
            entity=entity,
            path=str(path),
        ) from exc
    except OSError as exc:
        raise FilesystemConflictError(
            f"could not create {entity} directory",
            entity=entity,
            path=str(path),
            os_error=str(exc),
        ) from exc


def ensure_canonical_product_tree(product_path: Path) -> list[Path]:
    """Add missing canonical subdirectories without changing existing entries."""

    created: list[Path] = []
    for directory_name in CANONICAL_DIRECTORIES.values():
        target = product_path / directory_name
        if target.is_symlink():
            raise FilesystemConflictError(
                "canonical product directory cannot be a symbolic link",
                path=str(target),
            )
        if target.exists():
            if not target.is_dir():
                raise FilesystemConflictError(
                    "canonical product path exists but is not a directory",
                    path=str(target),
                )
            continue
        create_directory_exclusive(target, "canonical product subdirectory")
        created.append(target)
    return created


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def initial_manifest(
    root: Path, company_path: Path, product_path: Path
) -> dict[str, Any]:
    created_at = utc_now()
    paths = dict(CANONICAL_DIRECTORIES)
    paths["manifest"] = MANIFEST_RELATIVE_PATH
    return {
        "schema_name": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "manifest_revision": 1,
        "company": {
            "display_name": company_path.name,
            "normalized_name": normalized_match_key(company_path.name),
        },
        "product": {
            "display_name": product_path.name,
            "normalized_name": normalized_match_key(product_path.name),
        },
        "library_root": str(root),
        "company_dir": str(company_path),
        "product_dir": str(product_path),
        "detail_page": {
            "url": "",
            "checked_at": "",
            "packaging_version_note": "",
            "packaging_fingerprint": "",
        },
        "approved_anchors": {
            "product_master_asset_id": None,
            "deterministic_label_asset_id": None,
            "styled_product_asset_ids": [],
        },
        "created_at": created_at,
        "updated_at": created_at,
        "paths": paths,
        "policy": {
            "match_mode": MATCH_MODE,
            "fuzzy_matching": False,
            "overwrite_existing_assets": False,
            "legacy_assets_auto_approved": False,
            "product_anchor_generation": "gpt_imagegen_upstream",
            "scene_still_generation": "higgsfield_gpt_image_2",
            "readable_label_source": "deterministic_official_pixels",
            "asset_version_format": "v001",
        },
        "ready_for_scene_generation": False,
        "assets": [],
        "revisions": [
            {
                "revision": 1,
                "event": "manifest_initialized",
                "created_at": created_at,
            }
        ],
    }


def _fsync_directory(path: Path) -> None:
    try:
        directory_fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(directory_fd)
    except OSError:
        pass
    finally:
        os.close(directory_fd)


def initialize_manifest_atomic(
    manifest_path: Path, manifest: dict[str, Any]
) -> bool:
    """Publish a new manifest atomically; never replace an existing path."""

    if manifest_path.is_symlink():
        raise FilesystemConflictError(
            "manifest path cannot be a symbolic link", path=str(manifest_path)
        )
    if manifest_path.exists():
        if not manifest_path.is_file():
            raise FilesystemConflictError(
                "manifest path exists but is not a regular file",
                path=str(manifest_path),
            )
        return False

    parent = manifest_path.parent
    if not parent.is_dir() or parent.is_symlink():
        raise FilesystemConflictError(
            "manifest parent must be a real directory", path=str(parent)
        )

    temporary_path = parent / (
        f".{manifest_path.name}.tmp-{os.getpid()}-{uuid.uuid4().hex}"
    )
    file_descriptor: Optional[int] = None
    try:
        file_descriptor = os.open(
            temporary_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o644,
        )
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            file_descriptor = None
            json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        try:
            os.link(temporary_path, manifest_path)
        except FileExistsError:
            return False
        except OSError as exc:
            raise FilesystemConflictError(
                "could not atomically publish manifest without overwriting",
                path=str(manifest_path),
                os_error=str(exc),
            ) from exc
        _fsync_directory(parent)
        return True
    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def product_paths(product_path: Path) -> dict[str, str]:
    paths = {
        key: str(product_path / relative)
        for key, relative in CANONICAL_DIRECTORIES.items()
    }
    paths["manifest"] = str(product_path / MANIFEST_RELATIVE_PATH)
    return paths


def relative_path_is_safe(value: str) -> bool:
    """Allow only normalized, product-relative POSIX paths without traversal."""

    if not value or "\\" in value:
        return False
    candidate = PurePosixPath(value)
    if candidate.is_absolute() or any(
        part in {"", ".", ".."} for part in candidate.parts
    ):
        return False
    return not bool(re.match(r"^[A-Za-z]:", value))

#!/usr/bin/env python3
"""Validate one persistent company/product asset manifest and its folder tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from _product_asset_library import (
    CANONICAL_DIRECTORIES,
    DEFAULT_LIBRARY_ROOT,
    MANIFEST_RELATIVE_PATH,
    MATCH_MODE,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    normalized_match_key,
    relative_path_is_safe,
)


APPROVAL_STATUSES = {"candidate", "qc_passed", "approved", "rejected", "stale"}
ASSET_TYPES = {
    "official_source",
    "deterministic_cutout",
    "deterministic_label",
    "product_master",
    "style_derivative",
    "product_expression",
    "video_expression",
    "scene_output",
    "evidence",
}
QC_STATUSES = {"pending", "pass", "fail"}
LABEL_METHODS = {
    "pending",
    "not_applicable",
    "no_readable_label",
    "official_pixel_composite",
    "official_product_composite",
}
MASTER_LABEL_METHODS = {
    "no_readable_label",
    "official_pixel_composite",
    "official_product_composite",
}
OFFICIAL_LABEL_SOURCE_TYPES = {"detail_page", "user_supplied_official"}
ASSET_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate product-assets.json and its canonical non-destructive folder tree."
    )
    parser.add_argument(
        "manifest",
        type=Path,
        help="absolute path to 제품 정보/product-assets.json",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_LIBRARY_ROOT,
        help=f"expected absolute library root (default: {DEFAULT_LIBRARY_ROOT})",
    )
    return parser.parse_args()


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _timestamp(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _resolved_equal(left: Path, right: Path) -> bool:
    return left.resolve(strict=False) == right.resolve(strict=False)


def _inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve(strict=False).relative_to(root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_manifest(path: Path, expected_root: Path) -> list[str]:
    errors: list[str] = []
    if not path.is_absolute():
        return ["manifest path must be absolute"]
    if not expected_root.is_absolute():
        return ["expected library root must be absolute"]
    if path.is_symlink():
        return ["manifest path cannot be a symbolic link"]
    if not path.is_file():
        return [f"manifest file not found: {path}"]

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"manifest is not valid UTF-8 JSON: {exc}"]
    if not isinstance(payload, dict):
        return ["manifest root must be a JSON object"]

    if payload.get("schema_name") != SCHEMA_NAME:
        errors.append(f"schema_name must equal {SCHEMA_NAME!r}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must equal {SCHEMA_VERSION}")
    revision = payload.get("manifest_revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
        errors.append("manifest_revision must be an integer >= 1")

    created_at = _timestamp(payload.get("created_at"))
    updated_at = _timestamp(payload.get("updated_at"))
    if created_at is None:
        errors.append("created_at must be an ISO-8601 timestamp")
    if updated_at is None:
        errors.append("updated_at must be an ISO-8601 timestamp")
    if created_at and updated_at and updated_at < created_at:
        errors.append("updated_at cannot be earlier than created_at")

    product_root = path.parent.parent
    company_path = product_root.parent
    canonical_manifest = product_root / MANIFEST_RELATIVE_PATH
    if not _resolved_equal(path, canonical_manifest):
        errors.append(f"manifest must be stored at canonical path: {canonical_manifest}")
    if not _inside(expected_root, product_root):
        errors.append("product directory must stay inside the expected library root")
    for directory in (expected_root, company_path, product_root):
        if directory.is_symlink() or not directory.is_dir():
            errors.append(f"library scope is missing or unsafe: {directory}")

    library_root = payload.get("library_root")
    company_dir = payload.get("company_dir")
    product_dir = payload.get("product_dir")
    if not _is_nonempty_string(library_root) or not _resolved_equal(
        Path(library_root or "."), expected_root
    ):
        errors.append("library_root must equal the expected canonical root")
    if not _is_nonempty_string(company_dir) or not _resolved_equal(
        Path(company_dir or "."), company_path
    ):
        errors.append("company_dir must equal the manifest's company directory")
    if not _is_nonempty_string(product_dir) or not _resolved_equal(
        Path(product_dir or "."), product_root
    ):
        errors.append("product_dir must equal the manifest's product directory")

    for key, folder in (("company", company_path), ("product", product_root)):
        identity = payload.get(key)
        if not isinstance(identity, dict):
            errors.append(f"{key} must be an object")
            continue
        display_name = identity.get("display_name")
        normalized_name = identity.get("normalized_name")
        if not _is_nonempty_string(display_name):
            errors.append(f"{key}.display_name must be a non-empty string")
            continue
        expected_key = normalized_match_key(display_name)
        if normalized_name != expected_key:
            errors.append(f"{key}.normalized_name does not match display_name")
        if expected_key != normalized_match_key(folder.name):
            errors.append(f"{key}.display_name does not match its directory")

    detail_page = payload.get("detail_page")
    if not isinstance(detail_page, dict):
        errors.append("detail_page must be an object")
        detail_page = {}
    else:
        for key in ("url", "checked_at", "packaging_version_note", "packaging_fingerprint"):
            if not isinstance(detail_page.get(key), str):
                errors.append(f"detail_page.{key} must be a string")
        if detail_page.get("checked_at") and _timestamp(detail_page.get("checked_at")) is None:
            errors.append("detail_page.checked_at must be empty or an ISO-8601 timestamp")

    expected_paths = dict(CANONICAL_DIRECTORIES)
    expected_paths["manifest"] = MANIFEST_RELATIVE_PATH
    if payload.get("paths") != expected_paths:
        errors.append("paths must exactly match the canonical folder mapping")
    for directory_name in CANONICAL_DIRECTORIES.values():
        directory = product_root / directory_name
        if directory.is_symlink() or not directory.is_dir():
            errors.append(f"canonical directory missing or unsafe: {directory}")

    policy = payload.get("policy")
    required_policy = {
        "match_mode": MATCH_MODE,
        "fuzzy_matching": False,
        "overwrite_existing_assets": False,
        "legacy_assets_auto_approved": False,
        "product_anchor_generation": "gpt_imagegen_upstream",
        "scene_still_generation": "higgsfield_gpt_image_2",
        "readable_label_source": "deterministic_official_pixels",
        "asset_version_format": "v001",
    }
    if not isinstance(policy, dict):
        errors.append("policy must be an object")
    else:
        for key, expected in required_policy.items():
            if policy.get(key) != expected:
                errors.append(f"policy.{key} must equal {expected!r}")

    assets = payload.get("assets")
    asset_by_id: dict[str, dict[str, Any]] = {}
    paths_seen: set[str] = set()
    role_versions: set[tuple[str, str, int]] = set()
    if not isinstance(assets, list):
        errors.append("assets must be an array")
        assets = []

    for index, asset in enumerate(assets):
        prefix = f"assets[{index}]"
        if not isinstance(asset, dict):
            errors.append(f"{prefix} must be an object")
            continue
        asset_id = asset.get("asset_id")
        if not _is_nonempty_string(asset_id) or not ASSET_ID_PATTERN.fullmatch(asset_id):
            errors.append(f"{prefix}.asset_id must match {ASSET_ID_PATTERN.pattern}")
        elif asset_id in asset_by_id:
            errors.append(f"duplicate asset_id: {asset_id}")
        else:
            asset_by_id[asset_id] = asset

        asset_type = asset.get("asset_type")
        role = asset.get("role")
        version = asset.get("version")
        if asset_type not in ASSET_TYPES:
            errors.append(f"{prefix}.asset_type must be one of {sorted(ASSET_TYPES)}")
        if not _is_nonempty_string(role):
            errors.append(f"{prefix}.role must be a non-empty string")
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            errors.append(f"{prefix}.version must be an integer >= 1")
        elif asset_type in ASSET_TYPES and _is_nonempty_string(role):
            key = (asset_type, role, version)
            if key in role_versions:
                errors.append(f"duplicate asset type/role/version: {key}")
            role_versions.add(key)

        status = asset.get("approval_status")
        if status not in APPROVAL_STATUSES:
            errors.append(f"{prefix}.approval_status must be one of {sorted(APPROVAL_STATUSES)}")
        scope = asset.get("product_scope")
        if scope not in {"same_product", "product_neutral"}:
            errors.append(f"{prefix}.product_scope must be same_product or product_neutral")
        neutral = asset.get("product_neutral")
        if not isinstance(neutral, bool):
            errors.append(f"{prefix}.product_neutral must be boolean")
        elif neutral != (scope == "product_neutral"):
            errors.append(f"{prefix}.product_neutral conflicts with product_scope")
        if asset_type in {"official_source", "deterministic_cutout", "deterministic_label", "product_master", "style_derivative"} and scope != "same_product":
            errors.append(f"{prefix} product identity assets must be same_product")

        relative_path = asset.get("relative_path")
        asset_path: Optional[Path] = None
        if not isinstance(relative_path, str) or not relative_path_is_safe(relative_path):
            errors.append(f"{prefix}.relative_path must be a safe relative path")
        else:
            if relative_path in paths_seen:
                errors.append(f"duplicate asset relative_path: {relative_path}")
            paths_seen.add(relative_path)
            asset_path = product_root / relative_path
            if not _inside(product_root, asset_path):
                errors.append(f"{prefix}.relative_path escapes the product folder")
            elif asset_path.is_symlink() or not asset_path.is_file():
                errors.append(f"{prefix}.relative_path must name a real existing file")

        if not _is_nonempty_string(asset.get("source_type")):
            errors.append(f"{prefix}.source_type must be a non-empty string")
        if not isinstance(asset.get("source_url", ""), str):
            errors.append(f"{prefix}.source_url must be a string")
        source_sha256 = asset.get("source_sha256", "")
        if source_sha256 and not SHA256_PATTERN.fullmatch(source_sha256):
            errors.append(f"{prefix}.source_sha256 must be empty or lowercase SHA-256")
        if asset_type in {"official_source", "deterministic_label"} and not SHA256_PATTERN.fullmatch(source_sha256 or ""):
            errors.append(f"{prefix} official-pixel assets require source_sha256")
        if asset_path and asset_path.is_file() and source_sha256 and _hash_file(asset_path) != source_sha256:
            errors.append(f"{prefix}.source_sha256 does not match the file")

        derived = asset.get("derived_from_asset_ids")
        if not isinstance(derived, list) or not all(_is_nonempty_string(item) for item in derived):
            errors.append(f"{prefix}.derived_from_asset_ids must be an array of strings")
        elif len(derived) != len(set(derived)):
            errors.append(f"{prefix}.derived_from_asset_ids cannot contain duplicates")
        if not isinstance(asset.get("generator", ""), str):
            errors.append(f"{prefix}.generator must be a string")
        if not isinstance(asset.get("generation_prompt", ""), str):
            errors.append(f"{prefix}.generation_prompt must be a string")
        label_method = asset.get("label_preservation_method")
        if label_method not in LABEL_METHODS:
            errors.append(f"{prefix}.label_preservation_method must be one of {sorted(LABEL_METHODS)}")

        qc = asset.get("qc")
        if not isinstance(qc, dict) or qc.get("status") not in QC_STATUSES:
            errors.append(f"{prefix}.qc.status must be pending, pass, or fail")
        else:
            if qc.get("checked_at") and _timestamp(qc.get("checked_at")) is None:
                errors.append(f"{prefix}.qc.checked_at must be empty or ISO-8601")
            if status == "approved" and qc.get("status") != "pass":
                errors.append(f"{prefix} approved assets require qc.status pass")
        if _timestamp(asset.get("created_at")) is None:
            errors.append(f"{prefix}.created_at must be an ISO-8601 timestamp")

    for asset_id, asset in asset_by_id.items():
        for source_id in asset.get("derived_from_asset_ids", []):
            if source_id not in asset_by_id:
                errors.append(f"asset {asset_id} derives from missing asset {source_id}")

    anchors = payload.get("approved_anchors")
    if not isinstance(anchors, dict):
        errors.append("approved_anchors must be an object")
        anchors = {}
    approved_master_id = anchors.get("product_master_asset_id")
    approved_label_id = anchors.get("deterministic_label_asset_id")
    styled_ids = anchors.get("styled_product_asset_ids")
    if approved_master_id is not None and not _is_nonempty_string(approved_master_id):
        errors.append("approved_anchors.product_master_asset_id must be null or a string")
    if approved_label_id is not None and not _is_nonempty_string(approved_label_id):
        errors.append("approved_anchors.deterministic_label_asset_id must be null or a string")
    if not isinstance(styled_ids, list) or not all(_is_nonempty_string(item) for item in styled_ids):
        errors.append("approved_anchors.styled_product_asset_ids must be an array of strings")
        styled_ids = []
    elif len(styled_ids) != len(set(styled_ids)):
        errors.append("approved_anchors.styled_product_asset_ids cannot contain duplicates")

    master = asset_by_id.get(approved_master_id) if approved_master_id else None
    if approved_master_id and master is None:
        errors.append("approved product master must reference an existing asset")
    if master:
        if master.get("asset_type") != "product_master" or master.get("approval_status") != "approved":
            errors.append("approved product master must be an approved product_master asset")
        if master.get("qc", {}).get("status") != "pass":
            errors.append("approved product master requires qc.status pass")
        if not str(master.get("generator", "")).startswith("built_in_imagegen"):
            errors.append("approved product master must originate from built-in ImageGen")
        if not _is_nonempty_string(master.get("generation_prompt")):
            errors.append("approved product master must preserve its ImageGen prompt")
        if master.get("label_preservation_method") not in MASTER_LABEL_METHODS:
            errors.append("approved product master requires deterministic label preservation")
        source_ids = master.get("derived_from_asset_ids", [])
        official_sources = [
            asset_by_id[item]
            for item in source_ids
            if item in asset_by_id
            and asset_by_id[item].get("asset_type") == "official_source"
        ]
        if not official_sources:
            errors.append("approved product master must derive from an official_source asset")
        elif not any(
            item.get("approval_status") == "approved"
            and item.get("qc", {}).get("status") == "pass"
            for item in official_sources
        ):
            errors.append("approved product master requires a QC-passed approved official_source")
        fingerprint = detail_page.get("packaging_fingerprint", "")
        if fingerprint and master.get("packaging_fingerprint") != fingerprint:
            errors.append("approved product master packaging_fingerprint must match detail_page")

    label = asset_by_id.get(approved_label_id) if approved_label_id else None
    if approved_label_id and label is None:
        errors.append("approved deterministic label must reference an existing asset")
    if label:
        if label.get("asset_type") != "deterministic_label" or label.get("approval_status") != "approved":
            errors.append("approved deterministic label must be an approved deterministic_label asset")
        if label.get("source_type") not in OFFICIAL_LABEL_SOURCE_TYPES:
            errors.append("approved deterministic label must come from an official pixel source")
        if label.get("generator") not in {"", "deterministic_crop", "deterministic_composite"}:
            errors.append("approved deterministic label cannot be generatively redrawn")

    for styled_id in styled_ids:
        asset = asset_by_id.get(styled_id)
        if asset is None:
            errors.append(f"approved styled product asset is missing: {styled_id}")
        elif asset.get("asset_type") != "style_derivative" or asset.get("approval_status") != "approved":
            errors.append(f"approved styled product asset must be an approved style_derivative: {styled_id}")

    ready = payload.get("ready_for_scene_generation")
    if not isinstance(ready, bool):
        errors.append("ready_for_scene_generation must be boolean")
    elif ready != bool(master):
        errors.append("ready_for_scene_generation must be true exactly when an approved product master is selected")
    if ready:
        detail_url = detail_page.get("url", "")
        if not detail_url.startswith(("https://", "http://")):
            errors.append("ready manifests require an HTTP(S) detail_page.url")
        if _timestamp(detail_page.get("checked_at")) is None:
            errors.append("ready manifests require detail_page.checked_at")
        if not _is_nonempty_string(detail_page.get("packaging_fingerprint")):
            errors.append("ready manifests require detail_page.packaging_fingerprint")

    revisions = payload.get("revisions")
    if not isinstance(revisions, list) or not revisions:
        errors.append("revisions must be a non-empty array")
    else:
        previous_revision = 0
        for index, item in enumerate(revisions):
            prefix = f"revisions[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{prefix} must be an object")
                continue
            item_revision = item.get("revision")
            if not isinstance(item_revision, int) or isinstance(item_revision, bool) or item_revision <= previous_revision:
                errors.append(f"{prefix}.revision must increase monotonically")
            else:
                previous_revision = item_revision
            if not _is_nonempty_string(item.get("event")):
                errors.append(f"{prefix}.event must be a non-empty string")
            if _timestamp(item.get("created_at")) is None:
                errors.append(f"{prefix}.created_at must be an ISO-8601 timestamp")
        if isinstance(revision, int) and previous_revision != revision:
            errors.append("manifest_revision must equal the latest revisions[].revision")

    return errors


def main() -> int:
    args = _parse_args()
    errors = validate_manifest(args.manifest, args.root)
    if errors:
        print("ERROR: product asset manifest is invalid")
        for error in errors:
            print(f"- {error}")
        return 1
    print("PASS: product asset manifest, provenance, anchors and folder tree are valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

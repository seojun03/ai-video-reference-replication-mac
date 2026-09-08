#!/usr/bin/env python3
"""Store user-provided clean footage in an exact company/product library."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Any


DEFAULT_LIBRARY_ROOT = Path(os.environ.get("VIDEO_PRODUCT_LIBRARY_ROOT", str(Path.home() / "Documents" / "인코어")))
LIBRARY_DIRECTORY = Path("기존 영상 표현") / "사용자 제공 클린본"
ORIGINALS_DIRECTORY = "originals"
MANIFEST_NAME = "clean-clip-library.json"
SCHEMA_NAME = "incore.user-clean-clips"
SCHEMA_VERSION = 1
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}


class IntakeError(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )


def normalize_name(value: str) -> str:
    return " ".join(unicodedata.normalize("NFC", value).split())


def validate_name(value: str, field: str) -> str:
    cleaned = normalize_name(value)
    if not cleaned:
        raise IntakeError(f"{field} must not be empty")
    if cleaned in {".", ".."} or "/" in cleaned or "\\" in cleaned:
        raise IntakeError(f"{field} contains an unsafe path value")
    if any(unicodedata.category(char) == "Cc" for char in cleaned):
        raise IntakeError(f"{field} contains control characters")
    return cleaned


def match_key(value: str) -> str:
    return normalize_name(value).casefold()


def resolve_exact_directory(parent: Path, requested: str, entity: str) -> Path | None:
    if not parent.exists():
        return None
    if not parent.is_dir() or parent.is_symlink():
        raise IntakeError(f"{entity} parent is not a safe directory: {parent}")
    matches: list[Path] = []
    conflicts: list[Path] = []
    requested_key = match_key(requested)
    for entry in os.scandir(parent):
        if match_key(entry.name) != requested_key:
            continue
        path = Path(entry.path)
        if entry.is_dir(follow_symlinks=False):
            matches.append(path)
        else:
            conflicts.append(path)
    if conflicts:
        raise IntakeError(
            f"{entity} identity is occupied by a non-directory or symlink: {conflicts}"
        )
    if len(matches) > 1:
        raise IntakeError(f"ambiguous exact {entity} match: {matches}")
    return matches[0] if matches else None


def ensure_plain_directory(path: Path) -> None:
    if path.is_symlink():
        raise IntakeError(f"refusing symbolic-link directory: {path}")
    if path.exists() and not path.is_dir():
        raise IntakeError(f"expected a directory: {path}")
    path.mkdir(mode=0o755, parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probe_video(path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return {"status": "unavailable", "reason": "ffprobe_not_found"}
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=index,codec_type,width,height,avg_frame_rate",
        "-of",
        "json",
        str(path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return {
            "status": "error",
            "reason": "ffprobe_failed",
            "detail": result.stderr.strip()[:500],
        }
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        return {"status": "error", "reason": f"ffprobe_invalid_json:{exc}"}
    streams = payload.get("streams") or []
    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"), None
    )
    if not video:
        return {"status": "error", "reason": "no_video_stream"}
    duration_raw = (payload.get("format") or {}).get("duration")
    try:
        duration = round(float(duration_raw), 6)
    except (TypeError, ValueError):
        duration = None
    frame_rate_raw = str(video.get("avg_frame_rate") or "")
    try:
        frame_rate = round(float(Fraction(frame_rate_raw)), 6)
    except (ValueError, ZeroDivisionError):
        frame_rate = None
    return {
        "status": "ok",
        "duration_seconds": duration,
        "width": video.get("width"),
        "height": video.get("height"),
        "avg_frame_rate": frame_rate,
        "has_audio": any(
            stream.get("codec_type") == "audio" for stream in streams
        ),
    }


def load_manifest(
    path: Path, root: Path, company_dir: Path, product_dir: Path
) -> dict[str, Any]:
    if not path.exists():
        timestamp = utc_now()
        return {
            "schema_name": SCHEMA_NAME,
            "schema_version": SCHEMA_VERSION,
            "manifest_revision": 0,
            "company": {
                "display_name": company_dir.name,
                "normalized_name": match_key(company_dir.name),
            },
            "product": {
                "display_name": product_dir.name,
                "normalized_name": match_key(product_dir.name),
            },
            "library_root": str(root),
            "product_dir": str(product_dir),
            "stored_clean_clips_dir": str(path.parent / ORIGINALS_DIRECTORY),
            "created_at": timestamp,
            "updated_at": timestamp,
            "clips": [],
        }
    if path.is_symlink() or not path.is_file():
        raise IntakeError(f"manifest is not a regular file: {path}")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IntakeError(f"could not read clean-clip manifest: {exc}") from exc
    if manifest.get("schema_name") != SCHEMA_NAME:
        raise IntakeError(f"unexpected manifest schema: {path}")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise IntakeError(f"unsupported manifest schema version: {path}")
    if (manifest.get("company") or {}).get("normalized_name") != match_key(
        company_dir.name
    ):
        raise IntakeError("manifest company identity does not match the resolved scope")
    if (manifest.get("product") or {}).get("normalized_name") != match_key(
        product_dir.name
    ):
        raise IntakeError("manifest product identity does not match the resolved scope")
    if not isinstance(manifest.get("clips"), list):
        raise IntakeError("manifest clips must be a list")
    return manifest


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def collision_safe_target(originals_dir: Path, source_name: str) -> Path:
    normalized = unicodedata.normalize("NFC", Path(source_name).name)
    if not normalized or normalized in {".", ".."}:
        raise IntakeError(f"invalid source filename: {source_name!r}")
    initial = originals_dir / normalized
    if not initial.exists():
        return initial
    stem = Path(normalized).stem
    suffix = Path(normalized).suffix
    for version in range(2, 10000):
        candidate = originals_dir / f"{stem}_v{version:03d}{suffix}"
        if not candidate.exists():
            return candidate
    raise IntakeError(f"could not allocate a collision-safe filename for {source_name}")


def copy_exclusive(source: Path, destination: Path) -> None:
    descriptor = os.open(
        destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, source.stat().st_mode & 0o777
    )
    try:
        with source.open("rb") as source_handle, os.fdopen(
            descriptor, "wb"
        ) as destination_handle:
            shutil.copyfileobj(source_handle, destination_handle, 1024 * 1024)
            destination_handle.flush()
            os.fsync(destination_handle.fileno())
        shutil.copystat(source, destination, follow_symlinks=False)
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        if destination.exists():
            destination.unlink()
        raise


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Store clean videos under an exact company/product without altering sources."
    )
    parser.add_argument("--company", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument(
        "--source", action="append", type=Path, required=True, dest="sources"
    )
    parser.add_argument("--root", type=Path, default=DEFAULT_LIBRARY_ROOT)
    parser.add_argument(
        "--create-product-scope",
        action="store_true",
        help="create the exact missing company/product directories named by the user",
    )
    return parser.parse_args()


def validate_sources(sources: list[Path]) -> list[Path]:
    validated: list[Path] = []
    for raw_path in sources:
        if not raw_path.is_absolute():
            raise IntakeError(f"source path must be absolute: {raw_path}")
        if raw_path.is_symlink() or not raw_path.is_file():
            raise IntakeError(f"source must be a regular non-symlink file: {raw_path}")
        if raw_path.suffix.casefold() not in VIDEO_EXTENSIONS:
            raise IntakeError(f"unsupported video extension: {raw_path}")
        validated.append(raw_path)
    return validated


def run(args: argparse.Namespace) -> dict[str, Any]:
    company = validate_name(args.company, "company")
    product = validate_name(args.product, "product")
    sources = validate_sources(args.sources)
    root = args.root
    if not root.is_absolute():
        raise IntakeError("library root must be absolute")
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise IntakeError(f"library root is not a safe directory: {root}")
    if not root.exists():
        if not args.create_product_scope:
            raise IntakeError(f"library root does not exist: {root}")
        ensure_plain_directory(root)

    company_dir = resolve_exact_directory(root, company, "company")
    if company_dir is None:
        if not args.create_product_scope:
            raise IntakeError(f"exact company scope does not exist: {company}")
        company_dir = root / company
        company_dir.mkdir(mode=0o755, exist_ok=False)

    product_dir = resolve_exact_directory(company_dir, product, "product")
    if product_dir is None:
        if not args.create_product_scope:
            raise IntakeError(f"exact product scope does not exist: {product}")
        product_dir = company_dir / product
        product_dir.mkdir(mode=0o755, exist_ok=False)

    library_dir = product_dir / LIBRARY_DIRECTORY
    originals_dir = library_dir / ORIGINALS_DIRECTORY
    ensure_plain_directory(originals_dir)
    manifest_path = library_dir / MANIFEST_NAME
    manifest = load_manifest(manifest_path, root, company_dir, product_dir)
    clips: list[dict[str, Any]] = manifest["clips"]

    by_hash: dict[str, dict[str, Any]] = {}
    originals_resolved = originals_dir.resolve()
    for clip in clips:
        source_hash = str(clip.get("source_sha256") or "")
        stored_path = Path(str(clip.get("stored_path") or ""))
        if not source_hash or not stored_path.is_absolute():
            raise IntakeError("existing manifest contains an invalid clip record")
        if source_hash in by_hash:
            raise IntakeError(f"existing manifest contains duplicate hash: {source_hash}")
        try:
            stored_path.resolve(strict=True).relative_to(originals_resolved)
        except (FileNotFoundError, ValueError) as exc:
            raise IntakeError(
                f"stored clip is outside the product originals directory: {stored_path}"
            ) from exc
        if (
            stored_path.is_symlink()
            or not stored_path.is_file()
            or sha256_file(stored_path) != source_hash
        ):
            raise IntakeError(f"stored clip is missing or hash-mismatched: {stored_path}")
        by_hash[source_hash] = clip

    copied_paths: list[Path] = []
    results: list[dict[str, Any]] = []
    changed = False
    try:
        for source in sources:
            source_hash = sha256_file(source)
            existing = by_hash.get(source_hash)
            if existing:
                results.append(
                    {
                        "source": str(source),
                        "status": "deduplicated",
                        "clip_id": existing["clip_id"],
                        "stored_path": existing["stored_path"],
                        "source_sha256": source_hash,
                    }
                )
                continue

            source_resolved = source.resolve(strict=True)
            if source_resolved.parent == originals_dir.resolve():
                target = source_resolved
                status = "registered_existing_library_file"
            else:
                target = collision_safe_target(originals_dir, source.name)
                copy_exclusive(source, target)
                copied_paths.append(target)
                status = "copied"
            if sha256_file(target) != source_hash:
                raise IntakeError(f"stored copy hash mismatch: {target}")

            clip_id = f"clean_{source_hash[:16]}"
            relative_path = target.relative_to(product_dir).as_posix()
            clip = {
                "clip_id": clip_id,
                "source_type": "user_provided_clean_clip",
                "status": "available",
                "original_filename": source.name,
                "original_source_path": str(source),
                "stored_path": str(target),
                "relative_path": relative_path,
                "source_sha256": source_hash,
                "bytes": target.stat().st_size,
                "probe": probe_video(target),
                "added_at": utc_now(),
            }
            clips.append(clip)
            by_hash[source_hash] = clip
            changed = True
            results.append(
                {
                    "source": str(source),
                    "status": status,
                    "clip_id": clip_id,
                    "stored_path": str(target),
                    "source_sha256": source_hash,
                    "probe_status": clip["probe"]["status"],
                }
            )

        if changed or not manifest_path.exists():
            manifest["manifest_revision"] = int(manifest["manifest_revision"]) + 1
            manifest["updated_at"] = utc_now()
            manifest["registered_clean_clip_count"] = len(clips)
            atomic_write_json(manifest_path, manifest)
    except Exception:
        for copied_path in copied_paths:
            if copied_path.exists():
                copied_path.unlink()
        raise

    return {
        "ok": True,
        "changed": changed,
        "company": company_dir.name,
        "product": product_dir.name,
        "product_dir": str(product_dir),
        "stored_clean_clips_dir": str(originals_dir),
        "clean_clip_library_manifest": str(manifest_path),
        "manifest_revision": manifest["manifest_revision"],
        "registered_clean_clip_count": len(clips),
        "results": results,
    }


def main() -> int:
    try:
        result = run(parse_args())
    except (IntakeError, OSError) as exc:
        print(
            json.dumps(
                {"ok": False, "error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())

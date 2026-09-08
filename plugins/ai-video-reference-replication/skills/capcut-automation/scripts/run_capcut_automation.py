#!/usr/bin/env python3
"""Inspect inputs and invoke the local PyCapCut automation engine safely."""

from __future__ import annotations

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


DEFAULT_ENGINE_ROOT = Path.home() / "Documents" / "서준 AI" / "캡컷 자동화"
DEFAULT_DRAFT_ROOT = (
    Path.home()
    / "Movies"
    / "CapCut"
    / "User Data"
    / "Projects"
    / "com.lveditor.draft"
)
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".heic"}


def _deep_merge_manifest(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if key == "extends":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_manifest(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _load_manifest(
    path: Path,
    *,
    _seen: set[Path] | None = None,
) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    seen = set() if _seen is None else set(_seen)
    if resolved in seen:
        raise ValueError(f"프로젝트 설정 extends 순환 참조입니다: {resolved}")
    seen.add(resolved)
    payload = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("최상위 값은 JSON 객체여야 합니다.")
    base_value = payload.get("extends")
    if base_value is None:
        return payload
    if not isinstance(base_value, str) or not base_value.strip():
        raise ValueError("extends는 비어 있지 않은 파일 경로 문자열이어야 합니다.")
    base_path = Path(base_value).expanduser()
    if not base_path.is_absolute():
        base_path = resolved.parent / base_path
    if not base_path.is_file():
        raise FileNotFoundError(f"extends 대상 설정 파일이 없습니다: {base_path}")
    return _deep_merge_manifest(
        _load_manifest(base_path, _seen=seen),
        payload,
    )


def resolve_engine_root(value: str | None) -> Path:
    candidates: list[Path] = []
    if value:
        candidates.append(Path(value))
    configured = os.environ.get("CAPCUT_AUTOMATION_ROOT")
    if configured:
        candidates.append(Path(configured))
    current = Path.cwd().resolve()
    candidates.extend([current, *current.parents, DEFAULT_ENGINE_ROOT])

    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.expanduser().resolve()
        if path in seen:
            continue
        seen.add(path)
        if (path / "capcut_auto").is_dir() and (path / ".venv" / "bin" / "python").is_file():
            return path
    checked = "\n".join(f"- {path}" for path in seen)
    raise FileNotFoundError(
        "PyCapCut 자동화 엔진을 찾지 못했습니다. --engine-root 또는 "
        "CAPCUT_AUTOMATION_ROOT를 지정하세요.\n확인한 위치:\n" + checked
    )


def engine_python(root: Path) -> Path:
    python = root / ".venv" / "bin" / "python"
    if not python.is_file():
        raise FileNotFoundError(f"가상환경 Python이 없습니다: {python}")
    return python


def probe_media(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "size_bytes": path.stat().st_size,
        "suffix": path.suffix.lower(),
    }
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or path.suffix.lower() not in VIDEO_SUFFIXES | AUDIO_SUFFIXES:
        return result
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=codec_type,codec_name,width,height",
            "-of",
            "json",
            str(path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        result["probe_error"] = completed.stderr.strip()
        return result
    payload = json.loads(completed.stdout)
    result["duration"] = float(payload.get("format", {}).get("duration") or 0)
    streams = payload.get("streams", [])
    result["has_video"] = any(stream.get("codec_type") == "video" for stream in streams)
    result["has_audio"] = any(stream.get("codec_type") == "audio" for stream in streams)
    return result


def media_files(folder: Path, suffixes: set[str]) -> list[Path]:
    return sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in suffixes
    )


def validate_manifest(path: Path) -> dict[str, Any]:
    report: dict[str, Any] = {
        "kind": "voiceover_manifest",
        "path": str(path),
        "errors": [],
        "warnings": [],
    }
    try:
        payload = _load_manifest(path)
    except (OSError, json.JSONDecodeError) as exc:
        report["errors"].append(f"JSON을 읽을 수 없습니다: {exc}")
        return report
    if not isinstance(payload, dict):
        report["errors"].append("최상위 값은 JSON 객체여야 합니다.")
        return report

    engine_root = resolve_engine_root(None)
    engine_root_string = str(engine_root)
    if engine_root_string not in sys.path:
        sys.path.insert(0, engine_root_string)
    from capcut_auto.editing_interview import validate_ordered_editing_interview

    interview_errors, interview_warnings = validate_ordered_editing_interview(
        payload,
        base_dir=path.parent,
        require_font_ready=True,
    )
    report["errors"].extend(interview_errors)
    report["warnings"].extend(interview_warnings)

    timing = payload.get("timing", {})
    if not isinstance(timing, dict):
        report["errors"].append("timing은 JSON 객체여야 합니다.")
        timing = {}
    else:
        if "trim_silence" in timing and not isinstance(timing["trim_silence"], bool):
            report["errors"].append("timing.trim_silence는 true 또는 false여야 합니다.")
        numeric_timing = {
            "silence_db": (-100.0, 0.0),
            "silence_min_duration": (0.001, 10.0),
            "head_padding": (0.0, 2.0),
            "tail_padding": (0.0, 2.0),
        }
        for key, (minimum, maximum) in numeric_timing.items():
            if key not in timing:
                continue
            value = timing[key]
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not minimum <= float(value) <= maximum
            ):
                report["errors"].append(
                    f"timing.{key}는 {minimum}~{maximum} 범위의 숫자여야 합니다."
                )
        if timing.get("caption_alignment", "whisper") not in {
            "whisper",
            "proportional",
        }:
            report["errors"].append(
                "timing.caption_alignment는 whisper 또는 proportional이어야 합니다."
            )

    product_context = payload.get("product_context")
    if product_context is not None:
        if not isinstance(product_context, dict):
            report["errors"].append("product_context는 JSON 객체여야 합니다.")
        else:
            enabled = product_context.get("enabled", True)
            if not isinstance(enabled, bool):
                report["errors"].append(
                    "product_context.enabled는 true 또는 false여야 합니다."
                )
            if enabled:
                for key in ("company", "product"):
                    value = product_context.get(key)
                    if not isinstance(value, str) or not value.strip():
                        report["errors"].append(
                            f"product_context.{key}가 필요합니다."
                        )
                for key in (
                    "sync_recent_scripts",
                    "include_pending_for_current_job",
                ):
                    if key in product_context and not isinstance(
                        product_context[key], bool
                    ):
                        report["errors"].append(
                            f"product_context.{key}는 true 또는 false여야 합니다."
                        )
                for key in ("root", "job_id", "style_id", "snapshot_path"):
                    if key in product_context and (
                        not isinstance(product_context[key], str)
                        or not product_context[key].strip()
                    ):
                        report["errors"].append(
                            f"product_context.{key}는 비어 있지 않은 문자열이어야 합니다."
                        )

    base = path.parent
    video_dir = base / payload.get("video_dir", "영상")
    audio_dir = base / payload.get("audio_dir", "음성")
    if not video_dir.is_dir():
        report["errors"].append(f"영상 폴더가 없습니다: {video_dir}")
        videos: list[Path] = []
    else:
        videos = media_files(video_dir, VIDEO_SUFFIXES)
        if not videos:
            report["errors"].append(f"영상 파일이 없습니다: {video_dir}")
    if not audio_dir.is_dir():
        report["errors"].append(f"음성 폴더가 없습니다: {audio_dir}")
        audios: list[Path] = []
    else:
        audios = media_files(audio_dir, AUDIO_SUFFIXES)
        if not audios:
            report["errors"].append(f"음성 파일이 없습니다: {audio_dir}")

    sequence = payload.get("video_sequence")
    assignments = payload.get("video_assignments")
    if sequence is not None and assignments is not None:
        report["errors"].append(
            "VIDEO_SELECTION_MODE_CONFLICT: video_sequence와 "
            "video_assignments를 동시에 지정할 수 없습니다."
        )
    if sequence is None and assignments is None:
        report["errors"].append(
            "video_sequence 또는 video_assignments 중 하나가 필요합니다."
        )
    if sequence is not None:
        if not isinstance(sequence, list) or not sequence:
            report["errors"].append(
                "video_sequence는 비어 있지 않은 배열이어야 합니다."
            )
        elif videos:
            invalid = [
                value
                for value in sequence
                if isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
                or value > len(videos)
            ]
            if invalid:
                report["errors"].append(
                    "video_sequence에 범위를 벗어난 1-based "
                    f"인덱스가 있습니다: {invalid}"
                )

    video_alignment = payload.get("video_alignment", {})
    if not isinstance(video_alignment, dict):
        report["errors"].append("video_alignment는 JSON 객체여야 합니다.")
        video_alignment = {}
    alignment_mode = str(
        video_alignment.get(
            "mode",
            "logical_caption" if assignments is not None else "reference_rhythm",
        )
    )
    if alignment_mode not in {"reference_rhythm", "logical_caption"}:
        report["errors"].append(
            "video_alignment.mode는 reference_rhythm 또는 "
            "logical_caption이어야 합니다."
        )
    short_source_policy = str(
        video_alignment.get("short_source_policy", "fail")
    ).strip()
    if short_source_policy not in {"fail", "leave_gap"}:
        report["errors"].append(
            "video_alignment.short_source_policy는 fail 또는 "
            "leave_gap이어야 합니다."
        )
    for key in ("require_whisper_alignment", "require_semantic_evidence"):
        if key in video_alignment and not isinstance(video_alignment[key], bool):
            report["errors"].append(
                f"video_alignment.{key}는 true 또는 false여야 합니다."
            )
    tolerance = video_alignment.get("tolerance_seconds", 0.001)
    if (
        isinstance(tolerance, bool)
        or not isinstance(tolerance, (int, float))
        or not 0 < float(tolerance) <= 0.1
    ):
        report["errors"].append(
            "video_alignment.tolerance_seconds는 0초 초과 "
            "0.1초 이하 숫자여야 합니다."
        )
    if (
        alignment_mode == "logical_caption"
        and timing.get("caption_alignment", "whisper") != "whisper"
    ):
        report["errors"].append(
            "CAPTION_WHISPER_ALIGNMENT_REQUIRED: logical_caption 모드는 "
            "timing.caption_alignment=whisper가 필요합니다."
        )

    resolved_assignment_indices: list[int] = []
    if assignments is not None:
        if payload.get("video_source_starts") is not None:
            report["errors"].append(
                "video_assignments를 사용할 때 top-level "
                "video_source_starts를 함께 지정할 수 없습니다."
            )
        if not isinstance(assignments, list) or not assignments:
            report["errors"].append(
                "video_assignments는 비어 있지 않은 배열이어야 합니다."
            )
            assignments = []
        for index, assignment in enumerate(assignments, start=1):
            if not isinstance(assignment, dict):
                report["errors"].append(
                    f"video_assignments[{index}]는 객체여야 합니다."
                )
                continue
            caption_index = assignment.get("caption_index")
            if (
                isinstance(caption_index, bool)
                or not isinstance(caption_index, int)
                or caption_index < 1
            ):
                report["errors"].append(
                    f"video_assignments[{index}].caption_index는 "
                    "1 이상의 정수여야 합니다."
                )
            else:
                resolved_assignment_indices.append(caption_index)
            match = assignment.get("match")
            if not isinstance(match, str) or not match.strip():
                report["errors"].append(
                    f"video_assignments[{index}].match가 비어 있습니다."
                )
            else:
                matches = [item for item in videos if match in item.name]
                if len(matches) != 1:
                    report["errors"].append(
                        f"video_assignments[{index}] match '{match}' "
                        f"결과가 {len(matches)}개입니다."
                    )
            source_start = assignment.get(
                "source_start",
                assignment.get("source_start_seconds"),
            )
            if (
                source_start is not None
                and (
                    isinstance(source_start, bool)
                    or not isinstance(source_start, (int, float))
                    or float(source_start) < 0
                )
            ):
                report["errors"].append(
                    f"video_assignments[{index}].source_start는 "
                    "0 이상의 초 단위 숫자여야 합니다."
                )
            if bool(video_alignment.get("require_semantic_evidence", True)):
                tags = assignment.get(
                    "semantic_tags",
                    assignment.get("tags"),
                )
                if (
                    not isinstance(tags, list)
                    or not any(str(tag).strip() for tag in tags)
                    or not str(assignment.get("reason", "")).strip()
                ):
                    report["errors"].append(
                        "VIDEO_SEMANTIC_EVIDENCE_MISSING: "
                        f"video_assignments[{index}]에 semantic_tags와 "
                        "선택 reason이 필요합니다."
                    )

    segments = payload.get("audio_segments")
    if not isinstance(segments, list) or not segments:
        report["errors"].append("audio_segments는 비어 있지 않은 배열이어야 합니다.")
        segments = []
    matched_audio: list[str] = []
    caption_count = 0
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            report["errors"].append(f"audio_segments[{index}]는 객체여야 합니다.")
            continue
        pattern = segment.get("match")
        captions = segment.get("captions")
        if not isinstance(pattern, str) or not pattern.strip():
            report["errors"].append(f"audio_segments[{index}].match가 비어 있습니다.")
        else:
            matches = [item for item in audios if pattern in item.name]
            if len(matches) != 1:
                report["errors"].append(
                    f"audio_segments[{index}] match '{pattern}' 결과가 {len(matches)}개입니다."
                )
            else:
                matched_audio.append(matches[0].name)
        for trim_key in ("trim_start", "trim_end"):
            if trim_key not in segment:
                continue
            trim_value = segment[trim_key]
            if (
                isinstance(trim_value, bool)
                or not isinstance(trim_value, (int, float))
                or float(trim_value) < 0
            ):
                report["errors"].append(
                    f"audio_segments[{index}].{trim_key}는 0 이상의 초 단위 숫자여야 합니다."
                )
        if (
            isinstance(segment.get("trim_start"), (int, float))
            and not isinstance(segment.get("trim_start"), bool)
            and isinstance(segment.get("trim_end"), (int, float))
            and not isinstance(segment.get("trim_end"), bool)
            and float(segment["trim_start"]) >= float(segment["trim_end"])
        ):
            report["errors"].append(
                f"audio_segments[{index}]의 trim_start는 trim_end보다 작아야 합니다."
            )
        if not isinstance(captions, list) or not captions or not all(
            isinstance(caption, str) and caption.strip() for caption in captions
        ):
            report["errors"].append(
                f"audio_segments[{index}].captions는 비어 있지 않은 문자열 배열이어야 합니다."
            )
        else:
            caption_count += len(captions)

    if assignments is not None:
        expected_indices = list(range(1, caption_count + 1))
        if resolved_assignment_indices != expected_indices:
            report["errors"].append(
                "VIDEO_SECTION_COUNT_MISMATCH: video_assignments의 "
                "caption_index는 원본 대본 섹션 수와 같고 1부터 "
                "순서대로여야 합니다. "
                f"configured={resolved_assignment_indices}, "
                f"expected={expected_indices}"
            )
        if alignment_mode != "logical_caption":
            report["errors"].append(
                "video_assignments를 사용할 때 "
                "video_alignment.mode는 logical_caption이어야 합니다."
            )

    unused = [audio.name for audio in audios if audio.name not in matched_audio]
    if unused:
        report["warnings"].append({"unused_audio_files": unused})

    report.update(
        {
            "draft_name": payload.get("draft_name"),
            "video_dir": str(video_dir),
            "audio_dir": str(audio_dir),
            "video_files": len(videos),
            "audio_files": len(audios),
            "selected_audio_files": len(matched_audio),
            "video_cuts": (
                len(assignments)
                if isinstance(assignments, list)
                else (len(sequence) if isinstance(sequence, list) else 0)
            ),
            "captions": caption_count,
            "timing": timing,
            "video_alignment": video_alignment,
        }
    )
    return report


def inspect_path(path: Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.exists():
        return {"path": str(path), "errors": ["입력 경로가 없습니다."]}
    if path.is_file():
        if path.name == "project_manifest.json" or path.suffix.lower() == ".json":
            return validate_manifest(path)
        return {"kind": "media_file", **probe_media(path), "errors": []}

    files = [item for item in path.rglob("*") if item.is_file()]

    def under_reference_folder(item: Path) -> bool:
        relative_parts = {
            part.casefold()
            for part in item.relative_to(path).parts[:-1]
        }
        return bool(relative_parts & {"레퍼런스", "reference", "references"})

    reference_videos = [
        item
        for item in files
        if item.suffix.lower() in VIDEO_SUFFIXES and under_reference_folder(item)
    ]
    videos = [
        item
        for item in files
        if item.suffix.lower() in VIDEO_SUFFIXES
        and not under_reference_folder(item)
    ]
    audios = [item for item in files if item.suffix.lower() in AUDIO_SUFFIXES]
    images = [item for item in files if item.suffix.lower() in IMAGE_SUFFIXES]
    scripts = [
        item
        for item in files
        if item.suffix.lower() in {".txt", ".md"} and "대본" in item.stem
    ]
    manifests = [item for item in files if item.name == "project_manifest.json"]
    errors: list[str] = []
    warnings: list[Any] = []
    if not videos:
        errors.append("영상 파일을 찾지 못했습니다.")
    if not audios:
        warnings.append("별도 음성 파일이 없습니다. 영상 자체 음성을 쓰는 모드라면 정상입니다.")
    if not scripts:
        warnings.append("대본 파일을 찾지 못했습니다. 말하는 영상 모드는 Whisper 자막을 사용할 수 있습니다.")
    if images:
        warnings.append("이미지는 발견했지만 현재 v0.1 엔진은 이미지 자동 배치를 지원하지 않습니다.")
    return {
        "kind": "input_directory",
        "path": str(path),
        "videos": len(videos),
        "reference_videos": len(reference_videos),
        "references": [str(item) for item in reference_videos],
        "audios": len(audios),
        "images": len(images),
        "scripts": [str(item) for item in scripts],
        "manifests": [str(item) for item in manifests],
        "errors": errors,
        "warnings": warnings,
    }


def doctor(engine_root_value: str | None) -> int:
    report: dict[str, Any] = {
        "ffmpeg": shutil.which("ffmpeg"),
        "ffprobe": shutil.which("ffprobe"),
        "capcut_app": str(Path("/Applications/CapCut.app"))
        if Path("/Applications/CapCut.app").exists()
        else None,
        "draft_root": str(DEFAULT_DRAFT_ROOT),
        "draft_root_exists": DEFAULT_DRAFT_ROOT.is_dir(),
        "errors": [],
    }
    try:
        root = resolve_engine_root(engine_root_value)
        report["engine_root"] = str(root)
        report["engine_python"] = str(engine_python(root))
    except (FileNotFoundError, OSError) as exc:
        report["errors"].append(str(exc))
    if not report["ffmpeg"]:
        report["errors"].append("ffmpeg를 찾지 못했습니다.")
    if not report["ffprobe"]:
        report["errors"].append("ffprobe를 찾지 못했습니다.")
    if not report["capcut_app"]:
        report["errors"].append("/Applications/CapCut.app을 찾지 못했습니다.")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not report["errors"] else 2


def print_command(command: list[str]) -> None:
    import shlex

    print(shlex.join(command))


def validate_live_run_context(
    root: Path,
    *,
    run_context_value: str | None,
    expected_hash: str | None,
    expected_modes: set[str] | None = None,
) -> dict[str, str]:
    """Fail before a live edit when its compiled context is absent or stale."""

    if not run_context_value or not expected_hash:
        raise ValueError(
            "RUN_CONTEXT_REQUIRED: 실제 편집에는 --run-context와 "
            "--run-context-hash가 모두 필요합니다."
        )
    path = Path(run_context_value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"RUN_CONTEXT_REQUIRED: 계약 파일이 없습니다: {path}")

    root_string = str(root)
    if root_string not in sys.path:
        sys.path.insert(0, root_string)
    from capcut_auto.run_context import validate_run_contract

    try:
        validation = validate_run_contract(path, require_fresh=True, sync_sources=False)
    except (OSError, ValueError) as exc:
        message = str(exc)
        if message.startswith("RUN_CONTEXT_"):
            raise ValueError(message) from exc
        raise ValueError(f"RUN_CONTEXT_STALE: {message}") from exc

    payload = validation.get("contract") if isinstance(validation, dict) else None
    if not isinstance(payload, dict):
        raise ValueError(
            "RUN_CONTEXT_STALE: validator가 검증된 contract snapshot을 반환하지 않았습니다."
        )
    actual_hash = str(payload.get("run_context_hash") or "")
    if not actual_hash or actual_hash != expected_hash:
        raise ValueError(
            "RUN_CONTEXT_HASH_MISMATCH: 전달된 해시와 계약의 "
            f"run_context_hash가 다릅니다 ({expected_hash} != {actual_hash})."
        )
    actual_mode = str(payload.get("mode") or "")
    if expected_modes and actual_mode not in expected_modes:
        allowed = ", ".join(sorted(expected_modes))
        raise ValueError(
            "RUN_CONTEXT_MODE_MISMATCH: 이 실행은 "
            f"[{allowed}] 계약만 허용하지만 {actual_mode!r}가 전달됐습니다."
        )
    return {"path": str(path), "hash": actual_hash, "mode": actual_mode}


def run_font_style_interview(args: argparse.Namespace) -> int:
    root = resolve_engine_root(args.engine_root)
    command = [
        str(engine_python(root)),
        "-m",
        "capcut_auto.font_style_interview",
        args.font_style_command,
    ]
    if args.font_style_command == "select":
        command.append(args.choice)
        if args.reference:
            command.extend(
                ["--reference", str(Path(args.reference).expanduser().resolve())]
            )
    return subprocess.run(command, cwd=root, check=False).returncode


def run_editing_interview(args: argparse.Namespace) -> int:
    root = resolve_engine_root(args.engine_root)
    command = [
        str(engine_python(root)),
        "-m",
        "capcut_auto.editing_interview",
        args.interview_command,
    ]
    if args.interview_command == "select-style":
        command.append(args.choice)
    elif args.interview_command == "font-menu":
        command.extend(["--style", args.style])
    elif args.interview_command == "select-font":
        command.extend([args.choice, "--style", args.style])
        if args.reference:
            command.extend(
                ["--reference", str(Path(args.reference).expanduser().resolve())]
            )
    return subprocess.run(command, cwd=root, check=False).returncode


def run_engine(args: argparse.Namespace) -> int:
    root = resolve_engine_root(args.engine_root)
    python = engine_python(root)
    if not args.dry_run and getattr(args, "open_capcut", False):
        raise ValueError(
            "RUN_CONTEXT_FORBIDDEN_ACTION: 현재 run contract는 CapCut GUI 실행 권한을 발급하지 않습니다."
        )
    if not args.dry_run:
        validate_live_run_context(
            root,
            run_context_value=getattr(args, "run_context", None),
            expected_hash=getattr(args, "run_context_hash", None),
            expected_modes={"base_cut", "feedback_revision"},
        )
        raise ValueError(
            "RUN_CONTEXT_TARGET_BINDING_REQUIRED: legacy talking-head/voiceover wrapper는 "
            "exact existing project, source timeline, destination timeline binding을 지원하지 않으므로 "
            "live mutation이 금지됩니다."
        )
    if args.command == "talking-head":
        video = Path(args.video).expanduser().resolve()
        if not video.is_file():
            raise FileNotFoundError(f"원본 영상이 없습니다: {video}")
        command = [str(python), "-m", "capcut_auto", str(video)]
        if args.config:
            command.extend(["--config", str(Path(args.config).expanduser().resolve())])
        if args.model:
            command.extend(["--model", args.model])
        if args.draft_name:
            command.extend(["--draft-name", args.draft_name])
        if args.output_dir:
            command.extend(["--output-dir", str(Path(args.output_dir).expanduser().resolve())])
        if args.preview:
            command.append("--preview")

    else:
        manifest = Path(args.manifest).expanduser().resolve()
        validation = validate_manifest(manifest)
        if validation["errors"]:
            print(json.dumps(validation, ensure_ascii=False, indent=2), file=sys.stderr)
            return 2
        command = [
            str(python),
            "-m",
            "capcut_auto.voiceover_cli",
            str(manifest),
        ]
        if args.draft_name:
            command.extend(["--draft-name", args.draft_name])
        if args.draft_root:
            command.extend(["--draft-root", str(Path(args.draft_root).expanduser().resolve())])
        if args.replace_draft:
            command.append("--replace-draft")
        if args.no_trim_silence:
            command.append("--no-trim-silence")
        if args.silence_db is not None:
            command.extend(["--silence-db", str(args.silence_db)])
        if args.silence_min_duration is not None:
            command.extend(
                ["--silence-min-duration", str(args.silence_min_duration)]
            )
        if args.head_padding is not None:
            command.extend(["--head-padding", str(args.head_padding)])
        if args.tail_padding is not None:
            command.extend(["--tail-padding", str(args.tail_padding)])
        if args.caption_alignment:
            command.extend(["--caption-alignment", args.caption_alignment])
        if args.model:
            command.extend(["--model", args.model])
        if args.language:
            command.extend(["--language", args.language])

    print_command(command)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor_parser = subparsers.add_parser("doctor", help="엔진과 CapCut 실행 환경 확인")
    doctor_parser.add_argument("--engine-root")

    inspect_parser = subparsers.add_parser("inspect", help="입력 폴더 또는 매니페스트 검사")
    inspect_parser.add_argument("path")

    interview = subparsers.add_parser(
        "interview",
        help="편집 스타일을 먼저 고르고 폰트를 고르는 필수 인터뷰",
    )
    interview.add_argument("--engine-root")
    interview_subparsers = interview.add_subparsers(
        dest="interview_command",
        required=True,
    )
    interview_subparsers.add_parser("style-menu", help="첫 단계 편집 스타일 질문")
    interview_style = interview_subparsers.add_parser(
        "select-style",
        help="편집 스타일 선택 기록",
    )
    interview_style.add_argument("choice")
    interview_font_menu = interview_subparsers.add_parser(
        "font-menu",
        help="스타일 선택 후 폰트 질문",
    )
    interview_font_menu.add_argument("--style", required=True)
    interview_font = interview_subparsers.add_parser(
        "select-font",
        help="스타일과 폰트 선택을 완료",
    )
    interview_font.add_argument("choice")
    interview_font.add_argument("--style", required=True)
    interview_font.add_argument("--reference")

    font_style = subparsers.add_parser(
        "font-style",
        help="초안 생성 전 필수 폰트 스타일 인터뷰",
    )
    font_style.add_argument("--engine-root")
    font_style_subparsers = font_style.add_subparsers(
        dest="font_style_command",
        required=True,
    )
    font_style_subparsers.add_parser("menu", help="선택 질문 표시")
    font_style_select = font_style_subparsers.add_parser(
        "select",
        help="선택값을 매니페스트 조각으로 변환",
    )
    font_style_select.add_argument("choice")
    font_style_select.add_argument("--reference")

    talking = subparsers.add_parser("talking-head", help="영상 자체 음성의 무음·말버릇·반복 제거")
    talking.add_argument("video")
    talking.add_argument("--engine-root")
    talking.add_argument("--config")
    talking.add_argument("--model")
    talking.add_argument("--draft-name")
    talking.add_argument("--output-dir")
    talking.add_argument("--preview", action="store_true")
    talking.add_argument("--open-capcut", action="store_true")
    talking.add_argument("--dry-run", action="store_true")
    talking.add_argument("--run-context")
    talking.add_argument("--run-context-hash")

    voiceover = subparsers.add_parser("voiceover", help="클린본 영상과 별도 음성으로 몽타주 생성")
    voiceover.add_argument("manifest")
    voiceover.add_argument("--engine-root")
    voiceover.add_argument("--draft-root")
    voiceover.add_argument("--draft-name")
    voiceover.add_argument("--replace-draft", action="store_true")
    voiceover.add_argument("--no-trim-silence", action="store_true")
    voiceover.add_argument("--silence-db", type=float)
    voiceover.add_argument("--silence-min-duration", type=float)
    voiceover.add_argument("--head-padding", type=float)
    voiceover.add_argument("--tail-padding", type=float)
    voiceover.add_argument(
        "--caption-alignment",
        choices=("whisper", "proportional"),
    )
    voiceover.add_argument("--model")
    voiceover.add_argument("--language")
    voiceover.add_argument("--open-capcut", action="store_true")
    voiceover.add_argument("--dry-run", action="store_true")
    voiceover.add_argument("--run-context")
    voiceover.add_argument("--run-context-hash")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command == "doctor":
            return doctor(args.engine_root)
        if args.command == "inspect":
            report = inspect_path(Path(args.path))
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0 if not report.get("errors") else 2
        if args.command == "interview":
            return run_editing_interview(args)
        if args.command == "font-style":
            return run_font_style_interview(args)
        return run_engine(args)
    except KeyboardInterrupt:
        print("작업을 취소했습니다.", file=sys.stderr)
        return 130
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

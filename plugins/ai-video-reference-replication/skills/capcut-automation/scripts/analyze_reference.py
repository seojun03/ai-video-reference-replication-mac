#!/usr/bin/env python3
"""Analyze a reference video and create a reusable editing-style profile."""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import statistics
import subprocess
from pathlib import Path
from typing import Any, Sequence


SHOWINFO_TIME_RE = re.compile(r"\bpts_time:([0-9.]+)")
LOUDNESS_JSON_RE = re.compile(
    r"\{\s*\"input_i\".*?\"target_offset\"\s*:\s*\"[^\"]+\"\s*\}",
    re.DOTALL,
)


def require_binary(name: str) -> str:
    value = shutil.which(name)
    if value is None:
        raise RuntimeError(f"{name}를 찾지 못했습니다. FFmpeg를 먼저 설치해 주세요.")
    return value


def run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        check=False,
        capture_output=True,
        text=True,
    )


def probe_video(path: Path) -> dict[str, Any]:
    ffprobe = require_binary("ffprobe")
    completed = run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ]
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "ffprobe 실행에 실패했습니다.")
    payload = json.loads(completed.stdout)
    streams = payload.get("streams", [])
    video = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    if video is None:
        raise ValueError(f"비디오 트랙이 없습니다: {path}")

    def rate(value: str | None) -> float:
        if not value or value == "0/0":
            return 0.0
        if "/" in value:
            numerator, denominator = value.split("/", 1)
            denominator_value = float(denominator)
            return float(numerator) / denominator_value if denominator_value else 0.0
        return float(value)

    duration = float(
        video.get("duration")
        or payload.get("format", {}).get("duration")
        or 0
    )
    if duration <= 0:
        raise ValueError(f"영상 길이를 읽지 못했습니다: {path}")
    width = int(video["width"])
    height = int(video["height"])
    return {
        "duration": duration,
        "width": width,
        "height": height,
        "aspect_ratio": width / height,
        "fps": rate(video.get("avg_frame_rate") or video.get("r_frame_rate")),
        "video_codec": video.get("codec_name"),
        "has_audio": any(
            stream.get("codec_type") == "audio" for stream in streams
        ),
        "audio_codec": next(
            (
                stream.get("codec_name")
                for stream in streams
                if stream.get("codec_type") == "audio"
            ),
            None,
        ),
    }


def detect_scene_cuts(
    path: Path,
    duration: float,
    threshold: float,
) -> list[float]:
    ffmpeg = require_binary("ffmpeg")
    completed = run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-vf",
            f"select='gt(scene,{threshold})',showinfo",
            "-an",
            "-f",
            "null",
            "-",
        ]
    )
    cuts = [
        float(match.group(1))
        for match in SHOWINFO_TIME_RE.finditer(completed.stderr)
    ]
    return sorted(
        {
            round(value, 6)
            for value in cuts
            if 0.05 < value < duration - 0.05
        }
    )


def shot_statistics(duration: float, cuts: Sequence[float]) -> dict[str, Any]:
    boundaries = [0.0, *cuts, duration]
    shot_durations = [
        right - left for left, right in zip(boundaries, boundaries[1:])
    ]
    return {
        "scene_cut_count": len(cuts),
        "scene_cut_timestamps": list(cuts),
        "shot_count": len(shot_durations),
        "shot_durations": [round(value, 4) for value in shot_durations],
        "average_shot_duration": round(statistics.mean(shot_durations), 4),
        "median_shot_duration": round(statistics.median(shot_durations), 4),
        "shortest_shot": round(min(shot_durations), 4),
        "longest_shot": round(max(shot_durations), 4),
        "cuts_per_minute": round(len(cuts) * 60 / duration, 2),
    }


def select_sample_times(
    duration: float,
    cuts: Sequence[float],
    maximum: int,
) -> list[float]:
    regular = [
        duration * index / max(1, maximum - 1)
        for index in range(maximum)
    ]
    candidates = [
        min(duration - 0.03, max(0.0, value))
        for value in [0.05, *regular, *[cut + 0.04 for cut in cuts]]
    ]
    unique: list[float] = []
    for value in sorted(candidates):
        if not unique or value - unique[-1] >= 0.08:
            unique.append(value)
    if len(unique) <= maximum:
        return unique
    if maximum == 1:
        return [unique[len(unique) // 2]]
    selected_indexes = {
        round(index * (len(unique) - 1) / (maximum - 1))
        for index in range(maximum)
    }
    return [unique[index] for index in sorted(selected_indexes)]


def export_review_frames(
    path: Path,
    output_dir: Path,
    times: Sequence[float],
) -> tuple[list[dict[str, Any]], Path | None]:
    ffmpeg = require_binary("ffmpeg")
    frame_dir = output_dir / "frames"
    frame_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, timestamp in enumerate(times, start=1):
        frame_path = frame_dir / f"frame_{index:02d}_{timestamp:08.3f}s.jpg"
        completed = run(
            [
                ffmpeg,
                "-y",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                str(frame_path),
            ]
        )
        if completed.returncode != 0:
            continue
        records.append({"time": round(timestamp, 6), "path": str(frame_path)})

    if not records:
        return records, None
    columns = min(4, len(records))
    rows = math.ceil(len(records) / columns)
    contact_sheet = output_dir / "contact_sheet.jpg"
    completed = run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-framerate",
            "1",
            "-pattern_type",
            "glob",
            "-i",
            str(frame_dir / "frame_*.jpg"),
            "-vf",
            (
                "scale=320:-2,"
                f"tile={columns}x{rows}:padding=8:margin=8:color=black"
            ),
            "-frames:v",
            "1",
            str(contact_sheet),
        ]
    )
    return records, contact_sheet if completed.returncode == 0 else None


def analyze_loudness(path: Path) -> dict[str, Any] | None:
    ffmpeg = require_binary("ffmpeg")
    completed = run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json",
            "-vn",
            "-f",
            "null",
            "-",
        ]
    )
    matches = list(LOUDNESS_JSON_RE.finditer(completed.stderr))
    if not matches:
        return None
    try:
        payload = json.loads(matches[-1].group(0))
    except json.JSONDecodeError:
        return None
    result: dict[str, Any] = {}
    for key, value in payload.items():
        try:
            result[key] = float(value)
        except (TypeError, ValueError):
            result[key] = value
    return result


def extract_audio(path: Path, output_dir: Path) -> Path | None:
    ffmpeg = require_binary("ffmpeg")
    audio_path = output_dir / "reference_audio.m4a"
    completed = run(
        [
            ffmpeg,
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vn",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(audio_path),
        ]
    )
    return audio_path if completed.returncode == 0 else None


def build_profile(
    source: Path,
    media: dict[str, Any],
    editing: dict[str, Any],
    frames: Sequence[dict[str, Any]],
    contact_sheet: Path | None,
    loudness: dict[str, Any] | None,
    audio_path: Path | None,
    scene_threshold: float,
) -> dict[str, Any]:
    return {
        "status": "needs_visual_and_audio_review",
        "reference": {
            "path": str(source),
            "file_name": source.name,
            "size_bytes": source.stat().st_size,
        },
        "canvas": media,
        "editing_rhythm": {
            **editing,
            "scene_threshold": scene_threshold,
            "hook_duration": None,
            "transition_types": [],
            "speed_ramps": [],
            "punch_in_pattern": None,
        },
        "review_assets": {
            "contact_sheet": str(contact_sheet) if contact_sheet else None,
            "frames": list(frames),
            "audio": str(audio_path) if audio_path else None,
        },
        "caption_style": {
            "font_family": None,
            "fallback_font": None,
            "weight": None,
            "size_px": None,
            "size_ratio_of_frame_height": None,
            "text_color": None,
            "highlight_colors": [],
            "outline_color": None,
            "outline_width": None,
            "shadow": None,
            "position": None,
            "max_lines": None,
            "words_per_caption": None,
            "animation_in": None,
            "animation_out": None,
            "emphasis_rules": [],
            "confidence": "unreviewed",
        },
        "visual_effects": [],
        "sound_effects": [],
        "music": {
            "identified_title": None,
            "reuse_rights_confirmed": False,
            "genre": None,
            "mood": None,
            "bpm_estimate": None,
            "loudness_analysis": loudness,
            "voice_ducking": None,
            "entry_exit_pattern": None,
            "confidence": "unreviewed",
        },
        "application_rules": {
            "cut_mapping": "Map new video cuts to the reference shot-duration distribution and spoken phrase boundaries.",
            "caption_mapping": "Match reference typography and animation while keeping captions aligned to actual word timestamps.",
            "effect_mapping": "Match the function and timing trigger of each effect; do not add unobserved effects.",
            "audio_mapping": "Use licensed or user-provided music/SFX with equivalent function and mix balance.",
        },
        "review_checklist": [
            "Inspect every exported frame and the contact sheet.",
            "Listen to the extracted audio with the original video.",
            "Fill all observable caption, visual-effect, sound-effect, and music fields.",
            "Record unknown items as unknown; do not invent exact font or track names.",
            "Set status to ready only after the style blueprint is complete.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", help="분석할 레퍼런스 영상")
    parser.add_argument("--output", required=True, help="분석 결과 폴더")
    parser.add_argument(
        "--scene-threshold",
        type=float,
        default=0.25,
        help="장면 전환 민감도 0~1, 낮을수록 더 많은 컷 감지",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=12,
        help="육안 검수용 최대 프레임 수",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="검수용 오디오 추출 생략",
    )
    args = parser.parse_args()

    if not 0 < args.scene_threshold < 1:
        raise ValueError("--scene-threshold는 0과 1 사이여야 합니다.")
    if args.max_frames < 1:
        raise ValueError("--max-frames는 1 이상이어야 합니다.")
    source = Path(args.video).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"레퍼런스 영상을 찾을 수 없습니다: {source}")
    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    media = probe_video(source)
    cuts = detect_scene_cuts(source, media["duration"], args.scene_threshold)
    editing = shot_statistics(media["duration"], cuts)
    sample_times = select_sample_times(
        media["duration"],
        cuts,
        args.max_frames,
    )
    frames, contact_sheet = export_review_frames(
        source,
        output,
        sample_times,
    )
    loudness = analyze_loudness(source) if media["has_audio"] else None
    audio_path = (
        extract_audio(source, output)
        if media["has_audio"] and not args.no_audio
        else None
    )
    profile = build_profile(
        source,
        media,
        editing,
        frames,
        contact_sheet,
        loudness,
        audio_path,
        args.scene_threshold,
    )
    profile_path = output / "style_profile.json"
    profile_path.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("레퍼런스 스타일 분석 완료")
    print(f"- 프로필: {profile_path}")
    print(f"- 검수 프레임: {len(frames)}개")
    print(f"- 장면 컷: {len(cuts)}개")
    print(f"- 평균 컷 길이: {editing['average_shot_duration']:.2f}초")
    if contact_sheet:
        print(f"- 콘택트시트: {contact_sheet}")
    if audio_path:
        print(f"- 검수 오디오: {audio_path}")
    print("- 다음 단계: 프레임과 오디오를 직접 검수하고 프로필의 미확정 필드를 채우세요.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Create a non-destructive client/job input structure for CapCut automation."""

from __future__ import annotations

import argparse
import os
import json
import re
from pathlib import Path


INVALID_COMPONENT = re.compile(r"[/:\x00]")
DEFAULT_CLIENT_ROOT = Path(os.environ.get("VIDEO_PRODUCT_LIBRARY_ROOT", str(Path.home() / "Documents" / "인코어")))


def safe_component(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned or cleaned in {".", ".."} or INVALID_COMPONENT.search(cleaned):
        raise ValueError(f"{label} 이름으로 사용할 수 없습니다: {value!r}")
    return cleaned


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "root",
        nargs="?",
        default=DEFAULT_CLIENT_ROOT,
        help=(
            "업체별 작업 폴더를 만들 상위 경로 "
            f"(기본값: {DEFAULT_CLIENT_ROOT})"
        ),
    )
    parser.add_argument("--client", required=True, help="업체명")
    parser.add_argument("--job", required=True, help="작업명")
    args = parser.parse_args()

    client = safe_component(args.client, "업체")
    job = safe_component(args.job, "작업")
    job_root = Path(args.root).expanduser().resolve() / client / job
    input_dir = job_root / "input"
    for name in ("영상", "음성", "이미지", "레퍼런스"):
        (input_dir / name).mkdir(parents=True, exist_ok=True)
    (job_root / "output").mkdir(parents=True, exist_ok=True)

    script_path = input_dir / "대본.txt"
    if not script_path.exists():
        script_path.write_text(
            "여기에 최종 대본을 붙여 넣으세요.\n",
            encoding="utf-8",
        )

    manifest_path = input_dir / "project_manifest.json"
    if not manifest_path.exists():
        payload = {
            "draft_name": f"{client}_{job}_자동편집",
            "video_dir": "영상",
            "audio_dir": "음성",
            "timing": {
                "trim_silence": True,
                "silence_db": -42.0,
                "silence_min_duration": 0.03,
                "head_padding": 0.02,
                "tail_padding": 0.05,
                "caption_alignment": "whisper",
                "whisper_model": "small",
                "language": "ko",
            },
            "video_alignment": {
                "mode": "logical_caption",
                "require_whisper_alignment": True,
                "require_semantic_evidence": True,
                "tolerance_seconds": 0.001,
            },
            "audio_segments": [],
            "video_assignments": [],
            "notes": [],
        }
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    print(job_root)
    print(f"- 대본: {script_path}")
    print(f"- 영상: {input_dir / '영상'}")
    print(f"- 음성: {input_dir / '음성'}")
    print(f"- 이미지: {input_dir / '이미지'}")
    print(f"- 레퍼런스: {input_dir / '레퍼런스'}")
    print(f"- 매니페스트: {manifest_path}")
    print(f"- 출력: {job_root / 'output'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

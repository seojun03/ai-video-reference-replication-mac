#!/usr/bin/env python3
"""Agent-facing entrypoint. No force/skip gates or legacy writer fallback."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from semantic_contract import PlanError, read_json, require, validate_plan, write_new_json
from semantic_media import analyze_voice, contact_sheet, file_ref, inventory, outside_project, prepare_audio
from semantic_native import _check_media, bind_project, install_timeline, resolve_project, stage_timeline, verify_install


def parser():
    p = argparse.ArgumentParser(description="대본·클린본·사용자 음성의 문맥별 CapCut 컷편집 보조 도구")
    subs = p.add_subparsers(dest="command", required=True)
    inv = subs.add_parser("inventory", help="사용자가 지정한 원본 목록·해시·길이 확인")
    inv.add_argument("--script", required=True); inv.add_argument("--voice", required=True)
    inv.add_argument("--clean", action="append", default=[])
    inv.add_argument("--clean-dir", action="append", default=[])
    inv.add_argument("--product", required=True); inv.add_argument("--output", required=True)
    init = subs.add_parser("init-plan", help="검토 전 빈 계획 생성; 곧바로 저장할 수 없음")
    init.add_argument("--inventory", required=True); init.add_argument("--category", choices=["supplement", "beauty", "food", "other"], required=True)
    init.add_argument("--voice-kind", choices=["recorded", "tts"], required=True)
    init.add_argument("--use-action", choices=["eating", "application", "product_use"], required=True)
    init.add_argument("--fps", type=int, default=30); init.add_argument("--font")
    init.add_argument("--output", required=True)
    inspect = subs.add_parser("contact-sheet", help="실제 선택 구간의 시작·중간·끝 화면 추출")
    inspect.add_argument("--inventory", required=True); inspect.add_argument("--asset-id", required=True)
    inspect.add_argument("--start-us", type=int, required=True); inspect.add_argument("--end-us", type=int, required=True)
    inspect.add_argument("--scale", type=float, default=1); inspect.add_argument("--center-x", type=float, default=.5)
    inspect.add_argument("--center-y", type=float, default=.5); inspect.add_argument("--output", required=True)
    audio = subs.add_parser("analyze-voice", help="무음 후보·파형만 분석; 자동 삭제/단어 추정 없음")
    audio.add_argument("--inventory", required=True); audio.add_argument("--kind", choices=["recorded", "tts"], required=True)
    audio.add_argument("--output", required=True)
    prepare = subs.add_parser("prepare-audio", help="계획에 적힌 원본 음성 컷으로 최종 확인 음성 생성")
    prepare.add_argument("--plan", required=True); prepare.add_argument("--output", required=True)
    validate = subs.add_parser("validate", help="실제 원본·프레임·음성·자막 계획을 검사; 저장 안 함")
    validate.add_argument("--plan", required=True); validate.add_argument("--output")
    resolve = subs.add_parser("resolve-project", help="기존 프로젝트의 저장 형식 연결을 자동 확인; 편집 기준 선택 아님")
    for key in ("project", "project-name"): resolve.add_argument("--" + key, required=True)
    resolve.add_argument("--source-id", help="사용자가 기존 타임라인을 명시한 경우에만 지정")
    resolve.add_argument("--source-name", help="사용자가 기존 타임라인을 명시한 경우에만 지정")
    bind = subs.add_parser("bind", help="정확한 기존 업체 프로젝트와 새 목적지를 읽기 전용으로 고정")
    for key in ("plan", "project", "project-name", "output"):
        bind.add_argument("--" + key, required=True)
    bind.add_argument("--source-id", help="생략하면 같은 프로젝트의 저장 형식만 자동 연결")
    bind.add_argument("--source-name", help="생략 가능; 명시된 이름은 실제 프로젝트에서 확인")
    bind.add_argument("--destination-name", help="생략하면 제품명 기반의 충돌 없는 새 이름 생성")
    stage = subs.add_parser("stage", help="프로젝트 밖에 편집 가능한 준비본 작성")
    for key in ("plan", "binding", "output"): stage.add_argument("--" + key, required=True)
    install = subs.add_parser("install", help="CapCut 정상 종료 후, 기존 프로젝트에 새 타임라인 1개 추가")
    install.add_argument("--stage", required=True)
    verify = subs.add_parser("verify", help="등록본과 원본 보존을 다시 읽어 검사; GUI 재생 아님")
    verify.add_argument("--stage", required=True); verify.add_argument("--output")
    return p


def default_font():
    candidates = [Path.home() / "Library/Fonts/Pretendard-SemiBold.otf",
                  Path.home() / "Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts/Pretendard-SemiBold.otf"]
    path = next((p for p in candidates if p.is_file()), None)
    require(path is not None, "FONT_REQUIRED", "provide an installed local font path with --font")
    return path


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "inventory":
            clean = list(args.clean)
            for directory in args.clean_dir:
                directory = Path(directory).expanduser().resolve()
                require(directory.is_dir(), "CLEAN_DIRECTORY_REQUIRED", str(directory))
                clean.extend(str(p) for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in
                             (".mp4", ".mov", ".m4v", ".mkv", ".webm", ".mts"))
            result = inventory(args.script, args.voice, clean, args.product)
            write_new_json(outside_project(args.output), result)
            result = {"status": "inventory_created", "path": str(Path(args.output).resolve()), "assets": len(result["assets"])}
        elif args.command == "init-plan":
            inv = read_json(args.inventory)
            require(inv["schema"] == "capcut-semantic-inventory/v1", "INVENTORY_SCHEMA")
            require(1 <= args.fps <= 120, "FPS_UNSUPPORTED")
            duration = inv["assets"]["voice"]["duration_us"] * args.fps // 1_000_000
            result = {"schema": "capcut-semantic-plan/v1", "category": args.category, "product": inv["product"],
                      "use_action": args.use_action, "script": inv["script"], "assets": inv["assets"],
                      "composition": {"width": 1080, "height": 1920, "fps": args.fps, "duration_frames": duration},
                      "voice": {"asset_id": "voice", "kind": args.voice_kind, "cuts": [{"start_frame": 0, "end_frame": duration, "source_in_us": 0}],
                                "review_note": "", "transcript": ""},
                      "caption_style": {"font": file_ref(args.font or default_font())},
                      "beats": [], "captions": [], "clips": [], "gaps": []}
            write_new_json(outside_project(args.output), result)
            result = {"status": "draft_requires_voice_and_visual_review", "path": str(Path(args.output).resolve())}
        elif args.command == "contact-sheet":
            inv = read_json(args.inventory)
            result = contact_sheet(inv["assets"][args.asset_id], args.start_us, args.end_us,
                                   {"scale": args.scale, "center_x": args.center_x, "center_y": args.center_y}, args.output)
            result = {"status": "frames_extracted_not_reviewed", "review_path": str(Path(args.output).resolve() / "review.json"),
                      "contact_sheet": result["contact_sheet"]["path"]}
        elif args.command == "analyze-voice":
            result = analyze_voice(read_json(args.inventory)["assets"]["voice"], args.kind, args.output)
            result = {"status": result["status"], "path": str(Path(args.output).resolve() / "voice-analysis.json"),
                      "candidate_count": len(result["silence_candidates"])}
        elif args.command == "prepare-audio":
            result = prepare_audio(read_json(args.plan), args.output)
            result = {"status": "audio_prepared_onsets_require_review", "path": str(Path(args.output).resolve() / "speech-evidence.json"),
                      "audio": result["audio"], "cut_sha256": result["cut_sha256"]}
        elif args.command == "validate":
            plan = read_json(args.plan)
            result = validate_plan(plan)
            _check_media(plan)
            if args.output: write_new_json(outside_project(args.output), result)
        elif args.command == "resolve-project":
            result = resolve_project(args.project, args.project_name, args.source_id, args.source_name)
        elif args.command == "bind":
            result = bind_project(args.plan, args.project, args.project_name, args.source_id, args.source_name, args.destination_name)
            write_new_json(outside_project(args.output), result)
            result = {"status": "target_bound_not_written", "path": str(Path(args.output).resolve()),
                      "timeline_id": result["destination_id"], "timeline_name": result["destination_name"],
                      "source_selection": result["source_selection"], "source_purpose": result["source_purpose"]}
        elif args.command == "stage":
            result = stage_timeline(args.plan, read_json(args.binding), args.output)
            result = {"status": result["status"], "path": str(Path(args.output).resolve())}
        elif args.command == "install":
            result = install_timeline(args.stage)
        else:
            result = verify_install(args.stage)
            if args.output: write_new_json(outside_project(args.output), result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (PlanError, OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

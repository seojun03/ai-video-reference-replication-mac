from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
LINTER = SKILL_ROOT / "scripts" / "lint_cut_plan.py"
SEMANTIC_VALIDATOR = SKILL_ROOT / "scripts" / "validate_semantic_qc.py"
MEDIA_QC = SKILL_ROOT / "scripts" / "qc_media.py"


def valid_plan() -> dict:
    return {
        "schema_version": 4,
        "reference_use_mode": "clean_visual_reference_only",
        "selected_start_reuse_policy": "forbid_across_cuts",
        "semantic_visual_contract": "literal_visual_proof_v1",
        "duration_policy": "adaptive_3_4_5_seconds",
        "quality_profile": "balanced_auto",
        "reserve_policy": "on_demand_after_main_qc",
        "image_generation_mode": "openai_only",
        "image_generation_route": "built_in_image_gen",
        "image_candidates_per_cut": 1,
        "higgsfield_image_jobs": 0,
        "image_api_jobs": 0,
        "image_cli_jobs": 0,
        "semantic_retry_policy": {
            "paid_retries": False,
            "authorized_in_gate_1": False,
            "max_semantic_retries_total": 0,
            "semantic_retry_budget_credits": 0,
        },
        "cuts": [
            {
                "cut": 1,
                "script": "마른 덩어리가 수분을 머금고 부드럽게 이동한다.",
                "visual_job": "같은 덩어리가 건조 상태에서 수분을 흡수해 이동하는 인과를 보여준다.",
                "style_reference": "reference_style_v1",
                "expression_reference": "material_change_v1",
                "composition_reference": "macro_side_v1",
                "native_camera_motion": "slow physical follow",
                "editing_effects": "forbidden",
                "reference_technique": "mechanism causal progression",
                "composition": "macro side view with clear route",
                "medium": "soft 3D illustration",
                "must_show": "같은 덩어리가 수분을 흡수해 부드러워지고 이동 완료",
                "hard_exclusions": ["물컵만 보여주기", "대상이 중간에 바뀌기"],
                "risk_level": "low",
                "image_quality": "low",
                "product_presence": "forbidden",
                "scene_design": {
                    "setting": "clean macro channel",
                    "subject_action": "dry mass absorbs moisture and travels",
                    "shot_scale": "extreme macro",
                    "camera_angle": "side cutaway without a human body",
                },
                "semantic_units": [
                    {
                        "id": "1a",
                        "text": "마른 덩어리가 수분을 머금는다",
                        "required_visual_evidence": "동일한 덩어리 표면에 수분이 스며들며 균열이 완화된다",
                    },
                    {
                        "id": "1b",
                        "text": "부드럽게 이동한다",
                        "required_visual_evidence": "부드러워진 동일 덩어리가 막힘 없이 출구 방향으로 이동한다",
                    },
                ],
                "visual_proof": {
                    "subject": "한 개의 동일한 마른 덩어리",
                    "start_state": "어둡고 갈라져 통로에 걸린 상태",
                    "visible_action": "수분이 스며들어 표면이 부드러워지고 덩어리가 전진",
                    "end_state": "부드러워진 덩어리가 통로를 통과한 상태",
                    "causal_link": "수분 흡수 뒤에만 이동이 시작됨",
                    "success_frame": "출구를 통과한 동일 덩어리와 비워진 통로가 한 프레임에 보임",
                    "forbidden_shortcuts": ["물컵만 보여주기", "화살표나 아이콘만으로 설명하기"],
                },
                "duration_class": "causal_transformation",
                "duration_seconds": 5.0,
                "duration_reason": "흡수 전, 흡수 진행, 이동 완료의 세 상태가 모두 필요",
                "motion_design": {
                    "primary_motion": "the same dry mass absorbs moisture and moves through the channel",
                    "secondary_motion": "small moisture beads merge into the mass surface",
                    "camera_motion": "slow side follow that keeps the mass centered",
                    "static_anchors": ["channel wall", "single mass identity", "exit direction"],
                    "motion_phases": "0.0-1.0 dry blockage -> 1.0-3.2 absorption -> 3.2-5.0 clear passage",
                },
                "image_prompt": "A clean macro channel with one cracked dry mass, action-ready, no text",
                "motion_prompt": "같은 덩어리에 수분이 스며들고 부드러워진 뒤 통로를 끝까지 이동한다.",
                "route": "Higgsfield Kling v3.0 — start image only",
                "deterministic_post": [],
                "cost": "planned",
            }
        ],
        "reserve_cuts": [],
    }


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run_script(script: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *args], text=True, capture_output=True)


def test_schema4_plan_passes_strict_lint(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, valid_plan())
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 0, result.stdout + result.stderr


def test_missing_visual_proof_fails_strict_lint(tmp_path: Path) -> None:
    plan = valid_plan()
    del plan["cuts"][0]["visual_proof"]
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 1
    assert "requires visual_proof object" in result.stdout


def test_duration_class_mismatch_fails_strict_lint(tmp_path: Path) -> None:
    plan = valid_plan()
    plan["cuts"][0]["duration_seconds"] = 3.0
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 1
    assert "requires duration_seconds=5.0" in result.stdout


def test_higgsfield_image_mode_fails_strict_lint(tmp_path: Path) -> None:
    plan = valid_plan()
    plan["image_generation_mode"] = "higgsfield_only"
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 1
    assert "Higgsfield still-image generation is forbidden" in result.stdout


def test_nonzero_higgsfield_image_jobs_fail_strict_lint(tmp_path: Path) -> None:
    plan = valid_plan()
    plan["higgsfield_image_jobs"] = 1
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 1
    assert "higgsfield_image_jobs must be 0" in result.stdout


def test_direct_image_api_route_fails_strict_lint(tmp_path: Path) -> None:
    plan = valid_plan()
    plan["image_generation_route"] = "openai_images_api"
    plan["image_api_jobs"] = 1
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)
    result = run_script(LINTER, str(plan_path), "--strict-schema")
    assert result.returncode == 1
    assert "image_generation_route must be built_in_image_gen" in result.stdout
    assert "image_api_jobs must be 0" in result.stdout


def semantic_review(plan_path: Path, *, unit_pass: bool = True) -> dict:
    return {
        "schema": "semantic-visual-qc",
        "schema_version": 1,
        "plan_sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
        "cuts": [
            {
                "cut": 1,
                "duration_seconds": 5.0,
                "sample_checkpoint_count": 5,
                "unit_results": [
                    {"semantic_unit_id": "1a", "pass": unit_pass, "evidence_frames": ["25%", "50%"]},
                    {"semantic_unit_id": "1b", "pass": True, "evidence_frames": ["75%", "end"]},
                ],
                "proof_checks": {
                    "subject_visible": True,
                    "start_state_visible": True,
                    "visible_action_completed": True,
                    "end_state_visible": True,
                    "causal_link_visible": True,
                    "success_frame_clear": True,
                    "literal_first_pass": True,
                    "static_anchors_stable": True,
                },
            }
        ],
    }


def test_semantic_validator_passes_complete_visible_proof(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    review_path = tmp_path / "review.json"
    write_json(plan_path, valid_plan())
    write_json(review_path, semantic_review(plan_path))
    result = run_script(SEMANTIC_VALIDATOR, str(plan_path), str(review_path))
    assert result.returncode == 0, result.stdout + result.stderr


def test_semantic_validator_rejects_one_failed_unit(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    review_path = tmp_path / "review.json"
    write_json(plan_path, valid_plan())
    write_json(review_path, semantic_review(plan_path, unit_pass=False))
    result = run_script(SEMANTIC_VALIDATOR, str(plan_path), str(review_path))
    assert result.returncode == 1
    assert '"semantic_qc_pass": false' in result.stdout


def test_media_qc_uses_plan_duration_and_five_checkpoints(tmp_path: Path) -> None:
    plan = valid_plan()
    three_second_cut = deepcopy(plan["cuts"][0])
    three_second_cut.update(
        {
            "cut": 1,
            "duration_class": "single_state_or_action",
            "duration_seconds": 3.0,
            "duration_reason": "one visible action",
        }
    )
    five_second_cut = deepcopy(plan["cuts"][0])
    five_second_cut.update({"cut": 2})
    plan["cuts"] = [three_second_cut, five_second_cut]
    plan_path = tmp_path / "plan.json"
    write_json(plan_path, plan)

    video_paths = []
    for cut_number, duration, color in ((1, 3, "red"), (2, 5, "blue")):
        video_path = tmp_path / f"cut-{cut_number:02d}.mp4"
        subprocess.run(
            [
                "ffmpeg",
                "-v",
                "error",
                "-y",
                "-f",
                "lavfi",
                "-i",
                f"color=c={color}:s=90x160:d={duration}:r=24",
                "-an",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(video_path),
            ],
            check=True,
        )
        video_paths.append(video_path)

    output_path = tmp_path / "qc.json"
    result = run_script(
        MEDIA_QC,
        *(str(item) for item in video_paths),
        "--plan",
        str(plan_path),
        "--sample-dir",
        str(tmp_path / "samples"),
        "--contact-sheet",
        str(tmp_path / "contact.jpg"),
        "--output",
        str(output_path),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(output_path.read_text(encoding="utf-8"))
    assert [item["expected_duration"] for item in report["results"]] == [3.0, 5.0]
    assert all(item["sample_checkpoint_count"] == 5 for item in report["results"])
    assert all(item["review_tier"] == "deep" for item in report["results"])
    assert all(item["semantic_review_status"] == "pending_semantic_visual_qc" for item in report["results"])

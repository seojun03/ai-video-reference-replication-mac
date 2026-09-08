#!/usr/bin/env python3
"""Lint a reference-video cut plan before paid generation."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ANATOMY_TERMS = re.compile(
    r"anatom|cutaway|internal organ|intestin|colon|pelvis|groin|torso cavity|"
    r"digestive|open torso|transparent body|장기|장 단면|복부 단면|골반|사타구니|해부",
    re.IGNORECASE,
)
BODY_FRAME_TERMS = re.compile(
    r"torso|body|woman|person|character|pelvis|groin|lower[- ]abdomen|"
    r"인물|여성|신체|복부|골반|사타구니",
    re.IGNORECASE,
)
UNSAFE_ANATOMY_TERMS = re.compile(
    r"open torso|surgical cutaway|exposed pelvis|groin|reproductive|genital|"
    r"torso cavity|transparent body|lower[- ]abdomen cutaway|세로형 복부 단면|"
    r"복부 단면|골반 단면|생식기|사타구니",
    re.IGNORECASE,
)
SAFE_ANATOMY_TERMS = re.compile(
    r"clothed|on clothing|outside (?:the )?frame|no open torso|no surgical cutaway|"
    r"no exposed pelvis|no groin|no reproductive|no genital|no body|no human body|옷을 입|화면 밖",
    re.IGNORECASE,
)

REQUIRED_VIDEO_ROUTE = "Higgsfield Kling v3.0 — start image only"
PRODUCT_TERMS = re.compile(r"\b(?:product|package|sachet|stick|label|logo)\b|제품|패키지|스틱|라벨", re.IGNORECASE)
TEXT_TERMS = re.compile(r"\b(?:claim|price|review|certificate|statistic|cta|offer|ui)\b|문구|가격|리뷰|인증|통계", re.IGNORECASE)
PRODUCT_PRESENCE_VALUES = {"required", "optional", "forbidden"}
IMAGE_QUALITY_VALUES = {"high", "low"}
QUALITY_PROFILES = {"balanced_auto", "precision"}
RESERVE_POLICIES = {"on_demand_after_main_qc", "approved_upfront"}
IMAGE_GENERATION_MODES = {"openai_only"}
IMAGE_CANDIDATE_COUNTS = {1}
PRODUCT_INTEGRATION_FIELDS = ("integration_strategy", "placement_plane", "occlusion_plan", "contact_shadow_plan")
SCENE_NATIVE_STRATEGY = "scene_native_reference_conditioned"
COMPOSITE_STRATEGY = "official_pixel_composite"
PRODUCT_REQUIRED_BEATS = re.compile(
    r"\b(?:product reveal|product use|package handling|sachet|stick|mixing|consumption|"
    r"sold out|repurchase|social proof|offer|stock up|purchase limit|cta)\b|"
    r"제품|패키지|스틱|한 포|챙기|마시|섭취|타(?:도|서|고)|붓|완판|재구매|입소문|쟁여|구매 수량|수량 제한",
    re.IGNORECASE,
)
GENERIC_SUBSTITUTE_TERMS = re.compile(
    r"\b(?:generic|unbranded|blank packet|plain packet|paper packet|tea bag|teabag|lookalike)\b|"
    r"무표기|무브랜드|빈 포|종이 포|티백|대체품",
    re.IGNORECASE,
)
MOTION_DESIGN_FIELDS = (
    "primary_motion",
    "secondary_motion",
    "camera_motion",
    "static_anchors",
    "motion_phases",
)
CLEAN_REFERENCE_FIELDS = (
    "style_reference",
    "expression_reference",
    "composition_reference",
    "native_camera_motion",
    "editing_effects",
)
REQUIRED_CLEAN_REFERENCE_MODE = "clean_visual_reference_only"
VAGUE_MOTION_TERMS = re.compile(
    r"^\s*(?:natural|subtle|gentle)\s+(?:motion|movement)\s*$|"
    r"^\s*camera\s+(?:motion|movement)\s*$|"
    r"^\s*(?:자연스러운|미세한|약한)\s*움직임(?:만)?\s*$|"
    r"^\s*카메라\s*(?:이동|움직임)\s*$",
    re.IGNORECASE,
)
SCENE_DESIGN_FIELDS = ("setting", "subject_action", "shot_scale", "camera_angle")
SEMANTIC_VISUAL_CONTRACT = "literal_visual_proof_v1"
DURATION_POLICY = "adaptive_3_4_5_seconds"
DURATION_CLASS_SECONDS = {
    "single_state_or_action": 3.0,
    "two_step_action": 4.0,
    "causal_transformation": 5.0,
}
SEMANTIC_UNIT_FIELDS = ("id", "text", "required_visual_evidence")
VISUAL_PROOF_FIELDS = (
    "subject",
    "start_state",
    "visible_action",
    "end_state",
    "causal_link",
    "success_frame",
    "forbidden_shortcuts",
)
SEMANTIC_RETRY_FIELDS = (
    "paid_retries",
    "authorized_in_gate_1",
    "max_semantic_retries_total",
    "semantic_retry_budget_credits",
)


def normalized_signature(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().casefold())


def cut_text(cut: dict[str, Any]) -> str:
    fields = [
        cut.get("script", ""),
        cut.get("visual_job", ""),
        cut.get("image_prompt", ""),
        cut.get("motion_prompt", ""),
        cut.get("risk_reason", ""),
        cut.get("safe_template", ""),
        " ".join(str(item) for item in cut.get("hard_exclusions", [])),
        json.dumps(cut.get("semantic_units", []), ensure_ascii=False),
        json.dumps(cut.get("visual_proof", {}), ensure_ascii=False),
    ]
    return "\n".join(str(item) for item in fields)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--strict-schema", action="store_true")
    args = parser.parse_args()

    payload = json.loads(args.plan.read_text())
    cuts = payload.get("cuts", [])
    reserve_cuts = payload.get("reserve_cuts", [])
    plan_blocking: list[str] = []
    plan_warnings: list[str] = []
    findings: list[dict[str, Any]] = []

    schema_version = payload.get("schema_version")
    clean_reference_mode = payload.get("reference_use_mode")
    requires_clean_reference_contract = (
        clean_reference_mode == REQUIRED_CLEAN_REFERENCE_MODE
        or (isinstance(schema_version, int) and schema_version >= 2)
    )
    requires_scene_diversity_contract = isinstance(schema_version, int) and schema_version >= 3
    requires_semantic_visual_contract = isinstance(schema_version, int) and schema_version >= 4

    if args.strict_schema:
        if not requires_semantic_visual_contract:
            plan_blocking.append(
                "new or materially remapped plans must use schema_version 4; inspect legacy plans without --strict-schema"
            )
        if requires_clean_reference_contract and clean_reference_mode != REQUIRED_CLEAN_REFERENCE_MODE:
            plan_blocking.append(
                "reference_use_mode must be clean_visual_reference_only"
            )
        elif not requires_clean_reference_contract:
            plan_warnings.append(
                "legacy plan: add schema_version 2 and reference_use_mode=clean_visual_reference_only"
            )
        if payload.get("quality_profile") not in (None, *QUALITY_PROFILES):
            plan_blocking.append("quality_profile must be balanced_auto or precision")
        elif requires_clean_reference_contract and payload.get("quality_profile") is None:
            plan_warnings.append("add quality_profile: balanced_auto or precision")
        if payload.get("reserve_policy") not in (None, *RESERVE_POLICIES):
            plan_blocking.append("reserve_policy must be on_demand_after_main_qc or approved_upfront")
        elif requires_clean_reference_contract and payload.get("reserve_policy") is None:
            plan_warnings.append("add reserve_policy: on_demand_after_main_qc or approved_upfront")
        if reserve_cuts and not isinstance(reserve_cuts, list):
            plan_blocking.append("reserve_cuts must be an array when present")
        image_generation_mode = payload.get("image_generation_mode")
        if image_generation_mode not in (None, *IMAGE_GENERATION_MODES):
            plan_blocking.append(
                "image_generation_mode must be openai_only; Higgsfield still-image generation is forbidden"
            )
        elif requires_clean_reference_contract and image_generation_mode is None:
            plan_warnings.append(
                "add image_generation_mode: openai_only"
            )
        image_candidates_per_cut = payload.get("image_candidates_per_cut")
        if image_candidates_per_cut is not None and image_candidates_per_cut not in IMAGE_CANDIDATE_COUNTS:
            plan_blocking.append("image_candidates_per_cut must be 1 for GPT-only first attempts")
        if requires_clean_reference_contract and image_generation_mode == "openai_only" and image_candidates_per_cut != 1:
            plan_blocking.append("openai_only requires image_candidates_per_cut=1")
        image_generation_route = payload.get("image_generation_route")
        if requires_clean_reference_contract and image_generation_route != "built_in_image_gen":
            plan_blocking.append("image_generation_route must be built_in_image_gen")
        higgsfield_image_jobs = payload.get("higgsfield_image_jobs")
        if requires_clean_reference_contract and higgsfield_image_jobs != 0:
            plan_blocking.append("higgsfield_image_jobs must be 0")
        image_api_jobs = payload.get("image_api_jobs")
        if requires_clean_reference_contract and image_api_jobs != 0:
            plan_blocking.append("image_api_jobs must be 0")
        image_cli_jobs = payload.get("image_cli_jobs")
        if requires_clean_reference_contract and image_cli_jobs != 0:
            plan_blocking.append("image_cli_jobs must be 0")
        image_lanes = payload.get("image_lanes")
        if isinstance(image_lanes, dict):
            higgsfield_lane = image_lanes.get("higgsfield")
            if isinstance(higgsfield_lane, dict) and any(
                (
                    higgsfield_lane.get("enabled") is True,
                    isinstance(higgsfield_lane.get("requests"), (int, float))
                    and not isinstance(higgsfield_lane.get("requests"), bool)
                    and higgsfield_lane.get("requests", 0) > 0,
                    bool(higgsfield_lane.get("model")),
                )
            ):
                plan_blocking.append("image_lanes.higgsfield must remain disabled with zero requests and no model")
            openai_lane = image_lanes.get("openai")
            if isinstance(openai_lane, dict) and openai_lane.get("route") not in (None, "built_in_image_gen"):
                plan_blocking.append("image_lanes.openai.route must be built_in_image_gen")
        if requires_scene_diversity_contract and payload.get("selected_start_reuse_policy") != "forbid_across_cuts":
            plan_blocking.append("schema_version 3+ requires selected_start_reuse_policy=forbid_across_cuts")
        if requires_semantic_visual_contract:
            if payload.get("semantic_visual_contract") != SEMANTIC_VISUAL_CONTRACT:
                plan_blocking.append(
                    f"schema_version 4 requires semantic_visual_contract={SEMANTIC_VISUAL_CONTRACT}"
                )
            if payload.get("duration_policy") != DURATION_POLICY:
                plan_blocking.append(
                    f"schema_version 4 requires duration_policy={DURATION_POLICY}"
                )
            retry_policy = payload.get("semantic_retry_policy")
            if not isinstance(retry_policy, dict):
                plan_blocking.append("schema_version 4 requires semantic_retry_policy object")
            else:
                for field in SEMANTIC_RETRY_FIELDS:
                    if field not in retry_policy:
                        plan_blocking.append(f"semantic_retry_policy is missing required field: {field}")
                paid_retries = retry_policy.get("paid_retries")
                authorized = retry_policy.get("authorized_in_gate_1")
                retry_count = retry_policy.get("max_semantic_retries_total")
                retry_budget = retry_policy.get("semantic_retry_budget_credits")
                if not isinstance(paid_retries, bool):
                    plan_blocking.append("semantic_retry_policy.paid_retries must be boolean")
                if not isinstance(authorized, bool):
                    plan_blocking.append("semantic_retry_policy.authorized_in_gate_1 must be boolean")
                if isinstance(retry_count, bool) or not isinstance(retry_count, int) or retry_count < 0:
                    plan_blocking.append("semantic_retry_policy.max_semantic_retries_total must be a non-negative integer")
                if isinstance(retry_budget, bool) or not isinstance(retry_budget, (int, float)) or retry_budget < 0:
                    plan_blocking.append("semantic_retry_policy.semantic_retry_budget_credits must be a non-negative number")
                if paid_retries is True and not (
                    authorized is True
                    and isinstance(retry_count, int)
                    and not isinstance(retry_count, bool)
                    and retry_count > 0
                    and isinstance(retry_budget, (int, float))
                    and not isinstance(retry_budget, bool)
                    and retry_budget > 0
                ):
                    plan_blocking.append(
                        "paid semantic retries require explicit Gate 1 authorization, a positive retry count, and a positive credit budget"
                    )
                if paid_retries is False and any(
                    value not in (False, 0, 0.0)
                    for value in (authorized, retry_count, retry_budget)
                ):
                    plan_blocking.append(
                        "when paid_retries=false, Gate 1 authorization, retry count, and retry budget must remain zero/false"
                    )

    planned_jobs = [(cut, "main") for cut in cuts]
    if isinstance(reserve_cuts, list):
        planned_jobs.extend((cut, "reserve") for cut in reserve_cuts)

    seen_scene_signatures: dict[str, Any] = {}
    seen_image_prompts: dict[str, Any] = {}

    for cut, job_role in planned_jobs:
        number = cut.get("cut")
        blocking: list[str] = []
        warnings: list[str] = []
        for required in ("cut", "script", "image_prompt", "route"):
            if not cut.get(required):
                blocking.append(f"missing required field: {required}")

        text = cut_text(cut)
        semantic_text = "\n".join(str(cut.get(field, "")) for field in ("script", "visual_job", "risk_reason", "safe_template"))
        substitute_design_text = "\n".join(
            str(cut.get(field, ""))
            for field in ("visual_job", "composition", "must_show", "safe_template")
        )
        route = str(cut.get("route", ""))
        route_lower = route.lower()
        anatomy = bool(ANATOMY_TERMS.search(text))
        body_frame = bool(BODY_FRAME_TERMS.search(text))
        unsafe_anatomy = bool(UNSAFE_ANATOMY_TERMS.search(text))
        safe_anatomy = bool(SAFE_ANATOMY_TERMS.search(text))

        if "local" in route_lower or "로컬" in route:
            blocking.append("local-only video route is forbidden; every cut requires a Higgsfield Kling v3.0 motion base")
        if route.strip() != REQUIRED_VIDEO_ROUTE:
            blocking.append(f"route must be exactly {REQUIRED_VIDEO_ROUTE}")
        if unsafe_anatomy and not safe_anatomy:
            blocking.append("prompt contains unsafe anatomy geometry")
        if anatomy and body_frame and not safe_anatomy:
            blocking.append("anatomy cut lacks clothed/cropped/no-open-body safety language")

        risk = cut.get("risk_level")
        product_presence = cut.get("product_presence")
        image_quality = cut.get("image_quality")
        integration_strategy = cut.get("integration_strategy")
        motion_design = cut.get("motion_design")
        scene_design = cut.get("scene_design")
        if args.strict_schema and requires_clean_reference_contract:
            for field in CLEAN_REFERENCE_FIELDS:
                value = cut.get(field)
                if value is None or value == "":
                    blocking.append(f"missing clean-reference field: {field}")
            if cut.get("editing_effects") != "forbidden":
                blocking.append("editing_effects must equal the literal value forbidden")
        if anatomy and body_frame and risk != "high":
            warnings.append("body-framed anatomy cut should use risk_level=high")
        if args.strict_schema and not risk:
            warnings.append("legacy plan: add risk_level")
        if image_quality is not None and image_quality not in IMAGE_QUALITY_VALUES:
            blocking.append("image_quality must be high or low")
        if args.strict_schema and image_quality is None:
            warnings.append("add image_quality: high for product/high-risk, low for low/medium product-independent cuts")
        if image_quality == "low" and (risk == "high" or product_presence == "required"):
            blocking.append("high-risk or required-product cut cannot use image_quality=low")
        if args.strict_schema and not cut.get("must_show"):
            if requires_semantic_visual_contract:
                blocking.append("schema_version 4 cut is missing must_show")
            else:
                warnings.append("legacy plan: add must_show")
        if requires_semantic_visual_contract:
            semantic_units = cut.get("semantic_units")
            if not isinstance(semantic_units, list) or not semantic_units:
                blocking.append("schema_version 4 cut requires a non-empty semantic_units array")
            else:
                seen_unit_ids: set[str] = set()
                for unit_index, unit in enumerate(semantic_units, start=1):
                    if not isinstance(unit, dict):
                        blocking.append(f"semantic_units[{unit_index}] must be an object")
                        continue
                    for field in SEMANTIC_UNIT_FIELDS:
                        value = unit.get(field)
                        if value is None or value == "" or value == []:
                            blocking.append(f"semantic_units[{unit_index}] is missing required field: {field}")
                    unit_id = normalized_signature(unit.get("id", ""))
                    if unit_id:
                        if unit_id in seen_unit_ids:
                            blocking.append(f"duplicate semantic unit id: {unit.get('id')}")
                        seen_unit_ids.add(unit_id)
                    evidence = unit.get("required_visual_evidence")
                    if evidence is not None and not isinstance(evidence, (str, list)):
                        blocking.append(
                            f"semantic_units[{unit_index}].required_visual_evidence must be text or a non-empty array"
                        )
                    if isinstance(evidence, list) and not evidence:
                        blocking.append(
                            f"semantic_units[{unit_index}].required_visual_evidence must not be empty"
                        )

            visual_proof = cut.get("visual_proof")
            if not isinstance(visual_proof, dict):
                blocking.append("schema_version 4 cut requires visual_proof object")
            else:
                for field in VISUAL_PROOF_FIELDS:
                    value = visual_proof.get(field)
                    if value is None or value == "" or value == []:
                        blocking.append(f"visual_proof is missing required field: {field}")
                shortcuts = visual_proof.get("forbidden_shortcuts")
                if shortcuts is not None and not isinstance(shortcuts, list):
                    blocking.append("visual_proof.forbidden_shortcuts must be a non-empty array")

            duration_class = cut.get("duration_class")
            duration_seconds = cut.get("duration_seconds")
            duration_reason = cut.get("duration_reason")
            if duration_class not in DURATION_CLASS_SECONDS:
                blocking.append(
                    "duration_class must be single_state_or_action, two_step_action, or causal_transformation"
                )
            else:
                expected_seconds = DURATION_CLASS_SECONDS[duration_class]
                if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, (int, float)):
                    blocking.append("duration_seconds must be numeric")
                elif abs(float(duration_seconds) - expected_seconds) > 0.001:
                    blocking.append(
                        f"duration_class={duration_class} requires duration_seconds={expected_seconds:.1f}"
                    )
            if not isinstance(duration_reason, str) or not duration_reason.strip():
                blocking.append("schema_version 4 cut requires a non-empty duration_reason")
        if motion_design is None:
            if args.strict_schema:
                blocking.append("new or materially remapped cut is missing motion_design")
            else:
                warnings.append("legacy plan: add motion_design before materially remapping")
        elif not isinstance(motion_design, dict):
            blocking.append("motion_design must be an object")
        else:
            for field in MOTION_DESIGN_FIELDS:
                value = motion_design.get(field)
                if value is None or value == "" or value == []:
                    blocking.append(f"motion_design is missing required field: {field}")
                    continue
                if field != "static_anchors" and VAGUE_MOTION_TERMS.search(str(value)):
                    blocking.append(f"motion_design.{field} is too vague; name a visible subject and action")
            anchors = motion_design.get("static_anchors")
            if anchors is not None and not isinstance(anchors, list):
                blocking.append("motion_design.static_anchors must be a list")
            if requires_semantic_visual_contract and isinstance(cut.get("duration_seconds"), (int, float)):
                phase_numbers = [
                    float(item)
                    for item in re.findall(r"\d+(?:\.\d+)?", str(motion_design.get("motion_phases", "")))
                ]
                if not phase_numbers:
                    blocking.append("motion_design.motion_phases must contain timed phases")
                elif abs(max(phase_numbers) - float(cut["duration_seconds"])) > 0.11:
                    blocking.append("motion_design.motion_phases must end at duration_seconds")
        if requires_scene_diversity_contract:
            if not isinstance(scene_design, dict):
                blocking.append("schema_version 3+ cut is missing scene_design object")
            else:
                missing_scene_fields = [field for field in SCENE_DESIGN_FIELDS if not scene_design.get(field)]
                for field in missing_scene_fields:
                    blocking.append(f"scene_design is missing required field: {field}")
                if not missing_scene_fields and job_role == "main":
                    signature = "|".join(normalized_signature(scene_design[field]) for field in SCENE_DESIGN_FIELDS)
                    if signature in seen_scene_signatures:
                        blocking.append(f"scene_design duplicates main cut {seen_scene_signatures[signature]}")
                    else:
                        seen_scene_signatures[signature] = number
            if job_role == "main":
                prompt_signature = normalized_signature(cut.get("image_prompt", ""))
                if prompt_signature:
                    if prompt_signature in seen_image_prompts:
                        blocking.append(f"image_prompt duplicates main cut {seen_image_prompts[prompt_signature]}")
                    else:
                        seen_image_prompts[prompt_signature] = number
        if product_presence is not None and product_presence not in PRODUCT_PRESENCE_VALUES:
            blocking.append("product_presence must be required, optional, or forbidden")
        if args.strict_schema and product_presence is None:
            warnings.append("legacy plan: add product_presence")
        if product_presence == "required":
            for field in ("integration_strategy", "product_asset_id", "product_source", "product_identity_lock"):
                if not cut.get(field):
                    blocking.append(f"required product cut is missing exact-product field: {field}")
            if integration_strategy not in {SCENE_NATIVE_STRATEGY, COMPOSITE_STRATEGY}:
                blocking.append("required product cut must use scene_native_reference_conditioned or official_pixel_composite")
            if integration_strategy == COMPOSITE_STRATEGY:
                for field in PRODUCT_INTEGRATION_FIELDS[1:]:
                    if not cut.get(field):
                        blocking.append(f"official-pixel composite cut is missing integration field: {field}")
                if not cut.get("deterministic_post"):
                    blocking.append("official-pixel composite cut needs explicit deterministic scene-integration post steps")
            if GENERIC_SUBSTITUTE_TERMS.search(substitute_design_text):
                blocking.append("required product cut contains a generic or unbranded substitute")
        if product_presence == "forbidden":
            post_text = "\n".join(str(item) for item in cut.get("deterministic_post", []))
            if PRODUCT_TERMS.search(post_text):
                blocking.append("product_presence=forbidden conflicts with product restoration in deterministic_post")
            if PRODUCT_REQUIRED_BEATS.search(semantic_text):
                blocking.append("product reveal/use/proof/social-proof/CTA beat cannot use product_presence=forbidden")
        exclusions = cut.get("hard_exclusions")
        if exclusions is None:
            if args.strict_schema:
                warnings.append("legacy plan: add hard_exclusions")
        elif len(exclusions) > 3:
            warnings.append("hard_exclusions should contain at most three cut-specific items")
        if PRODUCT_TERMS.search(semantic_text) and product_presence == "required" and integration_strategy == COMPOSITE_STRATEGY and not cut.get("deterministic_post"):
            warnings.append("official-pixel composite needs deterministic product restoration/tracking")
        if TEXT_TERMS.search(semantic_text) and not cut.get("deterministic_post"):
            blocking.append("claim/evidence/CTA needs a Higgsfield motion plate plus deterministic verified post layers")

        finding = {"cut": number, "blocking": blocking, "warnings": warnings}
        if job_role != "main":
            finding["job_role"] = job_role
        findings.append(finding)

    if plan_blocking or plan_warnings:
        findings.insert(
            0,
            {
                "cut": "plan",
                "blocking": plan_blocking,
                "warnings": plan_warnings,
            },
        )

    result = {
        "plan": str(args.plan),
        "cut_count": len(cuts),
        "reserve_cut_count": len(reserve_cuts) if isinstance(reserve_cuts, list) else 0,
        "plan_blocking": plan_blocking,
        "plan_warnings": plan_warnings,
        "blocking_count": sum(len(item["blocking"]) for item in findings),
        "warning_count": sum(len(item["warnings"]) for item in findings),
        "findings": [item for item in findings if item["blocking"] or item["warnings"]],
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(rendered + "\n")
    print(json.dumps({key: result[key] for key in ("cut_count", "blocking_count", "warning_count")}, ensure_ascii=False))
    for item in result["findings"]:
        if item["blocking"]:
            print(json.dumps(item, ensure_ascii=False))
    raise SystemExit(1 if result["blocking_count"] else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Fail closed unless every schema-v4 script unit has visible proof."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


REQUIRED_PROOF_CHECKS = (
    "subject_visible",
    "start_state_visible",
    "visible_action_completed",
    "end_state_visible",
    "causal_link_visible",
    "success_frame_clear",
    "literal_first_pass",
    "static_anchors_stable",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cut_key(value: Any) -> str:
    return str(value).strip().casefold()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("plan", type=Path)
    parser.add_argument("review", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    review = json.loads(args.review.read_text(encoding="utf-8"))
    failures: list[str] = []

    if plan.get("schema_version") != 4:
        failures.append("plan_schema_version_must_equal_4")
    if plan.get("semantic_visual_contract") != "literal_visual_proof_v1":
        failures.append("plan_semantic_visual_contract_mismatch")
    if review.get("schema") != "semantic-visual-qc" or review.get("schema_version") != 1:
        failures.append("review_schema_mismatch")
    if review.get("plan_sha256") != sha256(args.plan):
        failures.append("plan_sha256_mismatch")

    planned_cuts = {
        cut_key(cut.get("cut")): cut
        for cut in plan.get("cuts", [])
        if cut.get("cut") not in (None, "")
    }
    review_items = review.get("cuts")
    if not isinstance(review_items, list):
        review_items = []
        failures.append("review_cuts_must_be_array")

    reviewed_cuts: dict[str, dict[str, Any]] = {}
    for item in review_items:
        if not isinstance(item, dict):
            failures.append("review_cut_must_be_object")
            continue
        key = cut_key(item.get("cut"))
        if not key:
            failures.append("review_cut_id_missing")
            continue
        if key in reviewed_cuts:
            failures.append(f"cut_{key}:duplicate_review")
            continue
        reviewed_cuts[key] = item

    for key in sorted(set(reviewed_cuts) - set(planned_cuts)):
        failures.append(f"cut_{key}:not_in_plan")

    for key, planned in planned_cuts.items():
        item = reviewed_cuts.get(key)
        if item is None:
            failures.append(f"cut_{key}:missing_review")
            continue
        checkpoint_count = item.get("sample_checkpoint_count")
        if isinstance(checkpoint_count, bool) or not isinstance(checkpoint_count, int) or checkpoint_count < 5:
            failures.append(f"cut_{key}:requires_at_least_5_checkpoints")
        planned_duration = planned.get("duration_seconds")
        reviewed_duration = item.get("duration_seconds")
        if not isinstance(reviewed_duration, (int, float)) or isinstance(reviewed_duration, bool):
            failures.append(f"cut_{key}:duration_seconds_missing")
        elif not isinstance(planned_duration, (int, float)) or abs(float(reviewed_duration) - float(planned_duration)) > 0.001:
            failures.append(f"cut_{key}:duration_seconds_mismatch")

        checks = item.get("proof_checks")
        if not isinstance(checks, dict):
            checks = {}
            failures.append(f"cut_{key}:proof_checks_missing")
        for field in REQUIRED_PROOF_CHECKS:
            if checks.get(field) is not True:
                failures.append(f"cut_{key}:{field}_not_passed")

        unit_results = item.get("unit_results")
        if not isinstance(unit_results, list):
            unit_results = []
            failures.append(f"cut_{key}:unit_results_missing")
        result_by_id: dict[str, dict[str, Any]] = {}
        for unit_result in unit_results:
            if not isinstance(unit_result, dict):
                failures.append(f"cut_{key}:unit_result_must_be_object")
                continue
            unit_id = cut_key(unit_result.get("semantic_unit_id"))
            if not unit_id:
                failures.append(f"cut_{key}:semantic_unit_id_missing")
                continue
            if unit_id in result_by_id:
                failures.append(f"cut_{key}:duplicate_semantic_unit_{unit_id}")
                continue
            result_by_id[unit_id] = unit_result

        planned_unit_ids = {
            cut_key(unit.get("id"))
            for unit in planned.get("semantic_units", [])
            if isinstance(unit, dict) and unit.get("id") not in (None, "")
        }
        for extra in sorted(set(result_by_id) - planned_unit_ids):
            failures.append(f"cut_{key}:unknown_semantic_unit_{extra}")
        for unit_id in sorted(planned_unit_ids):
            unit_result = result_by_id.get(unit_id)
            if unit_result is None:
                failures.append(f"cut_{key}:missing_semantic_unit_{unit_id}")
                continue
            if unit_result.get("pass") is not True:
                failures.append(f"cut_{key}:semantic_unit_{unit_id}_not_passed")
            evidence_frames = unit_result.get("evidence_frames")
            if not isinstance(evidence_frames, list) or not evidence_frames:
                failures.append(f"cut_{key}:semantic_unit_{unit_id}_evidence_missing")

    result = {
        "schema": "semantic-visual-qc-validation",
        "schema_version": 1,
        "plan": str(args.plan),
        "review": str(args.review),
        "planned_cut_count": len(planned_cuts),
        "reviewed_cut_count": len(reviewed_cuts),
        "failure_count": len(failures),
        "failures": failures,
        "semantic_qc_pass": not failures,
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps({"semantic_qc_pass": result["semantic_qc_pass"], "failure_count": len(failures)}, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

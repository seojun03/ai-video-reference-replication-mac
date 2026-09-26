#!/usr/bin/env python3
"""Per-cut readiness and duplicate-safe claims. Provider calls stay in the agent tools."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from check_selected_start_diversity import dhash, sha256
from submission_ledger import locked as locked_ledger

ACTIVE = {"claimed", "submitted", "submitted_unknown"}
MODEL = "kling3_0"


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def write(path, data):
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp, path)


@contextmanager
def state_lock(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_name(path.name + ".lock").open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            data = json.loads(path.read_text()) if path.exists() else None
            yield data
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def initialize(path, plan_path, ledger, video_concurrency=3):
    plan = json.loads(plan_path.read_text())
    if plan.get("video_source_mode") == "existing_clean_edit" or plan.get("image_generation_route") != "built_in_image_gen":
        raise ValueError("streaming is only for approved built-in image_gen -> Kling generation")
    if not 1 <= video_concurrency <= 6:
        raise ValueError("video_concurrency must be 1..6; use the lower current provider limit")
    cuts = {}
    signatures = set()
    for cut in plan["cuts"]:
        key = str(cut["cut"])
        signature = tuple(str(cut["scene_design"][part]).strip().casefold() for part in ("setting", "subject_action", "shot_scale", "camera_angle"))
        if key in cuts or signature in signatures or not all(signature):
            raise ValueError("duplicate cut or scene design")
        signatures.add(signature)
        if cut["duration_seconds"] not in (3, 4, 5):
            raise ValueError("invalid planned duration")
        cuts[key] = {"cut": cut["cut"], "scene_signature": signature, "image": None, "video": None,
                     "video_depends_on": [str(x) for x in cut.get("video_depends_on", [])]}
    for key, cut in cuts.items():
        if key in cut["video_depends_on"] or set(cut["video_depends_on"]) - cuts.keys():
            raise ValueError("invalid video dependency")
    def visit(key, visiting, visited):
        if key in visiting:
            raise ValueError("cyclic video dependencies")
        if key not in visited:
            for parent in cuts[key]["video_depends_on"]:
                visit(parent, visiting | {key}, visited)
            visited.add(key)
    visited = set()
    for key in cuts:
        visit(key, set(), visited)
    data = {"schema": "per-cut-streaming/v1", "plan_path": str(plan_path.resolve()),
            "plan_sha256": sha256(plan_path), "ledger": str(ledger.resolve()),
            "video_concurrency": video_concurrency, "cuts": cuts, "created_at": now()}
    with state_lock(path) as existing:
        if existing:
            if existing["plan_sha256"] != data["plan_sha256"]:
                raise ValueError("plan changed; existing run is immutable")
            return existing
        write(path, data)
    return data


def bound_plan(data):
    if data is None or data.get("schema") != "per-cut-streaming/v1":
        raise ValueError("initialize streaming state first")
    path = Path(data["plan_path"])
    if sha256(path) != data["plan_sha256"]:
        raise ValueError("plan hash changed")
    return json.loads(path.read_text())


def accept_start(path, cut_id, image, review):
    image = image.resolve()
    image_hash = sha256(image)
    with state_lock(path) as data:
        plan = bound_plan(data)
        key = str(cut_id)
        cut = data["cuts"][key]
        if cut["image"]:
            if cut["image"]["sha256"] == image_hash:
                return {"status": "already_selected", "cut": cut_id}
            raise ValueError("selected start is immutable; replacement needs a separately authorized attempt")
        required = ["composition_pass", "action_ready", "scene_variety_pass"]
        spec = next(item for item in plan["cuts"] if str(item["cut"]) == key)
        if spec.get("product_presence") == "required":
            required.append("product_identity_pass")
        if any(review.get(flag) is not True for flag in required):
            raise ValueError("start-image visual QC incomplete")
        if review.get("image_sha256") != image_hash or review.get("provider") != "openai" or review.get("route") != "built_in_image_gen" or not review.get("tool_result_path"):
            raise ValueError("missing or mismatched built-in image provenance")
        selected = {k: row["image"] for k, row in data["cuts"].items() if row["image"]}
        if {str(x) for x in review.get("compared_with_selected_cut_ids", [])} != set(selected):
            raise ValueError("review must include every already selected start; refresh the rolling contact sheet")
        perceptual = dhash(image)
        for prior in selected.values():
            if sha256(Path(prior["path"])) != prior["sha256"]:
                raise ValueError("previously selected file changed")
            if image_hash == prior["sha256"] or (perceptual ^ int(prior["dhash"], 16)).bit_count() <= 4:
                raise ValueError("duplicate or near-duplicate selected start")
        cut["image"] = {"path": str(image), "sha256": image_hash, "dhash": f"{perceptual:016x}",
                        "review": review, "selected_at": now()}
        write(path, data)
    return {"status": "image_ready", "cut": cut_id, "all_images_required": False}


def ready(data):
    bound_plan(data)
    active = sum(bool(row["video"] and row["video"]["state"] in ACTIVE) for row in data["cuts"].values())
    slots = max(0, data["video_concurrency"] - active)
    result = []
    for key, row in data["cuts"].items():
        if not row["image"] or row["video"]:
            continue
        if all((data["cuts"][dep]["video"] or {}).get("qc_pass") is True for dep in row["video_depends_on"]):
            if sha256(Path(row["image"]["path"])) != row["image"]["sha256"]:
                raise ValueError("selected start changed after review")
            result.append(key)
    return {"ready_cut_ids": result[:slots], "active_videos": active, "available_slots": slots,
            "all_images_required": False}


def claim_video(path, cut_id):
    with state_lock(path) as data:
        plan = bound_plan(data)
        key = str(cut_id)
        cut = data["cuts"][key]
        if cut["video"]:
            return {"status": "existing", "video": cut["video"]}
        if key not in ready(data)["ready_cut_ids"]:
            raise ValueError("cut is not ready or video capacity is full")
        spec = next(item for item in plan["cuts"] if str(item["cut"]) == key)
        mode = spec.get("cost", {}).get("mode", "pro") if isinstance(spec.get("cost"), dict) else "pro"
        ratio = plan.get("output_ratio")
        if ratio not in {"1:1", "9:16", "16:9"} or mode not in {"std", "pro", "4k"}:
            raise ValueError("missing/unsupported ratio or mode")
        fields = {"plan_hash": data["plan_sha256"], "cut": key, "stage": "video", "attempt": 1,
                  "start_image_hash": cut["image"]["sha256"], "model": MODEL, "mode": mode,
                  "ratio": ratio, "duration": spec["duration_seconds"], "sound": "off"}
        submission_key = hashlib.sha256(encoded(fields)).hexdigest()
        with locked_ledger(Path(data["ledger"])) as ledger:
            prior = ledger["entries"].get(submission_key)
            if prior:
                cut["video"] = {"submission_key": submission_key, "state": prior["state"],
                                "job_id": prior.get("provider_job_id"), "qc_pass": False}
                write(path, data)
                return {"status": "existing", "video": cut["video"]}
            ledger["entries"][submission_key] = {**fields, "submission_key": submission_key,
                                                 "state": "claimed", "claimed_at": now()}
        cut["video"] = {"submission_key": submission_key, "state": "claimed", "job_id": None, "qc_pass": False}
        write(path, data)
        return {"status": "claimed", "submission_key": submission_key,
                "start_image_path": cut["image"]["path"],
                "params": {"model": MODEL, "aspect_ratio": ratio, "mode": mode, "duration": spec["duration_seconds"],
                           "sound": "off", "count": 1, "prompt": spec["motion_prompt"]}}


def record_video(path, cut_id, status, job_id=None, model=None, qc_pass=False):
    if status not in {"submitted", "submitted_unknown", "completed", "quarantined"}:
        raise ValueError("unsupported video status")
    if status in {"submitted", "completed"} and (not job_id or model != MODEL):
        raise ValueError("job ID and returned kling3_0 model are required")
    if qc_pass and status != "completed":
        raise ValueError("QC cannot pass an incomplete video")
    with state_lock(path) as data:
        bound_plan(data)
        video = data["cuts"][str(cut_id)]["video"]
        if not video:
            raise ValueError("claim the video before recording it")
        if video["state"] in {"completed", "quarantined"} and status != video["state"]:
            raise ValueError("terminal video cannot be resubmitted")
        if video.get("job_id") and job_id and video["job_id"] != job_id:
            raise ValueError("job ID changed")
        with locked_ledger(Path(data["ledger"])) as ledger:
            entry = ledger["entries"][video["submission_key"]]
            entry.update({"state": status, "updated_at": now()})
            if job_id:
                entry["provider_job_id"] = job_id
            if model:
                entry["returned_model"] = model
        video.update({"state": status, "job_id": job_id or video.get("job_id"), "qc_pass": qc_pass,
                      "updated_at": now(), status + "_at": now()})
        write(path, data)
    return {"status": status, "cut": cut_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.add_argument("--plan", type=Path, required=True)
    init.add_argument("--ledger", type=Path, required=True)
    init.add_argument("--video-concurrency", type=int, default=3)
    accept = sub.add_parser("accept-start")
    accept.add_argument("--cut", required=True)
    accept.add_argument("--image", type=Path, required=True)
    accept.add_argument("--review", type=Path, required=True)
    sub.add_parser("ready")
    claim = sub.add_parser("claim-video")
    claim.add_argument("--cut", required=True)
    record = sub.add_parser("record-video")
    record.add_argument("--cut", required=True)
    record.add_argument("--status", required=True)
    record.add_argument("--job-id")
    record.add_argument("--model")
    record.add_argument("--qc-pass", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "init":
            data = initialize(args.state, args.plan, args.ledger, args.video_concurrency)
            result = {"status": "initialized", "main_cut_count": len(data["cuts"])}
        elif args.command == "accept-start":
            result = accept_start(args.state, args.cut, args.image, json.loads(args.review.read_text()))
        elif args.command == "ready":
            result = ready(json.loads(args.state.read_text()))
        elif args.command == "claim-video":
            result = claim_video(args.state, args.cut)
        else:
            result = record_video(args.state, args.cut, args.status, args.job_id, args.model, args.qc_pass)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

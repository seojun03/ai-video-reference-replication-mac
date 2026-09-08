#!/usr/bin/env python3
"""Run objective media QC and build compact sampled-frame contact sheets."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageStat


def run_json(command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(command, text=True, capture_output=True, check=True)
    return json.loads(completed.stdout)


def border_flags(image: Image.Image) -> list[str]:
    gray = image.convert("L")
    width, height = gray.size
    band_x = max(2, round(width * 0.02))
    band_y = max(2, round(height * 0.02))
    regions = {
        "left": (0, 0, band_x, height),
        "right": (width - band_x, 0, width, height),
        "top": (0, 0, width, band_y),
        "bottom": (0, height - band_y, width, height),
    }
    flags = []
    for name, box in regions.items():
        stats = ImageStat.Stat(gray.crop(box))
        if stats.mean[0] < 12 and stats.stddev[0] < 6:
            flags.append(name)
    return flags


def probe_video(path: Path) -> dict[str, Any]:
    return run_json([
        "ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ])


def extract_samples(path: Path, duration: float, sample_dir: Path, checkpoint_count: int = 3) -> list[Path]:
    sample_dir.mkdir(parents=True, exist_ok=True)
    if checkpoint_count >= 5:
        times = [
            min(0.15, duration / 10),
            duration * 0.25,
            duration * 0.5,
            duration * 0.75,
            max(0.0, duration - 0.15),
        ]
    else:
        times = [min(0.2, duration / 4), duration / 2, max(0.0, duration - 0.2)]
    outputs: list[Path] = []
    for index, timestamp in enumerate(times, start=1):
        destination = sample_dir / f"{path.stem}-{index}.jpg"
        subprocess.run([
            "ffmpeg", "-v", "error", "-y", "-ss", f"{timestamp:.3f}", "-i", str(path),
            "-frames:v", "1", "-q:v", "3", str(destination)
        ], check=True)
        outputs.append(destination)
    return outputs


def expected_ratio_value(spec: str) -> float:
    left, right = (float(item) for item in spec.split(":", 1))
    return left / right


def make_contact_sheet(rows: list[tuple[str, list[Path]]], destination: Path) -> None:
    if not rows:
        return
    thumb_w, thumb_h, label_h = 224, 400, 24
    column_count = max(1, min(5, max(len(images) for _, images in rows)))
    canvas = Image.new("RGB", (thumb_w * column_count, (thumb_h + label_h) * len(rows)), "white")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for row_index, (label, images) in enumerate(rows):
        top = row_index * (thumb_h + label_h)
        draw.rectangle((0, top, canvas.width, top + label_h), fill="black")
        draw.text((6, top + 6), label, fill="white", font=font)
        for column, path in enumerate(images[:column_count]):
            with Image.open(path) as source:
                fitted = source.convert("RGB")
                fitted.thumbnail((thumb_w, thumb_h))
                x = column * thumb_w + (thumb_w - fitted.width) // 2
                y = top + label_h + (thumb_h - fitted.height) // 2
                canvas.paste(fitted, (x, y))
    destination.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination, quality=88)


def find_job_record(record_dir: Path | None, stem: str) -> Path | None:
    if not record_dir:
        return None
    candidates = [record_dir / f"{stem}-video-job.json", record_dir / f"{stem}-image-job.json"]
    return next((item for item in candidates if item.exists()), None)


def load_cut_metadata(plan_path: Path | None) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    if not plan_path:
        return {}, {}
    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    metadata: dict[str, dict[str, Any]] = {}
    plan_metadata = {
        "schema_version": payload.get("schema_version"),
        "semantic_visual_contract": payload.get("semantic_visual_contract"),
        "duration_policy": payload.get("duration_policy"),
    }
    for cut in payload.get("cuts", []):
        number = cut.get("cut")
        if number in (None, ""):
            continue
        try:
            numeric = int(number)
        except (TypeError, ValueError):
            continue
        record = {
            "risk_level": cut.get("risk_level"),
            "product_presence": cut.get("product_presence"),
            "duration_seconds": cut.get("duration_seconds"),
            "duration_class": cut.get("duration_class"),
            "semantic_units": cut.get("semantic_units"),
            "visual_proof": cut.get("visual_proof"),
            **plan_metadata,
        }
        for key in (f"cut-{numeric}", f"cut-{numeric:02d}"):
            metadata[key.lower()] = record
    return metadata, plan_metadata


def is_semantic_proof_cut(cut: dict[str, Any]) -> bool:
    return (
        cut.get("schema_version") == 4
        and cut.get("semantic_visual_contract") == "literal_visual_proof_v1"
    )


def review_tier(profile: str, cut: dict[str, Any], warnings: list[str]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if is_semantic_proof_cut(cut):
        reasons.append("schema4_semantic_visual_proof")
    if profile == "precision":
        reasons.append("precision_profile")
    if cut.get("risk_level") == "high":
        reasons.append("high_risk")
    if cut.get("product_presence") == "required":
        reasons.append("product_visible")
    if warnings:
        reasons.append("technical_warning")
    if reasons:
        return "deep", reasons
    return "contact_sheet", ["low_or_medium_risk_without_warning"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--expected-ratio", default="9:16")
    parser.add_argument("--expected-duration", type=float, default=3.0)
    parser.add_argument("--duration-tolerance", type=float, default=0.08)
    parser.add_argument("--allow-audio", action="store_true")
    parser.add_argument("--job-record-dir", type=Path)
    parser.add_argument("--sample-dir", type=Path)
    parser.add_argument("--contact-sheet", type=Path)
    parser.add_argument("--plan", type=Path, help="optional cut plan used to assign review tiers")
    parser.add_argument("--review-profile", choices=("balanced_auto", "precision"), default="balanced_auto")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    expected_ratio = expected_ratio_value(args.expected_ratio)
    cut_metadata, plan_metadata = load_cut_metadata(args.plan)
    results: list[dict[str, Any]] = []
    contact_rows: list[tuple[str, list[Path]]] = []

    for path in args.paths:
        hard_failures: list[str] = []
        warnings: list[str] = []
        cut = cut_metadata.get(path.stem.lower(), {})
        semantic_proof_cut = is_semantic_proof_cut(cut)
        result: dict[str, Any] = {"path": str(path), "hard_failures": hard_failures, "warnings": warnings}
        if not path.exists() or path.stat().st_size == 0:
            hard_failures.append("missing_or_empty_file")
            results.append(result)
            continue

        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            with Image.open(path) as image:
                width, height = image.size
                result.update({"type": "image", "width": width, "height": height})
                if not math.isclose(width / height, expected_ratio, rel_tol=0.02):
                    hard_failures.append("wrong_aspect_ratio")
                borders = border_flags(image)
                if borders:
                    warnings.append("possible_black_border:" + ",".join(borders))
        else:
            metadata = probe_video(path)
            video_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "video"]
            audio_streams = [item for item in metadata.get("streams", []) if item.get("codec_type") == "audio"]
            if not video_streams:
                hard_failures.append("missing_video_stream")
                results.append(result)
                continue
            stream = video_streams[0]
            width, height = int(stream["width"]), int(stream["height"])
            duration = float(stream.get("duration") or metadata.get("format", {}).get("duration") or 0)
            planned_duration = cut.get("duration_seconds")
            expected_duration = (
                float(planned_duration)
                if isinstance(planned_duration, (int, float)) and not isinstance(planned_duration, bool)
                else args.expected_duration
            )
            result.update({
                "type": "video", "width": width, "height": height, "duration": duration,
                "fps": stream.get("avg_frame_rate"), "frame_count": stream.get("nb_frames"),
                "audio_stream_count": len(audio_streams),
                "expected_duration": expected_duration,
                "duration_source": "plan_cut" if expected_duration != args.expected_duration or planned_duration is not None else "cli_default",
            })
            if not math.isclose(width / height, expected_ratio, rel_tol=0.02):
                hard_failures.append("wrong_aspect_ratio")
            if abs(duration - expected_duration) > args.duration_tolerance:
                hard_failures.append("wrong_duration")
            if audio_streams and not args.allow_audio:
                hard_failures.append("unexpected_audio")

            record_path = find_job_record(args.job_record_dir, path.stem)
            if record_path:
                record = json.loads(record_path.read_text())
                result["job_record"] = str(record_path)
                if record.get("returned_display_name") and record.get("returned_display_name") != "Kling v3.0":
                    hard_failures.append("wrong_returned_model")
                if record.get("returned_job_set_type") and record.get("returned_job_set_type") != "kling3_0":
                    hard_failures.append("wrong_returned_job_set_type")
                if record.get("start_image_only") is False or record.get("end_image"):
                    hard_failures.append("invalid_start_end_image_contract")
            elif args.job_record_dir:
                warnings.append("missing_job_record")

            sample_root = args.sample_dir or path.parent / "qc-samples"
            checkpoint_count = 5 if semantic_proof_cut else 3
            samples = extract_samples(path, duration, sample_root, checkpoint_count=checkpoint_count)
            result["sample_frames"] = [str(item) for item in samples]
            result["sample_checkpoint_count"] = checkpoint_count
            border_counts: dict[str, int] = {}
            for sample in samples:
                with Image.open(sample) as frame:
                    for side in border_flags(frame):
                        border_counts[side] = border_counts.get(side, 0) + 1
            persistent = [side for side, count in border_counts.items() if count == len(samples)]
            if persistent:
                hard_failures.append("persistent_black_border:" + ",".join(persistent))
            contact_rows.append((path.stem, samples))

        result["technical_pass"] = not hard_failures
        if semantic_proof_cut:
            result["semantic_units"] = cut.get("semantic_units", [])
            result["visual_proof"] = cut.get("visual_proof", {})
            result["duration_class"] = cut.get("duration_class")
            result["semantic_review_status"] = "pending_semantic_visual_qc"
            result["semantic_review_required"] = {
                "per_unit": "every semantic unit must have at least one visible evidence frame",
                "proof_checks": [
                    "subject_visible",
                    "start_state_visible",
                    "visible_action_completed",
                    "end_state_visible",
                    "causal_link_visible",
                    "success_frame_clear",
                    "literal_first_pass",
                    "static_anchors_stable",
                ],
                "validator": "scripts/validate_semantic_qc.py",
            }
        else:
            result["semantic_review_required"] = ["script_meaning", "anatomy_safety", "generated_text", "product_integrity", "reference_medium"]
        tier, reasons = review_tier(args.review_profile, cut, warnings)
        result["review_tier"] = tier
        result["review_reason"] = reasons
        results.append(result)

    if args.contact_sheet:
        make_contact_sheet(contact_rows, args.contact_sheet)

    payload = {
        "expected_ratio": args.expected_ratio,
        "expected_duration": args.expected_duration,
        "expected_duration_role": "legacy_or_unmatched_cut_default",
        "plan_schema_version": plan_metadata.get("schema_version"),
        "plan_duration_policy": plan_metadata.get("duration_policy"),
        "plan_semantic_visual_contract": plan_metadata.get("semantic_visual_contract"),
        "review_profile": args.review_profile,
        "review_tier_counts": {
            "deep": sum(item.get("review_tier") == "deep" for item in results),
            "contact_sheet": sum(item.get("review_tier") == "contact_sheet" for item in results),
        },
        "pass_count": sum(bool(item.get("technical_pass")) for item in results),
        "fail_count": sum(not bool(item.get("technical_pass")) for item in results),
        "warning_count": sum(len(item["warnings"]) for item in results),
        "results": results,
    }
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n")
    print(json.dumps({key: payload[key] for key in ("pass_count", "fail_count", "warning_count")}, ensure_ascii=False))
    for item in results:
        if item["hard_failures"] or item["warnings"]:
            print(json.dumps({"path": item["path"], "hard_failures": item["hard_failures"], "warnings": item["warnings"]}, ensure_ascii=False))
    raise SystemExit(1 if payload["fail_count"] else 0)


if __name__ == "__main__":
    main()

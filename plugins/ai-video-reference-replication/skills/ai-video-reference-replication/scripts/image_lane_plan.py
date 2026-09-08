#!/usr/bin/env python3
"""Create a deterministic still-candidate/concurrency plan for a video run.

This script does not call a provider. It records the GPT-only still plan,
planned candidate count, conservative OpenAI cap, and the distinction between
request concurrency and provider rate limits before any generation.
"""

from __future__ import annotations

import argparse
import json
from typing import Any


MODES = ("openai_only",)


def build_plan(
    cut_count: int,
    mode: str,
    openai_concurrency: int,
    openai_ipm_limit: int,
    request_batch_size: int,
) -> dict[str, Any]:
    if cut_count < 1:
        raise ValueError("cut_count must be positive")
    if mode not in MODES:
        raise ValueError(f"mode must be one of {', '.join(MODES)}")
    for name, value in (
        ("openai_concurrency", openai_concurrency),
        ("openai_ipm_limit", openai_ipm_limit),
        ("request_batch_size", request_batch_size),
    ):
        if value < 1:
            raise ValueError(f"{name} must be positive")

    openai_requests = cut_count
    candidate_count = openai_requests
    in_flight_slots = openai_concurrency

    # IPM is a per-minute throughput limit, not a hard concurrency limit. This
    # is only a conservative planning number for the default n=1 route.
    openai_images_per_minute_budget = openai_ipm_limit * request_batch_size
    return {
        "mode": mode,
        "image_generation_route": "built_in_image_gen",
        "main_cut_count": cut_count,
        "candidate_images_planned": candidate_count,
        "selected_start_images_required": cut_count,
        "candidate_images_per_cut": 1,
        "higgsfield_image_jobs": 0,
        "image_api_jobs": 0,
        "image_cli_jobs": 0,
        "lanes": {
            "higgsfield": {
                "enabled": False,
                "model": None,
                "requests": 0,
                "max_concurrency": 0,
                "policy": "forbidden_for_still_generation",
            },
            "openai": {
                "enabled": True,
                "route": "built_in_image_gen",
                "model": None,
                "requests": openai_requests,
                "max_concurrency": openai_concurrency,
                "request_batch_size": request_batch_size,
                "documented_ipm_budget": openai_ipm_limit,
                "conservative_images_per_minute_budget": openai_images_per_minute_budget,
            },
        },
        "nominal_in_flight_request_slots": in_flight_slots,
        "provider_limit_is_not_fixed": True,
        "notes": [
            "Distinct scene prompts use separate requests; request_batch_size is only for same-prompt variants.",
            "OpenAI public GPT Image documentation exposes tiered IPM/TPM limits, not a universal simultaneous-image maximum.",
            "Higgsfield is forbidden for still-image generation; it may be used only by the separately planned Kling video stage.",
            "Direct Images API and ImageGen CLI routes are disabled; built-in image_gen is the only still route.",
            "A selected start image is the only still passed to Kling; rejected candidates remain in the ledger.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cut-count", required=True, type=int)
    parser.add_argument("--mode", choices=MODES, default="openai_only")
    parser.add_argument("--openai-concurrency", type=int, default=5)
    parser.add_argument("--openai-ipm-limit", type=int, default=5)
    parser.add_argument("--request-batch-size", type=int, default=1)
    parser.add_argument("--output", type=str)
    args = parser.parse_args()
    plan = build_plan(
        cut_count=args.cut_count,
        mode=args.mode,
        openai_concurrency=args.openai_concurrency,
        openai_ipm_limit=args.openai_ipm_limit,
        request_batch_size=args.request_batch_size,
    )
    rendered = json.dumps(plan, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        from pathlib import Path

        Path(args.output).write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Block exact or perceptually near-duplicate selected starts across cuts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dhash(path: Path, size: int = 8) -> int:
    with Image.open(path) as image:
        gray = image.convert("L").resize((size + 1, size), Image.Resampling.LANCZOS)
        pixels = list(gray.get_flattened_data())
    value = 0
    for row in range(size):
        offset = row * (size + 1)
        for column in range(size):
            value = (value << 1) | (pixels[offset + column] > pixels[offset + column + 1])
    return value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-dhash-distance", type=int, default=4)
    args = parser.parse_args()

    records = []
    for path in args.paths:
        if not path.is_file():
            raise SystemExit(f"missing selected start: {path}")
        records.append({"path": str(path.resolve()), "sha256": sha256(path), "dhash": f"{dhash(path):016x}"})

    failures = []
    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            distance = (int(left["dhash"], 16) ^ int(right["dhash"], 16)).bit_count()
            exact = left["sha256"] == right["sha256"]
            near = distance <= args.max_dhash_distance
            if exact or near:
                failures.append(
                    {
                        "left": left["path"],
                        "right": right["path"],
                        "reason": "exact_sha256_duplicate" if exact else "perceptual_near_duplicate",
                        "dhash_distance": distance,
                    }
                )

    result = {
        "schema_version": "selected-start-diversity.v1",
        "status": "pass" if not failures else "fail",
        "selected_start_count": len(records),
        "max_dhash_distance": args.max_dhash_distance,
        "records": records,
        "blocking_duplicates": failures,
        "manual_contact_sheet_scene_variety_review_required": True,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"status": result["status"], "selected_start_count": len(records), "blocking_duplicate_count": len(failures)}, ensure_ascii=False))
    raise SystemExit(1 if failures else 0)


if __name__ == "__main__":
    main()

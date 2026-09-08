#!/usr/bin/env python3
"""Validate the required structure of a product visual source pack."""

from __future__ import annotations

import sys
import os
from pathlib import Path
from typing import Optional


REQUIRED_HEADINGS = [
    "## 1. Source Snapshot",
    "## 2. Library Resolution",
    "## 3. Official Product Source and Master Anchor",
    "## 4. Visible Product Material",
    "## 5. Ingredients, Build and Origin",
    "## 6. Core Visual Distinction",
    "## 7. Setting and Use Action",
    "## 8. Existing Visual Expressions",
    "## 9. Evidence and Deterministic Post",
    "## 10. Asset Manifest",
    "## 11. Script Visual Coverage",
    "## 12. Prohibited Inferences and Handoff Status",
]

REQUIRED_MARKERS = [
    "company_name:",
    "product_name:",
    "product_detail_url:",
    "library_root:",
    "library_resolution_status:",
    "approved_product_master_asset_id:",
    "product_master_status:",
    "| asset_id | absolute_path | page_location_or_url |",
    "| script_beat | viewer_takeaway |",
    "ready_for_visual_planning:",
    "ready_for_generation:",
]

LIBRARY_STATES = {
    "existing_product",
    "existing_company_new_product",
    "new_company_product",
    "ambiguous",
}

MASTER_STATES = {
    "approved_existing",
    "planned_imagegen",
    "qc_passed",
    "rejected",
    "blocked",
}

CANONICAL_LIBRARY_ROOT = os.environ.get("VIDEO_PRODUCT_LIBRARY_ROOT", str(Path.home() / "Documents" / "인코어"))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_visual_source_pack.py /absolute/path/to/product-visual-source-pack.md")
        return 2

    path = Path(sys.argv[1])
    if not path.is_absolute():
        print("ERROR: path must be absolute")
        return 2
    if not path.is_file():
        print(f"ERROR: file not found: {path}")
        return 2

    text = path.read_text(encoding="utf-8")
    missing = [item for item in REQUIRED_HEADINGS + REQUIRED_MARKERS if item not in text]
    lines = [line.strip().lstrip("- ").strip() for line in text.splitlines()]

    def value_for(marker: str) -> Optional[str]:
        values = []
        for line in lines:
            normalized_line = line.replace("`", "")
            if normalized_line.startswith(marker):
                values.append(normalized_line[len(marker) :].strip())
        return values[-1] if values else None

    planning_status = value_for("ready_for_visual_planning:")
    generation_status = value_for("ready_for_generation:")
    library_status = value_for("library_resolution_status:")
    master_status = value_for("product_master_status:")
    library_root = value_for("library_root:")
    approved_master = value_for("approved_product_master_asset_id:")
    company_name = value_for("company_name:")
    product_name = value_for("product_name:")
    product_detail_url = value_for("product_detail_url:")

    if missing:
        print("ERROR: missing required structure")
        for item in missing:
            print(f"- {item}")
        return 1
    if planning_status not in {"yes", "no"}:
        print("ERROR: ready_for_visual_planning must be yes or no")
        return 1
    if generation_status not in {"yes", "no"}:
        print("ERROR: ready_for_generation must be yes or no")
        return 1
    if library_status not in LIBRARY_STATES:
        print(f"ERROR: invalid library_resolution_status: {library_status!r}")
        return 1
    if master_status not in MASTER_STATES:
        print(f"ERROR: invalid product_master_status: {master_status!r}")
        return 1
    if not company_name:
        print("ERROR: company_name must not be empty")
        return 1
    if not product_name:
        print("ERROR: product_name must not be empty")
        return 1
    if not product_detail_url or not product_detail_url.startswith(("https://", "http://")):
        print("ERROR: product_detail_url must be an HTTP(S) URL")
        return 1
    if library_root != CANONICAL_LIBRARY_ROOT:
        print(f"ERROR: library_root must be {CANONICAL_LIBRARY_ROOT}")
        return 1
    if library_status == "ambiguous" and (planning_status != "no" or generation_status != "no"):
        print("ERROR: ambiguous library resolution cannot be ready for planning or generation")
        return 1
    if generation_status == "yes" and master_status not in {"approved_existing", "qc_passed"}:
        print("ERROR: ready_for_generation yes requires an approved or QC-passed product master")
        return 1
    if generation_status == "yes" and approved_master in {None, "", "pending", "null"}:
        print("ERROR: ready_for_generation yes requires approved_product_master_asset_id")
        return 1

    print("PASS: product visual source pack structure is valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

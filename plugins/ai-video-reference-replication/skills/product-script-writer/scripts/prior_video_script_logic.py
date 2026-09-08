#!/usr/bin/env python3
"""Find traceable prior video-script sources for one exact company/product."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import unicodedata


DEFAULT_ROOT = Path(os.environ.get("VIDEO_PRODUCT_LIBRARY_ROOT", str(Path.home() / "Documents" / "인코어")))
MAX_TEXT_BYTES = 200_000
EXCLUDED_PARTS = {
    "tts",
    "followup",
    "cta",
    "supplement",
    "supplements",
    "preview",
    "rejected",
    "폐기",
    "사용주의",
    "original_user_script",
}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFC", value)
    return " ".join(value.casefold().split())


def exact_child(parent: Path, requested: str) -> Path:
    wanted = normalized(requested)
    matches = [p for p in parent.iterdir() if p.is_dir() and normalized(p.name) == wanted]
    if len(matches) != 1:
        names = sorted(p.name for p in parent.iterdir() if p.is_dir())
        raise ValueError(
            f"exact scope resolution failed for {requested!r} under {parent}: "
            f"matches={len(matches)} candidates={names}"
        )
    return matches[0]


def optional_exact_child(parent: Path, requested: str) -> Path:
    wanted = normalized(requested)
    matches = [p for p in parent.iterdir() if p.is_dir() and normalized(p.name) == wanted]
    if len(matches) > 1:
        raise ValueError(f"ambiguous exact scope for {requested!r} under {parent}: matches={len(matches)}")
    return matches[0] if matches else parent / requested


def safe_text(path: Path) -> str | None:
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_TEXT_BYTES:
            return None
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def excluded(path: Path) -> bool:
    lowered = normalized(str(path))
    return any(token in lowered for token in EXCLUDED_PARTS)


def has_canonical_written_sibling(path: Path) -> bool:
    name = path.name
    replacements = {
        "-spoken.txt": ".txt",
        "spoken-script.txt": "script.txt",
        "spoken_script.txt": "script.txt",
    }
    lowered = name.casefold()
    for suffix, replacement in replacements.items():
        if lowered.endswith(suffix):
            candidate = path.with_name(name[: len(name) - len(suffix)] + replacement)
            if candidate.is_file():
                return True
    return False


def context_approved_paths(context_path: Path, product_dir: Path) -> list[Path]:
    text = safe_text(context_path)
    if not text:
        return []
    match = re.search(
        r"^## 승인된 최근 대본 예시\s*$([\s\S]*?)(?=^##\s|\Z)",
        text,
        flags=re.MULTILINE,
    )
    if not match:
        return []
    paths: list[Path] = []
    for relative in re.findall(r"^###\s+(.+?)\s*$", match.group(1), flags=re.MULTILINE):
        raw = Path(relative.strip().strip("`"))
        candidate = (raw if raw.is_absolute() else product_dir / raw).resolve()
        try:
            candidate.relative_to(product_dir.resolve())
        except ValueError:
            continue
        if candidate.is_file():
            paths.append(candidate)
    return paths


def classify(path: Path, product_dir: Path, context_approved: set[Path]) -> tuple[str, int] | None:
    resolved = path.resolve()
    name = normalized(path.name)
    parts = {normalized(part) for part in path.parts}
    if resolved in context_approved:
        return "product_context_approved_example", 400
    if name.startswith("approved-script") and name.endswith(".txt"):
        if "spoken" in name:
            return "approved_spoken_variant", 320
        return "approved_script", 360
    if name == "대본.txt" and "capcut 자동편집" in parts:
        return "capcut_edit_input", 340
    if name == "script.txt" and "생성 결과물" in parts:
        if "tts" in parts:
            return None
        return "generation_main_script", 240
    return None


def artifact_evidence(path: Path, product_dir: Path) -> list[str]:
    evidence: list[str] = []
    current = path.parent
    for _ in range(5):
        if current == product_dir.parent or current == current.parent:
            break
        try:
            names = [p.name for p in current.iterdir() if p.is_file()]
        except OSError:
            names = []
        if any(name.endswith(".mp4") for name in names):
            evidence.append("sibling_video")
        if any("manifest" in normalized(name) and name.endswith(".json") for name in names):
            evidence.append("sibling_manifest")
        if evidence:
            break
        current = current.parent
    return sorted(set(evidence))


def build_inventory(root: Path, company: str, product: str, limit: int) -> dict:
    company_dir = exact_child(root, company)
    products_dir = company_dir / "_knowledge" / "products"
    product_dir = optional_exact_child(company_dir, product)
    product_knowledge_dir = optional_exact_child(products_dir, product) if products_dir.is_dir() else products_dir / product
    if not product_dir.is_dir() and not product_knowledge_dir.is_dir():
        raise ValueError(f"exact product scope {product!r} does not exist under {company_dir}")
    context_path = product_knowledge_dir / "product_context.md"

    approved_paths = set()
    if context_path.is_file() and product_dir.is_dir():
        approved_paths = {p.resolve() for p in context_approved_paths(context_path, product_dir)}

    paths: set[Path] = set(approved_paths)
    if product_dir.is_dir():
        for path in product_dir.rglob("*.txt"):
            if excluded(path):
                continue
            if classify(path, product_dir, approved_paths):
                paths.add(path.resolve())

    candidates = []
    for path in paths:
        if has_canonical_written_sibling(path):
            continue
        text = safe_text(path)
        classification = classify(path, product_dir, approved_paths)
        if text is None or not text.strip() or classification is None:
            continue
        source_type, rank = classification
        evidence = artifact_evidence(path, product_dir)
        if source_type == "generation_main_script" and not evidence:
            rank -= 100
        candidates.append(
            {
                "source_type": source_type,
                "rank": rank,
                "path": str(path),
                "relative_path": str(path.relative_to(product_dir)) if product_dir in path.parents else None,
                "sha256": sha256_text(text),
                "modified_at_epoch": int(path.stat().st_mtime),
                "artifact_evidence": evidence,
                "content_chars": len(text),
            }
        )

    candidates.sort(key=lambda item: (item["rank"], item["modified_at_epoch"]), reverse=True)
    selected = []
    seen_hashes = set()
    for item in candidates:
        if item["sha256"] in seen_hashes:
            continue
        seen_hashes.add(item["sha256"])
        selected.append(item)
        if len(selected) >= limit:
            break

    return {
        "schema_version": 1,
        "status": "ready" if selected else "no_prior_video_script",
        "company": company_dir.name,
        "product": product_knowledge_dir.name if product_knowledge_dir.is_dir() else product_dir.name,
        "company_path": str(company_dir),
        "product_path": str(product_dir) if product_dir.is_dir() else None,
        "product_context_path": str(context_path) if context_path.is_file() else None,
        "selection_policy": "exact company/product; approved and actual edit inputs first; content-hash deduplicated",
        "selected_sources": selected,
        "candidate_count": len(candidates),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--company", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    try:
        payload = build_inventory(args.root.resolve(), args.company, args.product, args.limit)
    except (OSError, ValueError) as exc:
        print(json.dumps({"schema_version": 1, "status": "scope_error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Validate the structure of an AI-ready product advertising knowledge brief."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_CONCEPTS = {
    "source record": (r"^##\s+\d+\.\s+소스 기록", r"확인 페이지", r"source"),
    "product definition": (r"^##\s+\d+\.\s+제품 핵심 정의", r"AI가 가장 먼저 알아야 할", r"제품 정의"),
    "product specifications": (r"제품 정체성과 기본 사양", r"기본 상품 정보", r"제품 정보"),
    "fact ledger": (r"사실 원장",),
    "manufacturing": (r"원재료·원산지·제조 공정", r"핵심 제조 공정", r"제조 공정"),
    "sensory or visual": (r"맛·향·식감", r"비주얼"),
    "audiences": (r"타깃",),
    "commerce": (r"가격·옵션·배송", r"가격과 구성", r"판매가"),
    "social proof": (r"사회적 증거", r"판매 신뢰"),
    "claim safety": (r"광고 주장 안전성", r"조심해야 할 표현", r"표현 원칙"),
    "missing information": (r"추가 확보가 필요한 정보", r"페이지에 없어", r"확인 필요"),
    "master prompt": (r"AI 마스터 프롬프트", r"AI에 그대로 전달할"),
    "provenance": (r"출처 추적표",),
}

FACT_LEDGER_LABELS = ("확인된 사실", "페이지 주장", "동적 정보", "광고 해석", "확인 필요")


def matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.MULTILINE | re.IGNORECASE) for pattern in patterns)


def validate(path: Path) -> list[str]:
    errors: list[str] = []

    if not path.is_file():
        return [f"File not found: {path}"]

    text = path.read_text(encoding="utf-8")

    if not re.search(r"^#\s+\S", text, re.MULTILINE):
        errors.append("Missing document title (# ...).")

    if not re.search(r"https?://\S+", text):
        errors.append("Missing source URL.")

    if not re.search(r"(확인일|기준일|checked_at).{0,20}\d{4}-\d{2}-\d{2}", text, re.IGNORECASE):
        errors.append("Missing dated source snapshot (YYYY-MM-DD).")

    for concept, patterns in REQUIRED_CONCEPTS.items():
        if not matches_any(text, patterns):
            errors.append(f"Missing required concept: {concept}.")

    missing_labels = [label for label in FACT_LEDGER_LABELS if label not in text]
    if missing_labels:
        errors.append("Fact ledger labels missing: " + ", ".join(missing_labels))

    if "```text" not in text:
        errors.append("AI master prompt must be in a ```text code block.")

    if not re.search(r"(동적 정보|가격|재고|배송).{0,120}(재확인|기준일|변경)", text, re.DOTALL):
        errors.append("Missing warning that dynamic commerce information must be rechecked.")

    if not re.search(r"(100%|ZERO|최고|건강|인증|무료|한정)", text, re.IGNORECASE):
        errors.append("Claim-safety section does not demonstrate review of risky advertising language.")

    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate_brief.py /absolute/path/to/product-ad-knowledge.md")
        return 2

    path = Path(sys.argv[1]).expanduser().resolve()
    errors = validate(path)

    if errors:
        print(f"FAIL: {path}")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"OK: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

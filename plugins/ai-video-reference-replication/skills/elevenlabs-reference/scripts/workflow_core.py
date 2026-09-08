#!/usr/bin/env python3
"""Text planning, quality scoring, and state helpers for the workflow."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class WorkflowError(RuntimeError):
    """Raised when a workflow precondition or invariant fails."""


KOREAN_DIRECTION_TAGS = {
    "신나게": "excited",
    "밝게": "brightly",
    "강조": "emphatically",
    "강조해서": "emphatically",
    "차분하게": "calmly",
    "속삭이듯": "whisper",
    "속삭이기": "whisper",
    "슬프게": "sad",
    "화나게": "angry",
    "놀라서": "surprised",
    "놀랍게": "surprised",
    "진지하게": "seriously",
    "따뜻하게": "warmly",
    "친근하게": "conversationally",
    "빠르게": "quickly",
    "천천히": "slowly",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def atomic_write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"필수 상태 파일을 찾을 수 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"JSON 상태 파일이 손상되었습니다: {path}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_for_comparison(text: str) -> str:
    return "".join(character for character in text if "가" <= character <= "힣")


def normalize_lexical_content(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def levenshtein_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, 1):
        current = [left_index]
        for right_index, right_character in enumerate(right, 1):
            insertion = current[right_index - 1] + 1
            deletion = previous[right_index] + 1
            substitution = previous[right_index - 1] + (
                left_character != right_character
            )
            current.append(min(insertion, deletion, substitution))
        previous = current
    return previous[-1]


def character_error_rate(expected: str, actual: str) -> tuple[float, int, str, str]:
    normalized_expected = normalize_for_comparison(expected)
    normalized_actual = normalize_for_comparison(actual)
    if not normalized_expected:
        raise WorkflowError("비교할 한글 발음 대본이 없습니다.")
    distance = levenshtein_distance(normalized_expected, normalized_actual)
    return (
        distance / len(normalized_expected),
        distance,
        normalized_expected,
        normalized_actual,
    )


def _split_long_segment(text: str, maximum: int = 180) -> list[str]:
    if len(text) <= maximum:
        return [text.strip()]
    pieces = re.split(r"(?<=[,，;:])\s+|(?<=고)\s+|(?<=며)\s+", text)
    result: list[str] = []
    buffer = ""
    for piece in pieces:
        piece = piece.strip()
        if not piece:
            continue
        candidate = f"{buffer} {piece}".strip()
        if buffer and len(candidate) > maximum:
            result.append(buffer)
            buffer = piece
        else:
            buffer = candidate
    if buffer:
        result.append(buffer)
    return result


def split_script(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        raise WorkflowError("대본이 비어 있습니다.")

    raw_parts: list[str] = []
    for paragraph in re.split(r"\n+", normalized):
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        parts = re.split(r"(?<=[.!?。！？])\s+", paragraph)
        raw_parts.extend(part.strip() for part in parts if part.strip())

    result: list[str] = []
    for part in raw_parts:
        result.extend(_split_long_segment(part))
    if not result:
        raise WorkflowError("대본을 발화 구간으로 나누지 못했습니다.")
    return result


def _extract_leading_directions(text: str) -> tuple[list[str], str]:
    directions: list[str] = []
    remainder = text.strip()
    while True:
        match = re.match(r"^\[([^\]]+)\]\s*", remainder)
        if not match:
            break
        raw_direction = match.group(1).strip()
        directions.append(KOREAN_DIRECTION_TAGS.get(raw_direction, raw_direction))
        remainder = remainder[match.end() :].strip()
    return directions, remainder


def validate_korean_only(text: str) -> None:
    without_directions = re.sub(
        r"(?m)^\s*(?:\[[가-힣\s]+\]\s*)+",
        "",
        text,
    )
    latin_tokens = sorted(set(re.findall(r"[A-Za-z]+", without_directions)))
    number_tokens = sorted(set(re.findall(r"\d+(?:[.,]\d+)*", without_directions)))
    if latin_tokens or number_tokens:
        items = latin_tokens + number_tokens
        raise WorkflowError(
            "엄격한 한국어 발음 모드에서 읽는 법이 모호한 토큰을 발견했습니다: "
            + ", ".join(items)
            + ". 한글 발음으로 대본을 고친 뒤 다시 실행하세요."
        )
    if not re.search(r"[가-힣]", without_directions):
        raise WorkflowError("대본에서 한글 발화 문장을 찾지 못했습니다.")


def infer_direction(text: str, default_direction: str) -> str:
    if "?" in text or "？" in text:
        return "curiously"
    if any(keyword in text for keyword in ("놀랍", "세상에", "정말요")):
        return "surprised"
    if any(keyword in text for keyword in ("걱정", "문제", "어렵", "힘들")):
        return "concerned"
    if any(keyword in text for keyword in ("추천", "좋아요", "해결", "가능")):
        return "warmly"
    if "!" in text or "！" in text:
        return "excited"
    return default_direction


def direction_from_profile(profile: dict[str, Any]) -> tuple[str, str | None]:
    metrics = profile.get("audio_metrics", profile)
    rate = metrics.get("syllables_per_active_second")
    pitch_range = metrics.get("pitch_range_semitones")
    if isinstance(rate, (int, float)) and rate >= 5.3:
        return "energetically", None
    if (
        isinstance(rate, (int, float))
        and rate <= 3.4
        and isinstance(pitch_range, (int, float))
        and pitch_range <= 4.0
    ):
        return "calmly", None
    if isinstance(pitch_range, (int, float)) and pitch_range >= 7.0:
        return "expressively", None
    return "conversationally", None


def plan_script(text: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    validate_korean_only(text)
    default_direction, pace_direction = direction_from_profile(profile)
    segments: list[dict[str, Any]] = []
    for index, raw_segment in enumerate(split_script(text), 1):
        manual_directions, spoken_text = _extract_leading_directions(raw_segment)
        if not spoken_text:
            raise WorkflowError(f"{index}번 구간에 실제 발화 문장이 없습니다.")
        direction = (
            manual_directions[0]
            if manual_directions
            else infer_direction(spoken_text, default_direction)
        )
        tags = [direction]
        for extra_direction in manual_directions[1:]:
            if extra_direction not in tags:
                tags.append(extra_direction)
        if pace_direction and pace_direction not in tags:
            tags.append(pace_direction)
        tts_text = " ".join(f"[{tag}]" for tag in tags) + " " + spoken_text
        segments.append(
            {
                "index": index,
                "source_text": raw_segment,
                "spoken_text": spoken_text,
                "tts_text": tts_text.strip(),
                "directions": tags,
                "status": "pending_generation",
                "attempts": [],
                "selected_attempt": None,
                "user_feedback": [],
            }
        )
    return segments


def reference_quality(
    metrics: dict[str, Any],
    transcript: str,
    *,
    transcript_language_code: str | None,
    speaker_count: int | None,
) -> dict[str, Any]:
    hard_failures: list[str] = []
    warnings: list[str] = []
    active_seconds = float(metrics.get("active_speech_seconds") or 0.0)
    hangul_count = len(normalize_for_comparison(transcript))
    clipping_ratio = float(metrics.get("clipping_ratio") or 0.0)

    if not transcript_language_code or transcript_language_code.lower() not in {
        "ko",
        "kor",
    }:
        hard_failures.append("레퍼런스 발화가 한국어로 확인되지 않았습니다.")
    if speaker_count is None:
        hard_failures.append("레퍼런스의 단일 화자 여부를 확인하지 못했습니다.")
    elif speaker_count != 1:
        hard_failures.append(
            f"레퍼런스에서 {speaker_count}명의 화자가 감지되었습니다. 단일 화자만 허용합니다."
        )
    if active_seconds < 20.0:
        hard_failures.append("정제된 유효 발화가 20초 미만입니다.")
    elif active_seconds < 45.0:
        warnings.append(
            "정제된 유효 발화가 45초 미만이라 복제 일관성이 낮을 수 있습니다."
        )
    if hangul_count < 40:
        hard_failures.append("음성에서 확인된 한글 발화량이 너무 적습니다.")
    if clipping_ratio > 0.01:
        hard_failures.append("클리핑 비율이 높아 복제 샘플로 사용할 수 없습니다.")
    elif clipping_ratio > 0.001:
        warnings.append("일부 클리핑이 감지되었습니다.")

    return {
        "status": "failed" if hard_failures else ("warning" if warnings else "passed"),
        "hard_failures": hard_failures,
        "warnings": warnings,
        "active_speech_seconds": active_seconds,
        "hangul_syllable_count": hangul_count,
        "transcript_language_code": transcript_language_code,
        "speaker_count": speaker_count,
    }


def score_candidate(
    *,
    expected_text: str,
    transcript_text: str,
    transcript_language_code: str | None = None,
    candidate_metrics: dict[str, Any],
    reference_profile: dict[str, Any],
    alignment: dict[str, Any],
    target_duration_seconds: float | None = None,
) -> dict[str, Any]:
    cer, distance, expected_normalized, actual_normalized = character_error_rate(
        expected_text,
        transcript_text,
    )
    reference_metrics = reference_profile.get("audio_metrics", reference_profile)
    reference_rate = reference_metrics.get("syllables_per_active_second")
    candidate_rate = candidate_metrics.get("syllables_per_active_second")
    speed_deviation: float | None = None
    if (
        isinstance(reference_rate, (int, float))
        and reference_rate > 0
        and isinstance(candidate_rate, (int, float))
    ):
        speed_deviation = abs(candidate_rate - reference_rate) / reference_rate

    duration_deviation: float | None = None
    if target_duration_seconds and target_duration_seconds > 0:
        candidate_duration = float(candidate_metrics.get("duration_seconds") or 0.0)
        duration_deviation = (
            abs(candidate_duration - target_duration_seconds) / target_duration_seconds
        )

    clipping_ratio = float(candidate_metrics.get("clipping_ratio") or 0.0)
    leading_silence = float(candidate_metrics.get("leading_silence_seconds") or 0.0)
    trailing_silence = float(candidate_metrics.get("trailing_silence_seconds") or 0.0)
    alignment_characters = [
        character
        for character in (alignment.get("characters") or [])
        if isinstance(character, dict)
    ]
    aligned_text = "".join(
        str(character.get("text") or "")
        for character in alignment_characters
    )
    aligned_normalized = normalize_for_comparison(aligned_text)
    expected_lexical = normalize_lexical_content(expected_text)
    actual_lexical = normalize_lexical_content(transcript_text)
    timing_valid = bool(alignment_characters)
    previous_start = -1.0
    for character in alignment_characters:
        start = character.get("start")
        end = character.get("end")
        character_text = str(character.get("text") or "")
        if not (
            isinstance(start, (int, float))
            and isinstance(end, (int, float))
            and start >= 0
            and end >= start
            and start >= previous_start
            and (
                not normalize_for_comparison(character_text)
                or end > start
            )
        ):
            timing_valid = False
            break
        previous_start = float(start)
    checks = {
        "exact_hangul_transcript": distance == 0,
        "no_unexpected_lexical_content": actual_lexical == expected_lexical,
        "korean_language_confirmed": (
            transcript_language_code is not None
            and transcript_language_code.lower() in {"ko", "kor"}
        ),
        "speed_within_10_percent": (
            speed_deviation is not None and speed_deviation <= 0.10
        ),
        "target_duration_within_5_percent": (
            duration_deviation is None or duration_deviation <= 0.05
        ),
        "no_material_clipping": clipping_ratio <= 0.001,
        "leading_silence_ok": leading_silence <= 0.35,
        "trailing_silence_ok": trailing_silence <= 0.55,
        "forced_alignment_complete": aligned_normalized == expected_normalized,
        "forced_alignment_timing_valid": timing_valid,
        "nonempty_active_audio": float(
            candidate_metrics.get("active_speech_seconds") or 0.0
        )
        > 0.1,
    }
    auto_pass = all(checks.values())
    score = (
        cer * 100.0
        + (speed_deviation or 0.0) * 12.0
        + (duration_deviation or 0.0) * 8.0
        + clipping_ratio * 100.0
        + max(0.0, leading_silence - 0.35) * 2.0
        + max(0.0, trailing_silence - 0.55) * 2.0
    )
    return {
        "auto_pass": auto_pass,
        "checks": checks,
        "score": round(score, 6),
        "character_error_rate": round(cer, 6),
        "edit_distance": distance,
        "expected_normalized": expected_normalized,
        "transcript_normalized": actual_normalized,
        "expected_lexical": expected_lexical,
        "transcript_lexical": actual_lexical,
        "alignment_normalized": aligned_normalized,
        "speed_deviation_ratio": (
            round(speed_deviation, 6) if speed_deviation is not None else None
        ),
        "duration_deviation_ratio": (
            round(duration_deviation, 6) if duration_deviation is not None else None
        ),
        "alignment_loss": alignment.get("loss"),
        "requires_human_listening": True,
    }

#!/usr/bin/env python3
"""Generate one coherent ElevenLabs v3 take and stop before listening approval.

This module deliberately does not finalize audio.  It creates a new revision
from an already-finalized source job, submits the complete script in one TTS
request per attempt, runs strict whole-script transcription/alignment gates,
and preserves the selected whole-take WAV byte-for-byte as
``review/full_preview.wav``.  Sentence clips are derived review aids only.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import hashlib
import io
import json
import math
import os
import re
import secrets
import shutil
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from audio_tools import (
    AudioToolError,
    _sanitized_media_environment,
    analyze_wav,
    extract_wav_interval,
    require_binary,
    wav_to_mp3,
)
from elevenlabs_reference import (
    ApiError,
    ElevenLabsClient,
    LISTENING_APPROVAL_CONFIRMATION,
    STATE_DIR,
    _command_approve_locked,
    canonicalize_stt_notation,
    choose_output_format,
    create_new_clone,
    decode_tts_audio,
    initialize_job_directory,
    job_write_lock,
    profile_for_existing_voice,
    resolve_cloud_voice,
    validate_run_preconditions,
    validate_current_prosody_qc,
    verify_existing_voice,
    verify_live_model,
)
from workflow_core import (
    KOREAN_DIRECTION_TAGS,
    WorkflowError,
    atomic_write_json,
    direction_from_profile,
    load_json,
    normalize_for_comparison,
    normalize_lexical_content,
    plan_script,
    sha256_file,
    utc_now,
    validate_korean_only,
)


MAX_DURATION_SECONDS = 60.0
MAX_ATTEMPTS = 5
NATURAL_DEFAULT_MODEL_ID = "eleven_v3"
NATURAL_DEFAULT_DELIVERY_TAG = "conversationally"
NATURAL_DEFAULT_SPEED = 1.15
NATURAL_DEFAULT_STABILITY = 0.35
STT_VARIANTS = (
    (173, 0.0),
    (907, 0.1),
    (2027, 0.2),
)


def _standing_tts_generation_authorized() -> bool:
    preferences_path = STATE_DIR / "user_preferences.json"
    if not preferences_path.is_file():
        return False
    try:
        authorization = load_json(preferences_path).get(
            "standing_tts_generation_authorization",
            {},
        )
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    return bool(
        authorization.get("confirmed")
        and authorization.get("never_request_per_generation_approval")
        and authorization.get("repeat_prompt") is False
    )


class CoherentClient(Protocol):
    """Small client surface used by the workflow and its offline test."""

    def create_speech_with_timing(
        self,
        *,
        voice_id: str,
        text: str,
        output_format: str,
        seed: int,
        stability: float,
        speed: float,
        previous_text: str | None,
        next_text: str | None,
        pronunciation_dictionary_locators: (
            list[dict[str, str]] | None
        ) = None,
        model_id: str | None = None,
    ) -> tuple[dict[str, Any], dict[str, str]]: ...

    def transcribe(
        self,
        source: Path,
        *,
        detect_speakers: bool = False,
        seed: int = 173,
        temperature: float = 0.0,
    ) -> dict[str, Any]: ...

    def forced_alignment(self, source: Path, text: str) -> dict[str, Any]: ...


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_name, path)
    finally:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _relative(path: Path, job_dir: Path) -> str:
    return str(path.resolve().relative_to(job_dir.resolve()))


def _write_job(job_dir: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    atomic_write_json(job_dir / "job.json", job)


def _validate_empty_destination(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise WorkflowError(f"새 리비전 경로가 폴더가 아닙니다: {path}")
        if any(path.iterdir()):
            raise WorkflowError(
                "coherent-block 출력은 비어 있는 새 리비전 폴더여야 합니다: "
                f"{path}"
            )
    else:
        path.mkdir(parents=True, exist_ok=False)


def _validate_delivery_tag(value: str) -> str:
    tag = value.strip()
    bracketed = re.fullmatch(r"\[([^\[\]\r\n]+)\]", tag)
    if bracketed:
        tag = bracketed.group(1).strip()
    tag = KOREAN_DIRECTION_TAGS.get(tag, tag)
    if (
        not tag
        or len(tag) > 80
        or any(character in tag for character in "[]\r\n")
    ):
        raise WorkflowError(
            "전체 테이크에는 대괄호·줄바꿈이 없는 전달 태그 하나만 사용할 수 있습니다."
        )
    return tag


def _request_text_for_model(
    *,
    model_id: str,
    delivery_tag: str,
    generation_text: str,
) -> str:
    if model_id == "eleven_v3":
        return f"[{delivery_tag}] {generation_text}"
    return generation_text


def _source_final_wav(
    source_dir: Path,
    source_job: dict[str, Any],
) -> Path:
    relative_value = source_job.get("final_wav")
    if not relative_value:
        raise WorkflowError("원본 완료 작업에 final_wav 기록이 없습니다.")
    path = source_dir / str(relative_value)
    if not path.is_file():
        raise WorkflowError(f"원본 완료 WAV를 찾을 수 없습니다: {path}")
    return path


def _load_source(
    source_dir: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], Path]:
    if not source_dir.is_dir():
        raise WorkflowError(f"원본 작업 폴더를 찾을 수 없습니다: {source_dir}")
    source_job = load_json(source_dir / "job.json")
    source_plan = load_json(source_dir / "script_plan.json")
    reference_profile = load_json(source_dir / "reference_profile.json")
    if source_job.get("finalized") is not True:
        raise WorkflowError(
            "coherent-block은 이미 최종 완료된 원본 작업에서만 새 리비전을 만듭니다."
        )
    voice_id = str(source_job.get("voice_id") or "")
    if not voice_id:
        raise WorkflowError("원본 완료 작업에 voice_id가 없습니다.")
    segments = source_plan.get("segments")
    if not isinstance(segments, list) or not segments:
        raise WorkflowError("원본 완료 작업에 문장 계획이 없습니다.")
    for expected_index, segment in enumerate(segments, 1):
        if (
            not isinstance(segment, dict)
            or int(segment.get("index") or 0) != expected_index
            or not str(segment.get("spoken_text") or "").strip()
        ):
            raise WorkflowError(
                f"원본 문장 계획의 {expected_index}번 항목이 유효하지 않습니다."
            )
    final_wav = _source_final_wav(source_dir, source_job)
    source_metrics = analyze_wav(final_wav)
    duration = source_metrics.get("duration_seconds")
    if (
        not isinstance(duration, (int, float))
        or not math.isfinite(float(duration))
        or duration <= 0
        or duration > MAX_DURATION_SECONDS
    ):
        raise WorkflowError(
            "원본 전체 WAV가 coherent-block의 60초 제한을 충족하지 않습니다: "
            f"{duration}"
        )
    reference_rate = (
        reference_profile.get("audio_metrics", reference_profile)
    ).get("syllables_per_active_second")
    if (
        not isinstance(reference_rate, (int, float))
        or not math.isfinite(float(reference_rate))
        or reference_rate <= 0
    ):
        raise WorkflowError("원본 레퍼런스 프로필에 유효한 전체 발화 속도가 없습니다.")
    return source_job, source_plan, reference_profile, final_wav


def _full_spoken_text(source_plan: dict[str, Any]) -> str:
    # A newline between every sentence makes Eleven v3 reset delivery and adds
    # block-like pauses.  Spaces preserve punctuation while keeping one coherent
    # conversational take.
    return " ".join(
        str(segment["spoken_text"]).strip()
        for segment in source_plan["segments"]
    )


def _strict_transcript_result(
    *,
    expected_text: str,
    transcript: dict[str, Any],
    seed: int,
    temperature: float,
) -> dict[str, Any]:
    transcript_text = str(transcript.get("text") or "")
    canonical_text = canonicalize_stt_notation(expected_text, transcript_text)
    language_code = (
        str(transcript.get("language_code"))
        if transcript.get("language_code")
        else None
    )
    checks = {
        "korean_language_confirmed": bool(
            language_code and language_code.lower() in {"ko", "kor"}
        ),
        "exact_hangul_transcript": (
            normalize_for_comparison(canonical_text)
            == normalize_for_comparison(expected_text)
        ),
        "no_unexpected_lexical_content": (
            normalize_lexical_content(canonical_text)
            == normalize_lexical_content(expected_text)
        ),
    }
    return {
        "seed": seed,
        "temperature": temperature,
        "transcript_text": transcript_text,
        "canonical_text": canonical_text,
        "language_code": language_code,
        "checks": checks,
        "passed": all(checks.values()),
    }


def _forced_alignment_result(
    *,
    expected_text: str,
    alignment: dict[str, Any],
    audio_duration_seconds: float,
) -> dict[str, Any]:
    characters = [
        item
        for item in (alignment.get("characters") or [])
        if isinstance(item, dict)
    ]
    aligned_text = "".join(str(item.get("text") or "") for item in characters)
    previous_start = -1.0
    previous_end = -1.0
    timing_valid = bool(characters)
    for item in characters:
        text = str(item.get("text") or "")
        start = item.get("start")
        end = item.get("end")
        if not (
            isinstance(start, (int, float))
            and isinstance(end, (int, float))
            and math.isfinite(float(start))
            and math.isfinite(float(end))
            and start >= 0
            and end >= start
            and start >= previous_start
            and end + 1e-6 >= previous_end
            and (
                not normalize_for_comparison(text)
                or end > start
            )
            and end <= audio_duration_seconds + 0.5
        ):
            timing_valid = False
            break
        previous_start = float(start)
        previous_end = float(end)
    checks = {
        "complete_hangul_alignment": (
            normalize_for_comparison(aligned_text)
            == normalize_for_comparison(expected_text)
        ),
        "no_unexpected_lexical_alignment": (
            normalize_lexical_content(aligned_text)
            == normalize_lexical_content(expected_text)
        ),
        "timing_valid": timing_valid,
    }
    return {
        "aligned_text": aligned_text,
        "alignment_loss": alignment.get("loss"),
        "character_count": len(characters),
        "checks": checks,
        "passed": all(checks.values()),
    }


def _alignment_intervals(
    alignment: dict[str, Any],
    segment_texts: list[str],
) -> list[tuple[float, float]]:
    characters = [
        item
        for item in (alignment.get("characters") or [])
        if isinstance(item, dict)
    ]
    flat_text_parts: list[str] = []
    flat_item_indices: list[int] = []
    for item_index, item in enumerate(characters):
        text = str(item.get("text") or "")
        flat_text_parts.append(text)
        flat_item_indices.extend([item_index] * len(text))
    flat_text = "".join(flat_text_parts)

    intervals: list[tuple[float, float]] = []
    cursor = 0
    for index, segment_text in enumerate(segment_texts, 1):
        start_offset = flat_text.find(segment_text, cursor)
        if start_offset < 0:
            raise WorkflowError(
                f"강제 정렬 결과에서 {index}번 문장의 정확한 경계를 찾지 못했습니다."
            )
        end_offset = start_offset + len(segment_text)
        if end_offset > len(flat_item_indices):
            raise WorkflowError(f"{index}번 문장의 정렬 문자 범위가 손상되었습니다.")
        item_indices = sorted(set(flat_item_indices[start_offset:end_offset]))
        timed_items = [characters[item_index] for item_index in item_indices]
        starts = [
            float(item["start"])
            for item in timed_items
            if isinstance(item.get("start"), (int, float))
        ]
        ends = [
            float(item["end"])
            for item in timed_items
            if isinstance(item.get("end"), (int, float))
        ]
        if not starts or not ends:
            raise WorkflowError(f"{index}번 문장의 정렬 시간이 없습니다.")
        start_seconds = min(starts)
        end_seconds = max(ends)
        if end_seconds - start_seconds < 0.1:
            raise WorkflowError(
                f"{index}번 문장의 정렬 구간이 0.1초 미만입니다."
            )
        intervals.append((start_seconds, end_seconds))
        cursor = end_offset
    return intervals


def _split_review_clips(
    *,
    preview_wav: Path,
    alignment: dict[str, Any],
    source_plan: dict[str, Any],
    output_dir: Path,
) -> list[dict[str, Any]]:
    segment_texts = [
        str(segment["spoken_text"]).strip()
        for segment in source_plan["segments"]
    ]
    intervals = _alignment_intervals(alignment, segment_texts)
    segment_dir = output_dir / "review" / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for segment, (start_seconds, end_seconds) in zip(
        source_plan["segments"],
        intervals,
        strict=True,
    ):
        index = int(segment["index"])
        wav_path = extract_wav_interval(
            preview_wav,
            segment_dir / f"{index:03d}.wav",
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            silence_padding_seconds=0.0,
        )
        mp3_path = wav_to_mp3(wav_path, segment_dir / f"{index:03d}.mp3")
        records.append(
            {
                "index": index,
                "spoken_text": str(segment["spoken_text"]),
                "start_seconds": round(start_seconds, 6),
                "end_seconds": round(end_seconds, 6),
                "wav": _relative(wav_path, output_dir),
                "mp3": _relative(mp3_path, output_dir),
                "wav_sha256": sha256_file(wav_path),
                "mp3_sha256": sha256_file(mp3_path),
                "scope": "alignment_derived_review_clip_only",
            }
        )
    return records


def _initial_state(
    *,
    source_dir: Path,
    source_job: dict[str, Any],
    source_plan: dict[str, Any],
    reference_profile: dict[str, Any],
    source_final_wav: Path,
    output_dir: Path,
    delivery_tag: str,
    speed: float,
    stability: float,
    seed: int,
    attempt_limit: int,
    reason: str,
    tts_override_text: str | None,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    full_text = _full_spoken_text(source_plan)
    generation_text = (tts_override_text or full_text).strip()
    if not normalize_for_comparison(generation_text):
        raise WorkflowError("전체 테이크 생성용 문장에 한글 발화가 없습니다.")
    request_text = f"[{delivery_tag}] {generation_text}"
    source_input = source_dir / str(source_job.get("script_path") or "")
    copied_script = output_dir / "input" / "script.txt"
    copied_script.parent.mkdir(parents=True, exist_ok=True)
    if source_input.is_file():
        shutil.copy2(source_input, copied_script)
    else:
        _atomic_write_text(copied_script, full_text + "\n")
    atomic_write_json(output_dir / "reference_profile.json", reference_profile)

    source_hashes = {
        "job_json": sha256_file(source_dir / "job.json"),
        "script_plan_json": sha256_file(source_dir / "script_plan.json"),
        "reference_profile_json": sha256_file(
            source_dir / "reference_profile.json"
        ),
        "final_wav": sha256_file(source_final_wav),
    }
    job = {
        "version": 2,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "workflow": "coherent_full_script_block",
        "status": "generating_coherent_take",
        "model_id": "eleven_v3",
        "finalized": False,
        "voice_id": str(source_job["voice_id"]),
        "voice_name": source_job.get("voice_name"),
        "voice_source": "authorized_existing_voice_from_finalized_job",
        "api_output_format": str(
            source_job.get("api_output_format") or "mp3_44100_128"
        ),
        "script_path": _relative(copied_script, output_dir),
        "segment_count": len(source_plan["segments"]),
        "maximum_duration_seconds": MAX_DURATION_SECONDS,
        "attempt_limit": attempt_limit,
        "global_delivery": {
            "tag": delivery_tag,
            "speed": speed,
            "stability": stability,
            "base_seed": seed,
            "seed_strategy": "base_seed_plus_zero_based_attempt_index",
            "scope": "one_settings_bundle_per_whole_take",
        },
        "tts_override": {
            "used": tts_override_text is not None,
            "text": generation_text if tts_override_text is not None else None,
            "sha256": (
                hashlib.sha256(generation_text.encode("utf-8")).hexdigest()
                if tts_override_text is not None
                else None
            ),
            "note": (
                "생성 유도문만 변경하며 STT와 Forced Alignment는 원래 "
                "발화문을 기준으로 수행한다."
                if tts_override_text is not None
                else None
            ),
        },
        "lineage": {
            "source_job_dir": str(source_dir),
            "source_status": source_job.get("status"),
            "source_approval_id": source_job.get("approval_id"),
            "source_hashes": source_hashes,
            "reason": reason,
        },
        "rights_attestation": source_job.get("rights_attestation"),
        "user_listening_approval_required": True,
        "human_listening_completed": False,
        "audio_listening_qc": {
            "status": "not_started",
            "required": True,
        },
        "review_revision": 0,
        "attempts": [],
        "retention_notice": (
            "전체 테이크 후보·전사·정렬과 정렬 기반 문장별 검토 클립이 "
            "새 리비전 폴더에 보존됩니다."
        ),
    }
    preferences_path = STATE_DIR / "user_preferences.json"
    if preferences_path.is_file():
        preferences = load_json(preferences_path)
        natural_policy = preferences.get("natural_voice_generation_policy", {})
        job["persistent_preferences"] = {
            "path": str(preferences_path),
            "sha256": sha256_file(preferences_path),
            "schema_version": preferences.get("schema_version"),
            "natural_generation_preset": natural_policy.get("preset"),
            "natural_generation_defaults": natural_policy.get("defaults", {}),
            "applied_model_id": NATURAL_DEFAULT_MODEL_ID,
            "applied_delivery_tag": delivery_tag,
            "applied_speed": speed,
            "applied_stability": stability,
        }
    plan = {
        "version": 2,
        "created_at": utc_now(),
        "workflow": "coherent_full_script_block",
        "model_id": "eleven_v3",
        "original_script": source_plan.get("original_script") or full_text,
        "full_spoken_text": full_text,
        "global_tts_text": request_text,
        "global_delivery": job["global_delivery"],
        "segments": [
            {
                "index": int(segment["index"]),
                "source_text": str(
                    segment.get("source_text") or segment["spoken_text"]
                ),
                "spoken_text": str(segment["spoken_text"]),
                "status": "pending_coherent_take",
            }
            for segment in source_plan["segments"]
        ],
        "attempts": [],
    }
    atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)
    return job, plan, request_text


def _initialize_prepared_new_reference_state(
    *,
    output_dir: Path,
    script_path: Path,
    script_text: str,
    reference_profile: dict[str, Any],
    reference_source_sha256: str,
    voice_id: str,
    voice_name: str,
    output_format: str,
    subscription_tier: str,
    delivery_tag: str | None,
    speed: float,
    stability: float,
    seed: int,
    model_id: str = NATURAL_DEFAULT_MODEL_ID,
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Create the canonical coherent job after reference/voice preparation.

    This helper is intentionally independent of the cloud preparation calls so
    the one-request initial generation contract can be tested offline.
    """
    segments = plan_script(script_text, reference_profile)
    selected_delivery = _validate_delivery_tag(
        delivery_tag or direction_from_profile(reference_profile)[0]
    )
    copied_script = output_dir / "input" / "script.txt"
    if script_path.resolve() != copied_script.resolve():
        shutil.copy2(script_path, copied_script)
    full_text = " ".join(
        str(segment["spoken_text"]).strip() for segment in segments
    )
    request_text = _request_text_for_model(
        model_id=model_id,
        delivery_tag=selected_delivery,
        generation_text=full_text,
    )
    atomic_write_json(output_dir / "reference_profile.json", reference_profile)
    now = utc_now()
    job: dict[str, Any] = {
        "version": 2,
        "created_at": now,
        "updated_at": now,
        "workflow": "coherent_full_script_block",
        "status": "generating_initial_coherent_take",
        "model_id": model_id,
        "active_model_id": model_id,
        "finalized": False,
        "voice_id": voice_id,
        "voice_name": voice_name,
        "voice_source": "new_authorized_clone",
        "api_output_format": output_format,
        "subscription_tier_detected": subscription_tier,
        "script_path": _relative(copied_script, output_dir),
        "segment_count": len(segments),
        "maximum_duration_seconds": MAX_DURATION_SECONDS,
        "attempt_limit": MAX_ATTEMPTS,
        "initial_batch_tts_request_limit": 1,
        "global_delivery": {
            "tag": selected_delivery,
            "speed": speed,
            "stability": stability,
            "base_seed": seed,
            "scope": "one_settings_bundle_per_whole_take",
        },
        "rights_attestation": {
            "confirmed": True,
            "confirmed_at": now,
            "actor": "current_user_confirmed_via_cli",
            "scope": "authorized_new_voice_clone",
            "reference_source_sha256": reference_source_sha256,
        },
        "generation_cost_contract": {
            "initial_whole_script_requests": 1,
            "retry_requests_per_explicit_token": 1,
            "maximum_total_requests": MAX_ATTEMPTS,
        },
        "user_listening_approval_required": True,
        "human_listening_completed": False,
        "audio_listening_qc": {
            "status": "not_started",
            "required": True,
        },
        "review_revision": 0,
        "attempts": [],
        "retention_notice": (
            "전체 테이크 후보·전사·정렬과 정렬 기반 문장별 검토 클립이 "
            "작업 폴더에 보존됩니다."
        ),
    }
    preferences_path = STATE_DIR / "user_preferences.json"
    if preferences_path.is_file():
        preferences = load_json(preferences_path)
        natural_policy = preferences.get("natural_voice_generation_policy", {})
        job["persistent_preferences"] = {
            "path": str(preferences_path),
            "sha256": sha256_file(preferences_path),
            "schema_version": preferences.get("schema_version"),
            "natural_generation_preset": natural_policy.get("preset"),
            "natural_generation_defaults": natural_policy.get("defaults", {}),
            "applied_model_id": model_id,
            "applied_delivery_tag": selected_delivery,
            "applied_speed": speed,
            "applied_stability": stability,
        }
    plan = {
        "version": 2,
        "created_at": now,
        "workflow": "coherent_full_script_block",
        "model_id": model_id,
        "active_model_id": model_id,
        "original_script": script_text,
        "full_spoken_text": full_text,
        "global_tts_text": request_text,
        "global_delivery": job["global_delivery"],
        "segments": [
            {
                "index": int(segment["index"]),
                "source_text": str(segment["source_text"]),
                "spoken_text": str(segment["spoken_text"]),
                "directions": [selected_delivery],
                "status": "pending_coherent_take",
            }
            for segment in segments
        ],
        "attempts": [],
    }
    atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)
    return job, plan, request_text


def _conservative_duration_preflight(
    *,
    output_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    reference_rate: float,
    speed: float,
    planned_attempt: int,
) -> dict[str, Any]:
    """Persist a conservative duration estimate before any billable TTS call."""
    full_text = str(plan.get("full_spoken_text") or _full_spoken_text(plan))
    hangul_syllable_count = len(re.findall(r"[가-힣]", full_text))
    segment_count = len(plan.get("segments") or [])
    minor_pause_count = len(re.findall(r"[,，;:]", full_text))
    # Do not assume speed > 1.0 will shorten the output.  Slower requested
    # speeds are included because they can only increase duration.
    conservative_speed_factor = min(float(speed), 1.0)
    effective_rate = float(reference_rate) * conservative_speed_factor
    active_speech_estimate = (
        hangul_syllable_count / effective_rate
        if hangul_syllable_count > 0 and effective_rate > 0
        else math.inf
    )
    uncertainty_multiplier = 1.20
    inter_segment_pause_seconds = max(segment_count - 1, 0) * 0.45
    minor_pause_seconds = minor_pause_count * 0.18
    edge_allowance_seconds = 0.80
    estimated_upper_seconds = (
        active_speech_estimate * uncertainty_multiplier
        + inter_segment_pause_seconds
        + minor_pause_seconds
        + edge_allowance_seconds
    )
    passed = bool(
        math.isfinite(estimated_upper_seconds)
        and estimated_upper_seconds <= MAX_DURATION_SECONDS
    )
    evidence = {
        "created_at": utc_now(),
        "planned_attempt": planned_attempt,
        "method": "reference_rate_conservative_upper_bound_v1",
        "hangul_syllable_count": hangul_syllable_count,
        "segment_count": segment_count,
        "minor_pause_count": minor_pause_count,
        "reference_syllables_per_active_second": reference_rate,
        "requested_speed": speed,
        "conservative_speed_factor": conservative_speed_factor,
        "effective_rate": round(effective_rate, 6),
        "active_speech_estimate_seconds": round(
            active_speech_estimate,
            6,
        ),
        "uncertainty_multiplier": uncertainty_multiplier,
        "inter_segment_pause_seconds": round(
            inter_segment_pause_seconds,
            6,
        ),
        "minor_pause_seconds": round(minor_pause_seconds, 6),
        "edge_allowance_seconds": edge_allowance_seconds,
        "estimated_upper_seconds": round(estimated_upper_seconds, 6),
        "maximum_duration_seconds": MAX_DURATION_SECONDS,
        "passed": passed,
        "tts_calls_before_gate": len(job.get("attempts") or []),
        "blocked_reason": (
            None
            if passed
            else (
                "보수적 예상 길이가 coherent 전체 테이크의 60초 제한을 "
                "초과하므로 유료 TTS 전에 차단함"
            )
        ),
    }
    evidence_path = (
        output_dir
        / "review"
        / f"duration-preflight-attempt-{planned_attempt:03d}.json"
    )
    atomic_write_json(evidence_path, evidence)
    job["duration_preflight"] = evidence
    job["duration_preflight_report"] = _relative(evidence_path, output_dir)
    job["duration_preflight_sha256"] = sha256_file(evidence_path)
    job.setdefault("duration_preflight_history", []).append(
        {
            "planned_attempt": planned_attempt,
            "report": _relative(evidence_path, output_dir),
            "sha256": sha256_file(evidence_path),
            "passed": passed,
            "estimated_upper_seconds": evidence["estimated_upper_seconds"],
        }
    )
    if not passed:
        job["status"] = "blocked_before_tts"
        job["finalized"] = False
        job["additional_generation_token"] = None
        job["audio_listening_qc"] = {
            "status": "blocked_before_tts",
            "required": True,
            "completed": False,
        }
        for segment in plan.get("segments") or []:
            segment["status"] = "blocked_before_tts_duration_limit"
        atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)
    return evidence


def _issue_single_retry_token(
    *,
    output_dir: Path,
    job: dict[str, Any],
    failed_attempt: dict[str, Any],
) -> str | None:
    attempt_count = len(job.get("attempts") or [])
    job["selected_take"] = None
    job["finalized"] = False
    job["audio_listening_qc"] = {
        "status": "blocked_before_audio_listening_qc",
        "required": True,
        "completed": False,
    }
    if attempt_count >= MAX_ATTEMPTS:
        job["status"] = "blocked_after_five_coherent_take_attempts"
        job["additional_generation_token"] = None
        token = None
    else:
        job["status"] = "coherent_retry_approval_required"
        token = secrets.token_hex(16)
        job["additional_generation_token"] = token
        job["additional_generation_scope"] = {
            "requests": 1,
            "next_attempt": attempt_count + 1,
            "failed_checks": [
                key
                for key, passed in (failed_attempt.get("checks") or {}).items()
                if not passed
            ],
        }
    _write_job(output_dir, job)
    return token


def _run_one_coherent_attempt(
    *,
    client: CoherentClient,
    output_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    seed: int,
    stability: float,
    speed: float,
) -> dict[str, Any]:
    attempt_number = len(job.get("attempts") or []) + 1
    if attempt_number > MAX_ATTEMPTS:
        raise WorkflowError("전체 테이크 최대 5회 시도를 이미 사용했습니다.")
    profile = load_json(output_dir / "reference_profile.json")
    reference_rate = profile.get("audio_metrics", profile).get(
        "syllables_per_active_second"
    )
    if (
        not isinstance(reference_rate, (int, float))
        or not math.isfinite(float(reference_rate))
        or float(reference_rate) <= 0
    ):
        raise WorkflowError("레퍼런스 프로필에 유효한 전체 발화 속도가 없습니다.")
    duration_preflight = _conservative_duration_preflight(
        output_dir=output_dir,
        job=job,
        plan=plan,
        reference_rate=float(reference_rate),
        speed=speed,
        planned_attempt=attempt_number,
    )
    if not duration_preflight["passed"]:
        return {
            "status": "blocked_before_tts",
            "attempt_count": len(job.get("attempts") or []),
            "duration_preflight": duration_preflight,
            "duration_preflight_report": str(
                (output_dir / str(job["duration_preflight_report"])).resolve()
            ),
            "additional_generation_token": None,
            "finalized": False,
        }
    expected_text = str(plan.get("full_spoken_text") or _full_spoken_text(plan))
    model_id = str(
        job.get("active_model_id") or job.get("model_id") or "eleven_v3"
    )
    attempt, alignment, wav_path, mp3_path = _run_attempt(
        client=client,
        output_dir=output_dir,
        job=job,
        plan=plan,
        request_text=str(plan["global_tts_text"]),
        expected_text=expected_text,
        reference_rate=float(reference_rate),
        attempt_number=attempt_number,
        seed=seed,
        stability=stability,
        speed=speed,
        model_id=model_id,
    )
    if attempt["strict_auto_pass"]:
        _select_for_audio_listening(
            output_dir=output_dir,
            job=job,
            plan=plan,
            source_plan=plan,
            attempt=attempt,
            alignment=alignment,
            wav_path=wav_path,
            mp3_path=mp3_path,
        )
        return {
            "status": job["status"],
            "selected_take": job["selected_take"],
            "preview_wav": str(
                (output_dir / str(job["review_preview_wav"])).resolve()
            ),
            "preview_mp3": str(
                (output_dir / str(job["review_preview_mp3"])).resolve()
            ),
            "preview_revision": job["review_revision"],
            "preview_sha256": job["review_preview_sha256"],
            "attempt_count": len(job["attempts"]),
            "finalized": False,
        }
    token = _issue_single_retry_token(
        output_dir=output_dir,
        job=job,
        failed_attempt=attempt,
    )
    return {
        "status": job["status"],
        "attempt_count": len(job["attempts"]),
        "failed_checks": [
            key
            for key, passed in (attempt.get("checks") or {}).items()
            if not passed
        ],
        "additional_generation_token": token,
        "finalized": False,
    }


def run_new_reference(
    *,
    script_path: Path,
    output_dir: Path,
    reference_video: Path,
    voice_name: str,
    consent_confirmed: bool,
    delivery_tag: str | None,
    speed: float,
    stability: float,
    seed: int,
    client: ElevenLabsClient,
) -> dict[str, Any]:
    """Create a new clone and make exactly one initial whole-script TTS call."""
    script_path = script_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    reference_video = reference_video.expanduser().resolve()
    if not script_path.is_file():
        raise WorkflowError(f"대본 파일을 찾을 수 없습니다: {script_path}")
    script_text = script_path.read_text(encoding="utf-8").strip()
    validate_korean_only(script_text)
    plan_script(script_text, {"audio_metrics": {}})
    if not 0.7 <= speed <= 1.2:
        raise WorkflowError("전체 테이크 speed는 0.7~1.2 범위여야 합니다.")
    if not 0.0 <= stability <= 1.0:
        raise WorkflowError("전체 테이크 stability는 0~1 범위여야 합니다.")
    if not 0 <= seed < 2**32:
        raise WorkflowError("seed는 0 이상 2^32 미만이어야 합니다.")
    if not voice_name.strip():
        raise WorkflowError("--new-voice-name은 비어 있을 수 없습니다.")
    validation_args = argparse.Namespace(
        target_duration=None,
        consent_confirmed=consent_confirmed,
        reference_video=reference_video,
        new_voice_name=voice_name,
        style_reference_video=None,
    )
    validate_run_preconditions(validation_args, output_dir)
    verify_live_model(client)
    output_format, tier = choose_output_format(client)
    initialize_job_directory(output_dir)
    copied_script = output_dir / "input" / "script.txt"
    shutil.copy2(script_path, copied_script)
    initialization_job = {
        "version": 2,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "workflow": "coherent_full_script_block",
        "status": "initializing_new_reference",
        "model_id": "eleven_v3",
        "script_path": _relative(copied_script, output_dir),
        "finalized": False,
        "rights_attestation": {
            "confirmed": True,
            "confirmed_at": utc_now(),
            "actor": "current_user_confirmed_via_cli",
            "scope": "authorized_new_voice_clone",
            "reference_source_sha256": sha256_file(reference_video),
        },
    }
    _write_job(output_dir, initialization_job)
    try:
        voice_id, profile = create_new_clone(
            client,
            reference_video=reference_video,
            voice_name=voice_name.strip(),
            job_dir=output_dir,
        )
        job, plan, _ = _initialize_prepared_new_reference_state(
            output_dir=output_dir,
            script_path=copied_script,
            script_text=script_text,
            reference_profile=profile,
            reference_source_sha256=sha256_file(reference_video),
            voice_id=voice_id,
            voice_name=voice_name.strip(),
            output_format=output_format,
            subscription_tier=tier,
            delivery_tag=delivery_tag,
            speed=speed,
            stability=stability,
            seed=seed,
        )
        return _run_one_coherent_attempt(
            client=client,
            output_dir=output_dir,
            job=job,
            plan=plan,
            seed=seed,
            stability=stability,
            speed=speed,
        )
    except (WorkflowError, AudioToolError, ApiError, OSError) as exc:
        if (output_dir / "job.json").is_file():
            failed_job = load_json(output_dir / "job.json")
            if not failed_job.get("attempts"):
                failed_job["status"] = "initialization_failed"
            else:
                failed_job["status"] = "coherent_generation_failed_cost_state_unknown"
            failed_job["additional_generation_token"] = None
            failed_job["last_error"] = {
                "created_at": utc_now(),
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            _write_job(output_dir, failed_job)
        raise


def run_existing_voice(
    *,
    script_path: Path,
    output_dir: Path,
    voice_id: str,
    style_reference_video: Path | None,
    consent_confirmed: bool,
    delivery_tag: str | None,
    speed: float,
    stability: float,
    seed: int,
    client: ElevenLabsClient,
    model_id: str = NATURAL_DEFAULT_MODEL_ID,
    pronunciation_dictionary_locators: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Reuse an authorized saved voice for exactly one initial coherent take."""
    script_path = script_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not script_path.is_file():
        raise WorkflowError(f"대본 파일을 찾을 수 없습니다: {script_path}")
    script_text = script_path.read_text(encoding="utf-8").strip()
    validate_korean_only(script_text)
    plan_script(script_text, {"audio_metrics": {}})
    if not 0.7 <= speed <= 1.2:
        raise WorkflowError("전체 테이크 speed는 0.7~1.2 범위여야 합니다.")
    if not 0.0 <= stability <= 1.0:
        raise WorkflowError("전체 테이크 stability는 0~1 범위여야 합니다.")
    if not 0 <= seed < 2**32:
        raise WorkflowError("seed는 0 이상 2^32 미만이어야 합니다.")
    if not voice_id.strip():
        raise WorkflowError("--voice-id는 비어 있을 수 없습니다.")
    if model_id not in {"eleven_v3", "eleven_multilingual_v2"}:
        raise WorkflowError(
            "run-existing 모델은 eleven_v3 또는 eleven_multilingual_v2여야 합니다."
        )
    validation_args = argparse.Namespace(
        target_duration=None,
        consent_confirmed=consent_confirmed,
        reference_video=None,
        new_voice_name=None,
        style_reference_video=style_reference_video,
    )
    validate_run_preconditions(validation_args, output_dir)
    verify_live_model(client, model_id=model_id)
    resolved_voice_id, voice_name = resolve_cloud_voice(
        client,
        voice_id=voice_id.strip(),
        name=None,
    )
    verify_existing_voice(client, voice_id=resolved_voice_id)
    output_format, tier = choose_output_format(client)
    initialize_job_directory(output_dir)
    try:
        profile = profile_for_existing_voice(
            voice_id=resolved_voice_id,
            style_reference_video=(
                style_reference_video.expanduser().resolve()
                if style_reference_video is not None
                else None
            ),
            client=client,
            job_dir=output_dir,
        )
        source_sha256 = str(profile.get("source_sha256") or "").strip()
        if not source_sha256:
            raise WorkflowError(
                "저장된 보이스 프로필에 레퍼런스 SHA-256이 없습니다."
            )
        job, plan, _ = _initialize_prepared_new_reference_state(
            output_dir=output_dir,
            script_path=script_path,
            script_text=script_text,
            reference_profile=profile,
            reference_source_sha256=source_sha256,
            voice_id=resolved_voice_id,
            voice_name=voice_name,
            output_format=output_format,
            subscription_tier=tier,
            delivery_tag=delivery_tag,
            speed=speed,
            stability=stability,
            seed=seed,
            model_id=model_id,
        )
        job["voice_source"] = "authorized_existing_voice_reuse"
        job["rights_attestation"] = {
            "confirmed": True,
            "confirmed_at": utc_now(),
            "actor": "current_user_confirmed_via_cli",
            "scope": "authorized_existing_voice_reuse",
            "reference_source_sha256": source_sha256,
        }
        if pronunciation_dictionary_locators:
            job["pronunciation_dictionary_locators"] = (
                pronunciation_dictionary_locators
            )
            job["pronunciation_dictionary_policy"] = {
                "purpose": "preserve_grapheme_and_enforce_connected_pronunciation",
                "focus_term": "창상피복재",
                "spoken_alias": "창상피복째",
                "no_internal_pause": True,
            }
        preferences_path = Path(
            "~/.codex/state/elevenlabs-reference/"
            "user_preferences.json"
        )
        if preferences_path.is_file():
            preferences = load_json(preferences_path)
            job["persistent_preferences"] = {
                "path": str(preferences_path),
                "sha256": sha256_file(preferences_path),
                "schema_version": preferences.get("schema_version"),
                "delivery_preset": (
                    preferences.get("reference_style_policy", {}).get("preset")
                ),
                "natural_generation_preset": (
                    preferences.get("natural_voice_generation_policy", {}).get(
                        "preset"
                    )
                ),
                "natural_generation_defaults": (
                    preferences.get("natural_voice_generation_policy", {}).get(
                        "defaults",
                        {},
                    )
                ),
                "applied_model_id": model_id,
                "applied_delivery_tag": (
                    job.get("global_delivery", {}).get("tag")
                ),
                "applied_speed": speed,
                "applied_stability": stability,
                "no_split_terms": (
                    preferences.get("pronunciation_policy", {}).get(
                        "no_split_terms",
                        [],
                    )
                ),
                "standing_tts_generation_authorization": (
                    preferences.get(
                        "standing_tts_generation_authorization",
                        {},
                    ).get("confirmed", False)
                ),
                "repeat_generation_approval_prompt": (
                    preferences.get(
                        "standing_tts_generation_authorization",
                        {},
                    ).get("repeat_prompt", True)
                ),
            }
        _write_job(output_dir, job)
        return _run_one_coherent_attempt(
            client=client,
            output_dir=output_dir,
            job=job,
            plan=plan,
            seed=seed,
            stability=stability,
            speed=speed,
        )
    except (WorkflowError, AudioToolError, ApiError, OSError) as exc:
        if (output_dir / "job.json").is_file():
            failed_job = load_json(output_dir / "job.json")
            if not failed_job.get("attempts"):
                failed_job["status"] = "initialization_failed"
            else:
                failed_job["status"] = (
                    "coherent_generation_failed_cost_state_unknown"
                )
            failed_job["additional_generation_token"] = None
            failed_job["last_error"] = {
                "created_at": utc_now(),
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            _write_job(output_dir, failed_job)
        raise


def _run_attempt(
    *,
    client: CoherentClient,
    output_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    request_text: str,
    expected_text: str,
    reference_rate: float,
    attempt_number: int,
    seed: int,
    stability: float,
    speed: float,
    model_id: str,
) -> tuple[dict[str, Any], dict[str, Any], Path, Path]:
    attempt_dir = output_dir / "candidates" / f"take-{attempt_number:03d}"
    attempt_dir.mkdir(parents=True, exist_ok=False)
    attempt_record: dict[str, Any] = {
        "attempt": attempt_number,
        "created_at": utc_now(),
        "status": "reserved_before_tts",
        "seed": seed,
        "stability": stability,
        "speed": speed,
        "model_id": model_id,
        "delivery_tag": job["global_delivery"]["tag"],
        "delivery_tag_applied": model_id == "eleven_v3",
        "voice_settings": {
            "stability": stability,
            "similarity_boost": 0.86,
            "use_speaker_boost": True,
            "style": 0.0 if model_id == "eleven_multilingual_v2" else None,
            "speed": speed,
        },
        "request_text": request_text,
        "scope": "one_tts_response_for_complete_script",
        "pronunciation_dictionary_locators": (
            job.get("pronunciation_dictionary_locators") or None
        ),
        "pronunciation_dictionary_policy": (
            job.get("pronunciation_dictionary_policy") or None
        ),
    }
    job["attempts"].append(attempt_record)
    plan["attempts"].append(attempt_record)
    atomic_write_json(attempt_dir / "attempt.json", attempt_record)
    atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)

    response, headers = client.create_speech_with_timing(
        voice_id=str(job["voice_id"]),
        text=request_text,
        output_format=str(job["api_output_format"]),
        seed=seed,
        stability=stability,
        speed=speed,
        previous_text=None,
        next_text=None,
        pronunciation_dictionary_locators=(
            job.get("pronunciation_dictionary_locators") or None
        ),
        model_id=model_id,
    )
    try:
        audio_bytes = base64.b64decode(
            response["audio_base64"],
            validate=True,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise WorkflowError(
            "전체 테이크 TTS 응답에서 유효한 오디오를 찾지 못했습니다."
        ) from exc
    wav_path, mp3_path = decode_tts_audio(
        audio_bytes,
        output_format=str(job["api_output_format"]),
        destination_dir=attempt_dir,
    )

    transcript_runs: list[dict[str, Any]] = []
    for run_number, (transcript_seed, temperature) in enumerate(
        STT_VARIANTS,
        1,
    ):
        transcript = client.transcribe(
            wav_path,
            seed=transcript_seed,
            temperature=temperature,
        )
        atomic_write_json(
            attempt_dir / f"transcript-{run_number}.json",
            transcript,
        )
        transcript_runs.append(
            _strict_transcript_result(
                expected_text=expected_text,
                transcript=transcript,
                seed=transcript_seed,
                temperature=temperature,
            )
        )

    transcripts_passed = all(run["passed"] for run in transcript_runs)
    if transcripts_passed:
        alignment = client.forced_alignment(wav_path, expected_text)
    else:
        alignment = {
            "characters": [],
            "words": [],
            "loss": None,
            "skipped_reason": "3회 전체 STT 하드 게이트가 먼저 실패함",
        }
    atomic_write_json(attempt_dir / "forced_alignment.json", alignment)
    atomic_write_json(
        attempt_dir / "tts_alignment.json",
        response.get("alignment"),
    )
    atomic_write_json(
        attempt_dir / "tts_normalized_alignment.json",
        response.get("normalized_alignment"),
    )
    metrics = analyze_wav(wav_path, transcript=expected_text)
    duration = metrics.get("duration_seconds")
    candidate_rate = metrics.get("syllables_per_active_second")
    speed_deviation = (
        abs(float(candidate_rate) - reference_rate) / reference_rate
        if isinstance(candidate_rate, (int, float))
        and math.isfinite(float(candidate_rate))
        and candidate_rate > 0
        else None
    )
    alignment_result = _forced_alignment_result(
        expected_text=expected_text,
        alignment=alignment,
        audio_duration_seconds=float(duration or 0.0),
    )
    clipping = metrics.get("clipping_ratio")
    checks = {
        "three_full_stt_runs_exact": transcripts_passed,
        "forced_alignment_complete_and_timed": alignment_result["passed"],
        "duration_at_most_60_seconds": bool(
            isinstance(duration, (int, float))
            and math.isfinite(float(duration))
            and 0 < duration <= MAX_DURATION_SECONDS
        ),
        "reference_speed_within_10_percent": bool(
            speed_deviation is not None and speed_deviation <= 0.10
        ),
        "nonempty_active_audio": bool(
            isinstance(metrics.get("active_speech_seconds"), (int, float))
            and metrics["active_speech_seconds"] > 0
        ),
        "no_material_clipping": bool(
            isinstance(clipping, (int, float)) and clipping <= 0.001
        ),
    }
    request_id = headers.get("request-id") or headers.get("x-request-id")
    attempt_record.update(
        {
            "status": "strict_qc_complete",
            "request_id": request_id,
            "usage_headers": {
                key: headers[key]
                for key in (
                    "character-cost",
                    "x-character-count",
                    "history-item-id",
                )
                if headers.get(key) is not None
            },
            "wav": _relative(wav_path, output_dir),
            "mp3": _relative(mp3_path, output_dir),
            "wav_sha256": sha256_file(wav_path),
            "mp3_sha256": sha256_file(mp3_path),
            "audio_metrics": metrics,
            "reference_rate": reference_rate,
            "speed_deviation_ratio": (
                round(speed_deviation, 6)
                if speed_deviation is not None
                else None
            ),
            "transcript_runs": transcript_runs,
            "forced_alignment": alignment_result,
            "checks": checks,
            "strict_auto_pass": all(checks.values()),
        }
    )
    atomic_write_json(attempt_dir / "qc.json", attempt_record)
    atomic_write_json(attempt_dir / "attempt.json", attempt_record)
    atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)
    return attempt_record, alignment, wav_path, mp3_path


def _select_for_audio_listening(
    *,
    output_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    source_plan: dict[str, Any],
    attempt: dict[str, Any],
    alignment: dict[str, Any],
    wav_path: Path,
    mp3_path: Path,
) -> None:
    previous_revision = int(job.get("review_revision") or 0)
    review_dir = output_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    preview_wav = review_dir / "full_preview.wav"
    preview_mp3 = review_dir / "full_preview.mp3"
    shutil.copy2(wav_path, preview_wav)
    shutil.copy2(mp3_path, preview_mp3)
    if sha256_file(preview_wav) != sha256_file(wav_path):
        raise WorkflowError(
            "전체 테이크 WAV를 review/full_preview.wav로 무변형 보존하지 못했습니다."
        )
    clip_records = _split_review_clips(
        preview_wav=preview_wav,
        alignment=alignment,
        source_plan=source_plan,
        output_dir=output_dir,
    )
    by_index = {record["index"]: record for record in clip_records}
    for segment in plan["segments"]:
        clip = by_index[int(segment["index"])]
        segment.update(
            {
                "status": "derived_clip_awaiting_audio_listening_qc",
                "selected_take": int(attempt["attempt"]),
                "selected_wav": clip["wav"],
                "selected_mp3": clip["mp3"],
                "alignment_interval": {
                    "start_seconds": clip["start_seconds"],
                    "end_seconds": clip["end_seconds"],
                },
                "review_scope": "derived_only_full_take_is_authoritative",
            }
        )
    review_files = [preview_wav, preview_mp3]
    for clip in clip_records:
        review_files.extend(
            (
                output_dir / clip["wav"],
                output_dir / clip["mp3"],
            )
        )
    job.update(
        {
            "status": "awaiting_audio_listening_qc",
            "finalized": False,
            "selected_take": int(attempt["attempt"]),
            "selected_model_id": str(
                attempt.get("model_id") or job.get("model_id") or "eleven_v3"
            ),
            "review_preview_wav": _relative(preview_wav, output_dir),
            "review_preview_mp3": _relative(preview_mp3, output_dir),
            "review_preview_wav_sha256": sha256_file(preview_wav),
            "review_preview_sha256": sha256_file(preview_mp3),
            "review_revision": previous_revision + 1,
            "review_file_hashes": {
                _relative(path, output_dir): sha256_file(path)
                for path in review_files
            },
            "audio_listening_qc": {
                "status": "awaiting_audio_listening_qc",
                "required": True,
                "completed": False,
                "authoritative_audio": _relative(preview_wav, output_dir),
                "note": (
                    "문장 클립은 정렬 기반 검토 보조물이며 최종 판정은 "
                    "무변형 전체 테이크 WAV를 대상으로 해야 합니다."
                ),
            },
            "human_listening_completed": False,
            "user_listening_approval_required": True,
            "additional_generation_token": secrets.token_hex(16),
        }
    )
    for forbidden_key in (
        "final_wav",
        "final_mp3",
        "approval_id",
        "approval_type",
        "prosody_listening_qc_report",
        "prosody_listening_qc_sha256",
        "prosody_objective_flagged_segments",
    ):
        job.pop(forbidden_key, None)
    atomic_write_json(review_dir / "alignment_clip_manifest.json", clip_records)
    atomic_write_json(output_dir / "script_plan.json", plan)
    _write_job(output_dir, job)


def run_coherent_block(
    *,
    source_dir: Path,
    output_dir: Path,
    delivery_tag: str,
    speed: float,
    stability: float,
    base_seed: int,
    attempt_limit: int,
    reason: str,
    client: CoherentClient,
    verify_cloud: bool,
    tts_override_text: str | None = None,
) -> dict[str, Any]:
    source_dir = source_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if source_dir == output_dir:
        raise WorkflowError("원본 작업 폴더와 새 리비전 폴더는 달라야 합니다.")
    if not 0.7 <= speed <= 1.2:
        raise WorkflowError("전체 테이크 speed는 0.7~1.2 범위여야 합니다.")
    if not 0.0 <= stability <= 1.0:
        raise WorkflowError("전체 테이크 stability는 0~1 범위여야 합니다.")
    if not 0 <= base_seed < 2**32:
        raise WorkflowError("seed는 0 이상 2^32 미만이어야 합니다.")
    if not 1 <= attempt_limit <= MAX_ATTEMPTS:
        raise WorkflowError(f"시도 횟수는 1~{MAX_ATTEMPTS}회여야 합니다.")
    delivery_tag = _validate_delivery_tag(delivery_tag)
    source_job, source_plan, reference_profile, source_final_wav = _load_source(
        source_dir
    )
    _validate_empty_destination(output_dir)
    if verify_cloud:
        if not isinstance(client, ElevenLabsClient):
            raise WorkflowError("실제 실행에는 검증 가능한 ElevenLabsClient가 필요합니다.")
        verify_live_model(client)
        verify_existing_voice(client, voice_id=str(source_job["voice_id"]))
    job, plan, request_text = _initial_state(
        source_dir=source_dir,
        source_job=source_job,
        source_plan=source_plan,
        reference_profile=reference_profile,
        source_final_wav=source_final_wav,
        output_dir=output_dir,
        delivery_tag=delivery_tag,
        speed=speed,
        stability=stability,
        seed=base_seed,
        attempt_limit=attempt_limit,
        reason=reason,
        tts_override_text=tts_override_text,
    )
    expected_text = _full_spoken_text(source_plan)
    reference_rate = float(
        reference_profile.get("audio_metrics", reference_profile)[
            "syllables_per_active_second"
        ]
    )

    for attempt_number in range(1, attempt_limit + 1):
        attempt_seed = (base_seed + attempt_number - 1) % (2**32)
        attempt, alignment, wav_path, mp3_path = _run_attempt(
            client=client,
            output_dir=output_dir,
            job=job,
            plan=plan,
            request_text=request_text,
            expected_text=expected_text,
            reference_rate=reference_rate,
            attempt_number=attempt_number,
            seed=attempt_seed,
            stability=stability,
            speed=speed,
            model_id=str(job.get("model_id") or "eleven_v3"),
        )
        if attempt["strict_auto_pass"]:
            _select_for_audio_listening(
                output_dir=output_dir,
                job=job,
                plan=plan,
                source_plan=source_plan,
                attempt=attempt,
                alignment=alignment,
                wav_path=wav_path,
                mp3_path=mp3_path,
            )
            return {
                "status": job["status"],
                "selected_take": job["selected_take"],
                "preview_wav": str(
                    (output_dir / job["review_preview_wav"]).resolve()
                ),
                "preview_mp3": str(
                    (output_dir / job["review_preview_mp3"]).resolve()
                ),
                "segment_review_dir": str(
                    (output_dir / "review" / "segments").resolve()
                ),
                "finalized": False,
            }

    job["status"] = "blocked_after_five_coherent_take_attempts"
    job["finalized"] = False
    job["additional_generation_token"] = secrets.token_hex(16)
    job["audio_listening_qc"] = {
        "status": "blocked_before_audio_listening_qc",
        "required": True,
        "completed": False,
    }
    _write_job(output_dir, job)
    return {
        "status": job["status"],
        "attempt_count": attempt_limit,
        "strict_qc_failures": [
            {
                "attempt": attempt["attempt"],
                "failed_checks": [
                    name
                    for name, passed in attempt.get("checks", {}).items()
                    if not passed
                ],
            }
            for attempt in job["attempts"]
        ],
        "additional_generation_token": job["additional_generation_token"],
        "finalized": False,
    }


def _write_test_wav(path: Path, *, duration_seconds: float = 2.4) -> None:
    sample_rate = 48_000
    time_axis = np.arange(round(sample_rate * duration_seconds)) / sample_rate
    envelope = np.ones_like(time_axis)
    edge_silence = round(sample_rate * 0.30)
    envelope[:edge_silence] = 0.0
    envelope[-edge_silence:] = 0.0
    middle_start = round(sample_rate * 1.10)
    middle_end = round(sample_rate * 1.30)
    envelope[middle_start:middle_end] = 0.0
    fade = round(sample_rate * 0.05)
    envelope[edge_silence : edge_silence + fade] = np.linspace(
        0.0,
        1.0,
        fade,
    )
    envelope[-edge_silence - fade : -edge_silence] = np.linspace(
        1.0,
        0.0,
        fade,
    )
    samples = 0.18 * np.sin(2 * np.pi * 220.0 * time_axis) * envelope
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(sample_rate)
        file.writeframes(
            (np.clip(samples, -1.0, 1.0) * 32767).astype("<i2").tobytes()
        )


def _synthetic_alignment(text: str, duration_seconds: float) -> dict[str, Any]:
    character_duration = duration_seconds / max(len(text), 1)
    return {
        "characters": [
            {
                "text": character,
                "start": index * character_duration,
                "end": (index + 1) * character_duration,
            }
            for index, character in enumerate(text)
        ],
        "words": [],
        "loss": 0.1,
    }


class _OfflineClient:
    def __init__(self, audio_bytes: bytes, expected_text: str):
        self.audio_bytes = audio_bytes
        self.expected_text = expected_text
        self.tts_calls = 0
        self.transcription_calls = 0
        self.alignment_calls = 0

    def create_speech_with_timing(self, **_: Any) -> tuple[dict[str, Any], dict[str, str]]:
        self.tts_calls += 1
        return (
            {
                "audio_base64": base64.b64encode(self.audio_bytes).decode("ascii"),
                "alignment": _synthetic_alignment(self.expected_text, 2.4),
                "normalized_alignment": _synthetic_alignment(
                    self.expected_text,
                    2.4,
                ),
            },
            {"request-id": "offline-self-test"},
        )

    def transcribe(
        self,
        source: Path,
        *,
        detect_speakers: bool = False,
        seed: int = 173,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        del source, detect_speakers, seed, temperature
        self.transcription_calls += 1
        return {"text": self.expected_text, "language_code": "kor"}

    def forced_alignment(self, source: Path, text: str) -> dict[str, Any]:
        del source
        self.alignment_calls += 1
        return _synthetic_alignment(text, 2.4)


class _FailingTranscriptOfflineClient(_OfflineClient):
    def transcribe(
        self,
        source: Path,
        *,
        detect_speakers: bool = False,
        seed: int = 173,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        del source, detect_speakers, seed, temperature
        self.transcription_calls += 1
        return {"text": "전혀 다른 발화입니다.", "language_code": "kor"}


def command_self_test(_: argparse.Namespace) -> int:
    require_binary("ffmpeg")
    require_binary("ffprobe")
    with tempfile.TemporaryDirectory(
        prefix="elevenlabs-coherent-block-test-"
    ) as temporary:
        root = Path(temporary)
        source_dir = root / "source"
        output_dir = root / "revision"
        full_text = "첫 문장을 또렷하게 말해요.\n두 번째 문장도 이어서 말해요."
        segments = full_text.splitlines()
        final_wav = source_dir / "final" / "final.wav"
        _write_test_wav(final_wav)
        _atomic_write_text(source_dir / "input" / "script.txt", full_text + "\n")
        metrics = analyze_wav(final_wav, transcript=full_text)
        atomic_write_json(
            source_dir / "job.json",
            {
                "version": 1,
                "status": "user_approved_final",
                "finalized": True,
                "voice_id": "offline-voice",
                "voice_name": "offline",
                "api_output_format": "wav_48000",
                "script_path": "input/script.txt",
                "final_wav": "final/final.wav",
                "rights_attestation": {"confirmed": True},
            },
        )
        atomic_write_json(
            source_dir / "script_plan.json",
            {
                "version": 1,
                "original_script": full_text,
                "segments": [
                    {
                        "index": index,
                        "source_text": text,
                        "spoken_text": text,
                    }
                    for index, text in enumerate(segments, 1)
                ],
            },
        )
        atomic_write_json(
            source_dir / "reference_profile.json",
            {"audio_metrics": metrics},
        )
        offline_client = _OfflineClient(final_wav.read_bytes(), full_text)
        result = run_coherent_block(
            source_dir=source_dir,
            output_dir=output_dir,
            delivery_tag="conversationally",
            speed=1.0,
            stability=0.5,
            base_seed=100,
            attempt_limit=MAX_ATTEMPTS,
            reason="offline self-test",
            client=offline_client,
            verify_cloud=False,
            tts_override_text=None,
        )
        job = load_json(output_dir / "job.json")
        plan = load_json(output_dir / "script_plan.json")
        preview_wav = output_dir / str(job["review_preview_wav"])
        selected_attempt = job["attempts"][int(job["selected_take"]) - 1]
        candidate_wav = output_dir / str(selected_attempt["wav"])
        assertions = {
            "media_children_receive_no_elevenlabs_or_proxy_secrets": (
                _sanitized_media_environment(
                    {
                        "PATH": "/usr/bin:/bin",
                        "HOME": "/tmp/offline-home",
                        "LANG": "ko_KR.UTF-8",
                        "TMPDIR": "/tmp",
                        "ELEVENLABS_API_KEY": "must-not-leak",
                        "ELEVENLABS_API_BASE": "https://invalid.example",
                        "HTTPS_PROXY": "https://proxy.invalid",
                        "HTTP_PROXY": "http://proxy.invalid",
                        "ALL_PROXY": "socks5://proxy.invalid",
                    }
                )
                == {
                    "PATH": "/usr/bin:/bin",
                    "HOME": "/tmp/offline-home",
                    "LANG": "ko_KR.UTF-8",
                    "TMPDIR": "/tmp",
                }
            ),
            "one_whole_take_tts_call": offline_client.tts_calls == 1,
            "three_strict_stt_calls": offline_client.transcription_calls == 3,
            "one_forced_alignment_call": offline_client.alignment_calls == 1,
            "awaiting_audio_listening_qc": (
                result["status"] == "awaiting_audio_listening_qc"
                and job["status"] == "awaiting_audio_listening_qc"
            ),
            "never_finalized": (
                job["finalized"] is False
                and not (output_dir / "final").exists()
                and not job.get("final_wav")
                and not job.get("final_mp3")
            ),
            "whole_take_wav_byte_preserved": (
                sha256_file(preview_wav) == sha256_file(candidate_wav)
            ),
            "alignment_derived_clips_exist": all(
                (output_dir / str(segment["selected_wav"])).is_file()
                and (output_dir / str(segment["selected_mp3"])).is_file()
                for segment in plan["segments"]
            ),
        }

        # Exercise the canonical new-reference state directly.  Cloud isolation
        # and cloning are intentionally outside an offline test; everything from
        # the prepared authorized clone through the one-request cost boundary is
        # covered here.
        new_script_path = root / "new-script.txt"
        _atomic_write_text(new_script_path, full_text + "\n")
        new_output = root / "new-reference-job"
        initialize_job_directory(new_output)
        new_job, new_plan, _ = _initialize_prepared_new_reference_state(
            output_dir=new_output,
            script_path=new_script_path,
            script_text=full_text,
            reference_profile={"audio_metrics": metrics},
            reference_source_sha256=sha256_file(final_wav),
            voice_id="offline-new-voice",
            voice_name="offline-new",
            output_format="wav_48000",
            subscription_tier="offline",
            delivery_tag=None,
            speed=1.0,
            stability=0.5,
            seed=300,
        )
        new_expected_text = str(new_plan["full_spoken_text"])
        new_client = _OfflineClient(final_wav.read_bytes(), new_expected_text)
        new_result = _run_one_coherent_attempt(
            client=new_client,
            output_dir=new_output,
            job=new_job,
            plan=new_plan,
            seed=300,
            stability=0.5,
            speed=1.0,
        )
        new_job = load_json(new_output / "job.json")
        new_plan = load_json(new_output / "script_plan.json")
        assertions.update(
            {
                "new_reference_initial_batch_exactly_one_tts": (
                    new_client.tts_calls == 1
                    and new_result["attempt_count"] == 1
                    and new_job["initial_batch_tts_request_limit"] == 1
                    and new_job["duration_preflight"]["passed"] is True
                ),
                "new_reference_stops_before_listening_approval": (
                    new_job["status"] == "awaiting_audio_listening_qc"
                    and new_job["finalized"] is False
                    and not (new_output / "final").exists()
                ),
            }
        )

        # A script whose conservative upper estimate exceeds 60 seconds must
        # persist its evidence and stop before create_speech_with_timing.
        overlong_text = ("가" * 1000) + "."
        overlong_script_path = root / "overlong-script.txt"
        _atomic_write_text(overlong_script_path, overlong_text + "\n")
        duration_blocked_output = root / "duration-blocked-job"
        initialize_job_directory(duration_blocked_output)
        duration_blocked_job, duration_blocked_plan, _ = (
            _initialize_prepared_new_reference_state(
                output_dir=duration_blocked_output,
                script_path=overlong_script_path,
                script_text=overlong_text,
                reference_profile={
                    "audio_metrics": {
                        "syllables_per_active_second": 4.0,
                        "pitch_range_semitones": 5.0,
                    }
                },
                reference_source_sha256=sha256_file(final_wav),
                voice_id="offline-duration-blocked-voice",
                voice_name="offline-duration-blocked",
                output_format="wav_48000",
                subscription_tier="offline",
                delivery_tag="conversationally",
                speed=1.0,
                stability=0.5,
                seed=350,
            )
        )
        duration_blocked_client = _OfflineClient(
            final_wav.read_bytes(),
            str(duration_blocked_plan["full_spoken_text"]),
        )
        duration_blocked_result = _run_one_coherent_attempt(
            client=duration_blocked_client,
            output_dir=duration_blocked_output,
            job=duration_blocked_job,
            plan=duration_blocked_plan,
            seed=350,
            stability=0.5,
            speed=1.0,
        )
        duration_blocked_job = load_json(
            duration_blocked_output / "job.json"
        )
        duration_evidence_path = duration_blocked_output / str(
            duration_blocked_job["duration_preflight_report"]
        )
        assertions.update(
            {
                "over_60s_estimate_blocks_before_paid_tts": (
                    duration_blocked_result["status"] == "blocked_before_tts"
                    and duration_blocked_job["status"] == "blocked_before_tts"
                    and duration_blocked_client.tts_calls == 0
                    and duration_blocked_client.transcription_calls == 0
                    and duration_blocked_client.alignment_calls == 0
                    and duration_blocked_job["attempts"] == []
                ),
                "duration_block_persists_verifiable_evidence": (
                    duration_evidence_path.is_file()
                    and duration_blocked_job["duration_preflight"]["passed"]
                    is False
                    and duration_blocked_job["duration_preflight"][
                        "estimated_upper_seconds"
                    ]
                    > MAX_DURATION_SECONDS
                    and duration_blocked_job["duration_preflight_sha256"]
                    == sha256_file(duration_evidence_path)
                ),
            }
        )

        # A failed initial whole take must not trigger an automatic second
        # billable call.  It emits a one-use token and skips alignment because
        # the three STT hard gates failed first.
        blocked_output = root / "blocked-new-reference-job"
        initialize_job_directory(blocked_output)
        blocked_job, blocked_plan, _ = _initialize_prepared_new_reference_state(
            output_dir=blocked_output,
            script_path=new_script_path,
            script_text=full_text,
            reference_profile={"audio_metrics": metrics},
            reference_source_sha256=sha256_file(final_wav),
            voice_id="offline-blocked-voice",
            voice_name="offline-blocked",
            output_format="wav_48000",
            subscription_tier="offline",
            delivery_tag="conversationally",
            speed=1.0,
            stability=0.5,
            seed=400,
        )
        failing_client = _FailingTranscriptOfflineClient(
            final_wav.read_bytes(),
            str(blocked_plan["full_spoken_text"]),
        )
        blocked_result = _run_one_coherent_attempt(
            client=failing_client,
            output_dir=blocked_output,
            job=blocked_job,
            plan=blocked_plan,
            seed=400,
            stability=0.5,
            speed=1.0,
        )
        missing_cost_rejected = False
        wrong_token_rejected = False
        retry_args = argparse.Namespace(
            job_dir=blocked_output,
            approval_token="not-the-current-token",
            feedback="offline gate test",
            additional_cost_approved=False,
        )
        try:
            command_retry(retry_args)
        except WorkflowError:
            missing_cost_rejected = True
        retry_args.additional_cost_approved = True
        try:
            command_retry(retry_args)
        except WorkflowError:
            wrong_token_rejected = True
        assertions.update(
            {
                "failed_initial_take_never_auto_retries": (
                    failing_client.tts_calls == 1
                    and blocked_result["attempt_count"] == 1
                    and blocked_result["status"]
                    == "coherent_retry_approval_required"
                    and bool(blocked_result["additional_generation_token"])
                ),
                "failed_stt_skips_forced_alignment": (
                    failing_client.transcription_calls == 3
                    and failing_client.alignment_calls == 0
                ),
                "retry_requires_explicit_cost_flag": missing_cost_rejected,
                "retry_requires_current_one_time_token": wrong_token_rejected,
            }
        )

        # Approval must fail closed without three real-audio judge runs, then
        # preserve the authoritative preview bytes after a complete report.
        preview_wav = new_output / str(new_job["review_preview_wav"])
        preview_mp3 = new_output / str(new_job["review_preview_mp3"])
        reference_hash = sha256_file(final_wav)
        report_path = new_output / "review" / "prosody-listening-qc.json"
        report_segments = [
            {
                "index": int(segment["index"]),
                "selected_take": segment["selected_take"],
                "features": {
                    "sha256": sha256_file(
                        new_output / str(segment["selected_wav"])
                    )
                },
                "objective_qc": {"passed": True},
            }
            for segment in new_plan["segments"]
        ]
        base_report = {
            "reference": {
                "path": str(final_wav.resolve()),
                "sha256": reference_hash,
            },
            "preview": {
                "path": str(preview_wav.resolve()),
                "sha256": sha256_file(preview_wav),
                "review_revision": new_job["review_revision"],
            },
            "segments": report_segments,
            "objective_qc": {"passed": True, "flagged_segments": []},
            "audio_listening_qc": {
                "status": "blocked_unavailable",
                "passed": False,
                "runs": [],
            },
            "strict_qc": {"passed": False},
        }
        atomic_write_json(report_path, base_report)
        new_job["prosody_listening_qc_report"] = _relative(
            report_path,
            new_output,
        )
        new_job["prosody_listening_qc_sha256"] = sha256_file(report_path)
        _write_job(new_output, new_job)
        fail_closed = False
        try:
            validate_current_prosody_qc(new_output, new_job, new_plan)
        except WorkflowError:
            fail_closed = True

        passing_report = dict(base_report)
        passing_report["audio_listening_qc"] = {
            "status": "passed",
            "passed": True,
            "evaluator": "offline-coherent-self-test-evaluator",
            "runs": [
                {
                    "settings_id": f"offline-audio-judge-{index}",
                    "model": "offline-coherent-self-test-model",
                    "all_passed": True,
                    "segments": [
                        {
                            "index": int(segment["index"]),
                            "spoken_text": str(
                                segment.get("spoken_text") or ""
                            ),
                            "pronunciation_pass": True,
                            "tone_pass": True,
                            "intonation_pass": True,
                            "emotion_pass": True,
                            "speaker_character_pass": True,
                            "boundary_continuity_pass": True,
                            "no_synthesis_artifact_pass": True,
                        }
                        for segment in new_plan["segments"]
                    ],
                }
                for index in range(1, 4)
            ],
        }
        passing_report["strict_qc"] = {"passed": True}
        atomic_write_json(report_path, passing_report)
        new_job["prosody_listening_qc_sha256"] = sha256_file(report_path)
        new_job["status"] = "awaiting_user_listening_approval"
        for segment in new_plan["segments"]:
            segment["status"] = "coherent_auto_passed_awaiting_user"
        atomic_write_json(new_output / "script_plan.json", new_plan)
        _write_job(new_output, new_job)
        approval_args = argparse.Namespace(
            job_dir=new_output,
            segments="all",
            confirmation=LISTENING_APPROVAL_CONFIRMATION,
            preview_sha256=sha256_file(preview_mp3),
        )
        with contextlib.redirect_stdout(io.StringIO()):
            _command_approve_locked(approval_args, new_output)
        finalized_job = load_json(new_output / "job.json")
        final_wav_path = new_output / str(finalized_job["final_wav"])
        final_report = load_json(new_output / "final" / "qc_report.json")
        assertions.update(
            {
                "approval_fails_closed_without_three_audio_runs": fail_closed,
                "coherent_final_wav_is_authoritative_preview": (
                    sha256_file(final_wav_path) == sha256_file(preview_wav)
                    and final_report["authoritative_final_source"]
                    == "review/full_preview.wav_byte_preserved"
                ),
                "coherent_human_approval_finalizes_only_after_strict_qc": (
                    finalized_job["status"] == "user_approved_final"
                    and finalized_job["human_listening_completed"] is True
                    and final_report["coherent_take_qc"]["transcript_run_count"]
                    == 3
                ),
            }
        )
        if not all(assertions.values()):
            raise WorkflowError(
                "coherent-block self-test 실패: "
                + json.dumps(assertions, ensure_ascii=False)
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "network_used": False,
                    "assertions": assertions,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def command_run(args: argparse.Namespace) -> int:
    if not args.additional_cost_approved and not _standing_tts_generation_authorized():
        raise WorkflowError(
            "최대 5회 전체 대본 TTS 비용을 승인한 경우에만 "
            "--additional-cost-approved를 사용하세요."
        )
    client = ElevenLabsClient()
    result = run_coherent_block(
        source_dir=args.source_job,
        output_dir=args.output_dir,
        delivery_tag=args.delivery_tag,
        speed=args.speed,
        stability=args.stability,
        base_seed=args.seed,
        attempt_limit=args.attempts,
        reason=args.reason.strip(),
        client=client,
        verify_cloud=True,
        tts_override_text=(
            args.tts_override_script.expanduser().resolve().read_text(
                encoding="utf-8"
            )
            if args.tts_override_script
            else None
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "awaiting_audio_listening_qc" else 2


def command_run_new(args: argparse.Namespace) -> int:
    client = ElevenLabsClient()
    result = run_new_reference(
        script_path=args.script,
        output_dir=args.output_dir,
        reference_video=args.reference_video,
        voice_name=args.new_voice_name,
        consent_confirmed=args.consent_confirmed,
        delivery_tag=args.delivery_tag,
        speed=args.speed,
        stability=args.stability,
        seed=args.seed,
        client=client,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "awaiting_audio_listening_qc" else 2


def command_run_existing(args: argparse.Namespace) -> int:
    client = ElevenLabsClient()
    dictionary_id = str(
        getattr(args, "pronunciation_dictionary_id", "") or ""
    ).strip()
    dictionary_version_id = str(
        getattr(args, "pronunciation_dictionary_version_id", "") or ""
    ).strip()
    if bool(dictionary_id) != bool(dictionary_version_id):
        raise WorkflowError("발음 사전 ID와 버전 ID는 함께 지정해야 합니다.")
    result = run_existing_voice(
        script_path=args.script,
        output_dir=args.output_dir,
        voice_id=args.voice_id,
        style_reference_video=args.style_reference_video,
        consent_confirmed=args.consent_confirmed,
        delivery_tag=args.delivery_tag,
        speed=args.speed,
        stability=args.stability,
        seed=args.seed,
        client=client,
        model_id=args.model_id,
        pronunciation_dictionary_locators=(
            [
                {
                    "pronunciation_dictionary_id": dictionary_id,
                    "version_id": dictionary_version_id,
                }
            ]
            if dictionary_id
            else None
        ),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "awaiting_audio_listening_qc" else 2


def _retry_parameters(
    job_dir: Path,
    job: dict[str, Any],
) -> tuple[int, float, float]:
    attempts = list(job.get("attempts") or [])
    if not attempts:
        raise WorkflowError("재시도 기준이 될 전체 테이크 기록이 없습니다.")
    previous = attempts[-1]
    attempt_number = len(attempts) + 1
    previous_seed = int(previous.get("seed") or 0)
    seed = (previous_seed + 1) % (2**32)
    stability_schedule = (0.50, 0.42, 0.58, 0.35, 0.66)
    stability = stability_schedule[(attempt_number - 1) % len(stability_schedule)]
    previous_speed = float(previous.get("speed") or 1.0)
    candidate_rate = (previous.get("audio_metrics") or {}).get(
        "syllables_per_active_second"
    )
    profile = load_json(job_dir / "reference_profile.json")
    reference_rate = profile.get("audio_metrics", profile).get(
        "syllables_per_active_second"
    )
    speed = previous_speed
    if (
        isinstance(candidate_rate, (int, float))
        and float(candidate_rate) > 0
        and isinstance(reference_rate, (int, float))
        and float(reference_rate) > 0
    ):
        speed = previous_speed * float(reference_rate) / float(candidate_rate)
    return seed, stability, round(min(1.2, max(0.7, speed)), 4)


def command_retry(args: argparse.Namespace) -> int:
    standing_authorization = _standing_tts_generation_authorized()
    if not args.additional_cost_approved and not standing_authorization:
        raise WorkflowError(
            "전체 대본 TTS 1회 추가 비용을 승인한 경우에만 "
            "--additional-cost-approved를 사용하세요."
        )
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        plan = load_json(job_dir / "script_plan.json")
        dictionary_id = (
            str(getattr(args, "pronunciation_dictionary_id", "") or "").strip()
        )
        dictionary_version_id = str(
            getattr(args, "pronunciation_dictionary_version_id", "") or ""
        ).strip()
        dictionary_term = str(
            getattr(args, "pronunciation_dictionary_term", "") or ""
        ).strip()
        dictionary_alias = str(
            getattr(args, "pronunciation_dictionary_alias", "") or ""
        ).strip()
        if bool(dictionary_id) != bool(dictionary_version_id):
            raise WorkflowError(
                "발음 사전 ID와 버전 ID는 함께 지정해야 합니다."
            )
        if bool(dictionary_term) != bool(dictionary_alias):
            raise WorkflowError(
                "발음 사전 원문과 발음 별칭은 함께 지정해야 합니다."
            )
        if (dictionary_term or dictionary_alias) and not dictionary_id:
            raise WorkflowError(
                "발음 사전 원문·별칭을 기록하려면 사전 ID와 버전 ID도 필요합니다."
            )
        if dictionary_id:
            job["pronunciation_dictionary_locators"] = [
                {
                    "pronunciation_dictionary_id": dictionary_id,
                    "version_id": dictionary_version_id,
                }
            ]
            job["pronunciation_dictionary_policy"] = {
                "purpose": "preserve_grapheme_and_enforce_connected_pronunciation",
                "focus_term": dictionary_term or "unspecified",
                "spoken_alias": dictionary_alias or "unspecified",
                "no_internal_pause": True,
            }
        else:
            previous_locators = job.pop(
                "pronunciation_dictionary_locators",
                None,
            )
            previous_policy = job.pop(
                "pronunciation_dictionary_policy",
                None,
            )
            if previous_locators and job.get("attempts"):
                job["attempts"][-1].setdefault(
                    "pronunciation_dictionary_locators",
                    previous_locators,
                )
                job["attempts"][-1].setdefault(
                    "pronunciation_dictionary_policy",
                    previous_policy,
                )
        tts_override_text: str | None = None
        tts_override_script = getattr(args, "tts_override_script", None)
        if tts_override_script:
            override_path = tts_override_script.expanduser().resolve()
            tts_override_text = override_path.read_text(encoding="utf-8").strip()
            expected_text = str(
                plan.get("full_spoken_text") or _full_spoken_text(plan)
            ).strip()
            if not normalize_for_comparison(tts_override_text):
                raise WorkflowError("발음 유도용 전체 대본에 한글 발화가 없습니다.")
            if normalize_for_comparison(
                tts_override_text
            ) != normalize_for_comparison(expected_text):
                raise WorkflowError(
                    "retry 발음 유도문은 공백·문장부호만 조정할 수 있으며 "
                    "원래 발화문과 동일한 한글 어휘를 유지해야 합니다."
                )
        if job.get("workflow") != "coherent_full_script_block":
            raise WorkflowError("retry는 coherent 전체 테이크 작업에만 사용할 수 있습니다.")
        if job.get("finalized"):
            raise WorkflowError("이미 최종 승인된 작업은 재생성하지 않습니다.")
        if job.get("status") not in {
            "coherent_retry_approval_required",
            "prosody_regeneration_required",
            "awaiting_audio_listening_qc",
            "awaiting_user_listening_approval",
        }:
            raise WorkflowError(
                "현재 coherent 작업 상태에서는 재시도할 수 없습니다. status를 확인하세요."
            )
        if len(job.get("attempts") or []) >= MAX_ATTEMPTS:
            raise WorkflowError("전체 테이크 최대 5회 시도를 이미 사용했습니다.")
        expected_token = str(job.get("additional_generation_token") or "")
        provided_token = str(getattr(args, "approval_token", "") or "").strip()
        if standing_authorization and not provided_token:
            provided_token = expected_token
        if not expected_token or provided_token != expected_token:
            raise WorkflowError(
                "현재 작업의 일회용 내부 재시도 상태 토큰이 아닙니다."
            )
        previous_delivery_tag = _validate_delivery_tag(
            str((job.get("global_delivery") or {}).get("tag") or "")
        )
        previous_model_id = str(
            job.get("active_model_id") or job.get("model_id") or "eleven_v3"
        )
        for previous_attempt in job.get("attempts") or []:
            previous_attempt.setdefault("model_id", previous_model_id)
        for previous_attempt in plan.get("attempts") or []:
            previous_attempt.setdefault("model_id", previous_model_id)
        requested_model_id = str(
            getattr(args, "model_id", None) or previous_model_id
        ).strip()
        if requested_model_id not in {
            "eleven_v3",
            "eleven_multilingual_v2",
        }:
            raise WorkflowError(
                "retry 모델은 eleven_v3 또는 eleven_multilingual_v2여야 합니다."
            )
        requested_delivery_tag = getattr(args, "delivery_tag", None)
        delivery_tag = _validate_delivery_tag(
            requested_delivery_tag or previous_delivery_tag
        )
        client = ElevenLabsClient()
        verify_live_model(client, model_id=requested_model_id)
        verify_existing_voice(client, voice_id=str(job["voice_id"]))
        seed, stability, speed = _retry_parameters(job_dir, job)
        requested_seed = getattr(args, "seed", None)
        if requested_seed is not None:
            if not 0 <= int(requested_seed) <= (2**32 - 1):
                raise WorkflowError("retry seed는 0~4294967295 범위여야 합니다.")
            previous_seed = seed
            seed = int(requested_seed)
            job.setdefault("parameter_override_history", []).append(
                {
                    "created_at": utc_now(),
                    "attempt": len(job.get("attempts") or []) + 1,
                    "parameter": "seed",
                    "automatic_value": previous_seed,
                    "override_value": seed,
                    "reason": args.feedback.strip(),
                }
            )
        requested_speed = getattr(args, "speed", None)
        if requested_speed is not None:
            if not 0.7 <= float(requested_speed) <= 1.2:
                raise WorkflowError("retry speed는 0.7~1.2 범위여야 합니다.")
            previous_speed = speed
            speed = float(requested_speed)
            job.setdefault("parameter_override_history", []).append(
                {
                    "created_at": utc_now(),
                    "attempt": len(job.get("attempts") or []) + 1,
                    "parameter": "speed",
                    "automatic_value": previous_speed,
                    "override_value": speed,
                    "reason": args.feedback.strip(),
                }
            )
        requested_stability = getattr(args, "stability", None)
        if requested_stability is not None:
            if not 0.0 <= float(requested_stability) <= 1.0:
                raise WorkflowError("retry stability는 0~1 범위여야 합니다.")
            previous_stability = stability
            stability = float(requested_stability)
            job.setdefault("parameter_override_history", []).append(
                {
                    "created_at": utc_now(),
                    "attempt": len(job.get("attempts") or []) + 1,
                    "parameter": "stability",
                    "automatic_value": previous_stability,
                    "override_value": stability,
                    "reason": args.feedback.strip(),
                }
            )
        generation_text = (
            tts_override_text
            or str((job.get("tts_override") or {}).get("text") or "").strip()
            or str(plan.get("full_spoken_text") or _full_spoken_text(plan)).strip()
        )
        plan["global_tts_text"] = _request_text_for_model(
            model_id=requested_model_id,
            delivery_tag=delivery_tag,
            generation_text=generation_text,
        )
        job.setdefault("global_delivery", {})["tag"] = delivery_tag
        plan.setdefault("global_delivery", {})["tag"] = delivery_tag
        job["active_model_id"] = requested_model_id
        plan["active_model_id"] = requested_model_id
        if requested_model_id != previous_model_id:
            job.setdefault("model_override_history", []).append(
                {
                    "created_at": utc_now(),
                    "attempt": len(job.get("attempts") or []) + 1,
                    "previous_model_id": previous_model_id,
                    "new_model_id": requested_model_id,
                    "reason": args.feedback.strip(),
                    "scope": "single_whole_script_retry",
                }
            )
        if delivery_tag != previous_delivery_tag:
            job.setdefault("delivery_override_history", []).append(
                {
                    "created_at": utc_now(),
                    "attempt": len(job.get("attempts") or []) + 1,
                    "previous_tag": previous_delivery_tag,
                    "new_tag": delivery_tag,
                    "reason": args.feedback.strip(),
                }
            )
        if tts_override_text is not None:
            job["tts_override"] = {
                "used": True,
                "text": tts_override_text,
                "sha256": hashlib.sha256(
                    tts_override_text.encode("utf-8")
                ).hexdigest(),
                "source_path": str(tts_override_script.expanduser().resolve()),
                "applied_for_attempt": len(job.get("attempts") or []) + 1,
                "note": (
                    "생성 유도문은 공백·문장부호만 조정했으며 STT와 "
                    "Forced Alignment는 원래 발화문을 기준으로 수행한다."
                ),
            }

        approval_record = {
            "created_at": utc_now(),
            "token_sha256": hashlib.sha256(
                expected_token.encode("utf-8")
            ).hexdigest(),
            "requests_approved": 1,
            "attempt": len(job.get("attempts") or []) + 1,
            "feedback": args.feedback.strip(),
            "model_id": requested_model_id,
            "authorization_type": (
                "standing_user_authorization"
                if standing_authorization
                else "legacy_per_call_authorization"
            ),
        }
        job.setdefault("additional_generation_approvals", []).append(
            approval_record
        )
        job["additional_generation_token"] = None
        job["additional_generation_scope"] = None
        job["status"] = "generating_approved_coherent_retry"
        for key in (
            "review_preview_wav",
            "review_preview_mp3",
            "review_preview_wav_sha256",
            "review_preview_sha256",
            "review_file_hashes",
            "prosody_listening_qc_report",
            "prosody_listening_qc_sha256",
            "prosody_objective_flagged_segments",
            "approval_id",
            "approval_type",
        ):
            job.pop(key, None)
        for segment in plan["segments"]:
            segment["status"] = "pending_coherent_take"
            for key in (
                "selected_take",
                "selected_wav",
                "selected_mp3",
                "alignment_interval",
            ):
                segment.pop(key, None)
        atomic_write_json(job_dir / "script_plan.json", plan)
        _write_job(job_dir, job)
        try:
            result = _run_one_coherent_attempt(
                client=client,
                output_dir=job_dir,
                job=job,
                plan=plan,
                seed=seed,
                stability=stability,
                speed=speed,
            )
        except (WorkflowError, AudioToolError, ApiError, OSError) as exc:
            current = load_json(job_dir / "job.json")
            current["status"] = "coherent_retry_failed_cost_state_unknown"
            current["additional_generation_token"] = None
            current["last_error"] = {
                "created_at": utc_now(),
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            _write_job(job_dir, current)
            raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "awaiting_audio_listening_qc" else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "새 권한 확인 레퍼런스 또는 완료된 ElevenLabs 작업에서 "
            "60초 이하 전체 대본 coherent take를 만듭니다."
        )
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser(
        "run",
        help="비어 있는 새 리비전 폴더에 전체 테이크를 생성합니다.",
    )
    run_parser.add_argument("--source-job", type=Path, required=True)
    run_parser.add_argument("--output-dir", type=Path, required=True)
    run_parser.add_argument(
        "--delivery-tag",
        default=NATURAL_DEFAULT_DELIVERY_TAG,
        help="기본값: conversationally",
    )
    run_parser.add_argument(
        "--speed",
        type=float,
        default=NATURAL_DEFAULT_SPEED,
    )
    run_parser.add_argument(
        "--stability",
        type=float,
        default=NATURAL_DEFAULT_STABILITY,
    )
    run_parser.add_argument("--seed", type=int, default=173)
    run_parser.add_argument("--attempts", type=int, default=MAX_ATTEMPTS)
    run_parser.add_argument("--reason", required=True)
    run_parser.add_argument(
        "--tts-override-script",
        type=Path,
        help=(
            "발음 유도용 전체 한국어 대본. 생성에만 사용하고 검수는 "
            "원래 source job 발화문을 기준으로 수행합니다."
        ),
    )
    run_parser.add_argument(
        "--additional-cost-approved",
        action="store_true",
        help=(
            "지속 설정이 없는 환경의 레거시 건별 허용 플래그. 현재 로컬 "
            "사용자의 상시 생성 허용에서는 생략할 수 있습니다."
        ),
    )
    run_parser.set_defaults(handler=command_run)
    run_new_parser = subparsers.add_parser(
        "run-new",
        help=(
            "새 권한 확인 레퍼런스를 복제하고 전체 대본 TTS를 정확히 1회 "
            "생성합니다."
        ),
    )
    run_new_parser.add_argument("--script", type=Path, required=True)
    run_new_parser.add_argument("--output-dir", type=Path, required=True)
    run_new_parser.add_argument("--reference-video", type=Path, required=True)
    run_new_parser.add_argument("--new-voice-name", required=True)
    run_new_parser.add_argument("--consent-confirmed", action="store_true")
    run_new_parser.add_argument(
        "--delivery-tag",
        default=NATURAL_DEFAULT_DELIVERY_TAG,
        help="전체 테이크에 적용할 단일 전달 태그. 기본값: conversationally",
    )
    run_new_parser.add_argument(
        "--speed",
        type=float,
        default=NATURAL_DEFAULT_SPEED,
    )
    run_new_parser.add_argument(
        "--stability",
        type=float,
        default=NATURAL_DEFAULT_STABILITY,
    )
    run_new_parser.add_argument("--seed", type=int, default=173)
    run_new_parser.set_defaults(handler=command_run_new)
    run_existing_parser = subparsers.add_parser(
        "run-existing",
        help=(
            "저장된 권한 확인 보이스를 재사용해 전체 대본 TTS를 정확히 "
            "1회 생성합니다."
        ),
    )
    run_existing_parser.add_argument("--script", type=Path, required=True)
    run_existing_parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    run_existing_parser.add_argument("--voice-id", required=True)
    run_existing_parser.add_argument(
        "--style-reference-video",
        type=Path,
        help=(
            "로컬 프로필이 없는 기존 보이스의 속도·감정 기준 영상"
        ),
    )
    run_existing_parser.add_argument(
        "--consent-confirmed",
        action="store_true",
    )
    run_existing_parser.add_argument(
        "--delivery-tag",
        default=NATURAL_DEFAULT_DELIVERY_TAG,
        help="전체 테이크에 적용할 단일 전달 태그. 기본값: conversationally",
    )
    run_existing_parser.add_argument(
        "--speed",
        type=float,
        default=NATURAL_DEFAULT_SPEED,
    )
    run_existing_parser.add_argument(
        "--stability",
        type=float,
        default=NATURAL_DEFAULT_STABILITY,
    )
    run_existing_parser.add_argument("--seed", type=int, default=173)
    run_existing_parser.add_argument(
        "--model-id",
        choices=("eleven_v3", "eleven_multilingual_v2"),
        default=NATURAL_DEFAULT_MODEL_ID,
    )
    run_existing_parser.add_argument(
        "--pronunciation-dictionary-id",
        help="초기 전체 take에 적용할 ElevenLabs 발음 사전 ID",
    )
    run_existing_parser.add_argument(
        "--pronunciation-dictionary-version-id",
        help="초기 전체 take에 적용할 ElevenLabs 발음 사전 버전 ID",
    )
    run_existing_parser.set_defaults(handler=command_run_existing)
    retry_parser = subparsers.add_parser(
        "retry",
        help="현재 일회용 토큰으로 전체 대본 TTS를 정확히 1회 추가 생성합니다.",
    )
    retry_parser.add_argument("--job-dir", type=Path, required=True)
    retry_parser.add_argument(
        "--approval-token",
        help=(
            "내부 재시도 상태 토큰. 지속 설정의 상시 생성 허용이 활성화되면 "
            "생략할 수 있습니다."
        ),
    )
    retry_parser.add_argument("--feedback", required=True)
    retry_parser.add_argument(
        "--delivery-tag",
        help=(
            "이번 전체 재시도에 적용할 단일 전달 태그. 생략하면 직전 태그를 "
            "유지합니다."
        ),
    )
    retry_parser.add_argument(
        "--model-id",
        choices=("eleven_v3", "eleven_multilingual_v2"),
        help=(
            "이번 전체 재시도에 사용할 TTS 모델. Multilingual v2에서는 "
            "v3 전용 대괄호 오디오 태그를 요청문에서 제거합니다."
        ),
    )
    retry_parser.add_argument(
        "--stability",
        type=float,
        help=(
            "이번 전체 재시도의 stability를 0~1 범위에서 명시합니다. "
            "생략하면 기록된 재시도 스케줄을 사용합니다."
        ),
    )
    retry_parser.add_argument(
        "--seed",
        type=int,
        help=(
            "이번 전체 재시도의 seed를 명시합니다. 생략하면 직전 seed 다음 값을 "
            "사용합니다."
        ),
    )
    retry_parser.add_argument(
        "--speed",
        type=float,
        help=(
            "이번 전체 재시도의 API speed를 0.7~1.2 범위에서 명시합니다. "
            "생략하면 기록된 발화율 기반 재시도 값을 사용합니다."
        ),
    )
    retry_parser.add_argument(
        "--tts-override-script",
        type=Path,
        help=(
            "발음 유도용 전체 한국어 대본. 원래 발화문과 같은 한글 "
            "어휘를 유지한 채 공백·문장부호만 조정할 수 있습니다."
        ),
    )
    retry_parser.add_argument(
        "--pronunciation-dictionary-id",
        help="현재 재시도에 적용할 ElevenLabs 발음 사전 ID",
    )
    retry_parser.add_argument(
        "--pronunciation-dictionary-version-id",
        help="현재 재시도에 적용할 ElevenLabs 발음 사전 버전 ID",
    )
    retry_parser.add_argument(
        "--pronunciation-dictionary-term",
        help="작업 기록에 보존할 발음 사전 원문",
    )
    retry_parser.add_argument(
        "--pronunciation-dictionary-alias",
        help="작업 기록에 보존할 발음 사전 발음 별칭",
    )
    retry_parser.add_argument(
        "--additional-cost-approved",
        action="store_true",
        help=(
            "지속 설정이 없는 환경의 레거시 건별 허용 플래그. 현재 로컬 "
            "사용자의 상시 생성 허용에서는 생략할 수 있습니다."
        ),
    )
    retry_parser.set_defaults(handler=command_retry)
    test_parser = subparsers.add_parser(
        "self-test",
        help="네트워크 없이 전체 테이크 불변조건을 검사합니다.",
    )
    test_parser.set_defaults(handler=command_self_test)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except KeyboardInterrupt:
        print(
            json.dumps(
                {
                    "error": "KeyboardInterrupt",
                    "message": (
                        "전체 테이크 생성이 중단되었습니다. 비용 중복을 막기 위해 "
                        "비어 있는 새 리비전 폴더에서 다시 시작하세요."
                    ),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 130
    except (WorkflowError, AudioToolError, ApiError, OSError) as exc:
        print(
            json.dumps(
                {
                    "error": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

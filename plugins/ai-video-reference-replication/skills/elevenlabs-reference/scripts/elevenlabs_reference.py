#!/usr/bin/env python3
"""Authorized reference-voice cloning and strict Korean TTS review workflow."""

from __future__ import annotations

import argparse
import base64
import contextlib
import fcntl
import hashlib
import json
import math
import mimetypes
import os
import re
import secrets
import shutil
import sys
import time
import wave
from pathlib import Path
from typing import Any

import numpy as np

try:
    import requests
except ImportError as exc:  # pragma: no cover - doctor reports this more cleanly
    raise SystemExit("requests 패키지가 필요합니다: python3 -m pip install requests") from exc

from audio_tools import (
    AudioToolError,
    analyze_wav,
    canonical_pcm_fingerprint,
    concatenate_wavs,
    convert_raw_pcm_to_wav,
    convert_to_wav,
    extract_wav_interval,
    probe_media,
    require_binary,
    trim_edge_silence,
    wav_to_mp3,
)
from workflow_core import (
    KOREAN_DIRECTION_TAGS,
    WorkflowError,
    atomic_write_json,
    load_json,
    normalize_for_comparison,
    normalize_lexical_content,
    plan_script,
    reference_quality,
    score_candidate,
    sha256_file,
    utc_now,
    validate_korean_only,
)
from prosody_qc import (
    _audio_judge_gate,
    analyze_job as analyze_prosody_job,
)


API_BASE = os.environ.get("ELEVENLABS_API_BASE", "https://api.elevenlabs.io").rstrip("/")
STATE_DIR = Path(
    os.environ.get(
        "ELEVENLABS_REFERENCE_STATE_DIR",
        str(Path.home() / ".codex" / "state" / "elevenlabs-reference"),
    )
).expanduser()
REGISTRY_PATH = STATE_DIR / "voices.json"
REGISTRY_LOCK_PATH = STATE_DIR / "voices.lock"
MODEL_ID = "eleven_v3"
MAX_ATTEMPTS_PER_BATCH = 5
LISTENING_APPROVAL_CONFIRMATION = "사용자가 전체 미리보기를 직접 듣고 승인함"
DELEGATED_AUTO_APPROVAL_CONFIRMATION = (
    "사용자가 전체 미리보기 직접 청취를 생략하고 강화 자동 검증 기반 최종화를 위임함"
)


def standing_tts_generation_authorized() -> bool:
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
STT_SINGLE_DIGIT_READINGS = {
    "0": ("영", "공"),
    "1": ("일", "하나", "한"),
    "2": ("이", "둘", "두"),
    "3": ("삼", "셋", "세"),
    "4": ("사", "넷", "네"),
    "5": ("오", "다섯"),
    "6": ("육", "여섯"),
    "7": ("칠", "일곱"),
    "8": ("팔", "여덟"),
    "9": ("구", "아홉"),
}
SINO_KOREAN_DIGITS = ("", "일", "이", "삼", "사", "오", "육", "칠", "팔", "구")
SINO_KOREAN_SMALL_UNITS = ("", "십", "백", "천")
SINO_KOREAN_LARGE_UNITS = ("", "만", "억", "조", "경")
STT_LATIN_LETTER_READINGS = {
    "A": "에이",
    "B": "비",
    "C": "씨",
    "D": "디",
    "E": "이",
    "F": "에프",
    "G": "지",
    "H": "에이치",
    "I": "아이",
    "J": "제이",
    "K": "케이",
    "L": "엘",
    "M": "엠",
    "N": "엔",
    "O": "오",
    "P": "피",
    "Q": "큐",
    "R": "알",
    "S": "에스",
    "T": "티",
    "U": "유",
    "V": "브이",
    "W": "더블유",
    "X": "엑스",
    "Y": "와이",
    "Z": "지",
}


class ApiError(RuntimeError):
    """Sanitized ElevenLabs API failure."""

    def __init__(self, status_code: int | None, message: str):
        self.status_code = status_code
        super().__init__(message)


class ElevenLabsClient:
    def __init__(self, api_key: str | None = None):
        key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        if not key:
            raise ApiError(
                None,
                "ELEVENLABS_API_KEY 환경변수가 설정되지 않았습니다. "
                "API 키를 명령문이나 스킬 파일에 직접 넣지 마세요.",
            )
        self.session = requests.Session()
        # Do not inherit proxy/.netrc configuration from the long-running
        # desktop session. Voice data and the API key must go directly to the
        # fixed official ElevenLabs endpoint used below.
        self.session.trust_env = False
        self.session.headers.update({"xi-api-key": key})

    def _request(
        self,
        method: str,
        path: str,
        *,
        retry_safe: bool = False,
        timeout: int = 240,
        **kwargs: Any,
    ) -> requests.Response:
        url = f"{API_BASE}{path}"
        maximum_attempts = 3 if retry_safe else 1
        for attempt in range(1, maximum_attempts + 1):
            try:
                response = self.session.request(
                    method,
                    url,
                    timeout=timeout,
                    **kwargs,
                )
            except requests.RequestException as exc:
                if attempt < maximum_attempts:
                    time.sleep(min(2**attempt, 8))
                    continue
                raise ApiError(None, f"ElevenLabs API 연결에 실패했습니다: {exc}") from exc

            if response.ok:
                return response
            if retry_safe and response.status_code in {429, 500, 502, 503, 504}:
                if attempt < maximum_attempts:
                    retry_after = response.headers.get("retry-after")
                    try:
                        wait_seconds = float(retry_after) if retry_after else 2**attempt
                    except ValueError:
                        wait_seconds = 2**attempt
                    time.sleep(min(max(wait_seconds, 0.25), 30.0))
                    continue
            try:
                detail: Any = response.json()
            except ValueError:
                detail = response.text[:800]
            request_id = response.headers.get("request-id") or response.headers.get(
                "x-request-id"
            )
            request_note = f" request_id={request_id}" if request_id else ""
            raise ApiError(
                response.status_code,
                f"ElevenLabs API 오류 {response.status_code}:{request_note} "
                f"{json.dumps(detail, ensure_ascii=False)[:1000]}",
            )
        raise ApiError(None, "ElevenLabs API 요청이 완료되지 않았습니다.")

    def get_json(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        response = self._request("GET", path, params=params, retry_safe=True)
        return response.json()

    def get_subscription(self) -> dict[str, Any]:
        return self.get_json("/v1/user/subscription")

    def get_voice(self, voice_id: str) -> dict[str, Any]:
        return self.get_json(f"/v1/voices/{voice_id}")

    def list_voices(self) -> list[dict[str, Any]]:
        voices: list[dict[str, Any]] = []
        page_token: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if page_token:
                params["next_page_token"] = page_token
            data = self.get_json("/v2/voices", params=params)
            voices.extend(data.get("voices") or [])
            page_token = data.get("next_page_token")
            if not page_token:
                break
        return voices

    def isolate_audio(self, source: Path) -> tuple[bytes, str]:
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        with source.open("rb") as file:
            response = self._request(
                "POST",
                "/v1/audio-isolation",
                files={"audio": (source.name, file, mime_type)},
            )
        return response.content, response.headers.get("content-type", "application/octet-stream")

    def transcribe(
        self,
        source: Path,
        *,
        detect_speakers: bool = False,
        seed: int = 173,
        temperature: float = 0.0,
    ) -> dict[str, Any]:
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        form_data = {
            "model_id": "scribe_v2",
            "language_code": "ko",
            "tag_audio_events": "false",
            "diarize": "true" if detect_speakers else "false",
            "timestamps_granularity": "character",
            "temperature": str(temperature),
            "seed": str(seed),
        }
        if not detect_speakers:
            form_data["num_speakers"] = "1"
        with source.open("rb") as file:
            response = self._request(
                "POST",
                "/v1/speech-to-text",
                files={"file": (source.name, file, mime_type)},
                data=form_data,
            )
        return response.json()

    def forced_alignment(self, source: Path, text: str) -> dict[str, Any]:
        mime_type = mimetypes.guess_type(source.name)[0] or "application/octet-stream"
        with source.open("rb") as file:
            response = self._request(
                "POST",
                "/v1/forced-alignment",
                files={"file": (source.name, file, mime_type)},
                data={"text": text},
            )
        return response.json()

    def clone_voice(
        self,
        source: Path,
        *,
        name: str,
        description: str,
    ) -> dict[str, Any]:
        mime_type = mimetypes.guess_type(source.name)[0] or "audio/wav"
        with source.open("rb") as file:
            response = self._request(
                "POST",
                "/v1/voices/add",
                files=[("files", (source.name, file, mime_type))],
                data={
                    "name": name,
                    "description": description,
                    "remove_background_noise": "false",
                    "labels": json.dumps(
                        {
                            "language": "ko",
                            "use_case": "authorized_reference_voice",
                        },
                        ensure_ascii=False,
                    ),
                },
            )
        return response.json()

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
    ) -> tuple[dict[str, Any], dict[str, str]]:
        effective_model_id = (model_id or MODEL_ID).strip()
        payload: dict[str, Any] = {
            "text": text,
            "model_id": effective_model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": 0.86,
                "use_speaker_boost": True,
                "speed": speed,
            },
            "seed": seed,
            "apply_text_normalization": "auto",
        }
        if effective_model_id == "eleven_v3":
            payload["language_code"] = "ko"
        elif effective_model_id == "eleven_multilingual_v2":
            # Multilingual v2 infers Korean from the text and does not support
            # the language_code field. Zero style exaggeration also reduces
            # instability and articulation artifacts.
            payload["voice_settings"]["style"] = 0.0
        if pronunciation_dictionary_locators:
            payload["pronunciation_dictionary_locators"] = (
                pronunciation_dictionary_locators
            )
        # Eleven v3 currently rejects request-stitching context fields even
        # though the generic TTS endpoint schema exposes them.
        if effective_model_id != "eleven_v3":
            if previous_text:
                payload["previous_text"] = previous_text
            if next_text:
                payload["next_text"] = next_text
        response = self._request(
            "POST",
            f"/v1/text-to-speech/{voice_id}/with-timestamps",
            params={"output_format": output_format},
            json=payload,
        )
        return response.json(), dict(response.headers)


def _sino_korean_integer_reading(raw_digits: str) -> str | None:
    """Return the standard Sino-Korean cardinal reading for an integer token."""
    compact = raw_digits.replace(",", "")
    if not compact.isdigit() or len(compact) > 20:
        return None
    compact = compact.lstrip("0")
    if not compact:
        return "영"

    groups: list[str] = []
    while compact:
        groups.append(compact[-4:])
        compact = compact[:-4]
    if len(groups) > len(SINO_KOREAN_LARGE_UNITS):
        return None

    parts: list[str] = []
    for group_index in range(len(groups) - 1, -1, -1):
        group = groups[group_index].zfill(4)
        group_parts: list[str] = []
        for position, character in enumerate(group):
            digit = int(character)
            if digit == 0:
                continue
            unit_index = 3 - position
            if digit != 1 or unit_index == 0:
                group_parts.append(SINO_KOREAN_DIGITS[digit])
            group_parts.append(SINO_KOREAN_SMALL_UNITS[unit_index])
        if group_parts:
            parts.extend(group_parts)
            parts.append(SINO_KOREAN_LARGE_UNITS[group_index])
    return "".join(parts)


def _expand_stt_integer_tokens(text: str) -> str:
    """Expand integer/percent notation while leaving all other text untouched."""

    def replace(match: re.Match[str]) -> str:
        reading = _sino_korean_integer_reading(match.group("number"))
        if reading is None:
            return match.group(0)
        if match.group("percent"):
            return f"{reading} 퍼센트"
        return reading

    return re.sub(
        (
            r"(?<![A-Za-z0-9.,+\-−])"
            r"(?P<number>(?:0|[1-9]\d*)(?:,\d{3})*)"
            r"(?P<percent>%?)"
            r"(?![A-Za-z0-9.,+\-−])"
        ),
        replace,
        text,
    )


def canonicalize_stt_notation(
    expected_text: str,
    transcript_text: str,
) -> str:
    """Expand STT-rendered digits/acronyms only when that makes the text exact."""
    expected_normalized = normalize_for_comparison(expected_text)
    expected_lexical = normalize_lexical_content(expected_text)
    expanded_integer_tokens = _expand_stt_integer_tokens(transcript_text)
    candidates = (
        [expanded_integer_tokens, transcript_text]
        if expanded_integer_tokens != transcript_text
        else [transcript_text]
    )
    for match in list(re.finditer(r"\d", transcript_text)):
        readings = STT_SINGLE_DIGIT_READINGS.get(match.group())
        if not readings:
            continue
        next_candidates: list[str] = []
        for candidate in candidates:
            digit_position = next(
                (
                    index
                    for index, character in enumerate(candidate)
                    if character.isdigit()
                ),
                None,
            )
            if digit_position is None:
                next_candidates.append(candidate)
                continue
            for reading in readings:
                next_candidates.append(
                    candidate[:digit_position]
                    + reading
                    + candidate[digit_position + 1 :]
                )
        candidates = next_candidates[:256]
    latin_count = len(re.findall(r"[A-Za-z]", transcript_text))
    for _ in range(latin_count):
        next_candidates = []
        for candidate in candidates:
            letter_match = re.search(r"[A-Za-z]", candidate)
            if not letter_match:
                next_candidates.append(candidate)
                continue
            reading = STT_LATIN_LETTER_READINGS[letter_match.group().upper()]
            next_candidates.append(
                candidate[: letter_match.start()]
                + reading
                + candidate[letter_match.end() :]
            )
        candidates = next_candidates[:256]
    for candidate in candidates:
        if (
            normalize_for_comparison(candidate) == expected_normalized
            and normalize_lexical_content(candidate) == expected_lexical
        ):
            return candidate
    return transcript_text


def canonicalize_stt_number_notation(
    expected_text: str,
    transcript_text: str,
) -> str:
    """Backward-compatible alias for callers of the original helper name."""
    return canonicalize_stt_notation(expected_text, transcript_text)


FOCUS_TRANSCRIPTION_VARIANTS = (
    (173, 0.0),
    (907, 0.1),
    (2027, 0.2),
)


def focus_phrase_interval(
    alignment: dict[str, Any],
    phrase: str,
    *,
    audio_duration_seconds: float | None = None,
) -> tuple[float, float]:
    characters = [
        item
        for item in (alignment.get("characters") or [])
        if isinstance(item, dict)
    ]
    aligned_text = "".join(str(item.get("text") or "") for item in characters)
    if aligned_text.count(phrase) != 1:
        raise WorkflowError(
            "강제 정렬 결과에서 집중 발음 구절이 정확히 한 번 나타나지 않습니다: "
            f"{phrase}"
        )
    phrase_start = aligned_text.find(phrase)
    phrase_end = phrase_start + len(phrase)
    focused_characters = [
        item
        for item in characters[phrase_start:phrase_end]
        if normalize_for_comparison(str(item.get("text") or ""))
    ]
    if not focused_characters:
        raise WorkflowError(f"집중 발음 구절의 유효한 정렬 문자가 없습니다: {phrase}")
    start = focused_characters[0].get("start")
    end = focused_characters[-1].get("end")
    if not (
        isinstance(start, (int, float))
        and isinstance(end, (int, float))
        and start >= 0
        and end > start
    ):
        raise WorkflowError(f"집중 발음 구절의 정렬 시간이 유효하지 않습니다: {phrase}")

    # Forced-alignment onsets can land a few frames after the acoustic attack.
    # Preserve only the immediately preceding non-lexical boundary (spaces and
    # punctuation), never a neighboring word. At the beginning of the aligned
    # text, the audio start itself is the non-lexical boundary, so retain it as
    # well. This keeps the initial consonant intact without leaking a neighbor.
    boundary_start = phrase_start
    while boundary_start > 0:
        previous = characters[boundary_start - 1]
        previous_text = str(previous.get("text") or "")
        previous_start = previous.get("start")
        if (
            normalize_lexical_content(previous_text)
            or not isinstance(previous_start, (int, float))
            or previous_start < 0
        ):
            break
        boundary_start -= 1
        start = min(float(start), float(previous_start))
    if boundary_start == 0:
        start = 0.0

    # Symmetrically preserve the acoustic release at the end of the audio.
    # Forced alignment often assigns trailing punctuation the same timestamp
    # as the last lexical character and therefore does not describe the real
    # release/tail. Include only immediately following non-lexical characters;
    # if no later lexical content exists, extend to the actual WAV boundary.
    following_characters = characters[phrase_end:]
    has_following_lexical_content = any(
        normalize_lexical_content(str(item.get("text") or ""))
        for item in following_characters
    )
    if not has_following_lexical_content:
        for following in following_characters:
            following_end = following.get("end")
            if isinstance(following_end, (int, float)) and following_end >= 0:
                end = max(float(end), float(following_end))
    if (
        not has_following_lexical_content
        and isinstance(audio_duration_seconds, (int, float))
        and math.isfinite(float(audio_duration_seconds))
        and float(audio_duration_seconds) > float(end)
    ):
        end = float(audio_duration_seconds)

    return float(start), float(end)


def focus_clip_silence_padding_seconds(
    *,
    start_seconds: float,
    end_seconds: float,
    audio_duration_seconds: float,
) -> float:
    """Avoid adding artificial silence when the native WAV is kept whole."""
    full_audio_interval = (
        start_seconds <= 1e-6
        and end_seconds >= audio_duration_seconds - 1e-3
    )
    return 0.0 if full_audio_interval else 0.2


def run_focus_pronunciation_checks(
    client: ElevenLabsClient,
    *,
    wav_path: Path,
    alignment: dict[str, Any],
    phrases: list[str],
    attempt_dir: Path,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    focus_root = attempt_dir / "focus_pronunciation"
    with wave.open(str(wav_path), "rb") as wav_file:
        audio_duration_seconds = (
            wav_file.getnframes() / max(wav_file.getframerate(), 1)
        )
    for phrase_index, phrase in enumerate(phrases, 1):
        focus_dir = focus_root / f"{phrase_index:02d}"
        start, end = focus_phrase_interval(
            alignment,
            phrase,
            audio_duration_seconds=audio_duration_seconds,
        )
        silence_padding_seconds = focus_clip_silence_padding_seconds(
            start_seconds=start,
            end_seconds=end,
            audio_duration_seconds=audio_duration_seconds,
        )
        clip_path = extract_wav_interval(
            wav_path,
            focus_dir / "clip.wav",
            start_seconds=start,
            end_seconds=end,
            silence_padding_seconds=silence_padding_seconds,
        )
        runs: list[dict[str, Any]] = []
        for run_index, (seed, temperature) in enumerate(
            FOCUS_TRANSCRIPTION_VARIANTS,
            1,
        ):
            transcript = client.transcribe(
                clip_path,
                seed=seed,
                temperature=temperature,
            )
            transcript_text = str(transcript.get("text") or "")
            canonical_text = canonicalize_stt_notation(phrase, transcript_text)
            language_code = (
                str(transcript.get("language_code"))
                if transcript.get("language_code")
                else None
            )
            passed = (
                language_code is not None
                and language_code.lower() in {"ko", "kor"}
                and normalize_for_comparison(canonical_text)
                == normalize_for_comparison(phrase)
                and normalize_lexical_content(canonical_text)
                == normalize_lexical_content(phrase)
            )
            atomic_write_json(
                focus_dir / f"transcript-{run_index}.json",
                transcript,
            )
            runs.append(
                {
                    "run": run_index,
                    "seed": seed,
                    "temperature": temperature,
                    "transcript_text": transcript_text,
                    "canonical_text": canonical_text,
                    "language_code": language_code,
                    "passed": passed,
                }
            )
        result = {
            "phrase": phrase,
            "start_seconds": round(start, 6),
            "end_seconds": round(end, 6),
            "silence_padding_seconds": silence_padding_seconds,
            "clip": str(clip_path.name),
            "runs": runs,
            "passed": all(run["passed"] for run in runs),
        }
        atomic_write_json(focus_dir / "result.json", result)
        results.append(result)
    atomic_write_json(focus_root / "summary.json", {"results": results})
    return results


def attach_focus_pronunciation_qc(
    qc: dict[str, Any],
    *,
    required: bool,
    results: list[dict[str, Any]],
) -> dict[str, Any]:
    passed = (not required) or (
        bool(results) and all(bool(result.get("passed")) for result in results)
    )
    qc["checks"]["focused_pronunciation_consensus"] = passed
    qc["pronunciation_focus_required"] = required
    qc["pronunciation_focus_results"] = results
    qc["auto_pass"] = all(bool(value) for value in qc["checks"].values())
    if required and not passed:
        qc["score"] = round(float(qc.get("score") or 0.0) + 25.0, 6)
    return qc


def relative_to_job(path: Path, job_dir: Path) -> str:
    return str(path.resolve().relative_to(job_dir.resolve()))


def ensure_private_state_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        STATE_DIR.chmod(0o700)
    except OSError:
        pass


@contextlib.contextmanager
def registry_write_lock() -> Any:
    ensure_private_state_dir()
    with REGISTRY_LOCK_PATH.open("a+", encoding="utf-8") as lock_file:
        try:
            REGISTRY_LOCK_PATH.chmod(0o600)
        except OSError:
            pass
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def load_registry() -> dict[str, Any]:
    ensure_private_state_dir()
    if not REGISTRY_PATH.exists():
        return {"version": 1, "voices": []}
    registry = load_json(REGISTRY_PATH)
    if not isinstance(registry, dict) or not isinstance(registry.get("voices"), list):
        raise WorkflowError(f"보이스 레지스트리 형식이 올바르지 않습니다: {REGISTRY_PATH}")
    return registry


def save_registry(registry: dict[str, Any]) -> None:
    ensure_private_state_dir()
    atomic_write_json(REGISTRY_PATH, registry)
    try:
        REGISTRY_PATH.chmod(0o600)
    except OSError:
        pass


def register_voice(
    *,
    voice_id: str,
    name: str,
    profile: dict[str, Any],
    source_sha256: str,
    requires_verification: bool,
) -> None:
    with registry_write_lock():
        registry = load_registry()
        profile_dir = STATE_DIR / "profiles"
        profile_path = profile_dir / f"{voice_id}.json"
        profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            profile_dir.chmod(0o700)
        except OSError:
            pass
        persistent_profile = {
            "created_at": profile.get("created_at"),
            "source_sha256": source_sha256,
            "transcript_language_code": profile.get("transcript_language_code"),
            "speaker_count": profile.get("speaker_count"),
            "audio_metrics": profile.get("audio_metrics"),
            "quality_gate": profile.get("quality_gate"),
            "scope": profile.get("scope"),
        }
        atomic_write_json(profile_path, persistent_profile)
        try:
            profile_path.chmod(0o600)
        except OSError:
            pass
        entry = {
            "voice_id": voice_id,
            "name": name,
            "created_at": utc_now(),
            "source_sha256": source_sha256,
            "profile_path": str(profile_path),
            "requires_verification": requires_verification,
            "retention": "keep",
        }
        registry["voices"] = [
            existing
            for existing in registry["voices"]
            if existing.get("voice_id") != voice_id
        ]
        registry["voices"].append(entry)
        registry["updated_at"] = utc_now()
        save_registry(registry)


def find_registry_voice(
    *,
    voice_id: str | None = None,
    name: str | None = None,
) -> dict[str, Any] | None:
    registry = load_registry()
    matches = []
    for voice in registry["voices"]:
        if voice_id and voice.get("voice_id") == voice_id:
            matches.append(voice)
        elif name and str(voice.get("name", "")).casefold() == name.casefold():
            matches.append(voice)
    if len(matches) > 1:
        raise WorkflowError(
            f"같은 이름의 저장된 보이스가 여러 개입니다. voice_id를 지정하세요: {name}"
        )
    return matches[0] if matches else None


def verify_existing_voice(
    client: ElevenLabsClient,
    *,
    voice_id: str,
) -> None:
    cloud_voice = client.get_voice(voice_id)
    verification = cloud_voice.get("voice_verification")
    if not isinstance(verification, dict):
        raise WorkflowError(
            "ElevenLabs에서 이 보이스의 검증 상태를 확인하지 못했습니다: "
            f"{voice_id}"
        )
    cloud_requires = verification.get("requires_verification")
    cloud_verified = verification.get("is_verified")
    registry_voice = find_registry_voice(voice_id=voice_id)
    locally_blocked = bool(
        registry_voice and registry_voice.get("requires_verification")
    )
    if cloud_verified is not True and cloud_requires is not False:
        raise WorkflowError(
            "이 보이스는 ElevenLabs 검증 완료 또는 검증 불필요 상태가 "
            "명시되기 전에는 사용할 수 없습니다: "
            f"{voice_id}"
        )
    if locally_blocked and not (
        cloud_verified is True or cloud_requires is False
    ):
        raise WorkflowError(
            "로컬 레지스트리에 검증 대기 보이스로 기록되어 있으며 "
            "ElevenLabs에서 검증 완료를 확인하지 못했습니다: "
            f"{voice_id}"
        )
    if locally_blocked:
        with registry_write_lock():
            registry = load_registry()
            changed = False
            for voice in registry["voices"]:
                if voice.get("voice_id") == voice_id:
                    voice["requires_verification"] = False
                    voice["verification_confirmed_at"] = utc_now()
                    changed = True
            if changed:
                registry["updated_at"] = utc_now()
                save_registry(registry)


def resolve_cloud_voice(
    client: ElevenLabsClient,
    *,
    voice_id: str | None,
    name: str | None,
) -> tuple[str, str]:
    if voice_id:
        registry_voice = find_registry_voice(voice_id=voice_id)
        return voice_id, str(registry_voice.get("name") if registry_voice else voice_id)
    if not name:
        raise WorkflowError("기존 보이스의 ID 또는 정확한 이름이 필요합니다.")
    voices = client.list_voices()
    matches = [
        voice
        for voice in voices
        if str(voice.get("name", "")).casefold() == name.casefold()
    ]
    if not matches:
        raise WorkflowError(f"ElevenLabs 계정에서 보이스를 찾지 못했습니다: {name}")
    if len(matches) > 1:
        ids = ", ".join(str(voice.get("voice_id")) for voice in matches)
        raise WorkflowError(f"같은 이름의 보이스가 여러 개입니다. voice_id를 사용하세요: {ids}")
    return str(matches[0]["voice_id"]), str(matches[0].get("name") or name)


def choose_output_format(client: ElevenLabsClient) -> tuple[str, str]:
    try:
        subscription = client.get_subscription()
        tier = str(subscription.get("tier") or "unknown").lower()
    except ApiError:
        return "mp3_44100_128", "unknown"
    if tier in {"pro", "scale", "business", "enterprise"}:
        return "pcm_44100", tier
    if tier == "creator":
        return "mp3_44100_192", tier
    return "mp3_44100_128", tier


def write_job(job_dir: Path, job: dict[str, Any]) -> None:
    job["updated_at"] = utc_now()
    atomic_write_json(job_dir / "job.json", job)


def mark_interrupted_job(job_dir: Path) -> None:
    job_path = job_dir / "job.json"
    if not job_path.is_file():
        return
    try:
        job = load_json(job_path)
    except WorkflowError:
        return
    if job.get("finalized"):
        return
    has_plan = (job_dir / "script_plan.json").is_file()
    job["status"] = (
        "interrupted_recoverable"
        if has_plan
        else "initialization_interrupted_new_job_required"
    )
    job["additional_generation_token"] = (
        secrets.token_hex(16) if has_plan else None
    )
    job["last_error"] = {
        "created_at": utc_now(),
        "error_type": "KeyboardInterrupt",
        "message": (
            (
                "생성이 중단되었습니다. status를 확인하고 사용자가 추가 호출 비용을 "
                "승인한 뒤 중단된 문장만 재개하세요."
            )
            if has_plan
            else (
                "레퍼런스 준비 중 중단되어 이 폴더에서는 재개할 수 없습니다. "
                "클라우드에 clone이 생겼는지 list-voices로 확인한 뒤 새 작업 폴더에서 "
                "기존 voice_id 또는 레퍼런스로 다시 시작하세요."
            )
        ),
    }
    write_job(job_dir, job)


@contextlib.contextmanager
def job_write_lock(job_dir: Path) -> Any:
    if not job_dir.is_dir():
        raise WorkflowError(f"작업 폴더를 찾을 수 없습니다: {job_dir}")
    lock_path = job_dir / ".job.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            lock_path.chmod(0o600)
        except OSError:
            pass
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def decode_tts_audio(
    audio_bytes: bytes,
    *,
    output_format: str,
    destination_dir: Path,
) -> tuple[Path, Path]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    wav_path = destination_dir / "candidate.wav"
    mp3_path = destination_dir / "candidate.mp3"
    if output_format.startswith("pcm_"):
        sample_rate_match = output_format.split("_", 1)[1]
        try:
            sample_rate = int(sample_rate_match)
        except ValueError as exc:
            raise WorkflowError(f"알 수 없는 PCM 출력 형식입니다: {output_format}") from exc
        raw_path = destination_dir / "candidate.pcm"
        raw_path.write_bytes(audio_bytes)
        convert_raw_pcm_to_wav(raw_path, wav_path, sample_rate=sample_rate)
        wav_to_mp3(wav_path, mp3_path)
    elif output_format.startswith("mp3_"):
        mp3_path.write_bytes(audio_bytes)
        convert_to_wav(mp3_path, wav_path)
    elif output_format.startswith("wav_"):
        source_wav = destination_dir / "candidate-source.wav"
        source_wav.write_bytes(audio_bytes)
        convert_to_wav(source_wav, wav_path)
        wav_to_mp3(wav_path, mp3_path)
    else:
        encoded_path = destination_dir / "candidate-audio.bin"
        encoded_path.write_bytes(audio_bytes)
        convert_to_wav(encoded_path, wav_path)
        wav_to_mp3(wav_path, mp3_path)
    return wav_path, mp3_path


def prepare_style_reference(
    client: ElevenLabsClient,
    *,
    source_video: Path,
    job_dir: Path,
    subdirectory: str = "reference",
) -> tuple[dict[str, Any], Path]:
    if not source_video.exists() or not source_video.is_file():
        raise WorkflowError(f"레퍼런스 영상을 찾을 수 없습니다: {source_video}")
    reference_dir = job_dir / subdirectory
    reference_dir.mkdir(parents=True, exist_ok=True)
    probe = probe_media(source_video)
    raw_wav = convert_to_wav(source_video, reference_dir / "reference_raw.wav")
    isolated_bytes, content_type = client.isolate_audio(raw_wav)
    isolated_encoded = reference_dir / "reference_isolated.bin"
    isolated_encoded.write_bytes(isolated_bytes)
    isolated_wav = convert_to_wav(
        isolated_encoded,
        reference_dir / "reference_isolated.wav",
    )
    trimmed_wav = trim_edge_silence(
        isolated_wav,
        reference_dir / "reference_clone_sample.wav",
    )
    transcript_data = client.transcribe(trimmed_wav, detect_speakers=True)
    transcript = str(transcript_data.get("text") or "").strip()
    speaker_ids = {
        str(word.get("speaker_id"))
        for word in (transcript_data.get("words") or [])
        if isinstance(word, dict) and word.get("speaker_id")
    }
    speaker_count = len(speaker_ids) if speaker_ids else None
    metrics = analyze_wav(trimmed_wav, transcript=transcript)
    transcript_language_code = (
        str(transcript_data.get("language_code"))
        if transcript_data.get("language_code")
        else None
    )
    quality = reference_quality(
        metrics,
        transcript,
        transcript_language_code=transcript_language_code,
        speaker_count=speaker_count,
    )
    profile = {
        "created_at": utc_now(),
        "source_name": source_video.name,
        "source_sha256": sha256_file(source_video),
        "source_probe": probe,
        "isolation_content_type": content_type,
        "transcript": transcript,
        "transcript_language_code": transcript_language_code,
        "speaker_count": speaker_count,
        "speaker_ids": sorted(speaker_ids),
        "audio_metrics": metrics,
        "quality_gate": quality,
        "scope": "overall_voice_style_and_average_pace",
    }
    atomic_write_json(reference_dir / "reference_transcript.json", transcript_data)
    atomic_write_json(reference_dir / "reference_profile.json", profile)
    if quality["hard_failures"]:
        raise WorkflowError(
            "레퍼런스 음성 품질 게이트를 통과하지 못했습니다: "
            + " ".join(quality["hard_failures"])
        )
    return profile, trimmed_wav


def profile_for_existing_voice(
    *,
    voice_id: str,
    style_reference_video: Path | None,
    client: ElevenLabsClient,
    job_dir: Path,
) -> dict[str, Any]:
    if style_reference_video:
        profile, _ = prepare_style_reference(
            client,
            source_video=style_reference_video,
            job_dir=job_dir,
            subdirectory="style_reference",
        )
        return profile
    registry_voice = find_registry_voice(voice_id=voice_id)
    if not registry_voice:
        raise WorkflowError(
            "이 기존 보이스에는 저장된 속도·감정 프로필이 없습니다. "
            "--style-reference-video를 함께 제공하세요."
        )
    profile_path = Path(str(registry_voice.get("profile_path") or ""))
    if not profile_path.exists():
        raise WorkflowError(
            "저장된 보이스 프로필 파일이 없습니다. --style-reference-video가 필요합니다."
        )
    return load_json(profile_path)


def create_new_clone(
    client: ElevenLabsClient,
    *,
    reference_video: Path,
    voice_name: str,
    job_dir: Path,
) -> tuple[str, dict[str, Any]]:
    profile, sample_wav = prepare_style_reference(
        client,
        source_video=reference_video,
        job_dir=job_dir,
    )
    clone_result = client.clone_voice(
        sample_wav,
        name=voice_name,
        description="Authorized Korean reference voice retained by elevenlabs-reference skill",
    )
    voice_id = str(clone_result.get("voice_id") or "")
    if not voice_id:
        raise WorkflowError("ElevenLabs가 새 voice_id를 반환하지 않았습니다.")
    requires_verification = bool(clone_result.get("requires_verification"))
    register_voice(
        voice_id=voice_id,
        name=voice_name,
        profile=profile,
        source_sha256=str(profile["source_sha256"]),
        requires_verification=requires_verification,
    )
    if requires_verification:
        raise WorkflowError(
            "새 보이스가 ElevenLabs 계정 검증을 요구합니다. 대시보드에서 검증을 "
            f"완료한 뒤 기존 voice_id로 다시 실행하세요: {voice_id}"
        )
    return voice_id, profile


def adjusted_tts_text(segment: dict[str, Any]) -> str:
    return str(segment.get("tts_override") or segment["tts_text"])


def adjusted_speed(segment: dict[str, Any]) -> float:
    for attempt in reversed(segment.get("attempts") or []):
        attempt_metrics = attempt.get("audio_metrics") or {}
        reference_rate = attempt.get("reference_rate")
        candidate_rate = attempt_metrics.get("syllables_per_active_second")
        previous_speed = attempt.get("speed", 1.0)
        if (
            isinstance(reference_rate, (int, float))
            and reference_rate > 0
            and isinstance(candidate_rate, (int, float))
            and candidate_rate > 0
            and isinstance(previous_speed, (int, float))
        ):
            corrected = float(previous_speed) * float(reference_rate) / float(
                candidate_rate
            )
            return round(min(1.2, max(0.7, corrected)), 4)
    return 1.0


def segment_target_duration(
    plan: dict[str, Any],
    segment: dict[str, Any],
    job: dict[str, Any],
) -> float | None:
    total_target = job.get("target_duration_seconds")
    if not isinstance(total_target, (int, float)) or total_target <= 0:
        return None
    total_syllables = sum(
        len(normalize_for_comparison(str(item["spoken_text"])))
        for item in plan["segments"]
    )
    segment_syllables = len(normalize_for_comparison(str(segment["spoken_text"])))
    if not total_syllables:
        return None
    return float(total_target) * segment_syllables / total_syllables


def generate_segment(
    client: ElevenLabsClient,
    *,
    job_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    segment: dict[str, Any],
    attempt_limit: int,
) -> bool:
    index = int(segment["index"])
    segment_dir = job_dir / "candidates" / f"{index:03d}"
    reference_profile = load_json(job_dir / "reference_profile.json")
    reference_metrics = reference_profile.get("audio_metrics", reference_profile)
    reference_rate = reference_metrics.get("syllables_per_active_second")
    previous_text = (
        str(plan["segments"][index - 2]["spoken_text"]) if index > 1 else None
    )
    next_text = (
        str(plan["segments"][index]["spoken_text"])
        if index < len(plan["segments"])
        else None
    )
    target_duration = segment_target_duration(plan, segment, job)
    focus_phrases = [
        str(phrase).strip()
        for phrase in (segment.get("pronunciation_focus_phrases") or [])
        if str(phrase).strip()
    ]
    stability_values = [0.50, 0.42, 0.58, 0.35, 0.66]

    for _ in range(attempt_limit):
        existing_numbers = [
            int(path.name.removeprefix("attempt-"))
            for path in segment_dir.glob("attempt-*")
            if path.is_dir() and path.name.removeprefix("attempt-").isdigit()
        ]
        recorded_numbers = [
            int(attempt.get("attempt") or 0)
            for attempt in segment.get("attempts", [])
            if isinstance(attempt, dict)
        ]
        attempt_number = max([0, *existing_numbers, *recorded_numbers]) + 1
        attempt_dir = segment_dir / f"attempt-{attempt_number:03d}"
        attempt_dir.mkdir(parents=True, exist_ok=False)
        seed = secrets.randbelow(2**32)
        stability = stability_values[(attempt_number - 1) % len(stability_values)]
        request_text = adjusted_tts_text(segment)
        speed = adjusted_speed(segment)
        attempt_record: dict[str, Any] = {
            "attempt": attempt_number,
            "created_at": utc_now(),
            "seed": seed,
            "stability": stability,
            "speed": speed,
            "request_text": request_text,
            "status": "reserved_before_tts",
        }
        segment["attempts"].append(attempt_record)
        recorded = True
        atomic_write_json(attempt_dir / "attempt.json", attempt_record)
        atomic_write_json(job_dir / "script_plan.json", plan)
        try:
            response, headers = client.create_speech_with_timing(
                voice_id=str(job["voice_id"]),
                text=request_text,
                output_format=str(job["api_output_format"]),
                seed=seed,
                stability=stability,
                speed=speed,
                previous_text=previous_text,
                next_text=next_text,
            )
            try:
                audio_bytes = base64.b64decode(
                    response["audio_base64"],
                    validate=True,
                )
            except (KeyError, ValueError) as exc:
                raise WorkflowError(
                    "TTS 응답에서 유효한 오디오를 찾지 못했습니다."
                ) from exc

            wav_path, mp3_path = decode_tts_audio(
                audio_bytes,
                output_format=str(job["api_output_format"]),
                destination_dir=attempt_dir,
            )
            transcript = client.transcribe(wav_path)
            transcript_text = str(transcript.get("text") or "")
            transcript_language_code = (
                str(transcript.get("language_code"))
                if transcript.get("language_code")
                else None
            )
            expected_spoken_text = str(segment["spoken_text"])
            qc_transcript_text = canonicalize_stt_notation(
                expected_spoken_text,
                transcript_text,
            )
            transcript_precheck_passed = (
                transcript_language_code is not None
                and transcript_language_code.lower() in {"ko", "kor"}
                and normalize_for_comparison(qc_transcript_text)
                == normalize_for_comparison(expected_spoken_text)
                and normalize_lexical_content(qc_transcript_text)
                == normalize_lexical_content(expected_spoken_text)
            )
            if transcript_precheck_passed:
                alignment = client.forced_alignment(
                    wav_path,
                    expected_spoken_text,
                )
            else:
                alignment = {
                    "characters": [],
                    "words": [],
                    "loss": None,
                    "skipped_reason": "STT 또는 언어 하드 게이트가 먼저 실패함",
                }
            metrics = analyze_wav(wav_path, transcript=qc_transcript_text)
            qc = score_candidate(
                expected_text=expected_spoken_text,
                transcript_text=qc_transcript_text,
                transcript_language_code=transcript_language_code,
                candidate_metrics=metrics,
                reference_profile=reference_profile,
                alignment=alignment,
                target_duration_seconds=target_duration,
            )
            focus_results: list[dict[str, Any]] = []
            if qc["auto_pass"] and focus_phrases:
                focus_results = run_focus_pronunciation_checks(
                    client,
                    wav_path=wav_path,
                    alignment=alignment,
                    phrases=focus_phrases,
                    attempt_dir=attempt_dir,
                )
            qc = attach_focus_pronunciation_qc(
                qc,
                required=bool(focus_phrases),
                results=focus_results,
            )
            request_id = headers.get("request-id") or headers.get("x-request-id")
            usage_headers = {
                key: headers[key]
                for key in (
                    "character-cost",
                    "x-character-count",
                    "history-item-id",
                )
                if headers.get(key) is not None
            }
            atomic_write_json(
                attempt_dir / "tts_alignment.json",
                response.get("alignment"),
            )
            atomic_write_json(
                attempt_dir / "tts_normalized_alignment.json",
                response.get("normalized_alignment"),
            )
            atomic_write_json(attempt_dir / "transcript.json", transcript)
            atomic_write_json(attempt_dir / "forced_alignment.json", alignment)
            attempt_record.update(
                {
                    "status": "auto_qc_complete",
                    "request_id": request_id,
                    "usage_headers": usage_headers,
                    "wav": relative_to_job(wav_path, job_dir),
                    "mp3": relative_to_job(mp3_path, job_dir),
                    "transcript_text": transcript_text,
                    "qc_transcript_text": qc_transcript_text,
                    "pronunciation_focus_phrases": focus_phrases,
                    "pronunciation_focus_results": focus_results,
                    "audio_metrics": metrics,
                    "reference_rate": reference_rate,
                    "qc": qc,
                }
            )
            atomic_write_json(attempt_dir / "qc.json", attempt_record)
            atomic_write_json(job_dir / "script_plan.json", plan)

            if qc["auto_pass"]:
                review_segment_dir = job_dir / "review" / "segments"
                review_segment_dir.mkdir(parents=True, exist_ok=True)
                selected_wav = review_segment_dir / f"{index:03d}.wav"
                selected_mp3 = review_segment_dir / f"{index:03d}.mp3"
                shutil.copy2(wav_path, selected_wav)
                shutil.copy2(mp3_path, selected_mp3)
                segment["selected_attempt"] = attempt_number
                segment["selected_wav"] = relative_to_job(selected_wav, job_dir)
                segment["selected_mp3"] = relative_to_job(selected_mp3, job_dir)
                segment["status"] = "auto_passed_awaiting_user"
                atomic_write_json(job_dir / "script_plan.json", plan)
                return True
        except Exception as exc:
            attempt_record["status"] = "processing_error"
            attempt_record["error_type"] = type(exc).__name__
            attempt_record["error"] = str(exc)[:1000]
            if not recorded:
                segment["attempts"].append(attempt_record)
            atomic_write_json(attempt_dir / "error.json", attempt_record)
            atomic_write_json(job_dir / "script_plan.json", plan)
            if isinstance(exc, (WorkflowError, AudioToolError, ApiError)):
                raise
            raise WorkflowError(
                f"{index}번 문장 {attempt_number}차 처리 중 오류가 발생했습니다: {exc}"
            ) from exc

    qc_attempts = [
        attempt for attempt in segment["attempts"] if attempt.get("qc") is not None
    ]
    if not qc_attempts:
        raise WorkflowError(f"{index}번 문장에 자동 검수 가능한 후보가 없습니다.")
    best_attempt = min(
        qc_attempts,
        key=lambda attempt: float(attempt.get("qc", {}).get("score", float("inf"))),
    )
    segment["best_failed_attempt"] = best_attempt["attempt"]
    segment["status"] = "blocked_after_five_attempts"
    atomic_write_json(job_dir / "script_plan.json", plan)
    return False


def assemble_review_preview(job_dir: Path, plan: dict[str, Any]) -> tuple[Path, Path]:
    segment_wavs = [
        job_dir / str(segment["selected_wav"])
        for segment in plan["segments"]
        if segment.get("selected_wav")
    ]
    if len(segment_wavs) != len(plan["segments"]):
        raise WorkflowError("모든 문장이 자동 검수를 통과하기 전에는 전체 미리보기를 만들 수 없습니다.")
    review_dir = job_dir / "review"
    preview_wav = concatenate_wavs(segment_wavs, review_dir / "full_preview.wav")
    preview_mp3 = wav_to_mp3(preview_wav, review_dir / "full_preview.mp3")
    return preview_wav, preview_mp3


def generate_pending_segments(
    client: ElevenLabsClient,
    *,
    job_dir: Path,
    selected_indices: set[int] | None = None,
) -> bool:
    job = load_json(job_dir / "job.json")
    plan = load_json(job_dir / "script_plan.json")
    job["status"] = "generating_and_auto_qc"
    write_job(job_dir, job)
    for segment in plan["segments"]:
        index = int(segment["index"])
        if selected_indices is not None and index not in selected_indices:
            if segment["status"] not in {
                "pending_generation",
                "generating",
                "pending_regeneration",
            }:
                continue
        if segment["status"] == "user_approved":
            continue
        segment["status"] = "generating"
        atomic_write_json(job_dir / "script_plan.json", plan)
        try:
            passed = generate_segment(
                client,
                job_dir=job_dir,
                job=job,
                plan=plan,
                segment=segment,
                attempt_limit=MAX_ATTEMPTS_PER_BATCH,
            )
        except (WorkflowError, AudioToolError, ApiError) as exc:
            job["status"] = "processing_error"
            job["blocked_segment"] = index
            job["additional_generation_token"] = secrets.token_hex(16)
            job["last_error"] = {
                "created_at": utc_now(),
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
            write_job(job_dir, job)
            raise
        if not passed:
            job["status"] = "blocked_after_five_attempts"
            job["blocked_segment"] = index
            job["additional_generation_token"] = secrets.token_hex(16)
            write_job(job_dir, job)
            print(
                json.dumps(
                    {
                        "status": job["status"],
                        "blocked_segment": index,
                        "message": "추가 생성 전에 사용자 확인이 필요합니다.",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return False

    preview_wav, preview_mp3 = assemble_review_preview(job_dir, plan)
    job["status"] = "awaiting_user_listening_approval"
    job["review_preview_wav"] = relative_to_job(preview_wav, job_dir)
    job["review_preview_mp3"] = relative_to_job(preview_mp3, job_dir)
    review_files = [preview_wav, preview_mp3]
    for segment in plan["segments"]:
        review_files.append(job_dir / str(segment["selected_wav"]))
        review_files.append(job_dir / str(segment["selected_mp3"]))
    job["review_file_hashes"] = {
        relative_to_job(path, job_dir): sha256_file(path) for path in review_files
    }
    job["review_revision"] = int(job.get("review_revision") or 0) + 1
    job["review_preview_sha256"] = sha256_file(preview_mp3)
    job["prosody_listening_qc_report"] = None
    job["prosody_listening_qc_sha256"] = None
    job["prosody_objective_flagged_segments"] = None
    job["additional_generation_token"] = secrets.token_hex(16)
    job["user_approvals"] = []
    job["finalized"] = False
    write_job(job_dir, job)
    print(
        json.dumps(
            {
                "status": job["status"],
                "preview_mp3": str(preview_mp3.resolve()),
                "preview_wav": str(preview_wav.resolve()),
                "preview_revision": job["review_revision"],
                "preview_sha256": job["review_preview_sha256"],
                "segment_count": len(plan["segments"]),
                "next_action": "미리보기를 직접 듣고 자연어 품질 피드백 또는 사용 선택",
                "next_action_policy": (
                    "정형화된 승인 문구를 요청하지 않고 자연어 품질 피드백을 받음"
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return True


def initialize_job_directory(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise WorkflowError(
            f"출력 폴더가 비어 있지 않습니다. 기존 작업을 덮어쓰지 않습니다: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        output_dir.chmod(0o700)
    except OSError:
        pass
    for name in ("input", "review", "candidates"):
        child = output_dir / name
        child.mkdir(parents=True, exist_ok=True)
        try:
            child.chmod(0o700)
        except OSError:
            pass


def validate_output_directory(output_dir: Path) -> None:
    if output_dir.exists() and not output_dir.is_dir():
        raise WorkflowError(f"출력 경로가 폴더가 아닙니다: {output_dir}")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise WorkflowError(
            f"출력 폴더가 비어 있지 않습니다. 기존 작업을 덮어쓰지 않습니다: {output_dir}"
        )


def verify_live_model(
    client: ElevenLabsClient,
    model_id: str = MODEL_ID,
) -> None:
    models = client.get_json("/v1/models")
    if not isinstance(models, list):
        raise WorkflowError("ElevenLabs 모델 목록 응답 형식을 확인하지 못했습니다.")
    if not any(
        isinstance(model, dict)
        and model.get("model_id") == model_id
        and model.get("can_do_text_to_speech")
        for model in models
    ):
        raise WorkflowError(
            f"현재 ElevenLabs 계정에서 {model_id} TTS 모델을 확인하지 못했습니다."
        )


def validate_run_preconditions(args: argparse.Namespace, job_dir: Path) -> None:
    def validate_reference_media(path: Path) -> None:
        media = probe_media(path)
        streams = media.get("streams") or []
        if not any(
            isinstance(stream, dict) and stream.get("codec_type") == "audio"
            for stream in streams
        ):
            raise WorkflowError(f"레퍼런스에 음성 스트림이 없습니다: {path}")
        try:
            duration = float((media.get("format") or {}).get("duration") or 0.0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration <= 0:
            raise WorkflowError(f"레퍼런스 재생시간을 확인하지 못했습니다: {path}")
        if duration > 75.0:
            raise WorkflowError(
                f"레퍼런스가 75초를 초과합니다({duration:.1f}초). "
                "한 명이 말하는 1분 안팎 구간으로 잘라 주세요."
            )

    validate_output_directory(job_dir)
    if args.target_duration is not None and (
        not math.isfinite(args.target_duration) or args.target_duration <= 0
    ):
        raise WorkflowError("--target-duration은 유한한 양수여야 합니다.")
    if not args.consent_confirmed:
        raise WorkflowError(
            "음성 복제·재사용 권한 확인에는 --consent-confirmed가 필요합니다."
        )
    if args.reference_video:
        if not (args.new_voice_name or "").strip():
            raise WorkflowError("--reference-video 사용 시 --new-voice-name이 필요합니다.")
        reference_video = args.reference_video.expanduser().resolve()
        if not reference_video.is_file():
            raise WorkflowError(f"레퍼런스 영상을 찾을 수 없습니다: {reference_video}")
        validate_reference_media(reference_video)
        if args.style_reference_video:
            raise WorkflowError(
                "새 clone 작업에는 --style-reference-video를 함께 사용할 수 없습니다."
            )
    elif args.style_reference_video:
        style_reference_video = args.style_reference_video.expanduser().resolve()
        if not style_reference_video.is_file():
            raise WorkflowError(
                f"스타일 레퍼런스 영상을 찾을 수 없습니다: {style_reference_video}"
            )
        validate_reference_media(style_reference_video)


def command_run(args: argparse.Namespace) -> int:
    job_dir = args.output_dir.expanduser().resolve()
    script_path = args.script.expanduser().resolve()
    if not script_path.is_file():
        raise WorkflowError(f"대본 파일을 찾을 수 없습니다: {script_path}")
    script_text = script_path.read_text(encoding="utf-8").strip()
    validate_korean_only(script_text)
    plan_script(script_text, {"audio_metrics": {}})
    validate_run_preconditions(args, job_dir)
    client = ElevenLabsClient()
    verify_live_model(client)
    output_format, tier = choose_output_format(client)
    resolved_existing_voice: tuple[str, str] | None = None
    if not args.reference_video:
        resolved_existing_voice = resolve_cloud_voice(
            client,
            voice_id=args.voice_id,
            name=args.existing_voice_name,
        )
        verify_existing_voice(
            client,
            voice_id=resolved_existing_voice[0],
        )
        if not args.style_reference_video:
            registry_voice = find_registry_voice(
                voice_id=resolved_existing_voice[0],
            )
            profile_path = Path(
                str(registry_voice.get("profile_path") or "")
                if registry_voice
                else ""
            )
            if not registry_voice or not profile_path.is_file():
                raise WorkflowError(
                    "이 기존 보이스에는 저장된 속도·감정 프로필이 없습니다. "
                    "--style-reference-video를 함께 제공하세요."
                )

    initialize_job_directory(job_dir)
    copied_script = job_dir / "input" / "script.txt"
    shutil.copy2(script_path, copied_script)

    job: dict[str, Any] = {
        "version": 1,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "initializing",
        "model_id": MODEL_ID,
        "max_attempts_per_batch": MAX_ATTEMPTS_PER_BATCH,
        "target_duration_seconds": args.target_duration,
        "user_listening_approval_required": True,
        "voice_retention": "keep",
        "script_path": relative_to_job(copied_script, job_dir),
        "finalized": False,
        "retention_notice": (
            "작업 폴더에는 레퍼런스 파생 음성·전사·실패 후보가 남습니다. "
            "최종 확인 뒤 사용자가 작업 폴더를 직접 보존하거나 삭제합니다."
        ),
        "rights_attestation": {
            "confirmed": True,
            "confirmed_at": utc_now(),
            "actor": "current_user_confirmed_via_cli",
            "scope": (
                "authorized_new_voice_clone"
                if args.reference_video
                else "authorized_existing_voice_reuse"
            ),
            "reference_source_sha256": (
                sha256_file(args.reference_video.expanduser().resolve())
                if args.reference_video
                else (
                    sha256_file(args.style_reference_video.expanduser().resolve())
                    if args.style_reference_video
                    else None
                )
            ),
        },
    }
    write_job(job_dir, job)
    job["api_output_format"] = output_format
    job["subscription_tier_detected"] = tier

    try:
        if args.reference_video:
            voice_name = (args.new_voice_name or "").strip()
            voice_id, profile = create_new_clone(
                client,
                reference_video=args.reference_video.expanduser().resolve(),
                voice_name=voice_name,
                job_dir=job_dir,
            )
            job["voice_source"] = "new_authorized_clone"
            job["voice_name"] = voice_name
        else:
            if resolved_existing_voice is None:
                raise WorkflowError("기존 보이스를 확인하지 못했습니다.")
            voice_id, voice_name = resolved_existing_voice
            profile = profile_for_existing_voice(
                voice_id=voice_id,
                style_reference_video=(
                    args.style_reference_video.expanduser().resolve()
                    if args.style_reference_video
                    else None
                ),
                client=client,
                job_dir=job_dir,
            )
            if args.style_reference_video:
                register_voice(
                    voice_id=voice_id,
                    name=voice_name,
                    profile=profile,
                    source_sha256=str(profile["source_sha256"]),
                    requires_verification=False,
                )
            job["voice_source"] = "existing_voice"
            job["voice_name"] = voice_name
    except (WorkflowError, AudioToolError, ApiError) as exc:
        job["status"] = "initialization_failed"
        job["last_error"] = {
            "created_at": utc_now(),
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
        write_job(job_dir, job)
        raise

    job["voice_id"] = voice_id
    atomic_write_json(job_dir / "reference_profile.json", profile)
    segments = plan_script(script_text, profile)
    plan = {
        "version": 1,
        "created_at": utc_now(),
        "model_id": MODEL_ID,
        "original_script": script_text,
        "segments": segments,
    }
    atomic_write_json(job_dir / "script_plan.json", plan)
    job["status"] = "planned"
    job["segment_count"] = len(segments)
    write_job(job_dir, job)
    return 0 if generate_pending_segments(client, job_dir=job_dir) else 2


def parse_segment_indices(value: str, segment_count: int) -> set[int]:
    if value.strip().lower() == "all":
        return set(range(1, segment_count + 1))
    result: set[int] = set()
    for item in value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            index = int(item)
        except ValueError as exc:
            raise WorkflowError(f"문장 번호가 올바르지 않습니다: {item}") from exc
        if index < 1 or index > segment_count:
            raise WorkflowError(f"문장 번호 범위를 벗어났습니다: {index}")
        result.add(index)
    if not result:
        raise WorkflowError("하나 이상의 문장 번호가 필요합니다.")
    return result


def approval_state_names(approval: dict[str, Any]) -> tuple[str, str]:
    approval_type = approval.get("approval_type")
    if approval_type == "delegated_automatic_qc":
        return "user_delegated_auto_qc_final", "delegated_auto_qc_approved"
    if approval_type == "human_listening":
        return "user_approved_final", "user_approved"
    raise WorkflowError(f"지원하지 않는 최종 승인 유형입니다: {approval_type}")


def expected_preview_text(plan: dict[str, Any]) -> str:
    return "\n".join(str(segment["spoken_text"]) for segment in plan["segments"])


def make_approval_id(
    *,
    approval_type: str,
    preview_revision: int,
    preview_sha256: str,
    confirmation: str,
    preview_wav_sha256: str,
    review_file_hashes: dict[str, str],
    expected_text: str,
) -> str:
    material = json.dumps(
        {
            "approval_type": approval_type,
            "preview_revision": preview_revision,
            "preview_mp3_sha256": preview_sha256,
            "preview_wav_sha256": preview_wav_sha256,
            "review_file_hashes": dict(sorted(review_file_hashes.items())),
            "expected_text_sha256": hashlib.sha256(
                expected_text.encode("utf-8")
            ).hexdigest(),
            "confirmation": confirmation,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


def selected_attempt_record(segment: dict[str, Any]) -> dict[str, Any]:
    selected_attempt = segment.get("selected_attempt")
    attempt = next(
        (
            item
            for item in segment.get("attempts", [])
            if item.get("attempt") == selected_attempt
        ),
        None,
    )
    if not isinstance(attempt, dict):
        raise WorkflowError(
            f"{segment['index']}번 문장의 선택 후보 기록을 찾을 수 없습니다."
        )
    return attempt


def is_coherent_job(job: dict[str, Any]) -> bool:
    return job.get("workflow") == "coherent_full_script_block"


def validate_coherent_take_integrity(
    job_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    """Validate the authoritative whole take and its persisted strict-QC proof."""
    if not is_coherent_job(job):
        raise WorkflowError("coherent 전체 테이크 작업이 아닙니다.")
    selected_take = job.get("selected_take")
    if not isinstance(selected_take, int) or selected_take < 1:
        raise WorkflowError("현재 선택된 coherent 전체 테이크가 없습니다.")
    attempt = next(
        (
            item
            for item in (job.get("attempts") or [])
            if isinstance(item, dict) and item.get("attempt") == selected_take
        ),
        None,
    )
    if not isinstance(attempt, dict):
        raise WorkflowError("선택된 coherent 전체 테이크 기록을 찾을 수 없습니다.")
    checks = attempt.get("checks")
    transcript_runs = attempt.get("transcript_runs")
    alignment_summary = attempt.get("forced_alignment")
    expected_variants = [(173, 0.0), (907, 0.1), (2027, 0.2)]
    if (
        attempt.get("strict_auto_pass") is not True
        or not isinstance(checks, dict)
        or not checks
        or not all(bool(value) for value in checks.values())
        or not isinstance(transcript_runs, list)
        or len(transcript_runs) != 3
        or [
            (run.get("seed"), run.get("temperature"))
            for run in transcript_runs
            if isinstance(run, dict)
        ]
        != expected_variants
        or not all(
            isinstance(run, dict) and run.get("passed") is True
            for run in transcript_runs
        )
        or not isinstance(alignment_summary, dict)
        or alignment_summary.get("passed") is not True
    ):
        raise WorkflowError(
            "선택된 coherent 전체 테이크의 3회 STT·정렬 하드 게이트 "
            "통과 증거가 완전하지 않습니다."
        )

    candidate_wav = job_dir / str(attempt.get("wav") or "")
    candidate_mp3 = job_dir / str(attempt.get("mp3") or "")
    preview_wav = job_dir / str(job.get("review_preview_wav") or "")
    preview_mp3 = job_dir / str(job.get("review_preview_mp3") or "")
    if not all(
        path.is_file()
        for path in (candidate_wav, candidate_mp3, preview_wav, preview_mp3)
    ):
        raise WorkflowError("coherent 전체 테이크 후보 또는 미리보기 파일이 없습니다.")
    candidate_wav_hash = sha256_file(candidate_wav)
    candidate_mp3_hash = sha256_file(candidate_mp3)
    if (
        attempt.get("wav_sha256") != candidate_wav_hash
        or attempt.get("mp3_sha256") != candidate_mp3_hash
        or sha256_file(preview_wav) != candidate_wav_hash
        or sha256_file(preview_mp3) != candidate_mp3_hash
        or job.get("review_preview_wav_sha256") != candidate_wav_hash
        or job.get("review_preview_sha256") != candidate_mp3_hash
    ):
        raise WorkflowError(
            "coherent 전체 테이크 후보와 무변형 미리보기의 해시가 일치하지 않습니다."
        )

    attempt_dir = candidate_wav.parent
    for record_name in ("attempt.json", "qc.json"):
        record_path = attempt_dir / record_name
        if not record_path.is_file() or load_json(record_path) != attempt:
            raise WorkflowError(
                f"coherent 전체 테이크 증거 기록이 현재 선택본과 다릅니다: {record_name}"
            )
    for run_number, run in enumerate(transcript_runs, 1):
        raw_path = attempt_dir / f"transcript-{run_number}.json"
        if not raw_path.is_file():
            raise WorkflowError(
                f"coherent 전체 테이크 {run_number}회 STT 원본 증거가 없습니다."
            )
        raw = load_json(raw_path)
        if (
            str(raw.get("text") or "") != str(run.get("transcript_text") or "")
            or str(raw.get("language_code") or "")
            != str(run.get("language_code") or "")
        ):
            raise WorkflowError(
                f"coherent 전체 테이크 {run_number}회 STT 증거가 기록과 다릅니다."
            )
    alignment_path = attempt_dir / "forced_alignment.json"
    if not alignment_path.is_file():
        raise WorkflowError("coherent 전체 테이크 강제 정렬 원본 증거가 없습니다.")
    alignment = load_json(alignment_path)
    expected_text = str(
        plan.get("full_spoken_text") or expected_preview_text(plan).replace("\n", " ")
    )
    audio_metrics = analyze_wav(candidate_wav, transcript=expected_text)
    alignment_integrity = forced_alignment_integrity(
        expected_text,
        alignment,
        audio_duration_seconds=float(audio_metrics.get("duration_seconds") or 0.0),
    )
    if (
        alignment_integrity.get("complete") is not True
        or alignment_integrity.get("timing_valid") is not True
    ):
        raise WorkflowError("coherent 전체 테이크 강제 정렬 증거가 현재 대본과 다릅니다.")

    for segment in plan.get("segments") or []:
        index = int(segment.get("index") or 0)
        if segment.get("selected_take") != selected_take:
            raise WorkflowError(
                f"{index}번 검토 클립이 현재 coherent 전체 테이크와 연결되지 않았습니다."
            )
        for key in ("selected_wav", "selected_mp3"):
            path = job_dir / str(segment.get(key) or "")
            if not path.is_file():
                raise WorkflowError(
                    f"{index}번 정렬 기반 검토 클립이 없습니다: {key}"
                )
    return {
        "selected_take": selected_take,
        "candidate_wav_sha256": candidate_wav_hash,
        "candidate_mp3_sha256": candidate_mp3_hash,
        "strict_checks": checks,
        "transcript_run_count": len(transcript_runs),
        "forced_alignment_passed": True,
    }


def validate_current_review_integrity(
    job_dir: Path,
    job: dict[str, Any],
    *,
    supplied_preview_sha256: str,
) -> tuple[Path, Path, str, dict[str, str]]:
    preview_wav = job_dir / str(job.get("review_preview_wav") or "")
    preview_mp3 = job_dir / str(job.get("review_preview_mp3") or "")
    expected_hash = str(job.get("review_preview_sha256") or "")
    supplied_hash = supplied_preview_sha256.strip().lower()
    if not preview_wav.is_file() or not preview_mp3.is_file():
        raise WorkflowError("승인할 전체 미리보기 파일이 없습니다.")
    review_file_hashes = job.get("review_file_hashes")
    if not isinstance(review_file_hashes, dict) or not review_file_hashes:
        raise WorkflowError("현재 미리보기 파일 무결성 기록이 없습니다.")
    normalized_hashes: dict[str, str] = {}
    for relative_path, recorded_hash in review_file_hashes.items():
        review_file = job_dir / str(relative_path)
        recorded_hash_text = str(recorded_hash)
        if (
            not review_file.is_file()
            or sha256_file(review_file) != recorded_hash_text
        ):
            raise WorkflowError(
                "미리보기 또는 문장별 선택본이 생성 후 변경되었습니다. "
                "최신 미리보기를 다시 생성해야 합니다."
            )
        normalized_hashes[str(relative_path)] = recorded_hash_text
    current_hash = sha256_file(preview_mp3)
    if not expected_hash or supplied_hash != expected_hash or current_hash != expected_hash:
        raise WorkflowError(
            "승인 대상 미리보기가 현재 리비전과 일치하지 않습니다."
        )
    return preview_wav, preview_mp3, expected_hash, normalized_hashes


def forced_alignment_integrity(
    expected_text: str,
    alignment: dict[str, Any],
    *,
    audio_duration_seconds: float,
) -> dict[str, Any]:
    characters = [
        item
        for item in (alignment.get("characters") or [])
        if isinstance(item, dict)
    ]
    aligned_text = "".join(str(item.get("text") or "") for item in characters)
    previous_start = -1.0
    timing_valid = bool(characters)
    for item in characters:
        start = item.get("start")
        end = item.get("end")
        character_text = str(item.get("text") or "")
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
            and end <= audio_duration_seconds + 0.5
        ):
            timing_valid = False
            break
        previous_start = float(start)
    return {
        "aligned_text": aligned_text,
        "alignment_loss": alignment.get("loss"),
        "complete": (
            normalize_for_comparison(aligned_text)
            == normalize_for_comparison(expected_text)
        ),
        "timing_valid": timing_valid,
    }


def validate_delegated_segment_qc(
    job_dir: Path,
    plan: dict[str, Any],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    expected_variants = list(FOCUS_TRANSCRIPTION_VARIANTS)
    for segment in plan["segments"]:
        if segment.get("status") != "auto_passed_awaiting_user":
            raise WorkflowError(
                f"{segment['index']}번 문장은 자동 검수 통과 상태가 아닙니다."
            )
        attempt = selected_attempt_record(segment)
        qc = attempt.get("qc")
        if not isinstance(qc, dict) or not qc.get("auto_pass"):
            raise WorkflowError(
                f"{segment['index']}번 문장의 선택 후보가 자동 검수를 통과하지 않았습니다."
            )
        for key, value in (qc.get("checks") or {}).items():
            if not value:
                raise WorkflowError(
                    f"{segment['index']}번 문장의 자동 검수 항목이 실패했습니다: {key}"
                )
        focus_phrases = list(segment.get("pronunciation_focus_phrases") or [])
        focus_results = list(attempt.get("pronunciation_focus_results") or [])
        focus_evidence_hashes: dict[str, str] = {}
        if focus_phrases:
            if [item.get("phrase") for item in focus_results] != focus_phrases:
                raise WorkflowError(
                    f"{segment['index']}번 문장의 집중 발음 검증 결과가 현재 설정과 "
                    "일치하지 않습니다."
                )
            for result_index, result in enumerate(focus_results, 1):
                phrase = str(result.get("phrase") or "")
                runs = list(result.get("runs") or [])
                observed_variants = [
                    (run.get("seed"), run.get("temperature")) for run in runs
                ]
                if (
                    not result.get("passed")
                    or observed_variants != expected_variants
                    or not all(
                        bool(run.get("passed"))
                        and str(run.get("language_code") or "").lower()
                        in {"ko", "kor"}
                        and normalize_for_comparison(
                            str(run.get("canonical_text") or "")
                        )
                        == normalize_for_comparison(phrase)
                        and normalize_lexical_content(
                            str(run.get("canonical_text") or "")
                        )
                        == normalize_lexical_content(phrase)
                        for run in runs
                    )
                ):
                    raise WorkflowError(
                        f"{segment['index']}번 문장의 집중 발음 3회 합의 검증이 "
                        f"완료되지 않았습니다: {result.get('phrase')}"
                    )
                focus_dir = (
                    job_dir
                    / str(attempt.get("wav") or "")
                ).parent / "focus_pronunciation" / f"{result_index:02d}"
                required_evidence = [
                    focus_dir / "clip.wav",
                    focus_dir / "result.json",
                    *[
                        focus_dir / f"transcript-{run_index}.json"
                        for run_index in range(1, 4)
                    ],
                ]
                if not all(path.is_file() for path in required_evidence):
                    raise WorkflowError(
                        f"{segment['index']}번 문장의 집중 발음 증거 파일이 누락됐습니다: "
                        f"{phrase}"
                    )
                if load_json(focus_dir / "result.json") != result:
                    raise WorkflowError(
                        f"{segment['index']}번 문장의 집중 발음 결과 파일이 "
                        f"선택 후보 기록과 일치하지 않습니다: {phrase}"
                    )
                for run_index, run in enumerate(runs, 1):
                    raw_transcript = load_json(
                        focus_dir / f"transcript-{run_index}.json"
                    )
                    if (
                        str(raw_transcript.get("text") or "")
                        != str(run.get("transcript_text") or "")
                        or str(raw_transcript.get("language_code") or "")
                        != str(run.get("language_code") or "")
                    ):
                        raise WorkflowError(
                            f"{segment['index']}번 문장의 집중 발음 전사 증거가 "
                            f"기록과 일치하지 않습니다: {phrase}, {run_index}회"
                        )
                for path in required_evidence:
                    focus_evidence_hashes[relative_to_job(path, job_dir)] = (
                        sha256_file(path)
                    )
        selected_wav = job_dir / str(segment.get("selected_wav") or "")
        selected_mp3 = job_dir / str(segment.get("selected_mp3") or "")
        if not selected_wav.is_file() or not selected_mp3.is_file():
            raise WorkflowError(
                f"{segment['index']}번 문장의 선택 음성 파일이 없습니다."
            )
        candidate_wav = job_dir / str(attempt.get("wav") or "")
        candidate_mp3 = job_dir / str(attempt.get("mp3") or "")
        if (
            not candidate_wav.is_file()
            or not candidate_mp3.is_file()
            or sha256_file(selected_wav) != sha256_file(candidate_wav)
            or sha256_file(selected_mp3) != sha256_file(candidate_mp3)
        ):
            raise WorkflowError(
                f"{segment['index']}번 문장의 검수본이 선택 후보와 일치하지 않습니다."
            )
        summaries.append(
            {
                "index": segment["index"],
                "selected_attempt": segment["selected_attempt"],
                "base_auto_qc_passed": True,
                "pronunciation_focus_phrases": focus_phrases,
                "focused_pronunciation_consensus_passed": (
                    all(bool(item.get("passed")) for item in focus_results)
                    if focus_phrases
                    else None
                ),
                "focused_pronunciation_evidence_sha256": focus_evidence_hashes,
            }
        )
    return summaries


def wav_pcm_fingerprint(path: Path) -> dict[str, Any]:
    hasher = hashlib.sha256()
    with wave.open(str(path), "rb") as wav_file:
        metadata = {
            "channels": wav_file.getnchannels(),
            "sample_width": wav_file.getsampwidth(),
            "sample_rate": wav_file.getframerate(),
            "frame_count": wav_file.getnframes(),
        }
        while True:
            frames = wav_file.readframes(65_536)
            if not frames:
                break
            hasher.update(frames)
    metadata["pcm_sha256"] = hasher.hexdigest()
    return metadata


def is_nonempty_ordered_subsequence(candidate: str, expected: str) -> bool:
    if not candidate or candidate == expected:
        return False
    expected_iterator = iter(expected)
    return all(
        any(expected_character == character for expected_character in expected_iterator)
        for character in candidate
    )


def verify_segment_chunk_preview_fallback(
    client: ElevenLabsClient,
    *,
    job_dir: Path,
    preview_wav: Path,
    plan: dict[str, Any],
    evidence_dir: Path,
) -> dict[str, Any]:
    selected_wavs = [
        job_dir / str(segment.get("selected_wav") or "")
        for segment in plan["segments"]
    ]
    if not selected_wavs or not all(path.is_file() for path in selected_wavs):
        raise WorkflowError("장문 합본 보조 검증에 필요한 문장별 WAV가 없습니다.")

    preview_stored_pcm = wav_pcm_fingerprint(preview_wav)
    preview_pcm = canonical_pcm_fingerprint([preview_wav])
    selected_segments_pcm = canonical_pcm_fingerprint(selected_wavs)
    comparable_pcm_fields = (
        "channels",
        "sample_width",
        "sample_rate",
        "frame_count",
        "pcm_sha256",
    )
    pcm_matches = all(
        preview_pcm[field] == selected_segments_pcm[field]
        for field in comparable_pcm_fields
    )
    preview_metrics = analyze_wav(
        preview_wav,
        transcript=expected_preview_text(plan),
    )
    aggregate_checks = {
        "preview_format_is_mono_48khz_24bit": (
            preview_stored_pcm["channels"] == 1
            and preview_stored_pcm["sample_width"] == 3
            and preview_stored_pcm["sample_rate"] == 48_000
        ),
        "preview_frame_count_matches_selected_segments": (
            preview_pcm["frame_count"]
            == selected_segments_pcm["frame_count"]
        ),
        "preview_pcm_matches_selected_segments": pcm_matches,
        "preview_no_material_clipping": float(
            preview_metrics.get("clipping_ratio") or 0.0
        )
        <= 0.001,
        "preview_nonempty_active_audio": float(
            preview_metrics.get("active_speech_seconds") or 0.0
        )
        > 0.1,
    }
    if not all(aggregate_checks.values()):
        return {
            "auto_pass": False,
            "checks": aggregate_checks,
            "preview_stored_pcm": preview_stored_pcm,
            "preview_pcm": preview_pcm,
            "selected_segments_pcm": selected_segments_pcm,
            "preview_audio_metrics": preview_metrics,
            "segment_results": [],
            "evidence_files": {},
        }

    chunk_root = evidence_dir / "segment-chunks"
    segment_results: list[dict[str, Any]] = []
    evidence_files: dict[str, str] = {}
    for segment, wav_path in zip(plan["segments"], selected_wavs):
        index = int(segment["index"])
        expected_text = str(segment["spoken_text"])
        chunk_dir = chunk_root / f"{index:03d}"
        chunk_dir.mkdir(parents=True, exist_ok=True)
        transcription_runs: list[dict[str, Any]] = []
        for run_index, (seed, temperature) in enumerate(
            FOCUS_TRANSCRIPTION_VARIANTS,
            1,
        ):
            transcript = client.transcribe(
                wav_path,
                seed=seed,
                temperature=temperature,
            )
            transcript_text = str(transcript.get("text") or "")
            canonical_text = canonicalize_stt_notation(
                expected_text,
                transcript_text,
            )
            language_code = (
                str(transcript.get("language_code"))
                if transcript.get("language_code")
                else None
            )
            run_checks = {
                "exact_hangul_transcript": (
                    normalize_for_comparison(canonical_text)
                    == normalize_for_comparison(expected_text)
                ),
                "no_unexpected_lexical_content": (
                    normalize_lexical_content(canonical_text)
                    == normalize_lexical_content(expected_text)
                ),
                "korean_language_confirmed": (
                    language_code is not None
                    and language_code.lower() in {"ko", "kor"}
                ),
            }
            transcript_path = chunk_dir / f"transcript-{run_index}.json"
            atomic_write_json(transcript_path, transcript)
            evidence_files[relative_to_job(transcript_path, job_dir)] = (
                sha256_file(transcript_path)
            )
            transcription_runs.append(
                {
                    "run": run_index,
                    "seed": seed,
                    "temperature": temperature,
                    "transcript_text": transcript_text,
                    "canonical_transcript_text": canonical_text,
                    "language_code": language_code,
                    "checks": run_checks,
                    "evidence": relative_to_job(
                        transcript_path,
                        job_dir,
                    ),
                }
            )

        metrics = analyze_wav(wav_path, transcript=expected_text)
        checks: dict[str, bool] = {
            "exact_hangul_transcript": all(
                run["checks"]["exact_hangul_transcript"]
                for run in transcription_runs
            ),
            "no_unexpected_lexical_content": all(
                run["checks"]["no_unexpected_lexical_content"]
                for run in transcription_runs
            ),
            "korean_language_confirmed": all(
                run["checks"]["korean_language_confirmed"]
                for run in transcription_runs
            ),
            "no_material_clipping": float(
                metrics.get("clipping_ratio") or 0.0
            )
            <= 0.001,
            "nonempty_active_audio": float(
                metrics.get("active_speech_seconds") or 0.0
            )
            > 0.1,
        }
        transcript_gate_passed = all(
            checks[key]
            for key in (
                "exact_hangul_transcript",
                "no_unexpected_lexical_content",
                "korean_language_confirmed",
            )
        )
        if transcript_gate_passed:
            alignment = client.forced_alignment(wav_path, expected_text)
            alignment_qc = forced_alignment_integrity(
                expected_text,
                alignment,
                audio_duration_seconds=float(
                    metrics.get("duration_seconds") or 0.0
                ),
            )
            alignment_path = chunk_dir / "forced_alignment.json"
            atomic_write_json(alignment_path, alignment)
            evidence_files[relative_to_job(alignment_path, job_dir)] = (
                sha256_file(alignment_path)
            )
        else:
            alignment_qc = {
                "complete": False,
                "timing_valid": False,
                "skipped_due_to_transcript_failure": True,
            }
        checks["forced_alignment_complete"] = bool(
            alignment_qc["complete"]
        )
        checks["forced_alignment_timing_valid"] = bool(
            alignment_qc["timing_valid"]
        )
        segment_results.append(
            {
                "index": index,
                "auto_pass": all(checks.values()),
                "checks": checks,
                "transcript_consensus_required": len(
                    FOCUS_TRANSCRIPTION_VARIANTS
                ),
                "transcription_runs": transcription_runs,
                "alignment": alignment_qc,
                "audio_metrics": metrics,
            }
        )

    aggregate_checks.update(
        {
            "exact_hangul_transcript": all(
                item["checks"]["exact_hangul_transcript"]
                for item in segment_results
            ),
            "no_unexpected_lexical_content": all(
                item["checks"]["no_unexpected_lexical_content"]
                for item in segment_results
            ),
            "korean_language_confirmed": all(
                item["checks"]["korean_language_confirmed"]
                for item in segment_results
            ),
            "forced_alignment_complete": all(
                item["checks"]["forced_alignment_complete"]
                for item in segment_results
            ),
            "forced_alignment_timing_valid": all(
                item["checks"]["forced_alignment_timing_valid"]
                for item in segment_results
            ),
            "no_material_clipping": all(
                item["checks"]["no_material_clipping"]
                for item in segment_results
            ),
            "nonempty_active_audio": all(
                item["checks"]["nonempty_active_audio"]
                for item in segment_results
            ),
        }
    )
    return {
        "auto_pass": all(aggregate_checks.values()),
        "checks": aggregate_checks,
        "preview_stored_pcm": preview_stored_pcm,
        "preview_pcm": preview_pcm,
        "selected_segments_pcm": selected_segments_pcm,
        "preview_audio_metrics": preview_metrics,
        "segment_results": segment_results,
        "evidence_files": evidence_files,
    }


def verify_full_preview_automatic_qc(
    client: ElevenLabsClient,
    *,
    job_dir: Path,
    preview_wav: Path,
    expected_text: str,
    approval_id: str,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    evidence_dir = job_dir / "review" / "approval-evidence" / approval_id
    evidence_dir.mkdir(parents=True, exist_ok=True)
    transcript = client.transcribe(
        preview_wav,
        seed=173,
        temperature=0.0,
    )
    transcript_text = str(transcript.get("text") or "")
    canonical_text = canonicalize_stt_notation(expected_text, transcript_text)
    language_code = (
        str(transcript.get("language_code"))
        if transcript.get("language_code")
        else None
    )
    transcript_path = evidence_dir / "full_preview_transcript.json"
    atomic_write_json(transcript_path, transcript)
    transcript_checks = {
        "exact_hangul_transcript": (
            normalize_for_comparison(canonical_text)
            == normalize_for_comparison(expected_text)
        ),
        "no_unexpected_lexical_content": (
            normalize_lexical_content(canonical_text)
            == normalize_lexical_content(expected_text)
        ),
        "korean_language_confirmed": (
            language_code is not None and language_code.lower() in {"ko", "kor"}
        ),
    }
    expected_lexical = normalize_lexical_content(expected_text)
    transcript_lexical = normalize_lexical_content(canonical_text)
    fallback_eligibility = {
        "korean_language_confirmed": transcript_checks[
            "korean_language_confirmed"
        ],
        "nonempty_long_form_transcript": bool(transcript_lexical),
        "diagnostic_order_preserving_omission_only": (
            is_nonempty_ordered_subsequence(
                transcript_lexical,
                expected_lexical,
            )
        ),
        "fresh_per_segment_transcript_consensus_required": len(
            FOCUS_TRANSCRIPTION_VARIANTS
        ),
    }
    fallback_allowed = bool(
        plan is not None
        and fallback_eligibility["korean_language_confirmed"]
        and fallback_eligibility["nonempty_long_form_transcript"]
    )
    if not all(transcript_checks.values()):
        if fallback_allowed:
            fallback = verify_segment_chunk_preview_fallback(
                client,
                job_dir=job_dir,
                preview_wav=preview_wav,
                plan=plan,
                evidence_dir=evidence_dir,
            )
            result = {
                "created_at": utc_now(),
                "approval_id": approval_id,
                "auto_pass": fallback["auto_pass"],
                "verification_strategy": (
                    "pcm_locked_segment_chunk_fallback"
                ),
                "checks": fallback["checks"],
                "long_form_transcript_diagnostic": {
                    "checks": transcript_checks,
                    "fallback_eligibility": fallback_eligibility,
                    "transcript_text": transcript_text,
                    "canonical_transcript_text": canonical_text,
                    "language_code": language_code,
                },
                "alignment": {
                    "mode": "fresh_per_segment_forced_alignment",
                    "complete": bool(
                        fallback["checks"].get(
                            "forced_alignment_complete",
                            False,
                        )
                    ),
                    "timing_valid": bool(
                        fallback["checks"].get(
                            "forced_alignment_timing_valid",
                            False,
                        )
                    ),
                },
                "audio_metrics": fallback["preview_audio_metrics"],
                "preview_stored_pcm": fallback["preview_stored_pcm"],
                "preview_pcm": fallback["preview_pcm"],
                "selected_segments_pcm": fallback[
                    "selected_segments_pcm"
                ],
                "segment_results": fallback["segment_results"],
                "evidence_files": {
                    relative_to_job(
                        transcript_path,
                        job_dir,
                    ): sha256_file(transcript_path),
                    **fallback["evidence_files"],
                },
            }
            verification_path = evidence_dir / "verification.json"
            atomic_write_json(verification_path, result)
            result["verification_record"] = relative_to_job(
                verification_path,
                job_dir,
            )
            result["verification_record_sha256"] = sha256_file(
                verification_path
            )
            if result["auto_pass"]:
                return result
            failed_checks = [
                key
                for key, value in fallback["checks"].items()
                if not value
            ]
            raise WorkflowError(
                "전체 미리보기 장문 보조 검증이 실패했습니다: "
                + ", ".join(failed_checks)
            )
        result = {
            "created_at": utc_now(),
            "approval_id": approval_id,
            "auto_pass": False,
            "stage": "full_preview_transcript",
            "checks": transcript_checks,
            "transcript_text": transcript_text,
            "canonical_transcript_text": canonical_text,
            "language_code": language_code,
            "fallback_eligibility": fallback_eligibility,
            "evidence_files": {
                relative_to_job(transcript_path, job_dir): sha256_file(
                    transcript_path
                ),
            },
        }
        atomic_write_json(evidence_dir / "verification.json", result)
        failed_checks = [
            key for key, value in transcript_checks.items() if not value
        ]
        raise WorkflowError(
            "전체 미리보기 전사 검증이 실패했습니다: "
            + ", ".join(failed_checks)
        )

    alignment = client.forced_alignment(preview_wav, expected_text)
    metrics = analyze_wav(preview_wav, transcript=canonical_text)
    alignment_qc = forced_alignment_integrity(
        expected_text,
        alignment,
        audio_duration_seconds=float(metrics.get("duration_seconds") or 0.0),
    )
    checks = {
        **transcript_checks,
        "forced_alignment_complete": alignment_qc["complete"],
        "forced_alignment_timing_valid": alignment_qc["timing_valid"],
        "no_material_clipping": float(metrics.get("clipping_ratio") or 0.0)
        <= 0.001,
        "nonempty_active_audio": float(metrics.get("active_speech_seconds") or 0.0)
        > 0.1,
    }
    alignment_path = evidence_dir / "full_preview_forced_alignment.json"
    atomic_write_json(alignment_path, alignment)
    result = {
        "created_at": utc_now(),
        "approval_id": approval_id,
        "auto_pass": all(checks.values()),
        "checks": checks,
        "transcript_text": transcript_text,
        "canonical_transcript_text": canonical_text,
        "language_code": language_code,
        "alignment": alignment_qc,
        "audio_metrics": metrics,
        "evidence_files": {
            relative_to_job(transcript_path, job_dir): sha256_file(transcript_path),
            relative_to_job(alignment_path, job_dir): sha256_file(alignment_path),
        },
    }
    verification_path = evidence_dir / "verification.json"
    atomic_write_json(verification_path, result)
    result["verification_record"] = relative_to_job(verification_path, job_dir)
    result["verification_record_sha256"] = sha256_file(verification_path)
    if not result["auto_pass"]:
        failed_checks = [key for key, value in checks.items() if not value]
        raise WorkflowError(
            "전체 미리보기 강화 자동 검증이 실패했습니다: "
            + ", ".join(failed_checks)
        )
    return result


def _commit_final_state(
    job_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    final_status, segment_status = approval_state_names(approval)
    for segment in plan["segments"]:
        segment["status"] = segment_status
    approval_id = approval.get("approval_id")
    approval_records = job.setdefault("approval_records", [])
    if not any(item.get("approval_id") == approval_id for item in approval_records):
        approval_records.append(approval)
    if approval.get("approval_type") == "human_listening":
        user_approvals = job.setdefault("user_approvals", [])
        if not any(item.get("approval_id") == approval_id for item in user_approvals):
            user_approvals.append(approval)
    else:
        job["user_listening_approval_required"] = False
        job["user_listening_waived"] = True
    job["approval_type"] = approval.get("approval_type")
    job["human_listening_completed"] = approval.get(
        "human_listening_completed"
    )
    job["approval_id"] = approval_id
    job["status"] = final_status
    job["finalized"] = True
    job["final_wav"] = "final/final.wav"
    job["final_mp3"] = "final/final.mp3"
    atomic_write_json(job_dir / "script_plan.json", plan)
    write_job(job_dir, job)


def final_artifact_paths(
    final_dir: Path,
    plan: dict[str, Any],
) -> list[Path]:
    return [
        final_dir / "final.wav",
        final_dir / "final.mp3",
        final_dir / "script.txt",
        *[
            final_dir / "segments" / f"{int(segment['index']):03d}.{extension}"
            for segment in plan["segments"]
            for extension in ("wav", "mp3")
        ],
    ]


def finalize_job(
    job_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
    approval: dict[str, Any],
) -> None:
    final_dir = job_dir / "final"
    final_status, segment_status = approval_state_names(approval)
    coherent = is_coherent_job(job)
    coherent_take_qc = (
        validate_coherent_take_integrity(job_dir, job, plan)
        if coherent
        else None
    )
    if final_dir.exists():
        report = load_json(final_dir / "qc_report.json")
        required_final_files = final_artifact_paths(final_dir, plan)
        final_file_hashes = report.get("final_file_hashes")
        final_hashes_valid = isinstance(final_file_hashes, dict) and all(
            path.is_file()
            and final_file_hashes.get(str(path.relative_to(final_dir)))
            == sha256_file(path)
            for path in required_final_files
        )
        coherent_final_matches = (
            (
                sha256_file(final_dir / "final.wav")
                == sha256_file(job_dir / str(job["review_preview_wav"]))
                and sha256_file(final_dir / "final.mp3")
                == sha256_file(job_dir / str(job["review_preview_mp3"]))
            )
            if coherent
            else True
        )
        if (
            report.get("status") == final_status
            and report.get("approval_id") == approval.get("approval_id")
            and report.get("preview_sha256") == approval["preview_sha256"]
            and report.get("review_file_hashes")
            == approval["review_file_hashes"]
            and final_hashes_valid
            and coherent_final_matches
        ):
            _commit_final_state(job_dir, job, plan, approval)
            return
        raise WorkflowError(
            "기존 final 폴더가 현재 미리보기 승인과 일치하지 않습니다. "
            "파일을 덮어쓰지 않았습니다."
        )

    staging_dir = job_dir / f".final-staging-{secrets.token_hex(6)}"
    staging_segments_dir = staging_dir / "segments"
    staging_segments_dir.mkdir(parents=True, exist_ok=False)
    try:
        segment_wavs: list[Path] = []
        for segment in plan["segments"]:
            index = int(segment["index"])
            source_wav = job_dir / str(segment["selected_wav"])
            source_mp3 = job_dir / str(segment["selected_mp3"])
            destination_wav = staging_segments_dir / f"{index:03d}.wav"
            destination_mp3 = staging_segments_dir / f"{index:03d}.mp3"
            shutil.copy2(source_wav, destination_wav)
            shutil.copy2(source_mp3, destination_mp3)
            segment_wavs.append(destination_wav)
        if coherent:
            preview_wav = job_dir / str(job["review_preview_wav"])
            preview_mp3 = job_dir / str(job["review_preview_mp3"])
            final_wav = staging_dir / "final.wav"
            final_mp3 = staging_dir / "final.mp3"
            shutil.copy2(preview_wav, final_wav)
            shutil.copy2(preview_mp3, final_mp3)
            if (
                sha256_file(final_wav) != sha256_file(preview_wav)
                or sha256_file(final_mp3) != sha256_file(preview_mp3)
            ):
                raise WorkflowError(
                    "coherent 전체 테이크 미리보기를 최종본으로 무변형 보존하지 못했습니다."
                )
        else:
            final_wav = concatenate_wavs(segment_wavs, staging_dir / "final.wav")
            wav_to_mp3(final_wav, staging_dir / "final.mp3")
        shutil.copy2(job_dir / str(job["script_path"]), staging_dir / "script.txt")
        final_file_hashes = {
            str(path.relative_to(staging_dir)): sha256_file(path)
            for path in final_artifact_paths(staging_dir, plan)
        }
        delegated = approval.get("approval_type") == "delegated_automatic_qc"
        limitations = [
            "자동 STT·정렬·속도 검수는 자연스러움·감정·음색 동일성을 "
            "수학적으로 완전히 보증하지 않는다.",
        ]
        if delegated:
            limitations.append(
                "사용자는 전체 미리보기 직접 청취를 생략했으며, 최종화는 "
                "명시적으로 위임된 강화 자동 검증 결과다."
            )
        else:
            limitations.append(
                "최종 상태는 사용자가 전체 미리보기를 직접 듣고 승인한 결과다."
            )
        if coherent:
            segment_reports = [
                {
                    "index": segment["index"],
                    "spoken_text": segment["spoken_text"],
                    "selected_take": segment["selected_take"],
                    "status": segment_status,
                    "alignment_interval": segment.get("alignment_interval"),
                    "scope": "alignment_derived_review_clip_only",
                }
                for segment in plan["segments"]
            ]
        else:
            segment_reports = [
                {
                    "index": segment["index"],
                    "spoken_text": segment["spoken_text"],
                    "selected_attempt": segment["selected_attempt"],
                    "status": segment_status,
                    "selected_qc": selected_attempt_record(segment)["qc"],
                    "pronunciation_focus_phrases": segment.get(
                        "pronunciation_focus_phrases",
                        [],
                    ),
                    "pronunciation_focus_results": selected_attempt_record(
                        segment
                    ).get("pronunciation_focus_results", []),
                }
                for segment in plan["segments"]
            ]
        qc_report = {
            "created_at": utc_now(),
            "workflow": job.get("workflow"),
            "status": final_status,
            "approval_id": approval.get("approval_id"),
            "approval_type": approval.get("approval_type"),
            "human_listening_completed": approval.get(
                "human_listening_completed"
            ),
            "voice_id": job["voice_id"],
            "voice_name": job["voice_name"],
            "model_id": approval.get("model_id") or job["model_id"],
            "api_output_format": job["api_output_format"],
            "preview_revision": approval["preview_revision"],
            "preview_sha256": approval["preview_sha256"],
            "review_file_hashes": approval["review_file_hashes"],
            "final_file_hashes": final_file_hashes,
            "approval_records": [*job.get("approval_records", []), approval],
            "delegated_auto_qc_verification": approval.get(
                "delegated_auto_qc_verification"
            ),
            "prosody_listening_qc_evidence": approval.get(
                "prosody_listening_qc_evidence"
            ),
            "coherent_take_qc": coherent_take_qc,
            "authoritative_final_source": (
                "review/full_preview.wav_byte_preserved"
                if coherent
                else "concatenated_selected_sentence_clips"
            ),
            "segments": segment_reports,
            "limitations": limitations,
        }
        atomic_write_json(staging_dir / "qc_report.json", qc_report)
        staging_dir.replace(final_dir)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir)

    _commit_final_state(job_dir, job, plan, approval)


def command_approve(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        return _command_approve_locked(args, job_dir)


def _command_approve_locked(args: argparse.Namespace, job_dir: Path) -> int:
    job = load_json(job_dir / "job.json")
    plan = load_json(job_dir / "script_plan.json")
    if job.get("finalized"):
        raise WorkflowError("이미 최종 승인된 작업입니다.")
    if job.get("status") != "awaiting_user_listening_approval":
        raise WorkflowError(
            "현재 작업은 전체 미리보기 청취 승인 대기 상태가 아닙니다."
        )
    confirmation = args.confirmation.strip()
    if confirmation != LISTENING_APPROVAL_CONFIRMATION:
        raise WorkflowError(
            "청취 승인 문구가 정확하지 않습니다. 사용자가 실제로 들은 뒤 다음 문구를 "
            f"그대로 기록하세요: {LISTENING_APPROVAL_CONFIRMATION}"
        )
    selected = parse_segment_indices(args.segments, len(plan["segments"]))
    if selected != set(range(1, len(plan["segments"]) + 1)):
        raise WorkflowError("최종 확정은 현재 전체 미리보기의 모든 문장만 승인할 수 있습니다.")
    preview_wav, _, expected_hash, review_file_hashes = validate_current_review_integrity(
        job_dir,
        job,
        supplied_preview_sha256=args.preview_sha256,
    )
    prosody_qc_evidence = validate_current_prosody_qc(job_dir, job, plan)
    coherent_take_qc = (
        validate_coherent_take_integrity(job_dir, job, plan)
        if is_coherent_job(job)
        else None
    )
    approval = {
        "created_at": utc_now(),
        "approval_type": "human_listening",
        "human_listening_completed": True,
        "model_id": job.get("selected_model_id") or job["model_id"],
        "approval_id": make_approval_id(
            approval_type="human_listening",
            preview_revision=int(job["review_revision"]),
            preview_sha256=expected_hash,
            confirmation=confirmation,
            preview_wav_sha256=sha256_file(preview_wav),
            review_file_hashes=review_file_hashes,
            expected_text=expected_preview_text(plan),
        ),
        "segments": sorted(selected),
        "confirmation": confirmation,
        "preview_revision": int(job["review_revision"]),
        "preview_sha256": expected_hash,
        "review_file_hashes": review_file_hashes,
        "prosody_listening_qc_evidence": prosody_qc_evidence,
        "coherent_take_qc": coherent_take_qc,
    }
    if not (job_dir / "final").exists():
        for segment in plan["segments"]:
            expected_status = (
                "coherent_auto_passed_awaiting_user"
                if is_coherent_job(job)
                else "auto_passed_awaiting_user"
            )
            if segment["status"] != expected_status:
                raise WorkflowError(
                    f"{segment['index']}번 문장은 자동 검수 통과 상태가 아니어서 승인할 수 없습니다."
                )
    finalize_job(job_dir, job, plan, approval)
    print(
        json.dumps(
            {
                "status": job["status"],
                "final_wav": str((job_dir / job["final_wav"]).resolve()),
                "final_mp3": str((job_dir / job["final_mp3"]).resolve()),
                "segments": str((job_dir / "final" / "segments").resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_delegate_approve(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        if job.get("finalized"):
            return replay_delegated_approval(args, job_dir, job)
        return _command_delegate_approve_locked(
            args,
            job_dir,
            client=ElevenLabsClient(),
        )


def replay_delegated_approval(
    args: argparse.Namespace,
    job_dir: Path,
    job: dict[str, Any],
) -> int:
    if (
        job.get("status") != "user_delegated_auto_qc_final"
        or job.get("approval_type") != "delegated_automatic_qc"
        or job.get("human_listening_completed") is not False
        or args.confirmation.strip() != DELEGATED_AUTO_APPROVAL_CONFIRMATION
    ):
        raise WorkflowError("기존 최종화 기록이 현재 위임 승인 요청과 다릅니다.")
    plan = load_json(job_dir / "script_plan.json")
    selected = parse_segment_indices(args.segments, len(plan["segments"]))
    if selected != set(range(1, len(plan["segments"]) + 1)):
        raise WorkflowError("위임 최종화 재확인은 전체 문장에만 적용됩니다.")
    preview_wav, _, expected_hash, review_hashes = validate_current_review_integrity(
        job_dir,
        job,
        supplied_preview_sha256=args.preview_sha256,
    )
    approval_id = make_approval_id(
        approval_type="delegated_automatic_qc",
        preview_revision=int(job["review_revision"]),
        preview_sha256=expected_hash,
        confirmation=args.confirmation.strip(),
        preview_wav_sha256=sha256_file(preview_wav),
        review_file_hashes=review_hashes,
        expected_text=expected_preview_text(plan),
    )
    final_dir = job_dir / "final"
    report = load_json(final_dir / "qc_report.json")
    final_paths = final_artifact_paths(final_dir, plan)
    final_hashes = report.get("final_file_hashes")
    coherent_final_matches = (
        (
            sha256_file(final_dir / "final.wav")
            == sha256_file(job_dir / str(job["review_preview_wav"]))
            and sha256_file(final_dir / "final.mp3")
            == sha256_file(job_dir / str(job["review_preview_mp3"]))
        )
        if is_coherent_job(job)
        else True
    )
    if (
        approval_id != job.get("approval_id")
        or approval_id != report.get("approval_id")
        or report.get("status") != "user_delegated_auto_qc_final"
        or not isinstance(final_hashes, dict)
        or not coherent_final_matches
        or not all(
            path.is_file()
            and final_hashes.get(str(path.relative_to(final_dir)))
            == sha256_file(path)
            for path in final_paths
        )
    ):
        raise WorkflowError("기존 위임 최종본의 ID 또는 파일 무결성이 일치하지 않습니다.")
    print(
        json.dumps(
            {
                "status": job["status"],
                "approval_type": job["approval_type"],
                "human_listening_completed": False,
                "approval_id": approval_id,
                "idempotent_replay": True,
                "final_wav": str((job_dir / job["final_wav"]).resolve()),
                "final_mp3": str((job_dir / job["final_mp3"]).resolve()),
                "segments": str((job_dir / "final" / "segments").resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _command_delegate_approve_locked(
    args: argparse.Namespace,
    job_dir: Path,
    *,
    client: ElevenLabsClient,
) -> int:
    job = load_json(job_dir / "job.json")
    plan = load_json(job_dir / "script_plan.json")
    if job.get("finalized"):
        raise WorkflowError("이미 최종 승인된 작업입니다.")
    if job.get("status") != "awaiting_user_listening_approval":
        raise WorkflowError(
            "현재 작업은 전체 미리보기 승인 대기 상태가 아닙니다."
        )
    confirmation = args.confirmation.strip()
    if confirmation != DELEGATED_AUTO_APPROVAL_CONFIRMATION:
        raise WorkflowError(
            "자동 검증 최종화 위임 문구가 정확하지 않습니다: "
            f"{DELEGATED_AUTO_APPROVAL_CONFIRMATION}"
        )
    selected = parse_segment_indices(args.segments, len(plan["segments"]))
    if selected != set(range(1, len(plan["segments"]) + 1)):
        raise WorkflowError("위임 최종화는 현재 전체 미리보기의 모든 문장에만 적용됩니다.")
    (
        preview_wav,
        _,
        expected_hash,
        review_file_hashes,
    ) = validate_current_review_integrity(
        job_dir,
        job,
        supplied_preview_sha256=args.preview_sha256,
    )
    prosody_qc_evidence = validate_current_prosody_qc(job_dir, job, plan)
    coherent_take_qc = (
        validate_coherent_take_integrity(job_dir, job, plan)
        if is_coherent_job(job)
        else None
    )
    segment_qc = (
        [
            {
                "index": int(segment["index"]),
                "selected_take": job["selected_take"],
                "scope": "alignment_derived_review_clip_only",
            }
            for segment in plan["segments"]
        ]
        if is_coherent_job(job)
        else validate_delegated_segment_qc(job_dir, plan)
    )
    approval_id = make_approval_id(
        approval_type="delegated_automatic_qc",
        preview_revision=int(job["review_revision"]),
        preview_sha256=expected_hash,
        confirmation=confirmation,
        preview_wav_sha256=sha256_file(preview_wav),
        review_file_hashes=review_file_hashes,
        expected_text=expected_preview_text(plan),
    )
    full_preview_qc = verify_full_preview_automatic_qc(
        client,
        job_dir=job_dir,
        preview_wav=preview_wav,
        expected_text=expected_preview_text(plan),
        approval_id=approval_id,
        plan=plan,
    )
    approval = {
        "created_at": utc_now(),
        "approval_type": "delegated_automatic_qc",
        "human_listening_completed": False,
        "model_id": job.get("selected_model_id") or job["model_id"],
        "approval_id": approval_id,
        "segments": sorted(selected),
        "confirmation": confirmation,
        "preview_revision": int(job["review_revision"]),
        "preview_sha256": expected_hash,
        "review_file_hashes": review_file_hashes,
        "prosody_listening_qc_evidence": prosody_qc_evidence,
        "coherent_take_qc": coherent_take_qc,
        "delegated_auto_qc_verification": {
            "segment_qc": segment_qc,
            "full_preview_qc": full_preview_qc,
        },
    }
    finalize_job(job_dir, job, plan, approval)
    print(
        json.dumps(
            {
                "status": job["status"],
                "approval_type": approval["approval_type"],
                "human_listening_completed": False,
                "full_preview_auto_qc": full_preview_qc["checks"],
                "final_wav": str((job_dir / job["final_wav"]).resolve()),
                "final_mp3": str((job_dir / job["final_mp3"]).resolve()),
                "segments": str((job_dir / "final" / "segments").resolve()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def command_regenerate(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        return _command_regenerate_locked(args, job_dir)


def command_select_attempt(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        plan = load_json(job_dir / "script_plan.json")
        if job.get("finalized"):
            raise WorkflowError("이미 최종 승인된 작업의 후보를 바꿀 수 없습니다.")

        segment_index = int(args.segment)
        attempt_number = int(args.attempt)
        if not 1 <= segment_index <= len(plan["segments"]):
            raise WorkflowError(f"문장 번호가 범위를 벗어났습니다: {segment_index}")
        if attempt_number < 1:
            raise WorkflowError("후보 시도 번호는 1 이상이어야 합니다.")

        segment = plan["segments"][segment_index - 1]
        attempt = next(
            (
                item
                for item in segment.get("attempts", [])
                if int(item.get("attempt") or 0) == attempt_number
            ),
            None,
        )
        if not attempt:
            raise WorkflowError(
                f"{segment_index}번 문장의 {attempt_number}번 후보를 찾을 수 없습니다."
            )

        wav_path = job_dir / str(attempt.get("wav") or "")
        mp3_path = job_dir / str(attempt.get("mp3") or "")
        if not wav_path.is_file() or not mp3_path.is_file():
            raise WorkflowError("선택할 기존 후보의 WAV 또는 MP3 파일이 없습니다.")
        transcript_path = wav_path.parent / "transcript.json"
        transcript = load_json(transcript_path)
        transcript_text = str(
            transcript.get("text") or attempt.get("transcript_text") or ""
        )
        transcript_language_code = (
            str(transcript.get("language_code"))
            if transcript.get("language_code")
            else None
        )
        expected_spoken_text = str(segment["spoken_text"])
        qc_transcript_text = canonicalize_stt_notation(
            expected_spoken_text,
            transcript_text,
        )
        transcript_precheck_passed = (
            transcript_language_code is not None
            and transcript_language_code.lower() in {"ko", "kor"}
            and normalize_for_comparison(qc_transcript_text)
            == normalize_for_comparison(expected_spoken_text)
            and normalize_lexical_content(qc_transcript_text)
            == normalize_lexical_content(expected_spoken_text)
        )
        if not transcript_precheck_passed:
            raise WorkflowError(
                "기존 후보의 재전사가 원래 발화문과 일치하지 않아 선택할 수 없습니다."
            )

        client = ElevenLabsClient()
        alignment = client.forced_alignment(wav_path, expected_spoken_text)
        metrics = analyze_wav(wav_path, transcript=qc_transcript_text)
        reference_profile = load_json(job_dir / "reference_profile.json")
        qc = score_candidate(
            expected_text=expected_spoken_text,
            transcript_text=qc_transcript_text,
            transcript_language_code=transcript_language_code,
            candidate_metrics=metrics,
            reference_profile=reference_profile,
            alignment=alignment,
            target_duration_seconds=segment_target_duration(plan, segment, job),
        )
        focus_phrases = validate_focus_phrases(
            segment,
            list(segment.get("pronunciation_focus_phrases") or []),
        ) if segment.get("pronunciation_focus_phrases") else []
        focus_results: list[dict[str, Any]] = []
        if qc["auto_pass"] and focus_phrases:
            focus_results = run_focus_pronunciation_checks(
                client,
                wav_path=wav_path,
                alignment=alignment,
                phrases=focus_phrases,
                attempt_dir=wav_path.parent,
            )
        qc = attach_focus_pronunciation_qc(
            qc,
            required=bool(focus_phrases),
            results=focus_results,
        )
        attempt.update(
            {
                "status": "auto_qc_complete",
                "transcript_text": transcript_text,
                "qc_transcript_text": qc_transcript_text,
                "transcript_language_code": transcript_language_code,
                "pronunciation_focus_phrases": focus_phrases,
                "pronunciation_focus_results": focus_results,
                "audio_metrics": metrics,
                "qc": qc,
                "qc_rechecked_at": utc_now(),
            }
        )
        atomic_write_json(wav_path.parent / "forced_alignment.json", alignment)
        atomic_write_json(wav_path.parent / "qc.json", attempt)
        atomic_write_json(wav_path.parent / "attempt.json", attempt)
        if not qc["auto_pass"]:
            atomic_write_json(job_dir / "script_plan.json", plan)
            raise WorkflowError(
                "사용자가 선택한 기존 후보가 현재 자동 검수 게이트를 통과하지 못했습니다."
            )

        review_segment_dir = job_dir / "review" / "segments"
        review_segment_dir.mkdir(parents=True, exist_ok=True)
        selected_wav = review_segment_dir / f"{segment_index:03d}.wav"
        selected_mp3 = review_segment_dir / f"{segment_index:03d}.mp3"
        shutil.copy2(wav_path, selected_wav)
        shutil.copy2(mp3_path, selected_mp3)
        segment["selected_attempt"] = attempt_number
        segment["selected_wav"] = relative_to_job(selected_wav, job_dir)
        segment["selected_mp3"] = relative_to_job(selected_mp3, job_dir)
        segment["status"] = "auto_passed_awaiting_user"
        selection = {
            "created_at": utc_now(),
            "segment": segment_index,
            "attempt": attempt_number,
            "confirmation": args.confirmation.strip(),
            "scope": "segment_candidate_only_not_final_approval",
        }
        segment.setdefault("candidate_selections", []).append(selection)
        job.setdefault("candidate_selections", []).append(selection)
        job["review_preview_wav"] = None
        job["review_preview_mp3"] = None
        job["review_preview_sha256"] = None
        job["review_file_hashes"] = None
        job["user_approvals"] = []
        job["finalized"] = False
        atomic_write_json(job_dir / "script_plan.json", plan)
        write_job(job_dir, job)
        print(
            json.dumps(
                {
                    "status": job.get("status"),
                    "segment": segment_index,
                    "selected_attempt": attempt_number,
                    "review_mp3": str(selected_mp3.resolve()),
                    "qc": qc,
                    "note": "문장 후보 선택이며 전체 미리보기 최종 승인이 아닙니다.",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


def validate_focus_phrases(
    segment: dict[str, Any],
    phrases: list[str],
) -> list[str]:
    spoken_text = str(segment["spoken_text"])
    validated: list[str] = []
    for raw_phrase in phrases:
        phrase = raw_phrase.strip()
        if not phrase:
            continue
        validate_korean_only(phrase)
        occurrence_count = spoken_text.count(phrase)
        if occurrence_count != 1:
            raise WorkflowError(
                f"{segment['index']}번 문장에 집중 발음 구절이 정확히 한 번 "
                f"존재해야 합니다({occurrence_count}회): {phrase}"
            )
        if phrase not in validated:
            validated.append(phrase)
    if not validated:
        raise WorkflowError("하나 이상의 집중 발음 구절이 필요합니다.")
    return validated


def command_set_focus(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        plan = load_json(job_dir / "script_plan.json")
        if job.get("finalized"):
            raise WorkflowError("이미 최종 승인된 작업의 발음 게이트를 바꿀 수 없습니다.")
        segment_index = int(args.segment)
        if not 1 <= segment_index <= len(plan["segments"]):
            raise WorkflowError(f"문장 번호가 범위를 벗어났습니다: {segment_index}")
        segment = plan["segments"][segment_index - 1]
        if segment.get("selected_attempt") is not None:
            raise WorkflowError(
                "이미 선택본이 있는 문장은 기존 후보 재검수 또는 재생성 전에 "
                "집중 발음 구절을 추가할 수 없습니다."
            )
        phrases = validate_focus_phrases(segment, list(args.phrase or []))
        direction = args.direction.strip() if args.direction else None
        if direction:
            direction = KOREAN_DIRECTION_TAGS.get(direction, direction)
            segment["directions"] = [direction]
            segment["tts_text"] = f"[{direction}] {segment['spoken_text']}"
        tts_override = args.tts_override.strip() if args.tts_override else None
        if tts_override:
            validate_korean_only(tts_override)
            prefix = " ".join(
                f"[{item}]" for item in segment.get("directions", [])
            )
            segment["tts_override"] = f"{prefix} {tts_override}".strip()
        segment["pronunciation_focus_phrases"] = phrases
        segment.setdefault("pronunciation_focus_configurations", []).append(
            {
                "created_at": utc_now(),
                "phrases": phrases,
                "reason": args.reason.strip(),
                "direction": direction,
                "tts_override": tts_override,
            }
        )
        atomic_write_json(job_dir / "script_plan.json", plan)
        print(
            json.dumps(
                {
                    "status": job.get("status"),
                    "segment": segment_index,
                    "pronunciation_focus_phrases": phrases,
                    "direction": direction,
                    "tts_override": tts_override,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0


def _command_regenerate_locked(args: argparse.Namespace, job_dir: Path) -> int:
    standing_authorization = standing_tts_generation_authorized()
    if not args.additional_cost_approved and not standing_authorization:
        raise WorkflowError(
            "5회 추가 생성 비용을 승인한 경우에만 --additional-cost-approved를 사용하세요."
        )
    job = load_json(job_dir / "job.json")
    plan = load_json(job_dir / "script_plan.json")
    if is_coherent_job(job):
        raise WorkflowError(
            "coherent 전체 테이크는 coherent_block.py retry와 현재 일회용 "
            "승인 토큰으로만 재생성할 수 있습니다."
        )
    if job.get("finalized"):
        raise WorkflowError("이미 최종 승인된 작업은 재생성하지 않습니다.")
    if job.get("status") not in {
        "awaiting_user_listening_approval",
        "prosody_regeneration_required",
        "awaiting_audio_listening_qc",
        "blocked_after_five_attempts",
        "processing_error",
        "interrupted_recoverable",
    }:
        raise WorkflowError(
            "현재 작업 상태에서는 재생성할 수 없습니다. 먼저 status를 확인하세요."
        )
    expected_token = str(job.get("additional_generation_token") or "")
    provided_token = str(getattr(args, "approval_token", "") or "").strip()
    if standing_authorization and not provided_token:
        provided_token = expected_token
    if not expected_token or provided_token != expected_token:
        raise WorkflowError(
            "현재 작업의 일회용 내부 재생성 상태 토큰이 아닙니다. "
            "status를 다시 확인하세요."
        )
    selected = parse_segment_indices(args.segments, len(plan["segments"]))
    direction = args.direction.strip() if args.direction else None
    if direction:
        direction = KOREAN_DIRECTION_TAGS.get(direction, direction)
    tts_override = args.tts_override.strip() if args.tts_override else None
    if tts_override:
        validate_korean_only(tts_override)
    raw_focus_phrases = list(getattr(args, "focus_phrase", None) or [])
    client = ElevenLabsClient()
    verify_live_model(client)

    for segment in plan["segments"]:
        if int(segment["index"]) not in selected:
            continue
        if segment["status"] == "user_approved":
            raise WorkflowError(
                f"{segment['index']}번 문장은 이미 최종 승인되어 재생성할 수 없습니다."
            )
        if segment["status"] not in {
            "auto_passed_awaiting_user",
            "blocked_after_five_attempts",
            "generating",
            "pending_generation",
            "pending_regeneration",
        }:
            raise WorkflowError(
                f"{segment['index']}번 문장은 현재 재생성 가능한 상태가 아닙니다: "
                f"{segment['status']}"
            )
        feedback = {
            "created_at": utc_now(),
            "reason": args.feedback.strip(),
            "direction": direction,
            "tts_override": tts_override,
        }
        segment.setdefault("user_feedback", []).append(feedback)
        if direction:
            # A user's regeneration direction replaces the earlier heuristic.
            # Keeping both can create conflicting delivery cues (for example,
            # "conversationally" plus the auto-selected "curiously").
            directions = [direction]
            segment["directions"] = directions
            segment["tts_text"] = (
                " ".join(f"[{item}]" for item in directions)
                + " "
                + str(segment["spoken_text"])
            )
        if tts_override:
            prefix = " ".join(
                f"[{item}]" for item in segment.get("directions", [])
            )
            segment["tts_override"] = f"{prefix} {tts_override}".strip()
        if raw_focus_phrases:
            segment["pronunciation_focus_phrases"] = validate_focus_phrases(
                segment,
                raw_focus_phrases,
            )
        segment["status"] = "pending_regeneration"
        segment["selected_attempt"] = None
        segment.pop("selected_wav", None)
        segment.pop("selected_mp3", None)
    atomic_write_json(job_dir / "script_plan.json", plan)
    job["status"] = "additional_generation_approved"
    job["review_preview_wav"] = None
    job["review_preview_mp3"] = None
    job["review_preview_sha256"] = None
    job["review_file_hashes"] = None
    job["prosody_listening_qc_report"] = None
    job["prosody_listening_qc_sha256"] = None
    job["prosody_objective_flagged_segments"] = None
    job["additional_generation_token"] = None
    job["user_approvals"] = []
    job.setdefault("additional_generation_approvals", []).append(
        {
            "created_at": utc_now(),
            "segments": sorted(selected),
            "feedback": args.feedback.strip(),
            "pronunciation_focus_phrases": raw_focus_phrases,
            "attempts_per_segment": MAX_ATTEMPTS_PER_BATCH,
        }
    )
    write_job(job_dir, job)
    return (
        0
        if generate_pending_segments(
            client,
            job_dir=job_dir,
            selected_indices=selected,
        )
        else 2
    )


def validate_current_prosody_qc(
    job_dir: Path,
    job: dict[str, Any],
    plan: dict[str, Any],
) -> dict[str, Any]:
    report_value = job.get("prosody_listening_qc_report")
    if not report_value:
        raise WorkflowError(
            "현재 미리보기에 대한 prosody-listening-qc 보고서가 없습니다."
        )
    report_path = job_dir / str(report_value)
    report = load_json(report_path)
    report_hash = sha256_file(report_path)
    if str(job.get("prosody_listening_qc_sha256") or "") != report_hash:
        raise WorkflowError(
            "운율 QC 보고서 파일이 현재 작업에 기록된 해시와 일치하지 않습니다."
        )
    strict_qc = report.get("strict_qc")
    if not isinstance(strict_qc, dict) or strict_qc.get("passed") is not True:
        raise WorkflowError(
            "운율 검사와 실제 오디오 A/B 판정 3회가 모두 통과하지 않았습니다."
        )
    objective_qc = report.get("objective_qc")
    if (
        not isinstance(objective_qc, dict)
        or objective_qc.get("passed") is not True
        or objective_qc.get("flagged_segments") not in ([], None)
    ):
        raise WorkflowError("운율 QC 보고서에 재생성 대상 문장이 남아 있습니다.")
    audio_qc = report.get("audio_listening_qc")
    runs = audio_qc.get("runs") if isinstance(audio_qc, dict) else None
    expected_spoken_text = {
        int(segment["index"]): str(segment.get("spoken_text") or "")
        for segment in plan["segments"]
    }
    required_audio_checks = {
        "pronunciation_pass",
        "tone_pass",
        "intonation_pass",
        "emotion_pass",
        "speaker_character_pass",
        "boundary_continuity_pass",
        "no_synthesis_artifact_pass",
    }

    def valid_audio_run(run: Any) -> bool:
        if not isinstance(run, dict):
            return False
        settings_id = run.get("settings_id")
        model = run.get("model")
        segments = run.get("segments")
        if (
            not isinstance(settings_id, str)
            or not settings_id.strip()
            or not isinstance(model, str)
            or not model.strip()
            or run.get("all_passed") is not True
            or not isinstance(segments, list)
            or len(segments) != len(expected_spoken_text)
            or any(not isinstance(item, dict) for item in segments)
        ):
            return False
        indices = [item.get("index") for item in segments]
        if any(
            not isinstance(index, int) or isinstance(index, bool)
            for index in indices
        ):
            return False
        if (
            len(set(indices)) != len(indices)
            or set(indices) != set(expected_spoken_text)
        ):
            return False
        return all(
            item.get("spoken_text") == expected_spoken_text[item["index"]]
            and required_audio_checks.issubset(item)
            and all(item.get(check) is True for check in required_audio_checks)
            for item in segments
        )

    evaluator = (
        audio_qc.get("evaluator")
        if isinstance(audio_qc, dict)
        else None
    )
    if (
        not isinstance(audio_qc, dict)
        or audio_qc.get("passed") is not True
        or not isinstance(evaluator, str)
        or not evaluator.strip()
        or not isinstance(runs, list)
        or len(runs) != 3
        or not all(valid_audio_run(run) for run in runs)
        or len(
            {
                run["settings_id"].strip()
                for run in runs
                if isinstance(run, dict)
            }
        )
        != 3
    ):
        raise WorkflowError(
            "서로 다른 설정의 실제 오디오 판정 3회 만장일치 증거가 없습니다."
        )
    preview_wav_value = job.get("review_preview_wav")
    if not preview_wav_value:
        raise WorkflowError("현재 전체 WAV 미리보기 경로가 없습니다.")
    preview_wav = job_dir / str(preview_wav_value)
    report_preview = report.get("preview")
    if (
        not preview_wav.is_file()
        or not isinstance(report_preview, dict)
        or report_preview.get("sha256") != sha256_file(preview_wav)
        or report_preview.get("review_revision") != job.get("review_revision")
    ):
        raise WorkflowError(
            "운율 QC 보고서가 현재 전체 미리보기 리비전과 일치하지 않습니다."
        )
    report_segments = report.get("segments")
    if not isinstance(report_segments, list):
        raise WorkflowError("운율 QC 보고서의 문장별 증거가 없습니다.")
    by_index = {
        int(item["index"]): item
        for item in report_segments
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }
    if set(by_index) != {
        int(segment["index"]) for segment in plan["segments"]
    }:
        raise WorkflowError("운율 QC 보고서의 문장 범위가 현재 계획과 다릅니다.")
    for segment in plan["segments"]:
        index = int(segment["index"])
        selected_wav = job_dir / str(segment.get("selected_wav") or "")
        evidence = by_index[index]
        features = evidence.get("features")
        selection_matches = (
            evidence.get("selected_take") == segment.get("selected_take")
            and segment.get("selected_take") == job.get("selected_take")
            if is_coherent_job(job)
            else evidence.get("selected_attempt")
            == segment.get("selected_attempt")
        )
        if (
            not selected_wav.is_file()
            or not isinstance(features, dict)
            or features.get("sha256") != sha256_file(selected_wav)
            or not selection_matches
            or not isinstance(evidence.get("objective_qc"), dict)
            or evidence["objective_qc"].get("passed") is not True
        ):
            raise WorkflowError(
                f"{index}번 문장의 운율 QC 증거가 현재 선택본과 일치하지 않습니다."
            )
    reference = report.get("reference")
    if not isinstance(reference, dict):
        raise WorkflowError("운율 QC 레퍼런스 증거가 없습니다.")
    reference_path = Path(str(reference.get("path") or "")).expanduser()
    if (
        not reference_path.is_file()
        or reference.get("sha256") != sha256_file(reference_path)
    ):
        raise WorkflowError("운율 QC 레퍼런스 파일 또는 해시가 현재 증거와 다릅니다.")
    return {
        "report": relative_to_job(report_path, job_dir),
        "report_sha256": report_hash,
        "reference_sha256": reference["sha256"],
        "preview_wav_sha256": report_preview["sha256"],
        "objective_qc": objective_qc,
        "audio_listening_run_count": len(runs),
        "audio_listening_settings_ids": [
            str(run["settings_id"]) for run in runs
        ],
    }


def command_prosody_qc(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    reference_wav = args.reference_wav.expanduser().resolve()
    audio_judge_report = (
        args.audio_judge_report.expanduser().resolve()
        if args.audio_judge_report
        else None
    )
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        report = analyze_prosody_job(
            job_dir=job_dir,
            reference_wav=reference_wav,
            audio_judge_report=audio_judge_report,
        )
        report_path = job_dir / "review" / "prosody-listening-qc.json"
        atomic_write_json(report_path, report)
        job["prosody_listening_qc_report"] = relative_to_job(
            report_path,
            job_dir,
        )
        job["prosody_listening_qc_sha256"] = sha256_file(report_path)
        job["prosody_listening_qc_updated_at"] = utc_now()
        job["prosody_objective_flagged_segments"] = report[
            "objective_qc"
        ]["flagged_segments"]
        if not job.get("finalized"):
            if not report["objective_qc"]["passed"]:
                job["status"] = "prosody_regeneration_required"
            elif not report["audio_listening_qc"]["passed"]:
                job["status"] = "awaiting_audio_listening_qc"
            else:
                job["status"] = "awaiting_user_listening_approval"
            if is_coherent_job(job):
                if not report["objective_qc"]["passed"]:
                    flagged = set(
                        report["objective_qc"].get("flagged_segments") or []
                    )
                    coherent_plan = load_json(job_dir / "script_plan.json")
                    for segment in coherent_plan["segments"]:
                        segment["status"] = (
                            "coherent_prosody_regeneration_required"
                            if int(segment["index"]) in flagged
                            else "derived_clip_objective_qc_passed"
                        )
                    atomic_write_json(
                        job_dir / "script_plan.json",
                        coherent_plan,
                    )
                else:
                    coherent_plan = load_json(job_dir / "script_plan.json")
                    coherent_status = (
                        "coherent_auto_passed_awaiting_user"
                        if report["audio_listening_qc"]["passed"]
                        else "derived_clip_awaiting_audio_listening_qc"
                    )
                    for segment in coherent_plan["segments"]:
                        segment["status"] = coherent_status
                    atomic_write_json(
                        job_dir / "script_plan.json",
                        coherent_plan,
                    )
        write_job(job_dir, job)
        print(
            json.dumps(
                {
                    "status": job.get("status"),
                    "objective_qc": report["objective_qc"],
                    "audio_listening_qc": {
                        "status": report["audio_listening_qc"]["status"],
                        "passed": report["audio_listening_qc"]["passed"],
                    },
                    "strict_qc": report["strict_qc"],
                    "report": str(report_path.resolve()),
                    "finalized_job_unchanged": bool(job.get("finalized")),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if report["strict_qc"]["passed"] else 2


def command_status(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    job = load_json(job_dir / "job.json")
    plan_path = job_dir / "script_plan.json"
    plan = load_json(plan_path) if plan_path.exists() else {"segments": []}
    coherent = is_coherent_job(job)
    summary = {
        "status": job.get("status"),
        "workflow": job.get("workflow"),
        "voice_name": job.get("voice_name"),
        "voice_id": job.get("voice_id"),
        "selected_take": job.get("selected_take"),
        "segment_count": len(plan["segments"]),
        "segments": [
            {
                "index": segment["index"],
                "status": segment["status"],
                "attempt_count": (
                    len(job.get("attempts") or [])
                    if coherent
                    else len(segment.get("attempts") or [])
                ),
                "selected_attempt": (
                    segment.get("selected_take")
                    if coherent
                    else segment.get("selected_attempt")
                ),
                "review_mp3": (
                    str((job_dir / segment["selected_mp3"]).resolve())
                    if segment.get("selected_mp3")
                    else None
                ),
            }
            for segment in plan["segments"]
        ],
        "preview_mp3": (
            str((job_dir / job["review_preview_mp3"]).resolve())
            if job.get("review_preview_mp3")
            else None
        ),
        "preview_wav": (
            str((job_dir / job["review_preview_wav"]).resolve())
            if job.get("review_preview_wav")
            else None
        ),
        "preview_revision": job.get("review_revision"),
        "preview_sha256": job.get("review_preview_sha256"),
        "approval_id": job.get("approval_id"),
        "approval_type": job.get("approval_type"),
        "human_listening_completed": job.get("human_listening_completed"),
        "additional_generation_token": job.get("additional_generation_token"),
        "final_mp3": (
            str((job_dir / job["final_mp3"]).resolve())
            if job.get("final_mp3")
            else None
        ),
        "final_wav": (
            str((job_dir / job["final_wav"]).resolve())
            if job.get("final_wav")
            else None
        ),
        "last_error": job.get("last_error"),
        "retention_notice": job.get("retention_notice"),
        "prosody_listening_qc_report": (
            str((job_dir / job["prosody_listening_qc_report"]).resolve())
            if job.get("prosody_listening_qc_report")
            else None
        ),
        "prosody_objective_flagged_segments": job.get(
            "prosody_objective_flagged_segments"
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def command_rebuild_preview(args: argparse.Namespace) -> int:
    job_dir = args.job_dir.expanduser().resolve()
    with job_write_lock(job_dir):
        job = load_json(job_dir / "job.json")
        plan = load_json(job_dir / "script_plan.json")
        if is_coherent_job(job):
            raise WorkflowError(
                "coherent 전체 테이크 미리보기는 문장 클립으로 재조립하지 않습니다. "
                "선택된 전체 테이크가 유일한 권위 음원입니다."
            )
        if job.get("finalized"):
            raise WorkflowError("이미 최종 승인된 작업의 미리보기는 다시 만들 수 없습니다.")
        if job.get("status") != "awaiting_user_listening_approval":
            raise WorkflowError(
                "현재 작업은 전체 미리보기 승인 대기 상태가 아니어서 다시 만들 수 없습니다."
            )
        for segment in plan["segments"]:
            if (
                segment.get("status") != "auto_passed_awaiting_user"
                or not segment.get("selected_wav")
                or not segment.get("selected_mp3")
            ):
                raise WorkflowError(
                    f"{segment['index']}번 문장이 검수 통과 선택 상태가 아닙니다."
                )

        previous_revision = int(job.get("review_revision") or 0)
        previous_preview_sha256 = job.get("review_preview_sha256")
        preview_wav, preview_mp3 = assemble_review_preview(job_dir, plan)
        review_files = [preview_wav, preview_mp3]
        for segment in plan["segments"]:
            review_files.append(job_dir / str(segment["selected_wav"]))
            review_files.append(job_dir / str(segment["selected_mp3"]))
        job["review_preview_wav"] = relative_to_job(preview_wav, job_dir)
        job["review_preview_mp3"] = relative_to_job(preview_mp3, job_dir)
        job["review_file_hashes"] = {
            relative_to_job(path, job_dir): sha256_file(path)
            for path in review_files
        }
        job["review_revision"] = previous_revision + 1
        job["review_preview_sha256"] = sha256_file(preview_mp3)
        job["additional_generation_token"] = secrets.token_hex(16)
        job["user_approvals"] = []
        for key in (
            "approval_id",
            "approval_type",
            "human_listening_completed",
        ):
            job.pop(key, None)
        job.setdefault("review_rebuild_records", []).append(
            {
                "created_at": utc_now(),
                "reason": args.reason.strip(),
                "previous_revision": previous_revision,
                "previous_preview_sha256": previous_preview_sha256,
                "new_revision": job["review_revision"],
                "new_preview_sha256": job["review_preview_sha256"],
            }
        )
        write_job(job_dir, job)
        print(
            json.dumps(
                {
                    "status": job["status"],
                    "preview_mp3": str(preview_mp3.resolve()),
                    "preview_wav": str(preview_wav.resolve()),
                    "preview_revision": job["review_revision"],
                    "preview_sha256": job["review_preview_sha256"],
                    "segment_count": len(plan["segments"]),
                    "reason": args.reason.strip(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    return 0


def command_list_voices(args: argparse.Namespace) -> int:
    registry = load_registry()
    result: dict[str, Any] = {"saved_by_skill": registry["voices"]}
    if args.cloud:
        client = ElevenLabsClient()
        result["elevenlabs_account"] = [
            {
                "voice_id": voice.get("voice_id"),
                "name": voice.get("name"),
                "category": voice.get("category"),
            }
            for voice in client.list_voices()
        ]
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    checks: dict[str, Any] = {
        "ffmpeg": None,
        "ffprobe": None,
        "numpy": np.__version__,
        "requests": requests.__version__,
        "api_key_set": bool(os.environ.get("ELEVENLABS_API_KEY")),
        "state_dir": str(STATE_DIR),
        "live_api": "not_requested",
    }
    failures: list[str] = []
    for binary in ("ffmpeg", "ffprobe"):
        try:
            checks[binary] = require_binary(binary)
        except AudioToolError as exc:
            failures.append(str(exc))
    ensure_private_state_dir()
    if args.live:
        if not checks["api_key_set"]:
            failures.append("ELEVENLABS_API_KEY가 설정되지 않았습니다.")
            checks["live_api"] = "blocked_missing_api_key"
        else:
            client = ElevenLabsClient()
            subscription = client.get_subscription()
            models = client.get_json("/v1/models")
            checks["live_api"] = {
                "subscription_tier": subscription.get("tier"),
                "tts_models": [
                    model.get("model_id")
                    for model in models
                    if model.get("can_do_text_to_speech")
                ],
                "eleven_v3_available": any(
                    model.get("model_id") == MODEL_ID
                    for model in models
                    if model.get("can_do_text_to_speech")
                ),
            }
            if not checks["live_api"]["eleven_v3_available"]:
                failures.append("계정에서 eleven_v3 TTS 모델을 확인하지 못했습니다.")
    checks["ok"] = not failures
    checks["local_checks_ok"] = not any(
        failure.startswith("필수 프로그램") for failure in failures
    )
    checks["failures"] = failures
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


def command_self_test(_: argparse.Namespace) -> int:
    import tempfile

    def require(condition: bool, label: str) -> None:
        if not condition:
            raise WorkflowError(f"self-test 실패: {label}")

    offline_client = ElevenLabsClient(api_key="offline-self-test-key")
    require(
        offline_client.session.trust_env is False,
        "http session ignores proxy and netrc environment",
    )

    with tempfile.TemporaryDirectory(prefix="elevenlabs-reference-test-") as temporary:
        temporary_dir = Path(temporary)
        audio_report_path = temporary_dir / "audio-judge.json"
        required_audio_checks = (
            "pronunciation_pass",
            "tone_pass",
            "intonation_pass",
            "emotion_pass",
            "speaker_character_pass",
            "boundary_continuity_pass",
            "no_synthesis_artifact_pass",
        )

        def audio_report() -> dict[str, Any]:
            return {
                "schema_version": 1,
                "reference_sha256": "a" * 64,
                "preview_sha256": "b" * 64,
                "evaluator": "strict-self-test-evaluator",
                "runs": [
                    {
                        "settings_id": f"strict-{run_index}",
                        "model": "strict-self-test-model",
                        "all_passed": True,
                        "segments": [
                            {
                                "index": 1,
                                "spoken_text": "안녕하세요",
                                **{
                                    check: True
                                    for check in required_audio_checks
                                },
                            }
                        ],
                    }
                    for run_index in range(1, 4)
                ],
            }

        strict_report = audio_report()
        atomic_write_json(audio_report_path, strict_report)
        require(
            _audio_judge_gate(
                audio_report_path,
                reference_sha256="a" * 64,
                preview_sha256="b" * 64,
                segment_texts={1: "안녕하세요"},
            )["passed"]
            is True,
            "exact JSON boolean audio judge",
        )
        for invalid_value in ("false", 1, []):
            invalid_report = audio_report()
            invalid_report["runs"][0]["segments"][0][
                "pronunciation_pass"
            ] = invalid_value
            atomic_write_json(audio_report_path, invalid_report)
            try:
                _audio_judge_gate(
                    audio_report_path,
                    reference_sha256="a" * 64,
                    preview_sha256="b" * 64,
                    segment_texts={1: "안녕하세요"},
                )
            except WorkflowError:
                pass
            else:
                raise WorkflowError(
                    "self-test 실패: non-boolean audio judge field"
                )
        duplicate_report = audio_report()
        duplicate_report["runs"][0]["segments"].append(
            dict(duplicate_report["runs"][0]["segments"][0])
        )
        atomic_write_json(audio_report_path, duplicate_report)
        try:
            _audio_judge_gate(
                audio_report_path,
                reference_sha256="a" * 64,
                preview_sha256="b" * 64,
                segment_texts={1: "안녕하세요"},
            )
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: duplicate audio judge segment")
        nonstring_setting_report = audio_report()
        nonstring_setting_report["runs"][0]["settings_id"] = 1
        atomic_write_json(audio_report_path, nonstring_setting_report)
        try:
            _audio_judge_gate(
                audio_report_path,
                reference_sha256="a" * 64,
                preview_sha256="b" * 64,
                segment_texts={1: "안녕하세요"},
            )
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: non-string settings_id")
        for label, mutate in (
            (
                "missing schema version",
                lambda report: report.pop("schema_version"),
            ),
            (
                "wrong schema version",
                lambda report: report.update({"schema_version": True}),
            ),
            (
                "unsupported schema version",
                lambda report: report.update({"schema_version": 2}),
            ),
            (
                "string schema version",
                lambda report: report.update({"schema_version": "1"}),
            ),
            (
                "empty evaluator",
                lambda report: report.update({"evaluator": ""}),
            ),
            (
                "non-string evaluator",
                lambda report: report.update({"evaluator": 1}),
            ),
            (
                "empty model",
                lambda report: report["runs"][0].update({"model": ""}),
            ),
            (
                "non-string model",
                lambda report: report["runs"][0].update({"model": 1}),
            ),
            (
                "mismatched spoken text",
                lambda report: report["runs"][0]["segments"][0].update(
                    {"spoken_text": "다른 문장"}
                ),
            ),
            (
                "non-string spoken text",
                lambda report: report["runs"][0]["segments"][0].update(
                    {"spoken_text": 1}
                ),
            ),
        ):
            invalid_report = audio_report()
            mutate(invalid_report)
            atomic_write_json(audio_report_path, invalid_report)
            try:
                _audio_judge_gate(
                    audio_report_path,
                    reference_sha256="a" * 64,
                    preview_sha256="b" * 64,
                    segment_texts={1: "안녕하세요"},
                )
            except WorkflowError:
                pass
            else:
                raise WorkflowError(f"self-test 실패: {label}")
        try:
            validate_run_preconditions(
                argparse.Namespace(
                    target_duration=float("nan"),
                    consent_confirmed=True,
                    reference_video=None,
                    style_reference_video=None,
                ),
                temporary_dir / "nan-target-output",
            )
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: non-finite target duration")
        sample_rate = 16_000
        silence = np.zeros(int(sample_rate * 0.2), dtype=np.float64)
        time_axis = np.arange(int(sample_rate * 1.0)) / sample_rate
        tone = 0.18 * np.sin(2 * np.pi * 180.0 * time_axis)
        samples = np.concatenate((silence, tone, silence))
        wav_path = temporary_dir / "synthetic.wav"
        with wave.open(str(wav_path), "wb") as file:
            file.setnchannels(1)
            file.setsampwidth(2)
            file.setframerate(sample_rate)
            file.writeframes(
                (np.clip(samples, -1, 1) * 32767).astype("<i2").tobytes()
            )
        wav_24bit_path = convert_to_wav(
            wav_path,
            temporary_dir / "synthetic-24bit.wav",
            sample_rate=sample_rate,
            sample_format="pcm_s24le",
        )
        mixed_bit_depth_concat = concatenate_wavs(
            [wav_24bit_path, wav_path],
            temporary_dir / "mixed-bit-depth-concat.wav",
        )
        mixed_sources_pcm = canonical_pcm_fingerprint(
            [wav_24bit_path, wav_path]
        )
        with wave.open(str(mixed_bit_depth_concat), "rb") as mixed_wav:
            require(
                mixed_wav.getnchannels() == 1
                and mixed_wav.getsampwidth() == 3
                and mixed_wav.getframerate() == 48_000
                and mixed_wav.getnframes()
                == mixed_sources_pcm["frame_count"],
                "mixed bit-depth concat frame preservation",
            )
        mixed_output_pcm = canonical_pcm_fingerprint(
            [mixed_bit_depth_concat]
        )
        require(
            all(
                mixed_sources_pcm[key] == mixed_output_pcm[key]
                for key in (
                    "channels",
                    "sample_width",
                    "sample_rate",
                    "frame_count",
                    "pcm_sha256",
                )
            ),
            "mixed bit-depth concat canonical PCM equality",
        )
        metrics = analyze_wav(wav_path, transcript="안녕하세요 반갑습니다")
        require(metrics["duration_seconds"] > 1.3, "audio duration")
        require(metrics["pitch_median_hz"] is not None, "pitch measurement")
        focus_clip_path = extract_wav_interval(
            wav_path,
            temporary_dir / "focus-clip.wav",
            start_seconds=0.2,
            end_seconds=0.7,
            silence_padding_seconds=0.2,
        )
        focus_clip_metrics = analyze_wav(focus_clip_path, transcript="안녕")
        require(
            focus_clip_metrics["duration_seconds"] >= 0.89
            and focus_clip_metrics["leading_silence_seconds"] >= 0.18
            and focus_clip_metrics["trailing_silence_seconds"] >= 0.18,
            "focused audio interval extraction and silence padding",
        )
        reference_gate_metrics = dict(metrics)
        reference_gate_metrics["active_speech_seconds"] = 46.0
        reference_gate_metrics["clipping_ratio"] = 0.0
        reference_gate = reference_quality(
            reference_gate_metrics,
            "안녕하세요반갑습니다" * 6,
            transcript_language_code="ko",
            speaker_count=1,
        )
        require(
            not reference_gate["hard_failures"],
            "valid single-speaker reference gate",
        )
        multi_speaker_gate = reference_quality(
            reference_gate_metrics,
            "안녕하세요반갑습니다" * 6,
            transcript_language_code="ko",
            speaker_count=2,
        )
        require(
            any("2명의 화자" in item for item in multi_speaker_gate["hard_failures"]),
            "multi-speaker reference rejection",
        )

        profile = {"audio_metrics": metrics}
        planned = plan_script(
            "[신나게] 안녕하세요! 오늘은 좋은 소식을 알려드릴게요.",
            profile,
        )
        require(len(planned) >= 1, "script segmentation")
        require(
            planned[0]["spoken_text"].startswith("안녕하세요"),
            "manual direction removal",
        )
        require(
            expected_preview_text(
                {
                    "segments": planned,
                    "original_script": (
                        "[신나게] 안녕하세요! 오늘은 좋은 소식을 알려드릴게요."
                    ),
                }
            )
            == "\n".join(segment["spoken_text"] for segment in planned)
            and "[신나게]" not in expected_preview_text({"segments": planned}),
            "preview verification excludes direction tags",
        )
        try:
            plan_script("[신나게]\n안녕하세요.", profile)
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: tag-only segment preflight")
        try:
            validate_korean_only("가격은 100원입니다.")
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: 숫자 발음 사전검사")
        try:
            validate_korean_only("[API] 사용법입니다.")
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: 대괄호 영문 발음 사전검사")
        qc = score_candidate(
            expected_text="안녕하세요",
            transcript_text="안녕하세요.",
            transcript_language_code="ko",
            candidate_metrics=metrics,
            reference_profile=profile,
            alignment={"characters": [{"text": "안", "start": 0, "end": 0.1}], "loss": 0.1},
        )
        require(qc["edit_distance"] == 0, "strict transcript comparison")
        require(qc["requires_human_listening"] is True, "human listening flag")
        focus_alignment = {
            "characters": [
                {
                    "text": character,
                    "start": index * 0.1,
                    "end": (index + 1) * 0.1,
                }
                for index, character in enumerate("일반 보습제로는")
            ]
        }
        focus_start, focus_end = focus_phrase_interval(
            focus_alignment,
            "일반 보습제",
        )
        require(
            0.0 <= focus_start < focus_end,
            "focused pronunciation alignment interval",
        )
        duplicate_focus_alignment = {
            "characters": [
                {
                    "text": character,
                    "start": index * 0.1,
                    "end": (index + 1) * 0.1,
                }
                for index, character in enumerate("일반 보습제 일반 보습제")
            ]
        }
        try:
            focus_phrase_interval(duplicate_focus_alignment, "일반 보습제")
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: duplicate focus phrase")
        boundary_alignment = {
            "characters": [
                {
                    "text": character,
                    "start": index * 0.1,
                    "end": (index + 1) * 0.1,
                }
                for index, character in enumerate("앞 일반, 뒤")
            ]
        }
        boundary_start, boundary_end = focus_phrase_interval(
            boundary_alignment,
            "일반",
        )
        require(
            abs(boundary_start - 0.1) < 1e-9
            and abs(boundary_end - 0.4) < 1e-9,
            "focused pronunciation preserves adjacent nonlexical boundaries",
        )
        audio_start_alignment = {
            "characters": [
                {
                    "text": character,
                    "start": 0.1 + index * 0.1,
                    "end": 0.2 + index * 0.1,
                }
                for index, character in enumerate("와 진짜")
            ]
        }
        audio_start, audio_start_end = focus_phrase_interval(
            audio_start_alignment,
            "와 진짜",
        )
        require(
            abs(audio_start) < 1e-9
            and abs(audio_start_end - 0.5) < 1e-9,
            "focused pronunciation preserves audio-start boundary",
        )
        audio_end_alignment = {
            "characters": [
                {"text": "끝", "start": 0.1, "end": 0.3},
                {"text": "!", "start": 0.3, "end": 0.3},
            ]
        }
        audio_end_start, audio_end = focus_phrase_interval(
            audio_end_alignment,
            "끝",
            audio_duration_seconds=0.75,
        )
        require(
            abs(audio_end_start) < 1e-9
            and abs(audio_end - 0.75) < 1e-9,
            "focused pronunciation preserves audio-end boundary",
        )
        require(
            focus_clip_silence_padding_seconds(
                start_seconds=0.0,
                end_seconds=0.75,
                audio_duration_seconds=0.75,
            )
            == 0.0
            and focus_clip_silence_padding_seconds(
                start_seconds=0.1,
                end_seconds=0.5,
                audio_duration_seconds=0.75,
            )
            == 0.2,
            "focused pronunciation full-audio padding policy",
        )
        focused_qc = attach_focus_pronunciation_qc(
            dict(qc, checks=dict(qc["checks"])),
            required=True,
            results=[{"phrase": "일반 보습제", "passed": True}],
        )
        require(
            focused_qc["checks"]["focused_pronunciation_consensus"],
            "focused pronunciation consensus pass",
        )
        failed_focused_qc = attach_focus_pronunciation_qc(
            dict(qc, checks=dict(qc["checks"])),
            required=True,
            results=[{"phrase": "일반 보습제", "passed": False}],
        )
        require(
            not failed_focused_qc["auto_pass"],
            "focused pronunciation mismatch must fail",
        )
        require(
            canonicalize_stt_number_notation(
                "제가 진짜 삼 일 동안 매일 발랐는데 차이 미쳤죠?",
                "제가 진짜 3일 동안 매일 발랐는데 차이 미쳤죠?",
            )
            == "제가 진짜 삼일 동안 매일 발랐는데 차이 미쳤죠?",
            "STT numeric notation equivalence",
        )
        require(
            canonicalize_stt_number_notation(
                "오직 아래 링크에서만 사십구 퍼센트 할인 중!",
                "오직 아래 링크에서만 49% 할인 중",
            )
            == "오직 아래 링크에서만 사십구 퍼센트 할인 중",
            "STT multi-digit percent notation equivalence",
        )
        require(
            canonicalize_stt_number_notation(
                "실제 후기만 천백 개가 넘었어요.",
                "실제 후기만 1,100개가 넘었어요.",
            )
            == "실제 후기만 천백개가 넘었어요.",
            "STT comma-separated integer notation equivalence",
        )
        require(
            canonicalize_stt_number_notation(
                "십이만삼천사백오십육",
                "123456",
            )
            == "십이만삼천사백오십육",
            "STT long integer notation equivalence preserves expanded candidate",
        )
        for unsafe_numeric_notation in ("-49%", "123.4%", "049%", "11,00%"):
            require(
                canonicalize_stt_number_notation(
                    "사십구 퍼센트",
                    unsafe_numeric_notation,
                )
                == unsafe_numeric_notation,
                f"STT unsafe numeric notation fails closed: {unsafe_numeric_notation}",
            )
        require(
            canonicalize_stt_number_notation(
                "제가 진짜 삼 일 동안 매일 발랐는데 차이 미쳤죠?",
                "제가 진짜 3일 동안 매일 받았는데 차이 미쳤죠?",
            )
            == "제가 진짜 3일 동안 매일 받았는데 차이 미쳤죠?",
            "STT numeric notation must not mask other errors",
        )
        require(
            canonicalize_stt_notation(
                "정식 인증받은 의료기기 엠디 크림이 있다길래 써봤거든요?",
                "정식 인증받은 의료기기 MD 크림이 있다길래 써봤거든요?",
            )
            == "정식 인증받은 의료기기 엠디 크림이 있다길래 써봤거든요?",
            "STT acronym notation equivalence",
        )
        require(
            canonicalize_stt_notation(
                "정식 인증받은 의료기기 엠디 크림이 있다길래 써봤거든요?",
                "정식 인증받은 의료기기 앤디 크림이 있다길래 써봤거든요?",
            )
            == "정식 인증받은 의료기기 앤디 크림이 있다길래 써봤거든요?",
            "STT acronym notation must not mask a mispronunciation",
        )

        missing_language_qc = score_candidate(
            expected_text="안녕하세요",
            transcript_text="안녕하세요",
            transcript_language_code=None,
            candidate_metrics=metrics,
            reference_profile=profile,
            alignment={
                "characters": [
                    {
                        "text": character,
                        "start": index * 0.1,
                        "end": (index + 1) * 0.1,
                    }
                    for index, character in enumerate("안녕하세요")
                ]
            },
        )
        require(
            not missing_language_qc["auto_pass"]
            and not missing_language_qc["checks"]["korean_language_confirmed"],
            "missing language must fail closed",
        )
        extra_speech_qc = score_candidate(
            expected_text="안녕하세요",
            transcript_text="안녕하세요 hello",
            transcript_language_code="ko",
            candidate_metrics=metrics,
            reference_profile=profile,
            alignment={
                "characters": [
                    {
                        "text": character,
                        "start": index * 0.1,
                        "end": (index + 1) * 0.1,
                    }
                    for index, character in enumerate("안녕하세요")
                ]
            },
        )
        require(
            not extra_speech_qc["auto_pass"]
            and not extra_speech_qc["checks"]["no_unexpected_lexical_content"],
            "unexpected lexical speech must fail",
        )
        zero_timing_qc = score_candidate(
            expected_text="안녕하세요",
            transcript_text="안녕하세요",
            transcript_language_code="ko",
            candidate_metrics=metrics,
            reference_profile=profile,
            alignment={
                "characters": [
                    {"text": character, "start": 0.0, "end": 0.0}
                    for character in "안녕하세요"
                ]
            },
        )
        require(
            not zero_timing_qc["auto_pass"]
            and not zero_timing_qc["checks"]["forced_alignment_timing_valid"],
            "zero-duration alignment must fail",
        )
        missing_rate_metrics = dict(metrics)
        missing_rate_metrics["syllables_per_active_second"] = None
        missing_rate_qc = score_candidate(
            expected_text="안녕하세요",
            transcript_text="안녕하세요",
            transcript_language_code="ko",
            candidate_metrics=missing_rate_metrics,
            reference_profile=profile,
            alignment={
                "characters": [
                    {
                        "text": character,
                        "start": index * 0.1,
                        "end": (index + 1) * 0.1,
                    }
                    for index, character in enumerate("안녕하세요")
                ]
            },
        )
        require(
            not missing_rate_qc["auto_pass"]
            and not missing_rate_qc["checks"]["speed_within_10_percent"],
            "missing speed must fail closed",
        )

        class FakeClient:
            def create_speech_with_timing(self, **_: Any) -> tuple[dict[str, Any], dict[str, str]]:
                return (
                    {
                        "audio_base64": base64.b64encode(wav_path.read_bytes()).decode(
                            "ascii"
                        ),
                        "alignment": {
                            "characters": list("안녕하세요"),
                            "character_start_times_seconds": [
                                0.2,
                                0.35,
                                0.5,
                                0.65,
                                0.8,
                            ],
                            "character_end_times_seconds": [
                                0.35,
                                0.5,
                                0.65,
                                0.8,
                                0.95,
                            ],
                        },
                        "normalized_alignment": None,
                    },
                    {"request-id": "offline-self-test"},
                )

            def transcribe(self, _: Path, **__: Any) -> dict[str, Any]:
                return {
                    "language_code": "ko",
                    "text": "안녕하세요",
                    "words": [],
                }

            def forced_alignment(self, _: Path, text: str) -> dict[str, Any]:
                return {
                    "characters": [
                        {"text": character, "start": index * 0.1, "end": (index + 1) * 0.1}
                        for index, character in enumerate(text)
                    ],
                    "words": [],
                    "loss": 0.1,
                }

        workflow_dir = temporary_dir / "workflow"
        initialize_job_directory(workflow_dir)
        input_script = workflow_dir / "input" / "script.txt"
        input_script.write_text("안녕하세요", encoding="utf-8")
        workflow_metrics = analyze_wav(wav_path, transcript="안녕하세요")
        test_profile = {"audio_metrics": workflow_metrics}
        atomic_write_json(workflow_dir / "reference_profile.json", test_profile)
        test_plan = {
            "version": 1,
            "created_at": utc_now(),
            "model_id": MODEL_ID,
            "original_script": "안녕하세요",
            "segments": plan_script("안녕하세요", test_profile),
        }
        atomic_write_json(workflow_dir / "script_plan.json", test_plan)
        test_job = {
            "version": 1,
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": "planned",
            "model_id": MODEL_ID,
            "max_attempts_per_batch": MAX_ATTEMPTS_PER_BATCH,
            "target_duration_seconds": None,
            "user_listening_approval_required": True,
            "voice_retention": "keep",
            "script_path": "input/script.txt",
            "voice_id": "offline-voice",
            "voice_name": "오프라인 테스트",
            "api_output_format": "wav_44100",
            "finalized": False,
        }
        write_job(workflow_dir, test_job)
        require(
            generate_pending_segments(FakeClient(), job_dir=workflow_dir),
            "offline generation state machine",
        )
        generated_job = load_json(workflow_dir / "job.json")
        generated_plan = load_json(workflow_dir / "script_plan.json")
        offline_selected_wav = (
            workflow_dir
            / str(generated_plan["segments"][0]["selected_wav"])
        )
        offline_preview_wav = (
            workflow_dir / str(generated_job["review_preview_wav"])
        )
        offline_audio_runs = [
            {
                "run": run_index,
                "settings_id": f"offline-audio-setting-{run_index}",
                "model": "offline-self-test",
                "all_passed": True,
                "segments": [
                    {
                        "index": 1,
                        "spoken_text": "안녕하세요",
                        "pronunciation_pass": True,
                        "tone_pass": True,
                        "intonation_pass": True,
                        "emotion_pass": True,
                        "speaker_character_pass": True,
                        "boundary_continuity_pass": True,
                        "no_synthesis_artifact_pass": True,
                    }
                ],
            }
            for run_index in range(1, 4)
        ]
        offline_prosody_report = {
            "schema_version": 1,
            "created_at": utc_now(),
            "job_dir": str(workflow_dir),
            "reference": {
                "path": str(wav_path.resolve()),
                "sha256": sha256_file(wav_path),
            },
            "preview": {
                "path": str(offline_preview_wav.resolve()),
                "sha256": sha256_file(offline_preview_wav),
                "review_revision": generated_job["review_revision"],
            },
            "segments": [
                {
                    "index": 1,
                    "selected_attempt": generated_plan["segments"][0][
                        "selected_attempt"
                    ],
                    "features": {
                        "sha256": sha256_file(offline_selected_wav),
                    },
                    "objective_qc": {"passed": True},
                }
            ],
            "objective_qc": {
                "passed": True,
                "flagged_segments": [],
                "status": "passed",
            },
            "audio_listening_qc": {
                "required": True,
                "required_runs": 3,
                "status": "passed",
                "passed": True,
                "evaluator": "offline-self-test-evaluator",
                "runs": offline_audio_runs,
            },
            "strict_qc": {
                "passed": True,
                "final_approval_allowed": True,
                "blocked_reason": None,
            },
        }
        offline_prosody_path = (
            workflow_dir / "review" / "prosody-listening-qc.json"
        )
        atomic_write_json(offline_prosody_path, offline_prosody_report)
        generated_job["prosody_listening_qc_report"] = relative_to_job(
            offline_prosody_path,
            workflow_dir,
        )
        generated_job["prosody_listening_qc_sha256"] = sha256_file(
            offline_prosody_path
        )
        write_job(workflow_dir, generated_job)

        class NoFallbackApiCallsClient:
            def __init__(self) -> None:
                self.transcribe_calls = 0
                self.alignment_calls = 0

            def transcribe(self, _: Path, **__: Any) -> dict[str, Any]:
                self.transcribe_calls += 1
                raise AssertionError("PCM 불일치 뒤에는 STT를 호출하면 안 됩니다.")

            def forced_alignment(
                self,
                _: Path,
                __: str,
            ) -> dict[str, Any]:
                self.alignment_calls += 1
                raise AssertionError("PCM 불일치 뒤에는 정렬을 호출하면 안 됩니다.")

        pcm_mismatch_client = NoFallbackApiCallsClient()
        pcm_mismatch_result = verify_segment_chunk_preview_fallback(
            pcm_mismatch_client,
            job_dir=workflow_dir,
            preview_wav=focus_clip_path,
            plan=generated_plan,
            evidence_dir=(
                workflow_dir
                / "review"
                / "approval-evidence"
                / "offline-pcm-mismatch"
            ),
        )
        require(
            not pcm_mismatch_result["auto_pass"]
            and not pcm_mismatch_result["checks"][
                "preview_pcm_matches_selected_segments"
            ]
            and pcm_mismatch_client.transcribe_calls == 0
            and pcm_mismatch_client.alignment_calls == 0,
            "PCM mismatch must fail before fallback API calls",
        )

        class BadSegmentTranscriptClient(FakeClient):
            def __init__(self) -> None:
                self.transcribe_calls = 0
                self.alignment_calls = 0

            def transcribe(self, _: Path, **__: Any) -> dict[str, Any]:
                self.transcribe_calls += 1
                return {
                    "language_code": "ko",
                    "text": "반갑습니다",
                    "words": [],
                }

            def forced_alignment(
                self,
                path: Path,
                text: str,
            ) -> dict[str, Any]:
                self.alignment_calls += 1
                return super().forced_alignment(path, text)

        bad_segment_client = BadSegmentTranscriptClient()
        bad_segment_result = verify_segment_chunk_preview_fallback(
            bad_segment_client,
            job_dir=workflow_dir,
            preview_wav=workflow_dir / "review" / "full_preview.wav",
            plan=generated_plan,
            evidence_dir=(
                workflow_dir
                / "review"
                / "approval-evidence"
                / "offline-bad-segment"
            ),
        )
        require(
            not bad_segment_result["auto_pass"]
            and not bad_segment_result["checks"]["exact_hangul_transcript"]
            and bad_segment_client.transcribe_calls
            == len(FOCUS_TRANSCRIPTION_VARIANTS)
            and bad_segment_client.alignment_calls == 0,
            "segment transcript failure must skip forced alignment and fail",
        )

        substitution_client = BadSegmentTranscriptClient()
        try:
            verify_full_preview_automatic_qc(
                substitution_client,
                job_dir=workflow_dir,
                preview_wav=workflow_dir / "review" / "full_preview.wav",
                expected_text=expected_preview_text(generated_plan),
                approval_id="offline-long-substitution",
                plan=generated_plan,
            )
        except WorkflowError:
            pass
        else:
            raise WorkflowError(
                "self-test 실패: long-preview substitution consensus"
            )
        substitution_record = load_json(
            workflow_dir
            / "review"
            / "approval-evidence"
            / "offline-long-substitution"
            / "verification.json"
        )
        require(
            substitution_client.transcribe_calls
            == 1 + len(FOCUS_TRANSCRIPTION_VARIANTS)
            and substitution_client.alignment_calls == 0
            and not substitution_record[
                "long_form_transcript_diagnostic"
            ]["fallback_eligibility"][
                "diagnostic_order_preserving_omission_only"
            ],
            "long-preview substitution must fail without segment consensus",
        )

        interrupted_job = dict(generated_job)
        interrupted_job["status"] = "generating_and_auto_qc"
        write_job(workflow_dir, interrupted_job)
        mark_interrupted_job(workflow_dir)
        marked_job = load_json(workflow_dir / "job.json")
        require(
            marked_job["status"] == "interrupted_recoverable"
            and bool(marked_job.get("additional_generation_token")),
            "interruption state recovery",
        )
        initialization_dir = temporary_dir / "initialization-interruption"
        initialize_job_directory(initialization_dir)
        write_job(
            initialization_dir,
            {
                "status": "initializing",
                "created_at": utc_now(),
                "finalized": False,
            },
        )
        mark_interrupted_job(initialization_dir)
        initialization_interrupted_job = load_json(
            initialization_dir / "job.json"
        )
        require(
            initialization_interrupted_job["status"]
            == "initialization_interrupted_new_job_required"
            and not initialization_interrupted_job.get(
                "additional_generation_token"
            ),
            "initialization interruption must not advertise regeneration",
        )
        write_job(workflow_dir, generated_job)
        wrong_state_job = dict(generated_job)
        wrong_state_job["status"] = "generating_and_auto_qc"
        write_job(workflow_dir, wrong_state_job)
        wrong_state_args = argparse.Namespace(
            job_dir=workflow_dir,
            segments="all",
            confirmation=LISTENING_APPROVAL_CONFIRMATION,
            preview_sha256=generated_job["review_preview_sha256"],
        )
        try:
            command_approve(wrong_state_args)
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: wrong-state approval")
        write_job(workflow_dir, generated_job)
        negative_confirmation_args = argparse.Namespace(
            job_dir=workflow_dir,
            segments="all",
            confirmation="사용자가 전체 미리보기를 듣지 않았지만 승인함",
            preview_sha256=generated_job["review_preview_sha256"],
        )
        try:
            command_approve(negative_confirmation_args)
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: negative listening confirmation")
        stale_approval_args = argparse.Namespace(
            job_dir=workflow_dir,
            segments="all",
            confirmation=LISTENING_APPROVAL_CONFIRMATION,
            preview_sha256="0" * 64,
        )
        try:
            command_approve(stale_approval_args)
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: stale preview approval")
        require(
            not (workflow_dir / "final").exists(),
            "no final output before current preview approval",
        )
        delegated_dir = temporary_dir / "delegated-workflow"
        shutil.copytree(workflow_dir, delegated_dir)
        delegated_args = argparse.Namespace(
            job_dir=delegated_dir,
            segments="all",
            confirmation=DELEGATED_AUTO_APPROVAL_CONFIRMATION,
            preview_sha256=generated_job["review_preview_sha256"],
        )
        require(
            _command_delegate_approve_locked(
                delegated_args,
                delegated_dir,
                client=FakeClient(),
            )
            == 0,
            "delegated automatic approval",
        )
        delegated_job = load_json(delegated_dir / "job.json")
        delegated_report = load_json(
            delegated_dir / "final" / "qc_report.json"
        )
        require(
            delegated_job["status"] == "user_delegated_auto_qc_final"
            and delegated_job.get("user_listening_waived") is True
            and delegated_report["status"] == "user_delegated_auto_qc_final"
            and delegated_report.get("human_listening_completed") is False,
            "truthful delegated final state",
        )
        require(
            command_delegate_approve(delegated_args) == 0,
            "delegated finalization idempotent replay",
        )

        class LongPreviewOmissionClient(FakeClient):
            def transcribe(self, path: Path, **kwargs: Any) -> dict[str, Any]:
                if path.name == "full_preview.wav":
                    return {
                        "language_code": "ko",
                        "text": "안녕",
                        "words": [],
                    }
                return super().transcribe(path, **kwargs)

        delegated_fallback_dir = temporary_dir / "delegated-fallback-workflow"
        shutil.copytree(workflow_dir, delegated_fallback_dir)
        delegated_fallback_args = argparse.Namespace(
            job_dir=delegated_fallback_dir,
            segments="all",
            confirmation=DELEGATED_AUTO_APPROVAL_CONFIRMATION,
            preview_sha256=generated_job["review_preview_sha256"],
        )
        require(
            _command_delegate_approve_locked(
                delegated_fallback_args,
                delegated_fallback_dir,
                client=LongPreviewOmissionClient(),
            )
            == 0,
            "delegated long-preview omission fallback",
        )
        delegated_fallback_report = load_json(
            delegated_fallback_dir / "final" / "qc_report.json"
        )
        delegated_fallback_qc = delegated_fallback_report[
            "delegated_auto_qc_verification"
        ]["full_preview_qc"]
        require(
            delegated_fallback_qc["verification_strategy"]
            == "pcm_locked_segment_chunk_fallback"
            and delegated_fallback_qc["checks"][
                "preview_pcm_matches_selected_segments"
            ]
            and delegated_fallback_qc["auto_pass"],
            "PCM-locked per-segment fallback must pass only on exact reconstruction",
        )

        class MissingVerificationClient:
            def get_voice(self, _: str) -> dict[str, Any]:
                return {}

        try:
            verify_existing_voice(
                MissingVerificationClient(),
                voice_id="missing-verification",
            )
        except WorkflowError:
            pass
        else:
            raise WorkflowError("self-test 실패: missing voice verification")
        approval_args = argparse.Namespace(
            job_dir=workflow_dir,
            segments="all",
            confirmation=LISTENING_APPROVAL_CONFIRMATION,
            preview_sha256=generated_job["review_preview_sha256"],
        )
        require(command_approve(approval_args) == 0, "valid preview approval")
        finalized_job = load_json(workflow_dir / "job.json")
        require(
            finalized_job["status"] == "user_approved_final",
            "final state",
        )
        require(
            (workflow_dir / "final" / "final.wav").exists(),
            "final wav assembly",
        )
        require(
            (workflow_dir / "final" / "final.mp3").exists(),
            "final mp3 assembly",
        )
    print(
        json.dumps(
            {
                "status": "passed",
                "tests": [
                    "http_session_environment_isolation",
                    "audio_metrics",
                    "focused_audio_interval_extraction",
                    "focused_audio_silence_padding",
                    "non_finite_target_duration_rejected",
                    "single_speaker_reference_gate",
                    "multi_speaker_reference_rejected",
                    "korean_script_planning",
                    "preview_verification_excludes_direction_tags",
                    "tag_only_segment_preflight",
                    "ambiguous_token_preflight",
                    "strict_transcript_comparison",
                    "stt_numeric_notation_equivalence",
                    "stt_acronym_notation_equivalence",
                    "focused_pronunciation_consensus",
                    "duplicate_focus_phrase_rejected",
                    "focused_nonlexical_boundary_preserved",
                    "focused_audio_start_boundary_preserved",
                    "focused_audio_end_boundary_preserved",
                    "focused_full_audio_padding_omitted",
                    "unknown_qc_values_fail_closed",
                    "unexpected_lexical_speech_rejected",
                    "zero_duration_alignment_rejected",
                    "human_approval_invariant",
                    "delegated_automatic_qc_truthfulness",
                    "delegated_finalization_idempotent_replay",
                    "delegated_long_preview_omission_fallback",
                    "mixed_bit_depth_concat_frame_preservation",
                    "mixed_bit_depth_concat_pcm_equality",
                    "fallback_pcm_mismatch_fails_before_api",
                    "fallback_segment_stt_failure_skips_alignment",
                    "long_preview_substitution_requires_segment_consensus",
                    "negative_listening_confirmation_rejected",
                    "stale_preview_approval_rejected",
                    "wrong_state_approval_rejected",
                    "interruption_recovery_state",
                    "initialization_interruption_state",
                    "missing_voice_verification_rejected",
                    "offline_generation_state_machine",
                    "final_output_assembly",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="레퍼런스 음성 기반 ElevenLabs 한국어 TTS 생성·검수 워크플로우"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    doctor = subparsers.add_parser("doctor", help="로컬 및 API 준비 상태 확인")
    doctor.add_argument("--live", action="store_true", help="실제 API 권한과 모델도 확인")
    doctor.set_defaults(func=command_doctor)

    list_voices = subparsers.add_parser("list-voices", help="저장된 보이스 목록 확인")
    list_voices.add_argument(
        "--cloud",
        action="store_true",
        help="ElevenLabs 계정의 전체 보이스 목록도 조회",
    )
    list_voices.set_defaults(func=command_list_voices)

    run = subparsers.add_parser("run", help="새 작업 생성부터 자동 검수까지 실행")
    run.add_argument("--script", type=Path, required=True, help="UTF-8 한국어 대본 파일")
    run.add_argument("--output-dir", type=Path, required=True, help="비어 있는 새 작업 폴더")
    voice_source = run.add_mutually_exclusive_group(required=True)
    voice_source.add_argument("--reference-video", type=Path, help="새로 복제할 레퍼런스 영상")
    voice_source.add_argument("--voice-id", help="기존 ElevenLabs voice_id")
    voice_source.add_argument("--existing-voice-name", help="기존 보이스의 정확한 이름")
    run.add_argument("--new-voice-name", help="새 복제 보이스에 저장할 이름")
    run.add_argument(
        "--style-reference-video",
        type=Path,
        help="기존 보이스의 속도·감정 기준 영상",
    )
    run.add_argument(
        "--consent-confirmed",
        action="store_true",
        help="복제 또는 재사용할 음성의 사용 권한과 동의를 확인했음을 명시",
    )
    run.add_argument(
        "--target-duration",
        type=float,
        help="선택적 전체 목표 길이(초). 기본값은 레퍼런스 평균 속도",
    )
    run.set_defaults(func=command_run)

    status = subparsers.add_parser("status", help="작업 상태와 청취 파일 확인")
    status.add_argument("--job-dir", type=Path, required=True)
    status.set_defaults(func=command_status)

    rebuild_preview = subparsers.add_parser(
        "rebuild-preview",
        help="선택 음성을 재생성하지 않고 안전한 전체 미리보기로 다시 조립",
    )
    rebuild_preview.add_argument("--job-dir", type=Path, required=True)
    rebuild_preview.add_argument(
        "--reason",
        required=True,
        help="미리보기를 다시 조립하는 이유",
    )
    rebuild_preview.set_defaults(func=command_rebuild_preview)

    prosody_qc = subparsers.add_parser(
        "prosody-qc",
        help="레퍼런스 보정형 운율·문장 경계와 실제 오디오 판정 증거 검수",
    )
    prosody_qc.add_argument("--job-dir", type=Path, required=True)
    prosody_qc.add_argument(
        "--reference-wav",
        type=Path,
        required=True,
        help="배경음악·효과음이 제거된 레퍼런스 화자 WAV",
    )
    prosody_qc.add_argument(
        "--audio-judge-report",
        type=Path,
        help="서로 다른 설정으로 3회 수행한 실제 오디오 A/B 판정 JSON",
    )
    prosody_qc.set_defaults(func=command_prosody_qc)

    approve = subparsers.add_parser("approve", help="사용자 청취 승인을 기록하고 최종본 생성")
    approve.add_argument("--job-dir", type=Path, required=True)
    approve.add_argument(
        "--segments",
        default="all",
        help="'all' 또는 쉼표로 구분한 문장 번호",
    )
    approve.add_argument(
        "--confirmation",
        required=True,
        help=f"정확한 승인 문구: {LISTENING_APPROVAL_CONFIRMATION}",
    )
    approve.add_argument(
        "--preview-sha256",
        required=True,
        help="status에 표시된 현재 전체 미리보기 SHA-256",
    )
    approve.set_defaults(func=command_approve)

    delegate_approve = subparsers.add_parser(
        "delegate-approve",
        help="사용자 청취 생략 위임을 기록하고 강화 자동 검증 후 최종본 생성",
    )
    delegate_approve.add_argument("--job-dir", type=Path, required=True)
    delegate_approve.add_argument(
        "--segments",
        default="all",
        help="'all' 또는 쉼표로 구분한 문장 번호",
    )
    delegate_approve.add_argument(
        "--confirmation",
        required=True,
        help=f"정확한 위임 문구: {DELEGATED_AUTO_APPROVAL_CONFIRMATION}",
    )
    delegate_approve.add_argument(
        "--preview-sha256",
        required=True,
        help="status에 표시된 현재 전체 미리보기 SHA-256",
    )
    delegate_approve.set_defaults(func=command_delegate_approve)

    select_attempt = subparsers.add_parser(
        "select-attempt",
        help="사용자가 들은 기존 후보를 재검수한 뒤 문장 선택본으로 복원",
    )
    select_attempt.add_argument("--job-dir", type=Path, required=True)
    select_attempt.add_argument("--segment", type=int, required=True)
    select_attempt.add_argument("--attempt", type=int, required=True)
    select_attempt.add_argument(
        "--confirmation",
        required=True,
        help="사용자가 해당 후보를 직접 듣고 선택한 문구",
    )
    select_attempt.set_defaults(func=command_select_attempt)

    set_focus = subparsers.add_parser(
        "set-focus",
        help="아직 선택되지 않은 문장에 집중 발음 반복 STT 구절 설정",
    )
    set_focus.add_argument("--job-dir", type=Path, required=True)
    set_focus.add_argument("--segment", type=int, required=True)
    set_focus.add_argument(
        "--phrase",
        action="append",
        required=True,
        help="문장에 정확히 존재하는 집중 발음 구절. 여러 번 지정 가능",
    )
    set_focus.add_argument("--reason", required=True)
    set_focus.add_argument(
        "--direction",
        help="선택적 Eleven v3 전달 방향(한국어 별칭 또는 영문 태그)",
    )
    set_focus.add_argument(
        "--tts-override",
        help="선택적 발음 유도용 TTS 문장. 원래 검수 문장은 변경하지 않음",
    )
    set_focus.set_defaults(func=command_set_focus)

    regenerate = subparsers.add_parser(
        "regenerate",
        help="거절된 문장만 최대 5회 추가 생성",
    )
    regenerate.add_argument("--job-dir", type=Path, required=True)
    regenerate.add_argument("--segments", required=True, help="쉼표로 구분한 문장 번호")
    regenerate.add_argument("--feedback", required=True, help="사용자의 거절 사유")
    regenerate.add_argument(
        "--approval-token",
        help=(
            "내부 재생성 상태 토큰. 지속 설정의 상시 생성 허용이 활성화되면 "
            "생략할 수 있습니다."
        ),
    )
    regenerate.add_argument("--direction", help="새 감정·전달 방향")
    regenerate.add_argument(
        "--tts-override",
        help="발음 유도를 위한 한국어 생성용 문장. 원래 대본과 별도로 기록됨",
    )
    regenerate.add_argument(
        "--focus-phrase",
        action="append",
        help="강제 정렬 구간을 잘라 3회 반복 STT할 집중 발음 구절",
    )
    regenerate.add_argument(
        "--additional-cost-approved",
        action="store_true",
        help=(
            "지속 설정이 없는 환경의 레거시 건별 허용 플래그. 현재 로컬 "
            "사용자의 상시 생성 허용에서는 생략할 수 있습니다."
        ),
    )
    regenerate.set_defaults(func=command_regenerate)

    self_test = subparsers.add_parser("self-test", help="API를 사용하지 않는 내부 테스트")
    self_test.set_defaults(func=command_self_test)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except (WorkflowError, AudioToolError, ApiError) as exc:
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2
    except KeyboardInterrupt:
        if args.command == "run":
            mark_interrupted_job(args.output_dir.expanduser().resolve())
        elif args.command == "regenerate":
            mark_interrupted_job(args.job_dir.expanduser().resolve())
        print(
            json.dumps(
                {
                    "status": "interrupted",
                    "message": "사용자가 작업을 중단했습니다. 기존 상태 파일은 보존됩니다.",
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

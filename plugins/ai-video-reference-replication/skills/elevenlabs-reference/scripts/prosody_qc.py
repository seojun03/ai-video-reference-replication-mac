#!/usr/bin/env python3
"""Reference-calibrated objective prosody and sentence-boundary QC.

This module deliberately does not claim to hear or understand audio.  It measures
acoustic evidence and validates a separately produced three-run audio-judge report.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

from audio_tools import AudioToolError, _load_wav_mono_float
from workflow_core import (
    WorkflowError,
    atomic_write_json,
    load_json,
    normalize_for_comparison,
    sha256_file,
    utc_now,
)


SCHEMA_VERSION = 1
AUDIO_JUDGE_REQUIRED_RUNS = 3
FAMILY_WARNING_Z = 3.0
FAMILY_CRITICAL_Z = 4.75

METRIC_MIN_SCALES = {
    "pitch_center_semitones": 0.85,
    "pitch_range_semitones": 1.25,
    "pitch_contour_std_semitones": 0.45,
    "pitch_slope_semitones": 0.9,
    "pitch_end_delta_semitones": 0.8,
    "active_rms_dbfs": 1.75,
    "energy_dynamic_db": 1.5,
    "energy_slope_db": 1.1,
    "pause_ratio": 0.055,
    "spectral_centroid_hz": 280.0,
    "zero_crossing_rate": 0.012,
}

REFERENCE_METRICS = tuple(METRIC_MIN_SCALES)


def _round(value: float | None, digits: int = 5) -> float | None:
    if value is None or not math.isfinite(float(value)):
        return None
    return round(float(value), digits)


def _runs(mask: np.ndarray, value: bool) -> list[tuple[int, int]]:
    if mask.size == 0:
        return []
    target = mask == value
    padded = np.concatenate(([False], target, [False]))
    transitions = np.flatnonzero(padded[1:] != padded[:-1])
    return [
        (int(start), int(end))
        for start, end in transitions.reshape(-1, 2)
    ]


def _frame_data(
    samples: np.ndarray,
    sample_rate: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
    # Keep VAD identical to the workflow's established speed gate.  A longer
    # window raises the estimated noise floor around short Korean syllables and
    # can incorrectly halve active-speech time.
    frame_samples = max(256, int(round(sample_rate * 0.025)))
    hop_samples = max(1, int(round(sample_rate * 0.01)))
    if samples.size < frame_samples:
        samples = np.pad(samples, (0, frame_samples - samples.size))
    starts = np.arange(
        0,
        max(1, samples.size - frame_samples + 1),
        hop_samples,
        dtype=np.int64,
    )
    rms = np.empty(starts.size, dtype=np.float64)
    zcr = np.empty(starts.size, dtype=np.float64)
    for index, start in enumerate(starts):
        frame = samples[start : start + frame_samples]
        rms[index] = math.sqrt(float(np.mean(np.square(frame))) + 1e-12)
        signs = np.signbit(frame)
        zcr[index] = float(np.mean(signs[1:] != signs[:-1]))
    floor = float(np.percentile(rms, 20))
    threshold = max(10 ** (-46.0 / 20.0), floor * 2.8, float(rms.max()) * 0.025)
    active = rms >= threshold
    return starts, rms, zcr, frame_samples, hop_samples


def _pitch_track(
    samples: np.ndarray,
    sample_rate: int,
    starts: np.ndarray,
    active: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    window_size = max(256, int(round(sample_rate * 0.05)))
    minimum_lag = max(1, int(sample_rate / 430.0))
    maximum_lag = min(window_size - 2, int(sample_rate / 65.0))
    selected = np.flatnonzero(active)[::2]
    times: list[float] = []
    frequencies: list[float] = []
    confidences: list[float] = []
    window = np.hanning(window_size)
    fft_size = 1 << max(1, (2 * window_size - 1).bit_length())
    for frame_index in selected:
        start = int(starts[frame_index])
        frame = samples[start : start + window_size]
        if frame.size < window_size:
            continue
        frame = (frame - float(frame.mean())) * window
        energy = float(np.dot(frame, frame))
        if energy < 1e-7:
            continue
        spectrum = np.fft.rfft(frame, n=fft_size)
        autocorrelation = np.fft.irfft(
            spectrum * np.conjugate(spectrum),
            n=fft_size,
        )[:window_size]
        search = autocorrelation[minimum_lag : maximum_lag + 1]
        if search.size == 0:
            continue
        lag = int(np.argmax(search)) + minimum_lag
        confidence = float(
            autocorrelation[lag] / max(float(autocorrelation[0]), 1e-12)
        )
        if confidence < 0.30:
            continue
        times.append((start + window_size / 2.0) / sample_rate)
        frequencies.append(sample_rate / lag)
        confidences.append(confidence)
    if not frequencies:
        return (
            np.asarray([], dtype=np.float64),
            np.asarray([], dtype=np.float64),
            np.asarray([], dtype=np.float64),
        )
    frequency_values = np.asarray(frequencies, dtype=np.float64)
    if frequency_values.size >= 5:
        semitones = 12.0 * np.log2(np.maximum(frequency_values, 1e-9))
        padded = np.pad(semitones, (2, 2), mode="edge")
        smoothed = np.asarray(
            [np.median(padded[index : index + 5]) for index in range(semitones.size)]
        )
        # Octave mistakes are common in autocorrelation.  Keep the raw value only
        # when it is closer to the local median than either octave alternative.
        alternatives = np.stack((semitones - 12.0, semitones, semitones + 12.0))
        nearest = np.argmin(np.abs(alternatives - smoothed), axis=0)
        semitones = alternatives[nearest, np.arange(semitones.size)]
        frequency_values = np.power(2.0, semitones / 12.0)
    return (
        np.asarray(times, dtype=np.float64),
        frequency_values,
        np.asarray(confidences, dtype=np.float64),
    )


def _spectral_summary(
    samples: np.ndarray,
    sample_rate: int,
    starts: np.ndarray,
    active: np.ndarray,
    frame_samples: int,
) -> tuple[float | None, list[float] | None]:
    selected = np.flatnonzero(active)[::4]
    if selected.size == 0:
        return None, None
    window = np.hanning(frame_samples)
    fft_size = 1 << max(1, (frame_samples - 1).bit_length())
    frequencies = np.fft.rfftfreq(fft_size, 1.0 / sample_rate)
    valid = (frequencies >= 70.0) & (frequencies <= 8_000.0)
    valid_frequencies = frequencies[valid]
    centroids: list[float] = []
    embeddings: list[np.ndarray] = []
    # Log-spaced bands provide a deterministic, model-free timbre proxy.  This is
    # intentionally reported as an acoustic embedding, never a speaker embedding.
    band_edges = np.geomspace(80.0, 8_000.0, 25)
    for frame_index in selected:
        start = int(starts[frame_index])
        frame = samples[start : start + frame_samples]
        if frame.size < frame_samples:
            continue
        power = np.square(np.abs(np.fft.rfft(frame * window, n=fft_size)))
        valid_power = power[valid]
        total = float(valid_power.sum())
        if total <= 1e-12:
            continue
        centroids.append(float(np.sum(valid_frequencies * valid_power) / total))
        bands = []
        for low, high in zip(band_edges[:-1], band_edges[1:]):
            mask = (frequencies >= low) & (frequencies < high)
            bands.append(math.log(float(power[mask].sum()) + 1e-12))
        embedding = np.asarray(bands, dtype=np.float64)
        embedding -= float(embedding.mean())
        norm = float(np.linalg.norm(embedding))
        if norm > 1e-9:
            embeddings.append(embedding / norm)
    if not centroids or not embeddings:
        return None, None
    mean_embedding = np.mean(np.stack(embeddings), axis=0)
    norm = float(np.linalg.norm(mean_embedding))
    if norm > 1e-9:
        mean_embedding /= norm
    return float(np.median(centroids)), [
        round(float(value), 7) for value in mean_embedding
    ]


def _linear_slope(values: np.ndarray) -> float | None:
    if values.size < 3:
        return None
    x = np.linspace(-0.5, 0.5, values.size)
    design = np.column_stack((x, np.ones(x.size)))
    slope, _ = np.linalg.lstsq(design, values, rcond=None)[0]
    return float(slope)


def extract_prosody_features(
    path: Path,
    *,
    transcript: str = "",
    reference_pitch_hz: float | None = None,
) -> dict[str, Any]:
    sample_rate, samples = _load_wav_mono_float(path)
    if samples.size == 0:
        raise AudioToolError(f"빈 오디오 파일입니다: {path}")
    starts, rms, zcr, frame_samples, hop_samples = _frame_data(samples, sample_rate)
    floor = float(np.percentile(rms, 20))
    threshold = max(10 ** (-46.0 / 20.0), floor * 2.8, float(rms.max()) * 0.025)
    active = rms >= threshold
    active_indices = np.flatnonzero(active)
    total_seconds = samples.size / sample_rate
    active_seconds = min(
        total_seconds,
        active_indices.size * hop_samples / sample_rate,
    )
    rms_db = 20.0 * np.log10(np.maximum(rms, 1e-12))
    active_db = rms_db[active]
    pitch_times, pitch_hz, pitch_confidence = _pitch_track(
        samples,
        sample_rate,
        starts,
        active,
    )
    spectral_centroid, embedding = _spectral_summary(
        samples,
        sample_rate,
        starts,
        active,
        frame_samples,
    )

    internal_pause_seconds = 0.0
    pause_count = 0
    for start, end in _runs(active, False):
        if start == 0 or end == active.size:
            continue
        duration = (end - start) * hop_samples / sample_rate
        if duration >= 0.12:
            pause_count += 1
            internal_pause_seconds += duration

    pitch_median = float(np.median(pitch_hz)) if pitch_hz.size else None
    pitch_semitones = (
        12.0 * np.log2(pitch_hz / max(float(pitch_median), 1e-9))
        if pitch_median is not None
        else np.asarray([], dtype=np.float64)
    )
    pitch_center_semitones = None
    if (
        pitch_median is not None
        and reference_pitch_hz is not None
        and reference_pitch_hz > 0
    ):
        pitch_center_semitones = 12.0 * math.log2(
            pitch_median / reference_pitch_hz
        )
    pitch_start_hz = (
        float(np.median(pitch_hz[: max(1, pitch_hz.size // 4)]))
        if pitch_hz.size
        else None
    )
    pitch_end_hz = (
        float(np.median(pitch_hz[-max(1, pitch_hz.size // 4) :]))
        if pitch_hz.size
        else None
    )
    pitch_end_delta = None
    if pitch_start_hz and pitch_end_hz:
        pitch_end_delta = 12.0 * math.log2(pitch_end_hz / pitch_start_hz)

    active_rms_dbfs = (
        20.0
        * math.log10(
            math.sqrt(
                float(
                    np.mean(
                        np.square(
                            samples[
                                np.concatenate(
                                    [
                                        np.arange(
                                            int(starts[index]),
                                            min(
                                                samples.size,
                                                int(starts[index]) + hop_samples,
                                            ),
                                            dtype=np.int64,
                                        )
                                        for index in active_indices
                                    ]
                                )
                            ]
                        )
                    )
                )
                + 1e-12
            )
        )
        if active_indices.size
        else None
    )
    energy_start = (
        float(np.median(active_db[: max(1, active_db.size // 4)]))
        if active_db.size
        else None
    )
    energy_end = (
        float(np.median(active_db[-max(1, active_db.size // 4) :]))
        if active_db.size
        else None
    )
    hangul_count = len(normalize_for_comparison(transcript))
    rate = (
        hangul_count / active_seconds
        if hangul_count and active_seconds > 0
        else None
    )
    return {
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "sample_rate": sample_rate,
        "duration_seconds": _round(total_seconds),
        "active_speech_seconds": _round(active_seconds),
        "pause_count": pause_count,
        "pause_ratio": _round(
            internal_pause_seconds / max(active_seconds + internal_pause_seconds, 1e-9)
        ),
        "syllables_per_active_second": _round(rate),
        "pitch_median_hz": _round(pitch_median, 3),
        "pitch_start_hz": _round(pitch_start_hz, 3),
        "pitch_end_hz": _round(pitch_end_hz, 3),
        "pitch_center_semitones": _round(pitch_center_semitones),
        "pitch_range_semitones": _round(
            (
                float(np.percentile(pitch_semitones, 90))
                - float(np.percentile(pitch_semitones, 10))
            )
            if pitch_semitones.size
            else None
        ),
        "pitch_contour_std_semitones": _round(
            float(np.std(pitch_semitones)) if pitch_semitones.size else None
        ),
        "pitch_slope_semitones": _round(_linear_slope(pitch_semitones)),
        "pitch_end_delta_semitones": _round(pitch_end_delta),
        "pitch_voiced_frame_count": int(pitch_hz.size),
        "pitch_confidence_median": _round(
            float(np.median(pitch_confidence)) if pitch_confidence.size else None
        ),
        "active_rms_dbfs": _round(active_rms_dbfs),
        "energy_start_dbfs": _round(energy_start),
        "energy_end_dbfs": _round(energy_end),
        "energy_dynamic_db": _round(
            (
                float(np.percentile(active_db, 90))
                - float(np.percentile(active_db, 10))
            )
            if active_db.size
            else None
        ),
        "energy_slope_db": _round(_linear_slope(active_db)),
        "spectral_centroid_hz": _round(spectral_centroid, 2),
        "zero_crossing_rate": _round(
            float(np.median(zcr[active])) if active_indices.size else None
        ),
        "acoustic_embedding": embedding,
    }


def _reference_spans(path: Path) -> list[tuple[float, float]]:
    sample_rate, samples = _load_wav_mono_float(path)
    starts, rms, _, frame_samples, hop_samples = _frame_data(samples, sample_rate)
    floor = float(np.percentile(rms, 20))
    threshold = max(10 ** (-46.0 / 20.0), floor * 2.8, float(rms.max()) * 0.025)
    active = rms >= threshold
    active_runs = _runs(active, True)
    if not active_runs:
        return [(0.0, samples.size / sample_rate)]

    groups: list[list[int]] = []
    current: list[int] = []
    current_start = active_runs[0][0]
    previous_end = active_runs[0][0]
    for run_start, run_end in active_runs:
        gap_seconds = (run_start - previous_end) * hop_samples / sample_rate
        current_seconds = (run_end - current_start) * hop_samples / sample_rate
        if current and gap_seconds >= 0.20 and current_seconds >= 0.85:
            groups.append(current)
            current = []
            current_start = run_start
        current.extend((run_start, run_end))
        previous_end = run_end
    if current:
        groups.append(current)

    spans: list[tuple[float, float]] = []
    duration = samples.size / sample_rate
    for group in groups:
        start_frame = group[0]
        end_frame = group[-1]
        start = max(0.0, start_frame * hop_samples / sample_rate - 0.05)
        end = min(
            duration,
            (end_frame * hop_samples + frame_samples) / sample_rate + 0.05,
        )
        if end - start < 0.65:
            continue
        cursor = start
        while end - cursor > 6.0:
            spans.append((cursor, cursor + 4.0))
            cursor += 4.0
        if end - cursor >= 0.65:
            spans.append((cursor, end))
    if len(spans) < 5:
        window = min(4.0, duration)
        spans = []
        cursor = 0.0
        while cursor < duration and len(spans) < 20:
            end = min(duration, cursor + window)
            if end - cursor >= 0.65:
                spans.append((cursor, end))
            if end >= duration:
                break
            cursor += max(1.5, window * 0.75)
    return spans


def _features_from_interval(
    reference_path: Path,
    start_seconds: float,
    end_seconds: float,
    reference_pitch_hz: float,
) -> dict[str, Any]:
    sample_rate, samples = _load_wav_mono_float(reference_path)
    start = max(0, int(round(start_seconds * sample_rate)))
    end = min(samples.size, int(round(end_seconds * sample_rate)))
    if end <= start:
        raise AudioToolError("레퍼런스 분석 구간이 비어 있습니다.")
    # The feature extractor accepts paths so use an in-memory twin of its core by
    # temporarily writing a deterministic PCM WAV next to no user artifact.
    import tempfile
    import wave

    with tempfile.TemporaryDirectory(prefix="prosody-reference-") as temporary:
        interval_path = Path(temporary) / "interval.wav"
        interval = np.clip(samples[start:end], -1.0, 1.0)
        pcm = np.round(interval * 2_147_483_647.0).astype("<i4")
        with wave.open(str(interval_path), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(4)
            output.setframerate(sample_rate)
            output.writeframes(pcm.tobytes())
        features = extract_prosody_features(
            interval_path,
            reference_pitch_hz=reference_pitch_hz,
        )
    features["interval_start_seconds"] = _round(start_seconds)
    features["interval_end_seconds"] = _round(end_seconds)
    features.pop("path", None)
    features.pop("sha256", None)
    return features


def _robust_baseline(
    records: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any] | None:
    values = [
        float(record[metric])
        for record in records
        if isinstance(record.get(metric), (int, float))
        and math.isfinite(float(record[metric]))
    ]
    if len(values) < 3:
        return None
    array = np.asarray(values, dtype=np.float64)
    median = float(np.median(array))
    mad = float(np.median(np.abs(array - median)))
    scale = max(METRIC_MIN_SCALES[metric], mad * 1.4826)
    return {
        "count": len(values),
        "median": _round(median),
        "mad": _round(mad),
        "robust_scale": _round(scale),
        "p05": _round(float(np.percentile(array, 5))),
        "p95": _round(float(np.percentile(array, 95))),
    }


def _zscore(value: Any, baseline: dict[str, Any] | None) -> float | None:
    if not isinstance(value, (int, float)) or baseline is None:
        return None
    scale = float(baseline.get("robust_scale") or 0.0)
    if scale <= 0:
        return None
    return abs(float(value) - float(baseline["median"])) / scale


def _cosine_distance(left: Any, right: Any) -> float | None:
    if not isinstance(left, list) or not isinstance(right, list):
        return None
    if not left or len(left) != len(right):
        return None
    left_array = np.asarray(left, dtype=np.float64)
    right_array = np.asarray(right, dtype=np.float64)
    left_norm = float(np.linalg.norm(left_array))
    right_norm = float(np.linalg.norm(right_array))
    if left_norm <= 1e-9 or right_norm <= 1e-9:
        return None
    return float(
        1.0
        - np.dot(left_array, right_array) / (left_norm * right_norm)
    )


def _audio_judge_gate(
    report_path: Path | None,
    *,
    reference_sha256: str,
    preview_sha256: str,
    segment_texts: dict[int, str],
) -> dict[str, Any]:
    blocked = {
        "required": True,
        "required_runs": AUDIO_JUDGE_REQUIRED_RUNS,
        "status": "blocked_unavailable",
        "passed": False,
        "reason": (
            "실제 오디오를 입력받는 평가 도구의 3회 A/B 판정 증거가 없습니다. "
            "객관적 신호 분석을 실제 청취로 표현할 수 없습니다."
        ),
        "runs": [],
    }
    if report_path is None:
        return blocked
    report = load_json(report_path)
    if not isinstance(report, dict):
        raise WorkflowError("오디오 판정 보고서는 JSON 객체여야 합니다.")
    schema_version = report.get("schema_version")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version != SCHEMA_VERSION
    ):
        raise WorkflowError("오디오 판정 보고서 schema_version은 정수 1이어야 합니다.")
    if report.get("reference_sha256") != reference_sha256:
        raise WorkflowError("오디오 판정 보고서의 레퍼런스 해시가 현재 파일과 다릅니다.")
    if report.get("preview_sha256") != preview_sha256:
        raise WorkflowError("오디오 판정 보고서의 미리보기 해시가 현재 파일과 다릅니다.")
    evaluator_value = report.get("evaluator")
    if not isinstance(evaluator_value, str) or not evaluator_value.strip():
        raise WorkflowError("오디오 판정 evaluator는 비어 있지 않은 문자열이어야 합니다.")
    evaluator = evaluator_value.strip()
    runs = report.get("runs")
    if not isinstance(runs, list) or len(runs) != AUDIO_JUDGE_REQUIRED_RUNS:
        raise WorkflowError("오디오 판정은 서로 다른 설정으로 정확히 3회 필요합니다.")
    setting_ids: set[str] = set()
    required = set(segment_texts)
    normalized_runs: list[dict[str, Any]] = []
    required_checks = {
        "pronunciation_pass",
        "tone_pass",
        "intonation_pass",
        "emotion_pass",
        "speaker_character_pass",
        "boundary_continuity_pass",
        "no_synthesis_artifact_pass",
    }
    for expected_run, run in enumerate(runs, 1):
        if not isinstance(run, dict):
            raise WorkflowError("오디오 판정 실행 기록 형식이 올바르지 않습니다.")
        setting_id_value = run.get("settings_id")
        if not isinstance(setting_id_value, str):
            raise WorkflowError("오디오 판정 settings_id는 비어 있지 않은 문자열이어야 합니다.")
        setting_id = setting_id_value.strip()
        if not setting_id or setting_id in setting_ids:
            raise WorkflowError("오디오 판정 3회는 서로 다른 settings_id가 필요합니다.")
        setting_ids.add(setting_id)
        model_value = run.get("model")
        if not isinstance(model_value, str) or not model_value.strip():
            raise WorkflowError("오디오 판정 model은 비어 있지 않은 문자열이어야 합니다.")
        model = model_value.strip()
        segment_results = run.get("segments")
        if (
            not isinstance(segment_results, list)
            or len(segment_results) != len(required)
            or any(not isinstance(item, dict) for item in segment_results)
        ):
            raise WorkflowError("오디오 판정 실행에 문장별 결과가 없습니다.")
        indices = [item.get("index") for item in segment_results]
        if any(
            not isinstance(index, int) or isinstance(index, bool)
            for index in indices
        ):
            raise WorkflowError("오디오 판정의 문장 index는 정수여야 합니다.")
        seen = set(indices)
        if len(seen) != len(indices):
            raise WorkflowError("오디오 판정에 중복된 문장 index가 있습니다.")
        if seen != required:
            raise WorkflowError("오디오 판정 실행이 모든 현재 문장을 포함하지 않습니다.")
        run_passed = True
        for item in segment_results:
            if not isinstance(item, dict):
                run_passed = False
                continue
            if not required_checks.issubset(item):
                run_passed = False
                continue
            index = item["index"]
            spoken_text = item.get("spoken_text")
            if (
                not isinstance(spoken_text, str)
                or spoken_text != segment_texts[index]
            ):
                run_passed = False
                continue
            if not all(item.get(check) is True for check in required_checks):
                run_passed = False
        if not run_passed or run.get("all_passed") is not True:
            raise WorkflowError(
                f"오디오 판정 {expected_run}회차에서 하나 이상의 문장이 실패했습니다."
            )
        normalized_runs.append(
            {
                "run": expected_run,
                "settings_id": setting_id,
                "model": model,
                "all_passed": True,
                "segments": segment_results,
            }
        )
    return {
        "required": True,
        "required_runs": AUDIO_JUDGE_REQUIRED_RUNS,
        "status": "passed",
        "passed": True,
        "reason": None,
        "evaluator": evaluator,
        "runs": normalized_runs,
    }


def analyze_job(
    *,
    job_dir: Path,
    reference_wav: Path,
    audio_judge_report: Path | None = None,
) -> dict[str, Any]:
    job = load_json(job_dir / "job.json")
    plan = load_json(job_dir / "script_plan.json")
    segments = plan.get("segments")
    if not isinstance(segments, list) or not segments:
        raise WorkflowError("분석할 문장 계획이 없습니다.")
    preview_value = job.get("review_preview_wav")
    if not preview_value:
        raise WorkflowError("전체 WAV 미리보기가 아직 없습니다.")
    preview_path = job_dir / str(preview_value)
    if not preview_path.is_file():
        raise WorkflowError(f"전체 WAV 미리보기를 찾을 수 없습니다: {preview_path}")
    if not reference_wav.is_file():
        raise WorkflowError(f"레퍼런스 WAV를 찾을 수 없습니다: {reference_wav}")

    reference_overall = extract_prosody_features(reference_wav)
    reference_pitch = reference_overall.get("pitch_median_hz")
    if not isinstance(reference_pitch, (int, float)) or reference_pitch <= 0:
        raise WorkflowError("레퍼런스에서 신뢰할 수 있는 기준 피치를 추출하지 못했습니다.")
    reference_overall = extract_prosody_features(
        reference_wav,
        reference_pitch_hz=float(reference_pitch),
    )
    reference_chunks = [
        _features_from_interval(
            reference_wav,
            start,
            end,
            float(reference_pitch),
        )
        for start, end in _reference_spans(reference_wav)
    ]
    reference_chunks = [
        item
        for item in reference_chunks
        if int(item.get("pitch_voiced_frame_count") or 0) >= 8
        and float(item.get("active_speech_seconds") or 0.0) >= 0.35
    ]
    if len(reference_chunks) < 3:
        raise WorkflowError(
            "레퍼런스의 자연 변동 범위를 계산할 유효 발화 구간이 3개 미만입니다."
        )
    reference_baselines = {
        metric: baseline
        for metric in REFERENCE_METRICS
        if (baseline := _robust_baseline(reference_chunks, metric)) is not None
    }

    candidate_records: list[dict[str, Any]] = []
    for segment in segments:
        selected_wav = segment.get("selected_wav")
        if not selected_wav:
            raise WorkflowError(
                f"{segment.get('index')}번 문장에 선택된 WAV가 없습니다."
            )
        path = job_dir / str(selected_wav)
        if not path.is_file():
            raise WorkflowError(f"문장 WAV를 찾을 수 없습니다: {path}")
        features = extract_prosody_features(
            path,
            transcript=str(segment.get("spoken_text") or ""),
            reference_pitch_hz=float(reference_pitch),
        )
        candidate_records.append(
            {
                "index": int(segment["index"]),
                "spoken_text": str(segment.get("spoken_text") or ""),
                "directions": list(segment.get("directions") or []),
                "selected_attempt": segment.get("selected_attempt"),
                "selected_take": segment.get("selected_take"),
                "features": features,
            }
        )

    peer_records = [record["features"] for record in candidate_records]
    peer_baselines = {
        metric: baseline
        for metric in REFERENCE_METRICS
        if (baseline := _robust_baseline(peer_records, metric)) is not None
    }
    direction_groups: dict[str, list[dict[str, Any]]] = {}
    for record in candidate_records:
        key = ",".join(record["directions"]) or "untagged"
        direction_groups.setdefault(key, []).append(record["features"])
    direction_baselines: dict[str, dict[str, dict[str, Any]]] = {}
    for key, records in direction_groups.items():
        if len(records) < 3:
            continue
        direction_baselines[key] = {
            metric: baseline
            for metric in REFERENCE_METRICS
            if (baseline := _robust_baseline(records, metric)) is not None
        }

    reference_embedding = reference_overall.get("acoustic_embedding")
    reference_chunk_distances = [
        distance
        for item in reference_chunks
        if (
            distance := _cosine_distance(
                item.get("acoustic_embedding"),
                reference_embedding,
            )
        )
        is not None
    ]
    embedding_limit = (
        max(0.08, float(np.percentile(reference_chunk_distances, 95)) * 1.75)
        if reference_chunk_distances
        else None
    )
    reference_rate = load_json(job_dir / "reference_profile.json").get(
        "audio_metrics",
        {},
    ).get("syllables_per_active_second")

    family_metrics = {
        "pitch_center": ["pitch_center_semitones"],
        "pitch_shape": [
            "pitch_range_semitones",
            "pitch_contour_std_semitones",
            "pitch_slope_semitones",
            "pitch_end_delta_semitones",
        ],
        "energy": [
            "active_rms_dbfs",
            "energy_dynamic_db",
            "energy_slope_db",
        ],
        "rhythm": ["pause_ratio"],
        "timbre_proxy": ["spectral_centroid_hz", "zero_crossing_rate"],
    }
    flagged: set[int] = set()
    for record in candidate_records:
        features = record["features"]
        direction_key = ",".join(record["directions"]) or "untagged"
        local_baselines = direction_baselines.get(direction_key, peer_baselines)
        metric_scores: dict[str, Any] = {}
        for metric in REFERENCE_METRICS:
            reference_z = _zscore(features.get(metric), reference_baselines.get(metric))
            peer_z = _zscore(features.get(metric), local_baselines.get(metric))
            metric_scores[metric] = {
                "reference_robust_z": _round(reference_z),
                "peer_robust_z": _round(peer_z),
                "maximum_robust_z": _round(
                    max(
                        value
                        for value in (reference_z, peer_z)
                        if value is not None
                    )
                    if reference_z is not None or peer_z is not None
                    else None
                ),
            }
        family_scores: dict[str, float | None] = {}
        warning_families: list[str] = []
        critical_families: list[str] = []
        for family, metrics in family_metrics.items():
            values = [
                float(metric_scores[metric]["maximum_robust_z"])
                for metric in metrics
                if isinstance(metric_scores[metric]["maximum_robust_z"], (int, float))
            ]
            score = max(values) if values else None
            family_scores[family] = _round(score)
            if score is not None and score >= FAMILY_CRITICAL_Z:
                critical_families.append(family)
            elif score is not None and score >= FAMILY_WARNING_Z:
                warning_families.append(family)

        pitch_center = features.get("pitch_center_semitones")
        if isinstance(pitch_center, (int, float)) and abs(pitch_center) >= 4.5:
            if "pitch_center" not in critical_families:
                critical_families.append("pitch_center")
        rate_deviation = None
        if (
            isinstance(reference_rate, (int, float))
            and reference_rate > 0
            and isinstance(features.get("syllables_per_active_second"), (int, float))
        ):
            rate_deviation = abs(
                float(features["syllables_per_active_second"]) - float(reference_rate)
            ) / float(reference_rate)
            if rate_deviation > 0.10:
                critical_families.append("speaking_rate")
            elif rate_deviation > 0.075:
                warning_families.append("speaking_rate")
        embedding_distance = _cosine_distance(
            features.get("acoustic_embedding"),
            reference_embedding,
        )
        embedding_warning = (
            embedding_limit is not None
            and embedding_distance is not None
            and embedding_distance > embedding_limit
        )
        if embedding_warning:
            warning_families.append("acoustic_embedding_proxy")

        # A single very severe independent family, or two separate warning
        # families, is enough to request regeneration.  This avoids declaring a
        # failure from one noisy pitch estimate.
        unique_warnings = sorted(set(warning_families))
        unique_critical = sorted(set(critical_families))
        objective_pass = not unique_critical and len(unique_warnings) < 2
        if not objective_pass:
            flagged.add(record["index"])
        record["objective_qc"] = {
            "passed": objective_pass,
            "metric_scores": metric_scores,
            "family_scores": family_scores,
            "warning_families": unique_warnings,
            "critical_families": unique_critical,
            "speaking_rate_deviation_ratio": _round(rate_deviation),
            "acoustic_embedding_distance": _round(embedding_distance),
            "acoustic_embedding_reference_limit": _round(embedding_limit),
            "regeneration_reasons": [
                *[f"critical:{item}" for item in unique_critical],
                *[f"warning:{item}" for item in unique_warnings],
            ],
        }

    boundaries: list[dict[str, Any]] = []
    for left, right in zip(candidate_records, candidate_records[1:]):
        left_features = left["features"]
        right_features = right["features"]
        left_pitch = left_features.get("pitch_end_hz")
        right_pitch = right_features.get("pitch_start_hz")
        pitch_jump = None
        if (
            isinstance(left_pitch, (int, float))
            and left_pitch > 0
            and isinstance(right_pitch, (int, float))
            and right_pitch > 0
        ):
            pitch_jump = abs(12.0 * math.log2(float(right_pitch) / float(left_pitch)))
        left_energy = left_features.get("energy_end_dbfs")
        right_energy = right_features.get("energy_start_dbfs")
        energy_jump = (
            abs(float(right_energy) - float(left_energy))
            if isinstance(left_energy, (int, float))
            and isinstance(right_energy, (int, float))
            else None
        )
        pitch_failed = pitch_jump is not None and pitch_jump > 5.5
        energy_failed = energy_jump is not None and energy_jump > 6.5
        failed = pitch_failed or energy_failed
        if failed:
            flagged.add(right["index"])
        boundaries.append(
            {
                "from_segment": left["index"],
                "to_segment": right["index"],
                "pitch_jump_semitones": _round(pitch_jump),
                "energy_jump_db": _round(energy_jump),
                "checks": {
                    "pitch_transition_within_guardrail": not pitch_failed,
                    "energy_transition_within_guardrail": not energy_failed,
                },
                "passed": not failed,
                "attributed_regeneration_segment": right["index"] if failed else None,
            }
        )

    preview_sha256 = sha256_file(preview_path)
    audio_judge = _audio_judge_gate(
        audio_judge_report,
        reference_sha256=sha256_file(reference_wav),
        preview_sha256=preview_sha256,
        segment_texts={
            record["index"]: record["spoken_text"]
            for record in candidate_records
        },
    )
    objective_pass = not flagged
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "job_dir": str(job_dir.resolve()),
        "reference": {
            "path": str(reference_wav.resolve()),
            "sha256": sha256_file(reference_wav),
            "overall_features": reference_overall,
            "utterance_count": len(reference_chunks),
            "utterances": reference_chunks,
            "natural_variation_baselines": reference_baselines,
        },
        "preview": {
            "path": str(preview_path.resolve()),
            "sha256": preview_sha256,
            "review_revision": job.get("review_revision"),
        },
        "capabilities": {
            "objective_signal_analysis": True,
            "reference_calibrated_thresholds": True,
            "acoustic_embedding_proxy": True,
            "learned_speaker_embedding": False,
            "learned_emotion_style_embedding": False,
            "native_audio_listening_in_current_codex": False,
        },
        "threshold_policy": {
            "family_warning_robust_z": FAMILY_WARNING_Z,
            "family_critical_robust_z": FAMILY_CRITICAL_Z,
            "minimum_two_warning_families_to_fail": True,
            "pitch_boundary_guardrail_semitones": 5.5,
            "energy_boundary_guardrail_db": 6.5,
            "reference_calibration": "median_and_MAD_over_reference_utterances",
        },
        "peer_baselines": peer_baselines,
        "direction_peer_baselines": direction_baselines,
        "segments": candidate_records,
        "boundaries": boundaries,
        "objective_qc": {
            "passed": objective_pass,
            "flagged_segments": sorted(flagged),
            "status": "passed" if objective_pass else "regeneration_required",
        },
        "audio_listening_qc": audio_judge,
        "strict_qc": {
            "passed": objective_pass and bool(audio_judge.get("passed")),
            "final_approval_allowed": objective_pass
            and bool(audio_judge.get("passed")),
            "blocked_reason": (
                None
                if objective_pass and audio_judge.get("passed")
                else (
                    "객관적 운율 검사에서 재생성 대상이 있습니다."
                    if not objective_pass
                    else "실제 오디오 A/B 판정 3회 증거가 없습니다."
                )
            ),
        },
        "limitations": [
            "객관적 신호 분석은 실제 청취 또는 감정 이해와 동일하지 않다.",
            "acoustic_embedding은 모델 학습 화자 임베딩이 아니라 스펙트럼 프록시다.",
            "실제 오디오 판정 보고서가 없으면 strict_qc는 실패 폐쇄된다.",
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="레퍼런스 보정형 문장별 운율·경계 및 실제 오디오 판정 증거 검수"
    )
    parser.add_argument("--job-dir", type=Path, required=True)
    parser.add_argument("--reference-wav", type=Path, required=True)
    parser.add_argument("--audio-judge-report", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        job_dir = args.job_dir.expanduser().resolve()
        report = analyze_job(
            job_dir=job_dir,
            reference_wav=args.reference_wav.expanduser().resolve(),
            audio_judge_report=(
                args.audio_judge_report.expanduser().resolve()
                if args.audio_judge_report
                else None
            ),
        )
        destination = (
            args.output.expanduser().resolve()
            if args.output
            else job_dir / "review" / "prosody-listening-qc.json"
        )
        atomic_write_json(destination, report)
        print(
            json.dumps(
                {
                    "status": report["strict_qc"]["blocked_reason"]
                    and "blocked"
                    or "passed",
                    "objective_qc": report["objective_qc"],
                    "audio_listening_qc": {
                        "status": report["audio_listening_qc"]["status"],
                        "passed": report["audio_listening_qc"]["passed"],
                    },
                    "strict_qc": report["strict_qc"],
                    "report": str(destination),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if report["strict_qc"]["passed"] else 2
    except (WorkflowError, AudioToolError, ValueError) as exc:
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


if __name__ == "__main__":
    raise SystemExit(main())

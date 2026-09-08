#!/usr/bin/env python3
"""Deterministic audio conversion, measurement, and assembly helpers."""

from __future__ import annotations

import json
import hashlib
import math
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any, Mapping

import numpy as np


class AudioToolError(RuntimeError):
    """Raised when local audio processing cannot be completed."""


def _sanitized_media_environment(
    source: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Return the minimal non-secret environment for ffmpeg/ffprobe.

    The ElevenLabs API key is intentionally available to the Python workflow,
    but local media helpers never need it.  An allowlist also prevents proxy,
    credential, and unrelated application variables from reaching child
    processes.
    """

    values = source if source is not None else os.environ
    environment = {
        key: str(values[key])
        for key in ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR")
        if values.get(key)
    }
    environment.setdefault("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    environment.setdefault("LANG", "ko_KR.UTF-8")
    return environment


def require_binary(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise AudioToolError(f"필수 프로그램을 찾을 수 없습니다: {name}")
    try:
        binary = Path(resolved).resolve(strict=True)
        mode = binary.stat().st_mode
    except OSError as exc:
        raise AudioToolError(
            f"필수 프로그램 경로를 확인할 수 없습니다: {name}"
        ) from exc
    if (
        not binary.is_file()
        or not binary.is_absolute()
        or mode & 0o022
    ):
        raise AudioToolError(
            f"필수 프로그램 경로가 안전하지 않습니다: {name}"
        )
    return str(binary)


def run_command(command: list[str], *, capture: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        env=_sanitized_media_environment(),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise AudioToolError(
            f"오디오 명령이 실패했습니다 ({command[0]}): {detail[-1200:]}"
        )
    return result


def probe_media(path: Path) -> dict[str, Any]:
    ffprobe = require_binary("ffprobe")
    result = run_command(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration,size:stream=index,codec_type,codec_name,sample_rate,channels",
            "-of",
            "json",
            str(path),
        ]
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AudioToolError(f"미디어 정보를 해석하지 못했습니다: {path}") from exc


def convert_to_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int = 48_000,
    sample_format: str = "pcm_s24le",
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            sample_format,
            str(destination),
        ]
    )
    return destination


def convert_raw_pcm_to_wav(
    source: Path,
    destination: Path,
    *,
    sample_rate: int,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "s16le",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",
            "-i",
            str(source),
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s24le",
            str(destination),
        ]
    )
    return destination


def wav_to_mp3(source: Path, destination: Path, *, bitrate: str = "192k") -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = require_binary("ffmpeg")
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "libmp3lame",
            "-b:a",
            bitrate,
            str(destination),
        ]
    )
    return destination


def trim_edge_silence(source: Path, destination: Path) -> Path:
    """Trim only leading/trailing silence while preserving natural internal pauses."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = require_binary("ffmpeg")
    filter_value = (
        "silenceremove=start_periods=1:start_duration=0.08:start_threshold=-45dB,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.12:start_threshold=-45dB,"
        "areverse"
    )
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            filter_value,
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s24le",
            str(destination),
        ]
    )
    return destination


def extract_wav_interval(
    source: Path,
    destination: Path,
    *,
    start_seconds: float,
    end_seconds: float,
    silence_padding_seconds: float = 0.0,
) -> Path:
    """Extract an exact mono 48 kHz PCM interval for focused speech checks."""
    if start_seconds < 0 or end_seconds <= start_seconds:
        raise AudioToolError(
            f"유효하지 않은 오디오 구간입니다: {start_seconds:.3f}-{end_seconds:.3f}"
        )
    if end_seconds - start_seconds < 0.1:
        raise AudioToolError("집중 발음 검사용 오디오 구간이 0.1초 미만입니다.")
    if silence_padding_seconds < 0:
        raise AudioToolError("집중 발음 검사용 무음 패딩은 0초 이상이어야 합니다.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = require_binary("ffmpeg")
    filter_value = (
        f"atrim=start={start_seconds:.6f}:end={end_seconds:.6f},"
        "asetpts=PTS-STARTPTS"
    )
    if silence_padding_seconds > 0:
        delay_ms = round(silence_padding_seconds * 1000)
        filter_value += (
            f",adelay={delay_ms}:all=1,"
            f"apad=pad_dur={silence_padding_seconds:.6f}"
        )
    run_command(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(source),
            "-af",
            filter_value,
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s24le",
            str(destination),
        ]
    )
    return destination


def _load_wav_mono_float(path: Path) -> tuple[int, np.ndarray]:
    with wave.open(str(path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_width = wav_file.getsampwidth()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(frame_count)

    if sample_width == 2:
        data = np.frombuffer(frames, dtype="<i2").astype(np.float64) / 32768.0
    elif sample_width == 3:
        raw = np.frombuffer(frames, dtype=np.uint8).reshape(-1, 3)
        values = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        values = np.where(values & 0x800000, values - 0x1000000, values)
        data = values.astype(np.float64) / 8_388_608.0
    elif sample_width == 4:
        data = np.frombuffer(frames, dtype="<i4").astype(np.float64) / 2_147_483_648.0
    else:
        raise AudioToolError(f"지원하지 않는 WAV 비트 깊이입니다: {sample_width * 8}bit")

    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return sample_rate, data


def _runs(mask: np.ndarray, value: bool) -> list[tuple[int, int]]:
    if mask.size == 0:
        return []
    target = mask == value
    padded = np.concatenate(([False], target, [False]))
    transitions = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(start), int(end)) for start, end in transitions.reshape(-1, 2)]


def _estimate_pitch(
    samples: np.ndarray,
    sample_rate: int,
    active_mask: np.ndarray,
    hop_samples: int,
) -> dict[str, float | None]:
    window_size = int(sample_rate * 0.05)
    min_lag = max(1, int(sample_rate / 420.0))
    max_lag = min(window_size - 2, int(sample_rate / 65.0))
    active_indices = np.flatnonzero(active_mask)
    if active_indices.size == 0 or max_lag <= min_lag:
        return {
            "pitch_median_hz": None,
            "pitch_p10_hz": None,
            "pitch_p90_hz": None,
            "pitch_range_semitones": None,
        }

    sample_count = min(180, active_indices.size)
    selected = active_indices[np.linspace(0, active_indices.size - 1, sample_count).astype(int)]
    frequencies: list[float] = []
    window = np.hanning(window_size)
    for frame_index in selected:
        start = int(frame_index * hop_samples)
        frame = samples[start : start + window_size]
        if frame.size < window_size:
            continue
        frame = (frame - frame.mean()) * window
        energy = float(np.dot(frame, frame))
        if energy < 1e-7:
            continue
        autocorrelation = np.correlate(frame, frame, mode="full")[window_size - 1 :]
        segment = autocorrelation[min_lag : max_lag + 1]
        if segment.size == 0:
            continue
        lag = int(np.argmax(segment)) + min_lag
        confidence = float(autocorrelation[lag] / max(autocorrelation[0], 1e-12))
        if confidence >= 0.28:
            frequencies.append(sample_rate / lag)

    if not frequencies:
        return {
            "pitch_median_hz": None,
            "pitch_p10_hz": None,
            "pitch_p90_hz": None,
            "pitch_range_semitones": None,
        }
    values = np.asarray(frequencies, dtype=np.float64)
    p10 = float(np.percentile(values, 10))
    p90 = float(np.percentile(values, 90))
    semitones = float(12.0 * math.log2(max(p90, 1e-6) / max(p10, 1e-6)))
    return {
        "pitch_median_hz": round(float(np.median(values)), 3),
        "pitch_p10_hz": round(p10, 3),
        "pitch_p90_hz": round(p90, 3),
        "pitch_range_semitones": round(semitones, 3),
    }


def analyze_wav(path: Path, *, transcript: str = "") -> dict[str, Any]:
    sample_rate, samples = _load_wav_mono_float(path)
    if samples.size == 0:
        raise AudioToolError(f"빈 오디오 파일입니다: {path}")

    frame_samples = max(1, int(sample_rate * 0.025))
    hop_samples = max(1, int(sample_rate * 0.010))
    starts = np.arange(0, max(1, samples.size - frame_samples + 1), hop_samples)
    rms_values = np.empty(starts.size, dtype=np.float64)
    for index, start in enumerate(starts):
        frame = samples[start : start + frame_samples]
        rms_values[index] = math.sqrt(float(np.mean(np.square(frame))) + 1e-12)

    max_rms = float(np.max(rms_values))
    floor = float(np.percentile(rms_values, 20))
    threshold = max(10 ** (-46 / 20), floor * 2.8, max_rms * 0.025)
    active_mask = rms_values >= threshold
    total_duration = samples.size / sample_rate
    active_duration = float(active_mask.sum() * hop_samples / sample_rate)
    active_duration = min(active_duration, total_duration)

    active_indices = np.flatnonzero(active_mask)
    if active_indices.size:
        leading_silence = float(active_indices[0] * hop_samples / sample_rate)
        active_end = float(
            min(samples.size, active_indices[-1] * hop_samples + frame_samples) / sample_rate
        )
        trailing_silence = max(0.0, total_duration - active_end)
    else:
        leading_silence = total_duration
        trailing_silence = total_duration

    internal_pauses: list[float] = []
    for start, end in _runs(active_mask, False):
        if start == 0 or end == active_mask.size:
            continue
        duration = (end - start) * hop_samples / sample_rate
        if duration >= 0.12:
            internal_pauses.append(float(duration))

    absolute = np.abs(samples)
    overall_rms = math.sqrt(float(np.mean(np.square(samples))) + 1e-12)
    peak = float(np.max(absolute))
    clipping_ratio = float(np.mean(absolute >= 0.999))
    hangul_count = len([character for character in transcript if "가" <= character <= "힣"])
    syllables_per_active_second = (
        hangul_count / active_duration if active_duration > 0 and hangul_count else None
    )

    result: dict[str, Any] = {
        "sample_rate": sample_rate,
        "duration_seconds": round(total_duration, 4),
        "active_speech_seconds": round(active_duration, 4),
        "silence_ratio": round(1.0 - active_duration / max(total_duration, 1e-9), 4),
        "leading_silence_seconds": round(leading_silence, 4),
        "trailing_silence_seconds": round(trailing_silence, 4),
        "pause_count": len(internal_pauses),
        "mean_pause_seconds": (
            round(float(np.mean(internal_pauses)), 4) if internal_pauses else 0.0
        ),
        "p90_pause_seconds": (
            round(float(np.percentile(internal_pauses, 90)), 4) if internal_pauses else 0.0
        ),
        "rms_dbfs": round(20 * math.log10(max(overall_rms, 1e-12)), 3),
        "peak_dbfs": round(20 * math.log10(max(peak, 1e-12)), 3),
        "clipping_ratio": round(clipping_ratio, 7),
        "hangul_syllable_count": hangul_count,
        "syllables_per_active_second": (
            round(float(syllables_per_active_second), 4)
            if syllables_per_active_second is not None
            else None
        ),
    }
    result.update(_estimate_pitch(samples, sample_rate, active_mask, hop_samples))
    return result


def canonical_pcm_fingerprint(
    sources: list[Path],
    *,
    sample_rate: int = 48_000,
) -> dict[str, Any]:
    if not sources:
        raise AudioToolError("PCM 지문을 계산할 음성 구간이 없습니다.")
    ffmpeg = require_binary("ffmpeg")
    hasher = hashlib.sha256()
    frame_count = 0
    frame_bytes = 3
    for source in sources:
        if not source.is_file():
            raise AudioToolError(f"음성 구간 파일이 없습니다: {source}")
        result = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                str(sample_rate),
                "-c:a",
                "pcm_s24le",
                "-f",
                "s24le",
                "pipe:1",
            ],
            check=False,
            env=_sanitized_media_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise AudioToolError(
                f"PCM 정규화가 실패했습니다 ({source}): {detail[-1200:]}"
            )
        pcm = result.stdout
        if len(pcm) % frame_bytes:
            raise AudioToolError(
                f"PCM 프레임 경계가 올바르지 않습니다: {source}"
            )
        hasher.update(pcm)
        frame_count += len(pcm) // frame_bytes
    return {
        "channels": 1,
        "sample_width": 3,
        "sample_rate": sample_rate,
        "frame_count": frame_count,
        "pcm_sha256": hasher.hexdigest(),
        "source_count": len(sources),
    }


def concatenate_wavs(sources: list[Path], destination: Path) -> Path:
    if not sources:
        raise AudioToolError("결합할 음성 구간이 없습니다.")
    missing = [str(source) for source in sources if not source.is_file()]
    if missing:
        raise AudioToolError("음성 구간 파일이 없습니다: " + ", ".join(missing))
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=f".{destination.stem}-assemble-",
        dir=str(destination.parent),
    ) as temporary:
        temporary_dir = Path(temporary)
        normalized_paths: list[Path] = []
        for index, source in enumerate(sources, 1):
            normalized = temporary_dir / f"{index:04d}.wav"
            convert_to_wav(
                source,
                normalized,
                sample_rate=48_000,
                sample_format="pcm_s24le",
            )
            normalized_paths.append(normalized)

        assembled = temporary_dir / "assembled.wav"
        expected_hasher = hashlib.sha256()
        expected_frames = 0
        with wave.open(str(assembled), "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(3)
            output.setframerate(48_000)
            for normalized in normalized_paths:
                with wave.open(str(normalized), "rb") as source_wav:
                    if (
                        source_wav.getnchannels() != 1
                        or source_wav.getsampwidth() != 3
                        or source_wav.getframerate() != 48_000
                    ):
                        raise AudioToolError(
                            "정규화된 WAV 형식이 mono/48kHz/24-bit가 아닙니다: "
                            f"{normalized}"
                        )
                    declared_frames = source_wav.getnframes()
                    if declared_frames <= 0:
                        raise AudioToolError(
                            f"정규화된 WAV에 PCM 프레임이 없습니다: {normalized}"
                        )
                    read_frames = 0
                    while True:
                        frames = source_wav.readframes(65_536)
                        if not frames:
                            break
                        if len(frames) % 3:
                            raise AudioToolError(
                                f"정규화된 WAV 프레임 경계가 올바르지 않습니다: "
                                f"{normalized}"
                            )
                        expected_hasher.update(frames)
                        frame_count = len(frames) // 3
                        read_frames += frame_count
                        expected_frames += frame_count
                        output.writeframesraw(frames)
                    if read_frames != declared_frames:
                        raise AudioToolError(
                            "정규화된 WAV 헤더와 실제 PCM 프레임 수가 다릅니다: "
                            f"{normalized}"
                        )

        actual_hasher = hashlib.sha256()
        with wave.open(str(assembled), "rb") as assembled_wav:
            if (
                assembled_wav.getnchannels() != 1
                or assembled_wav.getsampwidth() != 3
                or assembled_wav.getframerate() != 48_000
                or assembled_wav.getnframes() != expected_frames
            ):
                raise AudioToolError(
                    "합본 WAV의 형식 또는 총 프레임 수가 예상과 다릅니다."
                )
            while True:
                frames = assembled_wav.readframes(65_536)
                if not frames:
                    break
                actual_hasher.update(frames)
        if actual_hasher.hexdigest() != expected_hasher.hexdigest():
            raise AudioToolError("합본 WAV의 PCM 내용이 선택 구간 순서와 다릅니다.")
        assembled.replace(destination)
    return destination

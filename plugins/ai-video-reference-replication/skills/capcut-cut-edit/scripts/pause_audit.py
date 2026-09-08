#!/usr/bin/env python3
"""Read-only full-audio pause inventory and fail-closed review gate.

Energy spans are navigation candidates, never permission to remove speech.
The caller must prove this WAV is the exact audio of the planned source ranges.
"""
from __future__ import annotations

import argparse
import array
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import wave


class PauseAuditError(ValueError):
    pass


def require(ok, code, detail=""):
    if not ok:
        raise PauseAuditError(f"{code}: {detail}")


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def policy():
    text = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
    blocks = re.findall(r"<!-- pause-audit-policy\s*(\{.*?\})\s*-->", text, re.S)
    require(len(blocks) == 1, "PAUSE_POLICY_MISSING")
    value = json.loads(blocks[0])
    require(0 < value["retained_pause_target_seconds"] < value["candidate_min_seconds"], "PAUSE_POLICY_INVALID")
    require(0 < value["analysis_window_seconds"] < value["candidate_min_seconds"], "PAUSE_POLICY_INVALID")
    require(value["detector_db"] and all(-90 < d < 0 for d in value["detector_db"]), "PAUSE_POLICY_INVALID")
    return value


def _audio(path):
    path = Path(path)
    require(path.is_absolute() and path.is_file(), "PAUSE_AUDIO_REQUIRED", str(path))
    with wave.open(str(path), "rb") as f:
        channels, width, rate, frames = f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()
        require(width == 2 and channels in (1, 2) and rate > 0, "PAUSE_PCM16_WAV_REQUIRED")
        raw = f.readframes(frames)
    require(frames > 0 and len(raw) == frames * channels * 2, "PAUSE_AUDIO_TRUNCATED")
    return raw, rate, channels, frames


def scan_pcm(raw, rate, channels=1, *, settings=None):
    """Scan every sample; stereo uses the louder channel to avoid phase cancellation."""
    p = settings or policy()
    require(rate > 0 and channels in (1, 2) and len(raw) % (2 * channels) == 0, "PAUSE_PCM_INVALID")
    values = array.array("h", raw)
    if sys.byteorder != "little":
        values.byteswap()
    frames = len(values) // channels
    hop = max(1, round(rate * p["analysis_window_seconds"]))
    peaks = [max(abs(min(v)), abs(max(v))) for i in range(0, len(values), hop * channels)
             if (v := values[i:i + hop * channels])]
    spans = []
    minimum = round(p["candidate_min_seconds"] * rate)
    for db in p["detector_db"]:
        limit, start = 32768 * 10 ** (db / 20), None
        for index in range(len(peaks) + 1):
            quiet = index < len(peaks) and peaks[index] <= limit
            if quiet and start is None:
                start = index * hop
            elif not quiet and start is not None:
                end = min(index * hop, frames)
                if end - start >= minimum:
                    spans.append((start, end, db))
                start = None
    merged = []
    for a, b, db in sorted(spans):
        if merged and a < merged[-1][1]:
            merged[-1][1] = max(b, merged[-1][1]); merged[-1][2].add(db)
        else:
            merged.append([a, b, {db}])
    return [{"start_us": a * 1_000_000 // rate, "end_us": b * 1_000_000 // rate,
             "duration_us": (b - a) * 1_000_000 // rate, "detector_db": sorted(dbs),
             "kind": "edge" if a == 0 or b == frames else "internal"}
            for a, b, dbs in merged]


def build_audit(audio, cut_sha256, fps, boundaries_us=()):
    require(re.fullmatch(r"[a-f0-9]{64}", str(cut_sha256)), "PAUSE_CUT_HASH_REQUIRED")
    require(type(fps) is int and 0 < fps <= 120, "PAUSE_FPS_REQUIRED")
    raw, rate, channels, frames = _audio(audio)
    p = policy(); duration = frames * 1_000_000 // rate
    boundaries = sorted(set(boundaries_us))
    require(all(type(b) is int and 0 <= b <= duration for b in boundaries), "PAUSE_BOUNDARIES_INVALID")
    rows = scan_pcm(raw, rate, channels, settings=p)
    for row in rows:
        row["id"] = "pause-" + digest(row)[:16]
        row["location"] = "across_cut" if any(row["start_us"] < b < row["end_us"] for b in boundaries) else "inside_cut"
    return {"schema": "capcut-full-pause-audit/v1", "audio": {"path": str(Path(audio).resolve()), "sha256": file_hash(audio)},
            "cut_sha256": cut_sha256, "fps": fps, "policy": p, "policy_sha256": digest(p),
            "coverage": {"start_us": 0, "end_us": duration, "samples": frames, "sample_rate": rate,
                         "channels": channels, "scope": "continuous_full_audio_including_clip_interiors_and_joins"},
            "boundaries_us": boundaries, "candidates": rows, "decisions": [],
            "full_audio_review": {"reviewed": False, "note": ""},
            "status": "pending_pause_review", "automatic_cutting": False}


def _evidence(ref):
    require(isinstance(ref, dict), "PAUSE_REVIEW_EVIDENCE_REQUIRED")
    p = Path(ref.get("path", ""))
    require(p.is_absolute() and p.is_file() and ref.get("sha256") == file_hash(p), "PAUSE_REVIEW_EVIDENCE_STALE")


def validate_audit(report, *, audio, cut_sha256, fps, boundaries_us=()):
    """Recompute inventory; old hashes, omitted rows and vague exceptions cannot pass."""
    require(isinstance(report, dict), "PAUSE_AUDIT_REQUIRED")
    expected = build_audit(audio, cut_sha256, fps, boundaries_us)
    for key in ("schema", "audio", "cut_sha256", "fps", "policy", "policy_sha256", "coverage", "boundaries_us", "candidates"):
        require(report.get(key) == expected[key], "PAUSE_AUDIT_STALE_OR_INCOMPLETE", key)
    review = report.get("full_audio_review", {})
    require(review.get("reviewed") is True and str(review.get("note", "")).strip(), "PAUSE_FULL_AUDIO_REVIEW_REQUIRED")
    # A noise floor / voiced breath can mask silence; energy count alone is not speech review.
    decisions = report.get("decisions")
    require(isinstance(decisions, list), "PAUSE_DECISIONS_REQUIRED")
    ids = [d.get("candidate_id") for d in decisions if isinstance(d, dict)]
    wanted = [c["id"] for c in expected["candidates"]]
    require(len(ids) == len(decisions) == len(set(ids)) and set(ids) == set(wanted), "PAUSE_DECISIONS_INCOMPLETE")
    for candidate, decision in ((c, next(d for d in decisions if d["candidate_id"] == c["id"])) for c in expected["candidates"]):
        require(decision.get("resolution") in ("speech_protection", "intentional_pause", "natural_short_pause"), "PAUSE_UNRESOLVED", candidate["id"])
        require(decision.get("audio_sha256") == expected["audio"]["sha256"], "PAUSE_DECISION_STALE")
        require(decision.get("start_us") == candidate["start_us"] and decision.get("end_us") == candidate["end_us"], "PAUSE_DECISION_RANGE")
        require(str(decision.get("reason", "")).strip() and str(decision.get("context_before", "")).strip()
                and str(decision.get("context_after", "")).strip(), "PAUSE_CONTEXT_REQUIRED")
        _evidence(decision.get("evidence"))
        require(decision.get("waveform_reviewed") is True, "PAUSE_WAVEFORM_REVIEW_REQUIRED")
        if decision["resolution"] == "intentional_pause":
            authority = decision.get("intent_evidence", {})
            require(authority.get("kind") in ("user_instruction", "approved_reference")
                    and str(authority.get("quote", "")).strip(), "PAUSE_INTENT_EVIDENCE_REQUIRED")
            _evidence(authority.get("source"))
        elif decision["resolution"] == "speech_protection":
            require(str(decision.get("protected_phoneme", "")).strip(), "PAUSE_PHONEME_REQUIRED")
        else:
            a, b = decision.get("previous_speech_end_us"), decision.get("next_speech_start_us")
            require(type(a) is int and type(b) is int and 0 <= a <= b <= expected["coverage"]["end_us"], "PAUSE_SPEECH_EDGES_REQUIRED")
            require(a <= candidate["end_us"] and b >= candidate["start_us"], "PAUSE_SPEECH_EDGES_REQUIRED")
            maximum = round(expected["policy"]["retained_pause_target_seconds"] * 1_000_000) + math.ceil(1_000_000 / fps)
            require(b - a <= maximum, "PAUSE_RETAINED_TOO_LONG", candidate["id"])
    return {"status": "pause_audit_pass", "audio_sha256": expected["audio"]["sha256"],
            "cut_sha256": cut_sha256, "candidate_count": len(wanted), "unresolved_count": 0,
            "review_basis": "measured_audio_and_recorded_context_review", "direct_listening_certified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("scan", "verify"))
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--cut-sha256", required=True)
    parser.add_argument("--fps", type=int, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--boundaries-us", nargs="*", type=int, default=[])
    args = parser.parse_args()
    try:
        if args.action == "scan":
            result = build_audit(args.audio, args.cut_sha256, args.fps, args.boundaries_us)
            args.report.parent.mkdir(parents=True, exist_ok=True)
            with args.report.open("x") as f:
                json.dump(result, f, ensure_ascii=False, indent=2); f.write("\n")
            print(json.dumps({"status": result["status"], "candidates": len(result["candidates"])}, ensure_ascii=False))
        else:
            result = validate_audit(json.loads(args.report.read_text()), audio=args.audio,
                                    cut_sha256=args.cut_sha256, fps=args.fps, boundaries_us=args.boundaries_us)
            print(json.dumps(result, ensure_ascii=False))
    except (PauseAuditError, OSError, ValueError, KeyError, TypeError, wave.Error) as exc:
        print(str(exc), file=sys.stderr); return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

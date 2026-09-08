"""Local source inspection and cut-only narration evidence, outside live projects."""
from __future__ import annotations

import array
import io
import math
import subprocess
import sys
import wave
from fractions import Fraction
from pathlib import Path

from semantic_contract import (PlanError, framing_geometry, cut_hash, descriptor, frame_us,
                               read_json, require, sha256, validate_voice, write_new_json)


# One shared gate for native dialogue, recorded voice and TTS, in this installed bundle.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "capcut-cut-edit/scripts"))
from pause_audit import PauseAuditError, build_audit, validate_audit, scan_pcm, policy as pause_policy


def outside_project(path):
    path = Path(path).expanduser().resolve()
    require("com.lveditor.draft" not in path.parts, "STAGE_OUTSIDE_PROJECT", str(path))
    for parent in (path, *path.parents):
        require(not ((parent / "Timelines/project.json").is_file()
                     or (parent / "draft_meta_info.json").is_file()), "STAGE_OUTSIDE_PROJECT", str(path))
    return path


def run(args, *, timeout=300):
    try:
        result = subprocess.run(args, capture_output=True, timeout=timeout, check=True)
        return result.stdout
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as exc:
        stderr = getattr(exc, "stderr", b"") or b""
        raise PlanError(f"MEDIA_COMMAND_FAILED: {args[0]}: {stderr.decode(errors='replace')[-1800:]}") from exc


def file_ref(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": sha256(path)}


def probe_asset(path, role):
    import json
    path = Path(path).expanduser().resolve()
    require(path.is_file(), "SOURCE_MISSING", str(path))
    require(role in ("clean", "voice"), "ASSET_ROLE")
    payload = json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))
    streams = payload.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    selected = video if role == "clean" else audio
    require(selected is not None, "MEDIA_STREAM_REQUIRED", role)
    duration = selected.get("duration") or payload.get("format", {}).get("duration")
    require(duration not in (None, "N/A") and float(duration) > 0, "MEDIA_DURATION")
    asset = {**file_ref(path), "role": role, "duration_us": int(float(duration) * 1_000_000), "has_audio": audio is not None}
    if video:
        rotation = int(round(float(video.get("tags", {}).get("rotate", 0)))) % 360
        for side in video.get("side_data_list", []):
            if "rotation" in side: rotation = int(round(float(side["rotation"]))) % 360
        w, h = int(video["width"]), int(video["height"])
        asset.update({"width": h if rotation % 180 else w, "height": w if rotation % 180 else h,
                      "encoded_width": w, "encoded_height": h, "rotation": rotation,
                      "fps": video.get("avg_frame_rate") or video.get("r_frame_rate")})
    return asset


def inventory(script, voice, clean_paths, product):
    require(bool(product.strip()), "PRODUCT_REQUIRED")
    script = Path(script).resolve()
    require(script.is_file(), "SOURCE_MISSING", str(script))
    paths = sorted({str(Path(p).expanduser().resolve()) for p in clean_paths})
    require(bool(paths), "CLEAN_FILES_REQUIRED")
    assets = {"voice": probe_asset(voice, "voice")}
    for i, path in enumerate(paths, 1):
        assets[f"clean-{i:03d}"] = {**probe_asset(path, "clean"), "product": product}
    return {"schema": "capcut-semantic-inventory/v1", "product": product,
            "script": file_ref(script), "assets": assets,
            "note": "Metadata only. Observe source intervals before assigning semantic actions."}


def _frame_bytes(asset, t, framing):
    x0, y0, x1, y1 = framing_geometry(asset, framing)["visible_crop"]
    vf = f"crop=iw*{x1-x0}:ih*{y1-y0}:iw*{x0}:ih*{y0},scale=270:480:flags=lanczos,setsar=1"
    return run(["ffmpeg", "-v", "error", "-ss", f"{t / 1_000_000:.6f}", "-i", asset["path"],
                "-frames:v", "1", "-vf", vf, "-c:v", "mjpeg", "-q:v", "2", "-f", "image2pipe", "pipe:1"])


def _sheet_bytes(frames):
    from PIL import Image, ImageDraw
    sheet = Image.new("RGB", (810, 508), "#171717")
    draw = ImageDraw.Draw(sheet)
    for i, frame in enumerate(frames):
        with Image.open(frame["path"]) as picture: sheet.paste(picture.convert("RGB"), (i * 270, 28))
        draw.text((i * 270 + 8, 7), f'{frame["time_us"] / 1_000_000:.3f}s', fill="white")
    buffer = io.BytesIO()
    sheet.save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def contact_sheet(asset, source_in_us, source_out_us, framing, output):
    from PIL import Image, ImageDraw
    descriptor(asset)
    require(0 <= source_in_us < source_out_us <= asset["duration_us"], "SOURCE_RANGE")
    require(set(framing) == {"scale", "center_x", "center_y"}, "FRAMING_FIELDS")
    require(1 <= framing["scale"] < 1.5, "ZOOM_LIMIT")
    require(0 <= framing["center_x"] <= 1 and 0 <= framing["center_y"] <= 1, "FRAMING_CENTER")
    output = outside_project(output)
    output.mkdir(parents=True, exist_ok=False)
    source_fps = Fraction(asset.get("fps") or "30")
    require(source_fps > 0, "SOURCE_FPS")
    tail = min((source_out_us - source_in_us) // 6, max(1, int(1_000_000 / source_fps)))
    times = [source_in_us, (source_in_us + source_out_us) // 2, source_out_us - tail]
    frames = []
    for i, t in enumerate(times):
        path = output / f"{i + 1}-{t}us.jpg"
        content = _frame_bytes(asset, t, framing)
        require(bool(content), "FRAME_EXTRACTION_EMPTY", str(t))
        with path.open("xb") as out: out.write(content)
        frames.append({"time_us": t, **file_ref(path)})
    sheet_path = output / "contact-sheet.jpg"
    with sheet_path.open("xb") as out: out.write(_sheet_bytes(frames))
    result = {"asset_sha256": asset["sha256"], "source_in_us": source_in_us, "source_out_us": source_out_us,
              "framing": dict(framing), "frames": frames, "contact_sheet": file_ref(sheet_path), "note": ""}
    write_new_json(output / "review.json", result)
    return result


def verify_visual_reviews(plan):
    import hashlib
    count = 0
    for clip in plan["clips"]:
        asset, review = plan["assets"][clip["asset_id"]], clip["review"]
        descriptor(asset)
        for frame in review["frames"]:
            descriptor(frame)
            expected = _frame_bytes(asset, frame["time_us"], clip["framing"])
            require(hashlib.sha256(expected).hexdigest() == frame["sha256"], "VISUAL_FRAME_MISMATCH", clip["id"])
            count += 1
        descriptor(review["contact_sheet"])
        require(hashlib.sha256(_sheet_bytes(review["frames"])).hexdigest() == review["contact_sheet"]["sha256"],
                "VISUAL_SHEET_MISMATCH", clip["id"])
    return {"verified_frames": count, "semantic_quality": "requires_agent_observation"}


def audio_pcm(plan):
    info = validate_voice(plan)
    source = plan["assets"][plan["voice"]["asset_id"]]["path"]
    cuts = plan["voice"]["cuts"]
    fps = info["fps"]
    n = len(cuts)
    filters = [f"[0:a:0]aresample=48000,asplit={n}" + "".join(f"[s{i}]" for i in range(n))]
    for i, row in enumerate(cuts):
        a = round(row["source_in_us"] * 48_000 / 1_000_000)
        count = round(row["end_frame"] * 48_000 / fps) - round(row["start_frame"] * 48_000 / fps)
        filters.append(f"[s{i}]atrim=start_sample={a}:end_sample={a + count},asetpts=PTS-STARTPTS[c{i}]")
    filters.append("".join(f"[c{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1[out]")
    pcm = run(["ffmpeg", "-v", "error", "-i", source, "-filter_complex", ";".join(filters),
               "-map", "[out]", "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"])
    expected = round(info["duration_frames"] * 48_000 / fps)
    require(len(pcm) == expected * 2, "AUDIO_DURATION", f"{len(pcm) // 2} != {expected}")
    return pcm


def waveform(pcm):
    values = array.array("h", pcm)
    if sys.byteorder != "little": values.byteswap()
    rows = []
    for offset in range(0, len(values), 480):
        chunk = values[offset:offset + 480]
        rms = math.sqrt(sum(v * v for v in chunk) / len(chunk)) / 32768
        rows.append({"time_us": offset * 1_000_000 // 48_000, "rms_db": round(20 * math.log10(max(rms, 1e-9)), 2)})
    return rows


def silence_candidates(pcm, kind):
    """Shared full-range candidates; recorded speech is never restricted to >=0.5 s."""
    require(kind in ("tts", "recorded"), "VOICE_KIND")
    candidates = []
    p = pause_policy()
    # Preserve the separate TTS edge behavior; internal discovery is shared.
    if kind == "tts":
        samples = array.array("h", pcm)
        if sys.byteorder != "little": samples.byteswap()
        limit = 32768 * 10 ** (-42 / 20)
        first, last = 0, len(samples)
        while first < last and abs(samples[first]) <= limit: first += 1
        while last > first and abs(samples[last - 1]) <= limit: last -= 1
        for a, b, x, y, label in [(0, first, 0, first - 960, "leading_silence"),
                                  (last, len(samples), last + 2400, len(samples), "trailing_silence")]:
            if b - a >= 1440 and x < y:
                candidates.append({"kind": label, "source_start_us": a * 1000000 // 48000,
                                   "source_end_us": b * 1000000 // 48000, "remove_start_us": x * 1000000 // 48000,
                                   "remove_end_us": y * 1000000 // 48000, "status": "candidate_requires_review"})
    half_keep = round(p["retained_pause_target_seconds"] * 1_000_000 / 2)
    for row in scan_pcm(pcm, 48000):
        if row["kind"] != "internal": continue
        a, b = row["start_us"], row["end_us"]
        candidates.append({"kind": "internal_pause", "source_start_us": a, "source_end_us": b,
                           "remove_start_us": a + half_keep, "remove_end_us": b - half_keep,
                           "status": "candidate_requires_review", "detector_db": row["detector_db"]})
    return sorted(candidates, key=lambda row: row["source_start_us"])


def analyze_voice(asset, kind, output):
    descriptor(asset)
    pcm = run(["ffmpeg", "-v", "error", "-i", asset["path"], "-map", "0:a:0", "-ar", "48000", "-ac", "1",
               "-c:a", "pcm_s16le", "-f", "s16le", "pipe:1"])
    output = outside_project(output)
    output.mkdir(parents=True, exist_ok=False)
    path = output / "source-voice-qc.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(48000); out.writeframes(pcm)
    result = {"source": asset, "kind": kind, "audio_qc": file_ref(path),
              "silence_candidates": silence_candidates(pcm, kind),
              "waveform": {"sample_rate": 48000, "step_us": 10000, "rows": waveform(pcm)},
              "status": "analysis_only_no_cuts_approved", "speech_recognition": "not_performed"}
    write_new_json(output / "voice-analysis.json", result)
    return result


def prepare_audio(plan, output):
    pcm = audio_pcm(plan)
    output = outside_project(output)
    output.mkdir(parents=True, exist_ok=False)
    path = output / "final-voice-qc.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(48_000); out.writeframes(pcm)
    evidence = {"audio": file_ref(path), "cut_sha256": cut_hash(plan), "review_note": "",
                "waveform": {"sample_rate": 48_000, "step_us": 10_000, "rows": waveform(pcm)},
                "pause_audit": build_audit(path, cut_hash(plan), plan["composition"]["fps"],
                                           [frame_us(c["start_frame"], plan["composition"]["fps"]) for c in plan["voice"]["cuts"]]),
                "note": "QC-only mono decode. Native timeline references original voice cuts, not this rendered file. Onsets require actual speech review."}
    write_new_json(output / "speech-evidence.json", evidence)
    return evidence


def verify_audio(plan):
    descriptor(plan["speech"]["audio"])
    require(plan["speech"]["cut_sha256"] == cut_hash(plan), "SPEECH_STALE")
    with wave.open(plan["speech"]["audio"]["path"], "rb") as source:
        require((source.getnchannels(), source.getsampwidth(), source.getframerate()) == (1, 2, 48_000), "AUDIO_QC_FORMAT")
        actual = source.readframes(source.getnframes())
    require(actual == audio_pcm(plan), "AUDIO_CUT_MISMATCH")
    try:
        pause_result = validate_audit(plan["speech"].get("pause_audit"), audio=plan["speech"]["audio"]["path"],
                                      cut_sha256=cut_hash(plan), fps=plan["composition"]["fps"],
                                      boundaries_us=[frame_us(c["start_frame"], plan["composition"]["fps"]) for c in plan["voice"]["cuts"]])
    except PauseAuditError as exc:
        raise PlanError(str(exc)) from exc
    return {"sample_count": len(actual) // 2, "sample_rate": 48_000, "status": "cut_audio_verified", "pause_audit": pause_result}

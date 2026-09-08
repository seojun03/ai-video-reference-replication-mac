"""Deterministic checks for an agent-reviewed semantic edit; no project writes."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import unicodedata
from pathlib import Path


class PlanError(ValueError):
    pass


def require(condition, code, detail=""):
    if not condition:
        raise PlanError(f"{code}: {detail}")


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def json_hash(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path):
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    require(isinstance(value, dict), "JSON_OBJECT_REQUIRED", str(path))
    return value


def write_new_json(path, value):
    """Never replace user files, including a dangling symlink."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_bytes(value) + b"\n")
        stream.flush()
        os.fsync(stream.fileno())


def integer(value, label, minimum=0):
    require(type(value) is int and value >= minimum, "INTEGER_REQUIRED", label)
    return value


def frame_us(frame, fps):
    return integer(frame, "frame") * 1_000_000 // integer(fps, "fps", 1)


def segment_duration(row, fps):
    return frame_us(row["end_frame"], fps) - frame_us(row["start_frame"], fps)


def descriptor(value, verify_files=True):
    require(isinstance(value, dict), "FILE_DESCRIPTOR")
    path = Path(value.get("path", ""))
    require(path.is_absolute(), "ABSOLUTE_PATH_REQUIRED", str(path))
    require(bool(re.fullmatch(r"[a-f0-9]{64}", str(value.get("sha256", "")))), "SHA256_REQUIRED", str(path))
    if verify_files:
        require(path.is_file(), "SOURCE_MISSING", str(path))
        require(sha256(path) == value["sha256"], "SOURCE_CHANGED", str(path))
    return path


def cut_hash(plan):
    return json_hash({"asset_sha256": plan["assets"][plan["voice"]["asset_id"]]["sha256"],
                      "fps": plan["composition"]["fps"], "cuts": plan["voice"]["cuts"]})


def normalized_words(text):
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[.．。]+(?=\s|$)", "", text)
    return re.sub(r"\s+", "", text)


def _ranges(rows, duration, code, *, start=0, end=None):
    cursor = start
    for row in rows:
        a, b = integer(row["start_frame"], code), integer(row["end_frame"], code, 1)
        require(a == cursor and a < b <= duration, code, str(row.get("id", "")))
        cursor = b
    require(cursor == (duration if end is None else end), code, "end")


def _unique(rows, code):
    ids = [r.get("id") for r in rows]
    require(all(isinstance(i, str) and i.strip() for i in ids) and len(ids) == len(set(ids)), code)
    return {r["id"]: r for r in rows}


def crop_box(asset, framing):
    """Largest 9:16 source window; pan it, but never shrink it to evade zoom."""
    w, h = asset["width"], asset["height"]
    cw, ch = min(1.0, h * 9 / (16 * w)), min(1.0, w * 16 / (9 * h))
    cx = min(1 - cw / 2, max(cw / 2, framing["center_x"]))
    cy = min(1 - ch / 2, max(ch / 2, framing["center_y"]))
    return [cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2]


def framing_geometry(asset, framing):
    base = crop_box(asset, framing)
    x0, y0, x1, y1 = base
    w, h, z = x1 - x0, y1 - y0, framing["scale"]
    vw, vh = w / z, h / z
    cx = min(x1 - vw / 2, max(x0 + vw / 2, framing["center_x"]))
    cy = min(y1 - vh / 2, max(y0 + vh / 2, framing["center_y"]))
    return {"base_crop": base, "visible_crop": [cx - vw / 2, cy - vh / 2, cx + vw / 2, cy + vh / 2],
            "transform_x": 2 * z * ((x0 + x1) / 2 - cx) / w,
            "transform_y": 2 * z * (cy - (y0 + y1) / 2) / h}


def validate_voice(plan, verify_files=True):
    comp, voice = plan["composition"], plan["voice"]
    fps, duration = integer(comp["fps"], "fps", 1), integer(comp["duration_frames"], "duration", 1)
    require(fps <= 120, "FPS_UNSUPPORTED")
    asset = plan["assets"][voice["asset_id"]]
    descriptor(asset, verify_files)
    require(asset["role"] == "voice" and asset["has_audio"] is True, "VOICE_ASSET")
    require(voice["kind"] in ("recorded", "tts"), "VOICE_KIND")
    require(bool(voice.get("review_note", "").strip()), "VOICE_REVIEW_REQUIRED")
    require(voice.get("speed", 1) == 1 and voice.get("pitch", 0) == 0, "VOICE_SPEED_PITCH")
    cuts = voice["cuts"]
    require(isinstance(cuts, list) and bool(cuts), "VOICE_CUTS")
    _ranges(cuts, duration, "VOICE_COVERAGE")
    previous_out = 0
    for row in cuts:
        source_in = integer(row["source_in_us"], "voice source")
        source_out = source_in + segment_duration(row, fps)
        require(source_in >= previous_out, "VOICE_SOURCE_ORDER")
        require(source_out <= asset["duration_us"], "VOICE_SOURCE_RANGE")
        previous_out = source_out
    return {"fps": fps, "duration_frames": duration, "cut_sha256": cut_hash(plan)}


def _validate(plan, verify_files):
    require(plan["schema"] == "capcut-semantic-plan/v1", "PLAN_SCHEMA")
    require(plan["category"] in ("food", "beauty", "supplement", "other"), "CATEGORY")
    require(isinstance(plan["product"], str) and bool(plan["product"].strip()), "PRODUCT_REQUIRED")
    require(plan["use_action"] in ("eating", "application", "product_use"), "USE_ACTION")
    if plan["category"] == "food": require(plan["use_action"] == "eating", "CATEGORY_ACTION")
    if plan["use_action"] == "product_use": require(plan["category"] == "other", "CATEGORY_ACTION")
    comp = plan["composition"]
    width, height = integer(comp["width"], "width", 1), integer(comp["height"], "height", 1)
    require(width * 16 == height * 9, "ASPECT_RATIO", "9:16 required")
    voice_info = validate_voice(plan, verify_files)
    fps, duration = voice_info["fps"], voice_info["duration_frames"]
    descriptor(plan["script"], verify_files)
    for name, asset in plan["assets"].items():
        descriptor(asset, verify_files)
        integer(asset["duration_us"], f"{name} duration", 1)
        require(asset["role"] in ("voice", "clean"), "ASSET_ROLE", name)
        if asset["role"] == "clean":
            require(asset["product"] == plan["product"], "PRODUCT_MISMATCH", name)
            integer(asset["width"], "source width", 1); integer(asset["height"], "source height", 1)
    speech = plan["speech"]
    descriptor(speech["audio"], verify_files)
    require(speech["cut_sha256"] == cut_hash(plan), "SPEECH_STALE")
    require(bool(speech.get("review_note", "").strip()), "SPEECH_REVIEW_REQUIRED")
    style = plan["caption_style"]
    require(set(style) == {"font"}, "CAPTION_STYLE_UNSUPPORTED", "only a local font with the common base style")
    font_path = descriptor(style["font"], verify_files)
    beats, caps, clips = plan["beats"], plan["captions"], plan["clips"]
    require(bool(beats) and bool(caps) and bool(clips), "EMPTY_EDIT")
    beat_map = _unique(beats, "BEAT_IDS")
    _unique(caps, "CAPTION_IDS"); _unique(clips, "CLIP_IDS")
    require(caps[0]["start_frame"] == 0, "LEADING_SPEECH_ALIGNMENT_REQUIRED",
            "this adapter requires the first spoken onset in frame 0; preserve intentional leading pauses and report this limit, never fabricate onset or trim them to pass")
    _ranges(beats, duration, "BEAT_CONTIGUITY")
    _ranges(caps, duration, "CAPTION_CONTIGUITY", start=caps[0]["start_frame"])
    cap_starts = {c["start_frame"] for c in caps}
    for c in caps:
        require(isinstance(c["text"], str) and bool(c["text"].strip()), "CAPTION_EMPTY")
        require(not c["text"].rstrip().endswith((".", "．", "。")), "CAPTION_PERIOD")
        require("\n" not in c["text"] and "\r" not in c["text"], "CAPTION_ONE_LINE")
        onset = integer(c["onset_us"], "onset")
        require(frame_us(c["start_frame"], fps) <= onset < frame_us(c["start_frame"] + 1, fps), "CAPTION_ONSET", c["id"])
        require(bool(c.get("onset_note", "").strip()), "CAPTION_ONSET_REVIEW", c["id"])
        require(c["beat_id"] in beat_map, "CAPTION_BEAT", c["id"])
        beat = beat_map[c["beat_id"]]
        require(beat["start_frame"] <= c["start_frame"] < c["end_frame"] <= beat["end_frame"], "BEAT_CAPTION_RANGE")
    require(normalized_words("".join(c["text"] for c in caps)) == normalized_words(plan["voice"]["transcript"]), "CAPTION_TRANSCRIPT")
    if verify_files:
        from PIL import ImageFont
        font = ImageFont.truetype(str(font_path), max(1, round(78 * width / 1080)))
        for c in caps:
            require(font.getlength(c["text"]) <= width * 0.84, "CAPTION_WIDTH", c["id"])
    for beat in beats:
        linked = [c for c in caps if c["beat_id"] == beat["id"]]
        require(linked and linked[0]["start_frame"] == beat["start_frame"], "BEAT_CAPTION_START")
        require(any(v["beat_id"] == beat["id"] and v["start_frame"] == beat["start_frame"] for v in clips), "BEAT_VIDEO_START")
        require(bool(beat.get("text", "").strip()) and bool(beat.get("intent", "").strip()), "BEAT_MEANING")
    gaps = plan.get("gaps", [])
    coverage = sorted(clips + gaps, key=lambda r: r["start_frame"])
    _ranges(coverage, duration, "VISUAL_COVERAGE")
    for gap in gaps:
        beat = beat_map.get(gap.get("beat_id"))
        require(beat and gap["end_frame"] == beat["end_frame"] and gap.get("reason"), "GAP_TAIL_ONLY")
        require(any(v["beat_id"] == beat["id"] and v["end_frame"] == gap["start_frame"] for v in clips), "GAP_TAIL_ONLY")
    intervals = []
    for clip in clips:
        asset = plan["assets"][clip["asset_id"]]
        require(asset["role"] == "clean", "CLEAN_ASSET")
        require(clip["volume"] == 0, "CLEAN_AUDIO_MUTED")
        require(clip["speed"] == 1, "SOURCE_SPEED")
        beat = beat_map.get(clip["beat_id"])
        require(beat and beat["start_frame"] <= clip["start_frame"] < clip["end_frame"] <= beat["end_frame"], "BEAT_VIDEO_RANGE")
        require(clip["start_frame"] in cap_starts, "VIDEO_CAPTION_START")
        source_in = integer(clip["source_in_us"], "source in")
        source_out = source_in + segment_duration(clip, fps)
        require(source_out <= asset["duration_us"], "SOURCE_RANGE", clip["id"])
        sel, framing, review = clip["selection"], clip["framing"], clip["review"]
        require(sel["mode"] in ("context", "fallback") and sel.get("reason") and sel.get("action"), "SELECTION_REASON")
        if sel["mode"] == "fallback": require(sel["action"] == plan["use_action"], "FALLBACK_ACTION")
        require(set(framing) == {"scale", "center_x", "center_y"}, "FRAMING_FIELDS")
        require(all(type(v) in (int, float) and math.isfinite(v) for v in framing.values()), "FRAMING_VALUES")
        require(1 <= framing["scale"] < 1.5, "ZOOM_LIMIT", "100% <= scale < 150%")
        require(0 <= framing["center_x"] <= 1 and 0 <= framing["center_y"] <= 1, "FRAMING_CENTER")
        require(review["asset_sha256"] == asset["sha256"] and review["source_in_us"] == source_in
                and review["source_out_us"] == source_out and review["framing"] == framing
                and bool(review.get("note", "").strip()), "VISUAL_REVIEW_STALE", clip["id"])
        frames = review["frames"]
        require(len(frames) == 3, "VISUAL_REVIEW_FRAMES")
        for i, f in enumerate(frames):
            descriptor(f, verify_files)
            t = integer(f["time_us"], "review frame")
            require(source_in <= t < source_out and i * (source_out - source_in) <= 3 * (t - source_in) < (i + 1) * (source_out - source_in), "VISUAL_REVIEW_FRAMES")
        intervals.append((clip, asset["sha256"], source_in, source_out))
    reuses = []
    ordered = sorted(intervals, key=lambda x: x[0]["start_frame"])
    for i, (left, asset_hash, a, b) in enumerate(ordered):
        for right, other_hash, c, d in ordered[i + 1:]:
            if asset_hash != other_hash or min(b, d) <= max(a, c):
                continue
            require(left["end_frame"] * 3 <= duration and right["start_frame"] * 3 >= duration * 2,
                    "REUSE_FRONT_BACK_ONLY", f'{left["id"]} -> {right["id"]}')
            reuses.append([left["id"], right["id"]])
    return {"status": "plan_validated", "duration_frames": duration, "duration_us": frame_us(duration, fps),
            "reuses": reuses, "declared_gaps": len(gaps), "plan_sha256": json_hash(plan),
            "visual_semantics": "agent_reviewed_not_machine_proven", "native_playback": "not_performed"}


def validate_plan(plan, verify_files=True):
    try:
        return _validate(plan, verify_files)
    except PlanError:
        raise
    except (KeyError, TypeError, IndexError, AttributeError, ZeroDivisionError) as exc:
        raise PlanError(f"PLAN_SHAPE: {exc}") from exc

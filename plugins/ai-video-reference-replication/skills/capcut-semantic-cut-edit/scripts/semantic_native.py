"""Target-bound, new-timeline-only CapCut adapter. Never calls a legacy writer."""
from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import unicodedata
import uuid
from contextlib import contextmanager
from pathlib import Path

from semantic_contract import (PlanError, canonical_bytes, framing_geometry, descriptor, frame_us,
                               json_hash, read_json, require, segment_duration, sha256,
                               validate_plan, write_new_json)
from semantic_media import file_ref, outside_project, probe_asset, verify_audio, verify_visual_reviews


def _name(value):
    require(isinstance(value, str) and bool(value.strip()) and len(value) <= 180
            and not re.search(r"[/\\\x00-\x1f]", value), "INVALID_NAME")
    return unicodedata.normalize("NFC", value)


def _uuid(value):
    require(isinstance(value, str), "INVALID_UUID")
    try: parsed = uuid.UUID(value)
    except ValueError as exc: raise PlanError(f"INVALID_UUID: {value}") from exc
    return str(parsed).upper()


def tree_hashes(root):
    root = Path(root)
    result = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "PROJECT_SYMLINK_UNSUPPORTED", str(path))
        if path.is_file():
            result[str(path.relative_to(root))] = sha256(path)
        elif not path.is_dir():
            raise PlanError(f"PROJECT_SPECIAL_FILE: {path}")
    return result


def capcut_running():
    try:
        output = subprocess.run(["/bin/ps", "-axo", "comm="], capture_output=True, text=True, check=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlanError("APP_STATE_UNAVAILABLE: cannot prove CapCut is closed") from exc
    return any(Path(line.strip()).name == "CapCut" or "CapCut.app/" in line for line in output.splitlines())


def assert_idle(project):
    require(not capcut_running(), "CAPCUT_RUNNING", "close CapCut normally; no live writes")
    locks = [p for p in Path(project).rglob("*") if p.name in (".locked", ".lock", "draft.lock") or p.suffix == ".lock"]
    require(not locks, "PROJECT_LOCKED", ", ".join(str(p) for p in locks[:3]))


def _check_media(plan):
    for name, asset in plan["assets"].items():
        actual = probe_asset(asset["path"], asset["role"])
        for field in ("sha256", "duration_us", "has_audio", "width", "height", "fps", "rotation"):
            if field in actual:
                require(actual[field] == asset.get(field), "MEDIA_METADATA_CHANGED", f"{name}.{field}")
    verify_audio(plan)
    verify_visual_reviews(plan)


def _project_inputs(project, project_name):
    raw_project = Path(project).expanduser()
    require(not raw_project.is_symlink(), "PROJECT_SYMLINK_UNSUPPORTED")
    project = raw_project.resolve()
    require(project.is_dir(), "EXISTING_PROJECT_REQUIRED", str(project))
    for path in (project / "Timelines", project / "draft_meta_info.json", project / "Timelines/project.json"):
        require(not path.is_symlink(), "PROJECT_SYMLINK_UNSUPPORTED", str(path))
    meta = read_json(project / "draft_meta_info.json")
    index = read_json(project / "Timelines/project.json")
    require(_name(project_name) == _name(project.name) == _name(meta["draft_name"]), "PROJECT_IDENTITY")
    _uuid(index["id"]); _uuid(meta["draft_id"])
    entries = index["timelines"]
    require(isinstance(entries, list), "PROJECT_TIMELINES")
    ids = [e["id"] for e in entries]
    require(len(ids) == len({_uuid(ident) for ident in ids}), "PROJECT_DUPLICATE_IDS")
    for entry in entries: _name(entry["name"])
    return project, meta, index


def _schema_source(project, index, source_id=None, source_name=None):
    """Choose a same-project format anchor, never a creative reference or media donor."""
    active = [entry for entry in index["timelines"] if not entry.get("is_marked_delete")]
    payloads = {}

    def payload_for(entry):
        if entry["id"] in payloads:
            return payloads[entry["id"]]
        directory = project / "Timelines" / entry["id"]
        path = directory / "draft_info.json"
        require(not directory.is_symlink() and not path.is_symlink(), "PROJECT_SYMLINK_UNSUPPORTED", str(path))
        payloads[entry["id"]] = None
        if not path.is_file():
            return None
        try:
            payload = read_json(path)
        except (OSError, ValueError):
            return None
        valid = (isinstance(payload, dict) and payload.get("id") == entry["id"]
                 and type(payload.get("version")) is int and payload["version"] > 0
                 and isinstance(payload.get("new_version"), str) and bool(payload["new_version"].strip())
                 and all(key not in payload or isinstance(payload[key], dict)
                         for key in ("platform", "last_modified_platform")))
        if valid:
            payloads[entry["id"]] = payload
        return payloads[entry["id"]]

    if source_id is not None or source_name is not None:
        requested_id = _uuid(source_id) if source_id is not None else None
        requested_name = _name(source_name) if source_name is not None else None
        chosen = [entry for entry in active
                  if (requested_id is None or _uuid(entry["id"]) == requested_id)
                  and (requested_name is None or _name(entry["name"]) == requested_name)]
        require(len(chosen) == 1, "SOURCE_IDENTITY", "explicit source must resolve uniquely")
        require(payload_for(chosen[0]) is not None, "SOURCE_SCHEMA_INVALID",
                "explicit source has no readable matching native format; do not substitute another timeline")
        reason = "explicit_source"
    else:
        main_id = index.get("main_timeline_id")
        chosen = [entry for entry in active if main_id and _uuid(entry["id"]) == _uuid(main_id)]
        chosen = [entry for entry in chosen if payload_for(entry) is not None]
        reason = "project_main_schema_only"
        if not chosen:
            chosen = [entry for entry in active if payload_for(entry) is not None]
            require(len(chosen) == 1, "PROJECT_SCHEMA_ANCHOR_UNAVAILABLE",
                    "no usable main timeline or unique same-project format anchor; inspect project structure, not a new editing reference")
            reason = "unique_project_schema_only"
    source = chosen[0]
    return source, payload_for(source), reason


def resolve_project(project, project_name, source_id=None, source_name=None):
    project, meta, index = _project_inputs(project, project_name)
    source, _, reason = _schema_source(project, index, source_id, source_name)
    return {"status": "project_schema_resolved", "project_path": str(project), "project_name": meta["draft_name"],
            "project_id": index["id"], "project_meta_id": meta["draft_id"],
            "source_id": source["id"], "source_name": source["name"], "source_selection": reason,
            "source_purpose": "native_schema_only_not_editing_reference"}


def _automatic_destination_name(product, entries):
    base = re.sub(r"[/\\\x00-\x1f]", "-", unicodedata.normalize("NFC", product)).strip()[:140]
    occupied = {_name(entry["name"]) for entry in entries}
    for number in range(1, len(entries) + 2):
        candidate = f"{base} 컷편집 v{number:03d}"
        if candidate not in occupied:
            return candidate
    raise PlanError("DESTINATION_EXISTS: could not derive an unused name")


def bind_project(plan_path, project, project_name, source_id=None, source_name=None, destination_name=None):
    plan_path = Path(plan_path).expanduser().resolve()
    plan = read_json(plan_path)
    validate_plan(plan)
    _check_media(plan)
    project, meta, index = _project_inputs(project, project_name)
    source, source_payload, reason = _schema_source(project, index, source_id, source_name)
    source_id, entries = source["id"], index["timelines"]
    if destination_name is None:
        destination_name = _automatic_destination_name(plan["product"], entries)
    _name(destination_name)
    require(not any(_name(e["name"]) == _name(destination_name) for e in entries), "DESTINATION_EXISTS", destination_name)
    destination_id = str(uuid.uuid4()).upper()
    require(not (project / "Timelines" / destination_id).exists(), "DESTINATION_EXISTS")
    protected = tree_hashes(project)
    require(protected["Timelines/project.json"] == sha256(project / "Timelines/project.json"), "PROJECT_CHANGED")
    return {"schema": "capcut-semantic-binding/v1", "project_path": str(project), "project_name": project_name,
            "project_id": index["id"], "project_meta_id": meta["draft_id"],
            "source_id": source_id, "source_name": source["name"], "source_selection": reason,
            "source_purpose": "native_schema_only_not_editing_reference",
            "destination_id": destination_id, "destination_name": destination_name,
            "created_us": time.time_ns() // 1000, "plan": file_ref(plan_path), "plan_sha256": json_hash(plan),
            "index_before": index, "protected": protected,
            "source_schema": {k: source_payload[k] for k in ("new_version", "version", "platform", "last_modified_platform") if k in source_payload}}


def _binding(binding):
    require(binding["schema"] == "capcut-semantic-binding/v1", "BINDING_SCHEMA")
    for key in ("source_id", "destination_id", "project_id", "project_meta_id"): _uuid(binding[key])
    require(_uuid(binding["source_id"]) != _uuid(binding["destination_id"]), "DESTINATION_EXISTS")
    _name(binding["project_name"]); _name(binding["source_name"]); _name(binding["destination_name"])
    project = Path(binding["project_path"])
    require(project.is_absolute() and project.is_dir() and not project.is_symlink(), "EXISTING_PROJECT_REQUIRED")
    require(str(project.resolve()) == str(project), "PROJECT_CANONICAL_PATH")
    meta = read_json(project / "draft_meta_info.json")
    require(meta["draft_id"] == binding["project_meta_id"] and _name(meta["draft_name"]) == _name(binding["project_name"])
            == _name(project.name), "PROJECT_IDENTITY")
    descriptor(binding["plan"])
    plan = read_json(binding["plan"]["path"])
    require(json_hash(plan) == binding["plan_sha256"], "PLAN_CHANGED")
    require(binding["index_before"]["id"] == binding["project_id"], "PROJECT_IDENTITY")
    require(not any(_uuid(e["id"]) == _uuid(binding["destination_id"]) or _name(e["name"]) == _name(binding["destination_name"])
                    for e in binding["index_before"]["timelines"]), "DESTINATION_EXISTS", "registered ID or name")
    current_index = read_json(project / "Timelines/project.json")
    require(current_index in (binding["index_before"], _new_index(binding)), "BINDING_INDEX",
            "bound registry must retain every actual existing entry")
    entry = [e for e in binding["index_before"]["timelines"] if e["id"] == binding["source_id"]]
    require(len(entry) == 1 and _name(entry[0]["name"]) == _name(binding["source_name"]), "SOURCE_IDENTITY")
    source_payload = read_json(project / "Timelines" / binding["source_id"] / "draft_info.json")
    require(source_payload["id"] == binding["source_id"], "SOURCE_IDENTITY")
    schema = {k: source_payload[k] for k in ("new_version", "version", "platform", "last_modified_platform") if k in source_payload}
    require(schema == binding["source_schema"], "SOURCE_SCHEMA_CHANGED")
    return project, plan


def _new_index(binding):
    result = copy.deepcopy(binding["index_before"])
    result["timelines"].append({"id": binding["destination_id"], "name": binding["destination_name"],
                                "is_marked_delete": False, "create_time": binding["created_us"], "update_time": binding["created_us"]})
    return result


def _fresh(binding, *, destination_allowed=False, registered=False):
    project, _ = _binding(binding)
    actual = tree_hashes(project)
    expected = dict(binding["protected"])
    if destination_allowed:
        prefix = f'Timelines/{binding["destination_id"]}/'
        actual = {k: v for k, v in actual.items() if not k.startswith(prefix)}
    if registered:
        require(read_json(project / "Timelines/project.json") == _new_index(binding), "REGISTRATION_MISMATCH")
        actual.pop("Timelines/project.json", None); expected.pop("Timelines/project.json", None)
    else:
        require(read_json(project / "Timelines/project.json") == binding["index_before"], "BINDING_INDEX")
    require(actual == expected, "PROJECT_CHANGED", "existing files or project registry changed; bind again")


def _media_name(ref):
    suffix = Path(ref["path"]).suffix.lower()
    require(bool(re.fullmatch(r"\.[a-z0-9]{1,10}", suffix)), "MEDIA_EXTENSION")
    return ref["sha256"] + suffix


def _media_refs(plan):
    used = {c["asset_id"] for c in plan["clips"]} | {plan["voice"]["asset_id"]}
    refs = {f'semantic_media/{_media_name(plan["assets"][ident])}': plan["assets"][ident] for ident in sorted(used)}
    font = plan["caption_style"]["font"]
    refs[f'semantic_media/{_media_name(font)}'] = font
    return refs


def _stable_ids(payload, destination_id):
    """Library object IDs are random; remap all IDs/references in stable traversal order."""
    mapping = {}
    pattern = re.compile(r"^(?:[0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})$")
    namespace = uuid.UUID(destination_id)
    def replace(value):
        if isinstance(value, dict): return {k: replace(value[k]) for k in sorted(value)}
        if isinstance(value, list): return [replace(v) for v in value]
        if isinstance(value, str) and pattern.fullmatch(value) and value != destination_id:
            if value not in mapping: mapping[value] = str(uuid.uuid5(namespace, str(len(mapping)))).upper()
            return mapping[value]
        return value
    return replace(payload)


def build_payload(plan, binding):
    import pycapcut as cc
    comp = plan["composition"]
    width, height, fps = comp["width"], comp["height"], comp["fps"]
    script = cc.ScriptFile(width, height, fps)
    script.add_track(cc.TrackType.video, "문맥별 클린본", absolute_index=0)
    script.add_track(cc.TrackType.audio, "사용자 음성 컷편집", absolute_index=1)
    script.add_track(cc.TrackType.text, "기본 한 줄 자막", absolute_index=2)
    destination = Path(binding["project_path"]) / "Timelines" / binding["destination_id"]
    def location(ref): return str(destination / "semantic_media" / _media_name(ref))
    for row in plan["clips"]:
        asset = plan["assets"][row["asset_id"]]
        geometry = framing_geometry(asset, row["framing"])
        x0, y0, x1, y1 = geometry["base_crop"]
        crop = cc.CropSettings(upper_left_x=x0, upper_left_y=y0, upper_right_x=x1, upper_right_y=y0,
                               lower_left_x=x0, lower_left_y=y1, lower_right_x=x1, lower_right_y=y1)
        material = cc.VideoMaterial(asset["path"], crop_settings=crop)
        material.path = location(asset)
        material.width, material.height, material.duration = asset["width"], asset["height"], asset["duration_us"]
        duration = segment_duration(row, fps)
        segment = cc.VideoSegment(material, cc.Timerange(frame_us(row["start_frame"], fps), duration),
                                  source_timerange=cc.Timerange(row["source_in_us"], duration), volume=0,
                                  clip_settings=cc.ClipSettings(scale_x=row["framing"]["scale"], scale_y=row["framing"]["scale"],
                                                               transform_x=geometry["transform_x"], transform_y=geometry["transform_y"]))
        script.add_segment(segment, "문맥별 클린본")
    voice = plan["assets"][plan["voice"]["asset_id"]]
    # The library rejects a narration MP4 at its constructor. The native audio
    # material itself supports extract_music pointing at the original container.
    # Use the probed local metadata without extracting/re-encoding that original.
    material = cc.AudioMaterial.__new__(cc.AudioMaterial)
    material.material_id = uuid.uuid4().hex
    material.path, material.material_name, material.duration = location(voice), Path(voice["path"]).name, voice["duration_us"]
    for row in plan["voice"]["cuts"]:
        duration = segment_duration(row, fps)
        segment = cc.AudioSegment(material, cc.Timerange(frame_us(row["start_frame"], fps), duration),
                                  source_timerange=cc.Timerange(row["source_in_us"], duration), volume=1)
        script.add_segment(segment, "사용자 음성 컷편집")
    for row in plan["captions"]:
        segment = cc.TextSegment(row["text"], cc.Timerange(frame_us(row["start_frame"], fps), segment_duration(row, fps)),
                                 style=cc.TextStyle(size=13, bold=False, color=(1, 1, 1), align=1, auto_wrapping=False, max_line_width=0.84),
                                 background=cc.TextBackground(color="#000000", style=1, alpha=1, round_radius=0),
                                 clip_settings=cc.ClipSettings(transform_x=0, transform_y=-800 / 1920))
        script.add_segment(segment, "기본 한 줄 자막")
    payload = json.loads(script.dumps())
    font_path = location(plan["caption_style"]["font"])
    for text in payload["materials"]["texts"]:
        content = json.loads(text["content"])
        for style in content["styles"]:
            style["font"] = {"id": "", "path": font_path}
            style["range"] = [0, len(content["text"].encode("utf-16-le")) // 2]
        text.update({"content": json.dumps(content, ensure_ascii=False, sort_keys=True), "font_path": font_path,
                     "font_name": Path(plan["caption_style"]["font"]["path"]).stem,
                     "font_resource_id": "", "font_size": 13, "line_feed": 0, "force_apply_line_max_width": False})
    payload.update({"id": binding["destination_id"], "name": binding["destination_name"],
                    "duration": frame_us(comp["duration_frames"], fps), "draft_type": "video",
                    "create_time": binding["created_us"], "update_time": binding["created_us"],
                    "mixed_track_mode_on": False})
    payload["canvas_config"] = {"width": width, "height": height, "ratio": "9:16", "background": None}
    payload["config"]["maintrack_adsorb"] = False
    schema = binding["source_schema"]
    for key in ("new_version", "version"):
        if key in schema: payload[key] = schema[key]
    for key in ("platform", "last_modified_platform"):
        source_platform = schema.get(key, schema.get("platform", {}))
        payload[key] = {k: source_platform.get(k, "") for k in ("os", "os_version", "app_id", "app_version", "app_source")}
        payload[key].update({"device_id": "", "hard_disk_id": "", "mac_address": ""})
    return _stable_ids(payload, binding["destination_id"])


def _copy_new(source, destination):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Path(source).open("rb") as src, destination.open("xb") as dst:
        shutil.copyfileobj(src, dst, 1024 * 1024)
        dst.flush(); os.fsync(dst.fileno())


def stage_timeline(plan_path, binding, output):
    output = outside_project(output)
    project, plan = _binding(binding)
    require(Path(plan_path).resolve() == Path(binding["plan"]["path"]), "PLAN_BINDING")
    _fresh(binding)
    validation = validate_plan(plan)
    _check_media(plan)
    payload = build_payload(plan, binding)
    output.mkdir(parents=True, exist_ok=False)
    timeline = output / "timeline"
    timeline.mkdir()
    for rel, ref in _media_refs(plan).items():
        descriptor(ref)
        _copy_new(ref["path"], timeline / rel)
        require(sha256(timeline / rel) == ref["sha256"], "STAGE_COPY_MISMATCH", rel)
    for name in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
        write_new_json(timeline / name, payload)
    write_new_json(output / "binding.json", binding)
    write_new_json(output / "plan.json", plan)
    stage_manifest = {"schema": "capcut-semantic-stage/v1", "binding_sha256": json_hash(binding),
                      "plan_sha256": json_hash(plan), "files": tree_hashes(timeline), "validation": validation,
                      "status": "staged_not_registered", "native_playback": "not_performed"}
    write_new_json(output / "stage.json", stage_manifest)
    _fresh(binding)
    return stage_manifest


def _load_stage(stage):
    stage = outside_project(stage)
    require(stage.is_dir() and not stage.is_symlink(), "STAGE_REQUIRED")
    binding, plan, manifest = (read_json(stage / name) for name in ("binding.json", "plan.json", "stage.json"))
    require(json_hash(binding) == manifest["binding_sha256"] and json_hash(plan) == manifest["plan_sha256"]
            == binding["plan_sha256"], "STAGE_TAMPERED", "manifest")
    _, current_plan = _binding(binding)
    require(current_plan == plan, "STAGE_TAMPERED", "plan")
    require(tree_hashes(stage / "timeline") == manifest["files"], "STAGE_TAMPERED", "files")
    validate_plan(plan)
    _check_media(plan)
    expected = build_payload(plan, binding)
    for name in ("draft_info.json", "draft_info.json.bak", "template-2.tmp"):
        require(read_json(stage / "timeline" / name) == expected, "STAGE_TAMPERED", name)
    expected_files = {"draft_info.json", "draft_info.json.bak", "template-2.tmp", *_media_refs(plan)}
    require(set(manifest["files"]) == expected_files, "STAGE_TAMPERED", "unexpected files")
    for rel, ref in _media_refs(plan).items():
        require(manifest["files"][rel] == ref["sha256"], "STAGE_TAMPERED", rel)
    return stage, binding, plan, manifest


@contextmanager
def _writer_lock(project):
    path = Path(tempfile.gettempdir()) / f"capcut-semantic-{json_hash(str(project))}.lock"
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), "WRITER_LOCK_INVALID")
        try: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc: raise PlanError("WRITER_BUSY") from exc
        yield
    finally:
        os.close(fd)


def install_timeline(stage):
    stage = outside_project(stage)
    early_binding = read_json(stage / "binding.json")
    project = Path(early_binding["project_path"])
    assert_idle(project)
    stage, binding, plan, manifest = _load_stage(stage)
    project, _ = _binding(binding)
    destination = project / "Timelines" / binding["destination_id"]
    with _writer_lock(project):
        assert_idle(project)
        require(not destination.exists() and not destination.is_symlink(), "DESTINATION_EXISTS", str(destination))
        _fresh(binding)
        registry = project / "Timelines/project.json"
        _copy_new(registry, stage / "project.json.before.json")
        require(sha256(stage / "project.json.before.json") == binding["protected"]["Timelines/project.json"], "PROJECT_CHANGED")
        assert_idle(project)
        _fresh(binding)
        destination.mkdir()  # exclusive: an existing directory is never merged/replaced
        try:
            for rel in manifest["files"]:
                assert_idle(project)
                _copy_new(stage / "timeline" / rel, destination / rel)
            require(tree_hashes(destination) == manifest["files"], "INSTALL_COPY_MISMATCH")
            assert_idle(project)
            _fresh(binding, destination_allowed=True)
            pending_index = destination / ".project-index.pending"
            write_new_json(pending_index, _new_index(binding))
            assert_idle(project)
            _fresh(binding, destination_allowed=True)
            require(sha256(registry) == binding["protected"]["Timelines/project.json"], "PROJECT_CHANGED")
            os.replace(pending_index, registry)
            directory_fd = os.open(str(registry.parent), os.O_RDONLY)
            try: os.fsync(directory_fd)
            finally: os.close(directory_fd)
        except Exception as exc:
            # Never roll back a user index or delete an in-flight native directory.
            # Before registration this directory is unregistered, and originals are untouched.
            raise PlanError(f"INSTALL_INTERRUPTED: inspect new directory {destination}; registry backup {stage / 'project.json.before.json'}; {exc}") from exc
        result = verify_install(stage)
        write_new_json(stage / "install-receipt.json", result)
        return result


def verify_install(stage):
    stage, binding, plan, manifest = _load_stage(stage)
    project, _ = _binding(binding)
    _fresh(binding, destination_allowed=True, registered=True)
    destination = project / "Timelines" / binding["destination_id"]
    require(tree_hashes(destination) == manifest["files"], "SAVED_TIMELINE_CHANGED")
    saved = read_json(destination / "draft_info.json")
    require(saved == build_payload(plan, binding), "SAVED_SEMANTICS_MISMATCH")
    for rel, ref in _media_refs(plan).items():
        require((destination / rel).is_file() and sha256(destination / rel) == ref["sha256"], "SAVED_MEDIA_MISMATCH")
    return {"schema": "capcut-semantic-install/v1", "status": "registered_pending_native_playback",
            "project_name": binding["project_name"], "project_path": str(project),
            "timeline_name": binding["destination_name"], "timeline_id": binding["destination_id"],
            "timeline_path": str(destination), "duration_frames": plan["composition"]["duration_frames"],
            "existing_files_preserved": len(binding["protected"]) - 1,
            "exactly_one_timeline_added": True, "main_timeline_preserved": True,
            "saved_draft_sha256": sha256(destination / "draft_info.json"),
            "declared_gaps": len(plan.get("gaps", [])), "native_playback": "not_performed", "export": "not_performed"}

from __future__ import annotations

import importlib.util
import json
import random
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + ".py"))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


store = module("product_knowledge_store")
pipeline = module("streaming_cut_pipeline")


def bundle(**extra):
    return {"company": "브랜드", "product": "제품", "job_id": "test-job", "items": [
        {"kind": "script", "text": "사용자 원문\n  띄어쓰기 유지", "source_type": "user_supplied", "status": "draft"},
        {"kind": "product_facts", "text": "특징: 정제\nUSP: 물에 녹여 사용", "source_type": "user_supplied"}
    ], **extra}


def test_read_only_lookup_creates_nothing_and_never_borrows_another_product(tmp_path):
    root = tmp_path / "library"
    missing = store.inspect(root, "브랜드", "다른제품", ["product_image"])
    assert not root.exists()
    assert missing["missing_roles"] == ["product_image"]
    store.capture(root, "브랜드", "제품", bundle())
    assert store.inspect(root, "브랜드", "다른제품")["records"] == []
    assert store.inspect(root, "다른업체", "제품")["records"] == []


def test_capture_reloads_exact_bytes_across_sessions_and_deduplicates(tmp_path):
    root = tmp_path / "library"
    first = store.capture(root, "브랜드", "제품", bundle())
    again = store.capture(root, unicodedata.normalize("NFD", "브랜드"), "제품", bundle())
    assert again["status"] == "unchanged"
    assert again["revision"] == first["revision"]
    snapshot = module("product_knowledge_store").inspect(root, "브랜드", "제품", ["script", "product_facts"])
    assert snapshot["missing_roles"] == []
    original = next(row for row in snapshot["records"] if row["kind"] == "script")
    assert Path(original["path"]).read_bytes() == bundle()["items"][0]["text"].encode()


def test_new_version_and_approval_are_distinct_and_existing_context_is_preserved(tmp_path):
    root = tmp_path / "library"
    folder = root / "브랜드/_knowledge/products/제품"
    folder.mkdir(parents=True)
    (folder / "product_context.md").write_text("기존 승인 정보는 보존\n")
    store.capture(root, "브랜드", "제품", bundle())
    changed = bundle(items=[{"kind": "script", "text": "새 확정본", "source_type": "user_supplied", "status": "approved", "approval_quote": "이걸로 확정"}])
    store.capture(root, "브랜드", "제품", changed)
    snapshot = store.inspect(root, "브랜드", "제품")
    assert len(snapshot["records"]) == 3
    assert (folder / "product_context.md").read_text().startswith("기존 승인 정보는 보존")
    assert sum(row["status"] == "approved" for row in snapshot["records"]) == 1
    del changed["items"][0]["approval_quote"]
    with pytest.raises(ValueError, match="approval_quote"):
        store.capture(root, "브랜드", "제품", changed)


def test_asset_copy_survives_source_loss_and_stored_damage_is_reported(tmp_path):
    root = tmp_path / "library"
    source = tmp_path / "source.png"
    source.write_bytes(b"fixture-original")
    value = bundle(items=[{"kind": "product_image", "path": str(source), "source_type": "official_page"}])
    store.capture(root, "브랜드", "제품", value)
    source.unlink()
    snapshot = store.inspect(root, "브랜드", "제품", ["product_image"])
    assert snapshot["missing_roles"] == []
    Path(snapshot["records"][0]["path"]).write_bytes(b"corrupt")
    snapshot = store.inspect(root, "브랜드", "제품", ["product_image"])
    assert snapshot["missing_roles"] == ["product_image"]
    assert snapshot["unavailable"][0]["reason"] == "hash_mismatch"


def test_url_conflict_is_not_silently_overwritten(tmp_path):
    root = tmp_path / "library"
    store.capture(root, "브랜드", "제품", bundle(detail_page_url="https://example.com/one"))
    with pytest.raises(ValueError, match="conflicting"):
        store.capture(root, "브랜드", "제품", bundle(detail_page_url="https://example.com/two"))
    assert store.inspect(root, "브랜드", "제품")["detail_page_url"].endswith("/one")
    store.capture(root, "브랜드", "제품", bundle(detail_page_url="https://example.com/two", latest_user_url=True))
    assert store.inspect(root, "브랜드", "제품")["detail_page_url"].endswith("/two")


def test_scope_mismatch_and_path_escape_do_not_create_storage(tmp_path):
    root = tmp_path / "library"
    with pytest.raises(ValueError, match="identity"):
        store.capture(root, "다른업체", "제품", bundle())
    with pytest.raises(Exception, match="path separators"):
        store.inspect(root, "../escape", "제품")
    assert not root.exists()


def make_run(tmp_path, count=3, capacity=3):
    plan = {"video_source_mode": "ai_generation", "image_generation_route": "built_in_image_gen", "output_ratio": "1:1", "cuts": []}
    for number in range(1, count + 1):
        plan["cuts"].append({"cut": number, "duration_seconds": 4, "motion_prompt": "손을 움직인다",
                             "product_presence": "forbidden", "cost": {"mode": "pro"},
                             "scene_design": {"setting": f"room-{number}", "subject_action": f"action-{number}", "shot_scale": "medium", "camera_angle": "side"}})
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(plan))
    state = tmp_path / "pipeline.json"
    pipeline.initialize(state, path, tmp_path / "ledger.json", capacity)
    return state, path


def make_image(tmp_path, number):
    rng = random.Random(number)
    image = Image.frombytes("RGB", (64, 64), bytes(rng.randrange(256) for _ in range(64 * 64 * 3)))
    path = tmp_path / f"image-{number}.png"
    image.save(path)
    return path


def review(image, selected=()):
    return {"image_sha256": pipeline.sha256(image), "provider": "openai", "route": "built_in_image_gen",
            "tool_result_path": str(image), "composition_pass": True, "action_ready": True,
            "scene_variety_pass": True, "compared_with_selected_cut_ids": list(selected)}


def test_first_video_can_start_while_other_images_are_missing(tmp_path):
    state, _ = make_run(tmp_path)
    image = make_image(tmp_path, 1)
    pipeline.accept_start(state, 1, image, review(image))
    assert pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"] == ["1"]
    claim = pipeline.claim_video(state, 1)
    assert claim["status"] == "claimed"
    assert claim["params"]["model"] == "kling3_0"
    assert json.loads(state.read_text())["cuts"]["2"]["image"] is None
    assert pipeline.claim_video(state, 1)["status"] == "existing"


def test_timeout_does_not_resubmit_and_other_ready_cut_can_run(tmp_path):
    state, _ = make_run(tmp_path)
    for n in (1, 2):
        image = make_image(tmp_path, n)
        pipeline.accept_start(state, n, image, review(image, range(1, n)))
    pipeline.claim_video(state, 1)
    pipeline.record_video(state, 1, "submitted_unknown")
    assert pipeline.claim_video(state, 1)["status"] == "existing"
    assert pipeline.claim_video(state, 2)["status"] == "claimed"
    assert len(json.loads((tmp_path / "ledger.json").read_text())["entries"]) == 2


def test_rolling_duplicate_and_stale_contact_review_are_blocked(tmp_path):
    state, _ = make_run(tmp_path)
    image = make_image(tmp_path, 1)
    pipeline.accept_start(state, 1, image, review(image))
    with pytest.raises(ValueError, match="every already selected"):
        pipeline.accept_start(state, 2, make_image(tmp_path, 2), review(make_image(tmp_path, 2)))
    copy = tmp_path / "same-bytes.png"
    copy.write_bytes(image.read_bytes())
    with pytest.raises(ValueError, match="duplicate"):
        pipeline.accept_start(state, 2, copy, review(copy, [1]))


def test_simultaneous_claims_only_grant_one_submission(tmp_path):
    state, _ = make_run(tmp_path)
    image = make_image(tmp_path, 1)
    pipeline.accept_start(state, 1, image, review(image))
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: pipeline.claim_video(state, 1), range(2)))
    assert sorted(result["status"] for result in results) == ["claimed", "existing"]


def test_video_capacity_model_and_changed_plan_guards(tmp_path):
    state, plan = make_run(tmp_path, capacity=1)
    for n in (1, 2):
        image = make_image(tmp_path, n)
        pipeline.accept_start(state, n, image, review(image, range(1, n)))
    pipeline.claim_video(state, 1)
    assert pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"] == []
    with pytest.raises(ValueError, match="kling3_0"):
        pipeline.record_video(state, 1, "submitted", "job-1", "seedance")
    pipeline.record_video(state, 1, "completed", "job-1", "kling3_0", True)
    assert pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"] == ["2"]
    plan.write_text(plan.read_text() + "\n")
    with pytest.raises(ValueError, match="hash changed"):
        pipeline.claim_video(state, 2)


def test_product_cut_requires_identity_review_and_existing_clean_is_disabled(tmp_path):
    state, plan = make_run(tmp_path)
    value = json.loads(plan.read_text())
    value["cuts"][0]["product_presence"] = "required"
    plan.write_text(json.dumps(value))
    fresh = tmp_path / "fresh.json"
    pipeline.initialize(fresh, plan, tmp_path / "fresh-ledger.json")
    image = make_image(tmp_path, 1)
    with pytest.raises(ValueError, match="QC incomplete"):
        pipeline.accept_start(fresh, 1, image, review(image))
    value["video_source_mode"] = "existing_clean_edit"
    plan.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="only for"):
        pipeline.initialize(tmp_path / "forbidden.json", plan, tmp_path / "unused.json")


def test_intake_enables_product_storage_without_tts_or_capcut():
    intake = module("production_intake").resolve({"scope": "visuals_only", "scope_response_text": "영상만", "output_ratio": "1:1"})
    assert intake["product_knowledge"]["enabled"] is True
    assert intake["product_knowledge"]["requires_capcut_engine"] is False
    assert intake["capcut"]["requested"] is False


def test_real_pilot_dependency_only_blocks_its_dependent_cut(tmp_path):
    _, plan = make_run(tmp_path)
    value = json.loads(plan.read_text())
    value["cuts"][1]["video_depends_on"] = [1]
    plan.write_text(json.dumps(value))
    state = tmp_path / "dependent.json"
    pipeline.initialize(state, plan, tmp_path / "dependent-ledger.json")
    for n in (1, 2, 3):
        image = make_image(tmp_path, n)
        pipeline.accept_start(state, n, image, review(image, range(1, n)))
    assert pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"] == ["1", "3"]
    pipeline.claim_video(state, 1)
    pipeline.record_video(state, 1, "completed", "pilot-1", "kling3_0", True)
    assert "2" in pipeline.ready(json.loads(state.read_text()))["ready_cut_ids"]


def test_crash_after_ledger_claim_recovers_without_another_submission(tmp_path):
    state, _ = make_run(tmp_path)
    image = make_image(tmp_path, 1)
    pipeline.accept_start(state, 1, image, review(image))
    claim = pipeline.claim_video(state, 1)
    payload = json.loads(state.read_text())
    payload["cuts"]["1"]["video"] = None  # Simulate lost state save, durable ledger survives.
    state.write_text(json.dumps(payload))
    recovered = pipeline.claim_video(state, 1)
    assert recovered["status"] == "existing"
    assert recovered["video"]["submission_key"] == claim["submission_key"]


def test_reencoded_same_scene_is_rejected(tmp_path):
    state, _ = make_run(tmp_path)
    image = make_image(tmp_path, 1)
    pipeline.accept_start(state, 1, image, review(image))
    reencoded = tmp_path / "same-scene.bmp"
    Image.open(image).save(reencoded)
    assert pipeline.sha256(image) != pipeline.sha256(reencoded)
    with pytest.raises(ValueError, match="near-duplicate"):
        pipeline.accept_start(state, 2, reencoded, review(reencoded, [1]))

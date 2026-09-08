from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_contract import PlanError, cut_hash, read_json, sha256, validate_plan, write_new_json
from semantic_media import contact_sheet, prepare_audio, probe_asset, verify_audio
from semantic_native import bind_project, install_timeline, resolve_project, stage_timeline, verify_install
from test_contract import fixture_plan

FONT = Path.home() / "Library/Fonts/Pretendard-SemiBold.otf"
SOURCE_ID = "11111111-1111-4111-8111-111111111111"
PROJECT_ID = "22222222-2222-4222-8222-222222222222"
META_ID = "33333333-3333-4333-8333-333333333333"


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = tempfile.TemporaryDirectory(prefix="semantic-capcut-media-")
        cls.media = Path(cls.shared.name).resolve()
        cls.video = cls.media / "same-product.mp4"
        cls.voice = cls.media / "voice.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", "color=c=blue:s=72x128:r=30:d=50",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(cls.video)], check=True)
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=30",
                        "-c:a", "pcm_s16le", str(cls.voice)], check=True)
        cls.base_plan = fixture_plan()
        cls.base_plan["assets"] = {
            "clean": {**probe_asset(cls.video, "clean"), "product": "테스트 견과"},
            "voice": probe_asset(cls.voice, "voice")}
        script = cls.media / "script.txt"
        script.write_text(cls.base_plan["voice"]["transcript"], encoding="utf-8")
        cls.base_plan["script"] = {"path": str(script), "sha256": sha256(script)}
        cls.base_plan["caption_style"]["font"] = {"path": str(FONT), "sha256": sha256(FONT)}
        for i, clip in enumerate(cls.base_plan["clips"]):
            clip["review"] = contact_sheet(cls.base_plan["assets"]["clean"], clip["source_in_us"],
                                           clip["source_in_us"] + 10_000_000, clip["framing"], cls.media / f"review-{i}")
            clip["review"]["note"] = "합성 파란 영상의 세 시점을 검사하는 기술 테스트; 실제 식품 판단 아님"
        cls.base_plan["speech"] = prepare_audio(cls.base_plan, cls.media / "audio-qc")
        cls.base_plan["speech"]["review_note"] = "합성 톤 기반의 타이밍 테스트; 실제 발화 청취 아님"

    @classmethod
    def tearDownClass(cls):
        cls.shared.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="semantic-capcut-project-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project = self.root / "가상 업체"
        source = self.project / "Timelines" / SOURCE_ID
        source.mkdir(parents=True)
        self.registry = self.project / "Timelines" / "project.json"
        self.original_index = {"id": PROJECT_ID, "main_timeline_id": SOURCE_ID,
                               "timelines": [{"id": SOURCE_ID, "name": "기존 원본", "is_marked_delete": False,
                                              "create_time": 1, "update_time": 1}]}
        write_new_json(self.registry, self.original_index)
        write_new_json(self.project / "draft_meta_info.json", {"draft_id": META_ID, "draft_name": "가상 업체"})
        write_new_json(source / "draft_info.json", {"id": SOURCE_ID, "tracks": [], "materials": {},
                                                   "new_version": "183.0.0", "version": 360000,
                                                   "platform": {"os": "mac", "app_version": "9.3.0", "app_id": 359289}})
        (source / "unchanged.bin").write_bytes(b"preserve me")
        write_new_json(self.project / "timeline_layout.json", {"dockItems": [{"timelineIds": [SOURCE_ID]}]})
        self.plan = copy.deepcopy(self.base_plan)
        self.plan_path = self.root / "plan.json"
        write_new_json(self.plan_path, self.plan)

    def bind(self):
        return bind_project(self.plan_path, self.project, "가상 업체", SOURCE_ID, "기존 원본", "문맥 컷편집 테스트")

    def stage(self):
        binding = self.bind()
        stage = self.root / "stage"
        stage_timeline(self.plan_path, binding, stage)
        return stage, binding

    def add_fixture_timeline(self, ident, name, deleted=False):
        source = self.project / "Timelines" / ident
        source.mkdir()
        write_new_json(source / "draft_info.json", {"id": ident, "tracks": [], "materials": {},
                                                   "new_version": "183.0.0", "version": 360000})
        index = read_json(self.registry)
        index["timelines"].append({"id": ident, "name": name, "is_marked_delete": deleted,
                                  "create_time": 999, "update_time": 999})
        self.registry.write_text(json.dumps(index), encoding="utf-8")

    def test_media_probe_review_and_cut_only_audio_are_real_files(self):
        self.assertEqual((self.plan["assets"]["clean"]["width"], self.plan["assets"]["clean"]["height"]), (72, 128))
        self.assertTrue(Path(self.plan["clips"][0]["review"]["contact_sheet"]["path"]).is_file())
        self.assertEqual(verify_audio(self.plan)["sample_count"], 1_440_000)
        self.assertEqual(validate_plan(self.plan)["duration_frames"], 900)

    def test_cli_inventory_and_draft_require_real_review_before_validation(self):
        cli = Path(__file__).resolve().parents[1] / "scripts/semantic_cut.py"
        inv = self.root / "inventory.json"
        process = subprocess.run([sys.executable, str(cli), "inventory", "--script", self.plan["script"]["path"],
                                  "--voice", str(self.voice), "--clean", str(self.video), "--product", "테스트 견과",
                                  "--output", str(inv)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(read_json(inv)["assets"]), 2)
        draft = self.root / "draft-plan.json"
        process = subprocess.run([sys.executable, str(cli), "init-plan", "--inventory", str(inv), "--category", "food",
                                  "--voice-kind", "recorded", "--use-action", "eating", "--output", str(draft)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(read_json(draft)["clips"], [])
        rejected = subprocess.run([sys.executable, str(cli), "validate", "--plan", str(draft)], capture_output=True, text=True)
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("VOICE_REVIEW_REQUIRED", rejected.stderr)

    def test_cli_bind_resolves_reference_and_names_new_timeline_without_questions(self):
        cli = Path(__file__).resolve().parents[1] / "scripts/semantic_cut.py"
        before = {str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}
        output = self.root / "automatic-binding.json"
        process = subprocess.run([sys.executable, str(cli), "bind", "--plan", str(self.plan_path),
                                  "--project", str(self.project), "--project-name", "가상 업체",
                                  "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        binding = read_json(output)
        self.assertEqual(binding["source_id"], SOURCE_ID)
        self.assertEqual(binding["source_selection"], "project_main_schema_only")
        self.assertEqual(binding["destination_name"], "테스트 견과 컷편집 v001")
        self.assertNotEqual(binding["destination_id"], SOURCE_ID)
        self.assertEqual({str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}, before)

    def test_cli_other_category_reaches_unreviewed_draft_without_touching_project(self):
        cli = Path(__file__).resolve().parents[1] / "scripts/semantic_cut.py"
        inv = self.root / "other-inventory.json"
        write_new_json(inv, {"schema": "capcut-semantic-inventory/v1", "product": self.plan["product"],
                             "script": self.plan["script"], "assets": self.plan["assets"]})
        draft = self.root / "other-plan.json"
        before = self.registry.read_bytes()
        process = subprocess.run([sys.executable, str(cli), "init-plan", "--inventory", str(inv),
                                  "--category", "other", "--voice-kind", "recorded", "--use-action", "product_use",
                                  "--output", str(draft)], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = read_json(draft)
        self.assertEqual((result["category"], result["use_action"]), ("other", "product_use"))
        self.assertEqual(result["clips"], [])
        with self.assertRaisesRegex(PlanError, "VOICE_REVIEW_REQUIRED"):
            validate_plan(result)
        self.assertEqual(self.registry.read_bytes(), before)

    def test_resolve_project_cli_requires_no_media_or_reference_selector(self):
        cli = Path(__file__).resolve().parents[1] / "scripts/semantic_cut.py"
        before = {str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}
        process = subprocess.run([sys.executable, str(cli), "resolve-project", "--project", str(self.project),
                                  "--project-name", "가상 업체"], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "project_schema_resolved")
        self.assertEqual(result["source_id"], SOURCE_ID)
        self.assertEqual(result["source_purpose"], "native_schema_only_not_editing_reference")
        self.assertEqual(result["project_path"], str(self.project))
        self.assertEqual({str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}, before)

    def test_named_or_identified_source_overrides_automatic_schema_anchor(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "사용자가 지정한 타임라인")
        for ident, name in ((None, "사용자가 지정한 타임라인"), (other_id, None)):
            with self.subTest(ident=ident, name=name):
                result = bind_project(self.plan_path, self.project, "가상 업체", ident, name, None)
                self.assertEqual(result["source_id"], other_id)
                self.assertEqual(result["source_selection"], "explicit_source")

    def test_automatic_source_is_project_main_not_latest_or_first_entry(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "더 최근 타임라인")
        index = read_json(self.registry); index["timelines"].reverse()
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        result = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        self.assertEqual(result["source_id"], SOURCE_ID)
        self.assertEqual(result["source_selection"], "project_main_schema_only")

    def test_missing_main_uses_only_unique_existing_schema_anchor(self):
        index = read_json(self.registry); index["main_timeline_id"] = "44444444-4444-4444-8444-444444444444"
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        result = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        self.assertEqual(result["source_id"], SOURCE_ID)
        self.assertEqual(result["source_selection"], "unique_project_schema_only")

    def test_missing_main_with_multiple_candidates_does_not_guess(self):
        self.add_fixture_timeline("44444444-4444-4444-8444-444444444444", "다른 기존 타임라인")
        index = read_json(self.registry); index["main_timeline_id"] = "55555555-5555-4555-8555-555555555555"
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "PROJECT_SCHEMA_ANCHOR_UNAVAILABLE"):
            bind_project(self.plan_path, self.project, "가상 업체", None, None, None)

    def test_unique_schema_fallback_excludes_payload_id_mismatch(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "ID가 일치하지 않는 타임라인")
        bad_path = self.project / "Timelines" / other_id / "draft_info.json"
        bad = read_json(bad_path); bad["id"] = "55555555-5555-4555-8555-555555555555"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        index = read_json(self.registry); index["main_timeline_id"] = "66666666-6666-4666-8666-666666666666"
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        result = resolve_project(self.project, "가상 업체")
        self.assertEqual(result["source_id"], SOURCE_ID)
        self.assertEqual(result["source_selection"], "unique_project_schema_only")

    def test_id_only_or_invalid_version_is_not_a_resolved_project_schema(self):
        source_path = self.project / "Timelines" / SOURCE_ID / "draft_info.json"
        cases = [{"id": SOURCE_ID},
                 {"id": SOURCE_ID, "version": True, "new_version": "183.0.0"},
                 {"id": SOURCE_ID, "version": 360000, "new_version": ""},
                 {"id": SOURCE_ID, "version": 360000, "new_version": "183.0.0", "platform": "not a mapping"}]
        for payload in cases:
            with self.subTest(payload=payload):
                source_path.write_text(json.dumps(payload), encoding="utf-8")
                with self.assertRaisesRegex(PlanError, "PROJECT_SCHEMA_ANCHOR_UNAVAILABLE"):
                    resolve_project(self.project, "가상 업체")

    def test_malformed_main_json_falls_back_only_to_unique_valid_schema(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "정상 저장 형식")
        source_path = self.project / "Timelines" / SOURCE_ID / "draft_info.json"
        source_path.write_text("{unfinished", encoding="utf-8")
        result = resolve_project(self.project, "가상 업체")
        self.assertEqual(result["source_id"], other_id)
        self.assertEqual(result["source_selection"], "unique_project_schema_only")
        self.assertEqual(source_path.read_text(encoding="utf-8"), "{unfinished")

    def test_explicit_invalid_schema_does_not_fall_back_to_valid_main(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "불완전한 지정 타임라인")
        path = self.project / "Timelines" / other_id / "draft_info.json"
        path.write_text(json.dumps({"id": other_id}), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "SOURCE_SCHEMA_INVALID"):
            resolve_project(self.project, "가상 업체", source_name="불완전한 지정 타임라인")

    def test_deleted_main_is_not_used_as_automatic_schema_anchor(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        self.add_fixture_timeline(other_id, "유일한 현재 타임라인")
        index = read_json(self.registry); index["timelines"][0]["is_marked_delete"] = True
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        result = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        self.assertEqual(result["source_id"], other_id)
        self.assertEqual(result["source_selection"], "unique_project_schema_only")

    def test_explicit_unknown_source_is_not_replaced_by_main(self):
        with self.assertRaisesRegex(PlanError, "SOURCE_IDENTITY"):
            bind_project(self.plan_path, self.project, "가상 업체", None, "없는 타임라인", None)

    def test_automatic_new_name_skips_registered_and_deleted_name_collisions(self):
        self.add_fixture_timeline("44444444-4444-4444-8444-444444444444", "테스트 견과 컷편집 v001")
        self.add_fixture_timeline("55555555-5555-4555-8555-555555555555", "테스트 견과 컷편집 v002", deleted=True)
        result = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        self.assertEqual(result["destination_name"], "테스트 견과 컷편집 v003")
        self.assertEqual(len(read_json(self.registry)["timelines"]), 3)

    def test_automatic_schema_anchor_never_copies_its_editing_or_product(self):
        source_path = self.project / "Timelines" / SOURCE_ID / "draft_info.json"
        source = read_json(source_path)
        source["tracks"] = [{"type": "video", "name": "UNRELATED_DONOR_STYLE", "segments": []}]
        source["materials"] = {"videos": [{"path": "/UNRELATED_DONOR_PRODUCT.mov"}]}
        source_path.write_text(json.dumps(source), encoding="utf-8")
        binding = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        stage = self.root / "automatic-stage"
        stage_timeline(self.plan_path, binding, stage)
        payload = read_json(stage / "timeline/draft_info.json")
        self.assertNotIn("UNRELATED_DONOR", json.dumps(payload))
        self.assertEqual([t["type"] for t in payload["tracks"]], ["video", "audio", "text"])
        self.assertEqual(read_json(source_path), source)

    def test_automatic_binding_does_not_bypass_running_app_guard(self):
        binding = bind_project(self.plan_path, self.project, "가상 업체", None, None, None)
        stage = self.root / "automatic-stage"
        stage_timeline(self.plan_path, binding, stage)
        with patch("semantic_native.capcut_running", return_value=True):
            with self.assertRaisesRegex(PlanError, "CAPCUT_RUNNING"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), self.original_index)
        self.assertFalse((self.project / "Timelines" / binding["destination_id"]).exists())

    def test_silence_candidates_preserve_padding_and_do_not_approve_cuts(self):
        from semantic_media import silence_candidates
        pcm = bytes(48000 * 2) + (b"\x10\x27" * 48000) + bytes(48000 * 2)
        rows = silence_candidates(pcm, "tts")
        self.assertEqual([(r["remove_start_us"], r["remove_end_us"]) for r in rows], [(0, 980000), (2050000, 3000000)])
        self.assertTrue(all(r["status"] == "candidate_requires_review" for r in rows))

    def test_recorded_pause_candidates_keep_short_breaths_and_review_padding(self):
        from semantic_media import silence_candidates
        speech = b"\x10\x27" * 48000
        # Recorded edges stay untouched; only the half-second internal gap qualifies.
        pcm = bytes(48000 * 2) + speech + bytes(23999 * 2) + speech + bytes(24000 * 2) + speech + bytes(48000 * 2)
        rows = silence_candidates(pcm, "recorded")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["kind"], "internal_pause")
        self.assertEqual(row["source_end_us"] - row["source_start_us"], 500000)
        self.assertEqual(row["remove_start_us"] - row["source_start_us"], 100000)
        self.assertEqual(row["source_end_us"] - row["remove_end_us"], 100000)
        self.assertEqual(row["status"], "candidate_requires_review")

    def test_tts_internal_pause_threshold_stays_separate_from_recorded(self):
        from semantic_media import silence_candidates
        speech = b"\x10\x27" * 48000
        pcm = speech + bytes(9600 * 2) + speech
        self.assertEqual(silence_candidates(pcm, "recorded"), [])
        row, = silence_candidates(pcm, "tts")
        self.assertEqual((row["remove_start_us"], row["remove_end_us"]), (1050000, 1150000))
        self.assertEqual(row["status"], "candidate_requires_review")

    def test_wrong_audio_bytes_cannot_pass_merely_by_updating_hash(self):
        fake = self.root / "fake.wav"
        shutil.copy2(self.voice, fake)
        data = bytearray(fake.read_bytes()); data[-100:] = bytes(100); fake.write_bytes(data)
        self.plan["speech"]["audio"] = {"path": str(fake), "sha256": sha256(fake)}
        with self.assertRaisesRegex(PlanError, "AUDIO_CUT_MISMATCH"):
            verify_audio(self.plan)

    def test_binding_rejects_wrong_project_or_source_name(self):
        with self.assertRaisesRegex(PlanError, "PROJECT_IDENTITY"):
            bind_project(self.plan_path, self.project, "다른 업체", SOURCE_ID, "기존 원본", "새 컷")
        with self.assertRaisesRegex(PlanError, "SOURCE_IDENTITY"):
            bind_project(self.plan_path, self.project, "가상 업체", SOURCE_ID, "다른 타임라인", "새 컷")

    def test_new_destination_does_not_overwrite_a_name_collision(self):
        with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
            bind_project(self.plan_path, self.project, "가상 업체", SOURCE_ID, "기존 원본", "기존 원본")

    def test_loading_binding_rechecks_destination_name_collision(self):
        binding = self.bind(); binding["destination_name"] = "기존 원본"
        with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
            stage_timeline(self.plan_path, binding, self.root / "collision-stage")

    def test_registered_id_without_directory_is_still_a_collision(self):
        other_id = "44444444-4444-4444-8444-444444444444"
        index = read_json(self.registry)
        index["timelines"].append({"id": other_id, "name": "등록된 기존 컷", "is_marked_delete": False})
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        binding = self.bind(); binding["destination_id"] = other_id
        with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
            stage_timeline(self.plan_path, binding, self.root / "id-collision-stage")
        self.assertEqual(read_json(self.registry), index)

    def test_uuid_case_cannot_evade_registered_destination_collision(self):
        other_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
        index = read_json(self.registry)
        index["timelines"].append({"id": other_id, "name": "기존 등록 컷", "is_marked_delete": True})
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        binding = self.bind(); binding["destination_id"] = other_id.lower()
        with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
            stage_timeline(self.plan_path, binding, self.root / "case-collision-stage")
        self.assertEqual(read_json(self.registry), index)

    def test_korean_source_name_normalization_is_consistent(self):
        import unicodedata
        binding = bind_project(self.plan_path, self.project, "가상 업체", SOURCE_ID,
                               unicodedata.normalize("NFD", "기존 원본"), "새 문맥 컷")
        self.assertEqual(stage_timeline(self.plan_path, binding, self.root / "normalized-stage")["status"], "staged_not_registered")

    def test_declared_tail_gap_disables_maintrack_magnet(self):
        row = self.plan["clips"][0]; row["end_frame"] = 290
        row["review"] = contact_sheet(self.plan["assets"]["clean"], 0, 9_666_666, row["framing"], self.root / "gap-review")
        row["review"]["note"] = "합성 영상의 짧은 선택 구간 검사"
        self.plan["gaps"] = [{"id": "gap0", "beat_id": "b0", "start_frame": 290, "end_frame": 300, "reason": "선택 가능한 원본 구간 부족"}]
        self.plan_path = self.root / "gap-plan.json"; write_new_json(self.plan_path, self.plan)
        stage, _ = self.stage()
        payload = read_json(stage / "timeline/draft_info.json")
        self.assertIs(payload["config"]["maintrack_adsorb"], False)
        self.assertEqual(payload["tracks"][0]["segments"][1]["target_timerange"]["start"], 10_000_000)

    def test_stage_is_deterministic_editable_and_does_not_touch_project(self):
        before = {str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}
        stage, binding = self.stage()
        native = read_json(stage / "timeline" / "draft_info.json")
        self.assertEqual([t["type"] for t in native["tracks"]], ["video", "audio", "text"])
        visual = native["tracks"][0]["segments"]
        self.assertEqual([s["volume"] for s in visual], [0, 0, 0])
        self.assertEqual([s["speed"] for s in visual], [1, 1, 1])
        self.assertEqual([s["target_timerange"]["start"] for s in visual], [0, 10_000_000, 20_000_000])
        self.assertEqual(native["canvas_config"]["ratio"], "9:16")
        self.assertEqual(native["id"], binding["destination_id"])
        self.assertEqual({str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}, before)

    def test_zoomed_portrait_can_pan_to_an_off_center_subject(self):
        from semantic_contract import framing_geometry
        geometry = framing_geometry(self.plan["assets"]["clean"], {"scale": 1.49, "center_x": 0.2, "center_y": 0.8})
        self.assertAlmostEqual(geometry["visible_crop"][0], 0)
        self.assertAlmostEqual(geometry["visible_crop"][3], 1)
        self.assertGreater(geometry["transform_x"], 0)
        self.assertGreater(geometry["transform_y"], 0)

    def test_rewritten_frame_hash_cannot_launder_unrelated_review_image(self):
        from PIL import Image
        wrong = self.root / "wrong.jpg"
        Image.new("RGB", (270, 480), "red").save(wrong)
        self.plan["clips"][0]["review"]["frames"][0].update({"path": str(wrong), "sha256": sha256(wrong)})
        wrong_plan = self.root / "wrong-plan.json"; write_new_json(wrong_plan, self.plan)
        with self.assertRaisesRegex(PlanError, "VISUAL_FRAME_MISMATCH"):
            bind_project(wrong_plan, self.project, "가상 업체", SOURCE_ID, "기존 원본", "새 컷")

    def test_staging_inside_any_live_project_is_rejected(self):
        with self.assertRaisesRegex(PlanError, "STAGE_OUTSIDE_PROJECT"):
            stage_timeline(self.plan_path, self.bind(), self.project / "stage")

    def test_process_or_native_lock_prevents_all_project_writes(self):
        stage, binding = self.stage()
        with patch("semantic_native.capcut_running", return_value=True):
            with self.assertRaisesRegex(PlanError, "CAPCUT_RUNNING"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), self.original_index)
        self.assertFalse((self.project / "Timelines" / binding["destination_id"]).exists())
        (self.project / ".locked").write_text("native lock")
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "PROJECT_LOCKED"):
                install_timeline(stage)

    def test_app_reopening_during_copy_never_commits_registry(self):
        stage, binding = self.stage()
        with patch("semantic_native.capcut_running", side_effect=[False, False, False, False, True]):
            with self.assertRaisesRegex(PlanError, "INSTALL_INTERRUPTED.*CAPCUT_RUNNING"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), self.original_index)
        self.assertTrue((self.project / "Timelines" / binding["destination_id"]).is_dir())

    def test_narration_mp4_keeps_original_file_as_editable_audio(self):
        mp4 = self.root / "provided-voice.mp4"
        subprocess.run(["ffmpeg", "-v", "error", "-n", "-i", str(self.video), "-i", str(self.voice),
                        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-shortest", str(mp4)], check=True)
        self.plan["assets"]["voice"] = probe_asset(mp4, "voice")
        self.plan["speech"] = prepare_audio(self.plan, self.root / "mp4-voice-review")
        self.plan["speech"]["review_note"] = "합성 MP4 음성 트랙 기술 검사"
        self.plan_path = self.root / "mp4-plan.json"; write_new_json(self.plan_path, self.plan)
        stage, _ = self.stage()
        material = read_json(stage / "timeline/draft_info.json")["materials"]["audios"][0]
        self.assertTrue(material["path"].endswith(".mp4"))
        copied = stage / "timeline/semantic_media" / Path(material["path"]).name
        self.assertEqual(sha256(copied), sha256(mp4))

    def test_real_font_width_rejects_an_overlong_caption(self):
        self.plan["captions"][0]["text"] = "가" * 30
        self.plan["voice"]["transcript"] = "가" * 30 + " 오븐에서 구워요 한 번 드셔보세요"
        with self.assertRaisesRegex(PlanError, "CAPTION_WIDTH"):
            validate_plan(self.plan)

    def test_stale_original_timeline_prevents_registration(self):
        stage, binding = self.stage()
        source_file = self.project / "Timelines" / SOURCE_ID / "unchanged.bin"
        source_file.write_bytes(b"user edit")
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "PROJECT_CHANGED"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), self.original_index)
        self.assertEqual(source_file.read_bytes(), b"user edit")

    def test_tampered_staged_caption_is_not_registered(self):
        stage, binding = self.stage()
        target = stage / "timeline" / "draft_info.json"
        payload = read_json(target); payload["tracks"][-1]["segments"].pop()
        target.write_text(json.dumps(payload), encoding="utf-8")
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "STAGE_TAMPERED"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), self.original_index)

    def test_rehashed_binding_cannot_drop_existing_registry_entries(self):
        from semantic_contract import json_hash
        other_id = "44444444-4444-4444-8444-444444444444"
        other = self.project / "Timelines" / other_id
        other.mkdir(); write_new_json(other / "draft_info.json", {"id": other_id})
        index = read_json(self.registry)
        index["timelines"].append({"id": other_id, "name": "다른 기존 타임라인", "is_marked_delete": False})
        self.registry.write_text(json.dumps(index), encoding="utf-8")
        stage, binding = self.stage()
        binding["index_before"]["timelines"].pop()
        (stage / "binding.json").write_text(json.dumps(binding), encoding="utf-8")
        manifest = read_json(stage / "stage.json"); manifest["binding_sha256"] = json_hash(binding)
        (stage / "stage.json").write_text(json.dumps(manifest), encoding="utf-8")
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "BINDING_INDEX"):
                install_timeline(stage)
        self.assertEqual(read_json(self.registry), index)

    def test_unused_inventory_files_are_not_copied_into_new_timeline(self):
        unused = self.root / "unused.mov"
        shutil.copy2(self.video, unused)
        self.plan["assets"]["unused"] = {**probe_asset(unused, "clean"), "product": "테스트 견과"}
        self.plan_path = self.root / "with-unused.json"; write_new_json(self.plan_path, self.plan)
        stage, _ = self.stage()
        self.assertFalse(any(p.suffix == ".mov" for p in (stage / "timeline/semantic_media").iterdir()))

    def test_existing_destination_directory_is_never_replaced(self):
        stage, binding = self.stage()
        dest = self.project / "Timelines" / binding["destination_id"]
        dest.mkdir(); (dest / "user.txt").write_text("keep")
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
                install_timeline(stage)
        self.assertEqual((dest / "user.txt").read_text(), "keep")

    def test_success_appends_exactly_one_preserves_old_files_and_reverse_verifies(self):
        before = {str(p.relative_to(self.project)): sha256(p) for p in self.project.rglob("*") if p.is_file()}
        stage, binding = self.stage()
        with patch("semantic_native.capcut_running", return_value=False):
            result = install_timeline(stage)
        after = read_json(self.registry)
        self.assertEqual(after["timelines"][:-1], self.original_index["timelines"])
        self.assertEqual(after["main_timeline_id"], SOURCE_ID)
        self.assertEqual(after["timelines"][-1]["id"], binding["destination_id"])
        self.assertEqual(result["status"], "registered_pending_native_playback")
        for rel, expected in before.items():
            if rel != "Timelines/project.json": self.assertEqual(sha256(self.project / rel), expected)
        self.assertEqual(verify_install(stage)["existing_files_preserved"], len(before) - 1)
        self.assertEqual(read_json(stage / "project.json.before.json"), self.original_index)
        with patch("semantic_native.capcut_running", return_value=False):
            with self.assertRaisesRegex(PlanError, "DESTINATION_EXISTS"):
                install_timeline(stage)

    def test_new_voice_segments_stay_editable_at_original_speed(self):
        self.plan["composition"]["duration_frames"] = 450
        for group in ("beats", "captions", "clips"):
            for row in self.plan[group]:
                row["start_frame"] //= 2; row["end_frame"] //= 2
                if group == "captions": row["onset_us"] //= 2
                if group == "clips":
                    row["review"] = contact_sheet(self.plan["assets"]["clean"], row["source_in_us"], row["source_in_us"] + 5_000_000,
                                                  row["framing"], self.root / (row["id"] + "-review"))
                    row["review"]["note"] = "합성 영상 기술 검사"
        self.plan["voice"]["cuts"] = [
            {"start_frame": 0, "end_frame": 150, "source_in_us": 0},
            {"start_frame": 150, "end_frame": 450, "source_in_us": 20_000_000}]
        self.plan["speech"] = prepare_audio(self.plan, self.root / "cut-audio")
        self.plan["speech"]["review_note"] = "합성 톤 기술 검사"
        self.plan_path = self.root / "recut-plan.json"; write_new_json(self.plan_path, self.plan)
        stage, _ = self.stage()
        native = read_json(stage / "timeline" / "draft_info.json")
        audio = next(t for t in native["tracks"] if t["type"] == "audio")["segments"]
        self.assertEqual(len(audio), 2)
        self.assertEqual([s["source_timerange"]["start"] for s in audio], [0, 20_000_000])
        self.assertEqual([s["speed"] for s in audio], [1, 1])
        self.assertEqual([s["target_timerange"]["start"] for s in audio], [0, 5_000_000])


if __name__ == "__main__":
    unittest.main()

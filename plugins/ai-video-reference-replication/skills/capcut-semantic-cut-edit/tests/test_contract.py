from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from semantic_contract import PlanError, frame_us, validate_plan


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def fixture_plan():
    asset = {"path": "/fixture/clean.mov", "sha256": "a" * 64,
             "duration_us": 50_000_000, "width": 1080, "height": 1920,
             "fps": "30/1", "has_audio": True, "role": "clean", "product": "테스트 견과"}
    voice = {"path": "/fixture/voice.wav", "sha256": "b" * 64,
             "duration_us": 30_000_000, "has_audio": True, "role": "voice"}
    cuts = [{"start_frame": 0, "end_frame": 900, "source_in_us": 0}]
    clips = []
    captions = []
    beats = []
    for i, (source, text, action) in enumerate([(0, "먹어보니 바삭해요", "eating"),
                                               (10_000_000, "오븐에서 구워요", "process"),
                                               (0, "한 번 드셔보세요", "eating")]):
        start, end = i * 300, (i + 1) * 300
        beats.append({"id": f"b{i}", "start_frame": start, "end_frame": end,
                      "text": text, "intent": action})
        captions.append({"id": f"c{i}", "beat_id": f"b{i}", "text": text,
                         "start_frame": start, "end_frame": end,
                         "onset_us": start * 1_000_000 // 30,
                         "onset_note": "최종 음성의 해당 첫소리를 파형과 함께 확인"})
        clips.append({"id": f"v{i}", "beat_id": f"b{i}", "asset_id": "clean",
                      "start_frame": start, "end_frame": end, "source_in_us": source,
                      "volume": 0, "speed": 1,
                      "selection": {"mode": "context", "action": action,
                                    "reason": "이 의미를 표현하는 실제 같은 제품 장면"},
                      "framing": {"scale": 1.0, "center_x": 0.5, "center_y": 0.5},
                      "review": {"asset_sha256": asset["sha256"],
                                 "source_in_us": source, "source_out_us": source + 10_000_000,
                                 "framing": {"scale": 1.0, "center_x": 0.5, "center_y": 0.5},
                                 "note": "시작·중간·끝에서 제품과 행동이 보임",
                                 "frames": [{"time_us": source + delta,
                                             "path": f"/fixture/v{i}-{j}.jpg", "sha256": "d" * 64}
                                            for j, delta in enumerate([0, 5_000_000, 9_966_666])]}})
    p = {"schema": "capcut-semantic-plan/v1", "category": "food", "product": "테스트 견과",
         "use_action": "eating",
         "composition": {"width": 1080, "height": 1920, "fps": 30, "duration_frames": 900},
         "script": {"path": "/fixture/script.txt", "sha256": "c" * 64},
         "assets": {"clean": asset, "voice": voice},
         "voice": {"asset_id": "voice", "kind": "recorded", "cuts": cuts,
                   "review_note": "의도적인 발화와 쉼을 보존", "transcript": "먹어보니 바삭해요 오븐에서 구워요 한 번 드셔보세요"},
         "speech": {"audio": {"path": "/fixture/final.wav", "sha256": "e" * 64},
                    "cut_sha256": digest({"asset_sha256": "b" * 64, "fps": 30, "cuts": cuts}),
                    "review_note": "최종 파일에서 문장별 첫 발화를 확인"},
         "caption_style": {"font": {"path": "/fixture/Pretendard-SemiBold.otf", "sha256": "f" * 64}},
         "beats": beats, "captions": captions, "clips": clips, "gaps": []}
    return p


class ContractTests(unittest.TestCase):
    def check(self, p):
        return validate_plan(p, verify_files=False)

    def reject(self, p, code):
        with self.assertRaisesRegex(PlanError, code):
            self.check(p)

    def test_front_then_back_source_interval_is_accepted(self):
        result = self.check(fixture_plan())
        self.assertEqual(result["duration_frames"], 900)
        self.assertEqual(result["reuses"], [["v0", "v2"]])

    def test_other_category_accepts_observed_product_use_fallback(self):
        p = fixture_plan()
        p["category"], p["use_action"] = "other", "product_use"
        p["clips"][1]["selection"] = {
            "mode": "fallback", "action": "product_use", "reason": "같은 제품의 실제 조작 장면으로 대체"}
        self.assertEqual(self.check(p)["duration_frames"], 900)

    def test_generic_action_does_not_weaken_named_category_rules(self):
        for category in ("food", "beauty", "supplement"):
            with self.subTest(category=category):
                p = fixture_plan()
                p["category"], p["use_action"] = category, "product_use"
                self.reject(p, "CATEGORY_ACTION")

    def test_other_category_still_rejects_an_unrelated_fallback_action(self):
        p = fixture_plan()
        p["category"], p["use_action"] = "other", "product_use"
        p["clips"][1]["selection"] = {"mode": "fallback", "action": "unrelated_stock", "reason": "임의 영상"}
        self.reject(p, "FALLBACK_ACTION")

    def test_floor_frame_conversion_avoids_rounding_up_at_30fps(self):
        self.assertEqual([frame_us(n, 30) for n in (1, 2, 3, 29)], [33333, 66666, 100000, 966666])

    def test_149_percent_allowed_but_150_rejected(self):
        p = fixture_plan()
        for value in (1.49, 1.5):
            p["clips"][0]["framing"]["scale"] = value
            p["clips"][0]["review"]["framing"]["scale"] = value
            if value < 1.5:
                self.check(p)
            else:
                self.reject(p, "ZOOM_LIMIT")

    def test_invalid_canvas_is_not_silently_reframed(self):
        p = fixture_plan(); p["composition"]["width"] = 1920
        self.reject(p, "ASPECT_RATIO")

    def test_disjoint_intervals_of_same_file_are_independent(self):
        p = fixture_plan()
        p["clips"][2]["source_in_us"] = 20_000_000
        p["clips"][2]["review"]["source_in_us"] = 20_000_000
        p["clips"][2]["review"]["source_out_us"] = 30_000_000
        for frame in p["clips"][2]["review"]["frames"]:
            frame["time_us"] += 20_000_000
        self.assertEqual(self.check(p)["reuses"], [])

    def test_middle_reuse_is_rejected_even_under_different_filename(self):
        p = fixture_plan()
        p["assets"]["alias"] = {**p["assets"]["clean"], "path": "/fixture/copied.mov"}
        p["clips"][1]["asset_id"] = "alias"
        p["clips"][1]["source_in_us"] = 1_000_000
        p["clips"][1]["review"]["source_in_us"] = 1_000_000
        p["clips"][1]["review"]["source_out_us"] = 11_000_000
        for frame in p["clips"][1]["review"]["frames"]:
            frame["time_us"] -= 9_000_000
        self.reject(p, "REUSE_FRONT_BACK_ONLY")

    def test_overlapping_source_subinterval_is_reuse_not_a_new_clip(self):
        p = fixture_plan()
        p["clips"][1]["source_in_us"] += 10_000_000
        p["clips"][1]["review"]["source_in_us"] += 10_000_000
        p["clips"][1]["review"]["source_out_us"] += 10_000_000
        for f in p["clips"][1]["review"]["frames"]: f["time_us"] += 10_000_000
        p["clips"][2]["source_in_us"] = 1_000_000
        p["clips"][2]["review"]["source_in_us"] += 1_000_000
        p["clips"][2]["review"]["source_out_us"] += 1_000_000
        for f in p["clips"][2]["review"]["frames"]: f["time_us"] += 1_000_000
        self.assertEqual(self.check(p)["reuses"], [["v0", "v2"]])

    def test_third_use_cannot_be_hidden_as_three_clips(self):
        p = fixture_plan()
        p["clips"][1]["source_in_us"] = 0
        p["clips"][1]["review"] = copy.deepcopy(p["clips"][0]["review"])
        self.reject(p, "REUSE_FRONT_BACK_ONLY")

    def test_no_source_audio_or_speed_change(self):
        for key, value, code in [("volume", 1, "CLEAN_AUDIO_MUTED"), ("speed", 1.1, "SOURCE_SPEED")]:
            p = fixture_plan(); p["clips"][0][key] = value
            self.reject(p, code)

    def test_caption_gap_overlap_or_onset_drift_is_rejected(self):
        for key, value, code in [("end_frame", 299, "CAPTION_CONTIGUITY"),
                                 ("end_frame", 301, "CAPTION_CONTIGUITY"),
                                 ("onset_us", 40_000, "CAPTION_ONSET")]:
            p = fixture_plan(); p["captions"][0][key] = value
            self.reject(p, code)

    def test_floor_encoded_frame_start_is_accepted_as_that_frame(self):
        p = fixture_plan()
        p["captions"][0]["text"] = "먹어보니"
        p["captions"][0]["end_frame"] = 1
        p["captions"].insert(1, {"id": "c0b", "beat_id": "b0", "text": "바삭해요", "start_frame": 1,
                                 "end_frame": 300, "onset_us": 33333, "onset_note": "native frame 1"})
        self.check(p)

    def test_preserved_leading_pause_is_reported_not_silently_deleted(self):
        p = fixture_plan()
        p["captions"][0]["start_frame"] = 12
        p["captions"][0]["onset_us"] = 400000
        before = copy.deepcopy(p["voice"])
        self.reject(p, "LEADING_SPEECH_ALIGNMENT_REQUIRED")
        self.assertEqual(p["voice"], before)

    def test_new_meaning_cut_and_caption_must_share_start(self):
        p = fixture_plan(); p["beats"][1]["start_frame"] = 301
        self.reject(p, "BEAT_")

    def test_caption_text_cannot_invent_words_or_end_with_period(self):
        for text, code in [("먹으면 최고예요", "CAPTION_TRANSCRIPT"), ("먹어보니 바삭해요.", "CAPTION_PERIOD")]:
            p = fixture_plan(); p["captions"][0]["text"] = text
            self.reject(p, code)

    def test_decimal_point_is_not_discarded_when_comparing_transcript(self):
        p = fixture_plan()
        p["voice"]["transcript"] = "1.5g만 넣었어요 오븐에서 구워요 한 번 드셔보세요"
        p["captions"][0]["text"] = "15g만 넣었어요"
        self.reject(p, "CAPTION_TRANSCRIPT")

    def test_sentence_final_periods_do_not_require_periods_in_captions(self):
        p = fixture_plan()
        p["voice"]["transcript"] = "먹어보니 바삭해요. 오븐에서 구워요. 한 번 드셔보세요."
        self.check(p)

    def test_fallback_is_product_use_action_not_unrelated_process(self):
        p = fixture_plan(); p["clips"][1]["selection"]["mode"] = "fallback"
        self.reject(p, "FALLBACK_ACTION")
        p["clips"][1]["selection"]["action"] = "eating"
        self.check(p)

    def test_foreign_product_asset_is_rejected(self):
        p = fixture_plan(); p["assets"]["clean"]["product"] = "다른 제품"
        self.reject(p, "PRODUCT_MISMATCH")

    def test_review_must_cover_actual_selected_interval_and_framing(self):
        for mutation in ("range", "frames", "framing"):
            p = fixture_plan()
            if mutation == "range": p["clips"][0]["review"]["source_out_us"] -= 1
            if mutation == "frames": p["clips"][0]["review"]["frames"].pop()
            if mutation == "framing": p["clips"][0]["framing"]["center_x"] = 0.6
            self.reject(p, "VISUAL_REVIEW")

    def test_voice_change_invalidates_prior_waveform_evidence(self):
        p = fixture_plan(); p["voice"]["cuts"][0]["source_in_us"] = 1
        p["assets"]["voice"]["duration_us"] += 1
        self.reject(p, "SPEECH_STALE")

    def test_voice_cannot_loop_or_reorder_original(self):
        p = fixture_plan(); p["voice"]["cuts"] = [
            {"start_frame": 0, "end_frame": 450, "source_in_us": 1_000_000},
            {"start_frame": 450, "end_frame": 900, "source_in_us": 0}]
        self.reject(p, "VOICE_SOURCE_ORDER")

    def test_undeclared_visual_gap_is_rejected(self):
        p = fixture_plan(); p["clips"][0]["end_frame"] = 299
        self.reject(p, "VISUAL_COVERAGE")


if __name__ == "__main__":
    unittest.main()

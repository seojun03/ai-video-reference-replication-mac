import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from production_intake import resolve


class ProductionIntakeTests(unittest.TestCase):
    def test_scope_menu_only_offers_full_production_or_visuals(self):
        result = resolve({"output_ratio": "9:16"})
        self.assertEqual([(x["number"], x["scope"]) for x in result["next_question_options"]],
                         [("1", "tts_and_edit"), ("2", "visuals_only")])

    def test_scope_menu_one_continues_to_voice_and_two_skips_voice_and_edit(self):
        first = resolve({"output_ratio": "9:16", "scope_choice": "1", "scope_response_text": "1"})
        self.assertTrue(first["tts"]["requested"])
        self.assertTrue(first["capcut"]["requested"])
        self.assertEqual(first["next_question"], "tts_voice_choice")
        second = resolve({"output_ratio": "9:16", "scope_choice": 2, "scope_response_text": "2"})
        self.assertEqual(second["scope"], "visuals_only")
        self.assertFalse(second["tts"]["requested"])
        self.assertFalse(second["capcut"]["requested"])
        self.assertIsNone(second["next_question"])
        self.assertTrue(second["script_approval"]["required"])
        self.assertEqual(second["authorization"]["text"], "2")

    def test_scope_menu_rejects_removed_numbers_and_conflicting_scope(self):
        for number in (3, 4):
            with self.assertRaisesRegex(ValueError, "INVALID_CHOICE: scope_choice"):
                resolve({"scope_choice": number, "scope_response_text": str(number)})
        with self.assertRaisesRegex(ValueError, "CONFLICTING_SCOPE_CHOICE"):
            resolve({"scope_choice": 2, "scope": "tts_only", "scope_response_text": "2"})

    def both(self, **values):
        return {"output_ratio": "9:16", "scope": "tts_and_edit",
                "scope_response_text": "어 TTS랑 편집까지 해줘", **values}

    def full(self, **values):
        return {"full_edit_requested": True, "full_edit_request_text": "편집까지 다 해줘", **values}

    def test_questions_move_from_ratio_to_scope_to_voice_to_category(self):
        self.assertEqual(resolve({})["next_question"], "output_ratio")
        self.assertEqual(resolve({"output_ratio": "9:16"})["next_question"], "production_scope")
        self.assertEqual(resolve(self.both())["next_question"], "tts_voice_choice")
        self.assertEqual(resolve(self.both(tts_voice_choice=1))["next_question"], "edit_category")
        done = resolve(self.both(tts_voice_choice=1, edit_category_choice=2))
        self.assertIsNone(done["next_question"])
        self.assertEqual(done["capcut"]["category"], "beauty")
        self.assertEqual(done["tts"]["reference_source"], "current_job_reference_video")
        self.assertFalse(done["repeat_execution_mode_question"])

    def test_each_edit_menu_number_is_forwarded_by_name(self):
        for number, name in [(1, "supplement"), (2, "beauty"), (3, "food"), (4, "other")]:
            with self.subTest(number=number):
                self.assertEqual(resolve(self.both(tts_voice_choice=1, edit_category_choice=number))["capcut"]["category"], name)

    def test_normalized_legacy_food_is_not_reinterpreted_by_new_menu_number(self):
        result = resolve(self.both(tts_voice_choice=1, edit_category_choice="food", edit_category_response_text="이전 질문의 2"))
        self.assertEqual(result["capcut"]["category"], "food")

    def test_early_full_edit_skips_scope_and_voice_but_not_missing_inputs(self):
        result = resolve(self.full())
        self.assertEqual(result["next_question"], "output_ratio")
        self.assertEqual(result["missing_fields"], ["output_ratio", "edit_category"])
        done = resolve(self.full(output_ratio="9:16", edit_category_choice="뷰티"))
        self.assertIsNone(done["next_question"])
        self.assertEqual(done["execution_mode"], "auto")
        self.assertEqual(done["tts"]["voice_mode"], "reference_voice")

    def test_explicit_voice_and_settings_override_full_edit_default(self):
        result = resolve(self.full(output_ratio="9:16", edit_category_choice=2, voice_id="user-designated-id",
                                   voice_settings={"model_id": "eleven_v3", "speed": 1.1, "tags": ["conversational", "confident"]}))
        self.assertEqual(result["tts"]["voice_mode"], "user_voice")
        self.assertEqual(result["tts"]["voice_id"], "user-designated-id")
        self.assertEqual(result["tts"]["settings"]["speed"], 1.1)
        self.assertIsNone(result["tts"]["reference_source"])

    def test_custom_voice_asks_for_actual_source_only_when_missing(self):
        result = resolve(self.both(tts_voice_choice=2, edit_category_choice=4))
        self.assertEqual(result["next_question"], "user_voice_source")
        result = resolve(self.both(tts_voice_choice=2, edit_category_choice=4, voice_source_path="/provided/voice.wav"))
        self.assertIsNone(result["next_question"])

    def test_edit_only_does_not_enable_tts_even_after_full_edit_request(self):
        result = resolve(self.full(output_ratio="9:16", scope="edit_only", scope_response_text="TTS는 하지 마. 음성은 이 파일로",
                                   edit_category_choice=3, provided_audio_path="/provided/narration.wav"))
        self.assertFalse(result["tts"]["requested"])
        self.assertTrue(result["capcut"]["requested"])
        self.assertIsNone(result["next_question"])
        self.assertEqual(result["authorization"]["text"], "TTS는 하지 마. 음성은 이 파일로")

    def test_edit_only_requires_provided_audio_instead_of_cloning_silently(self):
        result = resolve({"output_ratio": "9:16", "scope": "edit_only", "scope_response_text": "편집만", "edit_category_choice": 4})
        self.assertEqual(result["next_question"], "provided_edit_audio")
        self.assertFalse(result["tts"]["requested"])

    def test_tts_only_does_not_require_category_or_register_edit(self):
        result = resolve({"output_ratio": "9:16", "scope": "tts_only", "scope_response_text": "TTS만", "tts_voice_choice": 1})
        self.assertIsNone(result["next_question"])
        self.assertFalse(result["capcut"]["requested"])

    def test_declined_branches_are_not_reenabled_by_stale_voice_fields(self):
        result = resolve(self.full(output_ratio="9:16", scope="visuals_only", scope_response_text="둘 다 하지 말고 영상 소스만",
                                   voice_id="earlier-voice", edit_category_choice=2))
        self.assertFalse(result["tts"]["requested"])
        self.assertFalse(result["capcut"]["requested"])
        self.assertIsNone(result["tts"]["voice_id"])

    def test_reserved_reviews_are_not_overridden_by_automatic_execution(self):
        result = resolve(self.full(output_ratio="9:16", edit_category_choice=2, script_review_requested=True, visual_review_requested=True))
        self.assertFalse(result["delegation"]["script_preparation"])
        self.assertFalse(result["delegation"]["visual_decisions"])

    def test_full_delegation_never_confirms_a_script(self):
        for review in (False, True):
            with self.subTest(review=review):
                result = resolve(self.full(output_ratio="9:16", edit_category_choice=4, script_review_requested=review))
                self.assertEqual(result["execution_mode"], "auto")
                self.assertFalse(result["delegation"]["script_preparation"])
                self.assertFalse(result["delegation"]["script_auto_approval"])
                self.assertTrue(result["script_approval"]["production_blocked_until_confirmed"])
                self.assertEqual(result["script_approval"]["status"], "awaiting_script_confirmation")
                self.assertEqual(result["answers"]["script_review_requested"], review)

    def test_every_scope_requires_script_confirmation_even_when_choices_are_ready(self):
        for scope in ("visuals_only", "tts_only", "edit_only", "tts_and_edit"):
            with self.subTest(scope=scope):
                result = resolve({"output_ratio": "9:16", "scope": scope, "scope_response_text": scope,
                                  "tts_voice_choice": 1, "edit_category_choice": 4,
                                  "provided_audio_path": "/provided/voice.wav"})
                self.assertIsNone(result["next_question"])
                self.assertTrue(result["script_approval"]["required"])
                self.assertTrue(result["script_approval"]["production_blocked_until_confirmed"])

    def test_quoted_words_are_not_automatically_parsed_as_an_execution_request(self):
        result = resolve({"output_ratio": "9:16", "full_edit_request_text": "스킬 예시로 '편집까지 다 해줘'를 추가해줘"})
        self.assertEqual(result["next_question"], "production_scope")
        self.assertFalse(result["tts"]["requested"])

    def test_request_without_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "QUOTE_REQUIRED"):
            resolve({"full_edit_requested": True})
        with self.assertRaisesRegex(ValueError, "SCOPE_AND_RESPONSE_REQUIRED"):
            resolve({"scope": "tts_and_edit"})

    def test_requested_ratio_and_font_are_not_silently_changed(self):
        result = resolve(self.full(output_ratio="1:1", edit_category_choice=4, caption_font="User Font"))
        self.assertEqual(result["capcut"]["output_ratio"], "1:1")
        self.assertEqual(result["capcut"]["caption_font"], "User Font")

    def test_cli_writes_a_receipt_without_overwriting_previous_answers(self):
        cli = Path(__file__).resolve().parents[1] / "scripts/production_intake.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "answers.json", root / "receipt.json"
            source.write_text(json.dumps(self.full(output_ratio="9:16", edit_category_choice=2)))
            command = [sys.executable, str(cli), "--input", str(source), "--output", str(target)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original = target.read_bytes()
            self.assertEqual(json.loads(original)["capcut"]["category"], "beauty")
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(target.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()

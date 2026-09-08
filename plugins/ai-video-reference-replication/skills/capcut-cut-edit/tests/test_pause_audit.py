from __future__ import annotations

import array
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pause_audit import PauseAuditError, build_audit, validate_audit, file_hash


class PauseAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.audio = self.root / "test.wav"
        self.cut_hash = "1" * 64
        self.fps = 24

    def wav(self, parts, channels=1):
        samples = array.array("h")
        for seconds, amplitude in parts:
            samples.extend([amplitude] * round(seconds * 48000) * channels)
        if sys.byteorder != "little": samples.byteswap()
        with wave.open(str(self.audio), "wb") as w:
            w.setnchannels(channels); w.setsampwidth(2); w.setframerate(48000); w.writeframes(samples.tobytes())

    def audit(self, boundaries=()):
        return build_audit(self.audio, self.cut_hash, self.fps, boundaries)

    def reviewed(self, report):
        report["full_audio_review"] = {"reviewed": True, "note": "Synthetic amplitude fixture reviewed; no actual spoken phonemes."}
        return report

    def verify(self, report, boundaries=()):
        return validate_audit(report, audio=self.audio, cut_sha256=self.cut_hash, fps=self.fps, boundaries_us=boundaries)

    def decision(self, report, resolution="intentional_pause"):
        row = report["candidates"][0]
        evidence = self.root / "review.json"
        evidence.write_text(json.dumps({"audio_sha256": report["audio"]["sha256"], "range": row,
                                        "observation": "Synthetic silence interval with nonzero samples on each side."}))
        return {"candidate_id": row["id"], "start_us": row["start_us"], "end_us": row["end_us"],
                "audio_sha256": report["audio"]["sha256"], "resolution": resolution,
                "context_before": "before fixture", "context_after": "after fixture", "reason": "Synthetic test exception",
                "waveform_reviewed": True, "evidence": {"path": str(evidence), "sha256": file_hash(evidence)}}

    def test_sub_half_second_inside_one_clip_is_not_missed(self):
        self.wav([(1, 12000), (.25, 0), (1, 12000)])
        report = self.audit()
        self.assertEqual(len(report["candidates"]), 1)
        self.assertEqual(report["candidates"][0]["duration_us"], 250000)
        self.assertEqual(report["candidates"][0]["location"], "inside_cut")
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_FULL_AUDIO_REVIEW_REQUIRED"):
            self.verify(report)

    def test_short_candidate_at_clip_join_is_also_scanned(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.audit([1100000])
        self.assertEqual(report["candidates"][0]["location"], "across_cut")
        self.assertEqual(report["coverage"]["end_us"], 2300000)

    def test_quiet_breath_level_above_first_detector_is_still_a_candidate(self):
        self.wav([(1, 12000), (.3, 400), (1, 12000)])
        row, = self.audit()["candidates"]
        self.assertEqual(row["detector_db"], [-35])

    def test_missing_decision_cannot_pass_a_clean_word_or_sync_claim(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.reviewed(self.audit())
        report.update(cut_integrity_pass=True, caption_gap_frames=0)
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_DECISIONS_INCOMPLETE"):
            self.verify(report)

    def test_removing_candidate_from_report_fails_fresh_full_rescan(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.reviewed(self.audit()); report["candidates"] = []
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_AUDIT_STALE_OR_INCOMPLETE"):
            self.verify(report)

    def test_generic_ranking_exception_is_not_authority(self):
        self.wav([(1, 12000), (.6, 0), (1, 12000)])
        report = self.reviewed(self.audit()); decision = self.decision(report)
        decision["reason"] = "Ranking announcement should feel natural"
        report["decisions"] = [decision]
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_INTENT_EVIDENCE_REQUIRED"):
            self.verify(report)

    def test_explicit_current_instruction_preserves_real_intentional_pause(self):
        self.wav([(1, 12000), (.6, 0), (1, 12000)])
        report = self.reviewed(self.audit()); decision = self.decision(report)
        source = self.root / "explicit-request.txt"; source.write_text("Keep the silence between the two synthetic tones.")
        decision["intent_evidence"] = {"kind": "user_instruction", "quote": source.read_text(),
                                      "source": {"path": str(source), "sha256": file_hash(source)}}
        report["decisions"] = [decision]
        self.assertEqual(self.verify(report)["status"], "pause_audit_pass")

    def test_long_silence_cannot_be_relabeled_a_short_natural_pause(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.reviewed(self.audit()); decision = self.decision(report, "natural_short_pause")
        decision.update(previous_speech_end_us=1000000, next_speech_start_us=1300000)
        report["decisions"] = [decision]
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_RETAINED_TOO_LONG"):
            self.verify(report)

    def test_speech_protection_needs_specific_phoneme(self):
        self.wav([(1, 12000), (.3, 400), (1, 12000)])
        report = self.reviewed(self.audit()); report["decisions"] = [self.decision(report, "speech_protection")]
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_PHONEME_REQUIRED"):
            self.verify(report)

    def test_actual_cleanup_passes_and_waveform_stays_intact(self):
        self.wav([(1, 12000), (.1, 0), (1, 12000)])
        report = self.reviewed(self.audit()); before = self.audio.read_bytes()
        self.assertEqual(self.verify(report)["status"], "pause_audit_pass")
        self.assertEqual(before, self.audio.read_bytes())

    def test_changed_audio_and_cut_mapping_each_invalidate_review(self):
        self.wav([(1, 12000), (.1, 0), (1, 12000)])
        report = self.reviewed(self.audit())
        self.cut_hash = "2" * 64
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_AUDIT_STALE_OR_INCOMPLETE"):
            self.verify(report)
        self.cut_hash = "1" * 64
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_AUDIT_STALE_OR_INCOMPLETE"):
            self.verify(report)

    def test_pending_candidate_cannot_be_marked_for_cut_without_rendering_it(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.reviewed(self.audit()); report["decisions"] = [self.decision(report, "needs_cut")]
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_UNRESOLVED"):
            self.verify(report)

    def test_policy_cannot_be_relaxed_only_in_report(self):
        self.wav([(1, 12000), (.3, 0), (1, 12000)])
        report = self.reviewed(self.audit()); report["policy"]["candidate_min_seconds"] = .5
        with self.assertRaisesRegex(PauseAuditError, "PAUSE_AUDIT_STALE_OR_INCOMPLETE"):
            self.verify(report)

    def test_stereo_phase_inversion_does_not_turn_speech_into_silence(self):
        raw = array.array("h", [12000, -12000] * 48000)
        if sys.byteorder != "little": raw.byteswap()
        with wave.open(str(self.audio), "wb") as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(48000); w.writeframes(raw.tobytes())
        self.assertEqual(self.audit()["candidates"], [])


if __name__ == "__main__":
    unittest.main()

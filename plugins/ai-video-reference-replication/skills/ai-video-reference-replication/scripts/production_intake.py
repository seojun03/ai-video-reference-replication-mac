#!/usr/bin/env python3
"""Normalize current interview answers. No intent inference, API calls, or editor access."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime
from pathlib import Path


CATEGORIES = {
    "1": "supplement", "건기식": "supplement", "건강기능식품": "supplement", "supplement": "supplement",
    "2": "beauty", "뷰티": "beauty", "beauty": "beauty",
    "3": "food", "식품": "food", "food": "food",
    "4": "other", "그외": "other", "기타": "other", "other": "other",
}
VOICES = {"1": "reference_voice", "레퍼런스음성": "reference_voice", "reference_voice": "reference_voice",
          "2": "user_voice", "사용자지정음성": "user_voice", "user_voice": "user_voice"}
SCOPES = {"tts_and_edit": (True, True), "tts_only": (True, False),
          "edit_only": (False, True), "visuals_only": (False, False)}
SETTING_KEYS = {"model_id", "tags", "speed", "stability", "seed", "delivery_tag", "similarity_boost", "style"}
ANSWER_KEYS = {"output_ratio", "scope", "scope_response_text", "tts_voice_choice", "tts_voice_response_text",
               "edit_category_choice", "edit_category_response_text", "full_edit_requested", "full_edit_request_text",
               "script_review_requested", "visual_review_requested", "voice_id", "voice_name", "voice_source_path",
               "provided_audio_path", "caption_font", "voice_settings"}


def text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("TEXT_VALUE_REQUIRED")
    return value.strip() or None


def flag(answers, name):
    value = answers.get(name, False)
    if type(value) is not bool:
        raise ValueError(f"BOOLEAN_REQUIRED: {name}")
    return value


def choice(value, choices, field):
    if value is None or value == "":
        return None
    if type(value) not in (str, int):
        raise ValueError(f"INVALID_CHOICE: {field}")
    key = "".join(str(value).strip().lower().split())
    if key not in choices:
        raise ValueError(f"INVALID_CHOICE: {field}")
    return choices[key]


def resolve(answers):
    if not isinstance(answers, dict):
        raise ValueError("ANSWERS_OBJECT_REQUIRED")
    unknown = set(answers) - ANSWER_KEYS
    if unknown:
        raise ValueError("UNEXPECTED_ANSWER_FIELDS: " + ", ".join(sorted(unknown)))
    full_request = flag(answers, "full_edit_requested")
    flag(answers, "script_review_requested")  # Legacy answer remains provenance, never an approval waiver.
    full_text = text(answers.get("full_edit_request_text"))
    if full_request and not full_text:
        raise ValueError("FULL_EDIT_REQUEST_QUOTE_REQUIRED")

    ratio = text(answers.get("output_ratio"))
    if ratio is not None and ratio not in ("9:16", "1:1"):
        raise ValueError("OUTPUT_RATIO_UNSUPPORTED")
    scope = text(answers.get("scope"))
    scope_text = text(answers.get("scope_response_text"))
    explicit_scope = scope is not None
    if explicit_scope and (scope not in SCOPES or not scope_text):
        raise ValueError("SCOPE_AND_RESPONSE_REQUIRED")
    if scope is None and full_request:
        scope = "tts_and_edit"
    tts_requested, edit_requested = SCOPES.get(scope, (False, False))

    voice_id = text(answers.get("voice_id"))
    voice_name = text(answers.get("voice_name"))
    voice_source = text(answers.get("voice_source_path"))
    voice_mode = choice(answers.get("tts_voice_choice"), VOICES, "tts_voice_choice") if tts_requested else None
    if tts_requested and voice_mode is None:
        if voice_id or voice_name or voice_source:
            voice_mode = "user_voice"
        elif full_request:
            voice_mode = "reference_voice"
    category = choice(answers.get("edit_category_choice"), CATEGORIES, "edit_category_choice") if edit_requested else None
    settings = answers.get("voice_settings", {})
    if not isinstance(settings, dict) or set(settings) - SETTING_KEYS:
        raise ValueError("VOICE_SETTINGS_FIELDS")
    provided_audio = text(answers.get("provided_audio_path"))

    missing = []
    if ratio is None:
        missing.append("output_ratio")
    if scope is None:
        missing.append("production_scope")
    if tts_requested and voice_mode is None:
        missing.append("tts_voice_choice")
    if tts_requested and voice_mode == "user_voice" and not (voice_id or voice_name or voice_source):
        missing.append("user_voice_source")
    if edit_requested and category is None:
        missing.append("edit_category")
    if edit_requested and not tts_requested and not provided_audio:
        missing.append("provided_edit_audio")

    authorization = None
    if scope is not None:
        authorization = {"source": "scope_interview" if explicit_scope else "early_full_edit_request",
                         "text": scope_text if explicit_scope else full_text}
    return {
        "schema": "reference-production-intake/v1",
        "status": "choices_ready" if not missing else "awaiting_interview_answer",
        "output_ratio": ratio,
        "scope": scope,
        "execution_mode": "auto" if scope is not None else None,
        "mode_selection_source": "early_production_intake" if scope is not None else None,
        "authorization": authorization,
        "next_question": missing[0] if missing else None,
        "missing_fields": missing,
        "repeat_execution_mode_question": scope is None,
        "tts": {
            "requested": tts_requested, "voice_mode": voice_mode,
            "reference_source": "current_job_reference_video" if voice_mode == "reference_voice" else None,
            "voice_id": voice_id if voice_mode == "user_voice" else None,
            "voice_name": voice_name if voice_mode == "user_voice" else None,
            "voice_source_path": voice_source if voice_mode == "user_voice" else None,
            "settings": copy.deepcopy(settings) if tts_requested else {},
        },
        "capcut": {
            "requested": edit_requested, "category": category,
            "category_response_text": text(answers.get("edit_category_response_text")) or
                                      (str(answers["edit_category_choice"]) if category else None),
            "output_ratio": ratio,
            "caption_font": text(answers.get("caption_font")) or "Pretendard SemiBold",
            "provided_audio_path": provided_audio if edit_requested and not tts_requested else None,
            "target_policy": "exact_existing_company_project_new_editable_timeline" if edit_requested else None,
        },
        "delegation": {
            "script_preparation": False,
            "script_auto_approval": False,
            "visual_decisions": edit_requested and not flag(answers, "visual_review_requested"),
            "user_reserved_reviews_preserved": True,
        },
        "script_approval": {
            "required": True,
            "status": "awaiting_script_confirmation",
            "policy": "explicit_user_confirmation_of_exact_script_sha256",
            "production_blocked_until_confirmed": True,
        },
        "answers": copy.deepcopy(answers),
        "boundary": "Interview choices only; not proof of media, voice rights, cost limits, QC, or saved delivery.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    raw = Path(args.input).read_bytes()
    result = resolve(json.loads(raw))
    result["answers_source"] = {"path": str(Path(args.input).resolve()), "sha256": hashlib.sha256(raw).hexdigest()}
    result["recorded_at"] = datetime.now().astimezone().isoformat()
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        destination = Path(args.output)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("x", encoding="utf-8") as stream:
            stream.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()

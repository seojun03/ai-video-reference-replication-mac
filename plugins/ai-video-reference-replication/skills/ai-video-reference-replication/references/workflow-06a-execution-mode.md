# Gate 1B execution mode — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

## Gate 1B — execution-mode checkpoint

First load `production-intake.json`. If the early TTS/edit scope or an earlier end-to-end request already sets `execution_mode: auto`, carry its exact authorization text and selected actions forward, show the validated plan/costs, and **skip this mode question**. Do not overwrite a declined TTS/edit action merely because execution is automatic. The questions below are only for a legacy/unanswered run or an explicitly reserved precision-planning workflow.

Without an existing execution choice, after the complete plan passes mode-specific validation, ask one mode question before paid generation. Use the prompt matching `video_source_mode` and do not ask again in the same run.

For `ai_generation`:

```text
기획이 완료되었습니다. 진행 모드를 선택해주세요.
1. 정밀 기획 모드 — 상세 컷 기획과 근거를 검토한 뒤, 다음 실행을 별도로 승인합니다.
2. 자동모드 — 현재 기획 범위 안에서 영상 생성, 레퍼런스 음성 TTS, CapCut 컷편집까지 자동으로 이어서 진행합니다.
```

For `existing_clean_edit`:

```text
기획이 완료되었습니다. 진행 모드를 선택해주세요.
1. 정밀 기획 모드 — 상세 컷 기획과 클린본 배정을 검토한 뒤, 다음 실행을 별도로 승인합니다.
2. 자동모드 — 현재 기획 범위 안에서 클린본 편집, 레퍼런스 음성 TTS, CapCut 컷편집까지 자동으로 이어서 진행합니다.
```

Record `execution_mode: "precision_planning"` or `execution_mode: "auto"` with the user's actual response and timestamp. For an early scope/end-to-end request, record `mode_selection_source: "early_production_intake"` and its original response rather than inventing a later mode-menu answer. Do not silently default a run with no applicable execution request.

This is an execution checkpoint and is separate from Gate 0's `intake_mode`. Never overwrite, reuse, or reinterpret `intake_mode` when recording `execution_mode`.

### `precision_planning`

- Show the concise Gate 1 table and the linked full plan, then stop for the user's explicit first-attempt approval.
- Do not invoke `$elevenlabs-reference`, `$capcut-automation`, or any paid generation automatically from this mode.
- Preserve the plan, product gate, estimated costs, and unresolved questions so a later approval resumes without repeating intake.

### `auto`

- Treat either the early recorded production request or the later mode selection as authorization for the selected scope's listed first attempts and deterministic work. Preserve the visual-source branch: `existing_clean_edit` never gains AI-generation permission. Do not request another approval between already requested branches, and never enable TTS or editing the user declined.
- Invoke `$elevenlabs-reference` only when `production_intake.tts.requested` is true. Honor its `reference_voice` or `user_voice` selection; pass the current reference path/hash for the former and the exact designated ID/name/audio source for the latter. The early ‘finish editing’ shortcut chooses the reference only when no voice override exists. Reuse a reference clone only for an exact `source_sha256` match. Pass current explicit model/tags/speed settings unchanged; otherwise use the child skill's current defaults, not settings copied from a previous job. Run bounded generation and QC under the child's existing authorization/retry limits. If strict finalization is pending, keep the complete candidate as `preview`/`working_audio` and continue requested editing without calling it final.

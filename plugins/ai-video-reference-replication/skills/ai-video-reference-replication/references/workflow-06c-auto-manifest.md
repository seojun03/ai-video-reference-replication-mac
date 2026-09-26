# Auto-mode manifest minimum — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

### Auto-mode manifest minimum

Record `production_intake` with its path/hash, exact answer provenance, requested TTS/edit booleans, normalized voice/category, ratio, and review delegation before execution. The examples below show a full TTS+edit request; derive `auto_actions.tts_initial` and `auto_actions.capcut_edit` from the current scope instead of copying both as true. Add these fields to the run manifest before execution:

```json
{
  "video_source_mode": "ai_generation",
  "execution_mode": "auto",
  "mode_selected_at": "ISO-8601",
  "mode_selection_text": "사용자 원문",
  "auto_actions": {
    "clean_clip_intake": false,
    "image_generation": true,
    "video_generation": true,
    "tts_initial": true,
    "capcut_edit": true,
    "intermediate_approval_prompts": false,
    "paid_retries": false,
    "publishing": false
  },
  "quality_profile": "balanced_auto",
  "semantic_visual_contract": "literal_visual_proof_v1",
  "duration_policy": "adaptive_3_4_5_seconds",
  "semantic_retry_policy": {
    "paid_retries": false,
    "authorized_in_gate_1": false,
    "max_semantic_retries_total": 0,
    "semantic_retry_budget_credits": 0
  },
  "reserve_policy": "on_demand_after_main_qc",
  "image_generation_mode": "openai_only",
  "image_generation_route": "built_in_image_gen",
  "execution_pipeline": "per_cut_streaming",
  "streaming_pipeline_state": "<run>/qc/streaming-pipeline.json",
  "product_knowledge": {
    "enabled": true,
    "library": "<exact-product-knowledge>/knowledge-library.json",
    "snapshot_path": "<run>/product_context_snapshot.json",
    "snapshot_sha256": "<actual snapshot hash>"
  },
  "image_candidates_per_cut": 1,
  "higgsfield_image_jobs": 0,
  "image_api_jobs": 0,
  "image_cli_jobs": 0,
  "image_lanes": {
    "openai": {"route": "built_in_image_gen", "max_concurrency": 5, "request_batch_size": 1}
  },
  "submission_ledger": "<run>/qc/submission-ledger.json",
  "tts_finalization_state": "pending|user_approved_final|user_delegated_auto_qc_final",
  "capcut_target": {
    "project": "resolved exact company project",
    "timeline": "generated_unique_new_timeline"
  }
}
```

For `existing_clean_edit`, replace all generation-only fields with this minimum instead of inventing empty Higgsfield/OpenAI jobs:

```json
{
  "video_source_mode": "existing_clean_edit",
  "execution_mode": "auto",
  "mode_selected_at": "ISO-8601",
  "mode_selection_text": "사용자 원문",
  "auto_actions": {
    "clean_clip_intake": true,
    "image_generation": false,
    "video_generation": false,
    "tts_initial": true,
    "capcut_edit": true,
    "intermediate_approval_prompts": false,
    "publishing": false
  },
  "quality_profile": "balanced_auto",
  "image_generation_mode": "disabled_existing_clean_edit",
  "clean_clip_library_manifest": "<product>/기존 영상 표현/사용자 제공 클린본/clean-clip-library.json",
  "stored_clean_clips_dir": "<product>/클린본/사용자 제공 클린본",
  "registered_clean_clip_count": 0,
  "tts_finalization_state": "pending|user_approved_final|user_delegated_auto_qc_final",
  "capcut_target": {"project": "resolved exact company project", "timeline": "generated_unique_new_timeline"}
}
```

`auto` means no intermediate user prompt, not permission to mislabel a preview as final or to bypass a child skill's failed quality gate. Report `auto_edit_complete_tts_pending` when CapCut is verified but the TTS child still lacks its required final state.

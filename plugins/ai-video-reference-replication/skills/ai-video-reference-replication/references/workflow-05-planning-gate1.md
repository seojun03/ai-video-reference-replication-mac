# Planning — Gate 1 — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

## Planning — Gate 1

Require a current `visual_detail_contract.json` with `ready_for_visual_planning: true` before segmentation. Segment the exact script into atomic semantic units before designing shots. Group units into the fewest cuts that can literally prove every unit, then assign `3.0 s` to `single_state_or_action`, `4.0 s` to `two_step_action`, or `5.0 s` to `causal_transformation`. Split again when one subject/action/result chain cannot prove all grouped units inside five seconds. Do not inherit the reference cut count, force every cut to three seconds, or pad to a round number. Match each beat to the best reference technique by communicative function and causal compatibility, not by index. Bind every cut to the relevant visual-detail question IDs or direct user directives; a cut may not contradict or silently weaken a locked answer.

### `existing_clean_edit` planning branch

- Build a machine-readable source-edit plan from the registered clean-clip manifest. Do not create image prompts, motion-generation prompts, image candidates, selected-start records, provider jobs, generation costs, or reserve-generation jobs.
- For every cut record `cut`, `script`, `visual_job`, `reference_technique`, `composition`, `must_show`, `hard_exclusions`, `risk_level`, `source_clip_id`, `source_path`, `source_sha256`, `source_in`, `source_out`, `source_duration`, `selection_rationale`, `reframe`, `speed`, `source_audio_policy`, and `route: "사용자 제공 클린본 → CapCut 편집"`.
- Verify every planned segment against the stored original's start/middle/end frames. Do not use a prepared, proxy, upscaled, FPS-converted, or previously edited derivative as the main visual source.
- Keep the registered originals immutable. Apply trims, reframes, speed changes, audio muting, captions, and other approved edit operations only in an edit staging area or the CapCut timeline.
- Run the clean-edit plan validation procedure in `references/existing-clean-edit-workflow.md`. The Gate 1 table must show cut, script beat, selected clip ID and time range, mapped reference technique/composition, planned edit, risk, must-show, hard exclusions, and generation cost `0`.
- State the stored clip count, unmatched script beats, reused clip segments, output ratio, duration estimate, planned cut count, source-audio policy, TTS state, CapCut target state, and AI image/video generation `disabled`.

The early selected scope/end-to-end request or one explicit Gate 1 approval authorizes only the listed non-paid source selections, deterministic transforms, requested TTS initial action, and requested CapCut edit. Show the plan and continue without another approval when the early contract already covers these actions. It never authorizes AI image/video generation, publishing, uploading, deletion, or replacement of library originals.

### `ai_generation` planning branch

For every cut store full prompts and generation provenance in a machine-readable plan. Include:

- `cut`, `script`, `visual_job`, `reference_technique`, `composition`, and `medium`;
- `style_reference`, `expression_reference`, `composition_reference`, `native_camera_motion`, and `editing_effects: "forbidden"`;
- `must_show`: one immediately understandable requirement;
- `semantic_units`: every meaning-bearing clause as a separate object with stable `id`, exact `text`, and concrete `required_visual_evidence`;
- `visual_proof`: non-empty `subject`, `start_state`, `visible_action`, `end_state`, `causal_link`, `success_frame`, and a `forbidden_shortcuts` list. The start still must be action-ready immediately before `visible_action`; it must not depict an already completed result;
- `duration_class`: `single_state_or_action`, `two_step_action`, or `causal_transformation`; `duration_seconds`: exactly `3.0`, `4.0`, or `5.0` according to that class; and `duration_reason`: why that much time is needed to make the proof legible;
- `hard_exclusions`: at most three cut-specific failure triggers in addition to global exclusions;
- `risk_level`: `high`, `medium`, or `low`;
- `risk_reason` and `safe_template` when applicable;
- `motion_design`: `primary_motion`, `secondary_motion`, `camera_motion`, `static_anchors`, and `motion_phases`. Name visible subjects and verbs; vague entries such as `natural motion`, `subtle movement`, or `camera movement` are invalid. `camera_motion` may be deliberately locked only when it states why and the primary and secondary motions still make the shot visibly alive;
- `image_quality`: `high` for the product master, `product_presence: required`, or high-risk cuts; `low` is allowed for low/medium-risk product-independent cuts. If omitted in a legacy plan, infer it at execution time rather than regenerating the plan;
- `image_generation_mode` at plan level: exactly `openai_only`; `image_generation_route`: exactly `built_in_image_gen`; all stills use the built-in OpenAI `image_gen` tool through `$imagegen` default mode;
- `image_candidates_per_cut`: exactly `1` for the approved first attempt. Candidate provenance, built-in result path, quality, and selected/rejected state must be retained in the ledger and manifest. Record `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, and `image_cli_jobs: 0`; fail closed if a plan or execution record contains a Higgsfield image, direct Images API, or ImageGen CLI candidate;
- `scene_design`: a cut-specific object containing non-empty `setting`, `subject_action`, `shot_scale`, and `camera_angle`. No two main cuts may share the same four-part scene-design signature or the same normalized image prompt;
- `product_presence`: `required`, `optional`, or `forbidden`; when `required`, add exact `product_asset_id`, `product_source`, `product_identity_lock`, and `integration_strategy`. Use `scene_native_reference_conditioned` by default. Add `placement_plane`, `occlusion_plan`, and `contact_shadow_plan` only for `official_pixel_composite`;
- `route`: exactly `Higgsfield Kling v3.0 — start image only`;
- one English image prompt, one Korean Higgsfield motion instruction whose timed phases end at the planned `3.0 s`, `4.0 s`, or `5.0 s`, deterministic post layers, and cost.

At plan level add `semantic_retry_policy`. Default it to `paid_retries: false`, `authorized_in_gate_1: false`, `max_semantic_retries_total: 0`, and `semantic_retry_budget_credits: 0`. A nonzero cut-local semantic retry allowance is valid only when Gate 1 displays its maximum job count and maximum credits and the user's approval explicitly covers that total. Never infer a standing paid-retry permission from this global quality rule.

Run `scripts/lint_cut_plan.py PLAN.json --strict-schema` before Gate 1 approval. Fix every blocking finding before generation. A resumed legacy plan may be inspected without `--strict-schema`, but any newly built or materially remapped plan must pass the strict motion schema.

Show a concise Gate 1 table in chat with only: cut, script beat, literal visual proof summary, duration class/seconds, mapped reference technique/composition, primary/secondary/camera motion summary, route, risk, must-show, hard exclusions, and cost. Save full prompts in the linked plan file; print them in chat only when the user asks. State product source/master, output ratio, duration estimate, main cut count, optional reserve count/policy, `image_generation_mode: "openai_only"`, OpenAI candidate count, `higgsfield_image_jobs: 0`, selected-start count, OpenAI image cost or usage boundary, separately exposed Kling video cost, quality profile, deterministic post layers, transition exclusions, and any separately capped semantic-retry allowance. For new plans, `cuts[]` and the initial image/video job counts cover main cuts only; `reserve_cuts[]` are separately listed and costed unless `reserve_policy: "approved_upfront"` is explicit.

In `ai_generation`, the early end-to-end/selected-production-scope request or one explicit Gate 1 approval authorizes the listed first-attempt image candidates, listed Higgsfield video attempts, and listed non-paid deterministic post corrections within the requested visual scope. Preserve strict plan validation, cost disclosure, and user budget limits; display the plan and proceed when the early request already authorizes execution rather than demanding another approval phrase. It does not authorize extra keyframes, changed scope, publishing, unlisted charges, or new paid retries. Existing separately authorized retry job/credit ceilings remain binding.

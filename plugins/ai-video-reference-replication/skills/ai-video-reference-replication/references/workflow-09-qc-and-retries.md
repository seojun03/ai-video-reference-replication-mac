# QC, failure isolation and retries — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

## Fast QC

Run `scripts/qc_media.py` before visual review. It handles objective checks, reads each cut's planned duration, and produces sampled frames/contact sheets. Pass `--review-profile balanced_auto` for auto runs or `--review-profile precision` for precision runs, plus the plan when available, so it records the review tier. For schema-version-4 cuts, create `semantic-visual-qc.json` from the five original-resolution checkpoints and run `scripts/validate_semantic_qc.py PLAN.json semantic-visual-qc.json`; technical QC alone never promotes a clip. Keep full job responses and prompts in files; show only exceptions in chat.

In `existing_clean_edit`, use this QC on the registered source files and selected time ranges. Require playable media, valid duration, correct ratio/reframe plan, exact source hash, script-beat relevance, stable product identity where visible, and no accidental use of source audio. Do not require a user-provided source to be exactly three seconds or silent; those are edit-plan decisions.

### Hard failures

Apply generation/model/provenance failures below only to `ai_generation`. In `existing_clean_edit`, hard-fail a missing or hash-mismatched registered source, invalid time range, wrong-company/product clip substitution, unreadable/corrupt media, unapproved derivative used as the main source, or any AI image/video generation job.

- unclear or wrong assigned-script meaning;
- any semantic unit without a visible evidence frame; a prop, package, bottle, icon, arrow, label, reactionless pose, or abstract symbol used instead of an available literal action; a missing start state, completed action, end state, causal link, or unmistakable success frame; an object/character swap that fakes the transformation; or a result that appears without showing its stated cause;
- frozen or near-frozen footage; motion limited to compression shimmer, edge wobble, random micro-jitter, a local Ken Burns move, or text animation; a motion prompt that names movement but produces no visible start-to-middle-to-end progression; missing script-bearing primary motion; or a scene that relies on camera motion alone without meaningful subject, material, or environmental life unless the plan explicitly justifies a locked tableau reveal;
- unsafe, sexualized, gory, malformed, or unintended anatomy;
- wrong brand, generic substitute, tea-bag-like or unbranded packet, wrong package type/color/silhouette, materially deformed product identity, or invented competing label/claim/text/UI;
- sticker-like, floating, doubled, intersecting, perspective-mismatched, or lighting-mismatched product insertion; visible rectangular cleanup patch or unexplained bar beside a product;
- in `ai_generation`, wrong model, start/end-image contract, ratio, duration, missing file, audio, border, or transition;
- in `ai_generation`, any still image created, planned, retried, or restored outside the built-in OpenAI `image_gen` route, including Higgsfield, direct Images API, or ImageGen CLI;
- in `ai_generation`, missing Higgsfield provider/job/model provenance or any local-only motion substitute;
- gross reference-composition drift or wrong visual medium.

### Soft deviations

In `ai_generation`, accept minor palette, watercolor density, background-prop, lighting, camera-position variation, compression softness, fine-print blur, or brief edge shimmer when meaning, safety, unmistakable designated-product identity, medium, and composition class remain intact. In `existing_clean_edit`, do not judge the user-provided source against generated-medium fidelity; only approve or reject its selected segment for script meaning, reference-edit role, safety, product identity, and technical usability. Never accept a generic or different product as a soft deviation.

### Review policy

- Always visually review high-risk cuts and automated warnings.
- Review low/medium-risk cuts in compact contact sheets; open original frames only when uncertain.
- In `ai_generation`, extract start, middle, and end frames for every legacy cut and start/25%/50%/75%/end frames for every schema-version-4 cut. Record `primary_motion_visible`, `secondary_motion_visible`, `camera_motion_matches_plan`, `static_anchors_stable`, and `motion_progression_pass`. For schema version 4 also record every semantic unit's evidence frames plus `subject_visible`, `start_state_visible`, `visible_action_completed`, `end_state_visible`, `causal_link_visible`, `success_frame_clear`, and `literal_first_pass`; every value must be true. Optical-flow or frame-difference values may flag a cut for review but never prove meaningful action or meaning by themselves. A deliberately locked camera passes `camera_motion_matches_plan` only when the recorded reason is valid and the other motion layers remain visible. In `existing_clean_edit`, extract start/middle/end frames for the selected source range and record `script_meaning_pass`, `source_range_pass`, `product_identity_pass`, `technical_usability_pass`, and `source_hash_verified`. In `balanced_auto`, every schema-version-4 cut still receives original-resolution semantic review; contact-sheet-only review remains limited to clean low/medium-risk legacy cuts.
- In `ai_generation`, add `selected_start_diversity_pass` and `cross_cut_scene_variety_pass` to final QC. Both must be true. Video-level motion differences cannot rescue clips generated from the same or near-identical start image; quarantine the later clip and return to its still-generation stage.
- Record passes in `qc-summary.json`. In chat report only failed/warning cuts plus one aggregate pass count.
- In `ai_generation`, for every product-visible cut, inspect start, middle, and end frames at original resolution and record every criterion from `references/product-integration-qc.md`. Treat any failed product-integration criterion as a hard failure, never a soft deviation. In `existing_clean_edit`, inspect the selected stored-source frames for exact designated-product identity and record the source clip ID/hash instead of applying generated-composite criteria.

## Failure isolation and retries

- In `ai_generation`, a **cut-local failure** affects one prompt/output: quarantine that cut, skip its downstream promotion, and continue unrelated already-approved first attempts. Do not retry unless the current Gate 1-approved `semantic_retry_policy` still has both a remaining job and remaining credit budget; when authorized, make only the narrow cut-local change named by the failed proof check and never redesign unrelated cuts.
- In `ai_generation`, a **systemic failure** includes wrong product scope/master, wrong model/ratio, corrupt tooling, or the same medium/text/box failure across two or more pilot outputs: stop the batch.
- In `ai_generation`, a provider timeout or lost response is not a failed submission. Mark the ledger entry `submitted_unknown`, query the provider by job ID or matching request metadata, and only submit a new attempt after reconciliation proves no accepted job exists. Never use a second CLI/MCP call as a timeout workaround.
- In `existing_clean_edit`, isolate an unusable registered source and remap only to another already-supplied, registered clip when the approved plan permits it. If no supplied clip covers a beat, report `unmatched_visual_beat` and ask for another clean clip or a narrower edit decision; never generate a replacement.
- Deterministic non-paid corrections listed in Gate 1 may continue without a new approval.
- Aggregate retry candidates not covered by a remaining preauthorized semantic-retry allowance into one Gate 3 report: cut/job ID, failed semantic unit and evidence checkpoint, symptom, likely cause, one narrow fix, job count, and current cost. Wait for explicit approval before any paid retry outside the visible Gate 1 ceilings.

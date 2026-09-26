# Staged execution — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

## Staged execution

The numbered generation stages below apply only to `ai_generation`.

1. Load/capture exact-product knowledge and its snapshot; validate the product master and plan lint. Initialize `<run>/qc/streaming-pipeline.json` and the shared submission ledger under `references/per-cut-streaming.md`.
2. Claim every still using `scripts/submission_ledger.py`. For videos use `streaming_cut_pipeline.py claim-video`, which atomically claims the same ledger format. Include plan hash, cut, stage, attempt, start-image hash, model/mode, ratio, duration and sound. An existing claim is never permission to resubmit.
3. Start independent built-in OpenAI images concurrently, prioritizing high-risk/product-required starts and respecting common character/product prerequisites. Keep one first-attempt candidate per cut and existing quality caps. Do not create a Higgsfield image lane.
4. Process each image completion immediately, even while other images are running: save provenance, review its action-ready state and product/composition, inspect the rolling contact sheet, and atomically register its unique start. Reject only the failing cut; a new paid image requires its existing retry authorization.
5. Drain ready video cuts whenever a slot is free. Upload/confirm the selected image and submit Kling immediately for that cut; do not wait for the remaining images or a full submission batch. Use a batch only for cuts already ready together. Continue image generation, image review and video status/download/QC concurrently. The primary/secondary/camera motion and exact designated product requirements remain unchanged.
6. Prioritize at most two high-risk video pilots. Only cuts with a real pilot dependency recorded as `video_depends_on` wait for its motion QC; unrelated cuts and image work continue. Stop affected submissions on a systemic failure. Record lost/timeout responses as `submitted_unknown` and reconcile before any further attempt.
7. Never animate failed/unselected starts. After all main images are ready, run the full cross-cut diversity audit/contact sheet before final promotion. After main video QC, evaluate only the reserves permitted by `reserve_policy`.
8. Normalize passing media to the approved ratio and planned `3.0 s`, `4.0 s`, or `5.0 s`, retaining the completed action/success frame. Never substitute local-only motion.
9. Capture new product inputs and final script/asset states, re-read the product library, and refresh the final run manifest. Record unresolved items explicitly instead of claiming future reuse is ready when storage failed.

For `existing_clean_edit`, execute these stages instead:

1. Resolve the exact company/product scope, store the supplied originals with `scripts/store_clean_clips.py`, and freeze the returned manifest revision for the run.
2. Probe every registered clip and extract contact sheets plus start/middle/end frames without altering the originals.
3. Validate every planned `source_clip_id`, SHA-256, path, and source time range against the frozen manifest. Stop on a missing/hash-mismatched source; never silently substitute another clip.
4. When editing was requested, stage only the selected original clips, then apply the requested trim, reframe, source-audio, caption, and supported deterministic edit instructions in CapCut.
5. For requested editing, verify that the saved draft uses authoritative stored sources, contains the planned order/durations, preserves editable narration/captions, and has no AI image/video job or generated substitute. Source-only scope finishes with the reviewed source package instead.

# Generation rules and model locks — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

## Quality-speed profile

Set `quality_profile: "balanced_auto"` for `execution_mode: "auto"` and `quality_profile: "precision"` for `precision_planning`, unless the user explicitly chooses another documented profile. Both profiles keep the same hard-failure list. For legacy plans, `balanced_auto` changes only scheduling: objective probes and frame extraction still run for every clip, while original-resolution human review is reserved for high-risk/product/warning cuts and the rest are reviewed in contact sheets. Every schema-version-4 cut is always `deep` for sentence-level review in both profiles and uses five checkpoints (start, 25%, 50%, 75%, end). `precision` also opens original frames for every legacy cut. Never treat the balanced profile as permission to accept an unproven semantic unit, wrong product, unsafe anatomy, frozen motion, wrong model, or unverified final TTS.

In `ai_generation`, use `reserve_policy: "on_demand_after_main_qc"` by default for new plans. Generate and QC main cuts first, then create only the minimum reserve clips needed to cover a failed beat or an explicitly requested alternate. Use `"approved_upfront"` only when the user explicitly authorizes all reserve first attempts and their separate cost. In `existing_clean_edit`, do not create reserve footage; report unmatched beats and reuse only approved stored segments.

## GPT-only image generation and concurrency

This section applies only when `video_source_mode: "ai_generation"`. In `existing_clean_edit`, set `image_generation_mode: "disabled_existing_clean_edit"` and skip the section completely.

For every new or resumed future generation action, set `image_generation_mode: "openai_only"` and `image_generation_route: "built_in_image_gen"`. Use only the built-in OpenAI `image_gen` tool through `$imagegen` default mode for stills. Historical manifests may contain `higgsfield_only`, `hybrid_parallel`, direct API, or CLI records; preserve them as read-only provenance, but never submit another image job through those routes. A material remap must migrate the new plan to the built-in route before generation.

- The built-in `image_gen` tool is the only permitted route for scene still generation. It produces one distinct scene asset per call, so submit distinct cuts as separate parallel calls; do not use a multi-output request to represent different prompts.
- Use the recorded internal OpenAI concurrency cap (default five) and reduce it on actual 429/5xx or tool capacity signals. Do not infer built-in tool capacity from a direct Images API account tier. Concurrency is not a guaranteed images-per-minute number.
- For `N` main cuts, plan exactly `N` OpenAI first-attempt stills, select exactly `N` starts after QC, and keep the Higgsfield image count at zero. Do not create a second provider lane or duplicate every cut for comparison.
- A provider lane may use the same approved character or product reference as conditioning input across cuts, but its generated scene output may not be reused. Register each QC-passing image with `scripts/streaming_cut_pipeline.py accept-start`: atomically compare against all already selected hashes, perceptual hashes and the reviewed rolling contact sheet. Reject a duplicate later cut and keep unrelated first attempts running; replacement remains subject to the paid-retry boundary. At final promotion run `scripts/check_selected_start_diversity.py --output <run>/qc/selected-start-diversity.json <selected-starts...>` on the complete set and inspect its full contact sheet. This final audit does not delay earlier eligible Kling submissions.
- Every candidate receives a unique ledger key such as `<plan>:cut-07:image:built-in-image-gen`. Record `provider`, `route`, built-in result path, `output_hash`, `qc_state`, and `selected_for_kling`; a rejected candidate remains traceable and is never silently overwritten.
- If built-in `image_gen` is unavailable, mark the route `unavailable` and stop or quarantine the affected cut. Never substitute Higgsfield image generation, direct Images API, ImageGen CLI, or a local still-to-video path.

Run `scripts/image_lane_plan.py --cut-count N --mode openai_only` during preflight to write the planned candidate count, selected-start count, OpenAI cap, and `higgsfield_image_jobs: 0` into the manifest.

## Risk router

The generation constructions below apply only to `ai_generation`. For `existing_clean_edit`, use the source-selection and edit-risk rules in `references/existing-clean-edit-workflow.md` and never convert a missing visual beat into an AI generation job.

Mark these as `high` by default:

- internal organs, anatomy, excretion, disease, pain close-ups, body before/after, or groin-adjacent framing;
- readable products, labels, logos, claims, evidence, numbers, prices, certificates, reviews, or UI;
- hands/fingers as the main action or complex multi-object interactions.

Use these safe constructions while keeping the Higgsfield Kling video route mandatory:

- **Universal scene life:** design motion from the setting instead of copying temple props into unrelated scenes. Indoor scenes may use hands, steam, fabric, curtains, reflections, shifting daylight, or focus changes; outdoor scenes may use people, foliage, mist, weather, shadows, or depth parallax created by genuine camera travel; product-use scenes may use pouring, stirring, dissolving, condensation, powder flow, packaging handling, or contact shadows; character scenes may use breathing, gaze, posture, hair, clothing, or purposeful action. Use only motions that support the script and composition. Do not animate every object, add random crowds, or let environmental motion cross through the product.
- **Body/anatomy:** show a clothed body, keep groin and reproductive anatomy outside frame, use a closed abstract surface metaphor when needed, and prohibit open torso, surgical cutaway, exposed pelvis, nudity, gore, and genital-like geometry. Redesign the still or action until a safe Higgsfield motion pilot is possible. If the pilot fails, quarantine the cut; never replace it with local motion.
- **Readable product:** if the beat is product reveal/use/proof/offer/CTA, require the exact designated product. Prefer an approved-product-reference image edit that creates the complete scene with the real box/stick geometry already integrated, then animate that single start image through Higgsfield. Never prompt a generic packet or blank substitute. Use a product-free placement plate plus official-pixel composite only when exact readable fine text is necessary and the full integration gate is feasible. Minor fine-text softness is acceptable when the user allows it, but a changed brand, colorway, package type, silhouette, box/stick relationship, or invented competing label is a hard failure.
- **Text/claims/evidence/CTA:** generate a text-free Higgsfield motion plate with meaningful camera, actor, liquid, foliage, light, or environmental motion. Add verified copy directly in deterministic post. A static background with local text animation is not sufficient.
- **Liquid, powder, swelling, spreading, assembly, filling:** make the genuine transformation the primary Higgsfield motion. When deformation is unnecessary, specify natural actor, object, camera, light, foliage, mist, fabric, or surface motion so the cut remains a real generated video.

## Hard model locks

This entire section applies only to `ai_generation`. `existing_clean_edit` must have zero image-provider and Higgsfield/Kling submissions.

### Per-cut images

Use only the built-in OpenAI `image_gen` tool through `$imagegen` default mode. The plan must contain `image_generation_mode: "openai_only"`, `image_generation_route: "built_in_image_gen"`, `image_candidates_per_cut: 1`, `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, and `image_cli_jobs: 0`. Any Higgsfield image provider, `gpt_image_2` job, `higgsfield_only`, `hybrid_parallel`, direct Images API, or ImageGen CLI value is a blocking failure for a new or materially remapped plan.

Use `quality: high` for the product master, `product_presence: required`, or high-risk cuts; `quality: low` only for low/medium-risk product-independent cuts; `resolution: 1k` (or the approved ratio-compatible GPT Image size); one distinct prompt per scene; no end image. The selected start image must pass product/composition QC and the cross-cut diversity gate before Kling submission. Never feed the same selected image path or SHA-256 to more than one cut, even with different motion prompts.

### Generated video through Higgsfield

Immediately before cost estimation and submission verify:

- `display_name: Kling v3.0`
- `job_set_type: kling3_0`

Use only base `kling3_0`, the approved `std`, `pro`, or `4k` mode, sound off unless separately approved, one approved action-ready start image, no end image, and one first attempt at the cut's planned `3.0 s`, `4.0 s`, or `5.0 s`. Verify returned identifiers after submission. Never fall back to another Kling model.

Save provider provenance, job ID or built-in tool result path, returned model identifiers, route, candidate QC result, selected/rejected state, and downloaded output for every still candidate. A selected file without this provenance cannot be promoted to a Kling start image or `videos/final`.

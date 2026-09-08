# Clean Visual Reference / Single-Keyframe Contract

Use this reference only while building or materially remapping a plan. The output is script-led and clean-plate oriented: use the finished reference video only as a visual-expression reference, never as a completed edit to reproduce, a pixel-for-pixel copy, or a start/end-frame interpolation target. For `자동모드` timing, reserve staging, adaptive still quality, tiered review, and duplicate-credit protection, also read `performance-optimized-execution.md`.

Mode boundary: this document's generation schema, prompts, model locks, adaptive three/four/five-second generated-motion requirements, candidate lanes, product-master generation, and provider QC apply only when `video_source_mode: "ai_generation"`. When `video_source_mode: "existing_clean_edit"`, use only sections 1 and 2 for reference technique analysis, then follow `existing-clean-edit-workflow.md` for the source-plan schema, storage, QC, CapCut edit, and completion. Never invoke ImageGen, GPT Image, Higgsfield, Kling, generative fill, or a synthetic-motion fallback in that mode.

## 0. User-specified reference-use mode

When the user provides the clean-reference prompt, set the plan-level value:

```json
{
  "schema_version": 4,
  "reference_use_mode": "clean_visual_reference_only",
  "selected_start_reuse_policy": "forbid_across_cuts",
  "semantic_visual_contract": "literal_visual_proof_v1",
  "duration_policy": "adaptive_3_4_5_seconds",
  "semantic_retry_policy": {
    "paid_retries": false,
    "authorized_in_gate_1": false,
    "max_semantic_retries_total": 0,
    "semantic_retry_budget_credits": 0
  }
}
```

Only the following reference layers may influence generation:

```json
{
  "style_reference": "reference style, atmosphere, texture, contrast, palette, lighting, character/skin rendering, visual density, mise-en-scene",
  "expression_reference": "hand/product application, skin-state depiction, surface/internal macro, Before/After separation, person/product/skin interaction",
  "composition_reference": "shot scale, frontal/diagonal/side angle, hand/product placement, face/skin framing, subject/background layout, depth and perspective",
  "native_camera_motion": "physically plausible within-scene camera move only",
  "editing_effects": "forbidden"
}
```

`native_camera_motion` may describe a slow physical push-in, a short follow of a hand or product, a natural focus pull, or a slow viewpoint change. It may not describe digital zoom, crop animation, transition, speed change, shake effect, rapid cut connection, or any other post-production movement. The literal value of `editing_effects` must be `forbidden` for every cut.

Replace all literal source identity with the designated target: reference product, logo, phrase, disease, foot, fungus, review, red X, icon, banner, and UI never survive into the target clip. Generate advertising Before, product-use, and After as separate independent clean clips, with one comparison state and one principal action per clip. Do not generate a Before-identity-to-After-identity transformation inside one clip. A script-required causal mechanism may show the same subject moving from its declared start state through an action to an end state when that progression is the literal proof.

Clean output means silent, full-bleed footage with no captions, text, cards, overlays, music, voice, sound effects, borders, letterboxing, final-ad frame, or sticker-like product composite. Deterministic post is limited to technical normalization and unavoidable natural product restoration/tracking; it must not add editing effects or ad graphics.

## 1. Technique bank

Analyze the reference at native speed. For each usable cut record:

- source in/out, duration, one representative semantic moment, and clean boundary;
- communicative function and persuasion role;
- angle, perspective, crop, shot scale, subject/frame ratio, primary-subject coordinates, dominant silhouette, layer order, negative-space map, and broad motion direction;
- initial state, emphasis device, acting subject/object, trigger, transformation operator, propagation/reveal rule, after-state, phase timing, script-bearing primary motion, secondary environmental motion, camera motion, and static anchors;
- dominant medium, secondary layers, line quality, shading, palette, texture, realism, lighting, and compositing logic;
- captions, text, product, logos, UI, boxes, black bars, props, and transitions as exclusions or deterministic post layers.
- `style_reference`, `expression_reference`, `composition_reference`, `native_camera_motion`, and `editing_effects: "forbidden"` as separate target-cut fields.

Use one source cut as a technique record, not as a required target index. Leave unused techniques unassigned and reuse compatible ones only with a new script-led substitution.

## 2. Functional mapping

For every target beat:

1. classify `hook`, `problem`, `mechanism`, `contrast`, `proof`, `authority`, `relief`, `value`, `objection`, or `cta`;
2. choose the best technique by function, causal-operator compatibility, composition, medium/intensity, then pacing;
3. map source roles to target subject, condition, object/product, action, evidence, environment, and outcome;
4. preserve the compatible composition scaffold and causal sequence while replacing all literal source nouns;
5. record confidence and ask only when competing choices materially change the result.

For a user-designated frame or effect, apply strict composition/effect locking and read `effect-translation-interview.md`.

## 3. Cut count and plan schema

Estimate narration from supplied audio or a stated Korean reading rate. First split every sentence into meaning-bearing `semantic_units`. Group only units that one named subject/action/result chain can visibly prove, then assign `3.0 s` to `single_state_or_action`, `4.0 s` to `two_step_action`, or `5.0 s` to `causal_transformation`. Split again when five seconds cannot prove all units. Never inherit the reference count, force every cut to three seconds, force a round number, or pad. New plans should keep main jobs in `cuts[]`, optional alternates in `reserve_cuts[]`, and record `main_cut_count`, `reserve_cut_count`, and `reserve_policy: "on_demand_after_main_qc"`; `planned_cut_count` may remain as a legacy alias for schema-version-1 runs.

Store the complete plan as JSON. Each cut must contain:

```json
{
  "cut": 1,
  "script": "...",
  "style_reference": "...",
  "expression_reference": "...",
  "composition_reference": "...",
  "native_camera_motion": "...",
  "editing_effects": "forbidden",
  "visual_job": "one viewer takeaway",
  "reference_technique": "source cut/timestamp and operator",
  "composition": "angle, crop, placement, layers, motion direction",
  "medium": "dominant and secondary medium",
  "must_show": "one hard visual requirement",
  "semantic_units": [
    {
      "id": "1a",
      "text": "one exact meaning-bearing clause",
      "required_visual_evidence": "the concrete visible evidence that proves this clause"
    }
  ],
  "visual_proof": {
    "subject": "the same named subject throughout the proof",
    "start_state": "visible condition before the action",
    "visible_action": "literal action that proves the line",
    "end_state": "visible completed result",
    "causal_link": "how the viewer sees the action cause the result",
    "success_frame": "unmistakable frame that proves completion",
    "forbidden_shortcuts": ["prop-only or icon-only substitute"]
  },
  "hard_exclusions": ["cut-specific exclusion, max three"],
  "risk_level": "high|medium|low",
  "image_quality": "high|low",
  "risk_reason": "...",
  "safe_template": "...",
  "motion_design": {
    "primary_motion": "named subject + visible action that carries the script beat",
    "secondary_motion": "setting-specific environmental or supporting motion",
    "camera_motion": "specific move and purpose, or locked with an explicit reason",
    "static_anchors": ["identity and geometry that must remain stable"],
    "motion_phases": "timed establish -> literal action -> completed result, ending at duration_seconds"
  },
  "image_prompt": "...",
  "motion_prompt": "...",
  "duration_class": "single_state_or_action|two_step_action|causal_transformation",
  "duration_seconds": 3.0,
  "duration_reason": "why this proof requires exactly 3.0, 4.0, or 5.0 seconds",
  "route": "Higgsfield Kling v3.0 — start image only",
  "deterministic_post": [],
  "cost": "..."
}
```

The English image prompt begins with `SCRIPT FUNCTION LOCK`, `CLEAN VISUAL REFERENCE LOCK`, `STYLE REFERENCE LOCK`, `EXPRESSION REFERENCE LOCK`, `COMPOSITION CLASS LOCK`, `SEMANTIC SUBSTITUTION LOCK`, and `VISUAL MEDIUM LOCK`. It states the representative moment, style/atmosphere, expression method, composition class, permitted native camera behavior, target substitutions, final state, palette, texture, approved anchors, and cut-specific safety constraints. It explicitly excludes the finished reference edit, source product/identity, text, disease, foot/fungus, review, red X, UI, and all editing effects. Append the shared global full-bleed/no-text/no-box exclusions once at submission time rather than repeating them in chat.

The Korean Higgsfield motion instruction realizes the complete `motion_design` and `visual_proof`: the named subject begins in the declared start state, performs the literal script-bearing action, and reaches the unmistakable end state within the exact planned three-, four-, or five-second phase timing. It also includes one scene-appropriate secondary motion, a purposeful camera move or justified locked camera, fixed anchors, and prohibited unobserved motion. Vague wording such as `natural motion`, `subtle movement`, or `camera movement` is invalid. For trigger effects, time-code hold -> action -> trigger -> propagation -> settle.

Use literal-first evidence. A package, bottle, glass, icon, arrow, label, pose, or abstract metaphor may support a beat but cannot replace an available action or outcome. The start still must be action-ready immediately before the visible action, not an already completed result. For example, consumption requires the substance to cross the lips and the swallow to complete; relief requires a clearly relaxed end-state performance; dehydration requires the same material to lose moisture, darken/crack, and lodge; cleansing requires the same accumulated material to exit and leave a visibly clear channel. These examples define evidence quality only and do not transfer any company, product, character, or art style.

For clean-reference mode, the Korean motion instruction must describe only the independent clip's single state and single action plus allowed native camera behavior. State `editing_effects: forbidden` in the plan and exclude edit zoom, transition, fast cut, speed change, shake effect, captions, cards, UI, music, voice, and sound effects from both the image and motion prompts.

## 4. Anchor and product contract

- Keep the approved actor/character design consistent in identity, silhouette, age coding, hair, wardrobe, linework, palette, and texture.
- Keep the exact designated company/product identity wherever any product-like object is visible. Never use a generic sachet, blank packet, tea bag, lookalike box, or another product.
- For product reveal/use/proof/CTA beats, prefer an approved-product-reference image edit that builds the complete scene around the official box/stick geometry before Higgsfield motion. Use a clean placement plate and official-pixel composite only when exact readable fine text is necessary and natural integration is feasible.
- Do not force a flat product overlay over an already generated object. Never ask a model to invent readable certification, price, claim, review, statistic, UI, or legal text.

## 5. Safety templates

### Body and digestive topics

- Prefer a clothed front or three-quarter torso with the groin outside frame.
- Show a closed, simplified light/ribbon overlay on clothing rather than an opened or transparent body cavity.
- Prohibit open torso, surgical cutaway, exposed pelvis/groin, reproductive anatomy, nudity, gore, genital-like geometry, and visceral realism.
- Redesign static rhythm, discomfort, and organ-location scenes into safe clothed acting, surface metaphors, or abstract material motion that Higgsfield can animate. Never replace a failed or risky cut with local mask/reveal/zoom.

### Product, evidence, and CTA

- Require the exact designated product for reveal, handling, mixing, consumption, proof, social-proof, offer, stock-up, purchase-limit, and CTA beats.
- Prefer scene-native official-product-reference generation. Minor fine-print softness or brief shimmer is acceptable only when the brand, colorway, silhouette, and box/stick structure remain unmistakable.
- Use official product pixels in deterministic post only when a natural perspective/contact/occlusion/lighting/motion match is possible.
- Do not generate text containers, blank panels, fake UI, cards, labels, or pseudo-text.
- Add verified claim/offer copy deterministically. Do not replace the required product with a blank or unbranded prop merely to avoid label distortion.

### Material transformation

- Use Higgsfield Kling for script-critical spreading, swelling, dissolving, filling, flowing, or assembly.
- When deformation is not necessary, require natural actor, object, camera, light, foliage, mist, fabric, or surface motion in the Higgsfield output. Local zoom, pan, parallax, crop, mask, or layer reveal cannot replace the generated motion base.

## 6. Universal scene-liveness contract

- Apply this contract to every future setting. Mist, visitors, foliage, changing light, and a temple push-in are examples of one successful temple scene, not mandatory props for unrelated videos.
- Give every cut a script-bearing primary motion with a named subject and visible verb. Camera travel alone is not the primary motion.
- Add one restrained secondary motion that belongs to the depicted space: people, hands, steam, liquid, powder, fabric, foliage, weather, reflections, shadows, focus, light, or another physically plausible environmental response.
- Specify a purposeful camera move such as push-in, pull-back, track, orbit, tilt, crane, rack focus, or restrained handheld drift. A locked camera is valid only with an explicit compositional reason and sufficient primary and secondary motion.
- Declare static anchors whose identity or geometry cannot drift: approved product, label block, face, hands, glass, architectural lines, table plane, or horizon.
- Stage motion in phases across the exact planned three, four, or five seconds so the frame has an initial state, visible progression, completed result, and success frame. Do not animate every layer at once or introduce unrelated people, props, particles, or weather.
- Reject motion that is only compression shimmer, edge wobble, random micro-jitter, local pan/zoom, parallax, or animated text. Start, 25%, middle, 75%, and end checkpoints must show the planned causal or spatial progression while static anchors remain stable for schema-version-4 cuts.

## 7. Candidate-still and motion contract

- Every new or resumed future image action uses `image_generation_mode: "openai_only"` and `image_generation_route: "built_in_image_gen"`. Create stills only with the built-in OpenAI `image_gen` tool through `$imagegen` default mode; record `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, and `image_cli_jobs: 0`. Never use Higgsfield, direct Images API, or ImageGen CLI for still images. Historical records using those routes remain read-only provenance.
- The built-in `image_gen` route uses one call per distinct scene. Do not switch to CLI/API batching or use a multi-output request to hide distinct prompts.
- Select exactly one QC-passing OpenAI start still per cut. Record the candidate's provider, route, model, quality, output hash, and selected/rejected state. Use `high` for the master, product-required, or high-risk stills and `low` only for low/medium-risk product-independent stills.
- Exactly one Higgsfield start-image-only base `Kling v3.0` / `kling3_0` first attempt for every approved cut at its planned `3.0 s`, `4.0 s`, or `5.0 s`, using the selected still only.
- No end image, image pair, interpolation target, motion-control pair, fallback model, sound, transition, or outro.
- Every candidate and final video must retain provider provenance, job ID or built-in result path, returned model identifiers, output file, and QC state. Missing or failed jobs remain quarantined; never create a local-only fallback.
- Deterministic local post is allowed only after the Higgsfield output exists and only for optional official product restoration/tracking, verified text/evidence/CTA, occlusion mattes, color matching, normalization, and assembly. Do not add a second product when the start image already contains the exact scene-native product.
- Full-bleed only. Exclude generated letters, digits, symbols, pseudo-text, labels, logos, claims, prices, reviews, UI, cards, panels, banners, borders, black bars, and unused margins.

## 8. QC decision contract

Hard-fail only material problems:

- script meaning, safety/anatomy, product/claim/text integrity, model/input contract, ratio/duration/audio/border/transition, gross composition drift, or wrong medium;
- any planned semantic unit lacks a visible evidence frame; the literal action, start state, end state, causal link, or success frame is missing; a prop/symbol substitutes for an available action; the subject swaps mid-cause; or the result appears without its stated cause;
- more than the plan-authorized candidate count, more than one selected start still, or any end-image conditioning;
- a local-only MP4, still-to-video pan/zoom, parallax, mask reveal, or frozen image is presented as a completed video cut;
- `motion_design` or `visual_proof` is missing or vague; the primary or secondary motion is not visibly present; the five semantic checkpoints show no meaningful progression; the camera move contradicts the plan; or a declared static anchor drifts, deforms, intersects, or duplicates;
- `reference_use_mode` is missing or not `clean_visual_reference_only` for a user-requested clean-reference plan; any required per-cut reference field is missing; `editing_effects` is not exactly `forbidden`; or the prompt hides a forbidden edit effect inside a native-camera description;
- a Before, product-use, or After target merges multiple states or asks one clip to transform Before into After;
- a product, evidence, CTA, or anatomy-safe cut lacks a meaningful Higgsfield actor/object/camera/environment motion base;
- a product-related beat shows a generic, unbranded, tea-bag-like, wrong-color, wrong-silhouette, or wrong-company product.

Accept small differences in palette, watercolor density, lighting, background props, camera position, compression softness, fine-print blur, and brief edge shimmer when the cut still communicates correctly and preserves the approved composition class, medium, and unmistakable exact-product identity.

Quarantine a cut-local failure and continue unrelated approved first attempts. Stop only for a systemic product/master/model/tool failure or the same systematic visual failure across at least two pilot outputs. A failed cut never authorizes a paid retry by itself. One narrow cut-local semantic retry is allowed only while both the explicitly Gate 1-approved `max_semantic_retries_total` and `semantic_retry_budget_credits` retain capacity; otherwise wait at Gate 3. A provider timeout or lost response is `submitted_unknown`: reconcile the provider job and local submission ledger before submitting anything with the same key.

For every schema-version-4 output, build a five-checkpoint semantic review and run `scripts/validate_semantic_qc.py`. Promotion is fail-closed until every `semantic_units[].id` has at least one evidence frame and all proof checks pass. Technical media QC, attractive style, motion amount, or reference similarity cannot override a failed semantic unit.

---
name: ai-video-reference-replication
description: Create reference-based ecommerce ads with AI visuals or supplied clean footage, optional reference/user-selected TTS, and editable CapCut delivery. Ask source mode and script mode, then collect ratio, TTS/edit scope, voice choice, and editing category early. In planning mode, always determine whether the user has a script or draft; use it as the primary planning input when present and create a new script only when absent. Honor an earlier request to finish editing as end-to-end delegation with the current reference voice unless another voice is specified. Carry answers through production without repeated execution-mode questions. Preserve exact product/source identity, child-skill quality and retry limits, and safe project saving.
---

## 공유 플러그인 실행 경로

이 문서가 들어 있는 `skills`의 상위 폴더를 `PLUGIN_ROOT`로 확인하고, 먼저 `../../references/recipient-runtime.md`를 읽는다. `${PLUGIN_ROOT}`는 현재 설치된 이 플러그인의 절대 경로로, `${VIDEO_PRODUCT_LIBRARY_ROOT}`와 `${CAPCUT_AUTOMATION_ROOT}`는 수신자 환경의 경로로 해석한다. 하위 스킬은 이 플러그인 안의 형제 폴더를 우선 사용한다. 플러그인 제작·수정·공유 요청은 영상 제작 인터뷰나 유료 생성, 앱 종료를 시작하지 않는다.


# 영상 생성

## 시작 표시와 버전

- 현재 자동화 버전: `1.8`
- 실제 영상 제작을 시작하면 `assets/automation-version.json`을 읽고 `버전 v{automationVersion} 업데이트 된 시각 {displayUpdatedAtKst}`를 먼저 표시한다. 유지보수 요청에서는 제작 인터뷰를 시작하지 않는다.


## 스킬 수정과 배포 완료 기준

소유자는 2026-09-08 이 플러그인의 스킬 수정 요청에 공개 배포 반영까지 포함하도록 명시적으로 지정했다. 소유자 환경에서 이 스킬 또는 포함된 지원 스킬을 수정할 때는 `../../references/skill-maintenance.md`를 읽고 원본 수정 → 검증 → 로컬 설치 → 공개 릴리스 → 공개 파일 확인까지 완료한다. 로컬 수정만으로 완료를 보고하거나 같은 대상의 배포 승인을 다시 묻지 않는다. 최신 사용자 지시가 로컬 시험만 요청하거나 배포를 금지하면 그 제한을 우선한다. 받는 사람의 환경에 소유자의 배포 권한을 적용하지 않는다.

## Reference structure and mandatory script confirmation

Every newly written or rewritten ad script must preserve the supplied reference video's full spoken-script structure: sentence/semantic-unit order, persuasive role, paragraph breaks, hook type, reveal timing, argument transitions, CTA placement, expression strength, and spoken rhythm. Transcribe the complete reference first and keep an ordered one-to-one internal mapping from its exact units to the target units. Use the designated product's facts and causal logic inside those same structural positions. Prior scripts supply product logic, never a replacement outline. Do not invent a generic outline, reorder the reference to fit an old script, or shorten it to a default 30–40 seconds. Resolve an actual product-logic/structure conflict with a focused question rather than silently changing either.

Always show the complete exact target script and wait for the user's explicit confirmation before Gate 0.5, cut planning, prompts, image/video generation (including native talking-head speech), separate TTS, or CapCut editing. This applies to both source modes, every production scope, direct/transcribed scripts, and every new or revised draft. A user message explicitly designating the exact supplied text as the confirmed final script can serve as confirmation; choosing a mode, requesting all editing, silence, or merely supplying a draft cannot. Broad end-to-end delegation never waives this gate.

Set `script_approval.required: true` and `status: awaiting_script_confirmation` until confirmed. Bind the approval receipt to the exact script path/SHA-256, approval quotation, and timestamp; link it in intake and the workflow manifest. A script change invalidates its prior receipt: show the whole revised script and obtain confirmation again, preserving unrelated intake answers. Keep old `planned_under_end_to_end_delegation` records as history only; before further production, require actual confirmation of the current script. After confirmation resume the already authorized scope without repeating the scope interview.

## Core contract

- Higgsfield video generation is Kling-only for every task and retry, including direct edits of user-supplied videos and requests to preserve exact source identity or motion. Never use Seedance (`seedance_*`) or any other non-Kling video model, and never invent a `video_edit` or source-preservation exception. Keep this skill's existing `kling3_0` version lock. Check the requested model before submission and the returned model afterward; if the supported Kling route cannot satisfy the source-preservation requirements, report the limitation and stop that generation instead of substituting another model. Previously generated non-Kling candidates remain traceable in review records and must not be promoted as Kling-compliant final clips.

- Keep `video_source_mode` independent from `intake_mode` and `execution_mode`. The three choices answer, respectively, where the visual footage comes from, how the script is prepared, and how much of the approved plan runs automatically.
- Read `references/production-intake.md` for the early ratio, TTS/edit scope, voice, and category interview. Its recorded end-to-end request is the execution authorization for the selected scope; do not ask Gate 1B again after that choice. A skill-maintenance request never starts production.
- Let the target script determine meaning, order, duration estimate, and cut count.
- In every future `ai_generation` job, for every company and product, convert each script sentence into explicit `semantic_units` and a literal `visual_proof` chain: named subject -> visible start state -> visible action -> visible end state -> causal link -> unmistakable success frame. Style, character continuity, attractive composition, props, icons, arrows, bottles, packages, or abstract metaphors never substitute for the action or result the sentence actually states.
- After Gate 0.5 has produced a hash-bound `visual_detail_contract`, infer the most direct filmable proof for remaining low-impact choices without asking the user to describe every cut. Never infer a high-impact variable the user reserved for confirmation, including primary subject or body area, character identity, problem-state intensity, product-use action, material transformation, After-state degree, supporting characters, evidence setting, or CTA composition. Ask when two materially different literal interpretations remain. When a real action can prove the line, show the action itself: ingestion crosses the lips and completes a swallow, relief appears as a clearly relaxed character state, dehydration visibly dries/cracks/lodges the same material, and cleansing visibly removes the same accumulated material and leaves a clear end state. These are examples of the rule, not product facts or reusable props.
- Give the proof enough screen time automatically: `3.0 s` for one state or one action, `4.0 s` for a two-step action, and `5.0 s` for a causal transformation or mechanism. Split the sentence into additional cuts when even five seconds cannot make every semantic unit visible. Never compress a multi-stage claim into a decorative three-second symbol shot.
- Treat the reference as a clean-visual-reference bank: style/atmosphere -> expression method -> composition class -> physically plausible native camera motion -> target substitution. Never treat the finished edit as a shot list to reproduce.
- Generate TTS only when the early scope includes it. Honor `reference_voice` or `user_voice`; an earlier end-to-end request defaults to the current job's reference voice only when no voice override exists. `clean_visual_reference_only` does not disable the current reference as a voice source or authorize a different old clone.
- Preserve the reference's style, texture, palette, lighting, visual density, expression method, composition type, subject interaction, and broad native camera behavior only. Recompose each target for the new script and product. Never copy source identity, product, text, UI, boxes, black bars, edit effects, or irrelevant props.
- In `ai_generation`, use one or more explicitly planned candidate stills per cut only when the plan's image-generation mode requests parallel candidates. Select exactly one QC-passing start still per cut for Kling; never create or send an end image.
- In every future `ai_generation` job, create all still images exclusively with the built-in OpenAI `image_gen` tool through the `$imagegen` skill's default built-in mode. Set `image_generation_mode: "openai_only"`, `image_generation_route: "built_in_image_gen"`, keep `image_candidates_per_cut: 1` for the approved first attempt, and record `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, and `image_cli_jobs: 0`. Never call or plan Higgsfield `gpt_image_2`, `higgsfield_only`, `hybrid_parallel`, a direct Images API, or the ImageGen fallback CLI. If built-in `image_gen` is unavailable, stop and report the blocker; do not substitute another still provider. Higgsfield remains permitted only for the separately approved Kling motion-video stage.
- In `ai_generation`, never reuse one selected start image, an exact copy, a re-encoded near-duplicate, or the same base composition across two different main cuts. Character and product continuity do not justify scene reuse. Give every cut a cut-specific setting/action/shot-scale/camera-angle design, then prove selected-start diversity before any Kling submission.
- In `existing_clean_edit`, use only user-provided clean footage registered under the exact company/product. Never invoke AI image generation, AI video generation, Higgsfield, Kling, or a local synthetic-motion substitute. Continue source QC and the editing/TTS/caption branches actually selected in the early production scope.
- Preserve the exact user-designated company and product whenever a beat shows product recognition, handling, mixing, consumption, proof, offer, social proof, or CTA. Never replace it with a generic sachet, unbranded packet, tea bag, lookalike box, or another product. In `ai_generation`, prefer a scene-native reference-conditioned still built from the approved official product asset so the product belongs to the photographed or illustrated scene from the start. Use official-pixel compositing only when it can be integrated naturally; never paste a flat asset over an existing product, prop, hand, glass, or shadow.
- In `ai_generation`, generate full-bleed scenes without text, pseudo-text, cards, panels, fake UI, borders, letterboxing, transitions, or outros.
- In `ai_generation`, generate every final motion cut through Higgsfield Kling. A GPT Image candidate is an input still only; a local-only MP4, still-to-video pan/zoom, parallax, mask reveal, or frozen image never satisfies a video cut.
- In `ai_generation`, treat visible scene life as a universal per-cut requirement, not a temple-specific style. Every cut must have a planned script-bearing primary motion, a scene-appropriate secondary environmental motion, and either a purposeful camera move or an explicit locked-camera reason. Protect named static anchors such as the approved product, face, hands, architecture, glass, and horizon from drift or deformation. Temple mist, visitors, foliage, changing light, and a push-in are examples for one setting only; choose equivalent human, object, material, atmospheric, lighting, reflection, fabric, shadow, or camera motion for the actual setting of each future video.
- In `ai_generation`, allow deterministic local post only after a valid Higgsfield motion base exists, and only for optional scene-integrated official product restoration/tracking, verified text/evidence/CTA, occlusion mattes, perspective and contact-shadow matching, color matching, normalization, and assembly. Do not force an overlay when the scene-native reference-conditioned product is already identifiable. A rectangular sticker-like overlay, doubled silhouette, floating package, exposed cleanup bar, or unmatched plane is forbidden.
- If Higgsfield generation fails or is unsafe in `ai_generation`, quarantine or redesign that cut. Never fall back to a local motion substitute.

Before creating any new `ai_generation` run directory, read `references/output-folder-organization.md` and initialize `생성 결과물/YYYY-MM-DD/작업 기록/<한글 작업명>` with `scripts/organize_result_folders.py --init-run`. The user-facing daily clean directory is always `생성 결과물/YYYY-MM-DD/생성 클린본`. Same-day additional scenes and approved reserve clips append to that same folder; never create separate user-facing clean directories by batch, model, scene type, version, or cut count. Keep independent job/QC records inside `작업 기록` and use Korean names for the visible planning, audio, and edit folders. This is the default for future company/product jobs; reorganize another existing product only when requested.

Read `references/finalized-script-visual-detail-interview.md` completely every time the target script first becomes exact or is materially revised, then run Gate 0.5. Read `references/reference-replication-contract.md` completely only when building or materially remapping a plan. When resuming an approved run with a traceable plan, source pack, manifest, and QC records, load those records and continue from the unresolved gate without repeating page or reference forensics. Read `references/effect-translation-interview.md` only when the user designates a particular effect or frame sequence. Read `references/performance-optimized-execution.md` when `자동모드` is selected for `ai_generation` or the user asks to reduce generation time, missing outputs, or duplicate jobs.

Read `references/product-integration-qc.md` completely whenever any cut may show an official product master or product-derived overlay. Apply its product-necessity decision before prompting and its start/middle/end integration gate before promotion.

When `video_source_mode: "existing_clean_edit"` is selected, read `references/existing-clean-edit-workflow.md` completely before accepting or planning supplied clean clips. Use `scripts/store_clean_clips.py` for product-scoped immutable intake and its returned manifest as the only clip inventory for that run.

## Reference-use contract — clean visual reference only

This section applies only to `ai_generation`. When the user supplies the clean-reference instruction or asks for this level of reference use, create a new `schema_version: 4` plan, set the plan-level fields `reference_use_mode: "clean_visual_reference_only"`, `selected_start_reuse_policy: "forbid_across_cuts"`, `semantic_visual_contract: "literal_visual_proof_v1"`, and `duration_policy: "adaptive_3_4_5_seconds"`, and apply the following contract to every cut. Existing schema-version-1 through schema-version-3 runs remain resumable as legacy plans without rewriting their historical records; inspect them without strict-schema validation unless they are materially remapped.

### Allowed reference inputs

Use only these three reference layers:

1. `style_reference`: the reference's illustration/photographic style, atmosphere, texture, contrast, color, lighting, character and skin rendering, exaggerated-but-intuitive visual density, and overall mise-en-scène;
2. `expression_reference`: the way a hand holds and applies a product, hand/product placement, provocative and direct skin-state depiction, skin-surface/internal macro expansion, Before/After separation, and person/product/skin interaction;
3. `composition_reference`: shot scale, close-up/macro/medium distance, frontal/diagonal/side angle, hand/product position, face/skin framing, subject/background placement, depth, and perspective class.

Record the permitted physical camera behavior separately as `native_camera_motion`. Allow only a real within-scene camera move such as a slow push-in, short hand/product follow, natural focus pull, or slow viewpoint change. Treat digital zoom, edit zoom, crop animation, transition, speed change, shake effect, and rapid cut connection as forbidden editing effects.

### Mandatory clean-plate substitutions

- Replace every literal reference product, logo, phrase, disease, foot, fungus, review, red X, icon, banner, and UI element with the designated company/product and the approved target condition.
- Generate Before, product-use, and After as separate independent clean clips. Before shows red, irritated, painful, cracked skin; product-use shows the exact product being applied; After shows clean, smooth improved skin.
- Keep one comparison state and one principal action per clip. Do not make an advertising Before identity transform into its After identity inside one generated clip. A five-second causal mechanism may show the same subject progressing from its declared start state through the script-required action to its end state when that progression itself is the sentence's proof.
- Generate silent, full-bleed clips with no captions, text, cards, overlays, music, voice, sound effects, borders, letterboxing, final-ad screen, or sticker-like product composite.
- Under this clean-reference contract, deterministic post is limited to technical normalization and genuinely scene-integrated product restoration when unavoidable; do not add edit zooms, transitions, captions, or advertising graphics during generation.

### Required per-cut record

Every newly planned cut must record these fields separately:

```json
{
  "style_reference": "...",
  "expression_reference": "...",
  "composition_reference": "...",
  "native_camera_motion": "...",
  "editing_effects": "forbidden"
}
```

`editing_effects` must equal the literal string `forbidden`. Do not hide edit zooms, transitions, speed changes, shakes, captions, or overlays inside `native_camera_motion` or a generic motion description.

Create a plan-level `reference_profile` once, then let the five per-cut fields contain short profile IDs plus a cut-specific delta. The fields are audit/provenance records, not a reason to repeat a long reference analysis or invoke a separate validation model for every cut.

```json
{
  "reference_profile": {
    "style": "reference_style_v1",
    "expression": "skin_state_and_application_v1",
    "composition": "macro_face_diagonal_v1",
    "native_camera_motion": "slow_physical_push_or_focus_pull_v1"
  }
}
```

## 질문 표시 — 채팅 번호 목록

이 플러그인의 사용자 질문은 카드가 아닌 일반 채팅에 남는 번호 목록으로 표시한다. Gate -1, Gate 0, 초반 제작 인터뷰, 시각 표현 인터뷰, 실행 방식 선택과 이 워크플로에서 호출하는 하위 스킬에 동일하게 적용한다.

- 질문 문장 다음에 빈 줄을 두고 `1.`, `2.` 형식으로 모든 선택지를 같은 최종 답변에 표시한다. 각 항목에는 선택지 이름과 사용자가 차이를 이해할 수 있는 짧은 설명을 쓴다. 이미 정해진 메뉴 문구·번호·순서는 유지한다.
- 질문 카드, 선택 위젯, 비동기 입력 UI를 기본값이나 카드가 사라졌을 때의 재시도 경로로 사용하지 않는다. `request_user_input`, `request_user_input_async` 같은 도구가 있다는 이유만으로 채팅 질문을 도구 호출로 바꾸지 않는다. “카드에서 선택해주세요” 또는 “번호로 답해주세요”만 남기고 선택지를 생략하지 않는다.
- 사용자가 현재 질문의 번호나 선택지 이름으로 답하면 그대로 접수한다. 첫 제작 방식과 대본 준비 방식은 각각 별도 턴으로 묻고, 이미 답한 항목을 반복하지 않는다. 기존 시각 표현 인터뷰의 통합 질문 범위는 유지하되 각 질문의 선택지도 채팅에 표시한다. 자유 입력이 필요한 업체명·대본·파일은 존재하지 않는 선택지를 만들어 번호를 붙이지 않는다.
- 표시 예시:

```text
영상 제작 방식을 선택해주세요.

1. AI 영상 생성
2. 클린본 기존 영상 편집
```

- 이 표시 선호는 시스템·개발자 지침을 덮어쓰지 않는다. 상위 지침이 채팅 선택형 질문을 명시적으로 금지하거나 특정 질문 도구를 강제하면 그 제한을 따르고, 요청한 표시 방식과의 충돌을 짧게 설명한다. 카드로 조용히 전환하거나 채팅 번호 목록이 보장된다고 보고하지 않는다. 이 예외는 카드가 제공된다는 사실만으로 발동하지 않는다.
- 표시 수정·진단 요청은 스킬 유지보수다. 실제 제작 인터뷰나 생성을 시작하거나 예시 번호를 사용자의 선택으로 기록하지 않는다.

## Gate -1 — video-source workflow mode

First record any current, affirmative request to finish through editing under `references/production-intake.md`; do not confuse a quoted example or a skill-edit request with a production instruction. This does not answer the separate visual-source question.

On every fresh invocation, determine the visual-source workflow before asking any other question. If the user has not already selected one in the current request, ask exactly this question and end the turn:

```text
영상 제작 방식을 선택해주세요.
1. AI 영상 생성
2. 클린본 기존 영상 편집
```

Do not combine company, product, reference, script-intake mode, URL, clean-clip upload, ratio, CapCut target, or execution-mode questions with this first workflow question. Record the normalized value as `video_source_mode: "ai_generation"` or `video_source_mode: "existing_clean_edit"`, together with the user's exact response. Do not ask again when the user already selected the mode in the current conversation.

`existing_clean_edit` removes AI still and motion generation. Continue script intake, reference analysis, source QC, and the TTS/edit branches selected in the early interview, using registered supplied clean clips as the authoritative visual source. A declined TTS/edit branch stays disabled.

## Gate 0 — script intake mode and required inputs

After Gate -1 is answered, determine the script-intake mode before asking for any project inputs. If the user has not already selected one in the current request, ask exactly this question and end the turn:

```text
어떤 방식으로 진행할까요?
1. 기획모드 — 업체명·제품명·레퍼런스 영상을 받은 뒤 대본·초안 보유 여부를 확인하고, 있으면 기획에 반영하며 없으면 제품 맞춤 대본부터 기획
2. 직접모드 — 사용자가 제공한 확정 대본으로 영상 제작
```

Do not combine company, product, reference, script, URL, clean-clip upload, ratio, or execution-mode questions with this script-intake question. Record the normalized value as `intake_mode: "planning"` or `intake_mode: "direct"`, together with the user's exact response. Do not ask again when the user already selected the mode in the current conversation.

### Early ratio, TTS, and edit interview

Before script planning or visual production, read `references/production-intake.md` completely and collect unresolved choices in this order: **영상 비율 → 제작 범위 → TTS 방식 → 편집 분야**. The production-scope menu has exactly two options, with these exact labels: **1. 영상 생성 + AI 내레이션(TTS) + CapCut 편집 / 2. 영상생성만**. Map them to `tts_and_edit` and `visuals_only` respectively; never add TTS-only or edit-only options to this menu. Option 2 disables both TTS and CapCut editing and skips their voice/category questions. TTS choices are **1. 레퍼런스 음성 / 2. 사용자 지정 음성**. Editing choices are **1. 건기식 / 2. 뷰티 / 3. 식품 / 4. 그외**. Ask only applicable, unanswered items using the numbered chat display contract above; do not merge these choice numbers with either mode menu above.

An earlier `편집까지 다 해줘` request already answers the scope and defaults the otherwise unspecified voice to the current reference. Skip those questions, preserve explicit voice/settings overrides, and collect only genuinely missing ratio/category/core inputs. Record normalized choices plus exact answers in `production-intake.json`. Once TTS/editing is selected, set `execution_mode: auto` for that selected scope and continue through its final deliverable without another mode, generation, TTS, or edit confirmation. Technical, source, and explicit user-reserved review boundaries remain in force.

### `planning` — 기획모드

Before the planning-script question, require exactly these three user-designated identity/reference inputs:

1. company name;
2. product name;
3. reference video.

Ask only for missing values and end the turn. Do not request a product-detail URL at this stage. The ratio and production choices were collected in the early interview; do not postpone them until script approval or ask them again. Never infer company or product names from filenames, URLs, folders, or prior projects.

After all three values are present, determine the planning-script source before transcript extraction, product-context discovery, prior-script discovery, or drafting. If the user has not already supplied a script/draft or explicitly asked for a new one in the current request, ask exactly this question and end the turn:

```text
기획에 사용할 대본이나 초안이 있나요?
1. 있어요 — 대본을 제공할게요
2. 없어요 — 제품 정보와 레퍼런스를 바탕으로 새로 작성해주세요
```

Record `planning_script_mode: "user_draft"` or `"generate_new"` together with the user's exact response. If the user selects `1` without including the actual text or file, ask only `기획에 사용할 대본이나 초안을 보내주세요.` and end the turn. If a script or draft was already supplied with the planning-mode request, record `user_draft` and do not repeat the menu. If the user already said to create a new script from the product and reference, record `generate_new` and do not repeat it. A broad end-to-end request such as `편집까지 다 해줘` does not answer this planning-script question unless it also supplies a script/draft or explicitly asks for a new script.

In planning mode, a user-supplied script or draft is the primary planning input, not permission to ignore it and write from scratch. Preserve its facts, numbers, required wording, order constraints, strength, and the user's latest corrections. The planner may restructure or rewrite only within the user's planning request, and must show the resulting complete draft for the normal approval/delegation boundary below. If the user says the supplied wording is exact or locked, freeze those bytes and do not rewrite them; preserve `intake_mode: "planning"` for the remaining planning workflow rather than silently reclassifying the job as direct mode. Record the input text or file path, SHA-256, exact user directives, and any exact-lock state in the run intake/manifest.

After the three identity/reference values and the planning-script decision are complete:

1. Extract the reference video's complete spoken transcript with the fastest reliable available ASR route. Preserve sentence order, hook, persuasion sequence, numbers, and spoken rhythm; verify unclear words against the audio when they materially affect the rewrite.
2. Resolve and load the exact product-specific context asset at `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/_knowledge/products/<제품명>/product_context.md`. This generated product asset, not a generic company summary or conversational memory, is the primary product context. Never borrow another company's or product's context.
3. Before drafting, require `$product-script-writer` to run its exact-company/exact-product prior-video-script discovery and read the selected recent approved or actual edit-input scripts completely. Build `prior_video_logic` from those sources. This is mandatory for every company and product, not a product-specific exception. If no eligible prior script exists, record `status: no_prior_video_script` and continue from the current product context; never borrow another company's or product's logic.
4. Invoke `$product-script-writer` with the exact company name, product name, `planning_script_mode`, any user-supplied planning-script text/path/hash and exact-lock state, extracted reference transcript, resolved product-context path, selected prior-script paths and hashes, and `prior_video_logic`. Reuse the context already loaded in this run instead of reading the unchanged file twice. Use its default `미검증 컨셉 초안` mode. When `planning_script_mode: "user_draft"`, the user's current script/draft is the primary content-and-order input and the reference/prior logic may shape only the parts the user allowed to be planned; when `generate_new`, the prior logic supplies the product's problem → cause → existing-solution limit → mechanism → result → proof/offer → CTA chain. In both cases the new reference supplies sentence roles, reveal timing, expression strength, and spoken rhythm. Latest direct user corrections override every other source. If product information is contradictory, ambiguous, or suspicious enough to materially change the script, require the child skill to finish the draft first and append up to three focused confirmation questions below it.
5. Record `prior_video_script_logic.status`, every selected source path and SHA-256, the internal logic profile, and any user-directed deviation in the run intake/manifest. Do not count duplicate spoken versions, TTS fragments, CTA-only supplements, rejected drafts, or abandoned generation intermediates as separate logic sources.
6. Return the child skill's complete draft and ask for confirmation, then end the turn. Set `script_approval.status: "awaiting_script_confirmation"`; even full end-to-end delegation cannot approve the script. Continue only after explicit user confirmation bound to this exact script hash. Never re-ask the already selected TTS/edit scope.

If the user edits or rejects the draft, honor that feedback and any requested review before proceeding. Record `script_source: "planned_and_user_approved"` only after actual script approval; an automatically prepared draft remains `awaiting_script_confirmation` until that approval. Every revised script requires a new confirmation of its complete text. Resolve the product-detail page URL by the existing-context reuse rule below. Reuse the early ratio, scope, voice, and category answers; ask only for actual missing or conflicting inputs. Continue to the product gate only after both the URL and ratio are present.

### `direct` — 직접모드

After the user selects direct mode, require these six intake values before exploration or generation. The company, product, reference, target script instruction, and ratio must be user-designated; the product-detail page URL may be satisfied automatically by the existing-context reuse rule below:

1. company name;
2. product name;
3. product-detail page URL;
4. reference video;
5. exact script or an explicit instruction to transcribe the reference as the target script;
6. the `1:1` or `9:16` ratio already collected in the early production interview.

After the company and product names are supplied, resolve the product-detail page URL before deciding that item 3 is missing. Ask only for values still missing after resolution and end the turn. Never infer company or product names from filenames, URLs, folders, or prior projects. Do not repeat a question already answered in the current conversation. Record `script_source: "user_supplied"` or `"reference_transcribed_as_target"` as applicable.

### Additional intake for `existing_clean_edit`

- Require one or more user-provided clean video files in addition to the normal inputs. In `planning`, ask for them only after the draft script is approved and before cut planning. In `direct`, treat them as the seventh required intake value.
- Ask only for the missing clean files; do not ask the user to rename, pre-trim, transcode, or reorganize them.
- Once exact company and product names and the files are present, resolve the product scope by normalized exact match and run `scripts/store_clean_clips.py`. Use `--create-product-scope` only when that exact user-designated company/product scope does not yet exist.
- Copy the original bytes into `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/<제품명>/기존 영상 표현/사용자 제공 클린본/originals/`. Never move, delete, transcode, overwrite, or silently replace the supplied file. Deduplicate exact SHA-256 matches and use collision-safe versioned names for different files with the same filename.
- Record `clean_clip_library_manifest`, `stored_clean_clips_dir`, every `clip_id`, stored path, SHA-256, probe metadata, and intake result in the run manifest. Use the stored originals, not prepared/proxy/upscaled/FPS-converted derivatives, as authoritative CapCut sources.

### Existing product-detail URL reuse

- Once the user has designated the exact company and product names, read only the matching `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/_knowledge/products/<제품명>/product_context.md` before asking for a product-detail page URL.
- When that exact product context contains one current product-detail page URL, use it without asking the user again. Record `product_detail_url_source: "existing_product_context"` together with the context path and resolved URL in the run intake.
- When the current conversation supplies a URL, use the user's latest URL and record `product_detail_url_source: "user_supplied"`.
- Ask for the product-detail page URL only when the exact product context is absent, contains no URL, or contains multiple conflicting current URLs. Do not borrow a URL from another company or product, infer one from a folder or filename, or ask merely to reconfirm an exact reusable URL.

## Product and asset gate

- Resolve exact normalized company/product names under `${VIDEO_PRODUCT_LIBRARY_ROOT}`; never fuzzy-match or borrow another product's assets. The legacy `${VIDEO_PRODUCT_LIBRARY_ROOT}` path may be used only when it resolves to the same canonical root.
- Read `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/_knowledge/products/<제품명>/product_context.md` first when present. Treat it as the generated product-specific context asset containing the current product knowledge, approved assets, recent-script context, and approved feedback rules. Keep its fact, claim, dynamic-information, confirmation-needed, and prohibited-use boundaries intact.
- In planning mode, do not treat `product_context.md` presence alone as proof that the latest video-script logic was loaded. Complete `$product-script-writer`'s exact-product prior-video-script discovery, read its selected sources, and preserve the resulting `prior_video_logic` provenance before drafting. Apply this to every company and product.
- Follow `product-page-reference-video/references/company-product-asset-library.md` for library rules.
- In `ai_generation`, if a validated current `product_visual_source_pack` and `product-assets.json` do not exist, run only the product-analysis stages of `product-page-reference-video` first.
- In `existing_clean_edit`, do not run product-master, product-expression, still-generation, or motion-generation preparation merely because a visual source pack is missing. Register and inspect the user-provided clean clips instead. Keep product context and current product identity checks because they still govern script meaning, clip selection, captions, proof, offer, and CTA.
- Treat page claims as page claims. Ask at most three product-claim clarification questions and only when the answer changes a visible subject, action, material, setting, transformation, or outcome. This product-claim cap is separate from Gate 0.5's consolidated visual-detail interview.
- Reuse only approved, current-packaging-compatible assets. Treat unmanifested legacy files as candidates.
- In `ai_generation`, if no current approved product master exists, include one built-in ImageGen master attempt in Gate 1. Use high-quality GPT Image 2 for the master, restore official label/logo pixels deterministically, and QC silhouette, proportions, material, color, label placement, option, and quantity. A master failure is systemic: stop before per-cut generation and never retry without approval.
- In `ai_generation`, decide product presence per cut before generation. Set `product_presence: required` for product reveal, product selection, package handling, one-stick/one-sachet use, mixing, consumption, proof, sold-out/repurchase/social-proof, offer, stock-up, purchase-limit, or CTA beats. Set `forbidden` only for strictly product-independent symptom, anatomy, ingredient-only, mechanism-only, or atmosphere shots when the complete sequence already contains unmistakable required product shots. Never use `forbidden` to replace the designated product with a generic or unbranded substitute. In `existing_clean_edit`, require stored-source coverage of every product recognition/use/proof/CTA beat or report it as unmatched.
- When the user says the product must appear, treat that as a sequence-level identity lock: every product-like object must be the exact designated product, and at least every reveal/use/proof/CTA beat must show it. Slight compression, fine-print softening, or brief AI shimmer may be accepted only when the brand, package color, silhouette, box/stick structure, and product identity remain unmistakable and no invented competing label appears.

## Gate 0.5 — finalized-script visual-detail interview

Run this gate only after explicit confirmation of the current script hash, and after the exact target script, product-detail URL, output ratio, and any mode-required clean clips are present, and before semantic segmentation, cut count, prompts, costs, TTS, or CapCut work. It applies to `planned_and_user_approved`, `planned_under_end_to_end_delegation`, `user_supplied`, and `reference_transcribed_as_target` scripts in both visual-source modes. Carry the early production contract into this gate: an end-to-end delegation can supply `user_delegated` visual decisions without a new questionnaire, while any explicitly reserved user decisions remain unresolved until answered.

1. Freeze the exact script bytes and SHA-256. Do not silently fix spelling, spacing, pronunciation, numbers, or claims. When a likely typo or homophone would change narration or visible meaning, show the exact original and proposed correction and ask which version to lock.
2. Perform only the read-only preflight needed for the interview: inspect the reference at native speed for medium, character proportions, expression method, composition classes, and native camera behavior; load the exact product context and approved asset inventory or the frozen clean-clip manifest; preserve every visual directive already supplied by the user.
3. Invoke `$script-visual-expression-interview` with `interview_profile: "finalized_script_detail"`, the exact script/hash, reference profile, approved product or clip inventory, and existing directives. Follow `references/finalized-script-visual-detail-interview.md` for the question and record contract.
4. Ask one consolidated set of concrete, answerable choices only for unresolved decisions that materially change a visible subject, action, material, location, Before intensity, product-use mechanism, After degree, supporting character, evidence setting, camera composition, CTA frame, or plan-changing narration duration. Do not ask again for a value the user already fixed.
5. When the user says not to decide expression strength or details arbitrarily, every unresolved high-impact variable is blocking. Do not choose a recommended, conservative, attractive, or reference-derived default. Show concrete A/B/C outcomes and end the turn for answers before any cut plan.
6. Record actual questions, options, user answers, direct quotations, script-normalization decisions, and resulting locks in `visual_detail_contract.json`. Set `ready_for_visual_planning: true` only when every applicable high-impact variable has a user answer or is covered by the recorded end-to-end/explicit visual delegation. Record agent-selected values as `user_delegated`; never fabricate a question or user answer. A user's explicit instruction to reserve a decision overrides a broad earlier delegation.
7. Record the contract path and SHA-256 in the run intake, workflow manifest, and plan. A missing, stale, or `ready_for_visual_planning: false` contract blocks Gate 1. If the script later changes, invalidate and re-ask only the answers affected by the changed semantic units; preserve unrelated answers.

In `existing_clean_edit`, ask only about choices achievable with the registered supplied clips. A missing intensity, character, action, or result that the source library cannot show becomes `unmatched_visual_beat`; never turn the interview into permission to generate replacement footage.

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

### Default cut-edit handoff — use the early answers

For requested 9:16 editing without a separate stable style or strict event-level replication request, use `$capcut-cut-edit` → `$capcut-semantic-cut-edit`. Pass `production_intake.capcut.category` as `supplement`, `beauty`, `food`, or `other`, the exact category answer, selected ratio, user-confirmed script, current reviewed media, current voice file, explicit font or the common Pretendard default, and exact company project. Do not ask a category, style, font, existing baseline timeline, or new timeline name already answered or covered by defaults. ‘그외’ uses observed product-use/demonstration context, not another category's assets or facts.

Use the dedicated semantic `inventory → plan/review → validate → bind → stage → install → verify` path and its actual supported canvas/voice/source contract. Verify the selected ratio before editing; do not force an unsupported ratio into 9:16. Build outside the live project while CapCut is open and install only after normal closure. Resolve the exact existing company project and add one new editable timeline; a staged folder or flattened MP4 is not completion. This narrow adapter has its own binding/verification and does **not** take the broad automation run-context flags below.

The broad bridge below applies when the user separately requested stable style/strict event-level replication, or when its currently permitted adapter is verified to support the user's selected canvas that the narrow adapter does not. For a canvas-only bridge use `base_cut` and the already selected/default font; do not repeat style/font intake or claim an unsupported canvas is supported. If neither permitted adapter supports the requested canvas, report that actual limit without modifying guards or silently changing the ratio. Do not invoke the broad or combined TTS workflow merely to repeat the default cut-edit interview.

### CapCut fresh run-context bridge

Before invoking `$capcut-automation`, carry the early answers and delegated defaults forward. Only ask an unresolved style/font decision when the user actually requested custom style work; a canvas-only base edit uses `base_cut` and the common font without another interview. Then compile a fresh contract for the exact company, product, and job. Never substitute a chat summary or parent plan for this contract.

1. Choose one canonical CapCut mode. Use `base_cut` for assembly without a stable recipe, `style_apply` only for an explicitly selected stable recipe, and `reference_replication` only when the user explicitly requests **strict event-level replication** with bounded fidelity evidence. A clean visual reference by itself is not strict replication.
2. For strict `reference_replication`, freeze the approved parent plan/source-pack manifest and build with `--mode-source MANIFEST`, repeated `--allowed-asset ID`, and at least one `--fidelity-scope SCOPE`. The manifest, target asset allowlist, and fidelity scope must be finalized before the contract is built.
3. Run the canonical wrapper from any working directory:

```bash
python3 "${PLUGIN_ROOT}/skills/capcut-automation/scripts/build_run_context.py" build --company ... --product ... --job-id ... --mode ... --font ... --output "${CAPCUT_AUTOMATION_ROOT}/.hermes/run-contexts/<job-id>/run_contract.json"
```

Add `--style ...` only for a selected stable recipe. Add the strict-replication flags from step 2 only for `reference_replication`. For every build, pass the parent plan's current task boundary with repeated `--rule-category CATEGORY --semantic-role ROLE`; do not load unrelated approved or negative evidence. Pass each explicit current-run directive as `--runtime-override '{"rule_key":"...","effect":"must_do|must_not","instruction":"..."}'` so it is hash-bound without mutating durable approval state. Before live mutation, freeze the exact existing project, protected source timeline, unique destination name, and bank/profile/selection paths plus hashes and pass `--execution-manifest MANIFEST`; omitting it creates a planning-only contract and forbids live mutation.

4. Preserve the returned machine-contract path and semantic hash. Require its matching `run_contract.md` and `run_contract.commit.json`; a missing or mismatched commit marker is fail-closed. Read the Markdown plus exactly one mode playbook; do not preload the other CapCut playbooks.
5. Pass `--run-context CONTRACT.json --run-context-hash HASH` to every mutating CapCut entrypoint and completion gate. Any missing, stale, mismatched, conflicting, or over-budget contract stops the CapCut branch without a fallback edit.
6. Resolve the exact existing company project and create exactly one unique new timeline inside it. Never create a replacement project. Never open CapCut and never export under the current contract. Never create or enable a watcher, LaunchAgent, or cron unless the user says the exact phrase `자동 실행 승인`.
   - A flattened local render is preview/QC evidence only. It never satisfies a requested edit or completion state. When the user requests editing, completion requires exactly one newly registered editable CapCut timeline, separate editable video/audio/caption assets, and a saved-draft reverse verification that proves the destination registration, media hashes, track timing, caption font, and preservation of every pre-existing timeline. If that proof is absent, report the edit as incomplete even when a playable local MP4 exists.
7. When the user gives feedback intended to improve future edits, route it to `$capcut-automation` feedback capture with the exact feedback text and baseline artifact. Do not append it to either SKILL.md or the stable recipe. Hermes may propose one shadow replacement; promotion requires three golden A/B wins with zero regressions.

- Invoke `$capcut-automation` only after this fresh bridge passes and after the main generated visual set or registered clean-source set passes its mode-specific QC and a usable TTS candidate or approved final exists. If the user explicitly names a CapCut project, resolve that exact project. Otherwise use the already approved company name to locate the single existing CapCut project whose direct folder name or project metadata exactly matches the company after NFC·case normalization. A pre-existing timeline name is never required because this workflow must create exactly one uniquely named new timeline for the run. Pass the resolved project root, run-contract path/hash, and an auto-generated company/product/job/date/version timeline name to `$capcut-automation`; create the editable draft only through its permitted file-based path, and run its permitted file-based verification without asking for a sample review. Optional reserves and strict TTS finalization do not block draft creation. Record `awaiting_capcut_target` only when no exact company project exists or multiple exact candidates remain; never record it merely because the user did not supply a project or existing timeline name.
- In `ai_generation`, keep generated video silent. In `existing_clean_edit`, keep source audio disabled unless the approved plan explicitly uses it. Pass TTS as a separate editable audio asset to CapCut. Preserve hidden/editable captions when the request asks for a clean video, and do not add reviews, X marks, music, effects, or transitions that are outside the approved plan.
- Auto mode authorizes no paid retries by default, no extra keyframes, scope expansion, publishing, uploading, deletion, or destructive replacement. A schema-version-4 run may perform at most the explicitly listed cut-local semantic retries only when `semantic_retry_policy.authorized_in_gate_1` is true and both its job-count and credit ceilings remain unexceeded. Otherwise quarantine failed/duplicate attempts, report their actual cost, and continue unrelated first attempts when the child contracts allow it.
- If a child branch reaches a user-listening or paid-retry gate, do not block the already-authorized CapCut draft. Record the exact pending state, candidate path, failed gate, and next one-time action in the manifest and final report.

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
  "stored_clean_clips_dir": "<product>/기존 영상 표현/사용자 제공 클린본/originals",
  "registered_clean_clip_count": 0,
  "tts_finalization_state": "pending|user_approved_final|user_delegated_auto_qc_final",
  "capcut_target": {"project": "resolved exact company project", "timeline": "generated_unique_new_timeline"}
}
```

`auto` means no intermediate user prompt, not permission to mislabel a preview as final or to bypass a child skill's failed quality gate. Report `auto_edit_complete_tts_pending` when CapCut is verified but the TTS child still lacks its required final state.

## Quality-speed profile

Set `quality_profile: "balanced_auto"` for `execution_mode: "auto"` and `quality_profile: "precision"` for `precision_planning`, unless the user explicitly chooses another documented profile. Both profiles keep the same hard-failure list. For legacy plans, `balanced_auto` changes only scheduling: objective probes and frame extraction still run for every clip, while original-resolution human review is reserved for high-risk/product/warning cuts and the rest are reviewed in contact sheets. Every schema-version-4 cut is always `deep` for sentence-level review in both profiles and uses five checkpoints (start, 25%, 50%, 75%, end). `precision` also opens original frames for every legacy cut. Never treat the balanced profile as permission to accept an unproven semantic unit, wrong product, unsafe anatomy, frozen motion, wrong model, or unverified final TTS.

In `ai_generation`, use `reserve_policy: "on_demand_after_main_qc"` by default for new plans. Generate and QC main cuts first, then create only the minimum reserve clips needed to cover a failed beat or an explicitly requested alternate. Use `"approved_upfront"` only when the user explicitly authorizes all reserve first attempts and their separate cost. In `existing_clean_edit`, do not create reserve footage; report unmatched beats and reuse only approved stored segments.

## GPT-only image generation and concurrency

This section applies only when `video_source_mode: "ai_generation"`. In `existing_clean_edit`, set `image_generation_mode: "disabled_existing_clean_edit"` and skip the section completely.

For every new or resumed future generation action, set `image_generation_mode: "openai_only"` and `image_generation_route: "built_in_image_gen"`. Use only the built-in OpenAI `image_gen` tool through `$imagegen` default mode for stills. Historical manifests may contain `higgsfield_only`, `hybrid_parallel`, direct API, or CLI records; preserve them as read-only provenance, but never submit another image job through those routes. A material remap must migrate the new plan to the built-in route before generation.

- The built-in `image_gen` tool is the only permitted route for scene still generation. It produces one distinct scene asset per call, so submit distinct cuts as separate parallel calls; do not use a multi-output request to represent different prompts.
- OpenAI requests start at a conservative five concurrent requests for a Tier-1 account and must be reduced on a 429/5xx or raised only after the current account headers/preflight prove a higher limit. The provider's IPM limit remains authoritative; concurrency is not a guaranteed images-per-minute number.
- For `N` main cuts, plan exactly `N` OpenAI first-attempt stills, select exactly `N` starts after QC, and keep the Higgsfield image count at zero. Do not create a second provider lane or duplicate every cut for comparison.
- A provider lane may use the same approved character or product reference as conditioning input across cuts, but its generated scene output may not be reused. After selection, run `scripts/check_selected_start_diversity.py --output <run>/qc/selected-start-diversity.json <selected-starts...>` across all main cuts. Any exact hash duplicate or perceptual near-duplicate is blocking: reject the later cut's still and generate a new scene before Kling. Also inspect one labeled contact sheet of all selected starts; repeated background, pose, action, shot scale, and camera angle as a group is a hard scene-variety failure even when bytes differ.
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

## Staged execution

The numbered generation stages below apply only to `ai_generation`.

1. Validate the product master and plan lint. Create `<run>/qc/submission-ledger.json`.
2. Claim a deterministic submission key before every paid still/video job with `scripts/submission_ledger.py`. The key must include plan hash, cut, stage, attempt, start-image hash, model, ratio, duration, and sound.
3. Build one OpenAI image schedule. Generate high-risk/product-required candidates first, with high quality and the configured OpenAI cap. QC candidates before motion. Do not create or schedule a Higgsfield image lane.
4. Generate remaining approved main candidates with low quality only for low/medium-risk product-independent cuts. Keep each distinct scene as its own built-in `image_gen` call; do not collapse different prompts into one multi-output request.
5. Select exactly one QC-passing, action-ready start image per cut and record the selected route, absolute path, SHA-256, perceptual hash, scene-design signature, and rejected alternatives. Run the cross-cut diversity script and inspect the all-starts contact sheet before any Kling submission. If two cuts share an exact/near-duplicate image or substantially the same background-pose-action-framing group, keep the earlier approved cut and regenerate the later cut's start still with a different scene design. Only after this gate passes submit each Higgsfield motion base. The primary motion must visibly complete the planned proof during its three, four, or five seconds, the secondary motion must make the actual setting feel inhabited, and camera motion must preserve the declared static anchors. For `product_presence: required`, animate a start image containing the exact scene-native reference-conditioned product by default. Never substitute an unbranded product-like prop. Use a product/text-free placement plate only for a planned `official_pixel_composite`. Add verified claims or offer text only in deterministic post.
6. Run at most two high-risk Higgsfield Kling video pilots after their OpenAI starts pass QC, then submit the remaining approved video first attempts. Batch independent low/medium-risk OpenAI image candidates within the OpenAI cap. A provider timeout becomes `submitted_unknown`; reconcile the ledger/provider status before any new submission.
7. Never create motion from a failed or unselected still. After main QC, evaluate reserve coverage and submit only the minimum reserves permitted by `reserve_policy`.
8. Normalize final media deterministically to the approved ratio and the cut's exact planned `3.0 s`, `4.0 s`, or `5.0 s`; use hard cuts only. Never trim away the action completion or success frame to hit duration.
9. Never create or promote a local-only fallback when a required image candidate or Higgsfield motion job is missing, failed, quarantined, or rejected.

For `existing_clean_edit`, execute these stages instead:

1. Resolve the exact company/product scope, store the supplied originals with `scripts/store_clean_clips.py`, and freeze the returned manifest revision for the run.
2. Probe every registered clip and extract contact sheets plus start/middle/end frames without altering the originals.
3. Validate every planned `source_clip_id`, SHA-256, path, and source time range against the frozen manifest. Stop on a missing/hash-mismatched source; never silently substitute another clip.
4. When editing was requested, stage only the selected original clips, then apply the requested trim, reframe, source-audio, caption, and supported deterministic edit instructions in CapCut.
5. For requested editing, verify that the saved draft uses authoritative stored sources, contains the planned order/durations, preserves editable narration/captions, and has no AI image/video job or generated substitute. Source-only scope finishes with the reviewed source package instead.

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

## Completion

In `ai_generation`, complete only when every approved main cut has one selected traceable action-ready still (with all planned candidates and their QC decisions retained), a unique selected-start path/hash and distinct scene-design signature, one Higgsfield Kling v3.0 output at its exact planned three-, four-, or five-second duration, provider/job/model provenance, QC status, approved anchors, a complete motion-design record, a passed cross-cut scene-variety gate, a passed motion-progression gate, and accurate deterministic text/evidence layers. Every schema-version-4 cut must additionally have a passing `validate_semantic_qc.py` report proving every semantic unit, literal-first action, start state, end state, causal link, success frame, and stable anchors. Any product-visible cut must also pass the complete scene-integration gate; a technically accurate package pasted into an implausible scene is incomplete. For new plans, the number of valid unique selected main starts and Higgsfield video jobs must each equal `main_cut_count`; deferred reserves are reported separately and never mask missing main coverage. Legacy plans that use `planned_cut_count` remain resumable under their original count.

In `existing_clean_edit`, require exact registered `clip_id`, immutable path, SHA-256, valid source range, and visual/source QC for every selected cut. If editing was requested, also require a saved editable CapCut timeline using those originals, separate narration/captions, and reverse-verified order and duration. Record `image_generation: false`, `video_generation: false`, and zero AI visual-generation jobs. Source-only or TTS-only scope does not authorize a CapCut timeline. Report unresolved beats rather than generating replacements, and distinguish file verification from actual app playback.

For `execution_mode: "auto"`, continue through every branch selected in the early production contract without pausing to ask again. Run `$elevenlabs-reference` only when TTS was requested; use provided narration for edit-only scope. When editing was requested, use the default cut-edit handoff above (or the separately requested style bridge), resolve the exact existing company project, create exactly one new editable timeline, attach audio separately, and reverse-verify the saved result. Do not stop at finished clips, a TTS preview, an edit plan, or staging. Distinguish `auto_complete` from `auto_edit_complete_tts_pending`, and never call preview audio final. For scopes without editing, finish only the selected deliverables and do not create a CapCut timeline.

When editing was requested, never label the run `auto_complete` or `auto_edit_complete_tts_pending` from a local master alone. Both states require the saved CapCut timeline and its reverse-verification report; a local master may be linked only as an additional preview.

- In `ai_generation`, collect every clean normalized cut in one numbered folder, normally `videos/final`, using zero-padded names such as `cut-01.mp4`, `cut-02.mp4`, and so on.
- In `ai_generation`, verify that this run's selected main-clip count equals `main_cut_count` for new plans (or legacy `planned_cut_count`). Keep reserve counts and provenance separate in the manifest, but collect all approved same-day clips into the same daily `생성 클린본` folder. Record that shared directory as `numbered_clean_clips_dir` and retain an explicit per-run file mapping; the daily total may exceed this run's cut count.
- In `ai_generation`, run `scripts/organize_result_folders.py` after QC, following `references/output-folder-organization.md`. Use its daily `final_clean_clips_dir` and per-file `files` mapping for new manifest entries; keep signed/hash-bound historical records intact through compatibility links. In `existing_clean_edit`, retain the product library path returned by `store_clean_clips.py` as `stored_clean_clips_dir`; do not relocate supplied originals into generated outputs.
- In `ai_generation`, expose one `YYYY-MM-DD/생성 클린본` folder per generation date in Korea. Put visible supporting folders under Korean names such as `기획 자료`, `음성`, `편집 자료`, and `작업 기록`. First scenes, later CG, extra model scenes, and approved reserves created that date all share the same clean folder, with continuing numbers and Korean scene names. Do not expose the old `01_최종_영상클린본_N컷` or English batch-folder layout as the primary result view.
- In `ai_generation`, preserve original bytes and references without generating or copying media again. Use same-filesystem moves with compatibility symlinks, hide only the legacy links in Finder, and keep raw/QC/previous versions inside `작업 기록`. Append different same-day files with unique names, skip already indexed identical hashes, and refuse conflicting or untracked files instead of overwriting them.
- In `ai_generation`, preserve every earlier generation. Clearly label rejected or wrong-product versions with `폐기버전` or `사용주의`; never present them beside the canonical final folder as usable outputs.
- In `ai_generation`, verify the current batch count separately from the daily total, every media hash, and all preserved old paths/links. Accumulate canonical paths and provenance in `YYYY-MM-DD/작업 기록/클린본 목록.json`; use the organizer's returned manifest path instead of assuming a root-level `result-folder-manifest.json`.
- Save a generation manifest and final hard-cut master for `ai_generation`; save a workflow manifest, stored-source manifest link, and final CapCut draft/master for `existing_clean_edit`.
- Refresh the generation/workflow manifest from the final child job records immediately before reporting. A candidate path, output hash, CapCut draft, or QC result discovered during execution must not remain a stale `null`; use an explicit pending status and reason only when the value is truly unavailable.
- In every `ai_generation` completion response, provide clickable local links labeled `날짜별 생성 결과물` and `생성 클린본`, the day's total clip count, and the relevant final master/QC/manifest paths. In every `existing_clean_edit` completion response, print clickable links labeled `제품별 저장 클린본 폴더` and `클린본 라이브러리 매니페스트` alongside the CapCut draft/master path, QC summary, and workflow manifest.
- Do not upload, publish, or launch an ad without separate authorization.

---
name: ai-video-reference-replication
description: Create reference-based ecommerce ads with AI visuals or supplied clean footage, optional reference/user-selected TTS, and editable CapCut delivery. Ask source mode and script mode, then collect ratio, TTS/edit scope, voice choice, and editing category early. In planning mode, always determine whether the user has a script or draft; use it as the primary planning input when present and create a new script only when absent. Honor an earlier request to finish editing as end-to-end delegation with the current reference voice unless another voice is specified. Carry answers through production without repeated execution-mode questions. Preserve exact product/source identity, child-skill quality and retry limits, and safe project saving.
---

## 업체별 영상 폴더 기준 (2026-09-19)

- 사용자가 이번 작업에서 지정한 소스가 우선이다. 업체·제품 소스를 요청하면 `/Users/seojun/Documents/인코어/<업체>/영상/<제품>/클린본`을 기본으로 사용한다. 경로의 한글은 Unicode 정규화 후 정확히 일치하는 업체·제품만 선택한다.
- 편집 시작 전에 실제 소스 폴더의 절대경로와 사용 가능한 영상 개수를 사용자에게 짧게 알린다. 하위 폴더까지 현재 파일을 확인하고, 예전 매니페스트에 없다는 이유로 같은 제품의 새 클린본을 누락하지 않는다. 링크는 같은 업체·제품 내부만 해석하고 실제 경로 기준으로 중복 집계하지 않는다. 존재하지 않거나 읽지 못한 파일은 개수와 구별해 보고한다.
- `완성본`은 완성 영상 보관용, `레퍼런스`는 참고 영상용이다. 별도 요청 없이 이 두 폴더를 클린 소스로 사용하지 않는다. `제품 미분류`는 사용자 지정 전 다른 제품 소스에 섞지 않는다.
- 새로 제공받아 보관하는 클린 원본은 `<제품>/클린본/사용자 제공 클린본`, 검수 통과한 AI 생성 클린본은 `<제품>/클린본/AI 생성/YYYY-MM-DD`에 저장한다. 같은 날짜의 추가 생성은 같은 폴더에 모은다. 새 완성 영상의 업체 보관 위치는 `<제품>/완성본`이다.
- 기존 제품 정보·생성 작업 기록은 제품 폴더 안의 숨김 자료로 보존되어 있다. `생성 결과물`은 내부 작업 이력용이며, 사용자가 보는 생성 클린본 경로는 위 `클린본/AI 생성`이다. 이전 경로 연결과 서명된 작업 기록은 임의 삭제하거나 일괄 치환하지 않는다.


## 공유 플러그인 실행 경로

이 문서가 들어 있는 `skills`의 상위 폴더를 `PLUGIN_ROOT`로 확인하고, 먼저 `../../references/recipient-runtime.md`를 읽는다. `${PLUGIN_ROOT}`는 현재 설치된 이 플러그인의 절대 경로로, `${VIDEO_PRODUCT_LIBRARY_ROOT}`와 `${CAPCUT_AUTOMATION_ROOT}`는 수신자 환경의 경로로 해석한다. 하위 스킬은 이 플러그인 안의 형제 폴더를 우선 사용한다. 플러그인 제작·수정·공유 요청은 영상 제작 인터뷰나 유료 생성, 앱 종료를 시작하지 않는다.


# 영상 생성

## 시작 표시와 버전

- 현재 자동화 버전: `1.11`
- 실제 영상 제작을 시작하면 `assets/automation-version.json`을 읽고 `버전 v{automationVersion} 업데이트 된 시각 {displayUpdatedAtKst}`를 먼저 표시한다. 유지보수 요청에서는 제작 인터뷰를 시작하지 않는다.


## 스킬 수정과 배포 완료 기준

소유자는 2026-09-08 이 플러그인의 스킬 수정 요청에 공개 배포 반영까지 포함하도록 명시적으로 지정했다. 소유자 환경에서 이 스킬 또는 포함된 지원 스킬을 수정할 때는 `../../references/skill-maintenance.md`를 읽고 원본 수정 → 검증 → 로컬 설치 → 공개 릴리스 → 공개 파일 확인까지 완료한다. 로컬 수정만으로 완료를 보고하거나 같은 대상의 배포 승인을 다시 묻지 않는다. 최신 사용자 지시가 로컬 시험만 요청하거나 배포를 금지하면 그 제한을 우선한다. 받는 사람의 환경에 소유자의 배포 권한을 적용하지 않는다.

## Reference structure and mandatory script confirmation

Every newly written or rewritten ad script must preserve the supplied reference video's full spoken-script structure: sentence/semantic-unit order, persuasive role, paragraph breaks, hook type, reveal timing, argument transitions, CTA placement, expression strength, and spoken rhythm. Transcribe the complete reference first and keep an ordered one-to-one internal mapping from its exact units to the target units. Use the designated product's facts and causal logic inside those same structural positions. Prior scripts supply product logic, never a replacement outline. Do not invent a generic outline, reorder the reference to fit an old script, or shorten it to a default 30–40 seconds. Resolve an actual product-logic/structure conflict with a focused question rather than silently changing either.

Always show the complete exact target script and wait for the user's explicit confirmation before Gate 0.5, cut planning, prompts, image/video generation (including native talking-head speech), separate TTS, or CapCut editing. This applies to both source modes, every production scope, direct/transcribed scripts, and every new or revised draft. A user message explicitly designating the exact supplied text as the confirmed final script can serve as confirmation; choosing a mode, requesting all editing, silence, or merely supplying a draft cannot. Broad end-to-end delegation never waives this gate.

Set `script_approval.required: true` and `status: awaiting_script_confirmation` until confirmed. Bind the approval receipt to the exact script path/SHA-256, approval quotation, and timestamp; link it in intake and the workflow manifest. A script change invalidates its prior receipt: show the whole revised script and obtain confirmation again, preserving unrelated intake answers. Keep old `planned_under_end_to_end_delegation` records as history only; before further production, require actual confirmation of the current script. After confirmation resume the already authorized scope without repeating the scope interview.

## Core contract

- Product persistence is mandatory in every production scope, including `visuals_only`. After the user identifies the exact company/product, read `references/product-knowledge-persistence.md`, inspect its saved library before asking for information or images, and capture new scripts, features/USP, source pages, product images and corrections as soon as received. Reuse saved exact-product inputs on later runs; ask only for genuinely missing or ambiguous items after checking the matching sources. Do not require the separate CapCut context engine for this baseline storage.
- Default AI execution is `execution_pipeline: "per_cut_streaming"`. Read `references/per-cut-streaming.md`: as each built-in image completes, perform that cut's visual QC and rolling cross-cut diversity check, then submit its Kling video as soon as a slot is available while other image/video requests continue. Never wait for all starting images or an entire image batch before beginning eligible videos. Keep script/product/budget gates and the final full-set diversity/QC audit.
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
- In `ai_generation`, never reuse one selected start image, an exact copy, a re-encoded near-duplicate, or the same base composition across two different main cuts. Character and product continuity do not justify scene reuse. Give every cut a cut-specific setting/action/shot-scale/camera-angle design. Before each Kling submission, prove that start's diversity against every already selected start; repeat the full-set audit before final promotion without blocking early submissions on unfinished images.
- In `existing_clean_edit`, use only user-provided clean footage registered under the exact company/product. Never invoke AI image generation, AI video generation, Higgsfield, Kling, or a local synthetic-motion substitute. Continue source QC and the editing/TTS/caption branches actually selected in the early production scope.
- Preserve the exact user-designated company and product whenever a beat shows product recognition, handling, mixing, consumption, proof, offer, social proof, or CTA. Never replace it with a generic sachet, unbranded packet, tea bag, lookalike box, or another product. In `ai_generation`, prefer a scene-native reference-conditioned still built from the approved official product asset so the product belongs to the photographed or illustrated scene from the start. Use official-pixel compositing only when it can be integrated naturally; never paste a flat asset over an existing product, prop, hand, glass, or shadow.
- In `ai_generation`, generate full-bleed scenes without text, pseudo-text, cards, panels, fake UI, borders, letterboxing, transitions, or outros.
- In `ai_generation`, generate every final motion cut through Higgsfield Kling. A GPT Image candidate is an input still only; a local-only MP4, still-to-video pan/zoom, parallax, mask reveal, or frozen image never satisfies a video cut.
- In `ai_generation`, treat visible scene life as a universal per-cut requirement, not a temple-specific style. Every cut must have a planned script-bearing primary motion, a scene-appropriate secondary environmental motion, and either a purposeful camera move or an explicit locked-camera reason. Protect named static anchors such as the approved product, face, hands, architecture, glass, and horizon from drift or deformation. Temple mist, visitors, foliage, changing light, and a push-in are examples for one setting only; choose equivalent human, object, material, atmospheric, lighting, reflection, fabric, shadow, or camera motion for the actual setting of each future video.
- In `ai_generation`, allow deterministic local post only after a valid Higgsfield motion base exists, and only for optional scene-integrated official product restoration/tracking, verified text/evidence/CTA, occlusion mattes, perspective and contact-shadow matching, color matching, normalization, and assembly. Do not force an overlay when the scene-native reference-conditioned product is already identifiable. A rectangular sticker-like overlay, doubled silhouette, floating package, exposed cleanup bar, or unmatched plane is forbidden.
- If Higgsfield generation fails or is unsafe in `ai_generation`, quarantine or redesign that cut. Never fall back to a local motion substitute.

Before creating any new `ai_generation` run directory, read `references/output-folder-organization.md` and initialize `생성 결과물/YYYY-MM-DD/작업 기록/<한글 작업명>` with `scripts/organize_result_folders.py --init-run`. For the reorganized company library, the user-facing daily clean directory is `<제품>/클린본/AI 생성/YYYY-MM-DD`. Same-day additional scenes and approved reserve clips append to that same folder; never create separate user-facing clean directories by batch, model, scene type, version, or cut count. Keep independent job/QC records inside `작업 기록` and use Korean names for the visible planning, audio, and edit folders. This is the default for future company/product jobs; reorganize another existing product only when requested.

Read `references/finalized-script-visual-detail-interview.md` completely every time the target script first becomes exact or is materially revised, then run Gate 0.5. Read `references/reference-replication-contract.md` completely only when building or materially remapping a plan. When resuming an approved run with a traceable plan, source pack, manifest, and QC records, load those records and continue from the unresolved gate without repeating page or reference forensics. Read `references/effect-translation-interview.md` only when the user designates a particular effect or frame sequence. Read `references/performance-optimized-execution.md` when `자동모드` is selected for `ai_generation` or the user asks to reduce generation time, missing outputs, or duplicate jobs.

Read `references/product-integration-qc.md` completely whenever any cut may show an official product master or product-derived overlay. Apply its product-necessity decision before prompting and its start/middle/end integration gate before promotion.

When `video_source_mode: "existing_clean_edit"` is selected, read `references/existing-clean-edit-workflow.md` completely before accepting or planning supplied clean clips. Use `scripts/store_clean_clips.py` for product-scoped immutable intake and its returned manifest as the only clip inventory for that run.

## 단계 지도 — 필요한 단계 문서만 읽기

아래 문서는 이 SKILL.md에서 문구 변경 없이 분리한 원문이다. 각 단계에 들어가기 전에 해당 문서를 처음부터 끝까지 읽는다. 같은 실행에서 이미 읽었고 바뀌지 않은 문서는 다시 읽지 않아도 된다. 이 문서 위쪽의 폴더 기준, 대본 확정, Core contract는 모든 단계에 항상 적용된다.

| 순서 | 언제 읽나 | 문서 |
|---|---|---|
| 0 | `ai_generation`에서 clean-reference 지시가 있거나 그 수준의 레퍼런스 사용을 요청받았을 때 | `references/workflow-00-clean-visual-reference-contract.md` |
| 1 | 모든 신규 제작 실행에서 첫 사용자 질문 전 | `references/workflow-01-question-display.md` |
| 2 | 첫 질문 전: Gate -1, Gate 0, 초반 비율·제작 범위·TTS·편집 분야 인터뷰, 기획모드·직접모드 입력, 클린본 추가 입력, 상세페이지 URL 재사용 | `references/workflow-02-intake-gates.md` |
| 3 | 업체·제품이 정해진 뒤 제품·자산 확인 | `references/workflow-03-product-asset-gate.md` |
| 4 | 현재 대본 해시가 확정된 직후 Gate 0.5 | `references/workflow-04-visual-detail-gate.md` |
| 5 | 컷 기획 Gate 1 | `references/workflow-05-planning-gate1.md` |
| 6a | 기획 검증 후 실행 방식 Gate 1B, 정밀 기획·자동모드 | `references/workflow-06a-execution-mode.md` |
| 6b | TTS·CapCut 편집으로 넘길 때 | `references/workflow-06b-capcut-handoff.md` |
| 6c | 자동모드 실행 매니페스트를 쓰기 전 | `references/workflow-06c-auto-manifest.md` |
| 7 | 이미지·영상 생성 제출 전: 품질 프로필, GPT 이미지 경로, 위험도, 모델 고정 | `references/workflow-07-generation-rules.md` |
| 8 | 생성 또는 클린본 편집 실행 | `references/workflow-08-staged-execution.md` |
| 9 | QC, 실패 격리, 재시도 판단 | `references/workflow-09-qc-and-retries.md` |
| 10 | 완료 보고 전 | `references/workflow-10-completion.md` |

On every fresh production invocation, read documents 1 and 2 before asking anything; Gate -1 remains the first question. Read document 7 before any image or video submission, including resumed runs. A gate is never optional because its text now lives in a reference file.

# Intake gates (Gate -1, Gate 0) — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

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

- First run the exact-product library inspection under `references/product-knowledge-persistence.md`. Its saved current URL, product facts and images are reusable inputs, including on a later chat. Load actual source files; do not re-download an unchanged complete source pack or require reattachment merely because the current chat is new.
- Once the user has designated the exact company and product names, read only the matching `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/_knowledge/products/<제품명>/product_context.md` before asking for a product-detail page URL.
- When that exact product context contains one current product-detail page URL, use it without asking the user again. Record `product_detail_url_source: "existing_product_context"` together with the context path and resolved URL in the run intake.
- When the current conversation supplies a URL, use the user's latest URL and record `product_detail_url_source: "user_supplied"`.
- Ask for the product-detail page URL only when the exact product context is absent, contains no URL, or contains multiple conflicting current URLs. Do not borrow a URL from another company or product, infer one from a folder or filename, or ask merely to reconfirm an exact reusable URL.

# Existing Clean-Footage Edit Workflow

Use this contract only when `video_source_mode: "existing_clean_edit"`.

## Scope

- Keep the normal script intake, product context, reference analysis, Gate 1 approval, execution-mode choice, reference-voice TTS, QC, CapCut edit, and final verification.
- Remove every AI visual-generation action: no ImageGen, GPT Image, Higgsfield image, Kling video, generative fill, synthetic-motion fallback, paid visual job, provider retry, product-master generation, or reserve generation.
- Treat user-provided clean video as the authoritative visual source. Never use a prepared, proxy, upscaled, interpolated, FPS-converted, or previously edited derivative as the main source when its registered original exists.

## Product-scoped storage

Store originals under the exact user-designated company and product:

```text
${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체명>/<제품명>/기존 영상 표현/사용자 제공 클린본/
├── originals/
│   └── <collision-safe original filenames>
└── clean-clip-library.json
```

- Match company and product only after Unicode NFC normalization, outer-space removal, repeated-space collapse, and casefold. Never fuzzy-match or infer either name from a filename, reference, URL, or another product.
- Run `scripts/store_clean_clips.py` after the exact company/product and one or more source files are present. Use `--create-product-scope` only for a missing exact scope explicitly named by the user.
- Copy bytes; never move, delete, transcode, rename at source, or overwrite. Reuse an existing stored file only on exact SHA-256 match. If a different file has the same filename, create `_v002`, `_v003`, and so on.
- Freeze the returned `manifest_revision`, clip IDs, stored paths, hashes, and probe metadata in the run manifest before planning.

## Intake command

```bash
python3 scripts/store_clean_clips.py \
  --company "<업체명>" \
  --product "<제품명>" \
  --source "/absolute/path/clip-01.mp4" \
  --source "/absolute/path/clip-02.mov"
```

Add `--create-product-scope` only when the resolver reports that the exact company/product directory is missing.

## Source inspection and plan

1. Verify every stored path and SHA-256 from `clean-clip-library.json`.
2. Use `ffprobe` plus contact sheets and start/middle/end frames to inspect the registered originals without mutation.
3. Segment the target script into atomic beats. Map each beat to a stored `clip_id` and exact source range by meaning and reference-edit role, not filename order.
4. Record for every cut: script beat, clip ID, stored path, SHA-256, source in/out, selected-range duration, visual evidence, reference technique/composition, trim, reframe, speed, source-audio policy, captions/post layers, risk, must-show, and hard exclusions.
5. Allow the same registered clip to cover multiple beats only with distinct valid source ranges or an explicitly approved reuse. Never cycle clips merely because there are fewer clips than beats.
6. Report `unmatched_visual_beat` when supplied footage cannot communicate a beat. Ask for another clean clip or a narrower edit decision; do not generate a replacement.

## Gate 1 validation

Block approval when any planned cut has:

- a path or SHA-256 outside the frozen product manifest;
- a missing, corrupt, or unreadable source;
- `source_in < 0`, `source_out <= source_in`, or `source_out` beyond media duration;
- a wrong-company/product substitution or materially wrong script meaning;
- an unregistered derivative as the authoritative source;
- an AI image/video route, generation cost, provider job, or generation retry.

Show generation cost `0`, AI image/video generation `disabled`, the stored-source count, unmatched beats, reused ranges, output ratio, duration estimate, source-audio policy, TTS state, and CapCut target state.

## CapCut and completion

- Keep registered originals immutable. Stage them by verified path and hash, then apply only approved trims, reframes, speed changes, source-audio muting, captions, TTS, and edit effects in the CapCut draft.
- Default source audio to disabled. Keep reference-voice TTS as a separate editable asset unless the approved plan explicitly uses source audio.
- Reopen and verify the saved timeline: source hashes, segment order, time ranges, output duration, frame fill/reframe, audio policy, editable TTS/captions, and no AI visual-generation artifact.
- Complete only when all planned beats have valid registered source coverage and the verified CapCut draft/master exists. Otherwise report the exact pending state.
- In the final response link `제품별 저장 클린본 폴더`, `클린본 라이브러리 매니페스트`, CapCut draft/master, QC summary, and workflow manifest.

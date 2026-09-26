# Clean visual reference contract — ai-video-reference-replication

> 이 문서는 `SKILL.md`의 단계 지도에서 분리한 원문이다(2026-09-27, 문구 변경 없음). `references/`·`scripts/` 경로는 스킬 루트(`skills/ai-video-reference-replication/`) 기준이다. 본문의 above/below·위/아래는 `SKILL.md` 단계 지도의 순서를 가리킨다. `SKILL.md`의 폴더 기준·대본 확정·Core contract는 이 단계에도 항상 적용된다.

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

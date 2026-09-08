# Finalized-script visual-detail interview

Use this reference only for Gate 0.5 after the target script is exact. The gate converts an approved script plus the user's existing visual directions into a hash-bound contract before any cut plan. It is not a product-fact interview, a compliance review, or permission to generate media.

## Trigger and stop boundary

Run the gate for all exact-script sources:

- `planned_and_user_approved`;
- `planned_under_end_to_end_delegation`;
- `user_supplied`;
- `reference_transcribed_as_target`.

Wait until the core intake is complete: exact company and product, exact script, reference video, product-detail URL, output ratio, and supplied clean clips when `existing_clean_edit` is selected. Read-only reference and asset inspection is allowed only to make the questions concrete. Do not segment the script, choose a cut count, write prompts, estimate generation cost, invoke TTS, edit CapCut, or submit any provider job until the gate is ready.

## Child-skill call

Invoke `$script-visual-expression-interview` with this integration input:

```json
{
  "interview_profile": "finalized_script_detail",
  "script_source": "planned_and_user_approved|planned_under_end_to_end_delegation|user_supplied|reference_transcribed_as_target",
  "exact_script_path": "absolute path",
  "exact_script_sha256": "sha256",
  "reference_profile": {
    "medium": "observed medium and texture",
    "character_proportions": "observed proportions when applicable",
    "expression_methods": ["observed visual methods"],
    "composition_classes": ["observed composition classes"],
    "native_camera_behavior": ["observed physical camera behavior"]
  },
  "approved_asset_or_clip_inventory": "path or concise exact-product inventory",
  "existing_user_directives": ["exact user quotations"],
  "production_intake": "path/hash and early answers when present",
  "visual_decisions_delegated": "true only within the recorded end-to-end request, excluding user-reserved decisions"
}
```

This profile permits one consolidated turn containing up to six grouped questions. It overrides only the child skill's ordinary three-question ceiling and its exclusion of plan-changing narration normalization, duration, and reference-edit styling. All other child-skill relevance and no-repetition rules remain active.

When `production_intake.delegation.visual_decisions` is true, perform the same analysis and decision audit but do not require an additional questionnaire for those delegated values. Choose from the current script, reference and designated models/sources, record each choice as `user_delegated` with the real delegation quote, and retain any explicit user-reserved question. This is a scoped instruction to the child profile, not a fictional approval or permission to skip media/semantic QC. Questions may be empty when all applicable decisions are already answered or delegated.

## Decision audit

Audit every category below, but ask only those that are both applicable to the script and unresolved. Never turn the list into a fixed questionnaire.

1. **Primary subject and location** — exact person, age coding, identity traits requested by the user, body area, object, ingredient, room, outdoor location, or other main visible subject.
2. **Problem or Before state** — visible coverage, severity, density, color, deformation, discomfort performance, realism versus stylization, and hard exclusion line. Use concrete outcomes rather than `강하게` or `자연스럽게` alone.
3. **Use action and mechanism** — who handles the exact product, hand or tool, amount, order, contact point, material behavior, trigger, propagation, and whether the mechanism must be literal, macro, internal, or surface-only.
4. **Result or After state** — exact degree of relief or completion, residual texture, immediate versus delayed result, separate Before/use/After clips, and the unmistakable success frame.
5. **Supporting proof and setting** — additional characters, professional roles, evidence objects, clinic/shop/home/lab setting, authority performance, and whether a script claim needs a literal human action or a deterministic evidence layer.
6. **Plan-changing finish details** — CTA product/person composition; reference-style banner or caption treatment when the user asked to follow the finished reference; exact-script typo, homophone, or pronunciation correction; and target narration duration or cadence only when it changes semantic timing, cut count, or cost.

Do not ask for visual information already fixed by the user's current message, exact approved asset, or reference lock. Do not ask the user to verify or weaken product facts they directly supplied. Do not request broad company history, full evidence packs, budget, publishing, or unrelated production preferences.

## Question construction

- State the relevant observed reference baseline before a question when it helps the user choose, while making clear that it is not an automatic target default.
- Offer concrete A/B/C choices whose visible differences are immediately understandable. Include the affected script beat or scene consequence in the same grouped question.
- Combine details that control one decision, such as body area plus crop, or After percentage plus residual texture.
- Use one consolidated turn. The ordinary target is three to six grouped questions; fewer are valid when the user already fixed most decisions.
- If the user explicitly says `임의로 정하지 마`, `내가 정할게`, or equivalent wording, do not mark any high-impact option as recommended or silently select the reference baseline.
- If the user explicitly delegates a variable with `알아서`, `기본값`, `자연스럽게`, or equivalent wording, choose the narrowest filmable value, state it, and record the delegation quotation.
- Safety or model hard limits are stated as boundaries, not presented as selectable unsafe options.

## Mode boundary

For `ai_generation`, the interview may lock generation-specific character, medium, intensity, action, transformation, and result details. For `existing_clean_edit`, ask only how to choose, trim, reframe, sequence, or caption actions already visible in the registered clips. If no registered clip can show a locked subject/action/result, record `unmatched_visual_beat` and request another clean clip or a narrower edit decision.

## Record contract

Write a machine-readable `visual_detail_contract.json` with at least:

```json
{
  "schema_version": 1,
  "interview_profile": "finalized_script_detail",
  "exact_script_path": "absolute path",
  "exact_script_sha256": "sha256",
  "reference_video_path": "absolute path",
  "reference_video_sha256": "sha256",
  "video_source_mode": "ai_generation|existing_clean_edit",
  "output_ratio": "1:1|9:16",
  "questions": [
    {
      "id": "VDQ-01",
      "affected_script_units": ["stable semantic-unit IDs or exact excerpts"],
      "decision": "visible decision being locked",
      "options_shown": ["concrete visible options"],
      "user_answer_text": "exact user answer",
      "normalized_lock": "machine-readable chosen value",
      "source": "user_direct|user_delegated"
    }
  ],
  "script_normalization": [
    {
      "original": "exact original",
      "proposed": "proposed correction",
      "user_choice": "original|proposed|custom"
    }
  ],
  "locked_visual_directives": {},
  "unresolved_high_impact_variables": [],
  "unmatched_visual_beats": [],
  "ready_for_visual_planning": true
}
```

Preserve exact user wording alongside normalized locks. Compute and record the contract SHA-256 in the run intake, workflow manifest, and final plan. Do not overwrite an earlier contract; create a new version when answers or the script change.

## Re-entry and completion

If the exact script changes, map the changed text to affected question IDs. Invalidate only those answers and any downstream cuts; preserve unrelated locks. Run the consolidated interview again for the invalidated decisions.

Gate 0.5 is complete only when:

- every applicable high-impact variable is user-answered or explicitly delegated;
- script pronunciation or normalization conflicts that affect narration or visible meaning are resolved;
- `existing_clean_edit` has either source coverage or explicit unmatched beats;
- `visual_detail_contract.json` exists, its hash is recorded, and `ready_for_visual_planning` is `true`.

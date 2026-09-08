# Performance-Optimized Execution Contract

This contract improves wall-clock time and credit safety without weakening material-quality gates. It is loaded when the user selects `자동모드` or asks why generation is slow.

## Profiles

Set one run-level `quality_profile`:

- `balanced_auto` for `execution_mode: "auto"` (default): keep every hard failure, run deterministic checks for every output, and reserve deep human review for high-risk/product/warning legacy cuts plus every schema-version-4 semantic-proof cut. Use adaptive still quality and start CapCut as soon as the main visual set and a usable audio candidate exist.
- `precision` for `execution_mode: "precision_planning"`: use the same hard failures but inspect every legacy cut's original start/middle/end frames, every schema-version-4 cut's original start/25%/50%/75%/end frames, and do not defer any explicitly approved reserve set.

The profile changes review scheduling and batching only. It never permits a wrong product, unsafe anatomy, wrong model, wrong ratio/duration, missing provenance, frozen motion, forbidden edit effect, or unverified final TTS to pass.

Adaptive duration does not weaken batching. Schedule independent `3.0 s`, `4.0 s`, and `5.0 s` jobs together while keeping duration in each deterministic submission key. Do not trim away a completed action or success frame merely to standardize clip lengths.

## GPT-only image generation

The video motion provider remains Higgsfield Kling v3.0, but Higgsfield is forbidden for still-image generation. Every new or resumed future image action must use `image_generation_mode: "openai_only"` and `image_generation_route: "built_in_image_gen"` with one built-in OpenAI `image_gen` first-attempt candidate per cut. Record `higgsfield_image_jobs: 0`, `image_api_jobs: 0`, and `image_cli_jobs: 0`. Historical Higgsfield, direct API, or CLI records are read-only provenance and never authorize a new image submission through those routes.

The built-in `image_gen` tool has no documented multi-scene batch parameter; issue one call per distinct scene and run independent calls concurrently. Do not switch to the ImageGen CLI or direct Images API for batching, file-path control, quality, or size.

Start with `openai_concurrency: 5` for a Tier-1 OpenAI account. The OpenAI documented rate limit is IPM/TPM by tier, not a fixed simultaneous-image maximum; lower concurrency on 429/5xx and only raise it after the current account's preflight/headers prove the available limit. This is an internal starting cap, not a provider guarantee or exact images-per-minute promise.

For each cut, retain the OpenAI candidate record even when it is rejected. A candidate key must include the route `built_in_image_gen` so a timeout cannot cause a duplicate submission. Only a QC-passing built-in ImageGen candidate may be passed as Kling's start image; no Higgsfield still, API/CLI still, end image, or local motion fallback is allowed.

## Reference fields without repeated prose

Create one plan-level `reference_profile` with the shared style, expression, composition, and native-camera rules. The five required per-cut fields remain mandatory audit fields, but they may be concise profile IDs or short deltas such as `skin_macro_v1`, `apply_hand_follow_v1`, or `slow_push_in_v1`. Do not repeat the full reference analysis in every prompt and do not run a separate model call just to validate those strings. The linter checks presence and the literal `editing_effects: "forbidden"`; semantic reference fidelity is checked in the normal visual QC pass.

## Adaptive still quality

Use one selected GPT Image 2 start still per cut, but choose candidate quality by failure cost:

- `high`: product master, every `product_presence: required` cut, every high-risk cut, and any cut whose first pilot exposes identity or anatomy drift;
- `low`: low/medium-risk, product-independent atmosphere or mechanism cuts where exact readable identity is not the visual job.

Never lower a required-product or high-risk candidate to save time. Do not regenerate a low-quality candidate automatically; promote it to a high-quality replacement only after a concrete QC failure and within the approved retry boundary. A rejected OpenAI candidate does not authorize an additional attempt or a Higgsfield image fallback.

## Main and reserve scheduling

Separate `main_cut_count` and `reserve_cut_count`; keep main jobs in `cuts[]` and optional alternates in `reserve_cuts[]` so a reserve cannot accidentally satisfy main coverage. The initial batch contains main cuts only. Use `reserve_policy: "on_demand_after_main_qc"` by default:

1. finish and QC all main first attempts;
2. compute whether any script beat lacks a usable clean clip or whether the user requested an alternate expression;
3. submit only the minimum reserve cuts needed, in one bounded batch.

Use `reserve_policy: "approved_upfront"` only when the user explicitly wants every reserve asset generated now. Reserve jobs are never silently counted as main coverage, and their cost is reported separately.

## Idempotent external submissions

Before every paid still/video submission, create a deterministic `submission_key` from the plan hash, cut, stage, attempt number, start-image hash, model, ratio, duration, and sound setting. Claim it in the run's append-only job ledger. If the ledger already contains `submitted`, `submitted_unknown`, `completed`, or `quarantined` for that key, reconcile the provider status and do not submit again. A timeout is `submitted_unknown`, not permission to retry. Store the provider job ID, returned model, response hash, output hash, and cost when known. Retakes use a new attempt number and visible versioned output name.

Use `scripts/submission_ledger.py` for the local claim/record operation. The ledger is a safety barrier against the duplicate-credit failure caused by a delayed provider response; it is not a substitute for checking the provider's job-status endpoint.

```bash
python3 scripts/submission_ledger.py --ledger "/absolute/run/qc/submission-ledger.json" \
  claim --submission-key "<deterministic-key>" --stage video --cut 07 --attempt 1
```

Record `submitted`, `submitted_unknown`, `completed`, or `quarantined` with the same key after the provider response or download check.

## Parallel branches and CapCut barrier

After the early production interview/end-to-end request or a later explicit mode selection establishes `execution_mode: auto`, start the requested visual and TTS branches in parallel. Skip TTS when declined and preserve provided narration for edit-only scope. Do not ask another mode or TTS/edit confirmation. The visual branch may continue main still/video batches while the requested TTS branch performs its bounded generation and QC. Start requested CapCut editing after both of these minimum inputs exist:

- the complete QC-passing main visual set (reserves may remain deferred);
- one usable TTS candidate, approved final TTS, or the user's provided narration for edit-only scope.

Do not wait for optional reserves or strict TTS finalization to create the editable draft. Keep `working_audio` visibly distinct from `final` and rebuild the sync map only if the audio hash changes.

## Tiered review

Run objective media probes and start/middle/end extraction for every clip. In `balanced_auto`, assign:

- `deep`: high-risk, product-visible, or any warning/uncertain cut; inspect original-resolution frames and the product-integration criteria;
- `contact_sheet`: low/medium-risk clean cuts with no warning; inspect the compact sheet and open originals only if the sheet is ambiguous.

In `precision`, assign `deep` to every cut. Record the tier in `qc-summary.json` so a fast run is auditable rather than silently skipping review.

Regardless of profile, assign `deep` to every schema-version-4 cut and review start, 25%, 50%, 75%, and end at original resolution. Record evidence for every semantic unit and validate the separate `semantic-visual-qc.json` with `scripts/validate_semantic_qc.py`. A contact sheet may accelerate scanning but cannot be the sole semantic approval evidence.

Paid semantic retries remain zero by default. Automatic execution may make only the number of narrow cut-local retries explicitly shown and approved in Gate 1, and only while the numeric credit ceiling remains unexceeded. A missing ceiling, failed provider reconciliation, or exhausted allowance stops that cut at Gate 3 without slowing unrelated authorized work.

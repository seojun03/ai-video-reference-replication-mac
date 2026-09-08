# Product Visual Source Pack Schema

상세페이지와 업체·제품 자산 라이브러리에서 확정한 정보를 영상 기획에 넘길 때 이 구조를 사용한다. 페이지에 없는 정보는 추정해 채우지 말고 `확인 필요` 또는 공개된 `가정`으로 표시한다.

## Contents

1. Source Snapshot
2. Library Resolution
3. Official Product Source and Master Anchor
4. Visible Product Material
5. Ingredients, Build and Origin
6. Core Visual Distinction
7. Setting and Use Action
8. Existing Visual Expressions
9. Evidence and Deterministic Post
10. Asset Manifest
11. Script Visual Coverage
12. Prohibited Inferences and Handoff Status

## 1. Source Snapshot

- `company_name:` 사용자가 직접 입력한 업체명
- `product_name:` 사용자가 직접 입력한 제품명
- `product_detail_url:` 사용자 지정 상세페이지 URL
- `checked_at:` 확인 시각
- Page access state
- Source limitations
- Page identity match result

## 2. Library Resolution

- `library_root:` `${VIDEO_PRODUCT_LIBRARY_ROOT}`
- `library_resolution_status:` `existing_product`, `existing_company_new_product`, `new_company_product` 또는 `ambiguous`
- Company directory
- Product directory
- Product manifest path
- Exact normalized match evidence
- Existing approved assets selected for reuse
- Legacy candidates inspected but not automatically approved

## 3. Official Product Source and Master Anchor

- Official source asset IDs for front, back, side, individual unit, opened state and bundle
- Selected ImageGen edit target
- Existing approved master match result
- `approved_product_master_asset_id:` asset ID 또는 `pending`
- Deterministic label or logo asset ID
- Packaging silhouette, proportions, material, colors and label treatment
- Parts that must remain official pixels
- `product_master_status:` `approved_existing`, `planned_imagegen`, `qc_passed`, `rejected` 또는 `blocked`
- Master QC comparison result
- Actor or model identity exclusion

## 4. Visible Product Material

- Content form
- Color
- Particle size or surface
- Viscosity or transparency
- Dry state
- Contact trigger
- Observed transformation
- Settled final state
- Unknowns that must not be invented

## 5. Ingredients, Build and Origin

- Representative ingredients or parts
- Exact page wording
- Visible appearance
- Source or origin setting
- Manufacturing or processing sequence
- Page claims versus confirmed package facts

## 6. Core Visual Distinction

- Ordinary or problem state
- Product-specific action
- Transformation operator
- Viewer takeaway
- Final visible state
- Realism or exaggeration limit

## 7. Setting and Use Action

- Primary setting
- Secondary setting
- User or character
- Hand action and tool
- Interaction order
- Camera-dependent facts

## 8. Existing Visual Expressions

- Reused same-product image or video assets
- Reused product-neutral company expressions
- Reuse scope and approval status
- Compatibility with the current script and designated reference
- Excluded other-product or ambiguous legacy assets

## 9. Evidence and Deterministic Post

- Claims, numbers, certifications, reviews, price, stock and offer assets
- Exact source location and checked date
- Whether the element is `confirmed_page_fact`, `page_claim` or `dynamic_page_state`
- Official product label and logo composite plan
- Approved deterministic overlay only; never generated typography

## 10. Asset Manifest

| asset_id | absolute_path | page_location_or_url | source_class | depicts | approval_status | official_product_anchor | crop_quality | intended_script_beats | treatment | claim_status | notes |
|---|---|---|---|---|---|---|---|---|---|---|---|

`treatment`은 `imagegen_master_source`, `deterministic_product_composite`, `visual_reference_only`, `deterministic_evidence_overlay` 또는 `exclude` 중 하나로 기록한다. `approval_status`는 `candidate`, `qc_passed`, `approved`, `rejected` 또는 `stale` 중 하나로 기록한다.

## 11. Script Visual Coverage

| script_beat | viewer_takeaway | visible_subject | initial_state | trigger_or_action | transformation | final_state | setting | source_asset_or_fact | remaining_assumption |
|---|---|---|---|---|---|---|---|---|---|

## 12. Prohibited Inferences and Handoff Status

- 페이지에 없거나 외부 증빙이 없는 효능·수치·비교 우위
- 유사 제품에서 가져온 포장, 원료, 공정 또는 물성
- 사용자가 허용하지 않은 상세페이지 모델의 얼굴·정체성
- 생성 모델이 다시 그린 제품 라벨, 로고, 인증, 가격 또는 후기
- Missing visual-critical facts
- Disclosed assumptions
- Deterministic post assets
- `ready_for_visual_planning: yes|no`
- `ready_for_generation: yes|no`

`ready_for_visual_planning: yes`는 Gate 1 계획을 작성할 수 있다는 뜻이다. `ready_for_generation: yes`는 검수된 제품 마스터가 매니페스트에 승인되어 컷 이미지를 생성해도 된다는 뜻이다. ImageGen 제품 마스터가 아직 계획 상태면 전자는 `yes`, 후자는 `no`일 수 있다.

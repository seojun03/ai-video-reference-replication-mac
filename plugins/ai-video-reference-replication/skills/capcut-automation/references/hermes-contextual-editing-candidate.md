# Hermes 문맥 편집 후보 라우팅

이 문서는 run contract가 `mode=style_learning`이며 `mode_inputs.candidate_id=contextual-persuasion-editing-20260817-v001`일 때만 연다. 완료본 3개의 native CapCut timeline에서 추출한 문맥 반응을 새 대본 challenger plan으로 평가하기 위한 후보 경로다. stable style, 자동 승인 또는 모든 영상의 기본 화면 스타일이 아니다.

## 학습된 행동

- 통증·증상은 짧은 부정 확인음과 shake/punch 계열을 선택할 수 있지만 인물을 희화화하지 않는다.
- 경고·공포 결과는 impact/break 계열과 monochrome/red warning 계열을 제한적으로 쓴다.
- 수치심·사회적 불편은 낮은 강도 또는 무음 hold를 우선하고 코믹·굴욕 효과를 금지한다.
- 문제 원리는 원인 강조, 제품·성분 원리는 clean focus와 설명 overlay를 우선한다. literal Foley는 화면 동작이 있을 때만 허용한다.
- 증거·수치는 clean informational 처리를 기본으로 하고 낮은 확인음만 선택적으로 허용한다.
- 혜택 과정·결과는 문맥 전환이 분명할 때만 밝은 payoff를 쓴다.
- 혜택, 긴급성, CTA를 한 덩어리로 취급하지 않는다. 각 의미 비트마다 효과 또는 무음을 따로 결정한다.
- 연결 문장은 무음과 hold가 정상 결정이다.

## Runtime job 계약

`style_learning/contextual_editing_runtime_job.v1.template.json`을 현재 작업의 값으로 채운다. `source_revisions`의 run context, script, voice, alignment는 모두 현재 job의 SHA-256이어야 한다. 사건은 30fps frame 구간과 실제로 증명 가능한 anchor만 가진다.

- `sensitive_context`: `none`, `medical`, `proof`, `shame` 중 하나
- `positive_payoff_allowed`: 현재 job에서 민감 효능 구간의 긍정 payoff를 허용했는지
- `playful_offer_sfx_allowed`: 현재 브랜드 톤이 금전·장난스러운 혜택음을 허용했는지
- `allowed_experimental_rule_ids`: 단일 source 근거 규칙을 현재 challenger에서 평가하도록 사용자가 범위를 명시했을 때만 넣는다. 기본값은 빈 목록이다.

다음 명령은 CapCut을 수정하지 않고 격리된 후보 plan과 receipt만 만든다.

```bash
python3 "${CAPCUT_AUTOMATION_ROOT}/scripts/plan_contextual_editing_job.py" \
  --run-contract RUN_CONTRACT \
  --job CONTEXTUAL_RUNTIME_JOB \
  --candidate-dir "${CAPCUT_AUTOMATION_ROOT}/style_learning/candidates/contextual-persuasion-editing-20260817-v001" \
  --output-dir ISOLATED_OUTPUT_DIR
```

성공 상태는 `candidate_plan_ready_for_review`다. 이것은 timeline 적용 승인이 아니다. concrete 효과음은 [Hermes 기본 효과음 라우팅](hermes-default-sfx-routing.md)이 승인된 442개 asset index에서 다시 선택하고 hash-bound receipt를 내야 한다.

## 결정적 hard gates

- candidate verification 상태가 `verified_candidate_evidence`가 아니면 중단한다.
- run contract의 job ID·candidate ID·hash와 runtime job이 다르면 중단한다.
- word alignment가 없으면 `visual_action_start`, `cut_start`, `semantic_event_start` 중 선언된 anchor만 사용한다. 모두 없으면 효과음을 생략한다.
- 승인된 asset family가 없으면 다른 소리로 대체하지 않고 생략한다. 현재 camera와 water/liquid family는 승인 자산이 없어 생략 대상이다.
- 분당 효과음은 최대 24개, 한 의미 비트의 primary accent는 1개다. 배치 순서상 같은 family가 연속되면 근거 tier·문맥 중요도·강도·확신도가 낮은 쪽을 생략한다.
- `blur`, `blur_in`은 source evidence로만 보존하고 새 산출물에서는 `none`으로 억제한다.
- candidate minimum confidence 0.72 미만은 효과음과 장식 visual을 모두 생략한다.
- 단일-source 규칙은 current job allowlist가 없으면 생략한다.
- 의료·증거·수치심 문맥의 과한 payoff, 긍정 희화화, 공포 과장은 생략한다. 사용자 제공 제품 문장의 의미와 강도 자체를 약화하지 않는다.

## 피드백과 재사용

candidate plan을 적용한 challenger와 기존 편집 baseline을 같은 대본·음성·자산 조건으로 비교한다. 사용자가 직접 고친 결과가 있으면 자동본과 수정본의 사건 role, 선택/생략, anchor, 강도, 자막·화면·컷 차이만 pending evidence로 캡처한다. 특정 절대 타임코드·제품명·폰트·색·asset ID는 일반화하지 않는다.

사용자 선호가 확인되지 않은 결과는 다음 작업에 자동 승계하지 않는다. 서로 다른 golden job 3개의 A/B에서 objective gate 회귀 없이 challenger가 모두 선택되고 사용자가 재사용 범위를 명시 승인해야만 growth controller의 stable 승격 심사로 보낼 수 있다.

## 증거와 범위

- 후보: `${CAPCUT_AUTOMATION_ROOT}/style_learning/candidates/contextual-persuasion-editing-20260817-v001`
- 최종 짧은 unseen-script 실행: `style_learning/contextual_editing_generalization_runs/v2-20260818-009`
- 최종 긴 반복-role 실행: `style_learning/contextual_editing_generalization_runs/long-20260818-002`
- 검증 범위: 문맥별 semantic plan, frame anchor, 밀도·반복·asset·blur gate
- 검증하지 않은 범위: 실제 concrete SFX 청취 품질, CapCut 저장본 적용, GUI 확인, export 영상 품질

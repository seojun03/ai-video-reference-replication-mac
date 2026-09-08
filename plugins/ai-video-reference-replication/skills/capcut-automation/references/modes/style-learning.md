# Style Learning 모드 플레이북

공통 우선순위·안전 규칙은 부트로더와 `run_contract.md`가 소유한다. 학습은 글을 추가하는 과정이 아니라, 기존 규칙 하나를 더 나은 규칙 하나로 교체하는 검증 루프다.

## 진입 조건

- `mode=style_learning`이고 사용자가 새 style candidate 작성을 명시했다.
- 사용자 피드백 원문, baseline artifact, source provenance가 있다.
- 계약에 source provenance, 후보 scope, 금지 자산, 평가 기준이 고정돼 있다.
- 기존 stable recipe 적용은 `style_apply`로 라우팅한다.

## 권한 경계

- **Hermes 자동 approve 금지.** 분석 성공, reviewer 동의, 사용자 침묵은 승인이 아니다.
- **stable recipe 직접 쓰기 금지.** 기존 recipe를 덮어쓰거나 Hermes가 registry를 수정하지 않는다.
- Hermes와 reviewer가 낼 수 있는 상태 제안은 `reject`, `revise`, `consider_for_approval`뿐이다.
- Hermes는 `target_json_pointer` 하나와 교체값 하나만 제안하며 stable 쓰기 권한이 없다.
- deterministic growth controller만 golden A/B 증거를 검사해 새 patch recipe를 만들고 registry를 atomic 교체할 수 있다. 기존 recipe는 보존한다.

## 실행 순서

1. `scripts/hermes_growth_loop.py capture-feedback`으로 사용자 피드백 원문과 기준 영상·증거 hash를 불변 저장한다.
2. 자동 poller가 zero-tool Hermes에게 원문과 resolved stable recipe를 데이터로 전달해 기존 leaf 교체 후보 하나만 받는다.
3. controller가 stable hash를 고정하고 격리된 challenger registry를 만든다. 이때 stable byte는 변경하지 않는다.
4. 같은 입력으로 baseline과 challenger 결과를 만들고 객관 gate와 artifact hash를 `record-evaluation`에 넘긴다.
5. style·연출 변경은 사용자에게 기술 선택이 아닌 A/B 결과 선호만 묻는다.
6. 서로 다른 golden job 3개에서 challenger가 전부 승리하고 객관 gate 회귀가 0일 때만 controller가 새 patch 버전을 승격한다.
7. 한 job이라도 baseline 선호·동률·gate 실패면 즉시 폐기하고 negative memory로 남긴다. 이 결정 전에는 다음 candidate를 만들지 않는다.

## 필수 산출물

- 피드백 원문, baseline artifact hash, Hermes proposal hash
- 기존 leaf와 교체 leaf의 JSON pointer·값·hash
- 격리 challenger registry와 stable 불변 증거
- golden job별 baseline/challenger artifact·gate·A/B preference
- promoted 또는 rejected decision과 negative memory

## 검증

- candidate가 기존 scalar leaf 하나만 교체하며 complexity delta가 0이다.
- 후보 생성·평가 동안 stable registry와 recipe bytes가 변하지 않았다.
- 서로 다른 golden job 3개의 artifact와 objective gate가 모두 있다.
- style candidate는 모든 job에서 challenger 선호를 받았고 동률이 없다.
- 승격은 기존 파일 덮어쓰기가 아닌 새 patch recipe와 atomic registry 교체로만 이뤄졌다.

## 필요한 deep references

- 신규 style family를 설계할 때만 [스타일 선택 및 신규 등록 워크플로우](../style-selection-workflow.md)의 신규 등록 절을 연다.
- 레퍼런스 source에서 관찰 증거를 추출해야 할 때만 [레퍼런스 스타일 워크플로우](../reference-style-workflow.md)의 분석 절을 연다.
- run contract가 `contextual-persuasion-editing-20260817-v001` 후보를 정확히 선택했을 때만 [Hermes 문맥 편집 후보 라우팅](../hermes-contextual-editing-candidate.md)을 열어 새 대본 challenger plan을 만든다.

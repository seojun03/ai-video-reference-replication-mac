# Feedback Revision 모드 플레이북

공통 우선순위·안전 규칙은 부트로더와 `run_contract.md`가 소유한다. 이 문서는 현재 작업 피드백의 수정·승인 상태 전이만 정의한다.

## 진입 조건

- `mode=feedback_revision`이고 피드백의 job ID가 현재 계약과 정확히 일치한다.
- 적용할 feedback event가 `pending`이며 원문, scope, 대상 revision이 보존돼 있다.
- 계약을 `--include-pending`으로 다시 빌드해 같은 job의 pending만 포함됐음을 확인한다.
- 다른 작업의 pending 피드백은 현재 수정본에 섞지 않는다.

## 상태 흐름

**pending → 수정본 → 사용자 명시 승인 또는 거절** 순서를 지킨다.

- 수정 요청은 먼저 `pending`으로 기록한다.
- 새 수정본을 만들고 기존본과 차이 및 gate 결과를 제시한다.
- 사용자가 재사용을 명시 승인하면 지정 scope에서만 `approved`로 전이한다.
- 사용자가 롤백·사용 금지·품질 저하를 확인하면 `rejected`로 전이해 부정 근거로 남긴다.
- 침묵, 작업 종료, gate 통과는 승인 증거가 아니다.
- `global` 승격은 반복 증거와 별도 사용자 승인 없이 만들지 않는다.

## 실행 순서

1. event identity, 대상 revision, 현재 job scope를 검증한다.
2. 수정 의도를 checkable change set으로 정규화한다.
3. 원본 결과가 아닌 새 revision에 change set을 적용한다.
4. 관련 gate를 다시 실행하고 before/after 차이를 만든다.
5. 수정본을 제시한 뒤 사용자 승인 또는 거절 전까지 `pending`을 유지한다.
6. 명시 응답과 scope를 audit evidence로 기록한다.
7. 사용자가 향후 개선을 원하는 피드백은 `scripts/hermes_growth_loop.py capture-feedback`으로 원문·기준 영상·증거 hash를 저장한다. stable에 바로 반영하지 않는다.
8. growth controller가 만든 challenger는 같은 입력의 기존판과 비교하고, 편집 취향 변경은 사용자에게 기술 승인 대신 결과 A/B 선호만 받는다.

## 필수 산출물

- feedback event와 원문 provenance
- 저장된 `feedback_id`, 현재 `status`, 적용 `scope`, 실제 저장 경로
- revision change set과 before/after diff
- 새 수정본 및 gate 결과
- `approved` 또는 `rejected` 전이의 사용자 증거와 scope

## 검증

- 현재 job과 무관한 pending event가 적용되지 않았다.
- 수정본이 기존 결과를 덮어쓰지 않았다.
- 명시 응답 전에는 active durable rule이 생기지 않았다.
- 승인 scope가 업체·제품·style·job 경계를 넘지 않는다.
- rejected 내용은 active rule이 아니라 negative evidence로만 남는다.
- growth candidate는 한 번에 하나만 활성이며, 기존 rule leaf 교체로 complexity delta가 0이다.

## 필요한 deep references

제품 컨텍스트나 차기 작업 재사용 상태를 기록할 때만 [제품 컨텍스트와 피드백 누적 워크플로우](../product-context-feedback-workflow.md)의 피드백 절을 연다. 영상 gate 재실행이 필요하면 [결과 검수 기준](../quality-check.md)의 영향받은 절만 연다.

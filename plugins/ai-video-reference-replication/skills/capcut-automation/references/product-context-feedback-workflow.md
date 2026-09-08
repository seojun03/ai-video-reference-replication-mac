# 제품 컨텍스트와 피드백 누적 워크플로우

새 영상에서 업체·제품 정보를 즉시 이어 쓰고, 사용자의 수정 피드백을 다음 영상 품질 개선에 반영할 때 이 문서를 따른다.

## 목적

각 업체의 원본 자료는 `${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체>/<제품>/`에 그대로 둔다. 자동화가 만드는 파생 지식만 다음 위치에 저장한다.

```text
${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체>/_knowledge/products/<제품>/
├── product_context.md
├── product_context.json
├── assets.json
├── creative_history.jsonl
├── feedback_events.jsonl
├── accepted_rules.json
└── sync_state.json
```

원본 파일을 이동·복사·이름 변경하지 않는다. 제품 자산은 절대경로로 연결한다.

## 세 종류의 정보를 섞지 않기

1. 제품 사실
   - `제품 정보/product-ad-knowledge.md`와 사용자가 승인한 구조화 사실이 근거다.
   - 문서 안의 `확인된 사실`, `페이지 주장`, `동적 정보`, `확인 필요`, `사용 금지` 구분을 그대로 유지한다.
   - 가격·재고·할인·배송·후기·혜택은 최신 영상 대본에서 사실로 가져오지 않고 게시 직전에 다시 확인한다.

2. 창작 이력
   - 최근 대본의 훅, 소구 순서, 타깃 언어, 화면 표현을 참고하기 위한 자료다.
   - `approved/승인/확정/최종본`이 파일명·경로에 확인된 대본만 승인 예시로 분류한다.
   - 그 외 최근 대본은 `unreviewed`, 폐기·반려 대본은 `rejected`다.
   - 어떤 대본도 성분·효능·수치·인증의 사실 근거로 자동 승격하지 않는다.

3. 사용자 피드백
   - 수정 지시는 먼저 `pending`으로 현재 작업에만 적용한다.
   - 사용자가 수정본을 확인하고 좋다고 명시한 뒤에만 `approved`로 바꾸어 다음 작업에 승계한다.
   - 사용자가 “이전보다 나쁘다”, “롤백”, “이 방식 쓰지 마”라고 하면 `rejected`로 남겨 부정 예시로 사용한다.
   - AI가 사용자의 침묵이나 작업 완료를 승인으로 추정하면 안 된다.

## 새 영상 시작 절차

1. 사용자가 지정한 업체명과 제품명을 정확히 확정한다. 같은 이름이 다른 업체에 있어도 대체하지 않는다.
2. 다음 명령으로 변경된 문서·자산·최근 대본만 증분 색인한다.

```bash
python3 ${PLUGIN_ROOT}/skills/capcut-automation/scripts/manage_product_context.py \
  sync \
  --company "무위록" \
  --product "정화 차전자피"
```

3. 생성된 `product_context.md`를 대본·영상 기획 전에 읽는다. 전체 업체 루트를 매번 재분석하지 않는다.
4. 현재 작업의 `job_id`와 선택 스타일이 정해지면 스냅샷을 만든다.

```bash
python3 ${PLUGIN_ROOT}/skills/capcut-automation/scripts/manage_product_context.py \
  snapshot \
  --company "무위록" \
  --product "정화 차전자피" \
  --job-id "muwirok-20260809-001" \
  --style-id "clean.basic" \
  --include-pending \
  --output "/작업/output/product_context_snapshot.json"
```

5. 대본·소스 선택·효과 계획에는 스냅샷의 현재 제품 자료와 적용 가능한 규칙만 사용한다.
6. 작업 중 제품 문서가 바뀌어도 이미 시작한 작업은 스냅샷으로 재현한다. 다음 작업에서 다시 `sync`한다.

## CapCut 보이스오버 매니페스트 연결

`project_manifest.json`에 다음을 넣으면 초안 생성 전에 제품 자료를 동기화하고 출력 폴더에 `product_context_snapshot.json`을 만든다.

```json
{
  "product_context": {
    "enabled": true,
    "root": "${VIDEO_PRODUCT_LIBRARY_ROOT}",
    "company": "무위록",
    "product": "정화 차전자피",
    "job_id": "muwirok-20260809-001",
    "style_id": "clean.basic",
    "sync_recent_scripts": true,
    "include_pending_for_current_job": true
  }
}
```

기존 매니페스트에 `product_context`가 없으면 기존 동작을 유지한다. 이 연결은 컨텍스트 스냅샷만 만들며 영상을 내보내지 않는다.

## 피드백 기록과 승인

사용자가 특정 결과를 다시 만들라고 하면 먼저 대기 피드백을 기록한다.

```bash
python3 ${PLUGIN_ROOT}/skills/capcut-automation/scripts/manage_product_context.py \
  record-feedback \
  --company "무위록" \
  --product "정화 차전자피" \
  --job-id "muwirok-20260809-001" \
  --scope product \
  --category caption_rhythm \
  --semantic-role hook \
  --before "아침마다 아랫배가 묵직하다면" \
  --after "아침마다 / 아랫배가 묵직하다면" \
  --instruction "초반 훅 자막은 첫 의미 단위를 두 비트로 빠르게 보여준다."
```

범위는 다음처럼 사용한다.

- `job`: 현재 작업에서만 쓰는 예외. 승인돼도 다른 작업에 적용하지 않는다.
- `product`: 같은 업체의 같은 제품 다음 영상에 적용하는 기본값.
- `style`: 같은 제품에서 해당 `style_id`를 선택했을 때만 적용한다.

다른 업체·제품으로 자동 확장하는 전역 범위는 지원하지 않는다. 확대가 필요하면 사용자가 별도 규칙으로 명시해야 한다.

수정본을 만든 뒤 사용자에게 확인을 받는다. 사용자가 승인한 경우 반환된 `feedback_id`로 승인한다.

```bash
python3 ${PLUGIN_ROOT}/skills/capcut-automation/scripts/manage_product_context.py \
  approve-feedback \
  --company "무위록" \
  --product "정화 차전자피" \
  <feedback_id> \
  --decision-note "사용자가 수정본 승인"
```

거절 또는 롤백이면 다음처럼 기록한다.

```bash
python3 ${PLUGIN_ROOT}/skills/capcut-automation/scripts/manage_product_context.py \
  reject-feedback \
  --company "무위록" \
  --product "정화 차전자피" \
  <feedback_id> \
  --decision-note "발화보다 효과가 빨라 이전 방식으로 롤백"
```

승인·거절은 기존 행을 덮어쓰지 않고 `feedback_events.jsonl`에 새 사건으로 추가한다. 나중에 다른 지시가 같은 규칙 자리를 대체해야 하면 새 피드백을 `--supersedes-feedback-id`와 함께 기록하고 승인한다.

## 작업 완료 전 확인

- `product_context_snapshot.json`의 업체·제품이 현재 작업과 정확히 같은가?
- 제품 사실 문장에 원본 제품 문서 근거가 있는가?
- 최근 대본을 제품 효능·가격의 근거로 사용하지 않았는가?
- `pending_current_job_feedback`는 같은 `job_id`에서만 적용됐는가?
- 다음 영상에 반영한 규칙은 모두 `approved`인가?
- 거절된 결과가 `negative_examples`에 남았는가?
- 원본 업체·제품 폴더의 파일이 이동·변경되지 않았는가?
- CapCut 내보내기나 preview 렌더를 실행하지 않았는가?

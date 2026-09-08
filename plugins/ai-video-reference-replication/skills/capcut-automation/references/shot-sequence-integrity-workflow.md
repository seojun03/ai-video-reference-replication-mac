# 영상 컷 순서·중복 무결성 워크플로우

번호가 있는 생성 컷, 스토리보드 또는 장면 기획안의 소스 배정을 CapCut 초안까지 그대로 보존할 때 이 계약을 따른다.

## 1. 권위 있는 컷 계획 고정

- CapCut 변환 전에 스토리보드와 사용자의 수동 교정을 반영한 `expected_shot_ids`를 대본 의미 섹션 순서대로 고정한다.
- 숫자 오름차순은 기본 초안일 뿐이다. 사용자가 의도적으로 순서를 바꿨다면 바뀐 순서를 계획에 명시하고 그 계획을 권위로 사용한다.
- 각 `video_assignments[]`에 `shot_id`, `expected_source_name`, `source_start`, `semantic_tags`, `reason`을 기록한다.
- 실제 소스를 해결한 뒤 파일 SHA-256과 샘플 프레임 시각 지문을 기록한다. 파일명이 달라도 같은 장면이면 같은 소스로 판정한다.

```json
{
  "shot_sequence_integrity": {
    "enabled": true,
    "expected_shot_ids": ["cut-01", "cut-17", "cut-03", "cut-04"],
    "default_reuse": "forbidden",
    "effect_split_policy": "contiguous_same_source_is_one_logical_use"
  },
  "video_assignments": [
    {
      "caption_index": 4,
      "shot_id": "cut-04",
      "expected_source_name": "cut-04.mp4",
      "match": "cut-04.mp4",
      "source_start": 0.0,
      "semantic_tags": ["barrier", "moisture_loss"],
      "reason": "기획안의 네 번째 장벽 손상 장면"
    }
  ]
}
```

## 2. 대체와 재사용 금지

- 자동 QC는 한 컷을 `unusable`로 표시할 수 있지만 다른 컷으로 조용히 교체할 수 없다.
- 계획된 `cut-04` 자리에 의미가 비슷하다는 이유로 `cut-11`을 넣지 않는다. 대체가 필요하면 사용자 승인을 받고 `expected_shot_ids`, `shot_id`, `expected_source_name`, 대체 이유를 함께 갱신한다.
- 서로 다른 의미 섹션에서 같은 경로·SHA-256·시각 지문의 소스를 다시 쓰지 않는다. 의도적 반복은 해당 assignment에 `allow_reuse: true`와 구체적인 `reuse_reason`이 모두 있을 때만 허용한다.
- 스타일 레시피, 효과 길이, 자막 분할 또는 소스 길이 부족을 이유로 source assignment를 바꾸지 않는다. 소스가 부족하면 다른 컷을 넣지 말고 `PLANNED_SHOT_SOURCE_INSUFFICIENT`로 중단한다.
- 크롭·확대·화면 효과를 위해 같은 소스를 연속 분할한 조각은 source 시간이 이어지고 중간에 다른 소스가 없을 때 하나의 논리 컷으로 센다. 비연속 재등장은 재사용이다.

## 3. 저장 초안 역검증

1. 메인 영상 트랙을 target 시작 순서로 읽고 연속된 동일 source 조각을 하나의 논리 컷으로 접는다.
2. 각 논리 컷의 `shot_id`, material path, source SHA-256, source 시작·종료를 권위 계획과 비교한다.
3. 계획된 순서·소스·의미 섹션이 모두 일치하고 계획 밖 재사용·누락이 0개인지 확인한다.
4. 효과 적용 전후에 같은 검증을 반복해 스타일 단계가 소스를 바꾸지 않았음을 증명한다.
5. 다음 값을 `shot_sequence_verification.json`에 기록한다.
   - `planned_shot_count`, `saved_logical_shot_count`
   - `planned_shot_source_mismatch_count`
   - `unplanned_shot_duplicate_count`
   - `planned_shot_omission_count`
   - `shot_order_violation_count`
   - `effect_split_continuity_violation_count`
   - `style_source_mutation_count`

하나라도 0이 아니면 CapCut 초안 생성을 완료로 보고하지 않는다.

## 4. 실패 코드

- `SHOT_SEQUENCE_CONTRACT_REQUIRED`
- `SHOT_PLAN_LENGTH_MISMATCH`
- `PLANNED_SHOT_ID_MISMATCH`
- `PLANNED_SHOT_SOURCE_MISMATCH`
- `PLANNED_SHOT_SOURCE_HASH_MISMATCH`
- `UNPLANNED_SHOT_DUPLICATE`
- `PLANNED_SHOT_OMITTED`
- `SHOT_ORDER_VIOLATION`
- `EFFECT_SPLIT_SOURCE_CONTINUITY_VIOLATION`
- `STYLE_SOURCE_ASSIGNMENT_MUTATED`

사용자가 현재 타임라인을 건드리지 말라고 한 피드백 작업에서는 초안을 수정하지 않는다. 읽기 전용으로 증거만 확인하고 이 계약과 피드백 기록만 갱신한다.

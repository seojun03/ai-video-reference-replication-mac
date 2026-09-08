# Reference Replication 모드 플레이북

공통 우선순위·안전 규칙은 부트로더와 `run_contract.md`가 소유한다. 이 모드는 일반적인 스타일 유사 적용이 아니라 사용자의 명확한 정밀 복제 의도를 다룬다.

## 진입 조건

- `mode=reference_replication`이고 현재 사용자가 정밀 모사를 명시했다.
- 사용자가 최소 사건 단위, 정밀 타이밍, 엄격한 발생 목록 등 **정밀 모사 요청에만** 이 모드를 선택한다.
- 단순히 비슷한 분위기나 저장 스타일 적용을 원하면 `style_apply`로 라우팅한다.
- 계약에 reference source revision, 타깃 대본·자산 허용 목록, fidelity 범위가 고정돼 있다.
- 계약은 `--mode-source` frozen manifest, 반복 가능한 `--allowed-asset`, `--fidelity-scope`로 빌드하며 source hash가 바뀌면 stale로 중단한다.

## 실행 순서

1. 정밀 모사 의도와 증명 가능한 fidelity 범위를 확정한다.
2. 동결 snapshot이 있으면 그 revision을 사용하고 원본을 임의 재분석하지 않는다.
3. 최초 분석이 필요한 경우 reference 사건을 컷·텍스트·그래픽·음향의 경계와 의미 역할로 구조화한다.
4. 사건 종류·순서·상대 타이밍을 새 대본의 같은 역할 앵커에 매핑한다.
5. 레퍼런스 문구·상품 사실·원본 시각 자산은 복사하지 않고 현재 작업 자산으로 치환한다.
6. 편집 가능한 내부 초안을 만든 뒤 저장 사건 inventory를 계획과 비교한다.
7. exact, fallback, unknown, unresolved를 근거와 함께 분리한다.

## 필수 산출물

- reference source provenance와 분석 범위
- reference event graph
- semantic adaptation plan
- 허용·금지 사건 inventory
- fidelity 및 unresolved report
- 저장 초안 역검증 결과

## 검증

- 계획된 사건의 누락·추가·순서 위반과 허용 오차 밖 타이밍이 없다.
- 현재 대본에 없는 사실이나 레퍼런스 전용 리터럴이 남지 않았다.
- 타깃 source는 현재 작업 허용 목록에 속한다.
- 증명하지 못한 자원 identity를 exact라고 보고하지 않는다.
- unresolved 사건이 있으면 전체 fidelity 완료를 주장하지 않는다.

## 필요한 deep references

- 이 모드에서만 [레퍼런스 미시 분석·맥락 치환 규칙](../micro-reference-imitation.md)을 연다.
- 원본 스타일 분석이나 네이티브 자원 증빙이 실제로 필요할 때만 [레퍼런스 스타일 워크플로우](../reference-style-workflow.md)의 해당 절을 연다.
- 사용자 SFX 라이브러리 대조가 요청됐을 때만 [효과음 라이브러리 워크플로우](../sfx-library-workflow.md)의 대조 절을 연다.
- 최종 fidelity 항목이 필요할 때 [결과 검수 기준](../quality-check.md)의 정밀 복제 관련 절만 연다.

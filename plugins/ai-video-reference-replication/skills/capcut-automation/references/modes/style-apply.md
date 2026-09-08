# Style Apply 모드 플레이북

공통 우선순위·안전 규칙은 부트로더와 `run_contract.md`가 소유한다. 이 문서는 검증된 기준본에 선택 스타일을 적용하는 절차만 정의한다.

## 진입 조건

- `mode=style_apply`이고 base gates가 모두 통과했다.
- 계약에 style ID, version, recipe revision과 기준본 지문이 고정돼 있다.
- **stable recipe가 canonical**이며 채팅 설명이나 과거 결과는 이를 덮어쓰지 않는다.

## 실행 순서

1. 계약의 recipe revision과 현재 registry의 revision을 대조한다.
2. 기준본의 영상·음성·논리 자막 경계와 선택 폰트를 읽기 전용 기준으로 고정한다.
3. recipe가 허용한 사건만 의미 앵커에 매핑해 style application plan을 만든다.
4. 기준본이 아닌 새 산출물에 계획을 적용한다.
5. 저장본을 다시 읽어 style 사건과 기준본 불변 항목을 각각 검증한다.
6. recipe provenance와 fallback·unknown을 분리해 보고한다.

## Style A 조건부 경로

Style A가 선택됐을 때만 [Style A 맥락 효과음·화면 반응 워크플로우](../style-a-contextual-sfx-workflow.md)를 **조건부** 로드한다. 구체적인 contextual SFX 사례는 그 문서만 근거로 삼고 이 플레이북에서 일반화하지 않는다.

## 필수 산출물

- recipe ID·version·revision·hash provenance
- 기준본 불변 스냅샷
- style application plan과 적용 보고서
- 저장 사건 inventory와 resource compatibility 결과
- style completion gate 결과

## 검증

- 기준본의 영상·음성·논리 자막 경계와 선택 폰트가 변하지 않았다.
- 저장된 효과·애니메이션·음향 사건은 계획 및 recipe 허용 목록과 일치한다.
- 미해결 네이티브 자원, 계획 밖 사건, 리터럴 레퍼런스 자산 복사가 없다.
- stable recipe 파일을 직접 고치지 않았고 적용 결과를 새 recipe로 승격하지 않았다.
- 필수 gate가 실패하면 스타일 완료 명칭을 사용하지 않는다.

## 필요한 deep references

- 사용자가 문맥 변주를 요청했을 때만 [문맥 변주 디테일 편집 워크플로우](../context-varied-detail-workflow.md)를 연다.
- 사용자 SFX 폴더를 실제로 사용할 때만 [효과음 라이브러리 워크플로우](../sfx-library-workflow.md)를 연다.
- style registry 선택이 해석되지 않을 때만 [스타일 선택 및 신규 등록 워크플로우](../style-selection-workflow.md)의 선택 절을 연다.
- 최종 style gate 항목이 필요할 때 [결과 검수 기준](../quality-check.md)의 레퍼런스·자원 관련 절만 연다.

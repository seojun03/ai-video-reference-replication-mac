# CapCut 자동화 핵심 빠른 참조

정상 fresh-chat 라우트는 `SKILL.md` + 생성된 `run_contract.md` + 선택 모드 플레이북 하나다. 이 문서는 명령이나 실패 코드를 확인할 때만 사용하며 정상 실행 컨텍스트에 추가하지 않는다.

## 컨텍스트 빌드

어느 작업 디렉터리에서든 실제 값을 넣어 실행한다.

```bash
python3 "${PLUGIN_ROOT}/skills/capcut-automation/scripts/build_run_context.py" build --company ... --product ... --job-id ... --mode ... --style ... --font ... --output ...
```

필수 식별자는 업체, 제품, 작업 ID, 모드, 스타일, 폰트다. 출력된 계약 경로와 해시는 이후 변경 명령에 함께 전달한다.

## 모드 값

| 값 | 목적 |
|---|---|
| `base_cut` | 컷·음성·자막·소스 배정의 기준본 생성 |
| `style_apply` | 검증된 기준본에 선택 stable recipe 적용 |
| `reference_replication` | 사용자가 정밀 모사를 명시한 레퍼런스 사건 복제 |
| `feedback_revision` | 현재 작업의 pending 피드백으로 수정본 생성 |
| `style_learning` | 새 스타일 후보 분석과 승인 제안 |

## 계약 확인 순서

1. identity와 mode가 현재 요청과 일치하는지 확인한다.
2. source revisions와 semantic hash가 현재 저장소와 일치하는지 확인한다.
3. must-do, must-not, active rules, matching-job pending을 확인한다.
4. required gates와 mode playbook 경로가 존재하는지 확인한다.
5. 계약 해시를 변경 명령과 완료 게이트에 전달한다.

## 닫힌 실패 코드

- `RUN_CONTEXT_REQUIRED`: 계약 또는 계약 해시가 없다.
- `RUN_CONTEXT_STALE`: 계약 이후 source revision이 달라졌다.
- `RUN_CONTEXT_RULE_CONFLICT`: 동일 우선순위 규칙이 충돌한다.
- `RUN_CONTEXT_MODE_MISMATCH`: 계약 mode가 실행 단계와 달라 해당 mode로 다시 빌드해야 한다.
- `RUN_CONTEXT_STYLE_REQUIRED`: 선택 mode에 필요한 stable style이 없어 Style 선택 뒤 다시 빌드해야 한다.
- `RUN_CONTEXT_MODE_INPUT_REQUIRED`: 고급 mode의 frozen source 또는 compact 범위 입력이 없어 보완 뒤 다시 빌드해야 한다.
- `RUN_CONTEXT_BUDGET_EXCEEDED`: 활성 규칙을 보존한 컨텍스트가 예산을 넘는다.

실패 코드를 만나면 실행을 멈춘다. 이전 계약 재사용, 임의 우선순위 결정, 조용한 규칙 삭제로 우회하지 않는다.

## 실행 인계

- 검사·계획 단계는 읽기 전용이어야 한다.
- 변경 명령에는 빌드가 반환한 계약 경로와 해시를 모두 넘긴다.
- 저장 후 같은 계약과 같은 해시로 완료 게이트를 실행한다.
- 계약과 산출물의 identity, mode, style, font가 다르면 완료로 보고하지 않는다.

## 깊은 참조 원칙

깊은 참조는 선택 모드 플레이북에 적힌 조건이 실제로 성립할 때 해당 문서만 연다. 여러 워크플로를 예방적으로 한꺼번에 로드하지 않는다.

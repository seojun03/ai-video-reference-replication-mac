---
name: capcut-automation
description: Fresh chat에서 계약 기반 CapCut 초안 편집을 안전하게 라우팅한다.
---

## 공유 플러그인 실행 경로

이 문서가 들어 있는 `skills`의 상위 폴더를 `PLUGIN_ROOT`로 확인하고, 먼저 `../../references/recipient-runtime.md`를 읽는다. `${PLUGIN_ROOT}`는 현재 설치된 이 플러그인의 절대 경로로, `${VIDEO_PRODUCT_LIBRARY_ROOT}`와 `${CAPCUT_AUTOMATION_ROOT}`는 수신자 환경의 경로로 해석한다. 하위 스킬은 이 플러그인 안의 형제 폴더를 우선 사용한다. 플러그인 제작·수정·공유 요청은 영상 제작 인터뷰나 유료 생성, 앱 종료를 시작하지 않는다.


# CapCut 자동화 Fresh-Chat 부트로더

## 컷편집 요청의 우선 연결

`컷편집 해줘`, `컷편집해줘`, 일반 무음 정리·대화 자막 싱크 요청은 아래 레거시 인터뷰·컨텍스트 빌드 전에 [공통 컷편집 스킬](../capcut-cut-edit/SKILL.md)로 연결한다. 사용자가 승인한 실제 첫 발음 상승·자연스러운 짧은 쉼·기본 자막·영상 컷 0프레임 일치를 적용하며 스타일·폰트·자막 포함 여부를 다시 묻지 않는다. `base_cut`을 다른 명시적 제작 모드의 일부로 수행할 때도 음성·쉼·자막 타이밍은 공통 스킬을 따른다.

이하 스타일 인터뷰·레거시 계약·Hermes 효과음 단계는 사용자가 그 제작/스타일 작업을 명시한 경우에만 적용한다. 일반 컷편집을 그 경로로 돌려 스타일 질문이나 효과음을 추가하지 않는다. 레거시 쓰기 차단과 원본 보호를 해제하는 예외는 아니다.

이 스킬은 대화 기억 대신 결정적 run contract를 사용해 편집 가능한 CapCut 초안을 만든다. 긴 편집 규칙은 선택 모드 플레이북과 조건부 deep reference가 소유하며, 이 파일은 시작·안전·승인·완료 계약만 유지한다.

## 사용 조건

- 자동 컷, 음성·자막 싱크, 스타일 적용, 레퍼런스 정밀 모사, 피드백 수정, 스타일 학습 요청에 사용한다.
- 원본을 직접 수정하거나 기존 결과를 덮어쓰는 요청에는 사용하지 않는다.
- 현재 채팅의 과거 메시지를 durable state나 승인 증거로 간주하지 않는다.

## 1. 첫 두 질문

도구 실행, 파일 검사, 과거 작업 탐색보다 인터뷰가 먼저다. 사용자가 이미 답한 값은 다시 묻지 않는다. 이전 작업의 선택은 새 작업에 자동 상속하지 않는다.

**첫 질문: 편집 스타일**

```text
어떤 편집 스타일로 진행할까요? 등록된 stable 스타일 또는 새 스타일 후보를 지정해 주세요.
```

첫 응답에는 이 질문만 한다. 사용자가 현재 요청에서 스타일을 이미 명시했다면 반복하지 않는다.

**두 번째 질문: 폰트**

```text
자막 폰트는 기본 Pretendard 계열과 레퍼런스 유사 폰트 중 무엇으로 할까요?
```

스타일 답변을 받은 다음 응답에서만 묻는다. 사용자가 폰트도 이미 명시했다면 반복하지 않는다. 폰트는 기본 자막 생성 전에 고정하며 이후 스타일 단계가 덮어쓰지 못한다.

두 답변 뒤에만 업체, 제품, 작업 ID, 입력 위치, 출력 위치와 실제 결과를 바꾸는 누락값을 한 묶음으로 확인한다.

## 2. Fresh-chat 컨텍스트 빌드

어느 작업 디렉터리에서든 실제 값을 넣어 다음 canonical wrapper를 실행한다.

```bash
python3 "${PLUGIN_ROOT}/skills/capcut-automation/scripts/build_run_context.py" build --company ... --product ... --job-id ... --mode ... --style ... --font ... --output "${CAPCUT_AUTOMATION_ROOT}/.hermes/run-contexts/<job-id>/run_contract.json"
```

고급 모드는 원문 대신 frozen manifest 경로·hash와 compact 경계를 계약에 넣는다.

- `reference_replication`: `--mode-source MANIFEST --allowed-asset ID`를 필요한 만큼 반복하고 `--fidelity-scope SCOPE`를 최소 1개 준다.
- `style_learning`: `--mode-source MANIFEST --style-candidate-id ID --mode-scope SCOPE --forbidden-asset ID --evaluation-criterion CRITERION`을 주며 반복 가능한 항목은 필요한 만큼 반복한다.
- 완료된 native timeline에서 학습한 문맥 편집 후보를 평가할 때만 [Hermes 문맥 편집 후보 라우팅](references/hermes-contextual-editing-candidate.md)을 추가로 열고, 선택한 candidate ID를 run contract에 고정한다. 이 문서는 stable style 적용 경로가 아니다.
- 모든 build에서 현재 mode에 필요한 category와 semantic role만 `--rule-category CATEGORY --semantic-role ROLE`로 각각 최소 1개 지정하며 필요한 만큼 반복한다.
- 현재 실행에만 적용할 지시는 `--runtime-override '{"rule_key":"...","effect":"must_do|must_not","instruction":"..."}'`로 전달해 contract hash에 고정하며 durable 승인 규칙을 수정하지 않는다.
- Hermes 의미 기반 효과음은 모든 영상 작업의 기본값이므로 평소에는 별도 문구나 옵션이 필요 없다. 현재 작업에서 사용자가 `효과음 없이`라고 하면 `--sfx-mode off`, `기존 효과음 유지`라고 하면 `--sfx-mode keep_existing`을 전달하며 이 예외는 다음 job에 승계하지 않는다.
- live mutation 전에는 exact project/source timeline/destination과 bank/profile/selection hash를 frozen manifest에 고정해 `--execution-manifest MANIFEST`로 전달한다. 생략하면 planning-only contract이며 live 실행은 금지된다.
- mode source가 바뀌면 `mode_source_hash`가 달라져 기존 계약은 stale이다. 원문 영상·대본·전체 분석은 Markdown에 복사하지 않는다.

- 성공한 빌드가 낸 `run_contract.json`, `run_contract.md`, `run_contract.commit.json`과 semantic hash/source revisions를 고정한다. commit marker가 두 sibling SHA-256과 hash에 맞지 않으면 실행하지 않는다.
- identity·mode·style·font가 현재 인터뷰와 다르면 실행하지 말고 계약을 다시 빌드한다.
- 변경 명령과 완료 gate에는 machine contract 경로와 hash를 모두 전달한다.
- 계약 없는 채팅 요약, 과거 보고서, 최근 파일을 대신 사용하지 않는다.

### 닫힌 실패 의미

- `RUN_CONTEXT_REQUIRED`: run contract 또는 hash가 없어 변경 실행을 시작할 수 없다.
- `RUN_CONTEXT_STALE`: 계약 뒤 source revision 변경이 감지돼 다시 빌드해야 한다.
- `RUN_CONTEXT_RULE_CONFLICT`: 동일 우선순위 규칙이 충돌해 사용자의 결정을 받아야 한다.
- `RUN_CONTEXT_MODE_MISMATCH`: 계약 mode가 현재 명령과 달라 올바른 mode로 다시 빌드해야 한다.
- `RUN_CONTEXT_STYLE_REQUIRED`: 선택 mode에 필요한 stable style이 없어 Style을 선택한 뒤 다시 빌드해야 한다.
- `RUN_CONTEXT_MODE_INPUT_REQUIRED`: 고급 mode에 필요한 frozen source·허용/금지 범위·평가 입력이 없어 보완 뒤 다시 빌드해야 한다.
- `RUN_CONTEXT_BUDGET_EXCEEDED`: 활성 규칙이 컨텍스트 예산을 넘으며 규칙을 조용히 잘라내지 않는다.
- `RUN_CONTEXT_UNSAFE_OUTPUT`: 계약 경로가 전용 `.hermes/run-contexts/` 경계 밖이므로 source 보호를 위해 중단한다.

오류를 만나면 중단한다. 이전 계약 재사용, 임의 충돌 해소, 규칙 누락으로 우회하지 않는다.

## 3. 우선순위

1. 비가역·원본 보호 hard invariant
2. 현재 실행의 사용자 명시 지시 중 hard invariant와 충돌하지 않는 내용
3. 현재 job과 정확히 일치하는 pending 피드백
4. approved 업체·제품 규칙
5. approved 선택 style 규칙
6. 선택된 stable recipe
7. 기본값

동일 유효 우선순위의 상충 규칙은 `RUN_CONTEXT_RULE_CONFLICT`로 멈춘다. 최신 문장이나 파일 순서로 임의 선택하지 않는다.

## 4. Hard safety invariants

- 원본 미디어를 수정·이동·이름 변경하지 않는다.
- 기존 프로젝트와 기존 타임라인은 변경하지 않는다. 업체명과 정확히 일치하는 기존 프로젝트 안에 고유한 새 timeline을 정확히 1개 만들어 그곳에만 쓴다.
- 정확한 업체 프로젝트가 없거나 둘 이상이면 각각 `CLIENT_CAPCUT_PROJECT_NOT_FOUND`, `CLIENT_CAPCUT_PROJECT_AMBIGUOUS`로 중단한다. 임의의 새 프로젝트나 기존 timeline으로 대체하지 않는다.
- 교체·삭제·파괴적 overwrite는 현재 실행의 승인 대상으로 해석하지 않는다.
- 현재 run contract는 export 권한을 발급하지 않는다. 사용자가 export를 요청해도 별도 승인 필드와 gate가 구현된 새 계약 형식이 마련되기 전에는 실행하지 않는다.
- [공통 저장·정상 종료 절차](../capcut-cut-edit/SKILL.md#실행-중인-capcut의-자동-저장정상-종료)에 필요한 최소한의 앱 제어만 허용한다. 실행 중이면 현재 작업 저장 확인 후 직접 정상 종료하며 사용자에게 종료 요청이나 종료 승인 질문을 하지 않는다. 그 외 앱 재실행·GUI 편집은 자동으로 추가하지 않는다.
- watcher·LaunchAgent·cron은 사용자가 정확히 `자동 실행 승인`이라고 말하기 전에는 생성·활성화하지 않는다.
- 흐림·블러 계열 표현과 미해결 native resource를 새 산출물에 넣지 않는다.
- 레퍼런스의 문구, 업체 사실, 원본 영상·이미지·음원을 새 결과에 그대로 복사하지 않는다.
- stable recipe 직접 수정 금지. 선택 recipe와 registry는 읽기 전용 canonical source다.

## 5. 모드 라우팅

컨텍스트 빌드 후 `run_contract.md`와 선택한 모드 플레이북 정확히 1개만 읽는다. 예방적으로 다른 모드나 deep reference를 함께 로드하지 않는다.

| contract mode | 선택 플레이북 |
|---|---|
| `base_cut` | [Base Cut](references/modes/base-cut.md) |
| `style_apply` | [Style Apply](references/modes/style-apply.md) |
| `reference_replication` | [Reference Replication](references/modes/reference-replication.md) |
| `feedback_revision` | [Feedback Revision](references/modes/feedback-revision.md) |
| `style_learning` | [Style Learning](references/modes/style-learning.md) |

모드 플레이북이 지시한 조건이 실제로 성립할 때만 해당 deep reference의 필요한 절을 추가로 연다. 일반 명령 조회가 필요하면 [핵심 빠른 참조](references/core-quick-reference.md)를 사용하되 정상 실행 컨텍스트에는 추가하지 않는다.

## 6. 공통 파이프라인

1. 계약 path·hash·identity·source revisions를 검증한다.
2. 입력 자산과 durable stores를 읽기 전용으로 조사한다.
3. 계약이 지정한 정확한 기존 업체 프로젝트·고유한 새 timeline과 출력 경계를 확정한다.
4. `base_cut` 기준본에서 컷·최종 음성·논리 자막·source assignment를 먼저 완성한다. 자연스러운 연결 발화가 필요한 쇼트폼은 전체 대본 1개의 일관된 테이크를 기본으로 하고, 현재 job의 명시적 승인과 파일 증거 없는 문장별 스플라이싱·돈너 테이크 혼합·부분 배속·후처리 스트레치를 완료품으로 쓰지 않는다. `클린본 기존 영상 편집`이면 [클린본 프레임 무결성 워크플로우](references/clean-source-frame-integrity-workflow.md)와 [인물·제품 프레이밍 확장](references/clean-source-subject-framing-workflow.md)을 열고, 컷별 소스 SHA-256·실제 source range에 결합된 시작·중간·끝 인물·제품 관찰과 소스별 3:4 crop 계획을 편집 전에 만든다. 제품은 salient 추정이 아닌 수동 제품 박스 증거를 쓴다.
5. base gates 통과 뒤 `sfx.hermes_semantic_route`가 must-do이면 [Hermes 기본 효과음 라우팅](references/hermes-default-sfx-routing.md)을 실행해 hash-bound receipt를 얻은 뒤 선택 모드의 스타일·효과·피드백 변경을 적용한다.
6. `style_learning` 계약이 완료 timeline 기반 문맥 편집 후보를 선택했다면 후보 라우팅의 runtime job을 zero-tool Hermes로 먼저 계획하고, 검증된 abstract family만 기본 효과음 라우터의 concrete asset 선택 입력으로 넘긴다. 화면·자막·컷 결정은 challenger 평가 대상으로만 유지한다.
7. 저장 초안을 다시 읽어 계획이 아니라 실제 target/source 구간과 resource를 검증한다. 클린본 편집은 `clean_source_subject_framing_verification.json`의 소스별 crop·scale·transform·source range·중앙·크기·잘림·keyframe 역검증이 pass여야 한다.
8. required gates가 모두 통과한 뒤에만 완료 보고를 만든다.

## 7. Required gates

- 계약 존재·hash 일치·source freshness·mode 일치
- 원본, 기존 프로젝트, 기존 timeline, stable registry의 실행 전후 불변성
- 컷·최종 음성·논리 자막·source assignment의 저장본 역검증
- 최종 음성 hash에 결합된 coherent connected-speech provenance. 전체 대본 테이크가 아닌 seamless comp은 현재 job 명시 승인과 파일 증거가 모두 있을 때만 허용
- 현재 job이 선언한 threshold·retained natural pause를 사용한 source-splice 공백 편집 보고서, 미해결 비의도적 내부 호흡·스플라이스 공백 0건, 음성 속도·피치 무변경. 작업 계획에 명시한 의도적 연출 휴지는 보존
- 공백 편집이 끝난 정확한 최종 음성 hash를 타이밍 권한으로 삼아 영상 컷과 자막을 재구축했으며 두 경계가 같은 frame에서 시작함을 해시 결합 보고서로 역검증
- 클린본 편집은 시작·중간·끝 피사체 관찰 3개와 정확한 소스 SHA-256·실제 구간이 결합되고, 하단 1080x1440 3:4 무대, clip scale 1.0, 기본 1.0배·자동 1.12배 이하·hash-bound 예외도 절대 1.334배 이하, 제품 신원 증거, 소스별 중앙·크기·잘림·저장 crop·transform·source range·keyframe 검증을 통과. 누락·미검출·낮은 신뢰도·opt-out은 blind crop으로 우회하지 않고 완료 차단
- 위 3가지 음성 증거는 `scripts/verify_voice_delivery_gate.py`로 검증하고 `pass` 보고서가 없으면 완료를 차단
- 선택 폰트 유지, 본문 한 줄, 의미 경계, 누락·겹침·임의 대체 없음
- 장식 전 base gate, 스타일 적용 시 recipe provenance와 기준본 불변성
- Hermes route가 must-do이면 request의 `source_revisions.run_context` 일치, zero-tool 실행, `ready_for_capcut_application` receipt와 montage adapter hash 일치
- 문맥 편집 후보를 선택했다면 candidate verification, run context·script·voice·alignment hash, declared frame anchor, 허용 자산 family, 분당 24개 이하, 연속 동일 family 제거, blur 억제, 민감 문맥·단일-source gate가 모두 통과
- 금지 효과·미해결 resource·계획 밖 사건·레퍼런스 리터럴 복사 없음
- GUI·청취·export를 수행하지 않았다면 실제 수행한 것처럼 보고하지 않음

하나라도 실패하면 산출물을 보존하되 완료로 승격하지 않고 실패 코드, 영향 범위, 재개 조건을 보고한다.

## 8. 피드백 상태와 승인 권한

- `pending`: 현재 job 수정본에만 적용하며 다른 작업에는 비활성이다.
- `approved`: 사용자가 재사용 범위와 함께 명시 승인한 규칙만 활성화한다.
- `rejected`: 롤백·금지·품질 저하 피드백을 negative evidence로 보존한다.
- 사용자 침묵, 작업 종료, 자동 gate 통과, reviewer 추천은 사용자 명시 승인이 아니다.
- 자동 승인 금지. Hermes가 수행할 수 있는 전이는 `reject`, `revise`, `consider_for_approval`뿐이다.
- candidate나 수정 결과를 stable recipe에 직접 쓰지 않는다.
- 성장 피드백은 기존 rule leaf 하나를 교체하는 그림자 candidate로만 만들며 신규 규칙을 누적하지 않는다.
- Hermes는 후보만 제안한다. 서로 다른 golden job 3개의 A/B에서 회귀 없이 승리한 후보만 deterministic growth controller가 기존 규칙과 교체한다.
- 한 job이라도 열화·동률·미확인이면 candidate를 폐기하고 negative evidence로 남긴다.

## 9. 완료 보고

- 업체·제품·작업 ID, 선택 mode·style·font
- run contract 경로·hash와 source revision, Hermes SFX route receipt 요약
- 대상 기존 업체 프로젝트·새 timeline 위치와 생성 산출물
- 통과·실패 gate, 미수행 GUI·청취·export, fallback·unknown
- pending 피드백과 사용자 결정이 필요한 항목
- 원본·기존 결과·stable recipe 불변성 확인

검증되지 않은 exact 재현, UI 확인, 청취, export, 승인 또는 완료를 주장하지 않는다.

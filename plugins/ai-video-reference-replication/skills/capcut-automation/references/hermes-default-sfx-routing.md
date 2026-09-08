# Hermes 기본 효과음 라우팅

이 문서는 run contract의 `sfx.hermes_semantic_route`가 `must_do`일 때만 연다. 모든 사용자가 시작한 영상 작업에서 별도 요청 없이 적용하며, 현재 작업의 `--sfx-mode off` 또는 `--sfx-mode keep_existing`만 해당 job을 건너뛸 수 있다.

## 1. 실행 경계

- 이 기본값은 사용자가 시작한 영상 작업 안에서 동기 실행되는 job route다.
- watcher, LaunchAgent, cron, 예약 작업, 백그라운드 감시는 설치하거나 실행하지 않는다.
- Hermes는 `context_engine` zero-tool 구성으로 의미 결정을 제안하며 CapCut 프로젝트나 timeline을 직접 쓰지 않는다.
- 원본 효과음·기존 프로젝트·기존 timeline·stable recipe·registry는 읽기 전용이다.

## 2. Hash-bound request

base cut과 최종 음성 clock이 고정된 뒤 `capcut-hermes-semantic-sfx-request`를 만든다. 업체·제품·job ID는 run contract와 정확히 같아야 하고 `source_revisions.run_context`에는 현재 `run_context_hash`를 넣는다.

각 의미 사건에는 role, 문장, 시작·종료 frame, 허용 function·polarity, 실제 화면·발화 anchor, 발화 구간 RMS를 기록한다. 후보 파일 경로나 gain을 Hermes prompt에 넣지 않고 hash-bound asset index의 opaque ID만 허용한다.

## 3. 기본 라우터 실행

```bash
python3 "${CAPCUT_AUTOMATION_ROOT}/scripts/route_video_job_sfx.py" bind --run-contract RUN_CONTRACT --request-template JOB_SFX_REQUEST_TEMPLATE

python3 "${CAPCUT_AUTOMATION_ROOT}/scripts/route_video_job_sfx.py" run --run-contract RUN_CONTRACT --request HERMES_SFX_REQUEST
```

- route가 기본 `must_do`인데 request가 없으면 `HERMES_SFX_ROUTE_REQUEST_REQUIRED`로 중단한다.
- request identity 또는 `source_revisions.run_context`가 다르면 실행하지 않는다.
- Hermes 결과가 `ready_for_capcut_application`이 아니면 timeline 적용을 시작하지 않는다.
- 성공 결과의 hash-bound receipt를 실행 인계에 사용한다. 보이스오버 manifest는 `hermes_sfx_route_receipt`에 이 경로를 넣고, 다른 적용기는 receipt에서 hash 검증된 `application_plan.json.montage_sfx_config`만 읽는다.
- route가 현재 작업의 `must_not`이면 `--request` 없이 같은 명령을 실행해 skip receipt를 남기며 Hermes를 호출하지 않는다.

## 4. 적용과 완료 게이트

- receipt의 run context hash, application plan hash, montage adapter hash를 적용 직전에 다시 확인한다.
- `manual_events`만 사용하고 자동 파일명 매칭으로 대체하지 않는다.
- 첫 가청음, 의미 anchor, 음성 RMS 기반 gain, peak ceiling, 동시 재생·반복·인접 family 제한을 저장 초안에서 역검증한다.
- 화면 컷·자막 애니메이션과 효과음 의미가 충돌하면 밀도를 채우지 말고 해당 event를 omit 또는 실패로 남긴다.
- receipt, application plan, 실제 적용 결과가 모두 일치할 때만 효과음 gate를 통과시킨다.

## 5. 효과음 피드백

사용자가 직접 수정한 결과는 현재 job의 `pending` 피드백으로 기록하고 수정 전 자동본과 수정 후 정답본을 읽기 전용으로 비교한다. 사건 role, micro-intent, 선택·탈락 이유, anchor, 음량 관계만 추출하며 특정 절대 타임코드나 파일을 다른 영상에 복사하지 않는다.

현재 수정본에 반영하는 것과 다음 영상에 재사용하는 승인은 분리한다. 사용자가 재사용 범위를 명시적으로 승인한 경우에만 `approved` 제품 또는 style 규칙으로 승격하며 Hermes는 자동 approve나 stable recipe promotion을 수행하지 않는다.

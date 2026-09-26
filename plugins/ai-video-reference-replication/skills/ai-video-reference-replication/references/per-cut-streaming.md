# 이미지 완료 즉시 컷별 영상 생성

`ai_generation`의 기본 실행은 `execution_pipeline: per_cut_streaming`이다. 이미지 전체/배치 전체가 끝나는 대기 장벽을 두지 않는다. 승인된 첫 시도 범위에서 `이미지 완료 → 해당 컷 검수 → 누적 중복 검사 → 업로드 → Kling 제출`을 이어가며, 다른 이미지 생성과 이미 제출된 영상 생성은 계속 진행한다.

## 사전 조건

- 정확한 대본 승인, 시각 계약, 제품 마스터/QC, 계획 lint, 비용·작업 수 경계는 유지한다.
- 이미지: 내장 `image_gen`, 컷당 첫 시도 1장. 영상: `kling3_0`, 시작 이미지 1장, 종료 이미지 없음. 기존 클린본 편집에는 이 대기열을 만들지 않는다.
- 공통 얼굴/제품 기준이 필요한 컷은 그 기준을 먼저 확보한다. 이후 독립 컷은 병렬 실행한다.
- 기존 자료와 공통 레퍼런스를 한 번 로드하고 컷별 차이만 추가한다. 제품 정보 저장 완료를 영상 전체 완료까지 미루지 않는다.
- 이미지 동시 실행 기본값은 기존 계획의 상한을 사용하되 내장 도구의 실제 제한/오류에 따라 줄인다. 직접 Images API의 계정 등급을 내장 도구의 확인된 한도로 주장하지 않는다. 영상 동시 실행은 보수적으로 3개부터 시작하고 현재 공급자 상한 및 예산 안에서만 조정한다. 배치 제출 크기와 동시 실행 수는 서로 다르다.

## 컷 완료 이벤트 처리

1. 독립 이미지 호출을 별도로 시작한다. 각 완료 결과를 즉시 저장하고 내장 도구 결과 경로·해시를 기록한다.
2. 해당 시작 이미지를 직접 검수한다. 동작 직전 상태, 인물/제품 식별, 구도와 의미가 맞아야 한다.
3. 지금까지 선택한 모든 시작 이미지와 SHA·지각 해시를 비교하고 누적 연락시트로 장면 다양성을 검수한다. **나중에 만들어질 이미지까지 기다리지 않는다.** 새 이미지가 기존 이미지와 겹치면 새 컷만 보류한다. 동시 완료 컷은 잠금 안에서 차례로 등록해 둘 다 중복 검사를 건너뛰지 못하게 한다.
4. 준비된 컷은 영상 슬롯이 나는 즉시 claim → 업로드/확인 → Kling 제출한다. 준비된 것이 1개면 1개를 제출하고 배치가 차기를 기다리지 않는다. 동시에 여러 개가 준비됐을 때만 도구의 배치 상한 안에서 묶는다.
5. 제출 결과/불명확한 응답을 바로 기록한다. `claimed`/`submitted_unknown`이면 상태를 먼저 대조하며 절대 자동 재제출하지 않는다.
6. 영상 생성 대기 중 다음 이미지 검수·업로드·다른 영상 제출을 계속한다. 완료 영상도 즉시 다운로드·검수한다. 컷별 실패는 격리하고, 공통 모델/제품/도구 오류는 관련 제출을 멈춘다.
7. 마지막 이미지가 등록되면 전체 다양성 검사와 전체 연락시트를 한 번 더 확인한다. 이는 **최종 사용본 확정 조건**이며 첫 영상 제출의 조건이 아니다.

일괄 `Promise.all`이 전체 이미지 세트를 반환한 뒤 영상을 시작하는 구조는 금지한다. 완료 이벤트 큐 또는 `Promise.race` 기반 처리를 사용하되, 실행 셀이 끝나면서 진행 중 도구 호출이 버려지지 않도록 모든 호출을 끝까지 추적/await한다. 장시간 도구 작업은 결과가 생길 때 제어를 돌려주고 상태를 저장한다. 별도 채팅·서브에이전트나 백그라운드 감시기 없이도 동일 작업의 독립 도구 요청으로 병렬화한다.

## 실행 가능한 상태 관리

다음 도구는 로컬 상태·준비된 컷·중복 제출 방지를 관리한다. 실제 생성은 에이전트의 내장 이미지 도구와 Higgsfield 도구로 실행한다. 이것만 실행하고 영상 생성까지 했다고 보고하지 않는다.

```bash
python3 "${PLUGIN_ROOT}/skills/ai-video-reference-replication/scripts/streaming_cut_pipeline.py" \
  --state "<run>/qc/streaming-pipeline.json" init \
  --plan "<run>/cut-plan.json" --ledger "<run>/qc/submission-ledger.json" --video-concurrency 3
```

시작 이미지 검수 파일의 필수 항목:

```json
{
  "image_sha256": "<실제 파일 해시>", "provider": "openai", "route": "built_in_image_gen",
  "tool_result_path": "<내장 이미지 도구가 반환한 원본 경로>",
  "composition_pass": true, "action_ready": true, "scene_variety_pass": true,
  "product_identity_pass": true,
  "compared_with_selected_cut_ids": [1, 2]
}
```

`product_identity_pass`는 제품 필수 컷에 필수다. `compared_with_selected_cut_ids`는 검수 시 이미 선택된 실제 컷 ID 전부이고 첫 컷이면 빈 배열이다. 새 이미지가 추가되어 목록이 달라졌다면 비교 검수만 다시 하고 이미지 생성은 재실행하지 않는다.

```bash
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" accept-start --cut 3 --image "<image>" --review "<review.json>"
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" ready
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" claim-video --cut 3
```

`claim-video`가 `claimed`를 반환한 최초 한 번만 제출한다. 반환 `params`에 업로드 확인된 시작 이미지 media ID를 추가한다. `existing`은 재제출 허가가 아니다. 이 명령이 기존 `submission_ledger.py` 형식으로 원장까지 claim하므로 동일 영상에 두 번째 claim을 만들지 않는다.

```bash
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" record-video --cut 3 --status submitted --job-id "<id>" --model kling3_0
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" record-video --cut 3 --status submitted_unknown
python3 "<scripts>/streaming_cut_pipeline.py" --state "<state>" record-video --cut 3 --status completed --job-id "<id>" --model kling3_0 --qc-pass
```

마지막 명령의 `--qc-pass`는 실제 영상의 기존 의미/동작/제품 QC가 전부 통과한 뒤에만 사용한다. 모델 오류/컷 실패는 `quarantined`로 기록하고 별도 재시도 예산 없이 새 작업을 제출하지 않는다. 타임아웃을 완료/실패로 추정하지 않는다.

이 대기열 helper는 컷별 첫 시도 전용이다. 이미 별도 승인된 재시도는 기존 재시도 원장의 새 attempt 번호/새 버전 경로로 처리하고 첫 시도의 상태를 덮어쓰지 않는다. 실패 컷을 대기열에서 삭제하거나 초기화해 첫 시도처럼 다시 제출하지 않는다.

고위험 파일럿은 준비되는 순서대로 우선 제출한다. 파일럿 결과에 실제로 의존하는 컷만 계획의 `video_depends_on: [컷 ID]`로 연결한다. 관계없는 모든 컷을 파일럿 뒤에 직렬화하지 않는다. 다른 이미지 생성은 파일럿 대기 중에도 계속한다. 준비된 큐가 없는 경우에만 미완료 영상 상태를 기다린다.

완료 전 기존의 전체 컷 수·다양성·영상 QC·비용 검사를 유지한다. 컷별 이미지 완료/검수/영상 제출/영상 완료 시각을 기록해 실제 대기 시간을 비교한다. 속도 배수는 실측 전 약속하지 않는다.

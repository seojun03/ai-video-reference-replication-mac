# 클린본 인물·제품 프레이밍 확장

이 문서는 [클린본 프레임 무결성 워크플로우](clean-source-frame-integrity-workflow.md)를 확장한다. 모든 업체의 `클린본 기존 영상 편집`에 적용하며, 기존 타임라인과 원본은 읽기 전용이다.

## 실행 계약

1. 각 컷에 정확한 원본 절대 경로, SHA-256, 실제 `source_start_seconds`·`source_end_seconds`, `person|product`를 기록한다. `auto`로 주 피사체를 추정하지 않는다.
2. 전체 클립의 첫 프레임부터 쓰는 작업은 기존 `source_start_policy=zero`를 유지한다. 원본 내부 구간을 쓰는 작업은 `source_start_policy=exact_assignment`로 지정하고, `video_assignments[].source_start`·프레이밍 구간·저장 `source_timerange.start`가 마이크로초 단위로 같아야 한다. 0초도 `exact_assignment`에서 유효하다.
3. 회전 메타데이터가 있는 MOV는 encoded width/height가 아니라 ffprobe display rotation을 반영한 표시 width/height로 crop을 계획하고 검증한다.
4. 수정 전에 읽기 전용 planner를 실행한다.

```bash
python3 "${CAPCUT_AUTOMATION_ROOT}/scripts/plan_clean_source_framing.py" \
  --request "/절대경로/clean-source-framing-request.json" \
  --output-root "/전용-job-경계/clean-source-framing"
```

5. planner는 소스별 실제 구간의 시작·중간·끝을 관찰해 하단 1080x1440 3:4 무대용 crop을 만든다. 한 소스 crop을 다른 소스에 복사하지 않는다. 관찰 프레임은 실제 PNG 파일이어야 하고 요청 시각과 실제 추출 시각 오차는 0.051초 이하여야 한다.
6. 인물은 human 검출을 사용한다. 제품은 Apple Vision salient를 제품 신원 근거로 쓰지 않고, 소스 SHA-256·구간·세 시각에 결합된 수동 제품 박스 JSON을 필수로 쓴다.
7. clip scale은 1.0이다. 기본 확대 1.0배, 자동 확대 1.12배 이하이며, 초과는 소스·구간·사용자 승인문에 결합된 hash-bound 예외 영수증이 있어도 1.334배 이하이다. `manual_zoom_approval=true`만으로는 승인하지 않는다.
8. 축소, blind center crop, cover, punch-in, 메인 영상 transform keyframe·intro animation, 프레이밍 opt-out을 금지한다. 미검출·낮은 신뢰도·중심/크기/잘림 실패는 완료를 차단한다.
9. planner가 낸 `framing_plan.json`과 원본 request의 절대 경로·SHA-256을 `clean_source_frame_integrity.subject_framing.plan_path|plan_sha256`에 고정한다. 실행 assignment의 소스·구간·`subject_framing`이 plan의 같은 index와 완전히 같지 않으면 초안을 만들지 않는다.

## 저장본 gate

- `clean_source_frame_verification.json`: 원본·staging SHA-256, speed 1.0, reverse/loop off, 선언한 `source_start_policy` 일치, 저장 source range를 확인한다.
- `clean_source_subject_framing_verification.json`: 모든 메인 영상 컷의 crop·scale·transform·source range·keyframe을 계획과 역검증하고 plan·request 경로·SHA-256을 기록한다.
- 두 파일 모두 pass이고 failure code와 source-start policy mismatch가 0건이어야 한다.
- 이 gate는 계획 JSON이 아니라 실제 저장 초안을 다시 읽은 결과로 판정한다.

승인된 전역 프로필 ID는 `clean-source-subject-framing-global-v001`이다. 프로필·승인 영수증·관찰 프레임은 SHA-256으로 결합하며, 다른 프로필 ID나 해시를 임의 대체하지 않는다.

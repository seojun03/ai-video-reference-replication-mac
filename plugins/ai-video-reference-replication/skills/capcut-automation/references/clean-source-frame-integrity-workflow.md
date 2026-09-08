# 클린본 프레임 무결성 워크플로우

클린본 영상과 CapCut 화면의 프레임이 달라지지 않게 할 때 이 계약을 따른다. 원본 클린본의 픽셀·프레임 순서·PTS가 권위이며, 편집 편의를 위한 길이 연장본·FPS 변환본·업스케일본은 메인 영상 소스로 사용할 수 없다.

## 1. 권위 원본 고정

- 생성 제공자가 만든 최종 클린본 폴더를 `authoritative_root`로 고정한다.
- `prepared-video`, 렌더 검수본, 프록시, 합본, 속도 변경본, 프레임 보간본을 권위 원본으로 승격하지 않는다.
- 각 `video_assignments[]`에 원본의 절대 `expected_source_path`, SHA-256 `expected_source_sha256`, `source_start: 0.0`을 기록한다.
- CapCut에는 원본 경로를 직접 연결하거나 SHA-256이 원본과 같은 byte-for-byte 사본만 연결한다. 컨테이너 재작성·재인코딩·해상도 변환·FPS 변환·길이 연장을 모두 금지한다.

```json
{
  "clean_source_frame_integrity": {
    "enabled": true,
    "authoritative_root": "/절대경로/video",
    "material_policy": "direct_original_or_byte_identical_copy",
    "transcode": "forbidden",
    "source_start_policy": "zero",
    "speed": 1.0,
    "reverse": false,
    "frame_interpolation": "forbidden",
    "effect_split_source_continuity_required": true,
    "verification_filename": "clean_source_frame_verification.json"
  }
}
```

## 2. 컷편집 규칙

- 논리 컷은 클린본의 첫 프레임, 즉 `source_timerange.start=0`에서 시작한다.
- 속도는 정확히 `1.0`, `reverse=false`, `is_loop=false`로 유지한다.
- 클린본보다 긴 구간을 만들기 위해 마지막 프레임 정지, 루프, 광학 흐름, 임의 속도 변경이나 대체 소스를 사용하지 않는다. 이 사용자의 기본 제작은 `video_alignment.short_source_policy: "leave_gap"`으로 클린본을 논리 섹션 시작부터 실제 길이까지만 원속 배치하고 남은 꼬리를 빈 화면으로 둔 채 계속 편집한다. `short_source_policy: "fail"`인 작업만 다음 승인 클린본을 배정하거나 `CLEAN_SOURCE_DURATION_INSUFFICIENT`로 중단한다.
- 확대·크롭·화면 효과는 CapCut의 비파괴 transform/effect 메타데이터로 적용한다. 어떤 효과도 원본 프레임 선택이나 순서를 바꿀 수 없다.
- 한 논리 컷을 효과 때문에 나누면 첫 조각만 0에서 시작하고 다음 조각은 `이전 source_start + 이전 source_duration`에서 정확히 이어야 한다. 중간 프레임 누락·재시작·겹침은 금지한다.
- 24fps 원본을 30fps 프로젝트에 넣더라도 원본 파일을 30fps로 다시 만들지 않는다. 프로젝트의 각 시각은 원본 PTS의 대응 프레임을 읽게 하고 frame interpolation을 사용하지 않는다. 1:1 프레임 스텝이 작업 필수 조건이면 프로젝트 FPS를 원본 FPS로 정한 별도 새 초안에서만 진행한다.

## 3. 저장 초안 역검증

1. 저장된 모든 메인 영상 material 경로를 원본 또는 staging 파일로 해결한다.
2. 원본, staging 파일, 매니페스트 기대 SHA-256이 모두 같은지 확인한다.
3. 저장된 `source_timerange.start`, `speed`, `reverse`, `is_loop`를 다시 읽는다.
4. 효과 분할 조각의 source 구간을 합쳐 원본 프레임이 연속이고 중복·누락이 없는지 확인한다.
5. `leave_gap`이면 각 짧은 클린본의 저장 target/source 길이가 실제 사용 가능한 원본 길이와 같고, 그 끝부터 논리 섹션 종료까지가 정확히 선언된 꼬리 공백인지 확인한다. 선언되지 않은 공백·겹침은 실패한다.
6. 다음 값을 `clean_source_frame_verification.json`에 기록한다.
   - `source_identity_mismatch_count`
   - `source_start_nonzero_count`
   - `source_speed_not_one_count`
   - `source_reverse_or_loop_count`
   - `effect_split_source_continuity_violation_count`
   - `clean_source_frame_integrity_pass`

모든 count가 0이고 pass가 참일 때만 클린본 프레임이 보존됐다고 보고한다.

## 4. 실패 코드

- `CLEAN_SOURCE_FRAME_CONTRACT_REQUIRED`
- `CLEAN_SOURCE_AUTHORITATIVE_ROOT_MISSING`
- `CLEAN_SOURCE_OUTSIDE_AUTHORITATIVE_ROOT`
- `CLEAN_SOURCE_IDENTITY_MISMATCH`
- `VIDEO_DERIVATIVE_REENCODE_DETECTED`
- `SOURCE_START_NOT_ZERO`
- `SOURCE_SPEED_NOT_ONE`
- `SOURCE_REVERSE_ENABLED`
- `SOURCE_LOOP_ENABLED`
- `SOURCE_FRAME_DISCONTINUITY`
- `CLEAN_SOURCE_DURATION_INSUFFICIENT`
- `INTENTIONAL_VIDEO_GAP_DECLARATION_INVALID`
- `INTENTIONAL_VIDEO_GAP_MISMATCH`

사용자가 현재 타임라인을 건드리지 말라고 한 피드백 작업에서는 초안을 수정하지 않는다. 읽기 전용 대조와 이 계약·다음 실행 설정만 갱신한다.

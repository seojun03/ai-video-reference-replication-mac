# 결과 검수 기준

## 내보내기 금지 계약

- 이 검수는 편집 가능한 CapCut 초안과 파일 기반 증거를 대상으로 하며, CapCut 내보내기·렌더 MP4·preview 파일 생성을 허가하지 않는다.
- 아래의 `렌더 bbox`, `렌더 line count`, `UI/렌더`라는 표현은 텍스트 레이아웃 계산이나 편집기 내부 확인 기준이다. CapCut 내보내기 버튼을 누르라는 뜻이 아니다.
- 내보낸 파일에서만 확인할 수 있는 항목은 `not_performed_export_prohibited`로 기록하고 나머지 검증과 분리한다. 사용자가 이 금지를 명시적으로 철회하기 전에는 내보내기를 제안하거나 실행하지 않는다.

## 목차

- 파일 검수
- 타임라인 검수
- 모드별 검수
- 본문 자막 한 줄 게이트
- 기본 본문 자막 스타일 게이트
- 음성·대본·영상 섹션 잠금 게이트
- 효과음 정밀 싱크·단일 배치 게이트
- 완료 보고

## 파일 검수

- 출력 폴더에 SRT와 JSON 보고서가 생성됐는지 확인한다.
- CapCut 초안 폴더에 `draft_info.json`이 있는지 확인한다.
- 초안의 `media` 폴더에 원본 미디어 링크 또는 복사본이 있는지 확인한다.
- 같은 이름의 기존 프로젝트가 의도치 않게 교체되지 않았는지 확인한다.

## 타임라인 검수

먼저 저장 초안·미디어 경로·probe 결과로 다음 세 구간을 구조 검증한다. 포그라운드 검수가 허용된 경우에만 CapCut에서 프로젝트를 열고 재생한다. 사용자가 화면 전환이나 소리 재생을 금지한 백그라운드 안전 모드에서는 앱을 열지 않고 UI·청취 항목을 `pending_foreground_preservation`으로 남긴다.

1. 시작 3~5초
2. 중간의 컷 전환이 있는 구간
3. 마지막 3~5초

다음을 확인한다.

- 모든 영상 material이 실제 파일과 해상도·길이 범위로 해결된다. 포그라운드 검수가 허용되면 검은 화면·오프라인 표시가 없는지 추가 확인한다.
- 모든 음성 material과 source 범위가 해결된다. 포그라운드 검수가 허용되면 레벨 미터와 청취를 추가 확인한다.
- 자막이 실제 발화와 같은 순서다.
- 자막이 문장 또는 의미 단위로 끊긴다.
- 본문 자막이 화면에서 정확히 한 줄로 보이고, 마지막 한 음절만 다음 자막으로 떨어지지 않는다.
- 저장된 모든 본문 자막의 끝에 `.`·`．`·`。`가 없고 `caption_terminal_period_count=0`이다.
- 마지막 음성과 영상이 비정상적으로 잘리지 않는다.
- 시작 위치에서 파형만 비어 있는 구간이 보이지 않는다. 30fps 기준 1프레임 이내의 안전 여유만 허용한다.
- 원본 대본 의미 섹션 직전의 파형 골이 끝나고 발성 에너지가 처음 지속 상승하는 순간이 포함된 프레임에서 대응 자막과 incoming 영상 컷이 함께 바뀐다. 정렬된 첫 단어 timestamp 또는 상승점 다음 프레임까지 기다리면 늦은 컷으로 실패한다. `logical_caption` 모드는 상승점을 포함한 프레임 시작값과 자막·영상 저장 시작이 같고 자막·영상 상호 시작 오차는 `0ms`여야 한다.
- 한 줄 폭 때문에 같은 원본 의미 섹션이 여러 표시 자막으로 나뉜 경우에는 표시 자막만 바뀌고 영상은 유지된다. 어떤 영상 컷도 표시 자막 중간에 들어가지 않는다.

## 모드별 검수

### 말하는 영상 정리

- 삭제 보고서에서 무음·말버릇·연속 반복 사유를 확인한다.
- 문맥상 의도적인 강조 반복이 잘못 삭제되지 않았는지 확인한다.
- 컷 경계에서 첫음절과 끝음절이 잘리지 않았는지 확인한다.

### 보이스오버 몽타주

- 모든 선택 음성이 한 번씩 올바른 순서로 들어갔는지 확인한다.
- 첫 오디오 세그먼트의 `target_timerange.start`가 `0`인지 확인한다.
- 앞 무음이 있던 음성의 `source_timerange.start`가 `0`보다 큰지 확인한다.
- 현재 저장 음성 SHA-256과 `audio_silence_edit_report.json` 또는 `voice_silence_edit_reports`의 `output_audio_sha256`가 일치하는지 확인한다. `status=pass`, `unresolved_internal_breath_gap_count=0`, `source_splice_only=true`, `speech_speed_change_applied=false`, `pitch_shift_applied=false`, `capcut_speed_change_applied=false`가 아니거나 보고서가 없으면 `VOICE_SILENCE_EDIT_REPORT_REQUIRED`, `VOICE_SILENCE_EDIT_AUDIO_HASH_MISMATCH`, `VOICE_INTERNAL_BREATH_SILENCE_UNRESOLVED` 중 정확한 코드로 완료를 막는다.
- 각 오디오 사이에 타임라인 공백이 없는지 확인한다.
- 사용하지 않은 중복 음성 파일이 타임라인에 들어가지 않았는지 확인한다.
- `logical_caption` 모드에서는 영상 컷 수와 원본 `audio_segments[].captions[]` 의미 섹션 수가 정확히 같은지 확인한다. 한 줄 분할 후 표시 자막 수와 비교하지 않는다.
- 각 영상의 target 시작·종료·길이가 대응 의미 섹션과 각각 1ms 이내이고, 영상 source 시작·길이와 material 순서가 매니페스트 할당과 일치하는지 확인한다.
- 저장 영상이 대응 저장 음성 세그먼트 안에 완전히 포함되는지 확인한다. 기본 `fail`은 0초부터 마지막 음성 끝까지 공백·중첩 없이 이어져야 한다. `leave_gap`은 각 영상이 대응 자막·의미 섹션 시작점에 배치된 상태에서 짧은 원본 끝부터 그 논리 섹션 종료까지 선언된 꼬리 공백만 허용한다. 후속 영상을 앞당겨 이어 붙여 후반 전체만 비우는 배열은 실패한다.
- 각 `video_assignments`에 실제 프레임 검수로 확정한 `semantic_tags`, `reason`, `source_start`가 있고 대본의 문제·행동·효능·결과·오퍼 역할과 화면이 맞는지 확인한다.
- 대본 누락 문장이 있으면 완료로 숨기지 말고 보고한다.
- 기본 `single_track_compact`에서는 저장된 비디오 트랙 수가 정확히 1이고, 선언된 `leave_gap` 꼬리 공백 외의 공백·겹침이 없으며 원본 새 영상 material과 source 연속성이 유지되는지 확인한다. 선언된 꼬리 공백이 있으면 `config.maintrack_adsorb=false`인지도 확인하고, 켜져 있으면 `MAINTRACK_ADSORB_ENABLED_WITH_INTENTIONAL_GAPS`로 실패한다. 동시 표시가 필요한 PIP·분할 화면 예외가 없는데 비디오 트랙이 둘 이상이면 `VIDEO_TRACK_COUNT_EXCEEDED`로 실패한다.

### 레퍼런스 기반 편집

- `style_profile.json`과 `style_application_plan.json`이 있는지 확인한다.
- 현재 레퍼런스 파일 경로·지문·새 분석 run ID가 기록됐고 이전 작업 프로필을 묵시적으로 재사용하지 않았는지 확인한다.
- 전체 초안 전에 0~8초 내부 샘플, 나란히 비교한 프레임, `fidelity_report.json`을 만들었는지 확인한다. `reference.approval_required: true`일 때만 사용자 승인을 요구하며, `false`이면 내부 게이트 통과 후 같은 실행에서 전체 초안까지 자동 확장한다.
- 사용자 승인 샘플 또는 내부 게이트 통과 샘플과 본편이 같은 스타일 프로필 해시·폰트 자원·레이어 프리셋을 쓰는지 확인한다.
- 전체 레퍼런스의 프레임 coverage가 `start_frame=0`, `end_frame_exclusive=decoded_frame_count=analyzed_frame_count`인지 확인한다. 다르면 `REFERENCE_FULL_TIMELINE_COVERAGE_INCOMPLETE`다.
- 오디오 스트림이 있으면 `audio_analysis_coverage.start_sample=0`, `end_sample_exclusive=decoded_sample_count=analyzed_sample_count`인지 확인한다. 다르면 `REFERENCE_FULL_AUDIO_SAMPLE_COVERAGE_INCOMPLETE`다. 무오디오 레퍼런스는 probe 근거가 있는 명시적 `not_applicable`만 허용한다.
- 레퍼런스와 완성본의 화면비·FPS가 의도대로 맞는지 확인한다.
- 레퍼런스 29.97fps와 초안 30fps처럼 같은 방송 프레임 계열을 의도적으로 사용할 수 있다. 이 경우 FPS 숫자 자체가 아니라 각 영상의 실제 FPS로 초를 환산한 뒤 의미 트리거 오차가 1프레임 이내인지 확인하고, 허용 사실을 보고서에 기록한다.
- 첫 훅 길이, 평균·중앙 컷 길이, 분당 컷 수를 비교한다. 기본 허용 차이는 ±15%다.
- 오프닝 훅·본문 자막·CTA를 따로 비교하고 텍스트 위치 차이가 화면 높이·너비의 ±2% 이내인지 확인한다.
- 훅·CTA 문구가 현재 대본의 문제·해결·오퍼에서 도출됐고 레퍼런스 문구를 그대로 복제하지 않았는지 확인한다.
- 의도적 다중행 훅·CTA 텍스트의 실제 bbox·외곽선·그림자를 기준으로 행간이 20px 이상이고 `overlap_px=0`인지 확인한다. 이 예외를 본문 자막에 적용하지 않는다.
- 실제 폰트 파일 경로·resource ID·검증 상태, 굵기, 크기, 위치, 색, 외곽선, 그림자, 줄바꿈, 강조 규칙을 비교한다.
- CTA의 pill/박스, 정상가, 할인가, 할인 문구, 이모지, 보조 문구와 본문 카피가 독립 레이어인지 확인한다.
- MP4만으로 확인하지 못한 폰트·효과·레이어는 `unknown` 또는 승인된 `fallback`으로 명시됐는지 확인한다.
- 전환·펀치인·속도·플래시·필터가 같은 의미적 트리거에 배치됐는지 확인한다.
- 레퍼런스에서 관찰되지 않은 범용 필터·반짝이·펀치인·애니메이션을 추측해 넣지 않았는지 확인한다.
- 효과음과 화면 이벤트의 싱크가 1프레임 이내인지 확인한다.
- BGM 분위기·대략적 템포·진입/종료와 내레이션 대비 음량을 확인한다.
- 지원하지 못한 효과, 식별하지 못한 폰트·음악, 권리 문제로 대체한 자산을 목록으로 남긴다.

### 사용자 효과음 자동 배치

- `sfx_index.json`의 파일 수가 실제 지원 오디오 수와 맞고 하위 폴더가 재귀 색인됐는지 확인한다.
- 각 색인 항목에 경로 지문, 길이, 평균·최대 음량, onset·attack·peak·active end, 태그와 근거가 있는지 확인한다.
- `sfx_selection_report.json`에 선택 파일, 점수·2위·이유, target/source 범위, sync mode·point, gain, lane이 있는지 확인한다.
- MP3·AAC 원본이 직접 배치되지 않고 시작 PTS 0의 48kHz PCM 파생본이 분석·배치에 사용됐는지 확인한다.
- `max_duration` 때문에 sync point나 active tail이 잘린 placement가 없는지 확인한다.
- 30ms 일괄 fade가 없고 fade가 active 구간 뒤에만 위치하는지 확인한다.
- `trim_to_active_end: true`이면 각 source 끝이 `max(active_end + active_tail_padding, sync_point + min_post_sync)`에 필요한 범위를 넘겨 불필요한 무음 꼬리를 유지하지 않는지 확인한다.
- 저장된 draft에서 재계산한 sync error가 프로젝트 FPS 기준 1프레임 이내인지 확인한다.
- `allow_layering: false`이면 한 의미 이벤트당 primary 효과음 하나만 배치됐고 보조 후보는 미선택 사유와 함께 보고됐는지 확인한다.
- 기본 `max_simultaneous: 1`이면 저장된 draft의 모든 효과음 세그먼트가 서로 겹치지 않고 효과음 트랙 수가 최대 1인지 확인한다.
- 같은 파일이 설정한 반복 간격 안에서 불필요하게 재사용되지 않았는지 확인한다.
- 각 placement의 `semantic_polarity`와 `asset_polarity`가 같거나 자산이 `neutral`인지 확인한다. 부정 사건에 긍정음을 넣거나 해결·성과·CTA에 부정음을 넣으면 `SFX_POLARITY_MISMATCH`로 실패한다.
- 내레이션을 가리거나 합산 peak가 clipping하지 않는지 확인한다.
- 후보 점수가 낮은 이벤트가 억지로 채워지지 않고 `unfilled_events`에 기록됐는지 확인한다.
- 효과음 폴더가 없거나 비었을 때 프로젝트가 실패하지 않고 효과음 0개와 명확한 경고로 완료됐는지 확인한다.
- 0~8초 샘플 검수 뒤 SFX 자산·sync point·gain이 바뀌었다면 음향 게이트를 다시 수행한다. `approval_required: true`일 때만 사용자 재승인을 요구하고, `false`이면 내부 음향 게이트 재통과로 계속 진행한다.

## 본문 자막 한 줄 게이트

CapCut에 저장된 본문 자막 material과 실제 사용 폰트로 각 세그먼트를 다시 검사한다. 계획 파일이나 원문만 검사해 통과시키지 않는다.

- 텍스트에 실제 줄바꿈 문자 `\n` 또는 `\r`가 없어야 한다.
- 실제 폰트 크기·외곽선·그림자를 포함한 렌더 bbox 폭이 `captions.max_width_px` 이하여야 한다.
- 렌더 line count가 정확히 `1`이어야 한다. CapCut 자동 줄바꿈으로 두 줄이 된 경우도 실패다.
- 공백·구두점을 뺀 표시 글자 수가 `captions.orphan_min_chars` 이상이어야 한다. 한 음절만 남은 끝 조각을 허용하지 않는다.
- 한 줄 폭을 넘긴 원문은 Whisper 단어 경계에서 순차 자막으로 분할되고, 각 자막의 시작·종료가 해당 단어 발화 범위를 포함해야 한다.
- `배변에 필요한 / 수분과 부피감도 부족해집니다`, `그런데 일반 차전자피는 / 물에 뭉치고 거칠어`처럼 한 줄 안전폭을 위한 분할은 표시 줄바꿈이 아니라 구절별 음향 attack/onset이 다른 독립 자막 세그먼트 2개여야 한다. 내부 분할 지점에는 새 영상 컷을 만들지 않는다.
- 훅·CTA의 의도적 그래픽 다중행은 별도 레이어 유형으로 식별된 경우에만 이 게이트에서 제외한다.

하나라도 어기면 `CAPTION_LINE_BREAK`, `CAPTION_BBOX_OVERFLOW`, `CAPTION_RENDERED_MULTILINE`, `CAPTION_ORPHAN_FRAGMENT` 중 정확한 이유를 기록하고 완료하지 않는다.

## 기본 본문 자막 스타일 게이트

레퍼런스나 사용자의 별도 본문 스타일 지정이 없는 기본 컷편집에서는 저장된 `draft_info.json`의 본문 text material과 segment를 직접 검사한다.

- 모든 본문 material의 실제 폰트 경로가 설치된 `Pretendard-SemiBold.otf`이고 크기가 `13.0`, 중앙 정렬인지 확인한다. 로컬 시스템 폰트의 `font_resource_id: ""`는 정상이며 임의 ID가 있으면 실패시킨다.
- 1080×1920 기준 segment transform이 `x=0.0`, `y=-0.20833333333333334`인지 확인한다. 이는 CapCut UI의 X=0, Y=-400이다.
- 배경은 `background_color: "#000000"`, `background_alpha: 1.0`, `background_style: 1`, `background_round_radius/background_height/background_width: 0.0`이어야 한다.
- UI의 배경 X/Y 오프셋 50%는 저장 JSON의 `background_horizontal_offset/background_vertical_offset: 0.0`과 대응해야 한다.
- 자막 분리는 화면 폭만 맞추지 말고 TTS/화자의 실제 호흡과 문법적 결합을 보존해야 한다. 조사, 보조용언, 조건절의 서술부를 서로 다른 자막이나 영상 컷으로 갈라놓지 않는다.
- 별도 스타일을 적용한 실행은 그 근거와 덮어쓴 필드를 보고서에 기록하고 이 기본 게이트 대신 해당 실행의 스타일 계약으로 검증한다.

하나라도 어기면 `DEFAULT_BODY_FONT_MISMATCH`, `DEFAULT_BODY_SIZE_MISMATCH`, `DEFAULT_BODY_POSITION_MISMATCH`, `DEFAULT_BODY_BACKGROUND_MISMATCH`, `CAPTION_SEMANTIC_BREAK_MISMATCH` 중 정확한 이유를 기록하고 완료하지 않는다.

## 음성·대본·영상 섹션 잠금 게이트

`logical_caption` 모드는 계획 파일이 아니라 저장된 CapCut `draft_info.json`의 `클린본 영상`, `최종 음성`, `문장별 자막` 트랙을 다시 읽어 검사한다.

- 원본 `audio_segments[].captions[]` 항목 하나를 논리 의미 섹션 하나로 세고, 저장 영상 세그먼트 수와 정확히 1대1인지 확인한다.
- 각 영상 `target_timerange.start/end/duration`이 대응 논리 섹션의 첫 표시 자막 시작부터 마지막 표시 자막 종료까지와 각각 `video_alignment.tolerance_seconds` 이내인지 확인한다.
- 각 영상의 저장 `material_id`, `source_timerange.start/duration`이 해당 `video_assignments`와 실제로 배치된 값에 일치하는지 확인한다.
- 논리 섹션이 해당 저장 음성 `target_timerange` 안에 완전히 포함되는지 확인한다.
- 저장 영상 첫 세그먼트가 0초에 시작하는지 확인한다. `fail`이면 마지막 세그먼트가 최종 음성 끝에 도달하고 인접 영상 사이에 1ms 초과 공백·중첩이 없어야 한다. `leave_gap`이면 짧은 원본의 실제 끝부터 다음 논리 섹션 시작 또는 최종 음성 끝까지의 선언된 꼬리 공백만 허용하며, 그 밖의 공백·겹침은 실패한다.
- 내부 영상 컷 시각이 어떤 한 줄 표시 자막의 `start < cut < end`에도 들어가지 않는지 확인한다.
- 저장 본문 자막의 material별 `target_timerange.start/duration`을 Whisper 계획값과 비교하고, 인접 본문 자막 사이 공백·중첩을 확인한다.
- 각 논리 섹션의 정규화 텍스트를 Whisper 단어 배열에 단조 정렬해 파형 탐색 앵커만 찾는다. 실제 컷 시각은 단어 timestamp가 아니라 현재 최종 음성을 48kHz PCM, 5ms RMS, 1ms hop으로 측정해 찾은 문장 경계의 안정적인 저에너지 골이다. 가까운 짧은 단어 내부 notch보다 앵커와의 거리·저에너지 지속시간을 함께 점수화해 안정 골 하나를 선택한다.
- `saved_caption_start`와 대응 incoming 영상의 `saved_video_start`는 선택된 골의 같은 30fps 프레임 시작값과 정확히 같아야 한다. 골이 걸친 전체 프레임 범위와 직후 1프레임을 `accepted_first_frame`/`accepted_last_frame`으로 기록하고, 자동 선택 프레임과 저장 프레임이 이 범위 안에 있는지 검사한다. 자막·영상 상호 시작 오차는 항상 `0ms`다.
- trim, TTS 교체, pitch-preserving `atempo`, 속도 변경 후에는 예전 시간을 배속률로 나눈 값을 최종 권한으로 쓰지 않는다. 완성된 음성을 다시 분석한 `waveform_boundary_plan.json`의 `audio_sha256`가 현재 음성과 같고 `timing_authority=final_audio_waveform_not_scaled_old_timestamps`일 때만 저장·완료한다. 예전 타임스탬프를 나눈 계획이거나 저장 초안 시간에서 역산한 자체참조 계획이면 `WAVEFORM_BOUNDARY_PLAN_REQUIRED`로 실패한다.
- 안정된 골을 하나로 확정하지 못하면 forced-alignment 단어 timestamp나 글자 수 비례값으로 대체하지 않고 `WAVEFORM_RISE_ONSET_AMBIGUOUS`로 실패한다. 사용자가 직접 지정한 프레임은 `manual_frame_override`로 저장하되 해당 최종 음성의 SHA-256이 같을 때만 재사용한다. 사용자 프레임을 다른 음성의 고정 offset으로 학습하지 않는다.
- 사용자가 실제 청취를 요청했으면 보고서의 `human_auditory_input_available`, `human_listening_pass`, 경계별 청취 근거를 확인한다. 오디오 입력을 지원하지 않는 실행에서 ASR을 사용한 경우 `human_listening_pass: not_performed`를 기록하며, ASR 검수를 사람 청취 완료라고 표시하면 실패다.
- 30fps 반복소수 프레임 시각은 정수 마이크로초로 내림 저장됐는지 확인한다. `round(n/30*1e6)` 때문에 저장값이 실제 프레임 시작보다 1µs 뒤가 되어 CapCut UI 전환이 다음 프레임으로 밀리면 `FRAME_TIME_MICROSECOND_ROUNDING_LAG`로 실패한다. 대표 경계뿐 아니라 분모가 3인 모든 프레임 시각을 검사한다.
- 문장 폭 분할이나 논리 자막 병합 때문에 단어 정렬이 모호하면 글자 수 비례 fallback으로 완료하지 않고 `CAPTION_TOKEN_ALIGNMENT_AMBIGUOUS`로 실패한다. 엄격 싱크 모드에는 선행 자막 예외가 없으며 레퍼런스에 선행 표시가 있어도 현재 작업 정책과의 의도적 차이로 보고한다.
- 모든 할당에 실제 화면 근거인 `semantic_tags`와 `reason`이 있고, 보고서에 원본 대본·영상 경로·source 시작점과 함께 보존됐는지 확인한다.
- `logical_caption` 엄격 모드에서 Whisper 단어 타임스탬프가 없거나 분석이 실패했으면 비례 분할 결과를 허용하지 않는다.

결과는 `video_alignment_verification.json`, `caption_timing_verification.json`, `reference_animation_verification.json`, `project_report.json`에 저장한다. 하나라도 실패하면 `VIDEO_SECTION_COUNT_MISMATCH`, `VIDEO_SECTION_START_MISMATCH`, `VIDEO_SECTION_END_MISMATCH`, `VIDEO_SECTION_DURATION_MISMATCH`, `VIDEO_SECTION_MATERIAL_MISMATCH`, `VIDEO_SOURCE_START_MISMATCH`, `VIDEO_CUT_INSIDE_CAPTION`, `VIDEO_AUDIO_COVERAGE_MISMATCH`, `VIDEO_TIMELINE_GAP_OR_OVERLAP`, `VIDEO_SEMANTIC_EVIDENCE_MISSING`, `BODY_CAPTION_TARGET_START_MISMATCH`, `BODY_CAPTION_TARGET_DURATION_MISMATCH`, `BODY_CAPTION_TIMELINE_GAP`, `BODY_CAPTION_TIMELINE_OVERLAP`, `CAPTION_WHISPER_ALIGNMENT_UNAVAILABLE`, `CAPTION_TOKEN_ALIGNMENT_AMBIGUOUS`, `WAVEFORM_RISE_ONSET_AMBIGUOUS`, `FRAME_TIME_MICROSECOND_ROUNDING_LAG`, `CAPTION_WAVEFORM_RISE_LEAD_EXCEEDED`, `CAPTION_WAVEFORM_RISE_LAG_EXCEEDED`, `VIDEO_WAVEFORM_RISE_LEAD_EXCEEDED`, `VIDEO_WAVEFORM_RISE_LAG_EXCEEDED`, `CAPTION_TEXT_AUDIO_ORDER_MISMATCH` 중 정확한 코드를 기록하고 완료하지 않는다.
최종 음성 파형 계획 경로에서는 `WAVEFORM_BOUNDARY_PLAN_REQUIRED`, `WAVEFORM_BOUNDARY_AUDIO_HASH_MISMATCH`, `CAPTION_WAVEFORM_BOUNDARY_MISMATCH`, `CAPTION_OUTSIDE_WAVEFORM_VALLEY`, `CAPTION_VIDEO_WAVEFORM_BOUNDARY_MISMATCH`도 동일하게 완료 차단 코드로 취급한다.

## 레퍼런스 자막 애니메이션 1대1 게이트

저장 애니메이션의 개수만 세지 않는다. 전체 레퍼런스의 모든 text lifecycle 사건에 `animation_signature`를 만들고 타깃 표시 자막마다 하나의 `reference_event_id`를 지정한다.

- signature는 `mode: none|in|out|loop|combo`, 표시 이름, resource ID/path, 시작 offset 프레임, 지속 프레임, 반복·파라미터, 근거 프레임을 가진다.
- `cut_on_no_animation`은 이름 있는 애니메이션이 없는 것이 정확한 결과다. `none` 사건에 pop·펀치·페이드가 붙으면 `REFERENCE_CUT_ON_ANIMATION_ADDED`다.
- 논리 자막이 여러 표시 자막으로 나뉘어도 같은 애니메이션을 자동 복제하지 않는다. 각 표시 자막에 별도 사건 매핑이 없으면 `REFERENCE_SPLIT_CAPTION_ANIMATION_DUPLICATED` 또는 `REFERENCE_TEXT_EVENT_MAPPING_MISSING`으로 실패한다.
- 레퍼런스가 여러 signature를 사용했는데 저장 결과가 하나로 축소되면 `REFERENCE_ANIMATION_VARIANT_COLLAPSED`다. 반대로 레퍼런스가 uniform `none`임이 전체 분석으로 증명된 경우에는 동일한 `none` 분포가 정상이다.
- `reference_animation_verification.json`에서 사건 mapping coverage 100%, signature 일치 100%, 계획되지 않은 애니메이션 0개를 요구한다.

## 레퍼런스 효과 화이트리스트 게이트

사용자가 레퍼런스에 없는 효과를 절대 추가하지 말라고 요청한 작업은 저장 초안 전체를 닫힌 목록으로 검사한다. 요청 효과가 “있다”는 것만으로 통과시키지 않는다.

- 모든 허용 사건에 `reference_event_id`, 원본 start/peak/end frame, 의미 앵커, 컷 대비 상대 offset, 타깃 start/duration frame이 있다.
- 가시 효과 envelope와 강한 core가 다르면 envelope 전체를 배치하고 두 범위를 모두 보고한다. core만 맞추고 onset·easing tail을 누락하면 실패다.
- text/video animation, transition, clip/timeline effect, clip/timeline filter, PIP·mask·sticker·overlay, segment/material/top-level keyframe을 모두 발생 단위로 색인한다.
- 관찰되지 않은 범주의 기대 개수는 정확히 `0`이며, 자막의 `none` animation signature도 필수 기대 사건이다.
- 저장 인벤토리는 track name만 보지 않고 track ID, segment ID, material ID, effect/resource ID, 시작·길이, 파라미터, lane, attachment 경로까지 비교한다.
- 같은 이름 트랙 중복, 허용 트랙 안의 추가 segment, 미참조 effect material, 빈 path·placeholder, 숨은 keyframe graph도 계획 외 효과로 센다.
- `reference_effect_inventory_verification.json`의 `effect_event_recall`은 `1.0`, `unplanned_effect_count`는 `0`, `missing_effects`와 `unexpected_effects`는 빈 배열, 모든 expected/saved count는 같고 `strict_effect_inventory_pass`는 `true`여야 한다.
- `unresolved_reference_events`가 비어 있는지도 별도로 검사한다. 비어 있지 않으면 구현된 motion subset의 수·타이밍이 모두 맞아도 `REFERENCE_EVENT_SCOPE_INCOMPLETE`로 전체 충실도 검사를 실패시키고 결과를 `partial_verified`로만 보고한다.
- 원본 CapCut 초안이 없는 MP4 분석에서는 사건 충실도와 자산 동일성을 분리한다. 로컬 fallback package를 썼으면 `asset_identity_exact: false`이고 “원본 효과 자산 100% 동일”로 보고하지 않는다.
- PIP·split의 editable layer stack을 근거 없이 단일 효과로 바꾸지 않는다. 원본 레이어를 재구성할 근거가 부족하면 `REFERENCE_EDITABLE_LAYER_STACK_UNRESOLVED` 또는 명시적 미구현 제한으로 남긴다.
- PIP·split·before/after를 구현했다면 `composite_layout_verification.json`이 있고 expected/saved 사건·component·트랙 segment 수가 모두 같으며, 각 component의 target/source timerange, crop, clip alpha/scale/transform, render order가 계획과 일치하는지 확인한다.
- 레퍼런스가 해당 합성 화면을 하드컷으로 켜고 껐다면 모든 component가 `cut_on_off`이고 animation·transition·common keyframe이 0개인지 확인한다. `all_components_cut_on_off: true`, `objective_composite_pass: true`가 아니면 완료하지 않는다.
- 화면 bbox 계약을 맞췄다는 이유로 원본 source crop 또는 원본 CapCut asset identity까지 동일하다고 보고하지 않는다. `observed_event_fidelity_exact`, `reference_original_source_crop_recovered`, `asset_identity_exact`를 분리한다.

하나라도 어기면 `REFERENCE_EFFECT_EVENT_MISSING`, `REFERENCE_EFFECT_INVENTORY_COUNT_MISMATCH`, `REFERENCE_UNPLANNED_TEXT_ANIMATION`, `REFERENCE_UNPLANNED_VIDEO_ANIMATION`, `REFERENCE_UNPLANNED_TRANSITION`, `REFERENCE_UNPLANNED_VIDEO_EFFECT`, `REFERENCE_UNPLANNED_FILTER`, `REFERENCE_UNPLANNED_COMMON_KEYFRAMES`, `REFERENCE_UNPLANNED_EFFECT_MATERIAL`, `REFERENCE_UNPLANNED_AUXILIARY_EFFECT`, `REFERENCE_UNPLANNED_VISUAL_TRACK`, `REFERENCE_DUPLICATE_VISUAL_TRACK`, `REFERENCE_VISUAL_TRACK_SEGMENT_COUNT_MISMATCH`, `REFERENCE_UNPLANNED_EMBEDDED_KEYFRAMES`, `REFERENCE_EDITABLE_LAYER_STACK_UNRESOLVED`, `REFERENCE_EVENT_SCOPE_INCOMPLETE` 중 정확한 코드를 기록하고 완료하지 않는다.

## 효과음 정밀 싱크·단일 배치 게이트

각 placement는 저장된 CapCut 초안에서 다음을 계산한다.

```text
draft_sync_sec =
    target_timerange.start
    + sync_point_seconds
    - source_timerange.start

sync_error_frames =
    abs(draft_sync_sec - resolved_event_time_sec) * project_fps
```

다음 조건을 모두 통과해야 한다.

- `sync_error_frames <= 1.0`
- `source_start <= sync_point < source_end`
- `min_post_sync_seconds` 이상이 sync point 뒤에 남는다.
- `preserve_active_tail=true`이면 `source_end >= active_end`
- `fade_start >= active_end`
- 스테이징 PCM의 시작 PTS가 0이고 분석 시간축과 일치한다.
- 발화 앵커는 자막 시작이 아니라 실제 정렬된 단어 시각과 비교한다.
- planner와 draft의 source/target duration 차이가 1ms를 넘지 않는다.
- 레퍼런스 동일 자산 표시는 상관 점수·2위 후보·레퍼런스 발생 시각이 있을 때만 허용한다.
- `allow_layering: false`이면 같은 의미 이벤트에 placement가 둘 이상 없어야 한다.
- `max_simultaneous: 1`이면 모든 효과음 트랙의 `target_timerange`를 합쳐 검사했을 때 양의 길이로 겹치는 두 세그먼트가 없어야 한다. 끝점과 다음 시작점이 같은 것은 겹침이 아니다.
- 효과음 placement가 하나 이상이면 저장된 draft의 효과음 트랙 수가 정확히 `1`이어야 한다. placement가 0개면 0개 트랙을 허용한다.
- 각 placement에 대상 자막, 의미 사건, 의미 극성, 자산 극성, 선택 이유가 있고 `polarity_match_pass=true`인지 확인한다.

하나라도 실패하면 `complete` 또는 `maximum_sync_error_frames: 0`으로 보고하지 않는다. `blocked_sync`, `active_tail_truncated`, `codec_clock_mismatch`, `unverified_reference_asset`, `SFX_EVENT_LAYERED`, `SFX_CONCURRENCY_EXCEEDED`, `SFX_TRACK_COUNT_EXCEEDED` 중 정확한 실패 이유를 기록한다.

사용자가 레이어링을 명시적으로 요청해 `allow_layering: true`로 바꾼 경우에만 단일 배치 게이트 대신 승인된 `max_simultaneous`와 트랙 수를 검증한다. 기본 설정을 묵시적으로 완화하지 않는다.

사용자가 작업 중 소리 재생을 금지한 경우 이를 지키되 자동 파형·draft timerange 검증만으로 `청감 검수 완료`라고 표시하지 않는다. `objective_sync_pass`와 `remaining_listening_check`를 분리해 보고한다.

## 흐림·블러 절대 금지 게이트

저장된 새 타임라인의 모든 편집 JSON을 검사한다. `draft_info.json`만 깨끗하고 attachment 또는 backup 초안에 금지 효과가 남은 상태도 실패다.

- `video_effects`, `transitions`, `filters`, `material_animations`에 `흐림`, `흐리게`, `블러`, `blur`, `motion blur`, `Gaussian blur`, `가우시안`, `defocus`, `frosted` 이름·파라미터·자원이 없어야 한다.
- 어떤 segment의 `material_id`·`extra_material_refs`도 금지 material을 참조하지 않아야 한다.
- 모든 영상 material의 `video_algorithm.motion_blur_config`는 `null`이어야 한다.
- segment/material/top-level 키프레임과 텍스트·배경 스타일의 활성 blur 값이 0이어야 한다.
- 복제 기반 수정은 금지 material 삭제 뒤 dangling reference도 0인지 확인한다.
- `blur_effect_verification.json`의 모든 count가 0이고 `blur_effect_free_pass: true`여야 한다.

하나라도 어기면 `BLUR_EFFECT_FORBIDDEN`으로 실패시키며, 레퍼런스 충실도나 동결 레시피를 이유로 예외 처리하지 않는다.

## 완료 보고

다음만 간결하게 전달한다.

- CapCut 프로젝트 이름과 경로
- 최종 길이, 원본 의미 섹션 수, 영상 컷 수, 음성 수, 표시 자막 수
- SRT, `video_alignment_verification.json`, `caption_timing_verification.json`과 보고서 경로
- 영상·음성·자막 최대 구간 오차, 표시 자막 내부 컷 수, 영상 공백·중첩 수
- 제외한 중복 음성 또는 누락된 대본
- 레퍼런스에서 적용한 스타일 요소와 대체한 요소
- 0~8초 스타일 샘플의 사용자 승인 또는 내부 게이트 상태와 `verified`·`fallback`·`unknown` 항목
- 효과음 색인 파일 수, 자동 배치 수, 미충족 이벤트 수와 선택 보고서 경로
- 사람이 마지막으로 확인해야 할 부분

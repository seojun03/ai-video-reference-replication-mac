# 레퍼런스 미시 분석·맥락 치환 규칙

## 적용 조건

다음 중 하나면 이 워크플로우를 사용한다.

- 사용자가 “레퍼런스와 거의 똑같이”를 요청한다.
- 컷·자막·효과·효과음을 최소 단위나 프레임 단위로 분석해 달라고 한다.
- 대표 프레임 수준의 분석으로 만든 이전 결과가 레퍼런스와 다르다고 지적한다.
- 효과 이름·폰트 이름·효과음 싱크를 CapCut에서 다시 확인하고 수정할 수 있어야 한다.

이 모드는 문구를 베끼는 모드가 아니다. 레퍼런스의 편집 사건 문법을 현재 대본의 동일한 의미 역할에 옮기는 모드다.

## 사용자 호출 문구

사용자가 `레퍼런스 정밀 모사 모드로 진행해줘`라고 말하면 이 문서의 전체 규칙을 자동 적용한다. 사용자가 매번 분석 항목을 길게 나열하게 하지 않는다. 다음 상세 호출문은 단순 예시가 아니라 같은 모드의 **실행 계약**이다. 짧은 호출문도 아래 전체 내용을 요청한 것으로 해석한다.

> 레퍼런스 정밀 모사 모드로 진행해줘.
>
> 레퍼런스 영상을 원본 FPS와 48kHz 오디오 기준으로 전체 분석해. 고정 간격 캡처가 아니라 다음 사건의 시작·최고점·종료를 최소 단위로 분해해줘.
>
> - 모든 컷과 장면 전환
> - 장면 내부 확대·흔들림·블러·플래시의 시작·최고점·종료
> - 자막의 등장·완전 표시·강조·퇴장
> - 그래픽·PIP·스티커·화면 효과
> - 효과음의 시작·실제 onset·attack·peak·active end
> - BGM 비트·브레이크와 편집 사건의 싱크
>
> 분석한 사건을 `hook/problem/question/solution/product_reveal/benefit/proof/offer/cta` 역할로 분류하고, 내가 만드는 대본에서 같은 의미 역할을 가진 구간에 사건 순서와 상대 프레임 간격만 옮겨줘.
>
> 레퍼런스의 문구·가격·혜택은 복사하지 말고 현재 대본의 사실과 맥락에 맞게 화면 카피를 새로 작성해줘.
>
> 폰트·자막 애니메이션·영상 애니메이션·화면 효과는 CapCut 목록에서 실제 이름으로 다시 선택 가능한 네이티브 소재만 사용해. 폰트의 `(시스템)`·`none`·빈 이름과 이름이 필요한 애니메이션·효과의 빈 이름·`없음`은 사용하지 마. 단 reference animation signature가 `none`인 세그먼트의 `없음`은 정상 상태로 유지해. 편집 가능 모드에서는 키프레임으로 애니메이션을 흉내 내지 마.
>
> 효과음은 사용자가 지정한 효과음 폴더에서 파형·주파수대·지각상 sync point를 비교하고, 레퍼런스와 일치가 검증된 파일만 `verified_exact`으로 표시해. 확인되지 않은 파일은 `candidate` 또는 `unknown`으로 표시해. 기본값은 효과음 한 트랙과 동시 재생 한 개로 유지해.
>
> 먼저 0~8초 샘플을 만들고 다음 항목을 검증해줘.
>
> 1. 음성·자막·영상 컷·효과음 오차 1프레임 이내
> 2. 일반 본문 자막 한 줄 유지
> 3. 폰트·애니메이션·화면 효과의 CapCut UI 재선택 가능 여부
> 4. 효과음 동시 재생 최대 한 개와 SFX 트랙 최대 한 개
> 5. 레퍼런스의 필수 사건 recall, 계획되지 않은 효과 0개
> 6. 레퍼런스와 다르게 구현된 사건과 그 이유 보고
>
> `reference.approval_required: true`이면 검증 통과와 사용자 승인 뒤 본편으로 확장해줘. 사용자가 전체본 생성을 이미 명시해 `approval_required: false`이면 0~8초 내부 게이트 통과 직후 같은 실행에서 전체본까지 자동 확장하고 샘플에서 멈추지 마. 게이트를 통과하지 못한 항목은 추측 자원이나 키프레임으로 조용히 대체하지 말고 실패 코드와 차이를 보고해.

## 근거 우선순위

1. 같은 레퍼런스를 만든 원본 CapCut `draft_info.json` 또는 `draft_content.json`
2. 레퍼런스 원본 영상·원본 오디오와 사용자가 제공한 자산
3. 렌더 MP4의 전체 프레임·PCM 분석
4. 로컬 CapCut 캐시와 효과음 라이브러리의 후보 대조
5. 시각적으로 가까운 fallback

원본 초안 후보는 프로젝트명만으로 확정하지 않는다. 영상 길이·FPS·해상도, 사용 미디어 경로/지문, 첫 자막과 주요 컷 시각 중 둘 이상이 일치해야 한다. 일치한 원본 초안이 있으면 MP4에서 추정한 효과 이름이나 SFX 후보보다 초안의 실제 자원 ID·경로·source range를 우선한다.

원본 초안이 없으면 MP4에서 관찰 가능한 동작과 음향 사건만 `verified_visual` 또는 `candidate`로 기록한다. 편집 가능한 CapCut 효과 이름이나 원본 효과음 파일을 추측해 `verified_exact`이라고 하지 않는다.

전체 프레임에서 관찰된 PIP·split·mask·overlay를 현재 소스의 editable layer로 재구성할 근거가 없으면 그 사건을 생략한 채 전체 충실도 통과로 표시하지 않는다. `unresolved_reference_events`에 사건 ID와 이유를 기록하고 `REFERENCE_EVENT_SCOPE_INCOMPLETE`로 전체 완료를 차단한다. 검증 가능한 motion subset으로 전체 길이 초안을 만들 수는 있지만 상태는 `partial_verified`이고, 원본 초안이나 분리된 레이어 소스가 제공될 때까지 “100% 동일”이 아니다.

길이·주요 컷 경계가 렌더 MP4와 다른 관련 초안은 폰트·애니메이션·효과·SFX **후보 자원 목록**을 찾는 데만 쓴다. 해당 초안의 타임라인 시각, 자막 문구, source range와 음량은 렌더 레퍼런스의 정확한 근거로 승격하지 않는다. `native_draft_match_status`를 `exact_source`, `related_resource_inventory_only`, `unrelated` 중 하나로 명시하고 `exact_source`가 아닌 초안에서 얻은 값은 `candidate`를 넘을 수 없다.

## 1. 원본 시계 확정

`reference_event_graph.json.source`에 다음을 고정한다.

- reference 절대경로와 SHA-256
- width, height, frame count
- FPS 분수 `fps_num/fps_den`
- 각 프레임 PTS와 VFR 여부
- 오디오 sample rate, channel 수, 시작 PTS, `start_sample`, `end_sample_exclusive`, `decoded_sample_count`, `analyzed_sample_count`
- 분석기 버전과 분석 시각
- 원본 CapCut 초안 경로와 일치 근거

프레임 번호를 단순 `seconds × 30`으로 반올림하지 않는다. `frame × fps_den / fps_num`으로 변환한다. 오디오는 PTS 0의 48kHz PCM 파생본을 만들고 원본을 수정하지 않는다. 오디오 스트림이 있으면 `start_sample=0` 및 `end_sample_exclusive=decoded_sample_count=analyzed_sample_count`가 아니면 전체 분석으로 판정하지 않는다. 오디오가 없으면 probe 근거와 함께 `not_applicable`을 명시한다.

## 2. 사건 추출

“최소 단위”는 고정 길이 조각이 아니라 다음 사건의 시작·peak·끝이다.

### 영상

- hard cut, dissolve, whip, flash
- shot 안의 zoom/punch/rock/blur
- PIP, split, mask, before/after, product macro
- overlay/sticker/effect track
- source motion과 edit motion의 구분

각 후보는 직전 2프레임, 시작, peak, 끝, 직후 2프레임을 근거 이미지로 남긴다.

### 텍스트

- 첫 픽셀 등장
- 완전 표시
- 강조 변화
- 퇴장 시작과 마지막 프레임
- bbox, baseline, 줄 수, 색상별 rich-text range
- 실제 폰트 display name/family/PostScript/path/resource ID
- 입장·반복·퇴장 애니메이션의 이름/ID/경로

새 문구가 첫 프레임부터 완전 표시되면 `cut_on_no_animation`이다. 분위기가 비슷하다는 이유로 pop이나 fade를 추가하지 않는다.

### 오디오

- BGM 시작·beat·break·ducking·끝 tail
- SFX 자산 시작, onset, attack, peak, active end
- 발화 단어 시작·끝
- cut/text/graphic/spoken-word 사건과의 지각 peak offset

SFX는 파일 시작을 무조건 sync point로 쓰지 않는다. 원본 초안이 있으면 저장된 source start/duration/volume을 추출한다. 렌더 MP4만 있으면 자산 대조 점수와 2위 차이가 기준을 통과할 때만 `verified_exact`으로 승격한다.

## 3. 이벤트 그래프

모든 시작·끝 경계를 합친 union timeline을 만들고 다음 구조로 저장한다.

```json
{
  "schema_version": 1,
  "source": {
    "reference_path": "/absolute/reference.mp4",
    "sha256": "...",
    "fps_num": 30000,
    "fps_den": 1001,
    "sample_rate": 48000
  },
  "events": [
    {
      "id": "text-001",
      "modality": "text",
      "kind": "text.enter",
      "start_frame": 45,
      "peak_frame": 49,
      "end_frame_exclusive": 50,
      "semantic_role": "hook_problem",
      "literal_reference_text": "분석 근거 전용",
      "reusable_literal": false,
      "resource": {
        "display_name": "연성",
        "resource_id": "7616274860225891600",
        "path": "/absolute/font.ttf"
      },
      "evidence": ["draft:text-material-id", "frames/f0045.jpg"]
    }
  ],
  "edges": [
    {
      "from": "audio-001",
      "to": "text-001",
      "relation": "syncs_to",
      "offset_frames": 0.2
    }
  ],
  "beats": [
    {
      "id": "beat-001",
      "semantic_role": "hook_problem",
      "start_frame": 30,
      "end_frame_exclusive": 81,
      "event_ids": ["visual-001", "text-001", "audio-001"],
      "mandatory_event_ids": ["text-001", "audio-001"]
    }
  ]
}
```

레퍼런스 리터럴 문구는 증거 필드에만 저장하고 `reusable_literal: false`로 고정한다.

## 4. 새 대본 맥락 치환

`semantic_adaptation_plan.json`을 별도로 만든다.

1. 대본과 Whisper 단어를 `hook/problem/question/solution/product_reveal/benefit/proof/offer/cta` 역할로 나눈다.
2. 각 역할에서 화면 카피가 근거로 삼은 현재 대본 구절을 기록한다.
3. 동일 역할의 reference beat를 연결한다.
4. reference beat 내부 사건의 순서와 상대 프레임 offset을 보존한다.
5. 새 음성 길이에 맞게 역할 구간을 국소적으로 늘이거나 줄인다.
6. 컷·텍스트·SFX는 마지막에 실제 단어·텍스트·영상 사건에 스냅한다.

```json
{
  "target_beats": [
    {
      "semantic_role": "hook_problem",
      "script_evidence": "외출 한 시간 만에 개기름...",
      "generated_copy": "외출 1시간 만에 개기름 폭발?",
      "facts_from_target_script": ["외출 1시간", "개기름"],
      "reference_beat_ids": ["beat-001"],
      "event_mappings": [
        {
          "reference_event_id": "audio-001",
          "target_anchor": {
            "kind": "spoken_keyword_start",
            "text": "개기름"
          },
          "preserve_offset_frames": true
        }
      ]
    }
  ]
}
```

레퍼런스에만 있는 가격·할인율·순위·혜택은 버린다. 현재 대본에 있는 사실을 같은 시각 계층과 리듬으로 새로 압축한다. 문구가 길면 의미를 먼저 줄이고 승인된 최소 폰트 크기까지만 축소한다.

## 5. CapCut 컴파일 규칙

- 텍스트는 실제 `TextSegment`로 둔다.
- 폰트는 실제 CapCut native record 또는 검증된 시스템 폰트 절대경로를 사용한다.
- 편집 가능 모드는 이름 있는 `material_animations`와 `video_effects`만 쓴다.
- 애니메이션 시작과 지속시간은 프로젝트 FPS의 정수 프레임으로 양자화하고, CapCut 오픈 후 `mini_draft.json`의 effective animation 이름·ID·duration이 계획과 일치하는지 확인한다.
- `common_keyframes`는 사용자가 명시적으로 허용하지 않는 한 0개다.
- 자막이 reference에서도 샷 경계를 가로지르면 타깃에서도 의미상 필요한 동안 유지할 수 있다.
- 한 의미 문장 안의 다중 컷은 `semantic_event` 계획에 명시된 경우만 허용한다. 계획되지 않은 내부 컷은 실패다.
- SFX는 기본 한 트랙·동시성 1이다. reference가 레이어링을 써도 사용자 정책과 충돌하면 `REFERENCE_POLICY_CONFLICT_SFX_LAYERING`을 기록하고 primary만 선택한다.
- 사용 가능한 권리가 확인되지 않은 BGM·효과음을 원본에서 복사하지 않는다.

### 엄격 효과 화이트리스트

사용자가 “레퍼런스와 효과를 똑같이”, “임의로 더 넣지 말 것”, “100% 동일”을 요청하면 추천형 스타일 이식을 중단하고 닫힌 사건 목록으로 컴파일한다. 이 최신 요청은 이전의 “훅을 더 강하게”·“효과를 더 넣기” 요청보다 우선한다.

1. 전체 프레임에서 확인한 자막 애니메이션, 영상 애니메이션, 전환, clip/timeline effect, filter, PIP·split·mask·sticker·overlay, 모든 keyframe을 발생 단위로 기록한다. 관찰되지 않은 범주는 생략하지 않고 기대 개수 `0`과 `verified_absent`로 고정한다.
2. 각 허용 사건은 고유 `reference_event_id`, 원본 `start_frame`, `peak_frame`, `end_frame_exclusive`, 완전한 가시 envelope, 강한 core가 다르면 두 구간 모두, 의미 역할, 타깃 의미 앵커와 컷 대비 상대 프레임 offset을 가진다.
3. 타깃에서는 레퍼런스 절대 초가 아니라 같은 의미 역할의 컷·발화·텍스트 앵커에 붙인다. 사건 종류·순서·발생 횟수, 가시 프레임 길이와 컷 대비 offset은 바꾸지 않는다.
4. 레퍼런스 자막이 첫 프레임부터 완전 표시되면 `animation_signature.mode: "none"`이 필수 기대값이다. 더 화려하게 보이게 하려고 pop·fade·bounce를 추가하지 않는다.
5. PIP·split처럼 구조가 보이지만 원본 editable layer stack이 없는 사건을 조용히 누락하거나 단일 효과로 허위 변환하지 않는다. 재구성 근거가 충분하면 독립 editable track으로 만들고, 부족하면 `REFERENCE_EDITABLE_LAYER_STACK_UNRESOLVED`로 실패 또는 명시적 제한으로 남긴다.
6. 렌더 MP4만으로는 원본 CapCut effect/resource ID를 증명할 수 없다. 시각 사건의 수·순서·프레임 문법은 엄격히 맞출 수 있지만 설치 효과는 `fallback_nearest_verified_local_package`이며 `asset_identity_exact: false`로 기록한다. 원본 초안에서 동일 ID·path·parameter가 확인된 경우에만 `verified_exact`이다.
7. 컷 주변 블러·스트레치를 분류할 때 전체 프레임과 자막 ROI를 따로 측정한다. incoming 영상의 고주파 선명도·경계가 정상인데 자막 ROI만 번지면 `text_animation`이며 video transition/effect로 분류하지 않는다. 같은 문구가 컷을 가로질러 유지되면 동일 문구 TextSegment를 컷에서 둘로 나누고 out/in 사건으로 기록한다.
8. 관찰된 text animation과 같은 로컬 패키지가 없으면 PyCapCut enum의 ID만 직렬화하지 않는다. 미설치 ID는 `EDITABLE_ANIMATION_SELECTOR_UNRESOLVED` 및 애니메이션 분실 위험으로 처리한다. 사용자가 근접 구현을 허용한 경우에만 설치 확인된 이름 있는 대체를 한 번 사용하고 `fallback_nearest_verified_local_package_scope_mismatch`, `asset_identity_exact: false`, 원본 scope와 대체 scope를 함께 기록한다.
9. 저장 초안의 전체 시각 인벤토리를 multiset으로 다시 만들고 계획 Counter와 비교한다. 허용되지 않은 발생 사건, 미참조 효과 material, 숨은 animation/transition/filter/keyframe, 추가 시각 트랙이나 중복 트랙이 하나라도 있으면 실패한다.
10. 측정 가능한 PIP·split·before/after 사건은 `video.composite_layouts[]`에 `reference_event_id`, 의미 앵커, 정확한 frame duration, component별 source assignment/start, crop, clip alpha/scale/transform, viewport bbox와 z-index를 기록한다. 각 component는 독립 video track이어야 하며 레퍼런스가 cut-on/off이면 animation·transition·keyframe을 0개로 유지한다.
11. `composite_layout_verification.json`에서 사건/component/트랙 segment Counter, target/source timerange, crop·clip·render order가 저장 초안과 모두 일치하고 `objective_composite_pass: true`여야 해당 합성 사건을 해결한 것으로 센다.
12. 새 대본 맥락에 맞춘 target source 선택은 허용된 의미 치환이지만 원본 source crop 복구로 간주하지 않는다. `observed_event_fidelity_exact`, `reference_original_source_crop_recovered`, `asset_identity_exact`를 별도 필드로 보고한다.

## 6. 저장 초안 역검증

저장된 초안을 다시 event trace로 추출해 계획과 비교한다.

필수 게이트:

- high-salience mandatory event recall 100%
- 정밀 모사의 전체 계획 사건 recall 100%
- 계획되지 않은 효과 0개
- mandatory event 순서 변경 0개
- 컷·텍스트·SFX anchor 오차 1프레임 이하
- 텍스트 bbox 위치 차이 화면 너비·높이 ±2% 이하
- 줄 수, 레이어 순서, 색상 역할 일치
- SFX active tail 절단 0
- 폰트 display name/path/resource ID 해결
- `(시스템)` 폰트 0개
- 편집 가능 모드 `common_keyframes` 0개
- animation/effect/font package 누락 0개
- 레퍼런스·event graph·adaptation plan 해시 일치
- 전체 분석 coverage가 프레임 0부터 `ffprobe`의 `end_frame_exclusive`까지이며 decoded/analyzed frame 수가 정확히 일치
- 오디오가 있으면 전체 sample coverage가 `start_sample=0`, `end_sample_exclusive=decoded_sample_count=analyzed_sample_count`로 정확히 일치
- 모든 표시 자막에 `reference_event_id`와 animation signature가 있고, `none`도 명시적 기대 사건으로 검증
- 저장 자막 첫 토큰이 실제 정렬 단어보다 먼저 나타나는 사건 0개
- 합성 화면이 있으면 `composite_layout_verification.json`의 observed event coverage 100%, component coverage 100%, 계획되지 않은 component 0개, 모든 component cut-on/off, geometry/source timerange drift 0개

구조 역검증 다음에는 포그라운드 UI 확인이 허용된 경우에만 CapCut UI 역검증을 별도 수행한다. 각 고유 폰트·텍스트 애니메이션·영상 애니메이션·화면 효과가 적용된 대표 세그먼트를 직접 선택해 다음을 확인한다. 사용자가 화면 전환을 금지한 백그라운드 안전 모드에서는 앱을 열지 않고 로컬 패키지·selector 메타데이터·저장 객체 검증을 완료한 뒤 UI round-trip을 `pending_foreground_preservation`으로 남긴다.

- 폰트 드롭다운이 실제 표시명이며 `(시스템)`·`none`·빈 값이 아님
- signature가 `in/out/loop/combo`이면 해당 탭에서 저장한 애니메이션 이름이 선택 상태이고, signature가 `none`이면 `없음` 선택 상태가 유지됨
- 화면 효과 타임라인 소재를 선택했을 때 저장한 효과 이름이 표시됨
- 선택한 항목을 다른 항목으로 바꿨다가 되돌릴 수 있어 실제 편집 컨트롤로 round-trip 됨

JSON 객체가 남아 있더라도 UI에서 이름이 복원되지 않으면 편집 가능한 결과가 아니다. 이 경우 키프레임으로 대체하지 말고 샘플을 실패시키며 다음 코드를 사용한다.

다음 실패 코드를 사용한다.

- `REFERENCE_FULL_TIMELINE_COVERAGE_INCOMPLETE`
- `REFERENCE_FULL_AUDIO_SAMPLE_COVERAGE_INCOMPLETE`
- `REFERENCE_STYLE_COVERAGE_SAMPLE_INCOMPLETE`
- `REFERENCE_TEXT_EVENT_MAPPING_MISSING`
- `REFERENCE_ANIMATION_SIGNATURE_MISMATCH`
- `REFERENCE_ANIMATION_VARIANT_COLLAPSED`
- `REFERENCE_CUT_ON_ANIMATION_ADDED`
- `REFERENCE_SPLIT_CAPTION_ANIMATION_DUPLICATED`
- `REFERENCE_STRICT_EVENT_RECALL_BELOW_100`
- `CAPTION_TOKEN_ALIGNMENT_AMBIGUOUS`
- `CAPTION_FIRST_TOKEN_LEAD_EXCEEDED`
- `CAPTION_FIRST_TOKEN_LAG_EXCEEDED`
- `CAPTION_TEXT_AUDIO_ORDER_MISMATCH`
- `REFERENCE_FRAME_CLOCK_UNRESOLVED`
- `REFERENCE_HIGH_SALIENCE_EVENT_UNKNOWN`
- `REFERENCE_TEXT_LIFECYCLE_UNRESOLVED`
- `REFERENCE_AUDIO_EVENT_UNRESOLVED`
- `REFERENCE_ANALYSIS_HASH_MISMATCH`
- `TARGET_WORD_ALIGNMENT_UNAVAILABLE`
- `TARGET_SEMANTIC_BEAT_UNMAPPED`
- `TARGET_LITERAL_COPY_DETECTED`
- `TARGET_FACT_NOT_IN_SCRIPT`
- `TARGET_EVENT_DURATION_UNFIT`
- `EDITABLE_FONT_SELECTOR_UNRESOLVED`
- `EDITABLE_ANIMATION_SELECTOR_UNRESOLVED`
- `EDITABLE_VIDEO_EFFECT_SELECTOR_UNRESOLVED`
- `EDITABLE_UI_ROUNDTRIP_NOT_VERIFIED`
- `REFERENCE_POLICY_CONFLICT_SFX_LAYERING`
- `REFERENCE_EVENT_RECALL_BELOW_GATE`
- `REFERENCE_EVENT_SYNC_OUT_OF_TOLERANCE`
- `REFERENCE_EFFECT_EVENT_MISSING`
- `REFERENCE_UNPLANNED_TEXT_ANIMATION`
- `REFERENCE_UNPLANNED_VIDEO_ANIMATION`
- `REFERENCE_UNPLANNED_TRANSITION`
- `REFERENCE_UNPLANNED_VIDEO_EFFECT`
- `REFERENCE_UNPLANNED_FILTER`
- `REFERENCE_UNPLANNED_COMMON_KEYFRAMES`
- `REFERENCE_UNPLANNED_EFFECT_MATERIAL`
- `REFERENCE_UNPLANNED_AUXILIARY_EFFECT`
- `REFERENCE_UNPLANNED_VISUAL_TRACK`
- `REFERENCE_UNPLANNED_EMBEDDED_KEYFRAMES`
- `REFERENCE_EFFECT_INVENTORY_COUNT_MISMATCH`
- `REFERENCE_EDITABLE_LAYER_STACK_UNRESOLVED`

## 7. 0~8초 내부 게이트와 조건부 승인

본편 전에 전체 레퍼런스 분석을 끝낸 뒤 0~8초 샘플을 만든다. 0~8초 밖에만 존재하는 고유 본문·혜택 강조·CTA signature가 있으면 해당 사건을 한 번씩 포함한 `style_coverage_reel`도 함께 만든다. 다음을 제공한다.

- reference event와 target event의 1:1 비교표
- 컷/텍스트/effect/SFX 경계가 표시된 타임라인
- 주요 사건 전·peak·후 side-by-side 프레임
- 폰트 UI 표시명과 사용 animation/effect 이름
- 사용자 정책 때문에 reference와 달라진 항목
- `verified_exact`, `verified_visual`, `candidate`, `fallback`, `unknown`

`reference.approval_required: true`인 샘플 검토 모드는 게이트 통과와 사용자 승인 전 본편을 생성하지 않는다. 사용자가 전체본 생성을 이미 명시해 `approval_required: false`인 실행은 내부 게이트 통과 직후 전체 초안까지 자동 확장하며 샘플만 결과로 전달하지 않는다.

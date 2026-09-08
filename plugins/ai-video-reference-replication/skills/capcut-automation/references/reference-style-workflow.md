# 레퍼런스 스타일 워크플로우

## 목차

- 목적과 우선순위
- 레퍼런스 입력 한계
- 필수 폰트 스타일 인터뷰
- 기계·시각·오디오 분석 순서
- 타이포그래피·레이어 실측
- 스타일 프로필 완료 조건
- 새 영상 매핑
- 0~8초 충실도 게이트
- 비교 검수

## 목적

레퍼런스의 내용을 복사하는 것이 아니라 편집 문법을 구조화해 새 대본과 소스에 적용한다. 같은 업체·제품·편집자여도 새 레퍼런스를 받을 때마다 기계 분석과 사람의 프레임 검수를 새로 수행하고 `style_profile.json`을 해당 작업 폴더에 저장한다. 이전 프로필은 사용자가 명시적으로 재사용하라고 한 경우에만 참고한다.

사용자가 최소 단위·프레임 단위 분석이나 “거의 같은 편집”을 요청하면 이 문서에 더해 [레퍼런스 미시 분석·맥락 치환 규칙](micro-reference-imitation.md)을 전부 적용한다. 대표 프레임과 전역 통계만 만든 상태는 정밀 모사 분석 완료가 아니다.

정밀 모사는 **전체 레퍼런스 분석이 먼저, 0~8초 타깃 내부 검수본이 나중**이다. `ffprobe` 프레임 수와 전체 48kHz PCM sample 범위를 끝까지 분석하지 않은 이벤트 그래프는 훅 검수용일 뿐 본문·CTA 생성 근거가 아니다. 오디오 분석 보고서에는 `start_sample: 0`, `end_sample_exclusive`, `decoded_sample_count`, `analyzed_sample_count`를 저장하고 뒤의 세 값이 서로 일치해야 한다. 길이·컷 경계가 다른 관련 CapCut 초안은 자원 후보 목록으로만 사용하고 렌더 MP4의 타이밍 권한을 덮어쓰지 않는다.

## 우선순위

충돌할 때 다음 순서를 따른다.

1. 사용자가 이번 영상에 명시한 요구
2. 이번에 제공한 레퍼런스
3. 사용자가 재사용하라고 지정한 업체 스타일 프로필
4. 캡컷 자동화 기본값

## 레퍼런스 입력 한계

MP4 한 개에서 직접 확인할 수 있는 것은 최종 합성 화면, 컷·애니메이션 타이밍, 들리는 믹스와 상대 음량이다. 다음은 MP4만으로 확정할 수 없다.

- 실제 폰트 파일과 PostScript 이름, CapCut font resource ID
- 텍스트·도형·스티커의 원래 레이어 구조와 편집 가능 속성
- CapCut 효과·전환·필터의 정확한 내부 ID와 파라미터
- 원본 BGM·효과음 파일, 라이선스와 무손실 음원

이를 추측해 `verified`로 기록하지 않는다. 로컬에 원본 CapCut 초안이 있으면 `draft_info.json`과 연결된 캐시·미디어를 읽어 확인한다. 원본 초안이 없으면 `unknown` 또는 `fallback`으로 분류한다. `reference.approval_required: true`이면 사용자 승인 전 본편에 fallback 폰트·효과를 적용하지 않는다. `false`인 전체본 실행은 내부 게이트를 통과한 검증 가능한 fallback만 적용해 자동 확장하되 `verified_exact`이나 “동일 자산”이라고 보고하지 않는다. 레퍼런스에서 분리한 오디오를 최종 자산으로 쓰지 않는다.

## 필수 폰트 스타일 인터뷰

레퍼런스 분석을 시작하기 전에 사용자가 본문 자막 폰트를 선택하게 한다.

```text
자막 폰트 스타일을 어떻게 할까요?
1. 기본 — Pretendard SemiBold, 흰색 글자, 검은색 배경
2. 레퍼런스 영상 폰트 — korean-vibe-fonts를 활용해 레퍼런스와 동일·최근접 재현
번호로 선택해 주세요.
```

1번이면 레퍼런스의 폰트·색·배경을 본문 자막에 이식하지 않고 기본 프리셋을 유지한다. 레퍼런스의 컷·모션·효과·음향 분석은 별도로 계속할 수 있다.

2번이면 다음 순서로 처리한다.

1. 렌더 MP4와 일치하는 원본 CapCut 초안을 찾아 `draft_info.json`의 font name/path/resource ID를 우선 확인한다.
2. 원본 초안이 없거나 자원이 미해결이면 자막이 선명한 여러 프레임을 추출하고, 설치된 폰트를 `fc-scan`·fontTools·같은 문구 렌더 bbox/픽셀 비교로 좁힌다.
3. 여전히 정확한 자원이 확인되지 않으면 `korean-vibe-fonts` 카탈로그와 상황별 가이드로 형태·분위기·굵기 후보를 고른다. 카탈로그 밖 폰트의 상업 이용 가능성을 임의로 주장하지 않는다.
4. 선택 폰트를 현재 Mac에 존재하는 실제 로컬 파일과 연결하고 CapCut selector 표시명까지 검증한다. 웹 CSS만 존재하고 로컬 파일·라이선스·selector를 해결하지 못한 후보는 적용하지 않는다.
5. 원본 자원까지 확인했으면 `verified_exact`, 가장 가까운 검증 로컬 대체면 `fallback_nearest_verified_local`로 분리한다. 후자는 `catalog_font_id`, 외형 차이, 상업 이용 근거를 함께 기록한다.
6. `font_style_selection.analysis`와 `reference_style.body`의 `font_name`·`font_path`가 정확히 같을 때만 0~8초 내부 검수 초안을 만든다.

`pending_reference_analysis`, 존재하지 않는 폰트 경로, 라이선스 미확정, `(시스템)`·`none`·빈 selector 이름은 생성 게이트를 통과할 수 없다.

## 분석 순서

### 1. 기계 분석

`analyze_reference.py`로 다음을 추출한다.

- 화면 크기, 비율, FPS, 길이
- 장면 전환 후보 시각
- 컷 수, 평균·중앙 컷 길이, 분당 컷 수
- 영상 전체에 분산된 검수 프레임과 콘택트시트
- 오디오 통합 음량과 검수용 오디오

장면 감지가 실제보다 적으면 `--scene-threshold 0.18`, 너무 많으면 `0.35`처럼 조정해 다시 실행한다.

### 2. 시각 검수

콘택트시트만으로 확정하지 말고 개별 프레임을 컷·텍스트 등장·강조·퇴장 전후로 직접 확인해 다음을 채운다.

- 첫 1~3초 훅 구성과 첫 컷 길이
- 하드컷, 디졸브, 플래시, 모션블러 등 전환 방식
- 펀치인/줌, 화면 흔들림, 속도 변화, 정지 화면
- 색감, 노출, 대비, 채도, 그레인, 비네트
- 제품·인물·B-roll 배치 규칙
- 자막 폰트, 굵기, 크기, 색상, 외곽선, 그림자, 위치, 줄 수
- 단어 강조색, 이모지, 스티커, 자막 등장/퇴장 애니메이션

각 관찰값에 프레임 번호·타임코드·스크린샷 경로를 근거로 연결한다. 정확한 폰트를 식별할 수 없으면 `font_family`를 `unknown`으로 두고 `fallback_font`에 가장 가까운 설치 폰트를 기록한다. 근거 없이 특정 폰트명을 단정하거나 범용 고딕·마커체로 바꾸지 않는다.

### 모션 포렌식 게이트

애니메이션·강조 효과는 대표 프레임 한 장만 보고 판정하지 않는다.

- 컷·텍스트 등장·강조 전후를 최소 2프레임씩 확인하고 객체 위치, 프레임 전체 스케일, 선명도, 블러 방향, 노출 변화를 기록한다.
- 핸드헬드 흔들림, 피사체 접근, 원본 카메라 줌처럼 소스 안에 이미 있는 움직임과 편집 키프레임·효과를 분리한다. 구분할 근거가 부족하면 `source_or_edit_unknown`으로 남긴다.
- 자막은 이전 문구의 마지막 프레임, 새 문구의 첫 프레임, 완전 표시 프레임을 비교한다. 새 문구가 첫 프레임부터 완전 표시되면 `cut_on_no_animation`이며 팝·바운스·페이드로 바꾸지 않는다.
- 모든 text lifecycle 사건에 `animation_signature`를 만든다. `none`도 명시적 signature다. 타깃 표시 자막은 각각 하나의 `reference_event_id`와 연결하고 저장 초안의 실제 animation object/없음 상태를 1대1로 비교한다. `minimum_named_text_animations` 같은 개수 검사는 리소스 건강 상태만 확인할 뿐 충실도 게이트가 아니다.
- MP4에서 보이는 줌·블러·반짝이·PIP는 시각 관찰만 `verified_visual`이다. 원본 `draft_info.json`에서 resource ID와 파라미터를 확인하지 못한 CapCut 내장 효과 이름은 `fallback_nearest_capcut_effect`로 기록한다.
- PyCapCut enum에 이름과 ID가 있더라도 현재 Mac의 CapCut 캐시에 실제 패키지가 있다는 뜻은 아니다. 리소스 기반 애니메이션·장면 효과·전환은 `path`가 비어 있지 않고 디렉터리 및 내부 `content.json`·scene/prefab 연결이 존재하는지 확인한다. 저장 뒤 빈 `path`로 남으면 `verified`가 아니라 미해결 리소스이며 샘플을 실패시킨다. 편집 가능 모드는 CapCut UI의 로컬 표시 이름과 full resource metadata를 `native_resources`에 고정하고 저장 뒤 동일 객체에 복원한다.
- 사용자가 CapCut에서 애니메이션을 다시 선택·수정하길 원하면 `editability.enabled: true`로 둔다. 이때는 실제 텍스트 세그먼트와 이름 있는 `material_animations`·`video_effects`만 허용하며 `common_keyframes`와 글자가 합성된 PNG를 금지한다. 정확한 패키지가 없으면 같은 의미의 다른 설치된 목록 애니메이션을 고르거나 샘플을 실패시키며, 키프레임으로 조용히 모방하지 않는다.
- 저장된 JSON의 이름·ID·경로 검사는 UI 편집 가능성의 필요조건이며, 화면 사용이 허용된 검수에서는 대표 세그먼트를 선택해 폰트 드롭다운의 실제 표시명, 애니메이션 `인/아웃/조합` 탭의 선택 이름, 화면 효과 소재의 이름까지 확인한다. `(시스템)`·`none`·빈 폰트, 이름이 필요한 애니메이션/효과가 복원되지 않으면 실패다. reference signature가 `none`인 세그먼트는 애니메이션 목록의 `없음`이 정확한 정상 상태다. 사용자가 화면 전환 금지를 요청하면 앱을 열지 않고 로컬 패키지와 저장 selector 메타데이터를 검증하며 UI round-trip 미실행 사실을 별도로 남긴다.
- 편집 가능성이 우선이 아닌 작업에서 사용자가 커스텀 모션을 명시적으로 승인한 경우에만 관찰한 모션을 `common_keyframes`로 재구성한다. 텍스트 팝은 scale-only, 영상·로컬 PNG 오버레이는 scale·position·rotation을 사용하고 CapCut 효과명을 임의로 붙이지 않는다.
- 사용자가 레퍼런스보다 더 강한 애니메이션을 명시하면 `fallback_user_requested`로 분리한다. 강조 논리 문장에만 2~5프레임의 짧은 입장 효과를 쓰고, 일반 본문 자막은 레퍼런스의 컷온을 유지한다.
- 사용자가 훅을 더 강하게 해 달라고 명시한 경우에는 레퍼런스의 하드컷·짧은 히트·펄스·휩 순서를 실제 새 영상의 컷/단어 앵커에 맞춰 반복·고밀도화할 수 있다. 상태는 `fallback_user_requested_reference_derived`이며, 효과음은 레퍼런스 역할에 대응하는 primary만 순차 배치해 동시성 1을 넘지 않는다.
- 논리 음성·대본 섹션마다 primary 영상 강조 효과는 기본 한 개다. 훅 전체 반짝이 같은 지속 배경 효과는 별도 lane으로 분리하고 같은 lane의 효과는 겹치지 않게 한다.
- 플래시·합성 흔들림·전역 필터는 레퍼런스에서 프레임 근거가 확인된 경우만 적용한다. 관찰되지 않았으면 명시적으로 `verified_absent`로 기록해 자동 추가를 막는다.
- 레퍼런스 절대 초를 새 음성에 복사하지 않는다. `timeline_start/end`, `hook_start/end`, `section_start/end`에 관찰된 역할과 프레임 길이를 이식한다.

### 레퍼런스 효과 화이트리스트 게이트

사용자가 효과를 레퍼런스와 똑같이 적용하고 임의 추가를 금지하면 스타일 추천이 아니라 닫힌 허용 목록으로 컴파일한다.

1. 전체 프레임 분석에서 확인한 모든 text animation, video animation, transition, clip/timeline effect, filter, keyframe, PIP·mask·sticker·overlay 사건을 발생 단위로 기록한다. 관찰되지 않은 범주는 `expected_count: 0`과 `verified_absent`를 함께 기록한다.
2. 각 허용 사건은 고유 `reference_event_id`, 원본 `start_frame`, `peak_frame`, `end_frame_exclusive`, 의미 역할, 기준 컷과의 상대 프레임 offset을 가져야 한다. 가시 envelope와 강한 core가 다르면 두 범위를 모두 기록하고 배치는 envelope 전체를 보존한다. 같은 효과가 두 번 나오면 두 사건이며 한 소재 이름으로 합치지 않는다.
3. 타깃에서는 동일 의미 역할의 컷·발화·텍스트 앵커에 사건을 옮긴다. 영상·자막 구간을 레퍼런스 절대 초에 억지로 맞추지 않되, 컷 대비 시작 offset, 가시 지속 프레임 수, 사건 순서와 발생 횟수는 그대로 유지한다. 지속 배경 효과처럼 의미 구간 전체를 덮는 사건은 시작·종료 앵커를 둘 다 명시한다.
4. 이전 요청에 “훅을 더 강하게”가 있어도 최신 요청이 “더 넣지 말고 동일하게”라면 반복·밀도 증가·보조 효과를 모두 제거한다. 레퍼런스 사건을 한 번 더 반복하는 것도 임의 추가다.
5. 생성 뒤 저장된 전체 트랙을 다시 읽어 계획과 저장을 multiset으로 비교한다. 요청 항목의 존재만 확인하지 말고 계획되지 않은 animation container, transition attachment, filter, clip/timeline video effect, common/material/top-level keyframe, 추가 video·filter·sticker 시각 트랙, 미참조 effect material을 역으로 찾아 실패시킨다.
6. `reference_effect_inventory_verification.json`은 `effect_event_recall=1.0`, `unplanned_effect_count=0`, 빈 `unexpected_effects`·`missing_effects`, `strict_effect_inventory_pass=true`여야 한다. 기대 count와 저장 count가 어느 종류에서든 다르면 실패다.
7. 전체 프레임 분석에서 발견했지만 원본 레이어 구조를 확정하지 못한 사건은 `unresolved_reference_events`에 숨김없이 남긴다. 하나라도 있으면 `REFERENCE_EVENT_SCOPE_INCOMPLETE`이며, 구현된 motion scope만 통과했더라도 전체 레퍼런스 충실도 완료로 승격하지 않는다.
8. 원본 CapCut 초안이 없는 렌더 MP4의 `verified_visual` 사건은 원본 effect/resource ID를 증명하지 못한다. 가까운 설치 패키지를 쓰면 `fallback_nearest_verified_local_package`로 허용 목록에 별도 표시하고 시각 사건 충실도와 자산 동일성을 구분한다. 이를 `verified_exact`이나 “원본 자산까지 100% 동일”로 승격하지 않는다.
9. PIP·split·before/after 사건은 관찰 가능한 화면 geometry를 독립 계약으로 다룬다. 시작·종료 프레임, 각 component의 viewport bbox, z-order, alpha와 cut-on/off를 측정할 수 있으면 현재 대본에 맞는 source assignment를 별도 editable video track으로 재구성한다. 하드컷 사건에 임의 animation·transition·keyframe을 붙이지 않는다.
10. 저장 뒤 `composite_layout_verification.json`에서 사건 수와 component 수, 트랙별 segment 수, target/source timerange, crop, clip transform/alpha, render order가 모두 계획과 일치해야 한다. `objective_composite_pass`가 거짓이면 전체 화이트리스트도 실패다.
11. visible viewport 계약 일치는 `observed_event_fidelity_exact`의 근거일 뿐 원본 source crop이나 네이티브 CapCut 자산 ID의 동일성 근거가 아니다. 두 값은 각각 `reference_original_source_crop_recovered`, `asset_identity_exact`로 분리하고 근거가 없으면 `false`로 둔다.

### 3. 오디오 검수

포그라운드 청취 검수가 허용되면 원본 영상과 추출 오디오를 함께 들어 다음을 타임코드로 기록한다. 사용자가 소리 재생을 금지한 백그라운드 안전 모드에서는 재생하지 않고 PCM 파형·스펙트럼·무음·attack 분석으로 가능한 항목만 기록하며, 주관적 음향 판단은 `pending_foreground_preservation`으로 남긴다.

- BGM 장르, 분위기, 대략적 BPM, 인트로/아웃트로
- 내레이션 대비 BGM 음량과 음성 구간 덕킹
- 효과음의 시각적 트리거와 종류: whoosh, pop, click, impact, riser 등
- 효과음 시각 동기 오차와 반복 패턴
- 무음, 강조 정지, 음악 브레이크

곡명이나 효과음 파일을 식별하지 못하면 기능·분위기·타이밍을 기록한다. 레퍼런스에서 추출한 음악을 최종 영상에 넣지 않는다. 사용자가 권리를 확인한 파일, 직접 제공한 파일 또는 사용 가능한 CapCut 라이브러리 음원을 사용한다.

### 효과음 정밀 분석 게이트

레퍼런스 효과음은 `reference_asset_start_sec`(자산 시작), `reference_sync_sec`(컷·텍스트·발화와 맞는 지각상 기준점), `reference_active_end_sec`(유효 본체 끝)를 분리해 기록한다. 트리거는 `video_cut`, `text_in`, `spoken_keyword`, `graphic_in`, `transition_arrival` 중 하나로 분류한다. whoosh는 도착 peak가 컷에 맞을 수 있고 click·pop은 최초 threshold 뒤의 강한 transient가 기준일 수 있으므로 자동 onset을 그대로 사용하지 않는다.

MP4 혼합 음원과 라이브러리 자산을 대조할 때 다음 근거를 `reference_sfx_match_report.json`에 저장한다.

- 레퍼런스 경로·SHA-256·분석 run ID
- 자산의 정확한 상대경로·지문과 레퍼런스 최적 시작 시각
- 자산 `onset`, `attack`, `peak`, `active_end`와 선택한 `sync_mode`
- 0.98~1.02 속도 탐색 결과
- 전체 파형과 저·중·고 주파수대 정규화 상관 점수
- 최고 점수, 2위 점수, 점수 차·비율
- 추정 gain, 반복 발생 시각, 시각·발화 트리거
- `verified_exact`, `candidate`, `unknown` 상태와 판정 이유

보고서를 재생성하는 코드나 점수 근거가 없으면 파일명이 비슷해도 `verified_exact`으로 기록하지 않는다. 음성·BGM에 가려 기준을 통과하지 못하면 승인된 기능 대체음으로 분리하거나 `unknown`으로 남긴다.

측정이 끝난 포렌식 JSON은 엔진의 `python3 -m capcut_auto.reference_sfx_report`로 현재 매니페스트와 결합한다. 이 단계에서 레퍼런스·자산 SHA-256, 최고·2위 점수, source/sync 범위와 정규 상태를 `reference_sfx_match_report.json`으로 고정한다. 이 명령은 파형 상관을 새로 계산하지 않으므로 입력 포렌식에 없는 근거를 만들어내지 않는다.

## 타이포그래피·레이어 실측

오프닝 훅, 본문 자막, CTA를 하나의 `caption_style`로 합치지 말고 별도 시스템으로 기록한다.

### 프레임별 측정

각 대표 문구의 최초 등장, 완전 표시, 강조, 퇴장 프레임을 캡처하고 다음 값을 프레임 좌표와 화면 비율로 저장한다.

- 텍스트 경계 상자 `x`, `y`, `width`, `height`
- 기준선, 행간, 자간, 정렬, 정확한 줄바꿈과 최대 줄 수
- 글자 높이/프레임 높이, 외곽선 px, 그림자 offset·blur
- 채움·강조·외곽선·배경의 샘플 색상과 투명도
- 등장·퇴장 지속 프레임, scale·position·opacity 변화

스크린샷에서 보이는 UI 여백이 아니라 실제 1080×1920 영상 프레임을 기준으로 측정한다. 여러 프레임에서 값이 달라지면 평균으로 뭉개지 말고 애니메이션 keyframe으로 기록한다.

### 실제 폰트 검증

다음 순서로 폰트를 판정한다.

1. 원본 CapCut 초안이 있으면 텍스트 material과 해당 track segment를 연결해 `font.path`, font resource ID, style range, transform을 추출한다.
2. `fc-scan`, `fc-query` 또는 `fontTools.ttLib.TTFont`로 파일의 family·subfamily·PostScript 이름을 확인한다.
3. 동일 문구를 후보 폰트로 렌더하고 글자 폭, 획 모양, 받침·숫자·문장부호를 기준 프레임과 비교한다.
4. 경로와 resource ID까지 일치하면 `verified_exact`, 파일만 일치하면 `verified_file`, 시각 비교만 통과하면 `verified_visual`, 대체만 가능하면 `fallback`, 확인 불가면 `unknown`으로 기록한다.

폰트 경로나 resource ID를 발견했으면 실제 값을 `style_profile.json`과 `fidelity_report.json`에 저장한다. 정확한 파일을 연결할 수 없는데도 이름만 비슷한 폰트를 자동 적용하지 않는다.

편집 가능한 CapCut 폰트는 저장 초안의 각 텍스트 material에서 `fonts[]` 레코드, top-level resource ID/path/source platform, 모든 rich-style font ID/path가 일치해야 한다. `fonts[].title`과 CapCut UI 선택 필드의 표시명이 비거나 `(시스템)`이면 파일이 렌더되더라도 폰트 검증 실패다. 임의 `local.*` resource ID와 프로젝트 임시 폰트 경로를 함께 쓰지 않는다.

폰트 표시명은 family 이름을 임의 번역한 값이 아니라 현재 CapCut 목록이 표시하는 `title`을 사용한다. 같은 파일이라도 CapCut이 `연성`으로 표시하면 완료 보고와 매니페스트도 `연성`으로 통일한다.

### 레이어 재구성

- **오프닝 훅:** 1행·2행, 색상별 문구, 외곽선·그림자, 스티커·반짝이, 등장 애니메이션을 분리한다.
- **본문 자막:** 발화 단위 텍스트, 강조 단어, 테두리, 위치, 등장·퇴장을 분리하고 Whisper 단어 경계에 맞춘다.
- **본문 자막 타이밍:** 표시 계획을 다시 확인하는 것으로 끝내지 않는다. 저장 자막의 첫 토큰을 Whisper 단어 배열에 독립 정렬해 `audio_target_start + word_source_start - audio_source_start`와 직접 비교한다. ASR이 첫 토큰을 누락한 음성 파일의 첫 자막은 `silencedetect`의 leading-silence end를 독립 음향 기준으로 쓴다. 엄격 모드의 자막 선행 허용값은 정확히 0초이며 저장 시작이 기준보다 앞선 양이 0보다 크면 실패한다. 1ms는 계획값 직렬화 비교 허용 오차일 뿐 발화 전 표시 허용치가 아니다.
- **CTA:** 좁은 pill/박스, 정상가, 할인가, 할인 문구, 이모지, 보조 각주, 별도 본문 카피를 각각 독립 레이어로 만든다.

CTA를 긴 공백이 든 단일 텍스트나 화면을 크게 가리는 하나의 배경 텍스트로 흉내 내지 않는다. 레퍼런스에 보이지 않는 필터·반짝이·펀치인·흔들림을 “비슷한 분위기”라는 이유로 추가하지 않는다.

## 스타일 프로필 완료 조건

다음 필드를 관찰 가능한 범위에서 채운다.

```json
{
  "source": {
    "reference_path": "/absolute/reference.mp4",
    "analysis_run_id": "20260726T011800+0900",
    "fresh_analysis": true,
    "source_capcut_project": null,
    "mp4_only_limitations": ["font_resource_id", "editable_layer_stack"]
  },
  "editing_rhythm": {
    "hook_duration": 1.2,
    "median_shot_duration": 1.05,
    "transition_types": ["hard_cut", "flash"],
    "speed_ramps": [],
    "punch_in_pattern": "강조 단어 직전 105%→115%"
  },
  "caption_style": {
    "status": "fallback",
    "font_family": "unknown",
    "font_path": null,
    "font_resource_id": null,
    "fallback_font": "Pretendard ExtraBold",
    "weight": 800,
    "size_ratio_of_frame_height": 0.045,
    "text_color": "#FFFFFF",
    "highlight_colors": ["#FFE44D"],
    "outline_color": "#111111",
    "outline_width": 8,
    "position": "하단 22%",
    "max_lines": 2,
    "animation_in": "pop 4 frames",
    "emphasis_rules": ["핵심 명사만 노란색"]
  },
  "layer_systems": {
    "opening_hook": {},
    "body_caption": {},
    "cta": {}
  },
  "visual_effects": [
    {
      "trigger": "강조 문장 시작",
      "type": "punch_in",
      "duration": 0.18,
      "intensity": "110%"
    }
  ],
  "sound_effects": [
    {
      "reference_event_id": "ref-sfx-001",
      "trigger": {
        "kind": "spoken_keyword",
        "text": "최초 특가",
        "reference_time_sec": 31.42
      },
      "asset_status": "verified_exact",
      "asset_relative_path": "효과음 120가지 #03/086_팝.mp3",
      "reference_asset_start_sec": 31.25,
      "sync_mode": "manual",
      "sync_point_seconds": 0.18,
      "source_start_seconds": 0.15,
      "active_end_seconds": 0.22,
      "gain_db": -8.0,
      "match_evidence": {
        "normalized_correlation": 0.72,
        "second_best_score": 0.51,
        "speed": 1.0,
        "band_time_spread_frames": 0
      }
    }
  ],
  "music": {
    "genre": "bright beauty pop",
    "mood": "빠르고 산뜻함",
    "bpm_estimate": 118,
    "voice_ducking": "-10dB under narration"
  }
}
```

보이지 않거나 들리지 않는 항목은 `unknown` 또는 `null`로 남긴다. 프로필 상태를 `ready`로 바꾸기 전에 미확정 항목이 제작에 영향을 주는지 판단한다.

## 새 영상 매핑

- 레퍼런스의 **문구 내용은 복사하지 않는다**. 먼저 현재 대본에서 `problem`, `solution`, `proof`, `offer`, `cta`를 추출해 `semantic_copy_plan`에 근거 문장과 화면 카피를 함께 기록한다.
- 훅은 현재 대본의 첫 문제와 첫 해결 단서를 2행 이내로 압축한다. CTA는 대본에 실제로 존재하는 판매 채널·가격 범위·기한·행동만 사용하며, 레퍼런스에만 있는 정상가·할인율·혜택을 가져오지 않는다.
- 레퍼런스에서 옮기는 것은 폰트 계층, 색상 역할, 외곽선, 그림자, 레이어 순서, 등장 시간과 컷 리듬이다.
- 다중 행 카피는 각 행을 실제 폰트로 렌더한 `textbbox`에 stroke와 shadow를 포함해 배치한다. `line2_top >= line1_bottom + gap`을 강제하고 기본 gap은 24px, 최소 허용은 20px로 한다.
- 카피가 기준 폭을 넘으면 의미를 먼저 짧게 줄이고, 그래도 넘을 때만 승인된 최소 폰트 크기까지 축소한다. 어떤 경우에도 두 행을 겹쳐 폭을 맞추지 않는다.
- 현재 대본의 원본 문장/의미 항목마다 `problem`, `action`, `texture`, `benefit`, `before_after`, `proof`, `offer`, `cta` 역할을 먼저 정하고 하나의 논리 음성 섹션으로 만든다.
- 영상 폴더 전체를 파일당 한 장의 대표 프레임만으로 판단하지 않는다. 후보 영상의 여러 시점과 사용할 `source_start`부터 해당 음성 섹션 길이까지를 무음으로 확인해 객체·행동·피부 상태·제품 노출을 `video source index`에 기록한다.
- 각 논리 음성 섹션에 화면 의미가 가장 가까운 영상 하나를 배정하고 고유 파일명 `match`, `source_start`, `semantic_tags`, `reason`을 `video_assignments`에 고정한다. 대본과 무관한 장면을 레퍼런스의 컷 수를 맞추기 위해 넣지 않는다.
- 레퍼런스 컷을 절대 시각으로 복사하지 않는다. `logical_caption` 모드에서는 새 음성 섹션의 Whisper 시작·종료가 영상 컷 경계보다 우선하며, 레퍼런스 전역 `shot_durations`는 이 경계를 덮어쓰지 않는다.
- 첫 훅 길이, 중앙 컷 길이 분포, CTA 구간 속도를 우선 재현한다.
- 컷 밀도가 더 필요해도 표시 자막 내부를 자르지 않는다. 사용자가 명시적으로 섹션 내부 다중 컷을 승인하기 전에는 원본 의미 섹션당 영상 하나를 유지한다.
- 영상 소스가 부족하면 같은 컷 반복보다 크롭·펀치인·제품 디테일 등 레퍼런스에서 실제 사용한 변형만 활용한다.
- 자막은 레퍼런스 모양을 재현하되 실제 발화 타임스탬프에 맞춘다.
- 효과와 효과음은 레퍼런스와 같은 의미적 트리거에 배치한다.
- 자막 애니메이션은 `body.logical_overrides`, 섹션 영상 애니메이션은 `video.section_effects[].intro_animation`, 짧은 전역 화면 효과는 `video.timeline_effects`에 역할·상태·근거와 함께 고정한다.
- 편집 가능 모드는 `editability`와 `native_resources`를 함께 사용한다. 훅은 `render_mode: text`, 텍스트·영상은 이름 있는 animation object, 화면 효과는 별도 effect-track을 쓰며 `forbid_common_keyframes: true`를 유지한다.
- 리소스 없는 모션은 사용자가 커스텀 키프레임을 명시적으로 승인한 비편집 우선 작업에만 `body.logical_overrides[].style.keyframe_motion`, `hook.keyframe_motion`, `video.section_effects[].keyframe_motion`으로 고정한다.
- 각 효과는 저장된 초안에서 material animation, clip effect 또는 effect-track timerange로 다시 확인한다. 계획값만 존재하거나 저장된 효과 수가 다르면 실패시킨다. 활성 material animation·video effect·transition의 로컬 `path`가 없거나 placeholder가 하나라도 있으면 ID와 구간이 맞아도 실패다.
- 엄격 화이트리스트 모드에서는 모든 계획 효과에 `reference_event_id`가 있어야 하고, `reference_fidelity.effect_inventory.allowed_reference_event_ids` 밖의 사건은 생성하지 않는다. `expected_counts`에 애니메이션·전환·필터·키프레임·clip/timeline effect의 0개 범주까지 빠짐없이 적는다.
- 영상 컷 수나 순서를 바꾼 뒤에는 기존 `video_cut_start.index` 효과음을 그대로 두지 않는다. 실제 발화 또는 논리 섹션 역할을 다시 분석해 `spoken_keyword_start`, `caption_start` 같은 안정적인 의미 앵커로 옮기고 싱크를 재검증한다.
- BGM은 음성 가독성을 해치지 않도록 레퍼런스의 상대 음량과 덕킹을 재현한다.

## 0~8초 충실도 게이트

전체 CapCut 초안을 만들기 전에 새 소스로 0~8초 샘플을 만든다. 레퍼런스의 동일 역할 프레임과 샘플 프레임을 나란히 비교하고 `fidelity_report.json`을 작성한다.

필수 게이트:

- 오프닝 소스의 의미와 구도 역할이 레퍼런스와 대응한다.
- 훅의 실제 폰트 상태가 `verified_*`이거나 조건에 맞는 `fallback`이다. `approval_required: true`이면 사용자가 명시적으로 승인한 fallback만 허용하고, `false`이면 실제 표시명·로컬 경로·bbox를 검증해 내부 게이트를 통과한 fallback을 허용하되 `verified_exact`으로 승격하지 않는다.
- 줄바꿈·레이어 수·혼합색 구조가 같고, 텍스트 위치 차이가 화면 높이·너비의 ±2% 이내다.
- 화면 카피가 현재 대본에서 도출됐고 레퍼런스 리터럴 문구를 복사하지 않았다.
- 모든 다중 행 텍스트의 `overlap_px`가 0이고 실제 bbox 사이에 최소 20px의 여백이 있다.
- 글자 높이, 외곽선, 그림자, 배경 크기가 육안상 같은 계층으로 보인다.
- 첫 컷 길이, 훅 지속 시간, 첫 8초 컷 밀도 차이가 ±15% 이내다.
- 첫 8초의 각 영상 시작·종료가 대응 논리 음성 섹션과 저장 초안 기준 1ms 이내이고, 표시 자막 내부 컷·영상 공백·중첩이 0개다.
- 첫 8초 `video_assignments`의 실제 소스 장면이 현재 대본 역할과 맞고 `semantic_tags`, `reason`, `source_start` 근거가 있다.
- 레퍼런스에서 관찰되지 않은 전역 필터·효과가 없다.
- `motion_effect_verification.json`의 요청 효과 수와 저장 효과 수가 같고, 자막 애니메이션·영상 애니메이션·클립 효과·타임라인 효과의 이름·구간이 모두 일치한다.
- 엄격 화이트리스트 모드의 `reference_effect_inventory_verification.json`에서 사건 recall이 1.0이고 계획 외 효과 수가 0이며, 누락·추가·count mismatch·미참조 효과 material·추가 시각 트랙·숨은 keyframe 경로가 모두 빈 배열이다.
- `resource_compatibility_verification.json`의 미해결 animation/video effect/transition 배열, placeholder 수, 알려진 PyCapCut 텍스트 speed UUID를 제외한 미해결 `extra_material_refs` 수가 모두 0이며 `resource_compatibility_pass`가 참이다.
- 편집 가능 모드는 `native_resource_patch_report.json`에서 실제 요청한 등록 패키지와 사용 횟수가 통과하고, `editable_controls_verification.json`에서 훅/본문 실제 텍스트, 사건 그래프의 `mode != none` 고유 사건 수와 일치하는 named animation/effect 수, `common_keyframe_group_count: 0`, `editable_controls_pass: true`를 확인한다. 레퍼런스의 모든 signature가 `none`이면 named animation 0개가 정확한 성공 상태다.
- 편집 가능 모드의 모든 텍스트에서 `font_ui_name`이 실제 이름이고 `font_selection_resolved: true`, `nested_font_record_count >= 1`이어야 하며 `(시스템)` 표시는 0개여야 한다.
- 커스텀 키프레임을 명시적으로 허용한 비편집 우선 작업만 리소스 없는 텍스트·훅 그래픽·영상 키프레임의 property type, keyframe 수, 상대 시각, 값을 검증한다.
- 기준 초안이 있으면 첫 8초의 영상 target/source, 음성 trim/target, 표시 자막 텍스트/구간, 효과음 target/source/sync가 스타일 적용 전과 1ms 이내로 같다.
- 레퍼런스의 컷온 자막에 추가한 사용자 요청 애니메이션은 `fallback_user_requested`로 표시되고 강조 논리 문장에만 제한돼 있다.
- 같은 논리 섹션에 primary 영상 강조 효과가 중복되지 않고, 레퍼런스에서 확인되지 않은 플래시·합성 흔들림이 없다.
- 첫 8초 효과음의 선택 자산과 레퍼런스 판정 상태가 기록돼 있다.
- 선택한 `sync_point`가 저장된 CapCut 초안의 실제 source/target 범위에서 트리거와 1프레임 이내다.
- `sync_point`와 `active_end`가 잘리지 않고 fade가 active 구간을 침범하지 않는다.
- 파형 대조 근거가 없는 효과음을 “레퍼런스와 동일”이라고 표시하지 않는다.
- `fallback`·`unknown` 항목과 차이가 비교 이미지에 명시돼 있다.

`reference.approval_required: true`인 샘플 검토 모드는 사용자에게 비교 프레임을 보여 승인받은 뒤 동일 `style_profile.json` 해시와 레이어 프리셋으로 본편을 만든다. 사용자가 `전체본`, `다 만들어`, `계속 진행`, `이대로 진행`으로 본편을 이미 승인한 실행은 내부 검수 게이트가 통과하면 같은 해시와 프리셋으로 전체 초안까지 자동 확장한다. 스타일 파라미터가 바뀌면 두 모드 모두 내부 검수를 다시 수행한다.

## 비교 검수

완성본과 레퍼런스를 다음 기준으로 비교한다.

- 화면비·FPS 일치
- 첫 훅 길이와 컷 밀도
- 평균 및 중앙 컷 길이 차이 ±15% 이내
- 자막 위치 차이 화면 높이·너비의 ±2% 이내
- 자막 색·외곽선·굵기·줄 수·강조 규칙
- 실제 폰트 경로·resource ID 또는 승인된 fallback의 상태
- 오프닝·본문·CTA의 레이어 수와 겹침 순서
- 전환·줌·속도 효과의 종류와 의미적 트리거
- 효과음의 트리거와 프레임 단위 싱크
- BGM 분위기·템포·음성 대비 음량

숫자를 맞추기 위해 부자연스럽게 편집하지 않는다. 차이가 생기면 소스 부족, MP4-only 한계, 권리 문제, 폰트 자원 부재, CapCut 효과 미지원 등 이유를 보고한다. `unknown`을 숨기거나 “거의 동일”처럼 근거 없는 표현으로 완료 처리하지 않는다.

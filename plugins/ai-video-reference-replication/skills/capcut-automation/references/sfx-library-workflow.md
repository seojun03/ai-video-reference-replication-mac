# 효과음 라이브러리 워크플로우

## 목차

- 목적
- 재귀 색인
- 의미 태그
- 이벤트 매칭
- 타임라인 배치
- 선택 보고서
- 실패·빈 폴더 처리

## 목적

사용자가 지정한 효과음 폴더를 원본 그대로 유지하면서 구조화된 검색 색인을 만들고, 레퍼런스와 새 대본에서 관찰한 의미적 이벤트에 알맞은 파일을 자동 배치한다. 여기서 “학습”은 모델 훈련이나 파일 복제가 아니라 재현 가능한 `sfx_index.json`과 선택 규칙을 만드는 것이다.

## 재귀 색인

지정 폴더의 모든 하위 폴더를 탐색하고 `.wav`, `.mp3`, `.m4a`, `.aac`, `.flac`, `.ogg`, `.aif`, `.aiff`만 분석한다. 숨김 파일, 0바이트 파일, 디코딩 실패 파일은 건너뛰되 이유를 기록한다.

파일마다 다음 값을 저장한다.

```json
{
  "path": "/absolute/효과음/긍정/띠링.wav",
  "relative_path": "긍정/띠링.wav",
  "fingerprint": {
    "size": 421338,
    "mtime_ns": 1784994000000000000
  },
  "audio": {
    "format": "wav",
    "duration_sec": 0.72,
    "sample_rate": 48000,
    "channels": 2,
    "mean_dbfs": -18.4,
    "peak_dbfs": -2.1,
    "stream_start_time_sec": 0.0,
    "onset_sec": 0.016,
    "attack_sec": 0.041,
    "peak_sec": 0.052,
    "active_end_sec": 0.61,
    "tail_sec": 0.11,
    "analysis_window_ms": 5
  },
  "tags": ["positive", "sparkle", "reveal", "short"],
  "tag_sources": ["folder:긍정", "filename:띠링", "audio:short_bright"],
  "confidence": 0.94
}
```

- `ffprobe`로 형식·길이·샘플레이트·채널을 읽는다.
- `onset`은 첫 threshold 통과, `attack`은 평활 RMS의 가장 큰 상승점, `peak`는 가장 큰 5ms RMS 창, `active_end`는 마지막 유효음 창으로 서로 구분한다.
- MP3·AAC의 stream 시작 timestamp와 codec padding을 기록한다. 최종 초안에는 원본을 건드리지 않고 시작 PTS가 0인 48kHz PCM WAV 파생본을 스테이징하며 분석과 배치 모두 같은 PCM 시계를 사용한다.
- 색인 스키마에 sync marker가 추가되면 버전을 올리고 이전 cache를 그대로 재사용하지 않는다.
- 폴더명·파일명·분석값을 함께 사용하고 사용자가 만든 폴더 분류를 가장 강한 신호로 취급한다.
- 파일을 추가·수정·삭제한 경우 크기·수정 시각 지문을 비교해 해당 항목만 다시 분석한다.
- 원본 파일의 이름, 위치, 내용, 수정 시각을 바꾸지 않는다.

## 의미 태그

한국어·영어 파일명과 상위 폴더명을 정규화해 다음 기능 태그로 매핑한다. 한 파일에 여러 태그를 허용하고 근거를 `tag_sources`에 남긴다.

| 기능 | 대표 단서 |
|---|---|
| `positive`, `success`, `sparkle` | 긍정, 성공, 띠링, 반짝, shine, twinkle |
| `negative`, `fail`, `shock` | 현타, 실패, 뜨헉, 헉, fail, error |
| `question` | 물음표, 궁금, question |
| `transition`, `whoosh` | 전환, 휙, 슉, whoosh, swoosh, wind |
| `impact`, `hit`, `emphasis` | 강타, 타격, strike, hit, punch, gong |
| `pop`, `click`, `beep` | 팝, 뿅, 클릭, beep, toy |
| `product`, `reveal` | 제품, 등장, reveal, unveil |
| `money`, `price`, `discount` | 돈, 현금, 동전, cash, coin, sale |
| `soft`, `hard`, `short`, `long` | 음량·길이·transient 분석 |

파일명만으로 의미를 확정할 수 없으면 낮은 신뢰도로 남긴다. 자동 음성 인식으로 효과음에 없는 대사를 만들어내거나, 불명확한 파일에 특정 상품 의미를 부여하지 않는다.

## 이벤트 매칭

새 영상의 대본, 단어 타임스탬프, 자막 스타일 계획, 컷과 레퍼런스 프로필에서 이벤트를 만든다.

- `hook_text_in`: 첫 훅 문구 완전 등장
- `problem`: 고민·실패·부정 증상 제시
- `question`: 질문이나 의문 표시
- `transition`: 컷·화면 이동·와이프
- `product_reveal`: 제품 첫 등장·클로즈업
- `benefit`: 장점·효능 강조
- `result`: 전후 결과·성공 장면
- `price_reveal`: 가격·할인 숫자 등장
- `cta`: 구매·클릭·마감 행동 유도

후보 점수는 최소한 다음 요소를 포함한다.

1. 이벤트와 태그의 의미 일치
2. 레퍼런스가 요구한 세기·질감과의 일치
3. 시각 이벤트 길이와 효과음 onset·active tail의 적합성
4. 직전 사용 파일과의 반복 간격
5. 내레이션 가독성과 동시 효과음 수

동점이면 신뢰도가 높고 피크가 안전하며 최근에 쓰지 않은 파일을 선택한다. 선택을 무작위로 만들지 말고 동일 입력·설정에서는 같은 결과가 나오게 한다. 매칭 점수가 기준 미만이면 억지로 배치하지 않고 `unfilled_event`로 남긴다.

의미 극성은 강제 호환성 게이트다. `problem`·증상·통증·악화·실패·경고·손실·낭비는 `negative`, `solution`·제품 공개·효능·근거·결과·혜택·환불 보장·CTA는 `positive`, 화면 전환·클릭·기계적 조작은 `neutral`로 분류한다. `positive` 자산을 `negative` 사건에, `negative` 자산을 `positive` 사건에 배치하지 않는다. `neutral` 자산은 양쪽에 사용할 수 있지만 감정 반전을 암시해서는 안 된다. 파일명만으로 극성을 확정하기 어렵다면 낮은 신뢰도로 남기고 중립 자산 또는 무효과를 선택한다.

기본 정책은 한 의미 이벤트당 primary 효과음 한 개다. 같은 이벤트의 pop·whoosh·voice accent 같은 보조 레이어는 후보로 비교하되 동시에 배치하지 않는다. 사용자가 레이어링을 명시적으로 요청해 `allow_layering: true`로 설정한 경우에만 보조 레이어를 배치하며, 이때도 `max_simultaneous` 상한을 지킨다.

파일명·폴더명에 `BGM`, `배경음`, `background music`이 있는 자산은 자동 SFX 후보에서 제외한다. 기본적으로 4초를 넘는 자산도 자동 후보에서 제외하되, 사용자가 정확한 상대경로와 `max_duration`을 지정한 수동 이벤트에서는 허용한다. 중복 basename이 둘 이상이면 임의의 첫 파일을 고르지 말고 정확한 라이브러리 상대경로를 요구한다.

레퍼런스와 같은 자산으로 고정하려면 최고 상관 점수뿐 아니라 2위 후보와의 분리도, 0.98~1.02 속도 탐색, 저·중·고 주파수대별 최적 시각과 시각·발화 트리거를 함께 검증한다. `verified_exact`은 전 기준 통과 때만 허용한다. 근거가 기준 미만이면 `candidate` 또는 `unknown`으로 남긴다. 사용자가 가장 가까운 후보의 실제 적용을 요청한 경우 `candidate`도 수동 배치할 수 있으나 동일 자산이라고 보고하지 않는다. 고정할 때는 자산 경로와 함께 검증된 `sync_mode`, `sync_point_seconds`, `source_start_seconds` 또는 `pre_roll_seconds`, match score와 runner-up을 저장한다.

고정 이벤트 시각은 가능하면 `anchor`로 지정한다. 자막의 시각적 등장은 `caption_keyword`, 실제 발화는 `spoken_keyword_start/end`, 컷 전환은 `video_cut_start`, 구조적 구간은 `hook_start/end`·`cta_start/end`를 사용한다. 키워드는 고유하게 매칭돼야 하고 컷 인덱스는 1-based다. 해석 후 `offset_seconds`·`offset_frames`를 적용하며, 미해결·저신뢰·중복 앵커는 조용히 건너뛰지 않고 실패시켜 잘못된 타이밍의 초안을 막는다. 대본 단어가 Whisper에서 다르게 인식된 경우에는 실제 인식 문자열을 확인한 뒤 정확히 한 번만 나타나는 `asr_fallback_text`를 이벤트에 명시하고 보고서에 사유를 남긴다. 자동 추측 fallback은 금지한다.

## 타임라인 배치

1. 이벤트 시각은 컷·텍스트·그래픽·실제 발화 중 올바른 앵커에서 먼저 해결한다.
2. 자산의 기준점은 `start`, `onset`, `attack`, `peak`, `active_end`, `manual` 중 하나로 정한다. 레퍼런스 고정 자산은 `manual`과 `sync_point_seconds`를 권장한다.
3. `source_start_seconds`와 `pre_roll_seconds`는 동시에 지정하지 않는다. 둘 다 없으면 `source_start=max(0, onset-0.020)`으로 계산한다.
4. `timeline_start = event_time - (sync_point - source_start)`로 계산한다. 타임라인 0초를 넘으면 `source_start`를 앞으로 이동해 sync point의 이벤트 시각을 유지한다.
5. `max_duration`은 파일 0초가 아니라 계산된 `source_start`부터의 총 길이다. sync point 뒤 `min_post_sync_seconds` 기본 0.08초를 포함해야 한다.
6. 수동·강제 이벤트의 `preserve_active_tail` 기본값은 `true`다. source 끝이 `active_end`보다 앞서면 생성에 실패한다.
7. `trim_to_active_end: true`이면 source 끝을 `max(active_end + active_tail_padding, sync_point + min_post_sync_seconds)`에 맞춰 줄인다. 파일의 긴 무음 꼬리를 타임라인에 남기지 않되 sync point와 유효음을 자르지 않는다.
8. fade-out 요청 기본값은 12ms다. 실제 값은 `min(요청값, source_end-active_end)`이며 active 구간을 침범하면 0으로 줄인다. `active_end`를 모르면 자동 fade를 넣지 않는다.
9. 압축 원본을 CapCut source clock으로 직접 쓰지 않고 시작 PTS가 0인 48kHz PCM WAV 파생본을 사용한다.
10. 기본값은 `max_simultaneous: 1`, `allow_layering: false`다. 각 의미 이벤트에서 primary 한 개만 남기고, 타임라인이 겹치는 후보는 우선순위·점수·신뢰도·이벤트 시각 순으로 결정적으로 비교해 하나만 배치한다. 탈락 후보는 `simultaneous_limit`으로 보고한다.
11. 강제 이벤트 둘이 같은 우선순위로 충돌해 primary를 결정할 근거가 없으면 임의로 겹치거나 첫 파일을 고르지 말고 `ambiguous_primary_effect`로 실패한다.
12. 기본 정책에서는 모든 효과음을 하나의 `효과음 1` 트랙에 배치한다. 저장 후 모든 효과음 트랙의 실제 `target_timerange`를 합쳐 최대 동시성 1과 효과음 트랙 최대 1개를 다시 검사한다.
13. 각 placement에는 `target_caption_text`, `semantic_event`, `semantic_polarity`, `asset_polarity`, `polarity_match_pass`, `selection_reason`을 저장한다. Style A는 여기에 `micro_intent`, `sfx_family`, `anchor.target_frame`, `search_audit`, 선택·탈락 후보와 이유, `companion_visual`을 추가한다. 저장 후 극성 불일치가 하나라도 있으면 `SFX_POLARITY_MISMATCH`로 실패한다.
14. 사용자가 레이어링을 명시적으로 요청해 `allow_layering: true`로 설정한 경우에만 여러 lane을 만들 수 있다. 이때도 승인된 `max_simultaneous`를 넘지 않는다.
15. 저장 후 CapCut 초안을 다시 읽어 `actual_sync = target_start + sync_point - source_start`를 계산하고 실제 FPS 기준 1프레임 이내인지 검사한다.
16. gain은 보이스오버와 BGM 가독성을 보존하고 합산 peak가 clipping하지 않도록 조절한다.
17. 알맞은 후보가 없으면 레퍼런스 추출 오디오나 임의의 CapCut 자산으로 대체하지 않는다.

## 선택 보고서

`sfx_selection_report.json`에 색인 버전과 모든 결정 근거를 기록한다.

```json
{
  "library_root": "/absolute/효과음",
  "indexed_files": 84,
  "project_fps": 29.97,
  "policy": {
    "max_simultaneous": 1,
    "allow_layering": false,
    "trim_to_active_end": true,
    "active_tail_padding_ms": 12
  },
  "saved_draft_verification": {
    "maximum_simultaneous": 1,
    "sfx_track_count": 1,
    "single_effect_pass": true
  },
  "placements": [
    {
      "event": "price_reveal",
      "anchor_kind": "spoken_keyword_start",
      "resolved_anchor_time_sec": 27.694,
      "asset": "긍정/돈들어오는소리.mp3",
      "staged_asset": "media/sfx/sfx_010.wav",
      "score": 0.91,
      "runner_up_score": 0.72,
      "score_margin": 0.19,
      "score_ratio": 1.264,
      "reasons": ["tag:money", "tag:price", "short_onset"],
      "match_status": "verified_exact",
      "sync_mode": "peak",
      "sync_point_sec": 0.180,
      "source_start_sec": 0.150,
      "source_end_sec": 0.240,
      "active_end_sec": 0.220,
      "target_start_sec": 27.664,
      "actual_sync_sec": 27.694,
      "sync_error_ms": 0.0,
      "sync_error_frames": 0.0,
      "active_tail_preserved": true,
      "fade_out_ms": 12,
      "gain_db": -12.0,
      "lane": "효과음 1"
    }
  ],
  "unfilled_events": [
    {
      "event": "transition",
      "event_time_sec": 6.24,
      "reason": "simultaneous_limit"
    }
  ],
  "warnings": []
}
```

`sync_error_frames`는 planner 식을 다시 기록한 값이 아니라 저장된 CapCut draft의 실제 timerange를 읽어 계산한다. `sync_point`가 source 범위 밖이거나 active tail이 잘린 placement는 `placed`로 집계하지 않는다. 최종 검수에서는 배치 수만 세지 말고 실제 sync point, 전체 세그먼트 겹침, 효과음 트랙 수, gain과 선택 이유를 확인한다.

`allow_layering: false`인데 같은 의미 이벤트에 둘 이상이 배치되거나, `max_simultaneous: 1`인데 저장된 세그먼트가 겹치거나, 효과음이 있는데 효과음 트랙이 둘 이상이면 `single_effect_pass: false`로 기록하고 완료를 실패시킨다.

## 실패·빈 폴더 처리

- Style A가 아닌 작업에서 경로가 없거나 파일이 0개면 빈 색인과 `library_missing` 또는 `library_empty` 경고를 만들고 효과음 없이 나머지 편집을 계속할 수 있다.
- Style A는 사용자 라이브러리가 비어 있어도 끝내지 않는다. 설치된 CapCut 로컬 자원을 영어·한국어 검색어로 찾고, 없으면 상업 이용 조건이 확인된 외부 자산까지 검색한다. 직접 출처·라이선스·상업 이용 확인을 남기지 못하거나 적합한 필수 효과음을 확보하지 못하면 `STYLE_A_CONTEXTUAL_SFX_UNRESOLVED`로 완료를 막는다.
- 일부 파일만 디코딩 실패하면 정상 파일로 계속하고 실패 경로·오류를 보고한다.
- 전체 색인이 실패해도 원본 파일을 변환·삭제·이동하지 않는다.
- 사용자에게 아직 폴더를 받지 못했으면 표준 `input/효과음/` 경로를 준비하되 자산이 있다고 가정하지 않는다.
- 단일 배치 정책과 충돌한 보조 후보는 조용히 삭제하지 말고 `simultaneous_limit`과 유지된 primary ID를 보고한다.
- 기본 정책에서 저장된 초안의 최대 동시성이 1을 넘거나 효과음 트랙이 둘 이상이면 `SFX_CONCURRENCY_EXCEEDED` 또는 `SFX_TRACK_COUNT_EXCEEDED`로 실패한다.

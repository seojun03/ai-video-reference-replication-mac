# Style A 맥락 효과음·화면 반응 워크플로우

Style A의 효과음을 단순 밀도나 긍정·부정 극성으로 고르지 않고, 대본 사건이 전달해야 하는 구체적 감각과 반응으로 결정할 때 이 계약을 따른다.

## 1. 정답본에서 학습할 범위

사용자가 직접 고친 CapCut 타임라인을 정답본으로 승인하면 수정 전 자동본과 수정 후 정답본을 읽기 전용으로 스냅샷한다.

- 초안 SHA-256, 편집 의미 해시, FPS, 비교 프레임 범위를 기록한다.
- 컷·자막·화면 효과·애니메이션·효과음·음량·앵커가 달라진 사건을 추출한다.
- 사용자가 설명한 수정 이유와 실제 저장 초안 증거를 연결한다.
- 다른 영상에는 의미 사건, 선택 이유, 효과음 가족, 화면 반응만 재사용한다.
- 절대 타임코드, 특정 배율, 수동 source trim, 보조 트랙 수, 실험용 복제 구간은 복사하지 않는다.
- 기존 Style A 금지 규칙과 충돌하는 수동 요소는 승인 범위에 포함하지 않는다. 특히 blur 금지 규칙은 사용자가 명시적으로 해제하지 않는 한 유지한다.

## 2. 효과음 선택 전 사건 분해

각 의미 사건을 다음 여섯 축으로 먼저 기록한다.

1. `persuasion_role`: 훅, 문제, 경고, 메커니즘, 결과, CTA 중 어떤 역할인가
2. `micro_intent`: 막힘, 위기, 민망함, 부족, 수분 이동, 정화, 안도, 조급함 중 무엇인가
3. `desired_emotional_reaction`: 시청자가 무엇을 느껴야 하는가
4. `physical_action_or_texture`: 삐삐, 낙차, 깨짐, 버블, 물 내려감, 감탄, 달려감처럼 어떤 물성이 필요한가
5. `energy`: 짧고 날카로운지, 지속 경고인지, 부드러운지
6. `literal_or_figurative_use`: 화면의 실제 행동음인지 광고적 비유음인지

이 여섯 축이 없으면 파일 검색과 배치를 시작하지 않는다. 극성이 맞더라도 미세 의도가 다르면 부적합 후보다.

## 3. 승인된 Style A 예시 문법

다음은 무위록 수동 완성본에서 승인된 의미 예시다. 문구나 파일명을 고정하지 않고 같은 역할의 새 사건에 일반화한다.

| 미세 의도 | 예시 문맥 | 우선 효과음 가족 | 화면 반응 |
|---|---|---|---|
| `obstruction_blocked` | 안 나온다면 | 금지 삐삐, 오류 비프 | 짧은 정지 반응 또는 화면 hold |
| `urgent_stop_warning` | 그만두시고 절대 방치하지 마세요 | 짧은 사이렌, 경보 | 짧은 위험 반응 또는 소리 단독 |
| `overconsumption_awkward` | 초가공식품 많이 먹는다 | teardrop, 힘 빠지는 낙차, 실제 섭취 사건이면 먹는 소리 | 민망한 반응 또는 소리 단독 |
| `severe_deficiency` | 턱없이 부족하거든요 | 쨍그랑, 짧은 깨짐 | 흑백·저채도 부정 반응 |
| `water_osmosis` | 죽염의 삼투압 | bubble, liquid bubbling | 수분 이동 강조 또는 소리 단독 |
| `cleansing_flush` | 찌꺼기를 깨끗하게 정화 | 물 내려감, 배수, 깨끗한 물 흐름 | 정화 흐름 강조 또는 소리 단독 |
| `effortless_relief` | 힘주지 않아도 편안하게 나오고 | wow, 밝은 reveal | 짧은 punch-in 확대 |
| `urgent_cta` | 지금 쟁여두세요 | 도망감, 급한 발걸음 | 빨간 글씨와 불안정 흔들림 |

위 표에 없는 문장은 여섯 축으로 새 미세 의도를 만들고, 선택 이유를 기록한다. 가장 가까운 표 항목에 억지로 끼워 맞추지 않는다.

## 4. 검색 사다리

각 사건은 다음 순서로 후보를 찾는다.

1. 사용자 효과음 폴더와 등록된 기본 라이브러리의 재귀 색인
2. 설치된 CapCut 로컬 자원 메타데이터와 캐시
3. 상업적 이용 조건이 확인된 외부 효과음 원본

- CapCut 검색어는 영어를 기본으로 하고 한국어 별칭을 함께 기록한다. 예: `eating sound`, `chewing sound`, `short police siren`, `water flush`, `running away sound`.
- 앞 단계에서 문맥·길이·질감·피크가 충분히 맞는 후보를 찾으면 뒤 단계를 생략할 수 있다.
- CapCut 로컬 자원을 선택하면 실제 설치 경로와 자원 ID를 기록한다.
- 외부 자원을 선택하면 직접 다운로드 페이지 URL, 라이선스명, 라이선스 URL, 상업 이용 확인 결과를 기록한다.
- 링크나 라이선스를 확인하지 못한 외부 파일은 선택하지 않는다.
- 적합한 자산이 없으면 밀도만 채우기 위한 click·pop으로 대체하지 않는다. 필수 사건은 `STYLE_A_CONTEXTUAL_SFX_UNRESOLVED`로 완료를 막는다.

## 5. 후보 비교 계약

각 placement에는 최소 두 후보를 비교하고 정확히 하나만 선택한다.

```json
{
  "caption_text": "턱 없이 부족하거든요",
  "micro_intent": "severe_deficiency",
  "semantic_polarity": "negative",
  "sfx_family": "glass_shatter",
  "selection_reason": "부족 상태를 깨지는 감각으로 강조",
  "anchor": {
    "kind": "spoken_keyword_start",
    "keyword": "부족하거든요",
    "target_frame": 235
  },
  "companion_visual": {
    "mode": "monochrome_desaturation",
    "reason": "소리와 함께 생기를 제거해 부족감을 강화"
  },
  "search_audit": {
    "selected_stage": "user_library",
    "steps": [
      {
        "stage": "user_library",
        "queries": ["glass shatter short", "쨍그랑"],
        "status": "matched"
      }
    ]
  },
  "acquisition_status": "resolved",
  "candidates": [
    {
      "candidate_id": "glass-a",
      "origin": "user_library",
      "family": "glass_shatter",
      "status": "selected"
    },
    {
      "candidate_id": "click-a",
      "origin": "user_library",
      "family": "click",
      "status": "rejected",
      "rejection_reason": "깨지는 물성이 없어 문맥이 약함"
    }
  ]
}
```

선택 후보의 장점만 쓰지 말고 탈락 후보가 왜 이 사건에 약한지도 적는다. 같은 효과음 파일은 한 영상에서 재사용하지 않는다. 인접 사건에 같은 가족을 반복할 때는 감정 진행상 반드시 필요한 이유가 있어야 한다.

## 6. 화면 반응과 음향 결합

- 한 의미 사건의 주요 화면 표현은 최대 하나다.
- `monochrome_desaturation`, `short_punch_in`, `red_unstable_text`처럼 승인된 결합은 효과음과 함께 하나의 의미 반응으로 계획한다.
- 화면 효과를 추가하기 어려운 사건은 소리 단독을 허용하되 이유를 쓴다.
- 수동본에서 보인 특정 CapCut 효과 ID는 실제 설치가 확인된 현재 작업에서만 사용한다.
- CTA 빨간 글씨·흔들림은 본문 전체로 확장하지 않는다.
- 확대는 핵심어에 짧게 적용하고 한 사례의 배율·프레임을 전역 고정값으로 만들지 않는다.

## 7. 프레임·오디오 계약

- 최종 음성과 Whisper 단어 정렬을 유일한 시계로 사용한다.
- 발화 강조음은 `spoken_keyword_start`, 인샷 의미음은 `semantic_event_start`, 컷 임팩트는 `video_cut_start`에 둔다.
- placement에 해결된 `target_frame`을 기록하고 저장 초안에서 다시 계산한다.
- MP3·AAC는 첫 가청음까지 정리한 48kHz PCM으로 스테이징하고 `source_timerange.start=0`으로 저장한다.
- 효과음 클립 시작, 첫 가청음, 의미 앵커의 오차는 0프레임이다.
- 음성 trim·TTS 교체·배속 뒤에는 기존 프레임을 비율 변환하지 않고 최종 음성을 다시 분석한다.

## 8. 완료 게이트

Style A는 다음이 모두 참일 때만 완료다.

- `decision_contract_version >= 2`
- 모든 필수 사건의 `acquisition_status=resolved`
- 각 사건에 선택 이유와 탈락 후보 이유가 존재
- 외부 선택 자산의 상업 이용 근거가 존재
- 같은 효과음 파일 재사용 0개
- 이유 없는 인접 동일 가족 반복 0개
- 첫 가청음 앵커 오차 0프레임
- 효과음 누락, 화면 반응 누락, 자막 잘림, 자막 중간 영상 컷 0개

하나라도 실패하면 `style_detail_edit_complete`라고 기록하지 않는다.

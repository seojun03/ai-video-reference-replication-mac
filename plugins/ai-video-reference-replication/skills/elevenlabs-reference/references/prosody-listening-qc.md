# 운율·실제 오디오 QC

## 목적과 표현 원칙

이 단계는 같은 화자의 캐릭터·말투·평균 에너지·속도를 유지하면서 대본에
필요한 의도적 감정 변화만 허용한다. 모든 문장을 기계적으로 같은 음높이로
만드는 단계가 아니다.

검증은 서로 다른 두 층으로 기록한다.

1. `objective_signal_analysis`
   - 실제 WAV 신호에서 피치, 에너지, 속도, 쉼, 스펙트럼, 문장 경계를 측정
   - 레퍼런스 안의 발화 구간들로 median·MAD 기반 자연 변동 범위를 계산
2. `audio_listening_qc`
   - 실제 음성을 입력받아 판단하는 오디오 이해 모델 또는 청취 도구
   - 레퍼런스와 전체 생성본을 A/B로 비교

첫 번째 층을 두 번째 층처럼 표현하지 않는다. 현재 실행 환경이 오디오
입력을 지원하지 않으면 `blocked_unavailable`로 기록하고 실제로 들었다고
말하지 않는다.

## 생성 provenance

1분 이하 단일 화자 작업은 `coherent_block`이 기본이다.

- 전체 대본을 한 Eleven v3 요청으로 생성한다.
- 전체 take에는 하나의 seed, stability, speed, 전역 전달 태그만 쓴다.
- 별도 작업 지시가 없으면 `conversationally`, `speed=1.15`,
  `stability=0.35`를 사용하고, 레이아웃용 줄바꿈을 제거한 연결 발화문을
  전달한다.
- 문장부호만 보고 `curiously`, `excited` 등을 문장마다 자동 교체하지 않는다.
- 전체 take를 Forced Alignment로 문장별 리뷰 클립만 파생한다.
- 전체 미리보기와 최종 WAV는 원래 take의 연속 PCM을 그대로 사용한다.
- 문장별 splice, 부분 배속, gain 보정, 다른 후보 donor 삽입은 허용하지 않는다.
- 한 문장이 실패해도 전체 take를 새로 생성한다. 초기에는 정확히 한
  take만 만들고, 이후 take마다 일회용 내부 토큰을 사용한다. 이 로컬
  사용자의 상시 생성 허용에 따라 별도 승인 질문 없이 최대 5개 take까지
  교정한 뒤 중단한다.

60초를 넘는 작업은 의미 단락 단위 coherent block으로 나누되, 한 문장
안에서 블록을 자르지 않는다. 블록 경계도 아래 연결성 검사를 통과해야 한다.

## 객관적 분석

`scripts/prosody_qc.py`가 다음 증거를 만든다.

- 피치 중심, p10–p90 범위, 윤곽 표준편차, 전체 기울기, 종결부 상승·하강
- 활성 음성 RMS, 에너지 동적 범위, 에너지 기울기
- 한글 음절/활성 발화 초, 내부 쉼 비율
- 스펙트럼 중심과 zero-crossing
- 24개 로그 스펙트럼 밴드 기반 `acoustic_embedding_proxy`
- 인접 문장 종결·시작 피치 jump와 에너지 jump

`acoustic_embedding_proxy`는 학습된 화자 임베딩이 아니다. 화자 동일성이나
감정 이해를 통과했다고 표현하지 않는다.

레퍼런스는 무음 경계를 이용해 최소 3개 유효 발화 구간으로 나눈다. 각
지표의 기준은 고정된 절대 점수 대신 다음으로 계산한다.

```text
center = median(reference utterances)
scale  = max(1.4826 × MAD(reference utterances), measurement floor)
robust_z = abs(candidate - center) / scale
```

한 개의 불안정한 측정으로 거절하지 않도록 독립 지표군을 사용한다.

- critical 지표군 하나 이상이면 실패
- warning 지표군 두 개 이상이면 실패
- 측정 불가가 필수 지표에 발생하면 실패
- 속도는 기존 레퍼런스 대비 ±10% 하드 게이트를 유지
- 인접 문장 경계 피치 jump가 5.5 semitone 초과하면 실패
- 인접 문장 경계 에너지 jump가 6.5 dB 초과하면 실패

통과 후보를 순위화하는 점수는 사용할 수 있지만, 실패 항목을 다른 높은
점수로 상쇄하지 않는다.

## 실제 오디오 A/B 판정

실제 오디오 입력을 지원하는 평가 수단으로 서로 다른 설정 3회를 수행한다.
세 실행은 서로 다른 `settings_id`를 가져야 한다. 매 실행은 레퍼런스와
전체 미리보기를 먼저 비교한 뒤 모든 문장을 다음 항목으로 판정한다.

- `pronunciation_pass`
- `tone_pass`
- `intonation_pass`
- `emotion_pass`
- `speaker_character_pass`
- `boundary_continuity_pass`
- `no_synthesis_artifact_pass`

3회 중 한 항목이라도 실패하면 해당 take를 승인하지 않는다. 다수결,
평균점수, 임계값 완화로 통과시키지 않는다.

외부 오디오 평가 수단은 다음 최소 JSON을 반환해야 한다.

```json
{
  "schema_version": 1,
  "evaluator": "audio-input evaluator name",
  "reference_sha256": "reference wav sha256",
  "preview_sha256": "full preview wav sha256",
  "runs": [
    {
      "settings_id": "independent-setting-1",
      "model": "model identifier",
      "all_passed": true,
      "segments": [
        {
          "index": 1,
          "spoken_text": "현재 대본의 정확한 문장",
          "pronunciation_pass": true,
          "tone_pass": true,
          "intonation_pass": true,
          "emotion_pass": true,
          "speaker_character_pass": true,
          "boundary_continuity_pass": true,
          "no_synthesis_artifact_pass": true,
          "notes": "간결한 판정 근거"
        }
      ]
    }
  ]
}
```

`runs`에는 동일 구조의 실행이 정확히 3개 있어야 하며 각 실행에는 현재
모든 문장이 한 번씩 포함되어야 한다.

## 실행과 상태

배경음악·효과음이 제거된 레퍼런스 WAV를 사용한다.

```bash
python3 scripts/elevenlabs_reference.py prosody-qc \
  --job-dir "/절대경로/작업" \
  --reference-wav "/절대경로/reference_isolated.wav"
```

오디오 판정 JSON이 준비되면 현재 미리보기에 다시 실행한다.

```bash
python3 scripts/elevenlabs_reference.py prosody-qc \
  --job-dir "/절대경로/작업" \
  --reference-wav "/절대경로/reference_isolated.wav" \
  --audio-judge-report "/절대경로/audio-judge-report.json"
```

상태 의미:

- `prosody_regeneration_required`: 객관적 지표 또는 경계 실패
- `awaiting_audio_listening_qc`: 객관적 지표는 통과했지만 실제 오디오 3회 판정 없음
- `awaiting_user_listening_approval`: 객관적 지표와 오디오 3회 판정 모두 통과
- `blocked_unavailable`: 현재 환경에 실제 오디오 입력 평가 수단 없음

현재 미리보기 SHA-256, 문장별 WAV SHA-256, 레퍼런스 SHA-256, 선택 후보
번호가 보고서와 모두 일치해야 승인할 수 있다. 새 take가 생성되거나
미리보기가 바뀌면 이전 운율·오디오 판정 보고서는 무효다.

## 최종 보고서

최종 QC 보고서에는 다음을 보존한다.

- 선택된 take와 문장별 파생 클립
- STT·Forced Alignment·집중 발음 결과
- 문장별 객관적 피치·에너지·속도·쉼 결과
- 앞뒤 문장 연결성
- 오디오 A/B 3회 전체 결과와 settings ID
- 실패 및 전체 take 재생성 내역
- 승인에 사용된 레퍼런스·미리보기·문장별 파일 해시
- 실제 오디오 판정으로 확인하지 못한 한계

# ElevenLabs API 계약

이 문서는 API 오류 조사나 구현 갱신 시에만 읽는다. API는 변경될 수 있으므로 수정 전 공식 문서를 다시 확인한다.

## 인증

- 헤더: `xi-api-key`
- 환경변수: `ELEVENLABS_API_KEY`
- API 키를 파일, 로그, 명령 인자에 넣지 않는다.
- API 키는 ElevenLabs HTTPS 요청을 수행하는 Python 프로세스 경계에만 둔다. `ffmpeg`, `ffprobe` 등 로컬 미디어 하위 프로세스는 allowlist 환경으로 실행하여 키와 프록시 변수를 상속하지 않는다. HTTP 세션은 `trust_env = False`로 실행해 환경변수, `.netrc`, macOS 시스템 프록시를 상속하지 않는다.

## 사용하는 엔드포인트

| 기능 | 메서드와 경로 | 핵심 입력 |
|---|---|---|
| 구독 확인 | `GET /v1/user/subscription` | 없음 |
| 모델 확인 | `GET /v1/models` | 없음 |
| 보이스 목록 | `GET /v2/voices` | `page_size`, 페이지 토큰 |
| 보이스 확인 | `GET /v1/voices/{voice_id}` | `voice_verification` |
| 배경음 분리 | `POST /v1/audio-isolation` | multipart `audio` |
| IVC 생성 | `POST /v1/voices/add` | multipart `files`, `name` |
| 발음 사전 생성 | `POST /v1/pronunciation-dictionaries/add-from-rules` | `rules`, `name`; 기술 용어의 표기는 유지하고 발음만 고정할 때 사용 |
| TTS와 타임스탬프 | `POST /v1/text-to-speech/{voice_id}/with-timestamps` | text, model, seed; Eleven v3에는 context 제외 |
| STT | `POST /v1/speech-to-text` | file, `scribe_v2`, `ko`; 레퍼런스는 diarization, 집중 발음 크롭은 지정된 seed·temperature 사용 |
| 강제 정렬 | `POST /v1/forced-alignment` | file, 원래 발화문 |

## 모델과 출력

- 기본 TTS 모델: `eleven_v3`
- 사용자가 현재 생성에 `eleven_multilingual_v2`를 명시한 경우에만 해당
  전체 take에 모델을 명시하고 시도별 provenance에 기록한다. 이때 v3 전용
  대괄호 오디오 태그와 `language_code`를 보내지 않으며 `style=0`을 사용한다.
- STT 모델: `scribe_v2`
- 언어: 한국어
- Pro 이상: `pcm_44100`
- Creator: `mp3_44100_192`
- 그 외 또는 요금제 확인 실패: `mp3_44100_128`

TTS 응답의 `audio_base64`, `alignment`, `normalized_alignment`를 저장한다. 평균 속도 보정에는 `voice_settings.speed`(0.7~1.2)를 사용한다. seed는 재현 근거로 기록하지만 생성의 완전한 결정성을 가정하지 않는다. 발음 사전을 적용할 때는 현재 사전의 `pronunciation_dictionary_id`와 `version_id`를 `pronunciation_dictionary_locators`에 함께 전달하고 작업 기록에 보존한다.

`eleven_multilingual_v2`에서 발음 사전을 사용할 때는 phoneme 규칙이 아닌
alias 규칙만 사용한다.

엔드포인트의 공통 스키마에 `previous_text`와 `next_text`가 있더라도 현재
`eleven_v3` 요청에는 보내지 않는다. API가 `unsupported_model`로 거부하기
때문이다.

## 집중 발음 API 계약

집중 발음 검사는 전체 문장 STT와 Forced Alignment를 통과한 후보에
추가로 적용한다.

1. Forced Alignment의 문자 정렬에서 집중 구절이 정확히 한 번 나타나는지
   확인하고 첫 유효 문자 시작 시각과 마지막 유효 문자 종료 시각을
   구한다.
2. 인접 단어는 제외하되 바로 앞의 공백·문장부호 정렬 경계부터 시작해
   초성을 보존하고, 뒤는 구절 종료 시각에서 잘라 다음 단어 onset이
   들어오지 않는 48kHz mono WAV로 만든 뒤 앞뒤에 각각 0.2초 무음을
   붙인다.
3. 같은 크롭 파일을 `POST /v1/speech-to-text`로 정확히 세 번 전사한다.

| 실행 | seed | temperature |
|---|---:|---:|
| 1 | 173 | 0.0 |
| 2 | 907 | 0.1 |
| 3 | 2027 | 0.2 |

세 응답 모두 한국어 언어 코드가 명시되고, 허용된 숫자·영문 표기
정규화 뒤 원 집중 구절과 정확히 일치해야 통과한다. 한 번이라도
불일치하거나 API 응답을 측정할 수 없으면 실패이며 다수결이나 임의
재시도로 대체하지 않는다. 강제 정렬에서 구절이 없거나 둘 이상이어서
위치가 비고유하거나 유효한 시각을 얻지 못해도 실패다.

보존된 기존 후보를 다시 선택할 때도 같은 Forced Alignment 위치 탐색,
인접 단어를 제외한 비어휘 경계 포함 크롭, 앞뒤 0.2초 무음과 세 STT
조합을 새로 실행한다. 과거
집중 발음 결과만으로 재선택을 통과시키지 않는다.

## 로컬 최종화 계약

`coherent_full_script_block` 작업은 선택된 전체 take의 WAV를
`review/full_preview.wav`에 바이트 단위로 보존한다. 문장별 파일은 강제
정렬에서 파생한 검토 클립일 뿐이다. `approve`와 `delegate-approve`는
현재 take의 3회 전체 STT, Forced Alignment, 후보·미리보기 해시,
객관적 운율 QC와 서로 다른 설정의 실제 오디오 A/B 판정 3회 만장일치를
모두 다시 검증한다. 최종 `final/final.wav`와 MP3는 문장 클립을 재결합
하지 않고 승인된 전체 미리보기 파일을 그대로 복사한다.

기본 `approve`는 사용자가 현재 전체 미리보기를 직접 들은 승인에만
사용한다. 사용자가 청취를 생략하고 강화 자동 QC 기반 최종화를
명시적으로 위임하면 별도 CLI `delegate-approve`를 사용하며 확인 문구는
다음과 정확히 일치해야 한다.

```text
사용자가 전체 미리보기 직접 청취를 생략하고 강화 자동 검증 기반 최종화를 위임함
```

`delegate-approve`는 새 TTS를 생성하지 않지만, 현재 미리보기와 문장별
선택본의 SHA-256·리비전·파일 해시를 다시 확인한 뒤 전체 미리보기 WAV를
Scribe로 새로 전사하고 Forced Alignment를 새로 호출한다. 전체 전사가
한글·어휘·언어 게이트를 먼저 통과한 경우에만 Forced Alignment를
호출한다. 모든 일반 자동 게이트와 설정된 모든 집중 발음 게이트도
통과하지 않으면 실패한다.

최종 `job.json`과 `qc_report.json`에는 다음을 기록한다.

- 상태: `user_delegated_auto_qc_final`
- `approval_type`: `delegated_automatic_qc`
- `human_listening_completed`: `false`

이 기록은 사람 청취 승인으로 변환하지 않는다. 최종 보고서에는 자동
STT·Forced Alignment·집중 발음 3회 합의가 자연스러움, 감정, 억양,
목소리 동일성을 완전히 보증하지 못한다는 한계를 포함한다.

## 보존과 비용

- `enable_logging=false`의 Zero Retention은 Enterprise 전용일 수 있으므로 기본 요청에서 사용하지 않는다.
- TTS POST는 중복 과금 위험 때문에 네트워크 오류에 자동 재시도하지 않는다.
- GET만 제한적으로 재시도한다.
- 새 coherent 레퍼런스의 초기 배치는 전체 대본 TTS POST 정확히 1회다.
- coherent retry는 현재 일회용 내부 토큰과 지속 설정의 상시 생성 허용을
  확인한 뒤 전체 대본 TTS POST 정확히 1회만 실행한다. 사용자에게 건별
  비용 승인을 요청하지 않는다.
- coherent 전체 take는 초기 요청을 포함해 최대 5회이며, 실패한 명령이
  다음 TTS를 자동 호출하지 않는다.
- 문장별 TTS는 한 배치 최대 5회다.
- STT와 Forced Alignment도 별도 사용량이 발생할 수 있다.
- 집중 발음 구절 하나당 후보 검사 시 Scribe STT 세 호출이 발생하며,
  기존 후보 재선택 검사에도 동일하게 세 호출이 발생한다.

## 공식 문서

- Audio Isolation: https://elevenlabs.io/docs/api-reference/audio-isolation/convert
- Instant Voice Clone: https://elevenlabs.io/docs/api-reference/voices/ivc/create
- IVC 권장 샘플: https://elevenlabs.io/docs/eleven-creative/voices/voice-cloning/instant-voice-cloning
- TTS with timestamps: https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- Speech to Text: https://elevenlabs.io/docs/api-reference/speech-to-text/convert
- Forced Alignment: https://elevenlabs.io/docs/api-reference/forced-alignment/create
- Models: https://elevenlabs.io/docs/overview/models
- Eleven v3 prompting: https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices

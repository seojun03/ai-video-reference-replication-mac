---
name: elevenlabs-reference
description: ElevenLabs API로 사용 권한이 확인된 1인 화자 레퍼런스 영상의 배경음악·효과음을 분리하고, 현재 작업의 레퍼런스 영상과 소스 해시가 일치하는 Instant Voice Clone을 만들거나 재사용해 한국어 대본 TTS를 만든다. 사용자가 다른 보이스를 명시하지 않은 한 이전 작업의 다른 레퍼런스 보이스를 자동 재사용하지 않는다. 1분 이하 대본은 한 번의 coherent-block 응답으로 생성해 문장별 태그·seed·속도 차이와 이어 붙이기 톤 변화를 막는다. 문장별 STT·강제 정렬·집중 발음 검사에 더해 레퍼런스 자연 변동 범위로 보정한 피치·에너지·리듬·문장 경계 검수와 실제 오디오 A/B 판정 3회 만장일치를 요구한다. 실제 오디오 입력 평가 도구가 없으면 청취했다고 주장하거나 자동 승인하지 않는다. 사용자가 일레븐랩스 레퍼런스 음성 복제, 영상 TTS 목소리로 새 대본 읽기, 문장마다 달라지는 톤·억양·감정·속도 교정, 엄격한 한국어 발음 검수 또는 승인형 음성 생성을 요청할 때 사용한다.
---

## 공유 플러그인 실행 경로

이 문서가 들어 있는 `skills`의 상위 폴더를 `PLUGIN_ROOT`로 확인하고, 먼저 `../../references/recipient-runtime.md`를 읽는다. `${PLUGIN_ROOT}`는 현재 설치된 이 플러그인의 절대 경로로, `${VIDEO_PRODUCT_LIBRARY_ROOT}`와 `${CAPCUT_AUTOMATION_ROOT}`는 수신자 환경의 경로로 해석한다. 하위 스킬은 이 플러그인 안의 형제 폴더를 우선 사용한다. 플러그인 제작·수정·공유 요청은 영상 제작 인터뷰나 유료 생성, 앱 종료를 시작하지 않는다.


# 일레븐랩스 레퍼런스

## 목적

권한이 확인된 레퍼런스 음성을 사용해 한국어 TTS 후보를 만들고 자동 검수한다. 이 로컬 사용자는 활성 요청 범위 안의 초기 생성과 교정 재생성을 작업당 총 5개 take까지 상시 허용했으므로, 생성 비용이나 재시도에 대한 별도 승인 문구를 요구하지 않는다. 사용자 청취는 생성 권한이 아니라 품질 피드백과 최종 선택을 위한 단계다. 별도 작업 지시가 없으면 모든 음성은 `natural_v3_conversational_coherent` 프리셋으로 생성한다.

## 필수 계약

- 음성 복제·재사용 전 사용 권한과 동의를 확인한다. 확인되지 않으면 중단한다.
- API 키는 `ELEVENLABS_API_KEY` 환경변수로만 읽는다. 채팅, `SKILL.md`, 작업 JSON, 명령 인자 또는 출력 로그에 키를 기록하지 않는다. `ffmpeg`, `ffprobe` 등 로컬 미디어 하위 프로세스에는 키·프록시 환경변수를 전달하지 않는다. ElevenLabs HTTP 세션도 환경변수·`.netrc`·macOS 시스템 프록시를 상속하지 않고 고정된 공식 API 엔드포인트에 직접 연결한다.
- 원본 영상과 대본을 수정하거나 덮어쓰지 않는다. 매 작업은 비어 있는 새 출력 폴더에서 시작한다.
- 새로 만든 clone은 ElevenLabs와 로컬 보이스 레지스트리에 계속 저장한다. 사용자가 명시적으로 요청하지 않으면 삭제하지 않는다.
- 자동 검수를 통과해도 자연스러운 발음·감정·억양·음색 동일성을 절대적으로 보증했다고 표현하지 않는다. 기본 경로의 최종 품질 판정은 사용자의 실제 청취 승인이다.
- STT·Forced Alignment 또는 피치 수치만으로 “직접 들었다”고 표현하지 않는다. 실제 음성을 입력받는 오디오 평가 도구가 없으면 `blocked_unavailable`로 실패 폐쇄한다.
- 실제 오디오 A/B 평가는 서로 다른 설정으로 정확히 3회 수행하며 모든 문장의 발음·톤·억양·감정·화자 캐릭터·경계·합성 흔적 항목이 3회 모두 통과해야 한다.
- 1분 이하 단일 화자 대본은 기본적으로 `coherent_block` 한 번의 TTS 응답으로 만든다. 문장별 후보 splice, 부분 배속, gain, 다른 donor 삽입본은 강화 QC에서 거절한다.
- 사용자 청취 승인 또는 사용자의 명시적 강화 자동 QC 최종화 위임 전에는 `final/`을 만들거나 “최종본”이라고 부르지 않는다.
- 승인은 현재 전체 미리보기의 SHA-256과 연결한다. 이전 리비전 승인이나 문장별 부분 승인을 최종 승인으로 승계하지 않는다.
- 한 작업에서 전체 take를 최대 5회만 생성한다. 5회 뒤에는 가장 나은 미리보기를 전달하고 멈추며, 추가 비용 승인 질문을 하지 않는다.
- 승인된 문장은 재생성하지 않는다. 거절되거나 실패한 문장만 다시 만든다.
- Eleven v3를 기본 모델로 사용한다. 계정에서 사용할 수 없으면 다른 모델로 조용히 대체하지 말고 중단한다.
- 사용자가 현재 작업에서 다른 설정을 명시하지 않은 한 `conversationally`, API `speed=1.15`, `stability=0.35`를 자연스러운 기본값으로 사용한다. 60초 이하 대본은 레이아웃용 줄바꿈을 제거한 한 번의 연속 발화로 만들고, 발음 교정을 이유로 단어·음절을 쪼개거나 문장 내부에 과도한 쉼을 넣지 않는다.

첫 실행 전에 [전체 실행 절차](references/workflow.md), [품질 게이트](references/quality-gates.md), [운율·실제 오디오 QC](references/prosody-listening-qc.md)를 전부 읽는다. API 오류를 조사하거나 엔드포인트를 수정할 때만 [API 계약](references/api-contract.md)을 읽는다.

## 입력 판별

현재 작업에 레퍼런스 영상이 있으면 그 파일을 TTS 보이스의 기본 소스로 사용한다. 사용자가 특정 기존 `voice_id`, 보이스 이름 또는 다른 음성 소스를 명시하지 않은 한 업체명·제품명·과거 성공 기록만으로 이전 보이스를 고르지 않는다. 먼저 현재 레퍼런스 영상의 SHA-256을 계산하고 로컬 보이스 레지스트리의 `source_sha256`과 정확히 일치하는 보이스가 하나 있으면 그 보이스만 재사용할 수 있다. 일치 보이스가 없으면 현재 레퍼런스에서 음성을 추출·분리해 새 Instant Voice Clone을 만든다. 다른 레퍼런스 해시의 보이스를 자동 재사용하면 `REFERENCE_VOICE_SOURCE_MISMATCH`로 중단한다.

영상 제작 상위 워크플로의 `clean_visual_reference_only`는 생성 영상에 레퍼런스의 리터럴 화면을 복사하지 않는다는 뜻일 뿐, TTS에서 현재 레퍼런스 음성을 제외한다는 뜻이 아니다. 별도 TTS 보이스 지시가 없으면 시각 레퍼런스와 동일한 현재 레퍼런스 파일을 음성 소스로 전달한다.

다음 두 모드 중 하나를 선택한다.

1. **새 보이스 생성**
   - 한국어 단일 화자 레퍼런스 영상
   - 배경음악·효과음 허용
   - `--reference-video`, `--new-voice-name`, `--consent-confirmed` 사용
2. **기존 보이스 재사용**
   - 정확한 `voice_id`를 우선 사용
   - `--consent-confirmed`로 재사용 권한을 확인
   - 이 스킬로 만든 보이스는 저장된 스타일 프로필을 재사용
   - 외부에서 만든 기존 보이스는 `--style-reference-video`를 함께 받아 속도·감정 기준을 새로 만든다

## 이 로컬 사용자의 지속 설정

이 설치에서는 사용자가 2026-07-29에 다음 지속 설정을 명시했다.

- 사용자가 이 스킬 작업용으로 직접 제공한 레퍼런스는 복제·재사용 권한과 동의를 보유한 것으로 확인한다. 같은 권한 질문을 반복하지 말고, 각 작업에는 해당 확인 시각·사용 모드·레퍼런스 SHA-256을 계속 기록하며 `--consent-confirmed`를 사용한다. 사용자가 권한이 없다고 말하거나 명백히 상충하는 정보가 있으면 생성하지 않고 중단한다.
- 숫자와 영문 토큰은 문맥상 자연스러운 표준 한국어 발음으로 자동 정규화하며 사용자에게 반복 확인하지 않는다. 예: `2주`→`이 주`, `MD`→`엠디`, `1,100개`→`천백 개`, `37%`→`삼십칠 퍼센트`, `2개`→`두 개`. 원문과 실제 발화문을 모두 작업 기록에 보존한다.
- API 키 값을 채팅으로 요청하거나 로컬 작업 파일·레지스트리에 저장하지 않는다. macOS Keychain 같은 로컬 비밀 저장소에서 실행 시점의 `ELEVENLABS_API_KEY` 환경변수로만 주입한다. 키가 확인되는 동안 재질문하지 않으며, 확인되지 않으면 값을 요청하지 말고 `blocked_missing_api_key`로 보고한다.
- 사용자는 2026-08-19에 활성 요청 범위 안의 ElevenLabs 초기 생성과 발음·감정·속도 교정 재생성을 작업당 총 5개 take까지 상시 허용했다. `TTS 1회 추가 생성 승인`, `추가 비용 승인` 또는 같은 의미의 확인을 사용자에게 절대 요청하지 않는다. `status`의 일회용 토큰과 CLI 호환용 `--additional-cost-approved` 플래그가 필요하면 에이전트가 내부적으로 처리한다. 자동 검수 실패 또는 사용자의 품질 피드백으로 재생성이 필요하면 남은 take 한도 안에서 바로 실행하고, 5개를 모두 사용하면 가장 나은 미리보기를 전달한 뒤 중단한다. 이 상시 허용은 사용자가 요청하지 않은 별도 대본·보이스·작업으로 범위를 넓히는 권한이 아니다.
- 기존 작업 상태가 레거시 이름인 `coherent_retry_approval_required`로 표시돼도 사용자 승인이 필요하다는 뜻으로 해석하지 않는다. 남은 take가 있음을 나타내는 내부 상태로 취급하고 토큰을 자동 사용한다.
- 매 작업 시작 시 `~/.codex/state/elevenlabs-reference/user_preferences.json`을 읽고 적용한 설정과 파일 SHA-256을 작업 기록에 남긴다. 사용자가 새 요청에서 다른 전달 방식을 명시하면 그 작업에만 최신 요청을 우선하고 지속 설정을 조용히 덮어쓰지 않는다.
- 사용자는 2026-08-19에 모든 이후 음성을 직전 승인형 자연 발화 기준처럼 생성하도록 지정했다. 현재 작업에서 별도 모델·톤·속도 지시가 없으면 `user_preferences.json`의 `natural_voice_generation_policy`를 그대로 적용한다. 기본값은 Eleven v3, `conversationally`, `speed=1.15`, `stability=0.35`, 60초 이하 전체 대본 단일 coherent take다. 이 값은 보이스의 음색을 서로 같게 만들라는 뜻이 아니라, 각 보이스가 사람처럼 자연스럽게 연결 발화하도록 만드는 공통 전달 방식이다.
- 기본 전달 목표를 `reference_maximum_match_natural_connected_speech`로 사용한다. 분리된 레퍼런스의 화자 캐릭터·음색·평균 톤·피치 범위·에너지·활성 발화율·억양 성향·쉼 및 호흡 밀도를 우선 기준으로 삼고, 새 대본의 의미와 문법 경계에 맞게 자연스럽게 전이한다. 레퍼런스 분석과 무관한 `slowly`, `calmly`, `energetically` 같은 수동 태그로 스타일을 임의 덮어쓰지 않는다.
- 60초 이하 대본은 원문의 어휘와 문장부호 의미를 보존하되 레이아웃용 줄바꿈과 빈 줄을 공백으로 정리해 한 문단처럼 전달한다. 문장 내부는 자연스럽게 이어 읽고 문장 끝에서만 짧게 쉰다. 발음 교정을 위해 쉼표·대시·마침표를 과도하게 삽입하거나 음절을 기계적으로 분리하지 않는다. 발음 문제는 알려진 붙임말 발음 사전 → seed·stability 재시도 → 자연스러운 문법 경계의 문장부호 전용 전체 대본 override 순서로 해결한다. 사후 타임 스트레치는 사용하지 않는다.
- `창상피복재`는 항상 한 단어로 붙여 생성하고 단어 내부에 공백·쉼표·대시·마침표를 넣지 않는다. 숫자·영문 자동 발음과 함께 `user_preferences.json`의 `no_split_terms` 및 알려진 발음 매핑을 그대로 적용한다.
- “레퍼런스와 똑같이”는 가능한 최대 스타일 전이 목표로 기록한다. 새 대본은 음절 수와 의미가 달라 레퍼런스의 순간별 억양·호흡 시점을 시간축 그대로 복사하거나 완전 동일성을 보증할 수 없다. 대신 레퍼런스의 자연 변동 범위 안에서 전 항목을 최적화하고, 실제 동일감은 사용자 전체 청취 승인으로만 판정한다.
- TTS 보이스 선택 기본값은 `current_job_reference_video_unless_explicit_voice_override`다. 현재 작업 레퍼런스의 SHA-256과 동일한 저장 보이스만 자동 재사용하고, 다른 해시의 과거 보이스는 사용자가 그 보이스를 직접 지정한 경우에만 사용한다. 새 레퍼런스면 Audio Isolation과 단일 화자 검증 후 새 clone을 만든다.

대본은 UTF-8 한국어 텍스트 파일로 받는다. 기본적으로 숫자와 영문 토큰이 발견되면 임의로 읽지 말고 한글 발음을 확인한다. 단, 위의 이 로컬 사용자 지속 설정이 활성화된 경우에는 원문을 보존한 채 문맥상 자연스러운 표준 한국어 발음으로 자동 정규화하고 반복 확인하지 않는다.

사용자는 문장 앞에 다음과 같은 선택적 지시를 넣을 수 있다.

```text
[신나게] 오늘은 정말 반가운 소식이 있어요!
[강조] 이 부분이 가장 중요합니다.
[차분하게] 천천히 하나씩 살펴볼게요.
```

지시가 없으면 대본 의미와 레퍼런스의 속도·피치 범위에서 휴리스틱 감정 지시를 선택한다. 이는 감정 동일성을 자동 증명하지 않는다. 기본 경로에서는 전체 미리보기 청취로 판정하고, 명시적 위임 경로에서는 확인되지 않은 한계로 기록한다.

## 실행

### 1. 준비 확인

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py doctor
```

API 키가 환경에 설정된 뒤 라이브 권한과 Eleven v3 사용 가능 여부를 확인한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py doctor --live
```

API 키가 없으면 사용자가 로컬 환경변수로 설정하도록 안내하고 멈춘다. 키 값을 요청하지 않는다.

### 2A. 새 레퍼런스 보이스

1분 이하 대본의 기본 새 레퍼런스 경로는 `run-new`다. 레퍼런스 준비와
clone 뒤 전체 대본을 정확히 한 번의 TTS 요청으로 생성한다. 이후 교정
take도 상시 생성 허용과 작업당 최대 5회 한도 안에서 별도 질문 없이 처리한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/coherent_block.py run-new \
  --script "/절대경로/대본.txt" \
  --reference-video "/절대경로/레퍼런스.mp4" \
  --new-voice-name "사용자가 정한 보이스 이름" \
  --delivery-tag "conversationally" \
  --speed 1.15 \
  --stability 0.35 \
  --consent-confirmed \
  --output-dir "/절대경로/새 작업 폴더"
```

현재 로컬 기본값은 `conversationally`, `speed=1.15`, `stability=0.35`다.
사용자가 현재 작업에서 다른 전달 방식을 명시한 경우에만 그 값을 우선한다. 60초를 넘는
대본이나 기존 문장별 호환이 필요한 작업만 별도 계획을 세운다. clone 뒤
레퍼런스 발화율로 계산한 보수적 예상 상한이 60초를 넘으면
`blocked_before_tts` 증거를 남기고 첫 유료 TTS 호출 전에 중단한다.

### 2B. 기존 보이스

먼저 로컬에 저장된 보이스와 필요하면 ElevenLabs 계정 보이스를 확인한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py list-voices --cloud
```

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/coherent_block.py run-existing \
  --script "/절대경로/대본.txt" \
  --voice-id "정확한_voice_id" \
  --delivery-tag "conversationally" \
  --model-id "eleven_v3" \
  --speed 1.15 \
  --stability 0.35 \
  --consent-confirmed \
  --output-dir "/절대경로/새 작업 폴더"
```

저장된 스타일 프로필이 없는 기존 보이스에는 `--style-reference-video "/절대경로/레퍼런스.mp4"`를 추가한다. 이름이 중복될 수 있으므로 가능하면 `voice_id`를 사용한다.

## 집중 발음 검증

뭉개지기 쉬운 단어나 구절은 선택본이 없는 동안 `set-focus`로 지정한다.
구절은 원래 발화문과 강제 정렬 결과에 각각 정확히 한 번 존재해야 한다.
강제 정렬 위치에서 인접 단어는 제외하되 바로 앞에 맞닿은 공백·문장부호
경계부터 잘라 초성이 잘리지 않게 한다. 구절이 정렬 문자열의 맨 앞에서
시작하면 오디오 0초 경계를 사용한다. 구절이 마지막 어휘에서 끝나면
뒤따르는 문장부호와 실제 오디오 끝까지 보존해 종성·모음 릴리스를 자르지
않고, 그 밖에는 다음 단어의 시작 전에서 자른다. 잘라낸 구절에는 앞뒤
각 0.2초 무음을 붙이되, 집중 구절이 원본 WAV 전체 범위를 그대로
사용하면 원래의 앞뒤 여백을 유지하고 인위적 무음은 더하지 않는다.
지정된 seed·temperature 세 조합의 STT가 모두 정확히 일치해야 통과한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py set-focus \
  --job-dir "/절대경로/작업 폴더" \
  --segment 6 \
  --phrase "일반 보습제로는" \
  --phrase "보습제로는" \
  --reason "사용자가 지적한 발음 불명확"
```

필요하면 `--direction "친근하게"`와 `--tts-override "한글 발음 유도 문장"`을
함께 지정한다. 기존 후보를 `select-attempt`로 복원할 때도 설정된 집중
발음 검사를 새로 실행한다.

전체 미리보기와 최종본을 조립할 때는 문장별 WAV를 각각
mono·48kHz·24-bit PCM으로 먼저 디코딩한 뒤 PCM 프레임을 순서대로
이어 붙인다. 입력 WAV의 비트 심도가 섞여 있어도 concat demuxer에
직접 넘기지 않는다. 결과의 총 프레임 수와 PCM 해시가 정규화된
문장별 PCM 순서와 다르면 조립을 실패 처리하고 기존 파일을 보존한다.

## 운율·실제 오디오 검수

1분 이하의 기존 완료 작업을 톤 연결성 문제로 다시 만들 때는 새 빈
리비전 폴더에 전체 대본 연속 take를 생성한다. 작업당 총 5개 take의
상시 생성 허용 범위에서 실행하며 사용자에게 비용 승인을 묻지 않는다.
실제 오디오 QC 전에는 최종화하지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/coherent_block.py run \
  --source-job "/절대경로/기존 완료 작업" \
  --output-dir "/절대경로/새 빈 리비전" \
  --delivery-tag "conversationally" \
  --speed 1.15 \
  --stability 0.35 \
  --seed 173 \
  --attempts 5 \
  --reason "문장별 톤·억양 불일치 제거" \
  --additional-cost-approved
```

어려운 발음 때문에 전체 take가 실패하면 원 대본은 보존한 채
`--tts-override-script "/절대경로/발음 유도용 전체 대본.txt"`를 쓸 수
있다. 검수와 Forced Alignment 기준은 항상 원래 발화문이다.

전체 미리보기가 생기면 STT 통과만으로 사용자에게 승인 요청을 보내지
않는다. 배경음악·효과음이 제거된 레퍼런스 WAV로 객관적 운율·문장 경계를
먼저 검사한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py prosody-qc \
  --job-dir "/절대경로/작업 폴더" \
  --reference-wav "/절대경로/reference_isolated.wav"
```

실제 오디오 입력을 지원하는 평가 수단의 서로 다른 설정 3회 결과가
준비되면 같은 현재 미리보기에 연결한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py prosody-qc \
  --job-dir "/절대경로/작업 폴더" \
  --reference-wav "/절대경로/reference_isolated.wav" \
  --audio-judge-report "/절대경로/audio-judge-report.json"
```

객관적 실패 문장은 재생성한다. `coherent_block` 작업에서는 한 문장만
splice하지 않고 전체 take를 다시 만든다. `status`의 현재 일회용 토큰은
에이전트가 내부적으로 읽어 다음 명령에 전달하며 사용자에게 승인 질문을
하지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/coherent_block.py retry \
  --job-dir "/절대경로/작업 폴더" \
  --approval-token "status가 발급한 현재 토큰" \
  --feedback "재생성 이유" \
  --additional-cost-approved
```

한 `retry` 호출은 전체 대본 TTS를 정확히 한 번만 요청하고 토큰을 먼저
소진한다. 실패하면 새 내부 토큰을 사용해 총 5회 한도 안에서 필요한 다음
교정 take를 이어서 만들 수 있다. 사용자에게 생성 승인을 요구하지 않는다.
실제 오디오 입력 평가 수단이 없으면 `awaiting_audio_listening_qc`에서
멈추며, 객관적 수치 분석을 청취라고 표현하지 않는다.

## 청취 피드백과 최종화

STT·정렬·집중 발음·운율과 실제 오디오 A/B 3회 검수가 모두 통과한
상태만 `awaiting_user_listening_approval`이다. 이때 다음 파일을
사용자에게 실제로 재생할 수 있는 로컬 링크로 제시한다.

```text
<작업 폴더>/review/full_preview.mp3
<작업 폴더>/review/segments/001.mp3
```

Codex 앱에서는 절대경로를 사용해 다음 형태로 재생한다.

```markdown
![전체 음성 미리보기](/절대경로/review/full_preview.mp3)
```

사용자에게 정형화된 승인 문구를 요구하지 않는다. 미리보기를 들은 뒤
`이걸로 가자`, `괜찮아`, `이 음성 사용해`처럼 자연어로 선택하면 청취
확인으로 기록할 수 있다. 청취 여부가 드러나지 않으면 미리보기 상태로
유지하되 TTS 생성 권한을 다시 묻지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py status \
  --job-dir "/절대경로/작업 폴더"
```

`status`에 표시된 현재 `preview_sha256`을 그대로 사용한다.

선택 음성을 새로 생성하지 않고 안전한 조립 규칙으로 미리보기만 다시
만들어야 할 때는 다음 명령을 사용한다. 새 리비전과 SHA-256이 발급되며
이전 승인·해시는 승계하지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py rebuild-preview \
  --job-dir "/절대경로/작업 폴더" \
  --reason "미리보기 재조립 사유"
```

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py approve \
  --job-dir "/절대경로/작업 폴더" \
  --segments all \
  --confirmation "사용자가 전체 미리보기를 직접 듣고 승인함" \
  --preview-sha256 "status에_표시된_현재_SHA-256"
```

사용자가 전체 미리보기 직접 청취를 생략하고 강화 자동 검증 기반
최종화를 명시적으로 위임한 경우에만 별도 명령을 사용한다. 이 명령은
모든 선택 후보와 리뷰 파일의 일치·해시, 모든 일반/집중 발음 게이트,
전체 미리보기의 새 STT와 Forced Alignment를 다시 확인한다. 결과를
사람 청취 승인으로 기록하지 않는다.

장문 전체 미리보기 STT가 정확 일치하지 않더라도 비어 있지 않은
한국어인 경우에만 보조 검증 후보가 된다. 장문 전사의 누락·치환 여부는
진단으로 보존한다. 선택된 문장별 WAV를 각각 공통 PCM으로 독립
디코딩해 순서대로 누적한 프레임 수·해시와 실제 미리보기의 공통 PCM
프레임 수·해시가 완전히 같아야 한다. 실제 미리보기의
mono·48kHz·24-bit 형식, 클리핑, 활성 음성도 하드 게이트다. 이후
모든 문장별 WAV를 서로 다른 설정으로 3회 새로 전사해 세 결과가 모두
정확해야 하며, 그때만 새 Forced Alignment를 실행한다. 한 검사라도
다르면 최종화하지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py delegate-approve \
  --job-dir "/절대경로/작업 폴더" \
  --segments all \
  --confirmation "사용자가 전체 미리보기 직접 청취를 생략하고 강화 자동 검증 기반 최종화를 위임함" \
  --preview-sha256 "status에_표시된_현재_SHA-256"
```

### 상위 워크플로 자동모드 위임

`$ai-video-reference-replication` 또는 `$ai-video-reference-tts-workflow`가 전체 기획을 제시한 뒤 사용자가 `자동모드`를 선택하고, 그 원문 응답을 `execution_mode: "auto"`와 함께 매니페스트에 보존한 경우 이를 전체 미리보기 직접 청취 생략에 대한 명시적 자동 QC 위임으로 취급할 수 있다. 부모 워크플로는 현재 자동 QC가 모두 통과했을 때만 위의 정확한 `DELEGATED_AUTO_APPROVAL_CONFIRMATION` 문구로 `delegate-approve`를 호출한다. TTS 생성·재생성은 별도 승인 없이 상시 허용 범위에서 진행한다. 자동 QC가 실패하면 `preview`/`working_audio`로 남기고 CapCut 편집을 이어가되 최종 TTS라고 부르지 않는다.

발음이나 감정이 어색하다는 피드백을 받으면 해당 문장만 추가 생성한다.
남은 take 한도 안에서 다음 명령을 바로 사용하며 승인 질문을 하지 않는다.

사용자가 보존된 이전 후보를 직접 듣고 그 후보로 되돌리길 원하면 새 TTS를
만들지 말고 해당 후보를 현재 기준으로 재검수한다. 전체 미리보기 승인이
아닌 문장 후보 선택으로만 기록한다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py select-attempt \
  --job-dir "/절대경로/작업 폴더" \
  --segment 2 \
  --attempt 1 \
  --confirmation "사용자가 해당 이전 후보를 직접 듣고 선택함"
```

먼저 `status`를 다시 확인하고 표시된 현재 `additional_generation_token`을
에이전트가 내부적으로 한 번만 사용한다. 토큰을 사용자에게 보여주거나
승인 문구를 요청하지 않는다.

```bash
python3 ${PLUGIN_ROOT}/skills/elevenlabs-reference/scripts/elevenlabs_reference.py regenerate \
  --job-dir "/절대경로/작업 폴더" \
  --segments "3" \
  --feedback "사용자가 설명한 어색한 발음 또는 감정" \
  --direction "차분하게" \
  --approval-token "status에_표시된_일회용_토큰" \
  --additional-cost-approved
```

발음 표기를 바꿔 유도해야 할 때만 `--tts-override "한글 발음 유도 문장"`을 추가한다. 원래 대본은 그대로 보존하며 자동 검수는 원래 발화문을 기준으로 한다.

## 완료 조건

다음을 모두 만족해야 완료다.

- 모든 문장이 자동 검수 통과
- 전체 미리보기 파일 생성
- 사용자가 전체 미리보기를 직접 듣고 명시적으로 승인하거나, 직접 청취
  생략과 강화 자동 QC 최종화를 명시적으로 위임
- `job.json` 상태가 `user_approved_final` 또는
  `user_delegated_auto_qc_final`
- 다음 산출물이 모두 존재
  - `final/final.wav`
  - `final/final.mp3`
  - `final/segments/*.wav`
  - `final/segments/*.mp3`
  - `final/script.txt`
  - `final/qc_report.json`

완료 응답에는 최종 WAV·MP3와 문장별 폴더를 절대경로 링크로 제공한다.
위임 경로라면 `human_listening_completed: false`와 자동 검수의 남는 한계를
함께 알린다. 자동 검수만 통과하고 승인이나 위임이 없다면 “검수 대기 중
미리보기”라고 명확히 말한다.

작업 폴더에는 레퍼런스에서 파생된 음성, 전사문, 실패 후보가 품질 재검수와 선택 재생성을 위해 남는다. 이는 클라우드 보이스 보존과 별개다. 최종 완료 시 이 보존 사실을 알리고, 사용자가 원할 때만 정확한 작업 폴더를 삭제한다.

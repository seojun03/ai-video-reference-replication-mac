# 문맥별 컷편집 실행

## 실행 환경과 금지된 우회

이 저장기는 **대본·클린본·음성을 새로 조합하는 모드 전용**이다. 기존 타임라인의 효과/스타일을 보존하며 수정하는 범용 저장기가 아니다. 기존 `run_capcut_automation.py`의 차단을 풀거나 `create_capcut_draft`, 업체별 설치기, 전체 `capcut_auto` 파이프라인을 실행하지 않는다.

필요 환경은 Python, FFmpeg/ffprobe, Pillow, pycapcut이다. 현재 로컬 환경에서는 다음 경로를 확인해 사용할 수 있다. 다른 컴퓨터에서는 해당 환경이 실제 존재하는지 먼저 확인한다. 자동 설치/다운로드/외부 전송은 하지 않는다.

```sh
CAPCUT_SEMANTIC_PY="$HOME/.local/share/ai-video-reference-replication/venv/bin/python"
CAPCUT_SEMANTIC_CLI="${PLUGIN_ROOT}/skills/capcut-semantic-cut-edit/scripts/semantic_cut.py"
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" --help
```

아래 `/작업/...`는 형식 예시다. 이번 작업의 실제 **프로젝트 밖 고유 작업 폴더**로 치환한다. 같은 출력은 덮어쓰지 않는다. 중간 수정은 사용자가 승인한 로컬 계획 파일만 수정하고 검사를 다시 한다.

## 0. 제품 종류 확인 후 화면 프로필과 저장 프로젝트

[제품 종류 인터뷰](visual-direction.md)를 먼저 마친 뒤 선택된 분야의 화면 프로필을 적용한다. 종류를 제품명으로 추정해 이 단계부터 시작하지 않는다. 분야별 학습은 화면 선택에만 사용하고 자막·호흡·무음·싱크·공통 컷 기준과 아래 실행 경로는 그대로 유지한다. 사용자에게 기준 타임라인을 다시 묻거나 새 타임라인 생성 문구를 요구하지 않는다. 종류와 저장 프로젝트가 확인되면 다음 읽기 전용 명령으로 내부 형식 연결을 확인할 수 있다. 미디어 분석이나 완성된 계획이 없어도 실행 가능하다.

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" resolve-project \
  --project '/정확한 기존 업체 프로젝트 경로' --project-name '정확한 기존 업체 프로젝트명'
```

반환된 `source_id`/`source_name`의 용도는 `native_schema_only_not_editing_reference`다. 현재 프로젝트의 유효한 메인 타임라인, 메인이 없으면 유일한 유효 타임라인에서 기술 형식만 읽는다. 이는 새 편집 기준/스타일을 임의 선택한 것이 아니며, 화면 학습 사례의 타임라인을 저장 대상으로 삼는 것도 아니다. 유효한 메인이 없고 후보가 여러 개면 `PROJECT_SCHEMA_ANCHOR_UNAVAILABLE`로 실제 프로젝트 구조 문제를 보고한다.

유효한 후보는 일반 파일의 JSON 객체이고 등록 ID가 일치하며, 양의 정수 `version`과 비어 있지 않은 `new_version`을 가진다. 선택적인 플랫폼 정보도 있으면 객체여야 한다. 잘못된 자동 후보는 제외하되 파일은 수정하지 않는다. 사용자가 명시한 타임라인이 불완전하면 `SOURCE_SCHEMA_INVALID`로 보고하고 다른 타임라인으로 대체하지 않는다.

## 1. 자료 목록과 음성

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" inventory \
  --script '/작업/대본.txt' --voice '/작업/음성.wav' \
  --clean-dir '/작업/이번 제품 클린본' --product '이번 제품명' \
  --output '/작업/run-001/inventory.json'

"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" init-plan \
  --inventory '/작업/run-001/inventory.json' --category food \
  --voice-kind tts --use-action eating --fps 30 \
  --output '/작업/run-001/plan.json'

"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" analyze-voice \
  --inventory '/작업/run-001/inventory.json' --kind tts \
  --output '/작업/run-001/source-audio-review'
```

- `--clean`을 반복해서 파일을 직접 지정할 수도 있다. `--clean-dir`은 지정 폴더 내부 영상만 찾는다. 그 안의 자료가 이번 제품의 제공 소스인지 사용자 입력 범위를 확인한다.
- 분야는 현재 인터뷰 응답 **1=건기식 `supplement`, 2=뷰티 `beauty`, 3=식품 `food`, 4=그외 `other`**를 정규화해 전달한다. 상위 `production_intake`가 있으면 그 `capcut.category`와 응답 원문을 승계하고 재질문하지 않는다. 위 `--category food`는 식품 선택 후의 예시다. 실제 사용 행동은 `eating / application / product_use`이며 `product_use`는 `other`의 실제 조작·시연에만 쓴다. 음성은 `recorded / tts`이며 확장자만 보고 추정하지 않는다.
- `init-plan`은 **미검토 초안**이다. 빈 관찰 기록·전사·장면 때문에 그대로 검증/저장할 수 없다. 승인된 편집을 생성했다고 보고하지 않는다.
- `analyze-voice`는 공통 정책의 복수 검출 수준으로 중간 쉼 후보와 파형을 제공한다. TTS와 녹음의 공통 스킬 기준을 구분한다. 의도적인 쉼·발화·말실수를 실제 내용과 함께 확인하고 삭제 후보를 선택한다. 전사/말실수 판단을 자동으로 한 결과가 아니다.
- 전사가 필요하면 공통 실행 문서의 로컬 전사 모듈을 먼저 확인한다. 캐시된 모델/도구가 없으면 외부 전송이나 모델 다운로드를 임의 수행하지 말고 해당 누락을 알린다. 수동 제공 전사도 현재 음성과 확인한다.

## 2. 최종 음성 컷과 기준 시각

`plan.voice.cuts`를 원본 순서대로 적는다. 각 행은 `source_in_us`, `start_frame`, `end_frame`이다. 원속 재생 길이는 `floor(end_frame*1000000/fps) - floor(start_frame*1000000/fps)`로 계산되며, 같은 길이만 원본에서 가져온다. 삭제만 가능하고 원본 구간 재생 순서를 뒤집거나 반복하지 못한다. `review_note`에는 실제 삭제/보존 판단, `transcript`에는 편집 후 실제 발화 문구를 적는다.

완성 영상 길이 `composition.duration_frames`와 음성 컷의 마지막 프레임을 일치시킨다.

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" prepare-audio \
  --plan '/작업/run-001/plan.json' --output '/작업/run-001/final-audio-review'
```

생성된 `speech-evidence.json`의 `audio`, `cut_sha256`와 실제 검토한 `review_note`를 `plan.speech`에 넣는다. 파형 행 전체를 계획에 복사할 필요는 없다. 확인용 WAV는 모노 PCM이며 **타임라인의 대체 원본이 아니다**. 실제 네이티브 음성 트랙은 사용자 원본 파일의 편집 가능한 컷들이다. 생성된 PCM이 그 원본 컷과 같음을 저장 전 다시 비교한다.

단어별 ASR 시각은 탐색용이다. 최종 음성에서 실제 첫소리를 확인하고 자막 `onset_us`에 기록한다. 시간은 정수 마이크로초, 타임라인 위치는 정수 프레임이다. `frame_us(start) <= onset_us < frame_us(start+1)`를 만족해야 한다. 옛 음성 시각/문자 수/균등 분할로 onset을 채우지 않는다.

현재 저장기는 첫 의미 구간·첫 영상·첫 자막이 0번 프레임에서 시작하고 실제 첫소리도 그 프레임 안에 있는 구성을 지원한다. 불필요한 시작 무음은 실제 청취 후 공통 기준에 따라 컷할 수 있다. 다만 **의도적인 시작 쉼을 보존해야 해서 첫 발화가 다음 프레임 이후에 오는 구성은 현재 지원하지 않는다.** 이때 `LEADING_SPEECH_ALIGNMENT_REQUIRED`를 보고하고 입력과 쉼을 유지한다. 통과 목적으로 음성을 자르거나 onset/자막/영상 시각을 조작하지 않는다. 첫 자막을 0으로 옮겼다고 실제 발화 정합이 해결되는 것이 아니다.

## 3. 의미 구간·장면·자막

세 목록을 작성한다. 아래는 **형식 예시**이지 실제 관찰 결과가 아니다.

```json
{
  "beats": [{"id": "b01", "start_frame": 0, "end_frame": 60,
             "text": "먹어보니 바삭해요", "intent": "실제 섭취와 질감 표현"}],
  "captions": [{"id": "c01", "beat_id": "b01", "start_frame": 0, "end_frame": 60,
                "text": "먹어보니 바삭해요", "onset_us": 18000,
                "onset_note": "현재 최종 음성에서 확인한 첫소리 근거를 적음"}],
  "clips": [{"id": "v01", "beat_id": "b01", "asset_id": "clean-001",
             "start_frame": 0, "end_frame": 60, "source_in_us": 1000000,
             "volume": 0, "speed": 1,
             "selection": {"mode": "context", "action": "eating", "reason": "실제 관찰한 선택 이유"},
             "framing": {"scale": 1.2, "center_x": 0.5, "center_y": 0.5}}]
}
```

- `beats`는 첫 프레임부터 끝까지 빈틈없는 의미 구간이다. `captions`는 실제 발화 문구를 단어/소수점/순서 그대로 유지하고 문장 끝 마침표만 제거한다. 첫 자막은 첫 의미/영상 시작, 각 자막 끝은 다음 자막 시작, 마지막은 완성 영상 끝이다.
- 표시 자막이 길면 같은 `beat_id` 안에서 자연스럽게 나누고 영상은 유지한다. 새 의미 시작에는 영상이 있어야 한다. 같은 의미 안에 컷을 더 넣는 경우에도 실제 발화 자막 경계에서만 바꾼다. 불필요한 기술 분할은 합친다.
- `source_in_us`는 원본 내부 절대 시각이다. 위 30fps·60프레임 예에서는 원본 1–3초를 사용한다. 검토할 범위도 정확히 이 범위여야 한다.
- `framing`의 중심은 원본 표시 좌표의 0–1 범위다. 가로세로 비율 크롭과 확대 뒤 가능한 이동 범위 안으로만 중심이 제한된다. 확대는 1.0 이상 1.5 미만. 추가 crop/비균일 확대/회전/키프레임을 넣지 않는다.
- 소스 길이가 부족하고 유효한 대체도 없으면 `gaps`에 `id, beat_id, start_frame, end_frame, reason`을 적는다. 같은 의미 구간의 마지막 꼬리만 가능하다. 다음 영상 시간을 당기지 않으며 결과에 공백을 알린다.

선택한 각 실제 구간에 대해 실행한다:

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" contact-sheet \
  --inventory '/작업/run-001/inventory.json' --asset-id clean-001 \
  --start-us 1000000 --end-us 3000000 --scale 1.2 --center-x 0.5 --center-y 0.5 \
  --output '/작업/run-001/visual-v01'
```

`contact-sheet.jpg`와 필요시 개별 프레임을 실제로 본다. `review.json`에 실제 관찰 `note`를 적고 그 객체를 해당 clip의 `review`로 넣는다. 경로/시각/크롭 값만 고쳐 낡은 이미지를 재사용하지 않는다. 저장 전 원본에서 다시 추출한 프레임과 비교하므로, 범위/보정을 바꾸면 이미지도 새로 만들어야 한다. 반복 구간은 최종 영상 앞 1/3과 뒤 1/3 조건을 만족할 때만 최대 두 번이다.

## 4. 검증·대상 고정·준비본

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" validate --plan '/작업/run-001/plan.json'

"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" bind \
  --plan '/작업/run-001/plan.json' --project '/정확한 기존 업체 프로젝트 경로' \
  --project-name '정확한 기존 업체 프로젝트명' \
  --output '/작업/run-001/binding.json'

"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" stage \
  --plan '/작업/run-001/plan.json' --binding '/작업/run-001/binding.json' \
  --output '/작업/run-001/stage'
```

- 기존 프로젝트와 저장 형식 연결을 `Timelines/project.json` 및 실제 `draft_info.json`에서 자동 확인한다. `main_timeline_id`는 **기술 형식 연결용**일 뿐 사용자의 편집 레퍼런스라는 뜻이 아니다. 가장 최근 파일/첫 항목으로 대체하지 않는다.
- `--source-id`, `--source-name`, `--destination-name`은 선택 사항이다. 일반 호출에서는 모두 생략한다. 사용자가 특정 기존 타임라인이나 새 이름을 직접 지정했다면 해당 옵션만 전달한다. 명시한 소스가 없거나 중복이면 임의 대체하지 않는다. 새 이름을 생략하면 제품명 기반의 `컷편집 v001`, `v002` 등으로 기존 등록과 충돌하지 않게 만든다.
- 바인딩에는 프로젝트 이름/경로/두 프로젝트 ID, 소스 이름/ID, 고유 새 ID/이름, 계획 해시, 기존 파일 해시가 들어간다. 기술 스키마 정보만 기존 소스에서 가져오며 기존 트랙·제품·효과를 복제하지 않는다.
- 준비본은 프로젝트 밖에만 생성한다. 사용한 원본과 폰트만 byte-identical 사본으로 넣고 파일 해시를 비교한다. 사용하지 않은 영상 풀 전체를 복사하지 않는다.
- 폰트는 Pretendard SemiBold 기본이다. 도구는 실제 폰트의 1080 너비 기준 78px 사전 측정과 84% 안전 폭을 사용한다. 이는 native 폰트 크기 13의 **사전 레이아웃 검사**이며 실제 앱 렌더 확인은 별개다. 다른 폰트 명시 요청은 설치된 실제 파일을 `--font`로 지정할 수 있으나 문법/화면 확인은 다시 한다.
- 현재 자동 저장기는 자막 포함·9:16·원속·기본 한 줄 자막 조합만 지원한다. 예외를 맞추려고 검사를 제거하지 않는다.

## 5. 실제 등록과 재확인

CapCut이 열려 있으면 [공통 자동 저장·정상 종료 절차](../../capcut-cut-edit/SKILL.md#실행-중인-capcut의-자동-저장정상-종료)를 수행해 현재 작업을 저장하고 직접 정상 종료한다. **사용자에게 종료나 종료 승인을 요청하지 않는다.** 종료와 잠금 해제를 확인한 뒤 계속하며, 저장 중 앱이 다시 실행되면 쓰기를 중단하고 같은 절차로 상태를 재확인한다. 켜진 채로 쓰거나 강제 종료/잠금 삭제를 하지 않는다. 앱 종료로 기존 파일이 바뀌었다면 예전 계약을 조작하지 말고 최신 사용자 편집을 보존한 새 바인딩/준비본을 생성한다.

```sh
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" install --stage '/작업/run-001/stage'
"$CAPCUT_SEMANTIC_PY" "$CAPCUT_SEMANTIC_CLI" verify --stage '/작업/run-001/stage'
```

독립 쓰기 잠금 → 앱/프로젝트 잠금 → 원본/계약/프레임/음성 재검사 → 외부 색인 백업 → 새 폴더 독점 생성 → 등록 직전 다시 검사 → 색인에 새 항목 하나 추가 → 저장본/원본 불변성 비교 순서다. 기존 메인 타임라인과 탭 배치는 바꾸지 않는다. 재열었을 때 새 이름을 타임라인 목록에서 선택할 수 있는 등록본이며, 앱 화면을 자동으로 전환했다는 뜻은 아니다.

실패하면 기존 항목을 삭제·덮어쓰지 않는다. `INSTALL_INTERRUPTED`는 새 미등록 폴더/색인 백업의 정확한 위치를 표시한다. 자동 재시도·원본 복구·폴더 삭제 없이 상태를 보고한다. 앱 실행 중에 롤백을 시도하지 않는다.

`registered_pending_native_playback`은 **파일 등록과 역검증 통과**다. 실제 CapCut 재생, 입·손 동작의 자연스러움, 렌더된 자막 위치, MP4 출력 확인은 별개다. JSON/PCM 테스트만으로 이 항목들을 통과라고 기록하지 않는다.

## 유지보수 검사

```sh
"$CAPCUT_SEMANTIC_PY" -m unittest discover \
  -s '${PLUGIN_ROOT}/skills/capcut-semantic-cut-edit/tests' -p 'test_*.py' -v
```

테스트는 합성 미디어와 임시 프로젝트만 생성한다. 실제 업체 프로젝트를 대상으로 삼지 않는다. 구현 상세 형식이 필요하면 `tests/test_contract.py`의 완전한 계획 픽스처와 `tests/test_media_native.py`의 실제 파일 연결 예제를 참고한다. 테스트용 음성/관찰 문구를 실작업 증거에 복사하지 않는다.

## 최종 중간 쉼 검수

`prepare-audio`가 `speech-evidence.json`의 `pause_audit`에 최종 전체 음성의 후보와 검토 초안을 넣는다. [공통 검수 절차](../../capcut-cut-edit/references/pause-audit.md)를 따라 원본 후보 처리 기록과 최종 잔여 후보의 구간별 검토를 작성하고 이 증거를 계획의 `speech`에 반영한다. 후보 감지는 삭제 승인이 아니다. 필요한 컷을 바꿨으면 `prepare-audio`를 새 작업 경로에 다시 실행한다.

`verify_audio`는 실제 계획대로 만든 PCM 일치 확인 후 공통 `validate_audit`를 호출한다. `bind`, `stage`, `install`, `verify`가 모두 이 함수를 호출하므로, 검토 누락이나 음성/컷 변경 후 과거 검수를 재사용하면 저장할 수 없다. 자막 시각·단어 전사 검사만으로 이 단계를 대체하지 않는다.


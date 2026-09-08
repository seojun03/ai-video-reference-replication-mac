# 스타일 선택 및 신규 등록 워크플로우

작업 시작 때 사용자 승인 스타일을 먼저 번호로 선택하고, 다음 단계에서 폰트를 선택한 뒤, 기본 컷 검증 후 선택 스타일을 적용할 때 이 문서를 따른다.

## 내보내기 금지

- 이 워크플로의 `0~8초 샘플`은 별도의 편집 가능한 CapCut 초안을 뜻한다. 렌더 MP4·저화질 preview 파일을 만들지 않는다.
- CapCut 내보내기 창을 열거나 Computer Use로 내보내기 버튼을 누르지 않고, 공유·업로드도 하지 않는다.
- 사용자에게 내보낼지 묻는 단계도 두지 않는다. 샘플 프로젝트 이름과 경로를 알려 사용자가 CapCut 편집기에서 확인하게 한다.
- 내보낸 영상이 필요한 비교 항목은 `not_performed_export_prohibited`로 기록하고, 초안 구조·자원·싱크 검증 결과와 분리한다.

## 1. 단계 상태를 분리하기

다음 상태를 혼용하지 않는다.

- `editing_style_pending`: 작업 시작, 편집 스타일 선택 대기
- `style_selected_font_pending`: 편집 스타일 선택 완료, 폰트 선택 대기
- `interview_complete_base_cut_pending`: 스타일·폰트 선택 완료, 기본 컷 생성 대기
- `base_cut_in_progress`: 선택 폰트로 기본 컷·자막 생성 또는 검증 중
- `base_cut_complete_style_ready`: 기본 컷 검증 완료, 이미 선택한 스타일 적용 대기
- `style_definition_in_progress`: 새 스타일 규칙과 자원을 작성 중
- `style_plan_pending_validation`: 선택 스타일의 `effect_plan.json` 검증 대기
- `style_detail_edit_complete`: 복제본 적용과 기준본 불변 검증 완료

스타일 선택 완료는 스타일 적용 완료가 아니다. 선택만 작업 시작에 먼저 기록하고, 기본 컷이 검증될 때까지 효과·효과음은 적용하지 않는다. 기본 컷 완료도 디테일 편집 완료가 아니며 기준 초안을 그대로 보존한다.

## 2. 동적 메뉴 만들기

작업 시작 첫 질문을 만들기 위해 엔진 루트에서 다음 명령을 실행한다.

```bash
python3 -m capcut_auto.style_registry menu
```

메뉴에는 다음 조건을 모두 만족하는 항목만 포함한다.

- `origin: "user_created"`
- `status: "stable"`
- `menu_enabled: true`
- 실제 레시피 파일 존재

`menu_order` 오름차순으로 정렬하고 현재 표시 순서대로 1부터 번호를 붙인다. `menu_slot`은 스타일 A, B, C처럼 영구 라벨로 사용한다. 새 스타일은 마지막에 다음 미사용 슬롯과 `menu_order`로 추가하고 기존 슬롯이나 순서를 바꾸지 않는다. Z 다음은 AA, AB 순서로 확장한다.

등록된 스타일이 있으면 다음 형식만 사용한다.

```text
어떤 스타일로 편집할까요?
1. 스타일 A — <이름>
2. 스타일 B — <이름>
번호로 선택해 주세요.
```

등록된 스타일이 0개면 다음처럼 묻는다.

```text
현재 등록된 새 편집 스타일이 없습니다. 기존 스타일은 사용하지 않습니다. 스타일 A부터 새로 만들까요?
```

## 3. 새 스타일을 하나씩 등록하기

한 번에 하나만 만든다. 기존 레시피를 새 스타일의 기본값으로 복사하지 않는다.

1. 스타일의 사용 목적과 이름을 확정한다.
2. `hook`, `problem`, `product_reveal`, `benefit`, `proof`, `offer`, `cta` 중 강조할 의미 사건을 정한다.
3. 자막 디자인, 자막 애니메이션, 영상 효과, 전환, 효과음, BGM의 허용 규칙과 금지 규칙을 각각 기록한다.
4. 실제 설치된 CapCut 자원 이름·ID·경로와 사용 가능한 효과음 파일을 검증한다.
5. `effect_plan.json`을 먼저 만들고 효과 밀도, 중복, 겹침, 미설치 자원, 기준본 타이밍 변경을 검사한다.
6. 0~8초 샘플을 기준본 복제본인 편집 가능한 CapCut 초안에 적용해 사용자의 승인을 받는다. MP4로 내보내지 않는다.
7. 승인 전에는 `candidate`, `menu_enabled: false`로 둔다. 승인 후에만 `stable`, `origin: "user_created"`, `menu_enabled: true`, 다음 `menu_slot`과 `menu_order`를 부여한다.

스타일 레시피에는 효과 목록뿐 아니라 다음 금지 규칙을 포함한다.

- 한 의미 구간의 주요 화면 효과 상한
- 효과음 최대 동시 재생 수와 재사용 금지 간격
- 일반 설명 구간에서 효과를 생략하는 조건
- 같은 효과의 연속 반복 금지
- 설치되지 않았거나 selector 복원이 안 되는 CapCut 자원 금지
- 기준본 영상·음성·자막 구간 변경 금지
- 번호형 생성 컷의 계획된 source 이름·해시·순서 변경과 승인 없는 장면 재사용 금지
- 화면 전환·컷 임팩트 효과음은 메인 영상 incoming 컷에 배치하고, 자막·핵심어·그래픽 강조 효과음은 대응 의미 사건에 배치한다. 파일 앞 무음을 첫 가청음까지 물리적으로 제거한 48kHz cut-ready PCM과 `source_start=0`을 사용해 첫 가청음을 선택 앵커와 정확히 같은 프레임으로 저장
- 스타일 A 효과음은 3~4초 구간마다 문맥에 맞는 primary 최소 1개를 두고 `maximum_sfx_free_gap_seconds <= 4.0`을 검증한다. 절대 시간 자동 삽입, 극성 불일치, 겹침, 같은 자산 반복은 금지한다
- 레퍼런스 효과음은 후보 자산과 리듬 근거로 사용하되 새 대본의 의미 극성이 우선이다. 문제·통증·악화·손실에는 부정 계열, 제품 공개·해결·효능·성과·혜택·CTA에는 긍정 계열, 단순 전환에는 중립 계열만 배치한다. 기본 출력은 효과음 1트랙·동시 재생 1개이며, 레퍼런스의 다중 트랙 자체를 복제하지 않는다

## 4. 번호 선택 후 폰트를 고르고 나중에 적용하기

사용자 응답을 다음 명령으로 해석한다.

```bash
python3 -m capcut_auto.style_registry select <번호>
```

반환된 `style_id`, 버전, 레시피 경로를 현재 작업에 고정한다. 번호가 없거나 범위를 벗어나면 다시 메뉴를 보여주고 추측하지 않는다. 서로 다른 스타일을 혼합하지 않는다.

스타일 번호를 고정한 직후 폰트 질문으로 넘어간다. `editing_style_selection.selection_order: 1`, `font_style_selection.selection_order: 2`, `editing_interview.required_order: ["editing_style", "font_style"]`를 기록한다. 폰트를 먼저 선택했거나 스타일과 폰트 중 하나가 누락되면 기본 컷 생성을 중단한다. 스타일 효과를 이 시점에 적용하지는 않는다.

선택한 스타일 레시피에 `reference_bank`가 있으면 다음 동결 은행 절차를 우선한다.

1. 원본 레퍼런스 타임라인을 열거나 재생하거나 다시 전사·프레임 분석하지 않는다.
2. 선택 레시피의 `reference_bank.runtime_guard`를 확인한다. 승인된 `frozen_bank_integrity`이면 `python3 -m capcut_auto.reference_style_bank verify-frozen <bank.json>`으로 동결 snapshot·profile·event graph의 기록 해시만 검사하고 live 원본 draft는 읽지 않는다. 승인 동결 전 레시피만 `verify-sources`로 원본·의미 해시를 검사한다.
3. `verify-frozen`의 `ok`, 또는 `verify-sources`의 `ok`·`ok_metadata_only_drift`일 때만 저장된 profile로 새 기준본을 선택한다. 동결 은행 무결성이 깨지면 `frozen_bank_integrity_failed`, 승인 전 live 원본 의미가 바뀌면 `reference_source_changed_rebuild_required`로 중단한다.
4. `python3 -m capcut_auto.reference_style_bank select <bank.json> <target draft_info.json>` 결과에서 정확히 한 `recipe_id`와 한 `window_id`만 고른다. 동점·낮은 margin이면 임의 선택하거나 레시피를 혼합하지 않는다.
5. 적용 시 원본 레퍼런스가 아니라 은행 안의 frozen snapshot과 event graph만 읽는다. 현재 영상에서는 대본·Whisper 단어·기준본만 분석한다.
6. 선택 레시피의 관찰된 자막 표시 비트, 네이티브 자원 ID·경로, 효과음·BGM과 사건 순서를 의미 앵커에 옮긴다. 기본 영상은 `single_track_compact`로 평탄화하고, 동시 표시가 필수인 PIP·분할 화면만 최소 보조 트랙을 허용한다. 새 대본에 존재하지 않는 레퍼런스 전용 문구 사건은 억지로 넣지 않고 `source_only_text_omitted_in_target`으로 기록한다.
7. 선택된 레시피 외 자원이나 범용 추정 효과를 추가하지 않는다.

사용자가 레퍼런스의 발생 사건을 그대로 복제하는 대신 `편집법만 가져와 새 영상으로`, `반복 효과 없이 맥락에 맞게`, `지금처럼 변주`를 요청하면 `application_mode: "context_varied"`를 선택하고 [문맥 변주 디테일 편집 워크플로우](context-varied-detail-workflow.md)를 전부 읽는다. 이 모드도 정확히 한 레시피만 사용하고 선택 레시피 밖의 자원을 섞지 않지만, 레퍼런스의 효과 발생 순서·횟수를 기계적으로 복사하지는 않는다. 검증된 자원 어휘와 밀도·극성·강조 문법을 현재 대본의 의미 사건에 다시 배정하며, 같은 자원 반복보다 낮은 우선순위 사건의 무효과를 우선한다. 레퍼런스 영상·이미지·자막 material은 새 타임라인에 복제하지 않는다.

`스타일 A`(`ecommerce.clean-basic` 1.1.0 이상)는 번호 선택 자체가 `application_mode: "context_varied"`의 명시적 선택이다. 사용자가 별도로 변주라고 말하지 않아도 이 모드를 적용하고 다시 묻지 않는다. 다만 현재 요청에서 `효과 발생 횟수까지 100% 동일`을 명시하면 그 실행에만 엄격 화이트리스트 모드가 우선한다.

스타일 적용 순서는 다음과 같다.

1. 작업 시작에 고정한 `style_id`·버전과 기본 컷에 기록된 선택 폰트를 다시 검증한다.
2. 승인된 기본 컷 초안을 고유 이름으로 복제한다.
3. 번호형 생성 컷이면 [영상 컷 순서·중복 무결성 워크플로우](shot-sequence-integrity-workflow.md)의 권위 계획과 source 지문을 검증한다.
4. 대본을 의미 사건으로 분류한다.
5. 선택 레시피를 적용해 `effect_plan.json`을 만든다.
6. 충돌, 자원 유효성, 4초 최대 효과음 공백, source assignment 불변을 검사한다.
7. 검증된 계획만 복제본에 적용한다. 기본 자막 정책은 `preserve_selected`로 두어 기준본의 폰트·배경·자막 material을 유지하고 선택 레시피의 네이티브 자막 제어·영상 효과·효과음만 추가한다.
8. 기준본과 메인 영상·음성의 target/source 구간, 본문 자막의 논리 구간·전체 문구·폰트 경로를 비교한다. 스타일 레시피가 선언한 훅 표시 분할은 논리 구간의 합집합과 결합 문구로 검증한다.
9. 메인 컷과 자막 논리 구간 차이가 1ms 이내이고, 선택 폰트가 보존됐으며, 선언되지 않은 표시 분할·계획 밖 소스 대체·중복이 없고 스타일 자원 검증이 통과한 경우에만 `style_detail_edit_complete`로 기록한다.

최종 등록 직전에는 공용 `capcut_auto.style_completion_gate`를 반드시 실행한다. 이 게이트가 저장 초안의 실제 자막 bbox·논리 컷·소스 길이·화면 디테일·효과음 트랙과 간격을 다시 읽어 통과하기 전에는 등록 스타일 표시명을 타임라인 최종 이름에 쓰거나 매니페스트를 `completed`로 바꾸지 않는다. 업체별 일회성 스크립트와 수동 조립 스크립트도 같은 게이트를 우회할 수 없다.

훅의 시각 리듬을 높이기 위해 자막을 나눌 때는 `caption_display_sequence`에 각 표시 문구와 `spoken_keyword_start` 앵커를 먼저 기록한다. 영상 효과는 자막 레이어가 아니라 footage 또는 별도 footage overlay에 적용한다. 효과음의 의미 사건을 먼저 `video_cut_start`와 `semantic_event_start`로 분류한다. 12프레임 이내의 화면 전환·컷 효과음은 메인 영상 incoming 컷에 잠그고, 컷이 없는 자막·핵심어·그래픽 강조음은 해당 의미 사건에 유지한다. 효과음 파일의 앞 무음을 첫 가청음까지 제거한 48kHz cut-ready PCM을 만들고 `source_start = 0`, `SFX target_start = first_audible_onset = selected anchor start`, `saved_event_sync_error_frames = 0`을 CapCut 재저장 후에도 검증한다. 효과음 때문에 기준본 메인 컷을 이동하거나 새로 만들지 않으며, 선택 레퍼런스에서 관찰된 개수·순서·음량·트랙 레이어를 삭제하거나 임의로 늘리지 않는다.

사용자가 직접 편집한 구간을 스타일 피드백으로 주면 기준본과 수동본을 같은 FPS의 프레임 단위로 동결·비교한 뒤 다음 순서로 처리한다.

1. 자막·영상·효과음의 수동 시작 프레임과 종료 프레임을 기록한다.
2. 각 변화에 사용자가 설명한 이유를 `attention_or_urgency`, `audience_pain`, `damage_or_threat`, `hope_or_desired_result`, `neutral_explanation` 중 하나로 연결한다.
3. 전체 자막이 아니라 실제 강조 단어 범위, 색상, 크기, 네이티브 효과 ID·경로, 효과음 첫 가청음 앵커를 기록한다.
4. 수동 보조 트랙은 스타일 규칙으로 복제하지 않고, 최종 출력은 PIP 근거가 없는 한 `single_track_compact` 한 영상 트랙으로 평탄화한다.
5. `semantic_emphasis_plan.json`을 만들어 `scripts/validate_semantic_emphasis_plan.py`로 단일 영상 트랙, 한 줄 자막, 종결 마침표 0개, 의미 극성, 효과 밀도, 효과음 `source_start=0`, 자원 경로를 검사한다.
6. 수동본에 증거가 없는 확대·변형값은 `pending_native_or_transform_validation`으로 차단한다. 하나의 사례에서 관찰된 프레임 차이를 전체 타이밍 오프셋으로 일반화하지 않는다.
7. 피드백은 먼저 `pending`으로 저장하고, 새 고유 복제본에서 사용자가 결과를 승인한 뒤에만 스타일의 안정 규칙으로 승격한다.
8. 단, 사용자가 직접 만든 수동본을 승인 기준이라고 명시하고 그 편집 이유와 함께 `학습`, `저장`, `다음부터 적용`을 요청하면 그 수동본 자체를 승인 결과로 취급할 수 있다. 이 경우 저장 초안에서 실제로 확인된 자원·크롭·앵커와 일반화된 의미 규칙만 승격하고, 한 사례의 절대 프레임·고정 배율을 전역값으로 만들지 않는다.

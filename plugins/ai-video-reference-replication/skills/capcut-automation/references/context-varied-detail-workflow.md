# 문맥 변주 디테일 편집 워크플로우

레퍼런스의 영상·자막을 복사하지 않고, 선택한 한 편집 레시피의 검증된 표현 어휘를 새 대본 문맥에 맞게 다양하게 배치할 때 이 계약을 따른다.

## 1. 적용 모드 확정

- 사용자가 `편집법만 가져와`, `같은 효과를 반복하지 마`, `맥락에 맞게 변주`, `지금처럼 편집`을 요청하면 `application_mode: "context_varied"`를 기록한다.
- 사용자가 등록 메뉴에서 `스타일 A`(`ecommerce.clean-basic` 1.1.0 이상)를 선택하면 같은 요청으로 간주하고 별도 모드 질문 없이 `application_mode: "context_varied"`를 기록한다.
- 사용자가 `효과 100% 동일`, `발생 횟수까지 똑같이`, `임의 추가 금지`를 요청하면 이 모드를 사용하지 않고 엄격 화이트리스트 모드를 적용한다.
- 두 요청이 충돌하면 가장 최근의 구체적인 요청을 우선하고 선택한 모드를 `effect_plan.json`에 명시한다.

## 2. 레퍼런스 은행과 기준본 고정

1. 기본 컷·음성·논리 자막 검증이 끝난 기준본의 해시와 프레임 구조를 고정한다.
2. 동결 은행의 source guard를 검사하고 정확히 한 `recipe_id`와 한 `window_id`만 선택한다. 다른 레시피의 효과·효과음·BGM을 섞지 않는다.
3. source guard가 실패하면 조용히 재학습하지 않는다. 사용자가 `다시 참고해서 학습`을 명시한 경우에만 이전 은행을 보존하고 새 버전으로 전체 레퍼런스를 다시 색인한다.
4. 사용자 수동 편집이 승인된 프레임 구간은 `manual_preserved_ranges`로 기록하고 이후 자동 변주에서 수정하지 않는다.
5. 기준본은 읽기 전용으로 보존하고 고유 이름의 복제본에서만 디테일을 적용한다.
6. 번호형 생성 컷이면 [영상 컷 순서·중복 무결성 워크플로우](shot-sequence-integrity-workflow.md)를 적용한다. 스타일 레시피는 계획된 source assignment를 바꾸지 못한다.

## 3. 콘텐츠와 자원 격리

- 새 타임라인의 영상·이미지 material은 현재 작업의 승인 자산만 사용한다. frozen snapshot의 영상·이미지·합성 클립을 복제하면 `TARGET_LITERAL_VISUAL_ASSET_COPY_DETECTED`로 실패시킨다.
- 자막 `content.text`는 현재 대본 문구만 허용한다. 레퍼런스 자막 문구·가격·혜택이 남으면 `TARGET_LITERAL_COPY_DETECTED`로 실패시킨다.
- 레퍼런스에서는 편집 문법과 검증된 네이티브 효과·애니메이션 패키지, 로컬에서 권리가 확인된 CapCut/사용자 라이브러리 SFX만 가져온다. 렌더 영상에서 추출한 음악·효과음은 재사용하지 않는다.
- 모든 네이티브 자원은 표시 이름·resource ID·절대 경로·필수 파일이 실제로 해결될 때만 사용한다.
- 흐림·블러·모션블러·가우시안·defocus·frosted 계열 자원과 파라미터는 레퍼런스 은행에 있어도 후보 어휘에서 제외한다. 같은 역할은 블러 없는 하드컷, 직접 크롭, 허용 네이티브 애니메이션 또는 무효과로 표현한다.

## 4. 의미 사건별 변주 계획

대본을 `hook`, `problem`, `worsening`, `product_reveal`, `mechanism`, `benefit`, `proof`, `loss_warning`, `result`, `offer`, `cta`로 나눈 뒤 먼저 `effect_plan.json`을 만든다. Style A 효과음은 [Style A 맥락 효과음·화면 반응 워크플로우](style-a-contextual-sfx-workflow.md)를 추가로 읽고 각 사건의 `micro_intent`와 후보 비교를 먼저 확정한다.

- 한 의미 사건에는 주요 화면 표현을 최대 1개만 배치한다.
- 표현 modality를 `hard_cut_or_hold`, `direct_scale_or_crop`, `native_animation`, `native_video_effect`, `word_color_accent`, `audio_only`로 분류한다.
- 인접 사건에 같은 modality를 연속 배치하지 않는다. 의도적인 CTA 2단 확대처럼 계획에 이유가 적힌 progression만 예외다.
- 짧은 한 영상 안에서는 같은 이름의 primary 네이티브 효과·애니메이션과 같은 SFX 파일을 기본적으로 다시 쓰지 않는다. Style A 필수 사건에 적합한 고유 후보가 없으면 사용자 라이브러리 → CapCut 로컬 자원 → 상업 이용이 확인된 외부 자산 순으로 검색하고, 그래도 해결하지 못하면 완료를 막는다. 낮은 우선순위 장식 사건만 이유를 기록하고 무효과로 둘 수 있다.
- 일반 설명은 하드컷·기본 자막 위주로 두고, 문제 악화·제품 최초 공개·수치 근거·손실 경고·결과·오퍼·CTA처럼 설득 기능이 바뀌는 사건만 강조한다.
- 확대·크롭 강도와 지속 프레임은 선택 레시피나 현재 사용자가 승인한 사례에서 근거를 얻는다. 한 테스트의 프레임 번호·배율을 전 영상의 고정값으로 저장하지 않는다.
- 색·효과·SFX를 한 사건에 모두 쌓지 않는다. 예를 들어 오퍼는 강조색과 금액 SFX만 쓰고 화면은 hold로 둘 수 있다.
- 사용자가 승인한 고위험 `damage_or_threat` 사례처럼 네이티브 화면 효과와 크롭 확대가 하나의 핵심어에 동시에 필요한 경우에는 둘을 `compound_visual_punch` 하나로 묶어 primary 1개로 센다. 이 예외는 이유·앵커·두 구성요소를 모두 계획한 사건에만 허용하고 제3의 화면 효과를 더하지 않는다.

다음은 역할 예시이며 고정 효과표가 아니다.

- `worsening` → 부정 극성 화면 효과
- `competitor_short_lived_limit` → 민망함·부정 극성 SFX와 결론 핵심어 크롭 확대
- `continuous_damage_threat` → 경고 화면 효과와 부정 SFX, 피해 결과 핵심어 크롭 확대를 하나의 compound 표현으로 사용 가능
- `symptom_worsening_result` → 충격 계열 SFX와 악화 결론 핵심어 크롭 확대
- `product_reveal` → 짧은 진입 애니메이션과 긍정 reveal SFX
- `proof` → 낮은 배율의 미세 확대 또는 수치 강조음
- `loss_warning` → 앞 사건과 다른 줌·hit 계열
- `result` → 과한 반짝임 대신 표정 집중 확대 또는 긍정 SFX
- `offer` → 화면 hold·강조색·price SFX 중 필요한 조합
- `cta` → 단일 click 또는 이유가 명시된 단계 확대

## 5. 효과음 계약

- 효과음은 의미 극성이 맞는 서로 다른 자산을 우선하고, 한 트랙·동시 재생 1개·겹침 0개를 유지한다.
- 극성만 맞는 generic click·pop으로 밀도를 채우지 않는다. 설득 역할, 미세 의도, 원하는 감정, 물리적 질감, 세기, 실제음·비유음을 기록하고 최소 두 후보의 선택·탈락 이유를 비교한다.
- 컷 임팩트는 `video_cut_start`, 인샷 키워드·수치·그래픽 강조는 `semantic_event_start` 또는 `spoken_keyword_start`에 연결한다.
- MP3/AAC는 앞 무음과 codec pre-roll을 제거한 48kHz PCM WAV로 스테이징하고 모든 저장 `source_timerange.start`를 0으로 만든다.
- 첫 가청음과 선택 앵커의 저장 오차는 정확히 0프레임이어야 한다. 활성 꼬리를 자르거나 다음 효과음과 겹치면 실패시킨다.
- 스타일 A에서는 첫 효과음부터 마지막 핵심 구간까지 효과음이 전혀 없는 간격이 4초를 넘지 않게 한다. 목표 밀도는 3~4초당 문맥 효과음 최소 1개다. 시간표를 먼저 채우지 말고 각 구간의 의미 사건을 먼저 고른 뒤, 사건이 없을 때만 자연스러운 문장·컷 경계의 약한 중립음을 사용한다.
- 더 중요한 의미 사건이 가까이 있어 첫 가청음 간격이 3초보다 짧아질 수는 있지만, 한 트랙·동시 1개·같은 자산 재사용 금지·극성 일치는 그대로 유지한다. 사용할 수 있는 문맥 적합 자산이 없으면 엉뚱한 소리를 넣지 말고 계획 검증을 실패시킨다.

## 6. 적용과 검증

1. `effect_plan.json`에서 단일 레시피, 수동 보존 구간, 사건별 역할·극성·modality·자원·선택 이유를 검사한다.
2. 효과 충돌, 같은 이름 반복, 인접 modality 반복, 미설치 자원, SFX 겹침, 기준본 변경이 있으면 적용 전에 중단한다.
3. 검증된 계획만 기준본 복제본에 적용하고 기본 영상은 `single_track_compact` 한 트랙으로 유지한다.
4. 저장 초안을 다시 읽어 기준본의 음성, 메인 영상 target/source 구간, 논리 자막 문구·구간이 1ms 이내로 동일한지 확인한다.
5. `context_variation_verification.json`에 다음을 기록한다.
   - `selected_recipe_count: 1`, `cross_recipe_asset_count: 0`
   - `reference_literal_visual_count: 0`, `reference_literal_caption_count: 0`
   - `primary_visual_collision_count: 0`
   - `repeated_post_manual_native_visual_count: 0`
   - `repeated_sfx_asset_count: 0`, `sfx_track_count: 1`, `sfx_overlap_count: 0`
   - `maximum_sfx_free_gap_seconds <= 4.0`, `sfx_context_anchor_mismatch_count: 0`
   - `sfx_source_start_nonzero_count: 0`, `saved_event_sync_error_frames: 0`
   - `video_track_count: 1`, `caption_newline_count: 0`, `caption_terminal_period_count: 0`
   - `planned_shot_source_mismatch_count: 0`, `unplanned_shot_duplicate_count: 0`
   - `planned_shot_omission_count: 0`, `shot_order_violation_count: 0`, `style_source_mutation_count: 0`
   - `unresolved_native_resource_count: 0`, `unreferenced_effect_material_count: 0`
   - `forbidden_blur_material_count: 0`, `forbidden_blur_reference_count: 0`, `active_motion_blur_count: 0`
   - `base_timeline_mutation_count: 0`, `export_performed: false`
6. 백그라운드 안전 모드이면 구조 검증 완료와 `pending_foreground_preservation`을 함께 보고하고 UI 재생·청취 완료라고 표현하지 않는다.

위 검증이 모두 통과해야 `style_detail_edit_complete`로 기록한다.

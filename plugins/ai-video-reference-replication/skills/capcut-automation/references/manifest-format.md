# 보이스오버 매니페스트

`project_manifest.json`은 UTF-8 JSON 객체다. 파일이 있는 폴더를 기준으로 영상·음성 폴더를 찾는다.

## 목차

- 예시
- 필드
- 작성 규칙

## 예시

```json
{
  "draft_name": "업체_상품_자동편집_20260725",
  "video_dir": "영상",
  "audio_dir": "음성",
  "product_context": {
    "enabled": true,
    "root": "${VIDEO_PRODUCT_LIBRARY_ROOT}",
    "company": "무위록",
    "product": "정화 차전자피",
    "job_id": "muwirok-20260725-001",
    "style_id": "ecommerce.clean-basic",
    "sync_recent_scripts": true,
    "include_pending_for_current_job": true,
    "snapshot_path": "product_context_snapshot.json"
  },
  "editing_interview": {
    "version": 1,
    "required_order": ["editing_style", "font_style"],
    "completed_steps": ["editing_style", "font_style"],
    "current_step": "complete",
    "status": "complete"
  },
  "editing_style_selection": {
    "interview_completed": true,
    "selection_order": 1,
    "choice": 1,
    "style_id": "ecommerce.clean-basic",
    "display_name": "AI 영상 기본",
    "version": "1.2.0",
    "application_mode": "context_varied",
    "application_timing": "after_base_cut_verification"
  },
  "font_style_selection": {
    "interview_completed": true,
    "selection_order": 2,
    "choice": 1,
    "mode": "basic_pretendard_black",
    "label": "기본",
    "style_id": "ecommerce.clean-basic",
    "preserve_through_style_application": true,
    "analysis": {
      "status": "not_applicable",
      "font_name": "Pretendard SemiBold",
      "font_resource_id": "",
      "foreground_color": "#FFFFFF",
      "background_color": "#000000",
      "background_alpha": 1.0
    }
  },
  "reference": {
    "video": "레퍼런스/reference.mp4",
    "analysis_dir": "../output/reference_analysis",
    "sample_start": 0.0,
    "sample_end": 8.0,
    "approval_required": true
  },
  "reference_style": {
    "editability": {
      "enabled": true,
      "require_hook_text_tracks": true,
      "require_body_text_tracks": true,
      "forbid_common_keyframes": true,
      "minimum_named_video_animations": 0,
      "minimum_named_text_animations": 0,
      "minimum_named_video_effects": 0,
      "require_resolved_resource_paths": true
    },
    "native_resources": {
      "strict": true,
      "animations": [
        {
          "effect_id": "LOCAL_EFFECT_ID",
          "replace_effect_ids": ["PYCAPCUT_PLACEHOLDER_EFFECT_ID"],
          "name": "CapCut에 표시되는 이름",
          "path": "/absolute/path/to/local/effect/package",
          "resource_id": "LOCAL_EFFECT_ID",
          "third_resource_id": "LOCAL_EFFECT_ID",
          "required_files": ["config.json", "content.json", "anim.prefab"]
        }
      ],
      "video_effects": []
    },
    "reference_fidelity": {
      "strict": true,
      "analysis_coverage": {
        "start_frame": 0,
        "end_frame_exclusive": 1005,
        "decoded_frame_count": 1005,
        "analyzed_frame_count": 1005
      },
      "audio_analysis_coverage": {
        "status": "complete",
        "sample_rate": 48000,
        "start_sample": 0,
        "end_sample_exclusive": 1609728,
        "decoded_sample_count": 1609728,
        "analyzed_sample_count": 1609728
      },
      "text_events": [],
      "effect_inventory": {
        "enabled": true,
        "authority": "rendered_reference_mp4_full_frame_analysis",
        "require_reference_event_id": true,
        "allowed_reference_event_ids": [
          "motion-hook-sparkle",
          "motion-hook-radial-hit",
          "motion-hook-left-whip"
        ],
        "expected_counts": {
          "text_animation": 0,
          "video_animation": 0,
          "common_keyframes": 0,
          "clip_effect": 0,
          "timeline_effect": 3,
          "transition": 0,
          "clip_filter": 0,
          "timeline_filter": 0
        },
        "allowed_visual_track_names": ["클린본 영상"],
        "forbid_unreferenced_effect_materials": true,
        "forbid_auxiliary_effect_materials": true,
        "forbid_embedded_keyframes": true,
        "asset_identity_exact": false
      }
    },
    "hook": {
      "render_mode": "text",
      "keyframe_motion": null
    },
    "body": {
      "font_path": "~/Library/Containers/com.lemon.lvoverseas/Data/Library/Fonts/Pretendard-SemiBold.otf",
      "font_resource_id": "",
      "font_name": "Pretendard SemiBold",
      "size": 13.0,
      "bold": true,
      "color": "#FFFFFF",
      "align": 1,
      "transform_x": 0.0,
      "transform_y": -0.20833333333333334,
      "background": {
        "color": "#000000",
        "style": 1,
        "alpha": 1.0,
        "round_radius": 0.0,
        "height": 0.0,
        "width": 0.0,
        "horizontal_offset": 0.5,
        "vertical_offset": 0.5
      },
      "logical_overrides": [
        {
          "logical_caption_index": 4,
          "status": "native_editable_animation",
          "reason": "해결 행동을 촉구하는 강조 문장",
          "style": {
            "animation_in": "PyCapCut enum 이름",
            "animation_in_duration": "0.16s"
          }
        }
      ]
    },
    "video": {
      "section_effects": [
        {
          "section_index": 4,
          "role": "product_reveal",
          "status": "native_editable_animation",
          "intro_animation": {
            "name": "PyCapCut enum 이름",
            "duration": "0.16s"
          }
        }
      ],
      "timeline_effects": []
    }
  },
  "captions": {
    "single_line": true,
    "max_width_px": 930,
    "orphan_min_chars": 2
  },
  "sfx": {
    "library_profile": "default",
    "auto_match": false,
    "default_gain_db": -12.0,
    "minimum_score": 1.6,
    "cooldown_seconds": 0.45,
    "max_per_minute": 10,
    "max_repeats_per_asset": 2,
    "max_auto_asset_duration": 4.0,
    "overlap_padding": 0.015,
    "max_simultaneous": 1,
    "allow_layering": false,
    "trim_to_active_end": true,
    "active_tail_padding_ms": 12,
    "manual_events": [
      {
        "id": "reference-price-pop",
        "type": "price_reveal",
        "anchor": {
          "kind": "spoken_keyword_start",
          "text": "최초 특가",
          "caption_index": 17
        },
        "asset": "효과음 120가지 #03/086_팝.mp3",
        "sync_mode": "manual",
        "sync_point_seconds": 0.18,
        "source_start_seconds": 0.15,
        "max_duration": 0.5,
        "min_post_sync_seconds": 0.08,
        "preserve_active_tail": true,
        "fade_out_ms": 12,
        "gain_db": -8.0,
        "force": true
      }
    ]
  },
  "timing": {
    "trim_silence": true,
    "trim_internal_breath_silence": true,
    "silence_db": -42.0,
    "silence_min_duration": 0.03,
    "head_padding": 0.02,
    "tail_padding": 0.05,
    "internal_breath_gap_threshold": 0.20,
    "retained_internal_breath_gap": 0.10,
    "caption_lead_seconds": 0.0,
    "caption_alignment": "whisper",
    "whisper_model": "small",
    "language": "ko"
  },
  "video_alignment": {
    "mode": "logical_caption",
    "require_whisper_alignment": true,
    "require_semantic_evidence": true,
    "short_source_policy": "leave_gap",
    "max_caption_lead_frames": 0,
    "tolerance_seconds": 0.001
  },
  "audio_segments": [
    {
      "match": "01_hook",
      "trim_start": 0.166,
      "captions": [
        "요즘 날씨 너무 덥죠?",
        "외출 한 시간 만에 화장이 뜬다면"
      ]
    },
    {
      "match": "02_solution",
      "captions": [
        "외출 전 10분만 사용해 보세요!"
      ]
    }
  ],
  "video_assignments": [
    {
      "caption_index": 1,
      "match": "outdoor_heat",
      "source_start": 0.0,
      "semantic_tags": ["heat", "outdoor", "problem"],
      "reason": "더운 날 외출 상황을 보여주는 실제 야외 장면"
    },
    {
      "caption_index": 2,
      "match": "skin_closeup",
      "source_start": 3.5,
      "semantic_tags": ["makeup_failure", "pores", "problem"],
      "reason": "모공과 들뜬 화장을 확인하는 피부 근접 장면"
    },
    {
      "caption_index": 3,
      "match": "product_application",
      "source_start": 1.0,
      "semantic_tags": ["application", "solution"],
      "reason": "제품을 얼굴에 바르는 해결 시연 장면"
    }
  ],
  "notes": [
    "02_solution_take1은 발음 오류로 제외"
  ]
}
```

## 필드

- `draft_name`: 새 CapCut 프로젝트 이름. 기존 이름과 충돌하지 않게 날짜나 버전을 포함한다.
- `extends`: 선택 사항. 현재 매니페스트 기준 상대 경로의 부모 JSON을 불러온 뒤 객체는 재귀 병합하고 배열은 현재 값으로 교체한다. 승인된 컷·음성·자막 구성을 유지한 채 스타일만 새 버전으로 덮어쓸 때 사용한다.
- `video_dir`: 매니페스트 기준 영상 폴더의 상대 경로.
- `audio_dir`: 매니페스트 기준 음성 폴더의 상대 경로.
- `product_context`: 선택 사항. 현재 업체·제품의 원본 자료, 자산 색인, 최근 대본 이력과 승인형 피드백을 초안 생성 전에 연결하고 출력 폴더에 작업별 스냅샷을 고정한다. 자세한 운영 계약은 [제품 컨텍스트와 피드백 누적 워크플로우](product-context-feedback-workflow.md)를 따른다.
- `product_context.enabled`: 기본 `true`. `false`이면 제품 자료를 동기화하거나 스냅샷을 만들지 않는다.
- `product_context.root`: 업체 폴더 루트. 기본 `${VIDEO_PRODUCT_LIBRARY_ROOT}`이며 상대경로이면 매니페스트 폴더 기준으로 해석한다.
- `product_context.company`, `product_context.product`: 실제 폴더명과 정규화 후 정확히 일치해야 한다. 다른 업체나 제품으로 유사 검색·대체하지 않는다.
- `product_context.job_id`: 현재 수정 주기의 고유 ID. 생략하면 `draft_name`을 사용한다. `pending` 피드백은 이 값이 같은 작업에만 적용된다.
- `product_context.style_id`: 선택 사항. 스타일 범위로 승인된 피드백을 불러올 때 현재 선택 스타일 ID를 적는다.
- `product_context.sync_recent_scripts`: 기본 `true`. 새로 생기거나 변경된 최근 대본만 `creative_history.jsonl`에 증분 기록한다. 대본 내용은 제품 사실로 승격하지 않는다.
- `product_context.include_pending_for_current_job`: 기본 `true`. 같은 `job_id`의 수정 중 피드백을 현재 스냅샷에 포함한다. 다른 작업에는 승인된 규칙만 들어간다.
- `product_context.snapshot_path`: 기본 `product_context_snapshot.json`. 상대경로이면 현재 초안 출력 폴더 기준이다.
- `editing_interview`: 필수. `required_order`는 `editing_style`, `font_style` 순서이고 두 단계가 모두 `completed_steps`에 들어가며 `status: "complete"`여야 한다. 순서가 반대거나 단계 기록이 없으면 `EDITING_INTERVIEW_ORDER_INVALID` 또는 `EDITING_INTERVIEW_ORDER_REQUIRED`다.
- `editing_style_selection`: 필수. 작업 시작 첫 단계에서 고른 사용자 승인 편집 스타일이다. `selection_order: 1`, 현재 레지스트리의 `style_id`·버전, `application_timing: "after_base_cut_verification"`를 기록한다. 선택은 폰트보다 먼저 하지만 효과·효과음의 실제 적용은 기본 컷 검증 뒤에 한다.
- `font_style_selection`: 필수. 편집 스타일 선택 다음 단계에서 사용자에게 1번 기본 또는 2번 레퍼런스 폰트를 물은 결과다. `selection_order: 2`, `preserve_through_style_application: true`, 선택한 `style_id`를 기록한다. 누락하거나 `interview_completed`가 `true`가 아니면 `FONT_STYLE_INTERVIEW_REQUIRED`다.
- `font_style_selection.choice`, `mode`: `1`/`basic_pretendard_black` 또는 `2`/`reference_font_match` 조합만 허용한다.
- 1번은 본문 자막을 `Pretendard SemiBold`, 흰색, 불투명 검은 배경으로 유지한다. `reference_style.body`가 이 계약을 덮어쓰면 `FONT_STYLE_BASIC_MISMATCH`다.
- 2번은 실제 `reference.video`가 필요하다. `analysis.required_skill`은 `korean-vibe-fonts`, `analysis.status`는 `verified_exact` 또는 `fallback_nearest_verified_local`이어야 한다. `pending_reference_analysis` 상태에서는 초안을 만들지 않는다.
- 2번의 `analysis.font_name`·`analysis.font_path`는 `reference_style.body`와 정확히 같아야 한다. `font_path`는 현재 Mac에 존재하는 로컬 파일이어야 한다.
- `verified_exact`은 원본 CapCut 초안 또는 동일 자원 근거가 있을 때만 사용한다. `fallback_nearest_verified_local`은 `korean-vibe-fonts` 카탈로그의 `catalog_font_id`와 `commercial_use_status: "catalog_verified"`를 기록한다. 카탈로그 밖 정확 폰트는 사용자가 권리를 확인한 경우에만 `commercial_use_status: "user_rights_confirmed"`로 적용한다.
- 선택 스타일을 기본 컷 뒤에 적용할 때 기본 자막 정책은 `preserve_selected`다. 기준본의 폰트·배경·자막 material을 유지하면서 선택 레시피의 자막 네이티브 제어·영상 효과·효과음만 추가한다. 적용 보고서의 `selected_caption_style_preserved`가 `true`여야 한다.
- `reference.video`: 선택 사항. 이번 작업에서 새로 분석할 레퍼런스 영상 경로.
- `reference.analysis_dir`: 이번 레퍼런스의 `style_profile.json`, 프레임, 오디오 분석 결과를 저장할 폴더.
- `reference.sample_start`, `reference.sample_end`: 본편 전에 제작·검수할 스타일 샘플 구간. 기본은 `0.0`~`8.0초`.
- `reference.approval_required`: 사용자가 샘플을 직접 검토하겠다고 한 작업은 `true`다. 사용자가 `전체본`, `다 만들어`, `계속 진행`, `이대로 진행`처럼 본편 생성을 이미 명시·승인한 백그라운드 실행은 `false`로 둘 수 있다. 이 경우에도 0~8초 내부 검수 게이트는 생략하지 않고, 통과하면 같은 실행에서 전체 초안까지 확장한다.
- `reference_style.editability.enabled`: 사용자가 CapCut에서 글씨체·문구·애니메이션·편집 효과를 직접 수정할 결과를 원하면 `true`다.
- `reference_style.editability.require_hook_text_tracks`, `require_body_text_tracks`: 훅/본문이 합성 PNG가 아니라 실제 텍스트 트랙으로 저장됐는지 강제한다.
- `reference_style.editability.forbid_common_keyframes`: 편집 가능 모드의 기본값은 `true`다. 저장된 모든 세그먼트의 `common_keyframes` 그룹 수가 0이어야 한다.
- `reference_style.editability.minimum_named_*`: 기본값은 `0` 또는 생략이다. 사건 그래프에서 `mode != none`으로 확인된 실제 기대 사건 수가 있을 때만 그 고유 named control 수로 동적 설정한다. 레퍼런스가 전부 컷온 `none`이면 animation object 0개와 CapCut 목록의 `없음`이 정확한 성공 상태다. 이 수치는 보조 리소스 건강 검사일 뿐 충실도는 `reference_style.reference_fidelity.text_events`의 사건별 signature로 검증한다.
- `reference_style.reference_fidelity.strict`: 전체 프레임 사건 매핑을 강제한다. `true`이면 분석 coverage·text event mapping·signature·사건 순서·anchor가 모두 완전해야 한다.
- `reference_style.reference_fidelity.analysis_coverage`: `start_frame`, `end_frame_exclusive`, `decoded_frame_count`, `analyzed_frame_count`를 기록한다. 전체 레퍼런스가 아니면 본편 근거로 사용할 수 없다.
- `reference_style.reference_fidelity.audio_analysis_coverage`: 오디오가 있으면 `status: complete`, `sample_rate`, `start_sample: 0`, `end_sample_exclusive`, `decoded_sample_count`, `analyzed_sample_count`를 기록하고 끝 세 값이 같아야 한다. 불완전하면 `REFERENCE_FULL_AUDIO_SAMPLE_COVERAGE_INCOMPLETE`다. 무오디오 파일은 probe 근거와 함께 `status: not_applicable`을 명시한다.
- `reference_style.reference_fidelity.text_events[]`: 저장 **표시 자막**별 `caption_index`, `reference_event_id`, `animation_signature`를 기록한다. signature의 `mode`는 `none|in|out|loop|combo`이며 이름/resource ID/path/offset frame/duration frame을 근거에 따라 포함한다. 레퍼런스가 컷온이면 `mode: "none"`을 명시한다.
- `reference_style.reference_fidelity.effect_inventory.enabled`: 레퍼런스 효과를 닫힌 화이트리스트로 검증한다. 사용자가 임의 효과 추가를 금지하면 `true`가 필수다.
- `reference_style.reference_fidelity.effect_inventory.allowed_reference_event_ids`: 생성 가능한 모든 효과 발생 사건의 고유 ID다. 같은 효과가 두 번 나타나면 ID도 두 개이며, 이 배열 밖의 사건은 생성하면 안 된다.
- `reference_style.reference_fidelity.effect_inventory.expected_counts`: `text_animation`, `video_animation`, `common_keyframes`, `clip_effect`, `timeline_effect`, `transition`, `clip_filter`, `timeline_filter`의 정확한 저장 개수다. 관찰되지 않은 범주도 반드시 `0`을 적는다.
- `reference_style.reference_fidelity.effect_inventory.allowed_visual_track_names`: 계획에 포함된 시각 트랙 이름이다. 이름만 허용하는 것으로 끝내지 말고 저장 세그먼트의 발생 수·구간·material까지 별도 사건 계획과 1대1 비교한다.
- `reference_style.reference_fidelity.effect_inventory.expected_visual_track_segment_counts`: 허용 시각 트랙별 정확한 segment 수다. 같은 이름의 중복 트랙이나 허용 트랙 안의 추가 segment도 실패시키기 위해 적는다.
- `reference_style.reference_fidelity.effect_inventory.forbid_unreferenced_effect_materials`: 저장됐지만 어떤 세그먼트에서도 참조되지 않은 effect material을 실패시킨다.
- `reference_style.reference_fidelity.effect_inventory.forbid_auxiliary_effect_materials`: 계획하지 않은 animation/transition/filter/keyframe 보조 material을 실패시킨다.
- `reference_style.reference_fidelity.effect_inventory.forbid_embedded_keyframes`: segment·material·top-level·graph list의 숨은 keyframe을 모두 실패시킨다.
- `reference_style.reference_fidelity.effect_inventory.asset_identity_exact`: 원본 CapCut 초안에서 동일 ID·path·parameter까지 확인한 경우만 `true`다. 렌더 MP4 기반 nearest local package는 반드시 `false`다.
- `reference_style.reference_fidelity.effect_inventory.allowed_composite_reference_event_ids`: PIP·split·before/after처럼 독립 editable layer로 구현할 수 있는 합성 사건 ID의 닫힌 목록이다.
- `reference_style.reference_fidelity.effect_inventory.expected_composite_layout_count`, `expected_composite_component_count`: 저장 초안에서 정확히 존재해야 하는 합성 사건 수와 component segment 수다. 하나라도 추가·누락되면 엄격 화이트리스트를 실패시킨다.
- 엄격 화이트리스트의 각 `video.timeline_effects[]`, `section_effects[]`, 자막/영상 animation 계획에는 `reference_event_id`, 원본 start/peak/end frame, target semantic anchor, 컷 대비 상대 frame offset, target duration frame을 기록한다. 가시 envelope와 강한 core가 다르면 두 범위를 모두 기록한다.
- `reference_style.editability.require_resolved_resource_paths`: 모든 사용 리소스의 실제 로컬 경로와 패키지 파일을 요구한다.
- `reference_style.native_resources.strict`: 등록했지만 실제 초안에서 사용되지 않은 리소스도 오류로 처리한다.
- `reference_style.native_resources.animations`, `video_effects`: CapCut 로컬 표시 이름, ID, 절대 `path`, resource/category/panel/source/third-resource 메타데이터, `required_files`를 기록한다. PyCapCut 저장 뒤 이 값으로 실제 material 객체를 패치하고 다시 검증한다.
- `reference_style.native_resources.animations[].replace_effect_ids`: 선택 사항. PyCapCut enum이 생성한 placeholder 애니메이션 ID를 현재 CapCut UI에서 확인한 canonical `effect_id`로 교체할 때 사용한다. 저장 객체의 `id/resource_id/third_resource_id/name/path/category/panel`을 모두 canonical 자원으로 바꾸고 `native_resource_patch_report.json`의 `matched_source_ids`·`replacement_count`가 의도한 수와 일치해야 한다. 한 source ID를 여러 자원에 중복 등록하면 실패한다.
- `reference_style.hook.render_mode`: 편집 가능 모드는 `text`다. 장식용 그래픽은 별도 오버레이로 만들 수 있지만 카피를 PNG에 합성하지 않는다.
- `reference_style.body`: 레퍼런스나 사용자별 덮어쓰기가 없을 때 기본 본문 프리셋은 Pretendard SemiBold, 크기 13, 흰색 중앙 정렬, 1080×1920 기준 X=0/Y=-400이다. 이 위치는 `transform_x: 0.0`, `transform_y: -0.20833333333333334`로 저장한다. 검은 배경은 불투명도 100%, 둥근 직사각형·높이·너비 0%, UI X/Y 오프셋 50%다. PyCapCut에는 offset `0.5`를 입력하며 초안 JSON의 중립값 `0.0`으로 저장되는 것이 정상이다.
- `reference_style.body.font_path`: 로컬 시스템 Pretendard SemiBold의 실제 절대경로를 사용한다. `font_resource_id`는 빈 문자열로 두며 임의 ID를 만들지 않는다. 생성 전 파일 존재와 PostScript/family 이름을 확인하고 포그라운드 검수가 허용되면 CapCut UI에서 `Pretendard SemiBold` 선택 상태를 smoke-test한다.
- `reference_style.body.logical_overrides`: 선택한 원본 논리 자막에 본문 스타일을 덮어쓴다. `logical_caption_index`는 `audio_segments[].captions[]` 전체를 1부터 센 번호다. 입장 애니메이션은 레퍼런스 사건이 해당 논리 자막의 모든 표시 조각에 같은 동작을 쓴다는 프레임 근거가 있을 때만 이 필드로 일괄 적용한다. 그렇지 않으면 표시 자막별 `reference_fidelity.text_events[]`로 지정하며 자동 복제를 금지한다.
- `reference_style.body.logical_overrides[].status`: `verified_exact`, `verified_visual`, `fallback_nearest_capcut_effect`, `fallback_user_requested`, `fallback_user_requested_reference_derived`, `unknown` 중 근거에 맞는 상태를 기록한다. 레퍼런스가 컷온인데 사용자가 움직임을 추가한 경우 `fallback_user_requested`, 레퍼런스의 동작 문법을 더 강하게 반복한 훅은 `fallback_user_requested_reference_derived`다.
- `reference_style.body.logical_overrides[].style.animation_in`: 편집 가능 모드의 권장 입장 애니메이션. 현재 Mac에서 animation object의 표시 이름, `path`, 내부 패키지가 검증돼야 한다. PyCapCut enum 이름이나 resource ID만 존재하고 저장 결과의 `path`가 비어 있으면 사용 금지다.
- `reference_style.body.logical_overrides[].style.keyframe_motion`: 사용자가 커스텀 키프레임을 명시적으로 승인하고 `forbid_common_keyframes: false`로 둔 비편집 우선 작업만 사용한다.
- `reference_style.hook.keyframe_motion`: 로컬 PNG 훅 오버레이의 리소스 없는 모션이다. 편집 가능 모드에서는 금지하며 훅 카피는 `render_mode: text`와 이름 있는 text animation으로 만든다.
- `reference_style.video.section_effects`: `logical_caption` 영상 섹션 번호별 강조 설정. 한 섹션당 항목 하나만 허용하며 `role`, `status`, 근거를 함께 기록한다.
- `reference_style.video.section_effects[].scale_keyframes`: 섹션 내부 영상 확대 키프레임. 각 점은 `offset_seconds` 또는 `time_ratio` 중 하나와 `scale`을 가지며 0초부터 섹션 끝 사이에서 시간 순서로 배치한다.
- `reference_style.video.section_effects[].keyframe_motion`: 사용자가 커스텀 키프레임을 명시적으로 승인한 비편집 우선 작업만 사용한다. 편집 가능 모드에서는 금지한다.
- `reference_style.video.section_effects[].intro_animation`: 편집 가능 모드의 권장 영상 입장 애니메이션. 실제 PyCapCut enum 이름과 지속 시간을 기록하고 `native_resources`의 CapCut 표시 이름·ID·경로로 저장 객체를 완성한다. 지속 시간이 영상 섹션보다 길면 오류다.
- `reference_style.video.section_effects[].clip_effects`: 해당 영상 컷 전체에 적용할 CapCut 장면 효과 배열. 각 항목은 `name`, 선택 `params`를 가진다. MP4에서 원본 effect ID를 확인하지 못했다면 상태를 `fallback_nearest_capcut_effect`로 두며, 저장 전후 실제 로컬 effect `path`와 패키지가 확인되지 않으면 사용하지 않는다.
- `reference_style.video.section_effects[].transition_after`: 선택 사항. 해당 섹션 뒤 전환 이름과 지속 시간. 영상·음성·자막 경계를 바꾸지 않고 저장 구간 안에서만 적용한다.
- `reference_style.video.timeline_effects`: 특정 짧은 구간에 적용할 이름 있는 effect-track 효과. `id`, `lane`, `effect`, `anchor`, `duration_seconds`, 선택 `offset_seconds`, `params`, `status`, `reference_evidence`를 기록한다. 편집 가능 모드에서 로컬 `path`를 검증할 수 없으면 키프레임으로 대체하지 않고 다른 설치 효과를 선택하거나 실패시킨다.
- `reference_style.video.timeline_effects[].anchor.kind`: `timeline_start/end`, `hook_start/end`, `cta_start/end`, `section_start/end`를 지원한다. 섹션 앵커에는 1-based `section_index`가 필요하다. 절대 초 대신 새 음성의 같은 의미 위치에 효과를 옮길 때 사용한다.
- `reference_style.video.timeline_effects[].lane`: 1 이상의 정수다. 같은 lane의 효과 구간은 겹칠 수 없으며, 훅 전체 반짝이 같은 지속 효과와 짧은 히트·블러는 서로 다른 lane을 쓴다.
- `reference_style.video.composite_layouts[]`: 관찰된 PIP·split·before/after를 편집 가능한 영상 트랙으로 재구성한다. 각 항목은 `id`, `reference_event_id`, `anchor`, `duration_frames_at_30fps`, `components[]`를 가진다. 레퍼런스가 하드컷이면 duration은 초가 아니라 관찰 프레임 수로 고정한다.
- `reference_style.video.composite_layouts[].components[]`: `id`, `track_name`, `z_index`, `source_assignment_index` 또는 `solid_rgba`, 선택 `source_start_seconds`·`source_offset_seconds`, `crop`, `clip`, `viewport_bbox_px`를 기록한다. `crop`은 0~1의 left/top/right/bottom, `clip`은 alpha·flip·rotation·scale_x/y·transform_x/y다. 화면 조각마다 독립 segment를 만들며 애니메이션·전환·키프레임으로 합성을 흉내 내지 않는다.
- 합성 화면을 쓴 프로젝트는 `composite_layout_verification.json`을 출력한다. expected/saved component 수, 트랙별 segment 수, 사건별 component 수, target/source timerange, crop·clip·render order가 일치하고 `all_components_cut_on_off: true`, `objective_composite_pass: true`여야 완료한다.
- 스타일 효과를 요청한 프로젝트는 `motion_effect_verification.json`을 출력한다. 요청한 자막 애니메이션·common keyframes·클립 효과·타임라인 효과의 수, property, 값, resource ID, target 구간을 저장 초안에서 다시 읽어 모두 일치해야 통과한다.
- 레퍼런스 기반 프로젝트는 `reference_animation_verification.json`을 출력한다. 모든 저장 표시 자막의 `reference_event_id`, 예상/saved signature, mapping coverage, signature histogram을 기록하고 coverage·일치율 100%여야 한다. 레퍼런스가 여러 signature인데 저장 histogram이 하나로 축소되면 실패한다.
- 엄격 화이트리스트 프로젝트는 `reference_effect_inventory_verification.json`을 출력한다. `effect_event_recall: 1.0`, `unplanned_effect_count: 0`, 빈 `missing_effects`·`unexpected_effects`, 모든 종류의 expected/saved Counter 일치, `strict_effect_inventory_pass: true`를 동시에 요구한다.
- `reference_style.reference_fidelity.effect_inventory.unresolved_reference_events`: 전체 레퍼런스에서 관찰했지만 원본 source range·crop·mask·editable layer stack을 확정하지 못한 사건 배열이다. 각 항목에 `reference_event_id`, `kind`, `reason`을 기록한다. 엄격 모드에서 비어 있지 않으면 `REFERENCE_EVENT_SCOPE_INCOMPLETE`, `strict_reference_fidelity_pass: false`, `strict_effect_inventory_pass: false`이며, 구현된 subset만 `strict_motion_scope_pass: true`일 수 있다.
- `resource_compatibility_verification.json`은 활성 `material_animations`, `video_effects`, `transitions` 중 빈 경로·존재하지 않는 로컬 경로를 나열한다. 세 미해결 배열이 모두 비고 `resource_compatibility_pass: true`일 때만 완료한다. 리소스 없는 `common_keyframes`는 이 배열을 만들지 않아야 한다.
- `native_resource_patch_report.json`: 등록한 애니메이션·화면 효과가 저장 객체에 몇 번 사용됐는지, 경로와 필수 패키지 파일이 모두 존재하는지 기록한다.
- `editable_controls_verification.json`: 훅/본문 실제 텍스트 수, 이름 있는 영상·텍스트 애니메이션과 화면 효과 수, 전체 `common_keyframes` 그룹 수를 저장 초안에서 다시 계산한다. 편집 가능 모드는 `editable_controls_pass: true`여야 완료한다.
- `captions.single_line`: 본문 자막의 실제 렌더 결과를 정확히 한 줄로 제한할지 여부. 기본 `true`다. 본문 자막 문자열의 `\n`도 금지한다. 훅·CTA에서 별도 그래픽 레이어로 만든 의도적 다중행 카피에는 적용하지 않는다.
- `captions.max_width_px`: 본문 자막이 들어갈 수 있는 최대 렌더 폭. 실제 폰트·크기·외곽선·그림자를 포함한 bbox 기준 픽셀값이며, 출력 해상도에 맞춰 지정한다. 초과 문장은 자동 줄바꿈하지 않고 Whisper 단어 경계에서 시간 순서 자막으로 분할한다.
- `captions.orphan_min_chars`: 분할 뒤 각 본문 자막 조각에 필요한 최소 표시 문자 수. 공백과 구두점을 제외해 계산하며 기본 `2`다. 끝에 한 음절만 남으면 인접 단어 묶음을 재분배한다.
- `sfx.directory`: 선택 사항. 사용자가 지정한 효과음 라이브러리 폴더. 하위 폴더 분류를 보존한다.
- `sfx.library_profile`: `config/capcut_preferences.json`에 저장된 재사용 효과음 폴더 이름. 작업별 `directory`·`library_dir`·`path`가 있으면 해당 경로가 우선한다.
- `sfx.auto_match`: 자막·컷·텍스트 이벤트에 의미 태그로 후보를 고를지 여부.
- `sfx.default_gain_db`: 별도 규칙이 없는 효과음의 초기 gain. 최종 clipping·가독성 검수로 조정한다.
- `sfx.minimum_score`: 기준 미만 후보를 억지로 배치하지 않기 위한 최소 일치 점수.
- `sfx.cooldown_seconds`: 서로 다른 자동 이벤트의 과밀 배치를 막는 최소 간격.
- `sfx.max_per_minute`: 자동 이벤트의 분당 최대 개수.
- `sfx.max_repeats_per_asset`: 동일 파일의 자동 재사용 상한.
- `sfx.max_auto_asset_duration`: 자동 후보로 허용할 효과음의 최대 전체 길이. 기본 `4.0초`이며 BGM 태그 파일은 길이와 무관하게 자동 후보에서 제외한다.
- `sfx.overlap_padding`: 같은 자동 lane의 세그먼트 사이에 확보할 최소 간격.
- `sfx.max_simultaneous`: 모든 효과음 세그먼트의 타임라인 최대 동시성. 기본 `1`이며 저장된 초안의 전체 `target_timerange`를 기준으로 검증한다.
- `sfx.allow_layering`: 같은 이벤트나 같은 순간에 효과음 레이어를 둘 이상 허용할지 여부. 기본 `false`다. 사용자가 레이어링을 명시적으로 요청한 경우에만 `true`로 바꾸며, 이때도 `max_simultaneous` 상한을 지킨다.
- `sfx.trim_to_active_end`: `true`이면 긴 무음 파일 꼬리를 그대로 배치하지 않고, sync point 뒤 최소 보존 구간과 `active_end` 중 늦은 지점까지 보존한 뒤 padding·fade만 남긴다. 기본 `true`다.
- `sfx.active_tail_padding_ms`: `trim_to_active_end: true`일 때 `active_end` 뒤에 남길 비활성 안전 여유. 기본 `12ms`이며 fade가 있으면 이 구간 안에 둔다.
- `sfx.manual_events`: 레퍼런스 파형 대조 등으로 파일과 의미 이벤트를 확정했을 때 쓰는 고정 이벤트. 중복 파일명이 많으므로 basename이 아니라 라이브러리 기준 정확한 상대경로를 `asset`에 넣는다. `auto_match: false`면 이 이벤트만 배치한다.
- 효과음 스테이징 형식은 현재 엔진에서 시작 PTS 0의 48kHz stereo PCM WAV로 고정된다. 매니페스트 옵션이 아니며 원본은 바꾸지 않는다.
- 출력 이름은 현재 엔진에서 `sfx_index.json`, `sfx_selection_report.json`, `sfx_sync_verification.json`으로 고정되며 기존 호환용 snapshot·placement 보고서도 함께 쓴다.
- `sfx.manual_events[].anchor`: 절대 `time`보다 권장하는 의미 시각 지정. `kind`는 `timeline_start/end`, `hook_start/end`, `cta_start/end`, `caption_start/end`, `caption_keyword`, `word_start/end`, `word_keyword`, `spoken_keyword_start/end`, `video_cut_start`를 지원한다.
- `spoken_keyword_start`, `spoken_keyword_end`: 대본과 Whisper 단어를 문자 편집거리로 정렬해 실제 발화 시작·종료를 찾는다. `caption_index`로 범위를 좁힐 수 있으며 기준 미달이면 실패한다.
- `asr_fallback_text`: `spoken_keyword_start/end`의 대본↔Whisper 정렬이 기준 미달일 때만 허용하는 명시적 실제 인식어다. Whisper 결과 안에서 정확히 한 번만 일치해야 하며, 원래 `keyword`와 다른 이유를 분석 보고서에 남긴다. 이를 생략한 저신뢰 앵커는 자막 시작이나 근사 시각으로 대체하지 않고 실패한다.
- `caption_keyword`: 해당 문구를 포함한 자막 세그먼트의 시각적 시작이다. 실제 발화 단어 싱크 용도로 사용하지 않는다.
- `sync_mode`: `auto`, `start`, `onset`, `attack`, `peak`, `active_end`, `manual` 중 하나다. `manual`이면 `sync_point_seconds`가 필수다.
- `match_status`: 레퍼런스 자산 판정의 정규 상태다. 허용값은 `verified_exact`, `candidate`, `unknown`이며 파형 검증 기준을 통과하지 않은 자산을 `verified_exact`으로 표시하지 않는다.
- `match_label`: `candidate` 안에서 `near_or_layered`, `semantic_best`, `exact_high_hypothesis`처럼 조사 맥락을 남기는 비정규 설명 필드다. 완료 판정에는 사용하지 않는다.
- `match_confidence`: 재현 가능한 대조 보고서의 정규화 점수다. 강제 배치 우선순위 점수와 혼동하지 않는다.
- `sync_point_seconds`: 원본 효과음에서 이벤트와 맞출 지각상 기준점의 초다.
- `source_start_seconds`: 사용할 정확한 source 시작점이다.
- `pre_roll_seconds`: sync point 앞에 보존할 길이다. `source_start_seconds`와 동시에 지정할 수 없다.
- `max_duration`: 계산된 source 시작점부터의 총 최대 길이다. 파일 0초부터의 길이가 아니다.
- `min_post_sync_seconds`: sync point 뒤에 반드시 남길 최소 길이. 수동 이벤트 기본값은 `0.08초`.
- `preserve_active_tail`: `true`면 `active_end` 이전 절단을 오류로 처리한다. 수동·강제 이벤트 기본값은 `true`.
- `fade_out_ms`: 요청 기본값 `12ms`. 실제 fade는 active end 뒤 비활성 꼬리보다 길지 않게 자동 축소한다.
- `sfx.manual_events[].time`: 하위 호환용 절대 초. 대본이나 음성 길이가 달라질 수 있는 레퍼런스 기반 작업에서는 사용하지 않는다.
- `sfx.manual_events[].offset_seconds`, `offset_frames`: 해석된 앵커 시각에 더하는 미세 보정. 효과음 자체의 유효 onset 보정은 배치 엔진이 별도로 적용한다.
- 앵커가 미해결되거나 `caption_keyword`가 둘 이상의 자막에 걸리면 임의의 첫 항목을 선택하지 않고 오류로 중단한다.
- `timing.trim_silence`: 각 음성 파일의 앞뒤 무음을 잘라 타임라인을 빈틈없이 붙인다.
- `timing.trim_internal_breath_silence`: TTS 단어 사이의 호흡 무음을 source splice PCM으로 축소한다. 기본 `true`이며 `trim_silence`의 앞뒤 트림과 별도 단계다.
- `timing.silence_db`: 무음 판단 기준. 기본 `-42.0dB`.
- `timing.silence_min_duration`: 제거 후보가 되는 최소 연속 무음. 기본 `0.03초`.
- `timing.head_padding`: 첫소리 앞에 남기는 안전 여유. 기본 `0.02초`.
- `timing.tail_padding`: 마지막 소리 뒤에 남기는 안전 여유. 기본 `0.05초`.
- `timing.internal_breath_gap_threshold`: Whisper 단어 사이 공백을 내부 호흡 편집 후보로 보는 최소 길이. 기본 `0.20초`.
- `timing.retained_internal_breath_gap`: 후보 공백에서 최종 PCM에 남기는 총 호흡 길이. 기본 `0.10초`. 발화 샘플 속도와 음높이는 바꾸지 않는다.
- `timing.caption_lead_seconds`: 엄격 싱크 기본값은 `0.0`이다. 저장 자막이 실제 첫 소리·첫 단어보다 먼저 시작할 수 있는 허용량이 아니며 양수 설정을 금지한다.
- `timing.caption_alignment`: `whisper`이면 대본 문장을 실제 단어 타임스탬프에 정렬하고, `proportional`이면 글자 수 비례로 배치한다. 기본값과 권장값은 `whisper`.
- `timing.whisper_model`: 발화 경계 분석 모델. 기본 `small`.
- `timing.language`: 음성 언어 코드. 한국어는 `ko`.
- `audio_segments`: 재생 순서대로 정렬한 음성 및 자막 배열.
- `audio_segments[].match`: 음성 파일명에 포함된 고유 문자열. 정확히 한 파일과 일치해야 한다.
- `audio_segments[].trim_start`: 선택 사항. 사용자가 CapCut 재생헤드로 지정한 정확한 원본 시작 시각(초). 있으면 자동 감지값보다 우선한다.
- `audio_segments[].trim_end`: 선택 사항. 정확한 원본 종료 시각(초). 있으면 자동 감지값보다 우선한다.
- `audio_segments[].captions`: 해당 음성에서 실제로 발화한 문장/의미 단위 자막. 순서를 보존하며 원본 항목 하나가 `logical_caption` 영상 정렬의 의미 섹션 하나가 된다. 한 줄 폭 때문에 표시 자막이 여러 개로 나뉘어도 원본 의미 섹션 번호는 바뀌지 않는다.
- `video_alignment.mode`: 기본·권장값은 `logical_caption`. Whisper로 확정한 원본 대본 섹션의 시작·종료를 대응 영상 `target_timerange`로 그대로 사용한다. 하위 호환 `reference_rhythm`은 `video_sequence`와 전역 컷 리듬을 사용할 때만 선택한다.
- `video_alignment.require_whisper_alignment`: `true`이면 Whisper 단어 타임스탬프가 없을 때 비례 타이밍으로 대체하지 않고 생성에 실패한다. `logical_caption` 기본값은 `true`다.
- `video_alignment.require_semantic_evidence`: `true`이면 모든 `video_assignments`에 비어 있지 않은 `semantic_tags`와 `reason`이 필요하다. 기본값은 `true`다.
- `video_alignment.short_source_policy`: `fail` 또는 `leave_gap`. 이 사용자의 기본 제작값은 `leave_gap`이다. 배정 클린본이 논리 섹션보다 짧으면 원본을 `source_start`부터 실제 남은 길이까지만 원속 배치하고 섹션의 나머지 꼬리는 의도적 빈 화면으로 둔다. 루프·정지·속도 변경·대체 소스는 금지한다. `fail`이면 `CLEAN_SOURCE_DURATION_INSUFFICIENT`로 중단한다.
- `video_alignment.tolerance_seconds`: 저장된 영상·음성·자막 구간을 다시 읽어 비교할 허용 오차. 기본 `0.001초`다.
- `video_alignment.max_caption_lead_frames`: 엄격 싱크 기본값은 `0`이다. 1ms 타이밍 허용 오차와 별개로 자막 선행은 한 프레임도 허용하지 않는다.
- `video_assignments`: 원본 `audio_segments[].captions[]` 전체 항목과 정확히 1대1인 영상 할당 배열. `caption_index` 1부터 대본 순서대로 누락·중복 없이 정렬한다.
- `video_assignments[].caption_index`: 전체 원본 대본 의미 섹션의 1-based 번호.
- `video_assignments[].match`: `video_dir` 안의 정확히 한 영상 파일에만 대응하는 고유 파일명 조각. 파일 정렬 인덱스보다 안정적이다.
- `video_assignments[].source_start`: 해당 영상에서 사용할 시작 시각(초). 실제 프레임을 확인해 의미 행동이 전체 음성 섹션 길이 동안 유지되는 구간을 고른다.
- `video_assignments[].semantic_tags`: 화면이 담당하는 대본 역할과 객체·행동 태그. 예: `problem`, `makeup_failure`, `application`, `before_after`, `price`, `cta`.
- `video_assignments[].reason`: 해당 영상과 시작점이 현재 대본 섹션에 맞는다는 사람이 확인 가능한 근거. 파일명만 근거로 쓰지 않는다.
- `video_sequence`: 하위 호환 `reference_rhythm` 모드에서만 사용하는 영상 폴더 파일명 정렬 기준 1-based 인덱스 배열. `video_assignments`와 동시에 지정할 수 없다.
- `notes`: 중복 생성본, 빠진 대본, 선택 이유 등 검수자가 알아야 할 정보.

## 작성 규칙

1. 편집 스타일을 먼저 선택하고 `editing_style_selection.selection_order: 1`로 기록한다.
2. 다음 단계에서 폰트를 선택하고 `font_style_selection.selection_order: 2`로 기록한다.
3. 음성 파일을 실제로 듣거나 Whisper로 전사한다.
4. 대본과 전사를 대조한다.
3. 중복 후보 중 사용할 파일을 선택한다.
4. 발화되지 않은 문장을 자막에 넣지 않는다.
5. 긴 문장은 화면에서 읽기 좋은 의미 단위로 나누되 단어를 바꾸지 않는다.
6. `inspect`가 오류 없이 통과한 뒤 프로젝트를 생성한다.
7. `project_report.json`에서 첫 음성의 `trim.start`가 앞 무음만큼 이동했는지 확인한다.
8. `logical_caption` 모드에서는 먼저 원본 대본 의미 섹션의 Whisper 시작·종료를 확정하고, 각 `video_cuts[]`의 시작·종료를 그 구간과 정확히 같게 만든다. 레퍼런스의 전역 `shot_durations`는 이 경계를 덮어쓰지 않는다.
9. 새 레퍼런스마다 기존 `style_profile.json`을 그대로 복사하지 말고 `reference.analysis_dir`에서 새 분석을 만든다.
10. `reference.approval_required: true`이면 0~8초 샘플 승인 전 `draft_name`의 전체 초안을 생성하지 않는다. `false`이면 내부 검수 게이트 통과 뒤 전체 초안을 자동 생성하고 샘플만 최종 결과처럼 전달하지 않는다.
11. `sfx.directory`가 없거나 비어 있어도 오류로 중단하지 말고 빈 색인·경고·미충족 이벤트를 보고한다.
12. 효과음 싱크는 onset이 아니라 이벤트별로 선택한 지각상 sync point를 기준으로 검증한다.
13. 저장된 CapCut 초안에서 `target_start + sync_point - source_start`를 다시 계산하고 해결된 앵커와 실제 FPS 기준 1프레임 이내인지 확인한다.
14. `sync_point` 또는 필요한 active tail이 `max_duration`, source 범위, fade로 잘리면 생성에 실패한다.
15. 레퍼런스와 같은 효과음이라고 기록하려면 재현 가능한 파형 점수, 2위 후보와 레퍼런스 발생 시각을 보고서에 남긴다. 레퍼런스 절대 타임은 새 영상에 복사하지 않는다.
16. 본문 자막은 저장된 초안의 실제 텍스트와 bbox를 다시 읽어 `single_line`, `max_width_px`, `orphan_min_chars`를 모두 검증한다. 줄바꿈·폭 초과·고아 조각이 하나라도 있으면 생성에 실패한다.
17. `allow_layering: false`이면 한 의미 이벤트당 primary 한 개만 배치한다. 충돌한 후보는 `simultaneous_limit`으로 보고하고 타임라인에 넣지 않는다.
18. 기본 `max_simultaneous: 1` 프로젝트는 저장된 초안에서 효과음 세그먼트 겹침이 없어야 하고, 효과음이 하나 이상이면 효과음 트랙도 정확히 한 개여야 한다. 위반하면 생성에 실패한다.
19. `video_assignments`의 수는 원본 `audio_segments[].captions[]` 총수와 같아야 한다. 모든 `caption_index`, 파일 `match`, `semantic_tags`, `reason`을 생성 전에 검사한다.
20. 한 줄 표시를 위해 나뉜 생성 자막의 첫 시작부터 마지막 종료까지를 원본 의미 섹션 범위로 보존한다. 같은 섹션 내부와 어떤 표시 자막 내부에도 영상 컷을 넣지 않는다.
21. 저장된 `draft_info.json`에서 영상 material 순서, target/source 시작·길이, 음성 커버리지, 본문 자막 target 구간, 영상 공백·겹침을 다시 계산한다. `leave_gap`이면 짧은 소스가 끝난 시각부터 해당 논리 섹션 종료까지의 선언된 꼬리 공백만 허용한다. 위치·길이 오차가 `video_alignment.tolerance_seconds`를 넘거나 선언되지 않은 공백·겹침이 있으면 생성에 실패한다.
22. 실패 시 `VIDEO_SECTION_COUNT_MISMATCH`, `VIDEO_SECTION_START_MISMATCH`, `VIDEO_SECTION_END_MISMATCH`, `VIDEO_SECTION_DURATION_MISMATCH`, `VIDEO_SECTION_MATERIAL_MISMATCH`, `VIDEO_SOURCE_START_MISMATCH`, `VIDEO_CUT_INSIDE_CAPTION`, `VIDEO_AUDIO_COVERAGE_MISMATCH`, `VIDEO_TIMELINE_GAP_OR_OVERLAP`, `VIDEO_SEMANTIC_EVIDENCE_MISSING`, `BODY_CAPTION_TARGET_START_MISMATCH`, `BODY_CAPTION_TARGET_DURATION_MISMATCH`, `CAPTION_WHISPER_ALIGNMENT_UNAVAILABLE` 중 실제 원인 코드를 기록한다.
23. 리소스 기반 animation/effect/transition의 저장 객체에 `path`가 없거나 경로가 존재하지 않으면 `MOTION_ANIMATION_RESOURCE_UNRESOLVED`, `MOTION_VIDEO_EFFECT_RESOURCE_UNRESOLVED`, `MOTION_TRANSITION_RESOURCE_UNRESOLVED` 중 실제 코드를 기록하고 생성을 실패시킨다.
24. `keyframe_motion`은 저장된 `common_keyframes`의 property type, keyframe 수, 상대 시각, 값이 모두 일치해야 한다. 하나라도 다르면 `MOTION_KEYFRAME_*_MISMATCH`로 실패시킨다.
25. placeholder와 해결되지 않은 `extra_material_refs`를 저장 초안에서 검사한다. 알려진 PyCapCut 0.0.3 텍스트 1x speed UUID는 별도 `known_pycapcut_text_speed_refs`로 보고하고, 그 밖의 미해결 참조는 `MOTION_EXTRA_MATERIAL_REF_UNRESOLVED`로 실패시킨다.
26. 훅 강도를 올린 작업도 영상·음성·본문 자막 경계는 승인 샘플과 1ms 이내로 유지한다. 훅 SFX는 사용자가 레이어링을 명시하지 않은 한 단일 트랙에서 순차 배치하고 동시성 1을 유지한다.
27. 레퍼런스가 컷온 자막이면 기본 본문 애니메이션을 비워 둔다. 사용자가 추가 움직임을 요청한 논리 문장만 `logical_overrides`에 넣고 상태를 `fallback_user_requested`로 남긴다.
28. 섹션당 primary 영상 강조는 하나만 두고, 타임라인 효과는 같은 lane에서 겹치지 않게 한다. 레퍼런스에서 확인되지 않은 플래시·합성 흔들림을 임의 추가하지 않는다.
29. 스타일 효과 적용 전 기준 초안이 있으면 영상 target/source, 음성 trim/target, 자막 텍스트/target, 효과음 target/source/sync의 앞 샘플 범위를 직접 비교한다. 1ms를 넘는 차이가 생기면 효과 적용을 완료하지 않는다.
30. `motion_effect_verification.json`의 `expected_effect_count`와 `saved_effect_count`가 같고 `objective_motion_pass: true`인지 확인한다. 효과가 저장되지 않았거나 이름·구간·키프레임이 다르면 생성에 실패한다.
31. 편집 가능 모드는 훅·본문·CTA를 실제 텍스트 세그먼트로 만들고 CapCut 목록의 이름 있는 animation/effect만 사용한다. 글자가 합성된 PNG와 `common_keyframes`가 하나라도 있으면 `EDITABLE_*` 원인 코드로 실패시킨다.
32. 편집 가능 모드는 `native_resource_patch_report.json`과 `editable_controls_verification.json`을 반드시 출력하고, 실제 요청된 로컬 패키지·사용 횟수·사건 그래프에서 `mode != none`인 고유 사건 수와 같은 named control 수·`common_keyframe_group_count: 0`·`editable_controls_pass: true`를 모두 만족해야 한다. 전부 `none`인 레퍼런스에는 named animation 0개를 요구한다.
33. 설치되지 않은 애니메이션을 키프레임으로 조용히 흉내 내지 않는다. 현재 CapCut 목록에서 역할이 가까운 검증 리소스를 고르거나 사용자에게 미해결 차이를 보고한다.
34. `product_context`가 활성화된 작업은 초안 생성 전에 정확한 업체·제품을 증분 동기화하고 `product_context_snapshot.json`을 만든다. 최근 대본은 창작 이력으로만 쓰고 제품 사실·가격·효능의 근거로 사용하지 않는다.
35. 같은 `job_id`의 대기 피드백은 현재 수정본에 사용할 수 있지만, 다음 작업에는 사용자 승인 상태가 `approved`인 제품·스타일 규칙만 적용한다. `rejected` 피드백은 부정 예시로 남기며 다시 긍정 규칙으로 사용하지 않는다.

사용자가 “재생헤드까지 잘라 달라”고 스크린샷과 정확한 초/프레임을 주면 해당 음성 항목의 `trim_start`로 기록한다. 30fps에서 5프레임은 약 `0.1667초`다. 정확한 값이 없으면 파형 자동 감지를 사용하고 추측한 수동 값을 넣지 않는다.

`audio_segments`가 비어 있거나 `video_sequence`와 `video_assignments`가 모두 없으면 초안 생성이 불가능하다. `video_sequence`와 `video_assignments`를 동시에 쓰는 것도 오류다. 대본에 있지만 음성이 없는 부분은 `notes`에 기록하고 사용자에게 알린다.

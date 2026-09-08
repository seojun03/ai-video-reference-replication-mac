# Company and Product Asset Library

업체와 제품 자산을 다음 고정 루트 아래에서 관리한다.

`${VIDEO_PRODUCT_LIBRARY_ROOT}`

## Contents

1. Identity and matching
2. Canonical product folder
3. Reuse policy
4. Product asset manifest
5. Official source and ImageGen master
6. Master QC and failure policy

## 1. Identity and matching

- 사용자에게 `업체명`과 `제품명`을 반드시 직접 입력받는다. 상세페이지에서 추론한 이름으로 대체하지 않는다.
- 비교할 때만 Unicode NFC, 앞뒤 공백 제거, 연속 공백 축약, casefold를 적용한다.
- 정규화된 이름이 정확히 같은 디렉터리만 일치로 인정한다.
- 부분 일치, 포함 관계, 철자 유사도, 다른 업체의 동명 제품으로 자동 선택하지 않는다.
- 같은 정규화 이름에 둘 이상의 디렉터리가 대응하면 `ambiguous`로 중단하고 사용자에게 정확한 폴더를 확인한다.
- 실제 디렉터리 이름에는 사용자가 입력한 표시명을 유지한다. `/`, `\\`, NUL, `.` 또는 `..`처럼 경로를 바꾸는 이름은 거부한다.

다음 상태를 구분한다.

| 상태 | 처리 |
|---|---|
| `existing_product` | 정확히 일치하는 업체와 제품 폴더를 사용하고 승인된 제품 매니페스트를 우선 읽는다. |
| `existing_company_new_product` | 기존 업체 폴더 아래 새 제품 폴더를 만든다. 다른 제품의 제품 앵커는 재사용하지 않는다. |
| `new_company_product` | 새 업체와 제품 폴더를 만든다. |
| `ambiguous` | 어떤 폴더도 선택하거나 만들지 않고 확인을 요청한다. |

`scripts/resolve_product_asset_library.py`를 먼저 생성 없는 상태로 실행해 일치 상태를 확인한다. 상세페이지가 사용자가 말한 제품과 일치함을 확인한 뒤, 신규 범위에만 `--create`를 사용한다.

## 2. Canonical product folder

```text
업체별 영상소스/
└── {업체명}/
    ├── _공용 표현/
    └── {제품명}/
        ├── 상세페이지 원본/
        ├── 제품 마스터 이미지/
        ├── 제품 표현 이미지/
        ├── 기존 영상 표현/
        ├── 제품 정보/
        │   └── product-assets.json
        └── 생성 결과물/
```

- `상세페이지 원본`: 다운로드한 공식 페이지 이미지와 출처 메타데이터. 원본을 수정하지 않는다.
- `제품 마스터 이미지`: ImageGen 결과, 공식 라벨·로고 레이어, 검수된 최종 제품 마스터.
- `제품 표현 이미지`: 수채화·일러스트·재질 표현처럼 제품 마스터에서 파생된 정지 이미지.
- `기존 영상 표현`: 해당 제품에서 승인된 영상 컷, 모션 예시와 레퍼런스 분석.
- `제품 정보`: 지식 문서, 시각 자료팩과 매니페스트.
- `생성 결과물`: 날짜별 영상 결과. 새 생성 작업은 `YYYY-MM-DD/작업 기록/<한글 작업명>`에 독립 기록을 두고, 같은 날짜의 사용 영상은 모두 `YYYY-MM-DD/생성 클린본`에 모은다. 기획·음성·편집 등 보이는 폴더 이름은 한글을 쓴다. 상세 저장·호환 경로 규칙은 `ai-video-reference-replication/references/output-folder-organization.md`를 따른다.
- `_공용 표현`: 제품에 종속되지 않은 업체 공용 색감, 공간, 캐릭터와 연출만 둔다.

기존 업체 폴더의 레거시 구조를 이동하거나 이름을 바꾸지 않는다. 정확한 제품 폴더 밖의 파일은 읽기 전용 후보로만 조사하고, 매니페스트에 `approved`와 재사용 범위가 기록되기 전에는 자동 사용하지 않는다.

## 3. Reuse policy

- 제품 앵커는 같은 업체·같은 제품에서만 재사용한다.
- 기존 제품 마스터라도 현재 상세페이지의 용기, 포장 버전, 용량, 뚜껑, 색상과 라벨 배치가 일치하는지 다시 확인한다.
- 다른 제품의 실루엣, 라벨, 내용물, 원료 또는 사용 결과를 가져오지 않는다.
- 업체 공용 표현은 `product_neutral: true`, `approval_status: approved`이고 현재 대본의 공간·스타일 역할과 호환될 때만 재사용한다.
- 기존 영상은 구도·연출 후보가 될 수 있지만, 현재 사용자가 지정한 레퍼런스 영상의 역할을 덮어쓰지 않는다.
- 매니페스트가 없는 레거시 자산은 `candidate`다. 시각 확인과 출처 기록 없이 `approved`로 승격하지 않는다.

## 4. Product asset manifest

`제품 정보/product-assets.json`은 다음 핵심 필드를 유지한다.

```json
{
  "schema_name": "incore.product-assets",
  "schema_version": 1,
  "manifest_revision": 1,
  "company": {"display_name": "", "normalized_name": ""},
  "product": {"display_name": "", "normalized_name": ""},
  "library_root": "",
  "company_dir": "",
  "product_dir": "",
  "detail_page": {
    "url": "",
    "checked_at": "",
    "packaging_version_note": "",
    "packaging_fingerprint": ""
  },
  "approved_anchors": {
    "product_master_asset_id": null,
    "deterministic_label_asset_id": null,
    "styled_product_asset_ids": []
  },
  "ready_for_scene_generation": false,
  "assets": [],
  "created_at": "",
  "updated_at": "",
  "paths": {},
  "policy": {},
  "revisions": []
}
```

각 `assets` 항목에는 최소한 다음을 기록한다.

- `asset_id`, 제품 폴더 기준 `relative_path`, `asset_type`, `role`, `version`;
- `approval_status`: `candidate`, `qc_passed`, `approved`, `rejected`, `stale` 중 하나;
- `product_scope`, `product_neutral`, `source_type`, `source_url`, `source_sha256`, `packaging_fingerprint`;
- `derived_from_asset_ids`, `generator`, `generation_prompt`;
- `label_preservation_method`, `qc`, `created_at`.

승인 제품 마스터는 반드시 승인·QC 통과한 `official_source` 자산에서 파생되고 `generator`가 `built_in_imagegen`으로 시작하며 실제 생성 프롬프트와 `qc.status: pass`를 보존해야 한다. 읽을 수 있는 라벨은 `official_pixel_composite`, `official_product_composite` 또는 실제로 읽을 라벨이 없는 경우만 허용한다. `ready_for_scene_generation`은 상세페이지 URL·확인 시각·포장 fingerprint가 기록되고 승인 마스터의 fingerprint가 일치할 때만 `true`다.

기존 파일을 덮어쓰지 않는다. 새 파일은 `v001`, `v002`처럼 증가하는 버전 이름을 사용하고, 승인 앵커 포인터만 새 자산 ID로 갱신한다.

## 5. Official source and ImageGen master

제품이 페이지에 보이면 상세페이지 이미지를 컷 생성에 곧바로 사용하지 않는다.

1. 가장 선명한 공식 정면·측면·후면 이미지를 원본 그대로 `상세페이지 원본`에 저장한다.
2. 기존 승인 마스터가 현재 포장과 정확히 맞으면 재사용한다.
3. 없거나 포장이 바뀌었으면 Gate 1에 `ImageGen 제품 마스터 1회`를 별도 작업으로 표시한다.
4. 승인 후 `imagegen` 스킬을 전부 읽고 built-in `image_gen` edit 경로를 사용한다.
5. 로컬 원본을 편집 대상으로 쓸 때 먼저 `view_image`로 확인한다.
6. 생성 결과를 기본 생성 폴더에 남겨두지 말고 `제품 마스터 이미지`에 새 버전으로 복사한다.
7. 생성 결과와 공식 원본을 나란히 검사한 뒤에만 승인 앵커로 기록한다.

제품 마스터 프롬프트는 `precise-object-edit`로 취급하고 다음 불변 조건을 반복한다.

- 제품 종류, 실루엣, 가로세로 비율, 용기·파우치 구조, 뚜껑·펌프·스파우트 모양을 바꾸지 않는다.
- 재질, 색, 반사, 내용물 색과 라벨 위치를 바꾸지 않는다.
- 새 문구, 로고, 인증, 숫자, 장식 또는 제품 부품을 만들지 않는다.
- 배경과 노이즈 정리, 해상도와 가장자리 품질 개선만 수행한다.

ImageGen 출력의 글자를 정확한 라벨로 간주하지 않는다. 읽을 수 있는 라벨·로고·인증은 공식 원본 픽셀을 마스크 또는 후반 합성으로 되돌린다. 원본 라벨 자체가 판독 불가능하면 AI로 복원하지 않고 고해상도 공식 이미지를 요청한다.

## 6. Master QC and failure policy

다음을 공식 원본과 비교한다.

- 전체 실루엣과 비율;
- 뚜껑, 펌프, 포장 접힘, 손잡이와 가장자리;
- 재질, 색, 광택과 투명도;
- 라벨 크기, 위치, 로고와 읽을 수 있는 문구;
- 용량·구성·개수와 개봉 상태;
- 배경 잔여물, 가짜 글자, 추가 부품과 다른 제품처럼 보이는 변형.

하나라도 중요한 차이가 있으면 `rejected`로 기록하고 컷 생성을 중단한다. 자동 재생성하지 않는다. 원인, 한 번의 좁은 수정안과 예상 작업 수를 보고하고 별도 승인을 받는다.

수채화 같은 스타일 버전은 검수된 제품 마스터에서 파생한다. 스타일은 배경·질감·가장자리 표현에 적용하되, 가독성이 필요한 실제 라벨은 결정적 공식 픽셀로 유지한다.

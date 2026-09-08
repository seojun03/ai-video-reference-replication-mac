---
name: product-page-reference-video
description: Turn a user-supplied company name, product name, ecommerce product detail page URL, reference video, exact target script, and 1:1 or 9:16 ratio into a reusable company/product asset library, source-grounded product visual pack, approved ImageGen product master, and reference-led AI video workflow. Use when the user asks to 상세페이지 링크로 제품을 파악해서 영상 생성, 상세페이지 이미지와 정보를 자동으로 영상에 반영, 업체별 제품 이미지와 기존 표현 재사용, 신규 업체·제품 폴더와 제품 마스터 생성, or product-page-to-video automation. Require company and product names explicitly, use normalized exact folder matching only, preserve official product labels deterministically, and hand per-cut still generation to the selected Higgsfield/OpenAI GPT Image 2 lane and motion to Kling v3.0 after Gate 1 approval.
---

## 공유 플러그인 실행 경로

이 문서가 들어 있는 `skills`의 상위 폴더를 `PLUGIN_ROOT`로 확인하고, 먼저 `../../references/recipient-runtime.md`를 읽는다. `${PLUGIN_ROOT}`는 현재 설치된 이 플러그인의 절대 경로로, `${VIDEO_PRODUCT_LIBRARY_ROOT}`와 `${CAPCUT_AUTOMATION_ROOT}`는 수신자 환경의 경로로 해석한다. 하위 스킬은 이 플러그인 안의 형제 폴더를 우선 사용한다. 플러그인 제작·수정·공유 요청은 영상 제작 인터뷰나 유료 생성, 앱 종료를 시작하지 않는다.


# 상세페이지 기반 레퍼런스 영상 자동화

## 목적

사용자가 지정한 업체명·제품명·상세페이지에서 제품 정보와 공식 이미지를 확인하고, 고정 자산 루트에서 기존 승인 자산을 재사용하거나 신규 제품 폴더를 만든다. 상세페이지의 제품 이미지를 컷 생성에 바로 넣지 않는다. 검수된 제품 마스터를 먼저 확정하고, 대본의 각 의미 구간에 제품 외형·물성·원료·공정·공간·전후 상태를 연결한 뒤 `ai-video-reference-replication`으로 넘긴다.

역할을 다음처럼 분리한다.

- 업체·제품 라이브러리: 승인된 자산과 과거 표현의 재사용 기준;
- 상세페이지: 제품 정체성, 공식 원본, 물성, 원료, 공정과 페이지 주장;
- built-in ImageGen: 공식 원본을 보존하는 제품 마스터 전처리;
- 레퍼런스 영상: 구도, 연출 연산자, 화풍과 페이싱;
- 대본: 장면 의미, 설득 순서와 대본 길이에 따른 컷 수;
- selected still lane: Gate 1 이후 컷별 장면 스틸 (`higgsfield_only`, `openai_only`, or `hybrid_parallel`);
- Kling v3.0: 승인된 단일 시작 이미지의 3초 모션.

## 필수 입력 — Gate P0

현재 대화에서 사용자가 직접 제공하거나 지정한 다음 여섯 가지를 확인한다.

1. 업체명;
2. 제품명;
3. 제품 상세페이지 URL;
4. 레퍼런스 영상;
5. 정확한 대상 대본 또는 레퍼런스 음성을 대본으로 전사하라는 명시;
6. `1:1` 또는 `9:16` 화면비.

누락되거나 모호한 항목만 요청하고 그 턴을 끝낸다. 여섯 항목이 모두 없으면 다음처럼 요청한다.

> 1. 업체명을 알려주세요.  
> 2. 제품명을 알려주세요.  
> 3. 제품 상세페이지 URL을 보내주세요.  
> 4. 레퍼런스 영상을 첨부하거나 정확한 파일 경로를 알려주세요.  
> 5. 사용할 대본을 붙여주세요. 레퍼런스 음성을 전사해 대본으로 쓰려면 그렇게 명시해 주세요.  
> 6. 최종 화면비를 `1:1` 또는 `9:16` 중에서 선택해 주세요.

업체명과 제품명은 상세페이지에서 추론해 대신 채우지 않는다. 사용자가 직접 입력하게 한다. URL 없이 로컬 제품 사진만 제공된 경우에도 공식 제품 정보의 기준이 될 상세페이지 URL을 요청한다. 페이지가 삭제됐거나 접근이 막힌 경우에만 같은 페이지의 PDF, 전체 스크린샷 또는 저장 HTML을 대체 자료로 받되 원래 URL도 기록한다.

Gate P0 전에는 업체 폴더 검색, 페이지 탐색, 유사 상품 추정, 로컬 파일 탐색, 비용 확인 또는 생성 작업을 하지 않는다.

## 의존 스킬과 참고 자료

Gate P0가 충족되면 다음을 필요한 순서대로 전부 읽고 따른다.

1. [references/company-product-asset-library.md](references/company-product-asset-library.md): 고정 루트, 정확 일치, 폴더와 매니페스트 규칙;
2. `extract-product-ad-knowledge`: 상세페이지 전체 판독과 사실 원장;
3. [references/product-visual-source-pack.md](references/product-visual-source-pack.md): 영상용 제품 자료팩 구조;
4. `script-visual-expression-interview`: 시각 정보 커버리지와 최대 3개 질문;
5. `imagegen`: 제품 마스터를 새로 만들어야 할 때의 built-in 편집·저장·검수 규칙;
6. `ai-video-reference-replication`: 레퍼런스 기법 매핑, Gate 1, Higgsfield 이미지·Kling 영상과 QC.

레퍼런스 분석 전에 `ai-video-reference-replication/references/reference-replication-contract.md`도 전부 읽는다. 연결 스킬의 후보 원장, 컷당 단일 선택 시작 이미지, 비용 승인, 모델 잠금과 재시도 규칙을 완화하지 않는다.

## 1. 업체·제품 라이브러리 정확 일치

고정 루트는 다음이다.

`${VIDEO_PRODUCT_LIBRARY_ROOT}`

다음 명령을 생성 옵션 없이 먼저 실행한다.

```bash
python3 scripts/resolve_product_asset_library.py \
  --company "<업체명>" \
  --product "<제품명>"
```

비교할 때만 Unicode NFC, 앞뒤 공백 제거, 연속 공백 축약과 casefold를 적용한다. 정규화된 이름이 정확히 같은 항목만 재사용한다. 부분 일치, 유사어, 철자 추정 또는 다른 제품 폴더를 자동 선택하지 않는다. 후보가 둘 이상이면 어떤 폴더도 사용하거나 만들지 않고 정확한 폴더를 확인한다.

상태별로 처리한다.

- `existing_product`: `제품 정보/product-assets.json`을 먼저 읽고 승인된 제품 마스터와 표현을 후보로 삼는다.
- `existing_company_new_product`: 기존 업체의 제품 중립적인 승인 표현만 후보로 삼고, 다른 제품 앵커는 절대 빌리지 않는다.
- `new_company_product`: 다른 업체의 자료를 가져오지 않는다.

레거시 자산은 자동 승인하지 않는다. 매니페스트가 없는 파일은 읽기 전용 `candidate`로만 검사한다. 기존 업체 공용 표현은 `product_neutral: true`, `approval_status: approved`일 때만 재사용한다.

정확한 기존 업체가 확인되면 그 업체 폴더 안에서만 `rg --files`로 이미지·영상·매니페스트 후보를 찾는다. 다른 업체 폴더는 검색하지 않는다. 파일명만으로 제품을 확정하지 말고 상세페이지의 현재 제품 외형과 직접 비교한다. 같은 제품임이 확인된 자산은 제품 범위 후보로, 제품에 종속되지 않은 공간·색감·캐릭터·연출만 공용 표현 후보로 분리한다. 출처와 QC를 매니페스트에 기록하기 전에는 생성 입력으로 쓰지 않는다.

## 2. 상세페이지 전체 판독과 제품 일치 확인

페이지를 읽기 전용으로 열고 `extract-product-ad-knowledge` 절차에 따라 본문, 옵션, 구매 안내, 리뷰, Q&A, JSON-LD, 대표·상세·지연 로딩 이미지와 GIF를 끝까지 확인한다. 구매, 로그인 제출, 장바구니 추가나 리뷰 작성 같은 외부 변경을 하지 않는다.

특히 다음을 확인한다.

- 제품 정면·후면·측면·개별 구성·개봉 상태·내용물·사용 장면;
- 원료, 제조·가공 방식, 물성, 사용 순서, 변화 과정과 결과 상태;
- 산지, 사찰, 연구실, 공장, 주방처럼 제품 의미에 필요한 공간;
- 인증, 수치, 후기, 판매·재고·혜택처럼 후반 합성에만 쓸 증거 자산.

사용자가 입력한 업체명·제품명과 페이지의 브랜드·본품이 실질적으로 다르면 폴더를 만들거나 오염시키지 말고 불일치를 보여준 뒤 확인을 요청한다. 접근이 막히면 사용자에게 같은 페이지의 스크린샷·PDF·HTML을 요청하고 유사 상품 페이지로 대체하지 않는다.

페이지 일치가 확인된 뒤 신규 범위 또는 정확히 일치하는 기존 제품에 표준 하위 폴더·매니페스트가 없는 경우에만 `--create`를 사용한다. 이 옵션은 빠진 구조만 추가하며 기존 파일을 덮어쓰지 않는다.

```bash
python3 scripts/resolve_product_asset_library.py \
  --company "<업체명>" \
  --product "<제품명>" \
  --create
```

기존 디렉터리나 파일을 이동·개명·덮어쓰지 않는다.

## 3. 사실과 자산 분류

모든 내용을 다음으로 분리한다.

- `confirmed_page_fact`: 포장이나 페이지에 명확히 보이는 제품 정보;
- `page_claim`: 브랜드가 주장하지만 외부 검증되지 않은 내용;
- `dynamic_page_state`: 가격, 재고, 리뷰 수와 한정 혜택;
- `visual_inference`: 페이지 장면에서 읽을 수 있지만 사실로 단정하면 안 되는 해석;
- `missing_visual_fact`: 대본 표현에 필요하지만 페이지에서 확인되지 않은 정보.

페이지 주장과 동적 정보에는 확인 날짜와 출처 위치를 붙인다. 상세페이지에서 확인되지 않은 효능, 물성, 인증, 비교 우위 또는 사용 결과를 만들지 않는다.

## 4. 공식 원본 저장과 기존 마스터 판정

가장 선명한 공식 정면·측면·후면 이미지를 원형 그대로 `상세페이지 원본`에 버전 이름으로 저장한다. 출처 URL, 페이지 위치, 확인 날짜와 역할을 매니페스트에 기록한다.

기존 승인 제품 마스터가 있으면 현재 페이지와 다음을 비교한다.

- 제품 종류, 용량과 구성;
- 실루엣, 비율과 포장 구조;
- 뚜껑, 펌프, 스파우트와 개봉 방식;
- 재질, 색상, 광택과 투명도;
- 라벨 크기, 위치와 포장 버전.

모두 일치할 때만 `approved_existing`으로 재사용한다. 하나라도 제품 정체성을 바꾸는 차이가 있으면 기존 자산을 `stale` 후보로 두고 새 마스터를 계획한다.

## 5. 제품 시각 자료팩 생성

[references/product-visual-source-pack.md](references/product-visual-source-pack.md) 구조로 다음을 만든다.

- `제품 정보/product-ad-knowledge.md`;
- `제품 정보/product-visual-source-pack.md`;
- `제품 정보/product-visual-source-manifest.json`;
- `제품 정보/product-assets.json`.

자료팩에는 업체·제품의 정확 일치 상태, 공식 원본, 기존 승인 자산, 제품 외형·물성·원료·공간·공정, 대본 구간별 커버리지, 결정적 후반 합성 요소와 금지 추론을 기록한다. 상세페이지 모델·고객 얼굴은 별도 허가 없이는 인물 앵커로 사용하지 않는다. 페이지 레이아웃은 사용자가 지정하지 않는 한 레퍼런스 구도를 덮어쓰지 않는다.

구조 검증기를 실행한다.

```bash
python3 scripts/validate_visual_source_pack.py \
  /absolute/path/to/product-visual-source-pack.md

python3 scripts/validate_product_asset_manifest.py \
  /absolute/path/to/product-assets.json
```

## 6. 대본 시각 커버리지와 최소 인터뷰

대본을 의미 구간으로 나누고 각 구간에 자료팩의 제품·물성·원료·공간·동작·전후 상태를 연결한다. 페이지와 승인 자산에서 확인된 내용을 다시 묻지 않는다.

`script-visual-expression-interview`의 다음 판정식을 적용한다.

> 답 A와 답 B가 피사체, 동작, 재료, 공간, 상태 변화, 카메라 구도 또는 최종 화면을 다르게 만드는가?

`예`인 누락 정보만 한 턴에 최대 3개 질문한다. 사용자가 `알아서`, `기본값`, `자연스럽게`라고 답하면 페이지 근거 안에서 보수적인 가정을 선택하고 공개한다. 모든 중요 대본 구간이 연결되면 `ready_for_visual_planning: yes`로 표시한다.

## 7. 제품 마스터 계획과 Gate 1

상세페이지 제품이 보이고 현재 포장과 일치하는 승인 마스터가 없으면 상세페이지 이미지를 컷 생성에 바로 쓰지 않는다. Gate 1에 built-in ImageGen 제품 마스터 첫 시도 1회를 별도 작업으로 넣는다.

Gate 1에서 다음을 함께 보여준다.

- 업체명, 제품명, 라이브러리 상태와 실제 경로;
- 재사용할 승인 자산 또는 신규 ImageGen 작업 수;
- 선택한 공식 원본과 공식 라벨·로고 원본;
- 제품 마스터 불변 조건과 QC 항목;
- 전체 컷 계획과 선택된 이미지 레인별 후보 수·Kling·로컬 편집 작업 수;
- 각 도구가 노출하는 현재 비용. 비용이 노출되지 않으면 0으로 쓰지 말고 `도구에서 비용 메타데이터 미제공`으로 표시;
- 페이지 주장, 가정과 후반 합성 요소.

한 번의 명시적 Gate 1 승인은 표에 적힌 제품 마스터 첫 시도, 선택된 이미지 레인의 컷별 후보 첫 시도, Kling 첫 시도와 로컬 편집만 허가한다. 추가 변형, 재시도, 범위 변경, 게시 또는 미기재 비용은 허가하지 않는다.

## 8. ImageGen 제품 마스터 생성과 QC

Gate 1 승인 뒤 새 마스터가 필요할 때만 `imagegen` 스킬을 전부 읽는다. built-in `image_gen`의 편집 경로를 사용하고, 로컬 공식 원본을 먼저 `view_image`로 확인한다. 이 단계는 컷별 Higgsfield 모델 잠금의 예외인 제품 자산 전처리다.

제품 마스터 프롬프트를 `precise-object-edit`로 작성하고 다음을 잠근다.

- 제품 실루엣, 비율, 용기·포장 구조, 뚜껑·펌프와 라벨 위치 유지;
- 재질, 색, 반사, 투명도와 내용물 색 유지;
- 배경·노이즈·가장자리와 해상도만 정리;
- 새 문구, 로고, 인증, 숫자, 장식 또는 부품 생성 금지.

생성 결과는 기본 생성 폴더에만 두지 않고 `제품 마스터 이미지`에 덮어쓰지 않는 버전 파일로 복사한다. 생성된 글자를 최종 라벨로 인정하지 않는다. 공식 원본의 라벨·로고·인증 픽셀을 결정적으로 되돌려 최종 제품 마스터를 만든다. 원본 라벨도 판독 불가능하면 AI로 복원하지 않고 고해상도 공식 이미지를 요청한다.

공식 원본과 나란히 실루엣, 비율, 구조, 재질, 색, 라벨 위치·문구, 구성 수량, 가짜 글자와 추가 부품을 검사한다. 통과한 자산만 매니페스트의 `approved_anchors.product_master_asset_id`로 기록하고 `ready_for_scene_generation: true`, 자료팩의 `ready_for_generation: yes`로 바꾼다. 실패하면 `rejected`로 기록하고 이후 컷 생성을 시작하지 않는다. 자동 재생성하지 않고 한 번의 좁은 수정안과 작업 수를 보고해 별도 승인을 받는다.

수채화 같은 제품 표현 버전은 승인 마스터에서 파생한다. 배경과 질감은 스타일화할 수 있지만 읽을 수 있는 실제 라벨은 공식 픽셀로 유지한다.

## 9. 레퍼런스 영상 기획으로 핸드오프

`ready_for_visual_planning: yes`가 되면 다음을 `ai-video-reference-replication`에 넘긴다.

- 업체명, 제품명과 제품 폴더·매니페스트 경로;
- 상세페이지 URL과 확인 날짜;
- 공식 원본, 승인 마스터 또는 계획된 ImageGen 마스터 작업;
- 제품 자료팩과 대본 시각 커버리지;
- 정확한 대본, 화면비와 레퍼런스 영상;
- 재사용 승인 표현, 공개된 가정, 결정적 후반 합성 자산과 금지 요소.

대본 길이로 컷 수를 산정하고 각 대본 기능에 가장 적합한 레퍼런스 기법을 선택한다. 상세페이지 이미지 순서나 기존 프로젝트 컷 순서를 새 영상 컷 순서로 복사하지 않는다. 컷별 장면 스틸은 상위 계획의 `image_generation_mode`를 따른다. `hybrid_parallel`이면 Higgsfield GPT Image 2와 OpenAI GPT Image 2 후보를 각각 생성한 뒤 하나만 Kling 시작 이미지로 선택하고, 생성 영상은 항상 base Kling v3.0을 유지한다.

## 산출물과 완료 기준

사용자가 확인할 수 있는 해당 업체·제품 폴더에 절대 경로가 추적되는 결과를 남긴다.

- 제품 지식 문서, 제품 시각 자료팩과 두 매니페스트;
- 공식 상세페이지 원본과 출처;
- 승인된 제품 마스터, 결정적 라벨·로고 레이어와 QC 기록;
- 재사용한 기존 표현과 재사용 근거;
- 레퍼런스 기법 분석과 Gate 1 컷 계획;
- 승인 후 컷별 이미지·3초 영상·QC 보고서.

완료하려면 사용자 입력 업체·제품이 정확히 일치하고, 신규 폴더가 고정 루트 아래에만 생성되어야 한다. 페이지의 이미지형 콘텐츠까지 확인하고, 다른 제품 자산을 제품 앵커로 쓰지 않으며, 읽을 수 있는 라벨을 생성 모델에 맡기지 않는다. Gate 1 전에는 생성하지 않고, 제품 마스터 QC가 끝나기 전에는 컷 생성을 시작하지 않는다. 승인된 모든 컷에는 출처·모델·자산 버전과 QC가 있어야 한다.

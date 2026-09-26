# 제품별 자료 자동 저장과 다음 작업 재사용

이 절차는 모든 제작 범위에서 필수다. `visuals_only`에서도 실행하고 CapCut 엔진 설치 여부와 무관하게 동작한다. 채팅 기억이나 사용자에게 같은 자료를 다시 받는 것으로 대체하지 않는다. 유지보수 중에는 실제 고객 자료를 수집하거나 진행 중인 제작 기록을 변경하지 않는다.

## 저장 위치와 내용

`${VIDEO_PRODUCT_LIBRARY_ROOT}/<업체>/_knowledge/products/<제품>/` 아래에 보관한다.

- `knowledge-library.json`: 정확한 업체·제품, 현재 상세페이지 URL과 변경 이력, 원본 출처·해시·상태 목록.
- `saved-inputs/`: 사용자 대본·초안·확정본, 특징·USP·성분·사용법·타깃, 사용자 정정, 상세페이지 저장본, 공식 제품 이미지, 레퍼런스 분석, 시각 자료팩의 변경하지 않은 사본. 같은 바이트는 중복 저장하지 않는다.
- `product_context.md`: 기존 내용을 보존하며 저장 자료의 위치를 연결한다. `product_facts` 원문을 읽어 실제 특징과 USP를 로드한다. 경로 목록만 읽고 제품 분석을 완료했다고 보고하지 않는다.

생성물 승인과 제품 마스터 QC는 기존 `product-assets.json`에서 계속 관리한다. 저장됐다는 이유만으로 모든 이미지를 승인 마스터로 승격하지 않는다. 사용자가 준 이미지도 실제 제품·포장·필요 각도를 확인한 후 사용한다. 파일은 플러그인 설치 폴더 밖에 보관하며 플러그인 배포에 포함하지 않는다.

## 새 작업 시작: 조회 먼저

1. 사용자가 지정한 정확한 업체명·제품명을 사용한다. 같은 업체의 다른 제품도 자동 혼용하지 않는다.
2. 아래 `inspect`로 저장 자료와 파일 무결성을 조회하고, 기존 `product_context.md`와 이번 컷에 필요한 원문·이미지만 읽는다. 기존 방식의 `product-assets.json`과 자료팩도 함께 사용할 수 있다.
3. 충분한 자료가 있으면 상세페이지 재다운로드·재분석이나 사용자 재첨부 요청 없이 재사용한다. 사용자 새 자료·정정, 포장 변경, 깨진 파일, 실제 필요한 정보 공백이 있을 때만 해당 부분을 갱신한다.
4. 신규 업체·제품이면 제공된 상세페이지/첨부 자료에서 특징·USP·성분·사용법·타깃·공식 이미지를 먼저 확보한다. 현재 작업에 필요한 정보와 이미지를 정리해 `capture`한다. 저장 자체의 별도 승인을 반복하지 않는다.
5. 필요한 이미지가 없으면 같은 제품의 저장된 공식 URL/자료에서 먼저 확보한다. 필요한 각도·라벨·사용 동작이 여전히 안 보이거나, 제품 식별·정보가 모호하거나 충돌하면 그 누락/충돌만 사용자에게 요청한다. 다른 제품으로 채우거나 추측하지 않는다.

```bash
python3 "${PLUGIN_ROOT}/skills/ai-video-reference-replication/scripts/product_knowledge_store.py" \
  --root "${VIDEO_PRODUCT_LIBRARY_ROOT}" --company "<업체>" --product "<제품>" \
  inspect --require product_facts --require product_image --snapshot "<run>/product_context_snapshot.json"
```

`missing_roles`는 새 저장 목록에서의 공백이다. 기존 동일 제품 자료와 이번 작업의 실제 필요 여부까지 확인한 후 질문한다. 제품이 등장하지 않는 작업에 불필요한 이미지 요청을 만들지 않는다. 최초 기획에서는 저장된 대본 이력이 있다는 이유로 현재 사용자의 새 대본/새 기획 의사를 대신 결정하지 않는다.

## 확보 직후 저장: 완료 시점까지 미루지 않기

대본 수신·수정·명시적 확정, 제품 분석, 공식 이미지 확보, 사용자 정정이 발생할 때마다 해당 자료만 추가한다. 대본 원문을 그대로 보존하고 초안/확정본과 승인 문구를 구별한다. 최신 정정은 우선하되 이전 버전도 보존한다. 대본의 문장을 제품 사실로 자동 추출·승격하지 않는다.

에이전트가 아래처럼 입력 묶음을 만든 뒤 `capture --input <bundle.json>`을 실행한다. `path`와 `text`는 항목마다 하나만 사용한다. 제품 특징과 USP는 구조화 JSON이나 Markdown 원문으로 저장한다. 기록 가능한 사실·주장의 출처를 보존하며 저장 작업이 별도의 검증/단정이 되지 않게 한다.

```json
{
  "company": "<업체>", "product": "<제품>", "job_id": "<현재 작업 ID>",
  "detail_page_url": "https://example.com/product",
  "latest_user_url": true,
  "items": [
    {"kind": "script", "path": "<대본 절대경로>", "source_type": "user_supplied", "status": "approved", "approval_quote": "<실제 승인 문구>"},
    {"kind": "product_facts", "path": "<특징·USP 원문 절대경로>", "source_type": "official_page", "source_url": "https://example.com/product", "status": "provided"},
    {"kind": "product_image", "path": "<공식 이미지 절대경로>", "source_type": "official_page", "source_url": "https://example.com/image.png", "status": "provided"}
  ]
}
```

`latest_user_url: true`는 사용자가 실제로 새 URL을 직접 지정한 경우에만 쓴다. 기존 URL과 새 추출 URL이 충돌하면 자동 덮어쓰지 않는다. 대본 수정본은 새 바이트로 저장하고 승인 전에는 `draft`로 둔다. 보관 이력은 현재 작업의 사용/생성 허가와 별개다.

저장 후 `inspect --snapshot`으로 다시 읽어 경로·해시·업체·제품을 확인한다. 실행 매니페스트에 `product_knowledge.enabled: true`, `library`, `revision`, `snapshot_path`, `snapshot_sha256`, 재사용한 record ID와 실제 요청한 누락 항목을 기록한다. 저장 실패는 명시하고 재사용 가능하다고 보고하지 않는다. 작업이 중단돼도 이미 확보한 자료는 남아 있어야 한다.

기존 CapCut `manage_product_context.py sync`가 사용되는 경우 원본 지식·승인 피드백은 그 엔진과 호환되게 유지한다. 엔진이 `product_context.md`를 다시 만들면 `capture`로 자동 저장 절을 다시 연결한다. `knowledge-library.json`과 `saved-inputs`를 대체하거나 삭제하지 않는다. 이 저장소는 모델 학습이 아니라 로컬 자료 보관·검색·재사용이다.

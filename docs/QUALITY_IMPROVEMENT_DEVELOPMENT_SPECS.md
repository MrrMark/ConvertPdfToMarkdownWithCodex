# Quality Improvement Development Specs

이 문서는 `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 남아 있는 **active Q 작업**을 실제 구현 PR로 옮기기 위한 개발 명세다.

완료된 Q 작업의 명세와 구현 결과는 이 문서에 남기지 않고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 관리한다.

## 운영 규칙

- `docs/NEXT_QUALITY_IMPROVEMENT_PLAN.md`에 신규 Q 항목이 추가되면, 구현 전에 이 문서에 대응 개발 명세를 작성한다.
- 구현 중 범위가 바뀌면 Next Plan 항목과 이 문서를 함께 갱신한다.
- 구현 완료, 테스트 통과, PR merge까지 끝난 Q 항목은 이 문서에서 제거하고 완료 명세 archive로 옮긴다.
- 완료 이력은 Git commit, PR, release note, changelog, 그리고 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에서 추적한다.
- 이 문서에는 앞으로 구현할 active 명세만 있어야 한다.

## 공통 원칙

- 외부 RAG/indexing 서비스 호출은 구현 범위에 포함하지 않는다.
- 모든 검증과 fixture 생성은 local-only, deterministic 동작을 기본으로 한다.
- PDF 원문 텍스트, 표, 이미지 provenance는 요약하거나 재서술하지 않는다.
- 새 public JSON 출력이 생기면 `docs/OUTPUT_SCHEMA.md`와 `docs/schema/` 계약을 함께 갱신한다.
- 실패는 가능한 한 구조화된 report로 남기고, 어느 파일/record/field/page가 문제인지 식별 가능해야 한다.
- 테스트는 작은 unit test, script smoke test, golden regression test를 우선한다.

## 현재 Active Development Specs

### 공통 결정 사항

Q103-Q105는 팀 RAG 업로드 제약 대응과 Docling 벤치마킹/확장 설계를 함께 다룬다.
상충되는 요구는 아래 기준으로 정리한다.

- 기본 `image_mode=referenced`와 기존 public output contract는 유지한다.
- OCR 비활성화는 성능 개선책으로 사용하지 않는다. OCR 호출 수를 줄이더라도 evidence/context로 결정 가능한 경우에만 줄인다.
- 팀 RAG용 assetless 경로는 opt-in으로 둔다. 이미지 파일을 못 올리는 환경에서는 `placeholder + figure_text chunk` 조합을 쓰게 한다.
- Docling식 picture description 또는 VLM 경로는 벤치마크와 설계 대상이지만 기본 변환에는 넣지 않는다.
- benchmark evidence는 `/tmp` 또는 local `pdf/` 아래에 두고 raw PDF, image, Markdown 원문, 고객 식별 경로는 커밋하지 않는다.
- 새 CLI 옵션, public JSON field, summary count가 생기면 README, `docs/OUTPUT_SCHEMA.md`, schema export, docs tests를 함께 갱신한다.

### P0 / Q103. Assetless Technical RAG Figure Text Chunks

#### 배경

팀 RAG가 PNG/JPG 같은 이미지 파일을 지원하지 않는 경우, 현재 `referenced` 이미지 파일은 업로드 대상에서 제외된다.
이미 `--image-mode placeholder`는 있으나, 이것만 쓰면 도표/이미지의 검색 가능한 정보가 caption/comment 수준으로 제한된다.

#### 목표

이미지 파일 없이도 기술 스펙 도표의 검색성과 provenance를 유지한다.
`figures_rag.jsonl`의 caption, heading path, bbox, detected labels, nearby text refs를 이용해 `retrieval_chunks_rag.jsonl`에 `figure_text` chunk를 opt-in으로 추가한다.

#### 제안 인터페이스

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode placeholder \
  --rag-figure-text-chunks
```

GUI는 기존 `기술 스펙 RAG`에 별도 toggle 또는 새 표시명 `기술 스펙 RAG(이미지 파일 제외)`를 제공하되, 내부 구현은 위 option 조합을 사용한다.

#### 구현 규칙

- `figure_text`의 `text`는 관측된 텍스트만 사용한다.
  - caption text
  - section/heading path
  - detected labels
  - nearby text refs
  - figure kind
- 생성형 설명, 추론된 의미, 사람이 읽기 좋게 만든 요약은 넣지 않는다.
- `source_refs`는 `figures_rag.jsonl`의 `figure_id`, page, bbox를 가리킨다.
- 이미지 파일 path가 없는 placeholder 모드에서도 manifest/report/provenance가 깨지지 않아야 한다.
- captionless/low-confidence 후보는 `figure_text`로 승격하지 않거나 `retrieval_priority`를 낮추고 diagnostics-only로 남긴다.

#### 주요 파일

- `pdf2md/config.py`
- `pdf2md/models.py`
- `pdf2md/cli.py`
- `pdf2md/gui_presets.py`
- `pdf2md/serializers/rag_figures.py`
- `pdf2md/serializers/rag_chunks.py`
- `pdf2md/pipeline.py`
- `docs/OUTPUT_SCHEMA.md`
- `docs/RAG_INDEXER_INTEGRATION_RECIPES.md`
- `tests/test_rag_figures.py`
- `tests/test_rag_chunks.py`
- `tests/test_output_schema_contract.py`

#### 검증

- `--image-mode placeholder --rag-figure-text-chunks`에서 이미지 파일 없이 `figure_text` chunk가 생성된다.
- `retrieval_chunks_rag.jsonl`의 source refs가 `figures_rag.jsonl` record와 해소된다.
- `validate_index_contract.py`, `validate_provenance_integrity.py`, `validate_artifact_integrity.py`가 assetless profile을 통과한다.
- generated description이 기본 출력에 들어가지 않는 테스트를 추가한다.

### P1 / Q104. Docling Benchmark Harness And Comparison Pack

#### 목표

Docling에서 배울 부분을 감으로 도입하지 않고, 현재 툴과 같은 input corpus에서 OCR/layout/table/figure/RAG 품질과 속도를 비교한다.
벤치마크는 local-only를 기본으로 하며, Docling 미설치 환경에서는 skip/advisory로 처리한다.

#### 벤치마크 축

- OCR backend
  - Docling `auto`, Tesseract, RapidOCR, EasyOCR, macOS OCR 중 설치된 것
  - 현재 툴 `pytesseract + pypdfium2`
- OCR mode
  - normal OCR
  - force full page OCR
  - image/table/figure region OCR 후보
- Table/layout
  - Docling table structure fast/accurate
  - 현재 툴 auto/html fallback/table sidecar
- Image/figure
  - placeholder/referenced export
  - figure caption coverage
  - picture classification/description은 local model 또는 explicit opt-in일 때만 측정
- RAG readiness
  - retrieval chunk count
  - expected source coverage
  - table-field coverage
  - figure_text query coverage
  - source-ref/provenance integrity
- Performance
  - total duration
  - pages/sec
  - stage durations when available
  - output file count/size

#### 제안 산출물

- `docling_benchmark_report.json`
- `docling_artifact_comparison.json`
- `docling_scorecard.md`

위 산출물은 raw text body, image bytes, customer path를 복사하지 않고 count, hash, metric, warning code, sanitized label만 저장한다.

#### 주요 파일

- `scripts/benchmark_conversion.py`
- `scripts/run_preset_eval.py`
- 신규 `scripts/benchmark_docling_comparison.py`
- `docs/RAG_INDEXER_INTEGRATION_RECIPES.md`
- `docs/QUALITY_SCORECARD.md` if the scorecard is refreshed
- `tests/test_quality_gate_scripts.py`
- `tests/test_docs_examples.py`

#### 검증

- Docling 미설치 환경에서 script가 명확한 advisory report를 남기고 실패하지 않음
- synthetic fixture에서 현재 툴만으로 comparison schema를 생성 가능
- local Docling 설치 환경에서는 최소 PDF 1개에 대해 Markdown/JSON export metric을 수집 가능
- remote service, hosted VLM, external embedding 호출은 기본 금지

### P2 / Q105. Docling-Informed OCR And Layout Extension Design

#### 목표

Q104 벤치마크 결과를 바탕으로 실제 도입할 확장 기능을 정한다.
후보는 다중 OCR backend, 도표/표 영역별 OCR, 선택적 picture description, layout-aware table/figure 인식이다.

#### 설계 후보

- OCR backend adapter
  - `TesseractOcrBackend` 기존 구현 유지
  - `RapidOcrBackend`, `EasyOcrBackend`, `OcrMacBackend`는 optional dependency로 분리
  - backend별 language code mapping과 confidence normalization을 명시
- Region OCR
  - full page OCR보다 image/table/figure crop OCR을 먼저 시도
  - crop bbox, source figure/table id, confidence, rejected reason을 report에 기록
- Picture description
  - 기본 비활성화
  - local-only model 또는 explicit remote opt-in만 허용
  - output field는 `generated_description` 계열로 원문 `text`와 분리
- Layout-aware table/figure adapter
  - Docling adapter는 P2 experimental backend로 둔다.
  - current extractor 결과와 adapter 결과를 바로 섞지 않고 comparison/evidence pack을 먼저 만든다.

#### 완료 조건

- Q104 metric으로 실제 개선 가능성이 확인된 후보만 구현 backlog로 승격한다.
- 새 기능은 adapter/opt-in 구조와 schema contract를 갖는다.
- 원문 텍스트와 table row source-of-truth를 생성형 출력으로 대체하지 않는다.

## 완료 명세 Archive

완료된 Q34-Q102 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.

# Docling-Informed OCR And Layout Extension Design

이 문서는 Q105 산출물이다.
Q104 `scripts/benchmark_docling_comparison.py` 하네스와 Docling 공식 문서 기준으로 다중 OCR backend, region OCR, picture description, layout-aware table/figure adapter 도입 여부를 검토한다.

## Decision Summary

- 기본 변환 경로는 변경하지 않는다.
- Docling은 필수 dependency로 추가하지 않는다.
- 현재 Q104 local smoke에서는 Docling이 설치되지 않아 `docling_not_installed` advisory skip만 확인됐다. 따라서 Docling-backed 품질 우위가 입증됐다고 보지 않는다.
- 구현 backlog로 바로 승격할 항목은 없다.
- 다음에 새 Q 작업을 만들려면 Docling 설치 환경에서 같은 PDF corpus를 대상으로 `docling_benchmark_report.json`, `docling_artifact_comparison.json`, `docling_scorecard.md`를 먼저 생성해야 한다.
- 코드 변경 후보는 모두 adapter 또는 opt-in이어야 하며, 원문 `text`, table row source, image provenance를 생성형 출력으로 대체하면 안 된다.

## Evidence Inputs

Q104 local evidence:

- `scripts/benchmark_docling_comparison.py`는 current-tool metric과 Docling optional run을 같은 comparison pack에 기록한다.
- local smoke에서는 current-tool output과 validator metric이 생성됐고, Docling은 미설치 상태로 advisory skip 처리됐다.
- report/comparison pack은 `raw_content_included=false`, `image_bytes_included=false`, `customer_paths_included=false`를 유지한다.

Docling reference points:

- `DocumentConverter().convert(...)`가 PDF 변환 entry point이고, 결과 `document`에서 Markdown export가 가능하다: <https://docling-project.github.io/docling/reference/document_converter/>
- Docling은 EasyOCR, Tesseract, Tesseract CLI, OcrMac, RapidOCR OCR engine을 지원한다: <https://docling-project.github.io/docling/getting_started/installation/#ocr-engines>
- PDF pipeline options는 OCR, table structure, picture description 같은 feature flag를 분리한다: <https://docling-project.github.io/docling/reference/pipeline_options/>
- table structure는 fast/accurate mode와 cell matching option을 가진다: <https://docling-project.github.io/docling/usage/advanced_options/#control-pdf-table-extraction-options>
- picture description은 `do_picture_description=True`와 local VLM option으로 켤 수 있다: <https://docling-project.github.io/docling/examples/pictures_description/>
- Docling CLI도 image export mode와 table mode를 option으로 분리한다: <https://docling-project.github.io/docling/reference/cli/>

Current tool baseline:

- OCR은 `pypdfium2` page render와 `pytesseract` 기반 full-page OCR이며, confidence warning과 partial success report를 남긴다.
- Q98-Q100으로 structure marker OCR lazy 처리, page worker chunking, OCR page parallelization을 완료했다.
- image는 `referenced`, `embedded`, `placeholder` mode를 지원하고, Q103에서 image file 없이 `figure_text` chunk를 opt-in으로 생성한다.
- table은 `pdfplumber` strategy 기반이며, Q101 adaptive mode와 HTML fallback 안전 정책을 유지한다.
- RAG sidecar는 source refs, provenance validators, schema contract로 검증한다.

## Candidate Review

| Candidate | Docling에서 배울 점 | 현재 상태 | 기대 효과 | 리스크 | Q105 결정 |
| --- | --- | --- | --- | --- | --- |
| Multi OCR backend | engine option을 분리하고 optional dependency로 다룬다 | Tesseract 한 경로 | scanned PDF/한글/저해상도 OCR 품질 비교 가능 | backend별 language/confidence 의미가 다름 | 설계만 유지. Docling-installed benchmark 없이 구현 승격 보류 |
| Region OCR | OCR을 page 전체가 아니라 image/table/figure region에 한정할 수 있다 | full-page OCR 중심, structure marker lazy OCR 있음 | 불필요한 OCR 비용 감소, figure/table 내부 text 보강 | bbox crop 오류가 원문을 오염시킬 수 있음 | report-only prototype 후보. 기본 text 대체 금지 |
| Picture description | local VLM description을 optional enrichment로 분리한다 | 생성형 description 기본 비활성 | 이미지 업로드 불가 RAG에서 diagram 검색성 보완 가능 | 환각, 저작권/보안, 원문과 생성 텍스트 혼동 | 기본 변환/ingest 승격 금지. local-only 평가 pack 후보 |
| Layout-aware table/figure adapter | table structure fast/accurate, layout model, unified document representation | current extractor 중심 | 복잡 표/figure bbox 비교 기준 확보 | current output과 섞으면 결정성/원문 보존 위험 | comparison-only adapter 후보. merge/blend 금지 |

## Proposed Adapter Boundaries

향후 구현이 필요해지면 아래 경계를 따른다.

```text
pdf2md/
  adapters/
    docling_adapter.py          # optional import only
  ocr_backends/
    base.py                     # OCR backend protocol and normalized result
    tesseract.py                # current behavior
    rapidocr.py                 # optional dependency
    easyocr.py                  # optional dependency
    ocrmac.py                   # optional dependency
```

Public option 후보:

- `--ocr-backend tesseract|rapidocr|easyocr|ocrmac`
- `--ocr-scope auto|page|region`
- `--region-ocr` default false
- `--picture-description-mode off|local`
- `--layout-adapter current|docling-experimental`

Default policy:

- 모든 신규 옵션 기본값은 기존 동작과 같아야 한다.
- optional dependency import 실패는 fatal이 아니라 structured warning/report로 남긴다.
- remote service는 `enable_remote_services`에 해당하는 명시 opt-in 없이는 사용하지 않는다.
- generated description은 `text`가 아니라 `generated_description` 계열 field로 분리한다.

## Required Schema If Implemented Later

Manifest option 후보:

- `options.ocr_backend`
- `options.ocr_scope`
- `options.region_ocr`
- `options.picture_description_mode`
- `options.layout_adapter`

Report summary 후보:

- `ocr_backend_counts`
- `region_ocr_attempt_count`
- `region_ocr_accepted_count`
- `region_ocr_rejected_count`
- `picture_description_attempt_count`
- `picture_description_generated_count`
- `layout_adapter_status`

Warning/reason 후보:

- `OCR_BACKEND_UNAVAILABLE`
- `OCR_BACKEND_CONFIDENCE_UNSUPPORTED`
- `REGION_OCR_REJECTED`
- `PICTURE_DESCRIPTION_DISABLED`
- `PICTURE_DESCRIPTION_UNAVAILABLE`
- `LAYOUT_ADAPTER_UNAVAILABLE`
- `LAYOUT_ADAPTER_COMPARISON_ONLY`

## Benchmark Gate Before Any Implementation

새 Q 작업을 열기 전 최소 조건:

1. Docling이 설치된 local-only 환경에서 공개 가능 synthetic fixture와 비공개 local corpus 각각 1개 이상을 Q104 harness로 실행한다.
2. `docling_status="success"`인 report를 확보한다.
3. raw text, raw image, customer path가 report/comparison pack에 포함되지 않았음을 확인한다.
4. current-tool 대비 개선 후보가 metric으로 보여야 한다.
5. 개선 후보가 없으면 implementation backlog를 만들지 않는다.

승격 가능한 metric 예:

- OCR backend: 낮은 confidence warning 감소, OCR empty result 감소, 처리 시간 허용 범위 내 유지
- Region OCR: full-page OCR 대비 duration 감소, accepted region text provenance 증가, rejected reason 안정화
- Picture description: figure_text query hit 개선, generated field 분리 유지, hallucination review 통과
- Layout adapter: 복잡 표 HTML fallback 품질 개선, table-field coverage 증가, hash/determinism 유지

## Conservative Rollout Plan

현재 시점에서는 아래 남은 작업을 active backlog로 등록하지 않는다.
Q110/Q111에서 runtime probe와 OCR backend adapter contract는 완료했다.
추가 Docling-installed benchmark evidence가 확보되면 다음 순서로 별도 Q 작업을 생성한다.

1. Region OCR report-only prototype
2. Local-only picture description evaluation pack
3. Docling layout adapter comparison mode

## Non-Goals

- Docling을 기본 변환 backend로 교체하지 않는다.
- OCR 결과를 사람이 읽기 좋게 임의 교정하지 않는다.
- 복잡 표를 모델 출력만 믿고 GFM으로 강제하지 않는다.
- generated picture description을 원문 `text`로 섞지 않는다.
- remote VLM/API를 기본값 또는 암묵적 fallback으로 호출하지 않는다.

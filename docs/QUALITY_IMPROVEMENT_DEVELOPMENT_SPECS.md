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

## P1 / Q107. Assetless Figure Visual Semantics Layer

### 배경

Q103/Q106에서 이미지 업로드가 불가능한 RAG 환경을 위해 `image_mode=placeholder`와 `figure_text` chunk 경로를 마련했다.
현재 `figure_text`는 caption, heading path, detected labels, nearby text refs, conservative `figure_kind`처럼 PDF에서 관측 가능한 텍스트와 provenance만 사용한다.

이 방식은 hallucination 위험이 낮고 원문 보존 원칙에 맞지만, 회로도, 파형, 블록다이어그램처럼 의미가 이미지 픽셀 자체에 있는 figure는 검색 텍스트가 부족할 수 있다.
Q107은 이 공백을 줄이기 위해 opt-in 시각 의미 보강 계층을 설계하고 구현한다.

### 목표

- 이미지 파일을 RAG에 업로드하지 못하는 환경에서도 figure의 의미 검색성을 개선한다.
- `figure_text`의 원문/관측 텍스트 계약은 유지한다.
- 생성 설명과 구조화 추출 결과를 원문 텍스트와 명확히 분리한다.
- backend 미설치, 저신뢰 OCR, 저신뢰 생성 결과를 변환 실패로 과장하지 않고 report warning/diagnostic으로 남긴다.
- 동일 입력, 동일 옵션, 동일 backend/version이면 deterministic output을 유지한다.

### 비목표

- 기존 `이미지 업로드 불가 RAG 대응` preset의 기본 동작을 생성형 설명 기반으로 변경하지 않는다.
- `document.md` 본문에 생성형 figure description을 기본 삽입하지 않는다.
- 외부 RAG/indexing service, 외부 hosted VLM API 호출을 기본 구현 범위에 넣지 않는다.
- 이미지 binary/base64를 JSONL sidecar에 저장하지 않는다.
- 생성 설명을 원문 PDF 텍스트처럼 citation source of truth로 취급하지 않는다.

### 제안 옵션

CLI/Config 후보:

- `--figure-region-ocr`
  - figure bbox, caption 주변, axis/legend/label 후보 영역을 crop해 region-level OCR을 수행한다.
  - OCR 결과는 confidence와 함께 `figures_rag.jsonl` diagnostics 또는 새 sidecar에 기록한다.
- `--rag-generated-figure-descriptions`
  - opt-in generated figure description sidecar와 retrieval chunk를 생성한다.
  - backend가 없으면 advisory warning을 남기고 기존 산출물은 계속 생성한다.
- `--figure-description-backend local-vlm|docling`
  - 초기 구현은 adapter interface와 fake/test backend, 또는 설치 증거가 있는 local-only backend부터 허용한다.
  - hosted API backend는 별도 보안/비용/재현성 검토 전까지 제외한다.
- `--figure-structure-extraction`
  - block diagram, waveform, circuit/register layout 같은 유형에 대해 구조화 extraction을 시도한다.

GUI 후보:

- 기존 `이미지 업로드 불가 RAG 대응` preset은 그대로 `placeholder + figure_text`만 켠다.
- generated description, region OCR, structure extraction은 `Optimize Options(유저 선택)` 또는 별도 experimental section에서만 켠다.
- 생성형 옵션 label에는 원문이 아니라 생성 보강임을 명시한다.

### 산출물 계약 초안

기존 산출물:

- `figures_rag.jsonl`
  - figure provenance의 source of truth로 유지한다.
  - region OCR 후보와 figure kind diagnostics를 확장할 수 있다.
- `retrieval_chunks_rag.jsonl`
  - 기존 `chunk_type="figure_text"`는 관측 텍스트 전용으로 유지한다.

신규 sidecar 후보:

- `figure_descriptions_rag.jsonl`
  - generated visual description 전용 sidecar다.
  - 필수 필드 후보:
    - `schema_version`
    - `figure_description_id`
    - `figure_id`
    - `page`
    - `bbox`
    - `description_type`: `generated_visual_description`
    - `text`
    - `generated_text`: `true`
    - `backend`
    - `backend_version`
    - `prompt_profile`
    - `confidence`
    - `source_refs`
    - `warnings`
  - `text`는 source-of-truth가 아니며, 반드시 generated provenance flag를 포함한다.
- `figure_structures_rag.jsonl`
  - diagram/waveform/circuit 구조화 결과 전용 sidecar다.
  - 필수 필드 후보:
    - `schema_version`
    - `figure_structure_id`
    - `figure_id`
    - `page`
    - `bbox`
    - `figure_kind`
    - `structure_type`
    - `nodes`
    - `edges`
    - `signals`
    - `components`
    - `axes`
    - `source_refs`
    - `extraction_method`
    - `confidence`
    - `warnings`

Retrieval chunk 후보:

- `chunk_type="figure_description"`
  - `source_refs[]`는 `figure_descriptions_rag.jsonl` record와 `figure_id/page/bbox`를 가리킨다.
  - `semantic_types`에는 `generated_figure_description`을 포함한다.
  - `generated_text=true` 또는 동등한 metadata를 유지한다.
- `chunk_type="figure_structure"`
  - `source_refs[]`는 `figure_structures_rag.jsonl` record와 `figure_id/page/bbox`를 가리킨다.
  - block/edge/signal/component를 text로 직렬화하되, 구조화 field도 별도 sidecar에 남긴다.

### 처리 흐름

1. 기존 image/figure extraction으로 `figure_records`와 bbox를 만든다.
2. `--figure-region-ocr`가 켜져 있으면 figure bbox 기반 crop을 생성한다.
3. region OCR은 전체 페이지 OCR과 분리된 stage로 수행하고, low confidence 후보는 rejected diagnostics에만 남긴다.
4. `--rag-generated-figure-descriptions`가 켜져 있으면 backend adapter에 crop request를 전달한다.
5. backend 결과는 confidence, backend metadata, generated provenance flag와 함께 sidecar로 기록한다.
6. `--figure-structure-extraction`이 켜져 있으면 figure kind별 extractor를 실행한다.
7. retrieval chunk 생성 단계에서 `figure_text`, `figure_description`, `figure_structure`를 서로 다른 `chunk_type`으로 추가한다.
8. manifest/report에는 option, sidecar filename, record count, skipped/rejected count, backend warning을 기록한다.

### Backend adapter 설계

권장 interface:

```python
@dataclass(frozen=True)
class FigureCropRequest:
    figure_id: str
    page: int
    bbox: list[float]
    image_path: Path | None
    heading_path: list[str]
    caption_text: str | None
    nearby_text: list[str]


@dataclass(frozen=True)
class FigureDescriptionResult:
    text: str
    confidence: float | None
    backend: str
    backend_version: str | None
    warnings: list[dict[str, object]]
```

구현 규칙:

- adapter는 `pdf2md/extractors` 또는 `pdf2md/adapters` 하위에 분리한다.
- backend import 실패는 import time failure가 아니라 runtime advisory warning으로 처리한다.
- prompt/profile text는 deterministic하게 versioned profile id로 관리한다.
- raw prompt에 PDF 원문 전체나 파일 경로를 넣지 않는다.
- confidential safe mode에서는 backend metadata에도 absolute path를 남기지 않는다.

### Figure kind별 구조화 후보

- Block diagram
  - `nodes`: block label, bbox, confidence
  - `edges`: source node, target node, arrow label, confidence
  - `signals`: input/output signal name
- Waveform
  - `signals`: signal name, state transition text, timing relation
  - `axes`: time axis, voltage/value axis, units
  - `events`: rising/falling edge, annotated interval
- Circuit/register layout
  - `components`: reference designator, symbol kind, pin/net label
  - `edges`: connectivity relation
  - `signals`: named nets or bus labels

초기 구현은 모든 유형을 완성하려 하지 말고, block diagram과 waveform fixture를 우선한다.
저신뢰 구조화 결과는 `figure_structures_rag.jsonl`에 넣지 않고 diagnostics/rejected count로 남긴다.

### 경고와 report

신규 warning 후보:

- `FIGURE_REGION_OCR_UNAVAILABLE`
- `FIGURE_REGION_OCR_LOW_CONFIDENCE`
- `FIGURE_DESCRIPTION_BACKEND_UNAVAILABLE`
- `FIGURE_DESCRIPTION_LOW_CONFIDENCE`
- `FIGURE_STRUCTURE_EXTRACTION_LOW_CONFIDENCE`
- `FIGURE_VISUAL_SEMANTICS_SKIPPED`

`report.summary` 후보:

- `figure_region_ocr_attempted_count`
- `figure_region_ocr_promoted_label_count`
- `figure_description_record_count`
- `figure_description_file_count`
- `figure_description_low_confidence_count`
- `figure_structure_record_count`
- `figure_structure_file_count`
- `figure_structure_low_confidence_count`

warning severity는 기본 advisory로 시작한다.
단, 사용자가 strict quality gate를 명시한 별도 option을 추가하기 전에는 generated/structure 실패가 변환 exit code를 partial로 올리지 않는다.

### 주요 파일

- `pdf2md/config.py`
- `pdf2md/cli.py`
- `pdf2md/gui.py`
- `pdf2md/gui_presets.py`
- `pdf2md/gui_runner.py`
- `pdf2md/pipeline.py`
- `pdf2md/extractors/images.py`
- `pdf2md/extractors/ocr.py`
- `pdf2md/serializers/rag_figures.py`
- `pdf2md/serializers/rag_chunks.py`
- `pdf2md/output_writers.py`
- 신규 후보: `pdf2md/serializers/rag_figure_descriptions.py`
- 신규 후보: `pdf2md/serializers/rag_figure_structures.py`
- 신규 후보: `pdf2md/adapters/figure_description.py`

### 테스트 계획

- Unit tests
  - option parsing과 Config contract
  - fake figure description backend success/failure
  - generated description sidecar serialization
  - figure structure sidecar serialization
  - retrieval chunk `figure_description`/`figure_structure` 생성
  - generated chunk가 `figure_text`와 다른 `chunk_type`/metadata를 갖는지 확인
- Integration tests
  - synthetic block diagram PDF
  - synthetic waveform PDF
  - captionless diagram fixture
  - backend unavailable advisory warning
  - confidential-safe mode path redaction
- Golden/regression tests
  - 기존 `이미지 업로드 불가 RAG 대응` preset output이 생성 설명 없이 유지되는지 확인
  - 기존 `figure_text` record count와 source refs가 기본값에서 회귀하지 않는지 확인
- Contract tests
  - `docs/OUTPUT_SCHEMA.md`와 schema export/update
  - `manifest.options`와 `report.summary` 필드 존재 조건
  - JSONL record ordering deterministic check

### 검증 명령

최소:

```bash
.venv311/bin/python -m pytest tests/test_rag_figures.py tests/test_cli.py tests/test_gui_presets.py tests/test_docs_examples.py -q
.venv311/bin/python -m pytest -q
.venv311/bin/python -m ruff check .
git diff --check
```

신규 fixture가 추가되면:

```bash
.venv311/bin/python -m pytest tests/test_golden.py -q
.venv311/bin/python scripts/run_release_gates.py --output-dir /private/tmp/pdf2md-q107-release --gates schema
```

### 완료 기준

- 기본 변환과 기존 `이미지 업로드 불가 RAG 대응` preset은 생성 설명 없이 기존 보수 정책을 유지한다.
- opt-in 옵션을 켰을 때만 generated description/structure sidecar와 retrieval chunk가 생성된다.
- 생성 설명은 `generated_text=true` 또는 동등 metadata로 원문 텍스트와 분리된다.
- `document.md`에는 생성 설명이 기본 삽입되지 않는다.
- backend unavailable/low confidence 상황에서도 partial success 원칙에 따라 core outputs는 생성된다.
- 모든 신규 JSONL record는 `figure_id/page/bbox/source_refs`로 원본 PDF 위치를 추적할 수 있다.
- 문서와 테스트가 새 public output schema를 고정한다.

### 리스크와 완화

- 생성형 설명 hallucination
  - 기본 off, generated metadata 필수, source text와 chunk type 분리.
- backend 설치/성능 편차
  - adapter boundary, advisory warning, fake backend test, benchmark evidence 기록.
- JSONL에 이미지 binary가 섞이는 위험
  - sidecar에는 path/provenance만 기록하고 base64/image bytes 금지.
- 회로도/파형 구조화 난이도
  - block diagram/waveform fixture부터 단계적 구현, low-confidence 결과는 rejected diagnostics로 제한.
- RAG 검색 결과에서 원문과 생성 설명 혼동
  - `chunk_type`, `semantic_types`, `generated_text`, `source_refs`를 모두 분리하고 docs에 명시.

## 완료 명세 Archive

완료된 Q34-Q106 품질 개선 명세와 구현 결과는 `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`에 보관한다.

# RAG Indexer Integration Recipes

이 문서는 `pdf2md` 산출물을 OpenAI, Azure AI Search, LangChain, LlamaIndex 같은 downstream RAG/indexing 파이프라인에 넣을 때의 field mapping과 운영 체크리스트를 정리한다.

원칙:

- 외부 서비스 호출 코드는 이 저장소 기본 구현에 넣지 않는다.
- indexer 입력은 `retrieval_chunks_rag.jsonl`을 기본으로 사용한다.
- 정밀 추적, 요구사항 diff, table-field QA가 필요하면 source sidecar를 함께 보관한다.
- `text`는 원문 또는 deterministic row text이며 요약/재서술 대상이 아니다.

## 기본 입력 선택

권장 ingest 순서:

1. `retrieval_chunks_rag.jsonl`
2. `requirement_traceability_rag.jsonl`
3. `technical_tables_rag.jsonl`
4. `tables_rag.jsonl`
5. `figures_rag.jsonl`
6. `cross_refs_rag.jsonl`

Vector DB에는 보통 `retrieval_chunks_rag.jsonl`만 넣고, 나머지 sidecar는 citation expansion, impact analysis, UI drilldown, test script 수정 범위 계산에 사용한다.

## Purpose Profiles

CLI와 GUI preset은 같은 local-only profile matrix를 사용한다.

| Profile | 목적 | 주요 효과 |
| --- | --- | --- |
| `preserve` | 기본 원문 보존 | RAG table sidecar와 chunk 보강 옵션을 보수적으로 끔 |
| `rag_optimized` | 일반 RAG ingest | RAG table both, page marker, header/footer removal, hyphen repair, contextual embedding text, sibling merge, relationship metadata |
| `technical_spec_rag` | storage/PCIe/security spec ingest | `rag_optimized`와 같은 chunk 보강을 켜고, 필요 시 `--domain-adapter nvme|pcie|ocp|tcg|spdm|manual`와 함께 사용 |
| `confidential_rag` | 공유/evidence pack | confidential-safe mode, JSONL table sidecar, chunk 보강, sanitized report |
| `preserve_with_sidecars` | Markdown 원문 보존 + sidecar ingest | 본문 변화 가능성이 있는 header/footer/hyphen repair는 끄고 JSONL sidecar와 relationship metadata만 추가 |

```bash
python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag --domain-adapter nvme
python3 -m pdf2md spec.pdf -o output/share --rag-profile confidential_rag
```

## Assetless Figure Text Chunks

PNG/JPG 같은 image asset을 업로드할 수 없는 팀 RAG 환경에서는 placeholder mode와 figure_text chunk를 함께 사용한다.
GUI에서는 `이미지 업로드 불가 RAG 대응` preset을 선택하면 같은 조합이 적용된다. 이 GUI preset은 새 CLI profile이 아니라 `technical_spec_rag`에 `image_mode=placeholder`, `rag_figure_text_chunks=true`를 더한 조합이다.

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode placeholder \
  --rag-figure-text-chunks
```

운영 정책:

- `document.md`에는 image link 대신 placeholder comment가 남는다.
- `figures_rag.jsonl`은 caption, heading path, bbox, detected labels, nearby text refs를 원문 provenance로 보존한다.
- `retrieval_chunks_rag.jsonl`에는 `chunk_type="figure_text"` record가 추가된다.
- `figure_text.text`는 관측된 caption/heading/label/nearby text와 conservative figure kind만 사용한다.
- 생성형 picture description, VLM 설명, 사람이 읽기 좋게 만든 요약은 기본 출력에 넣지 않는다.
- `figure_text.source_refs[]`는 `figures_rag.jsonl`의 `figure_id`, page, bbox로 해소되어야 하며 image path는 넣지 않는다.
- `--rag-sidecar-scope minimal`을 함께 쓰더라도 `--rag-figure-text-chunks`가 켜져 있으면 `figures_rag.jsonl`은 provenance 해소를 위해 함께 생성된다.

## Manual Domain Adapter

기존 `nvme`, `pcie`, `ocp`, `tcg`, `spdm`, `customer-requirements`에 맞지 않는 고객 requirement 표는 `manual` adapter로 header 키워드를 보수적으로 추가한다.

```bash
python3 -m pdf2md customer-spec.pdf -o output/customer \
  --rag-profile technical_spec_rag \
  --domain-adapter manual \
  --manual-domain-adapter-label "Customer A Requirements" \
  --manual-domain-adapter-keywords "Customer Key, Customer Requirement"
```

운영 정책:

- `domain_units_rag.jsonl`의 `domain`은 `manual`로 유지하고, `adapter_profile`에 manual label을 기록한다.
- manual keywords는 table header matching을 넓히는 데만 사용한다.
- domain unit의 `text`, `name`, `value`, `description`은 표 또는 typed technical table sidecar에서 관측된 값만 사용한다.
- 고객별 downstream mapping은 RAG/indexer 쪽 profile 문서에서 `manual` adapter label을 기준으로 관리한다.

검증:

```bash
python scripts/validate_index_contract.py --output-dir output/spec --target all --fail-on-error
python scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
```

## 공통 Field Mapping

| Index field | Source field | 비고 |
| --- | --- | --- |
| `id` | `chunk_id` | deterministic primary key |
| `text` | `embedding_text` if present, otherwise `text` | embedding 대상. `embedding_text`는 optional context prefix이며 원문 `text`를 대체하지 않는다. |
| `source_text` | `text` | citation/원문 확인용 source of truth |
| `chunk_type` | `chunk_type` | `requirement`, `technical_table`, `table_row` 우선순위 조정에 사용 |
| `source_refs` | `source_refs` | citation/provenance 원본 |
| `page_start` | `page_range[0]` | page filter |
| `page_end` | `page_range[1]` | page filter |
| `section_path` | `section_path` | section filter/facet |
| `semantic_types` | `semantic_types` | requirement/table/domain unit 필터 |
| `retrieval_priority` | `retrieval_priority` | re-ranking hint |
| `token_estimate` | `token_estimate` | chunk budget diagnostics |
| `embedding_token_estimate` | `embedding_token_estimate` | optional context-prefixed embedding budget diagnostics |
| `source_dedupe_key` | `source_dedupe_key` | duplicate guard |
| `merged_source_chunk_ids` | `merged_source_chunk_ids` | optional original chunk ids for merged sibling text chunks |
| `previous_chunk_id` | `previous_chunk_id` | optional same-group neighbor for context expansion |
| `next_chunk_id` | `next_chunk_id` | optional same-group neighbor for context expansion |
| `section_anchor_chunk_id` | `section_anchor_chunk_id` | optional first chunk in the same section |
| `related_chunk_ids` | `related_chunk_ids` | optional lightweight relationship id list |
| `relationship_strategy` | `relationship_strategy` | optional relationship generation strategy |
| `schema_version` | `schema_version` | chunk contract version |
| `source_sha256` | `source_sha256` | 원본 PDF identity / corpus diff guard |

## Offline Index Contract Validation

Indexer나 framework SDK를 호출하기 전에 local-only validator로 field contract와 metadata mapping 가능성을 점검한다.

```bash
python scripts/validate_index_contract.py --output-dir output --target all --fail-on-error
python scripts/validate_index_contract.py --output-dir output --target azure-ai-search --metadata-max-bytes 32768 --fail-on-error
python scripts/validate_index_contract.py --output-dir output --target all --confidential-safe --fail-on-warning
python scripts/validate_provenance_integrity.py --output-dir output --fail-on-error
python scripts/validate_artifact_integrity.py --output-dir output --fail-on-error
```

생성물:

- `index_contract_report.json`: target별 mapping 가능 여부, JSONL field/type 오류, metadata size guardrail, `source_refs` provenance, confidential-safe metadata finding
- `provenance_integrity_report.json`: sidecar 간 `source_refs` 해소 여부, page/bbox/count/dedupe 정합성 finding
- `artifact_integrity_report.json`: Markdown image link, asset file, manifest path, sidecar count, batch/corpus file map 정합성 finding

운영 체크:

- 이 validator는 OpenAI, Azure AI Search, LangChain, LlamaIndex SDK를 import하거나 외부 서비스에 접속하지 않는다.
- `--confidential-safe`는 path/filename/source hash 노출을 점검하지만 원문 `text`를 익명화하지 않는다.
- `--metadata-max-bytes`는 운영 profile의 보수적 guardrail로 지정한다. 실제 서비스 제한이 바뀔 수 있으므로 배포 profile에서 값을 명시하는 편이 안전하다.
- index contract는 target별 mapping 가능성을, provenance integrity는 sidecar 내부 참조 무결성을, artifact integrity는 실제 파일 세트 소비 가능성을 검증한다. 운영 release gate에서는 셋을 함께 실행하는 편이 안전하다.

## Preset Evaluation Score Gate

GUI에서 `RAG 등록용(최적화)`와 `기술 스펙 RAG`를 비교한 결과를 반복 재현하려면 local-only preset evaluation runner를 사용한다. runner는 preset별 변환, artifact/index/provenance validation, 선택적 SSD contract/RAG eval, 100점 score를 한 번에 산출한다.

```bash
python scripts/run_preset_eval.py \
  --input-pdf spec.pdf \
  --output-root /tmp/pdf2md-preset-eval \
  --presets rag_optimized,technical_spec_rag \
  --domain-adapter nvme \
  --fail-on-threshold
```

생성 파일:

- `preset_eval_report.json`: preset별 score, gate condition, validator summary
- `preset_artifact_comparison.json`: raw content 없이 artifact 존재/크기/record count와 주요 metric delta
- `preset_scorecard.md`: 사람이 빠르게 보는 점수표

`technical_spec_rag`는 `--domain-adapter nvme|pcie|ocp|tcg|spdm|manual`를 함께 지정해야 domain unit, technical table, SSD contract gate가 의미 있게 동작한다. 실제 corpus 원문은 커밋하지 않고 위 세 파일처럼 sanitized summary만 공유한다.

release gate에 포함:

```bash
python scripts/run_release_gates.py \
  --output-dir /tmp/pdf2md-release-preset \
  --gates preset-eval \
  --preset-eval-input-pdf spec.pdf \
  --preset-eval-domain-adapter nvme \
  --preset-eval-min-score 80
```

## Docling Comparison Harness

Docling의 OCR/layout/table/figure 처리 결과를 현재 툴과 비교할 때는 local-only comparison harness를 사용한다.
이 harness는 Docling이 설치되지 않은 CI/개발 환경에서도 현재 툴 metric을 생성하고, Docling 경로는 `docling_not_installed` advisory로 기록한다.

```bash
python scripts/benchmark_docling_comparison.py \
  --input-pdf spec.pdf \
  --output-dir /tmp/pdf2md-docling-comparison \
  --document-label doc-0001 \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode placeholder \
  --figure-region-ocr \
  --rag-generated-figure-descriptions \
  --figure-structure-extraction
```

공식 최신 NVMe NVM Command Set Rev. 1.2를 같은 정책으로 점검할 때는 wrapper를 사용한다.

```bash
python scripts/run_latest_nvme_command_set_eval.py \
  --input-pdf /tmp/NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-command-set
```

공식 최신 NVMe Base와 NVM Command Set은 repo 밖에 내려받은 PDF를 대상으로 sanitized benchmark만 공유한다.
NVM Express 공식 specifications 페이지 기준 최신 NVMe specification set은 NVMe 2.3이며 2025-08-05에 공개되었다.
공식 페이지는 NVMe 2.3 specification set에 Base specification과 NVM Command Set 같은 Command Set specification이 함께 포함된다고 설명한다.

```bash
python scripts/run_latest_nvme_spec_benchmark.py \
  --input-pdf /tmp/NVMe-Base-latest.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-base \
  --spec-document base \
  --mode full_precision \
  --source-url https://nvmexpress.org/specifications/ \
  --fail-on-contract-error
```

NVM Command Set도 같은 `technical_spec_rag + domain_adapter=nvme` contract와 summary-only report 정책을 사용한다.
Command Set 전용 표는 `command_dword_field`, `command_pointer_field`, `command_scope`/`queue_type`,
`pointer_type`, `status_code_group`, `error_class`, `retry_hint` metadata를 추가로 가질 수 있다.
P1 관계 metadata로 `command_context`, `related_command_unit_id`, `related_command_opcode`,
`relationship_hints`가 채워지면 command opcode row와 CDW/pointer/status row를 같은 command 검색 결과로 묶을 수 있다.
이 값들은 reranking/filter hint이며, citation source는 항상 `text`, `raw_cells`, `source_refs`를 기준으로 확인한다.
P2 benchmark는 변환 후 `command_opcode`, `command_dword_field`, `command_pointer_field`, `status_code`
대표 row를 대상으로 local query eval을 실행하고, report에는 query/result 원문 없이 aggregate metric만 남긴다.

```bash
python scripts/run_latest_nvme_spec_benchmark.py \
  --input-pdf /tmp/NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-command-set-benchmark \
  --spec-document nvm_command_set \
  --mode full_precision \
  --fail-on-contract-error \
  --fail-on-command-eval-error
```

빠른 회귀 확인은 기본 1-5페이지 smoke mode로 실행한다.

```bash
python scripts/run_latest_nvme_spec_benchmark.py \
  --input-pdf /tmp/NVMe-Base-latest.pdf \
  --output-dir /tmp/pdf2md-latest-nvme-base-smoke \
  --spec-document base \
  --mode fast_smoke
```

Docling이 실제 설치된 환경에서만 통과해야 하는 release gate는 다음과 같이 실행한다.

```bash
python scripts/run_release_gates.py \
  --output-dir /tmp/pdf2md-release-docling \
  --gates docling \
  --docling-input-pdf /tmp/NVM-Express-NVM-Command-Set-Specification-Revision-1.2-2025.08.01-Ratified.pdf
```

생성 파일:

- `docling_benchmark_report.json`: current-tool/Docling 실행 상태, duration/pages/sec, backend availability, validator metric, finding count
- `docling_artifact_comparison.json`: committed-safe artifact name의 existence/size/SHA-256과 numeric metric delta
- `docling_scorecard.md`: 사람이 빠르게 검토하는 local scorecard
- `latest_nvme_command_set_scorecard.md`: latest NVMe Command Set 전용 sanitized metric scorecard
- `latest_nvme_spec_benchmark_report.json`: latest NVMe Base/NVM Command Set 전용 source URL, source_sha256, option matrix, summary count, sanitized Command Set P2 query-eval summary
- `latest_nvme_spec_benchmark_scorecard.md`: latest NVMe Base/NVM Command Set 전용 sanitized metric scorecard

운영 정책:

- raw Markdown body, Docling raw document dict, image bytes, 고객 파일 경로는 comparison pack에 넣지 않는다.
- latest NVMe spec benchmark report에도 raw spec 전문, Markdown body, generated query, retrieved text, table row content, image bytes, local input path를 넣지 않는다.
- Docling Markdown/dict export는 파일로 저장하지 않고 in-memory virtual artifact hash/size만 기록한다.
- `--require-docling` 또는 release gate `--gates docling`은 Docling 미설치를 실패로 처리한다.
- Q105 확장 설계는 `docs/DOCLING_INFORMED_EXTENSION_DESIGN.md`에서 관리하며, 이 comparison pack에서 확인된 metric/finding을 근거로 adapter/opt-in 후보를 정한다.

## Multi OCR Backend Probe

OCR backend adapter를 도입하기 전에는 backend별 설치 상태와 confidence 단위를 먼저 local-only probe로 확인한다.

```bash
python scripts/probe_ocr_backends.py \
  --ocr-lang kor+eng \
  --backends all \
  --report-file /tmp/pdf2md-ocr-backends/ocr_backend_probe_report.json \
  --json
```

릴리스 전 optional gate로도 실행할 수 있다.

```bash
python scripts/run_release_gates.py \
  --output-dir /tmp/pdf2md-release-ocr-backends \
  --gates ocr-backends \
  --ocr-backend-probe-backends all
```

운영 정책:

- probe는 OCR을 문서에 적용하지 않고 module, executable, language data, platform support만 기록한다.
- `ocr_backend_probe_report.json`에는 raw PDF text, image bytes, customer path를 넣지 않는다.
- Tesseract 계열은 language data를 확인하고, RapidOCR/EasyOCR/OCRmac/Docling은 adapter 구현 전까지 availability와 confidence normalization hint만 기록한다.

## OpenAI Vector Store / Generic Embedding Pipeline

권장 payload:

```json
{
  "id": "chunk-000001",
  "text": "The controller shall return SUCCESS.",
  "metadata": {
    "chunk_type": "requirement",
    "section_path": "1 Requirements",
    "page_start": 1,
    "page_end": 1,
    "source_refs": [
      {"source_type": "requirement_trace", "source_id": "req-trace-000001", "page": 1}
    ]
  }
}
```

운영 체크:

- `source_refs`는 citation 화면이나 test script generator에서 원문 위치로 되돌아가기 위해 보존한다.
- table/technical table chunk에 `embedding_text`가 있으면 embedding 대상은 `embedding_text`, citation 화면과 원문 검증 대상은 `text`를 사용한다.
- `chunk_boundary_policy="merged_sibling_text_blocks"`인 chunk는 adjacent text block만 token budget 안에서 결합한 것이므로 citation expansion에는 `source_refs`와 `merged_source_chunk_ids`를 함께 보존한다.
- relationship metadata가 있으면 `previous_chunk_id`, `next_chunk_id`, `section_anchor_chunk_id`, `related_chunk_ids`는 같은 `retrieval_chunks_rag.jsonl` 내부 final chunk id를 가리킨다. Downstream에서 neighbor expansion에 사용하되 원문 검증은 계속 `source_refs`를 기준으로 한다.
- metadata 크기 제한이 있는 indexer에서는 `source_refs` 전체를 별도 object store에 저장하고 `source_dedupe_key`나 `chunk_id`만 metadata에 둔다.
- confidential safe mode 산출물을 공유할 때는 path, filename, customer-specific identifier가 노출되지 않았는지 확인한다.

## SSD 검증 에이전트 연동 계약

SSD 검증 에이전트의 Secure RAG adapter는 `retrieval_chunks_rag.jsonl`을 기본 입력으로 삼고, 나머지 sidecar는 citation expansion, impact review, UI drilldown에 보존한다. `document.md` 단독 업로드는 fallback이며 권장 경로가 아니다.

Profile mapping:

| domain_adapter | SSD domain | SSD spec_type |
| --- | --- | --- |
| `nvme` | `HIL` | `NVMe` |
| `pcie` | `HIL` | `PCIe` |
| `ocp` | `HIL` | `OCP` |
| `tcg` | `HIL` | `TCG` |
| `spdm` | `HIL` | `SPDM` |

`TCG`와 `SPDM`은 first-class `spec_type`으로 취급한다. `CustomerRequirement + feature_name=TCG/SPDM` fallback은 사용하지 않는다.

RagChunk/RagCitation mapping:

| SSD field | pdf2md field |
| --- | --- |
| `RagChunk.chunk_id` | `chunk_id` |
| `RagChunk.text` | `text` |
| `RagCitation.document_id` | Secure RAG document id |
| `RagCitation.chunk_id` | `chunk_id` |
| `RagCitation.page_number` | `page_range[0]` |
| `RagCitation.section_title` | `section_path` |
| `RagCitation.heading_path` | `section_path` |
| `RagChunk.metadata` | `chunk_type`, `source_refs`, `semantic_types`, `normative_strength`, `retrieval_priority`, `source_dedupe_key`, `schema_version`, `source_sha256` |

Local validation:

```bash
python scripts/validate_ssd_rag_contract.py --output-dir output/nvme --ssd-agent-domain HIL --ssd-agent-spec-type NVMe --domain-adapter nvme
python scripts/validate_ssd_rag_contract.py --output-dir output/tcg --ssd-agent-domain HIL --ssd-agent-spec-type TCG --domain-adapter tcg
python scripts/validate_ssd_rag_contract.py --output-dir output/spdm --ssd-agent-domain HIL --ssd-agent-spec-type SPDM --domain-adapter spdm
python scripts/run_ssd_corpus_profile.py --profile local_ssd_corpus_profile.json --fail-on-error
python scripts/run_ssd_corpus_profile.py --profile local_ssd_corpus_profile.json --fail-on-error --evidence-pack
python scripts/analyze_corpus_evidence_pack.py --evidence-pack local_corpus_evidence_pack.json
python scripts/compare_corpus_evidence_packs.py --baseline old_evidence_pack.json --current local_corpus_evidence_pack.json --fail-on-new-signature
```

운영 profile에서는 `--rag-table-output jsonl|both`와 `--domain-adapter nvme|pcie|ocp|tcg|spdm|manual`를 필수로 지정한다. `--domain-adapter nvme` 검증은 NVMe Base와 NVM Command Set 모두에 대해 core NVMe domain unit, Command Set CDW/pointer/status taxonomy normalized fields, command relationship metadata, technical table provenance, stable metadata, `requirement_traceability_rag.jsonl` 존재 여부까지 확인한다. 원본 PDF와 raw output은 커밋하지 않고, 필요한 경우 `ssd_rag_contract_report.json`, sanitized summary, 또는 raw path/query text를 제거한 `local_corpus_evidence_pack.json`만 공유한다. 공유된 evidence pack은 `corpus_evidence_analysis_report.json`으로 hotspot/follow-up hint를 확인하고, `corpus_evidence_trend_report.json`으로 baseline/current signature trend를 비교한다.

## Azure AI Search

권장 index shape:

| Field | Type 예시 | 속성 |
| --- | --- | --- |
| `id` | `Edm.String` | key |
| `text` | `Edm.String` | searchable |
| `chunk_type` | `Edm.String` | filterable/facetable |
| `section_path` | `Edm.String` | searchable/filterable |
| `semantic_types` | `Collection(Edm.String)` | filterable |
| `page_start` | `Edm.Int32` | filterable/sortable |
| `page_end` | `Edm.Int32` | filterable |
| `retrieval_priority` | `Edm.Int32` | sortable |
| `token_estimate` | `Edm.Int32` | filterable |
| `source_refs_json` | `Edm.String` | retrievable |

운영 체크:

- `source_refs`는 JSON string으로 넣거나 별도 lookup table로 분리한다.
- requirement 중심 검색은 `chunk_type eq 'requirement' or chunk_type eq 'requirement_trace'` 필터를 우선 적용한다.
- register/bitfield 질의는 `chunk_type eq 'technical_table' or chunk_type eq 'domain_unit'` 필터가 유리하다.

## LangChain

권장 `Document` mapping:

```python
Document(
    page_content=record.get("embedding_text") or record["text"],
    metadata={
        "id": record["chunk_id"],
        "source_text": record["text"],
        "chunk_type": record["chunk_type"],
        "source_refs": record["source_refs"],
        "section_path": record["section_path"],
        "page_range": record["page_range"],
        "semantic_types": record["semantic_types"],
        "retrieval_priority": record["retrieval_priority"],
    },
)
```

운영 체크:

- `RecursiveCharacterTextSplitter`로 다시 쪼개지 않는 것을 기본으로 한다. 이미 PDF provenance 기준으로 chunk boundary가 잡혀 있다.
- re-ranking 단계에서 `retrieval_priority`, `chunk_type`, `semantic_types`를 feature로 사용할 수 있다.

## LlamaIndex

권장 node mapping:

```python
TextNode(
    id_=record["chunk_id"],
    text=record.get("embedding_text") or record["text"],
    metadata={
        "chunk_type": record["chunk_type"],
        "source_text": record["text"],
        "source_refs": record["source_refs"],
        "section_path": record["section_path"],
        "page_range": record["page_range"],
    },
)
```

운영 체크:

- Node relationship을 임의 생성하지 말고 `source_refs`와 `chunk_group_id`를 먼저 사용한다.
- table row와 technical table unit은 같은 `table_id`를 가진 record끼리 UI에서 묶어 보여주는 편이 안전하다.

## Requirement Change Impact

여러 버전의 spec corpus를 운영할 때:

```bash
python -m pdf2md --input-dir specs_v2 --previous-corpus-manifest specs_v1/output/corpus_manifest.json
```

생성물:

- `corpus_diff_report.json`: PDF 단위 added/changed/removed/unchanged
- `requirement_change_impact_report.json`: requirement trace 단위 added/changed/removed와 source_refs

AI Agent에 넘길 때는 `requirement_change_impact_report.json`의 `entries[]`만 컨텍스트로 넣고, 필요한 경우 `current_source_refs`로 원문 sidecar를 lookup한다.

## Calibration Gate

RAG smoke/eval fixture:

```json
{
  "queries": [
    {
      "query": "Which requirement controls reserved bits?",
      "expected_source_ids": ["req-trace-000002"],
      "expected_requirement_source_ids": ["req-trace-000002"],
      "expected_requirement_source_types": ["requirement_trace"]
    }
  ]
}
```

로컬 평가:

```bash
python scripts/run_rag_eval.py \
  --output-dir output \
  --eval-set rag_eval_queries.json \
  --top-k 5 \
  --min-requirement-coverage 0.9 \
  --min-table-field-coverage 0.85 \
  --min-cross-ref-resolved-coverage 0.8 \
  --min-relationship-target-coverage 1.0 \
  --chunk-token-target 512 \
  --min-chunk-size-compliance 0.95 \
  --min-source-ref-presence-coverage 1.0 \
  --max-chunk-token-p95 512 \
  --max-duplicate-source-ratio 0.0 \
  --max-conversion-duration-ms 10000 \
  --fail-on-threshold
```

Profile 파일을 쓰는 경우:

```bash
python scripts/run_rag_eval.py \
  --output-dir output \
  --eval-set rag_eval_queries.json \
  --calibration-profile docs/rag_calibration_profile.example.json \
  --fail-on-threshold
```

release gate에 포함:

```bash
python scripts/run_release_gates.py \
  --output-dir release_gate_output \
  --gates rag \
  --rag-output-dir output \
  --rag-eval-set rag_eval_queries.json \
  --rag-min-requirement-coverage 0.9 \
  --rag-min-table-field-coverage 0.85 \
  --rag-min-cross-ref-resolved-coverage 0.8 \
  --rag-min-relationship-target-coverage 1.0
```

실제 NVMe/PCIe/OCP/TCG/SPDM/customer-like corpus는 repo에 커밋하지 말고 로컬 profile과 sanitized eval fixture만 사용한다.

Eval fixture의 requirement coverage는 기본적으로 `requirement`, `requirement_trace` source type만 인정한다. Table-field coverage는 기본적으로 `table_row`, `technical_table_unit`, `domain_unit` source type만 인정한다. 다른 source type을 의도적으로 허용해야 할 때만 `expected_requirement_source_types` 또는 `expected_table_field_source_types`를 명시한다. Relationship metadata coverage는 `previous_chunk_id`, `next_chunk_id`, `section_anchor_chunk_id`, `related_chunk_ids`가 같은 `retrieval_chunks_rag.jsonl` 내부 final chunk id로 해소되는지 local-only로 계산한다.

## Confidential Safe Mode Metadata

공유 가능한 기본 metadata:

- `chunk_id`
- `chunk_type`
- `page_range`
- `section_path`
- `semantic_types`
- `retrieval_priority`
- `token_estimate`
- redacted `source_refs`

공유 전 검토가 필요한 metadata:

- 원본 `input_pdf` path
- customer/product codenames
- requirement text 자체
- absolute asset paths
- source hash와 local output path

`--confidential-safe-mode`는 public metadata의 path redaction을 돕지만, 원문 text를 자동 익명화하지 않는다. 고객 문서 공유는 별도 sanitized fixture를 만들어 검증한다.

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

## 공통 Field Mapping

| Index field | Source field | 비고 |
| --- | --- | --- |
| `id` | `chunk_id` | deterministic primary key |
| `text` | `text` | embedding 대상 원문 |
| `chunk_type` | `chunk_type` | `requirement`, `technical_table`, `table_row` 우선순위 조정에 사용 |
| `source_refs` | `source_refs` | citation/provenance 원본 |
| `page_start` | `page_range[0]` | page filter |
| `page_end` | `page_range[1]` | page filter |
| `section_path` | `section_path` | section filter/facet |
| `semantic_types` | `semantic_types` | requirement/table/domain unit 필터 |
| `retrieval_priority` | `retrieval_priority` | re-ranking hint |
| `token_estimate` | `token_estimate` | chunk budget diagnostics |
| `source_dedupe_key` | `source_dedupe_key` | duplicate guard |

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
- metadata 크기 제한이 있는 indexer에서는 `source_refs` 전체를 별도 object store에 저장하고 `source_dedupe_key`나 `chunk_id`만 metadata에 둔다.
- confidential safe mode 산출물을 공유할 때는 path, filename, customer-specific identifier가 노출되지 않았는지 확인한다.

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
    page_content=record["text"],
    metadata={
        "id": record["chunk_id"],
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
    text=record["text"],
    metadata={
        "chunk_type": record["chunk_type"],
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
      "expected_requirement_source_ids": ["req-trace-000002"]
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
  --max-chunk-token-p95 512 \
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
  --rag-min-cross-ref-resolved-coverage 0.8
```

실제 NVMe/PCIe/OCP/TCG/customer-like corpus는 repo에 커밋하지 말고 로컬 profile과 sanitized eval fixture만 사용한다.

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

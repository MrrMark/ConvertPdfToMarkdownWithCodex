# OCP SpecAnalysisAgent Handoff

이 문서는 `ssd-verification-agent`의 `SpecAnalysisAgent`가 OCP Datacenter NVMe SSD 산출물을 사용할 때 필요한 최소 handoff 계약을 정리한다.

## Source

- Spec family: `OCP`
- Spec title: `Datacenter NVMe SSD Specification`
- Expected version: `2.7`
- Expected date marker: `01082026`
- Official URL: `https://www.opencompute.org/documents/datacenter-nvme-ssd-specification-v2-7-final-pdf-1`

원본 PDF와 전체 변환 산출물은 repo에 커밋하지 않는다. 로컬 PDF는 repo 밖 `/tmp` 또는 private local path에 둔다.

## Conversion

```bash
python scripts/run_latest_ocp_datacenter_nvme_ssd_benchmark.py \
  --input-pdf /tmp/datacenter-nvme-ssd-specification-v2-7-final.pdf \
  --output-dir /tmp/pdf2md-latest-ocp-datacenter-nvme-ssd \
  --mode full_precision \
  --fail-on-contract-error \
  --fail-on-ocp-eval-error
```

## Required Sidecars

`SpecAnalysisAgent` ingest에는 아래 sidecar를 우선 사용한다.

- `retrieval_chunks_rag.jsonl`
- `domain_units_rag.jsonl`
- `requirement_traceability_rag.jsonl`
- `technical_tables_rag.jsonl`
- `tables_rag.jsonl`
- `cross_refs_rag.jsonl`
- `manifest.json`
- `report.json`

Sanitized 공유용 evidence는 다음 파일만 사용한다.

- `latest_ocp_datacenter_nvme_ssd_benchmark_report.json`
- `latest_ocp_datacenter_nvme_ssd_benchmark_scorecard.md`
- 필요 시 `ssd_rag_contract_report.json`

## Domain Fields

OCP requirement domain units는 `domain="ocp"`와 `unit_type="requirement"`를 사용한다.
Q125 이후 각 record는 `adapter_metadata`와 `cross_spec_compatibility`를 포함한다.

필수 adapter metadata:

- `adapter_metadata.registry_version`
- `adapter_metadata.adapter="ocp"`
- `adapter_metadata.ssd_agent_domain="HIL"`
- `adapter_metadata.ssd_agent_spec_type="OCP"`
- `adapter_metadata.unit_taxonomy=["requirement"]`
- `adapter_metadata.required_normalized_fields`
- `cross_spec_compatibility.compatibility_group`
- `cross_spec_compatibility.compatible_adapters`
- `cross_spec_compatibility.source_id_fields`

주요 normalized fields:

- `requirement_id`
- `requirement_prefix`
- `requirement_number`
- `requirement_family`
- `ocp_section_context`
- `normative_strength`
- `ssd_requirement_status`
- `related_command`
- `related_log_identifier`
- `related_feature_identifier`
- `related_statistic_identifier`
- `related_security_protocol`
- `related_form_factor`
- `source_table_id`
- `source_table_row_id`

Agent는 citation과 원문 확인을 위해 항상 `source_refs`, `page_range`, `bbox`, `source_sha256`, `source_dedupe_key`, `stable_source_id`, `stable_requirement_seed`, `adapter_metadata`, `cross_spec_compatibility`를 함께 보존해야 한다.

## Representative Questions

초기 품질 확인에는 아래 질문 유형을 사용한다.

- requirement ID lookup: `NVMe-IO-*`, `STD-LOG-*`, `SEC-*`, `TEL*`, `FF*`
- log page support: `related_log_identifier`
- feature behavior: `related_feature_identifier`
- telemetry statistic: `related_statistic_identifier`
- security compliance: `related_security_protocol`
- form-factor or thermal compliance: `related_form_factor`, `requirement_family=form_factor|thermal`

Benchmark report의 `ocp_eval`은 query/result 원문을 저장하지 않고 aggregate metric만 저장한다. 통과 기준은 required buckets 전체 coverage, `hit_at_k=1.0`, `expected_source_coverage=1.0`, `table_field_coverage=1.0`이다.

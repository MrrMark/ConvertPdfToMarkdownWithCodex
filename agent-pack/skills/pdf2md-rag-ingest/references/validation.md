# PDF2MD Validation

Run the smallest validation set that covers the user's request. Use broader gates before release or shared artifact delivery.

## Local Conversion Validation

```bash
python3 -m pdf2md --help
python3 -m pytest
python3 -m ruff check .
git diff --check
```

## Output Bundle Validation

For a converted output directory:

```bash
python3 scripts/validate_index_contract.py --output-dir output/spec --target all --fail-on-error
python3 scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python3 scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
```

For public schema drift checks after adding JSON outputs:

```bash
python3 scripts/export_output_schema.py --check
python3 -m pytest tests/test_output_schema_contract.py -q
```

For confidential/customer outputs:

```bash
python3 scripts/validate_index_contract.py \
  --output-dir output/spec \
  --target all \
  --confidential-safe \
  --fail-on-warning
```

## RAG Evaluation

Use an eval fixture only when the user has one or asks for retrieval-quality validation:

```bash
python3 scripts/run_rag_eval.py \
  --output-dir output/spec \
  --eval-set rag_eval_queries.json \
  --top-k 5 \
  --min-expected-source-coverage 0.9 \
  --fail-on-threshold
```

## SSD/Technical Contract Validation

```bash
python3 scripts/validate_ssd_rag_contract.py \
  --output-dir output/nvme \
  --ssd-agent-domain HIL \
  --ssd-agent-spec-type NVMe \
  --domain-adapter nvme
```

Use this validator for NVMe Base, NVM Command Set, OCP, PCIe, TCG, SPDM, customer
requirements, and manual domain adapter outputs before sharing a technical RAG
bundle. Report only status, counts, warning/error codes, and affected sidecar
names. Keep `adapter_metadata`, `cross_spec_compatibility`, `source_sha256`,
`source_dedupe_key`, `stable_source_id`, and `stable_requirement_seed` intact for
downstream reconciliation.

For `technical_spec_rag_visual`, also inspect sidecar counts for
`page_layout_rag.jsonl`, `figure_ocr_evidence_rag.jsonl`,
`figure_descriptions_rag.jsonl`, and `figure_structures_rag.jsonl`. If a visual
sidecar is absent, distinguish intentionally skipped outputs, such as
`--image-mode none` or minimal/fast sidecar scope, from unexpected omissions.

## Interrupted or Windowed Conversion Checks

- If `report.json` has `summary.interrupted=true`, inspect `interrupted_report.json` and `conversion_state.json`.
- Preserve existing partial artifacts unless the user explicitly asks to remove them.
- For page-window conversion, inspect `page_window_merge_report.json` and validator summaries before reading full sidecars.
- Re-run only failed window directories when possible.

## Troubleshooting

- `python` not found: use `python3`, `.venv311/bin/python`, or `.venv314/bin/python`.
- OCR missing: run `scripts/check_ocr_runtime.py`; install Tesseract/language data outside the conversion path.
- Low OCR confidence: keep warning visible; do not silently correct OCR text.
- Missing sidecars: inspect `manifest.options.rag_sidecar_scope` and `report.summary.rag_sidecar_omitted_outputs`.
- Table quality warnings: prefer HTML fallback; do not force Markdown unless the user accepts structure loss.
- Assetless RAG requested: use placeholder images plus `--rag-figure-text-chunks`.
- Text-first large spec ingest requested: use `--image-mode none` and document that visual sidecars are intentionally skipped.

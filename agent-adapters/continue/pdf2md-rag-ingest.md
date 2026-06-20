---
name: PDF2MD RAG Ingest
---

Use the canonical Agent Skill at `agent-pack/skills/pdf2md-rag-ingest/SKILL.md` when converting PDFs, generating RAG sidecars, validating pdf2md outputs, checking OCR readiness, or inspecting report/manifest warnings.
For sidecar details, use `agent-pack/skills/pdf2md-rag-ingest/references/artifacts.md`
and `references/validation.md`; do not duplicate the full output contract in
this rule.

Rules:

- Preserve PDF text exactly; do not summarize, paraphrase, correct, or invent source text.
- Use `--table-mode auto` by default; keep complex tables as HTML fallback.
- Use referenced images by default; use placeholder plus `--rag-figure-text-chunks` only for assetless RAG.
- Use `--image-mode none` only for intentional text/table/domain ingest where visual evidence is out of scope.
- Keep warnings visible in `report.json`.
- If conversion is interrupted, inspect `conversion_state.json`, `interrupted_report.json`, and `report.json` before rerunning or deleting artifacts.
- Use `--confidential-safe-mode` or `--rag-profile confidential_rag` for sensitive documents.

Common commands:

```bash
python3 -m pdf2md input.pdf -o output/input
python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag --domain-adapter nvme --rag-table-output jsonl
python3 -m pdf2md nvme-base.pdf -o output/nvme-base --rag-profile technical_spec_rag --domain-adapter nvme --image-mode none
python3 scripts/validate_index_contract.py --output-dir output/spec --target all --fail-on-error
python3 scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python3 scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
```

For MCP clients, use `pdf2md_convert_pdf_windowed` or the explicit page-window sequence for very large PDFs.

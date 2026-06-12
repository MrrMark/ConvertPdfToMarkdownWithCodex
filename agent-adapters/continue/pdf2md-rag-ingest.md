---
name: PDF2MD RAG Ingest
---

Use the canonical Agent Skill at `agent-pack/skills/pdf2md-rag-ingest/SKILL.md` when converting PDFs, generating RAG sidecars, validating pdf2md outputs, checking OCR readiness, or inspecting report/manifest warnings.

Rules:

- Preserve PDF text exactly; do not summarize, paraphrase, correct, or invent source text.
- Use `--table-mode auto` by default; keep complex tables as HTML fallback.
- Use referenced images by default; use placeholder plus `--rag-figure-text-chunks` only for assetless RAG.
- Keep warnings visible in `report.json`.
- Use `--confidential-safe-mode` or `--rag-profile confidential_rag` for sensitive documents.

Common commands:

```bash
python3 -m pdf2md input.pdf -o output/input
python3 -m pdf2md spec.pdf -o output/spec --rag-profile technical_spec_rag --domain-adapter nvme --rag-table-output jsonl
python3 scripts/validate_index_contract.py --output-dir output/spec --target all --fail-on-error
python3 scripts/validate_provenance_integrity.py --output-dir output/spec --fail-on-error
python3 scripts/validate_artifact_integrity.py --output-dir output/spec --fail-on-error
```

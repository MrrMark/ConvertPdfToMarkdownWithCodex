---
name: pdf2md-rag-ingest
description: Convert PDF files into deterministic Markdown and RAG-ready sidecars with pdf2md. Use when the user asks to convert PDFs, batch process PDF folders, prepare technical specifications for RAG or indexing, validate pdf2md outputs, inspect manifest/report warnings, run OCR readiness checks, or create requirement/corpus diff artifacts.
compatibility: Agent Skills compatible clients. Requires Python 3.11+, this pdf2md project or an installed pdf2md package, and Tesseract only when OCR is needed.
---

# PDF2MD RAG Ingest

Use the local `pdf2md` converter as the source of truth. Do not rewrite the converter logic inside the agent.

## Non-Negotiable Rules

- Preserve extracted text. Do not summarize, paraphrase, correct, or invent PDF text.
- Preserve tables as tables. Use `auto` by default; complex tables must remain HTML fallback instead of unsafe GFM.
- Keep images referenced by default. Use placeholder mode only when an RAG target cannot ingest image files.
- Treat OCR as evidence with confidence, not certainty. Low confidence must remain visible in `report.json`.
- Prefer partial success. Do not discard an output bundle because one page, table, image, or OCR step warned.
- For confidential/customer PDFs, use `--confidential-safe-mode` or `--rag-profile confidential_rag`.

## Quick Workflow

1. Locate the project root or installed package.
2. Select a Python runner: prefer `.venv311/bin/python`, then `.venv314/bin/python`, then `python3`.
3. Run a doctor check before OCR-heavy work:
   `python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py doctor --ocr-lang kor+eng`
4. Choose the workflow from [workflows](references/workflows.md).
5. Convert the PDF or folder.
6. Validate artifacts with [validation](references/validation.md).
7. Report only paths, status, warning codes, counts, and validation results unless the user asks to inspect content.

## Common Commands

Single PDF, preservation first:

```bash
python3 -m pdf2md input.pdf -o output/input
```

Technical spec RAG with domain sidecars:

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --rag-table-output jsonl
```

For NVMe Base or NVM Command Set PDFs, use `--domain-adapter nvme` and report only sidecar counts plus validation status.

Assetless technical RAG:

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag \
  --domain-adapter nvme \
  --image-mode placeholder \
  --rag-figure-text-chunks
```

Batch conversion:

```bash
python3 -m pdf2md --input-dir ./pdfs --skip-existing
```

Use the bundled runner when a client benefits from a smaller command surface:

```bash
python3 agent-pack/skills/pdf2md-rag-ingest/scripts/pdf2md_agent_runner.py convert spec.pdf \
  --workflow technical-rag \
  --domain-adapter nvme \
  --output-dir output/spec
```

## References

- Workflow/profile selection: [references/workflows.md](references/workflows.md)
- Output artifact map: [references/artifacts.md](references/artifacts.md)
- Validation and troubleshooting: [references/validation.md](references/validation.md)
- Cross-agent adapter notes: [references/adapters.md](references/adapters.md)

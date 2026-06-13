# Changelog

All notable project changes are tracked through PRs and this changelog. The project still keeps detailed
quality-improvement implementation notes in `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`.

## Unreleased

- Add a local stdio MCP server entry point with pdf2md conversion, profile discovery, output validation, report inspection, and Streamable HTTP follow-up specification.
- Add a portable AI agent skill/rule pack for pdf2md RAG ingest workflows across Agent Skills-compatible clients and rule-based coding assistants.
- Fix wheel packaging so nested OCR backend adapters are included and covered by the wheel contract inspector.
- Add Q107 development spec for opt-in assetless figure visual semantics, covering region OCR, generated figure descriptions, and figure structure sidecars.
- Add GUI `이미지 업로드 불가 RAG 대응` preset and manual domain adapter inputs for customer requirement table headers.
- Add Docling-informed OCR/layout extension design, keeping new backend, region OCR, and picture-description work gated on Docling-installed benchmark evidence.
- Add local-only Docling comparison harness outputs with sanitized benchmark, artifact comparison, scorecard, and schema contracts.
- Add opt-in assetless `figure_text` retrieval chunks for placeholder image mode in RAG environments that cannot ingest image files.
- Add opt-in fast output profile and RAG sidecar scope controls while preserving the default full output contract.
- Add adaptive table strategy skipping when the default candidate meets conservative quality thresholds.
- Add bounded OCR page chunk workers, reusing effective page worker count while preserving deterministic warning and page merge order.
- Add chunked page worker execution so parallel conversion opens the PDF once per worker chunk instead of once per page.
- Add lazy/context-first structure marker OCR so context-resolvable markers avoid Tesseract calls while unresolved markers keep the existing OCR fallback.
- Add conservative ruff lint smoke configuration for Python 3.11+.
- Add `pdf2md/py.typed` packaging contract and wheel inspection coverage.
- Add advisory dependency audit release gate support.

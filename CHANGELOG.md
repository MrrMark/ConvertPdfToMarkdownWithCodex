# Changelog

All notable project changes are tracked through PRs and this changelog. The project still keeps detailed
quality-improvement implementation notes in `docs/QUALITY_IMPROVEMENT_IMPLEMENTED_SPECS.md`.

## Unreleased

- Add chunked page worker execution so parallel conversion opens the PDF once per worker chunk instead of once per page.
- Add lazy/context-first structure marker OCR so context-resolvable markers avoid Tesseract calls while unresolved markers keep the existing OCR fallback.
- Add conservative ruff lint smoke configuration for Python 3.11+.
- Add `pdf2md/py.typed` packaging contract and wheel inspection coverage.
- Add advisory dependency audit release gate support.

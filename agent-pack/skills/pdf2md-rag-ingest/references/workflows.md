# PDF2MD Workflow Selection

Choose conservative defaults. If a request is ambiguous, prefer source preservation over aggressive cleanup.

## Profiles

| User intent | Recommended command options |
| --- | --- |
| Basic Markdown conversion | `--rag-profile preserve` or no profile override |
| General RAG ingest | `--rag-profile rag_optimized` |
| Technical specification RAG | `--rag-profile technical_spec_rag --domain-adapter <adapter>` |
| Technical specification RAG with visual sidecars | `--rag-profile technical_spec_rag_visual --domain-adapter <adapter>` |
| Confidential/customer evidence pack | `--rag-profile confidential_rag` |
| Preserve Markdown while emitting sidecars | `--rag-profile preserve_with_sidecars` |
| Image upload is not supported by target RAG | `--rag-profile technical_spec_rag_visual --image-mode placeholder` |
| Fast core artifact generation | `--output-profile fast` |

## Domain Adapters

Use a domain adapter only when the source document matches that domain or the user explicitly asks for it.

Supported adapters:

- `nvme`
- `pcie`
- `ocp`
- `tcg`
- `spdm`
- `customer-requirements`
- `manual`

For `manual`, require observed customer requirement headers or explicit user-provided keywords:

```bash
python3 -m pdf2md customer.pdf -o output/customer \
  --rag-profile technical_spec_rag \
  --domain-adapter manual \
  --manual-domain-adapter-label "Customer Requirements" \
  --manual-domain-adapter-keywords "Customer Key, Customer Requirement"
```

## OCR

Before OCR-heavy conversion:

```bash
python3 scripts/check_ocr_runtime.py --ocr-lang kor+eng
python3 scripts/probe_ocr_backends.py --ocr-lang kor+eng --backends all --json
```

Only force OCR when the user requests it or the PDF has little/no text layer:

```bash
python3 -m pdf2md scan.pdf -o output/scan --force-ocr --ocr-lang kor+eng --ocr-backend tesseract
```

## Batch and Corpus Diff

Batch conversion:

```bash
python3 -m pdf2md --input-dir ./pdfs --skip-existing
```

Incremental corpus comparison:

```bash
python3 -m pdf2md --input-dir ./pdfs_v2 \
  --previous-corpus-manifest ./pdfs_v1/output/corpus_manifest.json \
  --reuse-unchanged
```

Requirement impact review pack:

```bash
python3 scripts/build_requirement_impact_review_pack.py \
  --impact-report ./pdfs_v2/output/requirement_change_impact_report.json
```

# Technical Visual RAG Output Guide

`technical_spec_rag_visual` converts a technical specification PDF into Markdown plus RAG sidecar files. This guide describes full sidecar output with the default `referenced` image mode.

Example:

```bash
python3 -m pdf2md spec.pdf -o output/spec \
  --rag-profile technical_spec_rag_visual \
  --domain-adapter nvme
```

Each JSONL file contains one independent JSON record per line. Use each record's `source_refs`, page number, bounding box (`bbox`), and input PDF hash for source citation and provenance.

## Core output

| File or path | Purpose |
| --- | --- |
| `document.md` | The final human-readable Markdown document. It contains extracted text, tables, relative image references, and optional page markers. |
| `assets/images/page-0001-figure-001.*` | An extracted image asset from the PDF. The filename is determined by the page number and figure sequence within that page. |
| `manifest.json` | Metadata about the input document, effective options, generated assets, and sidecars. Use it to connect outputs and support repeatable processing. |
| `report.json` | Conversion status, warnings, partially failed pages, record counts, and quality diagnostics. This is the primary file for reviewing a conversion. |
| `conversion_state.json` | The current or completed conversion stage, completed and failed pages, and written artifacts. Use it for triage and reruns after interruption. |

## RAG retrieval and source evidence

| File | Purpose |
| --- | --- |
| `retrieval_chunks_rag.jsonl` | The primary input for RAG indexing. It organizes text, tables, requirements, and figure-related information into retrieval units while preserving source evidence, context, and chunk relationships. It does not store embedding vectors. |
| `text_blocks_rag.jsonl` | Source text blocks for headings, paragraphs, lists, code, footnotes, and captions, with page, bounding box, and heading-path metadata. Use it to verify retrieved source text. |
| `semantic_units_rag.jsonl` | Conservative classification of source blocks as sections, requirements, definitions, parameters, procedures, notes, warnings, or references. Use it for type-aware retrieval and filtering. |
| `requirements_rag.jsonl` | The requirement subset of `semantic_units_rag.jsonl`. It provides normative strength and stable source identity fields. |
| `requirement_traceability_rag.jsonl` | Requirement IDs, conditions, applicability, exceptions, dependencies, linked table rows, and verification intent. Use it for requirement traceability and verification planning. |
| `cross_refs_rag.jsonl` | Internal references to sections, tables, figures, appendices, and their resolution results. It also records why unresolved references could not be linked. |

## Tables and domain-specific structure

| File | Purpose |
| --- | --- |
| `tables_rag.jsonl` | Table rows, cells, header lineage, and source positions. Use it for table retrieval and row-level provenance. |
| `rag_tables.md` | Extracted tables serialized as standalone Markdown. Use it for table-focused review or Markdown-based RAG inputs. |
| `technical_tables_rag.jsonl` | Structured technical table rows, such as opcodes, registers, bit fields, status codes, and command fields. Use it for precise technical-specification retrieval and field analysis. |
| `domain_units_rag.jsonl` | Domain units identified by the selected adapter, such as NVMe, PCIe, OCP, TCG, SPDM, or Caliptra. This file is produced only when `--domain-adapter` is specified. |

## Page and figure analysis

| File | Purpose |
| --- | --- |
| `page_layout_rag.jsonl` | Per-page reading order, multi-column detection, text/table/figure regions, and caption links. Use it for layout-based quality diagnostics and provenance. |
| `figures_rag.jsonl` | Figure IDs, paths, page locations, bounding boxes, captions, detected labels, and nearby text references. This is the primary record for figure retrieval and image-asset linkage. |
| `figure_ocr_evidence_rag.jsonl` | OCR text, confidence, and accept/reject reasons for figure and table regions. It is evidence for review and does not alter source text in `document.md`. |
| `figure_descriptions_rag.jsonl` | Figure retrieval helper descriptions built from captions, labels, nearby text, and OCR evidence. Records include generated-text and review-required indicators. |
| `figure_structures_rag.jsonl` | Observed labels, nodes, signals, and relationship hints for diagrams. Use it as a retrieval and human-review aid. |

Figure descriptions and structure records are never inserted into the Markdown body. The current implementation uses observable evidence such as captions, labels, nearby text, and OCR; it does not represent the output as pixel-level image interpretation. These sidecars assist retrieval and review and do not replace the original figure.

## Conditional output and generation conditions

| File or path | Generation condition and purpose |
| --- | --- |
| `interrupted_report.json` | Written when conversion is interrupted by `KeyboardInterrupt` or a fatal exception. It records the interruption point, failure reason, remaining artifacts, and resume guidance. |
| `sanitized_report.json` | Written with `--confidential-safe-mode`. This is a shareable sanitized report that reduces exposure of sensitive paths and input-identifying information. |
| `debug/page-0001-raw-lines.json` | Written with `--debug`. Contains raw extracted text lines and page metadata. |
| `debug/page-0001-ordered-lines.json` | Written with `--debug`. Contains text lines after reading-order processing. |
| `debug/page-0001-normalized-lines.json` | Written with `--debug`. Contains text lines after safe normalization. |
| `debug/page-0001-table-candidates.json` | Written with `--debug`. Contains table-detection candidates and diagnostics. |
| `debug/page-0001-image-candidates.json` | Written with `--debug`. Contains figure-detection candidates and diagnostics. |
| `debug/table-quality-review-pack.json` | Written when table-quality review data is available. Contains diagnostic material for table review. |

With `image_mode=placeholder`, the converter does not write physical files under `assets/images/`; it writes image placeholders in Markdown and preserves figure RAG sidecars where possible. With `image_mode=none`, image extraction and figure-sidecar features can be omitted. If the document has no applicable figures, tables, or requirements, the related JSONL file may be empty or may not be produced.

For the exact field contracts, see [OUTPUT_SCHEMA.md](OUTPUT_SCHEMA.md). For profile options, see [rag_profiles.py](../pdf2md/rag_profiles.py).

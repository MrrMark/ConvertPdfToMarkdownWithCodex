"""Evaluate a reviewed bilingual source set without changing the legacy lexical gate."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pdf2md.bm25 import BM25Index
from scripts.run_rag_eval import retrieve as lexical_retrieve


def ref_key(ref: dict) -> tuple:
    """Match source identity and page, never an ID without its source type."""
    return ref["source_type"], ref["source_id"], ref["page"]


def has_bbox(ref: dict) -> bool:
    """Require a finite nonempty rectangle for citation metadata coverage."""
    bbox = ref.get("bbox")
    return (isinstance(bbox, (list, tuple)) and len(bbox) == 4
            and all(isinstance(v, (int, float)) and math.isfinite(v) for v in bbox)
            and bbox[0] < bbox[2] and bbox[1] < bbox[3])


def evaluate(chunks: list[dict], dataset: dict) -> dict:
    """Report macro recall/MRR and relevant citation/token preservation at five."""
    queries = dataset["queries"]
    if len(queries) != 30 or Counter(q["language"] for q in queries) != {"ko": 15, "en": 15}:
        raise ValueError("Exactly 15 Korean and 15 English queries are required")
    if len({q["query_id"] for q in queries}) != 30:
        raise ValueError("Query IDs must be unique")
    for q in queries:
        if not q["query"].strip() or not q["expected_refs"] or not q["critical_tokens"]:
            raise ValueError("Queries require text, source references and critical tokens")
        for ref in q["expected_refs"]:
            if ref["source_type"] not in {"requirement", "table_row", "figure"} or not ref["source_id"] or ref["page"] < 1:
                raise ValueError("Invalid source reference")
    index = BM25Index(chunks)
    rows = []
    for method in ("lexical", "bm25"):
        for q in queries:
            retrieved = index.retrieve(q["query"]) if method == "bm25" else lexical_retrieve(q["query"], chunks, top_k=5)
            expected = {ref_key(ref) for ref in q["expected_refs"]}
            covered, cited, preserved = set(), set(), set()
            first = None
            for rank, chunk in enumerate(retrieved, 1):
                refs = chunk.get("source_refs") or []
                matched = {ref_key(ref) for ref in refs if all(k in ref for k in ("source_type", "source_id", "page"))} & expected
                if matched:
                    first = first or rank
                    covered.update(matched)
                    cited.update(ref_key(ref) for ref in refs
                                 if all(k in ref for k in ("source_type", "source_id", "page"))
                                 and has_bbox(ref) and ref_key(ref) in matched)
                    text = unicodedata.normalize("NFC", str(chunk.get("text") or ""))
                    preserved.update(token for token in q["critical_tokens"] if unicodedata.normalize("NFC", token) in text)
            rows.append({
                "query_id": q["query_id"], "language": q["language"], "method": method,
                "recall_at_5": len(covered) / len(expected), "mrr_at_5": 1 / first if first else 0,
                "citation_coverage_at_5": len(cited) / len(expected),
                "critical_token_preservation_at_5": len(preserved) / len(set(q["critical_tokens"])),
                "retrieved_chunk_ids": [chunk["chunk_id"] for chunk in retrieved],
            })
    metrics = {}
    for method in ("lexical", "bm25"):
        metrics[method] = {}
        for language in ("ko", "en", "all"):
            group = [row for row in rows if row["method"] == method and (language == "all" or row["language"] == language)]
            metrics[method][language] = {key: sum(row[key] for row in group) / len(group) for key in (
                "recall_at_5", "mrr_at_5", "citation_coverage_at_5", "critical_token_preservation_at_5")}
    reviewed = dataset.get("review", {}).get("status") == "human_reviewed" and bool(dataset["review"].get("reviewer"))
    return {"schema_version": "1.0", "top_k": 5, "query_count": 30, "human_review_complete": reviewed,
            "review_gate_passed": bool(reviewed), "quality_thresholds": "not_configured", "metrics": metrics, "results": rows,
            "scope": "local lexical/BM25; citation metadata coverage, not answer faithfulness",
            "parameters": {"k1": 1.2, "b": 0.75, "tokenizer": "unicode_identifier_hangul_bigram_v1"}}


def main() -> int:
    """Write provisional results too, returning 2 until human review is recorded."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--eval-set", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if args.report.resolve() in {args.chunks.resolve(), args.eval_set.resolve()}:
        parser.error("report must not overwrite input")
    chunk_bytes, query_bytes = args.chunks.read_bytes(), args.eval_set.read_bytes()
    dataset = json.loads(query_bytes)
    chunk_hash = hashlib.sha256(chunk_bytes).hexdigest()
    if dataset["chunks_sha256"] != chunk_hash:
        raise ValueError("Retrieval corpus hash mismatch")
    report = evaluate([json.loads(line) for line in chunk_bytes.decode().splitlines() if line.strip()], dataset)
    report.update(chunks_sha256=chunk_hash, eval_set_sha256=hashlib.sha256(query_bytes).hexdigest())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if report["review_gate_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

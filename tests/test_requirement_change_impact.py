from __future__ import annotations

import json
from pathlib import Path

from pdf2md.batch_runner import build_requirement_change_impact_report
from pdf2md.models import CorpusManifest
from scripts.build_requirement_impact_review_pack import build_review_pack, main as review_pack_main, render_markdown


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def _trace(trace_id: str, requirement_id: str, text: str, source_id: str) -> dict:
    return {
        "trace_id": trace_id,
        "trace_index": int(trace_id.rsplit("-", 1)[1]),
        "requirement_id": requirement_id,
        "normative_strength": "required",
        "text": text,
        "testability_hint": "conformance_check",
        "source_refs": [{"source_type": "requirement_trace", "source_id": source_id, "page": 1}],
    }


def test_requirement_change_impact_report_tracks_added_changed_removed_and_sources(tmp_path: Path) -> None:
    previous_sidecar = tmp_path / "previous" / "spec" / "requirement_traceability_rag.jsonl"
    current_sidecar = tmp_path / "current" / "spec" / "requirement_traceability_rag.jsonl"
    _write_jsonl(
        previous_sidecar,
        [
            _trace("req-trace-000001", "REQ-1", "REQ-1 shall return GOOD.", "prev-req-1"),
            _trace("req-trace-000002", "REQ-2", "REQ-2 shall be removed.", "prev-req-2"),
            _trace("req-trace-000003", "REQ-4", "REQ-4 shall remain.", "same-req-4"),
        ],
    )
    _write_jsonl(
        current_sidecar,
        [
            _trace("req-trace-000001", "REQ-1", "REQ-1 shall return BETTER.", "current-req-1"),
            _trace("req-trace-000002", "REQ-3", "REQ-3 shall be added.", "current-req-3"),
            _trace("req-trace-000003", "REQ-4", "REQ-4 shall remain.", "same-req-4"),
        ],
    )
    previous_manifest = tmp_path / "previous_corpus_manifest.json"
    previous_manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "purpose": "rag_corpus_ingest",
                "input_dir": str(tmp_path / "previous"),
                "output_dir": str(tmp_path / "previous"),
                "documents": [
                    {
                        "doc_id": "spec",
                        "input_pdf": str(tmp_path / "previous" / "spec.pdf"),
                        "source_sha256": "0" * 64,
                        "output_dir": str(previous_sidecar.parent),
                        "status": "success",
                        "selected_pages": [1],
                        "skipped": False,
                        "files": {"requirement_traceability_rag": str(previous_sidecar)},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    current_manifest_path = tmp_path / "current" / "corpus_manifest.json"
    current_manifest = CorpusManifest.model_validate(
        {
            "schema_version": "1.0",
            "purpose": "rag_corpus_ingest",
            "input_dir": str(tmp_path / "current"),
            "output_dir": str(tmp_path / "current"),
            "documents": [
                {
                    "doc_id": "spec",
                    "input_pdf": str(tmp_path / "current" / "spec.pdf"),
                    "source_sha256": "1" * 64,
                    "output_dir": str(current_sidecar.parent),
                    "status": "success",
                    "selected_pages": [1],
                    "skipped": False,
                    "files": {"requirement_traceability_rag": str(current_sidecar)},
                }
            ],
        }
    )

    report = build_requirement_change_impact_report(
        previous_manifest_path=previous_manifest,
        current_manifest_path=current_manifest_path,
        current_manifest=current_manifest,
    )

    assert report.summary.changed_count == 1
    assert report.summary.removed_count == 1
    assert report.summary.added_count == 1
    assert report.summary.unchanged_count == 1
    assert report.summary.documents_with_requirement_changes == 1
    by_requirement = {entry.requirement_id: entry for entry in report.entries}
    assert by_requirement["REQ-1"].status == "changed"
    assert by_requirement["REQ-1"].changed_fields == ["texts", "source_refs"]
    assert by_requirement["REQ-1"].previous_source_refs[0]["source_id"] == "prev-req-1"
    assert by_requirement["REQ-1"].current_source_refs[0]["source_id"] == "current-req-1"
    assert by_requirement["REQ-2"].status == "removed"
    assert by_requirement["REQ-3"].status == "added"


def test_requirement_impact_review_pack_builds_json_and_markdown(tmp_path: Path) -> None:
    impact_report = {
        "schema_version": "1.0",
        "purpose": "rag_requirement_change_impact",
        "previous_manifest": "previous/corpus_manifest.json",
        "current_manifest": "current/corpus_manifest.json",
        "summary": {"changed_count": 1, "removed_count": 0, "added_count": 1, "unchanged_count": 3},
        "entries": [
            {
                "doc_id": "spec",
                "requirement_key": "REQ-1",
                "requirement_id": "REQ-1",
                "status": "changed",
                "changed_fields": ["texts", "source_refs"],
                "previous_trace_ids": ["req-trace-000001"],
                "current_trace_ids": ["req-trace-000001"],
                "previous_texts": ["REQ-1 shall return GOOD."],
                "current_texts": ["REQ-1 shall return BETTER."],
                "previous_source_refs": [{"source_id": "prev-req-1", "page": 1}],
                "current_source_refs": [{"source_id": "current-req-1", "page": 2}],
            },
            {
                "doc_id": "spec",
                "requirement_key": "REQ-2",
                "requirement_id": "REQ-2",
                "status": "added",
                "changed_fields": ["texts", "source_refs"],
                "previous_texts": [],
                "current_texts": ["REQ-2 shall be added."],
                "previous_source_refs": [],
                "current_source_refs": [{"source_id": "current-req-2", "page": 3}],
            },
        ],
    }

    pack = build_review_pack(impact_report, source_report="requirement_change_impact_report.json")
    markdown = render_markdown(pack)

    assert pack["summary"]["total_review_items"] == 2
    assert pack["summary"]["status_counts"] == {"added": 1, "changed": 1, "removed": 0}
    assert pack["review_items"][0]["recommendation"] == "review_test_logic_and_expected_results"
    assert pack["review_items"][0]["current_pages"] == [2]
    assert "REQ-1 shall return BETTER." in markdown

    impact_path = tmp_path / "requirement_change_impact_report.json"
    impact_path.write_text(json.dumps(impact_report), encoding="utf-8")
    output_dir = tmp_path / "pack"
    assert review_pack_main(["--impact-report", str(impact_path), "--output-dir", str(output_dir)]) == 0
    assert (output_dir / "requirement_impact_review_pack.json").exists()
    assert (output_dir / "requirement_impact_review_pack.md").exists()

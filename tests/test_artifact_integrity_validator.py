from __future__ import annotations

import json
from pathlib import Path

from scripts import validate_artifact_integrity


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _write_valid_output(output_dir: Path) -> None:
    image_dir = output_dir / "assets" / "images"
    image_dir.mkdir(parents=True)
    (image_dir / "page-0001-figure-001.png").write_bytes(b"png")
    (output_dir / "document.md").write_text(
        "![Figure](./assets/images/page-0001-figure-001.png)\n",
        encoding="utf-8",
    )
    _write_json(
        output_dir / "manifest.json",
        {
            "schema_version": "1.0",
            "images": [{"path": "assets/images/page-0001-figure-001.png"}],
            "tables": [],
        },
    )
    _write_json(
        output_dir / "report.json",
        {
            "schema_version": "1.0",
            "summary": {
                "figure_rag_record_count": 1,
                "retrieval_chunk_record_count": 0,
                "table_total": 0,
            },
        },
    )
    _write_jsonl(
        output_dir / "figures_rag.jsonl",
        [
            {
                "figure_id": "page-0001-figure-0001",
                "path": "assets/images/page-0001-figure-001.png",
            }
        ],
    )
    _write_jsonl(output_dir / "retrieval_chunks_rag.jsonl", [])


def test_artifact_integrity_accepts_consistent_single_output(tmp_path: Path) -> None:
    _write_valid_output(tmp_path)

    report = validate_artifact_integrity.validate_artifact_integrity(output_dir=tmp_path)

    assert report["passed"] is True
    assert report["summary"]["checked_links"] == 1
    assert report["summary"]["checked_assets"] == 2
    assert report["findings"] == []


def test_artifact_integrity_reports_missing_links_and_count_mismatches(tmp_path: Path) -> None:
    _write_valid_output(tmp_path)
    (tmp_path / "assets" / "images" / "page-0001-figure-001.png").unlink()
    (tmp_path / "assets" / "images" / "orphan.png").write_bytes(b"orphan")
    report_payload = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    report_payload["summary"]["figure_rag_record_count"] = 2
    _write_json(tmp_path / "report.json", report_payload)

    report = validate_artifact_integrity.validate_artifact_integrity(output_dir=tmp_path)

    codes = [finding["code"] for finding in report["findings"]]
    assert report["passed"] is False
    assert "missing_markdown_image_asset" in codes
    assert "missing_manifest_image_asset" in codes
    assert "missing_figure_asset" in codes
    assert "sidecar_record_count_mismatch" in codes
    assert "orphan_image_asset" in codes
    assert report["summary"]["missing_assets"] == 3
    assert report["summary"]["sidecar_count_mismatches"] == 1


def test_artifact_integrity_checks_batch_and_corpus_file_maps(tmp_path: Path) -> None:
    _write_valid_output(tmp_path)
    _write_json(
        tmp_path / "batch_report.json",
        {
            "schema_version": "1.0",
            "documents": [
                {
                    "output_dir": str(tmp_path / "doc"),
                    "files": {
                        "markdown": str(tmp_path / "document.md"),
                        "report": str(tmp_path / "missing_report.json"),
                    },
                }
            ],
        },
    )
    _write_json(
        tmp_path / "corpus_manifest.json",
        {
            "schema_version": "1.0",
            "purpose": "rag_corpus_ingest",
            "documents": [
                {
                    "doc_id": "doc",
                    "output_dir": str(tmp_path),
                    "files": {"manifest": "manifest.json"},
                }
            ],
        },
    )

    report = validate_artifact_integrity.validate_artifact_integrity(output_dir=tmp_path, confidential_safe=True)

    codes = [finding["code"] for finding in report["findings"]]
    assert "confidential_absolute_path" in codes
    assert "missing_file_map_path" in codes
    assert report["summary"]["file_map_missing_count"] == 1


def test_artifact_integrity_main_writes_report_and_honors_fail_on_error(tmp_path: Path) -> None:
    _write_valid_output(tmp_path)
    (tmp_path / "assets" / "images" / "page-0001-figure-001.png").unlink()
    report_path = tmp_path / "artifact_integrity_report.json"

    exit_code = validate_artifact_integrity.main(
        [
            "--output-dir",
            str(tmp_path),
            "--report-file",
            str(report_path),
            "--fail-on-error",
        ]
    )

    assert exit_code == 1
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["purpose"] == "output_artifact_integrity_validation"
    assert payload["summary"]["error_count"] >= 1

from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_visual_sidecar_contract import (
    REPORT_FILENAME,
    main as visual_sidecar_main,
    validate_visual_sidecar_contract,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def _figure_source_ref(figure_id: str = "figure-0001") -> dict:
    return {"source_type": "figure", "source_id": figure_id, "page": 1, "bbox": [10, 20, 30, 40]}


def _write_valid_visual_bundle(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "manifest.json", {"options": {"rag_profile": "technical_spec_rag_visual"}})
    _write_json(output_dir / "report.json", {"summary": {"warning_count": 0}})
    _write_jsonl(
        output_dir / "figures_rag.jsonl",
        [{"figure_id": "figure-0001", "page": 1, "bbox": [10, 20, 30, 40], "caption": "Confidential label"}],
    )
    _write_jsonl(
        output_dir / "page_layout_rag.jsonl",
        [
            {
                "layout_id": "layout-page-0001",
                "page": 1,
                "region_refs": [_figure_source_ref()],
                "region_ref_count": 1,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_ocr_evidence_rag.jsonl",
        [
            {
                "evidence_id": "ocr-0001",
                "target_type": "figure",
                "target_id": "figure-0001",
                "source_refs": [_figure_source_ref()],
                "text_replaced": False,
                "markdown_inserted": False,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "description-0001",
                "figure_id": "figure-0001",
                "source_refs": [_figure_source_ref()],
                "generated_text": True,
                "generated_content_scope": "sidecar_only",
                "markdown_inserted": False,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_structures_rag.jsonl",
        [
            {
                "structure_id": "structure-0001",
                "figure_id": "figure-0001",
                "source_refs": [_figure_source_ref()],
                "generated_text": False,
            }
        ],
    )


def test_validate_visual_sidecar_contract_accepts_linked_bundle(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    _write_valid_visual_bundle(output_dir)

    report = validate_visual_sidecar_contract(output_dir, require_visual_sidecars=True)

    assert report["passed"] is True
    assert report["summary"]["visual_sidecar_file_count"] == 5
    assert report["summary"]["figure_record_count"] == 1
    assert report["summary"]["page_layout_record_count"] == 1
    assert report["summary"]["error_count"] == 0
    assert report["findings"] == []


def test_validate_visual_sidecar_contract_accepts_security_diagram_bundle_without_raw_text(tmp_path: Path) -> None:
    output_dir = tmp_path / "security-out"
    output_dir.mkdir(parents=True)
    figure_ref = _figure_source_ref("page-0001-figure-0001")
    _write_json(
        output_dir / "manifest.json",
        {"options": {"rag_profile": "technical_spec_rag_visual", "domain_adapter": "spdm"}},
    )
    _write_json(output_dir / "report.json", {"summary": {"warning_count": 0}})
    _write_jsonl(
        output_dir / "figures_rag.jsonl",
        [
            {
                "figure_id": "page-0001-figure-0001",
                "page": 1,
                "bbox": [10, 20, 30, 40],
                "figure_kind": "sequence_diagram",
                "caption": "SPDM confidential fixture text",
            }
        ],
    )
    _write_jsonl(
        output_dir / "page_layout_rag.jsonl",
        [
            {
                "layout_id": "layout-page-0001",
                "page": 1,
                "region_refs": [figure_ref],
                "region_ref_count": 1,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_ocr_evidence_rag.jsonl",
        [
            {
                "evidence_id": "ocr-0001",
                "target_type": "figure",
                "target_id": "page-0001-figure-0001",
                "source_refs": [figure_ref],
                "ocr_text": "SPDMREQ1 SPDMRSP1",
                "text_replaced": False,
                "markdown_inserted": False,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "description-0001",
                "figure_id": "page-0001-figure-0001",
                "source_refs": [figure_ref],
                "generated_text": True,
                "generated_content_scope": "sidecar_only",
                "markdown_inserted": False,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_structures_rag.jsonl",
        [
            {
                "structure_id": "structure-0001",
                "figure_id": "page-0001-figure-0001",
                "source_refs": [figure_ref],
                "generated_text": False,
            }
        ],
    )

    report = validate_visual_sidecar_contract(output_dir, require_visual_sidecars=True)

    assert report["passed"] is True
    assert report["summary"]["figure_ocr_evidence_record_count"] == 1
    assert report["summary"]["figure_description_record_count"] == 1
    assert report["summary"]["figure_structure_record_count"] == 1
    assert "SPDMREQ1" not in json.dumps(report, ensure_ascii=False, sort_keys=True)


def test_validate_visual_sidecar_contract_rejects_generated_markdown_insertion(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    _write_jsonl(
        output_dir / "figures_rag.jsonl",
        [{"figure_id": "figure-0001", "page": 1, "bbox": [10, 20, 30, 40]}],
    )
    _write_jsonl(
        output_dir / "page_layout_rag.jsonl",
        [{"layout_id": "layout-page-0001", "page": 1, "region_refs": [], "region_ref_count": 1}],
    )
    _write_jsonl(
        output_dir / "figure_ocr_evidence_rag.jsonl",
        [
            {
                "evidence_id": "ocr-0001",
                "target_type": "figure",
                "target_id": "missing-figure",
                "source_refs": [],
                "text_replaced": True,
                "markdown_inserted": False,
            }
        ],
    )
    _write_jsonl(
        output_dir / "figure_descriptions_rag.jsonl",
        [
            {
                "description_id": "description-0001",
                "figure_id": "figure-0001",
                "source_refs": [],
                "generated_text": False,
                "generated_content_scope": "markdown",
                "markdown_inserted": True,
            }
        ],
    )

    report = validate_visual_sidecar_contract(output_dir)
    codes = {finding["code"] for finding in report["findings"]}

    assert report["passed"] is False
    assert "layout_region_ref_count_mismatch" in codes
    assert "ocr_evidence_unresolved_figure" in codes
    assert "ocr_evidence_missing_figure_source_ref" in codes
    assert "ocr_evidence_replaced_source_text" in codes
    assert "description_missing_figure_source_ref" in codes
    assert "description_missing_generated_text_flag" in codes
    assert "description_generated_content_scope_violation" in codes


def test_validate_visual_sidecar_contract_cli_writes_report(tmp_path: Path) -> None:
    output_dir = tmp_path / "out"
    _write_valid_visual_bundle(output_dir)

    exit_code = visual_sidecar_main(["--output-dir", str(output_dir), "--require-visual-sidecars"])

    payload = json.loads((output_dir / REPORT_FILENAME).read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["purpose"] == "visual_sidecar_contract_validation"
    assert payload["passed"] is True

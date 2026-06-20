from __future__ import annotations

import json
from pathlib import Path

import pdf2md.pipeline as pipeline_module
import pdf2md.serializers.rag_figure_semantics as figure_semantics_module
import pdf2md.serializers.rag_ocr_evidence as ocr_evidence_module
from pdf2md.config import Config
from pdf2md.extractors.images import ImageExtractionResult
from pdf2md.extractors.ocr import OcrResult
from pdf2md.extractors.ocr_backends import OCRBackendMetadata, OCRBackendResult
from pdf2md.extractors.tables import TableExtractionResult
from pdf2md.models import ExcludedImageAsset, ImageAsset, ImageMode, RagSidecarScope, RagTableOutputMode
from pdf2md.serializers.rag_chunks import build_retrieval_chunks
from pdf2md.serializers.rag_figure_semantics import (
    augment_figure_records_with_region_ocr,
    build_figure_description_records,
    build_figure_structure_records,
)
from pdf2md.serializers.rag_figures import build_figure_records, serialize_figures_jsonl
from pdf2md.serializers.rag_ocr_evidence import build_region_ocr_evidence_records
from scripts.validate_artifact_integrity import validate_artifact_integrity
from scripts.validate_index_contract import validate_index_contract
from scripts.validate_provenance_integrity import validate_provenance_integrity


class _FakeRegionImage:
    width = 1000
    height = 1000

    def crop(self, box):  # noqa: ANN001, ANN201
        return {"crop_box": box}


class _FakeRegionPage:
    def render(self, scale: float):  # noqa: ANN201, ARG002
        return type("FakeBitmap", (), {"to_pil": lambda self: _FakeRegionImage()})()

    def close(self) -> None:
        return None


class _FakeRegionDocument:
    def __init__(self, path: str) -> None:  # noqa: ARG002
        self.path = path

    def get_page(self, index: int) -> _FakeRegionPage:  # noqa: ARG002
        return _FakeRegionPage()

    def close(self) -> None:
        return None


class _FakePdfium:
    PdfDocument = _FakeRegionDocument


class _FakeRegionOCRBackend:
    metadata = OCRBackendMetadata(name="tesseract", raw_confidence_unit="0_to_100")

    def __init__(self, *, text: str = "NVME1", confidence: str = "90", available: bool = True) -> None:
        self.text = text
        self.confidence = confidence
        self.available = available

    def is_available(self) -> bool:
        return self.available

    def configure_runtime(self) -> None:
        return None

    def recognize(self, image, *, lang: str) -> OCRBackendResult:  # noqa: ANN001
        return OCRBackendResult(text=self.text, confidence_data={"text": [self.text], "conf": [self.confidence]})


def test_figure_records_include_available_and_excluded_image_provenance() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "heading",
            "text": "1 Figures",
            "bbox": [72.0, 50.0, 160.0, 64.0],
            "line_indices": [0],
            "heading_path": ["1 Figures"],
        }
    ]
    image = ImageAsset(
        page=1,
        index=1,
        path="assets/images/page-0001-figure-001.png",
        caption_text="Figure 1: State machine flow",
        caption_source="nearby_caption",
        caption_confidence=0.92,
        bbox=[72.0, 90.0, 200.0, 180.0],
        width=128,
        height=90,
        sha256="abc",
        anchor_line_index=2,
        anchor_top=90.0,
    )
    excluded = ExcludedImageAsset(
        page=1,
        index=2,
        reason="decorative_or_too_small",
        classification="small_image",
        recovered_text="Figure candidate",
        recovered_confidence=0.61,
        ocr_candidates=[{"text": "Figure candidate", "confidence": 0.61}],
        bbox=[220.0, 90.0, 240.0, 110.0],
    )

    records = build_figure_records(images=[image], excluded_images=[excluded], text_block_records=text_blocks)

    assert [record["figure_id"] for record in records] == [
        "page-0001-figure-0001",
        "page-0001-figure-0002",
    ]
    assert records[0]["record_type"] == "image"
    assert records[0]["figure_kind"] == "state_machine"
    assert records[0]["diagram_candidate"] is True
    assert records[0]["heading_path"] == ["1 Figures"]
    assert records[0]["source_refs"][0]["path"].endswith("page-0001-figure-001.png")
    assert records[1]["record_type"] == "excluded_image"
    assert records[1]["ocr_candidates"][0]["text"] == "Figure candidate"
    assert "decorative_or_too_small" in records[1]["classification_reasons"]

    jsonl = serialize_figures_jsonl(records)
    assert json.loads(jsonl.splitlines()[0])["figure_id"] == "page-0001-figure-0001"


def test_diagram_ocr_labels_require_confidence_for_promotion() -> None:
    high_confidence = ExcludedImageAsset(
        page=1,
        index=1,
        reason="diagram_crop_candidate",
        classification="large_image",
        recovered_text="Sequence diagram MSG1",
        recovered_confidence=0.91,
        ocr_candidates=[{"text": "Sequence diagram MSG1", "confidence": 0.91}],
        bbox=[72.0, 90.0, 300.0, 180.0],
    )
    low_confidence = ExcludedImageAsset(
        page=1,
        index=2,
        reason="diagram_crop_candidate",
        classification="large_image",
        recovered_text="State machine IDLE",
        recovered_confidence=0.42,
        ocr_candidates=[{"text": "State machine IDLE", "confidence": 0.42}],
        bbox=[72.0, 200.0, 300.0, 280.0],
    )

    records = build_figure_records(images=[], excluded_images=[high_confidence, low_confidence], text_block_records=[])

    assert records[0]["figure_kind"] == "sequence_diagram"
    assert "MSG1" in records[0]["detected_labels"]
    assert records[0]["diagram_label_diagnostics"]["promoted_ocr_candidate_count"] == 1
    assert records[1]["figure_kind"] == "image"
    assert records[1]["diagram_candidate"] is False
    assert "IDLE" not in records[1]["detected_labels"]
    assert records[1]["diagram_label_diagnostics"]["rejected_ocr_candidate_count"] == 1
    assert records[1]["diagram_label_diagnostics"]["rejected_ocr_candidates"][0]["reason"] == "low_confidence"


def test_captionless_low_confidence_diagram_candidate_stays_diagnostics_only() -> None:
    candidate = ExcludedImageAsset(
        page=1,
        index=1,
        reason="diagram_crop_candidate",
        classification="large_image",
        ocr_candidates=[{"text": "State machine IDLE", "confidence": 0.42}],
        bbox=[72.0, 90.0, 300.0, 180.0],
    )

    records = build_figure_records(images=[], excluded_images=[candidate], text_block_records=[])

    assert records[0]["caption_text"] is None
    assert records[0]["figure_kind"] == "image"
    assert "IDLE" not in records[0]["detected_labels"]
    assert records[0]["diagram_label_diagnostics"]["rejected_ocr_candidates"][0]["reason"] == "low_confidence"
    assert records[0]["captionless_diagnostics"] == {
        "caption_present": False,
        "heading_path_present": False,
        "nearby_text_ref_count": 0,
        "ocr_candidate_count": 1,
        "promoted_label_count": 0,
        "status": "captionless_diagnostics_only",
        "rejection_reasons": [
            "low_confidence",
            "missing_caption",
            "missing_heading_path",
            "no_nearby_text_refs",
            "no_promoted_ocr_labels",
        ],
    }


def test_figure_records_use_nearby_crop_text_for_diagram_labels() -> None:
    text_blocks = [
        {
            "block_id": "page-0001-block-0001",
            "page": 1,
            "block_index": 1,
            "block_type": "heading",
            "text": "2.1 State Machine",
            "bbox": [72.0, 40.0, 200.0, 58.0],
            "line_indices": [0],
            "heading_path": ["2.1 State Machine"],
        },
        {
            "block_id": "page-0001-block-0002",
            "page": 1,
            "block_index": 2,
            "block_type": "caption",
            "text": "Figure 1: State machine diagram",
            "bbox": [72.0, 80.0, 230.0, 94.0],
            "line_indices": [1],
            "heading_path": ["2.1 State Machine"],
        },
        {
            "block_id": "page-0001-block-0003",
            "page": 1,
            "block_index": 3,
            "block_type": "paragraph",
            "text": "IDLE READY ERROR RESET",
            "bbox": [96.0, 132.0, 360.0, 150.0],
            "line_indices": [2],
            "heading_path": ["2.1 State Machine"],
        },
        {
            "block_id": "page-0001-block-0004",
            "page": 1,
            "block_index": 4,
            "block_type": "paragraph",
            "text": "outside text",
            "bbox": [72.0, 360.0, 180.0, 378.0],
            "line_indices": [3],
            "heading_path": ["2.1 State Machine"],
        },
    ]
    image = ImageAsset(
        page=1,
        index=1,
        path="assets/images/page-0001-figure-001.png",
        caption_text="Figure 1: State machine diagram",
        caption_source="nearby_caption",
        caption_confidence=0.85,
        bbox=[72.0, 104.0, 520.0, 320.0],
        width=896,
        height=432,
        sha256="abc",
        source="page_crop",
        crop_reason="captioned_figure_without_embedded_image",
        anchor_line_index=1,
        anchor_top=80.0,
    )

    records = build_figure_records(images=[image], excluded_images=[], text_block_records=text_blocks)

    assert records[0]["nearby_text_refs"] == [
        {
            "block_id": "page-0001-block-0003",
            "page": 1,
            "block_index": 3,
            "block_type": "paragraph",
            "text": "IDLE READY ERROR RESET",
            "bbox": [96.0, 132.0, 360.0, 150.0],
        }
    ]
    assert "READY" in records[0]["detected_labels"]
    assert "ERROR" in records[0]["detected_labels"]
    assert "outside" not in records[0]["detected_labels"]


def test_figure_visual_semantics_sidecars_are_context_only_and_chunkable() -> None:
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "page": 1,
            "figure_index": 1,
            "bbox": [72.0, 100.0, 420.0, 300.0],
            "caption_text": "Figure 1: PCIe block diagram",
            "caption_confidence": 0.9,
            "heading_path": ["3 Architecture"],
            "figure_kind": "diagram",
            "diagram_candidate": True,
            "detected_labels": ["HOST"],
            "nearby_text_refs": [{"text": "CTRL DATA", "page": 1}],
            "ocr_candidates": [{"text": "NVME1 READY", "confidence": 0.88}],
            "source_refs": [
                {
                    "source_type": "figure",
                    "source_id": "page-0001-figure-0001",
                    "page": 1,
                    "bbox": [72.0, 100.0, 420.0, 300.0],
                    "path": "assets/images/page-0001-figure-001.png",
                }
            ],
        }
    ]

    augmented, region_metrics = augment_figure_records_with_region_ocr(figure_records)
    descriptions, description_metrics = build_figure_description_records(augmented, backend="local-vlm")
    structures, structure_metrics = build_figure_structure_records(augmented)
    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        figure_records=augmented,
        figure_description_records=descriptions,
        figure_structure_records=structures,
        source_sha256="a" * 64,
    )

    assert region_metrics["figure_region_ocr_promoted_label_count"] == 2
    assert augmented[0]["figure_region_ocr"]["status"] == "promoted_labels"
    assert "NVME1" in augmented[0]["detected_labels"]
    assert descriptions[0]["generated_text"] is True
    assert descriptions[0]["backend_status"] == "not_invoked_context_only"
    assert descriptions[0]["source_evidence"]["visual_pixels_interpreted"] is False
    assert "Generated figure description (context-only)." in descriptions[0]["text"]
    assert description_metrics["figure_description_record_count"] == 1
    assert structures[0]["structure_type"] == "block_diagram"
    assert structures[0]["derived_from_context"] is True
    assert structure_metrics["figure_structure_record_count"] == 1
    chunk_types = [chunk["chunk_type"] for chunk in chunks]
    assert "figure_description" in chunk_types
    assert "figure_structure" in chunk_types
    description_chunk = next(chunk for chunk in chunks if chunk["chunk_type"] == "figure_description")
    assert description_chunk["generated_text"] is True
    assert {ref["source_type"] for ref in description_chunk["source_refs"]} == {"figure", "figure_description"}


def test_region_ocr_report_only_promotes_labels_from_figure_bbox(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr(figure_semantics_module, "pdfium", _FakePdfium)
    monkeypatch.setattr(
        figure_semantics_module,
        "get_ocr_backend",
        lambda name, *, pytesseract_module: _FakeRegionOCRBackend(text="NVME1", confidence="90"),
    )
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "figure_index": 1,
            "page": 1,
            "bbox": [10.0, 20.0, 120.0, 160.0],
            "detected_labels": [],
        }
    ]

    augmented, metrics = augment_figure_records_with_region_ocr(
        figure_records,
        pdf_path=tmp_path / "figure.pdf",
        ocr_lang="eng",
        ocr_backend="tesseract",
    )

    diagnostics = augmented[0]["figure_region_ocr"]
    assert augmented[0]["detected_labels"] == ["NVME1"]
    assert diagnostics["status"] == "promoted_labels"
    assert diagnostics["region_ocr"]["status"] == "candidate"
    assert diagnostics["region_ocr"]["candidate"]["source"] == "region_ocr"
    assert diagnostics["region_ocr"]["report_only"] is True
    assert diagnostics["region_ocr"]["text_replaced"] is False
    assert metrics["figure_region_ocr_render_attempted_count"] == 1
    assert metrics["figure_region_ocr_region_candidate_count"] == 1
    assert metrics["figure_region_ocr_accepted_region_count"] == 1
    assert metrics["figure_region_ocr_rejected_region_count"] == 0


def test_region_ocr_report_only_records_runtime_unavailable(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr(figure_semantics_module, "pdfium", None)

    augmented, metrics = augment_figure_records_with_region_ocr(
        [
            {
                "figure_id": "page-0001-figure-0001",
                "figure_index": 1,
                "page": 1,
                "bbox": [10.0, 20.0, 120.0, 160.0],
            }
        ],
        pdf_path=tmp_path / "figure.pdf",
    )

    diagnostics = augmented[0]["figure_region_ocr"]
    assert diagnostics["region_ocr"]["status"] == "runtime_unavailable"
    assert diagnostics["region_ocr"]["reason"] == "pdfium_unavailable"
    assert diagnostics["region_ocr"]["report_only"] is True
    assert metrics["figure_region_ocr_runtime_unavailable_count"] == 1
    assert metrics["figure_region_ocr_render_attempted_count"] == 0


def test_region_ocr_report_only_rejects_invalid_bbox(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr(figure_semantics_module, "pdfium", _FakePdfium)
    monkeypatch.setattr(
        figure_semantics_module,
        "get_ocr_backend",
        lambda name, *, pytesseract_module: _FakeRegionOCRBackend(text="NVME1", confidence="90"),
    )

    augmented, metrics = augment_figure_records_with_region_ocr(
        [
            {
                "figure_id": "page-0001-figure-0001",
                "figure_index": 1,
                "page": 1,
                "bbox": [10.0, 20.0, 10.5, 20.5],
            }
        ],
        pdf_path=tmp_path / "figure.pdf",
    )

    diagnostics = augmented[0]["figure_region_ocr"]
    assert diagnostics["region_ocr"]["status"] == "rejected"
    assert diagnostics["region_ocr"]["reason"] == "invalid_bbox"
    assert metrics["figure_region_ocr_crop_rejected_count"] == 1
    assert metrics["figure_region_ocr_rejected_region_count"] == 1


def test_region_ocr_evidence_records_include_figure_and_table_targets(monkeypatch, tmp_path: Path) -> None:  # noqa: ANN001
    monkeypatch.setattr(ocr_evidence_module, "_region_ocr_runtime", lambda *, ocr_backend: (
        _FakePdfium,
        _FakeRegionOCRBackend(text="TABLE1", confidence="92"),
        None,
    ))
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "figure_index": 1,
            "page": 1,
            "bbox": [10.0, 20.0, 120.0, 160.0],
            "source_refs": [
                {
                    "source_type": "figure",
                    "source_id": "page-0001-figure-0001",
                    "page": 1,
                    "bbox": [10.0, 20.0, 120.0, 160.0],
                }
            ],
            "figure_region_ocr": {
                "region_ocr": {
                    "status": "candidate",
                    "backend": "tesseract",
                    "ocr_lang": "eng",
                    "attempted": True,
                    "candidate": {
                        "text": "NVME1",
                        "confidence": 0.9,
                        "source": "region_ocr",
                        "bbox": [10.0, 20.0, 120.0, 160.0],
                        "ocr_confidence_mean": 90.0,
                        "ocr_confidence_median": 90.0,
                        "low_conf_token_ratio": 0.0,
                    },
                    "rejected": None,
                    "report_only": True,
                    "text_replaced": False,
                }
            },
        }
    ]
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "table_id": "page-0001-table-0001",
            "bbox": [130.0, 20.0, 280.0, 160.0],
            "source_mode": "image_only",
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "source_mode": "image_only",
                    "headers": [],
                    "row_index": 1,
                    "cells": {"label": "diagram-only"},
                    "row_text": "label=diagram-only",
                    "bbox": [130.0, 20.0, 280.0, 160.0],
                    "quality_score": 0.8,
                    "fallback_reasons": [],
                    "header_depth": 0,
                    "header_confidence": 0.0,
                    "rag_header_strategy": "none",
                }
            ],
        }
    ]

    records, metrics = build_region_ocr_evidence_records(
        figure_records=figure_records,
        rag_tables=rag_tables,
        source_sha256="a" * 64,
        pdf_path=tmp_path / "sample.pdf",
        ocr_backend="tesseract",
        ocr_lang="eng",
    )

    assert metrics["figure_ocr_evidence_record_count"] == 2
    assert metrics["region_ocr_evidence_accepted_count"] == 2
    assert {record["target_type"] for record in records} == {"figure", "table"}
    assert [record["evidence_id"] for record in records] == ["ocr-evidence-000001", "ocr-evidence-000002"]
    assert records[0]["ocr_text"] == "NVME1"
    assert records[0]["source_refs"][0]["source_type"] == "figure"
    assert records[1]["ocr_text"] == "TABLE1"
    assert records[1]["source_refs"][0]["source_type"] == "table"
    assert records[1]["report_only"] is True
    assert records[1]["text_replaced"] is False
    assert records[1]["markdown_inserted"] is False


def test_region_ocr_evidence_rejects_low_confidence_candidate() -> None:
    figure_records = [
        {
            "figure_id": "page-0001-figure-0001",
            "figure_index": 1,
            "page": 1,
            "bbox": [10.0, 20.0, 120.0, 160.0],
            "source_refs": [{"source_type": "figure", "source_id": "page-0001-figure-0001", "page": 1}],
            "figure_region_ocr": {
                "region_ocr": {
                    "status": "candidate",
                    "backend": "tesseract",
                    "ocr_lang": "eng",
                    "attempted": True,
                    "candidate": {"text": "NOISY", "confidence": 0.3, "source": "region_ocr"},
                    "rejected": None,
                    "report_only": True,
                    "text_replaced": False,
                }
            },
        }
    ]

    records, metrics = build_region_ocr_evidence_records(
        figure_records=figure_records,
        rag_tables=[],
        source_sha256="a" * 64,
    )

    assert metrics["region_ocr_evidence_rejected_count"] == 1
    assert records[0]["status"] == "rejected"
    assert records[0]["rejected_reason"] == "low_confidence"
    assert records[0]["ocr_text"] is None
    assert records[0]["candidate"]["text"] == "NOISY"


def test_pipeline_writes_assetless_figure_text_chunks_with_placeholder_mode(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    image = ImageAsset(
        page=1,
        index=1,
        path="assets/images/page-0001-figure-001.png",
        caption_text="Figure 1: State machine diagram",
        caption_source="nearby_caption",
        caption_confidence=0.91,
        bbox=[72.0, 120.0, 420.0, 320.0],
        width=348,
        height=200,
        sha256="abc",
        source="page_crop",
        anchor_line_index=1,
        anchor_top=120.0,
    )
    monkeypatch.setattr(
        pipeline_module,
        "extract_images",
        lambda *args, **kwargs: ImageExtractionResult(assets=[image]),
    )
    monkeypatch.setattr(pipeline_module, "extract_tables", lambda *args, **kwargs: TableExtractionResult())
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "assetless"
    result = pipeline_module.run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.PLACEHOLDER,
            rag_sidecar_scope=RagSidecarScope.MINIMAL,
            rag_figure_text_chunks=True,
            figure_region_ocr=True,
            rag_generated_figure_descriptions=True,
            figure_structure_extraction=True,
        )
    )

    assert result.exit_code == 0
    assert not (output_dir / "assets" / "images" / "page-0001-figure-001.png").exists()
    assert (output_dir / "figures_rag.jsonl").exists()
    assert (output_dir / "figure_descriptions_rag.jsonl").exists()
    assert (output_dir / "figure_structures_rag.jsonl").exists()
    retrieval_records = [
        json.loads(line)
        for line in (output_dir / "retrieval_chunks_rag.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    figure_chunks = [record for record in retrieval_records if record.get("chunk_type") == "figure_text"]
    description_chunks = [record for record in retrieval_records if record.get("chunk_type") == "figure_description"]
    structure_chunks = [record for record in retrieval_records if record.get("chunk_type") == "figure_structure"]
    assert len(figure_chunks) == 1
    assert len(description_chunks) == 1
    assert len(structure_chunks) == 1
    assert "caption: Figure 1: State machine diagram" in figure_chunks[0]["text"]
    assert figure_chunks[0]["source_refs"][0]["source_id"] == "page-0001-figure-0001"
    assert "path" not in figure_chunks[0]["source_refs"][0]
    assert description_chunks[0]["generated_text"] is True
    assert structure_chunks[0]["derived_from_context"] is True

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["rag_figure_text_chunks"] is True
    assert manifest["options"]["figure_region_ocr"] is True
    assert manifest["options"]["rag_generated_figure_descriptions"] is True
    assert manifest["options"]["figure_structure_extraction"] is True
    assert manifest["options"]["rag_sidecar_scope"] == "minimal"
    assert manifest["options"]["figures_rag_jsonl_filename"] == "figures_rag.jsonl"
    assert manifest["options"]["figure_descriptions_jsonl_filename"] == "figure_descriptions_rag.jsonl"
    assert manifest["options"]["figure_structures_jsonl_filename"] == "figure_structures_rag.jsonl"
    assert "figures_rag.jsonl" not in manifest["options"]["rag_sidecar_omitted_outputs"]
    assert "figure_descriptions_rag.jsonl" not in manifest["options"]["rag_sidecar_omitted_outputs"]
    assert "figure_structures_rag.jsonl" not in manifest["options"]["rag_sidecar_omitted_outputs"]
    assert report["summary"]["figure_text_chunk_record_count"] == 1
    assert report["summary"]["figure_description_chunk_record_count"] == 1
    assert report["summary"]["figure_structure_chunk_record_count"] == 1
    assert report["summary"]["figure_rag_record_count"] == 1
    assert report["summary"]["figure_description_record_count"] == 1
    assert report["summary"]["figure_structure_record_count"] == 1

    assert validate_index_contract(output_dir=output_dir)["passed"] is True
    assert validate_provenance_integrity(output_dir=output_dir)["passed"] is True
    assert validate_artifact_integrity(output_dir=output_dir)["passed"] is True


def test_pipeline_writes_region_ocr_evidence_sidecar_without_markdown_pollution(
    sample_pdf: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(figure_semantics_module, "pdfium", _FakePdfium)
    monkeypatch.setattr(
        figure_semantics_module,
        "get_ocr_backend",
        lambda name, *, pytesseract_module: _FakeRegionOCRBackend(text="NVME1 READY", confidence="90"),
    )
    image = ImageAsset(
        page=1,
        index=1,
        path="assets/images/page-0001-figure-001.png",
        caption_text="Figure 1: State machine diagram",
        caption_source="nearby_caption",
        caption_confidence=0.91,
        bbox=[72.0, 120.0, 420.0, 320.0],
        width=348,
        height=200,
        sha256="abc",
        source="page_crop",
        anchor_line_index=1,
        anchor_top=120.0,
    )
    table_payload = {
        "page": 1,
        "table_index": 1,
        "table_id": "page-0001-table-0001",
        "bbox": [72.0, 340.0, 420.0, 460.0],
        "source_mode": "image_only",
        "headers": [],
        "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "source_mode": "image_only",
                    "headers": [],
                    "row_index": 1,
                    "cells": {"label": "diagram-only"},
                    "row_text": "label=diagram-only",
                    "bbox": [72.0, 340.0, 420.0, 460.0],
                    "quality_score": 0.8,
                    "fallback_reasons": [],
                    "header_depth": 0,
                    "header_confidence": 0.0,
                    "rag_header_strategy": "none",
                }
            ],
    }
    monkeypatch.setattr(
        pipeline_module,
        "extract_images",
        lambda *args, **kwargs: ImageExtractionResult(assets=[image]),
    )
    monkeypatch.setattr(
        pipeline_module,
        "extract_tables",
        lambda *args, **kwargs: TableExtractionResult(rag_tables=[table_payload]),
    )
    monkeypatch.setattr(pipeline_module, "run_ocr", lambda *args, **kwargs: OcrResult())

    output_dir = tmp_path / "region-ocr-evidence"
    result = pipeline_module.run_conversion(
        Config(
            input_pdf=sample_pdf,
            output_dir=output_dir,
            image_mode=ImageMode.PLACEHOLDER,
            rag_sidecar_scope=RagSidecarScope.FULL,
            rag_table_output=RagTableOutputMode.JSONL,
            figure_region_ocr=True,
        )
    )

    assert result.exit_code == 0
    evidence_path = output_dir / "figure_ocr_evidence_rag.jsonl"
    assert evidence_path.exists()
    records = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert {record["target_type"] for record in records} == {"figure", "table"}
    assert all(record["report_only"] is True for record in records)
    assert all(record["text_replaced"] is False for record in records)
    assert all(record["markdown_inserted"] is False for record in records)
    assert all(record["status"] == "accepted" for record in records)
    assert all(record["ocr_text"] == "NVME1 READY" for record in records)
    markdown = (output_dir / "document.md").read_text(encoding="utf-8")
    assert "NVME1 READY" not in markdown

    manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
    report = json.loads((output_dir / "report.json").read_text(encoding="utf-8"))
    assert manifest["options"]["figure_ocr_evidence_jsonl_filename"] == "figure_ocr_evidence_rag.jsonl"
    assert report["summary"]["figure_ocr_evidence_record_count"] == 2
    assert report["summary"]["region_ocr_evidence_accepted_count"] == 2

    assert validate_index_contract(output_dir=output_dir)["passed"] is True
    assert validate_provenance_integrity(output_dir=output_dir)["passed"] is True
    assert validate_artifact_integrity(output_dir=output_dir)["passed"] is True

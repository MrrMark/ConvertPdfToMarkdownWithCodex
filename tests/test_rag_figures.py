from __future__ import annotations

import json

from pdf2md.models import ExcludedImageAsset, ImageAsset
from pdf2md.serializers.rag_figures import build_figure_records, serialize_figures_jsonl


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

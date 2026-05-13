from __future__ import annotations

import json
from pathlib import Path

from scripts.run_ssd_corpus_profile import run_profile
from scripts.validate_ssd_rag_contract import validate_ssd_rag_contract


def _write_jsonl(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n", encoding="utf-8")


def test_ssd_rag_contract_accepts_tcg_first_class_spec_type(tmp_path: Path) -> None:
    source_sha256 = "a" * 64
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-000001",
                "schema_version": "1.0",
                "chunk_index": 1,
                "chunk_type": "domain_unit",
                "text": "Method = StartSession | UID = 0001h | Description = Starts a session",
                "source_sha256": source_sha256,
                "source_refs": [{"source_type": "domain_unit", "source_id": "domain-tcg-000001", "page": 1}],
                "page_range": [1, 1],
                "bbox": [72.0, 100.0, 300.0, 120.0],
                "heading_path": ["TCG Methods"],
                "semantic_types": ["security_method"],
                "normative_strength": None,
                "retrieval_priority": 90,
                "char_count": 68,
                "token_estimate": 17,
                "section_path": "TCG Methods",
                "chunk_group_id": "domain-tcg",
                "source_record_count": 1,
                "source_dedupe_key": "domain-tcg-000001",
                "chunk_boundary_policy": "source_record",
                "chunk_boundary_reasons": ["domain_unit_boundary"],
            }
        ],
    )
    _write_jsonl(tmp_path / "requirements_rag.jsonl", [])
    _write_jsonl(
        tmp_path / "technical_tables_rag.jsonl",
        [
            {
                "technical_table_unit_id": "tech-table-000001",
                "unit_type": "security_method",
                "page": 1,
                "table_id": "page-0001-table-0001",
                "table_row_id": "page-0001-table-0001-row-0001",
                "bbox": [72.0, 100.0, 300.0, 120.0],
            }
        ],
    )
    _write_jsonl(tmp_path / "tables_rag.jsonl", [
        {
            "table_row_id": "page-0001-table-0001-row-0001",
            "table_id": "page-0001-table-0001",
            "page": 1,
            "bbox": [72.0, 100.0, 300.0, 120.0],
        }
    ])
    _write_jsonl(tmp_path / "domain_units_rag.jsonl", [
        {
            "domain_unit_id": "domain-tcg-000001",
            "domain": "tcg",
            "unit_type": "security_method",
            "source_refs": [{"source_type": "table_row", "source_id": "page-0001-table-0001-row-0001"}],
        }
    ])
    _write_jsonl(tmp_path / "cross_refs_rag.jsonl", [])
    _write_jsonl(tmp_path / "figures_rag.jsonl", [])

    report = validate_ssd_rag_contract(
        output_dir=tmp_path,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="TCG",
        domain_adapter="tcg",
        document_id="TCG_DOC",
        source_sha256=source_sha256,
    )

    assert report["passed"] is True
    assert report["sample_mapped_chunk"]["citation"]["document_id"] == "TCG_DOC"
    assert report["sample_mapped_chunk"]["citation"]["heading_path"] == "TCG Methods"
    assert report["sample_mapped_chunk"]["metadata"]["source_sha256"] == source_sha256


def test_ssd_rag_contract_rejects_adapter_spec_type_mismatch(tmp_path: Path) -> None:
    _write_jsonl(tmp_path / "retrieval_chunks_rag.jsonl", [])

    report = validate_ssd_rag_contract(
        output_dir=tmp_path,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="CustomerRequirement",
        domain_adapter="tcg",
        require_tables=False,
        require_domain_units=False,
    )

    assert report["passed"] is False
    assert "adapter_spec_type_mismatch" in {error["code"] for error in report["errors"]}


def test_ssd_corpus_profile_dry_run_builds_required_command_and_tcg_mapping(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "profile_name": "ssd-local",
                "documents": [
                    {
                        "name": "tcg-sample",
                        "input_pdf": "/secure/specs/tcg.pdf",
                        "output_dir": str(tmp_path / "tcg-output"),
                        "domain_adapter": "tcg",
                        "ssd_agent_domain": "HIL",
                        "ssd_agent_spec_type": "TCG",
                        "pages": "1-2",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = run_profile(profile, dry_run=True)

    assert report["passed"] is True
    doc = report["documents"][0]
    assert doc["ssd_agent_spec_type"] == "TCG"
    assert "--rag-table-output" in doc["command"]
    assert "jsonl" in doc["command"]
    assert "--confidential-safe-mode" in doc["command"]

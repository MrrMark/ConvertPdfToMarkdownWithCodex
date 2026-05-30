from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from pdf2md.models import LocalCorpusEvidencePack
from scripts.run_ssd_corpus_profile import build_evidence_pack, main as run_ssd_corpus_profile_main, run_profile
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


def test_ssd_rag_contract_accepts_spdm_first_class_spec_type(tmp_path: Path) -> None:
    source_sha256 = "b" * 64
    _write_jsonl(
        tmp_path / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-000001",
                "schema_version": "1.0",
                "chunk_index": 1,
                "chunk_type": "domain_unit",
                "text": "Message = GET_VERSION | Message Code = 0x84 | Description = Request version",
                "source_sha256": source_sha256,
                "source_refs": [{"source_type": "domain_unit", "source_id": "domain-spdm-000001", "page": 1}],
                "page_range": [1, 1],
                "bbox": [72.0, 100.0, 300.0, 120.0],
                "heading_path": ["SPDM Messages"],
                "semantic_types": ["spdm_message"],
                "normative_strength": None,
                "retrieval_priority": 96,
                "char_count": 78,
                "token_estimate": 20,
                "section_path": "SPDM Messages",
                "chunk_group_id": "domain-spdm",
                "source_record_count": 1,
                "source_dedupe_key": "domain-spdm-000001",
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
                "unit_type": "spdm_message",
                "page": 1,
                "table_id": "page-0001-table-0001",
                "table_row_id": "page-0001-table-0001-row-0001",
                "bbox": [72.0, 100.0, 300.0, 120.0],
            }
        ],
    )
    _write_jsonl(
        tmp_path / "tables_rag.jsonl",
        [
            {
                "table_row_id": "page-0001-table-0001-row-0001",
                "table_id": "page-0001-table-0001",
                "page": 1,
                "bbox": [72.0, 100.0, 300.0, 120.0],
            }
        ],
    )
    _write_jsonl(
        tmp_path / "domain_units_rag.jsonl",
        [
            {
                "domain_unit_id": "domain-spdm-000001",
                "domain": "spdm",
                "unit_type": "spdm_message",
                "source_refs": [{"source_type": "table_row", "source_id": "page-0001-table-0001-row-0001"}],
            }
        ],
    )
    _write_jsonl(tmp_path / "cross_refs_rag.jsonl", [])
    _write_jsonl(tmp_path / "figures_rag.jsonl", [])

    report = validate_ssd_rag_contract(
        output_dir=tmp_path,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="SPDM",
        domain_adapter="spdm",
        document_id="SPDM_DOC",
        source_sha256=source_sha256,
    )

    assert report["passed"] is True
    assert report["sample_mapped_chunk"]["citation"]["document_id"] == "SPDM_DOC"
    assert report["sample_mapped_chunk"]["metadata"]["semantic_types"] == ["spdm_message"]


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


def test_ssd_corpus_profile_aggregates_rag_eval_metrics(tmp_path: Path, monkeypatch) -> None:
    output_dir = tmp_path / "tcg-output"
    output_dir.mkdir()
    source_sha256 = "b" * 64
    _write_jsonl(
        output_dir / "retrieval_chunks_rag.jsonl",
        [
            {
                "chunk_id": "chunk-000001",
                "schema_version": "1.0",
                "chunk_index": 1,
                "chunk_type": "domain_unit",
                "text": "StartSession method starts a trusted session.",
                "source_sha256": source_sha256,
                "source_refs": [{"source_type": "domain_unit", "source_id": "domain-tcg-000001", "page": 1}],
                "page_range": [1, 1],
                "bbox": [72.0, 100.0, 300.0, 120.0],
                "heading_path": ["TCG Methods"],
                "semantic_types": ["security_method"],
                "normative_strength": None,
                "retrieval_priority": 90,
                "char_count": 43,
                "token_estimate": 11,
                "section_path": "TCG Methods",
                "chunk_group_id": "domain-tcg",
                "source_record_count": 1,
                "source_dedupe_key": "domain-tcg-000001",
                "chunk_boundary_policy": "source_record",
                "chunk_boundary_reasons": ["domain_unit_boundary"],
            }
        ],
    )
    _write_jsonl(output_dir / "requirements_rag.jsonl", [])
    _write_jsonl(
        output_dir / "technical_tables_rag.jsonl",
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
    _write_jsonl(
        output_dir / "tables_rag.jsonl",
        [
            {
                "table_row_id": "page-0001-table-0001-row-0001",
                "table_id": "page-0001-table-0001",
                "page": 1,
                "bbox": [72.0, 100.0, 300.0, 120.0],
            }
        ],
    )
    _write_jsonl(
        output_dir / "domain_units_rag.jsonl",
        [
            {
                "domain_unit_id": "domain-tcg-000001",
                "domain": "tcg",
                "unit_type": "security_method",
                "source_refs": [{"source_type": "table_row", "source_id": "page-0001-table-0001-row-0001"}],
            }
        ],
    )
    _write_jsonl(output_dir / "cross_refs_rag.jsonl", [{"ref_id": "ref-1", "resolved": True}])
    _write_jsonl(output_dir / "figures_rag.jsonl", [])
    (output_dir / "report.json").write_text(json.dumps({"duration_ms": 25}), encoding="utf-8")
    eval_set = tmp_path / "eval.json"
    eval_set.write_text(
        json.dumps(
            {
                "queries": [
                    {
                        "query": "StartSession trusted session",
                        "expected_source_ids": ["domain-tcg-000001"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    input_pdf = tmp_path / "tcg.pdf"
    input_pdf.write_bytes(b"tcg")
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "profile_name": "ssd-local",
                "documents": [
                    {
                        "name": "tcg-sample",
                        "input_pdf": str(input_pdf),
                        "output_dir": str(output_dir),
                        "domain_adapter": "tcg",
                        "ssd_agent_domain": "HIL",
                        "ssd_agent_spec_type": "TCG",
                        "eval_set": str(eval_set),
                        "rag_thresholds": {"min_hit_at_k": 1.0, "max_chunk_token_p95": 64},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("scripts.run_ssd_corpus_profile.subprocess.run", lambda *_args, **_kwargs: SimpleNamespace(returncode=0))

    report = run_profile(profile)

    assert report["passed"] is True
    assert report["summary"]["rag_eval_document_count"] == 1
    assert report["documents"][0]["rag_eval_passed"] is True
    assert report["documents"][0]["rag_eval_metrics"]["hit_at_k"] == 1.0
    assert report["rag_metrics_by_domain"]["tcg"]["hit_at_k"]["average"] == 1.0
    assert report["rag_metrics_by_spec_type"]["TCG"]["chunk_token_p95"]["max"] == 11
    assert (output_dir / "rag_eval_report.json").exists()


def test_local_corpus_evidence_pack_redacts_paths_and_groups_failures() -> None:
    profile_report = {
        "schema_version": "1.0",
        "purpose": "ssd_local_corpus_profile",
        "profile": "/secure/customer/SecretVendor/local_profile.json",
        "profile_name": "SecretVendorProfile",
        "passed": False,
        "summary": {"document_count": 1, "failed_count": 1},
        "documents": [
            {
                "name": "SecretVendor-NVMe-Requirement.pdf",
                "input_pdf": "/secure/customer/SecretVendor/SecretVendor-NVMe-Requirement.pdf",
                "output_dir": "/private/tmp/secret-output",
                "command": ["python", "-m", "pdf2md", "/secure/customer/SecretVendor/SecretVendor-NVMe-Requirement.pdf"],
                "domain_adapter": "nvme",
                "ssd_agent_domain": "HIL",
                "ssd_agent_spec_type": "NVMe",
                "conversion_exit_code": 0,
                "contract_passed": False,
                "contract_summary": {"error_count": 1, "warning_count": 1},
                "contract_findings": [
                    {"severity": "error", "code": "missing_sidecar", "path": "domain_units_rag"},
                    {"severity": "warning", "code": "heading_path_not_list", "path": "retrieval_chunks_rag.jsonl[1]"},
                ],
                "rag_eval_passed": False,
                "rag_eval_metrics": {"expected_source_coverage": 0.5},
                "rag_eval_report": {
                    "results": [{"query": "SecretVendor proprietary query"}],
                    "gate_failures": [
                        {
                            "type": "threshold_failure",
                            "metric": "expected_source_coverage",
                            "current": 0.5,
                            "limit": 0.9,
                            "direction": "min",
                        }
                    ],
                },
                "budget_failures": [
                    {"metric": "min_domain_units", "current": 0, "limit": 1, "direction": "min"}
                ],
            }
        ],
    }

    first_pack = build_evidence_pack(profile_report)
    second_pack = build_evidence_pack(profile_report)

    LocalCorpusEvidencePack.model_validate(first_pack)
    assert first_pack == second_pack
    assert first_pack["profile_label"] == "redacted-profile"
    assert first_pack["summary"]["failure_signature_count"] == 4
    assert first_pack["summary"]["failed_document_count"] == 1
    assert first_pack["documents"][0]["document_label"] == "document-000001"
    assert set(first_pack["documents"][0]["signature_ids"]) == {
        signature["signature_id"] for signature in first_pack["failure_signatures"]
    }
    assert {signature["category"] for signature in first_pack["failure_signatures"]} == {
        "budget_failure",
        "contract_error",
        "contract_warning",
        "rag_threshold",
    }
    serialized = json.dumps(first_pack, ensure_ascii=False, sort_keys=True)
    assert "/secure" not in serialized
    assert "/private/tmp" not in serialized
    assert "SecretVendor" not in serialized
    assert "proprietary query" not in serialized
    assert '"command"' not in serialized


def test_ssd_corpus_profile_cli_writes_redacted_evidence_pack(tmp_path: Path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "profile_name": "SecretVendorProfile",
                "documents": [
                    {
                        "name": "SecretVendor-NVMe",
                        "input_pdf": "/secure/customer/SecretVendor/nvme.pdf",
                        "output_dir": str(tmp_path / "nvme-output"),
                        "domain_adapter": "nvme",
                        "ssd_agent_domain": "HIL",
                        "ssd_agent_spec_type": "NVMe",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    report_path = tmp_path / "profile_report.json"
    evidence_path = tmp_path / "evidence_pack.json"

    exit_code = run_ssd_corpus_profile_main(
        [
            "--profile",
            str(profile),
            "--dry-run",
            "--report-path",
            str(report_path),
            "--evidence-pack-path",
            str(evidence_path),
        ]
    )

    assert exit_code == 0
    payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    LocalCorpusEvidencePack.model_validate(payload)
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    assert payload["summary"]["document_count"] == 1
    assert payload["documents"][0]["document_label"] == "document-000001"
    assert "/secure/customer" not in serialized
    assert "SecretVendor" not in serialized

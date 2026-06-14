from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
REPORT_FILENAME = "ssd_rag_contract_report.json"
HEX_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_HIL_SPEC_TYPES = {"NVMe", "PCIe", "OCP", "TCG", "SPDM", "CustomerRequirement"}
ALLOWED_FTL_SPEC_TYPES = {
    "BMS",
    "ReadDisturb",
    "XORRecovery",
    "GarbageCollection",
    "WearLeveling",
    "DataIntegrity",
    "Metadata",
    "PowerLossRecovery",
    "OtherFWFeature",
}
DOMAIN_ADAPTER_TO_SPEC_TYPE = {
    "nvme": "NVMe",
    "pcie": "PCIe",
    "ocp": "OCP",
    "tcg": "TCG",
    "spdm": "SPDM",
    "customer-requirements": "CustomerRequirement",
}
REQUIRED_CHUNK_FIELDS = {
    "chunk_id",
    "schema_version",
    "chunk_type",
    "text",
    "source_sha256",
    "source_refs",
    "page_range",
    "section_path",
    "heading_path",
    "semantic_types",
    "normative_strength",
    "retrieval_priority",
    "source_dedupe_key",
}
SSD_METADATA_FIELDS = {
    "chunk_type",
    "source_refs",
    "semantic_types",
    "normative_strength",
    "retrieval_priority",
    "source_dedupe_key",
    "schema_version",
    "source_sha256",
}
TCG_DOMAIN_UNIT_TYPES = {
    "security_method",
    "security_object",
    "security_authority",
    "security_field",
    "security_provider",
    "locking_range",
    "key_management",
    "session_state",
}
SPDM_DOMAIN_UNIT_TYPES = {
    "spdm_message",
    "spdm_request_response",
    "spdm_measurement",
    "spdm_certificate",
    "spdm_algorithm",
    "spdm_key_exchange",
    "spdm_session",
}
NVME_CORE_DOMAIN_UNIT_TYPES = {"command", "log_page", "feature", "register_field"}
OCP_CORE_DOMAIN_UNIT_TYPES = {"requirement"}
OCP_NORMALIZED_FIELD_REQUIREMENTS = ("requirement_id", "requirement_prefix", "requirement_family")
NVME_NORMALIZED_FIELD_REQUIREMENTS = {
    "command": ("opcode",),
    "log_page": ("log_identifier",),
    "feature": ("feature_identifier",),
    "register_field": ("field_name",),
    "status_code": ("status_code_value",),
    "queue_field": ("field_name",),
    "namespace_field": ("field_name",),
    "controller_field": ("field_name",),
    "data_structure_field": ("field_name",),
    "command_dword_field": ("command_dword", "field_name", "bit_range"),
    "command_pointer_field": ("pointer_type", "field_name"),
}
STABLE_METADATA_FIELDS = ("source_sha256", "source_dedupe_key", "stable_source_id", "stable_requirement_seed")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(str(path))
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"{path.name}:{line_number} must be a JSON object.")
        records.append(payload)
    return records


def _optional_jsonl(path: Path) -> list[dict[str, Any]]:
    return _read_jsonl(path) if path.exists() else []


def _add_issue(issues: list[dict[str, Any]], *, path: str, message: str, code: str) -> None:
    issues.append({"code": code, "path": path, "message": message})


def _valid_spec(domain: str, spec_type: str) -> bool:
    if domain == "HIL":
        return spec_type in ALLOWED_HIL_SPEC_TYPES
    if domain == "FTL":
        return spec_type in ALLOWED_FTL_SPEC_TYPES
    return False


def _chunk_to_ssd_shape(chunk: dict[str, Any], *, document_id: str) -> dict[str, Any]:
    page_range = chunk.get("page_range") if isinstance(chunk.get("page_range"), list) else []
    section_path = str(chunk.get("section_path") or "")
    return {
        "chunk_id": chunk.get("chunk_id"),
        "text": chunk.get("text"),
        "citation": {
            "document_id": document_id,
            "chunk_id": chunk.get("chunk_id"),
            "page_number": page_range[0] if page_range else None,
            "section_title": section_path,
            "heading_path": section_path,
            "citation_text": None,
        },
        "metadata": {field: chunk.get(field) for field in SSD_METADATA_FIELDS},
    }


def _validate_chunks(
    chunks: list[dict[str, Any]],
    *,
    document_id: str,
    expected_source_sha256: str | None,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    mapped: list[dict[str, Any]] = []
    seen_chunk_ids: set[str] = set()
    for index, chunk in enumerate(chunks, start=1):
        path = f"retrieval_chunks_rag.jsonl[{index}]"
        missing = sorted(field for field in REQUIRED_CHUNK_FIELDS if field not in chunk)
        if missing:
            _add_issue(errors, path=path, code="missing_chunk_fields", message=f"Missing fields: {', '.join(missing)}")
            continue
        chunk_id = str(chunk.get("chunk_id") or "")
        if not chunk_id:
            _add_issue(errors, path=path, code="empty_chunk_id", message="chunk_id must not be empty.")
        elif chunk_id in seen_chunk_ids:
            _add_issue(errors, path=path, code="duplicate_chunk_id", message=f"Duplicate chunk_id: {chunk_id}")
        seen_chunk_ids.add(chunk_id)
        if chunk.get("schema_version") != SCHEMA_VERSION:
            _add_issue(errors, path=path, code="schema_version_mismatch", message="schema_version must be 1.0.")
        source_sha256 = str(chunk.get("source_sha256") or "")
        if expected_source_sha256 and source_sha256 != expected_source_sha256:
            _add_issue(errors, path=path, code="source_sha256_mismatch", message="source_sha256 does not match expected value.")
        if not HEX_SHA256_RE.fullmatch(source_sha256):
            _add_issue(errors, path=path, code="invalid_source_sha256", message="source_sha256 must be a lowercase SHA-256 hex string.")
        if not isinstance(chunk.get("source_refs"), list) or not chunk["source_refs"]:
            _add_issue(errors, path=path, code="missing_source_refs", message="source_refs must be a non-empty list.")
        page_range = chunk.get("page_range")
        if (
            not isinstance(page_range, list)
            or len(page_range) != 2
            or not all(isinstance(page, int) for page in page_range)
        ):
            _add_issue(errors, path=path, code="invalid_page_range", message="page_range must be [start, end] integers.")
        if not isinstance(chunk.get("section_path"), str):
            _add_issue(errors, path=path, code="invalid_section_path", message="section_path must be a string.")
        if not isinstance(chunk.get("heading_path"), list):
            _add_issue(warnings, path=path, code="heading_path_not_list", message="heading_path is expected as the source list.")
        if not isinstance(chunk.get("semantic_types"), list):
            _add_issue(errors, path=path, code="invalid_semantic_types", message="semantic_types must be a list.")
        mapped.append(_chunk_to_ssd_shape(chunk, document_id=document_id))
    return mapped


def _validate_table_rows(
    records: list[dict[str, Any]],
    *,
    sidecar_name: str,
    id_field: str,
    errors: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
    strict_provenance: bool,
) -> None:
    for index, record in enumerate(records, start=1):
        path = f"{sidecar_name}[{index}]"
        for field in (id_field, "table_id", "table_row_id", "page"):
            if record.get(field) in {None, ""}:
                _add_issue(errors, path=path, code="missing_table_provenance", message=f"Missing {field}.")
        if record.get("bbox") is None:
            target = errors if strict_provenance else warnings
            _add_issue(target, path=path, code="missing_bbox", message="bbox is not available for this row.")


def _validate_stable_metadata(
    records: list[dict[str, Any]],
    *,
    sidecar_name: str,
    errors: list[dict[str, Any]],
) -> None:
    for index, record in enumerate(records, start=1):
        path = f"{sidecar_name}[{index}]"
        for field in STABLE_METADATA_FIELDS:
            if record.get(field) in {None, ""}:
                _add_issue(errors, path=path, code="missing_stable_metadata", message=f"Missing {field}.")


def _validate_nvme_domain_units(domain_units: list[dict[str, Any]], *, errors: list[dict[str, Any]]) -> None:
    if domain_units and not any(record.get("unit_type") in NVME_CORE_DOMAIN_UNIT_TYPES for record in domain_units):
        _add_issue(
            errors,
            path="domain_units_rag.jsonl",
            code="missing_nvme_core_domain_unit",
            message="NVMe domain output must include at least one command, log_page, feature, or register_field unit.",
        )
    for index, record in enumerate(domain_units, start=1):
        unit_type = str(record.get("unit_type") or "")
        normalized_fields = record.get("normalized_fields")
        path = f"domain_units_rag.jsonl[{index}]"
        if not isinstance(normalized_fields, dict):
            _add_issue(errors, path=path, code="missing_nvme_normalized_fields", message="Missing normalized_fields object.")
            continue
        required_any = NVME_NORMALIZED_FIELD_REQUIREMENTS.get(unit_type)
        if required_any and not any(normalized_fields.get(field) not in {None, ""} for field in required_any):
            _add_issue(
                errors,
                path=path,
                code="missing_nvme_normalized_field",
                message=f"{unit_type} requires one of: {', '.join(required_any)}.",
            )


def _validate_ocp_domain_units(domain_units: list[dict[str, Any]], *, errors: list[dict[str, Any]]) -> None:
    if domain_units and not any(record.get("unit_type") in OCP_CORE_DOMAIN_UNIT_TYPES for record in domain_units):
        _add_issue(
            errors,
            path="domain_units_rag.jsonl",
            code="missing_ocp_requirement_domain_unit",
            message="OCP domain output must include at least one requirement unit.",
        )
    for index, record in enumerate(domain_units, start=1):
        path = f"domain_units_rag.jsonl[{index}]"
        if record.get("unit_type") != "requirement":
            continue
        normalized_fields = record.get("normalized_fields")
        if not isinstance(normalized_fields, dict):
            _add_issue(errors, path=path, code="missing_ocp_normalized_fields", message="Missing normalized_fields object.")
            continue
        missing = [
            field
            for field in OCP_NORMALIZED_FIELD_REQUIREMENTS
            if normalized_fields.get(field) in {None, ""}
        ]
        if missing:
            _add_issue(
                errors,
                path=path,
                code="missing_ocp_normalized_field",
                message=f"OCP requirement requires: {', '.join(missing)}.",
            )
        if normalized_fields.get("source_table_row_id") in {None, ""}:
            _add_issue(
                errors,
                path=path,
                code="missing_ocp_requirement_source_row",
                message="OCP requirement normalized fields must retain source_table_row_id.",
            )


def _validate_nvme_technical_tables(technical_tables: list[dict[str, Any]], *, errors: list[dict[str, Any]]) -> None:
    for index, record in enumerate(technical_tables, start=1):
        path = f"technical_tables_rag.jsonl[{index}]"
        if not isinstance(record.get("source_refs"), list) or not record["source_refs"]:
            _add_issue(
                errors,
                path=path,
                code="missing_technical_table_source_refs",
                message="technical table units must retain source_refs.",
            )


def validate_ssd_rag_contract(
    *,
    output_dir: Path,
    ssd_agent_domain: str,
    ssd_agent_spec_type: str,
    domain_adapter: str | None = None,
    document_id: str = "SSD_RAG_DOCUMENT",
    source_sha256: str | None = None,
    require_tables: bool = True,
    require_domain_units: bool = True,
    strict_provenance: bool = False,
) -> dict[str, Any]:
    """Validate that pdf2md RAG sidecars can map to the SSD agent RAG contract."""
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    adapter = (domain_adapter or "").strip().lower() or None

    if not _valid_spec(ssd_agent_domain, ssd_agent_spec_type):
        _add_issue(
            errors,
            path="profile.ssd_agent_spec_type",
            code="invalid_ssd_spec_type",
            message=f"{ssd_agent_domain}/{ssd_agent_spec_type} is not supported by the SSD RAG contract.",
        )
    if adapter is not None:
        expected_spec_type = DOMAIN_ADAPTER_TO_SPEC_TYPE.get(adapter)
        if expected_spec_type is None:
            _add_issue(errors, path="profile.domain_adapter", code="invalid_domain_adapter", message=f"Unknown adapter: {adapter}")
        elif expected_spec_type != ssd_agent_spec_type:
            _add_issue(
                errors,
                path="profile",
                code="adapter_spec_type_mismatch",
                message=f"{adapter} maps to {expected_spec_type}, not {ssd_agent_spec_type}.",
            )
    elif ssd_agent_spec_type == "NVMe":
        _add_issue(
            warnings,
            path="profile.domain_adapter",
            code="domain_adapter_none_for_nvme",
            message="NVMe technical RAG validation should use --domain-adapter nvme for domain-unit coverage.",
        )

    sidecar_paths = {
        "retrieval_chunks_rag": output_dir / "retrieval_chunks_rag.jsonl",
        "requirements_rag": output_dir / "requirements_rag.jsonl",
        "technical_tables_rag": output_dir / "technical_tables_rag.jsonl",
        "cross_refs_rag": output_dir / "cross_refs_rag.jsonl",
        "figures_rag": output_dir / "figures_rag.jsonl",
    }
    if require_tables:
        sidecar_paths["tables_rag"] = output_dir / "tables_rag.jsonl"
    if require_domain_units:
        sidecar_paths["domain_units_rag"] = output_dir / "domain_units_rag.jsonl"
    if adapter in {"nvme", "ocp"}:
        sidecar_paths["requirement_traceability_rag"] = output_dir / "requirement_traceability_rag.jsonl"
    for name, path in sidecar_paths.items():
        if not path.exists():
            _add_issue(errors, path=name, code="missing_sidecar", message=f"Missing {path.name}.")

    chunks = _optional_jsonl(output_dir / "retrieval_chunks_rag.jsonl")
    mapped_chunks = _validate_chunks(
        chunks,
        document_id=document_id,
        expected_source_sha256=source_sha256,
        errors=errors,
        warnings=warnings,
    )
    tables = _optional_jsonl(output_dir / "tables_rag.jsonl")
    technical_tables = _optional_jsonl(output_dir / "technical_tables_rag.jsonl")
    domain_units = _optional_jsonl(output_dir / "domain_units_rag.jsonl")
    requirement_traceability = _optional_jsonl(output_dir / "requirement_traceability_rag.jsonl")
    if require_tables:
        _validate_table_rows(
            tables,
            sidecar_name="tables_rag.jsonl",
            id_field="table_row_id",
            errors=errors,
            warnings=warnings,
            strict_provenance=strict_provenance,
        )
    _validate_table_rows(
        technical_tables,
        sidecar_name="technical_tables_rag.jsonl",
        id_field="technical_table_unit_id",
        errors=errors,
        warnings=warnings,
        strict_provenance=strict_provenance,
    )
    if require_domain_units and adapter:
        if not domain_units:
            _add_issue(errors, path="domain_units_rag.jsonl", code="empty_domain_units", message="Expected domain unit records.")
        for index, record in enumerate(domain_units, start=1):
            path = f"domain_units_rag.jsonl[{index}]"
            if record.get("domain") != adapter:
                _add_issue(errors, path=path, code="domain_unit_adapter_mismatch", message=f"Expected domain={adapter}.")
            if not record.get("source_refs"):
                _add_issue(errors, path=path, code="missing_domain_unit_source_refs", message="Missing source_refs.")
        if adapter == "tcg" and domain_units and not any(record.get("unit_type") in TCG_DOMAIN_UNIT_TYPES for record in domain_units):
            _add_issue(
                errors,
                path="domain_units_rag.jsonl",
                code="missing_tcg_security_unit",
                message="TCG domain output must include at least one security unit.",
            )
        if adapter == "spdm" and domain_units and not any(record.get("unit_type") in SPDM_DOMAIN_UNIT_TYPES for record in domain_units):
            _add_issue(
                errors,
                path="domain_units_rag.jsonl",
                code="missing_spdm_security_unit",
                message="SPDM domain output must include at least one SPDM security unit.",
            )
        if adapter == "nvme":
            _validate_nvme_domain_units(domain_units, errors=errors)
        if adapter == "ocp":
            _validate_ocp_domain_units(domain_units, errors=errors)

    if adapter == "nvme":
        _validate_nvme_technical_tables(technical_tables, errors=errors)
        _validate_stable_metadata(
            technical_tables,
            sidecar_name="technical_tables_rag.jsonl",
            errors=errors,
        )

    if adapter == "ocp":
        _validate_nvme_technical_tables(technical_tables, errors=errors)
        _validate_stable_metadata(
            technical_tables,
            sidecar_name="technical_tables_rag.jsonl",
            errors=errors,
        )
        _validate_stable_metadata(
            domain_units,
            sidecar_name="domain_units_rag.jsonl",
            errors=errors,
        )
        _validate_stable_metadata(
            requirement_traceability,
            sidecar_name="requirement_traceability_rag.jsonl",
            errors=errors,
        )
        _validate_stable_metadata(
            domain_units,
            sidecar_name="domain_units_rag.jsonl",
            errors=errors,
        )
        _validate_stable_metadata(
            requirement_traceability,
            sidecar_name="requirement_traceability_rag.jsonl",
            errors=errors,
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "purpose": "ssd_rag_contract_validation",
        "output_dir": str(output_dir),
        "ssd_agent_domain": ssd_agent_domain,
        "ssd_agent_spec_type": ssd_agent_spec_type,
        "domain_adapter": adapter,
        "document_id": document_id,
        "passed": not errors,
        "summary": {
            "chunk_count": len(chunks),
            "mapped_chunk_count": len(mapped_chunks),
            "table_row_count": len(tables),
            "technical_table_row_count": len(technical_tables),
            "domain_unit_count": len(domain_units),
            "requirement_traceability_count": len(requirement_traceability),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
        "errors": errors,
        "warnings": warnings,
        "sample_mapped_chunk": mapped_chunks[0] if mapped_chunks else None,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate pdf2md RAG sidecars for SSD verification agent ingest.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--ssd-agent-domain", default="HIL")
    parser.add_argument("--ssd-agent-spec-type", required=True)
    parser.add_argument("--domain-adapter", choices=sorted(DOMAIN_ADAPTER_TO_SPEC_TYPE), default=None)
    parser.add_argument("--document-id", default="SSD_RAG_DOCUMENT")
    parser.add_argument("--source-sha256", default=None)
    parser.add_argument("--report-path", type=Path, default=None)
    parser.add_argument("--no-require-tables", action="store_true")
    parser.add_argument("--no-require-domain-units", action="store_true")
    parser.add_argument("--strict-provenance", action="store_true")
    parser.add_argument("--fail-on-warning", action="store_true")
    args = parser.parse_args(argv)

    report = validate_ssd_rag_contract(
        output_dir=args.output_dir,
        ssd_agent_domain=args.ssd_agent_domain,
        ssd_agent_spec_type=args.ssd_agent_spec_type,
        domain_adapter=args.domain_adapter,
        document_id=args.document_id,
        source_sha256=args.source_sha256,
        require_tables=not args.no_require_tables,
        require_domain_units=not args.no_require_domain_units,
        strict_provenance=args.strict_provenance,
    )
    report_path = args.report_path or args.output_dir / REPORT_FILENAME
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        "SSD RAG contract validation: "
        f"passed={report['passed']} errors={report['summary']['error_count']} "
        f"warnings={report['summary']['warning_count']} report={report_path}"
    )
    if report["errors"] or (args.fail_on_warning and report["warnings"]):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

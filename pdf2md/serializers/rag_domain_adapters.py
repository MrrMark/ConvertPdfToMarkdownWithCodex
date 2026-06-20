from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from pdf2md.models import DomainAdapterMode
from pdf2md.serializers.rag_tables import flatten_rag_table_records, normalize_rag_table_payload
from pdf2md.serializers.rag_stable_ids import with_stable_source_metadata
from pdf2md.serializers.rag_technical_tables import build_technical_table_records


NVME_HEADER_TOKENS = {
    "access",
    "attributes",
    "bits",
    "bit",
    "cdw",
    "command",
    "commanddword",
    "commandname",
    "commandopcode",
    "commandscope",
    "commandtype",
    "controller",
    "controllerfield",
    "controllersupport",
    "controllersupportrequirements",
    "datastructure",
    "datastructurefield",
    "description",
    "dword",
    "feature",
    "featureidentifier",
    "fid",
    "field",
    "fieldname",
    "lid",
    "log",
    "logidentifier",
    "logpage",
    "logpageidentifier",
    "name",
    "namespace",
    "namespacefield",
    "namespacesupport",
    "namespacesupportrequirements",
    "nvmsubsystem",
    "offset",
    "opcode",
    "parameter",
    "pointer",
    "pointerfield",
    "pointertype",
    "property",
    "queue",
    "queuefield",
    "queuetype",
    "register",
    "registername",
    "reset",
    "resetdefault",
    "sc",
    "scope",
    "sct",
    "status",
    "statuscode",
    "statuscodetype",
    "statuscodevalue",
    "structure",
    "subsystem",
    "support",
    "value",
}
PCIE_HEADER_TOKENS = {
    "access",
    "address",
    "bits",
    "capability",
    "description",
    "field",
    "offset",
    "register",
    "value",
}
OCP_HEADER_TOKENS = {
    "command",
    "description",
    "feature",
    "featureidentifier",
    "formfactor",
    "id",
    "log",
    "logidentifier",
    "must",
    "nvme",
    "optional",
    "profile",
    "requirement",
    "requirementdescription",
    "requirementid",
    "requirementtext",
    "section",
    "security",
    "shall",
    "ssd",
    "status",
    "telemetry",
}
TCG_HEADER_TOKENS = {
    "authority",
    "bits",
    "bytes",
    "description",
    "field",
    "key",
    "keymanagement",
    "lockingrange",
    "method",
    "object",
    "protocolid",
    "securitydescription",
    "securityfield",
    "securityprovider",
    "session",
    "sessionstate",
    "uid",
    "value",
}
SPDM_HEADER_TOKENS = {
    "algorithm",
    "algorithmtype",
    "certificate",
    "certificateslot",
    "code",
    "description",
    "keyexchange",
    "message",
    "messagecode",
    "measurement",
    "measurementindex",
    "request",
    "response",
    "session",
    "sessionstate",
    "slot",
    "state",
    "value",
}
MANUAL_REQUIREMENT_TOKENS = OCP_HEADER_TOKENS | {
    "customer",
    "customerid",
    "customerrequirement",
    "id",
    "must",
    "requirementdescription",
    "requirementid",
    "reqid",
    "shall",
}
MANUAL_REQUIREMENT_ID_FIELDS = (
    "Requirement ID",
    "Req ID",
    "ID",
    "Requirement",
    "Customer Requirement ID",
    "Customer Req ID",
)
MANUAL_DESCRIPTION_FIELDS = (
    "Description",
    "Requirement Description",
    "Customer Requirement",
    "Requirement Text",
    "Requirement",
)

DOMAIN_ADAPTER_REGISTRY_VERSION = "1.0"


@dataclass(frozen=True)
class DomainAdapterSpec:
    """Stable registry metadata for a built-in domain adapter."""

    name: str
    ssd_agent_domain: str
    ssd_agent_spec_type: str
    keyword_profile: str
    header_tokens: frozenset[str]
    unit_taxonomy: tuple[str, ...]
    revision_hints: tuple[str, ...]
    evaluator_hooks: tuple[str, ...] = ()
    compatible_adapters: tuple[str, ...] = ()
    required_normalized_fields: dict[str, tuple[str, ...]] | None = None

    @property
    def compatibility_group(self) -> str:
        if self.name in {"nvme", "ocp", "pcie"}:
            return "storage-technical-spec"
        if self.name in {"tcg", "spdm"}:
            return "security-technical-spec"
        if self.name in {"customer-requirements", "manual"}:
            return "customer-requirement-spec"
        return f"{self.name}-technical-spec"


NVME_UNIT_TAXONOMY = (
    "command",
    "command_dword_field",
    "command_pointer_field",
    "log_page",
    "feature",
    "register_field",
    "status_code",
    "queue_field",
    "namespace_field",
    "controller_field",
    "support_requirement",
    "data_structure_field",
    "enum_value",
)
NVME_REQUIRED_NORMALIZED_FIELDS = {
    "command": ("opcode",),
    "log_page": ("log_identifier",),
    "feature": ("feature_identifier",),
    "register_field": ("field_name", "register_name", "bit_range"),
    "status_code": ("status_code_value",),
    "queue_field": ("field_name",),
    "namespace_field": ("field_name",),
    "controller_field": ("field_name",),
    "data_structure_field": ("field_name",),
    "command_dword_field": ("command_dword", "field_name", "bit_range"),
    "command_pointer_field": ("pointer_type", "field_name"),
}
OCP_REQUIRED_NORMALIZED_FIELDS = {
    "requirement": ("requirement_id", "requirement_prefix", "requirement_family"),
}
DOMAIN_ADAPTER_REGISTRY: dict[DomainAdapterMode, DomainAdapterSpec] = {
    DomainAdapterMode.NVME: DomainAdapterSpec(
        name=DomainAdapterMode.NVME.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="NVMe",
        keyword_profile="nvme-technical-header-tokens",
        header_tokens=frozenset(NVME_HEADER_TOKENS),
        unit_taxonomy=NVME_UNIT_TAXONOMY,
        revision_hints=("nvme-base", "nvm-command-set", "revision-pattern:nvme"),
        evaluator_hooks=("ssd_rag_contract", "latest_nvme_base_benchmark", "latest_nvme_command_set_eval"),
        compatible_adapters=("ocp", "pcie"),
        required_normalized_fields=NVME_REQUIRED_NORMALIZED_FIELDS,
    ),
    DomainAdapterMode.PCIE: DomainAdapterSpec(
        name=DomainAdapterMode.PCIE.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="PCIe",
        keyword_profile="pcie-register-header-tokens",
        header_tokens=frozenset(PCIE_HEADER_TOKENS),
        unit_taxonomy=("register_field",),
        revision_hints=("pcie-base", "pcie-capability-registers"),
        evaluator_hooks=("ssd_rag_contract",),
        compatible_adapters=("nvme", "ocp"),
        required_normalized_fields={"register_field": ("name", "value", "field_name", "bit_range")},
    ),
    DomainAdapterMode.OCP: DomainAdapterSpec(
        name=DomainAdapterMode.OCP.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="OCP",
        keyword_profile="ocp-requirement-header-tokens",
        header_tokens=frozenset(OCP_HEADER_TOKENS),
        unit_taxonomy=("requirement",),
        revision_hints=("ocp-datacenter-nvme-ssd", "requirement-id"),
        evaluator_hooks=("ssd_rag_contract", "latest_ocp_datacenter_nvme_ssd_benchmark"),
        compatible_adapters=("nvme", "pcie", "tcg", "spdm"),
        required_normalized_fields=OCP_REQUIRED_NORMALIZED_FIELDS,
    ),
    DomainAdapterMode.TCG: DomainAdapterSpec(
        name=DomainAdapterMode.TCG.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="TCG",
        keyword_profile="tcg-security-header-tokens",
        header_tokens=frozenset(TCG_HEADER_TOKENS),
        unit_taxonomy=(
            "security_method",
            "security_object",
            "security_authority",
            "security_field",
            "security_provider",
            "locking_range",
            "key_management",
            "session_state",
        ),
        revision_hints=("tcg-storage", "opal", "enterprise"),
        evaluator_hooks=("ssd_rag_contract",),
        compatible_adapters=("ocp",),
        required_normalized_fields={
            "security_method": ("method", "uid", "name"),
            "security_object": ("security_object", "uid", "name"),
            "security_authority": ("authority", "uid", "name"),
            "security_field": ("security_field", "name"),
            "security_provider": ("security_provider", "name"),
            "locking_range": ("locking_range", "name"),
            "key_management": ("key_name", "name"),
            "session_state": ("session_state", "name"),
        },
    ),
    DomainAdapterMode.SPDM: DomainAdapterSpec(
        name=DomainAdapterMode.SPDM.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="SPDM",
        keyword_profile="spdm-security-header-tokens",
        header_tokens=frozenset(SPDM_HEADER_TOKENS),
        unit_taxonomy=(
            "spdm_message",
            "spdm_request_response",
            "spdm_measurement",
            "spdm_certificate",
            "spdm_algorithm",
            "spdm_key_exchange",
            "spdm_session",
        ),
        revision_hints=("dmtf-spdm", "security-protocol-message"),
        evaluator_hooks=("ssd_rag_contract",),
        compatible_adapters=("ocp",),
        required_normalized_fields={
            "spdm_message": ("message", "message_code", "name"),
            "spdm_request_response": ("request", "response", "name"),
            "spdm_measurement": ("measurement", "name"),
            "spdm_certificate": ("certificate", "name"),
            "spdm_algorithm": ("algorithm", "name"),
            "spdm_key_exchange": ("key_exchange", "name"),
            "spdm_session": ("session_state", "name"),
        },
    ),
    DomainAdapterMode.CUSTOMER_REQUIREMENTS: DomainAdapterSpec(
        name=DomainAdapterMode.CUSTOMER_REQUIREMENTS.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="CustomerRequirement",
        keyword_profile="customer-requirement-header-tokens",
        header_tokens=frozenset(OCP_HEADER_TOKENS | {"id", "reqid", "shall", "must"}),
        unit_taxonomy=("requirement",),
        revision_hints=("customer-requirement", "customer-requirement-id"),
        evaluator_hooks=("ssd_rag_contract",),
        compatible_adapters=("manual", "nvme", "ocp"),
        required_normalized_fields={"requirement": ("requirement_id", "name", "value")},
    ),
    DomainAdapterMode.MANUAL: DomainAdapterSpec(
        name=DomainAdapterMode.MANUAL.value,
        ssd_agent_domain="HIL",
        ssd_agent_spec_type="CustomerRequirement",
        keyword_profile="manual-domain-adapter-keywords",
        header_tokens=frozenset(MANUAL_REQUIREMENT_TOKENS),
        unit_taxonomy=("requirement", "manual_field"),
        revision_hints=("manual-domain-adapter", "customer-requirement"),
        evaluator_hooks=("ssd_rag_contract",),
        compatible_adapters=("customer-requirements", "nvme", "ocp"),
        required_normalized_fields={
            "requirement": ("requirement_id", "name", "value"),
            "manual_field": ("name", "value"),
        },
    ),
}


def supported_domain_adapter_specs() -> tuple[DomainAdapterSpec, ...]:
    """Return stable metadata for all built-in non-default domain adapters."""
    return tuple(DOMAIN_ADAPTER_REGISTRY.values())


def get_domain_adapter_spec(domain_adapter: DomainAdapterMode | str) -> DomainAdapterSpec:
    """Return registry metadata for a supported domain adapter."""
    if not isinstance(domain_adapter, DomainAdapterMode):
        domain_adapter = DomainAdapterMode(domain_adapter)
    try:
        return DOMAIN_ADAPTER_REGISTRY[domain_adapter]
    except KeyError as exc:
        raise ValueError(f"Domain adapter does not have registry metadata: {domain_adapter.value}") from exc


def _adapter_metadata(spec: DomainAdapterSpec, *, adapter_profile: str, unit_type: str) -> dict[str, Any]:
    required_fields = (spec.required_normalized_fields or {}).get(unit_type, ())
    return {
        "registry_version": DOMAIN_ADAPTER_REGISTRY_VERSION,
        "adapter": spec.name,
        "adapter_profile": adapter_profile,
        "ssd_agent_domain": spec.ssd_agent_domain,
        "ssd_agent_spec_type": spec.ssd_agent_spec_type,
        "keyword_profile": spec.keyword_profile,
        "unit_taxonomy": list(spec.unit_taxonomy),
        "revision_hints": list(spec.revision_hints),
        "evaluator_hooks": list(spec.evaluator_hooks),
        "required_normalized_fields": list(required_fields),
    }


def _cross_spec_compatibility(spec: DomainAdapterSpec) -> dict[str, Any]:
    return {
        "compatibility_group": spec.compatibility_group,
        "compatible_adapters": list(spec.compatible_adapters),
        "source_id_fields": [
            "source_sha256",
            "source_dedupe_key",
            "stable_source_id",
            "stable_requirement_seed",
        ],
        "stable_id_policy": "preserve_pdf2md_stable_source_metadata",
    }


def _clean_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _split_manual_adapter_keywords(value: str | None) -> tuple[str, ...]:
    if not value:
        return ()
    keywords: list[str] = []
    seen: set[str] = set()
    for raw_part in re.split(r"[,;\n]+", value):
        keyword = raw_part.strip()
        if not keyword:
            continue
        cleaned = _clean_key(keyword)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        keywords.append(cleaned)
    return tuple(keywords)


def _adapter_profile(domain_adapter: DomainAdapterMode, manual_adapter_label: str | None) -> str:
    if domain_adapter is not DomainAdapterMode.MANUAL:
        return domain_adapter.value
    label = re.sub(r"\s+", " ", (manual_adapter_label or "").strip())
    return label[:120] if label else DomainAdapterMode.MANUAL.value


def _cell_value(cells: dict[str, Any], *names: str) -> str | None:
    by_clean_key = {_clean_key(key): value for key, value in cells.items()}
    for name in names:
        value = by_clean_key.get(_clean_key(name))
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


OCP_REQUIREMENT_ID_PATTERN = re.compile(
    r"^(?P<prefix>[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*)-(?P<number>\d+[A-Za-z]?)$",
    re.IGNORECASE,
)
OCP_HEX_ID_PATTERN = re.compile(
    r"\b(?:0x[0-9A-Fa-f]{1,4}|[0-9A-Fa-f]{1,4}h)\b",
)
OCP_COMMAND_NAMES = (
    "Dataset Management",
    "Directive Receive",
    "Directive Send",
    "Format NVM",
    "Get Features",
    "Get Log Page",
    "Identify",
    "Sanitize",
    "Set Features",
    "Write Zeroes",
    "Compare",
    "Flush",
    "Read",
    "Write",
)
OCP_SECURITY_PROTOCOLS = ("SPDM", "TCG", "IEEE 1667", "Opal")
OCP_FORM_FACTORS = ("E1.S", "E1.L", "E3.S", "E3.L", "E3", "M.2", "U.2", "U.3", "SFF-8639")


def _ocp_requirement_id(value: str | None) -> str | None:
    text = re.sub(r"\s+", "", str(value or "").strip())
    if not text:
        return None
    return text


def _ocp_requirement_prefix(requirement_id: str | None) -> str | None:
    req_id = _ocp_requirement_id(requirement_id)
    if not req_id:
        return None
    match = OCP_REQUIREMENT_ID_PATTERN.fullmatch(req_id)
    if match:
        return match.group("prefix")
    if "-" in req_id:
        return req_id.rsplit("-", 1)[0]
    return None


def _ocp_requirement_number(requirement_id: str | None) -> str | None:
    req_id = _ocp_requirement_id(requirement_id)
    if not req_id:
        return None
    match = OCP_REQUIREMENT_ID_PATTERN.fullmatch(req_id)
    if match:
        return match.group("number")
    if "-" in req_id:
        return req_id.rsplit("-", 1)[1]
    return None


def _ocp_requirement_family(prefix: str | None, text: str) -> str | None:
    upper = str(prefix or "").upper()
    lowered = text.lower()
    if upper.startswith("NVME-OPT") or "feature identifier" in lowered:
        return "feature"
    if upper.startswith("NVME"):
        return "nvme"
    if "LOG" in upper or upper in {"GLP", "SLOG", "ERL", "SMART"} or "log identifier" in lowered or "log page" in lowered:
        return "log_page"
    if upper.startswith(("TEL", "LM", "STAT", "EVT")) or "telemetry" in lowered or "statistic identifier" in lowered:
        return "telemetry"
    if upper.startswith("CTO") or "command timeout" in lowered:
        return "command_timeout"
    if upper.startswith(("SEC", "TCG", "SPDM", "S1667")):
        return "security"
    if any(protocol.lower() in lowered for protocol in OCP_SECURITY_PROTOCOLS):
        return "security"
    if upper.startswith("PCI"):
        return "pcie"
    if upper.startswith("THM") or "thermal" in lowered:
        return "thermal"
    if upper.startswith("FF") or any(form_factor.lower() in lowered for form_factor in OCP_FORM_FACTORS):
        return "form_factor"
    if upper.startswith("PLP") or "power loss" in lowered:
        return "power_loss_protection"
    if upper.startswith("REL") or "reliability" in lowered:
        return "reliability"
    if upper.startswith(("END", "EOL", "SLIFE", "RETC")):
        return "endurance"
    if upper.startswith("LABL") or "label" in lowered:
        return "labeling"
    if upper.startswith("COMP") or "compliance" in lowered:
        return "compliance"
    if not upper:
        return None
    return re.sub(r"[^a-z0-9]+", "_", upper.lower()).strip("_")


def _ocp_section_context(value: str | None, full_text: str) -> str | None:
    text = f"{value or ''} {full_text}".lower()
    if "telemetry" in text or "statistic" in text or "event fifo" in text:
        return "telemetry"
    if "feature" in text:
        return "feature"
    if "log page" in text or "log identifier" in text or "smart" in text:
        return "log_page"
    if "security" in text or "spdm" in text or "tcg" in text:
        return "security"
    if "thermal" in text:
        return "thermal"
    if "form factor" in text or any(form_factor.lower() in text for form_factor in OCP_FORM_FACTORS):
        return "form_factor"
    if "pcie" in text or "pci express" in text:
        return "pcie"
    if "nvme" in text:
        return "nvme"
    return None


def _ocp_normative_strength(text: str) -> str | None:
    lowered = text.lower()
    if re.search(r"\bshall\b", lowered):
        return "shall"
    if re.search(r"\bmust\b", lowered):
        return "must"
    if re.search(r"\bshould\b", lowered):
        return "should"
    if re.search(r"\bmay\b", lowered):
        return "may"
    if re.search(r"\boptional\b", lowered):
        return "optional"
    return None


def _ocp_first_hex_after(text: str, *labels: str) -> str | None:
    for label in labels:
        pattern = re.compile(rf"\b{re.escape(label)}\b\s*(?:=|is|:)?\s*(?P<value>0x[0-9A-Fa-f]+|[0-9A-Fa-f]{{1,4}}h)\b", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match.group("value")
    return None


def _ocp_related_command(text: str) -> str | None:
    for command in OCP_COMMAND_NAMES:
        if re.search(rf"\b{re.escape(command)}\b(?:\s+command)?", text, re.IGNORECASE):
            return command
    return None


def _ocp_related_token(text: str, candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if re.search(rf"\b{re.escape(candidate)}\b", text, re.IGNORECASE):
            return candidate
    return None


def _ocp_text_from_cells(cells: dict[str, Any]) -> str:
    return " ".join(str(value).strip() for value in cells.values() if str(value).strip())


def _nvme_pointer_type(value: str | None) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    if re.search(r"\bmetadata\s+pointer\b", text) or "mptr" in text:
        return "metadata"
    if re.search(r"\bdata\s+pointer\b", text) or re.search(r"\bdptr\b", text):
        return "data"
    return str(value).strip()


def _manual_token_cell_value(cells: dict[str, Any], manual_tokens: set[str]) -> tuple[str, str] | None:
    for key, value in cells.items():
        if _clean_key(str(key)) not in manual_tokens:
            continue
        text = str(value).strip()
        if text:
            return str(key), text
    return None


def _known_domain_row(record: dict[str, Any], tokens: set[str]) -> bool:
    headers = record.get("headers")
    cells = record.get("cells")
    if not isinstance(headers, list) or not isinstance(cells, dict):
        return False
    normalized_headers = {_clean_key(str(header)) for header in headers}
    return len(normalized_headers & tokens) >= 2


def _reason_prefix(domain_adapter: DomainAdapterMode) -> str:
    return domain_adapter.value.replace("-", "_")


def _unit_from_row(
    record: dict[str, Any],
    *,
    domain_adapter: DomainAdapterMode,
    manual_tokens: set[str] | None = None,
) -> tuple[str, str, str | None, str | None, list[str]] | None:
    cells = record.get("cells")
    if not isinstance(cells, dict):
        return None
    headers = record.get("headers")
    row_keys = {_clean_key(str(key)) for key in cells}
    if isinstance(headers, list):
        row_keys.update(_clean_key(str(header)) for header in headers)
    prefix = _reason_prefix(domain_adapter)
    command = _cell_value(cells, "Command", "Command Name", "Name")
    opcode = _cell_value(cells, "Opcode", "Command Opcode")
    field = _cell_value(
        cells,
        "Field",
        "Field Name",
        "Parameter",
        "Command Dword Field",
        "CDW Field",
        "Dword Field",
        "Pointer Field",
        "Data Pointer Field",
        "Metadata Pointer Field",
        "Queue Field",
        "Namespace Field",
        "Controller Field",
        "Data Structure Field",
    )
    bits = _cell_value(cells, "Bits", "Bit", "Bit Range")
    value = _cell_value(cells, "Value")
    description = _cell_value(cells, "Description", "Meaning", "Requirement Description", "Security Description")
    requirement_id = _cell_value(cells, "Requirement ID", "Req ID", "ID", "Requirement")
    capability = _cell_value(cells, "Capability", "Register", "Register Name")
    method = _cell_value(cells, "Method", "Method ID")
    security_object = _cell_value(cells, "Object", "Object ID")
    security_provider = _cell_value(cells, "Security Provider", "SP", "Provider")
    locking_range = _cell_value(cells, "Locking Range", "Range")
    key_name = _cell_value(cells, "Key", "Key Name", "Key Management")
    session_state = _cell_value(cells, "Session State", "Session", "State")
    authority = _cell_value(cells, "Authority")
    uid = _cell_value(cells, "UID", "Protocol ID", "ProtocolID")
    security_field = _cell_value(cells, "Security Field", "Field", "Parameter")
    message = _cell_value(cells, "Message", "Message Name", "Command")
    message_code = _cell_value(cells, "Message Code", "Code", "Request Code", "Response Code", "Opcode")
    request = _cell_value(cells, "Request", "Request Message")
    response = _cell_value(cells, "Response", "Response Message")
    measurement = _cell_value(cells, "Measurement", "Measurement Index", "Measurement Block", "Measurement Type")
    certificate = _cell_value(cells, "Certificate", "Certificate Slot", "Slot")
    algorithm = _cell_value(cells, "Algorithm", "Algorithm Type", "Base Asym Algo", "Hash Algorithm")
    key_exchange = _cell_value(cells, "Key Exchange", "KeyExchange", "Key Exchange Parameter")
    spdm_session = _cell_value(cells, "Session", "Session State", "State")
    manual_tokens = manual_tokens or set()

    if domain_adapter in {DomainAdapterMode.OCP, DomainAdapterMode.CUSTOMER_REQUIREMENTS} and requirement_id:
        return "requirement", requirement_id, requirement_id, description, [f"{prefix}_requirement_id_row"]
    if domain_adapter is DomainAdapterMode.MANUAL:
        manual_requirement_id = _cell_value(cells, *MANUAL_REQUIREMENT_ID_FIELDS)
        manual_description = _cell_value(cells, *MANUAL_DESCRIPTION_FIELDS) or description
        if manual_requirement_id:
            return (
                "requirement",
                manual_requirement_id,
                manual_requirement_id,
                manual_description,
                [f"{prefix}_requirement_id_row"],
            )
        manual_match = _manual_token_cell_value(cells, manual_tokens)
        if manual_match is not None:
            header, name = manual_match
            unit_type = (
                "requirement"
                if any("requirement" in _clean_key(str(cell_header)) for cell_header in cells)
                else "manual_field"
            )
            return unit_type, name, value or name, manual_description, [f"{prefix}_keyword_row"]
    if domain_adapter is DomainAdapterMode.TCG:
        if method:
            return "security_method", method, value or uid or opcode, description, [f"{prefix}_security_method_row"]
        if security_provider:
            return "security_provider", security_provider, uid or value or opcode, description, [f"{prefix}_security_provider_row"]
        if locking_range:
            return "locking_range", locking_range, bits or value or uid, description, [f"{prefix}_locking_range_row"]
        if key_name:
            return "key_management", key_name, value or uid or opcode, description, [f"{prefix}_key_management_row"]
        if session_state:
            return "session_state", session_state, value or uid or opcode, description, [f"{prefix}_session_state_row"]
        if security_object:
            return "security_object", security_object, uid or value or opcode, description, [f"{prefix}_security_object_row"]
        if authority:
            return "security_authority", authority, uid or value or opcode, description, [f"{prefix}_security_authority_row"]
        if uid and description:
            return "security_object", uid, uid, description, [f"{prefix}_security_uid_row"]
        if security_field and description:
            return "security_field", security_field, bits or value or uid, description, [f"{prefix}_security_field_row"]
    if domain_adapter is DomainAdapterMode.SPDM:
        if message and message_code:
            return "spdm_message", message, message_code, description, [f"{prefix}_message_code_row"]
        if request and response:
            return "spdm_request_response", f"{request} -> {response}", response, description, [f"{prefix}_request_response_row"]
        if measurement:
            return "spdm_measurement", measurement, value or bits or message_code, description, [f"{prefix}_measurement_row"]
        if certificate:
            return "spdm_certificate", certificate, value or message_code, description, [f"{prefix}_certificate_row"]
        if algorithm:
            return "spdm_algorithm", algorithm, value or message_code, description, [f"{prefix}_algorithm_row"]
        if key_exchange:
            return "spdm_key_exchange", key_exchange, value or message_code, description, [f"{prefix}_key_exchange_row"]
        if spdm_session:
            return "spdm_session", spdm_session, value or message_code, description, [f"{prefix}_session_row"]
    if domain_adapter is DomainAdapterMode.PCIE and (capability or field):
        return "register_field", capability or field or "", bits or value, description, [f"{prefix}_register_or_capability_row"]

    if domain_adapter is DomainAdapterMode.NVME:
        log_identifier = _cell_value(cells, "Log Identifier", "LID", "Log Page", "Log Page Identifier", "Identifier")
        feature_identifier = _cell_value(cells, "Feature Identifier", "FID", "Feature")
        register = _cell_value(cells, "Register", "Register Name", "Property")
        offset = _cell_value(cells, "Offset", "Address")
        status_code_type = _cell_value(cells, "Status Code Type", "SCT")
        status_code_value = _cell_value(cells, "Status Code", "Status Code Value", "SC", "Code")
        controller_support = _cell_value(cells, "Controller Support", "Controller Support Requirements")
        namespace_support = _cell_value(cells, "Namespace Support", "Namespace Support Requirements", "NVM Subsystem")
        support = _cell_value(cells, "Support", "Supported", "Support Requirement")
        scope = _cell_value(cells, "Scope", "NVM Subsystem")
        queue = _cell_value(cells, "Queue", "Queue Type")
        data_structure = _cell_value(cells, "Data Structure", "Structure")
        command_dword = _cell_value(cells, "Command Dword", "Command DW", "CDW", "Dword", "DW")
        pointer = _cell_value(cells, "Pointer", "Pointer Type", "Command Pointer", "Data Pointer", "Metadata Pointer")
        if command and opcode:
            return "command", command, opcode, description, [f"{prefix}_command_opcode_row"]
        if log_identifier:
            return "log_page", log_identifier, log_identifier, description, [f"{prefix}_log_identifier_row"]
        if feature_identifier:
            return "feature", feature_identifier, feature_identifier, description, [f"{prefix}_feature_identifier_row"]
        if status_code_type and status_code_value:
            return "status_code", status_code_value, status_code_value, description, [f"{prefix}_status_code_row"]
        if command_dword and (field or bits):
            return "command_dword_field", field or command_dword, bits or command_dword, description, [
                f"{prefix}_command_dword_row"
            ]
        if pointer and (field or description):
            return "command_pointer_field", field or pointer, _nvme_pointer_type(pointer), description, [
                f"{prefix}_command_pointer_row"
            ]
        if controller_support or namespace_support or support:
            name = _cell_value(cells, "Requirement", "Requirement ID", "Name") or scope or "support_requirement"
            return (
                "support_requirement",
                name,
                controller_support or namespace_support or support,
                description,
                [f"{prefix}_support_requirement_row"],
            )
        if field and (queue or {"queue", "queuefield"} & row_keys):
            return "queue_field", field, bits or value, description, [f"{prefix}_queue_field_row"]
        if field and (
            namespace_support
            or (scope or "").lower() == "namespace"
            or _cell_value(cells, "Namespace", "NVM Subsystem")
            or {"namespace", "namespacefield", "nvmsubsystem"} & row_keys
        ):
            return "namespace_field", field, bits or value, description, [f"{prefix}_namespace_field_row"]
        if field and (_cell_value(cells, "Controller", "Controller Field") or {"controller", "controllerfield"} & row_keys):
            return "controller_field", field, bits or value, description, [f"{prefix}_controller_field_row"]
        if field and (data_structure or {"datastructure", "datastructurefield", "structure"} & row_keys):
            return "data_structure_field", field, bits or value, description, [f"{prefix}_data_structure_field_row"]
        if field and (register or offset):
            return "register_field", field, bits or value or offset, description, [f"{prefix}_register_field_row"]
        if field and bits:
            return "register_field", field, bits, description, [f"{prefix}_register_field_row"]
        if value and description:
            return "enum_value", value, value, description, [f"{prefix}_enum_value_row"]

    if command and opcode:
        return "command", command, opcode, description, [f"{prefix}_command_opcode_row"]
    if opcode:
        return "opcode", opcode, opcode, description, [f"{prefix}_opcode_row"]
    if field and bits:
        return "register_field", field, bits, description, [f"{prefix}_register_field_row"]
    if value and description:
        return "enum_value", value, value, description, [f"{prefix}_enum_value_row"]
    if field and description:
        return "field", field, bits or value, description, [f"{prefix}_field_row"]
    return None


def _domain_tokens(domain_adapter: DomainAdapterMode, manual_tokens: set[str] | None = None) -> set[str]:
    if domain_adapter in DOMAIN_ADAPTER_REGISTRY:
        tokens = set(get_domain_adapter_spec(domain_adapter).header_tokens)
        if domain_adapter is DomainAdapterMode.MANUAL:
            tokens.update(manual_tokens or set())
        return tokens
    return set()


def _unit_from_technical_record(
    record: dict[str, Any],
    *,
    domain_adapter: DomainAdapterMode,
    manual_tokens: set[str] | None = None,
) -> tuple[str, str, str | None, str | None, list[str]] | None:
    unit_type = str(record.get("unit_type") or "")
    raw_cells = record.get("raw_cells")
    if not isinstance(raw_cells, dict):
        raw_cells = {}
    field = str(record.get("field_name") or "").strip()
    value = str(record.get("value") or record.get("opcode") or record.get("bit_range") or "").strip()
    description = str(record.get("meaning") or "").strip() or None
    command = str(record.get("command") or "").strip()
    log_identifier = str(record.get("log_identifier") or "").strip()
    feature_identifier = str(record.get("feature_identifier") or "").strip()
    requirement_ref = str(record.get("requirement_ref") or "").strip()
    status_code_value = str(record.get("status_code_value") or "").strip()
    controller_support = str(record.get("controller_support") or "").strip()
    namespace_support = str(record.get("namespace_support") or "").strip()
    scope = str(record.get("scope") or "").strip()
    offset = str(record.get("offset") or "").strip()
    command_dword = str(record.get("command_dword") or "").strip()
    pointer_type = str(record.get("pointer_type") or "").strip()

    if domain_adapter is DomainAdapterMode.NVME:
        if unit_type == "command_opcode" and command:
            opcode = str(record.get("opcode") or value).strip()
            return "command", command, opcode or None, description, ["nvme_command_opcode_row"]
        if unit_type == "log_page" and log_identifier:
            return "log_page", log_identifier, log_identifier, description, ["nvme_log_identifier_row"]
        if unit_type == "feature_identifier" and feature_identifier:
            return "feature", feature_identifier, feature_identifier, description, ["nvme_feature_identifier_row"]
        if unit_type == "status_code" and status_code_value:
            return "status_code", status_code_value, status_code_value, description, ["nvme_status_code_row"]
        if unit_type == "command_dword_field" and (field or command_dword):
            return "command_dword_field", field or command_dword, value or command_dword or None, description, [
                "nvme_command_dword_row"
            ]
        if unit_type == "command_pointer_field" and (field or pointer_type):
            return "command_pointer_field", field or pointer_type, pointer_type or value or None, description, [
                "nvme_command_pointer_row"
            ]
        if unit_type == "support_requirement":
            name = _cell_value(raw_cells, "Requirement", "Requirement ID", "Name") or scope or requirement_ref or "support_requirement"
            return (
                "support_requirement",
                name,
                controller_support or namespace_support or value or None,
                description,
                ["nvme_support_requirement_row"],
            )
        if unit_type in {"queue_field", "namespace_field", "controller_field", "data_structure_field"} and field:
            return unit_type, field, value or None, description, [f"nvme_{unit_type}_row"]
        if unit_type in {"bitfield", "register_field"} and field:
            return "register_field", field, value or offset or None, description, ["nvme_register_field_row"]
        if unit_type == "enum_value" and value:
            return "enum_value", value, value, description, ["nvme_enum_value_row"]

    if domain_adapter is DomainAdapterMode.PCIE:
        register = _cell_value(raw_cells, "Register", "Capability", "Field", "Name") or field
        if unit_type in {"register_field", "bitfield", "technical_parameter"} and register:
            return "register_field", register, value or None, description, ["pcie_register_or_capability_row"]

    if domain_adapter is DomainAdapterMode.OCP:
        req_id = requirement_ref or _cell_value(raw_cells, "Requirement ID", "Requirement", "ID")
        if req_id:
            return "requirement", req_id, req_id, description, ["ocp_requirement_id_row"]

    if domain_adapter is DomainAdapterMode.TCG:
        method = _cell_value(raw_cells, "Method", "Method ID")
        security_object = _cell_value(raw_cells, "Object", "Object ID")
        security_provider = _cell_value(raw_cells, "Security Provider", "SP", "Provider")
        locking_range = _cell_value(raw_cells, "Locking Range", "Range")
        key_name = _cell_value(raw_cells, "Key", "Key Name", "Key Management")
        session_state = _cell_value(raw_cells, "Session State", "Session", "State")
        authority = _cell_value(raw_cells, "Authority")
        uid = _cell_value(raw_cells, "UID", "Protocol ID", "ProtocolID")
        security_field = _cell_value(raw_cells, "Security Field", "Field", "Parameter") or field
        if method or unit_type == "security_method":
            return "security_method", method or field, uid or value or None, description, ["tcg_security_method_row"]
        if security_provider or unit_type == "security_provider":
            return "security_provider", security_provider or field, uid or value or None, description, ["tcg_security_provider_row"]
        if locking_range or unit_type == "locking_range":
            return "locking_range", locking_range or field, uid or value or None, description, ["tcg_locking_range_row"]
        if key_name or unit_type == "key_management":
            return "key_management", key_name or field, uid or value or None, description, ["tcg_key_management_row"]
        if session_state or unit_type == "session_state":
            return "session_state", session_state or field, uid or value or None, description, ["tcg_session_state_row"]
        if security_object or unit_type == "security_object":
            return "security_object", security_object or uid or field, uid or value or None, description, ["tcg_security_object_row"]
        if authority or unit_type == "security_authority":
            return "security_authority", authority or field, uid or value or None, description, ["tcg_security_authority_row"]
        if uid and description:
            return "security_object", uid, uid, description, ["tcg_security_uid_row"]
        if unit_type in {"bitfield", "register_field", "technical_parameter", "security_method", "security_field"} and security_field:
            return "security_field", security_field, uid or value or None, description, ["tcg_security_field_row"]

    if domain_adapter is DomainAdapterMode.SPDM:
        message = _cell_value(raw_cells, "Message", "Message Name", "Command") or field or command
        message_code = _cell_value(raw_cells, "Message Code", "Code", "Request Code", "Response Code") or value
        request = _cell_value(raw_cells, "Request", "Request Message")
        response = _cell_value(raw_cells, "Response", "Response Message")
        measurement = _cell_value(raw_cells, "Measurement", "Measurement Index", "Measurement Block", "Measurement Type")
        certificate = _cell_value(raw_cells, "Certificate", "Certificate Slot", "Slot")
        algorithm = _cell_value(raw_cells, "Algorithm", "Algorithm Type", "Base Asym Algo", "Hash Algorithm")
        key_exchange = _cell_value(raw_cells, "Key Exchange", "KeyExchange", "Key Exchange Parameter")
        spdm_session = _cell_value(raw_cells, "Session", "Session State", "State")
        if unit_type == "spdm_message" and message:
            return "spdm_message", message, message_code or None, description, ["spdm_message_code_row"]
        if unit_type == "spdm_request_response" and (request or response):
            name = f"{request or message} -> {response or message_code}".strip()
            return "spdm_request_response", name, response or message_code or None, description, ["spdm_request_response_row"]
        if unit_type == "spdm_measurement" and measurement:
            return "spdm_measurement", measurement, message_code or None, description, ["spdm_measurement_row"]
        if unit_type == "spdm_certificate" and certificate:
            return "spdm_certificate", certificate, message_code or None, description, ["spdm_certificate_row"]
        if unit_type == "spdm_algorithm" and algorithm:
            return "spdm_algorithm", algorithm, message_code or None, description, ["spdm_algorithm_row"]
        if unit_type == "spdm_key_exchange" and key_exchange:
            return "spdm_key_exchange", key_exchange, message_code or None, description, ["spdm_key_exchange_row"]
        if unit_type in {"spdm_session", "session_state"} and spdm_session:
            return "spdm_session", spdm_session, message_code or None, description, ["spdm_session_row"]

    if domain_adapter is DomainAdapterMode.CUSTOMER_REQUIREMENTS:
        req_id = requirement_ref or _cell_value(raw_cells, "Requirement ID", "Req ID", "ID", "Requirement")
        if req_id:
            return "requirement", req_id, req_id, description, ["customer_requirement_id_row"]

    if domain_adapter is DomainAdapterMode.MANUAL:
        manual_description = _cell_value(raw_cells, *MANUAL_DESCRIPTION_FIELDS) or description
        req_id = requirement_ref or _cell_value(raw_cells, *MANUAL_REQUIREMENT_ID_FIELDS)
        if req_id:
            return "requirement", req_id, req_id, manual_description, ["manual_requirement_id_row"]
        manual_match = _manual_token_cell_value(raw_cells, manual_tokens or set())
        if manual_match is not None:
            header, name = manual_match
            unit_type = (
                "requirement"
                if any("requirement" in _clean_key(str(cell_header)) for cell_header in raw_cells)
                else "manual_field"
            )
            return unit_type, name, value or name, manual_description, ["manual_keyword_technical_row"]

    return None


def _page(record: dict[str, Any]) -> int:
    try:
        return int(record.get("page") or 0)
    except (TypeError, ValueError):
        return 0


def _heading_path(record: dict[str, Any]) -> list[str]:
    value = record.get("heading_path")
    return [str(item) for item in value] if isinstance(value, list) else []


def _without_empty_fields(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if value is not None and value != "" and value != []
    }


def _normalized_domain_fields(
    *,
    cells: dict[str, Any],
    domain_adapter: DomainAdapterMode,
    unit_type: str,
    name: str,
    value: str | None,
    base_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    fields = dict(base_fields or {})
    fields.update(
        {
            "unit_type": unit_type,
            "name": name,
            "value": value,
        }
    )
    if domain_adapter is not DomainAdapterMode.OCP:
        fields.pop("source_table_id", None)
        fields.pop("source_table_row_id", None)
    if domain_adapter is DomainAdapterMode.TCG:
        fields.update(
            {
                "method": _cell_value(cells, "Method", "Method ID"),
                "security_object": _cell_value(cells, "Object", "Object ID"),
                "security_provider": _cell_value(cells, "Security Provider", "SP", "Provider"),
                "locking_range": _cell_value(cells, "Locking Range", "Range"),
                "key_name": _cell_value(cells, "Key", "Key Name", "Key Management"),
                "session_state": _cell_value(cells, "Session State", "Session", "State"),
                "authority": _cell_value(cells, "Authority"),
                "uid": _cell_value(cells, "UID", "Protocol ID", "ProtocolID"),
                "security_field": _cell_value(cells, "Security Field", "Field", "Parameter"),
            }
        )
    if domain_adapter is DomainAdapterMode.NVME:
        fields.update(
            {
                "canonical_name": name,
                "opcode": fields.get("opcode") or _cell_value(cells, "Opcode", "Command Opcode"),
                "log_identifier": fields.get("log_identifier")
                or _cell_value(cells, "Log Identifier", "LID", "Log Page", "Log Page Identifier", "Identifier"),
                "feature_identifier": fields.get("feature_identifier")
                or _cell_value(cells, "Feature Identifier", "FID", "Feature"),
                "register_name": fields.get("register_name") or _cell_value(cells, "Register", "Register Name", "Property"),
                "offset": fields.get("offset") or _cell_value(cells, "Offset", "Address"),
                "bit_range": fields.get("bit_range") or _cell_value(cells, "Bits", "Bit", "Bit Range"),
                "field_name": fields.get("field_name")
                or _cell_value(
                    cells,
                    "Field",
                    "Field Name",
                    "Parameter",
                    "Command Dword Field",
                    "CDW Field",
                    "Dword Field",
                    "Pointer Field",
                    "Data Pointer Field",
                    "Metadata Pointer Field",
                    "Queue Field",
                    "Namespace Field",
                    "Controller Field",
                    "Data Structure Field",
                ),
                "command_dword": fields.get("command_dword")
                or _cell_value(cells, "Command Dword", "Command DW", "CDW", "Dword", "DW"),
                "command_scope": fields.get("command_scope")
                or _cell_value(cells, "Command Scope", "Command Type", "Queue Type", "Scope", "Command Set"),
                "queue_type": fields.get("queue_type") or _cell_value(cells, "Queue Type", "Command Type"),
                "pointer_type": fields.get("pointer_type")
                or _nvme_pointer_type(
                    _cell_value(cells, "Pointer", "Pointer Type", "Command Pointer", "Data Pointer", "Metadata Pointer")
                ),
                "command_context": fields.get("command_context"),
                "command_context_source": fields.get("command_context_source"),
                "related_command_unit_id": fields.get("related_command_unit_id"),
                "related_command_opcode": fields.get("related_command_opcode"),
                "relationship_hints": fields.get("relationship_hints"),
                "status_code_type": fields.get("status_code_type") or _cell_value(cells, "Status Code Type", "SCT"),
                "status_code_value": fields.get("status_code_value")
                or _cell_value(cells, "Status Code", "Status Code Value", "SC", "Code"),
                "status_code_group": fields.get("status_code_group"),
                "error_class": fields.get("error_class"),
                "retry_hint": fields.get("retry_hint"),
                "controller_support": fields.get("controller_support")
                or _cell_value(cells, "Controller Support", "Controller Support Requirements"),
                "namespace_support": fields.get("namespace_support")
                or _cell_value(cells, "Namespace Support", "Namespace Support Requirements", "NVM Subsystem"),
                "scope": fields.get("scope") or _cell_value(cells, "Scope", "NVM Subsystem"),
                "access": fields.get("access") or _cell_value(cells, "Access", "Attributes"),
                "reset_default": fields.get("reset_default") or _cell_value(cells, "Reset", "Default", "Reset Default"),
                "requirement_ref": fields.get("requirement_ref")
                or _cell_value(cells, "Requirement ID", "Requirement", "Req ID", "ID"),
            }
        )
    if domain_adapter is DomainAdapterMode.OCP:
        requirement_id = _ocp_requirement_id(
            fields.get("requirement_ref")
            or _cell_value(cells, "Requirement ID", "Requirement", "Req ID", "ID")
            or (value if unit_type == "requirement" else None)
        )
        description = _cell_value(cells, "Requirement Description", "Requirement Text", "Description", "Meaning")
        full_text = f"{_ocp_text_from_cells(cells)} {description or ''} {name} {value or ''}"
        prefix = _ocp_requirement_prefix(requirement_id)
        family = _ocp_requirement_family(prefix, full_text)
        related_log_identifier = (
            fields.get("log_identifier")
            or _cell_value(cells, "Log Identifier", "LID", "Log Page", "Log Page Identifier")
            or _ocp_first_hex_after(full_text, "Log Identifier", "LID")
        )
        related_feature_identifier = (
            fields.get("feature_identifier")
            or _cell_value(cells, "Feature Identifier", "FID", "Feature")
            or _ocp_first_hex_after(full_text, "Feature Identifier", "FID")
        )
        related_statistic_identifier = _cell_value(
            cells,
            "Statistic Identifier",
            "Statistic ID",
            "Telemetry Statistic Identifier",
        ) or _ocp_first_hex_after(full_text, "Statistic Identifier", "Statistic ID")
        related_command = _cell_value(cells, "Command", "Command Name") or _ocp_related_command(full_text)
        relationship_hints: list[str] = []
        if related_command:
            relationship_hints.append("references_nvme_command")
        if related_log_identifier:
            relationship_hints.append("references_nvme_log_page")
        if related_feature_identifier:
            relationship_hints.append("references_nvme_feature")
        if related_statistic_identifier:
            relationship_hints.append("references_telemetry_statistic")
        security_protocol = _ocp_related_token(full_text, OCP_SECURITY_PROTOCOLS)
        form_factor = _ocp_related_token(full_text, OCP_FORM_FACTORS)
        if security_protocol:
            relationship_hints.append("references_security_protocol")
        if form_factor:
            relationship_hints.append("references_form_factor")
        fields.update(
            {
                "requirement_id": requirement_id,
                "requirement_prefix": prefix,
                "requirement_number": _ocp_requirement_number(requirement_id),
                "requirement_family": family,
                "requirement_description": description,
                "normative_strength": _ocp_normative_strength(full_text),
                "ssd_requirement_status": _cell_value(cells, "SSD", "Required", "Optional", "Status"),
                "ocp_profile": _cell_value(cells, "OCP Profile", "Profile", "SSD Profile"),
                "ocp_section_context": _ocp_section_context(
                    fields.get("section_path") or _cell_value(cells, "Section", "Clause"),
                    full_text,
                ),
                "topic": family,
                "related_command": related_command,
                "related_log_identifier": related_log_identifier,
                "related_feature_identifier": related_feature_identifier,
                "related_statistic_identifier": related_statistic_identifier,
                "related_security_protocol": security_protocol,
                "related_form_factor": form_factor,
                "relationship_hints": relationship_hints,
                "source_table_id": fields.get("source_table_id"),
                "source_table_row_id": fields.get("source_table_row_id"),
                "section_path": fields.get("section_path"),
            }
        )
    if domain_adapter is DomainAdapterMode.SPDM:
        fields.update(
            {
                "message": _cell_value(cells, "Message", "Message Name", "Command"),
                "message_code": _cell_value(cells, "Message Code", "Code", "Request Code", "Response Code"),
                "request": _cell_value(cells, "Request", "Request Message"),
                "response": _cell_value(cells, "Response", "Response Message"),
                "measurement": _cell_value(cells, "Measurement", "Measurement Index", "Measurement Block", "Measurement Type"),
                "certificate": _cell_value(cells, "Certificate", "Certificate Slot", "Slot"),
                "algorithm": _cell_value(cells, "Algorithm", "Algorithm Type", "Base Asym Algo", "Hash Algorithm"),
                "key_exchange": _cell_value(cells, "Key Exchange", "KeyExchange", "Key Exchange Parameter"),
                "session_state": _cell_value(cells, "Session", "Session State", "State"),
            }
        )
    if domain_adapter is DomainAdapterMode.MANUAL:
        fields.update(
            {
                "requirement_id": _cell_value(cells, *MANUAL_REQUIREMENT_ID_FIELDS),
                "requirement_description": _cell_value(cells, *MANUAL_DESCRIPTION_FIELDS),
            }
        )
    return _without_empty_fields(fields)


def build_domain_units(
    *,
    domain_adapter: DomainAdapterMode | str,
    rag_tables: list[dict[str, Any]],
    technical_table_records: list[dict[str, Any]] | None = None,
    manual_adapter_label: str | None = None,
    manual_adapter_keywords: str | None = None,
    source_sha256: str = "",
) -> list[dict[str, Any]]:
    """Build opt-in domain-specific RAG records from deterministic table provenance."""
    if not isinstance(domain_adapter, DomainAdapterMode):
        domain_adapter = DomainAdapterMode(domain_adapter)
    if domain_adapter is DomainAdapterMode.NONE:
        return []

    records: list[dict[str, Any]] = []
    manual_tokens = set(_split_manual_adapter_keywords(manual_adapter_keywords))
    adapter_profile = _adapter_profile(domain_adapter, manual_adapter_label)
    adapter_spec = get_domain_adapter_spec(domain_adapter)
    adapter_technical_records = (
        technical_table_records
        if technical_table_records is not None
        else build_technical_table_records(rag_tables, source_sha256=source_sha256)
    )
    for technical_record in adapter_technical_records:
        unit = _unit_from_technical_record(
            technical_record,
            domain_adapter=domain_adapter,
            manual_tokens=manual_tokens,
        )
        if unit is None:
            continue
        unit_type, name, value, description, reasons = unit
        page = _page(technical_record)
        index = len(records) + 1
        source_refs = list(technical_record.get("source_refs") or [])
        source_refs.append(
            {
                "source_type": "technical_table_unit",
                "source_id": technical_record.get("technical_table_unit_id"),
                "page": page,
                "bbox": technical_record.get("bbox"),
            }
        )
        records.append(
            with_stable_source_metadata(
                {
                    "domain_unit_id": f"domain-{domain_adapter.value}-{index:06d}",
                    "domain_unit_index": index,
                    "domain": domain_adapter.value,
                    "adapter_profile": adapter_profile,
                    "adapter_version": "1.0",
                    "adapter_metadata": _adapter_metadata(
                        adapter_spec,
                        adapter_profile=adapter_profile,
                        unit_type=unit_type,
                    ),
                    "cross_spec_compatibility": _cross_spec_compatibility(adapter_spec),
                    "unit_type": unit_type,
                    "name": name,
                    "value": value,
                    "description": description,
                    "text": str(technical_record.get("text") or "").strip(),
                    "normalized_fields": _normalized_domain_fields(
                        cells=technical_record.get("raw_cells")
                        if isinstance(technical_record.get("raw_cells"), dict)
                        else {},
                        domain_adapter=domain_adapter,
                        unit_type=unit_type,
                        name=name,
                        value=value,
                        base_fields={
                            "bit_range": technical_record.get("bit_range"),
                            "field_name": technical_record.get("field_name"),
                            "opcode": technical_record.get("opcode"),
                            "command_dword": technical_record.get("command_dword"),
                            "command_scope": technical_record.get("command_scope"),
                            "queue_type": technical_record.get("queue_type"),
                            "pointer_type": technical_record.get("pointer_type"),
                            "command_context": technical_record.get("command_context"),
                            "command_context_source": technical_record.get("command_context_source"),
                            "related_command_unit_id": technical_record.get("related_command_unit_id"),
                            "related_command_opcode": technical_record.get("related_command_opcode"),
                            "relationship_hints": technical_record.get("relationship_hints"),
                            "log_identifier": technical_record.get("log_identifier"),
                            "feature_identifier": technical_record.get("feature_identifier"),
                            "register_name": technical_record.get("register_name"),
                            "offset": technical_record.get("offset"),
                            "status_code_type": technical_record.get("status_code_type"),
                            "status_code_value": technical_record.get("status_code_value"),
                            "status_code_group": technical_record.get("status_code_group"),
                            "error_class": technical_record.get("error_class"),
                            "retry_hint": technical_record.get("retry_hint"),
                            "controller_support": technical_record.get("controller_support"),
                            "namespace_support": technical_record.get("namespace_support"),
                            "scope": technical_record.get("scope"),
                            "requirement_ref": technical_record.get("requirement_ref"),
                            "access": technical_record.get("access"),
                            "reset_default": technical_record.get("reset_default"),
                            "source_table_id": technical_record.get("table_id"),
                            "source_table_row_id": technical_record.get("table_row_id"),
                            "section_path": " > ".join(_heading_path(technical_record)),
                        },
                    ),
                    "source_refs": source_refs,
                    "page_range": [page, page],
                    "bbox": technical_record.get("bbox"),
                    "heading_path": _heading_path(technical_record),
                    "relationship_hints": list(technical_record.get("relationship_hints") or []),
                    "classification_confidence": 0.9,
                    "classification_reasons": reasons,
                },
                source_sha256=source_sha256,
                requirement_locator_id=str(technical_record.get("table_row_id") or ""),
            )
        )

    for table_row in flatten_rag_table_records(normalize_rag_table_payload(rag_tables)):
        if not _known_domain_row(table_row, _domain_tokens(domain_adapter, manual_tokens)):
            continue
        unit = _unit_from_row(table_row, domain_adapter=domain_adapter, manual_tokens=manual_tokens)
        if unit is None:
            continue
        unit_type, name, value, description, reasons = unit
        page = _page(table_row)
        index = len(records) + 1
        records.append(
            with_stable_source_metadata(
                {
                    "domain_unit_id": f"domain-{domain_adapter.value}-{index:06d}",
                    "domain_unit_index": index,
                    "domain": domain_adapter.value,
                    "adapter_profile": adapter_profile,
                    "adapter_version": "1.0",
                    "adapter_metadata": _adapter_metadata(
                        adapter_spec,
                        adapter_profile=adapter_profile,
                        unit_type=unit_type,
                    ),
                    "cross_spec_compatibility": _cross_spec_compatibility(adapter_spec),
                    "unit_type": unit_type,
                    "name": name,
                    "value": value,
                    "description": description,
                    "text": str(table_row.get("row_text") or "").strip(),
                    "normalized_fields": _normalized_domain_fields(
                        cells=table_row.get("cells") if isinstance(table_row.get("cells"), dict) else {},
                        domain_adapter=domain_adapter,
                        unit_type=unit_type,
                        name=name,
                        value=value,
                        base_fields={
                            "source_table_id": table_row.get("table_id"),
                            "source_table_row_id": table_row.get("table_row_id"),
                            "section_path": " > ".join(_heading_path(table_row)),
                        },
                    ),
                    "source_refs": [
                        {
                            "source_type": "table_row",
                            "source_id": table_row.get("table_row_id"),
                            "page": page,
                            "table_id": table_row.get("table_id"),
                            "row_index": table_row.get("row_index"),
                            "bbox": table_row.get("bbox"),
                        }
                    ],
                    "page_range": [page, page],
                    "bbox": table_row.get("bbox"),
                    "heading_path": _heading_path(table_row),
                    "classification_confidence": 0.88,
                    "classification_reasons": reasons,
                },
                source_sha256=source_sha256,
                requirement_locator_id=str(table_row.get("table_row_id") or ""),
            )
        )
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str | None]] = set()
    for record in records:
        key = (str(record.get("unit_type")), str(record.get("name")), record.get("value"))
        if key in seen:
            continue
        seen.add(key)
        record["domain_unit_id"] = f"domain-{domain_adapter.value}-{len(deduped) + 1:06d}"
        record["domain_unit_index"] = len(deduped) + 1
        deduped.append(record)
    return deduped


def serialize_domain_units_jsonl(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records) + "\n"

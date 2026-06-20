from __future__ import annotations

import json

from pdf2md.models import DomainAdapterMode
from pdf2md.serializers.rag_chunks import build_retrieval_chunks
from pdf2md.serializers.rag_domain_adapters import (
    DOMAIN_ADAPTER_REGISTRY_VERSION,
    build_domain_units,
    get_domain_adapter_spec,
    serialize_domain_units_jsonl,
    supported_domain_adapter_specs,
)
from pdf2md.serializers.rag_tables import normalize_rag_table_payload


def test_domain_adapter_registry_exposes_ssd_agent_contract_metadata() -> None:
    specs = {spec.name: spec for spec in supported_domain_adapter_specs()}

    assert specs["nvme"].ssd_agent_domain == "HIL"
    assert specs["nvme"].ssd_agent_spec_type == "NVMe"
    assert {"command", "command_dword_field", "status_code"} <= set(specs["nvme"].unit_taxonomy)
    assert specs["nvme"].required_normalized_fields["command"] == ("opcode",)
    assert "latest_nvme_command_set_eval" in specs["nvme"].evaluator_hooks
    assert specs["ocp"].ssd_agent_spec_type == "OCP"
    assert specs["ocp"].required_normalized_fields["requirement"] == (
        "requirement_id",
        "requirement_prefix",
        "requirement_family",
    )
    assert specs["caliptra"].ssd_agent_spec_type == "Caliptra"
    assert {"caliptra_asset", "caliptra_mailbox_command", "caliptra_register_field"} <= set(
        specs["caliptra"].unit_taxonomy
    )
    assert "latest_ssd_security_spec_benchmark" in specs["caliptra"].evaluator_hooks
    assert specs["manual"].ssd_agent_spec_type == "CustomerRequirement"
    assert get_domain_adapter_spec(DomainAdapterMode.MANUAL).keyword_profile == "manual-domain-adapter-keywords"


def test_nvme_domain_adapter_extracts_command_and_register_units() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Command", "Opcode", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Command", "Opcode", "Description"],
                        "cells": {"Command": "KV Store", "Opcode": "0x81", "Description": "Store a key value pair"},
                        "row_text": "Command = KV Store | Opcode = 0x81 | Description = Store a key value pair",
                        "bbox": [72.0, 120.0, 420.0, 150.0],
                    }
                ],
            },
            {
                "page": 1,
                "table_index": 2,
                "headers": ["Field", "Bits", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 2,
                        "row_index": 1,
                        "headers": ["Field", "Bits", "Description"],
                        "cells": {"Field": "Reserved", "Bits": "7:4", "Description": "Reserved bits"},
                        "row_text": "Field = Reserved | Bits = 7:4 | Description = Reserved bits",
                    }
                ],
            },
        ]
    )

    records = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables, source_sha256="f" * 64)

    assert [record["unit_type"] for record in records] == ["command", "register_field"]
    assert records[0]["domain_unit_id"] == "domain-nvme-000001"
    assert records[0]["name"] == "KV Store"
    assert records[0]["value"] == "0x81"
    assert records[0]["source_refs"][0]["source_id"] == "page-0001-table-0001-row-0001"
    assert records[0]["source_refs"][1]["source_type"] == "technical_table_unit"
    assert records[0]["source_refs"][1]["source_id"] == "tech-table-000001"
    assert records[1]["source_refs"][0]["source_id"] == "page-0001-table-0002-row-0001"
    assert records[0]["source_sha256"] == "f" * 64
    assert records[0]["source_dedupe_key"] == "page-0001-table-0001-row-0001|tech-table-000001"
    assert len(records[0]["stable_source_id"]) == 40
    assert len(records[0]["stable_requirement_seed"]) == 40
    assert records[0]["adapter_metadata"] == {
        "registry_version": DOMAIN_ADAPTER_REGISTRY_VERSION,
        "adapter": "nvme",
        "adapter_profile": "nvme",
        "ssd_agent_domain": "HIL",
        "ssd_agent_spec_type": "NVMe",
        "keyword_profile": "nvme-technical-header-tokens",
        "unit_taxonomy": list(get_domain_adapter_spec("nvme").unit_taxonomy),
        "revision_hints": list(get_domain_adapter_spec("nvme").revision_hints),
        "evaluator_hooks": list(get_domain_adapter_spec("nvme").evaluator_hooks),
        "required_normalized_fields": ["opcode"],
    }
    assert records[0]["cross_spec_compatibility"] == {
        "compatibility_group": "storage-technical-spec",
        "compatible_adapters": ["ocp", "pcie"],
        "source_id_fields": [
            "source_sha256",
            "source_dedupe_key",
            "stable_source_id",
            "stable_requirement_seed",
        ],
        "stable_id_policy": "preserve_pdf2md_stable_source_metadata",
    }

    jsonl = serialize_domain_units_jsonl(records)
    assert json.loads(jsonl.splitlines()[0])["domain"] == "nvme"


def test_nvme_domain_adapter_populates_expanded_normalized_fields() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 2,
                "table_index": 1,
                "headers": ["SCT", "SC", "Description"],
                "records": [
                    {
                        "page": 2,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["SCT", "SC", "Description"],
                        "cells": {"SCT": "generic", "SC": "0x00", "Description": "Successful completion"},
                        "row_text": "SCT = generic | SC = 0x00 | Description = Successful completion",
                    }
                ],
            },
            {
                "page": 2,
                "table_index": 2,
                "headers": ["Property", "Offset", "Field", "Attributes", "Reset Default", "Description"],
                "records": [
                    {
                        "page": 2,
                        "table_index": 2,
                        "row_index": 1,
                        "headers": ["Property", "Offset", "Field", "Attributes", "Reset Default", "Description"],
                        "cells": {
                            "Property": "CAP",
                            "Offset": "0x0000",
                            "Field": "MQES",
                            "Attributes": "RO",
                            "Reset Default": "0h",
                            "Description": "Maximum queue entries supported",
                        },
                        "row_text": (
                            "Property = CAP | Offset = 0x0000 | Field = MQES | Attributes = RO | "
                            "Reset Default = 0h | Description = Maximum queue entries supported"
                        ),
                    }
                ],
            },
            {
                "page": 2,
                "table_index": 3,
                "headers": ["Controller Support", "Namespace Support", "Scope", "Description"],
                "records": [
                    {
                        "page": 2,
                        "table_index": 3,
                        "row_index": 1,
                        "headers": ["Controller Support", "Namespace Support", "Scope", "Description"],
                        "cells": {
                            "Controller Support": "mandatory",
                            "Namespace Support": "optional",
                            "Scope": "controller",
                            "Description": "Telemetry support requirement",
                        },
                        "row_text": (
                            "Controller Support = mandatory | Namespace Support = optional | Scope = controller | "
                            "Description = Telemetry support requirement"
                        ),
                    }
                ],
            },
            {
                "page": 2,
                "table_index": 4,
                "headers": ["Queue Field", "Bits", "Description"],
                "records": [
                    {
                        "page": 2,
                        "table_index": 4,
                        "row_index": 1,
                        "headers": ["Queue Field", "Bits", "Description"],
                        "cells": {
                            "Queue Field": "SQID",
                            "Bits": "15:0",
                            "Description": "Submission queue identifier",
                        },
                        "row_text": "Queue Field = SQID | Bits = 15:0 | Description = Submission queue identifier",
                    }
                ],
            },
        ]
    )

    records = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables)

    assert [record["unit_type"] for record in records] == [
        "status_code",
        "register_field",
        "support_requirement",
        "queue_field",
    ]
    status_fields = records[0]["normalized_fields"]
    register_fields = records[1]["normalized_fields"]
    support_fields = records[2]["normalized_fields"]
    queue_fields = records[3]["normalized_fields"]
    assert status_fields["canonical_name"] == "0x00"
    assert status_fields["status_code_type"] == "generic"
    assert status_fields["status_code_value"] == "0x00"
    assert register_fields["canonical_name"] == "MQES"
    assert register_fields["register_name"] == "CAP"
    assert register_fields["offset"] == "0x0000"
    assert register_fields["field_name"] == "MQES"
    assert register_fields["access"] == "RO"
    assert register_fields["reset_default"] == "0h"
    assert support_fields["controller_support"] == "mandatory"
    assert support_fields["namespace_support"] == "optional"
    assert support_fields["scope"] == "controller"
    assert queue_fields["bit_range"] == "15:0"
    assert queue_fields["field_name"] == "SQID"
    assert records[0]["classification_reasons"] == ["nvme_status_code_row"]
    assert records[2]["classification_reasons"] == ["nvme_support_requirement_row"]


def test_nvme_domain_adapter_preserves_command_spec_p0_fields() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 5,
                "table_index": 1,
                "headers": ["Command", "Queue Type", "Opcode", "Description"],
                "records": [
                    {
                        "page": 5,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Command", "Queue Type", "Opcode", "Description"],
                        "cells": {
                            "Command": "Read",
                            "Queue Type": "I/O",
                            "Opcode": "02h",
                            "Description": "Read command",
                        },
                        "row_text": "Command = Read | Queue Type = I/O | Opcode = 02h | Description = Read command",
                    }
                ],
            },
            {
                "page": 5,
                "table_index": 2,
                "headers": ["Command Dword", "Bits", "Field", "Description"],
                "records": [
                    {
                        "page": 5,
                        "table_index": 2,
                        "row_index": 1,
                        "headers": ["Command Dword", "Bits", "Field", "Description"],
                        "cells": {
                            "Command Dword": "CDW10",
                            "Bits": "31:00",
                            "Field": "SLBA",
                            "Description": "Starting LBA",
                        },
                        "row_text": "Command Dword = CDW10 | Bits = 31:00 | Field = SLBA | Description = Starting LBA",
                    }
                ],
            },
            {
                "page": 5,
                "table_index": 3,
                "headers": ["Pointer", "Field", "Description"],
                "records": [
                    {
                        "page": 5,
                        "table_index": 3,
                        "row_index": 1,
                        "headers": ["Pointer", "Field", "Description"],
                        "cells": {
                            "Pointer": "Metadata Pointer",
                            "Field": "MPTR",
                            "Description": "Metadata pointer field",
                        },
                        "row_text": "Pointer = Metadata Pointer | Field = MPTR | Description = Metadata pointer field",
                    }
                ],
            },
            {
                "page": 5,
                "table_index": 4,
                "headers": ["SCT", "SC", "Description"],
                "records": [
                    {
                        "page": 5,
                        "table_index": 4,
                        "row_index": 1,
                        "headers": ["SCT", "SC", "Description"],
                        "cells": {
                            "SCT": "Command Specific Status",
                            "SC": "80h",
                            "Description": "LBA out of range; correct the command before retry.",
                        },
                        "row_text": (
                            "SCT = Command Specific Status | SC = 80h | "
                            "Description = LBA out of range; correct the command before retry."
                        ),
                    }
                ],
            },
        ]
    )

    records = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables)

    assert [record["unit_type"] for record in records] == [
        "command",
        "command_dword_field",
        "command_pointer_field",
        "status_code",
    ]
    command_fields = records[0]["normalized_fields"]
    dword_fields = records[1]["normalized_fields"]
    pointer_fields = records[2]["normalized_fields"]
    status_fields = records[3]["normalized_fields"]
    assert command_fields["opcode"] == "02h"
    assert command_fields["command_scope"] == "io"
    assert command_fields["queue_type"] == "io"
    assert dword_fields["command_dword"] == "CDW10"
    assert dword_fields["field_name"] == "SLBA"
    assert dword_fields["bit_range"] == "31:00"
    assert pointer_fields["pointer_type"] == "metadata"
    assert pointer_fields["field_name"] == "MPTR"
    assert status_fields["status_code_group"] == "command_specific"
    assert status_fields["error_class"] == "invalid_address"
    assert status_fields["retry_hint"] == "correct_command"
    assert records[1]["classification_reasons"] == ["nvme_command_dword_row"]
    assert records[2]["classification_reasons"] == ["nvme_command_pointer_row"]


def test_nvme_domain_adapter_preserves_command_spec_relationship_context() -> None:
    heading_path = ["NVM Command Set", "Read Command"]
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 6,
                "table_index": 1,
                "headers": ["Command", "Queue Type", "Opcode", "Description"],
                "records": [
                    {
                        "page": 6,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Command", "Queue Type", "Opcode", "Description"],
                        "heading_path": heading_path,
                        "cells": {
                            "Command": "Read",
                            "Queue Type": "I/O",
                            "Opcode": "02h",
                            "Description": "Read command",
                        },
                        "row_text": "Command = Read | Queue Type = I/O | Opcode = 02h | Description = Read command",
                    }
                ],
            },
            {
                "page": 6,
                "table_index": 2,
                "headers": ["Command Dword", "Bits", "Field", "Description"],
                "records": [
                    {
                        "page": 6,
                        "table_index": 2,
                        "row_index": 1,
                        "headers": ["Command Dword", "Bits", "Field", "Description"],
                        "heading_path": heading_path,
                        "cells": {
                            "Command Dword": "CDW10",
                            "Bits": "31:00",
                            "Field": "SLBA",
                            "Description": "Starting LBA",
                        },
                        "row_text": "Command Dword = CDW10 | Bits = 31:00 | Field = SLBA | Description = Starting LBA",
                    }
                ],
            },
        ]
    )

    records = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables)

    fields = records[1]["normalized_fields"]
    assert records[1]["unit_type"] == "command_dword_field"
    assert records[1]["relationship_hints"] == ["belongs_to_command", "command_dword_layout"]
    assert fields["command_context"] == "Read"
    assert fields["command_context_source"] == "heading_path"
    assert fields["related_command_unit_id"] == "tech-table-000001"
    assert fields["related_command_opcode"] == "02h"
    assert fields["relationship_hints"] == ["belongs_to_command", "command_dword_layout"]


def test_domain_adapter_is_opt_in_and_feeds_retrieval_chunks() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Value", "Description"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Value", "Description"],
                        "cells": {"Value": "0h", "Description": "Disabled"},
                        "row_text": "Value = 0h | Description = Disabled",
                    }
                ],
            }
        ]
    )

    assert build_domain_units(domain_adapter=DomainAdapterMode.NONE, rag_tables=rag_tables) == []
    domain_units = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables)
    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        domain_units=domain_units,
    )

    assert chunks[0]["chunk_type"] == "domain_unit"
    assert chunks[0]["semantic_types"] == ["enum_value"]
    assert chunks[0]["source_refs"][-1]["source_type"] == "domain_unit"


def test_manual_domain_adapter_uses_user_keywords_without_generated_text() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 3,
                "table_index": 1,
                "headers": ["Customer Key", "Customer Requirement", "Verification Note"],
                "records": [
                    {
                        "page": 3,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Customer Key", "Customer Requirement", "Verification Note"],
                        "cells": {
                            "Customer Key": "CUST-LAT-001",
                            "Customer Requirement": "The controller shall preserve latency telemetry.",
                            "Verification Note": "Trace to customer acceptance test.",
                        },
                        "row_text": (
                            "Customer Key = CUST-LAT-001 | Customer Requirement = The controller shall preserve "
                            "latency telemetry. | Verification Note = Trace to customer acceptance test."
                        ),
                    }
                ],
            }
        ]
    )

    records = build_domain_units(
        domain_adapter=DomainAdapterMode.MANUAL,
        rag_tables=rag_tables,
        manual_adapter_label="Customer A Requirements",
        manual_adapter_keywords="Customer Key, Customer Requirement",
    )

    assert len(records) == 1
    record = records[0]
    assert record["domain"] == "manual"
    assert record["adapter_profile"] == "Customer A Requirements"
    assert record["unit_type"] == "requirement"
    assert record["name"] == "CUST-LAT-001"
    assert record["value"] == "CUST-LAT-001"
    assert record["description"] == "The controller shall preserve latency telemetry."
    assert record["classification_reasons"] == ["manual_requirement_id_row"]
    assert "Trace to customer acceptance test." in record["text"]
    assert record["adapter_metadata"]["adapter"] == "manual"
    assert record["adapter_metadata"]["ssd_agent_spec_type"] == "CustomerRequirement"
    assert record["adapter_metadata"]["required_normalized_fields"] == ["requirement_id", "name", "value"]
    assert record["cross_spec_compatibility"]["compatible_adapters"] == ["customer-requirements", "nvme", "ocp"]


def test_domain_adapter_profiles_extract_pcie_ocp_tcg_and_customer_units() -> None:
    pcie_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Register", "Bits", "Field", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Register", "Bits", "Field", "Description"],
                    "cells": {
                        "Register": "Device Control",
                        "Bits": "3:0",
                        "Field": "Max Payload Size",
                        "Description": "Controls payload size",
                    },
                    "row_text": (
                        "Register = Device Control | Bits = 3:0 | Field = Max Payload Size | "
                        "Description = Controls payload size"
                    ),
                }
            ],
        }
    ]
    ocp_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Requirement ID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Requirement ID", "Description"],
                    "cells": {"Requirement ID": "LABL-9", "Description": "Label shall not degrade."},
                    "row_text": "Requirement ID = LABL-9 | Description = Label shall not degrade.",
                }
            ],
        }
    ]
    tcg_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Method", "UID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Method", "UID", "Description"],
                    "cells": {"Method": "Authenticate", "UID": "0001h", "Description": "Authenticate method"},
                    "row_text": "Method = Authenticate | UID = 0001h | Description = Authenticate method",
                }
            ],
        }
    ]

    pcie = build_domain_units(domain_adapter=DomainAdapterMode.PCIE, rag_tables=pcie_tables)
    ocp = build_domain_units(domain_adapter=DomainAdapterMode.OCP, rag_tables=ocp_tables)
    tcg = build_domain_units(domain_adapter=DomainAdapterMode.TCG, rag_tables=tcg_tables)
    customer = build_domain_units(domain_adapter=DomainAdapterMode.CUSTOMER_REQUIREMENTS, rag_tables=ocp_tables)

    assert pcie[0]["domain"] == "pcie"
    assert pcie[0]["unit_type"] == "register_field"
    assert ocp[0]["unit_type"] == "requirement"
    assert tcg[0]["unit_type"] == "security_method"
    assert customer[0]["classification_reasons"] == ["customer_requirement_id_row"]


def test_caliptra_domain_adapter_extracts_rot_assets_and_mailbox_units() -> None:
    caliptra_tables = normalize_rag_table_payload(
        [
            {
                "page": 1,
                "table_index": 1,
                "headers": ["Asset Category", "Asset", "Security Property", "Attack Profile", "Mitigation"],
                "records": [
                    {
                        "page": 1,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Asset Category", "Asset", "Security Property", "Attack Profile", "Mitigation"],
                        "cells": {
                            "Asset Category": "Die unique asset",
                            "Asset": "Synthetic device identity seed",
                            "Security Property": "Confidentiality",
                            "Attack Profile": "Logical attack",
                            "Mitigation": "Keep derived values inside the key vault.",
                        },
                        "row_text": (
                            "Asset Category = Die unique asset | Asset = Synthetic device identity seed | "
                            "Security Property = Confidentiality | Attack Profile = Logical attack | "
                            "Mitigation = Keep derived values inside the key vault."
                        ),
                    }
                ],
            },
            {
                "page": 2,
                "table_index": 1,
                "headers": ["Mailbox Command", "Interface", "Register", "Field", "Bits", "Description"],
                "records": [
                    {
                        "page": 2,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Mailbox Command", "Interface", "Register", "Field", "Bits", "Description"],
                        "cells": {
                            "Mailbox Command": "GET_SYNTHETIC_MEASUREMENT",
                            "Interface": "Mailbox",
                            "Register": "CPTRA_STATUS",
                            "Field": "READY",
                            "Bits": "0",
                            "Description": "Synthetic command reports measured boot status.",
                        },
                        "row_text": (
                            "Mailbox Command = GET_SYNTHETIC_MEASUREMENT | Interface = Mailbox | "
                            "Register = CPTRA_STATUS | Field = READY | Bits = 0 | "
                            "Description = Synthetic command reports measured boot status."
                        ),
                    }
                ],
            },
        ]
    )

    records = build_domain_units(
        domain_adapter=DomainAdapterMode.CALIPTRA,
        rag_tables=caliptra_tables,
        source_sha256="e" * 64,
    )

    by_type = {record["unit_type"]: record for record in records}

    assert {"caliptra_asset", "caliptra_mailbox_command"} <= set(by_type)
    assert by_type["caliptra_asset"]["domain"] == "caliptra"
    assert by_type["caliptra_asset"]["normalized_fields"]["asset"] == "Synthetic device identity seed"
    assert by_type["caliptra_asset"]["adapter_metadata"]["ssd_agent_spec_type"] == "Caliptra"
    assert by_type["caliptra_asset"]["cross_spec_compatibility"]["compatibility_group"] == "security-technical-spec"
    assert by_type["caliptra_mailbox_command"]["normalized_fields"]["command"] == "GET_SYNTHETIC_MEASUREMENT"
    assert by_type["caliptra_mailbox_command"]["normalized_fields"]["register_name"] == "CPTRA_STATUS"


def test_ocp_domain_adapter_populates_requirement_taxonomy_and_related_hints() -> None:
    rag_tables = normalize_rag_table_payload(
        [
            {
                "page": 4,
                "table_index": 1,
                "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                "records": [
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 1,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "NVMe-IO-6",
                            "SSD": "Required",
                            "Requirement Description": "SSD shall support Write Zeroes command.",
                            "Section": "NVMe",
                        },
                        "row_text": (
                            "Requirement ID = NVMe-IO-6 | SSD = Required | "
                            "Requirement Description = SSD shall support Write Zeroes command. | Section = NVMe"
                        ),
                    },
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 2,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "STD-LOG-1",
                            "SSD": "Required",
                            "Requirement Description": "SSD shall expose Error Information Log Identifier 01h.",
                            "Section": "Logs",
                        },
                        "row_text": (
                            "Requirement ID = STD-LOG-1 | SSD = Required | "
                            "Requirement Description = SSD shall expose Error Information Log Identifier 01h. | "
                            "Section = Logs"
                        ),
                    },
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 3,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "NVMe-OPT-2",
                            "SSD": "Optional",
                            "Requirement Description": "SSD should support Feature Identifier 0Eh.",
                            "Section": "Feature",
                        },
                        "row_text": (
                            "Requirement ID = NVMe-OPT-2 | SSD = Optional | "
                            "Requirement Description = SSD should support Feature Identifier 0Eh. | Section = Feature"
                        ),
                    },
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 4,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "TEL-1",
                            "SSD": "Required",
                            "Requirement Description": "SSD shall report telemetry Statistic Identifier 0001h.",
                            "Section": "Telemetry",
                        },
                        "row_text": (
                            "Requirement ID = TEL-1 | SSD = Required | "
                            "Requirement Description = SSD shall report telemetry Statistic Identifier 0001h. | "
                            "Section = Telemetry"
                        ),
                    },
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 5,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "SEC-43",
                            "SSD": "Required",
                            "Requirement Description": "SSD shall support SPDM authentication and TCG handoff.",
                            "Section": "Security",
                        },
                        "row_text": (
                            "Requirement ID = SEC-43 | SSD = Required | "
                            "Requirement Description = SSD shall support SPDM authentication and TCG handoff. | "
                            "Section = Security"
                        ),
                    },
                    {
                        "page": 4,
                        "table_index": 1,
                        "row_index": 6,
                        "headers": ["Requirement ID", "SSD", "Requirement Description", "Section"],
                        "cells": {
                            "Requirement ID": "FF-1",
                            "SSD": "Required",
                            "Requirement Description": "SSD shall fit the E1.S form factor envelope.",
                            "Section": "Mechanical",
                        },
                        "row_text": (
                            "Requirement ID = FF-1 | SSD = Required | "
                            "Requirement Description = SSD shall fit the E1.S form factor envelope. | "
                            "Section = Mechanical"
                        ),
                    },
                ],
            }
        ]
    )

    records = build_domain_units(domain_adapter=DomainAdapterMode.OCP, rag_tables=rag_tables, source_sha256="a" * 64)
    fields_by_id = {record["normalized_fields"]["requirement_id"]: record["normalized_fields"] for record in records}

    assert len(records) == 6
    assert all(record["unit_type"] == "requirement" for record in records)
    assert fields_by_id["NVMe-IO-6"]["requirement_prefix"] == "NVMe-IO"
    assert fields_by_id["NVMe-IO-6"]["requirement_number"] == "6"
    assert fields_by_id["NVMe-IO-6"]["requirement_family"] == "nvme"
    assert fields_by_id["NVMe-IO-6"]["related_command"] == "Write Zeroes"
    assert fields_by_id["STD-LOG-1"]["requirement_family"] == "log_page"
    assert fields_by_id["STD-LOG-1"]["related_log_identifier"] == "01h"
    assert fields_by_id["NVMe-OPT-2"]["requirement_family"] == "feature"
    assert fields_by_id["NVMe-OPT-2"]["related_feature_identifier"] == "0Eh"
    assert fields_by_id["NVMe-OPT-2"]["normative_strength"] == "should"
    assert fields_by_id["TEL-1"]["requirement_family"] == "telemetry"
    assert fields_by_id["TEL-1"]["ocp_section_context"] == "telemetry"
    assert fields_by_id["TEL-1"]["related_statistic_identifier"] == "0001h"
    assert fields_by_id["SEC-43"]["requirement_family"] == "security"
    assert fields_by_id["SEC-43"]["related_security_protocol"] == "SPDM"
    assert fields_by_id["FF-1"]["requirement_family"] == "form_factor"
    assert fields_by_id["FF-1"]["related_form_factor"] == "E1.S"
    assert fields_by_id["FF-1"]["source_table_row_id"] == "page-0004-table-0001-row-0006"


def test_tcg_domain_adapter_extracts_security_method_authority_object_and_field_units() -> None:
    tcg_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Method", "UID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Method", "UID", "Description"],
                    "cells": {"Method": "StartSession", "UID": "0001h", "Description": "Starts a session"},
                    "row_text": "Method = StartSession | UID = 0001h | Description = Starts a session",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Authority", "UID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Authority", "UID", "Description"],
                    "cells": {"Authority": "SID", "UID": "0002h", "Description": "Security identifier authority"},
                    "row_text": "Authority = SID | UID = 0002h | Description = Security identifier authority",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 3,
            "headers": ["Security Field", "Bits", "Security Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Security Field", "Bits", "Security Description"],
                    "cells": {
                        "Security Field": "ReadLockEnabled",
                        "Bits": "0",
                        "Security Description": "Read locking state",
                    },
                    "row_text": (
                        "Security Field = ReadLockEnabled | Bits = 0 | "
                        "Security Description = Read locking state"
                    ),
                }
            ],
        },
    ]

    records = build_domain_units(domain_adapter=DomainAdapterMode.TCG, rag_tables=tcg_tables)

    assert [record["unit_type"] for record in records] == [
        "security_method",
        "security_authority",
        "security_field",
    ]
    assert records[0]["value"] == "0001h"
    assert records[2]["name"] == "ReadLockEnabled"
    assert all(record["source_refs"][1]["source_type"] == "technical_table_unit" for record in records)


def test_tcg_domain_adapter_extracts_expanded_security_units() -> None:
    tcg_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Security Provider", "UID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Security Provider", "UID", "Description"],
                    "cells": {
                        "Security Provider": "LockingSP",
                        "UID": "0002h",
                        "Description": "Locking security provider",
                    },
                    "row_text": (
                        "Security Provider = LockingSP | UID = 0002h | "
                        "Description = Locking security provider"
                    ),
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Locking Range", "Bits", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Locking Range", "Bits", "Description"],
                    "cells": {"Locking Range": "Range 1", "Bits": "7:0", "Description": "User data range"},
                    "row_text": "Locking Range = Range 1 | Bits = 7:0 | Description = User data range",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 3,
            "headers": ["Key Management", "UID", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Key Management", "UID", "Description"],
                    "cells": {"Key Management": "Media Encryption Key", "UID": "0003h", "Description": "MEK control"},
                    "row_text": (
                        "Key Management = Media Encryption Key | UID = 0003h | Description = MEK control"
                    ),
                }
            ],
        },
        {
            "page": 1,
            "table_index": 4,
            "headers": ["Session State", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 4,
                    "row_index": 1,
                    "headers": ["Session State", "Value", "Description"],
                    "cells": {"Session State": "Authenticated", "Value": "01h", "Description": "Session is active"},
                    "row_text": "Session State = Authenticated | Value = 01h | Description = Session is active",
                }
            ],
        },
    ]

    records = build_domain_units(domain_adapter=DomainAdapterMode.TCG, rag_tables=tcg_tables)

    assert [record["unit_type"] for record in records] == [
        "security_provider",
        "locking_range",
        "key_management",
        "session_state",
    ]
    assert records[0]["normalized_fields"]["security_provider"] == "LockingSP"
    assert records[2]["normalized_fields"]["key_name"] == "Media Encryption Key"


def test_spdm_domain_adapter_extracts_security_protocol_units_and_chunks() -> None:
    spdm_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Message", "Message Code", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Message", "Message Code", "Description"],
                    "cells": {"Message": "GET_VERSION", "Message Code": "0x84", "Description": "Request version"},
                    "row_text": "Message = GET_VERSION | Message Code = 0x84 | Description = Request version",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Request", "Response", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Request", "Response", "Description"],
                    "cells": {"Request": "GET_DIGESTS", "Response": "DIGESTS", "Description": "Digest exchange"},
                    "row_text": "Request = GET_DIGESTS | Response = DIGESTS | Description = Digest exchange",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 3,
            "headers": ["Measurement Index", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Measurement Index", "Value", "Description"],
                    "cells": {"Measurement Index": "0", "Value": "TCB", "Description": "TCB measurement block"},
                    "row_text": "Measurement Index = 0 | Value = TCB | Description = TCB measurement block",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 4,
            "headers": ["Certificate Slot", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 4,
                    "row_index": 1,
                    "headers": ["Certificate Slot", "Value", "Description"],
                    "cells": {"Certificate Slot": "Slot 0", "Value": "Leaf", "Description": "Certificate chain slot"},
                    "row_text": "Certificate Slot = Slot 0 | Value = Leaf | Description = Certificate chain slot",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 5,
            "headers": ["Algorithm Type", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 5,
                    "row_index": 1,
                    "headers": ["Algorithm Type", "Value", "Description"],
                    "cells": {"Algorithm Type": "BaseAsymAlgo", "Value": "TPM_ALG_ECDSA_ECC_NIST_P384", "Description": "Asymmetric algorithm"},
                    "row_text": (
                        "Algorithm Type = BaseAsymAlgo | Value = TPM_ALG_ECDSA_ECC_NIST_P384 | "
                        "Description = Asymmetric algorithm"
                    ),
                }
            ],
        },
        {
            "page": 1,
            "table_index": 6,
            "headers": ["Key Exchange", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 6,
                    "row_index": 1,
                    "headers": ["Key Exchange", "Value", "Description"],
                    "cells": {"Key Exchange": "DHE", "Value": "secp384r1", "Description": "DHE named group"},
                    "row_text": "Key Exchange = DHE | Value = secp384r1 | Description = DHE named group",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 7,
            "headers": ["Session State", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 7,
                    "row_index": 1,
                    "headers": ["Session State", "Value", "Description"],
                    "cells": {"Session State": "Secured", "Value": "01h", "Description": "Encrypted session active"},
                    "row_text": "Session State = Secured | Value = 01h | Description = Encrypted session active",
                }
            ],
        },
    ]

    records = build_domain_units(domain_adapter=DomainAdapterMode.SPDM, rag_tables=spdm_tables)
    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        domain_units=records,
    )

    assert [record["unit_type"] for record in records] == [
        "spdm_message",
        "spdm_request_response",
        "spdm_measurement",
        "spdm_certificate",
        "spdm_algorithm",
        "spdm_key_exchange",
        "spdm_session",
    ]
    assert records[0]["domain_unit_id"] == "domain-spdm-000001"
    assert records[0]["normalized_fields"]["message_code"] == "0x84"
    assert records[1]["normalized_fields"]["request"] == "GET_DIGESTS"
    assert json.loads(serialize_domain_units_jsonl(records).splitlines()[0])["domain"] == "spdm"
    assert chunks[0]["chunk_type"] == "domain_unit"
    assert chunks[0]["retrieval_priority"] == 96
    assert chunks[0]["source_refs"][-1]["source_id"] == "domain-spdm-000001"


def test_domain_adapter_deep_fixtures_cover_storage_pcie_ocp_tcg_and_customer_shapes() -> None:
    nvme_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Log Identifier", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Log Identifier", "Description"],
                    "cells": {"Log Identifier": "0x02", "Description": "SMART / Health Information"},
                    "row_text": "Log Identifier = 0x02 | Description = SMART / Health Information",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Feature Identifier", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Feature Identifier", "Description"],
                    "cells": {"Feature Identifier": "0x0C", "Description": "Autonomous Power State Transition"},
                    "row_text": "Feature Identifier = 0x0C | Description = Autonomous Power State Transition",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 3,
            "headers": ["Status", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Status", "Value", "Description"],
                    "cells": {"Status": "Success", "Value": "0h", "Description": "Command completed successfully"},
                    "row_text": "Status = Success | Value = 0h | Description = Command completed successfully",
                }
            ],
        },
    ]
    pcie_tables = [
        {
            "page": 2,
            "table_index": 1,
            "headers": ["Capability", "Offset", "Field", "Description"],
            "records": [
                {
                    "page": 2,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Capability", "Offset", "Field", "Description"],
                    "cells": {
                        "Capability": "Advanced Error Reporting",
                        "Offset": "0x100",
                        "Field": "Uncorrectable Error Status",
                        "Description": "ECN-defined error status bits",
                    },
                    "row_text": (
                        "Capability = Advanced Error Reporting | Offset = 0x100 | "
                        "Field = Uncorrectable Error Status | Description = ECN-defined error status bits"
                    ),
                }
            ],
        }
    ]
    ocp_tables = [
        {
            "page": 3,
            "table_index": 1,
            "headers": ["Requirement ID", "SSD", "Requirement Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Requirement ID", "SSD", "Requirement Description"],
                    "cells": {
                        "Requirement ID": "SLIFE-12",
                        "SSD": "Required",
                        "Requirement Description": "The device shall report spare life.",
                    },
                    "row_text": (
                        "Requirement ID = SLIFE-12 | SSD = Required | "
                        "Requirement Description = The device shall report spare life."
                    ),
                }
            ],
        }
    ]
    tcg_tables = [
        {
            "page": 4,
            "table_index": 1,
            "headers": ["Object", "UID", "Description"],
            "records": [
                {
                    "page": 4,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Object", "UID", "Description"],
                    "cells": {"Object": "LockingSP", "UID": "0002h", "Description": "Locking security provider object"},
                    "row_text": "Object = LockingSP | UID = 0002h | Description = Locking security provider object",
                }
            ],
        }
    ]
    customer_tables = [
        {
            "page": 5,
            "table_index": 1,
            "headers": ["Req ID", "Requirement Description"],
            "records": [
                {
                    "page": 5,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Req ID", "Requirement Description"],
                    "cells": {"Req ID": "CUST-101", "Requirement Description": "The product must preserve telemetry."},
                    "row_text": "Req ID = CUST-101 | Requirement Description = The product must preserve telemetry.",
                }
            ],
        }
    ]

    nvme = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=nvme_tables)
    pcie = build_domain_units(domain_adapter=DomainAdapterMode.PCIE, rag_tables=pcie_tables)
    ocp = build_domain_units(domain_adapter=DomainAdapterMode.OCP, rag_tables=ocp_tables)
    tcg = build_domain_units(domain_adapter=DomainAdapterMode.TCG, rag_tables=tcg_tables)
    customer = build_domain_units(domain_adapter=DomainAdapterMode.CUSTOMER_REQUIREMENTS, rag_tables=customer_tables)

    assert [record["unit_type"] for record in nvme] == ["log_page", "feature", "enum_value"]
    assert nvme[0]["value"] == "0x02"
    assert pcie[0]["unit_type"] == "register_field"
    assert pcie[0]["name"] == "Advanced Error Reporting"
    assert ocp[0]["name"] == "SLIFE-12"
    assert tcg[0]["unit_type"] == "security_object"
    assert customer[0]["classification_reasons"] == ["customer_requirement_id_row"]

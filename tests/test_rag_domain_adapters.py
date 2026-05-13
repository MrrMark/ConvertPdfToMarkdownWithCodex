from __future__ import annotations

import json

from pdf2md.models import DomainAdapterMode
from pdf2md.serializers.rag_chunks import build_retrieval_chunks
from pdf2md.serializers.rag_domain_adapters import build_domain_units, serialize_domain_units_jsonl
from pdf2md.serializers.rag_tables import normalize_rag_table_payload


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

    records = build_domain_units(domain_adapter=DomainAdapterMode.NVME, rag_tables=rag_tables)

    assert [record["unit_type"] for record in records] == ["command", "register_field"]
    assert records[0]["domain_unit_id"] == "domain-nvme-000001"
    assert records[0]["name"] == "KV Store"
    assert records[0]["value"] == "0x81"
    assert records[0]["source_refs"][0]["source_id"] == "page-0001-table-0001-row-0001"
    assert records[1]["source_refs"][0]["source_id"] == "page-0001-table-0002-row-0001"

    jsonl = serialize_domain_units_jsonl(records)
    assert json.loads(jsonl.splitlines()[0])["domain"] == "nvme"


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

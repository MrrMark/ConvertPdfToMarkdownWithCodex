from __future__ import annotations

import json

from pdf2md.serializers.rag_chunks import build_retrieval_chunks
from pdf2md.serializers.rag_technical_tables import (
    build_technical_table_records,
    serialize_technical_tables_jsonl,
)
from scripts.run_rag_eval import evaluate_queries


def test_technical_tables_extract_bitfield_and_opcode_units() -> None:
    rag_tables = [
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
                    "cells": {"Command": "Identify", "Opcode": "06h", "Description": "Identify command"},
                    "row_text": "Command = Identify | Opcode = 06h | Description = Identify command",
                    "table_confidence_v2": 0.91,
                    "table_confidence_v2_bucket": "high",
                    "table_confidence_v2_reasons": ["header_confidence_high"],
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Bits", "Field", "Reset", "Access", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Bits", "Field", "Reset", "Access", "Description"],
                    "cells": {
                        "Bits": "7:4",
                        "Field": "Status",
                        "Reset": "0h",
                        "Access": "RO",
                        "Description": "Current status",
                    },
                    "row_text": "Bits = 7:4 | Field = Status | Reset = 0h | Access = RO | Description = Current status",
                }
            ],
        },
    ]

    records = build_technical_table_records(rag_tables, source_sha256="1" * 64)

    assert [record["unit_type"] for record in records] == ["command_opcode", "bitfield"]
    assert records[0]["technical_table_unit_id"] == "tech-table-000001"
    assert records[0]["opcode"] == "06h"
    assert records[0]["table_confidence_v2"] == 0.91
    assert records[0]["table_confidence_v2_bucket"] == "high"
    assert records[0]["table_confidence_v2_reasons"] == ["header_confidence_high"]
    assert records[1]["bit_range"] == "7:4"
    assert records[1]["reset_default"] == "0h"
    assert records[1]["access"] == "RO"
    assert records[1]["source_refs"][0]["source_id"] == "page-0001-table-0002-row-0001"
    assert records[0]["source_sha256"] == "1" * 64
    assert records[0]["source_dedupe_key"] == "page-0001-table-0001-row-0001"
    assert len(records[0]["stable_source_id"]) == 40
    assert len(records[0]["stable_requirement_seed"]) == 40

    jsonl = serialize_technical_tables_jsonl(records)
    assert json.loads(jsonl.splitlines()[1])["field_name"] == "Status"


def test_technical_tables_extract_storage_identifier_and_security_units() -> None:
    rag_tables = [
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
                    "cells": {"Log Identifier": "02h", "Description": "SMART information"},
                    "row_text": "Log Identifier = 02h | Description = SMART information",
                }
            ],
        },
        {
            "page": 1,
            "table_index": 2,
            "headers": ["Feature Identifier", "Value", "Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Feature Identifier", "Value", "Description"],
                    "cells": {
                        "Feature Identifier": "06h",
                        "Value": "Volatile Write Cache",
                        "Description": "Feature setting",
                    },
                    "row_text": (
                        "Feature Identifier = 06h | Value = Volatile Write Cache | "
                        "Description = Feature setting"
                    ),
                }
            ],
        },
        {
            "page": 2,
            "table_index": 1,
            "headers": ["Method", "ProtocolID", "Description"],
            "records": [
                {
                    "page": 2,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["Method", "ProtocolID", "Description"],
                    "cells": {"Method": "Erase", "ProtocolID": "01h", "Description": "Security method"},
                    "row_text": "Method = Erase | ProtocolID = 01h | Description = Security method",
                }
            ],
        },
        {
            "page": 2,
            "table_index": 2,
            "headers": ["Object", "UID", "Description"],
            "records": [
                {
                    "page": 2,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Object", "UID", "Description"],
                    "cells": {"Object": "LockingSP", "UID": "0002h", "Description": "Security object"},
                    "row_text": "Object = LockingSP | UID = 0002h | Description = Security object",
                }
            ],
        },
        {
            "page": 2,
            "table_index": 3,
            "headers": ["Authority", "UID", "Description"],
            "records": [
                {
                    "page": 2,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Authority", "UID", "Description"],
                    "cells": {"Authority": "SID", "UID": "0003h", "Description": "Security authority"},
                    "row_text": "Authority = SID | UID = 0003h | Description = Security authority",
                }
            ],
        },
        {
            "page": 2,
            "table_index": 4,
            "headers": ["Security Field", "Bits", "Security Description"],
            "records": [
                {
                    "page": 2,
                    "table_index": 4,
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

    records = build_technical_table_records(rag_tables)

    assert [record["unit_type"] for record in records] == [
        "log_page",
        "feature_identifier",
        "security_method",
        "security_object",
        "security_authority",
        "security_field",
    ]
    assert records[0]["log_identifier"] == "02h"
    assert records[1]["feature_identifier"] == "06h"
    assert records[2]["raw_cells"]["Method"] == "Erase"
    assert records[2]["source_refs"][0]["source_id"] == "page-0002-table-0001-row-0001"
    assert records[3]["field_name"] is None
    assert records[3]["value"] == "0002h"
    assert records[4]["value"] == "0003h"
    assert records[5]["field_name"] == "ReadLockEnabled"
    assert records[5]["meaning"] == "Read locking state"
    assert records[5]["classification_confidence"] == 0.9
    assert json.loads(serialize_technical_tables_jsonl(records).splitlines()[5])["unit_type"] == "security_field"


def test_technical_tables_extract_expanded_nvme_unit_types_and_aliases() -> None:
    rag_tables = [
        {
            "page": 3,
            "table_index": 1,
            "headers": ["SCT", "SC", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": ["SCT", "SC", "Description"],
                    "cells": {"SCT": "generic", "SC": "0x00", "Description": "Successful completion"},
                    "row_text": "SCT = generic | SC = 0x00 | Description = Successful completion",
                }
            ],
        },
        {
            "page": 3,
            "table_index": 2,
            "headers": ["Queue Field", "Bits", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 2,
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
        {
            "page": 3,
            "table_index": 3,
            "headers": ["Namespace Field", "Bit", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["Namespace Field", "Bit", "Description"],
                    "cells": {"Namespace Field": "NSZE", "Bit": "63:0", "Description": "Namespace size"},
                    "row_text": "Namespace Field = NSZE | Bit = 63:0 | Description = Namespace size",
                }
            ],
        },
        {
            "page": 3,
            "table_index": 4,
            "headers": ["Controller Field", "Bits", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 4,
                    "row_index": 1,
                    "headers": ["Controller Field", "Bits", "Description"],
                    "cells": {"Controller Field": "CQR", "Bits": "16", "Description": "Contiguous queues required"},
                    "row_text": "Controller Field = CQR | Bits = 16 | Description = Contiguous queues required",
                }
            ],
        },
        {
            "page": 3,
            "table_index": 5,
            "headers": ["Controller Support", "Namespace Support", "Scope", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 5,
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
            "page": 3,
            "table_index": 6,
            "headers": ["Data Structure Field", "Bits", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 6,
                    "row_index": 1,
                    "headers": ["Data Structure Field", "Bits", "Description"],
                    "cells": {
                        "Data Structure Field": "VID",
                        "Bits": "15:0",
                        "Description": "PCI vendor identifier",
                    },
                    "row_text": "Data Structure Field = VID | Bits = 15:0 | Description = PCI vendor identifier",
                }
            ],
        },
        {
            "page": 3,
            "table_index": 7,
            "headers": ["Property", "Offset", "Field", "Attributes", "Reset Default", "Description"],
            "records": [
                {
                    "page": 3,
                    "table_index": 7,
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
    ]

    records = build_technical_table_records(rag_tables)

    assert [record["unit_type"] for record in records] == [
        "status_code",
        "queue_field",
        "namespace_field",
        "controller_field",
        "support_requirement",
        "data_structure_field",
        "register_field",
    ]
    assert records[0]["status_code_type"] == "generic"
    assert records[0]["status_code_value"] == "0x00"
    assert records[0]["status_code_group"] == "generic"
    assert records[0]["error_class"] == "success"
    assert records[0]["retry_hint"] == "not_applicable"
    assert records[1]["field_name"] == "SQID"
    assert records[2]["bit_range"] == "63:0"
    assert records[4]["controller_support"] == "mandatory"
    assert records[4]["namespace_support"] == "optional"
    assert records[4]["scope"] == "controller"
    assert records[6]["register_name"] == "CAP"
    assert records[6]["offset"] == "0x0000"
    assert records[6]["access"] == "RO"
    assert records[6]["reset_default"] == "0h"
    assert json.loads(serialize_technical_tables_jsonl(records).splitlines()[4])["unit_type"] == "support_requirement"


def test_technical_tables_extract_nvme_command_spec_p0_fields() -> None:
    rag_tables = [
        {
            "page": 4,
            "table_index": 1,
            "headers": ["Command", "Queue Type", "Opcode", "Description"],
            "records": [
                {
                    "page": 4,
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
            "page": 4,
            "table_index": 2,
            "headers": ["Command Dword", "Bits", "Field", "Description"],
            "records": [
                {
                    "page": 4,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Command Dword", "Bits", "Field", "Description"],
                    "cells": {
                        "Command Dword": "Command Dword 10",
                        "Bits": "31:00",
                        "Field": "SLBA",
                        "Description": "Starting LBA",
                    },
                    "row_text": (
                        "Command Dword = Command Dword 10 | Bits = 31:00 | "
                        "Field = SLBA | Description = Starting LBA"
                    ),
                }
            ],
        },
        {
            "page": 4,
            "table_index": 3,
            "headers": ["Pointer", "Field", "Description"],
            "records": [
                {
                    "page": 4,
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
            "page": 4,
            "table_index": 4,
            "headers": ["SCT", "SC", "Description"],
            "records": [
                {
                    "page": 4,
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

    records = build_technical_table_records(rag_tables)

    assert [record["unit_type"] for record in records] == [
        "command_opcode",
        "command_dword_field",
        "command_pointer_field",
        "status_code",
    ]
    assert records[0]["command_scope"] == "io"
    assert records[0]["queue_type"] == "io"
    assert records[1]["command_dword"] == "CDW10"
    assert records[1]["bit_range"] == "31:00"
    assert records[1]["field_name"] == "SLBA"
    assert records[1]["classification_confidence"] == 0.9
    assert records[2]["pointer_type"] == "metadata"
    assert records[2]["field_name"] == "MPTR"
    assert records[3]["status_code_group"] == "command_specific"
    assert records[3]["error_class"] == "invalid_address"
    assert records[3]["retry_hint"] == "correct_command"
    serialized = json.loads(serialize_technical_tables_jsonl(records).splitlines()[1])
    assert serialized["unit_type"] == "command_dword_field"
    assert serialized["command_dword"] == "CDW10"


def test_technical_tables_extract_official_command_set_header_variants() -> None:
    rag_tables = [
        {
            "page": 26,
            "table_index": 1,
            "headers": ["Opcode by Field", "Column 2", "Combined Opcode 1", "2 Command", "Reference Section"],
            "records": [
                {
                    "page": 26,
                    "table_index": 1,
                    "row_index": 1,
                    "headers": [
                        "Opcode by Field",
                        "Column 2",
                        "Combined Opcode 1",
                        "2 Command",
                        "Reference Section",
                    ],
                    "column_header_paths": [
                        {
                            "column_index": 1,
                            "header": "Opcode by Field",
                            "path": ["Opcode by Field"],
                            "path_text": "Opcode by Field",
                            "source": "multi_row_header",
                            "placeholder": False,
                        },
                        {
                            "column_index": 2,
                            "header": "Column 2",
                            "path": ["Opcode by Field", "Column 2"],
                            "path_text": "Opcode by Field / Column 2",
                            "source": "multi_row_header",
                            "placeholder": True,
                            "inferred_parent_header": "Opcode by Field",
                            "neighbor_headers": ["Opcode by Field", "Combined Opcode 1"],
                        },
                    ],
                    "column_placeholder_header_ratio": 0.2,
                    "cells": {
                        "Opcode by Field": "0000 00b",
                        "Column 2": "10b",
                        "Combined Opcode 1": "02h",
                        "2 Command": "Read",
                        "Reference Section": "3.3.4",
                    },
                    "row_text": (
                        "Opcode by Field = 0000 00b | Column 2 = 10b | Combined Opcode 1 = 02h | "
                        "2 Command = Read | Reference Section = 3.3.4"
                    ),
                }
            ],
        },
        {
            "page": 24,
            "table_index": 2,
            "headers": ["Value", "Definition", "Commands Affected"],
            "records": [
                {
                    "page": 24,
                    "table_index": 2,
                    "row_index": 1,
                    "headers": ["Value", "Definition", "Commands Affected"],
                    "cells": {
                        "Value": "80h",
                        "Definition": "Conflicting Attributes",
                        "Commands Affected": "Dataset Management, Read, Write",
                    },
                    "row_text": (
                        "Value = 80h | Definition = Conflicting Attributes | "
                        "Commands Affected = Dataset Management, Read, Write"
                    ),
                }
            ],
        },
    ]

    records = build_technical_table_records(rag_tables)

    assert [record["unit_type"] for record in records] == ["command_opcode", "status_code"]
    assert records[0]["command"] == "Read"
    assert records[0]["opcode"] == "02h"
    assert records[0]["column_header_paths"][1]["path_text"] == "Opcode by Field / Column 2"
    assert records[0]["column_placeholder_header_ratio"] == 0.2
    assert "placeholder_header_context_available" in records[0]["classification_reasons"]
    assert records[0]["command_context"] == "Read"
    assert records[0]["relationship_hints"] == ["command_anchor"]
    assert records[1]["status_code_type"] == "Command Specific Status"
    assert records[1]["status_code_value"] == "80h"
    assert records[1]["status_code_group"] == "command_specific"
    assert records[1]["error_class"] == "conflict"


def test_technical_tables_link_command_spec_rows_by_heading_context() -> None:
    heading_path = ["NVM Command Set", "Read Command"]
    rag_tables = [
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
        {
            "page": 6,
            "table_index": 3,
            "headers": ["SCT", "SC", "Description"],
            "records": [
                {
                    "page": 6,
                    "table_index": 3,
                    "row_index": 1,
                    "headers": ["SCT", "SC", "Description"],
                    "heading_path": heading_path,
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

    records = build_technical_table_records(rag_tables)

    assert records[0]["relationship_hints"] == ["command_anchor"]
    assert records[0]["command_context"] == "Read"
    assert records[1]["command_context"] == "Read"
    assert records[1]["command_context_source"] == "heading_path"
    assert records[1]["related_command_unit_id"] == "tech-table-000001"
    assert records[1]["related_command_opcode"] == "02h"
    assert records[1]["relationship_hints"] == ["belongs_to_command", "command_dword_layout"]
    assert records[2]["command_context"] == "Read"
    assert records[2]["related_command_unit_id"] == "tech-table-000001"
    assert records[2]["relationship_hints"] == ["belongs_to_command", "status_code_taxonomy"]


def test_technical_table_units_are_verifiable_by_expected_source_coverage() -> None:
    rag_tables = [
        {
            "page": 1,
            "table_index": 1,
            "headers": ["Security Field", "Bits", "Security Description"],
            "records": [
                {
                    "page": 1,
                    "table_index": 1,
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
        }
    ]
    technical_records = build_technical_table_records(rag_tables)
    chunks = build_retrieval_chunks(
        text_block_records=[],
        semantic_units=[],
        requirements=[],
        rag_tables=[],
        technical_table_records=technical_records,
    )

    report = evaluate_queries(
        chunks=chunks,
        queries=[
            {
                "query": "read lock enabled security field",
                "expected_source_ids": ["tech-table-000001"],
                "expected_source_types": ["technical_table_unit"],
            }
        ],
        top_k=3,
    )

    assert technical_records[0]["unit_type"] == "security_field"
    assert report["metrics"]["expected_source_coverage"] == 1.0
    assert report["results"][0]["missing_expected_source_ids"] == []

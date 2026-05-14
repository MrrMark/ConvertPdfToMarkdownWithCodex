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

    records = build_technical_table_records(rag_tables)

    assert [record["unit_type"] for record in records] == ["command_opcode", "bitfield"]
    assert records[0]["technical_table_unit_id"] == "tech-table-000001"
    assert records[0]["opcode"] == "06h"
    assert records[1]["bit_range"] == "7:4"
    assert records[1]["reset_default"] == "0h"
    assert records[1]["access"] == "RO"
    assert records[1]["source_refs"][0]["source_id"] == "page-0001-table-0002-row-0001"

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

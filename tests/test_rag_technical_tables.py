from __future__ import annotations

import json

from pdf2md.serializers.rag_technical_tables import (
    build_technical_table_records,
    serialize_technical_tables_jsonl,
)


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

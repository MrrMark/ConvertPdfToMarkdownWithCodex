<!-- table-rag: page=1 index=1 source=html -->
Caption: Table 1: Command timing fields
Headers: Command | Latency / Min | Latency / Max | Latency / Typical
Row 1: Command = Read | Latency / Min = 1 | Latency / Max = 3 | Latency / Typical = 2
Row 2: Command = Write | Latency / Min = 2 | Latency / Max = 4 | Latency / Typical = 3

<!-- table-rag: page=2 index=1 source=gfm -->
Caption: Table 2: Control register bits
Headers: Bits | Field | Reset | Access | Description
Row 1: Bits = 31:16 | Field = RSVD | Reset = 0h | Access = RO | Description = Reserved bits
Row 2: Bits = 15:8 | Field = STATUS | Reset = 0h | Access = RO | Description = Current status
Row 3: Bits = 7:0 | Field = ENABLE | Reset = 0h | Access = RW | Description = Enable mask

<!-- table-rag: page=3 index=1 source=html -->
Caption: Table 3: Command opcodes
Headers: Command | Opcode | Description
Row 1: Command = Identify | Opcode = 06h | Description = Identify command
Row 2: Command = Sanitize | Opcode = 84h | Description = Sanitize command

<!-- table-rag: page=4 index=1 source=gfm -->
Caption: Table 4: Log identifiers
Headers: Log Identifier | Description
Row 1: Log Identifier = 02h | Description = SMART information

<!-- table-rag: page=5 index=1 source=gfm -->
Caption: Table 5: Feature identifiers
Headers: Feature Identifier | Value | Description
Row 1: Feature Identifier = 02h | Value = Volatile Write Cache | Description = Feature setting

<!-- table-rag: page=6 index=1 source=html -->
Caption: Table 6: Security methods
Headers: Method | ProtocolID | Description
Row 1: Method = Erase | ProtocolID = 01h | Description = Security method

<!-- table-rag: page=7 index=1 source=html group=table-continuation-001 -->
Caption: Table 7: Continued status fields
Headers: Field | Value
Row 1: Field = alpha | Value = 1

<!-- table-rag: page=8 index=1 source=html group=table-continuation-001 -->
Caption:
Headers: Field | Value
Row 1: Field = beta | Value = 2

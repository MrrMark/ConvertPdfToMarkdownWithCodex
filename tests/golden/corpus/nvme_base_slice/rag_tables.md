<!-- table-rag: page=2 index=1 source=html -->
Caption: Table 1: Command opcode slice
Headers: Command | Opcode | Description
Row 1: Command = Identify | Opcode = 06h | Description = Synthetic identify command

<!-- table-rag: page=3 index=1 source=gfm -->
Caption: Table 2: Log page identifier slice
Headers: Log Identifier | Description
Row 1: Log Identifier = 02h | Description = Synthetic health log

<!-- table-rag: page=4 index=1 source=gfm -->
Caption: Table 3: Feature identifier slice
Headers: Feature Identifier | Value | Description
Row 1: Feature Identifier = 0Ch | Value = Async Event | Description = Synthetic event feature

<!-- table-rag: page=5 index=1 source=html -->
Caption: Table 4: Register bitfield slice
Headers: Register | Offset | Bits | Field | Reset Default | Access | Description
Row 1: Register = CAP | Offset = 0x0000 | Bits = 15:0 | Field = MQES | Reset Default = 0h | Access = RO | Description = Synthetic max queue entries

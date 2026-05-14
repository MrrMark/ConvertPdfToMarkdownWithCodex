<!-- page: 1 -->

Table 1: Command timing fields

<!-- table: page=1 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th></th>
      <th>Latency</th>
      <th>Latency</th>
      <th>Latency</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Command</td>
      <td>Min</td>
      <td>Max</td>
      <td>Typical</td>
    </tr>
    <tr>
      <td>Read</td>
      <td>1</td>
      <td>3</td>
      <td>2</td>
    </tr>
    <tr>
      <td>Write</td>
      <td>2</td>
      <td>4</td>
      <td>3</td>
    </tr>
  </tbody>
  <tfoot>
    <tr>
      <td colspan="4">Notes: values are cycles</td>
    </tr>
  </tfoot>
</table>

<!-- page: 2 -->

Table 2: Control register bits

<!-- table: page=2 index=1 mode=gfm -->
| Bits | Field | Reset | Access | Description |
| --- | --- | --- | --- | --- |
| 31:16 | RSVD | 0h | RO | Reserved bits |
| 15:8 | STATUS | 0h | RO | Current status |
| 7:0 | ENABLE | 0h | RW | Enable mask |

<!-- page: 3 -->

Table 3: Command opcodes

<!-- table: page=3 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Command</th>
      <th>Opcode</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Identify</td>
      <td>06h</td>
      <td>Identify command</td>
    </tr>
    <tr>
      <td>Sanitize</td>
      <td>84h</td>
      <td>Sanitize command</td>
    </tr>
  </tbody>
</table>

<!-- page: 4 -->

Table 4: Log identifiers

<!-- table: page=4 index=1 mode=gfm -->
| Log Identifier | Description |
| --- | --- |
| 02h | SMART information |

<!-- page: 5 -->

Table 5: Feature identifiers

<!-- table: page=5 index=1 mode=gfm -->
| Feature Identifier | Value | Description |
| --- | --- | --- |
| 02h | Volatile Write Cache | Feature setting |

<!-- page: 6 -->

Table 6: Security methods

<!-- table: page=6 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Method</th>
      <th>ProtocolID</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Erase</td>
      <td>01h</td>
      <td>Security method</td>
    </tr>
  </tbody>
</table>

<!-- page: 7 -->

Table 7: Continued status fields

<!-- table: page=7 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Field</th>
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>alpha</td>
      <td>1</td>
    </tr>
  </tbody>
</table>

<!-- page: 8 -->

<!-- table: page=8 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Field</th>
      <th>Value</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>beta</td>
      <td>2</td>
    </tr>
  </tbody>
</table>

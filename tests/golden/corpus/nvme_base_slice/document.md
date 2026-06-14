<!-- page: 1 -->

## 1 NVMe Synthetic Slice

The controller shall report synthetic health status when requested.
NOTE: Synthetic notes are review-only adapter evidence.
Example: A host may issue Identify for demonstration.

<!-- page: 2 -->

Table 1: Command opcode slice

<!-- table: page=2 index=1 mode=html -->
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
      <td>Synthetic identify command</td>
    </tr>
  </tbody>
</table>

<!-- page: 3 -->

Table 2: Log page identifier slice

<!-- table: page=3 index=1 mode=gfm -->
| Log Identifier | Description |
| --- | --- |
| 02h | Synthetic health log |

<!-- page: 4 -->

Table 3: Feature identifier slice

<!-- table: page=4 index=1 mode=gfm -->
| Feature Identifier | Value | Description |
| --- | --- | --- |
| 0Ch | Async Event | Synthetic event feature |

<!-- page: 5 -->

Table 4: Register bitfield slice

<!-- table: page=5 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Register</th>
      <th>Offset</th>
      <th>Bits</th>
      <th>Field</th>
      <th>Reset Default</th>
      <th>Access</th>
      <th>Description</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>CAP</td>
      <td>0x0000</td>
      <td>15:0</td>
      <td>MQES</td>
      <td>0h</td>
      <td>RO</td>
      <td>Synthetic max queue entries</td>
    </tr>
  </tbody>
</table>

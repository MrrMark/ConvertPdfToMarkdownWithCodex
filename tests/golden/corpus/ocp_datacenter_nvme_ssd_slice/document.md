<!-- page: 1 -->

## 1 OCP Datacenter NVMe SSD Synthetic Slice

This synthetic slice shall preserve requirement traceability metadata.
NOTE: These rows are fixture-only adapter evidence.

<!-- page: 2 -->

2 NVMe I/O Requirements

Table 1: OCP command requirement slice

<!-- table: page=2 index=1 mode=gfm -->
| Requirement ID | SSD | Requirement Description | Section |
| --- | --- | --- | --- |
| NVMe-IO-6 | Required | SSD shall support Write Zeroes command for synthetic compliance. | NVMe |

<!-- page: 3 -->

3 Standard Log Requirements

Table 2: OCP log requirement slice

<!-- table: page=3 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Requirement ID</th>
      <th>SSD</th>
      <th>Requirement Description</th>
      <th>Section</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>STD-LOG-1</td>
      <td>Required</td>
      <td>SSD shall expose Error Information Log Identifier 01h for test collection.</td>
      <td>Logs</td>
    </tr>
  </tbody>
</table>

<!-- page: 4 -->

4 Feature Requirements

Table 3: OCP feature requirement slice

<!-- table: page=4 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Requirement ID</th>
      <th>SSD</th>
      <th>Requirement Description</th>
      <th>Section</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>NVMe-OPT-2</td>
      <td>Optional</td>
      <td>SSD should support Feature Identifier 0Eh for timestamp handling.</td>
      <td>Feature</td>
    </tr>
    <tr>
      <td>TEL-1</td>
      <td>Required</td>
      <td>SSD shall report telemetry Statistic Identifier 0001h.</td>
      <td>Telemetry</td>
    </tr>
  </tbody>
</table>

<!-- page: 5 -->

5 Security and Form Factor Requirements

Table 4: OCP security requirement slice

<!-- table: page=5 index=1 mode=gfm -->
| Requirement ID | SSD | Requirement Description | Section |
| --- | --- | --- | --- |
| SEC-43 | Required | SSD shall support SPDM authentication and TCG handoff. | Security |
| FF-1 | Required | SSD shall fit the E1.S form factor envelope. | Mechanical |

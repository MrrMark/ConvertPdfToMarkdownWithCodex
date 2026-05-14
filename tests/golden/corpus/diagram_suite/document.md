<!-- page: 1 -->

## 2.1 State Machine

![Image page-0001-figure-001](./assets/images/page-0001-figure-001.png)

Figure 1: State machine diagram READY ERROR RESET

<!-- table: page=1 index=1 mode=gfm -->
| READY | FAULT |
| --- | --- |
| IDLE | ACTIVE |

<!-- page: 2 -->

## 2.2 Sequence Flow

![Image page-0002-figure-001](./assets/images/page-0002-figure-001.png)

Figure 2: Sequence diagram Command Completion

<!-- table: page=2 index=1 mode=html -->
<table>
  <thead>
    <tr>
      <th>Command</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>Completion</td>
    </tr>
  </tbody>
</table>

<!-- page: 3 -->

## 2.3 Register Layout

![Image page-0003-figure-001](./assets/images/page-0003-figure-001.png)

Figure 3: Register layout bit field RSVD STATUS ENABLE

<!-- table: page=3 index=1 mode=gfm -->
| 31:16 | 15:8 | 7:0 |
| --- | --- | --- |
| RSVD | STATUS | ENABLE |

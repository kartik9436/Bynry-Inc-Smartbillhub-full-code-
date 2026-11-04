---
id: T3P-20
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: capacity, category: IND, read_source: bulk, bill_type: cycle, payment: none, delivery: returned}
dataset_row: "capacity,cycle,none"
---
# T3P-20 · capacity × IND × bulk × cycle × none × returned

Full ride: IND-category account on a capacity plan · reads via staged bulk import (BR-MET-012/038) · billed as cycle · payment none · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as cycle (IND template class per BR-BIL-025) | taxable 129.00 · tax 12.19 · total **141.19** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-005 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 141.19 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

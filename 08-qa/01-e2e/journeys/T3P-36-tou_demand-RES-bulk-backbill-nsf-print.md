---
id: T3P-36
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: RES, read_source: bulk, bill_type: backbill, payment: nsf, delivery: print}
dataset_row: "tou_demand,backbill,nsf"
---
# T3P-36 · tou_demand × RES × bulk × backbill × nsf × print

Full ride: RES-category account on a tou_demand plan · reads via staged bulk import (BR-MET-012/038) · billed as backbill · payment nsf · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as backbill (RES template class per BR-BIL-025) | taxable 2032.20 · tax 192.03 · total **2224.23** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-018 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 2254.23 · credit 0.00 · next fee 33.81 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

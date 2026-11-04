---
id: T3P-10
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: GOV, read_source: bulk, bill_type: penalty, payment: over150, delivery: print}
dataset_row: "tou_demand,penalty,over150"
---
# T3P-10 · tou_demand × GOV × bulk × penalty × over150 × print

Full ride: GOV-category account on a tou_demand plan · reads via staged bulk import (BR-MET-012/038) · billed as penalty · payment over150 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as penalty (GOV template class per BR-BIL-025) | taxable 314.70 · tax 29.74 · total **844.44** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-019 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 1266.66 · outstanding 0.00 · credit 422.22 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

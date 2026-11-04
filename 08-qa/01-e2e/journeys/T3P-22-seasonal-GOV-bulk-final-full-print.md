---
id: T3P-22
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: seasonal, category: GOV, read_source: bulk, bill_type: final, payment: full, delivery: print}
dataset_row: "seasonal,final,full"
---
# T3P-22 · seasonal × GOV × bulk × final × full × print

Full ride: GOV-category account on a seasonal plan · reads via staged bulk import (BR-MET-012/038) · billed as final · payment full · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as final (GOV template class per BR-BIL-025) | taxable 55.00 · tax 5.20 · total **60.20** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-013 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: full | paid 60.20 · outstanding 0.00 · credit 0.00 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

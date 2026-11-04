---
id: T3P-38
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: mixed, category: RES, read_source: bulk, bill_type: cycle, payment: partial60, delivery: print}
dataset_row: "mixed,cycle,partial60"
---
# T3P-38 · mixed × RES × bulk × cycle × partial60 × print

Full ride: RES-category account on a mixed plan · reads via staged bulk import (BR-MET-012/038) · billed as cycle · payment partial60 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as cycle (RES template class per BR-BIL-025) | taxable 221.90 · tax 20.97 · total **242.87** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-005 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: partial60 | paid 145.72 · outstanding 97.15 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

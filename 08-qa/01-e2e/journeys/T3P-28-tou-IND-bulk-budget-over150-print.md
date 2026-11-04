---
id: T3P-28
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou, category: IND, read_source: bulk, bill_type: budget, payment: over150, delivery: print}
dataset_row: "tou,budget,over150"
---
# T3P-28 · tou × IND × bulk × budget × over150 × print

Full ride: IND-category account on a tou plan · reads via staged bulk import (BR-MET-012/038) · billed as budget · payment over150 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as budget (IND template class per BR-BIL-025) | taxable 100.60 · tax 9.51 · total **110.11** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-017 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 165.17 · outstanding 0.00 · credit 55.06 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

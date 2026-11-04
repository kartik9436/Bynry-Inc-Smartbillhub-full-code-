---
id: T3P-31
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou, category: RES, read_source: estimated, bill_type: first, payment: full, delivery: print}
dataset_row: "tou,first,full"
---
# T3P-31 · tou × RES × estimated × first × full × print

Full ride: RES-category account on a tou plan · reads via estimate + later true-up (BR-MET-026..029) · billed as first · payment full · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as first (RES template class per BR-BIL-025) | taxable 64.89 · tax 6.14 · total **246.03** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-012 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: full | paid 246.03 · outstanding 0.00 · credit 0.00 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

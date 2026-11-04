---
id: T3P-34
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: flat, category: RES, read_source: corrected, bill_type: penalty, payment: none, delivery: print}
dataset_row: "flat,penalty,none"
---
# T3P-34 · flat × RES × corrected × penalty × none × print

Full ride: RES-category account on a flat plan · reads via supersede-corrected read (BR-MET-053) · billed as penalty · payment none · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as penalty (RES template class per BR-BIL-025) | taxable 38.50 · tax 3.65 · total **542.15** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-019 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 542.15 · credit 0.00 · next fee 8.13 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

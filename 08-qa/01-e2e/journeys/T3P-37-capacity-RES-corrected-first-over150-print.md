---
id: T3P-37
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: capacity, category: RES, read_source: corrected, bill_type: first, payment: over150, delivery: print}
dataset_row: "capacity,first,over150"
---
# T3P-37 · capacity × RES × corrected × first × over150 × print

Full ride: RES-category account on a capacity plan · reads via supersede-corrected read (BR-MET-053) · billed as first · payment over150 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as first (RES template class per BR-BIL-025) | taxable 83.23 · tax 7.86 · total **266.09** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-012 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 399.14 · outstanding 0.00 · credit 133.05 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

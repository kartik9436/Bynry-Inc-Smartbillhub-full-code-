---
id: T3P-27
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: COM, read_source: corrected, bill_type: cycle, payment: partial60, delivery: print}
dataset_row: "tiered,cycle,partial60"
---
# T3P-27 · tiered × COM × corrected × cycle × partial60 × print

Full ride: COM-category account on a tiered plan · reads via supersede-corrected read (BR-MET-053) · billed as cycle · payment partial60 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as cycle (COM template class per BR-BIL-025) | taxable 63.30 · tax 5.99 · total **69.29** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-005 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: partial60 | paid 41.57 · outstanding 27.72 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

---
id: T3P-23
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: flat, category: GOV, read_source: corrected, bill_type: rebill, payment: partial60, delivery: print}
dataset_row: "flat,rebill,partial60"
---
# T3P-23 · flat × GOV × corrected × rebill × partial60 × print

Full ride: GOV-category account on a flat plan · reads via supersede-corrected read (BR-MET-053) · billed as rebill · payment partial60 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as rebill (GOV template class per BR-BIL-025) | taxable 69.75 · tax 6.60 · total **76.35** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-014 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: partial60 | paid 45.81 · outstanding 30.54 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

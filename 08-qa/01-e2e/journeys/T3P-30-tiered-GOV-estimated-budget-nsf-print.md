---
id: T3P-30
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: GOV, read_source: estimated, bill_type: budget, payment: nsf, delivery: print}
dataset_row: "tiered,budget,nsf"
---
# T3P-30 · tiered × GOV × estimated × budget × nsf × print

Full ride: GOV-category account on a tiered plan · reads via estimate + later true-up (BR-MET-026..029) · billed as budget · payment nsf · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as budget (GOV template class per BR-BIL-025) | taxable 63.30 · tax 5.99 · total **69.29** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-017 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 99.29 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

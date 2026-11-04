---
id: T3P-12
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: capacity, category: GOV, read_source: estimated, bill_type: cycle, payment: nsf, delivery: email_w6}
dataset_row: "capacity,cycle,nsf"
---
# T3P-12 · capacity × GOV × estimated × cycle × nsf × email_w6

Full ride: GOV-category account on a capacity plan · reads via estimate + later true-up (BR-MET-026..029) · billed as cycle · payment nsf · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as cycle (GOV template class per BR-BIL-025) | taxable 129.00 · tax 12.19 · total **141.19** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-005 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 171.19 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

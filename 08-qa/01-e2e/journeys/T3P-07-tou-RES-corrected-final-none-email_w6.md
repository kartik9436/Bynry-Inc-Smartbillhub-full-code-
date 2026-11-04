---
id: T3P-07
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou, category: RES, read_source: corrected, bill_type: final, payment: none, delivery: email_w6}
dataset_row: "tou,final,none"
---
# T3P-07 · tou × RES × corrected × final × none × email_w6

Full ride: RES-category account on a tou plan · reads via supersede-corrected read (BR-MET-053) · billed as final · payment none · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as final (RES template class per BR-BIL-025) | taxable 58.42 · tax 5.52 · total **63.94** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-013 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 63.94 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

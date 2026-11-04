---
id: T3P-17
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: IND, read_source: manual, bill_type: budget, payment: none, delivery: email_w6}
dataset_row: "tou_demand,budget,none"
---
# T3P-17 · tou_demand × IND × manual × budget × none × email_w6

Full ride: IND-category account on a tou_demand plan · reads via single manual entry (BR-MET-054) · billed as budget · payment none · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as budget (IND template class per BR-BIL-025) | taxable 677.40 · tax 64.01 · total **741.41** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-017 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 741.41 · credit 0.00 · next fee 11.12 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

---
id: T3P-09
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: COM, read_source: corrected, bill_type: budget, payment: full, delivery: returned}
dataset_row: "tou_demand,budget,full"
---
# T3P-09 · tou_demand × COM × corrected × budget × full × returned

Full ride: COM-category account on a tou_demand plan · reads via supersede-corrected read (BR-MET-053) · billed as budget · payment full · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as budget (COM template class per BR-BIL-025) | taxable 677.40 · tax 64.01 · total **741.41** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-017 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: full | paid 741.41 · outstanding 0.00 · credit 0.00 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

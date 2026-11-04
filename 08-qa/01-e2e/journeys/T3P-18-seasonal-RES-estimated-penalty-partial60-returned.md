---
id: T3P-18
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: seasonal, category: RES, read_source: estimated, bill_type: penalty, payment: partial60, delivery: returned}
dataset_row: "seasonal,penalty,partial60"
---
# T3P-18 · seasonal × RES × estimated × penalty × partial60 × returned

Full ride: RES-category account on a seasonal plan · reads via estimate + later true-up (BR-MET-026..029) · billed as penalty · payment partial60 · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as penalty (RES template class per BR-BIL-025) | taxable 41.36 · tax 3.91 · total **545.27** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-019 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: partial60 | paid 327.16 · outstanding 218.11 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

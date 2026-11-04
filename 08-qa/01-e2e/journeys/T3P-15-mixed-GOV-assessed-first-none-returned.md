---
id: T3P-15
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: mixed, category: GOV, read_source: assessed, bill_type: first, payment: none, delivery: returned}
dataset_row: "mixed,first,none"
---
# T3P-15 · mixed × GOV × assessed × first × none × returned

Full ride: GOV-category account on a mixed plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as first · payment none · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as first (GOV template class per BR-BIL-025) | taxable 143.14 · tax 13.53 · total **331.67** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-012 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 331.67 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

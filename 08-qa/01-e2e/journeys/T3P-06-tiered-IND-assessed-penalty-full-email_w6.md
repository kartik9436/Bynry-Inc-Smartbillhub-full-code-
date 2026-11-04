---
id: T3P-06
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: IND, read_source: assessed, bill_type: penalty, payment: full, delivery: email_w6}
dataset_row: "tiered,penalty,full"
---
# T3P-06 · tiered × IND × assessed × penalty × full × email_w6

Full ride: IND-category account on a tiered plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as penalty · payment full · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as penalty (IND template class per BR-BIL-025) | taxable 19.75 · tax 1.87 · total **521.62** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-019 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: full | paid 521.62 · outstanding 0.00 · credit 0.00 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

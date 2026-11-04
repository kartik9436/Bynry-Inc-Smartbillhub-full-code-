---
id: T3P-13
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: seasonal, category: COM, read_source: manual, bill_type: rebill, payment: over150, delivery: email_w6}
dataset_row: "seasonal,rebill,over150"
---
# T3P-13 · seasonal × COM × manual × rebill × over150 × email_w6

Full ride: COM-category account on a seasonal plan · reads via single manual entry (BR-MET-054) · billed as rebill · payment over150 · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as rebill (COM template class per BR-BIL-025) | taxable 91.20 · tax 8.61 · total **99.81** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-014 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 149.72 · outstanding 0.00 · credit 49.91 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

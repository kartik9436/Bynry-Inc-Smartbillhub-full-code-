---
id: T3P-19
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: mixed, category: RES, read_source: corrected, bill_type: backbill, payment: over150, delivery: email_w6}
dataset_row: "mixed,backbill,over150"
---
# T3P-19 · mixed × RES × corrected × backbill × over150 × email_w6

Full ride: RES-category account on a mixed plan · reads via supersede-corrected read (BR-MET-053) · billed as backbill · payment over150 · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: supersede-corrected read (BR-MET-053) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as backbill (RES template class per BR-BIL-025) | taxable 665.70 · tax 62.91 · total **728.61** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-018 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 1092.92 · outstanding 0.00 · credit 364.31 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

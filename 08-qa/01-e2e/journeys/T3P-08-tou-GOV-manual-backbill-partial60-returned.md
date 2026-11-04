---
id: T3P-08
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou, category: GOV, read_source: manual, bill_type: backbill, payment: partial60, delivery: returned}
dataset_row: "tou,backbill,partial60"
---
# T3P-08 · tou × GOV × manual × backbill × partial60 × returned

Full ride: GOV-category account on a tou plan · reads via single manual entry (BR-MET-054) · billed as backbill · payment partial60 · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as backbill (GOV template class per BR-BIL-025) | taxable 301.80 · tax 28.53 · total **330.33** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-018 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: partial60 | paid 198.20 · outstanding 132.13 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

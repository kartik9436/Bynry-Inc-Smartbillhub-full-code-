---
id: T3P-03
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: flat, category: IND, read_source: estimated, bill_type: final, payment: over150, delivery: returned}
dataset_row: "flat,final,over150"
---
# T3P-03 · flat × IND × estimated × final × over150 × returned

Full ride: IND-category account on a flat plan · reads via estimate + later true-up (BR-MET-026..029) · billed as final · payment over150 · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as final (IND template class per BR-BIL-025) | taxable 51.68 · tax 4.88 · total **56.56** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-013 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: over150 | paid 84.84 · outstanding 0.00 · credit 28.28 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

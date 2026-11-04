---
id: T3P-16
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou, category: COM, read_source: assessed, bill_type: final, payment: nsf, delivery: print}
dataset_row: "tou,final,nsf"
---
# T3P-16 · tou × COM × assessed × final × nsf × print

Full ride: COM-category account on a tou plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as final · payment nsf · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as final (COM template class per BR-BIL-025) | taxable 58.42 · tax 5.52 · total **63.94** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-013 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 93.94 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

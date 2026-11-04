---
id: T3P-29
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: RES, read_source: assessed, bill_type: cycle, payment: over150, delivery: print}
dataset_row: "tou_demand,cycle,over150"
---
# T3P-29 · tou_demand × RES × assessed × cycle × over150 × print

Full ride: RES-category account on a tou_demand plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as cycle · payment over150 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as cycle (RES template class per BR-BIL-025) | taxable 677.40 · tax 64.01 · total **741.41** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-005 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 1112.12 · outstanding 0.00 · credit 370.71 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

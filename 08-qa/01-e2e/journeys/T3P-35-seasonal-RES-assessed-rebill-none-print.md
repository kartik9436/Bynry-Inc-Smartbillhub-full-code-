---
id: T3P-35
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: seasonal, category: RES, read_source: assessed, bill_type: rebill, payment: none, delivery: print}
dataset_row: "seasonal,rebill,none"
---
# T3P-35 · seasonal × RES × assessed × rebill × none × print

Full ride: RES-category account on a seasonal plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as rebill · payment none · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as rebill (RES template class per BR-BIL-025) | taxable 91.20 · tax 8.61 · total **99.81** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-014 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 99.81 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

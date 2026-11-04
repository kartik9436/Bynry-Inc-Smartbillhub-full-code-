---
id: T3P-25
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: flat, category: IND, read_source: assessed, bill_type: backbill, payment: nsf, delivery: print}
dataset_row: "flat,backbill,nsf"
---
# T3P-25 · flat × IND × assessed × backbill × nsf × print

Full ride: IND-category account on a flat plan · reads via assessed reads, reason-coded (BR-BIL-019) · billed as backbill · payment nsf · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: assessed reads, reason-coded (BR-BIL-019) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as backbill (IND template class per BR-BIL-025) | taxable 267.00 · tax 25.23 · total **292.23** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-018 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 322.23 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

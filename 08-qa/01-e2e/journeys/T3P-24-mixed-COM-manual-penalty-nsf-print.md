---
id: T3P-24
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: mixed, category: COM, read_source: manual, bill_type: penalty, payment: nsf, delivery: print}
dataset_row: "mixed,penalty,nsf"
---
# T3P-24 · mixed × COM × manual × penalty × nsf × print

Full ride: COM-category account on a mixed plan · reads via single manual entry (BR-MET-054) · billed as penalty · payment nsf · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as penalty (COM template class per BR-BIL-025) | taxable 64.05 · tax 6.05 · total **570.10** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-019 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 600.10 · credit 0.00 · next fee 9.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

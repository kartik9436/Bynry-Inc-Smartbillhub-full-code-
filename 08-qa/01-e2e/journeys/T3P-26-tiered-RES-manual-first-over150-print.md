---
id: T3P-26
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: RES, read_source: manual, bill_type: first, payment: over150, delivery: print}
dataset_row: "tiered,first,over150"
---
# T3P-26 · tiered × RES × manual × first × over150 × print

Full ride: RES-category account on a tiered plan · reads via single manual entry (BR-MET-054) · billed as first · payment over150 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as first (RES template class per BR-BIL-025) | taxable 40.83 · tax 3.86 · total **219.69** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-012 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: over150 | paid 329.54 · outstanding 0.00 · credit 109.85 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

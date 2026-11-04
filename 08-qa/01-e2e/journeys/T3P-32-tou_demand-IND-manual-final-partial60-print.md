---
id: T3P-32
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: IND, read_source: manual, bill_type: final, payment: partial60, delivery: print}
dataset_row: "tou_demand,final,partial60"
---
# T3P-32 · tou_demand × IND × manual × final × partial60 × print

Full ride: IND-category account on a tou_demand plan · reads via single manual entry (BR-MET-054) · billed as final · payment partial60 · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as final (IND template class per BR-BIL-025) | taxable 449.90 · tax 42.52 · total **492.42** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-013 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: partial60 | paid 295.45 · outstanding 196.97 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

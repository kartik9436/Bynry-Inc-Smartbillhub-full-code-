---
id: T3P-45
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tou_demand, category: RES, read_source: manual, bill_type: rebill, payment: full, delivery: print}
dataset_row: "tou_demand,rebill,full"
---
# T3P-45 · tou_demand × RES × manual × rebill × full × print

Full ride: RES-category account on a tou_demand plan · reads via single manual entry (BR-MET-054) · billed as rebill · payment full · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: single manual entry (BR-MET-054) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as rebill (RES template class per BR-BIL-025) | taxable 637.03 · tax 60.19 · total **697.22** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-014 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: full | paid 697.22 · outstanding 0.00 · credit 0.00 · next fee 0.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

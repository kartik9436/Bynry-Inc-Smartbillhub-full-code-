---
id: T3P-05
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: COM, read_source: estimated, bill_type: backbill, payment: none, delivery: print}
dataset_row: "tiered,backbill,none"
---
# T3P-05 · tiered × COM × estimated × backbill × none × print

Full ride: COM-category account on a tiered plan · reads via estimate + later true-up (BR-MET-026..029) · billed as backbill · payment none · delivered print/PDF queue row (BR-NOT-005).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: estimate + later true-up (BR-MET-026..029) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as backbill (COM template class per BR-BIL-025) | taxable 189.90 · tax 17.97 · total **207.87** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-018 |
| 3 | Delivery: print | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: none | paid 0.00 · outstanding 207.87 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

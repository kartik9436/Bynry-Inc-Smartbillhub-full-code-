---
id: T3P-04
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: tiered, category: RES, read_source: bulk, bill_type: rebill, payment: nsf, delivery: returned}
dataset_row: "tiered,rebill,nsf"
---
# T3P-04 · tiered × RES × bulk × rebill × nsf × returned

Full ride: RES-category account on a tiered plan · reads via staged bulk import (BR-MET-012/038) · billed as rebill · payment nsf · delivered print returned → bad-address flag + suppression (BR-PAY-018).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as rebill (RES template class per BR-BIL-025) | taxable 58.30 · tax 5.51 · total **63.81** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-014 |
| 3 | Delivery: returned | queue row(s) per channel | dispatch pacing; suppression + needs-attention queue | BR-NOT-005 |
| 4 | Payment: nsf | paid 0.00 · outstanding 93.81 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

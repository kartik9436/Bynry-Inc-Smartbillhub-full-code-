---
id: T3P-02
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {shape: flat, category: COM, read_source: bulk, bill_type: first, payment: partial60, delivery: email_w6}
dataset_row: "flat,first,partial60"
---
# T3P-02 · flat × COM × bulk × first × partial60 × email_w6

Full ride: COM-category account on a flat plan · reads via staged bulk import (BR-MET-012/038) · billed as first · payment partial60 · delivered email queue row, W6-deferred send flag (OQ-073).

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: staged bulk import (BR-MET-012/038) | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as first (COM template class per BR-BIL-025) | taxable 57.42 · tax 5.42 · total **237.84** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, BR-BIL-012 |
| 3 | Delivery: email_w6 | queue row(s) per channel | dispatch pacing; status lifecycle | BR-NOT-005 |
| 4 | Payment: partial60 | paid 142.70 · outstanding 95.14 · credit 0.00 · next fee 5.00 | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |

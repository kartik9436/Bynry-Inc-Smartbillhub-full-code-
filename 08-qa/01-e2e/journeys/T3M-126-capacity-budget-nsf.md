---
id: T3M-126
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: capacity, bill_type: budget, payment: nsf}
dataset_row: "capacity,budget,nsf"
rules: [BR-BIL-017, BR-PAY-013]
---
# T3M-126 · capacity × budget × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the capacity fixture as budget | taxable 129.00 · tax 12.19 · total **141.19** · level 141; variance -0.19 (BR-BIL-017) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 141.19-class / CR buckets); delivery row queued; audit row | BR-BIL-017 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 171.19 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

---
id: T3M-042
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tiered, bill_type: budget, payment: nsf}
dataset_row: "tiered,budget,nsf"
rules: [BR-BIL-017, BR-PAY-013]
---
# T3M-042 · tiered × budget × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tiered fixture as budget | taxable 63.30 · tax 5.99 · total **69.29** · level 69; variance -0.29 (BR-BIL-017) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 69.29-class / CR buckets); delivery row queued; audit row | BR-BIL-017 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 99.29 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

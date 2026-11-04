---
id: T3M-120
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: capacity, bill_type: backbill, payment: nsf}
dataset_row: "capacity,backbill,nsf"
rules: [BR-BIL-018, BR-PAY-013]
---
# T3M-120 · capacity × backbill × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the capacity fixture as backbill | taxable 387.00 · tax 36.57 · total **423.57** · 3 months, period-labeled groups, per-version pricing (BR-BIL-018) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 423.57-class / CR buckets); delivery row queued; audit row | BR-BIL-018 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 453.57 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 6.80 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

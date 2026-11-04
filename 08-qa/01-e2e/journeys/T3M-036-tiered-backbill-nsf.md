---
id: T3M-036
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tiered, bill_type: backbill, payment: nsf}
dataset_row: "tiered,backbill,nsf"
rules: [BR-BIL-018, BR-PAY-013]
---
# T3M-036 · tiered × backbill × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tiered fixture as backbill | taxable 189.90 · tax 17.97 · total **207.87** · 3 months, period-labeled groups, per-version pricing (BR-BIL-018) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 207.87-class / CR buckets); delivery row queued; audit row | BR-BIL-018 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 237.87 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

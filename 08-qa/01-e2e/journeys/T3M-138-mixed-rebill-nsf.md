---
id: T3M-138
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: mixed, bill_type: rebill, payment: nsf}
dataset_row: "mixed,rebill,nsf"
rules: [BR-BIL-014/004, BR-PAY-013]
---
# T3M-138 · mixed × rebill × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the mixed fixture as rebill | taxable 215.30 · tax 20.35 · total **235.65** · credit note -242.87; customer delta 7.22 (BR-BIL-014) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 235.65-class / CR buckets); delivery row queued; audit row | BR-BIL-014/004 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 265.65 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

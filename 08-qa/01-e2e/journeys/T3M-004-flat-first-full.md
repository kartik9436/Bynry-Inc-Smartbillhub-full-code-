---
id: T3M-004
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: flat, bill_type: first, payment: full}
dataset_row: "flat,first,full"
rules: [BR-BIL-012, BR-PAY-010/021]
---
# T3M-004 · flat × first × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the flat fixture as first | taxable 57.42 · tax 5.42 · total **237.84** · deposit 150.00 + CONN 25.00 non-taxable (BR-BIL-012) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 237.84-class / CR buckets); delivery row queued; audit row | BR-BIL-012 |
| 2 | Payment outcome: full | paid 237.84 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

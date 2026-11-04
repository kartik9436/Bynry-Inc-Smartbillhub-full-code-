---
id: T3M-002
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: flat, bill_type: cycle, payment: partial60}
dataset_row: "flat,cycle,partial60"
rules: [BR-BIL-005/011/024, BR-PAY-010/032]
---
# T3M-002 · flat × cycle × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the flat fixture as cycle | taxable 89.00 · tax 8.41 · total **97.41**  | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 97.41-class / CR buckets); delivery row queued; audit row | BR-BIL-005/011/024 |
| 2 | Payment outcome: partial60 | paid 58.45 · outstanding 38.96 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

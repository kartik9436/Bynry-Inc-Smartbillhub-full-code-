---
id: T3M-046
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tou, bill_type: first, payment: full}
dataset_row: "tou,first,full"
rules: [BR-BIL-012, BR-PAY-010/021]
---
# T3M-046 · tou × first × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tou fixture as first | taxable 64.89 · tax 6.14 · total **246.03** · deposit 150.00 + CONN 25.00 non-taxable (BR-BIL-012) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 246.03-class / CR buckets); delivery row queued; audit row | BR-BIL-012 |
| 2 | Payment outcome: full | paid 246.03 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

---
id: T3M-032
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tiered, bill_type: rebill, payment: partial60}
dataset_row: "tiered,rebill,partial60"
rules: [BR-BIL-014/004, BR-PAY-010/032]
---
# T3M-032 · tiered × rebill × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tiered fixture as rebill | taxable 58.30 · tax 5.51 · total **63.81** · credit note -69.29; customer delta 5.48 (BR-BIL-014) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 63.81-class / CR buckets); delivery row queued; audit row | BR-BIL-014/004 |
| 2 | Payment outcome: partial60 | paid 38.29 · outstanding 25.52 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

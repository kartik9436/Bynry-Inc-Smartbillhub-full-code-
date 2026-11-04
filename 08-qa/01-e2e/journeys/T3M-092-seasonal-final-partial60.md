---
id: T3M-092
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: seasonal, bill_type: final, payment: partial60}
dataset_row: "seasonal,final,partial60"
rules: [BR-BIL-013, BR-PAY-010/032]
---
# T3M-092 · seasonal × final × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the seasonal fixture as final | taxable 55.00 · tax 5.20 · total **60.20** · deposit credit 153.50 applies; settlement path per BR-BIL-013 | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 60.20-class / CR buckets); delivery row queued; audit row | BR-BIL-013 |
| 2 | Payment outcome: partial60 | paid 36.12 · outstanding 24.08 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

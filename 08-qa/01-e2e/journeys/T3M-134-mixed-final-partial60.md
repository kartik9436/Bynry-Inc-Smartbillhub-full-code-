---
id: T3M-134
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: mixed, bill_type: final, payment: partial60}
dataset_row: "mixed,final,partial60"
rules: [BR-BIL-013, BR-PAY-010/032]
---
# T3M-134 · mixed × final × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the mixed fixture as final | taxable 128.85 · tax 12.18 · total **141.03** · deposit credit 153.50 applies; settlement path per BR-BIL-013 | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 141.03-class / CR buckets); delivery row queued; audit row | BR-BIL-013 |
| 2 | Payment outcome: partial60 | paid 84.62 · outstanding 56.41 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

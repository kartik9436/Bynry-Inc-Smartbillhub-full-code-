---
id: T3M-146
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: mixed, bill_type: budget, payment: partial60}
dataset_row: "mixed,budget,partial60"
rules: [BR-BIL-017, BR-PAY-010/032]
---
# T3M-146 · mixed × budget × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the mixed fixture as budget | taxable 221.90 · tax 20.97 · total **242.87** · level 243; variance 0.13 (BR-BIL-017) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 242.87-class / CR buckets); delivery row queued; audit row | BR-BIL-017 |
| 2 | Payment outcome: partial60 | paid 145.72 · outstanding 97.15 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

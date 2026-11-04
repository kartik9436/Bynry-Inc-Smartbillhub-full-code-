---
id: T3M-083
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tou_demand, bill_type: budget, payment: partial60}
dataset_row: "tou_demand,budget,partial60"
rules: [BR-BIL-017, BR-PAY-010/032]
---
# T3M-083 · tou_demand × budget × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tou_demand fixture as budget | taxable 677.40 · tax 64.01 · total **741.41** · level 741; variance -0.41 (BR-BIL-017) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 741.41-class / CR buckets); delivery row queued; audit row | BR-BIL-017 |
| 2 | Payment outcome: partial60 | paid 444.85 · outstanding 296.56 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

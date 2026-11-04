---
id: T3M-070
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tou_demand, bill_type: final, payment: full}
dataset_row: "tou_demand,final,full"
rules: [BR-BIL-013, BR-PAY-010/021]
---
# T3M-070 · tou_demand × final × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tou_demand fixture as final | taxable 449.90 · tax 42.52 · total **492.42** · deposit credit 153.50 applies; settlement path per BR-BIL-013 | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 492.42-class / CR buckets); delivery row queued; audit row | BR-BIL-013 |
| 2 | Payment outcome: full | paid 492.42 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

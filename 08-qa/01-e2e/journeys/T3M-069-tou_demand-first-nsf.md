---
id: T3M-069
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tou_demand, bill_type: first, payment: nsf}
dataset_row: "tou_demand,first,nsf"
rules: [BR-BIL-012, BR-PAY-013]
---
# T3M-069 · tou_demand × first × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tou_demand fixture as first | taxable 484.90 · tax 45.83 · total **705.73** · deposit 150.00 + CONN 25.00 non-taxable (BR-BIL-012) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 705.73-class / CR buckets); delivery row queued; audit row | BR-BIL-012 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 735.73 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 11.04 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

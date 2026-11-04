---
id: T3M-012
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: flat, bill_type: rebill, payment: nsf}
dataset_row: "flat,rebill,nsf"
rules: [BR-BIL-014/004, BR-PAY-013]
---
# T3M-012 · flat × rebill × nsf

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the flat fixture as rebill | taxable 69.75 · tax 6.60 · total **76.35** · credit note -97.41; customer delta 21.06 (BR-BIL-014) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 76.35-class / CR buckets); delivery row queued; audit row | BR-BIL-014/004 |
| 2 | Payment outcome: nsf | paid 0.00 · outstanding 106.35 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-013 (original due date; +30.00 fee; privilege count) |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

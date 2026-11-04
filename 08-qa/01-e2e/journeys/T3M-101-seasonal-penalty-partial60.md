---
id: T3M-101
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: seasonal, bill_type: penalty, payment: partial60}
dataset_row: "seasonal,penalty,partial60"
rules: [BR-BIL-019, BR-PAY-010/032]
---
# T3M-101 · seasonal × penalty × partial60

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the seasonal fixture as penalty | taxable 41.36 · tax 3.91 · total **545.27** · assessed reads 50% + TAMPER 500.00 non-taxable (BR-BIL-019) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 545.27-class / CR buckets); delivery row queued; audit row | BR-BIL-019 |
| 2 | Payment outcome: partial60 | paid 327.16 · outstanding 218.11 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/032 + BR-BIL-001 overdue-portion |
| 3 | Next late-fee evaluation | 5.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

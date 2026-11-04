---
id: T3M-121
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: capacity, bill_type: penalty, payment: full}
dataset_row: "capacity,penalty,full"
rules: [BR-BIL-019, BR-PAY-010/021]
---
# T3M-121 · capacity × penalty × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the capacity fixture as penalty | taxable 38.50 · tax 3.65 · total **542.15** · assessed reads 50% + TAMPER 500.00 non-taxable (BR-BIL-019) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 542.15-class / CR buckets); delivery row queued; audit row | BR-BIL-019 |
| 2 | Payment outcome: full | paid 542.15 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

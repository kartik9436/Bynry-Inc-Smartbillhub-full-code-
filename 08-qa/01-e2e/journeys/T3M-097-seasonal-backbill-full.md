---
id: T3M-097
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: seasonal, bill_type: backbill, payment: full}
dataset_row: "seasonal,backbill,full"
rules: [BR-BIL-018, BR-PAY-010/021]
---
# T3M-097 · seasonal × backbill × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the seasonal fixture as backbill | taxable 284.16 · tax 26.85 · total **311.01** · 3 months, period-labeled groups, per-version pricing (BR-BIL-018) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 311.01-class / CR buckets); delivery row queued; audit row | BR-BIL-018 |
| 2 | Payment outcome: full | paid 311.01 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

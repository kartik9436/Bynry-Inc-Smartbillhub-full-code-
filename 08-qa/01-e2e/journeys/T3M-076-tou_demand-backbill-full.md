---
id: T3M-076
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {shape: tou_demand, bill_type: backbill, payment: full}
dataset_row: "tou_demand,backbill,full"
rules: [BR-BIL-018, BR-PAY-010/021]
---
# T3M-076 · tou_demand × backbill × full

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the tou_demand fixture as backbill | taxable 2032.20 · tax 192.03 · total **2224.23** · 3 months, period-labeled groups, per-version pricing (BR-BIL-018) | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR 2224.23-class / CR buckets); delivery row queued; audit row | BR-BIL-018 |
| 2 | Payment outcome: full | paid 2224.23 · outstanding 0.00 · credit 0.00 | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | BR-PAY-010/021 |
| 3 | Next late-fee evaluation | 0.00 on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |

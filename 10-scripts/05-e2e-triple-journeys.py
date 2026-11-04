#!/usr/bin/env python3
"""Generate T3M money-triple journey files from expected/money-triples.csv.
Authored subset per design §2: all shapes x all bill types x payments
{full, partial60, nsf} = 147 files; remaining dataset rows are data-covered.
Deterministic; re-runnable (overwrites T3M-*). QA scaffolding."""
import csv, os

RULES = {"cycle": "BR-BIL-005/011/024", "first": "BR-BIL-012", "final": "BR-BIL-013",
         "rebill": "BR-BIL-014/004", "backbill": "BR-BIL-018", "penalty": "BR-BIL-019",
         "budget": "BR-BIL-017"}
PAYR = {"full": "BR-PAY-010/021", "partial60": "BR-PAY-010/032 + BR-BIL-001 overdue-portion",
        "nsf": "BR-PAY-013 (original due date; +30.00 fee; privilege count)"}
rows = list(csv.DictReader(open("08-qa/01-e2e/expected/money-triples.csv")))
n = 0
for r in rows:
    if r["payment"] not in ("full", "partial60", "nsf"):
        continue
    n += 1
    fid = f"T3M-{n:03d}"
    fn = f"08-qa/01-e2e/journeys/{fid}-{r['shape']}-{r['bill_type']}-{r['payment']}.md"
    with open(fn, "w") as f:
        f.write(f"""---
id: {fid}
tier: 3
kind: money-triple (generated — 10-scripts/05-e2e-triple-journeys.py; do not hand-edit)
axes: {{shape: {r['shape']}, bill_type: {r['bill_type']}, payment: {r['payment']}}}
dataset_row: "{r['shape']},{r['bill_type']},{r['payment']}"
rules: [{RULES[r['bill_type']]}, {PAYR[r['payment']].split(' ')[0]}]
---
# {fid} · {r['shape']} × {r['bill_type']} × {r['payment']}

Full ride at this combination; every figure from expected/money-triples.csv (frozen B4 math).

| # | Step | Expected (dataset) | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Bill the {r['shape']} fixture as {r['bill_type']} | taxable {r['taxable']} · tax {r['tax']} · total **{r['total']}** {("· " + r['notes']) if r['notes'] else ""} | invoice lines GL-stamped + taxable-flagged; posting balanced (DR AR {r['total']}-class / CR buckets); delivery row queued; audit row | {RULES[r['bill_type']]} |
| 2 | Payment outcome: {r['payment']} | paid {r['paid']} · outstanding {r['outstanding']} · credit {r['credit']} | allocation per BR-PAY-010; posting-date basis on billing KPIs (BR-REP-001); receipt queued if cleared; audit | {PAYR[r['payment']]} |
| 3 | Next late-fee evaluation | {r['next_late_fee']} on the overdue portion | fee line non-taxable when assessed; aging reads posting date | BR-BIL-001/008 |
| 4 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold (BR-LED-007) | HR-4/5 |
""")
print(f"generated {n} T3M journey files")

#!/usr/bin/env python3
"""T3P pairwise covering-array generator (agent replacement — deterministic).
Greedy pairwise over axes A-F; emits T3P journey files + a PROVEN coverage
matrix (every cross-axis pair -> journey id). Money figures cite the
money-triples dataset row for (A,D,E). Deterministic; re-runnable."""
import csv, itertools, os

AX = {"A": ["flat","tiered","tou","tou_demand","seasonal","capacity","mixed"],
      "B": ["RES","COM","IND","GOV"],
      "C": ["manual","bulk","estimated","assessed","corrected"],
      "D": ["cycle","first","final","rebill","backbill","penalty","budget"],
      "E": ["full","partial60","over150","nsf","none"],
      "F": ["print","email_w6","returned"]}
keys = list(AX)
pairs = set()
for i, j in itertools.combinations(range(len(keys)), 2):
    for v1 in AX[keys[i]]:
        for v2 in AX[keys[j]]:
            pairs.add((keys[i], v1, keys[j], v2))
total_pairs = len(pairs)

ds = {(r["shape"], r["bill_type"], r["payment"]): r
      for r in csv.DictReader(open("08-qa/01-e2e/expected/money-triples.csv"))}

combos = []
uncovered = set(pairs)
# deterministic greedy: scan the full cartesian in a fixed rotated order, pick best each round
cart = list(itertools.product(*[AX[k] for k in keys]))
while uncovered:
    best, best_gain = None, -1
    for idx, c in enumerate(cart):
        gain = 0
        for i, j in itertools.combinations(range(6), 2):
            if (keys[i], c[i], keys[j], c[j]) in uncovered:
                gain += 1
        if gain > best_gain:
            best, best_gain = c, gain
        if best_gain == 15:  # max possible pairs per row
            break
    combos.append(best)
    for i, j in itertools.combinations(range(6), 2):
        uncovered.discard((keys[i], best[i], keys[j], best[j]))

CNARR = {"manual": "single manual entry (BR-MET-054)", "bulk": "staged bulk import (BR-MET-012/038)",
         "estimated": "estimate + later true-up (BR-MET-026..029)", "assessed": "assessed reads, reason-coded (BR-BIL-019)",
         "corrected": "supersede-corrected read (BR-MET-053)"}
FNARR = {"print": "print/PDF queue row (BR-NOT-005)", "email_w6": "email queue row, W6-deferred send flag (OQ-073)",
         "returned": "print returned → bad-address flag + suppression (BR-PAY-018)"}
cover_map = []
for n, c in enumerate(combos, 1):
    a, b, cx, d, e, f = c
    r = ds.get((a, d, e))
    fid = f"T3P-{n:02d}"
    newly = []
    with open(f"08-qa/01-e2e/journeys/{fid}-{a}-{b}-{cx}-{d}-{e}-{f}.md", "w") as fh:
        fh.write(f"""---
id: {fid}
tier: 3
kind: pairwise (generated — 10-scripts/06-e2e-pairwise.py; do not hand-edit)
axes: {{shape: {a}, category: {b}, read_source: {cx}, bill_type: {d}, payment: {e}, delivery: {f}}}
dataset_row: "{a},{d},{e}"
---
# {fid} · {a} × {b} × {cx} × {d} × {e} × {f}

Full ride: {b}-category account on a {a} plan · reads via {CNARR[cx]} · billed as {d} · payment {e} · delivered {FNARR[f]}.

| # | Step | Expected | Downstream assertions | Rule |
|---|---|---|---|---|
| 1 | Reads arrive: {CNARR[cx]} | committed rows, plan-complete channel set | VEE per BR-MET-052; audit | BR-MET-049 |
| 2 | Bill as {d} ({b} template class per BR-BIL-025) | taxable {r['taxable']} · tax {r['tax']} · total **{r['total']}** | GL-stamped lines; balanced posting; category deposit rules referenced | BR-BIL-011, {'{}'.format('BR-BIL-012' if d=='first' else 'BR-BIL-013' if d=='final' else 'BR-BIL-017' if d=='budget' else 'BR-BIL-018' if d=='backbill' else 'BR-BIL-019' if d=='penalty' else 'BR-BIL-014' if d=='rebill' else 'BR-BIL-005')} |
| 3 | Delivery: {f} | queue row(s) per channel | dispatch pacing; {'suppression + needs-attention queue' if f=='returned' else 'status lifecycle'} | BR-NOT-005 |
| 4 | Payment: {e} | paid {r['paid']} · outstanding {r['outstanding']} · credit {r['credit']} · next fee {r['next_late_fee']} | allocation BR-PAY-010; posting-date KPIs (BR-REP-001); receipt if cleared | BR-PAY-021/036 |
| 5 | Invariance | — | issued docs unrestated; ledger append-only; tie-outs hold | HR-4/5, BR-LED-007 |
""")
    for i, j in itertools.combinations(range(6), 2):
        cover_map.append((keys[i], c[i], keys[j], c[j], fid))

with open("08-qa/01-e2e/journeys/T3P-00-coverage-matrix.md", "w") as fh:
    fh.write(f"""---
id: T3P-00
tier: 3
kind: coverage proof (generated)
---
# T3P pairwise coverage proof

Axes A(7) B(4) C(5) D(7) E(5) F(3) → **{total_pairs} cross-axis pairs**, covered by **{len(combos)} journeys** (greedy covering array, deterministic). Every pair's FIRST covering journey:

| Axis-pair | Value-pair | Journey |
|---|---|---|
""")
    seen = set()
    for k1, v1, k2, v2, fid in cover_map:
        if (k1, v1, k2, v2) not in seen:
            seen.add((k1, v1, k2, v2))
            fh.write(f"| {k1}×{k2} | {v1} × {v2} | {fid} |\n")
    assert len(seen) == total_pairs, f"coverage HOLE: {total_pairs - len(seen)} pairs missing"
print(f"pairs={total_pairs} journeys={len(combos)} — ALL PAIRS COVERED (assert passed)")

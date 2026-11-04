"""Independent re-pricing of J74 case 6 (Unit E, catch-up Jul–Sep) from the seed's rates.

Nothing imported from the application. Reads (seed + typed on step 2):
  W-10442E  Jun30 452.1 · Jul31 466.0 · Sep30 482.3 (typed)
  W-10443E  Jun30 110.4 · Sep30 130.6 (typed; no July or August read)
  E-55120E  Jun30 16700 · Jul31 17400 · Sep30 18420 (typed)
Segments: Jul 1–15 (v1, 15/31) · Jul 16–31 (v2, 16/31) · Aug (v2, 31/31) · Sep (v2, 30/30).
A read covering several segments is shared by calendar days (decision log 2026-09-30).
Water tiers: v1 $3.00 to 5 kgal, $4.25 above; v2 $3.25 / $4.50; the 5-kgal bound and the
bases scale by the segment's factor (B4.3 / BR-RAT-002). Electric $0.1245/kWh, no base.
Sewer 40% of THAT segment's water × $5.00 + $6.00 base × factor. Trash: $15.00 per cart
+ $3.00 base. The per-cart charge PRORATES by the factor like the base — PO ruling
2026-10-01 (DEF-BIL-8566), verbatim *"A · Cart shrinks too: $9.00"* — so July's halves
are 15/31 × $15.00 = $7.26 and 16/31 × $15.00 = $7.74. The superseded reading (whole
$15.00 in each half, $649.49) is still printed so the $15.30 difference is visible.
Tax: Local 2.00% on every usage and base line, once over the bill (B4.2). Half-up per line.
"""
from decimal import ROUND_HALF_UP, Decimal as D

C = D("0.01")
r = lambda x: x.quantize(C, ROUND_HALF_UP)  # noqa: E731


def share(total, days, of):
    return (D(total) * days / of).quantize(D("0.000001"), ROUND_HALF_UP)


segs = [("Jul1-15", 15, 31, "v1"), ("Jul16-31", 16, 31, "v2"), ("Aug", 31, 31, "v2"), ("Sep", 30, 30, "v2")]
w1 = [share("13.9", 15, 31), share("13.9", 16, 31), share("16.3", 31, 61), share("16.3", 30, 61)]
w2 = [share("20.2", 15, 92), share("20.2", 16, 92), share("20.2", 31, 92), share("20.2", 30, 92)]
el = [share("700", 15, 31), share("700", 16, 31), share("1020", 31, 61), share("1020", 30, 61)]
price = {"v1": (D("3.00"), D("4.25")), "v2": (D("3.25"), D("4.50"))}


def water(q, factor, v):
    bound = D(5) * factor
    lo, hi = price[v]
    t1 = min(q, bound)
    t2 = max(q - bound, D(0))
    return r(t1 * lo) + r(t2 * hi)


for label, trash_prorated in (("SUPERSEDED - per-cart charge whole in each segment", False),
                              ("RULED 2026-10-01 - per-cart charge prorated like the base (expected)", True)):
    lines = []
    for i, (name, days, of, v) in enumerate(segs):
        f = D(days) / D(of)
        lines += [water(w1[i], f, v), r(D(8) * f), water(w2[i], f, v), r(D(8) * f)]
        lines += [r(el[i] * D("0.1245"))]
        lines += [r((w1[i] + w2[i]) * D("0.4") * D(5)), r(D(6) * f)]
        lines += [r(D(15) * f) if trash_prorated else D("15.00"), r(D(3) * f)]
    sub = sum(lines)
    tax = r(sub * D("0.02"))
    print(f"{label}: charges {sub} + tax {tax} = {sub + tax}")

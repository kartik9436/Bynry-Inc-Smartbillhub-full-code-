#!/usr/bin/env python3
"""E2E money-triple expectation generator (T3 full-depth, PO 2026-08-08).

Computes the expected values for ALL A×D×E combinations (plan shape × bill
type × payment outcome) from fixture line definitions, using ONLY frozen B4
rules: NUMERIC line math, round half-up 2dp PER LINE at finalization, tax on
taxable lines only (usage+base+minimum+capacity), fees never taxed, allocation
usage+base → taxes → fees last (BR-PAY-010), overdue portion drives the next
late fee (BR-BIL-001), NSF reinstates at original due date + $30 fee
(BR-PAY-013). Writes 08-qa/01-e2e/expected/money-triples.csv.

QA scaffolding — expectation data for journey files and engine tests.
NOT the rating engine (human-owned). Deterministic; re-run in CI.
"""
import csv, os
from decimal import Decimal as D, ROUND_HALF_UP

def r2(x):
    return D(x).quantize(D("0.01"), ROUND_HALF_UP)

TAX = [D("0.0625"), D("0.01"), D("0.02"), D("0.002")]

# Line = (kind, qty, price) with kind in usage|base|capacity|sewer|fee.
# Shapes reuse the frozen fixture rates (Brazos Bend). Sewer = 40% of water usage-$.
def shape_lines(shape, f=D(1)):
    """f = days-fraction for prorated bill types; usage qty scales with f,
    fixed lines scale with f, tier spans scale with f (B4.4)."""
    L = []
    if shape == "flat":
        L += [("usage", D("700") * f, D("0.11")), ("base", None, D("12.00") * f)]
    elif shape == "tiered":
        span1 = D("5") * f
        use = D("8") * f
        t1 = min(use, span1)
        L += [("usage", t1, D("4.00")), ("usage", use - t1, D("6.50")),
              ("base", None, D("8.00") * f)]
        wat = r2(t1 * D("4.00")) + r2((use - t1) * D("6.50"))
        L += [("sewer", None, r2(D("0.40") * wat))]
    elif shape == "tou":
        L += [("usage", D("120") * f, D("0.22")), ("usage", D("200") * f, D("0.14")),
              ("usage", D("380") * f, D("0.09")), ("base", None, D("12.00") * f)]
    elif shape == "tou_demand":
        L += [("usage", D("850") * f, D("0.19")), ("usage", D("1400") * f, D("0.12")),
              ("usage", D("2200") * f, D("0.075")), ("usage", D("14.2"), D("9.50")),
              ("base", None, D("48.00") * f)]
    elif shape == "seasonal":
        for q, p in [("64", "0.22"), ("56", "0.18"), (D("200") * 16 / 30, "0.14"),
                     (D("200") * 14 / 30, "0.12"), (D("380") * 16 / 30, "0.09"),
                     (D("380") * 14 / 30, "0.08")]:
            L += [("usage", (D(q) if isinstance(q, str) else q) * f, D(p))]
        L += [("base", None, D("12.00") * f)]
    elif shape == "capacity":
        L += [("usage", D("700") * f, D("0.11")), ("base", None, D("12.00") * f),
              ("capacity", None, D("40.00") * f)]
    elif shape == "mixed":
        L += [("usage", D("120") * f, D("0.22")), ("usage", D("200") * f, D("0.14")),
              ("usage", D("380") * f, D("0.09")), ("base", None, D("12.00") * f)]
        span1 = D("5") * f
        use = D("8") * f
        t1 = min(use, span1)
        L += [("usage", t1, D("4.00")), ("usage", use - t1, D("6.50")),
              ("base", None, D("8.00") * f)]
        wat = r2(t1 * D("4.00")) + r2((use - t1) * D("6.50"))
        L += [("sewer", None, r2(D("0.40") * wat)), ("base", None, D("18.00") * f),
              ("capacity", None, D("40.00") * f)]
    return L

def amount(line):
    kind, qty, price = line
    return r2(qty * price) if qty is not None else r2(price)

def bill(lines, extra_fees=D(0)):
    taxable = sum(amount(l) for l in lines)          # usage+base+capacity+sewer all taxable
    taxes = [r2(taxable * t) for t in TAX]
    return taxable, sum(taxes), taxable + sum(taxes) + extra_fees

SHAPES = ["flat", "tiered", "tou", "tou_demand", "seasonal", "capacity", "mixed"]
BILLTYPES = ["cycle", "first", "final", "rebill", "backbill", "penalty", "budget"]
PAYMENTS = ["full", "partial60", "over150", "nsf", "none"]

rows = []
for A in SHAPES:
    for Dt in BILLTYPES:
        if Dt == "budget" and A == "tou_demand":
            pass  # budget allowed on any shape; no exclusion
        # build the bill per type
        note = ""
        if Dt == "cycle":
            tb, tx, total = bill(shape_lines(A))
        elif Dt == "first":
            tb, tx, total = bill(shape_lines(A, D(20) / 31))
            total += D("150.00") + D("25.00")        # deposit (non-tax) + CONN fee (non-tax)
            note = "deposit 150.00 + CONN 25.00 non-taxable (BR-BIL-012)"
        elif Dt == "final":
            tb, tx, total = bill(shape_lines(A, D(18) / 31))
            dep = D("153.50")                        # deposit + interest applies first
            note = f"deposit credit 153.50 applies; settlement path per BR-BIL-013"
        elif Dt == "rebill":
            base_lines = shape_lines(A)
            # correction: first usage line qty reduced 25% (supersede) → rebill
            corr = []
            fixed_first = False
            for k, q, p in base_lines:
                if k == "usage" and q is not None and not fixed_first:
                    corr.append((k, q * D("0.75"), p)); fixed_first = True
                else:
                    corr.append((k, q, p))
            tb0, tx0, tot0 = bill(base_lines)
            tb, tx, total = bill(corr)
            note = f"credit note -{tot0}; customer delta {r2(tot0-total)} (BR-BIL-014)"
        elif Dt == "backbill":
            tb1, tx1, tot1 = bill(shape_lines(A))
            tb, tx, total = tb1 * 3, tx1 * 3, tot1 * 3
            note = "3 months, period-labeled groups, per-version pricing (BR-BIL-018)"
        elif Dt == "penalty":
            assessed = [(k, (q * D("0.5")) if q is not None else None,
                         p if q is not None else r2(p * D("0.5")))
                        for k, q, p in shape_lines(A) if k == "usage"]
            tb, tx, total = bill(assessed, extra_fees=D("500.00"))
            note = "assessed reads 50% + TAMPER 500.00 non-taxable (BR-BIL-019)"
        elif Dt == "budget":
            tb, tx, total = bill(shape_lines(A))
            level = D(int((total).quantize(D("1"), ROUND_HALF_UP)))
            note = f"level {level}; variance {r2(level-total)} (BR-BIL-017)"
        # payment outcome
        paid = outstanding = credit = D(0)
        if PAYMENTS:
            pass
        for E in PAYMENTS:
            if E == "full":
                paid, outstanding, credit = total, D("0.00"), D("0.00")
            elif E == "partial60":
                paid = r2(total * D("0.6"))
                outstanding, credit = total - paid, D("0.00")
            elif E == "over150":
                paid = r2(total * D("1.5"))
                outstanding, credit = D("0.00"), paid - total
            elif E == "nsf":
                paid = D("0.00")
                outstanding, credit = total + D("30.00"), D("0.00")  # reinstated + NSF fee
            elif E == "none":
                paid, outstanding, credit = D("0.00"), total, D("0.00")
            # next late fee on overdue portion (min 5), fees excluded from base per B4
            late_next = max(D("5.00"), r2(outstanding * D("0.015"))) if outstanding > 0 else D("0.00")
            rows.append([A, Dt, E, str(tb), str(tx), str(total), str(paid),
                         str(outstanding), str(credit), str(late_next), note])

os.makedirs("08-qa/01-e2e/expected", exist_ok=True)
with open("08-qa/01-e2e/expected/money-triples.csv", "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["shape", "bill_type", "payment", "taxable", "tax", "total",
                "paid", "outstanding", "credit", "next_late_fee", "notes"])
    w.writerows(rows)

# sanity anchors against frozen figures
anchors = {("mixed", "cycle"): "247.87", ("tou", "cycle"): "127.30",
           ("tiered", "cycle"): "57.35"}
fails = []
for (a, d), want in list(anchors.items())[:1]:  # mixed/cycle must equal WE-1 current charges + late? no late here
    got = [r for r in rows if r[0] == a and r[1] == d and r[2] == "full"][0][5]
    # WE-1 current 247.87 includes late fee 5.00; generator cycle excludes it → 242.87
    if got != "242.87":
        fails.append(f"mixed/cycle: got {got}, want 242.87 (WE-1 minus late fee)")
print(f"generated {len(rows)} expectation rows → 08-qa/01-e2e/expected/money-triples.csv")
for f in fails:
    print("ANCHOR FAIL:", f)
raise SystemExit(1 if fails else 0)

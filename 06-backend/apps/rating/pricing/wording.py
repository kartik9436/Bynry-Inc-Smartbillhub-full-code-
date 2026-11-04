# ── Trace ──────────────────────────────────────────────
# Story:    DEF-968 (CR-043 finding 2 — six decimal places of money and
#           percentage, at a clerk)   Screens: BIL-02 Charges tab
# Rules:    CLAUDE.md hard rule 2 (money stored 4, percentages 6, BOTH DISPLAY
#           2 — PO re-sign 2026-08-22) · BR-RAT-087 (the display half, PO's own
#           words: *"display 2 decimal - amount and percetnage both"*) ·
#           BR-MET-144 (a QUANTITY displays at most two decimals, trailing
#           zeros trimmed — PO 2026-08-27, closing DEF-894) ·
#           CLAUDE.md hard rule 3 (a quantity carries its unit)
# Tests:    06-backend/tests/test_cr043_line_wording.py
# Impacts:  apps/rating/pricing/models/tiered.py ·
#           apps/rating/pricing/models/percent_of_service.py
# ───────────────────────────────────────────────────────
"""How a priced line WORDS itself — the numbers inside `description`.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this file sits inside the rating engine
(B4 / CLAUDE.md sensitive paths) and rounds figures for a person to read.
**Nothing here rounds MONEY and nothing round-trips**: it takes a tier
THRESHOLD and a tariff PERCENT and returns a string for a sentence. The
arithmetic on the line beside it is untouched, `03-golden-verify.py` reads
figures rather than sentences, and it was 33 PASS / 0 FAIL before and after with
byte-identical output. Enrolled because a rounding decision inside the pricing
engine is one a human signs, not one a lane takes quietly — see
`12-governance/09-human-review-ledger.md`.

WHY A LINE'S OWN SENTENCE IS A DISPLAY SURFACE
-----------------------------------------------
`invoice_lines.description` is written by the pricing engine and then rendered
verbatim on the bill, on the Charges tab and in any reprint. It is the only
place in this product where a figure reaches a person WITHOUT passing through a
formatter — `MoneyCell` never sees it, `quantity_display` never sees it, and
every gate in this repo is blind to it because it is a string.

So they printed at STORAGE precision, `NUMERIC(18,6)`, and the Product Owner
read them on the live deployment at v2.61.1:

    "water usage tier 1 (0-5.000000 kgal)"
    "sewer usage — 40.000000% of water usage charges"

TWO RULES, AND USING THE WRONG ONE IS INVISIBLE
------------------------------------------------
* A **percentage** displays at **two places, padded** — `40.00%`. Hard rule 2
  and BR-RAT-087. `40%` would be a third convention.
* A **quantity** displays at **at most two places, trailing zeros trimmed** —
  `5`, never `5.00`. BR-MET-144, and the difference is deliberate: a quantity's
  precision is what the meter measured, so `5.00 kgal` is noise, where `$8.00`
  is right because a currency's precision is a property of the currency.

Both produce a well-formed string, so reaching for the wrong one is invisible
to `tsc`, to `ruff` and to every test that only checks the sentence is present.
That is DEF-364's shape, and it is why the two live here side by side with the
difference written between them.

⚠ **WHY THIS DUPLICATES `apps/metering/quantity_display.py` INSTEAD OF CALLING
IT.** `apps/rating/pricing` is a PURE module: it takes a tariff config and a
quantity and returns priced lines, and it imports no other app. Importing
metering from inside a pricing plugin would bind the engine to another module's
release, in a money path, to borrow six lines of formatting. So the rule is
implemented here and the DRIFT is guarded instead —
`tests/test_cr043_line_wording.py` asserts this function and
`apps.metering.quantity_display.quantity_text` agree on the same inputs, so the
day one of them changes the other goes RED. A guard beats a coupling; an
unguarded copy beats neither.

⚠ **NOTHING HERE IS ROUNDING MONEY.** No amount passes through this module —
only a tier THRESHOLD (a quantity) and a tariff PERCENT (a rate). B4's
finalization is untouched, `10-scripts/03-golden-verify.py` reads figures and
not sentences, and it was run before and after this change at 33 PASS / 0 FAIL.

⚠ **AND IT DOES NOT REACH BILLS ALREADY ISSUED.** A description is frozen onto
the row at draft and an issued bill is append-only (hard rule 4), so the 47
bills the PO was looking at keep their six places forever. This governs every
bill drafted from 2026-08-27.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

TWO_PLACES = Decimal("0.01")
#: FOUR, and it is the Product Owner's figure rather than this file's.
#: PO 2026-08-27, closing OQ-620(a), verbatim: *"What does a tariff rate show?
#: Four ($0.1420). A rate is not money and not a quantity - 4 decimal places"*.
FOUR_PLACES = Decimal("0.0001")


def quantity_text(value: Any) -> str:
    """A quantity for a person: at most 2dp, half-up, trailing zeros trimmed.

    `Decimal("5.000000")` -> `"5"` · `Decimal("15.5")` -> `"15.5"` ·
    `Decimal("2.005")` -> `"2.01"` (half-up, B4's direction).

    An unparseable value returns `str(value)` rather than raising: this composes
    a SENTENCE, and a pricing run that died formatting its own label would fail
    a bill over a cosmetic. The engine's arithmetic never reads this back.
    """
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return str(value)
    trimmed = amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP).normalize()
    # `normalize()` turns 5 into 5E+0 and 100 into 1E+2 — correct Decimals and
    # unreadable numbers. `to_integral_value` restores the plain digits.
    if trimmed == trimmed.to_integral_value():
        trimmed = trimmed.quantize(Decimal(1))
    return f"{trimmed:f}"


def percent_text(value: Any) -> str:
    """A percentage already in PERCENTAGE POINTS, at two padded places: `40.00`.

    ⚠ **POINTS, NOT A FRACTION.** `tariff_versions.percent` stores what the
    tenant typed — `40` for BR-RAT-015's *"40% of water usage-charge dollars"* —
    so nothing here multiplies by a hundred. `apps/rating/selectors` carries the
    same pair of conventions and the same warning: handing a fraction to this
    function serves `0.02%` for a two-percent rate, and handing points to a
    fraction formatter serves `4000.00%`. Both are well-formed strings.

    The `%` sign is NOT appended here — the caller's sentence owns it, and
    DEF-365 is the record that the symbol and the separator are en-US in this
    product and that IS-8's per-tenant number format does not reach this layer.
    """
    try:
        points = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return str(value)
    return str(points.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def rate_text(value: Any) -> str:
    """A unit PRICE for a person: up to 4dp, at least 2, half-up at the fourth.

    `Decimal("0.042500")` -> `"0.0425"` · `Decimal("0.142000")` -> `"0.142"` ·
    `Decimal("8.290000")` -> `"8.29"` · `Decimal("12.5")` -> `"12.50"` ·
    `Decimal("0.14205")` -> `"0.1421"` (half-up, B4's direction).

    ⚠ **AMENDED 2026-10-02 — PO, verbatim: *"Show unit prices with up to 4
    decimals and keep every total at 2."*** The zeros after the SECOND place
    are now dropped (`8.2900` -> `8.29`); the four places a price carries are
    kept (`0.0425` never reads `0.04`) and it never reads with fewer than two
    (`12.5` -> `12.50`). Shown to the PO: `$0.0425` per gallon read as `$0.04`
    turns 10,000 gallons into `$400.00` against the `$425.00` billed. Display
    only — the line's `amount`, `quantity` and `unit_price` are untouched, no
    figure moves, and the paragraphs below about OQ-620(a) are this function's
    history: they still govern the CEILING (four), no longer the zeros.

    ⚠ **THE ZEROS ARE KEPT, AND THAT IS THE EXACT OPPOSITE OF `quantity_text`
    TWENTY LINES UP.** `8.290000` becomes `8.2900` and *never* `8.29`. Reaching
    for the wrong one of these two functions produces a well-formed string
    either way, which is why they are neighbours in one file with this warning
    between them rather than in two places somebody could pick from.

    **WHY A RATE IS A THIRD KIND** — the Product Owner said it in their own
    words on 2026-08-27 (OQ-620(a)): *"A rate is not money and not a quantity -
    4 decimal places"*. A QUANTITY's precision is what the meter measured, so
    `8.00 kgal` is noise; MONEY's is what the currency is denominated in, so
    `$8.00` is right; a RATE's is **the precision it was priced at**, and
    dropping it prints a figure that cannot reproduce the line it made.
    `apps/billing/documents.py` had already written that down before there was
    a rule — *"quantizing $0.142000 to $0.14 would print a rate that does not
    reproduce the line it priced"* — and `05-prototype/r10`'s residential bill
    draws `$0.1420`.

    ⚠ **THIS DOES NOT ROUND MONEY AND MUST NEVER BE REACHED FOR ONE.** Money
    has CLAUDE.md hard rule 2, its own 2dp and its own composer. Storage is
    untouched by all of this: `NUMERIC(18,6)` is what is stored and what the
    engine computes with (BR-RAT-003), and nothing round-trips through here.

    An unparseable value returns `str(value)`, for `quantity_text`'s reason.
    """
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value))
    except (ArithmeticError, InvalidOperation, TypeError, ValueError):
        return str(value)
    # Quantize to the ceiling (four, half-up), then drop zeros back to the
    # floor (two). String surgery on the fixed-point text, never `normalize()`,
    # which would turn `100` into `1E+2`.
    text = f"{amount.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP):f}"
    whole, _, places = text.partition(".")
    places = places.rstrip("0")
    return f"{whole}.{places.ljust(2, '0')}"


def quantity_with_unit(value: Any, unit: Any) -> str | None:
    """The rendered pair — `"5 kgal"` — or `None` when either half is missing.

    ⚠ **THE UNIT IS NOT OPTIONAL AND THAT IS CLAUDE.md HARD RULE 3**, exactly as
    `apps/metering/quantity_display.quantity_with_unit` states it. A bare number
    in a column headed *From* is read as the tenant's own unit by whoever is
    looking at it.

    ⚠ **THIS IS THE SECOND IMPLEMENTATION OF ONE RULE AND THAT IS DELIBERATE,
    NOT AN OVERSIGHT.** `apps/rating/pricing` is a PURE module and may not
    import metering (B2 §2), so BR-MET-144 has to exist on both sides of that
    boundary. What keeps them honest is not discipline but
    `tests/test_cr043_line_wording.py`, which asserts the two agree value for
    value — and BR-SHL-250 §4 is the record of what happens without such a
    test: the same rule was implemented four times on this tree and **two of
    the four implemented only half of it**, so one consumption read
    `26.24 kgal` on one screen and `26.2437 kgal` on another for three days.
    """
    if value is None:
        return None
    if unit is None or str(unit).strip() == "":
        return None
    return f"{quantity_text(value)} {unit}"

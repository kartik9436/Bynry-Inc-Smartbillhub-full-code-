# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — the JOINING READ behind R46 Bill
#           Projection. Drawing read as an IMAGE (B14 rule 42): p062 of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 3.0x.
# Story:    R46 `bill_projection` — Customers › Enrolment · meter reads +
#           rating · **Projection date**.
# Rules:    `BR-REP-042` (PO ruling 2026-09-27, verbatim: *"Set a percentage —
#           say ±15% — applied to the usage part only, never to fixed
#           charges"*) · `OQ-REP-12769` (the *Winter average* basis — UNRULED,
#           stubbed, never chosen) · `BR-REP-024` (NULL with a reason, never a
#           0) · `BR-REP-001` (basis) · CLAUDE.md hard rule 2 (money stored 4
#           decimals, percentages 6, both DISPLAY 2) · hard rule 3 (consumption
#           always with an explicit unit) · hard rule 4 (this file writes
#           nothing) · B14 rule 33 (no rationale on screen).
# Tests:    06-backend/tests/test_rep_p6w4_bill_projection.py
# ───────────────────────────────────────────────────────
"""**R46 BILL PROJECTION — one row is one projected CHARGE COMPONENT.**

p062's own footnote is the specification:

    *"Usage is straight-lined and base charges are not, and each row says which
    it is. The projection is a prediction shown to a customer, so the definition
    seeded by P0.6 carries the ± range beside the figure: a single number reads
    as a promise and generates a complaint when the real bill differs."*

═══════════════════════════════════════════════════════════════════════════════
THE ± RANGE IS 15% OF THE **USAGE PART ONLY** — `BR-REP-042`
═══════════════════════════════════════════════════════════════════════════════
PO ruling 2026-09-27, verbatim:

    *"Set a percentage — say ±15% — applied to the usage part only, never to
    fixed charges"*

⚠ **THE `±$12` DRAWN ON p062 IS AN ILLUSTRATION AND IS NOT THE FIGURE** (B14
rule 37 — a number drawn in a wireframe is never a fact to build to). On p062's
own components the ruled band is a different number, and the arithmetic is worth
writing out because two plausible wrong answers sit either side of it:

    base      18.00 (water) + 22.00 (sewer) =  40.00   ← NO range over this
    usage     59.64 (water) + 88.46 (sewer) = 148.10   ← the range is over THIS
    total                                     188.10

    ruled      0.15 × 148.10 = 22.215        → ± $22.22
    WRONG (a)  0.15 × 188.10 = 28.215        → ± $28.22   (15% of the TOTAL)
    WRONG (b)  the drawn figure                ± $12.00   (an illustration)

`BR-REP-042`'s own signed worked example is the simpler one and is asserted
beside it: **`$84.00` made of `$24.00` base and `$60.00` usage carries
± `$9.00`, not ± `$12.60`.**

⚠ **THE REASON IS NOT TIDINESS — IT IS THAT THE FIXED CHARGE IS KNOWN EXACTLY.**
A range over the base *"invents doubt the product does not have"* (the rule's own
words). A customer told their $24.00 standing charge might be $27.60 has been
told something false by a product that knows better.

⚠ **AND THE RANGE IS COMPUTED OVER THE COMPONENTS THAT ACTUALLY PROJECTED.** A
usage component whose basis this product cannot compute (`OQ-REP-12769`) is NOT
in the band, because including a quantity nobody derived would make the band
either wider or narrower than the doubt the product really has.

═══════════════════════════════════════════════════════════════════════════════
`Winter average` IS NOT RULED AND IS STUBBED — `OQ-REP-12769`
═══════════════════════════════════════════════════════════════════════════════
p062's sewer row draws a `Winter average` basis. Nothing in this product defines
it, and it is not a rounding convention: it changes the QUANTITY a customer is
shown and therefore the money. It is a real North-American practice — sewer has
no meter of its own and is priced on water, so summer irrigation would bill for
water that never entered the sewer — and precisely because it is real, four
things about it are a TARIFF decision and not a lane's: which months, which
statistic, what happens in a customer's first year, and whether it CAPS or
SUBSTITUTES. `winter_average_quantity` raises with that question's id, at the
boundary, exactly as the prime directive requires.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT DO
═══════════════════════════════════════════════════════════════════════════════
* **It writes nothing** (hard rule 4) and **it prices nothing new**: the rates
  are the plan's own, read through the seam that already publishes them.
* **It puts no rationale on a screen** (B14 rule 33). The read serves the figure
  and its range; it composes no sentence about straight-lining.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

#: `BR-REP-042` — the ruled band, as a FRACTION, stored at hard rule 2's six
#: places. Named once so the read, the tile and the test cannot disagree.
PROJECTION_BAND = Decimal("0.150000")

#: `BR-REP-001` — p062's eyebrow reads *Projection date*.
BASIS_PROJECTION = "projection"

#: p062's BASIS column vocabulary. The SCREEN renders each into its own language
#: (B14 rule 35); nothing here composes English.
BASIS_MONTHLY = "monthly"
BASIS_STRAIGHT_LINED = "projected_from_days_elapsed"
BASIS_WINTER_AVERAGE = "winter_average"

#: ⚠ **WHICH BASES ARE USAGE-DRIVEN, DECLARED AS DATA AND NOT AS AN `if`.**
#: `BR-REP-042` turns entirely on this split, and a hand-written condition in the
#: band arithmetic is a second spelling of it — which is how a base charge ends
#: up inside a range that was ruled never to cover one.
USAGE_DRIVEN_BASES: frozenset[str] = frozenset({BASIS_STRAIGHT_LINED, BASIS_WINTER_AVERAGE})

#: `BR-REP-024` — the reason a component's figures are ABSENT rather than zero.
GAP_WINTER_AVERAGE_UNRULED = {
    "code": "winter_average_basis_is_not_ruled",
    "oq_ref": "OQ-REP-12769",
    "br_ref": "BR-REP-042 · BR-REP-024 · p062",
    "detail": (
        "p062 draws a `Winter average` basis on the sewer usage row. Nothing in this "
        "product defines which months the winter is, which statistic is taken, what "
        "happens in a customer's first year, or whether it CAPS the quantity or "
        "SUBSTITUTES for it — and each of those four moves the money. It is this "
        "utility's own tariff practice, so it is OQ-REP-12769 and is the Product "
        "Owner's to rule. The component is served with its quantity and amount NULL "
        "and this reason beside them, and it is EXCLUDED from the ± range: a band "
        "widened by a quantity nobody derived is not the doubt the product has."
    ),
}


def winter_average_quantity(*args: Any, **kwargs: Any) -> Decimal:
    """The *Winter average* basis — **NOT RULED**.

    ⚠ **THE PRIME DIRECTIVE'S STUB, AT THE BOUNDARY.** Choosing any of the four
    undecided things would mint a tariff rule in a helper function and put a
    number a regulator has not seen in front of a customer. `OQ-REP-12769` holds
    the question with its worked `$7.30` difference on p062's own row.
    """
    raise NotImplementedError("OQ-REP-12769")


@dataclass(frozen=True)
class ProjectionComponent:
    """One projected charge component, in p062's own column order.

    ⚠ **`unit` IS A FIELD AND IS NEVER NULL ON A QUANTITY ROW** — hard rule 3.
    p062 draws UNIT as its own column *"and the reason there is no Total usage
    tile on a multi-service account"*; a quantity without its unit is not a
    number this product will serve.

    ⚠ **`is_usage` IS SERVED RATHER THAN INFERRED FROM THE BASIS STRING BY THE
    CLIENT.** `BR-REP-042` turns on this one boolean, and a screen re-deriving it
    from the basis word would be a second spelling of the ruling — the day a
    fifth basis is added, the band and the table would disagree about which
    charges it covers, and neither would look wrong.
    """

    component: str
    service: str
    basis: str
    quantity: Decimal | None
    unit: str | None
    rate: Decimal | None
    projected: Decimal | None
    is_usage: bool
    absence: str | None


def _money(value: Any) -> Decimal | None:
    """Hard rule 2 — money is STORED to four decimals. Display is the screen's."""
    if value is None:
        return None
    return Decimal(value).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def straight_line(usage_so_far: Any, days_elapsed: int, days_in_period: int) -> Decimal | None:
    """p062's *Projected from 14 days* — the whole of the straight-lining.

    **Worked, on the drawing's own figures:** 1,960 gal over 14 of 30 days
    projects to `1960 ÷ 14 × 30` = **4,200 gal**, which is what p062 draws.

    Returns None rather than 0 on a period with no days elapsed: nothing has been
    consumed *yet* is not the same fact as nothing will be, and `BR-REP-024`
    forbids the plausible number.
    """
    if usage_so_far is None or not days_elapsed or days_elapsed <= 0:
        return None
    if not days_in_period or days_in_period <= 0:
        return None
    per_day = Decimal(usage_so_far) / Decimal(days_elapsed)
    return (per_day * Decimal(days_in_period)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )


def band_for(components: list[ProjectionComponent]) -> Decimal | None:
    """`BR-REP-042` — ± **15% of the USAGE part only**, never of the total.

    ⚠ **THIS FUNCTION IS THE RULING AND THERE IS NO SECOND COPY OF IT.** The
    screen renders what it returns; nothing recomputes a percentage of a total
    anywhere.

    **Worked, on p062's own components:** usage `59.64 + 88.46 = 148.10`, so the
    band is `0.15 × 148.10` = **`$22.22`** — not `$28.22` (15% of the `$188.10`
    total, which would put a range over the two known base charges) and not the
    drawn `$12`, which is an illustration (B14 rule 37).

    **And on `BR-REP-042`'s own signed example:** `$84.00` of `$24.00` base and
    `$60.00` usage carries **`$9.00`**, not `$12.60`.

    Returns None where NOTHING projected, because a `$0.00` range is a promise of
    exactness this product has not made.
    """
    usage = [
        component.projected
        for component in components
        if component.is_usage and component.projected is not None
    ]
    if not usage:
        return None
    total = sum(usage, Decimal("0"))
    return _money(total * PROJECTION_BAND)


def component(
    *,
    name: str,
    service: str,
    basis: str,
    rate: Any,
    quantity: Any = None,
    unit: str | None = None,
) -> ProjectionComponent:
    """One component, with its money derived once and its absence named.

    ⚠ **A `winter_average` COMPONENT IS BUILT AND SERVED, NOT DROPPED.** p062
    draws that row, and deleting it would make the projection's own table
    disagree with the drawing while the total quietly stopped mentioning sewer at
    all — an absence with no reason beside it, which is the thing this repository
    is least able to see.
    """
    is_usage = basis in USAGE_DRIVEN_BASES
    if basis == BASIS_WINTER_AVERAGE:
        return ProjectionComponent(
            component=name,
            service=service,
            basis=basis,
            quantity=None,
            unit=unit,
            rate=_money(rate),
            projected=None,
            is_usage=is_usage,
            absence=GAP_WINTER_AVERAGE_UNRULED["code"],
        )
    amount = None
    if quantity is not None and rate is not None:
        amount = _money(Decimal(quantity) * Decimal(rate))
    return ProjectionComponent(
        component=name,
        service=service,
        basis=basis,
        quantity=None if quantity is None else Decimal(quantity),
        unit=unit,
        rate=_money(rate),
        projected=amount,
        is_usage=is_usage,
        absence=None,
    )


def projected_total(components: list[ProjectionComponent]) -> Decimal | None:
    """p062's `Projected total`. None where nothing at all could be projected."""
    amounts = [c.projected for c in components if c.projected is not None]
    if not amounts:
        return None
    return _money(sum(amounts, Decimal("0")))


def projection(
    *,
    components: list[ProjectionComponent],
    through: date | None = None,
    days_elapsed: int | None = None,
    days_in_period: int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    """R46's wire shape — the four tiles, the component rows and the ± range.

    ⚠ **THE `PROJECTED BILL` TILE AND THE `Projected total` FOOT TO THE SAME
    NUMBER**, because there is one derivation and the tile reads it. p062 draws
    `$188.00` above a total of `188.10`, which is the drawing rounding for a
    tile — an illustration (B14 rule 37) and not two figures.
    """
    total = projected_total(components)
    band = band_for(components)
    problems: list[dict[str, Any]] = []
    if any(c.absence == GAP_WINTER_AVERAGE_UNRULED["code"] for c in components):
        problems.append(dict(GAP_WINTER_AVERAGE_UNRULED))
    return {
        "basis": BASIS_PROJECTION,
        "window": {"start": None, "end": through},
        "currency": currency,
        "grain": "one projected charge component",
        "rows": tuple(components),
        "totals": {
            "projected_bill": total,
            # ⚠ **SERVED AS ITS OWN FIGURE AND NEVER AS A PERCENTAGE OF THE
            # TILE.** A screen handed `188.10` and `15%` would render `±$28.22`
            # — the wrong answer `BR-REP-042` exists to forbid.
            "projected_band": band,
            "days_elapsed": days_elapsed,
            "days_in_period": days_in_period,
            "usage_so_far": None,
        },
        "additivity": {
            "projected_bill": "full",
            # A band is derived from the usage part and is not a column sum.
            "projected_band": "non",
            "days_elapsed": "non",
            "days_in_period": "non",
        },
        "problems": tuple(problems),
        "total": len(components),
        "page": 1,
        "per": None,
        "pages": 1,
    }

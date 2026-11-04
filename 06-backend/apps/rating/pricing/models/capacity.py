# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-06 (capacity charges — solar / battery) · EP-RAT-05 (the
#           plugin interface it registers through)
#           Screens: — (the line renders in S31.2 and S21; the unit label and
#           rate are configured on S11 step 2's Capacity card)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-018/019 (v1 bills solar & battery as CAPACITY charges — rate
#           per tenant-defined capacity unit x account capacity; NOT
#           net-metering kWh credits, which are v1.1) · BR-RAT-022 (unit label
#           and rate are tenant-defined; prorated calendar-days on a mid-cycle
#           start) · BR-RAT-029 (taxable LIKE BASE) · BR-RAT-004 (proration is
#           by calendar days, B4.3) · BR-RAT-003 (a plugin never rounds) ·
#           BR-RAT-038 (UoM gate) · BR-RAT-044 (one price(...) interface)
# Golden:   GT-15 (solar 4 x $10.00 = $40.00; battery 2 x $12.00 = $24.00) ·
#           GT-17 (= WE-1: the same $40.00 solar line, inside the frozen
#           taxable base of 221.90, machine-verified) · GT-31 (= WE-16:
#           10/31 x $40.00 = $12.90) — B5 ❄️ FROZEN / GT-15 PROPOSED
# Tests:    06-backend/tests/test_us_rat_014_capacity.py
# Impacts:  apps/rating/pricing/stages/price_usage.py (resolves this by name)
# ───────────────────────────────────────────────────────
"""`capacity` pricing model: units in effect x the tenant's rate per unit.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-014 TC-1/TC-2 and US-RAT-015 TC-2.

THE FROZEN FIGURES THIS REPRODUCES
----------------------------------
    GT-15 / GT-17   solar   4 "panel"   x $10.00 = $40.00   (the 4150 posting
                    battery 2 "kW block" x $12.00 = $24.00    on the WE-1 bill)
    GT-31 / WE-16   solar activated on the 22nd of a 31-day July:
                    10/31 x $40.00 = $12.90

WHY THIS IS NOT `flat` WITH A DIFFERENT NAME
--------------------------------------------
Three differences, each a rule:

1. **It prorates and `flat` must not** (BR-RAT-022 / B4.3, GT-31). A per-unit
   price on a METERED quantity is already proportional to the days that produced
   the quantity, so prorating it would charge a short period twice as short —
   `flat.py` says exactly that. A capacity charge measures nothing: 4 panels is
   4 panels whether the month is 28 days or 31, so the DAYS are the only thing
   that can make a part-month cost less.
2. **It is taxable like BASE, not like usage** (BR-RAT-029). The line's kind is
   `base`, which is what puts it in B4.2's tax base by KIND rather than by a
   flag — the same structural guarantee `finalize.py` relies on.
3. **Its unit is the tenant's own word** (BR-RAT-022) — "panel", "kW block",
   "meter equivalent" — and it is the BILLED UNIT, so the BR-RAT-038 UoM gate
   works on it exactly as it does on kWh: 4 arriving in "panel" against a tariff
   written in "kW block" is refused, not multiplied by $12.00.

WHAT ARRIVES AS THE "QUANTITY"
------------------------------
The account's capacity units in effect (`account_capacities.units`, B2 r5 #5 /
BR-CUS-012), carried on the seam as a `Quantity` with the tenant's unit label —
so hard rule 3 holds without a special case. That table is CUSTOMERS-owned and
is **not built** (`apps/customers/services.py` records it: *"`account_capacities`
has no DDL in any signed document"*), so today the units reach the engine only
when a caller states them. A capacity service with no units is US-RAT-014 TC-6:
*"No capacity line invented; the account surfaces in S31.3 exceptions as
'capacity not set'"* — a refusal by name, which is what the caller's seam does.

WHAT IS DELIBERATELY ABSENT
---------------------------
* **Net-metering kWh credits.** OQ-001 CLOSED to v1.1 (BR-RAT-018). This plugin
  reads no import/export quantity and emits no credit line — US-RAT-014 TC-5
  asserts exactly that.
* **Mid-period capacity CHANGES** (US-RAT-014 TC-3: 2 -> 3 blocks on day 11 =
  10/30 x 24.00 + 20/30 x 36.00). Each segment is one call of this plugin with
  its own units and its own period shape; splitting a period into segments is
  the caller's, the same way a tariff-change split is (BR-RAT-004 as extended
  2026-08-12). Nothing here invents a second segment.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating import proration
from core.units import same_unit
from apps.rating.pricing import errors, wording
from apps.rating.pricing.contracts import (
    KIND_BASE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    PeriodShape,
    SubscriptionContext,
)

MODEL = "capacity"

ZERO = Decimal(0)


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
    period: PeriodShape | None = None,
) -> tuple[LineCandidate, ...]:
    """One capacity line, calendar-day prorated. UNROUNDED (BR-RAT-003).

    `period` is optional only so the plugin can be exercised from a fixture with
    no period; the stage always passes one, and its absence means a factor of 1
    (no proration), never a guess — the same contract `tiered.py` states.
    """
    service = subscription.service
    if config.capacity is None:
        raise errors.TariffConfigError(
            f"capacity tariff for service {service!r} states no unit label and no rate "
            "(BR-RAT-022 — both are tenant-defined). A capacity schedule that cannot "
            "price a unit is a refusal, never a zero line."
        )
    unit_label = config.capacity.unit_label
    rate = config.capacity.rate_per_unit
    if not same_unit(usage.unit, unit_label):  # DEF-RAT-10220 — `_gate_uom`'s rule
        raise errors.UomMismatch(
            f"service {service!r}: capacity arrived in {usage.unit!r} and the tariff prices "
            f"{unit_label!r} at {rate}. BR-RAT-038: a unit mismatch blocks rating for that "
            "input — 4 panels are not 4 kW blocks and the engine holds no factor between "
            "one tenant's word and another's."
        )
    units = usage.billed_quantity
    if units < ZERO:
        # r5 #5 puts `units >= 0` on the capture side; asserted here too because
        # a negative capacity would produce a CREDIT on a bill (US-RAT-014 TC-7).
        raise errors.RatingInputError(
            f"service {service!r}: capacity units are {units}. `account_capacities.units` "
            "is >= 0 (B2 r5 #5) and a negative capacity would put a credit on a customer's "
            "bill by arithmetic rather than by decision."
        )

    factor = Decimal(1) if period is None else period.factor
    label = " (prorated)" if period is not None and period.is_partial else ""
    return (
        LineCandidate(
            kind=KIND_BASE,  # BR-RAT-029: taxable LIKE BASE, structurally (B4.2)
            # ⚠ DEF-968's DEFECT, IN THE MODEL CR-043 COULD NOT SEE. Both
            # figures USED TO INTERPOLATE RAW, so a customer billing four
            # panels from a `NUMERIC(18,6)` column read *"4 panel @
            # 10.000000"*. CR-043 fixed `tiered.py` and `percent_of_service.py`
            # — the two the Product Owner had read on the live deployment — and
            # `wording.py`'s Impacts header still names only those two.
            # Capacity was missed because it had never reached a bill: nothing
            # drove it past the engine until `tests/test_capacity_end_to_end.py`,
            # and the engine test asserting `"4 panel @ 10.00"` passes because
            # ITS OWN fixture types `Decimal("10.00")` and never a stored one.
            #
            # TWO DIFFERENT RULES ON ONE LINE, and reaching for the wrong one is
            # invisible because both produce a well-formed string:
            #   · the RATE is `rate_text` — up to 4dp, at least 2 (PO
            #     2026-10-02, *"Show unit prices with up to 4 decimals and
            #     keep every total at 2"*, narrowing OQ-620(a)), so `10.00`;
            #   · the UNITS are a QUANTITY — `quantity_text`, at most 2dp with
            #     trailing zeros TRIMMED (BR-MET-144), so `4` and never `4.00`.
            # **Only the SENTENCE changes.** `amount`, `quantity` and
            # `unit_price` below are untouched Decimals, the engine never reads
            # this string back, and no B4/B5 figure moves.
            description=(
                f"{service} capacity — {wording.quantity_text(units)} {unit_label} "
                f"@ {wording.rate_text(rate)}{label}"
            ),
            amount=proration.prorated_amount(units * rate, factor),
            taxable=True,
            quantity=units,
            unit=unit_label,
            # 🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10067` (PO 2026-10-12,
            # *"quantity × rate = amount on every row"*): on a part month the
            # printed rate is the rate for THESE days, so `1 ERU × $2.85` reads
            # `$2.85`. A whole month is a factor of 1 and prints `rate` as before.
            unit_price=proration.prorated_rate(rate, factor),
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-014@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-06 US-RAT-014)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half; the CONFIG half is S11's Capacity card, already built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_014_capacity.py✔ · pytest -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: (1) GT-15 is PROPOSED in B5, not frozen — but its $40.00 solar line is ALSO inside GT-17's frozen, machine-verified taxable base of 221.90, and its proration (10/31 x 40.00 = 12.90) is check #21 of the frozen harness as WE-16/GT-31. So every figure this plugin reproduces is machine-checked somewhere, and the PROPOSED status is stated rather than relied on. (2) B5 GT-15's own text leaves ONE cent open — "whether the two [prorated capacity lines] round per line (12.90 + 7.74 = 20.64) or once (20.65)". This plugin emits ONE line per capacity SERVICE and never two in one call, so the fork cannot arise inside it; `stages/finalize.py` rounds per line, which is BR-RAT-003 and gives 20.64 across two services. REPORTED as OQ-235 rather than treated as settled. (3) `account_capacities` has no DDL (customers-owned, BR-CUS-029) so the units arrive only from a caller that states them; the missing-units path is the caller's named refusal (US-RAT-014 TC-6), never an invented line.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — usage pricing) · EP-RAT-02
#           (US-RAT-007 configures the energy and demand rates)
#           Screens: — (the two lines render in S31.2 and on the bill; the
#           rates are configured on S11 step 2's Demand card)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-014 (demand billing is v1 SCOPE; measurement = max-demand
#           REGISTER READ; ratchet OFF by default and the measurement/ratchet
#           rules remain PROPOSED — "the engine treats demand quantity as an
#           input") · BR-RAT-003 (a plugin never rounds) · BR-RAT-038 (UoM
#           gate) · BR-RAT-044 (one price(...) interface)
# Golden:   GT-20 (= WE-4, Small Commercial: demand 14.2 kW x $9.50 = $134.90) ·
#           GT-21 (= WE-5, Industrial: 48,200 kWh x $0.085 = $4,097.00 and
#           182 kW x $11.00 = $2,002.00) — B5 GT-17..61 are the billing-math
#           contract, ❄️ signed 2026-08-08
# Tests:    06-backend/tests/test_us_rat_012_demand.py
# Impacts:  apps/rating/pricing/stages/price_usage.py (resolves this by name)
# ───────────────────────────────────────────────────────
"""`demand` pricing model: energy on the volume, PLUS a charge on the peak.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-007 §7 and US-RAT-015 §4's `demand` registry row. This is the
charge a commercial or industrial customer pays for the SIZE of their draw
rather than the amount of it — the utility has to build for the peak whether or
not it is used again.

THE FROZEN FIGURES THIS REPRODUCES
----------------------------------
    GT-20 (WE-4)  Small Commercial: peak 14.2 kW x $9.50/kW  =   $134.90
    GT-21 (WE-5)  Industrial:  48,200 kWh x $0.085/kWh       = $4,097.00
                                  182 kW x $11.00/kW         = $2,002.00

TWO UNITS ON ONE BILL, AND THAT IS THE POINT
--------------------------------------------
The energy line is in **kWh** and the demand line is in **kW**. They are not the
same measurement, they are not convertible, and they are not addable — which is
why `MeasuredUsage.demand` is its own typed field (`PeakDemand`) rather than a
second number beside the energy. On WE-5 the two quantities are 48,200 and 182;
a contract that let them be swapped would produce $4,100 of demand and $15.47 of
energy, and the bill would still add up.

WHAT THIS PLUGIN DOES NOT COMPUTE, AND WHY REFUSING IS THE RULE
---------------------------------------------------------------
BR-RAT-014 is CONFIRMED for SCOPE and its measurement half is still PROPOSED
(B4 addendum, OQ-006 family). EP-RAT-05's scope line says it exactly: the engine
*"consumes demand qty, computes no ratchet/PF"*. So:

* **The peak is an INPUT.** Nothing here reads an interval series or computes a
  rolling 15-minute maximum. Metering supplies the max-demand register read
  (`channel = "demand"`, B2 r8 / BR-MET-059). An absent read REFUSES by name —
  a month with no demand read is not a month with no peak, and on WE-5 the
  difference is $2,002.00.
* **A RATCHET is refused, not ignored.** `demand_rate_config.ratchet_enabled`
  exists and defaults false (B2 r6.2). A tenant who switches it on believes the
  bill will carry 80% of the trailing 11-month peak as a floor; this engine
  cannot compute that and would silently bill the raw peak instead — lower than
  the tariff says, on every bill, invisibly. So it refuses. Same for the
  power-factor penalty, which US-RAT-007 TC-8 already words as *"engine will not
  compute PF penalties until the demand rules ratify; no silent math"*.
* **It does not prorate.** Both components price a measured quantity, and B4.3
  prorates fixed charges, not measured ones (`flat.py` states the reasoning).
"""

from __future__ import annotations

from apps.rating.pricing import errors, wording
from core.units import same_unit
from apps.rating.pricing.contracts import (
    KIND_USAGE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    SubscriptionContext,
)

MODEL = "demand"


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
) -> tuple[LineCandidate, ...]:
    """Two usage lines — energy then demand. UNROUNDED (BR-RAT-003)."""
    service = subscription.service
    if config.energy_rate is None or config.demand_rate is None:
        raise errors.TariffConfigError(
            f"demand tariff for service {service!r} needs BOTH an energy rate per "
            f"{config.billed_unit} and a demand rate per kW (BR-RAT-014); it states "
            f"energy={config.energy_rate} demand={config.demand_rate}. Half a demand "
            "tariff prices half a bill, so it is refused."
        )
    if config.ratchet_enabled or config.pf_penalty_enabled:
        # Fail CLOSED (hard-won law 3). Both are captured on the S11 Demand card
        # and BOTH of their rule families are still PROPOSED in the B4 addendum.
        # Pricing without them bills LESS than the tariff the tenant configured,
        # on every bill, with nothing on the document to show it.
        raise errors.TariffConfigError(
            f"service {service!r}: this demand tariff enables "
            f"{'a ratchet' if config.ratchet_enabled else ''}"
            f"{' and ' if config.ratchet_enabled and config.pf_penalty_enabled else ''}"
            f"{'a power-factor penalty' if config.pf_penalty_enabled else ''}, and the "
            "measurement rules for both are still PROPOSED (BR-RAT-014, B4 addendum "
            "OQ-006 family; US-RAT-007 TC-8 — 'no silent math'). The engine computes "
            "neither. Billing the raw peak instead would undercharge every bill this "
            "tariff prices and nothing on the document would say so."
        )
    if not same_unit(usage.unit, config.billed_unit):  # DEF-RAT-10220 — `_gate_uom`'s rule
        raise errors.UomMismatch(
            f"service {service!r}: energy was measured in {usage.unit!r} and the tariff "
            f"bills in {config.billed_unit!r}. BR-RAT-038: convert at rating input with a "
            "defined per-service factor, or block the read — never convert silently."
        )
    if usage.demand is None:
        raise errors.MissingDemandQuantity(
            f"service {service!r} bills a demand charge at {config.demand_rate} per kW and "
            "no peak-demand read arrived. BR-RAT-014's measurement is a MAX-DEMAND "
            "REGISTER READ; an absent register is unread, not a month without a peak. "
            "The account is an exception for a human (BR-BIL-015), not a bill missing "
            "its largest line."
        )

    return (
        LineCandidate(
            kind=KIND_USAGE,
            description=f"{service} energy",
            amount=usage.billed_quantity * config.energy_rate,
            taxable=True,  # B4.2: usage is in the tax base
            quantity=usage.billed_quantity,
            unit=usage.unit,
            unit_price=config.energy_rate,
        ),
        LineCandidate(
            kind=KIND_USAGE,
            # ⚠ DEF-968 AGAIN, AND HERE IT IS A QUANTITY RATHER THAN A RATE.
            # The peak USED TO INTERPOLATE RAW, so a `NUMERIC(18,6)` register
            # read reaches the customer as *"peak 182.000000 kW"*. CR-043 fixed
            # `tiered.py` and `percent_of_service.py` and missed this model and
            # `capacity.py` for the same reason: neither had ever reached a
            # bill, so the Product Owner could not read the defect off the live
            # deployment the way they read the other two.
            # `wording.quantity_text` is BR-MET-144 — at most 2dp, trailing
            # zeros TRIMMED, so `182` and never `182.00`, while GT-20's
            # fractional `14.2` peak keeps its place. **Only the SENTENCE
            # changes**: `amount`, `quantity` and `unit_price` are untouched.
            description=(
                f"{service} demand — peak {wording.quantity_text(usage.demand.quantity)} "
                f"{usage.demand.unit}"
            ),
            amount=usage.demand.quantity * config.demand_rate,
            taxable=True,
            quantity=usage.demand.quantity,
            # The DEMAND line's own unit, which is not the energy line's. Hard
            # rule 3 applies per line, and this is the line it is about.
            unit=usage.demand.unit,
            unit_price=config.demand_rate,
        ),
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md)
# generated: 2026-08-16 by the pricing-engines lane (EP-RAT-02 US-RAT-007 §7 · EP-RAT-05 US-RAT-015 §4)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half; the CONFIG half is S11's Demand card, already built) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_rat_012_demand.py✔ · pytest -m golden✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔
# exceptions: the demand QUANTITY's unit is whatever metering stamped on the demand register read and is NOT gated against a configured "kW" — B2 gives `demand_rate_config` a `demand_rate_per_kw` column and no unit column, so there is no configured unit to gate against and inventing the literal string "kW" as a gate would refuse a tenant metering in kVA. The unit is carried onto the line faithfully so the bill states it. REPORTED, not silently normalised. The ratchet and PF-penalty branches REFUSE rather than compute (BR-RAT-014 measurement half still PROPOSED, US-RAT-007 TC-8).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

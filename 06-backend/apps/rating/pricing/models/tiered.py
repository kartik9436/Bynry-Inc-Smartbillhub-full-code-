# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — tiered pricing)
#           Screens: — (the per-block lines render in S31.2)
#           No US-ID is cited in this header ON PURPOSE — see ../errors.py.
# Rules:    BR-RAT-002 (tier thresholds reset each bill AND scale with the
#           prorated period) · BR-RAT-026 (PURE tiers: every unit bills through
#           a tier, no allowance) · BR-RAT-032 (contiguous, seq-ordered, only
#           the last tier open-ended) · BR-RAT-001 (the quantity tiered is the
#           POST-multiplier one — B4.4, GT-5) · BR-RAT-003 (a plugin never
#           rounds) · BR-RAT-044 (one price(...) interface)
# Golden:   GT-2 (2x3.00 + 1.72x4.50 = 13.74) · GT-5 (1000x0.10 + 1740x0.14 =
#           343.60) — B5 ❄️ FROZEN 2026-08-08
# Tests:    06-backend/tests/test_us_rat_012_engine.py (GT-2, GT-5, ordering) ·
#           06-backend/tests/test_us_rat_015_plugins.py
# Impacts:  apps/rating/pricing/stages/price_usage.py (resolves this by name)
# ───────────────────────────────────────────────────────
"""`tiered` pricing model: inclining blocks, one line per block consumed.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money math (B4/CLAUDE.md sensitive paths),
AI-authored under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md. Implements finance-signed law, never invents it.

Serves US-RAT-012 TC-2/TC-3/TC-4. B5 GT-2: tiers 0-2 @ 3.00 / 2-5 @ 4.50 / 5+ @
6.00 on 3.72 kgal -> 2 x 3.00 + 1.72 x 4.50 = 13.74. B5 GT-5: the same shape
with a x10 multiplier already applied -> 1000 x 0.10 + 1740 x 0.14 = 343.60.

THE ORDER IS THE RULE (B4.4, and GT-5 exists to prove it)
---------------------------------------------------------
This plugin tiers `usage.billed_quantity`, which is post-multiplier by contract
(`MeasuredUsage` carries the raw quantity and the multiplier separately so the
order is assertable). It never sees a raw register delta. Tiering the raw 274 of
GT-5 instead of the post-multiplier 2,740 produces 100.36 — a plausible number
that is wrong, which is why US-RAT-012 TC-3 asserts it must NOT occur.

THRESHOLD SCALING (BR-RAT-002, and this is the "usage prorated" half of B4.3)
----------------------------------------------------------------------------
For a short or long period the block BOUNDS scale by the calendar-day factor,
not the quantity: US-RAT-012 TC-4 states it as "tier thresholds scale x15/30
(0-1,000 -> 0-500) before pricing". A half-month of service must not get a whole
month of cheap first-block units. The quantity itself is what the meter
measured and is never scaled — scaling both would prorate twice.
B5 freezes no worked tiered-proration figure (GT-3 says "example total pending
usage figures"), so the RULE is implemented and the missing example is reported.

PURE TIERS (BR-RAT-026, PO R5): there is no allowance and no included-units
block. Every unit bills through a tier; the base charge is a separate line.
"""

from __future__ import annotations

from decimal import Decimal

from apps.rating.pricing import errors, wording
from apps.rating.pricing.contracts import (
    KIND_USAGE,
    LineCandidate,
    MeasuredUsage,
    ModelConfig,
    PeriodShape,
    SubscriptionContext,
    TierSpec,
)

MODEL = "tiered"

ZERO = Decimal(0)


def _validate(tiers: tuple[TierSpec, ...], service: str) -> None:
    """BR-RAT-032, enforced at pricing time as well as at configuration time.

    apps/rating/services.py validates a structure before it may be STORED; this
    is the pricing-time half, because a tariff row that reached the engine
    malformed must refuse rather than price a nonsense block.
    """
    if not tiers:
        raise errors.TariffConfigError(
            f"tiered tariff for service {service!r} has no tiers (BR-RAT-032)."
        )
    previous: Decimal | None = None
    for index, tier in enumerate(tiers):
        if tier.unit_price < ZERO:
            raise errors.TariffConfigError(
                f"tier {index + 1} of service {service!r} has a negative unit price."
            )
        if tier.upper is None:
            if index != len(tiers) - 1:
                raise errors.TariffConfigError(
                    f"service {service!r}: only the LAST tier may be open-ended "
                    "(BR-RAT-032); tier "
                    f"{index + 1} of {len(tiers)} has no upper bound."
                )
            continue
        if previous is not None and tier.upper <= previous:
            raise errors.TariffConfigError(
                f"service {service!r}: tier bounds must ascend and be contiguous "
                f"(BR-RAT-032); tier {index + 1} ends at {tier.upper} after {previous}."
            )
        previous = tier.upper


def price(
    subscription: SubscriptionContext,
    usage: MeasuredUsage,
    config: ModelConfig,
    period: PeriodShape | None = None,
) -> tuple[LineCandidate, ...]:
    """One line per block actually consumed, in block order. UNROUNDED.

    `period` is optional ONLY so the plugin can be exercised from a fixture with
    no period at all; the stage always passes one, and its absence means a
    factor of 1 (no proration), never a guess.
    """
    _validate(config.tiers, subscription.service)
    factor = Decimal(1) if period is None else period.factor

    lines: list[LineCandidate] = []
    remaining = usage.billed_quantity
    lower = ZERO
    if config.per_size_line and remaining <= ZERO and config.tiers:
        # ── CR-063 · BR-MET-108's RULED ZERO IS A LINE, NOT A SILENCE ───────
        # A counting capacity service's ladder is one unbounded tier per size,
        # so a connection with nothing installed walks NO block and the loop
        # below emits nothing. The utility looked and found no equipment, which
        # is a real, billable answer: `OQ-670` (PO 2026-08-27, *"(b) Bill
        # $0.00"*) chose the visible zero over a refusal precisely because *"the
        # zero line buys VISIBILITY, putting the gap on the document instead of
        # in a silence"*. Trash already has this for nothing — its schedule is
        # FLAT and that plugin always emits its one line.
        #
        # ⚠ **GATED ON `per_size_line` AND NOT ON THE QUANTITY.** A METERED
        # tiered service that consumed nothing must go on emitting no usage
        # line: a `$0.00` kWh line would state on the customer's document that
        # their meter was read and showed nothing, which is a different claim
        # and is `stages/measure_consumption`'s to make, not this plugin's.
        return (
            LineCandidate(
                kind=KIND_USAGE,
                description=(
                    f"{subscription.service} usage"
                    if not config.size_label
                    else f"{subscription.service} - {config.size_label}"
                ),
                amount=ZERO,
                taxable=True,
                quantity=remaining,
                unit=usage.unit,
                unit_price=config.tiers[0].unit_price,
            ),
        )
    for index, tier in enumerate(config.tiers):
        if remaining <= ZERO:
            break
        if tier.upper is None:
            quantity = remaining
            block = f"{wording.quantity_text(lower)}+ {config.billed_unit}"
            next_lower = None
        else:
            # BR-RAT-002: the THRESHOLD scales with the prorated period; the
            # metered quantity never does — scaling both would prorate twice.
            upper = tier.upper * factor
            span = upper - lower
            if span <= ZERO:
                continue
            quantity = remaining if remaining < span else span
            block = f"{wording.quantity_text(lower)}-{wording.quantity_text(upper)} {config.billed_unit}"
            next_lower = upper
        lines.append(
            LineCandidate(
                kind=KIND_USAGE,
                # ⚠ DEF-968 — `block` USED TO INTERPOLATE THE THRESHOLD RAW, so
                # a customer read *"water usage tier 1 (0-5.000000 kgal)"*: the
                # bound is a `NUMERIC(18,6)` Decimal and an f-string prints it
                # at its storage scale. `wording.quantity_text` applies
                # BR-MET-144 — at most 2dp, trailing zeros trimmed, so `5` and
                # never `5.00`, because a quantity's precision is what the meter
                # measured. **Only the SENTENCE changes**: `quantity`,
                # `unit_price` and `amount` below are untouched Decimals and the
                # engine's arithmetic never reads this string back.
                # CR-063 — A COUNTING CAPACITY SERVICE'S LADDER IS ONE
                # UNBOUNDED TIER PER SIZE, and calling it *"tier 1 (0+
                # connection)"* on a customer's bill would be true and useless.
                # Where the config names a size, the line is named for the
                # EQUIPMENT: *fire - Fire line 6"*. `size_label` is None on
                # every metered ladder, so water's and electric's tier wording
                # is byte-identical and no frozen figure moves.
                description=(
                    f"{subscription.service} usage tier {index + 1} ({block})"
                    if not config.size_label
                    else f"{subscription.service} - {config.size_label}"
                ),
                amount=quantity * tier.unit_price,
                taxable=True,  # B4.2: usage is in the tax base
                quantity=quantity,
                unit=usage.unit,
                unit_price=tier.unit_price,
            )
        )
        remaining -= quantity
        if next_lower is not None:
            lower = next_lower

    if remaining > ZERO:
        # Only reachable when the top block is bounded — a structure that cannot
        # price every unit. BR-RAT-026 (pure tiers) says every unit bills through
        # a tier, so this is a refusal, not a silently dropped quantity.
        raise errors.TariffConfigError(
            f"service {subscription.service!r}: {remaining} {usage.unit} of usage falls "
            "above the highest tier and no tier is open-ended (BR-RAT-026/032). "
            "Unbilled usage is a refusal, never a dropped quantity."
        )
    return tuple(lines)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of the four frozen sources, concatenated in
#         order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-05-engine.md ·
#         04-docs/05-modules/06-rating/02-business-rules.md — recomputed 2026-08-10)
# generated: 2026-08-10 by story-coder (rating-engine lane — EP-RAT-05)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure module) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → GT-2 + GT-5 PASS✔ · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 14 PASS/0 FAIL/1 SKIP✔
# exceptions: PARTIAL evidence for threshold scaling — BR-RAT-002 and US-RAT-012 TC-4 state the rule ("0-1,000 -> 0-500 at 15/30") and B5 GT-3 explicitly withholds the worked figure ("example total pending usage figures"). The rule is implemented and covered by a repo test citing TC-4; no B5 figure exists to bind it to, and none is invented. REPORTED.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

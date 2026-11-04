# ── Trace ──────────────────────────────────────────────
# Epics:    EP-RAT-05 (rating engine core — multiplier + tiers)
#           Screens: — (priced lines render in S31.2)
# Rules:    BR-RAT-001 (multiplier applies BEFORE tier evaluation) ·
#           BR-RAT-002 (tier thresholds reset each bill) · BR-RAT-026 (pure
#           tiers) · BR-RAT-003 (round per line, half-up, 2dp, at finalization)
# Golden:   GT-5 — B5 ❄️ FROZEN, finance-signed 2026-08-08 (05-golden-tests.md
#           lines 24-25). Every figure below is COPIED from those two lines.
# Tests:    this file (xfail until apps.rating.engine.price_period lands)
# Impacts:  06-backend/apps/billing/rating_seam.py · apps/rating/engine.py 🔒
# ───────────────────────────────────────────────────────
"""GT-5 - raw 274 x10 -> 2,740 kWh; tiers 0-1000@0.10, 1000+@0.14 -> 343.60; multiplier-BEFORE-tiers (B4.4 CONFIRMED)

B5 GT-5 verbatim
----------------
  line 24: "## GT-5 - Tier crossing with multiplier - CONFIRMED
            multiplier-before-tiers (B4.4)"
  line 25: "Input: raw (current-prior)=274, multiplier x10 -> 2,740 kWh; tiers
            0-1000 @0.10, 1000+ @0.14. Multiplier applied first: 1000x0.10 +
            1740x0.14 = 100+243.60 = **343.60**. [check] rule confirmed."

This is the case that proves the ORDER, which is the whole content of B4.4:
tier the post-multiplier quantity, never the raw delta.

WHERE THE MULTIPLIER IS APPLIED — PO ruling 2026-08-11 (decision 4)
------------------------------------------------------------------
B4.4 fixes the ORDER (multiplier, then tiers) and says nothing about which
module does the multiplying. Until this ruling, BOTH could: metering's
`consumption_from_registers` multiplied by the METER's multiplier, and the
pricing engine multiplied again by a multiplier carried on the TARIFF. Nothing
connected the two yet, so nothing was wrong in production — but the moment
billing wired metering's output into the engine, a dial delta of 1,247 at x40
would have been priced as 1,995,200 kWh instead of 49,880, turning a $4,853
bill into $194,113 with no structural sign that anything had gone wrong.

The PO ruled: **metering applies it, the engine never does.** The multiplier is
a property of the METER (`assets.Asset.multiplier`) — two meters on the same
tariff have different multipliers, so a tariff-carried multiplier could only
ever be right by coincidence.

NO FROZEN FIGURE MOVED, and no finance re-sign was required. B5 line 25 states
the input BOTH ways — "raw (current-prior)=274, multiplier x10 -> 2,740 kWh" —
so this test now walks the frozen line left to right through the two modules
that own each half, instead of handing the whole line to one of them. Every
figure below is still B5's: 274, x10, 2,740, 100, 243.60, 343.60.

That is also why this test IMPORTS METERING. With the two halves in different
modules, an engine-only test can no longer prove "multiplier before tiers" — it
can only prove "tiers on whatever it was given". The chain is the rule now, so
the chain is what is asserted.

WHAT THE CHAIN TEST DOES *NOT* CATCH — measured, not assumed. An earlier draft
of this docstring claimed the chain test would also fail if the engine started
multiplying again. It would not, and the red-proof said so: this tariff carries
NO multiplier, so an engine that re-armed its multiplication would multiply by
1 and produce the identical 343.60. Only `test_gt05_engine_refuses_a_tariff_
multiplier` below caught the re-armed engine. That is the whole reason the
trip-wire is a separate assertion instead of a comment — and the reason the
claim is written here as a limit rather than left as the reassurance it was.

NOT FROZEN IN B5: GT-5 names no base charge, no tax rate and no bill total — so
the tariff carries no base charge (absence, not a base of zero) and the test
asserts the usage charge only.
"""

from decimal import Decimal

import pytest

from apps.billing import rating_seam
from apps.metering import quantities

from .conftest import FULL_PERIOD, TAXED_ACCOUNT

pytestmark = pytest.mark.golden

# ── INPUT (B5 GT-5 line 25) ─────────────────────────────────────────────────
RAW_DELTA = Decimal("274")  # "raw (current-prior)=274"
MULTIPLIER = Decimal("10")  # "multiplier x10"
# B5 states the post-multiplier quantity itself — "-> 2,740 kWh" — so this is a
# copied figure, not a product computed here. It is what the ASSERTION uses; the
# value the engine actually receives is DERIVED by metering below, so agreement
# between the two is a result, not a restatement.
POST_MULTIPLIER_CONSUMPTION = Decimal("2740")  # "-> 2,740 kWh"

TARIFF = rating_seam.TariffConfig(
    service="electric",
    model="tiered",
    billed_unit="kWh",  # "2,740 kWh"
    base_charge=None,  # B5 GT-5 names NO base charge — absence, not zero
    tiers=(
        rating_seam.Tier(upper=Decimal("1000"), unit_price=Decimal("0.10")),  # "0-1000 @0.10"
        rating_seam.Tier(upper=None, unit_price=Decimal("0.14")),  # "1000+ @0.14"
    ),
    # NO multiplier. The engine refuses one outright now, and that refusal is
    # asserted below — the trip-wire matters more than the absence.
)

# METERING's half of the frozen line: the raw delta and the meter's multiplier
# become a real quantity in a real unit. Prior 0 / current 274 is B5's
# "(current-prior)=274" written as the two readings it is a difference of; the
# 5-digit register is stated because the wrap check has no default span, and
# 274 is nowhere near it.
CONSUMPTION = quantities.consumption_from_registers(
    prior_read=Decimal("0"),
    current_read=RAW_DELTA,
    multiplier=MULTIPLIER,
    register_digits=5,
    unit="kWh",
)

# ── EXPECTED (B5 GT-5 line 25) ──────────────────────────────────────────────
EXPECTED_USAGE = Decimal("343.60")  # "100+243.60 = **343.60**"
EXPECTED_TIER_1 = Decimal("100")  # "1000x0.10 ... 100"
EXPECTED_TIER_2 = Decimal("243.60")  # "1740x0.14 ... 243.60"

# The wrong-order result, quoted from EP-RAT-05 US-RAT-012 TC-3 (a spec doc, NOT
# B5): "multiplier-after-tiers (= 100.36) must NOT occur". Asserted as a
# negative so a regression that tiers the raw 274 fails loudly instead of
# quietly producing a plausible number.
MULTIPLIER_AFTER_TIERS_MUST_NOT_OCCUR = Decimal("100.36")  # EP-RAT-05 US-RAT-012 TC-3


def test_gt05_metering_supplies_the_post_multiplier_quantity():
    """Metering's half of the frozen line, on its own: 274 x10 -> 2,740 kWh.

    Asserted separately so that if the chain test fails, it says WHICH module
    lost the multiplier rather than only that the bill came out wrong.
    """
    assert CONSUMPTION.amount == POST_MULTIPLIER_CONSUMPTION  # B5 "-> 2,740 kWh"
    assert CONSUMPTION.unit == "kWh"  # hard rule 3 — carried, never assumed


def test_gt05_engine_refuses_a_tariff_multiplier():
    """The trip-wire. A caller that still supplies one believes a stale thing.

    Ignoring the field would price the right number for the wrong reason and
    leave that belief intact for the next change to act on. So it refuses, and
    the refusal names the ruling. This is the guard that makes double
    multiplication impossible rather than merely unlikely.

    AMENDED 2026-08-11 (DEF-047). This called the SEAM and caught RATING's
    exception type, which worked only because the seam did not translate one —
    and that missing translation is the defect: an untranslated rating refusal
    escaped billing's run loop and killed whole runs. Now `price_period` raises
    `rating_seam.PricingRefused`, so both sides are pinned rather than one: the
    seam's own type on the outside, rating's `TariffConfigError` as the CAUSE,
    and the ruling still named in the message. The trip-wire is not weakened by
    this — it is the same refusal, asserted at both ends of the translation.
    """
    from apps.rating.pricing import errors as pricing_errors

    with pytest.raises(rating_seam.PricingRefused) as raised:
        rating_seam.price_period(
            tariff=rating_seam.TariffConfig(
                service="electric",
                model="tiered",
                billed_unit="kWh",
                tiers=TARIFF.tiers,
                multiplier=MULTIPLIER,  # what the OLD contract expected
            ),
            consumption=CONSUMPTION,
            period=FULL_PERIOD,
            account=TAXED_ACCOUNT,
            taxes=(),
        )
    assert "double-multiply" in str(raised.value)
    # The engine's own refusal survives the translation intact — a seam that
    # swallowed the cause would leave a clerk with billing's paraphrase and no
    # way back to the rule that fired.
    assert isinstance(raised.value.__cause__, pricing_errors.TariffConfigError)
    assert "PO ruling 2026-08-11" in str(raised.value.__cause__)


def test_gt05_tier_multiplier():
    # Rule CONFIRMED by finance (B4, 2026-08-07). Expected values: B5 GT-5.
    bill = rating_seam.price_period(
        tariff=TARIFF,
        consumption=CONSUMPTION,
        period=FULL_PERIOD,
        account=TAXED_ACCOUNT,
        # NOT FROZEN IN B5: GT-5 names no tax rate, so none is supplied.
        taxes=(),
    )

    usage_lines = bill.lines_of("usage")
    total_usage = sum((line.amount for line in usage_lines), Decimal("0"))
    assert total_usage == EXPECTED_USAGE
    assert total_usage != MULTIPLIER_AFTER_TIERS_MUST_NOT_OCCUR  # B4.4: order matters
    assert {line.unit for line in usage_lines} == {"kWh"}  # hard rule 3

    # The multiplier must have been applied BEFORE tiering: the quantity that
    # went through the tier table is 2,740 (B5's own figure), not the raw 274.
    assert (
        sum((line.quantity or Decimal("0") for line in usage_lines), Decimal("0"))
        == POST_MULTIPLIER_CONSUMPTION
    )

    if len(usage_lines) > 1:  # per-block lines: assert B5's own split
        assert [line.amount for line in usage_lines][:2] == [EXPECTED_TIER_1, EXPECTED_TIER_2]

    # B5 GT-5 names no base charge, so no base line may be invented.
    assert bill.lines_of("base") == ()

    # NOT FROZEN IN B5: tax and total for GT-5. Deliberately unasserted.


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-012@70a0044 (sha1[:7] of 05-golden-tests.md + 04-money-math-rules.md
#         + EP-RAT-05-engine.md + 06-rating/02-business-rules.md, concatenated in that order)
# generated: 2026-08-10 by story-coder (golden-fixture lane — B5 encoding, test-first)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure-math fixture) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → 12 passed / 1 xfailed✔
# revised: 2026-08-11 (PO ruling, decision 4 — metering applies the meter
#         multiplier, the engine refuses one). No frozen figure moved: B5 line
#         25 states the input BOTH ways ("raw 274, x10 -> 2,740"), so the test
#         now walks that line through the two modules owning each half. NO
#         finance re-sign was required and none was taken.
# gates(revision): proved RED by re-arming the engine to multiply AND removing
#         the trip-wire. The two refusal tests failed; the CHAIN test PASSED —
#         because this tariff carries no multiplier, a re-armed engine
#         multiplies by 1 and yields the same 343.60. The docstring had claimed
#         the chain test would catch it; the red-proof disproved that claim and
#         the docstring now records the limit instead (hard-won law 1 — a
#         comment claiming a guarantee is not the guarantee).
# exceptions: PARTIAL — B5 GT-5 names no base charge, no tax rate and no bill total; the tariff carries base_charge=None (absence, not zero) and tax/total are unasserted. The negative guard 100.36 is copied from EP-RAT-05 US-RAT-012 TC-3, a spec doc — cited as such, NOT presented as a B5 figure.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

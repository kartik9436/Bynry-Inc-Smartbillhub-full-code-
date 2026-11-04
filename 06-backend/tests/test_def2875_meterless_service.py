# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-2875 — the R1–R7 shadow could not evaluate ONE account of any
#          utility whose sewer service point holds no meter. `adapt()` demanded
#          a meter multiplier for every metered service; `BR-RAT-015` prices
#          sewer as a share of the water usage charge, so it has no meter and
#          metering publishes no factor. Measured 2026-09-01 over three
#          utilities: 116 of 163 accounts NOT ATTEMPTED, while the live path
#          billed their sewer base charge without difficulty.
# Rules:   BR-RAT-015 (sewer is a share of the water usage charge) ·
#          BR-MET-056 (a read stores the factor USED; an absent factor is not
#          1) · BR-RAT-081 / BR-RAT-090 (a DECLARED-unmetered service bills per
#          asset count — a different case) · DEF-161 (the two kinds of "no
#          meter") · DEF-2851 (the same conflation, one field over)
# Tests:   this file. The measured half is
#          `10-scripts/cr052_r1r7_shadow_measure.py --tenant all`.
# Impacts: apps/rating/resolution.billable_quantity 🔒 (rating math —
#          HUMAN-REVIEW-PENDING) · apps/billing/resolution_shadow.adapt 🔒
# ───────────────────────────────────────────────────────
"""A service with NO METER is not a meter whose factor nobody wrote down.

Three `absent_reason`s reach billing on a reading row and only one of them is
this defect. The file exists to keep them apart, in both directions, because
each direction costs something different:

  * treat *"no meter"* as *"factor missing"* and every utility that bills sewer
    is unevaluable — 116 of 163 accounts, which is what `DEF-2875` measured;
  * treat *"factor missing"* as *"no meter"* and a ×10 register with no recorded
    factor bills a TENTH of the customer's consumption on a document that looks
    entirely normal — `BR-MET-056`, and the reason the refusal exists at all.

The fix is an ORDERING, not a removal: nothing to multiply is answered before
the factor is asked for, and the factor is still demanded the moment there is a
register difference to scale.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.billing import resolution_shadow
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.metering import selectors as metering_selectors
from apps.rating import resolution


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE RATING HALF — nothing to multiply is answered before the factor
# ══════════════════════════════════════════════════════════════════════════


def test_no_register_difference_needs_no_multiplier():
    """RED BEFORE THE FIX: this raised `MeterMultiplierUnstated`.

    A sewer connection has no register, so `register_quantity` is None and the
    factor is a question about a meter that does not exist. Refusing here
    refused the whole ACCOUNT — `BR-BIL-872` gives a chain refusal no fallback —
    for a service the live path bills from its base charge.
    """
    meter = resolution.MeterFacts(
        service="sewer", connection_size=resolution.NO_SIZE, multiplier=None
    )
    assert resolution.billable_quantity(meter, None) is None


def test_a_register_difference_with_no_multiplier_still_refuses():
    """THE GUARD IS NOT WEAKENED, and this is the case it exists for.

    Reordering the two checks would be worth nothing if it also let a real
    ×10 register through. `62` on a ×10 register is `620` and lands in tier 2;
    `62` never leaves tier 1 (BR-RAT-001). With a difference present and no
    factor, the refusal fires exactly as it always did.
    """
    meter = resolution.MeterFacts(
        service="electric", connection_size="E-CT", multiplier=None
    )
    with pytest.raises(resolution.MeterMultiplierUnstated) as refusal:
        resolution.billable_quantity(meter, Decimal("62"))
    assert "an absent factor is not 1" in str(refusal.value)


def test_the_arithmetic_is_unchanged_where_both_facts_are_present():
    """×10 on a difference of 50 is 500, before and after. No priced figure moved."""
    meter = resolution.MeterFacts(
        service="electric", connection_size="E-CT", multiplier=Decimal("10")
    )
    assert resolution.billable_quantity(meter, Decimal("50")) == Decimal("500")


def test_a_zero_register_difference_is_not_a_missing_one():
    """`0` is a meter that was read and showed nothing, and it still needs a factor.

    Written because the fix's own `if register_quantity is None` would be wrong
    as `if not register_quantity` — `Decimal("0")` is falsey, and that spelling
    would have quietly waved a real meter through with no factor.
    """
    meter = resolution.MeterFacts(
        service="electric", connection_size="E-CT", multiplier=None
    )
    with pytest.raises(resolution.MeterMultiplierUnstated):
        resolution.billable_quantity(meter, Decimal("0"))


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE ADAPTER HALF — which `absent_reason` blocks and which does not
# ══════════════════════════════════════════════════════════════════════════


class _Account:
    """The two attributes `adapt` reads off an account row."""

    unit_id = "unit-1"
    account_type = None


def _data(*readings: ServiceReading) -> AccountBillingData:
    return AccountBillingData(
        account_id="a-1",
        account_no="AC-2026-00001",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=None,
        period_end=None,
        cycle_days=31,
        service_days=31,
        rate_plan_id="plan-1",
        readings=readings,
    )


@pytest.fixture()
def seams(monkeypatch):
    """Metering publishes a size and a factor for water, and neither for sewer.

    That is the real shape measured on `perf-utility-1`: the water service point
    holds an asset with a ×1 read, the sewer service point holds none, so
    `billing_multiplier_for` answers None for sewer for a reason no human can
    fix on a screen.
    """
    monkeypatch.setattr(
        metering_selectors,
        "connection_size_for",
        lambda unit_id, service, *a, **k: "W-58" if service == "water" else None,
        raising=False,
    )
    monkeypatch.setattr(
        metering_selectors,
        "billing_multiplier_for",
        lambda unit_id, service, *a, **k: (
            Decimal("1") if service == "water" else None
        ),
        raising=False,
    )
    monkeypatch.setattr(
        metering_selectors, "unit_row", lambda unit_id: {}, raising=False
    )
    # BR-RAT-090's count seam. `None` is "nobody looked", which is what the
    # declared-unmetered case below is asserting still blocks — and stubbing it
    # keeps this file out of the database, which is the only reason it can
    # enumerate cases at this speed.
    monkeypatch.setattr(
        metering_selectors,
        "billable_asset_count",
        lambda unit_id, service, period_end, *a, **k: None,
        raising=False,
    )


def test_a_meterless_sewer_service_no_longer_blocks_the_whole_account(seams):
    """RED BEFORE THE FIX: `blocked_reason` was `MISSING_MULTIPLIER`.

    This is the account shape that was 116 of 163. Every OTHER step — the plan
    version, the schedule version, the base amount, the jurisdiction factor, the
    discounts and the taxes — was unevaluable on all of them because of one
    field on one service that has no meter.
    """
    inputs = resolution_shadow.adapt(
        _data(
            ServiceReading(service_code="water", prior_read=Decimal("828"),
                           current_read=Decimal("837")),
            ServiceReading(
                service_code="sewer",
                absent_reason=metering_selectors.READ_ABSENT_NO_METER,
            ),
        ),
        account=_Account(),
    )

    assert inputs.blocked_reason is None, inputs.blocked_detail
    sewer = next(m for m in inputs.meters if m.service == "sewer")
    assert sewer.connection_size == resolution.NO_SIZE
    assert sewer.multiplier is None, (
        "the adapter defaulted the factor to 1 — that makes R3b report parity by "
        "construction on every meterless service, which is the comfortable lie "
        "this whole shadow exists to refuse"
    )
    # And the chain agrees it has nothing to bill from a quantity.
    assert resolution.billable_quantity(sewer, inputs.quantities["sewer"]) is None


def test_a_meter_that_was_simply_not_read_still_blocks(seams):
    """`no_read` is a DATA GAP a human fixes, and it must keep blocking.

    The factor is knowable and absent here — there IS a meter — so this is
    exactly what `MeterMultiplierUnstated` was written for. Without this case
    the fix above is indistinguishable from deleting the guard.
    """
    inputs = resolution_shadow.adapt(
        _data(
            ServiceReading(
                service_code="electric",
                absent_reason=metering_selectors.READ_ABSENT_NO_READ,
            ),
        ),
        account=_Account(),
    )
    assert inputs.blocked_reason == resolution_shadow.MISSING_CONNECTION_SIZE, (
        "fixture: electric has a ratified ladder and this stub publishes no size, "
        "so the SIZE branch blocks first — which is DEF-514 and is correct"
    )


def test_a_declared_unmetered_service_still_takes_the_asset_count_path(seams):
    """`service_not_metered` is BR-RAT-090's route and this fix must not touch it.

    A declared-unmetered service bills per CART, so it needs a count and not a
    multiplier, and an absent count still blocks (`AssetCountUnavailable`'s own
    reasoning: *"no carts recorded" and "zero carts" are different facts*).
    """
    inputs = resolution_shadow.adapt(
        _data(
            ServiceReading(
                service_code="trash",
                absent_reason=metering_selectors.READ_ABSENT_SERVICE_NOT_METERED,
            ),
        ),
        account=_Account(),
    )
    assert inputs.blocked_reason == resolution_shadow.MISSING_ASSET_COUNT
    assert inputs.meters == (), "a declared-unmetered service is not a meter"


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-2875 · DEF-2851 (the same conflation at the SIZE) · CR-052 task 20
#         · decision log 2026-08-31 *"STEP 4 OF THE CUTOVER, ANSWERED"* (the
#         widening that found this) · decision log 2026-09-01
# status: VERIFIED-UNRATIFIED · HUMAN-REVIEW-PENDING 🔒 — `billable_quantity` is
#         rating math and `adapt` feeds it; the review-ledger row states the
#         reordering in plain English with its figure.
# generated: 2026-09-01 by the R3-release evidence lane (claude)
# gates: golden-verify 33 PASS / 0 FAIL and G61 frozen-figures PASS before and
#         after. NO ❄️ B4/B5 figure is read or moved: the reordering changes an
#         answer only where `register_quantity` is None, and every golden case
#         states a quantity.
# exceptions: (1) nothing is switched — `resolution_switch.SERVED_BY_CHAIN_
#         DEFAULT` is the empty string and no real bill is priced through the
#         chain, so this changes no customer's charge today.

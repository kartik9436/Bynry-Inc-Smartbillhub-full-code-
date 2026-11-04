# ── Trace ──────────────────────────────────────────────
# Defects: DEF-438 (the chain has no production caller) · DEF-1810..DEF-1816
#          (the disagreements this suite MEASURES) · DEF-514 (no connection size
#          is stored anywhere) · DEF-494 (the two paths mean opposite things by
#          "a plan in force")
# Rules:   BR-RAT-001 (the METER multiplier scales the QUANTITY, before tiers) ·
#          BR-MET-019 · BR-MET-056 (a read stores the multiplier USED) ·
#          BR-RAT-081 (metered or unmetered is DECLARED) · BR-SHL-020 (a refusal
#          reads as a sentence, not a code)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""THE SHADOW ADAPTER, and the one property that makes it worth anything.

`DEF-438`'s escape reason names the trap this suite is written against:

    "every gate that touches this file is a unit test calling it DIRECTLY,
     which is exactly the shape that passes forever on dead code."

So the tests below are NOT "does the adapter work". They are:

  * **does it go RED when the chain is unplugged** — `test_unplugging_the_chain_
    changes_the_outcome`, which is the whole acceptance criterion of the
    recorded method (decision log 2026-08-27, *"HOW THE SCREEN PROVES R1–R7 IS
    WIRED — the test must FAIL when the chain is unplugged, or it proves
    nothing"*);
  * **does it refuse to invent the facts it is missing** — four `MISSING_*`
    tests, one per fact, because a defaulted value is how a disagreement gets
    reconciled away quietly;
  * **does it feed R3b the REGISTER DIFFERENCE and never the stored
    consumption** — the 100× test, the only one here whose failure would mean a
    live bill is wrong.

⚠ NOTHING HERE ASSERTS A FROZEN FIGURE. B4 money math and B5's GT-1..61 are
❄️ FROZEN; no number in this file is one of theirs.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, resolution_shadow
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.rating import resolution
from core import sample_fixture as fixture

from tests.test_def_438_parity import (  # the fixture set this extends
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    CYCLE_DAYS,
    _account_on,
    _price_live,
    _water_plan,
    price_water_base_by_size,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _publish(monkeypatch, *, size="1", multiplier="1"):
    """Publish the two metering seams the adapter late-binds.

    This is `gather.py`'s own defence of the same posture, made executable:
    *"What is missing is the SOURCE, and it has a defect row; what is proved is
    the HOP."* The seams do not exist in the product (DEF-514 for the size, and
    billing's read seam publishes no multiplier at all), so the hop is proved
    by publishing them here and asserting the fact lands in `MeterFacts`.
    """
    from apps.metering import selectors as metering_selectors

    monkeypatch.setattr(
        metering_selectors, "connection_size_for", lambda _u, _s: size, raising=False
    )
    monkeypatch.setattr(
        metering_selectors,
        "billing_multiplier_for",
        (lambda _u, _s: multiplier) if multiplier is not None else (lambda _u, _s: None),
        raising=False,
    )


# ══════════════════════════════════════════════════════════════════════════
# THE ACCEPTANCE CRITERION — red when unplugged
# ══════════════════════════════════════════════════════════════════════════


def test_unplugging_the_chain_changes_the_outcome(brazos, dana, monkeypatch):
    """THE test. If this passes with the chain unplugged, nothing here is wired.

    A shadow run that reported the same thing whether or not `resolve()` ran
    would be indistinguishable from dead code — which is the state DEF-438 has
    described since 2.29.54. So the assertion is a DIFFERENCE between two runs,
    not a property of one.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _publish(monkeypatch, size="5/8", multiplier="1")
        data = _price_live(account)

        wired = resolution_shadow.shadow_account(
            data, account=account, service_date=SERVICE_DATE
        )

        assert wired.status != resolution_shadow.STATUS_NOT_ATTEMPTED, (
            "the chain never ran, so this suite proves nothing about it — "
            f"blocked on {wired.blocked_reason!r}: {wired.blocked_detail}"
        )

        # Unplug the chain exactly as a broken adapter would: `resolve` gone.
        monkeypatch.setattr(resolution, "resolve", None, raising=False)
        with pytest.raises(TypeError):
            resolution_shadow.shadow_account(
                data, account=account, service_date=SERVICE_DATE
            )


def shadowing_only():
    """The switch OFF, because a SHADOW measures a world nothing is switched on in.

    ⚠ **THE THREE CASES BELOW DELIBERATELY BUILD AN ACCOUNT THE RULED CHAIN
    CANNOT PRICE, AND SINCE `CR-057` THAT STOPS THE LIVE CALL BEFORE THE SHADOW
    IS EVER ASKED (`DEF-2965`).** Each one patches the seam so a fact is missing
    — no size, no multiplier, no base — and then calls `_price_live` to get the
    `AccountBillingData` it hands to `resolution_shadow.shadow_account`. With
    R3 + R4 served, `gather` runs the chain through `resolution_switch.apply`,
    the chain refuses on that same missing fact, and `_price_live` RAISES
    `GatherProblem` instead of returning. The assertion under test — *the
    ADAPTER reports which fact is missing and stops* — is never reached.

    `resolution_shadow`'s own docstring is the authority for the posture: it
    *"switches no step"*, it *"measures and publishes"*. A shadow reading is a
    statement about the UNSWITCHED path by construction, so these cases now say
    so instead of inheriting it from a default that has moved twice — which is
    `DEF-2817`'s lesson, in `nothing_switched_on`'s own words: *"here the switch
    is OFF, and that is the point, never here the switch happens to be off."*

    ⚠ **IT WRAPS THE LIVE CALL ONLY.** `shadow_account` is deliberately left
    outside it: the shadow must behave identically either way, and running it
    under the override would hide it if it ever stopped doing so.
    """
    from django.test import override_settings

    return override_settings(BILLING_RESOLUTION_STEPS="")


def test_the_refusal_reaches_the_screen_as_a_sentence_naming_its_step(
    brazos, dana, monkeypatch
):
    """The chain's signature — *"R3: connection size …"* — not a class name.

    BR-SHL-020: a refusal reads as a SENTENCE. The decision log calls rendering
    the exception class name *"the lazy way to make the first test pass"*, so
    this asserts the sentence and the step SEPARATELY: a `refusal_type` with an
    empty `refusal_sentence` would satisfy a careless version of this test.

    The seeded size is one the schedule does not price, which is the exact case
    the recorded screen test uses — and the live path's own word for it
    (`GATHER_SIZE_UNRESOLVED`) is a DIFFERENT sentence, which is what makes the
    screen a probe for which path ran.
    """
    from apps.rating import models as rating_models

    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        # ⚠ DEF-1811 — the refusal is reached by BLANKING THE BASE, not by
        # naming an unpriced size. A size the adapter supplies is a size the
        # catalogue serves, by construction; see that defect and the test below.
        rating_models.TariffVersion.objects.filter(tenant=brazos).update(
            base_charge=None
        )
        _publish(monkeypatch, size="5/8", multiplier="1")
        with shadowing_only():
            data = _price_live(account)
        # ⚠ `DEF-BIL-9054` — THE BASE IS RE-PRICED BY SIZE *AFTER* THE LIVE
        # PRICE, AND THAT ORDER IS THE CASE. Since `DEF-RAT-8822` (PO
        # 2026-10-01, option A) the ruled path holds a size only where the base
        # DEPENDS on it, and since `DEF-BIL-9024` the live path refuses the same
        # account for the same reason — so on one catalogue the two agree and
        # this block cannot be reached. It is reached when the catalogue moved
        # between the two reads, which is exactly what the shadow exists to
        # catch; the adapter must still refuse to invent the size.
        price_water_base_by_size(brazos)

        outcome = resolution_shadow.shadow_account(
            data, account=account, service_date=SERVICE_DATE
        )

        assert outcome.status == resolution_shadow.STATUS_CHAIN_REFUSED
        assert outcome.refusal_step == "R3"
        assert outcome.refusal_type == "SizeNotServed"
        assert outcome.refusal_sentence and "5/8" in outcome.refusal_sentence
        # The two vocabularies, side by side — both sentences cannot be on screen.
        assert gather.GATHER_SIZE_UNRESOLVED not in outcome.refusal_sentence


# ══════════════════════════════════════════════════════════════════════════
# THE ADAPTER REFUSES TO INVENT — one test per missing fact
# ══════════════════════════════════════════════════════════════════════════


def test_an_unpublished_multiplier_blocks_and_is_never_defaulted_to_one(
    brazos, dana, monkeypatch
):
    """`resolution.MeterMultiplierUnstated`'s reasoning, enforced at the adapter.

    ⚠ A defaulted 1 would make R3b report PARITY BY CONSTRUCTION on every
    account, because ×1 of the register difference equals metering's stored
    figure exactly when the multiplier really is 1. The parity would be an
    artefact of the adapter, not a fact about the product — and it would read
    as the best possible news.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(
            brazos, dana, plan, multiplier="10"
        )
        _publish(monkeypatch, size="5/8", multiplier=None)
        with shadowing_only():
            data = _price_live(account)

        outcome = resolution_shadow.shadow_account(
            data, account=account, service_date=SERVICE_DATE
        )

        assert outcome.status == resolution_shadow.STATUS_NOT_ATTEMPTED
        assert outcome.blocked_reason == resolution_shadow.MISSING_MULTIPLIER
        assert "is NOT 1" in (outcome.blocked_detail or "")


def test_an_unresolved_connection_size_blocks_rather_than_guessing(
    brazos, dana, monkeypatch
):
    """DEF-514 — the product stores a connection size on NO table.

    The adapter reports which service and stops. A guessed size is a priced
    bill: `resolve_size_row` refuses a size the schedule does not carry
    precisely so that nobody is charged $0.00 for a size the utility never
    priced.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(brazos, dana, plan)
        _publish(monkeypatch, size=None, multiplier="1")
        with shadowing_only():
            data = _price_live(account)
        # ⚠ `DEF-BIL-9054` — THE BASE IS RE-PRICED BY SIZE *AFTER* THE LIVE
        # PRICE, AND THAT ORDER IS THE CASE. Since `DEF-RAT-8822` (PO
        # 2026-10-01, option A) the ruled path holds a size only where the base
        # DEPENDS on it, and since `DEF-BIL-9024` the live path refuses the same
        # account for the same reason — so on one catalogue the two agree and
        # this block cannot be reached. It is reached when the catalogue moved
        # between the two reads, which is exactly what the shadow exists to
        # catch; the adapter must still refuse to invent the size.
        price_water_base_by_size(brazos)

        outcome = resolution_shadow.shadow_account(
            data, account=account, service_date=SERVICE_DATE
        )

        assert outcome.status == resolution_shadow.STATUS_NOT_ATTEMPTED
        assert outcome.blocked_reason == resolution_shadow.MISSING_CONNECTION_SIZE


def test_the_adapter_feeds_the_register_difference_and_never_the_consumption(
    brazos, dana, monkeypatch
):
    """THE 100× TEST — the only failure here that would mean a live bill is wrong.

    Metering stores `consumption = (current − prior) × multiplier` and publishes
    it ALREADY POST-MULTIPLIER. `resolution.billable_quantity` multiplies again.
    On a ×10 register the difference is 50 and the stored consumption is 500; if
    the adapter passed the stored figure the chain would bill **5,000**.

    Asserted on the ADAPTER's own output rather than on a total, because a total
    can hide two errors that cancel.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        account, _unit, _asset, delta = _account_on(
            brazos, dana, plan, multiplier="10", register="1200", prior="1150"
        )
        _publish(monkeypatch, size="5/8", multiplier="10")
        data = _price_live(account)

        inputs = resolution_shadow.adapt(data, account=account)

        assert inputs.blocked_reason is None, inputs.blocked_detail
        assert inputs.quantities["water"] == delta == Decimal("50"), (
            "the adapter must hand the chain the RAW register difference"
        )
        stored = next(
            r.consumption.amount for r in data.readings if r.service_code == "water"
        )
        assert stored == Decimal("500"), "fixture sanity: metering stored the ×10 figure"
        assert inputs.quantities["water"] != stored, (
            "the adapter passed metering's post-multiplier figure — the chain "
            "would multiply it a second time and bill 5,000 on a 50-unit "
            "register difference"
        )
        # And the multiplier reached the chain, so R3b reproduces 500 itself.
        meter = next(m for m in inputs.meters if m.service == "water")
        assert meter.multiplier == Decimal("10")
        assert resolution.billable_quantity(meter, inputs.quantities["water"]) == stored


# ══════════════════════════════════════════════════════════════════════════
# THE REPORT CANNOT TELL A COMFORTABLE LIE
# ══════════════════════════════════════════════════════════════════════════


def test_compare_refuses_to_report_parity_over_zero_services():
    """An empty comparison is a FAILURE, not a pass.

    `tests/test_def_438_parity.py` very nearly shipped exactly this: a fixture
    wrote no `plan_services` row, the per-service loop never ran once, and
    PARITY was reported over zero services compared.
    """

    class _Empty:
        services = ()

    data = AccountBillingData(
        account_id="a",
        account_no="A-1",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=CYCLE_DAYS,
        service_days=CYCLE_DAYS,
    )
    with pytest.raises(AssertionError, match="compared nothing"):
        resolution_shadow.compare(data, _Empty())


def test_summarise_distinguishes_zero_disagreements_from_zero_attempts():
    """⚠ A COUNT THAT IS ALWAYS ZERO MEANS THE CHAIN IS NOT RUNNING.

    Two reports that both say *"0 disagreements"* and mean opposite things: one
    compared 2 accounts and found them identical, the other compared none at
    all. A screen showing only the disagreement count could not tell them apart,
    which is why `attempted` is published beside it.
    """
    agreed = resolution_shadow.ShadowOutcome(
        account_id="a", account_no="A-1", status=resolution_shadow.STATUS_AGREED
    )
    blocked = resolution_shadow.ShadowOutcome(
        account_id="b",
        account_no="A-2",
        status=resolution_shadow.STATUS_NOT_ATTEMPTED,
        blocked_reason=resolution_shadow.MISSING_MULTIPLIER,
    )

    real = resolution_shadow.summarise((agreed, agreed))
    hollow = resolution_shadow.summarise((blocked, blocked))

    assert real["disagreed"] == hollow["disagreed"] == 0
    assert real["attempted"] == 2 and hollow["attempted"] == 0
    assert hollow["blocked_by_reason"] == {resolution_shadow.MISSING_MULTIPLIER: 2}


def test_a_chain_refusal_is_counted_by_its_step():
    """The report groups by R-step, because that is what step 4 rules on."""
    refused = resolution_shadow.ShadowOutcome(
        account_id="a",
        account_no="A-1",
        status=resolution_shadow.STATUS_CHAIN_REFUSED,
        refusal_step="R4",
        refusal_type="ChargeCodeAmountMissing",
        refusal_sentence="R4: charge code 'LATE' ...",
    )
    report = resolution_shadow.summarise((refused,))
    assert report["chain_refused"] == 1
    assert report["by_step"] == {"R4": 1}
    assert report["disagreed"] == 1, "a refusal IS a disagreement, not a third state"


# ── Lifecycle ─────────────────────────────────────────────
# status: PROPOSED — proves the SHADOW. Nothing here asserts that the chain
#   prices a bill, because it does not (step 5 has not been started).
# ──────────────────────────────────────────────────────────

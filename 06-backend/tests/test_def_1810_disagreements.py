# ── Trace ──────────────────────────────────────────────
# Defects: DEF-438 (root) · DEF-1810 (R3's size refusal was unreachable through
#          any real adapter — CLOSED 2026-08-28 by BR-RAT-120; this file now
#          pins the refusal, and the superseded $8.00/$8.00 assertion is kept
#          visible inside the case) · DEF-1811 (the shadow cannot run on ANY real
#          account) · DEF-1812 (no multiplier crosses metering's billing seam) ·
#          DEF-1813 (no asset count crosses it either) · DEF-514 · DEF-494 ·
#          DEF-498 · DEF-493
# Rules:   BR-RAT-081 · BR-RAT-088 · BR-RAT-090 · BR-MET-056 · BR-RAT-001
# Tests:   this file
# ───────────────────────────────────────────────────────
"""STEP 3 — THE DISAGREEMENTS, MEASURED THROUGH THE PRODUCTION ADAPTER.

⚠ **THIS FILE IS THE DELIVERABLE, NOT SCAFFOLDING ON THE WAY TO A SWITCH.**
Decision log 2026-08-27: *"STEP 3 IS THE DELIVERABLE, NOT A PHASE TO GET
THROUGH … A lane that makes the disagreements go away has destroyed the evidence
this job exists to produce."* Every assertion below RECORDS a difference with
both figures and chooses neither.

WHY THESE ARE NEW, GIVEN `tests/test_def_438_parity.py` ALREADY EXISTS
----------------------------------------------------------------------
That harness compares the two paths with the hard facts passed in as TEST
ARGUMENTS — `_price_chain(account, sizes={"water": "5/8"}, multipliers=…)`. It
had to: there was no adapter, so the facts had to come from somewhere, and the
author supplied them.

**Supplying them is what hid these four.** Every finding here is about a fact
the PRODUCT cannot supply, and a test that hands the fact over cannot see that.
This is DEF-498's own escape reason one level up: *"a hand-built code always
states an amount because the author is thinking about the case under test."*
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import resolution_shadow
from apps.rating import resolution, resolution_catalogue

from tests.test_def_438_parity import (
    SERVICE_DATE,
    _account_on,
    _price_live,
    _water_plan,
    price_water_base_by_size,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_def_1810_resolution_shadow import shadowing_only
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def test_DEF_1811_the_shadow_cannot_run_on_a_single_real_account(brazos, dana):
    """⚠ **THE HEADLINE. THE CHAIN CANNOT BE RUN ON ANY ACCOUNT OF ANY TENANT.**

    Not "the chain disagrees" and not "the chain refuses" — **the adapter cannot
    assemble its inputs at all**, on 1 of 1 accounts here and, by the same
    mechanism, on every account of every tenant.

⚠ **THE HEADLINE MOVED ON 2026-08-27 AND THIS CASE DID NOT — READ THE
    DIFFERENCE BEFORE CONCLUDING ANYTHING FROM IT.** As filed, the account here
    could not be attempted because **the product stored a connection size on no
    table at all** (DEF-514: no column on `assets.Asset`, none on
    `metering.ServicePoint`, none on `metering.Unit`; DEF-255 checked
    `information_schema` for `%size_class%` and found nothing). BR-AST-500 added
    `assets.size_class` and BR-MET-500 published it as
    `metering.connection_size_for`, so an account whose meter HAS a recorded
    size is now attempted — proved on this same fixture in
    `tests/test_def_1900_connection_size.py::test_TC6_the_shadow_can_now_be_run_on_a_real_account`
    (`attempted 1 · blocked {}`).

    **This fixture records no size, so it is still not attempted, and the
    assertions below are unchanged and still correct.** What changed is WHY:
    `connection_size_unresolved` used to mean *"this product cannot hold the
    fact"* and now means *"nobody has typed it in for this meter"* — a data
    state a human can fix. The case is kept because the second meaning still
    has to block: an account with no recorded size must never be priced off a
    guessed one.

    The mechanical detail, unchanged: `MeterFacts.connection_size` is typed
    `str` and R3 narrows on it, so an unresolved size stops the adapter.

    **This reframes DEF-438.** The register says the chain has no production
    caller. It is worse than that: a caller could not be written today even if
    someone wanted one, because a required input to R3 does not exist as data.
    Wiring the chain is therefore blocked on a METERING column, not on billing
    work — which is a different team, a different module and a different order
    of work from what the execution sequence assumes.

    ⚠ **AND IT IS WHY THE SCREEN HALF OF STEP 3 IS NOT BUILT.** The recorded
    acceptance test wants S31.2 to show *"the ruled path and the live path
    disagree on 14 of 1,247 accounts"* and warns that **a count that is always
    zero means the chain is not running**. Today that count is always zero and
    the chain is not running — so shipping the panel now would ship the exact
    reading the decision log says to distrust, with nothing to distinguish it
    from a wiring fault.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        # ⚠ **`size_class=None` IS STATED FROM 2026-09-01, AND THIS CASE'S OWN
        # DOCSTRING IS WHAT SETTLES IT (`DEF-2965`).** It says, in terms: *"This
        # fixture records no size, so it is still not attempted, and the
        # assertions below are unchanged and still correct."* That was a
        # statement about `_account_on`'s DEFAULT, and on 2026-09-01 the default
        # became the service's smallest ratified band — because an unsized meter
        # on a banded service stops its bill under R3 and a fixture may not hand
        # one out by accident. The account was then attempted and the case read
        # `assert 'agreed' == 'not_attempted'`.
        #
        # Fourth occurrence in one wave of `DEF-2817`'s shape: the INTENT was
        # written down, in prose, and the CODE inherited a default. The prose was
        # right; it is now the code as well.
        account, _unit, _asset, _delta = _account_on(
            brazos, dana, plan, size_class=None
        )
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
        report = resolution_shadow.summarise((outcome,))

        assert outcome.status == resolution_shadow.STATUS_NOT_ATTEMPTED
        assert outcome.blocked_reason == resolution_shadow.MISSING_CONNECTION_SIZE
        # The worked figure, in the shape the screen would show it.
        assert report == {
            "accounts": 1,
            "attempted": 0,
            "agreed": 0,
            "disagreed": 0,
            "chain_refused": 0,
            "not_attempted": 1,
            "by_step": {},
            "blocked_by_reason": {resolution_shadow.MISSING_CONNECTION_SIZE: 1},
        }, report
        # ⚠ 0 disagreed and 0 attempted. The first number alone reads as PARITY.
        assert report["disagreed"] == 0 and report["attempted"] == 0


def test_DEF_1812_no_meter_multiplier_crosses_metering_s_BILLING_seam(brazos, dana):
    """R3b cannot be run from production data, and the reason is a missing KEY.

⚠ **FIXED 2026-08-27 BY BR-MET-500 — THIS CASE NOW PINS THE FIX AND ITS
    ORIGINAL WORDING IS KEPT BELOW BECAUSE THE REASONING IS WHY THE OBVIOUS FIX
    WAS REFUSED.**

    As filed: `apps.metering.selectors.billing_reads_for_unit` is the seam the
    bill run reads, and it published `consumption`, `unit`, `prior_value`,
    `current_value`, `read_id`, `windows` and `demand` — **and no
    `multiplier`.** The figure existed on the read row (BR-MET-056 stores the
    factor USED) and `read_dict` and `read_analysis_for_unit` both published it;
    the one seam billing read did not. The fix was one key off the row already
    in hand — no new query, no new join, no second definition of the factor.

    The live path does not need it — metering hands billing a consumption that
    is ALREADY post-multiplier. The chain does need it, because
    `billable_quantity` scales the register difference itself (BR-RAT-001).
    **So this is not a bug in either path. It is the seam between them, shaped
    for one consumer and now needed by two.**

    ⚠ The tempting fix is a default of 1, and it is the worst option available:
    ×1 of the register difference equals metering's stored figure exactly when
    the multiplier really is 1, so R3b would report **parity by construction**
    on every account and the report would read as the best possible news.
    """
    with tenant_ctx(brazos):
        from apps.metering import selectors as metering_selectors

        plan = _water_plan(brazos)
        account, _unit, _asset, _delta = _account_on(
            brazos, dana, plan, multiplier="10"
        )
        rows = metering_selectors.billing_reads_for_unit(
            account.unit_id, period_start=data_period()[0], period_end=data_period()[1]
        )
        assert rows, "fixture sanity: the unit has a read"
        # ⚠ **THIS ASSERTION IS THE INVERSE OF THE ONE IT REPLACES, AND THAT IS
        # THE FIX LANDING.** Until 2026-08-27 it read `"multiplier" not in
        # rows[0]` with the message *"DEF-1812 is fixed and this test should
        # become the parity assertion it was blocking"*. BR-MET-500 landed the
        # key; this is that parity assertion.
        assert "multiplier" in rows[0], (
            "billing's read seam has LOST the multiplier again — DEF-1812 has "
            "regressed and the R1-R7 shadow cannot be run on real data"
        )
        # The duplication the module docstring warns about, now visible on ONE
        # row so a caller can choose: the live path prices the 500, the chain
        # scales the 50 itself (BR-RAT-001).
        assert rows[0]["consumption"] == Decimal("500.000000")
        assert Decimal(str(rows[0]["current_value"])) - Decimal(
            str(rows[0]["prior_value"])
        ) == Decimal("50")
        assert Decimal(str(rows[0]["multiplier"])) == Decimal("10")
        # ⚠ AND IT IS THE STORED FACTOR, NOT A DEFAULT. The whole reason
        # DEF-1812 refused the obvious fix is that a defaulted 1 reports parity
        # by construction; a factor that does not EXPLAIN the published product
        # is that default wearing the right name.
        assert Decimal(str(rows[0]["multiplier"])) * (
            Decimal(str(rows[0]["current_value"]))
            - Decimal(str(rows[0]["prior_value"]))
        ) == rows[0]["consumption"]


def data_period():
    from tests.test_def_438_parity import PERIOD_END, PERIOD_START

    return PERIOD_START, PERIOD_END


def test_DEF_1810_R3s_size_refusal_now_fires_and_names_the_size(brazos, dana):
    """⚠ **CLOSED 2026-08-28 BY THE PO's RULING. THIS CASE IS NOW ITS INVERSE.**

    ⚠ **THE SUPERSEDED ASSERTION IS KEPT VISIBLE, NOT DELETED**, because the
    figure it pinned is the whole reason the ruling exists. As filed, this test
    asserted:

        assert "3-inch" in water_invented.size_rows
        assert resolve_size_row(water_invented, MeterFacts("water", "3-inch"))
            == resolve_size_row(water_configured, MeterFacts("water", "5/8"))
        # "the two sizes resolve to the SAME base — R3 narrowed on nothing"

    **Worked, on this same tenant and this same plan: $8.00 and $8.00.** A
    3-inch connection — a size the utility never priced — resolved the 5/8 rate,
    because `resolution_catalogue.schedule_version_facts` built `size_rows` as
    ``served_sizes | size_classes_for(version)`` and `served_sizes` came from
    the CALLER. The size R3 looked up was, by construction, one the catalogue
    had just been told to serve, so R3's *"this size is not served"* refusal was
    dead code.

    **PO ruling 2026-08-28, verbatim: *"we need to charge account based on
    connection size they have"*** (`BR-RAT-120`, which CONFIRMS `BR-RAT-088`'s
    refusal clause rather than making a new rule). `served_sizes` is now what
    the TENANT HAS CONFIGURED on the schedule version, the keyword is REMOVED
    from `build_catalogue`, and a size that is not configured refuses BY NAME
    and never falls back to another size's rate.

    ⚠ **NO BILL CHANGES BY THIS COMMIT.** The chain still has no production
    caller and the shadow only observes. The order is fixed by the same ruling:
    load the connection sizes first, switch the chain in after — switching first
    would refuse every bill on every tenant, because not one meter carries a
    size yet.

    The blank-base refusal below is UNCHANGED and still correct: it is CR-013
    part 1's *"blank base = size not served"* (DEF-277) and it is a statement
    about the VERSION, not about the size. There are now two reachable R3
    refusals where there was one.
    """
    with tenant_ctx(brazos):
        plan = _water_plan(brazos)
        _account, _unit, _asset, _delta = _account_on(brazos, dana, plan)

        catalogue = resolution_catalogue.build_catalogue(
            plan_id=plan.id,
            service_date=SERVICE_DATE,
            # R7's narrowing facts, REQUIRED since `DEF-2824`. This case is
            # about the SIZE axis and asks about no tax; they are stated so the
            # `TypeError` below is about `served_sizes` and nothing else.
            account=resolution.AccountFacts(account_no="", unit_id=""),
            premises=resolution.PremisesFacts(),
        )
        water = next(v for v in catalogue.schedule_versions if v.service == "water")

        # The size the tenant CONFIGURED still prices, and still at $8.00.
        assert resolution.resolve_size_row(
            water, resolution.MeterFacts("water", "5/8")
        ) == Decimal("8.00")

        # ⚠ THE INVERSE OF THE SUPERSEDED ASSERTION. A size nobody configured is
        # not on the axis and cannot be put there by asking.
        assert "3-inch" not in water.size_rows
        with pytest.raises(resolution.SizeNotServed) as refusal:
            resolution.resolve_size_row(
                water, resolution.MeterFacts("water", "3-inch")
            )
        assert "3-inch" in str(refusal.value), str(refusal.value)

        # And the mechanism that produced the defect is now unwritable: the
        # caller cannot hand the catalogue a size at all.
        with pytest.raises(TypeError):
            resolution_catalogue.build_catalogue(
                plan_id=plan.id,
                service_date=SERVICE_DATE,
                account=resolution.AccountFacts(account_no="", unit_id=""),
                premises=resolution.PremisesFacts(),
                served_sizes=("3-inch",),  # type: ignore[call-arg]
            )

        # The blank-base refusal — unchanged, and about the VERSION not the size.
        with pytest.raises(resolution.SizeNotServed) as blank:
            resolution.resolve_size_row(
                resolution.ScheduleVersion(
                    version_id="v1",
                    service="water",
                    effective_from=SERVICE_DATE,
                    size_rows={"5/8": None},
                ),
                resolution.MeterFacts("water", "5/8"),
            )
        assert "BLANK base charge" in str(blank.value)


def test_DEF_1813_the_asset_count_now_crosses_the_billing_seam(brazos, dana):
    """**THIS PIN FIRED, AND IT IS NOW THE RE-PROOF IT ASKED FOR (2026-08-28).**

    It read `assert not hasattr(metering_selectors, "billable_asset_count")`,
    with the message *"metering has GAINED a billable asset count — DEF-1813 is
    fixed and the unmetered half of R3b can now be shadowed"*. It has, so the
    assertion is inverted rather than deleted: an absence pin that fires has
    done its whole job, and turning it into the positive statement is what stops
    the gap re-opening silently. Same treatment DEF-484's size pin got.

    BR-RAT-090: a service declared unmetered (BR-RAT-081) bills a COUNT OF ITS
    ASSETS on the unit — **three carts × $15.00 = $45.00, ratified; remove one
    and the next bill is $30.00.** The count is OBSERVED, and
    `AssetCountUnavailable` refuses an ABSENT one rather than reading it as
    zero, because *"nobody looked"* and *"this unit has none"* are different
    facts and only one of them bills nothing.

    The end-to-end money is `tests/test_def_1813_unmetered_count.py`. What this
    case keeps is the SEAM's existence and its absent branch, in the file that
    measured the gap.
    """
    assert resolution_shadow.MISSING_ASSET_COUNT == (
        "unmetered_asset_count_not_published_to_billing"
    )
    from apps.metering import selectors as metering_selectors

    assert callable(getattr(metering_selectors, "billable_asset_count", None)), (
        "metering has LOST its billable asset count — DEF-1813 has re-opened and "
        "every unmetered service is unbillable by count again"
    )
    # ⚠ The absent branch is the half that matters: a unit with no service point
    # for the service answers None — *nobody looked* — and never 0, which would
    # be a claim that the utility looked and found no carts.
    with tenant_ctx(brazos):
        assert (
            metering_selectors.billable_asset_count(
                "00000000-0000-0000-0000-000000000000", "trash", date(2026, 8, 31)
            )
            is None
        )


def test_the_four_blockers_are_reported_separately_and_not_summed(brazos, dana):
    """Four different facts, four different owners, four different fixes.

    A single "cannot run" count would have sent one lane to fix "the adapter".
    The size is a metering COLUMN (DEF-514), the multiplier is a metering SEAM
    KEY (DEF-1812), the asset count is a metering SEAM (DEF-1813) and the plan
    is a customer configuration. Only the last is billing's.
    """
    reasons = {
        resolution_shadow.MISSING_CONNECTION_SIZE,
        resolution_shadow.MISSING_MULTIPLIER,
        resolution_shadow.MISSING_ASSET_COUNT,
        resolution_shadow.MISSING_PLAN,
    }
    assert len(reasons) == 4, "two blockers have collapsed into one string"


# ── Lifecycle ─────────────────────────────────────────────
# status: PROPOSED — a MEASUREMENT file. Every test here records a difference
#   and none of them fixes one, on purpose (decision log 2026-08-27).
# ──────────────────────────────────────────────────────────

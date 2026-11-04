# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5255 — bill-run step 1 draws two inputs where the blueprint
#          draws five groups; SCOPE and WHAT THIS COVERS do not exist, so a
#          run is all-or-nothing on a cycle and a 40,000-account utility has no
#          way to bill a subset (DEF-BIL-4224).
#          DEF-BIL-5258 — every chip on the Check screen is `.length` of an
#          array the browser was sent, over an unpaginated findings read that
#          costs 66,053 SQL statements at 1,000 accounts.
#          DEF-BIL-5283 — the run's idempotency key omits the service scope, so
#          a scoped run consumes the key for the whole cycle-period and the
#          rest is refused as a duplicate with no exclusion row written.
# Rules:   BR-BIL-005 (a run is unique on tenant + cycle + period — the key this
#          work must not widen behind) · BR-BIL-015 (a missing input is a
#          CHOICE, and an unreachable seam is REFUSED rather than guessed) ·
#          BR-BIL-040 (a finding sits on the tab that owns its stage) ·
#          BR-MET-121 (the cycle's own expected span, derived) ·
#          BR-TEN-043 (*today* belongs to the tenant, never to this process) ·
#          B14 rule 16 (a pagination footer on every list table) · B14 rule 37
#          (a figure drawn in a wireframe is an ILLUSTRATION)
# Tests:   this file
# Impacts: apps/billing/selectors.py · apps/billing/api.py
# ───────────────────────────────────────────────────────
"""The three reads screen 16 and screen 17 are built on, proved as NUMBERS.

⚠ **EVERY ASSERTION HERE IS A COUNT OR A NAMED ABSENCE, NEVER A STATE.** These
surfaces fail silently by construction: a scope that quietly widened, a chip
that counted a page instead of a population, an age band computed from a
guessed thirty days — not one of them raises, logs or moves a gate. So each
case below pins the figure, and the two that matter most pin an INEQUALITY and
a REFUSAL rather than a value.

⚠ **`tc6` IS THE COUNTER-INTUITIVE ONE AND IT ASSERTS STRICTLY GREATER.** A
chip is an ACTION, so an account needing two actions appears in two chips and
the tags under a band sum to MORE than the band. A test that pinned equality
there would pass on today's data and enforce the wrong rule for ever
(`DEF-BIL-5273`); a tag row summing exactly to its band has been misread.

⚠ **AND `tc3` PINS A REFUSAL WE COULD HAVE SHIPPED WITHOUT.** The scope card
answers `committable: False` for every narrowed scope because the run key does
not carry the scope. Take that assertion out and the screen becomes a dropdown
over a revenue hole: the Water run consumes September, the Sewer run is refused
as a duplicate, no exclusion row is written, so those accounts never reach the
held queue and no catch-up ever bills them.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import selectors
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_004_run_loop import a_planless_unit, a_run

pytestmark = pytest.mark.django_db

#: The day every age band below is measured against. A CONSTANT IN THE TEST,
#: never `date.today()`: BR-TEN-043 puts *today* in the tenant's hands, and a
#: suite that read the process clock would change its own answers at midnight.
AS_OF = date(2026, 7, 15)


def a_hold(tenant, run, account, *, days_ago: int, as_of: date = AS_OF):
    """One UNRESOLVED exclusion, aged by writing its `created_at` backwards.

    `auto_now_add` fills the column on insert, so the age is set by an UPDATE
    afterwards — the only way to build a queue with a history in a test that
    has no clock to wind.
    """
    row = billing_models.BillRunExclusion.objects.create(
        tenant=tenant,
        bill_run=run,
        account=account,
        reason_code="staff_hold_missing_read",
    )
    billing_models.BillRunExclusion.objects.filter(pk=row.pk).update(
        created_at=datetime.combine(
            as_of - timedelta(days=days_ago), datetime.min.time(), tzinfo=timezone.utc
        )
    )
    return row


def a_stageless_break(actor, tenant, cycle, plan, *, label):
    """A unit that breaks with a reason carrying NO STAGE.

    A stage of None is a real answer, not a gap — some problems are facts about
    the run's shape rather than stage failures (BR-BIL-040) — and it is the only
    fixture that can tell *where the fix is* counting its own tags from *where
    the fix is* counting every blocked account.
    """
    from apps.metering import services as metering_services

    premises = make_premises(actor, address_line=f"{label} Stageless Row")
    unit = make_unit(actor, premises["id"], label=label, services=["electric", "water"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    return unit


def a_dated_run(tenant, cycle, *, key):
    """A run carrying its own BILL DATE.

    `prepared_for` refuses a run with neither a typed bill date nor a cycle
    bill day, and refusing is the point (BR-RAT-007 prices on the service date,
    so a guessed one silently selects a different tariff version). The fixture
    types one, which is what a clerk does on step 1.
    """
    run = a_run(tenant, cycle, key=key)
    billing_models.BillRun.objects.filter(pk=run.pk).update(bill_date=PERIOD_END)
    run.refresh_from_db()
    return run


def tag(counts, tag_id):
    for row in counts["tags"]:
        if row["id"] == tag_id:
            return row
    return None


def band(counts, band_id):
    for row in counts["bands"]:
        if row["id"] == band_id:
            return row
    raise AssertionError(f"no band {band_id}")


def absence(payload, code):
    for row in payload["unavailable"]:
        if row["code"] == code:
            return row
    return None


# ══════════════════════════════════════════════════════════════════════════
# CONTRACT 1 — the scope resolver (blueprint screen 16, group SCOPE)
# ══════════════════════════════════════════════════════════════════════════


def test_tc1__the_whole_cycle_resolves_to_its_own_population(brazos, dana):
    """Two unit numbers and an account number, all three COUNTS.

    The card draws *units in the cycle* and *accounts to bill* side by side
    because they are different numbers and the gap between them is where every
    master-account failure lives. Here they agree — one account per unit — and
    the test says so with figures rather than asserting they are "consistent".
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        for n in (1, 2, 3):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-525{n}", label=f"U{n}")
            an_account(brazos, unit["id"], f"A-525{n}")

        card = selectors.scope_resolution(cycle_id=str(cycle.id))

        assert card["counts"]["units_in_cycle"] == 3
        assert card["counts"]["units_in_scope"] == 3
        assert card["counts"]["accounts_to_bill"] == 3
        assert card["counts"]["master_accounts"] == 0
        # NOT A ZERO. A zero here would be a claim that this cycle has no
        # meters; the figure needs a bulk assets read that does not exist.
        assert card["counts"]["meters_this_cycle"] is None
        assert card["counts"]["points_with_no_meter"] is None
        assert absence(card, "meter_counts_not_available_here") is not None
        # No money anywhere on the card — the drawing's own note.
        assert "amount" not in card["counts"]
        assert "total" not in card["counts"]


def test_tc2__no_money_and_no_forecast_reaches_the_card(brazos, dana):
    """The drawing's note, asserted structurally rather than by eye.

    Resolving a scope for real costs the measured 137 ms per account, so a card
    that previewed money would pay for the whole run to draw a header — 40,000
    accounts is about ninety minutes. The rule is enforced here by walking the
    served payload for anything money-shaped.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5254", label="U1")
        an_account(brazos, unit["id"], "A-5254")

        card = selectors.scope_resolution(cycle_id=str(cycle.id))

        money_shaped = {"amount", "total", "currency", "value", "at_stake", "would_bill"}
        for key, value in card["counts"].items():
            assert key not in money_shaped, key
            assert not isinstance(value, Decimal), key


def test_tc3__a_narrowed_scope_is_not_committable_and_says_why(brazos, dana):
    """`DEF-BIL-5283`, pinned. **Delete this and the screen becomes a trap.**

    A run narrowed to a route consumes the cycle-period key, so the second
    scoped run over that period is refused as a duplicate — and because it is
    refused rather than excluded, no exclusion row is written, those accounts
    never enter the held queue, and no catch-up ever bills them. The resolver
    may SHOW such a scope; it may not call one committable.

    ⚠ **AMENDED 2026-09-14 — THE SERVICE HALF OF `DEF-BIL-5283` IS FIXED AND
    THE OTHER THREE KINDS ARE NOT.** `bill_run_key` now appends `|scope|<codes>`
    under BR-BIL-005's signed *"key = parent key + scope"*, so a SERVICE scope
    is keyed and is committable. A route, an area and a named set still are not,
    and the reason is a COLUMN rather than a key: `bill_runs` persists nothing
    for them. **This case now asserts BOTH sides**, because a version that
    checked only the service would have gone green over a flag flipped for all
    four — and the service case, the one anybody would test, bills correctly
    either way.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5255", label="U1")
        an_account(brazos, unit["id"], "A-5255")

        whole = selectors.scope_resolution(cycle_id=str(cycle.id))
        by_service = selectors.scope_resolution(cycle_id=str(cycle.id), scope_services=["electric"])
        scoped = selectors.scope_resolution(
            cycle_id=str(cycle.id), kind=selectors.SCOPE_ROUTE, scope_ids=[str(cycle.id)]
        )

        assert whole["committable"] is True
        # ⚠ AMENDED 2026-09-30 (bulk bill run plan B3): the services filter is
        # removed and `create_run` takes no services, so a service narrowing is
        # no longer committable. It carries no route refusal, because it is not
        # a route.
        assert by_service["committable"] is False
        assert absence(by_service, selectors.SCOPE_KEY_LIMIT) is None
        # NOT keyable — no column persists a route — so still refused.
        assert scoped["committable"] is False
        refusal = absence(scoped, selectors.SCOPE_KEY_LIMIT)
        assert refusal is not None
        # Clerk-facing, and carrying no route, rule id or defect id (CR-016).
        assert "BR-" not in refusal["detail"]
        assert "DEF-" not in refusal["detail"]
        assert "/billing" not in refusal["detail"]


def test_tc4__a_route_scope_narrows_and_never_widens(brazos, dana):
    """The cycle is the ceiling; a scope can only take rows away.

    A route may hold a unit this cycle does not bill — a route serves reads and
    a cycle serves bills, and the two are allowed to diverge. Resolving
    route-first would put such a unit into a run the cycle never covered, which
    is a bill nobody asked for, so the resolver intersects.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        for n in (1, 2):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-526{n}", label=f"U{n}")
            an_account(brazos, unit["id"], f"A-526{n}")

        # A route with no members at all: the intersection is empty, and the
        # cycle's own count is unchanged beside it.
        card = selectors.scope_resolution(
            cycle_id=str(cycle.id),
            kind=selectors.SCOPE_ROUTE,
            scope_ids=["00000000-0000-0000-0000-000000000000"],
        )

        assert card["counts"]["units_in_cycle"] == 2
        assert card["counts"]["units_in_scope"] == 0
        assert card["counts"]["accounts_to_bill"] == 0
        assert card["committable"] is False


def test_tc5__a_named_set_says_it_does_not_exist(brazos, dana):
    """Drawn on the screen, modelled nowhere.

    Answering the cycle's own units silently would be a widening; answering
    none would read as *"that named set has nobody in it"*. So the population
    is unchanged and the surface says the narrowing did not happen.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5265", label="U1")
        an_account(brazos, unit["id"], "A-5265")

        card = selectors.scope_resolution(
            cycle_id=str(cycle.id), kind=selectors.SCOPE_NAMED_SET, scope_ids=["anything"]
        )

        assert card["counts"]["units_in_scope"] == 1
        assert absence(card, "named_sets_do_not_exist") is not None
        assert card["committable"] is False


# ══════════════════════════════════════════════════════════════════════════
# CONTRACT 2 — the streaming counts (blueprint screen 17, layers L2 and L3)
# ══════════════════════════════════════════════════════════════════════════


def test_tc6__tags_count_cases_and_bands_count_accounts(brazos, dana):
    """**THE ARITHMETIC RULE, AND IT ASSERTS STRICTLY GREATER.**

    A chip is an ACTION. One account carrying two unanswered questions has two
    actions waiting on it and appears in two chips, so the tags under a band
    sum to MORE than the band — *"twelve accounts raise nineteen case rows"*.
    The band stays ACCOUNTS because the band is what ties to the cycle: nobody
    is missing.

    Built here as one account with a missing read on two services, which is two
    cases and one account.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        broken = a_planless_unit(dana, brazos, cycle, asset_no="M-5266", label="U1")
        account = an_account(brazos, broken["id"], "A-5266")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc6")
        # ONE account, TWO actions: it broke at stage 1 AND a clerk has already
        # held it. Both chips are true of it and both have to be dealt with, so
        # it appears in both — which is the whole rule, and which the drawn
        # frames happen never to show because neither of them has an account in
        # two chips of one band.
        a_hold(brazos, run, account, days_ago=3)

        counts = selectors.finding_counts(run, as_of=AS_OF)

        held = band(counts, selectors.BAND_HELD)
        tag_cases = sum(
            row["cases"] for row in counts["tags"] if row["band"] == selectors.BAND_HELD
        )
        assert held["accounts"] == 1
        assert tag(counts, selectors.TAG_NEVER_CALCULATED)["cases"] == 1
        assert tag(counts, selectors.TAG_CALCULATED_AND_BROKE)["cases"] == 1
        assert tag_cases == 2
        # STRICTLY GREATER. Pinning equality here would pass today and enforce
        # the wrong rule for ever.
        assert tag_cases > held["accounts"], (tag_cases, held["accounts"])


def test_tc7__the_four_populations_reconcile_by_construction(brazos, dana):
    """*"All 1,284 accounts in the cycle are accounted for."* — generated.

    The screen's reconciling sentence is composed from these four numbers, not
    typed, which is what `DEF-BIL-5280` costs when it is not: one frame said
    *"21 held by your defaults, 0 broke"* while its own KPI said *"15 by a
    default · 6 blocked"*.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        clean = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5270", label="U1")
        an_account(brazos, clean["id"], "A-5270")
        broken = a_planless_unit(dana, brazos, cycle, asset_no="M-5271", label="U2")
        an_account(brazos, broken["id"], "A-5271")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc7")

        counts = selectors.finding_counts(run, as_of=AS_OF)
        rec = counts["reconciliation"]

        assert rec["ready"] + rec["needs_you"] + rec["held"] + rec["nothing_to_bill"] == (
            rec["accounts_in_scope"]
        )
        assert rec["accounts_in_scope"] == 2
        assert counts["kpi"]["held"]["calculated_and_broke"] == 1
        # PHASE 1 COMPUTES NO MONEY AT ALL — null under its contracted name,
        # never a Σ of zero, which would be a claim about revenue.
        assert counts["kpi"]["run_total"]["amount"] is None
        assert counts["kpi"]["ready_to_bill"]["amount"] is None


def test_tc8__the_waiting_bands_derive_from_the_cycles_frequency(brazos, dana):
    """**NOT 14 AND 60.** Those are drawn figures, and a drawn figure is an
    illustration (B14 rule 37).

    One cycle length escalates and two is a long wait, so a MONTHLY cycle over
    1–30 June answers **30 and 60** and a FORTNIGHTLY one answers **14 and 28**.
    A fixed fourteen would escalate a quarterly cycle's whole queue before its
    first bill was even due.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        metering_models.Cycle.objects.filter(pk=cycle.id).update(frequency="monthly")
        cycle.refresh_from_db()
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc8")

        bands = selectors.waiting_bands_for(run)
        assert bands["period_days"] == 30
        assert bands["escalate_after_days"] == 30
        assert bands["long_wait_after_days"] == 60
        assert bands["source"] == "derived_from_cycle_frequency"

        metering_models.Cycle.objects.filter(pk=cycle.id).update(frequency="fortnightly")
        run.refresh_from_db()
        fortnightly = selectors.waiting_bands_for(run)
        assert fortnightly["period_days"] == 14
        assert fortnightly["escalate_after_days"] == 14
        assert fortnightly["long_wait_after_days"] == 28


def test_tc9__no_frequency_means_no_age_tags_at_all(brazos, dana):
    """A cycle with no frequency has no period to take a multiple of.

    The honest answer is no age tags and a named absence. Guessing thirty days
    would band a quarterly cycle's queue wrong every single period — the same
    failure `BR-MET-121` was written to close one layer down.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)  # no frequency
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5280", label="U1")
        account = an_account(brazos, unit["id"], "A-5280")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc9")
        a_hold(brazos, run, account, days_ago=40)

        counts = selectors.finding_counts(run, as_of=AS_OF)

        assert tag(counts, selectors.TAG_WAITING_UNDER) is None
        assert tag(counts, selectors.TAG_WAITING_ESCALATED) is None
        assert absence(counts, "waiting_bands_not_derivable") is not None
        assert band(counts, selectors.BAND_HOW_LONG)["accounts"] == 0


def test_tc10__a_hold_is_aged_from_the_oldest_unresolved_row(brazos, dana):
    """An account held month after month has waited since the FIRST month.

    Reading only this run's own row would report it as new every cycle, which
    is precisely how an account held repeatedly stops looking urgent — *"the
    thing that quietly loses revenue"*.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        metering_models.Cycle.objects.filter(pk=cycle.id).update(frequency="monthly")
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5290", label="U1")
        account = an_account(brazos, unit["id"], "A-5290")
        old_run = a_run(brazos, cycle, key="2026-05|counts-tc10-old")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc10")
        a_hold(brazos, old_run, account, days_ago=71)
        a_hold(brazos, run, account, days_ago=3)

        counts = selectors.finding_counts(run, as_of=AS_OF)

        # 71 days against a 30/60 pair: the long-wait tag, not the under one.
        assert tag(counts, selectors.TAG_WAITING_LONG)["cases"] == 1
        assert tag(counts, selectors.TAG_WAITING_UNDER)["cases"] == 0
        assert band(counts, selectors.BAND_HELD)["accounts"] == 1


def test_tc11__a_cross_cycle_hold_is_counted_and_never_banded(brazos, dana):
    """**AN OPEN QUESTION, LEFT OPEN.**

    An account held from one cycle and appearing in a run over another has two
    candidate band sets — the cycle it was held from, and the cycle being run.
    Which governs has not been ruled. Banding it either way would answer that
    question silently, so it is counted on its own and named; passing the
    parameter is what bands it, and that is one argument away for the day the
    ruling lands.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        other = a_cycle(brazos, code="05-A")
        metering_models.Cycle.objects.filter(pk=cycle.id).update(frequency="monthly")
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5300", label="U1")
        account = an_account(brazos, unit["id"], "A-5300")
        elsewhere = a_run(brazos, other, key="2026-05|counts-tc11-other")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc11")
        # Held again here — which is how it reaches THIS run's queue at all —
        # and the OLDEST unresolved hold is the one from the other cycle.
        a_hold(brazos, elsewhere, account, days_ago=71)
        a_hold(brazos, run, account, days_ago=3)

        unruled = selectors.finding_counts(run, as_of=AS_OF)
        assert unruled["waiting"]["cross_cycle_unsettled"] == 1
        assert unruled["waiting"]["banded"] == 0
        assert absence(unruled, "held_across_cycles_not_grouped") is not None

        ruled = selectors.finding_counts(
            run, as_of=AS_OF, age_bands_from=selectors.AGE_BANDS_FROM_RUN_CYCLE
        )
        assert ruled["waiting"]["cross_cycle_unsettled"] == 0
        assert tag(ruled, selectors.TAG_WAITING_LONG)["cases"] == 1


def test_tc12__in_arrears_is_not_folded_into_the_findings_pass(brazos, dana):
    """*In arrears* is a fact about an ACCOUNT, not about this run.

    It is a balance read at a date the clerk chooses, from a different source
    and against a different clock, and folding it into the billing pass would
    give the run a number that moves when somebody pays. Declared, and absent,
    with the reason beside it.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5310", label="U1")
        an_account(brazos, unit["id"], "A-5310")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc12")

        counts = selectors.finding_counts(run, as_of=AS_OF)

        assert tag(counts, selectors.TAG_IN_ARREARS) is None
        assert absence(counts, "arrears_not_counted_here") is not None


def test_tc13__the_seven_bands_are_always_served_in_the_drawn_order(brazos, dana):
    """Seven bands, ordered by obligation — a clerk is finished when the first
    one is empty. The TAGS are generated (a case the engine did not raise gets
    no chip); the BANDS are the taxonomy and are always there, including at
    zero, so the strip does not change shape under a clerk mid-run."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5320", label="U1")
        an_account(brazos, unit["id"], "A-5320")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc13")

        counts = selectors.finding_counts(run, as_of=AS_OF)

        assert [row["id"] for row in counts["bands"]] == list(selectors.BAND_ORDER)
        assert len(counts["bands"]) == 7
        for row in counts["bands"]:
            if row["id"] in (
                selectors.BAND_WHERE_THE_FIX_IS,
                selectors.BAND_THE_REASON,
                selectors.BAND_HOW_LONG,
            ):
                assert row["partitions"] == selectors.BAND_HELD
            else:
                assert row["partitions"] is None


def test_tc16__no_band_ever_claims_an_account_its_tags_do_not_hold(brazos, dana):
    """**THE INVARIANT, ASSERTED OVER EVERY BAND — `sum(tags) >= band`.**

    ⚠ **THIS ONE FOUND A REAL BUG BEFORE IT WAS WRITTEN DOWN.** *Where the fix
    is* counted every blocked account, and a stage of None is a real answer —
    some problems are facts about the run's shape rather than stage failures.
    So a `ruled_path_refused` block gave a band of one over tags summing to
    zero: a band claiming work its own chips do not show, which is the
    direction that HIDES work from a clerk. The band now counts only the
    accounts its stages actually name.

    The other direction is lawful and is the rule (`tc6`): tags may sum to more.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        metering_models.Cycle.objects.filter(pk=cycle.id).update(frequency="monthly")
        plan = a_priced_plan(brazos)
        clean = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5330", label="U1")
        an_account(brazos, clean["id"], "A-5330")
        staged = a_planless_unit(dana, brazos, cycle, asset_no="M-5331", label="U2")
        held_account = an_account(brazos, staged["id"], "A-5331")
        # ⚠ **THE THIRD ACCOUNT IS THE WHOLE TEST AND THE FIRST DRAFT DID NOT
        # HAVE IT.** Without a block whose stage is NONE, `len(staged_ids)` and
        # `len(blocked_ids)` are the same number and this case passes with the
        # bug put back — proved by reverting the fix in a pinned worktree and
        # watching it stay green. A guard that cannot fail is worse than none.
        stageless = a_stageless_break(dana, brazos, cycle, plan, label="U3")
        an_account(brazos, stageless["id"], "A-5332")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc16")
        a_hold(brazos, run, held_account, days_ago=45)

        counts = selectors.finding_counts(run, as_of=AS_OF)

        # THE INVARIANT FIRST, so it is the assertion that fires.
        for row in counts["bands"]:
            summed = sum(
                entry["cases"] for entry in counts["tags"] if entry["band"] == row["id"]
            )
            assert summed >= row["accounts"], (row["id"], summed, row["accounts"])

        # And the fixture really does hold a stage-less block — asserted so this
        # case cannot quietly lose its teeth if the engine re-homes a reason.
        assert band(counts, selectors.BAND_THE_REASON)["accounts"] == 2
        assert band(counts, selectors.BAND_WHERE_THE_FIX_IS)["accounts"] == 1


# ══════════════════════════════════════════════════════════════════════════
# CONTRACT 5 — the cycle-scoped runs read (blueprint screen 16, group E)
# ══════════════════════════════════════════════════════════════════════════


def test_tc14__the_runs_table_names_who_ran_it_and_whether_it_is_open(brazos, dana):
    """*"Dana Reyes has this cycle open. Take it over, or ask them to sign
    off."* — every fact in that sentence, served.

    The blueprint REMOVED the old *no actor column* panel as **ruled by fact**:
    `bill_runs.run_by` exists and is populated, and it was reaching a clerk on
    two refusals and on nothing they could read. `is_open` is NOT the stored
    status word, which never advances off *draft* and therefore cannot answer
    *is somebody in the middle of this*.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        run = a_dated_run(brazos, cycle, key="2026-06|runs-tc14")
        billing_models.BillRun.objects.filter(pk=run.pk).update(
            run_by=dana.user, label="September, after the water rate change"
        )

        rows = selectors.bill_runs_list(cycle_id=str(cycle.id))

        assert len(rows) == 1
        assert rows[0]["ran_by"] == str(dana.user.id)
        assert rows[0]["ran_by_name"] == dana.user.full_name
        assert rows[0]["is_open"] is True
        # The run's own name, which is what makes two runs over one period
        # distinguishable to anybody quoting them. Null where nobody typed one.
        assert rows[0]["label"] == "September, after the water rate change"


def test_tc15__the_runs_table_is_scoped_to_one_cycle(brazos, dana):
    """*Already run for this cycle* — this cycle, and not the utility's whole
    history. An unreadable id answers the EMPTY list rather than widening."""
    with tenant_ctx(brazos):
        mine = a_cycle(brazos)
        theirs = a_cycle(brazos, code="05-A")
        a_run(brazos, mine, key="2026-06|runs-tc15-a")
        a_run(brazos, theirs, key="2026-06|runs-tc15-b")

        assert len(selectors.bill_runs_list(cycle_id=str(mine.id))) == 1
        assert len(selectors.bill_runs_list(cycle_id="not-a-uuid")) == 0
        assert len(selectors.bill_runs_list()) == 2


# ══════════════════════════════════════════════════════════════════════════
# THE ROUTES ARE MOUNTED AND THE VIEWS ANSWER — hard-won law 2
# ══════════════════════════════════════════════════════════════════════════


def test_tc17__the_two_new_reads_are_actually_mounted(brazos):
    """Exporting `urlpatterns` is not an endpoint until the root URLconf
    includes it, and S31 shipped against exactly that gap. Resolved through the
    REAL root URLconf, so a lost include goes red here rather than in a
    browser."""
    import uuid as _uuid

    from django.urls import resolve

    from apps.billing import api as billing_api

    run_id = _uuid.uuid4()
    assert resolve("/api/brazosbend/billing/run-scope").func is billing_api.run_scope
    assert (
        resolve(f"/api/brazosbend/billing/runs/{run_id}/findings/counts").func
        is billing_api.run_finding_counts
    )


def test_tc18__the_scope_read_answers_over_the_wire(brazos, dana):
    """A view is not wired because it resolves — it has to answer. This one
    reads its cycle, its scope kind and its service narrowing off the QUERY
    STRING, which is where a route or an area chip will arrive from."""
    from apps.billing import api as billing_api
    from tests.test_us_ten_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5340", label="U1")
        an_account(brazos, unit["id"], "A-5340")

    whole = api_call(
        billing_api.run_scope,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"cycle_id": str(cycle.id)},
    )
    assert whole.status_code == 200
    assert whole.data["counts"]["accounts_to_bill"] == 1
    assert whole.data["committable"] is True

    scoped = api_call(
        billing_api.run_scope,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        query={"cycle_id": str(cycle.id), "f.service": "electric"},
    )
    assert scoped.status_code == 200
    assert scoped.data["scope"]["services"] == ["electric"]
    # ⚠ AMENDED 2026-09-30 (bulk bill run plan B3): the services filter is
    # removed and `create_run` takes no services, so the card may no longer
    # call a service narrowing committable.
    assert scoped.data["committable"] is False


def test_tc19__the_counts_read_refuses_without_a_day_to_measure_against(brazos, dana):
    """`as_of` is required and is never the server's clock.

    *Today* belongs to the tenant (BR-TEN-043 / gate G6): a queue whose ages
    came from this process would age by a day the moment somebody opened it
    from another timezone, and an escalation is a figure a clerk acts on.
    """
    from apps.billing import api as billing_api
    from core import errors
    from tests.test_us_ten_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5350", label="U1")
        an_account(brazos, unit["id"], "A-5350")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc19")

    refused = api_call(
        billing_api.run_finding_counts,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
    )
    # 422 — a well-formed request the server will not act on, which is this
    # product's shape for a validation refusal.
    assert refused.status_code == 422
    assert refused.data["code"] == errors.VAL_FORMAT

    answered = api_call(
        billing_api.run_finding_counts,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
        query={"as_of": AS_OF.isoformat()},
    )
    assert answered.status_code == 200
    assert len(answered.data["bands"]) == 7
    assert answered.data["as_of"] == AS_OF.isoformat()


def test_tc20__one_findings_list_pages_and_the_default_body_is_unchanged(brazos, dana):
    """B14 rule 16, opt-in.

    ⚠ **THE DEFAULT MUST STAY THE WHOLE BODY UNTIL THE SCREEN READS ITS
    NUMBERS FROM THE COUNTS ADDRESS.** Today every chip is `.length` of these
    lists, so paging them by default would turn `ready.length` into a page size
    and the screen would report fifty accounts in a run of ten thousand.
    """
    from apps.billing import api as billing_api
    from tests.test_us_ten_helpers import FakeUser, api_call

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        for n in (1, 2, 3):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-536{n}", label=f"U{n}")
            an_account(brazos, unit["id"], f"A-536{n}")
        run = a_dated_run(brazos, cycle, key="2026-06|counts-tc20")

    whole = api_call(
        billing_api.run_findings,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
    )
    assert len(whole.data["ready"]) == 3
    assert "results" not in whole.data

    # `per` clamps to the ONE page-size vocabulary — 1 is below the floor and
    # becomes 50, so three rows are one page. The envelope is the point.
    paged = api_call(
        billing_api.run_findings,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
        query={"list": "ready", "per": "1", "page": "9"},
    )
    assert paged.data["list"] == "ready"
    assert paged.data["count"] == 3
    assert paged.data["per"] == 50
    # BR-SHL-011 "never error": an out-of-range page CLAMPS rather than 404s.
    assert paged.data["page"] == 1
    assert len(paged.data["results"]) == 3
    # The list it paged is GONE from the body, so nothing can count a page as a
    # population by reading the old key.
    assert "ready" not in paged.data

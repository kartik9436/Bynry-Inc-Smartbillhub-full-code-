# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-5270 — a cycle run never checks that an account's
#          consumption starts where its last BILL ended. Metering answers a
#          PERIOD with a figure it stored as (current − prior) × multiplier,
#          and the anchor is the previous READ, not the read the last ISSUED
#          bill closed on. A skipped read, a re-read, a meter exchange or a
#          draft that was never issued puts the two out of step, and the
#          failure is money in both directions.
#          DEF-BIL-5271 — a decision records a choice and never re-prices, and
#          sign-off gates only on UNRESOLVED breaks, so a bulk decision over 44
#          accounts leaves 44 drafts at their pre-decision figures and walks
#          through the BR-BIL-053 gate.
# Rules:   BR-BIL-053 (a break's two ways out, and *"the run cannot enter phase
#          4 with an unresolved break row"* — extended here to decisions) ·
#          BR-BIL-015 (a missing input is a CHOICE) · BR-BIL-023 (stage 6
#          REPLACES this run's draft rather than adding one) · BR-BIL-039
#          (stages 1–5 are pure) · BR-BIL-004 (an issued bill is never
#          re-priced) · BR-CUS-103 (the first unbilled day is the day AFTER the
#          last issued period end — `cut_bill`'s anchor, reused)
# Tests:   this file
# Impacts: apps/billing/runs.py · apps/billing/decisions.py ·
#          apps/billing/release.py · apps/billing/api.py
# ───────────────────────────────────────────────────────
"""The two money-path checks a bill run did not have.

⚠ **BOTH OF THESE WERE SILENT, WHICH IS WHY EVERY EXISTING TEST PASSED OVER
THEM.** Nothing raised, nothing logged, no gate moved and no screen said
anything — a bill simply carried a figure derived from the wrong anchor, or
the figure it had before a clerk decided anything. That is the shape this
repository fails in, so each case below asserts a NUMBER rather than a state:
the days in the gap, the register position, the count of stale drafts.

⚠ **THE FIXTURES DELIBERATELY ISSUE A BILL.** An account with no issued bill
is the FIRST-BILL case and raises nothing — correct, and the reason `tc1`
exists: a check that fired on every new customer's first month would be turned
off inside a week.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.billing import decisions, models as billing_models, release, runs
from apps.billing.exceptions import BillingRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_004_run_loop import a_run, prepared_for

pytestmark = pytest.mark.django_db

#: The window an EARLIER bill covered. May, where the run under test is June —
#: so a bill issued for 1–31 May leaves 1 June as the first unbilled day and
#: the run is CONTINUOUS. Every other case below moves one of these two dates
#: and nothing else, so the arithmetic in each assertion is readable.
MAY_START = date(2026, 5, 1)
MAY_END = date(2026, 5, 31)


def an_issued_bill(
    tenant, account, *, period_start=MAY_START, period_end=MAY_END, bill_payload=None
):
    """An ISSUED invoice covering a window — the anchor under test.

    `status=issued` and not `draft`, because a draft anchors nothing: it is
    discardable (BR-BIL-004) and a run that anchored on its own draft would
    look continuous with itself.

    ⚠ `DEF-BIL-9040` — THE SNAPSHOT IS STAMPED AT CREATION. An issued bill
    takes no later edit but its status (hard rule 4; BR-BIL-030's trigger,
    `billing/0017`), so the cases below used to issue the bill and then SAVE
    the anchor read onto its `bill_payload` — which PostgreSQL refuses and
    sqlite never noticed. A real issue carries its snapshot from the start.
    """
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        status=billing_models.INVOICE_ISSUED,
        bill_payload=bill_payload if bill_payload is not None else {"services": []},
        period_start=period_start,
        period_end=period_end,
        service_date=period_end,
        currency="USD",
        total=Decimal("0.000000"),
        subtotal=Decimal("0.000000"),
        tax_total=Decimal("0.000000"),
    )


def continuity_rows(prepared, account_no):
    return [
        problem
        for problem in prepared.decisions
        if problem.reason == "billing_continuity" and problem.account_no == account_no
    ]


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-5270 — does the consumption start where the last BILL ended?
# ══════════════════════════════════════════════════════════════════════════


def test_def_bil_5270_tc1__an_account_with_no_issued_bill_raises_nothing(brazos, dana):
    """A first bill has no anchor, and *no anchor* is not *out of step*.

    The distinction `periodContinuity` draws with its own `unknown` state, one
    layer down: a check that fired on every new customer would be the same
    false alarm `DEF-572` and `BR-BIL-1025` were each filed for.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5270", label="Unit A")
        an_account(brazos, unit["id"], "A-52701")

        prepared = prepared_for(cycle)

        assert continuity_rows(prepared, "A-52701") == []


def test_def_bil_5270_tc2__continuous_billing_raises_nothing(brazos, dana):
    """Billed through 31 May, this run opens 1 June. `cut_bill`'s own anchor."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5271", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52702")
        an_issued_bill(brazos, account)

        assert runs.period_anchor(str(account.id), period_start=PERIOD_START).state == (
            runs.CONTINUITY_ALIGNED
        )
        assert continuity_rows(prepared_for(cycle), "A-52702") == []


def test_def_bil_5270_tc3__a_gap_is_named_with_its_days(brazos, dana):
    """Billed through 30 April, this run opens 1 June: **31 days nobody billed.**

    THE FIGURE IS THE POINT. *"Check continuity"* sends a clerk hunting;
    *"1 May to 31 May, 31 days, on no issued bill"* is a minute's work — the
    same reasoning BR-BIL-040 gives for naming the stage on a break.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5272", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52703")
        an_issued_bill(brazos, account, period_start=date(2026, 4, 1), period_end=date(2026, 4, 30))

        anchor = runs.period_anchor(str(account.id), period_start=PERIOD_START)
        assert anchor.state == runs.CONTINUITY_GAP
        assert anchor.days == 31
        assert anchor.from_day == date(2026, 5, 1)
        assert anchor.to_day == date(2026, 5, 31)

        rows = continuity_rows(prepared_for(cycle), "A-52703")
        assert len(rows) == 1
        assert "31 day(s)" in rows[0].detail
        # BR-BIL-040 — the finding lands on the tab that owns the input.
        assert rows[0].stage == "measure-consumption"


def test_def_bil_5270_tc4__an_overlap_is_named_with_its_days(brazos, dana):
    """Billed through 30 June, this run opens 1 June: **30 days billed twice.**

    The direction that costs a CUSTOMER money rather than the utility, and the
    one a run-period continuity band cannot see: the two runs' periods can be
    perfectly contiguous while one account inside them has been billed ahead by
    a cut bill or a catch-up sub-run.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5273", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52704")
        an_issued_bill(brazos, account, period_start=PERIOD_START, period_end=PERIOD_END)

        anchor = runs.period_anchor(str(account.id), period_start=PERIOD_START)
        assert anchor.state == runs.CONTINUITY_OVERLAP
        assert anchor.days == 30

        rows = continuity_rows(prepared_for(cycle), "A-52704")
        # ⚠ **ONE row, and it is the CALENDAR one.** Until the PO's ruling of
        # 2026-09-14 this raised a second, REGISTER row beside it; that branch
        # is gone and its case is the anchor's own behaviour now. A register
        # row here again would mean the overruled decision had come back.
        assert len(rows) == 1
        assert rows[0].service_code is None
        assert "already covers" in rows[0].detail


def a_read_on(actor, tenant, asset_no, *, day, value, prior_value, consumption):
    """One committed read on a NAMED meter — history the anchor is taken from."""
    from apps.assets import models as asset_models
    from tests.test_us_met_reads_helpers import commit_read

    asset_id = asset_models.Asset.objects.get(tenant=tenant, asset_no=asset_no).id
    return commit_read(
        actor,
        asset_id,
        day=day,
        value=value,
        prior_value=prior_value,
        consumption=consumption,
        unit="kWh",
    )


def test_def_bil_5270_tc5__the_period_opens_at_the_last_billed_read(brazos, dana):
    """**THE PO'S RULING, AS THE FIGURE.** 13,500 → 13,800 bills **300**.

    Verbatim, 2026-09-14: *"there is no sign off issue - you ahve to raje start
    reading as 13,500 - we cannot create wrong conusmption that is loss"*.

    The May bill closed the meter at **13,500**. June's read was taken from a
    prior of **13,800** — a re-read, a skipped read, anything — and metering
    stored `14,212 − 13,800 = 412`. Every period ties out and **300 kWh sit on
    no issued bill**.

    ⚠ **THIS CASE USED TO RAISE A DECISION AND THAT IS WHAT WAS OVERRULED.** A
    decision asks a clerk to choose between defensible outcomes; here one
    outcome is simply wrong, and a control that offers it will have it chosen
    in bulk on a busy day. So there is NO row on the exceptions list and the
    quantity is **712**, not 412: `14,212 − 13,500`.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5274", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52705")
        # The May bill, and the read it closed on at 13,500.
        anchor_read = a_read_on(
            dana,
            brazos,
            "M-5274",
            day="2026-05-28",
            value="13500",
            prior_value="13100",
            consumption="400.000000",
        )
        an_issued_bill(
            brazos,
            account,
            bill_payload={"services": [{"code": "electric", "read_id": str(anchor_read.id)}]},
        )

        prepared = prepared_for(cycle)

        assert continuity_rows(prepared, "A-52705") == []
        reading = next(r for r in prepared.ready[0].readings if r.service_code == "electric")
        # 14,212 − 13,500, not 14,212 − 13,800.
        assert reading.consumption.amount == Decimal("712")
        # The pair the BILL prints must foot against the 712 it charges.
        assert reading.prior_read == Decimal("13500.000000")
        assert reading.current_read == Decimal("14212.000000")
        # And the trace says what it moved OFF — metering's own prior.
        assert reading.unanchored_prior_read == Decimal("13800.000000")


def test_def_bil_5270_tc5b__an_aligned_period_is_left_exactly_as_metering_gave_it(brazos, dana):
    """The overwhelming majority, and the reason no ❄️ B4/B5 figure can move.

    The May bill closed at **13,800** and June's read opens at 13,800. There is
    nothing to anchor, so the reading comes back with metering's own **412**
    and `anchored_from` is None — a fact a reader can check rather than a
    promise in a comment.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5276", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52707")
        anchor_read = a_read_on(
            dana,
            brazos,
            "M-5276",
            day="2026-05-28",
            value="13800",
            prior_value="13400",
            consumption="400.000000",
        )
        an_issued_bill(
            brazos,
            account,
            bill_payload={"services": [{"code": "electric", "read_id": str(anchor_read.id)}]},
        )

        reading = next(
            r for r in prepared_for(cycle).ready[0].readings if r.service_code == "electric"
        )

        assert reading.consumption.amount == Decimal("412.000000")
        assert reading.unanchored_prior_read is None


def test_def_bil_5270_tc5c__a_meter_exchange_refuses_rather_than_billing_a_fiction(brazos, dana):
    """⚠ **THE MIRROR OF THE LOSS THE RULING PREVENTS.**

    The old device left at 13,500 and this period's read is on a DIFFERENT
    meter. Anchoring across the two would bill `14,212 − 13,500 = 712` on a
    register that never counted from 13,500 — a fiction, and the ruling names
    this exclusion in as many words.

    ⚠ **THE EXCHANGE IS READ, NOT INFERRED.** The refusal comes from metering's
    published `asset_id` on each read (`DEF-BIL-5269`'s lesson), never from the
    numbers looking odd — a new meter whose first read happens to sit above the
    old one's last produces a perfectly plausible delta.
    """
    from apps.metering import models as metering_models
    from tests.test_us_met_reads_helpers import a_meter, commit_read

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        # ⚠ AMENDED 2026-09-30 (DEF-BIL-8244) — `consumption=None`: the old
        # meter carries NO reading after the one the May bill closed on. With
        # the helper's June read left on it, the old meter's final AND the new
        # meter's first were both recorded, which is now the *Meter swapped →
        # bill both parts* suggestion (`runs._meter_swap`), not this refusal.
        # This case is the other half of that ruling: ONE PART MISSING.
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-5277", label="Unit A", consumption=None
        )
        account = an_account(brazos, unit["id"], "A-52708")
        from apps.assets import models as asset_models

        old_asset_id = asset_models.Asset.objects.get(tenant=brazos, asset_no="M-5277").id
        # The OLD meter's final read, and the bill that closed on it.
        anchor_read = commit_read(
            dana,
            old_asset_id,
            day="2026-05-28",
            value="13500",
            prior_value="13100",
            consumption="400.000000",
            unit="kWh",
        )
        an_issued_bill(
            brazos,
            account,
            bill_payload={"services": [{"code": "electric", "read_id": str(anchor_read.id)}]},
        )
        # A NEW meter on the same unit, carrying this period's read.
        new_meter = a_meter(dana, asset_no="M-5277-NEW", unit_id=unit["id"])
        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(
            cycle=cycle
        )
        # ⚠ AMENDED 2026-09-30 — AN EXCHANGE RETIRES THE OLD METER. PO ruling of
        # that date: two IN-SERVICE meters on one metered point are two
        # connections, billed as two line sets. This fixture used to leave the
        # old meter in service beside the new one, which is now the two-meter
        # case and not an exchange (it went RED as `plan_has_no_tariff_for_service`
        # — each meter priced on its own, off a base this fixture never declared).
        # An exchange is the old device taken OUT of service; with it retired the
        # point is one connection again and the anchor refusal below is reached.
        from apps.assets import models as asset_models
        from apps.assets import services as asset_services

        asset_models.Asset.objects.filter(tenant=brazos, id=old_asset_id).update(
            status=asset_services.stage_by_code("retired")
        )
        commit_read(
            dana,
            new_meter["id"],
            day="2026-06-29",
            value="14212",
            prior_value="13800",
            consumption="412.000000",
            unit="kWh",
        )

        prepared = prepared_for(cycle)

        blocked = [p for p in prepared.blocked if p.account_no == "A-52708"]
        assert [p.reason for p in blocked] == [runs.ANCHOR_METER_EXCHANGED]
        assert blocked[0].stage == "measure-consumption"
        assert "cannot be subtracted" in blocked[0].detail
        # And it never reaches a draft — a fiction must not be billable.
        assert [d.account_no for d in prepared.ready] == []


def test_def_bil_5270_tc5d__a_wrap_the_anchor_would_have_to_span_refuses(brazos, dana):
    """A 5-digit register passing 99,999 returns to 0 — the ruling's second
    exclusion, and it only bites where the ANCHOR would have to cross it.

    The May bill closed at **99,800**. A re-read on 10 June caught the wrap
    (metering's own ❄️ GT-4/GT-14 arithmetic makes 99,800 → 240 a lawful
    **440**), and the read this period bills on is 29 June at **700**, counting
    from 240. Anchoring that to 99,800 asks for `700 − 99,800`.

    ⚠ **BILLING REFUSES RATHER THAN DECIDING.** Whether that is one register
    span plus 700 or a bad read is `BR-AST-015`'s test of the drop against the
    register's SPAN, and metering does not publish the span across this seam.
    Guessing a 5-, 6- or 9-digit register invents consumption; calling every
    wrap a bad read loses a whole register of it. So the account is named and a
    human is sent to the module that owns the answer.

    ⚠ **AND A WRAP THE ANCHOR DOES *NOT* HAVE TO SPAN IS LEFT ALONE** — see
    `tc5e`. That distinction is the whole reason this refusal is narrow.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-5278", label="Unit A", consumption=None
        )
        account = an_account(brazos, unit["id"], "A-52709")
        anchor_read = a_read_on(
            dana,
            brazos,
            "M-5278",
            day="2026-05-28",
            value="99800",
            prior_value="99400",
            consumption="400.000000",
        )
        a_read_on(
            dana,
            brazos,
            "M-5278",
            day="2026-06-10",
            value="240",
            prior_value="99800",
            consumption="440.000000",
        )
        a_read_on(
            dana,
            brazos,
            "M-5278",
            day="2026-06-29",
            value="700",
            prior_value="240",
            consumption="460.000000",
        )
        an_issued_bill(
            brazos,
            account,
            bill_payload={"services": [{"code": "electric", "read_id": str(anchor_read.id)}]},
        )

        prepared = prepared_for(cycle)

        blocked = [p for p in prepared.blocked if p.account_no == "A-52709"]
        # ⚠ AMENDED 2026-09-30 (PO, changes rows 45–46, *"Possible rollover"*):
        # metering now publishes the meter's register span to the Check
        # (`register_digits_for_read`), so where the dial PROVES the wrap the
        # refusal carries the SUGGESTION — 100,000 − 99,800 + 700 = 900 — and
        # the account is still not billed until a clerk accepts it. A drop the
        # span does not prove stays `ANCHOR_REGISTER_WENT_BACKWARDS`.
        assert [p.reason for p in blocked] == [runs.POSSIBLE_ROLLOVER]
        assert Decimal(blocked[0].message_params["suggested_quantity"]) == Decimal("900")
        # NOT retryable from the phase-3 screen: nothing there records a span.
        assert runs.ANCHOR_REGISTER_WENT_BACKWARDS in runs.NOT_RETRYABLE_HERE
        assert [d.account_no for d in prepared.ready] == []


def test_def_bil_5270_tc5e__a_wrap_already_inside_the_period_is_left_alone(brazos, dana):
    """The case that must NOT be swept up: the period already opens at the
    anchor, and the wrap is metering's to have handled.

    The May bill closed at **99,800** and this period's read counts from
    99,800 to 240 — so the period IS anchored, there is nothing to move, and
    metering's stored **440** (`BR-AST-015`'s span test, ❄️ GT-4/GT-14) stands
    untouched. Billing neither recomputes it nor refuses it.

    ⚠ **THIS IS THE ASSERTION THAT KEEPS THE REFUSAL HONEST.** A backwards-read
    check written one line higher — before the already-aligned test — would
    refuse every wrapped meter in the book, every cycle, and would read exactly
    like the rule working.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-5279", label="Unit A", consumption=None
        )
        account = an_account(brazos, unit["id"], "A-52710")
        anchor_read = a_read_on(
            dana,
            brazos,
            "M-5279",
            day="2026-05-28",
            value="99800",
            prior_value="99400",
            consumption="400.000000",
        )
        a_read_on(
            dana,
            brazos,
            "M-5279",
            day="2026-06-29",
            value="240",
            prior_value="99800",
            consumption="440.000000",
        )
        an_issued_bill(
            brazos,
            account,
            bill_payload={"services": [{"code": "electric", "read_id": str(anchor_read.id)}]},
        )

        prepared = prepared_for(cycle)

        assert [p.reason for p in prepared.blocked if p.account_no == "A-52710"] == []
        reading = next(r for r in prepared.ready[0].readings if r.service_code == "electric")
        assert reading.consumption.amount == Decimal("440.000000")
        assert reading.unanchored_prior_read is None


def test_def_bil_5270_tc6__the_case_is_recordable_and_investigate_holds(brazos, dana):
    """A finding a clerk cannot answer is work no work list may carry.

    Two choices, both words this vocabulary already uses — `bill_as_is` records
    that a human looked and let it, `investigate` takes the account out into
    BR-BIL-055's one pending queue.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-5275", label="Unit A")
        account = an_account(brazos, unit["id"], "A-52706")
        an_issued_bill(brazos, account, period_start=date(2026, 4, 1), period_end=date(2026, 4, 30))
        run = a_run(brazos, cycle, key="2026-06|def-bil-5270-tc6")

        assert decisions.CHOICES_BY_CASE["billing_continuity"] == (
            decisions.CHOICE_BILL_AS_IS,
            decisions.CHOICE_INVESTIGATE,
        )
        decisions.record_decision(
            bill_run=run,
            account_id=str(account.id),
            case="billing_continuity",
            choice=decisions.CHOICE_INVESTIGATE,
            reason="meter exchanged in May, checking the residual",
            decided_by=dana.user,
        )
        decided = decisions.apply_decisions(prepared_for(cycle), bill_run=run)

        assert [data.account_no for data in decided.ready] == []
        assert billing_models.BillRunExclusion.objects.filter(
            tenant=brazos, bill_run=run, account_id=account.id
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# DEF-BIL-5271 — a decision that re-prices, and a gate that insists on it
# ══════════════════════════════════════════════════════════════════════════


def two_billed_accounts(brazos, dana, cycle, plan, *, prefix="M-527"):
    first = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"{prefix}A", label="Unit A")
    second = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"{prefix}B", label="Unit B")
    return (
        an_account(brazos, first["id"], "A-52711"),
        an_account(brazos, second["id"], "A-52712"),
    )


def test_def_bil_5271_tc1__only_accounts_narrows_the_pass(brazos, dana):
    """`calculate_run(only_accounts=…)` drafts the named account and no other.

    ⚠ **THE OTHER ACCOUNT IS NOT MERELY UNDRAFTED — IT IS UNTOUCHED.** A
    narrowing that quietly redrafted the rest would be a whole run wearing a
    decision's name, and at T5 that is 40,000 accounts of work for a decision
    about one.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        first, second = two_billed_accounts(brazos, dana, cycle, plan)
        run = a_run(brazos, cycle, key="2026-06|def-bil-5271-tc1")

        result = runs.calculate_run(
            prepared_for(cycle), bill_run=run, only_accounts=frozenset({str(first.id)})
        )

        assert result.drafted_count == 1
        assert result.account_count == 1
        drafted = set(
            billing_models.Invoice.objects.filter(tenant=brazos, bill_run=run).values_list(
                "account_id", flat=True
            )
        )
        assert drafted == {first.id}


def test_def_bil_5271_tc2__a_decision_taken_after_the_draft_makes_it_stale(brazos, dana):
    """**THE DEFECT, MEASURED.** 1 draft, 1 decision, and the gate saw nothing.

    `outstanding` breaks stays 0 because a decision is not a break — so before
    this check the run walked into phase 4 carrying a figure computed before
    anybody decided anything.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        first, _second = two_billed_accounts(brazos, dana, cycle, plan, prefix="M-528")
        run = a_run(brazos, cycle, key="2026-06|def-bil-5271-tc2")
        runs.calculate_run(prepared_for(cycle), bill_run=run)

        assert runs.stale_drafts(run) == ()

        decisions.record_decision(
            bill_run=run,
            account_id=str(first.id),
            case="base_only_billing",
            choice=decisions.CHOICE_INCLUDE,
            reason="staff opt-in",
            decided_by=dana.user,
        )

        stale = runs.stale_drafts(run)
        assert [row.account_id for row in stale] == [str(first.id)]
        # BR-BIL-053's own number is untouched — which is exactly why the old
        # gate let this through.
        assert (
            billing_models.BillRunBreak.objects.filter(
                tenant=brazos, bill_run=run, resolution__isnull=True
            ).count()
            == 0
        )
        with pytest.raises(BillingRuleError) as refused:
            runs.refuse_stale_drafts(run)
        assert "1 draft(s)" in str(refused.value)


def test_def_bil_5271_tc3__a_scoped_reprice_clears_the_gate(brazos, dana):
    """The two halves joined: re-price the accounts the decision touched, and
    the run may enter phase 4 again.

    ⚠ **THE SECOND ACCOUNT'S DRAFT IS THE SAME ROW AFTERWARDS.** A re-price
    that replaced every draft would be indistinguishable from a full
    recalculate, and the whole point of scoping is that it is not one.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        first, second = two_billed_accounts(brazos, dana, cycle, plan, prefix="M-529")
        run = a_run(brazos, cycle, key="2026-06|def-bil-5271-tc3")
        # BR-BIL-070 — `selectors.prepared_for` resolves the run's SERVICE date
        # from the bill date a clerk typed on step 1 and REFUSES rather than
        # reaching for a clock. A re-price goes through that same door, so the
        # fixture types one.
        billing_models.BillRun.objects.filter(pk=run.pk).update(bill_date=SERVICE_DATE)
        run.refresh_from_db()
        runs.calculate_run(prepared_for(cycle), bill_run=run)
        untouched = billing_models.Invoice.objects.get(
            tenant=brazos, bill_run=run, account_id=second.id
        )

        decisions.record_decision(
            bill_run=run,
            account_id=str(first.id),
            case="base_only_billing",
            choice=decisions.CHOICE_INCLUDE,
            reason="staff opt-in",
            decided_by=dana.user,
        )
        assert len(runs.stale_drafts(run)) == 1

        repriced = runs.reprice_accounts(bill_run=run, account_ids=[str(first.id)])

        assert repriced.drafted_count == 1
        assert runs.stale_drafts(run) == ()
        assert (
            billing_models.Invoice.objects.get(tenant=brazos, bill_run=run, account_id=second.id).pk
            == untouched.pk
        )


def test_def_bil_5271_tc4__the_release_gate_refuses_a_stale_draft(brazos, dana):
    """**HARD-WON LAW 2 — the check is WIRED, not merely written.**

    `authorise_release` is the one server-side act that says *I approve these
    figures*. A gate function with no caller would be the same built-not-wired
    shape `decisions.apply_decisions` sat in for five days.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        first, _second = two_billed_accounts(brazos, dana, cycle, plan, prefix="M-530")
        run = a_run(brazos, cycle, key="2026-06|def-bil-5271-tc4")
        billing_models.BillRun.objects.filter(pk=run.pk).update(bill_date=SERVICE_DATE)
        run.refresh_from_db()
        runs.calculate_run(prepared_for(cycle), bill_run=run)
        decisions.record_decision(
            bill_run=run,
            account_id=str(first.id),
            case="base_only_billing",
            choice=decisions.CHOICE_INCLUDE,
            reason="staff opt-in",
            decided_by=dana.user,
        )

        with pytest.raises(BillingRuleError) as refused:
            release.authorise_release(
                bill_run=run,
                summary=release.summary_for(run),
                confirmations=release.Confirmations(
                    compliance=True,
                    email_mandate=True,
                    sms_mandate=True,
                    autopay_mandate=True,
                    final=True,
                ),
                confirmed_by=dana.user.id,
                # A PARAMETER and never a clock read (BR-TEN-043 / G6).
                confirmed_at=datetime(2026, 6, 30, 12, 0, tzinfo=timezone.utc),
            )
        assert "before a decision was recorded" in str(refused.value)

        # And it stops refusing once the re-price has happened — a gate that
        # could never be satisfied is law 7's *incapable of passing*.
        runs.reprice_accounts(bill_run=run, account_ids=[str(first.id)])
        runs.refuse_stale_drafts(run)


def test_def_bil_5271_tc5__accounts_touched_dedupes_and_keeps_order(brazos, dana):
    """The scope comes from the ROWS WRITTEN, never from what was asked for."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        first, second = two_billed_accounts(brazos, dana, cycle, plan, prefix="M-531")
        run = a_run(brazos, cycle, key="2026-06|def-bil-5271-tc5")
        _bulk, rows = decisions.record_bulk(
            bill_run=run,
            account_ids=[str(first.id), str(second.id), str(first.id)],
            case="base_only_billing",
            choice=decisions.CHOICE_INCLUDE,
            reason="staff opt-in",
            decided_by=dana.user,
        )

        assert decisions.accounts_touched(rows) == (str(first.id), str(second.id))
        assert decisions.accounts_touched([]) == ()

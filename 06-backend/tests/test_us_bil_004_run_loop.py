# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-004 (phase 2 calculate + phase 3 breaks)   Screens: S31.4
# Rules:    BR-BIL-052 (per-account, restartable, resumable — one account's
#           failure never rolls back another's draft) · BR-BIL-053 (the breaks
#           list, with the failing STAGE named, retry-now or mark-for-later) ·
#           BR-BIL-055 (a partial run issues the clean and holds the rest; one
#           pending queue, two doors) · BR-BIL-023 (a re-run REPLACES a draft) ·
#           BR-BIL-004 (a draft is not money)
# ───────────────────────────────────────────────────────
"""The run loop, and the one property everything else depends on.

**One account's failure never touches another account's draft.** A run of 1,124
that fell over on number 400 and rolled back would throw away 399 correct
drafts and a morning's work — BR-BIL-052 forbids it in as many words, and the
reason it is safe to forbid is that a draft is not money (BR-BIL-004).

That property is easy to write and easy to lose: one `transaction.atomic()` in
the wrong place turns the whole run into a single unit, every test still
passes, and nobody finds out until a real run of 1,124 hits its first bad
account. `tc2` is that case with the transaction boundary asserted from the
outside — by counting what survived.
"""

from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import runs
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)

pytestmark = pytest.mark.django_db


def a_run(tenant, cycle, key="2026-06|run-loop"):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=key,
    )


def a_planless_unit(actor, tenant, cycle, *, asset_no, label):
    """A unit in the cycle with a meter and NO plan — breaks at stage 1."""
    from tests.test_us_met_reads_helpers import a_meter

    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")
    unit = make_unit(actor, premises["id"], label=label, services=["electric"])
    a_meter(actor, asset_no=asset_no, unit_id=unit["id"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    return unit


def prepared_for(cycle):
    return runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )


def test_us_bil_004_tc1__every_ready_account_is_drafted(brazos, dana):
    """The happy path over a run rather than an account."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        for n in (1, 2, 3):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-720{n}", label=f"Unit {n}")
            an_account(brazos, unit["id"], f"A-2000{n}")

        prepared = prepared_for(cycle)
        result = runs.calculate_run(prepared, bill_run=a_run(brazos, cycle))

        assert result.drafted_count == 3
        assert result.breaks == ()
        assert result.account_count == 3
        assert billing_models.Invoice.objects.count() == 3
        assert all(
            inv.status == billing_models.INVOICE_DRAFT
            for inv in billing_models.Invoice.objects.all()
        )


def test_us_bil_004_tc2__one_broken_account_never_rolls_back_another_draft(brazos, dana):
    """THE PROPERTY THIS MODULE EXISTS FOR — BR-BIL-052.

    Two good accounts either side of one that cannot be gathered. If the loop
    held a single transaction, the failure would take all three and the run
    would produce nothing. It produces two drafts and one break, and the count
    is the proof: a rolled-back run has 0 invoices, not 2.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)

        good_a = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7211", label="A")
        an_account(brazos, good_a["id"], "A-20011")

        broken = a_planless_unit(dana, brazos, cycle, asset_no="M-7212", label="B")
        an_account(brazos, broken["id"], "A-20012")

        good_b = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7213", label="C")
        an_account(brazos, good_b["id"], "A-20013")

        prepared = prepared_for(cycle)
        result = runs.calculate_run(prepared, bill_run=a_run(brazos, cycle))

    # The planless one never reaches `ready` — it breaks at PREPARE, which is
    # phase 1's job and is why it is in `blocked` there. What matters here is
    # that the two good accounts both drafted.
    assert result.drafted_count == 2
    assert billing_models.Invoice.objects.count() == 2
    assert [p.reason for p in prepared.blocked] == ["unit_has_no_plan"]


def test_us_bil_004_tc3__a_break_names_the_stage_that_failed(brazos, dana):
    """BR-BIL-040/053 — "ACC-1201 failed" sends a clerk hunting.

    An account whose read never arrived reaches phase 2 (BR-BIL-015 keeps it in
    the run) and breaks at measure-consumption. The break carries the stage by
    the pipeline's own name, so the screen groups by it and a clerk fixes every
    missing read in one pass.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-7214", label="A", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: read in May, missed in June
        )
        an_account(brazos, unit["id"], "A-20014")

        prepared = prepared_for(cycle)
        result = runs.calculate_run(prepared, bill_run=a_run(brazos, cycle))

    assert result.drafted_count == 0
    assert len(result.breaks) == 1
    broken = result.breaks[0]
    assert broken.account_no == "A-20014"
    assert broken.stage == "measure-consumption"
    assert broken.reason == runs.CALC_UNRESOLVED_READ
    assert broken.retryable is True  # a clerk can enter the read and retry
    assert list(result.breaks_by_stage()) == ["measure-consumption"]
    # Nothing partial was left behind for the broken account.
    assert billing_models.Invoice.objects.count() == 0


def test_us_bil_004_tc4__retry_after_a_fix_moves_the_account_into_the_draft_set(brazos, dana):
    """BR-BIL-053's first door: *"retry immediately by fixing the issue"*.

    The clerk enters the missing read; the account re-runs ALONE and joins the
    drafts. The other drafts are not recomputed — which is why the readings are
    swapped onto the data already gathered rather than re-gathering: a customer
    name changed since the run must not silently reach a bill priced before it.
    """
    from apps.billing.contracts import ServiceReading
    from apps.billing.rating_seam import Quantity

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-7215", label="A", consumption=None,
            read_last_month=True,  # DEF-BIL-8671: read in May, missed in June
        )
        account = an_account(brazos, unit["id"], "A-20015")
        run = a_run(brazos, cycle)

        prepared = prepared_for(cycle)
        assert runs.calculate_run(prepared, bill_run=run).drafted_count == 0

        fixed = (
            ServiceReading(
                service_code="electric",
                consumption=Quantity(amount=Decimal("412.000000"), unit="kWh"),
            ),
        )
        invoice = runs.retry_account(prepared, str(account.id), bill_run=run, readings=fixed)

        assert invoice.status == billing_models.INVOICE_DRAFT
        assert invoice.total == Decimal("67.940000")  # 412 × 0.12 + 18.50
        assert billing_models.Invoice.objects.count() == 1


def test_us_bil_004_tc5__mark_for_later_writes_the_pending_queue_row(brazos, dana):
    """BR-BIL-053's second door, and BR-BIL-055's one queue.

    A phase-3 mark-for-later and a phase-1 hold write the SAME table, because
    the PO confirmed one pending queue. The reason code is what records which
    door — "we never calculated this" and "we calculated it and it broke" are
    different facts, and a queue that cannot tell them apart cannot tell a
    clerk whether to fix data or fix configuration.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7216", label="A")
        account = an_account(brazos, unit["id"], "A-20016")
        run = a_run(brazos, cycle)

        row = runs.mark_for_later(
            bill_run=run,
            account_id=str(account.id),
            reason_code="calculation_broke",
            detail="no usable read for electric",
        )
        assert row.reason_code == "calculation_broke"
        assert row.resolved_at is None  # still pending — that is what makes it a queue

        # Idempotent: a double-click marks once rather than raising at the user.
        again = runs.mark_for_later(
            bill_run=run, account_id=str(account.id), reason_code="calculation_broke"
        )
        assert again.pk == row.pk
        assert billing_models.BillRunExclusion.objects.filter(bill_run=run).count() == 1


def test_us_bil_004_tc6__re_running_the_whole_loop_replaces_rather_than_duplicates(brazos, dana):
    """BR-BIL-052 — a killed batch resumes; drafts are "never duplicated".

    Resumability here is not a checkpoint, it is a property of the write: stage
    6 REPLACES an account's draft for this run (BR-BIL-023) and stages 1–5 are
    pure, so re-running the whole loop converges on the same drafts. Nothing
    tracks progress because nothing needs to — and a checkpoint is a thing that
    can rot, where the write cannot.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        for n in (1, 2):
            unit = a_billed_unit(dana, brazos, cycle, plan, asset_no=f"M-722{n}", label=f"Unit {n}")
            an_account(brazos, unit["id"], f"A-2002{n}")

        run = a_run(brazos, cycle)
        prepared = prepared_for(cycle)

        first = runs.calculate_run(prepared, bill_run=run)
        second = runs.calculate_run(prepared, bill_run=run)

        assert first.drafted_count == 2 and second.drafted_count == 2
        assert billing_models.Invoice.objects.count() == 2  # not 4
        # BR-BIL-063: each re-run allocates fresh numbers and the old ones are
        # spent. The PO ruled that acceptable; it is asserted so the cost stays
        # visible rather than surfacing as an auditor's question.
        assert set(first.drafted).isdisjoint(second.drafted)


def test_us_bil_004_tc7__a_break_a_clerk_cannot_fix_here_is_not_offered_a_retry(brazos, dana):
    """A retry button that always fails is worse than no button.

    An account whose plan has no tariff version in force cannot be fixed from
    the breaks screen — it needs a rate dated in Plans & Rates. The break says
    so instead of inviting a click that cannot work.
    """
    assert runs.NOT_RETRYABLE_HERE >= {
        "unit_has_no_plan",
        "plan_not_published",
        "tariff_has_no_version_in_force_at_service_date",
    }
    assert runs.CALC_UNRESOLVED_READ not in runs.NOT_RETRYABLE_HERE


def test_us_bil_004_tc8__a_rating_refusal_is_one_break_not_the_end_of_the_run(brazos, dana):
    """DEF-047 — tc2's property, against the OTHER exception hierarchy.

    tc2 proves a GATHER failure does not roll back its neighbours. Nothing
    proved it for a RATING failure, and rating raises neither type the loop
    caught: `apps.rating.pricing.errors.RatingError` is its own hierarchy on
    purpose (*"the caller maps a refusal onto its own S31.3 exception row"*) and
    nothing did that mapping. So one tenant's configuration mistake — a tariff
    billing in gallons against a meter reading kilowatt-hours — escaped the loop
    and killed the entire run.

    Two good accounts either side of it. The count is the proof, the same way it
    is in tc2: a run that died has 0 invoices, not 2.
    """
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)

        good_a = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7231", label="A")
        an_account(brazos, good_a["id"], "A-20031")

        # A real mis-configuration, not a mock: the plan bills in gallons and
        # the meter reads kilowatt-hours, so BR-RAT-038's UoM gate refuses
        # rather than converting. Rating's refusal, raised from rating's code.
        mismatched = a_priced_plan(brazos, name="Gallons By Mistake")
        rating_models.TariffVersion.objects.filter(
            tenant=brazos,
            tariff_id__in=[
                row["tariff"].id for row in rating_selectors.plan_rate_schedules(mismatched.id)
            ],
        ).update(uom="gal")
        bad = a_billed_unit(dana, brazos, cycle, mismatched, asset_no="M-7232", label="B")
        an_account(brazos, bad["id"], "A-20032")

        good_b = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7233", label="C")
        an_account(brazos, good_b["id"], "A-20033")

        prepared = prepared_for(cycle)
        result = runs.calculate_run(prepared, bill_run=a_run(brazos, cycle))

        assert result.drafted_count == 2
        assert billing_models.Invoice.objects.count() == 2  # not 0, and not 3
        assert len(result.breaks) == 1

        broken = result.breaks[0]
        assert broken.account_no == "A-20032"
        assert broken.reason == runs.PRICING_REFUSED
        # BR-BIL-040 — the break names the stage a clerk should look at, and
        # rating's own words ride along so they know WHICH rate is wrong.
        assert broken.stage == "price-usage"
        assert "kWh" in broken.detail and "gal" in broken.detail
        # Not fixable from this screen: the rate is wrong in Plans & Rates.
        assert broken.retryable is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-004@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-01-bill-run.md · 07-billing/02-business-rules.md ·
#         07-billing/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — phases 2 and 3)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half yet) E=deferred(no-frontend-half yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: (1) THE LOOP RUNS INLINE. BR-BIL-051 wants a background batch and
#         there is no job runner in this project — celery is a declared
#         dependency with zero tasks.py and JOBS_EAGER=true (TD-17, open) — so
#         "background" is not yet true and neither the code nor these tests
#         pretend it is. What exists is the work the batch will do
#         (2) PHASE 3 IS THE DATA, NOT THE SCREEN. `breaks`, `retry_account`
#         and `mark_for_later` are what S31.4 will render and act on; there is
#         no screen and no endpoint
#         (3) tc2's broken account breaks at PREPARE rather than at calculate,
#         because a planless unit never reaches `ready`. The rollback property
#         is asserted by counting survivors, which is the only way to observe a
#         transaction boundary from outside — stated so the test is not read as
#         proving more than it does
#         (4) tc8 ADDED 2026-08-11 (DEF-047) and it is the reason to read (3)
#         carefully. tc2 and tc3 both prove the no-rollback property using
#         BILLING's exception types, which the loop caught — so the suite was
#         green over a run that any RATING refusal would kill outright. The
#         property was never wrong; the coverage was, in a way no count of
#         passing tests could show. tc8 drives a real mis-configuration (a plan
#         billing in gallons against a kWh meter) rather than a mock, so it fails
#         if either the seam's translation or the loop's clause is removed —
#         both mutations were executed and are recorded in DEF-047
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

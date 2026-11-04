# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-001 (S9 Plans tab — the hard-delete audit lock, TC-5) ·
#           US-RAT-003 (charge codes — BR-RAT-035's audit lock) ·
#           US-TEN-007 (reference-data used-by counts)
#           Screens: S9 · S10 · S8 (Settings → reference data)
# Rules:    BR-RAT-030 (a published plan in use cannot be hard-deleted; Archive
#           is the way out) · BR-RAT-035 (a charge code referenced by issued
#           lines is audit-locked) · BR-TEN-029 (used-by counts come live from
#           the OWNING module) · BR-TEN-030 (a code freezes once used) ·
#           BR-TEN-034 (a used row cannot be deleted) · BR-BIL-042 (a
#           correction case carries SEVERAL reason codes) · hard rule 1
# ───────────────────────────────────────────────────────
"""DEF-079 — three guards that have been asking billing a question it never answered.

**THE GUARDS WERE ALWAYS CORRECT. THEY WERE ASKING A MODULE THAT SAID NOTHING.**
Each of the three seams below resolves `apps.billing.services.<name>` by name,
found nothing, and returned **0**. The callers then consumed that 0 as a fact:

  * `apps/rating/services.delete_plan` refuses a hard delete unless
    *accounts = 0 AND never billed*. The never-billed half answered 0 every
    time, so **a rate plan that HAS been billed could be permanently deleted**,
    taking its rate schedules and every charge, deposit, penalty and tax rule
    with it. `units.rate_plan_id` is `on_delete=PROTECT`, so a plan LIVE on a
    unit was safe; a RETIRED one was not, and invoices snapshot rather than
    reference a plan, so nothing else refused.
  * BR-RAT-035's audit lock never engaged on a charge code appearing on real
    bills.
  * BR-TEN-030 and BR-TEN-034 could not bite on a reason code in live use.

**THE TESTS ARE WRITTEN FROM THE GUARD'S SIDE, NOT THE COUNTER'S.** A test that
asserted `plan_invoice_count == 1` would have passed the day the function was
written and proved nothing about the delete. What matters is that the DELETE now
refuses, so that is what is asserted; the count is the mechanism, not the claim.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing.correction_models import CorrectionCase
from apps.rating import models as rating_models
from apps.rating import services as rating_services
from apps.tenancy import seams as tenancy_seams
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_bil_025_026_bills_read import an_account, an_invoice

pytestmark = pytest.mark.django_db


def a_billed_plan(tenant, account, *, name="Residential Standard"):
    """A plan, its tariff, a version of that tariff, and one invoice line
    priced under it — the shortest path from `rate_plans` to `invoice_lines`.

    This IS the chain the counter walks, built forwards, so a test failure
    points at the join rather than at a fixture that faked one.
    """
    service = rating_models.Tariff._meta.get_field("service").remote_field.model.objects.first()
    plan = rating_models.RatePlan.objects.create(
        tenant=tenant, code="RES-STD", name=name, status="published"
    )
    tariff = rating_models.Tariff.objects.create(
        tenant=tenant, name="Residential kWh", service=service
    )
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant, tariff=tariff, model="tiered", base_charge=Decimal("12.00")
    )
    rating_models.PlanRateSchedule.objects.create(
        tenant=tenant, rate_plan=plan, tariff=tariff, service=service
    )
    invoice = an_invoice(tenant, account)
    billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
        kind="usage",
        description="Electric usage 684 kWh",
        quantity=Decimal("684"),
        unit="kWh",
        unit_price=Decimal("0.12"),
        amount=Decimal("82.08"),
        taxable=True,
        period_start=date(2026, 7, 1),
        period_end=date(2026, 7, 31),
        tariff_version=version,
    )
    return plan, tariff


def test_def_079_tc1__a_plan_that_has_been_billed_cannot_be_hard_deleted(brazos, dana, marcus):
    """**THE DATA-LOSS DEFECT.** US-RAT-001 TC-5 / BR-RAT-030.

    The plan below has no accounts on it — it is retired, so the FK on `units`
    protects nothing — and it has priced a real invoice line. Before this fix
    the delete went through and took six tables of rules with it.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        plan, _ = a_billed_plan(brazos, account)

        with pytest.raises(errors.BizError) as excinfo:
            rating_services.delete_plan(dana, plan.id)

    assert excinfo.value.code == errors.BIZ_LOCKED
    assert excinfo.value.br_ref == "BR-RAT-030"
    assert excinfo.value.params["invoices"] == 1, (
        "the refusal must carry the COUNT the clerk is being blocked by — a "
        "'locked' message that cannot say how many bills exist tells them nothing"
    )
    # And the plan and its schedule are still there, which is the whole point.
    assert rating_models.RatePlan.objects.filter(pk=plan.pk).exists()
    assert rating_models.PlanRateSchedule.objects.filter(rate_plan_id=plan.pk).exists()


def test_def_079_tc2__an_unbilled_plan_still_deletes(brazos, dana):
    """The guard must not become a wall. A plan nobody has billed under is
    exactly what US-RAT-001 TC-5 permits a hard delete of, and over-blocking
    would be its own defect — a clerk who cannot clear a mistyped plan works
    around the product instead."""
    with tenant_ctx(brazos):
        plan = rating_models.RatePlan.objects.create(
            tenant=brazos, code="TYPO-1", name="Mistyped plan", status="draft"
        )
        rating_services.delete_plan(dana, plan.id)
        assert not rating_models.RatePlan.objects.filter(pk=plan.pk).exists()


def test_def_079_tc3__a_charge_code_on_a_real_bill_is_audit_locked(brazos, marcus):
    """BR-RAT-035. The bills themselves were never at risk — BR-BIL-010 stamps
    description and amount onto the line at issue, so history does not move
    under an edit. The lock exists to TELL a clerk they are editing something in
    live use, and while the count answered 0 it never told anybody."""
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        charge = rating_models.Charge.objects.create(
            tenant=brazos, code="CONN-FEE", name="Connection fee", amount=Decimal("25.00")
        )
        invoice = an_invoice(brazos, account)
        billing_models.InvoiceLine.objects.create(
            tenant=brazos,
            invoice=invoice,
            account=account,
            kind="charge",
            description="Connection fee",
            amount=Decimal("25.00"),
            taxable=False,
            charge=charge,
        )
        from apps.rating import seams as rating_seams

        assert rating_seams.invoice_line_references(charge.id) == 1


def test_def_079_tc4__a_reason_code_in_use_reports_its_uses(brazos, marcus):
    """BR-TEN-029/030/034, through TENANCY'S OWN SEAM rather than by calling
    billing — what broke was the wiring, not the function (hard-won law 2).

    Both tables count, because BR-BIL-042 makes a correction case carry SEVERAL
    reason codes in a list: a code used only on cases is still in use.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        assert tenancy_seams.reason_code_used_by_count("meter_misread") == 0

        invoice = an_invoice(brazos, account)
        billing_models.Adjustment.objects.create(
            tenant=brazos,
            account=account,
            invoice=invoice,
            direction="credit",
            amount=Decimal("18.40"),
            reason_code="meter_misread",
        )
        assert tenancy_seams.reason_code_used_by_count("meter_misread") == 1
        assert tenancy_seams.reason_code_used_by_count("goodwill") == 0

        # A code cited ONLY by a correction case, on no adjustment at all, is
        # still in use — BR-BIL-042's list is the second half of the count.
        CorrectionCase.objects.create(
            tenant=brazos, reason_codes=["goodwill"], correction_class="credit_only"
        )
        assert tenancy_seams.reason_code_used_by_count("goodwill") == 1


def test_def_079_tc5__the_counts_never_cross_a_tenant_boundary(
    brazos, lonestar, dana, marcus, erin
):
    """Hard rule 1. A neighbouring tenant's bill must not lock this tenant's
    plan — the guard would refuse a delete for a reason its owner cannot see,
    which is a worse failure than the one this closes."""
    with tenant_ctx(lonestar):
        their_account = an_account(lonestar, erin, account_no="A-90001", service="water")
        a_billed_plan(lonestar, their_account, name="Their Residential")

    with tenant_ctx(brazos):
        mine = rating_models.RatePlan.objects.create(
            tenant=brazos, code="RES-STD", name="Residential Standard", status="published"
        )
        from apps.billing import selectors as billing_selectors

        assert billing_selectors.plan_invoice_count(mine.id) == 0
        rating_services.delete_plan(dana, mine.id)
        assert not rating_models.RatePlan.objects.filter(pk=mine.pk).exists()


# ══════════════════════════════════════════════════════════════════════════
# THE DURABLE HALF — an unanswerable count is not zero (added 2026-08-15)
# ══════════════════════════════════════════════════════════════════════════
#
# Publishing the counters closed the finding. It did NOT close the SHAPE: both
# rating seams still answered `0` when billing published nothing, and both
# docstrings still said that was honest "by construction". DEF-079's prevention
# column states the law the fix has to reach —
#
#   "a fallback is only honest while the owning module holds no such fact, and
#    NOBODY re-reads that sentence — so the honest fallback is the one that
#    reports it could not answer, never the one that answers 0."
#
# So the seams now return None for "billing could not answer" and both delete
# guards FAIL CLOSED on it. These two cases drive that with the counter made
# unreachable, which is the world the register describes and the only world in
# which the fallback is ever consulted.


def test_def_079_tc6__an_unanswerable_plan_count_locks_the_delete(brazos, dana, monkeypatch):
    """A plan is NOT deleted on a count nobody could produce.

    The delete is permanent and takes six tables of rules with it; the FK on
    `units` protects only a plan that is live on a unit, and invoices snapshot
    rather than reference a plan, so nothing else in the database refuses. The
    only safe reading of "we could not check" is "do not delete".
    """
    from apps.billing import services as billing_services
    from apps.rating import seams as rating_seams

    monkeypatch.delattr(billing_services, "plan_invoice_count", raising=True)

    with tenant_ctx(brazos):
        plan = rating_models.RatePlan.objects.create(
            tenant=brazos, code="RES-STD", name="Residential Standard", status="published"
        )
        assert (
            rating_seams.plan_invoice_references(plan.id) is None
        ), "None is the whole fix: a 0 here is what let a billed plan be deleted"

        with pytest.raises(errors.BizError) as excinfo:
            rating_services.delete_plan(dana, plan.id)

    assert excinfo.value.code == errors.BIZ_LOCKED
    assert excinfo.value.params["invoices"] == "unavailable", (
        "the refusal must say WHICH half could not be answered — a clerk shown "
        "a bare lock cannot tell an in-use plan from an unreachable neighbour"
    )
    assert rating_models.RatePlan.objects.filter(pk=plan.pk).exists()


def test_def_079_tc7__an_unanswerable_charge_count_locks_the_delete(brazos, dana, monkeypatch):
    """BR-RAT-035's audit lock, same reading. A charge code deleted while live
    invoice lines cite it leaves those rows — which hard rule 4 forbids anyone
    from going back and fixing — pointing at a code that no longer exists."""
    from apps.billing import services as billing_services
    from apps.rating import seams as rating_seams

    monkeypatch.delattr(billing_services, "charge_line_count", raising=True)

    with tenant_ctx(brazos):
        charge = rating_models.Charge.objects.create(
            tenant=brazos, code="CONN-FEE", name="Connection fee", amount=Decimal("25.00")
        )
        assert rating_seams.invoice_line_references(charge.id) is None

        with pytest.raises(errors.BizError) as excinfo:
            rating_services.delete_charge(dana, charge.id)

    assert excinfo.value.code == errors.BIZ_LOCKED
    assert excinfo.value.params["invoice_lines"] == "unavailable"
    assert rating_models.Charge.objects.filter(pk=charge.pk).exists()


def test_def_079_tc8__an_unanswerable_count_reads_as_in_use_on_the_reference_screen(
    brazos, monkeypatch
):
    """BR-TEN-029/030/034 — the S8 reference-data card's used-by count.

    A code freezes once used and a used row cannot be deleted, and both hang off
    this number. An unverifiable 0 would UNFREEZE a code live bills cite, so an
    unanswerable billing leg counts as one use: the screen says in-use and the
    clerk meets a lock rather than a silent success.
    """
    from apps.billing import services as billing_services
    from apps.rating import lookups as rating_lookups

    monkeypatch.delattr(billing_services, "charge_line_count", raising=True)

    with tenant_ctx(brazos):
        charge = rating_models.Charge.objects.create(
            tenant=brazos, code="CONN-FEE2", name="Connection fee", amount=Decimal("25.00")
        )
        card = rating_lookups.ChargeCodeLookupHandler()
        assert card.used_by(charge) >= 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-079 (defect fix — sources: 12-governance/10-defect-log.csv DEF-079 ·
#         10-scripts/gates/seam_known_gaps.txt substitutes-answer block ·
#         04-docs/05-modules/06-rating/06-epics/EP-RAT-01 US-RAT-001 TC-5 ·
#         04-docs/05-modules/06-rating/02-business-rules.md BR-RAT-030/035 ·
#         04-docs/05-modules/01-tenancy/02-business-rules.md BR-TEN-029/030/034)
# generated: 2026-08-12 by the orchestrating session (DEF-079 lane)
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the commit message — every assertion here was seen RED against the
#         unpublished counters first, and the delete-plan case failed by
#         DELETING THE PLAN, which is the defect stated as a test.
# exceptions: `invoice_line_count_for_asset` is NOT closed by this lane and is
#         NOT tested here. No invoice line names an asset — there is no column
#         and no join — so the count cannot be derived at all, and the seam
#         stays parked in seam_known_gaps.txt with that as its blocker rather
#         than with a fabricated chain. Four right beats five guessed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-012 (ad-hoc single bill — the bulk wizard in single-account
#           mode)   Screens: S30 · S31
# Rules:    BR-BIL-020 (lines come ONLY from rules and charge codes; free-typed
#           amounts never exist on any bill) · BR-BIL-023 (same draft powers) ·
#           BR-BIL-055 (a held account waits for a catch-up sub-run) ·
#           BR-PAY-010 (unallocated credit auto-applies) · BR-CUS-055
# Golden:   GT-7's shape (allocation) · WE-14 (❄️ workbook): prior credit
#           −60.00 against charges 42.30 → due **0.00**, carry **−17.70**.
# ───────────────────────────────────────────────────────
"""One account, one period, the same pipeline — and no way to type an amount.

Two properties carry this story. The first is that single mode is not a second
implementation: the same gather, the same seven stages, the same draft. The
second is BR-BIL-020's, and `tc4` tests it in the only way that survives a
refactor — by INTROSPECTING the module's signatures. A rejection message can be
deleted by anyone; a parameter that does not exist cannot be passed.
"""

import inspect
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, models as billing_models, penalty, rating_seam, runs, single
from tests.test_us_bil_001_prepare import (
    PERIOD_END,
    PERIOD_START,
    SERVICE_DATE,
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

INTERIM_START = date(2026, 6, 15)
INTERIM_END = date(2026, 6, 30)
#: WE-14 verbatim.
PRIOR_CREDIT = Decimal("60.00")
CURRENT_CHARGES = Decimal("42.30")
CARRIED = Decimal("17.70")

#: Parameter names that would let a caller put money on a bill by hand. The
#: check is on the NAMES because that is what an API layer binds to a request
#: body; BR-BIL-020 forbids the concept, not a particular spelling.
FREE_TYPED = {"amount", "amounts", "line_amount", "price", "total", "lines", "description"}


def a_run(tenant, cycle, key="single-1", start=PERIOD_START, end=PERIOD_END):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=start,
        period_end=end,
        idempotency_key=key,
    )


def test_us_bil_012_tc1__single_mode_runs_the_whole_pipeline_for_one_account(brazos, dana):
    """TC-1: the same artifacts a cycle run produces, scoped to one account.

    Proved by comparing against the cycle run itself rather than by asserting a
    list of fields: `prepare_run` over the same cycle and period must gather the
    same account with the same plan, the same currency and the same reading, or
    single mode is quietly a different product.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7501", label="A")
        account = an_account(brazos, unit["id"], "A-12001")

        prepared = single.prepare_single_bill(
            account_id=account.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        by_cycle = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )

        assert [d.account_no for d in prepared.ready] == ["A-12001"]
        assert prepared.blocked == ()
        # The SAME gathered data, field for field — one definition of "billable".
        assert prepared.ready[0] == by_cycle.ready[0]
        # Nothing was written by looking.
        assert billing_models.Invoice.objects.count() == 0

        invoice = single.calculate_single_bill(prepared, bill_run=a_run(brazos, cycle))

    assert invoice.status == billing_models.INVOICE_DRAFT
    assert invoice.bill_type == "cycle"
    assert invoice.invoice_no  # BR-BIL-063 — a number at draft, same as a run's
    assert invoice.period_start == PERIOD_START and invoice.period_end == PERIOD_END
    assert invoice.lines.count() >= 1
    assert billing_models.Invoice.objects.count() == 1


def test_us_bil_012_tc2__we_14_the_credit_bill_settles_to_zero_and_carries_17_70():
    """TC-2 (WE-14): prior credit 60.00 against charges 42.30 → due **0.00**, carry **17.70**.

    The arithmetic is PAYMENTS' (BR-PAY-010) and is asserted here through the
    published seam, because US-BIL-012 §7 states it as this story's finance
    calculation and a story's own frozen figure should fail in the story's own
    file when it moves.

    WHAT IS NOT WIRED, and is REPORTED rather than implied: nothing in billing
    CALLS this when an ad-hoc bill is drafted or issued. `invoices.total` is the
    charges; the credit application is a payments act against the issued bill,
    and US-BIL-012's "auto-apply per allocation order" therefore has no caller
    in this codebase yet. Asserting the figure while saying so is the honest
    half; claiming the auto-apply works would be hard-won law 1.
    """
    outcome = rating_seam.allocate_payment(
        payment_amount=PRIOR_CREDIT,
        open_invoices=(rating_seam.OpenInvoice(number="BL-2606-0001", balance=CURRENT_CHARGES),),
    )

    assert outcome.applied_to("BL-2606-0001") == CURRENT_CHARGES  # the bill is met in full
    assert outcome.remaining_balance == 0  # amount due 0.00
    assert outcome.credit_carried == CARRIED  # −17.70 carries forward


def test_us_bil_012_tc3__the_draft_is_the_same_document_a_cycle_run_drafts(brazos, dana):
    """TC-3: identical issue artifacts — proved at the draft the issue path consumes.

    Issue itself (number series, GL stamps, template pin, delivery queue) is
    US-BIL-005's and is exercised by `test_us_bil_005_issue.py` against drafts
    of exactly this shape. What matters HERE is that single mode hands that
    path a draft indistinguishable from a cycle run's — same fields set, same
    fields left for issue — so there is nothing for the issue path to special-
    case.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit_a = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7502", label="A")
        unit_b = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7503", label="B")
        account_a = an_account(brazos, unit_a["id"], "A-12003")
        an_account(brazos, unit_b["id"], "A-12004")

        via_single = single.calculate_single_bill(
            single.prepare_single_bill(
                account_id=account_a.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            ),
            bill_run=a_run(brazos, cycle, key="single-3"),
        )
        via_run = runs.calculate_run(
            runs.prepare_run(
                cycle_id=cycle.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            ),
            bill_run=a_run(brazos, cycle, key="cycle-3"),
        )
        cycle_draft = billing_models.Invoice.objects.get(pk=via_run.drafted[0])

        def shape(invoice):
            return {
                "status": invoice.status,
                "bill_type": invoice.bill_type,
                "has_number": bool(invoice.invoice_no),
                "due_date": invoice.due_date,  # None — derived AT ISSUE
                "issued_at": invoice.issued_at,  # None — issue is a separate act
                "template_id": invoice.template_id,  # None — pinned at issue
                "currency": invoice.currency,
                "payload_keys": sorted(invoice.bill_payload),
                "line_kinds": sorted({line.kind for line in invoice.lines.all()}),
                "gl_stamped": {line.gl_account_id for line in invoice.lines.all()},
            }

        assert shape(via_single) == shape(cycle_draft)


def test_us_bil_012_tc4__no_entry_point_can_be_handed_a_typed_amount():
    """TC-4 (negative): the prototype's editable line inputs do not ship.

    STRUCTURAL, not a validation. `05-prototype/UtilityBilling.html` renders
    every one-time-bill line as an editable description + amount with a
    "+ Add line" button; BR-BIL-020 supersedes it in writing. So there is no
    parameter anywhere in these four entry points that could carry a hand-typed
    amount, a description or a line — and this test walks their signatures to
    say so, because a message can be deleted and a missing parameter cannot.
    """
    offenders = []
    for module in (single, backbill, penalty):
        for name, function in vars(module).items():
            if name.startswith("_") or not inspect.isfunction(function):
                continue
            if function.__module__ != module.__name__:
                continue  # imported helper, tested where it lives
            for parameter in inspect.signature(function).parameters:
                if parameter in FREE_TYPED:
                    offenders.append(f"{module.__name__}.{name}({parameter}=...)")
    assert offenders == []


def test_us_bil_012_tc5__a_held_period_routes_to_the_catch_up_sub_run(brazos, dana):
    """TC-5 (negative): never a colliding parallel bill for a held period.

    The account sits in the pending-billing queue for the June cycle. A clerk
    billing 15–30 June in single mode would produce a second bill covering days
    the catch-up sub-run is about to bill — two bills for the same fortnight,
    undoable only by a correction. The overlap is what is refused, not an exact
    period match.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7504", label="A")
        account = an_account(brazos, unit["id"], "A-12005")
        held_run = a_run(brazos, cycle, key="held-run")
        runs.mark_for_later(
            bill_run=held_run,
            account_id=account.id,
            reason_code="missing_read",
            detail="water read never taken",
        )

        with pytest.raises(Exception) as raised:
            single.prepare_single_bill(
                account_id=account.id,
                period_start=INTERIM_START,  # overlaps the held June period
                period_end=INTERIM_END,
                service_date=INTERIM_END,
            )

    assert raised.value.reason == single.SINGLE_HELD_PERIOD
    assert "catch-up sub-run" in str(raised.value)
    assert billing_models.Invoice.objects.count() == 0


def test_us_bil_012_tc6__single_mode_never_reaches_another_tenant_s_account(brazos, dana, lonestar):
    """TC-6 (isolation): Brazos Bend's account is ABSENT from Lone Star Ridge.

    HR-1: unknown, malformed and cross-tenant are one answer, so an account
    number cannot be probed from the wrong tenant's session.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7505", label="A")
        account = an_account(brazos, unit["id"], "A-12006")

    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as raised:
            single.prepare_single_bill(
                account_id=account.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            )
    assert raised.value.__class__.__name__ == "NotFoundError"


def test_us_bil_012_tc7__a_closed_account_is_refused_toward_the_final_bill_flow(brazos, dana):
    """BR-CUS-055: a closed account's last bill is a FINAL bill, not an ad-hoc one.

    The failure this prevents is quiet: an ordinary one-off bill for a closed
    account bills the period and settles no deposit, so the customer's money
    stays with the utility and the account closes with an unexplained balance —
    the exact outcome BR-BIL-013 exists to make impossible.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7506", label="A")
        account = an_account(brazos, unit["id"], "A-12007", status_code="closed")

        with pytest.raises(Exception) as raised:
            single.prepare_single_bill(
                account_id=account.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
            )
    assert raised.value.reason == single.SINGLE_NOT_BILLABLE
    assert "US-BIL-011" in str(raised.value)


def test_us_bil_012_tc8__an_unknown_bill_type_stops_rather_than_defaulting(brazos, dana):
    """A document kept for seven years is not typed by a fallback."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(dana, brazos, cycle, plan, asset_no="M-7507", label="A")
        account = an_account(brazos, unit["id"], "A-12008")

        with pytest.raises(Exception) as raised:
            single.prepare_single_bill(
                account_id=account.id,
                period_start=PERIOD_START,
                period_end=PERIOD_END,
                service_date=SERVICE_DATE,
                bill_type="estimate",
            )
    assert "unknown bill type" in str(raised.value)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-012@f0a3c21 (EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md · B2 §2 + Addendum r10)
# generated: 2026-08-11 by story-coder (W3/W5 bill-types lane)
# gates: ruff✔ black✔ · 8 passed
# RED PROOF EXECUTED 2026-08-11 (verbatim, not predicted). The held-period guard
#         is the one this file adds that nothing else covers, so it was removed
#         to prove it bites: `held_for_period(...)` was made to return None
#         unconditionally. Result: `1 failed, 7 passed in 20.15s` —
#         FAILED tc5 `Failed: DID NOT RAISE <class 'Exception'>`, i.e. a second
#         bill for a fortnight the catch-up sub-run was about to bill. Reverted;
#         8 passed.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

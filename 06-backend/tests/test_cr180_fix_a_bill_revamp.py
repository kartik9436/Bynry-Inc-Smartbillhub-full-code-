# ── Trace ──────────────────────────────────────────────
# Change:   CR-180-BRC10 — Fix a bill, revamped: the SERVER half, B1–B10
#           (12-governance/change-requests/CR-180-BRC10-fix-a-bill-revamp.md,
#           "The contract between server and screen")
# Journey:  08-qa/01-e2e/journeys/J-FIX-TWENTY-the-fix-a-bill-scenario-suite.md
# Rules:    BR-BIL-004 (the original never changes) · BR-BIL-011 (two balanced
#           entries, never one net entry) · BR-BIL-014 (no money-bearing write
#           before approval — the preview writes NOTHING) · BR-BIL-018 (back-
#           bill window) · BR-BIL-041/042 (R > C > D, derived across rows) ·
#           BR-BIL-044 (approval binds the figures; moved figures refuse) ·
#           BR-BIL-045 (posting period named before confirm) · BR-BIL-047 (one
#           bill, one transaction, no batch rollback) · BR-BIL-048 (one open
#           case per bill) · BR-PAY-010/031 (re-allocation is new rows) ·
#           BR-TEN-038 (a closed month posts forward) · CLAUDE.md rule 1–8 ·
#           hard-won law 14 (run the money cases on PostgreSQL too)
# ───────────────────────────────────────────────────────
"""Fix a bill, revamped — the server half, proved on real rows.

Every figure here is PRICED BY THE ENGINE from a meter read through the real
gather → stages → price path; nothing in this file is a stubbed recomputation.
The world is the repo's own Silver Creek water ladder (`core.sample_fixture`):
$4.00 for the first 5 kgal, $6.50 to 15 kgal, $8.00 above, base $8.00.

    July, register 1150 → 1200 = 50 kgal:
        5 × 4.00 + 10 × 6.50 + 35 × 8.00 = 20.00 + 65.00 + 280.00 = 365.00
        + base 8.00                                                = 373.00

    The reading should have been 1180 → 30 kgal:
        20.00 + 65.00 + 15 × 8.00 = 205.00 + 8.00                  = 213.00
        delta                                                      = −160.00

Run it on PostgreSQL as well (hard-won law 14 — the execution is a multi-
statement money write inside one transaction):

    cd 06-backend && CELERY_BROKER_URL=memory:// JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest -q tests/test_cr180_fix_a_bill_revamp.py \\
      --ds=config.settings.pgtest --create-db
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest
from django.db.models import Sum

from apps.billing import corrections_api, issue, models, single, templates_service
from apps.billing.correction_models import (
    CASE_DONE,
    CASE_OPEN,
    CASE_PENDING_APPROVAL,
    CorrectionCase,
    CorrectionCaseBill,
    InvoiceDocumentInstance,
)
from apps.customers import models as customer_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.test_def_438_parity import _water_plan
from tests.test_us_bil_005_release_gate import a_release
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import RATIFIED_BAND, a_meter, commit_read
from tests.test_us_ten_helpers import api_call
from tests.test_w3_billing_models import a_cycle

pytestmark = pytest.mark.django_db

ZERO = Decimal("0")
JUL_1 = date(2026, 7, 1)
JUL_31 = date(2026, 7, 31)
JUN_1 = date(2026, 6, 1)
JUN_30 = date(2026, 6, 30)
AS_OF = date(2026, 8, 15)
ISSUED_AT = datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
CORRECTED_AT = datetime(2026, 8, 16, 10, 0, tzinfo=UTC)
TEMPLATE_ID = "9f0e6a52-3c14-4a7d-8f21-2b6d0c9e5a71"
TEMPLATE_VERSION = 3

ORIGINAL_JULY = Decimal("373.00")
CORRECTED_JULY = Decimal("213.00")


# ═══════════════════════════════════════════════════════════════════════════
# THE WORLD — real plan, real meter, real reads, real issued bills
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture(autouse=True)
def _the_rebill_template(monkeypatch):
    """The rebill's template pin (BR-BIL-026) — the tenant has no published
    template in this harness, so the resolution is named, not hidden."""
    monkeypatch.setattr(
        templates_service,
        "resolve_for",
        lambda **kwargs: (
            SimpleNamespace(pk=TEMPLATE_ID),
            SimpleNamespace(version_no=TEMPLATE_VERSION),
        ),
    )


def _an_account(tenant, actor, plan, *, n: int, reads: list[tuple[str, str, str]]):
    """One account, one unit, one water meter, the given `(day, prior, value)`
    committed reads. Unique per `n` so a test can hold several."""
    from apps.metering import services as metering_services

    premises = make_premises(
        actor, address_line=f"{100 + n} Quarry Hill Rd", services_available=["water"]
    )
    unit = make_unit(actor, premises["id"], label=f"Unit {n}", services=["water"])
    asset = a_meter(
        actor,
        asset_no=f"M-18{n:03d}",
        service="water",
        uom=fixture.WATER_UOM,
        unit_id=unit["id"],
        size_class=RATIFIED_BAND,
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    for day, prior, value in reads:
        commit_read(
            actor,
            asset["id"],
            day=day,
            value=value,
            prior_value=prior,
            consumption=Decimal(value) - Decimal(prior),
            unit=fixture.WATER_UOM,
        )
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=f"FIX-{n:04d}",
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code="residential"),
    )
    return account, asset


def _a_run(tenant, actor, *, start: date, end: date, key: str, bill_date: date):
    run = models.BillRun.objects.create(
        tenant=tenant,
        cycle=a_cycle(tenant),
        period_start=start,
        period_end=end,
        bill_date=bill_date,
        idempotency_key=key,
    )
    a_release(tenant, run, actor)
    return run


def _issue(actor, account, run, *, start: date, end: date, issued_at=ISSUED_AT):
    prepared = single.prepare_single_bill(
        account_id=account.id, period_start=start, period_end=end, service_date=end
    )
    draft = single.calculate_single_bill(prepared, bill_run=run)
    return issue.issue_invoice(
        draft,
        issued_at=issued_at,
        template_id=TEMPLATE_ID,
        template_version=TEMPLATE_VERSION,
        actor=actor,
    )


def _july_world(tenant, actor, *, n: int = 1, plan=None, run=None):
    plan = plan or _water_plan(tenant)
    account, asset = _an_account(
        tenant,
        actor,
        plan,
        n=n,
        # June's reading is the dial July opens at — a real prior row, so a
        # corrected July reading is measured from it (metering's supersede
        # re-derives the prior from the meter's history, not from the fixture).
        reads=[("2026-06-28", "1100", "1150"), ("2026-07-28", "1150", "1200")],
    )
    run = run or _a_run(
        tenant, actor, start=JUL_1, end=JUL_31, key=f"fix|jul|{n}", bill_date=date(2026, 8, 1)
    )
    invoice = _issue(actor, account, run, start=JUL_1, end=JUL_31)
    assert invoice.total == ORIGINAL_JULY, "the engine prices the fixture ladder at 373.00"
    return SimpleNamespace(plan=plan, account=account, asset=asset, run=run, invoice=invoice)


# ═══════════════════════════════════════════════════════════════════════════
# THE HTTP SURFACE — the contract's four routes
# ═══════════════════════════════════════════════════════════════════════════
def _call(view, method, tenant, actor, *, role="system_admin", data=None, query=None, **kw):
    return api_call(
        view, method, user=actor.user, role=role, tenant=tenant, data=data, query=query, **kw
    )


def _one_customer(world, *bills) -> dict[str, Any]:
    return {
        "kind": "account",
        "account_id": str(world.account.id),
        "invoice_ids": [str(bill.pk) for bill in (bills or (world.invoice,))],
    }


def _preview(tenant, actor, scope, items, *, as_of=AS_OF):
    return _call(
        corrections_api.correction_preview,
        "post",
        tenant,
        actor,
        data={"scope": scope, "items": items, "as_of": as_of.isoformat()},
    )


def _send(tenant, actor, scope, items, preview_hash, *, as_of=AS_OF, role="billing_clerk"):
    return _call(
        corrections_api.correction_cases,
        "post",
        tenant,
        actor,
        role=role,
        data={
            "scope": scope,
            "items": items,
            "as_of": as_of.isoformat(),
            "preview_hash": preview_hash,
        },
    )


def _approve_and_issue(tenant, actor, case_id, preview_hash):
    return _call(
        corrections_api.correction_case_approve_and_issue,
        "post",
        tenant,
        actor,
        data={
            "preview_hash": preview_hash,
            "on_date": "2026-08-16",
            "issued_at": CORRECTED_AT.isoformat(),
        },
        case_id=case_id,
    )


# ── DEF-BIL-10091 — a BULK act is a background job: 202, run, read back ────
def _job_state(tenant, actor, job_id, per=1000):
    return _call(
        corrections_api.correction_job, "get", tenant, actor, query={"per": per}, job_id=job_id
    ).data


def _ran(tenant, actor, accepted):
    """Run the job a 202 queued (the suite runs JOBS_EAGER=False) and read it."""
    from core import jobs as core_jobs

    assert accepted.status_code == 202, accepted.data
    core_jobs.run_pending(accepted.data["job_id"])
    return _job_state(tenant, actor, accepted.data["job_id"])


def _bulk_preview(tenant, actor, scope, items, *, as_of=AS_OF):
    accepted = _preview(tenant, actor, scope, items, as_of=as_of)
    state = _ran(tenant, actor, accepted)
    if state["refusal"] is not None:
        return SimpleNamespace(status_code=422, data=state["refusal"], job_id=state["job_id"])
    return SimpleNamespace(status_code=200, data=state["preview"], job_id=state["job_id"])


def _bulk_send(tenant, actor, scope, items, preview, *, as_of=AS_OF):
    accepted = _call(
        corrections_api.correction_cases,
        "post",
        tenant,
        actor,
        role="billing_clerk",
        data={
            "scope": scope,
            "items": items,
            "as_of": as_of.isoformat(),
            "preview_hash": preview.data["preview_hash"],
            "preview_job_id": preview.job_id,
        },
    )
    state = _ran(tenant, actor, accepted)
    if state["refusal"] is not None:
        return SimpleNamespace(status_code=422, data=state["refusal"])
    return SimpleNamespace(status_code=201, data=state["case"])


def _bulk_approve(tenant, actor, case_id, preview_hash):
    state = _ran(tenant, actor, _approve_and_issue(tenant, actor, case_id, preview_hash))
    if state["refusal"] is not None:
        return SimpleNamespace(status_code=422, data=state["refusal"])
    return SimpleNamespace(status_code=200, data=state["case"])


def _bulk_execute(tenant, actor, case_id):
    accepted = _call(
        corrections_api.correction_case_execute,
        "post",
        tenant,
        actor,
        data={"on_date": "2026-08-16", "issued_at": CORRECTED_AT.isoformat()},
        case_id=case_id,
    )
    state = _ran(tenant, actor, accepted)
    return SimpleNamespace(status_code=200, data=state["case"])


def _wrong_read(world, value="1180", **extra):
    return {"reason": "wrong_read", "item": str(world.asset["id"]), "value": value, **extra}


def _counts() -> dict[str, int]:
    """Every table a correction could write, counted — BR-BIL-014 by COUNTING."""
    from apps.audit import models as audit_models
    from apps.ledger import models as ledger_models
    from apps.metering import models as metering_models
    from apps.notifications import models as notification_models
    from apps.payments import models as payment_models

    from apps.billing.correction_models import CorrectionCaseItem

    return {
        "correction_cases": CorrectionCase.objects.count(),
        "correction_case_bills": CorrectionCaseBill.objects.count(),
        "correction_case_items": CorrectionCaseItem.objects.count(),
        "invoices": models.Invoice.objects.count(),
        "invoice_lines": models.InvoiceLine.objects.count(),
        "credit_notes": models.CreditNote.objects.count(),
        "bill_runs": models.BillRun.objects.count(),
        "journal_entries": ledger_models.JournalEntry.objects.count(),
        "journal_lines": ledger_models.JournalLine.objects.count(),
        "allocations": payment_models.Allocation.objects.count(),
        "outbound_messages": notification_models.OutboundMessage.objects.count(),
        "audit_log": audit_models.AuditLog.objects.count(),
        "meter_reads": metering_models.MeterRead.objects.count(),
        "read_corrections": metering_models.ReadCorrection.objects.count(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# B7 · THE PREVIEW WRITES NOTHING — and prices the typed reading (B5)
# ═══════════════════════════════════════════════════════════════════════════
def test_b7_b5_the_preview_prices_the_typed_reading_and_writes_nothing(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        before = _counts()
    trail_before = len(audit_rows)
    response = _preview(brazos, dana, _one_customer(world), [_wrong_read(world)])
    assert response.status_code == 200, response.data
    with tenant_ctx(brazos):
        assert _counts() == before, "POST /corrections/preview wrote a row (BR-BIL-014)"
    assert len(audit_rows) == trail_before, "the preview wrote an audit row"

    body = response.data
    assert body["correction_class"] == "restatement"
    assert body["writes"] == "nothing"
    assert len(body["bills"]) == 1
    bill = body["bills"][0]
    assert Decimal(bill["original_total"]) == ORIGINAL_JULY
    assert Decimal(bill["corrected_total"]) == CORRECTED_JULY
    assert Decimal(bill["delta"]) == CORRECTED_JULY - ORIGINAL_JULY
    assert bill["direction"] == "down"
    # B8 — the posting month (July is open, so July) and the new due date.
    # AMENDED 2026-10-13 (PO ruling, decision log "RULED 2026-10-13" item 2):
    # the CORRECTION date + the cycle's 21 days, 15 Aug + 21 = 5 Sep. It read
    # the run's bill date 1 Aug + 21 = 22 Aug until that ruling.
    assert bill["posting_period"] == "2026-07"
    assert bill["posting_date"] == "2026-07-31"
    assert bill["posting_forwarded"] is False
    assert bill["new_due_date"] == "2026-09-05"
    # F4 — the bill by service and rate type, old beside new.
    old_water = bill["layout"]["old"]["services"][0]
    new_water = bill["layout"]["new"]["services"][0]
    assert old_water["service"] == "water" and old_water["rate_type"] == "tiered"
    assert sum(Decimal(line["quantity"]) for line in old_water["usage"]) == Decimal("50")
    assert sum(Decimal(line["quantity"]) for line in new_water["usage"]) == Decimal("30")
    assert Decimal(bill["layout"]["new"]["total"]) == CORRECTED_JULY
    # The nine sections are served for one customer (BR-BIL-044).
    assert list(bill["sections"]) == [
        "what_is_being_corrected",
        "the_lines",
        "the_money",
        "the_documents_that_will_exist",
        "the_ledger_handoff",
        "the_customers_balance",
        "what_the_customer_will_receive",
        "warnings",
        "the_gate",
    ]
    assert body["preview_hash"]


# ═══════════════════════════════════════════════════════════════════════════
# B7 · THE CASE IS OPENED AT SEND, AND MOVED FIGURES REFUSE (S19 / S20)
# ═══════════════════════════════════════════════════════════════════════════
def test_b7_b3_send_opens_the_case_with_its_items_and_refuses_moved_figures(brazos, dana):
    from apps.billing.correction_models import CorrectionCaseItem

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    scope, items = _one_customer(world), [_wrong_read(world)]
    preview = _preview(brazos, dana, scope, items)
    assert preview.status_code == 200, preview.data

    # S19 — a hash that is not what the server now computes is refused, and
    # nothing is written.
    with tenant_ctx(brazos):
        before = _counts()
    moved = _send(brazos, dana, scope, items, "0" * 64)
    assert moved.status_code == 422, moved.data
    assert moved.data["message_key"] == "billing.correction.figuresMoved"
    with tenant_ctx(brazos):
        assert _counts() == before

    sent = _send(brazos, dana, scope, items, preview.data["preview_hash"])
    assert sent.status_code == 201, sent.data
    assert sent.data["status"] == CASE_PENDING_APPROVAL
    assert sent.data["preview_hash"] == preview.data["preview_hash"]
    with tenant_ctx(brazos):
        case = CorrectionCase.objects.get(pk=sent.data["id"])
        rows = list(CorrectionCaseItem.objects.filter(case=case).order_by("position"))
        assert [(row.reason, row.item, row.value) for row in rows] == [
            ("wrong_read", str(world.asset["id"]), "1180")
        ]
        assert rows[0].bill_ids is None
        assert CorrectionCaseBill.objects.filter(case=case).count() == 1
        # S20 — the bill is held by an OPEN case now, so a second Send refuses.
    again = _send(brazos, dana, scope, items, preview.data["preview_hash"])
    assert again.status_code == 422, again.data


def test_s20_a_clerk_who_only_previews_leaves_the_bill_free(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    scope, items = _one_customer(world), [_wrong_read(world)]
    first = _preview(brazos, dana, scope, items)
    second = _preview(brazos, dana, scope, items)
    assert first.status_code == second.status_code == 200
    assert first.data["preview_hash"] == second.data["preview_hash"], "same facts, same hash"


# ═══════════════════════════════════════════════════════════════════════════
# B1 · ONE ACCOUNT, SEVERAL BILLS, ONE CASE — and the scope read (resolve)
# ═══════════════════════════════════════════════════════════════════════════
def _two_month_world(tenant, actor):
    plan = _water_plan(tenant)
    account, asset = _an_account(
        tenant,
        actor,
        plan,
        n=7,
        reads=[("2026-06-28", "1100", "1150"), ("2026-07-28", "1150", "1200")],
    )
    june_run = _a_run(
        tenant, actor, start=JUN_1, end=JUN_30, key="fix|jun", bill_date=date(2026, 7, 1)
    )
    july_run = _a_run(
        tenant, actor, start=JUL_1, end=JUL_31, key="fix|jul2", bill_date=date(2026, 8, 1)
    )
    june = _issue(actor, account, june_run, start=JUN_1, end=JUN_30)
    july = _issue(actor, account, july_run, start=JUL_1, end=JUL_31)
    return SimpleNamespace(
        plan=plan, account=account, asset=asset, june=june, july=july, invoice=july
    )


def test_b1_one_account_several_bills_are_one_case_each_bill_with_its_own_class(brazos, dana):
    with tenant_ctx(brazos):
        world = _two_month_world(brazos, dana)
    scope = _one_customer(world, world.june, world.july)
    items = [
        # the July reading was wrong — applies to July only
        _wrong_read(world, bill_ids=[str(world.july.pk)]),
        # a goodwill credit on June only
        {
            "reason": "goodwill",
            "item": "credit",
            "value": "25.00",
            "bill_ids": [str(world.june.pk)],
        },
    ]
    response = _preview(brazos, dana, scope, items)
    assert response.status_code == 200, response.data
    body = response.data
    assert body["correction_class"] == "restatement", "R > C across the rows (BR-BIL-042)"
    by_no = {bill["invoice_no"]: bill for bill in body["bills"]}
    assert by_no[world.july.invoice_no]["class"] == "restatement"
    assert Decimal(by_no[world.july.invoice_no]["corrected_total"]) == CORRECTED_JULY
    assert by_no[world.june.invoice_no]["class"] == "credit_only"
    assert by_no[world.june.invoice_no]["goodwill"] == "25.00"
    # The BILL is untouched (BillImpact.delta 0, PO 2026-08-11); A3's delta is
    # what the customer is better off by — the goodwill credit.
    assert Decimal(by_no[world.june.invoice_no]["delta"]) == Decimal("-25.00")
    assert by_no[world.june.invoice_no]["credit_note"]["total"] == "-25.0000"

    sent = _send(brazos, dana, scope, items, body["preview_hash"])
    assert sent.status_code == 201, sent.data
    assert len(sent.data["bills_detail"]) == 2, "several bills of ONE account in ONE case"


def test_b1_resolve_one_customer_lists_the_bills_and_excludes_a_draft(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        draft_run = _a_run(
            brazos, dana, start=JUN_1, end=JUN_30, key="fix|draft", bill_date=date(2026, 7, 1)
        )
        draft = models.Invoice.objects.create(
            tenant=brazos,
            account=world.account,
            bill_run=draft_run,
            service_date=JUN_30,
            period_start=JUN_1,
            period_end=JUN_30,
            subtotal=Decimal("10.00"),
            tax_total=ZERO,
            total=Decimal("10.00"),
        )
    response = _call(
        corrections_api.correction_scope_resolve,
        "get",
        brazos,
        dana,
        query={
            "scope_kind": "account",
            "account_id": str(world.account.id),
            "invoice_ids": [str(world.invoice.pk), str(draft.pk)],
        },
    )
    assert response.status_code == 200, response.data
    assert [row["invoice_id"] for row in response.data["results"]] == [str(world.invoice.pk)]
    assert response.data["excluded"] == [
        {
            "invoice_id": str(draft.pk),
            "invoice_no": draft.invoice_no,
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "code": "draft",
        }
    ]


# ═══════════════════════════════════════════════════════════════════════════
# B2 · A PRICE MISTAKE ACROSS RUNS
# ═══════════════════════════════════════════════════════════════════════════
def test_b2_a_price_mistake_finds_the_bills_that_used_the_schedule_across_runs(brazos, dana):
    with tenant_ctx(brazos):
        world = _two_month_world(brazos, dana)
        tariff_id = str(world.july.lines.filter(kind="usage").first().tariff_version.tariff_id)

    def _resolve(start, end):
        return _call(
            corrections_api.correction_scope_resolve,
            "get",
            brazos,
            dana,
            query={
                "scope_kind": "price_mistake",
                "period_start": start,
                "period_end": end,
                "wrong_kind": "rate",
                "wrong_id": tariff_id,
            },
        )

    both = _resolve("2026-06-01", "2026-07-31")
    assert both.status_code == 200, both.data
    assert {row["invoice_id"] for row in both.data["results"]} == {
        str(world.june.pk),
        str(world.july.pk),
    }, "two runs, one schedule"
    july_only = _resolve("2026-07-01", "2026-07-31")
    assert [row["invoice_id"] for row in july_only.data["results"]] == [str(world.july.pk)]

    # A price mistake takes only the re-price reasons (decision log item 3).
    # DEF-BIL-10091: a bulk preview is a job, so the refusal is its answer.
    refused = _bulk_preview(
        brazos,
        dana,
        {
            "kind": "price_mistake",
            "period_start": "2026-06-01",
            "period_end": "2026-07-31",
            "wrong_kind": "rate",
            "wrong_id": tariff_id,
        },
        [{"reason": "goodwill", "item": "credit", "value": "5.00"}],
    )
    assert refused.status_code == 422
    assert refused.data["message_key"] == "billing.correction.reasonNotForScope"


# ═══════════════════════════════════════════════════════════════════════════
# B4 · RE-PRICE FROM THE ITEMS — one case per reason
# ═══════════════════════════════════════════════════════════════════════════
def _single_bill(response):
    assert response.status_code == 200, response.data
    assert len(response.data["bills"]) == 1
    return response.data["bills"][0]


def test_b4_wrong_rate_picks_the_schedule_and_its_version(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        old_version = world.invoice.lines.filter(kind="usage").first().tariff_version
        # A second version of the same schedule whose ladder is $1.00 dearer per
        # tier. The clerk picks it explicitly.
        # The schedule's versions may not overlap (`ex_tariff_versions_no_overlap`),
        # so the version in force is closed the day before the new one starts.
        rating_models.TariffVersion.objects.filter(pk=old_version.pk).update(
            effective_to=date(2026, 12, 31)
        )
        new_version = rating_models.TariffVersion.objects.create(
            tenant=brazos,
            tariff=old_version.tariff,
            model="tiered",
            base_charge=old_version.base_charge,
            uom=fixture.WATER_UOM,
            currency="USD",
            effective_from=date(2027, 1, 1),
            base_charge_code_id=old_version.base_charge_code_id,
        )
        from tests.test_us_met_helpers import state_size_axis

        state_size_axis(new_version, "water")
        for seq, (lo, hi, price) in enumerate(fixture.WATER_TIERS, start=1):
            rating_models.RateTier.objects.create(
                tenant=brazos,
                tariff_version=new_version,
                seq=seq,
                from_qty=Decimal(lo),
                to_qty=None if hi is None else Decimal(hi),
                unit_price=Decimal(price) + Decimal("1"),
            )
    bill = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [
                {
                    "reason": "wrong_rate",
                    "item": str(old_version.tariff_id),
                    "value": str(new_version.pk),
                }
            ],
        )
    )
    # 50 kgal at $1.00 more on every unit = +50.00
    assert Decimal(bill["corrected_total"]) == ORIGINAL_JULY + Decimal("50.00")
    assert bill["class"] == "restatement"


def test_b4_wrong_plan_picks_the_plan_and_its_version(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    # A version that is not one of the plan's is refused by name.
    refused = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "wrong_plan", "item": str(world.plan.id), "value": "not-a-version"}],
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "billing.correction.itemInvalid"
    # The plan the bill already used, at its default version, re-prices to the
    # same figures — a wrong-plan row that changes nothing nets to zero and says so.
    same = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [{"reason": "wrong_plan", "item": str(world.plan.id)}],
        )
    )
    assert Decimal(same["delta"]) == ZERO
    assert "restatement_nets_to_zero" in {w["code"] for w in same["warnings"]}


def test_b4_missed_charge_adds_the_code_times_the_quantity(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(brazos),
        )
    bill = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [{"reason": "missed_charge", "item": "RECONNECT", "value": "2"}],
        )
    )
    assert Decimal(bill["corrected_total"]) == ORIGINAL_JULY + Decimal("30.00")
    charges = bill["layout"]["new"]["charges"]
    assert [(c["description"], c["quantity"], c["unit_price"], c["amount"]) for c in charges] == [
        ("Reconnection fee", "2", "15.00", "30.00")
    ]


def _a_revenue_account(tenant):
    from apps.ledger import models as ledger_models

    return (
        ledger_models.LedgerAccount.objects.filter(tenant=tenant, code__startswith="4")
        .values_list("id", flat=True)
        .first()
    )


def test_b4_wrong_deposit_is_untaxed_and_a_deposit_line(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    bill = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [{"reason": "wrong_deposit", "item": "DEP", "value": "150.00"}],
        )
    )
    assert Decimal(bill["corrected_total"]) == ORIGINAL_JULY + Decimal("150.00")
    deposits = bill["layout"]["new"]["deposits"]
    assert [(d["description"], d["amount"]) for d in deposits] == [("Security deposit", "150.00")]
    assert bill["layout"]["new"]["taxes"] == [], "a deposit is held money, never taxed"


def test_b4_wrong_period_prorates_the_base_days_over_days(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    bill = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [
                {
                    "reason": "wrong_period_or_service",
                    "item": "dates",
                    "value": "2026-07-01",
                    "value2": "2026-07-28",
                }
            ],
        )
    )
    # B4.3 prorates by service days ÷ cycle days, 28/31, the base AND the tier
    # widths (the engine's own rule — nothing here computes it):
    #   base 28/31 × 8.00 = 7.23
    #   tier 1  5 × 28/31 = 4.516129 kgal × 4.00 = 18.06
    #   tier 2 to 15 × 28/31 = 13.548387 → 9.032258 kgal × 6.50 = 58.71
    #   tier 3 the rest 36.451613 kgal × 8.00 = 291.61
    #   18.06 + 58.71 + 291.61 + 7.23 = 375.61
    base = bill["layout"]["new"]["services"][0]["base"]
    assert [line["amount"] for line in base] == ["7.23"]
    assert Decimal(bill["corrected_total"]) == Decimal("375.61")


def test_b4_theft_restates_the_assessed_usage(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    bill = _single_bill(
        _preview(
            brazos,
            dana,
            _one_customer(world),
            [{"reason": "theft_restated", "item": str(world.asset["id"]), "value": "80"}],
        )
    )
    # 80 kgal: 20.00 + 65.00 + 65 × 8.00 = 605.00 + 8.00 = 613.00 — upward,
    # and theft is EXEMPT from the back-bill window (BR-BIL-019).
    assert Decimal(bill["corrected_total"]) == Decimal("613.00")
    assert bill["direction"] == "up"


def test_b4_goodwill_alone_is_credit_only(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    response = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "goodwill", "item": "credit", "value": "25.00"}],
    )
    bill = _single_bill(response)
    assert response.data["correction_class"] == "credit_only"
    assert bill["goodwill"] == "25.00"
    assert bill["new_due_date"] is None, "no new bill on a credit-only correction"


def test_b6_a_reprint_row_serves_field_was_becomes(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        was = (world.invoice.bill_payload or {}).get("customer_name")
    response = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "customer_name", "item": "customer_name", "value": "Ben Bennett"}],
    )
    bill = _single_bill(response)
    assert response.data["correction_class"] == "document"
    assert bill["page_changes"] == [
        {"field": "customer_name", "was": was, "becomes": "Ben Bennett"}
    ]
    assert Decimal(bill["delta"]) == ZERO


def test_b4_mix_strongest_wins_and_every_row_rides_along(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    response = _preview(
        brazos,
        dana,
        _one_customer(world),
        [
            _wrong_read(world),
            {"reason": "goodwill", "item": "credit", "value": "10.00"},
            {"reason": "customer_name", "item": "customer_name", "value": "Ben Bennett"},
        ],
    )
    bill = _single_bill(response)
    assert response.data["correction_class"] == "restatement"
    assert bill["class"] == "restatement"
    assert Decimal(bill["corrected_total"]) == CORRECTED_JULY
    assert bill["goodwill"] == "10.00", "goodwill rides on the re-priced bill as a credit"
    assert bill["page_changes"][0]["becomes"] == "Ben Bennett"


def test_b4_an_item_naming_another_meter_is_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    refused = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "wrong_read", "item": "018f0000-0000-7000-8000-000000000099", "value": "1"}],
    )
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "billing.correction.notOnThisBill"


# ═══════════════════════════════════════════════════════════════════════════
# B9 · THE APPROVER AND THE INITIATOR, BY NAME
# ═══════════════════════════════════════════════════════════════════════════
def test_b9_the_case_serves_who_sent_it_by_name(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    scope, items = _one_customer(world), [_wrong_read(world)]
    preview = _preview(brazos, dana, scope, items)
    sent = _send(brazos, dana, scope, items, preview.data["preview_hash"])
    assert sent.status_code == 201, sent.data
    assert "initiated_by_name" in sent.data and "approved_by_name" in sent.data
    assert sent.data["approved_by_name"] is None
    assert sent.data["sections"]["the_gate"]["initiated_by_name"] == sent.data["initiated_by_name"]


# ═══════════════════════════════════════════════════════════════════════════
# B10 · APPROVE AND ISSUE — the record checks of J-FIX-TWENTY
# ═══════════════════════════════════════════════════════════════════════════
def _sent_case(tenant, actor, scope, items):
    preview = _preview(tenant, actor, scope, items)
    assert preview.status_code == 200, preview.data
    sent = _send(tenant, actor, scope, items, preview.data["preview_hash"])
    assert sent.status_code == 201, sent.data
    return preview.data, sent.data


def _pay(actor, account, amount):
    from uuid import uuid4

    from apps.payments import services as payment_services

    return payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=amount,
        posted_at=ISSUED_AT,
        cleared_at=ISSUED_AT,
        confirmation="4471",
        idempotency_reference=uuid4(),
    )


def test_b10_approve_and_issue_writes_every_record_the_walk_checks(brazos, dana, audit_rows):
    from apps.ledger import models as ledger_models
    from apps.metering import models as metering_models
    from apps.notifications import models as notification_models
    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        _pay(dana, world.account, ORIGINAL_JULY)  # S3 — paid in full before
        original_payload = dict(world.invoice.bill_payload)
        original_lines = list(
            world.invoice.lines.order_by("created_at", "id").values_list("description", "amount")
        )
    preview, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])

    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    result = done.data["result"]
    assert result["succeeded"] == [str(world.invoice.pk)]
    assert result["failed"] == []
    assert done.data["status"] == CASE_DONE
    assert done.data["approved_by_name"] is not None or done.data["approved_by"] is not None

    with tenant_ctx(brazos):
        # ── Bills ────────────────────────────────────────────────────────
        old = models.Invoice.objects.get(pk=world.invoice.pk)
        assert old.status == models.INVOICE_CORRECTED
        assert old.bill_payload == original_payload, "printed snapshot byte-identical"
        assert (
            list(old.lines.order_by("created_at", "id").values_list("description", "amount"))
            == original_lines
        ), "old lines untouched (hard rule 4)"
        new = models.Invoice.objects.get(corrects_invoice_id=old.pk)
        assert new.invoice_no and new.invoice_no != old.invoice_no
        assert new.total == CORRECTED_JULY == Decimal(preview["bills"][0]["corrected_total"])
        assert new.status in (models.INVOICE_ISSUED, models.INVOICE_PAID)
        # ── Credit notes ─────────────────────────────────────────────────
        notes = list(models.CreditNote.objects.filter(original_invoice=old))
        assert [note.amount for note in notes] == [-ORIGINAL_JULY]
        # ── Case rows ────────────────────────────────────────────────────
        row = CorrectionCaseBill.objects.get(case_id=sent["id"])
        assert row.status == "done"
        assert str(row.rebill_invoice_id) == str(new.pk)
        assert str(row.credit_note_id) == str(notes[0].pk)
        # ── General ledger: two balanced entries, never netted ───────────
        entries = list(
            ledger_models.JournalEntry.objects.filter(source_id__in=[notes[0].pk, new.pk])
        )
        assert len(entries) == 2
        for entry in entries:
            sides = {
                side: sum((line.amount for line in entry.lines.all() if line.side == side), ZERO)
                for side in ("debit", "credit")
            }
            assert sides["debit"] == sides["credit"], f"entry {entry.pk} unbalanced: {sides}"
            assert entry.entry_date == JUL_31, "July is open: the bill's own month"
        # net on AR = the Check step's delta (−160.00)
        from apps.billing import posting_seam

        ar = posting_seam._ar_account_id()
        net_ar = ZERO
        for entry in entries:
            for line in entry.lines.all():
                if str(line.ledger_account_id) == str(ar):
                    net_ar += line.amount if line.side == "debit" else -line.amount
        assert net_ar == CORRECTED_JULY - ORIGINAL_JULY
        # ── Payments: old allocations not edited, new rows to the new bill ─
        to_new = payment_models.Allocation.objects.filter(invoice_id=new.pk).aggregate(
            total=Sum("amount")
        )["total"]
        assert to_new == CORRECTED_JULY, "the payment met the new bill"
        assert (
            payment_selectors.account_credit_position(world.account.pk)
            == ORIGINAL_JULY - CORRECTED_JULY
        ), "the leftover is account credit, not a refund"
        # ── Delivery: queued for the new bill, paper at least ────────────
        assert notification_models.OutboundMessage.objects.filter(
            source_id=new.pk
        ).exists(), "the corrected bill is queued for delivery"
        # ── Meter Reads: the corrected reading saved, linked to the bill ──
        correction = metering_models.ReadCorrection.objects.get(invoice_id=old.pk)
        head = metering_models.MeterRead.objects.get(id=correction.superseding_read_id)
        assert head.current_value == Decimal("1180")
        # ── Audit: sent, approved, the bill done ─────────────────────────
        # The suite's autouse `audit_rows` fixture is the BE-03 capture sink,
        # so the trail is read there rather than from the table.
        actions = {row["action"] for row in audit_rows}
        assert {"correction.case_sent", "correction.approved", "correction.executed"} <= actions


def test_b10_goodwill_rides_on_the_re_priced_bill_and_the_name_is_reissued(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    preview, sent = _sent_case(
        brazos,
        dana,
        _one_customer(world),
        [
            _wrong_read(world),
            {"reason": "goodwill", "item": "credit", "value": "10.00"},
            {"reason": "customer_name", "item": "customer_name", "value": "Ben Bennett"},
        ],
    )
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == []
    with tenant_ctx(brazos):
        new = models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)
        notes = sorted(
            models.CreditNote.objects.filter(original_invoice=world.invoice).values_list(
                "amount", flat=True
            )
        )
        assert notes == [-ORIGINAL_JULY, Decimal("-10.00")], "reversal + goodwill credit"
        instance = InvoiceDocumentInstance.objects.get(invoice=new)
        assert instance.payload["customer_name"] == "Ben Bennett"


def test_b10_credit_only_issues_a_credit_note_and_no_new_bill(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    preview, sent = _sent_case(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "goodwill", "item": "credit", "value": "25.00"}],
    )
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    with tenant_ctx(brazos):
        assert not models.Invoice.objects.filter(corrects_invoice_id=world.invoice.pk).exists()
        assert models.Invoice.objects.get(pk=world.invoice.pk).status == models.INVOICE_ISSUED
        assert list(
            models.CreditNote.objects.filter(original_invoice=world.invoice).values_list(
                "amount", flat=True
            )
        ) == [Decimal("-25.00")]


def test_b10_a_deposit_posts_to_the_deposit_liability_never_revenue(brazos, dana):
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    preview, sent = _sent_case(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "wrong_deposit", "item": "DEP", "value": "150.00"}],
    )
    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]
    with tenant_ctx(brazos):
        new = models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)
        deposit = new.lines.get(kind="deposit")
        assert deposit.amount == Decimal("150.00") and deposit.taxable is False
        liability = ledger_models.LedgerAccount.objects.get(
            tenant=brazos, designation="deposit_liability"
        )
        assert str(deposit.gl_account_id) == str(liability.pk)


# ═══════════════════════════════════════════════════════════════════════════
# B8 · A CLOSED MONTH POSTS FORWARD, AND THE PREVIEW SAYS SO FIRST (S11)
# ═══════════════════════════════════════════════════════════════════════════
def test_b8_a_closed_month_posts_in_the_earliest_open_one(brazos, dana, monkeypatch):
    from apps.billing import posting_seam
    from apps.ledger import models as ledger_models

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
    # July is closed: the books take 1 Aug. The ledger's forward is the one
    # implementation (BR-TEN-038); the closed calendar is named here.
    closed = (date(2026, 8, 1), {"rule": "BR-TEN-038", "from": "2026-07-31", "to": "2026-08-01"})
    monkeypatch.setattr(
        posting_seam,
        "forward_for",
        lambda day: closed if day is not None and day <= JUL_31 else (day, None),
    )
    preview, sent = _sent_case(brazos, dana, _one_customer(world), [_wrong_read(world)])
    bill = preview["bills"][0]
    assert bill["posting_period"] == "2026-08"
    assert bill["posting_date"] == "2026-08-01"
    assert bill["posting_forwarded"] is True
    assert "posting_period_is_not_the_bill_period" in {w["code"] for w in bill["warnings"]}

    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]
    with tenant_ctx(brazos):
        new = models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)
        note = models.CreditNote.objects.get(original_invoice=world.invoice)
        dates = set(
            ledger_models.JournalEntry.objects.filter(source_id__in=[note.pk, new.pk]).values_list(
                "entry_date", flat=True
            )
        )
        assert dates == {date(2026, 8, 1)}


# ═══════════════════════════════════════════════════════════════════════════
# PRORATED · A MID-MONTH PRICE CHANGE IS RE-PRICED PER PART (S9)
# ═══════════════════════════════════════════════════════════════════════════
def test_s9_a_bill_across_a_mid_month_price_change_is_re_priced_per_part(brazos, dana):
    from tests.test_br_rat_114_midperiod_split import (
        PERIOD_END,
        PERIOD_START,
        a_cycled_water_unit,
        a_repricing_water_plan,
    )
    from tests.test_br_rat_114_midperiod_split import a_cycle as r114_cycle
    from tests.test_us_bil_001_prepare import an_account as w3_account

    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos)
        cycle = r114_cycle(brazos, "FIX-S9")
        unit = a_cycled_water_unit(
            dana,
            brazos,
            cycle,
            plan,
            asset_no="W-18901",
            reads=[(date(2026, 5, 31), "0"), (PERIOD_END, "10.000000")],
        )
        account = w3_account(brazos, unit["id"], "FIX-S9")
        run = models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            bill_date=date(2026, 7, 1),
            idempotency_key="fix|s9",
        )
        a_release(brazos, run, dana)
        invoice = _issue(dana, account, run, start=PERIOD_START, end=PERIOD_END)
        assert invoice.total == Decimal("21.00"), "5 × 2.00 + 5 × 2.20 (BR-RAT-114's pin)"
        from apps.metering import models as metering_models

        asset_id = str(
            metering_models.MeterRead.objects.filter(tenant=brazos).latest("read_at").asset_id
        )
    world = SimpleNamespace(account=account, invoice=invoice)
    scope = _one_customer(world)
    # The register should have read 1020, not 1010: 20 kgal, split evenly by day.
    items = [{"reason": "wrong_read", "item": asset_id, "value": "1020"}]
    preview, sent = _sent_case(brazos, dana, scope, items)
    bill = preview["bills"][0]
    usage = bill["layout"]["new"]["services"][0]["usage"]
    assert sorted(Decimal(line["amount"]) for line in usage) == [Decimal("20.00"), Decimal("22.00")]
    assert Decimal(bill["corrected_total"]) == Decimal("42.00")

    done = _approve_and_issue(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    assert done.data["result"]["failed"] == [], done.data["result"]
    with tenant_ctx(brazos):
        new = models.Invoice.objects.get(corrects_invoice_id=invoice.pk)
        assert new.total == Decimal("42.00")
        assert sorted(line.amount for line in new.lines.filter(kind="usage")) == [
            Decimal("20.00"),
            Decimal("22.00"),
        ], "each part priced on its own version"


# ═══════════════════════════════════════════════════════════════════════════
# BULK · ONE FORCED FAILURE, NO ROLLBACK, RESUME TOUCHES ONLY THE FAILURE (S17)
# ═══════════════════════════════════════════════════════════════════════════
def test_s17_bulk_run_one_bill_fails_the_rest_stand_and_resume_finishes_it(
    brazos, dana, monkeypatch
):
    from apps.billing import corrections

    with tenant_ctx(brazos):
        first = _july_world(brazos, dana, n=21)
        second = _july_world(brazos, dana, n=22, plan=first.plan, run=first.run)
        third = _july_world(brazos, dana, n=23, plan=first.plan, run=first.run)
        # DEF-BIL-10103 — a bulk bill whose total does not move is left as it
        # is and never pinned, so the rows must MOVE the three bills: a missed
        # $15.00 charge on each (this test is about failure and resume).
        rating_models.Charge.objects.create(
            tenant=brazos,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(brazos),
        )
    scope = {"kind": "run", "bill_run_id": str(first.run.pk)}
    items = [{"reason": "missed_charge", "item": "RECONNECT", "value": "1"}]
    # DEF-BIL-10091 — bulk preview, Send and approval run as background jobs.
    previewed = _bulk_preview(brazos, dana, scope, items)
    assert previewed.status_code == 200, previewed.data
    preview = previewed.data
    assert preview["aggregate"]["bills"] == 3
    sent = _bulk_send(brazos, dana, scope, items, previewed).data

    real = corrections.execute_restatement

    def _fails_on_the_second(invoice, **kwargs):
        if str(invoice.pk) == str(second.invoice.pk):
            from apps.billing.exceptions import BillingRuleError

            raise BillingRuleError("forced failure for the test")
        return real(invoice, **kwargs)

    monkeypatch.setattr(corrections, "execute_restatement", _fails_on_the_second)
    done = _bulk_approve(brazos, dana, sent["id"], preview["preview_hash"])
    assert done.status_code == 200, done.data
    result = done.data["result"]
    assert sorted(result["succeeded"]) == sorted([str(first.invoice.pk), str(third.invoice.pk)])
    assert [row["invoice_id"] for row in result["failed"]] == [str(second.invoice.pk)]
    assert done.data["status"] == CASE_OPEN, "the case stays open over a failure"
    with tenant_ctx(brazos):
        # no rollback of the two that worked
        assert models.Invoice.objects.filter(corrects_invoice_id=first.invoice.pk).exists()
        assert models.Invoice.objects.filter(corrects_invoice_id=third.invoice.pk).exists()
        # the failure left ZERO artifacts
        assert not models.Invoice.objects.filter(corrects_invoice_id=second.invoice.pk).exists()
        assert not models.CreditNote.objects.filter(original_invoice=second.invoice).exists()

    monkeypatch.setattr(corrections, "execute_restatement", real)
    resumed = _bulk_execute(brazos, dana, sent["id"])
    assert resumed.status_code == 200, resumed.data
    assert resumed.data["result"]["succeeded"] == [str(second.invoice.pk)]
    assert sorted(resumed.data["result"]["skipped_already_done"]) == sorted(
        [str(first.invoice.pk), str(third.invoice.pk)]
    )
    assert resumed.data["status"] == CASE_DONE


# ═══════════════════════════════════════════════════════════════════════════
# CONTRACT A1–A5 (the SCREEN lane's additions) — every key the screen reads
# ═══════════════════════════════════════════════════════════════════════════
#: The keys `07-frontend/src/features/billing/fixABill/__fixtures__/
#: fixABillFixtures.ts` is shaped to (screen lane commit f899697cc). Asserted
#: as SUBSETS: the server may carry more, never fewer — so the two halves
#: cannot drift apart without this going red.
A1_ROW = {
    "invoice_id",
    "invoice_no",
    "account_id",
    "account_no",
    "customer_name",
    "period_start",
    "period_end",
    "amount",
    "total",
    "paid",
    "state",
    "bill_status",
    "currency",
}
A1_TOTALS = {"bills", "amount", "paid", "currency", "accounts"}
A1_EXCLUDED = {"invoice_id", "invoice_no", "period_start", "period_end", "code"}
A2_TOP = {"plans", "rate_schedules", "taxes", "charge_codes", "discounts", "price_targets"}
A2_SCOPED = A2_TOP | {"meters", "bill_lines", "billed"}
A2_BILLED = {"plan_id", "plan_version_id", "tax_rates", "deposit", "fields"}
A3_TOP = {
    "correction_class",
    "scope_kind",
    "currency",
    "count",
    "accounts",
    "bills",
    "totals",
    "customer",
    "bulk",
    "finance",
    "page_changes",
    "approver",
    "preview_hash",
    "problems",
}
A3_BILL = {
    "invoice_id",
    "invoice_no",
    "account_id",
    "account_no",
    "customer_name",
    "period_start",
    "period_end",
    "was",
    "becomes",
    "credit_note",
    "was_total",
    "becomes_total",
    "delta",
    "paid",
    "moves_to_new_bill",
    "still_owed",
    "posting_period",
    "new_due_date",
}
A3_DOC = {
    "invoice_no",
    "plan_name",
    "plan_version",
    "currency",
    "sections",
    "subtotal",
    "taxes",
    "tax_total",
    "total",
}
A3_SECTION = {"key", "kind", "service_code", "rate_type", "total", "lines"}
A3_LINE = {"key", "label", "qty", "unit", "unit_price", "base", "percent", "amount"}
A3_TOTALS = {"was", "becomes", "net", "up", "down", "unchanged"}
A3_CUSTOMER = {
    "name",
    "account_no",
    "owes_before",
    "owes_after",
    "refund",
    "credit_notes",
    "new_bills",
    "reprints",
    "channels",
    "new_due_date",
}
A3_FINANCE = {"entries", "net", "accounts", "closed_through", "earliest_open"}
A4_CASE = {"items", "preview", "approval", "viewer_can_approve"}
A4_APPROVAL = {"role_name", "approver_name", "initiated_by_name", "sent_on", "approved_by_name"}
A5_BILL_ROW = {"invoice_no", "credit_note_no", "rebill_invoice_no"}


def _has(keys, payload, where):
    missing = sorted(set(keys) - set(payload))
    assert not missing, f"{where} is missing {missing}"


def test_contract_a1_to_a5_every_route_answers_the_keys_the_screen_reads(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana)
        draft_run = _a_run(
            brazos,
            dana,
            start=date(2026, 8, 1),
            end=date(2026, 8, 31),
            key="fix|a1",
            bill_date=date(2026, 9, 1),
        )
        models.Invoice.objects.create(
            tenant=brazos,
            account=world.account,
            bill_run=draft_run,
            service_date=date(2026, 8, 31),
            period_start=date(2026, 8, 1),
            period_end=date(2026, 8, 31),
            subtotal=Decimal("1.00"),
            tax_total=ZERO,
            total=Decimal("1.00"),
        )
    # A1 — account alone lists every correctable bill and the draft it leaves out.
    resolved = _call(
        corrections_api.correction_scope_resolve,
        "get",
        brazos,
        dana,
        query={"scope_kind": "account", "account_id": str(world.account.id)},
    )
    assert resolved.status_code == 200, resolved.data
    assert [row["invoice_id"] for row in resolved.data["results"]] == [str(world.invoice.pk)]
    _has(A1_ROW, resolved.data["results"][0], "A1 row")
    assert resolved.data["results"][0]["account_no"] == world.account.account_no
    _has(A1_TOTALS, resolved.data["totals"], "A1 totals")
    assert resolved.data["totals"]["accounts"] == 1
    assert [one["code"] for one in resolved.data["excluded"]] == ["draft"]
    _has(A1_EXCLUDED, resolved.data["excluded"][0], "A1 excluded")

    # A2 — the lists, with and without a scope.
    bare = _call(corrections_api.correction_options, "get", brazos, dana)
    assert bare.status_code == 200, bare.data
    _has(A2_TOP, bare.data, "A2")
    assert "meters" not in bare.data
    scoped = _call(
        corrections_api.correction_options,
        "get",
        brazos,
        dana,
        query={
            "scope_kind": "account",
            "account_id": str(world.account.id),
            "invoice_ids": [str(world.invoice.pk)],
        },
    )
    assert scoped.status_code == 200, scoped.data
    _has(A2_SCOPED, scoped.data, "A2 scoped")
    _has(A2_BILLED, scoped.data["billed"], "A2 billed")
    assert [m["asset_id"] for m in scoped.data["meters"]] == [str(world.asset["id"])]
    assert scoped.data["meters"][0]["billed_reading"].startswith("1200")
    assert scoped.data["billed"]["plan_id"] == str(world.plan.id)

    # A3 — the full preview answer.
    scope, items = _one_customer(world), [_wrong_read(world)]
    preview = _preview(brazos, dana, scope, items)
    assert preview.status_code == 200, preview.data
    body = preview.data
    _has(A3_TOP, body, "A3")
    _has(A3_TOTALS, body["totals"], "A3 totals")
    _has(A3_CUSTOMER, body["customer"], "A3 customer")
    _has(A3_FINANCE, body["finance"], "A3 finance")
    assert body["bulk"] is None and body["count"] == 1 and body["accounts"] == 1
    bill = body["bills"][0]
    _has(A3_BILL, bill, "A3 bill")
    for side in ("was", "becomes"):
        _has(A3_DOC, bill[side], f"A3 {side}")
        _has(A3_SECTION, bill[side]["sections"][0], f"A3 {side} section")
        _has(A3_LINE, bill[side]["sections"][0]["lines"][0], f"A3 {side} line")
    assert bill["was"]["sections"][0]["rate_type"] == "tiered"
    was_keys = {line["key"] for line in bill["was"]["sections"][0]["lines"]}
    becomes_keys = {line["key"] for line in bill["becomes"]["sections"][0]["lines"]}
    assert {"water.base", "water.tier1", "water.tier2", "water.tier3"} <= was_keys & becomes_keys
    assert Decimal(bill["was_total"]) == ORIGINAL_JULY
    assert Decimal(bill["becomes_total"]) == CORRECTED_JULY
    assert Decimal(body["totals"]["net"]) == CORRECTED_JULY - ORIGINAL_JULY
    assert {e["entry"] for e in body["finance"]["entries"]} == {"credit_notes", "new_bills"}

    # A4 — the case at Send carries its rows, the answer it was sent with, the
    # approval block, and whether THIS viewer may approve.
    sent = _send(brazos, dana, scope, items, body["preview_hash"])
    assert sent.status_code == 201, sent.data
    _has(A4_CASE, sent.data, "A4 case")
    _has(A4_APPROVAL, sent.data["approval"], "A4 approval")
    assert sent.data["preview"]["preview_hash"] == body["preview_hash"]
    assert sent.data["viewer_can_approve"] is False, "a clerk cannot approve"
    as_approver = _call(
        corrections_api.correction_case_item, "get", brazos, dana, case_id=sent.data["id"]
    )
    assert as_approver.data["viewer_can_approve"] is True

    # A5 — after approve-and-issue each bill row names its numbers.
    done = _approve_and_issue(brazos, dana, sent.data["id"], body["preview_hash"])
    assert done.status_code == 200, done.data
    row = done.data["bills_detail"][0]
    _has(A5_BILL_ROW, row, "A5 bill row")
    assert row["invoice_no"] == world.invoice.invoice_no
    assert row["rebill_invoice_no"] and row["rebill_invoice_no"] != world.invoice.invoice_no

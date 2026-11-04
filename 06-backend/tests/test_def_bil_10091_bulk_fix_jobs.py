"""DEF-BIL-10091 — bulk Fix a bill runs in the BACKGROUND, priced once.

A bulk preview, Send and Approve-and-issue each took about three minutes on 38
bills and a production web worker is killed at sixty seconds. Decision log
2026-10-13 (*FIX A BILL (CR-180-BRC10) RELEASED IN 2.573.0*): bulk runs as a
background job with progress on screen; Q3 warns (never refuses) when a Wrong
plan row bills a service at $0.00; Q5 refuses a bulk approval when a figure
moved after Send, exactly as one customer's is refused.

Every figure is priced by the engine (the Silver Creek water ladder of
`test_cr180_fix_a_bill_revamp`): each July bill is $373.00, and a missed
$15.00 RECONNECT charge raises it to $388.00.

The suite runs with `JOBS_EAGER=False` (config/settings/test.py), so a 202
leaves the job QUEUED and the test runs it with `core.jobs.run_pending` — the
two acts a request and a worker are.

PostgreSQL as well (law 14 — the issue job is a multi-statement money write):

    cd 06-backend && CELERY_BROKER_URL=memory:// JOBS_EAGER=false \\
      DATABASE_URL=postgres://… pytest -q tests/test_def_bil_10091_bulk_fix_jobs.py \\
      --ds=config.settings.pgtest --create-db
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import bulk_corrections, correction_items, corrections_api, models
from apps.billing.correction_models import (
    CASE_DONE,
    CASE_PENDING_APPROVAL,
    CorrectionCase,
    CorrectionCaseBill,
)
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import jobs as core_jobs

from tests.test_cr180_fix_a_bill_revamp import (  # noqa: F401 — the autouse template pin
    AS_OF,
    CORRECTED_AT,
    _a_revenue_account,
    _call,
    _july_world,
    _one_customer,
    _preview,
    _send,
    _the_rebill_template,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ITEMS = [{"reason": "missed_charge", "item": "RECONNECT", "value": "1"}]


def _three_bills(tenant, actor, n0=40):
    with tenant_ctx(tenant):
        first = _july_world(tenant, actor, n=n0)
        second = _july_world(tenant, actor, n=n0 + 1, plan=first.plan, run=first.run)
        third = _july_world(tenant, actor, n=n0 + 2, plan=first.plan, run=first.run)
        charge = rating_models.Charge.objects.create(
            tenant=tenant,
            code="RECONNECT",
            name="Reconnection fee",
            charge_type="one_time",
            amount_rule="flat",
            amount=Decimal("15.00"),
            service=tenancy_models.Service.objects.get(code="water"),
            gl_account_id=_a_revenue_account(tenant),
        )
    return SimpleNamespace(
        first=first,
        second=second,
        third=third,
        charge=charge,
        scope={"kind": "run", "bill_run_id": str(first.run.pk)},
        bills=[first.invoice, second.invoice, third.invoice],
    )


def _forbid(monkeypatch, *names):
    """Make the pricing path explode if THIS request reaches it."""

    def boom(*args, **kwargs):
        raise AssertionError("priced inside the request")

    for name in names:
        monkeypatch.setattr(correction_items, name, boom)


def _job(tenant, actor, job_id, **query):
    return _call(corrections_api.correction_job, "get", tenant, actor, query=query, job_id=job_id)


def _run(job_id):
    core_jobs.run_pending(job_id)


def _previewed(tenant, actor, world):
    accepted = _preview(tenant, actor, world.scope, ITEMS)
    assert accepted.status_code == 202, accepted.data
    _run(accepted.data["job_id"])
    return accepted.data["job_id"]


def _send_bulk(tenant, actor, world, job_id, preview_hash):
    return _call(
        corrections_api.correction_cases,
        "post",
        tenant,
        actor,
        role="billing_clerk",
        data={
            "scope": world.scope,
            "items": ITEMS,
            "as_of": AS_OF.isoformat(),
            "preview_hash": preview_hash,
            "preview_job_id": job_id,
        },
    )


def _approve(tenant, actor, case_id, preview_hash):
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


def _sent(tenant, actor, world):
    job_id = _previewed(tenant, actor, world)
    answer = _job(tenant, actor, job_id).data["preview"]
    sent = _send_bulk(tenant, actor, world, job_id, answer["preview_hash"])
    assert sent.status_code == 202, sent.data
    _run(sent.data["job_id"])
    case = _job(tenant, actor, sent.data["job_id"]).data["case"]
    assert case is not None
    return answer, case


# ═══════════════════════════════════════════════════════════════════════════
# 1 · A bulk request returns at once: it enqueues and does not price
# ═══════════════════════════════════════════════════════════════════════════
def test_bulk_preview_enqueues_and_prices_nothing_in_the_request(brazos, dana, monkeypatch):
    world = _three_bills(brazos, dana)
    real_build, real_prepare = correction_items.build, correction_items.prepare_bill
    _forbid(monkeypatch, "build", "prepare_bill")
    accepted = _preview(brazos, dana, world.scope, ITEMS)
    assert accepted.status_code == 202, accepted.data
    assert accepted.data["act"] == "preview"
    assert accepted.data["status_url"].endswith(accepted.data["job_id"])
    state = _job(brazos, dana, accepted.data["job_id"]).data
    assert state["status"] == core_jobs.QUEUED and state["preview"] is None
    with tenant_ctx(brazos):
        assert CorrectionCase.objects.count() == 0, "a preview opens no case (BR-BIL-014)"

    monkeypatch.setattr(correction_items, "build", real_build)
    monkeypatch.setattr(correction_items, "prepare_bill", real_prepare)
    _run(accepted.data["job_id"])
    page1 = _job(brazos, dana, accepted.data["job_id"], page=1, per=2).data
    assert page1["status"] == core_jobs.SUCCEEDED
    assert page1["progress"]["done"] == 3 and page1["progress"]["total"] == 3
    preview = page1["preview"]
    assert preview["count"] == 3 and len(preview["bills"]) == 2
    assert Decimal(preview["totals"]["net"]) == Decimal("45.00"), "3 × $15 over ALL bills"
    page2 = _job(brazos, dana, accepted.data["job_id"], page=2, per=2).data["preview"]
    assert len(page2["bills"]) == 1
    seen = {bill["invoice_id"] for bill in preview["bills"] + page2["bills"]}
    assert seen == {str(bill.pk) for bill in world.bills}
    with tenant_ctx(brazos):
        assert CorrectionCase.objects.count() == 0


def test_a_double_pressed_preview_is_one_job(brazos, dana):
    world = _three_bills(brazos, dana)
    first = _preview(brazos, dana, world.scope, ITEMS)
    again = _preview(brazos, dana, world.scope, ITEMS)
    assert first.status_code == again.status_code == 202
    assert first.data["job_id"] == again.data["job_id"]
    from apps.billing.correction_models import CorrectionJob

    with tenant_ctx(brazos):
        assert CorrectionJob.objects.filter(act="preview").count() == 1


def test_one_customer_preview_stays_in_the_request(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana, n=49)
    answer = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "wrong_read", "item": str(world.asset["id"]), "value": "1180"}],
    )
    assert answer.status_code == 200, answer.data
    assert Decimal(answer.data["bills"][0]["becomes_total"]) == Decimal("213.00")


# ═══════════════════════════════════════════════════════════════════════════
# 2 · Send opens the case from the stored preview, pricing nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_bulk_send_opens_the_case_from_the_stored_preview(brazos, dana, monkeypatch):
    world = _three_bills(brazos, dana)
    job_id = _previewed(brazos, dana, world)
    answer = _job(brazos, dana, job_id).data["preview"]
    _forbid(monkeypatch, "build", "prepare_bill")

    moved = _send_bulk(brazos, dana, world, job_id, "0" * 64)
    assert moved.status_code == 422 and moved.data["message_key"] == (
        "billing.correction.figuresMoved"
    )
    sent = _send_bulk(brazos, dana, world, job_id, answer["preview_hash"])
    again = _send_bulk(brazos, dana, world, job_id, answer["preview_hash"])
    assert sent.status_code == again.status_code == 202, sent.data
    assert sent.data["job_id"] == again.data["job_id"], "a double press is one Send"
    _run(sent.data["job_id"])  # still forbidden to price — the job must not
    case = _job(brazos, dana, sent.data["job_id"]).data["case"]
    assert case["status"] == CASE_PENDING_APPROVAL
    assert case["preview_hash"] == answer["preview_hash"]
    with tenant_ctx(brazos):
        assert CorrectionCaseBill.objects.filter(case_id=case["id"]).count() == 3
    after = _send_bulk(brazos, dana, world, job_id, answer["preview_hash"])
    assert after.status_code == 202 and after.data["job_id"] == sent.data["job_id"]
    with tenant_ctx(brazos):
        assert CorrectionCase.objects.count() == 1, "a press after it finished opens no second case"


def test_a_bulk_send_without_its_preview_is_refused(brazos, dana):
    world = _three_bills(brazos, dana)
    refused = _send(brazos, dana, world.scope, ITEMS, "a" * 64)
    assert refused.status_code == 422, refused.data
    assert refused.data["message_key"] == "billing.correction.previewGone"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · Approve and issue: a job, with progress, priced once, idempotent
# ═══════════════════════════════════════════════════════════════════════════
def test_bulk_approve_and_issue_is_a_job_that_prices_each_bill_once(brazos, dana, monkeypatch):
    world = _three_bills(brazos, dana)
    answer, case = _sent(brazos, dana, world)
    gathered: list[str] = []
    real_prepare = correction_items.prepare_bill

    def counting(invoice, pins, *, keyed):
        gathered.append(str(invoice.pk))
        return real_prepare(invoice, pins, keyed=keyed)

    monkeypatch.setattr(correction_items, "prepare_bill", counting)
    accepted = _approve(brazos, dana, case["id"], answer["preview_hash"])
    again = _approve(brazos, dana, case["id"], answer["preview_hash"])
    assert accepted.status_code == again.status_code == 202, accepted.data
    assert accepted.data["job_id"] == again.data["job_id"]
    assert gathered == [], "the request prices nothing"
    _run(accepted.data["job_id"])
    assert sorted(gathered) == sorted(
        str(bill.pk) for bill in world.bills
    ), "each bill gathered ONCE: the approval's check hands its data to the issue"
    state = _job(brazos, dana, accepted.data["job_id"]).data
    assert state["status"] == core_jobs.SUCCEEDED and state["refusal"] is None
    assert state["progress"] == {"done": 3, "total": 3, "stage": "issuing"}
    result = state["case"]["result"]
    assert sorted(result["succeeded"]) == sorted(str(bill.pk) for bill in world.bills)
    assert state["case"]["status"] == CASE_DONE
    with tenant_ctx(brazos):
        for bill in world.bills:
            rebill = models.Invoice.objects.get(corrects_invoice_id=bill.pk)
            assert rebill.total == Decimal("388.00"), "the issued total is the previewed one"
        notes = models.CreditNote.objects.count()
    # A re-delivered task does nothing: one credit note and one bill per bill.
    from apps.billing import correction_jobs
    from apps.billing.correction_models import CorrectionJob

    with tenant_ctx(brazos):
        row = CorrectionJob.objects.get(job_id=accepted.data["job_id"])
        correction_jobs.run_issue_job(
            {"id": accepted.data["job_id"], "payload": {"correction_job_id": str(row.pk)}}
        )
        assert models.CreditNote.objects.count() == notes
        assert models.Invoice.objects.filter(corrects_invoice_id__in=world.bills).count() == 3


# ═══════════════════════════════════════════════════════════════════════════
# 4 · Q5 — a figure that moved after Send refuses the BULK approval
# ═══════════════════════════════════════════════════════════════════════════
def test_q5_a_bulk_approval_is_refused_when_a_figure_moved_after_send(brazos, dana):
    world = _three_bills(brazos, dana)
    answer, case = _sent(brazos, dana, world)
    with tenant_ctx(brazos):
        rating_models.Charge.objects.filter(pk=world.charge.pk).update(amount=Decimal("20.00"))
    accepted = _approve(brazos, dana, case["id"], answer["preview_hash"])
    assert accepted.status_code == 202, accepted.data
    _run(accepted.data["job_id"])
    state = _job(brazos, dana, accepted.data["job_id"]).data
    assert state["refusal"]["message_key"] == "billing.correction.figuresMoved"
    assert state["case"]["status"] == CASE_PENDING_APPROVAL, "the approval is not recorded"
    with tenant_ctx(brazos):
        assert models.CreditNote.objects.count() == 0, "nothing is issued"
        assert CorrectionCase.objects.get(pk=case["id"]).approved_by_id is None


# ═══════════════════════════════════════════════════════════════════════════
# 5 · Q3 — a Wrong plan row that bills a service at $0.00 WARNS, never refuses
# ═══════════════════════════════════════════════════════════════════════════
def test_q3_a_plan_that_bills_water_at_zero_is_a_warning_beside_the_row(brazos, dana):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana, n=48)
        invoice = world.invoice
        row = correction_items.Item(position=2, reason="wrong_plan", correction_class="restatement")
        no_water = SimpleNamespace(lines=[])
        warned = correction_items._plan_warnings(invoice, (row,), no_water)
        other = correction_items.Item(
            position=1, reason="wrong_tax", correction_class="restatement"
        )
        assert correction_items._plan_warnings(invoice, (other,), no_water) == []
    assert warned == [{"position": 2, "service_code": "water", "amount": "0.00"}]
    assert correction_items._row_plan_warnings(
        [{"plan_warnings": warned}, {"plan_warnings": warned}]
    ) == [{"position": 2, "service_code": "water", "amount": "0.00", "bills": 2}]
    # Through the route: the same plan, re-priced, keeps water — no warning,
    # and the answer carries the (empty) list the screen reads.
    same = _preview(
        brazos,
        dana,
        _one_customer(world),
        [{"reason": "wrong_plan", "item": str(world.plan.id)}],
    )
    assert same.status_code == 200, same.data
    assert same.data["plan_warnings"] == []


# ═══════════════════════════════════════════════════════════════════════════
# 6 · DEF-BIL-10108 — Send is ONE transaction
# ═══════════════════════════════════════════════════════════════════════════
def test_def_bil_10108_a_send_refused_after_the_case_row_leaves_no_case(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana, n=47)
    scope = _one_customer(world)
    items = [{"reason": "wrong_read", "item": str(world.asset["id"]), "value": "1180"}]
    preview = _preview(brazos, dana, scope, items)
    assert preview.status_code == 200, preview.data

    def late_refusal(case):
        from apps.billing.exceptions import BillingRuleError

        raise BillingRuleError("refused after the case and its bills were written")

    monkeypatch.setattr(bulk_corrections, "aggregate", late_refusal)
    refused = _send(brazos, dana, scope, items, preview.data["preview_hash"])
    assert refused.status_code == 422, refused.data
    with tenant_ctx(brazos):
        assert CorrectionCase.objects.count() == 0, "no half-written case is left waiting"
        assert CorrectionCaseBill.objects.count() == 0


def test_a_stored_preview_holds_its_bills_until_the_clerk_starts_another(brazos, dana):
    world = _three_bills(brazos, dana)
    from apps.billing.correction_models import CorrectionJobBill

    first = _previewed(brazos, dana, world)
    with tenant_ctx(brazos):
        assert CorrectionJobBill.objects.filter(job__job_id=first).count() == 3
    other = [{"reason": "missed_charge", "item": "RECONNECT", "value": "2"}]
    second = _preview(brazos, dana, world.scope, other)
    assert second.status_code == 202
    with tenant_ctx(brazos):
        assert CorrectionJobBill.objects.filter(job__job_id=first).count() == 0


# ═══════════════════════════════════════════════════════════════════════════
# 7 · PO 2026-10-13 item 2 — a corrected bill is due on the CORRECTION date
#     plus the account's usual days to pay
# ═══════════════════════════════════════════════════════════════════════════
def test_a_corrected_bill_is_due_on_the_correction_date_plus_its_days_to_pay(brazos, dana):
    """The July bill went out on 1 Aug with the cycle's 21 days to pay (due
    22 Aug). Corrected on 10 Sep it is due 10 Sep + 21 = **1 Oct 2026** — the
    preview says so and the issued bill carries it. Before the ruling it came
    out due 22 Aug, already past."""
    from datetime import date as _date

    with tenant_ctx(brazos):
        world = _july_world(brazos, dana, n=46)
        assert world.invoice.due_date == _date(2026, 8, 22)
    scope = _one_customer(world)
    items = [{"reason": "wrong_read", "item": str(world.asset["id"]), "value": "1180"}]
    as_of = _date(2026, 9, 10)
    preview = _preview(brazos, dana, scope, items, as_of=as_of)
    assert preview.status_code == 200, preview.data
    assert preview.data["bills"][0]["new_due_date"] == "2026-10-01"
    sent = _send(brazos, dana, scope, items, preview.data["preview_hash"], as_of=as_of)
    assert sent.status_code == 201, sent.data
    done = _call(
        corrections_api.correction_case_approve_and_issue,
        "post",
        brazos,
        dana,
        data={
            "preview_hash": preview.data["preview_hash"],
            "on_date": as_of.isoformat(),
            "issued_at": "2026-09-10T15:00:00+00:00",
        },
        case_id=sent.data["id"],
    )
    assert done.status_code == 200, done.data
    with tenant_ctx(brazos):
        rebill = models.Invoice.objects.get(corrects_invoice_id=world.invoice.pk)
        assert rebill.due_date == _date(2026, 10, 1), "the issued bill equals the preview"


# ═══════════════════════════════════════════════════════════════════════════
# 8 · PO 2026-10-13 item 3 — a shortened period with no reading on its new
#     end date shares the usage by days
# ═══════════════════════════════════════════════════════════════════════════
def test_a_shortened_period_with_no_reading_on_its_end_shares_usage_by_days(brazos, dana):
    """July 1–31 read 50 kgal on 28 Jul. Shortened to 1–20 Jul, no reading on
    20 Jul, so the bill carries 20/31 of the 50 kgal = 32.258065 kgal, and the
    engine prorates the base and the tier widths by the same 20/31 (B4.3):

        tier 1  5 × 20/31  = 3.225806 kgal × 4.00             = 12.90
        tier 2 15 × 20/31  = 9.677419 → 6.451613 kgal × 6.50  = 41.94
        rest   32.258065 − 9.677419 = 22.580646 kgal × 8.00   = 180.65
        base   20/31 × 8.00                                  =   5.16
                                                               240.65

    A reading ON the new end date keeps its usage (the 1–28 Jul case in
    `test_cr180_fix_a_bill_revamp` stays 375.61)."""
    with tenant_ctx(brazos):
        world = _july_world(brazos, dana, n=45)
    preview = _preview(
        brazos,
        dana,
        _one_customer(world),
        [
            {
                "reason": "wrong_period_or_service",
                "item": "dates",
                "value": "2026-07-01",
                "value2": "2026-07-20",
            }
        ],
    )
    assert preview.status_code == 200, preview.data
    bill = preview.data["bills"][0]
    assert bill["usage_shared_by_days"] == ["water"]
    assert Decimal(bill["corrected_total"]) == Decimal("240.65")

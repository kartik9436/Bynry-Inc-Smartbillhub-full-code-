# ── Trace ──────────────────────────────────────────────
# Change:  CR-187-BRC10 · Phase 13 T-33 (the money freshness read) and T-35
#          (freshness on the template step; stale is warned and recorded).
# Screens: FF-25 (customer, contractor), FF-26 (restoration: $241.38 received,
#          balance $0.00), FF-27 (stale money: $241.38 owing, 3 days old),
#          FF-61 (before you reconnect: $312.40 paid, $45.00 fee not paid)
# Rules:   R16 · R17 · R18 · R26 · R111 · CR-186-BRC10 (posted then cleared;
#          cancelled never counts) · CLAUDE.md hard rules 1, 2, 7
# ───────────────────────────────────────────────────────
"""The field app's money read, and the record of proceeding on it (SQLite).

Every dollar figure below is a figure DRAWN on the four wireframes, read as
images: FF-27's `$241.38 owing`, FF-26's `$241.38 received` and `Balance now
$0.00`, FF-61's `Was $312.40 · paid` and `Reconnect fee $45.00 · not paid`.
The drawings' figures are illustrations (B14 rule 37); they are used here as
worked numbers, not as constants in any code.

The PostgreSQL half (RLS on the new table, the savepoint, the immutability
trigger under a cancelled payment) is `test_cr187_money_pg.py`.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import models as billing_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.payments import models as payment_models
from apps.payments import services as payment_services
from apps.work import money
from apps.work import models as work_models
from core import errors
from core.permissions import FIELD_TECHNICIAN

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx
from tests.test_us_bil_005_release_issue_api import a_bill_of
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

ISSUED_AT = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PAID_AT = datetime(2026, 10, 18, 16, 4, tzinfo=UTC)


# ── fixtures ────────────────────────────────────────────────────────────────


def a_technician(tenant, email, *, contractor=False):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=email)
    crew = None
    if contractor:
        crew = work_models.Crew.objects.create(
            tenant_id=tenant.id, name="Rio Valve Co.", kind=work_models.Crew.KIND_CONTRACTOR
        )
    tech = work_models.Technician.objects.create(tenant_id=tenant.id, user=user, crew=crew)
    return tech, SimpleNamespace(id=user.id, role=FIELD_TECHNICIAN)


def an_order_on(actor, account, technician, *, money_steps=((3, "Close the valve", 5, None),)):
    """A job on the account, assigned to `technician`, with money steps.

    `money_steps` = (seq, title, fresh minutes or None, charge code or None).
    The steps are the JOB's copy rows (`BR-WRK-008`); the template → job copy is
    proved separately in `test_t35_a_template_step_declares_freshness_and_the_job_copies_it`.
    """
    premises = make_premises(actor, address_line="22 Cedar Court", services_available=["water"])
    order = w6.create_work_order(
        actor, None, {"premises_id": str(premises["id"]), "type": "Disconnect — non-payment"}
    )
    work_tables.WorkOrder.objects.filter(pk=order["id"]).update(
        account_id=account.pk, assignee_technician_id=technician.id
    )
    tasks = []
    for seq, title, minutes, code in money_steps:
        tasks.append(
            work_models.WorkOrderTask.objects.create(
                tenant_id=account.tenant_id,
                work_order_id=order["id"],
                seq=seq,
                title=title,
                money_fresh_minutes=minutes,
                money_charge_code=code,
            )
        )
    return order, tasks


def a_bill(tenant, account, total, *, no, issued_at=ISSUED_AT):
    run = a_run(tenant, key=f"2026-10|cr187-{no}")
    return a_bill_of(
        tenant,
        account,
        run,
        invoice_no=no,
        total=Decimal(total),
        status=billing_models.INVOICE_ISSUED,
        issued_at=issued_at,
    )


def a_fee_bill(tenant, account, total, *, no, code="CC-RECON", issued_at=None):
    """A `fee` bill carrying ONE line of the tenant's charge code — the shape
    `billing.fee_bill.raise_and_issue_charge_fee` issues at the cut."""
    from apps.rating import models as rating_models

    charge, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": "Reconnection fee"}
    )
    bill = billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        invoice_no=no,
        bill_type="fee",
        service_date=(issued_at or ISSUED_AT).date(),
        period_start=(issued_at or ISSUED_AT).date(),
        period_end=(issued_at or ISSUED_AT).date(),
        subtotal=Decimal(total),
        tax_total=Decimal("0"),
        total=Decimal(total),
        status=billing_models.INVOICE_ISSUED,
        issued_at=issued_at or ISSUED_AT + timedelta(days=17),
    )
    billing_models.InvoiceLine.objects.create(
        tenant=tenant,
        invoice=bill,
        account=account,
        kind="fee",
        description="Reconnection fee",
        amount=Decimal(total),
        charge=charge,
        taxable=False,
    )
    return bill


def pay(actor, account, amount):
    recorded = payment_services.record_payment(
        actor,
        account_id=account.pk,
        amount=Decimal(amount),
        method_code="card",
        posted_at=PAID_AT,
        idempotency_reference=uuid.uuid4(),
    )
    return payment_models.Payment.objects.get(pk=recorded.payment_id)


def a_cancelled_payment(account, amount):
    """Inserted in its final status — a posted row may not be UPDATEd into
    `cancelled` except through `cancel.py` (payments/0051), and this is a test
    of ARITHMETIC (the CR-186 balance test's own posture)."""
    return payment_models.Payment.objects.create(
        tenant_id=account.tenant_id,
        account=account,
        payment_no=f"PMT-2610-{uuid.uuid4().hex[:8].upper()}",
        type=payment_models.PAYMENT_TYPE_PAYMENT,
        method=payment_services._method("card"),
        amount=Decimal(amount),
        currency="USD",
        status=payment_models.PAYMENT_CANCELLED,
        purpose=payment_models.PURPOSE_BILL,
        posted_at=PAID_AT,
    )


def _shown(figure):
    return None if figure is None else figure["display"]


# ══════════════════════════════════════════════════════════════════════════
# T-33 · the read
# ══════════════════════════════════════════════════════════════════════════


def test_ff27_a_241_38_bill_unpaid_reads_241_38_owing_with_an_as_at_stamp(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10588")
        a_bill(brazos, account, "241.38", no="BL-2610-010588")
        tech, me = a_technician(brazos, "bruner-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        now = datetime(2026, 10, 20, 9, 12, tzinfo=UTC)
        read = money.money_read(me, order["id"], now=now)

    assert read["owing"] == {"amount": "241.3800", "display": "241.38", "currency": "USD"}
    assert read["latest_payment"] is None
    assert read["account_no"] == "A-10588"
    # R17's bar is five minutes, and it is the STEP's — FF-27's *must be under
    # 5 minutes old*.
    assert read["as_at"] == now.isoformat()
    assert read["fresh_minutes"] == 5
    assert read["stale_after"] == (now + timedelta(minutes=5)).isoformat()
    assert [c["title"] for c in read["checks"]] == ["Close the valve"]
    # Hard rule 2 — strings, never floats, anywhere in the answer.
    assert '"241.38"' in json.dumps(read) and "241.38," not in json.dumps(read)


def test_ff26_paying_241_38_reads_received_and_balance_now_0_00_posted_then_cleared(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10589")
        a_bill(brazos, account, "241.38", no="BL-2610-010589")
        tech, me = a_technician(brazos, "restore-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech, money_steps=((1, "Open the kerb stop", 5, None),))
        payment = pay(dana, account, "241.38")
        posted = money.money_read(me, order["id"])
        # Bank reconciliation's one allowed move (payments/0051): posted → cleared.
        payment.status = payment_models.PAYMENT_CLEARED
        payment.cleared_at = PAID_AT + timedelta(days=1)
        payment.save(update_fields=["status", "cleared_at", "updated_at"])
        cleared = money.money_read(me, order["id"])

    assert _shown(posted["owing"]) == "0.00"
    assert _shown(posted["latest_payment"]) == "241.38"
    assert posted["latest_payment"]["state"] == "posted"
    assert posted["latest_payment"]["method"]  # the tenant's own word, never a code
    assert cleared["latest_payment"]["state"] == "cleared"
    assert cleared["latest_payment"]["cleared_at"] is not None
    assert _shown(cleared["owing"]) == "0.00"


def test_a_cancelled_payment_never_lowers_the_balance_and_is_never_the_last_payment(brazos, dana):
    """CR-186-BRC10 (`DEF-PAY-10340`): cancelled never counts. A technician
    reading $0.00 off a cancelled $241.38 would close a disconnect on a debt."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10590")
        a_bill(brazos, account, "241.38", no="BL-2610-010590")
        tech, me = a_technician(brazos, "cancel-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        a_cancelled_payment(account, "241.38")
        read = money.money_read(me, order["id"])

    assert _shown(read["owing"]) == "241.38"
    assert read["latest_payment"] is None


def test_ff61_arrears_312_40_paid_and_the_45_00_fee_unpaid_are_two_answers(brazos, dana):
    """R111 — *"They cleared the arrears and did not pay the fee."* The fee is
    asked about by the CHARGE CODE the step names (data), and its bill's own
    open amount answers it."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-10377")
        a_bill(brazos, account, "312.40", no="BL-2609-010377")
        a_fee_bill(brazos, account, "45.00", no="FEE-2610-0001")
        tech, me = a_technician(brazos, "reconnect-tech@brazos.test")
        order, _ = an_order_on(
            dana, account, tech, money_steps=((1, "Reconnect the supply", 5, "CC-RECON"),)
        )
        pay(dana, account, "312.40")
        before = money.money_read(me, order["id"])
        pay(dana, account, "45.00")
        after = money.money_read(me, order["id"])

    assert _shown(before["latest_payment"]) == "312.40"
    assert _shown(before["owing"]) == "45.00"
    [fee] = before["charges"]
    assert fee["charge_code"] == "CC-RECON"
    assert _shown(fee["charged"]) == "45.00"
    assert _shown(fee["still_open"]) == "45.00"
    assert fee["paid"] is False

    [fee_after] = after["charges"]
    assert fee_after["paid"] is True and _shown(fee_after["still_open"]) == "0.00"
    assert _shown(after["owing"]) == "0.00"


def test_a_charge_nobody_raised_is_not_drawn_as_paid(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="ACC-10378")
        tech, me = a_technician(brazos, "nofee-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech, money_steps=((1, "Reconnect", 5, "CC-RECON"),))
        read = money.money_read(me, order["id"])
    assert read["charges"] == [{"charge_code": "CC-RECON", "charged": None, "paid": None}]


def test_r26_a_contractor_gets_no_figure_at_all(brazos, dana):
    """FF-25 draws a contractor's customer screen with a name and no money."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10591")
        a_bill(brazos, account, "241.38", no="BL-2610-010591")
        tech, me = a_technician(brazos, "contractor@brazos.test", contractor=True)
        order, _ = an_order_on(dana, account, tech)
        read = money.money_read(me, order["id"])
    assert read["withheld"] == money.WITHHELD_EMPLOYEE_ONLY
    assert read["owing"] is None and read["balance"] is None and read["latest_payment"] is None
    assert "241" not in json.dumps(read)


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 1 — tenant isolation, and the colleague boundary
# ══════════════════════════════════════════════════════════════════════════


def test_isolation_another_utilitys_technician_gets_a_404_not_the_money(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10592")
        a_bill(brazos, account, "241.38", no="BL-2610-010592")
        tech, _me = a_technician(brazos, "own-tech@brazos.test")
        order, tasks = an_order_on(dana, account, tech)
    with tenant_ctx(lonestar):
        _other, intruder = a_technician(lonestar, "intruder@lsr.test")
        with pytest.raises(errors.NotFoundError):
            money.money_read(intruder, order["id"])
        with pytest.raises(errors.NotFoundError):
            money.record_proceed(intruder, order["id"], tasks[0].id, {})
        # And the payments read itself, asked for the foreign account directly
        # under the intruder's context, REFUSES — payments' own rule-1 check
        # (`open_bills._account`) — rather than answering a zero or the money.
        from apps.payments.exceptions import PaymentRuleError
        from apps.work.seams import payments_seam

        with pytest.raises(PaymentRuleError):
            payments_seam.money_position(account.pk)
        assert payments_seam.charge_position(account.pk, "CC-RECON") is None


def test_isolation_a_colleagues_job_is_a_404(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10593")
        tech, _ = a_technician(brazos, "assignee@brazos.test")
        _colleague, other = a_technician(brazos, "colleague@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        with pytest.raises(errors.NotFoundError):
            money.money_read(other, order["id"])


# ══════════════════════════════════════════════════════════════════════════
# T-35 · stale is warned, never blocked; proceeding is recorded (R17)
# ══════════════════════════════════════════════════════════════════════════


def test_r17_proceeding_on_a_3_day_old_balance_is_recorded_unverified(brazos, dana, audit_rows):
    proceeded = datetime(2026, 10, 20, 9, 12, tzinfo=UTC)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10594")
        tech, me = a_technician(brazos, "stale-tech@brazos.test")
        order, [step] = an_order_on(dana, account, tech)
        answer = money.record_proceed(
            me,
            order["id"],
            step.id,
            {
                "money_as_at": (proceeded - timedelta(days=3)).isoformat(),
                "proceeded_at": proceeded.isoformat(),
            },
        )
        step.refresh_from_db()
    assert answer["recorded"] is True and answer["unverified"] is True
    assert step.money_unverified is True
    assert step.money_as_at == proceeded - timedelta(days=3)
    assert [r["action"] for r in audit_rows if r["action"].startswith("work_order.task_money")] == [
        money.ACTION_PROCEEDED_UNVERIFIED
    ]


def test_r17_a_figure_two_minutes_old_is_fresh_and_none_seen_is_unverified(brazos, dana):
    now = datetime(2026, 10, 20, 9, 12, tzinfo=UTC)
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10595")
        tech, me = a_technician(brazos, "fresh-tech@brazos.test")
        order, [step] = an_order_on(dana, account, tech)
        fresh = money.record_proceed(
            me, order["id"], step.id,
            {"money_as_at": (now - timedelta(minutes=2)).isoformat(), "proceeded_at": now.isoformat()},
        )
        unseen = money.record_proceed(me, order["id"], step.id, {"proceeded_at": now.isoformat()})
    assert fresh["unverified"] is False
    assert unseen["unverified"] is True


def test_r17_the_bar_is_the_steps_own_and_the_boundary_is_inclusive():
    at = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
    assert money.verdict(fresh_minutes=5, money_as_at=at, proceeded_at=at + timedelta(minutes=5)) is False
    assert money.verdict(fresh_minutes=5, money_as_at=at, proceeded_at=at + timedelta(minutes=5, seconds=1)) is True
    assert money.verdict(fresh_minutes=15, money_as_at=at, proceeded_at=at + timedelta(minutes=10)) is False
    # A handset clock behind the server's: the figure is never "older" than now.
    assert money.verdict(fresh_minutes=5, money_as_at=at, proceeded_at=at - timedelta(minutes=3)) is False


def test_a_step_with_no_money_check_records_nothing(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10596")
        tech, me = a_technician(brazos, "plain-tech@brazos.test")
        order, [step] = an_order_on(dana, account, tech, money_steps=((1, "Fit new meter", None, None),))
        answer = money.record_proceed(me, order["id"], step.id, {"money_as_at": None})
        step.refresh_from_db()
    assert answer == {"task_id": str(step.id), "recorded": False}
    assert step.money_unverified is None


def test_a_sync_task_tick_records_the_proceed_in_the_same_item(brazos, dana):
    """The offline path (E2E-12: a disconnect with no signal): the `task_tick`
    item carries `money_as_at`, the server records UNVERIFIED and still ticks —
    never refused."""
    from apps.work import sync

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10597")
        tech, me = a_technician(brazos, "offline-tech@brazos.test")
        order, [step] = an_order_on(dana, account, tech)
        sync._apply_task_tick(
            me,
            order["id"],
            {
                "task_id": str(step.id),
                "money_as_at": "2026-10-17T09:12:00+00:00",
                "proceeded_at": "2026-10-20T09:12:00+00:00",
            },
        )
        step.refresh_from_db()
    assert step.money_unverified is True
    assert step.ticked_at is not None


# ══════════════════════════════════════════════════════════════════════════
# T-35 · the template step carries it (R18), the job copies it (BR-WRK-008)
# ══════════════════════════════════════════════════════════════════════════


def test_t35_a_template_step_declares_freshness_and_the_job_copies_it(brazos, dana):
    from apps.tenancy import models as tenancy_models
    from apps.work import checklist, selectors, templates_svc
    from apps.work import services as work_services

    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        work_services.seed_reference_list("work_order_types", [], "test")
        tpl = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id,
            name="Shut-off for arrears",
            service=tenancy_models.Service.objects.filter(code="water").first(),
            scope="per_unit",
            version=1,
        )
        templates_svc.replace_collection(
            dana, tpl.id, "tasks",
            [
                {"title": "Photograph the meter"},
                {"title": "Close the valve", "needs_fresh_money": True},
                {"title": "Reconnect", "money_fresh_minutes": 15, "money_charge_code": " CC-RECON "},
            ],
        )
        read = selectors.template(tpl.id)["bundle"]["tasks"]
        premises = make_premises(dana, address_line="95 Cedar Court", services_available=["water"])
        raised = w6.create_work_order(
            dana, None,
            {"type": "Leak investigation", "service": "water", "premises_id": premises["id"],
             "template_id": str(tpl.id)},
        )
        job = checklist.checklist(raised["id"])["tasks"]

    assert [r["money_fresh_minutes"] for r in read] == [None, 5, 15]
    assert [r["money_charge_code"] for r in read] == [None, None, "CC-RECON"]
    assert [t["money_fresh_minutes"] for t in job] == [None, 5, 15]
    assert job[2]["money_charge_code"] == "CC-RECON"


def test_t35_a_bar_of_zero_minutes_is_refused(brazos, dana):
    from apps.tenancy import models as tenancy_models
    from apps.work import templates_svc

    with tenant_ctx(brazos):
        tpl = work_tables.WorkOrderTemplate.objects.create(
            tenant_id=brazos.id, name="Zero", scope="per_unit", version=1,
            service=tenancy_models.Service.objects.filter(code="water").first(),
        )
        with pytest.raises(errors.ValidationError):
            templates_svc.replace_collection(
                dana, tpl.id, "tasks", [{"title": "Close the valve", "money_fresh_minutes": 0}]
            )


def test_no_code_in_work_names_a_disconnect():
    """R18, as a fact about the source: the money module keys off the step's
    two columns and never off a job type. Docstrings and comments are prose and
    may say the word; the CODE — names and string literals — may not."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(money))
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(
            getattr(body[0], "value", None), ast.Constant
        ):
            body.pop(0)  # the docstring
    assert "disconnect" not in ast.unparse(tree).lower()


def test_the_two_routes_resolve():
    from django.urls import resolve

    order_id, task_id = uuid.uuid4(), uuid.uuid4()
    money_view = resolve(f"/api/v1/work/mobile/jobs/{order_id}/money").func
    proceed_view = resolve(f"/api/v1/work/mobile/jobs/{order_id}/tasks/{task_id}/money-proceed").func
    assert money_view.cls.__name__ == "mobile_job_money"
    assert proceed_view.cls.__name__ == "mobile_task_money_proceed"


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-042@3e02d12e (CR-187-BRC10 Phase 13 T-33/T-35; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D✔ E=deferred(n/a) F✔ G✔ H=deferred(n/a)
# gates: pytest tests/test_cr187_money_freshness.py (JOBS_EAGER=false --reuse-db)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

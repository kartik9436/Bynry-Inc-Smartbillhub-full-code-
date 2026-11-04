# ── Trace ──────────────────────────────────────────────
# Change:  FB-023 (decision log 2026-10-31, PO F1–F6) — what the technician
#          sees about money on a field job.
# Defects: DEF-FLD-10789 (the phone never learns employee) · DEF-FLD-10792
#          (posted read as cleared — the wire half)
# Rules:   R26 · F2 (posted counts as paid, shown as posted) · F3 (contractor
#          only on a contractor crew) · F4 (fifth tick, display only) · F5 (plan
#          and notice on DISCONNECT jobs only) · BR-WRK-002 / G78 (read through
#          seams) · CLAUDE.md hard rules 1, 2
# ───────────────────────────────────────────────────────
"""FB-023's server half (SQLite). The PostgreSQL run of the same file is
recorded in the lane report; nothing here catches a database error.

Worked figures (B14 rule 37 — illustrations used as test data): a $241.38
disconnect on Aaron Bruner's account A-10588, a six-instalment plan of $45.00
with September's instalment unpaid, and a 48-hour notice dated 16 October.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment
from apps.work import checklist, mobile, money, templates_svc
from apps.work import connection_models as work_tables
from apps.work import models as work_models

from tests.test_cr187_money_freshness import a_bill, a_technician, an_order_on, pay
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 10, 20, 9, 12, tzinfo=UTC)


def _as_disconnect(order):
    work_tables.WorkOrder.objects.filter(pk=order["id"]).update(
        source=work_tables.SOURCE_DISCONNECT
    )


def _plan(tenant, account, *, paid_through=1):
    """Instalments 1..`paid_through` paid ON their due date; the rest unpaid."""
    plan = PaymentPlan.objects.create(
        tenant=tenant,
        account=account,
        total_amount=Decimal("270"),
        installment_count=6,
        status="active",
        proposed_on=date(2026, 8, 1),
        signed_on=date(2026, 8, 2),
    )
    for seq in range(1, 7):
        PaymentPlanInstallment.objects.create(
            tenant=tenant,
            plan=plan,
            seq=seq,
            due_date=date(2026, 7 + seq, 15) if seq <= 5 else date(2027, 1, 15),
            amount=Decimal("45"),
            paid_posted_on=(date(2026, 7 + seq, 15) if seq <= paid_through else None),
        )
    return plan


def _notice(tenant, account):
    from apps.customers import disconnects

    case = disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        case_no="DSC-26-0042",
        sequence=disconnects.SEQ_SERVICE,
        state=disconnects.STATE_NOTICE_SENT,
        tier=disconnects.TIER_3,
        tier_reached_on=date(2026, 10, 16),
        amount_owed_at_open=Decimal("241.38"),
        currency="USD",
        opened_on=date(2026, 9, 30),
    )
    disconnects.DisconnectNotice.objects.create(
        tenant=tenant, case=case, tier=disconnects.TIER_2, issued_on=date(2026, 10, 1)
    )
    disconnects.DisconnectNotice.objects.create(
        tenant=tenant, case=case, tier=disconnects.TIER_3, issued_on=date(2026, 10, 16)
    )
    return case


# ══════════════════════════════════════════════════════════════════════════
# F3 — the phone learns employee / contractor from the feeds it syncs through
# ══════════════════════════════════════════════════════════════════════════


def test_f3_staff_on_no_crew_are_employees_on_the_day_and_change_feeds(brazos):
    with tenant_ctx(brazos):
        _tech, me = a_technician(brazos, "dana-staff@brazos.test")
        day = mobile.today(me)
        feed = mobile.changes(me)
    assert day["technician"]["employment"] == "employee"
    assert feed["technician"] == {"employment": "employee"}


def test_f3_a_contractor_crew_reads_contractor_and_the_money_read_agrees(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-20588")
        a_bill(brazos, account, "241.38", no="BL-2610-020588")
        tech, me = a_technician(brazos, "rio@brazos.test", contractor=True)
        order, _ = an_order_on(dana, account, tech)
        day = mobile.today(me)
        feed = mobile.changes(me)
        read = money.money_read(me, order["id"], now=NOW)
    assert day["technician"]["employment"] == "contractor"
    assert feed["technician"]["employment"] == "contractor"
    # One test, two places: the phone hides exactly what the server withholds.
    assert read["withheld"] == money.WITHHELD_EMPLOYEE_ONLY
    assert read["disconnect"] is None


def test_f3_the_bundle_names_the_jobs_account_for_the_phone_to_keep(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-20589")
        tech, me = a_technician(brazos, "bundle-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        pack = mobile.bundle(me, order["id"])
    assert pack["account_id"] == str(account.pk)


# ══════════════════════════════════════════════════════════════════════════
# F5 — payment plan and disconnect notice, on DISCONNECT jobs only
# ══════════════════════════════════════════════════════════════════════════


def test_f5_a_disconnect_job_carries_the_plan_behind_and_the_48_hour_notice(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10588")
        a_bill(brazos, account, "241.38", no="BL-2610-110588")
        tech, me = a_technician(brazos, "bruner@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        _as_disconnect(order)
        _plan(brazos, account)  # September's and October's $45.00 never paid
        _notice(brazos, account)
        read = money.money_read(me, order["id"], now=NOW)
    # As of 20 October: 15 September and 15 October are both past and unmet.
    assert read["disconnect"]["plan"] == {"status": "behind", "missed": 2}
    assert read["disconnect"]["notice"] == {
        "tier": "tier_3_48_hour",
        "issued_on": "2026-10-16",
        "amount": {"amount": "241.3800", "display": "241.38", "currency": "USD"},
    }


def test_f5_a_plan_paid_on_time_is_on_track_and_no_plan_reads_none(brazos, dana):
    with tenant_ctx(brazos):
        kept = an_account(dana, brazos, account_no="A-10601")
        none = an_account(dana, brazos, account_no="A-10602")
        tech, me = a_technician(brazos, "plan-tech@brazos.test")
        kept_order, _ = an_order_on(dana, kept, tech)
        none_order, _ = an_order_on(dana, none, tech)
        _as_disconnect(kept_order)
        _as_disconnect(none_order)
        _plan(brazos, kept, paid_through=3)  # August, September, October on time
        on_track = money.money_read(me, kept_order["id"], now=NOW)
        no_plan = money.money_read(me, none_order["id"], now=NOW)
    assert on_track["disconnect"]["plan"] == {"status": "on_track", "missed": 0}
    assert no_plan["disconnect"] == {"plan": None, "notice": None}


def test_f5_the_same_account_on_a_restoration_job_carries_neither(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10603")
        tech, me = a_technician(brazos, "restore@brazos.test")
        order, _ = an_order_on(dana, account, tech, money_steps=((1, "Open the kerb stop", 5, None),))
        _plan(brazos, account)
        _notice(brazos, account)
        read = money.money_read(me, order["id"], now=NOW)
    assert read["disconnect"] is None


def test_f2_the_latest_payment_says_posted_until_the_bank_clears_it(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10604")
        a_bill(brazos, account, "241.38", no="BL-2610-110604")
        tech, me = a_technician(brazos, "posted@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        pay(dana, account, "241.38")
        read = money.money_read(me, order["id"], now=NOW)
    assert read["latest_payment"]["state"] == "posted"
    assert read["latest_payment"]["cleared_at"] is None
    assert read["owing"]["display"] == "0.00"


def test_f2_a_paid_close_on_a_posted_payment_saves_posted_not_cleared(brazos, dana):
    """The step stops on $0.00 owed whether the $241.38 is posted or cleared;
    the close keeps which one the technician was shown."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10605")
        a_bill(brazos, account, "241.38", no="BL-2610-110605")
        tech, me = a_technician(brazos, "paidclose@brazos.test")
        order, tasks = an_order_on(dana, account, tech)
        pay(dana, account, "241.38")
        seen = {
            "task_id": str(tasks[0].id),
            "balance": "0.0000",
            "currency": "USD",
            "as_at": NOW.isoformat(),
            "checked_at": NOW.isoformat(),
            "latest_payment": {"amount": "241.38", "at": "2026-10-18T16:04:00+00:00", "state": "posted"},
        }
        record = money.paid_close_record(order["id"], seen, NOW)
        odd = money.paid_close_record(
            order["id"], {**seen, "latest_payment": {**seen["latest_payment"], "state": "<b>x</b>"}}, NOW
        )
    assert record["phone"]["latest_payment"]["state"] == "posted"
    assert record["server"]["latest_payment"]["state"] == "posted"
    assert odd["phone"]["latest_payment"]["state"] is None


# ══════════════════════════════════════════════════════════════════════════
# F4 — the fifth tick: saved, copied onto the job, sent to the phone
# ══════════════════════════════════════════════════════════════════════════


def test_f4_the_balance_tick_is_saved_copied_and_sent(brazos, dana):
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        templates_svc.replace_collection(dana, tid, "details", {"show_balance_payments": False})
        templates_svc.publish(dana, tid)
        oid = _raise(dana, brazos, tid)["id"]
        row = work_models.WorkOrderDetail.objects.get(work_order_id=oid)
        sent = checklist.checklist(oid)["details"]
    assert row.show_balance_payments is False
    assert sent["show_balance_payments"] is False
    # The four that were already there still travel beside it.
    assert {"show_account_summary", "show_asset_card", "show_access_notes", "show_appointment"} <= set(sent)


def test_f4_a_template_that_never_mentions_the_tick_shows_the_balance(brazos, dana):
    with tenant_ctx(brazos):
        tid = _published_template(dana, brazos)
        oid = _raise(dana, brazos, tid)["id"]
        sent = checklist.checklist(oid)["details"]
    assert sent["show_balance_payments"] is True

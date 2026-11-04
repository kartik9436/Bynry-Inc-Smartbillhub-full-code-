# ── Trace ──────────────────────────────────────────────
# Change:  CR-187-BRC10 · Phase 13 T-34 — a push when money changes on an
#          account a technician is about to visit.
# Rules:   R19 (PO ruled: *"The server pushes the moment money changes. A
#          customer paying on Wednesday reaches the phone on Wednesday"*) · R18
#          (the qualifying job is one whose STEPS declare a money check — no
#          job type is named) · US-WRK-030 TC-2 (the audit line never says
#          *pushed* over a technician with no device) · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""The money push: once per money change, on a qualifying job, never otherwise.

**Run with `JOBS_EAGER=false --reuse-db`** — the assertions read the job ROW
(`queued`), the US-WRK-030 posture.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from apps.payments import models as payment_models
from apps.tenancy import models as tenancy_models
from apps.work import money
from apps.work import models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr187_money_freshness import (
    a_bill,
    a_cancelled_payment,
    a_technician,
    an_order_on,
    pay,
)
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db


def _push_jobs():
    from core import tenancy as core_tenancy

    return list(
        tenancy_models.Job.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), kind=money.MONEY_PUSH_JOB
        ).order_by("created_at", "id")
    )


def _device(tenant, technician, token):
    return work_models.TechnicianDevice.objects.create(
        tenant_id=tenant.id, technician=technician, token=token, platform="ios"
    )


def test_r19_a_payment_on_a_qualifying_account_pushes_once(brazos, dana):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10588")
        a_bill(brazos, account, "241.38", no="BL-2610-110588")
        tech, _ = a_technician(brazos, "push-tech@brazos.test")
        _device(brazos, tech, "fxtr-push-01")
        order, _ = an_order_on(dana, account, tech)
        pay(dana, account, "241.38")

        first = money.sweep()
        again = money.sweep()
        jobs = _push_jobs()
        marks = list(work_models.WorkMoneyPush.objects.filter(tenant_id=brazos.id))

    assert first == {"accounts": 1, "changes": 1, "pushed": 1}
    assert again == {"accounts": 1, "changes": 0, "pushed": 0}, "the same change never pushes twice"
    assert len(jobs) == 1 and jobs[0].status == "queued"
    assert jobs[0].payload["work_order_id"] == str(order["id"])
    assert jobs[0].payload["technician_id"] == str(tech.id)
    # The doorbell carries NO amount — the phone reads the figure live (R16).
    assert "241" not in str(jobs[0].payload)
    assert len(marks) == 1 and marks[0].devices == 1


def test_r19_a_second_money_change_pushes_again(brazos, dana):
    """A cancellation is a money change too: the balance goes back UP, and the
    technician who was about to *Close — customer paid* has to know."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10589")
        a_bill(brazos, account, "241.38", no="BL-2610-110589")
        tech, _ = a_technician(brazos, "push2-tech@brazos.test")
        an_order_on(dana, account, tech)
        payment = pay(dana, account, "100.00")
        money.sweep()
        # A later change on the same account — a newer `updated_at`.
        payment_models.Payment.objects.filter(pk=payment.pk).update(
            updated_at=payment.updated_at + timedelta(minutes=3)
        )
        second = money.sweep()
        jobs = _push_jobs()
    assert second["pushed"] == 1
    assert len(jobs) == 2


def test_r18_a_job_whose_steps_declare_no_money_check_never_pushes(brazos, dana):
    """The same account, the same payment — but a meter exchange, whose steps
    read no money. Nothing anywhere asks what TYPE the job is."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10590")
        a_bill(brazos, account, "241.38", no="BL-2610-110590")
        tech, _ = a_technician(brazos, "exchange-tech@brazos.test")
        an_order_on(dana, account, tech, money_steps=((1, "Fit new meter", None, None),))
        pay(dana, account, "241.38")
        result = money.sweep()
        jobs = _push_jobs()
    assert result == {"accounts": 0, "changes": 0, "pushed": 0}
    assert jobs == []


def test_money_moving_on_a_different_account_never_pushes(brazos, dana):
    with tenant_ctx(brazos):
        watched = an_account(dana, brazos, account_no="A-10591")
        other = an_account(dana, brazos, account_no="A-10592")
        a_bill(brazos, other, "241.38", no="BL-2610-110592")
        tech, _ = a_technician(brazos, "watch-tech@brazos.test")
        an_order_on(dana, watched, tech)
        pay(dana, other, "241.38")
        result = money.sweep()
        jobs = _push_jobs()
    assert result["pushed"] == 0 and jobs == []


def test_a_closed_job_no_longer_qualifies(brazos, dana):
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10593")
        a_bill(brazos, account, "241.38", no="BL-2610-110593")
        tech, _ = a_technician(brazos, "done-tech@brazos.test")
        order, _ = an_order_on(dana, account, tech)
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(state=work_tables.WO_COMPLETED)
        a_cancelled_payment(account, "10.00")
        result = money.sweep()
    assert result["pushed"] == 0


def test_isolation_one_utilitys_payment_never_pushes_anothers_phone(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-10594")
        a_bill(brazos, account, "241.38", no="BL-2610-110594")
        tech, _ = a_technician(brazos, "iso-tech@brazos.test")
        an_order_on(dana, account, tech)
        pay(dana, account, "241.38")
    with tenant_ctx(lonestar):
        result = money.sweep()
        jobs = _push_jobs()
        marks = work_models.WorkMoneyPush.objects.filter(tenant_id=lonestar.id).count()
    assert result["pushed"] == 0 and jobs == [] and marks == 0


def test_the_job_body_writes_pushed_only_when_a_device_was_addressed(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        tech, _ = a_technician(brazos, "body-tech@brazos.test")
        bare, _ = a_technician(brazos, "nodevice-tech@brazos.test")
        _device(brazos, tech, "fxtr-body-01")
        money.run_money_push_job(
            {"payload": {"work_order_id": "wo-1", "technician_id": str(tech.id), "order_no": "WO-4824"}}
        )
        money.run_money_push_job(
            {"payload": {"work_order_id": "wo-2", "technician_id": str(bare.id), "order_no": "WO-4825"}}
        )
    actions = {r["entity_id"]: r["action"] for r in audit_rows if r["action"].startswith("work.order.money")}
    assert actions == {"wo-1": money.ACTION_MONEY_PUSHED, "wo-2": money.ACTION_MONEY_WAITING}


def test_both_jobs_ride_the_work_queue_and_the_beat_is_a_minute():
    from core import jobs as core_jobs

    money.register()
    assert core_jobs.job_queue(money.MONEY_PUSH_JOB) == "work"
    assert core_jobs.job_queue(money.MONEY_SWEEP_JOB) == "work"
    assert core_jobs.job_handler(money.MONEY_PUSH_JOB) is money.run_money_push_job
    entry = money.beat_schedule()[money.BEAT_ENTRY]
    assert entry["schedule"] == 60.0 and entry["task"] == money.SWEEP_TASK


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-030@3e02d12e (CR-187-BRC10 Phase 13 T-34; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D=deferred(n/a) E=deferred(n/a) F✔ G✔ H=deferred(n/a)
# gates: pytest tests/test_cr187_money_push.py (JOBS_EAGER=false --reuse-db)
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10641 (FB-013, PO beta report 2026-10-28) — a cleared
#           balance stops the money-check step; the technician may close
#           "Not done — payment received".
# Rules:    PO rulings (a)(b)(c) of 2026-10-28 (decision log *"FB-013: a cleared
#           balance STOPS the money-check step"*) · R16 (money is READ) · R17
#           (stale is warned, never blocked — unchanged) · R18 (the check sits
#           on the template step; no code knows what a disconnect is) ·
#           BR-WRK-002 / G78 · CLAUDE.md hard rules 1, 2, 7
# Code:     apps/work/money.py (`paid_close_record`) · apps/work/sync.py
#           (`_apply_close`) · apps/work/field_outcomes.py · apps/work/
#           office_notices.py · apps/notifications/field_work_events.py
# ───────────────────────────────────────────────────────
"""The paid close, end to end on the server (SQLite; PostgreSQL half is `_pg`).

The worked figure the PO was shown: a $312.40 arrear, paid in full; the phone's
fresh read says the balance is $0.00, so the technician closes *Not done —
payment received* instead of cutting the supply.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apps.notifications import models as notification_models
from apps.notifications import seed_templates
from apps.work import connection_models as work_tables
from apps.work import field_outcomes, sync
from apps.work import models as work_models

from tests.test_cr168_technician_api import _ready, _token
from tests.test_cr187_order_helpers import close as helper_close
from tests.test_cr187_order_helpers import job as helper_job
from tests.test_cr187_money_freshness import a_bill, pay
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

CAPTURED_AT = "2026-03-15T16:07:00Z"
SEEN_AS_AT = "2026-03-15T15:58:00Z"
CHECKED_AT = "2026-03-15T16:00:00Z"
PAID = "not_done_payment_received"


def _paid_job(dana, brazos, *, account_no, owe="312.40", paid="312.40", money_step=True):
    """A ready job on an account that owed $312.40, with one money-check step."""
    oid, tech = _ready(dana, brazos)
    account = an_account(dana, brazos, account_no=account_no)
    a_bill(brazos, account, owe, no=f"BL-{account_no}")
    if paid:
        pay(dana, account, paid)
    work_tables.WorkOrder.objects.filter(pk=oid).update(
        account_id=account.pk, assigned_by_id=dana.user.id
    )
    step = work_models.WorkOrderTask.objects.filter(work_order_id=oid).order_by("seq").last()
    if money_step:
        step.money_fresh_minutes = 5
        step.save(update_fields=["money_fresh_minutes"])
    return oid, tech, step


def _seen(step, *, balance="0.0000", as_at=SEEN_AS_AT, checked_at=CHECKED_AT):
    return {
        "task_id": str(step.id),
        "balance": balance,
        "currency": "USD",
        "as_at": as_at,
        "checked_at": checked_at,
        "latest_payment": {"amount": "312.4000", "at": "2026-03-15T09:30:00Z"},
    }


def _paid_close(token, field_data, *, key="close-paid-1"):
    return {
        "key": key,
        "kind": "close",
        "seq": 99,
        "captured_at": CAPTURED_AT,
        "capture_token": token,
        "payload": {
            "outcome": PAID,
            "arrived_at": "2026-03-15T15:50:00Z",
            "finished_at": "2026-03-15T16:05:00Z",
            "field_data": field_data,
        },
    }


def _order(oid):
    return work_tables.WorkOrder.objects.get(pk=oid)


# ══════════════════════════════════════════════════════════════════════════
# The token
# ══════════════════════════════════════════════════════════════════════════


def test_the_paid_outcome_is_a_stored_token_and_an_office_word():
    assert work_tables.OUTCOME_NOT_DONE_PAID == PAID
    assert PAID in work_tables.WORK_ORDER_OUTCOMES
    assert field_outcomes.R4_WORDS["not_done_paid"] == PAID


# ══════════════════════════════════════════════════════════════════════════
# Accepted with a fresh, cleared snapshot — and BOTH reads stored
# ══════════════════════════════════════════════════════════════════════════


def test_a_fresh_cleared_snapshot_closes_paid_and_the_server_stores_both_reads(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, step = _paid_job(dana, brazos, account_no="A-13001")
        remark = "Customer has paid. Not disconnected."
        out = sync.sync_batch(
            tech, oid, {"items": [_paid_close(_token(tech), {"reason": remark, "money_seen": _seen(step)})]}
        )
        order = _order(oid)

    assert out["items"][0]["result"] == "accepted", out["items"][0]
    assert order.outcome == PAID and order.state == work_tables.WO_COMPLETED
    record = order.field_data["payment_received"]
    # What the phone SAW, as it saw it (hard rule 2 — strings at four places).
    assert record["phone"]["balance"] == "0.0000"
    assert record["phone"]["as_at"] == SEEN_AS_AT
    assert record["phone"]["latest_payment"]["amount"] == "312.4000"
    # What the SERVER read at the close — its own figure, its own clock.
    assert record["server"]["owing"]["display"] == "0.00"
    assert record["server"]["latest_payment"]["display"] == "312.40"
    assert record["server"]["as_at"]
    assert record["fresh_minutes"] == 5
    assert order.field_data["reason"] == remark
    assert "money_seen" not in order.field_data, "the raw snapshot is folded into the server's record"


def test_a_phone_cannot_write_the_payment_record_itself(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, step = _paid_job(dana, brazos, account_no="A-13002")
        forged = {"phone": {"balance": "-999"}, "server": {"owing": {"display": "0.00"}}}
        sync.sync_batch(
            tech, oid,
            {"items": [_paid_close(_token(tech), {"money_seen": _seen(step), "payment_received": forged})]},
        )
        record = _order(oid).field_data["payment_received"]
    assert record["phone"]["balance"] == "0.0000"
    assert record["server"]["owing"]["amount"] == "0.0000"


# ══════════════════════════════════════════════════════════════════════════
# STRICT: refused without proof — back to the technician, nothing closed
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "case, reason",
    [
        ("no_snapshot", "paid_close_needs_a_fresh_balance"),
        ("stale", "paid_close_balance_not_fresh"),
        ("owing", "paid_close_balance_not_cleared"),
        ("no_money_step", "paid_close_needs_a_money_check"),
    ],
)
def test_a_paid_close_without_proof_is_refused_and_the_job_stays_open(brazos, dana, case, reason):
    with tenant_ctx(brazos):
        oid, tech, step = _paid_job(
            dana, brazos, account_no=f"A-1301{len(case)}", money_step=case != "no_money_step"
        )
        if case == "no_snapshot":
            data = {"reason": "Paid"}
        elif case == "stale":
            # Read at 15:50, the stop shown at 16:00 — ten minutes on a five-minute bar.
            data = {"money_seen": _seen(step, as_at="2026-03-15T15:50:00Z")}
        elif case == "owing":
            data = {"money_seen": _seen(step, balance="45.0000")}
        else:
            data = {"money_seen": _seen(step)}
        out = sync.sync_batch(tech, oid, {"items": [_paid_close(_token(tech), data)]})
        order = _order(oid)

    item = out["items"][0]
    assert item["result"] == "refused", item
    assert item["detail"]["reason"] == reason, item
    assert order.state != work_tables.WO_COMPLETED and order.outcome is None


def test_other_outcomes_never_need_a_snapshot(brazos, dana):
    """R17 unchanged: a stale money step still closes Passed — no proof asked."""
    with tenant_ctx(brazos):
        oid, tech, _step = _paid_job(dana, brazos, account_no="A-13020")
        item = _paid_close(_token(tech), {})
        item["payload"]["outcome"] = "passed"
        out = sync.sync_batch(tech, oid, {"items": [item]})
    assert out["items"][0]["result"] == "accepted", out["items"][0]


# ══════════════════════════════════════════════════════════════════════════
# The office: the outcome, the remark, the times, the money seen; the filter
# ══════════════════════════════════════════════════════════════════════════


def test_the_office_reads_the_outcome_remark_times_and_money_and_can_filter_it(brazos, dana):
    with tenant_ctx(brazos):
        oid, tech, step = _paid_job(dana, brazos, account_no="A-13030")
        sync.sync_batch(
            tech, oid,
            {"items": [_paid_close(_token(tech), {"reason": "Customer has paid. Not disconnected.",
                                                  "money_seen": _seen(step)})]},
        )
        # A second, ordinary job closed Passed — through the shared helpers,
        # whose parts are get-or-create (two `_ready` jobs collide on them).
        other, tech2 = helper_job(dana, brazos)
        helper_close(tech2, other, "passed")
        outcome = field_outcomes.order_outcome(oid)
        paid_only = field_outcomes.office_queue(outcome="not_done_paid")
        every = field_outcomes.office_queue()

    assert outcome["word"] == "not_done_paid" and outcome["kind"] == "paid"
    assert outcome["is_failure"] is False and outcome["reason_missing"] is False
    assert outcome["reason"] == "Customer has paid. Not disconnected."
    assert outcome["payment_received"]["phone"]["balance"] == "0.0000"
    assert outcome["payment_received"]["server"]["owing"]["display"] == "0.00"
    assert outcome["times"]["arrived_at"] and outcome["times"]["finished_at"]
    assert [r["id"] for r in paid_only["rows"]] == [str(oid)]
    assert every["tally"]["not_done_paid"] == 1 and every["tally"]["passed"] == 1


def test_the_office_is_told_not_disconnected_payment_received(brazos, dana):
    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=datetime(2026, 8, 17, tzinfo=UTC).date())
        oid, tech, step = _paid_job(dana, brazos, account_no="A-13040")
        sync.sync_batch(tech, oid, {"items": [_paid_close(_token(tech), {"money_seen": _seen(step)})]})
        rows = list(
            notification_models.OutboundMessage.objects.filter(source_type="field_work").order_by("created_at")
        )
        from apps.notifications import field_work_events

        key, params = field_work_events.bell_key_for(rows[0].render_context)

    # ONE bell for the close, and it is the paid one — never "closed" as well.
    assert [r.render_context["event_code"] for r in rows] == ["not_done_paid"]
    assert key == "notifications.fieldWork.notDonePaid"
    assert params["order"] == _order_no(oid, brazos)


def _order_no(oid, tenant):
    with tenant_ctx(tenant):
        return _order(oid).order_no


def test_isolation_the_paid_record_reads_only_this_utilitys_money(brazos, lonestar, dana):
    """Hard rule 1 — the outcome read of another utility's job is a 404."""
    from core import errors

    with tenant_ctx(brazos):
        oid, tech, step = _paid_job(dana, brazos, account_no="A-13050")
        sync.sync_batch(tech, oid, {"items": [_paid_close(_token(tech), {"money_seen": _seen(step)})]})
    with tenant_ctx(lonestar):
        with pytest.raises(errors.NotFoundError):
            field_outcomes.order_outcome(oid)


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-WRK-10641 (FB-013; PO rulings 2026-10-28 (a)(b)(c))
# generated: 2026-10-28 by the FB-013 lane
# gates: pytest tests/test_fb013_paid_close.py (JOBS_EAGER=false --reuse-db)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


def test_sample_cut_and_restore_visits_check_the_money_first():
    """Judgment 8 — new sample utilities get the check on the step, as DATA."""
    from apps.metering import sample_data

    cut = sample_data._flow_visit_task_rows("Disconnect visit")
    restore = sample_data._flow_visit_task_rows("Reconnect visit")
    read = sample_data._flow_visit_task_rows("Final read")
    assert cut[0]["money_fresh_minutes"] == 5 and "money_fresh_minutes" not in cut[1]
    assert restore[0]["money_fresh_minutes"] == 5
    assert all("money_fresh_minutes" not in row for row in read)


def test_cleared_is_owing_at_four_places_at_or_below_zero():
    from apps.work import money

    assert money.is_cleared("0.0000") and money.is_cleared("-12.5000") and money.is_cleared("0")
    assert not money.is_cleared("0.0001") and not money.is_cleared("0.00004") and not money.is_cleared("45.00")
    assert not money.is_cleared(None) and not money.is_cleared("n/a")

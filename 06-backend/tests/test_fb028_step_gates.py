# ── Trace ──────────────────────────────────────────────
# Change:   FB-028 (DEF-FLD-10803) — the template's Reconnect limit, sent with
#           the job; the gate facts a job raised on site carries on its money
#           read; the office told when a gated step stops.
# Rules:    PO 2026-10-31 (decision log): reconnect at or below the limit;
#           *"the 25 $ limit should be part of work order template when payment
#           check is included"*; a raised disconnect stops on a cleared balance,
#           an unexpired notice or a protected account · hard rules 2, 7
# Code:     apps/work/templates_svc.py · checklist.py · money_flow_facts.py ·
#           seams/customers_seam.py · step_gates.py
# ───────────────────────────────────────────────────────
"""Worked figures: a $25.00 limit; a 10-day notice of 26 Oct, ending 5 Nov,
read on 31 Oct; a medical certificate in force."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.work import checklist, field_raise, money, selectors, step_gates, templates_svc
from apps.work import models as work_models
from apps.work.field_order_models import WorkFieldRaise
from core import errors

from tests.test_cr187_money_freshness import a_technician, an_order_on
from tests.test_cr187_order_helpers import FIX, job, template
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import an_account

pytestmark = pytest.mark.django_db

OCT_31 = datetime(2026, 10, 31, 15, 0, tzinfo=UTC)


def test_the_template_saves_the_reconnect_limit_and_the_raised_job_carries_it(brazos, dana):
    """Saved to 4 places, served by the builder, copied onto a job raised from
    it and sent to the phone in the job's details."""
    with tenant_ctx(brazos):
        oid, tech = job(dana, brazos)
        tid = template(dana, brazos, "Reconnect visit")
        templates_svc.replace_collection(dana, tid, "details", {"reconnect_limit": "25"})
        templates_svc.publish(dana, tid)
        served = selectors._collection_rows(tid)["details"]
        out = field_raise.raise_from_field(
            tech,
            {
                "key": "fb028-lim",
                "template_id": str(tid),
                "carried_from": str(oid),
                "location": FIX,
            },
        )
        sent = checklist.checklist(out["order_id"])["details"]
        stored = work_models.WorkOrderTemplateDetail.objects.get(template_id=tid).reconnect_limit
        # Absent is UNCHANGED, like the visit-message fields: a save that
        # does not name the limit leaves it where it was.
        templates_svc.replace_collection(dana, tid, "details", {"show_asset_card": False})
        kept = work_models.WorkOrderTemplateDetail.objects.get(template_id=tid).reconnect_limit
    served = served[0] if isinstance(served, list) else served
    assert stored == Decimal("25.0000") and kept == Decimal("25.0000")
    assert served["reconnect_limit"] == "25.0000"
    assert sent["reconnect_limit"] == "25.0000"


@pytest.mark.parametrize("bad", ["-1", "abc", 12.5])
def test_a_limit_that_is_not_money_is_refused_by_name(brazos, dana, bad):
    with tenant_ctx(brazos):
        tid = template(dana, brazos, "Reconnect visit")
        with pytest.raises(errors.ValidationError) as refused:
            templates_svc.replace_collection(dana, tid, "details", {"reconnect_limit": bad})
    assert refused.value.message_key == "work.template.reconnect_limit_not_money"


def _raised_job(dana, brazos, account, *, limit="25.0000"):
    tech, me = a_technician(brazos, f"gate-{account.account_no}@brazos.test")
    order_row, _tasks = an_order_on(dana, account, tech)
    WorkFieldRaise.objects.create(
        tenant_id=brazos.id, work_order_id=order_row["id"], key=f"k-{account.account_no}"
    )
    work_models.WorkOrderDetail.objects.update_or_create(
        tenant_id=brazos.id,
        work_order_id=order_row["id"],
        defaults={"reconnect_limit": Decimal(limit) if limit else None},
    )
    return order_row, me


def _notice(tenant, account, *, tier, issued_on):
    from apps.customers import disconnects

    case = disconnects.DisconnectCase.objects.create(
        tenant=tenant,
        account=account,
        sequence=disconnects.SEQ_SERVICE,
        state=disconnects.STATE_NOTICE_SENT,
        tier=tier,
        tier_reached_on=issued_on,
        amount_owed_at_open=Decimal("804.50"),
        currency="USD",
        opened_on=date(2026, 10, 1),
    )
    disconnects.DisconnectNotice.objects.create(
        tenant=tenant, case=case, tier=tier, issued_on=issued_on
    )


def test_a_raised_job_carries_its_limit_the_notice_end_and_protection(brazos, dana):
    from apps.customers import disconnects

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-28001")
        order_row, me = _raised_job(dana, brazos, account)
        _notice(brazos, account, tier=disconnects.TIER_2, issued_on=date(2026, 10, 26))
        disconnects.AccountProtection.objects.create(
            tenant=brazos,
            account=account,
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 10, 1),
            expires_on=date(2027, 1, 31),
        )
        read = money.money_read(me, order_row["id"], now=OCT_31)
    gate = read["field_gate"]
    assert gate["raised_on_site"] is True
    assert gate["reconnect_limit"] == {"amount": "25.0000", "display": "25.00"}
    assert gate["notice"] == {
        "tier": "tier_2_10_day",
        "issued_on": "2026-10-26",
        "ends_on": "2026-11-05",
    }
    assert gate["notice_open"] is True
    assert gate["protected"] is True


def test_after_the_notice_period_and_with_no_protection_nothing_holds(brazos, dana):
    from apps.customers import disconnects

    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-28002")
        order_row, me = _raised_job(dana, brazos, account)
        _notice(brazos, account, tier=disconnects.TIER_3, issued_on=date(2026, 10, 20))
        read = money.money_read(me, order_row["id"], now=OCT_31)
    assert read["field_gate"]["notice"]["ends_on"] == "2026-10-22"
    assert read["field_gate"]["notice_open"] is False
    assert read["field_gate"]["protected"] is False


def test_an_office_raised_job_carries_no_gate(brazos, dana):
    """2026-10-29 C1 is unchanged: an office-requested reconnect is never
    refused for owing, so a job not raised on site carries no gate at all."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-28003")
        tech, me = a_technician(brazos, "office-job@brazos.test")
        order_row, _ = an_order_on(dana, account, tech)
        read = money.money_read(me, order_row["id"], now=OCT_31)
    assert read["field_gate"] is None


def test_a_stopped_step_is_recorded_and_the_office_told(brazos, dana, audit_rows):
    """Worked: the live check reads $804.50 against a $25.00 limit → the phone
    stops the step and calls this door."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos, account_no="A-28004")
        order_row, me = _raised_job(dana, brazos, account)
        out = step_gates.record_stop(
            me,
            order_row["id"],
            {"reason": "owes_over_limit", "owing": "804.5000", "limit": "25.0000"},
        )
        with pytest.raises(errors.ValidationError) as unknown:
            step_gates.record_stop(me, order_row["id"], {"reason": "felt_like_it"})
        _other, stranger = a_technician(brazos, "stranger-gate@brazos.test")
        with pytest.raises(errors.NotFoundError):
            step_gates.record_stop(stranger, order_row["id"], {"reason": "protected"})
    assert out["recorded"] is True and out["reason"] == "owes_over_limit"
    rows = [r for r in audit_rows if r["action"] == step_gates.ACTION_STEP_STOPPED]
    assert len(rows) == 1 and rows[0]["after"]["owing"] == "804.5000"
    assert unknown.value.message_key == "work.mobile.step_stop_reason_unknown"


def test_the_step_stopped_route_resolves():
    import uuid

    from django.urls import resolve

    view = resolve(f"/api/v1/work/mobile/jobs/{uuid.uuid4()}/step-stopped").func
    assert view.cls.__name__ == "mobile_step_stopped"

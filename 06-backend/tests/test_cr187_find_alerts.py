# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 · T-41 — lane S-FIND
# Rules:    BR-FLD-00028 (R28 — acknowledge an emergency; 5 minutes, then
#           dispatch is told) · BR-FLD-00029 (R29) · BR-WRK-034 · hard rules
#           1 and 7 · hard-won law 2 (the hold carries the test that fires when
#           it expires)
# ───────────────────────────────────────────────────────
"""The four push kinds, each with its own sound and Android channel; the
emergency's acknowledgement; and R28's five minutes, told once."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import field_alerts, push
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _technician(tenant, email, name):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=name)
    tech = work_models.Technician.objects.create(tenant=tenant, user=user)
    return tech, type("Actor", (), {"id": user.id, "pk": user.id, "role": "field_technician"})()


def _order(actor, technician=None, address="14 Oak Street"):
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    order = w6.create_work_order(actor, None, {"premises_id": str(premises["id"]), "type": "Gas leak"})
    if technician is not None:
        work_tables.WorkOrder.objects.filter(pk=order["id"]).update(assignee_technician=technician)
    return order


def _emergency(dana, tenant, **payload):
    tech, tech_actor = _technician(tenant, "d.ortiz@b.test", "D. Ortiz")
    order = _order(dana, tech)
    sent = field_alerts.send_alert(dana, {"kind": "emergency", "work_order_id": order["id"], **payload})
    return sent, tech, tech_actor, order


# ══════════════════════════════════════════════════════════════════════════
# Kinds and channels
# ══════════════════════════════════════════════════════════════════════════


def test_every_kind_has_its_own_sound_and_its_own_android_channel():
    kinds = ("urgent_assignment", "emergency", "schedule_change", "dispatch_message")
    messages = {k: push.push_message(k, {"order_no": "WO-4850"}) for k in kinds}
    assert len({m["sound"] for m in messages.values()}) == 4
    assert len({m["android"]["channel_id"] for m in messages.values()}) == 4
    assert {m["kind"] for m in messages.values()} == set(kinds)
    assert messages["emergency"]["android"]["importance"] == "max"
    assert messages["emergency"]["ios"]["interruption_level"] == "critical"
    # Requirement 13: a dispatch message is an in-app badge, not audio.
    assert messages["dispatch_message"]["android"]["importance"] == "low"
    assert messages["dispatch_message"]["ios"]["interruption_level"] == "passive"
    assert messages["dispatch_message"]["badge"] is True
    # The automatic assignment doorbell keeps a channel of its own.
    assert push.push_message("new_job", {})["android"]["channel_id"] == "new_job"


def test_the_payload_carries_ids_and_the_order_number_never_a_token_or_an_address(brazos, dana):
    with tenant_ctx(brazos):
        sent, _tech, _actor, order = _emergency(dana, brazos)
    message = sent["push"]
    assert message["data"] == {
        "kind": "emergency",
        # DEF-WRK-10352: the utility, so a handset signed into another ignores it.
        "tenant": brazos.subdomain,
        "alert_id": sent["id"],
        "work_order_id": str(order["id"]),
        "order_no": order["order_no"],
    }
    assert "14 Oak Street" not in str(message)


def test_send_writes_the_row_the_audit_and_queues_the_push(brazos, dana):
    from core import jobs as core_jobs

    with tenant_ctx(brazos):
        sent, tech, _actor, order = _emergency(dana, brazos, message="Strong smell at the side of the house.")
        row = work_models.WorkFieldAlert.objects.get(pk=sent["id"])
        record = core_jobs.current(sent["job_id"])
    assert row.kind == "emergency" and row.ack_required is True
    assert row.ack_due_at - row.sent_at == timedelta(minutes=5)
    assert sent["seconds_to_ack"] in (299, 300)
    assert sent["premise"]["address"] == "14 Oak Street"
    assert sent["technician"] == "D. Ortiz"
    assert record["kind"] == push.ALERT_PUSH_JOB and record["payload"]["alert_id"] == sent["id"]
    assert core_jobs.job_queue(push.ALERT_PUSH_JOB) == "work"


def test_the_push_job_counts_the_devices_it_addressed(brazos, dana):
    with tenant_ctx(brazos):
        sent, tech, _actor, _order_ = _emergency(dana, brazos)
        push.run_alert_push_job({"payload": {"alert_id": sent["id"], "order_no": "x"}})
        none = work_models.WorkFieldAlert.objects.get(pk=sent["id"]).devices_attempted
        work_models.TechnicianDevice.objects.create(
            tenant=brazos, technician=tech, token="tok-android-1", platform="android", active=True
        )
        push.run_alert_push_job({"payload": {"alert_id": sent["id"], "order_no": "x"}})
        one = work_models.WorkFieldAlert.objects.get(pk=sent["id"]).devices_attempted
    assert (none, one) == (0, 1)


def test_a_repeated_key_sends_one_alert(brazos, dana):
    with tenant_ctx(brazos):
        tech, _actor = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        order = _order(dana, tech)
        body = {"kind": "schedule_change", "work_order_id": order["id"], "key": "k-1"}
        first = field_alerts.send_alert(dana, body)
        again = field_alerts.send_alert(dana, body)
        rows = work_models.WorkFieldAlert.objects.filter(key="k-1").count()
    assert again["id"] == first["id"] and again["duplicate"] is True and rows == 1


def test_send_refusals_by_name(brazos, dana):
    with tenant_ctx(brazos):
        unheld = _order(dana, None, address="1 Nobody Lane")
        with pytest.raises(errors.ValidationError) as kind:
            field_alerts.send_alert(dana, {"kind": "chat", "work_order_id": unheld["id"]})
        with pytest.raises(errors.ValidationError) as text:
            field_alerts.send_alert(dana, {"kind": "dispatch_message"})
        with pytest.raises(errors.ValidationError) as order:
            field_alerts.send_alert(dana, {"kind": "emergency"})
        with pytest.raises(errors.BizError) as nobody:
            field_alerts.send_alert(dana, {"kind": "emergency", "work_order_id": unheld["id"]})
    assert kind.value.params["reason"] == "kind_unknown"
    assert text.value.params["reason"] == "message_required"
    assert order.value.params["reason"] == "order_required"
    assert nobody.value.params["reason"] == "no_technician"


def test_a_dispatch_message_needs_no_order(brazos, dana):
    """FF-42 — *Depot closes at 16:30 on Friday. Return van keys to the box.*"""
    with tenant_ctx(brazos):
        tech, tech_actor = _technician(brazos, "d.ortiz@b.test", "D. Ortiz")
        sent = field_alerts.send_alert(
            dana,
            {"kind": "dispatch_message", "technician_id": str(tech.id),
             "message": "Depot closes at 16:30 on Friday."},
        )
        mine = field_alerts.my_alerts(tech_actor)
    assert sent["order_no"] is None and sent["ack_required"] is False
    assert [r["message"] for r in mine["results"]] == ["Depot closes at 16:30 on Friday."]


# ══════════════════════════════════════════════════════════════════════════
# R28 — acknowledge within five minutes, or dispatch is told
# ══════════════════════════════════════════════════════════════════════════


def test_acknowledged_within_five_minutes_dispatch_is_never_told(brazos, dana):
    with tenant_ctx(brazos):
        sent, _tech, tech_actor, _o = _emergency(dana, brazos)
        answered = field_alerts.acknowledge(tech_actor, sent["id"])
        again = field_alerts.acknowledge(tech_actor, sent["id"])
        swept = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=10))
        row = work_models.WorkFieldAlert.objects.get(pk=sent["id"])
    assert answered["late"] is False and answered["already_acknowledged"] is False
    assert again["already_acknowledged"] is True and again["acknowledged_at"] == answered["acknowledged_at"]
    assert swept["count"] == 0 and row.escalated_at is None


def test_not_acknowledged_in_five_minutes_dispatch_is_told_once(brazos, dana):
    from core import audit as core_audit  # noqa: F401 — the autouse fixture captures rows

    with tenant_ctx(brazos):
        sent, _tech, tech_actor, _o = _emergency(dana, brazos)
        at_four = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=4))
        at_six = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        at_seven = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=7))
        row = work_models.WorkFieldAlert.objects.get(pk=sent["id"])
        # The real clock has not reached the five minutes, so make it have.
        work_models.WorkFieldAlert.objects.filter(pk=sent["id"]).update(
            ack_due_at=timezone.now() - timedelta(seconds=1)
        )
        late = field_alerts.acknowledge(tech_actor, sent["id"])
    assert at_four["count"] == 0
    assert at_six["count"] == 1 and at_seven["count"] == 0
    assert at_six["fired"] == [{"id": sent["id"], "dispatch_told": "escalation_queued"}]
    assert row.escalated_at is not None
    # A late answer is kept, marked late, and dispatch stays told.
    assert late["late"] is True and late["dispatch_told"] is True


def test_the_office_list_shows_an_emergency_past_its_five_minutes(brazos, dana):
    with tenant_ctx(brazos):
        sent, _tech, _ta, _o = _emergency(dana, brazos)
        before = field_alerts.office_alerts(state="overdue")
        work_models.WorkFieldAlert.objects.filter(pk=sent["id"]).update(
            ack_due_at=timezone.now() - timedelta(seconds=1)
        )
        after = field_alerts.office_alerts(state="overdue")
        waiting = field_alerts.office_alerts(state="awaiting_ack")
    assert before["count"] == 0
    assert [r["id"] for r in after["results"]] == [sent["id"]]
    assert waiting["count"] == 1


def test_r28_dispatch_is_told_in_the_bell_with_the_job_and_the_technician(brazos, dana, audit_rows):
    """`DEF-WRK-10350` — R28's *"dispatch is told"*, end to end. This case
    replaced the hold-expiry test that asserted notifications' refusal of
    `emergency_unacknowledged` by name; it went red the day the kind landed,
    as it was written to. Now the sweep's notice is QUEUED under its own
    catalogue switch, reaches whoever sent the alert (and the System Admins),
    and the bell reads it as the job number and the technician — once, for
    this tenant only, with the audit row still written."""
    from datetime import datetime
    from datetime import timezone as dt_timezone

    from apps.notifications import dispatcher, in_app, seed_templates
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=timezone.now().date())
        sent, _tech, _ta, order = _emergency(dana, brazos)
        first = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        row = work_models.WorkFieldAlert.objects.get(pk=sent["id"])
        queued = list(
            notification_models.OutboundMessage.objects.filter(event_key="work_emergency_unacknowledged")
        )
        dispatcher.dispatch_cycle(
            now=datetime.now(dt_timezone.utc), channels=(notification_models.CHANNEL_IN_APP,), actor=dana
        )
        bell = [
            i for i in in_app.inbox(actor=dana)
            if (i.message_key or "").startswith("notifications.workOffice")
        ]
    assert first["fired"] == [{"id": sent["id"], "dispatch_told": "escalation_queued"}]
    assert row.dispatch_told == "escalation_queued"
    assert len(queued) == 1 and queued[0].render_context["event_code"] == "office_emergency_unacknowledged"
    # Hard rule 7 — the escalation's own audit row is still written, once.
    assert [
        str(r["entity_id"]) for r in audit_rows if r.get("action") == field_alerts.ACTION_UNACKNOWLEDGED
    ] == [sent["id"]]
    assert [(i.message_key, i.params["order"], i.params["technician"]) for i in bell] == [
        ("notifications.workOffice.emergency_unacknowledged", order["order_no"], "D. Ortiz")
    ]


def test_the_sweep_fan_out_enqueues_only_a_utility_with_an_emergency_due(brazos, dana):
    from core import jobs as core_jobs

    with tenant_ctx(brazos):
        sent, _tech, _ta, _o = _emergency(dana, brazos)
        assert not field_alerts._due(timezone.now()).exists()
        assert field_alerts._due(timezone.now() + timedelta(minutes=6)).exists()
    assert core_jobs.job_queue(field_alerts.ALERTS_SWEEP_JOB) == "work"
    assert field_alerts.beat_schedule()[field_alerts.BEAT_ENTRY]["schedule"] == 60.0


def test_my_alerts_puts_an_unanswered_emergency_first(brazos, dana):
    with tenant_ctx(brazos):
        sent, tech, tech_actor, order = _emergency(dana, brazos)
        field_alerts.send_alert(dana, {"kind": "schedule_change", "work_order_id": order["id"]})
        mine = field_alerts.my_alerts(tech_actor)
    assert [r["kind"] for r in mine["results"]] == ["emergency", "schedule_change"]
    assert mine["unacknowledged"] == 1


def test_another_technicians_alert_is_a_404(brazos, dana):
    with tenant_ctx(brazos):
        sent, _tech, _ta, _o = _emergency(dana, brazos)
        _other, other_actor = _technician(brazos, "r.patel@b.test", "R. Patel")
        with pytest.raises(errors.NotFoundError):
            field_alerts.acknowledge(other_actor, sent["id"])
        with pytest.raises(errors.NotFoundError):
            field_alerts.acknowledge(dana, sent["id"])  # no technician profile


def test_another_utility_never_sees_or_answers_the_alert(brazos, lonestar, dana, erin):
    with tenant_ctx(brazos):
        sent, _tech, _ta, _o = _emergency(dana, brazos)
    with tenant_ctx(lonestar):
        _their, their_actor = _technician(lonestar, "j.okafor@l.test", "J. Okafor")
        with pytest.raises(errors.NotFoundError):
            field_alerts.acknowledge(their_actor, sent["id"])
        listed = field_alerts.office_alerts(state="all")
        swept = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
    assert listed["count"] == 0 and swept["count"] == 0


def test_the_office_notice_stays_inside_the_utility_that_sent_the_alert(brazos, lonestar, dana, erin):
    """Hard rule 1 — the notice brazos's sweep queues is written under brazos,
    lonestar's sweep finds nothing to tell, and lonestar's bell stays empty."""
    from apps.notifications import in_app
    from apps.notifications import models as notification_models

    with tenant_ctx(brazos):
        _emergency(dana, brazos)
        ours = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        owners = set(
            notification_models.OutboundMessage.objects.filter(
                event_key="work_emergency_unacknowledged"
            ).values_list("tenant_id", flat=True)
        )
    with tenant_ctx(lonestar):
        theirs = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        their_bell = in_app.inbox(actor=erin)
    assert ours["count"] == 1 and owners == {brazos.id}
    assert theirs["count"] == 0 and their_bell == ()

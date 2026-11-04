# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 5, lane SRV-4 — P3.57 (the seven escalations
#           fire, once per job per kind), P3.58 (their messages are catalogue
#           rows with a switch), P3.59 (reminders live in Notifications).
# Rules:    Ruling 34 · BR-NOT-021 narrowed for Work escalations (PO
#           2026-10-04) · BR-NOT-017 · CLAUDE.md rule 6 · hard rule 7
# ───────────────────────────────────────────────────────
"""A stalled job is told about once, to the ruled people and the rule's extra
ones. Runs on SQLite and on PostgreSQL 16 (`config.settings.pgtest`)."""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timedelta, timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.notifications import dispatcher, in_app, models, rule_catalog, seed_templates
from apps.work import models as work_models
from apps.work import rules
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_installed_asset, staff_actor, tenant_ctx

pytestmark = pytest.mark.django_db

SEEDED_ON = datetime(2026, 8, 17, 9, 0, tzinfo=dt_timezone.utc)
YESTERDAY = dt.date.today() - dt.timedelta(days=1)


def _template(actor):
    header = w6.create_work_order_template(actor, {"name": "Meter exchange", "service": "electric", "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _rule_job(actor, tenant, escalations):
    """A job the asset-age rule raised overnight, carrying `escalations`."""
    template = _template(actor)
    # INSTALLED (`CR-168-BRC10` §30, `BR-WRK-066`).
    asset = make_installed_asset(actor, asset_no=f"AST-{len(escalations)}-77")
    from apps.assets import models as assets_models

    assets_models.Asset.objects.filter(pk=asset["id"]).update(certification_due=YESTERDAY)
    rule = rules.create_rule(
        actor,
        {"name": "Asset age rule", "triggers": [{"kind": "asset_age_rule", "params": {}}],
         "template_id": template["id"], "escalations": escalations},
    )
    rules.sweep(actor)
    order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
    return rule, order


def _rows():
    return list(models.OutboundMessage.objects.filter(source_type="field_work").order_by("created_at"))


def test_p357_nobody_picked_it_up_after_four_hours_tells_the_admins_and_the_extra_person_once(brazos, dana):
    """RED on the tip: nothing read `escalation` — ``AttributeError: module
    'apps.work' has no attribute 'escalations'`` and no message was queued."""
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        supervisor = staff_actor(brazos, role="billing_clerk", email="area.supervisor@b.test")
        rule, order = _rule_job(
            dana, brazos,
            [{"kind": "unassigned", "after_hours": 4,
              "also_tell": [{"kind": "user", "id": str(supervisor.user.id)}]}],
        )
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=5))

        first = escalations.escalate()
        second = escalations.escalate()
        rows = _rows()
        recipients = {e["user_id"]: e["reason"] for e in rows[0].recipient_snapshot["recipients"]}
        fires = work_models.WorkOrderRuleEscalationFire.objects.filter(work_order_id=order.id)

    assert first["count"] == 1 and second["count"] == 0
    assert [(f.kind) for f in fires] == ["unassigned"]
    assert len(rows) == 1
    assert rows[0].render_context["event_code"] == "escalation_unassigned"
    # BR-NOT-021: every active System Admin (nobody acted — the rule raised it
    # and nobody has assigned it) — AND the rule's extra person.
    assert "system_admin" in recipients.values()
    assert recipients[str(supervisor.user.id)] == "also_tell"


def test_p357_a_job_not_yet_four_hours_old_is_not_escalated(brazos, dana):
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        _rule, order = _rule_job(dana, brazos, [{"kind": "unassigned", "after_hours": 4}])
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=3))
        assert escalations.escalate()["count"] == 0


def test_p357_overdue_does_not_count_time_on_hold(brazos, dana):
    """Due 10 h ago, but on hold for the last 12 h: its promise moved 12 h, so
    it is not past due by 1 h yet (P5.2)."""
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        _rule, order = _rule_job(dana, brazos, [{"kind": "overdue", "after_hours": 1}])
        now = timezone.now()
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(
            due_at=now - timedelta(hours=10), held_at=now - timedelta(hours=12)
        )
        assert escalations.escalate()["count"] == 0
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(held_at=None)
        out = escalations.escalate()
        rows = _rows()
    assert out["count"] == 1
    assert rows[0].render_context["event_code"] == "escalation_overdue"


def test_p357_a_job_waiting_for_approval_too_long_is_told_and_reads_in_the_bell(brazos, dana):
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        _rule, order = _rule_job(dana, brazos, [{"kind": "not_approved", "after_hours": 24}])
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(
            state=work_tables.WO_COMPLETED, completed_at=timezone.now() - timedelta(hours=25)
        )
        # Dana sent it to the field: she is whoever acted, and is told.
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(assigned_by_id=dana.user.id)
        escalations.escalate()
        dispatcher.dispatch_cycle(
            now=datetime.now(dt_timezone.utc), channels=(models.CHANNEL_IN_APP,), actor=dana
        )
        bell = [
            i for i in in_app.inbox(actor=dana)
            if (i.message_key or "").startswith("notifications.work")
        ]
    assert [(i.message_key, i.params["order"], i.params["count"]) for i in bell] == [
        ("notifications.workEscalation.not_approved", order.order_no, 24)
    ]


def test_p358_a_utility_that_switches_the_escalation_off_is_not_told(brazos, dana):
    from apps.notifications import rule_service
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        rule_service.update_rule(event_key="work_job_not_assigned", actor=dana, enabled=False)
        _rule, order = _rule_job(dana, brazos, [{"kind": "unassigned", "after_hours": 1}])
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(hours=2))
        out = escalations.escalate()
        rows = _rows()
    assert out["count"] == 1, "the fire is recorded either way"
    assert rows == [], "the utility's own switch suppressed the message (BR-NOT-017)"


def test_p358_the_six_escalations_and_two_reminders_are_catalogue_rows_and_sla_breach_is_live():
    keys = set(rule_catalog.EVENT_KEYS)
    for key in (
        "work_job_not_assigned", "work_job_not_accepted", "work_job_running_late",
        "work_hold_overdue", "work_job_failed", "work_approval_overdue",
        "certificate_expiring", "technician_day",
    ):
        assert key in keys, key
    assert rule_catalog.event("sla_breach").trigger_blocked_by is None


AT_04_UTC = datetime(2026, 10, 5, 4, 0, tzinfo=dt_timezone.utc)  # 23:00 on 4 Oct in Texas


def test_p359_a_certificate_running_out_tells_the_admins_once(brazos, dana):
    from apps.tenancy import models as tenancy_models
    from apps.work import escalations

    with tenant_ctx(brazos):
        seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
        kind = tenancy_models.CertificationType.objects.create(tenant=brazos, code="BF", name="Backflow tester")
        from apps.identity import models as identity_models

        user = identity_models.User.objects.create(tenant=brazos, email="dortiz@b.test", full_name="D. Ortiz")
        tech = work_models.Technician.objects.create(tenant=brazos, user=user)
        from apps.work.seams import tenancy_seam

        work_models.TechnicianCertification.objects.create(
            tenant=brazos, technician=tech, certification_type_id=kind.id,
            # `DEF-WRK-9695` — 17 days from the UTILITY's today, which is what
            # `remind` counts from. The case read `date.today()` (the machine's
            # UTC day) and went red between UTC midnight and the tenant's: at
            # 04:00 UTC on 5 Oct it is still 4 Oct in Texas and the reminder
            # rightly said 18. The clock is pinned to that hour so the case
            # cannot pass by the time of day it happens to run.
            expires_on=AT_04_UTC.astimezone(tenancy_seam.tenant_timezone()).date()
            + dt.timedelta(days=17),
        )
        first = escalations.remind(now=AT_04_UTC)
        second = escalations.remind(now=AT_04_UTC)
        rows = [r for r in _rows() if r.render_context["event_code"] == "certificate_expiring"]
    assert first["certificates"] == 1 and second["certificates"] == 0
    assert len(rows) == 1
    assert rows[0].render_context["count"] == 17
    assert "D. Ortiz" in rows[0].render_context["order_no"]


def test_p359_a_rule_cannot_carry_reminders_and_an_unknown_escalation_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        template = _template(dana)
        base = {"name": "R", "triggers": [{"kind": "asset_age_rule", "params": {}}],
                "template_id": template["id"]}
        with pytest.raises(errors.ValidationError) as caught:
            rules.create_rule(dana, {**base, "reminders": [{"after_hours": 4}]})
        assert caught.value.message_key == "work.rules.reminders_live_in_notifications"
        with pytest.raises(errors.ValidationError) as caught:
            rules.create_rule(dana, {**base, "escalations": [{"kind": "lunch", "after_hours": 1}]})
        assert caught.value.message_key == "work.rules.escalation_unknown"

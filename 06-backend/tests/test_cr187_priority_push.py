# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 — PO answer 9 of 2026-10-21 (decision log *"Field app:
#           ten PO answers"*): a job MAY be pushed as urgent or emergency
#           AUTOMATICALLY, not only when a dispatcher chooses.
# Rules:    BR-WRK-034 (the push on assignment) · BR-FLD-00028 (R28 — an
#           emergency is acknowledged within five minutes) · BR-WRK-018 (the
#           priority list is the tenant's) · hard rules 1 and 7
# Code:     apps/work/dispatch.py (`push_kind_for`, `push_after_assign`) ·
#           apps/work/push.py (`run_push_job`) · apps/work/field_alerts.py
#           (`record_assignment_alert`) · apps/work/lookups.py (the setting) ·
#           apps/work/migrations/0045_cr187_push_kind_report_versions.py
# ───────────────────────────────────────────────────────
"""How an assignment rings is the priority's setting; a dispatcher may override.

⚠ **AND THE SETTING IS AN OPTION (PO answer 9 as corrected the same day).**
`work_settings.push_by_priority` is seeded OFF for every tenant: OFF, every
assignment rings as a new job and only a dispatcher's explicit choice sends
urgent or emergency; ON, the priority's `push_kind` decides. Both states are
tested here by name.

Run with `JOBS_EAGER=false --reuse-db` (the push tests' own reason): every
assertion reads the job ROW and the alert ROW, never a body that ran inline.
"""

from __future__ import annotations

import importlib
from datetime import timedelta

import pytest
from django.apps import apps as django_apps
from django.utils import timezone

from apps.metering import connections as w6
from apps.tenancy import models as tenancy_models
from apps.work import dispatch, field_alerts, push
from apps.work import models as work_models
from apps.work import services as work_services
from apps.work.lookups import WorkPriorityLookupHandler
from core import errors
from core import tenancy as core_tenancy

from tests.test_us_idn_helpers import idn  # noqa: F401 — fixture used by name
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _priorities(tenant):
    """The tenant's priorities, seeded from `SEED_PRIORITIES` when the fixture
    tenant was provisioned without them."""
    if not work_models.WorkPriority.objects.filter(tenant_id=tenant.id).exists():
        work_services.seed_reference_list("work_priorities", [], "test")
    return {
        row.code: row
        for row in work_models.WorkPriority.objects.filter(tenant_id=tenant.id)
    }


def _technician(tenant, email="d.ortiz@b.test", name="D. Ortiz"):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant=tenant, email=email, full_name=name)
    tech = work_models.Technician.objects.create(tenant=tenant, user=user)
    work_models.TechnicianDevice.objects.create(
        tenant=tenant, technician=tech, token="fxtr-ortiz-01", platform="web"
    )
    actor = type("Actor", (), {"id": user.id, "pk": user.id, "role": "field_technician"})()
    return tech, actor


def _order(actor, priority=None, service="electric", address="14 Oak Street"):
    premises = make_premises(actor, address_line=address, services_available=[service])
    order = w6.create_work_order(
        actor, None, {"premises_id": str(premises["id"]), "type": "Gas leak"}
    )
    if priority is not None:
        dispatch.change_priority(actor, order["id"], {"priority_id": str(priority.id)})
    return order


def _switch(tenant, on: bool):
    """Turn the tenant's *push by priority* option ON or OFF through the
    service the Settings screen calls."""
    from apps.work import workforce

    actor = type("Actor", (), {"id": None, "pk": None})()
    return workforce.set_push_settings(actor, {"push_by_priority": on})


def _push_jobs():
    return list(
        tenancy_models.Job.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(), kind=push.PUSH_JOB
        ).order_by("created_at", "id")
    )


def _alerts():
    return list(
        work_models.WorkFieldAlert.objects.filter(
            tenant_id=core_tenancy.current_tenant_id()
        ).order_by("sent_at", "id")
    )


# ══════════════════════════════════════════════════════════════════════════
# The setting — seeded, read and written on the existing settings API
# ══════════════════════════════════════════════════════════════════════════


def test_the_seed_rings_the_most_urgent_as_emergency_the_next_as_urgent_the_rest_as_new_job(
    brazos,
):
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
    assert rows["URGENT"].push_kind == "emergency"
    assert rows["HIGH"].push_kind == "urgent_assignment"
    assert rows["NORMAL"].push_kind == "new_job" and rows["LOW"].push_kind == "new_job"


def test_the_migration_seeds_existing_tenants_by_rank_among_active_priorities(brazos):
    """`work/0045` on a tenant whose priorities predate the column: the lowest
    ACTIVE rank is `emergency`, the next `urgent_assignment`, the rest stay
    `new_job` — an inactive priority is skipped, never seeded."""
    migration = importlib.import_module(
        "apps.work.migrations.0045_cr187_push_kind_report_versions"
    )
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        work_models.WorkPriority.objects.filter(tenant_id=brazos.id).update(push_kind="new_job")
        work_models.WorkPriority.objects.filter(pk=rows["URGENT"].pk).update(active=False)
        written = migration._apply_tenant(django_apps, brazos.id)
        after = {
            row.code: row.push_kind
            for row in work_models.WorkPriority.objects.filter(tenant_id=brazos.id)
        }
    assert written == 2
    assert after == {
        "URGENT": "new_job",
        "HIGH": "emergency",
        "NORMAL": "urgent_assignment",
        "LOW": "new_job",
    }


def test_the_settings_api_reads_and_writes_the_push_kind_and_refuses_anything_else(brazos):
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        handler = WorkPriorityLookupHandler()
        read = handler.serialize(rows["NORMAL"])
        handler.update(rows["NORMAL"], {"push_kind": "urgent_assignment"})
        written = work_models.WorkPriority.objects.get(pk=rows["NORMAL"].pk).push_kind
        with pytest.raises(errors.ValidationError) as refused:
            handler.update(rows["NORMAL"], {"push_kind": "siren"})
        created = handler.create({"code": "P5", "name": "Whenever", "sla_hours_text": "240 h"})
    assert read["push_kind"] == "new_job"
    assert written == "urgent_assignment"
    assert refused.value.message_key == "work.priorities.push_kind_unknown"
    assert refused.value.field_errors[0]["field"] == "push_kind"
    assert created.push_kind == "new_job", "a priority the utility adds rings as a new job"


# ══════════════════════════════════════════════════════════════════════════
# The assignment rings as the priority says
# ══════════════════════════════════════════════════════════════════════════


def test_an_urgent_priority_assignment_is_pushed_as_an_emergency_with_rs28_five_minutes(
    brazos, dana, audit_rows
):
    """The setting rang it, not a person: the SAME acknowledgeable alert a
    dispatcher's emergency send writes, keyed to the assignment, and the push
    job rings the emergency channel and stamps that alert."""
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        order = _order(dana, rows["URGENT"])
        result = dispatch.record_act(
            dana, order["id"], {"act": "assign", "technician_id": str(tech.id)}
        )
        jobs = _push_jobs()
        alerts = _alerts()
        push.run_push_job({"id": str(jobs[-1].id), "payload": jobs[-1].payload})
        stamped = work_models.WorkFieldAlert.objects.get(pk=alerts[0].pk)

    assert len(jobs) == 1 and jobs[0].payload["push_kind"] == "emergency"
    assert len(alerts) == 1
    alert = alerts[0]
    assert alert.kind == "emergency" and alert.ack_required is True
    assert alert.ack_due_at - alert.sent_at == timedelta(minutes=5)
    assert alert.key == f"assignment:{result['assignment_id']}"
    assert jobs[0].payload["alert_id"] == str(alert.id)
    assert stamped.devices_attempted == 1 and stamped.pushed_at is not None
    sent = [r for r in audit_rows if r["action"] == "work.alert.sent"]
    assert sent and sent[-1]["after"]["automatic"] is True
    pushed = [r for r in audit_rows if r["action"] == push.ACTION_PUSHED]
    assert pushed and pushed[-1]["after"]["kind"] == "emergency"


def test_an_automatic_emergency_left_unanswered_is_escalated_by_the_same_sweep(brazos, dana):
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        order = _order(dana, rows["URGENT"])
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(tech.id)})
        at_four = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=4))
        at_six = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
        overdue = field_alerts.office_alerts(state="awaiting_ack")
    assert at_four["count"] == 0 and at_six["count"] == 1
    assert overdue["results"] and overdue["results"][0]["kind"] == "emergency"


def test_a_high_priority_assignment_rings_as_urgent_and_needs_no_acknowledgement(brazos, dana):
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        order = _order(dana, rows["HIGH"])
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(tech.id)})
        jobs = _push_jobs()
        alerts = _alerts()
    assert jobs[-1].payload["push_kind"] == "urgent_assignment"
    assert len(alerts) == 1 and alerts[0].kind == "urgent_assignment"
    assert alerts[0].ack_required is False and alerts[0].ack_due_at is None


def test_a_normal_priority_or_none_rings_as_a_new_job_and_writes_no_alert(brazos, dana):
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        normal = _order(dana, rows["NORMAL"], address="1 Elm St")
        bare = _order(dana, None, address="2 Elm St")
        dispatch.record_act(dana, normal["id"], {"act": "assign", "technician_id": str(tech.id)})
        dispatch.record_act(dana, bare["id"], {"act": "assign", "technician_id": str(tech.id)})
        jobs = _push_jobs()
        alerts = _alerts()
    assert [j.payload["push_kind"] for j in jobs] == ["new_job", "new_job"]
    assert alerts == []


def test_the_dispatcher_can_still_choose_explicitly(brazos, dana):
    """An Urgent job pushed as an ordinary job, and a Low one as an emergency —
    the person's choice wins over the setting, both ways."""
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        urgent = _order(dana, rows["URGENT"], address="1 Elm St")
        low = _order(dana, rows["LOW"], address="2 Elm St")
        dispatch.record_act(
            dana,
            urgent["id"],
            {"act": "assign", "technician_id": str(tech.id), "push_kind": "new_job"},
        )
        dispatch.record_act(
            dana,
            low["id"],
            {"act": "assign", "technician_id": str(tech.id), "push_kind": "emergency"},
        )
        jobs = _push_jobs()
        alerts = _alerts()
    assert [j.payload["push_kind"] for j in jobs] == ["new_job", "emergency"]
    assert len(alerts) == 1 and str(alerts[0].work_order_id) == str(low["id"])


def test_an_unknown_push_kind_is_refused_before_anything_is_written(brazos, dana):
    with tenant_ctx(brazos):
        tech, _actor = _technician(brazos)
        order = _order(dana)
        with pytest.raises(errors.ValidationError) as refused:
            dispatch.record_act(
                dana,
                order["id"],
                {"act": "assign", "technician_id": str(tech.id), "push_kind": "siren"},
            )
        assigned = work_models.WorkOrderAssignment.objects.filter(
            work_order_id=order["id"]
        ).count()
    assert refused.value.message_key == "work.priorities.push_kind_unknown"
    assert assigned == 0


# ══════════════════════════════════════════════════════════════════════════
# The option — seeded OFF; OFF means only a dispatcher sends urgent/emergency
# ══════════════════════════════════════════════════════════════════════════


def test_push_by_priority_is_off_for_every_tenant_until_a_utility_turns_it_on(brazos, lonestar):
    from apps.work import workforce

    with tenant_ctx(brazos):
        assert workforce.push_settings() == {"push_by_priority": False}
        assert dispatch.push_by_priority_on() is False
    with tenant_ctx(lonestar):
        assert workforce.push_settings() == {"push_by_priority": False}


def test_switched_off_an_urgent_job_rings_as_a_new_job_and_writes_no_alert(brazos, dana):
    """OFF (the seeded state): the URGENT priority's `emergency` mapping is
    ignored; only the dispatcher's explicit choice sends one."""
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        tech, _actor = _technician(brazos)
        auto = _order(dana, rows["URGENT"], address="1 Elm St")
        chosen = _order(dana, rows["NORMAL"], address="2 Elm St")
        dispatch.record_act(dana, auto["id"], {"act": "assign", "technician_id": str(tech.id)})
        dispatch.record_act(
            dana,
            chosen["id"],
            {"act": "assign", "technician_id": str(tech.id), "push_kind": "emergency"},
        )
        jobs = _push_jobs()
        alerts = _alerts()
    assert [j.payload["push_kind"] for j in jobs] == ["new_job", "emergency"]
    assert len(alerts) == 1 and str(alerts[0].work_order_id) == str(chosen["id"])
    assert alerts[0].ack_required is True


def test_turning_it_on_and_off_is_audited_and_refuses_a_non_boolean(brazos, audit_rows):
    from apps.work import workforce

    with tenant_ctx(brazos):
        on = _switch(brazos, True)
        off = _switch(brazos, False)
        with pytest.raises(errors.ValidationError) as refused:
            workforce.set_push_settings(None, {"push_by_priority": "yes"})
    assert on == {"push_by_priority": True} and off == {"push_by_priority": False}
    rows = [r for r in audit_rows if r["action"] == "work.settings.push_by_priority_set"]
    assert [r["after"]["push_by_priority"] for r in rows] == [True, False]
    assert refused.value.message_key == "work.settings.push_by_priority_not_boolean"


# ══════════════════════════════════════════════════════════════════════════
# Through the stack: the System Admin writes; a clerk reads and cannot
# ══════════════════════════════════════════════════════════════════════════


def _signed_in(idn, email, role):
    from django.test import Client

    from tests.test_us_idn_helpers import JSON, SC, api_path

    idn.make_user(idn.silvercreek, email, "Test Person", password="Prairie2026grass", role=role)
    client = Client()
    response = client.post(
        api_path("/auth/session", SC),
        data={"email": email, "password": "Prairie2026grass"},
        content_type=JSON,
    )
    assert response.status_code == 201, response.content
    return client


def test_the_settings_routes_round_trip_the_option_and_the_mapping(idn):
    from tests.isolation_helpers import writing_as_tenant
    from tests.test_us_idn_helpers import JSON, SC, api_path

    admin = _signed_in(idn, "admin.push@silvercreek.example", "system_admin")
    clerk = _signed_in(idn, "clerk.push@silvercreek.example", "billing_clerk")
    with writing_as_tenant(idn.silvercreek):
        rows = _priorities(idn.silvercreek)

    read = admin.get(api_path("/work/settings/push", SC))
    assert read.status_code == 200, read.content
    assert read.json() == {"push_by_priority": False}
    wrote = admin.post(
        api_path("/work/settings/push", SC), data={"push_by_priority": True}, content_type=JSON
    )
    assert wrote.status_code == 200, wrote.content
    assert wrote.json() == {"push_by_priority": True}
    refused = clerk.post(
        api_path("/work/settings/push", SC), data={"push_by_priority": False}, content_type=JSON
    )
    assert refused.status_code == 403

    listed = admin.get(api_path("/lookups/work_priorities?per=50", SC))
    assert listed.status_code == 200, listed.content
    by_code = {r["code"]: r for r in listed.json()["results"]}
    assert by_code["URGENT"]["push_kind"] == "emergency"
    assert by_code["LOW"]["push_kind"] == "new_job"
    etag = listed.get("ETag")
    patched = admin.patch(
        api_path(f"/lookups/work_priorities/{rows['LOW'].id}", SC),
        data={"push_kind": "emergency"},
        content_type=JSON,
        **({"HTTP_IF_MATCH": etag} if etag else {}),
    )
    assert patched.status_code == 200, patched.content
    with writing_as_tenant(idn.silvercreek):
        assert work_models.WorkPriority.objects.get(pk=rows["LOW"].pk).push_kind == "emergency"


def test_the_automatic_alert_stays_inside_the_utility_that_assigned(brazos, lonestar, dana, erin):
    """Tenant isolation: Lone Star's office list and its sweep see nothing of
    Brazos's automatic emergency."""
    with tenant_ctx(brazos):
        rows = _priorities(brazos)
        _switch(brazos, True)
        tech, _actor = _technician(brazos)
        order = _order(dana, rows["URGENT"])
        dispatch.record_act(dana, order["id"], {"act": "assign", "technician_id": str(tech.id)})
    with tenant_ctx(lonestar):
        theirs = field_alerts.office_alerts(state="all")
        swept = field_alerts.escalate_unacknowledged(now=timezone.now() + timedelta(minutes=6))
    assert theirs["results"] == [] and swept["count"] == 0

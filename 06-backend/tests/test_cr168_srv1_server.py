# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 2, lane SRV-1 — P0.1, P0.3, P0.4, P1.6, P1.15,
#           P1.23, P1.25, P1.31, P1.33, P1.34, P4.11 and the default SLA target
# Rules:    CR-168-BRC10 §7.3 (the agreed contract) · judgments J1–J4, J7, J8 ·
#           ruling 18 · PO answers (1) and (3) of 2026-10-04 · BR-WRK-026 (six
#           filters) · NFR-3 (paged) · hard rules 3 and 7
# Tests:    this file (SQLite); tests/test_cr168_srv1_migrations_pg.py (PG)
# ───────────────────────────────────────────────────────
"""CR-168 round 2 · SRV-1 — the server half the redrawn Orders, order page and
edit page build against. Each case names the task or defect it proves; the six
held round-1 cases (`test_cr168_round1_held_defects.py`) prove the defects."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import api as work_api
from apps.work import dispatch, edit, evidence, workforce
from apps.work import models as work_models
from apps.work import services as work_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import make_premises, make_unit
from tests.test_us_ten_helpers import api_call, tenant_ctx

pytestmark = pytest.mark.django_db


@pytest.fixture()
def stored_audit():
    from apps.audit import services as audit_services
    from core import audit as core_audit

    previous = core_audit._sink
    core_audit.set_audit_sink(audit_services.store_row)
    yield
    core_audit.set_audit_sink(previous)


def _reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _order(actor, address="77 Cedar Ct", **payload):
    premises = make_premises(actor, address_line=address, services_available=["water"])
    body = {"type": "Leak investigation", "service": "water", "premises_id": premises["id"], **payload}
    return w6.create_work_order(actor, None, body)


def _technician(tenant, email, name, crew=None):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user, crew=crew)


def _as(technician):
    return SimpleNamespace(id=technician.user_id, role="field_technician")


def _assign(actor, order_id, technician=None, crew=None):
    body = {"act": "assign"}
    if technician is not None:
        body["technician_id"] = str(technician.id)
    if crew is not None:
        body["crew_id"] = str(crew.id)
    return dispatch.record_act(actor, order_id, body)


# ── P1.34 · ruling 18 — who may close ─────────────────────────────────────


def test_p1_34_the_technician_given_the_job_closes_it(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana)
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        _assign(dana, raised["id"], technician=tech)
        out = w6.submit_field_result(_as(tech), raised["id"], field_data={}, outcome="passed")
        assert out["state"] == "completed"


def test_p1_34_a_member_of_the_crew_given_the_job_closes_it(dana, brazos):
    """Ruling 36 — a crew's (or a contractor's) people close their own jobs."""
    with tenant_ctx(brazos):
        _reference()
        crew = work_models.Crew.objects.create(tenant_id=brazos.id, name="Apex Utility Svc",
                                               kind="contractor")
        member = _technician(brazos, "apex-1@brazos.test", "A. Member", crew=crew)
        raised = _order(dana)
        _assign(dana, raised["id"], crew=crew)
        out = w6.submit_field_result(_as(member), raised["id"], field_data={}, outcome="passed")
        assert out["state"] == "completed"


def test_p1_34_another_technician_and_an_unassigned_job_are_refused(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        given = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        other = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        raised = _order(dana)
        nobody = _order(dana, "12 Kestrel Park")
        _assign(dana, raised["id"], technician=given)
        for actor, order_id in ((_as(other), raised["id"]), (_as(given), nobody["id"])):
            with pytest.raises(errors.AuthError) as caught:
                w6.submit_field_result(actor, order_id, field_data={}, outcome="passed")
            assert caught.value.message_key == "work.order.closed_by_field_only"


# ── P1.31 · the dispatch axis moves with the close, except a person's hold ──


def test_p1_31_a_held_job_closed_by_the_field_stays_on_hold(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=tech)
        dispatch.hold(dana, raised["id"], {"reason_code": "WEATHER"})
        w6.submit_field_result(_as(tech), raised["id"], field_data={}, outcome="passed")
        row = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert (row.state, row.dispatch_state) == ("completed", "on_hold")


# ── P1.6 · status=complete reads the finished jobs (J3) ───────────────────


def test_p1_6_status_complete_lists_finished_jobs_accepted_or_not(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        done = _order(dana, "1 Done St")
        still_open = _order(dana, "2 Open St")
        _assign(dana, done["id"], technician=tech)
        w6.submit_field_result(_as(tech), done["id"], field_data={}, outcome="passed")
        finished = dispatch.dispatch_page(filters={"status": "complete"})
        assert [row["order_no"] for row in finished["rows"]] == [done["order_no"]]
        assert finished["rows"][0]["dispatch_state"] == "complete"
        assert finished["rows"][0]["accepted"] is None
        live = dispatch.dispatch_page(filters={})
        assert [row["order_no"] for row in live["rows"]] == [still_open["order_no"]]


def test_p1_6_the_list_still_refuses_a_seventh_filter_and_accepts_the_declared_sorts(
    dana, brazos
):
    with tenant_ctx(brazos):
        _reference()
        first = _order(dana, "1 A St")
        second = _order(dana, "2 B St")
        page = dispatch.dispatch_page(sort="order_no", direction="desc")
        assert [r["order_no"] for r in page["rows"]] == [second["order_no"], first["order_no"]]
    with pytest.raises(errors.ValidationError):
        dispatch.check_filters(["q", "status", "premises"])


def test_p1_6_a_row_carries_hold_acceptance_and_its_promise(dana, brazos):
    """§7.3: `hold`, `technician_acceptance`, `accepted`, `sla` on every row.
    An undated, priority-less job is measured against Normal's 72 h (J7)."""
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana)
        work_tables.WorkOrder.objects.filter(pk=raised["id"]).update(priority=None, due_at=None)
        row = dispatch.dispatch_page()["rows"][0]
        assert row["hold"] is None and row["technician_acceptance"] is None
        assert row["sla"]["target"] == "default"
        made = work_tables.WorkOrder.objects.get(pk=raised["id"]).created_at
        assert row["sla"]["due_at"] == (made + timedelta(hours=72)).isoformat()
        dispatch.hold(dana, raised["id"], {"reason_code": "WAITING_PART",
                                            "expected_return_on": "2026-10-09"})
        row = dispatch.dispatch_page(filters={"status": "on_hold"})["rows"][0]
        assert row["hold"]["reason"] == {"code": "WAITING_PART", "name": "Waiting for a part"}
        assert row["hold"]["expected_return_on"] == "2026-10-09"


# ── P0.3/P0.4 · hold with a reason, resume, and the clock ─────────────────


def test_p0_3_hold_needs_a_known_reason_and_resume_counts_the_time(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=tech)
        with pytest.raises(errors.ValidationError) as missing:
            dispatch.hold(dana, raised["id"], {})
        assert missing.value.message_key == "work.hold.reason_required"
        with pytest.raises(errors.ValidationError) as unknown:
            dispatch.hold(dana, raised["id"], {"reason_code": "PERMIT"})
        assert unknown.value.message_key == "work.hold.reason_unknown"
        dispatch.hold(dana, raised["id"], {"reason_code": "weather"})
        work_tables.WorkOrder.objects.filter(pk=raised["id"]).update(
            held_at=timezone.now() - timedelta(hours=2)
        )
        out = dispatch.resume(dana, raised["id"])
        assert out["dispatch_state"] == "scheduled"  # back to where the history says
        row = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert 7190 <= row.held_seconds <= 7300
        assert (row.held_at, row.hold_reason_id) == (None, None)
        with pytest.raises(errors.ValidationError) as again:
            dispatch.resume(dana, raised["id"])
        assert again.value.message_key == "work.hold.not_on_hold"


def test_p0_4_the_five_reasons_are_seeded_and_served_by_rank(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        # §7.3 `{code, name, active, rank}` — the flag is sent (lane SRV-3).
        assert all(r["active"] is True for r in dispatch.hold_reasons())
        assert [r["name"] for r in dispatch.hold_reasons()] == [
            "Weather", "Waiting for a part", "Customer not home", "Access refused", "Other",
        ]


# ── P4.11 · the order's whole history, paged (DEF-WRK-9532) ───────────────


def test_p4_11_the_history_holds_assign_hold_resume_close_and_is_paged(
    dana, brazos, stored_audit, monkeypatch
):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=tech)
        dispatch.hold(dana, raised["id"], {"reason_code": "WEATHER", "note": "Lightning"})
        dispatch.resume(dana, raised["id"])
        w6.submit_field_result(_as(tech), raised["id"], field_data={}, outcome="passed")
        full = dispatch.order_audit(raised["id"])
        assert [r["act"] for r in full["rows"]] == ["assign", "hold", "resume", "completed"]
        hold = full["rows"][1]
        assert (hold["after_display"], hold["reason"]) == ("Weather", "Lightning")
        assert hold["by"]["name"]
        # The house sizes start at 10; the slice is the same arithmetic at 2.
        monkeypatch.setattr(dispatch, "clamp_page_size", lambda per: int(per))
        second = dispatch.order_audit(raised["id"], page=2, per=2)
        assert second["total"] == 4
        assert [r["act"] for r in second["rows"]] == ["resume", "completed"]


def test_p4_11_a_reassign_reads_as_one_act_with_its_reason(dana, brazos):
    """J2 — two rows sharing an `act_group`, shown as one `reassign` line."""
    import uuid

    with tenant_ctx(brazos):
        _reference()
        first = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        second = _technician(brazos, "r-patel@brazos.test", "R. Patel")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=first)
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        group = uuid.uuid4()
        for act, tech in (("unassign", None), ("assign", second)):
            work_models.WorkOrderAssignment.objects.create(
                tenant_id=brazos.id, work_order=order, act=act, technician=tech,
                actor_id=dana.id, reason="Van in the shop", act_group=group,
            )
        rows = dispatch.order_audit(raised["id"])["rows"]
        assert [r["act"] for r in rows] == ["assign", "reassign"]
        assert rows[1]["reason"] == "Van in the shop"
        assert rows[1]["who"]["name"] == "R. Patel"


def test_p4_11_the_audit_route_answers_the_house_envelope(dana, brazos, stored_audit):
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana)
        dispatch.hold(dana, raised["id"], {"reason_code": "OTHER"})
    response = api_call(
        work_api.work_order_audit, "get", f"/api/{brazos.subdomain}/work-orders/x/audit",
        user=dana.user, role="system_admin", tenant=brazos, order_id=raised["id"],
    )
    assert response.status_code == 200, response.data
    assert {"count", "next", "previous", "results", "order_no"} <= set(response.data)
    assert response.data["count"] == 1
    # The one-round `rows` twin is retired (lane SRV-3, 2026-10-04).
    assert "rows" not in response.data


# ── P1.25 · the edit page opens with the truth ────────────────────────────


def test_p1_25_the_edit_form_serves_the_holder_appointment_and_priorities(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=tech)
        work_tables.WorkOrder.objects.filter(pk=raised["id"]).update(
            window_start="2026-10-09T13:00:00Z", window_end="2026-10-09T17:00:00Z"
        )
        values = edit.form_values(raised["id"])
        assert values["technician"]["id"] == str(tech.id)
        assert values["technician"]["kind"] == "person"
        assert [p["code"] for p in values["priorities"]] == ["URGENT", "HIGH", "NORMAL", "LOW"]
        # 13:00–17:00 UTC is 08:00–12:00 in Brazos Bend's own day (Central).
        assert values["appointment"]["date"] == "2026-10-09"
        assert (values["appointment"]["start"], values["appointment"]["end"]) == ("08:00", "12:00")


def test_p1_34_the_edit_page_cannot_set_complete(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana)
        with pytest.raises(errors.ValidationError) as caught:
            edit.save_order_edit(dana, raised["id"], {"dispatch_state": "complete"})
        assert caught.value.message_key == "work.order.closed_by_field_only"


# ── the default SLA target (PO answer 1, J7) ──────────────────────────────


def test_default_target_is_normal_until_a_tenant_names_another(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        seeded = workforce.default_target()
        assert (seeded["priority"]["code"], seeded["hours"], seeded["chosen"]) == ("NORMAL", 72, False)
        high = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="HIGH")
        chosen = workforce.set_default_target(dana, {"default_target_priority_id": str(high.id)})
        assert (chosen["priority"]["code"], chosen["hours"], chosen["chosen"]) == ("HIGH", 8, True)
        with pytest.raises(errors.ValidationError) as caught:
            workforce.set_default_target(dana, {"default_target_priority_id": ""})
        assert caught.value.message_key == "work.settings.sla_priority_unknown"


# ── P1.33 · a reading that is words ───────────────────────────────────────


def test_p1_33_a_text_reading_is_stored_as_text_and_never_posts(dana, brazos):
    with tenant_ctx(brazos):
        _reference()
        raised = _order(dana)
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        reading = work_models.WorkOrderReading.objects.create(
            tenant_id=brazos.id, work_order=order, seq=1, prompt="Seal number",
            unit_of_measure="", kind="text", posts_as_meter_read=False,
        )
        out = evidence.set_reading(dana, raised["id"], reading.id, {"value_text": "W-5000-N"})
        assert (out["kind"], out["value_text"], out["value"], out["in_range"]) == (
            "text", "W-5000-N", None, None,
        )


def test_p1_33_a_template_refuses_a_text_reading_that_posts(dana, brazos):
    from apps.work import templates_svc

    row = templates_svc._reading_row({"prompt": "Seal", "kind": "text"}, 1)
    assert (row["kind"], row["unit_of_measure"], row["posts_as_meter_read"]) == ("text", "", False)
    with pytest.raises(errors.ValidationError) as caught:
        templates_svc._reading_row(
            {"prompt": "Seal", "kind": "text", "posts_as_meter_read": True}, 1
        )
    assert caught.value.message_key == "work.template.text_reading_cannot_post"


# ── P1.15 · the customer reaches the job, also through its unit ───────────


def test_p1_15_a_job_on_a_unit_names_the_account_in_force_there(brazos, marcus):
    from apps.customers import services as customers_services
    from apps.work import mobile
    from tests.test_us_cus_003_account_write import _create_payload, _unit_with_plan

    with tenant_ctx(brazos):
        _reference()
        unit = _unit_with_plan(marcus, brazos)
        account = customers_services.create_account(marcus, _create_payload(unit["id"]))
        customers_services.update_account_contact(
            marcus, account["id"], {"full_name": "Sarah Miller", "phone": "(512) 555-0114"}
        )
        from apps.metering import models as metering_models

        unit_row = metering_models.Unit.objects.get(pk=unit["id"])
        raised = w6.create_work_order(
            marcus, None, {"type": "Leak investigation", "service": "water",
                           "premises_id": str(unit_row.premises_id), "unit_id": unit["id"]},
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.account_id is None
        contact = mobile._customer_contact(order)
        assert (contact["name"], contact["phone"]) == ("Sarah Miller", "(512) 555-0114")
        detail = dispatch.order_row(raised["id"])
        assert detail["customer"]["name"] == "Sarah Miller"
        assert detail["shape"] == "open" and detail["signature"] is None
        assert detail["location"]["unit"]["label"]
        assert [step["kind"] for step in detail["timeline"]] == ["raised"]


# ── P0.1 · DEF-WRK-9571 — sample jobs carry a priority ────────────────────


def test_def_wrk_9571_metering_0072_gives_sample_orders_a_priority_and_finished_ones_complete(
    dana, brazos
):
    """Red on the tip: the demo's orders carry NO priority (0 of 40) and 22 of
    23 finished ones read *queued*. `metering/0072` gives every SAMPLE order
    its type's default — else Normal — dated from the raise, and moves every
    finished order to Complete unless a person held or cancelled it. A
    utility's own order with no priority is left exactly as it is."""
    import importlib

    from django.apps import apps as live_apps

    data = importlib.import_module(
        "apps.metering.migrations.0072_cr168_priorities_and_complete_dispatch"
    )
    with tenant_ctx(brazos):
        _reference()
        sample = _order(dana, "1 Sample St")
        theirs = _order(dana, "2 Their St")
        finished = _order(dana, "3 Done St")
        held = _order(dana, "4 Held St")
        work_tables.WorkOrder.objects.filter(pk__in=[sample["id"], theirs["id"]]).update(
            priority=None, due_at=None
        )
        work_tables.WorkOrder.objects.filter(pk=sample["id"]).update(is_sample=True)
        work_tables.WorkOrder.objects.filter(pk__in=[finished["id"], held["id"]]).update(
            state="completed", dispatch_state="queued"
        )
        work_tables.WorkOrder.objects.filter(pk=held["id"]).update(dispatch_state="on_hold")
        seeded, dated, completed = data._apply_tenant(live_apps, brazos.id)
        assert (seeded, dated, completed) == (1, 1, 1)
        row = work_tables.WorkOrder.objects.select_related("priority").get(pk=sample["id"])
        assert row.priority.code == "NORMAL"  # "Leak investigation" names no default
        assert row.due_at == row.created_at + timedelta(hours=72)
        assert work_tables.WorkOrder.objects.get(pk=theirs["id"]).priority_id is None
        assert work_tables.WorkOrder.objects.get(pk=finished["id"]).dispatch_state == "complete"
        assert work_tables.WorkOrder.objects.get(pk=held["id"]).dispatch_state == "on_hold"


def test_def_wrk_9571_the_demo_seeders_raise_at_normal(brazos):
    from apps.metering import sample_data as metering_sample

    with tenant_ctx(brazos):
        _reference()
        normal = work_models.WorkPriority.objects.get(tenant_id=brazos.id, code="NORMAL")
        assert metering_sample._normal_priority_id(brazos.id) == str(normal.id)


# ── P1.23 / image 04 · who closed it, and the mark as a same-origin path ──


def test_p1_23_a_completed_order_names_its_closer_and_never_a_storage_link(
    dana, brazos, stored_audit
):
    import uuid

    with tenant_ctx(brazos):
        _reference()
        tech = _technician(brazos, "d-ortiz@brazos.test", "D. Ortiz")
        raised = _order(dana)
        _assign(dana, raised["id"], technician=tech)
        w6.submit_field_result(_as(tech), raised["id"], field_data={}, outcome="passed")
        detail = dispatch.order_row(raised["id"])
        assert detail["shape"] == "completed"
        assert detail["closed"]["by"] == {"name": "D. Ortiz"}
        assert [s["kind"] for s in detail["timeline"]][-1] == "completed"
        mark = SimpleNamespace(refused=False, image_id=uuid.uuid4(), work_order_id=raised["id"])
        assert evidence._signature_link(mark) == (
            f"/api/{brazos.subdomain}/work-orders/{raised['id']}/signature/image"
        )
        assert evidence._signature_link(SimpleNamespace(refused=True, image_id=None,
                                                        work_order_id=raised["id"])) is None

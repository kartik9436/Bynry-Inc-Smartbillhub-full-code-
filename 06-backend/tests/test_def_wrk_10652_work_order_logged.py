# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-WRK-10652 (PO report 2026-10-29, WO-0085 — *"Work Order Raised
#           Dual-Notification Missing for Customer & Assigned Field
#           Technician"*)
# Rules:    PO 2026-10-29 *"1A 2A 3B 4A, start"* — (1A) *Work order logged* for
#           a job with a customer raised without a date, never beside *booked*;
#           (2A) the technician is told by the field-app push only; (3B)
#           preparation instructions per template, a utility default when
#           blank; (4A) a template switch, never a type name, silences every
#           customer visit message · BR-WRK-008 (copy, never link) · hard rule
#           8 (the premises' address, walked) · rule 6 (idempotent)
# ───────────────────────────────────────────────────────
"""Every case drives the REAL raise (`raise_svc.raise_work_order`), the real
template service and the real queue, and reads the rows back off
`outbound_messages`."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone

from apps.notifications import models, rule_catalog, seed_templates
from apps.notifications import rendering
from apps.work import models as work_models
from apps.work import raise_svc, templates_svc, workforce
from apps.work import services as work_services
from apps.work import selectors as work_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_cr168_srv5_messages import SEEDED_ON, _technician

pytestmark = pytest.mark.django_db

ADDRESS = "1408 Willow Bend Dr"
PREP = "Clear 3 ft around the meter box."


def _setup(dana):
    seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _template(actor, *, name="Meter exchange", details=None):
    header = templates_svc.create_draft(actor, {"name": name, "service": "water"})
    templates_svc.replace_collection(actor, header["id"], "details", details or {})
    templates_svc.publish(actor, header["id"])
    return header["id"]


def _customer_unit(actor, tenant, *, address=ADDRESS):
    from apps.customers import models as customers_models
    from apps.customers import services as customers_services
    from apps.metering import services as metering_services

    from tests.test_us_cus_003_account_write import _create_payload, _plan

    premises = make_premises(actor, address_line=address, services_available=["water"])
    unit = make_unit(actor, premises["id"], label="Unit A")
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "water")
    account = customers_services.create_account(actor, _create_payload(unit["id"]))
    customers_models.Account.objects.filter(pk=account["id"]).update(
        paperless=True, sms_reminders=True
    )
    return premises, unit


def _raise(actor, tenant, *, template_id=None, technician=None, window=None, address=ADDRESS):
    premises, unit = _customer_unit(actor, tenant, address=address)
    payload = {"type": "Meter exchange", "service": "water",
               "premises_id": str(premises["id"]), "unit_id": str(unit["id"])}
    if template_id:
        payload["template_id"] = str(template_id)
    if technician is not None:
        payload["assignee"] = {"technician_id": str(technician.id)}
    if window is not None:
        payload["window_start"], payload["window_end"] = window
    return raise_svc.raise_work_order(actor, payload)


def _window():
    base = (timezone.now() + timedelta(days=2)).replace(minute=0, second=0, microsecond=0)
    return (base.replace(hour=14).isoformat(), base.replace(hour=18).isoformat())


def _rows():
    return list(
        models.OutboundMessage.objects.filter(source_type="appointment").order_by("channel")
    )


# ══════════════════════════════════════════════════════════════════════════
# The catalogue — one new customer event with wording on both channels
# ══════════════════════════════════════════════════════════════════════════


def test_work_order_logged_is_a_live_customer_event_on_email_and_sms():
    event = rule_catalog.event("work_order_logged")
    assert event.audience == rule_catalog.AUDIENCE_CUSTOMER
    assert event.trigger_blocked_by is None
    assert event.source_type == "appointment"
    assert event.timing_key == "on_raise"
    assert event.template_classes == {
        models.CHANNEL_EMAIL: "service_work_order_logged",
        models.CHANNEL_SMS: "sms_work_order_logged",
    }


# ══════════════════════════════════════════════════════════════════════════
# 1A · raised WITHOUT a date ⇒ logged; WITH a date ⇒ booked only
# ══════════════════════════════════════════════════════════════════════════


def test_1a_raise_with_customer_and_no_date_queues_one_logged_email_and_sms(brazos, dana):
    """RED on the tip: an undated raise wrote NOTHING — ``assert [] == [...]``."""
    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana, details={"prep_instructions": PREP})
        tech = _technician(brazos)
        created = _raise(dana, brazos, template_id=tid, technician=tech)
        rows = _rows()
        email = next(r for r in rows if r.channel == "email")
        rendered = rendering.render_for_dispatch(email)
        sms = rendering.render_for_dispatch(next(r for r in rows if r.channel == "sms"))

    assert sorted((r.channel, r.event_key, r.template_code) for r in rows) == [
        ("email", "work_order_logged", "service_work_order_logged"),
        ("sms", "work_order_logged", "sms_work_order_logged"),
    ]
    ctx = email.render_context
    assert ctx["order_no"] == created["order_no"]
    assert ctx["work_type"]
    # Hard rule 8 — the PREMISES' address, walked; never an id (B14 rule 31).
    assert ctx["service_address"] == ADDRESS
    assert ctx["prep_instructions"] == PREP
    # No date was given, so no window is named either.
    assert ctx["appointment_date"] is None and ctx["appointment_window"] is None
    assert str(created["id"]) not in str(ctx)
    assert created["order_no"] in rendered.body and ADDRESS in rendered.body
    assert "confirm a date" in rendered.body and PREP in rendered.body
    assert PREP in sms.body


def test_1a_raise_with_a_date_queues_only_booked_with_prep_and_no_logged(brazos, dana):
    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana, details={"prep_instructions": PREP})
        tech = _technician(brazos)
        _raise(dana, brazos, template_id=tid, technician=tech, window=_window())
        rows = _rows()
        email = next(r for r in rows if r.channel == "email")
        body = rendering.render_for_dispatch(email).body

    assert sorted((r.channel, r.event_key) for r in rows) == [
        ("email", "appointment_window"),
        ("sms", "appointment_window"),
    ]
    assert email.render_context["prep_instructions"] == PREP
    assert PREP in body


def test_1a_a_logged_job_later_dated_is_then_told_booked(brazos, dana):
    """The existing *booked* still follows when the date is decided later."""
    from apps.work import dispatch

    with tenant_ctx(brazos):
        _setup(dana)
        tech = _technician(brazos)
        created = _raise(dana, brazos)
        window = _window()
        dispatch.record_act(dana, created["id"], {"act": "assign", "technician_id": str(tech.id),
                                                  "window_start": window[0], "window_end": window[1]})
        kinds = sorted({r.event_key for r in _rows()})
    assert kinds == ["appointment_window", "work_order_logged"]


def test_1a_a_repeated_call_writes_nothing_twice(brazos, dana):
    from apps.work import visit_notices
    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        _setup(dana)
        created = _raise(dana, brazos)
        before = len(_rows())
        order = metering_seam.work_order_row(created["id"])
        visit_notices.after_raise(order, actor=dana)
        visit_notices.after_raise(order, actor=dana)
        after = len(_rows())
    assert before == 2
    assert after == 2


def test_3b_blank_template_prep_reads_the_utility_default_then_the_edited_one(brazos, dana):
    with tenant_ctx(brazos):
        _setup(dana)
        _raise(dana, brazos, address="1 Default Way")
        seeded = next(r for r in _rows() if r.channel == "email").render_context
        assert workforce.visit_message_settings() == {
            "visit_prep_default": work_models.VISIT_PREP_DEFAULT, "chosen": False}
        workforce.set_visit_message_settings(dana, {"visit_prep_default": "Turn off irrigation."})
        models.OutboundMessage.objects.all().delete()
        _raise(dana, brazos, address="2 Default Way")
        edited = next(r for r in _rows() if r.channel == "email").render_context
        workforce.set_visit_message_settings(dana, {"visit_prep_default": ""})
        models.OutboundMessage.objects.all().delete()
        _raise(dana, brazos, address="3 Default Way")
        none_row = next(r for r in _rows() if r.channel == "email")
        body = rendering.render_for_dispatch(none_row).body
    assert seeded["prep_instructions"] == (
        "Please give our technician clear access to the meter: unlock gates and keep pets inside."
    )
    assert edited["prep_instructions"] == "Turn off irrigation."
    # An empty default leaves the paragraph out — never a blank or a `——`.
    assert none_row.render_context["prep_instructions"] is None
    assert "Before we arrive" not in body and "——" not in body.split("Questions?")[0]


def test_3b_editing_the_template_after_the_raise_changes_nothing_already_raised(brazos, dana):
    """BR-WRK-008 — the job reads its OWN copy."""
    from apps.work import visit_notices
    from apps.work.seams import metering_seam

    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana, details={"prep_instructions": PREP})
        created = _raise(dana, brazos, template_id=tid)
        templates_svc.replace_collection(dana, tid, "details", {"prep_instructions": "Changed."})
        order = metering_seam.work_order_row(created["id"])
        assert visit_notices.prep_instructions(order) == PREP


# ══════════════════════════════════════════════════════════════════════════
# 4A · the template switch silences every customer visit message
# ══════════════════════════════════════════════════════════════════════════


def test_4a_template_switch_off_sends_no_customer_visit_message_dated_or_not(brazos, dana):
    from apps.work import dispatch

    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana, name="Disconnect visit",
                        details={"send_customer_visit_messages": False})
        tech = _technician(brazos)
        undated = _raise(dana, brazos, template_id=tid, address="10 Cut St")
        _raise(dana, brazos, template_id=tid, technician=tech, window=_window(), address="11 Cut St")
        moved = _window()
        answer = dispatch.record_act(dana, undated["id"], {
            "act": "assign", "technician_id": str(tech.id),
            "window_start": moved[0], "window_end": moved[1]})
        rows = _rows()
    assert rows == []
    assert answer["customer_notice"] == "visit_message_template_off"


def test_4a_seeded_disconnect_and_reconnect_templates_are_switched_off(brazos, dana):
    """The sample data plants them OFF; every other sample template stays ON."""
    from apps.metering import sample_data
    from apps.work import connection_models as work_tables

    with tenant_ctx(brazos):
        _setup(dana)
        sample_data._seed_flow_visit_templates(dana)
        flags = {
            t.name: work_models.WorkOrderTemplateDetail.objects.get(template_id=t.id)
            .send_customer_visit_messages
            for t in work_tables.WorkOrderTemplate.objects.filter(
                name__in=("Disconnect visit", "Reconnect visit", "Final read"))
        }
    assert flags == {"Disconnect visit": False, "Reconnect visit": False, "Final read": True}


# ══════════════════════════════════════════════════════════════════════════
# 2A · the technician — the push, and no email
# ══════════════════════════════════════════════════════════════════════════


def test_2a_technician_is_told_by_push_only_never_by_email(brazos, dana, monkeypatch):
    from apps.work import dispatch

    pushed = []
    monkeypatch.setattr(dispatch, "push_after_assign",
                        lambda row, order, act, technician, actor, **kw: pushed.append(
                            (order.order_no, act, technician.id)))
    with tenant_ctx(brazos):
        _setup(dana)
        tech = _technician(brazos, email="t.lee@b.test", name="T. Lee")
        created = _raise(dana, brazos, technician=tech)
        to_tech = models.OutboundMessage.objects.filter(recipient_address="t.lee@b.test").count()
    assert pushed == [(created["order_no"], "assign", tech.id)]
    assert to_tech == 0


# ══════════════════════════════════════════════════════════════════════════
# The editor — save, reload, save keeps both new fields
# ══════════════════════════════════════════════════════════════════════════


def test_editor_save_reload_save_keeps_prep_and_the_switch(brazos, dana):
    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana, details={"prep_instructions": PREP,
                                       "send_customer_visit_messages": False})
        first = work_selectors._collection_rows(tid)["details"]
        # A save that sends back exactly what it read …
        templates_svc.replace_collection(dana, tid, "details", dict(first))
        second = work_selectors._collection_rows(tid)["details"]
        # … and a save written before these fields existed (the seven ticks
        # only) must not wipe them.
        older = {k: v for k, v in first.items()
                 if k not in ("prep_instructions", "send_customer_visit_messages")}
        templates_svc.replace_collection(dana, tid, "details", older)
        third = work_selectors._collection_rows(tid)["details"]
    for answer in (first, second, third):
        assert answer["prep_instructions"] == PREP
        assert answer["send_customer_visit_messages"] is False


def test_editor_refuses_a_switch_that_is_not_a_boolean_and_an_overlong_prep(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        _setup(dana)
        tid = _template(dana)
        with pytest.raises(errors.ValidationError):
            templates_svc.replace_collection(dana, tid, "details",
                                             {"send_customer_visit_messages": "no"})
        with pytest.raises(errors.ValidationError):
            templates_svc.replace_collection(dana, tid, "details",
                                             {"prep_instructions": "x" * 301})


# ══════════════════════════════════════════════════════════════════════════
# The migration that brings an EXISTING utility along (notifications/0032)
# ══════════════════════════════════════════════════════════════════════════


def test_notifications_0032_new_bodies_are_the_seeders_and_old_ones_were_not():
    """The migration freezes the wording; this pins it to the seeder today, so
    a later re-word of the seed cannot leave the migration publishing a body
    no new utility would get."""
    import importlib

    mig = importlib.import_module(
        "apps.notifications.migrations.0032_def_wrk_10652_visit_prep_wording"
    )
    assert mig.NEW_APPOINTMENT == seed_templates.EMAIL_APPOINTMENT_BODY
    assert mig.NEW_MOVED == seed_templates.EMAIL_VISIT_MOVED_BODY
    assert mig.NEW_SMS_BOOKED == seed_templates.SMS_VISIT_BOOKED_BODY
    for old, new in mig.REWORD.values():
        assert "{prep_instructions}" in new and "{prep_instructions}" not in old

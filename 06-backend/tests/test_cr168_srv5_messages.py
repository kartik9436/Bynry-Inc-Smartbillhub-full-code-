# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6, lane SRV-5 — P6.1 (the customer told: booked,
#           moved, on the way, done), P6.2 (the office told: at risk, declined,
#           blocked), P6.4/P6.7 (the tenant's switch, on Notifications — the one
#           home), P6.5 (four consumer kinds), P6.6 (no message without a rule).
# Rules:    Ruling 3 (23 Sep) · BR-NOT-017 · BR-NOT-021 · DEF-NOT-5632 (the
#           do-not-send list holds a row) · OQ-WRK-1495 (`appointment`) ·
#           CLAUDE.md rule 6 · hard rule 8
# ───────────────────────────────────────────────────────
"""Every message driven through the REAL act — assign, schedule, depart,
accept, decline, hold, the sweep — and read back off the queue a dispatcher
and a customer's provider read. Runs on SQLite and on PostgreSQL 16
(`config.settings.pgtest`)."""

from __future__ import annotations

from datetime import datetime, timedelta
from datetime import timezone as dt_timezone

import pytest
from django.utils import timezone

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.notifications import models, rule_catalog, rule_service, seed_templates, suppression
from apps.work import dispatch, mobile
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana · marcus
from tests.test_us_met_helpers import field_close, make_premises, tenant_ctx

pytestmark = pytest.mark.django_db

SEEDED_ON = datetime(2026, 8, 17, 9, 0, tzinfo=dt_timezone.utc)
ADDRESS = "1408 Willow Bend Dr"


def _reference():
    for code in ("work_priorities", "work_order_types", "work_hold_reasons"):
        work_services.seed_reference_list(code, [], "test")


def _technician(tenant, email="r.patel@b.test", name="R. Patel"):
    from apps.identity import models as identity_models

    user = identity_models.User.objects.create(tenant_id=tenant.id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant.id, user=user)


def _customer_job(actor, tenant, *, email_on=True, text_on=True, address=ADDRESS,
                  service="water", template_id=None):
    """A job on a unit whose account belongs to Elena Rivera, who elected
    email and/or SMS (`accounts.paperless` / `.sms_reminders`)."""
    from apps.customers import models as customers_models
    from apps.customers import services as customers_services
    from apps.metering import models as metering_models
    from apps.metering import services as metering_services

    from tests.test_us_cus_003_account_write import _create_payload, _plan

    premises = make_premises(actor, address_line=address, services_available=[service])
    from tests.test_us_met_helpers import make_unit

    unit = make_unit(actor, premises["id"], label="Unit A")
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], service)
    account = customers_services.create_account(actor, _create_payload(unit["id"]))
    customers_models.Account.objects.filter(pk=account["id"]).update(
        paperless=email_on, sms_reminders=text_on
    )
    unit_row = metering_models.Unit.objects.get(pk=unit["id"])
    raised = w6.create_work_order(
        actor, None, {"type": "Meter exchange", "service": service,
                      "premises_id": str(unit_row.premises_id), "unit_id": unit["id"],
                      **({"template_id": str(template_id)} if template_id else {})},
    )
    return work_tables.WorkOrder.objects.get(pk=raised["id"])


def _window(day_offset=1, start_h=8, end_h=12):
    base = (timezone.now() + timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
    return (base.replace(hour=start_h).isoformat(), base.replace(hour=end_h).isoformat())


def _assign(actor, order, tech, window):
    return dispatch.record_act(
        actor, order.id,
        {"act": "assign", "technician_id": str(tech.id),
         "window_start": window[0], "window_end": window[1]},
    )


def _visit_rows():
    return list(models.OutboundMessage.objects.filter(source_type="appointment").order_by("created_at", "channel"))


def _office_rows():
    return list(
        models.OutboundMessage.objects.filter(
            source_type="field_work", render_context__event_code__startswith="office_"
        ).order_by("created_at")
    )


def _setup(brazos, dana):
    seed_templates.seed_notice_templates(dana, on_date=SEEDED_ON.date())
    _reference()


# ══════════════════════════════════════════════════════════════════════════
# P6.5 · the catalogue — four customer kinds and three office kinds, each live
# ══════════════════════════════════════════════════════════════════════════


def test_p6_5_four_customer_kinds_and_three_office_kinds_are_live_catalogue_rows():
    customer = {k: rule_catalog.event(k) for k in (
        "appointment_window", "visit_moved", "technician_on_the_way", "completion_receipt")}
    office = {k: rule_catalog.event(k) for k in (
        "work_job_at_risk", "work_job_declined", "work_job_blocked")}
    for event in customer.values():
        assert event.audience == rule_catalog.AUDIENCE_CUSTOMER
        assert event.trigger_blocked_by is None, event.key
        assert event.source_type == "appointment"
        # Every channel offered has wording — a toggle over nothing is a promise.
        assert set(event.template_classes) == set(event.channels), event.key
    for event in office.values():
        assert event.audience == rule_catalog.AUDIENCE_STAFF
        assert event.channels == (models.CHANNEL_IN_APP,)
        assert event.template_classes == {models.CHANNEL_IN_APP: "staff_field_work"}
    assert customer["visit_moved"].template_classes == {
        models.CHANNEL_EMAIL: "service_visit_moved", models.CHANNEL_SMS: "sms_visit_moved"}
    assert customer["technician_on_the_way"].template_classes == {
        models.CHANNEL_SMS: "sms_technician_on_the_way"}


def test_the_four_new_bodies_are_seeded_and_reach_an_existing_tenant_on_the_next_seed(
    growth_plan, identity_seam, monkeypatch
):
    """A utility provisioned before this build gets them the way FIELD-2's
    `staff_field_work` reached one: the next `seed_notice_templates` run
    (`manage.py seed_demo --tenant <subdomain>`) inserts what is missing.
    "Provisioned before" is modelled by provisioning it with the library as it
    stood (the four absent) — published versions are append-only on PostgreSQL
    (`BR-BIL-027`), so taking them back out afterwards is not a thing that can
    happen to a real utility and is not what this case does."""
    from apps.notifications import template_models as tm
    from tests.test_us_met_helpers import brazosbend_payload, provisioned_tenant, staff_actor

    new = {"service_visit_moved", "sms_visit_booked", "sms_visit_moved", "sms_technician_on_the_way"}
    before = tuple(e for e in seed_templates.SEEDABLE if e.code not in new)
    with monkeypatch.context() as patch:
        patch.setattr(seed_templates, "SEEDABLE", before)
        tenant, _result = provisioned_tenant(brazosbend_payload())
    admin = staff_actor(tenant, "system_admin", "dana@brazosbendutilities.test")
    with tenant_ctx(tenant):
        assert not tm.NotificationTemplate.objects.filter(code__in=new).exists()
        again = seed_templates.seed_notice_templates(admin, on_date=SEEDED_ON.date())
        created = {row["code"] for row in again["seeded"] if row["created"]}
        live = set(tm.NotificationTemplate.objects.filter(code__in=new).values_list("code", flat=True))
    assert created == new
    assert live == new


# ══════════════════════════════════════════════════════════════════════════
# P6.1 · the customer — booked, moved, on the way, done
# ══════════════════════════════════════════════════════════════════════════


def test_p6_1_booked_goes_once_on_each_channel_the_customer_elected(brazos, dana, marcus):
    """RED on the tip: nothing queued anything on an assignment —
    ``assert [] == [...]``."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        tech = _technician(brazos)
        window = _window()
        answer = _assign(dana, order, tech, window)
        rows = _visit_rows()

    assert answer["customer_notice"] == "visit_message_queued"
    assert sorted((r.channel, r.event_key, r.template_code) for r in rows) == [
        ("email", "appointment_window", "service_appointment"),
        ("sms", "appointment_window", "sms_visit_booked"),
    ]
    email = next(r for r in rows if r.channel == "email")
    assert email.recipient_address == "elena.rivera@example.com"
    ctx = email.render_context
    # Hard rule 8: the PREMISES' address, walked; B14 rule 31: no id travels.
    assert ctx["service_address"] == ADDRESS
    assert ctx["first_name"] == "Elena"
    assert ctx["appointment_window"] == "08:00–12:00" or "–" in ctx["appointment_window"]
    assert ctx["technician_name"] == "R. Patel"
    assert str(order.id) not in str(ctx)


def test_p6_1_a_customer_with_no_email_and_no_text_consent_gets_no_message_and_the_act_says_so(
    brazos, dana, marcus
):
    """⚠ AMENDED 2026-10-29 (`DEF-WRK-10663`, PO B1 A): this read *"elected
    nothing"* — paperless off was enough to tell nobody. Email now follows the
    address on file, as a bill does, so *nothing to tell them by* means NO email
    on file and no text consent."""
    from apps.customers import models as customers_models

    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=False)
        customers_models.Contact.objects.filter(tenant_id=brazos.id).update(email=None)
        answer = _assign(dana, order, _technician(brazos), _window())
        rows = _visit_rows()
    assert rows == []
    assert answer["customer_notice"] == "visit_message_no_channel_elected"


def test_def_wrk_10663_an_email_on_file_without_paperless_gets_the_booked_email(brazos, dana, marcus):
    """PO 2026-10-29 B1 A — *"Rosa has an email but never ticked paperless →
    she now gets the booked email"*. SMS still needs consent, so no text.
    RED on the tip: ``assert [] == [('email', 'appointment_window', ...)]``."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, email_on=False, text_on=False)
        answer = _assign(dana, order, _technician(brazos), _window())
        rows = _visit_rows()
    assert [(r.channel, r.event_key, r.template_code) for r in rows] == [
        ("email", "appointment_window", "service_appointment")
    ]
    assert rows[0].recipient_address == "elena.rivera@example.com"
    assert answer["customer_notice"] == "visit_message_queued"


def test_p6_1_moved_once_per_new_window_and_never_for_the_same_window(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, text_on=False)
        tech = _technician(brazos)
        _assign(dana, order, tech, _window())
        moved_to = _window(day_offset=2, start_h=13, end_h=17)
        first = dispatch.reschedule(dana, order.id, {"window_start": moved_to[0], "window_end": moved_to[1]})
        same = dispatch.reschedule(dana, order.id, {"window_start": moved_to[0], "window_end": moved_to[1]})
        rows = _visit_rows()

    assert [(r.event_key, r.template_code) for r in rows] == [
        ("appointment_window", "service_appointment"),
        ("visit_moved", "service_visit_moved"),
    ]
    assert first["customer_notice"] == "visit_message_queued"
    assert same["customer_notice"] is None


def test_p6_1_on_the_way_is_a_text_when_the_technician_departs(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        tech = _technician(brazos)
        _assign(dana, order, tech, _window(day_offset=0, start_h=0, end_h=23))
        from types import SimpleNamespace

        phone = SimpleNamespace(id=tech.user_id, role="field_technician")
        mobile.accept_job(phone, order.id)
        mobile.field_act(phone, order.id, {"act": "depart"})
        rows = [r for r in _visit_rows() if r.event_key == "technician_on_the_way"]

    assert [(r.channel, r.template_code) for r in rows] == [("sms", "sms_technician_on_the_way")]
    # ⚠ AMENDED 2026-10-05 (`DEF-NOT-9668`, lane FIX-7). This asserted the
    # text was WRITTEN UNADDRESSED as `recipient_not_resolvable` ("the platform
    # holds no MOBILE number yet"). Elena chose texts on the phone her account
    # carries, so the text is addressed to it — the number the work order prints.
    assert rows[0].recipient_address == "+1 (281) 555-0100"
    assert rows[0].unavailable_reason is None
    assert rows[0].render_context["technician_name"] == "R. Patel"


def test_p6_1_done_goes_when_the_office_accepts_a_passed_job_and_never_at_the_field_close(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, text_on=False)
        _assign(dana, order, _technician(brazos), _window(day_offset=0, start_h=0, end_h=23))
        field_close(dana, order.id, field_data={"ok": True}, outcome="passed")
        at_close = [r.event_key for r in _visit_rows()]
        w6.accept_field_result(dana, order.id)
        after = [r for r in _visit_rows() if r.event_key == "completion_receipt"]

    assert "completion_receipt" not in at_close
    assert [(r.channel, r.template_code) for r in after] == [("email", "service_work_completed")]
    assert after[0].render_context["completed_date"]


def test_p6_1_a_failed_job_accepted_is_not_done_to_the_customer(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos, text_on=False)
        _assign(dana, order, _technician(brazos), _window(day_offset=0, start_h=0, end_h=23))
        field_close(dana, order.id, field_data={"ok": False}, outcome="failed")
        try:
            w6.accept_field_result(dana, order.id)
        except Exception:  # noqa: BLE001 — a failed job's chain may refuse; the point is no message
            pass
        rows = [r for r in _visit_rows() if r.event_key == "completion_receipt"]
    assert rows == []


def test_p6_1_an_address_on_the_do_not_send_list_is_written_and_held(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        suppression.suppress(channel="email", address="elena.rivera@example.com",
                             reason="manual", at=timezone.now(), actor=dana)
        order = _customer_job(marcus, brazos, text_on=False)
        _assign(dana, order, _technician(brazos), _window())
        rows = _visit_rows()
    assert [(r.channel, r.held) for r in rows] == [("email", True)]


# ══════════════════════════════════════════════════════════════════════════
# P6.6 · no message without a rule — proved in both directions
# ══════════════════════════════════════════════════════════════════════════


def test_p6_6_the_utility_switched_booked_off_and_nothing_is_written(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        rule_service.update_rule(event_key="appointment_window", actor=dana, enabled=False)
        order = _customer_job(marcus, brazos)
        answer = _assign(dana, order, _technician(brazos), _window())
        rows = _visit_rows()
    assert rows == []
    assert answer["customer_notice"] == "visit_message_switched_off"


def test_p6_6_a_job_with_no_customer_tells_nobody(brazos, dana):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        premises = make_premises(dana, address_line="Elm St & 3rd", services_available=["water"])
        raised = w6.create_work_order(dana, None, {"type": "Main repair", "service": "water",
                                                   "premises_id": premises["id"]})
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        answer = _assign(dana, order, _technician(brazos), _window())
        rows = _visit_rows()
    assert rows == []
    assert answer["customer_notice"] == "visit_message_no_customer"


def test_p6_6_an_office_kind_switched_off_writes_nothing(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        rule_service.update_rule(event_key="work_job_declined", actor=dana, enabled=False)
        order = _customer_job(marcus, brazos)
        tech = _technician(brazos)
        _assign(dana, order, tech, _window())
        from types import SimpleNamespace

        mobile.decline_job(SimpleNamespace(id=tech.user_id, role="field_technician"), order.id,
                           {"reason": "Van in the shop"})
        rows = _office_rows()
    assert rows == []


# ══════════════════════════════════════════════════════════════════════════
# P6.2 · the office — declined, blocked, at risk
# ══════════════════════════════════════════════════════════════════════════


def test_p6_2_a_decline_tells_whoever_sent_it_and_every_admin_once(brazos, dana, marcus):
    """RED on the tip: a decline told nobody — ``assert [] == [...]``."""
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        tech = _technician(brazos)
        _assign(dana, order, tech, _window())
        from types import SimpleNamespace

        phone = SimpleNamespace(id=tech.user_id, role="field_technician")
        mobile.decline_job(phone, order.id, {"reason": "Van in the shop"})
        mobile.decline_job(phone, order.id, {"reason": "Van in the shop"})
        rows = _office_rows()
        order.refresh_from_db()

    assert [r.render_context["event_code"] for r in rows] == ["office_declined"]
    assert rows[0].event_key == "work_job_declined"
    recipients = {e["user_id"]: e["reason"] for e in rows[0].recipient_snapshot["recipients"]}
    assert str(dana.user.id) in recipients
    assert "system_admin" in recipients.values()
    assert rows[0].render_context["order_no"] == order.order_no


def test_p6_2_a_hold_tells_the_office_the_job_is_blocked_once_per_hold(brazos, dana, marcus):
    with tenant_ctx(brazos):
        _setup(brazos, dana)
        work_models.WorkHoldReason.objects.get_or_create(
            tenant_id=brazos.id, code="parts", defaults={"name": "Waiting on parts", "rank": 1, "active": True})
        order = _customer_job(marcus, brazos)
        _assign(dana, order, _technician(brazos), _window())
        dispatch.hold(dana, order.id, {"reason_code": "parts"})
        dispatch.hold(dana, order.id, {"reason_code": "parts", "note": "re-held"})
        rows = _office_rows()
    assert [(r.event_key, r.render_context["event_code"]) for r in rows] == [
        ("work_job_blocked", "office_blocked")]


def test_p6_2_the_sweep_tells_the_office_a_job_is_at_risk_once(brazos, dana, marcus):
    from apps.work import escalations, promise

    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        _assign(dana, order, _technician(brazos), _window())
        work_models.WorkSettings.objects.update_or_create(
            tenant_id=brazos.id, defaults={"at_risk_window_hours": 4})
        window = promise.at_risk_window_hours()
        assert window == 4, "the at-risk window is unset — this case would prove nothing"
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(due_at=timezone.now() + timedelta(hours=1))
        first = escalations.escalate()
        second = escalations.escalate()
        rows = _office_rows()
    assert first["at_risk"]["at_risk"] == 1 and second["at_risk"]["at_risk"] == 0
    assert [r.event_key for r in rows] == ["work_job_at_risk"]


def test_p6_2_no_at_risk_window_set_means_no_at_risk_notice(brazos, dana, marcus):
    """Without a warning window there is no *before*: a passed promise is the
    rule's *Past due* escalation, never a flood of at-risk notices on the
    first sweep after this build lands."""
    from apps.work import escalations

    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        _assign(dana, order, _technician(brazos), _window())
        work_tables.WorkOrder.objects.filter(pk=order.pk).update(due_at=timezone.now() + timedelta(hours=1))
        out = escalations.escalate()
        rows = _office_rows()
    assert out["at_risk"] == {"at_risk": 0}
    assert rows == []


def test_p6_2_the_bell_reads_each_office_kind_in_the_clerks_words(brazos, dana, marcus):
    from apps.notifications import dispatcher, in_app

    with tenant_ctx(brazos):
        _setup(brazos, dana)
        order = _customer_job(marcus, brazos)
        tech = _technician(brazos)
        _assign(dana, order, tech, _window())
        from types import SimpleNamespace

        mobile.decline_job(SimpleNamespace(id=tech.user_id, role="field_technician"), order.id,
                           {"reason": "Van in the shop"})
        dispatcher.dispatch_cycle(now=datetime.now(dt_timezone.utc),
                                  channels=(models.CHANNEL_IN_APP,), actor=dana)
        bell = [i for i in in_app.inbox(actor=dana) if (i.message_key or "").startswith("notifications.workOffice")]
    assert [(i.message_key, i.params["order"]) for i in bell] == [
        ("notifications.workOffice.declined", order.order_no)]

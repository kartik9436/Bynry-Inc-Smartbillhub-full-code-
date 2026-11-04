# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 — temporary stop (PO rulings B1–B4, 2026-10-14).
# Rules:    BR-CUS-1120 · BR-CUS-1121 · BR-CWP-026 · BR-CUS-055 · hard rules 1, 7
# ───────────────────────────────────────────────────────
"""A portal *stop my service* ask becomes a typed, scheduled hold.

The worked figures are the PO's: `SR-26-0017` asked 13 Oct → 16 Oct, **3 days**,
and is refused under the default minimum of **10**; 10 days is accepted; more
than **12 months** is refused. Dates here are relative to the utility's today so
the suite means the same thing on any day it runs.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.test import Client

from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as srs
from apps.customers import temporary_stop
from apps.customers import temporary_stop_api
from apps.customers.temporary_stop_models import TemporaryStop
from apps.tenancy import services as tenancy_services
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import (
    MARIA_EMAIL,
    MARIA_PASSWORD,
    elm_street_account,
    enrol_maria,
    switch_on,
)
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db


def _today(tenant):
    with tenant_context(tenant.id):
        return temporary_stop.today()


def _signed_in(tenant) -> Client:
    client = Client()
    signed = client.post(
        f"/api/{tenant.subdomain}/portal/auth/sign-in",
        data={"email": MARIA_EMAIL, "password": MARIA_PASSWORD},
        content_type="application/json",
    )
    assert signed.status_code == 200, signed.content
    return client


def _ask(tenant, client, account, *, stop_from, restart_on, reason="away for the winter"):
    sent = client.post(
        f"/api/{tenant.subdomain}/portal/accounts/{account.pk}/stop-or-restart/ask",
        data={
            "stop_from": stop_from.isoformat(),
            "start_again": restart_on.isoformat() if restart_on else None,
            "reason": reason,
            "name": "Maria Alvarez",
            "phone": "512-555-0101",
            "email": MARIA_EMAIL,
        },
        content_type="application/json",
    )
    assert sent.status_code == 200, sent.content
    with tenant_context(tenant.id):
        return customers_models.ServiceRequest.objects.get(request_no=sent.json()["reference"])


def _setup(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    enrol_maria(pine_hill, sarah)
    account = elm_street_account(pine_hill, sarah)
    return account, _signed_in(pine_hill)


def _status(tenant, account) -> str:
    with tenant_context(tenant.id):
        return customers_models.Account.objects.select_related("status").get(pk=account.pk).status.code


def _audit_actions(rows, entity_id) -> list[str]:
    """What the BE-03 sink captured for one entity (the `audit_rows` fixture)."""
    return [row.get("action") for row in rows if str(row.get("entity_id")) == str(entity_id)]


# ── T1 · T2 — the ask is stored and typed ───────────────────────────────────
def test_the_portal_ask_is_stored_with_its_account_and_dates_and_typed(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=5),
                   restart_on=today + timedelta(days=20))
    with tenant_context(pine_hill.id):
        stop = TemporaryStop.objects.get(request_id=request.id)
        assert stop.account_id == account.pk
        assert stop.stop_from == today + timedelta(days=5)
        assert stop.restart_on == today + timedelta(days=20)
        assert stop.reason == "away for the winter"
        assert stop.status == "requested"
        # The clerk's sentence is kept.
        assert "The account stays open" in request.what_they_said
        # Typed from the moment it arrives — the detail header and the list row.
        detail = reads.detail(request.id)
        assert detail["header"]["classification"] == "temporary_stop"
        assert detail["temporary_stop"]["kind"] == "temporary_stop"
        assert detail["temporary_stop"]["stop"]["account_no"] == account.account_no
        assert detail["temporary_stop"]["problems"] == []
        row = reads.list_row(request, kinds=temporary_stop.kinds_for([request.id]))
        assert row["type"] == "temporary_stop"
        assert row["type_absence"] is None
    # Nothing on the account moved (BR-CWP-026).
    assert _status(pine_hill, account) == "active"


def test_new_connection_and_move_in_are_refused_for_a_temporary_stop(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=2),
                   restart_on=today + timedelta(days=30))
    with tenant_context(pine_hill.id):
        for outcome in ("new_connection", "move_in"):
            with pytest.raises(errors.BizError) as refused:
                srs.approve_and_raise(sarah, request.id, outcome=outcome)
            assert refused.value.message_key == temporary_stop.KEY_USE_OWN_APPROVAL
        assert customers_models.ServiceRequest.objects.get(pk=request.id).outcome is None


# ── T3 · B3 — the limits ────────────────────────────────────────────────────
def test_a_three_day_stop_is_refused_by_name_and_nothing_is_written(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=1),
                   restart_on=today + timedelta(days=4))
    with tenant_context(pine_hill.id):
        assert [p["code"] for p in reads.detail(request.id)["temporary_stop"]["problems"]] == ["too_short"]
        with pytest.raises(errors.BizError) as refused:
            temporary_stop.approve_request(sarah, request.id)
        assert refused.value.message_key == temporary_stop.KEY_TOO_SHORT
        assert refused.value.params["min_days"] == 10
        assert refused.value.params["days"] == 3
        assert TemporaryStop.objects.get(request_id=request.id).status == "requested"
        assert customers_models.ServiceRequest.objects.get(pk=request.id).state == "submitted"


def test_ten_days_is_accepted_and_more_than_twelve_months_is_refused(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    start = today + timedelta(days=3)
    request = _ask(pine_hill, client, account, stop_from=start, restart_on=start + timedelta(days=400))
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.BizError) as refused:
            temporary_stop.approve_request(sarah, request.id)
        assert refused.value.message_key == temporary_stop.KEY_TOO_LONG
        assert refused.value.params["max_months"] == 12
        # The clerk agrees ten days with the customer and approves THOSE dates.
        answer = temporary_stop.approve_request(
            sarah, request.id, restart_on=(start + timedelta(days=10)).isoformat()
        )
        assert answer["stop"]["status"] == "scheduled"
        assert answer["stop"]["days"] == 10
        approved = customers_models.ServiceRequest.objects.get(pk=request.id)
        assert approved.state == "approved"
        assert approved.outcome == "temporary_stop"
    # Not started yet — the stop date is in three days.
    assert _status(pine_hill, account) == "active"


def test_the_minimum_is_a_setting(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=1),
                   restart_on=today + timedelta(days=4))
    with tenant_context(pine_hill.id):
        assert temporary_stop.limits() == {"min_days": 10, "max_months": 12}
        tenancy_services.save_settings_family(sarah, "billing-defaults", {"temporary_stop_min_days": 3})
        assert temporary_stop.limits()["min_days"] == 3
        assert temporary_stop.approve_request(sarah, request.id)["stop"]["days"] == 3


# ── T4 — the clock ──────────────────────────────────────────────────────────
def test_the_hold_starts_and_ends_on_its_dates_idempotently_and_audited(pine_hill, sarah, audit_rows):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    start, back = today + timedelta(days=2), today + timedelta(days=14)
    request = _ask(pine_hill, client, account, stop_from=start, restart_on=back)
    with tenant_context(pine_hill.id):
        agreements = customers_models.ServiceAgreement.objects.filter(
            tenant_id=pine_hill.id, account_id=account.pk, ended_on__isnull=True
        ).count()
        temporary_stop.approve_request(sarah, request.id)
        stop = TemporaryStop.objects.get(request_id=request.id)
        assert temporary_stop.apply_due(as_of=start - timedelta(days=1))["started"] == []
        assert temporary_stop.apply_due(as_of=start)["started"] == [str(stop.id)]
    assert _status(pine_hill, account) == "vacation_hold"
    with tenant_context(pine_hill.id):
        # A second firing the same day writes nothing.
        again = temporary_stop.apply_due(as_of=start)
        assert again["started"] == [] and again["ended"] == []
        assert temporary_stop.apply_due(as_of=back)["ended"] == [str(stop.id)]
        stop.refresh_from_db()
        assert stop.status == "ended" and stop.ended_early is False
        # The account stayed open and no service agreement was touched.
        account_row = customers_models.Account.objects.get(pk=account.pk)
        assert account_row.closed_at is None
        assert customers_models.ServiceAgreement.objects.filter(
            tenant_id=pine_hill.id, account_id=account.pk, ended_on__isnull=True
        ).count() == agreements
    assert _status(pine_hill, account) == "active"
    actions = _audit_actions(audit_rows, account.pk)
    assert actions.count("account.temporary_stop_started") == 1
    assert actions.count("account.temporary_stop_ended") == 1
    stop_actions = _audit_actions(audit_rows, stop.id)
    for action in ("temporary_stop.requested", "temporary_stop.approved",
                   "temporary_stop.started", "temporary_stop.ended"):
        assert action in stop_actions


def test_the_beat_entry_is_installed_on_the_real_celery_app():
    from config.celery import app

    from apps.customers import temporary_stop_schedule

    assert temporary_stop_schedule.BEAT_ENTRY in (app.conf.beat_schedule or {})


# ── B4 — the customer ends it early ─────────────────────────────────────────
def test_restart_my_service_now_is_asked_approved_and_billing_is_normal_from_today(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    # A hold that started today and is due back in a month.
    request = _ask(pine_hill, client, account, stop_from=today, restart_on=today + timedelta(days=30))
    with tenant_context(pine_hill.id):
        temporary_stop.approve_request(sarah, request.id)
    assert _status(pine_hill, account) == "vacation_hold"
    shown = client.get(f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/temporary-stop").json()
    assert shown["current"]["status"] == "on_hold"
    assert shown["can_restart_now"] is True
    assert "id" not in shown["current"]
    sent = client.post(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/temporary-stop/restart",
        data={"name": "Maria Alvarez", "email": MARIA_EMAIL},
        content_type="application/json",
    )
    assert sent.status_code == 200, sent.content
    # A second ask while the first waits is refused by name.
    twice = client.post(
        f"/api/{pine_hill.subdomain}/portal/accounts/{account.pk}/temporary-stop/restart",
        data={}, content_type="application/json",
    )
    assert twice.status_code in (409, 422), twice.content
    # Still on hold until a clerk approves (BR-CWP-026).
    assert _status(pine_hill, account) == "vacation_hold"
    with tenant_context(pine_hill.id):
        restart = customers_models.ServiceRequest.objects.get(request_no=sent.json()["reference"])
        assert reads.detail(restart.id)["header"]["classification"] == "restart_now"
        answer = temporary_stop.approve_request(sarah, restart.id)
        assert answer["kind"] == "restart_now"
    # Started today and ended today: no day was spent on hold, so it is
    # cancelled rather than ended, and the account is active again.
    assert _status(pine_hill, account) == "active"


def test_an_early_end_after_days_on_hold_ends_it_today(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    with tenant_context(pine_hill.id):
        # A counter stop that began 12 days ago (written as history).
        answer = temporary_stop.start_from_account(
            sarah, account.pk, stop_from=today, restart_on=today + timedelta(days=20)
        )
        stop = TemporaryStop.objects.get(pk=answer["stop"]["id"])
        TemporaryStop.objects.filter(pk=stop.pk).update(stop_from=today - timedelta(days=12))
        ended = temporary_stop.end_now(sarah, stop.pk)["stop"]
        assert ended["status"] == "ended"
        assert ended["restart_on"] == today.isoformat()
        assert ended["ended_early"] is True
    assert _status(pine_hill, account) == "active"


def test_ending_a_hold_whose_history_period_opens_later_does_not_fail(pine_hill, sarah):
    """Found by the walk (2026-10-14): the clock ran for 14 Oct while the
    utility's own day was still 13 Oct, so the account-history period opened on
    the 14th and the restart approved on the 13th was refused as a backdate —
    a 500 and nothing saved. The period is now updated in place."""
    account, _client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    with tenant_context(pine_hill.id):
        answer = temporary_stop.start_from_account(
            sarah, account.pk, stop_from=today + timedelta(days=1), restart_on=today + timedelta(days=20)
        )
        temporary_stop.apply_due(as_of=today + timedelta(days=1))
    assert _status(pine_hill, account) == "vacation_hold"
    with tenant_context(pine_hill.id):
        ended = temporary_stop.end_now(sarah, answer["stop"]["id"])["stop"]
        assert ended["status"] == "cancelled"
    assert _status(pine_hill, account) == "active"


# ── T7 — the account page's doors ───────────────────────────────────────────
def test_staff_start_change_and_end_through_the_api(pine_hill, sarah):
    account, _client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    start = today + timedelta(days=7)
    made = api_call(
        temporary_stop_api.account_stop, "post", user=sarah.user, role="system_admin",
        tenant=pine_hill, account_id=account.pk,
        data={"stop_from": start.isoformat(), "restart_on": (start + timedelta(days=3)).isoformat()},
    )
    assert made.status_code == 422, made.data  # 3 days — refused by name
    made = api_call(
        temporary_stop_api.account_stop, "post", user=sarah.user, role="system_admin",
        tenant=pine_hill, account_id=account.pk,
        data={"stop_from": start.isoformat(), "restart_on": (start + timedelta(days=14)).isoformat()},
    )
    assert made.status_code == 201, made.data
    stop_id = made.data["current"]["id"]
    assert made.data["current"]["channel"] == "staff"
    moved = api_call(
        temporary_stop_api.stop_item, "patch", user=sarah.user, role="system_admin",
        tenant=pine_hill, stop_id=stop_id,
        data={"restart_on": (start + timedelta(days=21)).isoformat()},
    )
    assert moved.status_code == 200, moved.data
    assert moved.data["stop"]["days"] == 21
    ended = api_call(
        temporary_stop_api.stop_end, "post", user=sarah.user, role="system_admin",
        tenant=pine_hill, stop_id=stop_id, data={},
    )
    assert ended.status_code == 200
    assert ended.data["stop"]["status"] == "cancelled"  # it never started
    shown = api_call(
        temporary_stop_api.account_stop, "get", user=sarah.user, role="system_admin",
        tenant=pine_hill, account_id=account.pk,
    )
    assert shown.data["current"] is None
    assert shown.data["limits"] == {"min_days": 10, "max_months": 12}


def test_a_second_hold_on_the_same_account_is_refused(pine_hill, sarah):
    account, _client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    with tenant_context(pine_hill.id):
        temporary_stop.start_from_account(
            sarah, account.pk, stop_from=today + timedelta(days=5), restart_on=today + timedelta(days=40)
        )
        with pytest.raises(errors.BizError) as refused:
            temporary_stop.start_from_account(
                sarah, account.pk, stop_from=today + timedelta(days=60), restart_on=today + timedelta(days=90)
            )
        assert refused.value.message_key == temporary_stop.KEY_ALREADY_ON_HOLD


# ── B2 — the field visit ────────────────────────────────────────────────────
def test_field_visit_needed_raises_a_shut_off_and_a_turn_on_or_says_why_not(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    start, back = today + timedelta(days=4), today + timedelta(days=24)
    request = _ask(pine_hill, client, account, stop_from=start, restart_on=back)
    with tenant_context(pine_hill.id):
        answer = temporary_stop.approve_request(sarah, request.id, field_visit_needed=True)
        stop = TemporaryStop.objects.get(request_id=request.id)
        assert stop.field_visit_needed is True
        if answer["warnings"]:
            # BR-WRK-055 — the hold stands and the screen is told why.
            assert answer["warnings"][0]["code"] == "work_orders_not_raised"
            pytest.fail(f"no work order was raised: {answer['warnings']}")
        from apps.work.connection_models import WorkOrder

        shutoff = WorkOrder.objects.get(tenant_id=pine_hill.id, order_no=stop.shutoff_order_no)
        turnon = WorkOrder.objects.get(tenant_id=pine_hill.id, order_no=stop.turnon_order_no)
        assert shutoff.source == "disconnect" and turnon.source == "reconnect"
        assert shutoff.due_at.date() == start
        assert turnon.due_at.date() == back


# ── isolation ───────────────────────────────────────────────────────────────
def test_another_utility_cannot_see_or_approve_this_hold(pine_hill, sarah, oak_ridge, elena):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=3),
                   restart_on=today + timedelta(days=30))
    with tenant_context(oak_ridge.id):
        with pytest.raises(errors.NotFoundError):
            temporary_stop.approve_request(elena, request.id)
        assert TemporaryStop.objects.filter(tenant_id=oak_ridge.id).count() == 0
        with pytest.raises(errors.NotFoundError):
            temporary_stop.start_from_account(
                elena, account.pk, stop_from=today + timedelta(days=3),
                restart_on=today + timedelta(days=30),
            )
    with tenant_context(pine_hill.id):
        assert TemporaryStop.objects.get(request_id=request.id).status == "requested"


def test_a_refused_ask_can_never_be_scheduled(pine_hill, sarah):
    account, client = _setup(pine_hill, sarah)
    today = _today(pine_hill)
    request = _ask(pine_hill, client, account, stop_from=today + timedelta(days=1),
                   restart_on=today + timedelta(days=4))
    with tenant_context(pine_hill.id):
        srs.refuse_request(sarah, request.id, reason="Shorter than ten days", reason_code="other")
        assert TemporaryStop.objects.get(request_id=request.id).status == "refused"
        assert temporary_stop.apply_due(as_of=today + timedelta(days=2))["started"] == []

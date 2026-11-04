"""`DEF-CWP-10539` — a portal request gets the acknowledgement when its email is valid.

PO ruling of 2026-10-22 (decision log *"Bill email sends a link instead of the
PDF; service-request target date in working days excluding holidays; portal
requests get the acknowledgement when the email is valid"*, ruling 3), verbatim:
*"yes if we have valid email"*. Until then `create_from_portal` recorded
`ACK_NO_ADDRESS` on every portal request (`BR-CWP-028`) and queued nothing.

Each case reads the queue itself, and the valid-email case RENDERS the row
through the dispatcher's own `render_for_dispatch`, so a row queued with the
service type or the target date missing shows as `ABSENT_MARK` and fails.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (hard-won law 7, habit 2):
  * a second, portal-only composer that queues a row with different facts — so
    the template code and the rendered sentences are the staff ones exactly;
  * a check that refuses every portal email (so nothing is ever queued) — the
    valid case asserts exactly ONE row, not "at most one";
  * a malformed address that Django accepts — the cases use addresses Django's
    `validate_email` refuses, asserted inline.

Runs on SQLite and on PostgreSQL (`--ds=config.settings.pgtest`).
"""

from __future__ import annotations

from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.customers import service_request_service as sr
from apps.notifications import rendering, seed_templates, service_request_events
from apps.notifications import models as notification_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

ACK = service_request_events.TEMPLATE_ACKNOWLEDGEMENT

PORTAL = {
    "applicant_kind": "person",
    "applicant_name": "Kyle Mark",
    "applicant_phone": "555-0100",
    "address_as_given": "1408 Elm St",
    "address_city_as_given": "Austin",
    "address_postal_code_as_given": "78704",
}


def _seeded(actor):
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    tenant = Tenant.objects.get(pk=core_tenancy.current_tenant_id())
    tenant.support_phone = "+1 (281) 555-0164"
    tenant.save(update_fields=["support_phone"])
    seed_templates.seed_notice_templates(actor, on_date=date(2026, 10, 22))


def _rows(request):
    return notification_models.OutboundMessage.objects.filter(
        source_type=service_request_events.SOURCE_SERVICE_REQUEST,
        source_id=str(request.id),
    )


def _portal(**overrides):
    return sr.create_from_portal({**PORTAL, **overrides}, service_codes=["water"])


def _working(day, count):
    from apps.customers import cut_date
    from apps.customers import seams as customer_seams

    return cut_date.business_days_after(day, count, customer_seams.tenant_holidays())


def test_a_portal_request_with_a_valid_email_queues_one_acknowledgement(brazos, dana):
    from django.utils import timezone

    from apps.tenancy import selectors as tenancy_selectors

    with tenant_ctx(brazos):
        _seeded(dana)
        request = _portal(applicant_email="kyle.mark@example.test")
        rows = list(_rows(request))
        assert len(rows) == 1, rows
        row = rows[0]
        # The staff letter, not a portal copy of it.
        assert row.template_code == ACK
        assert row.channel == "email"
        art = rendering.render_for_dispatch(row)
        assert rendering.ABSENT_MARK not in art.body
        assert "Thank you, Kyle Mark." in art.body
        assert request.request_no in art.body
        # Service type: the service's Settings name, never its code.
        assert "request for Water at" in art.body
        # Target date: request day + the setting's working days.
        day = timezone.localtime(request.submitted_at, tenancy_selectors.tenant_timezone()).date()
        expected = _working(day, 15).strftime("%m/%d/%Y")
        assert f"Our target date for it is {expected}." in art.body
        fresh = sr.request_row(request.id)
        assert fresh.acknowledgement_state == sr.ACK_QUEUED
        assert fresh.acknowledgement_ref == str(row.id)


def test_a_portal_request_with_no_email_queues_none(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        request = _portal()
        assert _rows(request).count() == 0
        fresh = sr.request_row(request.id)
        assert fresh.acknowledgement_state == sr.ACK_NOT_SENT
        assert fresh.acknowledgement_absence_reason == sr.ACK_NO_ADDRESS


@pytest.mark.parametrize(
    "bad", ["kyle.mark@example", "kyle.mark at example.test", "kyle@@example.test"]
)
def test_a_portal_request_with_a_malformed_email_queues_none(brazos, dana, bad):
    with pytest.raises(ValidationError):
        validate_email(bad)  # the case is only meaningful if Django refuses it
    with tenant_ctx(brazos):
        _seeded(dana)
        request = _portal(applicant_email=bad)
        assert _rows(request).count() == 0
        fresh = sr.request_row(request.id)
        assert fresh.acknowledgement_state == sr.ACK_NOT_SENT
        assert fresh.acknowledgement_absence_reason == sr.ACK_NO_ADDRESS


def test_the_staff_acknowledgement_keeps_its_role_guard(brazos, dana):
    """The body is shared; the staff door is still staff only (BR-SHL-025)."""
    from core import errors

    with tenant_ctx(brazos):
        _seeded(dana)
        request = _portal(applicant_email="kyle.mark@example.test")
        with pytest.raises(errors.AuthError):
            sr.send_acknowledgement(sr.PORTAL_REPORTER, request.id)


# ═══════════════════════════════════════════════════════════════════════════
# DEF-CWP-10540 — a portal ask that names NO service gets no acknowledgement
# ═══════════════════════════════════════════════════════════════════════════
LEE = {"name": "Lee Park", "phone": "555-0190", "email": "lee.park@example.test"}

#: Each non-service ask through its REAL portal door, with a valid email, so a
#: door that starts passing services (or stops) changes what this proves.
NON_SERVICE_DOORS = {
    "quick_ask": ("quick_ask", {**LEE, "address": "14 Oak St", "details": "Copy please"}),
    "question": ("question", {**LEE, "address": "14 Oak St", "what": "Why did it go up?"}),
    "dispute": (
        "dispute",
        {**LEE, "address": "14 Oak St", "bill_number": "B-1042", "what": "Wrong reading"},
    ),
}


def _assert_nothing_queued(request_id):
    request = sr.request_row(request_id)
    assert not request.services.exists()
    assert _rows(request).count() == 0
    assert request.acknowledgement_state == sr.ACK_NOT_SENT
    # Exactly the pre-DEF-CWP-10539 reason.
    assert request.acknowledgement_absence_reason == sr.ACK_NO_ADDRESS


@pytest.mark.parametrize("door", sorted(NON_SERVICE_DOORS))
def test_a_portal_ask_naming_no_service_queues_none(brazos, dana, door, monkeypatch):
    from apps.customers import models as customer_models
    from apps.portal import services as portal_services

    if door == "quick_ask":
        # The category list is the utility's own; the door's own words helper
        # is not what this case is about.
        monkeypatch.setattr(portal_services, "_quick_ask_words", lambda c, p: "Copy please")
    shape, payload = NON_SERVICE_DOORS[door]
    with tenant_ctx(brazos):
        _seeded(dana)
        before = set(customer_models.ServiceRequest.objects.values_list("id", flat=True))
        portal_services.raise_service_request(brazos.id, shape=shape, payload=payload)
        made = set(customer_models.ServiceRequest.objects.values_list("id", flat=True)) - before
        assert len(made) == 1, made
        _assert_nothing_queued(made.pop())


@pytest.mark.parametrize(
    "words",
    ["Spread $300 over 6 months", "I lost my job", "Stop service from 11/30/2026"],
)
def test_any_portal_request_without_a_service_row_queues_none(brazos, dana, words):
    """The plan, hardship and stop/restart doors name an account, not a
    service; the rule is on `create_from_portal` itself, so a request with no
    service row and a valid email is the case that decides them all."""
    with tenant_ctx(brazos):
        _seeded(dana)
        request = sr.create_from_portal(
            {**PORTAL, "applicant_email": "lee.park@example.test", "what_they_said": words}
        )
        _assert_nothing_queued(request.id)

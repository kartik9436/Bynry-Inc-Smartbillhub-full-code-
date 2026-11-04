"""`DEF-CUS-10445` — the service request acknowledgement, every value filled.

The PO's report of 2026-10-22: the acknowledgement *"shows dashes for name,
address, service type, target date and phone"*. Ruled the same day (decision
log *"Service request acknowledgement: target date, default 15 days, service
type name"*):

1. Target date → *"A: the preferred date the customer asked for."*
2. No date given → *"Default 15 days"* — a Settings number, not a constant
   (*"don't do any hardcoding"*).
3. Service type wording → the name as set in Settings, never the code.

Each case RENDERS the queued row through the same `render_for_dispatch` the
dispatcher uses and asserts the body carries no `ABSENT_MARK` — a test that
only read the stored context would pass over a palette that refused the token.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (hard-won law 7, habit 2):
  * a body that never mentions the token — so the seeded wording is asserted to
    CONTAIN `{service_type}` and `{target_date}`, and a utility's own edited
    body using both is published and rendered;
  * a target date that happens to equal today + 15 because the constant is
    still in the code — so a case moves the setting to 7 and expects +7;
  * one tenant's setting read for another — the isolation case.

Runs on SQLite and on PostgreSQL (`--ds=config.settings.pgtest`).
"""

from __future__ import annotations

import importlib
from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import service_request_service as sr
from apps.notifications import catalogs, rendering, seed_templates, service_request_events
from apps.notifications import models as notification_models
from apps.notifications import template_models as tm
from apps.notifications import template_service
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

ACK = service_request_events.TEMPLATE_ACKNOWLEDGEMENT
ACK_FEE = service_request_events.TEMPLATE_ACKNOWLEDGEMENT_FEE
SETTING = "service_request_default_target_days"

CAPTURE = {
    "channel": "walk_in",
    "applicant_kind": "person",
    "applicant_name": "Pat Rivera",
    "applicant_email": "pat.rivera@example.test",
    "applicant_phone": "555-0100",
    "address_as_given": "1408 Elm St",
    "address_city_as_given": "Austin",
    "address_state_as_given": "TX",
    "address_postal_code_as_given": "78704",
}


def _seeded(actor):
    """The seeded wording, and the support phone Settings → Company would hold.

    The fixture tenant is provisioned with no phone, so `{support_phone}` would
    print `——` — a Settings gap, which is not what these cases are about. It is
    set on the tenant row the identity tokens are read from, as a utility's own
    Company tab would set it.
    """
    from apps.tenancy.models import Tenant
    from core import tenancy as core_tenancy

    tenant = Tenant.objects.get(pk=core_tenancy.current_tenant_id())
    tenant.support_phone = "+1 (281) 555-0164"
    tenant.save(update_fields=["support_phone"])
    seed_templates.seed_notice_templates(actor, on_date=date(2026, 10, 22))


def _submitted(actor, *, services=("water",), **overrides):
    request = sr.create_request(actor, {**CAPTURE, **overrides})
    sr.set_services(actor, request.id, list(services))
    sr.submit(actor, request.id)
    return sr.request_row(request.id)


def _ack_row(request):
    return (
        notification_models.OutboundMessage.objects.filter(
            source_type=service_request_events.SOURCE_SERVICE_REQUEST,
            source_id=str(request.id),
        )
        .order_by("-created_at")
        .first()
    )


def _rendered(request):
    row = _ack_row(request)
    assert row is not None, "no acknowledgement was queued"
    return row, rendering.render_for_dispatch(row)


def _request_day(request):
    zone = tenancy_selectors.tenant_timezone()
    from django.utils import timezone

    return timezone.localtime(request.submitted_at, zone).date()


def _us(day):
    return day.strftime("%m/%d/%Y")


def _working(day, count):
    """The same count the product uses — weekends and this utility's holidays out."""
    from apps.customers import cut_date
    from apps.customers import seams as customer_seams

    return cut_date.business_days_after(day, count, customer_seams.tenant_holidays())


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE PALETTE — both classes allow the two tokens a utility already used
# ═══════════════════════════════════════════════════════════════════════════
def test_both_acknowledgement_classes_allow_service_type_and_target_date():
    for code in (ACK, ACK_FEE):
        tokens = catalogs.AUTHORED_CATALOGS[code].tokens
        assert {"service_type", "target_date"} <= tokens, code
        # The rest of the applicant palette is untouched.
        assert {"applicant_name", "request_no", "service_address"} <= tokens
    # The approval / refusal / more-info letters were not part of the ruling.
    assert "target_date" not in catalogs.AUTHORED_CATALOGS["service_request_approved"].tokens


def test_the_seeded_wording_names_both_and_the_migration_carries_it_exactly():
    mig = importlib.import_module(
        "apps.notifications.migrations.0026_def_cus_10445_service_request_ack_wording"
    )
    assert mig.NEW_ACK == seed_templates.SERVICE_REQUEST_ACK_BODY
    assert mig.NEW_ACK_FEE == seed_templates.SERVICE_REQUEST_ACK_FEE_BODY
    assert mig.SUBJECT == seed_templates.SERVICE_REQUEST_ACK_SUBJECT
    for body in (mig.NEW_ACK, mig.NEW_ACK_FEE):
        assert "{service_type}" in body and "{target_date}" in body
    for body in (mig.OLD_ACK, mig.OLD_ACK_FEE):
        assert "{service_type}" not in body


# ═══════════════════════════════════════════════════════════════════════════
# 2 · STAFF NEW REQUEST, NO FEE — every token filled
# ═══════════════════════════════════════════════════════════════════════════
def test_no_fee_with_a_preferred_date_fills_every_token(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        request = _submitted(dana, requested_start="2026-11-30")
        row, art = _rendered(request)
        assert row.template_code == ACK
        assert rendering.ABSENT_MARK not in art.body
        assert rendering.ABSENT_MARK not in (art.subject or "")
        assert "Thank you, Pat Rivera." in art.body
        assert request.request_no in art.body
        # The typed address in parts — street, town, state, postcode.
        assert "1408 Elm St, Austin, TX 78704" in art.body
        # The service's Settings name, never its code.
        assert "request for Water at" in art.body
        assert "water at" not in art.body
        # The preferred date, in the Regional format (brazos: MM/DD/YYYY).
        assert "Our target date for it is 11/30/2026." in art.body


def test_no_preferred_date_aims_at_the_request_date_plus_15_working_days(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        assert tenancy_selectors.settings_family("service-requests")[SETTING] == 15
        request = _submitted(dana)
        _row, art = _rendered(request)
        expected = _working(_request_day(request), 15)
        assert f"Our target date for it is {_us(expected)}." in art.body
        assert rendering.ABSENT_MARK not in art.body


def test_a_date_given_against_a_service_counts_as_the_preferred_date(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        request = sr.create_request(dana, CAPTURE)
        sr.set_services(dana, request.id, ["water"])
        customer_models.ServiceRequestService.objects.filter(request_id=request.id).update(
            requested_start=date(2026, 12, 4)
        )
        sr.submit(dana, request.id)
        _row, art = _rendered(sr.request_row(request.id))
        assert "Our target date for it is 12/04/2026." in art.body


def test_changing_the_setting_moves_the_target_date(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        saved = tenancy_services.save_settings_family(dana, "service-requests", {SETTING: 7})
        assert saved[SETTING] == 7
        request = _submitted(dana)
        _row, art = _rendered(request)
        expected = _working(_request_day(request), 7)
        assert f"Our target date for it is {_us(expected)}." in art.body


def test_the_connection_date_prefill_reads_the_same_setting(brazos, dana):
    """The 2026-09-22 *"15 working days"* prefill was a constant; it is the setting now."""
    from apps.customers import seams as customer_seams
    from apps.customers import service_request_api

    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        today = customer_seams.tenant_today()
        tenancy_services.save_settings_family(dana, "service-requests", {SETTING: 7})
        expected = _working(today, 7).isoformat()
    response = api_call(
        service_request_api.service_request_capture_defaults,
        "get",
        user=getattr(dana, "user", None),
        tenant=brazos,
        role="system_admin",
    )
    assert response.status_code == 200, response.data
    assert response.data["working_days"] == 7
    assert response.data["requested_start"] == expected
    assert not hasattr(service_request_api, "CONNECTION_DATE_WORKING_DAYS")


def test_the_setting_refuses_a_negative_number(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            tenancy_services.save_settings_family(dana, "service-requests", {SETTING: -1})
        assert tenancy_selectors.settings_family("service-requests")[SETTING] == 15


def test_several_services_are_named_from_settings_in_catalogue_order(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        request = _submitted(dana, services=("water", "electric"))
        _row, art = _rendered(request)
        # Settings → Services' names, in the platform catalogue's sort order.
        assert "request for Electric, Water at" in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE FEE PATH — the fee class carries the same facts
# ═══════════════════════════════════════════════════════════════════════════
def test_the_fee_class_fills_every_token_too(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        request = sr.create_request(dana, {**CAPTURE, "requested_start": "2026-11-30"})
        sr.set_services(dana, request.id, ["water"])
        # The money facts as `collect_fee` leaves them on the row; the receipt
        # number is what pins the fee class (BR-CUS-090 clause (3)).
        customer_models.ServiceRequest.objects.filter(pk=request.id).update(
            fee_collected=Decimal("25.0000"),
            fee_currency="USD",
            fee_method="cash",
            fee_receipt_no="RCT-26-0042",
        )
        sr.submit(dana, request.id)
        row, art = _rendered(sr.request_row(request.id))
        assert row.template_code == ACK_FEE
        assert rendering.ABSENT_MARK not in art.body
        assert "request for Water at 1408 Elm St, Austin, TX 78704" in art.body
        assert "Our target date for it is 11/30/2026." in art.body
        assert "You paid $25.00 by cash. Your receipt number is RCT-26-0042." in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 4 · HARD RULE 8 — a picked premises is walked to
# ═══════════════════════════════════════════════════════════════════════════
def test_a_picked_unit_reads_its_premises_address_and_its_own_label(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        premises = make_premises(dana, address_line="77 Bluestem Ln", city="Katy")
        unit = make_unit(dana, premises["id"], label="B")
        request = _submitted(
            dana,
            address_as_given="77 bluestem",
            picked_premises_id=str(premises["id"]),
            picked_unit_id=str(unit["id"]),
        )
        _row, art = _rendered(request)
        assert "at 77 Bluestem Ln · B, Katy, TX 77494." in art.body
        assert "77 bluestem" not in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE ACCOUNT HOLDER FILLS A BLANK NAME AND ADDRESS
# ═══════════════════════════════════════════════════════════════════════════
def test_a_blank_name_and_address_come_from_the_account_holder(monkeypatch):
    from apps.notifications import customer_context

    asked = []

    def holder(account_id):
        asked.append(account_id)
        return {
            "first_name": "Maria",
            "customer_name": "Maria Lopez",
            "account_no": "A-1001",
            "service_address": "12 Oak Ave, Austin, TX 78701",
        }

    monkeypatch.setattr(customer_context, "customer_context", holder)
    name, line = service_request_events._applicant_facts(
        applicant_name="",
        service_address="",
        service_address_parts=None,
        account_id="acct-1",
    )
    assert (name, line) == ("Maria Lopez", "12 Oak Ave, Austin, TX 78701")
    # The caller's own facts always win, and nothing is asked when none is blank.
    asked.clear()
    name, line = service_request_events._applicant_facts(
        applicant_name="Pat Rivera",
        service_address="1408 Elm St",
        service_address_parts=None,
        account_id="acct-1",
    )
    assert (name, line) == ("Pat Rivera", "1408 Elm St") and asked == []


# ═══════════════════════════════════════════════════════════════════════════
# 6 · A UTILITY'S OWN EDITED WORDING — publishes, and renders filled
# ═══════════════════════════════════════════════════════════════════════════
UTILITY_BODY = (
    "Hello, {applicant_name}. We received your request for {service_type} on "
    "{target_date} at {service_address}. Your number is {request_no}.\n\n"
    "Questions? Call {support_phone}.\n\n{utility_name}"
)


def test_a_utility_body_using_both_tokens_publishes_and_renders(brazos, dana):
    with tenant_ctx(brazos):
        _seeded(dana)
        template = tm.NotificationTemplate.objects.get(
            tenant=brazos, code=ACK, category="default", language="default"
        )
        draft = template_service.save_draft(
            template=template, body=UTILITY_BODY, actor=dana, subject="Your request {request_no}"
        )
        template_service.publish(version_row=draft, actor=dana)
        request = _submitted(dana, requested_start="2026-11-30")
        _row, art = _rendered(request)
        assert rendering.ABSENT_MARK not in art.body
        assert "request for Water on 11/30/2026 at 1408 Elm St, Austin, TX 78704" in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 7 · TENANT ISOLATION — one utility's number is not another's
# ═══════════════════════════════════════════════════════════════════════════
def test_one_utilitys_setting_does_not_reach_another(brazos, dana, lonestar, erin):
    with tenant_ctx(lonestar):
        tenancy_services.save_settings_family(erin, "service-requests", {SETTING: 3})
        assert tenancy_selectors.settings_family("service-requests")[SETTING] == 3
    with tenant_ctx(brazos):
        assert tenancy_selectors.settings_family("service-requests")[SETTING] == 15
        _seeded(dana)
        request = _submitted(dana)
        _row, art = _rendered(request)
        expected = _working(_request_day(request), 15)
        assert f"Our target date for it is {_us(expected)}." in art.body


# ═══════════════════════════════════════════════════════════════════════════
# 8 · THE MIGRATION — an untouched copy moves, an edited one never does
# ═══════════════════════════════════════════════════════════════════════════
def test_the_migration_moves_an_untouched_copy_and_leaves_an_edited_one(brazos, dana):
    from django.apps import apps as django_apps
    from django.db import connection

    mig = importlib.import_module(
        "apps.notifications.migrations.0026_def_cus_10445_service_request_ack_wording"
    )
    with tenant_ctx(brazos):
        _seeded(dana)
        templates = {
            code: tm.NotificationTemplate.objects.get(
                tenant=brazos, code=code, category="default", language="default"
            )
            for code in (ACK, ACK_FEE)
        }
        # The no-fee copy goes back to the OLD seed; the fee copy is EDITED.
        bodies = {ACK: mig.OLD_ACK, ACK_FEE: mig.OLD_ACK_FEE + "\n\nSee you soon."}
        planted = {}
        for code, template in templates.items():
            live = tm.NotificationTemplateVersion.objects.get(template=template, status="published")
            live.status = "archived"
            live.save(update_fields=["status"])
            planted[code] = tm.NotificationTemplateVersion.objects.create(
                tenant=brazos,
                template=template,
                version=live.version + 1,
                status="published",
                subject=mig.SUBJECT,
                body=bodies[code],
            )

        class _Editor:
            pass

        editor = _Editor()
        editor.connection = connection
        mig.republish_unedited(django_apps, editor)

    with tenant_ctx(brazos):
        moved = tm.NotificationTemplateVersion.objects.get(
            template=templates[ACK], status="published"
        )
        assert moved.body == mig.NEW_ACK and moved.version == planted[ACK].version + 1
        kept = tm.NotificationTemplateVersion.objects.get(
            template=templates[ACK_FEE], status="published"
        )
        assert kept.pk == planted[ACK_FEE].pk and kept.body.endswith("See you soon.")
        count = tm.NotificationTemplateVersion.objects.filter(tenant=brazos).count()
        mig.republish_unedited(django_apps, editor)
    with tenant_ctx(brazos):
        assert tm.NotificationTemplateVersion.objects.filter(tenant=brazos).count() == count

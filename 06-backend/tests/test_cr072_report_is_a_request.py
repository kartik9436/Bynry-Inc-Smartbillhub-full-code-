# ── Trace ──────────────────────────────────────────────
# Change:  CR-072 (2026-09-04) — *"all the request coming from portal should go
#          in Service request. if we have to icnrease the defination of Service
#          request we should do it"* (PO, on the live deployment).
#          Screens: CWP-006 · CWP-007 · CWP-012 · the Interruption section
# Rules:   BR-CWP-100 (a report IS a service request; one record, one number) ·
#          BR-CWP-101 (a CLERK opens the interruption, and many reports may
#          point at one) · BR-CWP-024 (one reference, and it is theirs) ·
#          BR-CWP-026 (a guest write creates work and changes no account) ·
#          BR-CWP-027 (the reporter need not be a customer)
# Tests:   this file — one row not two; the SR- number is what a stranger keeps;
#          the kind is refused by name; only a clerk may open an interruption;
#          twelve reports gather onto one; a non-report is refused a link;
#          BR-CWP-026 on the database
# Impacts: apps/portal/services._report · apps/portal/guest_api.reports ·
#          apps/customers/service_request_service.attach_interruption ·
#          apps/customers/service_request_api.service_request_interruption
# ───────────────────────────────────────────────────────
"""CR-072 — the report IS the request, and a clerk decides what is an outage."""

import pytest

from apps.customers import models as customers_models
from apps.customers import service_request_api, service_request_service
from apps.metering import interruption_service
from apps.metering import interruptions as interruption_models
from apps.portal import guest_api
from core import errors
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_ten_helpers import api_call

REPORT = {
    "kind": "leak_or_burst",
    "location_text": "1408 Elm St, Austin TX 78702",
    "notes": "Water coming up through the pavement outside number 1412.",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}


def _report(tenant, body=None):
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT if body is None else body),
        headers={"X-Forwarded-For": "198.51.100.10"},
    )


def _section(tenant, actor, request_id, method="get", data=None):
    return api_call(
        service_request_api.service_request_interruption,
        method,
        f"/api/{tenant.subdomain}/service-requests/{request_id}/interruption",
        tenant=tenant,
        user=actor.user,
        role="system_admin",
        data=data or {},
        request_id=str(request_id),
    )


@pytest.mark.django_db
def test_cr072_one_press_of_send_writes_one_row_and_hands_back_its_number(pine_hill, sarah):
    """**THE WHOLE RULING, ON THE DATABASE.**

    Before: two rows and the stranger held the number of the one that was not
    their request. After: one row, and its number is what they keep.
    """
    switch_on(pine_hill, sarah)
    body = _report(pine_hill).data

    assert customers_models.ServiceRequest.objects.count() == 1
    assert interruption_models.Interruption.objects.count() == 0

    request = customers_models.ServiceRequest.objects.get()
    assert body["reference"] == request.request_no
    assert body["reference"].startswith("SR-")
    assert request.problem_kind == "leak_or_burst"
    assert request.what_they_said == REPORT["notes"]
    assert request.address_as_given == REPORT["location_text"]
    assert request.applicant_name == "D. Okafor"
    assert request.channel == "customer_portal"


@pytest.mark.django_db
def test_cr072_a_kind_the_utility_does_not_record_is_refused_by_name(pine_hill, sarah):
    """The vocabulary is `metering`'s and it is checked, not copied.

    ⚠ `gas_smell` is the one that matters: it is OFFERED by the form and routed
    to a phone number, and a row carrying it would sit on a queue — which is the
    opposite of what `US-CWP-007` TC-3 asks for.
    """
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.ValidationError) as caught:
            service_request_service.create_from_portal(
                {
                    "applicant_name": "D. Okafor",
                    "applicant_phone": "(512) 555-7730",
                    "address_as_given": "1408 Elm St",
                    "problem_kind": "a_dragon",
                }
            )
    assert caught.value.message_key == "customers.serviceRequest.problemKindUnknown"
    assert "gas_smell" not in interruption_models.STORABLE_KINDS
    assert customers_models.ServiceRequest.objects.count() == 0


@pytest.mark.django_db
def test_cr072_a_guest_cannot_open_an_interruption_and_the_guard_is_a_role(pine_hill, sarah):
    """⚠ **THE NARROWING THIS RULING BOUGHT.** `create_interruption` carried no
    `@require_role` while the guest edge reached it — the guard was the
    narrowness of its arguments. The guest edge is gone, so the guard is a role,
    and `PORTAL_REPORTER` (which has none) is refused by it."""
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        with pytest.raises(errors.AuthError) as caught:
            interruption_service.create_interruption(
                service_request_service.PORTAL_REPORTER,
                kind="leak_or_burst",
                location_text="1408 Elm St",
            )
    assert caught.value.code == "AUTH-002"
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_cr072_a_clerk_opens_one_and_the_report_reads_its_progress_through(pine_hill, sarah):
    """`BR-CWP-101` — a person judges the reports real, and from then on the
    report shows what the CREW is doing rather than what the paperwork says."""
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    request = customers_models.ServiceRequest.objects.get()

    before = _section(pine_hill, sarah, request.id)
    assert before.status_code == 200
    assert before.data["interruption"] is None, "nobody has judged it yet"
    assert before.data["report"]["kind"] == "leak_or_burst"

    opened = _section(pine_hill, sarah, request.id, method="post")
    assert opened.status_code == 201
    assert opened.data["interruption"]["reference"].startswith("RP-")
    request.refresh_from_db()
    assert request.interruption_id is not None

    row = interruption_models.Interruption.objects.get()
    with tenant_context(pine_hill.id):
        interruption_service.set_status(sarah, row.id, status="crew_on_site")

    tracked = api_call(
        guest_api.track,
        "post",
        f"/api/{pine_hill.subdomain}/portal/public/track",
        tenant=pine_hill,
        data={"reference": reference, "second_fact": "78702"},
        headers={"X-Forwarded-For": "203.0.113.7"},
    )
    assert tracked.data["status"] == "crew_on_site"
    # ⚠ AND STILL ONE REFERENCE. The `RP-` is the utility's own record.
    assert "RP-" not in str(tracked.data)


@pytest.mark.django_db
def test_cr072_many_reports_gather_onto_one_interruption(pine_hill, sarah):
    """**THE SHAPE THE RULING ASKS FOR.** Three people ring about one burst
    main: three requests, ONE operational record, and the second and third are
    offered the one that is already open rather than opening another."""
    switch_on(pine_hill, sarah)
    _report(pine_hill)
    _report(pine_hill, dict(REPORT, location_text="1412 Elm St, outside the shop"))
    _report(pine_hill, dict(REPORT, location_text="1416 Elm St, by the postbox"))
    requests = list(customers_models.ServiceRequest.objects.order_by("received_at"))
    assert len(requests) == 3

    first = _section(pine_hill, sarah, requests[0].id, method="post")
    opened_id = first.data["interruption"]["id"]

    # The clerk opening the SECOND report is offered the one already open.
    second = _section(pine_hill, sarah, requests[1].id)
    assert second.data["already_open_nearby"]["id"] == opened_id

    for row in requests[1:]:
        answer = _section(pine_hill, sarah, row.id, method="post", data={"interruption_id": opened_id})
        assert answer.status_code == 201
        assert answer.data["interruption"]["id"] == opened_id

    assert interruption_models.Interruption.objects.count() == 1
    assert (
        customers_models.ServiceRequest.objects.filter(interruption_id=opened_id).count() == 3
    )


@pytest.mark.django_db
def test_cr072_a_request_that_is_not_a_report_is_refused_an_interruption(pine_hill, sarah):
    """A move-in is not about a burst main, and the section is ABSENT on it."""
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        request = service_request_service.create_from_portal(
            {
                "applicant_name": "M. Alvarez",
                "applicant_phone": "(512) 555-0134",
                "address_as_given": "31 Palm Ct, Austin TX 78702",
                "what_they_said": "Applied through the customer portal for: water.",
            }
        )
    answer = _section(pine_hill, sarah, request.id)
    assert answer.status_code == 404, "absent, not an empty frame"

    with tenant_context(pine_hill.id):
        row = interruption_service.create_interruption(
            sarah, kind="leak_or_burst", location_text="1408 Elm St"
        )
        with pytest.raises(errors.BizError) as caught:
            service_request_service.attach_interruption(
                sarah, request.id, interruption_id=row.id
            )
    assert caught.value.message_key == "customers.serviceRequest.notAReport"


@pytest.mark.django_db
def test_cr072_a_report_already_attached_is_refused_a_second_one(pine_hill, sarah):
    """The same refusal `link_child` makes, and for the same reason: a silent
    re-point moves a report off a record a clerk has already told somebody
    about."""
    switch_on(pine_hill, sarah)
    _report(pine_hill)
    request = customers_models.ServiceRequest.objects.get()
    _section(pine_hill, sarah, request.id, method="post")
    with tenant_context(pine_hill.id):
        other = interruption_service.create_interruption(
            sarah, kind="no_water", location_text="9 Cedar Row"
        )
        with pytest.raises(errors.BizError) as caught:
            service_request_service.attach_interruption(
                sarah, request.id, interruption_id=other.id
            )
    assert caught.value.message_key == "customers.serviceRequest.interruptionAlreadyAttached"


@pytest.mark.django_db
def test_cr072_widening_the_request_record_changes_no_account(pine_hill, sarah):
    """`BR-CWP-026`, re-asserted on the database because the record widened.

    *A public form may create work and may never change an account.* The two new
    columns are a radio button and a pointer at the utility's own record; the
    rule they might have weakened is checked rather than assumed.
    """
    switch_on(pine_hill, sarah)
    before = list(customers_models.Account.objects.values_list("id", "updated_at"))
    _report(pine_hill)
    request = customers_models.ServiceRequest.objects.get()
    _section(pine_hill, sarah, request.id, method="post")
    assert list(customers_models.Account.objects.values_list("id", "updated_at")) == before


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-072 §4 (the ruled shape) + BR-CWP-100/100 (added by this build)
# generated: 2026-09-04 by the CR-072 build lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=n/a
# gates: pytest tests/test_cr072_report_is_a_request.py · the PostgreSQL half is tests/test_cr072_pg.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

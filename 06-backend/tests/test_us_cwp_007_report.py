# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-007 (EP-CWP-03) — report a problem, and the reporter need not
#           be a customer. Screens: CWP-006 · CWP-007
# Rules:    BR-CWP-027 · BR-CWP-026 · BR-CWP-076 · BR-CWP-022 · CR-068 §2b
#           (consumer upload is a SIGNED DEFERRAL — the picker is held and the
#           edge refuses a file)
# Tests:    this file — TC-1 (the reference and the worklist row), TC-2 (an
#           address matching no premises is ACCEPTED), TC-3 (a smell of gas
#           creates NOTHING), TC-4 (no phone → refused), TC-6 (the row lands
#           under one tenant only), TC-7 (a second report on the street is
#           accepted and says so), TC-8 (a photo is refused, not dropped)
# Impacts:  apps/portal/services.py · guest_api.py · apps/customers/
#           service_request_service.create_from_portal
# ───────────────────────────────────────────────────────
"""US-CWP-007 — the first write the customer portal has ever done.

⚠ **AMENDED 2026-09-04 BY `CR-072`, AND WHAT MOVED IS SAID CASE BY CASE.**
Every case below used to assert that ONE press of *Send* produced TWO rows — a
`service_requests` row and an `interruptions` row — and that the stranger was
handed the INTERRUPTION's `RP-26-0412` while the `SR-` number the same call made
was withheld. The Product Owner ruled that shape out on the live deployment:
*"all the request coming from portal should go in Service request"*.

**Nothing here was deleted.** Each case keeps its number, its name and the rule
it was written for; what changed is which row it counts and which prefix it
reads, and each says so where it does it. A test that was rewritten silently
would leave nobody able to tell a supersession from a regression.
"""

import pytest

from apps.customers import models as customers_models
from apps.metering import interruptions as interruption_models
from apps.portal import guest_api
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, switch_on
from tests.test_us_ten_helpers import api_call

REPORT = {
    "kind": "leak_or_burst",
    "location_text": "1408 Elm St, Austin TX 78702",
    "notes": "Water coming up through the pavement outside number 1412, been going since about seven...",
    "reporter_name": "D. Okafor",
    "reporter_phone": "(512) 555-7730",
}


def _report(tenant, body=None, address="198.51.100.10"):
    """The guest call: NO user, NO role — a passer-by holding nothing."""
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT if body is None else body),
        headers={"X-Forwarded-For": address},
    )


@pytest.mark.django_db
def test_us_cwp_007_tc1_a_stranger_gets_a_reference_and_a_clerk_gets_the_row(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    response = _report(pine_hill)
    assert response.status_code == 201
    body = response.data

    # ⚠ **THIS ASSERTED `RP-` UNTIL 2026-09-04 AND NOW ASSERTS `SR-`
    # (`CR-072`).** The reference is the whole record of the interaction
    # (`BR-CWP-028`) and `BR-CWP-024` gives the person ONE of them — so it has
    # to be the number of the record that IS their request. It used to be the
    # number of the second row the same call created.
    assert body["reference"].startswith("SR-")
    assert body["kind"] == "leak_or_burst"
    assert body["status"] == "looking_into_it"
    assert body["location_text"] == REPORT["location_text"]

    # BR-CWP-076 — the first row in this product ever to carry the channel.
    request = customers_models.ServiceRequest.objects.get(tenant_id=pine_hill.id)
    assert request.channel == "customer_portal"
    assert request.state == "submitted", "a guest has no draft to come back to"
    assert request.request_no == body["reference"]
    assert request.applicant_name == "D. Okafor"
    # CR-072 — the widening the PO pre-authorised. What was wrong is on the row.
    assert request.problem_kind == "leak_or_burst"

    # ⚠ **AND NO SECOND ROW AT ALL.** This block used to fetch the interruption
    # the same act created and assert its `service_request_id`; there is no such
    # row now, and counting it is the assertion that keeps it that way.
    assert interruption_models.Interruption.objects.count() == 0
    assert request.interruption_id is None, "a clerk opens one; a form does not"
    assert "RP-" not in str(body)

    # BR-CWP-021 / hard rule 7 — nobody is signed in, so the trail says so
    # rather than naming somebody who was not there.
    assert request.received_by_id is None


@pytest.mark.django_db
def test_us_cwp_007_tc2_an_address_matching_no_premises_is_accepted(pine_hill, sarah):
    """⚠ NEVER A REFUSAL. `premises_id` stays null and a clerk resolves it."""
    switch_on(pine_hill, sarah)
    body = dict(REPORT, location_text="the corner of Elm and something, near the big oak")
    response = _report(pine_hill, body)
    assert response.status_code == 201
    # ⚠ **THE ROW MOVED TABLES (`CR-072`) AND THE RULE DID NOT.** This read
    # `Interruption.objects.get(...)` and asserted `premises_id is None`; the
    # free text now lands in `address_as_given`, which `BR-CUS-070` keeps
    # verbatim, and the resolved premises sits BESIDE it, still empty.
    row = customers_models.ServiceRequest.objects.get(tenant_id=pine_hill.id)
    assert row.resolved_premises_id is None
    assert row.address_as_given == body["location_text"]


@pytest.mark.django_db
def test_us_cwp_007_tc3_a_smell_of_gas_returns_a_phone_number_and_creates_nothing(pine_hill, sarah):
    """⚠ THE EMERGENCY PANEL IS ROUTING, NOT A DISCLAIMER."""
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    response = _report(pine_hill, dict(REPORT, kind="gas_smell"))
    assert response.status_code == 200
    assert response.data["created"] is False
    assert response.data["emergency_phone"] == "(512) 555-0100"
    # Asserted ON THE DATABASE, which is what the demo script asks for.
    assert customers_models.ServiceRequest.objects.count() == 0
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_007_tc4_no_phone_is_refused(pine_hill, sarah):
    """*"We ring you only if we need to"* requires a way to ring."""
    switch_on(pine_hill, sarah)
    body = dict(REPORT)
    body.pop("reporter_phone")
    response = _report(pine_hill, body)
    assert response.status_code == 422
    assert response.data["code"] == "VAL-001"
    assert response.data["message_key"] == "customers.serviceRequest.fieldRequired"
    assert response.data["params"]["field"] == "applicant_phone"
    # ⚠ Now the count that matters is the REQUEST's — a refused report must
    # leave no worklist row either.
    assert customers_models.ServiceRequest.objects.count() == 0
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_007_tc6_the_row_lands_under_one_tenant_only(pine_hill, sarah, oak_ridge, elena):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    _report(oak_ridge)
    # ⚠ The row this counts moved (`CR-072`): the report IS the request, so the
    # tenant boundary is asserted on the table it now lands in.
    assert customers_models.ServiceRequest.objects.filter(tenant_id=oak_ridge.id).count() == 1
    assert customers_models.ServiceRequest.objects.filter(tenant_id=pine_hill.id).count() == 0
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_007_tc7_a_second_report_on_the_street_is_accepted_and_says_so(pine_hill, sarah):
    """⚠ TWO REPORTS OF ONE BURST IS THE DESIRED BEHAVIOUR."""
    switch_on(pine_hill, sarah)
    first = _report(pine_hill)
    assert first.data["already_reported_street"] is None
    second = _report(pine_hill, dict(REPORT, location_text="1412 Elm St, outside the shop"))
    assert second.status_code == 201, "a second report is never refused"
    # ⚠ **THE SENTENCE SURVIVED A TABLE MOVE, AND THIS LINE IS WHY IT HAD TO BE
    # CHECKED (`CR-072`).** The scan behind it read `interruptions`; reports do
    # not write that table any more, so left alone it would have answered None
    # for every real second report — a shipped promise going silent with every
    # test green. It reads open REPORTS now (`customers_seam.
    # open_report_on_street`) and a confirmed interruption when there is one.
    assert second.data["already_reported_street"] == "Elm St"
    # Two reports, two REQUESTS, and still no interruption: nobody has judged
    # them yet, which is the honest state.
    assert customers_models.ServiceRequest.objects.count() == 2
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_007_tc8_a_photo_is_refused_by_name_and_not_dropped(pine_hill, sarah):
    """⚠ HELD — consumer upload is a signed deferral (PO 2026-08-08, DF-4).

    A dropped file is a screen that says *attached* over nothing, so the edge
    refuses the field by name until the re-sign (task B9).
    """
    switch_on(pine_hill, sarah)
    response = _report(pine_hill, dict(REPORT, photo="data:image/jpeg;base64,AAAA"))
    assert response.status_code in (409, 422)
    assert response.data["message_key"] == "portal.report.photoHeld"
    assert customers_models.ServiceRequest.objects.count() == 0
    assert interruption_models.Interruption.objects.count() == 0


@pytest.mark.django_db
def test_us_cwp_007_no_account_row_is_changed_by_a_guest_write(pine_hill, sarah):
    """BR-CWP-026 — *a public form may create work and may never change an
    account*. The wave's exit test, asserted on the database."""
    switch_on(pine_hill, sarah)
    before = list(customers_models.Account.objects.values_list("id", "updated_at"))
    _report(pine_hill)
    assert list(customers_models.Account.objects.values_list("id", "updated_at")) == before


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-007@d6d31c46 (EP-CWP-03 §3 cases, written before the code)
# generated: 2026-09-04 by the CR-068 wave B build lane · AMENDED 2026-09-04 by the CR-072 lane (the report IS the request: the `SR-` number is served, and the second row is gone). Each amended assertion names what it used to assert and why it moved.
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_007_report.py
# exceptions: TC-5 (the 61st report in a minute) is in tests/test_us_cwp_002_lockout.py with the other throttle cases, so the throttle's two halves are read together
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

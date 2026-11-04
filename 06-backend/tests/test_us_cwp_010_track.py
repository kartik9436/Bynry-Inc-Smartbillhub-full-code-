# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-010 (EP-CWP-03) — Track anything: progress, and never data ·
#           US-CWP-009 — the reference a stranger keeps. Screens: CWP-012 · CWP-007
# Rules:    BR-CWP-024 (progress and never data — no name, no balance, no other
#           reference) · BR-CWP-025 (a second fact only the sender would know) ·
#           BR-CWP-023 (five wrong pairs lock fifteen minutes — the cases are in
#           tests/test_us_cwp_002_lockout.py) · BR-CWP-028
# Tests:    this file — 010 TC-1 (reference + postcode), TC-2 (a request +
#           the phone given), TC-3 (a wrong postcode is refused IDENTICALLY to
#           an unknown reference), TC-4 (the RESPONSE BODY names no customer
#           field), TC-6 (a Pine Hill reference under Oak Ridge is not found),
#           TC-7 (a payment reference — the wave-P boundary, stated) · 009 TC-2
#           (the timeline updated), TC-4 (an internal note never appears)
# Impacts:  apps/portal/selectors.track · seams/metering_seam.py ·
#           seams/customers_seam.py
# ───────────────────────────────────────────────────────
"""US-CWP-010 — the limit is absolute: PROGRESS, NEVER DATA.

⚠ **AMENDED 2026-09-04 BY `CR-072`.** Every case here used to type an `RP-`
reference into the tracker, because a report WAS an interruption. It is a
service request now and the person is handed its `SR-` number, so what changes
is the reference typed and the row behind it — **not one key of the answer**.
`TC-4`'s frozen key set is byte-identical on purpose: moving the record was not
licence to widen what a stranger can read.
"""

import pytest

from apps.customers import service_request_service
from apps.metering import interruption_service
from apps.metering import interruptions as interruption_models
from apps.portal import guest_api
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


def _report(tenant):
    return api_call(
        guest_api.reports,
        "post",
        f"/api/{tenant.subdomain}/portal/public/reports",
        tenant=tenant,
        data=dict(REPORT),
        headers={"X-Forwarded-For": "198.51.100.10"},
    )


def _track(tenant, reference, second_fact, address="203.0.113.7"):
    return api_call(
        guest_api.track,
        "post",
        f"/api/{tenant.subdomain}/portal/public/track",
        tenant=tenant,
        data={"reference": reference, "second_fact": second_fact},
        headers={"X-Forwarded-For": address},
    )


@pytest.mark.django_db
def test_us_cwp_010_tc1_a_reference_and_a_postcode_show_the_kind_and_the_status(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    assert reference.startswith("SR-"), "CR-072 — one reference, and it is the request's"

    # ⚠ **THREE LINES WHERE THERE USED TO BE TWO, AND THE EXTRA ONE IS THE
    # RULING.** This case fetched the interruption the report had just created
    # and moved it. A report does not create one; a CLERK opens it when the
    # reports are real (`BR-CWP-101`), so the test does what the clerk does.
    request = service_request_service.models.ServiceRequest.objects.get(tenant_id=pine_hill.id)
    with tenant_context(pine_hill.id):
        row = interruption_service.create_interruption(
            sarah, kind="leak_or_burst", location_text=REPORT["location_text"]
        )
        service_request_service.attach_interruption(sarah, request.id, interruption_id=row.id)
        interruption_service.set_status(sarah, row.id, status="crew_on_site")

    response = _track(pine_hill, reference, "78702")
    assert response.status_code == 200
    body = response.data
    assert body["reference"] == reference
    assert body["kind"] == "leak_or_burst"
    # 009 TC-2 — the timeline moved. It moved on the CONFIRMED interruption and
    # the report reads it through, which is what makes twelve reports of one
    # burst all show the same crew arriving.
    assert body["status"] == "crew_on_site"
    assert body["location_text"] == REPORT["location_text"]
    assert "RP-" not in str(body), "the RP- series is not customer-facing (CR-072)"


@pytest.mark.django_db
def test_us_cwp_010_tc2_a_request_and_the_phone_given_show_progress_and_dates(pine_hill, sarah):
    """⚠ **THIS CASE USED TO TRACK A REPORT AND NOW TRACKS A NON-REPORT
    (`CR-072`).** Before, the report's `SR-` number was the second reference the
    same act created, so tracking it exercised the `request` shape. There is one
    reference now and a report answers the REPORT shape, so the *request* shape
    needs a request that is not a report — a quick ask, which is what
    `CWP-010`'s cards raise."""
    switch_on(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        request = service_request_service.create_from_portal(
            {
                "applicant_name": "D. Okafor",
                "applicant_phone": "(512) 555-7730",
                "address_as_given": "1408 Elm St, Austin TX 78702",
                "what_they_said": "Asked through the customer portal: A copy of a bill",
            }
        )
    response = _track(pine_hill, request.request_no, "512 555 7730")
    assert response.status_code == 200
    assert response.data["series"] == "request"
    assert response.data["status"] == "submitted"
    assert response.data["submitted_at"] is not None


@pytest.mark.django_db
def test_us_cwp_010_tc3_a_wrong_postcode_is_refused_identically_to_an_unknown_reference(
    pine_hill, sarah
):
    """⚠ ONE ANSWER FOR BOTH. A different answer for *right reference, wrong
    postcode* confirms the reference exists, which is the enumeration this
    endpoint is guarded against."""
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]

    wrong_fact = _track(pine_hill, reference, "99999")
    # ⚠ The unknown reference is an `SR-` now: an `RP-` is not a series a guest
    # is ever handed (`CR-072`), so typing one proves nothing about this rule.
    unknown = _track(pine_hill, "SR-26-9999", "78702")
    assert wrong_fact.status_code == unknown.status_code
    assert wrong_fact.data["code"] == unknown.data["code"]
    assert wrong_fact.data["message_key"] == unknown.data["message_key"] == "portal.track.notFound"
    assert wrong_fact.data["params"] == unknown.data["params"] == {}


@pytest.mark.django_db
def test_us_cwp_010_tc4_the_response_body_names_no_customer_field(pine_hill, sarah):
    """⚠ ASSERTED ON THE RESPONSE BODY, NOT ON THE RENDERED PAGE — a field that
    is served and merely not drawn is served. The wave's exit test."""
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    body = _track(pine_hill, reference, "78702").data
    flat = str(body).lower()
    assert "okafor" not in flat, "no name"
    assert "555-7730" not in str(body) and "5557730" not in str(body), "no phone"
    for forbidden in ("balance", "amount", "owing", "account", "customer", "name", "phone", "id"):
        assert forbidden not in body, f"the body must not carry {forbidden!r}"
    # ⚠ **THE KEY SET IS UNCHANGED BY `CR-072`, DELIBERATELY.** The record moved
    # tables; a stranger reads exactly what they read before. `kind` comes off
    # `problem_kind` and `location_text` off `address_as_given`, which
    # `BR-CUS-070` keeps verbatim — so it is still their own words.
    assert set(body) == {
        "series",
        "reference",
        "kind",
        "location_text",
        "status",
        "reported_at",
        "resolved_at",
        "expected_back_on",
    }
    # ⚠ **THIS LINE INVERTED (`CR-072`).** It read `assert "SR-" not in ...`,
    # for a build where the SR- number was the OTHER reference the same act
    # created and had to be withheld. There is one reference now and it is the
    # `SR-`; what must not appear is the `RP-`.
    assert body["reference"].startswith("SR-")
    assert "RP-" not in str(body)


@pytest.mark.django_db
def test_us_cwp_010_tc6_a_pine_hill_reference_under_oak_ridge_is_not_found(
    pine_hill, sarah, oak_ridge, elena
):
    switch_on(pine_hill, sarah)
    switch_on(oak_ridge, elena)
    reference = _report(pine_hill).data["reference"]
    response = _track(oak_ridge, reference, "78702")
    assert response.status_code in (409, 422)
    assert response.data["message_key"] == "portal.track.notFound"


@pytest.mark.django_db
def test_us_cwp_010_tc7_the_payment_series_is_trackable_and_the_hold_is_spent(pine_hill, sarah):
    """⚠ **REWRITTEN 2026-09-05, EXACTLY AS THIS CASE SAID IT WOULD BE.**

    It used to assert the ABSENCE — *"a payment reference is refused
    IDENTICALLY to an unknown one"* — and its own docstring closed with *"this
    case is written so the day wave P lands it is rewritten to assert the
    lookup, rather than left quietly passing over an absence."* That day has
    come: `bill_lookup` has walked `account → premises → postcode` since wave P,
    so the reason the hold gave is spent and the tuple names the payment.

    **The full lookup lives in `tests/test_us_cwp_005_receipt.py`** with the
    rest of `US-CWP-005` TC-3 — the payment row, the postcode pair, the frozen
    key set, the tenant isolation and the refusal that is byte-identical to an
    unknown reference. What is asserted HERE is the boundary this file has
    always owned: which series a visitor may type.
    """
    from apps.portal import selectors

    switch_on(pine_hill, sarah)
    # ⚠ **TWO SERIES SINCE 2026-09-05, AND NEITHER IS THE `RP-`.** `"report"`
    # meant the `RP-` series, looked up on `interruptions` from an
    # unauthenticated endpoint; `CR-072` took it out and nothing hands an `RP-`
    # to a guest any more. A tracked REPORT still ANSWERS `series: "report"`,
    # which is the SHAPE the screen draws and not what a visitor may type.
    assert selectors.TRACKABLE_SERIES == ("request", "payment")

    # And a payment reference nobody issued is still refused identically to any
    # other miss — the boundary moved, the refusal did not (`TC-3`).
    response = _track(pine_hill, "PAY-26-08841", "78702")
    assert response.data["message_key"] == "portal.track.notFound"


@pytest.mark.django_db
def test_us_cwp_009_tc4_an_internal_routing_note_never_appears(pine_hill, sarah):
    """A clerk's note is `internal=True` on every row this product writes, and
    the tracked view serves no notes at all."""
    switch_on(pine_hill, sarah)
    reference = _report(pine_hill).data["reference"]
    request = service_request_service.models.ServiceRequest.objects.get(tenant_id=pine_hill.id)
    with tenant_context(pine_hill.id):
        service_request_service.add_note(sarah, request.id, note="route to Tuesday crew, low priority")
    body = _track(pine_hill, reference, "78702").data
    assert "Tuesday" not in str(body)
    assert "note" not in body and "notes" not in body


@pytest.mark.django_db
def test_us_cwp_010_the_second_fact_matches_a_phone_however_it_is_typed(pine_hill, sarah):
    """`(512) 555-7730` and `+1 512 555 7730` are one telephone."""
    switch_on(pine_hill, sarah)
    request = service_request_service.models.ServiceRequest
    reference = _report(pine_hill).data["reference"]
    for typed in ("(512) 555-7730", "+1 512 555 7730", "5557730"):
        assert _track(pine_hill, reference, typed).status_code == 200, typed
    assert request  # the import is used above; keeps ruff quiet without a noqa


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-010@d6d31c46 · US-CWP-009@d6d31c46 (EP-CWP-03 §3 cases)
# generated: 2026-09-04 by the CR-068 wave B build lane · AMENDED 2026-09-04 by the CR-072 lane (one reference, and it is the `SR-`; the report shape is served off `service_requests`). Every amended assertion names what it used to assert. · AMENDED 2026-09-05 by the CR-068 ending lane: TC-7 asserted the ABSENCE of the payment series and its own docstring said to rewrite it the day the lookup landed — it has, so it does.
# checklist: A✔ B✔ C✔ D✔ E=n/a(test file) F✔ G✔ H=n/a
# gates: pytest tests/test_us_cwp_010_track.py tests/test_us_cwp_005_receipt.py
# exceptions: TC-5 (six wrong pairs) is in tests/test_us_cwp_002_lockout.py with the rest of the lockout · TC-7's LOOKUP lives in tests/test_us_cwp_005_receipt.py with the rest of US-CWP-005 TC-3 (the payment row, the postcode pair, the frozen key set, the tenant isolation); what stays here is the boundary this file owns — which series a visitor may TYPE
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

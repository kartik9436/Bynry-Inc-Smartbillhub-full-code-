# ── Trace ──────────────────────────────────────────────
# Change:   CR-031 (PO 2026-08-24) · B19   Screens: REQ-01 · REQ-02 · REQ-03
# Rules:    BR-CUS-090 · BR-CUS-091 · BR-CUS-093 · BR-CUS-094 · BR-CUS-095 ·
#           BR-CUS-079 · BR-CUS-080 · BR-SHL-025 (server-enforced RBAC) ·
#           CLAUDE.md rules 2 (money) · 6 (idempotency) · 7 (audit)
# ───────────────────────────────────────────────────────
"""The service-request SURFACE — the half CR-031's backend shipped without.

**WHAT THIS FILE IS ACTUALLY GUARDING, and it is hard-won law 2.**
`apps/customers/service_request*.py` landed on 2026-08-24 as ~2,700 lines over
five tables and eleven states with **no route naming any of it**, so a clerk
could not raise a service request and the whole W4 frontend had nothing to call.
`config/urls.py` already records that exact defect five times over.

So **the first test resolves every path THROUGH THE ROOT URLCONF** — an `api.py`
exporting `urlpatterns` that `config/urls.py` never includes is not an endpoint,
and every other test in this file would pass on a module nobody could reach.

**THE NEGATIVE ASSERTIONS ARE THE POINT.** The easy way to make a surface green
is to answer everything plausibly. Each of these is a sentence about a real
person's money or identity that no row supports, so each is asserted the other
way:

  · an Executive's forged POST is refused **by the server**, not by a hidden
    button (A4 gives them VIEW);
  · a JSON FLOAT amount is REFUSED rather than coerced — `25.10` arrives as
    `25.099999999999998` and this is a counter taking somebody's cash (rule 2);
  · a shortfall at the counter is **stored**, not refused and not waived;
  · a second submit sends the customer NOTHING twice;
  · the checklist grid comes back with every cell UNTICKED.
"""

import re
from decimal import Decimal

import pytest
from django.urls import Resolver404, resolve
from django.utils import timezone

from apps.customers import models as customers_models
from apps.customers import service_request_api as api
from apps.customers import service_request_service as sr
from apps.payments import counters
from apps.tenancy import published_content_models as content_models
from tests.fee_quote_helpers import quote_fee  # DEF-CUS-6416: the catalogue prices the line

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

DOC_ID = customers_models.ServiceRequestDocument.DOC_PROOF_OF_IDENTITY

CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Okonkwo, David",
    "applicant_email": "david@example.test",
    "address_as_given": "14 Willow Bend, Springfield",
}

#: Every path this surface serves, as a REAL URL under the tenant mount.
SERVED_PATHS = (
    ("/api/brazos/service-requests", api.service_requests),
    ("/api/brazos/service-requests/categories", api.service_request_categories),
    ("/api/brazos/service-requests/abc", api.service_request_item),
    ("/api/brazos/service-requests/abc/submit", api.service_request_submit),
    ("/api/brazos/service-requests/abc/transitions", api.service_request_transition),
    ("/api/brazos/service-requests/abc/approve", api.service_request_approve),
    ("/api/brazos/service-requests/abc/refuse", api.service_request_refuse),
    ("/api/brazos/service-requests/abc/decision", api.service_request_decision),
    ("/api/brazos/service-requests/abc/park", api.service_request_park),
    ("/api/brazos/service-requests/abc/resume", api.service_request_resume),
    ("/api/brazos/service-requests/abc/notes", api.service_request_notes),
    ("/api/brazos/service-requests/abc/category", api.service_request_category),
    ("/api/brazos/service-requests/abc/services", api.service_request_services),
    ("/api/brazos/service-requests/abc/resolve-address", api.service_request_resolve_address),
    ("/api/brazos/service-requests/abc/customer-link", api.service_request_customer_link),
    ("/api/brazos/service-requests/abc/child-link", api.service_request_child_link),
    ("/api/brazos/service-requests/abc/documents", api.service_request_documents),
    (
        "/api/brazos/service-requests/abc/documents/d1/verify",
        api.service_request_document_verify,
    ),
    (
        "/api/brazos/service-requests/abc/documents/d1/reject",
        api.service_request_document_reject,
    ),
    ("/api/brazos/service-requests/abc/fees", api.service_request_fees),
    ("/api/brazos/service-requests/abc/fees/f1/waive", api.service_request_fee_waive),
    ("/api/brazos/service-requests/abc/fee-collection", api.service_request_fee_collection),
    (
        "/api/brazos/service-request-settings/document-requirements",
        api.service_request_document_requirements,
    ),
)


def _make(actor, **overrides):
    return sr.create_request(actor, {**CAPTURE, **overrides})


# ══════════════════════════════════════════════════════════════════════════
# 1 · IS IT WIRED AT ALL — the only question the morning lane could not answer
# ══════════════════════════════════════════════════════════════════════════
def test_every_service_request_path_resolves_through_the_root_urlconf():
    """**HARD-WON LAW 2.** A module exporting `urlpatterns` that `config/urls.py`
    never includes is dead code with a green test suite over it. This is the
    assertion that goes red if the include is lost."""
    for path, view in SERVED_PATHS:
        match = resolve(path)
        assert match.func is view, f"{path} resolved to {match.func!r}, not {view.__name__}"


def test_the_static_segments_are_not_swallowed_by_the_id_matcher():
    """`service-requests/categories` is all-static and MUST be declared above
    `service-requests/<request_id>` — the same trap `accounts/master` records in
    apps/customers/api.py. If it ever moves, the picker 404s."""
    assert resolve("/api/brazos/service-requests/categories").func is (
        api.service_request_categories
    )
    assert resolve("/api/brazos/service-requests/01a0-whatever").func is api.service_request_item


def test_no_route_promises_something_this_module_refuses():
    """A route that answers 501 is a promise. There is no fee-line REMOVAL
    endpoint (OQ-357), no identifier endpoint (BR-CUS-092(b)) and no automatic
    customer MATCHER (DEF-632/638 12.b) — none is stubbed."""
    for absent in (
        "/api/brazos/service-requests/abc/fees/f1/remove",
        "/api/brazos/service-requests/abc/identifier",
        "/api/brazos/service-requests/abc/customer-matches",
    ):
        with pytest.raises(Resolver404):
            resolve(absent)


# ══════════════════════════════════════════════════════════════════════════
# 2 · BR-CUS-093 — the 201 comes back NUMBERED
# ══════════════════════════════════════════════════════════════════════════
def test_creating_a_request_returns_its_number_and_a_location(brazos, dana):  # noqa: F811
    """*"At creation — every draft is numbered"*, and the number is what the
    clerk reads down the phone, so the 201 carries it."""
    response = api_call(
        api.service_requests,
        "post",
        "/api/brazos/service-requests",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data=CAPTURE,
    )
    assert response.status_code == 201
    assert response.data["header"]["request_no"]
    assert response.data["header"]["number_absence"] is None
    assert response["Location"].endswith(response.data["header"]["id"])


def test_a_second_submit_answers_two_hundred_and_sends_nothing_twice(brazos, dana):  # noqa: F811
    """BR-CUS-093 (e) over HTTP — a double-click at the counter."""
    with tenant_ctx(brazos):
        request = _make(dana)
    first = api_call(
        api.service_request_submit,
        "post",
        f"/api/brazos/service-requests/{request.id}/submit",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={},
        request_id=str(request.id),
    )
    second = api_call(
        api.service_request_submit,
        "post",
        f"/api/brazos/service-requests/{request.id}/submit",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={},
        request_id=str(request.id),
    )
    assert first.data["idempotent_replay"] is False
    assert second.data["idempotent_replay"] is True
    assert second.status_code == 200


def test_the_address_parts_are_captured_as_a_statement_and_are_not_the_service_address(
    brazos, dana  # noqa: F811
):
    """**PO ruling 2026-09-22 — `BR-CUS-1091`, reversing a refusal of 2026-09-15.**

    Verbatim: *"correct address will be on presmies but first time you will
    ahve to take the details to match it"*. A request that cannot take a city
    and a ZIP cannot find the premises it is about.

    ⚠ **THIS CASE GUARDS THE POSTURE AS HARD AS THE PLUMBING.** `BR-MET-1161`
    is NOT narrowed: an address is stored on `premises` and nowhere else, and
    these three columns are a record of WHAT A MEMBER OF THE PUBLIC SAID —
    which is why every one of them is spelled `_as_given`.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): an implementation that
    accepted a BARE `city` would satisfy *the parts are captured* and would be
    exactly the fourth home the rule forbids and `G85` refuses by name. So the
    bare spellings are asserted REFUSED, in the same breath as the `_as_given`
    ones are asserted stored.
    """
    from core import errors

    with tenant_ctx(brazos):
        request = _make(
            dana,
            address_city_as_given="Austin",
            address_state_as_given="TX",
            address_postal_code_as_given="78704",
        )
        stored = customers_models.ServiceRequest.objects.get(id=request.id)
        assert stored.address_city_as_given == "Austin"
        assert stored.address_state_as_given == "TX"
        assert stored.address_postal_code_as_given == "78704"
        # ⛔ **THE BARE SPELLINGS ARE STILL REFUSED BY NAME.** They are what the
        # 2026-09-15 near-miss actually was (`BR-CUS-1055`), and the ruling that
        # reversed the CAPTURE refusal left the STORAGE rule exactly where it
        # was.
        for bare in ("city", "state", "postal_code"):
            with pytest.raises(errors.ValidationError):
                _make(dana, **{bare: "Austin"})


def test_a_broken_response_builder_cannot_undo_a_committed_submit(brazos, dana, monkeypatch):  # noqa: F811
    """**`DEF-CUS-6178` — the endpoint DESCRIBES a submit and may never DENY it.**

    PO report 2026-09-22, priority 0: step 6 answered *"We could not submit this
    request / Something went wrong. Nothing was saved — try again."* **and the
    request was submitted.**

    `writes.submit` commits the state move, the timeline row, the audit row and
    the acknowledgement. The response is composed AFTERWARDS, from
    `reads.list_row`, and a raise there used to 500 — over work that stands.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY** (law 7): a version that returned 200
    while ALSO rolling the submit back would satisfy the status assertion and be
    a worse product. So the row is read back from the DATABASE and asserted
    `submitted`, and the payload is asserted to NAME that state — a caller that
    cannot see the state cannot tell the clerk the truth either.
    """
    with tenant_ctx(brazos):
        request = _make(dana)

    def explode(_row, **_kwargs):
        raise RuntimeError("the read model is broken and the state has moved")

    monkeypatch.setattr(api.reads, "list_row", explode)
    response = api_call(
        api.service_request_submit,
        "post",
        f"/api/brazos/service-requests/{request.id}/submit",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={},
        request_id=str(request.id),
    )
    assert response.status_code == 200
    assert response.data["request"]["state"] == "submitted"
    assert response.data["request"]["request_no"]
    with tenant_ctx(brazos):
        stored = customers_models.ServiceRequest.objects.get(id=request.id)
    assert stored.state == "submitted"
    assert stored.submitted_at is not None


# ══════════════════════════════════════════════════════════════════════════
# 3 · BR-CUS-094 — the picker offers seven and never the legacy code
# ══════════════════════════════════════════════════════════════════════════
def test_the_category_picker_offers_seven_and_lists_the_legacy_code_apart(
    brazos, dana
):  # noqa: F811,E501
    """The two lists are the ruling: `government` is unselectable and is still
    served, because it is still a valid FK on records that hold it and a screen
    filtering by it must be able to name it."""
    response = api_call(
        api.service_request_categories,
        "get",
        "/api/brazos/service-requests/categories",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    selectable = [row["code"] for row in response.data["selectable"]]
    assert selectable == [code for code, _ in customers_models.AccountType.SEVEN_CATEGORIES]
    assert [row["code"] for row in response.data["legacy"]] == ["government"]
    assert response.data["legacy"][0]["br_ref"] == "BR-CUS-094"


# ══════════════════════════════════════════════════════════════════════════
# 4 · BR-CUS-090 — money over HTTP
# ══════════════════════════════════════════════════════════════════════════
def test_a_json_float_amount_is_refused_rather_than_coerced(brazos, dana):  # noqa: F811
    """**CLAUDE.md rule 2.** By the time a JSON number reaches the view it is an
    IEEE double: `25.10` arrives as `25.099999999999998` and would be stored to
    four places as exactly that. This is a counter taking somebody's cash, so
    the refusal names the field instead."""
    with tenant_ctx(brazos):
        request = _make(dana)
        quote_fee(dana, request.id, charge_code="CC-REQFEE", unit_amount=Decimal("130.00"))
    response = api_call(
        api.service_request_fee_collection,
        "post",
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"amount": 25.10, "method": "cash", "receipt_no": "RCP-26-4471"},
        request_id=str(request.id),
    )
    # 422, the BE-02 handler's status for a VAL-* refusal in this product.
    assert response.status_code == 422
    assert response.data["code"] == "VAL-002"
    assert response.data["message_key"] == "customers.serviceRequest.moneyMustBeString"


def test_the_counter_shortfall_is_refused_and_the_whole_fee_is_served(brazos, dana):  # noqa: F811
    """**FLIPPED 2026-09-24 — `OQ-CUS-12624`, `DEF-CUS-6455`.** The worked case
    over the wire: $130.00 quoted, $25.00 offered → **422**, refused naming the
    whole $130.00 (PO: *"all or waived"*); then $130.00 taken → $0.00
    outstanding. It read *"$25.00 taken, $105.00 outstanding — and the request
    is not refused"*, BR-CUS-090's 2026-08-24 desk clause, superseded for
    application fees.

    ⚠ **DANA OPENS A TILL FIRST — `DEF-CUS-6374`, 2026-09-23.** Cash at this
    door is refused with no till open (PO ruling 2026-09-23 §3.4); that refusal
    is `test_def_cus_6376_request_fee_like_record_payment.py`'s to prove. This
    case is about the SHORTFALL, so it stands where a real clerk stands: with
    their counter open."""
    with tenant_ctx(brazos):
        request = _make(dana)
        for code, amount in (("CC-REQFEE", "25.00"), ("CC-EXPED", "60.00"), ("CC-METERT", "45.00")):
            quote_fee(dana, request.id, charge_code=code, unit_amount=Decimal(amount))
        centre = content_models.ServiceCentre.objects.create(
            tenant=brazos, slug="api-window", name="Main office", address="101 Bend Road"
        )
        counters.open_counter(
            dana,
            service_centre_id=centre.pk,
            opening_float=Decimal("0.0000"),
            opened_at=timezone.now(),
        )
    response = api_call(
        api.service_request_fee_collection,
        "post",
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"amount": "25.00", "method": "cash", "receipt_no": "RCP-26-4471"},
        request_id=str(request.id),
    )
    assert response.status_code == 422
    assert response.data["code"] == "BIZ-COMPLETENESS"
    assert response.data["message_key"] == "customers.serviceRequest.feeTakeInFull"
    assert response.data["params"]["amount"] == "130.0000"
    assert response.data["params"]["currency"] == "USD"
    response = api_call(
        api.service_request_fee_collection,
        "post",
        f"/api/brazos/service-requests/{request.id}/fee-collection",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        data={"amount": "130.00", "method": "cash", "receipt_no": "RCP-26-4471"},
        request_id=str(request.id),
    )
    assert response.status_code == 200
    assert response.data["quoted"]["display"] == "130.00"
    assert response.data["collected"]["display"] == "130.00"
    assert response.data["outstanding"]["display"] == "0.00"


# ══════════════════════════════════════════════════════════════════════════
# 5 · BR-CUS-095 — the checklist surface, System Admin only, shipped unticked
# ══════════════════════════════════════════════════════════════════════════
def test_the_checklist_grid_ships_with_every_cell_unticked(brazos, dana):  # noqa: F811
    """*"We ship with nothing ticked, and a utility that configures nothing
    blocks nothing."* The GRID is served so a box can be ticked for the first
    time; every cell is `configured: false`."""
    response = api_call(
        api.service_request_document_requirements,
        "get",
        "/api/brazos/service-request-settings/document-requirements",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
    )
    grid = response.data["requirements"]
    assert len(grid) == 40  # five job outcomes × eight designed types
    assert all(cell["required"] is False and cell["configured"] is False for cell in grid)
    assert response.data["ships_unticked"] is True


def test_a_billing_clerk_may_not_change_the_checklist(brazos, marcus):  # noqa: F811
    """It is a tenant SETTING — ticking `proof_of_identity` for `move_in`
    changes what every future approval demands — so it sits where the lookups
    and policy screens sit, not where the capture form does."""
    response = api_call(
        api.service_request_document_requirements,
        "put",
        "/api/brazos/service-request-settings/document-requirements",
        user=marcus.user,
        role="billing_clerk",
        tenant=brazos,
        data={"request_type": "move_in", "doc_type": DOC_ID, "required": True},
    )
    assert response.status_code == 403
    assert customers_models.ServiceRequestDocumentRequirement.objects.count() == 0


# ══════════════════════════════════════════════════════════════════════════
# 6 · RBAC — refused by the SERVER, never by a hidden button
# ══════════════════════════════════════════════════════════════════════════
#: ⚠ **WHY THE STRUCTURAL TEST BELOW EXISTS, AND IT IS A RED-PROOF FINDING.**
#: The two behavioural RBAC cases in this section were RED-PROVED like every
#: other guard here — the API-layer check was deleted and the test re-run — and
#: **both stayed GREEN**, because the SERVICE layer's own `@require_role`
#: refuses a moment later and returns the same 403.
#:
#: That is defence in depth working exactly as BR-SHL-025 intends, and it is
#: also a hole in the proof: a behavioural test cannot tell which of two layers
#: refused, so **deleting the outer one is invisible to it**. Losing the outer
#: layer is not harmless — it is what decides whether an unauthorised caller is
#: refused BEFORE their payload is parsed, and it is the layer a reviewer reads
#: first.
#:
#: So the declared permission classes are pinned structurally as well. Between
#: the two, removing either layer goes red. (Hard-won law 7: a check whose
#: output cannot distinguish pass from fail is worse than no check, because it
#: is trusted.)
EXPECTED_PERMISSIONS = {
    # A4: "Premises / Accounts — System Admin Full · Billing Clerk Full ·
    # Executive View". Reads are open to any tenant role; writes are AdminOrClerk.
    "service_requests": "AnyTenantRole",
    "service_request_categories": "AnyTenantRole",
    "service_request_item": "AnyTenantRole",
    "service_request_documents": "AnyTenantRole",
    "service_request_fees": "AnyTenantRole",
    "service_request_submit": "AdminOrClerk",
    "service_request_transition": "AdminOrClerk",
    "service_request_approve": "AdminOrClerk",
    "service_request_refuse": "AdminOrClerk",
    "service_request_decision": "AdminOrClerk",
    "service_request_park": "AdminOrClerk",
    "service_request_resume": "AdminOrClerk",
    "service_request_notes": "AdminOrClerk",
    "service_request_category": "AdminOrClerk",
    "service_request_services": "AdminOrClerk",
    "service_request_resolve_address": "AdminOrClerk",
    "service_request_customer_link": "AdminOrClerk",
    "service_request_child_link": "AdminOrClerk",
    "service_request_document_verify": "AdminOrClerk",
    "service_request_document_reject": "AdminOrClerk",
    "service_request_fee_waive": "AdminOrClerk",
    "service_request_fee_collection": "AdminOrClerk",
    # ⚠ THE ONE THAT IS DIFFERENT, AND IT IS BR-CUS-095. The checklist is a
    # tenant SETTING — ticking `proof_of_identity` for `move_in` changes what
    # every future approval of that job type demands — so it sits where the
    # lookups and policy screens sit, not where the capture form does.
    "service_request_document_requirements": "SystemAdminOnly",
}


def test_every_view_declares_the_permission_class_a4_gives_it():
    """The structural half of the RBAC proof — see the note above."""
    for name, expected in EXPECTED_PERMISSIONS.items():
        view = getattr(api, name)
        declared = [c.__name__ for c in view.cls.permission_classes]
        assert declared == [expected], f"{name} declares {declared}, expected [{expected}]"


def test_the_write_helper_refuses_an_executive_independently_of_the_service():
    """The API layer's OWN guard, called directly, so the service's
    `@require_role` cannot answer for it. This is what goes red if
    `_require_write_role` is emptied."""
    from types import SimpleNamespace

    from core import errors

    def _request(role):
        # `_role_of` reads the AUTHENTICATED user and the SERVER-ATTACHED role —
        # never client input (BE-04). Both halves are needed for the positive
        # branch to mean anything.
        return SimpleNamespace(
            tenant_role=role, user=SimpleNamespace(is_authenticated=True, id=None)
        )

    with pytest.raises(errors.AuthError) as caught:
        api._require_write_role(_request("executive"))
    assert caught.value.code == errors.AUTH_PERMISSION_DENIED
    # …and it lets the two roles A4 gives Full through, or the guard would be
    # passing for the wrong reason.
    for role in ("system_admin", "billing_clerk"):
        api._require_write_role(_request(role))
    # An unauthenticated caller has no role at all and is refused too.
    with pytest.raises(errors.AuthError):
        api._require_write_role(SimpleNamespace(tenant_role="system_admin", user=None))


def test_an_executive_may_read_the_list_and_may_not_create(brazos, dana):  # noqa: F811
    """A4: *"Premises / Accounts — System Admin Full · Billing Clerk Full ·
    Executive View"*. The list is open to all three roles; the forged POST is
    refused by the server (BR-SHL-025), and nothing is written."""
    with tenant_ctx(brazos):
        _make(dana)
    read = api_call(
        api.service_requests,
        "get",
        "/api/brazos/service-requests",
        user=dana.user,
        role="executive",
        tenant=brazos,
    )
    assert read.status_code == 200
    before = customers_models.ServiceRequest.objects.count()
    forged = api_call(
        api.service_requests,
        "post",
        "/api/brazos/service-requests",
        user=dana.user,
        role="executive",
        tenant=brazos,
        data=CAPTURE,
    )
    assert forged.status_code == 403
    assert customers_models.ServiceRequest.objects.count() == before


# ══════════════════════════════════════════════════════════════════════════
# 7 · THE DETAIL CARRIES WHAT THIS SURFACE CANNOT ANSWER
# ══════════════════════════════════════════════════════════════════════════
def test_the_detail_states_what_it_cannot_answer(brazos, dana):  # noqa: F811
    """A caller must never have to INFER an absence, and a reviewer must never
    have to take a docstring's word for it. Every open row this surface is
    blocked by is named in the payload with the question that will close it."""
    with tenant_ctx(brazos):
        request = _make(dana)
    response = api_call(
        api.service_request_item,
        "get",
        f"/api/brazos/service-requests/{request.id}",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        request_id=str(request.id),
    )
    codes = {row["code"] for row in response.data["unavailable"]}
    # ⚠ **NARROWED TWICE, AND THE SECOND TIME EMPTIED IT — DEF-632 (PO
    # 2026-08-27) then BR-CUS-092(a) FINISHED (PO 2026-09-15).** It asserted
    # `applicant_identifier_needs_an_encryptor`, then
    # `applicant_drivers_licence_not_captured`; the encryptor exists, the SSN
    # landed in August, and the date of birth and the driving licence landed on
    # 2026-09-15. **No identifier absence is declared on this surface any more**,
    # and the assertion is written in the negative so that re-adding one without
    # a reason goes red.
    assert "applicant_drivers_licence_not_captured" not in codes
    assert "applicant_identifier_needs_an_encryptor" not in codes
    # ⚠ **`fee_line_cannot_be_removed` LEFT ON 2026-09-23 (OQ-357 closed as
    # 'both').** A draft's line is removed through `DELETE …/fees/{fee_id}`, so
    # declaring the absence would now be false; written in the negative for the
    # same reason as the two above.
    assert "fee_line_cannot_be_removed" not in codes
    assert "fifth_approval_condition_unnamed" in codes
    refs = " ".join(row["br_ref"] for row in response.data["unavailable"])
    # ⚠ **`BR-CUS-092` LEFT THIS SET ON 2026-09-15 BECAUSE THE FACT ARRIVED, NOT
    # BECAUSE ANYBODY TIDIED.** It was the `br_ref` of the driving-licence entry
    # above, and that entry is retired: the licence is captured, encrypted and
    # served as its last four. What this line still guards is that every REMAINING
    # entry names the question that will close it.
    assert "BR-CUS-092" not in refs
    assert "OQ-355" in refs
    # ⚠ **AND THE PROVENANCE STAYS OUT OF THE SCREEN COPY (G28 / CR-016).** The
    # ids belong in `br_ref` and in the code comment beside each entry; a clerk
    # reading "OQ-357" learns nothing and we leak our own register.
    for row in response.data["unavailable"]:
        assert not re.search(r"\b(BR-[A-Z]{3}-\d+|OQ-\d+|DEF-\d+|US-[A-Z]{3}-\d+)\b", row["detail"])

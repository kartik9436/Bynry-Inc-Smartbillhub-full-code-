# ── Trace ──────────────────────────────────────────────
# Change:   CR-200-BRC10 lane B — S7 (public address suggestions), S8 (the
#           apartment, occupancy judged for THAT unit), S9 (portal requests
#           arrive linked to the premises and unit). T3 + T4.
# Defects:  DEF-CWP-10680 (apartment ignored; whole building judged) ·
#           DEF-CWP-10681 (portal requests arrive unlinked) · DEF-CWP-10682
#           (no suggestions)
# Rulings:  PO 2026-10-29 — 1A (after 4 characters, at most 5, street + town +
#           ZIP only, never a name or whether anyone lives there), 2A (pick
#           from the building's unit LABELS, judged for THAT unit), Ask us A
#           (same suggestions; a pick links the request; an unmatched address
#           is still accepted as typed)
# Rules:    BR-CWP-021 · B14 rule 31 · US-CWP-012 TC-2 · BR-CUS-070 · hard rule 1
# ───────────────────────────────────────────────────────
"""CR-200-BRC10 lane B on the suite, and on PostgreSQL with
`--ds=config.settings.pgtest`.

The street is Pine Hill's fixture street (`sample_data.seed_street` +
`seed_priced_addresses`): **1408 Elm St** holds units `A` (a live account),
`B` (empty) and `Common`; **31 Palm Ct** holds one unit. That is the PO's case
in miniature — *"today Apt 2B empty + Apt 1A occupied reads move-in"*.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a suggestion test
that only checked the street would pass over a body that also carried the
premises id, so the KEYS are asserted exactly; an occupancy test that asked
only the occupied unit would pass the old whole-building reading, so the EMPTY
unit is the assertion that matters; a cross-tenant test on an address only one
tenant holds proves nothing, so Oak Ridge is given the SAME street.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.customers import models as customers_models
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.portal import applications, availability, guest_api, sample_data
from apps.tenancy.api import PublicOnboardingThrottle
from core.tenancy import tenant_context
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

SUGGESTION_KEYS = {"street", "city", "state", "postal_code"}


def _suggest(tenant, q):
    return api_call(
        guest_api.address_suggestions,
        "get",
        f"/api/{tenant.subdomain}/portal/public/premises/suggestions",
        tenant=tenant,
        query={"q": q},
    )


def _availability(tenant, street, *, unit=None, city="Austin", postal_code="78702"):
    query = {"address": street, "city": city, "postal_code": postal_code}
    if unit is not None:
        query["unit"] = unit
    return api_call(
        guest_api.availability,
        "get",
        f"/api/{tenant.subdomain}/portal/public/premises/availability",
        tenant=tenant,
        query=query,
    )


def _ask(tenant, **body):
    return api_call(
        guest_api.quick_request,
        "post",
        f"/api/{tenant.subdomain}/portal/public/requests",
        tenant=tenant,
        data=body,
    )


@pytest.fixture()
def pine(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


# ═══════════════════════════════════════════════════════════════════════════
# T3 — the suggestion read
# ═══════════════════════════════════════════════════════════════════════════


def test_t3_four_characters_find_the_street_and_carry_street_town_zip_only(pine):
    response = _suggest(pine, "1408 Elm")
    assert response.status_code == 200
    [only] = response.data["suggestions"]
    assert only == {"street": "1408 Elm St", "city": "Austin", "state": "TX", "postal_code": "78702"}
    # The KEYS, exactly: no id, no premise number, no name, no unit, no occupancy.
    assert set(only) == SUGGESTION_KEYS
    flat = str(response.data)
    for forbidden in (sample_data.OCCUPIER_NAME, sample_data.OCCUPIER_PHONE, "Alvarez", "@", "id"):
        assert forbidden not in flat, forbidden
    with tenant_context(pine.id):
        premises = metering_models.Premises.objects.get(address_line="1408 Elm St")
    assert str(premises.id) not in flat and (premises.premise_no or "~") not in flat


def test_t3_under_four_characters_returns_nothing_and_is_not_a_refusal(pine):
    for typed in ("", "E", "Elm", " El ", "14 "):
        response = _suggest(pine, typed)
        assert response.status_code == 200
        assert response.data["suggestions"] == [], typed


def test_t3_every_word_must_match_street_town_or_zip(pine):
    """Word by word: street + town, street + ZIP, and a street word in its
    other spelling (`Street` for `St`)."""
    assert [row["street"] for row in _suggest(pine, "Elm Austin 1408").data["suggestions"]] == [
        "1408 Elm St"
    ]
    assert [row["street"] for row in _suggest(pine, "1408 Elm Street").data["suggestions"]] == [
        "1408 Elm St"
    ]
    assert {row["street"] for row in _suggest(pine, "palm 78702").data["suggestions"]} == {
        "22 Palm Ct",
        "31 Palm Ct",
    }
    assert _suggest(pine, "Elm Dallas").data["suggestions"] == []


def test_t3_at_most_five(pine, sarah):
    with tenant_context(pine.id):
        owner = sample_data._fixture_owner(sarah)
        for number in range(101, 108):
            metering_services.create_premises(
                sarah,
                {
                    "address_line": f"{number} Oak Ln",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78704",
                    "owner_id": owner,
                },
            )
    rows = _suggest(pine, "Oak Ln").data["suggestions"]
    assert len(rows) == 5
    assert [row["street"] for row in rows] == [f"{n} Oak Ln" for n in range(101, 106)]


def test_t3_another_utilitys_addresses_never_appear(pine, oak_ridge, elena):
    """Oak Ridge holds the SAME street spelling in another town, so the only
    thing keeping it off Pine Hill's list is the tenant scope."""
    switch_on(oak_ridge, elena)
    with tenant_context(oak_ridge.id):
        metering_services.create_premises(
            elena,
            {
                "address_line": "1408 Elm St",
                "city": "Oakville",
                "state": "CA",
                "postal_code": "94000",
                "owner_id": sample_data._fixture_owner(elena),
            },
        )
    pine_rows = _suggest(pine, "1408 Elm").data["suggestions"]
    assert [row["city"] for row in pine_rows] == ["Austin"]
    oak_rows = _suggest(oak_ridge, "1408 Elm").data["suggestions"]
    assert [row["city"] for row in oak_rows] == ["Oakville"]


def test_t3_rate_limited_like_every_public_read(pine):
    """The same two throttles as availability — and the sixty-first call in a
    minute from one address is refused."""
    assert guest_api.address_suggestions.cls.throttle_classes == (
        guest_api.availability.cls.throttle_classes
    )
    assert PublicOnboardingThrottle in guest_api.address_suggestions.cls.throttle_classes
    statuses = [_suggest(pine, "1408 Elm").status_code for _ in range(61)]
    assert statuses[:60] == [200] * 60
    assert statuses[60] == 429


# ═══════════════════════════════════════════════════════════════════════════
# T4 — the apartment, judged for THAT unit
# ═══════════════════════════════════════════════════════════════════════════


def test_t4_apt_b_empty_is_a_move_in_like_the_approve_window(pine):
    """PO 2026-10-30, ruling A (`DEF-CWP-10690`), verbatim: *"A, move-in"*.

    An apartment that is already in Premises is a MOVE-IN whether anybody lives
    there or not; a new connection is only an address NOT in Premises (the
    2026-09-23 and 2026-10-11 rulings the staff Approve window keeps). Lane B
    first built the opposite for the empty unit — B read `new_connection` —
    so the EMPTY apartment is the assertion that matters here."""
    empty = _availability(pine, "1408 Elm St", unit="B").data
    assert empty["matched"] is True
    assert empty["unit"] == "B"
    assert empty["job"] == "move_in"
    occupied = _availability(pine, "1408 Elm St", unit="A").data
    assert occupied["unit"] == "A" and occupied["job"] == "move_in"
    # Typed rather than picked, in another spelling, still means B.
    assert _availability(pine, "1408 Elm St", unit="Apt. b").data["job"] == "move_in"


def test_t4_a_building_with_several_units_lists_labels_only_and_waits_for_a_pick(pine):
    body = _availability(pine, "1408 Elm St").data
    assert body["units"] == ["A", "B", "Common"]
    assert all(isinstance(label, str) for label in body["units"])  # labels, nothing else
    assert body["unit"] is None and body["job"] is None
    # *Mine isn't listed* — a label we do not hold is no answer, never a refusal.
    other = _availability(pine, "1408 Elm St", unit="9Z")
    assert other.status_code == 200 and other.data["unit"] is None and other.data["job"] is None
    flat = str(body)
    for forbidden in (sample_data.OCCUPIER_NAME, sample_data.OCCUPIER_PHONE, "Alvarez", "@"):
        assert forbidden not in flat


def test_t4_an_empty_house_in_premises_is_a_move_in_too(pine):
    """Ruling A reaches the single-unit premises as well: `31 Palm Ct` is in
    Premises and nobody lives there, and the Approve window would grey *New
    connection* out for it — so the portal says move-in, not new connection."""
    body = _availability(pine, "31 Palm Ct").data
    assert body["units"] == [] and body["unit"] is None
    assert body["job"] == "move_in"


def test_t4_the_job_no_longer_needs_occupancy_so_the_guest_seam_has_none():
    """`BR-CWP-021` — the guest surface never names the occupier. Since ruling A
    the job is decided by PRESENCE in Premises, so whether anybody lives there
    no longer leaves the server at all: the two occupancy reads are gone from
    the portal's customers seam rather than kept unused."""
    from apps.portal.seams import customers_seam

    assert not hasattr(customers_seam, "unit_is_occupied")
    assert not hasattr(customers_seam, "premises_is_occupied")


def test_t4_the_figures_are_what_a_move_in_charges_not_every_one_time_code(pine, sarah):
    """`IF YOU APPLY` quotes the plan's MOVE-IN fees — `rating.move_in_fees`,
    the read the staff move-in's Fees table uses — so a one-time code the plan
    carries for COMMERCIAL customers only is not quoted to somebody moving into
    a home. The old connection-fee read quoted every one-time code: this one, at
    `$999.00`, landed in Sewer's *To connect* (an account-level code) and in
    *before we start*."""
    from apps.rating import models as rating_models
    from apps.rating import services as rating_services

    with tenant_context(pine.id):
        plan = rating_models.RatePlan.objects.get(code="PORTAL-RES")
        charge = rating_services.create_charge(
            sarah,
            {
                "code": "SETUP-COM",
                "name": "Commercial setup",
                "charge_type": "one_time",
                "amount_rule": "flat",
                "amount": "999.0000",
                "applies_to_customer_classes": ["commercial"],
                "effective_from": "2020-01-01",
            },
        )
        rating_models.PlanChargeRule.objects.create(
            tenant_id=pine.id, rate_plan_id=plan.id, charge_id=charge["id"], recurrence="once"
        )
    body = _availability(pine, "31 Palm Ct").data
    assert body["job"] == "move_in"
    assert "999" not in str(body)
    water = next(row for row in body["rows"] if row["service_code"] == "water")
    sewer = next(row for row in body["rows"] if row["service_code"] == "sewer")
    assert water["to_connect"]["display"] == "$185.00"
    assert sewer["to_connect"]["kind"] == "included"
    assert body["if_you_apply"]["before_we_start"]["display"] == "$185.00"
    assert body["if_you_apply"]["on_first_bill"]["display"] == "$150.00"


# ═══════════════════════════════════════════════════════════════════════════
# S9 — portal requests arrive linked
# ═══════════════════════════════════════════════════════════════════════════


def _request(tenant, request_id):
    with tenant_context(tenant.id):
        return customers_models.ServiceRequest.objects.get(pk=request_id)


def _unit(tenant, street, label):
    with tenant_context(tenant.id):
        return metering_models.Unit.objects.get(premises__address_line=street, label=label)


def test_s9_ask_us_a_picked_address_and_apartment_arrive_linked(pine):
    body = _ask(
        pine,
        category="re_read",
        name="Daniel Okafor",
        phone="(512) 555-7730",
        address="1408 Elm St, Austin, TX 78702",
        street="1408 Elm St",
        city="Austin",
        postal_code="78702",
        unit="B",
    ).data
    request = _request(pine, body["request_id"])
    unit_b = _unit(pine, "1408 Elm St", "B")
    assert str(request.resolved_unit_id) == str(unit_b.id)
    assert str(request.resolved_premises_id) == str(unit_b.premises_id)
    assert request.address_as_given == "1408 Elm St"
    assert request.address_unit_as_given == "B"


def test_s9_ask_us_an_unmatched_address_is_accepted_as_typed(pine):
    body = _ask(
        pine,
        category="re_read",
        name="Daniel Okafor",
        phone="(512) 555-7730",
        address="2155 Hemlok Dr",
    )
    assert body.status_code in (200, 201), body.data
    request = _request(pine, body.data["request_id"])
    assert request.address_as_given == "2155 Hemlok Dr"
    assert request.resolved_premises_id is None and request.resolved_unit_id is None


def test_s9_a_guest_still_cannot_name_a_premises_id(pine):
    """The server-resolved keyword is not a door a browser can use."""
    with tenant_context(pine.id):
        premises = metering_models.Premises.objects.get(address_line="1408 Elm St")
    body = _ask(
        pine,
        category="re_read",
        name="Daniel Okafor",
        phone="(512) 555-7730",
        address="77 Nowhere Ln",
        picked_premises_id=str(premises.id),
        resolved_place={"premises_id": str(premises.id)},
    )
    assert body.status_code in (200, 201), body.data
    request = _request(pine, body.data["request_id"])
    assert request.resolved_premises_id is None


def test_s9_place_for_links_the_only_unit_of_a_house_and_the_picked_one_of_a_building(pine):
    with tenant_context(pine.id):
        elm = metering_models.Premises.objects.get(address_line="1408 Elm St")
        palm = metering_models.Premises.objects.get(address_line="31 Palm Ct")
        palm_unit = metering_models.Unit.objects.get(premises_id=palm.id)
        unit_b = metering_models.Unit.objects.get(premises_id=elm.id, label="B")
        assert applications.place_for(pine.id, palm.id, None) == {
            "premises_id": str(palm.id),
            "unit_id": str(palm_unit.id),
        }
        assert applications.place_for(pine.id, elm.id, "B")["unit_id"] == str(unit_b.id)
        # *Mine isn't listed* — the premises only; the label stays as said.
        assert applications.place_for(pine.id, elm.id, "9Z") == {
            "premises_id": str(elm.id),
            "unit_id": None,
        }
        assert applications.place_for(pine.id, None, "B") is None


TOKEN = "c2000b00-5f6a-4b7c-8d9e-0f1a2b3c4d5e"


def test_s9_an_application_for_apt_b_arrives_linked_to_apt_b(pine):
    def call(fn, method, suffix, data):
        return api_call(
            fn,
            method,
            f"/api/{pine.subdomain}/portal/public/applications/{TOKEN}{suffix}",
            tenant=pine,
            data=data,
            token=TOKEN,
        )

    saved = call(
        guest_api.application_draft,
        "put",
        "",
        {
            "address_as_given": "1408 Elm St",
            "address_city_as_given": "Austin",
            "address_postal_code_as_given": "78702",
            "address_unit_as_given": "B",
            "service_codes": ["water"],
            "applicant_kind": "person",
            "first_name": "Kyle",
            "last_name": "Mark",
            "email": "kyle.mark@example.test",
            "phone": "(281) 555-0142",
            "account_type_code": "residential",
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
        },
    )
    assert saved.status_code == 200, saved.data
    sent = call(guest_api.submit_application, "post", "/submit", {"paperless": False})
    assert sent.status_code in (200, 201), sent.data
    with tenant_context(pine.id):
        request = customers_models.ServiceRequest.objects.get(request_no=sent.data["reference"])
    unit_b = _unit(pine, "1408 Elm St", "B")
    assert str(request.resolved_unit_id) == str(unit_b.id)
    assert str(request.resolved_premises_id) == str(unit_b.premises_id)
    assert request.address_unit_as_given == "B"

    # ⊕ Ruling A (`DEF-CWP-10690`) — the portal and the staff Approve window
    # AGREE: the portal said move-in for Apt B, and the window opened on the
    # request it sent greys *New connection* out with its reason.
    assert _availability(pine, "1408 Elm St", unit="B").data["job"] == "move_in"
    from apps.customers import service_request_reads as reads

    with tenant_context(pine.id):
        options = {row["outcome"]: row for row in reads.detail(request.id)["decision"]["options"]}
    assert options["new_connection"]["verdict"] == "not_possible"
    assert options["new_connection"]["message_key"] == "customers.serviceRequest.checkFact.addressInPremises"
    assert options["move_in"]["verdict"] != "not_possible"


def test_availability_signature_takes_the_unit():
    """The one read both screens call — the parameter exists and defaults off."""
    import inspect

    assert inspect.signature(availability.availability).parameters["unit"].default is None

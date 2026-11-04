"""CR-161-BRC10 wave W7 — the utility's own fields on the CUSTOMER PORTAL's
new-service form.

The PO's design, verbatim (Part 2 row 16): *"Portal new-service form
(applicant) · Staff Request detail · Customer → clerk · Off by default per
field; a utility turns each one on"*; the Rules table: *"One utility only —
Another utility never sees a utility's fields or answers, including on the
portal"* · *"Shown on the portal only when switched on — 'Ask the customer' is
off by default"* · *"Required means required only where it's typed in"*.

Worked example: *Roof Material* (Metal / Tile / Shingle) on Premises, switched
to *Ask the customer*. The applicant answers **Tile**; the request carries
Tile; Request detail shows it; Approve against a property already holding
**Metal** shows the W6 side-by-side pick.

RED FIRST (hard-won law 7), through pytest: run against the tip before the W7
code (`ccfd2bf5d`, a `git archive` copy) — the counts are in the CR file's W7
close.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (habit 2):
  * *"a Don't-ask field is not served"* passes if NO field is served — so every
    leak case first proves an asked field IS served in the same response;
  * *"another utility sees none of it"* passes if the other utility has no
    portal at all — so Oak Ridge is switched on, defines its OWN field, and is
    shown to see exactly that one;
  * *"the answer reaches the request"* passes on the response — so the request
    row is read back out of its own table;
  * *"an internal key is refused"* passes if every key is refused — so the
    same save carrying only the asked key is shown to succeed.

RUN WITH `JOBS_EAGER=false --reuse-db`.
"""

from __future__ import annotations

import json
from datetime import date, timedelta

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.portal import guest_api, models
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import services as tenancy_services
from core import errors
from core.tenancy import tenant_context
from tests.test_cr094_approval_raises_the_job import DOC_ID, _served_unit
from tests.test_us_cwp_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_helpers import brand_fully, seed_addresses_for, switch_on
from tests.test_us_met_helpers import brazos, dana, tenant_ctx  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

TOKEN = "c7f161a4-5f6a-4b7c-8d9e-0f1a2b3c4d5e"

COMPLETE = {
    "address_as_given": "31 Palm Ct",
    "service_codes": ["water"],
    "applicant_kind": "person",
    "first_name": "Amara",
    "last_name": "Okafor",
    "email": "amara.okafor@example.test",
    "phone": "(281) 555-0144",
    "account_type_code": "residential",  # DEF-CWP-9818 (required at Send)
}


def _field(actor, entity, label, placement, **over):
    payload = {"label": label, "entity": entity, "data_type": "text", **over}
    created = tenancy_services.create_custom_field(actor, payload)
    if placement:
        tenancy_services.save_custom_field_placement(actor, created["id"], placement)
    return created


def _roof(actor, placement=None, **over):
    return _field(
        actor,
        "premises",
        "Roof Material",
        placement if placement is not None else {"PORTAL_NEW_SERVICE": "input", "S16": "input"},
        data_type="select",
        options=["Metal", "Tile", "Shingle"],
        **over,
    )


@pytest.fixture()
def ready(pine_hill, sarah):
    switch_on(pine_hill, sarah)
    brand_fully(pine_hill, sarah)
    seed_addresses_for(pine_hill, sarah)
    return pine_hill


def _save(tenant, extra, token=TOKEN):
    return api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={
            **COMPLETE,
            "requested_start": (date.today() + timedelta(days=21)).isoformat(),
            **extra,
        },
        token=token,
    )


def _open(tenant, token=TOKEN):
    return api_call(
        guest_api.application_draft,
        "get",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        token=token,
    )


def _send(tenant, token=TOKEN):
    return api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data={"paperless": False},
        token=token,
    )


# ── 1 · the slot list ────────────────────────────────────────────────────────
def test_cr161_w7__the_portal_slot_is_rendered_for_the_three_intake_types():
    portal = {
        s.entity for s in cf_law.SLOTS if s.key == "PORTAL_NEW_SERVICE" and s.rendered
    }
    assert portal == {"customers", "accounts", "premises"}
    assert {s.wave for s in cf_law.SLOTS if not s.rendered} == set()


def test_cr161_w7__settings_accepts_ask_the_customer(ready, sarah):
    with tenant_context(ready.id):
        roof = _roof(sarah)
    assert roof["id"]
    with tenant_context(ready.id):
        from apps.tenancy import selectors as tenancy_selectors

        row = tenancy_selectors.custom_field_row(roof["id"])
    assert row["placement"]["PORTAL_NEW_SERVICE"] == "input"


# ── 2 · what the form is told ────────────────────────────────────────────────
def test_cr161_w7__the_draft_serves_only_asked_fields_and_only_their_public_shape(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah, help_text="What the roof is made of", is_required=True)
        # Don't ask: placed on a clerk screen only — the default for a portal.
        _field(sarah, "premises", "Meter vault code", {"S16": "input"})
        _field(sarah, "accounts", "Visit window", {"PORTAL_NEW_SERVICE": "input"})
        _field(sarah, "customers", "Credit note", {"S18": "input"})
    body = _save(ready, {}).data
    fields = body["custom_fields"]
    assert [f["key"] for f in fields["premises"]] == ["roof_material"]
    assert [f["key"] for f in fields["accounts"]] == ["visit_window"]
    assert fields["customers"] == []
    roof = fields["premises"][0]
    assert set(roof) == set(cf_law.PORTAL_PUBLIC_KEYS)
    assert roof == {
        "key": "roof_material",
        "label": "Roof Material",
        "help_text": "What the roof is made of",
        "data_type": "select",
        "options": ["Metal", "Tile", "Shingle"],
        "is_required": True,
    }
    wire = json.dumps(body)
    for leak in ("meter_vault_code", "Meter vault code", "credit_note", "placement", "S16"):
        assert leak not in wire, leak


def test_cr161_w7__a_new_field_is_off_the_portal_by_default(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah, placement={"S16": "input"})
        _field(sarah, "accounts", "Visit window", {"PORTAL_NEW_SERVICE": "input"})
    body = _save(ready, {}).data
    # Proved served in the SAME response: the leak check is not vacuous.
    assert [f["key"] for f in body["custom_fields"]["accounts"]] == ["visit_window"]
    assert body["custom_fields"]["premises"] == []
    assert "roof_material" not in json.dumps(body)


def test_cr161_w7__a_switched_off_field_is_not_served_and_its_answer_not_read_back(ready, sarah):
    with tenant_context(ready.id):
        roof = _roof(sarah)
    assert _save(ready, {"custom_data": {"premises": {"roof_material": "Tile"}}}).status_code == 200
    with tenant_context(ready.id):
        tenancy_services.set_custom_field_active(sarah, roof["id"], False)
    body = _open(ready).data
    assert body["custom_fields"]["premises"] == []
    assert body["custom_data"] == {}
    # Kept, not deleted (*"Can't be deleted, only switched off"*).
    with tenant_context(ready.id):
        assert models.PortalApplicationDraft.objects.get(token=TOKEN).custom_data == {
            "premises": {"roof_material": "Tile"}
        }


# ── 3 · what the form may send ───────────────────────────────────────────────
def test_cr161_w7__an_answer_is_saved_merged_and_read_back(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah)
        _field(sarah, "accounts", "Visit window", {"PORTAL_NEW_SERVICE": "input"})
    _save(ready, {"custom_data": {"premises": {"roof_material": "Tile"}}})
    body = _save(ready, {"custom_data": {"accounts": {"visit_window": "Mornings"}}}).data
    assert body["custom_data"] == {
        "premises": {"roof_material": "Tile"},
        "accounts": {"visit_window": "Mornings"},
    }


def test_cr161_w7__an_internal_field_cannot_be_written_from_the_portal(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah)
        _field(sarah, "premises", "Meter vault code", {"S16": "input"})
    refused = _save(
        ready, {"custom_data": {"premises": {"roof_material": "Tile", "meter_vault_code": "999"}}}
    )
    assert refused.status_code == 422, refused.data
    fields = [fe["field"] for fe in refused.data["field_errors"]]
    assert fields == ["custom_data.premises.meter_vault_code"]
    # The same refusal as a key that never existed — nothing tells the two apart.
    nonsense = _save(ready, {"custom_data": {"premises": {"no_such_field": "x"}}})
    assert nonsense.status_code == 422
    assert {fe["message_key"] for fe in nonsense.data["field_errors"]} == {
        fe["message_key"] for fe in refused.data["field_errors"]
    }
    # Proved the door is open for the asked key alone.
    assert _save(ready, {"custom_data": {"premises": {"roof_material": "Tile"}}}).status_code == 200


def test_cr161_w7__an_option_outside_the_list_is_refused_on_its_box(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah)
    refused = _save(ready, {"custom_data": {"premises": {"roof_material": "Thatch"}}})
    assert refused.status_code == 422
    assert [fe["field"] for fe in refused.data["field_errors"]] == [
        "custom_data.premises.roof_material"
    ]


def test_cr161_w7__a_record_type_outside_the_three_is_refused_by_name(ready, sarah):
    refused = _save(ready, {"custom_data": {"payments": {"x": "1"}}})
    assert refused.status_code == 422
    assert refused.data["params"]["field"] == "custom_data.payments"


# ── 4 · required, where it is typed in ───────────────────────────────────────
def test_cr161_w7__a_required_asked_field_lets_the_draft_save_and_holds_send(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah, is_required=True)
    assert _save(ready, {}).status_code == 200  # a draft is unfinished by definition
    held = _send(ready)
    assert held.status_code == 422, held.data
    assert held.data["message_key"] == "portal.application.stepIncomplete"
    assert held.data["params"]["step"] == "property_questions"
    with tenant_context(ready.id):
        assert customers_models.ServiceRequest.objects.count() == 0
    _save(ready, {"custom_data": {"premises": {"roof_material": "Tile"}}})
    assert _send(ready).status_code == 200


def test_cr161_w7__a_required_customer_field_names_the_about_you_step(ready, sarah):
    with tenant_context(ready.id):
        _field(sarah, "customers", "Preferred name", {"PORTAL_NEW_SERVICE": "input"}, is_required=True)
    held = _send_after_save(ready)
    assert held.data["params"]["step"] == "your_questions"


def _send_after_save(tenant):
    _save(tenant, {})
    return _send(tenant)


def test_cr161_w7__a_required_field_not_asked_on_the_portal_never_blocks_it(ready, sarah):
    with tenant_context(ready.id):
        _roof(sarah, placement={"S16": "input", "REQUEST_NEW": "input"}, is_required=True)
    sent = _send_after_save(ready)
    assert sent.status_code == 200, sent.data


# ── 5 · Send: the request's own copy ─────────────────────────────────────────
def test_cr161_w7__on_send_the_answers_land_on_the_requests_copy(ready, sarah, audit_rows):
    with tenant_context(ready.id):
        _roof(sarah)
        _field(sarah, "accounts", "Visit window", {"PORTAL_NEW_SERVICE": "input"})
    _save(
        ready,
        {
            "custom_data": {
                "premises": {"roof_material": "Tile"},
                "accounts": {"visit_window": "Mornings"},
            }
        },
    )
    sent = _send(ready)
    assert sent.status_code == 200, sent.data
    with tenant_context(ready.id):
        row = customers_models.ServiceRequest.objects.get(pk=sent.data["request_id"])
        assert row.custom_data == {
            "premises": {"roof_material": "Tile"},
            "accounts": {"visit_window": "Mornings"},
        }
        # Request detail serves the request's copy (gap 2).
        assert reads.detail(row.id)["custom_data"]["premises"] == {"roof_material": "Tile"}
    created = [r for r in audit_rows if r["action"] == "service_request.created_from_portal"]
    assert created and created[-1]["after"]["custom_data"]["premises"] == {"roof_material": "Tile"}


def test_cr161_w7__a_field_switched_to_dont_ask_after_it_was_typed_does_not_travel(ready, sarah):
    with tenant_context(ready.id):
        roof = _roof(sarah)
        _field(sarah, "accounts", "Visit window", {"PORTAL_NEW_SERVICE": "input"})
    _save(
        ready,
        {"custom_data": {"premises": {"roof_material": "Tile"}, "accounts": {"visit_window": "Noon"}}},
    )
    with tenant_context(ready.id):
        tenancy_services.save_custom_field_placement(sarah, roof["id"], {"S16": "input"})
    sent = _send(ready)
    assert sent.status_code == 200
    with tenant_context(ready.id):
        row = customers_models.ServiceRequest.objects.get(pk=sent.data["request_id"])
    assert row.custom_data == {"accounts": {"visit_window": "Noon"}}


def test_cr161_w7__no_fields_sends_exactly_as_before(ready):
    body = _save(ready, {}).data
    assert body["custom_fields"] == {"customers": [], "accounts": [], "premises": []}
    assert body["custom_data"] == {}
    sent = _send(ready)
    assert sent.status_code == 200
    with tenant_context(ready.id):
        assert customers_models.ServiceRequest.objects.get(
            pk=sent.data["request_id"]
        ).custom_data == {}


# ── 6 · one utility only ─────────────────────────────────────────────────────
def test_cr161_w7__another_utility_sees_only_its_own_fields_and_not_the_draft(
    ready, sarah, oak_ridge, elena
):
    with tenant_context(ready.id):
        _roof(sarah)
    _save(ready, {"custom_data": {"premises": {"roof_material": "Tile"}}})
    switch_on(oak_ridge, elena)
    with tenant_context(oak_ridge.id):
        _field(elena, "premises", "Well depth", {"PORTAL_NEW_SERVICE": "input"})
    # Oak Ridge cannot open Pine Hill's draft…
    assert _open(oak_ridge).status_code == 404
    # …and its own form names only its own field.
    other = _save(oak_ridge, {"address_as_given": "9 Oak Ave"}, token="c7f161b5-6a7b-4c8d-9e0f-1a2b3c4d5e6f")
    assert [f["key"] for f in other.data["custom_fields"]["premises"]] == ["well_depth"]
    wire = json.dumps(other.data)
    assert "roof_material" not in wire and "Roof Material" not in wire and "Tile" not in wire
    # Nor can it write Pine Hill's key into its own draft.
    refused = _save(
        oak_ridge,
        {"custom_data": {"premises": {"roof_material": "Tile"}}},
        token="c7f161b5-6a7b-4c8d-9e0f-1a2b3c4d5e6f",
    )
    assert refused.status_code == 422


# ── 7 · the customers door judges again ──────────────────────────────────────
def test_cr161_w7__the_portal_door_refuses_an_internal_key_even_called_directly(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "premises", "Meter vault code", {"S16": "input"})
        with pytest.raises(errors.ValidationError) as caught:
            sr.create_from_portal(
                {
                    "applicant_name": "Okafor, Amara",
                    "applicant_phone": "281-555-0144",
                    "address_as_given": "212 Balcones Drive",
                },
                custom_data={"premises": {"meter_vault_code": "999"}},
            )
        assert [fe["field"] for fe in caught.value.field_errors] == ["custom_data.meter_vault_code"]
        assert customers_models.ServiceRequest.objects.count() == 0


def test_cr161_w7__approve_copies_the_portal_answer_with_the_side_by_side_pick(
    brazos, dana, audit_rows
):
    """The PO's worked example end to end on the staff side: the property holds
    **Metal**, the applicant answered **Tile** on the portal; the review shows
    both with Existing pre-selected; picking Requested writes Tile."""
    with tenant_ctx(brazos):
        _roof(dana, placement={"PORTAL_NEW_SERVICE": "input", "REQUEST_DETAIL": "view"})
        premises, unit = _served_unit(dana, brazos, address="1408 Elm Street", label="Unit B")
        metering_services.update_premises(
            dana, premises["id"], {"custom_data": {"roof_material": "Metal"}}, custom_fields_screen=None
        )
        request = sr.create_from_portal(
            {
                "applicant_name": "Okafor, Amara",
                "applicant_phone": "281-555-0144",
                "address_as_given": str(unit["unit_no"]),
            },
            custom_data={"premises": {"roof_material": "Tile"}},
        )
        doc = sr.attach_document(
            dana, request.id, doc_type=DOC_ID, name="licence.pdf", storage_ref="s3://id"
        )
        sr.resolve_address(dana, request.id)
        sr.link_customer(dana, request.id, customer_id=None, tier=None)
        sr.decide_outcome(dana, request.id, outcome="move_in")
        sr.verify_document(dana, doc.id)
        # DEF-CUS-10251 (PO 2026-10-18) — a portal request carries no category
        # and staff set it before approving; Approve refuses without one.
        sr.set_customer_category(dana, request.id, account_type_code="residential")
        blocks = {b["entity"]: b for b in reads.detail(request.id)["custom_field_copy"]}
        row = blocks["premises"]["rows"][0]
        assert (row["existing"], row["requested"], row["state"], row["default_pick"]) == (
            "Metal",
            "Tile",
            "conflict",
            "existing",
        )
        sr.approve_and_raise(
            dana, request.id, custom_field_picks={"premises": {"roof_material": "requested"}}
        )
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data == {
            "roof_material": "Tile"
        }
    copied = [r for r in audit_rows if r["action"] == "service_request.custom_fields_copied"]
    assert copied[-1]["after"]["picks"] == {"premises": {"roof_material": "requested"}}


# ── 8 · the column, on PostgreSQL ────────────────────────────────────────────
@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="the database default is PostgreSQL DDL"
)
def test_cr161_w7__the_draft_column_is_not_null_with_an_empty_object_default():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'portal_application_drafts' AND column_name = 'custom_data'"
        )
        nullable, default = cursor.fetchone()
    assert nullable == "NO"
    assert default.startswith("'{}'::jsonb")

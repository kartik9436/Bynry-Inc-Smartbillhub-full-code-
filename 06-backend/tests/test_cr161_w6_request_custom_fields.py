"""CR-161-BRC10 wave W6 — the utility's own fields on the STAFF New Request,
read-only on Request detail, and COPIED to the real records on approval with
R5's side-by-side pick.

The PO's worked example, verbatim from the agreed design (gap 3, RULED C):
*"Existing: Metal · Requested: Tile side by side; the EXISTING value is
pre-selected; the clerk picks; the choice is audited; a key with no existing
value is copied"*.

RED FIRST (hard-won law 7), through pytest — the harness that runs these:
every case below was run against `2.462.0` before the W6 code and failed on
the product as it stood (`customers.serviceRequest.fieldNotAccepted` for
`custom_data`, `slot_not_rendered` for the two screens, no `custom_field_copy`
on the detail, nothing copied on approval). The mutation reds are listed in
the CR file's W6 close.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (habit 2): an assertion on the
approval RESPONSE rather than the record — so every copy case reads the
premises, customer and account back out of their own tables; a premises that
held nothing — so the conflict case writes *Metal* first through metering's own
door and proves it is there before approving; and a default that happens to
equal the pick — so the keep and the overwrite are two cases on one fixture.
"""

import pytest
from django.db import connection

from apps.customers import models as customers_models
from apps.customers import request_custom_fields as rcf
from apps.customers import service_request as rules
from apps.customers import service_request_reads as reads
from apps.customers import service_request_service as sr
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_cr094_approval_raises_the_job import (
    CAPTURE,
    _occupant,
    _request_ready_to_approve,
    _served_unit,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _field(actor, entity, label, placement, **over):
    payload = {"label": label, "entity": entity, "data_type": "text", **over}
    created = tenancy_services.create_custom_field(actor, payload)
    if placement:
        tenancy_services.save_custom_field_placement(actor, created["id"], placement)
    return created


def _roof(actor, **over):
    return _field(
        actor,
        "premises",
        "Roof Material",
        {"REQUEST_NEW": "input", "REQUEST_DETAIL": "view"},
        data_type="select",
        options=["Metal", "Tile", "Shingle"],
        **over,
    )


def _rows(audit_rows, action, entity_id=None):
    """The `audit_rows` CAPTURE SINK, not `AuditLog`: the shared fixture
    replaces the platform sink with a list, so a table query finds nothing
    (`test_cr094_approval_raises_the_job.test_every_raise_writes_an_audit_row`)."""
    return [
        r
        for r in audit_rows
        if r["action"] == action and (entity_id is None or str(r["entity_id"]) == str(entity_id))
    ]


def _one(rows):
    assert len(rows) == 1, rows
    return rows[0]


def _fields_of(caught):
    return [row["field"] for row in caught.value.field_errors]


def _transfer_world(actor, tenant, *, premises_answers=None, account_answers=None):
    """A request whose three targets all EXIST: the linked customer, the
    account that customer holds at the picked unit, and the picked premises."""
    premises, unit = _served_unit(actor, tenant, address="1408 Elm Street", label="Unit B")
    account = _occupant(actor, unit, name="Tan, Wei")
    customer_id = customers_models.CustomerAccount.objects.get(account_id=account["id"]).customer_id
    if premises_answers:
        metering_services.update_premises(
            actor, premises["id"], {"custom_data": premises_answers}, custom_fields_screen=None
        )
    if account_answers:
        customers_models.Account.objects.filter(pk=account["id"]).update(
            custom_data=account_answers
        )
    request = _request_ready_to_approve(
        actor, outcome="transfer", address=str(unit["unit_no"]), customer_id=customer_id
    )
    return premises, account, customer_id, request


# ── 1 · the slot list ────────────────────────────────────────────────────────
def test_cr161_w6__the_request_screens_are_rendered_for_the_three_intake_types():
    mine = {(s.entity, s.key, s.rendered) for s in cf_law.SLOTS if s.wave == "W6"}
    assert mine == {
        ("accounts", "REQUEST_NEW", True),
        ("accounts", "REQUEST_DETAIL", True),
        ("customers", "REQUEST_NEW", True),
        ("customers", "REQUEST_DETAIL", True),
        ("premises", "REQUEST_NEW", True),
        ("premises", "REQUEST_DETAIL", True),
    }


def test_cr161_w6__settings_accepts_staff_new_request_and_request_detail(brazos, dana):
    with tenant_ctx(brazos):
        roof = _roof(dana)
        stored = tenancy_services.save_custom_field_placement(
            dana, roof["id"], {"REQUEST_NEW": "input", "REQUEST_DETAIL": "view"}
        )
        assert stored["placement"] == {"REQUEST_NEW": "input", "REQUEST_DETAIL": "view"}


# ── 2 · capture: the request's own copy ──────────────────────────────────────
def test_cr161_w6__a_new_request_stores_each_record_types_answers(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        request = sr.create_request(
            dana,
            {
                **CAPTURE,
                "custom_data": {
                    "premises": {"roof_material": "Tile"},
                    "accounts": {"visit_window": "Mornings"},
                },
            },
        )
        row = sr.request_row(request.id)
        assert row.custom_data == {
            "premises": {"roof_material": "Tile"},
            "accounts": {"visit_window": "Mornings"},
        }


def test_cr161_w6__an_option_outside_the_list_and_an_unknown_key_are_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        with pytest.raises(errors.ValidationError) as bad_option:
            sr.create_request(
                dana, {**CAPTURE, "custom_data": {"premises": {"roof_material": "Straw"}}}
            )
        assert _fields_of(bad_option) == ["custom_data.roof_material"]
        with pytest.raises(errors.ValidationError) as unknown:
            sr.create_request(dana, {**CAPTURE, "custom_data": {"premises": {"colour": "Red"}}})
        assert _fields_of(unknown) == ["custom_data.colour"]
        with pytest.raises(errors.ValidationError) as wrong_type:
            sr.create_request(dana, {**CAPTURE, "custom_data": {"invoices": {"x": "1"}}})
        assert wrong_type.value.params == {"field": "custom_data.invoices"}


def test_cr161_w6__an_edit_merges_into_the_requests_copy_and_leaves_other_types_alone(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "premises", "Gate code", {"REQUEST_NEW": "input"})
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        request = sr.create_request(
            dana,
            {
                **CAPTURE,
                "custom_data": {
                    "premises": {"roof_material": "Tile", "gate_code": "4471"},
                    "accounts": {"visit_window": "Mornings"},
                },
            },
        )
        # One key of one record type: its sibling key and the other type stay.
        sr.update_request(
            dana, request.id, {"custom_data": {"premises": {"roof_material": "Metal"}}}
        )
        assert sr.request_row(request.id).custom_data == {
            "premises": {"roof_material": "Metal", "gate_code": "4471"},
            "accounts": {"visit_window": "Mornings"},
        }
        sr.update_request(dana, request.id, {"custom_data": {"accounts": {"visit_window": None}}})
        assert sr.request_row(request.id).custom_data == {
            "premises": {"roof_material": "Metal", "gate_code": "4471"}
        }


def test_cr161_w6__required_on_staff_new_request_lets_a_draft_save_and_stops_the_submit(
    brazos, dana
):
    with tenant_ctx(brazos):
        _roof(dana, is_required=True)
        request = sr.create_request(dana, CAPTURE)  # a draft: unfinished by definition
        with pytest.raises(errors.ValidationError) as caught:
            sr.submit(dana, request.id)
        assert _fields_of(caught) == ["custom_data.roof_material"]
        assert sr.request_row(request.id).state == rules.DRAFT
        sr.update_request(
            dana, request.id, {"custom_data": {"premises": {"roof_material": "Tile"}}}
        )
        sr.submit(dana, request.id)
        assert sr.request_row(request.id).state == rules.SUBMITTED


def test_cr161_w6__a_required_field_typed_elsewhere_never_blocks_the_request(brazos, dana):
    """*"Required means required only where it's typed in"* — placed on Edit
    premise only, it is nothing Staff New Request asks for."""
    with tenant_ctx(brazos):
        _field(
            dana,
            "premises",
            "Roof Material",
            {"PREMISE_EDIT": "input"},
            data_type="select",
            options=["Metal", "Tile"],
            is_required=True,
        )
        request = sr.create_request(dana, CAPTURE)
        sr.submit(dana, request.id)
        assert sr.request_row(request.id).state == rules.SUBMITTED


# ── 3 · Request detail: gap 2, and the review's rows ─────────────────────────
def test_cr161_w6__the_detail_serves_the_requests_copy_and_what_approval_would_do(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        _field(dana, "customers", "Loyalty tier", {"REQUEST_NEW": "input"})
        premises, account, customer_id, request = _transfer_world(
            dana, brazos, premises_answers={"roof_material": "Metal"}
        )
        customers_models.Customer.objects.filter(pk=customer_id).update(
            custom_data={"loyalty_tier": "Gold"}
        )
        sr.update_request(
            dana,
            request.id,
            {
                "custom_data": {
                    "premises": {"roof_material": "Tile"},
                    "accounts": {"visit_window": "Mornings"},
                    "customers": {"loyalty_tier": "Gold"},
                }
            },
        )
        detail = reads.detail(request.id)
        assert detail["custom_data"]["premises"] == {"roof_material": "Tile"}
        blocks = {block["entity"]: block for block in detail["custom_field_copy"]}
        assert [b["entity"] for b in detail["custom_field_copy"]] == [
            "customers",
            "accounts",
            "premises",
        ]
        roof = blocks["premises"]["rows"][0]
        assert (roof["state"], roof["existing"], roof["requested"], roof["default_pick"]) == (
            "conflict",
            "Metal",
            "Tile",
            "existing",
        )
        assert blocks["premises"]["target"] == {"label": premises["premise_no"]}
        assert blocks["accounts"]["rows"][0]["state"] == "copy"
        assert blocks["accounts"]["target"] == {"label": account["account_no"]}
        assert blocks["customers"]["rows"][0]["state"] == "same"


# ── 4 · approval: R5 ─────────────────────────────────────────────────────────
def test_cr161_w6__approval_keeps_the_existing_value_when_the_clerk_does_not_pick(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        premises, account, _customer, request = _transfer_world(
            dana, brazos, premises_answers={"roof_material": "Metal"}
        )
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data == {
            "roof_material": "Metal"
        }
        sr.update_request(
            dana,
            request.id,
            {
                "custom_data": {
                    "premises": {"roof_material": "Tile"},
                    "accounts": {"visit_window": "Mornings"},
                }
            },
        )
        sr.approve_and_raise(dana, request.id)
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data == {
            "roof_material": "Metal"
        }
        # A key with no existing value IS copied.
        assert customers_models.Account.objects.get(pk=account["id"]).custom_data == {
            "visit_window": "Mornings"
        }
        # The request's own copy is never touched.
        assert sr.request_row(request.id).custom_data["premises"] == {"roof_material": "Tile"}
        row = _one(_rows(audit_rows, "service_request.custom_fields_copied", request.id))
        assert row["after"]["kept"] == {"premises": {"roof_material": "Metal"}}
        assert row["after"]["copied"]["accounts"]["values"] == {"visit_window": "Mornings"}


def test_cr161_w6__approval_writes_the_requested_value_when_the_clerk_picks_it(
    brazos, dana, audit_rows
):
    with tenant_ctx(brazos):
        _roof(dana)
        premises, _account, _customer, request = _transfer_world(
            dana, brazos, premises_answers={"roof_material": "Metal"}
        )
        sr.update_request(
            dana, request.id, {"custom_data": {"premises": {"roof_material": "Tile"}}}
        )
        sr.approve_and_raise(
            dana, request.id, custom_field_picks={"premises": {"roof_material": "requested"}}
        )
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data == {
            "roof_material": "Tile"
        }
        row = _one(_rows(audit_rows, "service_request.custom_fields_copied", request.id))
        assert row["before"] == {"premises": {"roof_material": "Metal"}}
        assert row["after"]["picks"] == {"premises": {"roof_material": "requested"}}
        assert row["after"]["copied"]["premises"]["values"] == {"roof_material": "Tile"}
        # metering wrote its own audit row through its own door.
        assert _rows(audit_rows, "premises.updated", premises["id"])


def test_cr161_w6__a_bad_pick_is_refused_and_the_request_stays_unapproved(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        _premises, _account, _customer, request = _transfer_world(
            dana, brazos, premises_answers={"roof_material": "Metal"}
        )
        sr.update_request(
            dana, request.id, {"custom_data": {"premises": {"roof_material": "Tile"}}}
        )
        with pytest.raises(errors.ValidationError):
            sr.approve_and_raise(
                dana, request.id, custom_field_picks={"premises": {"roof_material": "both"}}
            )
        assert sr.request_row(request.id).state != rules.APPROVED


def test_cr161_w6__a_new_applicant_has_no_customer_or_account_yet_and_the_premises_is_copied(
    brazos, dana, audit_rows
):
    """A move-in by somebody not on file: the property exists and takes the
    answer; the customer and account do not exist yet, so theirs stay on the
    request (`no_target`, `DEF-CUS-9211`) — and the OCCUPIER's account is never
    written, whoever occupies the unit."""
    with tenant_ctx(brazos):
        _roof(dana)
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        premises, unit = _served_unit(dana, brazos, address="77 Oak Lane", label="Unit 1")
        request = _request_ready_to_approve(dana, outcome="move_in", address=str(unit["unit_no"]))
        sr.update_request(
            dana,
            request.id,
            {
                "custom_data": {
                    "premises": {"roof_material": "Shingle"},
                    "accounts": {"visit_window": "Noon"},
                }
            },
        )
        blocks = {b["entity"]: b for b in reads.detail(request.id)["custom_field_copy"]}
        assert blocks["accounts"]["target"] is None
        assert blocks["accounts"]["rows"][0]["state"] == "no_target"
        assert blocks["premises"]["rows"][0]["state"] == "copy"
        sr.approve_and_raise(dana, request.id)
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data == {
            "roof_material": "Shingle"
        }
        row = _one(_rows(audit_rows, "service_request.custom_fields_copied", request.id))
        assert row["after"]["waiting"] == {"accounts": ["visit_window"]}


def test_cr161_w6__the_occupiers_account_is_never_the_applicants_target(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "accounts", "Visit window", {"REQUEST_NEW": "input"})
        _premises, unit = _served_unit(dana, brazos, address="1408 Elm Street", label="Unit B")
        occupier = _occupant(dana, unit, name="Tan, Wei")
        request = sr.create_request(
            dana, {**CAPTURE, "custom_data": {"accounts": {"visit_window": "Noon"}}}
        )
        sr.update_request(
            dana,
            request.id,
            {"picked_premises_id": str(_premises["id"]), "picked_unit_id": str(unit["id"])},
        )
        assert rcf.targets(sr.request_row(request.id))["accounts"] is None
        assert customers_models.Account.objects.get(pk=occupier["id"]).custom_data in ({}, None)


def test_cr161_w6__a_field_switched_off_since_is_not_copied_and_stays_on_the_request(brazos, dana):
    with tenant_ctx(brazos):
        roof = _roof(dana)
        premises, _account, _customer, request = _transfer_world(dana, brazos)
        sr.update_request(
            dana, request.id, {"custom_data": {"premises": {"roof_material": "Tile"}}}
        )
        tenancy_services.set_custom_field_active(dana, roof["id"], False)
        assert reads.detail(request.id)["custom_field_copy"] == []
        sr.approve_and_raise(dana, request.id)
        assert metering_models.Premises.objects.get(pk=premises["id"]).custom_data in ({}, None)
        assert sr.request_row(request.id).custom_data == {"premises": {"roof_material": "Tile"}}


def test_cr161_w6__a_utility_with_no_fields_approves_exactly_as_before(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        _premises, _account, _customer, request = _transfer_world(dana, brazos)
        assert reads.detail(request.id)["custom_field_copy"] == []
        out = sr.approve_and_raise(dana, request.id)
        assert out["request"].state == rules.APPROVED
        assert not _rows(audit_rows, "service_request.custom_fields_copied")


def test_cr161_w6__another_utility_sees_none_of_the_fields(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        _roof(dana)
    with tenant_ctx(lonestar):
        assert rcf.seams.custom_field_definitions("premises") == []


# ── 5 · the column, on PostgreSQL ────────────────────────────────────────────
@pytest.mark.skipif(
    connection.vendor != "postgresql", reason="the database default is PostgreSQL DDL"
)
def test_cr161_w6__the_column_is_not_null_with_an_empty_object_default():
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT is_nullable, column_default FROM information_schema.columns "
            "WHERE table_name = 'service_requests' AND column_name = 'custom_data'"
        )
        nullable, default = cursor.fetchone()
    assert nullable == "NO"
    assert default.startswith("'{}'::jsonb")

"""`DEF-CUS-9211` — the utility's own fields typed on a service request reach
the records a LATER step creates from that request.

`CR-161-BRC10` W6 copies a request's answers on approval, but only onto records
that exist at that moment. Approving raises work and opens nothing, so a
first-time applicant's customer and account, and the premises of a brand-new
address, did not exist yet — their answers stayed on the request for ever. The
PO's three input routes (decision log 2026-10-02, *"SEU TEST MAPPING"*) require
that what a customer types on the portal reaches the Account and the Premises.

The fix carries them at the moment the record is created FROM THE REQUEST:

  * the move-in that opens the applicant's account (`service_request_id` on the
    move-in payload) — customers and accounts answers;
  * an owner's account opened for a request (`create_master_account`,
    `create_build_owner_account`) — customers and accounts answers;
  * the New Connection commit for a build raised from the request — the
    build's premises.

W6's rules hold: only ACTIVE fields of that record type and that utility, each
value through the owning module's validator, and **an answer already on the
target is never overwritten** — it is kept and the audit row says so. One
`service_request.custom_fields_carried` audit row per carry.

RED FIRST (hard-won law 7): every case except the regression guards was run
against `2.467.0` before the fix and failed — the account, customer and premises
read back with no answer at all.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (habit 2): asserting on a response
rather than the table — every case reads the record back out of its own table;
a target that holds nothing — so the keep case types a value on the account in
the move-in itself and proves it survives; a copy onto the wrong person — so the
owner case opens the account for somebody other than the request's customer and
proves nothing moved.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.customers import request_custom_fields as rcf
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import models as metering_models
from apps.portal import guest_api
from apps.tenancy import services as tenancy_services
from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    OPENED,
    _apply,
    _approve,
    _build,
    _ctx,
    _person_block,
    _served_premises,
    _unit_move_in,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam
from tests.test_us_met_helpers import brazos, dana, staff_actor  # noqa: F401
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

CARRIED = "service_request.custom_fields_carried"


def _admin(tenant):
    return staff_actor(tenant, "system_admin", "rae@cedarfork.test")


def _field(actor, entity, label, placement, **over):
    payload = {"label": label, "entity": entity, "data_type": "text", **over}
    created = tenancy_services.create_custom_field(actor, payload)
    tenancy_services.save_custom_field_placement(actor, created["id"], placement)
    return created


ASKED = {"PORTAL_NEW_SERVICE": "input", "REQUEST_NEW": "input", "REQUEST_DETAIL": "view"}


def _three_fields(tenant):
    """Roof Material (premises), Visit window (account), Preferred name
    (customer) — each asked on the portal AND on Staff New Request."""
    with _ctx(tenant):
        admin = _admin(tenant)
        _field(
            admin,
            "premises",
            "Roof Material",
            ASKED,
            data_type="select",
            options=["Metal", "Tile", "Shingle"],
        )
        _field(admin, "accounts", "Visit window", ASKED)
        _field(admin, "customers", "Preferred name", ASKED)


def _answer_on_the_portal(tenant, token, answers):
    """The applicant's own answers, through the portal draft's real door (W7)."""
    saved = api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data={"custom_data": answers},
        token=token,
    )
    assert saved.status_code in (200, 201), saved.data


def _rows(audit_rows, action, entity_id=None):
    return [
        r
        for r in audit_rows
        if r["action"] == action and (entity_id is None or str(r["entity_id"]) == str(entity_id))
    ]


def _custom(model, pk):
    return dict(model.objects.get(pk=pk).custom_data or {})


def _holder_id(account_id):
    return customers_models.CustomerAccount.objects.get(account_id=account_id).customer_id


# ═══════════════════════════════════════════════════════════════════════════
# 1 · PORTAL → MOVE-IN: a first-time applicant's customer and account answers
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__portal_answers_reach_the_customer_and_account_a_move_in_opens(
    cedar, clerk, audit_rows
):
    _three_fields(cedar)
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="12 Cedar Row", postal_code="78701"
        )
    token = "d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c01"
    _answer_on_the_portal(
        cedar,
        token,
        {"accounts": {"visit_window": "Mornings"}, "customers": {"preferred_name": "Ada"}},
    )
    request_id, _start = _apply(cedar, token=token, services=["water"], unit="Unit 1")
    with _ctx(cedar):
        held = customers_models.ServiceRequest.objects.get(pk=request_id).custom_data
        assert held == {
            "accounts": {"visit_window": "Mornings"},
            "customers": {"preferred_name": "Ada"},
        }
    _approve(clerk, cedar, request_id, outcome="move_in", pick=(premises["id"], unit["id"]))
    # At approval nothing exists to copy them to — they wait on the request.
    approval = _rows(audit_rows, "service_request.custom_fields_copied", request_id)
    assert approval and set(approval[-1]["after"]["waiting"]) == {"accounts", "customers"}

    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            "account_type": "residential",
            "opened_at": OPENED,
            "contact": {"full_name": "Ada Okonjo", "phone": "(512) 555-0177"},
            "customer": _person_block("Ada Okonjo", "(512) 555-0177"),
            "service_request_id": request_id,
            "services": ["water"],
        },
    )
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        account_id = moved.data["id"]
        assert _custom(customers_models.Account, account_id) == {"visit_window": "Mornings"}
        assert _custom(customers_models.Customer, _holder_id(account_id)) == {
            "preferred_name": "Ada"
        }
        # The request keeps its own copy.
        assert customers_models.ServiceRequest.objects.get(pk=request_id).custom_data == held
    (row,) = _rows(audit_rows, CARRIED, request_id)
    assert row["after"]["copied"]["accounts"]["values"] == {"visit_window": "Mornings"}
    assert row["after"]["copied"]["customers"]["values"] == {"preferred_name": "Ada"}
    assert row["after"]["kept"] == {}


# ═══════════════════════════════════════════════════════════════════════════
# 2 · PORTAL → NEW CONNECTION: the premises the build creates, then the account
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__portal_answers_reach_the_premises_a_new_connection_creates(
    cedar, clerk, audit_rows
):
    _three_fields(cedar)
    token = "d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c02"
    _answer_on_the_portal(
        cedar,
        token,
        {"premises": {"roof_material": "Tile"}, "accounts": {"visit_window": "Noon"}},
    )
    request_id, _start = _apply(
        cedar,
        token=token,
        services=["water"],
        first="Lena",
        last="Ortiz",
        email="lena@example.test",
        phone="(512) 555-0161",
        address="77 Juniper Bend",
    )
    _approve(clerk, cedar, request_id, outcome="new_connection")
    approval = _rows(audit_rows, "service_request.custom_fields_copied", request_id)
    assert approval and "premises" in approval[-1]["after"]["waiting"]

    _built, _draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="77 Juniper Bend",
        postal_code="78704",
        services=["water"],
    )
    with _ctx(cedar):
        assert _custom(metering_models.Premises, premises.id) == {"roof_material": "Tile"}
    moved = _unit_move_in(
        cedar,
        clerk,
        units["Unit 1"].id,
        {
            "opened_at": OPENED,
            "account_type": "residential",
            "contact": {"full_name": "Lena Ortiz", "phone": "(512) 555-0161"},
            "customer": _person_block("Lena Ortiz", "(512) 555-0161"),
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        assert _custom(customers_models.Account, moved.data["id"]) == {"visit_window": "Noon"}
    carried = _rows(audit_rows, CARRIED, request_id)
    assert [sorted(r["after"]["copied"]) for r in carried] == [["premises"], ["accounts"]]


# ═══════════════════════════════════════════════════════════════════════════
# 3 · STAFF NEW REQUEST: an answer the clerk typed in the wizard is KEPT
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__a_value_already_on_the_new_account_is_kept_not_overwritten(
    cedar, clerk, audit_rows
):
    _three_fields(cedar)
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="40 Elm Row", postal_code="78702"
        )
    request_id, _start = _apply(
        cedar,
        token="d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c03",
        services=["water"],
        unit="Unit 1",
        address="40 Elm Row",
    )
    with _ctx(cedar):
        # The staff route: the clerk types the answer on the request itself.
        sr.update_request(
            clerk, request_id, {"custom_data": {"accounts": {"visit_window": "Mornings"}}}
        )
    _approve(clerk, cedar, request_id, outcome="move_in", pick=(premises["id"], unit["id"]))
    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            "account_type": "residential",
            "opened_at": OPENED,
            "contact": {"full_name": "Ada Okonjo", "phone": "(512) 555-0177"},
            "customer": _person_block("Ada Okonjo", "(512) 555-0177"),
            "service_request_id": request_id,
            "custom_data": {"visit_window": "Evenings"},
        },
    )
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        assert _custom(customers_models.Account, moved.data["id"]) == {"visit_window": "Evenings"}
    (row,) = _rows(audit_rows, CARRIED, request_id)
    assert row["after"]["kept"] == {"accounts": {"visit_window": "Evenings"}}
    assert "accounts" not in row["after"]["copied"]


# ═══════════════════════════════════════════════════════════════════════════
# 4 · AN ACCOUNT OPENED FOR SOMEBODY ELSE TAKES NOTHING
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__an_account_held_by_another_customer_is_never_the_target(
    cedar, clerk, audit_rows
):
    """The request is linked to Ada (on file at Unit 3); an account Tan holds is
    handed to the carry. Tan is not who the request is for, so nothing moves —
    W6's *one person's facts on another's record* refusal, at the later door."""
    _three_fields(cedar)
    with _ctx(cedar):
        premises, units, _plan = _served_premises(
            clerk,
            cedar,
            address="64 Birch Row",
            postal_code="78709",
            labels=("Unit 1", "Unit 2", "Unit 3"),
        )

        def _occupy(unit, name, phone):
            made = customers_services.create_account(
                clerk,
                {
                    "unit_id": str(unit["id"]),
                    "account_type": "residential",
                    "status": "active",
                    "opened_at": "2026-06-01",
                    "contact": {"full_name": name},
                    "customer": _person_block(name, phone),
                },
            )
            return made, _holder_id(made["id"])

        tans, tan = _occupy(units[1], "Tan Wei", "(512) 555-0199")
        _adas, ada = _occupy(units[2], "Ada Okonjo", "(512) 555-0177")
    request_id, _start = _apply(
        cedar,
        token="d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c04",
        services=["water"],
        unit="Unit 1",
        address="64 Birch Row",
    )
    with _ctx(cedar):
        sr.update_request(
            clerk, request_id, {"custom_data": {"accounts": {"visit_window": "Mornings"}}}
        )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        customer_id=ada,
        pick=(premises["id"], units[0]["id"]),
    )
    with _ctx(cedar):
        assert rcf.carry_into_created(clerk, request_id, account_id=tans["id"]) is None
        assert _custom(customers_models.Account, tans["id"]) == {}
        assert _custom(customers_models.Customer, tan) == {}
    assert not _rows(audit_rows, CARRIED, request_id)


# ═══════════════════════════════════════════════════════════════════════════
# 5 · ONE UTILITY ONLY: another utility's request carries nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__another_utilitys_request_carries_nothing(cedar, clerk, brazos, dana):
    """Brazos Bend has a Roof Material field with the SAME key as Cedar Fork's,
    so only the tenant filter on the request read stands between Cedar's
    applicant's answer and a Brazos property."""
    _three_fields(cedar)
    request_id, _start = _apply(
        cedar,
        token="d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c05",
        services=["water"],
    )
    with _ctx(cedar):
        sr.update_request(
            clerk,
            request_id,
            {"custom_data": {"premises": {"roof_material": "Tile"}}},
        )
    from tests.test_cr094_approval_raises_the_job import _served_unit
    from tests.test_us_met_helpers import tenant_ctx

    with tenant_ctx(brazos):
        _field(
            dana,
            "premises",
            "Roof Material",
            {"S16": "input"},
            data_type="select",
            options=["Metal", "Tile", "Shingle"],
        )
        premises, _unit = _served_unit(dana, brazos, address="9 Pine Way", label="Unit 1")
        assert rcf.carry_into_created(dana, request_id, premises_id=premises["id"]) is None
        assert _custom(metering_models.Premises, premises["id"]) == {}


# ═══════════════════════════════════════════════════════════════════════════
# 6 · REGRESSION GUARD: a request with no answers changes nothing
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9211__a_request_with_no_answers_moves_in_exactly_as_before(
    cedar, clerk, audit_rows
):
    with _ctx(cedar):
        premises, (unit,), _plan = _served_premises(
            clerk, cedar, address="8 Ash Row", postal_code="78703"
        )
    request_id, _start = _apply(
        cedar,
        token="d9211aaa-e5f6-4a7b-8c9d-0e1f2a3b4c06",
        services=["water"],
        unit="Unit 1",
        address="8 Ash Row",
    )
    _approve(clerk, cedar, request_id, outcome="move_in", pick=(premises["id"], unit["id"]))
    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            "account_type": "residential",
            "opened_at": OPENED,
            "contact": {"full_name": "Ada Okonjo", "phone": "(512) 555-0177"},
            "customer": _person_block("Ada Okonjo", "(512) 555-0177"),
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    assert not _rows(audit_rows, CARRIED)

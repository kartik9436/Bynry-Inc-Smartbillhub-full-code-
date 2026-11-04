# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-1114 — a master account is raised only on a premises with
#           two or more units (PO ruling 2026-10-02, decision log top row:
#           *"we have to raise master account on multi pairtment building where
#           we can have multiple units. single family hime, single unit, we
#           should not do master account - how to handle this"*).
# Defect:   DEF-CUS-9113 — every master door opened a master account on a
#           single-unit premises; a single-unit new build's owner master opened
#           ACTIVE holding no service (the 21-walk's W11).
# Doors:    POST /accounts/master (the property's master form, and the portal
#           approval's *Owner's master account*, which is the same form with
#           `service_request_id`) · New Connect's owner step
#           (`metering.connections.create_owner_account`, through the commit).
# Law 14:   run on PostgreSQL — `--ds=config.settings.pgtest`.
# ───────────────────────────────────────────────────────
"""**A master account only on a multi-unit building.**

RED FIRST (law 7): before `_refuse_master_on_single_unit_premises` the three
refusal cases each OPENED a master account (201 / a committed build with an
owner master); the 3-unit case passed before and after, which is its job — it
proves the guard did not close the door on a building it is still open for.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY:** a refusal for some OTHER reason
(identity, no plan, an occupied unit) — so each refusal asserts the rule id
`BR-CUS-1114` and its message key, and the 3-unit case uses the same payload
shape that is refused on one unit; and a "no master" that is only absent from
the RESPONSE — so the tables are counted.
"""

from __future__ import annotations

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from core import errors

from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    EQUIPMENT_TYPE,
    OPENED,
    SIZES,
    _approve,
    _apply,
    _assert_active,
    _ctx,
    _person_block,
    _plan,
    _served_premises,
    _unit_move_in,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam
from tests.test_us_met_helpers import FakeUser
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

REFUSAL_KEY = "customers.account.master_needs_two_units"


def _master_form(tenant, clerk, premises_id, *, name, tax_id, request_id=None):
    body = {
        "premises_id": str(premises_id),
        "opened_at": OPENED,
        "account_type": "commercial",
        "contact": {"full_name": name, "email": "owner@example.test", "phone": "(512) 555-0100"},
        "customer": {"display_name": name, "kind": "company", "identity": {"tax_id": tax_id}},
    }
    if request_id is not None:
        body["service_request_id"] = request_id
    return api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(clerk.id),
        role="billing_clerk",
        tenant=tenant,
        data=body,
    )


def _masters_at(tenant, premises_id):
    with _ctx(tenant):
        return customers_models.Account.objects.filter(
            premises_id=premises_id, kind="master"
        ).count()


# ── (a) the property's master form ──────────────────────────────────────────
def test_a_master_account_on_a_one_unit_premises_is_refused(cedar, clerk):
    with _ctx(cedar):
        premises, _units, _ = _served_premises(
            clerk, cedar, address="14 Alder Run", postal_code="78701"
        )
    refused = _master_form(cedar, clerk, premises["id"], name="Alder Homes LLC", tax_id="99-0001114")
    assert refused.status_code == 409, refused.data
    assert refused.data["br_ref"] == "BR-CUS-1114"
    assert refused.data["message_key"] == REFUSAL_KEY
    assert _masters_at(cedar, premises["id"]) == 0


def test_a_common_area_does_not_make_a_house_a_building(cedar, clerk):
    """A judgment (decision log 2026-10-02, built row): dwellings are counted,
    so one home plus a laundry flagged common is still a single unit — the
    21-walk's W3 added exactly that to make the master form appear."""
    from tests.test_us_met_helpers import make_unit

    with _ctx(cedar):
        premises, _units, _ = _served_premises(
            clerk, cedar, address="18 Alder Run", postal_code="78701"
        )
        make_unit(clerk, premises["id"], label="Laundry", is_common_area=True, unit_type="common_area")
    refused = _master_form(cedar, clerk, premises["id"], name="Alder Bakery LLC", tax_id="99-0001118")
    assert refused.status_code == 409, refused.data
    assert refused.data["br_ref"] == "BR-CUS-1114"
    assert _masters_at(cedar, premises["id"]) == 0


def test_a_master_account_on_a_three_unit_premises_still_opens(cedar, clerk):
    with _ctx(cedar):
        premises, _units, _ = _served_premises(
            clerk,
            cedar,
            address="400 Heron Court",
            postal_code="78702",
            labels=("Unit 1", "Unit 2", "Unit 3"),
        )
    made = _master_form(cedar, clerk, premises["id"], name="Heron Court LLC", tax_id="99-0001115")
    assert made.status_code == 201, made.data
    _assert_active(cedar, made.data["id"], kind="master", category="commercial")
    assert _masters_at(cedar, premises["id"]) == 1


# ── (a) the portal approval's *Owner's master account* ──────────────────────
def test_the_portal_approvals_owner_master_is_refused_on_a_single_unit(cedar, clerk):
    with _ctx(cedar):
        premises, units, _ = _served_premises(
            clerk, cedar, address="18 Alder Run", postal_code="78703"
        )
    request_id, _start = _apply(
        cedar,
        token="b1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b1114",
        services=["sewer"],
        kind="business",
        company="Alder Bakery LLC",
        tax_id="99-0001116",
        email="ap@alderbakery.test",
        phone="(512) 555-0191",
        address="18 Alder Run",
        unit="Unit 1",
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        category="institutional",
        pick=(premises["id"], units[0]["id"]),
    )
    from apps.customers import service_request_api

    with _ctx(cedar):
        detail = service_request_api._detail(request_id)
    # The request page is told the address holds one unit, so the door draws
    # closed with its reason (`ServiceRequestJobLink`).
    assert detail["location_and_services"]["resolved_premises_units"] == 1
    refused = _master_form(
        cedar, clerk, premises["id"], name="Alder Bakery LLC", tax_id="99-0001116",
        request_id=request_id,
    )
    assert refused.status_code == 409, refused.data
    assert refused.data["br_ref"] == "BR-CUS-1114"
    assert _masters_at(cedar, premises["id"]) == 0
    # (b) the applicant gets a REGULAR account on the one unit, ACTIVE.
    moved = _unit_move_in(
        cedar,
        clerk,
        units[0]["id"],
        {
            "opened_at": OPENED,
            "account_type": "institutional",
            "contact": {"full_name": "Alder Bakery LLC", "email": "ap@alderbakery.test"},
            "customer": {
                "display_name": "Alder Bakery LLC",
                "kind": "company",
                "identity": {"tax_id": "99-0001116"},
            },
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    _assert_active(cedar, moved.data["id"], kind="regular", category="institutional")


# ── (a)(b)(c) New Connect: a single-unit new build from a portal request ─────
def _commit(clerk, tenant, request_id, *, address, postal_code, services, owner):
    plan = _plan(tenant)
    with _ctx(tenant):
        draft = work_tables.Connection.objects.get(service_request_id=request_id)
        return draft, w6.commit_new_connect(
            clerk,
            {
                "premises": {
                    "id": None,
                    "address": address,
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": postal_code,
                    "premise_type": None,
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": list(services),
                },
                "mode": "our_crew",
                "scope": "new_premise",
                "units_prefix": "Unit",
                "target_activation": None,
                "service_request_id": None,
                "connection_id": str(draft.id),
                "units": [{"label": "Unit 1", "is_common_area": False}],
                "meters": [],
                "unit_services": [
                    {
                        "unit_label": "Unit 1",
                        "service": code,
                        "equipment": [
                            {"type": EQUIPMENT_TYPE[code], "size_class": SIZES[code], "count": 1}
                        ],
                    }
                    for code in services
                ],
                "plan_assignments": [{"unit_label": "Unit 1", "tariff_id": str(plan.id)}],
                "create_owner_account": owner is not None,
                "owner": owner or {},
                "quote_total": None,
                "occupancy": "vacant_service_off",
                "work_orders": [],
            },
        )


def test_a_single_unit_new_build_ends_with_one_regular_active_account_and_no_master(
    cedar, clerk
):
    request_id, _start = _apply(
        cedar,
        token="b1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b1115",
        services=["battery"],
        kind="business",
        company="Kestrel Energy Co-op",
        tax_id="99-0001117",
        email="office@kestrel.test",
        phone="(512) 555-0133",
        address="81 Juniper Bend",
    )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="agricultural")
    owner = {
        "name": "Kestrel Energy Co-op",
        "email": "office@kestrel.test",
        "phone": "(512) 555-0133",
        "party_kind": "company",
        "identity": {"tax_id": "99-0001117"},
    }
    # (a) asked for an owner master on a single-unit build, the commit refuses
    # by name and writes nothing — the draft is still a draft.
    with pytest.raises(errors.BizError) as refusal:
        _commit(
            clerk, cedar, request_id, address="81 Juniper Bend", postal_code="78707",
            services=["battery"], owner=owner,
        )
    assert refusal.value.br_ref == "BR-CUS-1114"
    with _ctx(cedar):
        assert not customers_models.Account.objects.filter(kind="master").exists()
    # (c) the wizard sends no owner master for one unit (`buildOpensOwnerMaster`).
    draft, built = _commit(
        clerk, cedar, request_id, address="81 Juniper Bend", postal_code="78707",
        services=["battery"], owner=None,
    )
    draft.refresh_from_db()
    assert draft.owner_account_id is None
    with _ctx(cedar):
        from apps.metering import models as metering_models

        unit = metering_models.Unit.objects.get(premises_id=draft.premises_id)
    # (b) the applicant's REGULAR account on the one unit holds the service.
    moved = _unit_move_in(
        cedar,
        clerk,
        unit.id,
        {
            "opened_at": OPENED,
            "account_type": "agricultural",
            "contact": {"full_name": "Kestrel Energy Co-op", "email": "office@kestrel.test"},
            "customer": {
                "display_name": "Kestrel Energy Co-op",
                "kind": "company",
                "identity": {"tax_id": "99-0001117"},
            },
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    account, _holder = _assert_active(
        cedar, moved.data["id"], kind="regular", category="agricultural",
        name="Kestrel Energy Co-op",
    )
    with _ctx(cedar):
        held = set(
            customers_models.ServiceAgreement.objects.filter(
                account=account, ended_on__isnull=True
            ).values_list("service_point__service__code", flat=True)
        )
        assert held == {"battery"}
        at_the_address = customers_models.Account.objects.filter(
            premises_id=draft.premises_id
        ) | customers_models.Account.objects.filter(unit__premises_id=draft.premises_id)
        assert [a.kind for a in at_the_address.distinct()] == ["regular"]

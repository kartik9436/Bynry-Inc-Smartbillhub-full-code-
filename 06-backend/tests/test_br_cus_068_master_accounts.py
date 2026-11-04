# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-003 (the account write path this rides on)
#           Change: OQ-314 second half (PO ruling 2026-08-22 — master accounts)
# Rules:    BR-CUS-068 (a master account is an ordinary `accounts` row,
#           `kind='master'`, payer = the owner/manager, attached to the
#           premises' common-area units through the SAME account–unit linkage
#           every account uses — no new table) · BR-MET-101 (a common area is
#           a unit with a flag; the worked case this file builds: 1408 Elm,
#           3 units + 2 common areas, $41.20 + $28.40 = $69.60 on one owner
#           bill) · BR-CUS-017 (occupancy guard, extended to SA coverage) ·
#           BR-MET-040 (plan required on every covered unit) · BR-CUS-022
#           (start date required) · BR-TEN-035 (number from the tenant series)
# ───────────────────────────────────────────────────────
"""BR-CUS-068 — the master account over a premises' common areas.

The $69.60-SHAPED case is the spine of this file: BR-MET-101's 1408 Elm — three
ordinary units and two common areas (hallway lighting, shared irrigation) —
gets ONE master account covering BOTH common areas, with the billing linkage
(service agreements over each common area's service points) actually present.
The dollar figures themselves are rated by billing from the units' plans and
are not asserted here; what IS asserted is the exact attachment shape those
figures ride on.
"""

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_actions,
    brazos,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _plan(tenant, name, service_code):
    """A PUBLISHED plan the unit can be put on (same fixture shape as
    test_us_cus_003_account_write — plan CONTENT is EP-RAT-01's story; all
    BR-MET-040 asks is that `units.rate_plan_id` is non-null)."""
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _elm_1408(actor, tenant, *, with_plans=True, owner="Whitfield Rentals LLC"):
    """BR-MET-101's worked premises: 1408 Elm — 3 units + 2 common areas.

    The hallway carries electric (its $41.20 line), the irrigation carries
    water (its $28.40 line). Returns (premises, [hallway, irrigation])."""
    premises = make_premises(actor, address_line="1408 Elm St", owner_manager=owner)
    for label in ("Unit A", "Unit B", "Unit C"):
        make_unit(actor, premises["id"], label=label)
    hallway = make_unit(
        actor,
        premises["id"],
        label="Hallway lighting",
        unit_type="common_area",
        is_common_area=True,
    )
    irrigation = make_unit(
        actor,
        premises["id"],
        label="Shared irrigation",
        unit_type="common_area",
        is_common_area=True,
    )
    if with_plans:
        plan = _plan(tenant, "Small Commercial", "electric")
        _plan(tenant, "Small Commercial", "water")
        for unit in (hallway, irrigation):
            metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(hallway["id"], "electric")
    metering_services.ensure_service_point(irrigation["id"], "water")
    return premises, [hallway, irrigation]


#: ⛔ **THE OWNER CARRIES A TAX ID FROM 2026-09-01, AND THAT IS A RULING RATHER
#: THAN A FIXTURE TIDY-UP (`BR-CUS-1024`).** PO verbatim: *"Without identifier we
#: cannot create Customer ID or master account ot regular account"*, superseding
#: that morning's *"an account may still be opened"*. Every case in this file is
#: about master-account MECHANICS — what it covers, what it refuses, what it
#: bills — and none of them is about identity, so the owner is identified once
#: here and the eight cases go on testing what they were written to test. A
#: master account created from a free-text owner name alone is now refused, and
#: `test_cr058_w1_one_customer_every_door.py::test_tc8` is where that is asserted.
MASTER_OWNER_TAX_ID = "74-2915508"


def _owner_customer(name="Whitfield Rentals LLC"):
    return {
        "display_name": name,
        "kind": "company",
        "identity": {"tax_id": MASTER_OWNER_TAX_ID},
    }


def _create(actor, premises, **overrides):
    payload = {
        "premises_id": premises["id"],
        "account_type": "commercial",
        "opened_at": "2026-08-01",
        "customer": _owner_customer(),
    }
    payload.update(overrides)
    return customers_services.create_master_account(actor, payload)


# ══════════════════════════════════════════════════════════════════════════
# The $69.60-shaped attachment: one row, kind master, both common areas covered
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_068_tc1__one_master_row_covers_both_common_areas_with_billing_linkage(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        premises, (hallway, irrigation) = _elm_1408(marcus, brazos)
        audit_rows.clear()
        created = _create(marcus, premises)

        account = customers_models.Account.objects.get(pk=created["id"])
        # ONE ordinary accounts row, kind='master' — no new table anywhere.
        assert account.kind == "master"
        assert created["kind"] == "master"
        assert account.account_no.startswith("AC-")  # BR-TEN-035 series, not "MA-"
        # ⚠ **THE ATTACHMENT MOVED ON 2026-09-01 — `CR-056` W1 / `BR-CUS-1010`.**
        # This line read `assert str(account.unit_id) == hallway["id"]` — the
        # ANCHOR, the premises' first common-area unit by label. The account now
        # hangs off the ADDRESS and names no unit at all, so both shared spaces
        # are reached through the service agreements asserted just below, which
        # is where the second one already rode. **The $69.60 does not move**
        # (`tests/test_br_cus_068_master_bill.py` tc1).
        assert str(account.premises_id) == premises["id"]
        assert account.unit_id is None
        # PAYER: the premises' owner/manager (PO 2026-08-22).
        assert created["name"] == "Whitfield Rentals LLC"
        # BILLING LINKAGE PRESENT: one open SA per service point on BOTH common
        # areas — the hallway's electric ($41.20 line) and the irrigation's
        # water ($28.40 line) both hang off this one account.
        agreements = customers_models.ServiceAgreement.objects.filter(
            tenant_id=brazos.id, account=account, ended_on__isnull=True
        )
        # ⚠ **FOUR, NOT TWO, SINCE 2026-09-25 — `BR-MET-119` amended,
        # `DEF-MET-6796` (`630f472c3`, merged `12c206e7d` 2026-09-27).** PO
        # verbatim: *"the premises' list is what a unit takes, the tick-list
        # stays, and a clerk may untick"*. 1408 Elm advertises electric AND
        # water, so each common area is now born holding BOTH service points,
        # and `_open_master_service_agreements` opens one agreement per point
        # on every covered unit — 2 units × 2 services. This line asserted 2
        # (one point per unit, added by hand below) and was red from that
        # merge. The rule it tests did not move: one SA per ACTIVE service
        # point on every covered common area, which is what is counted now.
        points = sum(
            len(customers_selectors.seams.service_points_for(unit["id"]))
            for unit in (hallway, irrigation)
        )
        assert points == 4
        assert agreements.count() == points
        covered_units = {
            customers_selectors.seams.service_point_ref(str(a.service_point_id))["unit_id"]
            for a in agreements
        }
        assert covered_units == {hallway["id"], irrigation["id"]}
        # The detail resolves the NON-ANCHOR agreement's service too.
        assert set(created["services"]) == {"electric", "water"}
        # Active from birth — a master exists to be billed, and it audits.
        assert created["status_behavior_class"] == "billable"
        assert "account.master_created" in audit_actions(audit_rows)
        assert created["warnings"] == []
        # The coverage selector answers the master for BOTH units — including
        # the one accounts.unit_id does not point at.
        for unit in (hallway, irrigation):
            covering = customers_selectors.master_account_covering_unit(unit["id"])
            assert covering is not None and covering.pk == account.pk


def test_br_cus_068_tc2__a_unit_that_is_not_a_common_area_refuses_by_name(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos)
        from apps.metering import selectors as metering_selectors

        unit_a = next(
            u
            for u in metering_selectors.units_list(filters={"premises_id": premises["id"]})
            if u.label == "Unit A"
        )
        with pytest.raises(errors.BizError) as caught:
            _create(marcus, premises, unit_ids=[str(unit_a.id)])
        assert caught.value.br_ref == "BR-CUS-068"
        assert caught.value.params["unit_id"] == str(unit_a.id)
        assert caught.value.params["label"] == "Unit A"  # refused BY NAME
        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, kind="master"
        ).exists()


def test_br_cus_068_tc3__a_premises_with_no_common_areas_gets_its_owner_an_account(
    brazos, marcus
):
    """⚠ **THIS CASE IS INVERTED BY `CR-056` W1 TASK 9, AND THE INVERSION IS A
    PO RULING RATHER THAN A LOOSENED TEST.**

    It used to assert a REFUSAL — `BizError`, `reason="no_common_area_units"` —
    and that refusal's stated reason was that a master had to ANCHOR on a
    common-area unit, which a house has none of. The PO ruled on 2026-08-31 that
    **every address gets its owner a Master Account, whether or not anything is
    shared, and whether or not the owner lives there**, and `BR-CUS-1010` moves
    the account onto the address, so there is nothing left to anchor.

    The account covers nothing and therefore bills nothing — *no lines, no
    document* is the same ruling's general rule and is `CR-056` W4's to build.

    ⛔ **AND THE HOUSE HALF IS INVERTED AGAIN BY THE PO ON 2026-10-02
    (`BR-CUS-1114`):** *"single family hime, single unit, we should not do master
    account"*. So `9 Solo House Rd` (one unit) is now REFUSED by name, and the
    no-common-area case this test is about is proved on a DUPLEX — two homes,
    nothing shared — which still gets its owner an account covering nothing.
    """
    with tenant_ctx(brazos):
        house = make_premises(marcus, address_line="9 Solo House Rd")
        make_unit(marcus, house["id"], label="Unit A")
        with pytest.raises(errors.BizError) as caught:
            _create(marcus, house)
        assert caught.value.br_ref == "BR-CUS-1114"

        premises = make_premises(marcus, address_line="11 Twin Duplex Rd")
        make_unit(marcus, premises["id"], label="Unit A")
        make_unit(marcus, premises["id"], label="Unit B")

        created = _create(marcus, premises)

        assert created["kind"] == "master"
        assert created["premises_id"] == premises["id"]
        assert created["unit_id"] is None
        # No shared space, so no service agreement and nothing to price.
        # (`created["services"]` is the BUILDING's offering since `BR-CUS-1093`,
        # not what this account holds, so the agreements are what is counted.)
        account = customers_models.Account.objects.get(pk=created["id"])
        assert not customers_models.ServiceAgreement.objects.filter(account=account).exists()
        assert customers_selectors.covered_unit_ids(account) == []


def test_br_cus_068_tc4__a_second_master_on_covered_units_refuses_naming_the_first(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos)
        first = _create(marcus, premises)
        with pytest.raises(errors.BizError) as caught:
            _create(marcus, premises)
        assert caught.value.params["account_no"] == first["account_no"]
        assert (
            customers_models.Account.objects.filter(tenant_id=brazos.id, kind="master").count() == 1
        )


def test_br_cus_068_tc5__a_common_area_without_a_plan_is_now_ACCEPTED(brazos, marcus):
    """⛔ **REVERSED BY THE PO ON 2026-09-21 — this case used to be named
    `…_refuses_per_br_met_040` and asserted the opposite.**

    **PO, verbatim:** *"common area dont need rate plan as of now; make this
    optional"*.

    **What it used to assert, and why it was right.** `BR-MET-040` — *"Plan is
    REQUIRED at account ACTIVATION"* — fired on every unit a master account
    covers, and `create_master_account` creates the account ACTIVE. So a hallway
    with no plan refused the whole account, by name.

    **What the PO measured.** Eight builds raised in a browser, eight refused at
    the final press, and this was the refusal a clerk saw on every build that
    HAD a common area: *"This unit has no rate plan yet."* The other half of the
    pincer refused the builds that had none.

    ⚠ **THE RULE IS NARROWED, NOT DELETED, AND `COMMON_AREA_REQUIRES_A_PLAN` IS
    THE NARROWING.** The PO's words *"as of now"* are theirs and are kept: the
    exemption is one named constant in `customers/services.py`, and setting it
    back to `True` restores the refusal in one line. A DWELLING with no plan is
    refused exactly as it always was — `test_br_met_040_common_area.py` holds
    both sides, and holds the reason this is safe rather than reckless: the bill
    run refuses an unplanned unit and always will.
    """
    with tenant_ctx(brazos):
        premises, (hallway, irrigation) = _elm_1408(marcus, brazos, with_plans=False)
        created = _create(marcus, premises)

        account = customers_models.Account.objects.get(pk=created["id"])
        assert account.kind == "master"
        # Both unplanned common areas are covered, exactly as two planned ones
        # would be: what the ruling removed is the REFUSAL, not the coverage.
        covered = set(customers_selectors.covered_unit_ids(account))
        assert covered == {str(hallway["id"]), str(irrigation["id"])}


def test_br_cus_068_tc6__no_owner_manager_and_no_contact_refuses_the_payer(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos, owner=None)
        with pytest.raises(errors.ValidationError) as caught:
            _create(marcus, premises)
        assert caught.value.field_errors[0]["field"] == "contact.full_name"
        # …and an explicit contact fills the gap.
        created = _create(marcus, premises, contact={"full_name": "Dana Whitfield"})
        # The explicit contact is written as the account's contact …
        assert [row["full_name"] for row in created["contacts"]] == ["Dana Whitfield"]
        # … and the account is NAMED by its customer, the owner company
        # (`DEF-CUS-9776`, 2.549.8: it read the contact's name until then).
        assert created["name"] == "Whitfield Rentals LLC"
        assert created["kind"] == "master"


def test_br_cus_068_tc7__kind_is_a_refused_input_everywhere_else_and_partitions_the_list(
    brazos, marcus
):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos)
        master = _create(marcus, premises)

        # An ordinary create may not name the kind (REFUSED_FIELDS): the only
        # door to kind='master' is the master path itself.
        ordinary_unit = make_unit(
            marcus, make_premises(marcus, address_line="12 Oak St")["id"], label="Unit A"
        )
        plan = rating_models.RatePlan.objects.get(tenant=brazos, name="Small Commercial")
        metering_services.assign_unit_plan(marcus, ordinary_unit["id"], {"tariff_id": str(plan.id)})
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.create_account(
                marcus,
                {"unit_id": ordinary_unit["id"], "account_type": "residential", "kind": "master"},
            )
        assert caught.value.field_errors[0]["field"] == "kind"

        ordinary = customers_services.create_account(
            marcus, {"unit_id": ordinary_unit["id"], "account_type": "residential"}
        )
        assert ordinary["kind"] == "regular"

        # f.kind partitions the S17 list (BR-CUS-068's selector half).
        masters = customers_selectors.account_list(ListParams(filters={"kind": "master"}))
        assert [row["id"] for row in masters] == [master["id"]]
        regulars = customers_selectors.account_list(ListParams(filters={"kind": "regular"}))
        assert master["id"] not in [row["id"] for row in regulars]
        assert ordinary["id"] in [row["id"] for row in regulars]


def test_br_cus_068_tc8__the_endpoint_creates_and_the_executive_forged_post_refuses(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos)
    response = api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(),
        role="billing_clerk",
        tenant=brazos,
        data={
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            # `BR-CUS-1024` (2026-09-01) — the owner is identified. This
            # case is about the ENDPOINT and its RBAC, not about identity.
            "customer": _owner_customer(),
        },
    )
    assert response.status_code == 201
    assert response["Location"].endswith(f"/accounts/{response.data['id']}")
    assert response.data["kind"] == "master"

    forged = api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        data={"premises_id": premises["id"], "account_type": "commercial"},
    )
    assert forged.status_code == 403


def test_br_cus_068_tc9__the_start_date_is_required_before_anything_attaches(brazos, marcus):
    with tenant_ctx(brazos):
        premises, _ = _elm_1408(marcus, brazos)
        with pytest.raises(errors.BizError) as caught:
            _create(marcus, premises, opened_at=None)
        assert caught.value.br_ref == "BR-CUS-022"
        assert not customers_models.Account.objects.filter(
            tenant_id=brazos.id, kind="master"
        ).exists()

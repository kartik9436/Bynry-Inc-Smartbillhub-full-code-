# ── Trace ──────────────────────────────────────────────
# Change:   CR-159-BRC10 — a portal move-in / new-connection request is carried
#           all the way to an ACTIVE customer (PO ruling 2026-10-01, decision
#           log top row: *"complete the move in process or new conenct request
#           coming from portal - extend it until entire process is completed
#           and customer is activated; you will ahve to create regular or
#           master customer; you will ahve to create or link customer ID -
#           those cases also should be tested"*).
# Defects:  DEF-CUS-9034 (the applicant's ticked services never reach the
#           request) · DEF-CUS-9035 (the move-in ignores the customer the clerk
#           linked on the request, and its class) · DEF-MET-6119 (a build
#           records no unmetered service and no size) · DEF-CUS-9036 (the
#           master-account door cannot fulfil an approved request)
# Rules:    BR-CUS-1024 (no identifier, no account) · BR-CUS-068 / BR-MET-116
#           (master account) · BR-CWP-029 / BR-CWP-030 (a portal login attaches
#           to a customer found by account number, postcode and name) · hard
#           rule 8 (addresses on premises only) · hard rule 7 (audit) ·
#           hard-won law 14 (run on PostgreSQL: `--ds=config.settings.pgtest`)
# Journey:  08-qa/01-e2e/journeys/JCWPREQUESTTOACTIVE-portal-request-to-active-customer.md
# ───────────────────────────────────────────────────────
"""**A portal application, carried by a clerk from APPROVED to an ACTIVE customer.**

The test utility sells exactly the six services the PO named on 2026-10-01 —
water, trash, sewer, fire, solar and battery. Every case starts at the PORTAL
(the guest form's two real doors, `PUT` the draft and `POST` its submit), walks
the clerk's real service doors, and ends with:

  * the account ACTIVE, of the kind (regular / master) and class the clerk set;
  * its customer either NEW or the one the clerk LINKED — never a second number;
  * the portal user able to see it — a new customer by enrolling on the number,
    postcode and name printed on the bill (`BR-CWP-030`), a linked customer who
    already has a login by simply signing in again;
  * every row read back from the DATABASE and holding exactly what was typed,
    and the screens' own reads serving those saved values (PO, 2026-10-01:
    *"also ensure you check the all data is correctly saved updated, viewed"*).

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * reading the RESPONSE instead of the tables — every case reads the rows back;
  * a "link existing" case that passes because identity matching happened to
    reuse the customer — the linked customer is a COMPANY or a person with a
    different phone, so only the clerk's link can join them;
  * a service list asserted as "non-empty" — each is compared as a set.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from apps.assets import selectors as asset_selectors
from apps.assets import services as asset_services
from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import move_in_jobs, moves
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_api
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import services as metering_services
from apps.portal import credentials, guest_api
from apps.portal import models as portal_models
from apps.portal import session as portal_session
from core.tenancy import tenant_context

from tests import identity_fixtures
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam · throttle
from tests.test_us_cwp_helpers import switch_on
from tests.test_us_met_helpers import (
    FakeUser,
    make_plan,
    make_premises,
    make_unit,
    seed_physical_series,
    staff_actor,
)
from tests.test_us_ten_helpers import api_call, brazosbend_payload, provisioned_tenant

pytestmark = pytest.mark.django_db

#: PO, via the coordinator, 2026-10-01 — *"When you take utilty take it for 6
#: utility services water, trash, sewer, fire, solar and battery"*.
SIX = ("water", "trash", "sewer", "fire", "solar", "battery")

#: The equipment that SIZES each capacity service, from the ratified ladders
#: (`BR-TEN-171`) — never a string invented here: these are the codes the
#: seeded demo utility plants (`core/sample_fixture.py`).
SIZES = {"trash": "CART-96", "fire": "FL-4", "solar": "SOL-P5", "battery": "BAT-10"}
EQUIPMENT_TYPE = {
    "trash": "container_cart",
    "fire": "fire_line",
    "solar": "pv",
    "battery": "battery",
}
OPENED = "2026-10-05"


# ═══════════════════════════════════════════════════════════════════════════
# THE UTILITY
# ═══════════════════════════════════════════════════════════════════════════
@pytest.fixture()
def cedar(growth_plan, identity_seam):
    """Cedar Fork Utilities — the six services, portal switched on."""
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Cedar Fork Utilities",
            subdomain="cedarfork",
            services=list(SIX),
            owner={
                "full_name": "Rae Lindqvist",
                "email": "rae@cedarfork.test",
                "password": "S3cure!passw0rd",
                "phone": "+1 (512) 555-0101",
            },
        )
    )
    seed_physical_series(tenant)
    admin = staff_actor(tenant, "system_admin", "rae@cedarfork.test")
    switch_on(tenant, admin)
    return tenant


@pytest.fixture()
def clerk(cedar):
    return staff_actor(cedar, "billing_clerk", "clerk@cedarfork.test")


def _ctx(tenant):
    return tenant_context(tenant.id)


def _plan(tenant):
    return make_plan(tenant, name="Cedar Residential", services=SIX)


def _served_premises(clerk, tenant, *, address, postal_code, labels=("Unit 1",)):
    """A premises ON FILE with every unit served for all six services: a service
    point each, a water meter, and the sizing equipment the four capacity
    services bill on. This is the MOVE-IN shape — *"a unit that already has
    service"*."""
    plan = _plan(tenant)
    premises = make_premises(
        clerk,
        address_line=address,
        city="Austin",
        state="TX",
        postal_code=postal_code,
        services_available=list(SIX),
        owner_manager="Cedar Fork Holdings LLC",
    )
    units = []
    for n, label in enumerate(labels):
        unit = make_unit(clerk, premises["id"], label=label)
        metering_services.assign_unit_plan(clerk, unit["id"], {"tariff_id": str(plan.id)})
        for code in SIX:
            metering_services.ensure_service_point(unit["id"], code)
        asset_services.create_asset(
            clerk,
            {
                "type": "meter",
                "asset_no": f"WM-{address[:2]}{n}",
                "service": "water",
                "unit": "gal",
                "read_method": "manual",
                "multiplier": "1",
                "unit_id": unit["id"],
                "install_date": "2026-01-02",
                "size_class": "W-58",
            },
        )
        for code, size in SIZES.items():
            asset_services.create_asset(
                clerk,
                {
                    "type": EQUIPMENT_TYPE[code],
                    "asset_no": f"{code[:3].upper()}-{address[:2]}{n}",
                    "service": code,
                    "unit_id": unit["id"],
                    "install_date": "2026-01-02",
                    "size_class": size,
                },
            )
        units.append(unit)
    return premises, units, plan


# ═══════════════════════════════════════════════════════════════════════════
# THE PORTAL HALF — the guest form's two real doors
# ═══════════════════════════════════════════════════════════════════════════
def _apply(
    tenant,
    *,
    token,
    services,
    first="Ada",
    last="Okonjo",
    email="ada@example.test",
    phone="(512) 555-0177",
    address="12 Cedar Row",
    unit=None,
    kind="person",
    company=None,
    tax_id=None,
):
    start = (date.today() + timedelta(days=21)).isoformat()
    body = {
        "address_as_given": address,
        "service_codes": list(services),
        "applicant_kind": kind,
        "email": email,
        "phone": phone,
        "requested_start": start,
        # DEF-CWP-9818 — the applicant's own pick, required at Send (PO ruling
        # 2026-10-06 (b)); the clerk can still change it, which every case
        # below does through `set_customer_category`.
        "account_type_code": "residential",
    }
    if unit:
        body["address_unit_as_given"] = unit
    if kind == "business":
        body.update(company_name=company, tax_id=tax_id)
    else:
        body.update(first_name=first, last_name=last, date_of_birth="1987-12-04")
    saved = api_call(
        guest_api.application_draft,
        "put",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}",
        tenant=tenant,
        data=body,
        token=token,
    )
    assert saved.status_code in (200, 201), saved.data
    sent = api_call(
        guest_api.submit_application,
        "post",
        f"/api/{tenant.subdomain}/portal/public/applications/{token}/submit",
        tenant=tenant,
        data={"paperless": False},
        token=token,
    )
    assert sent.status_code in (200, 201), sent.data
    return sent.data["request_id"], start


def _assert_request_as_sent(tenant, request_id, *, name, email, phone, address, services, start):
    """Every field the applicant typed, read back off the ROW and off the
    clerk's own read (`GET /service-requests/{id}`)."""
    with _ctx(tenant):
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert row.channel == "customer_portal"
        assert row.state == customers_models.ServiceRequest.SUBMITTED
        assert row.applicant_name == name
        assert row.applicant_email == email
        assert row.applicant_phone == phone
        assert row.address_as_given == address
        assert row.requested_start.isoformat() == start
        asked = set(
            customers_models.ServiceRequestService.objects.filter(request=row).values_list(
                "service__code", flat=True
            )
        )
        assert asked == set(services), "the applicant's ticked services must reach the request"
        detail = service_request_api._detail(request_id)
    served = {s["code"] for s in move_in_jobs.services_asked_for(row)}
    assert served == set(services)
    # The clerk's screen serves the saved values (`GET /service-requests/{id}`).
    assert detail["header"]["request_no"] == row.request_no
    assert detail["applicant"]["name"] == name
    assert detail["applicant"]["email"] == email
    assert detail["applicant"]["phone"] == phone
    assert detail["location_and_services"]["address_as_given"] == address
    assert {s["code"] for s in detail["location_and_services"]["services"]} == set(services)
    assert {s["requested_start"] for s in detail["location_and_services"]["services"]} == {start}
    return row


def _approve(
    clerk, tenant, request_id, *, outcome, customer_id=None, category="residential", pick=None
):
    """The clerk's acts on the request page: pick the property off the register
    where the applicant's typed address did not resolve on its own, link (or
    record *no prior customer*), the class, and Approve with the outcome."""
    with _ctx(tenant):
        if pick is not None:
            premises_id, unit_id = pick
            sr.update_request(
                clerk,
                request_id,
                {"picked_premises_id": str(premises_id), "picked_unit_id": str(unit_id)},
            )
        sr.resolve_address(clerk, request_id)
        sr.set_customer_category(clerk, request_id, account_type_code=category)
        sr.link_customer(
            clerk,
            request_id,
            customer_id=customer_id,
            tier="strong" if customer_id else None,
            basis="clerk confirmed by phone" if customer_id else None,
        )
        out = sr.approve_and_raise(clerk, request_id, outcome=outcome)
        assert "raised" in out["job"], out["job"]
        return out


# ═══════════════════════════════════════════════════════════════════════════
# THE ACCOUNT HALF
# ═══════════════════════════════════════════════════════════════════════════
def _unit_move_in(tenant, clerk, unit_id, payload):
    return api_call(
        customers_api.unit_move_in,
        "post",
        user=FakeUser(clerk.id),
        role="billing_clerk",
        tenant=tenant,
        data=payload,
        unit_id=str(unit_id),
    )


def _person_block(name, phone):
    return {
        "display_name": name,
        "kind": "person",
        "identity": {"phone": phone, "date_of_birth": "1987-12-04"},
    }


def _existing_company_customer(clerk, tenant, unit_id):
    """A customer ALREADY on file — a company, so nothing about a later person
    application could match it by identity. Only the clerk's link can."""
    with _ctx(tenant):
        made = customers_services.create_account(
            clerk,
            {
                "unit_id": str(unit_id),
                "account_type": "commercial",
                "status": "active",
                "opened_at": "2026-06-01",
                "contact": {
                    "full_name": "Harbor Lane Property Mgmt",
                    "email": "ops@harborlane.test",
                    "phone": "512-555-0142",
                },
                "customer": identity_fixtures.customer_block(
                    "Harbor Lane Property Mgmt", account_type="commercial"
                ),
            },
        )
        link = customers_models.CustomerAccount.objects.get(account_id=made["id"])
        return link.customer, made


def _account(tenant, account_id):
    with _ctx(tenant):
        return customers_models.Account.objects.select_related("status", "account_type").get(
            pk=account_id
        )


def _holder(tenant, account_id):
    with _ctx(tenant):
        return (
            customers_models.CustomerAccount.live(tenant_id=tenant.id, account_id=account_id)
            .select_related("customer")
            .get()
            .customer
        )


def _assert_active(tenant, account_id, *, kind, category, customer_id=None, name=None):
    account = _account(tenant, account_id)
    assert (account.status.code, account.status.behavior_class) == ("active", "billable")
    assert account.kind == kind
    assert account.account_type.code == category
    holder = _holder(tenant, account_id)
    if customer_id is not None:
        assert str(holder.id) == str(customer_id), (
            "the clerk's linked customer, not a second number"
        )
    if name is not None:
        assert holder.display_name == name
    # The screen's read serves the saved values.
    with _ctx(tenant):
        detail = customers_selectors.account_detail(account_id)
    assert detail["account_no"] == account.account_no
    return account, holder


def _portal_sees(tenant, account, *, postcode, surname, email, existing_credential=None):
    """`BR-CWP-030` — the number, the postcode and the name on the bill find the
    account; enrolment attaches a login to its customer; a session's account set
    holds it. A customer who already had a login simply signs in again."""
    with _ctx(tenant):
        if existing_credential is None:
            found = credentials.find_account(
                tenant.id, account_no=account.account_no, postcode=postcode, name=surname
            )
            assert found is not None and found.pk == account.pk
            credential = credentials.create_credential(
                tenant.id,
                account=found,
                email=email,
                password="Cedar-Fork-2026",
                otp_channel=portal_models.CHANNEL_EMAIL,
            )
        else:
            credential = existing_credential
        issued = portal_session.issue(tenant.id, credential)
        held = {entry["account_id"] for entry in issued.account_set}
        assert str(account.pk) in held
        return credential, held


# ═══════════════════════════════════════════════════════════════════════════
# 1 · MOVE-IN · NEW CUSTOMER · REGULAR
# ═══════════════════════════════════════════════════════════════════════════
def test_move_in_new_customer_regular_account_for_water(cedar, clerk, audit_rows):
    with _ctx(cedar):
        premises, (unit,), plan = _served_premises(
            clerk, cedar, address="12 Cedar Row", postal_code="78701"
        )
    request_id, start = _apply(
        cedar, token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c01", services=["water"], unit="Unit 1"
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Ada Okonjo",
        email="ada@example.test",
        phone="(512) 555-0177",
        address="12 Cedar Row",
        services=["water"],
        start=start,
    )
    _approve(clerk, cedar, request_id, outcome="move_in", pick=(premises["id"], unit["id"]))
    with _ctx(cedar):
        job = move_in_jobs.MoveInJob.objects.get(request_id=request_id)
        assert job.state == move_in_jobs.STATE_PENDING

    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            "account_type": "residential",
            "opened_at": OPENED,
            "contact": {
                "full_name": "Ada Okonjo",
                "email": "ada@example.test",
                "phone": "(512) 555-0177",
            },
            "customer": _person_block("Ada Okonjo", "(512) 555-0177"),
            "service_request_id": request_id,
            "services": ["water"],
            "initial_reads": [{"meter_no": "WM-120", "value": "1200"}],
        },
    )
    assert moved.status_code == 201, moved.data
    account, holder = _assert_active(
        cedar, moved.data["id"], kind="regular", category="residential", name="Ada Okonjo"
    )
    with _ctx(cedar):
        assert str(account.unit_id) == str(unit["id"])
        assert account.opened_at.isoformat() == OPENED
        contact = customers_models.Contact.objects.get(account=account)
        assert (contact.full_name, contact.email, contact.phone) == (
            "Ada Okonjo",
            "ada@example.test",
            "(512) 555-0177",
        )
        agreements = set(
            customers_models.ServiceAgreement.objects.filter(
                account=account, ended_on__isnull=True
            ).values_list("service_point__service__code", flat=True)
        )
        assert agreements == {"water"}
        record = moves.MoveRecord.objects.get(pk=moved.data["move_record_id"])
        assert str(record.request_id) == request_id
        job.refresh_from_db()
        assert job.state == move_in_jobs.STATE_DONE
    actions = [row["action"] for row in audit_rows]
    for expected in (
        "service_request.created_from_portal",
        "service_request.approved",
        "account.moved_in",
    ):
        assert expected in actions, expected
    _portal_sees(cedar, account, postcode="78701", surname="Okonjo", email="ada@example.test")

    # ── A CLERK CORRECTION changes that one field and leaves a history row ──
    with _ctx(cedar):
        before = customers_selectors.account_detail(str(account.id))
        customers_services.update_account_contact(
            clerk, str(account.id), {"email": "ada.okonjo@example.test"}
        )
        contact = customers_models.Contact.objects.get(account=account)
        assert (contact.full_name, contact.email, contact.phone) == (
            "Ada Okonjo",
            "ada.okonjo@example.test",
            "(512) 555-0177",
        )
        after = customers_selectors.account_detail(str(account.id))
    changed = {key for key in before if before[key] != after.get(key)}
    assert changed <= {"contact", "contacts", "primary_contact", "updated_at"}, changed
    history = [row for row in audit_rows if row["action"] == "account.contact.updated"]
    assert len(history) == 1


# ═══════════════════════════════════════════════════════════════════════════
# 2 · MOVE-IN · LINK AN EXISTING CUSTOMER · REGULAR — and their login sees it
# ═══════════════════════════════════════════════════════════════════════════
def test_move_in_linked_customer_regular_account_for_trash(cedar, clerk):
    with _ctx(cedar):
        _p0, (first_unit,), _ = _served_premises(
            clerk, cedar, address="40 Harbor Ln", postal_code="78702"
        )
        premises, (unit,), _ = _served_premises(
            clerk, cedar, address="41 Harbor Ln", postal_code="78702"
        )
    existing, first = _existing_company_customer(clerk, cedar, first_unit["id"])
    first_account = _account(cedar, first["id"])
    credential, held = _portal_sees(
        cedar,
        first_account,
        postcode="78702",
        surname="Harbor Lane Property Mgmt",
        email="ops@harborlane.test",
    )
    assert held == {str(first_account.pk)}
    with _ctx(cedar):
        customers_before = customers_models.Customer.objects.count()

    # The manager applies through the portal for the next door, as a PERSON —
    # nothing in identity matching could join that to the company on file.
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c02",
        services=["trash"],
        first="Jo",
        last="Marsh",
        email="jo@harborlane.test",
        phone="(512) 555-0188",
        address="41 Harbor Ln",
        unit="Unit 1",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Jo Marsh",
        email="jo@harborlane.test",
        phone="(512) 555-0188",
        address="41 Harbor Ln",
        services=["trash"],
        start=start,
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        customer_id=existing.id,
        category="commercial",
        pick=(premises["id"], unit["id"]),
    )

    # The wizard sends the applicant as typed and NO customer id — the server
    # carries the clerk's link from the request (`DEF-CUS-9035`).
    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            "account_type": "commercial",
            "opened_at": OPENED,
            "contact": {
                "full_name": "Jo Marsh",
                "email": "jo@harborlane.test",
                "phone": "(512) 555-0188",
            },
            "customer": _person_block("Jo Marsh", "(512) 555-0188"),
            "service_request_id": request_id,
            "services": ["trash"],
        },
    )
    assert moved.status_code == 201, moved.data
    account, holder = _assert_active(
        cedar, moved.data["id"], kind="regular", category="commercial", customer_id=existing.id
    )
    with _ctx(cedar):
        assert customers_models.Customer.objects.count() == customers_before, "no second number"
        agreements = set(
            customers_models.ServiceAgreement.objects.filter(
                account=account, ended_on__isnull=True
            ).values_list("service_point__service__code", flat=True)
        )
        assert agreements == {"trash"}
        # The size trash bills on stands on the unit.
        sizes = asset_selectors.billable_asset_size_classes(unit["id"], "trash", date(2026, 10, 31))
        assert sizes == ["CART-96"]
    _c, held = _portal_sees(
        cedar, account, postcode="78702", surname="x", email="x", existing_credential=credential
    )
    assert held == {str(first_account.pk), str(account.pk)}


# ═══════════════════════════════════════════════════════════════════════════
# 3 · MOVE-IN SHAPE · NEW CUSTOMER · MASTER (an owner taking a whole building)
# ═══════════════════════════════════════════════════════════════════════════
def test_existing_building_new_company_master_account_for_fire(cedar, clerk, audit_rows):
    with _ctx(cedar):
        premises, units, _ = _served_premises(
            clerk,
            cedar,
            address="9 Ridgeway",
            postal_code="78703",
            labels=("Unit 1", "Unit 2", "Unit 3"),
        )
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c03",
        services=["fire"],
        kind="business",
        company="Ridgeway Lofts LLC",
        tax_id="99-0004417",
        email="ap@ridgewaylofts.test",
        phone="(512) 555-0190",
        address="9 Ridgeway",
        unit="Unit 1",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Ridgeway Lofts LLC",
        email="ap@ridgewaylofts.test",
        phone="(512) 555-0190",
        address="9 Ridgeway",
        services=["fire"],
        start=start,
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        category="institutional",
        pick=(premises["id"], units[0]["id"]),
    )
    with _ctx(cedar):
        job = move_in_jobs.MoveInJob.objects.get(request_id=request_id)
        made = customers_services.create_master_account(
            clerk,
            {
                "premises_id": str(premises["id"]),
                "opened_at": OPENED,
                "contact": {
                    "full_name": "Ridgeway Lofts LLC",
                    "email": "ap@ridgewaylofts.test",
                    "phone": "(512) 555-0190",
                },
                "customer": {
                    "display_name": "Ridgeway Lofts LLC",
                    "kind": "company",
                    "identity": {"tax_id": "99-0004417"},
                },
                "service_request_id": request_id,
            },
        )
        job.refresh_from_db()
        assert job.state == move_in_jobs.STATE_DONE
        assert job.closed_reason == move_in_jobs.CLOSED_BY_MASTER_ACCOUNT
        assert made["move_in_jobs_closed"] == 1
    # The class came from the REQUEST — the payload named none.
    account, holder = _assert_active(
        cedar, made["id"], kind="master", category="institutional", name="Ridgeway Lofts LLC"
    )
    assert str(account.premises_id) == str(premises["id"]) and account.unit_id is None
    assert holder.kind == "company"
    assert "service_request.fulfilled_by_master_account" in [r["action"] for r in audit_rows]
    _portal_sees(
        cedar,
        account,
        postcode="78703",
        surname="Ridgeway Lofts LLC",
        email="ap@ridgewaylofts.test",
    )


# ═══════════════════════════════════════════════════════════════════════════
# THE NEW-CONNECTION HALF — an address nobody has on file
# ═══════════════════════════════════════════════════════════════════════════
def _build(
    clerk, tenant, request_id, *, address, postal_code, services, owner=None, labels=("Unit 1",)
):
    """The New Connect wizard's last button on the DRAFT build the approval
    raised: the address, the units, the water meter, the sized equipment of
    every capacity service (`DEF-MET-6119`), the plan, and — for an owner — the
    master account."""
    plan = _plan(tenant)
    with _ctx(tenant):
        draft = work_tables.Connection.objects.get(service_request_id=request_id)
        meters = [
            {"unit_label": label, "service": "water"} for label in labels if "water" in services
        ]
        unit_services = [
            {
                "unit_label": label,
                "service": code,
                "equipment": (
                    [{"type": EQUIPMENT_TYPE[code], "size_class": SIZES[code], "count": 1}]
                    if code in SIZES
                    else []
                ),
            }
            for label in labels
            for code in services
            if code != "water"
        ]
        built = w6.commit_new_connect(
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
                "units": [{"label": label, "is_common_area": False} for label in labels],
                "meters": meters,
                "unit_services": unit_services,
                "plan_assignments": [
                    {"unit_label": label, "tariff_id": str(plan.id)} for label in labels
                ],
                "create_owner_account": owner is not None,
                "owner": owner or {},
                "quote_total": None,
                "occupancy": "vacant_service_off",
                "work_orders": [],
            },
        )
        draft.refresh_from_db()
        # ── CR-162-BRC10 · CREATE MAKES IT PENDING, APPROVAL MAKES IT ACTIVE ──
        # PO 2026-10-02: the premises *"will be activated at the time of
        # approval of new conenct request"*, and the owner's master account is
        # *"created PENDING at Create, ACTIVE on approval"*. So the build's own
        # Approve runs here (every service is ready: the build raised no
        # orders), after asserting both were pending until it did — every case
        # below still ends on an ACTIVE account, now for the ruled reason.
        from apps.metering import connection_activation

        assert metering_models.Premises.objects.get(pk=draft.premises_id).status == "pending"
        if draft.owner_account_id is not None:
            assert (
                customers_models.Account.objects.get(pk=draft.owner_account_id).status.code
                == customers_services.PENDING_STATUS_CODE
            )
        ready = connection_activation.activation_readiness(draft.id)["ready_ids"]
        connection_activation.activate(clerk, draft.id, service_ids=ready)
        draft.refresh_from_db()
        premises = metering_models.Premises.objects.get(pk=draft.premises_id)
        assert premises.status == "active"
        units = {u.label: u for u in metering_models.Unit.objects.filter(premises=premises)}
    return built, draft, premises, units


def _assert_build_recorded(tenant, draft, premises, units, *, address, postal_code, services):
    from apps.assets import models as asset_models

    with _ctx(tenant):
        assert premises.address_line == address
        assert premises.postal_code == postal_code
        assert set(premises.services_available or []) == set(services)
        for unit in units.values():
            recorded = set(
                work_tables.ConnectionService.objects.filter(connection=draft, unit=unit).values_list(
                    "service__code", flat=True
                )
            )
            assert recorded == set(services), "every service the build sold is recorded"
            for code, size in SIZES.items():
                if code not in services:
                    continue
                pieces = asset_models.Asset.objects.filter(
                    service_point__unit=unit, service_point__service__code=code
                )
                assert [p.size_class for p in pieces] == [size], code
                # Created at Create NOT installed (PO 2026-09-21); `_build`
                # then APPROVES the build (CR-162-BRC10), which installs them,
                # dated — so by here every piece is Installed with a date.
                assert all(p.install_date is not None for p in pieces)
                assert {p.status.code for p in pieces} == {"active"}
            if "water" in services:
                meter = asset_models.Asset.objects.get(
                    service_point__unit=unit, service_point__service__code="water"
                )
                assert meter.install_date is not None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · NEW CONNECTION · UNKNOWN ADDRESS · ALL SIX · NEW CUSTOMER · REGULAR
# ═══════════════════════════════════════════════════════════════════════════
def test_new_connection_unknown_address_all_six_new_customer_regular(cedar, clerk):
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c04",
        services=list(SIX),
        first="Lena",
        last="Ortiz",
        email="lena@example.test",
        phone="(512) 555-0161",
        address="77 Juniper Bend",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Lena Ortiz",
        email="lena@example.test",
        phone="(512) 555-0161",
        address="77 Juniper Bend",
        services=SIX,
        start=start,
    )
    with _ctx(cedar):
        premises_before = metering_models.Premises.objects.count()
    _approve(clerk, cedar, request_id, outcome="new_connection", category="industrial")
    with _ctx(cedar):
        assert metering_models.Premises.objects.count() == premises_before, (
            "nothing until the build"
        )
    built, draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="77 Juniper Bend",
        postal_code="78704",
        services=SIX,
    )
    assert built["premises_created"] is True
    assert built["sized_equipment"] == 4
    assert not [a for a in built["unavailable"] if a.get("field") == "connection_services"]
    _assert_build_recorded(
        cedar, draft, premises, units, address="77 Juniper Bend", postal_code="78704", services=SIX
    )

    moved = _unit_move_in(
        cedar,
        clerk,
        units["Unit 1"].id,
        {
            "opened_at": OPENED,
            "account_type": "industrial",
            "contact": {
                "full_name": "Lena Ortiz",
                "email": "lena@example.test",
                "phone": "(512) 555-0161",
            },
            "customer": _person_block("Lena Ortiz", "(512) 555-0161"),
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    account, _holder = _assert_active(
        cedar, moved.data["id"], kind="regular", category="industrial", name="Lena Ortiz"
    )
    with _ctx(cedar):
        agreements = set(
            customers_models.ServiceAgreement.objects.filter(
                account=account, ended_on__isnull=True
            ).values_list("service_point__service__code", flat=True)
        )
        assert agreements == set(SIX)
    _portal_sees(cedar, account, postcode="78704", surname="Ortiz", email="lena@example.test")


# ═══════════════════════════════════════════════════════════════════════════
# 5 · NEW CONNECTION · LINK AN EXISTING CUSTOMER · MASTER (the owner's account)
# ═══════════════════════════════════════════════════════════════════════════
def test_new_connection_linked_customer_master_account_for_solar(cedar, clerk):
    with _ctx(cedar):
        _p, (unit0,), _ = _served_premises(clerk, cedar, address="5 Mill St", postal_code="78705")
    existing, first = _existing_company_customer(clerk, cedar, unit0["id"])
    with _ctx(cedar):
        customers_before = customers_models.Customer.objects.count()
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c05",
        services=["solar"],
        first="Jo",
        last="Marsh",
        email="jo@harborlane.test",
        phone="(512) 555-0188",
        address="300 Quarry Rd",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Jo Marsh",
        email="jo@harborlane.test",
        phone="(512) 555-0188",
        address="300 Quarry Rd",
        services=["solar"],
        start=start,
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="new_connection",
        customer_id=existing.id,
        category="builder_developer",
    )
    # The wizard's owner step as it opens on a raised draft: the applicant's
    # name and contact offered as the owner, no customer id sent — the server
    # carries the clerk's link and class from the request.
    built, draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="300 Quarry Rd",
        postal_code="78706",
        services=["solar"],
        labels=("Unit 1", "Unit 2"),
        owner={
            "name": "Jo Marsh",
            "email": "jo@harborlane.test",
            "phone": "(512) 555-0188",
            "party_kind": "person",
        },
    )
    _assert_build_recorded(
        cedar,
        draft,
        premises,
        units,
        address="300 Quarry Rd",
        postal_code="78706",
        services=["solar"],
    )
    account, _holder = _assert_active(
        cedar,
        str(draft.owner_account_id),
        kind="master",
        category="builder_developer",
        customer_id=existing.id,
    )
    with _ctx(cedar):
        assert customers_models.Customer.objects.count() == customers_before
    _portal_sees(
        cedar,
        account,
        postcode="78706",
        surname="Harbor Lane Property Mgmt",
        email="ops2@harborlane.test",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 6 · NEW CONNECTION · NEW CUSTOMER · MASTER — battery
# 7 · MOVE-IN · NEW CUSTOMER · REGULAR — sewer
# ═══════════════════════════════════════════════════════════════════════════
def test_new_connection_new_customer_master_account_for_battery(cedar, clerk):
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c06",
        services=["battery"],
        kind="business",
        company="Oxbow Farms Co-op",
        tax_id="99-0006611",
        email="office@oxbow.test",
        phone="(512) 555-0133",
        address="2 Oxbow Trail",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Oxbow Farms Co-op",
        email="office@oxbow.test",
        phone="(512) 555-0133",
        address="2 Oxbow Trail",
        services=["battery"],
        start=start,
    )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="agricultural")
    built, draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="2 Oxbow Trail",
        postal_code="78707",
        services=["battery"],
        # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
        # building of two or more units, so this build makes two; the
        # single-unit shape is tests/test_br_cus_1114_master_only_multi_unit.py.
        labels=("Unit 1", "Unit 2"),
        owner={
            "name": "Oxbow Farms Co-op",
            "email": "office@oxbow.test",
            "phone": "(512) 555-0133",
            "party_kind": "company",
            "identity": {"tax_id": "99-0006611"},
        },
    )
    _assert_build_recorded(
        cedar,
        draft,
        premises,
        units,
        address="2 Oxbow Trail",
        postal_code="78707",
        services=["battery"],
    )
    account, holder = _assert_active(
        cedar,
        str(draft.owner_account_id),
        kind="master",
        category="agricultural",
        name="Oxbow Farms Co-op",
    )
    assert holder.kind == "company"
    _portal_sees(
        cedar, account, postcode="78707", surname="Oxbow Farms Co-op", email="office@oxbow.test"
    )


def test_move_in_new_customer_regular_account_for_sewer(cedar, clerk):
    with _ctx(cedar):
        premises, (unit,), _ = _served_premises(
            clerk, cedar, address="18 Elm Ct", postal_code="78708"
        )
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c07",
        services=["sewer"],
        first="Sam",
        last="Reyes",
        email="sam@example.test",
        phone="(512) 555-0122",
        address="18 Elm Ct",
        unit="Unit 1",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Sam Reyes",
        email="sam@example.test",
        phone="(512) 555-0122",
        address="18 Elm Ct",
        services=["sewer"],
        start=start,
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        category="municipal",
        pick=(premises["id"], unit["id"]),
    )
    moved = _unit_move_in(
        cedar,
        clerk,
        unit["id"],
        {
            # The wizard opens on `residential` and its prefill swaps in the
            # request's class; a caller that sends none gets it from the server.
            "opened_at": OPENED,
            "contact": {
                "full_name": "Sam Reyes",
                "email": "sam@example.test",
                "phone": "(512) 555-0122",
            },
            "customer": _person_block("Sam Reyes", "(512) 555-0122"),
            "service_request_id": request_id,
            "services": ["sewer"],
        },
    )
    assert moved.status_code == 201, moved.data
    account, _h = _assert_active(
        cedar, moved.data["id"], kind="regular", category="municipal", name="Sam Reyes"
    )
    _portal_sees(cedar, account, postcode="78708", surname="Reyes", email="sam@example.test")


def test_a_legacy_class_cannot_be_picked_for_a_new_request(cedar, clerk):
    """`BR-CUS-094` — `government` is the EIGHTH seeded class, lawful on rows
    that already carry it and UNSELECTABLE on a new record. The other seven are
    exercised by the cases above (residential, commercial, institutional,
    industrial, builder_developer, agricultural, municipal)."""
    from core import errors

    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c08",
        services=["water"],
        address="1 Civic Plaza",
    )
    with _ctx(cedar):
        with pytest.raises((errors.BizError, errors.ValidationError)):
            sr.set_customer_category(clerk, request_id, account_type_code="government")
        row = customers_models.ServiceRequest.objects.select_related("account_type").get(
            pk=request_id
        )
        # The refused pick changed nothing: the request keeps the category the
        # applicant chose online (DEF-CWP-9818), never `government`.
        assert row.account_type.code == "residential"


def test_the_property_master_form_fulfils_a_portal_request_for_a_person(cedar, clerk):
    """**The screen path for an owner on a building on file** — the request
    page's *Owner's master account* link opens the property's Common areas tab
    with `?request=`, and that tab's form sends a payer name and nothing else
    about the customer. The applicant is carried from the request."""
    with _ctx(cedar):
        premises, units, _ = _served_premises(
            clerk,
            cedar,
            address="64 Birch Row",
            postal_code="78709",
            labels=("Unit 1", "Unit 2"),
        )
        customers_before = customers_models.Customer.objects.count()
    request_id, start = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c09",
        services=["water", "sewer"],
        first="Priya",
        last="Nair",
        email="priya@example.test",
        phone="(512) 555-0155",
        address="64 Birch Row",
        unit="Unit 1",
    )
    _assert_request_as_sent(
        cedar,
        request_id,
        name="Priya Nair",
        email="priya@example.test",
        phone="(512) 555-0155",
        address="64 Birch Row",
        services=["water", "sewer"],
        start=start,
    )
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        category="residential",
        pick=(premises["id"], units[0]["id"]),
    )
    made = api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(clerk.id),
        role="billing_clerk",
        tenant=cedar,
        data={
            "premises_id": str(premises["id"]),
            "account_type": "residential",
            "opened_at": OPENED,
            "contact": {"full_name": "Priya Nair", "is_primary": True},
            "service_request_id": request_id,
        },
    )
    assert made.status_code == 201, made.data
    account, holder = _assert_active(
        cedar, made.data["id"], kind="master", category="residential", name="Priya Nair"
    )
    assert holder.kind == "person"
    with _ctx(cedar):
        assert customers_models.Customer.objects.count() == customers_before + 1
        job = move_in_jobs.MoveInJob.objects.get(request_id=request_id)
        assert job.state == move_in_jobs.STATE_DONE
    _portal_sees(cedar, account, postcode="78709", surname="Nair", email="priya@example.test")


# ═══════════════════════════════════════════════════════════════════════════
# 10 · DEF-CUS-9043 — the request's own read says WHICH customer it is linked to
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9043_the_request_names_the_customer_it_is_linked_to(cedar, clerk):
    """The clerk's link (or *searched, none*) is a fact the request page must
    be able to SHOW: the row printed tier and basis only, so after *Record
    that I searched* it was blank and after a link it named nobody."""
    with _ctx(cedar):
        _p, (unit0,), _ = _served_premises(clerk, cedar, address="70 Kingfisher Ln", postal_code="78710")
    existing, _first = _existing_company_customer(clerk, cedar, unit0["id"])
    request_id, _ = _apply(
        cedar, token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c10", services=["water"], address="9 Nowhere Rd"
    )
    with _ctx(cedar):
        sr.link_customer(clerk, request_id, customer_id=None)
        searched = service_request_api._detail(request_id)["applicant"]["customer_match"]
        assert searched["confirmed_at"] is not None
        assert searched["customer_id"] is None and searched["customer_no"] is None
        sr.link_customer(clerk, request_id, customer_id=existing.id, tier="strong")
        linked = service_request_api._detail(request_id)["applicant"]["customer_match"]
    assert linked["customer_no"] == existing.customer_no
    assert linked["display_name"] == "Harbor Lane Property Mgmt"


# ═══════════════════════════════════════════════════════════════════════════
# 11 · DEF-CWP-9045 — a business's Tax ID typed online reaches the clerk (last
#      four) and the NEW customer the request opens (OQ-CWP-1560, ruled (b))
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cwp_9045_a_tax_id_typed_online_reaches_the_clerk_and_the_new_company(cedar, clerk):
    """*"stays on the draft and the clerk reads it from there"* — and nothing
    read it from there: the request page showed no Tax ID, and the property's
    master form (a payer name, no identity fields) was REFUSED for every new
    company by `BR-CUS-1024`, because the applicant was carried with no
    identifier. The number is stored ONCE on the draft and read from it."""
    with _ctx(cedar):
        premises, units, _ = _served_premises(
            clerk, cedar, address="12 Mill Row", postal_code="78711", labels=("Unit 1", "Unit 2")
        )
        customers_before = customers_models.Customer.objects.count()
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c11",
        services=["water", "sewer"],
        kind="business",
        company="Mill Row Bakery LLC",
        tax_id="99-0007731",
        email="books@millrow.test",
        phone="(512) 555-0171",
        address="12 Mill Row",
        unit="Unit 1",
    )
    with _ctx(cedar):
        detail = service_request_api._detail(request_id)
    assert detail["applicant"]["identifier"]["tax_id_last4"] == "7731"
    assert detail["applicant"]["identifier"]["tax_id_present"] is True
    assert "99-0007731" not in str(detail), "the clerk reads the LAST FOUR, never the number"
    _approve(
        clerk,
        cedar,
        request_id,
        outcome="move_in",
        category="commercial",
        pick=(premises["id"], units[0]["id"]),
    )
    made = api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(clerk.id),
        role="billing_clerk",
        tenant=cedar,
        data={
            "premises_id": str(premises["id"]),
            "account_type": "commercial",
            "opened_at": OPENED,
            "contact": {"full_name": "Mill Row Bakery LLC", "is_primary": True},
            "service_request_id": request_id,
        },
    )
    assert made.status_code == 201, made.data
    account, holder = _assert_active(
        cedar, made.data["id"], kind="master", category="commercial", name="Mill Row Bakery LLC"
    )
    assert holder.kind == "company"
    with _ctx(cedar):
        assert customers_models.Customer.objects.count() == customers_before + 1
        assert customers_models.Customer.objects.get(pk=holder.pk).tax_id == "99-0007731"


# ═══════════════════════════════════════════════════════════════════════════
# 12 · DEF-CWP-9046 — the date of birth typed online reaches the REQUEST
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cwp_9046_the_date_of_birth_typed_online_is_on_the_request(cedar, clerk):
    """It was blanked at Send because the request had no column for it
    (CR-068 wave C, 2026-09-04); the column arrived on 2026-09-15 and the
    portal door never used it. Stored once — on the request — and the draft's
    copy is still blanked."""
    from apps.portal import models as portal_models

    request_id, _ = _apply(
        cedar, token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c12", services=["water"], address="3 Elm Ct"
    )
    with _ctx(cedar):
        row = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert row.date_of_birth is not None and row.date_of_birth.isoformat() == "1987-12-04"
        assert service_request_api._detail(request_id)["applicant"]["date_of_birth"] == "1987-12-04"
        draft = portal_models.PortalApplicationDraft.objects.get(service_request_id=request_id)
        assert draft.date_of_birth is None, "stored once: on the request, not also on the draft"


# ═══════════════════════════════════════════════════════════════════════════
# 13 · DEF-CUS-9047 — the category New Connect's step 1 sends is the owner's
#      account class; the request's class is only the default
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9047_the_build_owners_class_is_the_one_the_clerk_picked(cedar, clerk):
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c13",
        services=["battery"],
        kind="business",
        company="Kestrel Energy Co-op",
        tax_id="99-0001313",
        email="office@kestrel.test",
        phone="(512) 555-0113",
        address="4 Kestrel Way",
    )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="industrial")
    built, draft, premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="4 Kestrel Way",
        postal_code="78713",
        services=["battery"],
        # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
        # building of two or more units, so this build makes two; the
        # single-unit shape is tests/test_br_cus_1114_master_only_multi_unit.py.
        labels=("Unit 1", "Unit 2"),
        owner={
            "name": "Kestrel Energy Co-op",
            "email": "office@kestrel.test",
            "phone": "(512) 555-0113",
            "party_kind": "company",
            "identity": {"tax_id": "99-0001313"},
            "account_type": "agricultural",
        },
    )
    _assert_active(
        cedar,
        str(draft.owner_account_id),
        kind="master",
        category="agricultural",
        name="Kestrel Energy Co-op",
    )


# ═══════════════════════════════════════════════════════════════════════════
# 14 · DEF-CUS-9053 — the master form's account carries the applicant's email
#      and phone, so the customer can set up a portal login
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9053_the_master_form_account_holds_the_applicants_contact(cedar, clerk):
    with _ctx(cedar):
        premises, units, _ = _served_premises(
            clerk, cedar, address="70 Birch Row", postal_code="78714", labels=("Unit 1", "Unit 2")
        )
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c14",
        services=["water"],
        kind="business",
        company="Birch Row Bakery LLC",
        tax_id="99-0001414",
        email="books@birchrow.test",
        phone="(512) 555-0114",
        address="70 Birch Row",
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
    made = api_call(
        customers_api.master_accounts,
        "post",
        user=FakeUser(clerk.id),
        role="billing_clerk",
        tenant=cedar,
        data={
            "premises_id": str(premises["id"]),
            "account_type": "institutional",
            "opened_at": OPENED,
            # What the property's form sends: a payer NAME and nothing else.
            "contact": {"full_name": "Birch Row Bakery LLC", "is_primary": True},
            "service_request_id": request_id,
        },
    )
    assert made.status_code == 201, made.data
    account = _account(cedar, made.data["id"])
    with _ctx(cedar):
        contact = customers_models.Contact.objects.get(account=account)
        assert (contact.email, contact.phone) == ("books@birchrow.test", "(512) 555-0114")
        channel, _destination, _masked = credentials.contact_for(cedar.id, account)
    assert channel is not None, "the enrol screen would answer 'We hold no contact'"


# ═══════════════════════════════════════════════════════════════════════════
# 15 · DEF-CUS-9074 — the build a request raises PREFILLS what the request holds
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9074_the_build_prefill_carries_services_class_dob_and_tax_id(cedar, clerk):
    from apps.metering import connection_reads

    person_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c15",
        services=["water", "solar"],
        address="91 Juniper Bend",
    )
    _approve(clerk, cedar, person_id, outcome="new_connection", category="municipal")
    business_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c16",
        services=list(SIX),
        kind="business",
        company="Juniper Foods Co",
        tax_id="99-0001616",
        email="ap@juniperfoods.test",
        phone="(512) 555-0116",
        address="93 Juniper Bend",
    )
    _approve(clerk, cedar, business_id, outcome="new_connection", category="industrial")
    with _ctx(cedar):
        person = connection_reads.connection_detail(
            work_tables.Connection.objects.get(service_request_id=person_id).id
        )["prefill"]
        business = connection_reads.connection_detail(
            work_tables.Connection.objects.get(service_request_id=business_id).id
        )["prefill"]
    assert set(person["service_codes"]) == {"water", "solar"}
    assert person["account_type_code"] == "municipal"
    assert person["date_of_birth"] == "1987-12-04"
    assert person["tax_id_present"] is False
    assert set(business["service_codes"]) == set(SIX)
    assert business["account_type_code"] == "industrial"
    assert business["date_of_birth"] is None
    assert (business["tax_id_present"], business["tax_id_last4"]) == (True, "1616")
    assert "99-0001616" not in str(business), "the build reads the LAST FOUR, never the number"


# ═══════════════════════════════════════════════════════════════════════════
# 16 · DEF-CUS-9078 — ONE APPLICANT, ONE CUSTOMER NUMBER
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_9078_the_owner_and_the_occupant_of_a_new_build_are_one_customer(cedar, clerk):
    """A new PERSON asks online for a new connection. The build opens the
    owner's master account and mints them a customer number; the move-in that
    follows opens their regular account. Until this fix the move-in minted a
    SECOND number for the same applicant, because a person carries no
    government identifier for `BR-CUS-1024` to reuse by — the 21-walk's W10
    showed one applicant as C-00059 and C-00060. The customer a door creates
    for a request is now recorded on the request, so the next door carries it."""
    request_id, _ = _apply(
        cedar,
        token="a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c17",
        services=["water"],
        first="Rhea",
        last="Okafor",
        email="rhea@example.test",
        phone="(512) 555-0171",
        address="17 Juniper Bend",
    )
    _approve(clerk, cedar, request_id, outcome="new_connection", category="residential")
    with _ctx(cedar):
        customers_before = customers_models.Customer.objects.count()
    _built, draft, _premises, units = _build(
        clerk,
        cedar,
        request_id,
        address="17 Juniper Bend",
        postal_code="78704",
        services=["water"],
        # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
        # building of two or more units, so this build makes two; the
        # single-unit shape is tests/test_br_cus_1114_master_only_multi_unit.py.
        labels=("Unit 1", "Unit 2"),
        owner={
            "name": "Rhea Okafor",
            "email": "rhea@example.test",
            "phone": "(512) 555-0171",
            "party_kind": "person",
            "identity": {"phone": "(512) 555-0171"},
        },
    )
    _owner_account, owner = _assert_active(
        cedar, str(draft.owner_account_id), kind="master", category="residential", name="Rhea Okafor"
    )
    with _ctx(cedar):
        request = customers_models.ServiceRequest.objects.get(pk=request_id)
        assert request.matched_customer_id == owner.id, "the request names who the build created"
    moved = _unit_move_in(
        cedar,
        clerk,
        units["Unit 1"].id,
        {
            "opened_at": OPENED,
            "account_type": "residential",
            "contact": {
                "full_name": "Rhea Okafor",
                "email": "rhea@example.test",
                "phone": "(512) 555-0171",
            },
            "customer": _person_block("Rhea Okafor", "(512) 555-0171"),
            "service_request_id": request_id,
        },
    )
    assert moved.status_code == 201, moved.data
    _account, holder = _assert_active(
        cedar, moved.data["id"], kind="regular", category="residential", name="Rhea Okafor"
    )
    assert holder.id == owner.id, "one applicant, one customer number"
    with _ctx(cedar):
        assert customers_models.Customer.objects.count() == customers_before + 1

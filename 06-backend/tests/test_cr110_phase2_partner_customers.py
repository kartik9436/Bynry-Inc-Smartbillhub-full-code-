# ── Trace ──────────────────────────────────────────────
# Story:  CR-110-BRC04 phase 2 wave 2 — `GET /api/{utility}/partner/v1/
#         customers`, scope `serve_customer`. PO 2026-09-16, verbatim:
#         *"Customers = accounts"* and *"send service address"*.
# Rules:  CLAUDE.md hard rule 8 / BR-MET-1161 (an address is stored on
#         `premises` and NOWHERE else) · BR-CUS-1010 (an owner's account names
#         no unit) · BR-CUS-055 (account status is a TENANT lookup) ·
#         BR-TEN-003 (`company_id` is VERIFIED, never used to select) · B14
#         rule 31 (no database id is ever a visible value) · NFR-3 (the page is
#         taken in SQL) · hard-won law 7 (name the false pass and refuse it)
# ───────────────────────────────────────────────────────
"""THE CUSTOMER API SERVES ACCOUNTS, WITH THE ADDRESS WALKED TO THE PREMISES.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY — asked first, per law 7
--------------------------------------------------------------------
**Named answer, and the brief named it before a line was written: a fixture
whose accounts all share ONE premises, or have none at all.** Then a walk that
is broken in either direction still produces the right-looking string for every
row, and the suite prints green over an API that would send every customer the
same address. `DEF-CUS-3653` is the same failure one module along — a header
line composed from a retired address kind, *"null on every account forever with
`tsc` and every test green"*.

So the fixture below builds **four accounts that are four different address
stories**, and every case asserts all four:

    Ruiz     a regular account at premises 1        an address
    Okonjo   a regular account at premises 2        a DIFFERENT address
    Vestry   a master account naming premises 3     the `premises_id` leg
    Orphan   a master account naming a premises     `None` — and still SERVED
             this tenant does not hold
    Pryor    a regular account with `premises_id`   the UNIT leg
             NULL, the state the `customers 0036`
             backfill could not resolve

⚠ **THE FIFTH WAS ADDED AFTER THE OTHER FOUR WERE GREEN, BECAUSE THE FIRST
FIXTURE COULD NOT REACH THE WALK'S SECOND LEG AT ALL.** `create_account` writes
`premises_id=unit.premises_id` at creation, so **every account a test can build
through the front door takes the STORED leg** and the unit leg — the whole
reason the walk has two — was never executed. Four cases were green over it.
The unresolved-backfill row is the only shape that reaches it, the `accounts`
model's own column comment describes it, and it is now built on purpose.

**Second false pass:** asserting the `address` KEY is present. Every case reads
the VALUE back and compares it against the `premises` row's own columns — the
stored column, not a second selector, because agreeing with another read proves
only that two reads agree.

**Third:** a mailing address that happens to equal the service address. The
landlord case is built on purpose — a mailing line at a building the account
does not take service at — so serving the wrong one cannot look right.

**Fourth, and it is why the statement count is a test at all:** a per-row walk
is invisible on a demo tenant with twelve accounts and is 40,000 statements on
the largest utility this product models. The count is asserted to be the SAME
for two accounts and for four, which is the only form of that assertion that
cannot be satisfied by a slow implementation.

RED PROVED FIRST, IN `pytest` — the harness that runs it
----------------------------------------------------------
Each case was run against a deliberately broken tree before it was trusted
green; the failures are quoted in the CR section and in this lane's report.
`python3 <module>` was not used anywhere (`DEF-GOV-3733`).
"""

from __future__ import annotations

import json
import uuid

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection as django_connection

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.integrations import partner_api, reference
from apps.integrations.runners import serve
from apps.integrations.seams import customers as customers_seam
from apps.metering import models as metering_models

from tests.test_cr110_phase2_partner_reference import (  # noqa: F401
    ALLOWED_ADDRESS,
    HINT,
    KEY,
    _body,
    _connect,
    _get,
    wired,
)
from tests.test_us_cus_003_account_write import _create_payload, _plan
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

#: ⚠ **`/partner/v1/customers` UNTIL 2026-09-17 (`DEF-INT-5623`)** — the PO
#: ruled the partner surface must call an account an account. The values here
#: never moved; only the address did.
PATH = "/partner/v1/accounts"

#: The four addresses the fixture builds. Written out here so a case can assert
#: the SHAPE the PO's document prints — *"123 Main Street, Austin, TX 78704"* —
#: rather than whatever the composer happened to produce.
RUIZ_PREMISES = {
    "address_line": "123 Main Street",
    "city": "Austin",
    "state": "TX",
    "postal_code": "78704",
}
OKONJO_PREMISES = {
    "address_line": "88 Cypress Row",
    "city": "Katy",
    "state": "TX",
    "postal_code": "77494",
}
VESTRY_PREMISES = {
    "address_line": "4 Pecan Yard",
    "city": "Bastrop",
    "state": "TX",
    "postal_code": "78602",
}


def _account_at(actor, tenant, premises_overrides, *, label, contact, mailing=None,
                service="electric"):
    """One regular account on its own premises, through the real services.

    ⚠ **THE SERVICE IS A PARAMETER BECAUSE THE ISOLATION TENANT SELLS A
    DIFFERENT ONE.** Brazos Bend is Electric + Water and Lone Star Ridge is
    Water only, so a helper hardcoding `electric` refuses on the one tenant the
    isolation case exists to use — which is the fixture being right about the
    product rather than a nuisance."""
    from apps.metering import services as metering_services

    premises = make_premises(
        actor, services_available=[service], **premises_overrides
    )
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor,
        unit["id"],
        {"tariff_id": str(_plan(tenant, name=f"{service.title()} Standard",
                                service_code=service).id)},
    )
    metering_services.ensure_service_point(unit["id"], service)
    payload = _create_payload(unit["id"], contact=contact)
    payload["customer"] = {
        "display_name": contact["full_name"],
        "kind": "person",
        "identity": {"phone": contact["phone"]},
    }
    if mailing is not None:
        payload["addresses"] = [mailing]
    created = customers_services.create_account(actor, payload)
    return premises, customers_models.Account.objects.get(pk=created["id"])


def _master_at(actor, tenant, premises_id):
    """An owner's account — `BR-CUS-1010`: it names NO unit and hangs off the
    ADDRESS. Built by taking a regular account's unit away, because
    `create_master_account`'s own door is not what this file is about and the
    row it leaves is the row that matters here."""
    premises, account = _account_at(
        actor,
        tenant,
        VESTRY_PREMISES,
        label="Common area",
        contact={
            "full_name": "Vestry Holdings LLC",
            "email": "books@vestry.example.com",
            "phone": "+1 (512) 555-0144",
            "dob": "1980-01-01",
            "gov_id_last4": "9001",
        },
    )
    customers_models.Account.objects.filter(pk=account.pk).update(
        kind="master", unit=None, premises_id=premises["id"]
    )
    return premises, customers_models.Account.objects.get(pk=account.pk)


@pytest.fixture()
def address_stories(brazos, marcus):
    """Four accounts that are four different address stories — see the module
    docstring for why a fixture of one shared premises would print green over
    a broken walk."""
    with tenant_ctx(brazos):
        ruiz_premises, ruiz = _account_at(
            marcus,
            brazos,
            RUIZ_PREMISES,
            label="Unit A",
            contact={
                "full_name": "Charles Schultz",
                "email": "charles.schultz@example.com",
                "phone": "+1 (512) 555-0101",
                "dob": "1988-04-02",
                "gov_id_last4": "1122",
            },
            # ⚠ **THE LANDLORD CASE, ON PURPOSE.** The bill goes somewhere the
            # meter is not, so serving the mailing address cannot look right.
            mailing={
                "kind": "mailing",
                "line1": "PO Box 9912",
                "city": "Dallas",
                "state": "TX",
            },
        )
        okonjo_premises, okonjo = _account_at(
            marcus,
            brazos,
            OKONJO_PREMISES,
            label="Unit B",
            contact={
                "full_name": "Amara Okonjo",
                "email": "amara.okonjo@example.com",
                "phone": "+1 (281) 555-0102",
                "dob": "1975-11-30",
                "gov_id_last4": "3344",
            },
        )
        vestry_premises, vestry = _master_at(marcus, brazos, None)
        # The fourth: a master account naming a premises this tenant does not
        # hold. The `customers 0036` column comment calls this state out by
        # name — *"an account whose unit the metering seam cannot answer for"*.
        orphan_premises, orphan = _account_at(
            marcus,
            brazos,
            {**OKONJO_PREMISES, "address_line": "9 Lost Lane"},
            label="Unit C",
            contact={
                "full_name": "Dell Pryor",
                "email": "dell.pryor@example.com",
                "phone": "+1 (713) 555-0103",
                "dob": "1969-06-06",
                "gov_id_last4": "5566",
            },
        )
        customers_models.Account.objects.filter(pk=orphan.pk).update(
            kind="master", unit=None, premises_id=uuid.uuid4()
        )
        orphan = customers_models.Account.objects.get(pk=orphan.pk)
        # ── THE FIFTH: the UNIT leg, which no account built through the front
        # door can reach, because `create_account` writes `premises_id` from
        # the unit at creation. NULLing it is the `customers 0036` state the
        # column's own comment names — *"an account whose unit the metering
        # seam cannot answer for"* read the other way round: the unit answers
        # and the column does not.
        pryor_premises, pryor = _account_at(
            marcus,
            brazos,
            {**RUIZ_PREMISES, "address_line": "77 Dovetail Bend"},
            label="Unit D",
            contact={
                "full_name": "Rosa Pryor",
                "email": "rosa.pryor@example.com",
                "phone": "+1 (210) 555-0104",
                "dob": "1983-02-14",
                "gov_id_last4": "7788",
            },
        )
        customers_models.Account.objects.filter(pk=pryor.pk).update(premises_id=None)
        pryor = customers_models.Account.objects.get(pk=pryor.pk)
    return {
        "ruiz": (ruiz_premises, ruiz),
        "okonjo": (okonjo_premises, okonjo),
        "vestry": (vestry_premises, vestry),
        "orphan": (orphan_premises, orphan),
        "pryor": (pryor_premises, pryor),
    }


def _records(brazos, **query):
    response = _get(
        brazos, partner_api.partner_accounts, path=PATH, query=query or None
    )
    assert response.status_code == 200, _body(response)
    return json.loads(_body(response))


def _by_number(body):
    return {one["consumer_no"]: one for one in body["records"]}


# ══════════════════════════════════════════════════════════════════════════
# THE ROUTE IS SERVED — the hold this wave was written to release
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_route_no_longer_answers_not_yet_served(brazos, dana, wired, address_stories):
    """⚠ **HARD-WON LAW 2'S OTHER HALF, ON THE DAY IT FIRES.** Lane A wrote the
    hold and the case that goes red when it expires, in the same commit. This
    is the other side of it: the address serves, `ROUTE_WAVE` lost its row, and
    the phase-1 pair is untouched because it belongs to waves 3 and 4."""
    response = _get(brazos, partner_api.partner_accounts, path=PATH)
    assert response.status_code == 200, _body(response)
    assert "customers" not in partner_api.ROUTE_WAVE, (
        "the address serves and the hold that pointed at it still names a wave"
    )
    # ⚠ **ABOUT THIS ROUTE AND NOT ABOUT THE OTHER THREE.** The first draft
    # asserted the whole remaining set and was WRONG WITHIN THE HOUR, because a
    # sibling lane landed the ledger while this one was being written. A case
    # that goes red when somebody else does their job correctly is a case that
    # teaches the next lane to edit it rather than to read it.
    assert set(partner_api.ROUTE_WAVE) <= {"bills", "payments"}


@pytest.mark.django_db
def test_customers_means_accounts_and_not_the_customers_table(brazos, dana, wired, address_stories):
    """PO 2026-09-16, verbatim: *"Customers = accounts"*.

    ⚠ **A LANDLORD IS ONE `customers` ROW AND SEVERAL ACCOUNTS**, so reading
    the ruling the other way round would hand a partner one record where their
    ledger has several to post against. The count is asserted against the
    ACCOUNTS table, so an implementation that served `customers` rows would
    have to coincidentally agree on the number as well as on every field."""
    body = _records(brazos)
    with tenant_ctx(brazos):
        numbers = set(
            customers_models.Account.objects.filter(tenant_id=brazos.id).values_list(
                "account_no", flat=True
            )
        )
    assert body["total_records"] == len(numbers)
    assert set(_by_number(body)) == numbers


@pytest.mark.django_db
def test_the_id_is_the_account_number_and_no_database_id_is_on_the_payload(
    brazos, dana, wired, address_stories
):
    """B14 rule 31, and `seams/billing.as_record`'s rule for this whole surface:
    *"a partner keyed on our uuid is coupled to our storage forever."*

    ⚠ **THE SUPPLIED DOCUMENT SHOWS `"id": 1001` AND WE DIVERGE, DELIBERATELY.**
    Recorded on the CR rather than resolved quietly in either direction."""
    body = _records(brazos)
    printed = json.dumps(body)
    for record in body["records"]:
        assert record["id"] == record["consumer_no"], record
        assert record["id"], "an account with no number would be unkeyable"
    with tenant_ctx(brazos):
        for account in customers_models.Account.objects.filter(tenant_id=brazos.id):
            assert str(account.id) not in printed, (
                f"the uuid of {account.account_no} reached a partner payload"
            )


# ══════════════════════════════════════════════════════════════════════════
# THE SERVICE ADDRESS — walked, and proved against the stored column
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_address_is_the_service_address_walked_to_the_premises(
    brazos, dana, wired, address_stories
):
    """PO 2026-09-16: *"send service address"*, and hard rule 8 makes it a WALK.

    ⚠ **FOUR ACCOUNTS, FOUR ANSWERS, ALL ASSERTED.** A fixture sharing one
    premises would pass with a broken walk; this one cannot. Each address is
    compared against the `premises` ROW's own columns rather than against a
    second selector, because two reads agreeing proves only that they agree.
    """
    body = _by_number(_records(brazos))
    with tenant_ctx(brazos):
        for name in ("ruiz", "okonjo", "vestry"):
            premises, account = address_stories[name]
            row = metering_models.Premises.objects.get(pk=premises["id"])
            served = body[account.account_no]["address"]
            assert row.address_line in served, (name, served, row.address_line)
            assert row.city in served and row.state in served, (name, served)
            assert row.postal_code in served, (name, served)

    ruiz = body[address_stories["ruiz"][1].account_no]["address"]
    okonjo = body[address_stories["okonjo"][1].account_no]["address"]
    assert ruiz != okonjo, "two accounts at two premises were served one address"
    # The shape the PO's own document prints, exactly.
    assert ruiz == "123 Main Street, Austin, TX 78704", ruiz


@pytest.mark.django_db
def test_a_master_account_reaches_its_address_through_premises_id(
    brazos, dana, wired, address_stories
):
    """`BR-CUS-1010` — an owner's account names NO unit and still has an address.

    ⚠ **THE TEMPTING WRONG ANSWER IS `None` FOR THE WHOLE GROUP WHEN THERE IS
    NO UNIT**, which would blank the address on every master account in the
    product (`DEF-CUS-5163` says so one module along). So the second leg of the
    walk is asserted on a row that has no unit at all."""
    premises, vestry = address_stories["vestry"]
    assert vestry.unit_id is None, "the fixture is not testing what it claims to"
    assert vestry.premises_id is not None
    body = _by_number(_records(brazos))
    assert body[vestry.account_no]["address"] == "4 Pecan Yard, Bastrop, TX 78602"


@pytest.mark.django_db
def test_a_regular_account_with_no_stored_premises_reaches_it_through_the_unit(
    brazos, dana, wired, address_stories
):
    """⚠ **THE WALK'S SECOND LEG, WHICH FOUR GREEN CASES NEVER EXECUTED.**

    `create_account` writes `premises_id=unit.premises_id`, so every account
    built through the front door takes the STORED leg and the unit leg is
    unreachable from a fixture — the exact false pass law 7 asks for, found by
    reading `services.create_account` rather than by any check. The
    `customers 0036` backfill left real rows in this state and the model's own
    column comment names it.
    """
    premises, pryor = address_stories["pryor"]
    assert pryor.premises_id is None, "the fixture is not testing what it claims to"
    assert pryor.unit_id is not None
    body = _by_number(_records(brazos))
    assert body[pryor.account_no]["address"] == "77 Dovetail Bend, Austin, TX 78704"
    with tenant_ctx(brazos):
        row = metering_models.Premises.objects.get(pk=premises["id"])
    assert row.address_line in body[pryor.account_no]["address"]


@pytest.mark.django_db
def test_an_account_whose_premises_cannot_be_resolved_is_still_served(
    brazos, dana, wired, address_stories
):
    """⚠ **`null`, AND THE RECORD IS STILL ON THE PAGE.**

    Dropping it would move `total_records` and leave the partner reconciling a
    shortfall it cannot explain; inventing an address would have it reconcile
    consumption against the wrong property, which is worse. The field says
    nothing it does not know and the customer is still resolvable."""
    _, orphan = address_stories["orphan"]
    body = _by_number(_records(brazos))
    assert orphan.account_no in body, "an unresolvable address removed a customer"
    assert body[orphan.account_no]["address"] is None
    assert body[orphan.account_no]["customer_name"] == "Dell Pryor"


@pytest.mark.django_db
def test_the_walk_agrees_with_the_customers_modules_own_published_read(
    brazos, dana, wired, address_stories
):
    """⚠ **THE SEAM'S WALK IS THE BATCHED FORM OF A READ CUSTOMERS ALREADY
    PUBLISHES, AND THIS IS WHAT STOPS IT BECOMING A SECOND OPINION.**

    `customers.selectors.premises_id_for_account` owns `BR-CUS-1010`'s
    precedence. `billing/statement.py` names the hazard of a second copy in as
    many words — *"a second statement of `BR-CUS-1010`'s precedence and the one
    that drifts"* — and reads the answer rather than repeating the walk, which
    is right for ONE account and is a round trip per account for a thousand.

    So this seam takes the unit leg off the row it already joined, and the two
    are tied together HERE instead of in a comment. All four shapes are
    asserted — the unit leg, the `premises_id` leg, and the account that
    resolves to neither — because agreement on the easy case proves nothing.
    """
    from apps.customers import selectors as customers_selectors

    with tenant_ctx(brazos):
        accounts = list(customers_seam.collectable())
        assert len(accounts) == 5, "the fixture is not covering every shape"
        pairs = [
            (
                one.account_no,
                customers_seam.premises_id_for(one),
                customers_selectors.premises_id_for_account(one),
            )
            for one in accounts
        ]
    for number, ours, theirs in pairs:
        assert ours == theirs, (
            f"{number}: this seam walks to {ours} and customers' own published "
            f"read walks to {theirs} — one of the two precedences has moved"
        )
    # ⚠ **THE UNIT LEG IS EXERCISED HERE, NOT MERELY AGREED ABOUT.** The
    # account whose stored column is NULL must resolve through its unit in
    # BOTH reads, or this case is four accounts agreeing about one leg.
    unit_leg = next(
        one for one in pairs if one[0] == address_stories["pryor"][1].account_no
    )
    assert unit_leg[1] is not None and unit_leg[1] == unit_leg[2], unit_leg
    assert len({one[1] for one in pairs}) >= 4, "the five shapes collapsed to one answer"
    # ⚠ **NO ACCOUNT RESOLVES TO `None` HERE AND NONE CAN**, which is a fact
    # about the SCHEMA rather than about this fixture: `ck_accounts_anchored`
    # refuses a row with neither a unit nor a premises, so the walk's `None`
    # is defensive. The absence a partner actually meets is `address: null`
    # from a premises id that resolves to no row — which is the orphan, and is
    # `test_an_account_whose_premises_cannot_be_resolved_is_still_served`.
    assert all(one[1] is not None for one in pairs), pairs


@pytest.mark.django_db
def test_the_mailing_address_is_never_the_one_served(brazos, dana, wired, address_stories):
    """PO 2026-09-16: *"send service address"* — *"Not the mailing address,
    which for a landlord is a different building"* (the CR's own row).

    The fixture's first account has a `PO Box` in Dallas on `customers
    .addresses` `kind='mailing'` and a meter in Austin.

    ⚠⚠ **AMENDED 2026-09-17 (`CR-111-BRC04`) — AND THE AMENDMENT IS NARROWER
    THAN IT LOOKS, WHICH IS THE WHOLE POINT.** This case used to assert that the
    Dallas line appears **NOWHERE** in the payload. That was the right assertion
    while `address` was the only address on the record; it is the wrong one now
    that `territory_data` carries the BILLING address deliberately, and a lane
    that read the red line as *the mailing address leaked* would have deleted a
    field the payload is supposed to have.

    **The rule it exists for has not moved by an inch: the mailing address must
    never be served AS THE SERVICE ADDRESS.** So the assertion gets SHARPER
    rather than looser — it now names the two fields and checks that the two
    addresses are in the right ones, instead of checking that one of them is
    absent. Serving the PO Box as the service address, or the Austin line as the
    billing address, both go red here; they could not both have gone red before.
    """
    _, ruiz = address_stories["ruiz"]
    with tenant_ctx(brazos):
        mailing = customers_models.Address.objects.get(
            tenant_id=brazos.id, account=ruiz, kind="mailing"
        )
    records = _records(brazos)["records"]
    theirs = [one for one in records if one["consumer_no"] == ruiz.account_no]
    assert theirs, f"the landlord's account is not on the page: {records}"
    record = theirs[0]

    austin = "123 Main Street, Austin, TX 78704"
    assert record["address"] == austin, "the top-level address is the SERVICE address"
    assert record["territory_data"]["service_address"] == austin
    assert "PO Box 9912" in (record["territory_data"]["billing_address"] or ""), (
        "the bill's own address never reached the payload"
    )
    assert mailing.city not in (record["address"] or ""), (
        "the bill's address was served as the service address"
    )
    assert mailing.city not in (record["territory_data"]["service_address"] or "")


@pytest.mark.django_db
def test_the_retired_service_address_kind_is_not_what_is_read(brazos, dana, wired, address_stories):
    """`DEF-CUS-3653` — `kind='service'` is RETIRED and refused by name, and a
    screen line composed from it *"would have returned null on every account
    forever with `tsc` and every test green"*.

    This asserts the seam reads the PREMISES rather than any `addresses` row:
    the premises' street line is changed underneath and the payload follows it.
    An implementation reading a second copy would keep serving the old value.
    """
    premises, ruiz = address_stories["ruiz"]
    with tenant_ctx(brazos):
        metering_models.Premises.objects.filter(pk=premises["id"]).update(
            address_line="125 Main Street"
        )
    body = _by_number(_records(brazos))
    assert body[ruiz.account_no]["address"] == "125 Main Street, Austin, TX 78704"


@pytest.mark.django_db
def test_a_premises_with_no_locality_serves_its_street_line_alone(
    brazos, dana, wired, address_stories
):
    """A premises whose city was never typed is a FACT, not a failed derivation.
    The street line still travels and nothing is invented to fill the shape."""
    premises, okonjo = address_stories["okonjo"]
    with tenant_ctx(brazos):
        metering_models.Premises.objects.filter(pk=premises["id"]).update(
            city=None, state=None, postal_code=None
        )
    body = _by_number(_records(brazos))
    assert body[okonjo.account_no]["address"] == "88 Cypress Row"


# ══════════════════════════════════════════════════════════════════════════
# THE NAME, THE CONTACT AND THE STATUS
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_name_email_and_phone_are_the_accounts_primary_contact(
    brazos, dana, wired, address_stories
):
    """PO: *"`customer_name` the ACCOUNT name"*. The account's name is its
    primary contact's — `selectors.primary_contact_name`'s own rule, because
    `BR-CUS-054`'s first-class customer entity is not what a bill is addressed
    to. The ORDER that decides *which* contact is asserted below."""
    body = _by_number(_records(brazos))
    _, ruiz = address_stories["ruiz"]
    record = body[ruiz.account_no]
    assert record["customer_name"] == "Charles Schultz"
    assert record["email"] == "charles.schultz@example.com"
    assert record["phone"] == "+1 (512) 555-0101"


@pytest.mark.django_db
def test_which_contact_is_the_name_is_the_account_screens_own_order(
    brazos, dana, wired, address_stories
):
    """⚠ **A BATCHED READ THAT SORTED DIFFERENTLY WOULD QUIETLY RENAME
    CUSTOMERS** on the partner payload while the account screen kept the old
    name, and no statement count could see it (`primary_contact_names_for`
    records the same hazard about its own form). A second, non-primary contact
    is added and the answer must not move."""
    from apps.customers import selectors as customers_selectors

    _, ruiz = address_stories["ruiz"]
    with tenant_ctx(brazos):
        customers_models.Contact.objects.create(
            tenant_id=brazos.id,
            account=ruiz,
            full_name="Not The Primary",
            email="nope@example.com",
            is_primary=False,
        )
        on_screen = customers_selectors.primary_contact_name(ruiz)
    body = _by_number(_records(brazos))
    assert body[ruiz.account_no]["customer_name"] == on_screen == "Charles Schultz"


@pytest.mark.django_db
def test_an_account_with_no_contact_serves_three_nulls_and_is_still_on_the_page(
    brazos, dana, wired, address_stories
):
    """Absence is a fact. The account is still resolvable by its number, which
    is what the partner keys on."""
    _, okonjo = address_stories["okonjo"]
    with tenant_ctx(brazos):
        customers_models.Contact.objects.filter(
            tenant_id=brazos.id, account=okonjo
        ).delete()
    body = _by_number(_records(brazos))
    record = body[okonjo.account_no]
    assert record["customer_name"] is None
    assert record["email"] is None and record["phone"] is None
    assert record["consumer_no"] == okonjo.account_no


@pytest.mark.django_db
def test_the_status_label_is_the_reference_endpoints_own_word(
    brazos, dana, wired, address_stories
):
    """⚠ **TWO UTILITIES ANSWER DIFFERENTLY, SO A TYPED VOCABULARY IS WRONG ON
    THE FIRST TENANT THAT ADDS ONE** (`BR-CUS-055`). Lane A's reference
    endpoint publishes `accountStatus` from the same lookup; this asserts the
    two agree code-for-code and word-for-word, so they cannot drift without
    something going red."""
    body = _records(brazos)
    with tenant_ctx(brazos):
        published = {one["code"]: one["label"] for one in reference.account_statuses(brazos.id)}
    assert published, "an empty vocabulary makes every assertion below vacuous"
    seen = {record["status"]["code"] for record in body["records"]}
    assert seen, "no account carried a status"
    for record in body["records"]:
        status = record["status"]
        assert status["code"] in published, status
        assert status["label"] == published[status["code"]], (
            f"the customer payload calls {status['code']} '{status['label']}' and the "
            f"reference endpoint calls it '{published[status['code']]}'"
        )
        assert status["label"] != status["code"], "a label that is its own code says nothing"


@pytest.mark.django_db
def test_a_deactivated_status_still_resolves_on_the_record(brazos, dana, wired, address_stories):
    """⚠ **THE CASE THAT DECIDES WHERE THE LABEL IS READ FROM.** The reference
    endpoint filters `active=True`; an account may still hold a status a clerk
    has since deactivated. Built out of the reference list, that account's label
    would be missing. Read from the account's own joined row, it is right — and
    because the PO ruled every coded field ships inline as `{code, label}`, a
    partner resolves it even though it is not in the published list."""
    _, ruiz = address_stories["ruiz"]
    with tenant_ctx(brazos):
        status = customers_models.Account.objects.get(pk=ruiz.pk).status
        customers_models.AccountStatus.objects.filter(pk=status.pk).update(active=False)
        published = {one["code"] for one in reference.account_statuses(brazos.id)}
    record = _by_number(_records(brazos))[ruiz.account_no]
    assert status.code not in published, "the fixture did not deactivate anything"
    assert record["status"] == {"code": status.code, "label": status.name}


@pytest.mark.django_db
def test_the_behaviour_class_never_travels(brazos, dana, wired, address_stories):
    """`billable`, `billable_base_only`, `non_billable` and `terminal` are how
    OUR billing keys off a tenant's label. Publishing them would invite a
    finance system to make billing decisions from them — the same line
    `reference.account_statuses` already draws."""
    printed = json.dumps(_records(brazos))
    for word in ("billable_base_only", "non_billable", "behavior_class", "terminal"):
        assert word not in printed, f"{word} reached a partner payload"


# ══════════════════════════════════════════════════════════════════════════
# PAGING, THE TOTAL, AND THE STATEMENT COUNT
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_envelope_carries_a_total_and_a_page_walk_loses_nobody(
    brazos, dana, wired, address_stories
):
    """⚠ **THE TOTAL IS WHAT THE PARTNER'S JOB CHECKS ITSELF AGAINST**, rather
    than trusting that it reached the end (the CR's own paging note). Walked one
    row at a time so a boundary bug has somewhere to show."""
    first = _records(brazos, page_size="1")
    assert first["total_records"] == 5 and first["total_pages"] == 5
    assert first["page"] == 1 and first["page_size"] == 1

    seen = []
    for page in range(1, first["total_pages"] + 1):
        body = _records(brazos, page=str(page), page_size="1")
        assert len(body["records"]) == 1, (page, body)
        seen.append(body["records"][0]["consumer_no"])
    assert len(set(seen)) == first["total_records"], seen
    assert seen == sorted(seen), "the order is not the account number ascending"


@pytest.mark.django_db
def test_the_order_is_the_account_number_and_needs_no_date_window(
    brazos, dana, wired, address_stories
):
    """Unlike bills and payments, this API takes no `since`/`until`. The reason
    is the ORDER: `account_no` is unique per tenant and allocated from a
    monotonic series, so a new account lands AFTER any cursor a partner has
    passed and a page walk cannot skip a row. A `from`/`to` passed anyway
    changes nothing — it is not read, rather than accepted and ignored."""
    assert customers_seam.ORDER_BY == ("account_no", "id")
    plain = _records(brazos)
    windowed = _records(brazos, **{"from": "2026-09-01", "to": "2026-09-02"})
    assert windowed["records"] == plain["records"]
    assert windowed["total_records"] == plain["total_records"] == 5


@pytest.mark.django_db
def test_a_page_costs_the_same_number_of_statements_whatever_it_holds(
    brazos, marcus, dana, wired, address_stories
):
    """⚠ **40,000 ACCOUNTS AT 1,000 A PAGE IS 40 CALLS, AND A WALK PERFORMED
    PER ROW MAKES IT 40,000 QUERIES** — invisible on a demo tenant with twelve.

    The assertion is that two rows and four rows cost the SAME, which is the
    only form of it a slow implementation cannot satisfy. An absolute number
    would go red the day an unrelated read is added and teach a lane to raise
    it rather than to look."""
    with tenant_ctx(brazos):
        two = list(customers_seam.collectable()[:2])
        four = list(customers_seam.collectable()[:4])
        assert len(two) == 2 and len(four) == 4
        with CaptureQueriesContext(django_connection) as small:
            customers_seam.as_records(two)
        with CaptureQueriesContext(django_connection) as large:
            customers_seam.as_records(four)
    assert len(small) == len(large), (
        f"{len(small)} statements for two accounts and {len(large)} for four — "
        "the walk or the contact read is running per row (DEF-2723's shape)"
    )
    # ⚠ **THREE SINCE `CR-111-BRC04`, NOT TWO** — the MAILING address joined the
    # premises walk and the primary contact, and it is one `account_id__in` read
    # for the whole page like the other two. The ceiling is raised by exactly the
    # read that was added, with its reason, rather than loosened.
    #
    # ⚠ **IT WAS NEARLY FIVE, AND THIS CASE IS WHAT STOPPED IT (`DEF-INT-5587`).**
    # The first draft also resolved the plan and the balance here; the balance
    # costs a statement PER ACCOUNT, and this assertion's sibling above reported
    # **10 statements for two accounts and 14 for four**. Both moved to
    # `consumer-info`, which is a lookup by number rather than a walk.
    #
    # ⚠ **FOUR SINCE `DEF-INT-9796` (PO 2026-10-06 D3 (a))** — a company account
    # is sent under its legal name, read from `customers.selectors
    # .company_names_for` as ONE `account_id__in` read for the page. Raised by
    # exactly that read, with its reason.
    assert len(large) <= 4, (
        f"{len(large)} statements for one page: the address walk, the mailing "
        "address, the primary contact and the company name are one read each"
    )


@pytest.mark.django_db
def test_as_record_refuses_to_resolve_its_own_page_facts(brazos, address_stories):
    """The N+1 guard, stated as a signature rather than as a comment. A loop
    that forgot to batch is a `TypeError`, not a slow endpoint."""
    with tenant_ctx(brazos):
        account = customers_seam.collectable().first()
        with pytest.raises(TypeError):
            customers_seam.as_record(account)  # type: ignore[call-arg]


@pytest.mark.django_db
def test_the_default_page_size_is_the_pos_thousand(brazos, dana, wired, address_stories):
    """PO 2026-09-16: *"make this as 1000 per page"*. Read off the module rather
    than retyped, and asserted on THIS route's envelope."""
    body = _records(brazos)
    assert body["page_size"] == partner_api.DEFAULT_PAGE_SIZE == 1000


# ══════════════════════════════════════════════════════════════════════════
# THE DOOR — the scope, the company, the refusal, the isolation
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_a_key_with_only_serve_customer_reaches_this_and_is_refused_on_the_other_three(
    brazos, dana, address_stories
):
    """Check 5, from the one side that proves it BOTH ways. A key ticked for
    customers alone reads customers and gets the same five words on bills,
    payments and the ledger — which is the refusal a wrong key gets, because
    `BR-INT-044` will not tell a caller which of the causes was true."""
    serve.reset_partner_limits()
    with tenant_ctx(brazos):
        _connect(brazos, dana, scope=["serve_customer"])

    allowed = _get(brazos, partner_api.partner_accounts, path=PATH)
    assert allowed.status_code == 200, _body(allowed)

    for what, view in (
        ("bills", partner_api.partner_bills),
        ("payments", partner_api.partner_v1_payments),
        ("ledger", partner_api.partner_ledger),
    ):
        refused = _get(brazos, view, path=f"/partner/v1/{what}")
        assert refused.status_code == 404, f"{what} answered {refused.status_code}"
        assert _body(refused) == (
            b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
        ), what


@pytest.mark.django_db
def test_another_utilitys_company_id_serves_our_own_customers(
    brazos, lonestar, dana, wired, address_stories
):
    """⚠ **AMENDED 2026-09-17 (`CR-111-BRC04`) — WAS
    `test_another_utilitys_company_id_is_refused_and_echoes_neither_id`.**

    PO ruling: *"you will ahve to remove company ID filter from all Apis - we
    cannot tell tenant ID outside our system"*. There is no `403` any more.

    ⚠ **`BR-TEN-003` IS UNCHANGED AND IS WHAT THIS STILL ASSERTS.** Naming Lone
    Star Ridge returns **Brazos Bend's** customers, because the utility comes
    from the key and never from a parameter. The assertion moved from the STATUS
    to the CONTENT, which makes it stronger: a `403` proved only that we refused,
    while comparing the records against the ones served with no `company_id` at
    all proves the parameter changes nothing about what comes back.
    """
    serve.reset_partner_limits()
    named = _get(
        brazos,
        partner_api.partner_accounts,
        path=PATH,
        query={"company_id": str(lonestar.id)},
    )
    serve.reset_partner_limits()
    plain = _get(brazos, partner_api.partner_accounts, path=PATH)

    assert named.status_code == 200, _body(named)
    assert bytes(_body(named)) == bytes(_body(plain)), (
        "naming another utility changed the answer — something still selects on it"
    )
    printed = _body(named).decode()
    assert str(lonestar.id) not in printed and str(brazos.id) not in printed, (
        "a payload echoing a utility id is a probe for real utility ids"
    )


@pytest.mark.django_db
def test_no_key_at_all_is_the_one_refusal_sentence(brazos, dana, wired, address_stories):
    """The same bytes as a wrong key, a revoked key and an address off the
    allowlist — `BR-INT-044`'s whole point."""
    response = _get(brazos, partner_api.partner_accounts, path=PATH, key=None)
    assert response.status_code == 404
    assert _body(response) == b'{"error": "We cannot serve this request.", "code": "REFUSED"}'


@pytest.mark.django_db
def test_one_utility_cannot_read_anothers_customers(brazos, lonestar, dana, erin, marcus):
    """⚠ **THE CASE THE SUITE'S OWN DATABASE CANNOT PROVE, WHICH IS WHY THE
    SEAM STATES THE TENANT TWICE.** RLS `FORCE` scopes this on PostgreSQL and
    the suite runs on SQLite, which has none — so a draft relying on RLS alone
    would serve one utility another's customers and pass everything
    (`seams/billing.collectable` carries the same paragraph, and it was
    written after exactly this happened)."""
    with tenant_ctx(brazos):
        _account_at(
            marcus,
            brazos,
            RUIZ_PREMISES,
            label="Unit A",
            contact={
                "full_name": "Charles Schultz",
                "email": "charles.schultz@example.com",
                "phone": "+1 (512) 555-0101",
                "dob": "1988-04-02",
                "gov_id_last4": "1122",
            },
        )
    with tenant_ctx(lonestar):
        _account_at(
            erin,
            lonestar,
            OKONJO_PREMISES,
            label="Unit B",
            service="water",  # Lone Star Ridge sells water and nothing else
            contact={
                "full_name": "Amara Okonjo",
                "email": "amara.okonjo@example.com",
                "phone": "+1 (281) 555-0102",
                "dob": "1975-11-30",
                "gov_id_last4": "3344",
            },
        )
        _connect(lonestar, erin)
    serve.reset_partner_limits()
    body = _records(lonestar)
    assert body["total_records"] == 1, body
    assert body["records"][0]["customer_name"] == "Amara Okonjo"
    assert "Charles Schultz" not in json.dumps(body)


@pytest.mark.django_db
def test_the_read_is_recorded_on_the_access_log_without_the_key(
    brazos, dana, wired, address_stories
):
    """Hard rule 7's neighbour on this surface — every partner read is a run row
    a manager can see, and `caller.hint` is a mask. A run record naming a secret
    is a leaked secret."""
    from apps.integrations import models as int_models

    body = _records(brazos, page_size="2")
    with tenant_ctx(brazos):
        run = int_models.IntegrationRun.objects.get()
    # ⚠ **THE MANAGER'S OWN WORD MOVED WITH THE SURFACE (`DEF-INT-5623`).** The
    # run row reads *Accounts, everything · … · ••••7Q2F* where it read
    # *Customers* until 2026-09-17. `SERVED_ROUTES` carries the label, so the
    # access log, the API row and the address cannot say three different words.
    assert "Accounts" in run.summary and HINT in run.summary
    assert "Customers" not in run.summary
    # ⚠ **READ OFF THE ENVELOPE, NOT TYPED.** The first draft asserted
    # *"page 1 of 2"* and went red the moment the fixture grew a fifth
    # account — a case that breaks when the fixture gets BETTER teaches the
    # next lane to edit the number rather than read the row.
    assert f"{len(body['records'])} records" in run.summary, run.summary
    assert f"page 1 of {body['total_pages']}" in run.summary, run.summary
    assert KEY not in (run.summary or "")


@pytest.mark.django_db
def test_the_payload_is_exactly_the_seven_fields(brazos, dana, wired, address_stories):
    """The shape is the PO's document's, and a field added without this line
    moving is a field nobody decided to publish. `partner_fields` adds nothing
    today, which `BR-INT-054` says is the finished answer for this module."""
    body = _records(brazos)
    for record in body["records"]:
        assert list(record) == [
            "id",
            "consumer_no",
            "customer_name",
            # ── `CR-111-BRC04` ─────────────────────────────────────
            # ⚠ **THE NAME IN TWO HALVES, BESIDE THE WHOLE.** We hold ONE name
            # column, so the split is a PRESENTATION of a fact we do not have
            # (`seams/customers.split_name`) and keeping `customer_name` is what
            # makes it lossless: `first + " " + last` reassembles the original
            # exactly, for every input, which is asserted separately.
            "first_name",
            "last_name",
            # `DEF-INT-9796` (PO 2026-10-06 D3 (a)) — a company's legal name,
            # null for a person; announced in the release notes.
            "organization_name",
            "email",
            "phone",
            "status",
            # The status as a WORD, for a partner that shows it rather than
            # branching on it. It IS `status["label"]`, not a second vocabulary.
            "status_display",
            # ⚠ **HARD RULE 8, BOTH LEGS, IN ONE PLACE.** The service address is
            # WALKED to the premises; the billing address is the account's own
            # `kind='mailing'` row, falling back to the service address. Serving
            # both under one key rather than two top-level fields is what lets a
            # partner see that they are THE SAME address for most accounts.
            "territory_data",
            "address",
        ], record
        assert set(record["status"]) == {"code", "label"}
        assert set(record["territory_data"]) == {"service_address", "billing_address"}
        # ⚠ **`opening_balance` AND `remote_plan_id` ARE NOT HERE AND THAT IS
        # DELIBERATE (`DEF-INT-5587`).** Both cost a statement PER ACCOUNT, so
        # they are served on `consumer-info` — a lookup by number — and not on a
        # route that walks 40,000 accounts. `remote_plan_id` is consumer-info-only
        # by PO ruling 2026-09-17 in any case.
        assert "opening_balance" not in record and "remote_plan_id" not in record


# ══════════════════════════════════════════════════════════════════════════
# `DEF-INT-5623` — THE OLD ADDRESS, ANSWERING FOR ITSELF
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
def test_the_old_address_answers_410_and_names_the_new_one(brazos, dana, wired) -> None:
    """⚠ **THE WIRING IS NOT THE ANSWER, SO THIS CASE ASKS THE ROUTE.**

    `test_def_int_5622_5623_account_vocabulary.py` asserts that `customers` is
    registered and that `RETIRED_FOR` names its replacement. Both can be true
    of a view that raises, returns a `404`, or serves a page of accounts at the
    old address for ever — which is the whole reason the address was renamed.
    So this drives the real view and reads the body.

    **WHY A `410` AND NOT A `404`.** On this surface `404` IS the refusal — the
    same five words a stolen key gets (`BR-INT-044`) — so a deleted address
    would tell a partner holding yesterday's document that their KEY was bad
    and send their engineer to their credentials. `410` says *finished* and
    names where to go.
    """
    serve.reset_partner_limits()
    response = _get(brazos, partner_api.partner_customers_retired, path="/partner/v1/customers")
    assert response.status_code == 410, _body(response)
    body = json.loads(_body(response))
    assert body["code"] == "RETIRED"
    assert body["replaced_by"] == "/partner/v1/accounts"
    assert body["replaced_by"] == partner_api.RETIRED_FOR["customers"], (
        "the view and the map must not name different replacements"
    )


@pytest.mark.django_db
def test_a_stranger_at_the_old_address_learns_nothing(brazos, dana, wired) -> None:
    """⚠ **A RETIREMENT NOTICE HANDED TO ANYONE WHO ASKS IS AN ENUMERATION
    ORACLE**, and it arrives through the one door nobody thinks to lock: it
    would answer *this utility exists, and it used to serve customers* to a
    caller with no key at all. `_serve_retired` authenticates FIRST, exactly as
    every other route does, so a bad key gets the same bytes here as anywhere.
    """
    serve.reset_partner_limits()
    response = _get(
        brazos,
        partner_api.partner_customers_retired,
        key="sbh_live_never_issued",
        path="/partner/v1/customers",
    )
    assert response.status_code == 404
    assert _body(response) == (
        b'{"error": "We cannot serve this request.", "code": "REFUSED"}'
    )


@pytest.mark.django_db
def test_the_retired_address_is_a_row_a_manager_can_see(brazos, dana, wired) -> None:
    """A partner still calling a finished address every night is exactly the
    thing a manager should be able to read in words on S142."""
    from apps.integrations import models as int_models

    serve.reset_partner_limits()
    _get(brazos, partner_api.partner_customers_retired, path="/partner/v1/customers")
    with tenant_ctx(brazos):
        run = int_models.IntegrationRun.objects.order_by("-started_at").first()
    assert run is not None
    assert "retired address" in (run.summary or ""), run.summary
    assert KEY not in (run.summary or ""), "a run record naming a secret is a leaked secret"

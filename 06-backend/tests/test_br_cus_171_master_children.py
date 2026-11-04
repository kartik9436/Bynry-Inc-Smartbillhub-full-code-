# ── Trace ──────────────────────────────────────────────
# Rule:     BR-CUS-171 (a master's children are the OCCUPYING accounts on its
#           premises — DERIVED from the premises, never stored; PO ruling
#           2026-08-27 closing OQ-531, reading (A) BY PREMISES)
# Pin:      **NO COLUMN.** `accounts` gains no parent id and no migration is
#           written: the link is read from the premises every time it is asked
#           for, so a move-in makes a child and a move-out unmakes one with
#           nobody maintaining anything.
# Rules:    BR-CUS-068 (a master account anchors on a common area and covers
#           the rest through its open service agreements) · BR-CUS-055
#           (occupancy keys off the behaviour CLASS, never the label) ·
#           BR-CUS-018 (a draft account never derives occupancy)
# OQs:      OQ-531 (CLOSED 2026-08-27) · OQ-532 (CLOSED 2026-08-27, option B —
#           a master already on the ladder JOINS at the next tier; nothing here
#           seeds it. ⚠ This line read OQ-580 and OPEN until DEF-2950)
# CR:       CR-040 task B5 — *"the master account gets sub-accounts"*
# Impacts:  apps/customers/selectors.py · apps/customers/move_out_settlement.py
# ───────────────────────────────────────────────────────
"""BR-CUS-171 — the parent/child link, and it was already true.

**THE ONE ASSERTION THIS FILE EXISTS FOR is tc1:** an ordinary account on a
premises whose common areas a master covers is a CHILD of that master, with no
column written and no clerk action taken. CR-040 sized B5 as *"the master
account gets sub-accounts"* and OQ-531's closure re-read it: `500 Main
Street`'s five accounts have been children of `AC-2026-00052` since the day
both were seeded, so what was missing was the READ, not the data.

**PROVED RED FIRST (hard-won law 7).** Before `sub_accounts_for_master`
existed, `GET /accounts/{id}` served no `sub_accounts` key at all and
`GET /accounts/{id}/close-impact` served no `open_sub_accounts` — the field
`07-frontend/src/features/customers/moveShared.tsx` has TYPED AND RENDERED
since 2026-08-24. tc5 is that assertion in its inverted form: with the read
disabled, a master with two live tenants answers `0`, which is the number the
screen printed for two days and the number OQ-531 recorded it printing.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import services as metering_services

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = date(2026, 8, 1)


def _plan(tenant, *, services=("electric",)):
    return make_plan(tenant, name="Small Commercial", services=list(services))


def _premises(actor):
    return make_premises(
        actor,
        address_line="1408 Elm St",
        premises_type="apartment_complex",
        owner_manager="Miller Property LLC",
        services_available=["electric", "water"],
    )


def _common_area(actor, premises, plan, *, label, service="electric"):
    unit = make_unit(
        actor,
        premises["id"],
        label=label,
        unit_type="common_area",
        is_common_area=True,
        services=[service],
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


def _ordinary_unit(actor, premises, plan, *, label, service="electric"):
    unit = make_unit(actor, premises["id"], label=label, services=[service])
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    return unit


def _declare_owner(actor, premises, master):
    """⚠ **ADDED 2026-08-30 — DECLARE THE PREMISES' OWNER, BECAUSE THE LINK IS
    NO LONGER DERIVED FROM THE BUILDING'S SHAPE.**

    `DEF-650`, PO ruling 2026-08-27, verbatim: *"so premises owner is master
    accountin system … Bascially Premises -> owner = Master account"*, and on
    the derivation this file was written against (decision 4):

      > *"to find a building's master today, the code does not look at the owner
      > at all — it looks at the building's COMMON AREAS (the hallway, the car
      > park) and finds the account that pays for them. Whoever pays for the
      > hallway is treated as the owner. … The ruling replaces all of it: the
      > premises names its owner, the owner is the master, and nothing is
      > inferred from hallways. The old path is retired rather than kept as a
      > fallback, because a fallback that disagrees with the declared owner
      > would silently bill a different party."*

    So `create_master_account` alone no longer makes anybody's master:
    `customer_selectors.master_account_for` reads `premises → owner →
    master_account_id` and answers `None` where nothing is declared, which is
    honest and is fixed by declaring the owner rather than by inferring one.
    ⚠ **IT LINKS THE PARTY THE SHARED FIXTURE ALREADY MADE — IT DOES NOT MAKE A
    SECOND ONE.** `make_premises` has attached a typed owner since BR-MET-401
    (*"without owner how you can create premsies"*), reusing the party by name
    through the product's own `resolve_owner_name`. Creating another here would
    hit the unique-name refusal, and worse, would leave the address pointing at
    a party that is not the one under test. So the only act left is the one
    `DEF-650` says was missing: **saying which ACCOUNT that owner is billed
    through** (`link_owner_master_account`, BR-MET-400).
    """
    from apps.metering import premises_owners

    owner = premises["owner"]
    assert owner, "make_premises must attach a typed owner (BR-MET-401)"
    premises_owners.link_owner_master_account(actor, owner["id"], master.id)
    return owner


def _master(actor, premises):
    # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
    top_up_homes(actor, premises["id"])
    return customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            # ⛔ **`BR-CUS-1024` — THE MASTER DOOR IS GATED TOO, AND IT NEEDS A
            # `customer` BLOCK EVEN WITH NO `contact` IN THE PAYLOAD.** When one
            # is absent this door builds the contact from the premises' own
            # free-text `owner_manager` (PO 2026-08-22, *"payer = the premises'
            # owner/manager"*), so a party IS presented and the refusal fires —
            # which is why "no contact" is safe at `POST /accounts` and is NOT
            # safe here. The party named is therefore the owner the door would
            # otherwise have minted from, as a COMPANY: the seeded owner is
            # `Whitfield Rentals LLC` and a landlord is an organisation whatever
            # the account TYPE says. Same shape as every other fixture in the
            # repo: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                premises.get("owner_manager") or "Owner", kind="company"
            ),
        },
    )


def _occupying_account(actor, unit, *, name="Elena Rivera"):
    """An ACTIVE ordinary account on `unit` — a tenant, not a draft.

    `create_account` opens a DRAFT (BR-CUS-018: *"a draft account never derives
    occupancy and does not block the unit"*), which is exactly the distinction
    tc3 below is written about, so activation is a separate deliberate step
    here as it is in the product."""
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
            "addresses": [
                {"kind": "mailing", "line1": "1408 Elm St", "city": "Katy", "state": "TX"}
            ],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


# ══════════════════════════════════════════════════════════════════════════
# THE PIN
# ══════════════════════════════════════════════════════════════════════════
def test_br_cus_171_tc1__an_occupying_account_is_the_masters_child_with_no_column(brazos, dana):
    """**The link, both ways, and NOTHING WAS WRITTEN TO MAKE IT TRUE.**

    PO 2026-08-27: *"out of U1 to U5 - has accounts - regular accounts - all
    these accounts are child of Owner A"*.

    ⚠ **AMENDED 2026-08-30 — THE OWNER IS NOW DECLARED, BECAUSE THE SAME DAY'S
    OTHER RULING RETIRED THE GEOMETRY (`DEF-650`, decision 4).** This case built
    a common area, put a master over it, and expected `master_account_for` to
    find the master by walking hallways. That walk is gone — *"the premises
    names its owner, the owner is the master, and nothing is inferred from
    hallways"* — so the inverse read answered `None` and the two directions
    disagreed. The fixture now says which party owns the building and which
    account that party is billed through (`_declare_owner`), which is what a
    clerk does on the premises screen, and the assertion below is once again
    about what it was written to be about: the two reads AGREE.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        unit_a = _ordinary_unit(dana, premises, plan, label="Unit A")
        unit_b = _ordinary_unit(dana, premises, plan, label="Unit B")
        master_dict = _master(dana, premises)
        master = customer_models.Account.objects.get(pk=master_dict["id"])
        _declare_owner(dana, premises, master)

        tenant_a = _occupying_account(dana, unit_a, name="Elena Rivera")
        tenant_b = _occupying_account(dana, unit_b, name="Marcus Webb")

        children = customer_selectors.sub_accounts_for_master(master)
        assert {row.account_no for row in children} == {
            tenant_a.account_no,
            tenant_b.account_no,
        }
        # …and the inverse read agrees, which is what stops the child list and
        # BR-CUS-097's transfer target ever naming two different accounts.
        assert customer_selectors.master_account_for(tenant_a).id == master.id
        assert customer_selectors.master_account_for(tenant_b).id == master.id

        # ⚠ NO COLUMN. The whole of BR-CUS-171 is that this is derived, so the
        # test asserts the SCHEMA as well as the answer: an `accounts` parent id
        # would be a second place for this fact to be wrong.
        columns = {field.name for field in customer_models.Account._meta.get_fields()}
        assert "parent_account" not in columns
        assert "parent_account_id" not in columns
        assert "master_account" not in columns


def test_br_cus_171_tc2__a_master_is_not_its_own_child(brazos, dana):
    """A landlord is not one of their own tenants — and without the guard they
    would be, because a master anchors on a common area OF THE PREMISES IT
    COVERS and would answer itself on every read."""
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        master = customer_models.Account.objects.get(pk=_master(dana, premises)["id"])

        assert customer_selectors.sub_accounts_for_master(master) == []
        assert customer_selectors.master_account_for(master) is None


def test_br_cus_171_tc3__a_draft_account_is_not_a_child_and_a_closed_one_stops_being_one(
    brazos, dana
):
    """BR-CUS-055 — occupancy keys off the behaviour CLASS, never the label.

    This is what makes the link maintenance-free: nobody un-ticks anything when
    a tenant leaves, and nobody ticks anything when one is half-signed-up.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        unit_a = _ordinary_unit(dana, premises, plan, label="Unit A")
        master = customer_models.Account.objects.get(pk=_master(dana, premises)["id"])

        # A DRAFT: created, not activated. BR-CUS-018 — it does not occupy.
        draft = customer_services.create_account(
            dana,
            {
                "unit_id": str(unit_a["id"]),
                "account_type": "residential",
                "opened_at": OPENED.isoformat(),
                "contact": {"full_name": "Not Yet Rivera"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Not Yet Rivera", account_type="residential"
                ),
                "addresses": [
                    {"kind": "mailing", "line1": "1408 Elm St", "city": "Katy", "state": "TX"}
                ],
            },
        )
        assert customer_selectors.sub_accounts_for_master(master) == []

        # Activated: now a child, with nothing else changing.
        customer_services.activate_account(dana, draft["id"])
        assert [row.account_no for row in customer_selectors.sub_accounts_for_master(master)] == [
            draft["account_no"]
        ]


def test_br_cus_171_tc4__the_link_is_served_on_the_account_read(brazos, dana):
    """`GET /accounts/{id}` carries `sub_accounts` and `master_account`.

    Hard-won law 2 — built is not wired. A derivation nothing serves is a
    function, not a feature.

    ⚠ **AMENDED 2026-08-30 for the same reason as tc1** — `DEF-650` retired the
    hallway derivation and the account read now serves the DECLARED owner, so
    the fixture declares one. See `_declare_owner`.
    """
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        unit_a = _ordinary_unit(dana, premises, plan, label="Unit A")
        master = customer_models.Account.objects.get(pk=_master(dana, premises)["id"])
        _declare_owner(dana, premises, master)
        tenant_a = _occupying_account(dana, unit_a)

        owner_view = customer_selectors.account_detail_dict(master)
        assert [row["account_no"] for row in owner_view["sub_accounts"]] == [tenant_a.account_no]
        assert owner_view["master_account"] is None

        tenant_view = customer_selectors.account_detail_dict(tenant_a)
        assert tenant_view["sub_accounts"] == []
        assert tenant_view["master_account"]["account_no"] == master.account_no


def test_br_cus_171_tc5__open_sub_accounts_is_measured_and_the_old_zero_is_the_red(brazos, dana):
    """**THE RED PROOF, in its inverted form (hard-won law 7).**

    `open_sub_accounts` is a field the move-out screen has RENDERED since
    2026-08-24 and no backend has ever served — OQ-531 recorded it as *"renders
    `0` on every tenant until this is ruled"*. Here the same premises with two
    live tenants answers **2**; with the derivation disabled it answers **0**,
    which is the figure the screen printed and which said *"this landlord has
    no tenants"* about a building with two.
    """
    from apps.customers import move_out_settlement

    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        _common_area(dana, premises, plan, label="Hallway & exterior lighting")
        unit_a = _ordinary_unit(dana, premises, plan, label="Unit A")
        unit_b = _ordinary_unit(dana, premises, plan, label="Unit B")
        master = customer_models.Account.objects.get(pk=_master(dana, premises)["id"])
        _occupying_account(dana, unit_a, name="Elena Rivera")
        _occupying_account(dana, unit_b, name="Marcus Webb")

        # Non-vacuous first (DEF-828's shape): the set is not empty before
        # anything is asserted about the count it produces.
        assert len(customer_selectors.sub_accounts_for_master(master)) == 2

        settlement = move_out_settlement.settlement_for(
            dana, master.id, final_bill=Decimal("0.0000")
        )
        assert settlement["open_sub_accounts"] == 2


def test_br_cus_171_tc6__a_standalone_account_has_no_master_and_that_is_an_answer(brazos, dana):
    """A premises with no master account makes nobody anybody's child, and the
    read says so rather than reaching for the nearest owner."""
    with tenant_ctx(brazos):
        plan = _plan(brazos)
        premises = _premises(dana)
        unit_a = _ordinary_unit(dana, premises, plan, label="Unit A")
        tenant_a = _occupying_account(dana, unit_a)

        assert customer_selectors.master_account_for(tenant_a) is None
        assert customer_selectors.account_detail_dict(tenant_a)["master_account"] is None

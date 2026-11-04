# ── Trace ──────────────────────────────────────────────
# Change:  CR-056 W1 tasks 5–10 — the owner's account moves from a common-area
#          UNIT to the ADDRESS.   Screens: S17 · S21 · PRM-02
# Rules:   BR-CUS-1010 (a Master Account is the owner's account AT AN ADDRESS) ·
#          BR-CUS-1011 (one owner account per address) · BR-CUS-1012 (an account
#          that names no unit neither occupies nor blocks one) ·
#          BR-MET-1010 (`ensure_owner_master_account` is a working door) ·
#          BR-CUS-068 (superseded in its anchoring, confirmed in its shape) ·
#          BR-CUS-017 / OQ-092 (the enforcement posture)
# Ruling:  PO 2026-08-31 (`CR-056`) — *every address gets its owner a Master
#          Account, whether or not anything is shared, and whether or not the
#          owner lives there*; and `CR-056` R1, PO verbatim: *"Duplex should be
#          linked to master account of Ajinkya → link this account to customer #
#          that already exist"*.
# Pin:     The money is pinned NEXT DOOR, in
#          `tests/test_br_cus_068_master_bill.py` — 1408 Elm, $41.20 + $28.40 =
#          **$69.60**, on the new plumbing. This file pins the PLUMBING.
# ───────────────────────────────────────────────────────
"""The account hangs off the address — every guard, proved RED first.

⚠ **EACH CASE BELOW NAMES WHAT IT DID BEFORE THE CHANGE** (r11 step 2d,
hard-won law 7). Two of them are the reason this file exists at all rather than
a line in an existing one:

* `tc2` is the failure that would have been TOTAL AND SILENT. `accounts.unit_id`
  became nullable, and `filter(unit_id=None)` compiles to `unit_id IS NULL` — so
  without `BR-CUS-1012`'s guard every owner account in the tenant "occupies" the
  same imaginary unit, and **the second address in the product cannot open an
  account at all.** It was proved by removing the guard and watching the second
  `create_master_account` refuse with `customers.account.unit_already_occupied`
  naming an account on a different street.
* `tc1` is `CR-056` task 9. Before it, a premises with nothing shared refused
  with `reason="no_common_area_units"` — the refusal whose stated reason the
  2026-08-31 ruling removes.
"""

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import owner_selectors, premises_owners
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    make_plan,
    make_premises,
    make_unit,
    owner_for,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

OPENED = "2026-08-01"


def _premises(actor, *, address, owner, premises_type="apartment_complex"):  # CR-162-BRC10: the TYPE decides
    premises = make_premises(
        actor,
        address_line=address,
        premises_type=premises_type,
        owner_manager=owner,
        owner_id=owner_for(actor, owner),
        services_available=["electric", "water"],
    )
    # `BR-CUS-1114` (PO 2026-10-02) — a master account only on a building of
    # two or more homes. Every case here is about WHERE the account hangs, so
    # each address is given two flats and goes on testing that.
    for label in ("Flat 1", "Flat 2"):
        make_unit(actor, premises["id"], label=label)
    return premises


#: ⛔ **THE OWNER CARRIES A TAX ID FROM 2026-09-01 (`BR-CUS-1024`)** — PO
#: verbatim: *"Without identifier we cannot create Customer ID or master account
#: ot regular account"*. Every case in this file is about WHERE the master
#: account hangs (the address rather than a common-area unit) and none is about
#: identity, so the owner is identified once here and they go on testing what
#: they were written to test.
MASTER_OWNER_TAX_ID = "74-2915508"

#: The same identifier, shaped as the `customer` block the premises-owner seam
#: door passes straight through to `create_master_account` (`CR-058`, ruling 2
#: of 2026-09-01: New Connect and this door are under the rule too, because both
#: reach the master door through the customers seam rather than around it).
OWNER_CUSTOMER_BLOCK = {
    "kind": "company",
    "identity": {"tax_id": MASTER_OWNER_TAX_ID},
}


def _master(actor, premises, **extra):
    payload = {
        "premises_id": premises["id"],
        "account_type": "residential",
        "opened_at": OPENED,
        "customer": {
            "display_name": premises.get("owner_manager") or "Owner",
            "kind": "company",
            "identity": {"tax_id": MASTER_OWNER_TAX_ID},
        },
    }
    payload.update(extra)
    return customer_services.create_master_account(actor, payload)


# ══════════════════════════════════════════════════════════════════════════
# tc1 · CR-056 TASK 9 — A PREMISES WITH NOTHING SHARED GETS ITS OWNER AN ACCOUNT
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w1_tc1__a_premises_with_no_common_area_gets_its_owner_an_account(brazos, dana):
    """RED BEFORE: `create_master_account` raised `BIZ_STATE` with
    `params={"reason": "no_common_area_units"}` — because a master had to ANCHOR
    on a common-area unit and a single-family home has none.

    That refusal's stated reason is what the PO removed on 2026-08-31: *every
    address gets its owner a Master Account, whether or not anything is shared.*
    The account now names the ADDRESS and no unit.
    """
    with tenant_ctx(brazos):
        premises = _premises(dana, address="19 Cedar Row", owner="Ajinkya Kulkarni")
        make_unit(dana, premises["id"], label="House")  # a real unit, no common area

        master = _master(dana, premises)

        assert master["kind"] == customer_services.ACCOUNT_KIND_MASTER
        assert master["premises_id"] == premises["id"]
        assert master["unit_id"] is None
        # It covers nothing, so it bills nothing — *no lines, no document*, which
        # is the same ruling's general rule and `CR-056` W4's to build. Nothing
        # here asserts anything about a bill.
        row = customer_models.Account.objects.get(pk=master["id"])
        assert customer_selectors.covered_unit_ids(row) == []
        # And the screen has an address to show even with no unit (B14 rule 32 —
        # a stated absence is CLOSED by default, so the cell is not left blank
        # when the row is holding the fact one column along).
        assert master["premise"] == "19 Cedar Row"
        assert master["unit_label"] is None


# ══════════════════════════════════════════════════════════════════════════
# tc2 · BR-CUS-1012 — A NULL UNIT IS NOT A UNIT (the silent, total failure)
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w1_tc2__a_unit_less_account_does_not_occupy_the_null_unit(brazos, dana):
    """RED BEFORE: with `occupying_accounts_for_unit` left reading
    `filter(unit_id=None)`, the SECOND address refused with
    `customers.account.unit_already_occupied` — naming the owner account of a
    different street, because both matched `unit_id IS NULL`.

    Two addresses, two owners, two accounts. This is the ordinary case for a
    utility with more than one customer, which is every utility.
    """
    with tenant_ctx(brazos):
        first = _premises(dana, address="19 Cedar Row", owner="Ajinkya Kulkarni")
        second = _premises(dana, address="41 Alder Way", owner="Miller Property LLC")

        one = _master(dana, first)
        two = _master(dana, second)

        assert one["unit_id"] is None and two["unit_id"] is None
        assert one["premises_id"] == first["id"]
        assert two["premises_id"] == second["id"]
        assert one["id"] != two["id"]
        # Neither is "occupying a unit", because neither names one.
        assert list(customer_selectors.occupying_accounts_for_unit(None)) == []


def test_cr056_w1_tc2b__a_unit_less_account_does_not_block_a_real_move_in(brazos, dana):
    """The same hazard from the other side: the owner's account must not make
    the units of its own premises unavailable.

    RED BEFORE: the unit-less master matched the `unit_id IS NULL` read, so
    `_refuse_if_unit_occupied` had to be reasoned about rather than measured.
    Here a real tenant moves into a real unit while the owner's account exists.
    """
    with tenant_ctx(brazos):
        premises = _premises(
            dana, address="1408 Elm St", owner="Miller Property LLC",
            premises_type="apartment_complex",
        )
        plan = make_plan(brazos, name="Small Commercial", services=("electric", "water"))
        unit = make_unit(dana, premises["id"], label="Unit A")
        from apps.metering import services as metering_services

        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        _master(dana, premises)

        tenant_account = customer_services.create_account(
            dana,
            {
                "unit_id": unit["id"],
                "account_type": "residential",
                "opened_at": OPENED,
                "status": "active",
                "contact": {"full_name": "R. Alvarez"},
                # `BR-CUS-1024` (2026-09-01) — an account needs an identifier.
                # This case is about a unit-less MASTER account not blocking a
                # real move-in, and not about identity; the tenant is given a
                # phone so the door opens and the case tests what it means to.
                "customer": {
                    "display_name": "R. Alvarez",
                    "kind": "person",
                    "identity": {"phone": "+1 (512) 555-0177"},
                },
            },
        )
        assert tenant_account["unit_id"] == unit["id"]
        # `CR-056` W1 — the ordinary path writes the address too, so the column
        # means the same thing on a row the backfill filled and a row opened
        # today.
        assert tenant_account["premises_id"] == premises["id"]


# ══════════════════════════════════════════════════════════════════════════
# tc3 · BR-CUS-1011 — ONE OWNER ACCOUNT PER ADDRESS
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w1_tc3__a_second_master_at_one_address_refuses_by_name(brazos, dana):
    """RED BEFORE: with `_refuse_if_premises_has_master` removed, the second call
    SUCCEEDED and the premises held two owner accounts — a state every *who owns
    this address* read would then have to break a tie over, which is the failure
    `BR-CUS-171` already records from the days ownership was geometric.

    ⚠ The covered-unit guard cannot catch this one: a premises with no common
    area has no covered unit for it to find.
    """
    with tenant_ctx(brazos):
        premises = _premises(dana, address="19 Cedar Row", owner="Ajinkya Kulkarni")
        first = _master(dana, premises)

        with pytest.raises(errors.BizError) as caught:
            _master(dana, premises)

        assert caught.value.br_ref == "BR-CUS-1011"
        assert caught.value.params["account_no"] == first["account_no"]
        assert caught.value.params["premises_id"] == premises["id"]
        assert (
            customer_models.Account.objects.filter(
                premises_id=premises["id"],
                kind=customer_services.ACCOUNT_KIND_MASTER,
            ).count()
            == 1
        )


# ══════════════════════════════════════════════════════════════════════════
# tc4 · BR-MET-1010 — THE CREATION DOOR NO LONGER RAISES OQ-790
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w1_tc4__ensure_owner_master_account_creates_and_is_idempotent(brazos, dana):
    """RED BEFORE: `NotImplementedError: OQ-790`, on every call.

    `OQ-790` closed on 2026-08-27 (option (c), master immediately) leaving ONE
    obstacle recorded as WORK — *"`create_master_account` anchors on common-area
    units and a new premises has none"* — and `CR-056` W1 removed it.
    """
    with tenant_ctx(brazos):
        premises = _premises(dana, address="19 Cedar Row", owner="Ajinkya Kulkarni")
        owner_id = owner_for(dana, "Ajinkya Kulkarni")

        detail = premises_owners.ensure_owner_master_account(
            dana,
            owner_id,
            payload={
                "account_type": "residential",
                "opened_at": OPENED,
                # `BR-CUS-1024` (2026-09-01) — the owner is identified. This
                # door reaches `create_master_account` through the customers
                # seam and is under the rule with it.
                "customer": OWNER_CUSTOMER_BLOCK,
            },
        )
        account_id = detail["master_account_id"]
        assert account_id

        account = customer_models.Account.objects.get(pk=account_id)
        assert account.kind == customer_services.ACCOUNT_KIND_MASTER
        assert str(account.premises_id) == premises["id"]
        assert account.unit_id is None
        # BR-MET-400's link — the premises' owner IS this account.
        assert (
            owner_selectors.owner_detail_dict(premises_owners._owner_row(owner_id))[
                "master_account_id"
            ]
            == str(account_id)
        )

        # ENSURE, not create-a-second: a second call writes nothing and hands the
        # same account back. Without this, `BR-CUS-1011` would refuse instead —
        # a correct refusal, and the wrong behaviour for a door called *ensure*.
        again = premises_owners.ensure_owner_master_account(
            dana,
            owner_id,
            payload={
                "account_type": "residential",
                "opened_at": OPENED,
                # `BR-CUS-1024` (2026-09-01) — the owner is identified. This
                # door reaches `create_master_account` through the customers
                # seam and is under the rule with it.
                "customer": OWNER_CUSTOMER_BLOCK,
            },
        )
        assert again["master_account_id"] == account_id
        assert customer_models.Account.objects.filter(premises_id=premises["id"]).count() == 1


def test_cr056_w1_tc4b__an_owner_of_two_addresses_refuses_rather_than_picking(brazos, dana):
    """`premises_owners.master_account_id` is a link on the OWNER and an account
    is per ADDRESS, so an owner of two buildings is a question this signature
    cannot answer. It REFUSES BY NAME rather than picking one — naming a premises
    is the caller's job, and `CR-056` W2/W3 own the identity work that would let
    one party hold several accounts properly.
    """
    with tenant_ctx(brazos):
        owner_id = owner_for(dana, "Ajinkya Kulkarni")
        _premises(dana, address="19 Cedar Row", owner="Ajinkya Kulkarni")
        second = _premises(dana, address="41 Alder Way", owner="Ajinkya Kulkarni")

        with pytest.raises(errors.BizError) as caught:
            premises_owners.ensure_owner_master_account(
                dana,
                owner_id,
                payload={
                    "account_type": "residential",
                    "customer": OWNER_CUSTOMER_BLOCK,
                },
            )
        assert caught.value.params["reason"] == "owner_owns_several_premises_name_one"
        assert caught.value.params["premises_count"] == 2

        # Named, it builds — and it builds for the address it was told.
        detail = premises_owners.ensure_owner_master_account(
            dana,
            owner_id,
            second["id"],
            payload={"account_type": "residential", "customer": OWNER_CUSTOMER_BLOCK},
        )
        account = customer_models.Account.objects.get(pk=detail["master_account_id"])
        assert str(account.premises_id) == second["id"]


# ══════════════════════════════════════════════════════════════════════════
# tc5 · CR-056 TASK 6 — THE PRE-MIGRATION SHAPE STILL ANSWERS IDENTICALLY
# ══════════════════════════════════════════════════════════════════════════
def test_cr056_w1_tc5__a_backfilled_legacy_master_reads_exactly_as_it_did(brazos, dana):
    """The 0036 backfill fills `premises_id` IN and moves no `unit_id`, so a
    Master Account created before 2026-09-01 keeps its anchor. This builds that
    exact shape — address AND anchor — and proves every read that decides money
    answers the same thing on it as on an address-only master.

    RED BEFORE: `base_charge_only_coverage` and `master_account_for` read
    `_premises_id_for_unit(account.unit_id)`, which answers `None` for an
    address-only master, so an owner account with no unit collected **none** of
    its empty units' standing charges — the 2026-08-31 per-unit ruling
    ($183.00 on six flats at $30.50) billed as $0.00.
    """
    with tenant_ctx(brazos):
        premises = _premises(
            dana, address="1408 Elm St", owner="Miller Property LLC",
            premises_type="apartment_complex",
        )
        plan = make_plan(brazos, name="Small Commercial", services=("electric", "water"))
        hallway = make_unit(
            dana,
            premises["id"],
            label="Hallway & exterior lighting",
            unit_type="common_area",
            is_common_area=True,
            services=["electric"],
        )
        from apps.metering import services as metering_services

        metering_services.assign_unit_plan(
            dana, hallway["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        master = _master(dana, premises)
        row = customer_models.Account.objects.get(pk=master["id"])

        address_only = customer_selectors.covered_unit_ids(row)
        address_only_premises = customer_selectors.premises_id_for_account(row)

        # Now make it look exactly like a backfilled pre-0036 row: the anchor
        # restored beside the address. Nothing else moves.
        customer_models.Account.objects.filter(pk=row.pk).update(unit_id=hallway["id"])
        legacy = customer_models.Account.objects.get(pk=row.pk)

        assert customer_selectors.covered_unit_ids(legacy) == address_only == [hallway["id"]]
        assert customer_selectors.premises_id_for_account(legacy) == address_only_premises
        assert address_only_premises == premises["id"]

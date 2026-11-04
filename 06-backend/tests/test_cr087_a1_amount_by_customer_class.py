# ── Trace ──────────────────────────────────────────────
# Change:  CR-087 task A1 / PRB-01 — `charge_code_amounts` carries no customer
#          class at all, so a $45.00 residential connection fee and an $85.00
#          commercial one are the same row.
# Rules:   BR-RAT-088 (the base lives on the charge code) · CLAUDE.md hard rule
#          2 (money stored to four, displayed at two) · law 7 (proved RED on the
#          real fault first, in the harness that will run it) · law 14 (a
#          transaction-sensitive case is proved on real PostgreSQL, never on the
#          default sqlite suite).
# ───────────────────────────────────────────────────────
"""The amount a charge code states can differ by customer class.

⚠ **WHY A CODE AND NOT A UUID, WHICH IS THE ONE DESIGN DECISION HERE.**
`plan_deposit_rules` keys its class with `account_type_id`, a UUID, so that
precedent exists. This column follows `size_class` instead — TEXT, holding
`account_types.code` — for a reason that is about the RESOLVER rather than
about taste: `resolution.AccountFacts.customer_class` is a code string, and
`charges.applies_to_customer_classes` is a JSON list of code strings, and the
chain narrows by comparing those two. A UUID here would make the row beside
`applies_to_customer_classes` on the same object narrow by a different key,
and would force an id→code lookup on the hot path for every read.

⚠ **NULL IS NOT A CLASS, IT IS EVERY CLASS**, which is what makes this
additive: every row written before this column existed keeps pricing exactly
what it priced. The same reading `applies_to_customer_classes` already takes
(NULL or `[]` means every class).

⚠ **AND A CLASS-SPECIFIC ROW WINS OVER THE EVERY-CLASS ROW.** That is the
money rule of this task and the reason the tests below state a figure rather
than a shape: a code carrying `$45.00` for every class and `$85.00` for
Commercial must bill a commercial connection `$85.00`, not whichever row the
database happened to return first.
"""
from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from tests.test_us_rat_helpers import *  # noqa: F401,F403
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

WATER_SIZES = (("W-58", 'Water 5/8"'), ("W-2", 'Water 2"'))


def _configure_sizes(tenant):
    from apps.tenancy import models as tenancy_models

    for code, name in WATER_SIZES:
        tenancy_models.MeterSizeClass.objects.update_or_create(
            tenant=tenant, code=code,
            defaults={"name": name, "active": True, "is_system": True},
        )


def _payload(**over):
    p = {"code": "CONN", "name": "Connection fee", "charge_type": "one_time",
         "service": "water", "amount_rule": "flat", "is_base": False}
    p.update(over)
    return p


def _rows(tenant, charge_id):
    with tenant_ctx(tenant):
        return selectors.charge_row(models.Charge.objects.get(id=charge_id))["size_amounts"]


# ── TC1 · the figure the whole task exists for ─────────────────────────────
def test_cr087_a1_tc1__one_code_prices_residential_45_and_commercial_85(env):
    """CR-087's own worked example, expressible for the first time."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin,
            {**(_payload(size_amounts=[
                {"size_class": "W-58", "amount": "45.00"},
                {"size_class": "W-58", "amount": "85.00", "customer_class": "commercial"},
            ])), "effective_from": "2000-01-01"},
        )
    rows = _rows(env.tenant, charge["id"])
    by = {(r["size_class"], r.get("customer_class")): r for r in rows}
    assert by[("W-58", None)]["amount_display"] == "45.00", "the every-class row"
    assert by[("W-58", "commercial")]["amount_display"] == "85.00", "the commercial row"


# ── TC2 · the unique key must actually refuse ──────────────────────────────
def test_cr087_a1_tc2__two_rows_for_the_same_size_and_class_are_refused(env):
    """⚠ POSTGRES TREATS NULLS AS DISTINCT, so one constraint over four columns
    would let TWO every-class rows exist for one size — the exact duplicate the
    old three-column key refused. Two partial constraints are what actually
    refuse, and this asserts BOTH halves."""
    from django.db import IntegrityError, transaction

    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin, {**(_payload(size_amounts=[{"size_class": "W-58", "amount": "45.00"}])), "effective_from": "2000-01-01"}
        )
        row = models.Charge.objects.get(id=charge["id"])
        # a SECOND every-class row for the same size
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.ChargeCodeAmount.objects.create(
                    tenant_id=env.tenant.id, charge=row, size_class="W-58",
                    amount=Decimal("99.00"), customer_class=None)
        # and a second row for the same size AND the same named class
        models.ChargeCodeAmount.objects.create(
            tenant_id=env.tenant.id, charge=row, size_class="W-58",
            amount=Decimal("85.00"), customer_class="commercial")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.ChargeCodeAmount.objects.create(
                    tenant_id=env.tenant.id, charge=row, size_class="W-58",
                    amount=Decimal("90.00"), customer_class="commercial")


# ── TC3 · every row written before this column keeps its price ─────────────
def test_cr087_a1_tc3__a_row_with_no_class_still_prices_every_class(env):
    """The additive half. A code stating one amount and no class is what every
    tenant has today, and it must go on meaning *every class*."""
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        charge = services.create_charge(
            env.admin, {**(_payload(size_amounts=[{"size_class": "W-58", "amount": "45.00"}])), "effective_from": "2000-01-01"}
        )
        stored = models.ChargeCodeAmount.objects.get(charge_id=charge["id"], size_class="W-58")
        assert stored.customer_class is None, "no class named means every class"
        assert stored.amount == Decimal("45.0000")


# ── TC4 · the money rule: a named class BEATS the every-class row ──────────
def test_cr087_a1_tc4__the_commercial_row_wins_for_a_commercial_account(env):
    """⚠ **THIS IS THE ONE THAT DECIDES WHAT A CUSTOMER PAYS.**

    A code carrying $45.00 for every class and $85.00 for Commercial must
    resolve $85.00 for a commercial connection and $45.00 for a residential
    one. Nothing in the database can express that — two partial unique
    constraints keep the rows apart and say nothing about which wins — so the
    precedence lives in the catalogue, where the per-account view is built, and
    it is asserted here rather than assumed.
    """
    from apps.rating import resolution_catalogue

    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        services.create_charge(
            env.admin,
            {**(_payload(size_amounts=[
                {"size_class": "W-58", "amount": "45.00"},
                {"size_class": "W-58", "amount": "85.00", "customer_class": "commercial"},
            ])), "effective_from": "2000-01-01"},
        )
        codes = resolution_catalogue.charge_code_facts("commercial")
        conn = next(c for c in codes if c.code == "CONN")
        assert conn.amounts["W-58"] == Decimal("85.0000"), (
            "a commercial account must be priced by the commercial row"
        )
        codes = resolution_catalogue.charge_code_facts("residential")
        conn = next(c for c in codes if c.code == "CONN")
        assert conn.amounts["W-58"] == Decimal("45.0000"), (
            "a residential account falls back to the every-class row"
        )


# ── TC5 · the BASE read narrows too, or the whole thing is half-built ──────
def test_cr087_a1_tc5__the_base_charge_read_narrows_on_customer_class(env):
    """⚠ **THE SECOND MONEY PATH, AND IT IS NOT THE CATALOGUE.**

    `selectors.base_charge_from_charge_code` is `BR-RAT-088`'s live read — the
    base a charge code states for one service, at one class, at one size — and
    it already TAKES a `customer_class`. It uses it to decide which CODES apply
    (`applies_to_customer_classes`) and then builds its per-size dict with no
    narrowing at all, so two rows for one size differ only by a column it does
    not read: **whichever the database returns last wins**, silently, with no
    error and no refusal.

    A 5/8" water base of $8.00 for everybody and $34.00 for Commercial must
    read $34.00 for a commercial connection and $8.00 for a residential one.
    """
    _configure_sizes(env.tenant)
    with tenant_ctx(env.tenant):
        services.create_charge(
            env.admin,
            {**(_payload(code="BASE-W2", name="Water base", charge_type="recurring",
                     is_base=True,
                     size_amounts=[
                         {"size_class": "W-58", "amount": "8.00"},
                         {"size_class": "W-58", "amount": "34.00",
                          "customer_class": "commercial"},
                     ])), "effective_from": "2000-01-01"},
        )
        commercial = selectors.base_charge_from_charge_code(
            "water", customer_class="commercial", size_class="W-58", named_code="BASE-W2")  # DEF-RAT-9832: named
        assert commercial["refusal"] is None, commercial["refusal"]
        assert commercial["amount"] == Decimal("34.0000"), (
            "a commercial connection must read the commercial base"
        )
        residential = selectors.base_charge_from_charge_code(
            "water", customer_class="residential", size_class="W-58", named_code="BASE-W2")  # DEF-RAT-9832: named
        assert residential["refusal"] is None, residential["refusal"]
        assert residential["amount"] == Decimal("8.0000"), (
            "a residential connection falls back to the every-class base"
        )

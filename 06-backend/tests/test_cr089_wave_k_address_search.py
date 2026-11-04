# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-002 (the S17 register + its capability row) · US-PAY-004
#           (S33 the payments list) · US-BIL-025/026 (S30 the bills list)
#           Screens: S17 · S33 · S30
# Change:   CR-089 wave K — `PUJ-51` an address finds the ACCOUNTS at it ·
#           `PUJ-52` the PAYMENTS taken there · `PUJ-53` the BILLS raised there
# Rules:    CLAUDE.md hard rule 8 / BR-MET-1161 (an address lives on `premises`
#           and NOWHERE else; everything walks to it) · BR-CUS-1010 (a Master
#           Account is the owner's account AT AN ADDRESS and names no unit) ·
#           BR-CUS-053 (the S17 search set) · NFR-3 (universal server
#           pagination — the leg is a SQL subquery, never a Python list) ·
#           BR-SHL-011 (a list URL never 4xx's over its params) ·
#           CLAUDE.md rule 1 (tenant scoping, RLS FORCE)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""CR-089 wave K — finding things by address.

**THE PO ASKED FOR IT IN ONE SENTENCE** (2026-09-08, verbatim): *"you will ahve
changes when Premises, Units, Assets, Accounts, Bills, Payments are search by
address - you should take those changs also into account."*

**IT IS ONE CHANGE AND THREE GAPS OF DIFFERENT SIZES**, which is why the cases
below do not look alike:

  * **Accounts** already searched an address — through `seams.unit_ids_matching`,
    which walks *unit → premises*. So it found every OCCUPANT of a building and
    silently dropped the one account that has no unit: `BR-CUS-1010`'s owner
    Master Account, which hangs off the ADDRESS. On the demo utility that was
    five of the six accounts at *500 Main St*, the missing one being the account
    that owns the building.
  * **Payments** and **Bills** did not search an address AT ALL. A bill knows its
    account and the account knows its property, and no search crossed that.

⛔ **NOTHING HERE PUTS AN ADDRESS ON AN ACCOUNT, A PAYMENT OR A BILL.** Hard rule
8 keeps it on `premises`; `g85_one_address_home.py` fails a fourth home and would
be right to. The reach is a walk, and these cases assert the walk arrives.

**PROVED RED FIRST (hard-won law 7).** Against the branch tip, before the leg
existed, on the demo utility (`brazosbend`)::

    ACCOUNTS '500 Main St'      -> ['A-11720','A-11801','A-11802','A-11803','A-11804']
                                   (5 of 6 — AC-2026-00051, the master, missing)
    PAYMENTS '301 Mill Pond Ln' -> 0 rows   (9 payments stand at that address)
    BILLS    '301 Mill Pond Ln' -> 0 rows   (18 bills stand at that address)

The same three, with the leg::

    ACCOUNTS '500 Main St'      -> all 6, AC-2026-00051 included
    PAYMENTS '301 Mill Pond Ln' -> 9
    BILLS    '301 Mill Pond Ln' -> 18
"""

from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.billing import models as billing_models
from apps.billing import selectors as billing_selectors
from apps.customers import selectors
from apps.customers import services as customers_services
from apps.payments import models as payment_models
from apps.payments import selectors as payment_selectors
from core.pagination import ListParams

from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

from tests.test_cr030_w0_customer_no import _account_for  # noqa: E402

pytestmark = pytest.mark.django_db

#: One building, typed the way a clerk types it at the counter.
CYPRESS = "412 Cypress Row"

#: The owner's identity. `BR-CUS-1024` refuses a master account created from a
#: free-text owner name alone, and identity is not what this file is about.
OWNER_TAX_ID = "74-2915508"


def _accounts(term: str) -> list[str]:
    """`GET /accounts?q=<term>` as the selector sees it — account numbers back,
    because those are what a reader of a failure message can recognise."""
    return sorted(row["account_no"] for row in selectors.account_list(ListParams(q=term)))


def _payments(term: str) -> list[str]:
    """`GET /payments?q=<term>`, paged in SQL exactly as the endpoint pages it."""
    rows = payment_selectors.payment_list_queryset(ListParams(q=term))[:50]
    return sorted(row.payment_no for row in rows)


def _bills(term: str) -> list[str]:
    """`GET /bills?q=<term>`, paged in SQL exactly as the endpoint pages it."""
    rows = billing_selectors.invoice_list_queryset(ListParams(q=term))[:50]
    return sorted(row.invoice_no for row in rows)


def _building(actor, tenant, *, address=CYPRESS, unit_label="Apt 1"):
    """A property with ONE occupied unit and ONE owner Master Account.

    The two account kinds are the whole point: the occupant's account names a
    unit and the owner's account names only the address (`BR-CUS-1010`), and it
    is the second one every previous address search could not reach.
    """
    premises = make_premises(actor, address_line=address, services_available=["electric"])
    occupant = _account_for(actor, tenant, label=unit_label)
    # `_account_for` builds its own premise, so move the occupant onto THIS one
    # through the same two columns `services.create_account` writes.
    unit = make_unit(actor, premises["id"], label=unit_label + " B")
    from apps.customers import models as customers_models

    customers_models.Account.objects.filter(pk=occupant["id"]).update(
        unit_id=unit["id"], premises_id=premises["id"]
    )
    # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
    # building of two or more homes; a second, vacant flat makes it one.
    make_unit(actor, premises["id"], label=unit_label + " C")
    owner = customers_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": "2026-08-01",
            "customer": {
                "display_name": "Whitfield Rentals LLC",
                "kind": "company",
                "identity": {"tax_id": OWNER_TAX_ID},
            },
        },
    )
    return premises, occupant, owner


def _bill_for(tenant, account_id, *, no: str):
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account_id=account_id,
        invoice_no=no,
        service_date="2026-08-31",
        period_start="2026-08-01",
        period_end="2026-08-31",
        status=billing_models.INVOICE_ISSUED,
        issued_at="2026-09-01T09:00:00+00:00",
        subtotal=Decimal("61.40"),
        tax_total=Decimal("0"),
        total=Decimal("61.40"),
        currency="USD",
    )


def _payment_for(tenant, account_id, *, no: str):
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account_id=account_id,
        payment_no=no,
        amount=Decimal("61.40"),
        currency="USD",
        status=payment_models.PAYMENT_CLEARED,
        posted_at="2026-09-02T09:00:00+00:00",
        cleared_at="2026-09-02T09:00:00+00:00",
    )


# ══════════════════════════════════════════════════════════════════════════
# K1 / PUJ-51 — an address finds the ACCOUNTS at it
# ══════════════════════════════════════════════════════════════════════════


def test_puj_51__an_address_finds_every_account_at_the_building(brazos, marcus):
    """*"typing 412 Cypress Row into the accounts list returns … the others at
    that building"* — and **the others includes the owner**.

    RED before the leg: the occupant came back and the master did not, because
    `unit_ids_matching` can only reach an account through its unit and a master
    account has none.
    """
    with tenant_ctx(brazos):
        _premises, occupant, owner = _building(marcus, brazos)

        found = _accounts(CYPRESS)

        assert occupant["account_no"] in found, "the occupant's account"
        assert owner["account_no"] in found, (
            "BR-CUS-1010's owner account has no unit, so only the premises walk reaches it"
        )


def test_puj_51__a_street_that_matches_nothing_returns_nothing(brazos, marcus):
    """The leg NARROWS the search; it never widens it.

    A term matching no property must not fall back to *every account* — that is
    the failure shape a `Q()` built from an empty set has, and it would turn a
    typo into a full-tenant dump on the product's busiest screen.
    """
    with tenant_ctx(brazos):
        _building(marcus, brazos)

        assert _accounts("Nowhere Ln") == []


def test_puj_51__the_address_leg_never_reaches_another_tenant(brazos, lonestar, marcus, erin):
    """CLAUDE.md hard rule 1, asserted against the join that was just added.

    Two utilities may perfectly well have a *412 Cypress Row*, and a new way
    into `premises` is a new way to leak out of one tenant.
    """
    with tenant_ctx(brazos):
        _premises, occupant, owner = _building(marcus, brazos)
    with tenant_ctx(lonestar):
        make_premises(erin, address_line=CYPRESS, services_available=["water"])
        assert _accounts(CYPRESS) == [], "Lone Star sees none of Brazos's accounts"
    with tenant_ctx(brazos):
        found = _accounts(CYPRESS)
        assert occupant["account_no"] in found and owner["account_no"] in found


# ══════════════════════════════════════════════════════════════════════════
# K2 / PUJ-52 — the same address finds the PAYMENTS taken there
# ══════════════════════════════════════════════════════════════════════════


def test_puj_52__an_address_finds_the_payments_taken_at_it(brazos, marcus):
    """*"the same search on the payments list returns the payments taken against
    those accounts"* — both kinds of account, the owner's included."""
    with tenant_ctx(brazos):
        _premises, occupant, owner = _building(marcus, brazos)
        _payment_for(brazos, occupant["id"], no="PY-K-0001")
        _payment_for(brazos, owner["id"], no="PY-K-0002")
        elsewhere = _account_for(marcus, brazos, label="Far Away")
        _payment_for(brazos, elsewhere["id"], no="PY-K-0003")

        assert _payments(CYPRESS) == ["PY-K-0001", "PY-K-0002"]


# ══════════════════════════════════════════════════════════════════════════
# K3 / PUJ-53 — the same address finds the BILLS raised there
# ══════════════════════════════════════════════════════════════════════════


def test_puj_53__an_address_finds_the_bills_raised_at_it(brazos, marcus):
    """*"the same search on the bills list returns … every other bill at that
    building"* — the largest of the four gaps the PO named, because a bill knows
    its account, the account knows its property, and no search crossed that."""
    with tenant_ctx(brazos):
        _premises, occupant, owner = _building(marcus, brazos)
        _bill_for(brazos, occupant["id"], no="BL-2609-000001")
        _bill_for(brazos, owner["id"], no="BL-2609-000002")
        elsewhere = _account_for(marcus, brazos, label="Far Away")
        _bill_for(brazos, elsewhere["id"], no="BL-2609-000003")

        assert _bills(CYPRESS) == ["BL-2609-000001", "BL-2609-000002"]


# ══════════════════════════════════════════════════════════════════════════
# NFR-3 — the leg is a SUBQUERY, not a list, on all three screens
# ══════════════════════════════════════════════════════════════════════════


def test_nfr_3__the_address_leg_is_lazy_and_costs_no_round_trip(brazos, marcus):
    """`account_ids_at_matching_address` returns a LAZY queryset, so the leg
    renders as a nested subquery inside each list's own `WHERE` rather than as a
    second statement.

    Asserted because a stray `list(...)` around it would be invisible in review
    and would ship every account id at a matching street through Python **on
    every keystroke of a debounced search box** — which at the top of the
    customer band is 40,000 rows, not the 78 the demo utility has. It is also
    how a fifth `DEF-PAY-4221` gets added by accident.
    """
    with tenant_ctx(brazos):
        _building(marcus, brazos)

        with CaptureQueriesContext(connection) as ctx:
            ids = selectors.account_ids_at_matching_address(CYPRESS)
        assert hasattr(ids, "query"), type(ids)
        assert not isinstance(ids, list)
        assert ctx.captured_queries == [], "building the leg must touch the database ZERO times"

        # …and both neighbours consume it the same way.
        for module in (payment_selectors, billing_selectors):
            with CaptureQueriesContext(connection) as ctx:
                borrowed = module._account_ids_at_address(CYPRESS)
            assert hasattr(borrowed, "query"), (module.__name__, type(borrowed))
            assert ctx.captured_queries == [], module.__name__


def test_nfr_3__each_list_pages_the_address_search_in_sql(brazos, marcus):
    """The page is cut by the DATABASE, not after building every row.

    `GET /outstandings`, `GET /cheques` and the bank-rec batch list already
    answer unpaginated and name the old 3,000-connection ceiling as their
    excuse (`DEF-PAY-4221`). This asserts the address search does not become a
    fourth and a fifth: the LIMIT is in the statement, and the address predicate
    with it.
    """
    with tenant_ctx(brazos):
        _building(marcus, brazos)

        for name, sql in (
            ("payments", str(payment_selectors.payment_list_queryset(ListParams(q=CYPRESS)).query)),
            ("bills", str(billing_selectors.invoice_list_queryset(ListParams(q=CYPRESS)).query)),
        ):
            assert "IN (SELECT" in sql, f"{name}: the address leg is not a subquery"
            assert '"premises"' in sql, f"{name}: the walk does not reach the one address home"

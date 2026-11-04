# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-019 (the BR-CUS-054 customer entity and its link table) —
#           CR-060 **C16**, task **T17**
# Rules:    BR-CUS-054 as AMENDED by CR-060 C16 (sum within a customer, never
#           across; a jointly-held account in FULL to each holder; a weak or
#           untiered link shown and MARKED) · BR-CUS-089 (the tier and its
#           confirmer are stored, and an import link carries none) ·
#           BR-REP-002 (read models over the books, never a side-maintained
#           number) · DEF-127 (an absence is never spelled like a zero) ·
#           B14 rule 31 (no database id is a visible value)
# ───────────────────────────────────────────────────────
"""CR-060 C16 — **the customer statement**, and its four money rules.

*"One customer, their accounts, each balance, a total across them."* **ZERO
SCHEMA:** the link table has carried the pair, the confidence tier and the
confirmer since `BR-CUS-054` shipped, and every figure here is the LEDGER's own
per-account Σ reached through the customers seam. This is a door, not a
derivation.

**THE WORKED FIGURE IS SIGNED AND IS NOT MOVED BY ANY OF THIS.** LE-1's four
customer accounts hold **152.32** of receivables between them — the same number
`test_us_led_ledger_api` asserts as the trial balance's AR row and as S36's
*Still owed*, grouped three ways. Link all four to one customer and their
statement totals **152.32**; that is the one derivation reaching a third
surface, and if it ever reads anything else, one of the three is lying.

⚠ **THE LINKS ARE WRITTEN THROUGH THE ORM, DELIBERATELY, AND THAT NEEDS SAYING.**
`CR-056` is explicit that exactly one function writes a customer-to-account link
and it runs inside an import — so linking through the real door here would mean
staging an import file to test a REPORT. **The door under test is the
statement.** What matters is that each link's stored `match_tier` is the one
`BR-CUS-089` would have written, and every case below states it.

⚠ **PROVED RED FIRST (hard-won law 7).** Before `selectors.customer_statement`
existed, every case in this file failed on the same line:

    AttributeError: module 'apps.customers.selectors' has no attribute
    'customer_statement'

and the endpoint case on `AttributeError: module 'apps.customers.api' has no
attribute 'customer_statement'`.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from core import errors

from tests.ledger_le_fixtures import LE1_AR, make_accounts, post_le1_month
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import FakeUser, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

#: LE-1's four accounts, and the receivable they hold between them.
ALL_FOUR = ("ACC-1042", "ACC-1051", "ACC-1055", "ACC-0009")


def a_month(tenant, actor):
    accounts = make_accounts(actor, tenant, {})
    post_le1_month(tenant, accounts)
    return accounts


def a_customer(tenant, *, no, name, kind="person"):
    return customers_models.Customer.objects.create(
        tenant_id=tenant.id, customer_no=no, display_name=name, kind=kind
    )


def link(tenant, customer, account, *, tier="strong"):
    """One `customer_accounts` row, with the tier `BR-CUS-089` would have
    stored. `tier=None` is the IMPORT's own state and is a real one — the bulk
    import matches on the legacy id, which is a reconciliation key and not
    identity evidence, so it writes no tier at all."""
    return customers_models.CustomerAccount.objects.create(
        tenant_id=tenant.id,
        customer=customer,
        account=account,
        match_tier=tier,
        match_basis="name, date of birth and government id" if tier else None,
    )


def statement(tenant, customer):
    return customers_selectors.customer_statement(str(customer.id))


def call(tenant, **query):
    return api_call(
        customers_api.customer_statement,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=tenant,
        query=query or None,
    )


# ═══════════════════════════════════════════════════════════════════════════
# C16 proof 1 — one customer with several accounts sums to their total
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__the_total_is_the_sum_of_the_rows_and_it_is_the_signed_figure(brazos, dana):
    """All four of LE-1's accounts on one landlord: **152.32**, which is the
    number the trial balance and S36 already state about the same books."""
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        landlord = a_customer(brazos, no="C-1000", name="Alvarez Property Co", kind="business")
        for key in ALL_FOUR:
            link(brazos, landlord, accounts[key])

        result = statement(brazos, landlord)
        assert result is not None
        assert result["available"] is True
        assert result["account_count"] == 4
        assert Decimal(result["total"]) == LE1_AR == Decimal("152.32")
        # The total IS the rows — not a second query that happens to agree.
        assert sum(Decimal(row["balance"]) for row in result["rows"]) == Decimal(result["total"])
        # Every money member is the exact decimal STRING with its CHAR(3)
        # beside it (CLAUDE.md rule 2) — a float here is how 152.32000000001
        # reaches a customer.
        assert result["currency"] == brazos.currency
        assert result["basis"] == "posting"
        for row in result["rows"]:
            assert isinstance(row["balance"], str), row["account_no"]


def test_cr060_c16__the_statement_prints_no_database_id(brazos, dana):
    """B14 rule 31 — *"no Databse ID on screen - that is a rule"* (PO ruling).

    The ids travel as machine handles for the row links and the screen prints
    `account_no` and `customer_no`. Asserted here because the alternative is
    finding it in a browser, which is how rule 31 was ruled in the first place.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        landlord = a_customer(brazos, no="C-1000", name="Alvarez Property Co", kind="business")
        link(brazos, landlord, accounts["ACC-1042"])

        result = statement(brazos, landlord)
        assert result["customer"]["customer_no"] == "C-1000"
        assert result["rows"][0]["account_no"] == "ACC-1042"


# ═══════════════════════════════════════════════════════════════════════════
# C16 proof 2 — a jointly-held account is shown IN FULL to each holder
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__a_joint_account_is_full_value_on_both_statements(brazos, dana):
    """Joint and several liability, correctly presented.

    ⚠ **IT IS NOT APPORTIONED, AND HALVING IT WOULD BE THE DEFECT.** Two people
    holding one account each owe the WHOLE of it; showing each of them half
    would tell both that they owe less than they do. So the same figure appears
    on both statements at full value, and each row names the other holder so a
    reader can see WHY.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        rosa = a_customer(brazos, no="C-2001", name="Rosa Alvarez")
        marco = a_customer(brazos, no="C-2002", name="Marco Alvarez")
        link(brazos, rosa, accounts["ACC-1042"])
        link(brazos, marco, accounts["ACC-1042"])

        hers = statement(brazos, rosa)
        his = statement(brazos, marco)
        assert hers["rows"][0]["balance"] == his["rows"][0]["balance"]
        assert hers["total"] == his["total"]
        # Not halved, and this is the assertion that says so out loud.
        assert Decimal(hers["total"]) == Decimal(hers["rows"][0]["balance"])
        # Each sees the other named, so the duplicate figure is explained.
        assert hers["rows"][0]["held_with"] == ["Marco Alvarez"]
        assert his["rows"][0]["held_with"] == ["Rosa Alvarez"]


# ═══════════════════════════════════════════════════════════════════════════
# C16 proof 3 — no query sums ACROSS customers
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__one_customers_arrears_never_reach_another_statement(brazos, dana):
    """The link table is N:M, so the shape that would break this is a walk from
    account back out to every other holder and then to THEIR other accounts.

    Rosa holds a joint account with Marco; Marco also holds one of his own. Her
    statement must show the joint account and NOT his — a statement that summed
    across the link would put a stranger's arrears on her page.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        rosa = a_customer(brazos, no="C-2001", name="Rosa Alvarez")
        marco = a_customer(brazos, no="C-2002", name="Marco Alvarez")
        link(brazos, rosa, accounts["ACC-1042"])
        link(brazos, marco, accounts["ACC-1042"])
        link(brazos, marco, accounts["ACC-1051"])

        hers = statement(brazos, rosa)
        assert [row["account_no"] for row in hers["rows"]] == ["ACC-1042"]
        assert hers["account_count"] == 1
        his = statement(brazos, marco)
        assert sorted(row["account_no"] for row in his["rows"]) == ["ACC-1042", "ACC-1051"]
        # And the two totals differ by exactly Marco's own account.
        assert Decimal(his["total"]) - Decimal(hers["total"]) == sum(
            Decimal(row["balance"]) for row in his["rows"] if row["account_no"] == "ACC-1051"
        )


# ═══════════════════════════════════════════════════════════════════════════
# C16 proof 4 — a weak or untiered link is LISTED and MARKED
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__an_untiered_link_is_listed_marked_and_left_out_of_the_total(brazos, dana):
    """*"never silently merged and never silently dropped"* — both are lies.

    An import link carries no tier at all (`BR-CUS-089`: the legacy id is a
    reconciliation key, not identity evidence). The tier already refuses to
    carry a deposit forward, and this statement is no braver than that: the row
    is shown, it is marked, it is OUT of the total, and `unconfident_total`
    states what was left out **as a figure** so the screen can say so without an
    adjective.
    """
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        landlord = a_customer(brazos, no="C-1000", name="Alvarez Property Co", kind="business")
        for key in ("ACC-1042", "ACC-1051", "ACC-1055"):
            link(brazos, landlord, accounts[key])
        link(brazos, landlord, accounts["ACC-0009"], tier=None)  # the import's own state

        result = statement(brazos, landlord)
        assert result["account_count"] == 4, "not dropped"
        untiered = next(row for row in result["rows"] if row["account_no"] == "ACC-0009")
        assert untiered["confident"] is False, "marked"
        assert untiered["match_tier"] is None
        assert untiered["balance"] is not None, "its figure is still shown"
        assert result["unconfident_count"] == 1
        assert Decimal(result["unconfident_total"]) == Decimal(untiered["balance"])
        # Not merged: the confident total is the other three, and the four
        # together are still LE-1's 152.32 — so nothing was invented either.
        assert Decimal(result["total"]) == sum(
            Decimal(row["balance"]) for row in result["rows"] if row["confident"]
        )
        assert Decimal(result["total"]) + Decimal(result["unconfident_total"]) == LE1_AR


def test_cr060_c16__a_weak_tier_is_treated_the_same_as_no_tier(brazos, dana):
    """`weak` is evidence somebody looked and was not convinced. It carries no
    more weight in a total than no evidence at all."""
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        rosa = a_customer(brazos, no="C-2001", name="Rosa Alvarez")
        link(brazos, rosa, accounts["ACC-1042"], tier="weak")

        result = statement(brazos, rosa)
        assert result["rows"][0]["confident"] is False
        assert Decimal(result["total"]) == Decimal("0")
        assert Decimal(result["unconfident_total"]) == Decimal(result["rows"][0]["balance"])


def test_cr060_c16__probable_counts_and_strong_counts(brazos, dana):
    """The two tiers a human committed at a door both carry into the total —
    otherwise every counter-opened account would read as unverified."""
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        rosa = a_customer(brazos, no="C-2001", name="Rosa Alvarez")
        link(brazos, rosa, accounts["ACC-1042"], tier="probable")
        result = statement(brazos, rosa)
        assert result["rows"][0]["confident"] is True
        assert result["unconfident_count"] == 0


# ═══════════════════════════════════════════════════════════════════════════
# C16 proof 5 — no live account is an EMPTY statement, not an error
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__a_customer_with_no_account_gets_an_empty_statement(brazos, dana):
    """A real person holding nothing is a derived answer, not a failure."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        newcomer = a_customer(brazos, no="C-3000", name="Priya Menon")

        result = statement(brazos, newcomer)
        assert result is not None
        assert result["rows"] == []
        assert result["account_count"] == 0
        assert Decimal(result["total"]) == Decimal("0")
        assert result["unconfident_count"] == 0
        assert result["customer"]["display_name"] == "Priya Menon"


# ═══════════════════════════════════════════════════════════════════════════
# The endpoint — including the two refusals it must tell apart
# ═══════════════════════════════════════════════════════════════════════════
def test_cr060_c16__the_endpoint_serves_the_statement(brazos, dana):
    with tenant_ctx(brazos):
        accounts = a_month(brazos, dana)
        landlord = a_customer(brazos, no="C-1000", name="Alvarez Property Co", kind="business")
        for key in ALL_FOUR:
            link(brazos, landlord, accounts[key])

        body = call(brazos, customer=str(landlord.id)).data
        assert Decimal(body["total"]) == LE1_AR
        assert body["customer"]["customer_no"] == "C-1000"
        assert len(body["rows"]) == 4


def test_cr060_c16__a_missing_customer_param_is_refused_not_404ed(brazos, dana):
    """*"You did not say who"* and *"there is no such person"* are different
    answers, and collapsing them sends a clerk looking for a customer who never
    existed. B12 §3 maps the whole VAL class to 422."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        response = call(brazos)
        assert response.status_code == errors.HTTP_STATUS_BY_CODE[errors.VAL_REQUIRED]
        assert response.data["code"] == errors.VAL_REQUIRED


def test_cr060_c16__an_unknown_customer_is_404_and_so_is_a_malformed_one(brazos, dana):
    """404-never-403 (HR-1/G4): from outside the tenant an id that exists
    elsewhere and one that does not are the same fact, and telling them apart is
    a membership oracle. A malformed id answers the same way for the same
    reason — a 422 there would confirm that well-formed ids are worth trying."""
    with tenant_ctx(brazos):
        a_month(brazos, dana)
        assert call(brazos, customer="0198f0d0-0000-7000-8000-000000000000").status_code == 404
        assert call(brazos, customer="not-a-uuid").status_code == 404


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-019@cr060-c16 (12-governance/11-change-requests.md CR-060 C16 + task T17 · 04-docs/05-modules/03-customers/02-business-rules.md BR-CUS-054, BR-CUS-089 · tests/ledger_le_fixtures.py LE-1)
# generated: 2026-09-02 by the CR-060 finance-screens lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST (law 7) — `AttributeError: module 'apps.customers.selectors' has no attribute 'customer_statement'` on every case, quoted in the module docstring
# exceptions: (1) the `customer_accounts` links are written through the ORM rather than through the import door — CR-056 puts the only link writer inside an import, so using the real door would mean staging an import file to test a REPORT. Each case states the `match_tier` BR-CUS-089 would have written, which is the fact the statement reads · (2) there is NO case for the ledger being unreadable (`available=false`) in this file: that path is the `ar_positions` seam's own and is held by `test_def_127_one_account_one_figure.py`; the statement passes it through untouched and its `total` is `None` there rather than 0.00 · (3) the S60-style export/download is not built — `POST /reports/{key}/export` is served by no deployment (TD-17)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

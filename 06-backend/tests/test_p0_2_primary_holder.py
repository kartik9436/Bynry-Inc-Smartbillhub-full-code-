# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.2` — *"An account with two live customers
#           names which one is billed"*. Migration `customers/0070`.
# Rules:    `BR-CUS-054` (the link is N:M — a jointly-held account stays
#           lawful) · `BR-CUS-1030` (a sale ENDS a link rather than deleting
#           it, which is why the uniqueness is partial on `ended_at`) ·
#           CLAUDE.md hard rule 1
# Impacts:  apps/customers/models.py (`CustomerAccount.is_primary`)
# ───────────────────────────────────────────────────────
"""One primary holder per account — and the four ways to get it wrong.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY** (hard-won law 7, habit 2):

1. **The uniqueness is on the wrong scope.** A plain UNIQUE on
   `(tenant, account)` would allow exactly ONE LINK per account in total —
   silently forbidding the joint holding `BR-CUS-054` exists to permit. `tc2`
   adds a second, NON-primary link to the same account and requires it to be
   ACCEPTED. Without that case, the strictest possible constraint passes.
2. **The uniqueness ignores `ended_at`.** A seller who was primary and later
   buys the property back needs a second primary row for the same account.
   `tc4` ends the first link and nominates a new holder, and requires it to be
   accepted.
3. **The constraint is declared in Django and never reached the database.**
   `tc3` makes PostgreSQL do the refusing, inside a savepoint.
4. **The backfill nominated everybody.** *"Where a link is the only live one"*
   is the whole rule, and a backfill that set every live link primary would
   pass any test that only counted primaries upward. `tc5` builds a jointly
   held account and requires that NEITHER holder is nominated.

`tc3` is PostgreSQL-only and skips loudly; SQLite enforces a partial unique
index too, but the transaction behaviour the savepoint depends on is
PostgreSQL's, and it is the behaviour production has.
"""

import uuid

import pytest
from django.db import IntegrityError, transaction

from apps.customers import models as customer_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _two_customers(tenant):
    """Two people who could jointly hold one account."""
    return [
        customer_models.Customer.objects.create(
            tenant=tenant, kind="person", display_name=name
        )
        for name in ("Sarah Chen", "Michael Chen")
    ]


def _account(tenant, actor):
    """One account for these links to hang off.

    A `master` account anchored on a premises, because that is the cheapest
    lawful shape: `ck_accounts_anchored` wants a unit OR a premises, and a
    `regular` account additionally must name a unit (`BR-CUS-1012`). None of
    this rule is about what KIND of account is held — it is about the link
    table — so the shortest lawful anchor is the right one.
    """
    premises = make_premises(actor)  # noqa: F405 — shared fixture helper
    return customer_models.Account.objects.create(
        tenant=tenant,
        account_no=f"AC-{uuid.uuid4().hex[:8]}",
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        kind="master",
        premises_id=premises["id"],
    )


def test_tc1_the_column_exists_and_defaults_to_nobody(brazos):
    """`False` by default, so arriving at this column can never silently
    nominate anybody — which is what a `True` default would do to every link
    written from now on."""
    field = customer_models.CustomerAccount._meta.get_field("is_primary")
    assert field.default is False
    assert field.null is False


def test_tc2_a_second_non_primary_holder_is_still_lawful(brazos, dana):
    """See note 1 — the N:M this table exists for must survive the constraint.

    If this case ever goes red, the constraint has been widened from *one
    PRIMARY per account* to *one LINK per account*, and joint holding has been
    abolished by a typo.
    """
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        sarah, michael = _two_customers(brazos)
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=sarah, account=account, is_primary=True
        )
        # The second holder, NOT primary — accepted.
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=michael, account=account, is_primary=False
        )
        live = customer_models.CustomerAccount.live(account=account)
        assert live.count() >= 2
        assert live.filter(is_primary=True).count() == 1


def test_tc3_the_database_refuses_a_second_primary_on_one_account(brazos, dana):
    """See note 3 — the refusal has to come from the database.

    A service-layer check loses the race between two clerks, and the prize for
    losing it is a bill with two addressees.

    ⚠ The savepoint is not tidiness: on PostgreSQL the failed INSERT aborts the
    transaction, and without `atomic()` nothing after it in this test — its own
    teardown included — could run (hard-won law 14).
    """
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        sarah, michael = _two_customers(brazos)
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=sarah, account=account, is_primary=True
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():  # the SAVEPOINT
                customer_models.CustomerAccount.objects.create(
                    tenant=brazos, customer=michael, account=account, is_primary=True
                )
        # The connection survived, and the first nomination is untouched.
        assert (
            customer_models.CustomerAccount.live(account=account, is_primary=True).count()
            == 1
        )


def test_tc4_a_seller_who_buys_back_can_be_primary_again(brazos, dana):
    """See note 2 — `BR-CUS-1030` ends a link rather than deleting it.

    Without the `ended_at IS NULL` half of the predicate, a repurchase would
    die on a uniqueness error naming neither person — the identical trap
    `uq_customer_accounts_pair_live` already sidesteps one constraint over.
    """
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        sarah, michael = _two_customers(brazos)
        first = customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=sarah, account=account, is_primary=True
        )
        # The property is sold: the link ENDS, it is not deleted.
        first.ended_at = "2026-09-01T00:00:00Z"
        first.save(update_fields=["ended_at"])
        # The buyer becomes primary — accepted, because the old row is ended.
        customer_models.CustomerAccount.objects.create(
            tenant=brazos, customer=michael, account=account, is_primary=True
        )
        assert (
            customer_models.CustomerAccount.objects.filter(
                account=account, is_primary=True
            ).count()
            == 2
        )
        assert (
            customer_models.CustomerAccount.live(account=account, is_primary=True).count()
            == 1
        )


def test_tc5_a_jointly_held_account_nominates_nobody(brazos, dana):
    """See note 4 — *"where a link is the ONLY live one"* is the whole rule.

    Two live holders is a fact the product does not know the answer to, and
    inventing one would put a stranger's name on a bill with nothing recording
    that anybody guessed. An all-false account is a REAL state and this pins
    it, so a later "helpful" backfill that picks the oldest link goes red.
    """
    with tenant_ctx(brazos):
        account = _account(brazos, dana)
        sarah, michael = _two_customers(brazos)
        for person in (sarah, michael):
            customer_models.CustomerAccount.objects.create(
                tenant=brazos, customer=person, account=account, is_primary=False
            )
        live = customer_models.CustomerAccount.live(account=account)
        assert live.count() >= 2
        assert live.filter(is_primary=True).count() == 0, (
            "a jointly held account must nominate nobody until a human says who"
        )


def test_tc6_the_constraint_is_partial_on_both_clauses():
    """Read off the model rather than off the database, so the default suite
    covers it too. Both clauses are load-bearing and this is the cheapest
    place a reviewer can see both are there."""
    constraint = next(
        c
        for c in customer_models.CustomerAccount._meta.constraints
        if c.name == "uq_customer_accounts_primary_live"
    )
    assert tuple(constraint.fields) == ("account",)
    rendered = str(constraint.condition)
    assert "is_primary" in rendered
    assert "ended_at" in rendered

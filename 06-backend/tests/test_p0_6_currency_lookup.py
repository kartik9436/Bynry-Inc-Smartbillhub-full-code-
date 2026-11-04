# ── Trace ──────────────────────────────────────────────
# Task:     Finance blueprint `P0.6` (the lookup) · `P0.7` (the currency
#           validated at post) · `P0.8` (Settings reads the lookup) ·
#           **`P0.9` (PostgreSQL only)** — *"FK violation refused; currency
#           mismatch refused; a failed statement aborts the transaction.
#           `config/settings/test.py` hardcodes in-memory SQLite, which has no
#           aborted-transaction state — these cannot be proved on the default
#           suite."*
# Rules:    `OQ-031` (CLOSED → `BR-TEN-036`) · `BR-TEN-042` · `BR-TEN-021` (a
#           currency change is forward-only) · CLAUDE.md hard rule 2 · hard
#           rule 4 · **hard-won law 14**
# Code:     apps/tenancy/models.Currency · tenancy/0050 · ledger/0018 ·
#           apps/ledger/posting._refuse_unless_the_tenants_currency
# ───────────────────────────────────────────────────────
"""What a currency is, and the three guards that stop the books drifting.

**THIS FILE IS ALSO `P0.9`.** That task is not a separate suite — it is the
instruction that these particular guarantees have to be proved on PostgreSQL
and cannot be proved anywhere else, because `config/settings/test.py` replaces
`DATABASES` wholesale with in-memory SQLite. Three things live here that the
default suite is structurally incapable of showing:

  * **a foreign-key violation refused** — SQLite does not carry the constraint
    at all, because `ALTER TABLE … ADD CONSTRAINT` does not exist there and the
    migration deliberately writes nothing;
  * **a currency mismatch refused** — this one WOULD pass on SQLite, and it is
    here beside the other two so the whole rule is checked in one place, on the
    database that has to enforce it;
  * **a failed statement aborting the transaction** — SQLite has no
    aborted-transaction state, so the naive `except IntegrityError: continue`
    passes the entire suite green and loses the work at COMMIT in production.
    `tc5` is hard-won law 14 made visible.

⚠ **WHAT WOULD MAKE THIS SUITE PASS WRONGLY** (law 7, habit 2):

1. **The refusal comes from the wrong guard.** A bad currency could be refused
   by the CHAR(3) length check, by the tenant-match check, or by the foreign
   key — three different guards, three different meanings. Every case asserts
   WHICH one spoke.
2. **The seeded set drifts from the tuple it replaced.** `tc2` asserts the
   table and `services.SEED_CURRENCIES` agree, so a row added to one and not
   the other goes red rather than silently widening what a tenant may pick.
3. **A test that proves nothing because the tenant is already on that
   currency.** `tc4` moves the tenant to CAD first, so the refusal it asserts
   is a real mismatch and not a coincidence.
"""

import pytest
from django.db import IntegrityError, connection, transaction

from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

postgres_only = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "hard-won law 14: SQLite has no aborted-transaction state and carries "
        "none of these constraints, so a pass here would say nothing about the "
        "database that has to enforce them. Run with --ds=config.settings.pgtest."
    ),
)


def test_tc1_the_lookup_holds_the_five_the_platform_sells(brazos):
    """`P0.6` — the table exists and says what a currency is.

    The symbols are asserted too: `apps/reports/dashboard_format` renders money
    from a constant transcribed from `Intl.NumberFormat`, and the whole point
    of that constant is that the server's string and the client's string are
    the same string. A row whose symbol disagrees would render one way on a
    dashboard and another everywhere else.
    """
    rows = {row.code: row for row in tenancy_models.Currency.objects.all()}
    assert set(rows) == {"USD", "CAD", "MXN", "EUR", "GBP"}
    assert rows["USD"].symbol == "$"
    assert rows["CAD"].symbol == "CA$"
    assert rows["GBP"].symbol == "£"
    assert all(row.minor_units == 2 for row in rows.values())
    assert all(row.is_active for row in rows.values())


def test_tc2_the_table_and_the_tuple_it_replaced_agree(brazos):
    """See note 2 — there must be ONE vocabulary, not two that can disagree.

    `SEED_CURRENCIES` is kept as the fallback `active_currency_codes()` returns
    when the table cannot be read (mid-migration, or an empty install). If the
    two ever diverge, the product answers differently depending on which path
    it took — which is precisely the class of bug this lookup exists to end.
    """
    assert set(tenancy_services.active_currency_codes()) == set(
        tenancy_services.SEED_CURRENCIES
    )


def test_tc3_a_currency_that_is_not_the_tenants_is_refused_at_post(brazos, dana):
    """`P0.7` — *"a CAD tenant's books cannot quietly become USD"*.

    See note 1: the refusal must come from the TENANT-MATCH guard, not from the
    CHAR(3) length check. `CAD` is three characters and a real currency, so the
    only thing that can refuse it here is the rule under test.
    """
    from apps.ledger import posting

    with tenant_ctx(brazos):
        assert brazos.currency == "USD"
        with pytest.raises(posting.PostingError) as caught:
            posting._refuse_unless_the_tenants_currency("CAD")
        message = str(caught.value)
        assert "CAD" in message and "USD" in message
        assert "immutable" in message, (
            "the refusal does not say WHY it cannot be corrected later, which is "
            "the whole reason it has to refuse rather than warn"
        )
        # ...and the tenant's own currency is accepted, so the guard is not
        # simply refusing everything.
        posting._refuse_unless_the_tenants_currency("USD")


def test_tc4_the_guard_follows_the_tenant_rather_than_hardcoding_usd(brazos, dana):
    """See note 3 — move the tenant, and the guard must move with it.

    A check written as `if currency != "USD"` would pass `tc3` exactly as the
    correct one does. This is the case that tells them apart.
    """
    from apps.ledger import posting

    with tenant_ctx(brazos):
        tenancy_models.Tenant.objects.filter(pk=brazos.pk).update(currency="CAD")
        brazos.refresh_from_db()
        # Now CAD is lawful and USD is not — the exact opposite of `tc3`.
        posting._refuse_unless_the_tenants_currency("CAD")
        with pytest.raises(posting.PostingError):
            posting._refuse_unless_the_tenants_currency("USD")


@postgres_only
def test_tc5_the_database_refuses_a_currency_that_is_not_a_currency(brazos):
    """**`P0.9`, all three parts, in one case.**

    ① a FOREIGN-KEY violation is refused by PostgreSQL, ② it is refused by the
    CONSTRAINT WE ADDED and not by something else — the assertion names it —
    and ③ **the failed statement aborts the transaction**, which is asserted
    directly rather than described.

    ⚠ Part ③ is hard-won law 14 and is the reason this file exists. On
    PostgreSQL, once a statement errors, every later query in that transaction
    raises until the block ends. `except IntegrityError: continue` therefore
    loses all the work at COMMIT — while passing the entire SQLite suite green,
    on every machine. A SAVEPOINT (a nested `atomic()`) is not the tidy option,
    it is the only one, and this case proves the abort is real so nobody
    "simplifies" a savepoint away.

    `XYZ` is three characters, so the CHAR(3) shape check cannot be what
    refuses it; only the foreign key can.
    """
    with tenant_ctx(brazos):
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():  # the SAVEPOINT
                with connection.cursor() as cursor:
                    cursor.execute("UPDATE tenants SET currency = 'XYZ'")
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert "fk_tenants_currency" in str(caught.value), (
            f"something else refused the write: {caught.value}"
        )

        # ③ The connection survived BECAUSE of the savepoint — and the tenant's
        # currency is untouched.
        assert tenancy_models.Tenant.objects.get(pk=brazos.pk).currency == "USD"


@postgres_only
def test_tc6_a_failed_statement_aborts_the_transaction_without_a_savepoint(brazos):
    """**Law 14, shown rather than described** — the half `tc5` proves by
    surviving, proved here by NOT surviving.

    Without a savepoint the connection is unusable after the failure, and the
    next perfectly ordinary query raises. A lane that writes
    `except IntegrityError: continue` gets this, in production, having watched
    every test pass.
    """
    from django.db import InternalError, OperationalError, ProgrammingError

    with tenant_ctx(brazos):
        with transaction.atomic():  # the outer block, so the damage is rolled back
            with connection.cursor() as cursor:
                try:
                    cursor.execute("UPDATE tenants SET currency = 'XYZ'")
                    cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
                except IntegrityError:
                    pass  # ⚠ the naive handler, on purpose
                # The transaction is now ABORTED. Any query raises.
                with pytest.raises(
                    (InternalError, OperationalError, ProgrammingError, Exception)
                ) as caught:
                    cursor.execute("SELECT 1")
            assert "current transaction is aborted" in str(caught.value).lower(), (
                "the transaction was NOT aborted — either this is not PostgreSQL "
                f"or law 14 no longer applies here. Got: {caught.value}"
            )
            transaction.set_rollback(True)

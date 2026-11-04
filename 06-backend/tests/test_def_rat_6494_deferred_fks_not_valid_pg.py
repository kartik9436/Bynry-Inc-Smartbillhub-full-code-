# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6494 — `rating/0044` added eight foreign keys VALIDATING,
#          met one orphaned `plan_deposit_rules.account_type_id` on a real
#          deploy database, and PostgreSQL refused the migration. The container
#          could not start. Root cause `customers/0054`, whose repoint list is
#          ("Account", "AccountSubtype", "ServiceRequest") and does not name
#          `plan_deposit_rules` — a bare UUIDField with no FK, invisible to its
#          "stranded" guard and to the PROTECTed delete alike. Same root cause
#          as DEF-RAT-5823, one table further on.
# Rules:   CLAUDE.md hard-won law 7 (a check reporting zero over a scope it
#          silently excludes; ask what makes a check pass WRONGLY) · law 14
#          (the suite's sqlite cannot express this) · hard rule 1 (tenant
#          scoping) · hard rule 4 (financial immutability — nothing here writes
#          a money row) · `BR-RAT-020/023` (a deposit rule is a money path) ·
#          CLAUDE.md 🔒 migration ordering
# Fix in:  06-backend/apps/rating/migrations/0044_p0_4_p0_5_deferred_fks.py
# ───────────────────────────────────────────────────────
"""**The eight deferred FKs land on a database that already holds a bad id, and
every FUTURE bad write is still refused.**

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE IS RED ON, SAID FIRST SO A READER CAN CHECK IT
════════════════════════════════════════════════════════════════════════════
On the migration as it was written — `ADD CONSTRAINT … DEFERRABLE INITIALLY
DEFERRED`, with no `NOT VALID` — two cases here fail, and they fail for the two
different halves of the defect:

  * `test_the_migration_applies_over_a_row_that_already_names_nothing` raises
    `IntegrityError`, which is the deploy's own failure reproduced;
  * `test_the_constraint_is_marked_not_valid` sees `convalidated = True`, which
    is the constraint CLAIMING it checked rows it did not check.

Proved red in the harness that runs them, not through `python <file>`
(hard-won law 7's second half): `pytest --ds=config.settings.pgtest`.

════════════════════════════════════════════════════════════════════════════
WHAT WOULD MAKE THIS FILE PASS WRONGLY — asked before it was written
════════════════════════════════════════════════════════════════════════════
**THE WHOLE FILE CAN BE MADE GREEN BY ACCIDENT, AND THE MECHANISM IS RLS.**
`plan_deposit_rules` is `FORCE ROW LEVEL SECURITY`. PostgreSQL validates a new
foreign key with an ordinary scan, and that scan obeys the `B2 §3` policy like
any other read — so **a session that is not in the orphan's tenant context
cannot see the orphan, the old migration validates happily, and the
reproduction case passes on the broken code.** That is not hypothetical: it is
how the migration behaves on the app role in the first place, because the role
default is the NO-TENANT sentinel. Measured on PostgreSQL 16.13 on 2026-09-24:
one orphan present, `manage.py migrate` exits 0, `convalidated = t`, the orphan
still there.

So `_assert_the_orphan_is_visible_here` runs before the statement under test in
every case that needs it. **A test whose subject is hidden from it is a test
that cannot fail**, and this one would have been exactly that.

Two smaller ones, for completeness:
  * asserting only *"the migration applied"* would pass on a migration that
    added no constraint at all, so the constraint is read back out of
    `pg_constraint` by name every time;
  * asserting only *"a bad insert is refused"* would pass on the OLD file too —
    it is not evidence for this fix, it is the thing the fix must not COST, and
    it is here for that reason and labelled as such.

════════════════════════════════════════════════════════════════════════════
WHY PostgreSQL-ONLY (law 14)
════════════════════════════════════════════════════════════════════════════
`config/settings/test.py` hardcodes in-memory sqlite. SQLite has no
`ALTER TABLE … ADD CONSTRAINT`, no `NOT VALID`, no `pg_constraint` and no
row-level security, and `_add` returns early there — so the default suite
cannot see any of this and never could. `test_the_migration_text_still_says_not_valid`
is deliberately left OUT of that restriction: it reads a string, it runs
everywhere, and it is the one thing standing between this fix and a lane
"simplifying" the keyword away on a machine with no PostgreSQL on it.

Run with:

    cd 06-backend
    DATABASE_URL='postgres://…' .venv/bin/pytest \\
        tests/test_def_rat_6494_deferred_fks_not_valid_pg.py \\
        --ds=config.settings.pgtest --reuse-db
"""

from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction

from apps.customers.models import AccountType
from apps.rating.models import PlanDepositRule, RatePlan

from tests.isolation_helpers import requires_postgres
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared W1 fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db]

MIGRATION = "apps.rating.migrations.0044_p0_4_p0_5_deferred_fks"

#: The id the production deploy actually died on, kept verbatim so a failure
#: message here looks like the traceback somebody will be holding. Its uuid7
#: timestamp decodes to 2026-09-08 05:03:10 UTC — a PLATFORM-era `account_types`
#: row, from before `customers/0054` deleted that generation.
ORPHAN = "01a07f66-1139-79aa-a657-0afb2f867087"

#: The constraint the deploy died on: `FOREIGN_KEYS[7]`, the eighth and last.
DEPOSIT_FK = "fk_plan_deposit_rules_account_type"


def _module():
    """`import_module` because the module name starts with a digit and `from`
    cannot spell it — the same reason `test_def_rat_5823_…` does it."""
    return import_module(MIGRATION)


def _settle() -> None:
    """Fire the deferred constraint checks queued by whatever wrote last.

    ⚠ **WITHOUT THIS EVERY CASE HERE DIES IN ITS FIXTURE, AND THE MESSAGE NAMES
    NOTHING USEFUL:** `psycopg.errors.ObjectInUse: cannot ALTER TABLE "charges"
    because it has pending trigger events`. Every FK in this schema is
    `DEFERRABLE INITIALLY DEFERRED`, so the fixture's own writes leave checks
    queued for COMMIT, and PostgreSQL refuses to alter a table with events
    pending against it. `customers/0054._settle_deferred_constraints` is the
    same helper for the same reason.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def _run(func_name: str) -> None:
    """Run the migration's own forward/reverse function against the live
    registry. The historical models carry the same fields as the real ones at
    this point in the graph, so the app registry stands in for `apps` and a
    one-attribute shim for `schema_editor`."""
    from django.apps import apps as live_registry

    _settle()
    _module().__dict__[func_name](live_registry, SimpleNamespace(connection=connection))


def _convalidated(name: str):
    """`True`/`False` from `pg_constraint`, or `None` when no such constraint
    exists — three outcomes, because 'absent' and 'present but unvalidated' are
    different answers and a boolean would flatten them into one."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT convalidated FROM pg_constraint WHERE conname = %s", [name])
        row = cursor.fetchone()
    return None if row is None else row[0]


def _assert_the_orphan_is_visible_here(expected: int = 1) -> None:
    """⚠ **THE GUARD THAT STOPS THIS FILE BEING GREEN FOR THE WRONG REASON.**

    See the module docstring: under `FORCE ROW LEVEL SECURITY` a session
    outside the row's tenant context cannot see it, the FK validation scan
    matches nothing, and the BROKEN migration passes. Every case that depends
    on the orphan being examined calls this first, so a fixture that silently
    lost its tenant context fails HERE, saying so, instead of passing over
    there.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM plan_deposit_rules p "
            "LEFT JOIN account_types a ON a.id = p.account_type_id "
            "WHERE a.id IS NULL"
        )
        seen = cursor.fetchone()[0]
    assert seen == expected, (
        f"this session can see {seen} orphaned deposit rule(s), expected {expected}. "
        "If it is 0 the row is hidden by row-level security and every case below "
        "would pass on the broken migration too — the fixture is wrong, not the code."
    )


@pytest.fixture()
def orphaned_deposit_rule(env):
    """A deposit rule naming an `account_types` row that does not exist —
    exactly the state `customers/0054` left behind on the deploy database, and
    exactly the state `rating/0044`'s pre-check measured as zero somewhere
    else.

    The eight constraints are dropped first, because the test database was
    built by running the migration and they are therefore already in place;
    dropping them puts this database back to where a deploy starts.
    """
    _run("_drop")
    with tenant_ctx(env.tenant):
        plan = RatePlan.objects.create(
            tenant=env.tenant, code="DEF6494", name="DEF-RAT-6494 plan"
        )
        rule = PlanDepositRule.objects.create(
            tenant=env.tenant,
            rate_plan=plan,
            account_type_id=ORPHAN,
            amount="150.0000",
            currency="USD",
        )
        yield SimpleNamespace(env=env, plan=plan, rule=rule)


# ══ the reproduction — RED on the migration as it was written ══════════════


@requires_postgres
def test_the_migration_applies_over_a_row_that_already_names_nothing(
    orphaned_deposit_rule,
):
    """**THE DEPLOY'S OWN FAILURE, AS A TEST.** On the old text this raises

        IntegrityError: insert or update on table "plan_deposit_rules" violates
        foreign key constraint "fk_plan_deposit_rules_account_type"
        DETAIL: Key (account_type_id)=(01a07f66-…)   is not present in table
                "account_types".

    and the container does not start.
    """
    _assert_the_orphan_is_visible_here()

    _run("_add")  # the whole migration, all eight, exactly as `migrate` runs it

    assert _convalidated(DEPOSIT_FK) is not None, (
        "the migration applied but added no such constraint — a migration that "
        "does nothing would also 'pass' the line above"
    )


@requires_postgres
def test_the_constraint_is_marked_not_valid(orphaned_deposit_rule):
    """**AND IT MUST SAY SO.** `NOT VALID` is only honest if the database
    records it: a constraint marked validated over rows nothing examined is the
    lie this defect is made of, and it is what `rating/0044` produced on the
    app role even when it did NOT die."""
    _assert_the_orphan_is_visible_here()
    _run("_add")

    assert _convalidated(DEPOSIT_FK) is False, (
        f"{DEPOSIT_FK} reports convalidated={_convalidated(DEPOSIT_FK)!r}. It must be "
        "False: the existing rows were not examined, and nothing in this product may "
        "describe these constraints as validated until somebody runs VALIDATE "
        "CONSTRAINT (see OQ-RAT-12633)."
    )


@requires_postgres
def test_all_eight_are_not_valid_and_not_just_the_one_that_failed(
    orphaned_deposit_rule,
):
    """⚠ **THE SEVEN THAT SURVIVED THE DEPLOY ARE NOT EVIDENCE ABOUT ANYTHING.**
    They validated against one database's rows. Converting only the eighth
    would leave seven doors to the identical failure open on the next deploy —
    which is this defect's whole lesson, applied to itself."""
    _run("_add")

    states = {name: _convalidated(name) for name, _t, _c, _g in _module().FOREIGN_KEYS}
    assert len(states) == 8, f"expected eight constraints, the file names {len(states)}"
    wrong = {name: state for name, state in states.items() if state is not False}
    assert not wrong, (
        f"these are not NOT VALID: {wrong}. `None` means the constraint is missing "
        "entirely; `True` means it claims to have checked rows it may not have seen."
    )


# ══ what the fix must not COST — green on the old file too, deliberately ═══
#
# ⚠ These three are NOT evidence for this change and must not be read as such:
# the old migration passes them as well. They are here because a `NOT VALID`
# constraint that did not refuse future writes would make the fix worthless,
# and somebody has to have checked that rather than trusted the manual.


@requires_postgres
def test_a_new_bad_insert_is_still_refused(orphaned_deposit_rule):
    """⚠ **THE CONSTRAINT IS `DEFERRABLE INITIALLY DEFERRED`, SO THE OFFENDING
    STATEMENT IS ACCEPTED AND JUDGED AT COMMIT.** A case that wrote a bad id in
    a savepoint and expected a raise gets `DID NOT RAISE` and reads as a broken
    test rather than as a deferred constraint — which is how a real guard gets
    deleted as flaky. `SET CONSTRAINTS ALL IMMEDIATE` brings the judgement
    forward, and it is also the honest statement of when a real caller finds
    out: their whole unit of work fails."""
    _run("_add")
    env = orphaned_deposit_rule.env

    with tenant_ctx(env.tenant):
        with pytest.raises(IntegrityError) as caught:
            # ⚠ SAVEPOINT, not a bare try (law 14): on PostgreSQL the refused
            # statement aborts the transaction, and without a nested atomic()
            # nothing after this line could run one further query.
            with transaction.atomic():
                PlanDepositRule.objects.create(
                    tenant=env.tenant,
                    rate_plan=orphaned_deposit_rule.plan,
                    account_type_id=uuid4(),
                    amount="99.0000",
                    currency="USD",
                )
                _settle()
    assert DEPOSIT_FK in str(caught.value), (
        "something refused the write, but not the constraint under test — "
        f"got: {caught.value}"
    )


@requires_postgres
def test_a_new_bad_update_is_still_refused(orphaned_deposit_rule):
    """The correction path, not just the creation path: `rating/services
    ._apply_plan_children` REPLACES the deposit-rule set on every wizard save,
    so a bad id arrives by rewrite at least as often as by insert."""
    _run("_add")
    env = orphaned_deposit_rule.env

    with tenant_ctx(env.tenant):
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():
                rule = orphaned_deposit_rule.rule
                rule.account_type_id = uuid4()
                rule.save(update_fields=["account_type_id", "updated_at"])
                _settle()
    assert DEPOSIT_FK in str(caught.value), (
        "something refused the write, but not the constraint under test — "
        f"got: {caught.value}"
    )


@requires_postgres
def test_deleting_an_account_type_a_deposit_rule_points_at_is_still_refused(
    orphaned_deposit_rule,
):
    """**THE DIRECTION NOBODY WAS GUARDING.** `customers.lookups`'
    `AccountTypeLookupHandler.used_by` counts `accounts`, `account_subtypes`
    and `service_requests` — the same three tables `customers/0054` repointed —
    so a tenant admin deleting a consumer category that a deposit rule prices
    against is offered a Delete that nothing refuses. After this migration the
    DATABASE refuses it, which is the right answer arriving in the wrong words
    (see `DEF-CUS-6495`).

    ⚠ **THE FIRST DRAFT OF THIS CASE PASSED FOR THE WRONG REASON AND THE NAME
    ASSERTION IS WHAT CAUGHT IT (law 7).** Pointing the rule at a SEEDED type
    and deleting that raises Django's own `ProtectedError` — *"referenced
    through protected foreign keys: 'AccountSubtype.account_type'"* — from the
    ORM collector, **before a single statement reaches PostgreSQL**. The case
    was green, and it was green on the old migration too: it proved the ORM's
    `PROTECT`, not this constraint. So the type here is one the TENANT ADDED,
    with no subtype, no account and no service request under it — precisely the
    row `used_by` counts as `0` and offers a Delete for.
    """
    env = orphaned_deposit_rule.env
    with tenant_ctx(env.tenant):
        real_type = AccountType.objects.create(
            tenant=env.tenant,
            code="def6494_added",
            name="A category this tenant added",
            is_system=False,
            active=True,
            legacy=False,
            sort_order=990,
        )
        rule = orphaned_deposit_rule.rule
        rule.account_type_id = real_type.id
        rule.save(update_fields=["account_type_id", "updated_at"])

    _run("_add")

    with tenant_ctx(env.tenant):
        with pytest.raises(IntegrityError) as caught:
            with transaction.atomic():
                AccountType.objects.filter(pk=real_type.id).delete()
                _settle()
    assert DEPOSIT_FK in str(caught.value), (
        "the delete was refused by something other than the deposit-rule "
        f"constraint — got: {caught.value}"
    )


# ══ the one case that runs on sqlite too ═══════════════════════════════════


def test_the_migration_text_still_says_not_valid():
    """⚠ **NO `requires_postgres` ON PURPOSE.** Every case above skips on the
    default suite, so without this one a lane could delete the two words that
    fix this defect and see nothing but green on a machine with no PostgreSQL.
    This reads the statement the migration actually builds."""
    sql = _module().add_sql(DEPOSIT_FK, "plan_deposit_rules", "account_type_id", "account_types")

    assert sql.rstrip().upper().endswith("NOT VALID"), (
        f"rating/0044 no longer emits NOT VALID; it builds {sql!r}. Restoring the "
        "validating form re-breaks DEF-RAT-6494 and every deploy holding a deposit "
        "rule whose account_type_id was orphaned by customers/0054."
    )
    assert "DEFERRABLE INITIALLY DEFERRED" in sql.upper(), (
        "the deferrable clause was dropped along with the fix — B11 F-3's "
        "convention for every FK in this schema"
    )

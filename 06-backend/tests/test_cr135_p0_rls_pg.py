# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, tasks `P0.14` and
#          the BACKFILL half of `P0.15`.
#          `P0.14`: *"RLS probe, on PostgreSQL. Both directions on
#          counter_sessions."* Outcome: *"Tenant A cannot read or write tenant
#          B's till, proved where the policy actually runs."*
#          `P0.15`: *"Four backfill cases including the loud failure."* The
#          constraint half is `test_cr135_p0_foundations.py`; the backfill half
#          is here because `payments/0030`'s pass only exists on PostgreSQL.
#          The 🔒 file under review is
#          `apps/payments/migrations/0032_rls_cr135_p0_5_counter_sessions.py`
#          (review-ledger row, CR-135-BRC07).
# Rules:   CLAUDE.md hard rule 1 (never touch a tenant table without
#          `app.tenant_id` set; RLS FORCE is on) · B2 §3 · hard-won law 14 (the
#          suite runs on SQLite, which has no row-level security — a proof
#          about the real database runs on the real database) · law 7 (proved
#          RED first, in the harness that will run it)
# Tests:   this file — SKIPPED on SQLite BY DESIGN, and the skip is the point.
# ───────────────────────────────────────────────────────
"""`counter_sessions` under real row-level security, on real PostgreSQL.

⚠ **`P0.14` CARRIES ITS OWN WARNING AND IT IS WHY THIS FILE IS SEPARATE:** *"The
suite defaults to in-memory SQLite, where the guarantee cannot exist — 192
skips once read as a pass."* `config/settings/test.py` hardcodes in-memory
SQLite and ignores `DATABASE_URL`, so every assertion about a policy passes
there by vacuum.

Run it against a real database — the whole line, because a walkthrough header
that omits `JOBS_EAGER=false` costs an hour (`DEF-567`):

    10-scripts/proof-db.sh clone p0db          # sub-second, private to you
    export DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://smartbillhub:smartbillhub@127.0.0.1:5432/sbh_clone_p0db?sslmode=disable"
    pytest tests/test_cr135_p0_rls_pg.py

AND WHY IT READS UNDER A PROBE ROLE RATHER THAN THE APPLICATION'S OWN
-----------------------------------------------------------------------
PostgreSQL exempts SUPERUSER and BYPASSRLS roles from row-level security
**unconditionally, `FORCE` included**, and the development role is often a
superuser (`DEF-2717`: a second tenant reported 73 accounts inside its own
context when it had none — the count was the other tenant's). So the reads
below run inside `SET ROLE sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS) and
`rls.assert_is_a_real_proof()` FAILS — never skips — if that role could bypass
anything.

⚠ **SET THE TENANT BEFORE COUNTING ANYTHING.** With `app.tenant_id` unset this
policy answers ZERO for every query, truthfully, and a lane that counts first
and reads the number as *the table is empty* has drawn the wrong conclusion.
That is not hypothetical: it is `DEF-PAY-6166`, filed today, where
`payments/0029`'s backfill matched **zero rows of seventy-four** and printed
`OK`. The same policy is on this table from its first migration.

WHAT IS ASSERTED, AND THE FIRST TWO ARE OFTEN CONFUSED
--------------------------------------------------------
  1. **The flags** — `relrowsecurity` AND `relforcerowsecurity` in `pg_class`.
     `ENABLE` alone exempts the table's OWNER, and the application's migration
     role owns every table in this schema, so `ENABLE` without `FORCE` is no
     policy at all for the process that matters.
  2. **The zero rows** — with no tenant, nothing; under one tenant's context,
     not one of the other's rows. A flag is a claim; this is the behaviour.
  3. **The WITH CHECK** — a row stamped for another tenant is refused BY THE
     POLICY, with `row-level security` in PostgreSQL's own message.

And SEVEN that belong to `payments/0030` rather than to the policy, and can
only run here because every one of them needs the real freeze, the real
per-tenant scope, or both. Two read the schema and the trigger; five drive the
migration's own re-derivation and are `P0.15`'s backfill half — see the block
at the foot of this file for why they were missing until 2026-09-22
(`DEF-PAY-6206`).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.db import connection
from django.utils import timezone

from apps.payments import models as payment_models
from apps.payments.counter_session_models import CounterSession
from apps.tenancy import published_content_models as content_models

from tests.isolation_helpers import (  # noqa: F401 — `rls` needs `rls_probe_role`
    assert_denied_without_context,
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    requires_postgres,
    rls,
    rls_probe_role,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin · marcus
from tests.test_us_met_helpers import tenant_ctx

pytestmark = [pytest.mark.django_db, pytest.mark.isolation]

TABLE = "counter_sessions"


def _a_till_for(tenant, owner, *, slug):
    """One open till, and the centre it is at, inside `tenant`'s context."""
    centre = content_models.ServiceCentre.objects.create(
        tenant=tenant,
        slug=slug,
        name="Main office",
        address="101 Bend Road",
    )
    # ⚠ **`owner.user`, NOT `owner` (`DEF-GOV-6703`, filed 2026-09-25, fixed the
    # same day).** `dana` and `erin` are `staff_actor()` namespaces — an ACTOR,
    # carrying `.id`, `.role` and the real `User` row as `.user` — while
    # `CounterSession.owner` is a foreign key into `users`. Django refused the
    # assignment on the first line of the test body:
    #
    #     ValueError: Cannot assign "namespace(id=…, role='system_admin',
    #     user=<User: …>)": "CounterSession.owner" must be a "User" instance.
    #
    # So both `P0.14` cases raised BEFORE the cross-tenant assertion they exist
    # to make, and the till's isolation was advertised and never performed. It
    # was red rather than silent — and nobody read the red between 2026-09-07
    # and 2026-09-25, which is hard-won law 7's *proved red, then never read*.
    # `getattr` rather than `.user` outright so a caller that already holds a
    # `User` keeps working.
    return CounterSession.objects.create(
        tenant=tenant,
        owner=getattr(owner, "user", owner),
        service_centre=centre,
        opening_float=Decimal("200.0000"),
        opened_at=timezone.now(),
    )


@requires_postgres
def test_p0_5_counter_sessions_is_enabled_AND_forced():
    """`ENABLE` is half the guarantee; `FORCE` is the half that binds the owner.

    Read out of `pg_class` rather than out of the migration file, because a
    migration that ran, a policy somebody dropped by hand and a policy that was
    never written all look the same in the source tree.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relrowsecurity, c.relforcerowsecurity "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [TABLE],
        )
        row = cursor.fetchone()
    assert row is not None, f"{TABLE} does not exist — payments/0031 did not run"
    assert row == (True, True), (
        "CLAUDE.md hard rule 1 / B2 §3: `counter_sessions` needs ENABLE *and* "
        f"FORCE ROW LEVEL SECURITY — pg_class says {row}. `P0.5`: *a tenant "
        "table with no RLS migration is hard rule 1 broken*."
    )


@requires_postgres
def test_p0_5_the_policy_denies_on_an_UNSET_tenant_rather_than_erroring():
    """The `NULLIF(…, '')` form, and the difference is the SHAPE of the refusal.

    `core/tenancy.py::clear_current_tenant` writes the EMPTY STRING, not an
    unset GUC, and `''::uuid` cannot be parsed. The older bare-cast form
    therefore RAISES *invalid input syntax for type uuid: ""* where this one
    quietly returns zero rows — and an error is not a denial, it is a denial
    that also takes down whatever else was in the statement, foreign-key
    validation included (`DEF-639`, `DEF-PAY-4054`).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT qual, with_check FROM pg_policies WHERE tablename = %s",
            [TABLE],
        )
        rows = cursor.fetchall()
    assert len(rows) == 1, f"expected exactly one policy on {TABLE}, found {len(rows)}"
    qual, with_check = rows[0]
    for name, expression in (("USING", qual), ("WITH CHECK", with_check)):
        assert expression is not None, f"{TABLE}'s policy has no {name} clause"
        assert "NULLIF" in expression, (
            f"{TABLE}'s {name} clause is the pre-DEF-639 form: {expression}. "
            "Every policy written after 2026-08-24 must deny on UNSET — "
            "`payments/0025`'s docstring says so in capitals."
        )


@requires_postgres
def test_p0_14_with_no_tenant_context_the_table_returns_nothing(brazos, rls):
    """Hard rule 1, stated as the behaviour a person can check.

    ⚠ **AND THIS IS THE ZERO THAT HAS TWICE BEEN MISREAD AS AN EMPTY TABLE.**
    It is a DENIAL. The rows exist; this session may not see them, which the
    next case proves by setting a tenant and finding them.
    """
    assert_denied_without_context(rls, TABLE)


@requires_postgres
def test_p0_14_one_tenants_till_is_invisible_to_the_other(brazos, lonestar, dana, erin, rls):
    """**`P0.14`'s first direction.** Brazos Bend's open till is not there for
    Lone Star Ridge.

    Asserted through the DATABASE under a role RLS applies to — the
    application's own `filter(tenant_id=…)` is deliberately not in the path, so
    this is the POLICY and not the ORM agreeing with itself.

    A counter session names a named employee, the desk they were at, and what
    was in their drawer at the end of the day, including whether it was short.
    A cross-tenant read of it is another utility's payroll problem.
    """
    with tenant_ctx(brazos):
        _a_till_for(brazos, dana, slug="brazos-main")
    with tenant_ctx(lonestar):
        _a_till_for(lonestar, erin, slug="lonestar-main")

    assert_rls_scoped(rls, TABLE, owner=brazos, intruder=lonestar)


@requires_postgres
def test_p0_14_a_till_stamped_for_another_tenant_is_refused_by_the_policy(
    brazos, lonestar, dana, rls
):
    """**`P0.14`'s second direction, and it is the worse one.**

    Reading across the wall exposes a drawer count; WRITING across it puts a
    till on another utility's books — so their day's takings reconcile against
    a float nobody at that utility ever counted.
    """
    with tenant_ctx(brazos):
        _a_till_for(brazos, dana, slug="brazos-main")

    message = assert_write_into_other_tenant_refused(
        rls, TABLE, owner=brazos, intruder=lonestar
    )
    assert "row-level security" in message


# ═══════════════════════════════════════════════════════════════════════════
#  payments/0030 — the two things that can only be checked on PostgreSQL
# ═══════════════════════════════════════════════════════════════════════════


@requires_postgres
def test_p0_1_the_origin_check_is_on_the_table_itself(brazos):
    """`P0.1`'s CHECK, read out of `pg_constraint` rather than out of the model.

    ⚠ **THE MODEL IS NOT THE DATABASE.** `payments/0030` could have been
    written, committed, reviewed and never applied, and every model-level
    assertion in the suite would still pass. This is the one that asks the
    server.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname, pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid = 'payments'::regclass AND conname LIKE 'ck_payments_origin%%' "
            "ORDER BY conname"
        )
        found = dict(cursor.fetchall())

    assert set(found) == {
        "ck_payments_origin",
        "ck_payments_origin_derived_needs_a_value",
    }, f"payments/0030 has not been applied to this database: {sorted(found)}"
    for value in payment_models.PAYMENT_ORIGINS:
        assert f"'{value}'" in found["ck_payments_origin"], (
            f"{value!r} is in PAYMENT_ORIGINS and not in the database's CHECK — "
            "the model and the schema disagree about what a payment may say."
        )


@requires_postgres
def test_p0_2_the_backfill_left_the_payments_freeze_switched_back_ON():
    """⚠ **`DEF-PAY-6165`'s other half, and nothing else in this repository
    looks at it.**

    `payments/0030` takes `trg_payment_immutable` off to run its re-derivation
    and puts it straight back. If a future edit dropped the ENABLE, every other
    check in this suite would still be green and `payments` would be open to
    UPDATE for the life of the database — CLAUDE.md hard rule 4, silently off.

    `'O'` is *enabled, fires on origin*; `'D'` is disabled.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE c.relname = 'payments' AND t.tgname = 'trg_payment_immutable'"
        )
        row = cursor.fetchone()
    assert row is not None, (
        "trg_payment_immutable is missing from `payments`. The freeze CLAUDE.md "
        "hard rule 4 rests on is not there."
    )
    assert row[0] == "O", (
        f"trg_payment_immutable is in state {row[0]!r}, not 'O'. A migration "
        "took the payments freeze off and did not put it back."
    )


# ═══════════════════════════════════════════════════════════════════════════
#  P0.15 — THE BACKFILL CASES, DRIVING `payments/0030`'s OWN FUNCTION
# ═══════════════════════════════════════════════════════════════════════════
#
# `P0.15`, verbatim: *"The partial index refuses a second OPEN till and permits
# a second CLOSED one. Four backfill cases including the loud failure."*
# Outcome: *"The easy-to-miss half is covered."*
#
# The CONSTRAINT half is `test_cr135_p0_foundations.py` — a partial unique
# index is one of the few guarantees SQLite can genuinely answer, so it is
# checked where the whole suite runs.
#
# ⚠ **THE BACKFILL HALF WAS NOT COVERED ANYWHERE, AND A DOCSTRING SAID IT WAS**
# (`DEF-PAY-6206`). `test_cr135_p0_foundations.py`'s header reads *"`payments/
# 0030`'s re-derivation as it really runs — the per-tenant pass only exists on
# PostgreSQL. **Its cases are in the `_pg` file**"*, and until this block landed
# the `_pg` file held nothing that ran it. That is CLAUDE.md hard-won law 1 word
# for word: *a comment claiming a guarantee is not the guarantee* — and it is
# the more expensive direction of it, because the next lane reads *already
# covered* and writes no case. The five cases below are that gap closed.
#
# ⚠ **THEY DRIVE `re_derive_from_the_import_link` ITSELF, NOT A COPY OF ITS
# SQL.** A test that re-types the UPDATE proves the test's SQL works. What has
# to hold is that the shipped migration — the freeze coming off and going back,
# the tenant loop, the `EXISTS` on `payment_import_rows`, the two guards on
# `origin_is_derived` — does what its docstring says. So the module is imported
# and its function called with the real connection.
#
# ⚠ **AND THE FOUR CASES ARE THE ONES THAT WERE BUILT, NOT THE ONES THE DRAWING
# LISTS, BECAUSE THE DRAWING'S FIRST DERIVATION WAS MEASURED WRONG.** `P0.2`
# names *"non-null webhook_key → digital · named by a payment_import_rows.
# payment_id → post · otherwise counter"*; the first clause misclassifies 74 of
# 74 real rows and the decision log of 2026-09-22 records why. What shipped is
# the SECOND clause applied over the key-prefix derivation `payments/0029`
# already ran, under one rule: **an inference never overrules an observation.**
# Those are the four states a row can be in, and each is one case. The loud
# failure — a fourth value refused by name — is
# `test_cr135_p0_foundations.py::test_p0_2_a_fourth_origin_value_fails_loudly`.

PAYMENTS_0030 = "apps.payments.migrations.0030_cr135_p0_1_p0_2_origin_check"


def _run_the_backfill():
    """Call `payments/0030`'s re-derivation against THIS connection.

    ⚠ **`connection.schema_editor()` rather than a hand-rolled stand-in.** The
    function reads `schema_editor.connection.vendor` to decide whether there is
    a freeze and a policy to work around at all, and a stand-in that answered
    `"postgresql"` while holding something else would be testing the branch and
    not the behaviour. This is the object the migration framework passes it.

    ⚠ **`SET CONSTRAINTS ALL IMMEDIATE` FIRST, AND IT IS A HARNESS ARTEFACT
    RATHER THAN ANYTHING THE MIGRATION NEEDS.** Django wraps each case in one
    transaction and declares its foreign keys `DEFERRABLE INITIALLY DEFERRED`,
    so rows written in a case leave **pending trigger events** on `payments`.
    PostgreSQL then refuses the migration's very first statement:

        psycopg.errors.ObjectInUse: cannot ALTER TABLE "payments" because it
        has pending trigger events

    A real migration never meets this — it runs in its own transaction with
    nothing outstanding on the table. Flushing the deferred checks here puts
    the connection into the state a migration actually finds. **It is written
    out because the next lane meeting that message will otherwise read it as
    `payments/0030` being broken**, which is exactly what it looks like.
    """
    from importlib import import_module

    from django.apps import apps as global_apps

    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    migration = import_module(PAYMENTS_0030)
    with connection.schema_editor(atomic=False) as editor:
        migration.re_derive_from_the_import_link(global_apps, editor)


def _an_import_row_naming(tenant, payment, *, row_no=1):
    """A staged import row that says *this file created that payment*.

    The link the re-derivation reads is `payment_import_rows.payment_id`, which
    is a bare uuid and not a foreign key — `PaymentImportRow`'s own docstring
    says why: a staging row names a payment without opening a second write path
    into `payments`. So this fixture writes exactly that column.
    """
    batch = payment_models.PaymentImportBatch.objects.create(
        tenant=tenant, source_kind="lockbox", file_name="bank-2026-09-22.txt"
    )
    return payment_models.PaymentImportRow.objects.create(
        tenant=tenant,
        batch=batch,
        row_no=row_no,
        amount=payment.amount,
        payment_id=payment.id,
    )


def _an_account_in(tenant, actor, *, account_no, service):
    """An account in `tenant`, on a service THAT tenant actually has enabled.

    ⚠ **`tests.test_w3_billing_models.an_account` hardcodes `electric`**, and
    the isolation tenant (Lone Star Ridge) is provisioned **Water only** — so
    calling it there fails at premises creation with
    `VAL-005 (metering.service_not_enabled)` before a payment can exist at all.
    That is the fixture being honest: a utility cannot take a connection for a
    service it does not sell. The two-tenant case below needs an account on
    each side of the wall, so it names the service rather than assuming one.
    """
    from apps.customers import models as customer_models

    # ⚠ BOTH calls name the service. `make_premises` defaults
    # `services_available` to `["electric", "water"]`, so on a water-only tenant
    # the PREMISES is refused before the unit is ever reached — which is the
    # same VAL-005 and one step earlier than a reader expects.
    premises = make_premises(
        actor,
        address_line=f"1901 Bluestem Ln {account_no}",
        services_available=[service],
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=[service])
    statuses = customer_models.AccountStatus.objects.filter(tenant=tenant)
    status = statuses.filter(code="active").first() or statuses.first()
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=status,
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


def _a_payment(tenant, *, origin, derived, actor, account_no, service="electric"):
    """One `payments` row in a STATED origin state.

    ⚠ **CREATED, NEVER UPDATED INTO PLACE.** `trg_payment_immutable` compares
    whole rows minus a three-column allow list and refuses any UPDATE to a
    payment that is not `processing` — and `origin` is not on that list in any
    status. So the starting state has to be written by the INSERT, which the
    trigger does not fire on. A test that set it up with `.save()` would be
    testing the freeze, in a file whose subject is the backfill.
    """
    account = _an_account_in(tenant, actor, account_no=account_no, service=service)
    return payment_models.Payment.objects.create(
        tenant=tenant,
        account=account,
        amount=Decimal("142.180000"),
        currency="USD",
        posted_at=timezone.now(),
        origin=origin,
        origin_is_derived=derived,
    )


@requires_postgres
def test_p0_15_backfill_a_derived_guess_with_an_import_link_is_corrected(brazos, marcus):
    """**Case 1 — the one the pass exists for.**

    `payments/0029` guessed this row's origin from its idempotency key prefix
    and marked the guess. A row in `payment_import_rows` naming the payment is
    an OBSERVED fact about where the money came from, so it wins — and the
    result is STILL marked derived, because a better guess is still a guess.
    That last clause is the PO's ruling of 2026-09-22 held intact: the
    backfilled value *"is a DERIVATION, not an observed fact, and must be
    marked as one"*.
    """
    with tenant_ctx(brazos):
        payment = _a_payment(
            brazos, origin="entry", derived=True, actor=marcus, account_no="A-P015-1"
        )
        _an_import_row_naming(brazos, payment)

    _run_the_backfill()

    with tenant_ctx(brazos):
        payment.refresh_from_db()
    assert payment.origin == "import", (
        "a payment named by a row in `payment_import_rows` came in on a FILE. "
        f"payments/0030 left it as {payment.origin!r}."
    )
    assert payment.origin_is_derived is True, (
        "the corrected value is derived from a link instead of from a prefix, "
        "and is still derived. Clearing the marker would present an inference "
        "as evidence — PO ruling 2026-09-22."
    )


@requires_postgres
def test_p0_15_backfill_an_OBSERVED_origin_with_an_import_link_is_left_alone(brazos, marcus):
    """**Case 2 — an inference never overrules an observation, and this is the
    case that makes the pass safe to run on a live deployment.**

    This row's caller STATED its origin at creation (`origin_is_derived =
    FALSE`). The import link says something different. The pass does not touch
    it: a re-derivation that overwrote observed facts would be a migration
    quietly rewriting the record of where real money came from.

    ⚠ **This is also the one that would go green by accident.** If the `WHERE
    origin_is_derived = TRUE OR origin IS NULL` guard were dropped, cases 1 and
    3 would still pass and only this one would fail — which is why it is worth
    a case of its own rather than a clause in another.
    """
    with tenant_ctx(brazos):
        payment = _a_payment(
            brazos, origin="entry", derived=False, actor=marcus, account_no="A-P015-2"
        )
        _an_import_row_naming(brazos, payment)

    _run_the_backfill()

    with tenant_ctx(brazos):
        payment.refresh_from_db()
    assert payment.origin == "entry", (
        "payments/0030 overwrote an OBSERVED origin with an inference. Its own "
        "docstring: *an inference never overrules an observation*."
    )
    assert payment.origin_is_derived is False



@requires_postgres
def test_p0_15_backfill_a_NULL_origin_with_an_import_link_is_filled_in(brazos, marcus):
    """**Case 3 — *nobody told us* becomes *it came in on a file*.**

    A NULL origin is lawful and means exactly that (`payments/0030` does not add
    `NOT NULL`, and the reason is a sixth `Payment` creation site that passes no
    origin — `DEF-PAY-6196`). When a link turns up, the pass fills the gap and
    marks the value DERIVED, which is the state
    `ck_payments_origin_derived_needs_a_value` was written to keep honest:
    `TRUE` with no value is refused, so a row cannot claim to have inferred
    nothing.
    """
    with tenant_ctx(brazos):
        payment = _a_payment(
            brazos, origin=None, derived=False, actor=marcus, account_no="A-P015-3"
        )
        _an_import_row_naming(brazos, payment)

    _run_the_backfill()

    with tenant_ctx(brazos):
        payment.refresh_from_db()
    assert payment.origin == "import"
    assert payment.origin_is_derived is True, (
        "a value this pass supplied is an inference and is marked as one — "
        "PO ruling 2026-09-22."
    )


@requires_postgres
def test_p0_15_backfill_a_derived_guess_with_NO_import_link_is_untouched(brazos, marcus):
    """**Case 4 — the pass corrects what it has evidence about and nothing else.**

    No row in `payment_import_rows` names this payment, so there is nothing
    better than the key-prefix guess `payments/0029` already recorded. A pass
    that moved this row would be replacing one inference with another on no
    evidence at all — and on the demo clone this is **74 of the 74 rows**, so
    the default behaviour of the whole migration is *leave it alone*.
    """
    with tenant_ctx(brazos):
        payment = _a_payment(
            brazos, origin="entry", derived=True, actor=marcus, account_no="A-P015-4"
        )

    _run_the_backfill()

    with tenant_ctx(brazos):
        payment.refresh_from_db()
    assert payment.origin == "entry"
    assert payment.origin_is_derived is True


@requires_postgres
def test_p0_15_backfill_reaches_EVERY_tenant_and_not_only_the_first(
    brazos, lonestar, marcus, erin
):
    """⚠ **`DEF-PAY-6166`'s cure, asserted as behaviour rather than as a loop.**

    `payments` carries RLS **FORCE** and a migration runs with no tenant set, so
    an unscoped UPDATE matches **zero rows and prints OK** — which is how
    `payments/0029`'s backfill reported success over seventy-four rows it never
    saw. `payments/0030` answers it by entering each tenant with
    `set_config('app.tenant_id', …, true)`.

    **What would make this pass wrongly:** a loop that entered the first tenant
    and stopped, or one that never left a tenant and therefore corrected only
    that one. Two tenants, one correctable payment in each, and both must move —
    with a single-tenant case this whole class is invisible.
    """
    with tenant_ctx(brazos):
        theirs = _a_payment(
            brazos, origin="entry", derived=True, actor=marcus, account_no="A-P015-5A"
        )
        _an_import_row_naming(brazos, theirs)
    with tenant_ctx(lonestar):
        others = _a_payment(
            lonestar,
            origin="entry",
            derived=True,
            actor=erin,
            account_no="A-P015-5B",
            # Lone Star Ridge is provisioned WATER ONLY — see `_an_account_in`.
            service="water",
        )
        _an_import_row_naming(lonestar, others)

    _run_the_backfill()

    with tenant_ctx(brazos):
        theirs.refresh_from_db()
    with tenant_ctx(lonestar):
        others.refresh_from_db()
    assert (theirs.origin, others.origin) == ("import", "import"), (
        "the per-tenant pass corrected "
        f"{theirs.origin!r} for the first tenant and {others.origin!r} for the "
        "second. A pass that only reaches one tenant is DEF-PAY-6166 with a "
        "different loop — it reports OK over rows it never saw."
    )


@requires_postgres
def test_p0_15_the_backfill_leaves_the_freeze_ON_even_when_it_moves_rows(brazos, marcus):
    """⚠ **`DEF-PAY-6165`, checked on the path where the freeze actually has to
    come off.**

    `test_p0_2_the_backfill_left_the_payments_freeze_switched_back_ON` above
    reads the trigger's state after the migration ran at database build time,
    when there was nothing to re-derive. This one runs the pass over a row it
    WILL move and then asks the same question — because a re-enable inside a
    `finally` and a re-enable on the happy path are different code, and only one
    of them was being checked.

    `'O'` is *enabled, fires on origin*; `'D'` is disabled.
    """
    with tenant_ctx(brazos):
        payment = _a_payment(
            brazos, origin="entry", derived=True, actor=marcus, account_no="A-P015-6"
        )
        _an_import_row_naming(brazos, payment)

    _run_the_backfill()

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT t.tgenabled FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
            "WHERE c.relname = 'payments' AND t.tgname = 'trg_payment_immutable'"
        )
        row = cursor.fetchone()
    assert row is not None and row[0] == "O", (
        "payments/0030 moved a row and left `trg_payment_immutable` at "
        f"{row and row[0]!r}. Hard rule 4 would be off for the life of the "
        "database and every other check in this suite would still be green."
    )

# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, tasks `P0.1` and
#          `P0.2`. PO ruling 2026-09-22, verbatim: *"(a) One column — extend
#          what we shipped — Rename or map the three values, add the check the
#          blueprint wants."*
# Rules:   CLAUDE.md hard rule 4 (financial immutability — the freeze comes off
#          for this statement and goes straight back; the allow list in
#          `payments/0014` is NOT widened) · hard rule 1 (tenant scoping — the
#          re-derivation walks tenants under RLS) · hard rule 7 (a re-derivation
#          moves no money and writes no audit row — see below)
# Tests:   06-backend/tests/test_cr135_p0_foundations.py — the constraint
#          cases, the loud failure, and the creation-site enumeration ·
#          06-backend/tests/test_cr135_p0_rls_pg.py — `P0.15`'s four BACKFILL
#          cases, which drive `re_derive_from_the_import_link` itself, and the
#          freeze. They are in the `_pg` file because the per-tenant pass only
#          exists on PostgreSQL.
#          ⚠ This line named `test_cr135_p0_origin_check.py` until 2026-09-22
#          and no such file has ever existed (`DEF-PAY-6205`).
# Impacts: apps/payments/models.Payment.Meta.constraints (ck_payments_origin,
#          ck_payments_origin_derived_needs_a_value) ·
#          apps/payments/migrations/0029_cr132_payment_origin.py (the column
#          this extends) · apps/integrations/seams/payments.ORIGIN_ONLINE
# ───────────────────────────────────────────────────────
"""payments 0030 — THE SOURCE COLUMN GETS ITS CHECK. HUMAN-OWNED.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*). It is a 🔒
sensitive path twice over — **migration ordering** and a constraint on the
**money** table — so it carries a row in
`12-governance/09-human-review-ledger.md` and may never reach lifecycle
RATIFIED without a recorded human sign-off.

WHAT THE BLUEPRINT ASKED FOR AND WHAT IS BUILT
-----------------------------------------------
`P0.1` asks for `payments.source`, *"a text column with a CHECK over counter |
digital | post"*, and names `payments/0029` as its reference. **That migration
number was taken the same morning**: `CR-132-BRC07` shipped `payments.origin`
— `entry | webhook | import` — plus `origin_is_derived`, as `payments/0029`.
The document says of itself that every as-built statement was true at
`2.322.0` on 2026-09-21 and *"must be re-verified before it is trusted"*; this
is that warning coming true within a day, and the PO ruled ONE column.

So there is no `payments.source`. This adds the CHECK to the column that
exists, and re-derives the one clause of `P0.2` that turns out to be better
evidence than what shipped.

⚠ THE STORED WORDS DO NOT MOVE, AND THE REASON IS CORRECTNESS RATHER THAN COST
-------------------------------------------------------------------------------
The ruling offers *"Rename OR map"*. This is the MAP, argued in full in the
decision log of 2026-09-22 under *"THE SOURCE COLUMN KEEPS THE WORDS IT WAS
BORN WITH"*. The short form:

  * `apps/payments/transfer.py` writes `entry` for **both legs of an internal
    transfer** and `apps/payments/reversal.py` writes it for a bounce. Neither
    is money handed over at a service desk. `entry` says *a person keyed this
    row*, which is true of all five creation sites; `counter` would say *this
    was taken at a counter*, which is false for three of them.
  * The three values are the same three strings as the `<source>` segment of
    the idempotency key (`apps/payments/idempotency.py`), deliberately, and
    four creation sites pass that segment straight through as
    `origin=idempotency_source`. Renaming the column values without renaming
    the key prefixes — which are a UNIQUE key and 🔒 Eng-Lead mechanics —
    would put two vocabularies for one fact inside the money module.
  * `counter · digital · post` are LABELS and belong in the i18n catalogue
    with every other label (B14 rule 31; `reversal_reason` already stores
    `bank_chargeback` and shows *Bank chargeback*).

⚠ `P0.2`'s FIRST DERIVATION IS WRONG ABOUT THIS DATABASE, AND IT WAS MEASURED
------------------------------------------------------------------------------
`P0.2` says: *"non-null `webhook_key` → digital · named by a
`payment_import_rows.payment_id` → post · otherwise counter."*

Measured on a PostgreSQL 16 clone of the demo database on 2026-09-22, inside
the tenant context (`brazosbend`, `01a0c23c-…`), because `payments` carries RLS
**FORCE** and an unscoped count answers 0:

    payments                                            74
    with a non-null webhook_key                         74
    whose key prefix is `entry|`                        74
    named by a row in payment_import_rows                0
    rows in payment_import_rows at all                   0

**So `non-null webhook_key → digital` misclassifies 74 of 74 rows.**
`webhook_key` is not a webhook marker — it is the generic idempotency key, and
`idempotency.py` composes `"<source>|<reference>"` for all three sources. The
blueprint read the column's NAME. The shipped derivation reads its CONTENTS and
gets 74 of 74 right, so it stands and this migration does not touch it.

The SECOND clause is a genuine improvement and is what this migration applies.
A row in `payment_import_rows` naming the payment is an OBSERVED fact; a string
prefix is a label the importer chose. So where the two disagree the link wins.
**On today's data that set is empty — 0 rows of 74 — and the pass is expected
to move nothing.** It is written anyway because the Product Owner's live
deployment is not this database: it raised on `payments/0029` where this one
silently did nothing (`DEF-PAY-6165` / `DEF-PAY-6166`), so it demonstrably
holds rows this clone does not.

⚠ AN INFERENCE NEVER OVERRULES AN OBSERVATION
-----------------------------------------------
The re-derivation touches a row only where `origin_is_derived` is TRUE (the
value was guessed by `payments/0029`) or the origin is NULL (nobody told us).
**A row whose caller stated its origin is left exactly as it is**, because this
pass is a better guess and a better guess is still a guess. Rows it does move
keep `origin_is_derived = TRUE` — derived from a link rather than from a
prefix, and still derived. That is the PO's ruling of 2026-09-22 held intact:
the backfilled value *"is a DERIVATION, not an observed fact, and must be
marked as one"*.

⚠ WHY THERE IS NO `NOT NULL`, AND IT IS MEASURED RATHER THAN INHERITED
------------------------------------------------------------------------
`P0.2`'s outcome asks for *"No nulls"*. `payments/0029` argues the column must
stay nullable because *"a fifth creation site added by a lane that has not read
this file would fail its INSERT"*. **That site already exists and predates the
argument.** `apps/integrations/management/commands/seed_partner_morning.py:232`
bulk-creates `Payment` rows and passes no origin at all — a SIXTH creation
site, where `payments/0029`'s own `Impacts:` line counts four. Filed as
`DEF-PAY-6196`. A `NOT NULL` here would have failed that command on the day it
was added, and CLAUDE.md hard-won law 3 says the unsafe option must be the one
you type.

**What `P0.2` actually buys is refused instead: the FOURTH VALUE.**
`ck_payments_origin` rejects `'cheque'` or `'lockbox'` by name, from every
path, rather than letting it land as an origin no filter finds and no
reconciliation classifies. *"Fails loudly rather than defaulting"* is served;
NOT NULL is not, and the reason is written down rather than assumed.

The *"no nulls"* half is enforced where it can actually be checked — at merge,
not at 2am — by `test_cr135_p0_foundations.py::
test_p0_2_every_payment_creation_site_states_an_origin`, which enumerates the
creation sites rather than counting rows.

⚠ TWO DEFECTS SHIPPED FROM THIS TABLE ONE MIGRATION AGO AND BOTH APPLY HERE
-----------------------------------------------------------------------------
`DEF-PAY-6165` — `trg_payment_immutable` refuses any UPDATE to a cleared
payment, a column added later included (`payments/0014`'s whole-row
comparison). So the freeze comes off for the statement and goes straight back
**inside this migration's own transaction**, exactly as
`payments/0018_cr059_cs7_refund_account.py` does for `trg_refund_immutable`.
**The allow list in `payments/0014` is NOT widened** — CLAUDE.md hard rule 4:
*"`payments/0014` is the ONLY place the database's allow list moves; widening
it anywhere else is a new ruling, not this one."*

`DEF-PAY-6166` — `payments` carries RLS **FORCE** and a migration runs with no
tenant set, so an unscoped UPDATE matches zero rows and prints `OK`. The pass
below enters each tenant with `set_config('app.tenant_id', id, true)`.

⚠ AND THE ONE OPERATION IN THIS FILE THAT RLS CANNOT FOOL IS THE CONSTRAINT
-----------------------------------------------------------------------------
This is the answer to hard-won law 7's *what would make this check pass
wrongly*. The UPDATE can see nothing if the tenant loop is wrong, and that
failure is silent — it is exactly `DEF-PAY-6166`. **`ALTER TABLE … ADD
CONSTRAINT` is not.** Adding a CHECK validates every existing row through the
table scan the DDL itself performs, which is not filtered by a row-level
security policy, so a fourth value hiding in a tenant this migration never
entered still refuses the migration. **Measured on the clone on 2026-09-22, in
one session, with `app.tenant_id` unset** — quoted rather than described,
because hard-won law 1 says a comment claiming a guarantee is not the
guarantee:

    SELECT count(*) FROM payments;                        →  0
    ALTER TABLE payments ADD CONSTRAINT tmp CHECK (origin = 'nonsense');
    →  ERROR: check constraint "tmp" of relation "payments"
              is violated by some row

Zero rows to the SELECT, and the DDL still saw all seventy-four. ⚠ Note what
PostgreSQL does NOT say: *"some row"*, never a count and never an id. So the
constraint is a reliable REFUSAL and a useless diagnosis — if it ever fires,
the row has to be found by entering each tenant and looking. The constraint is
the belt; the tenant loop is the braces.

⚠ NO `audit_log` ROW, AND HARD RULE 7 IS WHY RATHER THAN AN EXCEPTION TO IT
-----------------------------------------------------------------------------
The same reasoning `payments/0029` records: rule 7 covers every money ACTION.
Adding a constraint moves no money, and re-labelling a derived origin changes
no amount, date, status, account or reference. The audit row that matters
already exists on each of these payments, written when the money was taken, and
what records THIS change is the migration plus `origin_is_derived` — which is a
permanent marker where `audit_log` is pruned on a retention schedule (hard rule
4's note, `OQ-1340`, OPEN).
"""

from django.db import migrations, models

#: Spelled out rather than imported from `apps/payments/models.py`. ⚠ **A
#: migration is a historical record and must go on producing the same schema
#: when that module's vocabulary changes** — which is the whole reason
#: migrations do not import application constants, and it is the same note
#: `payments/0029` carries three lines above its own copy.
ORIGIN_ENTRY = "entry"
ORIGIN_WEBHOOK = "webhook"
ORIGIN_IMPORT = "import"
ORIGINS = (ORIGIN_ENTRY, ORIGIN_WEBHOOK, ORIGIN_IMPORT)

#: The freeze, by name. `payments/0002` creates it and nothing has renamed it.
IMMUTABILITY_TRIGGER = "trg_payment_immutable"
DISABLE_FREEZE = f"ALTER TABLE payments DISABLE TRIGGER {IMMUTABILITY_TRIGGER}"
ENABLE_FREEZE = f"ALTER TABLE payments ENABLE TRIGGER {IMMUTABILITY_TRIGGER}"

#: `'O'` is PostgreSQL's "enabled, fires on origin" — the normal state and the
#: one `ENABLE TRIGGER` restores. `'D'` is disabled.
FREEZE_STATE = """
    SELECT t.tgenabled
      FROM pg_trigger t
      JOIN pg_class c ON c.oid = t.tgrelid
     WHERE c.relname = 'payments'
       AND t.tgname = %s
"""

#: Transaction-local, id bound as a parameter and never interpolated — the cure
#: `billing/0029` and `payments/0029` both carry for `DEF-BIL-5382` /
#: `DEF-PAY-6166`. `tenants` itself carries no RLS, so the list can be read.
ENTER_TENANT = "SELECT set_config('app.tenant_id', %s, true)"
LEAVE_TENANT = "SELECT set_config('app.tenant_id', '', true)"

VISIBLE_PAYMENTS = "SELECT count(*) FROM payments"

#: The blueprint's second clause, applied only where it is better evidence than
#: what is already recorded. See the docstring: an inference never overrules an
#: observation, so `origin_is_derived = FALSE` rows are untouched.
#
# ⚠ **NO TABLE ALIAS, AND NO `IS DISTINCT FROM` — BOTH ARE DELIBERATE AND BOTH
# WERE LEARNED THE HARD WAY HERE (`DEF-PAY-6197`).** This statement was first
# written `UPDATE payments p SET …`, which PostgreSQL accepts and **SQLite
# refuses** (`near "p": syntax error` — SQLite's `qualified-table-name` requires
# the `AS` keyword before an alias). A migration that will not parse cannot be
# applied, so the whole test database failed to build and **every backend test
# on the branch errored at setup**, naming nothing.
#
# That is CLAUDE.md hard-won law 14 running BACKWARDS, and it is the safe
# direction: the law's usual case is SQLite hiding a PostgreSQL failure, where
# the suite is green and production breaks. Here SQLite refused what PostgreSQL
# allows, so the branch went red at once. **The rule this leaves behind is
# neither vendor's: raw SQL in a migration is written in the intersection of
# the two, because the suite runs on one and the customer runs on the other.**
# Hence `(origin IS NULL OR origin <> %s)` rather than `IS DISTINCT FROM`,
# which SQLite has only since 3.39 and which nothing here pins.
RE_DERIVE_FROM_IMPORT_LINK = """
    UPDATE payments
       SET origin = %s,
           origin_is_derived = TRUE
     WHERE (origin_is_derived = TRUE OR origin IS NULL)
       AND (origin IS NULL OR origin <> %s)
       AND EXISTS (SELECT 1
                     FROM payment_import_rows r
                    WHERE r.payment_id = payments.id)
"""


def assert_the_freeze_is_back(cursor):
    """Refuse to finish with `payments` unfrozen.

    ⚠ Copied deliberately from `payments/0029` rather than imported: a
    migration is a historical record. Everything else in this file would be
    green if a future edit dropped the ENABLE — the constraints added, the
    values right, the tests unchanged — and `payments` would be open to UPDATE
    for the life of the database. Nothing else in this repository reads
    `pg_trigger`.
    """
    cursor.execute(FREEZE_STATE, [IMMUTABILITY_TRIGGER])
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            f"payments/0030: trigger {IMMUTABILITY_TRIGGER} is missing from "
            "`payments`. The freeze CLAUDE.md hard rule 4 rests on is not "
            "there; refusing to finish."
        )
    if row[0] != "O":
        raise RuntimeError(
            f"payments/0030: trigger {IMMUTABILITY_TRIGGER} is in state "
            f"{row[0]!r}, not 'O'. This migration took the payments freeze off "
            "and did not put it back; refusing to finish with hard rule 4 off."
        )


def re_derive_in_every_tenant(cursor, tenant_ids):
    """Run the re-derivation in every tenant's context and REPORT what it saw.

    ⚠ **THE COUNTS ARE PRINTED AND NOT ASSERTED, AND THAT IS THE HONEST SHAPE
    HERE.** `payments/0029`'s `assert_every_row_was_stamped` can demand a
    non-zero result because it stamps EVERY row; this pass corrects a subset
    that is legitimately empty on a database with no imported payments — 0 of
    74 on the demo clone, measured. So an assertion on the re-derived count
    would be a check that fails on correct data.

    What it prints instead is the pair CLAUDE.md hard-won law 7 asks for: how
    many rows the pass could SEE beside how many it changed. *"A declared blind
    spot with no NUMBER attached is indistinguishable from an empty one"* —
    `tenant …: 74 visible, 0 re-derived` and `tenant …: 0 visible, 0
    re-derived` are the two outcomes `DEF-PAY-6166` could not tell apart, and
    they are now different lines of output.
    """
    seen = changed = 0
    for tenant_id in tenant_ids:
        cursor.execute(ENTER_TENANT, [str(tenant_id)])
        cursor.execute(VISIBLE_PAYMENTS)
        visible = cursor.fetchone()[0]
        cursor.execute(RE_DERIVE_FROM_IMPORT_LINK, [ORIGIN_IMPORT, ORIGIN_IMPORT])
        moved = cursor.rowcount
        seen += visible
        changed += moved
        print(f"  payments/0030: tenant {tenant_id}: {visible} visible, {moved} re-derived")
    cursor.execute(LEAVE_TENANT)
    print(f"  payments/0030: {seen} payment row(s) visible in total, {changed} re-derived")


def re_derive_from_the_import_link(apps, schema_editor):
    """`P0.2`'s second clause, where it is better evidence than the key prefix.

    The freeze comes off for the statement and goes straight back in the same
    transaction (`DEF-PAY-6165`), and the pass enters each tenant so RLS lets
    the UPDATE see the rows (`DEF-PAY-6166`).
    """
    if schema_editor.connection.vendor != "postgresql":
        # SQLite: no RLS, no triggers. One pass over the whole table — and the
        # asymmetry is the whole of CLAUDE.md hard-won law 14, which is why
        # `payments/0029`'s first version was green on every machine here and
        # blocked the Product Owner's release.
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(RE_DERIVE_FROM_IMPORT_LINK, [ORIGIN_IMPORT, ORIGIN_IMPORT])
        return

    Tenant = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(Tenant.objects.values_list("id", flat=True))
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DISABLE_FREEZE)
        try:
            re_derive_in_every_tenant(cursor, tenant_ids)
        finally:
            # ⚠ The `finally` is load-bearing: a failure anywhere in the pass
            # must not leave `payments` unfrozen for the rest of the
            # transaction, and the assertion below is what proves it did not.
            cursor.execute(ENABLE_FREEZE)
        assert_the_freeze_is_back(cursor)


def leave_the_values_alone(apps, schema_editor):
    """The reverse of the re-derivation is deliberately a no-op.

    ⚠ **THIS IS NOT LAZINESS AND IT IS NOT IRREVERSIBILITY EITHER.** Reversing
    this migration removes the two CHECKs, which is the part that has a shape
    to undo. The UPDATE it also ran replaced one DERIVED value with another
    DERIVED value on the same rows, and there is no record of what the first
    guess was — `payments/0029` did not keep one, and inventing one to restore
    would be a worse lie than the guess it replaced. The rows stay where they
    are, still marked `origin_is_derived = TRUE`, which is the true statement
    in both directions.

    Named rather than `migrations.RunPython.noop` so the reason is attached to
    the thing it explains (CLAUDE.md hard-won law 1).
    """
    return


class Migration(migrations.Migration):
    # `tenancy` is here because the re-derivation reads the tenant list to
    # scope itself (`DEF-PAY-6166`). Without it the historical model registry
    # may not carry `Tenant` when this migration runs.
    dependencies = [
        ("payments", "0029_cr132_payment_origin"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        # ORDER MATTERS AND IT IS THE SAFE DIRECTION. The re-derivation runs
        # FIRST, so if it ever produced a value outside the three the CHECK
        # that follows refuses the migration rather than recording it as
        # applied over data it has not validated.
        migrations.RunPython(re_derive_from_the_import_link, leave_the_values_alone),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(origin__in=ORIGINS) | models.Q(origin__isnull=True),
                name="ck_payments_origin",
            ),
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                condition=models.Q(origin__isnull=False) | models.Q(origin_is_derived=False),
                name="ck_payments_origin_derived_needs_a_value",
            ),
        ),
    ]

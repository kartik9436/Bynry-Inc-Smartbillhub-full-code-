# ── Trace ──────────────────────────────────────────────
# Change:  CR-132-BRC07 — the New World / Logos receipt feed, which selects
#          `origin = webhook`. PO ruling 2026-09-22, decision log "NEW WORLD /
#          LOGOS: A SEPARATE ENDPOINT FOR THE RECEIPT, THE LEDGER REUSED
#          UNCHANGED", verbatim: *"we need to filter it based on origin -
#          webhooks only … or we might have to save the source seprately - and
#          make it available to import and entry also - what do you think"*.
# Rules:   CLAUDE.md hard rule 4 (WRITE-ONCE — nothing updates an issued
#          payment; this column is written at creation and never again, and it
#          is NOT one of the three the PO opened to correction on 2026-09-02) ·
#          hard rule 1 (tenant scoping — the backfill runs per tenant under
#          RLS) · hard rule 7 (every money action writes `audit_log`; a
#          BACKFILL is not a money action and writes none — see below)
# Tests:   tests/test_cr132_newworld_endpoint.py — `seeded_payments` records one
#          payment per origin through `record_payment` and
#          `test_only_webhook_origin_reaches_the_feed` proves the column
#          selects. ⚠ Named exactly, because a `Tests:` line pointing at a file
#          that does not exist says *this is covered* and the case never gets
#          written (`DEF-RBS-4335`).
# Impacts: apps/payments/models.Payment.origin + .origin_is_derived ·
#          apps/payments/services.record_payment · transfer.py · reversal.py ·
#          counter_receipts.py (the four places a payment row is created) ·
#          apps/integrations/newworld.py (the feed that reads it)
# ───────────────────────────────────────────────────────
"""payments 0029 — WHERE THE MONEY CAME FROM, AS A COLUMN. HUMAN-OWNED.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). It is a 🔒 sensitive path
twice over — **migration ordering** and a column on the **money** table — so it
carries a row in `12-governance/09-human-review-ledger.md` and may never reach
lifecycle RATIFIED without a recorded human sign-off. What would be put to the
Product Owner is written out in that row, in plain English with its figures.

WHY IT IS NOT READ OUT OF THE IDEMPOTENCY KEY, WHICH IS WHERE IT LIVED
-----------------------------------------------------------------------
A payment's origin has existed since `US-PAY-001` as a **prefix inside a
string**: `apps/payments/idempotency.py` composes `"<source>|<reference>"` and
its three sources are exactly `entry · webhook · import`. It is not a column,
not indexed and not queryable, and reading it back is `webhook_key.split("|")`.

Three reasons it becomes a column, and the third is the one that decided it:

  1 **The key's job is preventing duplicates, not reporting.** `webhook_key`
    exists to make double delivery one row (`BR-PAY-003`, `uq_payments_
    webhook_key`). Reading it as an origin gives one field two meanings, and
    the next lane to change the key's shape — which that file's own docstring
    says is delegated mechanics, `BR-PAY-028` *"key mechanics Eng-Lead 🔒"* —
    breaks a report nobody connected to it.
  2 **There were already TWO half-answers.** The key prefix, and
    `payment_import_batches.source_kind`. Two places that can disagree is a
    shape this product has recorded going wrong more than once.
  3 **`webhook_key` IS NULL WHENEVER NO IDEMPOTENCY REFERENCE WAS GIVEN.**
    `record_payment` composes the key only `if idempotency_reference is not
    None`, and the transfer, reversal and counter-receipt paths write no key at
    all. So the derivation is not merely awkward — **it is absent on real rows
    and silently returns nothing for them.**

⚠ THE BACKFILL IS A DERIVATION AND IT IS MARKED AS ONE
-------------------------------------------------------
PO ruling, and it is half the instruction rather than a caveat: the backfilled
value **"is a DERIVATION, not an observed fact, and must be marked as one"**.

So this migration writes TWO columns, not one:

    origin             'entry' | 'webhook' | 'import'
    origin_is_derived  TRUE for every row this migration touches

Existing rows take the key's prefix where there is one, and `entry` otherwise
— which is a good guess and is **not a record of what happened**. A row with a
null `webhook_key` could have been a clerk's entry, a transfer leg or a counter
receipt; `entry` is the likeliest and it is still an inference. **A report that
cannot tell an inference from an observation presents one as the other**, and a
reconciliation is precisely the place that matters.

Every row created after this migration carries `origin_is_derived = FALSE`,
written by the same statement that writes `origin`, from the caller that knows.

WHY THE BACKFILL IS SET-BASED AND WHAT IT COSTS
------------------------------------------------
Two UPDATE statements over the whole table, not a row loop:

    UPDATE payments SET origin = 'webhook', origin_is_derived = TRUE
      WHERE webhook_key LIKE 'webhook|%';        -- and 'import|%', 'entry|%'
    UPDATE payments SET origin = 'entry', origin_is_derived = TRUE
      WHERE origin IS NULL;

⚠ **NO SAVEPOINT AND NO `try/except` ANYWHERE IN THIS FILE, AND THAT IS
DELIBERATE (CLAUDE.md hard-won law 14).** That law exists because
`try: … except IntegrityError: continue` passes the whole suite on SQLite and
loses data on PostgreSQL. **The cure it prescribes is a SAVEPOINT around a
statement that is ALLOWED to fail** — and no statement here is. These are
unconditional UPDATEs of a nullable text column with no constraint, no unique
index and no FK, so there is no failure to skip past; adding a nested
`atomic()` would be a guarantee-shaped comment around a thing that cannot
happen (law 1). If one of them raises, the migration must stop.

⚠ **SUPERSEDED 2026-09-22 (`DEF-PAY-6166`) — IT RUNS UNDER RLS AND THEREFORE
TOUCHED NOTHING.** This paragraph read: *"A migration runs with `app.tenant_id`
unset; a statement-level UPDATE is applied by the same policy as everything
else … Reading rows into Python here would be the version that needs a tenant
loop and would silently touch nothing when it did not have one — the reports
zero over a scope it silently excludes shape."* **Every clause of that is true
and the conclusion is exactly inverted.** The statement-level UPDATE is the one
the policy silently empties; the tenant loop is the one that works. It is now a
tenant loop, and it is `RunPython` reading the tenant list — nothing else. See
the amendment section above for the measurement.

⚠ **NO `audit_log` ROW, AND HARD RULE 7 IS WHY RATHER THAN AN EXCEPTION TO
IT.** Rule 7 says every money ACTION writes an audit row. A backfill moves no
money, changes no amount and alters nothing a customer or a clerk did — it
stamps a derived label on history. The audit row that matters already exists on
each of these payments, written when the money was taken. What records THIS
change is the migration itself and `origin_is_derived`, which is a permanent
marker rather than a pruned one (`audit_log` is pruned on a retention schedule
— see hard rule 4's note and `OQ-1340`).

⚠ AMENDED 2026-09-22 — TWO DEFECTS, AND THE SECOND ONE IS WHY THE FIRST WAS
NEVER SEEN HERE (`DEF-PAY-6165`, `DEF-PAY-6166`)
-----------------------------------------------------------------------------
The first version of this file had the two UPDATEs bare and unscoped. It failed
on the Product Owner's live PostgreSQL deploy and blocked the release:

    psycopg.errors.RaiseException: BR-PAY-002 / hard rule 4: payment
    PY-260808-0001 is cleared and is append-only … Changed: origin,
    origin_is_derived
    CONTEXT: PL/pgSQL function payments_payment_immutable() line 53 at RAISE
    Applying payments.0029_cr132_payment_origin…

**DEFECT ONE — THE BACKFILL IS REFUSED BY THE FREEZE, AND `payments/0014`
PROMISED EXACTLY THAT.** Its past-`processing` branch compares
`to_jsonb(OLD) - stamps` with `to_jsonb(NEW) - stamps` — a WHOLE-ROW comparison
— and its own docstring says *"a column added later is frozen the day it is
created."* `origin` was frozen before this migration could write to it. The
freeze was working.

  **THE FIX IS NOT TO WIDEN THE ALLOW LIST.** Adding `origin` to
  `payments/0014`'s `stamps` array would have made the migration pass and left
  the column **permanently amendable on cleared money** — a reconciliation
  label an application bug could rewrite. CLAUDE.md hard rule 4 forbids it in
  terms: *"`payments/0014` is the ONLY place the database's allow list moves;
  widening it anywhere else is a new ruling, not this one."* So the trigger
  comes off for the backfill and goes straight back on, which is what
  `payments/0018_cr059_cs7_refund_account.py` already does for
  `trg_refund_immutable`, and for the same reason: *the schema is adding, not
  an application write path amending a financial fact.* No amount, date,
  status, account or reference moves. It is disabled and re-enabled **inside
  the migration's own transaction**, so no application statement can run while
  it is off, and a failure anywhere between rolls the whole thing back with the
  freeze intact. From the second this migration ends, `origin` is frozen by the
  same whole-row comparison — which is what CR-132 wants anyway, because an
  origin is written once by the caller that knows and is never corrected.

**DEFECT TWO — THE BACKFILL WROTE NOTHING AT ALL WHERE THE MIGRATION ROLE IS
SUBJECT TO RLS, AND SAID `OK`.** This is the worse of the two and it is the
reason nobody here saw defect one. `payments` carries RLS **FORCE** and its
policy is `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`
— unset reads as NULL, which matches no row. A migration runs with no tenant
set, so on any database whose migration role is not `BYPASSRLS` the UPDATE
matched **zero rows of seventy-four**, changed nothing, never reached the
trigger, and printed `Applying payments.0029… OK`.

  **MEASURED, NOT ASSUMED**, on a PostgreSQL 16 clone of the demo database on
  2026-09-22, with the unfixed file: `migrate payments 0029` → **OK**; then, as
  the tenant, `SELECT origin, count(*) FROM payments GROUP BY 1` → **`NULL`,
  74**. The connecting role reports `rolsuper=f rolbypassrls=f` and
  `pg_class.relforcerowsecurity` is `t`. The production role evidently sees the
  rows, which is why production raised and this did not — **the same product,
  two databases, two different outcomes from one migration.**

  ⚠ **AND THIS FILE'S OWN DOCSTRING ASSERTED THE OPPOSITE**, in the section
  below headed *"it runs under RLS and therefore per tenant"*: *"a
  statement-level UPDATE is applied by the same policy as everything else"* —
  true, and the conclusion drawn from it was backwards. CLAUDE.md hard-won law
  1: a comment claiming a guarantee is not the guarantee. That paragraph is
  struck where it stands.

  ⚠ **IT HAS HAPPENED IN THIS REPOSITORY BEFORE, IN THE SAME SHAPE, AND THE
  FIX IS COPIED FROM IT.** `apps/billing/migrations/0029_br_bil_1045_backfill_
  run_status.py` (`DEF-BIL-5382`) selected nothing, updated nothing and printed
  OK over four bill runs, for this exact reason. Its cure is the per-tenant
  pass below: `set_config('app.tenant_id', <id>, true)` — transaction-local,
  with the id bound as a parameter and never interpolated — once per tenant,
  then the UPDATEs. **`tenants` itself carries no RLS**, so the list can be
  read.

**AND THE MIGRATION NOW REFUSES TO REPORT SUCCESS OVER A BACKFILL THAT DID
NOTHING.** `assert_every_row_was_stamped` counts the payments still holding a
NULL origin, per tenant, after the pass, and raises naming the count if any
remain. ⚠ **That check is the whole point of this amendment and not a
flourish:** defect two's entire signature was a truthful `OK` over an untouched
table, and CLAUDE.md hard-won law 7 names it — *a declared blind spot with no
NUMBER attached is indistinguishable from an empty one.* `assert_the_freeze_is_
back` is its twin: it asks `pg_trigger.tgenabled`, because if a later edit
dropped the ENABLE every other check in this file would still be green and
`payments` would be left unfrozen for the life of the database.

WHY THE COLUMN IS NULLABLE WHEN EVERY ROW HAS A VALUE AFTER THIS RUNS
----------------------------------------------------------------------
`NOT NULL` would be a lie one deploy later: the four creation sites are updated
in this same change, but a fifth added by a lane that has not read this file
would fail its INSERT with a constraint error naming a column it has never
heard of. **A NULL origin is a real and readable answer — *nobody told us* —
and `G8`-style honesty is better than a constraint that turns a missing write
into a production outage.** `newworld.py` selects `origin = 'webhook'`
explicitly, so a NULL is excluded from the feed by the filter rather than by a
default anybody could get wrong.
"""

from django.db import migrations, models

#: The three sources, spelled exactly as `apps/payments/idempotency.py` spells
#: them. ⚠ **Written out rather than imported: a migration is a historical
#: record and must go on producing the same schema when that module's
#: vocabulary changes** — which is the whole reason migrations do not import
#: application constants.
ORIGIN_ENTRY = "entry"
ORIGIN_WEBHOOK = "webhook"
ORIGIN_IMPORT = "import"

BACKFILL_FROM_KEY = """
    UPDATE payments
       SET origin = %s,
           origin_is_derived = TRUE
     WHERE origin IS NULL
       AND webhook_key LIKE %s
"""

BACKFILL_REMAINDER = """
    UPDATE payments
       SET origin = %s,
           origin_is_derived = TRUE
     WHERE origin IS NULL
"""


#: The freeze, by name. ⚠ **Spelled out rather than looked up**, for the same
#: reason the three sources above are written out: a migration is a historical
#: record. `payments/0002` line 156 creates it and nothing has renamed it.
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

#: Transaction-local, id bound as a parameter and never interpolated — copied
#: from `billing/0029`'s cure for the identical defect (`DEF-BIL-5382`).
ENTER_TENANT = "SELECT set_config('app.tenant_id', %s, true)"
LEAVE_TENANT = "SELECT set_config('app.tenant_id', '', true)"

STILL_UNSTAMPED = "SELECT count(*) FROM payments WHERE origin IS NULL"


def assert_the_freeze_is_back(cursor):
    """Refuse to finish with `payments` unfrozen.

    ⚠ **CLAUDE.md hard-won law 7, the question *what would make this check pass
    wrongly*.** Everything else here would be green if a future edit dropped
    the ENABLE — the columns written, the values right, the tests unchanged —
    and `payments` would be open to UPDATE for the life of the database.
    Nothing else in this repository reads `pg_trigger`, so this is the only
    place that failure could ever be seen.
    """
    cursor.execute(FREEZE_STATE, [IMMUTABILITY_TRIGGER])
    row = cursor.fetchone()
    if row is None:
        raise RuntimeError(
            f"payments/0029: trigger {IMMUTABILITY_TRIGGER} is missing from "
            "`payments` after the backfill. The freeze CLAUDE.md hard rule 4 "
            "rests on is not there; refusing to finish."
        )
    if row[0] != "O":
        raise RuntimeError(
            f"payments/0029: trigger {IMMUTABILITY_TRIGGER} is in state "
            f"{row[0]!r}, not 'O'. The backfill took the payments freeze off "
            "and did not put it back; refusing to finish with hard rule 4 off."
        )


def assert_every_row_was_stamped(cursor, tenant_ids):
    """Refuse to report success over a backfill that changed nothing.

    ⚠ **THIS IS THE CHECK `DEF-PAY-6166` EXISTS FOR.** The unfixed version of
    this migration matched zero rows of seventy-four and printed `OK` — a
    truthful report over an untouched table. After the pass below, every
    payment in every tenant holds an origin: the remainder statement gives
    `entry` to anything the key could not classify, so a NULL left behind means
    the UPDATE did not see the row, which means the tenant scope is wrong
    again. The count is in the message because a number is the difference
    between a blind spot and an empty one.
    """
    for tenant_id in tenant_ids:
        cursor.execute(ENTER_TENANT, [str(tenant_id)])
        cursor.execute(STILL_UNSTAMPED)
        left = cursor.fetchone()[0]
        if left:
            raise RuntimeError(
                f"payments/0029: {left} payment row(s) in tenant {tenant_id} "
                "still have no origin after the backfill. The pass did not "
                "reach them — almost certainly a tenant-scope or RLS problem "
                "(DEF-PAY-6166). Refusing to record this migration as applied."
            )
    cursor.execute(LEAVE_TENANT)


def derive_origin(apps, schema_editor):
    """Stamp every existing row, in every tenant, and mark all of it derived.

    Two things this does that the first version did not, both in the amendment
    section of the module docstring: it enters **each tenant** so RLS lets the
    UPDATE see the rows, and it takes the **immutability trigger** off for the
    duration and puts it straight back.
    """
    postgres = schema_editor.connection.vendor == "postgresql"
    Tenant = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(Tenant.objects.values_list("id", flat=True))

    with schema_editor.connection.cursor() as cursor:
        if postgres:
            cursor.execute(DISABLE_FREEZE)
        try:
            if postgres and tenant_ids:
                for tenant_id in tenant_ids:
                    cursor.execute(ENTER_TENANT, [str(tenant_id)])
                    _stamp_what_is_visible(cursor)
                cursor.execute(LEAVE_TENANT)
            elif not postgres:
                # SQLite: no RLS, no trigger, one pass over the whole table.
                # ⚠ The asymmetry is the whole of hard-won law 14 — it is why
                # the broken version was green on every machine here.
                _stamp_what_is_visible(cursor)
        finally:
            if postgres:
                cursor.execute(ENABLE_FREEZE)
        if postgres:
            assert_the_freeze_is_back(cursor)
            assert_every_row_was_stamped(cursor, tenant_ids)


def _stamp_what_is_visible(cursor):
    """The four statements, against whatever rows the current scope shows."""
    for source in (ORIGIN_WEBHOOK, ORIGIN_IMPORT, ORIGIN_ENTRY):
        cursor.execute(BACKFILL_FROM_KEY, [source, f"{source}|%"])
    # Everything left has no key to read — see the docstring on why this
    # is a guess and why it is stamped as one.
    cursor.execute(BACKFILL_REMAINDER, [ORIGIN_ENTRY])


def unstamp(apps, schema_editor):
    """The reverse: clear what this migration wrote.

    ⚠ **IT CLEARS ONLY THE DERIVED ROWS.** A row written by the application
    after this migration carries `origin_is_derived = FALSE` and its origin is
    an OBSERVED fact; wiping it on a rollback would destroy a record that the
    forward migration never created. The reverse of a backfill is undoing the
    backfill, not emptying the column.
    """
    postgres = schema_editor.connection.vendor == "postgresql"
    Tenant = apps.get_model("tenancy", "Tenant")
    tenant_ids = list(Tenant.objects.values_list("id", flat=True))
    clear = (
        "UPDATE payments SET origin = NULL, origin_is_derived = FALSE "
        "WHERE origin_is_derived = TRUE"
    )
    with schema_editor.connection.cursor() as cursor:
        if postgres:
            cursor.execute(DISABLE_FREEZE)
        try:
            if postgres:
                for tenant_id in tenant_ids:
                    cursor.execute(ENTER_TENANT, [str(tenant_id)])
                    cursor.execute(clear)
                cursor.execute(LEAVE_TENANT)
            else:
                cursor.execute(clear)
        finally:
            if postgres:
                cursor.execute(ENABLE_FREEZE)
        if postgres:
            assert_the_freeze_is_back(cursor)


class Migration(migrations.Migration):
    # ⚠ `tenancy` is here because `derive_origin` reads the tenant list to
    # scope the backfill (`DEF-PAY-6166`). Without it the historical model
    # registry may not carry `Tenant` when this migration runs.
    dependencies = [
        ("payments", "0028_rls_cr094_counter_receipts"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="origin",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="origin_is_derived",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(derive_origin, unstamp),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["tenant", "origin"], name="ix_payments_origin"),
        ),
    ]

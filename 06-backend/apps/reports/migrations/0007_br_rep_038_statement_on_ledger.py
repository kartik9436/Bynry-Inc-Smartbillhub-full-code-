"""reports 0007 — R24 `statement` moves from `invoices` to `journal_lines`.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-27 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). Migration ordering is a
🔒 sensitive path in CLAUDE.md, so there is a row in
`12-governance/09-human-review-ledger.md` and this does not reach RATIFIED
without a recorded sign-off.

⚠ **THIS IS A MIGRATION AND NOT AN EDIT TO `0003`, AND THE REASON IS THE WHOLE
POINT.** `0003_seed_catalogue.py` line 237 seeded `R24 statement` on the
`invoices` dataset. **That seed has already run on every database.** Editing
the seed file would change what a NEW database gets and leave every existing
one — every beta tenant, every developer's, the demo — reporting a customer
statement out of a dataset that structurally cannot show a payment. A seed that
has run is a fact about the world, not a draft.

WHAT THE PO RULED, VERBATIM (2026-09-27, `BR-REP-038`)
──────────────────────────────────────────────────────
    *"it should be like bank statement. this si correct - Build it on the
    ledger — the account's running record, which holds both sides. Correct by
    construction; more work"*

A statement is an opening balance, every charge and every payment in date
order, and a closing balance. Invoices are CHARGES. The `invoices` dataset
already refused this definition by name and said exactly why: *"serving it here
would show every bill and no payment and still print a closing balance."*

THE WORKED CASE THE PO WAS SHOWN
────────────────────────────────
Dana opens Alia's statement for September: the September bill of **$84.20**,
the payment of **$84.20** on the 14th, and the balance carried forward. On the
invoice reading it shows what she owed and never what she paid.
Asserted in `06-backend/tests/test_br_rep_038_statement.py`.

⚠ **THE BASIS MOVES WITH THE DATASET, AND IT IS A CONSEQUENCE RATHER THAN A
CHOICE.** `0003` seeded R24 at the **EVENT** basis labelled *Statement date*.
Every figure on the ledger reading is struck on `journal_entries.entry_date` —
the BOOK date — and `apps.ledger.reporting.account_ledger` publishes `posting`.
The `journal_lines` dataset already refuses `regulatory_filing` over precisely
this mismatch: *"serving it here would answer a filing with a period the
regulator did not ask about, and BR-REP-001 exists so a money report cannot
state the wrong one."* Leaving the stored basis at `event` would ship a
statement whose stated basis contradicts its own rows. Recorded in
`12-governance/02-decision-log.md`, 2026-09-27, as a consequence of BR-REP-038.

⚠ **`R44 my_bills_and_payments` IS NOT TOUCHED.** It is seeded on `invoices`
too and its name promises both sides in the same way, and **the ruling names
the statement and not R44.** Measured on real PostgreSQL the same day: it
refuses with the invoices dataset's own sentence and **cannot show a payment
today**. That is `DEF-REP-6909`, open, with a one-line question for the PO. A
lane does not pick a dataset for a customer-facing money screen.

⚠ **IT IS REVERSIBLE, AND THE REVERSE IS THE OLD VALUES AND NOT A GUESS.**
`reverse_sql` runs the SAME statement with `BACKWARD` — `invoices` / `event` /
*Statement date*, the exact tuple `0003` seeded — so a rollback returns the row
to the state this migration found it in rather than to a plausible one. Proved
on real PostgreSQL 16: forward, `migrate reports 0006`, forward again; the
dataset and basis move both ways and `register`, `subject` and `subjects`
survive untouched.

⚠ **IT TOUCHES THE PLATFORM ROW ONLY (`tenant_id IS NULL`).** A utility that
has authored its own `statement` definition keeps it, exactly as `0003.unseed`
is careful to. A `filter(key=...)` without the tenant clause would rewrite a
tenant's own work under the name of a platform fix.

╔══════════════════════════════════════════════════════════════════════════╗
║  IT TURNS ROW-LEVEL SECURITY OFF FOR THIS ONE STATEMENT — `DEF-REP-6906`  ║
╚══════════════════════════════════════════════════════════════════════════╝
**MEASURED, NOT ASSUMED.** `0002_rls_force` gives `report_definitions` the
asymmetric policy the brief's §7.7 asks for and a human reviewed:

    USING      (tenant_id = <tenant> OR tenant_id IS NULL)
    WITH CHECK (tenant_id = <tenant>)

*"`tenant_id IS NULL` is readable by every tenant and writable by none."* That
is exactly right for a clerk and it forbids **this migration and `0003` itself**,
because every platform row carries `tenant_id = NULL` and no session can make
`tenant_id = current_setting(...)` true for one. Probed on real PostgreSQL 16
as the `NOSUPERUSER NOBYPASSRLS` application role, twice — with `app.tenant_id`
unset and with it set to the documented `00000000-…-0000` default — and refused
both times:

    ERROR:  new row violates row-level security policy for table "report_definitions"

So the table is taken out of row-level security for the length of one UPDATE and
put straight back, **including `FORCE`**. The table OWNER may do that and the
application role IS the owner; the alternative is granting `BYPASSRLS`, which
`10-scripts/13-provision-database.sh` refuses on a PO ruling and which would
void hard rule 1 for every table at once rather than for one statement.

⚠ **THE WHOLE MIGRATION IS ONE TRANSACTION AND DDL IS TRANSACTIONAL IN
POSTGRESQL**, so a failure anywhere between the two `ALTER`s rolls the policy
back on with it. There is no window in which a crash leaves the table
unprotected. **A reviewer should check the reverse SQL re-enables BOTH `ENABLE`
and `FORCE`** — `ENABLE` alone leaves the owner exempt, and the application role
is the owner, which is the same hole with a quieter name.

⚠ **`0003` HAS THE SAME PROBLEM AND IS NOT FIXED HERE.** A fresh production
`migrate` cannot apply it. That is `DEF-REP-6906`, filed, OPEN, and deliberately
not widened into this task — an already-migrated host is unaffected and fixing a
signed 🔒 RLS path is not something to do inside a different change.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations

KEY = "statement"

#: Where BR-REP-038 puts it, and what `0003` had.
FORWARD = {"dataset": "journal_lines", "basis": "posting", "basis_label": "Posting date"}
BACKWARD = {"dataset": "invoices", "basis": "event", "basis_label": "Statement date"}

#: The one statement, parameterised by the three values above.
#:
#: ⚠ **`jsonb_set` TWICE RATHER THAN A WHOLE-OBJECT WRITE.** `filters` also
#: carries `register`, `subject` and `subjects`, and rewriting the object would
#: drop `P2.14`'s four-grain vocabulary off this definition — a migration that
#: silently deletes a sibling's work inside its own diff.
_UPDATE = """
ALTER TABLE report_definitions DISABLE ROW LEVEL SECURITY;
UPDATE report_definitions
   SET dataset = %(dataset)s,
       filters = jsonb_set(
           jsonb_set(filters::jsonb, '{basis}', to_jsonb(%(basis)s::text)),
           '{basis_label}', to_jsonb(%(basis_label)s::text)
       )
 WHERE tenant_id IS NULL
   AND key = %(key)s;
ALTER TABLE report_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE report_definitions FORCE ROW LEVEL SECURITY;
"""


class PlatformRowUpdate(migrations.RunSQL):
    """`RunSQL` that is a NO-OP on anything but PostgreSQL.

    The suite hardcodes in-memory SQLite (hard-won law 14) and `ALTER TABLE …
    ROW LEVEL SECURITY` is not SQL there. Skipping is honest: SQLite has no
    row-level security to turn off, so there is nothing for this statement to
    protect — the UPDATE half is applied through the ORM instead so the
    definition still moves and the suite still tests the real shape.
    """

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            _move_with_orm(to_state.apps, FORWARD)
            return
        super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != "postgresql":
            _move_with_orm(to_state.apps, BACKWARD)
            return
        super().database_backwards(app_label, schema_editor, from_state, to_state)


def _move_with_orm(apps, values: dict[str, str]) -> None:
    """The same change, for a backend with no row-level security to disable.

    `filters` is read, COPIED and written back — never mutated on the instance
    the ORM handed back, which on some backends is a shared object and is how
    one migration quietly edits another row's dictionary.
    """
    Definition = apps.get_model("reports", "ReportDefinition")
    for row in Definition.objects.filter(tenant_id=None, key=KEY):
        filters = dict(row.filters or {})
        filters["basis"] = values["basis"]
        filters["basis_label"] = values["basis_label"]
        row.dataset = values["dataset"]
        row.filters = filters
        row.save(update_fields=["dataset", "filters"])


class Migration(migrations.Migration):

    dependencies = [
        # ⚠ **THE LEAF WAS CHECKED WITH `MigrationLoader.detect_conflicts()` AND
        # NOT WITH `build_graph()`** — `build_graph()` does NOT raise on a
        # two-leaf conflict, so a lane that checks with it alone writes the
        # second leaf it was trying to avoid. This branch broke exactly that way
        # on 2026-09-27 (`DEF-REP-6877`). `0006` was the single `reports` leaf
        # at authoring time and was re-checked at push.
        ("reports", "0006_p2_20_service_accounts"),
    ]

    operations = [
        PlatformRowUpdate(
            sql=[(_UPDATE, {**FORWARD, "key": KEY})],
            reverse_sql=[(_UPDATE, {**BACKWARD, "key": KEY})],
        ),
    ]

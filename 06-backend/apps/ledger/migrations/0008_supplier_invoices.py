# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-018 (capture a supplier invoice: date · service · supplier
#           FREE TEXT · amount · OPTIONAL volume · GL account · period) ·
#           US-LED-019 (the register — void with reason, NEVER delete)
#           Screens: S73
# Rules:    BR-LED-028 (capture, hold, reconcile, export — and process NOTHING;
#           no vendor master, so `supplier_name` is a text column by RULE) ·
#           BR-LED-029 (what a captured invoice holds) · BR-LED-030 (the volume
#           is OPTIONAL — nothing refuses a cost-only invoice) · BR-LED-033 (a
#           captured volume carries an EXPLICIT unit) · BR-LED-035 (void, never
#           delete; the reason is required and the row stays visible) ·
#           CLAUDE.md rule 1 (RLS FORCE on every tenant table) · rule 2 (money
#           NUMERIC(18,6) + CHAR(3)) · rule 3 (a quantity carries its unit) ·
#           rule 4's reasoning (corrections are new rows) · B2 Addendum r13 #8
#           (storage mechanics 🔒)
# Tests:    06-backend/tests/test_us_led_018_capture.py ·
#           06-backend/tests/test_us_led_019_register.py ·
#           06-backend/tests/test_us_led_020_reconciliation.py
# ───────────────────────────────────────────────────────
"""ledger 0008 — `supplier_invoices`, the CAPTURED payable side.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this migration also
installs an RLS policy and a delete refusal, both 🔒 in their own right).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of
2026-08-09. **A row in 12-governance/09-human-review-ledger.md is OWED**: that
directory is the Product Owner's to write, so the lane report names this file
and the exact row it needs rather than opening one on their behalf.

═══════════════════════════════════════════════════════════════════════════
1 · THE TABLE NAME IS **PROPOSED**, AND THAT IS RECORDED IN SIGNED PROSE
═══════════════════════════════════════════════════════════════════════════
B2 defines **no payable table at all**. The ledger field map's D-11 says it in
as many words — *"The payable table does not exist. Every `supplier_invoices.*`
row above is GAP; the name is PROPOSED"* — and points at the schema route (the
r13 #8 pattern: exact DDL, keys, RLS policy and immutability shape = Eng-Lead
🔒). EP-LED-06 names the table only *"so its rows can be written about"*.

So this migration is authored under the same B2 r13 #8 delegation that produced
`journal_entries.posting_key` and `fiscal_period_closes`, and is REPORTED as an
extension beyond B2 §2's literal DDL rather than presented as signed schema.
The columns transcribe the field map's `supplier_invoices.*` rows one for one,
so the owed addendum has ONE shape to ratify instead of two to reconcile.

═══════════════════════════════════════════════════════════════════════════
2 · WHAT THE CONSTRAINTS ENFORCE, AND WHICH RULE EACH ONE IS
═══════════════════════════════════════════════════════════════════════════
* `ck_supplier_invoices_volume_unit` — **CLAUDE.md rule 3, in the database.**
  A volume with no unit is refused; a unit with no volume is refused; **omitting
  BOTH is legal**, which is BR-LED-030 (PO 2026-08-12, OQ-190 verbatim: *"I
  dont know but we can make a provision and make it optional"*). CI-8's
  $1,845.50 of pipe and CI-9's $12,500.00 of meters go in with no volume and
  nothing complains.
* `ck_supplier_invoices_amount` — an invoice for nothing is not an invoice.
  ⚠ It also refuses a supplier CREDIT NOTE, which has no path today and is
  NAMED rather than assumed (workbook V-12).
* `ck_supplier_invoices_void_reason` — BR-LED-035: a void carries its reason or
  it is not a void. The reason is the only thing a visible voided row is FOR.
* `ck_supplier_invoices_status` — two states, `captured` and `voided`. There is
  no `approved`, no `scheduled` and no `paid`, because BR-LED-028 forbids the
  workflows that would set them. A state machine with an approval state in it is
  an approval queue whether or not anything drives it.

**THERE IS NO IMMUTABILITY TRIGGER ON THIS TABLE, AND THAT IS DELIBERATE.**
Hard rule 4 lists issued invoices, invoice lines, payments and journal entries;
a captured supplier invoice is on none of those lists and is not a document
anybody was sent. BR-LED-034 makes it EDITABLE while its own period is open,
with before/after audit. **RULED 2026-08-16 (OQ-203, PO verbatim: _"Yes it can
be corrected"_): an edit after the period CLOSES is lawful too, with a REASON
and an audit row.** The columns are unchanged by that ruling, which is why this
migration decided nothing about it and still does not: the correction is a
normal UPDATE carrying `after_close_correction` in its audit payload, and the
export screen names the batch it invalidated (`apps/ledger/exports.stale_batches`).

═══════════════════════════════════════════════════════════════════════════
3 · `ledger_supplier_invoice_no_delete()` — BR-LED-035 IN THE DATABASE
═══════════════════════════════════════════════════════════════════════════
US-LED-019 TC-6: *"Hard delete attempted on any captured row (UI, API or bulk)
→ Refused. No path exists at any layer."* The application half is that
`apps/ledger/cost_capture.py` publishes no delete function; this is the other
half, and it is the half that survives a `.delete()` typed into a shell.

`FOR EACH ROW` on purpose: a statement-level trigger would also fire on the
TRUNCATE that Django's test teardown uses, which is how the audit trail's own
append-only guard learned to fight its fixtures (see
`tests/isolation_helpers.py`). A row-level BEFORE DELETE trigger is invisible to
TRUNCATE and total to DELETE, which is exactly the split wanted here.

═══════════════════════════════════════════════════════════════════════════
RLS, AND WHAT IS PROVED RATHER THAN CLAIMED
═══════════════════════════════════════════════════════════════════════════
ENABLE + FORCE + the signed B2 §3 policy, read verbatim from
`db/rls_ledger_supplier_invoices.sql` — never a policy composed in Python.
Postgres only: the developer database is SQLite and has neither RLS nor
triggers, so every assertion depending on them carries `requires_postgres` and
SKIPS there rather than passing vacuously. **Never a bare `pytest.mark.skip`.**
The service-layer half (`apps/ledger/cost_capture.py` filters on `tenant_id`
explicitly and refuses without tenant context) is what protects the developer
database.
"""

from pathlib import Path

from django.db import migrations, models

import django.db.models.deletion  # noqa: F401 — kept for parity with 0001's generated ops

from core.dbfields import uuid7

#: The signed B2 §3 policy text, read from the .sql file rather than composed
#: here — same discipline as ledger/0002 and ledger/0007.
RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_ledger_supplier_invoices.sql"

NEW_TABLES = ("supplier_invoices",)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE
#: would abort the migration, so every placeholder is doubled here and arrives
#: at the server as a single `%`. Same reason as ledger/0002, 0004 and 0007 —
#: and the SQLite test tier cannot see this defect, so it is stated rather than
#: relied on being remembered.
NO_DELETE_SQL = """
CREATE OR REPLACE FUNCTION ledger_supplier_invoice_no_delete() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'BR-LED-035: captured supplier invoice %% cannot be DELETED. Void it with a reason instead — the row stays visible in the register (a register that hides its corrections cannot be reconciled against a supplier statement) and leaves every aggregate from that moment. Corrections are new rows (CLAUDE.md hard rule 4 / IS-1: financial records never delete).',
    COALESCE(OLD.reference, OLD.id::text);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_supplier_invoice_no_delete ON supplier_invoices;
CREATE TRIGGER trg_supplier_invoice_no_delete
  BEFORE DELETE ON supplier_invoices
  FOR EACH ROW EXECUTE FUNCTION ledger_supplier_invoice_no_delete();
"""

DROP_NO_DELETE_SQL = """
DROP TRIGGER IF EXISTS trg_supplier_invoice_no_delete ON supplier_invoices;
DROP FUNCTION IF EXISTS ledger_supplier_invoice_no_delete();
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in NEW_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def _pg_only(sql):
    def run(apps_registry, schema_editor):
        if schema_editor.connection.vendor != "postgresql":
            return
        schema_editor.execute(sql)

    return run


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0007_je_number_close_export"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SupplierInvoice",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid7, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("invoice_date", models.DateField()),
                ("service", models.TextField()),
                ("supplier_name", models.TextField()),
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(max_length=3)),
                (
                    "volume",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("volume_unit", models.TextField(blank=True, null=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("reference", models.TextField(blank=True, null=True)),
                ("memo", models.TextField(blank=True, null=True)),
                ("status", models.TextField(default="captured")),
                ("void_reason", models.TextField(blank=True, null=True)),
                ("voided_by_user_id", models.UUIDField(blank=True, null=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("captured_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "ledger_account",
                    models.ForeignKey(
                        db_column="ledger_account_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="ledger.ledgeraccount",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "supplier_invoices"},
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("captured", "voided"))),
                name="ck_supplier_invoices_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__gt", 0)), name="ck_supplier_invoices_amount"
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(("volume__isnull", True), ("volume_unit__isnull", True))
                | models.Q(("volume__isnull", False), ("volume_unit__isnull", False)),
                name="ck_supplier_invoices_volume_unit",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(("volume__isnull", True)) | models.Q(("volume__gte", 0)),
                name="ck_supplier_invoices_volume_sign",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="ck_supplier_invoices_period",
            ),
        ),
        migrations.AddConstraint(
            model_name="supplierinvoice",
            constraint=models.CheckConstraint(
                condition=~models.Q(status="voided")
                | (models.Q(("void_reason__isnull", False)) & ~models.Q(void_reason="")),
                name="ck_supplier_invoices_void_reason",
            ),
        ),
        migrations.AddIndex(
            model_name="supplierinvoice",
            index=models.Index(
                fields=["tenant", "period_start", "status"], name="ix_supplier_invoices_period"
            ),
        ),
        migrations.AddIndex(
            model_name="supplierinvoice",
            index=models.Index(
                fields=["tenant", "service", "period_start"], name="ix_supplier_invoices_svc"
            ),
        ),
        migrations.AddIndex(
            model_name="supplierinvoice",
            index=models.Index(
                fields=["tenant", "invoice_date"], name="ix_supplier_invoices_date"
            ),
        ),
        # BR-LED-035 in the database — the table must exist before the trigger.
        migrations.RunPython(_pg_only(NO_DELETE_SQL), _pg_only(DROP_NO_DELETE_SQL)),
        # RLS last: the table must exist before a policy can be put on it.
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-018@d744841 (sha1[:7], newline-joined in order; US-LED-019 ships in this migration too — the authorities this migration was written from, in order: 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-028..036 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-06-cost-of-service-capture.md US-LED-018/019 §5 · 04-docs/05-modules/09-ledger/03-field-map.md §"Cost-of-service capture" + D-11/D-12 · 04-docs/05-modules/09-ledger/08-worked-examples.md LE-11/LE-13 · 08-qa/01-e2e/journeys/J25-cost-of-service-month.md)
# generated: 2026-08-15 by the ledger AP-capture lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row OWED and named in the lane report; 12-governance/ is the PO's to write)
# gates: PROVED RED BEFORE GREEN — the delete refusal was driven by deleting a
#         captured row with the trigger absent (it succeeded, leaving the
#         register short a row) and present (`InternalError: BR-LED-035:
#         captured supplier invoice RS-2607-0141 cannot be DELETED`); the
#         volume/unit CHECK was driven by inserting 400000 with a NULL unit
#         before the constraint (accepted) and after it (IntegrityError on
#         ck_supplier_invoices_volume_unit). See
#         tests/test_us_led_018_capture.py and tests/test_us_led_019_register.py
# exceptions: `supplier_invoices` IS AN EXTENSION BEYOND B2 §2 AND ITS NAME IS
#         PROPOSED — the brief defines no payable table and the ledger field map
#         records the gap as D-11, routing it to the schema lane. Authored under
#         B2 r13 #8's *storage mechanics 🔒* delegation and REPORTED here rather
#         than presented as signed schema · NO IMMUTABILITY TRIGGER, on purpose:
#         hard rule 4 does not list this table and BR-LED-034 makes a capture
#         editable while its period is open. The after-close half is OQ-203 and
#         is STUBBED in the service, never decided here · `service` carries NO
#         CHECK constraint: BR-REP-006 makes the vocabulary the tenant's LIVE
#         service list, and a CHECK is inlined at migration time (the trap
#         `ledger/0003` and `ledger/0006` both paid for), so it would freeze a
#         platform catalogue into the database. Validated in `cost_capture.py`
#         against the live list on every write · `ck_supplier_invoices_amount`
#         also refuses a supplier CREDIT NOTE, which has no path today (workbook
#         V-12) — NAMED, not assumed · NO PARTITION: NFR-24's mandatory set
#         names meter_reads, audit_log, invoice_lines and journal_lines, and a
#         table growing at a few rows per supplier per month is not one of them
#         · `reference` is NOT unique — two suppliers may legitimately number
#         their invoices alike, and BR-LED-028 forbids the vendor master that
#         would make the pair unique. REPORTED · the RLS policy SQL lives in
#         06-backend/db/rls_ledger_supplier_invoices.sql and ALSO owes a
#         human-review-ledger row
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

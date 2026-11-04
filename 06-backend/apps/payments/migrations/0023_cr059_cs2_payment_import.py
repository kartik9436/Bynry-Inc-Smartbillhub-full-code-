# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-2 — "Import a lockbox or CSV remittance file". A utility
#           on a bank lockbox gets ONE FILE A DAY carrying hundreds of cheques
#           and types every one by hand today.
# Story:    US-PAY-003 (the staged payment import)   Screens: S35 · S33
# Rules:    BR-PAY-023 (bulk = staged import: batch → per-row validation →
#           preview → commit; file+SHA-256 stamp; idempotency file+tags;
#           account-match heuristics FLAG FOR REVIEW, never auto-guess
#           silently) · BR-PAY-028 🔒 (file+tags key; mechanics Eng-Lead) ·
#           BR-PAY-033 (imports default the posting date FROM FILE DATA) ·
#           CLAUDE.md hard rule 1 (tenant scoping, RLS FORCE) · rule 2 (money) ·
#           rule 4 (financial immutability) · rule 6 (idempotency)
# Tests:    06-backend/tests/test_cr059_cs2_payment_import.py
# ───────────────────────────────────────────────────────
"""payments 0021 — `payment_import_batches` + `payment_import_rows`.

HUMAN-OWNED (migration ordering, and the 🔒 file+tags idempotency key this
schema carries). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO
ruling of 2026-08-09.

════════════════════════════════════════════════════════════════════════════
NOTHING IS APPLIED ON UPLOAD, AND THE SCHEMA IS WHAT MAKES THAT TRUE
════════════════════════════════════════════════════════════════════════════
CS-2's first new rule: *"A remittance import is staged: upload → validate →
preview → commit; nothing is applied on upload"* — the same shape the meter-read
import already uses. These two tables ARE the staging. **No `payments` row
exists until the commit**, so a clerk who uploads January's file in March has
changed no customer's balance and can put it down again.

════════════════════════════════════════════════════════════════════════════
🔒 THE IDEMPOTENCY CONSTRAINT IS SCOPED TO COMMITTED BATCHES, DELIBERATELY
════════════════════════════════════════════════════════════════════════════
`uq_payment_import_batches_idempotency` is UNIQUE (tenant, file_hash,
tag_fingerprint) **WHERE status = 'committed'** — exactly the shape and exactly
the scope `uq_read_import_batches_idempotency` already has, and for OQ-044's own
reason: the closure blocks the COMMIT, not the staging. A clerk may open the
same file three times while working out whether it is the right one; only a
second COMMIT is the double-post, and that is the one the database refuses.

Two guards catching different facts — `DEF-058`'s lesson applied rather than
quoted:

    uq_payment_import_batches_idempotency   this FILE has been committed before
    uq_payments_idempotency  (webhook_key)  this ROW has been recorded before

The second is the one `record_payment` already uses per row, with
`idempotency_source="import"`. So a re-run of a partially committed batch cannot
double-pay a row even if the batch guard were somehow got past.

════════════════════════════════════════════════════════════════════════════
THE FREEZE TRIGGER, AND WHY A STAGING TABLE NEEDS ONE
════════════════════════════════════════════════════════════════════════════
Hard rule 4 protects `payments`. It says nothing about a staging row — and once
a batch is COMMITTED its rows are the only record of **which file created which
payment**. An edit there would rewrite the provenance of money already recorded
while every immutability guarantee on `payments` itself held perfectly.

So the walk is one-way and the database enforces it: `staged → validated →
committed`, with `discarded` reachable from either mutable state. A committed
batch and its rows are frozen. A discarded batch is KEPT rather than deleted — a
clerk putting a file down is an event an auditor may need to see.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

#: RLS in the shape `payments/0002`, `0013` and `0020` already use for this
#: module's tables. FORCE, so the table's own owner is filtered too (hard rule
#: 1) — an import row carries an account id, a payer's name and a money figure,
#: and a cross-tenant read of it is a cross-tenant read of a customer's payment.
RLS = """
ALTER TABLE payment_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_import_batches FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_payment_import_batches ON payment_import_batches;
CREATE POLICY rls_payment_import_batches ON payment_import_batches
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);

ALTER TABLE payment_import_rows ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_import_rows FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_payment_import_rows ON payment_import_rows;
CREATE POLICY rls_payment_import_rows ON payment_import_rows
  USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
"""

DROP_RLS = """
DROP POLICY IF EXISTS rls_payment_import_rows ON payment_import_rows;
ALTER TABLE payment_import_rows NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_import_rows DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rls_payment_import_batches ON payment_import_batches;
ALTER TABLE payment_import_batches NO FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_import_batches DISABLE ROW LEVEL SECURITY;
"""

#: ⚠ **SINGLE `%`, NOT `%%`, AND THE DIFFERENCE IS A MIGRATION THAT WILL NOT
#: APPLY.** These are installed through `schema_editor.connection.cursor()` with
#: NO parameters, so nothing interpolates and a doubled sign survives into
#: plpgsql as an escaped literal — leaving each RAISE with more arguments than
#: it has placeholders:
#:
#:     psycopg.errors.SyntaxError: too many parameters specified for RAISE
#:
#: The `RunSQL` neighbours in this module DO need `%%`, which is exactly how a
#: lane gets this wrong by copying one. It is invisible on the default suite
#: (hard-won law 14): SQLite installs no trigger here at all.
FREEZE = """
CREATE OR REPLACE FUNCTION payments_import_batch_freeze() RETURNS trigger AS $$
BEGIN
  IF OLD.status = 'committed' THEN
    RAISE EXCEPTION
      'payment import batch % is committed and names recorded payments, so it is append-only. Correct the payments, never the file that made them.',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_import_batch_freeze ON payment_import_batches;
CREATE TRIGGER trg_payment_import_batch_freeze
  BEFORE UPDATE OR DELETE ON payment_import_batches
  FOR EACH ROW EXECUTE FUNCTION payments_import_batch_freeze();

CREATE OR REPLACE FUNCTION payments_import_row_freeze() RETURNS trigger AS $$
DECLARE
  batch_status text;
BEGIN
  SELECT status INTO batch_status FROM payment_import_batches WHERE id = OLD.batch_id;
  IF batch_status = 'committed' THEN
    RAISE EXCEPTION
      'payment import row % belongs to a committed batch, so it is append-only. It is the only record of which file created which payment.',
      OLD.id
      USING ERRCODE = 'restrict_violation';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_payment_import_row_freeze ON payment_import_rows;
CREATE TRIGGER trg_payment_import_row_freeze
  BEFORE UPDATE OR DELETE ON payment_import_rows
  FOR EACH ROW EXECUTE FUNCTION payments_import_row_freeze();
"""

DROP_FREEZE = """
DROP TRIGGER IF EXISTS trg_payment_import_row_freeze ON payment_import_rows;
DROP FUNCTION IF EXISTS payments_import_row_freeze();
DROP TRIGGER IF EXISTS trg_payment_import_batch_freeze ON payment_import_batches;
DROP FUNCTION IF EXISTS payments_import_batch_freeze();
"""


def install_guards(apps, schema_editor):
    """RLS and the freeze, on PostgreSQL only.

    ⚠ **SQLite GETS NEITHER, AND THAT IS DELIBERATE RATHER THAN AN OVERSIGHT**
    (hard-won law 14). SQLite has no row-level security and no plpgsql, and a
    weaker approximation of either would make the suite GREEN over a guarantee
    production does not have. The cases that prove these carry
    `@requires_postgres`, and a real cluster is the only place they can run.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(RLS)
        cursor.execute(FREEZE)


def remove_guards(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(DROP_FREEZE)
        cursor.execute(DROP_RLS)


class Migration(migrations.Migration):

    dependencies = [
        ("customers", "0039_def2847_mailing_address_line2_country"),
        ("identity", "0004_rls_security_policies"),
        # ⚠ **THIS FILE WAS `0021` UNTIL IT WAS PUSHED, AND THE RENUMBER IS
        # LAW 11's ID CLAUSE (DEF-1787) DOING ITS JOB.** A sibling lane landed
        # `0021_cr059_cs12_cs27_payment_tenders` and `0022_rls_…` while this was
        # being written, in its own worktree, so neither number was visible from
        # here at the moment this file was generated. Two migrations numbered
        # 0021 in one app is not a merge conflict — it is
        # `django.db.migrations.exceptions.InconsistentMigrationHistory` /
        # "Conflicting migrations detected; multiple leaf nodes in the migration
        # graph", which refuses EVERY test in the process, names neither lane,
        # and reads like a broken tree (DEF-2872 records that exact confusion).
        # A migration number is an allocated id and is re-derived from the
        # pinned tip at push time, exactly like a defect id or a file's bytes.
        ("payments", "0022_rls_cr059_cs12_cs27_tenders"),
        ("tenancy", "0036_def3422_drop_bell_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="PaymentImportBatch",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("source_kind", models.TextField(default="lockbox")),
                ("file_name", models.TextField(blank=True, null=True)),
                ("file_hash", models.TextField(blank=True, null=True)),
                ("tag_fingerprint", models.TextField(blank=True, null=True)),
                ("tags", models.JSONField(blank=True, default=dict)),
                ("uploaded_at", models.DateTimeField(blank=True, null=True)),
                ("counts", models.JSONField(blank=True, default=dict)),
                ("status", models.TextField(default="staged")),
                ("committed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "committed_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="committed_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="committed_payment_import_batches",
                        to="identity.user",
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
                (
                    "uploaded_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="uploaded_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="identity.user",
                    ),
                ),
            ],
            options={
                "db_table": "payment_import_batches",
            },
        ),
        migrations.CreateModel(
            name="PaymentImportRow",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("row_no", models.IntegerField()),
                ("account_ref_raw", models.TextField(blank=True, null=True)),
                ("invoice_ref_raw", models.TextField(blank=True, null=True)),
                ("payer_name_raw", models.TextField(blank=True, null=True)),
                ("amount_raw", models.TextField(blank=True, null=True)),
                ("paid_on_raw", models.TextField(blank=True, null=True)),
                ("reference_raw", models.TextField(blank=True, null=True)),
                (
                    "amount",
                    models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True),
                ),
                ("paid_on", models.DateField(blank=True, null=True)),
                ("reference", models.TextField(blank=True, null=True)),
                ("invoice_id", models.UUIDField(blank=True, null=True)),
                ("match_method", models.TextField(default="none")),
                ("match_state", models.TextField(default="error")),
                ("match_detail", models.TextField(blank=True, null=True)),
                ("payment_id", models.UUIDField(blank=True, null=True)),
                ("commit_error", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "account",
                    models.ForeignKey(
                        blank=True,
                        db_column="account_id",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="payment_import_rows",
                        to="customers.account",
                    ),
                ),
                (
                    "batch",
                    models.ForeignKey(
                        db_column="batch_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="rows",
                        to="payments.paymentimportbatch",
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
            options={
                "db_table": "payment_import_rows",
            },
        ),
        migrations.AddIndex(
            model_name="paymentimportbatch",
            index=models.Index(fields=["tenant", "status"], name="ix_payment_import_batch_status"),
        ),
        migrations.AddConstraint(
            model_name="paymentimportbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("file_hash__isnull", False), ("status", "committed")),
                fields=("tenant", "file_hash", "tag_fingerprint"),
                name="uq_payment_import_batches_idempotency",
            ),
        ),
        migrations.AddIndex(
            model_name="paymentimportrow",
            index=models.Index(fields=["tenant", "batch"], name="ix_payment_import_rows_batch"),
        ),
        migrations.AddIndex(
            model_name="paymentimportrow",
            index=models.Index(
                fields=["tenant", "batch", "match_state"], name="ix_payment_import_rows_state"
            ),
        ),
        migrations.AddConstraint(
            model_name="paymentimportrow",
            constraint=models.UniqueConstraint(
                fields=("batch", "row_no"), name="uq_payment_import_rows"
            ),
        ),
        # ⚠ LAST, AND THE ORDER IS LOAD-BEARING. The tables must exist before a
        # policy or a trigger can name them. `payments/0019` was written the
        # other way round once — a constraint referencing a column added later in
        # the same file — and every test in the process died on
        # `FieldError: Cannot resolve keyword 'is_partial_reversal'`.
        migrations.RunPython(install_guards, remove_guards),
    ]

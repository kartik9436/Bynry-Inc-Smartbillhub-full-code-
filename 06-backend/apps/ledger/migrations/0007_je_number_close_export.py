# ── Trace ──────────────────────────────────────────────
# Story:    US-LED-011 (manual JE draft → post — the `JE-` number stamped AT
#           POST, BR-LED-021) · US-LED-015 (month close — the record of which
#           periods are closed, which no table in the schema held) ·
#           US-LED-016 (the accounting export — B2 r13 #4 `export_batches`)
#           Screens: S56 · S57 · S42
# Rules:    BR-LED-021 (a posted JE carries a `JE-` number, allocated per tenant
#           under BR-TEN-035) · BR-LED-006 / BR-TEN-038 (closed periods lock;
#           late-dated events auto-forward) · BR-LED-018 (WARN + CONFIRM with an
#           audited reason) · BR-LED-004 / BR-LED-017 (one recorded, IDEMPOTENT
#           batch per covered window per target) · CLAUDE.md rule 1 (RLS FORCE
#           on every tenant table) · rule 2 (money NUMERIC(18,6) + CHAR(3)) ·
#           rule 4 (financial immutability) · rule 6 (idempotency) ·
#           B2 Addendum r13 #4 (`export_batches`) + r13 #8 (storage mechanics 🔒)
# Tests:    06-backend/tests/test_us_led_011_manual_je.py ·
#           06-backend/tests/test_us_led_015_month_close.py ·
#           06-backend/tests/test_us_led_016_export.py
# ───────────────────────────────────────────────────────
"""ledger 0007 — the JE number, the period-close record, the export batch.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and two of the three
things here — the idempotency key on `export_batches` and the close state the
posting path consults — are 🔒 in their own right). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-15 under the PO ruling of 2026-08-09. Row in
12-governance/09-human-review-ledger.md; never RATIFIED without a recorded
human sign-off.

═══════════════════════════════════════════════════════════════════════════
1 · `journal_entries.number` — BR-LED-021, AND THE TWO CLAUSES IT DOES NOT SETTLE
═══════════════════════════════════════════════════════════════════════════
PO 2026-08-12, verbatim: *"Approve a JE- series"* (OQ-176). The S56 list showed
`019ff23d-13ee-7aba-a280-58058e492cb9` where LE-8 says **JE-104** and LE-4 says
**JE-201 / JE-202**; a finance officer cannot read a 36-character id aloud,
quote it in an email, or find it again.

The column is NULLABLE and UNIQUE-where-set, and both halves are the ruling:
*"allocated per tenant and stamped when the entry POSTS — a DRAFT has NO
number"*. A plain UNIQUE would have allowed exactly one draft per tenant.

⚠ **TWO CLAUSES OF THE RECORDED RULING SIT AGAINST SIGNED LAW. THIS MIGRATION
IMPLEMENTS THE RULING AS GIVEN AND FLAGS BOTH RATHER THAN CHOOSING.**
  (a) The decision-log row justifies the post-time stamp as *"exactly as a draft
      bill does under BR-BIL-063"* — and BR-BIL-063 says the OPPOSITE: *"A bill
      number is allocated when the DRAFT is created, not at issue"* (PO
      2026-08-11, *"Give a running number always even for Draft"*). What is
      BUILT is what was RULED for journal entries: number at POST. The analogy
      is backwards and the two documents cannot both be right about drafts.
  (b) The row records the series as *"gapless"*, while BR-TEN-035 allocates from
      a per-tenant monotonic counter where *"gaps ok, never reused"*. This
      column is filled by that allocator, so **GAPS HAPPEN** — a rolled-back
      post consumes its number. Stated here so it is not discovered in an audit.

**THE NUMBER IS FROZEN ONCE POSTED.** `ledger_journal_entry_immutable()` is
re-issued below with `number` in its frozen list, for the reason 0004 gave for
`posting_key`: a column the function does not name is a column a posted entry
can still change, and a re-numberable posted entry is BR-TEN-035's *"issued
numbers are never renumbered"* broken from the inside.

═══════════════════════════════════════════════════════════════════════════
2 · `fiscal_period_closes` — THE TABLE THE POSTING SERVICE SAID DID NOT EXIST
═══════════════════════════════════════════════════════════════════════════
`apps/ledger/posting.py`, 2026-08-11: *"there is no record of which periods are
closed — no fiscal period table exists anywhere in the schema. US-LED-015 owns
close."* `tenant_settings.lock_closed_periods` is a BOOLEAN — it says whether
locking is on, never which months are locked.

B2 defines no such table, and the field map delegates it in signed text: *"Close
/ reopen actions + period lock | fiscal period close state (**storage mechanics
🔒**)"*. So the shape is authored under the same B2 r13 #8 delegation that
produced `journal_entries.posting_key`, and is REPORTED as an extension beyond
B2 §2's literal DDL rather than presented as signed schema. See the model
docstring for why the state is one row and the history is `audit_log`.

═══════════════════════════════════════════════════════════════════════════
3 · `export_batches` — B2 r13 #4, WITH DB-12's IDEMPOTENCY KEY IN THE DATABASE
═══════════════════════════════════════════════════════════════════════════
r13 #4 names the table and its facts (*"period, target, idempotency, who/when,
content hash"*) and DB-12 — the consolidated idempotency register — carries it
by name, UNIQUE per period+target. Unlike the journal's posting key, this one is
SIGNED rather than delegated, and `uq_export_batches_period_target` is it.

T5-07 step 3 fixes what the key may NOT contain: a second export of an
already-covered window *"under the OTHER granularity"* is refused too, because
*"idempotency is per covered window, whichever granularity was chosen"*. So
`granularity` is a column and not a key part. The service adds the OVERLAP check
the unique index cannot express (a weekly window inside an already-exported
month); the index is the backstop that survives two workers racing.

The money columns are `NUMERIC(18,6)` (CLAUDE.md rule 2) with a `CHAR(3)`
currency beside them: these are the footing the ERP was told, and LE-5's July
payload balances at **598.69 = 598.69**.

═══════════════════════════════════════════════════════════════════════════
RLS, AND WHAT IS PROVED RATHER THAN CLAIMED
═══════════════════════════════════════════════════════════════════════════
Both new tables get ENABLE + FORCE + the signed B2 §3 policy, read verbatim from
`db/rls_ledger_close_export.sql` — never a policy composed in Python. Postgres
only: the developer database is SQLite and has neither RLS nor triggers, so the
assertions that depend on this carry `requires_postgres` and SKIP there rather
than passing vacuously. The service-layer halves (`apps/ledger/close.py` and
`apps/ledger/exports.py` both filter on `tenant_id` explicitly, and both refuse
without tenant context) are what protect the developer database.
"""

from pathlib import Path

from django.db import migrations, models

import django.db.models.deletion  # noqa: F401 — kept for parity with 0001's generated ops

from core.dbfields import uuid7

#: The signed B2 §3 policy text, read from the .sql file rather than composed
#: here — same discipline as ledger/0002.
RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_ledger_close_export.sql"

NEW_TABLES = ("fiscal_period_closes", "export_batches")

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE
#: would abort the migration, so every placeholder is doubled here and arrives
#: at the server as a single `%`. Same reason as ledger/0002 and ledger/0004 —
#: and the SQLite test tier cannot see this defect, so it is stated rather than
#: relied on being remembered.
#:
#: ledger/0004's function, re-issued with `number` added to the frozen column
#: list. Everything else is byte-identical to 0004 ON PURPOSE — a rewrite that
#: also "tidied" the other clauses would make the diff between two versions of a
#: hard-rule-4 guard unreadable, which is the last place a reviewer should have
#: to squint.
IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION ledger_journal_entry_immutable() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    IF OLD.status = 'posted' THEN
      RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED and cannot be deleted. A correction is a linked reversing entry, never a removal.',
        OLD.id;
    END IF;
    RETURN OLD;         -- a draft has not entered the books
  END IF;

  IF OLD.status = 'draft' THEN
    RETURN NEW;         -- BR-LED-003: drafts edit freely, including draft -> posted
  END IF;

  -- Posted. Exactly ONE column may still move, and only once: the forward
  -- auto-reverse link (BR-LED-005 — see ledger/0002 for the full argument).
  IF OLD.auto_reverse_entry_id IS NOT NULL
     AND NEW.auto_reverse_entry_id IS DISTINCT FROM OLD.auto_reverse_entry_id THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-005: journal entry %% already links to its auto-reversal; the link is written once and never moved',
      OLD.id;
  END IF;

  IF NEW.tenant_id      IS DISTINCT FROM OLD.tenant_id
  OR NEW.entry_date     IS DISTINCT FROM OLD.entry_date
  OR NEW.type           IS DISTINCT FROM OLD.type
  OR NEW.status         IS DISTINCT FROM OLD.status
  OR NEW.source_type    IS DISTINCT FROM OLD.source_type
  OR NEW.source_id      IS DISTINCT FROM OLD.source_id
  OR NEW.posting_key    IS DISTINCT FROM OLD.posting_key
  OR NEW.number         IS DISTINCT FROM OLD.number
  OR NEW.memo           IS DISTINCT FROM OLD.memo
  OR NEW.currency       IS DISTINCT FROM OLD.currency
  OR NEW.reversal_of    IS DISTINCT FROM OLD.reversal_of
  OR NEW.posted_at      IS DISTINCT FROM OLD.posted_at THEN
    RAISE EXCEPTION 'hard rule 4 / BR-LED-003: journal entry %% is POSTED and immutable — only its auto-reversal link may still be written. An "edit" is a reverse + repost (two new entries), never a change to this row. (The posting key and the JE- number are frozen with the rest: clearing the key would re-open the replay this entry already consumed (hard rule 6), and re-numbering a posted entry breaks BR-TEN-035 (issued numbers are never renumbered).)',
      OLD.id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

#: The 0004 text, verbatim, so a reverse of THIS migration restores the guard
#: that existed before it rather than dropping a clause of hard rule 4 on the
#: way back.
IMMUTABILITY_SQL_WITHOUT_NUMBER = IMMUTABILITY_SQL.replace(
    "  OR NEW.number         IS DISTINCT FROM OLD.number\n", ""
)


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
        ("ledger", "0006_budget_variance_designation"),
        ("tenancy", "0001_initial"),
    ]

    operations = [
        # ── 1 · the JE- number (BR-LED-021) ─────────────────────────────────
        migrations.AddField(
            model_name="journalentry",
            name="number",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="journalentry",
            constraint=models.UniqueConstraint(
                condition=models.Q(("number__isnull", False)),
                fields=("tenant", "number"),
                name="uq_journal_entries_number",
            ),
        ),
        # The column must exist before the trigger that freezes it.
        migrations.RunPython(
            _pg_only(IMMUTABILITY_SQL),
            _pg_only(IMMUTABILITY_SQL_WITHOUT_NUMBER),
        ),
        # ── 2 · the period-close record (US-LED-015) ────────────────────────
        migrations.CreateModel(
            name="FiscalPeriodClose",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid7, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("status", models.TextField(default="closed")),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("closed_by_user_id", models.UUIDField(blank=True, null=True)),
                ("close_reason", models.TextField(blank=True, null=True)),
                ("incomplete_items", models.JSONField(blank=True, default=list)),
                ("reopened_at", models.DateTimeField(blank=True, null=True)),
                ("reopened_by_user_id", models.UUIDField(blank=True, null=True)),
                ("reopen_reason", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "fiscal_period_closes"},
        ),
        migrations.AddConstraint(
            model_name="fiscalperiodclose",
            constraint=models.UniqueConstraint(
                fields=("tenant", "period_start", "period_end"),
                name="uq_fiscal_period_closes_period",
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalperiodclose",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("open", "closed"))),
                name="ck_fiscal_period_closes_status",
            ),
        ),
        migrations.AddConstraint(
            model_name="fiscalperiodclose",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="ck_fiscal_period_closes_window",
            ),
        ),
        migrations.AddIndex(
            model_name="fiscalperiodclose",
            index=models.Index(
                fields=["tenant", "status"], name="ix_fiscal_period_closes_state"
            ),
        ),
        # ── 3 · the recorded export batch (B2 r13 #4) ───────────────────────
        migrations.CreateModel(
            name="ExportBatch",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid7, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("batch_no", models.TextField(blank=True, null=True)),
                ("period_start", models.DateField()),
                ("period_end", models.DateField()),
                ("target", models.TextField()),
                ("granularity", models.TextField(default="summary")),
                ("content_hash", models.TextField()),
                ("row_count", models.IntegerField(default=0)),
                ("total_debits", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("total_credits", models.DecimalField(decimal_places=6, default=0, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("payload", models.JSONField(blank=True, default=list)),
                ("created_by_user_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={"db_table": "export_batches"},
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.UniqueConstraint(
                fields=("tenant", "period_start", "period_end", "target"),
                name="uq_export_batches_period_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.CheckConstraint(
                condition=models.Q(("target__in", ("qbo", "xero", "csv", "iif"))),
                name="ck_export_batches_target",
            ),
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.CheckConstraint(
                condition=models.Q(("granularity__in", ("summary", "weekly"))),
                name="ck_export_batches_granularity",
            ),
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.CheckConstraint(
                condition=models.Q(("period_end__gte", models.F("period_start"))),
                name="ck_export_batches_window",
            ),
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(("batch_no__isnull", False)),
                fields=("tenant", "batch_no"),
                name="uq_export_batches_no",
            ),
        ),
        migrations.AddIndex(
            model_name="exportbatch",
            index=models.Index(fields=["tenant", "created_at"], name="ix_export_batches_sent"),
        ),
        migrations.AddIndex(
            model_name="exportbatch",
            index=models.Index(
                fields=["tenant", "target", "period_start"], name="ix_export_batches_win"
            ),
        ),
        # RLS last: the tables must exist before a policy can be put on them.
        migrations.RunPython(apply_rls, drop_rls),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-LED-011@d744841 (sha1[:7], newline-joined in order; US-LED-015 and US-LED-016 ship in this migration too — the authorities this migration was written from, in order: 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-004/006/017/018/021 · 04-docs/05-modules/09-ledger/06-epics/EP-LED-04-manual-je.md US-LED-011 · EP-LED-05-remittance-close-export.md US-LED-015/016 · 04-docs/02-decisions/02-database-design-brief.md §2 + §3 + Addendum r13 #4 and #8 + DB-12 · 08-qa/01-e2e/journeys/J19-month-end-close.md and T5-07/T5-08/T5-09)
# generated: 2026-08-15 by the ledger close-the-books lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, ledger row owed)
# gates: PROVED RED BEFORE GREEN — see the three test modules named in the Trace
#         header. The immutability clause was proved by re-numbering a POSTED
#         entry before this migration (it succeeded) and after it (it raises);
#         the export idempotency key was proved by exporting July twice with the
#         unique constraint absent from the model (two batches) and present (one).
# exceptions: `fiscal_period_closes` IS AN EXTENSION BEYOND B2 §2 — the brief
#         defines no fiscal-period table at all and the ledger field map
#         delegates its *"storage mechanics 🔒"*. Authored under B2 r13 #8, the
#         same delegation that produced `journal_entries.posting_key`, and
#         REPORTED here rather than presented as signed schema · `export_batches`
#         IS signed (r13 #4 + DB-12) but three of its columns are not: `payload`,
#         `granularity` and the two money totals. `granularity` is BR-LED-017's
#         per-export choice; `payload` is what makes J19 step 7's *"the file
#         re-generated from the batch is identical"* true without re-deriving it
#         from books that have moved on; the totals are the footing the ERP was
#         told · NO PARTITION for either table: NFR-24's mandatory set names
#         meter_reads, audit_log, invoice_lines and journal_lines, and neither of
#         these grows with transaction volume (one row per period; one row per
#         period per target) · the `number` column is added to the frozen list of
#         `ledger_journal_entry_immutable()` and NOT to `ledger_sole_writer_guard`
#         — 0004 gates INSERT and a number is written during the draft → posted
#         UPDATE, which the trigger's `OLD.status = 'draft'` branch already
#         admits · BR-LED-021's *"gapless"* clause is NOT implemented and cannot
#         be while BR-TEN-035 allocates from a monotonic counter (*"gaps ok,
#         never reused"*); both are flagged in the docstring, neither is chosen
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

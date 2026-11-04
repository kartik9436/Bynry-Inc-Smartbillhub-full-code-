# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-009 (NSF — the reversing row and the entry it must unwind) ·
#           US-PAY-011 (refunds — the `refunds` table, its RLS and its freeze)
#           Screens: S33 · S35 · S58
# Rules:    BR-PAY-002 (a reversal is a NEW row; nothing edits the original) ·
#           BR-PAY-013 (NSF) · BR-PAY-014 (refunds only from a real credit;
#           immutable row) · BR-PAY-037 (initiate and approve are two recorded
#           acts) · CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · rule 4
#           (financial immutability — a void is a status move plus a reversing
#           posting, never a delete) · rule 6 (idempotency) · NFR-10 (isolation
#           — release blocker)
# ───────────────────────────────────────────────────────
"""payments 0006 — `refunds`, its isolation and its freeze, plus ONE new door.

HUMAN-OWNED (RLS policies, migration ordering and financial immutability are
all CLAUDE.md 🔒 paths). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the
PO ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md. Applies
the SIGNED B2 §3 policy template from `06-backend/db/rls_payments_refunds.sql`
verbatim and invents no new policy shape.

╔══════════════════════════════════════════════════════════════════════════╗
║  READ THIS FIRST: THREE OF THIS LANE'S COLUMNS ARE IN SOMEBODY ELSE'S    ║
║  MIGRATION, AND THAT IS A REPORTED DEFECT (DEF-068), NOT A DESIGN.       ║
╚══════════════════════════════════════════════════════════════════════════╝
`payments.reverses_payment_id`, `payments.reversal_reason` and
`payments.journal_entry_id` — with `uq_payments_reverses` and
`ck_payments_reversal_reason` — belong to US-PAY-009 and were declared on
`apps/payments/models.Payment` by this lane. They are applied by
**0004_w5_deposit_batches_bank_rec**, which is the bank-rec lane's file.

Two lanes were editing `apps/payments/models.py` in the same working tree at the
same time; the bank-rec lane ran `makemigrations` while this lane's model edits
were on disk and unmigrated, and Django did exactly what it is supposed to do —
it wrote the whole detected delta into the migration it was generating. The
SCHEMA is correct and the ORDERING is correct. What is wrong is that a file
whose subject is deposit batches carries three columns nobody reading it would
expect, and its Trace header cites neither US-PAY-009 nor BR-PAY-013.

**It was deliberately NOT edited back out.** 0004 may already be applied to the
other lane's database, and moving an `AddField` out of an applied migration into
a later one makes that database unmigratable — a second, worse defect, on a
🔒 path, to tidy the first. Recorded as DEF-068 with the ordering rule the next
lane needs: `makemigrations` is not a read-only command in a shared tree.

────────────────────────────────────────────────────────────────────────────
WHAT THIS MIGRATION DOES, IN ORDER
────────────────────────────────────────────────────────────────────────────
1. **`refunds`** — B2 §2's table, as redlined by r12 #5 (approval columns) and
   r2 (status/method/reference). Its two widenings from signed text — the
   `requested`/`approved` statuses and the `currency` column — are argued in
   `models.Refund`'s docstring and recorded in the decision log.
2. **RLS FORCE on `refunds`**, from the signed B2 §3 template, verbatim.
3. **The `refunds` freeze**, DENY-BY-DEFAULT — the shape 0002 argued for and
   for the same reason: a freeze that enumerates the columns it protects fails
   OPEN the day a migration adds one. `refunds` is not a DB-4 append-only table
   (B2's list is invoices/lines, payments, journal entries, credit notes,
   opening buckets, template versions), which is what makes r2's status
   TRANSITIONS lawful — so the allow list is the transition columns and nothing
   else. **DELETE is refused in every status**: a lost cheque is VOIDED with a
   reversing posting (US-PAY-011 TC-4), never removed.
4. **ONE new door in the `payments` freeze: `journal_entry_id`, WRITE-ONCE.**

────────────────────────────────────────────────────────────────────────────
THE DOOR, AND WHY IT IS THE NARROWEST ONE THAT WORKS
────────────────────────────────────────────────────────────────────────────
0002's docstring shut the `deposit_batch_id` door on purpose and left the
instruction for whoever needed to open one: *"The lane that builds batches opens
it, narrows it to write-once (the shape `ledger/0002` uses for
`auto_reverse_entry_id`), and proves it RED first."* This is that, for a
different column.

**Why it has to open at all.** `apps/ledger/posting.reverse_entry` is the mirror
this product must use rather than hand-composing a compensating entry, and it
takes an **entry id**. The ledger publishes no read that turns a posting key or
a `(source_type, source_id)` pair back into one — `_existing_entry` is private
to `posting.py` and `apps/ledger/selectors.py` serves accounts only. So a bounce
three weeks after the payment has no way to name the entry it must unwind. The
alternatives were each worse: importing the ledger's ORM violates B1 and G6 rule
4; a payments-owned table mirroring `journal_entries` duplicates the ledger; and
refusing the bounce until the ledger publishes a read leaves BR-PAY-013 built
and wired to nothing, which is hard-won law 2.

**Why the write cannot happen at INSERT.** The journal entry references the
payment as its `source_id`, so the payment row must exist first. The stamp
therefore happens microseconds later, inside the same transaction — and the
payment is already `cleared`, which 0002 freezes absolutely.

**Why WRITE-ONCE and not simply mutable.** NULL → set, once. It may never be
re-pointed or cleared, because re-pointing would silently detach a payment from
the entry that actually holds its money, and the whole reason the column exists
is to be the one true answer to "which entry does this bounce unwind?". Exactly
the argument `ledger/0002` makes for `auto_reverse_entry_id`, exactly its shape.

Everything else stays frozen, including the two reversal columns added by 0004:
a reversing row states its `reverses_payment_id` and its `reversal_reason` at
INSERT and never afterwards.

PROVED RED BEFORE GREEN on a live Postgres cluster — see the trailer.

Postgres only. The default test database is SQLite, which has neither RLS nor
triggers, so every one of these laws is ALSO asserted at the service layer and
each database-dependent case carries `requires_postgres` and SKIPS there rather
than passing vacuously.
"""

from pathlib import Path

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models

RLS_SQL = Path(__file__).resolve().parents[3] / "db" / "rls_payments_refunds.sql"

REFUND_TABLES = ("refunds",)

#: NOTE ON `%%`: `schema_editor.execute(sql)` passes `params=()` down to psycopg,
#: which then treats the string as a format template. A lone `%` in a RAISE would
#: abort the migration, so every placeholder is doubled here and arrives at the
#: server as a single `%`. Same reason as 0002, billing/0002 and ledger/0002.
IMMUTABILITY_SQL = """
-- ── refunds: frozen except the r2 status walk (BR-PAY-014, hard rule 4) ─────
CREATE OR REPLACE FUNCTION payments_refund_immutable() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a refund may move after it is written. Everything absent
  -- from this list is frozen, INCLUDING every column added after today: the
  -- amount, the currency, the payment it draws on, the method and the cheque
  -- number are facts from the moment the row exists.
  --
  -- `void_journal_entry_id` and `journal_entry_id` are here because the entry
  -- ids arrive microseconds after their transitions, in the same transaction,
  -- for the reason the module docstring gives; both are ALSO write-once, below.
  mutable text[] := ARRAY[
    'status',
    'approved_by_id', 'approved_at',
    'issued_at', 'cleared_at',
    'voided_at', 'void_reason',
    'journal_entry_id', 'void_journal_entry_id',
    'updated_at'
  ];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% cannot be removed, in any status. A refund cheque that was lost in the post is VOIDED — a status move plus a reversing posting that restores the credit (US-PAY-011 TC-4) — and the row stands as evidence that the money once left.',
      OLD.id::text;
  END IF;

  -- A voided refund is finished. Nothing moves after it, or the restored credit
  -- could be drawn down twice off one row.
  IF OLD.status = 'void' THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% is VOID and is closed. Its credit has been restored by a reversing entry; paying it again is a NEW refund request, never a revived row.',
      OLD.id::text;
  END IF;

  -- Write-once on both entry links: NULL -> set, and never re-pointed. A
  -- re-pointed link would silently detach a refund from the entry that actually
  -- holds its money.
  IF OLD.journal_entry_id IS NOT NULL
     AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
    RAISE EXCEPTION 'hard rule 4: refund %% already names the journal entry it posted; the link is written once and never moved.',
      OLD.id::text;
  END IF;
  IF OLD.void_journal_entry_id IS NOT NULL
     AND NEW.void_journal_entry_id IS DISTINCT FROM OLD.void_journal_entry_id THEN
    RAISE EXCEPTION 'hard rule 4: refund %% already names its voiding entry; the link is written once and never moved.',
      OLD.id::text;
  END IF;

  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% is frozen except its status walk (requested -> approved -> issued -> cleared, or -> void). The amount, currency, payment, method, cheque number, reason and the requesting act are fixed from the moment the row exists. Changed: %%',
      OLD.id::text,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_refund_immutable ON refunds;
CREATE TRIGGER trg_refund_immutable
  BEFORE UPDATE OR DELETE ON refunds
  FOR EACH ROW EXECUTE FUNCTION payments_refund_immutable();

-- ── payments: 0005's freeze, plus ONE more write-once stamp ─────────────────
-- Everything below is **0005's** function (NOT 0002's) VERBATIM, except that
-- `journal_entry_id` joins `deposit_batch_id` in the write-once stamp list and
-- gains its own re-point guard. It is restated in full rather than patched
-- because plpgsql has no partial replacement: `CREATE OR REPLACE` writes the
-- whole body, so the whole body has to be here and the diff against 0005 is the
-- review.
--
-- Building on 0005 rather than on 0002 is load-bearing. 0005 opened
-- `deposit_batch_id` WRITE-ONCE for BR-PAY-025 batch membership, and a body
-- copied from 0002 would have closed that door again silently — the bank-rec
-- lane's tests would have gone red for a reason nothing in this file mentions.
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a still-processing payment may move (payments/0002).
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  -- The columns a payment that is already financial history may GAIN, each
  -- exactly once: the deposit batch it was banked in (BR-PAY-025, opened by
  -- 0005) and the journal entry it posted (US-PAY-009, opened here).
  stamps   text[] := ARRAY['deposit_batch_id', 'journal_entry_id', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  IF OLD.status <> 'processing' THEN
    -- Append-only, with TWO doors, each write-once. Everything else is compared
    -- as a whole row, so a column added later is frozen the day it is created.
    frozen_old := to_jsonb(OLD) - stamps;
    frozen_new := to_jsonb(NEW) - stamps;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once. A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.status,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF OLD.deposit_batch_id IS NOT NULL
       AND NEW.deposit_batch_id IS DISTINCT FROM OLD.deposit_batch_id THEN
      RAISE EXCEPTION 'BR-PAY-025 / BR-PAY-004: payment %% is already in deposit batch %% and batch membership is WRITE-ONCE. A batch total is the sum of its members, so moving a payment between batches would rewrite two signed-off day totals at once; there is no regroup path.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
    END IF;
    -- 0006: the ledger stamp. The entry names the payment as its source and so
    -- cannot exist before it; the stamp lands microseconds later in the SAME
    -- transaction, on a row that is already `cleared`. NULL -> set only. Without
    -- it a bounce cannot name the entry `posting.reverse_entry` must unwind
    -- (US-PAY-009), and the ledger publishes no key -> entry read.
    IF OLD.journal_entry_id IS NOT NULL
       AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
      RAISE EXCEPTION 'hard rule 4 / US-PAY-009: payment %% already names journal entry %% and the link is WRITE-ONCE. Re-pointing it would detach the payment from the entry that holds its money, which is the one question the column exists to answer; a correction to the books is a reversing entry, never a new pointer.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.journal_entry_id;
    END IF;
    RETURN NEW;
  END IF;

  -- Still processing: the money has not arrived and nothing has been posted.
  -- The row may take the clearing transition and NOTHING else — a payment whose
  -- money has not arrived is in nobody's drawer and has reached no journal, so
  -- neither stamp is open here.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021). The amount, currency, account, purpose, number, posting date, deposit batch, journal entry, reversal link, reversal reason and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: The reverse is **0005's** function restored EXACTLY — not a drop, and not
#: 0002's. Dropping it would leave `payments` unfrozen after an unapply, and
#: restoring 0002's would close the batch door 0005 opened, so a
#: `migrate payments 0005` would break the bank-rec lane rather than return the
#: database to the state 0005 created. A freeze must fail closed AND unapply to
#: exactly what came before it (hard-won law 3).
DROP_IMMUTABILITY_SQL = """
DROP TRIGGER IF EXISTS trg_refund_immutable ON refunds;
DROP FUNCTION IF EXISTS payments_refund_immutable();

CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  mutable      text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  batch_stamp  text[] := ARRAY['deposit_batch_id', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  IF OLD.status <> 'processing' THEN
    frozen_old := to_jsonb(OLD) - batch_stamp;
    frozen_new := to_jsonb(NEW) - batch_stamp;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in, once (BR-PAY-025). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.status,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF OLD.deposit_batch_id IS NOT NULL
       AND NEW.deposit_batch_id IS DISTINCT FROM OLD.deposit_batch_id THEN
      RAISE EXCEPTION 'BR-PAY-025 / BR-PAY-004: payment %% is already in deposit batch %% and batch membership is WRITE-ONCE. A batch total is the sum of its members, so moving a payment between batches would rewrite two signed-off day totals at once; there is no regroup path.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
    END IF;
    RETURN NEW;
  END IF;

  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021). The amount, currency, account, purpose, number, posting date, deposit batch and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def apply_rls(apps_registry, schema_editor):
    """Apply the signed B2 §3 template, read from the .sql file verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RLS_SQL.read_text(encoding="utf-8"))


def drop_rls(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    for table in REFUND_TABLES:
        schema_editor.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
        schema_editor.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY;")
        schema_editor.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY;")


def apply_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(IMMUTABILITY_SQL)


def drop_immutability(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_IMMUTABILITY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0005_rls_w5_bankrec_and_lock"),
        ("tenancy", "0008_rls_custom_field"),
    ]

    operations = [
        migrations.CreateModel(
            name="Refund",
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
                ("amount", models.DecimalField(decimal_places=6, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("status", models.TextField(default="requested")),
                ("method", models.TextField(blank=True, null=True)),
                ("reference", models.TextField(blank=True, null=True)),
                ("reason", models.TextField(blank=True, null=True)),
                ("memo", models.TextField(blank=True, null=True)),
                ("requested_by_id", models.UUIDField(blank=True, null=True)),
                ("requested_at", models.DateTimeField(blank=True, null=True)),
                ("approved_by_id", models.UUIDField(blank=True, null=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("issued_at", models.DateTimeField(blank=True, null=True)),
                ("cleared_at", models.DateTimeField(blank=True, null=True)),
                ("voided_at", models.DateTimeField(blank=True, null=True)),
                ("void_reason", models.TextField(blank=True, null=True)),
                ("idempotency_key", models.TextField(blank=True, null=True)),
                ("journal_entry_id", models.UUIDField(blank=True, null=True)),
                ("void_journal_entry_id", models.UUIDField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "payment",
                    models.ForeignKey(
                        db_column="payment_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="refunds",
                        to="payments.payment",
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
                "db_table": "refunds",
                "indexes": [
                    models.Index(fields=["tenant", "payment"], name="ix_refunds_payment"),
                    models.Index(
                        fields=["tenant", "status", "-created_at"], name="ix_refunds_status"
                    ),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("status__in", ("requested", "approved", "issued", "cleared", "void"))
                        ),
                        name="ck_refunds_status",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("method__in", ("check", "ach")),
                            ("method__isnull", True),
                            _connector="OR",
                        ),
                        name="ck_refunds_method",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)), name="ck_refunds_amount_positive"
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("idempotency_key__isnull", False)),
                        fields=("tenant", "idempotency_key"),
                        name="uq_refunds_idempotency_key",
                    ),
                ],
            },
        ),
        migrations.RunPython(apply_rls, drop_rls),
        migrations.RunPython(apply_immutability, drop_immutability),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-009@f4d2b18 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments/refunds DDL + §3 RLS/immutability template + Addenda r2/r12/r14 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · makemigrations --check clean · migrate applied against a LIVE Postgres cluster · PROVED RED BEFORE GREEN, each quoted in the lane report: (1) with trg_refund_immutable dropped, an issued refund's AMOUNT can be updated and the row deleted; with it, both raise · (2) with the write-once clause removed from payments_payment_immutable, a cleared payment's journal_entry_id can be RE-POINTED at a second entry; with it, the second UPDATE raises · (3) with the refunds RLS policy dropped, a cross-tenant read returns the other tenant's refund cheques
# exceptions: (1) THREE PAYMENTS COLUMNS OF THIS LANE ARE APPLIED BY 0004, the
#         bank-rec lane's migration, because two lanes shared a working tree and
#         `makemigrations` swept an unmigrated model delta that was not its own.
#         Schema and ordering are correct; ownership and traceability are not.
#         DEF-068, reported. NOT edited back out: 0004 may already be applied
#         elsewhere and moving an AddField out of an applied migration makes that
#         database unmigratable — a worse defect, on a 🔒 path, to tidy the first
#         (2) THE `payments` FREEZE GAINS ONE WRITE-ONCE DOOR
#         (`journal_entry_id`), the shape 0002's docstring names for exactly this
#         case. It opens because `posting.reverse_entry` takes an ENTRY ID and
#         the ledger publishes no key -> entry read; the alternatives were a B1
#         violation, a table duplicating the ledger, or BR-PAY-013 wired to
#         nothing. `deposit_batch_id` stays SHUT — that door is still the batch
#         lane's to open
#         (3) `payments_payment_immutable` IS RESTATED IN FULL. plpgsql has no
#         partial replacement; the diff against 0002 is the review, and the
#         reverse restores 0002's function rather than dropping it, so an unapply
#         cannot leave `payments` unfrozen
#         (4) `refunds` IS NOT A DB-4 APPEND-ONLY TABLE and is not frozen as one.
#         B2's DB-4 list does not include it, which is what makes r2's status
#         walk lawful; the freeze is deny-by-default with the transition columns
#         allowed, and DELETE is refused in every status
#         (5) Postgres only: the test database is SQLite and has no triggers, so
#         the same laws are asserted at the service layer too — a guard that
#         skips silently on the developer's own database is not a guard
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

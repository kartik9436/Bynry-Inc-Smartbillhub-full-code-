# ── Trace ──────────────────────────────────────────────
# Change:   CR-186-BRC10 — every payment POSTED at entry, CLEARED at bank
#           reconciliation; one deposit batch per till or per provider per day,
#           all tenders together.
# Rulings:  12-governance/02-decision-log.md, 2026-10-21 ×7 — "INVOICE CLOUD
#           REAL-TIME BALANCE …", "THE PAYMENT LIFECYCLE, STATED BY THE PO FOR
#           EVERY METHOD", "NO 'RECONCILED' PAYMENT STATUS", "DEPOSIT BATCHES:
#           ONE BATCH ID PER TILL OR PER PROVIDER, PER DAY", "EXISTING `cleared`
#           PAYMENTS ARE LEFT AS THEY ARE"
# Rules:    CLAUDE.md hard rule 4 (NARROWED a second time, by the 2026-10-21
#           ruling, for exactly one transition — see below) · hard rule 1 (RLS
#           on both tables is unchanged) · BR-PAY-021 / BR-PAY-025 (both
#           SUPERSEDED-IN-PART 2026-10-21) · hard-won law 14 (every trigger
#           here is proved on PostgreSQL; SQLite has none)
# Tests:    06-backend/tests/test_cr186_paycore.py ·
#           06-backend/tests/test_cr186_paycore_pg.py
# ───────────────────────────────────────────────────────
"""payments 0051 — posted → cleared, and one batch per till or channel per day.

HUMAN-OWNED (migration ordering and hard rule 4's trigger are CLAUDE.md 🔒
paths). HUMAN-REVIEW-PENDING — AI-authored 2026-10-21 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
`12-governance/09-human-review-ledger.md` (CR-186-BRC10), stating what was put
to the PO: Dana's 14 Oct batch, cash $300.00 + cheques $500.00 = **$800.00**,
reconciled → every payment in it moves `posted` → `cleared` with the bank's date.

WHAT CHANGES
------------
1. **`payments_payment_immutable()` gains ONE door: a `posted` payment may move
   to `cleared` (with its clearing date, written once) or to `cancelled`, and
   nothing else about it may change.** PO 2026-10-21, verbatim: *"first they will
   pot the payment - so we crete the record and add posting date; then later
   money is recieved in the bank account ; uitlity will reconcile it bank
   statement that time it is cleared with clearing date"* and *"if payment is
   cancled then it will not be considered; reconciled ayment cannot be
   cancelled; cleared payment cannot be cancled"*. The statuses are ruled as
   *"`posted` → `cleared`, plus `cancelled` (only from `posted`)"*.

   ⚠ **`payments/0014` IS NO LONGER THE ONLY PLACE THE ALLOW LIST MOVES, AND
   THAT IS A NEW RULING RATHER THAN A CONVENIENCE.** CLAUDE.md hard rule 4 says
   *"widening it anywhere else is a new ruling, not this one"* — this is that
   new ruling. The `mutable` and `stamps` arrays are BYTE-IDENTICAL to 0014's;
   the new door is a third array, `clearing`, consulted ONLY when
   `OLD.status = 'posted'`, and `G131` now knows its ceiling (status,
   cleared_at, updated_at) and fails a fourth name. What stays exactly as
   frozen: every other column, `cleared` → anything (so `cleared` → `posted` is
   refused), `cancelled` → anything, a second clearing date, a clearing date
   without the clearing, and DELETE in every status.

2. **`counter_sessions.channel`** — a system till is one per (day, channel), so
   Invoice Cloud, Paymentus and the lockbox file each bank under their own.
   `uq_counter_sessions_system_day` narrows to the channel-less tills already
   opened (they keep their meaning; nothing is rewritten) and
   `uq_counter_sessions_system_day_channel` keys the new ones.

3. **`deposit_batches.method` becomes NULLABLE — NULL means all tenders** — and
   `uq_deposit_batches_session_all_tenders` makes it ONE batch per till or
   channel-day. `uq_deposit_batches_session_method` stays for the batches banked
   before today, each of which keeps its single tender.

4. **`trg_deposit_batch_needs_session` stays and its sentence is corrected** —
   *"a batch is one till and one tender"* stopped being true today. A new batch
   still needs a till or a channel's system till; no batch joins the
   session-less legacy population.

NO DATA MIGRATION. PO 2026-10-21, verbatim: *"b - we did not receive any payment
right now - it is all testing and sandbox only"*. Existing payments, batches and
system tills keep every value they hold; the indexes added are partial over
rows that cannot yet exist, and the narrowed one is narrower than what it
replaces, so neither can fail to apply over live rows.

ROLLBACK
--------
Reverse restores `payments/0033`'s function bodies verbatim, the two original
indexes, and `method` NOT NULL. ⚠ It FAILS once any all-tenders batch exists
(a NULL method) or two channel tills share a day — deliberately: a constraint
that silently stopped describing its rows is worse than a refused rollback.
"""

from importlib import import_module

from django.db import migrations, models

_P0033 = import_module("apps.payments.migrations.0033_cr135_p0_6_deposit_batch_rekey")

#: `%%` because `schema_editor.execute` percent-formats; the deployed text has single percents.
BATCH_NEEDS_A_SESSION_SQL = """
CREATE OR REPLACE FUNCTION payments_deposit_batch_needs_session() RETURNS trigger AS $$
BEGIN
  IF NEW.session_id IS NULL THEN
    RAISE EXCEPTION 'BR-PAY-025 (as amended 2026-10-21, CR-186-BRC10): deposit batch %% cannot be created without a counter till or a channel''s system till. A batch is one till, or one provider or channel, for one day, with every tender in it (PO ruling 2026-10-21, "this is correct"). The batches banked before 2026-09-22 have no session and keep none; nothing may join that population.',
      COALESCE(NEW.code, NEW.id::text);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

PAYMENT_IMMUTABLE_POSTED_THEN_CLEARED_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- ⚠ **`confirmation`, `memo` AND `method_id` APPEAR IN BOTH LISTS BELOW, AND
  -- THAT REPETITION IS DELIBERATE.** CR-059 CS-34, OQ-1322 CLOSED 2026-09-02
  -- (PO: "(a) Allow those fields to change"). Byte-identical to payments/0014.
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  stamps   text[] := ARRAY['deposit_batch_id', 'journal_entry_id', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  -- CR-186-BRC10, PO ruling 2026-10-21: a POSTED payment may take the clearing
  -- (bank reconciliation) or a cancel, and nothing else. Consulted ONLY in the
  -- posted branch below; G131 holds its ceiling at these three names.
  clearing text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a posted payment is a status move with a reversing row, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  -- The tender is part of what a deposit batch totals (BR-PAY-025 as amended
  -- 2026-10-21: one batch per till or channel-day with a total PER TENDER), so
  -- once the payment is banked the tender cannot be corrected.
  IF TG_OP = 'UPDATE'
     AND OLD.deposit_batch_id IS NOT NULL
     AND NEW.method_id IS DISTINCT FROM OLD.method_id THEN
    RAISE EXCEPTION 'BR-PAY-025 / CS-34: payment %% is already in deposit batch %% and a batch carries a total per tender, so the tender cannot be corrected while it is banked — the correction would rewrite a signed-off tender total. A reconciled batch must be unreconciled first (BR-PAY-004). The cheque number and the memo are correctable either way.',
      COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
  END IF;

  IF OLD.status <> 'processing' THEN
    IF OLD.status = 'posted' THEN
      -- CR-186-BRC10 · the ONE new door. posted -> cleared (bank reconciliation)
      -- or posted -> cancelled; nothing else.
      IF NEW.status IS DISTINCT FROM OLD.status
         AND NEW.status NOT IN ('cleared', 'cancelled') THEN
        RAISE EXCEPTION 'hard rule 4 / CR-186-BRC10: payment %% is posted and may move only to cleared (when its deposit batch is reconciled with the bank) or to cancelled. Asked for %%.',
          COALESCE(OLD.payment_no, OLD.id::text), NEW.status;
      END IF;
      IF NEW.cleared_at IS DISTINCT FROM OLD.cleared_at THEN
        IF OLD.cleared_at IS NOT NULL THEN
          RAISE EXCEPTION 'hard rule 4 / CR-186-BRC10: payment %% already carries clearing date %% and the clearing date is WRITE-ONCE.',
            COALESCE(OLD.payment_no, OLD.id::text), OLD.cleared_at;
        END IF;
        IF NEW.status <> 'cleared' THEN
          RAISE EXCEPTION 'hard rule 4 / CR-186-BRC10: payment %% may gain a clearing date only as it moves to cleared.',
            COALESCE(OLD.payment_no, OLD.id::text);
        END IF;
      END IF;
      IF NEW.status = 'cleared' AND NEW.cleared_at IS NULL THEN
        RAISE EXCEPTION 'hard rule 4 / CR-186-BRC10: payment %% cannot clear without its clearing date (the bank date of the reconciliation).',
          COALESCE(OLD.payment_no, OLD.id::text);
      END IF;
      frozen_old := (to_jsonb(OLD) - stamps) - clearing;
      frozen_new := (to_jsonb(NEW) - stamps) - clearing;
    ELSE
      -- Append-only, with two write-once doors and three CORRECTABLE columns.
      frozen_old := to_jsonb(OLD) - stamps;
      frozen_new := to_jsonb(NEW) - stamps;
    END IF;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once, the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34, PO ruling 2026-09-02), and — for a posted payment only — the move to cleared or cancelled (CR-186-BRC10, PO ruling 2026-10-21). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.status,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF OLD.deposit_batch_id IS NOT NULL
       AND NEW.deposit_batch_id IS DISTINCT FROM OLD.deposit_batch_id THEN
      RAISE EXCEPTION 'BR-PAY-025 / BR-PAY-004: payment %% is already in deposit batch %% and batch membership is WRITE-ONCE. A batch total is the sum of its members, so moving a payment between batches would rewrite two signed-off totals at once; there is no regroup path.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
    END IF;
    IF OLD.journal_entry_id IS NOT NULL
       AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
      RAISE EXCEPTION 'hard rule 4 / US-PAY-009: payment %% already names journal entry %% and the link is WRITE-ONCE. Re-pointing it would detach the payment from the entry that holds its money; a correction to the books is a reversing entry, never a new pointer.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.journal_entry_id;
    END IF;
    RETURN NEW;
  END IF;

  -- Still processing (a row written before 2026-10-21; new payments are never
  -- processing). The row may take the clearing transition and the three
  -- corrections, and NOTHING else.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change, plus the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34). Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def forwards(apps_registry, schema_editor):
    """PostgreSQL only — SQLite has no triggers (hard-won law 14)."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(BATCH_NEEDS_A_SESSION_SQL)
    schema_editor.execute(PAYMENT_IMMUTABLE_POSTED_THEN_CLEARED_SQL)


def backwards(apps_registry, schema_editor):
    """Back to `payments/0033`'s two bodies, verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_P0033.BATCH_NEEDS_A_SESSION_SQL)
    schema_editor.execute(_P0033.PAYMENT_IMMUTABLE_NAMES_THE_TILL_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0050_def_pay_10140_counter_code_stored"),
    ]

    operations = [
        migrations.AddField(
            model_name="countersession",
            name="channel",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="countersession",
            name="uq_counter_sessions_system_day",
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.UniqueConstraint(
                condition=models.Q(system_day__isnull=False, channel__isnull=True),
                fields=("tenant", "system_day"),
                name="uq_counter_sessions_system_day",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.UniqueConstraint(
                condition=models.Q(system_day__isnull=False, channel__isnull=False),
                fields=("tenant", "system_day", "channel"),
                name="uq_counter_sessions_system_day_channel",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(channel__isnull=True) | models.Q(system_day__isnull=False),
                name="ck_counter_sessions_channel_is_system",
            ),
        ),
        migrations.AlterField(
            model_name="depositbatch",
            name="method",
            field=models.ForeignKey(
                blank=True,
                db_column="method_id",
                null=True,
                on_delete=models.deletion.PROTECT,
                to="tenancy.paymentmethod",
            ),
        ),
        migrations.AddConstraint(
            model_name="depositbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(session__isnull=False, method__isnull=True),
                fields=("tenant", "session"),
                name="uq_deposit_batches_session_all_tenders",
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]

# ── Trace ──────────────────────────────────────────────
# Change:   CR-186-BRC10 follow-up — Unreconcile puts a batch's cleared
#           payments back to posted.
# Rulings:  12-governance/02-decision-log.md, 2026-10-21 — "TWO CR-186
#           FOLLOW-UP RULINGS" (1): PO chose "Allow, back to Posted".
# Rules:    CLAUDE.md hard rule 4 (NARROWED a third time, for exactly one
#           transition) · BR-PAY-004 · hard-won law 14 (proved on PostgreSQL)
# Tests:    06-backend/tests/test_cr186_unreconcile_unclears_pg.py ·
#           06-backend/tests/test_cr186_unreconcile_unclears.py
# ───────────────────────────────────────────────────────
"""payments 0052 — Unreconcile puts cleared payments back to posted.

HUMAN-OWNED (hard rule 4's trigger is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING
— AI-authored 2026-10-21; row in `12-governance/09-human-review-ledger.md`
(CR-186-BRC10 follow-up), stating what was put to the PO: the 14 Oct batch of
**$800.00** reconciled 16 Oct, then undone → its three payments go back to
Posted with no clearing date; reconciled again 17 Oct → Cleared, 17 Oct.

WHAT CHANGES
------------
`payments_payment_immutable()` gains ONE door: a `cleared` payment may move to
`posted`, with `cleared_at` back to NULL, and nothing else about it may change —
and only while `app.payment_unclearing` (transaction-local, `set_config(…,
true)`) names the payment's own deposit batch. `reconciliation.unreconcile_batch`
is the one caller that opens it. Everything else in `payments/0051`'s body is
byte-identical: `posted` → `cleared`/`cancelled`, `cancelled` frozen, DELETE
refused in every status, batch and journal links write-once.

ROLLBACK
--------
Reverse restores `payments/0051`'s body verbatim. Rows already moved back stay
`posted`, which 0051 accepts.
"""

from importlib import import_module

from django.db import migrations

_P0051 = import_module("apps.payments.migrations.0051_cr186_posted_then_cleared_batch_per_owner")

#: The transaction-local window the Unreconcile service opens (its value is the batch id).
UNCLEARING_GUC = "app.payment_unclearing"

PAYMENT_IMMUTABLE_UNRECONCILE_UNCLEARS_SQL = """
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
  -- CR-186-BRC10 follow-up, PO ruling 2026-10-21 ("Allow, back to Posted"):
  -- Unreconcile puts a CLEARED member of ITS OWN batch back to posted, clearing
  -- the clearing date. Consulted ONLY in the cleared branch below, and only
  -- while the Unreconcile service holds the transaction-local window naming
  -- this payment's batch. G131 holds its ceiling at these three names.
  unclearing text[] := ARRAY['status', 'cleared_at', 'updated_at'];
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
    ELSIF OLD.status = 'cleared'
          AND NEW.status = 'posted'
          AND OLD.deposit_batch_id IS NOT NULL
          AND COALESCE(current_setting('app.payment_unclearing', true), '') = OLD.deposit_batch_id::text THEN
      -- CR-186-BRC10 follow-up · the ONE door out of cleared: back to posted,
      -- through Unreconcile of this payment's own batch, the clearing date
      -- removed with it. Nothing else may change.
      IF NEW.cleared_at IS NOT NULL THEN
        RAISE EXCEPTION 'hard rule 4 / CR-186-BRC10: payment %% returns to posted only without a clearing date (Unreconcile, PO ruling 2026-10-21).',
          COALESCE(OLD.payment_no, OLD.id::text);
      END IF;
      frozen_old := (to_jsonb(OLD) - stamps) - unclearing;
      frozen_new := (to_jsonb(NEW) - stamps) - unclearing;
    ELSE
      -- Append-only, with two write-once doors and three CORRECTABLE columns.
      frozen_old := to_jsonb(OLD) - stamps;
      frozen_new := to_jsonb(NEW) - stamps;
    END IF;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once, the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34, PO ruling 2026-09-02), for a posted payment only, the move to cleared or cancelled, and for a cleared payment only, the move back to posted by Unreconcile of its own batch (CR-186-BRC10, PO rulings 2026-10-21). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
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
    schema_editor.execute(PAYMENT_IMMUTABLE_UNRECONCILE_UNCLEARS_SQL)


def backwards(apps_registry, schema_editor):
    """Back to `payments/0051`'s body, verbatim."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(_P0051.PAYMENT_IMMUTABLE_POSTED_THEN_CLEARED_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0051_cr186_posted_then_cleared_batch_per_owner"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]

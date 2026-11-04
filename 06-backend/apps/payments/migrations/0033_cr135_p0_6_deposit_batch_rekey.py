# ── Trace ──────────────────────────────────────────────
# Change:  CR-135-BRC07 — the payments blueprint's phase 0, task `P0.6`
#          ("Re-key the deposit batch"), `05-prototype/06 Payments Page
#          Blueprint.pdf` p012, read as an IMAGE per B14 rule 42. The drawing
#          is on the DEFAULT branch `claude/confirm-understanding-3ktufc`.
# Story:   no story — phase 0 ships no screen. The Counter screens that open
#          and close a till are phase 2.
# Rules:   CLAUDE.md hard rule 1 (RLS — `counter_sessions` has it from
#          `payments/0032`, `deposit_batches` from `payments/0005`) · hard rule
#          4 (financial immutability — this file RESTATES the payment trigger
#          and does NOT widen its allow list) · hard rule 5 (only the ledger
#          posting service writes journal lines — untouched here) · hard rule 6
#          (the batch cut is idempotent) · BR-PAY-025 (SUPERSEDED-IN-PART
#          2026-09-22) · BR-PAY-004 (a reconciled batch is LOCKED — untouched)
#          · BR-TEN-035 (the number series) · BR-SHL-025 (the guard is at the
#          database, not in a service)
# Tests:   06-backend/tests/test_cr135_p06_deposit_batch_rekey.py ·
#          06-backend/tests/test_cr135_p06_rekey_pg.py (PostgreSQL: the partial
#          index, the session guard and the trigger messages)
# Impacts: apps/payments/bankrec_models.DepositBatch (`session`) ·
#          apps/payments/counter_session_models.CounterSession (nullable owner
#          and centre, `system_day`, the `system` close kind) ·
#          apps/payments/reconciliation.cut_deposit_batches (groups by session
#          × tender and ALLOCATES its code) · core/numbering (the seeded
#          `deposit_batch` default) · LANE P0-DB's `P0.16`, which proves this
#          migration reverses
# ───────────────────────────────────────────────────────
"""payments 0033 — `P0.6`: a deposit batch is one TILL and one TENDER. HUMAN-OWNED.

HUMAN-REVIEW-PENDING — AI-authored 2026-09-22 under the PO ruling of
2026-08-09. Migration ordering and ledger posting are CLAUDE.md 🔒 sensitive
paths, so there is a row in `12-governance/09-human-review-ledger.md` stating
in plain English, with the `$1,240 / $880 / $2,120` figure, what would be put
to the Product Owner.

WHAT CHANGES, IN ONE SENTENCE
------------------------------
A deposit batch stops being *one day × one tender for the whole utility* and
becomes *one counter session × one tender* — so two clerks who each took
cheques on 22 September bank two batches instead of colliding in one.

THE FOUR PO RULINGS THIS BUILDS, ALL OF 2026-09-22
---------------------------------------------------
  1. *"(a) Payments and ledger together"* — one piece of work across two
     modules, each writing its own tables. **The ledger needed NO change** and
     this migration makes none: a deposit's journal entry is keyed on the
     BATCH (`deposit_batch|<id>|reconciled`), never on the day or the tender,
     so two deposits for one day already post and already balance. Proved on
     PostgreSQL by `10-scripts/p06_ledger_two_deposits_readback.py`: Dana
     **1,240.00** debits = credits, Sam **880.00** = **880.00**, the day
     **2,120.00**, no rows left behind.
  2. *"d) Tell them apart by what they lack — Nothing at all. A batch with no
     session is one banked the old way"* — **nothing is written to an existing
     batch.** The replacement key is PARTIAL (`WHERE session_id IS NOT NULL`)
     and every batch already banked keeps its code.
  3. *"we have to make process uniform for all hence we should geneate system
     generated till"* — so the guard is ONE SENTENCE with no tender-by-tender
     exception, and the money that never passed through anybody's hands banks
     under a till that is openly nobody's.
  4. *"(b) Put it in Settings today — DEP-260922-0001 — Settings → Numbering,
     like every other number"* — the banking path ALLOCATES from the
     `deposit_batch` series it already has. That lives in the service, not
     here, and is why this file adds no code column of its own.

⚠ WHY THE GUARD IS A TRIGGER AND NOT `NOT NULL`
------------------------------------------------
Ruling 2 forbids touching the rows already banked, and those rows have no
session. A `NOT NULL` is validated against **every existing row**, so it would
refuse to apply at all on any live tenant — and forcing it through would mean
inventing a session for money nobody took at a counter, which is exactly the
option the PO rejected. A `BEFORE INSERT` trigger asks the question only of
rows being born, which is precisely what the ruling describes: the legacy
population is closed, and no new row may join it.

**It is at the database and not in the service on purpose** — `BR-SHL-025`,
and `payments/0014`'s own reasoning: *a Python check is not a guarantee
against a repair script with a cursor.*

⚠ WHAT THE DRAWING ASKS FOR THAT IS NOT HERE, AND WHY
------------------------------------------------------
`P0.6` says *"⚠ A data migration, not just DDL — existing batches ARE day ×
method."* **There is no data migration, and that is the PO's own ruling (2)
rather than an omission.** The drawing was written before the question was put
to them; four options were offered and the two that WROTE to the old rows were
both impossible, because `BR-PAY-004` locks a reconciled batch and
`payments/0005`'s trigger refuses the UPDATE by name. The absence is the fact.

⚠ AND THE DRAWN HAZARD IS NOT THE REAL ONE
-------------------------------------------
`P0.6`'s outcome warns that *"a dropped unique key with no replacement lets two
batches collide silently"*. Measured on a live PostgreSQL 16 with the drawing's
change and nothing else: Dana's **$1,240** cheque batch banked and Sam's
**$880** batch **died**, loudly, on `uq_deposit_batches_code` — a SECOND unique
key the task row never mentions, over a code composed from the day and the
tender alone. So the collision was never silent; the second clerk of the day
simply could not bank at all. Ruling 4 dissolves it rather than solving it: the
code comes from the series and carries no tender.

WHAT THIS FILE DOES NOT TOUCH
------------------------------
  * **Hard rule 4's allow list.** `payments_payment_immutable` is re-emitted
    here with **one sentence corrected** — *"grouped by day AND tender"* became
    *"grouped by TILL and tender"*, because the refusal's stated REASON was
    about to become false. `mutable` and `stamps` are byte-identical to
    `payments/0014`'s. CLAUDE.md is explicit that `payments/0014` is the only
    place that list moves, and it has not moved.
  * **`counter_sessions.counted_totals`, `difference`, `note` or the
    one-open-till-per-person index.** They are LANE P0-DB's and are unchanged.
  * **Any journal line.** Hard rule 5 is enforced in the database by
    `ledger_sole_writer_guard()` and this migration writes nothing there.
"""

import django.db.models.deletion
from django.db import migrations, models

import apps.payments.models

#: `%%` throughout because `RunSQL`/`execute` percent-formats; the deployed
#: text carries single percents.
BATCH_NEEDS_A_SESSION_SQL = """
CREATE OR REPLACE FUNCTION payments_deposit_batch_needs_session() RETURNS trigger AS $$
BEGIN
  IF NEW.session_id IS NULL THEN
    RAISE EXCEPTION 'BR-PAY-025 (as amended 2026-09-22) / P0.6: deposit batch %% cannot be created without a counter session. A batch is one till and one tender. Money that passed through nobody''s hands — ACH, card, wire, a lockbox file — banks under that day''s SYSTEM till, which carries no owner, no service centre and no float (PO ruling 2026-09-22, "we have to make process uniform for all hence we should geneate system generated till"). The batches banked BEFORE this change have no session and keep none: a batch with no session is one banked the old way, and nothing may join that population.',
      COALESCE(NEW.code, NEW.id::text);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_deposit_batch_needs_session ON deposit_batches;
CREATE TRIGGER trg_deposit_batch_needs_session
  BEFORE INSERT ON deposit_batches
  FOR EACH ROW EXECUTE FUNCTION payments_deposit_batch_needs_session();
"""

DROP_BATCH_NEEDS_A_SESSION_SQL = """
DROP TRIGGER IF EXISTS trg_deposit_batch_needs_session ON deposit_batches;
DROP FUNCTION IF EXISTS payments_deposit_batch_needs_session();
"""

#: `payments/0005`'s batch lock, with its identity sentence naming the till.
#: `session_id` needed no entry in `open_columns`: a column absent from that
#: array is frozen from birth, which is how it arrived already immutable.
BATCH_LOCK_NAMES_THE_TILL_SQL = """
CREATE OR REPLACE FUNCTION payments_deposit_batch_lock() RETURNS trigger AS $$
DECLARE
  -- Columns a batch may move BEFORE it is reconciled. Its identity (tenant,
  -- code, method, day and — since `P0.6`, 2026-09-22 — the counter session it
  -- was banked from) is absent on purpose and is therefore frozen from birth.
  -- A column added later is frozen the day it is created, which is how
  -- `session_id` arrived already immutable without this array moving.
  open_columns  text[] := ARRAY['recorded_total', 'bank_total', 'status', 'updated_at'];
  -- Columns a RECONCILED batch may move: the status, back to 'unmatched', and
  -- nothing else. That single transition IS Unreconcile (BR-PAY-004).
  locked_columns text[] := ARRAY['status', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-004 / hard rule 4: deposit batch %% cannot be removed. A batch is the record of what physically went to the bank on a day; corrections are new events on its trail, never a deletion.',
      OLD.code;
  END IF;

  IF OLD.status = 'reconciled' THEN
    frozen_old := to_jsonb(OLD) - locked_columns;
    frozen_new := to_jsonb(NEW) - locked_columns;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is RECONCILED and LOCKED — its totals and membership are immutable. Unreconcile is the only way back (audited, Owner/Finance), and it is a state reversal, not a rewrite. Changed: %%',
        OLD.code,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF NEW.status <> 'unmatched' AND NEW.status <> OLD.status THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is reconciled; the only status it may take is ''unmatched'' (Unreconcile, which returns it for rework). Asked for %%.',
        OLD.code, NEW.status;
    END IF;
    RETURN NEW;
  END IF;

  frozen_old := to_jsonb(OLD) - open_columns;
  frozen_new := to_jsonb(NEW) - open_columns;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-025 (as amended 2026-09-22): deposit batch %% is identified by its tenant, TILL, day, method and code — none of them may change. A batch cut on the wrong day is not edited into the right one. Changed: %%',
      OLD.code,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: Back to `payments/0005`'s wording, verbatim.
RESTORE_0005_BATCH_LOCK_SQL = """
CREATE OR REPLACE FUNCTION payments_deposit_batch_lock() RETURNS trigger AS $$
DECLARE
  -- Columns a batch may move BEFORE it is reconciled. Its identity (tenant,
  -- code, method, day) is absent on purpose and is therefore frozen from birth.
  open_columns  text[] := ARRAY['recorded_total', 'bank_total', 'status', 'updated_at'];
  -- Columns a RECONCILED batch may move: the status, back to 'unmatched', and
  -- nothing else. That single transition IS Unreconcile (BR-PAY-004).
  locked_columns text[] := ARRAY['status', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-004 / hard rule 4: deposit batch %% cannot be removed. A batch is the record of what physically went to the bank on a day; corrections are new events on its trail, never a deletion.',
      OLD.code;
  END IF;

  IF OLD.status = 'reconciled' THEN
    frozen_old := to_jsonb(OLD) - locked_columns;
    frozen_new := to_jsonb(NEW) - locked_columns;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is RECONCILED and LOCKED — its totals and membership are immutable. Unreconcile is the only way back (audited, Owner/Finance), and it is a state reversal, not a rewrite. Changed: %%',
        OLD.code,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    IF NEW.status <> 'unmatched' AND NEW.status <> OLD.status THEN
      RAISE EXCEPTION 'BR-PAY-004: deposit batch %% is reconciled; the only status it may take is ''unmatched'' (Unreconcile, which returns it for rework). Asked for %%.',
        OLD.code, NEW.status;
    END IF;
    RETURN NEW;
  END IF;

  frozen_old := to_jsonb(OLD) - open_columns;
  frozen_new := to_jsonb(NEW) - open_columns;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-025: deposit batch %% is identified by its tenant, day, method and code — none of them may change. A batch cut on the wrong day is not edited into the right one. Changed: %%',
      OLD.code,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: `payments/0014`'s payment trigger, with ONE sentence corrected. The
#: `mutable` and `stamps` arrays are byte-identical — hard rule 4's allow list
#: does not move here.
PAYMENT_IMMUTABLE_NAMES_THE_TILL_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- ⚠ **`confirmation`, `memo` AND `method_id` APPEAR IN BOTH LISTS BELOW, AND
  -- THAT REPETITION IS DELIBERATE.** CR-059 CS-34, OQ-1322 CLOSED 2026-09-02
  -- (PO: "(a) Allow those fields to change"). The cheque number, the clerk's
  -- memo and the tender: none of them is money, and a wrong reference is an
  -- unmatched bank line and a reconciliation nobody can finish. The ruling says
  -- IN EVERY STATUS, so they are spelled out in both arrays rather than folded
  -- into a third variable — a reader checking whether the rule really covers
  -- both branches reads the branch, not a name defined thirty lines up.
  --
  -- The ONLY columns a still-processing payment may move (payments/0002),
  -- plus the three correctable ones.
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  -- The columns a payment that is already financial history may GAIN, each
  -- exactly once: the deposit batch it was banked in (BR-PAY-025, opened by
  -- 0005) and the journal entry it posted (US-PAY-009, opened by 0006) — plus
  -- the three correctable ones, which are NOT write-once and say so below.
  stamps   text[] := ARRAY['deposit_batch_id', 'journal_entry_id', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  -- The tender decides which deposit batch a payment belongs to (BR-PAY-025
  -- as amended 2026-09-22: batches group by TILL and tender — `P0.6` re-keyed
  -- the day out and the session in; the TENDER half is untouched and so is
  -- this refusal), so once the payment is banked, changing
  -- it would move the payment between two batches — one of which may be
  -- reconciled and locked. CS-34 rules this out in prose and
  -- `amendments.refuse_tender_change_once_batched` refuses it with the batch
  -- NAMED; this is the same rule at the database, for whoever bypassed the
  -- service. It is checked in every status because a batched payment is past
  -- `processing` by construction and a future path must not be able to sweep a
  -- processing one.
  IF TG_OP = 'UPDATE'
     AND OLD.deposit_batch_id IS NOT NULL
     AND NEW.method_id IS DISTINCT FROM OLD.method_id THEN
    RAISE EXCEPTION 'BR-PAY-025 / CS-34: payment %% is already in deposit batch %% and deposits are grouped by TILL and tender, so the tender cannot be corrected while it is banked — the correction would move this payment into a different batch and rewrite two signed-off totals. Take it out of the batch first; a reconciled batch must be unreconciled first (BR-PAY-004). The cheque number and the memo are correctable either way.',
      COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
  END IF;

  IF OLD.status <> 'processing' THEN
    -- Append-only, with two write-once doors and three CORRECTABLE columns.
    -- Everything else is compared as a whole row, so a column added later is
    -- frozen the day it is created.
    frozen_old := to_jsonb(OLD) - stamps;
    frozen_new := to_jsonb(NEW) - stamps;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once, and the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34, PO ruling 2026-09-02). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
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
    IF OLD.journal_entry_id IS NOT NULL
       AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
      RAISE EXCEPTION 'hard rule 4 / US-PAY-009: payment %% already names journal entry %% and the link is WRITE-ONCE. Re-pointing it would detach the payment from the entry that holds its money, which is the one question the column exists to answer; a correction to the books is a reversing entry, never a new pointer.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.journal_entry_id;
    END IF;
    RETURN NEW;
  END IF;

  -- Still processing: the money has not arrived and nothing has been posted.
  -- The row may take the clearing transition and the three corrections, and
  -- NOTHING else — a payment whose money has not arrived is in nobody's drawer
  -- and has reached no journal, so neither stamp is open here.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021), plus the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34). The amount, currency, account, purpose, number, posting date, deposit batch, journal entry, reversal link, reversal reason and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: Back to `payments/0014`'s wording, verbatim.
RESTORE_0014_PAYMENT_IMMUTABLE_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  -- ⚠ **`confirmation`, `memo` AND `method_id` APPEAR IN BOTH LISTS BELOW, AND
  -- THAT REPETITION IS DELIBERATE.** CR-059 CS-34, OQ-1322 CLOSED 2026-09-02
  -- (PO: "(a) Allow those fields to change"). The cheque number, the clerk's
  -- memo and the tender: none of them is money, and a wrong reference is an
  -- unmatched bank line and a reconciliation nobody can finish. The ruling says
  -- IN EVERY STATUS, so they are spelled out in both arrays rather than folded
  -- into a third variable — a reader checking whether the rule really covers
  -- both branches reads the branch, not a name defined thirty lines up.
  --
  -- The ONLY columns a still-processing payment may move (payments/0002),
  -- plus the three correctable ones.
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  -- The columns a payment that is already financial history may GAIN, each
  -- exactly once: the deposit batch it was banked in (BR-PAY-025, opened by
  -- 0005) and the journal entry it posted (US-PAY-009, opened by 0006) — plus
  -- the three correctable ones, which are NOT write-once and say so below.
  stamps   text[] := ARRAY['deposit_batch_id', 'journal_entry_id', 'updated_at',
                           'confirmation', 'memo', 'method_id'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  -- The tender decides which deposit batch a payment belongs to (BR-PAY-025:
  -- batches group by day AND tender), so once the payment is banked, changing
  -- it would move the payment between two batches — one of which may be
  -- reconciled and locked. CS-34 rules this out in prose and
  -- `amendments.refuse_tender_change_once_batched` refuses it with the batch
  -- NAMED; this is the same rule at the database, for whoever bypassed the
  -- service. It is checked in every status because a batched payment is past
  -- `processing` by construction and a future path must not be able to sweep a
  -- processing one.
  IF TG_OP = 'UPDATE'
     AND OLD.deposit_batch_id IS NOT NULL
     AND NEW.method_id IS DISTINCT FROM OLD.method_id THEN
    RAISE EXCEPTION 'BR-PAY-025 / CS-34: payment %% is already in deposit batch %% and deposits are grouped by day AND tender, so the tender cannot be corrected while it is banked — the correction would move this payment into a different batch and rewrite two day totals. Take it out of the batch first; a reconciled batch must be unreconciled first (BR-PAY-004). The cheque number and the memo are correctable either way.',
      COALESCE(OLD.payment_no, OLD.id::text), OLD.deposit_batch_id;
  END IF;

  IF OLD.status <> 'processing' THEN
    -- Append-only, with two write-once doors and three CORRECTABLE columns.
    -- Everything else is compared as a whole row, so a column added later is
    -- frozen the day it is created.
    frozen_old := to_jsonb(OLD) - stamps;
    frozen_new := to_jsonb(NEW) - stamps;
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is %% and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once, and the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34, PO ruling 2026-09-02). A reversal, an NSF and a reapply are all NEW rows. Changed: %%',
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
    IF OLD.journal_entry_id IS NOT NULL
       AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
      RAISE EXCEPTION 'hard rule 4 / US-PAY-009: payment %% already names journal entry %% and the link is WRITE-ONCE. Re-pointing it would detach the payment from the entry that holds its money, which is the one question the column exists to answer; a correction to the books is a reversing entry, never a new pointer.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.journal_entry_id;
    END IF;
    RETURN NEW;
  END IF;

  -- Still processing: the money has not arrived and nothing has been posted.
  -- The row may take the clearing transition and the three corrections, and
  -- NOTHING else — a payment whose money has not arrived is in nobody's drawer
  -- and has reached no journal, so neither stamp is open here.
  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% is processing — only status and cleared_at may change (the clearing transition, BR-PAY-021), plus the cheque number, memo and tender, which are corrections and carry no money (CR-059 CS-34). The amount, currency, account, purpose, number, posting date, deposit batch, journal entry, reversal link, reversal reason and idempotency key are frozen from the moment the row exists. Changed: %%',
      COALESCE(OLD.payment_no, OLD.id::text),
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""


def name_the_till(apps_registry, schema_editor):
    """PostgreSQL only — SQLite has no triggers (hard-won law 14)."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(BATCH_NEEDS_A_SESSION_SQL)
    schema_editor.execute(BATCH_LOCK_NAMES_THE_TILL_SQL)
    schema_editor.execute(PAYMENT_IMMUTABLE_NAMES_THE_TILL_SQL)


def unname_the_till(apps_registry, schema_editor):
    """`P0.16` — *"the deposit re-key is reversible"*, and this is that half."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(DROP_BATCH_NEEDS_A_SESSION_SQL)
    schema_editor.execute(RESTORE_0005_BATCH_LOCK_SQL)
    schema_editor.execute(RESTORE_0014_PAYMENT_IMMUTABLE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0032_rls_cr135_p0_5_counter_sessions"),
    ]

    operations = [
        # ── the system till: a session that is openly nobody's ──────────────
        migrations.AlterField(
            model_name="countersession",
            name="owner",
            field=models.ForeignKey(
                blank=True,
                db_column="owner_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="counter_sessions",
                to="identity.user",
            ),
        ),
        migrations.AlterField(
            model_name="countersession",
            name="service_centre",
            field=models.ForeignKey(
                blank=True,
                db_column="service_centre_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="counter_sessions",
                to="tenancy.servicecentre",
            ),
        ),
        migrations.AddField(
            model_name="countersession",
            name="system_day",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RemoveConstraint(
            model_name="countersession",
            name="ck_counter_sessions_close_kind",
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(close_kind__in=apps.payments.models.COUNTER_CLOSE_KINDS)
                | models.Q(close_kind__isnull=True),
                name="ck_counter_sessions_close_kind",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="countersession",
            name="ck_counter_sessions_closed_together",
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    closed_at__isnull=True, closed_by__isnull=True, close_kind__isnull=True
                )
                | models.Q(
                    closed_at__isnull=False, closed_by__isnull=False, close_kind__isnull=False
                )
                | models.Q(
                    closed_at__isnull=False,
                    closed_by__isnull=True,
                    close_kind=apps.payments.models.COUNTER_CLOSE_SYSTEM,
                ),
                name="ck_counter_sessions_closed_together",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    close_kind=apps.payments.models.COUNTER_CLOSE_SYSTEM,
                    closed_by__isnull=True,
                    opening_float=0,
                    owner__isnull=True,
                    service_centre__isnull=True,
                    system_day__isnull=False,
                )
                | (
                    (
                        models.Q(close_kind__isnull=True)
                        | models.Q(
                            close_kind__in=apps.payments.models.COUNTER_CLOSE_KINDS_BY_A_PERSON
                        )
                    )
                    & models.Q(
                        owner__isnull=False,
                        service_centre__isnull=False,
                        system_day__isnull=True,
                    )
                ),
                name="ck_counter_sessions_system_is_nobodys",
            ),
        ),
        migrations.AddConstraint(
            model_name="countersession",
            constraint=models.UniqueConstraint(
                condition=models.Q(system_day__isnull=False),
                fields=("tenant", "system_day"),
                name="uq_counter_sessions_system_day",
            ),
        ),
        # ── the re-key itself ───────────────────────────────────────────────
        migrations.AddField(
            model_name="depositbatch",
            name="session",
            field=models.ForeignKey(
                blank=True,
                db_column="session_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="deposit_batches",
                to="payments.countersession",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="depositbatch",
            name="uq_deposit_batches_day_method",
        ),
        migrations.AddConstraint(
            model_name="depositbatch",
            constraint=models.UniqueConstraint(
                condition=models.Q(session__isnull=False),
                fields=("tenant", "session", "method"),
                name="uq_deposit_batches_session_method",
            ),
        ),
        # ── the guard, and the two refusals whose REASON has changed ────────
        migrations.RunPython(name_the_till, unname_the_till),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/02-decision-log.md 2026-09-22 ×4 ("THE BATCHES ALREADY BANKED…", "PHASE 0 INCLUDES THE LEDGER CHANGE…", "THE DEPOSIT BATCH GETS A UNIQUENESS MECHANISM…", "THE DEPOSIT BATCH CODE COMES FROM SETTINGS → NUMBERING…") · 12-governance/01-open-questions.md OQ-PAY-12575/12576/12577 (all CLOSED by this work) · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-025 (SUPERSEDED-IN-PART) · 05-prototype/06 Payments Page Blueprint.pdf p012 · CLAUDE.md hard rules 1, 4, 5, 6 · hard-won laws 7 and 14
# generated: 2026-09-22 by LANE P0-BATCH-3
# checklist: A✔ B=n/a(phase 0 ships no screen) C✔ D=n/a(a migration) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: golden-verify 33 PASS / 0 FAIL (the HARNESS number; the ENGINE number is 14 of 61 signed GTs and this work touches neither) · ruff clean on every file changed · makemigrations --check clean for payments · APPLIED, REVERSED AND RE-APPLIED on a live PostgreSQL 16 clone (sbh_clone_p06rekey): forwards leaves uq_deposit_batches_session_method + trg_deposit_batch_needs_session and the TILL wording; backwards restores uq_deposit_batches_day_method, drops the guard and restores payments/0014's *grouped by day AND tender* verbatim; forwards again is identical to the first. PROVED RED WITH THE MIGRATION REVERSED, which is the red proof of the whole task: Dana's $1,240 cheque batch inserts and Sam's $880 dies on `ERROR: duplicate key value violates unique constraint "uq_deposit_batches_day_method"` — the second clerk of the day cannot bank. With it applied both bank, as DEP-260922-0001 and DEP-260922-0002. Every guard shown red on its own case and green on the lawful neighbour (10-scripts/p06_rekey_readback.py), including a RAW INSERT with a cursor that bypasses every Python check, and the mirror case a negation would have missed: an OPEN till with no owner. The ledger acceptance test (10-scripts/p06_ledger_two_deposits_readback.py, unchanged) re-run on the re-keyed schema: two deposits, 1,240.00 = 1,240.00, 880.00 = 880.00, the day 2,120.00, zero rows left behind
# exceptions:

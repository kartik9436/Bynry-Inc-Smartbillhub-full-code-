# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-34 · task 41 — "Correct what is not money". The write
#           half, which was stubbed until the Product Owner ruled.
# Story:    US-PAY-004 (the payment record) · US-PAY-020/023 (the bank
#           reconciliation that matches on the reference)
#           Screens: S35 (the Correct-reference modal) · S21 (the corrected
#           value) — both are CR-059 task 42
# Rules:    CLAUDE.md hard rule 4, **NARROWED for three columns by PO ruling
#           2026-09-02** · BR-PAY-002 (a payment past `processing` is
#           append-only) · BR-PAY-025 (batches group by day × tender) ·
#           BR-PAY-004 (a reconciled batch is LOCKED) · hard rule 7 (audit)
# Ruling:   OQ-1322 CLOSED 2026-09-02 (option a). PO verbatim: *"(a) Allow those
#           fields to change"*. The lane recommended (b), an append-only
#           amendments table; the PO chose (a). Built as ruled, not re-argued.
# Tests:    06-backend/tests/test_cr059_cs34_amend_reference.py
# Impacts:  apps/payments/amendments.py (the write this unblocks) ·
#           apps/payments/amendments_api.py
# ───────────────────────────────────────────────────────
"""payments 0014 — three columns a correction may move, and NOTHING else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this one narrows a
hard rule). HUMAN-REVIEW-PENDING — AI-authored 2026-09-02 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
`confirmation` (the cheque number), `memo` and `method_id` (the tender) may be
UPDATEd on a payment in every status. **Every other column of `payments`, and
every other table CLAUDE.md hard rule 4 names, is exactly as frozen as it was
yesterday** — the whole-row comparison that freezes a column added tomorrow is
untouched, and DELETE is still refused in every status.

**THE RULE BEING NARROWED, QUOTED, BECAUSE A SUPERSESSION IS STATED AND NEVER
ASSUMED.** CLAUDE.md hard rule 4: *"no UPDATE/DELETE on issued invoices, invoice
lines, payments, journal entries — corrections are new rows."* `CR-059` §2 lists
thirteen signed statements the change request reverses and this was not among
them, so the supersession could not be a lane's to take (CLAUDE.md law 13). It
is the Product Owner's, on the record, dated 2026-09-02, and CLAUDE.md's own
hard rule 4 carries the amendment in the same commit as this file.

**THE COST THE PO ACCEPTED, stated because a signature covers only what was
shown:** with the value changed in place the previous cheque number lives ONLY
in `audit_log`, and this product prunes that on a retention schedule. Whether a
reference-amendment audit row is EXEMPT from pruning was NOT put to them and is
not answered here — it is `OQ-1340`, and until it is answered nothing in this
repository may describe the amendment path as a permanent record of the old
value.

═══════════════════════════════════════════════════════════════════════════════
WHY THE WHOLE FUNCTION BODY IS RESTATED
═══════════════════════════════════════════════════════════════════════════════
plpgsql has no partial replacement: `CREATE OR REPLACE` writes the whole body,
so the whole body has to be here and the diff against 0006 IS the review. What
is below is **0006's function verbatim**, with three changes and no others:

  1. an `amendable` array, added to BOTH allow lists — the `processing` one and
     the past-`processing` one — because the ruling says *in every status*;
  2. the two refusal messages name the three correctable fields, so a clerk who
     hits the trigger is told what CAN be corrected rather than only what
     cannot (BR-SHL-020);
  3. a guard refusing `method_id` once the payment sits in a deposit batch.

**(3) IS NOT SCOPE CREEP AND IT IS WORTH A PARAGRAPH.** CS-34's own second rule
is *"the tender may not be amended once the payment has been swept into a
deposit batch, because batches group by day and tender: changing it would move
the payment between two batches, one of which may be reconciled and locked."*
That rule was already enforced in Python (`amendments.refuse_tender_change_once_
batched`) and the service is the only caller — but the whole reason this file
exists is that a Python check is not a guarantee when a repair script can open a
cursor. Opening `method_id` at the database without it would leave the database
permitting a state the spec forbids, which is hard-won law 1 in the guard
itself. The two refusals say different things on purpose: the trigger's is for
whoever bypassed the service, the service's names the batch a clerk can act on.

**WHY WRITE-ONCE IS WRONG FOR THESE THREE.** `deposit_batch_id` and
`journal_entry_id` are STAMPS — a payment is banked once and posts once — so
they are `NULL -> set` and guarded against re-pointing. A cheque number is a
CORRECTION, and a clerk who mistypes twice must be able to correct twice; a
write-once reference would make the second typo permanent, which is the very
failure CS-34 was written about.

═══════════════════════════════════════════════════════════════════════════════
⚠ POSTGRESQL ONLY — AND THAT IS WHY THIS IS A LAW-14 FILE
═══════════════════════════════════════════════════════════════════════════════
The trigger exists only on PostgreSQL, and `config/settings/test.py` hardcodes
in-memory SQLite. So **a `.update(confirmation=…)` written without this
migration passes the entire suite on every machine in this repository and raises
on the first real cheque** — which is exactly why the write it unblocks was
proved against a live PostgreSQL 16 cluster and not against the default suite.
The reverse restores **0006's** body exactly, not 0002's and not a DROP: a
freeze must unapply to precisely what came before it (hard-won law 3), and
dropping the function would leave `payments` unfrozen after an unapply.
"""

from django.db import migrations

#: 0006's body, plus the three amendable columns and the batched-tender guard.
#: `%%` throughout because `RunSQL`/`execute` percent-formats; the deployed text
#: carries single percents.
AMENDABLE_IMMUTABILITY_SQL = """
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

#: **0006's function restored EXACTLY** — not a DROP, and not 0005's or 0002's.
#: Dropping it would leave `payments` unfrozen after an unapply; restoring an
#: older body would close doors 0005 and 0006 opened. A freeze must fail closed
#: AND unapply to exactly what came before it (hard-won law 3).
RESTORE_0006_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION payments_payment_immutable() RETURNS trigger AS $$
DECLARE
  mutable  text[] := ARRAY['status', 'cleared_at', 'updated_at'];
  stamps   text[] := ARRAY['deposit_batch_id', 'journal_entry_id', 'updated_at'];
  frozen_old jsonb;
  frozen_new jsonb;
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'BR-PAY-002 / hard rule 4: payment %% cannot be removed, in any status. Money that was handed over is financial history; a correction is a new reversing row (BR-PAY-011/013/031), and Cancel on a processing payment is a status move, not a removal.',
      COALESCE(OLD.payment_no, OLD.id::text);
  END IF;

  IF OLD.status <> 'processing' THEN
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
    IF OLD.journal_entry_id IS NOT NULL
       AND NEW.journal_entry_id IS DISTINCT FROM OLD.journal_entry_id THEN
      RAISE EXCEPTION 'hard rule 4 / US-PAY-009: payment %% already names journal entry %% and the link is WRITE-ONCE. Re-pointing it would detach the payment from the entry that holds its money, which is the one question the column exists to answer; a correction to the books is a reversing entry, never a new pointer.',
        COALESCE(OLD.payment_no, OLD.id::text), OLD.journal_entry_id;
    END IF;
    RETURN NEW;
  END IF;

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


def open_the_three_columns(apps_registry, schema_editor):
    """PostgreSQL only — SQLite has no triggers and nothing to widen."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(AMENDABLE_IMMUTABILITY_SQL)


def close_the_three_columns(apps_registry, schema_editor):
    """Back to 0006's body verbatim — see the constant's own note."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RESTORE_0006_IMMUTABILITY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0013_rls_w8_reconciliation"),
    ]

    operations = [
        migrations.RunPython(open_the_three_columns, close_the_three_columns),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/02-decision-log.md 2026-09-02 "A PAYMENT'S REFERENCE, MEMO AND TENDER MAY BE AMENDED IN PLACE" · 12-governance/01-open-questions.md OQ-1322 (CLOSED — option a) + OQ-1340 (OPEN, retention) · 12-governance/11-change-requests.md CR-059 §8 CS-34 + §11 task 41 · CLAUDE.md hard rule 4 (amended 2026-09-02) · hard-won law 14 · apps/payments/migrations/0006_w4_reversal_and_refunds.py (the body this restates)
# generated: 2026-09-02 by the CR-059 W7 correct-what-is-not-money lane
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(S35's modal and S21's corrected value are CR-059 task 42) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · ruff ✔ black ✔ · G16 PASS before and after · golden-verify 33 PASS / 0 FAIL before and after · applied against a LIVE PostgreSQL 16 cluster · PROVED RED BEFORE GREEN on that same cluster by swapping this file's forward body for its own reverse body and re-running, verbatim: `django.db.utils.ProgrammingError: BR-PAY-002 / hard rule 4: payment PY-260808-0001 is cleared and is append-only — no column may change except the deposit batch it is banked in (BR-PAY-025) and the journal entry it posted (US-PAY-009), each once. A reversal, an NSF and a reapply are all NEW rows. Changed: confirmation` — 3 failed. With the forward body back, the same three pass and the amount, the DELETE and the banked tender all still raise
# exceptions:
#   E1 this migration NARROWS CLAUDE.md hard rule 4 for exactly three columns. The narrowing is the PO's ruling of 2026-09-02 and CLAUDE.md carries the amendment in the same commit; a hard rule narrowed in code and not in CLAUDE.md is the divergence that cost eleven days on BR-RAT-088
#   E2 the previous value of a corrected reference then lives ONLY in `audit_log`, which is pruned on a retention schedule. Whether that row is exempt is OQ-1340 and is NOT answered here; nothing may call this path a permanent record of the old value until it is
#   E3 the batched-tender refusal is enforced in BOTH the service and this trigger, deliberately — a Python check is not a guarantee against a repair script, and the two messages say different things because they are read by different people
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

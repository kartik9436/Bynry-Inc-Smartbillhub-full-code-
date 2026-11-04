# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-PAY-6331 — "The cheque number is asked for BEFORE the cheque
#           exists and cannot be recorded when it is written."
# Story:    US-PAY-011 §5 ("required for check") — unchanged in substance,
#           moved in ACT.
#           Screens: S58 · blueprint 6·3a Raise, 6·3b Issue.
# Rules:    CLAUDE.md hard rule 4 (financial immutability — **`refunds` is NOT
#           one of its tables**; see below) · BR-PAY-014 · BR-PAY-021 (the
#           bank line a refund is matched against) · hard rule 7 (audit)
# Blueprint:05-prototype/06 Payments Page Blueprint.pdf p078, read as an IMAGE
#           at scale 2.0 (B14 rule 42). Annotation ②: "Cheque number · **the
#           only record of which cheque this was**".
# Tests:    06-backend/tests/test_def_pay_6331_cheque_number_at_issue.py
# Impacts:  apps/payments/refunds.py (issue_refund) ·
#           apps/payments/refunds_api.py (both doors)
# ───────────────────────────────────────────────────────
"""payments 0041 — ONE more write-once column on `refunds`, and nothing else.

HUMAN-OWNED (migration ordering and financial immutability are CLAUDE.md 🔒
paths). HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
`refunds.reference` — the cheque number — may be written **once**, from NULL,
and may never be changed afterwards. Everything else about the `refunds` freeze
is exactly as it was: the amount, the currency, the payment, the method and the
reason are still fixed from the moment the row exists, a VOID row is still
closed, DELETE is still refused in every status, and both journal-entry links
are still write-once.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT A NARROWING OF HARD RULE 4, AND THE DISTINCTION MATTERS
═══════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard rule 4 names *"issued invoices, invoice lines, payments, journal
entries"* and — since 2026-09-02 — narrows for exactly three columns of
`payments` through one endpoint, adding that *"widening it anywhere else is a
new ruling, not this one."*

**`refunds` is not one of hard rule 4's tables, and 0006 says so itself**, in
its own exception (4), verbatim:

    "(4) `refunds` IS NOT A DB-4 APPEND-ONLY TABLE and is not frozen as one.
     B2's DB-4 list does not include it, which is what makes r2's status walk
     lawful; the freeze is deny-by-default with the transition columns allowed,
     and DELETE is refused in every status"

So this file does not touch hard rule 4's allow list and `payments/0014`
remains the only place that one has ever moved. What it widens is **0006's own
deny-by-default list**, by one column, under the standing *"Exact DDL =
Eng-Lead 🔒"* delegation (B2 r12 #17, r14 #9) — the same delegation under which
0006 added `requested` and `approved` to a status set B2 r2 signs three values
for. The judgment is recorded in 12-governance/02-decision-log.md.

**AND IT IS WRITE-ONCE, WHICH IS WHY IT IS NOT A HOLE.** A mutable cheque
number would be a real breach of the spirit hard rule 4 protects: the number is
what bank reconciliation matches the outgoing item on (BR-PAY-021, applied
outbound), so a number that can change is a tie-out that can be made to lie
about itself after the fact. NULL → set, once, and never again — the identical
shape `journal_entry_id` and `void_journal_entry_id` already have two clauses
above it in this same function, for the identical reason.

═══════════════════════════════════════════════════════════════════════════════
WHAT WAS WRONG THAT THIS FIXES
═══════════════════════════════════════════════════════════════════════════════
The cheque number was collected on the **Raise** form — when a clerk is asking
for a refund that Finance has not approved and nobody has written a cheque for.
Days later the real cheque is written and there was **nowhere to record its
number**: `issue_refund` took no such argument and the column was frozen from
row creation, so the field was either left blank forever or filled with a
guess. The blueprint calls it *"the only record of which cheque this was"* and
draws it on **Issue**.

The requirement therefore MOVES rather than goes: US-PAY-011 §5's *"required
for check"* names no act, and it is now enforced at the act that writes the
cheque.

═══════════════════════════════════════════════════════════════════════════════
WHY THE WHOLE FUNCTION BODY IS RESTATED
═══════════════════════════════════════════════════════════════════════════════
plpgsql has no partial replacement: `CREATE OR REPLACE` writes the whole body,
so the whole body has to be here and **the diff against 0006 IS the review**.
What is below is 0006's `payments_refund_immutable` verbatim, with two changes
and no others:

  1. `'reference'` joins the `mutable` array;
  2. a write-once guard for it, worded in the clerk's terms rather than the
     column's, immediately after the two journal-entry guards it copies.

`payments_payment_immutable` is NOT touched by this file — 0014 owns that one
now, and restating it here would silently revert the three-column correction.

⚠ **POSTGRES ONLY, AND THE SERVICE ASSERTS THE SAME LAW.** The test database is
SQLite and has no triggers (0006 exception (5), CLAUDE.md hard-won law 14), so
`refunds.issue_refund` refuses an overwrite in Python as well. Two enforcements
of one rule, deliberately, because a guard that skips silently on the
developer's own database is not a guard.
"""

from django.db import migrations

WRITE_ONCE_REFERENCE_SQL = """
-- ── refunds: 0006's freeze, plus ONE more write-once stamp ──────────────────
-- 0006's function VERBATIM except that `reference` joins the allow list and
-- gains its own re-write guard. See this migration's docstring for why the
-- whole body is restated.
CREATE OR REPLACE FUNCTION payments_refund_immutable() RETURNS trigger AS $$
DECLARE
  -- The ONLY columns a refund may move after it is written. Everything absent
  -- from this list is frozen, INCLUDING every column added after today: the
  -- amount, the currency, the payment it draws on, the method and the reason
  -- are facts from the moment the row exists.
  --
  -- `void_journal_entry_id` and `journal_entry_id` are here because the entry
  -- ids arrive microseconds after their transitions, in the same transaction,
  -- for the reason the module docstring gives; both are ALSO write-once, below.
  --
  -- ⚠ `reference` — the cheque number — JOINS THEM ON 2026-09-23 (DEF-PAY-6331)
  -- and is write-once for the same reason they are: it does not EXIST until the
  -- cheque is written, which happens at issue, and once it exists it is what
  -- bank rec matches the outgoing item on (BR-PAY-021). NULL -> set, once.
  mutable text[] := ARRAY[
    'status',
    'approved_by_id', 'approved_at',
    'issued_at', 'cleared_at',
    'voided_at', 'void_reason',
    'journal_entry_id', 'void_journal_entry_id',
    'reference',
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

  -- Write-once on the cheque number (DEF-PAY-6331). It is absent until the
  -- cheque is written and is a fact from the instant it is, because bank
  -- reconciliation matches the outgoing item on it.
  IF OLD.reference IS NOT NULL
     AND NEW.reference IS DISTINCT FROM OLD.reference THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% already names the cheque it was paid by (%%); a cheque number is written once and never changed. A cheque that left the building and came back is VOIDED and re-raised, which is what leaves a trail bank rec can follow.',
      OLD.id::text, OLD.reference;
  END IF;

  frozen_old := to_jsonb(OLD) - mutable;
  frozen_new := to_jsonb(NEW) - mutable;
  IF frozen_new IS DISTINCT FROM frozen_old THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% is frozen except its status walk (requested -> approved -> issued -> cleared, or -> void) and the cheque number written at issue. The amount, currency, payment, method, reason and the requesting act are fixed from the moment the row exists. Changed: %%',
      OLD.id::text,
      (SELECT string_agg(key, ', ' ORDER BY key)
         FROM jsonb_each(frozen_new)
        WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
  END IF;
  RETURN NEW;
END $$ LANGUAGE plpgsql;
"""

#: 0006's body, VERBATIM. The reverse restores it rather than dropping the
#: function, so an unapply cannot leave `refunds` unfrozen — 0006's own reasoning
#: for `payments`, applied to its own table.
RESTORE_0006_IMMUTABILITY_SQL = """
CREATE OR REPLACE FUNCTION payments_refund_immutable() RETURNS trigger AS $$
DECLARE
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

  IF OLD.status = 'void' THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% is VOID and is closed. Its credit has been restored by a reversing entry; paying it again is a NEW refund request, never a revived row.',
      OLD.id::text;
  END IF;

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
"""


def open_the_cheque_number(apps_registry, schema_editor):
    """PostgreSQL only — SQLite has no triggers and nothing to widen."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(WRITE_ONCE_REFERENCE_SQL)


def close_the_cheque_number(apps_registry, schema_editor):
    """Back to 0006's body verbatim — see the constant's own note."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RESTORE_0006_IMMUTABILITY_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0040_cr138_p45_debtor_credit_indexes"),
    ]

    operations = [
        migrations.RunPython(open_the_cheque_number, close_the_cheque_number),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-PAY-6331 · 05-prototype/06 Payments Page Blueprint.pdf p077-p078 (images, scale 2.0) · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md §5 · apps/payments/migrations/0006_w4_reversal_and_refunds.py (the body this restates) · CLAUDE.md hard rule 4
# generated: 2026-09-23 by lane REFUND-MONEY
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(S58's issue modal is this lane's frontend half) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 this widens 0006's deny-by-default allow list by ONE column. It does NOT touch CLAUDE.md hard rule 4's list — `refunds` is not one of that rule's tables and 0006 exception (4) says so — so `payments/0014` is still the only place THAT list has moved
#   E2 the column is WRITE-ONCE at the database AND in `refunds.issue_refund`, deliberately. The test database is SQLite and has no triggers (hard-won law 14), so a Python-only guard would be proved by a suite that cannot execute it
#   E3 `payments_payment_immutable` is deliberately NOT restated here. 0014 owns it; restating 0006's copy would silently revert the three-column correction the PO ruled on 2026-09-02
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

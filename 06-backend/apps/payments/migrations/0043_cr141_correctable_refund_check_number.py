# ── Trace ──────────────────────────────────────────────
# Change:   CR-141-BRC07 — a refund's check number may be corrected, the same
#           way a payment's can.
# Ruling:   OQ-PAY-12614 CLOSED 2026-09-23, option (b). PO, verbatim: *"One
#           thing needs your sign-off, because it is a money record: (b) Allow
#           a correction, the same way you allowed it for payments on 2
#           September"*. SHOWN, and so all the signature covers: *Dana sends a
#           refund of $91.60 by check #10241 but types #10214; as built it can
#           never be changed.*
# Story:    US-PAY-011 §5 ("required for check") · S58
# Rules:    CLAUDE.md hard rule 4 (financial immutability — **`refunds` is NOT
#           one of its tables**; see below) · hard rule 7 (audit) · BR-PAY-014
#           · BR-PAY-021 (the bank line a refund is matched against)
# Tests:    06-backend/tests/test_cr141_refund_check_number_correction.py
# Impacts:  apps/payments/refunds.py (`correct_refund_reference`, the ONE caller
#           that opens the window) · apps/payments/refunds_api.py
#           (`POST /refunds/{id}/correct-reference`)
# ───────────────────────────────────────────────────────
"""payments 0043 — the refund's check number gets ONE named door, and nothing else moves.

HUMAN-OWNED (migration ordering and financial immutability are CLAUDE.md 🔒
paths). Numbered 0043 because a sibling landed `0042_def_cus_6376_…` (the
counter-receipt freeze, a different function) while this was being written;
it restates `payments_refund_immutable` from `0041`, which `0042` does not touch. HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling of
2026-08-09 (*"AI will do it; we will review it later as human"*); row in
12-governance/09-human-review-ledger.md. **The RULE it implements is signed**
(`OQ-PAY-12614`, above); the MECHANISM below is this lane's and is what that row
asks a reviewer to weigh.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
`refunds.reference` — the check number — stays WRITE-ONCE for every writer
(`payments/0041`: NULL → set at issue, never rewritten), **except one**: inside
a transaction-local *correction window* that names THIS refund, it may be
replaced by another non-blank number, and while that window is open NOTHING ELSE
on the row may move. The amount, the currency, the account, the payment, the
method, the reason, the status walk, both entry links and DELETE are exactly as
frozen as they were yesterday.

═══════════════════════════════════════════════════════════════════════════════
THE TWO DESIGNS THE BRIEF OFFERED, AND WHY THIS IS THE SECOND
═══════════════════════════════════════════════════════════════════════════════
**(a) A narrow allow-list change, the correction path its only caller** — what
`payments/0014` did for a payment's cheque number: `confirmation` joins the
allow list and ANY statement may then rewrite it; that only the service does so
is a convention.

**(b) Write-once stays for the ISSUE write, plus a separately guarded
correction** — what this file does.

**(b) is the one that mirrors `0014` most closely where it matters, and (a)
would copy its surface and break its reasoning.** Three reasons:

  1. **`0014`'s own argument is against a Python-only guarantee.** Its
     docstring: *"a Python check is not a guarantee when a repair script can
     open a cursor"* — which is why it put the batched-tender refusal in the
     trigger as well as the service. Under (a) the rule *"only through the
     named correction"* would be exactly such a check: every bulk `.update()`,
     every data-fix script and every future door could rewrite a check number
     with no note and no audit row, and the database would agree.
  2. **`refunds` already had the stricter law, and the PO signed an exception
     to it, not its repeal.** `0041` made the number write-once and argued it
     from `BR-PAY-021`: a number bank reconciliation matches the outgoing check
     on, which anybody can edit afterwards, is a tie-out that can be made to
     lie. The PO's (b) says a clerk may CORRECT it; it does not say any writer
     may rewrite it. (b) keeps `0041`'s law for everything that is not the
     correction, which is the narrowest reading of a signature that *"covers
     only what was shown"*.
  3. **It is the only design under which proof (ii) — *"changing `reference` by
     any OTHER write is REFUSED by the database"* — can be true.** Under (a) a
     raw `UPDATE refunds SET reference = …` succeeds, and the test that says it
     is refused cannot be written.

**THE WINDOW IS A MECHANISM THIS CODEBASE ALREADY TRUSTS.** `ledger/0004` fences
the books the same way: `posting.post()` opens `app.ledger_posting` with
`set_config(…, true)` inside its own transaction and the trigger refuses every
INSERT outside it. Its docstring is honest about what that is — *"a fence, not a
vault"*: anything that can open a connection can issue the same `set_config`.
What it makes impossible is the ACCIDENT, and a caller that forges it has
written *"I am bypassing the correction"* into its own source. This window is
narrower than that one in two ways: it carries the REFUND'S ID, so it opens one
row and not a table, and `set_config(…, true)` is transaction-local, so a crash,
a rollback or a rollback-to-savepoint closes it whatever else happens.

WHAT THE WINDOW STILL REFUSES, each for a reason:

  * **a refund with no check number yet** (`OLD.reference IS NULL`) — writing
    the FIRST number is the issue act, which tests the credit, posts the money
    and audits the payout. A correction that could write it would be a second
    way to put a check number on a refund whose money never moved;
  * **a blank or NULL replacement** — US-PAY-011 §5 makes a check refund's
    number required at issue; a correction replaces a number and never erases
    one;
  * **any other column** — compared as a whole row minus `reference` and
    `updated_at`, so a column added tomorrow is refused inside the window the
    day it is created, exactly as `0006`'s own comparison freezes it outside;
  * **a VOID refund** — `0006`'s VOID guard runs first and is untouched. Nothing
    about a voided check was put to the PO.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT A NARROWING OF HARD RULE 4, AND WHY `payments/0014` IS UNTOUCHED
═══════════════════════════════════════════════════════════════════════════════
CLAUDE.md hard rule 4 names issued invoices, invoice lines, payments and journal
entries, and narrows for exactly three columns of `payments` through
`payments/0014`, adding *"widening it anywhere else is a new ruling, not this
one."* **`refunds` is none of those tables** — `payments/0006`'s own exception
(4): *"`refunds` IS NOT A DB-4 APPEND-ONLY TABLE and is not frozen as one"*. So
this file does not move hard rule 4's allow list, and **`payments/0014` remains
the only place that list has ever moved.** `payments_payment_immutable` is NOT
restated here, for `0041`'s reason: restating any older copy of it would
silently revert the PO's three-column correction of 2026-09-02. A test asserts
that neither SQL constant below so much as names that function.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE OLD NUMBER THEN LIVES ONLY IN `audit_log` — AND THAT IS NOT A PERMANENT RECORD
═══════════════════════════════════════════════════════════════════════════════
The correction writes an audit row carrying the replaced number and the new one
(hard rule 7), inside the same transaction as the UPDATE. **`audit_log` has ONE
retention rule and no row type is exempt from it** — `OQ-1340`, CLOSED
2026-09-23, PO: *"keep the same rule s; when audit log is delete - it is deleted
thats okay"*. So the replaced number is gone once that schedule reaches it, and
**nothing may describe this path as a permanent record of the old number.**

═══════════════════════════════════════════════════════════════════════════════
WHY THE WHOLE FUNCTION BODY IS RESTATED, AND HOW "NOTHING ELSE MOVED" IS PROVED
═══════════════════════════════════════════════════════════════════════════════
plpgsql has no partial replacement: `CREATE OR REPLACE` writes the whole body,
so the whole body is below and **the diff against `0041` IS the review**. It is
`0041`'s `payments_refund_immutable` with exactly the three hunks in `HUNKS`
replaced, and no other byte moved:

  1. the SQL's own header comment, which named `0041`'s change;
  2. the `mutable` array's comment on `reference`, which said *"NULL -> set,
     once"* and would otherwise be a comment claiming a guarantee the function
     no longer makes (hard-won law 1);
  3. the check number's write-once guard, which gains the window ahead of it
     and a last sentence naming the door that CAN change the number instead of
     saying it never changes.

`test_cr141__the_forward_body_is_0041_with_exactly_three_hunks_replaced` rebuilds
this body FROM `0041`'s by applying `HUNKS`, requires each hunk to occur in
`0041` exactly once, and requires the result to be byte-identical — so a fourth
change anywhere goes red rather than hiding in a long string. The reverse is
`0041`'s body verbatim and a second case asserts that byte-for-byte too.

⚠ **POSTGRES ONLY, AND THE SERVICE ASSERTS THE SAME LAW.** SQLite has no
triggers (`0006` exception (5), CLAUDE.md hard-won law 14), so
`refunds.correct_refund_reference` refuses every one of the cases above in
Python as well. Two enforcements of one rule, deliberately: a guard that skips
silently on the developer's own database is not a guard.
"""

from django.db import migrations

#: The GUC the correction window is. Named here AND in `apps/payments/refunds.py`
#: (`CORRECTION_WINDOW_GUC`) so the fence and the one lawful way through it are
#: greppable from each other — `ledger/0004` and `posting.WRITE_WINDOW_GUC`'s
#: shape.
CORRECTION_WINDOW_GUC = "app.refund_reference_correction"

# ── the three hunks, each as `0041` reads and as this file reads ────────────
#: `%%` throughout, because `schema_editor.execute` percent-formats; the
#: deployed text carries single percents. Same reason as 0014, 0041, ledger/0004.

_HEADER_0041 = """-- ── refunds: 0006's freeze, plus ONE more write-once stamp ──────────────────
-- 0006's function VERBATIM except that `reference` joins the allow list and
-- gains its own re-write guard. See this migration's docstring for why the
-- whole body is restated.
"""

_HEADER_0043 = """-- ── refunds: 0041's freeze, plus ONE named door for the check number ───────
-- 0041's function VERBATIM except that the check number's write-once guard now
-- opens for exactly one caller — the correction window, for one refund — and
-- the comment on `reference` says so. See payments/0043's docstring for why
-- the whole body is restated.
"""

_MUTABLE_COMMENT_0041 = """  -- ⚠ `reference` — the cheque number — JOINS THEM ON 2026-09-23 (DEF-PAY-6331)
  -- and is write-once for the same reason they are: it does not EXIST until the
  -- cheque is written, which happens at issue, and once it exists it is what
  -- bank rec matches the outgoing item on (BR-PAY-021). NULL -> set, once.
"""

_MUTABLE_COMMENT_0043 = """  -- ⚠ `reference` — the check number — JOINED THEM ON 2026-09-23 (DEF-PAY-6331):
  -- it does not EXIST until the check is written, which happens at issue, and
  -- once it exists it is what bank rec matches the outgoing item on
  -- (BR-PAY-021). NULL -> set at issue; set -> another number ONLY through the
  -- correction window below (OQ-PAY-12614, PO 2026-09-23, CR-141-BRC07).
"""

_GUARD_0041 = """  -- Write-once on the cheque number (DEF-PAY-6331). It is absent until the
  -- cheque is written and is a fact from the instant it is, because bank
  -- reconciliation matches the outgoing item on it.
  IF OLD.reference IS NOT NULL
     AND NEW.reference IS DISTINCT FROM OLD.reference THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% already names the cheque it was paid by (%%); a cheque number is written once and never changed. A cheque that left the building and came back is VOIDED and re-raised, which is what leaves a trail bank rec can follow.',
      OLD.id::text, OLD.reference;
  END IF;
"""

_GUARD_0043 = """  -- THE CORRECTION WINDOW (OQ-PAY-12614, PO 2026-09-23: "(b) Allow a
  -- correction, the same way you allowed it for payments on 2 September").
  -- `refunds.correct_refund_reference` opens it with
  --   SELECT set_config('app.refund_reference_correction', <this refund's id>, true)
  -- inside its own transaction and shuts it before returning. It names ONE
  -- refund, and while it is open that refund may replace its check number and
  -- move NOTHING else — not its status, not a date, not either entry link. A
  -- refund with no number yet has nothing to correct: the first number is the
  -- ISSUE act's, which is where the money moves.
  IF coalesce(current_setting('app.refund_reference_correction', true), '') = OLD.id::text THEN
    IF OLD.reference IS NULL THEN
      RAISE EXCEPTION 'OQ-PAY-12614: refund %% has no check number yet, so there is nothing to correct. The first number is recorded when the refund is issued, which is the act that writes the check.',
        OLD.id::text;
    END IF;
    IF NEW.reference IS NULL OR btrim(NEW.reference) = '' THEN
      RAISE EXCEPTION 'OQ-PAY-12614: refund %% names check %%; a correction replaces a check number with a new check number and never erases it.',
        OLD.id::text, OLD.reference;
    END IF;
    frozen_old := to_jsonb(OLD) - ARRAY['reference', 'updated_at'];
    frozen_new := to_jsonb(NEW) - ARRAY['reference', 'updated_at'];
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'OQ-PAY-12614: the check-number correction on refund %% moves the check number and nothing else. Changed: %%',
        OLD.id::text,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    RETURN NEW;
  END IF;

  -- Everywhere else the check number stays WRITE-ONCE, exactly as 0041 made it
  -- (DEF-PAY-6331): absent until the check is written at issue, and a fact from
  -- the instant it is, because bank reconciliation matches the outgoing item on
  -- it. Only the window above may replace it.
  IF OLD.reference IS NOT NULL
     AND NEW.reference IS DISTINCT FROM OLD.reference THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% already names the check it was paid by (%%); a check number is written once at issue, and is replaced only through Correct check number (POST /refunds/{id}/correct-reference, OQ-PAY-12614), which records who changed it and why.',
      OLD.id::text, OLD.reference;
  END IF;
"""

#: The review, as data: `(what 0041 reads, what this file reads)`, in the order
#: they appear. The test rebuilds `CORRECTABLE_REFERENCE_SQL` from `0041`'s body
#: with exactly these three replacements and requires byte identity.
HUNKS: tuple[tuple[str, str], ...] = (
    (_HEADER_0041, _HEADER_0043),
    (_MUTABLE_COMMENT_0041, _MUTABLE_COMMENT_0043),
    (_GUARD_0041, _GUARD_0043),
)

#: `0041`'s `payments_refund_immutable`, with the three hunks above replaced and
#: NOTHING else changed. Restated in full because plpgsql has no partial
#: replacement — read it against `0041`'s `WRITE_ONCE_REFERENCE_SQL`.
CORRECTABLE_REFERENCE_SQL = """
-- ── refunds: 0041's freeze, plus ONE named door for the check number ───────
-- 0041's function VERBATIM except that the check number's write-once guard now
-- opens for exactly one caller — the correction window, for one refund — and
-- the comment on `reference` says so. See payments/0043's docstring for why
-- the whole body is restated.
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
  -- ⚠ `reference` — the check number — JOINED THEM ON 2026-09-23 (DEF-PAY-6331):
  -- it does not EXIST until the check is written, which happens at issue, and
  -- once it exists it is what bank rec matches the outgoing item on
  -- (BR-PAY-021). NULL -> set at issue; set -> another number ONLY through the
  -- correction window below (OQ-PAY-12614, PO 2026-09-23, CR-141-BRC07).
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

  -- THE CORRECTION WINDOW (OQ-PAY-12614, PO 2026-09-23: "(b) Allow a
  -- correction, the same way you allowed it for payments on 2 September").
  -- `refunds.correct_refund_reference` opens it with
  --   SELECT set_config('app.refund_reference_correction', <this refund's id>, true)
  -- inside its own transaction and shuts it before returning. It names ONE
  -- refund, and while it is open that refund may replace its check number and
  -- move NOTHING else — not its status, not a date, not either entry link. A
  -- refund with no number yet has nothing to correct: the first number is the
  -- ISSUE act's, which is where the money moves.
  IF coalesce(current_setting('app.refund_reference_correction', true), '') = OLD.id::text THEN
    IF OLD.reference IS NULL THEN
      RAISE EXCEPTION 'OQ-PAY-12614: refund %% has no check number yet, so there is nothing to correct. The first number is recorded when the refund is issued, which is the act that writes the check.',
        OLD.id::text;
    END IF;
    IF NEW.reference IS NULL OR btrim(NEW.reference) = '' THEN
      RAISE EXCEPTION 'OQ-PAY-12614: refund %% names check %%; a correction replaces a check number with a new check number and never erases it.',
        OLD.id::text, OLD.reference;
    END IF;
    frozen_old := to_jsonb(OLD) - ARRAY['reference', 'updated_at'];
    frozen_new := to_jsonb(NEW) - ARRAY['reference', 'updated_at'];
    IF frozen_new IS DISTINCT FROM frozen_old THEN
      RAISE EXCEPTION 'OQ-PAY-12614: the check-number correction on refund %% moves the check number and nothing else. Changed: %%',
        OLD.id::text,
        (SELECT string_agg(key, ', ' ORDER BY key)
           FROM jsonb_each(frozen_new)
          WHERE frozen_old -> key IS DISTINCT FROM frozen_new -> key);
    END IF;
    RETURN NEW;
  END IF;

  -- Everywhere else the check number stays WRITE-ONCE, exactly as 0041 made it
  -- (DEF-PAY-6331): absent until the check is written at issue, and a fact from
  -- the instant it is, because bank reconciliation matches the outgoing item on
  -- it. Only the window above may replace it.
  IF OLD.reference IS NOT NULL
     AND NEW.reference IS DISTINCT FROM OLD.reference THEN
    RAISE EXCEPTION 'BR-PAY-014 / hard rule 4: refund %% already names the check it was paid by (%%); a check number is written once at issue, and is replaced only through Correct check number (POST /refunds/{id}/correct-reference, OQ-PAY-12614), which records who changed it and why.',
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

#: **`0041`'s body, VERBATIM** — not a DROP, and not `0006`'s. Dropping the
#: function would leave `refunds` unfrozen after an unapply; restoring `0006`'s
#: would re-freeze the check number `0041` opened at issue. A freeze must
#: unapply to exactly what came before it (hard-won law 3), and a test asserts
#: this constant equals `0041`'s `WRITE_ONCE_REFERENCE_SQL` byte for byte.
RESTORE_0041_SQL = """
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


def open_the_correction_window(apps_registry, schema_editor):
    """PostgreSQL only — SQLite has no triggers and nothing to widen."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(CORRECTABLE_REFERENCE_SQL)


def close_the_correction_window(apps_registry, schema_editor):
    """Back to `0041`'s body verbatim — see the constant's own note."""
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(RESTORE_0041_SQL)


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0042_def_cus_6376_counter_receipt_posting_date_memo"),
    ]

    operations = [
        migrations.RunPython(open_the_correction_window, close_the_correction_window),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-PAY-12614 (CLOSED 2026-09-23, option b) · 12-governance/02-decision-log.md 2026-09-23 "SIGNED: A REFUND'S CHECK NUMBER MAY BE CORRECTED" · apps/payments/migrations/0041_def_pay_6331_cheque_number_at_issue.py (the body this restates) · 0014_cr059_cs34_amendable_reference.py and amendments.py (the payment precedent) · ledger/0004 (the window mechanism) · CLAUDE.md hard rule 4, hard-won laws 7 and 14
# generated: 2026-09-23 by lane REFUND-CORRECT
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(the screen is RefundsPage's Correct check number) F✔ G✔ H=deferred(PO 2026-08-09)
# exceptions:
#   E1 this does NOT touch CLAUDE.md hard rule 4's allow list — `refunds` is not one of that rule's tables (0006 exception (4)) — so `payments/0014` is still the only place THAT list has moved, and `payments_payment_immutable` is not restated
#   E2 the correction window is a transaction-local GUC — a FENCE, not a vault, exactly as `ledger/0004` says of `app.ledger_posting`. A caller that forges it has written "I am bypassing the correction" into its own source
#   E3 only `reference` becomes correctable. The payment rule also covers a memo and a tender; those were NOT put to the PO for refunds and are NOT signed, so the window refuses every other column
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:  CR-137-BRC07 · P3.5 — "A sixth payment state". The payments
#          blueprint p19, verbatim: *"`ck_payments_status` is written against
#          the five, so `cancelled` needs a migration that ALTERS THE CHECK"*,
#          outcome *"The state exists in the database, not only in the
#          service."*
# Story:   no story — a blueprint task. `P3.2` (POST /payments/{id}/cancel) is
#          the service that writes it and is another lane's; this migration is
#          the state it writes INTO, and it lands first on purpose.
# Rules:   CLAUDE.md hard rule 4 (financial immutability — and `P3.6`'s proof
#          that this value lands on the FROZEN side of it) · hard rule 1
#          (tenant scoping — no data is touched here, see below) ·
#          BR-PAY-002 (a payment past `processing` is append-only) ·
#          hard-won law 7 (proved RED first, in the harness that will run it)
#          · hard-won law 14 (SQLite cannot show any of this)
# Tests:   10-scripts/p3_cancel_state_and_trigger_readback.py (PostgreSQL 16 —
#          the whole proof, both directions) · `P3.13`/`P3.14` are the suite
#          cases and are another lane's
# Impacts: apps/payments/models.PAYMENT_STATUSES (+1) and, by derivation and
#          WITHOUT AN EDIT, PAYMENT_FROZEN_STATUSES (+1) ·
#          apps/integrations/reference.PAYMENT_STATUS_LABELS (+1 sentence) ·
#          NOT apps/integrations/seams/payments.COLLECTABLE_STATUSES ·
#          NO trigger, NO allow list, NO column, NO index and NO data
# ───────────────────────────────────────────────────────
"""payments 0036 — `cancelled`, the sixth payment state, and nothing else.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09. Migration ordering is a CLAUDE.md 🔒 sensitive path and this file
widens a money vocabulary, so there is a row in
`12-governance/09-human-review-ledger.md`.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
`ck_payments_status` accepts a sixth word, `cancelled`. **No column is added,
no row is written, no trigger is touched and hard rule 4's allow list does not
move** — `P3.8` is the guard that keeps that last sentence true.

═══════════════════════════════════════════════════════════════════════════════
⚠ WHICH SIDE OF THE FREEZE IT LANDS ON — THE ONE QUESTION THIS FILE MUST ANSWER
═══════════════════════════════════════════════════════════════════════════════
**`cancelled` IS A FROZEN STATUS.** The instant it lands on a row, that row is
financial history: no column may change but the two write-once stamps
(`deposit_batch_id`, `journal_entry_id`) and the three correctable references
(`confirmation`, `memo`, `method_id`), and DELETE is refused as it is in every
status.

⚠ **AND IT LANDED THERE BY DEFAULT, WITHOUT AN EDIT, WHICH IS WHY IT IS
WRITTEN OUT HERE RATHER THAN LEFT TO BE INFERRED.** Two mechanisms put it
there and neither of them mentions `cancelled`:

  * `PAYMENT_FROZEN_STATUSES` is `tuple(s for s in PAYMENT_STATUSES if s !=
    PAYMENT_PROCESSING)` — a DERIVATION. Appending to `PAYMENT_STATUSES`
    appended to it, on a line nobody edited and in a file nobody had to read.
  * `trg_payment_immutable` does not read that tuple at all. It asks
    `OLD.status <> 'processing'` as a **literal**, so every status that is not
    `processing` is frozen by construction — including ones invented after the
    trigger was written.

**A default nobody chose is not a decision, so it was checked rather than
inherited**, and the check is the reason it is the right answer:

  * **The cancel MOVE is permitted** — `processing → cancelled` reaches the
    trigger's still-processing branch, where `status` is on the `mutable` allow
    list, so the one statement a cancel needs is lawful. Without this the
    feature could not exist at all.
  * **The cancelled ROW is frozen** — the next statement against it takes
    `OLD.status = 'cancelled'`, fails `<> 'processing'`, and is refused. So a
    cancelled payment cannot be un-cancelled, re-amounted, or quietly moved to
    another account, and `P3.4`'s history panel is reading a row that can never
    have changed under it.

**Both halves were proved on PostgreSQL 16 rather than assumed** —
`10-scripts/p3_cancel_state_and_trigger_readback.py`, which is `P3.6` — because
`config/settings/test.py` hardcodes in-memory SQLite, which has neither the
trigger nor the CHECK, and a green suite says nothing here (hard-won law 14).

⚠ **WHAT THE FREEZE DOES *NOT* SHUT, STATED SO NOBODY READS MORE INTO IT THAN
IS THERE.** A cancelled row can still GAIN `deposit_batch_id` and
`journal_entry_id` once each, and its cheque number, memo and tender can still
be corrected — because those doors are open on every frozen status and
`cancelled` is not special. Neither is reachable in practice today (a cancel is
only possible before the money settles, and nothing banks or posts a payment
that never cleared), and narrowing them FOR ONE STATUS would mean editing the
trigger, which means moving hard rule 4's allow list, which is the one thing
`P3.8` exists to refuse. **The honest statement is: `cancelled` is exactly as
frozen as `failed` and `reversed`, no more and no less.**

═══════════════════════════════════════════════════════════════════════════════
⚠ THE `DEF-PAY-6207` QUESTION, ASKED OF THIS CONSTRAINT RATHER THAN ASSUMED
═══════════════════════════════════════════════════════════════════════════════
**A CHECK refuses a row only when its expression is FALSE and PASSES when the
expression is NULL** — `payments/0034`'s rule, and this file's brief asked for
the shape of `ck_payments_status` to be checked while altering it.

It is a single membership test, not an OR'd chain, so `0034`'s specific fault
(a branch comparing a nullable column to a literal, weakening the whole chain
to nothing) cannot occur here. But the NULL rule still applies:
`pg_get_constraintdef` renders it `CHECK ((status = ANY (ARRAY[…])))`, which is
**NULL for a NULL status, and would therefore PASS**.

**What actually holds that door shut is the COLUMN and not this constraint.**
`status` is `models.TextField(default=PAYMENT_PROCESSING)` with no `null=True`,
so PostgreSQL carries `attnotnull` on it and a NULL never reaches the
expression. That is stated here, and **read back from `pg_attribute` rather
than reasoned about**, in the readback's §1 — because a door held shut by
something other than the guard a reader is looking at is exactly the
arrangement that opens quietly when somebody makes the column nullable for an
unrelated reason.

**Adding `status IS NOT NULL` to the CHECK was considered and declined**: it
would make the constraint stricter, not weaker, so it is safe — but it would
duplicate a guarantee the column already gives, and hard-won law 5's shape
says one source of truth, not two that can drift. The assertion is a proof
instead.

═══════════════════════════════════════════════════════════════════════════════
NO DATA IS TOUCHED, WHICH IS WHY THERE IS NO `set_config` LOOP
═══════════════════════════════════════════════════════════════════════════════
Hard rule 1's trap — a migration UPDATE with `app.tenant_id` unset matches zero
rows and reports success — needs an UPDATE to bite, and this migration issues
none. **A widened CHECK admits a value; it does not write one.** No existing row
changes, so there is nothing to backfill and nothing to assert unstamped. The
first `cancelled` row in this product will be written by `P3.2`'s service,
through the ordinary tenant-scoped path, with an `audit_log` row beside it
(hard rule 7).

⚠ **AND THE CONSTRAINT SWAP IS SAFE ON A TABLE WITH ROWS IN IT, WHICH IS WORTH
ONE LINE.** `RemoveConstraint` then `AddConstraint` re-validates the new CHECK
against every existing row — and the new set is a strict SUPERSET of the old
one, so every row that passed the five passes the six. A validation failure
here would mean a row already held a word the old constraint refused, which is
impossible while the old constraint was in force.

═══════════════════════════════════════════════════════════════════════════════
THE REVERSE, AND WHY IT IS NOT A NO-OP
═══════════════════════════════════════════════════════════════════════════════
Unapplying restores the five-value CHECK **exactly**, and PostgreSQL will
REFUSE to do that if any row has already reached `cancelled` — the revalidation
fails, loudly, naming the constraint. That is the correct behaviour and it is
why the reverse is written rather than elided: a freeze must unapply to
precisely what came before it (hard-won law 3), and silently dropping the
constraint to make a rollback succeed would leave `payments.status` open to any
word at all on exactly the hosts that rolled back.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0035_cr136_p2_4_p2_5_p2_20_the_till_on_a_payment"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="payment",
            name="ck_payments_status",
        ),
        migrations.AddConstraint(
            model_name="payment",
            constraint=models.CheckConstraint(
                # Spelled out rather than importing `PAYMENT_STATUSES`, because
                # a migration records what the schema became on the day it ran.
                # A migration that read the live tuple would silently mean
                # something different the next time the tuple moved, which is
                # the whole reason `0033` restates a function body verbatim
                # instead of naming it.
                condition=models.Q(
                    status__in=(
                        "processing",
                        "cleared",
                        "failed",
                        "reversed",
                        "posted",
                        "cancelled",
                    )
                ),
                name="ck_payments_status",
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/change-requests/CR-137-BRC07-payments-phase-3-a-payment-has-an-address.md §3 P3.5 · 05-prototype/06 Payments Page Blueprint.pdf p19 (the task table) · CLAUDE.md hard rule 4 · hard-won laws 7 and 14 · apps/payments/migrations/0002_rls_w4_and_immutability.py (the trigger this value lands inside) · apps/payments/migrations/0034_def_pay_6207_null_safe_check_branches.py (the NULL rule)
# generated: 2026-09-23 by LANE P3-DB
# checklist: A✔ B=n/a(no screen — P3.9..P3.12 are another lane) C✔ D=n/a(a migration) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: PROVED RED FIRST on a PostgreSQL 16 clone at payments/0035 — `UPDATE payments SET status='cancelled'` refused BY NAME by `ck_payments_status`; GREEN at 0036 with the same statement accepted and the trigger refusing every following statement against that row. makemigrations --check clean · ruff clean · FORWARDS, BACKWARDS, FORWARDS AGAIN on that clone, with `pg_get_constraintdef` read back at each step rather than inferred from migration state
# exceptions:
#   E1 `cancelled` joins PAYMENT_FROZEN_STATUSES by DERIVATION and joins the trigger's frozen side by a LITERAL that never mentions it. Neither mechanism required an edit, so neither would have shown up in review as a decision. It is argued in the docstring above and proved in both directions rather than left to be noticed
#   E2 a cancelled row can still take the two write-once stamps and the three correctable references, exactly as `failed` and `reversed` can. Narrowing them for one status would mean moving hard rule 4's allow list, which `P3.8` refuses
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

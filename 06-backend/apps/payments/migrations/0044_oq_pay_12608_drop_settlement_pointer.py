# ── Trace ──────────────────────────────────────────────
# Question: OQ-PAY-12608 — CLOSED 2026-09-24, option (b). PO, verbatim:
#           *"p7 (b) — nothing is lost, and the payment-row lock stays exactly
#           as it is"*.
# Rules:    CLAUDE.md hard rule 4 (financial immutability, and its own
#           narrowing: *"`payments/0014` is the ONLY place the database's
#           allow list moves; widening it anywhere else is a new ruling, not
#           this one"*) · hard-won law 7 (prove a guard RED first) · hard-won
#           law 14 (the suite runs on SQLite, which installs no trigger)
# Change:   CR-139-BRC07 `P5.6` — the blueprint's pointer, withdrawn
# Tests:    06-backend/tests/test_cr139_p5_settlements.py
#           (`…_the_pointer_column_is_gone_and_stays_gone`, the standing
#           guard) · 06-backend/tests/test_cr139_p5_12_to_p5_15.py
# Impacts:  apps/payments/models.Payment · apps/payments/settlements.py
#           (SETTLEMENT_UNAVAILABLE's first entry + the module docstring) ·
#           apps/payments/settlements_read.py · apps/payments/
#           settlement_models.py · 10-scripts/
#           cr139_p5_6_pointer_freeze_proof.py (INVERTED — see below)
# ───────────────────────────────────────────────────────
"""payments 0044 — DROP `payments.settlement_id`, and nothing else.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path, and this one drops a
column from the product's most tightly frozen table). HUMAN-REVIEW-PENDING —
AI-authored 2026-09-24 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in
12-governance/09-human-review-ledger.md.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES, IN ONE SENTENCE
═══════════════════════════════════════════════════════════════════════════════
`payments.settlement_id` — built by `payments/0038`, **never writable, never
written, read by nothing** — is removed. `settlement_members` stays the one
record of which payments a payout holds.

═══════════════════════════════════════════════════════════════════════════════
WHY A COLUMN THE BLUEPRINT ASKED FOR IS BEING REMOVED
═══════════════════════════════════════════════════════════════════════════════
`P5.6` of the payments blueprint (p024) draws *"`payments.settlement_id` —
nullable. **Null is *Awaiting settlement***. The third state the requirement
never named, made real."* The column was built exactly as drawn.

**Nothing could ever write it.** `payments_payment_immutable()` compares a
payment's WHOLE ROW minus a short allow list, and `payments/0005`'s own comment
says *"a column added later is frozen the day it is created"*. The obvious
guess — that the freeze begins at clearing, so a payout arriving days later is
too late — is not what was measured: the **`processing`** branch names its
mutable set explicitly too (*"only status and cleared_at may change … plus the
cheque number, memo and tender"*), so `settlement_id` was settable **only at
INSERT**, and a payout by definition arrives after the row exists. There was no
window at any point in a payment's life.

That was measured on **PostgreSQL 16.13** before anything was written, by
`10-scripts/cr139_p5_6_pointer_freeze_proof.py`: a `processing` payment REFUSES
it, a `cleared` payment REFUSES it, and — the control that makes the finding
mean something — a `cleared` payment ACCEPTS `confirmation`, because that IS on
`payments/0014`'s allow list.

**Making it writable was not a lane's decision to take.** Hard rule 4 narrows
itself in terms, so the choice went to the Product Owner as `OQ-PAY-12608` with
three options: (a) widen the allow list, write-once, as `deposit_batch_id`
already is · (b) leave the lock alone and DELETE the column · (c) leave it
frozen and unwritten as a declared absence. **They chose (b).**

═══════════════════════════════════════════════════════════════════════════════
WHY NOTHING IS LOST — AND THIS IS A FACT, NOT A REASSURANCE
═══════════════════════════════════════════════════════════════════════════════
The pointer was a DENORMALISATION whose stated purpose was *"so the payments
list can print Awaiting settlement without a join"*. It never served that
purpose for one day, because it was never written, so **no read in this product
changes behaviour today.** `settlements.awaiting_settlement_filter()` already
answers the third state from `settlement_members`, and
`uq_settlement_members_payment` already says *a payment is in at most one
payout* — the same constraint the pointer would have carried, one table over
and with referential integrity the pointer did not have.

**What it costs, stated with the worked figure put to the PO:** at the top of
tier T5 a utility holds about **40,000 accounts**, and the payments list
filtered to *Awaiting settlement* reads through `settlement_members` instead of
a column. That is one extra join on a paged query (`NFR-3`), not a table scan.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS A ONE-LINE `RemoveField` AND TOUCHES NO TRIGGER
═══════════════════════════════════════════════════════════════════════════════
`payments_payment_immutable()` is written as `to_jsonb(OLD) - locked_columns`,
so it names no column of its own and enumerates nothing. A column leaving the
table leaves the trigger's comparison exactly as it was — **the payment-row
lock does not move**, which is the other half of what the PO ruled. Nothing is
redefined here, and `payments/0014` is still the only place the database's
allow list has ever moved.

═══════════════════════════════════════════════════════════════════════════════
THE ROLLBACK, STATED BEFORE SHIPPING
═══════════════════════════════════════════════════════════════════════════════
The reverse re-creates the column as `uuid NULL`. It is **safe and exact**: the
column held NULL on every row in every tenant when it was dropped — it had no
writer — so a re-created all-NULL column is byte-for-byte the state that was
removed, and no data can be lost by going either way. This is the rare 🔒
migration whose reverse restores the world completely, and it is worth saying
so plainly because most do not (`customers/0069`'s reverse, three days old,
cannot be run once a property has been sold twice).

**What a rollback does NOT restore is the ruling.** Re-creating the column
re-creates a field nothing can write; the reason it went is in `OQ-PAY-12608`
and in the decision log of 2026-09-24, not in this file's ability to undo
itself.

═══════════════════════════════════════════════════════════════════════════════
THE PROOF SCRIPT IS INVERTED RATHER THAN DELETED, AND THE REASON IS WORTH A LINE
═══════════════════════════════════════════════════════════════════════════════
`10-scripts/cr139_p5_6_pointer_freeze_proof.py` probed the live column on
PostgreSQL and printed `FAIL: payments.settlement_id does not exist — run
payments/0038 first.` when it could not find it. After this migration that
would be the ONLY line it could ever print: a check that can only fail, over a
column the PO ruled away — hard-won law 7's *incapable of passing* shape, which
that same script's own docstring warns about.

**Deleting it was the first plan and it was wrong**, for a reason that only
showed up on a grep: the script is cited from six live places, one of them a
row in `12-governance/09-human-review-ledger.md`, **which may not be edited**
(the register guard reads a changed line as a deletion). Deleting the file
would have left six citations pointing at nothing and no lawful way to fix one
of them.

So the VERDICT is inverted and the reasoning is kept whole: the column's
ABSENCE is now the pass, its PRESENCE means this database predates
`payments/0044` and the three original probes still run and still report the
finding. **It can still fail, on the thing that would matter — the pointer
coming back.**

**The guard that runs in every suite on every machine** is
`test_cr139_p5_6_the_pointer_column_is_gone_and_stays_gone`, because a column
being absent is a schema fact and needs no trigger to observe — which is
precisely why the ORIGINAL finding needed PostgreSQL and this one does not.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0043_cr141_correctable_refund_check_number"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="payment",
            name="settlement_id",
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: OQ-PAY-12608 (CLOSED 2026-09-24, option (b)) · CR-139-BRC07 `P5.6` ·
#   payments/0005 (the freeze this does NOT touch) · payments/0038 (the
#   migration that added the column) · decision log 2026-09-24
# generated: 2026-09-24 by LANE RULINGS-0924
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=pending(🔒 HUMAN-REVIEW-PENDING)
# gates: makemigrations --check · migrate forwards and backwards on PostgreSQL
#   16 · the whole settlements suite on PostgreSQL after the drop
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

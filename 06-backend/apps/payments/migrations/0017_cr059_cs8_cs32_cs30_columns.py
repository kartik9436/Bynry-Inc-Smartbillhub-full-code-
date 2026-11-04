# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-8 (move money between two accounts) · CS-32 (move a
#           payment to the account it belonged to) · CS-30 (give a cheque a
#           state of its own). Screens: S21 · S22 · S33 · S35 · S58
# Rules:    CLAUDE.md hard rule 4 (financial immutability — every column here
#           is written at INSERT and never updated, so `payments/0014`'s
#           three-column UPDATE allow list does NOT move for any of them) ·
#           hard rule 1 (tenant scoping — `payments` already carries RLS FORCE
#           from `payments/0002` and adding columns does not touch a policy) ·
#           BR-PAY-865 (a moved payment is a reversal plus a linked new
#           payment) · BR-PAY-883 (a post-dated cheque is held out of the cut)
# Ruling:   CR-059 §8 CS-30, PO 2026-09-01.
# Tests:    06-backend/tests/test_cr059_cs8_transfer.py ·
#           06-backend/tests/test_cr059_cs32_move_payment.py ·
#           06-backend/tests/test_cr059_cs30_cheques.py
# ───────────────────────────────────────────────────────
"""payments 0017 — four nullable columns, no constraint moved, no trigger touched.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path and `payments` is the
money table). HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling
of 2026-08-09 (*"AI will do it; we will review it later as human"*).

WHAT IT ADDS, AND WHY EACH IS A COLUMN RATHER THAN SOMETHING ELSE
=================================================================

``moved_from_payment_id``  (CS-8 + CS-32, ONE column for both)
    CS-32's data note in its own words: *"One nullable column on `payments`
    linking a moved payment to the one it came from. No change to any signed
    contract."* CS-8's credit transfer needs the identical link between its two
    legs, and building a second column for the same fact is how two rows come to
    disagree about one movement. So there is one, and it always means the same
    thing read from the RECEIVING side: **this money was on another account a
    moment ago, and that row is where it was.**

    It is a self-FK with ``on_delete=PROTECT`` like ``reverses_payment_id``
    beside it — not because a payment can be deleted (the trigger refuses DELETE
    in every status) but because the two columns should fail the same way if the
    guarantee under them ever changed.

``cheque_date`` · ``drawer_bank``  (CS-30)
    CS-30's first rule: a cheque carries *"its number, its date and its drawer
    bank as structured fields"*. **The NUMBER is not here and its absence is the
    considered half.** ``payments.confirmation`` already holds it and is one of
    the exactly three columns the PO opened to correction on 2026-09-02
    (`payments/0014`), so a mistyped cheque number is fixable through
    ``POST /payments/{id}/correct-reference`` today. A fourth column holding the
    number would hold a number nobody could ever correct — which is the defect
    CS-34 exists to remove, rebuilt one column along.

``bankable_from``  (CS-30's fourth rule)
    *"A cheque dated in the future is held out of the batch cut until its date,
    and named on the day it becomes bankable."* NULL means bankable now, which is
    every other tender and every cheque handed over dated today or earlier.

WHAT THIS MIGRATION DELIBERATELY DOES **NOT** DO
================================================

* **It does not widen the UPDATE allow list, and it does not need to.** Every
  column above is written by the INSERT that creates its row. `payments/0002`'s
  trigger compares whole rows minus a constant allow list, *"so a column added
  later is frozen the day it is created rather than the day somebody remembers
  to add it here"* — which is exactly the behaviour these four want. A void, a
  hold and a move are all NEW ROWS or a lawful ``processing → failed`` status
  move; none of them edits a column of a row that already stands.
* **It adds no `voided_at` column**, and that is CS-30 honoured rather than
  trimmed. A cheque *"not yet banked"* is a `processing` payment — the money has
  not arrived, nothing has posted — and `payments/0002` already lets a
  processing row move its ``status``. So a void at the counter is
  ``processing → failed`` plus its audit row, which needs no column, no trigger
  change and no narrowing of hard rule 4. A ``voided_at`` column would have
  needed all three, for a fact the status already carries.
* **It adds no unique index on the cheque number.** CS-30 asks for a number
  *"unique per utility"* and a database index cannot express that soundly here:
  the predicate would have to exclude a cheque whose earlier row has been
  REVERSED, and *"has this row been reversed"* lives in another row. Worked: this
  same CR's CS-32 move re-records cheque #8842 on the correct account while the
  original row stays `cleared`, so a `(tenant, confirmation)` index would refuse
  a correction the product is being built to make. The duplicate check is
  therefore in `apps/payments/cheques.py`, where it can say *"cheque 8842 from
  First National is already recorded as PMT-…"* and can exempt a reversed one.
  Recorded in `12-governance/02-decision-log.md` rather than left as a silence.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0016_rls_cr060_t7d_allocation_classes"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="moved_from_payment",
            field=models.ForeignKey(
                blank=True,
                db_column="moved_from_payment_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="moved_to",
                to="payments.payment",
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="cheque_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="drawer_bank",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="bankable_from",
            field=models.DateField(blank=True, null=True),
        ),
        # ── the two reads these columns exist for ───────────────────────────
        # S21's *"moved to / moved from"* pair walks the link from the SOURCE
        # side, which is the direction the FK does not index for free.
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["tenant", "moved_from_payment"], name="ix_payments_moved_from"
            ),
        ),
        # The batch cut asks *"which cheques may be banked on this day"* on
        # every cut, and S37's post-dated list asks the complement. Without it
        # both are a sequential scan of every payment the tenant has ever taken.
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(fields=["tenant", "bankable_from"], name="ix_payments_bankable"),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-059 §8 CS-8 · CS-30 · CS-32 · §0d.1 · apps/payments/models.py ·
#         apps/payments/migrations/0002 (the immutability trigger this does not
#         touch) · apps/payments/migrations/0014 (the three-column allow list
#         this does not widen)
# generated: 2026-09-03 by the CR-059 payments cross-account lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — CR-059 tasks 32/40/57)
#            F✔ G✔ H=deferred(PO 2026-08-09)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

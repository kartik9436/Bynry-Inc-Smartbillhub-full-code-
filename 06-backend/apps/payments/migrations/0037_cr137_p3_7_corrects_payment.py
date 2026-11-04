# ── Trace ──────────────────────────────────────────────
# Change:  CR-137-BRC07 · P3.7 — "`payments.corrects_payment_id` — a self FK,
#          the mirror of `reverses_payment`", outcome *"An adjustment names
#          what it corrects instead of being related only in a clerk's
#          memory."* (payments blueprint p19)
# Story:   no story — a blueprint task. The service that WRITES it is phase 3's
#          correction path and is another lane's; this is the column it writes
#          into, and it lands first on purpose.
# Rules:   CLAUDE.md hard rule 4 (financial immutability — this column is
#          written at INSERT and never UPDATEd, so the allow list does not move
#          for it; `P3.8` is the guard) · hard rule 1 (tenant scoping — no data
#          is touched here) · BR-PAY-002 · hard-won law 14
# Tests:   `P3.15` (a correction leaves the original byte-identical and
#          `corrects_payment_id` points at it) is another lane's ·
#          10-scripts/p3_cancel_state_and_trigger_readback.py proves the
#          freeze the column lands inside
# Impacts: apps/payments/models.Payment (+1 nullable column, +1 index) ·
#          NO trigger, NO allow list, NO constraint on an existing column and
#          NO data
# ───────────────────────────────────────────────────────
"""payments 0037 — `corrects_payment_id`, and an index for the walk back.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-09-23 under the PO ruling
of 2026-08-09. Migration ordering is a CLAUDE.md 🔒 sensitive path, so there is
a row in `12-governance/09-human-review-ledger.md`.

═══════════════════════════════════════════════════════════════════════════════
WHAT CHANGES
═══════════════════════════════════════════════════════════════════════════════
One nullable self-FK on `payments`, and one index over `(tenant_id,
corrects_payment_id)`. **No trigger is touched, no allow list moves, no
existing column changes and no row is written.**

`corrects_payment` is `reverses_payment`'s declaration verbatim — `"self"`,
`on_delete=PROTECT`, `null=True`, `blank=True`, `db_column` spelled out, a
plural `related_name` — which is what the task asked for in the words *"the
mirror of `reverses_payment`"*.

`PROTECT` is the half worth naming, because it is the one that has teeth:
deleting a payment that something corrects would be refused by Django before
the database ever saw it — and the database refuses the DELETE anyway, in every
status, through `trg_payment_immutable`. Two guards on one fact, which is the
arrangement this module already keeps for a reversal's total.

═══════════════════════════════════════════════════════════════════════════════
⚠ WHERE THE MIRROR STOPS, AND IT IS ONE PLACE
═══════════════════════════════════════════════════════════════════════════════
`reverses_payment` carries `uq_payments_full_reverses` — a partial UNIQUE index
that makes a payment fully reversed **at most once**. **`corrects_payment`
carries no unique constraint at all, on purpose.** `payments/0014`'s own
reasoning, quoted because it is the argument: *"a clerk who mistypes twice must
be able to correct twice; a write-once reference would make the second typo
permanent, which is the very failure CS-34 was written about."*

So a payment is reversed once and may be corrected any number of times, and
copying the unique index across "for symmetry" would have quietly re-created
the failure `CR-059` CS-34 was written to remove.

═══════════════════════════════════════════════════════════════════════════════
WHY AN INDEX, SINCE THE TASK ASKS FOR THE REASONING RATHER THAN THE ANSWER
═══════════════════════════════════════════════════════════════════════════════
**Yes, and it is `(tenant, corrects_payment)` rather than the plain FK index
Django gives for free.** Three reasons, in the order they decide it:

  1. **THE READ EXISTS AND RUNS FROM THE OTHER END.** The question is *"what
     corrects this payment?"*, asked from the CORRECTED payment's own page —
     `P3.1`'s `GET /payments/{id}` and `P3.4`'s history panel. That walks the
     FK from the side it does not index for free. This is not a hypothetical
     future read; it is the outcome line of `P3.7` itself.
  2. **EVERY READ ON THIS TABLE IS TENANT-SCOPED, SO TENANT LEADS.** RLS scopes
     every statement and the tenant is always known, which is why every index
     on `payments` already leads with it. `ix_payments_moved_from` and
     `ix_payments_tender` are the same judgment, for the same shape of link,
     recorded in the same words: *"the direction the FK does not index for
     free."* This is the third instance of one pattern, not a new opinion.
  3. **THERE IS NO UNIQUE CONSTRAINT TO LEAN ON.** The reversal walk gets an
     index as a side effect of `uq_payments_full_reverses`. A correction has
     none (above), so without this line the question is a sequential scan of
     every payment the tenant has ever taken. `NFR-3`/`NFR-5` put the largest
     modelled tenant at **40,000 accounts** with no cap above it, and a
     sequential scan of a payments table at that size is exactly the shape the
     T4/T3 flexibility instruction forbids adding.

**The cost of being wrong here is small and asymmetric**, which is the honest
closing argument: an index nobody reads costs a few bytes per row and one more
entry to maintain per INSERT; a missing index on a detail page's own read costs
a scan on every open, and is found by a customer rather than by us.

═══════════════════════════════════════════════════════════════════════════════
NO DATA IS TOUCHED, SO THERE IS NO `set_config` LOOP (hard rule 1)
═══════════════════════════════════════════════════════════════════════════════
The trap — a migration UPDATE with `app.tenant_id` unset matches zero rows and
reports success — needs an UPDATE to bite, and this migration issues none. The
column is born NULL on all 74 existing payments in the sample tenant and on
every real row, which is the truthful value: none of them corrects anything.
Nothing to backfill, nothing to assert unstamped.

═══════════════════════════════════════════════════════════════════════════════
⚠ AND THE COLUMN IS FROZEN FROM THE INSTANT IT EXISTS, WITH NO EDIT ANYWHERE
═══════════════════════════════════════════════════════════════════════════════
`trg_payment_immutable` compares **whole rows minus a short allow list**, so a
column added today is frozen today — `payments/0002` says so in as many words:
*"A column added to `payments` next month is frozen on the day it is created,
with no edit here and no chance of anybody forgetting."* `corrects_payment_id`
is absent from both `mutable` and `stamps`, so it is written at INSERT and can
never be moved afterwards. **That is the reason this migration does not go near
`payments/0014`, and `P3.8` is the check that keeps it that way.**
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0036_cr137_p3_5_cancelled_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="corrects_payment",
            field=models.ForeignKey(
                blank=True,
                db_column="corrects_payment_id",
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="corrections",
                to="payments.payment",
            ),
        ),
        migrations.AddIndex(
            model_name="payment",
            index=models.Index(
                fields=["tenant", "corrects_payment"], name="ix_payments_corrects"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: 12-governance/change-requests/CR-137-BRC07-payments-phase-3-a-payment-has-an-address.md §3 P3.7 · 05-prototype/06 Payments Page Blueprint.pdf p19 · apps/payments/migrations/0014_cr059_cs34_amendable_reference.py (why there is no unique constraint) · apps/payments/migrations/0017_cr059_cs8_cs32_cs30_columns.py (`moved_from_payment`, the index this mirrors) · CLAUDE.md hard rule 4 · NFR-3 / NFR-5
# generated: 2026-09-23 by LANE P3-DB
# checklist: A✔ B=n/a(no screen — P3.9..P3.12 are another lane) C✔ D=n/a(a migration) E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check clean · ruff clean · applied to a LIVE PostgreSQL 16 clone, then FORWARDS, BACKWARDS, FORWARDS AGAIN with the column and the index read back from `pg_attribute` and `pg_indexes` at each step rather than inferred from migration state. The column's freeze is proved by `10-scripts/p3_cancel_state_and_trigger_readback.py` §6, which refuses a fourth column by name and reads the two allow-list arrays back out of the deployed function body
# exceptions:
#   E1 the mirror of `reverses_payment` stops at `uq_payments_full_reverses`, deliberately: a payment is reversed once and may be corrected repeatedly (`payments/0014`). Copying the unique index across would have re-created the failure CS-34 was written to remove
#   E2 the index is a judgment, not a measurement. It is the same judgment `ix_payments_moved_from` and `ix_payments_tender` already record for the same shape of link, and the docstring argues it rather than asserting it
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

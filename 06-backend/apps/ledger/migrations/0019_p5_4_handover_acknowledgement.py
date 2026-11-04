"""ledger 0019 — **a handover gets an answer, not just a send.**

Finance blueprint `P5.4` (p018). Its reference is `finance.export.noAckStatus`,
a string the screen has been rendering as a stated absence since it shipped:
*"Nothing reports back whether the accounting package accepted it, so no
acceptance status is shown."* `export_batches` recorded WHO sent WHAT and WHEN,
in full — and then the handover ended and nobody could say whether it landed.

═══════════════════════════════════════════════════════════════════════════
1 · A RECORDED ANSWER, NOT A LIVE ONE — AND THAT IS THE DESIGN
═══════════════════════════════════════════════════════════════════════════
`BR-LED-020` makes v1 a FILE/batch handover and direct connect v2, so there is
no callback to listen for and no status to poll. What closes the loop today is a
PERSON: the accountant imports the file, says whether it took, and a clerk
records that against the batch. **Inventing a live status would be three green
`Connected` chips over nothing**, which is `DEF-007` and which
`CloseExportPage.tsx` already refuses by name.

═══════════════════════════════════════════════════════════════════════════
2 · THREE STATES AND NO `pending` — NULL IS THE FOURTH AND MOST COMMON
═══════════════════════════════════════════════════════════════════════════
`accepted` · `rejected` · `partial`. A batch nobody has answered for carries
`ack_state = NULL`, and **that is a different fact from *the import is in
progress***. `DEF-127` is this register's own record of what it costs to spell
*nobody looked* and *the answer is no* the same way, and the CHECK below admits
NULL for exactly that reason.

`partial` is there because it is the answer that actually arrives: the package
refuses the two lines whose account codes it does not recognise and takes the
other thirty. Neither accepted nor rejected, and the case a finance officer most
needs to see.

═══════════════════════════════════════════════════════════════════════════
3 · EVERY COLUMN IS NULLABLE AND NOTHING IS BACKFILLED
═══════════════════════════════════════════════════════════════════════════
Every batch this product has ever recorded was sent with no answer, and there is
no honest value to put on one now. A `DEFAULT` of any kind would be this
migration asserting something about history it cannot know — and on a money path
that assertion would read as a fact on a screen.

⚠ **`ack_at` IS AN INPUT, NEVER A CLOCK READ** (`BR-TEN-043`). The import
happened when it happened and a clerk may be recording it a day later; stamping
`now()` would put our clock on their event.

⚠ **`ack_by_user_id` IS NOT `created_by_user_id`.** The person who sent the
batch and the person who heard back are routinely different people, and keeping
them apart is the entire point of a second column.

⚠ **THIS DOES NOT WIDEN HARD RULE 4.** `export_batches` is not one of the four
tables that rule names — it is a RECORD OF A HANDOVER, not an invoice, an
invoice line, a payment or a journal entry — and nothing about the books, the
payload or the content hash moves. The batch's own immutability (`BR-LED-004`'s
one recorded idempotent handover per period and target) is untouched: what is
being recorded is what somebody ELSE did with it afterwards.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ledger", "0018_p0_7_currency_has_no_default"),
        ("tenancy", "0051_p5_11_supplier_invoice_document"),
    ]

    operations = [
        migrations.AddField(
            model_name="exportbatch",
            name="ack_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exportbatch",
            name="ack_by_user_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exportbatch",
            name="ack_note",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exportbatch",
            name="ack_reference",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="exportbatch",
            name="ack_state",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="exportbatch",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("ack_state__in", ("accepted", "rejected", "partial")),
                    ("ack_state__isnull", True),
                    _connector="OR",
                ),
                name="ck_export_batches_ack_state",
            ),
        ),
    ]

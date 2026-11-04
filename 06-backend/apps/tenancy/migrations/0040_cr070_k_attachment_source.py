"""tenancy 0040 — an eighth source type, because nine photographs are not nine bills.

`CR-070` wave K · `US-WRK-049` TC-3 · `BR-WRK-047`.

WHY THIS EXISTS, AND IT IS A DESIGN COLLISION RATHER THAN AN OVERSIGHT
────────────────────────────────────────────────────────────────────────────
`0039` gave work-order evidence the source type `work_order`, which was the
obvious reading: a photograph belongs to a job. The **second** photograph on
one job is then refused by the database, and the constraint that refuses it is
correct and should not move:

    uq_stored_documents_stored  (tenant, source_type, source_id, content_type)

Its own docstring gives the reason, and the reason is about RENDERINGS:

    *"If one source could carry two artefacts of the same shape, 'serve the
    frozen copy' would have to CHOOSE one — and a chooser is a re-render
    wearing a different coat. `content_type` is in the key because a bill
    legitimately stores a PDF and an HTML of the same document: two
    representations of one thing, not two documents."*

That is exactly right about a bill, and it simply does not describe a job's
photographs. Nine pictures of a meter cupboard are not nine renderings of the
work order — they are nine independent facts that happen to share a job, all
`image/jpeg`. There is no "the frozen copy" to choose between, because none of
them is a copy of the order at all.

⚠ **SO THE CONSTRAINT IS NOT WIDENED, AND THAT IS THE WHOLE POINT OF THIS
FILE.** Widening it to accommodate Work would weaken a real guarantee on
`invoices` for every other module — the one that makes *serve the frozen copy*
mean something on a legal document. The thing that was wrong was the SOURCE,
not the rule.

WHAT CHANGES
────────────────────────────────────────────────────────────────────────────
`ck_stored_documents_source` goes 7 → 8 with `work_order_attachment`. A
photograph's `source_id` is its own `work_order_attachments.id`, which is
trivially unique and honest about what the document is a copy of: itself.

The ORDER is not lost and never was — `work_order_attachments` is the table
that says which job a photograph belongs to, which is its entire job. `Work-033`
lists a job's evidence from that table, not from `for_source`.

⚠ **THE SIGNATURE AND THE REPORT STAY ON `work_order`.** There is exactly one
signature per order, and report versions differ by `content_type`, so neither
collides. This value is for photographs and nothing else, and a lane reaching
for the nearest-sounding source should read that sentence before using it.

HOW IT WAS FOUND, BECAUSE THAT IS THE USEFUL PART
────────────────────────────────────────────────────────────────────────────
`US-WRK-049` TC-3 — *an optional missing photograph does not stop the close* —
uploads a photograph to two different readings on one order. It is not a test
about uniqueness at all. Nothing in the wave's own specification would have
caught this, and no gate reads a constraint against an intended access pattern;
the first place it could have surfaced in production is a technician's SECOND
photograph of the day, on the first real job.

REVERSIBLE, AND THE REVERSAL REFUSES OVER LIVE ROWS
────────────────────────────────────────────────────────────────────────────
Same shape as `0039`, same reason: `0026`'s write-once trigger means a row the
restored constraint forbids could be neither edited nor deleted to make room.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored under the PO ruling of 2026-08-09; the deferred
human review is its row in `12-governance/09-human-review-ledger.md`
(`DEF-GOV-8547`).
"""

from django.db import migrations, models

SOURCES_BEFORE = (
    "invoice",
    "outbound_message",
    "payment",
    "payment_plan",
    "customer_account",
    "import_batch",
    "work_order",
)

NEW_SOURCES = ("work_order_attachment",)

SOURCES_AFTER = SOURCES_BEFORE + NEW_SOURCES


def refuse_rollback_over_live_rows(apps, schema_editor):
    """Refuse to roll back while any row carries the new source type."""
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(source_type__in=NEW_SOURCES).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0040: {stuck} stored_documents row(s) already "
            f"carry source_type {NEW_SOURCES[0]!r}. Restoring the seven-value constraint "
            "would leave rows the CHECK forbids, and tenancy/0026's write-once trigger "
            "means they could be neither edited nor deleted to make room."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0039_cr070_k_work_document_kinds")]

    operations = [
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_source",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(source_type__in=SOURCES_AFTER),
                name="ck_stored_documents_source",
            ),
        ),
        # ⚠ DEF-TEN-9655 (2026-10-04, lane CREWS-2): the refusal is the LAST
        # operation, so it is the FIRST to run on the way back. Django reverses
        # operations; placed first it ran after the narrower CHECK had been
        # restored and the rollback failed on a raw IntegrityError instead of
        # the counted sentence. Forward it is a no-op, so nothing forward moved.
        migrations.RunPython(
            migrations.RunPython.noop,
            refuse_rollback_over_live_rows,
        ),
    ]

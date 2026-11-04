"""tenancy 0044 — a ninth source type, because a lease is not a rendering of an account.
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-12 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

`CR-094-BRC01` wave I · `ACC-S8` · `BR-CUS-036`.

WHY THIS EXISTS, AND IT IS `0040` ONE MODULE ACROSS
────────────────────────────────────────────────────────────────────────────
`SOURCE_CUSTOMER_ACCOUNT` has named *"account documents, certificates"* since
`0025`, and it is the obvious reading: a document filed on an account belongs to
the account. The **second** document on one account is then refused by the
database, and the constraint that refuses it is correct and must not move:

    uq_stored_documents_filed  (tenant, source_type, source_id, content_type)
                               WHERE channel IS NULL

Its own docstring gives the reason, and the reason is about RENDERINGS:

    *"If one source could carry two artefacts of the same shape, 'serve the
    frozen copy' would have to CHOOSE one — and a chooser is a re-render
    wearing a different coat."*

That is exactly right about a bill, and it does not describe a filing cabinet.
A signed lease, a scan of a driver's licence and a landlord's letter are three
`application/pdf`s on one account and **none of them is a copy of the account**,
so there is no "the frozen copy" to choose between.

⚠ **SO THE CONSTRAINT IS NOT WIDENED.** Widening it would weaken a real
guarantee on `invoices` for every other module. The thing that is wrong for this
case is the SOURCE, not the rule — which is the finding `tenancy/0040` already
recorded for a technician's ninth photograph, and this migration is that finding
applied a second time rather than rediscovered.

WHAT CHANGES
────────────────────────────────────────────────────────────────────────────
`ck_stored_documents_source` goes 8 → 9 with `account_document`. A filed
document's `source_id` is its own `customers.account_documents.id`, which is
trivially unique and honest about what the document is a copy of: itself. The
ACCOUNT is not lost and never was — `account_documents` is the table that says
which account a file belongs to, which is its entire job, and `ACC-T10` lists a
tab from that table rather than from `for_source`.

⚠ **`SOURCE_CUSTOMER_ACCOUNT` IS NOT RETIRED.** It still carries the exemption
certificate (`BR-CUS-063`), of which there is one per account per authority, so
it does not collide. Retiring a value read by nothing is a different job with
its own grep-for-the-consumers discipline (hard rule 8's closing lesson).

REVERSIBLE, AND THE REVERSAL REFUSES OVER LIVE ROWS
────────────────────────────────────────────────────────────────────────────
Same shape as `0039` and `0040`, same reason: `0026`'s write-once trigger means
a row the restored constraint forbids could be neither edited nor deleted to
make room.
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
    "work_order_attachment",
)

NEW_SOURCES = ("account_document",)

SOURCES_AFTER = SOURCES_BEFORE + NEW_SOURCES


def refuse_rollback_over_live_rows(apps, schema_editor):
    """Refuse to roll back while any row carries the new source type."""
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(source_type__in=NEW_SOURCES).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0044: {stuck} stored_documents row(s) already "
            f"carry source_type {NEW_SOURCES[0]!r}. Restoring the eight-value constraint "
            "would leave rows the CHECK forbids, and tenancy/0026's write-once trigger "
            "means they could be neither edited nor deleted to make room."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0043_cr080_thermal_capacity_basis")]

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

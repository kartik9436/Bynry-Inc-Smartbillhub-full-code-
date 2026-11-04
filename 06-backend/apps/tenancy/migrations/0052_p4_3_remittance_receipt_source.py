"""tenancy 0052 — **a tax filing can keep the receipt an auditor asks for.**

Finance blueprint `P4.3` (p017, and p060 item 2 — the `Receipt` field drawn on
4·2 *Record a payment*). `BR-LED-019` has required the attachment since it was
confirmed, and the form **refused it by name**:

    a remittance RECEIPT FILE cannot be stored: BR-LED-019 requires one and
    `tax_remittances` (B2 Addendum r13 #3) is not in the schema, so there is no
    attachment column and no storage seam. Refused rather than accepted and
    dropped — a clerk who attaches a receipt believes it was kept.

That refusal was correct and it is now unnecessary. `ledger/0020` builds the
filing register, and this makes the receipt storable against it.

═══════════════════════════════════════════════════════════════════════════
1 · ONE NAME. THE KIND ALREADY EXISTS
═══════════════════════════════════════════════════════════════════════════
⚠ **`remittance_receipt` HAS BEEN IN `DOCUMENT_KINDS` SINCE `CR-049`** — it is
in `tenancy/0040`'s constraint list, with `BR-LED-019` written beside it in
`document_models.py`. What was missing was the SOURCE: nothing said what such a
document belongs TO, because the thing it belongs to did not exist.

So this migration adds **one value**, `tax_remittance`, to
`ck_stored_documents_source`, and nothing else. The kind's constraint is not
touched.

═══════════════════════════════════════════════════════════════════════════
2 · `tax_remittances` GAINS NO COLUMN, AND THAT IS THE POINT
═══════════════════════════════════════════════════════════════════════════
`tenancy/0051` settled this shape for the supplier invoice and it is followed
rather than re-argued: a document is found by WHAT IT BELONGS TO —
`stored_documents.source_type` + `source_id`. A `receipt_document_id` column on
the register would be a second place one fact lives, it would hold ONE document
where a filing can have several (the receipt, the return, the authority's
acknowledgement), and the two would be free to disagree the first time one was
removed. `for_source()` answers the question without it.

⚠ **AND THE REGISTER IS APPEND-ONLY** (`ledger/0020`), so a column would have
been worse than redundant: attaching a second document later would have needed
an UPDATE the triggers refuse.

═══════════════════════════════════════════════════════════════════════════
3 · WHAT IS ALREADY TRUE, VERIFIED AT SOURCE RATHER THAN ASSUMED
═══════════════════════════════════════════════════════════════════════════
Read out of the code rather than out of a brief (hard-won law 1):

  * **10 MiB**, `customers.account_documents.MAX_UPLOAD_BYTES` — `10 * 1024 *
    1024`, and `BR-SHL-031`'s *"10MB tenant-config"* with the tenant half not
    built;
  * **PDF · PNG · JPG · CSV**, seven media-type spellings, because a browser
    sends `image/jpeg`, some scanners send `image/jpg` and Excel sends
    `application/vnd.ms-excel` for a file a person calls a CSV;
  * **write-once**, `tenancy/0026`'s trigger;
  * **seven years**, `document_storage.retention_years()`, on a bucket with
    Object Lock `COMPLIANCE` (`NFR-35`);
  * **tenant-scoped**, RLS from `tenancy/0025` — a cross-tenant read answers
    `document_not_stored`, indistinguishable from never having existed.

⚠ **THE CAP AND THE ALLOWLIST ARE ENFORCED BY THE UPLOAD PATH, NOT BY
`document_store.store()`.** `store()` refuses an empty payload, a missing
content type and an unknown kind or source, and it does **not** measure bytes or
check the media type — `account_documents.py` does, at its own endpoint. So the
remittance endpoint enforces them itself, against the same two constants, rather
than assuming the store will.

═══════════════════════════════════════════════════════════════════════════
4 · `RemoveConstraint` + `AddConstraint`, AND THE ROLLBACK REFUSES OVER ROWS
═══════════════════════════════════════════════════════════════════════════
Same shape as `0051`, for the same two reasons: Django's own operations keep the
migration state and the database in step where raw SQL would not, and a rollback
that restored the narrower CHECK over rows carrying the new value would strand
them — `tenancy/0026`'s write-once trigger means such a row can be neither
edited nor deleted to make room. So the backwards direction REFUSES with a count
instead of failing halfway.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored under the PO ruling of 2026-08-09; the deferred
human review is its row in `12-governance/09-human-review-ledger.md`
(`DEF-GOV-8547`).
"""

from django.db import migrations, models

#: The one value this migration adds. Written out rather than imported from
#: `document_models`, because a migration must describe the world AT ITS OWN
#: MOMENT: importing the live tuple would make this file's meaning change the
#: next time somebody appends a source, which is the whole reason migrations are
#: append-only.
NEW_SOURCES = ("tax_remittance",)

#: ⚠ **THE ORDER IS THE MODEL'S OWN, NOT ALPHABETICAL AND NOT TIDIED.** A
#: `CheckConstraint`'s `__in` is compared BY SEQUENCE when Django decides
#: whether the database matches the models, so a re-ordered tuple here reads as
#: a pending migration for ever — `0051` records `makemigrations --check` saying
#: so before it was corrected.
SOURCES_AFTER = (
    "invoice",
    "outbound_message",
    "payment",
    "payment_plan",
    "customer_account",
    "import_batch",
    "work_order",
    "work_order_attachment",
    "account_document",
    "service_request_document",
    "supplier_invoice",
    *NEW_SOURCES,
)


def refuse_rollback_over_live_rows(apps, schema_editor):
    """A rollback with rows already carrying the new value would STRAND them.

    `tenancy/0026`'s write-once trigger is why this is a refusal and not a
    warning: a row the restored constraint forbids cannot be updated or deleted
    to make room, so the rollback would leave the table permanently in breach of
    its own CHECK.
    """
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(source_type__in=NEW_SOURCES).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0052: {stuck} stored_documents row(s) already "
            f"carry source_type {', '.join(NEW_SOURCES)}. Restoring the 11-value constraint "
            "would leave rows the CHECK forbids, and tenancy/0026's write-once trigger means "
            "they could be neither edited nor deleted to make room. Remove the filings' "
            "receipts first, or stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly rather than inferred. `0051` is the
        # latest tenancy migration at the time of writing.
        ("tenancy", "0051_p5_11_supplier_invoice_document"),
    ]

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

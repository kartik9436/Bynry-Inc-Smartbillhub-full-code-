"""tenancy 0051 — **a captured purchase can carry the supplier's own invoice.**

Finance blueprint `P5.11` (p064, screen 5·3a *Capture*). `supplier_invoices` has
21 columns and not one of them holds a document, so a purchase carried the
supplier's name and a free-text `reference` while the PDF that settles the
argument lived in somebody's inbox — and 5·2 *Bought vs billed* argues about a
supplier's figure with no way to open the document that decides it.

═══════════════════════════════════════════════════════════════════════════
1 · THIS IS TWO NAMES AND A CONSTRAINT, NOT A SPIKE — AND THE BLUEPRINT SAYS
    OTHERWISE
═══════════════════════════════════════════════════════════════════════════
p018 sizes `P5.11` as a SPIKE because *"the platform has no general attachment
store at all"*, and p064 calls it *"the platform's first general attachment"*.
**Both sentences are false and were when they were written** (`DEF-LED-6527`,
PO 2026-09-24: *"we have in bill/invoices and in accounts we hve created it -
you need to see th compoent"*).

`apps/tenancy/document_store.py` has existed since `CR-049`, with six calling
modules and three live capture screens. **Four of the five things the blueprint
said this task would bring are already built** — storage (S3, Object Lock
`COMPLIANCE`, fail-closed), tenant-scoped access (RLS; a cross-tenant read
answers `document_not_stored`, indistinguishable from never existed), a 10 MB
cap and a PDF/PNG/JPG/CSV allowlist — and **virus posture is RULED AWAY**, twice
(PO 2026-09-23, `DEF-SHL-6347`). So the whole cost of the data half is the two
values below.

═══════════════════════════════════════════════════════════════════════════
2 · `supplier_invoices` GAINS NO COLUMN, AND THAT IS THE POINT
═══════════════════════════════════════════════════════════════════════════
A document is found by WHAT IT BELONGS TO — `stored_documents.source_type` +
`source_id` — which is how a bill, a receipt, a work order's photographs and a
service request's paperwork are all already found. A `document_id` column on
`supplier_invoices` would be a second place the same fact lives, it would hold
ONE document where a purchase can have several (the invoice, the delivery note,
the credit), and the two would be free to disagree the first time one was
deleted. `for_source()` answers the question without it.

═══════════════════════════════════════════════════════════════════════════
3 · RETENTION IS `OQ-LED-12628` AND THIS MIGRATION DOES NOT ANSWER IT
═══════════════════════════════════════════════════════════════════════════
The store's schedule is write-once SEVEN YEARS, which is very likely what a
purchase record needs — **and that is an argument to put to the Product Owner,
not an answer a lane may adopt.** The ruling of 2026-09-23 that `audit_log` has
one retention rule and no row type is exempt is about AUDIT ROWS; a supplier's
PDF is not one, the question was never put to them, and assuming it carries over
is how a seven-year obligation gets decided by a lane.

**Nothing here writes a retention rule.** The kind simply becomes storable, and
what happens to it in 2033 is the open question's to settle. The worked case is
on the question's own row: an auditor in 2033 asking to see the invoice behind a
**$2,400.00** power purchase captured in 2026.

═══════════════════════════════════════════════════════════════════════════
4 · `RemoveConstraint` + `AddConstraint`, AND THE ROLLBACK REFUSES OVER ROWS
═══════════════════════════════════════════════════════════════════════════
Same shape as `0039`, for the same two reasons: Django's own operations keep the
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

#: The two values this migration adds. Written out rather than imported from
#: `document_models`, because a migration must describe the world AT ITS OWN
#: MOMENT: importing the live tuple would make this file's meaning change the
#: next time somebody appends a kind, which is the whole reason migrations are
#: append-only.
NEW_KINDS = ("supplier_invoice",)
NEW_SOURCES = ("supplier_invoice",)

#: ⚠ **THE ORDER IS THE MODEL'S OWN, NOT ALPHABETICAL AND NOT TIDIED.** A
#: `CheckConstraint`'s `__in` is compared BY SEQUENCE when Django decides
#: whether the database matches the models, so a re-ordered tuple here reads
#: as a pending migration for ever — `makemigrations --check` said so before
#: this was corrected.
KINDS_AFTER = (
    "bill",
    "disconnect_notice",
    "dunning_letter",
    "payment_receipt",
    "failed_payment_notice",
    "payment_plan_instalment_due",
    "payment_plan_instalment_missed",
    "payment_plan_voided",
    "move_in_welcome",
    "move_out_final_bill",
    "plan_change_confirmation",
    "payment_plan_agreement",
    "exemption_certificate",
    "remittance_receipt",
    "account_document",
    "import_source_file",
    "statement",
    "bill_ready_notice",
    "corrected_bill_notice",
    "bill_insert",
    "refund_confirmation",
    "credit_note_confirmation",
    "deposit_notice",
    "writeoff_notice",
    "account_closed_letter",
    "autopay_confirmation",
    "service_agreement",
    "deposit_agreement",
    "autopay_authorization",
    "service_appointment",
    "service_work_completed",
    "service_outage_notice",
    "service_door_hanger",
    "work_order_photo",
    "work_order_signature",
    "work_order_report",
    "service_request_document",
    *NEW_KINDS,
)

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
    stuck = StoredDocument.objects.filter(kind__in=NEW_KINDS).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0051: {stuck} stored_documents row(s) already "
            f"carry one of {', '.join(NEW_KINDS)}. Restoring the 37-value constraint would "
            "leave rows the CHECK forbids, and tenancy/0026's write-once trigger means they "
            "could be neither edited nor deleted to make room. Remove the supplier invoices' "
            "documents first, or stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        # `0050` is the latest tenancy migration at the time of writing (`P0.6`'s
        # currency lookup). Named explicitly rather than inferred — migration
        # ORDERING is a CLAUDE.md 🔒 path.
        ("tenancy", "0050_p0_6_currency_lookup"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="storeddocument",
            name="ck_stored_documents_kind",
        ),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER),
                name="ck_stored_documents_kind",
            ),
        ),
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

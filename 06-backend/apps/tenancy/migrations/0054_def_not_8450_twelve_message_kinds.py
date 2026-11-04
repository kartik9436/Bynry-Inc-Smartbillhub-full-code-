"""tenancy 0054 — **twelve message types the product sends can now be KEPT, so
they can be sent at all** (`DEF-NOT-8450`).
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-30 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

WHAT WAS WRONG
────────────────────────────────────────────────────────────────────────────
Between 12 and 27 September the catalogue gained twelve message classes — the
clerk's account message, five service-request messages, the new-connection
quote and confirmation, the two property-sale letters, the buyer's meter-visit
SMS and the scheduled-report email — and none was given a document kind. The
dispatcher keeps a copy of every email, SMS and printed letter BEFORE it sends
(`BR-NOT-027`), and a row whose class has no kind is HELD rather than guessed
into a seven-year record. So on any utility with a connected provider, every
one of the twelve would have waited in the queue for ever.

The coordinator recorded on 2026-09-30 that they are kept under the PO's
`OQ-1164` ruling of 2026-08-30 (*"keep all of them … not judged one by one"*).
Twelve classes need TEN new kinds (the grouping is argued beside the kinds in
`apps/tenancy/document_models.py`); the meter-visit SMS reuses
`service_appointment`, which needs no change here.

`RemoveConstraint` + `AddConstraint`, AND THE ROLLBACK REFUSES OVER ROWS
────────────────────────────────────────────────────────────────────────────
Same shape as `0039`, `0047` and `0051`: Django's own operations keep the
migration state and the database in step, and a rollback that restored the
38-value CHECK over rows already carrying a new kind would strand them —
`tenancy/0026`'s write-once trigger means such a row can be neither edited nor
deleted. The backwards direction refuses with a count. ⚠ As `0047` records, a
`RunPython` count runs under `FORCE ROW LEVEL SECURITY` and may see zero rows
for a non-superuser migration role; the database's own re-validation of the
restored CHECK is then what refuses (`CheckViolation … is violated by some
row`), which was proved on PostgreSQL 16 for this migration.

The list is written out by hand, never imported from the model: a migration is a
historical record. `0045` once narrowed this list by misspelling it
(`DEF-TEN-6425`), so `test_def_ten_6425_models_and_migrations_agree.py` checks
the model and the migrations agree.
"""

from django.db import migrations, models

NEW_KINDS = (
    "account_message",
    "service_request_acknowledgement",
    "service_request_more_info",
    "service_request_approved",
    "service_request_refused",
    "new_connection_quote",
    "new_connection_confirmation",
    "property_sale_buyer_letter",
    "property_sale_seller_letter",
    "scheduled_report_notice",
)

KINDS_BEFORE = (
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
    "supplier_invoice",
)

KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)


def refuse_rollback_over_live_rows(apps, schema_editor):
    """A rollback with rows already carrying a new kind would STRAND them."""
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(kind__in=NEW_KINDS).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0054: {stuck} stored_documents row(s) already "
            f"carry one of {', '.join(NEW_KINDS)}. Restoring the 38-value constraint would "
            "leave rows the CHECK forbids, and tenancy/0026's write-once trigger means they "
            "could be neither edited nor deleted to make room. Stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly rather than inferred. `0053` is the
        # latest tenancy migration at the time of writing.
        ("tenancy", "0053_p4_6_reports_settings"),
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

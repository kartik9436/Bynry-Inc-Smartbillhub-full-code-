"""tenancy 0045 — a tenth source type, because a licence and a deed are not two
renderings of one request.
HUMAN-OWNED (migration ORDERING is a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-19 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human."*) Row in
`12-governance/09-human-review-ledger.md`; not RATIFIED without a sign-off.

The PO ruled the capability in: *"you will have to reduce the size and save them
on cloud container etc"*. Until this landed, the capture screen's step 4 said
*"We cannot take a file yet — there is nowhere to store it"*, and that was true.

WHY THIS EXISTS, AND IT IS `0044` ONE TABLE ACROSS — THE THIRD TIME
────────────────────────────────────────────────────────────────────────────
`tenancy/0040` recorded this finding for a technician's ninth photograph and
`tenancy/0044` recorded it again for a clerk's second account document. This is
the same finding a third time, and it is written out rather than inferred so the
next lane meets the reasoning instead of rediscovering it:

    uq_stored_documents_filed  (tenant, source_type, source_id, content_type)
                               WHERE channel IS NULL

Its own docstring gives the reason, and the reason is about RENDERINGS:

    *"If one source could carry two artefacts of the same shape, 'serve the
    frozen copy' would have to CHOOSE one — and a chooser is a re-render
    wearing a different coat."*

That is exactly right about a bill, whose PDF and HTML are two representations
of one document. **It does not describe a counter.** An applicant for a new
connection hands over a driving licence, a tenancy agreement and a site plan —
three `application/pdf`s against one request, and not one of them is a rendering
of the other two. Under a REQUEST-scoped source the first would file and the
**second would be refused by the database**, on the most ordinary thing a clerk
does all day.

⚠ **SO THE CONSTRAINT IS NOT WIDENED.** Widening it would weaken a real
guarantee on `invoices` for every other module. What is wrong for this case is
the SOURCE, not the rule. A document's `source_id` is its own
`customers.service_request_documents.id` — trivially unique, and honest about
what the document is a copy of: itself. The REQUEST is not lost and never was;
`service_request_documents` is the table that says which request a file belongs
to, which is its entire job.

WHY THE KIND MOVES TOO, AND WHY BOTH IN ONE MIGRATION
────────────────────────────────────────────────────────────────────────────
`0039` records this and it holds here. A stored document carries a `kind` AND a
`source_type`, both under CHECK constraints. Widening only the source would let
the row be written with `kind = 'account_document'` — a claim about an account
that, for a new-connection applicant, **does not exist yet**, which is the whole
reason they are filling in a request. A half-widened whitelist is a table that
cannot store the thing it was widened for.

  * `ck_stored_documents_kind`   — 36 → 37 (`service_request_document`)
  * `ck_stored_documents_source` —  9 → 10 (`service_request_document`)

⚠ **THE TWO NEW VALUES ARE SPELLED THE SAME AND ARE NOT THE SAME THING**, which
is true of `account_document` one migration back as well. The kind says *what
this file is*; the source says *what row it hangs off*. They are compared
against different columns and different lists.

WHY THIS MIGRATION IS IN **TENANCY** AND NOT IN **CUSTOMERS**
────────────────────────────────────────────────────────────────────────────
`0039` states it: `stored_documents` is tenancy's table and both constraints are
declared on `tenancy.StoredDocument`. Django resolves a migration's `model_name`
inside its OWN app, so an `AddConstraint` written into `apps/customers/migrations`
naming `storeddocument` raises before it can run.

WHY THE LISTS ARE WRITTEN OUT AND NOT IMPORTED
────────────────────────────────────────────────────────────────────────────
`0028` argues this and `0039` and `0044` repeat it: a migration is a HISTORICAL
RECORD and must not follow the model. Importing `document_models.SOURCE_TYPES`
would make `reverse` restore whatever the list happens to be on the day somebody
rolls back, which is not a reversal of THIS migration.

LOCK COST
────────────────────────────────────────────────────────────────────────────
`DROP CONSTRAINT` + `ADD CONSTRAINT` takes an ACCESS EXCLUSIVE lock and the ADD
validates the whole table. Measured on the beta cluster on 2026-09-19:
`stored_documents` holds **184 rows**, so the validation is instant. A lane
widening either list once a utility is years in should reach for `NOT VALID` +
`VALIDATE CONSTRAINT` instead.

REVERSIBLE, AND THE REVERSAL REFUSES OVER LIVE ROWS
────────────────────────────────────────────────────────────────────────────
Same shape as `0039`, `0040` and `0044`, same reason: `0026`'s write-once
trigger means a row the restored constraints forbid could be neither edited nor
deleted to make room.
"""

from django.db import migrations, models

KINDS_BEFORE = (
    "bill",
    "disconnect_notice",
    "dunning_letter",
    "payment_receipt",
    "failed_payment_notice",
    "plan_instalment_due",
    "plan_instalment_missed",
    "plan_voided",
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
)

SOURCES_BEFORE = (
    "invoice",
    "outbound_message",
    "payment",
    "payment_plan",
    "customer_account",
    "import_batch",
    "work_order",
    "work_order_attachment",
    "account_document",
)

#: The same string in both lists, checked against two different columns. See
#: the module docstring — they are not the same fact.
NEW_VALUE = "service_request_document"

KINDS_AFTER = KINDS_BEFORE + (NEW_VALUE,)
SOURCES_AFTER = SOURCES_BEFORE + (NEW_VALUE,)


def refuse_rollback_over_live_rows(apps, schema_editor):
    """Refuse to roll back while any row carries the new kind or source type.

    ⚠ **BOTH COLUMNS ARE COUNTED, NOT JUST THE SOURCE.** A row could in
    principle carry the new kind under an older source, and restoring the
    36-value kind list would strand it exactly as surely.
    """
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(
        models.Q(source_type=NEW_VALUE) | models.Q(kind=NEW_VALUE)
    ).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0045: {stuck} stored_documents row(s) already "
            f"carry {NEW_VALUE!r} as a kind or a source type. Restoring the 36-value and "
            "9-value constraints would leave rows the CHECKs forbid, and tenancy/0026's "
            "write-once trigger means they could be neither edited nor deleted to make room."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0044_cr094_i_account_document_source")]

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

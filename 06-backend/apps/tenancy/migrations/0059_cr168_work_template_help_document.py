# ── Trace ──────────────────────────────────────────────
# Story:    CR-168-BRC10 round 4, lane SRV-3 — P3.14 (a template holds a help
#           document; PO ruling 6 of 24 Sep: *"help can be an uploaded document
#           or a video link"*)
# Rules:    NFR-35 (the document store) · tenancy/0026 (write-once rows) ·
#           CLAUDE.md 🔒 migration ordering
# Tests:    06-backend/tests/test_cr168_srv3_templates.py
# ───────────────────────────────────────────────────────
"""tenancy 0059 — a work order TEMPLATE can hold a help document.

Two values and nothing else: the kind `work_template_help` joins
`ck_stored_documents_kind` (48 → 49) and the source `work_template_help` joins
`ck_stored_documents_source` (12 → 13) — each file its own source, because
`uq_stored_documents_filed` allows one artefact per (source, content type) and a
template carries several PDFs. No column moves: the help row's `ref`
holds the stored document's id, which is how the phone already opens one
(`apps/work/mobile._help_row`).

`RemoveConstraint` + `AddConstraint`, the `0051`/`0054` shape, and the rollback
REFUSES with a count while any row carries either new value — a narrower CHECK
over such rows would strand them, and `0026`'s write-once trigger means they
could be neither edited nor deleted to make room.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-04 under the PO ruling of 2026-08-09; the
deferred human review is its row in `12-governance/09-human-review-ledger.md`.
"""

from django.db import migrations, models

NEW_KINDS = ("work_template_help",)
NEW_SOURCES = ("work_template_help",)

KINDS_BEFORE = (
    "bill", "disconnect_notice", "dunning_letter", "payment_receipt", "failed_payment_notice",
    "payment_plan_instalment_due", "payment_plan_instalment_missed", "payment_plan_voided",
    "move_in_welcome", "move_out_final_bill", "plan_change_confirmation",
    "payment_plan_agreement", "exemption_certificate", "remittance_receipt",
    "account_document", "import_source_file", "statement", "bill_ready_notice",
    "corrected_bill_notice", "bill_insert", "refund_confirmation", "credit_note_confirmation",
    "deposit_notice", "writeoff_notice", "account_closed_letter", "autopay_confirmation",
    "service_agreement", "deposit_agreement", "autopay_authorization", "service_appointment",
    "service_work_completed", "service_outage_notice", "service_door_hanger",
    "work_order_photo", "work_order_signature", "work_order_report", "service_request_document",
    "supplier_invoice", "account_message", "service_request_acknowledgement",
    "service_request_more_info", "service_request_approved", "service_request_refused",
    "new_connection_quote", "new_connection_confirmation", "property_sale_buyer_letter",
    "property_sale_seller_letter", "scheduled_report_notice",
)
SOURCES_BEFORE = (
    "invoice", "outbound_message", "payment", "payment_plan", "customer_account",
    "import_batch", "work_order", "work_order_attachment", "account_document",
    "service_request_document", "supplier_invoice", "tax_remittance",
)
KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)
SOURCES_AFTER = (*SOURCES_BEFORE, *NEW_SOURCES)


def refuse_rollback_over_live_rows(apps, schema_editor):
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(
        models.Q(kind__in=NEW_KINDS) | models.Q(source_type__in=NEW_SOURCES)
    ).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0059: {stuck} stored_documents row(s) already "
            "carry kind or source work_template_help. The narrower constraints would "
            "leave rows the CHECK forbids, and tenancy/0026's write-once trigger means they "
            "could be neither edited nor deleted to make room. Stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0058_storm_water_flat_size")]

    operations = [
        migrations.RemoveConstraint(model_name="storeddocument", name="ck_stored_documents_kind"),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER), name="ck_stored_documents_kind"
            ),
        ),
        migrations.RemoveConstraint(model_name="storeddocument", name="ck_stored_documents_source"),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(source_type__in=SOURCES_AFTER), name="ck_stored_documents_source"
            ),
        ),
        # ⚠ DEF-TEN-9655 (2026-10-04, lane CREWS-2): the refusal is the LAST
        # operation, so it is the FIRST to run on the way back. Django reverses
        # operations; placed first it ran after the narrower CHECK had been
        # restored and the rollback failed on a raw IntegrityError instead of
        # the counted sentence. Forward it is a no-op, so nothing forward moved.
        migrations.RunPython(migrations.RunPython.noop, refuse_rollback_over_live_rows),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-168-BRC10 §7.3 (POST /work/templates/{id}/help/upload-url) · §16
# generated: 2026-10-04 by CR-168 round 4 lane SRV-3
# checklist: A✔ B✔ C=n/a D=n/a E=n/a F✔ G✔ H✔ (🔒 migration ordering → review-ledger row)
# gates: makemigrations --check · migrate up → down → up on PostgreSQL 16
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

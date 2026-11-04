"""tenancy 0065 — an account-access email is a kept document kind.

`0062`'s shape exactly: the kind `account_access_email` joins
`ck_stored_documents_kind` (52 → 53). No column, no source (a frozen message is
filed under the existing `outbound_message` source). `CR-188-BRC10`, decision
log 2026-10-22 *"Account-access emails are KEPT like every other document, with
the one-time link or code REDACTED in the kept copy"*: without a kind the
dispatcher refused the staff invitation (`document_kind_not_ruled`) and it waited
queued for ever — found by the lane's browser walk. The kept copy carries a
redaction marker where the link was (`notifications.frozen_documents.
redact_credentials`), so it holds no usable credential.

Rollback is refused while any row carries the kind: the narrower CHECK would
strand write-once rows (`DEF-TEN-9655`'s ordering — the refusal is the last
operation, so it is the first to run on the way back).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-22 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from importlib import import_module

from django.db import migrations, models

_previous = import_module("apps.tenancy.migrations.0062_cr182_high_usage_alert_document_kind")

NEW_KINDS = ("account_access_email",)

KINDS_BEFORE = _previous.KINDS_AFTER
KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)
SOURCES_AFTER = _previous.SOURCES_AFTER


def refuse_rollback_over_live_rows(apps, schema_editor):
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(kind__in=NEW_KINDS).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0065: {stuck} stored_documents row(s) carry kind "
            "account_access_email, and the narrower CHECK would strand these write-once "
            "rows. Stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0064_def_rat_10220_size_class_capacity")]

    operations = [
        migrations.RemoveConstraint(model_name="storeddocument", name="ck_stored_documents_kind"),
        migrations.AddConstraint(
            model_name="storeddocument",
            constraint=models.CheckConstraint(
                condition=models.Q(kind__in=KINDS_AFTER), name="ck_stored_documents_kind"
            ),
        ),
        # ⚠ THE REFUSAL IS THE LAST OPERATION, SO IT IS THE FIRST TO RUN ON THE
        # WAY BACK — before the narrower CHECK is restored (`DEF-TEN-9655`).
        migrations.RunPython(migrations.RunPython.noop, refuse_rollback_over_live_rows),
    ]

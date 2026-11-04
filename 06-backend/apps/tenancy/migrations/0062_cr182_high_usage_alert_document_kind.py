# ── Trace ──────────────────────────────────────────────
# Change:   CR-182-BRC10 — PO rulings A1–A5, 2026-10-14 (the high consumption
#           alert email); kept under OQ-1164's "keep all of them"
# Rules:    OQ-1164 (every customer document is kept) · CLAUDE.md 🔒 migration
#           ordering
# Tests:    tests/test_cr182_high_consumption_alert.py ·
#           tests/test_cr160_storage_key_layout.py (every kind has a module)
# ───────────────────────────────────────────────────────
"""tenancy 0062 — the high consumption alert email is a kept document kind.

`0061`'s shape exactly: the kind `high_usage_alert` joins
`ck_stored_documents_kind` (51 → 52). No column, no source (a frozen message is
filed under the existing `outbound_message` source). Without it the dispatcher
would HOLD every such email for ever once a provider is connected — the fault
`DEF-NOT-8450` fixed for twelve classes on 2026-09-30.

Rollback is refused while any row carries the kind: the narrower CHECK would
strand write-once rows (`DEF-TEN-9655`'s ordering — the refusal is the last
operation, so it is the first to run on the way back).

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path. AI-authored 2026-10-14 under the PO ruling of 2026-08-09; row in
`12-governance/09-human-review-ledger.md`.
"""

from importlib import import_module

from django.db import migrations, models

_previous = import_module("apps.tenancy.migrations.0061_cr172_logo_to_document_store")

NEW_KINDS = ("high_usage_alert",)

KINDS_BEFORE = _previous.KINDS_AFTER
KINDS_AFTER = (*KINDS_BEFORE, *NEW_KINDS)
SOURCES_AFTER = _previous.SOURCES_AFTER


def refuse_rollback_over_live_rows(apps, schema_editor):
    StoredDocument = apps.get_model("tenancy", "StoredDocument")
    stuck = StoredDocument.objects.filter(kind__in=NEW_KINDS).count()
    if stuck:
        raise RuntimeError(
            f"refusing to roll back tenancy/0062: {stuck} stored_documents row(s) carry kind "
            "high_usage_alert, and the narrower CHECK would strand these write-once rows. "
            "Stay on this migration."
        )


class Migration(migrations.Migration):
    dependencies = [("tenancy", "0061_cr172_logo_to_document_store")]

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

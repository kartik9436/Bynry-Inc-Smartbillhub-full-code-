# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W5 — `payments` becomes a record type a utility
#           may define custom fields on (capture at entry only). PO
#           2026-10-02, R3: *"Payments IN as capture-at-entry only"*.
# Rules:    BR-TEN-046 (as amended 2026-10-02) · BR-TEN-048 (unchanged)
# Tests:    06-backend/tests/test_cr161_w5_payment_custom_fields.py
# Impacts:  apps/tenancy/models.CUSTOM_FIELD_ENTITIES ·
#           apps/payments/migrations/0046_cr161_w5_payment_custom_data.py
# ───────────────────────────────────────────────────────
"""tenancy 0056 — the `ck_custom_field_entity` CHECK admits `payments`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-10-02 under the PO ruling of 2026-08-09 (*"AI will do it; we
will review it later as human"*); row in 12-governance/09-human-review-ledger.md.

The CHECK is `entity IN (<CUSTOM_FIELD_ENTITIES>)` (0007), so the tuple growing
by one name is a drop-and-recreate of the constraint and nothing else. No row
moves. The constraint is rebuilt from the tuple's literal value AT THIS
MIGRATION — never from the live tuple — so a later wave adding its own record
types writes its own migration and this one keeps meaning what it meant.

ROLLBACK: the reverse restores the eight-name CHECK, and PostgreSQL refuses it
while any `payments` definition exists — which is the honest answer: a utility
that has defined payment fields cannot silently lose them by an unapply.
"""

from django.db import migrations, models

#: The tuple as 0007 wrote it, and as this migration widens it — literal.
BEFORE = (
    "premises",
    "units",
    "service_points",
    "assets",
    "accounts",
    "contacts",
    "addresses",
    "service_agreements",
)
AFTER = (*BEFORE, "payments")


class Migration(migrations.Migration):
    dependencies = [
        ("tenancy", "0055_s3a_job_artifacts"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="customfield",
            name="ck_custom_field_entity",
        ),
        migrations.AddConstraint(
            model_name="customfield",
            constraint=models.CheckConstraint(
                condition=models.Q(("entity__in", AFTER)),
                name="ck_custom_field_entity",
            ),
        ),
    ]

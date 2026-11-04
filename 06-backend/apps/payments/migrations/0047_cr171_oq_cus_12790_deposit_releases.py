# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 lane RULINGS — `OQ-CUS-12790` CLOSED (a), decision log
#          *"FOUR PO RULINGS IN ONE REPLY"* (4): a cancelled move-in releases
#          its held deposit to credit and refunds everything as ONE refund.
# Rules:   CLAUDE.md hard rule 1 (isolation is `payments/0048`, its own file) ·
#          hard rule 2 (a NEW money column declares FOUR decimals) · hard
#          rule 4 (append-only: no code path updates or deletes a release)
# Tests:   06-backend/tests/test_cr171_oq_cus_12790_cancel_refund.py ·
#          06-backend/tests/test_cr171_deposit_releases_rls_pg.py
# Impacts: apps/payments/deposit_release_models.py (the column reasoning)
# ───────────────────────────────────────────────────────
"""payments 0047 — `deposit_releases`.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — migration ordering is a CLAUDE.md 🔒
sensitive path; AI-authored 2026-10-05 under the PO ruling of 2026-08-09, row in
`12-governance/09-human-review-ledger.md`.

ONE CreateModel on a new table, so Django's own reverse drops it and no existing
row is read, rewritten or deleted. RLS is `payments/0048`, its own file, for the
reason `payments/0039` gives.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("payments", "0046_cr161_w5_payment_custom_data"),
        ("tenancy", "0061_cr172_logo_to_document_store"),
    ]

    operations = [
        migrations.CreateModel(
            name="DepositRelease",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=core.dbfields.uuid7,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("account_id", models.UUIDField()),
                ("amount", models.DecimalField(decimal_places=4, max_digits=18)),
                ("currency", models.CharField(default="USD", max_length=3)),
                ("reason", models.TextField()),
                ("source_type", models.TextField()),
                ("source_id", models.TextField()),
                ("released_on", models.DateField()),
                ("released_by_id", models.UUIDField(blank=True, null=True)),
                ("journal_entry_id", models.UUIDField(blank=True, null=True)),
                ("idempotency_key", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        to="tenancy.tenant",
                    ),
                ),
            ],
            options={
                "db_table": "deposit_releases",
                "indexes": [
                    models.Index(
                        fields=["tenant", "account_id"], name="ix_deposit_releases_account"
                    )
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("amount__gt", 0)),
                        name="ck_deposit_releases_amount_positive",
                    ),
                    models.UniqueConstraint(
                        fields=("tenant", "idempotency_key"), name="uq_deposit_releases_idempotency"
                    ),
                ],
            },
        ),
    ]

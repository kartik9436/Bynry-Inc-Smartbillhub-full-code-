# ── Trace ──────────────────────────────────────────────
# Change:   CR-158-BRC10 — a customer attaches documents to a portal
#           new-service application (PO 2026-10-01; DF-4 superseded for the
#           new-service request only).
# Rules:    CLAUDE.md hard rule 1 (the table is tenant-scoped; its RLS policy
#           is portal/0011) · BR-SHL-031 (10 MB) · BR-CWP-026 (a public form
#           creates work and changes no account)
# Tests:    06-backend/tests/test_cr158_portal_application_documents.py ·
#           test_cr158_portal_application_documents_pg.py
# Impacts:  apps/portal/models.py PortalApplicationDocument ·
#           apps/portal/applications.py · apps/portal/write_points.py
# ───────────────────────────────────────────────────────
"""portal 0010 — ONE table: `portal_application_documents`.

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-10-01 under the PO ruling of
2026-08-09; row in 12-governance/09-human-review-ledger.md.

A file attached to an UNSENT application, held here until the application is
sent and then handed to the document store. `models.PortalApplicationDocument`
carries the reasoning; the two CHECKs make the type and size limits the
database's as well as the code's.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0009_cr068_request_errands"),
        ("tenancy", "0054_def_not_8450_twelve_message_kinds"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalApplicationDocument",
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
                ("name", models.TextField()),
                ("content_type", models.TextField()),
                ("size_bytes", models.IntegerField()),
                ("payload", models.BinaryField()),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                (
                    "draft",
                    models.ForeignKey(
                        db_column="draft_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="documents",
                        to="portal.portalapplicationdraft",
                    ),
                ),
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
                "db_table": "portal_application_documents",
                "indexes": [
                    models.Index(fields=["tenant", "draft"], name="ix_portal_app_docs_draft")
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("content_type__in", ("application/pdf", "image/jpeg", "image/png"))
                        ),
                        name="ck_portal_app_docs_content_type",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("size_bytes__gt", 0), ("size_bytes__lte", 10485760)),
                        name="ck_portal_app_docs_size",
                    ),
                ],
            },
        ),
    ]

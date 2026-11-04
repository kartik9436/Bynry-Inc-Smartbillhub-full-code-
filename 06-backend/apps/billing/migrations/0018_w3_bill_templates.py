# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-021 (template CRUD, append-only versions, publish rights)
#           Screens: S8 · S91 · S92 · S93
# Rules:    BR-BIL-025 (assignment defaults by category) · BR-BIL-026 (edit =
#           new version; one PUBLISHED per template; publishing affects only
#           FUTURE bills — AMENDED 2026-08-12 by OQ-149: v1 ships 3–5 PLATFORM
#           layouts, not tenant-authored design) · BR-BIL-027 (Clerk drafts,
#           System Admin publishes, a pinned version is never deletable) ·
#           B2 Addendum r10 #4 (the two tables) · r10 #15 (exact DDL =
#           Eng-Lead-owned) · CLAUDE.md rule 1
# Tests:    06-backend/tests/test_us_bil_021_templates.py
# ───────────────────────────────────────────────────────
"""billing 0018 — `bill_templates` + `bill_template_versions` (r10 #4).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO ruling of
2026-08-09; row owed in 12-governance/09-human-review-ledger.md.

These are Addendum r10 #4, the two tables `EP-BIL-06` has named as missing
since the epic was written and that `apps/billing/documents.py` records the
absence of on every document it renders (`layout_source` says its one built-in
layout is *standing in for* whatever version was pinned).

WHAT A VERSION HOLDS, AND THE RULING THAT DECIDED IT
------------------------------------------------------
**PO 2026-08-12, OQ-149 CLOSED:** *"out platform will porvide standard 3 to 5
variouation of printed bill - user can use those only in V1"*. So a version row
carries a platform `layout_key` plus the tenant's `options` — **there is no
`body` column and its absence is deliberate**. Tenant-authored markup is what
would have required an HTML/CSS engine (WeasyPrint plus Pango, HarfBuzz and
fontconfig — roughly 200MB in every container), and nothing renders tenant
markup in v1, so the engine question does not arrive and the deployment image
does not change.

WHY THE UNIQUE INDEXES ARE INDEXES AND NOT SERVICE CHECKS
-----------------------------------------------------------
`uq_bill_template_one_published` is BR-BIL-026's *"one published per template"*.
Two published versions is a question with no answer at issue time — a bill would
pin whichever the query happened to return — and a SELECT-then-INSERT check in
the service loses exactly the race that produces it. PARTIAL, so any number of
drafts and archived rows coexist.

`uq_bill_templates_category` is BR-BIL-025's resolution order made safe: issue
resolves account-override → category default, and a category with two defaults
makes the second step a coin toss.

RLS AND THE APPEND-ONLY FREEZE ARE `0019`, NOT THIS MIGRATION
---------------------------------------------------------------
Policy SQL is its own 🔒 review surface, and mixing DDL with policy in one file
has meant, twice in this repo, that a table shipped and its policy did not.
`0015` states the same split for the same reason.
"""

import core.dbfields
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0017_invoice_correction_chain"),
        ("identity", "0004_rls_security_policies"),
        ("tenancy", "0009_sample_data_runs"),
    ]

    operations = [
        migrations.CreateModel(
            name="BillTemplate",
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
                ("template_type", models.TextField(default="bill")),
                ("category", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
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
                "db_table": "bill_templates",
            },
        ),
        migrations.CreateModel(
            name="BillTemplateVersion",
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
                ("version_no", models.IntegerField()),
                ("status", models.TextField(default="draft")),
                ("layout_key", models.TextField()),
                ("options", models.JSONField(blank=True, default=dict)),
                ("published_on", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="created_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bill_template_versions_created",
                        to="identity.user",
                    ),
                ),
                (
                    "published_by",
                    models.ForeignKey(
                        blank=True,
                        db_column="published_by",
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="bill_template_versions_published",
                        to="identity.user",
                    ),
                ),
                (
                    "template",
                    models.ForeignKey(
                        db_column="template_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="billing.billtemplate",
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
                "db_table": "bill_template_versions",
            },
        ),
        migrations.AddIndex(
            model_name="billtemplate",
            index=models.Index(fields=["tenant", "template_type"], name="ix_bill_templates_type"),
        ),
        migrations.AddConstraint(
            model_name="billtemplate",
            constraint=models.UniqueConstraint(
                fields=("tenant", "name"), name="uq_bill_templates_name"
            ),
        ),
        migrations.AddConstraint(
            model_name="billtemplate",
            constraint=models.UniqueConstraint(
                condition=models.Q(("category__isnull", False)),
                fields=("tenant", "template_type", "category"),
                name="uq_bill_templates_category",
            ),
        ),
        migrations.AddIndex(
            model_name="billtemplateversion",
            index=models.Index(
                fields=["tenant", "template", "status"], name="ix_bill_tpl_versions_status"
            ),
        ),
        migrations.AddConstraint(
            model_name="billtemplateversion",
            constraint=models.UniqueConstraint(
                fields=("tenant", "template", "version_no"), name="uq_bill_template_version_no"
            ),
        ),
        migrations.AddConstraint(
            model_name="billtemplateversion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("status", "published")),
                fields=("tenant", "template"),
                name="uq_bill_template_one_published",
            ),
        ),
        migrations.AddConstraint(
            model_name="billtemplateversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("version_no__gte", 1)), name="ck_bill_template_version_positive"
            ),
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-021@2b52def (ships with apps/billing/template_models.py — the same four sources)
# generated: 2026-08-15 by story-coder (billing final lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — schema only; S8's Templates tab has no endpoint) E=deferred(no-frontend-half — S8 Templates tab and S91–S93 are unbuilt) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: makemigrations --check · pytest · run_gates — see the lane report.
# exceptions: (1) NO `body` COLUMN, AND THE ABSENCE IS THE GUARD. OQ-149 (PO
#         2026-08-12) closed v1 at 3–5 PLATFORM layouts, so a version stores a
#         `layout_key` plus the tenant's `options`. Tenant markup is what would
#         have required an HTML/CSS engine (WeasyPrint + Pango/HarfBuzz/
#         fontconfig, ~200MB per container); with nowhere to store markup,
#         nothing renders it and the image does not change.
#         (2) RLS AND THE VERSION FREEZE ARE `0019`, deliberately split — policy
#         SQL is its own review surface, and mixing DDL with policy in one file
#         has twice meant a table shipped and its policy did not (`0015`).
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

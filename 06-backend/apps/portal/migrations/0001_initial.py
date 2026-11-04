# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-069 (EP-CWP-12) — `portal_settings`, the module's first table.
# Rules:    CR-068 R8 (defaults: all on except self-read) · CLAUDE.md hard-won
#           law 3 (`is_live` defaults false) · 🔒 migration ordering (CLAUDE.md
#           sensitive paths — this is the portal module's FIRST migration)
# Tests:    06-backend/tests/test_us_cwp_069_settings.py TC-3 (a brand-new
#           tenant reads the R8 defaults) · tests/test_us_cwp_001_pg.py
# Impacts:  apps/portal/models.py · 0002_rls_portal_settings.py depends on this
# ───────────────────────────────────────────────────────
"""portal 0001 — one table, `portal_settings`. HUMAN-OWNED (migration ordering
is a CLAUDE.md 🔒 sensitive path; this is the module's FIRST migration).

HUMAN-REVIEW-PENDING — AI-authored 2026-09-03 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), implementing the SIGNED
schema only: `04-docs/05-modules/15-portal/03-field-map.md` §1 `portal_settings`
(CP-30) and CR-068 R8. Row in 12-governance/09-human-review-ledger.md; not
RATIFIED without a recorded human sign-off.

Plain `CreateModel`, both vendors: the PRIMARY KEY is the tenant id (one row
per tenant, and the row cannot exist without its tenant). No default row is
inserted for existing tenants — a tenant with no row reads as the R8 defaults
(`selectors.settings_view`), so a migration that wrote one would be a write
nobody asked for. RLS is the NEXT migration, in its own file, the way every
other module does it.
"""

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("tenancy", "0036_def3422_drop_bell_events"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalSettings",
            fields=[
                (
                    "tenant",
                    models.OneToOneField(
                        db_column="tenant_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        primary_key=True,
                        related_name="portal_settings",
                        serialize=False,
                        to="tenancy.tenant",
                    ),
                ),
                ("is_live", models.BooleanField(default=False)),
                ("quick_pay_enabled", models.BooleanField(default=True)),
                ("self_read_enabled", models.BooleanField(default=False)),
                ("plans_enabled", models.BooleanField(default=True)),
                ("requests_enabled", models.BooleanField(default=True)),
                ("outage_reporting_enabled", models.BooleanField(default=True)),
                ("strapline", models.TextField(blank=True, null=True)),
                ("front_page_service_ids", models.JSONField(blank=True, default=list)),
                ("office_hours_text", models.TextField(blank=True, null=True)),
                ("emergency_phone", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "portal_settings",
            },
        ),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CWP-069@87b94265 (EP-CWP-12 story + 03-field-map.md §1 snapshot)
# generated: 2026-09-03 by the CR-068 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=PENDING(🔒 migration ordering — ledger row 09-human-review-ledger.md)
# gates: G7 (HUMAN-OWNED + HUMAN-REVIEW-PENDING + ledger row) · migrate on PostgreSQL 16 and on the SQLite suite
# exceptions: none
# status: VERIFIED-UNRATIFIED (🔒 HUMAN-REVIEW-PENDING)
# ──────────────────────────────────────────────────────────

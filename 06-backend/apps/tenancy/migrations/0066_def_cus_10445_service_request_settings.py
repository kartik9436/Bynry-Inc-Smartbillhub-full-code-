# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10445 — the service request acknowledgement's target date
# Ruling:   PO 2026-10-22, decision log *"Service request acknowledgement:
#           target date, default 15 days, service type name"* — *"Default 15
#           days"*, and the same day's *"don't do any hardcoding"*
# Rules:    BR-CUS-079 (the acknowledgement) · BR-MET-020's config-over-constant
#           law (a number an engine reads lives in the database) · NFR-5 (no
#           hard caps) · CLAUDE.md hard rule 1 (tenant_settings is RLS-scoped)
# Tests:    06-backend/tests/test_def_cus_10445_service_request_acknowledgement.py
# ───────────────────────────────────────────────────────
"""tenancy 0066 — **a utility sets how far ahead an acknowledgement aims.**

When an applicant gives no preferred date, the acknowledgement's
`{target_date}` is the request date plus this many WORKING days; the same
number opens a new request's Connection date (it replaces the constant
`CONNECTION_DATE_WORKING_DAYS = 15`, ruled 2026-09-22). The PO ruled the
default (*"Default 15 days"*) and that it is not a constant (*"don't do any
hardcoding"*), so it is a parameter of a new rule-page family,
`settings_families.SERVICE_REQUESTS`, on tenancy's own `tenant_settings` row —
the shape `0053` gave the REPORTS family, for the same reason: one row every
rule page saves to, one validator, one audit action.

The default is the registry's own `default_service_requests()`, by dotted path,
so EVERY EXISTING ROW reads `15` the moment this runs — `AddField` with a
callable default backfills the rows already there — and a new tenant is seeded
the same way. Nobody has to open the card for the number to exist.

**Rollback:** `migrate tenancy 0065`. The column goes, and with it any value a
utility saved. Roll the code back with it: the build that reads the family
expects the column. Nothing else reads it.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path.
"""

from django.db import migrations, models

import apps.tenancy.settings_families


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly. Written as `0065` after `0064`;
        # RENUMBERED `0066` at merge 2026-10-22 (lane MERGE-EMAILS), after
        # CR-188-BRC10's own `0065`. Applied by no shared database.
        ("tenancy", "0065_cr188_account_access_email_document_kind"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantsettings",
            name="service_requests",
            field=models.JSONField(
                blank=True,
                default=apps.tenancy.settings_families.default_service_requests,
            ),
        ),
    ]

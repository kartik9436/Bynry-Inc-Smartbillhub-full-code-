# ── Trace ──────────────────────────────────────────────
# Change:   CR-199-BRC10 · lane TPL-SRV-EMAIL · task S5 (the logo link)
# Ruling:   PO 2026-10-29, ruling 1A — the logo link URL is set ONCE per
#           utility in Settings › Company › Branding
# Rules:    CLAUDE.md hard rule 1 (`tenants` is RLS-scoped; a column adds no
#           policy) · hard rule 7 (the save is audited by `save_company_profile`)
# Tests:    06-backend/tests/test_cr199_email_layout.py
# ───────────────────────────────────────────────────────
"""tenancy 0067 — **where the logo in a customer email points.**

One nullable text column on `tenants`, beside the two brand colours. Nullable
and with no default: a utility that has not set it gets a logo that links
nowhere, never a guessed address. `https://` is enforced by the service, not
by a CHECK, because the rule is a validation message a clerk reads.

**Rollback:** `migrate tenancy 0066`. The column goes with any value saved; the
email header then draws the logo unlinked. Roll the code back with it.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly; the tip's newest tenancy migration.
        ("tenancy", "0066_def_cus_10445_service_request_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenant",
            name="brand_logo_link_url",
            field=models.TextField(blank=True, null=True),
        ),
    ]

"""tenancy 0053 — **a utility can change how long its downloads are kept.**

Reports Build Brief `P4.6` (p047 legend ④ and p048's TODAY row, read as images
per B14 rule 42). The drawing's own words for the state this replaces:

    The section does not exist, and retention is a constant.
    ``ARTIFACT_RETENTION_DAYS = 3`` at ``exports.py`` — every tenant gets
    three days and no screen says so.

`BR-REP-018` (CONFIRMED, PO 2026-08-08, IS-11) has said *"retained 3 days by
default, **tenant-configurable**"* since the day it was signed, and
`apps/tenancy/exports.py` has carried *"(tenant-config half unbuilt)"* beside
the constant ever since. This is that half.

═══════════════════════════════════════════════════════════════════════════
ONE COLUMN, ON TENANCY'S OWN TABLE — AND THAT IS THE MODULE-BOUNDARY ANSWER
═══════════════════════════════════════════════════════════════════════════
The cards are drawn under a REPORTS heading, and `apps/reports` does not write
this row. It does not have to: **the constant was never reports'.**
`ARTIFACT_RETENTION_DAYS` governs the PLATFORM EXPORT KERNEL — every list
export in this product, audit's and the platform's as well as reports' — so the
tenant-settable half belongs exactly where the constant does. Tenancy declares
the family, validates it, writes it and audits it; reports READS it through the
seam it has had since `P3.1`. Nothing crosses `B2` §2.

The heading is presentation. `07-frontend/src/features/tenancy/reference
DataConfig.ts` already says so in its own words — *"owner is not the group"* —
and `reason_codes` is the worked case: owned by billing, filed under Plans &
Rates.

═══════════════════════════════════════════════════════════════════════════
WHY A jsonb DOCUMENT AND NOT TWO TYPED COLUMNS
═══════════════════════════════════════════════════════════════════════════
Because that is what the five families before it do, and a sixth shape would be
a sixth thing to read. `settings_families.REPORTS` is the field law; this
migration only gives it somewhere to live. The default is the registry's own
`default_reports()`, by dotted path, exactly as `0004` does for the others — so
a row seeded before anybody opens the card already reads `3` and `csv`, which
is where every tenant is today.

**Rollback:** `migrate tenancy 0052`. The column goes and with it every tenant
override; `exports.artifact_retention_days()` then answers the constant for
everybody, which is the behaviour of every build before this one. Nothing else
reads the column and no file is deleted by the change.

HUMAN-OWNED — migration ordering is a CLAUDE.md 🔒 sensitive path (`DEF-GOV-8547`).
"""

from django.db import migrations, models

import apps.tenancy.settings_families


class Migration(migrations.Migration):
    dependencies = [
        # 🔒 ORDERING — named explicitly rather than inferred. `0052` is the
        # latest tenancy migration at the time of writing.
        ("tenancy", "0052_p4_3_remittance_receipt_source"),
    ]

    operations = [
        migrations.AddField(
            model_name="tenantsettings",
            name="reports",
            field=models.JSONField(
                blank=True,
                default=apps.tenancy.settings_families.default_reports,
            ),
        ),
    ]

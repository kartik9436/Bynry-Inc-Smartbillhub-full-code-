"""identity 0015 — `security_policies.field_app_pins` (nullable JSON).

`OQ-FLD-12797` (PO 2026-10-24): the field app's certificate pins live in
Settings › Security, not in code. NULL = the platform default set is served.

No new table, so no new policy: `security_policies` has carried RLS ENABLE +
FORCE since `identity/0004`, and a column added to it is covered by the same
`tenant_id = app.tenant_id` policy. Proved on PostgreSQL 16 in
`tests/test_oq_fld_12797_field_app_pins.py` (the PG half).

HUMAN-OWNED (migration ordering is a CLAUDE.md 🔒 sensitive path).
HUMAN-REVIEW-PENDING — 🔒 transport security, AI-authored 2026-10-24 under the
PO ruling of 2026-08-09; its row is "CR-187-BRC10 PINS — CERTIFICATE PINS FROM
SETTINGS › SECURITY (OQ-FLD-12797)" in 12-governance/09-human-review-ledger.md.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("identity", "0014_cr188_password_links"),
    ]

    operations = [
        migrations.AddField(
            model_name="securitypolicy",
            name="field_app_pins",
            field=models.JSONField(blank=True, default=None, null=True),
        ),
    ]

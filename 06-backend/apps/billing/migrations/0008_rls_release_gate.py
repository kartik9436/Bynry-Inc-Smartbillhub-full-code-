# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — the step-5 sign-off)   Screens: S31 step 5
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · NFR-10 (isolation,
#           release blocker)
# ───────────────────────────────────────────────────────
"""billing 0008 — tenant isolation for `bill_run_releases`.

HUMAN-OWNED (RLS policies are a CLAUDE.md 🔒 path). HUMAN-REVIEW-PENDING —
AI-authored 2026-08-11 under the PO ruling of 2026-08-09. Applies the SIGNED
B2 §3 template verbatim, the same shape as `0002` and `0004`.

A separate migration rather than an edit to an applied one, for the reason
`0004` records: editing a migration that has already run changes nothing on
the cluster it ran against.

This row names a person, a money total and a tenant's whole billing position
for a period. It is not metadata.
"""

from django.db import migrations

POLICY_SQL = """
ALTER TABLE bill_run_releases ENABLE ROW LEVEL SECURITY;
ALTER TABLE bill_run_releases FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bill_run_releases_tenant_isolation ON bill_run_releases;
CREATE POLICY bill_run_releases_tenant_isolation ON bill_run_releases
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""


def apply_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(POLICY_SQL)


def drop_policy(apps_registry, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        "DROP POLICY IF EXISTS bill_run_releases_tenant_isolation ON bill_run_releases;"
        "ALTER TABLE bill_run_releases NO FORCE ROW LEVEL SECURITY;"
        "ALTER TABLE bill_run_releases DISABLE ROW LEVEL SECURITY;"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0007_w3_release_gate"),
    ]

    operations = [
        migrations.RunPython(apply_policy, drop_policy),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@e9d5a48 (ships with 0007)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane)
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI yet) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED — with apply_policy made a no-op the G5 catalog sweep names
#         'bill_run_releases'; restored, the suite passes
# exceptions: separate migration rather than editing an applied one, for the
#         reason 0004 records
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

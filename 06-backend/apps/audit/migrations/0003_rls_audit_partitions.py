# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (the audit trail is tenant-scoped)  Screens: S61
# Rules:    BR-AUD-007 (RLS on audit_log) · CLAUDE.md rule 1 (tenant scoping;
#           RLS FORCE is on; no cross-tenant read) · NFR-10 (isolation, zero
#           tolerance, release blocker)
# ───────────────────────────────────────────────────────
"""audit 0003 — repeat the parent's RLS policy on every `audit_log` PARTITION.

HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"). It applies the SIGNED B2 §3
policy template from `06-backend/db/rls_audit_w0.sql` verbatim, once per
partition, and invents no new policy shape. Row in
12-governance/09-human-review-ledger.md; not RATIFIED without a human sign-off.

⚠ WHY THIS EXISTS — a MEASURED cross-tenant exposure, not a theoretical one.

`audit 0002` enables ENABLE + FORCE + one policy on the partitioned PARENT
`audit_log`. That is not enough, and PostgreSQL documents why: a parent's row
policies are applied when rows are reached THROUGH the parent. **A partition
queried DIRECTLY consults only its own policies.** `audit_log` has none on its
partitions, so:

    SELECT * FROM audit_log_2026_08;     -- every tenant's audit trail

Measured on the deployed schema on 2026-08-10:

    audit_log                rls=True   force=True   policies=1
    audit_log_2026_08        rls=False  force=False  policies=0
    audit_log_2026_09        rls=False  force=False  policies=0
    audit_log_2026_10        rls=False  force=False  policies=0

The application itself always queries the parent, so the ORM path was never
leaking. The exposure is any direct read of a partition — a support script, a
reporting or BI connection, a psql session, or a future queryset that targets a
partition — and `audit_log` is the one table that holds every tenant's record of
who did what.

Found by the W2 reads lane, which hit the identical hole on its own
`meter_reads` partitions and proved it on a live cluster under a
NOSUPERUSER/NOBYPASSRLS role. `metering 0004` fixes that table; this fixes
`audit_log`, using the same loop so there is one pattern to review, not two.

⚠ FOR THE REVIEWER — this closes today's partitions. It does NOT make the
create-ahead partition job apply policies to partitions minted LATER; that job
lives in `core/` and is named in the defect log as the second half of the fix.
Until that lands, a partition created next month is unguarded again, and
`test_us_aud_001_tc5_rls__every_audit_log_partition_is_guarded` is what will say
so.
"""

from django.db import migrations


def apply_partition_policies(apps_registry, schema_editor):
    """Repeat the parent's policy on every `audit_log` partition.

    Postgres only. Idempotent — the policy is dropped-if-exists first, so
    re-running this (or running it again after new partitions appear) is safe
    and is in fact the intended remediation until the create-ahead job owns it.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = 'audit_log'"
        )
        partitions = [row[0] for row in cursor.fetchall()]
    for partition in partitions:
        # The B2 §3 template, verbatim. Deny-by-default: with `app.tenant_id`
        # unset the ::uuid cast of '' fails and NO row is visible.
        schema_editor.execute(f"""
ALTER TABLE {partition} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {partition} FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS {partition}_tenant_isolation ON {partition};
CREATE POLICY {partition}_tenant_isolation ON {partition}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
""")


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0002_rls_w0_policies"),
    ]

    operations = [
        migrations.RunPython(apply_partition_policies, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@9941789 (EP-AUD-01 — remediation of a measured
#         cross-tenant exposure found by the W2 reads lane 2026-08-10)
# generated: 2026-08-10 by Eng-Lead
# checklist: A✔ B✔ C✔ D=deferred(no API call — a migration) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — the guard test names all unguarded
#         partitions before this migration and passes after; pg_class verified
#         on the live cluster; ruff✔ black✔ suite✔ run_gates✔
# exceptions: closes TODAY's partitions only — the create-ahead job in core/
#         must also apply policies to partitions minted later, which is logged
#         as the second half of this defect rather than implied complete here
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

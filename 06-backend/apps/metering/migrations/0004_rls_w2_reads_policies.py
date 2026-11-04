# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-007/TC-8 · US-MET-008/TC-9 · US-MET-009/TC-7 · US-MET-010/TC-8 ·
#           US-MET-011/TC-10 · US-MET-014/TC-8 (every reads story's isolation TC)
#           Screens: S25, S28, S29
# Rules:    CLAUDE.md hard rule 1 (never touch a tenant table without
#           app.tenant_id; RLS FORCE is on) · B2 §3 policy template · DB-1 ·
#           NFR-10 (zero tolerance, release blocker)
# Tests:    06-backend/tests/test_us_met_reads_isolation.py (live-Postgres probes,
#           @pytest.mark.isolation) · the suite-wide G5 sweep
# Impacts:  every read query in apps/metering/selectors.py + services.py
# ───────────────────────────────────────────────────────
"""metering 0004 — RLS ENABLE+FORCE on every W2 READS tenant table.
HUMAN-OWNED (RLS policies are a CLAUDE.md rule-1 🔒 path).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-10 under the PO ruling of 2026-08-09
("AI will do it; we will review it later as human"), applying the SIGNED B2 §3
policy template VERBATIM, once per table. Row per file in
12-governance/09-human-review-ledger.md; not RATIFIED without human sign-off.

The B2 §3 template, repeated per tenant-scoped table — deny-by-default: with
`app.tenant_id` unset the `::uuid` cast of '' fails and NO row is visible:

    ALTER TABLE <t> ENABLE ROW LEVEL SECURITY;
    ALTER TABLE <t> FORCE ROW LEVEL SECURITY;    -- applies even to the owner
    CREATE POLICY <t>_tenant_isolation ON <t>
      USING      (tenant_id = current_setting('app.tenant_id')::uuid)
      WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);

FOUR tables — and `meter_reads`, the PARTITIONED one, needs a second step that
is easy to miss and was MEASURED here rather than assumed.

⚠ **A parent's RLS policy does NOT protect a partition queried directly.**
Enabling RLS on a partitioned parent covers access *through the parent*; a
`SELECT … FROM meter_reads_2026_08` consults only that partition's own
policies, and a partition created by `CREATE TABLE … PARTITION OF` has RLS
DISABLED. Proved on this cluster with a two-tenant fixture under a
NOSUPERUSER/NOBYPASSRLS role:

    via parent        → 1 row   (correctly scoped)
    direct partition  → 2 rows  (BOTH tenants — the policy never ran)

So `apply_partition_policies` below repeats ENABLE + FORCE + the same B2 §3
policy on every existing partition. `tests/test_us_met_reads_isolation.py`
asserts no partition is left unguarded, and that assertion is what keeps this
true as partitions are added — it was written by watching it go RED against
exactly the state this migration now fixes (Hard-won law 7).

⚠ FOR THE REVIEWER — the SAME hole exists on `audit_log`, whose partitions are
equally RLS-disabled (`apps/audit/migrations/0002_rls_w0_policies` enables the
parent only). apps/audit is outside this lane's territory, so it is REPORTED,
not silently patched: a direct read of `audit_log_2026_08` today returns every
tenant's trail. Same one-line fix, same owner decision.

Consequence for the future: any code path that creates a `meter_reads`
partition must apply the policy in the same breath. Today none does — the
BE-10 create-ahead job skips `meter_reads` entirely (see 0003's docstring) —
so there is no live drift, but whoever activates that job inherits this
requirement, and the isolation test will tell them so.

⚠ FOR THE REVIEWER — one hosting call, identical to the one customers 0002,
identity 0004 and tenancy 0004 each flagged: the policy SQL is INLINE here
rather than in 06-backend/db/rls_metering_w2_reads.sql, because 06-backend/db/
is outside this lane's stated territory. That is now FOUR files wanting the
same relocation, as one edit, by whoever owns that directory. The policy TEXT
is the B2 §3 template either way — metering 0002 loads its W1 twin from
db/rls_metering_w1.sql, so the split is visible in one module.

Postgres only — `PostgresOnlySQL` skips honestly on the sqlite test database,
where RLS does not exist. The live proofs are the G5 isolation suite (NFR-10,
zero tolerance, release blocker).
"""

from django.db import migrations

from core.migrationtools import PostgresOnlySQL

# B2 §3 template, verbatim, one block per tenant-scoped W2 reads table.
POLICIES = "\n".join(
    f"""
ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;
ALTER TABLE {table} FORCE ROW LEVEL SECURITY;
CREATE POLICY {table}_tenant_isolation ON {table}
  USING      (tenant_id = current_setting('app.tenant_id')::uuid)
  WITH CHECK (tenant_id = current_setting('app.tenant_id')::uuid);
"""
    for table in (
        "read_validation_settings",
        "read_import_batches",
        "read_import_rows",
        "meter_reads",
    )
)


def apply_partition_policies(apps_registry, schema_editor):
    """Repeat the parent's policy on every `meter_reads` partition.

    Postgres only. Required because a partition queried DIRECTLY consults only
    its own policies — see the ⚠ block in the module docstring for the measured
    proof. Idempotent: the policy is dropped-if-exists first, so re-running the
    migration (or running it after new partitions appear) is safe.
    """
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = 'meter_reads'"
        )
        partitions = [row[0] for row in cursor.fetchall()]
    for partition in partitions:
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
        ("metering", "0003_w2_reads"),
    ]

    operations = [
        PostgresOnlySQL(
            sql=POLICIES,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(apply_partition_policies, migrations.RunPython.noop),
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-011@64b3d87 (story+rules snapshot — EP-MET-04; the isolation half of every reads story)
# generated: 2026-08-10 by the reads lane (RLS half of the W2 metering slice)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — RLS migration) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — RLS 🔒 HUMAN-REVIEW-PENDING, ledger row appended)
# gates: see the lane report — ruff/black/pytest/run_gates/golden run over the whole slice
# exceptions: policy SQL inline rather than in 06-backend/db/ (fourth file to flag the same relocation — REPORTED, not resolved here)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (the audit trail is tenant-scoped)  Screens: S61
#           — generalised 2026-08-10 to every partitioned table (DEF-027)
# Rules:    BR-AUD-007 · CLAUDE.md rule 1 (tenant scoping, RLS FORCE) ·
#           B2 §3 policy template · NFR-10 (isolation — zero tolerance,
#           release blocker)
# ───────────────────────────────────────────────────────
"""EVERY partition of EVERY partitioned table carries its own RLS policy.

A parent's row policies are applied when rows are reached THROUGH the parent.
A partition queried DIRECTLY consults only its own policies. `audit 0002`
guarded the parent alone, so `SELECT * FROM audit_log_2026_08` returned every
tenant's audit trail; `meter_reads` had the identical hole. `audit 0003` and
`metering 0004` closed the partitions that existed on 2026-08-10, and
`core/partitioning.py` now guards the ones minted after (DEF-027, half two).

WHY THIS GUARD IS CATALOG-DRIVEN AND NOT PER-TABLE
--------------------------------------------------
It started as an `audit_log`-only check, written the day the exposure was
found. The same hole existed on `meter_reads` at that moment and nothing here
would have said so — it took a human noticing. So the query below asks
PostgreSQL for EVERY partitioned parent (`relkind = 'p'`) and EVERY child of
each, and fails naming whatever is unguarded. The next partitioned table —
`invoice_lines` (W3), `journal_lines` (W5), `outbound_messages` (W6) — is
covered the moment its migration runs, with no test to remember to write.
That is the whole point: the failure mode here is *forgetting a table*, so the
guard must not have a table list in it.

`tests/test_def_027_partition_rls_create_ahead.py` is its companion: this file
checks the partitions that EXIST, that one proves a NEWLY minted partition
comes out guarded. A guard over today's partitions alone would have passed
against the very defect that produced it.

Postgres only — sqlite has no RLS, so the check is skipped there rather than
passing vacuously.
"""

import pytest

from tests.isolation_helpers import RLS_EXEMPT_TABLES, requires_postgres

pytestmark = pytest.mark.isolation

# The table the exposure was measured on. Named ONLY to keep the catalog sweep
# from silently going vacuous — never to scope it.
AUDIT_PARENT = "audit_log"

#: (parent, child, rls, force, policy_count) for every partition in `public`.
_PARTITIONS_SQL = """
SELECT par.relname, c.relname, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
FROM pg_inherits i
JOIN pg_class par ON par.oid = i.inhparent
JOIN pg_class c ON c.oid = i.inhrelid
JOIN pg_namespace n ON n.oid = par.relnamespace
WHERE n.nspname = 'public' AND par.relkind = 'p'
ORDER BY par.relname, c.relname
"""

#: (parent, rls, force, policy_count) for every partitioned parent in `public`.
_PARENTS_SQL = """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind = 'p'
ORDER BY c.relname
"""


def _rows(sql):
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(sql)
        return cursor.fetchall()


def all_partitions():
    """Every (parent, child, rls, force, policies) row, RLS-exempt tables aside.

    Exported so the create-ahead companion asks the catalog the same question
    in the same words.
    """
    return [row for row in _rows(_PARTITIONS_SQL) if row[0] not in RLS_EXEMPT_TABLES]


def unguarded(partitions):
    """`parent.child` for every partition missing ENABLE, FORCE, or a policy."""
    return [
        f"{parent}.{child}"
        for parent, child, rls, force, policies in partitions
        if not rls or not force or policies < 1
    ]


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__every_partition_of_every_partitioned_table_is_guarded():
    """No partition of any partitioned table may be readable without context."""
    partitions = all_partitions()

    # A database with no partitions is not a pass — it means the partitioning
    # migrations have not run and this guard would be proving nothing.
    assert partitions, (
        "no partitioned table in this database has any partitions — the "
        "partitioning migrations have not run, so this guard is vacuous. Fix "
        "the fixture, do not delete the test."
    )

    leaks = unguarded(partitions)
    assert leaks == [], (
        f"partitions readable WITHOUT tenant isolation: {leaks}. A partition "
        "queried directly consults only its own policies, so each one needs "
        "ENABLE + FORCE + a tenant policy (B2 §3, CLAUDE.md rule 1). If these "
        "are newly-minted partitions, core/partitioning.create_partition_sql "
        "stopped emitting the policy alongside the CREATE (DEF-027)."
    )


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__every_partitioned_parent_is_guarded():
    """Each parent's own guard (audit 0002 / metering 0004) has not regressed."""
    parents = [row for row in _rows(_PARENTS_SQL) if row[0] not in RLS_EXEMPT_TABLES]
    assert parents, "this database has no partitioned tables at all — see the guard above"

    leaks = [name for name, rls, force, policies in parents if not rls or not force or policies < 1]
    assert leaks == [], (
        f"partitioned parents are unguarded: {leaks} (B2 §3, CLAUDE.md rule 1). "
        "Queries through the parent — which is every ORM query — are leaking."
    )


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__every_audit_log_partition_is_guarded():
    """The sweep above genuinely covered `audit_log`, the table it was found on.

    Kept under its original name because `apps/audit/0003` and the DEF-027 row
    in the defect log both cite it. Its job now is non-vacuity: if `audit_log`
    ever stopped being partitioned, or its partitions vanished from the test
    database, the catalog sweep would go quiet and this says so instead.
    """
    audit_partitions = [row for row in all_partitions() if row[0] == AUDIT_PARENT]
    assert audit_partitions, (
        f"{AUDIT_PARENT} has no partitions in this database — the partitioning "
        "migration has not run, so the catalog sweep above never looked at the "
        "table this defect was measured on."
    )
    assert unguarded(audit_partitions) == [], (
        f"{AUDIT_PARENT} partitions readable WITHOUT tenant isolation: "
        f"{unguarded(audit_partitions)}"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@9941789 (EP-AUD-01 — the guard for the partition-RLS
#         exposure found by the W2 reads lane 2026-08-10)
# generated: 2026-08-10 by Eng-Lead
# revised: 2026-08-10 (DEF-027 half two) — the audit_log-only sweep became a
#         catalog sweep over every partitioned parent, so the next partitioned
#         table is covered without a new test
# checklist: A✔ B✔ C✔ D=deferred(no API call) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — run against the schema before audit 0003 it
#         names audit_log_2026_08/09/10 as unguarded; green after. Re-proved RED
#         for the generalised form by minting a partition with create-only DDL:
#         the sweep named audit_log_2029_02/03 and meter_reads_2029_02/03.
# exceptions: skips under sqlite rather than passing vacuously, and asserts the
#         partition list is non-empty so an unmigrated database cannot make it
#         look green
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

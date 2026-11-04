# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-001 (the audit trail is tenant-scoped) · US-MET-011 (reads
#           isolation) — DEF-027, second half   Screens: S61 · S28
# Rules:    CLAUDE.md rule 1 (tenant scoping; RLS FORCE) · BR-AUD-007 ·
#           B2 §3 policy template · B2 §5 (create-ahead) · NFR-24 (the
#           mandatory monthly partition set) · NFR-10 (isolation — zero
#           tolerance, release blocker)
# Tests:    companion to tests/test_us_aud_001_partition_rls.py — that one
#           guards the partitions that EXIST, this one guards the ones the job
#           is about to MINT
# ───────────────────────────────────────────────────────
"""A partition born from the create-ahead job comes out guarded — DEF-027 half 2.

WHY A SEPARATE FILE, AND WHY IT MINTS A REAL PARTITION
------------------------------------------------------
The first half of DEF-027 (`apps/audit/0003`, `apps/metering/0004`) repeated
the B2 §3 policy on every partition that existed on 2026-08-10. Every guard
written that day inspected exactly those partitions — and would have stayed
green forever while the leak came back, because the create-ahead job mints a
NEW partition every month and applied no policy to it. A test that only checks
today's partitions passes without the fix.

So each case below creates a partition through the REAL create-ahead path
(`core.partitioning.ensure_partitions`, the body of `manage.py
maintain_partitions`) in a month that has none, and then asks PostgreSQL's
catalog what came out. Proved RED first (Hard-won law 7): with
`create_partition_sql` emitting the bare `CREATE TABLE … PARTITION OF`, these
cases name the brand-new partitions as unguarded.

Everything happens inside the test transaction — Postgres DDL is transactional,
so the far-future partitions roll back and no fixture is left behind.

Postgres only: on sqlite there are no partitions and no RLS, so these skip with
a vendor reason rather than passing vacuously (`requires_postgres`).
"""

from datetime import date

import pytest
from django.core.management import call_command

from core import partitioning
from tests.isolation_helpers import RLS_EXEMPT_TABLES, requires_postgres
from tests.test_us_aud_001_partition_rls import all_partitions, unguarded

pytestmark = pytest.mark.isolation

#: Far enough ahead that no bootstrap or create-ahead run has been there.
#: `meter_reads` bootstraps 24 months back + 3 ahead, so 30 clears every window.
FRESH_MONTHS_AHEAD = 30


def _fresh_month() -> date:
    return partitioning.add_months(partitioning.month_start(date.today()), FRESH_MONTHS_AHEAD)


def _guard_state(names):
    """(rls, force, policy_count) per partition name, from the catalog."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
            [list(names)],
        )
        return {row[0]: (row[1], row[2], row[3]) for row in cursor.fetchall()}


@requires_postgres
@pytest.mark.django_db
@pytest.mark.parametrize("table", sorted(partitioning.ACTIVE_TABLES))
def test_us_aud_001_tc5_rls__a_newly_minted_partition_is_born_guarded(table):
    """The create-ahead job's OWN output is tenant-isolated, not just today's.

    This is the assertion the first half of DEF-027 could not make: it runs the
    real job for a period that has no partition yet and reads the catalog back.

    Parametrised over ACTIVE_TABLES, so the two YEARLY tables the PO ruled on
    2026-08-12 (invoice_lines, journal_lines) are covered here with no edit —
    `plan_create_ahead` and `partition_bounds` read each table's granularity
    out of the registry.
    """
    month = _fresh_month()
    before = set(partitioning.partition_children(table))
    expected = partitioning.plan_create_ahead(table, month, ahead=1)
    assert not (set(expected) & before), (
        f"{expected} already exist — pick a period further out, or this case "
        "proves nothing about NEW partitions"
    )

    created = partitioning.ensure_partitions(table, month, ahead=1)
    assert created == expected

    state = _guard_state(created)
    assert set(state) == set(created), (
        f"the create-ahead job did not actually create {set(created) - set(state)} "
        f"on {table} — nothing was proved"
    )
    leaks = [
        name
        for name, (rls, force, policies) in state.items()
        if not rls or not force or policies < 1
    ]
    assert leaks == [], (
        f"{table}: partitions minted by the create-ahead job are readable WITHOUT "
        f"tenant isolation: {leaks}. A partition queried directly consults only its "
        "own policies — core/partitioning.create_partition_sql must emit ENABLE + "
        "FORCE + the B2 §3 policy in the same statement as the CREATE (DEF-027)."
    )


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__the_job_repairs_a_partition_that_predates_the_guarantee():
    """Re-running the job heals an unguarded partition — the remediation path.

    `apps/audit/0003` and `apps/metering/0004` both say re-running is the
    intended remediation. This creates the pre-DEF-027 state on purpose — a
    bare `CREATE TABLE … PARTITION OF`, the DDL the module no longer emits —
    and asserts one job run closes it.
    """
    from django.db import connection

    table = "audit_log"
    month = _fresh_month()
    orphan = partitioning.partition_name(table, month)
    start, end = partitioning.partition_bounds(table, month)
    with connection.cursor() as cursor:
        cursor.execute(
            f"CREATE TABLE {orphan} PARTITION OF {table} "
            f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');"
        )

    assert orphan in partitioning.unguarded_partitions(table), (
        "a bare CREATE TABLE … PARTITION OF was expected to produce an unguarded "
        "partition — if PostgreSQL now inherits the parent's policies, this whole "
        "defect changed shape and the module's docstring needs rewriting"
    )

    # The ordinary job run — nothing about it names the orphan.
    partitioning.ensure_partitions(table, date.today())

    assert partitioning.unguarded_partitions(table) == [], (
        f"{orphan} was created before this guarantee existed and one run of the "
        "create-ahead job did not heal it. Re-running the job is the remediation "
        "path apps/audit/0003 and apps/metering/0004 both point at, so it has to "
        "repair partitions it did not create."
    )


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__every_partitioned_parent_is_in_the_create_ahead_set():
    """A partitioned table the job does not know about is a future outage.

    Two different failures ride on this one set, which is why it is asserted
    against the DATABASE rather than against the registry:
      * partitions stop being RENEWED — `meter_reads` bootstrapped a fixed
        28-month window and nothing extended it, so INSERTs would have begun
        failing when it ran out (this is why it joined ACTIVE_TABLES);
      * partitions stop being GUARDED — the job is what applies the policy, so
        a table outside it also drifts back toward DEF-027.
    """
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind = 'p' ORDER BY c.relname"
        )
        parents = {row[0] for row in cursor.fetchall()} - RLS_EXEMPT_TABLES

    assert parents, "no partitioned tables in this database — the migrations have not run"
    missing = sorted(parents - partitioning.ACTIVE_TABLES)
    assert missing == [], (
        f"partitioned tables the create-ahead job never touches: {missing}. Add "
        "them to core.partitioning.ACTIVE_TABLES (and to REGISTRY with their "
        "partition key) or their partitions are neither renewed nor guarded."
    )

    # The other direction: everything the job believes is partitioned really is.
    for table in sorted(partitioning.ACTIVE_TABLES):
        assert partitioning.is_partitioned_parent(
            table
        ), f"{table} is in ACTIVE_TABLES but is not a partitioned table here"


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__a_host_behind_on_migrations_fails_with_a_diagnosis(monkeypatch):
    """A lagging host gets a sentence it can act on, not a psycopg riddle.

    MEASURED on the dev cluster on 2026-08-10: adding `meter_reads` to
    ACTIVE_TABLES made `manage.py maintain_partitions` die there with

        ProgrammingError: relation "meter_reads" does not exist

    because that host had never run `metering 0003`. Nothing in that message
    says which table the job wanted, that ACTIVE_TABLES and the schema
    disagree, or that `migrate` is the fix.

    It still FAILS — deliberately, and loudly. Skipping the table would stop
    its partitions being created and the first symptom would be failing
    INSERTs weeks later, which is the quiet failure this whole change exists
    to remove.
    """
    # `outbound_messages` is in the NFR-24 REGISTRY but is not a partitioned
    # parent — exactly the shape of the dev-cluster failure: a registered table,
    # switched on in ACTIVE_TABLES, with no partitioned parent on this host.
    # (This case used `invoice_lines` until 2026-08-15, when the PO's OQ-107
    # ruling partitioned it for real and it stopped being a table with no
    # parent. `outbound_messages` is the permanent stand-in: PO 2026-08-11 ruled
    # it stays unpartitioned, so it will never land.)
    lagging = "outbound_messages"
    assert lagging in partitioning.REGISTRY
    assert not partitioning.is_partitioned_parent(lagging), (
        f"{lagging} has landed as a partitioned parent — this case needs a "
        "registered table whose migration has NOT run; pick another wave's table"
    )
    monkeypatch.setattr(partitioning, "ACTIVE_TABLES", frozenset({lagging}))

    with pytest.raises(partitioning.PartitioningError) as excinfo:
        partitioning.ensure_partitions(lagging, date.today())
    message = str(excinfo.value)
    assert lagging in message
    assert "behind on migrations" in message and "migrate" in message, message


@requires_postgres
@pytest.mark.django_db
def test_us_aud_001_tc5_rls__maintain_partitions_command_mints_guarded_partitions(monkeypatch):
    """The shipped entry point, end to end: `manage.py maintain_partitions`.

    This is what ops and the scheduler actually run, so the guarantee is
    asserted from THERE and not only from the function underneath it.

    The command's clock is moved to a month with no partitions, because running
    it for today would only re-touch partitions that already exist and pass
    without proving anything — which is precisely how the first half of this
    defect stayed invisible.
    """
    month = _fresh_month()

    class _FrozenToday(date):
        @classmethod
        def today(cls):
            return month

    from apps.audit.management.commands import maintain_partitions as command_module

    monkeypatch.setattr(command_module, "date", _FrozenToday)

    before = {name for _p, name, *_ in all_partitions()}
    call_command("maintain_partitions")
    after = {name for _p, name, *_ in all_partitions()}

    minted = after - before
    assert minted, (
        "maintain_partitions created no partitions at all for a month that had "
        "none — the run proved nothing about newly minted partitions"
    )
    leaks = unguarded(all_partitions())
    assert leaks == [], (
        f"maintain_partitions minted {sorted(minted)} and left these unguarded: "
        f"{leaks} (CLAUDE.md rule 1 — every partition needs its own policy)"
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@9941789 (EP-AUD-01 — DEF-027 second half: the create-ahead
#         job must not mint unguarded partitions)
# generated: 2026-08-10 by the core/ lane
# checklist: A✔ B✔ C✔ D=deferred(no API call) E=deferred(no UI) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — with create_partition_sql reverted to the bare
#         CREATE TABLE … PARTITION OF, the parametrised case named
#         audit_log_2029_02/03 and meter_reads_2029_02/03 as unguarded, and the
#         command case named them too; all green once the policy rode along
# exceptions: skips under sqlite rather than passing vacuously (no RLS, no
#         partitions there); far-future months are used so the DDL cannot
#         collide with the bootstrap window, and the test transaction rolls the
#         partitions back
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

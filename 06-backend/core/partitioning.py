# ── Trace ──────────────────────────────────────────────
# Component: BE-10 partition manager (B13 §3, W0 kernel lane — component packet)
# Contract:  NFR-24 (mandatory partition set: audit_log, meter_reads,
#            invoice_lines, journal_lines, outbound_messages — "No exceptions";
#            its "monthly" wording is SUPERSEDED for the two financial line
#            tables by the PO ruling of 2026-08-12, "Nod to split both by year",
#            OQ-107 CLOSED) · NFR-25 (financial tables NEVER pruned; >2yr
#            partitions may move to cold storage but stay queryable) · NFR-28
#            (audit_log monthly, 2yr hot, 7yr total) · B2 §5 (pre-create ahead
#            via scheduled job; "Candidate key: period_start/created_at" for
#            invoice_lines + journal_lines) · B2 r16 #1 (F-1: §5 "do not
#            partition now" SUPERSEDED — the NFR-24 set stands)
# Rules:     BR-AUD-012 (audit_log monthly partitions, table half) · BR-MET-055 /
#            NFR-6 (reads 2yr hot → detach to cold, 7yr total — table lands W1/W2) ·
#            CLAUDE.md rule 1 + B2 §3 (every partition carries the tenant policy —
#            DEF-027, since a partition read DIRECTLY consults only its own) ·
#            CLAUDE.md rule 4 (financial immutability — the rebuild below copies
#            rows and ties them out; it never UPDATEs or DELETEs one)
# Tests:     06-backend/tests/test_be10_partitioning.py (pure period math + SQL text +
#            never-drop law) · tests/test_oq_107_yearly_partitions.py (the yearly
#            half + the live rebuild, PG) · tests/test_def_027_partition_rls_create_ahead.py
#            (a NEW partition is born guarded, live PG) · tests/test_us_aud_001_partition_rls.py
#            (the catalog-wide guard) · live-partition TCs (US-AUD-001 TC-1) = G5 lane
# Impacts:   audit_log (NOW) · meter_reads (W1/W2) · invoice_lines (W3, yearly) ·
#            journal_lines (W5, yearly) · outbound_messages (W6, RULED unpartitioned
#            — PO 2026-08-11, OQ-108) · EP-AUD-03 archival job ·
#            09-infra partition-growth telemetry
# ───────────────────────────────────────────────────────
"""BE-10 — range partitions for the NFR-24 big five. HUMAN-OWNED
(🔒-adjacent: partition DDL is migration-ordering-adjacent, CLAUDE.md list).

HUMAN-REVIEW-PENDING — AI-authored 2026-08-09 under PO ruling 2026-08-09
("AI will do it; we will review it later as human"), implementing SIGNED law
only (NFR-24/25/28 + B2 §5 + r16 #1). Row appended to
12-governance/09-human-review-ledger.md; must not reach RATIFIED without a
recorded human sign-off.

TWO GRANULARITIES, BECAUSE THE PO RULED ONE (2026-08-12, OQ-107)
----------------------------------------------------------------
`audit_log` and `meter_reads` are MONTHLY — NFR-24/NFR-28/BR-MET-055, unchanged.
`invoice_lines` and `journal_lines` are **YEARLY**: the PO's own words on
2026-08-12 were *"Nod to split both by year"*, recorded in
12-governance/02-decision-log.md. The option put to them was BY MONTH and they
answered by year, so NFR-24's "monthly" wording is SUPERSEDED for those two
tables and flagged as a change to a signed NFR rather than absorbed. At this
product's declared ceiling — utilities under 3,000 connections — a year of
invoice lines is a small partition and there are fewer of them to maintain.
`outbound_messages` stays UNPARTITIONED entirely (PO 2026-08-11, OQ-108: the
no-duplicate guarantee wins over NFR-24), which is why its registry entry never
joins ACTIVE_TABLES.

⚠ THE KEY IS NOT THE GRANULARITY, AND THE PO WAS NOT ASKED THE KEY.
The 2026-08-12 ruling settled how BIG a partition is. Which COLUMN it ranges
over was never put to them. What shipped is `created_at`, and the reason is
written here rather than left to be inferred:

  * B2 §5 names the candidates outright — *"Candidate key: period_start /
    created_at"* — for both tables, so `created_at` is chosen from signed law
    rather than invented.
  * `invoice_lines.period_start` is NULLABLE (a fee or late-charge line has no
    service period). A RANGE partition key that is NULL routes nowhere without
    a DEFAULT partition, and a DEFAULT partition breaks both create-ahead and
    NFR-25's detach-by-age model. It cannot be the key as the column stands.
  * `journal_lines` HAS NO BOOK DATE. `entry_date` lives on `journal_entries`.
    The Eng-Lead reading recorded in the decision log on 2026-08-11 — that the
    book date should be the key because it is what a trial balance groups by —
    is NOT implemented, and two things stand in the way of implementing it:
    the column would have to be denormalised onto `journal_lines` (a change to
    a B2-signed table the ledger module owns), and it would be a MUTABLE
    partition key, because BR-LED-003 lets a DRAFT entry's `entry_date` move —
    a row would have to change partition under an append-only trigger.
  * So `created_at` serves NFR-24's stated purpose (volume and detach-by-age)
    and does NOT serve the trial-balance pruning the 2026-08-11 reading wanted.
    That gap is real and is REPORTED, not papered over: it needs a PO ruling of
    its own before anyone treats the trial balance as partition-pruned.

The registry below is the NFR-24 mandatory set. Each entry carries its wave so
the create-ahead job never invents DDL for a table that is not there yet.

Four laws this module makes structural:
1. CREATE-AHEAD (B2 §5): partitions exist BEFORE rows need them — the current
   period plus `create_ahead` more (3 months for a monthly table, 1 year for a
   yearly one), maintained by a scheduled job (`manage.py maintain_partitions`,
   celery-beat wiring lands with the jobs story). A missing partition would
   fail INSERTs loudly; the job makes that impossible.
2. DETACH, NEVER DROP (NFR-25): after a table's hot window (24 months) a
   partition becomes a DETACH candidate — moved toward cold storage but still
   queryable for reprice/audit/drill-back. There is deliberately NO drop API
   in this module (same posture as core.numbering's missing renumber API):
   financial partitions are never pruned, and even non-financial data leaves
   hot storage only by DETACH through the EP-AUD-03 archival story.
3. GUARDED AT BIRTH (DEF-027, CLAUDE.md rule 1): every partition this module
   mints is created AND given its B2 §3 tenant policy in ONE statement batch,
   inside ONE transaction. See the ⚠ block below — this replaced a claim in
   law 3 that was simply false.
4. TENANT-NEUTRAL DDL: partitioning is platform DDL, not tenant work — no
   tenant context is read or required here. Which tenant is running the job
   does not matter; that the partition carries the tenant policy does.

⚠ DEF-027 — WHY LAW 3 EXISTS, AND WHAT IT REPLACED

This docstring used to end law 3 with: *"RLS on the parent keeps every query
tenant-scoped regardless of which partition serves it."* That is a comment
claiming a guarantee that was never written (Hard-won law 1), and it was
measured false on the live cluster on 2026-08-10:

    SELECT * FROM audit_log_2026_08;     -- every tenant's audit trail
    SELECT * FROM meter_reads_2026_08;   -- every tenant's reads

PostgreSQL applies a partitioned parent's row policies when rows are reached
THROUGH the parent. **A partition queried DIRECTLY consults only its own
policies**, and `CREATE TABLE … PARTITION OF` gives a partition none.

`apps/audit/0003` and `apps/metering/0004` closed the partitions that existed
on 2026-08-10. They could not close the ones that do not exist yet: the
create-ahead job below mints new partitions every month, and it did not apply
policies, so next month's partition would be born unguarded and the leak would
return on a schedule. That is the half this module now owns.

The fix is deliberately structural rather than a second step someone must
remember: `create_partition_sql()` — the ONLY producer of `PARTITION OF` DDL in
this codebase — emits the guard in the same string as the CREATE, and there is
NO create-only variant to reach for (same posture as the missing drop API).
Postgres DDL is transactional, so no other session can ever observe the
partition in its unguarded state.
"""

import re
from dataclasses import dataclass
from datetime import date

from django.db import connection, transaction

from core.rls import tenant_isolation_policy_sql

# ── the NFR-24 registry (RANGE partitions; partition-key column per B2 §5) ──
HOT_MONTHS_DEFAULT = 24  # 2-year hot window (NFR-6/25/28)

#: The two granularities this product uses, and nothing else. MONTH is NFR-24 as
#: signed; YEAR is the PO ruling of 2026-08-12 for the two financial line tables.
MONTHLY = "month"
YEARLY = "year"


@dataclass(frozen=True)
class PartitionedTable:
    table: str
    key_column: str  # RANGE partition key (timestamptz per B2)
    financial: bool  # NFR-25: financial data is never pruned, ever
    wave: str  # when the table lands (only landed tables get DDL)
    granularity: str = MONTHLY  # MONTHLY (NFR-24) | YEARLY (PO 2026-08-12)
    create_ahead: int = 3  # periods pre-created by the job (B2 §5)
    hot_months: int = HOT_MONTHS_DEFAULT


REGISTRY: dict[str, PartitionedTable] = {
    t.table: t
    for t in (
        PartitionedTable("audit_log", "created_at", financial=False, wave="W0"),
        PartitionedTable("meter_reads", "read_at", financial=False, wave="W2"),
        # ── the two the PO ruled yearly (OQ-107, 2026-08-12) ───────────────
        # key_column was `period_start` here until 2026-08-15 and could never
        # have been used: the column is NULLABLE and a NULL RANGE key routes to
        # no partition. See the ⚠ block in the module docstring — B2 §5 names
        # `created_at` as the other signed candidate, and that is what shipped.
        PartitionedTable(
            "invoice_lines",
            "created_at",
            financial=True,
            wave="W3",
            granularity=YEARLY,
            create_ahead=1,
        ),
        PartitionedTable(
            "journal_lines",
            "created_at",
            financial=True,
            wave="W5",
            granularity=YEARLY,
            create_ahead=1,
        ),
        # RULED unpartitioned — PO 2026-08-11 (OQ-108): monthly RANGE would force
        # created_at into every unique constraint and switch CLAUDE.md hard rule 6
        # off. Registered because NFR-24 names it; never in ACTIVE_TABLES.
        PartitionedTable("outbound_messages", "created_at", financial=False, wave="W6"),
        # ── CR-069 (2026-09-03): the integrations run record ──────────────────
        # `integration_run` — every attempt against an outside system, as a row
        # (BR-INT-039). YEARLY on `started_at`, which is therefore NOT NULL
        # (B2 Addendum r22). Not in NFR-24's list: that sentence names the five
        # tables of the ORIGINAL product, and this table did not exist when it
        # was signed. It is partitioned for the same reason the two yearly
        # financial tables are — volume with detach-by-age — and it joins
        # ACTIVE_TABLES the moment `integrations/0001` creates it, so the
        # create-ahead job renews it and every new partition is born guarded
        # (DEF-027). Not financial: it records that money moved, never the money.
        PartitionedTable(
            "integration_run",
            "started_at",
            financial=False,
            wave="CR-069 A",
            granularity=YEARLY,
            create_ahead=1,
        ),
    )
}

# Which of the five exist as partitioned parents today. Extended by each
# landing story (the migration that creates the parent flips its entry on).
#
# `meter_reads` landed with `apps/metering/0003_w2_reads` (W2) but was NOT
# flipped on here, because flipping it also means changing the test that pins
# this frozenset and that belonged to core/'s owner — 0003's docstring reported
# the gap rather than reaching into this lane. It is flipped on now (2026-08-10,
# DEF-027), and it closes a SECOND, quieter failure: 0003 bootstraps a fixed
# 28-partition window (24 months back + 3 ahead) and nothing renewed it, so
# reads INSERTs would have started failing once that window ran out. The
# create-ahead job now renews meter_reads like audit_log.
#
# `invoice_lines` and `journal_lines` joined on 2026-08-15 with the two
# migrations that rebuilt them as yearly parents (billing 0016, ledger 0005) —
# in the SAME change, deliberately: a partitioned parent outside this set gets
# neither renewed nor guarded, which is the failure `meter_reads` demonstrated.
#
# `outbound_messages` is absent on purpose and permanently (PO 2026-08-11).
#
# The guard against the next table repeating this: the DB-side check in
# tests/test_def_027_partition_rls_create_ahead.py fails if ANY partitioned
# parent in the database is missing from this set.
#
# THE ASSIGNMENT BELOW IS ONE LINE ON PURPOSE, AND THE ANNOTATION IS SPLIT OFF
# TO KEEP IT THAT WAY. G16 check C reads this set straight out of the source to
# tie it out against what the migrations really create, and its parser expects
# the set literal to open immediately after `frozenset(` on the same line.
# Four names no longer fit in 100 columns with the annotation attached, and
# black would then wrap it out of the gate's sight. G16 is PO-ratified law
# (2026-08-11) — "a loosening here — an allowlist entry, a skipped check, a
# widened pattern — is a change to a ratified decision" — so the gate was left
# exactly as it is and this file bent around it. Do not merge these two lines.
#
# (Nothing above may spell that assignment out in a comment either: the parser
# takes the first match in the file, and an illustrative one would win and
# report an EMPTY set. Found the hard way on 2026-08-15.)
ACTIVE_TABLES: frozenset[str]
ACTIVE_TABLES = frozenset({"audit_log", "meter_reads", "invoice_lines", "journal_lines", "integration_run"})  # fmt: skip

# NFR-25 names these outright (invoices/payments/allocations are not in the
# partition set but belong to the same never-prune law — kept here so any
# future partitioning of them inherits the protection by name).
FINANCIAL_NEVER_PRUNED: frozenset[str] = frozenset(
    {"journal_lines", "invoice_lines", "invoices", "payments", "allocations"}
)

_SAFE_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class PartitioningError(RuntimeError):
    """Misuse of the partition contract — fails the caller loudly."""


def _check_name(name: str) -> str:
    # DDL is assembled from registry constants + computed digits only; this
    # guard makes that assumption structural (nothing user-shaped reaches DDL).
    if not _SAFE_NAME_RE.match(name):
        raise PartitioningError(f"unsafe SQL identifier {name!r}")
    return name


# ── period math (pure — the tested half) ────────────────────────────────────
def month_start(day: date) -> date:
    return day.replace(day=1)


def add_months(month: date, count: int) -> date:
    """First-of-month arithmetic; input is normalized to its month start."""
    base = month.year * 12 + (month.month - 1) + count
    return date(base // 12, base % 12 + 1, 1)


def year_start(day: date) -> date:
    return date(day.year, 1, 1)


def add_years(year: date, count: int) -> date:
    """First-of-year arithmetic; input is normalized to its year start."""
    return date(year.year + count, 1, 1)


def granularity_of(table: str) -> str:
    """MONTHLY unless the registry says otherwise.

    Unregistered names fall through to MONTHLY rather than raising, so the
    identifier guard in `partition_name` is still the thing that rejects them —
    the safety check must not be reachable only for registered tables.
    """
    entry = REGISTRY.get(table)
    return entry.granularity if entry else MONTHLY


def partition_period(table: str, day: date) -> date:
    """The first day of the partition period `day` falls in, for `table`."""
    return year_start(day) if granularity_of(table) == YEARLY else month_start(day)


def add_periods(table: str, period: date, count: int) -> date:
    """`count` partition periods after `period`, in `table`'s granularity."""
    if granularity_of(table) == YEARLY:
        return add_years(year_start(period), count)
    return add_months(month_start(period), count)


def partition_name(table: str, period: date) -> str:
    """B2 §5 / US-AUD-001 TC-1 grammar, one form per granularity:

        monthly  <table>_YYYY_MM   audit_log_2026_08
        yearly   <table>_YYYY      journal_lines_2026   (PO 2026-08-12)

    The two forms cannot collide — a yearly name has no month segment — so a
    table that ever changed granularity would not silently reuse a name.
    """
    _check_name(table)
    if granularity_of(table) == YEARLY:
        return f"{table}_{period.year:04d}"
    return f"{table}_{period.year:04d}_{period.month:02d}"


def month_bounds(month: date) -> tuple[date, date]:
    """[first of month, first of next month) — Postgres RANGE convention."""
    start = month_start(month)
    return start, add_months(start, 1)


def year_bounds(year: date) -> tuple[date, date]:
    """[first of year, first of next year) — Postgres RANGE convention."""
    start = year_start(year)
    return start, add_years(start, 1)


def partition_bounds(table: str, period: date) -> tuple[date, date]:
    """The half-open RANGE bounds of one partition, in `table`'s granularity."""
    return year_bounds(period) if granularity_of(table) == YEARLY else month_bounds(period)


def plan_create_ahead(table: str, today: date, ahead: int | None = None) -> list[str]:
    """The partitions that must exist as of `today`: the current period plus
    `ahead` more (B2 §5). `ahead` defaults to the table's registry value — 3
    for a monthly table, 1 for a yearly one, which is the same span of runway
    expressed in each table's own units. Returns partition names in order."""
    entry = REGISTRY.get(table)
    if entry is None:
        raise PartitioningError(f"{table!r} is not in the NFR-24 partition registry")
    if ahead is None:
        ahead = entry.create_ahead
    current = partition_period(table, today)
    return [partition_name(table, add_periods(table, current, i)) for i in range(ahead + 1)]


def detach_candidates(table: str, today: date, existing_periods: list[date]) -> list[str]:
    """Partitions past the table's hot window (NFR-25/28): DETACH candidates
    for the archival story — candidates only, nothing is executed here, and
    nothing is ever dropped (there is no drop API in this module).

    The hot window is stated in MONTHS for every table (NFR-6/25/28 all say 24).
    For a yearly table the horizon is rounded DOWN to its year, so a yearly
    partition only becomes a candidate once every month it holds is outside the
    window — a 24-month promise is never shortened by the coarser granularity.
    """
    entry = REGISTRY.get(table)
    if entry is None:
        raise PartitioningError(f"{table!r} is not in the NFR-24 partition registry")
    horizon = partition_period(table, add_months(month_start(today), -entry.hot_months))
    return [
        partition_name(table, p)
        for p in sorted(existing_periods)
        if partition_period(table, p) < horizon
    ]


def create_partition_sql(table: str, period: date) -> str:
    """The COMPLETE DDL for one partition: create it AND guard it.

        CREATE TABLE IF NOT EXISTS <t>_<period> PARTITION OF <t> FOR VALUES …;
        ALTER TABLE <t>_<period> ENABLE ROW LEVEL SECURITY;
        ALTER TABLE <t>_<period> FORCE ROW LEVEL SECURITY;
        DROP POLICY IF EXISTS … ;  CREATE POLICY <t>_<period>_tenant_isolation …

    ONE string on purpose (DEF-027, law 3 above). Postgres runs a multi-
    statement batch in one implicit transaction and its DDL is transactional,
    so either the partition exists WITH its tenant policy or it does not exist:
    no other session can ever read it in between. Callers that already hold a
    transaction get the same guarantee from that transaction.

    The policy text is `core.rls.tenant_isolation_policy_sql` — the SIGNED B2 §3
    template, unmodified. This module invents no policy shape.

    There is deliberately NO create-only variant here, for the same reason
    there is no drop API: a second step that must be remembered is a step that
    will eventually be forgotten, and forgetting this one leaks every tenant's
    rows. Idempotent — safe to re-run, and re-running is the remediation path.
    """
    _check_name(table)
    start, end = partition_bounds(table, period)
    name = partition_name(table, period)
    return (
        f"CREATE TABLE IF NOT EXISTS {name} PARTITION OF {table} "
        f"FOR VALUES FROM ('{start.isoformat()}') TO ('{end.isoformat()}');\n"
        f"{tenant_isolation_policy_sql(name)}"
    )


# ── the catalog half: what the database actually has ────────────────────────
def is_partitioned_parent(table: str) -> bool:
    """True when `table` really is a PARTITIONED table in THIS database.

    `ACTIVE_TABLES` is a claim made in code; this is the database's answer. The
    two disagree on any host whose migrations are behind, and the job needs to
    say which one it is rather than emitting DDL that fails obscurely.
    """
    _check_name(table)
    if connection.vendor != "postgresql":
        return False
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relkind = 'p' FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = %s",
            [table],
        )
        row = cursor.fetchone()
    return bool(row and row[0])


def partition_children(table: str) -> list[str]:
    """Every existing partition of `table`, straight from `pg_inherits`.

    Empty on non-Postgres vendors (sqlite test DB has a plain table).
    """
    _check_name(table)
    if connection.vendor != "postgresql":
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = %s ORDER BY c.relname",
            [table],
        )
        return [row[0] for row in cursor.fetchall()]


def unguarded_partitions(table: str) -> list[str]:
    """Partitions of `table` missing ENABLE, FORCE, or a policy of their own.

    The same catalog question the isolation guard asks — kept here so the job
    can REPAIR what the guard would only name.
    """
    _check_name(table)
    if connection.vendor != "postgresql":
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_inherits i "
            "JOIN pg_class p ON p.oid = i.inhparent "
            "JOIN pg_class c ON c.oid = i.inhrelid "
            "WHERE p.relname = %s AND (NOT c.relrowsecurity OR NOT c.relforcerowsecurity "
            "OR (SELECT count(*) FROM pg_policy pol WHERE pol.polrelid = c.oid) < 1) "
            "ORDER BY c.relname",
            [table],
        )
        return [row[0] for row in cursor.fetchall()]


def ensure_partition_policies(table: str) -> list[str]:
    """Guard every partition of `table` that is not already guarded.

    Returns the names repaired (empty when there was nothing to do). This is
    the remediation path `apps/audit/0003` and `apps/metering/0004` each point
    at: partitions minted before DEF-027, or by any hand outside this module,
    are healed the next time the create-ahead job runs.

    Only actually-unguarded partitions are touched — each fix takes an ACCESS
    EXCLUSIVE lock, so a healthy table pays nothing but one catalog query.
    """
    if connection.vendor != "postgresql":
        return []
    repaired = unguarded_partitions(table)
    if not repaired:
        return []
    with transaction.atomic():
        with connection.cursor() as cursor:
            for partition in repaired:
                cursor.execute(tenant_isolation_policy_sql(partition))
    return repaired


# ── the create-ahead job body (Postgres executor) ───────────────────────────
def ensure_partitions(table: str, today: date, ahead: int | None = None) -> list[str]:
    """Create (idempotently) the current + `ahead` partitions for one
    registered, ACTIVE table, each one guarded in the same breath. Returns the
    partition names ensured. No-op with a loud error on a table whose parent
    has not landed yet; honest no-op on non-Postgres vendors (sqlite tests —
    the DDL would be a lie there).

    Named `ensure_monthly_partitions` until 2026-08-15. It was renamed rather
    than aliased because two of the four active tables are now YEARLY (PO
    2026-08-12) and a function whose NAME says monthly while it mints yearly
    partitions is exactly the kind of sentence hard-won law 1 is about.

    Two things happen, both idempotent (DEF-027):
      1. current + `ahead` partitions are created WITH their B2 §3 policy, in
         one transaction — an unguarded partition is never a reachable state;
      2. any OLDER partition found unguarded is repaired, so running the job is
         also the remediation for whatever predates this guarantee.
    """
    if table not in ACTIVE_TABLES:
        raise PartitioningError(
            f"{table!r} has no partitioned parent yet (lands {REGISTRY[table].wave})"
            if table in REGISTRY
            else f"{table!r} is not in the NFR-24 partition registry"
        )
    names = plan_create_ahead(table, today, ahead)
    if connection.vendor != "postgresql":
        return names  # sqlite test DB: plain table, no partitions to ensure
    if not is_partitioned_parent(table):
        # ACTIVE_TABLES says the parent landed; this database says otherwise, so
        # the host is behind on migrations. Raised — never skipped: skipping
        # would stop partitions being created and the first anyone would hear of
        # it is failing INSERTs. Measured on the dev cluster 2026-08-10, where
        # the raw psycopg error was `relation "meter_reads" does not exist` and
        # said nothing about what to do.
        raise PartitioningError(
            f"{table!r} is in ACTIVE_TABLES but is not a partitioned table in this "
            f"database — this host is behind on migrations (run `manage.py migrate`); "
            f"until it catches up, {table}'s partitions are neither created nor guarded"
        )
    current = partition_period(table, today)
    with transaction.atomic():
        with connection.cursor() as cursor:
            for i in range(len(names)):
                cursor.execute(create_partition_sql(table, add_periods(table, current, i)))
    ensure_partition_policies(table)
    return names


def partition_names_between(table: str, first: date, last: date) -> list[str]:
    """Every partition name from the period holding `first` to the period
    holding `last`, inclusive. Refuses a backwards range rather than returning
    an empty list a caller would read as "nothing to do"."""
    start = partition_period(table, first)
    end = partition_period(table, last)
    if end < start:
        raise PartitioningError(f"{table!r}: range ends ({last}) before it starts ({first})")
    names: list[str] = []
    period = start
    while period <= end:
        names.append(partition_name(table, period))
        period = add_periods(table, period, 1)
    return names


def ensure_partitions_cover(table: str, first: date, last: date) -> list[str]:
    """Create (idempotently, each WITH its tenant policy) every partition from
    `first` to `last` inclusive — for a writer that knows which dates it is
    about to write, however old. `DEF-INF-9033`.

    ⚠ **WHY THIS EXISTS BESIDE `ensure_partitions`.** That job creates the
    CURRENT period and the ones ahead; `metering/0003` bootstraps 24 months
    BACK from the day it runs. Both windows are relative to a CLOCK, so a writer
    with FIXED dates — the e2e fixture writes from September 2024 — works on a
    database migrated in September 2026 and fails on one migrated in October,
    with *"no partition of relation meter_reads found for row"*. Moving the
    writer's dates would only move the day it breaks; asking for the months it
    writes is the fix, and this is the one place that may create them, so a
    partition is never reachable without its policy (DEF-027).

    Honest no-op off PostgreSQL (the SQLite test table is not partitioned).
    """
    if table not in ACTIVE_TABLES:
        raise PartitioningError(f"{table!r} is not an active partitioned table")
    names = partition_names_between(table, first, last)
    if connection.vendor != "postgresql":
        return names
    if not is_partitioned_parent(table):
        raise PartitioningError(
            f"{table!r} is not a partitioned table in this database — run `manage.py migrate`"
        )
    period = partition_period(table, first)
    with transaction.atomic():
        with connection.cursor() as cursor:
            for _ in names:
                cursor.execute(create_partition_sql(table, period))
                period = add_periods(table, period, 1)
    ensure_partition_policies(table)
    return names


# ── converting a table that ALREADY HOLDS ROWS (OQ-107, 2026-08-12) ─────────
#
# ⚠ READ THIS BEFORE CHANGING ANYTHING BELOW. `invoice_lines` and `journal_lines`
# are covered by CLAUDE.md hard rule 4 and hold a utility's books.
#
# PostgreSQL CANNOT convert an existing table to a partitioned one in place.
# There is no `ALTER TABLE … PARTITION BY`. Every route is the same route: build
# a new partitioned parent, put the rows in it, and let the old heap go. So this
# IS a data migration, it is stated as one, and the two migrations that call it
# (billing 0016, ledger 0005) say the same thing in their own docstrings.
#
# What it does NOT do — and this is the part hard rule 4 cares about — is UPDATE
# or DELETE a single row. The rows are read once and INSERTed into the new
# parent verbatim; the old heap leaves by DROP TABLE, which is not a row-level
# delete and does not run the immutability triggers because there is nothing for
# them to refuse. Every value is carried across unchanged, and that claim is not
# left as a comment (hard-won law 1): `_tie_out` takes the row count, the sum of
# the money column and an md5 over the FULL TEXT of every row before the copy
# and again after it, and a single differing byte aborts the transaction with
# both figures named. Nothing is dropped until the tie-out has matched.
#
# Indexes, CHECK constraints, foreign keys and triggers are NOT re-declared
# here. They are read out of the catalog with `pg_get_indexdef` /
# `pg_get_constraintdef` / `pg_get_triggerdef` BEFORE the swap — while they
# still name the table by its real name — and replayed verbatim onto the new
# parent afterwards. That is deliberate: restating another module's immutability
# trigger or FK set in this file would be a second copy free to drift from the
# first, and the whole point of `journal_lines` is that its guarantees do not
# drift. PostgreSQL clones a parent's row triggers onto every partition,
# including partitions created later by the create-ahead job (measured on
# PG 16.13 — a partition added after the trigger carries it).
#
# DEF-064: every statement below goes through `cursor.execute(sql)` with NO
# params argument, so psycopg never attempts %-interpolation on it. There is no
# `%` in any SQL this module builds, and `tests/test_oq_107_yearly_partitions.py`
# asserts that for the migration bodies too.

#: The old heap's name for the length of one transaction. Never a live table.
_ASIDE_SUFFIX = "__unpartitioned_aside"


def _live_columns(cursor, table: str) -> list[str]:
    """The table's columns, in attribute order, straight from the catalog."""
    cursor.execute(
        "SELECT a.attname FROM pg_attribute a "
        "WHERE a.attrelid = to_regclass(%s) AND a.attnum > 0 AND NOT a.attisdropped "
        "ORDER BY a.attnum",
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _index_definitions(cursor, table: str) -> list[str]:
    """`CREATE INDEX …` for every index NOT backed by a constraint.

    Constraint-backed indexes (PRIMARY KEY, UNIQUE) come back through
    `_constraint_definitions`, or — for the primary key — are restated by the
    target DDL, because a partitioned table's PK must contain the partition key.
    """
    cursor.execute(
        "SELECT pg_get_indexdef(i.indexrelid) FROM pg_index i "
        "WHERE i.indrelid = to_regclass(%s) "
        "AND NOT EXISTS (SELECT 1 FROM pg_constraint c WHERE c.conindid = i.indexrelid) "
        "ORDER BY 1",
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _constraint_definitions(cursor, table: str) -> list[tuple[str, str]]:
    """(name, definition) for CHECK / FOREIGN KEY / UNIQUE constraints.

    The PRIMARY KEY is excluded on purpose: the target DDL declares it, because
    PostgreSQL requires the partition key inside it.
    """
    cursor.execute(
        "SELECT c.conname, pg_get_constraintdef(c.oid) FROM pg_constraint c "
        "WHERE c.conrelid = to_regclass(%s) AND c.contype IN ('c', 'f', 'u') "
        "ORDER BY c.contype DESC, c.conname",
        [table],
    )
    return [(row[0], row[1]) for row in cursor.fetchall()]


def _trigger_definitions(cursor, table: str) -> list[str]:
    """`CREATE [CONSTRAINT] TRIGGER …` for every non-internal trigger.

    Captured BEFORE the swap, so each statement already names the table by the
    name the NEW parent will carry, and is replayed unchanged. The trigger
    FUNCTIONS are untouched throughout — `DROP TABLE` does not remove them.
    """
    cursor.execute(
        "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
        "WHERE t.tgrelid = to_regclass(%s) AND NOT t.tgisinternal ORDER BY t.tgname",
        [table],
    )
    return [row[0] for row in cursor.fetchall()]


def _tie_out(cursor, table: str, money_column: str | None) -> tuple[int, str, str]:
    """(row count, money total, md5 of every row's full text) — the proof.

    The md5 is taken over `row::text`, so it moves if ANY column of ANY row
    differs by one character, including a numeric that lost a decimal place to a
    type change. Ordered by `id` so the digest is stable.
    """
    money = f"coalesce(sum({money_column}), 0)::text" if money_column else "''::text"
    cursor.execute(
        f"SELECT count(*)::bigint, {money}, "
        f"coalesce(md5(string_agg(t::text, chr(10) ORDER BY t.id)), '') FROM {table} t"
    )
    row = cursor.fetchone()
    return int(row[0]), str(row[1]), str(row[2])


def _period_span(cursor, table: str, source: str, today: date, ahead: int) -> list[date]:
    """Every partition period the rebuilt table needs, oldest first.

    Wide enough for the data that exists (a utility's cutover import carries
    years of history) AND for the create-ahead runway, so the first INSERT after
    the migration cannot land on a missing partition.
    """
    entry = REGISTRY[table]
    cursor.execute(f"SELECT min({entry.key_column}), max({entry.key_column}) FROM {source}")
    low, high = cursor.fetchone()
    current = partition_period(table, today)
    first = partition_period(table, low.date() if hasattr(low, "date") else low) if low else current
    last = (
        partition_period(table, high.date() if hasattr(high, "date") else high) if high else current
    )
    first = min(first, current)
    last = max(last, current)
    periods = []
    cursor_period = first
    while cursor_period <= last:
        periods.append(cursor_period)
        cursor_period = add_periods(table, cursor_period, 1)
    for i in range(1, ahead + 1):
        periods.append(add_periods(table, last, i))
    return periods


def _rebuild(
    schema_editor,
    *,
    table: str,
    target_ddl: str,
    columns: list[str],
    partitioned: bool,
    today: date,
    money_column: str | None,
) -> dict:
    """Replace `table` with a table built by `target_ddl`, carrying every row.

    Returns a report dict the migration prints. Raises `PartitioningError` —
    which aborts the migration's transaction and therefore changes nothing —
    on any of: a column set that is not what `target_ddl` describes, a leftover
    aside table, or a tie-out that does not match to the byte.
    """
    _check_name(table)
    connection_ = schema_editor.connection
    if connection_.vendor != "postgresql":
        # sqlite test DB keeps the plain table, exactly as apps/metering/0003
        # does: partition DDL there would be a lie. The live assertions are the
        # G5 isolation suite's.
        return {"table": table, "skipped": f"vendor {connection_.vendor}"}

    aside = f"{table}{_ASIDE_SUFFIX}"
    _check_name(aside)

    with connection_.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s) IS NOT NULL", [aside])
        if cursor.fetchone()[0]:
            raise PartitioningError(
                f"{aside} already exists — a previous rebuild of {table} did not finish "
                "inside its transaction. Do NOT re-run this migration until a human has "
                "looked at that table: it holds rows."
            )

        live = _live_columns(cursor, table)
        if live != list(columns):
            raise PartitioningError(
                f"{table} in this database does not have the columns this migration was "
                f"written against, so the DDL below would silently reshape the books.\n"
                f"  database: {live}\n  migration: {list(columns)}\n"
                "Nothing was changed. A column added to this table after this migration "
                "was authored must be added to its DDL and its column list together."
            )

        indexes = _index_definitions(cursor, table)
        constraints = _constraint_definitions(cursor, table)
        triggers = _trigger_definitions(cursor, table)

        # Aside, and out of RLS's way for the length of the copy. NO FORCE is the
        # narrowest door there is: it exempts the table OWNER (the role running
        # the migration) and nobody else, the table no longer answers to its
        # public name, and Postgres DDL is transactional — no other session can
        # observe any of this.
        cursor.execute(f"ALTER TABLE {table} RENAME TO {aside};")
        cursor.execute(f"ALTER TABLE {aside} NO FORCE ROW LEVEL SECURITY;")

        before = _tie_out(cursor, aside, money_column)

        cursor.execute(target_ddl)
        periods: list[date] = []
        if partitioned:
            periods = _period_span(cursor, table, aside, today, REGISTRY[table].create_ahead)
            for period in periods:
                cursor.execute(create_partition_sql(table, period))

        column_list = ", ".join(columns)
        cursor.execute(f"INSERT INTO {table} ({column_list}) SELECT {column_list} FROM {aside};")

        after = _tie_out(cursor, table, money_column)
        if after != before:
            raise PartitioningError(
                f"{table} did not tie out after the copy and NOTHING has been committed.\n"
                f"  before (rows, {money_column or 'n/a'} total, row digest): {before}\n"
                f"  after : {after}\n"
                "The transaction is being rolled back with every original row still in "
                "place. Do not retry until the difference is understood."
            )

        # Only now — the old rows are provably reproduced.
        cursor.execute(f"DROP TABLE {aside};")

        for sql in indexes:
            cursor.execute(sql)
        for name, definition in constraints:
            cursor.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} {definition};")
        for sql in triggers:
            cursor.execute(sql)

        # The parent's own guard. Every partition already carries its own,
        # emitted by create_partition_sql in the same batch that created it.
        cursor.execute(tenant_isolation_policy_sql(table))

    return {
        "table": table,
        "partitioned": partitioned,
        "rows": before[0],
        "money_total": before[1],
        "digest": before[2],
        "partitions": [partition_name(table, p) for p in periods],
        "indexes": len(indexes),
        "constraints": len(constraints),
        "triggers": len(triggers),
    }


def convert_to_partitioned(
    schema_editor,
    *,
    table: str,
    parent_ddl: str,
    columns: list[str],
    today: date,
    money_column: str | None = None,
) -> dict:
    """Rebuild an existing flat `table` as a partitioned parent, rows and all.

    Idempotent: a table that is already a partitioned parent is left alone, so
    re-running the migration on a host that has it is a no-op rather than a
    second rebuild.
    """
    if schema_editor.connection.vendor != "postgresql":
        return {"table": table, "skipped": f"vendor {schema_editor.connection.vendor}"}
    if is_partitioned_parent(table):
        return {"table": table, "skipped": "already a partitioned parent"}
    return _rebuild(
        schema_editor,
        table=table,
        target_ddl=parent_ddl,
        columns=columns,
        partitioned=True,
        today=today,
        money_column=money_column,
    )


def convert_to_flat(
    schema_editor,
    *,
    table: str,
    flat_ddl: str,
    columns: list[str],
    money_column: str | None = None,
) -> dict:
    """The reverse of `convert_to_partitioned` — one heap again, rows and all.

    A migration on the books that cannot be reversed is one a deploy cannot back
    out of, so the reverse is a real implementation and not a `noop` that would
    report success while leaving the table partitioned.
    """
    if schema_editor.connection.vendor != "postgresql":
        return {"table": table, "skipped": f"vendor {schema_editor.connection.vendor}"}
    if not is_partitioned_parent(table):
        return {"table": table, "skipped": "not a partitioned parent"}
    return _rebuild(
        schema_editor,
        table=table,
        target_ddl=flat_ddl,
        columns=columns,
        partitioned=False,
        today=date.today(),
        money_column=money_column,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-AUD-001@b2ae555 (story+rules snapshot hash; component row BE-10@05736ee)
# generated: 2026-08-09 by story-coder v1 (R1 critical path, W0 migrations lane)
# revised: 2026-08-10 — DEF-027 second half: partitions are created AND guarded in one
#          transaction (create_partition_sql emits the B2 §3 policy), unguarded partitions
#          are repaired on every job run, and meter_reads joined ACTIVE_TABLES
# revised: 2026-08-15 — OQ-107 (PO 2026-08-12, "Nod to split both by year"): the registry
#          carries a GRANULARITY, invoice_lines and journal_lines are YEARLY and joined
#          ACTIVE_TABLES with billing 0016 / ledger 0005, ensure_monthly_partitions was
#          RENAMED to ensure_partitions (two of the four active tables are no longer
#          monthly, so the old name had stopped being true), and the rebuild machinery
#          for a table that already holds rows landed here rather than in either
#          migration — one producer of PARTITION OF DDL, as this module already required
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09 — 🔒-adjacent HUMAN-REVIEW-PENDING, ledger row appended)
# gates: ruff✔ black✔ py_compile✔ pytest tests/test_be10_partitioning.py✔ · suite 180/180✔ (147 baseline + 33 W0) · run_gates✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
#        2026-08-10 re-run: sqlite 1056 passed/10 skipped (baseline 1052) · live-PG isolation 55 passed/12 skipped (baseline 48) · sqlite isolation 14 passed/53 skipped · ruff✔ black✔ · run_gates 14 PASS/0 FAIL/1 SKIP · proved RED first (create-only DDL ⇒ the guards named audit_log_2029_02/03 + meter_reads_2029_02/03 and the 8 partitions maintain_partitions minted)
# exceptions: DETACH execution (cold-storage attach target) deferred to EP-AUD-03 per its epic — candidates surfaced, nothing executed; celery-beat schedule wiring lands with the jobs-table story (command exists: manage.py maintain_partitions) · the per-partition policy text is built from core/rls.py rather than a db/rls_*.sql file because a partition's NAME is only known at run time — the fixed-table policies stay in 06-backend/db/ · THE PARTITION KEY IS `created_at` FOR BOTH YEARLY TABLES AND THE PO WAS NEVER ASKED THE KEY — they ruled the granularity ("by year") on 2026-08-12; B2 §5 names created_at as a signed candidate for both, invoice_lines.period_start is NULLABLE and cannot be a RANGE key, and journal_lines has no book date at all (entry_date lives on journal_entries and is MUTABLE while the entry is a draft, BR-LED-003). The Eng-Lead reading of 2026-08-11 — that the book date should be the key so a trial balance prunes — is NOT implemented and is reported for a ruling, not assumed · the conversion COPIES rows into a new heap because PostgreSQL has no in-place ALTER TABLE … PARTITION BY; nothing is UPDATEd or DELETEd and a count/sum/row-digest tie-out aborts the transaction before the old heap is released
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

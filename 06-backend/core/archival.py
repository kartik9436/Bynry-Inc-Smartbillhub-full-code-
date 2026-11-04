# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-020 (metering — auto-archival job: 2-yr hot window → cold
#           storage, 7-yr retention) · US-AUD-007 (audit — the same job over
#           `audit_log`, "audited, never manual") · US-AUD-008 / US-MET-020 TC-3
#           (the cold read path those two archive INTO)   Screens: S25 · S61
# Rules:    BR-MET-055 (2 yr hot → archive, 7 yr total, AUTOMATIC scheduled job,
#           never manual, audited) · BR-AUD-012 (the identical rule for
#           `audit_log`; NFR-28 "matches reads pattern") · BR-AUD-002 (archival
#           MOVES partitions; it never UPDATEs or DELETEs a row in the
#           operational path) · NFR-25 (financial tables are NEVER pruned) ·
#           NFR-24/NFR-28 (the mandatory monthly partition set) · CLAUDE.md
#           rule 1 (a detached partition keeps its own tenant policy — DEF-027)
# Tests:    06-backend/tests/test_us_met_020_tc_archival.py (the metering half,
#           per-TC) · 06-backend/tests/test_us_aud_007_tc_archival.py (the audit
#           half + the self-audit rows) · both run the pure planner on any
#           vendor and the live DETACH/DROP on Postgres only
# Impacts:  core/partitioning.py (detach CANDIDATES — this module executes them) ·
#           apps/audit (hosts `archive_job_runs` + writes the self-audit rows) ·
#           apps/metering (its partitions are archived by the same run) ·
#           apps/audit/selectors.py + apps/metering/selectors.py (archive reads)
# ───────────────────────────────────────────────────────
"""THE RETENTION LAW, WRITTEN ONCE — 2 years hot, 7 years total.

HUMAN-OWNED (🔒-adjacent: partition DDL is migration-ordering-adjacent,
CLAUDE.md list). HUMAN-REVIEW-PENDING — AI-authored 2026-08-15 under the PO
ruling of 2026-08-09 ("AI will do it; we will review it later as human"),
implementing SIGNED law only (BR-MET-055 · BR-AUD-012 · NFR-24/25/28). A row is
requested in 12-governance/09-human-review-ledger.md; this file must not reach
RATIFIED without a recorded human sign-off.

WHY ONE MODULE AND NOT TWO
--------------------------
US-MET-020 (`meter_reads`) and US-AUD-007 (`audit_log`) are the SAME rule twice.
NFR-28 says so in as many words — the audit retention "matches reads pattern" —
and US-AUD-007 §5 asks for "one mechanism, two tables". Two implementations of
one bound is two places for 24 and 84 to drift apart, and the drift would be
invisible: each job would keep passing its own tests. So the bound lives here,
in constants both stories import, and the executor below is table-agnostic.

WHAT "COLD STORAGE" IS, CONCRETELY — read this before believing anything else
------------------------------------------------------------------------------
Both stories' §4 name an object-store URI as their fixture
(`s3://smartbillhub-archive/prod/…`). **This module ships no object-store
client and does not pretend to.** What it actually does, and what the run record
therefore actually claims:

  1. DETACH the partition from its parent. The rows leave the hot table for
     good — every hot query is planned against the parent, so nothing on the
     hot path pays for them any more. That is the half the performance rule
     (NFR-3/BR-MET-055) is about, and it is real.
  2. The detached table REMAINS IN THE DATABASE, still carrying its own B2 §3
     tenant policy (DEF-027 — `create_partition_sql` emitted it in the same
     batch that created the partition, and DETACH does not remove it). That is
     what makes US-MET-020 TC-3 / US-AUD-008 possible at all: archived rows stay
     readable, read-only, under `app.tenant_id`, exactly like hot rows.
  3. A SHA-256 manifest over the partition's full row text is computed and
     recorded with the row count, so a later shipment can be verified against
     what was archived — the "checksummed" half of both stories' TC-1. It is
     computed ONE UTILITY AT A TIME (see `_manifest`), because the tables being
     archived are under FORCE row-level security and there is no identity that
     can see all of a partition at once.
  4. SHIPPING the detached table off-database is a registered seam
     (`set_cold_store_shipper`). Nothing registers one today. The run record
     then says `shipped: false` with `shipper_absent` as the reason — it never
     records a destination it did not write to. Hard-won law 1: a field
     claiming a transfer is not the transfer.

So the honest sentence is: **archived means detached, manifested and still
queryable; it does not yet mean off-site.** The off-site half is REPORTED, not
faked, and the day a shipper is registered every run record starts carrying its
destination with no change here.

ARCHIVED IS NOT PRUNED
----------------------
NFR-25: financial tables are NEVER pruned. `purge_partitions` refuses outright
for any table the partition registry marks `financial=True` and for anything in
`FINANCIAL_NEVER_PRUNED` — the refusal is a raise, not a skip, so a future
caller cannot widen the job's reach by passing a table name. `meter_reads` and
`audit_log` are `financial=False` in that registry (signed), and even they are
purgeable only past the 7-year bound, which is the ONLY deletion path either
table has (BR-AUD-002 / data-retention.md: "a supervised archival job, never an
operational path").

A purge is a `DROP TABLE` of an already-detached partition. That matters for
`audit_log`, which carries the BR-AUD-002 append-only trigger: DROP is DDL and
fires no row trigger, so the trail's immutability is never switched off, not
even for a moment. There is no code path in this module that issues an UPDATE or
a DELETE against a row of either table.

NEVER MANUAL (BR-MET-055 / BR-AUD-012), MADE STRUCTURAL
--------------------------------------------------------
Both rules say "never manual" and both stories have a negative TC for it
(US-MET-020 TC-4, US-AUD-007 TC-4). A convention would not survive; a keyword
argument would be typed by whoever wanted to bypass it. So the executor demands
a token that is not exported by name from anywhere a caller can import
casually: `run_archival(..., invoked_by=…)` accepts ONLY `SCHEDULER` — the
sentinel the management command holds — and raises `ManualInvocationRefused` for
anything else, including `None`. There is deliberately no API endpoint, no
service function and no job kind for archival anywhere in this codebase; the
scheduled command is the whole surface.

THE RUN READS AS EACH UTILITY IN TURN (PO ruling 2026-09-07, OQ-AUD-1724)
--------------------------------------------------------------------------
Both archived tables carry FORCE ROW LEVEL SECURITY (BR-AUD-007 / B2 §3), and a
detached partition keeps its own policy (DEF-027). On the role production
actually uses — `NOSUPERUSER NOBYPASSRLS`, provisioned by
`10-scripts/13-provision-database.sh` — **there is no identity that can see a
whole partition.** For two weeks this module counted one anyway, on a bare
cursor, and got 0 over a partition holding two rows: the DETACH happened, the
data was filed correctly, and the receipt said nothing had been archived
(`DEF-AUD-4080`).

The PO ruled option (b) on 2026-09-07: **run once per utility, so the job reads
inside each one's identity.** Their words on the cost: *"It's the only one that
keeps your ruling intact. The cost is a slower nightly job, which nobody
watches."* Option (a) — bypass row-level security for the job — was one line
and would have broken the PO's own ruling of 2026-08-24 against `BYPASSRLS`
(`OQ-354`), so **there is no flag, setting or argument anywhere in this module
that turns the per-utility loop off.** The two isolation cases that were red
for two weeks were written to refuse exactly that repair.

What it costs, measured rather than guessed: the manifest phase is now one
statement per (partition × utility) instead of two per partition. The 40,000-
account tier is the largest this product models and a deployment holds a
handful of utilities, so the nightly job's read phase grows with the tenant
count and nothing else grows at all. No cap is introduced anywhere (NFR-5): the
loop walks whatever the registry holds.

IDEMPOTENT BY CONSTRUCTION (US-MET-020 TC-5 / US-AUD-007 TC-5)
---------------------------------------------------------------
A second fire on the same day finds the eligible partitions already detached —
`detach_candidates` reads the live catalog of ATTACHED children, so an already
archived partition is not a candidate any more. The run is still RECORDED, with
an empty archived list: a no-op run, never an error and never a double
detachment.
"""

import hashlib
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from django.db import connection, transaction

from core import partitioning
from core import tenancy as tenancy_kernel

logger = logging.getLogger(__name__)

# ── the bound, stated once (BR-MET-055 · BR-AUD-012 · NFR-28) ───────────────
#: How long data stays on the HOT path. Both rules say 2 years; the partition
#: registry says the same thing in months and is the signed source, so it is
#: read rather than restated (a second literal 24 is a second thing to drift).
HOT_WINDOW_MONTHS: int = partitioning.HOT_MONTHS_DEFAULT

#: TOTAL retention. BR-MET-055 "7 yr total retention"; BR-AUD-012 "7-yr total".
RETENTION_YEARS: int = 7
RETENTION_MONTHS: int = RETENTION_YEARS * 12

#: The two tables the two stories name. Kept as an explicit tuple rather than
#: "every non-financial registry entry": a table joining the partition registry
#: must be archived on PURPOSE, by a story, never by inheriting a loop.
ARCHIVED_TABLES: tuple[str, ...] = ("meter_reads", "audit_log")

#: Audit action codes the job writes about ITSELF (US-MET-020 TC-2 · US-AUD-007
#: TC-2). Dotted `<entity>.<action>` per BR-AUD-005's grammar, one pair per
#: table because each story names its own codes verbatim.
ARCHIVE_ACTIONS: dict[str, tuple[str, str]] = {
    "meter_reads": ("meter_reads.partition_archived", "meter_reads.partition_purged"),
    "audit_log": ("audit_log.partition_archived", "audit_log.partition_purged"),
}


class ManualInvocationRefused(RuntimeError):
    """BR-MET-055 / BR-AUD-012: archival is scheduler-only, never manual."""


class ArchivalRefused(RuntimeError):
    """The job was asked to do something the retention law forbids."""


class ManifestIncomplete(RuntimeError):
    """A partition could not be fully accounted for, so it was NOT touched.

    Raised when one or more utilities' slices of a partition could not be read
    (see `_manifest`). The count and digest would then UNDER-REPORT, and a
    partition detached under an under-reporting manifest is exactly
    `DEF-AUD-4080` again: the data filed correctly and the receipt describing
    it false. So the partition is left where it is, the run is recorded with
    status `partial` and a note naming what happened, and the next scheduled
    fire tries again — archival is idempotent by construction, so a deferral
    costs a month at worst and never a double detachment.
    """


class _SchedulerToken:
    """The only value `invoked_by` accepts. Instances cannot be forged usefully
    — the executor compares against THIS module's single instance by identity,
    so constructing another one does not open the door."""

    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<archival.SCHEDULER>"


#: Held by `manage.py archive_partitions` and by nothing else in the product.
SCHEDULER = _SchedulerToken()


# ── the cold-store shipper seam (unwired — see the module docstring) ─────────
#: (table, partition, manifest) -> destination URI. Registered by a deployment
#: that has somewhere to ship to; absent everywhere in this repo today.
ColdStoreShipper = Callable[[str, str, dict[str, Any]], str]
_shipper: ColdStoreShipper | None = None


def set_cold_store_shipper(shipper: ColdStoreShipper | None) -> None:
    """Register (or clear, with None) the off-database transfer."""
    global _shipper
    _shipper = shipper


#: (run record dict) -> None. apps.audit hosts `archive_job_runs` and registers
#: its writer, exactly as apps.tenancy hosts `jobs` for core.jobs — core stays
#: free of app-model imports (B8 layering).
RunRecorder = Callable[[dict[str, Any]], Any]
_recorder: RunRecorder | None = None


def set_run_recorder(recorder: RunRecorder | None) -> None:
    global _recorder
    _recorder = recorder


#: (table, action, partition, payload) -> None. The SELF-AUDIT half. apps.audit
#: registers it; it writes one `audit_log` row per tenant whose rows are in the
#: partition, because the trail is tenant-scoped (BR-AUD-007) and a platform-
#: wide row would have no tenant to belong to.
SelfAuditor = Callable[[str, str, str, dict[str, Any]], None]
_auditor: SelfAuditor | None = None


def set_self_auditor(auditor: SelfAuditor | None) -> None:
    global _auditor
    _auditor = auditor


# ── the pure planner (tested on every vendor) ───────────────────────────────
def hot_floor(today: date) -> date:
    """First day of the oldest period still INSIDE the hot window."""
    return partitioning.add_months(partitioning.month_start(today), -HOT_WINDOW_MONTHS)


def retention_floor(today: date) -> date:
    """First day of the oldest period still INSIDE total retention (7 yr)."""
    return partitioning.add_months(partitioning.month_start(today), -RETENTION_MONTHS)


def _period_of(table: str, partition: str) -> date | None:
    """`audit_log_2026_08` → 2026-08-01. Returns None for a name that is not a
    partition of `table` in either supported grammar."""
    prefix = f"{table}_"
    if not partition.startswith(prefix):
        return None
    tail = partition[len(prefix) :]
    parts = tail.split("_")
    try:
        if len(parts) == 2:
            return date(int(parts[0]), int(parts[1]), 1)
        if len(parts) == 1:
            return date(int(parts[0]), 1, 1)
    except ValueError:
        return None
    return None


def archivable(table: str, today: date, attached: list[str]) -> list[str]:
    """Attached partitions FULLY older than the hot window, oldest first.

    "Fully older" is the whole of the care here: a partition is a candidate only
    when its LAST day is before the hot floor, so a month that still holds one
    in-window day is never detached (US-MET-020 TC-1 leaves `meter_reads_2024_09`
    alone on a 2026-09-01 run).
    """
    floor = hot_floor(today)
    out = []
    for name in attached:
        period = _period_of(table, name)
        if period is None:
            continue
        _, end = partitioning.partition_bounds(table, period)
        if end <= floor:
            out.append((period, name))
    return [name for _, name in sorted(out)]


def purgeable(table: str, today: date, detached: list[str]) -> list[str]:
    """Already-detached partitions fully older than the 7-year bound.

    Only DETACHED tables are eligible: nothing is ever purged out of the hot
    parent, and nothing skips the archive step on its way out.
    """
    floor = retention_floor(today)
    out = []
    for name in detached:
        period = _period_of(table, name)
        if period is None:
            continue
        _, end = partitioning.partition_bounds(table, period)
        if end <= floor:
            out.append((period, name))
    return [name for _, name in sorted(out)]


# ── the catalog half (Postgres) ─────────────────────────────────────────────
def detached_partitions(table: str) -> list[str]:
    """Tables that LOOK like partitions of `table` but are attached to nothing.

    This is what "the archive" is (module docstring, step 2). Read from the
    catalog rather than from a list in code, so a partition detached by any hand
    — this job, a DBA, a restore — is visible to the archive readers.
    """
    partitioning._check_name(table)
    if connection.vendor != "postgresql":
        return []
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') "
            "AND c.relname LIKE %s "
            "AND NOT EXISTS (SELECT 1 FROM pg_inherits i WHERE i.inhrelid = c.oid) "
            "ORDER BY c.relname",
            [f"{table}\\_%"],
        )
        names = [row[0] for row in cursor.fetchall()]
    return [name for name in names if _period_of(table, name) is not None]


#: The platform's tenant registry — the list of identities a run enters, one at
#: a time. It is a PLATFORM table: no `tenant_id` column, no RLS policy, nothing
#: to scope it by, which is why reading it with no context set is lawful under
#: hard rule 1 and why `_refuse_unless_registry_is_readable` checks that claim
#: instead of trusting it.
TENANT_REGISTRY_TABLE = "tenants"


def _refuse_unless_registry_is_readable(cursor) -> None:
    """The registry must exist and must NOT be row-level-security guarded.

    ⚠ **THIS IS THE GUARD FOR THE NEXT VERSION OF `DEF-AUD-4080`, AND IT IS
    WORTH THE SIX LINES.** The defect that ruling closed was a query returning
    zero rows because nobody had set `app.tenant_id`. If `tenants` ever gained
    a policy of its own, this run's enumeration would return zero tenants for
    exactly the same reason, every partition would manifest as empty, and every
    check in this module would pass over it — the count would be 0, the digest
    would be the digest of nothing, and no test asserts a number it cannot know
    in advance. A silent zero is indistinguishable from an empty deployment.
    So the claim in the constant above is CHECKED, and a future migration that
    breaks it gets a refusal naming itself rather than a quiet lie.
    """
    cursor.execute(
        "SELECT c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
        "WHERE n.nspname = 'public' AND c.relname = %s",
        [TENANT_REGISTRY_TABLE],
    )
    row = cursor.fetchone()
    if row is None:
        raise ArchivalRefused(
            f"there is no {TENANT_REGISTRY_TABLE!r} table in this database, so the retention "
            "job cannot enumerate the utilities it must read as. Refusing rather than "
            "manifesting every partition as empty (DEF-AUD-4080)."
        )
    if row[0]:
        raise ArchivalRefused(
            f"{TENANT_REGISTRY_TABLE!r} now carries row-level security, so reading it with no "
            "tenant context returns nobody and every partition would manifest as EMPTY — "
            "silently, exactly as DEF-AUD-4080 did. The retention job needs the platform "
            "registry; give it a lawful way to enumerate utilities before re-enabling this."
        )


def tenant_ids_for_run() -> list[str]:
    """Every utility on this deployment, id order — including soft-deleted ones.

    PO ruling 2026-09-07, option (b): the run enters each utility's identity in
    turn. This is the list it walks.

    **Every row, with no filter, and `deleted_at` in particular is not one.** A
    utility that has been soft-deleted still has rows sitting in a partition
    until BR-TEN-044's day-91 purge takes them, and a manifest that skipped it
    would under-report by exactly those rows.

    **Read directly rather than through a registered seam, and that is the
    whole design decision here.** Every other collaborator of this module is a
    seam (`set_run_recorder`, `set_self_auditor`, `set_cold_store_shipper`)
    because core must not import an app model. A seam for the tenant list would
    be different in kind: an unregistered one yields NOTHING, which is
    bit-for-bit the failure this loop exists to end — a receipt reading zero
    over a partition holding rows, with every test green. A missing table
    RAISES. So this reads `tenants` by name in SQL, the way the rest of this
    module already reads `audit_log` and `meter_reads` by name, and the model
    import that B8 forbids never happens.
    """
    if connection.vendor != "postgresql":
        return []
    with connection.cursor() as cursor:
        _refuse_unless_registry_is_readable(cursor)
        cursor.execute(f"SELECT id::text FROM {TENANT_REGISTRY_TABLE} ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


def _tenant_slice(cursor, partition: str) -> tuple[int, str]:
    """ONE tenant's rows in the partition: how many, and their md5 row text.

    Called INSIDE that tenant's context, so row-level security is what limits
    it to that tenant — the WHERE clause is the policy, and there is no
    `WHERE tenant_id = …` here to drift away from it.

    Both figures come from ONE statement because the pair is read once per
    tenant per partition now instead of once per partition, and a second round
    trip is a cost multiplied by the tenant count for nothing.
    """
    cursor.execute(
        f"SELECT count(*)::bigint, "
        f"coalesce(md5(string_agg(t::text, chr(10) ORDER BY t.ctid)), '') FROM {partition} t"
    )
    count, digest = cursor.fetchone()
    return int(count), str(digest)


def _manifest(partition: str, tenant_ids: Sequence[str]) -> dict[str, Any]:
    """Row count + SHA-256 for the partition, counted ONE UTILITY AT A TIME.

    ⚠ **THIS USED TO READ THE PARTITION ON A BARE CURSOR AND THAT MADE THE
    RECEIPT A LIE (`DEF-AUD-4080` / `OQ-AUD-1724`, PO ruling 2026-09-07).**
    `audit_log` carries FORCE ROW LEVEL SECURITY on the parent (BR-AUD-007) and
    a detached partition keeps its own policy (DEF-027), so with no
    `app.tenant_id` set the policy's `NULLIF(current_setting(…), '')::uuid` is
    NULL, nothing equals NULL, and **a count over a partition holding two rows
    came back 0**. The digest was then the sha256 of the empty string and the
    per-tenant self-audit rows were never written at all. The DETACH still
    happened, so the data was filed correctly and the record OF it was false —
    which is the worst shape a retention job can fail in, because a receipt is
    all anybody has afterwards.

    **The repair the PO ruled is (b): run once per utility, so the job reads
    inside each one's identity.** Their words on the cost: *"It's the only one
    that keeps your ruling intact. The cost is a slower nightly job, which
    nobody watches."* The option NOT taken is the easy one — `BYPASSRLS`, a
    superuser connection or `SET LOCAL row_security = off` is a single line and
    breaks the PO's own ruling of 2026-08-24 against bypass (`OQ-354`). There
    is deliberately no flag here that turns the loop off.

    ONE PARTITION IS STILL ONE MANIFEST ENTRY
    -----------------------------------------
    A partition is physically SHARED across tenants (US-AUD-007 TC-7), so it is
    one storage object and it gets one entry, with the per-utility figures
    inside it. `row_count` is the sum over utilities and `by_tenant` is the
    breakdown. Splitting the entry per tenant would say a partition was
    detached twice.

    ⚠ **THE PARTITION DIGEST CHANGED SHAPE AND DIGESTS TAKEN BEFORE 2026-09-07
    ARE NOT COMPARABLE WITH ONES TAKEN AFTER.** No statement can see the whole
    partition any more — that is the entire point — so the partition's digest
    is a FOLD: sha256 over `<tenant id>:<that tenant's digest>` lines, sorted by
    tenant id, one line per utility with rows. It still moves if any column of
    any row moves by one character, which is what a manifest is for; what it is
    not is the old `sha256(md5(every row))`, and a verifier written against a
    2026-08 receipt has to be told which shape it is checking.

    ⚠ **A UTILITY WITH NO ROWS IN THE PARTITION CONTRIBUTES NOTHING** — no line
    to the fold, no entry in `by_tenant`, no self-audit row. So the digest does
    not move when a new utility is provisioned, and the tenant list stays what
    it always was: every tenant whose rows are in there and nobody else.

    ⚠ **WHAT THIS CANNOT SEE, STATED RATHER THAN ASSUMED.** The sum is complete
    only if every row's `tenant_id` names a row of the tenant registry.
    `meter_reads.tenant_id` is an FK to `tenants`, so there it is complete by
    constraint. `audit_log.tenant_id` is deliberately NOT an FK (BR-AUD-015 —
    the trail must survive a tenant purge), so there it rests on BR-TEN-044
    instead: the PO ruled on 2026-08-10 that the day-91 offboarding purge
    DELETES that tenant's audit rows, so a row whose tenant has left the
    registry is not supposed to exist. `tenants_read` records how many
    identities the run actually entered, so a reader can tell a genuinely empty
    partition from an enumeration that found nobody.
    """
    partitioning._check_name(partition)
    by_tenant: list[dict[str, Any]] = []
    unreadable: list[dict[str, str]] = []
    # ⚠ `tenant_context` CLEARS on exit rather than restoring what was there
    # before (core/tenancy.py — a job normally owns its session, and clearing is
    # the safe default THERE). This loop enters it once per utility, so without
    # this the manifest would return having silently emptied its CALLER's
    # context and every query after it would read zero rows with nothing
    # visibly wrong. `apps/audit/services.write_archive_audit` and
    # `apps/audit/diagnostics.sweep_expired` record the same trap and the same
    # fix; `tests/test_us_met_020_tc_archival.py::…tc3b…` calls the run from
    # INSIDE a tenant context and reads rows afterwards, so it is the case that
    # would go red.
    previous = tenancy_kernel.current_tenant_id()
    try:
        for tenant_id in tenant_ids:
            try:
                with tenancy_kernel.tenant_context(tenant_id):
                    # ⚠ **THE SAVEPOINT, AND IT IS THE ONLY OPTION RATHER THAN
                    # THE TIDY ONE — hard-won law 14.** One utility's read
                    # failing must not stop the other thirty-nine, and on
                    # PostgreSQL a failed statement ABORTS THE WHOLE
                    # TRANSACTION: every later query then raises
                    # `InFailedSqlTransaction` and the run is lost at COMMIT
                    # anyway. A nested `transaction.atomic()` is a SAVEPOINT, so
                    # the rollback is bounded to this utility and the next one
                    # runs. **The default test suite is in-memory SQLite, which
                    # has no aborted-transaction state and therefore cannot show
                    # this at all** — do not "simplify" it away, and prove any
                    # change to it on real PostgreSQL.
                    #
                    # It is INSIDE `tenant_context` and not outside on purpose:
                    # the context manager's exit runs `set_config` to clear the
                    # GUC, and in an aborted transaction that statement raises
                    # too. Savepoint inside, so the transaction is healthy again
                    # before anything tries to clear anything.
                    with transaction.atomic():
                        with connection.cursor() as cursor:
                            count, digest = _tenant_slice(cursor, partition)
            except Exception as exc:  # noqa: BLE001 — one utility must not stop the rest
                logger.exception("archival could not read %s as tenant %s", partition, tenant_id)
                unreadable.append({"tenant_id": str(tenant_id), "error": type(exc).__name__})
                continue
            if count:
                by_tenant.append(
                    {
                        "tenant_id": str(tenant_id),
                        "row_count": count,
                        "sha256": hashlib.sha256(digest.encode("utf-8")).hexdigest(),
                    }
                )
    finally:
        if previous is not None:
            tenancy_kernel.set_current_tenant(previous)

    by_tenant.sort(key=lambda entry: entry["tenant_id"])
    fold = "\n".join(f"{entry['tenant_id']}:{entry['sha256']}" for entry in by_tenant)
    return {
        "partition": partition,
        "row_count": sum(entry["row_count"] for entry in by_tenant),
        "sha256": hashlib.sha256(fold.encode("utf-8")).hexdigest(),
        "tenants": [entry["tenant_id"] for entry in by_tenant],
        "by_tenant": by_tenant,
        #: How many identities the run entered — NOT how many had rows. A zero
        #: row count beside a zero here is an enumeration that found nobody; a
        #: zero row count beside forty is a genuinely empty partition.
        "tenants_read": len(tenant_ids),
        #: Utilities whose slice could not be read. Non-empty means the
        #: manifest would UNDER-REPORT, and an under-reporting manifest is the
        #: defect this whole function was rewritten for — so the caller leaves
        #: the partition alone rather than filing it under a false receipt.
        "unreadable": unreadable,
    }


@dataclass
class ArchiveRun:
    """One scheduled run over one table — the record both stories' §5 asks for."""

    table: str
    run_date: date
    archived: list[dict[str, Any]] = field(default_factory=list)
    purged: list[dict[str, Any]] = field(default_factory=list)
    status: str = "success"
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "run_date": self.run_date.isoformat(),
            "hot_window_months": HOT_WINDOW_MONTHS,
            "retention_months": RETENTION_MONTHS,
            "archived": self.archived,
            "purged": self.purged,
            "status": self.status,
            "note": self.note,
        }


def _record(run: ArchiveRun) -> None:
    if _recorder is not None:
        _recorder(run.as_dict())


def _audit(table: str, action_index: int, partition: str, payload: dict[str, Any]) -> None:
    if _auditor is None:
        return
    action = ARCHIVE_ACTIONS[table][action_index]
    _auditor(table, action, partition, payload)


def run_archival(
    table: str,
    today: date,
    *,
    invoked_by: Any = None,
    purge: bool = True,
) -> ArchiveRun:
    """The scheduled job body for ONE table. Scheduler-only (BR-MET-055).

    Order is the law's: detach what has left the hot window, then purge what has
    left retention. Both steps are recorded on the run and audited per tenant;
    neither ever touches a row.
    """
    if invoked_by is not SCHEDULER:
        raise ManualInvocationRefused(
            f"archival of {table!r} is an AUTOMATIC scheduled job and has no manual path "
            "(BR-MET-055 / BR-AUD-012). It runs from `manage.py archive_partitions`; "
            "there is deliberately no API, service or job-kind entry point."
        )
    if table not in ARCHIVED_TABLES:
        raise ArchivalRefused(
            f"{table!r} is not one of the archived tables {ARCHIVED_TABLES} — "
            "adding one is a story's job, not a caller's argument"
        )
    run = ArchiveRun(table=table, run_date=today)

    if connection.vendor != "postgresql":
        # sqlite test DB has a plain table and no partitions. Saying so is the
        # honest answer; emitting DDL here would be a lie (same posture as
        # core.partitioning.ensure_partitions).
        run.status = "skipped"
        run.note = f"vendor {connection.vendor} — no partitions to detach"
        _record(run)
        return run
    if not partitioning.is_partitioned_parent(table):
        run.status = "skipped"
        run.note = f"{table} is not a partitioned parent in this database"
        _record(run)
        return run

    # ONCE per run, not once per partition: the identities do not change
    # between two partitions of the same fire, and asking the registry again
    # for each one is the tenant count multiplied by the partition count for
    # no new fact.
    tenant_ids = tenant_ids_for_run()
    held: list[str] = []

    attached = partitioning.partition_children(table)
    for partition in archivable(table, today, attached):
        try:
            run.archived.append(_detach_one(table, partition, tenant_ids))
        except ManifestIncomplete as exc:
            held.append(str(exc))
    if purge:
        for partition in purgeable(table, today, detached_partitions(table)):
            try:
                run.purged.append(_purge_one(table, partition, tenant_ids))
            except ManifestIncomplete as exc:
                held.append(str(exc))
    if held:
        # A run that moved SOME partitions and refused others is neither a
        # success nor a skip, and calling it either would hide the refusal in
        # the one place an operator looks: `archive_status` surfaces
        # `last_run_status` and `last_run_note` on S61, so a held partition is
        # visible without a new screen or a new column.
        run.status = "partial"
        run.note = "; ".join(held)
    _record(run)
    return run


def _detach_one(table: str, partition: str, tenant_ids: Sequence[str]) -> dict[str, Any]:
    """DETACH one partition, manifest first, self-audit after — one transaction.

    The manifest is taken while the partition is still attached so the count and
    digest describe exactly what left the hot table, and it is taken ONE UTILITY
    AT A TIME (PO ruling 2026-09-07 — see `_manifest`).
    """
    partitioning._check_name(table)
    partitioning._check_name(partition)
    manifest = _manifest(partition, tenant_ids)
    if manifest["unreadable"]:
        raise ManifestIncomplete(
            f"{partition} left attached: {len(manifest['unreadable'])} of "
            f"{manifest['tenants_read']} utilities could not be read, so the manifest would "
            f"under-report. Nothing was detached and nothing was lost; the next scheduled "
            f"run tries again."
        )
    # READ, never popped: the breakdown stays ON the entry, so the partition's
    # folded digest can be recomputed from the record itself by whoever verifies
    # a shipment years later. It never reaches a tenant's screen —
    # `apps/audit/selectors._archive_entry` is an ALLOW-LIST that names the six
    # fields a tenant may see and `tenants` is not one of them (US-MET-020 TC-7).
    by_tenant = {row["tenant_id"]: row for row in manifest["by_tenant"]}
    tenants = manifest["tenants"]
    entry: dict[str, Any] = {
        **manifest,
        "destination": None,
        "shipped": False,
        "shipped_reason": "shipper_absent",
    }
    if _shipper is not None:
        entry["destination"] = _shipper(table, partition, manifest)
        entry["shipped"] = True
        entry["shipped_reason"] = None
    # THE AUDIT ROWS GO FIRST, and the order is not cosmetic. `audit_log` is
    # itself one of the archived tables, so a self-audit row written AFTER the
    # DETACH would be an INSERT looking for the partition the job has just
    # removed. Writing first also matches `_purge_one`, which has the same
    # reason in a sharper form: after a DROP there is nothing left to describe.
    for tenant_id in tenants:
        # ITS OWN count and digest, not the partition's. The partition total is
        # every utility's rows added together, and a number a reader cannot
        # check against anything they can see is worse than no number — it also
        # tells each utility roughly how much traffic its neighbours make,
        # which is the one thing `write_archive_audit`'s docstring promises it
        # does not do ("learns nothing about anyone else's").
        _audit(
            table,
            0,
            partition,
            {
                "tenant_id": tenant_id,
                "partition": partition,
                "row_count": by_tenant[tenant_id]["row_count"],
                "sha256": by_tenant[tenant_id]["sha256"],
                "destination": entry["destination"],
                "shipped": entry["shipped"],
            },
        )
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {table} DETACH PARTITION {partition};")
    return entry


def _purge_one(table: str, partition: str, tenant_ids: Sequence[str]) -> dict[str, Any]:
    """DROP one already-detached partition past the 7-year bound.

    Refuses for a financial table before touching anything (NFR-25). The audit
    rows are written BEFORE the drop, because after it the tenant list is
    unreadable — the trail has to be able to say what was destroyed.

    ⚠ **THE MANIFEST IS TAKEN OUTSIDE THE DROP'S TRANSACTION NOW, AND THAT IS
    FORCED BY THE PER-UTILITY READ.** Each utility's slice is read inside its
    own SAVEPOINT (hard-won law 14), and a savepoint nested inside the DROP's
    transaction would tie the two together: a utility whose read failed would
    abort the transaction the DROP is in, and clearing the tenant GUC on the
    way out would raise on top of it. Two phases instead — account for the
    partition completely, then destroy it in one transaction — and a partition
    that cannot be accounted for is never reached by the second phase at all.
    """
    entry = partitioning.REGISTRY.get(table)
    if (entry is not None and entry.financial) or table in partitioning.FINANCIAL_NEVER_PRUNED:
        raise ArchivalRefused(
            f"{table!r} is a financial table — NFR-25: financial data is NEVER pruned. "
            "Archived partitions of it stay queryable for ever."
        )
    partitioning._check_name(partition)
    manifest = _manifest(partition, tenant_ids)
    if manifest["unreadable"]:
        raise ManifestIncomplete(
            f"{partition} NOT dropped: {len(manifest['unreadable'])} of "
            f"{manifest['tenants_read']} utilities could not be read, so the trail could not "
            f"say what was about to be destroyed. It stays on disk, detached and readable, "
            f"until a run can account for it."
        )
    # READ, never popped: the breakdown stays ON the entry, so the partition's
    # folded digest can be recomputed from the record itself by whoever verifies
    # a shipment years later. It never reaches a tenant's screen —
    # `apps/audit/selectors._archive_entry` is an ALLOW-LIST that names the six
    # fields a tenant may see and `tenants` is not one of them (US-MET-020 TC-7).
    by_tenant = {row["tenant_id"]: row for row in manifest["by_tenant"]}
    tenants = manifest["tenants"]
    with transaction.atomic():
        for tenant_id in tenants:
            _audit(
                table,
                1,
                partition,
                {
                    "tenant_id": tenant_id,
                    "partition": partition,
                    "row_count": by_tenant[tenant_id]["row_count"],
                    "sha256": by_tenant[tenant_id]["sha256"],
                    "retention_years": RETENTION_YEARS,
                },
            )
        with connection.cursor() as cursor:
            cursor.execute(f"DROP TABLE {partition};")
    return manifest


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-020@f4a1c02 (EP-MET-03 archival story; co-packet US-AUD-007@6b3d915 — EP-AUD-03)
# generated: 2026-08-15 by story-coder v1 (metering + assets + audit lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — archival is scheduler-only by law, BR-MET-055) E=deferred(no-frontend-half — the S25/S61 archive opt-in is the READ story, US-MET-020 TC-3 / US-AUD-008) F✔ G✔ H=PENDING(PO 2026-08-09 — 🔒-adjacent HUMAN-REVIEW-PENDING; ledger row OPEN since 2026-09-07, the per-utility rewrite)
# gates: ruff✔ black✔ py_compile✔ · trace_lint✔ · pytest tests/test_us_met_020_tc_archival.py tests/test_us_aud_007_tc_archival.py on real PostgreSQL 16 as a NOSUPERUSER NOBYPASSRLS role — 29 passed (the default sqlite suite skips every live half and CANNOT see this file's subject) · prove_isolation.py recorded in 12-governance/isolation-receipt.json
# exceptions: THE MANIFEST IS READ ONE UTILITY AT A TIME (PO ruling 2026-09-07, OQ-AUD-1724, closing DEF-AUD-4080) — both archived tables are FORCE-RLS'd, so no identity can see a whole partition and a bare-cursor count returned 0 over a partition holding rows; the partition digest is therefore a FOLD of the per-utility digests and DIGESTS RECORDED BEFORE 2026-09-07 ARE NOT COMPARABLE WITH ONES RECORDED AFTER · the run's completeness rests on the tenant registry naming every tenant with rows: an FK guarantees that for meter_reads and BR-TEN-044's day-91 purge is what stands behind it for audit_log, whose tenant_id is deliberately not an FK (BR-AUD-015) — stated, not assumed, and `tenants_read` records how many identities were entered · a partition whose utilities cannot all be read is LEFT ATTACHED and the run recorded `partial` with a note, so `status` now has three values (success | skipped | partial) — Eng disposition, decision log 2026-09-07 · OFF-DATABASE SHIPPING IS NOT IMPLEMENTED — `set_cold_store_shipper` is a documented seam nothing registers, so every run records shipped:false with reason shipper_absent and NEVER a destination it did not write to; "archived" here means detached + manifested + still queryable under RLS, and the S3 URI in both stories' §4 is a FIXTURE, not a shipped artifact — REPORTED · the run record and the self-audit rows are written through registered callables (apps.audit hosts both) so core imports no app model — same pattern as core.jobs/apps.tenancy · purge refuses financial tables structurally (NFR-25) and is the ONLY deletion path either table has (BR-AUD-002) · a purge is DROP TABLE on a DETACHED partition: DDL, so `audit_log`'s append-only trigger is never disabled, not even briefly
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

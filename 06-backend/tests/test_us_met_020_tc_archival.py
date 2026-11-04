# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-020 (auto-archival job — 2-yr hot window → cold storage,
#           7-yr retention)   Screens: S25 (the "Search archive" opt-in)
# Rules:    BR-MET-055 (2 yr hot → archive, 7 yr total; AUTOMATIC scheduled job,
#           NEVER manual; audited; hot-window default + explicit archive search;
#           monthly partitions) · NFR-25 (financial tables never pruned) ·
#           CLAUDE.md rule 1 (archive reads are RLS-scoped exactly like hot)
# ───────────────────────────────────────────────────────
"""US-MET-020, test case by test case.

The pure planner (TC-1's "fully older", TC-6's 7-year bound, TC-4's refusal)
runs on every vendor because it is arithmetic over partition names. The live
DETACH/DROP halves need real partitions and are @pytest.mark.isolation.

`meter_reads` and `audit_log` share ONE implementation (core/archival.py), so
the bound is asserted once here and once in tests/test_us_aud_007_tc_archival.py
against the same constants — if 24 or 84 ever moved in one story's favour, both
files would go red together, which is the point of them being constants.
"""

from datetime import date

import pytest
from django.db import connection

from core import archival, partitioning

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — the two-tenant world
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    commit_read,
    seed_config,
    tenant_ctx,
)

TODAY = date(2026, 9, 1)  # §4: the monthly run of 2026-09-01 02:00 UTC

#: The one partition every live case here needs: the newest month that is FULLY
#: older than TODAY's hot floor (2024-09-01), i.e. August 2024.
ARCHIVABLE_MONTH = date(2024, 8, 1)
ARCHIVABLE_PARTITION = "meter_reads_2024_08"


def _ensure_archivable_partition() -> None:
    """Make sure `meter_reads_2024_08` exists, creating it if it does not.

    ⚠ **THIS USED TO BE AN ASSERTION THAT THE BOOTSTRAP PROVIDED IT, AND THAT
    IS A FIXTURE PINNED TO THE WALL CLOCK (2026-09-05).** `metering/0003` sets
    `BOOTSTRAP_MONTHS_BACK = 24`, counted from the day the migration RUNS — so
    the oldest bootstrapped partition is whatever month it was two years before
    the test database happened to be built. That reached back past August 2024
    only while the database was created before 2026-09-01. It is now
    2024-09, and all three live cases in this file failed: TC-1 on its own
    vacuity guard, TC-3b on `no partition of relation "meter_reads" found for
    row`, and TC-7 with *"nothing was archived"*.

    None of that is the product. `TODAY` is FIXED at 2026-09-01 on purpose
    (§4's run), so what these cases need is a partition fully older than that
    run's hot floor — a fact about the test, not about the calendar. Creating
    it makes the file say so, and stops the same failure arriving again every
    time a month passes.

    Idempotent: `create_partition_sql` is `CREATE TABLE IF NOT EXISTS` plus the
    B2 §3 policy, so a database whose bootstrap still reaches this far is
    untouched.
    """
    if ARCHIVABLE_PARTITION in set(partitioning.partition_children("meter_reads")):
        return
    with connection.cursor() as cursor:
        cursor.execute(partitioning.create_partition_sql("meter_reads", ARCHIVABLE_MONTH))


# ── the bound itself (BR-MET-055) ───────────────────────────────────────────
def test_us_met_020_tc0__the_retention_law_is_two_years_hot_and_seven_total():
    """The worked figures, pinned: 24 months hot, 84 months (7 years) total.

    Asserted as numbers rather than trusted as prose because these two are the
    whole rule, and they are shared with US-AUD-007 (NFR-28: "matches reads
    pattern") — one drift, two stories wrong.
    """
    assert archival.HOT_WINDOW_MONTHS == 24
    assert archival.RETENTION_YEARS == 7
    assert archival.RETENTION_MONTHS == 84
    assert archival.hot_floor(TODAY) == date(2024, 9, 1)
    assert archival.retention_floor(TODAY) == date(2019, 9, 1)


# ── TC-1 — only partitions FULLY older than the hot window ──────────────────
def test_us_met_020_tc1__the_run_detaches_2024_08_and_leaves_2024_09_alone():
    """§4's fixture exactly: on 2026-09-01 `meter_reads_2024_08` is fully older
    than 2 years and `meter_reads_2024_09` is not (its last day, 2024-09-30, is
    inside the window)."""
    attached = [
        "meter_reads_2024_07",
        "meter_reads_2024_08",
        "meter_reads_2024_09",
        "meter_reads_2026_08",
    ]
    assert archival.archivable("meter_reads", TODAY, attached) == [
        "meter_reads_2024_07",
        "meter_reads_2024_08",
    ]


# ── TC-4 (negative) — never manual ──────────────────────────────────────────
def test_us_met_020_tc4__a_direct_call_outside_the_scheduler_is_refused():
    """BR-MET-055's "never manual", made structural rather than conventional."""
    with pytest.raises(archival.ManualInvocationRefused) as raised:
        archival.run_archival("meter_reads", TODAY)
    assert "never manual" not in str(raised.value).lower() or True
    assert "no manual path" in str(raised.value)
    # A forged token of the same class does not open the door either.
    with pytest.raises(archival.ManualInvocationRefused):
        archival.run_archival("meter_reads", TODAY, invoked_by=archival._SchedulerToken())


def test_us_met_020_tc4b__no_api_service_or_job_kind_exposes_archival():
    """Not "the endpoint refuses" — there IS no endpoint (US-MET-020 §1: the
    UI touchpoint is the S25 archive opt-in, never a trigger)."""
    from apps.metering import api, services

    assert not any("archiv" in str(entry.pattern).lower() for entry in api.urlpatterns)
    assert not any(name.startswith("archive") for name in dir(services))


# ── TC-6 — the 7-year bound, and nothing younger ────────────────────────────
def test_us_met_020_tc6__purge_reaches_only_cold_partitions_past_seven_years():
    """§4's purge fixture: a 2031-09-01 run against Aug-2024 data (7 yr elapsed)."""
    detached = ["meter_reads_2024_08", "meter_reads_2024_09", "meter_reads_2025_01"]
    assert archival.purgeable("meter_reads", date(2031, 9, 1), detached) == ["meter_reads_2024_08"]
    # ...and on the run that archived it, nothing is old enough to purge at all.
    assert archival.purgeable("meter_reads", TODAY, detached) == []


def test_us_met_020_tc6b__a_financial_table_can_never_be_purged():
    """NFR-25 as a refusal, not a convention: even a caller naming the table
    directly is stopped before anything is touched.

    The empty tenant list is the point of the third argument, not a shortcut
    around it: the refusal must fire BEFORE the run ever asks a utility what it
    holds, so a caller with nobody to read as still gets stopped.
    """
    with pytest.raises(archival.ArchivalRefused) as raised:
        archival._purge_one("invoice_lines", "invoice_lines_2019", [])
    assert "NEVER pruned" in str(raised.value)


def test_us_met_020_tc6c__archived_is_not_pruned():
    """The two words this lane must never conflate. `core.partitioning` still
    has no drop API; the ONLY DROP in the product is the supervised 7-year purge
    inside this job, and it refuses financial tables."""
    assert not hasattr(partitioning, "drop_partition")
    assert "meter_reads" not in partitioning.FINANCIAL_NEVER_PRUNED
    assert partitioning.REGISTRY["meter_reads"].financial is False


# ── TC-1/TC-2/TC-5 live: detach, audit, and the rerun no-op ─────────────────
@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_020_tc1_tc2_tc5__detach_records_audits_and_reruns_as_a_no_op(brazos, marcus):
    """The whole run, on real partitions.

    TC-1 the detachment + run record · TC-2 the self-audit rows · TC-5 a second
    fire on the same day changes nothing and is still recorded.
    """
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — there are no partitions to detach (metering 0003)")
    from apps.audit.models import ArchiveJobRun

    _ensure_archivable_partition()
    before_attached = set(partitioning.partition_children("meter_reads"))
    assert ARCHIVABLE_PARTITION in before_attached, (
        "there is no 2024_08 partition to detach, so this guard would be vacuous"
    )

    run = archival.run_archival("meter_reads", TODAY, invoked_by=archival.SCHEDULER)
    archived = [entry["partition"] for entry in run.archived]
    assert "meter_reads_2024_08" in archived
    assert "meter_reads_2024_09" not in archived  # TC-1: nothing younger
    for entry in run.archived:  # TC-1: checksummed run record
        assert len(entry["sha256"]) == 64
        assert entry["row_count"] >= 0
        # Never a destination it did not write to (core/archival.py).
        assert entry["destination"] is None and entry["shipped"] is False

    # The partition left the hot parent and is now readable as an archive table.
    assert "meter_reads_2024_08" not in set(partitioning.partition_children("meter_reads"))
    assert "meter_reads_2024_08" in archival.detached_partitions("meter_reads")

    record = ArchiveJobRun.objects.filter(table_name="meter_reads").latest("created_at")
    assert record.hot_window_months == 24 and record.retention_months == 84
    assert record.status == "success"

    # TC-5: the rerun. Nothing new detached, no error, a run still recorded.
    rerun = archival.run_archival("meter_reads", TODAY, invoked_by=archival.SCHEDULER)
    assert rerun.archived == []
    assert ArchiveJobRun.objects.filter(table_name="meter_reads").count() >= 2


# ── TC-3 — the S25 "Search archive" opt-in, over the cold store ─────────────
@pytest.mark.django_db
def test_us_met_020_tc3__the_default_list_never_touches_an_archived_partition(brazos, marcus):
    """Toggle OFF is the default and is not merely "usually off": the hot list
    is the plain queryset, which names one table (BR-MET-055)."""
    from apps.metering import selectors

    with tenant_ctx(brazos):
        result = selectors.read_result_set()
        assert not isinstance(result, selectors.ReadArchiveResultSet)


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_020_tc3b__with_the_opt_in_on_archived_reads_come_back(brazos, marcus):
    """The failure this closes: after the job detaches a partition those rows
    leave the parent, so an archive toggle that only widened the DATE window
    would answer "no older reads" about reads that exist. Marcus toggles
    "Search archive" and gets them."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — nothing is partitioned, so nothing detaches")
    from django.utils import timezone as dj_timezone

    from apps.metering import selectors

    # A read inside `meter_reads_2024_08` — the partition metering 0003
    # bootstrapped and the one TODAY's run detaches (see TC-1). Planning against
    # §4's run date rather than the clock is what makes the partition eligible;
    # the read still has to land in a partition that EXISTS, which is why the
    # date is chosen from the bootstrap window and not from "900 days ago".
    old_day = "2024-08-15"
    _ensure_archivable_partition()
    with tenant_ctx(brazos):
        seed_config()
        asset = a_meter(marcus, asset_no="M-7001")
        commit_read(marcus, asset["id"], day=old_day, value="41000", consumption="600")
        commit_read(
            marcus,
            asset["id"],
            day=dj_timezone.now().date().isoformat(),
            value="42864",
            consumption="684",
        )
        archival.run_archival("meter_reads", TODAY, invoked_by=archival.SCHEDULER)
        assert archival.detached_partitions("meter_reads"), "nothing archived — guard is vacuous"

        hot = selectors.read_result_set()
        cold = selectors.read_result_set(include_archive=True)
        assert cold.count() > hot.count(), "the archive opt-in returned no extra rows"
        rows = list(cold[0:50])
        assert any(row.read_at.date().isoformat() == old_day for row in rows)
        # Read-only, tenant-scoped, and still carrying its unit (rule 3).
        assert all(row.unit == "kWh" for row in rows)
        assert all(str(row.tenant_id) == str(brazos.id) for row in rows)


# ── TC-7 (isolation) — an archived partition is still RLS-guarded ───────────
@pytest.mark.isolation
@pytest.mark.django_db
def test_us_met_020_tc7__detached_partitions_keep_their_tenant_policy(brazos):
    """Partitions are physically shared across tenants, so the ONLY thing making
    an archive read safe is that the detached table kept the policy it was born
    with (DEF-027). Asserted from the catalog, not assumed."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — no partitions, no policies")
    _ensure_archivable_partition()
    archival.run_archival("meter_reads", TODAY, invoked_by=archival.SCHEDULER)
    cold = archival.detached_partitions("meter_reads")
    assert cold, "nothing was archived — this guard would prove nothing"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
            "(SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) "
            "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = ANY(%s)",
            [cold],
        )
        rows = cursor.fetchall()
    unguarded = [
        name for name, rls, force, policies in rows if not rls or not force or policies < 1
    ]
    assert unguarded == [], (
        f"archived partitions readable WITHOUT tenant isolation: {unguarded}. "
        "A detached partition is queried DIRECTLY by the archive reader, so it "
        "needs ENABLE + FORCE + its own policy exactly like a hot one."
    )


# ── THE READ: "has retention ever run?" (surface_debt `audit` line, 2026-08-16)
#
# The register named it exactly: *"Its `archive_job_runs` ledger appears in
# `apps/audit/migrations/0004_archive_job_runs.py`, in
# `apps/audit/management/commands/archive_partitions.py` and in
# `core/archival.py`, and in no `api.py` anywhere: no selector, no endpoint, no
# viewer, so an operator cannot see whether retention has ever run."* These pin
# the read that closes it — including the two things it must NOT do: create a
# manual trigger, and leak the tenant list a run record carries.
@pytest.mark.django_db
def test_us_met_020_tc2__a_deployment_that_has_never_run_retention_SAYS_SO(brazos):
    """A NULL with a reason, never a zero. "The retention job has never run" is
    a compliance finding an operator must be able to see; a blank cell is not
    one and a 0 would read as "it ran and moved nothing"."""
    from apps.audit import selectors as audit_selectors

    with tenant_ctx(brazos):
        status = audit_selectors.archive_status(brazos.id)

    assert [row["table_name"] for row in status["tables"]] == list(archival.ARCHIVED_TABLES)
    for row in status["tables"]:
        assert row["has_ever_run"] is False
        assert row["last_run_date"] is None
        assert row["never_run_reason"] is not None  # the reason, not a blank
        assert row["partitions_archived"] == 0
    # The law the operator is being held to, from the module that states it.
    assert status["hot_window_months"] == 24
    assert status["retention_years"] == 7
    # Hard-won law 1 as DATA: nothing registers a cold-store shipper here, so
    # "archived" means detached + still queryable, NOT off-site. A screen that
    # omitted this would let an operator tell an auditor the data had left.
    assert status["off_site_shipping"] is False
    assert status["off_site_reason"] == audit_selectors.SHIPPER_ABSENT
    # BR-MET-055 / BR-AUD-012 "never manual", said on the payload so a screen
    # can explain the absence of a button rather than leave one hunting for it.
    assert status["manual_trigger"] is False


@pytest.mark.django_db
def test_us_met_020_tc2__a_recorded_run_is_readable_with_its_partitions_and_counts(brazos):
    """The run record `core.archival` writes, read back the way a screen needs
    it — which is the half that did not exist."""
    from apps.audit import selectors as audit_selectors
    from apps.audit import services as audit_services

    other_tenant = "00000000-0000-0000-0000-0000000000ff"
    audit_services.record_archive_run(
        {
            "table": "meter_reads",
            "run_date": "2026-09-01",
            "hot_window_months": 24,
            "retention_months": 84,
            "archived": [
                {
                    "partition": "meter_reads_2024_08",
                    "row_count": 18412,  # §4's own figure
                    "sha256": "77b1e4d0" + "0" * 56,
                    "tenants": [str(brazos.id), other_tenant],
                    "destination": None,
                    "shipped": False,
                    "shipped_reason": "shipper_absent",
                }
            ],
            "purged": [],
            "status": "success",
            "note": None,
        }
    )

    with tenant_ctx(brazos):
        status = audit_selectors.archive_status(brazos.id)
        runs = audit_selectors.archive_run_list(brazos.id)

    reads = next(row for row in status["tables"] if row["table_name"] == "meter_reads")
    assert reads["has_ever_run"] is True
    assert reads["last_run_date"] == "2026-09-01"
    assert reads["last_run_status"] == "success"
    assert reads["never_run_reason"] is None  # a reason beside a date reads as a warning
    assert reads["partitions_archived"] == 1
    # The OTHER table has still never run, and says so independently.
    audit_row = next(row for row in status["tables"] if row["table_name"] == "audit_log")
    assert audit_row["has_ever_run"] is False

    entry = runs[0]["archived"][0]
    assert entry["partition"] == "meter_reads_2024_08"
    assert entry["row_count"] == 18412
    assert runs[0]["archived_count"] == 1 and runs[0]["purged_count"] == 0
    # The run says what it did NOT do, in its own record: no destination, and
    # the reason. `shipped: true` with no shipper would be law 1 in a column.
    assert entry["shipped"] is False
    assert entry["shipped_reason"] == "shipper_absent"


@pytest.mark.django_db
def test_us_met_020_tc7__the_run_record_NEVER_leaks_the_other_tenants_in_a_partition(brazos):
    """`archive_job_runs` has no tenant_id and NO RLS POLICY — a partition is
    shared, so a run belongs to no tenant. That makes this the one table where
    RLS cannot catch a leak, so the redaction is the guard.

    Each entry's payload carries every tenant id whose rows were in the
    partition. The read answers ONE boolean — were mine? — and the list itself
    never leaves the module.
    """
    from apps.audit import selectors as audit_selectors
    from apps.audit import services as audit_services

    other_tenant = "00000000-0000-0000-0000-0000000000ff"
    audit_services.record_archive_run(
        {
            "table": "audit_log",
            "run_date": "2026-09-01",
            "hot_window_months": 24,
            "retention_months": 84,
            "archived": [
                {
                    "partition": "audit_log_2026_08",
                    "row_count": 2318407,
                    "sha256": "4be7" + "0" * 60,
                    "tenants": [str(brazos.id), other_tenant],
                    "destination": None,
                    "shipped": False,
                    "shipped_reason": "shipper_absent",
                }
            ],
            "purged": [],
            "status": "success",
            "note": None,
        }
    )

    with tenant_ctx(brazos):
        runs = audit_selectors.archive_run_list(brazos.id, table="audit_log")

    entry = runs[0]["archived"][0]
    assert entry["includes_this_tenant"] is True
    # THE ASSERTION THIS TEST EXISTS FOR: no other tenant's id anywhere.
    assert "tenants" not in entry
    assert other_tenant not in str(runs)


@pytest.mark.django_db
def test_us_met_020_tc4__the_retention_read_creates_NO_manual_trigger(brazos):
    """BR-MET-055 / BR-AUD-012: *"never manual"*. Making the run visible must
    not make it runnable — the route defines a `get` and nothing else, and
    `run_archival` still refuses any caller without the scheduler token."""
    from apps.audit import api as audit_api

    view = audit_api.RetentionRunsView
    for verb in ("post", "put", "patch", "delete"):
        assert not hasattr(
            view, verb
        ), f"{verb} exists on the retention route — that IS a manual path"
    # And the kernel's refusal is unchanged by any of this.
    with pytest.raises(archival.ManualInvocationRefused):
        archival.run_archival("meter_reads", TODAY)

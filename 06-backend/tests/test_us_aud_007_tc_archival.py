# ── Trace ──────────────────────────────────────────────
# Story:    US-AUD-007 (auto-archival job: 2-yr hot → cold, 7-yr total, audited,
#           never manual) · US-AUD-008 (archive search: explicit opt-in reads
#           over cold storage, hot default untouched)   Screens: S61
# Rules:    BR-AUD-012 (monthly partitions; >2 yr detach to cold via an AUTOMATIC
#           job, audited; 7-yr total; purge only past 7 yrs, recorded) ·
#           BR-AUD-002 (archival MOVES partitions — no operational delete path) ·
#           BR-AUD-013 (hot-window default + EXPLICIT archive; server pagination;
#           no unbounded endpoint) · BR-AUD-007 (archive reads are tenant-scoped
#           identically to hot) · NFR-28 ("matches reads pattern")
# Journeys: J5 (month-end close — the trail the close package draws on)
# ───────────────────────────────────────────────────────
"""US-AUD-007 and US-AUD-008, test case by test case.

NFR-28 says the audit retention "matches reads pattern", and the point of this
file is that the sentence is TRUE of the code and not just of the prose: every
bound asserted here comes from the same `core.archival` constants
tests/test_us_met_020_tc_archival.py asserts. There is one mechanism; these are
its two callers.
"""

import hashlib
from datetime import date, datetime, timedelta, timezone

import pytest
from django.db import connection

from apps.audit import selectors
from apps.audit.models import ArchiveJobRun
from core import archival, partitioning

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — the two-tenant world
from tests.isolation_helpers import writing_as_tenant
from tests.test_us_met_reads_helpers import tenant_ctx  # noqa: F401

TODAY = date(2028, 9, 1)  # §4: the monthly run of 2028-09-01 02:00 UTC
OLD_MONTH = date(2026, 8, 1)  # `audit_log_2026_08` — the partition §4 archives

# The LIVE tests plan against the real clock rather than §4's 2028 date, and the
# reason is worth stating: `audit_log` is one of the archived tables, so a run
# planned two years in the future would detach the partition this very test's
# audit rows are being written into. The story's dates are asserted by the pure
# planner above, where no clock is involved; the live halves use a partition that
# is genuinely outside today's hot window (ARCHIVABLE_MONTH) and one genuinely
# past the 7-year bound (ANCIENT_MONTH).
LIVE_RUN = date.today()
ARCHIVABLE_MONTH = date(LIVE_RUN.year - 2, 1, 1)  # > 24 months old, < 7 years
ANCIENT_MONTH = date(LIVE_RUN.year - 8, 1, 1)  # past the 7-year bound


# ── the shared bound, from the audit side (NFR-28) ──────────────────────────
def test_us_aud_007_tc0__the_bound_is_the_same_object_the_reads_story_uses():
    """ "Matches reads pattern" asserted as identity, not as similarity: if these
    two ever became separate constants, this test is what would notice."""
    assert archival.HOT_WINDOW_MONTHS == 24 and archival.RETENTION_MONTHS == 84
    assert "audit_log" in archival.ARCHIVED_TABLES
    assert "meter_reads" in archival.ARCHIVED_TABLES
    assert archival.hot_floor(TODAY) == date(2026, 9, 1)
    assert archival.retention_floor(TODAY) == date(2021, 9, 1)


# ── TC-1 — only what is fully older than the hot window ─────────────────────
def test_us_aud_007_tc1__the_2028_09_run_reaches_2026_08_and_nothing_younger():
    attached = ["audit_log_2026_08", "audit_log_2026_09", "audit_log_2028_08"]
    assert archival.archivable("audit_log", TODAY, attached) == ["audit_log_2026_08"]


# ── TC-3 — the 7-year purge, and never younger ──────────────────────────────
def test_us_aud_007_tc3__the_2033_run_purges_2026_08_and_nothing_younger():
    """§4's purge fixture: run 2033-09-01 against Aug-2026 data."""
    detached = ["audit_log_2026_08", "audit_log_2026_09", "audit_log_2027_01"]
    assert archival.purgeable("audit_log", date(2033, 9, 1), detached) == ["audit_log_2026_08"]
    assert archival.purgeable("audit_log", TODAY, detached) == []  # nothing yet in 2028


# ── TC-4 (negative) — never manual ──────────────────────────────────────────
def test_us_aud_007_tc4__there_is_no_manual_trigger_skip_or_early_run():
    from apps.audit import api, services

    with pytest.raises(archival.ManualInvocationRefused):
        archival.run_archival("audit_log", TODAY)
    assert not any("archiv" in str(entry.pattern).lower() for entry in api.urlpatterns)
    # No service function and no BE-07 job kind exposes it either.
    assert not any(name.startswith("run_archiv") for name in dir(services))


# ── TC-6 (immutability) — deletion exists ONLY as the supervised purge ──────
def test_us_aud_007_tc6__archival_never_updates_or_deletes_a_row():
    """BR-AUD-002. Read off the module's own source rather than asserted in
    prose: a future edit that introduced a row-level DELETE here would go red."""
    import ast
    import inspect

    # Only the SQL this module actually EXECUTES — docstrings and comments are
    # stripped, so the paragraph in core/archival.py that DESCRIBES the rule
    # cannot be what satisfies the test (that would be circular).
    tree = ast.parse(inspect.getsource(archival))
    executed = [
        ast.unparse(node).upper()
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "execute"
    ]
    assert executed, "no SQL found at all — this guard would be vacuous"
    for statement in executed:
        assert "DELETE FROM" not in statement, statement
        assert "UPDATE " not in statement or "ALTER TABLE" in statement, statement
    # The only destructive statement is DROP TABLE of an already-DETACHED one.
    assert any("DROP TABLE" in statement for statement in executed)


# ── live: detach, self-audit, run record, rerun no-op ───────────────────────
def _make_old_partition(month: date) -> str:
    name = partitioning.partition_name("audit_log", month)
    with connection.cursor() as cursor:
        cursor.execute(partitioning.create_partition_sql("audit_log", month))
    return name


def _seed_old_row(tenant_id, when: datetime) -> None:
    """One trail row inside the old partition. `created_at` is auto_now_add, so
    it is written directly — the row is HISTORY the test starts from.

    ⚠ **WRITTEN INSIDE THAT TENANT'S OWN CONTEXT (DEF-GOV-4024/4036,
    2026-09-05).** `audit_log` carries FORCE ROW LEVEL SECURITY on the
    partitioned parent (BR-AUD-007), so WITH CHECK applies to the table owner
    too and refuses an INSERT made with no `app.tenant_id`. This ran
    contextless and was taken only because the test connection was a SUPERUSER.
    Each call names ONE tenant, so each write is lawful on its own — which is
    what lets the callers below seed two different tenants into the SAME
    partition, the thing TC-7 is about.
    """
    with writing_as_tenant(tenant_id), connection.cursor() as cursor:
        cursor.execute(
            "INSERT INTO audit_log (id, tenant_id, actor_user_id, action, entity_type, "
            "entity_id, before, after, created_at) VALUES "
            "(gen_random_uuid(), %s, NULL, 'invoice.issued', 'invoice', NULL, NULL, NULL, %s)",
            [str(tenant_id), when],
        )


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_aud_007_tc1_tc2_tc5__detach_audits_itself_and_reruns_as_a_no_op(
    brazos, lonestar, audit_rows
):
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — audit_log is a plain table there (audit 0001)")
    partition = _make_old_partition(ARCHIVABLE_MONTH)
    moment = datetime(ARCHIVABLE_MONTH.year, 1, 14, 9, 15, tzinfo=timezone.utc)
    _seed_old_row(brazos.id, moment)
    _seed_old_row(lonestar.id, moment)  # TC-7: the partition is SHARED

    # ✅ GREEN SINCE 2026-09-07 — `DEF-AUD-4080` / `OQ-AUD-1724` are CLOSED, and
    # the history is kept here because it is what these assertions are FOR.
    # This case was RED for two weeks and deliberately so: `_manifest` and
    # `_tenants_in` read the partition on a bare cursor with NO `app.tenant_id`,
    # and `audit_log` is FORCE-RLS'd on the parent (BR-AUD-007), so on the role
    # production actually uses — typed `NOSUPERUSER NOBYPASSRLS` by
    # 10-scripts/13-provision-database.sh — the count came back 0 over a
    # partition holding two and the sha256 was the digest of the empty string.
    # The DETACH happened anyway, so the data was filed and the receipt lied.
    # **The assertions were never adjusted**, which is the only reason the
    # ruling had something true to be measured against: the PO ruled on
    # 2026-09-07 that the job runs ONCE PER UTILITY, and it now reads inside
    # each one's identity. Bypassing row-level security was the easy repair and
    # stays refused (PO 2026-08-24, OQ-354). Anyone tempted to "simplify" the
    # per-utility loop in core/archival.py: this case is what goes red.
    run = archival.run_archival("audit_log", LIVE_RUN, invoked_by=archival.SCHEDULER)
    archived = {entry["partition"]: entry for entry in run.archived}
    assert partition in archived
    entry = archived[partition]
    assert entry["row_count"] >= 2
    assert len(entry["sha256"]) == 64
    assert sorted(entry["tenants"]) == sorted([str(brazos.id), str(lonestar.id)])
    assert partition not in [e["partition"] for e in run.purged]  # nowhere near 7 yr

    # TC-2: the job audits ITSELF — one row per affected tenant, each carrying
    # that tenant's id because the writer entered THAT tenant's context
    # (BR-AUD-007; the id on the row is the proof the context was entered).
    written = [
        row
        for row in audit_rows
        if row["action"] == "audit_log.partition_archived"
        and row["after"]["partition"] == partition
    ]
    assert sorted(str(row["tenant_id"]) for row in written) == sorted(
        [str(brazos.id), str(lonestar.id)]
    )
    for row in written:
        assert row["actor_user_id"] is None  # BR-AUD-003: a system job, no actor
        assert row["after"]["job"] == "archive_partitions"
        assert row["after"]["shipped"] is False  # never a transfer it did not make

    record = ArchiveJobRun.objects.filter(table_name="audit_log").latest("created_at")
    assert (record.hot_window_months, record.retention_months) == (24, 84)

    # TC-5: a duplicate fire. Nothing double-detached, no error, run recorded.
    rerun = archival.run_archival("audit_log", LIVE_RUN, invoked_by=archival.SCHEDULER)
    assert partition not in [e["partition"] for e in rerun.archived]
    assert ArchiveJobRun.objects.filter(table_name="audit_log").count() >= 2


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_aud_007_tc3b__the_purge_drops_the_cold_partition_and_records_it(brazos, audit_rows):
    """The 7-year step, live.

    A partition already past the bound is detached AND purged by the same run,
    which is correct and is asserted rather than worked around: the hot window
    and the retention bound are two separate tests on the same partition, and a
    partition can fail both at once.
    """
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — audit_log is a plain table there (audit 0001)")
    # ✅ GREEN SINCE 2026-09-07 — `DEF-AUD-4080` / `OQ-AUD-1724`, closed. This
    # case was RED because `_purge_one` built its audit rows from a tenant list
    # read with no context, so the list was empty and the DROP happened having
    # written nothing — against its own docstring, *"the trail has to be able to
    # say what was destroyed"*. It now accounts for the partition one utility at
    # a time BEFORE the drop, and refuses to drop a partition it could not fully
    # account for. See the note in TC-1 above.
    partition = _make_old_partition(ANCIENT_MONTH)
    _seed_old_row(brazos.id, datetime(ANCIENT_MONTH.year, 1, 9, 12, 0, tzinfo=timezone.utc))

    run = archival.run_archival("audit_log", LIVE_RUN, invoked_by=archival.SCHEDULER)
    assert partition in [e["partition"] for e in run.archived]
    assert partition in [e["partition"] for e in run.purged]
    with connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass(%s) IS NULL", [partition])
        assert cursor.fetchone()[0] is True  # the table is gone
    purged = [
        row
        for row in audit_rows
        if row["action"] == "audit_log.partition_purged" and row["after"]["partition"] == partition
    ]
    assert len(purged) == 1
    assert purged[0]["after"]["retention_years"] == 7
    assert str(purged[0]["tenant_id"]) == str(brazos.id)


# ── DEF-AUD-4080 / OQ-AUD-1724 — the receipt has to be TRUE, not merely present
#
# The two cases above assert `row_count >= 2` and `len(sha256) == 64`, and the
# second of those is a check that CANNOT FAIL: **the sha256 of the empty string
# is also 64 characters long.** The whole defect was a manifest computed over
# nothing, so a length assertion would have passed on it happily and did — it
# was the COUNT that went red, and a partition holding rows for one tenant only
# would not even have moved the count far enough to notice.
#
# So these pin the figures themselves: an exact count, a digest that is provably
# not the digest of nothing, a digest that is reproducible from the per-utility
# parts it claims to be folded from, and two utilities' digests that differ from
# each other. Between them there is no way to satisfy this file without actually
# reading the rows.
EMPTY_DIGEST = hashlib.sha256(b"").hexdigest()


@pytest.mark.isolation
@pytest.mark.django_db
def test_def_aud_4080__the_receipt_names_a_real_count_and_a_digest_of_real_bytes(
    brazos, lonestar, audit_rows
):
    """One partition, two utilities, one row each — and the receipt says so."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — audit_log is a plain table there (audit 0001)")
    partition = _make_old_partition(ARCHIVABLE_MONTH)
    moment = datetime(ARCHIVABLE_MONTH.year, 1, 3, 8, 30, tzinfo=timezone.utc)
    _seed_old_row(brazos.id, moment)
    _seed_old_row(lonestar.id, moment)

    run = archival.run_archival("audit_log", LIVE_RUN, invoked_by=archival.SCHEDULER)
    assert run.status == "success", run.note
    entry = next(one for one in run.archived if one["partition"] == partition)

    # THE COUNT: exactly the two rows that were seeded, not "at least".
    assert entry["row_count"] == 2
    # THE DIGEST: of real bytes. `EMPTY_DIGEST` is what the defect produced and
    # it is 64 characters long, which is why the length assertion above could
    # never have caught this.
    assert entry["sha256"] != EMPTY_DIGEST

    # THE BREAKDOWN: one line per utility, each with its OWN row and its own
    # digest of real bytes — and the two differ, because the rows differ.
    by_tenant = {one["tenant_id"]: one for one in entry["by_tenant"]}
    assert sorted(by_tenant) == sorted([str(brazos.id), str(lonestar.id)])
    for one in by_tenant.values():
        assert one["row_count"] == 1
        assert one["sha256"] != EMPTY_DIGEST
    assert by_tenant[str(brazos.id)]["sha256"] != by_tenant[str(lonestar.id)]["sha256"]

    # THE FOLD IS REPRODUCIBLE from the parts it claims to be made of. A
    # partition digest that could not be recomputed would be a number nobody
    # could ever check a shipment against, which is the only reason it exists.
    ordered = sorted(entry["by_tenant"], key=lambda one: one["tenant_id"])
    recomputed = hashlib.sha256(
        "\n".join(f"{one['tenant_id']}:{one['sha256']}" for one in ordered).encode("utf-8")
    ).hexdigest()
    assert entry["sha256"] == recomputed

    # AND THE RUN SAYS HOW MANY IDENTITIES IT ENTERED, so a zero count beside a
    # zero here (an enumeration that found nobody) can never be mistaken for a
    # zero count beside forty (a genuinely empty partition).
    assert entry["tenants_read"] >= 2
    assert entry["unreadable"] == []

    # THE SELF-AUDIT ROWS CARRY THAT UTILITY'S OWN FIGURES — one row each, and
    # the count on each is 1 rather than the partition's 2. A partition-wide
    # number on a tenant's row would tell each utility roughly how much traffic
    # its neighbours make.
    written = {
        str(row["tenant_id"]): row
        for row in audit_rows
        if row["action"] == "audit_log.partition_archived"
        and row["after"]["partition"] == partition
    }
    assert sorted(written) == sorted([str(brazos.id), str(lonestar.id)])
    for tenant_id, row in written.items():
        assert row["after"]["row_count"] == 1
        assert row["after"]["sha256"] == by_tenant[tenant_id]["sha256"]

    # And the platform record holds the same figures a screen would read back.
    record = ArchiveJobRun.objects.filter(table_name="audit_log").latest("created_at")
    stored = next(one for one in record.archived if one["partition"] == partition)
    assert stored["row_count"] == 2 and stored["sha256"] == entry["sha256"]


@pytest.mark.isolation
@pytest.mark.django_db
def test_def_aud_4080__one_utility_failing_holds_the_partition_and_leaves_the_rest_usable(
    monkeypatch, brazos, lonestar
):
    """Hard-won law 14, on the database that can actually show it.

    The run reads as each utility in turn. If one of those reads fails, two
    things must be true and NEITHER of them is what the obvious code does:

      * the transaction must still be usable afterwards — on PostgreSQL a
        failed statement aborts the whole transaction, so `except: continue`
        loses every later query to `InFailedSqlTransaction` and the run dies at
        COMMIT. The nested `transaction.atomic()` savepoint is what makes the
        loop survive, and **the default suite is in-memory SQLite, which has no
        aborted-transaction state and cannot show this at all**;
      * the partition must NOT be detached. A manifest missing one utility's
        rows under-reports, and filing data away under an under-reporting
        receipt is `DEF-AUD-4080` over again.

    The failure injected here is a REAL database error (`SELECT 1 / 0`), not a
    Python one, because a Python exception would never poison the transaction
    and the test would prove nothing about the savepoint.
    """
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — no aborted-transaction state, so this proves nothing")
    partition = _make_old_partition(ARCHIVABLE_MONTH)
    moment = datetime(ARCHIVABLE_MONTH.year, 1, 4, 11, 45, tzinfo=timezone.utc)
    _seed_old_row(brazos.id, moment)
    _seed_old_row(lonestar.id, moment)

    real_slice = archival._tenant_slice
    seen = {"calls": 0}

    def one_bad_read(cursor, name):
        seen["calls"] += 1
        if seen["calls"] == 1:
            cursor.execute("SELECT 1 / 0")  # aborts this transaction, for real
        return real_slice(cursor, name)

    monkeypatch.setattr(archival, "_tenant_slice", one_bad_read)

    run = archival.run_archival("audit_log", LIVE_RUN, invoked_by=archival.SCHEDULER)

    # The run is neither a success nor a skip, and it says which partition and
    # how many utilities — `archive_status` surfaces status and note on S61.
    assert run.status == "partial"
    assert partition in (run.note or "")
    assert partition not in [one["partition"] for one in run.archived]
    # Still attached: nothing was filed under a manifest that could not account
    # for it. The next scheduled run picks it up.
    assert partition in partitioning.partition_children("audit_log")
    # The loop kept going after the bad read rather than dying on it.
    assert seen["calls"] > 1
    # LAW 14, ASSERTED: the connection still works. Without the savepoint this
    # raises InFailedSqlTransaction and every later query in the job is lost.
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1


@pytest.mark.isolation
@pytest.mark.django_db
def test_def_aud_4080__the_run_refuses_outright_if_the_tenant_registry_stops_being_readable(
    brazos,
):
    """The guard for the NEXT version of this defect.

    The enumeration reads `tenants` with no tenant context, which is lawful only
    because `tenants` is a platform table with no policy on it. Give it one and
    the read returns NOBODY — every partition then manifests as empty, quietly,
    with every check in the suite green, because no test can assert a row count
    it does not already know. So the module checks the claim rather than
    trusting it, and this is that check being made to fire.
    """
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — no row-level security to switch on")
    assert archival.tenant_ids_for_run(), "no utilities at all — this guard would be vacuous"
    with connection.cursor() as cursor:
        # ⚠ **`SET CONSTRAINTS ALL IMMEDIATE` FIRST — A HARNESS ARTEFACT, NOT
        # ANYTHING THIS GUARD NEEDS (`DEF-AUD-6784`, 2026-09-25).** Django wraps
        # the case in one transaction and this repo's foreign keys are
        # `DEFERRABLE INITIALLY DEFERRED`, so the rows the `brazos` fixture
        # writes leave **pending trigger events** on `tenants`. PostgreSQL then
        # refuses the very next statement:
        #
        #     django.db.utils.OperationalError: cannot ALTER TABLE "tenants"
        #     because it has pending trigger events
        #
        # That aborted the transaction, so this case FAILED and then ERRORED in
        # teardown — one of the two errors in the 2026-09-25 isolation proof,
        # and an error is a case nobody knows anything about. Flushing the
        # deferred checks puts the connection in the state a real caller finds.
        # The same line, for the same reason, is in `test_cr135_p0_rls_pg.py`
        # and `test_us_led_journal_core.py`.
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
        cursor.execute(f"ALTER TABLE {archival.TENANT_REGISTRY_TABLE} ENABLE ROW LEVEL SECURITY")
    try:
        with pytest.raises(archival.ArchivalRefused) as raised:
            archival.tenant_ids_for_run()
        assert "row-level security" in str(raised.value)
        assert "EMPTY" in str(raised.value)  # it names the failure it is preventing
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                f"ALTER TABLE {archival.TENANT_REGISTRY_TABLE} DISABLE ROW LEVEL SECURITY"
            )


# ── US-AUD-008 — archive search ─────────────────────────────────────────────
@pytest.mark.django_db
def test_us_aud_008_tc1__the_default_never_touches_cold_storage(brazos):
    """Toggle OFF is the default and is not merely "usually off": a hot query
    returns the plain queryset, which names one table and no partition."""
    result = selectors.audit_result_set(brazos.id, filters={})
    assert not isinstance(result, selectors.ArchiveResultSet)
    assert selectors.wants_archive({}) is False
    for token in ("0", "false", "no", "", "maybe", "arch"):
        assert selectors.wants_archive({"archive": token}) is False
    for token in ("1", "true", "yes", "on", "TRUE"):
        assert selectors.wants_archive({"archive": token}) is True


@pytest.mark.django_db
def test_us_aud_008_tc4__no_unbounded_archive_query_exists(brazos):
    """BR-AUD-013/NFR-3: even with the opt-in ON and no date filter, the query
    starts at the 7-year floor — there is no code path that asks for everything."""
    floor = selectors.window_floor(archive=True)
    assert (datetime.now(timezone.utc) - floor).days == selectors.RETENTION_DAYS
    hot = selectors.window_floor(archive=False)
    assert (datetime.now(timezone.utc) - hot).days == selectors.HOT_WINDOW_DAYS
    # ...and a `from` older than the floor cannot widen it (the floor is the law).
    queryset = selectors.audit_queryset(brazos.id, filters={"from": "1999-01-01"})
    assert str(hot.date()) in str(queryset.query) or "created_at" in str(queryset.query)


@pytest.mark.isolation
@pytest.mark.django_db
def test_us_aud_008_tc2_tc7__the_opt_in_reads_cold_rows_labelled_and_tenant_scoped(
    brazos, lonestar
):
    """TC-2 (archived rows return, labelled "Archive") and TC-7 (zero foreign
    rows) on the SAME shared partition — which is the only way TC-7 means
    anything, since partitions hold every tenant's rows."""
    if connection.vendor != "postgresql":
        pytest.skip("vendor sqlite — nothing is partitioned, so nothing detaches")
    _make_old_partition(OLD_MONTH)
    moment = datetime.now(timezone.utc) - timedelta(days=900)  # outside the hot window
    month = partitioning.month_start(moment.date())
    if month != OLD_MONTH:
        _make_old_partition(month)
    _seed_old_row(brazos.id, moment)
    _seed_old_row(lonestar.id, moment)
    archival.run_archival("audit_log", date.today(), invoked_by=archival.SCHEDULER)
    assert archival.detached_partitions("audit_log"), "nothing archived — guard is vacuous"

    with tenant_ctx(brazos):
        hot = selectors.audit_result_set(brazos.id, filters={})
        cold = selectors.audit_result_set(brazos.id, filters={}, archive=True)
        assert cold.count() > hot.count(), "the archive opt-in returned no extra rows"
        page = selectors.audit_page(brazos.id, list(cold[0:50]), archive=True)
        labels = {row["window"] for row in page}
        assert "archive" in labels  # TC-2: visibly labelled
        # TC-7, zero tolerance: not one Lone Star Ridge row in the answer.
        assert all(str(row.tenant_id) == str(brazos.id) for row in cold[0:50])

    with tenant_ctx(lonestar):
        theirs = selectors.audit_result_set(lonestar.id, filters={}, archive=True)
        assert all(str(row.tenant_id) == str(lonestar.id) for row in theirs[0:50])


@pytest.mark.django_db
def test_us_aud_008_tc6__the_archive_is_a_read_path_with_no_restore_or_edit(brazos):
    """BR-AUD-002: no rehydrate-into-hot, no edit, no attach-back. The module
    publishes none of them, and this asserts the absence rather than a refusal."""
    for forbidden in ("restore", "rehydrate", "reattach", "attach_partition", "unarchive"):
        assert not hasattr(archival, forbidden)
        assert not hasattr(selectors, forbidden)

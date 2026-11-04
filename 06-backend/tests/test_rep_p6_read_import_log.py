# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — R32 Read Import Log, the joining read.
#           Drawings read as IMAGES (B14 rule 42): p064 (the table and the
#           tiles) and p065 (the savepoint warning).
# Rules:    NFR-3 (pagination in SQL) · NFR-5 (no hard caps) · BR-MET-032
#           (validate-then-accept — `warning` is an ACCEPTED row) ·
#           BR-MET-017 (a posted batch is immutable) · BR-REP-024 (never a 0
#           where a figure is not derivable) · CLAUDE.md hard rule 1 (tenant
#           scoping) · B14 rule 31 (no uuid on screen)
# ───────────────────────────────────────────────────────
"""**R32 READ IMPORT LOG** — one row per read-import batch.

⚠ **EVERY CASE ASSERTS A KNOWN NON-ZERO COUNT**, and the fixture is built so
no two subsets share a sum: an assertion that passes on the wrong grouping is
not an assertion.

⚠ **NOTHING HERE SKIPS.** ⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE**, so these
cases prove the SHAPE and the ARITHMETIC and nothing about cost or the query
plan (hard-won law 14). The PostgreSQL half is `10-scripts/p6_join_cost.py`.
"""

from datetime import date, timedelta

import pytest
from django.utils import timezone

from apps.metering import models as metering_models
from apps.metering import read_import_log as report
from apps.reports import datasets, queries, runner

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: Three batches whose counts share no sum with any subset of the others, so
#: every total below names one arrangement and only one.
#:   handheld  · 10 rows · 10 ok           ·  0 error  → CLEAN
#:   ami batch ·  7 rows ·  4 ok + 1 warn  ·  2 error  → WITH REJECTIONS
#:   backfill  ·  3 rows ·  0 ok           ·  3 error  → ALL REJECTED
BATCHES = 3
ROWS = 20
ACCEPTED = 15  # 10 + (4 ok + 1 warning) — a WARNING row loaded and is ACCEPTED
REJECTED = 5  # 2 + 3
WARNINGS = 1


def _baseline():
    """What this tenant already holds, before the fixture adds anything.

    ⚠ **THE `brazos` FIXTURE PROVISIONS A REAL UTILITY AND A REAL UTILITY MAY
    ALREADY HOLD IMPORTS.** The first draft asserted absolutes and would have
    been a test of the fixture rather than of the report. Every case reads this
    first and asserts the MOVEMENT — and also asserts the absolute is non-zero,
    so an empty answer still fails.
    """
    return report.read_import_log(per=None)["totals"]


def _batch(tenant, actor, *, file_name, source_kind, ok, warn, error, days_ago, counts=None):
    batch = metering_models.ReadImportBatch.objects.create(
        tenant=tenant,
        file_name=file_name,
        source_kind=source_kind,
        # `dana` is a namespace carrying the membership AND the user; the FK
        # wants the user.
        uploaded_by=getattr(actor, "user", actor),
        uploaded_at=timezone.now() - timedelta(days=days_ago),
        status="posted",
        counts=counts,
    )
    row_no = 0
    for severity, how_many in (("ok", ok), ("warning", warn), ("error", error)):
        for _ in range(how_many):
            row_no += 1
            metering_models.ReadImportRow.objects.create(
                tenant=tenant, batch=batch, row_no=row_no, severity=severity
            )
    return batch


def _three(tenant, actor):
    return (
        _batch(
            tenant,
            actor,
            file_name="cy09b-r01.csv",
            source_kind="csv",
            ok=10,
            warn=0,
            error=0,
            days_ago=1,
        ),
        _batch(
            tenant,
            actor,
            file_name="cy09b-r02.csv",
            source_kind="ami_replay",
            ok=4,
            warn=1,
            error=2,
            days_ago=2,
        ),
        _batch(
            tenant,
            actor,
            file_name="backfill-aug.csv",
            source_kind="manual",
            ok=0,
            warn=0,
            error=3,
            days_ago=3,
        ),
    )


def test_one_row_is_one_batch_and_the_totals_foot_to_the_whole_set_not_the_page(brazos, dana):
    """p064's footer — `Total 81,204 · 80,918 · 286` — is the sum of the column
    and the tile above it is the same sum over the whole filtered set."""
    with tenant_ctx(brazos):
        before = _baseline()
        _three(brazos, dana)
        result = report.read_import_log(per=2, page=1)

    assert result["grain"] == "one read-import batch"
    assert len(result["rows"]) == 2  # the page
    totals = result["totals"]
    # The tile is the WHOLE set and the page is two — they must differ, or this
    # case cannot tell a tile struck over the page from one struck over the set.
    assert result["total"] > len(result["rows"])
    assert result["total"] == totals["imports"]
    assert totals["imports"] - before["imports"] == BATCHES
    assert totals["rows"] - before["rows"] == ROWS
    assert totals["accepted"] - before["accepted"] == ACCEPTED
    assert totals["rejected"] - before["rejected"] == REJECTED
    # ⚠ THE FOOTING IDENTITY, asserted rather than assumed — over the WHOLE
    # set, so it holds whatever the tenant already carried.
    assert totals["accepted"] + totals["rejected"] == totals["rows"]
    assert totals["rows"] > 0


def test_a_WARNING_row_is_ACCEPTED_because_it_loaded_and_carries_a_flag(brazos, dana):
    """`BR-MET-032` validate-then-accept — the one judgment in the read model.

    Counting warnings as rejections would make the ACCEPTED tile disagree with
    what a clerk sees when they open the batch, and every one of those rows IS
    in the database.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _three(brazos, dana)
        result = report.read_import_log(per=None)

    ami = next(row for row in result["rows"] if row.file_name == "cy09b-r02.csv")
    assert ami.rows == 7
    assert ami.accepted == 5  # 4 ok + 1 warning
    assert ami.rejected == 2
    assert ami.warnings == WARNINGS
    assert result["totals"]["warnings"] - before["warnings"] == WARNINGS
    assert "warning" not in report.SEVERITY_REJECTED
    assert "warning" in report.SEVERITY_ACCEPTED


def test_the_counts_blob_is_NOT_read_and_a_disagreement_is_reported_with_BOTH_numbers(brazos, dana):
    """⚠ **THE CACHE IS BYPASSED AND COMPARED, NEVER TRUSTED.**

    `read_import_batches.counts` is a denormalised blob whose own column comment
    reads *"must reconcile"*. The batch below CLAIMS 999 rows and holds 10. The
    report serves 10 — the fact — and says so rather than hiding the
    disagreement behind the decision not to trust it.
    """
    with tenant_ctx(brazos):
        before = _baseline()
        _batch(
            brazos,
            dana,
            file_name="liar.csv",
            source_kind="csv",
            ok=10,
            warn=0,
            error=0,
            days_ago=1,
            counts={"in": 999},
        )
        result = report.read_import_log(per=None)

    row = next(r for r in result["rows"] if r.file_name == "liar.csv")
    assert row.rows == 10  # the aggregate, not the blob
    assert row.counts_disagree == {"stored": 999, "counted": 10}
    # ⚠ THE TOTAL FOLLOWS THE ROWS AND NOT THE BLOB. If the blob were read,
    # this movement would be 999.
    assert result["totals"]["rows"] - before["rows"] == 10
    codes = {problem["code"] for problem in result["problems"]}
    assert "the_stored_counts_blob_disagrees_with_the_rows" in codes


def test_a_batch_whose_blob_AGREES_reports_no_disagreement(brazos, dana):
    """The mirror, so the check above cannot pass by always firing — hard-won
    law 7 habit (2): a check you cannot describe a false pass for is one you do
    not understand."""
    with tenant_ctx(brazos):
        _batch(
            brazos,
            dana,
            file_name="honest.csv",
            source_kind="csv",
            ok=10,
            warn=0,
            error=0,
            days_ago=1,
            counts={"in": 10},
        )
        result = report.read_import_log(per=None)

    row = next(r for r in result["rows"] if r.file_name == "honest.csv")
    assert row.counts_disagree is None
    codes = {problem["code"] for problem in result["problems"]}
    assert "the_stored_counts_blob_disagrees_with_the_rows" not in codes


def test_rejections_sit_BESIDE_accepted_rows_which_is_the_savepoint_s_evidence(brazos, dana):
    """p065: *"The 286 rejections are proof the savepoint is real."*

    A batch with BOTH accepted and rejected rows is what proves a rejection was
    skipped inside its own savepoint rather than aborting the import. So
    REJECTED is never folded into a status word and never suppressed when
    ACCEPTED is non-zero.
    """
    with tenant_ctx(brazos):
        _three(brazos, dana)
        result = report.read_import_log(per=None)

    mixed = [row for row in result["rows"] if row.accepted > 0 and row.rejected > 0]
    assert any(row.file_name == "cy09b-r02.csv" for row in mixed)


def test_accepted_share_is_NULL_over_a_set_with_no_rows_and_never_zero_percent(brazos, dana):
    """`BR-REP-024` — *no import had any rows* and *every row was rejected* are
    opposite facts and 0% is only one of them."""
    with tenant_ctx(brazos):
        _batch(
            brazos,
            dana,
            file_name="empty.csv",
            source_kind="csv",
            ok=0,
            warn=0,
            error=0,
            days_ago=1,
        )
        # A window holding ONLY the empty import — the zero-denominator case.
        today = date.today()
        empty = report.read_import_log(start=today - timedelta(days=1), end=today, per=None)
        _three(brazos, dana)
        populated = report.read_import_log(per=None)

    assert empty["totals"]["rows"] == 0
    assert empty["totals"]["accepted_pct"] is None
    codes = {problem["code"] for problem in empty["problems"]}
    assert "accepted_share_is_undefined_over_a_set_with_no_rows" in codes
    # The positive case beside the null one.
    assert populated["totals"]["accepted_pct"] is not None
    assert populated["totals"]["accepted_pct"] > 0


def test_the_result_filter_is_a_HAVING_over_the_counts_and_is_HONOURED(brazos, dana):
    """The drawn `Result` select is a statement about the ROWS, so it filters on
    the aggregate. A control declared and dropped shows every import under a
    chip that says otherwise."""
    with tenant_ctx(brazos):
        _three(brazos, dana)
        unfiltered = report.read_import_log(per=None)
        clean = report.read_import_log(result=report.RESULT_CLEAN, per=None)
        with_rejections = report.read_import_log(result=report.RESULT_WITH_REJECTIONS, per=None)
        all_rejected = report.read_import_log(result=report.RESULT_ALL_REJECTED, per=None)

    def names(view):
        return {row.file_name for row in view["rows"]}

    assert "cy09b-r01.csv" in names(clean)
    assert "cy09b-r02.csv" not in names(clean)
    assert names(with_rejections) >= {"cy09b-r02.csv", "backfill-aug.csv"}
    assert "cy09b-r01.csv" not in names(with_rejections)
    assert "backfill-aug.csv" in names(all_rejected)
    assert "cy09b-r02.csv" not in names(all_rejected)  # it has accepted rows too
    # ⚠ EACH NARROWS. A chip that changes nothing is the mirror of dead UI.
    for view in (clean, with_rejections, all_rejected):
        assert view["total"] < unfiltered["total"]
        assert view["total"] > 0


def test_it_sorts_by_an_AGGREGATE_in_SQL_and_the_order_is_total(brazos, dana):
    """`rejected` is an annotation, so ordering by it is an `ORDER BY` and not a
    Python `sorted()` over a materialised page."""
    with tenant_ctx(brazos):
        _three(brazos, dana)
        descending = report.read_import_log(sort="rejected", direction="desc", per=None)
        ascending = report.read_import_log(sort="rejected", direction="asc", per=None)

    high = [row.rejected for row in descending["rows"]]
    low = [row.rejected for row in ascending["rows"]]
    assert high == sorted(high, reverse=True)
    assert low == sorted(low)
    # ⚠ THE ENDS MUST REVERSE. Equal firsts mean `direction` was ignored, or
    # the sort was applied in Python after the page.
    assert high[0] != low[0]
    assert high[0] == 3  # backfill-aug.csv, all three rejected
    assert "accepted_pct" not in report.IMPORT_LOG_SORTS  # no caret over a dead sort


def test_paging_repeats_nothing_and_skips_nothing(brazos, dana):
    with tenant_ctx(brazos):
        _three(brazos, dana)
        whole = report.read_import_log(per=None)
        # `ceil`, not `// + 2` — `BR-SHL-011` CLAMPS a page past the end to
        # the last one, so an over-run counts the final page twice.
        last_page = max(1, -(-whole["total"] // 2))
        pages = [report.read_import_log(per=2, page=page) for page in range(1, last_page + 1)]

    total = whole["total"]
    assert total > 2  # or there is one page and this case proves nothing
    assert len(pages[0]["rows"]) == 2
    seen = [row.batch_id for page in pages for row in page["rows"]]
    assert len(seen) == total
    assert len(set(seen)) == total


def test_the_export_stream_takes_no_page_and_no_per_at_all(brazos, dana):
    import inspect

    signature = inspect.signature(report.read_import_log_stream)
    assert "page" not in signature.parameters
    assert "per" not in signature.parameters

    with tenant_ctx(brazos):
        _three(brazos, dana)
        paged = report.read_import_log(per=2, page=1)
        streamed = list(report.read_import_log_stream())
    assert len(streamed) == paged["total"]
    assert len(streamed) > len(paged["rows"])
    assert sum(row.rows for row in streamed) == paged["totals"]["rows"]


def test_the_drawn_controls_are_DECLARED_on_the_dataset_so_bind_cannot_drop_them(brazos):
    """`runner.bind` drops any parameter the DATASET does not declare, so the
    drawn `Source` and `Result` selects had to be added to `METER_READS.filters`
    — otherwise both would change the URL and nothing else."""
    reads = datasets.BY_CODE["meter_reads"]
    assert "source" in reads.filters
    assert "result" in reads.filters
    definition = runner.resolve("read_import_log")
    bound = runner.bind(definition, {"source": "ami_replay", "result": "clean"})
    assert bound["source"] == "ami_replay"
    assert bound["result"] == "clean"


def test_the_per_key_viewer_wins_over_the_dataset_that_refuses_this_report(brazos):
    assert queries.VIEWERS["read_import_log"] is queries.read_import_log
    assert runner.queries_for("read_import_log", "meter_reads") is queries.read_import_log
    assert queries.definition_refusal("read_import_log", "meter_reads") is None


def test_the_export_reaches_the_per_key_STREAM_and_not_the_dataset_generator(brazos):
    assert runner.stream_for("read_import_log", "meter_reads") is queries.read_import_log_rows


def test_no_uuid_is_a_drawn_column(brazos):
    """B14 rule 31 — `batch_id` travels for the DETAIL drill-through only."""
    assert "batch_id" not in queries.IMPORT_LOG_COLUMNS
    assert "file_name" in queries.IMPORT_LOG_COLUMNS

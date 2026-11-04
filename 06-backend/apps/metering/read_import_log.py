# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — the JOINING READ behind R32 Read Import
#           Log. Drawing read as an IMAGE (B14 rule 42): p064, rendered at 2.6x
#           by `10-scripts/pdf/pdf_render.py`; its commentary continues on p065.
# Story:    R32 `read_import_log` — Operations › Reads · **Import date**
#           (`reports/migrations/0003_seed_catalogue.py` line 250).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `tenant_id` on every
#           queryset, RLS FORCE underneath) · hard rule 3 (a quantity carries
#           its unit — this report serves COUNTS, which carry none, and serves
#           no reading value at all) · NFR-3 (server pagination applied IN SQL)
#           · NFR-5 (no hard caps) · BR-MET-014 (batch tags and their row-level
#           overrides) · BR-MET-017 (a posted batch is immutable) ·
#           BR-MET-032 (validate-then-accept) · BR-REP-001 (a report states its
#           basis) · BR-REP-002 (read models only) · BR-REP-024 (never a 0
#           where a figure could not be computed) · hard-won law 14 (the
#           rejected row inside its own SAVEPOINT — the report's own warning)
# Tests:    06-backend/tests/test_rep_p6_read_import_log.py
#           10-scripts/p6_join_cost.py (the PostgreSQL measurement)
# Impacts:  apps/reports/report_seams.py (the cross-module caller) ·
#           apps/reports/queries.py (the per-key viewer) ·
#           apps/reports/datasets.py (`METER_READS.filters` gains `source`,
#           `result` and `status`)
# ───────────────────────────────────────────────────────
"""**R32 READ IMPORT LOG — one row per READ-IMPORT BATCH**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
THE EYEBROW LINE NAMES THE WRONG SOURCES, AND THE MEASUREMENT IS HERE
═══════════════════════════════════════════════════════════════════════════════
p064's eyebrow reads *Operations › Reads · **jobs + meter reads** · Import
date*. **Neither is the source.**

`jobs` is tenancy's table, and the brief's own §05 owner table says what it is
for: *"The one write this module makes. An export inserts a `jobs` row."* An
export job has nothing to do with a read import. And `meter_reads` is the table
a COMMITTED reading lands in — a rejected row never reaches it at all, so the
`REJECTED 286` tile and the `Rejected` column could not be computed from it in
either direction.

**The sources are `read_import_batches` and `read_import_rows`, both metering's
own** — and that is what makes this a genuine joining read rather than a
dataset query: one row is a BATCH and every count on it is an aggregate over
its ROWS. Filed as `DEF-REP-6921` with the two other misnamed source lines
rather than left in a docstring (hard-won law 1).

═══════════════════════════════════════════════════════════════════════════════
ONE ROW IS ONE BATCH, AND EVERY COUNT ON IT FOOTS
═══════════════════════════════════════════════════════════════════════════════
p064 draws `DATE · FILE · SOURCE · ROWS · ACCEPTED · REJECTED · BY · DETAIL`
with the tiles `IMPORTS 42 · ROWS 81,204 · ACCEPTED 80,918 (99.6%) ·
REJECTED 286` and a footer `Total 81,204 · 80,918 · 286`.

`ROWS`, `ACCEPTED` and `REJECTED` are **fully additive** — they are counts of
file rows, and no row belongs to two batches, so the footer is the sum of the
column and the tile is the same sum over the whole filtered set. `IMPORTS` is a
count of batches and is additive across SOURCE and over TIME alike: an import
that happened in July did not also happen in August.

⚠ **`ACCEPTED %` IS NON-ADDITIVE** — a percentage is recomputed from its
components, never averaged, so both components travel beside it, and it is
`None` rather than `0.0` when a filtered set holds no rows at all (`BR-REP-024`:
*no file had any rows* and *every row was rejected* are opposite facts and 0%
is only one of them).

═══════════════════════════════════════════════════════════════════════════════
THE COUNTS ARE AGGREGATED FROM THE ROWS AND NOT READ FROM `counts`
═══════════════════════════════════════════════════════════════════════════════
`ReadImportBatch.counts` is a JSON blob, and its own column comment in
`models.py` reads *"denormalized composition (**must reconcile**)"*. Its sibling
`ImportRun.counts` says the same thing at more length: *"a count that cannot be
checked against the rows is a number nobody can defend."*

**So this report does not read it.** `ROWS`, `ACCEPTED` and `REJECTED` are a
`GROUP BY batch_id` over `read_import_rows`, which is the fact itself rather
than a cache of it. Coordinator ruling, 2026-09-27: *"Aggregate the rows. Never
trust a denormalised cache whose own comment says it must reconcile."*

⚠ **AND THE CACHE IS CHECKED RATHER THAN IGNORED.** `counts_disagree` is
published per row when the blob and the aggregate differ, and
`GAP_COUNTS_BLOB_DISAGREES` carries BOTH numbers into `problems`. A cache that
is quietly bypassed goes on being wrong; one that is bypassed and compared is a
defect report. If it fires on a real tenant, that is a defect worth filing with
both numbers in it.

═══════════════════════════════════════════════════════════════════════════════
ACCEPTED AND REJECTED ARE DECIDED BY `severity`, AND `warning` IS ACCEPTED
═══════════════════════════════════════════════════════════════════════════════
`ReadImportRow.severity` is `ok | warning | error` — the *worst* rule outcome on
that row (`BR-MET-032` validate-then-accept). **A warning row is ACCEPTED**: it
loads, it bills, and it carries a flag. Only `error` is rejected.

That is the one judgment in this file and it is stated rather than assumed,
because the alternative — counting warnings as rejections — would make the
`ACCEPTED 99.6%` tile disagree with what a clerk sees when they open the batch,
and every one of those rows IS in the database. `SEVERITY_ACCEPTED` and
`SEVERITY_REJECTED` name the split in one place so the tile, the column and the
footer cannot drift apart.

═══════════════════════════════════════════════════════════════════════════════
THE DRAWN WARNING IS ABOUT SAVEPOINTS AND THIS REPORT IS ITS EVIDENCE
═══════════════════════════════════════════════════════════════════════════════
p065, verbatim: *"**A rejected row is skipped inside its own savepoint** —
hard-won law 14. Without the nested transaction the first rejection aborts the
whole import on PostgreSQL and every row is lost at commit, while the test suite
on SQLite passes. The 286 rejections are proof the savepoint is real."*

This file writes nothing and takes no savepoint — it is a read model. What it
must not do is hide the evidence: **a batch with rejections and accepted rows in
the SAME batch is what proves the savepoint works**, so `REJECTED` is never
folded into a status word and never suppressed when `ACCEPTED` is non-zero.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE EXPORT TAKES NO `page` AND NO `per`
═══════════════════════════════════════════════════════════════════════════════
The page is a `LIMIT`/`OFFSET` on a QuerySet and the order is an `ORDER BY`.
**Nothing is sorted or sliced in Python anywhere in this file**, including the
row counts: they arrive as annotations on the same queryset, so a sort by
`rejected` is a SQL sort over an aggregate and not a Python `sorted()` over a
materialised list.

`read_import_log_stream()` is a separate function with no `page` and no `per`.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()`, on any table.

**It serves no uuid as a visible value** (B14 rule 31) — `batch_no` and
`file_name` are what a clerk reads; `batch_id` travels for the DETAIL
drill-through and is not a drawn column.

**It never falls back to zero.** A percentage over no rows is `None` with a
reason, never `0.0`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db.models import Count, Q, Sum
from django.db.models.functions import Coalesce

from apps.metering import models
from core.pagination import order_terms
from core.tenancy import current_tenant_id

#: `BR-REP-001`'s date label. R32 serves no money column, so there is no
#: posting/clearing basis to name and none is invented; the seeded basis is
#: `EVENT · "Import date"` and `uploaded_at` is what the window is struck on.
BASIS_DATE = "event"

#: `BR-MET-032`'s three row severities. ⚠ **`warning` IS ACCEPTED** — the row
#: loaded and carries a flag. Named here once so the tile, the column and the
#: footer are struck with the same rule.
SEVERITY_OK = "ok"
SEVERITY_WARNING = "warning"
SEVERITY_ERROR = "error"
SEVERITY_ACCEPTED: tuple[str, ...] = (SEVERITY_OK, SEVERITY_WARNING)
SEVERITY_REJECTED: tuple[str, ...] = (SEVERITY_ERROR,)

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN `id`** — a cycle
#: imported by an overnight job writes many batches inside one second, so a
#: non-total order would show one batch twice and another never.
#:
#: `accepted_pct` is NOT here: it is recomputed per row in Python from two
#: annotations, and a caret over a sort this query cannot honour is a live
#: control over a dead one (hard-won law 2's mirror, `DEF-CWP-3925`). `rows`,
#: `accepted` and `rejected` ARE here, because they are SQL annotations and
#: order in SQL.
IMPORT_LOG_SORTS: tuple[str, ...] = (
    "imported_at",
    "file_name",
    "source",
    "rows",
    "accepted",
    "rejected",
    "status",
)
IMPORT_LOG_DEFAULT_SORT = "imported_at"
IMPORT_LOG_DEFAULT_DIRECTION = "desc"
IMPORT_LOG_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "imported_at": ("uploaded_at", "id"),
    "file_name": ("file_name", "uploaded_at", "id"),
    "source": ("source_kind", "source_detail", "uploaded_at", "id"),
    "rows": ("row_count", "uploaded_at", "id"),
    "accepted": ("accepted_count", "uploaded_at", "id"),
    "rejected": ("rejected_count", "uploaded_at", "id"),
    "status": ("status", "uploaded_at", "id"),
}

#: The filters this report accepts, and every one of them is applied below.
IMPORT_LOG_FILTERS: tuple[str, ...] = ("from", "to", "source", "result", "status", "cycle", "route")

#: The drawn `Result` vocabulary — what a clerk picks in the third control.
RESULT_CLEAN = "clean"
RESULT_WITH_REJECTIONS = "with_rejections"
RESULT_ALL_REJECTED = "all_rejected"
IMPORT_RESULTS: tuple[str, ...] = (RESULT_CLEAN, RESULT_WITH_REJECTIONS, RESULT_ALL_REJECTED)


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_COUNTS_BLOB_DISAGREES = {
    "code": "the_stored_counts_blob_disagrees_with_the_rows",
    "br_ref": "BR-MET-032 · BR-REP-024",
    "detail": (
        "`read_import_batches.counts` is a denormalised JSON cache whose own column comment "
        'reads "must reconcile". This report does not read it — ROWS, ACCEPTED and '
        "REJECTED are a GROUP BY over `read_import_rows`, which is the fact rather than a "
        "cache of it. The blob is COMPARED anyway, and at least one batch in this filtered "
        "set disagrees with its own rows. Both numbers travel on the row that disagrees "
        "(`counts_disagree`), because a cache that is quietly bypassed goes on being wrong "
        "while one that is bypassed and compared is a defect report."
    ),
    "wanted_reads": (),
}

GAP_ACCEPTED_PCT_OVER_NOTHING = {
    "code": "accepted_share_is_undefined_over_a_set_with_no_rows",
    "br_ref": "BR-REP-024",
    "detail": (
        "ACCEPTED % is null rather than 0.0 when the filtered set holds no file rows at "
        "all. `no import in this window had any rows` and `every row in this window was "
        "rejected` are opposite facts and 0% is only one of them; a percentage over a zero "
        "denominator is undefined and is served as such."
    ),
    "wanted_reads": (),
}

GAP_ROWS_ARE_PRUNED_WITH_THE_BATCH = {
    "code": "a_discarded_batch_may_hold_no_rows_to_count",
    "br_ref": "BR-MET-017 · BR-REP-024",
    "detail": (
        "A batch counts what its `read_import_rows` still hold. A DISCARDED batch may have "
        "had its staged rows removed, in which case ROWS, ACCEPTED and REJECTED read 0 for "
        "it — which is a true statement about what survives and NOT a statement that the "
        "file was empty. `rows_absent` marks such a batch per row so a renderer can print "
        "an em-dash rather than a confident zero (the `not applicable` / `unknown` "
        "distinction `assets_dataset` already draws)."
    ),
    "wanted_reads": (),
}


@dataclass(frozen=True)
class ReadImportLogRow:
    """One read-import batch, in the report's declared column names.

    ⚠ **`rows`, `accepted` AND `rejected` ARE AGGREGATES OVER THIS BATCH'S OWN
    ROWS**, never the `counts` blob — see the module docstring.

    ⚠ **`counts_disagree` IS A PAIR OR `None`.** When the stored blob states a
    row count and the aggregate disagrees, both numbers travel together:
    `{"stored": …, "counted": …}`. A single boolean would tell a reader that
    something is wrong and nothing about what.

    ⚠ **`rows_absent` IS NOT THE SAME AS `rows == 0`.** A discarded batch whose
    staged rows were removed holds no rows to count; a file that genuinely had
    none is a different fact. Only the first earns the em-dash.

    ⚠ **NO UUID IS A DRAWN COLUMN** (B14 rule 31). `batch_id` travels for the
    DETAIL drill-through — the drawing's *View 14 rows* — and nothing else.
    """

    batch_id: str
    batch_no: str | None
    imported_at: datetime | None
    file_name: str | None
    source_kind: str | None
    source_detail: str | None
    read_method: str | None
    cycle_code: str | None
    route_code: str | None
    service_code: str | None
    imported_by: str | None
    rows: int
    accepted: int
    rejected: int
    warnings: int
    rows_absent: bool
    counts_disagree: dict[str, int] | None
    status: str
    posted_at: datetime | None


def _tenant_id() -> Any:
    return current_tenant_id()


def _annotated() -> Any:
    """The batch queryset with its three row counts as SQL annotations.

    ⚠ **THE COUNTS ARE ANNOTATIONS AND NOT A SECOND QUERY PER ROW**, which is
    what makes `sort=rejected` a SQL `ORDER BY` rather than a Python `sorted()`
    over a materialised page. One query per row for a count is the trap
    `DEF-324` measured at 40,000 round trips and `P2.21` measured again at 56
    statements for one page of the billing register.

    `Coalesce(..., 0)` because a batch with no rows LEFT JOINs to NULL, and a
    NULL sorting between numbers would put an empty batch in an arbitrary place
    in the order.
    """
    return (
        models.ReadImportBatch.objects.filter(tenant_id=_tenant_id())
        .select_related("cycle", "route", "uploaded_by")
        .annotate(
            row_count=Coalesce(Count("readimportrow", distinct=True), 0),
            accepted_count=Coalesce(
                Count(
                    "readimportrow",
                    filter=Q(readimportrow__severity__in=SEVERITY_ACCEPTED),
                    distinct=True,
                ),
                0,
            ),
            rejected_count=Coalesce(
                Count(
                    "readimportrow",
                    filter=Q(readimportrow__severity__in=SEVERITY_REJECTED),
                    distinct=True,
                ),
                0,
            ),
            warning_count=Coalesce(
                Count(
                    "readimportrow",
                    filter=Q(readimportrow__severity=SEVERITY_WARNING),
                    distinct=True,
                ),
                0,
            ),
        )
    )


def _base(
    *,
    start: date | None = None,
    end: date | None = None,
    source: str | None = None,
    result: str | None = None,
    status: str | None = None,
    cycle: Any = None,
    route: Any = None,
) -> Any:
    """The filtered set, as a QuerySet — every criterion a `WHERE` or a `HAVING`.

    Hard rule 1: `tenant_id=_tenant_id()`, RLS FORCE underneath. No cross-tenant
    queryset is constructible from here.

    ⚠ **`result` IS A `HAVING` OVER THE ANNOTATIONS, NOT A STORED COLUMN.**
    `clean | with_rejections | all_rejected` is a statement about the rows, so
    it filters on the aggregate — which is why it is applied here, after the
    annotation, and why it is honoured rather than declared and dropped.

    ⚠ **THE WINDOW IS ON `uploaded_at`**, which is the drawn `Import date`
    basis. `posted_at` is a different date and would answer a different
    question; a batch uploaded on the 30th and posted on the 1st belongs to
    September in this report and to October in a posting-dated one, and both are
    right (the drawing makes exactly that argument about R23's two dates).
    """
    rows = _annotated()
    if start is not None:
        rows = rows.filter(uploaded_at__date__gte=start)
    if end is not None:
        rows = rows.filter(uploaded_at__date__lte=end)
    if source:
        rows = rows.filter(
            Q(source_kind__iexact=source)
            | Q(source_detail__iexact=source)
            | Q(read_method__iexact=source)
        )
    if status:
        rows = rows.filter(status__iexact=status)
    if cycle:
        rows = rows.filter(cycle_id=cycle)
    if route:
        rows = rows.filter(route_id=route)
    if result == RESULT_CLEAN:
        rows = rows.filter(rejected_count=0, row_count__gt=0)
    elif result == RESULT_WITH_REJECTIONS:
        rows = rows.filter(rejected_count__gt=0)
    elif result == RESULT_ALL_REJECTED:
        rows = rows.filter(rejected_count__gt=0, accepted_count=0)
    return rows


def _stored_row_count(batch: Any) -> int | None:
    """What the `counts` blob CLAIMS this batch holds, or None if it claims nothing.

    Read only to be COMPARED — never to be served. The blob is a cache and the
    rows are the fact; this exists so a disagreement is reported rather than
    hidden by the decision not to trust it.
    """
    blob = batch.counts
    if not isinstance(blob, dict):
        return None
    for name in ("in", "rows", "total"):
        value = blob.get(name)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def _shape(batch: Any) -> ReadImportLogRow:
    """One stored batch, in the report's declared column names. No query."""
    counted = int(getattr(batch, "row_count", 0) or 0)
    stored = _stored_row_count(batch)
    disagrees = (
        {"stored": stored, "counted": counted} if stored is not None and stored != counted else None
    )
    return ReadImportLogRow(
        batch_id=str(batch.id),
        # B14 rule 31 — the tenant's own batch number, never the uuid.
        batch_no=batch.batch_no,
        imported_at=batch.uploaded_at,
        file_name=batch.file_name,
        source_kind=batch.source_kind,
        source_detail=batch.source_detail,
        read_method=batch.read_method,
        cycle_code=getattr(batch.cycle, "code", None),
        route_code=getattr(batch.route, "code", None),
        service_code=batch.service,
        imported_by=(
            getattr(batch.uploaded_by, "full_name", None)
            or getattr(batch.uploaded_by, "email", None)
        ),
        rows=counted,
        accepted=int(getattr(batch, "accepted_count", 0) or 0),
        rejected=int(getattr(batch, "rejected_count", 0) or 0),
        warnings=int(getattr(batch, "warning_count", 0) or 0),
        # A discarded batch may have had its staged rows removed — 0 that means
        # "nothing survives to count" rather than "the file was empty".
        rows_absent=counted == 0 and batch.status == "discarded",
        counts_disagree=disagrees,
        status=batch.status,
        posted_at=batch.posted_at,
    )


def read_import_log(
    *,
    start: date | None = None,
    end: date | None = None,
    source: str | None = None,
    result: str | None = None,
    status: str | None = None,
    cycle: Any = None,
    route: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = IMPORT_LOG_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R32, ONE PAGE. One row per batch, paged and sorted in SQL.

    `per=None` is the whole filtered set. The CALLER clamps `per`; this function
    invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `read_import_log_stream()`** — no `page`, no `per`.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so the four tiles foot to the report whether a page is cut or not.
    """
    rows = _base(
        start=start,
        end=end,
        source=source,
        result=result,
        status=status,
        cycle=cycle,
        route=route,
    )

    # ⚠ ONE aggregate over the annotated set, so every tile is struck over the
    # same population the rows come from. `Sum` of the per-batch annotations is
    # the same arithmetic the drawn footer performs on the column, which is why
    # the tile and the footer cannot differ.
    aggregated = rows.aggregate(
        imports=Count("id", distinct=True),
        file_rows=Coalesce(Sum("row_count"), 0),
        accepted=Coalesce(Sum("accepted_count"), 0),
        rejected=Coalesce(Sum("rejected_count"), 0),
        warnings=Coalesce(Sum("warning_count"), 0),
    )
    imports = int(aggregated["imports"] or 0)
    file_rows = int(aggregated["file_rows"] or 0)
    accepted = int(aggregated["accepted"] or 0)
    rejected = int(aggregated["rejected"] or 0)

    problems: list[dict[str, Any]] = []
    # ⚠ NON-ADDITIVE — recomputed from its components, never averaged, and both
    # components travel beside it.
    accepted_pct = (
        None
        if not file_rows
        else (Decimal(accepted) * 100 / Decimal(file_rows)).quantize(Decimal("0.000001"))
    )
    if accepted_pct is None:
        problems.append(dict(GAP_ACCEPTED_PCT_OVER_NOTHING))

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(
            sort, direction, columns=IMPORT_LOG_SORT_COLUMNS, default=IMPORT_LOG_DEFAULT_SORT
        )
    )
    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-imports // size)) if imports else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    shaped = tuple(_shape(batch) for batch in window)
    if any(row.counts_disagree for row in shaped):
        problems.append(dict(GAP_COUNTS_BLOB_DISAGREES))
    if any(row.rows_absent for row in shaped):
        problems.append(dict(GAP_ROWS_ARE_PRUNED_WITH_THE_BATCH))

    return {
        "basis": BASIS_DATE,
        "window": {"start": start, "end": end},
        "grain": "one read-import batch",
        "rows": shaped,
        "totals": {
            # ⚠ FULLY ADDITIVE, all four. No file row belongs to two batches
            # and no batch happened in two months, so these sum across SOURCE,
            # CYCLE, ROUTE and TIME alike — which is the opposite of the
            # headcounts R36 publishes and is worth the contrast.
            "imports": imports,
            "rows": file_rows,
            "accepted": accepted,
            "rejected": rejected,
            "warnings": int(aggregated["warnings"] or 0),
            # Non-additive, published WITH its denominator.
            "accepted_pct": accepted_pct,
            "accepted_of": file_rows,
        },
        "additivity": {
            "imports": "full",
            "rows": "full",
            "accepted": "full",
            "rejected": "full",
            "warnings": "full",
            "accepted_pct": "non",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": imports,
        "problems": tuple(problems),
    }


#: A fetch buffer, not a cap (`NFR-5`).
STREAM_CHUNK = 2_000


def read_import_log_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    source: str | None = None,
    result: str | None = None,
    status: str | None = None,
    cycle: Any = None,
    route: Any = None,
    sort: str | None = None,
    direction: str = IMPORT_LOG_DEFAULT_DIRECTION,
) -> Iterator[ReadImportLogRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    The absence of those two parameters is the whole design: an export cannot
    inherit a screen's fifty rows because there is no argument through which to
    pass them.
    """
    rows = _base(
        start=start,
        end=end,
        source=source,
        result=result,
        status=status,
        cycle=cycle,
        route=route,
    ).order_by(
        *order_terms(
            sort, direction, columns=IMPORT_LOG_SORT_COLUMNS, default=IMPORT_LOG_DEFAULT_SORT
        )
    )
    for batch in rows.iterator(chunk_size=STREAM_CHUNK):
        yield _shape(batch)


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 (R32 read_import_log; 12-governance/change-requests/CR-142-BRC07-reports-framework.md §9.2 · 05-prototype/09 Reports Build Brief.pdf p064-p065 read as images per B14 rule 42 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002/024)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-JOIN
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `tests/test_rep_p6_read_import_log.py` could not import this module before it existed, and `GET /reports/read_import_log` answered the meter_reads dataset's named refusal. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (0) the eyebrow line's `jobs + meter reads` names NEITHER source — the sources are `read_import_batches` and `read_import_rows` (filed DEF-REP-6921) · (1) ROWS/ACCEPTED/REJECTED are a GROUP BY over the rows and NOT the `counts` blob, which its own column comment calls a cache that must reconcile; the blob is compared and a disagreement is reported with both numbers (coordinator ruling 2026-09-27) · (2) `warning` severity counts as ACCEPTED — the row loaded and carries a flag (BR-MET-032) · (3) `result` is a HAVING over the annotations rather than a stored column, so the drawn control is honoured rather than declared and dropped · (4) this file writes nothing and takes no savepoint — it is the report the savepoint's evidence is read from
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

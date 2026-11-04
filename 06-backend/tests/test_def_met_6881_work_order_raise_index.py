# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-6881 — `work_orders` has no index on the RAISE DATE, so
#          every page of a report dated by the raise reads and sorts all
#          40,025 rows of a top-of-ICP tenant.
# Fix:     `metering/0062_def_met_6881_work_orders_raised`
# Rules:   CLAUDE.md hard rule 1 (an index leads with `tenant_id` or it is not
#          usable under the RLS predicate every read on this table carries) ·
#          hard rule 4 (CREATE INDEX writes no row) · `NFR-3` (server
#          pagination — a page is a window over a SQL ORDER) · `NFR-5` (no
#          hard caps; an index imposes none) · hard-won law 7 (proved RED
#          through the harness that runs it, and the skip is printed rather
#          than passing vacuously).
# ───────────────────────────────────────────────────────
"""`DEF-MET-6881` — the raise date is indexed, and it was the DEFAULT sort.

WHAT THIS FILE PINS
-------------------
`apps/work/work_orders_dataset.py` declares `WORK_ORDER_DEFAULT_SORT =
"raised_on"` and maps it to `("created_at", "id")`. `work_orders` carried FOUR
indexes — `(tenant, connection)`, `(tenant, state)`, `(tenant, dispatch_state)`,
`(tenant, due_at)` — and not one of them named `created_at`. So the report that
opens by default, R33 Service Order Activity, read the whole table and sorted
it, spilling to disk on the deep pages.

The assertion is deliberately made against BOTH ends of the thing that can
drift, because they drift independently:

  * the SORT declares the columns, and
  * the INDEX covers them.

A lane that adds a seventh sort on a new date column, or that changes
`raised_on`'s tuple, goes red here by name rather than being found by a report
two scale points later. That is the shape `test_cr060_t8_dimension_indexes.py`
already uses for `journal_lines`, and it is reused rather than reinvented.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
It says NOTHING about how fast the dataset CALL is, and that restraint is the
point. The index fixes the PAGE QUERY (measured 0.0655s → 0.0034s on page 1 at
40,025 orders, real PostgreSQL 16.13); the rest of the call is the TILE
AGGREGATES, which are SQL aggregates over the whole filtered set by design and
which no index removes. A timing assertion here would be a check that goes red
on a busy machine and green on a missing index — hard-won law 7's false pass in
both directions at once. The figures live in the migration's docstring and in
the decision log, where a reader can see what was measured and on what.

PROVED RED BEFORE GREEN (hard-won law 7), through `pytest`, against the commit
before the model change:

    FAILED tests/test_def_met_6881_work_order_raise_index.py::
      test_def_met_6881__the_default_sort_is_covered_by_an_index
      AssertionError: work_orders sorts by ('created_at', 'id') by default and
      no declared index covers it. Declared: ix_work_orders_conn
      (tenant, connection), ix_work_orders_dispatch (tenant, dispatch_state),
      ix_work_orders_due (tenant, due_at), ix_work_orders_tenant_state
      (tenant, state)

    FAILED ...::test_def_met_6881__the_index_is_declared_and_leads_with_tenant
      AssertionError: ix_work_orders_raised is not declared on WorkOrder

    4 failed, 2 passed, 1 skipped

The two that PASSED on the broken tree are the two that should: the migration
file's review enrolment and the four pre-existing indexes are both true either
way. The one that SKIPPED is the live-catalogue case, vendor-gated, and it
printed its reason rather than passing over a catalogue sqlite does not have.

The live PostgreSQL case is vendor-gated and SKIPS on the default sqlite suite
rather than passing over a catalogue it cannot read. Green both ways with the
index in place: `6 passed, 1 skipped` on the default sqlite suite and
`7 passed` under `--ds=config.settings.pgtest` against a real PostgreSQL 16.13
database built from the migrations — which is the run that proves `0062` lays
the index rather than the model merely declaring it.
"""

import pytest

from apps.work.connection_models import WorkOrder
from apps.work.work_orders_dataset import (
    WORK_ORDER_DEFAULT_SORT,
    WORK_ORDER_SORT_COLUMNS,
)
from tests.isolation_helpers import requires_postgres

#: The index `metering/0062` lays. Named rather than derived, so a rename is a
#: visible change and not a silently smaller assertion.
INDEX_NAME = "ix_work_orders_raised"
INDEX_FIELDS = ("tenant", "created_at", "id")


def _declared() -> dict[str, tuple[str, ...]]:
    return {index.name: tuple(index.fields) for index in WorkOrder._meta.indexes}


# ── the model, on any vendor ────────────────────────────────────────────────
def test_def_met_6881__the_index_is_declared_and_leads_with_tenant():
    """Hard rule 1 — an index that does not lead with `tenant_id` is not usable
    under the RLS predicate every query on this table carries, so it would be
    an index that costs writes and answers nothing."""
    declared = _declared()
    assert INDEX_NAME in declared, f"{INDEX_NAME} is not declared on WorkOrder"
    assert declared[INDEX_NAME] == INDEX_FIELDS, (
        f"{INDEX_NAME} indexes {declared[INDEX_NAME]}, expected {INDEX_FIELDS}"
    )
    assert declared[INDEX_NAME][0] == "tenant"


def test_def_met_6881__the_default_sort_is_covered_by_an_index():
    """THE ASSERTION THAT ACTUALLY CATCHES THE NEXT ONE.

    Not *"is `ix_work_orders_raised` there"* — that is the case above — but
    *"is whatever this dataset sorts by DEFAULT covered by some declared
    index"*. Change `WORK_ORDER_DEFAULT_SORT`, or change what `raised_on` maps
    to, and this goes red without anybody having to remember that an index was
    the reason the report was quick.
    """
    wanted = ("tenant",) + WORK_ORDER_SORT_COLUMNS[WORK_ORDER_DEFAULT_SORT]
    declared = _declared()
    covered = [
        name
        for name, fields in declared.items()
        if tuple(fields[: len(wanted)]) == wanted
    ]
    printable = ", ".join(
        f"{name} ({', '.join(fields)})" for name, fields in sorted(declared.items())
    )
    assert covered, (
        f"work_orders sorts by {WORK_ORDER_SORT_COLUMNS[WORK_ORDER_DEFAULT_SORT]} "
        f"by default and no declared index covers it. Declared: {printable}"
    )


def test_def_met_6881__the_index_carries_the_sort_tiebreak():
    """`id` is in the index BECAUSE it is in the sort.

    Every tuple in `WORK_ORDER_SORT_COLUMNS` ends in a unique column — a
    bill-run-raised batch stamps a hundred orders in the same second, so
    `created_at` alone is not a total order and a page over it can show one
    order twice and another never. An index that stopped at `created_at` would
    leave the planner sorting inside every equal run.
    """
    assert WORK_ORDER_SORT_COLUMNS[WORK_ORDER_DEFAULT_SORT][-1] == "id"
    assert _declared()[INDEX_NAME][-1] == "id"


def test_def_met_6881__no_direction_is_declared_on_the_index():
    """ASCENDING ON PURPOSE, AND THIS IS WHERE A "TIDY-UP" TO `DESC` GOES RED.

    The screen's default direction is `desc` and PostgreSQL serves it from this
    index by scanning BACKWARD; the ascending toggle is the same index read
    forward. A `(created_at DESC, id DESC)` index — which is what the defect's
    probe used — serves the default and leaves the other toggle on a Seq Scan.
    Django spells a descending index column `"-created_at"`.
    """
    declared = _declared()
    assert INDEX_NAME in declared, f"{INDEX_NAME} is not declared on WorkOrder"
    for field in declared[INDEX_NAME]:
        assert not field.startswith("-"), (
            f"{INDEX_NAME} declares {field} descending. One index serves both "
            "directions only while it declares none: backward for desc, "
            "forward for asc. Both were measured at 40,025 orders."
        )


def test_def_met_6881__the_migration_is_enrolled_for_human_review():
    """Migration ordering is a 🔒 sensitive path (CLAUDE.md), so the file that
    lays this carries the marker G7 reads. Asserted here too, because a gate
    that is not run does not protect anything."""
    from pathlib import Path

    path = (
        Path(__file__).resolve().parent.parent
        / "apps/metering/migrations/0062_def_met_6881_work_orders_raised.py"
    )
    text = path.read_text(encoding="utf-8")
    assert "HUMAN-OWNED" in text
    assert "HUMAN-REVIEW-PENDING" in text
    assert INDEX_NAME in text


def test_def_met_6881__the_four_existing_indexes_are_untouched():
    """This change ADDS a fifth. A lane that "consolidated" one of the four
    while it was in here goes red rather than being found by a dispatcher."""
    declared = _declared()
    for name, fields in (
        ("ix_work_orders_conn", ("tenant", "connection")),
        ("ix_work_orders_tenant_state", ("tenant", "state")),
        ("ix_work_orders_dispatch", ("tenant", "dispatch_state")),
        ("ix_work_orders_due", ("tenant", "due_at")),
    ):
        assert declared.get(name) == fields, f"{name} moved or was dropped"


# ── live PostgreSQL: what the migration actually built ──────────────────────
@requires_postgres
@pytest.mark.django_db
@pytest.mark.isolation
def test_def_met_6881__the_index_exists_in_the_catalogue():
    """Ask PostgreSQL, not the model — a declaration in code is not the schema."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT a.attname FROM pg_index i "
            "JOIN pg_class c ON c.oid = i.indexrelid "
            "JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum, ord) ON true "
            "JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = k.attnum "
            "WHERE i.indrelid = to_regclass('work_orders') AND c.relname = %s "
            "ORDER BY k.ord",
            [INDEX_NAME],
        )
        columns = tuple(row[0] for row in cursor.fetchall())
    assert columns == ("tenant_id", "created_at", "id"), (
        f"{INDEX_NAME} indexes {columns or '(it does not exist)'} in the live "
        "catalogue, expected ('tenant_id', 'created_at', 'id')"
    )

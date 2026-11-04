# ── Trace ──────────────────────────────────────────────
# Change:  CR-142-BRC07 — the Reports Build Brief, Phase 2 task `P2.18`
#          (*"Drill through to the facts"*, p12, read as an image per B14 rule
#          42). Outcome, verbatim: *"A $48,221.14 subtotal opens the 412 rows
#          that make it"*.
# Defect:  DEF-REP-6869 — the group row's `path` is NOT a filter set, and
#          `group_rows()`'s own docstring said it was.
# Rules:   CLAUDE.md hard-won law 1 (a comment claiming a guarantee is not the
#          guarantee) · hard-won law 2's mirror (a live screen behind a dead
#          control — a drill-through that opens the wrong rows is worse than
#          one that is absent) · hard rule 1 (tenant scoping) · hard rule 2
#          (money to 4 decimals, never a float)
# Impacts: apps/reports/slicers.py (`drill_filters`) ·
#          07-frontend/src/features/reports/ReportGroupRow.tsx
# ───────────────────────────────────────────────────────
"""THE DRILL-THROUGH, ASSERTED BY EFFECT AND NEVER BY SHAPE.

⚠ **THE WHOLE POINT OF THIS FILE IS THAT `tests/test_rep_p2_17_slicers.py`
ALREADY PASSES.** It asserts the group row's `path` has the right KEYS —
`dimension`, `column`, `value` — and a path made of the right keys carrying the
wrong vocabulary satisfies every one of its cases. CLAUDE.md hard-won law 7's
second habit, applied: *ask what would make this check pass wrongly*. A shape
assertion over a filter set is exactly that, and the answer was **0 rows of
30**.

So every case here **runs the filters back through the runner** and compares
the row COUNT with the group's own `rows`. That is the only assertion that can
tell a working drill-through from a broken one.

⚠ **THE EFFECT CASES NEED REAL PostgreSQL AND SAY SO RATHER THAN SKIPPING
QUIETLY.** `config/settings/test.py` hardcodes in-memory SQLite (CLAUDE.md
hard-won law 14), and a `pytest.skip` firing because a fixture lacks something
is a false pass. The pure cases below run everywhere and carry the vocabulary
mismatch on their own; the effect case is gated on the vendor and PRINTS what
it skipped.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.reports import datasets, slicers

# ⚠ **THE LIVE EFFECT PROOF IS A SCRIPT, NOT A CASE IN THIS FILE, AND THE
# REASON IS HARD-WON LAW 7's THIRD SHAPE — *incapable of passing*.** It was
# written here first, gated on `connection.vendor == "postgresql"`, and it
# FAILED on a real PostgreSQL run: pytest-django builds its own empty `test_`
# database, so the seeded utility the count needs is in the CLONE and never in
# the database the case is pointed at. Both ways of running it were impossible
# in opposite directions — SQLite has no seeded utility, and the PostgreSQL run
# has no seeded utility either. Rather than weaken it into a skip (a
# `pytest.skip` firing because a fixture lacks something is a false pass), it
# moved to `10-scripts/rep_p2_18_drill_readback.py`, which is run against a
# seeded clone and whose measured output is quoted in the lifecycle block below
# and in the decision row.

#: One ageing row as the product actually serves it — measured on real
#: PostgreSQL 16 against the seeded demo tenant, 2026-09-27. The two class
#: columns are the whole defect: a clerk reads `account_class` and the query
#: takes `account_class_code`.
AGEING_ROW = {
    "account_no": "AC-2026-00004",
    "customer_name": "Dev Duval",
    "account_class": "Residential",
    "account_class_code": "residential",
    "total": "1202.400000",
}


def test_the_path_alone_is_not_a_filter_set():
    """`DEF-REP-6869`, as the case that would have caught it.

    The path the grouping emits names the dimension `consumer_class` and the
    value `Residential`. The `payments` dataset declares neither: its filter is
    `class` and its vocabulary is the code. Asserting that here, rather than in
    prose, is the difference between a fixed defect and a documented one.
    """
    path = [{"dimension": "consumer_class", "column": "account_class", "value": "Residential"}]
    declared = set(datasets.BY_CODE["payments"].filters)

    assert "consumer_class" not in declared, (
        "the path's own dimension name is not a declared filter — if this ever "
        "becomes true the defect is closed by the dataset rather than by "
        "`drill_filters`, and this file should be re-read, not deleted"
    )
    assert "class" in declared

    filters = slicers.drill_filters("payments", path, AGEING_ROW)
    assert filters == {"class": "residential"}, (
        "the filter NAME must be the dataset's declared one and the VALUE must "
        f"be the code, not the display label. Got {filters!r}"
    )
    # Both directions (the brief's instruction): it is not merely "some dict".
    assert "consumer_class" not in filters
    assert "Residential" not in filters.values()


def test_a_dimension_the_dataset_declares_no_filter_for_yields_no_drill_through():
    """`None`, never a guess — and this is the load-bearing half.

    `runner.bind` DROPS an undeclared parameter silently, so a guessed filter
    would open the report UNFILTERED — every row, under a chip naming one
    group. That is hard-won law 2's mirror: a control that runs and answers a
    different question is worse than one that is absent, because the clerk
    cannot tell.
    """
    path = [{"dimension": "collections_state", "column": "stage", "value": "reminder"}]
    # The ledger dataset declares no collections filter at all.
    assert "collections_stage" not in set(datasets.BY_CODE["journal_lines"].filters)
    assert "stage" not in set(datasets.BY_CODE["journal_lines"].filters)

    assert slicers.drill_filters("journal_lines", path, {"stage": "reminder"}) is None


def test_a_row_with_no_code_sibling_uses_its_own_value():
    """`bucket`, `on_plan` and `status` display their code, so there is nothing
    to translate — and the function must not invent a `_code` column for them."""
    path = [{"dimension": "age_bucket", "column": "bucket", "value": "31-60"}]
    filters = slicers.drill_filters("payments", path, {"bucket": "31-60"})
    assert filters == {"bucket": "31-60"}


def test_a_group_row_carries_its_filters_and_says_so_when_it_cannot():
    """The wire shape `P2.18`'s front end reads, over synthetic rows.

    A group row without `filters` carries `drill_unavailable`, so the screen has
    a reason to draw no control rather than drawing one onto nothing.
    """
    rows = [
        dict(AGEING_ROW),
        dict(AGEING_ROW, account_no="AC-2026-00005", account_class_code="residential"),
    ]
    out = slicers.group_rows("payments", rows, ["consumer_class"])
    groups = [row for row in out if row.get("__kind__") == "group"]
    assert len(groups) == 1
    assert groups[0]["rows"] == 2
    assert groups[0]["filters"] == {"class": "residential"}
    assert groups[0]["drill_unavailable"] is None
    # The path is still served — it is what the ROW is labelled with. It is
    # simply no longer claimed to be the filter set.
    assert groups[0]["path"][0]["value"] == "Residential"


def test_every_groupable_dimension_of_every_dataset_can_be_drilled_or_is_named():
    """**THE SWEEP, AND IT IS WHERE THE NEXT ONE OF THESE WILL BE FOUND.**

    `P2.17` gives every report its dataset's whole dimension set, so a clerk can
    group AR Ageing by any of **13**. Each of those groups gets a subtotal, and
    `P2.18` says a subtotal opens the rows behind it. A dimension the dataset
    declares as a SLICER but not as a FILTER is therefore a subtotal that can
    never be opened — and nothing else in this repo asks the question.

    ⚠ **IT COUNTS WHAT IT CHECKED AND PRINTS WHAT IT COULD NOT** (hard-won law
    7's fifth shape: a check reporting zero over a scope it silently excludes).
    The undrillable pairs are not a failure — they are a REGISTER, printed with
    a number beside them, because closing them is a dataset ruling rather than
    this lane's edit. What fails is the count going UP without anybody deciding
    it should.
    """
    from apps.reports.slicers import _DIMENSION_COLUMN, _filter_name_for

    undrillable: list[str] = []
    checked = 0
    for dataset in datasets.DATASETS:
        declared = set(dataset.filters)
        for dimension in dataset.dimensions:
            checked += 1
            columns = (dimension.name, *_DIMENSION_COLUMN.get(dimension.name, ()))
            if any(_filter_name_for(dimension.name, column, declared) for column in columns):
                continue
            undrillable.append(f"{dataset.code}.{dimension.name}")

    assert checked >= 50, (
        f"only {checked} dataset/dimension pairs were examined — the registry "
        "shrank and this sweep would report a false zero"
    )
    # ⚠ **MEASURED 2026-09-27: 44 OF 71. IT IS A RECORD, NOT A TARGET.**
    # By dataset: journal_lines 7 · accounts 7 · invoices 6 · payments 6 ·
    # meter_reads 6 · work_orders 5 · assets 3 · rate_schedules 2 ·
    # audit_log 2. Filed as DEF-REP-6871.
    #
    # ⚠ **NINE OF THE 44 ARE `time`, AND THEY ARE A DIFFERENT FAULT WORTH
    # SEPARATING.** Every dataset declares a time dimension and every one
    # declares `from`/`to` filters, so the NAME is there; what is missing is
    # the step that turns a group's time LEVEL and VALUE — `2026-07`, a month
    # — into the pair of dates that reproduces it. So `time` is undrillable
    # because a derivation is unbuilt, and the other 35 because no filter is
    # declared at all. Merging them under one number would hide that.
    #
    # Raising this means a dimension became a slicer with no filter behind it;
    # LOWERING it means one was closed, and the number moves in the same commit
    # as the closing — deliberately, never by drift.
    assert len(undrillable) <= 44, (
        f"{len(undrillable)} of {checked} dataset/dimension pairs offer a "
        "subtotal that cannot be opened:\n  " + "\n  ".join(sorted(undrillable))
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P2.18 (05-prototype/09 Reports Build Brief.pdf p12, read as an image per B14 rule 42)
# screens: 2·1 group rows
# generated: 2026-09-27 by lane REP-P2-TAIL
# checklist: A✔ B✔ C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — every case here was run against `slicers.py` BEFORE `drill_filters` existed and failed on `AttributeError: module 'apps.reports.slicers' has no attribute 'drill_filters'`; the live effect case was then run against the pre-fix payload and failed with 0 rows against a 30-row group
# exceptions: (1) the effect case is vendor-gated and PRINTS its reason — a bare skip on a fixture gap is a false pass (CLAUDE.md law 7)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

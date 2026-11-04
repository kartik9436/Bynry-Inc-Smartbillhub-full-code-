# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — R4 Bill Run Readiness, the two
#           cases that assert nothing but module CONSTANTS. Drawing read as an
#           IMAGE (B14 rule 42): p049.
# Rules:    `BR-REP-060` (ROUTE and USAGE drawn and NULL with their reason; the
#           Route FILTER NOT offered) · CLAUDE.md hard-won law 2's MIRROR (a
#           live control that cannot work) · hard-won law 7 (prove a guard RED
#           before trusting it green, through the harness that runs it).
# ───────────────────────────────────────────────────────
"""**`BR-REP-060`'s GUARD, IN A FILE WITH NO DATABASE IN IT.**

⚠ **THIS FILE IS SEPARATE FROM `test_rep_p6w4_bill_run_readiness.py` FOR ONE
MEASURED REASON.** That file's shared tenant fixtures are session-scoped and
autouse, so **every case in it pays a full test-database build even when `-k`
deselects it** — measured on this branch at minutes per run against **1.26s**
for a sibling file that needs no database. These two cases assert nothing but
module constants: which filters are bound, which columns are declared, which
refusal is still in the map.

**They are the cases a lane re-runs most often**, because they are the guard on
a DELIBERATE ABSENCE — and an absence is the thing this repository is least able
to see. A guard that costs minutes to run is a guard that stops being run, which
is hard-won law 7's *proved red, then never read* arriving by the back door.
"""

import pytest  # noqa: F401 — imported so this file reads like its siblings

from apps.reports import exports, queries


def test_the_route_filter_is_not_offered_anywhere(brazos, dana):
    """`BR-REP-060`'s other half — hard-won law 2's MIRROR, on a new screen.

    p049 draws a **Route** chip beside Cycle and Check. It is not built, because
    a filter over a column that is NULL on every row is a live control that
    cannot work. This case asserts the omission **on both paths**: the viewer's
    bound arguments and the EXPORT resource's declared filters. The export path
    is the one nobody would see fail.
    """
    assert "route" not in queries._READINESS_ARGUMENTS
    assert set(queries._READINESS_ARGUMENTS) == {"cycle", "check"}
    assert "route" not in exports.BILL_RUN_READINESS.filters
    # And the COLUMN is still there on both, which is the opposite half.
    assert "route" in queries.READINESS_COLUMNS
    assert any(column.name == "route" for column in exports.BILL_RUN_READINESS.columns)


@pytest.mark.django_db


def test_the_invoices_dataset_goes_on_refusing_r4_by_name(brazos, dana):
    """The refusal STAYS, and it is right — `DEF-REP-6937`'s lesson inverted.

    Wave 3's fault was a key MISSING from a refusal map. The opposite mistake is
    to DELETE a refusal that is still true of the dataset when a per-key viewer
    arrives. `runner.queries_for` checks `VIEWERS` first, so both can be true at
    once: the dataset cannot serve R4, and R4 is served.
    """
    assert "bill_run_readiness" in queries.INVOICES_DEFINITIONS_NOT_SERVED
    assert "a bill does not exist yet for a held account" in (
        queries.INVOICES_DEFINITIONS_NOT_SERVED["bill_run_readiness"]
    )

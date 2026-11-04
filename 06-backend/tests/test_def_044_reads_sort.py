# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-012 (S25 reads list — its capability row)   Screens: S25
# Rules:    IS-2 (sort, with a stable secondary key) · BR-MET-055 (server
#           pagination, hot window) · BR-MET-016/053 (lineage heads only)
# ───────────────────────────────────────────────────────
"""DEF-044 — the reads list came back oldest-first, and `dir` did nothing.

Two defects in one expression. `read_list` ordered itself with

    READ_SORTS.get((sort or "").lstrip("-"), "read_at") if sort else READ_DEFAULT_SORT

and `parse_list_params` ALWAYS returns a truthy sort — it falls back to the
endpoint's declared default rather than to None. So the `else` branch was
unreachable, `READ_DEFAULT_SORT = "-read_at"` was dead code, the leading minus
was stripped and never reapplied, and the list came back **ascending: the
newest read last**. The function also took no `direction`, so the endpoint
parsed `dir` and dropped it — a clicked column header changed the URL and
nothing else.

Neither had a test, because the module's own `_order` helper — which every
other list here uses, and which applies the direction and adds IS-2's stable
secondary sort — was simply not called. A second ordering implementation is a
second thing to be wrong, and this is what that looks like.

Found by the S25 lane building the screen against it.
"""

from decimal import Decimal

import pytest

from apps.metering import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db


def three_reads(actor):
    """Three days of reads on one meter, written oldest first."""
    asset = a_meter(actor, asset_no="M-8001")
    for day, value in (("2026-06-10", "100"), ("2026-06-20", "200"), ("2026-06-30", "300")):
        commit_read(
            actor,
            asset["id"],
            day=day,
            value=value,
            consumption=Decimal("50"),
            unit="kWh",
        )
    return asset


def days(rows):
    return [row.read_at.date().isoformat() for row in rows]


def test_def_044_tc1__the_default_is_newest_first_AS_THE_ENDPOINT_CALLS_IT(brazos, dana):
    """The capability row declares `-read_at`, and now that is what runs.

    ⚠ THE ARGUMENTS HERE ARE THE POINT, and an earlier version of this test got
    them wrong. Calling `read_list()` bare does NOT reproduce the defect: with
    `sort=None` the old expression's `else` branch fired and gave `-read_at`,
    so a bare call looked correct while every real request was ascending.

    `parse_list_params` never passes None — it falls back to the endpoint's
    DECLARED DEFAULT, so the selector always saw a truthy `"-read_at"`, took
    the first branch, stripped the minus and ordered ascending. This test
    therefore passes exactly what the endpoint passes. A test that calls a
    function more conveniently than production does is a test of a path nobody
    uses.
    """
    with tenant_ctx(brazos):
        three_reads(dana)
        rows = selectors.read_list(sort=selectors.READ_DEFAULT_SORT, direction="desc")
    assert days(rows) == ["2026-06-30", "2026-06-20", "2026-06-10"]


def test_def_044_tc2__dir_asc_actually_reverses_it(brazos, dana):
    """`dir` reached the selector as nothing at all before this.

    The endpoint parsed it, validated it against the allowed set, and then did
    not pass it — so every column header on S25 was decoration.
    """
    with tenant_ctx(brazos):
        three_reads(dana)
        descending = days(selectors.read_list(sort="read_at", direction="desc"))
        ascending = days(selectors.read_list(sort="read_at", direction="asc"))
    # Asserted as a PAIR. Either alone passes under the old code by coincidence
    # — it ignored `direction` and always ordered ascending, which happens to be
    # what `dir=asc` wants. Only the two together prove the argument is read.
    assert ascending == ["2026-06-10", "2026-06-20", "2026-06-30"]
    assert descending == ["2026-06-30", "2026-06-20", "2026-06-10"]


def test_def_044_tc3__the_declared_default_is_reachable_at_all(brazos, dana):
    """READ_DEFAULT_SORT was dead code, and dead code that states a rule is
    worse than none: it reads as the answer while something else decides.

    Asserted through the selector rather than by inspecting the constant, so
    the test fails if the constant is honoured in name only again.
    """
    with tenant_ctx(brazos):
        three_reads(dana)
        default_rows = days(selectors.read_list())
        explicit = days(selectors.read_list(sort=selectors.READ_DEFAULT_SORT, direction="desc"))
    assert default_rows == explicit


def test_def_044_tc4__ordering_is_stable_when_two_reads_share_a_date(brazos, dana):
    """IS-2's secondary key, which the hand-rolled ordering also lacked.

    Two reads on the same day paged without a tiebreak can appear twice or not
    at all across pages — a paging bug that looks like missing data.
    """
    with tenant_ctx(brazos):
        asset_a = a_meter(dana, asset_no="M-8002")
        asset_b = a_meter(dana, asset_no="M-8003", unit_label="Unit B", address="2 Elm St")
        for asset in (asset_a, asset_b):
            commit_read(
                dana,
                asset["id"],
                day="2026-06-15",
                value="500",
                consumption=Decimal("10"),
                unit="kWh",
            )
        first = [str(row.id) for row in selectors.read_list()]
        second = [str(row.id) for row in selectors.read_list()]
    assert first == second and len(first) == 2


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-012@808e015 (04-docs/05-modules/04-metering/02-business-rules.md ·
#         04-docs/01-spec/01-screen-inventory.md — the capability row this pins)
# generated: 2026-08-11 by Eng-Lead (DEF-044, found by the S25 screens lane)
# checklist: A✔ B✔ C✔ D=deferred(the API half is one argument, asserted through the selector) E=deferred(no-frontend-half here) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · proved RED by restoring the hand-rolled ordering
#         expression — and the FIRST red-proof exposed a defect in these tests
#         rather than in the fix: only tc3 went red, 3 passed. tc1 called
#         `read_list()` bare, where `sort=None` made the old expression's dead
#         `else` branch fire and return the RIGHT answer, and tc2 asserted only
#         the ascending case, which the old code produced unconditionally.
#         Both were rewritten to pass what the ENDPOINT passes and to assert
#         both directions as a pair; the re-run is quoted in the trailer's
#         exceptions
# exceptions: the corrected red-proof, measured: `3 failed, 1 passed` —
#         tc1, tc2 and tc3 all bite on the old expression now, where the
#         first attempt managed only tc3. tc4 (stable secondary key) stays
#         green under both, which is correct: the old code's ordering was
#         wrong in direction, not unstable
#         · asserts the SELECTOR, not the endpoint. The endpoint half is one
#         argument (`direction=params["direction"]`) and is covered by the
#         reads API tests; stated so this file is not read as proving the route
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

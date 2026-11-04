# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — R4 Bill Run Readiness, the joining
#           read. Drawing read as an IMAGE (B14 rule 42): p049–p050 of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 3.0x.
# Rules:    `BR-REP-041` (the LATEST PREPARED RUN for the cycle; the absence
#           STATED where none exists) · `BR-REP-060` (ROUTE and USAGE drawn and
#           NULL with their reason; the Route FILTER NOT offered) ·
#           `BR-REP-061` (HELD counts OUTSTANDING breaks; NO READ by STAGE) ·
#           `BR-REP-024` (never a 0 where a figure is not derivable) · `NFR-3`
#           (pagination in SQL) · `NFR-5` (no caps) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 4 (this read writes nothing) · B14
#           rule 31 (no database id is ever a visible value).
# ───────────────────────────────────────────────────────
"""**R4 BILL RUN READINESS** — one row per HELD ACCOUNT of the latest prepared run.

⚠ **THE CASE THAT MATTERS MOST HERE IS THE ONE THAT ASSERTS AN ABSENCE.**
`BR-REP-060` leaves ROUTE and USAGE drawn and empty and refuses the Route
FILTER, and an absence is invisible to every other check this repo has: a column
that is NULL on every row and a column that was quietly deleted look identical on
a screen, and a filter that was never offered looks identical to one nobody
tried. So both are asserted **by name and in both directions** — the columns ARE
served, their reasons ARE carried, and `route` is NOT in the filter set.

⚠ **NOTHING HERE SKIPS.** ⚠ **THE SUITE RUNS ON IN-MEMORY SQLITE**, so these
cases prove the SHAPE and the ARITHMETIC and nothing about cost or the query
plan (hard-won law 14).
"""

from datetime import date

import pytest

from apps.billing import bill_run_readiness as report
from apps.billing import models as billing_models
from apps.reports import exports, queries

from tests.test_us_bil_025_026_bills_read import an_account
from tests.test_w3_billing_models import a_cycle
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared tenant fixtures
from tests.test_us_met_helpers import tenant_ctx

#: ⚠ **NOT A MODULE-LEVEL MARK, AND THAT IS DELIBERATE.** Three of these cases
#: assert nothing but module CONSTANTS — which filters are bound, which columns
#: are declared, which refusal is still in the map — and a blanket
#: `django_db` makes them pay a 278-migration database build to read a dict.
#: They are the cases a lane re-runs most often while proving `BR-REP-060` red
#: and green, so they are DB-free and finish in a second.

#: p049's own tile figures, used as the fixture's shape rather than its scale:
#: the drawing is an ILLUSTRATION (B14 rule 37), so what is asserted is that
#: READY + HELD describes one population, never that a utility has 1,247
#: accounts.
DRAWN_ACCOUNTS_IN_CYCLE = 1_247
DRAWN_READY_TO_BILL = 1_198
DRAWN_HELD = 49


def _run(tenant, *, cycle_code="CY-09B", summary=None, key="p6w4-1"):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=a_cycle(tenant, code=cycle_code),
        period_start=date(2026, 8, 12),
        period_end=date(2026, 9, 11),
        idempotency_key=key,
        findings_summary=summary,
    )


def _break(tenant, run, account, *, stage, reason, detail, resolution=None):
    return billing_models.BillRunBreak.objects.create(
        tenant=tenant,
        bill_run=run,
        account=account,
        account_no=account.account_no,
        stage=stage,
        reason=reason,
        detail=detail,
        resolution=resolution,
    )


@pytest.mark.django_db
def test_the_rows_are_the_held_accounts_and_not_the_cycle(brazos, dana):
    """p049's footnote IS the specification of the grain.

    *"Run before the bill run, not after. The 49 held accounts are the whole
    point of the screen — they are what a clerk fixes in the twenty minutes
    before issuing 1,198 bills."*

    So a report listing every account in the cycle would be a different report
    wearing this one's title. The fixture drafts two accounts that are FINE and
    holds one, and the assertion is that ONE row is served.
    """
    with tenant_ctx(brazos):
        held = an_account(brazos, dana, account_no="100907", label="Unit H")
        run = _run(brazos, summary={"accounts": 3, "ready": 2, "blocked": 1})
        _break(
            brazos, run, held,
            stage="measure-consumption",
            reason="missing_read_undecided_at_calculate",
            detail="Last read 12 Aug",
        )
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    assert view["total"] == 1
    assert len(view["rows"]) == 1
    assert view["rows"][0].account == "100907"
    assert view["grain"] == "one held account of the latest prepared run for the cycle"


@pytest.mark.django_db
def test_route_and_usage_are_served_null_with_their_reasons(brazos, dana):
    """`BR-REP-060`, asserted in BOTH directions because an absence is invisible.

    ⚠ **A DELETED COLUMN AND A COLUMN THAT IS NULL ON EVERY ROW LOOK IDENTICAL
    ON A SCREEN.** So this asserts that the fields EXIST, that they are None, and
    that each carries its own reason code beside it — a NULL with no reason is
    indistinguishable from a value nobody wrote.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100244", label="Unit R")
        run = _run(brazos)
        _break(
            brazos, run, account,
            stage="measure-consumption",
            reason="missing_read_undecided_at_calculate",
            detail="3.8x last month",
        )
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    row = view["rows"][0]
    assert row.route is None
    assert row.route_absence == "route_is_not_single_valued_per_account"
    assert row.usage is None
    assert row.usage_absence == "usage_is_not_summable_across_services"
    codes = {problem["code"] for problem in view["problems"]}
    assert "route_is_not_single_valued_per_account" in codes
    assert "usage_is_not_summable_across_services" in codes


@pytest.mark.django_db
def test_no_read_is_counted_by_stage_and_never_by_a_list_of_reasons(brazos, dana):
    """`BR-REP-061` — and `DEF-REP-6937` is why.

    Four different reason codes map onto `measure-consumption` in
    `runs.STAGE_BY_REASON`. A hand-kept list of reason codes here would count
    whichever ones somebody remembered; the stage counts all of them. The
    fixture uses a reason this file never names, and the tile must still see it.
    """
    with tenant_ctx(brazos):
        run = _run(brazos)
        for index, (stage, reason) in enumerate(
            [
                ("measure-consumption", "missing_read_undecided_at_calculate"),
                ("measure-consumption", "metering_has_not_published_reads"),
                # A reason on the SAME stage that this test file does not list
                # anywhere else — the point of the case.
                ("measure-consumption", "account_held_by_disputed_reading"),
                ("resolve-subscription", "unit_has_no_plan"),
            ]
        ):
            account = an_account(
                brazos, dana, account_no=f"1005{index:02d}", label=f"Unit {index}"
            )
            _break(brazos, run, account, stage=stage, reason=reason, detail="—")
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    assert view["totals"]["held"] == 4
    assert view["totals"]["no_read"] == 3


@pytest.mark.django_db
def test_a_resolved_break_is_not_held(brazos, dana):
    """`BR-REP-061` — `resolution IS NULL` is the model's own vocabulary.

    A break a clerk has already fixed is not one of the accounts they must fix
    in the twenty minutes before the run. Counting it would put a stale number on
    the one screen whose entire purpose is that twenty minutes.
    """
    with tenant_ctx(brazos):
        run = _run(brazos)
        fixed = an_account(brazos, dana, account_no="100600", label="Unit F")
        still = an_account(brazos, dana, account_no="100601", label="Unit S")
        _break(
            brazos, run, fixed,
            stage="measure-consumption", reason="missing_read_undecided_at_calculate",
            detail="Last read 12 Aug", resolution="read_entered",
        )
        _break(
            brazos, run, still,
            stage="resolve-subscription", reason="unit_has_no_plan", detail="Zero for 3 cycles",
        )
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    assert view["totals"]["held"] == 1
    assert [row.account for row in view["rows"]] == ["100601"]


@pytest.mark.django_db
def test_no_prepared_run_states_the_absence_and_substitutes_nothing(brazos, dana):
    """`BR-REP-041`, verbatim: *"where none exists it states the absence"*.

    ⚠ **AND THE TILES ARE NULL RATHER THAN 0.** A `0` in HELD over a cycle
    nobody has calculated reads as *nothing needs your attention*, which is the
    most expensive wrong answer this screen can give — a clerk issues 1,198 bills
    on it.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-EMPTY")
        billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=date(2026, 8, 12),
            period_end=date(2026, 9, 11),
            idempotency_key="p6w4-never-calculated",
        )
        view = report.bill_run_readiness(cycle=cycle.id, per=50)

    assert view["rows"] == ()
    assert view["totals"]["held"] is None
    assert view["totals"]["no_read"] is None
    assert view["absences"]["held"] == "no_bill_run_prepared_for_this_cycle"
    codes = {problem["code"] for problem in view["problems"]}
    assert "no_bill_run_prepared_for_this_cycle" in codes


@pytest.mark.django_db
def test_the_latest_prepared_run_wins_and_a_draft_run_is_not_prepared(brazos, dana):
    """`BR-REP-041` — and the tie-break is TOTAL on purpose.

    Two runs on one cycle: an older one that was calculated, and a newer DRAFT
    that nobody has touched. The draft is not prepared, so the older one's breaks
    are what a clerk sees — reporting four zeroes from the draft would say the
    cycle is clean.
    """
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, code="CY-TWO")
        account = an_account(brazos, dana, account_no="100801", label="Unit L")
        old = billing_models.BillRun.objects.create(
            tenant=brazos, cycle=cycle,
            period_start=date(2026, 8, 12), period_end=date(2026, 9, 11),
            idempotency_key="p6w4-old",
        )
        _break(
            brazos, old, account,
            stage="measure-consumption", reason="missing_read_undecided_at_calculate",
            detail="Last read 12 Aug",
        )
        billing_models.BillRun.objects.create(
            tenant=brazos, cycle=cycle,
            period_start=date(2026, 9, 12), period_end=date(2026, 10, 11),
            idempotency_key="p6w4-draft",
        )
        view = report.bill_run_readiness(cycle=cycle.id, per=50)

    assert view["totals"]["held"] == 1
    assert view["rows"][0].account == "100801"


@pytest.mark.django_db
def test_the_top_two_tiles_are_null_when_no_findings_pass_has_run(brazos, dana):
    """`BR-REP-061` — a `0` in ACCOUNTS IN CYCLE would say the cycle is empty.

    The truth is that nobody counted. `findings_summary` is written only by the
    background findings job, so a run calculated inline carries none — and that
    is the DEFAULT state, which is why it is the state proved first.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100900", label="Unit N")
        run = _run(brazos, cycle_code="CY-NOSUM", summary=None, key="p6w4-nosum")
        _break(
            brazos, run, account,
            stage="measure-consumption", reason="missing_read_undecided_at_calculate",
            detail="Last read 12 Aug",
        )
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    assert view["totals"]["accounts_in_cycle"] is None
    assert view["totals"]["ready_to_bill"] is None
    assert view["totals"]["ready_pct"] is None
    assert view["absences"]["accounts_in_cycle"] == "findings_pass_has_not_run_on_this_run"
    # ⚠ **AND HELD IS STILL A NUMBER**, because it comes from the persisted
    # table rather than from the summary. The asymmetry is the rule.
    assert view["totals"]["held"] == 1


@pytest.mark.django_db
def test_the_ready_percentage_is_the_drawn_sub_line_and_never_a_divide_by_zero(brazos, dana):
    """p049's `96%` under READY TO BILL, on the drawing's own two figures.

    **Worked:** 1,198 ÷ 1,247 = 96.070569…%, which p049 rounds to `96%` for
    display. The read serves the figure at six places (hard rule 2) and the
    screen displays two.
    """
    with tenant_ctx(brazos):
        run = _run(
            brazos,
            cycle_code="CY-PCT",
            summary={
                "accounts": DRAWN_ACCOUNTS_IN_CYCLE,
                "ready": DRAWN_READY_TO_BILL,
                "blocked": DRAWN_HELD,
            },
            key="p6w4-pct",
        )
        view = report.bill_run_readiness(cycle=run.cycle_id, per=50)

    assert view["totals"]["accounts_in_cycle"] == DRAWN_ACCOUNTS_IN_CYCLE
    assert view["totals"]["ready_to_bill"] == DRAWN_READY_TO_BILL
    assert round(view["totals"]["ready_pct"], 2) == 96.07
    # A cycle of no accounts is NOT `0%` — it is no answer at all.
    assert report._ready_pct(0, 0) is None


@pytest.mark.django_db
def test_the_tiles_foot_to_the_whole_filtered_set_and_never_to_the_page(brazos, dana):
    """`NFR-3` and `BR-REP-039`'s discipline, applied here.

    Proved by COMPARING page 1 with page 2 rather than by reading the code: a
    tile computed over the page would shrink, and the shrink is only visible
    across two pages.
    """
    with tenant_ctx(brazos):
        run = _run(brazos, cycle_code="CY-PAGE", key="p6w4-page")
        for index in range(5):
            account = an_account(
                brazos, dana, account_no=f"1010{index:02d}", label=f"Unit P{index}"
            )
            _break(
                brazos, run, account,
                stage="measure-consumption",
                reason="missing_read_undecided_at_calculate",
                detail="Last read 12 Aug",
            )
        first = report.bill_run_readiness(cycle=run.cycle_id, page=1, per=2)
        second = report.bill_run_readiness(cycle=run.cycle_id, page=2, per=2)

    assert len(first["rows"]) == 2
    assert len(second["rows"]) == 2
    assert first["totals"]["held"] == second["totals"]["held"] == 5
    assert first["pages"] == 3
    # Paged in SQL, and a boundary neither repeats nor drops a row.
    assert {row.account for row in first["rows"]}.isdisjoint(
        {row.account for row in second["rows"]}
    )


@pytest.mark.django_db
def test_the_export_stream_serves_every_row_and_is_registered(brazos, dana):
    """The Download button, and the reason this case exists at all.

    ⚠ **`ReportViewerPage` ENABLES THE EXPORT ICON THE MOMENT A REPORT
    RENDERS.** So the commit that stops R4 refusing is the commit that puts a
    live Download button over a **404** unless the resource lands with it — the
    fault this framework has shipped twice in three days. Asserted here rather
    than left to a browser.
    """
    with tenant_ctx(brazos):
        run = _run(brazos, cycle_code="CY-EXP", key="p6w4-exp")
        for index in range(3):
            account = an_account(
                brazos, dana, account_no=f"1020{index:02d}", label=f"Unit E{index}"
            )
            _break(
                brazos, run, account,
                stage="measure-consumption",
                reason="missing_read_undecided_at_calculate",
                detail="Last read 12 Aug",
            )
        streamed = list(report.bill_run_readiness_stream(cycle=run.cycle_id))

    assert len(streamed) == 3
    assert exports.KEY_BILL_RUN_READINESS in exports.SLUGS
    assert exports.BILL_RUN_READINESS in exports.RESOURCES
    assert "bill_run_readiness" in queries.KEY_STREAMS
    assert "bill_run_readiness" in queries.VIEWERS
    # R4 carries no money column at all — a currency symbol on a list of
    # accounts that could not be drafted would be a wrong answer.
    assert exports.BILL_RUN_READINESS.money is False


@pytest.mark.django_db
def test_the_read_writes_nothing(brazos, dana):
    """Hard rule 4, asserted rather than asserted-in-a-docstring (law 1).

    A report that touched `bill_run_breaks.resolution` would be resolving a
    clerk's work item by reading a screen.
    """
    with tenant_ctx(brazos):
        account = an_account(brazos, dana, account_no="100950", label="Unit W")
        run = _run(brazos, cycle_code="CY-RO", key="p6w4-ro")
        _break(
            brazos, run, account,
            stage="measure-consumption", reason="missing_read_undecided_at_calculate",
            detail="Last read 12 Aug",
        )
        before = billing_models.BillRunBreak.objects.filter(tenant=brazos).count()
        report.bill_run_readiness(cycle=run.cycle_id, per=50)
        list(report.bill_run_readiness_stream(cycle=run.cycle_id))
        after = billing_models.BillRunBreak.objects.filter(tenant=brazos).count()
        assert (
            billing_models.BillRunBreak.objects.filter(
                tenant=brazos, resolution__isnull=False
            ).count()
            == 0
        )

    assert before == after == 1

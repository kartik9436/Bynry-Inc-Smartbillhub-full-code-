# ── Trace ──────────────────────────────────────────────
# Plan:     04-docs/05-modules/07-billing/15-bulk-bill-run-build-plan.md
#           T1 (each Scope refusal and warning; continuity; bill date before
#           period end; run-number warning; counts; last-run counts) · T3 (the
#           two routes: mounting, all-at-once, pagination, tenant isolation)
# Rulings:  14-bulk-bill-run-changes.md row 43 (PO 2026-09-30 — THE list)
# Code:     apps/billing/run_scope.py · apps/billing/run_scope_api.py
# Defects:  DEF-BIL-8160 (continuity from one page of runs) · DEF-BIL-5297
# ───────────────────────────────────────────────────────
"""The bulk bill run's Scope step: one test per refusal and per warning on row 43.

RED FIRST. This file was run against the tip before `run_scope.py` existed and
every case failed on `ImportError` / a 404 — honest "not built" reds. The four
guards that matter most were then each broken ON PURPOSE in the finished code
and the matching case watched go red; the quoted failures are in the lane's
report and in the decision-log row of 2026-09-30 (bulk bill run Scope lane):

  * continuity read from the first 50 runs      → `test_continuity_*_over_60_runs`
  * the abandoned-run exclusion removed          → `test_an_abandoned_run_is_ignored`
  * the bill-date-before-period-end check removed→ its own case
  * the run-number series check removed          → its own case

NO FIGURE HERE IS TAKEN FROM THE DRAWING (B14 rule 37). Dates are this file's
own, and every count is derived from the world each test builds.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.billing import run_scope, run_scope_api
from apps.billing import api as billing_api
from apps.metering import models as metering_models
from core import errors, idempotency

from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    lonestar,
    make_premises,
    make_unit,
    staff_actor,
    tenant_ctx,
)
from tests.test_us_ten_helpers import (  # noqa: F401
    brazosbend_payload,
    lonestarridge_payload,
    provisioned_tenant,
)

pytestmark = pytest.mark.django_db

JUNE = (date(2026, 6, 1), date(2026, 6, 30))
JULY = (date(2026, 7, 1), date(2026, 7, 31))
BILL_DATE = date(2026, 7, 1)


# ══════════════════════════════════════════════════════════════════════════
# The world
# ══════════════════════════════════════════════════════════════════════════
def a_cycle(tenant, code="SC-A", *, bill_day=1, due_days=21, frequency="Monthly"):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        bill_day=bill_day,
        due_days=due_days,
        start_day=1,
        days_to_complete=5,
        frequency=frequency,
        first_run_date=date(2025, 1, 1),
    )


def a_published_template():
    from apps.billing import templates_service

    template = templates_service.tenant_fallback_template()
    if template is None or templates_service.published_version(template) is None:
        templates_service.seed_platform_default(on_date=date(2026, 1, 1))
        template = templates_service.tenant_fallback_template()
    assert templates_service.published_version(template) is not None
    return template


def a_second_published_template(actor):
    from apps.billing import templates_service

    template = templates_service.create_template(
        name="Riverside insert", template_type="bill", category=None, actor=actor
    )
    version = templates_service.save_draft(
        template, layout_key=templates_service.SEED_LAYOUT_KEY, actor=actor
    )
    templates_service.publish(version, actor=actor, on_date=date(2026, 1, 1))
    return template


def a_draft_template(actor):
    from apps.billing import templates_service

    template = templates_service.create_template(
        name="Winter insert", template_type="bill", category=None, actor=actor
    )
    templates_service.save_draft(template, layout_key=templates_service.SEED_LAYOUT_KEY, actor=actor)
    return template


def a_run(tenant, cycle, start, end, *, status="issued", template=None, label=None, run_no=None):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=start,
        period_end=end,
        status=status,
        label=label,
        run_no=run_no,
        template=template,
        idempotency_key=idempotency.bill_run_key(
            cycle_id=cycle.id, period_start=start, period_end=end
        ),
    )


def check(cycle, template, **over):
    values = dict(
        cycle_id=str(cycle.id),
        period_start=JULY[0].isoformat(),
        period_end=JULY[1].isoformat(),
        bill_date="2026-08-01",
        due_days=None,
        template_id=str(template.pk),
        label="July 2026 · Riverside",
        with_counts=False,
    )
    values.update(over)
    return run_scope.check_scope(**values)


def refusal(result, code):
    found = [p for p in result.refusals if p.code == code]
    assert found, f"{code} not refused; refusals were {[p.code for p in result.refusals]}"
    return found[0]


def warning(result, code):
    found = [p for p in result.warnings if p.code == code]
    assert found, f"{code} not warned; warnings were {[p.code for p in result.warnings]}"
    return found[0]


def a_june_run_behind(tenant, cycle):
    """Most cases need a previous run so `first_run` does not join in."""
    return a_run(tenant, cycle, *JUNE, label="June 2026 · Riverside", run_no="RUN-0001")


# ══════════════════════════════════════════════════════════════════════════
# Every key on the list resolves, and the list is the ruling's
# ══════════════════════════════════════════════════════════════════════════
def test_every_problem_has_its_own_key_and_every_key_is_in_the_catalogue():
    from core import refusal_catalogue

    keys = [entry[1] for entry in run_scope.PROBLEMS.values()] + [run_scope.REFUSED_SUMMARY_KEY]
    assert len(set(keys)) == len(keys), "two problems share one sentence"
    missing = [key for key in keys if not refusal_catalogue.resolves(key)]
    assert missing == []


def test_the_run_number_series_is_a_warning_not_a_refusal():
    """Decided 2026-09-30: the drawing had it as a refusal and is corrected."""
    assert run_scope.PROBLEMS["no_run_number_series"][0] == run_scope.WARNING


# ══════════════════════════════════════════════════════════════════════════
# Refusals — one each
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-19 (every refusal and warning named, on its field, all at once) · BULK-CHG-43 (the ruled list,
# one case each below) · BULK-CHG-16 (cycle and date checks) · BULK-CHG-27 (plan T1, T3)
def test_all_problems_come_back_at_once_each_on_its_field(brazos, dana):
    """The drawing's *Problems* state: five mistakes, five sentences, one pass."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, bill_day=None)
        draft = a_draft_template(dana)
        result = check(
            cycle,
            draft,
            label="",
            period_start="2026-08-30",
            period_end="2026-08-20",
            bill_date="",
            due_days="-3",
        )
    by_field = {p.field: p.code for p in result.refusals}
    assert by_field == {
        "label": "label_missing",
        "period_end": "period_order",
        "bill_date": "bill_date_needed",
        "due_days": "due_days_invalid",
        "template_id": "template_unpublished",
    }
    assert not result.ok


def test_refusal_not_allowed(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template(), can_run=False)
    assert refusal(result, "not_allowed").field is None


def test_refusal_run_name_missing(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        result = check(cycle, a_published_template(), label="   ")
    assert refusal(result, "label_missing").field == "label"


def test_refusal_cycle_missing(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), cycle_id="")
    assert refusal(result, "cycle_missing").field == "cycle_id"


def test_refusal_cycle_not_this_utilitys_is_one_answer(brazos, lonestar):
    """HR-1: unknown, malformed and another tenant's cycle read the same."""
    with tenant_ctx(lonestar):
        theirs = a_cycle(lonestar, code="LS-A")
    with tenant_ctx(brazos):
        template = a_published_template()
        mine = a_cycle(brazos)
        answers = [
            [p.as_dict() for p in check(mine, template, cycle_id=value).refusals]
            for value in (str(theirs.id), str(uuid.uuid4()), "not-a-uuid")
        ]
    assert answers[0] == answers[1] == answers[2]
    assert [p["code"] for p in answers[0]] == ["cycle_unknown"]


@pytest.mark.parametrize(
    "field_name, value, code",
    [
        ("period_start", "", "period_start_missing"),
        ("period_start", "30/06/2026", "period_start_invalid"),
        ("period_end", "", "period_end_missing"),
        ("period_end", "June", "period_end_invalid"),
    ],
)
def test_refusal_period_missing_or_not_a_date(brazos, field_name, value, code):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), **{field_name: value})
    assert refusal(result, code).field == field_name


def test_refusal_period_ends_before_it_starts(brazos):
    with tenant_ctx(brazos):
        result = check(
            a_cycle(brazos), a_published_template(), period_start="2026-07-31", period_end="2026-07-01"
        )
    assert refusal(result, "period_order").field == "period_end"


def test_refusal_overlap_names_and_links_the_run(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        june = a_june_run_behind(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_start="2026-06-15", period_end="2026-07-14"
        )
    problem = refusal(result, "period_overlap")
    assert problem.field == "period_start"
    assert problem.params["run_id"] == str(june.pk)
    assert problem.params["runNo"] == "RUN-0001"
    assert problem.params["label"] == "June 2026 · Riverside"
    assert (problem.params["from"], problem.params["to"]) == ("2026-06-15", "2026-06-30")
    assert result.continuity["state"] == "overlap"


def test_refusal_same_cycle_and_period_says_who_when_and_links(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        run = a_run(brazos, cycle, *JULY)
        billing_models.BillRun.objects.filter(pk=run.pk).update(run_by_id=dana.id)
        result = check(cycle, a_published_template())
    codes = [p.code for p in result.refusals]
    assert any(code.startswith("duplicate_run") for code in codes)
    problem = next(p for p in result.refusals if p.code.startswith("duplicate_run"))
    assert problem.params["run_id"] == str(run.pk)
    assert problem.params["ran_by"] == str(dana.id)
    assert problem.params["ranAt"].startswith("20")
    # The duplicate is not ALSO reported as an overlap with itself.
    assert "period_overlap" not in codes


def test_refusal_bill_date_missing_and_the_cycle_has_no_bill_day(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos, bill_day=None), a_published_template(), bill_date=None)
    assert refusal(result, "bill_date_needed").field == "bill_date"


def test_a_missing_bill_date_is_fine_when_the_cycle_has_a_bill_day(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template(), bill_date=None)
    assert result.ok, [p.code for p in result.refusals]


def test_refusal_bill_date_is_not_a_date(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), bill_date="tomorrow")
    assert refusal(result, "bill_date_invalid").field == "bill_date"


def test_refusal_bill_date_before_the_period_ends(brazos):
    """New on 2026-09-30. Period ends 31 Jul; a bill dated 30 Jul is refused,
    and 31 Jul itself is not."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        template = a_published_template()
        early = check(cycle, template, bill_date="2026-07-30")
        same_day = check(cycle, template, bill_date="2026-07-31")
    problem = refusal(early, "bill_date_before_period_end")
    assert problem.field == "bill_date"
    assert problem.params == {"periodEnd": "2026-07-31"}
    assert "bill_date_before_period_end" not in [p.code for p in same_day.refusals]


@pytest.mark.parametrize("value", ["-3", "2.5", "abc", True])
def test_refusal_days_to_pay_not_a_whole_number_zero_or_more(brazos, value):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), due_days=value)
    assert refusal(result, "due_days_invalid").field == "due_days"


def test_zero_days_to_pay_is_lawful(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template(), due_days=0)
    assert "due_days_invalid" not in [p.code for p in result.refusals]


def test_refusal_template_missing(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), template_id="")
    assert refusal(result, "template_missing").field == "template_id"


def test_refusal_template_not_this_utilitys_is_one_answer(brazos, lonestar):
    with tenant_ctx(lonestar):
        theirs = a_published_template()
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        mine = a_published_template()
        answers = [
            [p.as_dict() for p in check(cycle, mine, template_id=value).refusals]
            for value in (str(theirs.pk), str(uuid.uuid4()), "nope")
        ]
    assert answers[0] == answers[1] == answers[2]
    assert [p["code"] for p in answers[0]] == ["template_unknown"]


def test_refusal_template_not_published(brazos, dana):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_draft_template(dana))
    assert refusal(result, "template_unpublished").field == "template_id"


def test_refusal_cycle_has_no_units(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template(), with_counts=True)
    assert refusal(result, "cycle_no_units").field == "cycle_id"
    assert result.counts["units_in_cycle"] == 0


def test_refusal_cycle_has_no_accounts_to_bill(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_billed_unit(dana, brazos, cycle, a_priced_plan(brazos), asset_no="M-8801", label="Unit A")
        result = check(cycle, a_published_template(), with_counts=True)
    assert refusal(result, "cycle_no_accounts").field == "cycle_id"
    assert result.counts["units_in_cycle"] == 1
    assert result.counts["accounts_to_bill"] == 0


def test_refusal_meter_reads_not_answering_names_it_and_keeps_going(brazos, monkeypatch):
    """A failing seam is contained in its own savepoint and NAMED; the rest of
    the pass still runs (the template check after it still answers)."""
    from apps.metering import selectors as metering_selectors

    def broken(*_args, **_kwargs):
        raise RuntimeError("metering is down")

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        template = a_published_template()
        monkeypatch.setattr(metering_selectors, "units_in_cycle", broken)
        result = check(cycle, template, with_counts=True, label="")
    assert refusal(result, "meter_reads_not_answering").field is None
    assert refusal(result, "label_missing")
    assert result.counts["units_in_cycle"] is None


def _a_failing_statement(*_args, **_kwargs):
    """A seam that fails the way a real one does on PostgreSQL: a statement
    the database refuses, which ABORTS the surrounding transaction there."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM a_table_that_does_not_exist_bulk_scope")


def test_law_14_a_seam_that_fails_in_the_database_does_not_poison_the_pass(
    brazos, dana, monkeypatch
):
    """⚠ HARD-WON LAW 14. Written to be run on PostgreSQL 16 as well as SQLite
    (`--ds=config.settings.pgtest`): a failed statement there aborts the whole
    transaction, so without `run_scope._ask`'s SAVEPOINT every query AFTER the
    failing seam — the run-number series, the counts, the last run's bills —
    raises `InFailedSqlTransaction`. On SQLite this passes either way, which is
    exactly why it must also be run on PostgreSQL."""
    from apps.metering import selectors as metering_selectors

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_billed_unit(dana, brazos, cycle, a_priced_plan(brazos), asset_no="M-8821", label="Unit A")
        a_june_run_behind(brazos, cycle)
        template = a_published_template()
        monkeypatch.setattr(metering_selectors, "cycle_expected_span_days", _a_failing_statement)
        survived = check(cycle, template, with_counts=True)
        monkeypatch.setattr(metering_selectors, "units_in_cycle", _a_failing_statement)
        named = check(cycle, template, with_counts=True)
        # And the connection is still usable for the caller's next statement.
        assert billing_models.BillRun.objects.filter(cycle=cycle).count() == 1
    assert survived.counts["units_in_cycle"] == 1
    assert "period_length" not in [p.code for p in survived.warnings]
    assert refusal(named, "meter_reads_not_answering").field is None
    assert named.previous_run is not None


def test_refusal_customers_not_answering_names_it(brazos, dana, monkeypatch):
    from apps.customers import selectors as customer_selectors

    def broken(*_args, **_kwargs):
        raise RuntimeError("customers is down")

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_billed_unit(dana, brazos, cycle, a_priced_plan(brazos), asset_no="M-8811", label="Unit A")
        monkeypatch.setattr(customer_selectors, "accounts_for_bill_run", broken)
        result = check(cycle, a_published_template(), with_counts=True)
    assert refusal(result, "customers_not_answering").field is None
    # A module that did not answer leaves its figures NULL, never zero.
    assert result.counts["accounts_to_bill"] is None
    assert "cycle_no_accounts" not in [p.code for p in result.refusals]


# ══════════════════════════════════════════════════════════════════════════
# Warnings — one each; none of them blocks
# ══════════════════════════════════════════════════════════════════════════
def test_warning_gap_since_the_last_run(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_start="2026-07-10", period_end="2026-08-09",
            bill_date="2026-08-10",
        )
    problem = warning(result, "period_gap")
    assert problem.params == {"from": "2026-07-01", "to": "2026-07-09", "days": 9}
    assert result.continuity["state"] == "gap"
    assert result.ok, "a gap warns and never refuses (row 35: no tick)"


def test_warning_period_length_not_the_cycles_frequency(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template(), period_end="2026-08-14", bill_date="2026-09-01")
    problem = warning(result, "period_length")
    assert problem.field == "period_end"
    assert problem.params["days"] == 45
    assert problem.params["expected"] == 31
    assert result.ok


def test_no_period_length_warning_for_a_whole_month(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template())
    assert "period_length" not in [p.code for p in result.warnings]


def test_warning_period_ends_after_today(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_run(brazos, cycle, date(2031, 5, 1), date(2031, 5, 31))
        result = check(
            cycle, a_published_template(), period_start="2031-06-01", period_end="2031-06-30",
            bill_date="2031-07-01",
        )
    assert warning(result, "period_after_today").field == "period_end"
    assert result.ok


def test_warning_bill_date_not_the_cycles_bill_day(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, bill_day=1)
        a_june_run_behind(brazos, cycle)
        template = a_published_template()
        off = check(cycle, template, bill_date="2026-08-20")
        on = check(cycle, template, bill_date="2026-08-01")
    assert warning(off, "bill_day_differs").params == {"billDay": 1}
    assert "bill_day_differs" not in [p.code for p in on.warnings]


def test_the_bill_day_clamps_to_a_short_month(brazos):
    """OQ-339: a cycle billing on the 31st bills 28 Feb in a common year."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, bill_day=31)
        a_run(brazos, cycle, date(2027, 1, 1), date(2027, 1, 1))
        result = check(
            cycle, a_published_template(), period_start="2027-01-02", period_end="2027-01-31",
            bill_date="2027-02-28",
        )
    assert "bill_day_differs" not in [p.code for p in result.warnings]


def test_warning_days_to_pay_changed_from_the_cycles(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, due_days=21)
        a_june_run_behind(brazos, cycle)
        template = a_published_template()
        changed = check(cycle, template, due_days="30")
        same = check(cycle, template, due_days="21")
        blank = check(cycle, template, due_days="")
    assert warning(changed, "due_days_changed").params == {"cycleDays": 21}
    assert "due_days_changed" not in [p.code for p in same.warnings]
    assert "due_days_changed" not in [p.code for p in blank.warnings]


def test_warning_template_not_the_cycles_usual(brazos, dana):
    """*Usual* = the template the cycle's previous run was pinned to."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        usual = a_published_template()
        other = a_second_published_template(dana)
        a_run(brazos, cycle, *JUNE, template=usual)
        changed = check(cycle, other)
        kept = check(cycle, usual)
    assert warning(changed, "template_not_usual").field == "template_id"
    assert "template_not_usual" not in [p.code for p in kept.warnings]


def test_warning_no_run_number_series(brazos):
    """The run is numbered when the series is set up — a WARNING (2026-09-30)."""
    from apps.tenancy import models as tenancy_models
    from core import numbering

    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        template = a_published_template()
        before = check(cycle, template)
        tenancy_models.NumberSeries.objects.filter(tenant=brazos, series=numbering.BILL_RUN).delete()
        after = check(cycle, template)
    assert "no_run_number_series" not in [p.code for p in before.warnings]
    assert warning(after, "no_run_number_series").field is None
    assert after.ok


def test_warning_first_run_for_this_cycle(brazos):
    with tenant_ctx(brazos):
        result = check(a_cycle(brazos), a_published_template())
    assert warning(result, "first_run")
    assert result.continuity == {"state": "first"}
    assert result.previous_run is None
    assert result.last_run_counts is None


# ══════════════════════════════════════════════════════════════════════════
# Continuity against the REAL last run (B2 · DEF-BIL-8160)
# ══════════════════════════════════════════════════════════════════════════
def sixty_monthly_runs(tenant, cycle):
    """Jan 2021 → Dec 2025, one run a month, oldest created first."""
    runs = []
    for index in range(60):
        year, month = 2021 + index // 12, 1 + index % 12
        start = date(year, month, 1)
        end = (date(year + (month == 12), month % 12 + 1, 1)) - timedelta(days=1)
        runs.append(a_run(tenant, cycle, start, end, run_no=f"RUN-{index + 1:04d}"))
    return runs


# BULK-CHG-17 (continuity against the cycle's real last run; overlap refuses, gap warns with no tick)
def test_continuity_is_judged_against_the_newest_of_60_runs(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        runs = sixty_monthly_runs(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_start="2026-01-01", period_end="2026-01-31",
            bill_date="2026-02-01",
        )
    assert result.continuity["state"] == "continuous"
    assert result.previous_run["run_id"] == str(runs[-1].pk)
    assert result.previous_run["run_no"] == "RUN-0060"
    assert result.ok


def test_continuity_gap_over_60_runs(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        sixty_monthly_runs(brazos, cycle)
        result = check(
            cycle, a_published_template(), period_start="2026-03-01", period_end="2026-03-31",
            bill_date="2026-04-01",
        )
    assert warning(result, "period_gap").params == {
        "from": "2026-01-01",
        "to": "2026-02-28",
        "days": 59,
    }


def test_an_abandoned_run_is_ignored(brazos):
    """*"cancelled drafts ignored"*: a run over 1–15 Jan 2026 that was abandoned
    neither overlaps January nor counts as the last run."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        runs = sixty_monthly_runs(brazos, cycle)
        a_run(brazos, cycle, date(2026, 1, 1), date(2026, 1, 15), status="abandoned")
        a_run(brazos, cycle, date(2026, 1, 16), date(2026, 1, 20), status="cancelled")
        template = a_published_template()
        january = check(
            cycle, template, period_start="2026-01-01", period_end="2026-01-31",
            bill_date="2026-02-01",
        )
        february = check(
            cycle, template, period_start="2026-02-01", period_end="2026-02-28",
            bill_date="2026-03-01",
        )
    assert "period_overlap" not in [p.code for p in january.refusals]
    assert january.continuity["state"] == "continuous"
    assert january.previous_run["run_id"] == str(runs[-1].pk)
    assert warning(february, "period_gap").params["from"] == "2026-01-01"


def test_a_catch_up_run_is_not_a_period_of_its_own(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        june = a_june_run_behind(brazos, cycle)
        billing_models.BillRun.objects.create(
            tenant=brazos,
            cycle=cycle,
            period_start=JUNE[0],
            period_end=JUNE[1],
            parent_run=june,
            idempotency_key=idempotency.catch_up_run_key(
                parent_key=june.idempotency_key, account_ids=[uuid.uuid4()]
            ),
        )
        result = check(cycle, a_published_template())
    assert result.previous_run["run_id"] == str(june.pk)


# ══════════════════════════════════════════════════════════════════════════
# This run covers (B5) and the last run's three figures (row 30)
# ══════════════════════════════════════════════════════════════════════════
def counted_world(tenant, actor):
    """Four units on one cycle:

      A — metered, a regular account          → billed
      B — metered, an account made MASTER     → billed
      C — metered, NO account                 → nobody to bill
      D — electric service point, NO meter, a regular account → missing meter
    """
    from apps.customers import models as customer_models

    cycle = a_cycle(tenant)
    plan = a_priced_plan(tenant)
    unit_a = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9101", label="Unit A")
    unit_b = a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9102", label="Unit B")
    a_billed_unit(actor, tenant, cycle, plan, asset_no="M-9103", label="Unit C")
    premises = make_premises(actor, address_line="9104 Bluestem Ln")
    unit_d = make_unit(actor, premises["id"], label="Unit D", services=["electric"])
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit_d["id"]).update(
        cycle=cycle
    )
    account_a = an_account(tenant, unit_a["id"], "A-9101")
    account_b = an_account(tenant, unit_b["id"], "A-9102")
    customer_models.Account.objects.filter(pk=account_b.pk).update(kind="master")
    account_d = an_account(tenant, unit_d["id"], "A-9104")
    return cycle, (account_a, account_b, account_d)


# BULK-CHG-15 (the summary counts) · BULK-CHG-18 (a vacant unit with nobody to bill is a warning only)
def test_the_scope_counts(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        result = check(cycle, a_published_template(), with_counts=True)
    assert result.counts == {
        "units_in_cycle": 4,
        "accounts_to_bill": 3,
        "regular_accounts": 2,
        "master_accounts": 1,
        "meters": 3,
        "sub_meters": 0,
        "behind_the_meter": 0,
        "missing_meter": 1,
        "units_nobody_to_bill": 1,
    }
    assert warning(result, "units_nobody_to_bill").params == {"count": 1}
    assert warning(result, "services_no_meter").params == {"count": 1}
    assert result.ok, [p.code for p in result.refusals]


def an_invoice(tenant, account, run, number, status):
    return billing_models.Invoice.objects.create(
        tenant=tenant,
        account=account,
        bill_run=run,
        invoice_no=number,
        bill_type="cycle",
        status=status,
        service_date=JUNE[1],
        period_start=JUNE[0],
        period_end=JUNE[1],
        due_date=date(2026, 7, 22),
        issued_at=datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc),
        subtotal=Decimal("10.00"),
        tax_total=Decimal("0.00"),
        total=Decimal("10.00"),
        currency="USD",
        template_version=1,
        payload_version=1,
        bill_payload={},
    )


# BULK-CHG-30 (a last-run figure only where the previous run's sent bills prove it)
def test_the_last_runs_three_account_counts_come_from_its_sent_bills(brazos, dana):
    """Two accounts on June's SENT bills (one regular, one master) and a third
    whose bill is still a draft: the last run proves 2 · 1 · 1."""
    with tenant_ctx(brazos):
        cycle, (account_a, account_b, account_d) = counted_world(brazos, dana)
        june = a_june_run_behind(brazos, cycle)
        an_invoice(brazos, account_a, june, "BL-9101", billing_models.INVOICE_ISSUED)
        an_invoice(brazos, account_b, june, "BL-9102", billing_models.INVOICE_ISSUED)
        an_invoice(
            brazos, account_d, june, "BL-9104", billing_models.INVOICE_DRAFT
        )
        result = check(cycle, a_published_template())
    assert result.last_run_counts == {
        "run_id": str(june.pk),
        "accounts_to_bill": 2,
        "regular_accounts": 1,
        "master_accounts": 1,
    }


def test_a_last_run_that_sent_nothing_proves_no_count(brazos):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        a_june_run_behind(brazos, cycle)
        result = check(cycle, a_published_template())
    assert result.last_run_counts is None


# ══════════════════════════════════════════════════════════════════════════
# The routes (A1 · A2 · T3)
# ══════════════════════════════════════════════════════════════════════════
def test_the_preview_route_is_mounted_ahead_of_the_run_item_route(brazos):
    from django.urls import resolve

    assert (
        resolve("/api/brazosbend/billing/runs/scope-preview").func is run_scope_api.scope_preview
    )
    assert resolve("/api/brazosbend/billing/runs").func is billing_api.bill_runs


def an_actor_user(tenant, role="billing_clerk"):
    actor = staff_actor(tenant, role, f"{role}@scope.test")
    return FakeUser(user_id=actor.id)


def post_run(tenant, user, body, role="billing_clerk"):
    return api_call(billing_api.bill_runs, "post", user=user, role=role, tenant=tenant, data=body)


def preview(tenant, query, role="billing_clerk"):
    return api_call(
        run_scope_api.scope_preview, "get", user=FakeUser(), role=role, tenant=tenant, query=query
    )


def test_post_answers_every_refusal_at_once_and_writes_nothing(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos, bill_day=None)
        draft = a_draft_template(dana)
        user = an_actor_user(brazos)
    response = post_run(
        brazos,
        user,
        {
            "cycle_id": str(cycle.id),
            "label": "",
            "period_start": "2026-08-30",
            "period_end": "2026-08-20",
            "due_days": -3,
            "template_id": str(draft.pk),
        },
    )
    assert response.status_code == 422
    assert response.data["code"] == errors.BIZ_COMPLETENESS
    assert response.data["message_key"] == "billing.runScope.refused"
    # The five typed-field mistakes, AND the cycle-wide one the POST also
    # counts: this bare cycle has no units. Six sentences from one press.
    assert response.data["params"]["count"] == 6
    assert {(item["field"], item["reason"]) for item in response.data["field_errors"]} == {
        ("cycle_id", "cycle_no_units"),
        ("label", "label_missing"),
        ("period_end", "period_order"),
        ("bill_date", "bill_date_needed"),
        ("due_days", "due_days_invalid"),
        ("template_id", "template_unpublished"),
    }
    with tenant_ctx(brazos):
        assert billing_models.BillRun.objects.count() == 0


def test_post_creates_a_whole_cycle_run_with_name_and_template_and_returns_warnings(brazos, dana):
    """B3: a stale `scope_services` is IGNORED, and the key has no services term."""
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        template = a_published_template()
        user = an_actor_user(brazos)
    response = post_run(
        brazos,
        user,
        {
            "cycle_id": str(cycle.id),
            "label": "July 2026 · Riverside",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "bill_date": "2026-08-01",
            "template_id": str(template.pk),
            "scope_services": ["electric"],
        },
    )
    assert response.status_code == 201, response.data
    assert set(response.data) == {"id", "job_id", "status", "warnings"}
    assert {item["code"] for item in response.data["warnings"]} == {
        "first_run",
        "units_nobody_to_bill",
        "services_no_meter",
    }
    with tenant_ctx(brazos):
        run = billing_models.BillRun.objects.get(pk=response.data["id"])
    assert run.label == "July 2026 · Riverside"
    assert run.template_id == template.pk
    assert run.scope_services is None
    assert run.idempotency_key == f"{cycle.id}|2026-07-01|2026-07-31"


def test_post_duplicate_keeps_its_envelope_and_lists_the_rest(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        template = a_published_template()
        user = an_actor_user(brazos)
    body = {
        "cycle_id": str(cycle.id),
        "label": "July 2026 · Riverside",
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "template_id": str(template.pk),
    }
    first = post_run(brazos, user, body)
    second = post_run(brazos, user, {**body, "label": ""})
    assert first.status_code == 201
    assert second.status_code == 409
    assert second.data["code"] == errors.BIZ_IDEMPOTENT
    assert second.data["message_key"] == "billing.run.duplicate"
    assert second.data["params"]["run_id"] == first.data["id"]
    assert {item["reason"] for item in second.data["field_errors"]} >= {"label_missing"}


def test_an_executive_is_told_not_allowed_on_the_preview_and_refused_at_the_post(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        template = a_published_template()
        user = an_actor_user(brazos, "executive")
    query = {
        "cycle_id": str(cycle.id),
        "label": "July",
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "template_id": str(template.pk),
    }
    seen = preview(brazos, query, role="executive")
    refused = post_run(brazos, user, query, role="executive")
    assert seen.status_code == 200
    assert "not_allowed" in [item["code"] for item in seen.data["refusals"]]
    assert seen.data["can_start"] is False
    assert refused.status_code == 403


def test_the_preview_serves_everything_and_pages_previous_runs(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        template = a_published_template()
        may = a_run(brazos, cycle, date(2026, 5, 1), date(2026, 5, 31), run_no="RUN-0000")
        june = a_june_run_behind(brazos, cycle)
        before = billing_models.BillRun.objects.count()
    response = preview(
        brazos,
        {
            "cycle_id": str(cycle.id),
            "label": "July 2026 · Riverside",
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
            "bill_date": "2026-08-01",
            "template_id": str(template.pk),
        },
    )
    assert response.status_code == 200, response.data
    body = response.data
    assert set(body) == {
        "refusals",
        "warnings",
        "can_start",
        "counts",
        "last_run_counts",
        "continuity",
        "previous_run",
        "cycle",
        "previous_runs",
    }
    assert body["can_start"] is True
    assert body["counts"]["accounts_to_bill"] == 3
    assert body["continuity"]["state"] == "continuous"
    assert body["previous_run"]["run_id"] == str(june.pk)
    assert body["cycle"]["code"] == "SC-A"
    assert body["cycle"]["frequency"] == "Monthly"
    assert body["cycle"]["bill_day"] == 1
    assert body["cycle"]["due_days"] == 21
    assert body["cycle"]["runs_so_far"] == 2
    assert body["cycle"]["first_run_date"] == "2025-01-01"
    # NFR-3's envelope, newest first.
    assert body["previous_runs"]["count"] == 2
    assert [row["id"] for row in body["previous_runs"]["results"]] == [str(june.pk), str(may.pk)]
    assert body["previous_runs"]["next"] is None
    with tenant_ctx(brazos):
        assert billing_models.BillRun.objects.count() == before, "the preview wrote a run"


def test_the_preview_never_crosses_a_tenant(brazos, lonestar):
    """Another utility's cycle reads exactly like an unknown one, and none of
    its runs, counts or details reach the answer."""
    with tenant_ctx(lonestar):
        theirs = a_cycle(lonestar, code="LS-A")
        a_run(lonestar, theirs, *JUNE, run_no="RUN-0099")
    with tenant_ctx(brazos):
        template = a_published_template()
    base = {
        "label": "July",
        "period_start": "2026-07-01",
        "period_end": "2026-07-31",
        "template_id": str(template.pk),
    }
    foreign = preview(brazos, {**base, "cycle_id": str(theirs.id)})
    unknown = preview(brazos, {**base, "cycle_id": str(uuid.uuid4())})
    assert foreign.status_code == unknown.status_code == 200
    assert foreign.data == unknown.data
    assert [item["code"] for item in foreign.data["refusals"]] == ["cycle_unknown"]
    assert foreign.data["cycle"] is None
    assert foreign.data["previous_runs"] is None


def test_an_old_shape_request_with_no_name_and_no_template_field_is_refused(brazos, dana):
    """Plan task F2 retired `BillRunWizard` and, with it, the TEMPORARY path
    that derived a run name and a template for a request that sent NEITHER
    field. An absent field is now refused exactly like an empty one — the one
    screen left always sends both — and no run row is written."""
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        a_published_template()
        user = an_actor_user(brazos)
        before = billing_models.BillRun.objects.count()
    response = post_run(
        brazos,
        user,
        {
            "cycle_id": str(cycle.id),
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "bill_date": "2026-07-01",
        },
    )
    assert response.status_code == 422, response.data
    assert {item["reason"] for item in response.data["field_errors"]} == {
        "label_missing",
        "template_missing",
    }
    codes = {item["code"] for item in response.data["params"]["warnings"]}
    assert "name_derived" not in codes and "template_derived" not in codes
    with tenant_ctx(brazos):
        assert billing_models.BillRun.objects.count() == before


def test_a_new_shape_request_that_sends_an_empty_name_and_no_template_is_refused(brazos, dana):
    """The derivation is ONLY for an absent field. The new screen SENDS the
    fields, so an empty name and a null template are refused as before."""
    with tenant_ctx(brazos):
        cycle, _accounts = counted_world(brazos, dana)
        user = an_actor_user(brazos)
    response = post_run(
        brazos,
        user,
        {
            "cycle_id": str(cycle.id),
            "label": "",
            "template_id": None,
            "period_start": "2026-06-01",
            "period_end": "2026-06-30",
            "bill_date": "2026-07-01",
        },
    )
    assert response.status_code == 422
    assert {item["reason"] for item in response.data["field_errors"]} == {
        "label_missing",
        "template_missing",
    }


# BULK-CHG-32 (the Previous runs table for the chosen cycle, newest first, paged)
def test_the_preview_pages_a_cycles_previous_runs(brazos):
    """NFR-3: 60 runs, a 50-row page (the smallest the product serves); page 2
    holds the oldest ten — nothing is capped away."""
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        runs = sixty_monthly_runs(brazos, cycle)
        template = a_published_template()
    query = {
        "cycle_id": str(cycle.id),
        "label": "January 2026",
        "period_start": "2026-01-01",
        "period_end": "2026-01-31",
        "template_id": str(template.pk),
        "per": 50,
    }
    first = preview(brazos, query)
    second = preview(brazos, {**query, "page": 2})
    assert first.data["previous_runs"]["count"] == 60
    assert len(first.data["previous_runs"]["results"]) == 50
    assert first.data["previous_runs"]["results"][0]["id"] == str(runs[-1].pk)
    assert [row["id"] for row in second.data["previous_runs"]["results"]] == [
        str(run.pk) for run in reversed(runs[:10])
    ]
    assert first.data["cycle"]["runs_so_far"] == 60

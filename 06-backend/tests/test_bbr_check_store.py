# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-037 AMENDED 2026-09-30 — TC-A1 … TC-A5, TC-8, TC-9, TC-17
# Rules:    OQ-843 re-ruled (option C: save, re-check on change) · changes rows
#           44–46 (no automatic fix; every former "auto" is a decision with a
#           suggestion; the four kinds) · BR-BIL-1040 as amended (answers per
#           tag at Check)
# Plan:     15-bulk-bill-run-build-plan.md B9, B13, B15, B17, A3–A6 · DB1 · T1, T3
# ───────────────────────────────────────────────────────
"""The Check's saved results, its automatic re-check, its decisions, its API."""

from __future__ import annotations

import time
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import (
    check_api,
    check_models,
    check_staleness,
    check_store,
    decisions,
    runs,
)
from apps.billing import selectors as billing_selectors
from apps.metering import models as metering_models
from apps.metering import selectors as metering_selectors
from apps.rating import models as rating_models

from tests.test_bbr_check_engine import (
    BILL_DATE,
    PERIOD_END,
    PERIOD_START,
    a_cycle,
    reads_without_unit,
    three_accounts,
)
from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import FakeUser, api_call, tenant_ctx
from tests.test_us_met_reads_helpers import commit_read

pytestmark = pytest.mark.django_db


def a_run(cycle):
    return runs.create_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        bill_date=BILL_DATE,
        label="June 2026 · BBR",
    )


def saved_status(run, account):
    found = check_store.account_findings(run, str(account.id))
    return found["status"], sorted(f["code"] for f in found["findings"]) if found else None


def checked_at(run, account):
    return check_models.BillRunAccountCheck.objects.get(
        bill_run=run, account_id=account.id
    ).checked_at


def service_id(code):
    from apps.tenancy import selectors as tenancy_selectors

    return tenancy_selectors.service_ids_by_code()[code]


# ══════════════════════════════════════════════════════════════════════════
# TC-A1 · OQ-843 option C — six blocked on an unpublished plan; publish; only
# those six re-check and turn ready. A reading posted re-checks only its own.
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-53
def test_tc_a1__publishing_the_plan_rechecks_exactly_the_six_accounts_on_it(brazos, dana):
    with tenant_ctx(brazos):
        cycle = a_cycle(brazos)
        published = a_priced_plan(brazos, name="Published")
        draft = a_priced_plan(brazos, name="Draft")
        on_draft, on_published = [], []
        for n in range(6):
            unit = a_billed_unit(dana, brazos, cycle, draft, asset_no=f"M-81{n:02d}", label=f"D{n}")
            on_draft.append(an_account(brazos, unit["id"], f"A-0081{n}"))
        for n in range(2):
            unit = a_billed_unit(
                dana, brazos, cycle, published, asset_no=f"M-82{n:02d}", label=f"P{n}"
            )
            on_published.append(an_account(brazos, unit["id"], f"A-0082{n}"))
        # The six units' plan goes back to DRAFT (assigned while published —
        # the worked case: a colleague is mid-edit when the Check runs).
        rating_models.RatePlan.objects.filter(pk=draft.pk).update(status="draft")
        run = a_run(cycle)
        check_store.check_run(run)

        for account in on_draft:
            status, codes = saved_status(run, account)
            assert status == "decision" and "plan_not_published" in codes
        before = {a.account_no: checked_at(run, a) for a in on_draft + on_published}
        assert check_store.counts(run)["ready"] == 2

        time.sleep(0.01)
        plan = rating_models.RatePlan.objects.get(pk=draft.pk)
        plan.status = "published"
        plan.save()  # a real publish saves the row, which is what moves `updated_at`

        started = time.perf_counter()
        swept = check_staleness.sweep(run)
        six_seconds = time.perf_counter() - started

        assert swept == {"stale": 6, "rechecked": 6, "background": False}
        for account in on_draft:
            assert saved_status(run, account)[0] == "ready"
            assert checked_at(run, account) > before[account.account_no]
        for account in on_published:
            assert checked_at(run, account) == before[account.account_no]
        assert check_store.counts(run)["ready"] == 8

        started = time.perf_counter()
        check_store.check_run(run)
        whole_seconds = time.perf_counter() - started
        # Recorded for the report (the timing is the fixture's, not a rule).
        print(
            f"\nTC-A1 timing: re-check 6 = {six_seconds:.3f}s · whole run (8) = {whole_seconds:.3f}s"
        )


# BULK-CHG-53
def test_tc_a1__a_reading_posted_rechecks_only_that_account(brazos, dana):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
        before = {no: checked_at(run, a) for no, a in accounts.items()}
        time.sleep(0.01)
        meter = (
            metering_models.MeterRead.objects.filter(
                tenant=brazos, asset__service_point__unit_id=accounts["A-00106"].unit_id
            )
            .first()
            .asset_id
        )
        commit_read(
            dana,
            meter,
            day="2026-06-29",
            value="14300",
            prior_value="14212",
            consumption="88.000000",
            unit="kWh",
        )
        swept = check_staleness.sweep(run)
        assert swept["stale"] == 1 and swept["rechecked"] == 1
        assert checked_at(run, accounts["A-00106"]) > before["A-00106"]
        assert checked_at(run, accounts["A-00101"]) == before["A-00101"]
        assert checked_at(run, accounts["A-00102"]) == before["A-00102"]


# ══════════════════════════════════════════════════════════════════════════
# TC-A3 · a reading with no unit on a kWh meter: listed with the suggestion,
# and NO bill uses it until the suggestion is accepted.
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-44 · BULK-CHG-45
def test_tc_a3__a_suggestion_is_never_billed_until_accepted(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        reads_without_unit(monkeypatch, accounts["A-00102"].unit_id, meter_unit="kWh")
        run = a_run(cycle)
        check_store.check_run(run)
        page = check_store.tag_accounts(run, "reading_has_no_unit", {})
        assert [r["account_no"] for r in page["results"]] == ["A-00102"]
        assert page["results"][0]["params"]["suggested"] == {"unit": "kWh"}
        assert page["tag"]["choices"][0] == "accept_suggestion"
        assert saved_status(run, accounts["A-00102"])[0] == "decision"

        applied = decisions.apply_decisions(billing_selectors.prepared_for(run), bill_run=run)
        assert "A-00102" not in {d.account_no for d in applied.ready}
        assert "decision_needed" in {p.reason for p in applied.decisions}

        decisions.record_decision(
            bill_run=run,
            account_id=str(accounts["A-00102"].id),
            case="reading_has_no_unit",
            choice="accept_suggestion",
            service_id=service_id("electric"),
        )
        applied = decisions.apply_decisions(billing_selectors.prepared_for(run), bill_run=run)
        ready = {d.account_no: d for d in applied.ready}
        assert ready["A-00102"].readings[0].consumption.unit == "kWh"
        assert saved_status(run, accounts["A-00102"])[0] == "ready"


# ══════════════════════════════════════════════════════════════════════════
# TC-A4 / TC-A5 · the two anchor suggestions, fed back only when answered
# ══════════════════════════════════════════════════════════════════════════
def _anchored_at(monkeypatch, closed_at, *, current=None, prior=None, multiplier="keep"):
    """Test doubles at the two anchor reads: the last issued bill closed the
    electric register at `closed_at`; the reads row may be rewritten."""
    monkeypatch.setattr(
        runs, "last_issued_window", lambda account_id: (date(2026, 5, 1), date(2026, 5, 31))
    )
    monkeypatch.setattr(
        runs,
        "billed_positions",
        lambda *a, **k: {
            "electric": runs.BilledPosition(service_code="electric", closed_at=Decimal(closed_at))
        },
    )
    real = metering_selectors.billing_reads_for_unit

    def double(unit, **kwargs):
        rows = real(unit, **kwargs)
        out = []
        for row in rows:
            row = dict(row)
            if current is not None:
                row.update(
                    current_value=Decimal(current),
                    prior_value=Decimal(prior),
                    consumption=Decimal(current) - Decimal(prior),
                )
            if multiplier != "keep":
                row["multiplier"] = multiplier
            out.append(row)
        return out

    monkeypatch.setattr(metering_selectors, "billing_reads_for_unit", double)


# BULK-CHG-45 · BULK-CHG-46
def test_tc_a4__a_rollover_the_dial_proves_suggests_170_and_accepting_prices_170(
    brazos, dana, monkeypatch
):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        from apps.assets import models as asset_models

        asset_models.Asset.objects.filter(tenant=brazos).update(register_digits=5)
        _anchored_at(monkeypatch, "99950", current="120", prior="100")
        run = a_run(cycle)
        check_store.check_run(run)
        page = check_store.tag_accounts(run, "possible_rollover", {})
        assert len(page["results"]) == 3
        assert Decimal(page["results"][0]["params"]["suggested_quantity"]) == Decimal("170")
        prepared = billing_selectors.prepared_for(run)
        assert prepared.ready == ()  # nothing billed on a suggestion

        decisions.record_decision(
            bill_run=run,
            account_id=str(accounts["A-00101"].id),
            case="possible_rollover",
            choice="accept_suggestion",
            service_id=service_id("electric"),
        )
        prepared = billing_selectors.prepared_for(run)
        [data] = prepared.ready
        assert data.account_no == "A-00101"
        assert data.readings[0].consumption.amount == Decimal("170")


# BULK-CHG-44
def test_tc_a5__no_multiplier_defaults_to_hold_and_bill_with_1_prices_x1(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        _anchored_at(monkeypatch, "13500", multiplier=None)
        run = a_run(cycle)
        check_store.check_run(run)
        summary = check_store.findings_summary(run)
        tag = next(
            t
            for c in summary["categories"]
            for t in c["tags"]
            if t["code"] == "anchor_multiplier_unstated"
        )
        assert tag["count"] == 3 and tag["default_choice"] == "hold"
        assert billing_selectors.prepared_for(run).ready == ()

        # Answer for all N — the tag's standing answer (BR-BIL-1040 amended).
        decisions.set_standing_answer(
            bill_run=run, case="anchor_multiplier_unstated", choice="bill_with_multiplier_1"
        )
        prepared = billing_selectors.prepared_for(run)
        assert len(prepared.ready) == 3
        # 14,212 − 13,500 = 712, × 1.
        assert {d.readings[0].consumption.amount for d in prepared.ready} == {Decimal("712")}


# ══════════════════════════════════════════════════════════════════════════
# B13 · a per-account answer beats the tag's; apply to a selection
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-20
def test_b13__a_per_account_override_beats_the_answer_for_all(brazos, dana, monkeypatch):
    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        _anchored_at(monkeypatch, "13500", multiplier=None)
        run = a_run(cycle)
        check_store.check_run(run)
        decisions.set_standing_answer(
            bill_run=run, case="anchor_multiplier_unstated", choice="bill_with_multiplier_1"
        )
        decisions.record_decision(
            bill_run=run,
            account_id=str(accounts["A-00106"].id),
            case="anchor_multiplier_unstated",
            choice="hold",
            service_id=service_id("electric"),
        )
        prepared = billing_selectors.prepared_for(run)
        assert sorted(d.account_no for d in prepared.ready) == ["A-00101", "A-00102"]


# ══════════════════════════════════════════════════════════════════════════
# T3 · the routes — start inline, findings, one tag, decide, re-check, 404
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-20 · BULK-CHG-36
def test_t3__the_check_routes_work_end_to_end_and_page(brazos, dana, monkeypatch):
    from tests.test_us_bil_001_003_run_api import an_actor_user

    with tenant_ctx(brazos):
        cycle, _plan, accounts = three_accounts(brazos, dana)
        _anchored_at(monkeypatch, "13500", multiplier=None)
        run = a_run(cycle)
        clerk = an_actor_user(brazos)

    started = api_call(
        check_api.run_check,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        data={"background": False},
        run_id=str(run.pk),
    )
    assert started.status_code == 200, started.data
    assert started.data["counts"]["accounts"] == 3

    found = api_call(
        check_api.run_check_findings,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        run_id=str(run.pk),
    )
    assert found.status_code == 200
    assert found.data["tiles"]["decisions"] == 3
    assert len(found.data["categories"]) == 9

    one = api_call(
        check_api.run_check_findings,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        query={"tag": "anchor_multiplier_unstated", "per": 2, "page": 9},
        run_id=str(run.pk),
    )
    # NFR-3: the page grammar (per clamps UP to the smallest size, 50; an
    # out-of-range page clamps to the last) — never an error, never unpaged.
    assert (one.data["count"], one.data["per"], one.data["page"]) == (3, 50, 1)
    assert len(one.data["results"]) == 3
    searched = api_call(
        check_api.run_check_findings,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        query={"tag": "anchor_multiplier_unstated", "q": "00106"},
        run_id=str(run.pk),
    )
    assert [r["account_no"] for r in searched.data["results"]] == ["A-00106"]

    decided = api_call(
        check_api.run_check_decide,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
        data={
            "case": "anchor_multiplier_unstated",
            "choice": "bill_with_multiplier_1",
            "scope": "accounts",
            "service_code": "electric",
            "account_ids": [str(accounts["A-00101"].id), str(accounts["A-00102"].id)],
        },
    )
    assert decided.status_code == 201 and decided.data["recorded"] == 2

    refused = api_call(
        check_api.run_check_decide,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
        data={"case": "anchor_multiplier_unstated", "choice": "invent", "scope": "all"},
    )
    assert refused.status_code == 422  # VAL-002, the catalogue's validation status

    rechecked = api_call(
        check_api.run_check_recheck,
        "post",
        user=clerk,
        role="billing_clerk",
        tenant=brazos,
        run_id=str(run.pk),
        data={"account_ids": [str(accounts["A-00101"].id)]},
    )
    assert rechecked.status_code == 200 and rechecked.data["rechecked"] == 1

    ready = api_call(
        check_api.run_check_findings,
        "get",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        query={"list": "ready"},
        run_id=str(run.pk),
    )
    assert sorted(r["account_no"] for r in ready.data["results"]) == ["A-00101", "A-00102"]

    viewer = api_call(
        check_api.run_check_recheck,
        "post",
        user=FakeUser(),
        role="executive",
        tenant=brazos,
        run_id=str(run.pk),
        data={"account_ids": []},
    )
    assert viewer.status_code == 403


@pytest.mark.isolation
def test_t3__another_tenants_run_is_absent(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        check_store.check_run(run)
    answer = api_call(
        check_api.run_check_findings,
        "get",
        user=FakeUser(),
        role="billing_clerk",
        tenant=lonestar,
        run_id=str(run.pk),
    )
    assert answer.status_code == 404


# ══════════════════════════════════════════════════════════════════════════
# B17 · the Check as a background job with progress (G140: no role needed)
# ══════════════════════════════════════════════════════════════════════════
# BULK-CHG-25 · BULK-CHG-53
def test_b17__the_check_job_saves_every_account_and_reports_progress(brazos, dana):
    from apps.billing import run_jobs
    from core import jobs as core_jobs

    with tenant_ctx(brazos):
        cycle, _plan, _accounts = three_accounts(brazos, dana)
        run = a_run(cycle)
        record = run_jobs.enqueue_check(run, actor_user_id=None)
    # B28 — the Check job is the COORDINATOR of its batches of 500; with the
    # transport eager its one batch runs in-process the moment it is dispatched
    # (tests/test_b28_parallel_check_batches.py plays the workers by hand).
    from django.test import override_settings

    with override_settings(JOBS_EAGER=True):
        core_jobs.run_job(record["id"], run_jobs.run_check_job)
    with tenant_ctx(brazos):
        after = core_jobs.current(record["id"])
        assert after["status"] == core_jobs.SUCCEEDED
        assert after["progress"] == {"done": 3, "total": 3}
        run.refresh_from_db()
        assert run.findings_summary["accounts"] == 3
        assert check_models.BillRunAccountCheck.objects.filter(bill_run=run).count() == 3

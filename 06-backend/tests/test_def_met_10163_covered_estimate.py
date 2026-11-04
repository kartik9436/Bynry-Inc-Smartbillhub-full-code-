# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-10163 (high, wrong-logic) — a bill-run estimate dated
#           BETWEEN two actual readings, where the later actual already existed,
#           was counted in the monthly usage AND again inside the later actual.
# Ruling:   PO 2026-10-15, verbatim "go with 1 and 3" — decision log
#           "AN ESTIMATE BEHIND A LATER ACTUAL READING IS NOT COUNTED TWICE".
# Fix:      apps/metering/monthly_usage.covered_estimate_ids (the judgment) ·
#           monthly_usage_service._fact_rows (both grains) ·
#           metering/selectors._later_actual_covering + billing/runs
#           .covered_by_later_read + decisions._apply_to_account (the bill run).
# ───────────────────────────────────────────────────────
"""The PO's worked case, AC-2026-00049 electric, on the local sample data:

    09/24  actual   3,976 → 5,176   1,200 kWh
    09/30  estimate (bill run)        560 kWh
    10/06  actual   5,176 → 6,376   1,200 kWh, measured FROM 09/24

September showed **1,760** (1,200 + 560) and must show **1,200**; October stays
1,200. The estimate row is never edited or deleted (hard rule 4).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from django.test import override_settings

from apps.metering import models as metering_models
from apps.metering import monthly_usage as usage_rules
from apps.metering import monthly_usage_service as usage_service

from tests.test_br_met_106_monthly_usage import _account_on, _heads, _meter
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SEP = date(2026, 9, 1)
OCT = date(2026, 10, 1)


def _at(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=timezone.utc)


def _actual(tenant, account_id, asset_id, *, day, prior, value, prior_day, channel="total",
            trues_up=None, consumption=None):
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=_at(day),
        channel=channel,
        period_start=prior_day,
        period_end=day,
        prior_value=Decimal(prior),
        current_value=Decimal(value),
        consumption=(
            Decimal(consumption) if consumption is not None else Decimal(value) - Decimal(prior)
        ),
        unit="kWh",
        source="manual",
        status="ok",
        lifecycle="committed",
        days_since_prior=(day - prior_day).days,
        trues_up_read_ids=trues_up,
    )


def _estimate(tenant, account_id, asset_id, *, day, consumption, prior_day, channel="total"):
    """A bill-run estimate exactly as `record_billed_estimate` writes one."""
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=_at(day),
        channel=channel,
        period_start=prior_day,
        period_end=day,
        current_value=None,
        consumption=Decimal(consumption),
        unit="kWh",
        source="estimated",
        source_detail="billing_estimate:00000000-0000-0000-0000-000000000000",
        status="estimated",
        lifecycle="billed",
        estimation_method="clerk_decision",
    )


def _month(account_id, month):
    return next(h for h in _heads(account_id) if h.period_month == month)


def _worked_case(tenant, actor, asset_no):
    account, unit = _account_on(actor, tenant)
    meter = _meter(actor, unit["id"], asset_no=asset_no)
    aid, mid = account["id"], meter["id"]
    _actual(tenant, aid, mid, day=date(2026, 8, 25), prior="2776", value="3976",
            prior_day=date(2026, 7, 27))
    sep_actual = _actual(tenant, aid, mid, day=date(2026, 9, 24), prior="3976", value="5176",
                         prior_day=date(2026, 8, 25))
    account["unit_id"] = unit["id"]
    return account, meter, sep_actual


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE WORKED CASE — September 1,760 → 1,200, October stays 1,200
# ══════════════════════════════════════════════════════════════════════════
def test_def_met_10163__the_worked_case_september_1760_becomes_1200(brazos, marcus):
    with tenant_ctx(brazos):
        account, meter, sep_actual = _worked_case(brazos, marcus, "E-10163")
        oct_actual = _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                             prior="5176", value="6376", prior_day=date(2026, 9, 24))
        # The bill run's estimate arrives AFTER the October actual (the 42 of 45).
        estimate = _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                             consumption="560", prior_day=date(2026, 9, 24))

        usage_service.recompute_account(account["id"], actor=marcus)
        september = _month(account["id"], SEP)
        october = _month(account["id"], OCT)
        print(f"\nPROOF DEF-MET-10163: September {september.quantity} kWh, "
              f"October {october.quantity} kWh")
        assert september.quantity == Decimal("1200.000000")
        assert september.estimated_read_count == 0
        assert [str(i) for i in september.source_read_ids] == [str(sep_actual.id)]
        assert october.quantity == Decimal("1200.000000")
        assert [str(i) for i in october.source_read_ids] == [str(oct_actual.id)]

        # Hard rule 4: the estimate row is untouched.
        estimate.refresh_from_db()
        assert (estimate.consumption, estimate.status, estimate.superseded_by_id) == (
            Decimal("560.000000"), "estimated", None,
        )


def test_def_met_10163__the_meter_grain_drops_the_same_estimate(brazos, marcus):
    """OQ-421's constraint: one construction for both grains."""
    from apps.metering.monthly_usage_asset import AssetMonthlyUsage

    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10164")
        _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                prior="5176", value="6376", prior_day=date(2026, 9, 24))
        _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                  consumption="560", prior_day=date(2026, 9, 24))
        usage_service.recompute_account(account["id"], actor=marcus)
        row = AssetMonthlyUsage.objects.get(
            asset_id=meter["id"], channel="total", period_month=SEP,
            superseded_by_id__isnull=True, superseded_at__isnull=True,
        )
        assert row.quantity == Decimal("1200.000000")


# ══════════════════════════════════════════════════════════════════════════
# 2 · WHAT DOES NOT MOVE
# ══════════════════════════════════════════════════════════════════════════
def test_def_met_10163__an_estimate_with_no_later_actual_still_counts(brazos, marcus):
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10165")
        _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                  consumption="560", prior_day=date(2026, 9, 24))
        usage_service.recompute_account(account["id"], actor=marcus)
        september = _month(account["id"], SEP)
        assert september.quantity == Decimal("1760.000000")
        assert september.estimated_read_count == 1


def test_def_met_10163__an_estimate_the_actual_trued_up_still_counts(brazos, marcus):
    """BR-MET-029: the estimate on file BEFORE the actual — the actual is net of
    it and names it, so the two together are the register difference."""
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10166")
        estimate = _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                             consumption="560", prior_day=date(2026, 9, 24))
        trued = _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                        prior="5176", value="6376", prior_day=date(2026, 9, 24),
                        trues_up=[str(estimate.id)], consumption="640")
        assert trued.consumption == Decimal("640")  # 6,376 − 5,176 − 560, net of it
        usage_service.recompute_account(account["id"], actor=marcus)
        assert _month(account["id"], SEP).quantity == Decimal("1760.000000")
        assert _month(account["id"], OCT).quantity == Decimal("640.000000")


def test_def_met_10163__a_later_actual_on_another_meter_or_register_covers_nothing(
    brazos, marcus
):
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10167")
        other = _meter(marcus, account["unit_id"], asset_no="E-10168")
        _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                  consumption="560", prior_day=date(2026, 9, 24))
        # The SAME meter, a DIFFERENT register: never covers the total estimate.
        _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                prior="100", value="110", prior_day=date(2026, 9, 24), channel="demand")
        # ANOTHER meter on the account, measuring across 09/30: covers nothing.
        _actual(brazos, account["id"], other["id"], day=date(2026, 10, 6),
                prior="10", value="20", prior_day=date(2026, 9, 1))
        usage_service.recompute_account(account["id"], actor=marcus)
        assert _month(account["id"], SEP).quantity == Decimal("1760.000000")


def test_def_met_10163__the_judgment_is_per_meter_and_register():
    """The pure rule, with no database: another meter, another register, an
    actual measuring from AFTER the estimate, an earlier actual — none cover."""
    est = usage_rules.ReadFact("e", _at(date(2026, 9, 30)), Decimal("560"), "kWh", True,
                               asset_id="m1", channel="total")

    def act(asset="m1", channel="total", day=date(2026, 10, 6), start=date(2026, 9, 24)):
        return usage_rules.ReadFact("a", _at(day), Decimal("1200"), "kWh", False,
                                    asset_id=asset, channel=channel, measured_from=start)

    assert usage_rules.covered_estimate_ids([est], [act()]) == {"e"}
    assert usage_rules.covered_estimate_ids([est], [act(asset="m2")]) == set()
    assert usage_rules.covered_estimate_ids([est], [act(channel="tou_on")]) == set()
    assert usage_rules.covered_estimate_ids([est], [act(start=date(2026, 10, 1))]) == set()
    assert usage_rules.covered_estimate_ids([est], [act(day=date(2026, 9, 29),
                                                        start=date(2026, 9, 1))]) == set()
    # The ruling's "on or before": measured from the estimate's own date covers it.
    assert usage_rules.covered_estimate_ids([est], [act(start=date(2026, 9, 30))]) == {"e"}


# ══════════════════════════════════════════════════════════════════════════
# 3 · TENANT ISOLATION — another tenant's actual covers nothing here
# ══════════════════════════════════════════════════════════════════════════
def test_def_met_10163__another_tenants_reading_cannot_cover_an_estimate(
    brazos, marcus, lonestar, erin
):
    """Hard rule 1, app-layer half: the covering actuals are read under the
    CURRENT tenant only, so brazos's own covering actual is invisible to a
    computation run as lonestar — and lonestar's recompute and trigger reach
    nothing of brazos's."""
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10169")
        _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                  consumption="560", prior_day=date(2026, 9, 24))
        _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                prior="5176", value="6376", prior_day=date(2026, 9, 24))
        facts = [f for f, _ in usage_service._fact_rows(brazos.id, account_id=account["id"])]
        estimate_facts = [
            usage_rules.ReadFact(
                str(r.id), r.read_at, r.consumption, r.unit, True,
                asset_id=str(r.asset_id), channel=r.channel,
            )
            for r in metering_models.MeterRead.objects.filter(
                asset_id=meter["id"], status="estimated"
            )
        ]
        assert not any(f.is_estimate for f in facts), "covered within its own tenant"
        assert usage_service._covered_estimates(brazos.id, estimate_facts)
    with tenant_ctx(lonestar):
        assert usage_service._covered_estimates(lonestar.id, estimate_facts) == set()
        counts = usage_service.recompute_account(account["id"], actor=erin)
        assert counts == {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0}
        assert usage_service.with_estimate_holders([account["id"]]) == [str(account["id"])]


# ══════════════════════════════════════════════════════════════════════════
# 4 · THE TRIGGERS — the estimate's month is restated, not only the actual's
# ══════════════════════════════════════════════════════════════════════════
def _record_billed_estimate(account, meter, monkeypatch):
    """The real save path. The account it stamps is the product's own resolver
    in production (`collection_account_id`, the unit's occupant); this fixture's
    unit does not resolve one, so the stamp is pinned to the account here —
    the thing under test is the restatement, not the occupancy lookup."""
    from apps.metering import services as metering_services

    monkeypatch.setattr(
        metering_services, "collection_account_id", lambda *a, **k: account["id"]
    )
    return metering_services.record_billed_estimate(
        unit_id=account["unit_id"], service_code="electric", read_on=date(2026, 9, 30),
        consumption="560", unit="kWh", invoice_id="01a132a9-ffc7-7e9b-ae93-a514b5d4313b",
        asset_id=meter["id"],
    )


@override_settings(JOBS_EAGER=True)
def test_def_met_10163__a_billed_estimate_restates_its_month_and_a_covered_one_drops_out(
    brazos, marcus, django_capture_on_commit_callbacks, monkeypatch
):
    """The defect's own order: the 10/06 actual is on file, THEN the bill run's
    estimate is saved at issue. The save restates the account's months once the
    issue commits — and the covered estimate stays out of September."""
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10170")
        _actual(brazos, account["id"], meter["id"], day=date(2026, 10, 6),
                prior="5176", value="6376", prior_day=date(2026, 9, 24))
        usage_service.recompute_account(account["id"], actor=marcus)
        assert _month(account["id"], SEP).quantity == Decimal("1200.000000")

        with django_capture_on_commit_callbacks(execute=True) as callbacks:
            saved = _record_billed_estimate(account, meter, monkeypatch)
        assert saved["recorded"] is True and len(callbacks) == 1
        assert _month(account["id"], SEP).quantity == Decimal("1200.000000")
        assert _month(account["id"], OCT).quantity == Decimal("1200.000000")


@override_settings(JOBS_EAGER=True)
def test_def_met_10163__an_uncovered_billed_estimate_joins_its_month_on_save(
    brazos, marcus, django_capture_on_commit_callbacks, monkeypatch
):
    """No later actual: the saved estimate is restated INTO September (1,760)."""
    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10172")
        usage_service.recompute_account(account["id"], actor=marcus)
        assert _month(account["id"], SEP).quantity == Decimal("1200.000000")
        with django_capture_on_commit_callbacks(execute=True):
            _record_billed_estimate(account, meter, monkeypatch)
        september = _month(account["id"], SEP)
        assert (september.quantity, september.estimated_read_count) == (
            Decimal("1760.000000"), 1,
        )


def test_def_met_10163__another_occupants_estimate_on_the_meter_is_restated_too(
    brazos, marcus
):
    """The covering actual is the NEXT account's reading on the same meter: the
    read-commit refresh, asked for the newcomer only, restates the old
    account's September as well."""
    from apps.metering import services as metering_services

    with tenant_ctx(brazos):
        account, meter, _ = _worked_case(brazos, marcus, "E-10171")
        _estimate(brazos, account["id"], meter["id"], day=date(2026, 9, 30),
                  consumption="560", prior_day=date(2026, 9, 24))
        usage_service.recompute_account(account["id"], actor=marcus)
        assert _month(account["id"], SEP).quantity == Decimal("1760.000000")

        newcomer, _unit = _account_on(marcus, brazos, label="Unit B")
        _actual(brazos, newcomer["id"], meter["id"], day=date(2026, 10, 6),
                prior="5176", value="6376", prior_day=date(2026, 9, 24))
        assert usage_service.with_estimate_holders([newcomer["id"]]) == [
            str(newcomer["id"]), str(account["id"]),
        ]
        report = metering_services._refresh_monthly_usage(
            marcus, [newcomer["id"]], trigger="read_batch.posted"
        )
        assert report["accounts_restated"] == 2
        assert _month(account["id"], SEP).quantity == Decimal("1200.000000")


# ══════════════════════════════════════════════════════════════════════════
# 5 · THE BILL RUN — no estimate for a period a later actual already covers
# ══════════════════════════════════════════════════════════════════════════
def test_def_met_10163__a_bill_run_makes_no_estimate_a_later_actual_covers(brazos, dana):
    """Aug 31 actual 1,000; the 10/06 actual (1,012, measured FROM 08/31) is
    posted BEFORE the September run. September raises no missing read, makes no
    estimate and bills its base with the usage on the next bill; October then
    bills the 12 kWh once. Before the fix: a missing read, a clerk estimate
    saved at issue, and that estimate billed on top of the 12 kWh measured."""
    from apps.assets import models as asset_models
    from apps.billing import decisions, metering_seam, runs
    from apps.billing import models as billing_models
    from apps.metering import services as metering_services

    from tests.test_bbr_check_engine import a_cycle
    from tests.test_us_bil_001_prepare import a_billed_unit, a_priced_plan, an_account
    from tests.test_us_met_reads_helpers import (
        accept_warnings,
        commit_read,
        csv_body,
        seed_config,
        stage,
    )

    september_window = (date(2026, 9, 1), date(2026, 9, 30))
    october_window = (date(2026, 10, 1), date(2026, 10, 31))
    with tenant_ctx(brazos):
        seed_config()
        cycle = a_cycle(brazos)
        plan = a_priced_plan(brazos)
        unit = a_billed_unit(
            dana, brazos, cycle, plan, asset_no="M-10163", label="U", consumption=None
        )
        account = an_account(brazos, unit["id"], "A-10163")
        point = metering_models.ServicePoint.objects.get(tenant=brazos, unit_id=unit["id"])
        asset = asset_models.Asset.objects.get(tenant=brazos, service_point=point)
        commit_read(
            dana, asset.id, day="2026-08-31", value="1000", prior_value="990",
            consumption="10.000000", unit="kWh",
        )
        batch = stage(
            dana, csv_body("M-10163,2026-10-06,1012,total,E,"), period_month="2026-10-01"
        )
        metering_services.validate_read_batch(dana, batch["id"])
        accept_warnings(dana, batch["id"])
        metering_services.commit_read_batch(dana, batch["id"], {"certified": True})

        september = runs.create_run(
            cycle_id=cycle.id, period_start=september_window[0],
            period_end=september_window[1], bill_date=date(2026, 10, 7), label="September",
        )
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=september_window[0],
            period_end=september_window[1], service_date=date(2026, 10, 7),
        )
        raised = [p.reason for p in prepared.decisions if p.account_no == "A-10163"]
        [data] = [d for d in prepared.ready if d.account_no == "A-10163"]
        assert data.readings[0].covered_by_read_id is not None
        assert "missing_read" not in raised, raised
        # An `estimate` answer already on file for the service — given before
        # the 10/06 reading arrived — is NOT applied: the usage still waits.
        from apps.tenancy import selectors as tenancy_selectors

        decisions.record_decision(
            bill_run=september, account_id=str(account.id), case="missing_read",
            choice="estimate", amount=Decimal("5.000000"), unit="kWh",
            service_id=tenancy_selectors.service_ids_by_code()["electric"],
        )

        runs.calculate_run(
            decisions.apply_decisions(prepared, bill_run=september), bill_run=september
        )
        bill = billing_models.Invoice.objects.get(
            tenant=brazos, account=account, bill_run=september
        )
        services = bill.bill_payload["services"]
        assert not any(s.get("estimate") for s in services), services
        billing_models.Invoice.objects.filter(pk=bill.pk).update(
            status=billing_models.INVOICE_ISSUED
        )
        bill.refresh_from_db()
        saved = metering_seam.record_billed_estimates(bill)
        assert saved.recorded == 0
        assert not metering_models.MeterRead.objects.filter(
            asset_id=asset.id, status="estimated"
        ).exists()

        october = runs.prepare_run(
            cycle_id=cycle.id, period_start=october_window[0],
            period_end=october_window[1], service_date=date(2026, 11, 1),
        )
    [data] = [d for d in october.ready if d.account_no == "A-10163"]
    billed = data.readings[0].consumption
    print(
        f"\nPROOF DEF-MET-10163 bill run: September estimate none; October bills "
        f"{billed.amount} {billed.unit} for 12 measured"
    )
    assert (billed.amount, billed.unit) == (Decimal("12"), "kWh")

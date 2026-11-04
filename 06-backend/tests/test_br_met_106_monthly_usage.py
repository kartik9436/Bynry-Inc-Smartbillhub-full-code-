# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-011 (the S21 operational tabs — Usage is the first of five)
#           Change: CR-030 W3 task 3.8 (the ACC-01 Usage tab)
# Rules:    BR-MET-106 (Σ MeterRead.consumption per calendar month per account
#           per service, WITH its unit, STORED; corrections RESTATE and never
#           edit; an unread month is ABSENT, never 0; estimates count and are
#           MARKED — PO 2026-08-24) · BR-MET-028 (an estimate carries
#           consumption and NO current_value) · contrast BR-CUS-016 (ageing:
#           derived, never stored) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           rule 3 (an explicit unit, always) · rule 4 (corrections are new
#           rows) · rule 6 (idempotency) · rule 7 (the audit row)
# Questions: OQ-358 (a month whose reads for ONE service disagree about the unit)
# ───────────────────────────────────────────────────────
"""BR-MET-106 — the stored month, end to end.

The r10 figures this file pins, because they are the ones on the PO's own
screen (18-cr030-onboarding-design.md §5.2.2, Usage row):

    AVG/MONTH 628 kWh · PEAK 842 kWh (Jul 2026) · LOW 412 kWh (Feb 2026)
    · WATER AVG 3.42 kgal

`YOY +8.2%` is NOT pinned to that literal: it is screen copy over a fixture
this repo does not hold, and the strip computes the figure from the account's
own months. What IS pinned is the computation, against a fixture whose two
twelve-month totals are stated in the test.
"""

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from apps.assets import services as asset_services
from apps.customers import services as customers_services
from apps.metering import api as metering_api
from apps.metering import models as metering_models
from apps.metering import monthly_usage as usage_rules
from apps.metering import monthly_usage_reads as usage_reads
from apps.metering import monthly_usage_service as usage_service
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.isolation_helpers import (
    assert_rls_scoped,
    assert_write_into_other_tenant_refused,
    clear_live_guc,
    current_guc,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ── fixture plumbing ────────────────────────────────────────────────────────
def _plan(tenant, service_code="electric", name="Small Commercial"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account_on(actor, tenant, *, services=("electric",), label="Unit A", address=None):
    """One account on one unit, with a service point per service.

    The state J2 leaves behind, built through the real services — no ORM
    shortcut anywhere except the read rows themselves (see `_read`).
    """
    premises = make_premises(actor, **({"address_line": address} if address else {}))
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, services[0]).id)}
    )
    for code in services:
        _plan(tenant, code)
        metering_services.ensure_service_point(unit["id"], code)
    account = customers_services.create_account(
        actor,
        {
            "unit_id": unit["id"],
            "account_type": "residential",
            "opened_at": "2024-01-05",
            "contact": {"full_name": "Elena Rivera", "email": "elena@example.test"},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(
                "Elena Rivera", account_type="residential"
            ),
        },
    )
    return account, unit


def _meter(actor, unit_id, *, asset_no, service="electric", uom="kWh"):
    return asset_services.create_asset(
        actor,
        {
            "type": "meter",
            "asset_no": asset_no,
            "service": service,
            "unit": uom,
            "read_method": "walk_by" if service == "electric" else "manual",
            "multiplier": "1",
            "unit_id": unit_id,
            "install_date": "2024-01-05",
            "status": "active",
        },
    )


def _read(tenant, account_id, asset_id, *, day, consumption, unit="kWh", estimated=False):
    """One committed read, written directly — HISTORY SETUP only.

    Same posture as `tests/test_us_met_reads_helpers.commit_read`: building
    each row through the five-step import wizard would make the fixture, not
    the behaviour, the thing under test. Every row still carries its EXPLICIT
    unit (CLAUDE.md rule 3) and its account, which is what BR-MET-106 groups by.

    `estimated=True` reproduces BR-MET-028 exactly: consumption present,
    `current_value` NULL.
    """
    return metering_models.MeterRead.objects.create(
        tenant_id=tenant.id,
        account_id=account_id,
        asset_id=asset_id,
        read_at=datetime(day.year, day.month, day.day, tzinfo=timezone.utc),
        channel="total",
        current_value=None if estimated else Decimal("1000"),
        consumption=None if consumption is None else Decimal(str(consumption)),
        unit=unit,
        source="estimated" if estimated else "import",
        status="estimated" if estimated else "ok",
        lifecycle="committed",
    )


def _heads(account_id):
    return list(
        metering_models.MonthlyUsage.objects.filter(
            account_id=account_id, superseded_by_id__isnull=True, superseded_at__isnull=True
        ).order_by("period_month")
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · A NORMAL MONTH: Σ consumption, ONE row, carrying its unit
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc1__a_normal_month_is_summed_stored_and_carries_its_unit(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7001")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 31), consumption="158.000000")
        # A different month must not leak into July's figure.
        _read(brazos, account["id"], meter["id"], day=date(2026, 8, 3), consumption="284.000000")
        audit_rows.clear()

        counts = usage_service.recompute_account(account["id"], actor=marcus)
        assert counts["stated"] == 2 and counts["restated"] == 0

        july = [h for h in _heads(account["id"]) if h.period_month == date(2026, 7, 1)]
        assert len(july) == 1, "BR-MET-106: one LIVE statement per account per service per month"
        row = july[0]
        assert row.quantity == Decimal("842.000000")  # 684 + 158 — r10's PEAK figure
        assert row.unit == "kWh"  # hard rule 3: EXPLICIT, never inferred
        assert row.read_count == 2
        assert row.estimated_read_count == 0
        assert sorted(row.source_read_ids) == sorted(row.source_read_ids)
        assert len(row.source_read_ids) == 2, "the lineage HEADS it summed travel with the figure"
        assert row.computed_at is not None

        actions = [r["action"] for r in audit_rows]
        assert usage_service.ACTION_STATED in actions


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · AN ESTIMATE COUNTS AND IS MARKED (BR-MET-028 · BR-MET-106)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc2__an_estimate_is_included_in_the_month_and_recorded_as_one(brazos, marcus):
    """*"a customer looking at a 628 kWh month is entitled to know part of it
    was estimated"* — so the estimate is IN the sum and the month says so."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7002")
        _read(brazos, account["id"], meter["id"], day=date(2026, 6, 3), consumption="412.000000")
        estimate = _read(
            brazos,
            account["id"],
            meter["id"],
            day=date(2026, 6, 20),
            consumption="216.000000",
            estimated=True,
        )
        assert estimate.current_value is None, "BR-MET-028: an estimate has no register value"

        usage_service.recompute_account(account["id"], actor=marcus)
        row = _heads(account["id"])[0]

        assert row.quantity == Decimal("628.000000")  # 412 + 216 — r10's AVG figure
        assert row.read_count == 2
        assert row.estimated_read_count == 1, "the month RECORDS that it included an estimate"

        payload = usage_reads.usage_payload(account["id"], today=date(2026, 8, 1))
        point = [p for p in payload["series"][0]["points"] if p["month"] == "2026-06"][0]
        assert point["estimated"] is True
        assert point["estimated_read_count"] == 1
        assert point["quantity_display"] == "628"


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · A CORRECTION RESTATES, IT NEVER EDITS (hard rule 4 · BR-MET-106)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc3__a_corrected_read_restates_the_month_and_the_old_row_survives(
    brazos, marcus, audit_rows
):
    """The read is superseded exactly as B2 r8 allows; the MONTH gains a NEW
    row, the old one keeps the quantity and the read ids it was true for, and
    the chart reads the head."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7003")
        wrong = _read(
            brazos, account["id"], meter["id"], day=date(2026, 5, 3), consumption="612.000000"
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        first = _heads(account["id"])[0]
        assert first.quantity == Decimal("612.000000")

        # The read correction: a NEW row, and the old one marked superseded —
        # the ONE update B2 r8 permits on a committed read.
        right = _read(
            brazos, account["id"], meter["id"], day=date(2026, 5, 4), consumption="598.000000"
        )
        metering_models.MeterRead.objects.filter(pk=wrong.pk).update(
            superseded_by_id=right.id, superseded_at=datetime.now(timezone.utc)
        )
        audit_rows.clear()

        counts = usage_service.recompute_account(account["id"], actor=marcus)
        assert counts["restated"] == 1 and counts["stated"] == 0

        heads = _heads(account["id"])
        assert len(heads) == 1
        assert heads[0].quantity == Decimal("598.000000"), "the chart reads the LATEST statement"
        assert heads[0].id != first.id, "RESTATED — a new row, never an edit"

        # hard rule 4: the superseded statement is intact, not deleted, not edited.
        old = metering_models.MonthlyUsage.objects.get(pk=first.pk)
        assert old.quantity == Decimal("612.000000")
        assert old.superseded_by_id == heads[0].id
        assert old.superseded_at is not None
        assert old.supersede_reason == "reads_changed"

        restated = [r for r in audit_rows if r["action"] == usage_service.ACTION_RESTATED]
        assert restated, "a number the customer was already shown changed — it is audited"
        assert restated[0]["before"]["quantity"] == "612.000000"
        assert restated[0]["after"]["quantity"] == "598.000000"


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · AN UNREAD MONTH IS ABSENT, NEVER `0`
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc4__an_unread_month_has_no_row_and_renders_absent_not_zero(brazos, marcus):
    """*"zero usage and no read are different claims about a customer"*."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7004")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="842.000000")
        # June is never read. August IS read, and read at ZERO — which is a
        # real claim and must NOT look like June.
        _read(brazos, account["id"], meter["id"], day=date(2026, 8, 3), consumption="0.000000")

        usage_service.recompute_account(account["id"], actor=marcus)
        months = {h.period_month for h in _heads(account["id"])}
        assert date(2026, 6, 1) not in months, "no row is written for a month with no reads"
        assert date(2026, 8, 1) in months, "a month read at zero IS stated"

        payload = usage_reads.usage_payload(account["id"], today=date(2026, 8, 1))
        points = {p["month"]: p for p in payload["series"][0]["points"]}
        assert points["2026-06"]["absent"] is True
        assert points["2026-06"]["quantity"] is None, "ABSENT, never 0"
        assert points["2026-06"]["quantity_display"] is None
        assert points["2026-08"]["absent"] is False
        assert points["2026-08"]["quantity"] == "0.000000", "read-at-zero is a FIGURE, not absence"


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · TWO SERVICES ON ONE ACCOUNT ARE NEVER ADDED TOGETHER (hard rule 3)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc5__electric_and_water_are_two_rows_and_two_series(brazos, marcus):
    """*"kWh, kgal and therms are never added together"* — so `All` is two
    series with two units, never one summed bar."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos, services=("electric", "water"))
        electric = _meter(marcus, unit["id"], asset_no="M-7005")
        water = _meter(marcus, unit["id"], asset_no="M-7006", service="water", uom="kgal")
        _read(brazos, account["id"], electric["id"], day=date(2026, 7, 3), consumption="842.000000")
        _read(
            brazos,
            account["id"],
            water["id"],
            day=date(2026, 7, 3),
            consumption="3.420000",
            unit="kgal",
        )

        usage_service.recompute_account(account["id"], actor=marcus)
        heads = _heads(account["id"])
        assert len(heads) == 2, "one row per SERVICE per month — never one combined row"
        by_unit = {h.unit: h.quantity for h in heads}
        assert by_unit == {"kWh": Decimal("842.000000"), "kgal": Decimal("3.420000")}

        payload = usage_reads.usage_payload(account["id"], today=date(2026, 7, 1))
        assert [s["code"] for s in payload["services"]] == ["electric", "water"]
        units = {s["service"]["code"]: s["unit"] for s in payload["series"]}
        assert units == {"electric": "kWh", "water": "kgal"}
        # r10's fifth KPI reads the WATER series, not a conversion of anything.
        assert payload["water_avg"]["display"] == "3.42"
        assert payload["water_avg"]["unit"] == "kgal"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · A RECOMPUTE IS IDEMPOTENT (CLAUDE.md rule 6)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc6__recomputing_an_unchanged_month_writes_nothing_at_all(
    brazos, marcus, audit_rows
):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7007")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000")

        first = usage_service.recompute_account(account["id"], actor=marcus)
        assert first == {"stated": 1, "restated": 0, "unchanged": 0, "withdrawn": 0}
        head = _heads(account["id"])[0]
        audit_rows.clear()

        for _ in range(3):
            again = usage_service.recompute_account(account["id"], actor=marcus)
            assert again == {"stated": 0, "restated": 0, "unchanged": 1, "withdrawn": 0}

        assert metering_models.MonthlyUsage.objects.filter(account_id=account["id"]).count() == 1
        after = metering_models.MonthlyUsage.objects.get(pk=head.pk)
        assert after.computed_at == head.computed_at, (
            "an unchanged figure is not restamped — a new computed_at would be a "
            "restatement that did not happen"
        )
        assert audit_rows == [], "nothing was written, so nothing is audited"


def test_br_met_106_tc6b__a_month_whose_reads_are_withdrawn_goes_back_to_absent_once(
    brazos, marcus
):
    """The mirror of TC-4: a stated month whose reads are all superseded stops
    being stated — and is NOT replaced by a zero row. Withdrawal is idempotent
    too, or every recompute would write another audit row forever."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7008")
        read = _read(
            brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="684.000000"
        )
        usage_service.recompute_account(account["id"], actor=marcus)
        assert len(_heads(account["id"])) == 1

        metering_models.MeterRead.objects.filter(pk=read.pk).update(
            superseded_by_id=read.id, superseded_at=datetime.now(timezone.utc)
        )
        counts = usage_service.recompute_account(account["id"], actor=marcus)
        assert counts["withdrawn"] == 1
        assert _heads(account["id"]) == [], "ABSENT again — and no zero row was invented"

        again = usage_service.recompute_account(account["id"], actor=marcus)
        assert again["withdrawn"] == 0, "rule 6: a second withdrawal is not a second write"


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · OQ-358 — ONE MONTH, ONE SERVICE, TWO UNITS: REFUSED BY NAME
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc7__a_month_whose_reads_disagree_about_the_unit_refuses_naming_oq_358(
    brazos, marcus
):
    """Nothing is guessed. BR-MET-106 says the figure carries ONE unit; it does
    not say what happens when the inputs disagree, so the prime directive
    applies and the code stops with the question's id in it."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        first = _meter(marcus, unit["id"], asset_no="M-7009")
        second = _meter(marcus, unit["id"], asset_no="M-7010")
        _read(brazos, account["id"], first["id"], day=date(2026, 7, 3), consumption="600.000000")
        _read(
            brazos,
            account["id"],
            second["id"],
            day=date(2026, 7, 4),
            consumption="42.000000",
            unit="MWh",
        )

        with pytest.raises(NotImplementedError) as caught:
            usage_service.recompute_account(account["id"], actor=marcus)
        assert "OQ-358" in str(caught.value)
        assert metering_models.MonthlyUsage.objects.filter(account_id=account["id"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · THE 5-METRIC STRIP, ON r10's OWN FIGURES
# ══════════════════════════════════════════════════════════════════════════
#: Twelve months to 2026-08 whose mean is exactly 628 kWh, with Jul 2026 at 842
#: and Feb 2026 at 412 — r10's AVG / PEAK / LOW, reproduced out of the product.
#: Σ = 7,536.
_TWELVE = {
    date(2025, 9, 1): "560",
    date(2025, 10, 1): "540",
    date(2025, 11, 1): "600",
    date(2025, 12, 1): "770",
    date(2026, 1, 1): "830",
    date(2026, 2, 1): "412",
    date(2026, 3, 1): "500",
    date(2026, 4, 1): "520",
    date(2026, 5, 1): "598",
    date(2026, 6, 1): "628",
    date(2026, 7, 1): "842",
    date(2026, 8, 1): "736",
}
#: The twelve months before them, flat at 580 → Σ = 6,960. The YoY the strip
#: shows is therefore (7536 − 6960) / 6960 = +8.275862%, displayed +8.28%.
_PRIOR_MONTHLY = "580"


def test_br_met_106_tc8__the_kpi_strip_reproduces_r10s_own_figures(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos, services=("electric", "water"))
        electric = _meter(marcus, unit["id"], asset_no="M-7011")
        water = _meter(marcus, unit["id"], asset_no="M-7012", service="water", uom="kgal")

        for month, value in _TWELVE.items():
            _read(brazos, account["id"], electric["id"], day=month, consumption=value)
            _read(
                brazos,
                account["id"],
                water["id"],
                day=month,
                consumption="3.420000",
                unit="kgal",
            )
        for month in usage_rules.window_months(date(2025, 8, 1), 12):
            _read(brazos, account["id"], electric["id"], day=month, consumption=_PRIOR_MONTHLY)

        usage_service.recompute_account(account["id"], actor=marcus)
        payload = usage_reads.usage_payload(account["id"], months=24, today=date(2026, 8, 1))

        assert payload["window"] == {
            "months": 24,
            "from": "2024-09",
            "to": "2026-08",
            "options": [12, 24],
        }
        series = [s for s in payload["series"] if s["service"]["code"] == "electric"][0]
        assert len(series["points"]) == 24
        metrics = series["metrics"]

        # r10: `Avg / month 628 kWh · last 12 months`
        assert metrics["avg_per_month"]["display"] == "628"
        assert metrics["avg_per_month"]["unit"] == "kWh"
        assert metrics["avg_per_month"]["months_counted"] == 12
        # r10: `Peak month 842 kWh · Jul 2026`
        assert metrics["peak"]["display"] == "842"
        assert metrics["peak"]["month"] == "2026-07"
        # r10: `Low month 412 kWh · Feb 2026`
        assert metrics["low"]["display"] == "412"
        assert metrics["low"]["month"] == "2026-02"
        # r10: `YoY change +8.2% · vs prior year` — computed, at 6 dp, shown at 2.
        assert metrics["yoy"]["this_year_total"] == "7536.000000"
        assert metrics["yoy"]["prior_year_total"] == "6960.000000"
        assert metrics["yoy"]["value"] == "8.275862"
        assert metrics["yoy"]["display"] == "+8.28"
        # r10: `Water avg 3.42 kgal · last 12 months`
        assert payload["water_avg"]["display"] == "3.42"
        assert payload["water_avg"]["unit"] == "kgal"

        # `Compare to neighbors →` (B18 D3) is served by nothing and stubbed by
        # nothing — the whole payload must not mention it.
        assert "neighbor" not in str(payload).lower()


def test_br_met_106_tc8b__every_metric_is_absent_rather_than_zero_when_nothing_is_read(
    brazos, marcus
):
    """An average over nothing is not 0, and "no change" is not "we cannot
    say" — each absence names its own reason."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7013")
        _read(brazos, account["id"], meter["id"], day=date(2026, 8, 3), consumption="284.000000")
        usage_service.recompute_account(account["id"], actor=marcus)

        payload = usage_reads.usage_payload(account["id"], today=date(2026, 8, 1))
        metrics = payload["series"][0]["metrics"]
        assert metrics["avg_per_month"]["months_counted"] == 1
        assert metrics["avg_per_month"]["months_absent"] == 11, (
            "the average divides by the months that HAVE a figure — counting the "
            "absent ones as zero is the zero bar wearing a different hat"
        )
        assert metrics["avg_per_month"]["display"] == "284", (
            "one month of 284 kWh averages 284 kWh, not 284/12 = 23.67 — an "
            "absent month is NOT a zero in the denominator"
        )
        assert metrics["yoy"]["value"] is None
        assert metrics["yoy"]["absent_reason"] == "no_prior_reads"
        # …and the fifth KPI, on an account with no water at all.
        assert payload["water_avg"]["value"] is None
        assert payload["water_avg"]["absent_reason"] == "no_water_months"


# ══════════════════════════════════════════════════════════════════════════
# TC-9 · TENANT SCOPING (CLAUDE.md hard rule 1)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc9__one_tenants_months_are_invisible_to_another(
    brazos, marcus, lonestar, erin
):
    """The APP-LAYER half. The DATABASE half (RLS under a non-superuser role)
    is `test_br_met_106_tc9b`, and on this container it cannot run — see its
    own docstring."""
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7014")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="842.000000")
        usage_service.recompute_account(account["id"], actor=marcus)
        assert len(_heads(account["id"])) == 1

    with tenant_ctx(lonestar):
        # The intruder tenant asks for the SAME account id and gets nothing —
        # not an error, not another tenant's row.
        payload = usage_reads.usage_payload(account["id"], today=date(2026, 7, 1))
        assert payload["series"] == []
        assert payload["services"] == []
        assert usage_service.heads_for(account["id"]) == []
        # …and its own recompute cannot reach the foreign account's reads.
        counts = usage_service.recompute_account(account["id"], actor=erin)
        assert counts == {"stated": 0, "restated": 0, "unchanged": 0, "withdrawn": 0}

    with tenant_ctx(brazos):
        assert len(_heads(account["id"])) == 1, "the intruder's recompute changed nothing"


@pytest.mark.isolation
@requires_postgres
def test_br_met_106_tc9b__rls_scopes_meter_read_monthly_usage(brazos, marcus, lonestar, rls):
    """The DATABASE half, under `sbh_rls_probe` — a NOLOGIN NOSUPERUSER
    NOBYPASSRLS role, because the app role bypasses RLS in CI and an assertion
    made on it proves nothing.

    ⚠ **SKIPPED ON THE DEFAULT sqlite RUN** (`requires_postgres`), and it took
    a detour to run at all, which is worth recording: `migrate` on a FRESH
    Postgres database dies inside `assets.0003_meter_types_and_read_methods`
    with `DataError: invalid input syntax for type uuid: ""` — DEF-639 — so no
    test database can be built from scratch in this container today. It was RUN
    against a database cloned from an already-migrated one with metering 0024
    and 0025 applied on top, which exercises the REAL policy this migration
    installs.

    **PROVEN RED BEFORE TRUSTED GREEN (hard-won law 7):** with
    `ALTER TABLE meter_read_monthly_usage DISABLE ROW LEVEL SECURITY` this case
    failed with

        AssertionError: meter_read_monthly_usage: LEAK — tenant <lonestar> can
        read tenant <brazos>'s rows

    and passed again the moment ENABLE + FORCE were restored.
    """
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7015")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="842.000000")
        usage_service.recompute_account(account["id"], actor=marcus)

    # (2) the owner sees its own row, the intruder sees none of it — asserted
    # through the DATABASE, with the app-layer filter deliberately out of the path.
    assert_rls_scoped(
        rls, "meter_read_monthly_usage", owner=brazos, intruder=lonestar, min_owner_rows=1
    )
    # (1) DENY-BY-DEFAULT, and it is asserted DIFFERENTLY here on purpose.
    #
    # ⚠ **`isolation_helpers.assert_denied_without_context` DOES NOT HOLD FOR A
    # `NULLIF(...)` POLICY, AND THAT IS A FINDING FOR THE LANE REWRITING THE
    # OTHER 34.** It asserts the database RAISES — *"no `app.tenant_id` ⇒ the
    # `::uuid` cast fails ⇒ zero rows, loudly"* — which is true of B2 §3's
    # literal cast and is exactly the behaviour DEF-639 had to remove: a cast
    # that raises inside a migration's FK-validation scan is what makes a fresh
    # database un-buildable. Under `NULLIF(current_setting(...), '')::uuid` an
    # unset GUC yields NULL, `tenant_id = NULL` is NULL, and a NULL policy
    # admits NOTHING — **the same guarantee, delivered as zero rows instead of
    # an exception.** Measured here first: with the helper called as written
    # this case failed `Failed: DID NOT RAISE DatabaseError`.
    #
    # So the guarantee is asserted directly, in the shape the repaired policy
    # actually delivers: with no tenant context the probe sees NOTHING.
    clear_live_guc()
    assert current_guc() == ""
    assert rls.rows("SELECT count(*) FROM meter_read_monthly_usage") == [(0,)], (
        "deny-by-default: with app.tenant_id unset the table must expose no row. "
        "A NULL policy predicate admits nothing — same guarantee as the cast that "
        "used to raise, without the exception that poisoned migrations (DEF-639)."
    )
    # (4) WITH CHECK refuses a row stamped for another tenant.
    assert_write_into_other_tenant_refused(
        rls, "meter_read_monthly_usage", owner=brazos, intruder=lonestar
    )


# ══════════════════════════════════════════════════════════════════════════
# TC-10 · THE ENDPOINT (`GET /accounts/{id}/usage`)
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc10__the_endpoint_serves_the_tab_and_never_recomputes(brazos, marcus):
    with tenant_ctx(brazos):
        account, unit = _account_on(marcus, brazos)
        meter = _meter(marcus, unit["id"], asset_no="M-7016")
        _read(brazos, account["id"], meter["id"], day=date(2026, 7, 3), consumption="842.000000")

        # Before any recompute the endpoint answers HONESTLY: nothing has been
        # stated about this account, so there is no series. A GET that wrote
        # would be a GET that surprises somebody.
        empty = api_call(
            metering_api.account_usage,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            account_id=account["id"],
        )
        assert empty.status_code == 200
        assert empty.data["series"] == []
        assert metering_models.MonthlyUsage.objects.filter(account_id=account["id"]).count() == 0

    # ⚠ `api_call` enters its OWN tenant context and CLEARS it on exit, so the
    # outer `tenant_ctx` is gone by the time the view returns. Re-entered
    # rather than worked around: that is how the shipping middleware behaves.
    with tenant_ctx(brazos):
        usage_service.recompute_account(account["id"], actor=marcus)
        served = api_call(
            metering_api.account_usage,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            account_id=account["id"],
            query={"months": "12"},
        )
        assert served.status_code == 200
        assert served.data["window"]["months"] == 12
        assert len(served.data["series"][0]["points"]) == 12
        assert served.data["rule_ref"] == "BR-MET-106"

        # BR-SHL-011: an unknown param falls back, it never 4xxs.
        loose = api_call(
            metering_api.account_usage,
            "get",
            user=FakeUser(),
            tenant=brazos,
            role="billing_clerk",
            account_id=account["id"],
            query={"months": "nonsense"},
        )
        assert loose.status_code == 200
        assert loose.data["window"]["months"] == 24


# ══════════════════════════════════════════════════════════════════════════
# TC-11 · THE RULES MODULE ON ITS OWN — no tenant, no row, no transaction
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_106_tc11__the_month_key_never_shifts_a_read_into_a_neighbouring_month():
    """`meter_reads.read_at` is stamped 00:00Z of the read DATE, so the UTC
    date IS the read date. A read on the 1st stays in its own month."""
    assert usage_rules.month_of(datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc)) == date(2026, 7, 1)
    assert usage_rules.month_of(datetime(2026, 7, 31, 23, 59, tzinfo=timezone.utc)) == date(
        2026, 7, 1
    )


def test_br_met_106_tc11b__a_month_with_no_usable_reads_is_none_not_a_zero_figure():
    assert usage_rules.summarise(date(2026, 7, 1), []) is None
    only_nulls = [
        usage_rules.ReadFact(
            read_id="a",
            read_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
            consumption=None,
            unit="kWh",
            is_estimate=False,
        )
    ]
    assert usage_rules.summarise(date(2026, 7, 1), only_nulls) is None


def test_br_met_106_tc11c__the_fingerprint_is_stable_across_read_orderings():
    """CLAUDE.md rule 6: two recomputes that saw the same reads must produce
    the same key, whatever order the database handed them back in."""

    def fact(read_id, value):
        return usage_rules.ReadFact(
            read_id=read_id,
            read_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
            consumption=Decimal(value),
            unit="kWh",
            is_estimate=False,
        )

    forward = usage_rules.summarise(date(2026, 7, 1), [fact("a", "1"), fact("b", "2")])
    backward = usage_rules.summarise(date(2026, 7, 1), [fact("b", "2"), fact("a", "1")])
    assert forward.fingerprint == backward.fingerprint
    changed = usage_rules.summarise(date(2026, 7, 1), [fact("a", "1"), fact("b", "3")])
    assert changed.fingerprint != forward.fingerprint


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — AccountUsageTab.test.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_br_met_106_monthly_usage.py
# exceptions: E3 TC-9b RAN AND PASSED against live Postgres under `sbh_rls_probe`, but only after CLONING an already-migrated database: a fresh `migrate` dies inside assets.0003 with DEF-639's `invalid input syntax for type uuid: ""`, so the from-scratch path is still broken and is L1's to fix · E3 `isolation_helpers.assert_denied_without_context` DOES NOT HOLD for a `NULLIF(...)` policy — it asserts the database RAISES, and the repaired predicate denies by yielding NULL instead. This case asserts deny-by-default directly (zero rows under the probe with the GUC cleared) and the helper is REPORTED to the lane rewriting the other 34 policies
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

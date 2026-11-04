# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-BIL-9012
# Ruling:  PO 2026-10-01, option A (decision log, "A BILL CUT AT ONE CHARGE
#          CODE'S PRICE CHANGE SPLITS ONLY THE SERVICE WHOSE PRICE CHANGED"),
#          verbatim: *"A · Split only the service whose price changed. Electric
#          stays $12.00, and only water is split."*
# Rules:   BR-BIL-1066 · BR-RAT-1050 · BR-RAT-114 · B4.3 ❄️ (applied per part)
# Code:    apps/billing/backbill.py (cut_groups, groups_split_by_days) ·
#          apps/billing/midperiod.py (split_plan, gather_split, price_split_bill)
# ───────────────────────────────────────────────────────
"""A bill cut at a charge code's price change splits ONLY that service.

THE PO'S CASE. A bill for 16 Oct – 15 Nov; water's base $8.00 → $9.00 from
11/01; electric unchanged at $12.00.

* **Before:** every service was cut at 11/01, so electric came out
  16/31 × 12 + 15/30 × 12 = $6.19 + $6.00 = **$12.19** — 19 cents for a price
  that never moved.
* **Ruled (A):** electric is ONE part over the bill's own period = **$12.00**;
  water is split exactly as before, 16/31 × 8 + 15/30 × 9 = $4.13 + $4.50 =
  **$8.63**.

Proved through the one-time INTERIM door (the PO's example), the BULK run's own
prepare → price pair (`runs.prepare_run` → `runs.price_account`, which is what
the Check attaches the split for), and the CATCH-UP (each part over the stated
sub-period: water $4.13 + $4.35, electric ONE line of $12.00 where it was two).
A bill with nothing changed inside it is not cut at all.

Written RED FIRST (law 7): before the fix the interim bill carried electric as
[$6.00, $6.19] and the catch-up as [$5.81, $6.19].

PostgreSQL only, for the reason `test_cr156_charge_prices_pg.py` gives (the
dated price table is a range type with an exclusion constraint):

    DJANGO_SETTINGS_MODULE=config.settings.local JOBS_EAGER=false \\
      DATABASE_URL="postgres://postgres@127.0.0.1:55433/<your db>?sslmode=disable" \\
      pytest -q --reuse-db tests/test_def_bil_9012_cut_only_the_changed_service_pg.py
"""

from __future__ import annotations

import calendar
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import api as billing_api
from apps.billing import backbill
from apps.billing import models as billing_models
from apps.customers import models as customer_models
from apps.metering import models as metering_models
from apps.rating import charge_prices
from apps.rating import models as rating_models
from apps.rating.constants import ALL_SIZES
from apps.tenancy import models as tenancy_models
from core import sample_fixture as fixture

from tests.isolation_helpers import requires_postgres
from tests.test_otb_a_one_time_api_contract import _clerk, _post
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, state_size_axis, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = [pytest.mark.django_db]

CENT = Decimal("0.01")
WATER_OLD, WATER_NEW, ELECTRIC = Decimal("8.00"), Decimal("9.00"), Decimal("12.00")
CHANGE = date(2026, 11, 1)
FROM, TO = date(2026, 10, 16), date(2026, 11, 15)
KWH = "kWh"


# ── fixtures ────────────────────────────────────────────────────────────────
@pytest.fixture
def a_monthly_cycle(monkeypatch):
    """The unit bills on ONE calendar-month cycle (the cr156 file's fixture)."""
    from apps.metering import selectors as metering_selectors

    def period(unit_id, as_of=None):
        last = calendar.monthrange(as_of.year, as_of.month)[1]
        return {"start": as_of.replace(day=1).isoformat(), "end": as_of.replace(day=last).isoformat()}

    monkeypatch.setattr(
        metering_selectors,
        "cycle_terms_for_unit",
        lambda unit_id: {"code": "C-MONTH", "name": "Monthly", "due_days": 21},
    )
    monkeypatch.setattr(metering_selectors, "billing_period_for_unit", period)


def _two_service_plan(tenant):
    """Water ($8.00 base, the fixture's ladder) and electric ($12.00 base, the
    fixture's ladder) on ONE published plan, each base on its own `is_base`
    charge code — the object that owns the base (BR-RAT-088)."""
    from apps.rating import selectors as rating_selectors

    plan = make_plan(tenant, name="DEF-BIL-9012 Residential", services=("water", "electric"))
    rating_models.RatePlan.objects.filter(pk=plan.id).update(
        effective_from=date(2026, 1, 1), effective_to=None
    )
    shape = {
        "water": (WATER_OLD, fixture.WATER_UOM, fixture.WATER_TIERS),
        "electric": (ELECTRIC, KWH, fixture.ELECTRIC_TIERS),
    }
    for row in rating_selectors.plan_rate_schedules(plan.id):
        base, uom, tiers = shape[row["service_code"]]
        version = rating_models.TariffVersion.objects.create(
            tenant=tenant,
            tariff=row["tariff"],
            model="tiered",
            base_charge=base,
            uom=uom,
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        state_size_axis(version, row["service_code"])
        for seq, (from_qty, to_qty, price) in enumerate(tiers, start=1):
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=seq,
                from_qty=Decimal(from_qty),
                to_qty=None if to_qty is None else Decimal(to_qty),
                unit_price=Decimal(price),
            )
        rating_models.PlanService.objects.update_or_create(
            tenant=tenant,
            rate_plan_id=plan.id,
            service_id=row["service_id"],
            defaults={"base_charge": base},
        )
    codes = {}
    for service, amount in (("water", WATER_OLD), ("electric", ELECTRIC)):
        code, _ = rating_models.Charge.objects.get_or_create(
            tenant=tenant,
            code=f"BASE-{service[0].upper()}-9012",
            defaults=dict(
                name=f"{service} base",
                charge_type="recurring",
                service=tenancy_models.Service.objects.get(code=service),
                amount_rule="flat",
                is_base=True,
                applies_to_customer_classes=[],
            ),
        )
        charge_prices.write_flat_amount_directly(code, amount)
        codes[service] = code
    # The PO's case: water's base repriced $8.00 → $9.00 from 11/01.
    charge_prices.save_prices(
        codes["water"], {(ALL_SIZES, None): WATER_NEW}, effective_from=CHANGE, effective_to=None
    )
    return plan


def _two_service_account(tenant, actor, *, cycle=None, account_no="DEF-9012"):
    plan = _two_service_plan(tenant)
    premises = make_premises(
        actor, address_line=f"{account_no} Quarry Hill Rd", services_available=["water", "electric"]
    )
    unit = make_unit(actor, premises["id"], label="Unit A", services=["water", "electric"])
    water = a_meter(
        actor, asset_no=f"W-{account_no}", service="water", uom=fixture.WATER_UOM, unit_id=unit["id"]
    )
    power = a_meter(actor, asset_no=f"E-{account_no}", service="electric", uom=KWH, unit_id=unit["id"])
    if cycle is not None:
        metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
            cycle=cycle
        )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
    )
    account = customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        account_no=account_no,
        status=customer_models.AccountStatus.objects.get(tenant=tenant, code="active"),
        account_type=customer_models.AccountType.objects.get(tenant=tenant, code="residential"),
        opened_at=date(2026, 7, 1),
    )
    # A baseline the day before the window, and the window's closing read.
    for asset, uom, before, after in (
        (water, fixture.WATER_UOM, "1200", "1240"),
        (power, KWH, "5000", "5400"),
    ):
        for day, value, prior in ((date(2026, 10, 15), before, None), (TO, after, before)):
            commit_read(
                actor,
                asset["id"],
                day=day.isoformat(),
                value=value,
                prior_value=prior,
                consumption=None if prior is None else Decimal(value) - Decimal(prior),
                unit=uom,
                days_since_prior=None if prior is None else 31,
            )
    return account, unit


def _bases_by_service(lines) -> dict[str, list[Decimal]]:
    """`{service: sorted base amounts}` from invoice lines or priced lines."""
    out: dict[str, list[Decimal]] = {}
    for line in lines:
        if getattr(line, "kind", None) != "base":
            continue
        service = getattr(line, "service_code", None) or getattr(line, "service", None)
        service = getattr(service, "code", service)
        out.setdefault(str(service), []).append(Decimal(line.amount).quantize(CENT))
    return {key: sorted(value) for key, value in out.items()}


def _drafted(tenant) -> dict[str, list[Decimal]]:
    with tenant_ctx(tenant):
        invoice = billing_models.Invoice.objects.order_by("-created_at").first()
        return _bases_by_service(invoice.lines.all())


def _one_time(tenant, account, kind="interim", **extra):
    body = {
        "account_id": str(account.id),
        "kind": kind,
        "period_start": FROM.isoformat(),
        "period_end": TO.isoformat(),
        "bill_date": TO.isoformat(),
        "due_days": 21,
    }
    body.update(extra)
    response = _post(billing_api.one_time_create, tenant, _clerk(tenant), body)
    assert response.status_code == 201, response.data
    return _drafted(tenant)


# ── the rule itself (no database) ───────────────────────────────────────────
def test_cut_groups__only_the_repriced_service_is_cut():
    groups = backbill.cut_groups(
        ["water", "electric"], common_cuts=set(), service_cuts={"water": {CHANGE}}
    )
    assert groups == ((("electric",), ()), (("water",), (CHANGE,)))


def test_cut_groups__nothing_changed_or_everything_changed_is_the_identity():
    assert backbill.cut_groups(["water", "electric"], common_cuts=set(), service_cuts={}) == (
        (None, ()),
    )
    both = {"water": {CHANGE}, "electric": {CHANGE}}
    assert backbill.cut_groups(["water", "electric"], common_cuts=set(), service_cuts=both) == (
        (None, (CHANGE,)),
    )


def test_cut_groups__a_tariff_version_cut_still_cuts_every_service():
    version_day = date(2026, 11, 10)
    groups = backbill.cut_groups(
        ["water", "electric"], common_cuts={version_day}, service_cuts={"water": {CHANGE}}
    )
    assert groups == ((("electric",), (version_day,)), (("water",), (CHANGE, version_day)))


def test_cut_groups__a_percent_of_service_travels_with_its_basis():
    groups = backbill.cut_groups(
        ["water", "sewer", "electric"],
        common_cuts=set(),
        service_cuts={"water": {CHANGE}},
        linked={"sewer": "water"},
    )
    assert groups == ((("electric",), ()), (("sewer", "water"), (CHANGE,)))


# ── the PO's case, through the doors a clerk uses ───────────────────────────
@requires_postgres
def test_interim_electric_is_12_00_and_water_is_4_13_plus_4_50(brazos, dana, a_monthly_cycle):
    """Interim 10/16–11/15: electric ONE line $12.00 (was $6.00 + $6.19 =
    $12.19); water 16/31 × 8 + 15/30 × 9 = $4.13 + $4.50 = $8.63."""
    with tenant_ctx(brazos):
        account, _unit = _two_service_account(brazos, dana)
    bases = _one_time(brazos, account)
    assert bases["electric"] == [ELECTRIC], bases
    assert bases["water"] == [Decimal("4.13"), Decimal("4.50")], bases
    assert sum(bases["water"]) == Decimal("8.63")


@requires_postgres
def test_interim_with_nothing_changed_inside_is_not_cut(brazos, dana, a_monthly_cycle):
    """Identity: 11/01–11/15, wholly after the change (nothing changes inside)
    — one line per service, 15/30 of each: water $4.50, electric $6.00,
    exactly as before the ruling."""
    with tenant_ctx(brazos):
        account, _unit = _two_service_account(brazos, dana)
    bases = _one_time(brazos, account, period_start="2026-11-01")
    assert bases == {"electric": [Decimal("6.00")], "water": [Decimal("4.50")]}, bases


@requires_postgres
def test_catch_up_electric_is_one_line_and_water_is_split(brazos, dana, a_monthly_cycle):
    """Catch-up over the stated sub-period 10/16–11/15 (each part over the
    sub-period's 31 days): water 16/31 × 8 + 15/31 × 9 = $4.13 + $4.35; electric
    ONE line of $12.00 (it was two, $5.81 + $6.19)."""
    with tenant_ctx(brazos):
        account, _unit = _two_service_account(brazos, dana)
    bases = _one_time(
        brazos,
        account,
        kind="backbill",
        sub_periods=[{"period_start": FROM.isoformat(), "period_end": TO.isoformat()}],
        reason_code="BILLERR",
        bill_date="2026-12-05",
    )
    assert bases["electric"] == [ELECTRIC], bases
    assert bases["water"] == [Decimal("4.13"), Decimal("4.35")], bases


@requires_postgres
def test_bulk_run_split_prices_electric_12_00_and_water_split(brazos, dana):
    """The bulk run: `prepare_run` attaches BR-RAT-114's split for the clerk's
    *split at the change* answer and `price_account` prices it — the pair the
    run's Calculate uses. Cycle 10/16–11/15 (31 days, the cycle's own
    denominator): electric ONE line $12.00 (was 16/31 × 12 + 15/31 × 12 =
    $6.19 + $5.81); water 16/31 × 8 + 15/31 × 9 = $4.13 + $4.35."""
    from apps.billing import runs

    with tenant_ctx(brazos):
        cycle = metering_models.Cycle.objects.create(
            tenant=brazos,
            code="C-9012",
            start_day=FROM.day,
            days_to_complete=(TO - FROM).days + 1,
            bill_day=16,
            due_days=21,
        )
        account, _unit = _two_service_account(brazos, dana, cycle=cycle)
        prepared = runs.prepare_run(
            cycle_id=cycle.id, period_start=FROM, period_end=TO, service_date=TO
        )
        ready = [data for data in prepared.ready if data.account_no == account.account_no]
        assert ready, (prepared.blocked, getattr(prepared, "findings", None))
        data = ready[0]
        assert data.split_segments, "the bulk run attached no split for a mid-period price change"
        priced = runs.price_account(data)
    bases = _bases_by_service(priced.priced.lines)
    assert bases["electric"] == [ELECTRIC], bases
    assert bases["water"] == [Decimal("4.13"), Decimal("4.35")], bases

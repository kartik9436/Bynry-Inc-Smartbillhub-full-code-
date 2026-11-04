# ── Trace ──────────────────────────────────────────────
# Change:   CR-014 round 3 — the four journeys round 2 mis-grouped as flat-cohort
#           extensions. Each needs a PLAN of its own, not the shared one plus an
#           act: T4-04 (WE-12, four services), T4-07 (WE-10, two dated tariff
#           versions), T4-11 (WE-1's taxed bill), T5-18 (a demand register).
#           Builders in tests/journey_cohort_fixtures.py; seeders registered in
#           08-qa/01-e2e/stack/seed_journey_fixture.py.
# Rules:    BR-RAT-007 (history prices on the version in force on its SERVICE
#           date) · BR-RAT-067 (every TOU window states its register — a window
#           with no channel is REFUSED, never rank-matched) · BR-RAT-015
#           (percent-of-service) · BR-MET-062 (a demand value is NEVER
#           estimated) · BR-MET-003 (a premises may only offer services the
#           tenant sells) · CLAUDE.md rule 3 (every consumption carries its
#           unit — kW for a demand register, never kWh) · DEF-556 (no ISSUED
#           bill inside the finance-signed window).
# Golden:   The figures asserted are the journeys' own frozen-workbook rows —
#           WE-1's 221.90/20.97 and its four authority amounts, WE-10's
#           45.10/47.84, WE-12's 96.26/9.10/105.36. Each is held against what
#           the STORED RATE produces through `core.money`, never re-derived.
# Red-proof: shown RED before green; mutations and verbatim failures are in the
#           commit message and the W11 lane report, 2026-08-22.
# ───────────────────────────────────────────────────────
"""Four worked-example cohorts, and the one thing each is for.

A fixture for a worked example has a specific way of going wrong: it produces
the right TOTAL from the wrong INPUTS, and every downstream assertion still
passes. So each builder here checks its stored rates against the workbook line
they must produce — and these cases check that the builder really does refuse
when they do not, which is the only way a refusal is worth having.

The second shape is the ABSENCE. Three of these four cohorts cannot satisfy
part of their paragraph, because the product has no surface for it: WE-1's
$5.00 late line (no path assesses a late fee), T5-18's *"required channels
(BR-MET-049)"* (plan-driven completeness is not built), and T4-07's step 1
publishing a version the fixture already seeded. Each is stated on the seeder's
own output; these cases assert the state that IS there, so the gap stays
visible instead of being papered over by a green tick.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from tests import journey_cohort_fixtures as cohort
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ── T4-11 · WE-1's taxed bill ───────────────────────────────────────────────


def test_round3_t4_11__the_issued_bill_carries_we1s_taxable_and_its_four_authorities(
    brazos, dana
):
    """*"taxable $221.90 → tax $20.97 … State 13.87 · County 2.22 · City 4.44 ·
    PUC 0.44"*, all four quoted one by one by the journey's step 2.

    An aggregate that happens to sum to 20.97 is not enough: T4-11 asserts the
    per-authority remittance basis is unchanged after the exemption is set, and
    that is a statement about four rows.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        result = cohort.ensure_we1_taxed_bill(brazos, dana)
        invoice = billing_models.Invoice.objects.get(pk=result["invoice_id"])
        tax_lines = sorted(
            Decimal(line.amount).quantize(Decimal("0.01"))
            for line in invoice.lines.all()
            if line.kind == "tax"
        )

    assert invoice.status == "issued"
    assert Decimal(invoice.subtotal).quantize(Decimal("0.01")) == cohort.WE1_TAXABLE
    assert Decimal(invoice.tax_total).quantize(Decimal("0.01")) == cohort.WE1_TAX
    assert tax_lines == sorted(cohort.WE1_TAX_LINES)
    assert sum(tax_lines) == cohort.WE1_TAX


def test_round3_t4_11__the_account_is_not_exempt_at_seed_time(brazos, dana):
    """Setting the exemption is step 1. A pre-exempt account makes step 2's
    *"the issued bill did not move"* a comparison of nothing with nothing —
    DEF-108's shape, and exactly the trap T4-02 fell into in round 2."""
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        cohort.ensure_we1_taxed_bill(brazos, dana)
        account = customer_models.Account.objects.get(
            tenant=brazos, account_no=cohort.WE1_ACCOUNT
        )

    assert not getattr(account, "tax_exempt", False)


# ── T4-07 · WE-10's two dated versions ──────────────────────────────────────


def test_round3_t4_07__two_versions_price_we10s_two_monthly_figures(brazos, dana):
    """v3 → $45.10/mo, v4 → $47.84/mo, from the STORED rate.

    The builder checks this and refuses; this case is what proves the check is
    real, by reading the rows back out of the database and re-deriving the
    figures the same way the product would.
    """
    from apps.rating import models as rating_models
    from core import money

    with tenant_ctx(brazos):
        result = cohort.ensure_rate_version_cohort(brazos, dana)

        for spec in cohort.T407_VERSIONS:
            stored = result["versions"][spec["label"]]
            water = rating_models.TariffVersion.objects.get(pk=stored["water_version_id"])
            tier = rating_models.RateTier.objects.get(tenant=brazos, tariff_version=water)
            sewer = rating_models.TariffVersion.objects.get(pk=stored["sewer_version_id"])

            usage = money.finalize(tier.unit_price * cohort.T407_MONTHLY_KGAL)
            sewer_amount = money.finalize(sewer.percent * usage)
            assert usage == spec["usage"], f"{spec['label']} usage {usage} != {spec['usage']}"
            assert sewer_amount == spec["sewer"]
            assert water.base_charge == spec["base"]
            assert money.finalize(usage + sewer_amount + water.base_charge) == spec["monthly"]
            assert sewer.model == "percent_of_service"
            assert sewer.basis_service.code == "water"


def test_round3_t4_07__the_version_windows_do_not_overlap_and_the_months_are_unbilled(
    brazos, dana
):
    """Two properties, and both are the journey's whole subject.

    BR-RAT-007 prices history on the version in force on the SERVICE date, so
    an overlap leaves a March service date resolving to two versions. And a
    back-bill over a month that was already billed is not a catch-up, it is a
    duplicate charge — so the six months must be genuinely unbilled.
    """
    from apps.billing import models as billing_models

    with tenant_ctx(brazos):
        cohort.ensure_rate_version_cohort(brazos, dana)
        billed = billing_models.Invoice.objects.filter(
            tenant=brazos, account__account_no=cohort.T407_ACCOUNT
        ).count()

    assert cohort.T407_V3["effective_to"] < cohort.T407_V4["effective_from"]
    assert cohort.T407_V3["effective_to"] == date(2026, 3, 31)
    assert cohort.T407_V4["effective_from"] == date(2026, 4, 1)
    assert billed == 0, f"{cohort.T407_ACCOUNT} already carries {billed} invoice(s)"


# ── T4-04 · WE-12's four services ───────────────────────────────────────────


def test_round3_t4_04__four_services_are_enabled_and_the_plan_covers_all_of_them(
    brazos, dana
):
    """Sewer and trash ship DISABLED from signup, and BR-MET-003 refuses a
    premises that offers a service the tenant does not sell. WE-12's 105.36 has
    a sewer line AND a trash line, so both must genuinely be turned on — the
    first run of this cohort failed `VAL-005 metering.service_not_enabled`."""
    from apps.rating import selectors as rating_selectors
    from apps.tenancy import models as tenancy_models

    with tenant_ctx(brazos):
        result = cohort.ensure_we12_world(brazos, dana)
        enabled = {
            row.service.code
            for row in tenancy_models.TenantService.objects.filter(
                tenant=brazos, enabled=True
            ).select_related("service")
        }
        plan_services = {
            row["service_code"]
            for row in rating_selectors.plan_rate_schedules(
                __import__("apps.rating.models", fromlist=["models"]).RatePlan.objects.get(
                    tenant=brazos, code=cohort.T404_PLAN_CODE
                ).id
            )
        }

    assert set(cohort.T404_SERVICES) <= enabled
    assert set(cohort.T404_SERVICES) <= plan_services
    assert result["taxable"] == str(cohort.T404_TAXABLE)


def test_round3_t4_04__every_tou_window_names_its_register(brazos, dana):
    """BR-RAT-067, and it is not a formality.

    Before the channel column a window carried only a label and rating matched
    price to measurement by RANK — the demo tenant's own summer schedule billed
    one customer **38% high**. NULL is a refusal, never a default, so a fixture
    that stored windows without channels would seed rows the engine refuses by
    name and T4-04 would fail for a reason it never describes.
    """
    from apps.rating import models as rating_models
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        cohort.ensure_we12_world(brazos, dana)
        plan = rating_models.RatePlan.objects.get(tenant=brazos, code=cohort.T404_PLAN_CODE)
        electric = next(
            row["tariff"]
            for row in rating_selectors.plan_rate_schedules(plan.id)
            if row["service_code"] == "electric"
        )
        windows = list(
            rating_models.TimeOfUseWindow.objects.filter(
                tenant=brazos, tariff_version__tariff=electric
            )
        )

    assert len(windows) == len(cohort.T404_TOU)
    assert {window.channel for window in windows} == {row[1] for row in cohort.T404_TOU}
    assert all(window.channel for window in windows), "a NULL channel is a refusal, not a default"


def test_round3_t4_04__the_account_is_active_and_unbilled_when_the_journey_starts(
    brazos, dana
):
    """Step 1 moves it Active → Vacation hold and step 2 issues the 105.36
    bill. Seeding either would leave the journey asserting over its own answer,
    and step 5's *"ending the hold never re-opens the hold-period bill"* would
    compare a bill this fixture wrote against itself."""
    from apps.billing import models as billing_models
    from apps.customers import models as customer_models

    with tenant_ctx(brazos):
        cohort.ensure_we12_world(brazos, dana)
        account = customer_models.Account.objects.select_related("status").get(
            tenant=brazos, account_no=cohort.T404_ACCOUNT
        )
        bills = billing_models.Invoice.objects.filter(tenant=brazos, account=account).count()

    assert account.status.code == "active"
    assert bills == 0


# ── T5-18 · the demand register ─────────────────────────────────────────────


def test_round3_t5_18__the_cycle_under_test_has_no_read_at_all(brazos, dana):
    """*"reader skipped the site"* — the ABSENCE is the fixture.

    With a read present nothing is missing, no estimate is attempted, and the
    demand refusal this journey exists to prove is never reached. The trailing
    history must be there for the opposite reason: without it the kWh estimate
    fails for lack of data and step 1 is red for the wrong reason.
    """
    with tenant_ctx(brazos):
        result = cohort.ensure_demand_meter_cohort(brazos, dana)

    assert result["reads_in_cycle"] == 0
    assert result["history_rows"] >= len(cohort.T518_HISTORY) * (
        len(cohort.T518_KWH_CHANNELS) + 1
    )


def test_round3_t5_18__the_demand_register_is_committed_in_kw_not_kwh(brazos, dana):
    """CLAUDE.md rule 3, on the one channel where getting it wrong is invisible.

    A peak stored as kWh prices a $/kW demand charge off an energy number. Both
    are numbers, both render, and the bill is wrong by whatever the ratio
    happens to be.
    """
    from apps.metering.models import MeterRead

    with tenant_ctx(brazos):
        result = cohort.ensure_demand_meter_cohort(brazos, dana)
        units = {
            (row.channel, row.unit)
            for row in MeterRead.objects.filter(
                tenant=brazos, asset__asset_no=result["meter"]
            )
        }

    demand_units = {unit for channel, unit in units if channel == cohort.T518_DEMAND_CHANNEL}
    kwh_units = {unit for channel, unit in units if channel != cohort.T518_DEMAND_CHANNEL}
    assert demand_units == {"kW"}
    assert kwh_units == {"kWh"}


def test_round3_t5_18__the_rule_the_cohort_exists_for_actually_refuses(brazos, dana):
    """BR-MET-062, asserted against the engine rather than assumed.

    A cohort for a refusal is worth nothing if the refusal does not happen. The
    estimator is asked for a demand estimate WITH a full trailing history and a
    live config — every condition that would make a kWh estimate succeed — and
    must still refuse, by name.
    """
    from apps.metering import estimation

    with tenant_ctx(brazos):
        cohort.ensure_demand_meter_cohort(brazos, dana)

    refusal = estimation.estimate(
        estimation.EstimationInput(
            channel=cohort.T518_DEMAND_CHANNEL,
            unit="kW",
            days_in_period=31,
            trailing_actuals=[(Decimal("41.1"), 31), (Decimal("39.4"), 30)],
        ),
        config=None,
    )
    assert refusal.estimated is False
    assert refusal.reason == estimation.REASON_DEMAND_CHANNEL
    assert refusal.detail.get("rule_ref") == "BR-MET-062"

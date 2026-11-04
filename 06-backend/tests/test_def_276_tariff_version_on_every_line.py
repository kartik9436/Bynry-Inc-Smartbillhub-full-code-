# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-029 (stage 6 — the sole InvoiceLine constructor) ·
#           US-RAT-012 (the engine that priced the line)
#           Screens: S31 (the preview) · RAT-02 Versions tab (the reader that
#           counts bills per version and today counts nothing)
# Rules:    BR-RAT-007 (a bill prices on the version IN FORCE at the service
#           date — and must re-price to the identical figure for seven years) ·
#           BR-RAT-017 (rate history is an audit artefact) · CR-013 part 1
#           downstream, verbatim: *"Run bills cites the version id per line"*
# Defect:   DEF-276 — every invoice line stored `tariff_version_id` as NULL
# Tests:    this file IS the test the defect's own prevention column asked for
# ───────────────────────────────────────────────────────
"""DEF-276 — the provenance column that was never written.

**THE DEFECT.** `invoice_lines.tariff_version_id` has existed since the billing
slice and the ONLY code that constructs an `InvoiceLine`
(`apps/billing/stages/assemble_document.py`) never set it. Four readers join
through it — `reporting.py:404`, `bulk_corrections.py:272`/`:290`,
`selectors.py:409-413`/`:439` — and each got an empty result, which is a valid
answer to a query and an invalid answer to the question.

**WHY NOTHING WENT RED.** A NULL column reads as *"no rows matched"*, never as
*"this is broken"*. No test asserted the field is populated because no test
asserts a NEGATIVE, and the four readers each look correct in isolation. It is
hard-won law 2 inverted: not built-but-not-wired, but wired-to-nothing.

**WHAT THIS FILE ASSERTS, AND WHY IT IS NOT "SET A COLUMN".** The version id
must be the one the ENGINE ACTUALLY PRICED WITH, carried down the pricing chain
with the money — not looked up again at assembly from the tariff and the service
date. A second lookup would agree with the engine almost always and would
disagree exactly when it matters (a version window edited between pricing and
assembly, a service date read from a different field), and a provenance column
that can disagree with the price it describes is not provenance. So the test
seeds a plan with **two** versions of one schedule, prices a June bill on the
June version while a July version already exists, and asserts the line names the
version that produced the figure.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.billing.stages import assemble_document as stage6
from apps.billing.stages import measure_consumption as stage2
from apps.billing.stages import resolve_subscription as stage1
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx
from tests.test_w3_billing_models import a_run, an_account

pytestmark = pytest.mark.django_db

PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
SERVICE_DATE = date(2026, 6, 30)


def a_two_version_schedule(tenant, *, marker="def276"):
    """One electric schedule with a JUNE version and a JULY version.

    The second version exists so the assertion below cannot be satisfied by
    "any version of this tariff" — the line must name the one in force on the
    SERVICE date (BR-RAT-007), which is the whole of the seven-year
    reproducibility promise.
    """
    electric = tenancy_models.Service.objects.get(code="electric")
    plan = rating_models.RatePlan.objects.create(
        tenant=tenant, code=f"PL-{marker}", name=f"{marker} plan", status="published"
    )
    rating_models.PlanService.objects.create(
        tenant=tenant, rate_plan=plan, service=electric, base_charge=Decimal("18.50")
    )
    tariff = rating_models.Tariff.objects.create(
        tenant=tenant, service=electric, name=f"{marker} schedule"
    )
    june = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="flat",
        base_charge=Decimal("0"),
        currency="USD",
        uom="kWh",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 7, 1),
    )
    rating_models.RateTier.objects.create(
        tenant=tenant,
        tariff_version=june,
        seq=1,
        from_qty=Decimal("0"),
        to_qty=None,
        unit_price=Decimal("0.12"),
    )
    july = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="flat",
        base_charge=Decimal("0"),
        currency="USD",
        uom="kWh",
        effective_from=date(2026, 7, 1),
    )
    rating_models.RateTier.objects.create(
        tenant=tenant,
        tariff_version=july,
        seq=1,
        from_qty=Decimal("0"),
        to_qty=None,
        unit_price=Decimal("0.19"),
    )
    rating_models.PlanRateSchedule.objects.create(
        tenant=tenant, rate_plan=plan, service=electric, tariff=tariff
    )
    return plan, june, july


def a_bill(tenant, account, run, plan):
    """The REAL chain — gather, stage 1, stage 2, rating's priced pass, stage 6.

    Deliberately not a hand-built `TariffConfig`: the defect is about what
    survives the journey from `rating.selectors.pricing_inputs` to a row in
    `invoice_lines`, and a fixture assembled at the engine's doorstep proves
    nothing about that journey (the DEF-154 lesson, restated).
    """
    tariffs = gather._tariffs_for_plan(str(plan.id), None, SERVICE_DATE, None)
    data = AccountBillingData(
        account_id=str(account.id),
        account_no=account.account_no,
        behavior_class=stage1.CLASS_BILLABLE,
        currency="USD",
        tax_exempt=False,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        cycle_days=30,
        service_days=30,
        rate_plan_id=str(plan.id),
        rate_plan_name=plan.name,
        rate_plan_version=plan.version,
        tariffs=tariffs,
        readings=(
            ServiceReading(
                service_code="electric",
                consumption=rating_seam.Quantity(amount=Decimal("684"), unit="kWh"),
            ),
        ),
        taxes=(rating_seam.TaxRule(code="STATE+LOCAL", rate=Decimal("0.0825")),),
        snapshot={"customer_name": "Sarah Chen"},
    )
    subscription = stage1.resolve_subscription(data)
    usage = stage2.measure_consumption(subscription, data)
    measured = usage.measured[0]
    priced = rating_seam.price_period(
        tariff=measured.tariff,
        consumption=measured.consumption,
        period=subscription.period,
        account=rating_seam.AccountContext(
            currency=subscription.currency, tax_exempt=subscription.tax_exempt
        ),
        taxes=subscription.taxes,
    )
    return stage6.assemble_document(
        usage=usage,
        priced=priced,
        tenant_id=tenant.id,
        account_id=account.id,
        bill_run=run,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )


def test_def_276_tc1__every_priced_line_carries_a_tariff_version_id(brazos, dana):
    """The bare assertion the defect asked for: no priced line is NULL.

    Tax and fee lines are excluded BY NAME rather than by silence — a tax is not
    priced from a tariff version and stamping one on it would be a false claim,
    which is the same class of error as leaving the usage line blank.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        plan, june, _july = a_two_version_schedule(brazos)

        invoice = a_bill(brazos, account, run, plan)

        priced_lines = [
            line
            for line in invoice.lines.all()
            if line.kind in ("usage", "base", "minimum_adjustment")
        ]
        assert priced_lines, "the fixture must produce at least one priced line"
        assert all(line.tariff_version_id is not None for line in priced_lines), (
            "DEF-276: a priced invoice line with no tariff_version_id cannot be "
            "re-priced from the version that produced it, so BR-RAT-007's "
            "seven-year reproducibility promise is unkeepable for that bill."
        )
        assert all(str(line.tariff_version_id) == str(june.id) for line in priced_lines)


def test_def_276_tc2__the_version_named_is_the_one_in_force_not_the_newest(brazos, dana):
    """BR-RAT-007 — a June bill names June's version while July's already exists.

    This is the assertion a lookup-at-assembly implementation fails: the newest
    version of this tariff is July's, and the money on the line is June's.
    """
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        plan, june, july = a_two_version_schedule(brazos)

        invoice = a_bill(brazos, account, run, plan)
        usage = invoice.lines.get(kind="usage")

        assert str(usage.tariff_version_id) == str(june.id)
        assert str(usage.tariff_version_id) != str(july.id)
        # 684 kWh x 0.12 = 82.08 — June's price. July's 0.19 would be 129.96.
        assert usage.amount == Decimal("82.080000")


def test_def_276_tc3__a_tax_line_names_no_tariff_version(brazos, dana):
    """The negative half. A tax is not priced from a rate schedule, so a version
    id on a tax line would be a claim nothing supports — and BR-BIL-069's
    `tax_id` is that line's provenance instead."""
    with tenant_ctx(brazos):
        account = an_account(dana, brazos)
        run = a_run(brazos)
        plan, _june, _july = a_two_version_schedule(brazos)

        invoice = a_bill(brazos, account, run, plan)

        for line in invoice.lines.filter(kind="tax"):
            assert line.tariff_version_id is None

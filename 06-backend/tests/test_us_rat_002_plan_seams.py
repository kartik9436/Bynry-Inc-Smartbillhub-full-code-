# ── Trace ──────────────────────────────────────────────
# Story:    US-RAT-002 (the plan as a bundle — plan-as-bundle D1–D9)
#           Screens: S10 · S31.2 (billing's preview reads these)
# Rules:    BR-RAT-025 (plan-as-bundle) · BR-RAT-036 (tax forms; percent,
#           flat-per-bill and per-unit) · BR-RAT-007 (reprice on the service
#           date) · B4.2 (tax base) · CLAUDE.md rule 2 (money as Decimal)
# ───────────────────────────────────────────────────────
"""The two selectors billing's gather step reads a plan through.

A plan is a BUNDLE. `plan_rate_schedules` is that sentence made checkable: one
plan in, one tariff per service out. Before the PO's ruling of 2026-08-11 a
unit held a single rate schedule and this function had nothing to say; now it
is how a house on three services gets three sets of prices from one plan.

`plan_tax_rules` carries the other 2026-08-11 ruling — *"Tax rates are for
bill not for service"* — so the rate hangs off the plan and its jurisdictions.

TWO ABSENCES ARE ASSERTED HERE, and both are the point:
  * a jurisdiction attached with NO percent rate anywhere is SKIPPED, not
    defaulted to zero. A zero rate is a claim that the authority charges
    nothing; an absent rule claims nothing at all.
  * per-unit taxes are SKIPPED, because the rating seam carries no usage.
    Approximating $0.25/kgal as a percent would put a wrong number on a real
    bill.

⚠ FLAT-PER-BILL NO LONGER SKIPS (2026-08-18, DEF-273). The PO's ruled Texas
table carries a **PUC Regulatory Fee of $0.85 flat per bill on electric**, so
`TaxRule` gained `flat_amount` and the engine bills it as itself. What is
asserted below is now the narrower and still-true statement: a tax whose `kind`
this resolver does not recognise is skipped rather than guessed at. The flat
form's own worked figure lives in tests/test_def_273_tax_conditions.py.
"""

from decimal import Decimal

import pytest

from apps.rating import models as rating_models
from apps.rating import selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def a_jurisdiction(tenant, name="TX State"):
    return rating_models.TaxJurisdiction.objects.create(tenant=tenant, name=name)


def test_us_rat_002_tc8__a_plan_resolves_to_one_tariff_per_service(brazos, dana):
    """BR-RAT-025 — the bundle, made concrete.

    A house on electric + water is on ONE plan; billing needs both sets of
    prices to bill it. This is the function that turns one into two.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard", services=("electric", "water"))

        rows = selectors.plan_rate_schedules(plan.id)

        assert [row["service_code"] for row in rows] == ["electric", "water"]
        # The TARIFF ROW, not a dict of prices: the caller must resolve the
        # version in force at the SERVICE date (BR-RAT-007), and a flattened
        # dict would have to pick a version here — the seven-year
        # reproducibility mistake.
        assert all(hasattr(row["tariff"], "id") for row in rows)


def test_us_rat_002_tc8b__an_unknown_or_malformed_plan_yields_nothing(brazos, dana):
    """A bad id returns [], and the caller turns that into a named exception.

    Raising here would make every caller wrap it; returning a plausible default
    would bill someone on prices that do not exist. Empty is the honest answer
    and billing's gather step already refuses on it.
    """
    with tenant_ctx(brazos):
        assert selectors.plan_rate_schedules("not-a-uuid") == []
        assert selectors.plan_rate_schedules("0199c0de-0000-7000-8000-00000000dead") == []


def test_us_rat_002_tc9__a_plan_tax_rule_uses_the_jurisdiction_rate(brazos, dana):
    """r5 #11 / D8 — no override means the jurisdiction's own percent rate."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        jurisdiction = a_jurisdiction(brazos)
        rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="TX State sales",
            kind="percent",
            rate=Decimal("0.062500"),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )

        rules = selectors.plan_tax_rules(plan.id)

        assert len(rules) == 1
        assert rules[0]["code"] == "TX State"
        assert rules[0]["rate"] == Decimal("0.062500")  # a fraction, Decimal (rule 2)


def test_us_rat_002_tc9b__an_override_wins_and_is_not_merged(brazos, dana):
    """A tenant who overrode a rate meant to override it.

    Averaging, summing or otherwise combining the two would produce a number
    neither the tenant nor the jurisdiction chose.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        jurisdiction = a_jurisdiction(brazos)
        rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="TX State sales",
            kind="percent",
            rate=Decimal("0.062500"),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos,
            rate_plan=plan,
            jurisdiction=jurisdiction,
            rate_override=Decimal("0.040000"),
        )

        rules = selectors.plan_tax_rules(plan.id)
        assert rules[0]["rate"] == Decimal("0.040000")  # the override, alone


def test_us_rat_002_tc9c__a_jurisdiction_with_no_percent_rate_is_skipped_not_zeroed(brazos, dana):
    """THE ABSENCE THAT MATTERS.

    A jurisdiction attached to the plan with no percent tax anywhere yields NO
    rule. Defaulting to 0.00 would put a line on the bill asserting that this
    authority charges nothing — a claim, and a false one. An absent rule claims
    nothing, and the missing tax is visible on the preview, which is where it
    should be visible.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        jurisdiction = a_jurisdiction(brazos, name="Travis County")
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )

        assert selectors.plan_tax_rules(plan.id) == []


def test_us_rat_002_tc9d__a_tax_of_an_unrecognised_kind_is_skipped_not_approximated(
    brazos, dana
):
    """BR-RAT-036 names three forms and this row states none of them.

    `kind="flat"` is not `flat_per_bill`, not `percent` and not `per_unit` — it
    is a value nothing in rating's own `TAX_KINDS` defines, which is what a
    mis-typed import or a half-migrated row looks like. It is SKIPPED and named:
    charging $2.50 by guessing which form was meant would put a wrong number on
    a real customer's bill, and it would look right.

    ⚠ AMENDED 2026-08-18 (DEF-273): until today this case read as "flat taxes
    are skipped", and flat-per-bill now BILLS (the PO's ruled $0.85 PUC fee).
    The row is left spelled `flat` deliberately, because the assertion it can
    still make honestly is about an unrecognised kind rather than about a form
    the product has since built.
    """
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        jurisdiction = a_jurisdiction(brazos, name="City franchise")
        rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="City flat fee",
            kind="flat",
            flat_amount=Decimal("2.500000"),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )

        assert selectors.plan_tax_rules(plan.id) == []


def test_us_rat_002_tc9e__several_jurisdictions_come_back_in_a_stable_order(brazos, dana):
    """A bill shows one tax line per authority (US-RAT-013 §4), so the order
    they arrive in is the order they print. Stable, or the same bill reprints
    differently."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard")
        for name, rate in (("TX State", "0.062500"), ("Travis County", "0.010000")):
            jurisdiction = a_jurisdiction(brazos, name=name)
            rating_models.Tax.objects.create(
                tenant=brazos,
                jurisdiction=jurisdiction,
                name=f"{name} tax",
                kind="percent",
                rate=Decimal(rate),
            )
            rating_models.PlanTaxRule.objects.create(
                tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
            )

        codes = [rule["code"] for rule in selectors.plan_tax_rules(plan.id)]
        assert codes == ["TX State", "Travis County"]  # ordered by name, deterministic
        assert codes == [rule["code"] for rule in selectors.plan_tax_rules(plan.id)]


def test_us_rat_002_tc10__billings_gather_step_runs_end_to_end_against_these(brazos, dana):
    """THE PROOF THE GATHER STEP'S OWN TESTS COULD NOT GIVE.

    `tests/test_us_bil_002_gather.py` publishes a FAKE seam resolver, so it
    proves the gather's logic and its refusals — not that rating's real
    selectors return the shapes it expects. Until this test, the two halves
    agreed only in my head, and that is precisely the gap hard-won law 1 is
    about: a docstring saying "reads through the seam" is not evidence the seam
    fits.

    So this drives the REAL selectors, through the REAL resolver, against real
    rows. If either function's shape drifts from what billing reads, this fails
    here rather than at the first bill run.
    """
    from datetime import date

    from apps.billing import gather, runs

    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Residential Standard", services=("electric",))
        jurisdiction = a_jurisdiction(brazos)
        rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="TX State sales",
            kind="percent",
            rate=Decimal("0.082500"),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )
        # A version in force on the service date — BR-RAT-007's pivot. Built
        # the way rating really stores a flat rate: the price is NOT a column
        # on the version, it is ONE 0→∞ tier (BR-RAT-032), and `pricing_inputs`
        # is what unwraps that back into a `unit_price` for the engine. An
        # earlier cut of this fixture invented `version_no`/`unit_price`
        # columns, which is how the whole seam defect surfaced.
        tariff = selectors.plan_rate_schedules(plan.id)[0]["tariff"]
        version = rating_models.TariffVersion.objects.create(
            tenant=brazos,
            tariff=tariff,
            model="flat",
            base_charge=Decimal("18.500000"),
            uom="kWh",
            currency="USD",
            effective_from=date(2026, 1, 1),
        )
        rating_models.RateTier.objects.create(
            tenant=brazos,
            tariff_version=version,
            seq=1,
            from_qty=Decimal("0"),
            to_qty=None,  # ∞ — the single block a flat rate is stored as
            unit_price=Decimal("0.120000"),
        )
        # Electric is BANDED: a version stating no size axis prices no size
        # (`DEF-2816`, the PO's reading), so R3 refuses the meter's band. The
        # axis is membership only, no price — the shared helper's own words.
        from tests.test_us_met_helpers import state_size_axis

        state_size_axis(version, "electric")
        # ⚠ `DEF-BIL-9025` — THE BASE LIVES ON THE CHARGE CODE (BR-RAT-088;
        # PO: *"we will never take default value from plan $8.0 - that is
        # retired"*). The `$18.50` on the version above is no longer read, so
        # the same figure is declared where the product reads it: one `is_base`
        # electric code, one price for every size (CR-156: an All sizes row).
        from apps.rating import charge_prices
        from apps.rating.constants import ALL_SIZES, PRICE_HISTORY_EPOCH
        from apps.tenancy import models as tenancy_models

        base_code = rating_models.Charge.objects.create(
            tenant=brazos,
            code="BASE-E",
            name="Electric base",
            service=tenancy_models.Service.objects.get(code="electric"),
            is_base=True,
            charge_type="recurring",
            amount_rule="flat",
        )
        charge_prices.save_prices(
            base_code,
            {(ALL_SIZES, None): Decimal("18.50")},
            effective_from=PRICE_HISTORY_EPOCH,
            effective_to=None,
        )
        from tests.base_code_naming import name_base_code

        name_base_code(brazos, base_code)  # DEF-RAT-9832 — unnamed bills $0.00

        premises = make_premises(dana, address_line="1901 Bluestem Ln")
        unit = make_unit(dana, premises["id"], label="Unit A", services=["electric"])
        # ⚠ `DEF-BIL-9025` — THE METER. Since the PO's 2026-09-30 ruling
        # (`BR-BIL-300` as amended, 31358c239: *"No asset means not in service,
        # even if the account took the service"*) a service point with nothing
        # on it is not in service, so this plan had no tariff in scope and the
        # gather refused before any shape was read. An electric meter is what a
        # real electric customer has; the seam shapes asserted below are
        # unchanged.
        # Read, too: a meter never read states no multiplier (BR-MET-056), and
        # R3 takes its connection facts from a meter that has a reading.
        from tests.test_us_met_reads_helpers import a_meter, commit_read

        meter = a_meter(
            dana, asset_no="M-GATHER-E2E", unit_id=unit["id"], service="electric", uom="kWh"
        )
        from apps.metering import models as metering_models
        from tests.test_br_cus_068_master_bill import _cycle

        metering_models.ServicePoint.objects.filter(tenant=brazos, unit_id=unit["id"]).update(
            cycle=_cycle(brazos, "RAT002-TC10")
        )
        commit_read(dana, meter["id"], day="2026-06-01", value="100", unit="kWh")
        commit_read(
            dana,
            meter["id"],
            day="2026-06-30",
            value="400",
            unit="kWh",
            prior_value="100",
            consumption="300",
        )
        from apps.metering import services as metering_services

        metering_services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-01-01"}
        )

        from apps.customers import models as customer_models

        account = customer_models.Account.objects.create(
            tenant=brazos,
            unit_id=unit["id"],
            status=customer_models.AccountStatus.objects.filter(tenant=brazos).first(),
            account_type=customer_models.AccountType.objects.first(),
            account_no="A-GATHER-E2E",
        )

        data = gather.gather_account(
            account=account,
            service_date=date(2026, 6, 30),
            period_start=date(2026, 6, 1),
            period_end=date(2026, 6, 30),
            cycle_days=30,
            # The gather is handed the period's readings rather than fetching
            # them (its own docstring); the run reads them through
            # `runs.readings_for_account`, and so does this case now. With none,
            # R3 (on by default) sees no meter for electric and refuses.
            readings=runs.readings_for_account(
                account,
                period_start=date(2026, 6, 1),
                period_end=date(2026, 6, 30),
                scope_services=None,
            )[0],
        )

    assert data.account_no == "A-GATHER-E2E"
    assert data.rate_plan_name == "Residential Standard"
    assert len(data.tariffs) == 1
    assert data.tariffs[0].service == "electric"
    assert data.tariffs[0].model == "flat"
    assert data.tariffs[0].billed_unit == "kWh"  # rule 3 — a quantity carries its unit
    # The base, resolved through the seam from the CHARGE CODE that owns it
    # (BR-RAT-088) — the version's own column is retired and states nothing.
    assert data.tariffs[0].base_charge == Decimal("18.500000")
    assert data.tariffs[0].base_charge_code == "BASE-E"
    # The tier row, unwrapped by rating. Billing never learns that a flat rate
    # is stored as a tier — that is the module boundary working.
    assert data.tariffs[0].unit_price == Decimal("0.120000")
    assert data.tariffs[0].tiers == ()
    assert data.tariffs[0].multiplier == Decimal("1")  # metering owns it (PO 2026-08-11)
    assert len(data.taxes) == 1 and data.taxes[0].rate == Decimal("0.082500")
    assert data.currency == "USD"  # the tenant's, resolved through tenancy


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-002@6304a38 (EP-RAT-01 lead story — plan-as-bundle)
# generated: 2026-08-11 by Eng-Lead (W3 bill-run lane — unblocking the gather)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — selectors) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔
# exceptions: `plan_tax_rules` accepts a `service_date` it does not yet USE —
#         `taxes` carries no effective-dating columns, so there is nothing to
#         filter on. It is in the signature because BR-RAT-007's repricing
#         promise means a rate WILL have to be resolved at the service date
#         once those columns exist, and a caller written today should already
#         pass it rather than face a breaking change later. REPORTED so the
#         unused argument reads as deliberate rather than as a mistake ·
#         flat-per-bill and per-unit tax forms (BR-RAT-036) are SKIPPED, not
#         approximated — the seam's TaxRule carries a percent rate and nothing
#         else
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

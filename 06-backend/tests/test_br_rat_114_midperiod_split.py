# ── Trace ──────────────────────────────────────────────
# Rule:     BR-RAT-114 (AN ORDINARY BILL SPLITS AT A MID-PERIOD RATE OR PLAN
#           CHANGE — one bill, priced per sub-period, each sub-period at the
#           version in force; consumption evenly by day unless an actual read
#           dates the boundary; one line per sub-period per charge naming its
#           rate and dates)   PO ruling 2026-08-22, closing DEF-503 · DEF-504.
# Pin:      THE CONTRACT FIGURE, from the ruling verbatim ("Water at $2.00/kgal
#           until the 15th, then $2.20, 10 kgal spread evenly: split = $21.00"):
#           10 kgal evenly over a period whose change lands at its midpoint =
#           5 kgal @ 2.00 + 5 kgal @ 2.20 = $10.00 + $11.00 = **$21.00** —
#           never the single-version $20.00 or $22.00.
# Rules:    BR-RAT-007 (version in force at the SERVICE date) · BR-RAT-002
#           (tier thresholds scale with the prorated period) · B4.2 (ONE tax
#           pass over Σ(rounded taxable lines)) · B4.3 (day-weighted proration)
#           · BR-BIL-015 (a missing read stays a human decision) · BR-BIL-018
#           (the back-bill path, held to the SAME answer)
# Tests:    this file IS the BR-RAT-114 contract; tc1 was written first and
#           proved RED against the single-version behaviour (22.00 — the whole
#           period on the version at the run's service date) before any code.
# Impacts:  apps/billing/midperiod.py · apps/billing/runs.py (prepare/calculate)
#           · apps/billing/gather.py (plan override) · DEF-554 (carried lines'
#           version ids)
# ───────────────────────────────────────────────────────
"""BR-RAT-114: the ordinary cycle bill splits at a mid-period rate/plan change.

THE ONE ASSERTION THIS FILE EXISTS FOR is tc1's $21.00. Before BR-RAT-114 the
ordinary run gathered ONE tariff version at the run's service date and priced
the whole period on it (DEF-503), and stamped ONE plan for the whole period
(DEF-504) — so this exact fixture billed $22.00: plausible, footed, and wrong
by the full rate difference on every pre-boundary day.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import backbill, models as billing_models, runs
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    _smallest_ratified_band,
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)
from tests.test_us_met_reads_helpers import a_meter, commit_read

pytestmark = pytest.mark.django_db

# The PO's own example, on a 30-day June so the change lands at the MIDPOINT:
# $2.00/kgal through Jun 15, $2.20/kgal from Jun 16.
PERIOD_START = date(2026, 6, 1)
PERIOD_END = date(2026, 6, 30)
BOUNDARY = date(2026, 6, 16)  # first day of the NEW version's stretch
SERVICE_DATE = date(2026, 6, 30)  # the run's pivot — resolves the NEW version


def serve_the_ratified_size(tenant, version):
    """Put R3's SIZE AXIS on one schedule version — membership only, no money.

    ⚠ **WITHOUT THIS ROW THIS SUITE NEVER REACHES THE ARITHMETIC IT EXISTS TO
    PROVE.** `configured_sizes_for` reads a banded service's axis off
    `rate_size_rows`; with none, water's axis is `()` and `resolve_served_size`
    refuses the account at R3 BY NAME — *"connection size 'W-58' has no row on
    the rate schedule version …"* — before a single tier is priced. That is
    `DEF-2799`'s failure on the demo fixture, seeded there for the same reason.

    **The size comes from `BR-TEN-171` and never from a string typed here**, and
    from the SAME resolver `a_meter` uses for its own default — so the meter
    this suite fits and the schedule it binds cannot drift apart when the
    ratified list moves.

    `minimum_bill` is NULL on purpose: the model's own words are *"NULL = this
    size has no minimum bill … Absent is not zero"*, and a figure here would be
    money `BR-RAT-114` never signed. The tiers stay in the NULL "every size"
    group, which `resolve_tiers` documents as the schedule's default — so this
    restores R3 membership and changes no price.
    """
    band = _smallest_ratified_band("water")
    if band is None:  # pragma: no cover — water is banded in BR-TEN-171
        return
    rating_models.RateSizeRow.objects.create(
        tenant=tenant,
        tariff_version=version,
        size_class=band,
        minimum_bill=None,
        currency="USD",
    )


def state_the_water_base_as_zero(tenant):
    """`BR-RAT-088`'s owner of the base amount, stating that this suite's water
    service carries none.

    ORM-created rather than through `create_charge` because these fixtures hold
    no actor; `test_br_rat_120_size_refusal` declares its own the same way and
    for the same reason — *"so that the refusal it is actually testing … cannot
    be R4's missing-base refusal wearing the same exception."*
    """
    rating_models.Charge.objects.get_or_create(
        tenant=tenant,
        code="BASE-W-R114",
        defaults={
            "name": "Water base service",
            "charge_type": "recurring",
            "amount_rule": "flat",
            "amount": Decimal("0"),
            "service": tenancy_models.Service.objects.get(code="water"),
            "is_base": True,
        },
    )


def a_repricing_water_plan(tenant, *, name="Pin Water", old="2.000000", new="2.200000"):
    """One water schedule, single open tier, $2.00 → $2.20 effective Jun 16.

    Base charge STATED as zero, so the pin's $21.00 arrives with nothing added
    to the money: the two usage lines carry the whole bill.

    ⚠ **WHERE THAT ZERO IS STATED MOVED UNDER THIS FIXTURE, AND THAT IS WHY
    THESE SIX WENT RED (`DEF-RAT-5716`).** It used to be stated as the
    schedule version's `base_charge=0`, and two rulings retired that reading
    in turn: `BR-RAT-088` moved the base AMOUNT to the charge code, and
    `DEF-2830` (2026-08-31) then settled that a schedule's stored `0.00` reads
    as **NOT STATED** rather than as *the charge is nothing* — *"the opposite
    reading would give the standing charge away because somebody left a box
    alone"*. So R4 began refusing this fixture's account with *"Nobody has
    stated this service's base charge"*, and the refusal landed BEFORE any
    tier was priced. **The arithmetic never changed; only where a utility
    writes its zero did.**

    The zero is therefore declared where the product now reads it — a `water`
    charge code marked `is_base`, stating `$0.00` — which is the same thing
    `test_br_rat_120_size_refusal` does and for the same reason: *"so that the
    refusal it is actually testing … cannot be R4's missing-base refusal
    wearing the same exception."* This suite is about the mid-period SPLIT.
    The signed figure does not move: a base of `$0.00` adds nothing, and TC1
    still asserts `$21.00` from two usage lines of `$10.00` and `$11.00`.
    """
    plan = make_plan(tenant, name=name, services=("water",))
    state_the_water_base_as_zero(tenant)
    from apps.rating import selectors as rating_selectors

    versions = {}
    for row in rating_selectors.plan_rate_schedules(plan.id):
        for label, price, start, end in (
            ("old", old, date(2025, 1, 1), BOUNDARY - date.resolution),
            ("new", new, BOUNDARY, None),
        ):
            version = rating_models.TariffVersion.objects.create(
                tenant=tenant,
                tariff=row["tariff"],
                model="tiered",
                base_charge=Decimal("0"),
                uom="kgal",
                currency="USD",
                effective_from=start,
                effective_to=end,
            )
            rating_models.RateTier.objects.create(
                tenant=tenant,
                tariff_version=version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=Decimal(price),
            )
            serve_the_ratified_size(tenant, version)
            versions[label] = version
    return plan, versions


def a_cycle(tenant, code):
    return metering_models.Cycle.objects.create(
        tenant=tenant,
        code=code,
        # W5-T2 — the ruled fields; `window_start`/`window_end` were dropped
        # columns (metering 0021) and the window is derived from these two.
        start_day=PERIOD_START.day,
        days_to_complete=(PERIOD_END - PERIOD_START).days + 1,
        # ⚠ OQ-344 (RC-W6): `cycles.bill_date` is dropped (metering 0023). The
        # surviving default is the bill DAY, and a run with no typed date
        # resolves *"the bill day, in the month after the period ends"*.
        bill_day=1,
        due_days=21,
    )


def a_cycled_water_unit(actor, tenant, cycle, plan, *, asset_no, reads):
    """A metered water unit on the plan, in the cycle, with `(day, kgal)` reads."""
    premises = make_premises(actor, address_line=f"{asset_no} Bluestem Ln")
    unit = make_unit(actor, premises["id"], label=f"Unit {asset_no}", services=["water"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service="water", uom="kgal")
    metering_models.ServicePoint.objects.filter(tenant=tenant, unit_id=unit["id"]).update(
        cycle=cycle
    )
    from apps.metering import services as metering_services

    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    register = Decimal("1000")
    for day, consumption in reads:
        prior, register = register, register + Decimal(consumption)
        commit_read(
            actor,
            asset["id"],
            day=day.isoformat(),
            value=str(register),
            prior_value=str(prior),
            consumption=str(Decimal(consumption)),
            unit="kgal",
        )
    return unit


def a_run(tenant, cycle, key):
    return billing_models.BillRun.objects.create(
        tenant=tenant,
        cycle=cycle,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        idempotency_key=key,
    )


def an_ordinary_bill(tenant, cycle, key):
    """The ordinary path, end to end: prepare_run → calculate_account. ONE bill."""
    prepared = runs.prepare_run(
        cycle_id=cycle.id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        service_date=SERVICE_DATE,
    )
    assert prepared.blocked == (), prepared.blocked
    assert len(prepared.ready) == 1
    return runs.calculate_account(
        prepared.ready[0],
        bill_run=a_run(tenant, cycle, key),
        service_date=SERVICE_DATE,
    )


def _amounts(invoice, kind):
    return sorted(line.amount for line in invoice.lines.all() if line.kind == kind)


def test_br_rat_114_tc1__the_pin__ten_kgal_across_a_midpoint_reprice_is_21_00(brazos, dana):
    """THE CONTRACT FIGURE. PO verbatim (2026-08-22): "Water at $2.00/kgal until
    the 15th, then $2.20, 10 kgal spread evenly: split = $21.00".

    One read of 10 kgal dated period end, no read at the boundary → the 10 kgal
    apportions EVENLY BY DAY: 15/30 × 10 = 5 kgal on each side. 5 × 2.00 =
    10.00 + 5 × 2.20 = 11.00 = **21.00** — never 20.00 (old version all month)
    and never 22.00 (new version all month, which is what this exact fixture
    billed before BR-RAT-114: gather resolved ONE version at the Jun 30 service
    date, DEF-503's own mechanism).
    """
    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos)
        cycle = a_cycle(brazos, "R114-1")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-9101", reads=[(PERIOD_END, "10.000000")]
        )
        account = an_account(brazos, unit["id"], "A-14001")

        invoice = an_ordinary_bill(brazos, cycle, "r114-pin")

        assert _amounts(invoice, "usage") == [Decimal("10.00"), Decimal("11.00")]
        assert invoice.subtotal == Decimal("21.00")
        assert invoice.total == Decimal("21.00")  # no tax seeded, no base stated
        # ONE bill for the whole period, dated across it — never two invoices.
        assert billing_models.Invoice.objects.filter(account_id=account.id).count() == 1
        assert (invoice.period_start, invoice.period_end) == (PERIOD_START, PERIOD_END)

        # Requirement (4): one line per sub-period per charge, NAMING its rate
        # and its dates. The version id is the rate's identity (DEF-276) and the
        # dates ride the description — a split a customer cannot see is a number
        # they cannot check.
        lines = {
            str(line.tariff_version_id): line
            for line in invoice.lines.all()
            if line.kind == "usage"
        }
        assert set(lines) == {str(versions["old"].id), str(versions["new"].id)}
        old_line = lines[str(versions["old"].id)]
        new_line = lines[str(versions["new"].id)]
        assert old_line.amount == Decimal("10.00")
        assert new_line.amount == Decimal("11.00")
        assert "2026-06-01" in old_line.description and "2026-06-15" in old_line.description
        assert "2026-06-16" in new_line.description and "2026-06-30" in new_line.description
        # ...and each line names EXACTLY ONE window. The final tax-bearing call
        # re-emits the carried line beside the fresh one, and a post-call stamp
        # that missed the existing stamp would print BOTH windows on one line —
        # a real bug this assertion caught during the build.
        assert "2026-06-16" not in old_line.description
        assert "2026-06-01" not in new_line.description
        # The derived halves are MARKED estimated in the locked payload — a
        # day-weighted quantity presented as a meter reading would be the
        # defect OQ-191's flag exists to prevent.
        split = invoice.bill_payload["mid_period_split"]
        assert [s["period_start"] for s in split["segments"]] == ["2026-06-01", "2026-06-16"]
        assert all(
            entry["source"] == "day_weighted" and entry["quantity"] == "5.000000"
            for entry in split["estimates"]
        )


def test_br_rat_114_tc2__no_boundary_means_no_split_and_the_untouched_path(brazos, dana):
    """THE IDENTITY — the bar golden 33/33 rides on. A period containing no
    reprice and no plan change walks exactly the path it always walked: one
    usage line, no date stamp on the description, no split record, no
    estimated flag. This is what keeps every ❄️ B5 frozen figure frozen."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Steady Water", services=("water",))
        from apps.rating import selectors as rating_selectors

        for row in rating_selectors.plan_rate_schedules(plan.id):
            version = rating_models.TariffVersion.objects.create(
                tenant=brazos,
                tariff=row["tariff"],
                model="tiered",
                base_charge=Decimal("0"),
                uom="kgal",
                currency="USD",
                effective_from=date(2025, 1, 1),
                effective_to=None,
            )
            rating_models.RateTier.objects.create(
                tenant=brazos,
                tariff_version=version,
                seq=1,
                from_qty=Decimal("0"),
                to_qty=None,
                unit_price=Decimal("2.000000"),
            )
            serve_the_ratified_size(brazos, version)
        state_the_water_base_as_zero(brazos)
        cycle = a_cycle(brazos, "R114-2")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-9102", reads=[(PERIOD_END, "10.000000")]
        )
        an_account(brazos, unit["id"], "A-14002")

        prepared = runs.prepare_run(
            cycle_id=cycle.id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            service_date=SERVICE_DATE,
        )
        assert prepared.blocked == (), prepared.blocked
        assert prepared.ready[0].split_segments == ()

        invoice = runs.calculate_account(
            prepared.ready[0],
            bill_run=a_run(brazos, cycle, "r114-identity"),
            service_date=SERVICE_DATE,
        )
        assert _amounts(invoice, "usage") == [Decimal("20.00")]
        assert invoice.subtotal == Decimal("20.00")
        (usage_line,) = [line for line in invoice.lines.all() if line.kind == "usage"]
        assert "2026-06" not in usage_line.description  # no stamp on an unsplit bill
        assert "mid_period_split" not in invoice.bill_payload


def test_br_rat_114_tc3__a_read_dating_the_boundary_wins_over_the_day_weight(brazos, dana):
    """The rule's second clause, verbatim: "...unless an actual read dates the
    boundary (then the read wins)". A read of 6 kgal on Jun 15 and 4 kgal on
    Jun 30 measures each side, so NOTHING is derived: 6 @ 2.00 = 12.00 and
    4 @ 2.20 = 8.80 — not the day-weighted 5/5, and not marked estimated."""
    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos, name="Read Water")
        cycle = a_cycle(brazos, "R114-3")
        unit = a_cycled_water_unit(
            dana,
            brazos,
            cycle,
            plan,
            asset_no="W-9103",
            reads=[(BOUNDARY - date.resolution, "6.000000"), (PERIOD_END, "4.000000")],
        )
        an_account(brazos, unit["id"], "A-14003")

        invoice = an_ordinary_bill(brazos, cycle, "r114-read-wins")

        assert _amounts(invoice, "usage") == [Decimal("8.80"), Decimal("12.00")]
        assert invoice.subtotal == Decimal("20.80")
        split = invoice.bill_payload["mid_period_split"]
        assert split["estimates"] == []  # the reads won; nothing was derived
        assert all(
            service["estimated"] is False
            for segment in split["segments"]
            for service in segment["services"]
        )


def test_br_rat_114_tc4__a_plan_change_on_the_16th_splits_the_same_way(brazos, dana):
    """DEF-504's own case: the customer moves plans mid-period. Plan A prices
    water at $2.00, plan B at $2.20, the assignment changes effective Jun 16 —
    the SAME $21.00 as the rate change, each side on ITS OWN plan, and the
    locked record names both plans."""
    with tenant_ctx(brazos):
        from apps.metering import services as metering_services
        from apps.rating import selectors as rating_selectors

        plans = {}
        for label, name, price in (
            ("A", "Plan A Water", "2.000000"),
            ("B", "Plan B Water", "2.200000"),
        ):
            plan = make_plan(brazos, name=name, services=("water",))
            for row in rating_selectors.plan_rate_schedules(plan.id):
                version = rating_models.TariffVersion.objects.create(
                    tenant=brazos,
                    tariff=row["tariff"],
                    model="tiered",
                    base_charge=Decimal("0"),
                    uom="kgal",
                    currency="USD",
                    effective_from=date(2025, 1, 1),
                    effective_to=None,
                )
                rating_models.RateTier.objects.create(
                    tenant=brazos,
                    tariff_version=version,
                    seq=1,
                    from_qty=Decimal("0"),
                    to_qty=None,
                    unit_price=Decimal(price),
                )
                serve_the_ratified_size(brazos, version)
            plans[label] = plan
        state_the_water_base_as_zero(brazos)
        cycle = a_cycle(brazos, "R114-4")
        unit = a_cycled_water_unit(
            dana,
            brazos,
            cycle,
            plans["A"],
            asset_no="W-9104",
            reads=[(PERIOD_END, "10.000000")],
        )
        # The mid-period move: the unit changes to plan B effective Jun 16 —
        # the dated history row is what the split reads (BR-CUS-013).
        metering_services.assign_unit_plan(
            dana,
            unit["id"],
            {"tariff_id": str(plans["B"].id), "effective_from": BOUNDARY.isoformat()},
        )
        an_account(brazos, unit["id"], "A-14004")

        invoice = an_ordinary_bill(brazos, cycle, "r114-plan-change")

        assert _amounts(invoice, "usage") == [Decimal("10.00"), Decimal("11.00")]
        assert invoice.subtotal == Decimal("21.00")
        split = invoice.bill_payload["mid_period_split"]
        assert [s["rate_plan_id"] for s in split["segments"]] == [
            str(plans["A"].id),
            str(plans["B"].id),
        ]


def test_br_rat_114_tc5__the_ordinary_run_and_the_back_bill_give_one_answer(brazos, dana):
    """The two paths, held to ONE answer. The same facts through the ordinary
    run and through BR-BIL-018's back-bill (one stated sub-period = the
    period) must produce the same money — DEF-503's complaint was exactly
    that they did not."""
    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos, name="Agree Water")
        cycle = a_cycle(brazos, "R114-5")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-9105", reads=[(PERIOD_END, "10.000000")]
        )
        account = an_account(brazos, unit["id"], "A-14005")

        ordinary = an_ordinary_bill(brazos, cycle, "r114-agree-ordinary")

        prepared = backbill.prepare_back_bill(
            account_id=account.id,
            sub_periods=[(PERIOD_START, PERIOD_END)],
            reason_code="two-paths-one-answer",
        )
        catch_up = backbill.calculate_back_bill(
            prepared, bill_run=a_run(brazos, a_cycle(brazos, "R114-5B"), "r114-agree-backbill")
        )

        assert ordinary.subtotal == catch_up.subtotal == Decimal("21.00")
        assert ordinary.total == catch_up.total
        assert _amounts(ordinary, "usage") == _amounts(catch_up, "usage")
        # ⚠ AMENDED 2026-10-12 (`DEF-BIL-10067`, BR-RAT-114 as amended (2), Q-a):
        # the ORDINARY bill now carries ONE base row per service when only the
        # usage rate changed, where the back-bill (BR-BIL-018's own rules) still
        # prints one per part. This line compared the two LISTS of base rows;
        # it now compares their MONEY, which is what "one answer" means and
        # which is unchanged ($0.00 here either way).
        assert sum(_amounts(ordinary, "base"), Decimal("0")) == sum(
            _amounts(catch_up, "base"), Decimal("0")
        )
        assert len(_amounts(ordinary, "base")) == 1


def test_br_rat_114_tc6__the_split_bill_is_taxed_once_over_the_whole_bill(brazos, dana):
    """B4.2 on a split bill: ONE tax pass over Σ(rounded taxable lines) —
    8.25% × 21.00 = 1.7325 → **1.73**. Taxing each sub-period and summing
    gives 0.83 + 0.91 = 1.74; that cent is the decision-log worked figure
    (judgment 2) and this assertion is what keeps it from drifting."""
    with tenant_ctx(brazos):
        plan, versions = a_repricing_water_plan(brazos, name="Taxed Water")
        jurisdiction = rating_models.TaxJurisdiction.objects.create(
            tenant=brazos, name="State of Texas", authority="State of Texas", level="state"
        )
        rating_models.Tax.objects.create(
            tenant=brazos,
            jurisdiction=jurisdiction,
            name="State of Texas",
            kind="percent",
            rate=Decimal("0.082500"),
        )
        rating_models.PlanTaxRule.objects.create(
            tenant=brazos, rate_plan=plan, jurisdiction=jurisdiction
        )
        cycle = a_cycle(brazos, "R114-6")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-9106", reads=[(PERIOD_END, "10.000000")]
        )
        an_account(brazos, unit["id"], "A-14006")

        invoice = an_ordinary_bill(brazos, cycle, "r114-tax-once")

        assert invoice.subtotal == Decimal("21.00")
        assert invoice.tax_total == Decimal("1.73")  # one pass — never 1.74
        assert invoice.total == Decimal("22.73")

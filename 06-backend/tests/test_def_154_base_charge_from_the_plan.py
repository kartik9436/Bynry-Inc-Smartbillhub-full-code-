# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-003 (gather — the run collects each account's plan, tariffs
#           and reads) · US-RAT-012 (usage pricing — the base charge is one of
#           its inputs)   Screens: S31 (the preview a clerk reads the figure on)
# Rules:    BR-RAT-012 (base/fixed charge is defined PER SERVICE WITHIN A PLAN;
#           multi-service plans sum their service bases — CONFIRMED, PO Q&A R1
#           Q2) · BR-RAT-027 (base rate assigned per service; the plan total is
#           the DERIVED Σ — CONFIRMED, PO Q&A R5 Q9) · BR-RAT-004 (base AND
#           usage prorate by calendar days) · BR-RAT-007 (the version IN FORCE
#           at the service date) · CLAUDE.md rule 2 (money)
# Tests:    this file IS the test — DEF-154's own prevention column asked for it
# ───────────────────────────────────────────────────────
"""DEF-154 — the layer beneath the golden suite: does the engine collect the
right inputs from the right ROWS?

**THE DEFECT, as the PO saw it: every base charge on every bill printed
`$0.00`.** The demo tenant sets `RES-STD` electric **12.00** and water **8.00**
in `plan_services`, and the bill charged nothing for either.

**WHY 33/33 GOLDEN TESTS COULD NOT SEE IT, and this is the whole reason this
file exists.** B5's golden fixtures price a bill from RAW INPUTS through the
pricing engine, handing the base charge in directly. The arithmetic over that
input is right — `prorate_base_charge` is GT-3 and is frozen and correct — and
the SOURCING is wrong. A suite that supplies an input can never discover that
production reads it from the wrong table. Every other billing test in this
repository seeds its own figures for the same reason, so the whole test estate
was blind to it in the same way, and it took producing a bill on a booted stack
with a real plan behind it (DEF-154, reported by the pricing-engines lane).

So this file deliberately does the expensive thing: it SEEDS A PLAN and asks
what the gather step collects. It is not a second golden test — it asserts no
arithmetic at all — and it must never become one. Its whole subject is which
ROW a figure came out of.

**THE TWO ROWS.** `plan_services.base_charge` is the plan's per-service base
(BR-RAT-012/027, both CONFIRMED). `tariff_versions.base_charge` is a column on
the RATE SCHEDULE holding the same kind of fact. Both default to `0` and both
are NOT NULL, so a schedule that has simply never had a base charge typed into
it is indistinguishable from one deliberately set to zero — which is how the
wrong one could be read for days and print a plausible number.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import gather
from apps.billing.exceptions import BillingRuleError
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

SERVICE_DATE = date(2026, 7, 15)

#: The demo tenant's own figure for RES-STD electric (`seed_demo`, asserted in
#: tests/test_seed_demo.py). Used verbatim so this file and the seed cannot
#: drift into testing two different products.
PLAN_ELECTRIC_BASE = Decimal("12")


def a_plan_with_base(tenant, *, plan_base, schedule_base, marker="def154"):
    """A published plan whose electric service carries `plan_base`, priced by a
    schedule whose version carries `schedule_base`.

    Both figures are set explicitly on every call — including the zeroes —
    because the defect is precisely that one of them was zero by default and
    nobody had to decide it.
    """
    electric = tenancy_models.Service.objects.get(code="electric")
    plan = rating_models.RatePlan.objects.create(
        tenant=tenant, code=f"PL-{marker}", name=f"{marker} plan", status="published"
    )
    if plan_base is not None:
        rating_models.PlanService.objects.create(
            tenant=tenant, rate_plan=plan, service=electric, base_charge=plan_base
        )
    tariff = rating_models.Tariff.objects.create(
        tenant=tenant, service=electric, name=f"{marker} schedule"
    )
    version = rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=tariff,
        model="flat",
        base_charge=schedule_base,
        currency="USD",
        uom="kWh",
        effective_from=date(2026, 1, 1),
    )
    rating_models.RateTier.objects.create(
        tenant=tenant,
        tariff_version=version,
        seq=1,
        from_qty=Decimal("0"),
        to_qty=None,
        unit_price=Decimal("0.11"),
    )
    rating_models.PlanRateSchedule.objects.create(
        tenant=tenant, rate_plan=plan, service=electric, tariff=tariff
    )
    return plan, tariff


def electric_config(plan):
    """What the gather step hands the pricing engine for this plan's electric.

    Goes through `gather._tariffs_for_plan`, which is the SAME path a bill run
    takes — the point of the whole file is that a fixture built at the engine's
    doorstep proves nothing about which row was read.
    """
    configs = gather._tariffs_for_plan(str(plan.id), None, SERVICE_DATE, None)
    return next(config for config in configs if config.service == "electric")


def test_def_154_tc1__the_base_charge_on_a_bill_is_the_PLAN_s_figure(brazos, dana):
    """DEF-154 — 12.00 is set on the plan, 0 sits on the schedule, and the bill
    must charge 12.00.

    RED-PROVED against the pre-fix tree, where this returned `Decimal('0')` —
    which is exactly what a customer's bill printed as `$0.00`.
    """
    with tenant_ctx(brazos):
        plan, _ = a_plan_with_base(
            brazos, plan_base=PLAN_ELECTRIC_BASE, schedule_base=Decimal("0")
        )
        config = electric_config(plan)

    assert config.base_charge == PLAN_ELECTRIC_BASE


def test_def_154_tc2__a_schedule_base_is_still_read_when_the_plan_states_none(brazos, dana):
    """No `plan_services` row for the service — one source, no question.

    BR-RAT-012 defines the base per service within a PLAN; a plan that carries
    no row for a service has stated no base, and the schedule's figure is then
    the only one anybody typed. Kept working rather than refused, because
    refusing here would stop bills for every tenant configured before the plan
    row existed — and there is no precedence question where there is one source.
    """
    with tenant_ctx(brazos):
        plan, _ = a_plan_with_base(
            brazos, plan_base=None, schedule_base=Decimal("9.25"), marker="def154b"
        )
        config = electric_config(plan)

    assert config.base_charge == Decimal("9.25")


def test_def_154_tc3__two_sources_that_DISAGREE_refuse_by_name_oq_238(brazos, dana):
    """The precedence, refused rather than picked — and the precedence is RULED now.

    DEF-154's prevention column is explicit: *"Where a rate schedule also
    carries one, the precedence has to be stated rather than inferred from
    whichever the code happened to reach first."* **It is stated:**
    `BR-RAT-088` (PO 2026-08-20) closed `OQ-238` by removing its premise —
    NEITHER of these two objects owns the base charge, the CHARGE CODE does.

    ⚠ **SO THIS CASE IS AMENDED, NOT DELETED, AND WHAT IT PROTECTS IS
    UNCHANGED (`DEF-2823` / `DEF-2825`, 2026-08-31).** The bill still REFUSES,
    still names BOTH amounts, and still names the service — a clerk fixing it
    has to know which screen to open, and a message quoting one figure sends
    them to the wrong place. Silently preferring either one is how this defect
    happened the first time and that has not changed.

    **Two things the sentence no longer says**, because both had stopped being
    true: that `OQ-238` carries the question to the Product Owner (it was
    answered eleven days ago), and that the figure can be cleared *"on the rate
    schedule (S11)"* — `RateScheduleWizard` dropped that control in the same
    ruling, so an operator was offered a repair that did not exist.

    This branch is now reachable ONLY for a tenant that has declared no
    `is_base` charge code: a charge-code figure is checked first and wins.
    """
    with tenant_ctx(brazos):
        plan, _ = a_plan_with_base(
            brazos,
            plan_base=Decimal("12"),
            schedule_base=Decimal("30"),
            marker="def154c",
        )
        with pytest.raises((BillingRuleError, gather.GatherProblem)) as refused:
            electric_config(plan)

    message = str(refused.value)
    # The RULING that settles the precedence, not the question that used to.
    assert "BR-RAT-088" in message
    assert "OQ-238" not in message, "OQ-238 was closed on 2026-08-20 (BR-RAT-088)"
    # DEF-2825 — a refusal may not name a control the product removed.
    assert "S11" not in message, "RateScheduleWizard has no base-charge control"
    assert "12" in message and "30" in message
    assert "electric" in message


def test_def_154_tc4__agreeing_sources_are_not_a_conflict(brazos, dana):
    """The same figure in both places is a duplicate, not a disagreement.

    A tenant who typed 12.00 on the plan and 12.00 on the schedule has not
    posed the open question, and refusing their bill would be the gate biting
    the wrong hand. Asserted so the refusal in tc3 cannot be widened by
    accident into "any schedule base refuses".
    """
    with tenant_ctx(brazos):
        plan, _ = a_plan_with_base(
            brazos, plan_base=Decimal("12"), schedule_base=Decimal("12"), marker="def154d"
        )
        config = electric_config(plan)

    assert config.base_charge == Decimal("12")


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-154@10-defect-log.csv (the defect row's own FIX and PREVENT columns) + 04-docs/05-modules/06-rating/02-business-rules.md BR-RAT-012/BR-RAT-027 (both CONFIRMED) + 12-governance/01-open-questions.md OQ-238
# generated: 2026-08-16 by story-coder (billing-9 lane — the test DEF-154's prevention column asked for and no lane had written)
# checklist: A✔ B✔ C✔ D✔(exercises the gather path POST /billing/runs/{id}/calculate drives) E✔(the figure it guards is what S31.2's preview and every bill print) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tc1 returned `Decimal('0')` against the pre-fix tree, the `$0.00` the PO saw on a real bill; tc3 did not raise at all. Both quoted in the lane report. ruff✔ black✔
# exceptions: (1) THIS FILE ASSERTS NO ARITHMETIC and must never grow any. B5 owns the arithmetic and is ❄ frozen; the gap this covers is one layer beneath it — which ROW an input came from — and a file that tested both would be re-testing signed figures against unsigned fixtures. (2) It seeds through the ORM rather than through the rate-wizard service, because the subject is what the READ collects; a service-layer seed would prove the wizard and the reader agree, which is a different and weaker claim. (3) tc3 asserts a REFUSAL rather than a chosen precedence — the prime directive: an unruled question is carried to the PO (OQ-238), never answered by a lane, and a bill is not produced from a figure two tables disagree about
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

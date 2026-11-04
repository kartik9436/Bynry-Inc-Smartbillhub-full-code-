# ── Trace ──────────────────────────────────────────────
# Change:   PO ruling 2026-09-21 — *"common area dont need rate plan as of now;
#           make this optional"* and *"common area is option"*, the two rulings
#           that opened the pincer refusing every New Connect build.
# Rules:    BR-MET-040 (a plan is REQUIRED at account ACTIVATION — NARROWED for
#           a common area and for nothing else) · BR-MET-101 (a common area is a
#           unit with a flag) · BR-CUS-068 / BR-CUS-1010 (a master account is an
#           ordinary row anchored on the PREMISES) · BR-MET-116 (the owner's
#           build account) · CLAUDE.md hard-won law 7 (prove a guard red before
#           trusting it green, and ask what would make it pass wrongly)
# ───────────────────────────────────────────────────────
"""**THE TWO THINGS THAT HAVE TO GO ON BEING TRUE FOR THE RULINGS TO BE SAFE.**

The PO made an unplanned common area legal. That is only safe because of a
guarantee nobody re-checked when they did it, and because of a rule the PO
deliberately PROTECTED in the same breath. **Both are one edit away from
silently going, and neither had a test.**

**1 · AN UNPLANNED UNIT CAN EXIST AND CAN NEVER BE BILLED.**
`billing.gather.gather_account` raises `GatherProblem(GATHER_NO_PLAN)` for any
unit with no `rate_plan_id`; `runs.STAGE_BY_REASON` files it on the
`resolve-subscription` exception tab and `runs.NOT_RETRYABLE_HERE` marks it as
needing an edit somewhere else. **That is the whole reason an optional plan
requirement is safe rather than reckless** — the decision log says so in as many
words, and adds: *"if that ever stops being true, these rulings need
re-putting."* So this file holds it. A lane that "simplifies" `gather_account`
into defaulting a plan, or skipping the unplanned account, breaks a PO ruling's
precondition and will find out here rather than on a customer's bill.

**2 · A COMMON AREA IS NEVER HANDED A PLAN.**
PO 2026-09-16 (`DEF-CUS-5496`), put as three options — its own plan, the
dwellings' plan, or none — and they chose NONE. `commitPlanOf` filters common
areas out of `plan_assignments` and the server loops over what it is sent, so
the commit simply never assigns one. **This is the rule a later lane will
erode**, because *"the hallway has no plan"* reads like a gap to be filled, and
the tidy-looking fix — send the dwellings' plan to the common area too — is
precisely what the PO declined.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7's second habit). Case 1 would
pass over a build that has no unplanned unit at all, so it asserts the unit it
built is genuinely unplanned BEFORE it gathers. Case 2 would pass over a commit
that created no common area at all, so it asserts the common area exists and is
flagged before asking what plan it holds.
"""

from datetime import date

import pytest

from apps.billing import gather as billing_gather
from apps.billing import runs as billing_runs
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _published_plan(tenant, name="Residential Standard", service_code="electric"):
    """A PUBLISHED plan a unit can be put on. Plan CONTENT is EP-RAT-01's story;
    all `BR-MET-040` ever asked is that `units.rate_plan_id` is non-null."""
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


def _a_block(actor, tenant, *, address, common=True, plan_the_common_area=False):
    """A build committed exactly as step 8's button commits one: the premises,
    its units, the dwellings' plan, and the owner's account."""
    plan = _published_plan(tenant)
    # `BR-CUS-1114` (PO 2026-10-02) — the owner's master account needs two or
    # more homes; Apt 102 makes the block one, priced like Apt 101.
    units = [
        {"label": "Apt 101", "is_common_area": False},
        {"label": "Apt 102", "is_common_area": False},
    ]
    if common:
        units.append({"label": "Common area", "is_common_area": True})
    assignments = [
        {"unit_label": "Apt 101", "tariff_id": str(plan.id)},
        {"unit_label": "Apt 102", "tariff_id": str(plan.id)},
    ]
    if common and plan_the_common_area:
        # The shape the PO DECLINED, built here only so the second case can
        # prove the product refuses to produce it (see that case's docstring).
        assignments.append({"unit_label": "Common area", "tariff_id": str(plan.id)})
    committed = w6.commit_new_connect(
        actor,
        {
            "premises": {
                "id": None,
                "address": address,
                "city": "Katy",
                "state": "TX",
                "postal_code": "77494",
                "premise_type": "apartment_complex",
                "services_available": ["electric"],
            },
            "mode": "our_crew",
            "units": units,
            "meters": [],
            "plan_assignments": assignments,
            "create_owner_account": True,
            "owner": {
                "name": "Ridge Property LLC",
                "kind": "builder_developer",
                "party_kind": "company",
                "customer": identity_fixtures.customer_block(
                    "Ridge Property LLC", kind="company"
                ),
            },
            "work_orders": [],
        },
    )
    connection = work_tables.Connection.objects.get(pk=committed["id"])
    return committed, connection, plan


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE SAFETY THE RULING RESTS ON — an unplanned unit can never be billed
# ══════════════════════════════════════════════════════════════════════════
def test_the_bill_run_still_refuses_an_unplanned_unit(dana, brazos):
    """**If this goes red, the PO's ruling has lost its precondition and needs
    re-putting — it is not a test to "fix".**

    An unplanned common area is legal since 2026-09-21. What stops that being
    reckless is that such a unit is UNBILLABLE by construction, and this is the
    line that makes it so.
    """
    with tenant_ctx(brazos):
        _committed, connection, _plan = _a_block(dana, brazos, address="41 Gather Way")

        common = metering_models.Unit.objects.get(
            tenant_id=brazos.id, premises_id=connection.premises_id, is_common_area=True
        )
        # ⚠ **ASSERTED BEFORE THE GATHER, BECAUSE THIS IS WHAT WOULD MAKE THE
        # CASE PASS WRONGLY.** A build whose common area happened to carry a
        # plan would sail through the refusal below for the wrong reason.
        assert common.rate_plan_id is None, "the common area is genuinely unplanned"

        account = customers_models.Account.objects.get(pk=connection.owner_account_id)

        with pytest.raises(billing_gather.GatherProblem) as caught:
            billing_gather.gather_account(
                account=account,
                service_date=date(2026, 9, 30),
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                cycle_days=30,
            )

        # The REASON is the contract, not merely that something was raised:
        # `STAGE_BY_REASON` and `NOT_RETRYABLE_HERE` are both keyed off it, so a
        # refusal under a different code would file the account on the wrong tab.
        assert caught.value.reason in {
            billing_gather.GATHER_NO_PLAN,
            billing_gather.GATHER_NO_UNIT,
        }
        assert billing_runs.STAGE_BY_REASON[billing_gather.GATHER_NO_PLAN] == (
            "resolve-subscription"
        )
        assert billing_gather.GATHER_NO_PLAN in billing_runs.NOT_RETRYABLE_HERE


def test_an_unplanned_dwelling_is_refused_by_the_bill_run_too(dana, brazos):
    """The same guarantee stated on the unit that MATTERS commercially.

    The narrowing is about common areas; the safety net is about every unit. A
    dwelling that reached the database unplanned — through the S68 import's own
    `require_plan=False` exemption, say — must be just as unbillable.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="43 Gather Way")
        unit = make_unit(dana, premises["id"], label="Apt 1")
        row = metering_models.Unit.objects.get(pk=unit["id"])
        assert row.rate_plan_id is None

        # ⚠ **THROUGH THE IMPORT DOOR ON PURPOSE.** It is the ONE caller that
        # passes `require_plan=False` (`CR-047` task 11, `DEF-2518`), so it is
        # the only way a DWELLING legitimately reaches the database with an
        # active account and no plan — which is exactly the state this case
        # exists to prove is unbillable.
        account = customers_services.create_from_import(
            actor=dana,
            payload={
                "unit_id": unit["id"],
                "account": {
                    "account_type": "residential",
                    "status": "active",
                    "opened_at": "2026-09-01",
                    "contact": {"full_name": "Dana Whitfield"},
                    "customer": identity_fixtures.customer_block(
                        "Dana Whitfield", kind="person"
                    ),
                },
            },
        )
        account_row = customers_models.Account.objects.get(pk=account["id"])

        with pytest.raises(billing_gather.GatherProblem) as caught:
            billing_gather.gather_account(
                account=account_row,
                service_date=date(2026, 9, 30),
                period_start=date(2026, 9, 1),
                period_end=date(2026, 9, 30),
                cycle_days=30,
            )
        assert caught.value.reason == billing_gather.GATHER_NO_PLAN


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE RULE THE PO PROTECTED — a common area is never handed a plan
# ══════════════════════════════════════════════════════════════════════════
def test_a_commit_never_hands_the_common_area_a_plan(dana, brazos):
    """**PO 2026-09-16 (`DEF-CUS-5496`), three options, and they chose NONE.**

    This is the rule a later lane erodes, because *"the hallway has no plan"*
    reads like a gap. It is not a gap: it is the answer.
    """
    with tenant_ctx(brazos):
        committed, connection, _plan = _a_block(dana, brazos, address="45 Gather Way")

        units = list(
            metering_models.Unit.objects.filter(
                tenant_id=brazos.id, premises_id=connection.premises_id
            ).order_by("label")
        )
        common = [unit for unit in units if unit.is_common_area]
        dwellings = [unit for unit in units if not unit.is_common_area]

        # ⚠ **ASSERTED FIRST, BECAUSE A BUILD WITH NO COMMON AREA WOULD PASS THE
        # REAL ASSERTION VACUOUSLY** — law 7's *what would make this pass
        # wrongly*.
        assert len(common) == 1, "this build really does have a shared unit"
        assert len(dwellings) == 2  # Apt 101 + Apt 102 (BR-CUS-1114)

        assert common[0].rate_plan_id is None, (
            "PO 2026-09-16: a common area is sent NO plan. If this is red because "
            "somebody 'filled the gap', that is the option the PO declined."
        )
        assert dwellings[0].rate_plan_id is not None, "and the dwelling IS priced"
        assert committed["manifest"]["plan_assignments"] == 2  # both dwellings, BR-CUS-1114


def test_the_dwelling_plan_requirement_is_narrowed_and_not_deleted(dana, brazos):
    """**`BR-MET-040` goes on holding for a DWELLING**, which is the half of the
    ruling that is easiest to lose.

    PO, verbatim: *"common area dont need rate plan as of now; make this
    optional"*. `COMMON_AREA_REQUIRES_A_PLAN` is that *"as of now"* written as a
    condition that can be read and changed — flip it and the refusal returns —
    and this case holds the boundary it draws.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="47 Gather Way")
        dwelling = make_unit(dana, premises["id"], label="Apt 1")
        common = make_unit(
            dana,
            premises["id"],
            label="Hallway",
            unit_type="common_area",
            is_common_area=True,
        )

        dwelling_row = metering_models.Unit.objects.get(pk=dwelling["id"])
        common_row = metering_models.Unit.objects.get(pk=common["id"])

        # The exemption is a named, readable, changeable condition — never a
        # deleted rule. Both halves asserted so neither can drift alone.
        assert customers_services.COMMON_AREA_REQUIRES_A_PLAN is False
        assert customers_services._unit_is_a_common_area(common_row) is True
        assert customers_services._unit_is_a_common_area(dwelling_row) is False

        # A COMMON AREA: no refusal.
        customers_services._require_plan_on_unit(common_row)

        # A DWELLING: refused, by name, exactly as before the ruling.
        with pytest.raises(errors.BizError) as caught:
            customers_services._require_plan_on_unit(dwelling_row)
        assert caught.value.br_ref == "BR-MET-040"
        assert caught.value.message_key == "customers.account.plan_required_at_activation"

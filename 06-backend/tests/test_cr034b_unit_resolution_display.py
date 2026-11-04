# ── Trace ──────────────────────────────────────────────
# Change:  CR-034 (b) — the PO on the live build, verbatim: *"what exactly will
#          be use from plan for this unit when billing happens"*, and *"showing
#          in - what period you are reporting data for"*.
#          ⚠ NO STORY OWNS THE UNIT PLAN TAB — hard-won law 8, the same gap
#          `test_w5_unit_reads.py` reports for move-in step 3/4. REPORTED.
# Rules:   BR-RAT-007 (the version in force on the SERVICE-PERIOD END DATE — the
#          pivot every narrowing here uses) · BR-RAT-114 / DEF-504 (a plan change
#          inside a period SPLITS the bill; it is reported, never collapsed) ·
#          BR-RAT-069/110 (a plan BINDING grants a discount to nobody — the
#          enrolment does, and it belongs to an ACCOUNT) · BR-RAT-030 (only
#          published plans assign) · BR-RAT-031 (a draft has never been in
#          force) · BR-RAT-087 (money and percent carry a `*_display` companion)
#          · BR-RAT-088 (the charge code owns the base) · BR-RAT-108 (an empty
#          class list means EVERY class) · DEF-273 (a tax rate is not a tax
#          RULE — the set narrows again by customer class) · DEF-277 (a stated
#          `0.00` and a blank are different facts) · BR-TEN-043 (the tenant's
#          clock, never the server's) · CLAUDE.md rule 2 (money 4dp / percent
#          6dp / display 2)
# Golden:  NONE — AND THAT IS THE ASSERTION. This endpoint computes no money, so
#          it reproduces no GT figure; TC-7 pins that it holds no derived total.
# Tests:   this file (TC-1..TC-10; TC-11..TC-15 added 2026-08-26 by the CR-034 §7 lane)
# Impacts: apps/rating/services.py (_plan_snapshot drops `terms` — TC-15) ·
#          apps/metering/selectors.py (unit_pricing · _plan_history ·
#          _offered_discounts · _minimum_charges · _rate_schedule_card) ·
#          apps/metering/api.py (_pricing_period + the two query params) ·
#          apps/rating/selectors.py (schedule_detail's `as_of`; plan_detail's
#          charge_rules projection) ·
#          07-frontend/src/features/customers/UnitPricingPanel.tsx
# ───────────────────────────────────────────────────────
"""CR-034 (b) — the unit Plan tab answers *for a stated period*.

Every case runs through the REAL view function (`api_call`), so the tenant
context, the permission class, the query-param parsing and the selector are all
exercised together — a selector-only test would not prove the route accepts the
period at all.

🔒 **NOTHING HERE ASSERTS A COMPUTED FIGURE, BECAUSE NOTHING COMPUTES ONE.**
B4/B5 are ❄️ FROZEN and GT-1..61 are the billing-math contract. The figures
below are asserted to be BYTE-IDENTICAL to what rating's own selectors return,
which is the only property that keeps a second implementation of billing math
from being born on this endpoint.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.metering import api, selectors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (
    make_plan,
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


#: The fixture plan's two stored base charges, at the column's six places.
ELECTRIC_BASE = Decimal("8.000000")
WATER_BASE = Decimal("12.500000")

#: The two rate-schedule versions TC-3 turns on. `V1` is in force now; `V2` is
#: ACTIVATED and dated for a month that has not started. The whole of BR-RAT-007
#: is the difference between them, and a screen that always asked about "today"
#: cannot tell them apart.
V1_FROM = date(2026, 1, 1)
#: ⚠ 2099, not 2026-09: the date rotted into the past on 2026-10-01 and "now"
#: then resolved V2. A version for "a month that has not started" must stay so.
V2_FROM = date(2099, 9, 1)


def _plan_with_base_charges(tenant, services=("electric", "water")):
    """A published plan WITH its per-service base-charge rows (the W5 helper's
    fixture, reproduced here so this file does not import another test module's
    private helper)."""
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    plan = make_plan(tenant, services=services)
    for code, amount in (("electric", ELECTRIC_BASE), ("water", WATER_BASE)):
        if code not in services:
            continue
        rating_models.PlanService.objects.get_or_create(
            tenant=tenant,
            rate_plan=plan,
            service=tenancy_models.Service.objects.get(code=code),
            # `minimum_amount` is gone from this table (`rating/0031`,
            # 2026-09-10); writing it refused every case in this file.
            defaults={"base_charge": amount, "currency": "USD"},
        )
    return plan


def _unit_on(actor, tenant, plan, *, label="Unit A", effective_from=None):
    """One unit on a real premise, holding `plan` through the REAL service."""
    from apps.metering import services

    premise = make_premises(actor, services_available=["electric", "water"])
    unit = make_unit(actor, premise["id"], label=label, services=["electric", "water"])
    payload = {"tariff_id": str(plan.id)}
    if effective_from is not None:
        payload["effective_from"] = effective_from.isoformat()
    services.assign_unit_plan(actor, unit["id"], payload)
    return unit


def _version(tenant, plan, service_code, *, effective_from, effective_to, minimum_bill):
    """One ACTIVATED rate-schedule version on the plan's schedule for a service.

    `effective_from` non-NULL is what makes it activated rather than a draft
    (BR-RAT-031), which is the only reason `in_force_version` will ever see it.
    """
    from apps.rating import models as rating_models
    from apps.tenancy import models as tenancy_models

    service = tenancy_models.Service.objects.get(code=service_code)
    link = rating_models.PlanRateSchedule.objects.get(
        tenant=tenant, rate_plan=plan, service=service
    )
    return rating_models.TariffVersion.objects.create(
        tenant=tenant,
        tariff=link.tariff,
        model="flat",
        base_charge=None,
        minimum_bill=minimum_bill,
        currency="USD",
        uom="kWh",
        effective_from=effective_from,
        effective_to=effective_to,
    )


def _charge_on_plan(tenant, plan, **overrides):
    """A charge code the plan names, with the code's OWN amount stated.

    The hole CR-034 (b) closes: the plan rule carried `amount_override` and
    nothing else, so a NULL override left a screen with a name and no figure.
    """
    from apps.rating import models as rating_models

    fields = {
        "code": "FIRELINE",
        "name": "Fire line",
        "charge_type": "recurring",
        "amount_rule": "flat",
        "amount": Decimal("18.000000"),
        "is_base": False,
        "taxable_default": True,
    }
    fields.update(overrides)
    charge = rating_models.Charge.objects.create(tenant=tenant, **fields)
    rating_models.PlanChargeRule.objects.create(
        tenant=tenant,
        rate_plan=plan,
        charge=charge,
        amount_override=None,  # ← the case that printed a promise and no number
        recurrence="recurring",
        taxable=True,
    )
    return charge


def _discount_on_plan(tenant, plan):
    """A discount the PLAN OFFERS. Nobody is enrolled — deliberately."""
    from apps.rating import discounts as discount_models

    discount = discount_models.Discount.objects.create(
        tenant=tenant, code="SENIOR", name="Senior", status="active"
    )
    discount_models.DiscountVersion.objects.create(
        tenant=tenant,
        discount=discount,
        version_no=1,
        discount_type="percentage",
        value=Decimal("10.000000"),
        currency="USD",
    )
    discount_models.PlanDiscountRule.objects.create(
        tenant=tenant, rate_plan=plan, discount=discount
    )
    return discount


def _pricing(dana, brazos, unit_id, **params):
    return api_call(  # noqa: F405
        api.unit_pricing,
        "get",
        user=dana.user,
        role="system_admin",
        tenant=brazos,
        unit_id=unit_id,
        query=params or None,
    )


# ── TC-1 · NO PERIOD IS EVER INVENTED ──────────────────────────────────────
def test_cr034b_tc1__no_period_supplied_answers_as_of_today_and_says_so(brazos, dana):
    """The PO asked for the period to be STATED. A caller that names none gets
    `period: null` and `as_of` = the tenant's today — **never a default month.**

    ⚠ THIS IS THE CASE THAT KEEPS THE MOVE-IN WIZARD UNCHANGED. Step 4 calls
    this endpoint with no period, and the answer it receives is the one it
    received before CR-034 (b): the same plan, the same in-force versions.

    The declined alternative, worked against a calendar: defaulting to *the
    current month* makes `as_of` the 31st while today is the 25th, so a rate
    version effective the 28th — NOT in force today — resolves, and a customer
    signing up is shown next month's prices as the ones that will bill them.
    That is a product decision with a consequence and it went to the PO.
    """
    from apps.metering import seams

    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        today = seams.tenant_today()
        response = _pricing(dana, brazos, unit["id"])
    assert response.status_code == 200
    period = response.data["period"]
    assert period["start"] is None and period["end"] is None
    assert period["supplied"] is False
    assert period["source"] == "not_supplied_defaults_to_today"
    assert period["as_of"] == today.isoformat()
    # BR-RAT-114 has nothing to report when there is no period to change within,
    # and it says WHY rather than serving an empty list that reads as "no
    # changes" — the R6 `modelled` distinction, one object across.
    assert response.data["plan_history"]["served"] is False
    assert response.data["plan_history"]["reason"] == "period_not_supplied"
    assert response.data["plan_history"]["stretches"] == []


# ── TC-2 · A SUPPLIED PERIOD IS ECHOED, AND `as_of` IS ITS END ──────────────
def test_cr034b_tc2__as_of_is_the_period_end_not_today(brazos, dana):
    """BR-RAT-007, quoted by `rating.resolution.resolve_plan`: the plan version
    in force on the **SERVICE-PERIOD END DATE**. So `as_of` is the end, the
    answer carries it, and the resolved plan names the date that resolved it —
    a figure has to be able to state its own inputs (DEF-276's reasoning)."""
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
    assert response.status_code == 200
    period = response.data["period"]
    assert (period["start"], period["end"]) == ("2026-07-01", "2026-07-31")
    assert period["as_of"] == "2026-07-31"
    assert period["supplied"] is True
    assert period["source"] == "caller"
    assert response.data["plan"]["resolved_on"] == "2026-07-31"


# ── TC-3 · THE SCHEDULE RESOLVES ON THE SERVICE DATE, NOT ON TODAY ─────────
def test_cr034b_tc3__the_rate_schedule_version_follows_the_service_date(brazos, dana):
    """**The case the whole period argument exists for.** One schedule, two
    ACTIVATED versions: V1 in force now, V2 dated for a month that has not
    started. Asking about a period inside V2's window must resolve V2; asking
    with no period must still resolve V1.

    A screen that always asked about "today" cannot tell these apart, and the
    day a filing takes effect it would print the wrong month's rates under the
    heading of this one. The two versions are told apart here by their MINIMUM
    BILL, which is a stored column forwarded verbatim — no money is computed.
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        v1 = _version(
            brazos,
            plan,
            "electric",
            effective_from=V1_FROM,
            # ⚠ `DEF-RAT-8817` — the end date is INCLUSIVE, so V1 ends the day
            # before V2 starts. Ending ON V2's start overlaps it by a day:
            # PostgreSQL's `ex_tariff_versions_no_overlap` refuses that
            # (ExclusionViolation) and sqlite cannot see it.
            effective_to=V2_FROM - timedelta(days=1),
            minimum_bill=Decimal("5.000000"),
        )
        v2 = _version(
            brazos,
            plan,
            "electric",
            effective_from=V2_FROM,
            effective_to=None,
            minimum_bill=Decimal("9.000000"),
        )
        now = _pricing(dana, brazos, unit["id"])
        later = _pricing(
            dana, brazos, unit["id"], period_start="2099-09-01", period_end="2099-09-30"
        )

    def electric_version(body):
        row = next(r for r in body["rate_schedules"] if r["service"] == "electric")
        return row["schedule"]["current_version"]

    assert electric_version(now.data)["id"] == str(v1.id)
    assert electric_version(now.data)["minimum_bill_display"] == "5.00"
    assert electric_version(later.data)["id"] == str(v2.id)
    assert electric_version(later.data)["minimum_bill_display"] == "9.00"
    # …and the section that gathers the floors follows the same date, because it
    # reads the SAME resolved card rather than looking the version up again.
    floors = {row["service"]: row for row in later.data["minimum_charges"]["schedules"]}
    assert floors["electric"]["version_id"] == str(v2.id)
    # DEF-MET-8823 — the VERSION's own minimum is no longer the panel's figure
    # (PO 2026-10-01, option A: the minimum is per meter size). This unit has
    # no meter, so no size, so no minimum. See
    # `test_def_met_unit_panel_minimum_per_size.py` for the sized cases.
    assert floors["electric"]["minimum_bill_display"] is None
    assert floors["electric"]["minimum_state"] == "no_size_recorded"


# ── TC-4 · A PLAN CHANGE INSIDE THE PERIOD IS REPORTED, NEVER COLLAPSED ────
def test_cr034b_tc4__a_mid_period_plan_change_is_reported_not_collapsed(brazos, dana):
    """BR-RAT-114 / DEF-504 — a customer who moved plans on the 15th is billed
    once per stretch, each on ITS plan.

    So a screen that named ONE plan as *the* plan for the period would state
    something no bill will do. Every stretch travels, `splits_at` names the date
    a bill would break on, and the sections resolve on `as_of` — one DATE, which
    R1 answers with exactly one plan (`rating.resolution.resolve_plan`: *"exactly
    one answer or refuses"*).
    """
    with tenant_ctx(brazos):
        first = _plan_with_base_charges(brazos)
        second = make_plan(brazos, name="Residential", services=("electric", "water"))
        unit = _unit_on(dana, brazos, first, effective_from=date(2026, 7, 1))
        from apps.metering import services

        services.assign_unit_plan(
            dana,
            unit["id"],
            {"tariff_id": str(second.id), "effective_from": "2026-07-15"},
        )
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
    assert response.status_code == 200
    history = response.data["plan_history"]
    assert history["served"] is True
    assert len(history["stretches"]) == 2, "both stretches must be reported"
    assert [row["plan_name"] for row in history["stretches"]] == [
        "Small Commercial",
        "Residential",
    ]
    assert [row["assigned_from"] for row in history["stretches"]] == ["2026-07-01", "2026-07-15"]
    # The date a real bill for this period would split on.
    assert history["splits_at"] == ["2026-07-15"]
    # …and the plan the sections were resolved against is the END-DATE one,
    # named with the date that chose it. Nothing "picked" a stretch.
    assert response.data["plan"]["name"] == "Residential"
    assert response.data["plan"]["resolved_on"] == "2026-07-31"


# ── TC-5 · THE CHARGE CODE'S OWN AMOUNT, WHICH WAS PROMISED AND WITHHELD ───
def test_cr034b_tc5__a_charge_code_with_no_override_still_shows_its_amount(brazos, dana):
    """The panel printed *"At the charge code's own amount"* **without the
    amount** — a sentence that promises a figure and withholds it, which is
    worse than saying nothing, because a reader concludes the number is
    unknowable rather than merely unfetched.

    Both facts now travel and NEITHER is collapsed into an "effective amount":
    a NULL override means *this plan does not restate the price*, and which one
    bills is DEF-154's precedence rule, which lives in billing and is not
    reimplemented in a read.
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        _charge_on_plan(brazos, plan)
        response = _pricing(dana, brazos, unit["id"])
    row = next(r for r in response.data["charge_codes"] if r["code"] == "FIRELINE")
    assert row["amount_override"] is None
    assert row["amount"] == "18.000000"  # stored, six places (CLAUDE.md rule 2)
    assert row["amount_display"] == "18.00"  # displayed at two (BR-RAT-087)
    assert row["service"] is None  # CR-013 part 2 — `—` for an account-level code
    assert row["is_base"] is False  # BR-RAT-088 — declared, never inferred
    assert row["amount_rule"] == "flat"
    assert row["applies_to_customer_classes"] == []  # BR-RAT-108 — EVERY class
    assert row["size_amounts"] == []  # DEF-431 — this code does not vary by size
    # ⚠ NO DERIVED FIELD. The read must not decide which of the two amounts wins.
    assert "effective_amount" not in row


# ── TC-6 · OFFERED IS NOT GRANTED, AND THE COUNT IS DROPPED ───────────────
def test_cr034b_tc6__the_plan_offers_a_discount_and_the_grant_is_a_stated_absence(brazos, dana):
    """BR-RAT-069 — binding a discount to a plan grants it to NOBODY; a bill run
    reads `discount_enrolments`, and an enrolment belongs to an ACCOUNT, which a
    unit does not have.

    So the grant is a stated absence, exactly the shape
    `rating.resolution.DiscountResolution.modelled` uses: *"this product cannot
    express it"* and *"this customer has none"* are different facts, and so are
    *offered* and *granted*.

    ⚠ AND RATING'S `enrolled` COUNT IS DROPPED RATHER THAN LABELLED. It is
    TENANT-WIDE (rating's own docstring), and a number on a UNIT screen is read
    as that unit's however the caption is worded. An absent figure is safer than
    a correctly-labelled misleading one.
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        _discount_on_plan(brazos, plan)
        response = _pricing(dana, brazos, unit["id"])
    discounts = response.data["discounts"]
    assert [row["code"] for row in discounts["offered"]] == ["SENIOR"]
    offered = discounts["offered"][0]
    assert offered["type"] == "percentage"
    # rating's OWN string, never `value` — which stores percentage POINTS and
    # renders `15` as `1500.00%` through a fraction formatter (DEF-291).
    assert offered["value_display"] is not None
    assert "enrolled" not in offered, "a tenant-wide count must not reach a unit screen"
    assert discounts["granted"]["served"] is False
    assert discounts["granted"]["reason"] == "unit_has_no_account"
    # Never `[]`, which a screen would render as "no discounts apply".
    assert discounts["granted"].get("applied") is None


# ── TC-7 · THE FLOORS ARE ASSEMBLED, NOT RESOLVED AGAINST EACH OTHER ──────
def test_cr034b_tc7__minimum_charges_gathers_three_floors_and_derives_none(brazos, dana):
    """🔒 **THE FROZEN-MATH GUARD ON THIS SECTION.**

    Three places store a floor — the plan, the plan's service line and the rate
    schedule version — and this section puts all three under one heading because
    the PO asked to see the minimum charges for a unit and they were scattered.

    **Which floor WINS is BR-RAT-016/028, it is PROPOSED on GT-13 rather than
    frozen, and deriving it here would be billing math in a second place where
    no golden test can see it.** So the payload holds no total, no `min()`, no
    "effective minimum" — three labelled figures, and the screen says they are
    three.

    Each is asserted BYTE-IDENTICAL to rating's own answer, so the day somebody
    computes one here it goes RED.
    """
    from apps.rating import selectors as rating_selectors

    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        plan.minimum_bill_amount = Decimal("15.000000")
        plan.save(update_fields=["minimum_bill_amount"])
        unit = _unit_on(dana, brazos, plan)
        _version(
            brazos,
            plan,
            "electric",
            effective_from=V1_FROM,
            effective_to=None,
            minimum_bill=Decimal("5.000000"),
        )
        # ⚠ RATING'S ANSWER IS READ FIRST, and the order is load-bearing:
        # `api_call` enters its OWN tenant context around the view and leaves it
        # on the way out, which clears the one this block opened. A read after
        # it raises AUTH-003 rather than failing the comparison — a green-looking
        # trap for the next person who adds a case here.
        rating_answer = rating_selectors.plan_detail(plan.id)
        response = _pricing(dana, brazos, unit["id"])

    floors = response.data["minimum_charges"]
    # 1 · the PLAN's own floor — rating's string, forwarded.
    assert floors["plan"]["amount"] == rating_answer["minimum_bill_amount"] == "15.000000"
    # 2 · the plan's SERVICE line — rating's own read-through, forwarded. The
    # version states no size rows, so neither service has one figure to show,
    # and NULL never becomes 0.00 (DEF-277).
    electric = next(row for row in floors["services"] if row["service"] == "electric")
    assert electric["minimum_amount"] == next(
        row["schedule_minimum_amount"]
        for row in rating_answer["services"]
        if row["service"] == "electric"
    )
    water = next(row for row in floors["services"] if row["service"] == "water")
    assert water["minimum_amount"] is None
    # 3 · the SCHEDULE's floor for this unit's size (DEF-MET-8823). The
    # version's own $5.00 is no longer billed (PO 2026-10-01, option A) and is
    # not shown; this unit has no meter, so no size and no minimum.
    schedule = next(row for row in floors["schedules"] if row["service"] == "electric")
    assert schedule["minimum_bill"] is None
    assert schedule["minimum_state"] == "no_size_recorded"
    # ⚠ NOTHING IS DERIVED FROM THE THREE.
    assert set(floors) == {"plan", "services", "schedules"}
    for forbidden in ("total", "effective", "effective_minimum", "applies", "winner"):
        assert forbidden not in floors, "which floor wins is BR-RAT-016/028, not this read's"


# ── TC-8 · THE PERIOD IS BOTH OR NEITHER, AND NEVER REVERSED ──────────────
@pytest.mark.parametrize(
    "params, missing",
    [
        # …and the field the refusal NAMES is the one that is MISSING, not the
        # one that was typed. A refusal that points at the field the user filled
        # in correctly sends them to fix the wrong box.
        ({"period_start": "2026-07-01"}, "period_end"),
        ({"period_end": "2026-07-31"}, "period_start"),
    ],
)
def test_cr034b_tc8a__half_a_period_refuses_rather_than_defaulting(brazos, dana, params, missing):
    """A caller naming one end has asked a question with no answer: `as_of` is
    the period END, so a start with no end names no service date at all.
    Silently defaulting the missing half would answer a DIFFERENT question and
    print the result under the caller's own heading."""
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        response = _pricing(dana, brazos, unit["id"], **params)
    assert response.status_code == 422
    assert response.data["code"] == "VAL-001"
    assert [row["field"] for row in response.data["field_errors"]] == [missing]


def test_cr034b_tc8b__a_reversed_period_refuses(brazos, dana):
    """A reversed window is not a narrow one — it has no days at all, and
    `as_of` would sit BEFORE the period it claims to price."""
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-31", period_end="2026-07-01"
        )
    assert response.status_code == 422
    assert response.data["code"] == "VAL-003"


def test_cr034b_tc8c__an_unparseable_date_refuses_rather_than_guessing(brazos, dana):
    """`date.fromisoformat` and nothing looser (`billing/api._date_field`'s
    reason): a date parsed by guessing at a format resolves a different rate
    version in one region than in another."""
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        response = _pricing(
            dana, brazos, unit["id"], period_start="07/01/2026", period_end="2026-07-31"
        )
    assert response.status_code == 422
    assert response.data["code"] == "VAL-002"


# ── TC-9 · WHAT IS STILL NOT ANSWERED, AND SAYS SO ────────────────────────
def test_cr034b_tc9__the_contract_and_the_tax_set_state_their_limits(brazos, dana):
    """Three absences, three DIFFERENT sentences, none of them an empty list.

    * **The contract** — no contract object exists in this product. `tracks` is
      null because an OQ is OWED and is REPORTED rather than minted in code
      (the prime directive; DEF-445 — an absence citing a fabricated id is worse
      than one citing none).
    * **The worked month** — unchanged and still OQ-363. The PO re-scoped
      CR-034 (b) away from it and its two blockers are untouched; **(b), that no
      signed rule states the consumption, survives (a) being solved.**
    * **The tax set** — what is served is the PLAN's bindings and attachments,
      NOT R7's answer. Three of r10's five Texas rates scope by customer class
      (DEF-273), which is an ACCOUNT fact a unit cannot supply.
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        response = _pricing(dana, brazos, unit["id"])
    body = response.data
    assert body["contract"]["served"] is False
    # ⚠ THE ROW THAT COVERS THIS ALREADY EXISTED and the lane found it rather
    # than minting a second one: `CR-020`, the PO's own contracts-on-plans
    # request, captured 2026-08-20 and HELD by them on 2026-08-21 — *"hold on
    # dont proceed"*. `tracks` stays null because that field is typed for an
    # EXPIRY row (a DEF or an OQ); the CR travels in its own field.
    assert body["contract"]["reason"] == "captured_and_held_by_the_product_owner"
    assert body["contract"]["tracks"] is None
    assert body["contract"]["change_request"] == "CR-020"
    assert body["worked_month"]["served"] is False
    assert body["worked_month"]["tracks"] == "OQ-363"
    assert body["taxes"]["narrowing"]["final"] is False
    assert body["taxes"]["narrowing"]["reason"] == "narrows_by_customer_class_at_bill_time"


def test_cr034b_tc9b__an_unplanned_unit_still_answers_with_the_period(brazos, dana):
    """BR-MET-100 — a unit with no plan is COUNTED AND FINDABLE, not an error.

    The period section is served on EVERY response including this one, so the
    screen can print its heading before it knows whether there is a plan to
    describe. The stated absences keep their own reason codes.
    """
    with tenant_ctx(brazos):
        premise = make_premises(dana, services_available=["electric"])
        unit = make_unit(dana, premise["id"], label="Unit Z", services=["electric"])
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
    assert response.status_code == 200
    assert response.data["period"]["as_of"] == "2026-07-31"
    assert response.data["plan_absent"] == {"reason": "unit_has_no_plan", "tracks": None}
    assert response.data["minimum_charges"] == {"plan": None, "services": [], "schedules": []}
    assert response.data["discounts"]["granted"]["served"] is False


# ── The selector answers the same thing the route does ────────────────────
def test_cr034b_tc10__the_selector_and_the_route_agree(brazos, dana):
    """`api_call` proves the route; this proves the route adds nothing of its
    own to the answer, so a reader of either can trust the other."""
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        direct = selectors.unit_pricing(
            unit["id"], period_start=date(2026, 7, 1), period_end=date(2026, 7, 31)
        )
        routed = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
    assert routed.data == direct


# ── TC-11 · CR-034 §7 · THE CONDITIONS TO AVAIL IT ARE SERVED, AS STORED ───
def _senior_with_conditions(tenant, plan, **over):
    """SENIOR as `discount_sample_data` seeds it — the r10 programme, with the
    conditions a customer must satisfy filled in.

    Every figure is the fixture's own; nothing here is computed, and the test
    asserts the payload is byte-identical to what was stored.
    """
    from apps.rating import discounts as discount_models

    discount = discount_models.Discount.objects.create(
        tenant=tenant, code="SENIOR", name="Senior discount", status="active"
    )
    fields = {
        "discount_type": "percentage",
        "value": Decimal("15.000000"),
        "currency": "USD",
        "applies_to": "whole_bill",
        "eligibility_summary": "Age 65+",
        "eligibility_rule": {"all": [{"field": "age", "op": ">=", "value": 65}]},
        "enrolment_mode": "apply_and_approve",
        "verification_method": "annual_recertification",
        "proof_required": True,
        "accepted_proof_kinds": ["government_id", "birth_certificate"],
        "proof_before_first_reduction": True,
        "recertification_months": 12,
        "recertification_notice_days": 60,
        "lapse_behaviour": "notify_then_drop",
        "exclusivity_group": "assistance",
        "stacks_with_others": False,
        "stacking_precedence": 10,
        "cap_per_bill": Decimal("20.000000"),
        "bill_floor_amount": Decimal("0.000000"),
        # ⚠ SEEDED AND NEVER EXPECTED IN THE PAYLOAD — see TC-12.
        "budget_cap": Decimal("12312.000000"),
        "budget_period": "annual",
    }
    fields.update(over)
    version = discount_models.DiscountVersion.objects.create(
        tenant=tenant, discount=discount, version_no=1, **fields
    )
    discount_models.PlanDiscountRule.objects.create(
        tenant=tenant, rate_plan=plan, discount=discount
    )
    return discount, version


def test_cr034_s7_tc11__the_conditions_required_to_avail_a_discount_are_served(brazos, dana):
    """CR-034 §7, amended by the PO 2026-08-26, verbatim: *"We should show all
    discount plan offer and what condition are required to avail that discount ;
    when account is attached it will avail those discounts"*.

    **The conditions ARE stored** — on `discount_versions`, not on the plan's
    advisory `eligibility` jsonb — so this is a rendering gap and not a data
    one. Every key below is one column, forwarded: what a customer must be
    (`eligibility_summary`), how they get it (`enrolment_mode`), what proof it
    takes (`accepted_proof_kinds`), whether the reduction waits for the proof,
    how it is kept (`recertification_*`, `lapse_behaviour`), what it reduces
    (`applies_to`), the most it can take off (`cap_*`), how low it may drive a
    bill (`bill_floor_amount`, BR-RAT-074) and whether it can be had beside
    another (`stacks_with_others`, `exclusivity_group`, BR-RAT-073).
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        _senior_with_conditions(brazos, plan)
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
    terms = response.data["discounts"]["offered"][0]["terms"]
    assert terms["eligibility_summary"] == "Age 65+"
    assert terms["enrolment_mode"] == "apply_and_approve"
    assert terms["verification_method"] == "annual_recertification"
    assert terms["proof_required"] is True
    assert terms["accepted_proof_kinds"] == ["government_id", "birth_certificate"]
    assert terms["proof_before_first_reduction"] is True
    assert terms["recertification_months"] == 12
    assert terms["recertification_notice_days"] == 60
    assert terms["lapse_behaviour"] == "notify_then_drop"
    assert terms["applies_to"] == "whole_bill"
    assert terms["applies_to_service"] is None
    assert terms["applies_to_charge_codes"] == []
    assert terms["stacks_with_others"] is False
    assert terms["exclusivity_group"] == "assistance"
    assert terms["stacking_precedence"] == 10
    # Money at DISPLAY 2 beside its CHAR(3) currency (hard rule 2), and the
    # SIX-place stored figure never reaches the wire — a client that cannot see
    # `20.000000` cannot do arithmetic on it.
    assert terms["cap_per_bill_display"] == "20.00"
    assert terms["currency"] == "USD"
    assert "20.000000" not in str(terms)
    # ⚠ NULL IS UNCAPPED AND STAYS NULL. `0.00` would say the discount reduces
    # nothing — DEF-277's distinction, one section across.
    assert terms["cap_per_year_display"] is None
    assert terms["cap_lifetime_display"] is None
    # BR-RAT-074 — the floor's DEFAULT is a real statement: to zero, never
    # below, because a negative bill is a CREDIT.
    assert terms["bill_floor_amount_display"] == "0.00"


# ── TC-12 · A CONDITION IS RECORDED; NOTHING CHECKS IT, AND IT SAYS SO ────
def test_cr034_s7_tc12__eligibility_is_stated_as_recorded_never_as_enforced(brazos, dana):
    """⚠ **THE LOAD-BEARING CASE.** `eligibility_rule` is the DIS-02 rule
    builder's document and **nothing in this product evaluates it** — rating's
    own note (*"ADVISORY IN THIS SLICE: no code evaluates it"*) and
    `discount_services`' (*"It does not evaluate eligibility"*).

    So the payload says two things and never one: a rule IS recorded
    (`eligibility_rule_recorded`), and it is NOT checked
    (`eligibility_checked`, a stated absence in the same shape
    `DiscountResolution.modelled` uses). A screen given only the summary would
    render `Age 65+` as a condition the product enforces, and a clerk who
    believes that stops checking — the expensive direction of wrong.

    ⚠ **AND NO PROGRAMME-WIDE FIGURE IS SERVED.** `budget_cap` is seeded at
    $12,312 above and appears nowhere: it is tenant-wide, exactly like the
    `enrolled` count this payload already drops, and a number on a UNIT screen
    is read as this unit's however it is captioned.
    """
    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        _senior_with_conditions(brazos, plan)
        response = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
        no_rule = _pricing(dana, brazos, unit["id"])
    terms = response.data["discounts"]["offered"][0]["terms"]
    assert terms["eligibility_rule_recorded"] is True
    assert terms["eligibility_checked"]["served"] is False
    assert terms["eligibility_checked"]["reason"] == "no_code_evaluates_a_discount_eligibility_rule"
    # ⚠ THE RULE DOCUMENT ITSELF IS NOT SHIPPED. It is not a condition a screen
    # may render — it is an unevaluated document, and printing its clauses as
    # bullet points is the same false reassurance in a different font.
    assert "eligibility_rule" not in terms
    assert "age" not in str(terms)
    # No tenant-wide figure, by any name.
    assert "budget_cap" not in terms
    assert "12312" not in str(terms)
    assert "enrolled" not in str(response.data["discounts"]["offered"][0])
    # The same on the defaulted-period answer — the absence is not a property
    # of having been asked about a window.
    assert (
        no_rule.data["discounts"]["offered"][0]["terms"]["eligibility_checked"]["served"] is False
    )


# ── TC-13 · THE CONDITIONS RESOLVE ON THE SERVICE DATE, LIKE EVERYTHING ELSE ─
def test_cr034_s7_tc13__the_discount_version_follows_the_period_end(brazos, dana):
    """BR-RAT-007's service date reaches the DISCOUNT too.

    The plan, the rate schedules and the charge codes on this screen are all
    resolved on `as_of` (the period END). A discount whose terms were resolved
    on *today* instead would put one section of the answer on a different date
    from the rest — and the panel's own heading says which date the answer is
    about, so the two would contradict each other in writing.

    Worked: SENIOR is filed v1 *"Age 65+"* to 2026-07-31 and v2 *"Age 62+"*
    from 2026-08-01. July's answer says 65 and August's says 62.
    """
    from apps.rating import discounts as discount_models

    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        discount, first = _senior_with_conditions(
            brazos,
            plan,
            status=discount_models.VERSION_ACTIVE,
            effective_from=date(2026, 1, 1),
            effective_to=date(2026, 7, 31),
        )
        discount_models.DiscountVersion.objects.create(
            tenant=brazos,
            discount=discount,
            version_no=2,
            status=discount_models.VERSION_ACTIVE,
            discount_type="percentage",
            value=Decimal("15.000000"),
            currency="USD",
            eligibility_summary="Age 62+",
            effective_from=date(2026, 8, 1),
        )
        july = _pricing(
            dana, brazos, unit["id"], period_start="2026-07-01", period_end="2026-07-31"
        )
        august = _pricing(
            dana, brazos, unit["id"], period_start="2026-08-01", period_end="2026-08-31"
        )
    assert first.version_no == 1
    assert july.data["discounts"]["offered"][0]["terms"]["eligibility_summary"] == "Age 65+"
    assert july.data["discounts"]["offered"][0]["terms"]["version_no"] == 1
    # …and the terms name the date they were resolved on, so a reader never has
    # to assume the answer is about today (DEF-276's reasoning).
    assert july.data["discounts"]["offered"][0]["terms"]["resolved_on"] == "2026-07-31"
    assert august.data["discounts"]["offered"][0]["terms"]["eligibility_summary"] == "Age 62+"
    assert august.data["discounts"]["offered"][0]["terms"]["version_no"] == 2


# ── TC-14 · A DISCOUNT NOBODY HAS FILED STATES NO CONDITIONS ──────────────
def test_cr034_s7_tc14__a_discount_with_no_version_serves_null_terms(brazos, dana):
    """`terms: null` — *"this discount states no conditions"*, which is a
    different fact from *"it requires nothing"*, and a screen must be able to
    tell them apart. The row is still served: a discount the plan offers is on
    the list whether or not anyone has filled it in.
    """
    from apps.rating import discounts as discount_models

    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        unit = _unit_on(dana, brazos, plan)
        discount = discount_models.Discount.objects.create(
            tenant=brazos, code="MILITARY", name="Veteran discount", status="draft"
        )
        discount_models.PlanDiscountRule.objects.create(
            tenant=brazos, rate_plan=plan, discount=discount
        )
        response = _pricing(dana, brazos, unit["id"])
    offered = response.data["discounts"]["offered"]
    assert [row["code"] for row in offered] == ["MILITARY"]
    assert offered[0]["terms"] is None
    # …and no condition is invented to fill the hole.
    assert offered[0]["eligibility"] is None


# ── TC-15 · THE CONDITIONS ARE NOT PLAN CONTENT, SO THEY LEAVE THE SNAPSHOT ─
def test_cr034_s7_tc15__discount_terms_are_kept_out_of_the_plan_snapshot(brazos, dana):
    """⚠ **A SIDE EFFECT OF THIS CHANGE, CAUGHT AND CLOSED — and the guard
    lives here, beside the change that would cause it, rather than in the
    versioning suite that owns snapshots.**

    `rating.services._plan_snapshot` is `plan_detail` minus the three keys that
    are not plan CONTENT, and it is stored in every plan version row;
    `_plan_snapshot_diff` reports what changed between two of them and shows
    **eight** leaves before it starts counting.

    Serving `terms` from `plan_detail` put twenty-two more leaves per offered
    discount inside that blob. They belong to the DISCOUNT VERSION — a
    programme re-filed with a new proof list changes them while the plan is
    untouched — so the FIRST plan edit after this shipped would have diffed an
    old snapshot against a new one, reported the discount's conditions as what
    changed about the plan, and pushed the real edit off the row.

    So `terms` is popped, by the same test the other three keys pass: is it
    plan content? It is not. **The discount is still in the snapshot** — the
    binding IS plan content, and this asserts that too, so nobody "fixes" this
    by dropping the discounts.
    """
    from apps.rating import services as rating_services

    with tenant_ctx(brazos):
        plan = _plan_with_base_charges(brazos)
        _senior_with_conditions(brazos, plan)
        snapshot = rating_services._plan_snapshot(plan.id)
    assert [row["code"] for row in snapshot["discounts"]] == ["SENIOR"]
    assert "terms" not in snapshot["discounts"][0]
    # …and the binding facts a plan really does own are still there.
    assert snapshot["discounts"][0]["available_from"] is None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-034 (12-governance/11-change-requests.md, PO verbatim) + the PO's
#         re-scope of slice (b) + BR-RAT-007/069/088/108/110/114 + DEF-273 /
#         DEF-277 / DEF-431 / DEF-504 + CLAUDE.md rules 2 and 3
# generated: 2026-08-26 by the CR-034 (b) WORKEDMONTH lane · AMENDED 2026-08-26 by the CR-034 §7 DISCCOND lane (TC-11..TC-15 — the CONDITIONS to avail a discount are served as stored; the advisory rule is stated as UNCHECKED and its document is never shipped; the tenant-wide budget is absent; the service date reaches the discount VERSION; an unfiled discount serves `terms: null`)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: black✔ ruff✔ · pytest tests/test_cr034b_unit_resolution_display.py → 19 PASS✔ (14 before the §7 lane)
#        · pytest tests/test_w5_unit_reads.py + test_w5_move_in_out_cases.py → 36 PASS✔
#        · 10-scripts/03-golden-verify.py 33 PASS / 0 FAIL, unchanged before and after✔
#        · pytest tests -m golden → 23 passed / 1 xfailed, unchanged✔
#        · every case proved RED first under nine backend mutations in a `cp -a`
#          copy under the lane scratchpad, never the shared tree (r11 step 2d)
#        · TC-11..TC-14 proved RED first under six FURTHER backend mutations in six
#          parallel `cp -a` copies, never the shared tree (budget served beside the
#          caps · the advisory rule reported CHECKED · the rule document shipped ·
#          the six-place cap on the wire · `as_of` no longer reaching the discount
#          version · an unfiled discount served `{}` instead of null), and TC-15
#          under a seventh (`terms` left inside `_plan_snapshot`)
# exceptions: E-A NO GT FIGURE IS REPRODUCED HERE AND THAT IS THE ASSERTION —
#         this endpoint computes no money, so it has no golden case; TC-7 pins
#         that `minimum_charges` holds no derived total, no `min()` and no
#         "effective" floor, because which floor wins is BR-RAT-016/028
#         (PROPOSED on GT-13, not frozen) · E-A the WORKED MONTH is still not
#         served and TC-9 pins that it still says so (OQ-363, unchanged: the PO
#         re-scoped away from it and neither of its two blockers moved) · E-A
#         the CONTRACT absence cites NO id because no open question covers it
#         yet — one is OWED and is REPORTED to the PO rather than minted here
#         (prime directive; DEF-445), which is why G38's uncited count reads
#         73 against a baseline of 72 · E-A the three period refusals reuse
#         existing catalogue keys rather than minting new ones (G32 is a
#         ratchet at zero with no register); three precise sentences are owed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

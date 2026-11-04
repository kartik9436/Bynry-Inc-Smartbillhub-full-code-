# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 (EP-CUS-02 S19 Move-In) · US-CUS-005 (S20 Move-Out) ·
#           US-TEN-019 (the fixture task 5.11 declares)
#           Screens: S19 (steps 1–5) · S20 (steps 1–6, BR-SHL-046)
#           ⚠ NO STORY OWNS MOVE-IN STEP 3/4 OR THE MOVE-OUT IMPACT SCREEN —
#           hard-won law 8, reported by the W4 and W5 lanes before this one and
#           still owed. B18 proposes them; 05-user-stories.md carries none.
# Rules:    BR-CUS-017 (one occupying account per unit, ever) · BR-CUS-018 (a
#           new account is a draft until something activates it) · BR-CUS-021
#           (reads commit through metering's batch path) · BR-CUS-024 (deposit
#           carry-forward) · BR-CUS-025 as amended (the deposit settles
#           EVERYTHING outstanding) · BR-CUS-030/031 (move-out, the final-bill
#           handoff) · BR-CUS-041 (plan-change effective options) · BR-CUS-055
#           (status behaviour classes) · BR-CUS-056 (same-day move: the
#           OUTGOING account pays the move day) · BR-CUS-057 (deposit interest
#           — NOT BUILT) · BR-CUS-059 (autopay is RECORDED, never executed) ·
#           BR-CUS-081 (settle and refund the difference) · BR-CUS-082 (a debt
#           surviving closure is still chased; ladder restarts at TIER 1) ·
#           BR-CUS-089 (only a `strong` identity match may move money) ·
#           BR-CUS-096 (an open dispute HOLDS the excess) · BR-CUS-097 (a
#           sub-account's residue goes to its master) · BR-BIL-013 (the closed
#           settlement-path set) · BR-MET-036 (occupancy is DERIVED) ·
#           BR-MET-052 (negative usage — no auto-fix, by law) · BR-MET-105a
#           (the owner is a party; the column does not exist) · BR-MET-107 (an
#           unbanked export credit is applied to the FINAL BILL) · BR-SHL-046
#           (move-out is SIX steps) · CLAUDE.md hard rules 1 · 2 · 4 · 7
# Journeys: J08 (final-bill settlement — five paths, amended 2026-08-24 with
#           steps 1a/1b/2a/2b/3a/7a/7b)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.5.6 (TC-MVI-1
#           …10) · §5.6.6 (TC-MVO-1…10) · §5.5.7 / §5.6.7 (the seed rows)
# Tests:    this file (CR-030 W5 task 5.12) · the seed half is task 5.11 in
#           apps/customers/sample_data.py
# ───────────────────────────────────────────────────────
"""CR-030 W5 task 5.12 — B18's twenty declared move-in / move-out cases.

**THE CASES WERE DECLARED BEFORE THE CODE AND ARE NOT RE-AUTHORED HERE.**
B18 §5.5.6 and §5.6.6 state all twenty with their Given/When/Then; this file
writes the test CODE for them (process addendum r11, step 2c). Where a case
cannot be green on this tree, the test asserts **the gap, by name**, rather
than a weakened version of the case — and says which lane owns the missing
half. Six of the twenty are in that position and each says so in its own
docstring.

**NO ARITHMETIC OWNED ELSEWHERE IS RESTATED.** `tests/test_w5_move_out_
settlement.py` owns B19 §15.9.1's five landings and the pure `derive()`
figures; `tests/test_w5_move_out_endpoints.py` owns the four routes;
`tests/test_us_cus_004_005_move_in_out.py` owns the move/close mechanics;
`tests/test_w5_unit_reads.py` owns `unit_assets`/`unit_pricing`. This file
asserts what B18's TC ROWS ask, through those surfaces, and cites them rather
than copying them.

❄️ **WE-7 / GT-23 IS THE ONLY DEPOSIT FIGURE IN THIS FILE**: $150.00 held 14
months at the tenant's 2% simple rate earns $3.50, so $153.50 is applied. It is
finance-signed and frozen (B5); if a fixture here disagreed with a golden test
the fixture would be wrong.

⚠ **FOUR QUESTIONS ARE WITH THE PRODUCT OWNER AND NOTHING HERE ANSWERS ONE:**
what makes an identity match `strong`; whether unverified assistance evidence
grants or withholds a discount; what happens when a recertification date
lapses; who defines the discount programmes. TC-MVI-3 touches the first and
asserts only the CONSEQUENCE the signed rule states (a non-`strong` match may
not move money), never the definition.
"""

import dataclasses
from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import move_out_settlement as mos
from apps.customers import sample_data as customers_sample
from apps.customers import service_request_reads as sr_reads
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.metering import validation as metering_validation
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — W1/W2 shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    audit_rows,
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: E402,F401

# DEF-CUS-10093 (PO 2026-10-13, option B): the final-bill draft is isolated
# here — this suite tests the close; see tests/move_out_draft_isolation.py.
pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("move_out_draft_isolated")]

D = Decimal

# ── ❄️ WE-7 / GT-23, frozen 2026-08-08 — the only deposit figures here ──────
DEPOSIT_HELD = D("150.00")
DEPOSIT_INTEREST = D("3.50")
APPLIED = D("153.50")

#: B18 §5.6.7's two OQ fixtures, by their own worked numbers.
NAKAMURA_OWED = D("142.30")  # BR-CUS-081 → refund 11.20
NAKAMURA_REFUND = D("11.20")
RIDGE_OWED = D("328.70")  # BR-CUS-082 → SHORT 175.20, ladder restarts at TIER 1
RIDGE_SHORT = D("175.20")

MOVE_OUT_DAY = "2026-07-18"
NEXT_DAY = "2026-07-19"


# ══════════════════════════════════════════════════════════════════════════
# FIXTURE HELPERS — the world each case starts from
# ══════════════════════════════════════════════════════════════════════════
def _plan(tenant, name="Residential Standard", service_code="electric"):
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


def _unit(actor, tenant, *, label="Unit A", premises=None, with_plan=True):
    premises = premises or make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    if with_plan:
        metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _occupant(actor, unit, *, name="Sarah Miller", opened_at="2026-07-01", autopay=False):
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": opened_at,
            "autopay": autopay,
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _with_deposit(account_id, amount=DEPOSIT_HELD):
    """❄️ WE-7's principal onto an existing account.

    ⚠ **THERE IS NO SERVICE DOOR FOR THIS AND THAT IS THE POINT.**
    `services.REFUSED_FIELDS` types `deposit_on_file` as *"a LOOKUP from the
    plan deposit schedule (US-CUS-007)"*, so neither `create_account` nor
    `update_account` accepts it; only `create_from_import` does. A test that
    needs a held deposit on an already-created account therefore writes the
    column, and says so here rather than implying a door exists. It is the same
    posture `tests/test_w5_move_out_settlement.py` takes for the same reason.
    """
    customers_models.Account.objects.filter(id=account_id).update(deposit_on_file=amount)


def _publish_settlement_reads(monkeypatch, *, interest=DEPOSIT_INTEREST, disputed=D("0.00")):
    """BR-CUS-057's accrual and BR-CUS-096's dispute store, PUBLISHED.

    Both are unbuilt on this tree, so every settlement holding a deposit states
    NO LANDING (`deposit_interest_not_accrued` · `open_disputes_not_readable`).
    A case whose Then is a landing has to reach past that wall to assert
    anything at all, so it patches the two resolvers and **the patch itself is
    the statement that the wall is a wiring fact, not a permanent refusal**.
    Cases whose Then IS the wall (TC-MVO-6) never patch.
    """
    real_resolve = mos.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            # CR-059 CS-20 (2026-09-03) — the accrual seam states the day it
            # accrues to, so the stub takes two arguments. Ignored here: these
            # cases are about the move-in/move-out flow, and ❄️ GT-61's 22.25
            # is asserted against the real engine in its own suite.
            return lambda _account_id, _as_of=None: interest
        if (module, attribute) == ("billing", "open_dispute_total"):
            return lambda _account_id: disputed
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(mos.seams, "resolve", _resolve)


_CAPTURE = {
    "channel": "physical_form",
    "applicant_kind": "person",
    "applicant_name": "Alvarez, Rosa",
    "applicant_email": "rosa@example.test",
    "address_as_given": "3450 Oak Ridge Dr",
    "property_type": "standalone_owner_occupied",
    "what_they_said": "I'm moving in on the 26th",
}


def _sr_series(tenant, opening=44):
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": opening},
    )


# ══════════════════════════════════════════════════════════════════════════
# B18 §5.5.6 — THE TEN MOVE-IN CASES
# ══════════════════════════════════════════════════════════════════════════
def test_tc_mvi_1__a_unit_with_a_live_account_is_not_selectable_and_says_why(brazos, marcus):
    """**TC-MVI-1** — *"a unit with a live account → step 1 search → it is NOT
    SELECTABLE, and the reason is shown."*

    BR-CUS-017 as §5.5.4 states it: *"At most one live account per unit, ever.
    A unit with a live account is refused, never silently taken over."* The
    refusal must NAME the holder, because *"the reason is shown"* is half the
    case — a bare "not available" teaches the clerk nothing.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        holder = _occupant(marcus, unit, name="Thompson, R.")
        with pytest.raises(errors.BizError) as caught:
            _occupant(marcus, unit, name="Kwan, Michael")
    error = caught.value
    assert error.code == errors.BIZ_STATE
    assert error.br_ref == "BR-CUS-017"
    # The reason NAMES the account that holds it — that is what the screen shows.
    assert error.params["account_no"] == holder["account_no"]


def test_tc_mvi_2__a_returning_customer_s_153_50_is_NOT_carried_and_the_gap_is_named(
    brazos, marcus
):
    """**TC-MVI-2** — *"a returning customer with $153.50 on a closed account →
    step 4 → the carry-forward is OFFERED."*

    ⚠ **THIS CASE CANNOT BE GREEN AS WRITTEN, AND THE GAP IS THE ASSERTION.**
    `services.MOVE_IN_UNAVAILABLE` carries `deposit_carry_forward_unavailable`
    (BR-CUS-024) on EVERY move-in, and B18 §5.5.5 lists `GET /customers/{id}/
    deposit-position` as **NEW** — it does not exist. So the $153.50 is neither
    offered nor moved.

    What IS asserted is the direction that matters: the outgoing account's
    ❄️ WE-7 principal of $150.00 stays where it is and the incoming account
    opens holding **0.00**. Money never moves on an unbuilt path — §5.5.4's own
    reason for the rule is *"Requires a strong identity match, because money
    moves"*, and the safe state while nothing can check the match is that
    nothing moves at all.

    ⚠ **AND ONE REASON STRING IS NOW FALSE — REPORTED, NOT EDITED HERE.**
    `MOVE_IN_UNAVAILABLE`'s `customer_not_linked` says *"the first-class
    `customers` entity has no table"*. It HAS one (`customers_models.Customer`,
    `db_table = "customers"`, migration 0005) and `REFUSED_FIELDS` was corrected
    for exactly this on 2026-08-11 while this list was not. Hard-won law 1: the
    code is right and the reason is stale. `apps/customers/services.py` is not
    this lane's file.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        leaving = _occupant(marcus, unit, name="Osei, Grace")
        _with_deposit(leaving["id"])
        customers_services.move_out(marcus, leaving["id"], {"moved_out_on": MOVE_OUT_DAY})
        arriving = customers_services.move_in(
            marcus,
            leaving["id"],
            {
                "account_type": "residential",
                "status": "active",
                "opened_at": NEXT_DAY,
                "contact": {"full_name": "Osei, Grace"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Osei, Grace", account_type="residential"
                ),
            },
        )
        codes = {warning["code"] for warning in arriving["warnings"]}
        opened = customers_models.Account.objects.get(id=arriving["id"])
        closed = customers_models.Account.objects.get(id=leaving["id"])
    assert "deposit_carry_forward_unavailable" in codes
    assert (
        next(
            w["br_ref"]
            for w in arriving["warnings"]
            if w["code"] == "deposit_carry_forward_unavailable"
        )
        == "BR-CUS-024"
    )
    assert closed.deposit_on_file == DEPOSIT_HELD, "the closed account's own money moved"
    assert opened.deposit_on_file == D("0"), "a deposit was carried on an unbuilt path"
    # ❄️ WE-7: what WOULD be offered, stated so the figure is on the record.
    assert DEPOSIT_HELD + DEPOSIT_INTEREST == APPLIED


def test_tc_mvi_3__a_weak_match_may_not_move_money_and_strong_is_not_defined_here(brazos, dana):
    """**TC-MVI-3** — *"a WEAK identity match → step 4 → carry-forward is
    refused with its reason — money never moves on a weak match."*

    BR-CUS-089 is the signed half and it is asserted: only a `strong` match may
    move money, and the tier is the CLERK'S — there is no automatic matcher in
    this product (`suggest_customer_matches`, DEF-632/638). `weak` and
    `probable` both read `may_move_money: False`; `strong` reads True.

    ⚠ **WHAT MAKES A MATCH `strong` IS WITH THE PRODUCT OWNER AND IS NOT
    DECIDED HERE.** This case asserts the CONSEQUENCE the rule states, never the
    definition — picking one would resolve an open question by choosing a value.
    """
    with tenant_ctx(brazos):
        _sr_series(brazos)
        customer = customers_models.Customer.objects.create(
            tenant=brazos, display_name="Alvarez, Rosa"
        )
        seen = {}
        for tier in sr.MATCH_TIERS:
            request = sr.create_request(dana, dict(_CAPTURE))
            sr.link_customer(
                dana, request.id, customer_id=customer.id, tier=tier, basis="name + address"
            )
            applicant = sr_reads.detail(request.id)["applicant"]
            seen[tier] = applicant["customer_match"]["may_move_money"]
            assert applicant["customer_match"]["tier"] == tier
    assert seen == {"strong": True, "probable": False, "weak": False}


def test_tc_mvi_4__all_four_assets_are_listed_grouped_and_the_reading_half_is_a_gap(brazos, dana):
    """**TC-MVI-4** — *"a unit with 2 meters + 1 sub-meter + 1 PV inverter →
    step 3 → all four listed, grouped; a reading is asked for the billable
    meters only."*

    The FIRST half is served: `unit_assets` groups on `asset_types.category`
    (BR-AST-004), so the four land **2 / 1 / 1** and the PV inverter sits under
    behind-the-meter even though its `parent_asset` qualifier calls it a sub.
    `tests/test_w5_unit_reads.py::test_w5_tc1` owns the qualifier-versus-category
    argument and it is not repeated here.

    ⚠ **THE SECOND HALF IS A STATED ABSENCE (DEF-495).** *"a reading is asked
    for the billable meters only"* needs BR-RAT-081's metered/unmetered
    declaration, which has **no reader in this product**, so `reading_expected`
    serves `{served: false}` and the panel cannot say which of the four to read.
    Asserted as the gap, because a panel that guessed would ask for a reading
    off a PV inverter.
    """
    from apps.assets import services as asset_services

    with tenant_ctx(brazos):
        unit = _unit(dana, brazos, with_plan=False)
        master = a_meter(dana, "M-7001", unit_id=unit["id"])
        a_meter(dana, "M-7002", unit_id=unit["id"], service="water", uom="kgal")
        for asset_no, kind in (("SM-8801", "sub_meter"), ("PV-3300", "pv")):
            asset_services.create_asset(
                dana,
                {
                    "type": kind,
                    "asset_no": asset_no,
                    "service": "electric",
                    "unit": "kWh",
                    "parent_asset_no": master["asset_no"],
                    "unit_id": unit["id"],
                    "install_date": "2026-01-05",
                    **(
                        {"read_method": "walk_by", "multiplier": "1"} if kind == "sub_meter" else {}
                    ),
                },
            )
        panel = metering_selectors.unit_assets(unit["id"])
    assert panel["counts"]["total"] == 4
    assert (panel["counts"]["meters"], panel["counts"]["sub_meters"]) == (2, 1)
    assert panel["counts"]["behind_the_meter"] == 1
    assert panel["reading_expected"]["served"] is False
    assert panel["reading_expected"]["reason"] == "metered_declaration_has_no_reader"


def test_tc_mvi_5__the_prorated_worked_month_is_not_computed_and_the_payload_says_so(brazos, dana):
    """**TC-MVI-5** — *"a prorated first period → step 4 → tier thresholds are
    shown SCALED, and the screen says they are."*

    ⚠ **NOT GREEN, AND THE REASON IS TWO INDEPENDENT BLOCKERS (DEF-670,
    OQ-363).** §5.5.5 requires step 4 to show *"one worked month"* and **nothing
    in this product prices a plan outside a bill run** — `engine.price_bill` /
    `price_period` are keyed on an ACCOUNT, which a move-in draft does not have
    — and **no signed rule states the consumption** a worked month would be
    priced at. Scaled tier thresholds are a property of a priced period, so
    they cannot be drawn either.

    `unit_pricing` therefore serves `worked_month: {served: false, reason:
    "no_service_prices_a_plan_outside_a_bill_run", tracks: "OQ-363"}` and the
    plan, its schedules, charge codes and taxes ship around it. Asserted as the
    absence: a number invented here is the number a customer quotes back.
    """
    with tenant_ctx(brazos):
        unit = _unit(dana, brazos)
        pricing = metering_selectors.unit_pricing(unit["id"])
    assert pricing["worked_month"]["served"] is False
    assert pricing["worked_month"]["reason"] == "no_service_prices_a_plan_outside_a_bill_run"
    assert pricing["worked_month"]["tracks"] == "OQ-363"


def test_tc_mvi_6__a_reading_below_the_prior_is_an_ERROR_not_the_warning_b18_draws(brazos):
    """**TC-MVI-6** — *"a reading below the prior → step 3 → ACCEPTED, a meter
    exception is raised, and the screen says so."*

    ⚠ **B18 AND BR-MET-052 DISAGREE, AND THIS CASE PINS THE DISAGREEMENT RATHER
    THAN PICKING A SIDE.** §5.5.4's move-in rule is *"Reading below the prior —
    DOES NOT BLOCK. Raises a meter exception and says so."* The metering engine
    classifies the same pair as `negative_usage` at severity **ERROR** with
    `auto_fix: False` — *"never, by law"* — and offers `investigate / override /
    reject`. An ERROR is a meter exception that says so, and it is NOT
    "accepted".

    Worked on the fixture's own register: prior **42,180**, current **42,000**,
    drop **180** on a 5-digit register (span 100,000). The drop is far under
    50% of the span, so this is not the GT-14 rollover path (OQ-009, PO R7) —
    it is the plain negative-usage case, and **no consumption is returned**,
    because a value the engine cannot compute honestly must not be invented.

    Which rule governs the move-in wizard is a question for the PO; this test
    asserts what the engine does and names the conflict.
    """
    context = metering_validation.ReadContext(
        value=D("42000"),
        prior_value=D("42180"),
        multiplier=D("1"),
        register_digits=5,
        unit="kWh",
    )
    consumption, outcome = metering_validation.compute_consumption(context)
    assert consumption is None, "a consumption was invented for a reading below the prior"
    assert outcome.rule == metering_validation.RULE_NEGATIVE_USAGE
    assert outcome.severity == metering_validation.ERROR
    assert outcome.detail["drop"] == "180"
    assert outcome.detail["auto_fix"] is False  # BR-MET-052 — never, by law
    assert outcome.detail["resolutions"] == ["investigate", "override", "reject"]


def test_tc_mvi_7__autopay_is_RECORDED_and_no_method_can_be_attached_to_collect_with(
    brazos, marcus
):
    """**TC-MVI-7** — *"autopay ticked → step 5 → the copy says RECORDED, never
    'we will collect'."*

    BR-CUS-059 as §5.5.4 states it: *"Recorded, not executed, in this release.
    The screen must not imply money will be taken."* The backend half of *"not
    executed"* is stronger than a copy rule and is what this asserts: the flag
    is stored, and **`autopay_method_id` is a REFUSED field** — a PROPOSED-SCHEMA
    column that is not built — so there is no instrument on the account for
    anything to collect against. The screen cannot lie about a collection the
    product has no way to make.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, autopay=True)
        row = customers_models.Account.objects.get(id=account["id"])
        with pytest.raises(errors.ValidationError) as caught:
            customers_services.update_account(marcus, account["id"], {"autopay_method_id": "x"})
    assert row.autopay is True
    assert customers_services.REFUSED_FIELDS["autopay_method_id"][0] == "BR-CUS-059"
    refusal = caught.value.field_errors[0]
    assert refusal["field"] == "autopay_method_id"
    assert refusal["params"]["br_ref"] == "BR-CUS-059"


def test_tc_mvi_8__a_parked_move_in_has_nowhere_to_be_stored_and_that_is_measured(brazos):
    """**TC-MVI-8** — *"parked at step 2 → reopening the row → opens at step 2
    with the step-1 payload intact."*

    ⚠ **NOT GREEN: THERE IS NO WIZARD STORE, AND THIS TEST MEASURES THAT RATHER
    THAN DESCRIBING IT.** Park-and-resume (task 5.1) was built on
    `service_requests` — `waiting_on`, `park_note`, `parked_at` are columns on
    that table and on no other in the customers app — so a move-in **in
    progress** is not a row anywhere and neither its step nor its step-1 payload
    can survive the clerk closing the tab. `MoveInWizard.tsx`'s own exception E4
    says the same in the other territory and renders `Park` disabled with this
    reason.

    That is also why B18 §5.5.7's two DRAFT move-ins (`Alvarez, Rosa` and
    `Osei, Grace`) are seeded as SERVICE REQUESTS — §5.5.7 itself links them to
    `SR-26-0044` and `SR-26-0039`. The seed half of that is asserted by
    `test_task_5_11__eleven_rows_are_declared_five_move_ins_two_of_them_drafts`.
    """
    parkable = {
        model.__name__
        for model in customers_models.__dict__.values()
        if isinstance(model, type)
        and issubclass(model, customers_models.models.Model)
        and getattr(model, "_meta", None) is not None
        and not model._meta.abstract
        and {"waiting_on", "parked_at"} <= {f.name for f in model._meta.get_fields()}
    }
    assert parkable == {"ServiceRequest"}, (
        "a second parkable table appeared — TC-MVI-8's gap may have closed, or a "
        "move-in draft is being stored somewhere nobody declared"
    )
    # …and the request IS the draft: `park` is the door, and it is the ONLY one.
    assert callable(sr.park)


def test_tc_mvi_9__the_same_day_move_is_refused_and_the_next_day_is_taken(brazos, marcus):
    """**TC-MVI-9** — *"a same-day move → both wizards → the outgoing account
    pays the move day, the incoming starts the NEXT day from the same reading —
    no gap, no overlap."*

    BR-CUS-056 (CONFIRMED, PO OQ-060 option (a)). Worked on the journey's own
    dates: the outgoing account closes **2026-07-18** and bills through it; a
    move-in opening on **2026-07-18** is REFUSED and one opening **2026-07-19**
    is taken. `tests/test_us_cus_004_005_move_in_out.py` owns the boundary
    guard's mechanism and the race; this case asserts the pair B18 draws.

    ⚠ *"from the same reading"* is NOT asserted, because it cannot be: BR-CUS-021
    routes reads through metering's S28 batch path and `final_reads`/
    `initial_reads` are REFUSED inputs on both flows, so no reading travels
    between the two accounts here at all.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        leaving = _occupant(marcus, unit)
        closed = customers_services.move_out(marcus, leaving["id"], {"moved_out_on": MOVE_OUT_DAY})
        with pytest.raises(errors.BizError) as caught:
            customers_services.move_in(
                marcus,
                leaving["id"],
                {
                    "account_type": "residential",
                    "status": "active",
                    "opened_at": MOVE_OUT_DAY,
                    "contact": {"full_name": "Kwan, Michael"},
                    # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                    # customer identifies nobody, and this fixture's own name went in above.
                    # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                    "customer": identity_fixtures.customer_block(
                        "Kwan, Michael", account_type="residential"
                    ),
                },
            )
        arriving = customers_services.move_in(
            marcus,
            leaving["id"],
            {
                "account_type": "residential",
                "status": "active",
                "opened_at": NEXT_DAY,
                "contact": {"full_name": "Kwan, Michael"},
                # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
                # customer identifies nobody, and this fixture's own name went in above.
                # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    "Kwan, Michael", account_type="residential"
                ),
            },
        )
    assert closed["closed_at"] == MOVE_OUT_DAY
    assert caught.value.br_ref == "BR-CUS-056"
    assert arriving["opened_at"] == NEXT_DAY
    assert arriving["moved_in_after_account_no"] == closed["account_no"]


def test_tc_mvi_10__a_plan_override_moves_the_UNIT_s_plan_with_actor_and_from_to(
    brazos, marcus, audit_rows
):
    """**TC-MVI-10** — *"a plan overridden at step 4 → commit → THE UNIT'S PLAN
    IS UPDATED TOO, with actor, timestamp and from→to."*

    §5.5.4: *"Plan comes from the unit. An override UPDATES THE UNIT — the two
    never disagree."* There is no account-side plan record to disagree with it:
    BR-CUS-029 was SUPERSEDED by the PO on 2026-08-11 (*"from unit you will
    derive the plan"*), so the override has exactly one destination and
    `change_plan` reaches it through metering's own `assign_unit_plan` — the
    reviewed cross-module write path (B2 §2). Customers writes neither table.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        before = metering_selectors.unit_row(unit["id"]).rate_plan_id
        target = _plan(brazos, name="Residential Assisted")
        customers_services.change_plan(
            marcus,
            account["id"],
            {
                "rate_plan_id": str(target.id),
                "effective_on": NEXT_DAY,
                "reason": "step 4 override — the applicant qualifies",
            },
        )
        after = metering_selectors.unit_row(unit["id"]).rate_plan_id
        changed = [row for row in audit_rows if row["action"] == "plan.changed"]
    assert before != after and str(after) == str(target.id), "the UNIT's plan did not move"
    assert len(changed) == 1
    assert changed[0]["after"]["assigned_from"] == NEXT_DAY
    assert changed[0]["after"]["source"] == "change_plan"
    assert changed[0]["before"]["rate_plan_id"] != changed[0]["after"]["rate_plan_id"]
    assert changed[0]["actor_user_id"] is not None  # the actor, on the row


# ══════════════════════════════════════════════════════════════════════════
# B18 §5.6.6 — THE TEN MOVE-OUT CASES
# ══════════════════════════════════════════════════════════════════════════
def test_tc_mvo_1__328_70_against_153_50_is_SHORT_175_20_and_step_4_goes_live(
    brazos, marcus, monkeypatch
):
    """**TC-MVO-1** — *"outstanding $328.70, deposit $153.50 → step 3 → SHORT
    $175.20 in the accent, and the wizard CANNOT ADVANCE until a decision is
    made."*

    B18 §5.6.7's `A-11024 · Ridge Coffee Co.` — the shortfall proof, and OQ
    fixture 2 of 2. `328.70 − 153.50 = 175.20`. The backend half of *"cannot
    advance"* is `step_4_live`: §15.9.1 makes step 4 live in exactly ONE landing
    and greyed-and-named in the other four, so a `short` close is the only one
    that can reach `shortfall_decision` at all — every other landing refuses it
    by name.
    """
    _publish_settlement_reads(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, name="Ridge Coffee Co.")
        _with_deposit(account["id"])
        payload = mos.settlement_for(marcus, account["id"], final_bill=RIDGE_OWED)
    assert payload["everything_outstanding"]["total"]["display"] == "328.70"
    assert payload["what_is_applied"]["total"]["display"] == "153.50"
    assert payload["landing"] == mos.LANDING_SHORT
    assert payload["verdict"]["shortfall"]["display"] == "175.20"
    # CLAUDE.md rule 2 as re-signed 2026-08-22 — stored to 4, displayed to 2.
    assert payload["verdict"]["shortfall"]["stored"] == "175.2000"
    assert payload["step_4_live"] is True


def test_tc_mvo_2__the_fourth_option_is_greyed_WITH_ITS_REASON_never_hidden(brazos, marcus):
    """**TC-MVO-2** — *"the shortfall screen → option ④ → rendered DISABLED with
    the landlord-agreement reason, never hidden."*

    ⚠ **THE REASON HAS CHANGED SINCE B18 WROTE THE CASE, AND THE CASE'S SHAPE
    HAS NOT.** Task 5.8 said option ④ is disabled with BR-CUS-068's
    landlord-agreement reason; **BR-CUS-097 (PO 2026-08-24) signed a DIFFERENT
    transfer** — a sub-account's unpayable residue to its MASTER — and that one
    has a resolvable target, so the option is enabled exactly when a master
    resolves. Here no master covers the premises, so it is greyed, and BOTH
    refusals are named: BR-CUS-097's unsettled no-master case, and BR-MET-105a's
    `premises.owner_customer_id`, which is CONFIRMED and **has no column on this
    tree**.

    BR-SHL-025: a forbidden control is disabled WITH its reason. All three paths
    are still OFFERED — none of them is hidden. (`write_off` left the set on
    2026-10-12 by PO ruling, *"MOVE-OUT DOES NOT WRITE OFF"*; see TC-MVO-5.)
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        row = customers_models.Account.objects.get(id=account["id"])
        options = {opt["path"]: opt for opt in mos.shortfall_path_options(row)}
    assert set(options) == set(mos.SHORTFALL_PATHS)  # nothing hidden
    transfer = options[mos.SHORTFALL_TRANSFER]
    assert transfer["enabled"] is False
    assert transfer["reason"], "option ④ was greyed with no reason at all"
    assert "no master account covers this unit's premises" in transfer["reason"]
    assert "premises.owner_customer_id" in transfer["reason"]
    assert [t["target"] for t in transfer["targets"]] == list(mos.TRANSFER_TARGETS)


def test_tc_mvo_3__the_ladder_restarts_at_TIER_1_and_never_reaches_a_disconnect(
    brazos, marcus, monkeypatch, audit_rows
):
    """**TC-MVO-3** — CORRECTED 2026-08-24. *"`pursue it` chosen → close → the
    $175.20 stays chased after the close and the ladder RESTARTS AT TIER 1 (not
    the tier reached), and NO DISCONNECTION ESCALATION is offered on a closed
    account."*

    BR-CUS-082, PO verbatim *"(b) continue, ladder restarts"*, closing OQ-346.
    The stub this case used to carry (`NotImplementedError("OQ-346")`) is gone.

    ⚠ **AND J08 STEP 2b'S OPEN HALF IS ASSERTED AS OPEN.** BR-CUS-097 moves a
    sub-account's residue to its master and BR-CUS-082 restarts the ladder
    against the debt; **neither ruling says who is chased** — the departed
    sub-account holder or the master. The decision therefore states the subject
    as UNRESOLVED, and a green assertion here that named either party would mean
    somebody chose. W7 owns the ladder and must not build both readings.
    """
    _publish_settlement_reads(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, name="Ridge Coffee Co.")
        _with_deposit(account["id"])
        decision = mos.shortfall_decision(
            marcus,
            account["id"],
            {"final_bill": RIDGE_OWED, "path": mos.SHORTFALL_COLLECT},
        )
    assert decision["amount"]["display"] == "175.20"
    dunning = decision["dunning"]
    assert dunning["chased"] is True
    assert dunning["restarts_at_tier"] == 1
    assert dunning["escalates_to_disconnection"] is False
    assert dunning["br_ref"] == "BR-CUS-082"
    # ⚠ AMENDED 2026-08-27 — `OQ-366` IS CLOSED AND THE SUBJECT IS NO LONGER
    # UNRESOLVED. PO verbatim: *"Sub account is closed when debt is trasnfer
    # hence we now follow with owner for debt"*. It inherits the same day's
    # qualification of BR-CUS-097 — the transfer is CLERK-INITIATED — so the
    # ladder follows the master ONLY for a residue a clerk tied back. THIS
    # CASE IS A `COLLECT`: nothing was tied back, so the $175.20 stays here
    # and no master is named anywhere in the answer. The transferred half is
    # `tests/test_oq366_ladder_follows_the_master.py`.
    assert dunning["subject"] == "the closed account itself"
    assert "subject_unresolved" not in dunning
    assert "master_account" not in dunning
    assert "OQ-580" in dunning["oq_580_master_ladder_position_unsigned"]
    # Hard rule 7 — the decision is a money action and writes its row.
    assert [r["action"] for r in audit_rows].count("account.move_out.shortfall_decided") == 1


def test_tc_mvo_4__153_50_settles_142_30_and_refunds_11_20_with_both_movements_audited(
    brazos, marcus, monkeypatch, audit_rows
):
    """**TC-MVO-4** — CORRECTED 2026-08-24. *"deposit $153.50 > owed $142.30 →
    step 3 → the $142.30 is SETTLED from the deposit and $11.20 is REFUNDED;
    the account closes at zero and NO FINAL BILL STANDS. Both movements write
    `audit_log`."*

    BR-CUS-081, PO verbatim *"a) settle and refund the $11.20"*, closing OQ-347.
    B18 §5.6.7's `A-11208 · Nakamura, Yuki`, and OQ fixture 1 of 2. The rejected
    reading — refund the whole deposit and leave $142.30 standing — is asserted
    against directly: `settled_from_deposit` is **142.30**, not 0.00, and
    `bill_stands` is False.

    ⚠ **NEITHER MOVEMENT IS POSTED, AND THE RESULT SAYS SO.** `payments.refunds`
    types `payment_id NOT NULL` with no account column (OQ-195), so a deposit
    excess has no row to become here. (Since OQ-248 closed on 2026-09-30 the
    FINAL BILL's issue credits the excess to customer credit; this decision
    itself still posts nothing.) The `audit_log` row is this decision's trace.
    """
    _publish_settlement_reads(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, name="Nakamura, Yuki")
        _with_deposit(account["id"])
        decision = mos.refund_disposition(
            marcus,
            account["id"],
            {"final_bill": NAKAMURA_OWED, "method": mos.REFUND_ACH},
        )
    assert decision["settlement"]["landing"] == mos.LANDING_REFUND_DUE
    assert decision["settled_from_deposit"]["display"] == "142.30"
    assert decision["refund_amount"]["display"] == str(NAKAMURA_REFUND)
    assert decision["bill_stands"] is False
    assert decision["persisted"] is False
    assert {entry["code"] for entry in decision["execution_unavailable"]} == {
        "refund_has_no_row_to_become",
        "deposit_settlement_not_posted",
    }
    assert [r["action"] for r in audit_rows].count("account.move_out.refund_disposed") == 1


def test_tc_mvo_5__write_off_is_not_a_move_out_path(brazos, marcus, audit_rows):
    """**TC-MVO-5** — *"`write it off` above threshold → commit → refused for a
    clerk; a supervisor may; a reason is required; `audit_log` written."*

    ⚠ **SUPERSEDED BY PO RULING 2026-10-12** (decision log, *"MOVE-OUT DOES NOT
    WRITE OFF"*), verbatim: *"we will not write off at the time of move out;
    these charges remain outstanding on the account and followup is done as per
    outstanding rules"* — and *"fianance or system admin will do it seperately
    later"*. So the case's Then is now: write-off is **not offered** at move-out
    and a POST of it is **refused by name for everybody** with nothing written.
    The threshold and the approver chain stay where they always were, in
    Payments (BR-PAY-020), reached later and separately.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        row = customers_models.Account.objects.get(id=account["id"])
        options = {opt["path"]: opt for opt in mos.shortfall_path_options(row)}
        with pytest.raises(errors.BizError) as exc:
            mos.shortfall_decision(
                marcus, account["id"], {"final_bill": D("94.45"), "path": "write_off"}
            )
    assert "write_off" not in options
    assert exc.value.message_key == "customers.move_out.write_off_not_at_move_out"
    assert "account.move_out.shortfall_decided" not in [r["action"] for r in audit_rows]


def test_tc_mvo_6__nothing_settles_without_a_final_read_and_the_gap_says_which(brazos, marcus):
    """**TC-MVO-6** — *"no final read → commit → REFUSED — nothing settles
    without one."*

    ⚠ **THE REFUSAL EXISTS AND IT IS NOT THE ONE B18 DESCRIBES.** No read
    reaches the settlement at all: billing publishes no per-account final-bill
    total, so `settlement_for` takes the figure from the CALLER and, absent it,
    states **no landing** and serves `final_bill_not_stated`. That refusal is
    about the BILL, not the READ — a clerk who states a bill computed from
    nothing gets a landing.

    **NO SEAM IS PATCHED HERE**: this case's Then *is* the wall, so patching
    past it would test the opposite of the case. Also asserted: `move_out`
    itself does **not** refuse a close with no committed reads — it warns
    `final_reads_not_committed` (BR-CUS-021) and closes — so *"nothing settles
    without one"* is true of the SETTLEMENT and false of the CLOSE. Reported;
    which of the two B18 means is a question for the PO.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        payload = mos.settlement_for(marcus, account["id"])
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})
    assert payload["landing"] is None
    assert mos.GAP_FINAL_BILL in payload["gaps"]
    assert payload["final_bill_stated_by_caller"] is False
    # …and the CLOSE went through anyway, warning about the very reads B18
    # says nothing settles without.
    assert closed["closed_at"] == MOVE_OUT_DAY
    assert "final_reads_not_committed" in {w["code"] for w in closed["warnings"]}


def test_tc_mvo_7__an_estimated_final_read_has_nowhere_to_make_a_settlement_provisional(
    brazos, marcus, monkeypatch
):
    """**TC-MVO-7** — *"an estimated final read → the row → `estimated` in
    amber, and the settlement is PROVISIONAL on screen."*

    ⚠ **NOT GREEN: A SETTLEMENT CANNOT KNOW HOW ITS READS WERE OBTAINED, AND
    THIS TEST MEASURES THAT RATHER THAN DESCRIBING IT.** `MoveOutSettlement`'s
    terms are the prior balance, the final bill, the deposit, its interest, the
    account credit, the export credit, the siblings and the disputes — **and
    nothing about read provenance**. The final bill arrives as a bare figure
    STATED by the caller, so an estimated read and a walked one produce
    byte-identical payloads: there is no `provisional` flag to set and no field
    a screen could read one from.

    Driven on B18 §5.6.7's own `A-11780 · Delgado, Pilar`, whose FINAL READ cell
    is the amber `estimated` — the row the case is written about. The amber cell
    is metering's read status (BR-MET-044) and reaches the LIST; it does not
    reach the money. Owed by whichever lane wires read provenance into the
    handoff; named, not faked.
    """
    _publish_settlement_reads(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, name="Delgado, Pilar")
        _with_deposit(account["id"])
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("318.60"))
    terms = {field.name for field in dataclasses.fields(mos.MoveOutSettlement)}
    assert not any(
        word in name for name in terms for word in ("read", "estimat", "provision")
    ), f"a read-provenance term appeared on the settlement — TC-MVO-7 may be servable: {terms}"
    assert "provisional" not in str(payload)
    assert payload["landing"] == mos.LANDING_SHORT  # 318.60 − 153.50 = 165.10
    assert payload["verdict"]["shortfall"]["display"] == "165.10"


def test_tc_mvo_8__the_unit_is_DERIVED_vacant_and_the_owner_who_pays_has_no_column(brazos, marcus):
    """**TC-MVO-8** — *"close committed → after → the unit's occupancy is
    decided EXPLICITLY, never left implicit."*

    BR-MET-036 decides it from the account's behaviour CLASS: a terminal status
    does not occupy, so the unit derives Vacant and keeps its plan for the next
    occupant. It is never manually set — which is the *"never left implicit"*
    half, from the other direction.

    ⚠ **AND THE PANEL'S OTHER SENTENCE STILL CANNOT BE PRINTED.** OQ-350 is
    CLOSED → BR-MET-105 (PO 2026-08-24, *"(a) the owner/landlord"*): the
    **$30.50/month** base charge on the empty unit is the OWNER'S. BR-MET-105a
    makes the owner a real party through `premises.owner_customer_id` — **and
    that column does not exist on this tree**, measured again here. So a
    shortfall cannot be posted to an owner and the empty-unit charge has no
    payer; W7 task 7.15 owns it, and *per empty unit versus once per premises*
    is still unruled and is not assumed.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})
        after = metering_selectors.unit_row(unit["id"])
        row = customers_models.Account.objects.get(id=account["id"])
        owner = mos.owner_target_for(row)
        premises_fields = {
            field.name for field in after.premises._meta.get_fields()  # noqa: SLF001
        }
    assert after.rate_plan_id is not None, "the unit lost its plan on close"
    assert row.status.behavior_class == "terminal"
    assert customers_services.is_occupying(row.status) is False
    assert owner["available"] is False and owner["br_ref"] == "BR-MET-105a"
    assert "owner_customer" not in " ".join(premises_fields), (
        "BR-MET-105a's column appeared — TC-MVO-8's gap may have closed and this "
        "test, the settlement's refusal and W7 task 7.15 all need re-reading"
    )


def test_tc_mvo_9__no_settlement_path_updates_or_deletes_anything_hard_rule_4(
    brazos, marcus, monkeypatch, audit_rows
):
    """**TC-MVO-9** — *"an issued final invoice → any path → NO UPDATE, NO
    DELETE — corrections are new rows."*

    CLAUDE.md hard rule 4, and J08 step 7's invariance. Two halves, both
    asserted:

      · the CLOSE refuses to move behind an issued bill — the guard is written
        and its billing seam is unwired, so `move_out` warns rather than
        checking (`tests/test_us_cus_004_005_move_in_out.py` drives the seam to
        prove the refusal itself);
      · the SETTLEMENT writes nothing at all. There is no `final_settlements`
        table (US-BIL-011 §5 names one; B2 and its addenda carry none), so every
        decision reports `persisted: False` and rides its `audit_log` row —
        which is an append-only new row by construction, never an edit.

    ⚠ **"EXACTLY ONE SETTLEMENT PER CLOSE" (BR-BIL-013) THEREFORE HOLDS WITHIN A
    CALL AND NOT ACROSS CALLS**, because there is no row to be unique. Named,
    because a reader could otherwise take J08 step 7a's assertion as enforced
    here. J08 7a is unaffected: the enum is still FIVE.
    """
    _publish_settlement_reads(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit)
        _with_deposit(account["id"])
        first = mos.refund_disposition(
            marcus, account["id"], {"final_bill": NAKAMURA_OWED, "method": mos.REFUND_ACH}
        )
        second = mos.refund_disposition(
            marcus, account["id"], {"final_bill": NAKAMURA_OWED, "method": mos.REFUND_ACH}
        )
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})
    assert first["persisted"] is False and second["persisted"] is False
    assert len(mos.MONEY_LANDINGS) == 5, "the five-landing enum grew"
    # Two calls, two APPEND-ONLY audit rows and no stored settlement to edit.
    assert [r["action"] for r in audit_rows].count("account.move_out.refund_disposed") == 2
    assert "final_bill_handoff_not_persisted" in {w["code"] for w in closed["warnings"]}


def test_tc_mvo_10__autopay_survives_the_close_because_nothing_cancels_it(brazos, marcus):
    """**TC-MVO-10** — *"autopay enrolled → close → the SCHEDULE IS CANCELLED,
    and the screen said it would be."*

    ⚠ **NOT GREEN, AND THIS IS THE ONE WITH A CUSTOMER CONSEQUENCE.** §5.6.5's
    Payments panel promises *"scheduled autopay CANCELLED, not left to fire at a
    closed account"*. On this tree the flag is still True after the close and
    nothing anywhere cancels anything: `accounts.autopay` is a boolean,
    `autopay_method_id` is a PROPOSED-SCHEMA column that is not built, and
    `MOVE_OUT_UNAVAILABLE` names no autopay item at all — so the close does not
    even WARN about it, which is the part worth reporting.

    Asserted as it is, not as it should be: the flag survives, and the
    move-out's own list of what it could not do is silent on the subject.
    Nothing collects today (TC-MVI-7 asserts why), so no money is at risk **in
    this build** — the risk arrives the day a collection path does, and this
    test goes red the moment somebody starts cancelling, which is what it is
    for.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, unit, autopay=True)
        closed = customers_services.move_out(marcus, account["id"], {"moved_out_on": MOVE_OUT_DAY})
        row = customers_models.Account.objects.get(id=account["id"])
    assert row.autopay is True, "autopay is now cancelled on close — B18 §5.6.5 is served"
    codes = {w["code"] for w in closed["warnings"]}
    assert not any("autopay" in code for code in codes), (
        "the move-out now names autopay in what it could not do — TC-MVO-10's "
        "silent half has been closed and this assertion must be re-read"
    )


# ══════════════════════════════════════════════════════════════════════════
# TASK 5.11 — THE SEED, AND WHAT IT COULD NOT PLANT
# ══════════════════════════════════════════════════════════════════════════
def test_task_5_11__eleven_rows_are_declared_five_move_ins_two_of_them_drafts():
    """B18 §5.5.7's five and §5.6.7's six, declared as rows a reader can count.

    Two of the five move-ins are DRAFTS — §5.5.7's own *"park-and-resume proof"*
    — and each links to the service request that IS the draft, because
    TC-MVI-8's measurement shows there is nowhere else for one to live.
    """
    assert len(customers_sample.W5_MOVE_INS) == 5
    assert len(customers_sample.W5_MOVE_OUTS) == 6
    drafts = [row for row in customers_sample.W5_MOVE_INS if row["drawn_no"] is None]
    assert len(drafts) == 2
    assert {row["request_ref"] for row in drafts} == {"SR-26-0044", "SR-26-0039"}


def test_task_5_11__the_move_out_step_count_is_SIX_not_the_four_b18_prints():
    """BR-SHL-046 (PO 2026-08-24, closing DEF-648): move-out is **SIX** steps.

    §5.6.2's column header reads `STEP (of 4)` and §5.6.7's cells read `4 of 4`,
    `3 of 4`, `2 of 4`, `1 of 4`. That count is SUPERSEDED, so the fixture
    carries **6** and keeps each drawn numerator — *"a skipped step keeps its
    number"*. Seeding `of 4` would put a superseded count into the demo three
    days after it was ruled.
    """
    assert {row["step_of"] for row in customers_sample.W5_MOVE_OUTS} == {6}
    assert {row["step"] for row in customers_sample.W5_MOVE_OUTS} == {1, 2, 3, 4}
    # Step 4 is CONDITIONAL and still one of the six — the backend half.
    assert mos.STEP_4_LIVE_IN == frozenset({mos.LANDING_SHORT})


def test_task_5_11__the_two_OQ_fixtures_carry_their_ruled_figures():
    """Task 5.11's own parenthesis — *"the two OQ fixtures"*.

    OQ-347 → BR-CUS-081 on `A-11208 · Nakamura, Yuki`: `153.50 − 142.30 =
    11.20` refunded. OQ-346 → BR-CUS-082 on `A-11024 · Ridge Coffee Co.`:
    `328.70 − 153.50 = 175.20` short, still chased, ladder restarts at TIER 1.
    Both figures are the PO's own and neither is computed here.
    """
    rows = {row["key"]: row for row in customers_sample.W5_MOVE_OUTS}
    nakamura = rows["mvo-nakamura"]
    assert (nakamura["applied"], nakamura["outstanding"]) == ("153.50", "142.30")
    assert nakamura["refund"] == "11.20" and nakamura["br_ref"] == "BR-CUS-081"
    assert nakamura["landing"] == mos.LANDING_REFUND_DUE
    ridge = rows["mvo-ridge-coffee"]
    assert (ridge["applied"], ridge["outstanding"]) == ("153.50", "328.70")
    assert ridge["shortfall"] == "175.20" and ridge["br_ref"] == "BR-CUS-082"
    assert ridge["landing"] == mos.LANDING_SHORT
    # ❄️ WE-7 / GT-23 — the applied figure is the frozen pair, not a new number.
    assert D(nakamura["applied"]) == DEPOSIT_HELD + DEPOSIT_INTEREST == APPLIED


def test_task_5_11__every_drawn_landing_is_recorded_as_a_GAP_not_a_number():
    """⚠ **NO SEEDED SETTLEMENT PRODUCES A FIGURE, AND EACH ROW SAYS SO.**

    Two independent walls, both measured on this tree: BR-CUS-057's accrual is
    unbuilt, so an account holding a deposit states NO LANDING; and
    `deposit_on_file` is a REFUSED field on both editing doors, so a seeded
    account cannot be given a deposit at all. Every row drawing a settlement
    therefore carries `lands_on: GAP` with the reason — *seed it and let it gap*
    rather than tuning the fixture until a number appears.
    """
    drawn = [row for row in customers_sample.W5_MOVE_OUTS if row["landing"]]
    assert len(drawn) == 4  # refund_due ×2 · settled ×1 · short ×1
    report = {entry["key"]: entry for entry in _report_rows()}
    for row in drawn:
        entry = report[row["key"]]
        assert entry["lands_on"] == "GAP"
        assert "BR-CUS-057" in entry["lands_on_detail"]
        assert "REFUSED field" in entry["lands_on_detail"]


def test_task_5_11__the_six_move_outs_span_three_landings_and_name_the_other_two():
    """`MONEY_LANDINGS` is a CLOSED set of five; B18's six rows draw THREE.

    `refund_due` (two rows), `settled` (one) and `short` (one); the remaining
    two rows have no final read and so no landing at all. **`refused_excess` and
    `refused_other_debt` are drawn by neither**, which is not an omission in the
    seed: J08 step 1a puts `refused_excess` on `F=ACC-1059` (153.50 against
    140.38 with 48.00 disputed → 13.12 HELD) and B19 §15.9.5 puts
    `refused_other_debt` on a sibling-debt case, and both live where their
    figures are.

    ⚠ **`refused_excess` COULD NOT BE SEEDED EVEN IF A ROW DREW IT** — J08 step
    7b(i), measured 2026-08-24: nothing in this repository stores a disputed
    AMOUNT. And `metering`'s `disputed_at` on a METER READ is a QUANTITY in
    dispute, not an amount; wiring it here would hold a customer's refund
    because somebody queried a dial.
    """
    drawn = {row["landing"] for row in customers_sample.W5_MOVE_OUTS if row["landing"]}
    assert drawn == {mos.LANDING_REFUND_DUE, mos.LANDING_SETTLED, mos.LANDING_SHORT}
    assert set(mos.MONEY_LANDINGS) - drawn == {
        mos.LANDING_REFUSED_EXCESS,
        mos.LANDING_REFUSED_OTHER_DEBT,
    }
    assert mos.GAP_REASONS[mos.GAP_DISPUTES_UNREADABLE]["br_ref"] == "BR-CUS-096"
    assert "METER READ" in mos.GAP_REASONS[mos.GAP_DISPUTES_UNREADABLE]["detail"]


def test_task_5_11__four_rows_have_no_seat_and_one_of_them_is_the_headline():
    """⚠ **THE FIXTURE IS FOUR ROWS SHORT AND THE REASON IS SEATS.**

    `2201 Cedar Ln` · `12 Harbour View` · `17 Brambling Ct` · `44 Larkspur Way`
    are not seeded premises, and every one of the 62 seeded units already holds
    an account except `SCW-U-207 · 3450 Oak Ridge Dr`, which must stay VACANT —
    it is what makes `SR-26-0039` resolve `served_vacant`. `premises` and
    `units` are metering's tables (B1), so customers cannot create one.

    **One of the four is `A-11208 · Nakamura, Yuki` — BR-CUS-081's `refund
    $11.20`, half of task 5.11's own "two OQ fixtures".** So the ruling that
    closed OQ-347 is provable in this file and **is not plantable in the demo**.
    Reported here rather than left to be found on the screen.
    """
    seatless = {
        row["customer"]
        for rows in (customers_sample.W5_MOVE_INS, customers_sample.W5_MOVE_OUTS)
        for row in rows
        if row["blocker"] == "no_seat"
    }
    assert seatless == {
        "Baptiste, Marie",
        "Reyes, Antonio",
        "Fitzgerald, Sean",
        "Nakamura, Yuki",
    }
    detail = customers_sample.W5_BLOCKERS["no_seat"]
    assert "metering's tables" in detail and "CR030_PREMISES" in detail


def test_task_5_11__two_account_numbers_disagree_with_b18_and_carry_both():
    """⚠ **A FIXTURE SLIP, CARRIED RATHER THAN RENUMBERED.**

    §5.6.7 draws `A-11603 · Thompson, R.` and `A-11024 · Ridge Coffee Co.`;
    W2 task 2.10 planted the same customers at the same units as `A-11996` and
    `A-11801`. `A-11996` is also §5.7.6's own number for `Haddad, Nour`'s new
    transfer account, so one string names two accounts across two sections.

    Renumbering a planted account would move `Thompson, R.` out from under
    `SR-26-0046` and `Ridge Coffee Co.` out from under `SR-26-0048` and
    §5.1.2's `4 accounts` sub-link — and §5.6.7's own closing line is that a
    lane which breaks that cross-tab consistency has broken the fixture. So
    both numbers ride each row and the slip is REPORTED for the fixture owner.
    """
    rows = {row["key"]: row for row in customers_sample.W5_MOVE_OUTS}
    assert (rows["mvo-thompson"]["drawn_no"], rows["mvo-thompson"]["seeded_no"]) == (
        "A-11603",
        "A-11996",
    )
    assert (rows["mvo-ridge-coffee"]["drawn_no"], rows["mvo-ridge-coffee"]["seeded_no"]) == (
        "A-11024",
        "A-11801",
    )


def _report_rows():
    """`w5_move_fixture_report()` without a database — the declaration half.

    The report resolves each row against the tenant's accounts, which needs a
    seeded tenant; the four assertions above are about the DECLARATION and its
    reasons, so they read the same dispositions from the fixture rows directly.
    """
    out = []
    for kind, rows in (
        ("Move-in", customers_sample.W5_MOVE_INS),
        ("Move-out", customers_sample.W5_MOVE_OUTS),
    ):
        for row in rows:
            out.append(
                {
                    "kind": kind,
                    "key": row["key"],
                    "blocker": row["blocker"],
                    "lands_on": "GAP" if row.get("landing") else None,
                    "lands_on_detail": (
                        customers_sample.W5_SETTLEMENT_GAP if row.get("landing") else None
                    ),
                }
            )
    return out

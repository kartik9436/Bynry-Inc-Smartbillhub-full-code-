# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-004 / US-CUS-007 (EP-CUS-02 S19 Move-In step 4)
#           Screens: S19 step 4
# Change:   CR-030 W5 tasks 5.4 (eligibility panel) and 5.5 (deposit
#           carry-forward, `strong` match only)
# Rules:    BR-CUS-024 · BR-CUS-025 · BR-CUS-054 · BR-CUS-057 · BR-CUS-089 ·
#           BR-RAT-043 · BR-RAT-076 · BR-RAT-112 · CLAUDE.md rules 1, 2, 7
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.3.4 · §5.5.4 ·
#           §5.5.5 · §5.5.6 (TC-MVI-2, TC-MVI-3)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""W5 — move-in step 4's eligibility panel and its deposit carry-forward.

**EVERY FIGURE HERE IS SOMEBODY ELSE'S.** ❄️ WE-7 / GT-23's frozen pair —
$150.00 principal + $3.50 interest = **$153.50** — is B18 TC-MVI-2's own number
and B18 §5.5.2's `carried $153.50` DEPOSIT cell. Nothing in this file invents a
figure, which is what makes it a contract rather than a mirror.

RED-FIRST PROOF (r11 step 2d / hard-won law 7). **Every guard below was broken
FIRST, run, and its failure quoted VERBATIM, before it was trusted green.** Seven
mutations, each applied to a pristine copy and reverted from it in the same loop
(`scratchpad/redharness.py`); the file was md5-compared against the pristine at
the end and **no `# BREAK:` marker survives in this commit** (DEF-666).

  1. the carry-forward gate reading "any recorded match" instead of BR-CUS-089's
     `strong` →
        E       assert True is False
        E       assert True is False
        FAILED ...::test_tc_mvi_3_a_weak_match_is_refused_and_no_money_moves
        FAILED ...::test_a_probable_match_is_refused_too_because_only_strong_moves_money
  2. an ABSENT match defaulting to `strong` →
        E       assert True is False
        FAILED ...::test_a_move_in_with_no_recorded_match_is_refused_not_defaulted
  3. `_deposit_interest` reading an unwired seam as `Decimal("0")` — the single
     most tempting line in the module →
        E       AssertionError: assert '0.00' is None
        E       assert True is False
        FAILED ...::test_an_unreadable_interest_gaps_it_never_zeroes_it
        FAILED ...::test_the_total_refuses_to_foot_while_any_position_gaps
  4. `eligibility_panel` refusing a claim (the "surely an unverified claim should
     block" mistake) →
        E       core.errors.BizError: BIZ-COMPLETENESS (x)
        FAILED ...::test_eligibility_never_blocks_service
  5. `_claimed_rows` computing `reduces_bill_now` from `rule.verified` alone,
     dropping BR-RAT-076's `proof_before_first_reduction` half →
        ⛔ **1 passed, 22 deselected — THE GUARD DID NOT GO RED.**
     ⚠ **AND THAT IS THE MOST USEFUL LINE IN THIS FILE, so it is kept rather
     than quietly fixed away.** The fixture only ever built the two ENDS of
     BR-RAT-076's range — proof-first-and-unverified (`verified False`,
     `proof_before True`) and automatic (`verified True`, `proof_before False`)
     — and both formulas agree on both. A check whose output cannot distinguish
     pass from fail is worse than no check, because it is trusted (CLAUDE.md
     law 11, twice over). The missing case is the MIDDLE one, and it is a real
     programme shape rather than a test contrivance: **proof IS demanded and the
     reduction starts before it arrives** — *"we will check your income
     statement, and meanwhile you get the discount."* `CAPGRACE` below is that
     shape, and with it the same mutation gives
        E       assert False is True
        FAILED ...::test_br_rat_076_decides_per_programme_not_globally
  6. the refused branch still serving the figure →
        E       AssertionError: assert {'stored': '1...ay': '153.50'} == {'stored': No...isplay': None}
        E         Differing items:
        E         {'stored': '153.5000'} != {'stored': None}
        E         {'display': '153.50'} != {'display': None}
        FAILED ...::test_tc_mvi_3_a_weak_match_is_refused_and_no_money_moves
  7. the refusal writing no audit row →
        E       AssertionError: assert 'customer.deposit_carry_forward.refused' in
                ['reference.seeded', 'reference.seeded', ...]
        FAILED ...::test_both_branches_write_audit_log

⚠ **THE TENANT-ISOLATION CASE RUNS UNDER THE NON-SUPERUSER PROBE ROLE.** A plain
ORM query inside `tenant_ctx` runs as the app's superuser role and **bypasses
RLS unconditionally**, so an assertion made that way is VACUOUS and has fooled
this repo before (DEF-101). The case at the bottom carries `requires_postgres`
and asserts through `assert_rls_scoped` / `assert_no_foreign_rows_anywhere`.

⚠ **AND THE TABLE IT PROVES IS `discount_enrolments`, NOT `account_discounts`.**
The lane wrote no migration: every one of B18 §5.5.5's six `account_discounts`
facts already has a column on the CR-013 table a bill run actually reads, and a
second grant store would show a subsidy that reduces nothing. The reasoning is
in `apps/customers/discounts.py`'s docstring and the defect row is reported
rather than written (this lane may not edit `12-governance/*`).
"""

from datetime import date
from decimal import Decimal

import pytest

from core import errors

from apps.customers import discounts
from apps.customers import models as customers_models
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import discount_services
from apps.rating import discounts as rating_discounts
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.isolation_helpers import (
    assert_no_foreign_rows_anywhere,
    assert_rls_scoped,
    requires_postgres,
    rls,  # noqa: F401 — fixture
    rls_probe_role,  # noqa: F401 — fixture
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    dana,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

D = Decimal

# ── ❄️ WE-7 / GT-23, frozen: $150.00 held 14 months at 2% simple = $3.50 ────
DEPOSIT_HELD = D("150.00")
DEPOSIT_INTEREST = D("3.50")
CARRIED = D("153.50")  # B18 TC-MVI-2 and §5.5.2's `carried $153.50`

#: The tables `discount_enrolments` lives beside. `account_discounts` is
#: DELIBERATELY ABSENT — see the module docstring.
GRANT_TABLES = ("discounts", "discount_versions", "discount_enrolments")


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through real services (DEF-658: never the ORM)
# ═══════════════════════════════════════════════════════════════════════════
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


def _unit(actor, tenant, *, label="Unit A", premises=None, service_code="electric"):
    """⚠ `service_code` is a parameter because the two fixture tenants do not
    enable the same services: Brazos Bend has Electric + Water, the isolation
    tenant `lonestar` has WATER ONLY. A hard-coded `electric` here refuses on
    `metering.service_not_enabled` for lonestar, which is the tenant every
    isolation case needs."""
    premises = premises or make_premises(actor, services_available=[service_code])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant, service_code=service_code).id)}
    )
    metering_services.ensure_service_point(unit["id"], service_code)
    return unit


def _occupant(actor, tenant, unit, *, name="Alvarez, Rosa"):
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": name},
            # `BR-CUS-1024` (PO 2026-09-01) — the door refuses an account whose
            # customer identifies nobody, and this fixture's own name went in above.
            # ONE shape for every fixture in the suite: tests/identity_fixtures.py.
            "customer": identity_fixtures.customer_block(name, account_type="residential"),
        },
    )


def _the_accounts_customer(account_id):
    """The `customers` row the account was OPENED with, read off its link.

    ⚠ AMENDED 2026-10-01 (billing red triage). Both call sites read
    `link_customer(account_id=…, display_name=name)` and took its `id`. Since
    `BR-CUS-1023`/`1024` (PO 2026-09-01: *"Without identifier we cannot create
    Customer ID or master account ot regular account"*) a name alone creates no
    customer — `link_customer` answers `id: None` with
    `customer_not_identified` — so every case asked for a deposit position of
    customer `None` and got `NotFoundError` (12 red since the sweep
    `46b03f834`; `identity_kind_required` before it). The account already HAS
    its customer: `_occupant` opens it with `identity_fixtures.customer_block`,
    and the account door writes the `customer_accounts` link (BR-CUS-054). That
    link is the one the deposit position walks, so it is the one read here.
    """
    link = customers_models.CustomerAccount.objects.get(account_id=account_id)
    return {"id": str(link.customer_id)}


def _returning_customer(
    actor, tenant, *, deposit=DEPOSIT_HELD, name="Alvarez, Rosa", service_code="electric"
):
    """B18 §5.5.7 row 3 — `Alvarez, Rosa`, the draft carrying `carried $153.50`.

    A prior account, CLOSED through the real move-out flow (never a status
    write — `_apply_status_change` refuses those), holding the frozen $150.00,
    linked to a `customers` row through `customer_accounts` (BR-CUS-054).
    """
    unit = _unit(actor, tenant, label="3450 Oak Ridge Dr", service_code=service_code)
    prior = _occupant(actor, tenant, unit, name=name)
    customers_models.Account.objects.filter(id=prior["id"]).update(deposit_on_file=deposit)
    customer = _the_accounts_customer(prior["id"])
    customers_services.move_out(actor, prior["id"], {"moved_out_on": "2026-08-15"})
    return customer, prior


def _seed_sr_series(tenant, opening=44, *, if_absent=False):
    """⚠ `if_absent` exists because a second call with `update_or_create` REWINDS
    the counter, and the series carries a per-tenant unique index on the number
    it hands out — so a test that records two matches used to die on
    `UNIQUE constraint failed: service_requests.tenant_id, service_requests.
    request_no`. Rewinding a live number series is DEF-634's own hazard in
    miniature; the fixture must not do in a test what the product refuses."""
    if (
        if_absent
        and tenancy_models.NumberSeries.objects.filter(
            tenant=tenant, series="service_request"
        ).exists()
    ):
        return
    tenancy_models.NumberSeries.objects.update_or_create(
        tenant=tenant,
        series="service_request",
        defaults={"format": "SR-{YY}-{0000}", "next_number": opening},
    )


def _record_match(actor, tenant, customer, tier, *, basis="ID number and date of birth"):
    """BR-CUS-089's stored tier — written by a HUMAN through the only door that
    writes one, `service_request_service.link_customer`.

    ⚠ Written through the SERVICE, not by an ORM update, precisely because the
    thing under test is that the tier is somebody's recorded judgement with a
    confirmer beside it. An ORM write would prove the read and skip the rule.
    """
    _seed_sr_series(tenant, if_absent=True)
    request = sr.create_request(
        actor,
        {
            "channel": "physical_form",
            "applicant_kind": "person",
            "applicant_name": "Alvarez, Rosa",
            "address_as_given": "3450 Oak Ridge Dr",
            "what_they_said": "I'm moving into somewhere",
        },
    )
    sr.link_customer(actor, request.id, customer_id=customer["id"], tier=tier, basis=basis)
    return request


def _programme(tenant, actor, *, code="SENIOR", proof_required=True, proof_first=None, mode=None):
    """One tenant-authored assistance programme, through rating's own doors.

        This is the answer to *"who defines the programmes"* asserted rather than
        described: `create_discount` (identity + version 1) → `submit` → `approve`
        → `activate` is a TENANT act, and there is no seeded list anywhere.

    ⚠ **`proof_required` AND `proof_before_first_reduction` ARE TWO KNOBS, NOT
        ONE, AND THAT IS THE WHOLE POINT** — BR-RAT-076 stores them separately and a
        fixture that tied them together made this file's BR-RAT-076 case unable to
        fail. Proved: mutating `_claimed_rows` to drop the
        `proof_before_first_reduction` half left the case GREEN (`1 passed`) while
        the fixture only ever produced the two ends of the range. The third
        combination — **proof IS demanded, but the reduction starts before it
        arrives** — is the one that separates them, and it is a real programme
        shape: *"we will check your income statement, and meanwhile you get the
        discount."*

        The contradictory middle (automatic enrolment WITH mandatory proof) is
        refused by rating's own gate 1 (BR-RAT-076) and is not built here.
    """
    if proof_first is None:
        proof_first = proof_required
    proof_kinds = ["income_statement"] if proof_required else None
    row = discount_services.create_discount(
        actor,
        {
            "code": code,
            "name": f"{code} assistance",
            # `CR-166-BRC10`: a CODE (or label) of the utility's own owner list.
            "programme_owner": "Billing",
            "funding_source": "utility",
            "discount_type": "percentage",
            "value": "10",
            "applies_to": rating_discounts.SCOPE_WHOLE_BILL,
            "effective_from": date(2026, 1, 1),
            "enrolment_mode": mode
            or (
                rating_discounts.ENROLMENT_APPLY_AND_APPROVE
                if proof_required
                else rating_discounts.ENROLMENT_AUTOMATIC
            ),
            "verification_method": (
                rating_discounts.VERIFY_ONE_TIME_PROOF
                if proof_required
                else rating_discounts.VERIFY_AUTOMATIC
            ),
            "proof_required": proof_required,
            "proof_before_first_reduction": proof_first,
            "accepted_proof_kinds": proof_kinds,
            "change_reason": "initial",
        },
    )
    version = rating_discounts.DiscountVersion.objects.get(
        tenant=tenant, discount_id=row["id"], version_no=1
    )
    discount_services.submit_discount_version(actor, version.id)
    # PO ruling 2026-10-03 (1): approval is the last act — no Activate.
    discount_services.approve_discount_version(actor, version.id)
    # Ruling 2: only an account whose plan carries the programme can claim it,
    # so the programme is offered on the plan every `_unit` here is put on.
    discount_services.attach_discount_to_plan(actor, _plan(tenant).id, row["id"])
    return row


# ═══════════════════════════════════════════════════════════════════════════
# 1 · WHAT IS SETTLED — B18 §5.3.4: eligibility NEVER blocks service
# ═══════════════════════════════════════════════════════════════════════════
def test_eligibility_never_blocks_service(brazos, marcus):
    """B18 §5.3.4, verbatim: *"**Never blocks service** — only the discount."*

    Asserted on the input that would tempt a gate — an account with NO claim,
    no evidence and no verification of anything. Nothing raises, nothing is
    withheld, and the panel says so as a CONSTANT rather than as a computed
    field: a computed `False` is one refactor from becoming `True`.

    Two CONFIRMED rating rules say the same from the other side and both are
    quoted on the payload: BR-RAT-043 (*advisory-with-audit in v1*) and
    BR-RAT-112 (PO 2026-08-21, *"dont refuse … we have to keep flexibility"*).
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        panel = discounts.eligibility_panel(marcus, account["id"])
    assert panel["eligibility"]["blocks_service"] is False
    assert "BR-RAT-043" in panel["eligibility"]["br_ref"]
    assert "BR-RAT-112" in panel["eligibility"]["br_ref"]
    assert "Never blocks service" in panel["eligibility"]["detail"]
    # The account exists and claims nothing. That is an ANSWER, not an absence.
    assert panel["claimed"] == []
    assert discounts.GAP_ENROLMENT_UNWIRED not in panel["gaps"]


def test_a_draft_move_in_gets_the_panel_and_an_honest_reason_it_cannot_hold_a_claim(brazos, marcus):
    """B18 §5.5.2 draws two of five move-in rows with `ACCOUNT` reading
    *"— draft"*. A claim IS the grant and `discount_enrolments.account_id` is
    NOT NULL, so the wizard cannot hold one — and the panel says that instead
    of pretending."""
    with tenant_ctx(brazos):
        panel = discounts.eligibility_panel(marcus, None)
    assert panel["eligibility"]["blocks_service"] is False
    assert panel["claim_recordable"] is False
    assert panel["draft"]["code"] == "claim_lands_at_commit"
    assert panel["claimed"] is None  # not [] — nobody has asked yet


def test_household_size_is_refused_by_name_not_accepted_and_dropped(brazos, marcus):
    """B18 §5.3.4 asks for `household size` and the product has no column for
    it anywhere. DEF-632's shape: a clerk who types a field and watches it
    vanish was told a lie by the form."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.ValidationError) as exc:
            discounts.claim_assistance(marcus, account["id"], "any-programme", household_size=4)
    assert exc.value.message_key == "customers.eligibility.householdSizeHasNoColumn"
    with tenant_ctx(brazos):
        panel = discounts.eligibility_panel(marcus, account["id"])
    codes = {row["code"] for row in panel["unavailable"]}
    assert discounts.GAP_NO_HOUSEHOLD_SIZE in codes


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHERE AN UNVERIFIED CLAIM LANDS — BR-RAT-076, per programme
# ═══════════════════════════════════════════════════════════════════════════
def test_br_rat_076_decides_per_programme_not_globally(brazos, marcus, dana):
    """The second of the four points this lane was asked to leave open, and it
    is RULED — twice, and not as one answer.

    BR-RAT-076 (CONFIRMED 2026-08-19): *"`proof_before_first_reduction` is a
    MONEY rule and is stored: true means an unverified enrolment reduces
    nothing and the bill is charged in full."* So the same unverified claim
    reduces a bill on one programme and not on another, and the difference is
    the PROGRAMME's stored setting — which is why searching for a single global
    rule found nothing.

    Both programmes are claimed against the same account with NO evidence at
    all, and neither claim is refused (B18 §5.3.4 again).
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        strict = _programme(brazos, dana, code="SENIOR", proof_required=True)
        # ⚠ DEF-RAT-9792 (2026-10-06) — CAPAUTO WAS AN *AUTOMATIC* PROGRAMME
        # CLAIMED THROUGH `claim_assistance`, AND THAT DOOR NOW REFUSES ONE: an
        # Automatic discount is the nightly sync's to grant and end (PO
        # 2026-10-03 ruling (3)), and a hand enrolment was ended overnight. The
        # case was never about the MODE — it is the programme that asks NO
        # proof, so its claim is `not_required` and reduces from the first
        # bill. Re-pointed to *apply and approve, no proof* (verification
        # automatic), which is a person's claim the door still takes and lands
        # exactly where BR-RAT-076 put CAPAUTO. The code is kept so every
        # assertion below reads unchanged.
        automatic = _programme(
            brazos,
            dana,
            code="CAPAUTO",
            proof_required=False,
            mode=rating_discounts.ENROLMENT_APPLY_AND_APPROVE,
        )
        # THE THIRD SHAPE, and it is the only one that separates the two halves:
        # proof IS demanded (so the enrolment lands `pending`, unverified) and
        # the reduction starts anyway.
        grace = _programme(brazos, dana, code="CAPGRACE", proof_required=True, proof_first=False)
        discounts.claim_assistance(dana, account["id"], strict["id"])
        discounts.claim_assistance(dana, account["id"], automatic["id"])
        discounts.claim_assistance(dana, account["id"], grace["id"])
        panel = discounts.eligibility_panel(marcus, account["id"])

    rows = {row["programme"]: row for row in panel["claimed"]}
    assert set(rows) == {"SENIOR", "CAPAUTO", "CAPGRACE"}
    # Proof-first, unverified → the claim STANDS and the bill is charged full.
    assert rows["SENIOR"]["proof_before_first_reduction"] is True
    assert rows["SENIOR"]["verified"] is False
    assert rows["SENIOR"]["reduces_bill_now"] is False
    assert "BR-RAT-076" in rows["SENIOR"]["reduces_bill_now_reason"]
    # Automatic → nothing to prove, so it reduces from the first bill.
    assert rows["CAPAUTO"]["verified"] is True  # `not_required` IS verified
    assert rows["CAPAUTO"]["reduces_bill_now"] is True
    assert rows["CAPAUTO"]["reduces_bill_now_reason"] is None
    # ⚠ THE CASE THAT MAKES THIS TEST ABLE TO FAIL. Unverified, exactly like
    # SENIOR — and it reduces the bill anyway, because THIS programme does not
    # put proof first. Read `verified` alone and the two are indistinguishable;
    # that mutation left this file green until CAPGRACE existed.
    assert rows["CAPGRACE"]["verified"] is False
    assert rows["CAPGRACE"]["proof_before_first_reduction"] is False
    assert rows["CAPGRACE"]["reduces_bill_now"] is True
    assert rows["CAPGRACE"]["reduces_bill_now_reason"] is None
    # And neither of them touched service.
    assert panel["eligibility"]["blocks_service"] is False


def test_the_claim_status_is_ratings_to_decide_and_is_served_in_its_own_five_values(
    brazos, marcus, dana
):
    """B18 §5.5.5's `status` has two values; the built column has five.

    Served verbatim rather than collapsed — mapping `rejected` onto *"pending
    verification"* would show a refused claim as one still being processed, and
    `expired` is exactly the lapse state BR-RAT-076 names. The divergence rides
    the payload so nobody has to notice it in a diff.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        strict = _programme(brazos, dana, code="SENIOR", proof_required=True)
        claimed = discounts.claim_assistance(dana, account["id"], strict["id"])
    assert claimed["claimed"] is True
    assert claimed["status"] == rating_discounts.VERIFICATION_PENDING
    assert claimed["status"] not in ("pending verification", "active")
    codes = {row["code"] for row in claimed["unavailable"]}
    assert discounts.GAP_STATUS_VOCABULARY in codes


def test_the_recertification_date_has_a_rule_and_no_chaser(brazos, marcus):
    """The third point, and it is HALF ruled — which is the finding.

    BR-RAT-076 names three lapse behaviours and `discount_versions.
    lapse_behaviour` stores which. NOTHING READS THE DATE. This asserts the
    absence is stated rather than left silent — the same shape as
    `move_out_settlement.held_excess_has_no_release_path`, which is the
    precedent this lane was pointed at.
    """
    with tenant_ctx(brazos):
        panel = discounts.eligibility_panel(marcus, None)
    row = next(
        item for item in panel["unavailable"] if item["code"] == discounts.GAP_NO_RECERT_CHASER
    )
    assert row["br_ref"] == "BR-RAT-076 (mechanism half)"
    assert "no runner, job, queue, timer or management command" in row["detail"]


def test_the_programmes_are_tenant_authored_and_not_a_seeded_list(brazos, marcus, dana):
    """The fourth point, and it is not open: `GET /discount-programmes` serves
    the tenant's OWN `discounts` rows, authored through rating's create /
    version / activate doors. A fresh tenant that has authored none gets none.
    """
    with tenant_ctx(brazos):
        assert discounts.discount_programmes(marcus)["programmes"] == []
        _programme(brazos, dana, code="SENIOR")
        served = discounts.discount_programmes(marcus)
    assert [row["code"] for row in served["programmes"]] == ["SENIOR"]
    assert served["eligibility"]["blocks_service"] is False


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE DEPOSIT POSITION — gapping, never zeroing
# ═══════════════════════════════════════════════════════════════════════════
def test_an_unreadable_interest_gaps_it_never_zeroes_it(brazos, marcus):
    """BR-CUS-057 is CONFIRMED and its accrual engine is NOT BUILT.

    A zero here would carry **$150.00** where **$153.50** is owed and keep
    $3.50 of the customer's own money — which is the one direction this gap
    must never take. So the position serves NO figure: `interest` and
    `refundable` are both `None` and the gap is named with its rule.
    """
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        position = discounts.deposit_position(marcus, customer["id"])
    assert len(position["positions"]) == 1
    row = position["positions"][0]
    assert row["principal"]["display"] == "150.00"
    assert row["interest"]["display"] is None  # NOT "0.00"
    assert row["refundable"]["display"] is None
    assert discounts.GAP_DEPOSIT_INTEREST in row["gaps"]
    assert "BR-CUS-057" in " ".join(
        item["br_ref"]
        for item in position["unavailable"]
        if item["code"] == discounts.GAP_DEPOSIT_INTEREST
    )


def test_the_total_refuses_to_foot_while_any_position_gaps(brazos, marcus):
    """A total that summed the readable half would present $150.00 as the
    answer — and it would foot, which is what makes it dangerous."""
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        position = discounts.deposit_position(marcus, customer["id"])
    assert position["readable"] is False
    assert position["total_refundable"] == {"stored": None, "display": None}


def test_an_account_holding_no_deposit_answers_zero_without_the_engine(brazos, marcus):
    """Nothing to accrue on, so BR-CUS-057's absence does not block it — and
    gapping it would refuse a carry-forward for an account with nothing to
    carry. `move_out_settlement._deposit_interest`'s posture, deliberately
    identical: two modules disagreeing about when a deposit may be read is how
    a customer gets two answers to one question."""
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos, deposit=D("0"))
        position = discounts.deposit_position(marcus, customer["id"])
    row = position["positions"][0]
    assert row["interest"]["display"] == "0.00"
    assert row["refundable"]["display"] == "0.00"
    assert row["gaps"] == []
    assert position["readable"] is True


def test_the_stored_deposit_is_not_net_of_the_settlement_and_says_so(brazos, marcus):
    """The gap that points the OTHER way, and it is the sharper of the two.

    BR-CUS-025 settles the deposit against everything outstanding at close and
    NOTHING WRITES THAT BACK — `move_out_settlement` returns `persisted: False`
    and `accounts.deposit_on_file` is written only at create and by the
    US-CUS-023 import. So a CLOSED account's column is the deposit as RECEIVED.
    Carrying it forward silently would hand a customer money the utility
    already applied to their final bill.
    """
    with tenant_ctx(brazos):
        customer, prior = _returning_customer(marcus, brazos)
        position = discounts.deposit_position(marcus, customer["id"])
    row = position["positions"][0]
    assert row["closed_at"] == "2026-08-15"
    assert discounts.GAP_NOT_NET_OF_SETTLEMENT in row["gaps"]
    detail = next(
        item["detail"]
        for item in position["unavailable"]
        if item["code"] == discounts.GAP_NOT_NET_OF_SETTLEMENT
    )
    assert "persisted: False" in detail
    # And the column really is untouched by the close it just went through.
    with tenant_ctx(brazos):
        assert customers_models.Account.objects.get(id=prior["id"]).deposit_on_file == DEPOSIT_HELD


def test_only_closed_accounts_appear_in_the_position(brazos, marcus):
    """B18 §5.5.5: *"refundable deposit on any **closed** account"*. A LIVE
    account's deposit is not available to carry anywhere — it is securing the
    service the customer is still taking."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos, label="Live unit")
        live = _occupant(marcus, brazos, unit, name="Alvarez, Rosa")
        customers_models.Account.objects.filter(id=live["id"]).update(deposit_on_file=DEPOSIT_HELD)
        customer = _the_accounts_customer(live["id"])
        position = discounts.deposit_position(marcus, customer["id"])
    assert position["positions"] == []
    assert position["readable"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE CARRY-FORWARD — TC-MVI-2 and TC-MVI-3
# ═══════════════════════════════════════════════════════════════════════════
def _wire_interest(monkeypatch, amount=DEPOSIT_INTEREST):
    """Publish BR-CUS-057's read, the ONE place a seam is patched.

    Patched on purpose and named as such: it proves the gap is a WIRING fact
    and not a permanent refusal, which is the same device
    `test_w5_move_out_settlement.py` uses for the same absence.
    """
    real_resolve = discounts.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            # CR-059 CS-20 (2026-09-03): the published accrual states the day
            # it accrues to, so the stub takes two. `_as_of` is ignored here on
            # purpose — this suite is about the carry-forward, and the engine's
            # own arithmetic is asserted in `test_cr059_cs20_deposit_interest`.
            return lambda _account_id, _as_of=None: amount
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(discounts.seams, "resolve", _resolve)


def test_tc_mvi_2_a_strong_match_is_offered_the_frozen_153_50(brazos, marcus, monkeypatch):
    """**TC-MVI-2**: *"a returning customer with **$153.50** on a closed
    account … the carry-forward is **offered**, and the DEPOSIT cell reads
    `carried $153.50` in the accent."*

    $150.00 + $3.50 = $153.50 — ❄️ WE-7 / GT-23's frozen pair, not this file's
    arithmetic. Rule 2: stored to four places, displayed at two.
    """
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, customer, "strong")
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert offer["offered"] is True
    assert offer["refused"] is None
    assert offer["amount"]["display"] == "153.50"
    assert offer["amount"]["stored"] == "153.5000"
    assert offer["deposit_cell"] == "carried $153.50"
    assert offer["match"]["tier"] == "strong"
    assert offer["match"]["source"] == "service_request"
    assert offer["match"]["confirmed_by"] is not None  # BR-CUS-089's confirmer


def test_tc_mvi_3_a_weak_match_is_refused_and_no_money_moves(brazos, marcus, monkeypatch):
    """**TC-MVI-3**: *"a **weak** identity match … carry-forward is **refused
    with its reason** — money never moves on a weak match."*

    The refusal serves NO figure. A refused offer that still printed $153.50
    would be an invitation to type it in by hand, which is the same money
    moving with an extra step in front of it.
    """
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, customer, "weak")
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert offer["offered"] is False
    assert offer["amount"] == {"stored": None, "display": None}
    assert offer["positions"] == []
    assert offer["refused"]["code"] == discounts.REFUSAL_TIER_NOT_STRONG
    assert offer["refused"]["br_ref"] == "BR-CUS-089"
    assert offer["refused"]["tier"] == "weak"
    assert "money moves only on a strong match" in offer["refused"]["detail"]


def test_a_probable_match_is_refused_too_because_only_strong_moves_money(
    brazos, marcus, monkeypatch
):
    """BR-CUS-089 names three tiers and permits ONE. `probable` is the tier a
    reasonable person would let through, which is exactly why it is asserted:
    the rule says `strong`, not `strong enough`."""
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, customer, "probable")
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert offer["offered"] is False
    assert offer["refused"]["tier"] == "probable"


def test_a_move_in_with_no_recorded_match_is_refused_not_defaulted(brazos, marcus, monkeypatch):
    """The honest edge of the FIRST unruled point.

    Nothing in this repository defines what makes a match `strong` — there is
    no matcher, and `service_request_service.link_customer` says the tier is
    the clerk's judgement. So a move-in that never went through a request has
    no stored tier at all, and the money stays where it is. Choosing a default
    either way would be resolving an open question by picking a value.
    """
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert offer["offered"] is False
    assert offer["refused"]["code"] == discounts.REFUSAL_NO_STORED_MATCH
    assert offer["refused"]["tier"] is None
    codes = {row["code"] for row in offer["unavailable"]}
    assert discounts.GAP_NO_MATCH_RULE in codes


def test_the_tier_is_read_from_storage_and_can_never_be_passed_in(brazos, marcus):
    """BR-CUS-089: the tier *"and its confirmer"* are **stored**.

    A `tier=` parameter would let a caller assert `strong` and move money —
    the rule inverted. Asserted against the signature so a future convenience
    argument goes red rather than quiet.
    """
    import inspect

    params = set(inspect.signature(discounts.carry_forward_offer).parameters)
    assert params == {"actor", "customer_id"}
    assert "tier" not in params
    # And the vocabulary has not drifted from the request surface's own.
    assert discounts.MATCH_TIERS == sr.MATCH_TIERS


def test_a_strong_match_still_gaps_the_figure_while_the_engine_is_unbuilt(brazos, marcus):
    """The two halves are INDEPENDENT, and this is what proves it: the match is
    strong, the offer stands, and the figure is `None` because BR-CUS-057 is
    not built. Collapsing "offered with no readable figure" into "not offered"
    would hide a returning customer's money behind somebody else's engine."""
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, customer, "strong")
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert offer["offered"] is True
    assert offer["amount"] == {"stored": None, "display": None}
    assert offer["deposit_cell"] is None
    assert discounts.GAP_DEPOSIT_INTEREST in offer["gaps"]


def test_the_offer_has_no_accept_path_and_says_which_rule_is_missing(brazos, marcus, monkeypatch):
    """BR-CUS-024 is *"PROPOSED (mechanics) / linkage CONFIRMED"*. The linkage
    is signed; what row moves is not. And `accounts.deposit_on_file` is a
    REFUSED field on every non-import door. So there is no `accept` and the
    payload names the rule rather than leaving a clerk to wonder."""
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, customer, "strong")
        offer = discounts.carry_forward_offer(marcus, customer["id"])
    assert not hasattr(discounts, "accept_carry_forward")
    assert discounts.GAP_NO_ACCEPT_PATH in offer["gaps"]
    row = next(
        item for item in offer["unavailable"] if item["code"] == discounts.GAP_NO_ACCEPT_PATH
    )
    # AMENDED 2026-10-01 (billing red triage): this read `"PROPOSED
    # (mechanics)" in row["detail"]`. The mechanics were RULED on 2026-09-01
    # (CR-059 CS-22: the deposit is offered forward as a liability transfer)
    # and the notice was rewritten to say so (`c15c51f03` / `2c3d9114c`); what
    # is still missing is the WRITER. The case still asserts that the payload
    # names the rule and the gap, now in the ruled words.
    assert "BR-CUS-024" in row["br_ref"]
    assert "The MECHANICS are ruled and the WRITER is missing" in row["detail"]


def test_both_branches_write_audit_log(brazos, marcus, monkeypatch, audit_rows):
    """CLAUDE.md rule 7 — and the refusal is the half that would be forgotten.

    A refused carry-forward is the decision that a returning customer's $153.50
    stayed where it was, and B18's move-in KPI strip counts `DEPOSITS TO CARRY
    OVER`; a refusal leaving no trace is a figure nobody can reconcile.
    """
    _wire_interest(monkeypatch)
    with tenant_ctx(brazos):
        strong_customer, _a = _returning_customer(marcus, brazos)
        _record_match(marcus, brazos, strong_customer, "strong")
        discounts.carry_forward_offer(marcus, strong_customer["id"])
        weak_customer, _b = _returning_customer(marcus, brazos, name="Osei, Grace")
        _record_match(marcus, brazos, weak_customer, "weak")
        discounts.carry_forward_offer(marcus, weak_customer["id"])
    actions = audit_actions(audit_rows)
    assert "customer.deposit_carry_forward.offered" in actions
    assert "customer.deposit_carry_forward.refused" in actions


def test_a_float_is_refused_rather_than_coerced():
    """Rule 2: *"never float/cents"*. A float that reached this arithmetic
    would foot to the cent and be wrong in the fourth place."""
    with pytest.raises(errors.BizError) as exc:
        discounts._money(153.50, "the accrued deposit interest")
    assert exc.value.message_key == "customers.deposit_position.money_not_a_decimal"


# ═══════════════════════════════════════════════════════════════════════════
# 5 · TENANT ISOLATION — under the NON-SUPERUSER probe role
# ═══════════════════════════════════════════════════════════════════════════
def test_another_tenants_customer_is_a_404_never_a_403(brazos, lonestar, marcus, erin):
    """HR-1: existence must not leak. A cross-tenant customer id answers 404 on
    both doors, and the deposit figure never reaches the response at all."""
    with tenant_ctx(lonestar):
        foreign, _prior = _returning_customer(
            erin, lonestar, name="Somebody Else", service_code="water"
        )
    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            discounts.deposit_position(marcus, foreign["id"])
        with pytest.raises(errors.NotFoundError):
            discounts.carry_forward_offer(marcus, foreign["id"])


@requires_postgres
def test_the_grant_table_is_rls_scoped(rls, brazos, lonestar, marcus, dana, erin):  # noqa: F811
    """⚠ **THE ONLY ASSERTION IN THIS FILE THAT PROVES RLS.**

    A plain ORM query under `tenant_ctx` runs as the app's role, a SUPERUSER in
    dev and CI, and superusers bypass row-level security unconditionally —
    FORCE or not. Such an assertion returns rows because the policy was never
    consulted, and goes green having proven nothing (DEF-101). So this runs
    inside `SET ROLE sbh_rls_probe` (NOLOGIN NOSUPERUSER NOBYPASSRLS).

    ⚠ **AND THE TABLE IS `discount_enrolments`, NOT `account_discounts`.** The
    lane wrote no migration because the six facts B18 §5.5.5 wants already have
    columns on this table and a bill run reads only this one. `discount_
    enrolments` names a customer, a subsidy and — through
    `discount_enrolment_documents` — a proof of income, which is why its
    isolation is worth proving rather than assuming. Its policy is already the
    DEF-639 `NULLIF` form (`db/rls_rating_discounts.sql`), so it needs no
    rewrite and this lane added none.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        programme = _programme(brazos, dana, code="SENIOR")
        discounts.claim_assistance(dana, account["id"], programme["id"])
    with tenant_ctx(lonestar):
        other_unit = _unit(erin, lonestar, label="Far away", service_code="water")
        other_account = _occupant(erin, lonestar, other_unit, name="Somebody Else")
        other_programme = _programme(lonestar, erin, code="SENIOR")
        discounts.claim_assistance(erin, other_account["id"], other_programme["id"])

    for table in GRANT_TABLES:
        assert_rls_scoped(rls, table, owner=brazos, intruder=lonestar)
    assert_no_foreign_rows_anywhere(rls, brazos, GRANT_TABLES)
    assert_no_foreign_rows_anywhere(rls, lonestar, GRANT_TABLES)


# ═══════════════════════════════════════════════════════════════════════════
# 6 · DEF-CUS-8711 — the interest is stated at the day service ended
# ═══════════════════════════════════════════════════════════════════════════
def test_def_cus_8711_the_interest_is_stated_at_the_closing_date(brazos, marcus, monkeypatch):
    """The published read REQUIRES the day it accrues to (`fbe971d14`), and
    this file called it with none, so every closed account holding a deposit
    raised `TypeError` — a 500 on the deposit-position screen.

    The day is the account's CLOSING date, ``closed_at`` — the day service
    ended. BR-CUS-057 *"pays out at refund/closure"*, and the move-out
    settlement states it at the move-out date (`services.move_out` passes
    ``moved_out_on``). A closed account's deposit stops earning when the
    account closes; stating it at today would grow it forever.

    The stub REQUIRES `as_of`, like the real selector, so the old one-argument
    call fails here exactly as it failed in production.
    """
    seen: list[date] = []
    real_resolve = discounts.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):

            def _read(_account_id, as_of):
                seen.append(as_of)
                return DEPOSIT_INTEREST

            return _read
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(discounts.seams, "resolve", _resolve)
    with tenant_ctx(brazos):
        customer, _prior = _returning_customer(marcus, brazos)
        position = discounts.deposit_position(marcus, customer["id"])
    assert seen == [date(2026, 8, 15)]
    row = position["positions"][0]
    assert row["interest"]["display"] == "3.50"
    assert row["refundable"]["display"] == "153.50"


def test_def_cus_8711_the_real_engine_answers_we_7_at_the_closing_date(brazos, marcus, monkeypatch):
    """End to end through the REAL seam and the REAL accrual, no stub on the
    read: $150.00 received 15 June 2025, closed 15 August 2026 = 14 completed
    months; at 2% that is 150.00 × 0.02 × 14 ÷ 12 = **$3.50**, ❄️ WE-7's own
    figure, and $153.50 refundable. Stated at today (1 October 2026) it would
    be 15 months and $3.75 — a closed deposit still earning.
    """
    from apps.customers import deposit_interest

    monkeypatch.setattr(deposit_interest, "annual_rate_percent", lambda: D("2"))
    with tenant_ctx(brazos):
        customer, prior = _returning_customer(marcus, brazos)
        customers_models.Account.objects.filter(id=prior["id"]).update(
            deposit_received_on=date(2025, 6, 15)
        )
        position = discounts.deposit_position(marcus, customer["id"])
    row = position["positions"][0]
    assert row["interest"]["stored"] == "3.5000"
    assert row["interest"]["display"] == "3.50"
    assert row["refundable"]["display"] == "153.50"
    assert discounts.GAP_DEPOSIT_INTEREST not in row["gaps"]


def test_def_cus_8711_the_route_answers_200_not_500_for_a_closed_deposit(
    brazos, marcus, monkeypatch
):
    """The defect as a clerk met it: `GET /customers/{id}/deposit-position`
    through the mounted route, on a closed account holding $150.00. It
    answered 500 (`TypeError`); it answers 200 with WE-7's $153.50."""
    from django.urls import resolve
    from rest_framework.test import APIRequestFactory, force_authenticate

    from apps.customers import api as customers_api
    from apps.customers import deposit_interest

    monkeypatch.setattr(deposit_interest, "annual_rate_percent", lambda: D("2"))
    with tenant_ctx(brazos):
        customer, prior = _returning_customer(marcus, brazos)
        customers_models.Account.objects.filter(id=prior["id"]).update(
            deposit_received_on=date(2025, 6, 15)
        )
        path = f"/api/v1/customers/{customer['id']}/deposit-position"
        assert resolve(path).func is customers_api.customer_deposit_position
        request = APIRequestFactory().get(path)
        force_authenticate(request, user=marcus.user)
        request.tenant_role = "billing_clerk"
        request.tenant_id = brazos.id
        response = customers_api.customer_deposit_position(request, customer_id=customer["id"])
    assert response.status_code == 200, response.data
    row = response.data["positions"][0]
    assert row["refundable"]["display"] == "153.50"


def test_def_cus_8711_a_closed_account_with_no_closing_date_gaps_rather_than_guesses(
    brazos, marcus
):
    """A closed account with no ``closed_at`` has no day to state the interest
    at. It GAPS — never today's date, never a crash."""
    with tenant_ctx(brazos):
        customer, prior = _returning_customer(marcus, brazos)
        customers_models.Account.objects.filter(id=prior["id"]).update(
            deposit_received_on=date(2025, 6, 15), closed_at=None
        )
        position = discounts.deposit_position(marcus, customer["id"])
    row = position["positions"][0]
    assert row["interest"]["display"] is None
    assert discounts.GAP_DEPOSIT_INTEREST in row["gaps"]

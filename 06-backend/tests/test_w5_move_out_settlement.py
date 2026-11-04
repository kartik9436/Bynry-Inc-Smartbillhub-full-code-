# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (EP-CUS-02 S20 Move-Out — step 3's five money landings,
#           step 4's shortfall decision, the refund path and the held excess)
#           Screens: S20 (steps 3 and 4)
# Rules:    BR-CUS-025 (the deposit settles EVERYTHING OUTSTANDING) ·
#           BR-CUS-057 (deposit interest — not built) · BR-CUS-081 (settle and
#           refund the difference) · BR-CUS-082 (a surviving debt is chased;
#           ladder restarts at TIER 1) · BR-CUS-096 (an open dispute HOLDS the
#           excess) · BR-CUS-097 (a sub-account's residue goes to its master) ·
#           BR-MET-105a (the owner is a real party) · BR-MET-107 (an unbanked
#           export credit is APPLIED to the final bill) · BR-BIL-013 (the
#           settlement paths) · BR-PAY-012 (a credit may be negative) ·
#           BR-SHL-025 (server-enforced RBAC)
# Journeys: J08 (the move-out close and its shortfall paths)
# Design:   04-docs/02-decisions/19-cr031-service-request-capture.md §15.9
# ───────────────────────────────────────────────────────
"""W5 — the move-out settlement, driven on the PO's own figures.

**EVERY FIGURE HERE IS SOMEBODY ELSE'S.** B19 §15.9.1's five landings, the two
worked cases the PO ruled on 2026-08-24 (BR-CUS-081's $11.20 and BR-CUS-082's
$175.20), BR-CUS-025's 2026-08-12 amendment ($90.14 not refunded), BR-MET-107's
$4.10 and ❄️ WE-7/GT-23's frozen $150.00 + $3.50 = $153.50. Nothing in this file
invents a number, which is what makes it a contract rather than a mirror.

**TWO LAYERS, DELIBERATELY, AND THE SECOND IS THE ONE DEF-658 IS ABOUT.** The
arithmetic is proved on the pure `derive()` because that is where B19's figures
live; the WIRED path is then proved separately through the real service on real
rows — `settlement_for`, `shortfall_decision`, `refund_disposition`,
`hold_excess` — so nothing here passes because a test wrote a value production
never writes. Where a term genuinely has no publisher today (BR-CUS-057's
interest, the dispute store), the test asserts the GAP rather than patching a
number in, and one test patches the seam resolver on purpose to prove the gap
closes the moment the publisher lands.
"""

from decimal import Decimal

import pytest

from apps.customers import models as customers_models
from apps.customers import move_out_settlement as mos
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    brazos,
    executive_actor,
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
APPLIED = D("153.50")  # what every one of B19 §15.9.1's five screens applies


def _settlement(**overrides):
    """B19 §15.9.0's two columns with the frozen deposit pair, one term at a
    time overridden by each landing's own figures."""
    base = dict(
        currency="USD",
        prior_balance=D("0.00"),
        final_bill=D("0.00"),
        deposit_held=DEPOSIT_HELD,
        deposit_interest=DEPOSIT_INTEREST,
        open_dispute_total=D("0.00"),
        siblings=(),
    )
    base.update(overrides)
    return mos.derive(**base)


def _sibling(account_no, amount):
    return mos.SiblingPosition(
        account_id=f"id-{account_no}", account_no=account_no, amount=D(amount), currency="USD"
    )


# ══════════════════════════════════════════════════════════════════════════
# B19 §15.9.1 — THE FIVE MONEY LANDINGS, ONE TEST EACH, ON ITS OWN FIGURES
# ══════════════════════════════════════════════════════════════════════════
def test_w5_landing_1__settled_nothing_owed_either_way():
    """§15.9.1 row 1: *"Settled — nothing owed either way"*, step 4 skipped."""
    s = _settlement(final_bill=APPLIED)
    assert s.outstanding == APPLIED
    assert s.applied == APPLIED
    assert s.net == D("0.00")
    assert s.landing == mos.LANDING_SETTLED
    assert s.step_4_live is False
    assert s.refund_amount == 0
    assert s.shortfall == 0


def test_w5_landing_2__refund_due_is_94_45_against_153_50_leaving_59_05():
    """§15.9.3: *"After the final bill of $94.45 is met, $59.05 remains from
    the deposit and interest of $153.50 … it is refunded."*"""
    s = _settlement(final_bill=D("94.45"))
    assert s.outstanding == D("94.45")
    assert s.applied == D("153.50")
    assert s.net == D("-59.05")
    assert s.excess == D("59.05")
    assert s.refund_amount == D("59.05")
    # BR-CUS-081: the BILL IS SETTLED from the deposit — it does not stand.
    assert s.settled_amount == D("94.45")
    assert s.landing == mos.LANDING_REFUND_DUE
    assert s.step_4_live is False


def test_w5_landing_3__short_by_170_74_and_step_4_goes_live():
    """§15.9.4: *"Everything outstanding is $324.24. The deposit and interest
    of $153.50 leave $170.74 unrecovered."*

    And its decomposition, which is the BR-CUS-025 half: $324.24 is a $142.30
    prior balance plus the $181.94 final bill — settle the bill alone and the
    deposit would cover it with $28.44 to spare.
    """
    s = _settlement(prior_balance=D("142.30"), final_bill=D("181.94"))
    assert s.outstanding == D("324.24")
    assert s.net == D("170.74")
    assert s.shortfall == D("170.74")
    assert s.excess == 0
    assert s.settled_amount == D("153.50")  # the whole deposit is consumed
    assert s.landing == mos.LANDING_SHORT
    assert s.step_4_live is True


def test_w5_landing_4__a_sibling_debt_seizes_the_refund_and_948_20_becomes_889_15():
    """§15.9.5: *"This customer owes $948.20 … The $59.05 credit here goes
    there first — no refund. What remains … after the transfer is $889.15."*"""
    s = _settlement(final_bill=D("94.45"), siblings=(_sibling("A-11968", "948.20"),))
    assert s.landing == mos.LANDING_REFUSED_OTHER_DEBT
    assert s.excess == D("59.05")
    assert s.transfer_to_sibling == D("59.05")
    assert s.sibling_after_transfer == D("889.15")
    assert s.step_4_live is False
    # §15.9.5's own point: transferring does NOT clear the sibling account.
    assert s.sibling_after_transfer > 0


def test_w5_landing_5__an_open_dispute_holds_13_12_br_cus_096():
    """§15.9.6 + BR-CUS-096 (PO 2026-08-24, *"hold until dispute close"*):
    $153.50 against $140.38 leaves $13.12, and $48.00 is disputed."""
    s = _settlement(prior_balance=D("45.93"), final_bill=D("94.45"), open_dispute_total=D("48.00"))
    assert s.outstanding == D("140.38")
    assert s.net == D("-13.12")
    assert s.excess == D("13.12")
    assert s.landing == mos.LANDING_REFUSED_EXCESS
    assert s.step_4_live is False
    # BR-CUS-096's own open half rides the payload — nothing releases it.
    codes = {gap["code"] for gap in s.serialize()["unavailable"]}
    assert "held_excess_has_no_release_path" in codes


def test_w5_all_five_landings_are_reachable_from_one_derivation():
    """§15.12 item 1: *"five money landings … driven by ONE derived outcome"*.

    The guard against five branches drifting apart is that all five come out of
    the same function with only the inputs changed.
    """
    seen = {
        _settlement(final_bill=APPLIED).landing,
        _settlement(final_bill=D("94.45")).landing,
        _settlement(prior_balance=D("142.30"), final_bill=D("181.94")).landing,
        _settlement(final_bill=D("94.45"), siblings=(_sibling("A-11968", "948.20"),)).landing,
        _settlement(final_bill=D("140.38"), open_dispute_total=D("48.00")).landing,
    }
    assert seen == set(mos.MONEY_LANDINGS)


# ══════════════════════════════════════════════════════════════════════════
# THE SIGNED WORKED CASES — each rule's own figure, from its own row
# ══════════════════════════════════════════════════════════════════════════
def test_w5_br_cus_081__153_50_settles_142_30_and_refunds_11_20():
    """BR-CUS-081 verbatim: *"settle the $142.30 from the $153.50 deposit and
    refund $11.20; the account closes at zero and the bill does NOT stand."*"""
    s = _settlement(final_bill=D("142.30"))
    assert s.settled_amount == D("142.30")
    assert s.refund_amount == D("11.20")
    assert s.landing == mos.LANDING_REFUND_DUE
    # The REJECTED reading was "refund the whole $153.50, leave $142.30 standing".
    assert s.refund_amount != APPLIED


def test_w5_br_cus_096__the_same_11_20_is_held_when_something_is_disputed():
    """BR-CUS-096: *"BR-CUS-081 IS NOT REVERSED"* — the identical position
    refunds with nothing disputed and holds when $48.00 is."""
    undisputed = _settlement(final_bill=D("142.30"), open_dispute_total=D("0.00"))
    disputed = _settlement(final_bill=D("142.30"), open_dispute_total=D("48.00"))
    assert undisputed.landing == mos.LANDING_REFUND_DUE
    assert disputed.landing == mos.LANDING_REFUSED_EXCESS
    assert undisputed.excess == disputed.excess == D("11.20")


def test_w5_br_cus_082__a_328_70_close_against_153_50_is_175_20_short():
    """BR-CUS-082's fixture: *"`A-11024 · Ridge Coffee Co.` closes owing
    $328.70 with $153.50 of deposit and interest against it — the $175.20
    shortfall"*."""
    s = _settlement(prior_balance=D("328.70"), final_bill=D("0.00"))
    assert s.shortfall == D("175.20")
    assert s.landing == mos.LANDING_SHORT


def test_w5_br_cus_025__the_arrear_is_inside_the_settled_base_so_90_14_is_not_refunded():
    """BR-CUS-025 as amended 2026-08-12, with the figures built beside it: a
    $120.84 arrear inside a *Final amount due* of $184.20.

    Bill-only would refund $90.14 to a customer $120.84 in debt; the
    whole-position reading collects $30.70. Both are computed here so the
    difference is the assertion rather than the claim.
    """
    whole = _settlement(prior_balance=D("120.84"), final_bill=D("63.36"))
    bill_only = _settlement(prior_balance=D("0.00"), final_bill=D("63.36"))
    assert whole.outstanding == D("184.20")
    assert whole.shortfall == D("30.70")
    assert whole.landing == mos.LANDING_SHORT
    assert bill_only.refund_amount == D("90.14")
    assert whole.refund_amount == 0


def test_w5_br_met_107__the_4_10_export_credit_comes_off_the_final_bill():
    """BR-MET-107 (PO 2026-08-24, *"apply it to the final bill"*): M-4023's
    $4.10 of unbanked credit reduces what is owed, it is not forfeited.

    Driven on §15.9.6's own account, which is where the $4.10 was drawn: the
    prototype's $13.12 excess becomes **$17.22** once the credit is applied.
    """
    forfeited = _settlement(prior_balance=D("45.93"), final_bill=D("94.45"))
    applied = _settlement(prior_balance=D("45.93"), final_bill=D("94.45"), export_credit=D("4.10"))
    assert forfeited.excess == D("13.12")
    assert applied.final_bill_net == D("90.35")
    assert applied.outstanding == D("136.28")
    assert applied.excess == D("17.22")
    assert applied.excess - forfeited.excess == D("4.10")


def test_w5_br_met_107__a_credit_larger_than_the_bill_is_a_gap_not_a_floor():
    """BR-MET-107's open half: *"what happens when the credit EXCEEDS the final
    bill … is not settled"*. Not floored at zero — flooring confiscates the
    difference, which is the confiscation the ruling was made to stop."""
    s = _settlement(final_bill=D("3.00"), export_credit=D("4.10"))
    assert s.final_bill_net is None
    assert s.landing is None
    assert mos.GAP_EXPORT_CREDIT_EXCEEDS_BILL in s.gaps


# ══════════════════════════════════════════════════════════════════════════
# THE GAPS — every one fails CLOSED, and says which rule leaves it open
# ══════════════════════════════════════════════════════════════════════════
def test_w5_gap__a_deposit_whose_interest_cannot_be_read_states_no_landing():
    """BR-CUS-057 is not built. A principal-only settlement would keep WE-7's
    $3.50 on a bill that foots, so no landing is stated at all."""
    s = _settlement(final_bill=D("94.45"), deposit_interest=None)
    assert s.applied is None
    assert s.landing is None
    assert mos.GAP_DEPOSIT_INTEREST in s.gaps


def test_w5_gap__an_unread_dispute_blocks_a_refund_but_not_a_shortfall():
    """BR-CUS-096 makes an unread dispute decide whether money goes back, so an
    EXCESS gaps on it. A `short` close is unaffected — gapping that would
    refuse settlements the rules settle."""
    excess = _settlement(final_bill=D("94.45"), open_dispute_total=None)
    short = _settlement(prior_balance=D("328.70"), open_dispute_total=None)
    assert excess.landing is None and mos.GAP_DISPUTES_UNREADABLE in excess.gaps
    assert short.landing == mos.LANDING_SHORT


def test_w5_gap__unreadable_siblings_block_a_refund_because_15_9_3_is_a_precondition():
    """§15.9.3: *"The customer has no other debt with us, so it is refunded"* —
    the sentence §15.9.5 falsifies. `None` siblings ≠ no siblings."""
    unknown = _settlement(final_bill=D("94.45"), siblings=None)
    none_held = _settlement(final_bill=D("94.45"), siblings=())
    assert unknown.landing is None and mos.GAP_SIBLINGS_UNREADABLE in unknown.gaps
    assert none_held.landing == mos.LANDING_REFUND_DUE


def test_w5_gap__no_final_bill_states_no_landing():
    s = _settlement(final_bill=None)
    assert s.landing is None
    assert mos.GAP_FINAL_BILL in s.gaps


def test_w5_a_signed_hold_beats_an_unsigned_seizure_when_both_apply():
    """BR-CUS-096 is signed; the sibling-debt seizure is prototype drawing.
    Transferring money that may still be owed elsewhere is the irreversible act
    the signed rule prevents, so the hold wins."""
    s = _settlement(
        final_bill=D("94.45"),
        open_dispute_total=D("48.00"),
        siblings=(_sibling("A-11968", "948.20"),),
    )
    assert s.landing == mos.LANDING_REFUSED_EXCESS


def test_w5_a_sibling_credit_is_shown_and_never_applied():
    """§15.9.4: `Credit on A-09984 · Available · $61.40` beside a shortfall of
    $170.74 — *"$61.40 is nowhere in that"*. And the unsigned-rule flag rides
    the payload, because nothing signs it."""
    s = _settlement(
        prior_balance=D("142.30"),
        final_bill=D("181.94"),
        siblings=(_sibling("A-09984", "-61.40"),),
    )
    assert s.shortfall == D("170.74")  # unchanged by the $61.40
    row = s.serialize()["siblings"][0]
    assert row["kind"] == "credit"
    assert row["disposition"] == mos.DISPOSITION_SHOWN_NOT_APPLIED
    assert "sibling_credit_rule_unsigned" in {g["code"] for g in s.serialize()["unavailable"]}


def test_w5_a_negative_unapplied_credit_is_a_real_debt_br_pay_012():
    """PO 2026-08-11, OQ-132: *"Yes, it's a real debt"* — nothing floors it."""
    plain = _settlement(final_bill=D("94.45"))
    bounced = _settlement(final_bill=D("94.45"), unapplied_credit=D("-57.13"))
    assert plain.applied == D("153.50")
    # J15's own chain: the $350.00 cheque bounces and the credit goes to −57.13.
    assert bounced.applied == D("96.37")
    assert plain.refund_amount == D("59.05")
    assert bounced.refund_amount == D("1.92")
    assert plain.refund_amount - bounced.refund_amount == D("57.13")


# ══════════════════════════════════════════════════════════════════════════
# MONEY SHAPE — CLAUDE.md rule 2 (4dp stored, 2dp display, never float)
# ══════════════════════════════════════════════════════════════════════════
def test_w5_money_is_stored_to_four_places_and_displayed_to_two():
    s = _settlement(final_bill=D("94.4499"))
    verdict = s.serialize()["verdict"]["net"]
    assert verdict["stored"] == "-59.0501"
    assert verdict["display"] == "-59.05"


def test_w5_a_float_is_refused_rather_than_coerced():
    """Rule 2: *"never float/cents"*. A float that reached the arithmetic would
    foot to the cent and be wrong in the fourth place."""
    with pytest.raises(errors.BizError) as exc:
        mos.derive(
            currency="USD",
            prior_balance=94.45,
            final_bill=D("0"),
            deposit_held=DEPOSIT_HELD,
            deposit_interest=DEPOSIT_INTEREST,
        )
    assert exc.value.message_key == "customers.move_out.money_not_a_decimal"


# ══════════════════════════════════════════════════════════════════════════
# THE WIRED PATH — real rows, real services (DEF-658: never test the ORM)
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


def _unit(actor, tenant, *, label="Unit A", premises=None):
    premises = premises or make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _occupant(actor, tenant, unit, *, name="Sarah Miller"):
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


def test_w5_wired__an_account_with_no_deposit_lands_on_the_real_service(brazos, marcus):
    """The wired read model, end to end, with NO seam patched.

    An account holding no deposit has nothing to accrue on, so BR-CUS-057's
    unbuilt engine does not block it — which is `deposit_credit_for`'s own
    posture and is what keeps this path alive in production today.
    """
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("94.45"))
    assert payload["what_is_applied"]["deposit_held"]["display"] == "0.00"
    assert payload["what_is_applied"]["deposit_interest"]["display"] == "0.00"
    assert payload["everything_outstanding"]["total"]["display"] == "94.45"
    assert payload["landing"] == mos.LANDING_SHORT
    assert payload["step_4_live"] is True
    assert payload["final_bill_stated_by_caller"] is True


def test_w5_wired__a_held_deposit_gaps_on_br_cus_057_until_the_engine_lands(brazos, marcus):
    """The production wall, asserted rather than described: an account that
    HOLDS a deposit cannot be settled while `deposit_interest_accrued` is
    published by nothing."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        customers_models.Account.objects.filter(id=account["id"]).update(
            deposit_on_file=DEPOSIT_HELD
        )
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("94.45"))
    assert payload["landing"] is None
    assert mos.GAP_DEPOSIT_INTEREST in payload["gaps"]
    assert "BR-CUS-057" in " ".join(
        gap["br_ref"] for gap in payload["unavailable"] if gap["code"] == mos.GAP_DEPOSIT_INTEREST
    )


def test_w5_wired__the_gap_closes_the_moment_customers_publishes_the_accrual(
    brazos, marcus, monkeypatch
):
    """The same account, with BR-CUS-057's read PUBLISHED — the one place a
    seam is patched, and it is patched to prove the gap is a wiring fact and
    not a permanent refusal.

    §15.9.3's `refund_due` figures come out on the other side: $94.45 against
    the frozen $153.50 leaves $59.05, and the bill is SETTLED (BR-CUS-081).

    BR-CUS-096's dispute read is published here TOO, and it has to be: an
    excess gaps on an unreadable dispute store as well, so publishing only the
    accrual would leave the landing withheld for the second reason. That the
    two gaps are independent is asserted separately in
    `test_w5_gap__an_unread_dispute_blocks_a_refund_but_not_a_shortfall`.
    """
    real_resolve = mos.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            # CR-059 CS-20 (2026-09-03) — two arguments now: the seam states
            # the day it accrues to (BR-TEN-043 / gate G6). Ignored here on
            # purpose; the engine's own figures are asserted in
            # `test_cr059_cs20_deposit_interest.py`.
            return lambda _account_id, _as_of=None: DEPOSIT_INTEREST
        if (module, attribute) == ("billing", "open_dispute_total"):
            return lambda _account_id: D("0.00")
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(mos.seams, "resolve", _resolve)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        customers_models.Account.objects.filter(id=account["id"]).update(
            deposit_on_file=DEPOSIT_HELD
        )
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("94.45"))
    assert payload["gaps"] == []
    assert payload["landing"] == mos.LANDING_REFUND_DUE
    assert payload["what_is_applied"]["total"]["display"] == "153.50"
    assert payload["verdict"]["refund_amount"]["display"] == "59.05"
    assert payload["verdict"]["settled_from_deposit"]["display"] == "94.45"


def test_w5_wired__a_sibling_account_is_found_through_the_real_customer_link(brazos, marcus):
    """BR-CUS-054's `customer_accounts` N:M link is how the *other* accounts
    are reached — the landlord case, through the same rows the import writes."""
    with tenant_ctx(brazos):
        unit_a = _unit(marcus, brazos, label="Unit A")
        unit_b = _unit(marcus, brazos, label="Unit B")
        leaving = _occupant(marcus, brazos, unit_a)
        other = _occupant(marcus, brazos, unit_b, name="Sarah Miller")
        customer = customers_models.Customer.objects.create(
            tenant=brazos, display_name="Sarah Miller"
        )
        for account_id in (leaving["id"], other["id"]):
            customers_models.CustomerAccount.objects.create(
                tenant=brazos, customer=customer, account_id=account_id
            )
        payload = mos.settlement_for(marcus, leaving["id"], final_bill=D("94.45"))
    assert payload["siblings"] is not None
    assert [row["account_no"] for row in payload["siblings"]] == [other["account_no"]]


def test_w5_wired__the_four_shortfall_paths_are_offered_and_transfer_names_both_refusals(
    brazos, marcus
):
    """Task 5.8's four options. The fourth is greyed here because this premises
    has neither a master account naming it nor a declared owner with one.

    ⚠ **TWO ASSERTIONS MOVED WITH `CR-056` W6 (`DEF-2951`) AND THE OUTCOME DID
    NOT.** (1) The owner refusal used to name `premises.owner_customer_id` — the
    column `BR-MET-105a` asks for and nobody ever added — and read that absence
    as *the owner can never be a posting target*. The FACT the rule wanted
    arrived under another name (a typed owner row with an account of its own),
    so the refusal is now about THIS ADDRESS having no owner account, which is
    the case that genuinely remains. (2) The two targets are offered
    **owner-first**, because `shortfall_decision` posts to `available[0]` and a
    DECLARED owner is who the money belongs to; the list IS the precedence, so
    it is asserted as an order rather than as a set."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("94.45"))
    options = {opt["path"]: opt for opt in payload["shortfall_paths"]}
    assert set(options) == set(mos.SHORTFALL_PATHS)
    assert all(options[p]["enabled"] for p in mos.SHORTFALL_PATHS if p != mos.SHORTFALL_TRANSFER)
    transfer = options[mos.SHORTFALL_TRANSFER]
    assert transfer["enabled"] is False
    assert "no master account" in transfer["reason"]
    assert "no owner account" in transfer["reason"]
    # …and it no longer tells a reader a missing COLUMN is the obstacle.
    assert "owner_customer_id" not in transfer["reason"]
    # The order is the precedence, not the constant's declaration order.
    assert [t["target"] for t in transfer["targets"]] == [
        mos.TRANSFER_TARGET_OWNER,
        mos.TRANSFER_TARGET_MASTER,
    ]
    assert set(t["target"] for t in transfer["targets"]) == set(mos.TRANSFER_TARGETS)


def test_w5_wired__the_shortfall_decision_writes_an_audit_row_and_carries_br_cus_082(
    brazos, marcus, audit_rows
):
    """Hard rule 7 — every money action writes `audit_log`; and BR-CUS-082's
    restart-at-TIER-1 fact rides the decision, with BR-CUS-097's unresolved
    subject beside it rather than a guess."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        decision = mos.shortfall_decision(
            marcus,
            account["id"],
            {"final_bill": D("94.45"), "path": mos.SHORTFALL_COLLECT},
        )
    assert decision["amount"]["display"] == "94.45"
    assert decision["dunning"]["restarts_at_tier"] == 1
    assert decision["dunning"]["escalates_to_disconnection"] is False
    assert decision["dunning"]["subject"] == "the closed account itself"
    assert "subject_unresolved" not in decision["dunning"]
    # DEF-2950 — see the endpoint suite: OQ-580 was this question's id for one
    # hour on 2026-08-27 and is now a different, live question about imports.
    assert "OQ-532" in decision["dunning"]["oq_532_master_ladder_position"]
    assert "JOIN" in decision["dunning"]["oq_532_master_ladder_position"]
    assert decision["persisted"] is False
    assert "account.move_out.shortfall_decided" in audit_actions(audit_rows)


def test_w5_wired__a_transfer_with_no_resolvable_target_is_refused_by_name(brazos, marcus):
    """BR-CUS-097: *"a transfer cannot be built against an ambiguous target"*
    — and there is no target at all here, so it refuses rather than picking."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.BizError) as exc:
            mos.shortfall_decision(
                marcus,
                account["id"],
                {"final_bill": D("94.45"), "path": mos.SHORTFALL_TRANSFER},
            )
    assert exc.value.message_key == "customers.move_out.shortfall_transfer_no_target"


def test_w5_wired__a_shortfall_decision_on_a_non_short_landing_is_refused(brazos, marcus):
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        with pytest.raises(errors.BizError) as exc:
            mos.shortfall_decision(
                marcus, account["id"], {"final_bill": D("0.00"), "path": mos.SHORTFALL_COLLECT}
            )
    assert exc.value.message_key == "customers.move_out.no_shortfall"


# ════════════════════════════════════════════════════════════════════════════
# PO RULING 2026-10-11 (1) — BR-CUS-096 SUSPENDED: no dispute store, no dispute
# ════════════════════════════════════════════════════════════════════════════
def _interest_only(monkeypatch, interest=D("0.00")):
    """Publish BR-CUS-057's accrual ONLY — the dispute store stays unpublished,
    which is the production state these two cases are about."""
    real_resolve = mos.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            return lambda _id, _as_of=None: interest
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(mos.seams, "resolve", _resolve)


def test_br_cus_096_suspended__no_dispute_store_reads_zero_and_marias_60_is_refunded(
    brazos, marcus, monkeypatch
):
    """The PO's worked case, verbatim from the decision log of 2026-10-11:
    *"Maria Lopez moves out. Her $150 deposit pays her $90 final bill, so we owe
    her $60."* Ruling: *"remove it fo time being and process the refund"*.

    Until the ruling `_open_dispute_total` answered None here, the settlement
    gapped on `open_disputes_not_readable` and stated NO landing, so the $60
    went nowhere. The same rows of `test_move_out_scenarios` (L2, L4, L5, D3) were RED on PostgreSQL before the change; here the pre-ruling code would answer
    `assert None == 'refund_due'`.
    """
    # The precondition, asserted: no dispute store is published on this tree.
    assert mos.seams.resolve("billing", "open_dispute_total", kind="selectors") is None
    _interest_only(monkeypatch)
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit, name="Maria Lopez")
        customers_models.Account.objects.filter(id=account["id"]).update(
            deposit_on_file=D("150.00")
        )
        payload = mos.settlement_for(marcus, account["id"], final_bill=D("90.00"))
    assert mos.GAP_DISPUTES_UNREADABLE not in payload["gaps"]
    assert payload["open_dispute_total"]["display"] == "0.00"
    assert payload["landing"] == mos.LANDING_REFUND_DUE
    assert payload["verdict"]["settled_from_deposit"]["display"] == "90.00"
    assert payload["verdict"]["refund_amount"]["display"] == "60.00"


def test_br_cus_096_suspended__a_PUBLISHED_store_still_holds_and_still_gaps(
    brazos, marcus, monkeypatch
):
    """*"For the time being"* is part of the ruling: the seam is read FIRST, so
    the day a dispute store lands, BR-CUS-096's hold returns with no change in
    the settlement module. A published store answering $48.00 holds the excess
    (`refused_excess`); a published store that cannot answer is still a gap."""
    with tenant_ctx(brazos):
        account = _refundable(
            brazos, marcus, monkeypatch, final_bill=D("142.30"), disputes=D("48.00")
        )
        held = mos.settlement_for(marcus, account["id"], final_bill=D("142.30"))
    assert held["landing"] == mos.LANDING_REFUSED_EXCESS
    assert held["verdict"]["excess"]["display"] == "11.20"

    with tenant_ctx(brazos):
        account = _refundable(brazos, marcus, monkeypatch, final_bill=D("142.30"),
                              disputes=None)
        unread = mos.settlement_for(marcus, account["id"], final_bill=D("142.30"))
    assert unread["landing"] is None
    assert mos.GAP_DISPUTES_UNREADABLE in unread["gaps"]


# ════════════════════════════════════════════════════════════════════════════
# PO RULING 2026-10-12 — MOVE-OUT DOES NOT WRITE OFF (supersedes 2026-10-11 (2))
# ════════════════════════════════════════════════════════════════════════════
# Verbatim: *"we will not write off at the time of move out; these charges
# remain outstanding on the account and followup is done as per outstanding
# rules"*, and on Q6: *"fianance or system admin will do it seperately later"*.
# The 2026-10-11 build (`db7b2808d`) raised a payments write-off REQUEST from
# step 4; these cases replace the four that asserted it.
DEV_SHORTFALL = D("182.90")
WRITE_OFF_TERMS = {
    "reason": "uncollectible_120_days",
    "note": "Moved out owing the balance after the deposit.",
}


def _billed(monkeypatch, amount):
    """Make payments' own write-off guard (ISSUED bills less allocations) PASS
    for this account, so a refusal below can only be the move-out's own: were
    the 2026-10-11 path still wired, a request for $182.90 would succeed."""
    from apps.payments import writeoffs

    monkeypatch.setattr(writeoffs, "_outstanding_of", lambda _account_id: amount)


def _write_off_rows(account_id):
    from apps.payments import collections_models

    return collections_models.WriteOff.objects.filter(account_id=account_id)


def test_no_move_out_write_off__step_4_offers_three_paths_and_no_write_off(brazos, marcus):
    """Dev Duval owes $182.90 after his deposit. Step 4 offers pursue, payment
    plan and transfer — and no *Write off* row at all (absent, not greyed)."""
    assert mos.SHORTFALL_PATHS == (
        mos.SHORTFALL_COLLECT,
        mos.SHORTFALL_PAYMENT_PLAN,
        mos.SHORTFALL_TRANSFER,
    )
    assert "write_off" not in mos.SHORTFALL_PATHS
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit, name="Dev Duval")
        payload = mos.settlement_for(marcus, account["id"], final_bill=DEV_SHORTFALL)
    assert payload["landing"] == mos.LANDING_SHORT
    offered = [opt["path"] for opt in payload["shortfall_paths"]]
    assert offered == ["collect", "payment_plan", "transfer"]


def test_no_move_out_write_off__posting_write_off_is_refused_by_name_and_writes_nothing(
    brazos, marcus, monkeypatch, audit_rows
):
    """`POST .../settle-shortfall` with `path="write_off"` is refused BY NAME —
    `customers.move_out.write_off_not_at_move_out` — and nothing is written: no
    `write_offs` row, no recorded decision, no audit row of either kind. The
    $182.90 stays outstanding on the account (BR-CUS-082 chases it)."""
    _billed(monkeypatch, D("247.30"))
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit, name="Dev Duval")
        with pytest.raises(errors.BizError) as exc:
            mos.shortfall_decision(
                marcus,
                account["id"],
                {"final_bill": DEV_SHORTFALL, "path": "write_off", **WRITE_OFF_TERMS},
            )
        assert not _write_off_rows(account["id"]).exists()
    assert exc.value.message_key == "customers.move_out.write_off_not_at_move_out"
    assert "write_off" not in exc.value.params["paths"]
    actions = audit_actions(audit_rows)
    assert "account.move_out.shortfall_decided" not in actions
    assert "write_off.requested" not in actions


def test_no_move_out_write_off__the_other_paths_are_unaffected(brazos, marcus, monkeypatch):
    """Pursue, payment plan and transfer are exactly as they were: each records
    its decision for $182.90 and none raises a write-off request."""
    _billed(monkeypatch, D("247.30"))
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        for path in (mos.SHORTFALL_COLLECT, mos.SHORTFALL_PAYMENT_PLAN):
            decision = mos.shortfall_decision(
                marcus, account["id"], {"final_bill": DEV_SHORTFALL, "path": path}
            )
            assert decision["path"] == path
            assert decision["amount"]["display"] == "182.90"
            assert decision["dunning"]["restarts_at_tier"] == 1
            assert "write_off" not in decision
        # Transfer still refuses by its own name when no target resolves.
        with pytest.raises(errors.BizError) as exc:
            mos.shortfall_decision(
                marcus,
                account["id"],
                {"final_bill": DEV_SHORTFALL, "path": mos.SHORTFALL_TRANSFER},
            )
        assert exc.value.message_key == "customers.move_out.shortfall_transfer_no_target"
        assert not _write_off_rows(account["id"]).exists()


def _refundable(brazos, marcus, monkeypatch, *, final_bill, disputes=D("0.00")):
    """An account on the `refund_due` landing, built through the real services.

    BR-CUS-057's accrual and the dispute store are the two publishers that do
    not exist; both are stood up here so the REFUND path itself is what the
    test exercises rather than the two gaps in front of it.
    """
    real_resolve = mos.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == ("customers", "deposit_interest_accrued"):
            return lambda _id, _as_of=None: DEPOSIT_INTEREST  # CR-059 CS-20 — see above
        if (module, attribute) == ("billing", "open_dispute_total"):
            return lambda _id: disputes
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(mos.seams, "resolve", _resolve)
    unit = _unit(marcus, brazos)
    account = _occupant(marcus, brazos, unit)
    customers_models.Account.objects.filter(id=account["id"]).update(deposit_on_file=DEPOSIT_HELD)
    return account


def test_w5_wired__br_cus_081_refunds_11_20_and_records_both_movements(
    brazos, marcus, monkeypatch, audit_rows
):
    """BR-CUS-081's own worked case, through the real service: $153.50 settles
    $142.30 and $11.20 is refunded — and BOTH movements are on the record,
    because a response carrying only the refund reads as the reading the PO
    rejected."""
    with tenant_ctx(brazos):
        account = _refundable(brazos, marcus, monkeypatch, final_bill=D("142.30"))
        decision = mos.refund_disposition(
            marcus,
            account["id"],
            {"final_bill": D("142.30"), "method": mos.REFUND_ACH},
        )
    assert decision["settled_from_deposit"]["display"] == "142.30"
    assert decision["refund_amount"]["display"] == "11.20"
    assert decision["bill_stands"] is False
    assert decision["method"] == mos.REFUND_ACH
    assert decision["persisted"] is False
    assert "account.move_out.refund_disposed" in audit_actions(audit_rows)
    # The two reasons no money actually moves, both named.
    codes = {row["code"] for row in decision["execution_unavailable"]}
    assert codes == {"refund_has_no_row_to_become", "deposit_settlement_not_posted"}


def test_w5_wired__a_cheque_needs_a_forwarding_street_and_ach_does_not(brazos, marcus, monkeypatch):
    """§15.9.3: the `*` is on `Street` and the helper names the condition —
    *"A cheque needs a forwarding address."*"""
    with tenant_ctx(brazos):
        account = _refundable(brazos, marcus, monkeypatch, final_bill=D("142.30"))
        with pytest.raises(errors.BizError) as exc:
            mos.refund_disposition(
                marcus,
                account["id"],
                {"final_bill": D("142.30"), "method": mos.REFUND_CHEQUE},
            )
        assert exc.value.message_key == "customers.move_out.forwarding_street_required"
        posted = mos.refund_disposition(
            marcus,
            account["id"],
            {
                "final_bill": D("142.30"),
                "method": mos.REFUND_CHEQUE,
                "forwarding_address": {
                    "street": "77 Pecan Row",
                    "city": "Rosenberg",
                    "state": "TX",
                },
            },
        )
    assert posted["forwarding_address"]["street"] == "77 Pecan Row"


def test_w5_wired__the_refund_amount_is_never_a_caller_input(brazos, marcus, monkeypatch):
    """A clerk cannot refund a figure they typed: the amount is the
    settlement's own, and an amount in the payload changes nothing."""
    with tenant_ctx(brazos):
        account = _refundable(brazos, marcus, monkeypatch, final_bill=D("142.30"))
        decision = mos.refund_disposition(
            marcus,
            account["id"],
            {"final_bill": D("142.30"), "method": mos.REFUND_ACH, "refund_amount": "999.00"},
        )
    assert decision["refund_amount"]["display"] == "11.20"


def test_w5_wired__an_unknown_refund_method_is_refused(brazos, marcus, monkeypatch):
    with tenant_ctx(brazos):
        account = _refundable(brazos, marcus, monkeypatch, final_bill=D("142.30"))
        with pytest.raises(errors.BizError) as exc:
            mos.refund_disposition(
                marcus, account["id"], {"final_bill": D("142.30"), "method": "wire"}
            )
    assert exc.value.message_key == "customers.move_out.refund_method_unknown"


def test_w5_wired__br_cus_096_holds_the_excess_and_says_nothing_releases_it(
    brazos, marcus, monkeypatch, audit_rows
):
    """The same account with $48.00 disputed: the refund path REFUSES and the
    hold records the excess with its unanswered half."""
    with tenant_ctx(brazos):
        account = _refundable(
            brazos, marcus, monkeypatch, final_bill=D("142.30"), disputes=D("48.00")
        )
        with pytest.raises(errors.BizError) as exc:
            mos.refund_disposition(
                marcus, account["id"], {"final_bill": D("142.30"), "method": mos.REFUND_ACH}
            )
        assert exc.value.message_key == "customers.move_out.no_refund_due"
        held = mos.hold_excess(marcus, account["id"], {"final_bill": D("142.30")})
    assert held["held_amount"]["display"] == "11.20"
    assert held["disputed_amount"]["display"] == "48.00"
    assert held["released"] is False
    assert held["release_unavailable"]["br_ref"] == "BR-CUS-096 (open half)"
    assert "account.move_out.excess_held" in audit_actions(audit_rows)


def test_w5_wired__an_executive_may_not_settle_or_decide(brazos, marcus):
    """A4: Accounts is VIEW for Executive, and BR-SHL-025 / BR-IDN-009 make the
    SERVER the enforcement. All four entry points are asserted, because a
    settlement decides where a departing customer's money goes."""
    with tenant_ctx(brazos):
        unit = _unit(marcus, brazos)
        account = _occupant(marcus, brazos, unit)
        actor = executive_actor()
        for call in (
            lambda: mos.settlement_for(actor, account["id"], final_bill=D("94.45")),
            lambda: mos.shortfall_decision(
                actor, account["id"], {"final_bill": D("94.45"), "path": mos.SHORTFALL_COLLECT}
            ),
            lambda: mos.refund_disposition(
                actor, account["id"], {"final_bill": D("0.00"), "method": mos.REFUND_ACH}
            ),
            lambda: mos.hold_excess(actor, account["id"], {"final_bill": D("0.00")}),
        ):
            with pytest.raises(errors.AuthError):
                call()

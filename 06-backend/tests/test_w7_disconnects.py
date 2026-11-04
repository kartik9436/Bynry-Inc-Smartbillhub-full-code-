# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-015 (S22's disconnect-notice modal) · US-CUS-028 (S90, the
#           disconnects WORKLIST — written 2026-08-25 in EP-CUS-08 after the
#           code and saying so, DEF-695; `status: blocked` on OQ-374).
#           ⚠ **THE WRITE PATH THIS FILE TESTS STILL OWNS NO STORY** — the
#           ladder, the protections, the notice, the schedule, the cut and the
#           reconnect (tasks 7.5–7.9 · 7.16) are in no story's scope, and
#           `DSC-02.1…5`, the five-step wizard B18 §3 puts under S90, has no
#           route in this application. **One is OWED** and is reported rather
#           than invented here (hard-won law 8).
#           Screens: S22 · S90
# Rules:    BR-CUS-039 (tiers; certified on the final; medical-hold accounts
#           EXCLUDED) · BR-CUS-030 (its `dunning stops` clause superseded for
#           the closed-with-balance case) · BR-CUS-082 (a debt surviving
#           closure is STILL CHASED and the ladder RESTARTS AT TIER 1 — PO
#           2026-08-24, OQ-346) · BR-CUS-097 (the residue moves to the MASTER;
#           its "who is chased" half is OPEN) · BR-CUS-043 (an active AND
#           current plan pauses dunning and disconnect) · BR-PAY-016 as amended
#           (the partial-payment percentage is a TENANT SETTING — OQ-136; a
#           missed instalment lifts the pause immediately — OQ-170) ·
#           BR-PAY-017 (the tenant-config collection sequence) · BR-PAY-021
#           (the POSTING date) · BR-PAY-036 (payment is always accepted and
#           NEVER auto-changes account status) · BR-BIL-001 as amended (the
#           $25.00 floor governs the WHOLE ladder — OQ-137/OQ-157) ·
#           BR-CUS-098 (when a protection LAPSES the ladder RESTARTS AT TIER 1
#           — PO 2026-08-25, *"Back to tier 1"*, closing DEF-689; **CONFIRMED
#           and NOT BUILT**, pinned by `TC-DSC-3` under `xfail(strict=True)`) ·
#           BR-CUS-101 (three protections are the release, the other seven of
#           `DSC-02.2`'s ten are deferred — PO 2026-08-25, *"3 is okay to start
#           with"*; the tick's meaning is OWED, DEF-691) ·
#           BR-TEN-003 (a cross-tenant id is a 404, never a 403) ·
#           CLAUDE.md rule 1 (tenant scoping + RLS FORCE) · rule 2 (money 4dp
#           stored / 2dp displayed) · rule 7 (audit)
# Journeys: J08 step 2b (the unresolved SUBJECT, asserted as unresolved) ·
#           J29 (disconnect to reconnect — the ladder, the protection, the
#           cut, the payment and the visit; every step here is one of its
#           handoff contracts)
# Design:   04-docs/02-decisions/18-cr030-onboarding-design.md §5.8 (the ladder,
#           the three protections, TC-DSC-1…9) · §5.8.7 (`DSC-02.1…5` as
#           drawn, captured 2026-08-25 — the ten protection checks, the
#           reason cards, the restrictor) · §6.3 (the three tables)
# ───────────────────────────────────────────────────────
"""W7 tasks 7.5 · 7.6 · 7.7 · 7.16 — the disconnect ladder and its protections.

**THE CASE THIS FILE EXISTS FOR IS `TC-DSC-1`**, and it is the one to read
first. A customer at TIER 2 pays in full; **nothing is called**; and the next
evaluation refuses to advance. It proves the safety property BY OMISSION, which
is the only way this property can be proved — a test that calls a `stop()`
function proves the opposite of *"nothing here has to be cancelled by hand"*
(B18 §5.8.3).

⚠ **TWO ASSERTIONS HERE ARE DELIBERATELY NEGATIVE AND MUST STAY THAT WAY.**

  1. `test_tc_dsc_82__the_subject_of_the_restarted_ladder_is_UNRESOLVED` asserts
     that the product names NO party. BR-CUS-097 and BR-CUS-082 were ruled the
     same day and do not resolve each other, and
     `08-qa/01-e2e/journeys/J08-final-bill-settlement-five-paths.md` step **2b**
     says in as many words: *"A GREEN ASSERTION HERE THAT NAMES EITHER PARTY IS
     A FAILURE, because it means somebody chose."* If a later lane makes this
     test assert a subject, it must be because the PO ruled — not because the
     test was inconvenient.
  2. `test_the_ladder_advances_on_no_schedule` asserts an ABSENCE. Nothing in
     this product reads a date and acts on it (DEF-320), so a tier does not
     arrive by itself, and the module says so on every answer rather than
     letting a `next_step_due` read as a promise.

⛔ **AND ONE CASE ASSERTS A RULE THE CODE DOES NOT YET KEEP — `TC-DSC-3`.**
`BR-CUS-098` (PO 2026-08-25, *"Back to tier 1"*) rules that a lapsed protection
**RESTARTS the ladder at TIER 1**, and B18 §5.8.5's own `TC-DSC-3` cell says the
opposite and is stamped SUPERSEDED there. This file previously asserted the
superseded cell and was GREEN on it — the exact thing the rule warns about:
*"a test case stating the opposite of a signed rule is how the wrong one gets
built."* It now asserts the RULE, under `xfail(strict=True)`, because
`apps/customers/disconnects.py` does not restart anything on a lapse and is not
this lane's file. **A defect row is OWED** and is reported rather than written
here. When the restart lands the marker goes RED as an XPASS and must be
deleted — a pin that cannot outlive its gap.

**RED PROVED FIRST for every case** (hard-won law 7). Each guard was broken
under a `# BREAK: … — RESTORE …` marker, run, the failure quoted in the lane
report, and the mutation reverted — DEF-666 is a lane that died mid-proof and
left its mutation in a shared tree, so no marker survives in this file.

⚠ **AND THE 2026-08-25 ADDITIONS WERE PROVED IN A `cp -a` COPY, NEVER IN THE
SHARED TREE** — r11 step 2d as amended that morning: *"a lane proving a guard
RED holds, for the length of the run, a tree in which the guarantee is genuinely
gone and the comment promising it is still there … byte-for-byte identical to a
lane fabricating values."* Three mutations, each applied to
`scratchpad/w7t-red/06-backend` and run there:

  1. `protection_check` appends a fabricated `life_support_registration` tick
     with `outcome: "pass"` — one of `DSC-02.2`'s ten that this product does not
     evaluate →
        E  AssertionError: the answer names exactly what it ran — four of the ten `DSC-02.2` draws
        E  Extra items in the left set: 'life_support_registration'
        FAILED …::test_dsc_02_2_draws_TEN_checks_and_this_product_answers_FOUR
  2. **BR-CUS-098's restart, SIMULATED** — `ladder_state` and `advance` made to
     read the tier as `None` for an account carrying a live payment plan, so a
     lapsed hold sends the ladder back to the bottom →
        [XPASS(strict)] BR-CUS-098 IS CONFIRMED AND NOT BUILT …
        1 failed in 118.55s
     **That failure is the proof.** `strict=True` turns the pin RED the moment
     the behaviour arrives, so it cannot outlive the gap it records — and the
     assertions do detect the restart rather than merely sitting red for some
     other reason.
     ⚠ **TWO WRONG MUTATIONS CAME FIRST AND BOTH ARE WORTH KNOWING.** (a) An
     unconditional `ladder_tier_of → None` made `_at_tier`'s unbounded `while`
     loop **spin at 100% CPU forever instead of failing** — which is why that
     helper is bounded now; see its docstring. (b) Scoping it to `ladder_tier_of`
     alone still failed, because `case_payload` reads its tier through that same
     function: the mutation blinded the *report* as well as the *decision*, and
     the test failed on `advance()`'s payload rather than passing. **The one
     place that answers a question is also the one place a mutation deceives**,
     which is worth remembering the next time a guard is proved through a
     single accessor.
  3. the registration line deleted from `apps/customers/models.py` →
        E  AssertionError: apps/customers/models.py must end with `from apps.customers import
           disconnects  # noqa: E402,F401  (registers three models)` …
        FAILED …::test_customers_models_registers_the_three_disconnect_models
     — which is what earned that test its `xfail` removal: it is a live guard,
     not a pin.
"""

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import disconnects
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.payments import collections_models as pay_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models

from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_actions,
    audit_rows,
    brazos,
    erin,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 8, 25)

#: BR-CUS-082's own worked fixture (PO 2026-08-24, closing OQ-346):
#: `A-11024 · Ridge Coffee Co.` closes owing $328.70 against $153.50.
RIDGE_OWED = D("328.70")
RIDGE_DEPOSIT = D("153.50")
RIDGE_SHORTFALL = D("175.20")


# ════════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING
# ════════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="W7 Ladder", defaults={"code": "w7-ladder", "status": "published"}
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"W7 Ladder — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _account(actor, tenant, *, label="Unit A", name="Rita Sandoval"):
    """One billable account on a planned, metered unit.

    ⚠ **THE PREMISES CARRIES A TYPED OWNER — DEF-1610, 2026-08-27.** CR-039 C12
    (BR-MET-151 clause 3) made `owner_id` mandatory on `create_premises`, and
    this fixture was not re-pointed with it: **22 of this suite's 23 tests had
    been failing on `VAL-001 (metering.premises.owner_required)`**, raised on
    the first line here, before any disconnect behaviour ran at all. Nothing
    noticed, because no gate in this repository runs pytest.
    """
    from apps.metering import premises_owners

    owner = premises_owners.create_premises_owner(
        actor, {"name": f"Whitfield Rentals {label}", "category": "landlord"}
    )
    premises = make_premises(
        actor, services_available=["electric", "water"], owner_id=owner["id"]
    )
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
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


class _EveryAccount(dict):
    """A `positions` map that answers the same figure for any account id.

    The tests stand up the LEDGER BOUNDARY, not a fake of it:
    `seams.ArPositions` is the real class, so `available`, `amount_for` and
    DEF-127's *"an unwired seam reports, it never answers 0"* distinction are
    the product's own and not this file's re-statement of them.
    """

    def __init__(self, amount):
        super().__init__()
        self._amount = amount

    def get(self, _key, _default=None):
        return self._amount


def _owes(monkeypatch, amount, *, available=True):
    """`available=False` is the UNREADABLE case and is a first-class fixture.

    `halt_reason` must stop the ladder on it, and a suite that only ever
    supplies a number cannot see that.
    """
    positions = (
        disconnects.seams.ArPositions(
            positions=None, unavailable=disconnects.seams.AR_POSITIONS_UNWIRED
        )
        if not available
        else disconnects.seams.ArPositions(positions=_EveryAccount(amount), currency="USD")
    )
    monkeypatch.setattr(disconnects.seams, "ar_positions", lambda *_a, **_k: positions)


def _no_settings(monkeypatch):
    """The S70 collections family unreadable — the floor cannot be defaulted."""
    monkeypatch.setattr(disconnects, "_collections_settings", lambda: {})


def _active_plan(tenant, account_id, *, due_on=date(2026, 9, 30), suspend_disconnect=True):
    """A live plan that is ACTIVE and CURRENT: one instalment, not yet due.

    Built with the ORM rather than through `plans.propose_payment_plan` because
    what is under test is the PAUSE, not the schedule arithmetic — that is
    GT-47's and `test_us_pay_017_payment_plans.py`'s, and restating it here
    would be a second copy of frozen figures.
    """
    plan = pay_models.PaymentPlan.objects.create(
        tenant=tenant,
        account_id=account_id,
        total_amount=D("267.30"),
        down_payment=D("50.00"),
        currency="USD",
        installment_count=1,
        status=pay_models.PLAN_ACTIVE,
        suspend_disconnect=suspend_disconnect,
        proposed_on=date(2026, 8, 1),
        signed_on=date(2026, 8, 2),
    )
    pay_models.PaymentPlanInstallment.objects.create(
        tenant=tenant, plan=plan, seq=1, due_date=due_on, amount=D("217.30"), currency="USD"
    )
    return plan


def _at_tier(actor, account_id, tier):
    """Walk the ladder to `tier` through the real `advance()` — never by UPDATE.

    A tier set with an UPDATE would prove that a column can hold a string. What
    the tests need is a case that ARRIVED at the tier through the gate every
    other path goes through.

    ⚠ **THE LOOP IS BOUNDED, AND THE BOUND EARNED ITSELF (2026-08-25, W7-TESTS
    lane).** It was `while reached != tier:` with no limit. Proving a guard RED
    means running the suite against a tree where the ladder deliberately does
    not climb — and this helper met that by **spinning at 100% CPU forever**
    instead of failing, in a scratchpad copy, for seven minutes before it was
    noticed. A test helper that hangs where it should fail is the same class as
    a check whose output cannot distinguish pass from fail: it is trusted, and
    it reports nothing. There are three tiers, so four calls is already one more
    than the ladder can serve.
    """
    reached = None
    for _ in range(len(disconnects.LADDER_TIERS) + 1):
        if reached == tier:
            return reached
        payload = disconnects.advance(actor, account_id, as_of=TODAY)
        reached = payload["tier"]
    if reached != tier:
        raise AssertionError(
            f"the ladder did not reach {tier!r} in {len(disconnects.LADDER_TIERS) + 1} calls to "
            f"`advance()` — it stopped at {reached!r}. B18 §5.8.2 draws exactly three tiers "
            f"({', '.join(disconnects.LADDER_TIERS)}), so a walk that needs more than that is a "
            "ladder that is not climbing, not a fixture that needs another turn."
        )
    return reached


# ════════════════════════════════════════════════════════════════════════════
# TC-DSC-A · THE LADDER CLIMBS — 1 → 2 → 3, AND STOPS AT THE TOP
# ════════════════════════════════════════════════════════════════════════════


def _prove_tier_3_service(actor, account_id, *, served_on=date(2026, 8, 22)):
    """⚠ **BR-CUS-100 (PO 2026-08-25) — a tier-3 cut needs a RECORDED PROOF OF
    SERVICE before it can be scheduled.**

    Added to these fixtures on 2026-08-25, when the guard landed. Before it,
    every one of these cases scheduled a cut on three in-app notices with
    nothing posted — which is `DEF-692` exactly: the lawfulness of a tier-3 cut
    rests on certified mail, and the product had no way to record that it
    happened.

    The proof is a record a PERSON enters, not a send the product claims: the
    channel used, the article number, and the date it was served. The article
    number here is a real USPS certified-mail format, because a fixture that
    types `"ref"` teaches the next reader that anything passes.
    """
    notice = disconnects.latest_notice_at_tier(
        disconnects.open_case_for(account_id), disconnects.TIER_3
    )
    return disconnects.record_proof_of_service(
        actor,
        notice.id,
        channel=disconnects.SERVE_CERTIFIED_MAIL,
        reference="7020 1810 0001 2345 6789",
        served_on=served_on,
    )


def test_tc_dsc_a1__the_ladder_climbs_tier_1_to_2_to_3(brazos, marcus, monkeypatch):
    """B18 §5.8.3's three chips, in order, each with its own notice appended."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)

        first = disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert first["tier"] == disconnects.TIER_1
        second = disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert second["tier"] == disconnects.TIER_2
        third = disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert third["tier"] == disconnects.TIER_3

        notices = disconnects.DisconnectNotice.objects.filter(case_id=third["case_id"]).order_by(
            "created_at"
        )
        assert [row.tier for row in notices] == [
            disconnects.TIER_1,
            disconnects.TIER_2,
            disconnects.TIER_3,
        ]

        # TIER 3 is the LAST tier. What follows is a scheduled cut, not a
        # fourth notice — a fourth chip would be a tier nobody ruled.
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert refusal.value.code == disconnects.HALT_LADDER_COMPLETE


def test_tc_dsc_a2__one_open_case_per_account_is_held_by_the_database(brazos, marcus, monkeypatch):
    """Two clerks on two screens is the race a Python check loses."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        one = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        two = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        assert one["case_id"] == two["case_id"]
        assert disconnects.DisconnectCase.objects.filter(account_id=account["id"]).count() == 1


# ════════════════════════════════════════════════════════════════════════════
# TC-DSC-1 · IT STOPS ITSELF ON PAYMENT — THE CASE THIS FILE EXISTS FOR
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_1__paying_in_full_at_tier_2_stops_the_ladder_with_NOTHING_called(
    brazos, marcus, monkeypatch
):
    """B18 §5.8.3, verbatim: *"the ladder stops automatically and the row leaves
    this list. Nothing here has to be cancelled by hand."*

    The customer reaches TIER 2 owing $948.20 and pays it. **No function is
    called on the case.** The next evaluation refuses to advance and the row is
    reported as having left the list.

    ⚠ **THE ASSERTION IS THE ABSENCE OF A CALL.** `stop_by_hand` is never
    invoked, `stopped_reason` stays NULL, and the case's stored `state` is
    untouched — because a stop that must be called is a stop that can be
    missed, and that missed stop is the customer who paid on Friday and got a
    certified letter on Monday.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_2)

        # The money posts. Nothing else happens — no cancel, no clerk, no job.
        _owes(monkeypatch, D("0.00"))

        state = disconnects.ladder_state(account["id"], as_of=TODAY)
        assert state.runs is False
        assert state.halt_code == disconnects.HALT_NOTHING_OWED

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert refusal.value.code == disconnects.HALT_NOTHING_OWED

        case = disconnects.open_case_for(account["id"])
        assert case.stopped_reason is None, "the ladder stopped ITSELF — nothing was cancelled"
        assert case.tier == disconnects.TIER_2, "the tier it reached is a fact and is not erased"


def test_tc_dsc_1b__paying_does_not_restore_service(brazos, marcus, monkeypatch):
    """BR-PAY-036 — *"acceptance NEVER auto-changes account status; restoration
    stays an explicit, audited staff action"*.

    The LADDER stops itself; the METER does not turn itself back on. B18
    §5.8.6's `A-11507` owes $0.00, carries tier `—` and is STILL on the tab
    because a reconnection visit is due.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("612.75"))
        account = _account(marcus, brazos)
        case = disconnects.open_case_for(account["id"]) or disconnects.DisconnectCase.objects.get(
            id=disconnects.open_case(marcus, account["id"], as_of=TODAY)["case_id"]
        )
        case.state = disconnects.STATE_CUT
        case.cut_on = date(2026, 8, 18)
        # ⚠ **THE THREE FIELDS BESIDE `cut_on` ARE NOT DECORATION — migration
        # 0024's `ck_cut_records_the_price_of_coming_back` REFUSES a row that
        # says service was cut with no price beside it.** This fixture fakes a
        # cut with an UPDATE (what is under test here is BR-PAY-036's *payment
        # does not restore*, not `commit_cut`'s own gates, which
        # `test_w7_cut_reconnect.py` owns), so it must satisfy the same
        # all-or-nothing the service layer does: `DSC-02.4` quotes **$75.00**
        # before the cut *"so the customer is told what it will cost to get
        # service back before it is taken away"*, and `DSC-02.4`'s drawn
        # default election is ● **Hold it**.
        case.reconnection_fee_amount = D("75.0000")
        case.reconnection_fee_code = disconnects.RECONNECT_CHARGE_CODE
        case.deposit_disposition = disconnects.DEPOSIT_HELD
        case.save(
            update_fields=[
                "state",
                "cut_on",
                "reconnection_fee_amount",
                "reconnection_fee_code",
                "deposit_disposition",
                "updated_at",
            ]
        )

        _owes(monkeypatch, D("0.00"))
        state = disconnects.ladder_state(account["id"], as_of=TODAY)
        assert state.runs is False
        assert "restoration" not in state.detail.lower() or "explicit" in state.detail.lower()
        # The account's own status is untouched by the payment.
        account_row = customers_models.Account.objects.get(id=account["id"])
        assert account_row.closed_at is None
        assert disconnects.open_case_for(account["id"]).cut_on == date(2026, 8, 18)


def test_the_partial_payment_pause_is_a_tenant_setting_and_15_8_percent_does_not_pause(
    brazos, marcus, monkeypatch
):
    """PO 2026-08-12, OQ-136, on the PO's own S34 figures.

    An account owing **$948** pays **$150** the day before a disconnection
    notice — **15.8%**, under the seeded 25% threshold, so **the ladder
    continues**. At 25% it would need **$237.00**.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("798.00"))  # $948 owed, $150 paid → $798 left
        account = _account(marcus, brazos)
        disconnects.open_case(marcus, account["id"], as_of=TODAY)

        halt = disconnects.halt_reason(
            account["id"],
            as_of=TODAY,
            case=disconnects.open_case_for(account["id"]),
            paid_recently=D("150.00"),
        )
        assert halt is None, "15.8% is under the threshold — the ladder continues"

        # $237.00 against the same $948 IS 25%, and pauses it.
        _owes(monkeypatch, D("711.00"))
        halt = disconnects.halt_reason(
            account["id"],
            as_of=TODAY,
            case=disconnects.open_case_for(account["id"]),
            paid_recently=D("237.00"),
        )
        assert halt is not None and halt["code"] == disconnects.HALT_PARTIAL_PAYMENT


def test_a_partial_payment_with_no_stored_percentage_stops_rather_than_guesses(
    brazos, marcus, monkeypatch
):
    """The PO named 25% and 50% as EXAMPLES, not as the value (OQ-136).

    With no percentage stored, choosing one here would answer a question the PO
    deliberately handed to each utility — so the ladder does not run at all.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("798.00"))
        account = _account(marcus, brazos)
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        monkeypatch.setattr(
            disconnects, "_collections_settings", lambda: {disconnects.FLOOR_KEY: "25"}
        )
        halt = disconnects.halt_reason(
            account["id"],
            as_of=TODAY,
            case=disconnects.open_case_for(account["id"]),
            paid_recently=D("150.00"),
        )
        assert halt["code"] == disconnects.HALT_PAUSE_PERCENT_UNSET


# ════════════════════════════════════════════════════════════════════════════
# TC-DSC-2 / 3 · IT STOPS ITSELF ON A PLAN, AND RESTARTS AT TIER 1 (BR-CUS-098)
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_2__an_active_and_current_plan_freezes_the_ladder(brazos, marcus, monkeypatch):
    """B18 §5.8.3 / BR-CUS-043 — `HELD · PAYMENT PLAN`, ladder frozen.

    Nothing is called on the case: the plan activating is what stops it, and the
    stop is READ from `apps.payments.dunning` rather than re-derived here.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("205.40"))
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_1)

        _active_plan(brazos, account["id"])

        state = disconnects.ladder_state(account["id"], as_of=TODAY)
        assert state.runs is False
        assert state.halt_code == disconnects.HALT_PLAN_PAUSE
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert refusal.value.br_ref == "BR-CUS-043"


def test_the_hold_lifts_the_DAY_the_instalment_is_missed_with_no_grace(brazos, marcus, monkeypatch):
    """BR-PAY-016 as amended (OQ-170, *"Immediate"*, no grace) — **WHEN** the
    hold lifts, which is a different question from **WHERE** the ladder then
    stands (that is `TC-DSC-3` below, and BR-CUS-098 rules it).

    The 1 Aug instalment is never met, the plan stays `active` — *"nobody is
    dropped off a plan"* (PO 2026-08-11) — and the pause is gone from the very
    next day, with no grace period invented on the way past.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("205.40"))
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_2)
        plan = _active_plan(brazos, account["id"], due_on=date(2026, 8, 1))

        assert plan.status == pay_models.PLAN_ACTIVE, "nobody is dropped off a plan (PO 2026-08-11)"
        state = disconnects.ladder_state(account["id"], as_of=TODAY)
        assert state.runs is True, "a missed instalment lifts the pause IMMEDIATELY — no grace"
        assert state.halt_code is None


# ✅ **BUILT 2026-08-27 — DEF-705. THE `xfail(strict=True)` BELOW IS DELETED, AS
# ITS OWN REASON INSTRUCTED**: *"the day the restart is built this test goes RED
# as XPASS and the marker must be deleted, so the pin cannot outlive the gap it
# records."* It did exactly that, which is the whole argument for `strict=True`
# over a plain xfail — a lenient marker would have gone on passing silently over
# a rule that had since been implemented.
#
# `disconnects._protection_interrupted_since_last_notice` is the mechanism, and
# BOTH `ladder_state().next_tier` and `advance()` read it, so the state a screen
# shows and the notice the ladder sends cannot disagree.
def test_tc_dsc_3__a_lapsed_protection_RESTARTS_the_ladder_at_TIER_1(brazos, marcus, monkeypatch):
    """⛔ **B18 §5.8.5's `TC-DSC-3` CELL IS WRONG AND IS NOT WHAT THIS ASSERTS.**

    That cell says *"the hold lifts and the ladder resumes **where it was**, not
    from tier 1"*. **It is SUPERSEDED** — B18 stamps it so in its own table, and
    `BR-CUS-098` (customers `02-business-rules.md`, CONFIRMED, PO 2026-08-25)
    rules the opposite in the PO's own three words: **"Back to tier 1"**. The
    rule's closing line is why this test is written this way round rather than
    left agreeing with the code:

        ⛔ *"`TC-DSC-3` IS WRONG AND MUST BE CORRECTED, NOT LEFT AS A SECOND
        OPINION — a test case stating the opposite of a signed rule is how the
        wrong one gets built."*

    **The worked cost the PO was shown before ruling**, and the reason the
    assertion below is about the NEXT NOTICE rather than about a column: a
    customer at `TIER 3 · 48-HOUR` who produces a medical certificate, three
    months later sees it expire, and then receives **`TIER 1 · REMINDER`, then
    `TIER 2 · 10-DAY`, then `TIER 3 · 48-HOUR`** — **three more notices**,
    roughly **eighteen further days** on the drawn ladder's own intervals
    (Aug 04 → Aug 18 → Aug 22) — before a cut can be scheduled again.

    ✅ **AND IT MAKES THE PRODUCT CONSISTENT WITH ITSELF.** `BR-CUS-082` already
    restarts at TIER 1 for a debt surviving closure
    (`test_tc_dsc_82__a_debt_surviving_closure_restarts_at_TIER_1_not_where_it_was`,
    which passes today). Two interruptions — a closure and a lapsed protection —
    now resume the same way. **The two tests sit in one file deliberately**, so a
    lane changing either is looking at the other.

    ⚠ **What BR-CUS-098 does NOT decide, and this test therefore does not
    assert:** whether a SECOND protection filed during the restarted ladder holds
    it again from wherever it has reached, and whether a tenant who has had six
    notices for one debt is owed anything different from one who has had three.
    Neither was raised with the PO; neither is inferred here.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("205.40"))
        account = _account(marcus, brazos)
        _at_tier(marcus, account["id"], disconnects.TIER_2)
        plan = _active_plan(brazos, account["id"], due_on=date(2026, 8, 1))
        assert plan.status == pay_models.PLAN_ACTIVE

        # The instalment is missed: BR-PAY-016 as amended lifts the pause
        # immediately (OQ-170, *"Immediate"*), so the ladder runs again.
        state = disconnects.ladder_state(account["id"], as_of=TODAY)
        assert state.runs is True

        # ⛔ AND IT RUNS FROM THE BOTTOM. Not from TIER 2, where the hold found
        # it — the household gets a fresh reminder before a certified letter.
        assert (
            state.next_tier == disconnects.TIER_1
        ), "BR-CUS-098: the next notice after a lapsed protection is TIER 1 · REMINDER"
        restarted = disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert restarted["tier"] == disconnects.TIER_1, (
            "a household coming off a payment plan must not be served the 48-hour "
            "certified notice as its first contact"
        )


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.7 · THE THREE PROTECTIONS, EACH WITH ITS OWN LIFETIME
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_4__a_medical_certificate_refuses_the_step_and_is_NAMED(brazos, marcus, monkeypatch):
    """B18 TC-DSC-4 — *"refused to advance, with the protection named"*."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos, name="Emmanuel Okafor")
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 11, 1),
        )

        check = disconnects.protection_check(account["id"], as_of=TODAY)
        medical = [row for row in check["checks"] if row["check"] == disconnects.PROTECTION_MEDICAL]
        assert medical[0]["outcome"] == "fail"
        assert medical[0]["lifetime"] == disconnects.LIFETIME_EXPIRES

        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.advance(marcus, account["id"], as_of=TODAY)
        assert refusal.value.code == disconnects.HALT_PROTECTED
        assert disconnects.PROTECTION_MEDICAL in str(refusal.value)


def test_the_medical_certificate_LAPSES_and_the_ladder_runs_again(brazos, marcus, monkeypatch):
    """LIFETIME_EXPIRES — a certificate is not a permanent exemption.

    The customer's own rights footer already tells them *"a medical hold is not
    permanent: the certificate has to be renewed"*.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 6, 1),
            expires_on=date(2026, 8, 24),
        )
        assert disconnects.medical_hold_for(account["id"], as_of=date(2026, 8, 24)) is True
        assert disconnects.medical_hold_for(account["id"], as_of=TODAY) is False
        assert disconnects.ladder_state(account["id"], as_of=TODAY).runs is True


def test_a_medical_certificate_with_no_expiry_is_REFUSED(brazos, marcus, monkeypatch):
    """A hold with no end date is a permanent exemption nobody signed."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_protection(
                marcus,
                account["id"],
                kind=disconnects.PROTECTION_MEDICAL,
                effective_from=date(2026, 8, 1),
            )
        assert refusal.value.code == "medical_certificate_needs_expiry"


def test_a_plan_protection_REFUSES_an_expiry_because_it_has_no_lifetime_of_its_own(
    brazos, marcus, monkeypatch
):
    """LIFETIME_DERIVED — the difference this file most needs to hold.

    A protection with no expiry and a protection that lapses are DIFFERENT
    OBJECTS. BR-CUS-043 grants the plan hold no date: it lives while the plan is
    active AND current and lapses the day an instalment is missed. A stored date
    here would be a second, slower answer to a question payments answers
    exactly.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("205.40"))
        account = _account(marcus, brazos)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_protection(
                marcus,
                account["id"],
                kind=disconnects.PROTECTION_PLAN,
                effective_from=date(2026, 8, 1),
                expires_on=date(2026, 12, 1),
            )
        assert refusal.value.code == "plan_protection_takes_no_expiry"

        row = disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_PLAN,
            effective_from=date(2026, 8, 1),
        )
        assert row["expires_on"] is None
        assert row["lifetime"] == disconnects.LIFETIME_DERIVED

        # With NO plan on the account the protection is not in force: its
        # liveness is READ, never assumed from the row's existence.
        live = disconnects.protections_for(account["id"], as_of=TODAY)
        plan_row = [r for r in live if r["kind"] == disconnects.PROTECTION_PLAN][0]
        assert plan_row["in_force"] is False

        _active_plan(brazos, account["id"])
        live = disconnects.protections_for(account["id"], as_of=TODAY)
        plan_row = [r for r in live if r["kind"] == disconnects.PROTECTION_PLAN][0]
        assert plan_row["in_force"] is True
        assert plan_row["expires_on"] is None


def test_tc_dsc_5__a_weather_moratorium_refuses_and_SHOWS_ITS_WINDOW(brazos, marcus, monkeypatch):
    """B18 TC-DSC-5 — *"refused; the window's dates are shown"*, and §5.8.3:
    *"a date window set by the regulator, not by the tenant"*."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("402.15"))
        account = _account(marcus, brazos, name="Nadia Iqbal")
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        recorded = disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MORATORIUM,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 9, 30),
        )
        assert recorded["set_by"] == "regulator", "the window is the regulator's, not the tenant's"
        assert recorded["lifetime"] == disconnects.LIFETIME_WINDOW

        check = disconnects.protection_check(account["id"], as_of=TODAY)
        row = [r for r in check["checks"] if r["check"] == disconnects.PROTECTION_MORATORIUM][0]
        assert row["outcome"] == "fail"
        assert row["effective_from"] == date(2026, 8, 1)
        assert row["expires_on"] == date(2026, 9, 30), "the window's dates are SHOWN"

        with pytest.raises(disconnects.DisconnectRuleError):
            disconnects.advance(marcus, account["id"], as_of=TODAY)


def test_a_moratorium_with_one_end_is_REFUSED(brazos, marcus, monkeypatch):
    """A window with one end cannot be SHOWN, which TC-DSC-5 requires."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("402.15"))
        account = _account(marcus, brazos)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_protection(
                marcus,
                account["id"],
                kind=disconnects.PROTECTION_MORATORIUM,
                effective_from=date(2026, 8, 1),
            )
        assert refusal.value.code == "moratorium_needs_a_window"


def test_the_three_lifetimes_are_held_by_the_DATABASE_not_only_by_the_service(
    brazos, marcus, monkeypatch
):
    """Hard-won law 1 — a comment claiming a guarantee is not the guarantee.

    The service refusals above can be bypassed by any ORM write. The check
    constraint cannot, and this test writes AROUND the service on purpose.
    """
    from django.db.utils import IntegrityError

    with tenant_ctx(brazos):
        _owes(monkeypatch, D("100.00"))
        account = _account(marcus, brazos)
        with pytest.raises(IntegrityError):
            disconnects.AccountProtection.objects.create(
                tenant=brazos,
                account_id=account["id"],
                kind=disconnects.PROTECTION_PLAN,
                effective_from=date(2026, 8, 1),
                expires_on=date(2026, 12, 1),  # forbidden on a DERIVED lifetime
            )


def test_lifting_a_protection_keeps_it_and_requires_a_reason(brazos, marcus, monkeypatch):
    """A DELETE answers nothing a regulator asks; an unexplained lift is a cut
    nobody can account for."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        recorded = disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 11, 1),
        )
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.lift_protection(marcus, recorded["protection_id"], on_date=TODAY, reason="")
        assert refusal.value.code == "lift_needs_a_reason"

        disconnects.lift_protection(
            marcus, recorded["protection_id"], on_date=TODAY, reason="certificate withdrawn"
        )
        assert disconnects.AccountProtection.objects.filter(
            id=recorded["protection_id"]
        ).exists(), "the row SURVIVES the lift — the history is the record"
        assert disconnects.medical_hold_for(account["id"], as_of=TODAY) is False


def test_step_2s_FOURTH_check_is_the_dispute_and_it_is_served_as_ABSENT(
    brazos, marcus, monkeypatch
):
    """B18 §5.8.4 step 2 lists four checks; §5.8.3 names three protections.

    Nothing in this repository stores a disputed AMOUNT (J08 step 7b(i)), so a
    green *"no dispute"* would be a fabricated clearance on the screen that
    authorises a cut.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        check = disconnects.protection_check(account["id"], as_of=TODAY)
        assert len(check["checks"]) == 4
        dispute = [r for r in check["checks"] if r["check"] == "dispute"][0]
        assert (
            dispute["outcome"] == "unavailable"
        ), "never `pass` — nothing stores a disputed amount"
        assert "disputed_at" in dispute["reason"], "the obvious wrong wire is named"


#: `DSC-02.2` draws TEN checks (B18 §5.8.7, captured 2026-08-25). These are the
#: SIX this product does not answer at all — it holds the medical certificate,
#: the weather moratorium and the payment plan, and serves the open dispute as a
#: stated absence. Named here so the gap is a list a reader can count rather
#: than a sentence in a design document.
DSC_02_2_UNANSWERED = (
    "life_support_registration",
    "age_or_disability_protection",
    "assistance_application_pending",
    "recent_partial_payment",
    "notice_period_served",
    "landlord_billed_premises",
)


def test_dsc_02_2_draws_TEN_checks_and_this_product_answers_FOUR(brazos, marcus, monkeypatch):
    """⛔ **DEF-691 / BR-CUS-101 — and the point is that the SIX ARE NOT
    FABRICATED, not that they are missing.**

    B18 §5.8.7's step 2 draws **ten** ticked checks under the chip `All clear`,
    each with its own finding, over the sentence *"This step exists because
    **cutting service to a protected household is the single most serious thing
    this product can do**"*. **Three are built** — the medical certificate, the
    weather moratorium and the payment plan (task 7.7, *"three protections, each
    with its own lifetime"*) — and `BR-CUS-101` (PO 2026-08-25, verbatim: *"3 is
    okay to start with"*) makes that the release rather than a shortfall.

    ⚠ **SO THE DANGER IS NOT THE ABSENCE — IT IS AN ANSWER THAT READS AS TEN.**
    §5.8.7: *"Each is a reason a cut must not proceed, so each missing one is a
    household that can be cut when it should not be."* This asserts the only
    thing that keeps that honest at the service boundary: **no check this
    product did not run is ever served as `pass`**, and the answer NAMES what it
    ran so a caller can see four rather than infer ten.

    ⚠ **`all_clear` IS A STATEMENT ABOUT THE THREE, AND NOTHING HERE LETS IT
    GROW.** The tier-3 letter promises the customer a right *"to be protected
    from disconnection if somebody at this address depends on medical
    equipment"* — §5.8.7 calls that *"the loop closing"* — and life-support
    registration, an age/disability protection and a pending assistance
    application are each a separate promise no machine guard checks. BR-CUS-101
    leaves *"the tick's meaning OWED"*; until it is ruled, the tick is a
    person's job and this test is what stops it silently becoming the product's.

    ⚠ **WHEN A LANE BUILDS ONE OF THE SIX THIS TEST GOES RED**, and that is the
    intended signal: the new check appears in `checks`, this assertion names it,
    and whoever built it updates the list above rather than discovering later
    that a screen has been claiming a clearance for a month.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("8240.00"))
        account = _account(marcus, brazos, name="Northwind Mfg.")
        check = disconnects.protection_check(account["id"], as_of=TODAY)

        served = {row["check"] for row in check["checks"]}
        assert served == {
            disconnects.PROTECTION_MEDICAL,
            disconnects.PROTECTION_MORATORIUM,
            disconnects.PROTECTION_PLAN,
            "dispute",
        }, "the answer names exactly what it ran — four of the ten `DSC-02.2` draws"

        for name in DSC_02_2_UNANSWERED:
            assert name not in served, (
                f"{name!r} is one of `DSC-02.2`'s ten and this product does not evaluate it. "
                "Serving it at all means serving a finding — and a fabricated one authorises a "
                "cut on a household that may be protected (DEF-691). If it is now BUILT, take "
                "it out of DSC_02_2_UNANSWERED and assert what it finds."
            )

        # And nothing the product did not run can reach a caller as a clearance.
        passes = {row["check"] for row in check["checks"] if row["outcome"] == "pass"}
        assert passes <= set(disconnects.PROTECTIONS), (
            "only a protection this product actually holds may answer `pass`; the dispute check "
            "is served `unavailable` and the other six are not served at all"
        )
        assert check["all_clear"] is True
        assert check["protections_in_force"] == (), (
            "`all_clear` here is a statement about the THREE protections in "
            "`disconnects.PROTECTIONS`, and the payload says which three it means"
        )


# ════════════════════════════════════════════════════════════════════════════
# TC-DSC-6 · THE DELIVERY CLAIM THIS PRODUCT CANNOT MAKE
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_6__a_notice_records_NO_delivery_state_and_never_emailed(
    brazos, marcus, monkeypatch
):
    """Task 7.10 — *"renders the absence of a delivery adapter, never a
    fabricated `emailed`"*. There is no email, SMS or print adapter in this
    release; `certified signed` would assert a signature came back."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("318.60"))
        account = _account(marcus, brazos, name="Dana Whitfield")
        payload = disconnects.advance(marcus, account["id"], as_of=TODAY)
        row = disconnects.DisconnectNotice.objects.get(id=payload["notice"]["notice_id"])
        assert row.delivery_state is None
        assert row.delivery_unavailable_reason == "delivery_adapter_absent"
        assert payload["notice"]["delivery"]["code"] == "delivery_adapter_absent"


# ════════════════════════════════════════════════════════════════════════════
# THE BALANCE FLOOR, AND THE READINGS THAT STOP THE LADDER BY FAILING
# ════════════════════════════════════════════════════════════════════════════
def test_a_240_debt_earns_no_reminder_no_notice_and_no_8_dollar_letter(brazos, marcus, monkeypatch):
    """PO 2026-08-12, OQ-137 / OQ-157 — the $25.00 floor on the WHOLE ladder.

    Chasing **$2.40** spends more than it recovers: the certified letter alone
    costs about **$8.00**. The floor is STRICT — exactly $25.00 IS chased.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("2.40"))
        account = _account(marcus, brazos)
        halt = disconnects.halt_reason(account["id"], as_of=TODAY)
        assert halt["code"] == disconnects.HALT_BELOW_FLOOR

        _owes(monkeypatch, D("25.00"))
        assert disconnects.halt_reason(account["id"], as_of=TODAY) is None


def test_an_unreadable_balance_STOPS_the_ladder_and_is_never_read_as_zero(
    brazos, marcus, monkeypatch
):
    """Hard-won law 3 — the unsafe option must be the one you type, and here the
    unsafe option is chasing."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, None, available=False)
        account = _account(marcus, brazos)
        halt = disconnects.halt_reason(account["id"], as_of=TODAY)
        assert halt["code"] == disconnects.HALT_BALANCE_UNREADABLE


def test_an_unreadable_collection_floor_STOPS_the_ladder_rather_than_defaulting_25(
    brazos, marcus, monkeypatch
):
    """The ratified default lives ONCE, in `apps.tenancy.settings_families`.

    A copy here would be free to drift from the number on the tenant's own
    screen — the reason `seams.nsf_privilege_threshold` returns None rather
    than 2.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        _no_settings(monkeypatch)
        halt = disconnects.halt_reason(account["id"], as_of=TODAY)
        assert halt["code"] == disconnects.HALT_FLOOR_UNREADABLE


# ════════════════════════════════════════════════════════════════════════════
# TASK 7.16 · BR-CUS-082 — THE POST-CLOSURE LADDER
# ════════════════════════════════════════════════════════════════════════════
def test_tc_dsc_82__a_debt_surviving_closure_restarts_at_TIER_1_not_where_it_was(
    brazos, marcus, monkeypatch
):
    """BR-CUS-082 (PO 2026-08-24, closing OQ-346): *"(b) continue, ladder restarts"*.

    Worked on the PO's own fixture: `A-11024 · Ridge Coffee Co.` closes owing
    **$328.70** against **$153.50** — **$175.20** survives. The customer was at
    **TIER 2** when the account closed and **does not stay at TIER 2**.
    """
    assert RIDGE_OWED - RIDGE_DEPOSIT == RIDGE_SHORTFALL

    with tenant_ctx(brazos):
        _owes(monkeypatch, RIDGE_OWED)
        account = _account(marcus, brazos, name="Ridge Coffee Co.")
        _at_tier(marcus, account["id"], disconnects.TIER_2)

        customers_models.Account.objects.filter(id=account["id"]).update(
            closed_at=date(2026, 8, 20)
        )
        _owes(monkeypatch, RIDGE_SHORTFALL)

        restarted = disconnects.restart_after_closure(
            marcus,
            account["id"],
            as_of=TODAY,
            shortfall=RIDGE_SHORTFALL,
            currency="USD",
        )
        assert restarted["tier"] == disconnects.TIER_1, "TIER 1, not the tier it had reached"
        assert restarted["sequence"] == disconnects.SEQ_COLLECTIONS
        assert restarted["amount_chased"]["stored"] == "175.2000"
        assert restarted["amount_chased"]["display"] == "175.20"
        assert restarted["dunning"]["restarts_at_tier"] == 1
        assert restarted["dunning"]["chased"] is True
        assert restarted["escalates_to_disconnection"] is False


def test_tc_dsc_82b__the_SUBJECT_of_the_restarted_ladder_is_UNRESOLVED(brazos, marcus, monkeypatch):
    """J08 step 2b — *"A GREEN ASSERTION HERE THAT NAMES EITHER PARTY IS A
    FAILURE, because it means somebody chose."*

    BR-CUS-097 moves a sub-account's residue to its MASTER; BR-CUS-082 restarts
    the ladder against the debt. **Whether the restarted ladder chases the
    departed sub-account holder or the master is stated by neither ruling.** So
    this asserts that the product states the subject as UNRESOLVED and names no
    party — and that `restart_after_closure` cannot be TOLD one.

    ⚠ **DO NOT "FIX" THIS TEST BY NAMING A PARTY.** An OQ is owed and it is the
    PO's to close.
    """
    import inspect

    signature = inspect.signature(disconnects.restart_after_closure)
    assert "subject" not in signature.parameters, "naming a subject must be unrepresentable"
    assert "tier" not in signature.parameters, "resuming a tier must be unrepresentable"

    with tenant_ctx(brazos):
        _owes(monkeypatch, RIDGE_SHORTFALL)
        account = _account(marcus, brazos, name="Ridge Coffee Co.")
        customers_models.Account.objects.filter(id=account["id"]).update(
            closed_at=date(2026, 8, 20)
        )
        restarted = disconnects.restart_after_closure(
            marcus, account["id"], as_of=TODAY, shortfall=RIDGE_SHORTFALL, currency="USD"
        )

        # ⚠⚠ AMENDED 2026-08-27 — `OQ-366` IS CLOSED AND THIS TEST'S OWN NAME IS
        # NOW HALF WRONG. PO verbatim: *"Sub account is closed when debt is
        # trasnfer hence we now follow with owner for debt"* — the ladder
        # chases the MASTER, structurally, because the sub-account is closed by
        # the time the residue moves. `move_out_settlement.DUNNING_AFTER_CLOSE`
        # no longer carries a `subject_unresolved` sentence; the subject is
        # resolved PER DECISION by `_dunning_for()`, because it depends on
        # whether a clerk actually tied the residue back (BR-CUS-097 as
        # qualified the same day).
        #
        # ⚠ WHAT IS STILL TRUE, AND IS WHY THE STRUCTURAL HALF ABOVE IS KEPT:
        # `restart_after_closure()` STILL cannot name a subject — its signature
        # takes neither `subject` nor `tier`, asserted above — so this W7 read
        # serves `subject: None` and names nobody. That is now UNDER-stating a
        # settled answer rather than honestly refusing an open one, which is
        # **DEF-993**: `disconnect_reads.CHASE_SUBJECT_UNRESOLVED` still tells a
        # clerk on every collections row that nobody knows who is chased, and
        # cites OQ-366 by id while OQ-366 is closed. That fix is the W7 lane's
        # (this amendment comes from the CR-040 B5/B6 lane, which owns neither
        # `disconnects.py` nor `disconnect_reads.py`).
        assert restarted["subject"] is None
        assert restarted["dunning"].get("subject") is None
        assert "subject_unresolved" not in restarted["dunning"]
        # The ladder facts BR-CUS-082 signed are unchanged by the closure.
        assert restarted["dunning"]["restarts_at_tier"] == 1
        assert restarted["dunning"]["escalates_to_disconnection"] is False
        # ⚠ AND THE OQ-580 CARRY IS **NOT** ASSERTED HERE, DELIBERATELY.
        # `restart_after_closure()` builds its block from the
        # `DUNNING_AFTER_CLOSE` CONSTANT rather than through
        # `move_out_settlement._dunning_for()`, so it carries neither the
        # resolved subject nor the OQ-580 sentence that every move-out
        # shortfall decision now carries. Measured, not assumed:
        # `KeyError: 'oq_580_master_ladder_position_unsigned'`. That divergence
        # is DEF-993's second half and it is the W7 lane's to close — asserting
        # it green here would make this file the place the gap hides.
        assert "oq_580_master_ladder_position_unsigned" not in restarted["dunning"]


def test_an_account_that_closes_owing_NOTHING_starts_no_ladder(brazos, marcus, monkeypatch):
    """BR-CUS-030's `dunning stops` survives for the ordinary case.

    The supersession is NARROW, and reading it wider would start a ladder
    against a settled customer.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("0.00"))
        account = _account(marcus, brazos)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.restart_after_closure(
                marcus, account["id"], as_of=TODAY, shortfall=D("0.00"), currency="USD"
            )
        assert refusal.value.code == "closed_owing_nothing"
        assert refusal.value.br_ref == "BR-CUS-030"


def test_no_path_reaches_a_CUT_on_a_closed_account__three_independent_grounds(
    brazos, marcus, monkeypatch
):
    """BR-CUS-082 — *"a closed account cannot be escalated to disconnection —
    there is nothing left to disconnect"*.

    THREE grounds are asserted separately, because a guard that protects
    somebody's water supply must survive the deletion of any one of them:
      (1) the SEQUENCE — a collections case cannot cut;
      (2) the ACCOUNT's own closed status;
      (3) the DATABASE — `ck_collections_sequence_never_cuts`.
    """
    from django.db.utils import IntegrityError

    with tenant_ctx(brazos):
        _owes(monkeypatch, RIDGE_SHORTFALL)
        account = _account(marcus, brazos, name="Ridge Coffee Co.")
        customers_models.Account.objects.filter(id=account["id"]).update(
            closed_at=date(2026, 8, 20)
        )
        restarted = disconnects.restart_after_closure(
            marcus, account["id"], as_of=TODAY, shortfall=RIDGE_SHORTFALL, currency="USD"
        )
        case = disconnects.DisconnectCase.objects.get(id=restarted["case_id"])

        # (1) the sequence
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.assert_cut_reachable(case)
        assert refusal.value.code == "collections_sequence_cannot_cut"

        # ...and the only door to a cut date calls it.
        with pytest.raises(disconnects.DisconnectRuleError):
            disconnects.schedule_cut(marcus, account["id"], cut_on=date(2026, 9, 1), as_of=TODAY)

        # (2) the account's own status, with the sequence flipped away
        case.sequence = disconnects.SEQ_SERVICE
        case.save(update_fields=["sequence", "updated_at"])
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.assert_cut_reachable(case)
        assert refusal.value.code == "account_closed_cannot_cut"

        # (3) the database, with both service guards written around
        case.sequence = disconnects.SEQ_COLLECTIONS
        case.cut_scheduled_for = date(2026, 9, 1)
        with pytest.raises(IntegrityError):
            case.save(update_fields=["sequence", "cut_scheduled_for", "updated_at"])


def test_a_cut_is_scheduled_only_after_TIER_3(brazos, marcus, monkeypatch):
    """BR-CUS-039 — certified mail is REQUIRED on the final tier."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("8240.00"))
        account = _account(marcus, brazos, name="Northwind Mfg.")
        _at_tier(marcus, account["id"], disconnects.TIER_2)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.schedule_cut(marcus, account["id"], cut_on=date(2026, 8, 24), as_of=TODAY)
        assert refusal.value.code == "cut_before_final_tier"

        _at_tier(marcus, account["id"], disconnects.TIER_3)
        _prove_tier_3_service(marcus, account["id"])
        scheduled = disconnects.schedule_cut(
            marcus, account["id"], cut_on=date(2026, 8, 24), as_of=TODAY
        )
        assert scheduled["state"] == disconnects.STATE_SCHEDULED
        assert scheduled["cut_scheduled_for"] == "2026-08-24"


# ════════════════════════════════════════════════════════════════════════════
# THE BY-HAND STOP — §5.8.3's THREE NAMED REASONS, AND NO FOURTH
# ════════════════════════════════════════════════════════════════════════════
def test_the_by_hand_stop_takes_only_the_three_reasons_b18_names(brazos, marcus, monkeypatch):
    """*"the modal exists for clerk error, a dispute, or a regulator
    instruction"*. A fourth way to stop chasing a real debt needs a ruling."""
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.advance(marcus, account["id"], as_of=TODAY)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.stop_by_hand(marcus, account["id"], on_date=TODAY, reason="customer_called")
        assert refusal.value.code == "stop_reason_unknown"

        stopped = disconnects.stop_by_hand(
            marcus, account["id"], on_date=TODAY, reason=disconnects.STOP_REGULATOR
        )
        assert stopped["state"] == disconnects.STATE_STOPPED
        assert disconnects.open_case_for(account["id"]) is None


# ════════════════════════════════════════════════════════════════════════════
# THE TIER VOCABULARIES, AND THE RUNG WITH NO CHIP
# ════════════════════════════════════════════════════════════════════════════
def test_payments_second_5_day_rung_has_NO_chip_and_is_not_guessed_onto_one():
    """B18 §5.8.2 draws three chips; BR-PAY-017 names four rungs.

    Mapping `second_5_day` onto TIER 2 shows a customer at the 5-day notice as
    though they were at the 10-day one; onto TIER 3, as though a certified
    letter had gone out. Both are statements to a regulator about what a
    customer was told. **A ruling is OWED** and neither reading is built.
    """
    assert disconnects.tier_for_rung(disconnects.PAYMENTS_RUNG_FRIENDLY) == disconnects.TIER_1
    assert disconnects.tier_for_rung(disconnects.PAYMENTS_RUNG_10_DAY) == disconnects.TIER_2
    assert disconnects.tier_for_rung(disconnects.PAYMENTS_RUNG_48_HOUR) == disconnects.TIER_3
    assert disconnects.tier_for_rung(disconnects.PAYMENTS_RUNG_5_DAY) == disconnects.TIER_UNMAPPED


def test_the_mirrored_rung_names_still_match_payments_own_vocabulary():
    """A string typed twice is a mapping that silently stops matching.

    `apps/tenancy/settings_families.py` mirrors two vocabularies for exactly
    this reason and asserts each against its owner; this is the same assertion.
    """
    assert disconnects.PAYMENTS_RUNG_FRIENDLY == pay_models.TIER_FRIENDLY
    assert disconnects.PAYMENTS_RUNG_10_DAY == pay_models.TIER_FIRST_10_DAY
    assert disconnects.PAYMENTS_RUNG_5_DAY == pay_models.TIER_SECOND_5_DAY
    assert disconnects.PAYMENTS_RUNG_48_HOUR == pay_models.TIER_FINAL_48_HOUR


def test_a_notice_at_an_unknown_tier_is_refused_and_names_the_open_ruling(
    brazos, marcus, monkeypatch
):
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.open_case(marcus, account["id"], as_of=TODAY)
        with pytest.raises(disconnects.DisconnectRuleError) as refusal:
            disconnects.record_notice(
                marcus, account["id"], tier=disconnects.PAYMENTS_RUNG_5_DAY, on_date=TODAY
            )
        assert refusal.value.code == "tier_unknown"
        assert refusal.value.br_ref == "BR-PAY-017"


# ════════════════════════════════════════════════════════════════════════════
# NOTHING ADVANCES THIS LADDER ON A DATE
# ════════════════════════════════════════════════════════════════════════════
def test_the_ladder_advances_on_no_schedule_and_says_so(brazos, marcus, monkeypatch):
    """Measured 2026-08-25: no runner, job, queue or timer reads a date here.

    `next_step_due` is a STORED DATE THAT NOTHING WATCHES. The absence is served
    with **DEF-320** beside it on every answer, so a caller cannot mistake a due
    date for a promise that a tier will arrive.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        payload = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        assert payload["scheduler"]["advances_on_a_schedule"] is False
        assert payload["scheduler"]["tracks"] == "DEF-320"

        state = disconnects.ladder_state(account["id"], as_of=TODAY).as_dict()
        assert state["scheduler"]["advances_on_a_schedule"] is False

        # A month passes with nothing called. The tier has not moved.
        later = disconnects.ladder_state(account["id"], as_of=date(2026, 9, 25))
        assert later.tier == disconnects.open_case_for(account["id"]).tier


# ════════════════════════════════════════════════════════════════════════════
# MONEY SHAPE, AUDIT, AND TENANT ISOLATION
# ════════════════════════════════════════════════════════════════════════════
def test_the_money_columns_are_declared_4dp_and_serve_both_shapes(brazos, marcus, monkeypatch):
    """CLAUDE.md rule 2 as re-signed 2026-08-22 — *"MOney 4 decimal … display
    both 2 decimal"*. New columns declare 4dp; nothing here is a float."""
    field = disconnects.DisconnectCase._meta.get_field("amount_owed_at_open")
    assert (field.max_digits, field.decimal_places) == (18, 4)
    assert disconnects.DisconnectCase._meta.get_field("currency").max_length == 3

    with tenant_ctx(brazos):
        _owes(monkeypatch, RIDGE_SHORTFALL)
        account = _account(marcus, brazos)
        payload = disconnects.open_case(marcus, account["id"], as_of=TODAY)
        assert payload["amount_owed_at_open"] == {"stored": "175.2000", "display": "175.20"}
        assert payload["currency"] == "USD"


def test_every_service_action_writes_audit_log(brazos, marcus, monkeypatch, audit_rows):
    """CLAUDE.md rule 7, widened — a disconnection is not a money action, it is
    a SERVICE action against a named customer, and the record is the same.

    Read through the W1 suite's own capture sink (`audit_rows`, autouse in
    `tests/test_us_met_helpers.py`) rather than off `audit_log`: that fixture
    swaps `core.audit._sink` for a collector, so in this suite the TABLE is
    empty by design and a query against it would assert nothing. Measured
    before it was written this way — the table read returned `[]` for
    `create_account`'s rows too.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.advance(marcus, account["id"], as_of=TODAY)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 11, 1),
        )
        mine = [row for row in audit_rows if str(row["action"]).startswith("disconnect.")]
        actions = {row["action"] for row in mine}
        assert disconnects.AUDIT_CASE_OPENED in actions, audit_actions(audit_rows)
        assert disconnects.AUDIT_NOTICE in actions, audit_actions(audit_rows)
        assert disconnects.AUDIT_PROTECTION_RECORDED in actions, audit_actions(audit_rows)
        # Every one names the ACCOUNT — a service action against a customer is
        # findable from the customer, which is the whole point of the trail.
        assert {row["entity_type"] for row in mine} == {"account"}, mine
        # BR-AUD-007: the tenant comes from context, never from a parameter.
        assert {str(row["tenant_id"]) for row in mine} == {str(brazos.id)}, mine


def test_tc_dsc_9__tenant_b_sees_none_of_tenant_as_disconnects(
    brazos, marcus, lonestar, erin, monkeypatch
):
    """B18 TC-DSC-9 — *"tenant B · GET /disconnects · none of tenant A's"*.

    This is the ORM-level half. The database-level half — the RLS policy under a
    NON-SUPERUSER probe role — is G5's, because the app connects as a superuser
    and superusers bypass RLS unconditionally, which makes any assertion made on
    the app's own connection vacuous.
    """
    with tenant_ctx(brazos):
        _owes(monkeypatch, D("948.20"))
        account = _account(marcus, brazos)
        disconnects.advance(marcus, account["id"], as_of=TODAY)
        disconnects.record_protection(
            marcus,
            account["id"],
            kind=disconnects.PROTECTION_MEDICAL,
            effective_from=date(2026, 8, 1),
            expires_on=date(2026, 11, 1),
        )

    with tenant_ctx(lonestar):
        assert disconnects.open_case_for(account["id"]) is None
        assert disconnects.protections_for(account["id"], as_of=TODAY) == ()
        assert disconnects.medical_hold_for(account["id"], as_of=TODAY) is False


def test_customers_models_registers_the_three_disconnect_models():
    """The wiring guard for the one line the writing lane could not write.

    ✅ **THE `xfail` IS REMOVED — THE LINE LANDED.** It read *"XPASSes the moment
    the line lands"*, and on 2026-08-25 `apps/customers/models.py:1858` gained
    `from apps.customers import disconnects  # noqa: E402,F401  (registers three
    models)`. The marker was reporting XPASS in every run of this file, which is
    a pin outliving its gap: the assertion is a real guard now and carries no
    marker, exactly as `test_br_rat_080_081_separation.py` did when DEF-488
    closed. **Re-breaking that import is a migration-drift defect and this test
    is what says so.**

    A model is REGISTERED by importing the module that defines it. Django
    imports `apps.customers.models` and nothing else, so until that file
    imports this one, the three tables exist in migration STATE and not in the
    app registry — and the autodetector answers that difference with a
    `DeleteModel`. This suite cannot see the problem on its own, because
    importing `disconnects` at the top of THIS file registers them; only the
    source text of `models.py` can answer it.
    """
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "apps/customers/models.py").read_text()
    assert "from apps.customers import disconnects" in source, (
        "apps/customers/models.py must end with `from apps.customers import disconnects  "
        "# noqa: E402,F401  (registers three models)` — see apps/rating/models.py for the "
        "precedent. Without it `makemigrations --check` names DisconnectCase, DisconnectNotice "
        "and AccountProtection in a DeleteModel."
    )


def test_the_three_policies_use_the_NULLIF_form_and_force_rls(brazos):
    """CLAUDE.md hard rule 1 + DEF-639 (G41 ratchets this form).

    The bare cast `current_setting('app.tenant_id')::uuid` RAISES on an unset or
    empty marker instead of denying, and that is what made a fresh database
    un-buildable (DEF-622). Asserted against the migration SOURCE because the
    sqlite test database has no RLS at all to inspect.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1]
        / "apps"
        / "customers"
        / "migrations"
        / "0022_cr030_w7_disconnect_ladder.py"
    ).read_text()
    assert "NULLIF(current_setting('app.tenant_id', true), '')::uuid" in source
    assert "current_setting('app.tenant_id')::uuid" not in source, "the bare cast raises"
    assert "FORCE ROW LEVEL SECURITY" in source
    assert "ENABLE ROW LEVEL SECURITY" in source

    # All THREE tables are covered — a policy list that quietly names two is the
    # shape of a table shipped unprotected.
    assert set(_migration_tables(source)) == {
        disconnects.DisconnectCase._meta.db_table,
        disconnects.DisconnectNotice._meta.db_table,
        disconnects.AccountProtection._meta.db_table,
    }


def _migration_tables(source: str) -> list[str]:
    """The tuple the migration loops its policy over, read from the source."""
    import ast

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "DISCONNECT_TABLES" for target in node.targets
        ):
            return list(ast.literal_eval(node.value))
    raise AssertionError("the migration no longer declares DISCONNECT_TABLES")


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-030 W7 tasks 7.5 · 7.6 · 7.7 · 7.16 — B18 §5.8 (TC-DSC-1…9) ·
#         BR-CUS-082 · BR-CUS-097 (open half) · J08 step 2b
# generated: 2026-08-25 by lane S3 (W7 disconnects backend)
# checklist: A✔ B✔ C✔ D=deferred(no API half) E=deferred(no-frontend-half)
#         F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report — measured, not claimed
# exceptions: TC-DSC-7 (the cut commits, danger tier, base charges keep
#         accruing) and TC-DSC-8 (the reconnect row) are tasks 7.8/7.9 and are
#         NOT in this lane; what IS asserted here is that no path reaches a cut
#         on a closed account. TC-DSC-9's database half is G5's, for the
#         superuser reason stated on the test.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

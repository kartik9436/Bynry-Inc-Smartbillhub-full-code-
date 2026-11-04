# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-005 (EP-CUS-02 S20 Move-Out — steps 3 and 4 over the wire)
#           Screens: S20 (steps 3, 4 and the refund sub-panel)
# Rules:    BR-CUS-025 (the deposit settles EVERYTHING OUTSTANDING) ·
#           BR-CUS-057 (deposit interest — NOT BUILT, and therefore a GAP) ·
#           BR-CUS-081 (settle-and-refund; the bill does NOT stand) ·
#           BR-CUS-082 (a debt surviving closure is still chased, ladder
#           restarts at TIER 1) · BR-CUS-096 (an open dispute HOLDS the
#           excess) · BR-CUS-097 (a sub-account's residue goes to its MASTER,
#           and the target is RESOLVED, never supplied) · BR-BIL-013 (the four
#           shortfall paths) · BR-MET-107 (the export credit comes off first) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) · BR-TEN-003 / HR-1
#           (a cross-tenant id is a 404, never a 403) · CLAUDE.md rule 2 (money
#           4dp stored, DISPLAY 2 — never float) · rule 4 (new rows, never
#           edits) · rule 7 (every money action writes `audit_log`)
# Journeys: J08 (the move-out close and its shortfall paths) · T4-06 step 1
# Design:   04-docs/02-decisions/19-cr031-service-request-capture.md §15.9 —
#           "THE FIVE MONEY LANDINGS" · 18-cr030-onboarding-design.md §6.2
#           (the move-out endpoint gap, "❌ two")
# ───────────────────────────────────────────────────────
"""W5 tasks 5.8 / 5.9 — the SERVING half, and only the serving half.

`apps/customers/move_out_settlement.py` landed on 2026-08-24 built, tested (42
cases in `tests/test_w5_move_out_settlement.py`) and **unreachable**: its own
lifecycle block says `D=deferred(no-API-half — S20 steps 3/4 have no route yet;
another lane owns api.py)`, and `apps/customers/api.py` mounted
`accounts/<id>/move-out` and nothing else. That is hard-won law 2 in its purest
form — built is not wired; the S20 wizard's impact screen, shortfall decision
and refund path all render against endpoints that did not exist, every test
passed, and the feature was not there.

**WHAT THIS FILE ASSERTS, AND WHAT IT DELIBERATELY DOES NOT.** The arithmetic,
the five landings, every worked PO figure and every refusal are proved once, in
`test_w5_move_out_settlement.py`, against the module. Restating them here would
be a second copy of B19 §15.9 that can drift from the first. What is proved
HERE is the four claims only a route can make:

  1. **Each path is mounted at the name the SCREEN already uses.**
     `moveShared.tsx` reads `GET /accounts/{id}/close-impact` and step 4 names
     `POST /accounts/{id}/settle-shortfall`; B18 §6.2 lists exactly those two
     as the move-out gap. A route mounted at a name of our own invention is a
     defect that no unit test can see.
  2. **A GAP REACHES THE WIRE AS A GAP.** The endpoint serves `landing: null`
     with its `gaps[]` and the rule behind each, and never a number. This is
     the claim the money depends on: an account holding a deposit cannot be
     settled while BR-CUS-057's accrual engine does not exist, and a route that
     smoothed that into `0.00` would refund a customer their own interest.
  3. **The three decisions are money actions and audit** (hard rule 7) — and
     the row is written by the SERVICE, not a second one by the view.
  4. **A cross-tenant account is 404, never 403** (HR-1), on all four routes.

RED PROVED FIRST for every case — each guard was broken in `api.py` under a
BREAK/RESTORE marker, run, and the failure quoted in the lane report before the
mutation was reverted and the file verified byte-identical.

⚠ **ONE OF THEM TOOK TWO MUTATIONS TO GO RED, AND THAT IS WORTH KNOWING.**
Widening `account_close_impact`'s permission class from `AdminOrClerk` to
`AnyTenantRole` left the Executive test GREEN: `move_out_settlement`'s own
`@require_role(SYSTEM_ADMIN, BILLING_CLERK)` still answers 403. Swallowing that
service refusal in the view left it green too — the permission class rejects
before the view body runs. Only breaking BOTH halves turned it red (200 × 4).
That is BR-SHL-025's defence in depth working exactly as written, and it means
this test proves the ROLE OUTCOME rather than which half produced it.
"""

from decimal import Decimal

import pytest

from apps.customers import api as customers_api
from apps.customers import models as customers_models
from apps.customers import move_out_settlement as mos
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    audit_actions,
    brazos,
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


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — real rows through the real services of the owning module
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


def _unit(actor, tenant, *, label="Unit A", services_available=("electric", "water")):
    premises = make_premises(actor, services_available=list(services_available))
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
            # ⛔ **`BR-CUS-1024` (PO 2026-09-01) — the counter door refuses an
            # account whose customer identifies nobody, so the occupant is
            # identified** (`DEF-2392`). Every case in this file opens its
            # account through here, so from the moment that rule landed the
            # refusal fired in SIXTEEN setups and not one of them is about
            # identity: 16 of 17 red, the seventeenth being the one case that
            # never opens an account. One of the sixteen is `isolation`-marked,
            # which is how a fixture in a move-out file took down a
            # merge-blocking release gate.
            #
            # A PHONE is enough for a person and makes NO match strong — the
            # link carries no tier and no confirmer — so `BR-CUS-089` is
            # untouched and no money follows this. Same repair, same reasoning
            # and the same 555- shape as `450af92b` used for
            # `test_cr047_per_record_load.py`; no assertion in this file moves.
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": "+1 (512) 555-0162"},
            },
        },
    )


def _account(actor, tenant, *, label="Unit A", deposit=None):
    """An occupying account, optionally holding a deposit.

    The deposit is set with an UPDATE because there is no deposit-taking
    service in this module today — BR-CUS-023's lookup writes the column at
    account creation and nothing else moves it. That absence is the subject of
    `test_w5_api_close_impact__a_held_deposit_serves_the_gap…`, not a shortcut
    around a service that exists.
    """
    unit = _unit(actor, tenant, label=label)
    account = _occupant(actor, tenant, unit)
    if deposit is not None:
        customers_models.Account.objects.filter(id=account["id"]).update(deposit_on_file=deposit)
    return account


def _publish(monkeypatch, *, interest=None, disputes=None):
    """Stand up the two reads that no module publishes today.

    BR-CUS-096's disputed AMOUNT (`billing.open_dispute_total`) is published by
    nothing, and the settlement GAPS on it rather than reading silence as zero.
    A refund or a hold cannot be reached with that gap open, so it is published
    here — and ONLY here — so what these tests exercise is the ROUTE rather than
    the gap standing in front of it. That the gaps are real is asserted
    unpatched in `…_serves_the_gap_rather_than_a_number`.

    ⚠ **BR-CUS-057's ACCRUAL IS NO LONGER UNPUBLISHED (CR-059 CS-20,
    2026-09-03), AND ITS STUB TAKES TWO ARGUMENTS NOW.** The published
    `customers.deposit_interest_accrued(account_id, as_of)` states the day it
    accrues to, because gate G6 keeps a clock out of a money path — so a stub
    written for the one-argument shape stops matching the contract, which is
    what a contract change is supposed to do to a stub. It is still stubbed
    here rather than exercised, deliberately: these cases are about the ROUTE,
    and the engine has its own suite in
    `test_cr059_cs20_deposit_interest.py` where ❄️ GT-61's **22.25** and WE-7's
    **3.50** are asserted against the real arithmetic. `_as_of` is accepted and
    IGNORED for the same reason the amount is fixed — a route test that varied
    the interest would be testing the engine twice and the route not at all.
    """
    real_resolve = mos.seams.resolve

    def _resolve(module, attribute, kind="services"):
        if (module, attribute) == (
            "customers",
            "deposit_interest_accrued",
        ) and interest is not None:
            return lambda _account_id, _as_of=None: interest
        if (module, attribute) == ("billing", "open_dispute_total") and disputes is not None:
            return lambda _account_id: disputes
        return real_resolve(module, attribute, kind=kind)

    monkeypatch.setattr(mos.seams, "resolve", _resolve)


def _refundable(monkeypatch, actor, tenant, *, disputes=D("0.00"), label="Unit A"):
    """An account on the `refund_due` landing (or `refused_excess` with a
    dispute): $153.50 applied against a $142.30 final bill leaves $11.20."""
    _publish(monkeypatch, interest=DEPOSIT_INTEREST, disputes=disputes)
    return _account(actor, tenant, label=label, deposit=DEPOSIT_HELD)


def _get(tenant, account_id, *, role="billing_clerk", query=None, user=None):
    return api_call(
        customers_api.account_close_impact,
        "get",
        user=user or FakeUser(),
        role=role,
        tenant=tenant,
        query=query,
        account_id=account_id,
    )


def _post(view, tenant, account_id, payload=None, *, role="billing_clerk", user=None):
    return api_call(
        view,
        "post",
        user=user or FakeUser(),
        role=role,
        tenant=tenant,
        data=payload if payload is not None else {},
        account_id=account_id,
    )


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE PATHS — the names the SCREEN already uses (B18 §6.2)
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api__the_four_routes_are_mounted_at_the_names_the_screen_uses():
    """The claim no other test in this repository makes.

    `07-frontend/src/features/customers/moveShared.tsx` reads
    `GET /accounts/{id}/close-impact` and `MoveOutWizard.tsx` names
    `POST /accounts/{id}/settle-shortfall`; B18 §6.2's move-out row lists those
    two as *"❌ two"*. A route serving the right payload at a name the client
    does not call is a 404 in production and green everywhere in CI, which is
    why the PATHS are asserted as literals rather than reversed from a name.

    `refund` and `hold-excess` are ADDITIONS — no document or screen names a
    path for BR-CUS-081's refund or BR-CUS-096's hold, and both callables were
    unreachable. Asserted here so the addition is visible rather than implied.

    RED before this lane: `urlpatterns` held ten entries and none of these
    four; every assertion below failed on the empty set.
    """
    mounted = {str(entry.pattern): entry.callback for entry in customers_api.urlpatterns}
    # PATH → the handler it must reach. Both halves are asserted: a path with no
    # route is a 404 the client cannot see, and a path routed to the wrong
    # handler is a settlement decision landing on somebody else's endpoint.
    assert {
        path: view.cls.__name__
        for path, view in mounted.items()
        if path.endswith(("/close-impact", "/settle-shortfall", "/refund", "/hold-excess"))
    } == {
        "accounts/<str:account_id>/close-impact": "account_close_impact",
        "accounts/<str:account_id>/settle-shortfall": "account_settle_shortfall",
        "accounts/<str:account_id>/refund": "account_refund",
        "accounts/<str:account_id>/hold-excess": "account_hold_excess",
    }


# ══════════════════════════════════════════════════════════════════════════
# 2 · GET close-impact — the settlement, and the GAP served AS a gap
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api_close_impact__serves_the_settlement_with_both_money_shapes(brazos, marcus):
    """The happy path: an account with NO deposit has nothing to accrue on, so
    BR-CUS-057's unbuilt engine does not block it and the landing is stated.

    `$94.45` outstanding against nothing applied is `short by 94.45`, step 4
    goes LIVE, and every figure carries BOTH shapes CLAUDE.md rule 2 requires
    as re-signed on 2026-08-22 — a 4dp `stored` string and a 2dp `display` one,
    each labelled, so a caller never has to decide which it is holding.
    """
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        response = _get(brazos, account["id"], query={"final_bill": "94.45"})

    assert response.status_code == 200
    body = response.data
    assert body["landing"] == mos.LANDING_SHORT
    assert body["gaps"] == []
    assert body["step_4_live"] is True
    assert body["final_bill_stated_by_caller"] is True
    assert body["account_no"] == account["account_no"]
    assert body["everything_outstanding"]["total"] == {"stored": "94.4500", "display": "94.45"}
    assert body["verdict"]["shortfall"]["display"] == "94.45"
    # The five landings travel with the payload — the screen never invents one.
    assert body["landings"] == list(mos.MONEY_LANDINGS)


def test_w5_api_close_impact__a_held_deposit_serves_the_gap_rather_than_a_number(brazos, marcus):
    """**The claim this endpoint exists to keep honest.**

    An account HOLDING a deposit cannot be settled today: BR-CUS-057's accrual
    is customers' own and is NOT BUILT, so `applied` cannot be computed. The
    route serves `landing: null`, the gap code and the rule behind it — and NO
    verdict figure at all. WE-7 freezes $3.50 of interest on $150 held 14
    months; a principal-only settlement foots perfectly while keeping the
    customer's money, which is exactly what a defaulted zero here would ship.

    Nothing is patched in this test, deliberately: this is the state of a
    production deployment today.

    RED before this lane: no route — `AttributeError: module 'apps.customers.api'
    has no attribute 'account_close_impact'`.
    """
    with tenant_ctx(brazos):
        account = _account(marcus, brazos, deposit=DEPOSIT_HELD)
        response = _get(brazos, account["id"], query={"final_bill": "94.45"})

    assert response.status_code == 200
    body = response.data
    assert body["landing"] is None
    assert body["complete"] is False
    assert mos.GAP_DEPOSIT_INTEREST in body["gaps"]
    # A gap is not a number: the verdict carries None on BOTH shapes.
    assert body["verdict"]["net"] == {"stored": None, "display": None}
    assert body["what_is_applied"]["total"] == {"stored": None, "display": None}
    # …and the rule that leaves it open travels with it.
    reasons = {row["code"]: row for row in body["unavailable"]}
    assert "BR-CUS-057" in reasons[mos.GAP_DEPOSIT_INTEREST]["br_ref"]


def test_w5_api_close_impact__no_final_bill_stated_is_its_own_gap(brazos, marcus):
    """Billing publishes no per-account final-bill total, so the wizard states
    the drafted figure. Absent, the read model reports `final_bill_not_stated`
    and states no landing rather than settling against a bill nobody read."""
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        response = _get(brazos, account["id"])

    assert response.data["landing"] is None
    assert mos.GAP_FINAL_BILL in response.data["gaps"]
    assert response.data["final_bill_stated_by_caller"] is False


def test_w5_api_close_impact__a_final_bill_that_is_not_money_is_refused_not_a_500(brazos, marcus):
    """`Decimal("nine")` inside the service is an unhandled `InvalidOperation`,
    and a 500 is not a refusal (B12 §3 / G9). Parsed at the boundary, reusing
    the catalogue sentence that already means this — no new key is minted."""
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        response = _get(brazos, account["id"], query={"final_bill": "nine dollars"})

    assert response.status_code == 422
    assert response.data["code"] == errors.VAL_FORMAT
    assert response.data["message_key"] == "customers.move_out.money_not_a_decimal"


def test_w5_api_close_impact__a_json_number_is_refused_by_the_service_not_coerced(brazos, marcus):
    """CLAUDE.md rule 2 — never float. DRF parses a JSON number as a `float`,
    and this layer passes it through UNTOUCHED so the settlement's own
    `_money` refusal is the one that fires: a second copy of that rule in the
    view is a second place for it to drift."""
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        response = _post(
            customers_api.account_settle_shortfall,
            brazos,
            account["id"],
            {"final_bill": 94.45, "path": mos.SHORTFALL_COLLECT},
        )

    assert response.data["message_key"] == "customers.move_out.money_not_a_decimal"


# ══════════════════════════════════════════════════════════════════════════
# 3 · POST settle-shortfall — S20 step 4 (task 5.8)
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api_settle_shortfall__records_the_decision_and_audits_it(brazos, marcus, audit_rows):
    """Hard rule 7 — a money action writes `audit_log`. The row is written by
    the SERVICE (`move_out_settlement._audit`); the view writes none, and a
    second row from this layer would double-count the same decision.

    BR-CUS-082's restart-at-TIER-1 fact rides the response with BR-CUS-097's
    unresolved SUBJECT beside it: the two rulings do not resolve each other and
    W7 must not build both readings, so the collision travels as a fact.

    Nothing is persisted — there is no `final_settlements` table (US-BIL-011 §5
    names one; B2 carries none) — and the payload says so rather than letting a
    200 read as "recorded".
    """
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        audit_rows.clear()
        response = _post(
            customers_api.account_settle_shortfall,
            brazos,
            account["id"],
            {"final_bill": "94.45", "path": mos.SHORTFALL_COLLECT},
        )

    assert response.status_code == 200
    assert response.data["path"] == mos.SHORTFALL_COLLECT
    assert response.data["amount"]["display"] == "94.45"
    assert response.data["dunning"]["restarts_at_tier"] == 1
    assert response.data["dunning"]["escalates_to_disconnection"] is False
    assert response.data["dunning"]["subject"] == "the closed account itself"
    assert "subject_unresolved" not in response.data["dunning"]
    # DEF-2950 — the id was renumbered to OQ-532 the day it was minted, and
    # OQ-532 was RULED (option B, JOIN) four days before this assertion was
    # last read. Both halves move together: the key names the right question
    # and no longer claims nobody was asked.
    assert "OQ-532" in response.data["dunning"]["oq_532_master_ladder_position"]
    assert "JOIN" in response.data["dunning"]["oq_532_master_ladder_position"]
    assert response.data["persisted"] is False
    assert audit_actions(audit_rows).count("account.move_out.shortfall_decided") == 1


def test_w5_api_settle_shortfall__refuses_a_landing_that_is_not_short(brazos, marcus):
    """*"Step 4 decides where the remaining balance goes."* On a `settled`
    close there is no remaining balance, so it refuses by name rather than
    recording a decision about nothing."""
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        response = _post(
            customers_api.account_settle_shortfall,
            brazos,
            account["id"],
            {"final_bill": "0.00", "path": mos.SHORTFALL_COLLECT},
        )

    assert response.status_code == 409
    assert response.data["code"] == errors.BIZ_STATE
    assert response.data["br_ref"] == "BR-CUS-082"
    assert response.data["message_key"] == "customers.move_out.no_shortfall"


def test_w5_api_settle_shortfall__a_transfer_target_is_never_a_caller_argument(brazos, marcus):
    """BR-CUS-097: *"a transfer cannot be built against an ambiguous target"*.

    No master account covers this premises, so the path refuses with the
    no-master case AND BR-MET-105a's missing `premises.owner_customer_id` —
    and a `target_account_id` in the body changes nothing, because no function
    in the settlement takes one. US-BIL-011 TC-6's forged transfer is
    unrepresentable rather than merely rejected, and mounting a route must not
    quietly make it representable again."""
    with tenant_ctx(brazos):
        other = _account(marcus, brazos, label="Unit Z")
        account = _account(marcus, brazos, label="Unit A")
        response = _post(
            customers_api.account_settle_shortfall,
            brazos,
            account["id"],
            {
                "final_bill": "94.45",
                "path": mos.SHORTFALL_TRANSFER,
                "target_account_id": str(other["id"]),
            },
        )

    assert response.status_code == 409
    assert response.data["message_key"] == "customers.move_out.shortfall_transfer_no_target"
    assert any("no master account" in reason for reason in response.data["params"]["reasons"])


# ══════════════════════════════════════════════════════════════════════════
# 4 · POST refund — BR-CUS-081's settle-and-refund (task 5.9)
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api_refund__records_both_movements_and_audits(brazos, marcus, monkeypatch, audit_rows):
    """BR-CUS-081's own worked case over the wire: $153.50 settles $142.30 and
    $11.20 is refunded — BOTH movements on one response, because a payload
    carrying only the refund reads as *"the whole deposit went back"*, the
    reading the PO explicitly rejected.

    `bill_stands: false` is the other half of that ruling. And the two reasons
    no money actually moves reach the client verbatim: payments' `refunds` has
    no account column (OQ-195), and this decision posts nothing (the final
    bill's issue credits a deposit excess to customer credit since OQ-248
    closed, 2026-09-30).
    """
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos)
        audit_rows.clear()
        response = _post(
            customers_api.account_refund,
            brazos,
            account["id"],
            {"final_bill": "142.30", "method": mos.REFUND_ACH},
        )

    assert response.status_code == 200
    assert response.data["settled_from_deposit"]["display"] == "142.30"
    assert response.data["refund_amount"] == {"stored": "11.2000", "display": "11.20"}
    assert response.data["bill_stands"] is False
    assert response.data["persisted"] is False
    assert {row["code"] for row in response.data["execution_unavailable"]} == {
        "refund_has_no_row_to_become",
        "deposit_settlement_not_posted",
    }
    assert audit_actions(audit_rows).count("account.move_out.refund_disposed") == 1


def test_w5_api_refund__the_amount_is_never_a_caller_input(brazos, marcus, monkeypatch):
    """A clerk cannot refund a figure they typed. The route forwards the body
    and the settlement computes its own amount, so `refund_amount: 999.00` in
    the payload changes nothing — asserted at the API boundary because that is
    where a hostile figure would arrive."""
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos)
        response = _post(
            customers_api.account_refund,
            brazos,
            account["id"],
            {"final_bill": "142.30", "method": mos.REFUND_ACH, "refund_amount": "999.00"},
        )

    assert response.data["refund_amount"]["display"] == "11.20"


def test_w5_api_refund__a_cheque_without_a_forwarding_street_is_refused(
    brazos, marcus, monkeypatch
):
    """B19 §15.9.3: the `*` is on `Street` and on nothing else, so the address
    is required for the CHEQUE alone — requiring it of an ACH refund blocks a
    payout that needs no address, and requiring nothing posts a cheque to an
    empty envelope."""
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos)
        refused = _post(
            customers_api.account_refund,
            brazos,
            account["id"],
            {"final_bill": "142.30", "method": mos.REFUND_CHEQUE},
        )
        posted = _post(
            customers_api.account_refund,
            brazos,
            account["id"],
            {
                "final_bill": "142.30",
                "method": mos.REFUND_CHEQUE,
                "forwarding_address": {"street": "77 Pecan Row", "city": "Rosenberg"},
            },
        )

    assert refused.status_code == 422
    assert refused.data["message_key"] == "customers.move_out.forwarding_street_required"
    assert posted.status_code == 200
    assert posted.data["forwarding_address"]["street"] == "77 Pecan Row"


def test_w5_api_refund__is_refused_while_a_dispute_holds_the_excess(brazos, marcus, monkeypatch):
    """BR-CUS-096 over BR-CUS-081: with $48.00 disputed the landing is
    `refused_excess`, so the refund route refuses by name and the money stays
    where it is. The signed hold beats the refund because the amount owed can
    still move — the irreversible act is the one that is prevented."""
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos, disputes=D("48.00"))
        response = _post(
            customers_api.account_refund,
            brazos,
            account["id"],
            {"final_bill": "142.30", "method": mos.REFUND_ACH},
        )

    assert response.status_code == 409
    assert response.data["message_key"] == "customers.move_out.no_refund_due"
    assert response.data["params"]["landing"] == mos.LANDING_REFUSED_EXCESS


# ══════════════════════════════════════════════════════════════════════════
# 5 · POST hold-excess — BR-CUS-096 (task 5.9)
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api_hold_excess__holds_and_says_nothing_chases_it(
    brazos, marcus, monkeypatch, audit_rows
):
    """*"hold until dispute close"* — and the response states on EVERY call
    that no release path, timer or queue exists, because BR-CUS-096 does not
    say who releases the hold or on what clock. That sentence is the
    deliverable; a release clock invented here would answer a question the PO
    has not been asked, and a customer's $11.20 would sit undiscovered."""
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos, disputes=D("48.00"))
        audit_rows.clear()
        response = _post(
            customers_api.account_hold_excess, brazos, account["id"], {"final_bill": "142.30"}
        )

    assert response.status_code == 200
    assert response.data["held_amount"]["display"] == "11.20"
    assert response.data["disputed_amount"]["display"] == "48.00"
    assert response.data["released"] is False
    assert response.data["release_unavailable"]["code"] == "held_excess_has_no_release_path"
    assert audit_actions(audit_rows).count("account.move_out.excess_held") == 1


def test_w5_api_hold_excess__refuses_when_nothing_is_disputed(brazos, marcus, monkeypatch):
    """The same account with nothing disputed lands on `refund_due`, so there
    is no held excess to record and the route refuses by name."""
    with tenant_ctx(brazos):
        account = _refundable(monkeypatch, marcus, brazos)
        response = _post(
            customers_api.account_hold_excess, brazos, account["id"], {"final_bill": "142.30"}
        )

    assert response.status_code == 409
    assert response.data["br_ref"] == "BR-CUS-096"
    assert response.data["message_key"] == "customers.move_out.excess_not_held"


# ══════════════════════════════════════════════════════════════════════════
# 6 · RBAC and tenant isolation — the two claims only the route can make
# ══════════════════════════════════════════════════════════════════════════
def test_w5_api__an_executive_may_not_reach_any_of_the_four(brazos, marcus):
    """A4 gives Executive **View** on Premises/Accounts, and every other read in
    `customers/api.py` is `AnyTenantRole` for that reason — but
    `move_out_settlement.settlement_for` is `@require_role(SYSTEM_ADMIN,
    BILLING_CLERK)` and refuses an Executive itself. The narrower permission
    class is mounted so the two halves agree rather than handing a permitted
    view straight to a 403 from the layer below. The divergence from A4 is
    REPORTED in the lane report; it is not resolved here, because widening or
    narrowing the rule belongs to the settlement module.
    """
    with tenant_ctx(brazos):
        account = _account(marcus, brazos)
        answers = [_get(brazos, account["id"], role="executive", query={"final_bill": "94.45"})]
        for view in (
            customers_api.account_settle_shortfall,
            customers_api.account_refund,
            customers_api.account_hold_excess,
        ):
            answers.append(_post(view, brazos, account["id"], {}, role="executive"))

    assert [answer.status_code for answer in answers] == [403, 403, 403, 403]


@pytest.mark.isolation
def test_w5_api__another_tenants_account_is_404_never_403(brazos, lonestar, marcus, erin):
    """HR-1 / BR-TEN-003: existence must not leak. A cross-tenant id is
    indistinguishable from an absent one on all four routes — and it matters
    more here than on a list, because these routes answer *"how much of this
    customer's money comes back"*: a 403 would confirm that a guessed account
    number belongs to somebody, and a settlement payload would say how much
    they hold.

    The 404 comes from `selectors.account_or_404`, which every one of the four
    reaches through the settlement service. Asserted on all four rather than on
    one, because a route wired to a selector that skipped it would pass a
    single-route test.
    """
    with tenant_ctx(brazos):
        brazos_account = _account(marcus, brazos)

    with tenant_ctx(lonestar):
        answers = [_get(lonestar, brazos_account["id"], query={"final_bill": "94.45"})]
        for view in (
            customers_api.account_settle_shortfall,
            customers_api.account_refund,
            customers_api.account_hold_excess,
        ):
            answers.append(_post(view, lonestar, brazos_account["id"], {"final_bill": "94.45"}))

    assert [answer.status_code for answer in answers] == [404, 404, 404, 404]
    # G1/G4: a 404 carries no catalog code, so it is byte-identical to any other.
    assert {answer.data["code"] for answer in answers} == {None}


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-005 (04-docs/05-modules/03-customers/02-business-rules.md ·
#         04-docs/02-decisions/19-cr031-service-request-capture.md §15.9 ·
#         04-docs/02-decisions/18-cr030-onboarding-design.md §6.2 W5 tasks 5.8/5.9 ·
#         apps/customers/move_out_settlement.py's own docstring, read in full)
# generated: 2026-08-25 by the CR-030 W5 move-out SERVING lane (tasks 5.8 · 5.9, API half)
# checklist: A✔ B=n/a(backend-only lane; the S20 screen exists and is another lane's file) C✔ D✔ E=deferred(no-frontend-half — `moveShared.closeImpactPort()` still returns null and wiring it is the frontend lane's) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: black✔ · g09 PASS · g32 PASS (0 unresolved, baseline 0) · g20 PASS · g18 unchanged from its pre-lane baseline (pre-existing failures, none in this lane's files) — figures in the lane report
# exceptions: (1) THE ARITHMETIC IS NOT RESTATED HERE. Every landing, worked PO
#         figure and rule refusal is proved in tests/test_w5_move_out_settlement.py
#         against the module; a second copy in this file could drift from the
#         first. What is asserted here is what only a ROUTE can be wrong about.
#         (2) `openapi/schema.json` IS NOT REGENERATED. Four endpoints are added
#         and BE-11 TC05 diffs the committed snapshot, which lives outside
#         apps/customers and is not this lane's file (hard-won law 5).
#         `python manage.py export_openapi` is the command — MEASURED: TC05 is
#         RED on this tree and names it. REPORTED for whoever owns that commit.
#         (3) `refund` and `hold-excess` ARE ADDED PATHS. B18 §6.2 lists the
#         move-out gap as "❌ two" and no screen names a path for either. The
#         callables exist, are tested and were unreachable.
#         (4) THE TWO PUBLISHED SEAMS ARE PATCHED IN THE REFUND/HOLD TESTS ONLY.
#         BR-CUS-057's accrual and BR-CUS-096's disputed amount are published by
#         nothing, so those two landings are unreachable in a real deployment
#         today. That is asserted UNPATCHED in the gap test; the patched tests
#         exercise the route rather than the wall in front of it.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

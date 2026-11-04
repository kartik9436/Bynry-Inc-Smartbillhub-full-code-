# ── Trace ──────────────────────────────────────────────
# Change:  CR-094-BRC01 step 2 wave H — the ONE deposit capability.
#          PO 2026-09-12: *"(a) It is one concept — money held against an
#          account — and building it four times would give four behaviours."*
#          and *"if there are deposits, then there should be a proper flow to
#          accept those deposit also … but it should be in the same flow"*.
#          Screens: S18 step 4 · S19 step 5 (blueprint pages 63-64, 70-71)
# Rules:   BR-CUS-025 (a deposit is a LIABILITY, never revenue) · BR-CUS-037
#          (customers is an ENTRY POINT and writes no financial table) ·
#          BR-CUS-670 (the register moves with the money — already built, and
#          this file proves the wizard reaches it rather than duplicating it) ·
#          BR-CUS-050 (the ORIGINAL receipt date) · BR-PAY-012 (a deposit meets
#          no bill and becomes no credit) · BR-RAT-020/023 (`plan_deposit_rules`
#          holds the standard figure) · BR-SHL-019 (ONE transactional commit)
# Amended: 2026-09-23 — DEF-CUS-6369 (the figure is the PLAN's for the
#          category, no override) · DEF-CUS-6370 (a waive is kept on the
#          account) · DEF-CUS-6371 (OQ-CUS-12620 (a): *No* only where the plan
#          asks none) · DEF-CUS-6372 (an Executive cannot reach the waive)
# Amended: 2026-09-24 — OQ-CUS-12623 / BR-CUS-1050: a Billing Clerk OR a System
#          Admin waives (PO: "clark and sysem admin can do it"); Executive out
#          of the set, DEF-CUS-6372 closed
# Amended: 2026-10-21 — DEF-CUS-10324 / CR-186-BRC10: a deposit taken today is
#          POSTED (never cleared at entry), the register holds it at once, no
#          "not cleared yet" note is raised, and a `cleared_at` key is refused
#          by name; the result reports `held`, not `cleared`
# Tests:   this file
# ───────────────────────────────────────────────────────
"""**Can a clerk take a deposit in a move-in?** Until this wave, no.

WHAT WAS ACTUALLY MISSING, MEASURED ON 2.239.4
----------------------------------------------
Not the engine. `POST /accounts/{id}/payments` has accepted
`purpose="deposit"` since 2026-08-27 and does the whole job — the 2300
liability, the `BR-CUS-670` register, the customer's receipt. **No screen in
the product ever sent it.** Four wizards drew a deposit and all four refused
it by name.

So every case here asks the wizard's own question — *did the money arrive
through the flow* — and asserts it on the three artefacts that have to agree:
the payment row, the `accounts.deposit_on_file` register, and the account this
module created in the same transaction.

⚠ **AMENDED 2026-09-23 — THE FIGURE IS THE PLAN'S.** PO, verbatim: *"you need
to take deposit amount as per plan ; plan will have deposite chanrge code as
per customer categoris ;so that value should be atken as by default no
override is required"*, and on `OQ-CUS-12620`: *"(a) When the plan asks a
deposit: take it or waive it (supervisor). "No" only when the plan asks
none."* So every fixture unit now stands on a plan whose `plan_deposit_rules`
asks **$150.00** of a Residential account — Rosa Pemberton's worked figure —
and that figure is ASSERTED, so a drift in where it comes from goes red.

⚠ **AND ONE CASE ASSERTS AN ABSENCE ON PURPOSE.** `test_..._second_writer` is
the guard against this wave's own first draft, which wrote
`accounts.deposit_on_file` itself. Two paths to one money column is `DEF-154`'s
shape, so the register figure must equal what PAYMENTS reported and nothing
else. It goes red the day somebody adds a second writer here.
"""

import uuid
from datetime import date
from decimal import Decimal

import pytest

from apps.customers import deposit as customers_deposit
from apps.customers import api as customers_api
from apps.customers import selectors as customers_selectors
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.payments import models as payment_models
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    api_call,
    brazos,
    dana,
    make_premises,
    make_unit,
    marcus,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

MOVE_IN_DAY = "2026-08-15"
#: **THE WORKED FIGURE — Rosa Pemberton, Residential, on a plan asking $150.00.**
#: Blueprint p070 draws `$150.00` too, and B14 rule 37 makes that an
#: ILLUSTRATION; this figure is not the drawing's. It is the fixture PLAN's
#: `plan_deposit_rules` row for `residential`, and every case asserts the
#: account is asked exactly that — so if the figure ever comes from anywhere
#: else (a typed box, a default, the drawing), these go red.
A_DEPOSIT = "150.00"
THE_PLANS_FIGURE = Decimal("150.0000")
#: The same plan's figure for `commercial` — so a change of category is seen to
#: MOVE the figure, not merely to keep it.
COMMERCIAL_FIGURE = Decimal("400.0000")
HARDSHIP = "Hardship"


# ══════════════════════════════════════════════════════════════════════════
# Fixture plumbing — built through the real services of the owning modules
# ══════════════════════════════════════════════════════════════════════════
def _published_plan(tenant, name="Residential Standard", service_code="electric"):
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


def _ask(tenant, plan, code, amount):
    """`plan_deposit_rules` — rate_plan × category → one fixed figure
    (`BR-RAT-020/023`). `AccountType` is customers' tenant-scoped catalogue and
    the rule points at it by a plain uuid across the boundary (B2 §2)."""
    account_type = customers_services.models.AccountType.objects.get(
        tenant_id=tenant.id, code=code
    )
    rating_models.PlanDepositRule.objects.update_or_create(
        tenant=tenant,
        rate_plan=plan,
        account_type_id=account_type.id,
        defaults={"amount": amount, "currency": "USD"},
    )


def _unit(actor, tenant, *, label="Unit A", plan_name="Residential Standard", asks=True):
    """A vacant unit on a published plan. `asks=True` (the default) states the
    worked figure: Residential $150.00, Commercial $400.00, nothing else."""
    premises = make_premises(actor)
    unit = make_unit(actor, premises["id"], label=label)
    plan = _published_plan(tenant, name=plan_name)
    if asks:
        _ask(tenant, plan, "residential", THE_PLANS_FIGURE)
        _ask(tenant, plan, "commercial", COMMERCIAL_FIGURE)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit, plan


def _outgoing(actor, tenant, unit):
    # The outgoing tenancy predates the deposit step, so it is opened the way a
    # migrated account is — with its deposit answered as the plan asks.
    return customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": "Sarah Miller"},
            "customer": {
                "display_name": "Sarah Miller",
                "kind": "person",
                "identity": {"phone": "+1 (281) 555-0155"},
            },
            "deposit": {"decision": "required", "take_now": False},
        },
    )


def _payload(**overrides):
    payload = {
        "account_type": "residential",
        "status": "active",
        "opened_at": MOVE_IN_DAY,
        "contact": {
            "full_name": "Rosa Pemberton",
            "email": "rosa.pemberton@example.com",
            "phone": "+1 (281) 555-0144",
        },
        "customer": {
            "display_name": "Rosa Pemberton",
            "kind": "person",
            "identity": {"phone": "+1 (281) 555-0144"},
        },
    }
    payload.update(overrides)
    return payload


def _taken_today(**overrides):
    """Step 5, filled in as a clerk taking the money today. The AMOUNT is the
    figure the step SHOWED — the plan's — sent so a plan edited in between is
    refused rather than silently re-priced (see `deposit.py`)."""
    block = {
        "decision": "required",
        "amount": A_DEPOSIT,
        "due_on": MOVE_IN_DAY,
        "take_now": True,
        "method_code": "cash",
        "confirmation": "AUTH 55192",
        "posted_at": MOVE_IN_DAY,
        "idempotency_reference": str(uuid.uuid4()),
    }
    block.update(overrides)
    return block


def _waived(**overrides):
    block = {"decision": "waived", "amount": A_DEPOSIT, "waive_reason": HARDSHIP}
    block.update(overrides)
    return block


def _deposit_payments(account_id):
    return list(
        payment_models.Payment.objects.filter(
            account_id=account_id, purpose=payment_models.PURPOSE_DEPOSIT
        )
    )


def _refused_key(raised):
    return raised.value.message_key


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE CAPABILITY — a clerk takes the PLAN's deposit inside the move-in
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_wh__a_move_in_takes_the_deposit_and_the_register_moves(brazos, dana):
    """The whole wave, in one case: the money arrives through the FLOW.

    Three artefacts have to agree, and the register figure is asserted against
    what payments reported rather than against the clerk's number — see the
    module docstring.
    """
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos)
        outgoing = _outgoing(dana, brazos, unit)
        customers_services.move_out(dana, outgoing["id"], {"moved_out_on": "2026-08-14"})

        result = customers_services.move_in(dana, outgoing["id"], _payload(deposit=_taken_today()))

        # (a) the payment exists, with the purpose that makes it a liability
        payments = _deposit_payments(result["id"])
        assert len(payments) == 1
        assert payments[0].amount == THE_PLANS_FIGURE
        # CR-186-BRC10: posted at entry; only bank reconciliation clears it.
        assert payments[0].status == "posted"
        assert payments[0].cleared_at is None

        # (b) the register moved — BR-CUS-670, written by payments' own call
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == THE_PLANS_FIGURE
        assert account.deposit_received_on == date.fromisoformat(MOVE_IN_DAY)
        assert account.deposit_assessed == THE_PLANS_FIGURE

        # (c) the wizard's own answer says so, so the confirmation can too
        assert result["deposit"]["held"] is True
        assert "cleared" not in result["deposit"]
        assert Decimal(result["deposit"]["amount"]) == THE_PLANS_FIGURE
        # Compared as MONEY, not as text: the register column is `NUMERIC(18,6)`.
        assert Decimal(result["deposit"]["held_after"]) == account.deposit_on_file
        assert result["deposit"]["payment_no"] is not None
        # ⚠ The plan lookup RAN, so the confirmation must not say it is unbuilt.
        assert "deposit_not_applied" not in {w.get("code") for w in result["warnings"]}


def test_cr094_wh__the_same_capability_serves_the_new_account_wizard(brazos, dana):
    """PO: *"It is one concept … building it four times would give four
    behaviours."* So S18 reaches it by the SAME keyword and the SAME figure."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit B")
        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_taken_today())
        )
        assert result["deposit"]["held"] is True
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == THE_PLANS_FIGURE
        assert len(_deposit_payments(result["id"])) == 1


# ══════════════════════════════════════════════════════════════════════════
# 2 · THE FIGURE IS THE PLAN'S — for the category, with no override
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_wh__rosa_is_asked_the_plans_150_with_no_figure_sent(brazos, dana):
    """**The worked figure.** Rosa is Residential; the unit's plan asks
    Residential **$150.00**. The block names no amount at all — the server
    takes it from the plan — and she is asked exactly $150.00."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit P")
        block = _taken_today()
        del block["amount"]
        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=block)
        )
        assert Decimal(result["deposit"]["amount"]) == THE_PLANS_FIGURE
        assert _deposit_payments(result["id"])[0].amount == THE_PLANS_FIGURE
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_assessed == THE_PLANS_FIGURE


def test_cr094_wh__a_figure_that_is_not_the_plans_is_refused_by_name(brazos, dana):
    """No override (PO 2026-09-23). A block sending **$120.00** against a plan
    asking **$150.00** — a hand-built request, or a screen that read the plan
    before somebody edited it — is REFUSED, naming the amount field, and
    nothing is written: the customer is never charged a figure nobody showed
    them, and never an override either."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit Q")
        before = customers_services.models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as raised:
            customers_services.create_account(
                dana, _payload(unit_id=str(unit["id"]), deposit=_taken_today(amount="120.00"))
            )
        assert _refused_key(raised) == customers_deposit.AMOUNT_NOT_PLAN
        assert raised.value.params["amount"] == str(THE_PLANS_FIGURE)
        assert {e["field"] for e in raised.value.field_errors} == {"deposit.amount"}
        assert customers_services.models.Account.objects.count() == before


def test_cr094_wh__a_change_of_category_moves_the_figure(brazos, dana):
    """*"plan will have deposite chanrge code as per customer categoris"*. The
    same unit's plan asks Commercial **$400.00**, and asks Industrial nothing —
    so a Commercial account is asked $400.00 and an Industrial one is asked no
    deposit at all."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit R")
        commercial = customers_services.create_account(
            dana,
            _payload(
                unit_id=str(unit["id"]),
                account_type="commercial",
                deposit={"decision": "required", "take_now": False},
            ),
        )
        assert Decimal(commercial["deposit"]["amount"]) == COMMERCIAL_FIGURE

        unit2, _p2 = _unit(dana, brazos, label="Unit S")
        industrial = customers_services.create_account(
            dana, _payload(unit_id=str(unit2["id"]), account_type="industrial")
        )
        assert "deposit" not in industrial


def test_cr094_wh__the_step_reads_the_same_figure_before_the_account_exists(brazos, dana):
    """`GET /accounts/deposit-standard` — what the Deposit step SHOWS. The same
    walk the commit takes, from the unit and the category CODE the wizard holds,
    so the figure on screen cannot disagree with the figure the server takes."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit T")
        residential = customers_deposit.standard_for_unit(unit["id"], "residential")
        assert residential["asks"] is True
        assert Decimal(residential["amount"]) == THE_PLANS_FIGURE
        assert residential["currency"] == "USD"
        assert Decimal(
            customers_deposit.standard_for_unit(unit["id"], "commercial")["amount"]
        ) == COMMERCIAL_FIGURE
        industrial = customers_deposit.standard_for_unit(unit["id"], "industrial")
        assert industrial == {**industrial, "asks": False, "amount": None, "currency": None}

        response = api_call(
            customers_api.account_deposit_standard,
            "get",
            user=FakeUser(),
            role="billing_clerk",
            tenant=brazos,
            query={"unit_id": str(unit["id"]), "account_type": "residential"},
        )
        assert response.status_code == 200, response.data
        assert Decimal(response.data["amount"]) == THE_PLANS_FIGURE


# ══════════════════════════════════════════════════════════════════════════
# 3 · THE PLAN DECIDES WHICH ANSWERS EXIST — OQ-CUS-12620, ruled (a)
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_wh__no_is_refused_when_the_plan_asks_a_deposit(brazos, marcus):
    """*"we ahve to take depsoite if plans asked … "No" only when the plan asks
    none."* A billing clerk answering *No* on Rosa's $150.00 plan is refused
    in words — and so is a request that simply leaves the block OFF, which is
    how a hand-built request would try to skip it."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(marcus, brazos, label="Unit U")
        before = customers_services.models.Account.objects.count()
        for deposit_block in ({"decision": "not_required"}, None):
            payload = _payload(unit_id=str(unit["id"]))
            if deposit_block is not None:
                payload["deposit"] = deposit_block
            with pytest.raises(errors.ValidationError) as raised:
                customers_services.create_account(marcus, payload)
            assert _refused_key(raised) == customers_deposit.PLAN_ASKS_DEPOSIT
            assert raised.value.params["amount"] == str(THE_PLANS_FIGURE)
        assert customers_services.models.Account.objects.count() == before


def test_cr094_wh__no_plan_figure_means_no_deposit_and_nothing_to_take(brazos, dana):
    """rating's own warning, honoured one layer up: *"`None` is 'this plan asks
    no deposit of this category'"*. So *No* is the only answer — the account
    opens with no deposit block at all — and taking or waiving one is refused,
    because there is no figure to take or forgive and inventing one is the
    override the PO ruled out."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit H", plan_name="No Deposit Plan", asks=False)
        none_owed = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit={"decision": "not_required"})
        )
        assert "deposit" not in none_owed
        assert _deposit_payments(none_owed["id"]) == []

        for block in (_taken_today(), _waived()):
            unit2, _p2 = _unit(
                dana, brazos, label=f"Unit H-{block['decision']}", plan_name="No Deposit Plan",
                asks=False,
            )
            with pytest.raises(errors.ValidationError) as raised:
                customers_services.create_account(
                    dana, _payload(unit_id=str(unit2["id"]), deposit=block)
                )
            assert _refused_key(raised) == customers_deposit.PLAN_ASKS_NONE


def test_cr094_wh__the_one_condition_is_plan_asks_deposit():
    """`OQ-CUS-12620` moves ONE condition, and this pins what it answers — a
    zero rule is *asks none*, not *asks zero*."""
    assert customers_deposit.plan_asks_deposit(None) is None
    assert customers_deposit.plan_asks_deposit({"amount": None}) is None
    assert customers_deposit.plan_asks_deposit({"amount": Decimal("0")}) is None
    assert customers_deposit.plan_asks_deposit({"amount": Decimal("150.000000")}) == Decimal(
        "150.0000"
    )


# ══════════════════════════════════════════════════════════════════════════
# 4 · NO CLEARING DATE — posted at entry (CR-186-BRC10, DEF-CUS-10324)
# ══════════════════════════════════════════════════════════════════════════
def test_def_cus_10324__a_move_in_deposit_taken_today_is_posted_and_held_at_once(brazos, dana):
    """PO 2026-10-21: *"first they will pot the payment - so we crete the record
    and add posting date; then later … it is cleared with clearing date"*. The
    blueprint's *"the new account will read a deposit of $0.00 while the cash is
    in the drawer"* is superseded: a $150.00 deposit taken at a move-in today is
    recorded `posted` with NO clearing date, the register reads $150.00 at once,
    and nothing tells the clerk it reads $0.00 until it clears.

    Driven through the S19 wizard's STANDALONE road (`create_account` — a
    move-in into a vacant unit; `test_move_in_nineteen_scenarios` names both
    roads as the wizard's commit). The chained road needs a move-out whose
    final bill is drafted by a job, which a sandbox with no broker refuses
    (`final_bill_not_drafted`) before any deposit is touched."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit C")

        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_taken_today())
        )

        payments = _deposit_payments(result["id"])
        assert len(payments) == 1
        assert payments[0].amount == Decimal("150.0000")
        assert payments[0].status == "posted"
        assert payments[0].cleared_at is None
        assert payments[0].posted_at.date() == date.fromisoformat(MOVE_IN_DAY)

        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == Decimal("150.0000")

        retired = "deposit_payment_has_not_cleared"
        assert retired not in result["deposit"]["notes"]
        assert retired not in {w.get("code") for w in result.get("warnings") or []}
        assert result["deposit"]["held"] is True


def test_def_cus_10324__a_clearing_date_from_the_client_is_refused_by_name():
    """A key accepted and silently ignored is a clearing date the clerk believes
    they recorded, so `cleared_at` is no longer in the deposit vocabulary and is
    refused as an unknown field — on the deposit block and on the move-in's
    *Pay now* block (`cleared_on`) alike."""
    from apps.customers import move_fees

    with pytest.raises(errors.ValidationError) as raised:
        customers_deposit.clean(_taken_today(cleared_at=MOVE_IN_DAY))
    assert raised.value.field_errors[0]["field"] == "cleared_at"
    assert _refused_key(raised) == "customers.account.unknown_field"
    assert "cleared_at" not in customers_deposit.DEPOSIT_FIELDS

    with pytest.raises(errors.ValidationError) as raised:
        move_fees.clean_payment(
            {
                "mode": "pay_now",
                "method_code": "cash",
                "amount": "150.00",
                "received_on": MOVE_IN_DAY,
                "cleared_on": MOVE_IN_DAY,
            }
        )
    assert raised.value.field_errors[0]["field"] == "payment.cleared_on"
    assert _refused_key(raised) == "customers.account.unknown_field"


def test_cr094_wh__a_deposit_owed_but_not_taken_today_goes_with_the_first_bill(brazos, dana):
    """*"Falls on the first bill. Unless taken today."* The decision is recorded
    and no money moves, so nothing on the account claims a deposit it does not
    hold — and the figure it will be billed is the plan's."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit F")
        result = customers_services.create_account(
            dana,
            _payload(
                unit_id=str(unit["id"]),
                deposit={"decision": "required", "take_now": False},
            ),
        )
        assert customers_deposit.DEFERRED_TO_FIRST_BILL in result["deposit"]["notes"]
        assert _deposit_payments(result["id"]) == []
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == Decimal("0")
        assert account.deposit_assessed == THE_PLANS_FIGURE


# ══════════════════════════════════════════════════════════════════════════
# 5 · A WAIVE — a Billing Clerk's or a System Admin's (2026-09-24), KEPT ON THE ACCOUNT (DEF-CUS-6370)
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_wh__a_waive_is_kept_on_the_account_with_who_when_and_why(brazos, dana):
    """A System Admin waives Rosa's **$150.00** for *Hardship*. Nothing is taken,
    nothing is still to collect — and the ACCOUNT says so, for as long as it
    exists: `audit_log` is pruned with no row exempt (`OQ-1340`), so the
    commit's answer and the audit row were never enough.

    Read back off the ROW, not off the answer: a waive that only reached the
    response would pass every case that reads the response."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit D")
        waived = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_waived())
        )
        assert waived["deposit"]["decision"] == "waived"
        assert customers_deposit.WAIVED in waived["deposit"]["notes"]
        assert _deposit_payments(waived["id"]) == []

        account = customers_services.models.Account.objects.get(pk=waived["id"])
        assert account.deposit_waived_amount == THE_PLANS_FIGURE
        assert account.deposit_waived_by_id == dana.id
        assert account.deposit_waived_at is not None
        assert account.deposit_waive_reason == HARDSHIP
        # Forgiven, so nothing is demanded and nothing is held.
        assert account.deposit_assessed is None
        assert account.deposit_on_file == Decimal("0")

        # And the account page is SERVED it, by name and never by id (rule 31).
        detail = customers_selectors.account_detail_dict(account)
        waiver = detail["deposit_waiver"]
        assert Decimal(waiver["amount"]) == THE_PLANS_FIGURE
        assert waiver["currency"] == account.currency
        assert waiver["reason"] == HARDSHIP
        assert waiver["waived_by_name"] and str(dana.id) not in waiver["waived_by_name"]


def test_cr094_wh__an_account_nobody_waived_serves_no_waiver(brazos, dana):
    """NULL is *nothing was waived*, never a zero block the tile would read as
    *waived $0.00*."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit E")
        result = customers_services.create_account(
            dana,
            _payload(unit_id=str(unit["id"]), deposit={"decision": "required", "take_now": False}),
        )
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert customers_selectors.account_detail_dict(account)["deposit_waiver"] is None


def test_cr094_wh__a_billing_clerk_waives_rosas_150(brazos, marcus):
    """**FLIPPED 2026-09-24 — `OQ-CUS-12623`, `BR-CUS-1050` amended.** PO,
    verbatim: *"p3 - clark and sysem admin can do it"*.

    This case was `…_a_billing_clerk_is_refused_the_waive_in_words` and
    asserted p073's *"(needs a supervisor)"*. Now the worked case: a Billing
    Clerk waives Rosa's **$150.00** with the reason *Hardship*; nothing is
    taken, and the account reads **Waived · $150.00**, kept on the ROW with who
    and why."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(marcus, brazos, label="Unit V")
        waived = customers_services.create_account(
            marcus, _payload(unit_id=str(unit["id"]), deposit=_waived())
        )
        assert waived["deposit"]["decision"] == "waived"
        assert _deposit_payments(waived["id"]) == []
        account = customers_services.models.Account.objects.get(pk=waived["id"])
        assert account.deposit_waived_amount == Decimal("150.0000")
        assert account.deposit_waived_by_id == marcus.id
        assert account.deposit_waive_reason == HARDSHIP
        waiver = customers_selectors.account_detail_dict(account)["deposit_waiver"]
        assert Decimal(waiver["amount"]) == Decimal("150")
        assert waiver["reason"] == HARDSHIP


def test_cr094_wh__the_waive_set_is_a_billing_clerk_or_a_system_admin():
    """`WAIVE_ROLES` is exactly the PO's two — and an Executive is refused BY
    NAME, told who can. Asserted on the gate itself because no screen lets an
    Executive reach it (A4: View on Accounts), which is why the door case
    below cannot see the set."""
    from types import SimpleNamespace

    assert customers_deposit.WAIVE_ROLES == frozenset({"billing_clerk", "system_admin"})
    with pytest.raises(errors.BizError) as raised:
        customers_deposit._refuse_unless_may_waive(SimpleNamespace(role="executive"))
    assert raised.value.message_key == customers_deposit.WAIVE_NOT_YOUR_ROLE
    assert raised.value.params["accepts"] == ["billing_clerk", "system_admin"]
    for role in ("billing_clerk", "system_admin"):
        customers_deposit._refuse_unless_may_waive(SimpleNamespace(role=role))


def test_cr094_wh__a_waive_needs_its_reason():
    """Kept on the account, so it must say why — refused on its OWN field."""
    with pytest.raises(errors.ValidationError) as raised:
        customers_deposit.clean({"decision": "waived"})
    assert {e["field"] for e in raised.value.field_errors} == {"waive_reason"}


def test_cr094_wh__an_executive_cannot_reach_the_waive_and_is_not_in_the_set(brazos, dana):
    """**`DEF-CUS-6372` CLOSED 2026-09-24 — the rule moved to meet the door.**
    `BR-CUS-1050` named System Admin OR Executive while A4 (signed) makes an
    Executive VIEW on Accounts, so the door refused an Executive before the
    waive was asked. The PO's *"clark and sysem admin can do it"* takes the
    Executive out of the set, so the door and the rule now say the same thing:
    the door still refuses (`AuthError`), and the set above no longer names
    them."""
    avery = staff_actor(brazos, "executive", "avery@brazosbendutilities.test")
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit W")
        with pytest.raises(errors.AuthError):
            customers_services.create_account(
                avery, _payload(unit_id=str(unit["id"]), deposit=_waived())
            )


# ══════════════════════════════════════════════════════════════════════════
# 6 · THE REFUSALS — each names its OWN field (DEF-CUS-5082's lesson)
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "block,field",
    [
        ({"decision": "required", "amount": "-5.00"}, "amount"),
        ({"decision": "required", "amount": "not money"}, "amount"),
        ({"decision": "not_required", "take_now": True}, "take_now"),
        ({"decision": "required", "take_now": True}, "method_code"),
        ({"decision": "sort_of"}, "decision"),
        ({"decision": "required", "reason": "because"}, "reason"),
        ({"decision": "required", "waive_note": "x"}, "waive_note"),
        ({"decision": "waived"}, "waive_reason"),
    ],
)
def test_cr094_wh__every_refusal_names_its_own_field(block, field):
    """A form that refuses on one field and marks another makes a clerk give
    up — `DEF-CUS-5082`. So the FIELD is asserted, not merely a refusal."""
    with pytest.raises(errors.ValidationError) as raised:
        customers_deposit.clean(block)
    named = {entry["field"] for entry in (raised.value.field_errors or ())}
    assert field in named, f"refused {sorted(named)}, expected {field}"


def test_cr094_wh__an_absent_reason_is_still_accepted():
    """*Why this amount* is gone from the screen; the server stays tolerant of
    a block without one, and of a parked draft that still carries one."""
    assert customers_deposit.clean({"decision": "required"}).reason is None
    assert customers_deposit.clean({"decision": "required", "reason": "standard"}).reason == (
        "standard"
    )


def test_cr094_wh__amount_taken_defaults_to_the_deposit():
    """*"Defaults to the deposit."* Resolved on the SERVER."""
    instruction = customers_deposit.clean(
        {"decision": "required", "amount": "150", "take_now": False}
    )
    assert instruction.amount_taken == Decimal("150.0000")
    assert instruction.amount == Decimal("150.0000")


def test_cr094_wh__money_is_quantized_to_four_decimals_never_a_float():
    """CLAUDE.md hard rule 2, PO re-sign 2026-08-22: money to 4 decimals."""
    instruction = customers_deposit.clean(
        {"decision": "required", "amount": "150.123456789", "take_now": False}
    )
    assert instruction.amount == Decimal("150.1235")
    assert isinstance(instruction.amount, Decimal)


# ══════════════════════════════════════════════════════════════════════════
# 7 · ONE TRANSACTION, AND ONE WRITER
# ══════════════════════════════════════════════════════════════════════════
def test_cr094_wh__a_refused_deposit_writes_no_account_at_all(brazos, dana):
    """`BR-SHL-019` — ONE transactional commit. A deposit of `0` on a plan
    asking $150.00 is refused inside the creating transaction, after the
    account row exists — and the rollback takes the account with it."""
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit J")
        before = customers_services.models.Account.objects.count()
        with pytest.raises(errors.ValidationError):
            customers_services.create_account(
                dana,
                _payload(unit_id=str(unit["id"]), deposit={"decision": "required", "amount": "0"}),
            )
        assert customers_services.models.Account.objects.count() == before


def test_cr094_wh__customers_is_not_a_second_writer_of_the_register(brazos, dana, monkeypatch):
    """⚠ **THE GUARD AGAINST THIS WAVE'S OWN FIRST DRAFT.** `BR-CUS-670`'s
    `record_deposit_movement` is the ONLY thing that may move
    `accounts.deposit_on_file`. Proved by making it unreachable and asserting
    the column does NOT move."""
    from apps.payments import services as payment_services

    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit K")
        monkeypatch.setattr(
            payment_services, "DEPOSIT_REGISTER_WRITE", "record_deposit_movement_absent"
        )
        result = customers_services.create_account(
            dana, _payload(unit_id=str(unit["id"]), deposit=_taken_today())
        )
        account = customers_services.models.Account.objects.get(pk=result["id"])
        assert account.deposit_on_file == Decimal(
            "0"
        ), "customers wrote the register itself — BR-CUS-670's writer is the only one"
        assert result["deposit"]["held_after"] is None
        assert result["deposit"]["held"] is False
        assert "deposit_register_not_moved" in result["deposit"]["notes"]


def test_cr094_wh__the_api_door_accepts_the_block(brazos, dana):
    """The vocabulary reaches the HTTP door with no per-view plumbing."""
    assert "deposit" in customers_services.CREATE_FIELDS
    assert "deposit" in customers_services.MOVE_IN_FIELDS
    with tenant_ctx(brazos):
        unit, _plan = _unit(dana, brazos, label="Unit L")
        response = api_call(
            customers_api.accounts,
            "post",
            user=FakeUser(),
            role="system_admin",
            tenant=brazos,
            data=_payload(unit_id=str(unit["id"]), deposit=_taken_today()),
        )
        assert response.status_code == 201, response.data
        assert response.data["deposit"]["held"] is True

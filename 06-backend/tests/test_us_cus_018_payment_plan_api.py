# ── Trace ──────────────────────────────────────────────
# Story:    US-CUS-018 (S24 payment-plan wizard — its FOUR routes) ·
#           US-PAY-017 (the plan rows and the published read behind them)
#           Screens: S24 (entry S21)
# Rules:    BR-CUS-043 (schedule = (total − down) ÷ n, remainder on the FINAL
#           instalment; step-2 edits must re-sum EXACTLY; one live plan per
#           account) · BR-CUS-044 (activation on the CUSTOMER's e-signature
#           alone) · BR-CUS-037 (customers writes no financial table — the rows
#           are payments') · BR-BIL-073 (a plan does NOT suspend the current
#           bill — PO 2026-08-11) · BR-TEN-043 (a business date is an input) ·
#           BR-SHL-025 / BR-IDN-009 (server-enforced RBAC) ·
#           CLAUDE.md rule 2 (money is NUMERIC(18,6) + CHAR(3), never a float)
# Golden:   ❄️ GT-47 (B5 FROZEN): 267.30 − 50.00 over 6 → 5 × 36.22 + 36.20
# ───────────────────────────────────────────────────────
"""The S24 wizard, over HTTP — and the two figures that must come to the penny.

`test_us_cus_018_gt47__the_instalments_come_to_the_penny_over_http` is the case
to read first. ❄️ GT-47 is finance-signed: **267.30 less a 50.00 down payment
over six instalments is 5 × 36.22 and a FINAL 36.20**, and the last row is
36.20 rather than 36.22 because the remainder lands there and nowhere else
(BR-CUS-043 / A7). The assertion is Σ = the spread EXACTLY, as `Decimal` over
the strings the endpoint actually returns — not as a float, and not to a
tolerance. A schedule that is a cent out is an agreement whose own numbers
disagree, and the customer signs it.

`test_us_cus_018_tc6b__an_unreadable_balance_never_opens_the_wizard_at_zero` is
the second. DEF-127: when the ledger cannot be asked what an account owes, this
product used to answer **0.00**, which reads exactly like a settled account. The
wizard's context answers `balance: null` with a reason and `can_propose: false`,
and the preview route REFUSES rather than spreading a balance nobody could read.

Every route is resolved through the REAL root URLconf first: an `api.py` that
exports `urlpatterns` is not an endpoint until `config/urls.py` includes it
(DEF-112 / DEF-128, three times in this repository).
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.urls import resolve

from apps.customers import api as customers_api
from apps.customers import payment_plan

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_ten_helpers import api_call

pytestmark = pytest.mark.django_db

# ❄️ PE-13 / GT-47, verbatim from B5.
PE13_TOTAL = "267.30"
PE13_DOWN = "50.00"
PE13_INSTALLMENT = Decimal("36.22")
PE13_FINAL = Decimal("36.20")
PE13_SPREAD = Decimal("217.30")

# The prototype's own S24 fixture (US-CUS-018 §4) — NOT a frozen figure.
PROTO_TOTAL = "247.30"

TODAY = date(2026, 8, 16)
# ⚠ RELATIVE, NOT A CALENDAR DATE (2026-10-11): `payment_plan.py` refuses a
# first due date on or before the business day, so a fixed `2026-09-01` turned
# four cases red the day the calendar passed it. Two weeks ahead of the real
# day is always lawful and moves no figure (the amounts do not depend on it).
FIRST_DUE = (date.today() + timedelta(days=14)).isoformat()


def an_account(tenant, actor, *, account_no="A-10432", balance="0"):
    """One account on its own unit. The BALANCE is the ledger's and is patched
    per test — customers never writes it (DEF-127)."""
    from apps.customers import models as customer_models

    premises = make_premises(actor, address_line="1408 Elm St")
    unit = make_unit(actor, premises["id"], label=account_no, services=["electric"])
    return customer_models.Account.objects.create(
        tenant=tenant,
        unit_id=unit["id"],
        status=customer_models.AccountStatus.objects.filter(tenant=tenant).first(),
        account_type=customer_models.AccountType.objects.first(),
        account_no=account_no,
    )


@pytest.fixture()
def owing(monkeypatch):
    """The ledger's AR answer, stated by the test rather than posted.

    The wizard reads the balance through `seams.ar_positions` (DEF-127's one
    derivation). Patching the seam is exactly the deployment shape the screen
    sees, and it lets a test say "this account owes 267.30" without standing up
    a bill run to prove an unrelated rule.
    """

    def _owe(amount: str | None, *, unavailable: str | None = None):
        from apps.customers import seams

        # Bound OUTSIDE the class body: a class body cannot read an enclosing
        # name that one of its own attributes shadows.
        reason = None if amount is not None else (unavailable or "seam_unwired")

        class _Positions:
            available = amount is not None
            currency = "USD" if amount is not None else None
            basis = "accrual"
            unavailable = reason

            def amount_for(self, _account_id):
                return None if amount is None else Decimal(amount)

        monkeypatch.setattr(seams, "ar_positions", lambda *a, **k: _Positions())

    return _owe


def _context(tenant, actor, account, role="system_admin"):
    return api_call(
        customers_api.account_payment_plans_entry,
        "get",
        user=actor.user if hasattr(actor, "user") else None,
        role=role,
        tenant=tenant,
        account_id=str(account.id),
    )


def _preview(tenant, actor, account, **body):
    payload = {
        "balance_to_spread": PROTO_TOTAL,
        "installments": 4,
        "cadence": "monthly",
        "first_due_date": FIRST_DUE,
    }
    payload.update(body)
    return api_call(
        customers_api.account_payment_plan_preview,
        "post",
        user=getattr(actor, "user", None),
        role="system_admin",
        tenant=tenant,
        data=payload,
        account_id=str(account.id),
    )


# ── the routes exist at all (DEF-112's lesson, three modules deep) ──────────
def test_the_four_s24_paths_resolve_through_the_root_urlconf():
    """An `api.py` exporting `urlpatterns` is not an endpoint until
    `config/urls.py` includes it. Resolved through the REAL URLconf."""
    base = "/api/brazosbend"
    assert resolve(f"{base}/accounts/abc/payment-plans").func is (
        customers_api.account_payment_plans_entry
    )
    assert resolve(f"{base}/accounts/abc/payment-plans/preview").func is (
        customers_api.account_payment_plan_preview
    )
    assert resolve(f"{base}/payment-plans/abc/activate").func is (
        customers_api.payment_plan_activate
    )


def test_no_void_route_exists_because_there_is_no_void(brazos, marcus):
    """PO 2026-08-11: *"nodrop we chase for payments until write off"*.

    11b §S24 contracts `POST /payment-plans/{id}/void` and this product has no
    `void` state to move a plan into. Whether STAFF may cancel a plan is
    OQ-239 — MINTED, not answered — so the route is absent rather than stubbed:
    a route that answers 501 is a promise.
    """
    from django.urls import Resolver404

    assert "void" not in payment_plan.PLAN_STATUSES
    with pytest.raises(Resolver404):
        resolve("/api/brazosbend/payment-plans/abc/void")


# ── ❄️ the frozen figure, over the wire ─────────────────────────────────────
def test_us_cus_018_gt47__the_instalments_come_to_the_penny_over_http(brazos, marcus, owing):
    """❄️ GT-47: 267.30 − 50.00 over 6 → **5 × 36.22 + 36.20**, Σ = 217.30.

    The FINAL instalment is 36.20 and not 36.22, and that is the signed figure:
    36.22 × 6 = 217.32, which is two cents more than the customer agreed to
    spread. Asserted on the endpoint's own strings, as Decimal.
    """
    owing(PE13_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        response = _preview(
            brazos,
            marcus,
            account,
            balance_to_spread=PE13_TOTAL,
            down_payment=PE13_DOWN,
            installments=6,
        )
    assert response.status_code == 200
    rows = response.data["installments"]
    amounts = [Decimal(row["amount"]) for row in rows]
    assert amounts == [PE13_INSTALLMENT] * 5 + [PE13_FINAL]
    assert sum(amounts) == PE13_SPREAD  # to the penny, not to a tolerance
    assert Decimal(response.data["spread"]) == PE13_SPREAD
    assert Decimal(response.data["down_payment"]) == Decimal(PE13_DOWN)
    # Rule 2 — the CHAR(3) travels with the figures, and every instalment
    # carries the DAY it falls due.
    assert response.data["currency"] == "USD"
    assert all(row["due_date"] for row in rows)
    # This route commits nothing, and says so on the wire.
    assert response.data["writes"] == []
    # PO 2026-08-11, on the summary's face.
    assert response.data["current_bill_still_due"] is True


def test_us_cus_018_tc1__the_prototype_schedule_over_http(brazos, marcus, owing):
    """A-10432's $247.30 over 4 monthly from Sep 1 → 61.83 / 61.83 / 61.83 /
    61.81, remaining 185.47 / 123.64 / 61.81 / 0.00 (S24 step 2)."""
    owing(PROTO_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        response = _preview(brazos, marcus, account)
    amounts = [Decimal(row["amount"]) for row in response.data["installments"]]
    assert amounts == [Decimal("61.83")] * 3 + [Decimal("61.81")]
    assert [Decimal(row["remaining"]) for row in response.data["installments"]] == [
        Decimal("185.47"),
        Decimal("123.64"),
        Decimal("61.81"),
        Decimal("0.00"),
    ]


def test_us_cus_018_tc3__a_step_two_edit_rebalances_onto_the_final_row(brazos, marcus, owing):
    """Instalment 1 raised to $100.00 → the final row absorbs it and Σ is still
    247.30 exactly (BR-CUS-043 applied to an edit)."""
    owing(PROTO_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        response = _preview(
            brazos, marcus, account, edits=[{"seq": 1, "amount": "100.00"}]
        )
    amounts = [Decimal(row["amount"]) for row in response.data["installments"]]
    assert amounts[0] == Decimal("100.00")
    assert sum(amounts) == Decimal(PROTO_TOTAL)


def test_us_cus_018_tc5__edits_that_do_not_re_sum_are_refused_and_nothing_is_sent(
    brazos, marcus, owing
):
    """Σ = 240.00 against a 247.30 total → 422, and no plan row is written."""
    from apps.payments.collections_models import PaymentPlan

    owing(PROTO_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        response = api_call(
            customers_api.account_payment_plans_entry,
            "post",
            user=getattr(marcus, "user", None),
            role="system_admin",
            tenant=brazos,
            data={
                "balance_to_spread": PROTO_TOTAL,
                "installments": 4,
                "cadence": "monthly",
                "first_due_date": FIRST_DUE,
                "on_date": TODAY.isoformat(),
                "channels": ["email"],
                "edits": [
                    {"seq": 1, "amount": "60.00"},
                    {"seq": 2, "amount": "60.00"},
                    {"seq": 3, "amount": "60.00"},
                    {"seq": 4, "amount": "60.00"},
                ],
            },
            account_id=str(account.id),
        )
        assert response.status_code == 422
        assert PaymentPlan.objects.filter(account_id=account.id).count() == 0


def test_us_cus_018_tc6__zero_instalments_and_over_the_balance_are_refused(
    brazos, marcus, owing
):
    """US-CUS-018 TC-6 — both of its halves, each with its own sentence."""
    owing(PROTO_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        zero = _preview(brazos, marcus, account, installments=0)
        assert zero.status_code == 422
        over = _preview(brazos, marcus, account, balance_to_spread="900.00")
        assert over.status_code == 422
        assert "more than the account owes" in str(over.data)


def test_us_cus_018_tc6b__an_unreadable_balance_never_opens_the_wizard_at_zero(
    brazos, marcus, owing
):
    """DEF-127's rule, applied to S24: absence renders as absence, with its
    reason — never as 0.00, which reads exactly like a settled account."""
    owing(None, unavailable="no_ar_designation")
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        context = _context(brazos, marcus, account)
        assert context.data["balance"] is None
        assert context.data["balance"] != "0.00"
        assert context.data["balance_unavailable"] == "no_ar_designation"
        assert context.data["can_propose"] is False
        assert "ledger" in context.data["cannot_propose_reason"]
        assert context.data["cannot_propose_reason_key"] is None
        # And the preview refuses rather than spreading a balance nobody read.
        assert _preview(brazos, marcus, account).status_code == 409


# ── the send, the signature, and the one-live-plan rule ─────────────────────
def _send(tenant, actor, account, **body):
    payload = {
        "balance_to_spread": PE13_TOTAL,
        "down_payment": PE13_DOWN,
        "installments": 6,
        "cadence": "monthly",
        "first_due_date": FIRST_DUE,
        "on_date": TODAY.isoformat(),
        "channels": ["email"],
    }
    payload.update(body)
    return api_call(
        customers_api.account_payment_plans_entry,
        "post",
        user=getattr(actor, "user", None),
        role="system_admin",
        tenant=tenant,
        data=payload,
        account_id=str(account.id),
    )


def test_us_cus_018_tc1_send__the_plan_is_written_by_payments_and_read_back(
    brazos, marcus, owing
):
    """Send agreement ✓ → the payments-owned rows exist, the plan is
    `agreement_sent` (NOT active), and the account can read it back.

    The read is the half that did not exist before 2026-08-16: the wizard could
    write a plan since 2026-08-11 and nothing could ever show one.
    """
    owing(PE13_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        created = _send(brazos, marcus, account)
        assert created.status_code == 201
        assert created.data["status"] == payment_plan.PLAN_AGREEMENT_SENT
        assert created.data["current_bill_still_due"] is True

        context = _context(brazos, marcus, account)
        plans = context.data["plans"]
        assert len(plans) == 1
        assert plans[0]["status"] == payment_plan.PLAN_AGREEMENT_SENT
        assert plans[0]["currency"] == "USD"
        assert [Decimal(row["amount"]) for row in plans[0]["installments"]] == (
            [PE13_INSTALLMENT] * 5 + [PE13_FINAL]
        )
        # Every instalment carries its own date — a schedule is dated
        # obligations, and an amount without a day is not one.
        assert all(row["due_date"] for row in plans[0]["installments"])
        assert context.data["can_propose"] is False  # TC-7: one live plan
        # PO 2026-10-11 — the refusal a clerk reads is a catalogue sentence
        # ("This account already has a plan."), and no rule id reaches it.
        assert context.data["cannot_propose_reason_key"] == (
            "customers.paymentPlan.alreadyHasPlan"
        )
        assert "BR-" not in context.data["cannot_propose_reason"]


def test_us_cus_018_tc7__a_second_live_plan_is_refused(brazos, marcus, owing):
    """One live plan per account (BR-CUS-043 / A3), refused at the endpoint and
    by the partial unique index behind it."""
    owing(PE13_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        assert _send(brazos, marcus, account).status_code == 201
        second = _send(brazos, marcus, account)
        assert second.status_code == 409
        assert "live payment plan" in str(second.data)


def test_us_cus_018_tc2__the_plan_activates_on_the_customers_signature(brazos, marcus, owing):
    """BR-CUS-044 — `agreement_sent → active` on the CUSTOMER's signature alone.

    No countersignature is taken and none exists. The signature DATE is an
    input (BR-TEN-043); nothing here reads a clock.
    """
    owing(PE13_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        created = _send(brazos, marcus, account)
        activated = api_call(
            customers_api.payment_plan_activate,
            "post",
            user=getattr(marcus, "user", None),
            role="system_admin",
            tenant=brazos,
            data={
                "current_status": payment_plan.PLAN_AGREEMENT_SENT,
                "signed_on": "2026-08-20",
            },
            plan_id=created.data["id"],
        )
        assert activated.status_code == 200
        assert activated.data["status"] == payment_plan.PLAN_ACTIVE

        context = _context(brazos, marcus, account)
        assert context.data["live_plan"]["status"] == payment_plan.PLAN_ACTIVE
        assert context.data["live_plan"]["signed_on"] == "2026-08-20"


def test_a_money_field_sent_as_a_float_is_refused(brazos, marcus, owing):
    """CLAUDE.md rule 2. `float("36.22")` is not 36.22, and a schedule built
    from one re-sums to a total the agreement does not state."""
    owing(PROTO_TOTAL)
    with tenant_ctx(brazos):
        account = an_account(brazos, marcus)
        response = _preview(brazos, marcus, account, balance_to_spread=247.30)
    assert response.status_code == 422


def test_an_executive_may_read_the_plans_and_may_not_propose_one(brazos, marcus, owing):
    """A4: Accounts is Full for Admin/Clerk and VIEW for Executive. Both halves
    are server-enforced (BR-SHL-025) — the screen hiding a control is not the
    gate."""
    from tests.test_us_met_helpers import staff_actor

    owing(PE13_TOTAL)
    with tenant_ctx(brazos):
        priya = staff_actor(brazos, "executive", "priya@brazosbendutilities.test")
        account = an_account(brazos, marcus)
        assert _context(brazos, priya, account, role="executive").status_code == 200
        denied = api_call(
            customers_api.account_payment_plans_entry,
            "post",
            user=getattr(priya, "user", None),
            role="executive",
            tenant=brazos,
            data={"channels": ["email"]},
            account_id=str(account.id),
        )
        assert denied.status_code == 403


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-018@bbed56d (05-golden-tests.md + EP-CUS-06-payment-plan.md + 03-customers/02-business-rules.md + J13-payment-plan-life.md)
# generated: 2026-08-16 by story-coder (surface-debt tails lane — the S24 routes)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: MEASURED, not claimed — see the lane report for the verbatim RED
#         transcripts: the GT-47 assertion was first run against a build_schedule
#         that spread the remainder evenly (6 × 36.22 = 217.32) and FAILED by two
#         cents, and the balance-unavailable case was first run against a context
#         that defaulted the balance to 0.00 and FAILED on `can_propose`.
# exceptions: (1) THE LEDGER'S BALANCE IS PATCHED AT THE SEAM rather than posted
#         through a bill run: `ar_positions` is the one derivation every surface
#         reads (DEF-127), so patching it is the deployment shape the screen
#         sees. A test that posted a bill to prove a schedule would be asserting
#         billing's rules inside a customers story.
#         (2) NO VOID CASE, because there is no void — PO 2026-08-11. The
#         absence is asserted instead (`test_no_void_route_exists_…`), which is
#         how a rule that removed a transition stays visible.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

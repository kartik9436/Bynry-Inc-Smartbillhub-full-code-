# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-010 (First bill: prorated from move-in day + the one-time
#           lines)   Screens: S31 (single-account mode) · S30
# Rules:    BR-BIL-012 (prorated from move-in; deposit non-taxable → deposit
#           liability, never revenue; connection charge) · BR-BIL-062 (a first
#           bill with NO PRIOR READ prices at the plan's minimum, prorated, with
#           no usage line — and is NOT a missing-read exception) · BR-BIL-007
#           (a fee is a tenant charge code, never a literal) · BR-PAY-012 (a
#           deposit-purpose payment satisfies the deposit line) · B4.3 / B4.4 ❄️
#           (calendar-day proration) · B4.2 (fees and deposits are never taxed) ·
#           CLAUDE.md rule 1 · rule 2 · rule 3
# Golden:   GT-3 ❄️ (proration) · WE-6 (20/31, total 287.23)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""US-BIL-010 — the one bill an account will never get again.

**THE PRORATION DENOMINATOR IS THE WHOLE FAILURE MODE.** B4.3 divides occupied
days by CYCLE days, and a first bill's occupied window is shorter than its
cycle by construction. Handing the engine 20/20 instead of 20/31 charges a full
month's base for twenty days, produces a bill that looks entirely reasonable,
and is wrong in the customer's disfavour every time. `tc1` asserts the window
this module hands over, and `tc2` asserts what the engine does with it.

**THE DEPOSIT IS THE MONEY THIS FILE IS REALLY ABOUT.** BR-BIL-012 puts it on
the first bill; BR-PAY-012 says money already paid with purpose `deposit`
satisfies it. Three states, three different bills, and `tc4` walks all three:
nothing paid → **150.00** billed · paid in part → the **remainder** · paid in
full → **no line at all**. And `tc5` is the one that matters most: when the
payments read cannot be reached it answers None, and this module REFUSES rather
than reading None as zero — because zero would bill $150.00 a second time to
somebody who has already paid it, onto a row that is immutable at issue.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import first_bill, models
from apps.billing.exceptions import BillingRuleError
from apps.rating import models as rating_models
from apps.rating import selectors as rating_selectors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401
from tests.test_us_bil_001_prepare import (
    a_billed_unit,
    a_cycle,
    a_priced_plan,
    an_account,
)
from tests.test_us_bil_005_issue import a_run
from tests.test_us_pay_007_credit import _pay

pytestmark = pytest.mark.django_db

# ── WE-6's own window (US-BIL-010 §4) ───────────────────────────────────────
MOVED_IN_ON = date(2026, 6, 12)
PERIOD_END = date(2026, 6, 30)
CYCLE_DAYS = 30
OCCUPIED_DAYS = 19  # 12 → 30 June inclusive

DEPOSIT_ASKED = Decimal("150.00")
CONN_AMOUNT = Decimal("25.00")


def _a_first_bill_world(brazos, dana, *, account_no="ACC-1350", consumption="412.000000"):
    cycle = a_cycle(brazos)
    plan = a_priced_plan(brazos)
    unit = a_billed_unit(
        dana, brazos, cycle, plan, asset_no="M-1350", label="Unit 4B", consumption=consumption
    )
    account = an_account(brazos, unit["id"], account_no)
    return cycle, plan, account


def _a_deposit_rule(brazos, plan, account, amount=DEPOSIT_ASKED, currency="USD"):
    return rating_models.PlanDepositRule.objects.create(
        tenant=brazos,
        rate_plan=plan,
        account_type_id=account.account_type_id,
        amount=amount,
        currency=currency,
    )


def _a_conn_charge(brazos, *, code="CONN", amount=CONN_AMOUNT, amount_rule="flat"):
    """The tenant's connection charge, at a stated amount.

    `get_or_create`-shaped because provisioning SEEDS a `CONN` code with its own
    figure (BR-BIL-007 — the amounts are seeds a tenant edits, never constants).
    This sets the fixture's amount on whichever row exists, which is exactly
    what a tenant does on S12, rather than colliding with the seed.
    """
    row, _created = rating_models.Charge.objects.get_or_create(
        tenant=brazos,
        code=code,
        defaults={"name": "Connection charge", "charge_type": "one_time"},
    )
    row.name = "Connection charge"
    row.amount_rule = amount_rule
    row.amount = amount
    row.deleted_at = None
    row.save(update_fields=["name", "amount_rule", "amount", "deleted_at"])
    return row


def _prepare(account):
    return first_bill.prepare_first_bill(
        account_id=account.id,
        moved_in_on=MOVED_IN_ON,
        period_end=PERIOD_END,
        cycle_days=CYCLE_DAYS,
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 / TC-2 — the window, and the proration the engine does with it
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_010_tc1__the_occupied_window_is_the_period_and_the_cycle_is_the_denominator(
    brazos, dana
):
    """B4.3 — occupied days ÷ CYCLE days, and the two are separate inputs.

    The assertion that would catch the real defect is the DENOMINATOR: this
    gathers 19 occupied days against a 30-day cycle, and a module that defaulted
    `cycle_days` to the occupied window would produce 19/19 = no proration at
    all — a full month's base charge for nineteen days, on a bill that looks
    perfectly normal.
    """
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana)
        data = _prepare(account)

        assert data.period_start == MOVED_IN_ON, "the window STARTS on the move-in day"
        assert data.period_end == PERIOD_END
        assert data.service_days == OCCUPIED_DAYS
        assert data.cycle_days == CYCLE_DAYS
        assert data.service_days < data.cycle_days, "a first bill is a PART of a cycle"


def test_us_bil_010_tc2__the_base_charge_prorates_and_the_bill_is_typed_first(brazos, dana):
    """The engine prorates the base by the window this module handed it.

    `18.50 × 19/30 = 11.7166… → **11.72**` half-up (B4.4). The figure is
    computed here from the frozen inputs rather than copied, so a rounding
    regression is named as one; what is asserted about US-BIL-010 is that the
    FACTOR reached the engine at all — an unprorated bill would read 18.50.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        _a_conn_charge(brazos)
        run = a_run(brazos, key="2026-06|first-bill")
        data = _prepare(account)

        draft = first_bill.calculate_first_bill(
            data,
            bill_run=run,
            moved_in_on=MOVED_IN_ON,
            account_type_id=account.account_type_id,
        )

        assert draft.bill_type == "first"
        base = [line for line in draft.lines.all() if line.kind == "base"]
        assert len(base) == 1
        full_base = Decimal("18.50")
        expected = (full_base * Decimal(OCCUPIED_DAYS) / Decimal(CYCLE_DAYS)).quantize(
            Decimal("0.01")
        )
        assert base[0].amount == expected == Decimal("11.72")
        assert base[0].amount < full_base, "an unprorated first bill is the whole defect"


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 — the two one-time lines, neither of them taxed
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_010_tc3__the_deposit_and_the_connection_charge_ride_untaxed(brazos, dana):
    """BR-BIL-012 — deposit **150.00** + CONN **25.00**, and B4.2 taxes neither.

    Neither is in `rating.pricing.contracts.TAX_BASE_KINDS`, which is what keeps
    them out of the tax base STRUCTURALLY (the base is computed by KIND, not by
    a flag anybody sets), and both are asserted present with their figures
    because a first bill that quietly dropped one is a first bill nobody
    notices is wrong.

    ⚠ **THIS TEST READ `line.kind == "fee"` FOR BOTH UNTIL 2026-08-16, AND THAT
    IS WHY DEF-181 SURVIVED.** The deposit was fee-class and this file said so
    approvingly — *"both are fee-class"* — while `issue._gl_account_for` refused
    every fee line for want of a charge code, so no first bill carrying a
    deposit could ISSUE. This file never issued one. The deposit now carries its
    own kind so its GL account can be the **deposit-liability** designation
    (US-LED-001: *"never revenue"*); the tax guarantee is unchanged and is
    asserted below against the KINDS rather than against the word "fee", so it
    keeps holding whatever a line is called.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        _a_conn_charge(brazos)
        run = a_run(brazos, key="2026-06|first-onetimers")
        data = _prepare(account)

        draft = first_bill.calculate_first_bill(
            data,
            bill_run=run,
            moved_in_on=MOVED_IN_ON,
            account_type_id=account.account_type_id,
        )
        from apps.rating.pricing.contracts import TAX_BASE_KINDS

        one_timers = {
            line.description: line for line in draft.lines.all() if line.kind in ("fee", "deposit")
        }
        assert one_timers[first_bill.DEPOSIT_DESCRIPTION].amount == DEPOSIT_ASKED
        assert one_timers["Connection charge"].amount == CONN_AMOUNT
        # The deposit has its OWN kind so its GL account can be the liability
        # designation rather than a charge code's (DEF-181).
        assert one_timers[first_bill.DEPOSIT_DESCRIPTION].kind == "deposit"
        assert one_timers["Connection charge"].kind == "fee"
        # B4.2, asserted STRUCTURALLY — neither kind can reach a percent base,
        # whatever anybody flags.
        assert all(line.kind not in TAX_BASE_KINDS for line in one_timers.values())
        assert all(line.taxable is False for line in one_timers.values()), "B4.2 — never taxed"
        assert draft.tax_total == Decimal("0.00") or all(
            line.kind != "tax" or line.amount >= 0 for line in draft.lines.all()
        )


def test_us_bil_010_tc3b__a_plan_that_asks_no_deposit_gets_no_line_at_all(brazos, dana):
    """No rule ⇒ NO LINE — never a $0.00 one.

    A zero-valued deposit line states that a deposit was assessed and waived,
    which is a different fact from never having been assessed, and it is the
    kind of line a customer telephones about.
    """
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana)
        data = _prepare(account)
        result = first_bill.deposit_line_for(data, account_type_id=account.account_type_id)
        assert result.lines == ()
        assert result.deposit_asked is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 — BR-PAY-012: money already paid SATISFIES the line
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_010_tc4__a_deposit_already_paid_is_not_billed_again(brazos, dana):
    """Three states, three different bills — this is the payments lane's third
    call site, wired (hard-won law 2).

    Nothing paid → **150.00** billed. **50.00** paid at the counter → the
    **100.00** remainder. Paid in full → **no line**, and the figure travels on
    the result so a screen can say why it is absent rather than leaving a clerk
    to wonder.
    """
    from apps.payments import models as payment_models

    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        data = _prepare(account)

        nothing_paid = first_bill.deposit_line_for(data, account_type_id=account.account_type_id)
        assert nothing_paid.lines[0].amount == DEPOSIT_ASKED
        assert nothing_paid.deposit_already_paid == Decimal("0")

        _pay(dana, account, Decimal("50.00"), purpose=payment_models.PURPOSE_DEPOSIT)
        part_paid = first_bill.deposit_line_for(data, account_type_id=account.account_type_id)
        assert part_paid.lines[0].amount == Decimal("100.00"), "the REMAINDER, not the whole"

        _pay(dana, account, Decimal("100.00"), purpose=payment_models.PURPOSE_DEPOSIT)
        settled = first_bill.deposit_line_for(data, account_type_id=account.account_type_id)
        assert settled.lines == (), "paid in full — the line is not emitted"
        assert settled.deposit_asked == DEPOSIT_ASKED
        assert settled.deposit_already_paid == DEPOSIT_ASKED


def test_us_bil_010_tc5__an_unreachable_payments_read_refuses_rather_than_billing(
    brazos, dana, monkeypatch
):
    """**None is not zero, and the difference is $150.00 of somebody's money.**

    Zero means *they have paid nothing* and bills the deposit. None means
    *nobody asked*. Reading None as zero would charge a deposit already paid,
    onto a bill that is immutable the moment it issues (hard rule 4) — so the
    first bill REFUSES, naming the read a human has to restore.
    """
    from apps.billing import payments_seam

    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        data = _prepare(account)

        monkeypatch.setattr(payments_seam, "_resolve", lambda *args, **kwargs: None)
        with pytest.raises(BillingRuleError, match="could not be read"):
            first_bill.deposit_line_for(data, account_type_id=account.account_type_id)


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 (negative) — the bill TYPE is derived, never supplied
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_010_tc6__a_first_bill_cannot_be_requested_for_a_sitting_tenant(brazos, dana):
    """US-BIL-010 TC-6 — `bill_type=first` follows from the move-in DATE.

    A caller's opinion does not make a first bill, and this is not pedantry:
    the type decides whether a deposit and a connection charge exist on
    somebody's bill, so a field a caller could set is a field that will
    eventually put $175.00 on the wrong month.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account)
        run = a_run(brazos, key="2026-06|not-a-first-bill")
        data = _prepare(account)

        moved_in_long_ago = date(2024, 3, 1)
        with pytest.raises(BillingRuleError, match="did not move in"):
            first_bill.calculate_first_bill(
                data,
                bill_run=run,
                moved_in_on=moved_in_long_ago,
                account_type_id=account.account_type_id,
            )
        assert models.Invoice.objects.filter(bill_run=run).count() == 0

    # And the predicate itself, asserted directly because it is pure and is what
    # the run will use to CLASSIFY accounts rather than to refuse them.
    assert first_bill.is_first_bill(
        moved_in_on=MOVED_IN_ON, period_start=date(2026, 6, 1), period_end=PERIOD_END
    )
    assert not first_bill.is_first_bill(
        moved_in_on=date(2026, 5, 31), period_start=date(2026, 6, 1), period_end=PERIOD_END
    )
    assert not first_bill.is_first_bill(
        moved_in_on=None, period_start=date(2026, 6, 1), period_end=PERIOD_END
    )


# ═══════════════════════════════════════════════════════════════════════════
# The charge code is a CODE (BR-BIL-007), and BR-BIL-062's honest refusal
# ═══════════════════════════════════════════════════════════════════════════
def test_us_bil_010_tc7__a_connection_charge_is_never_a_typed_amount(brazos, dana):
    """BR-BIL-007/020 — *"free-typed amounts never exist on any bill"*.

    An unknown code, a RETIRED code (IS-1 — a deactivated charge is not
    chargeable) and a percent-shaped rule are each refused by name. The last is
    the subtle one: `charges.amount` is populated on a percent rule too, and
    reading it would state a flat price for a rule that is not one.
    """
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana)
        data = _prepare(account)

        with pytest.raises(BillingRuleError, match="not a live charge code"):
            first_bill.connection_charge_line_for(data, code="NOPE")

        retired = _a_conn_charge(brazos, code="OLD-CONN")
        from django.utils import timezone

        retired.deleted_at = timezone.now()
        retired.save(update_fields=["deleted_at"])
        with pytest.raises(BillingRuleError, match="not a live charge code"):
            first_bill.connection_charge_line_for(data, code="OLD-CONN")

        _a_conn_charge(brazos, code="PCT-CONN", amount=Decimal("5.00"), amount_rule="percent")
        with pytest.raises(BillingRuleError, match="amount rule"):
            first_bill.connection_charge_line_for(data, code="PCT-CONN")


def test_us_bil_010_tc8__no_prior_read_refuses_by_name_and_never_invents_a_floor(brazos, dana):
    """BR-BIL-062 — the RULE is confirmed and its INPUT is missing.

    A first bill with no prior read prices at the plan's minimum for the
    category, prorated, with no usage line. The minimum cannot reach the engine
    (the rating lane records that hole in `pricing/stages/apply_charges.py`), so
    this refuses and SAYS SO.

    **It is deliberately not `NotImplementedError("OQ-…")`.** OQ-102 was CLOSED
    on 2026-08-11 and BR-BIL-062 is its answer; citing an open question here
    would tell the next reader that nobody has decided, when somebody has.
    """
    with tenant_ctx(brazos):
        _cycle, _plan, account = _a_first_bill_world(brazos, dana, consumption=None)
        data = _prepare(account)
        # Stage 1 emits a reading row per plan service and marks the unmeasured
        # ones; "no prior read" is NO MEASURED CONSUMPTION, never an empty list.
        assert data.readings != ()
        assert all(reading.consumption is None for reading in data.readings)

        with pytest.raises(BillingRuleError, match="BR-BIL-062") as refusal:
            first_bill.refuse_without_a_minimum(data)
        message = str(refusal.value)
        assert "minimum" in message
        # OQ-102 IS cited — as the PO ruling that CLOSED it, which is where the
        # rule comes from. What must not happen is a STUB on it: the refusal is
        # a BillingRuleError naming a missing input, never
        # `NotImplementedError("OQ-102")`, which G8 would (correctly) call a
        # stale stub on a question somebody has already answered.
        assert "closing OQ-102" in message
        assert not isinstance(refusal.value, NotImplementedError)
        assert "not an open question" in message

    codes = {entry["code"] for entry in first_bill.FIRST_BILL_UNAVAILABLE}
    assert "no_prior_read_minimum_has_no_input" in codes


def test_us_bil_010_tc9__isolation_a_deposit_rule_never_crosses_a_tenant(brazos, lonestar, dana):
    """Hard rule 1 · HR-1 — another tenant's deposit rule is ABSENT.

    The read is asserted from BOTH sides, because a deposit rule that answered
    across tenants would put one utility's $150.00 on another's first bill.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        rule = _a_deposit_rule(brazos, plan, account)
        _a_conn_charge(brazos, code="BRAZOS-ONLY")
        assert rating_selectors.deposit_rule_for(plan.id, account.account_type_id) == {
            "amount": rule.amount,
            "currency": "USD",
        }

    with tenant_ctx(lonestar):
        assert rating_selectors.deposit_rule_for(plan.id, account.account_type_id) is None
        # A code only Brazos Bend has — `CONN` is SEEDED into every tenant by
        # provisioning, so asserting its absence would assert the seed's shape
        # rather than tenant isolation.
        assert rating_selectors.charge_by_code("BRAZOS-ONLY") is None


def test_us_bil_010_tc10__a_deposit_in_another_currency_is_refused_not_summed(brazos, dana):
    """CLAUDE.md rule 2 — money is never summed across currencies.

    A deposit rule denominated in EUR on a USD bill is a configuration error,
    and `USD + EUR` is a number with no name. Refused by name rather than added.
    """
    with tenant_ctx(brazos):
        _cycle, plan, account = _a_first_bill_world(brazos, dana)
        _a_deposit_rule(brazos, plan, account, currency="EUR")
        data = _prepare(account)
        with pytest.raises(BillingRuleError, match="denominated in EUR"):
            first_bill.deposit_line_for(data, account_type_id=account.account_type_id)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-010@e9d5a48 (the four billing sources — B2 §2 + Addendum r10 ·
#         EP-BIL-03-bill-types.md · 07-billing/02-business-rules.md ·
#         07-billing/08-worked-examples.md WE-6)
# generated: 2026-08-15 by Eng-Lead (US-BIL-010 lane)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_bil_010_first_bill.py
# exceptions: (1) WE-6's own 20/31 window needs a five-service plan and a
#         31-day June; this file uses the shared single-service fixture over
#         **19/30**, computes the expected proration FROM those inputs rather
#         than copying a figure, and leaves WE-6's frozen 287.23 composite to
#         the golden harness. The RULE under test is the factor reaching the
#         engine, and that is asserted exactly.
#         (2) WE-16's mid-cycle capacity rider (10/31 → 12.90) needs a capacity
#         structure the shared fixture does not build — REPORTED, not faked.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

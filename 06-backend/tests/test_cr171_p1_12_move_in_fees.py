# ── Trace ──────────────────────────────────────────────
# Change:  CR-171-BRC10 P1.12 (Fees table) · P1.13 (Pay now / Add to bill) —
#          lane MVI-MONEY. Images 41, 43, 44, 26.
# Rules:   BR-BIL-007 (a fee is a charge code) · BR-CUS-037 (payments records
#          the money) · BR-CUS-025 / BR-PAY-012 (the deposit is a liability and
#          is taken only in full) · OQ-BIL-12788 CLOSED (a) 2026-10-05 (never
#          taxed at move-in) · decision log 2026-10-05 MOVE-IN REDESIGN P0 J4/J5
# Tests:   this file (SQLite and PostgreSQL); the PostgreSQL-only proof is
#          tests/test_cr171_p1_29_money_pg.py
# ───────────────────────────────────────────────────────
"""**The move-in's fee table and the money taken for it at the counter.**

The worked figures are J4's, verbatim from the decision log of 2026-10-05:
DEPOSIT **$150.00** + CONNECT **$25.00** + RUSH **$40.00** = **$215.00**;
*Pay now* **$100.00** by check → *"$115.00 goes on the first bill."*
The fixture's connection fee is spelled `CONN` (the tenant's code); RUSH is a
code the clerk adds; LATE is a penalty the plan names and must NOT be offered.

Every figure is asserted, so a drift in where a fee's price comes from — a
typed box, the plan's override, a taxed figure — goes red.
"""

import uuid
from decimal import Decimal

import pytest

from apps.customers import move_fees
from apps.customers import services as customers_services
from apps.customers.move_in_extras import MoveFeeLine
from apps.payments import models as payment_models
from apps.rating import models as rating_models
from core import errors
from tests.test_cr094_wh_deposit import MOVE_IN_DAY, _outgoing, _payload, _unit
from tests.test_us_met_helpers import *  # noqa: F401,F403
from tests.test_us_met_helpers import brazos, dana, marcus, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db

DEPOSIT = Decimal("150.0000")
CONNECT = Decimal("25.0000")
RUSH = Decimal("40.0000")
TOTAL = Decimal("215.0000")


def _code(tenant, code, amount=None, *, charge_type="one_time", amount_rule="flat", name=None):
    row, _ = rating_models.Charge.objects.get_or_create(
        tenant=tenant, code=code, defaults={"name": name or code, "charge_type": charge_type}
    )
    row.name = name or code
    row.charge_type = charge_type
    row.amount_rule = amount_rule
    row.deleted_at = None
    row.save(update_fields=["name", "charge_type", "amount_rule", "deleted_at"])
    if amount is not None:
        row.amount = amount
        row.save()
    return row


def _world(actor, tenant):
    """A vacant unit on a plan that asks $150.00 of a Residential account and
    names CONN (one-time, $25.00) and LATE (a penalty). RUSH ($40.00) and
    INSPECT (per case) are codes the plan does not name."""
    unit, plan = _unit(actor, tenant)
    conn = _code(tenant, "CONN", CONNECT, name="Connection charge")
    late = _code(tenant, "LATE", Decimal("5.0000"), charge_type="penalty", name="Late fee")
    _code(tenant, "RUSH", RUSH, name="Same-day connection")
    _code(tenant, "INSPECT", None, amount_rule="per_case", name="Inspection")
    for charge in (conn, late):
        rating_models.PlanChargeRule.objects.get_or_create(
            tenant=tenant, rate_plan=plan, charge=charge, defaults={"role": "charge"}
        )
    outgoing = _outgoing(actor, tenant, unit)
    customers_services.move_out(actor, outgoing["id"], {"moved_out_on": "2026-08-14"})
    return unit, plan, outgoing


def _fees(*extra):
    rows = [
        {"kind": "deposit", "source": "plan", "amount": "150.00"},
        {"kind": "fee", "source": "plan", "code": "CONN", "amount": "25.00"},
        {"kind": "fee", "source": "charge_code", "code": "RUSH", "amount": "40.00"},
    ]
    rows.extend(extra)
    return rows


def _deferred():
    return {"decision": "required", "take_now": False}


def _move_in(actor, outgoing, **overrides):
    payload = _payload(deposit=_deferred(), fees=_fees(), payment={"mode": "add_to_bill"})
    payload.update(overrides)
    return customers_services.move_in(actor, outgoing["id"], payload)


def _lines(account_id):
    return list(
        MoveFeeLine.objects.filter(move_record__account_id=account_id).order_by("seq")
    )


# ══════════════════════════════════════════════════════════════════════════
# P1.12 — what the table SHOWS before the account exists
# ══════════════════════════════════════════════════════════════════════════
def test_p1_12__the_table_shows_the_deposit_then_the_plans_one_time_fees(brazos, dana):
    with tenant_ctx(brazos):
        unit, _plan, _out = _world(dana, brazos)
        shown = move_fees.default_rows(unit["id"], "residential")

    codes = [(row["kind"], row["code"], row["amount"]) for row in shown["rows"]]
    assert codes == [("deposit", "DEPOSIT", "150.0000"), ("fee", "CONN", "25.0000")]
    assert all(row["locked"] for row in shown["rows"])
    # LATE is a penalty the plan names: the charge code decides, never the plan.
    assert "LATE" not in [row["code"] for row in shown["rows"]]
    assert shown["total"] == "175.0000"
    # OQ-BIL-12788 (a) — stated on every row, and no tax figure anywhere.
    assert all(row["taxed_at_move_in"] is False for row in shown["rows"])


def test_p1_12__an_added_code_is_priced_from_its_code_or_refused_by_name(brazos, dana):
    with tenant_ctx(brazos):
        unit, _plan, _out = _world(dana, brazos)
        rush = move_fees.quote("RUSH", unit["id"], "residential")
        late = move_fees.quote("LATE", unit["id"], "residential")
        nothing = move_fees.quote("NOPE", unit["id"], "residential")
        inspect = move_fees.quote("INSPECT", unit["id"], "residential")

    assert (rush["amount"], rush["refusal"], rush["source"]) == ("40.0000", None, "charge_code")
    assert late["refusal"] == "not_a_one_time_code" and late["amount"] is None
    assert nothing["refusal"] == "unknown_code"
    assert inspect["priced_by"] == "per_case" and inspect["amount"] is None


# ══════════════════════════════════════════════════════════════════════════
# P1.12 — the lines written at Complete
# ══════════════════════════════════════════════════════════════════════════
def test_p1_12__complete_writes_j4s_three_lines_and_215(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing)
        lines = _lines(result["id"])

    assert [(line.seq, line.kind, line.source, line.code, line.amount) for line in lines] == [
        (1, "deposit", "plan", "DEPOSIT", DEPOSIT),
        (2, "fee", "plan", "CONN", CONNECT),
        (3, "fee", "charge_code", "RUSH", RUSH),
    ]
    assert lines[1].charge_code_id is not None, "BR-BIL-007 — the line names its code"
    assert Decimal(result["fees"]["total"]) == TOTAL
    assert all(line["taxed_at_move_in"] is False for line in result["fees"]["lines"])


def test_p1_12__a_figure_that_is_not_the_codes_refuses_the_whole_move_in(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        before = customers_services.models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(
                dana,
                outgoing,
                fees=[{"kind": "fee", "source": "charge_code", "code": "RUSH", "amount": "35.00"}],
            )
        assert customers_services.models.Account.objects.count() == before
        assert MoveFeeLine.objects.count() == 0

    assert raised.value.message_key == move_fees.AMOUNT_NOT_CODE
    assert raised.value.field_errors[0]["params"]["amount"] == "40.0000"


def test_p1_12__a_per_case_code_takes_the_clerks_amount_and_refuses_none(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, fees=[{"kind": "fee", "code": "INSPECT"}])
        assert raised.value.message_key == move_fees.AMOUNT_REQUIRED
        result = _move_in(dana, outgoing, fees=[{"kind": "fee", "code": "INSPECT", "amount": "60"}])
        lines = _lines(result["id"])

    assert [(line.code, line.amount) for line in lines] == [
        ("DEPOSIT", DEPOSIT),
        ("INSPECT", Decimal("60.0000")),
    ]


@pytest.mark.parametrize(
    "row, key",
    [
        ({"kind": "fee", "source": "charge_code", "code": "LATE"}, move_fees.CODE_REFUSED),
        ({"kind": "fee", "source": "plan", "code": "INSPECT", "amount": "60"}, move_fees.NOT_FROM_PLAN),
        ({"kind": "fee", "code": "CONN"}, move_fees.DUPLICATE_CODE),
    ],
)
def test_p1_12__a_fee_the_move_in_cannot_charge_is_refused_by_name(brazos, dana, row, key):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, fees=_fees(row))
    assert raised.value.message_key == key


def test_p1_12__a_deposit_row_where_none_is_owed_is_refused(brazos, dana):
    """A WAIVED deposit is not owed, so a deposit row beside it would charge
    money the clerk just forgave."""
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, deposit={"decision": "waived", "waive_reason": "Hardship"})
    assert raised.value.message_key == move_fees.DEPOSIT_NOT_OWED


def test_p1_12__a_waived_deposit_writes_no_deposit_line(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(
            dana,
            outgoing,
            deposit={"decision": "waived", "waive_reason": "Hardship"},
            fees=_fees()[1:],
        )
        lines = _lines(result["id"])
    assert [line.code for line in lines] == ["CONN", "RUSH"]
    assert Decimal(result["fees"]["total"]) == Decimal("65.0000")


def test_p1_12__the_old_wizard_writes_no_lines_and_answers_no_fees(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = customers_services.move_in(dana, outgoing["id"], _payload(deposit=_deferred()))
        assert _lines(result["id"]) == []
    assert "fees" not in result and "payment" not in result


# ══════════════════════════════════════════════════════════════════════════
# P1.13 — Pay now / Add to bill
# ══════════════════════════════════════════════════════════════════════════
def _paid(account_id):
    return {
        row.purpose: row.amount
        for row in payment_models.Payment.objects.filter(account_id=account_id)
    }


def _pay_now(amount, **extra):
    block = {
        "mode": "pay_now",
        "method_code": "check",
        "amount": amount,
        "confirmation": "1043",
        "received_on": MOVE_IN_DAY,
        "idempotency_reference": str(uuid.uuid4()),
    }
    block.update(extra)
    return block


def test_p1_13__add_to_bill_records_no_money_and_puts_215_on_the_first_bill(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing)
        assert _paid(result["id"]) == {}
    assert result["payment"]["mode"] == "add_to_bill"
    assert Decimal(result["payment"]["on_first_bill"]) == TOTAL


def test_p1_13__j4_100_by_check_is_all_prepay_and_115_goes_on_the_bill(brazos, dana):
    """J4 verbatim: the deposit is never taken partly, so $100.00 against a
    $150.00 deposit is ALL prepay and the deposit stays on the first bill."""
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("100.00"))
        paid = _paid(result["id"])
        account = customers_services.models.Account.objects.get(pk=result["id"])

    assert paid == {"prepay": Decimal("100.000000")}
    assert account.deposit_on_file in (None, Decimal("0"))
    assert Decimal(result["payment"]["amount_paid"]) == Decimal("100.0000")
    assert Decimal(result["payment"]["on_first_bill"]) == Decimal("115.0000")
    assert result["payment"]["receipt_no"] == result["payment"]["payments"][0]["payment_no"]
    assert result["deposit"]["notes"] == [move_fees.customers_deposit.DEFERRED_TO_FIRST_BILL]


def test_p1_13__215_cleared_takes_the_150_deposit_and_65_prepay(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("215.00"))
        paid = _paid(result["id"])
        account = customers_services.models.Account.objects.get(pk=result["id"])

    assert paid == {"deposit": Decimal("150.000000"), "prepay": Decimal("65.000000")}
    # BR-CUS-670's register moved — written by payments, read back here.
    assert account.deposit_on_file == DEPOSIT
    assert Decimal(result["payment"]["on_first_bill"]) == Decimal("0.0000")
    assert result["deposit"]["held"] is True
    assert move_fees.customers_deposit.DEFERRED_TO_FIRST_BILL not in result["deposit"]["notes"]


def test_p1_13__more_than_the_fees_is_refused_and_nothing_is_written(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        before = customers_services.models.Account.objects.count()
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, payment=_pay_now("215.01"))
        assert customers_services.models.Account.objects.count() == before
        assert payment_models.Payment.objects.filter(purpose="prepay").count() == 0
    assert raised.value.message_key == move_fees.MORE_THAN_FEES


def test_p1_13__pay_now_beside_a_deposit_taken_today_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        taken = {
            "decision": "required",
            "take_now": True,
            "method_code": "cash",
            "posted_at": MOVE_IN_DAY,
        }
        with pytest.raises(errors.ValidationError) as raised:
            _move_in(dana, outgoing, deposit=taken, payment=_pay_now("50.00"))
    assert raised.value.message_key == move_fees.DEPOSIT_TAKEN_TWICE


@pytest.mark.parametrize(
    "block, field",
    [
        ({"mode": "later"}, "payment.mode"),
        ({"mode": "pay_now", "method_code": "cash", "received_on": MOVE_IN_DAY}, "payment.amount"),
        ({"mode": "pay_now", "amount": "10", "received_on": MOVE_IN_DAY}, "payment.method_code"),
        ({"mode": "pay_now", "amount": "10", "method_code": "cash"}, "payment.received_on"),
        ({"mode": "add_to_bill", "tip": "1"}, "payment.tip"),
    ],
)
def test_p1_13__every_refusal_names_its_own_field(block, field):
    with pytest.raises(errors.ValidationError) as raised:
        move_fees.clean_payment(block)
    assert raised.value.field_errors[0]["field"] == field


def test_p1_13__money_is_four_places_never_a_float():
    instruction = move_fees.clean_payment(_pay_now("100.123449"))
    assert instruction.amount == Decimal("100.1234")


# ══════════════════════════════════════════════════════════════════════════
# ⚖️ THE HUMAN SIGN-OFF OF 2026-10-06 — statement 2 of six, asserted so drift
# goes red. PO verbatim: "Money-file review: approve these six? - all good -
# go ahead" (decision log "SIX MOVE-IN MONEY FILES SIGNED"). Shown, exactly:
#
#   "Rosa moves in: $150.00 deposit + $25.00 connection + $40.00 same-day =
#    $215.00, no tax. She pays $100.00 by cheque, so $100.00 is held toward her
#    first bill and $115.00 goes on it. Had she paid all $215.00, $150.00 is
#    held as her deposit and $65.00 covers the fees. Also, if a plan charges
#    Electric $12.00 and Water $8.00 and Rosa takes water only, her base charge
#    is $8.00 a month, not $20.00."
#
# Three tests, one per figure (the last lives in test_cr171_wiz_bill_base_total.py,
# beside its own fixture). NOT covered by the signature: "a typed fee figure
# that is not the code's saves nothing" — the ledger row offered it, the PO was
# not shown it, and `test_p1_12__a_figure_that_is_not_the_codes_refuses_…`
# holds it as machine evidence only.
# ══════════════════════════════════════════════════════════════════════════
def test_signed_2026_10_06__rosa_215_untaxed_100_by_cheque_held_and_115_on_the_bill(
    brazos, dana
):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("100.00"))
        paid = _paid(result["id"])
    # $150.00 + $25.00 + $40.00 = $215.00, no tax on any line.
    assert sorted(Decimal(line["amount"]) for line in result["fees"]["lines"]) == [
        Decimal("25.0000"),
        Decimal("40.0000"),
        Decimal("150.0000"),
    ]
    assert Decimal(result["fees"]["total"]) == Decimal("215.0000")
    assert all(line["taxed_at_move_in"] is False for line in result["fees"]["lines"])
    # $100.00 by cheque is held toward the first bill; $115.00 goes on it.
    assert paid == {"prepay": Decimal("100.000000")}
    assert Decimal(result["payment"]["on_first_bill"]) == Decimal("115.0000")


def test_signed_2026_10_06__rosa_pays_215_so_150_is_her_deposit_and_65_the_fees(brazos, dana):
    with tenant_ctx(brazos):
        _unit_, _plan, outgoing = _world(dana, brazos)
        result = _move_in(dana, outgoing, payment=_pay_now("215.00"))
        paid = _paid(result["id"])
    assert paid == {"deposit": Decimal("150.000000"), "prepay": Decimal("65.000000")}
    assert Decimal(result["payment"]["on_first_bill"]) == Decimal("0.0000")

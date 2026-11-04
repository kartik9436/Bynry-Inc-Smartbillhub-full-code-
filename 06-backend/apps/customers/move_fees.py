# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 P1.12 (the Fees table, images 41/43) and P1.13 (Pay
#           now or Add to bill at Complete, images 41/43/44/26) — lane
#           MVI-MONEY. PO, mock-up v12: *"this should be fees and table array
#           and allow user to add all fees for this move in - may will come from
#           plan and some can be come from others charge codes"*; v13: *"below
#           fees you need payment option - pay now or add in bill"*.
# Rules:    BR-BIL-007 (a fee is a tenant charge code, never a literal) ·
#           BR-BIL-012 (the first bill carries the move's one-time lines) ·
#           BR-CUS-037 (customers writes no financial table — payments records
#           the money) · BR-CUS-025 / BR-PAY-012 (a deposit-purpose payment is a
#           liability and satisfies the first-bill deposit line) · BR-PAY-010
#           (a prepay meets bills in the ratified order) · BR-SHL-019 (ONE
#           transactional commit) · OQ-BIL-12788 CLOSED (a) 2026-10-05 (a
#           move-in fee is never taxed at move-in) · decision log 2026-10-05
#           *"MOVE-IN REDESIGN P0"* J4/J5 · CLAUDE.md rules 1, 2, 4, 5, 7
# Tests:    06-backend/tests/test_cr171_p1_12_move_in_fees.py ·
#           06-backend/tests/test_cr171_p1_13_move_in_payment.py ·
#           06-backend/tests/test_cr171_p1_29_money_pg.py (PostgreSQL)
# Impacts:  apps/customers/services._move_in (pops `fees` and `payment`, calls
#           `record` and `take_payment` inside its transaction) ·
#           apps/rating/move_in_fees (the prices) · apps/payments/services.
#           record_payment (the money) · apps/billing/first_bill (reads the lines)
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — a move-in's FEES and the money taken
for them at the counter.

AI-authored 2026-10-05 (lane MVI-MONEY, `CR-171-BRC10` P1.12 + P1.13) under the
PO ruling of 2026-08-09; row in `12-governance/09-human-review-ledger.md`
(*"CR-171 MOVE-IN MONEY"*).

════════════════════════════════════════════════════════════════════════════
1 · THE FEES TABLE — WHAT IT HOLDS AND WHERE EACH FIGURE COMES FROM
════════════════════════════════════════════════════════════════════════════
Image 41 draws one table: the **deposit** first (locked), then the **plan's
one-time fees** (locked, *From plan*), then any fee the clerk adds by typing a
**charge code** (*From charge code*), and a **Total**.

* **The deposit** is `deposit.py`'s and nothing here prices it. The figure is
  the plan's for the category (`deposit.standard_for_unit` before the account
  exists, `deposit.take` at Complete). The fee table only SHOWS it; a deposit
  row sent with a different figure is refused by the deposit's own sentence.
* **A fee** is priced by RATING from its code (`rating.move_in_fees`,
  BR-BIL-007). A figure the screen sends is only ever COMPARED with the code's
  price and refused when different — never used — exactly the posture
  `deposit.take` takes for a plan edited between the screen and the commit: the
  figure the customer was quoted is the figure they pay, or nothing is written.
  A `per_case` code is the one exception and the clerk types its amount.

⚠ **NO TAX, AND IT IS A RULING, NOT AN OMISSION.** `OQ-BIL-12788` CLOSED (a),
PO 2026-10-05: *"this si correct - a (recommended) $25.00 (never taxed at
move-in)"*. A move-in fee costs the same whichever payment button the clerk
presses: a $25.00 connection fee is **$25.00**, not $25.50. So no line here
carries a tax figure and nothing reads a code's `taxable_default`. The ❄️ frozen
rule that fees on a regular bill are untaxed (B4.2) decides both paths, because
money taken today is an ADVANCE on the first bill (J4), not a separate fee bill.

════════════════════════════════════════════════════════════════════════════
2 · PAY NOW OR ADD TO BILL — J4, AND THE ONE SPLIT IT MAKES
════════════════════════════════════════════════════════════════════════════
*Add to bill* records no money. Every fee row lands on the first bill as a
one-time line (`billing.first_bill`, P1.14), the deposit included.

*Pay now* records the money through `payments.record_payment` — customers
writes no financial table (BR-CUS-037) — in at most TWO payments:

    deposit-purpose   the deposit, but ONLY when the amount covers it in full
    prepay            everything else

**The deposit is never taken partly.** A deposit-purpose payment is a
LIABILITY (BR-CUS-025, account 2300) and satisfies the first bill's deposit
line (BR-PAY-012); half a deposit held as a liability while the other half is
billed would split one fact across two books. So a part payment smaller than
the deposit is ALL prepay, the deposit stays *required, on the first bill*, and
`BR-PAY-010` allocates the prepay at issue.

**Worked (J4, decision log 2026-10-05):** DEPOSIT $150.00 + CONNECT $25.00 +
RUSH $40.00 = **$215.00**. *Pay now* $100.00 by check → one prepay payment of
$100.00; the first bill carries $215.00 of one-time lines and the $100.00
credit, and the clerk reads *"$115.00 goes on the first bill."* *Pay now*
$215.00 → a $150.00 deposit payment and a $65.00 prepay; the first bill carries
no deposit line (paid) and $65.00 of fees, met by the $65.00 credit.

⚠ **NOTHING HERE CATCHES A DATABASE ERROR (hard-won law 14).** A payment that
cannot be recorded refuses the whole move-in, account included, so the clerk
fixes one field with everything still on screen (BR-SHL-019).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from core import audit as core_audit
from core import errors

from apps.customers import deposit as customers_deposit
from apps.customers import seams
from apps.customers.move_in_extras import (
    FEE_KIND_DEPOSIT,
    FEE_KIND_FEE,
    FEE_KINDS,
    FEE_SOURCE_CHARGE_CODE,
    FEE_SOURCE_PLAN,
    FEE_SOURCES,
    MoveFeeLine,
)

MONEY_PLACES = Decimal("0.0001")
ZERO = Decimal("0")

#: What a deposit row is called when the plan's deposit names no code (a
#: typed `plan_deposit_rules` row). The first bill prints its own words.
DEPOSIT_CODE = "DEPOSIT"
DEPOSIT_DESCRIPTION = "Security deposit"

FEE_FIELDS: frozenset[str] = frozenset({"kind", "source", "code", "amount", "note"})
PAYMENT_FIELDS: frozenset[str] = frozenset(
    {
        "mode",
        "method_code",
        "amount",
        "confirmation",
        "received_on",
        # ⛔ NO `cleared_on` — `DEF-CUS-10324` (CR-186-BRC10): the money is
        # recorded `posted`; only bank reconciliation clears it. Sent, it is
        # refused by name as an unknown field rather than accepted and ignored.
        "idempotency_reference",
    }
)

MODE_PAY_NOW = "pay_now"
MODE_ADD_TO_BILL = "add_to_bill"
MODES: tuple[str, ...] = (MODE_PAY_NOW, MODE_ADD_TO_BILL)

PURPOSE_DEPOSIT = "deposit"
PURPOSE_PREPAY = "prepay"

# ── refusals. Each RESOLVES in all eleven catalogues (G32), ≤ six words (G33).
CODE_REFUSED = "customers.moveFees.codeRefused"
AMOUNT_NOT_CODE = "customers.moveFees.amountNotCode"
AMOUNT_REQUIRED = "customers.moveFees.amountRequired"
DUPLICATE_CODE = "customers.moveFees.duplicateCode"
NOT_FROM_PLAN = "customers.moveFees.notFromPlan"
MODE_REQUIRED = "customers.movePayment.modeRequired"
PAYMENT_AMOUNT_REQUIRED = "customers.movePayment.amountRequired"
MORE_THAN_FEES = "customers.movePayment.moreThanFees"
DEPOSIT_TAKEN_TWICE = "customers.movePayment.depositTakenTwice"
#: Reused, not twinned: these sentences already exist and say exactly this.
AMOUNT_INVALID = "customers.account.amount_invalid"
UNKNOWN_FIELD = "customers.account.unknown_field"
NOT_AN_OBJECT = "customers.payload_not_object"
DEPOSIT_NOT_OWED = "customers.deposit.take_without_deposit"
METHOD_REQUIRED = "customers.deposit.method_required"
RECEIVED_REQUIRED = "customers.deposit.posted_required"

#: Payments has published no `record_payment` — the G20 rule: say so, never
#: answer "recorded".
PAYMENTS_UNWIRED = "move_in_payment_path_unwired"


# ═══════════════════════════════════════════════════════════════════════════
# The two blocks, validated before anything is written
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class FeeRow:
    kind: str
    source: str
    code: str | None
    amount: Decimal | None
    note: str | None
    index: int


@dataclass(frozen=True)
class PaymentInstruction:
    mode: str
    method_code: str | None = None
    amount: Decimal | None = None
    confirmation: str | None = None
    received_on: date | None = None
    idempotency_reference: str | None = None

    @property
    def pays_now(self) -> bool:
        return self.mode == MODE_PAY_NOW


def _fe(field: str, error_code: str, key: str, **params: Any) -> dict[str, Any]:
    return {"field": field, "code": error_code, "message_key": key, "params": params}


def _raise(fe: list[dict[str, Any]]) -> None:
    if fe:
        raise errors.ValidationError(
            fe[0]["code"], message_key=fe[0]["message_key"], params=fe[0]["params"], field_errors=fe
        )


def _money(value: Any, field: str, fe: list[dict[str, Any]]) -> Decimal | None:
    """Four places, never a float (rule 2); negative refused — a credit is
    billing's, never a move-in fee (`ck_move_fee_lines_amount`)."""
    if value is None or value == "":
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, ArithmeticError):
        fe.append(_fe(field, errors.VAL_FORMAT, AMOUNT_INVALID))
        return None
    if amount.is_nan() or amount.is_infinite():
        fe.append(_fe(field, errors.VAL_FORMAT, AMOUNT_INVALID))
        return None
    if amount < 0:
        fe.append(_fe(field, errors.VAL_RANGE, AMOUNT_INVALID))
        return None
    return amount.quantize(MONEY_PLACES)


def _day(value: Any, field: str, fe: list[dict[str, Any]]) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        fe.append(_fe(field, errors.VAL_FORMAT, "customers.account.date_invalid"))
        return None


def _text(value: Any, limit: int = 120) -> str | None:
    text = str(value or "").strip()
    return text[:limit] if text else None


def clean_fees(raw: Any) -> list[FeeRow] | None:
    """The wizard's `fees` block. `None` when it sent none — the old wizard,
    whose move-ins carry no fee lines and whose first bills are unchanged."""
    if raw is None:
        return None
    if not isinstance(raw, list):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=NOT_AN_OBJECT)
    fe: list[dict[str, Any]] = []
    rows: list[FeeRow] = []
    codes: set[str] = set()
    deposits = 0
    for index, item in enumerate(raw):
        where = f"fees[{index}]"
        if not isinstance(item, dict):
            fe.append(_fe(where, errors.VAL_FORMAT, NOT_AN_OBJECT))
            continue
        for key in sorted(set(item) - FEE_FIELDS):
            fe.append(_fe(f"{where}.{key}", errors.VAL_FORMAT, UNKNOWN_FIELD))
        kind = _text(item.get("kind"), 20) or FEE_KIND_FEE
        if kind not in FEE_KINDS:
            fe.append(_fe(f"{where}.kind", errors.VAL_FORMAT, CODE_REFUSED))
            continue
        source = _text(item.get("source"), 20) or (
            FEE_SOURCE_PLAN if kind == FEE_KIND_DEPOSIT else FEE_SOURCE_CHARGE_CODE
        )
        if source not in FEE_SOURCES:
            fe.append(_fe(f"{where}.source", errors.VAL_FORMAT, CODE_REFUSED))
            continue
        code = _text(item.get("code"), 60)
        amount = _money(item.get("amount"), f"{where}.amount", fe)
        if kind == FEE_KIND_DEPOSIT:
            deposits += 1
            if deposits > 1:
                fe.append(_fe(f"{where}.kind", errors.VAL_RANGE, DUPLICATE_CODE, code=DEPOSIT_CODE))
                continue
        else:
            if code is None:
                fe.append(_fe(f"{where}.code", errors.VAL_REQUIRED, CODE_REFUSED, code=""))
                continue
            if code.upper() in codes:
                fe.append(_fe(f"{where}.code", errors.VAL_RANGE, DUPLICATE_CODE, code=code))
                continue
            codes.add(code.upper())
        rows.append(
            FeeRow(
                kind=kind,
                source=source,
                code=code,
                amount=amount,
                note=_text(item.get("note"), 200),
                index=index,
            )
        )
    _raise(fe)
    return rows


def clean_payment(raw: Any) -> PaymentInstruction | None:
    """The wizard's `payment` block. `None` when it sent none (the old wizard)."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise errors.ValidationError(errors.VAL_FORMAT, message_key=NOT_AN_OBJECT)
    fe: list[dict[str, Any]] = []
    for key in sorted(set(raw) - PAYMENT_FIELDS):
        fe.append(_fe(f"payment.{key}", errors.VAL_FORMAT, UNKNOWN_FIELD))
    mode = _text(raw.get("mode"), 20)
    if mode not in MODES:
        fe.append(_fe("payment.mode", errors.VAL_REQUIRED, MODE_REQUIRED))
        _raise(fe)
    if mode == MODE_ADD_TO_BILL:
        _raise(fe)
        return PaymentInstruction(mode=mode)
    amount = _money(raw.get("amount"), "payment.amount", fe)
    if amount is None or amount <= 0:
        if not any(e["field"] == "payment.amount" for e in fe):
            fe.append(_fe("payment.amount", errors.VAL_REQUIRED, PAYMENT_AMOUNT_REQUIRED))
    method = _text(raw.get("method_code"), 40)
    if method is None:
        fe.append(_fe("payment.method_code", errors.VAL_REQUIRED, METHOD_REQUIRED))
    received = _day(raw.get("received_on"), "payment.received_on", fe)
    if received is None and not any(e["field"] == "payment.received_on" for e in fe):
        fe.append(_fe("payment.received_on", errors.VAL_REQUIRED, RECEIVED_REQUIRED))
    _raise(fe)
    return PaymentInstruction(
        mode=mode,
        method_code=method,
        amount=amount,
        # The check number, the card's last four or the reference — one field,
        # payments' own `confirmation` (BR-PAY-022's *reference*).
        confirmation=_text(raw.get("confirmation"), 120),
        received_on=received,
        idempotency_reference=_text(raw.get("idempotency_reference"), 100),
    )


def refuse_deposit_taken_twice(
    instruction: PaymentInstruction | None, deposit_instruction: Any
) -> None:
    """*Pay now* takes the deposit when it covers it; the old step's *taken
    today* takes it too. Both at once would record the deposit twice, so the
    pair is refused before the transaction opens."""
    if instruction is None or not instruction.pays_now:
        return
    if getattr(deposit_instruction, "take_now", False):
        _raise([_fe("payment.mode", errors.VAL_RANGE, DEPOSIT_TAKEN_TWICE)])


# ═══════════════════════════════════════════════════════════════════════════
# What the table SHOWS before the account exists — `GET /move-ins/fees`
# ═══════════════════════════════════════════════════════════════════════════
def _unit_plan_id(unit_id: Any) -> Any:
    unit = seams.unit_row(unit_id)
    return getattr(unit, "rate_plan_id", None)


def unit_services(unit_id: Any) -> list[str]:
    """The services the unit's live service points carry, in their order."""
    return [str(point["service"]) for point in seams.service_points_for(unit_id) if point.get("service")]


def sizes_by_service(unit_id: Any, services: Iterable[str]) -> dict[str, str | None]:
    """Each service's RECORDED connection size (metering's `connection_size_for`)
    — None where nobody recorded one, which prices nothing (never a guess)."""
    size_of = seams.resolve("metering", "connection_size_for", kind="selectors")
    return {code: (size_of(unit_id, code) if size_of is not None else None) for code in services}


def _rating(name: str) -> Any:
    return seams.resolve("rating", name, kind="move_in_fees")


def default_rows(
    unit_id: Any,
    account_type: Any,
    *,
    services: Iterable[str] | None = None,
    size_class: Any = None,
) -> dict[str, Any]:
    """Image 41's locked rows for this unit and category, before anything exists.

    `{rows, total, currency, deposit}` — `deposit` is `deposit.standard_for_unit`'s
    own answer forwarded whole (so a size pick reads exactly as the Deposit step
    read it); `total` is the sum of every row that HAS a figure, at four places.
    A row with no figure (a `per_case` code, a size not recorded) is in `rows`
    with `amount: null` and `refusal`, and is left out of the total, which the
    screen says rather than hides.
    """
    standard = customers_deposit.standard_for_unit(unit_id, account_type, size_class)
    code = str(account_type or "").strip()
    started = list(services) if services is not None else unit_services(unit_id)
    rows: list[dict[str, Any]] = []
    if standard.get("asks"):
        rows.append(
            {
                "kind": FEE_KIND_DEPOSIT,
                "source": FEE_SOURCE_PLAN,
                "code": DEPOSIT_CODE,
                "name": DEPOSIT_DESCRIPTION,
                "amount": standard.get("amount"),
                "locked": True,
                "refusal": None if standard.get("amount") else "size_required",
                "taxed_at_move_in": False,
            }
        )
    plan_fees = _rating("plan_move_in_charges")
    plan_id = _unit_plan_id(unit_id)
    if plan_fees is not None and plan_id is not None:
        for row in plan_fees(
            plan_id,
            customer_class=code or None,
            size_by_service=sizes_by_service(unit_id, started),
            services=started,
        ):
            rows.append({**row, "kind": FEE_KIND_FEE, "source": FEE_SOURCE_PLAN, "locked": True})
    total = sum((Decimal(str(row["amount"])) for row in rows if row.get("amount") is not None), ZERO)
    return {
        "unit_id": str(unit_id),
        "account_type": code,
        "services": started,
        "rows": rows,
        "total": str(total.quantize(MONEY_PLACES)),
        "currency": standard.get("currency") or seams_currency(),
        "deposit": standard,
    }


def seams_currency() -> str:
    fn = getattr(seams, "tenant_currency", None)
    try:
        return (fn() if callable(fn) else None) or "USD"
    except Exception:  # pragma: no cover - a currency read never fails a quote
        return "USD"


def quote(code: Any, unit_id: Any, account_type: Any, *, services: Iterable[str] | None = None) -> dict[str, Any]:
    """`GET /move-ins/fees/quote?code=` — the *+ Add fee* row, priced."""
    price = _rating("price_code")
    started = list(services) if services is not None else unit_services(unit_id)
    if price is None:
        return {"code": str(code or ""), "amount": None, "refusal": "rating_not_wired"}
    row = price(
        str(code or ""),
        customer_class=str(account_type or "").strip() or None,
        size_by_service=sizes_by_service(unit_id, started),
    )
    return {**row, "kind": FEE_KIND_FEE, "source": FEE_SOURCE_CHARGE_CODE, "locked": False}


# ═══════════════════════════════════════════════════════════════════════════
# At Complete — the lines written on the move record (P1.12)
# ═══════════════════════════════════════════════════════════════════════════
def _price_check(row: FeeRow, priced: dict[str, Any]) -> Decimal:
    """The figure a line is written at — the CODE's, or the clerk's for a
    `per_case` code. A sent figure that is not the code's is refused by name."""
    where = f"fees[{row.index}]"
    if priced.get("refusal"):
        _raise(
            [_fe(f"{where}.code", errors.VAL_RANGE, CODE_REFUSED, code=row.code, reason=priced["refusal"])]
        )
    if priced.get("priced_by") == "per_case":
        if row.amount is None or row.amount <= 0:
            _raise([_fe(f"{where}.amount", errors.VAL_REQUIRED, AMOUNT_REQUIRED, code=row.code)])
        return row.amount  # type: ignore[return-value]
    figure = Decimal(str(priced["amount"])).quantize(MONEY_PLACES)
    if row.amount is not None and row.amount != figure:
        _raise(
            [_fe(f"{where}.amount", errors.VAL_RANGE, AMOUNT_NOT_CODE, code=row.code, amount=str(figure))]
        )
    return figure


def record(
    actor: Any,
    *,
    move_record_id: Any,
    account: Any,
    fees: list[FeeRow] | None,
    deposit_result: dict[str, Any] | None,
    services: Iterable[str] | None,
    is_sample: bool = False,
) -> dict[str, Any] | None:
    """Write the move's fee lines. INSIDE the move-in's transaction: a refused
    line rolls back the account, the reads and the record with it (BR-SHL-019).

    `None` when the wizard sent no `fees` block — the old wizard's move-ins
    carry no lines, so their first bill is exactly what it always was (§8.3).

    The DEPOSIT line is written from `deposit.take`'s answer and only when the
    deposit is OWED (`required`): a waived deposit is not charged, and a plan
    asking none has nothing to write. A sent deposit row is checked against it.
    """
    if fees is None:
        return None
    unit_id = getattr(account, "unit_id", None)
    started = list(services) if services is not None else unit_services(unit_id)
    customer_class = _account_type_code(account)
    sizes = sizes_by_service(unit_id, started)
    plan_fees = _rating("plan_move_in_charges")
    price = _rating("price_code")
    plan_codes: set[str] = set()
    if plan_fees is not None and getattr(account, "unit_id", None):
        plan_id = _unit_plan_id(unit_id)
        plan_codes = {
            str(row["code"]).upper()
            for row in plan_fees(
                plan_id, customer_class=customer_class, size_by_service=sizes, services=started
            )
        }

    owed = deposit_result if (deposit_result or {}).get("decision") == customers_deposit.DECISION_REQUIRED else None
    lines: list[dict[str, Any]] = []
    sent_deposit = next((row for row in fees if row.kind == FEE_KIND_DEPOSIT), None)
    if sent_deposit is not None:
        if owed is None:
            _raise([_fe(f"fees[{sent_deposit.index}].kind", errors.VAL_RANGE, DEPOSIT_NOT_OWED)])
        figure = Decimal(str(owed["amount"])).quantize(MONEY_PLACES)
        if sent_deposit.amount is not None and sent_deposit.amount != figure:
            _raise(
                [
                    _fe(
                        f"fees[{sent_deposit.index}].amount",
                        errors.VAL_RANGE,
                        customers_deposit.AMOUNT_NOT_PLAN,
                        amount=str(figure),
                    )
                ]
            )
    if owed is not None:
        standard = customers_deposit.plan_standard_for(account) or {}
        lines.append(
            {
                "kind": FEE_KIND_DEPOSIT,
                "source": FEE_SOURCE_PLAN,
                "charge_code_id": standard.get("charge_id") or None,
                "code": standard.get("code") or DEPOSIT_CODE,
                "description": DEPOSIT_DESCRIPTION,
                "amount": Decimal(str(owed["amount"])).quantize(MONEY_PLACES),
                "note": sent_deposit.note if sent_deposit is not None else None,
            }
        )
    for row in fees:
        if row.kind != FEE_KIND_FEE:
            continue
        if row.source == FEE_SOURCE_PLAN and str(row.code).upper() not in plan_codes:
            _raise([_fe(f"fees[{row.index}].code", errors.VAL_RANGE, NOT_FROM_PLAN, code=row.code)])
        priced = (
            price(str(row.code), customer_class=customer_class, size_by_service=sizes)
            if price is not None
            else {"refusal": "rating_not_wired"}
        )
        amount = _price_check(row, priced)
        lines.append(
            {
                "kind": FEE_KIND_FEE,
                "source": row.source,
                "charge_code_id": priced.get("charge_id"),
                "code": priced.get("code") or row.code,
                "description": priced.get("name") or row.code,
                "amount": amount,
                "note": row.note,
            }
        )
    currency = (owed or {}).get("currency") or seams_currency()
    written = []
    for seq, line in enumerate(lines, start=1):
        written.append(
            MoveFeeLine.objects.create(
                tenant_id=account.tenant_id,
                move_record_id=move_record_id,
                seq=seq,
                currency=currency,
                is_sample=is_sample,
                **line,
            )
        )
    total = sum((row.amount for row in written), ZERO)
    answer = {
        "lines": [line_dict(row) for row in written],
        "total": str(Decimal(total).quantize(MONEY_PLACES)),
        "currency": currency,
    }
    # CLAUDE.md rule 7 — charging a fee is a money action.
    core_audit.write_row(
        action="move_in.fees_recorded",
        entity_type="move_record",
        entity_id=move_record_id,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={"account_id": str(account.pk), **answer},
    )
    return answer


def _account_type_code(account: Any) -> str | None:
    account_type = getattr(account, "account_type", None)
    return getattr(account_type, "code", None) if account_type is not None else None


def line_dict(row: MoveFeeLine) -> dict[str, Any]:
    return {
        "seq": row.seq,
        "kind": row.kind,
        "source": row.source,
        "charge_code_id": str(row.charge_code_id) if row.charge_code_id else None,
        "code": row.code,
        "description": row.description,
        "amount": str(Decimal(row.amount).quantize(MONEY_PLACES)),
        "currency": row.currency,
        "note": row.note,
        # OQ-BIL-12788 (a), stated on every line.
        "taxed_at_move_in": False,
    }


def first_bill_fee_lines(account_id: Any) -> list[dict[str, Any]]:
    """**Billing's read (P1.14)** — the FEE lines (not the deposit) the move-in
    that OPENED this account recorded, oldest move first. `[]` for an account
    no move-in with a fee table opened, which is every account before this CR.

    The deposit is deliberately absent: the first bill prices it from the plan
    minus what was paid (`first_bill.deposit_line_for`, BR-PAY-012), and a
    second source for one figure would be `DEF-154`'s shape.
    """
    from apps.customers import moves

    return [
        {
            "code": row.code,
            "description": row.description,
            "amount": Decimal(row.amount).quantize(MONEY_PLACES),
            "currency": row.currency,
            "charge_id": str(row.charge_code_id) if row.charge_code_id else None,
        }
        for row in MoveFeeLine.objects.filter(
            move_record__account_id=account_id,
            move_record__kind=moves.KIND_MOVE_IN,
            kind=FEE_KIND_FEE,
        ).order_by("move_record__created_at", "seq")
    ]


# ═══════════════════════════════════════════════════════════════════════════
# At Complete — the money (P1.13)
# ═══════════════════════════════════════════════════════════════════════════
def _instant(day: date | None) -> datetime | None:
    """The clerk's DAY as payments' instant — never `now()` (BR-TEN-043),
    exactly `deposit._as_datetime`, which owns the reasoning: midnight in the
    UTILITY'S timezone (`OQ-153` CLOSED; `DEF-CUS-9754`)."""
    return customers_deposit._as_datetime(day) if day else None


def take_payment(
    actor: Any,
    *,
    account: Any,
    instruction: PaymentInstruction | None,
    fees: dict[str, Any] | None,
    deposit_result: dict[str, Any] | None,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Record what the customer paid today, or record that it goes on the bill.

    INSIDE the move-in's transaction. `None` when the wizard sent no `payment`
    block. See the module docstring §2 for the split and the worked figures.
    """
    if instruction is None:
        return None
    total = Decimal(str((fees or {}).get("total") or "0")).quantize(MONEY_PLACES)
    currency = (fees or {}).get("currency") or seams_currency()
    answer: dict[str, Any] = {
        "mode": instruction.mode,
        "total": str(total),
        "currency": currency,
        "amount_paid": str(ZERO.quantize(MONEY_PLACES)),
        "on_first_bill": str(total),
        "payments": [],
        "receipt_no": None,
        "notes": [],
    }
    if not instruction.pays_now:
        return answer
    amount = instruction.amount or ZERO
    if amount > total:
        _raise([_fe("payment.amount", errors.VAL_RANGE, MORE_THAN_FEES, total=str(total))])

    owed = None
    if (deposit_result or {}).get("decision") == customers_deposit.DECISION_REQUIRED:
        owed = Decimal(str(deposit_result["amount"])).quantize(MONEY_PLACES)  # type: ignore[index]
    deposit_part = owed if owed is not None and amount >= owed else ZERO
    prepay_part = amount - deposit_part
    reference = instruction.idempotency_reference
    common = {
        "actor": actor,
        "account_id": account.pk,
        # Posted at entry, never cleared here (CR-186-BRC10, DEF-CUS-10324).
        "posted_at": _instant(instruction.received_on),
        "method_code": instruction.method_code,
        "confirmation": instruction.confirmation,
    }
    if deposit_part > 0:
        recorded = seams.record_deposit_payment(
            **common,
            amount=deposit_part,
            idempotency_reference=f"{reference}:deposit" if reference else None,
        )
        _note_recorded(answer, recorded, PURPOSE_DEPOSIT, deposit_part, warnings)
        if recorded is not None and deposit_result is not None:
            # The deposit step said *deferred to the first bill*; it is paid now.
            deposit_result["notes"] = [
                note
                for note in deposit_result.get("notes") or []
                if note != customers_deposit.DEFERRED_TO_FIRST_BILL
            ]
            deposit_result["payment_no"] = recorded.get("payment_no")
            deposit_result["payment_id"] = str(recorded.get("payment_id") or "") or None
            deposit_result["amount_taken"] = str(deposit_part)
            held = recorded.get("held_after")
            deposit_result["held_after"] = str(held) if held is not None else None
            deposit_result["held"] = held is not None
            account.refresh_from_db(fields=["deposit_on_file", "deposit_received_on"])
    if prepay_part > 0:
        record_payment = seams.resolve("payments", "record_payment")
        recorded = None
        if record_payment is not None:
            paid = record_payment(
                actor,
                account_id=account.pk,
                amount=prepay_part,
                posted_at=common["posted_at"],
                method_code=instruction.method_code,
                confirmation=instruction.confirmation,
                purpose=PURPOSE_PREPAY,
                idempotency_reference=f"{reference}:fees" if reference else None,
            )
            recorded = {
                "payment_id": getattr(paid, "payment_id", None),
                "payment_no": getattr(paid, "payment_no", None),
                "status": getattr(paid, "status", None),
                "problems": tuple(getattr(paid, "problems", ()) or ()),
            }
        _note_recorded(answer, recorded, PURPOSE_PREPAY, prepay_part, warnings)

    paid_total = sum((Decimal(p["amount"]) for p in answer["payments"]), ZERO)
    answer["amount_paid"] = str(paid_total.quantize(MONEY_PLACES))
    answer["on_first_bill"] = str((total - paid_total).quantize(MONEY_PLACES))
    answer["receipt_no"] = answer["payments"][0]["payment_no"] if answer["payments"] else None
    core_audit.write_row(
        action="move_in.payment_taken",
        entity_type="account",
        entity_id=account.pk,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={k: v for k, v in answer.items() if k != "notes"},
    )
    return answer


def _note_recorded(
    answer: dict[str, Any],
    recorded: dict[str, Any] | None,
    purpose: str,
    amount: Decimal,
    warnings: list[dict[str, Any]] | None,
) -> None:
    if recorded is None:
        # G20 — an unwired seam REPORTS; it never answers "recorded".
        answer["notes"].append(PAYMENTS_UNWIRED)
        if warnings is not None:
            warnings.append({"code": PAYMENTS_UNWIRED, "rule": "BR-CUS-037"})
        return
    answer["payments"].append(
        {
            "purpose": purpose,
            "amount": str(amount.quantize(MONEY_PLACES)),
            "payment_id": str(recorded.get("payment_id")) if recorded.get("payment_id") else None,
            "payment_no": recorded.get("payment_no"),
            "status": recorded.get("status"),
        }
    )
    for problem in recorded.get("problems") or ():
        code = problem.get("code") if isinstance(problem, dict) else None
        if code:
            answer["notes"].append(code)


# ═══════════════════════════════════════════════════════════════════════════
# P1.16 — *See full rates*, narrowed to this move-in (image 42)
# ═══════════════════════════════════════════════════════════════════════════
def _asset_tree(unit_id: Any, services: Iterable[str]) -> list[dict[str, Any]]:
    """Per service: the unit's meters on that service's point, each with what
    hangs off it (a sub-meter, a backflow device, an inverter) — image 42's
    tree. The point's assets and the rows both come from the
    assets seam (`parent_asset_id`); nothing is written or priced."""
    ids_on = seams.resolve("assets", "asset_ids_for_service_point", kind="selectors")
    assets = {str(row["id"]): dict(row) for row in seams.assets_on_unit(unit_id)}
    children: dict[str, list[dict[str, Any]]] = {}
    for asset in assets.values():
        if asset.get("parent_asset_id"):
            children.setdefault(str(asset["parent_asset_id"]), []).append(asset)

    def node(asset: dict[str, Any]) -> dict[str, Any]:
        return {
            "asset_no": asset.get("asset_no"),
            "type": asset.get("type"),
            "qualifier": asset.get("qualifier"),
            "size_class": asset.get("size_class"),
            "children": [node(child) for child in children.get(str(asset["id"]), [])],
        }

    wanted = set(services)
    out = []
    for point in seams.service_points_for(unit_id):
        service = point.get("service")
        if service not in wanted:
            continue
        on_point = {str(one) for one in (ids_on(point["id"]) if ids_on is not None else [])}
        roots = [
            node(asset)
            for key, asset in assets.items()
            if key in on_point and str(asset.get("parent_asset_id") or "") not in on_point
        ]
        out.append({"service": service, "assets": roots})
    return out


def move_in_pricing(
    unit_id: Any, account_type: Any, *, services: Iterable[str] | None = None, size_class: Any = None
) -> dict[str, Any]:
    """`GET /move-ins/pricing` — CR-171 P1.16. The plan's shared sections
    narrowed by rating to this class, these services and these connection
    sizes, beside the deposit for this class and the move-in's fee rows."""
    code = str(account_type or "").strip() or None
    started = list(services) if services is not None else unit_services(unit_id)
    sizes = sizes_by_service(unit_id, started)
    plan_id = _unit_plan_id(unit_id)
    narrow = _rating("narrowed_sections")
    sections = None
    if plan_id is not None and narrow is not None:
        sections = narrow(plan_id, customer_class=code, size_by_service=sizes, services=started)
    fees = default_rows(unit_id, code, services=started, size_class=size_class)
    return {
        "unit_id": str(unit_id),
        "account_type": code,
        "services": started,
        "plan": sections,
        "plan_absent": None if plan_id is not None else "unit_has_no_plan",
        "deposit": fees["deposit"],
        "fees": {key: fees[key] for key in ("rows", "total", "currency")},
        "assets": _asset_tree(unit_id, started),
        # OQ-BIL-12788 (a), PO 2026-10-05 — said once for the whole read.
        "move_in_fees_taxed": False,
    }

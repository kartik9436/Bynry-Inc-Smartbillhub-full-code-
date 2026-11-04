# ── Trace ──────────────────────────────────────────────
# Change:   CR-181-BRC10 B1 (the offer on the search) · B2 (reopen at Complete)
#           · B3 (the balance choice) · B4 (the setting it reads) — lane
#           REOPEN, 2026-10-13
# Rules:    PO rulings 2026-10-13, verbatim: *"Q2 - Reopen, for the same unit
#           only ; Q3 - give opton to use whether pay it now or carry itr - Must
#           pay first · Carry it onto the reopened account · Clerk chooses"* and
#           *"Q4 - keep 5 years right now"* · BR-CUS-017 (at most one active
#           account per unit — enforced by `_make_occupying`, not here) ·
#           BR-CUS-056 (no start on or before the last move day) · BR-CUS-037
#           (customers writes no financial table) · DEF-127 (what an account
#           owes is the LEDGER's, never `accounts.balance`) · CLAUDE.md hard
#           rules 1, 4, 7
# Tests:    06-backend/tests/test_cr181_returning_customer_reopen.py
# ───────────────────────────────────────────────────────
"""**A returning customer's own account, reopened on the same unit.**

Viktor Valdez (C-00022) lived in SCW-U-022 on account AC-2026-00022, moved
out on 17 September and left owing money. He comes back to the same unit.
Until this module every move-in opened a NEW account, so his history and his
debt stayed on a closed number nobody at the counter was shown. PO Q2: the
clerk may **reopen** that account — same number, full history — and Q3: the
clerk then chooses whether what it still owes is **paid first** or **carried**.

WHAT IS CHANGED BY A REOPEN, AND NOTHING ELSE (hard rule 4)
    * the ACCOUNT row: status back to the move-in's occupying status,
      `opened_at` = the move-in date, `closed_at` cleared, and the move-in's
      own preferences (category, autopay, paperless …) — the same columns a
      new account would be written with;
    * NEW `service_agreements` rows for the services ticked, started on the
      move-in date (the old ones keep their `ended_on`);
    * the deposit and the fees are re-derived from TODAY's unit plan by the
      move-in's own steps, exactly as for a new account.
    No issued invoice, invoice line, payment or journal line is touched: the
    old balance simply stays where the books already have it, on this account.

THE GUARDS (refused BY NAME, before anything is written)
    same unit · this customer's account · closed (and not a cancelled move-in)
    · closed within `reopen_within_years` (S66 Billing defaults, default 5;
    0 = never) · the unit has nobody in it · the move-in date after the day it
    closed. The unit's occupancy is checked again under the unit lock by
    `_make_occupying` — this module never re-implements BR-CUS-017.

THE BALANCE CHOICE (PO Q3)
    * nothing owed → no choice is asked and none is recorded;
    * `pay_first` → Complete is REFUSED (`customers.moveIn.reopen.payFirst`)
      until the ledger says 0.00. The clerk records the payment through
      Payments' own record-payment door on the account (the wizard reuses the
      account page's `RecordPaymentModal`) — this module records no money;
    * `carry` → the balance stays on the reopened account and the next bill
      shows it; the choice and the figure are written on `move_in_reopenings`.
    A ledger that cannot be read refuses `pay_first` (fail closed) and records
    `carry` with no figure — never a 0.00 nobody derived (DEF-127).

⚠ **NOTHING HERE CATCHES A DATABASE ERROR** (hard-won law 14): every refusal is
raised before the move-in's transaction opens or rolls the whole of it back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from core import audit as core_audit
from core import errors

from apps.customers import models, seams
from apps.customers.move_in_reopen_models import (
    BALANCE_CHOICES,
    CHOICE_CARRY,
    CHOICE_PAY_FIRST,
    MoveInReopening,
)

#: The two keys the move-in door admits for this (`services.MOVE_IN_FIELDS`).
FIELD_ACCOUNT = "reopen_account_id"
FIELD_BALANCE = "reopen_balance"
FIELDS: frozenset[str] = frozenset({FIELD_ACCOUNT, FIELD_BALANCE})

#: The S66 parameter (`tenancy.settings_families.BILLING_DEFAULTS`).
SETTING_KEY = "reopen_within_years"
DEFAULT_YEARS = 5

MONEY_PLACES = Decimal("0.0001")
ZERO = Decimal("0")

#: Why an account cannot be reopened — the offer's `reason`, and the refusal.
REASON_OTHER_UNIT = "other_unit"
REASON_NOT_CLOSED = "not_closed"
REASON_CANCELLED = "cancelled"
REASON_TOO_OLD = "too_old"
REASON_UNIT_OCCUPIED = "unit_occupied"
REASON_OTHER_CUSTOMER = "other_customer"

REFUSAL_KEYS: dict[str, str] = {
    REASON_OTHER_UNIT: "customers.moveIn.reopen.otherUnit",
    REASON_NOT_CLOSED: "customers.moveIn.reopen.notClosed",
    REASON_CANCELLED: "customers.moveIn.reopen.notClosed",
    REASON_TOO_OLD: "customers.moveIn.reopen.tooOld",
    REASON_UNIT_OCCUPIED: "customers.account.unit_already_occupied",
    REASON_OTHER_CUSTOMER: "customers.moveIn.reopen.otherCustomer",
}
CHOICE_REQUIRED = "customers.moveIn.reopen.choiceRequired"
PAY_FIRST = "customers.moveIn.reopen.payFirst"
BALANCE_UNREADABLE = "customers.moveIn.reopen.balanceUnreadable"
START_ON_PRIOR_MOVE_DAY = "customers.account.start_on_prior_move_day"
BR_REF = "BR-CUS-1119"


# ═══════════════════════════════════════════════════════════════════════════
# THE SETTING AND THE FIGURE
# ═══════════════════════════════════════════════════════════════════════════
def within_years() -> int:
    """`reopen_within_years` from S66, through tenancy's own selector (B1).
    An unreadable settings row answers the ruled default rather than opening
    the door wider: 5 is the PO's figure."""
    reader = seams.resolve("tenancy", "settings_family", kind="selectors")
    if reader is None:  # pragma: no cover - tenancy always imports
        return DEFAULT_YEARS
    value = (reader("billing-defaults") or {}).get(SETTING_KEY)
    try:
        return int(value) if value is not None else DEFAULT_YEARS
    except (TypeError, ValueError):  # pragma: no cover - the family validates it
        return DEFAULT_YEARS


def _years_before(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29 February in a year that has none
        return day.replace(year=day.year - years, day=28)


def outstanding(account_id: Any) -> tuple[Decimal | None, str | None]:
    """What the account owes, from the LEDGER — `(amount, currency)`.

    The POSITIVE position (`owner_lookup.customer_accounts`' meaning): a credit
    is not a debt. `None` when the books cannot be asked (DEF-127)."""
    positions = seams.ar_positions([str(account_id)])
    amount = positions.amount_for(account_id)
    if amount is None:
        return None, positions.currency
    # ⚖️ **NET OF WHAT THE UTILITY ALREADY HOLDS FOR THE ACCOUNT** (our
    # judgment, decision log 2026-10-13 REOPEN (b)). A payment taken against a
    # debt with no allocatable bill — a cutover opening balance, a final bill
    # the allocator cannot class — is CARRIED as credit (2400) and leaves AR
    # where it was, so *pay first* measured on AR alone could never be met by
    # paying. Worked: AR $84.20, an $84.20 payment carried as credit → owes
    # $0.00. A NEGATIVE credit is a real debt (OQ-132) and adds to it.
    credit = _credit_held(account_id)
    owed = max(Decimal(str(amount)) - credit, ZERO).quantize(MONEY_PLACES)
    return owed, positions.currency


def _credit_held(account_id: Any) -> Decimal:
    """Payments' own signed credit position for the account, by name (B1)."""
    reader = seams.resolve("payments", "account_credit_position", kind="selectors")
    if reader is None:  # pragma: no cover - payments always imports
        return ZERO
    return Decimal(str(reader(account_id) or 0))


# ═══════════════════════════════════════════════════════════════════════════
# CAN THIS ACCOUNT BE REOPENED ON THIS UNIT?
# ═══════════════════════════════════════════════════════════════════════════
def why_not(account: models.Account, *, unit_id: Any, today: date | None = None) -> str | None:
    """`None` when `account` may be reopened on `unit_id` today, else the reason."""
    from apps.customers import move_in_cancel, selectors, services

    if account.unit_id is None or str(account.unit_id) != str(unit_id):
        return REASON_OTHER_UNIT
    if account.closed_at is None or account.status.behavior_class != services.CLASS_TERMINAL:
        return REASON_NOT_CLOSED
    if move_in_cancel.is_cancelled(account):
        return REASON_CANCELLED
    years = within_years()
    today = today or seams.tenant_today()
    if years <= 0 or account.closed_at < _years_before(today, years):
        return REASON_TOO_OLD
    if selectors.occupying_accounts_for_unit(unit_id).exists():
        return REASON_UNIT_OCCUPIED
    return None


def customer_account_on_unit(unit_id: Any, customer_id: Any) -> models.Account | None:
    """This customer's most recently CLOSED account on this unit (not a
    cancelled move-in), or None. The one the clerk may reopen."""
    from apps.customers import move_in_cancel, services

    rows = (
        models.Account.objects.filter(
            tenant_id=seams_tenant_id(),
            unit_id=unit_id,
            closed_at__isnull=False,
            status__behavior_class=services.CLASS_TERMINAL,
            pk__in=models.CustomerAccount.objects.filter(customer_id=customer_id).values(
                "account_id"
            ),
        )
        .select_related("status")
        .order_by("-closed_at", "-created_at", "-id")
    )
    for row in rows[:5]:
        if not move_in_cancel.is_cancelled(row):
            return row
    return None


def seams_tenant_id() -> Any:
    from apps.customers import services

    return services._tenant_id()


def offer_for(unit_id: Any, customer_id: Any) -> dict[str, Any] | None:
    """The search's *Reopen AC-…* fact for one customer on one unit, or None
    when the customer holds no closed account there. `eligible` False carries
    the `reason` so the screen can say *New account* and why, in its words."""
    account = customer_account_on_unit(unit_id, customer_id)
    if account is None:
        return None
    reason = why_not(account, unit_id=unit_id)
    owed, currency = outstanding(account.id)
    return {
        "account_id": str(account.id),
        "account_no": account.account_no,
        "closed_at": account.closed_at.isoformat() if account.closed_at else None,
        "eligible": reason is None,
        "reason": reason,
        "outstanding": str(owed) if owed is not None else None,
        "currency": currency,
        "within_years": within_years(),
    }


# ═══════════════════════════════════════════════════════════════════════════
# THE COMMIT — validated before the transaction, applied inside it
# ═══════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class ReopenRequest:
    account_id: str
    choice: str | None


@dataclass
class ReopenPlan:
    account: models.Account
    choice: str | None
    owed: Decimal | None
    currency: str | None
    previous_opened_at: date | None
    previous_closed_at: date


def _refuse(key: str, *, code: str = errors.BIZ_STATE, **params: Any) -> None:
    raise errors.BizError(code, br_ref=BR_REF, message_key=key, params=params)


def pop(data: dict[str, Any]) -> ReopenRequest | None:
    """POP both keys off the move-in body (the account write must never see
    them) and check their shape. `None` = a move-in that opens a new account."""
    raw_id = data.pop(FIELD_ACCOUNT, None)
    raw_choice = data.pop(FIELD_BALANCE, None)
    choice = None if raw_choice in (None, "") else str(raw_choice)
    if choice is not None and choice not in BALANCE_CHOICES:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key=CHOICE_REQUIRED,
            params={"field": FIELD_BALANCE, "allowed": list(BALANCE_CHOICES)},
        )
    if raw_id in (None, ""):
        if choice is not None:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="customers.account.unknown_field",
                params={"field": FIELD_BALANCE},
            )
        return None
    return ReopenRequest(account_id=str(raw_id), choice=choice)


def check(
    request: ReopenRequest | None,
    *,
    unit_id: Any,
    customer_block: Any,
    opened_at: Any,
) -> ReopenPlan | None:
    """Every guard, BEFORE the transaction opens — a refusal writes nothing and
    the clerk keeps every field on screen."""
    if request is None:
        return None
    account = (
        models.Account.objects.filter(tenant_id=seams_tenant_id(), pk=request.account_id)
        .select_related("status")
        .first()
    )
    if account is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    reason = why_not(account, unit_id=unit_id)
    if reason is not None:
        _refuse(REFUSAL_KEYS[reason], code=errors.BIZ_STATE, reason=reason, account_no=account.account_no)

    # The SAME customer: the clerk linked them on step 2 (`customer_id`).
    customer_id = customer_block.get("customer_id") if isinstance(customer_block, dict) else None
    linked = customer_id not in (None, "") and models.CustomerAccount.objects.filter(
        tenant_id=account.tenant_id, account_id=account.id, customer_id=customer_id
    ).exists()
    if not linked:
        _refuse(
            REFUSAL_KEYS[REASON_OTHER_CUSTOMER],
            reason=REASON_OTHER_CUSTOMER,
            account_no=account.account_no,
        )

    # BR-CUS-056 against the account's OWN last day — `_make_occupying` only
    # compares with OTHER accounts on the unit (it excludes this one).
    start = _as_date(opened_at)
    if start is not None and start <= account.closed_at:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-CUS-056",
            message_key=START_ON_PRIOR_MOVE_DAY,
            params={
                "opened_at": start.isoformat(),
                "prior_account_no": account.account_no,
                "prior_closed_at": account.closed_at.isoformat(),
            },
        )

    owed, currency = outstanding(account.id)
    if owed is None:
        if request.choice == CHOICE_PAY_FIRST:
            _refuse(BALANCE_UNREADABLE, account_no=account.account_no)
    elif owed > ZERO:
        if request.choice is None:
            _refuse(CHOICE_REQUIRED, account_no=account.account_no, amount=str(owed), currency=currency)
        if request.choice == CHOICE_PAY_FIRST:
            _refuse(PAY_FIRST, account_no=account.account_no, amount=str(owed), currency=currency)
    return ReopenPlan(
        account=account,
        # What the clerk chose, as sent: *pay first* that has been paid reaches
        # here owing 0.00 and is still the clerk's recorded choice.
        choice=request.choice,
        owed=owed,
        currency=currency,
        previous_opened_at=account.opened_at,
        previous_closed_at=account.closed_at,
    )


def _as_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


#: The account columns a reopen writes from the move-in's validated values —
#: the columns `_open_account` would have created a new row with. Nothing else
#: on the row moves: its number, currency, premises, unit and deposit register
#: are the account's own.
REOPEN_COLUMNS: tuple[str, ...] = (
    "status",
    "account_type",
    "account_subtype",
    "opened_at",
    "autopay",
    "paperless",
    "sms_reminders",
    "tax_exempt",
    "tax_exempt_ref",
    "tax_exempt_expires",
    "eligibility_claimed",
    "eligibility_note",
)


def reopen_row(actor: Any, plan: ReopenPlan, cleaned: dict[str, Any]) -> models.Account:
    """INSIDE `_open_account`'s transaction: lock the closed row and make it
    the move-in's account. Audited `account.reopened` (hard rule 7) with the
    dates it had before, which the row itself no longer holds."""
    from apps.customers import services

    account = (
        models.Account.objects.select_for_update()
        .select_related("status")
        .get(tenant_id=plan.account.tenant_id, pk=plan.account.pk)
    )
    before = {
        "status": account.status.code,
        "opened_at": str(account.opened_at) if account.opened_at else None,
        "closed_at": str(account.closed_at) if account.closed_at else None,
    }
    defaults = {"autopay": False, "paperless": False, "sms_reminders": False, "tax_exempt": False,
                "eligibility_claimed": False}
    for column in REOPEN_COLUMNS:
        if column in cleaned:
            setattr(account, column, cleaned[column])
        elif column in defaults:
            setattr(account, column, defaults[column])
    if cleaned.get("preferred_language"):
        account.preferred_language = cleaned["preferred_language"]
    if cleaned.get("custom_data"):
        account.custom_data = {**dict(account.custom_data or {}), **cleaned["custom_data"]}
    account.closed_at = None
    account.save()
    services._audit(
        actor,
        "account.reopened",
        account.id,
        before=before,
        after={
            "status": account.status.code,
            "opened_at": str(account.opened_at) if account.opened_at else None,
            "closed_at": None,
            "account_no": account.account_no,
            "unit_id": str(account.unit_id) if account.unit_id else None,
        },
    )
    return account


def merge_people(
    account: models.Account, contact: dict[str, Any] | None, addresses: list[dict[str, Any]]
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    """A reopened account keeps the people it already holds. The contact the
    clerk typed FILLS the primary contact's empty fields (a phone it never had,
    a new email where none was kept) rather than becoming a second primary; it
    is created only when the account holds no live contact at all. A mailing
    address is added only when the account has none. Returns what is still
    to be CREATED, in `_open_account`'s own shapes."""
    if contact is not None:
        existing = (
            models.Contact.objects.filter(
                tenant_id=account.tenant_id, account=account, deleted_at__isnull=True
            )
            .order_by("-is_primary", "created_at", "id")
            .first()
        )
        if existing is not None:
            changed = []
            for field, value in contact.items():
                if field in ("is_primary", "full_name") or value in (None, ""):
                    continue
                if hasattr(existing, field) and getattr(existing, field) in (None, ""):
                    setattr(existing, field, value)
                    changed.append(field)
            if changed:
                existing.save(update_fields=[*changed, "updated_at"])
            contact = None
    if addresses and models.Address.objects.filter(
        tenant_id=account.tenant_id, account=account, kind="mailing", deleted_at__isnull=True
    ).exists():
        addresses = [row for row in addresses if row.get("kind") != "mailing"]
    return contact, addresses


def record(actor: Any, plan: ReopenPlan, *, move_record_id: Any) -> dict[str, Any]:
    """The reopen and the clerk's balance choice, on the move-in (PO Q3), and
    its audit row. Returns what the response and the Move-ins list serve."""
    row = MoveInReopening.objects.create(
        tenant_id=plan.account.tenant_id,
        move_record_id=move_record_id,
        account_id=plan.account.pk,
        previous_opened_at=plan.previous_opened_at,
        previous_closed_at=plan.previous_closed_at,
        balance_choice=plan.choice,
        balance_at_complete=plan.owed,
        currency=plan.currency,
    )
    answer = serialize(row, account_no=plan.account.account_no)
    core_audit.write_row(
        action="move_in.reopen_balance",
        entity_type="account",
        entity_id=plan.account.pk,
        actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
        after={**answer, "move_record_id": str(move_record_id)},
    )
    return answer


def serialize(row: MoveInReopening, *, account_no: str | None = None) -> dict[str, Any]:
    return {
        "account_id": str(row.account_id),
        "account_no": account_no if account_no is not None else row.account.account_no,
        "previous_opened_at": str(row.previous_opened_at) if row.previous_opened_at else None,
        "previous_closed_at": str(row.previous_closed_at),
        "balance_choice": row.balance_choice,
        "balance_at_complete": (
            str(row.balance_at_complete.quantize(MONEY_PLACES))
            if row.balance_at_complete is not None
            else None
        ),
        "currency": row.currency,
    }


def for_move_records(move_record_ids: Any) -> dict[str, dict[str, Any]]:
    """`{move_record_id: reopen fact}` for a page of move-ins — ONE query."""
    rows = MoveInReopening.objects.filter(
        tenant_id=seams_tenant_id(), move_record_id__in=list(move_record_ids)
    ).select_related("account")
    return {str(row.move_record_id): serialize(row) for row in rows}


__all__ = [
    "CHOICE_CARRY",
    "CHOICE_PAY_FIRST",
    "FIELDS",
    "check",
    "offer_for",
    "pop",
    "record",
    "reopen_row",
    "why_not",
]

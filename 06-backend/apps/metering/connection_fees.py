# ── Trace ──────────────────────────────────────────────
# Change:   CR-163-BRC10 item 2 (lane NC-B) — "Add fees after submission, until
#           approval: pick a one-time charge code, qty, amount (price from the
#           charge code where it has one) → adds to the connection's quote/
#           invoice the lawful way". Decision log 2026-10-02 (`56eb54ba9`).
# Rules:    CLAUDE.md hard rule 4 (an issued invoice and its lines are never
#           edited — a correction or an addition is a NEW document) · hard
#           rule 2 (no figure is multiplied anywhere but billing) · hard rule 5
#           (only the ledger service writes journal lines — billing's issue
#           posts) · hard rule 7 (every money action writes audit_log) ·
#           BR-BIL-005 (one-time run idempotency) · BR-BIL-007 / BR-BIL-020
#           (the price is the tenant's charge code; a clerk types a figure only
#           for a code priced "entered when used") · BR-TEN-043 / G6 (an event
#           date, never a wall clock, on a money path) · BR-BIL-024 (the due
#           date is the posting date plus the terms the clerk captured)
# Tests:    06-backend/tests/test_cr163_add_fee.py (its money case runs on
#           PostgreSQL only — `requires_postgres`)
# ───────────────────────────────────────────────────────
"""**A fee added to a New Connection after it was submitted — a NEW bill.**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 money path (it raises and issues a
receivable). AI-authored 2026-10-02 under the PO ruling of 2026-08-09; the row
is in `12-governance/09-human-review-ledger.md`.

══════════════════════════════════════════════════════════════════════════════
WHY A NEW BILL AND NOT A LINE ON THE QUOTE
══════════════════════════════════════════════════════════════════════════════
A build's quote is raised AND ISSUED at Create (`commit_connection` step 6,
`billing.fee_bill.raise_and_issue_quote_bill`), so there is no draft to add a
line to — and an issued invoice line may never be updated (hard rule 4). The
only lawful way to charge more is a second document. So an added fee is ONE
issued `fee` bill against the same payer, through billing's own doors, and this
module writes down which bill belongs to which build in `connection_fee_bills`
— the same posture `connections.quote_invoice_id` already takes for the first.
The build record (`connection_record._money`) sums every bill it names.

══════════════════════════════════════════════════════════════════════════════
TWO DOORS, CHOSEN BY THE CODE'S OWN PRICING RULE
══════════════════════════════════════════════════════════════════════════════
* **A code that states its price** goes through the QUOTE door with a COUNT and
  the basis it is counted on (`per unit` · `per meter` · `per premise` —
  billing's spellings; CLAUDE.md hard rule 3: a quantity travels with its
  unit). Billing multiplies; nothing here does.
* **A code priced "entered when used"** (`per_case`) takes the clerk's figure,
  for the whole case and never multiplied (`DEF-RAT-8753`, CR-010 A2). That is
  billing's single-code door, `raise_charge_fee(entered_amount=…)`, drafted and
  issued in ONE transaction exactly as `raise_and_issue_charge_fee` does.

⚠ **`QuotedCharge` WAS NOT WIDENED TO CARRY AN AMOUNT, DELIBERATELY.** Its own
docstring says *"THE ABSENT MEMBER IS THE ENFORCEMENT"* of BR-BIL-020, and the
door that already takes an entered figure — for exactly the codes that may
have one — is the lawful route.

══════════════════════════════════════════════════════════════════════════════
THE SAME-DAY LIMIT, NAMED RATHER THAN WORKED AROUND
══════════════════════════════════════════════════════════════════════════════
Every one-time `fee` bill is idempotent on (account, `fee`, day) —
`core/idempotency.one_time_run_key`, 🔒 and signed. So a fee added ON THE DAY
the build was created, against the payer its quote went to, is refused by
`runs.DuplicateRun`: one account, one fee bill per day. That is `OQ-BIL-12377`,
OPEN, and the case it describes is now the common one. The refusal names the
day; nothing here invents a suffix to dodge the key and nothing merges two
charges onto one document.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from django.db import models, transaction
from django.utils import dateparse

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import seams
from core import audit as core_audit
from core import errors
from core.dbfields import uuid7_pk

BR_REF = "BR-BIL-020"

#: The states a fee may be added in — *"after submission, until approval"*.
#: A draft has no bill yet (its charges travel on the commit); an activated or
#: partly activated build has been approved; a cancelled one is over.
STATES_TAKING_FEES: tuple[str, ...] = (work_tables.REQUESTED, work_tables.IN_PROGRESS, work_tables.ON_HOLD)

#: Billing's own spellings (`fee_bill.BASIS_UNITS`), with spaces.
BASES: tuple[str, ...] = ("per unit", "per meter", "per premise")

#: The payment terms a clerk may pick — the wizard's own list (programme
#: item 19, PO 2026-10-02: *"Payment terms dropdown 7/15/30/60/90"*).
TERMS_DAYS: tuple[int, ...] = (7, 15, 30, 60, 90)

ONE_TIME = "one_time"
PER_CASE = "per_case"


class ConnectionFeeBill(models.Model):
    """One bill raised for a fee ADDED to a build after it was submitted.

    The invoice is billing's; this row is metering's note of which build it is
    for — an id held as a value, the reviewed posture of
    `connections.quote_invoice_id` (no cross-module foreign key; B2 §2).
    """

    id = uuid7_pk()
    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    connection = models.ForeignKey(
        work_tables.Connection,
        on_delete=models.PROTECT,
        db_column="connection_id",
        related_name="fee_bills",
    )
    invoice_id = models.UUIDField()
    charge_code = models.TextField()
    created_by = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "metering"
        db_table = "connection_fee_bills"
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "invoice_id"], name="uq_connection_fee_bills_invoice"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "connection"], name="ix_connection_fee_bills_conn"),
        ]


def _refuse(key: str, **params: Any) -> errors.ValidationError:
    return errors.ValidationError(errors.VAL_FORMAT, message_key=key, br_ref=BR_REF, params=params)


def _on_date(raw: Any) -> date:
    """The posting day the CLERK named — never a clock (BR-TEN-043, gate G6)."""
    if isinstance(raw, datetime):
        return raw.date()
    parsed = dateparse.parse_date(str(raw or "")[:10])
    if parsed is None:
        raise _refuse("metering.connection.feeDateRequired")
    return parsed


def _payer(connection: Any) -> Any:
    """The account the build's OWN bill went to; the owner's account where the
    build raised none. A second payer for one build is not this act's to pick."""
    if connection.quote_invoice_id is not None:
        bill = seams.quote_bill(connection.quote_invoice_id)
        if bill and bill.get("account_id") is not None:
            return bill["account_id"]
    return connection.owner_account_id


def add_connection_fee(actor: Any, connection_id: Any, payload: Any) -> dict[str, Any]:
    """`POST /connections/{id}/fees` — raise and issue ONE added fee as a new bill.

    Payload: `charge_code` · `quantity` + `basis` (a priced code) or `amount`
    (a code priced "entered when used") · `posting_date` · `due_days`.
    Answers the bill's number and total as billing stored them.
    """
    data = payload if isinstance(payload, dict) else {}
    connection = w6._connection_or_404(connection_id)
    if connection.state not in STATES_TAKING_FEES:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-MET-112",
            message_key="metering.connection.feeNotNow",
            params={"connection_no": connection.connection_no or "", "state": connection.state},
        )
    payer = _payer(connection)
    if payer is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-MET-113",
            message_key="metering.connection.messageNoOwnerAccount",
            params={"connection_no": connection.connection_no or ""},
        )

    code = str(data.get("charge_code") or "").strip()
    if not code:
        raise _refuse("metering.connection.feeCodeRequired")
    read_charge = seams.resolve("rating", "charge_by_code", kind="selectors")
    charge = read_charge(code) if read_charge is not None else None
    if charge is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if charge.get("charge_type") != ONE_TIME:
        # Item 2 says "a one-time charge code". A recurring base charge or a
        # penalty raised here would bill a build for a month or a late payment
        # it never had, so they are not a lawful pick (the dialog never offers them).
        raise _refuse("metering.connection.feeCodeRequired")
    per_case = charge.get("amount_rule") == PER_CASE

    try:
        due_days = int(data.get("due_days"))
    except (TypeError, ValueError):
        due_days = 0
    if due_days not in TERMS_DAYS:
        raise _refuse("metering.connection.feeTermsRequired")
    on_date = _on_date(data.get("posting_date"))

    quantity: Decimal | None = None
    entered: Decimal | None = None
    basis: str | None = None
    if per_case:
        try:
            entered = Decimal(str(data.get("amount")))
        except (InvalidOperation, TypeError, ValueError):
            entered = None
        if entered is None or not entered.is_finite() or entered <= 0:
            raise _refuse("metering.connection.feeAmountRequired")
    else:
        if data.get("amount") not in (None, ""):
            # BR-BIL-020 — a code that states its price takes no typed figure.
            raise _refuse("metering.connection.feeAmountNotTyped")
        try:
            quantity = Decimal(str(data.get("quantity")))
        except (InvalidOperation, TypeError, ValueError):
            quantity = None
        if quantity is None or not quantity.is_finite() or quantity <= 0:
            raise _refuse("metering.connection.feeQuantityRequired")
        basis = str(data.get("basis") or "").strip()
        if basis not in BASES:
            raise _refuse("metering.connection.feeBasisRequired")

    duplicate = seams.resolve("billing", "DuplicateRun", kind="runs")
    try:
        with transaction.atomic():
            if per_case:
                draft = seams.resolve("billing", "raise_charge_fee", kind="fee_bill")
                issue = seams.resolve("billing", "issue_charge_fee", kind="fee_bill")
                moment = seams.resolve("billing", "issue_moment", kind="fee_bill")
                if draft is None or issue is None or moment is None:
                    raise _unpublished(connection)
                invoice = draft(
                    actor,
                    account_id=payer,
                    charge_code=code,
                    on_date=on_date,
                    due_days=due_days,
                    entered_amount=entered,
                    # `DEF-MET-9217` — the build's owner account is held
                    # `pending_activation` until approval (CR-162), and this is
                    # the one door allowed to bill it in that window.
                    pending_new_connection_owner=True,
                )
                issue(actor, invoice, issued_at=moment(on_date))
                invoice.refresh_from_db()
            else:
                door = seams.quote_bill_door()
                shape = seams.quoted_charge_shape()
                if door is None or shape is None:
                    raise _unpublished(connection)
                invoice = door(
                    actor,
                    account_id=payer,
                    charges=[shape(charge_code=code, quantity=quantity, basis=basis)],
                    on_date=on_date,
                    due_days=due_days,
                    pending_new_connection_owner=True,  # `DEF-MET-9217`, as above
                )
            row = ConnectionFeeBill.objects.create(
                tenant_id=connection.tenant_id,
                connection=connection,
                invoice_id=invoice.pk,
                charge_code=code,
                created_by=getattr(actor, "id", None),
            )
            # Hard rule 7 — a money action, written by the person who pressed.
            core_audit.money_action(
                actor,
                "connection.fee_added",
                "connection",
                str(connection.id),
                before=None,
                after={
                    "connection_no": connection.connection_no,
                    "invoice_no": getattr(invoice, "invoice_no", None),
                    "charge_code": code,
                    "quantity": None if quantity is None else str(quantity),
                    "basis": basis,
                    "entered_amount": None if entered is None else str(entered),
                    "total": str(getattr(invoice, "total", "")),
                    "on_date": on_date.isoformat(),
                    "due_days": due_days,
                    "fee_bill_id": str(row.id),
                },
            )
    except Exception as exc:  # noqa: BLE001 — narrowed immediately below
        if duplicate is not None and isinstance(exc, duplicate):
            # ⚠ `OQ-BIL-12377` — one fee bill per account per day. The atomic
            # block above is a SAVEPOINT, so the refused run left nothing
            # behind and the request's transaction is still usable (law 14).
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-BIL-005",
                message_key="metering.connection.feeSameDay",
                params={"day": on_date.isoformat()},
            ) from exc
        refusal = seams.quote_refusal_class()
        if refusal is not None and isinstance(exc, refusal):
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="BR-BIL-007",
                message_key="metering.connection.feeCannotBePriced",
                params={"charge_code": code},
            ) from exc
        raise
    return {
        "invoice_no": getattr(invoice, "invoice_no", None),
        "invoice_id": str(invoice.pk),
        "total": str(getattr(invoice, "total", "")),
        "charge_code": code,
        "fee_bill_id": str(row.id),
    }


def _unpublished(connection: Any) -> errors.BizError:
    return errors.BizError(
        errors.BIZ_COMPLETENESS,
        br_ref="OQ-379",
        message_key="metering.connection.feeCannotBePriced",
        params={"charge_code": "", "connection_no": connection.connection_no or ""},
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-163-BRC10 item 2 · decision log 2026-10-02 (`56eb54ba9`) ·
#   billing.fee_bill (raise_and_issue_quote_bill · raise_charge_fee ·
#   issue_charge_fee) read as it stands · OQ-BIL-12377 (open)
# generated: 2026-10-02 by lane NC-B
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09 — HUMAN-REVIEW-PENDING)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

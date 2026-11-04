# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-FLOW · P1.23 · P1.24 ·
#           P1.25 (the details view's doors on a COMMITTED move-in)
# Rules:    CR-171 §6.2 J7 (change move-in date until the first bill issues) ·
#           BR-CUS-056 (the boundary day, re-checked on the new date) ·
#           BR-CUS-021 / BR-MET-128 / BR-MET-129 (opening reads commit through
#           metering's event door; customers never writes `meter_reads`) ·
#           BR-WRK-055 (a field module never fails the flow) · BR-CUS-152 (the
#           move record is never updated) · CLAUDE.md hard rules 1 · 7
# Tests:    06-backend/tests/test_cr171_mvi_flow_record_doors.py
# ───────────────────────────────────────────────────────
"""Three doors a clerk presses on a committed move-in (images 13, 14, 24, 27).

* **Change move-in date** (P1.23, J7) — moves the account's start and the
  service agreements that began on the old date. Refused once a bill has
  issued, or when billing cannot say (DEF-075's safe direction), and refused by
  `BR-CUS-056` when the new date lands on the previous occupant's last day.
* **Enter opening read** (P1.24) — the readings a clerk could not take at
  Complete, through the SAME metering event door the wizard uses
  (`services._commit_event_reads`, event `move_in`), dated the move-in date
  unless a row says otherwise. A reading below the last read is refused by
  metering (`BR-MET-129`) with the row named, and nothing is written.
* **Add a work order** (P1.25) — the rows the wizard's *Field visit* table
  takes, raised against the move record through `services._raise_flow_work`,
  the one function every flow uses. *Send a message* (P1.25's other half) needs
  NO new door: `GET|POST /accounts/{account_id}/communication` is the account's
  existing one and the record serves `account_id` (CR-171 §9.FLOW).

⚠ **THE MOVE RECORD IS NOT UPDATED BY A DATE CHANGE (`BR-CUS-152`).** Its
`effective_on` is the date the job was committed as; the date the account
STARTS is `accounts.opened_at`, which is what this door moves. So the details
view reads *Moved in on* from the account, not from the record (§9.FLOW, for
LIST). Our judgment, decision log 2026-10-05 MVI-FLOW.

⚠ **THE VISIT'S DUE DATE IS NOT MOVED HERE, AND THE ANSWER SAYS WHICH ORDERS
STILL CARRY THE OLD DAY.** J7 asks for it; Work's `reschedule` is an act with a
holder and a window that lane FIN-W is changing this round (CR-171 §8: P1.19
waits on FIN-W). Rather than guess its payload, the door answers
`visits_to_reschedule` (each `order_no`) so the screen links the clerk to the
order. Recorded as a deviation from J7 in the decision log.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.customers import models, move_in_cancel, seams


def _refuse(code: str, key: str, **params: Any) -> None:
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="CR-171-BRC10",
        message_key=key,
        params={"code": code, **params},
    )


def _committed(ref: str, *, lock: bool = False) -> tuple[Any, models.Account]:
    """The committed move-in and its account, or a named refusal. A pending
    job or a draft has no account to act on."""
    kind, record = move_in_cancel._resolve(ref)
    if kind != move_in_cancel.KIND_COMMITTED:
        _refuse("move_in_not_started", "customers.moveIn.notStartedYet")
    account = move_in_cancel._account(record, lock=lock)
    if move_in_cancel.record_is_cancelled(record, account):
        _refuse(move_in_cancel.ALREADY_CANCELLED, "customers.moveIn.cancel.alreadyCancelled")
    return record, account


def _refuse_once_billed(account: models.Account) -> None:
    if seams.last_issued_invoice_date(account.id) is not None:
        _refuse("move_in_date_bill_issued", "customers.moveIn.date.billIssued")
    if not seams.billing_can_answer():
        _refuse(move_in_cancel.BILLING_UNREADABLE, "customers.moveIn.cancel.billingUnreadable")


def _parse_date(value: Any) -> date:
    try:
        return date.fromisoformat(str(value or "").strip())
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.moveIn.date.invalid",
            params={"field": "opened_at"},
        ) from None


# ═══════════════════════════════════════════════════════════════════════════
# P1.23 · CHANGE MOVE-IN DATE (J7)
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def change_move_in_date(actor: Any, ref: str, opened_at: Any) -> dict[str, Any]:
    from apps.customers import services

    new = _parse_date(opened_at)
    with transaction.atomic():
        record, account = _committed(ref, lock=True)
        _refuse_once_billed(account)
        old = account.opened_at
        if old == new:
            return _date_answer(record, account, old, agreements=0)
        account.opened_at = new
        # BR-CUS-056 — the same refusal a move-in meets, on the new date,
        # BEFORE anything is saved.
        services._refuse_if_start_lands_on_the_prior_move_day(account)
        account.save(update_fields=["opened_at", "updated_at"])
        moved = 0
        for agreement in models.ServiceAgreement.objects.filter(
            tenant_id=account.tenant_id, account=account, started_on=old, ended_on__isnull=True
        ):
            agreement.started_on = new
            agreement.save(update_fields=["started_on", "updated_at"])
            moved += 1
        services._audit(
            actor,
            "account.move_in_date_changed",
            account.id,
            before={"opened_at": str(old)},
            after={"opened_at": str(new), "move_no": record.move_no, "agreements_moved": moved},
        )
    return _date_answer(record, account, old, agreements=moved)


def _date_answer(record: Any, account: models.Account, old: Any, *, agreements: int) -> dict[str, Any]:
    return {
        "move_no": record.move_no,
        "opened_at": str(account.opened_at),
        "was": str(old) if old else None,
        "agreements_moved": agreements,
        "visits_to_reschedule": [row["order_no"] for row in move_in_cancel._open_orders(record.move_no)],
    }


# ═══════════════════════════════════════════════════════════════════════════
# P1.24 · ENTER OPENING READ
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def enter_opening_reads(actor: Any, ref: str, reads: Any) -> dict[str, Any]:
    """`reads` = `[{meter_no, value | estimate, channel?, read_at?}]`, the
    wizard's own row shape. Dated the move-in date unless a row says
    otherwise (BR-TEN-043: an input, never a clock)."""
    from apps.customers import services

    with transaction.atomic():
        record, account = _committed(ref)
        answer = services._commit_event_reads(
            actor,
            event="move_in",
            reads=reads,
            default_read_at=account.opened_at,
            # DEF-CUS-10167 — the modal's read date, bounded like the wizard's.
            bounded_dates=True,
            field="reads",
            context={
                "account_id": str(account.id),
                "account_no": account.account_no,
                "unit_id": str(account.unit_id) if account.unit_id else None,
                "move_no": record.move_no,
                "after_complete": True,
            },
        )
        core_audit.write_row(
            action="move_in.opening_reads_entered",
            entity_type="account",
            entity_id=account.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            after={
                "move_no": record.move_no,
                "posted_reads": int(answer.get("posted_reads") or 0),
            },
        )
    return {
        "move_no": record.move_no,
        "posted_reads": int(answer.get("posted_reads") or 0),
        "warnings": list(answer.get("warnings") or ()),
    }


# ═══════════════════════════════════════════════════════════════════════════
# P1.25 · ADD A WORK ORDER
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def add_work_orders(actor: Any, ref: str, election: Any) -> dict[str, Any]:
    """`election` = the wizard's *Field visit* answer
    (`{"template_ids": [...], "orders": [...]}`), validated by the same
    `services._field_visit`. Raised OUTSIDE any transaction of ours, so a
    refused raise inside Work cannot poison one (hard-won law 14)."""
    from apps.customers import services

    record, account = _committed(ref)
    field_visit = services._field_visit(election)
    # `DEF-WRK-9784` — the wizard's own check, on the unit the move-in took.
    seams.check_flow_order_rows_on_unit(field_visit["orders"], getattr(account, "unit_id", None))
    if not field_visit["template_ids"] and not field_visit["orders"]:
        raise errors.ValidationError(
            errors.VAL_REQUIRED,
            message_key="customers.moveIn.work.nothingToRaise",
            params={"field": "orders"},
        )
    visit = services._raise_flow_work(
        actor,
        flow_kind="move_in",
        flow_id=record.id,
        template_ids=field_visit["template_ids"],
        orders=field_visit["orders"],
    )
    if not visit["work_orders"]:
        # The clerk's whole act was this raise; reporting it as a 200 with a
        # warning would put a success on screen over nothing (the
        # `queue_account_message` argument). The wizard's own call keeps the
        # warning posture because there the move is the act.
        warning = (visit["warnings"] or [seams.flow_work_not_raised()])[0]
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=warning.get("br_ref") or "BR-WRK-055",
            message_key=warning.get("message_key") or "work.fromFlows.notRaised",
            params={"code": warning.get("code")},
        )
    return {
        "move_no": record.move_no,
        "work_orders": visit["work_orders"],
        "warnings": visit["warnings"],
    }

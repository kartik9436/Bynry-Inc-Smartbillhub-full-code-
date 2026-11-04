# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · P1.22 · lane MVI-FLOW
# Rules:    CR-171 §6.2 J6 (cancel after Complete reverses only what has a
#           reversal, as new rows; refused once a bill has issued) · §6.1
#           (Cancelled status) · images 10, 14, 17 · BR-MET-036 (occupancy is
#           DERIVED — nothing here writes a unit or a meter) · BR-CUS-030
#           (closing an account: terminal status, closed_at, agreements end) ·
#           BR-CUS-1077 (`move_in_jobs`, `cancelled` written here and nowhere
#           else) · CLAUDE.md hard rules 1 · 4 · 5 · 7
# Question: OQ-CUS-12790 — CLOSED 2026-10-05 → (a), decision log *"FOUR PO
#           RULINGS IN ONE REPLY"* (4), verbatim: *"Release the deposit and
#           refund the full $175.00 as one refund, approved by Finance as
#           usual."* The stub is replaced (lane RULINGS, 2.541.0).
# Tests:    06-backend/tests/test_cr171_p1_22_cancel_move_in.py (+ PostgreSQL)
# 🔒 HUMAN-REVIEW-PENDING — money reversal (refund request) and an account
#    close; row in 12-governance/09-human-review-ledger.md.
# ───────────────────────────────────────────────────────
"""**Cancel move-in** — the danger item in *More ▾* on a *Not started* and on a
*Scheduled / Waiting on a read* move-in (images 10, 14), landing on the
*Cancelled* view (image 17).

════════════════════════════════════════════════════════════════════════════
TWO KINDS OF MOVE-IN CAN BE CANCELLED, AND THEY ARE DIFFERENT ACTS
════════════════════════════════════════════════════════════════════════════
* **Not started** — an approved request's pending `move_in_jobs` row. Nothing
  has been opened, so cancelling is one state move: `pending → cancelled`, with
  `closed_reason = move_in_cancelled`. The request stays *Approved* — it WAS
  approved; the job is what is called off (BR-CUS-080: the request answers what
  happened to the application, and the job carries the reason).
* **Committed** (*Scheduled / Waiting on a read*) — the wizard has already
  written an account, its agreements, opening reads, maybe money and work
  orders. J6 is the whole rule: **reverse only what has a reversal, as new
  rows** (hard rule 4):

  | What the move-in wrote | What cancel does |
  |---|---|
  | the account | CLOSED — terminal `closed` status, `closed_at` = the DAY BEFORE the move-in date, `close_reason = other` |
  | its service agreements | ENDED on that same day (`ended_on` is the documented close of an agreement, never an edit of history) |
  | money taken as credit | a REFUND REQUEST for the account's refundable credit, through `payments.refunds.request_refund` — Finance approves and issues it on the existing chain |
  | money taken and NOT YET CLEARED (a cheque or card still `processing`) | CALLED OFF through payments' own Cancel (`payments.cancel.cancel_payment`, reason `not_taken`) — nothing is refunded because nothing arrived (`DEF-CUS-9789`) |
  | a deposit held | RELEASED TO CREDIT (`payments.deposit_release.release_to_credit`: DR 2300 / CR 2400, a `deposit_releases` row) and the register moved by `services.record_deposit_movement(released=True)` — then refunded WITH the rest in the ONE refund request above (`OQ-CUS-12790` (a)) |
  | open work orders | CANCELLED through Work's own dispatch door (nothing deleted) |
  | opening reads | KEPT — append-only, and they are true readings |
  | the unit | nothing written — it reads Vacant because a terminal account does not occupy (BR-MET-036) |
  | the move record | nothing written — `BR-CUS-152`, nothing updates it |
  | a request's pending job | `done` stays `done`: the job WAS done; the cancel is the account's close |

⚠ **REFUSED ONCE A BILL HAS ISSUED (J6).** An issued invoice cannot be
reversed by a customers write (hard rule 4), so neither can the account it was
issued to. And a `None` from billing is NOT "no bill": when billing cannot
answer, the cancel is refused — `rollback_from_import`'s posture (DEF-075).

════════════════════════════════════════════════════════════════════════════
WHAT MAKES A COMMITTED MOVE-IN *CANCELLED* (for the list and the details view)
════════════════════════════════════════════════════════════════════════════
⚠ **DERIVED, BECAUSE NO COLUMN HOLDS IT.** `customers/0080` gave
`move_in_jobs` a `cancelled` state and gave the committed move-in nothing, and a
move record is never updated (`BR-CUS-152`). So: **a move-in whose account
closed BEFORE the day it opened never ran — it is Cancelled** (`is_cancelled`).
Both dates are retained columns, so the answer is durable, and a cancel writes
exactly that shape: `closed_at = opened_at − 1 day`. Our judgment, recorded in
the decision log (2026-10-05, MVI-FLOW).

⚠ **WHY THE DAY BEFORE AND NOT THE DAY ITSELF.** BR-CUS-056 refuses a new
occupant whose start lands ON the previous account's `closed_at`
(`_refuse_if_start_lands_on_the_prior_move_day`). Closing a cancelled account on
its own move-in date would therefore lock the NEXT real tenant out of that
date — cancelling Nilesh's 12 October move-in would refuse anyone else's 12
October. Closed on the 11th, the boundary is exactly where the previous
tenant left it. And no move-out can be dated before its own start, so the
shape is unambiguous.

⚖️ **THE DEPOSIT GOES BACK WITH EVERYTHING ELSE, AS ONE REFUND** — `OQ-CUS-12790`
CLOSED (a), PO verbatim: *"Release the deposit and refund the full $175.00 as one
refund, approved by Finance as usual."* Worked: Nilesh paid **$175.00 by check
1043** — a **$150.00** deposit and a **$25.00** fee — and cancels before any
bill. Inside the cancel's ONE transaction: the $150.00 is released to credit
(payments writes the release and its books entry, DR 2300 customer deposit
liability / CR 2400 customer credit balances; customers moves its own register
to $0.00), the credit now reads **$175.00**, and ONE refund request for
**$175.00** goes to Finance's existing approval. Nothing is paid out here
(BR-PAY-014). Any refusal on the way — a release larger than what is held, a
ledger that cannot post — refuses the whole cancel: the account stays open and
nothing is written. No interest is added: the PO's figure is the $175.00 paid,
and the deposit was held for days.

⚖️ **MONEY THAT HAS NOT CLEARED IS CALLED OFF, NOT REFUNDED (`DEF-CUS-9789`,
2026-10-06).** The wizard records every counter payment as `processing`, and a
release or refund counts CLEARED money only (`deposit_release.deposit_still_held`,
decision log 2026-10-06 *"WHICH READ COUNTS A PROCESSING DEPOSIT"*): a refund
must never pay out money that has not arrived. So until this fix a cancel the
same day closed the account and refunded NOTHING, and the cheque stayed in the
drawer against a closed account. Now each payment of the account still
`processing` is CANCELLED through payments' existing Cancel — the act a clerk
presses on the payment itself, which writes the original's status move and a
−amount reversing row, posts nothing (a processing payment never posted) and
audits both rows. The cheque is simply not banked; the card is not captured.
Cleared money is released and refunded exactly as before. Worked (M1): Avery
paid **$175.00 by cheque 2041** ($150.00 deposit + $25.00 connection), not
cleared; Cancel calls off both payments, refunds **$0.00**, releases nothing and
closes the account. **Every** processing payment of the account is called off,
not only the wizard's: the account exists because of this move-in and no bill
has issued (the cancel is refused after one), so any uncleared money on it is
money for a tenancy that never ran. A payment payments' Cancel would refuse
refuses the WHOLE cancel before anything is written (`paymentNotCallable`).

⚠ **PREVIEW FIRST.** J6: *"The confirm modal lists exactly those four lines
before the clerk presses."* `preview(ref)` answers the lines and any refusal
WITHOUT writing, so the modal never promises what the press would refuse.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

from apps.customers import models, move_in_jobs, moves, seams

#: `move_in_jobs.closed_reason` for a job a clerk called off.
CLOSED_BY_CANCEL = "move_in_cancelled"
#: Why a released deposit stopped being held — `deposit_releases.reason`.
RELEASE_REASON = "move_in_cancelled"

KIND_NOT_STARTED = "not_started"
KIND_COMMITTED = "committed"

#: Refusal codes, each with its catalogue key. Named beside the door.
BILL_ISSUED = "move_in_cancel_bill_issued"
BILLING_UNREADABLE = "move_in_cancel_billing_unreadable"
ALREADY_CANCELLED = "move_in_already_cancelled"
NOT_OCCUPYING = "move_in_cancel_account_not_live"
NOT_CANCELLABLE = "move_in_cancel_not_cancellable"
PAYMENT_NOT_CALLABLE = "move_in_cancel_payment_not_callable"
#: payments' cancel reason for money a move-in took and no longer needs.
CALL_OFF_REASON = "not_taken"

_ZERO = Decimal("0")


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _refuse(code: str, key: str, **params: Any) -> None:
    raise errors.BizError(
        errors.BIZ_STATE,
        br_ref="CR-171-BRC10",
        message_key=f"customers.moveIn.cancel.{key}",
        params={"code": code, **params},
    )


# ═══════════════════════════════════════════════════════════════════════════
# 1 · WHICH MOVE-IN, AND IS IT ALREADY CANCELLED
# ═══════════════════════════════════════════════════════════════════════════
def is_cancelled(account: Any) -> bool:
    """A committed move-in is Cancelled when its account closed BEFORE the day
    it opened (see the module docstring). One predicate, so the list, the
    details view and this door cannot disagree."""
    opened = getattr(account, "opened_at", None)
    closed = getattr(account, "closed_at", None)
    return opened is not None and closed is not None and closed < opened


def reopening_for(record: Any) -> Any:
    """The `move_in_reopenings` row when this move-in REOPENED an account
    (CR-181-BRC10), or None. Written once at Complete and never updated, so it
    is the durable record of the tenancy the reopen replaced on the account
    row: its `previous_opened_at` / `previous_closed_at`."""
    from apps.customers.move_in_reopen_models import MoveInReopening

    record_id = getattr(record, "id", None)
    if record_id is None:
        return None
    return MoveInReopening.objects.filter(tenant_id=_tenant_id(), move_record_id=record_id).first()


def record_is_cancelled(record: Any, account: Any, *, reopening: Any = None) -> bool:
    """`is_cancelled` for ONE committed move-in, which is what the list, the
    details view and the doors ask (`DEF-CUS-10126`).

    For a move-in that opened a NEW account it is exactly `is_cancelled`. For a
    move-in that REOPENED an account, cancelling it gives the account back its
    earlier tenancy — closed on the day that tenancy really ended — so the
    account no longer closes before it opened. What marks the move-in as
    Cancelled then is that the account closed BEFORE THIS MOVE-IN'S DAY: a
    reopen is refused unless the move-in starts after the earlier close
    (`move_in_reopen.check`), so a reopened move-in that ran can never carry a
    close before its own start."""
    if account is None:
        return False
    if is_cancelled(account):
        return True
    closed = getattr(account, "closed_at", None)
    if closed is None:
        return False
    if reopening is None:
        reopening = reopening_for(record)
    if reopening is None:
        return False
    return closed < record.effective_on


def _resolve(ref: str, *, lock: bool = False) -> tuple[str, Any]:
    """`(kind, row)` for a move-in reference — the move record first, then a
    pending job, the order `move_record_reads.record_detail` reads them in.
    A draft is not cancelled here: it has *Discard draft* (image 12)."""
    key = (ref or "").strip()
    if not key:
        raise errors.deny_as_not_found("BR-CUS-150")
    tenant_id = _tenant_id()
    record = moves.MoveRecord.objects.filter(
        tenant_id=tenant_id, move_no__iexact=key, kind=moves.KIND_MOVE_IN
    ).first()
    if record is not None:
        return KIND_COMMITTED, record
    jobs = move_in_jobs.MoveInJob.objects.filter(tenant_id=tenant_id, move_no__iexact=key)
    if lock:
        jobs = jobs.select_for_update()
    job = jobs.order_by("-created_at").first()
    if job is not None:
        return KIND_NOT_STARTED, job
    raise errors.deny_as_not_found("BR-CUS-150")


def _account(record: Any, *, lock: bool = False) -> models.Account:
    qs = models.Account.objects.filter(tenant_id=_tenant_id(), id=record.account_id)
    if lock:
        qs = qs.select_for_update()
    account = qs.select_related("status").first()
    if account is None:  # pragma: no cover - PROTECT keeps it
        raise errors.deny_as_not_found("BR-CUS-150")
    return account


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHAT A CANCEL WOULD DO — read, never write (the confirm modal)
# ═══════════════════════════════════════════════════════════════════════════
def _open_orders(move_no: str | None) -> list[dict[str, Any]]:
    """The move-in's work orders still to do — `{id, order_no}` each.

    Read through WORK's published flow seam (`orders_from_flow_queryset`,
    resolved by name: customers imports neither Work nor metering's model), and
    narrowed to what a cancel can still call off: not completed, not already
    cancelled on either axis (`state` or the dispatcher's `dispatch_state`).
    The `id` is used to call Work's own door and is never served (B14 rule 31).
    """
    if not move_no:
        return []
    fn = seams.resolve("work", "orders_from_flow_queryset", kind="seams.metering_seam")
    if fn is None:
        return []
    rows = (
        fn("move_in", move_no)
        .exclude(state__in=("completed", "cancelled"))
        .exclude(dispatch_state="cancelled")
        .order_by("order_no", "id")
        .values("id", "order_no")
    )
    return [{"id": row["id"], "order_no": row["order_no"]} for row in rows]


def _refundable_credit(account_id: Any) -> Decimal | None:
    fn = seams.resolve("payments", "refundable_position", kind="credit")
    if fn is None:
        return None
    balance = fn(account_id).balance
    return balance if balance > _ZERO else _ZERO


def _uncleared(account_id: Any) -> tuple[dict[str, Any], ...] | None:
    """The account's payments still `processing` (`DEF-CUS-9789`), each with
    payments' own Cancel refusal, or None when payments cannot be asked."""
    fn = seams.resolve("payments", "uncleared_payments_for_account", kind="cancel")
    return None if fn is None else fn(account_id)


def _called_off_line(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "payment_no": row.get("payment_no"),
        "amount": f"{Decimal(row['amount']):.4f}",
        "currency": row.get("currency"),
        "purpose": row.get("purpose"),
        "confirmation": row.get("confirmation"),
    }


def _deposit_held(account: models.Account) -> Decimal:
    """The customer register's held deposit — what a cancel releases."""
    return Decimal(account.deposit_on_file or 0)


def _refusal_for_committed(record: Any, account: models.Account) -> dict[str, Any] | None:
    """The first reason this committed move-in cannot be cancelled, or None."""
    reopening = reopening_for(record)
    if record_is_cancelled(record, account, reopening=reopening):
        return {"code": ALREADY_CANCELLED, "message_key": "customers.moveIn.cancel.alreadyCancelled"}
    from apps.customers import services

    if not services.is_occupying(account.status) and account.status.code != (
        services.PENDING_STATUS_CODE
    ):
        return {"code": NOT_OCCUPYING, "message_key": "customers.moveIn.cancel.accountNotLive"}
    last_bill = seams.last_issued_invoice_date(account.id)
    if last_bill is not None and (
        # `DEF-CUS-10126` — a REOPENED account carries the earlier tenancy's
        # issued bills, and those are not this move-in's. Only a bill issued
        # on or after this move-in's start belongs to it (J6's refusal); an
        # unreadable date refuses (fail closed).
        reopening is None
        or _as_day(last_bill) is None
        or _as_day(last_bill) >= _move_in_day(record, account)
    ):
        return {"code": BILL_ISSUED, "message_key": "customers.moveIn.cancel.billIssued"}
    if not seams.billing_can_answer():
        return {
            "code": BILLING_UNREADABLE,
            "message_key": "customers.moveIn.cancel.billingUnreadable",
        }
    uncleared = _uncleared(account.id)
    if uncleared is None or any(row.get("refusal") for row in uncleared):
        # Payments cannot be asked, or holds a processing payment its own Cancel
        # refuses: calling the rest off would leave that one in the drawer
        # against a closed account. Refused BEFORE anything is written.
        return {
            "code": PAYMENT_NOT_CALLABLE,
            "message_key": "customers.moveIn.cancel.paymentNotCallable",
        }
    return None


def _as_day(value: Any) -> Any:
    """A date from a date, a datetime or an ISO string; None when unreadable."""
    from datetime import date as _date
    from datetime import datetime as _datetime

    if isinstance(value, _datetime):
        return value.date()
    if isinstance(value, _date):
        return value
    try:
        return _date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def _move_in_day(record: Any, account: models.Account) -> Any:
    """The day this move-in started: the account's start, which *Change
    move-in date* moves (`DEF-CUS-9790`), else the record's own date."""
    return account.opened_at or record.effective_on


def _restored_dates(record: Any, account: models.Account, reopening: Any) -> dict[str, Any]:
    """What the account's dates become on cancel. A NEW account closes the day
    before the move-in (the module docstring); a REOPENED one gets back the
    earlier tenancy it had before the reopen (`DEF-CUS-10126`), read from
    `move_in_reopenings` — the row written for exactly that, never pruned the
    way the `account.reopened` audit row is (hard rule 4's note on
    `audit_log` retention)."""
    if reopening is not None:
        return {
            "opened_at": reopening.previous_opened_at,
            "closed_at": reopening.previous_closed_at,
            "restored": True,
        }
    return {
        "opened_at": account.opened_at,
        "closed_at": _move_in_day(record, account) - timedelta(days=1),
        "restored": False,
    }


def preview(ref: str) -> dict[str, Any]:
    """What pressing *Cancel move-in* would do — J6's lines — and whether it
    may. Nothing is written."""
    kind, row = _resolve(ref)
    if kind == KIND_NOT_STARTED:
        refusal = None
        if row.state != move_in_jobs.STATE_PENDING:
            refusal = (
                {"code": ALREADY_CANCELLED, "message_key": "customers.moveIn.cancel.alreadyCancelled"}
                if row.state == move_in_jobs.STATE_CANCELLED
                else {"code": NOT_CANCELLABLE, "message_key": "customers.moveIn.cancel.notCancellable"}
            )
        return {
            "kind": kind,
            "move_no": row.move_no,
            "allowed": refusal is None,
            "refusal": refusal,
            "reverses": {"job": "cancelled"},
        }
    account = _account(row)
    refusal = _refusal_for_committed(row, account)
    credit = _refundable_credit(account.id)
    deposit = _deposit_held(account)
    # The ONE refund the press would request: today's credit PLUS the deposit
    # it releases (`OQ-CUS-12790` (a)) — e.g. $25.00 + $150.00 = $175.00.
    refund_amount = None if credit is None else credit + deposit
    return {
        "kind": kind,
        "move_no": row.move_no,
        "allowed": refusal is None,
        "refusal": refusal,
        "reverses": {
            "account": {
                "account_no": account.account_no,
                # `DEF-CUS-10126` — a reopened account closes on its EARLIER
                # tenancy's own date, not the day before this move-in.
                "closes_on": str(_restored_dates(row, account, reopening_for(row))["closed_at"]),
            },
            "refund": {
                "amount": None if refund_amount is None else f"{refund_amount:.4f}",
                "currency": seams.tenant_currency(),
                "deposit_released": f"{deposit:.4f}",
            },
            # `DEF-CUS-9789` — each uncleared payment the press calls off.
            "called_off": [_called_off_line(p) for p in (_uncleared(account.id) or ())],
            "work_orders": [row_["order_no"] for row_ in _open_orders(row.move_no)],
            "reads_kept": int(row.reads_committed or 0),
            "unit_after": "vacant",
        },
    }


def _release_deposit(
    actor: Any, account: models.Account, record: Any, deposit: Decimal, released_on: Any
) -> dict[str, Any]:
    """`OQ-CUS-12790` (a): the held deposit becomes credit — payments writes the
    release and its books entry, customers moves its own register. Inside the
    cancel's transaction; any refusal from either side propagates and the whole
    cancel rolls back (nothing is caught here, so nothing is half-written)."""
    from apps.customers import services

    release = seams.resolve("payments", "release_to_credit", kind="deposit_release")
    if release is None:  # pragma: no cover - payments always publishes it
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="CR-171-BRC10",
            message_key="customers.moveIn.cancel.refundUnavailable",
        )
    result = release(
        actor,
        account_id=account.id,
        amount=deposit,
        reason=RELEASE_REASON,
        source_type="move_record",
        source_id=record.id,
        released_on=released_on,
        posted_at=timezone.now(),
        idempotency_key=f"move-in-cancel-deposit:{record.id}",
    )
    services.record_deposit_movement(account.id, deposit, actor=actor, released=True)
    return {
        "amount": f"{deposit:.4f}",
        "currency": result.currency,
        "release_id": result.release_id,
    }


def _call_off_uncleared(actor: Any, account: models.Account, record: Any) -> list[dict[str, Any]]:
    """Cancel every processing payment of the account through payments' own
    `cancel_payment` (`DEF-CUS-9789`). `_refusal_for_committed` has already
    refused the cancel if any of them would be refused, so nothing here is
    caught: an unexpected refusal rolls the whole cancel back."""
    rows = _uncleared(account.id) or ()
    if not rows:
        return []
    cancel_payment = seams.resolve("payments", "cancel_payment", kind="cancel")
    if cancel_payment is None:  # pragma: no cover - payments always publishes it
        _refuse(PAYMENT_NOT_CALLABLE, "paymentNotCallable")
    # The tenant's own moment (BR-TEN-043): its DATE dates the reversing row's
    # PMT- number, so it is the utility's day, not UTC's.
    moment = timezone.localtime(timezone.now(), seams.tenant_timezone())
    out: list[dict[str, Any]] = []
    for row in rows:
        result = cancel_payment(
            actor=actor,
            payment_id=row["payment_id"],
            reason=CALL_OFF_REASON,
            cancelled_on=moment,
            note=f"Move-in {record.move_no or ''} cancelled".strip(),
        )
        out.append({**_called_off_line(row), "reversing_payment_no": result.reversing_payment_no})
    return out


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE DOOR
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def cancel(
    actor: Any,
    ref: str,
    *,
    note: str | None = None,
    refund_method: str | None = None,
) -> dict[str, Any]:
    """Cancel one move-in. Returns what was reversed, in J6's order."""
    kind, _row = _resolve(ref)
    if kind == KIND_NOT_STARTED:
        return _cancel_job(actor, ref, note=note)
    return _cancel_committed(actor, ref, note=note, refund_method=refund_method)


def _cancel_job(actor: Any, ref: str, *, note: str | None) -> dict[str, Any]:
    from core import audit as core_audit

    with transaction.atomic():
        _kind, job = _resolve(ref, lock=True)
        if job.state == move_in_jobs.STATE_CANCELLED:
            _refuse(ALREADY_CANCELLED, "alreadyCancelled")
        if job.state != move_in_jobs.STATE_PENDING:
            _refuse(NOT_CANCELLABLE, "notCancellable", state=job.state)
        now = timezone.now()
        before = {"state": job.state}
        job.state = move_in_jobs.STATE_CANCELLED
        job.closed_at = now
        job.closed_reason = CLOSED_BY_CANCEL
        job.updated_at = now
        job.save(update_fields=["state", "closed_at", "closed_reason", "updated_at"])
        core_audit.write_row(
            action="move_in_job.cancelled",
            entity_type="move_in_job",
            entity_id=job.id,
            actor_user_id=getattr(actor, "id", None) or getattr(actor, "pk", None),
            before=before,
            after={"state": job.state, "move_no": job.move_no, "note": (note or None)},
        )
    return {
        "kind": KIND_NOT_STARTED,
        "move_no": job.move_no,
        "status": "cancelled",
        "job": {"state": job.state, "closed_reason": job.closed_reason},
    }


def _cancel_committed(
    actor: Any, ref: str, *, note: str | None, refund_method: str | None
) -> dict[str, Any]:
    from apps.customers import services

    method = (refund_method or "check").strip().lower()
    with transaction.atomic():
        _kind, record = _resolve(ref)
        account = _account(record, lock=True)
        refusal = _refusal_for_committed(record, account)
        if refusal is not None:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="CR-171-BRC10",
                message_key=refusal["message_key"],
                params={k: v for k, v in refusal.items() if k != "message_key"},
            )
        # The move-in's own agreements end the day before it started, either way.
        ended_on = _move_in_day(record, account) - timedelta(days=1)
        dates = _restored_dates(record, account, reopening_for(record))
        before = {
            "status": account.status.code,
            "opened_at": None if account.opened_at is None else str(account.opened_at),
            "closed_at": None if account.closed_at is None else str(account.closed_at),
            "close_reason": account.close_reason,
        }
        account.status = services._default_closed_status()
        account.opened_at = dates["opened_at"]
        account.closed_at = dates["closed_at"]
        if not dates["restored"]:
            # A reopened account keeps the close reason of the tenancy it gets
            # back — the reopen never changed it (`move_in_reopen.REOPEN_COLUMNS`).
            account.close_reason = models.CLOSE_REASON_OTHER
        account.save(
            update_fields=["status", "opened_at", "closed_at", "close_reason", "updated_at"]
        )
        agreements = services._end_service_agreements(account, ended_on)

        # ── MONEY NOT YET ARRIVED: called off, never refunded (`DEF-CUS-9789`)
        # Through payments' own Cancel — the act a clerk presses on the payment:
        # status move + a −amount reversing row, both audited, nothing posted.
        # Inside this transaction (its own atomic is a SAVEPOINT); a refusal
        # propagates and the whole cancel rolls back.
        called_off = _call_off_uncleared(actor, account, record)

        # ── THE DEPOSIT: released to credit, `OQ-CUS-12790` (a) ─────────────
        released: dict[str, Any] | None = None
        deposit = _deposit_held(account)
        if deposit > _ZERO:
            # The books entry is dated TODAY (the tenant's day, BR-TEN-043) — the act
            # happens now; the account's close date is history it does not move.
            released = _release_deposit(actor, account, record, deposit, seams.tenant_today())

        # ── THE MONEY: ONE refund REQUEST for the whole credit, never a payout
        # (BR-PAY-014) — the deposit just released is part of it.
        refund: dict[str, Any] | None = None
        credit = _refundable_credit(account.id)
        if credit is not None and credit > _ZERO:
            request_refund = seams.resolve("payments", "request_refund", kind="refunds")
            if request_refund is None:  # pragma: no cover - payments always publishes it
                raise errors.BizError(
                    errors.BIZ_COMPLETENESS,
                    br_ref="CR-171-BRC10",
                    message_key="customers.moveIn.cancel.refundUnavailable",
                )
            result = request_refund(
                actor,
                account_id=account.id,
                amount=credit,
                method=method,
                requested_at=timezone.now(),
                reason="move_in_cancelled",
                memo=f"Move-in {record.move_no or ''} cancelled".strip(),
                idempotency_key=f"move-in-cancel:{record.id}",
            )
            refund = {
                "refund_id": result.refund_id,
                "amount": f"{credit:.4f}",
                "currency": result.currency,
                "method": method,
                "status": result.status,
            }

        services._audit(
            actor,
            "account.move_in_cancelled",
            account.id,
            before=before,
            after={
                "status": account.status.code,
                "opened_at": None if account.opened_at is None else str(account.opened_at),
                "closed_at": str(account.closed_at),
                "close_reason": account.close_reason,
                # `DEF-CUS-10126` — True when the account got its earlier
                # tenancy back instead of closing the day before the move-in.
                "restored_previous_tenancy": dates["restored"],
                "move_no": record.move_no,
                "agreements_ended": len(agreements),
                "called_off": called_off,
                "deposit_released": released,
                "refund": refund,
                "note": note or None,
            },
        )

    # ── WORK: after the commit, BR-WRK-055's posture — a field module that
    # cannot cancel a visit never un-cancels the account. Each order goes
    # through Work's own door, which writes its own audit row.
    cancelled_orders: list[str] = []
    warnings: list[dict[str, Any]] = []
    cancel_order = seams.resolve("work", "set_dispatch_state", kind="dispatch")
    for order in _open_orders(record.move_no):
        if cancel_order is None:
            warnings.append({"code": "work_orders_not_cancelled", "order_no": order["order_no"]})
            continue
        try:
            with transaction.atomic():  # a SAVEPOINT — hard-won law 14
                cancel_order(actor, order["id"], "cancelled", "work.order.cancelled")
            cancelled_orders.append(order["order_no"])
        except Exception:  # noqa: BLE001 - one fact to the clerk: this one did not cancel
            warnings.append({"code": "work_orders_not_cancelled", "order_no": order["order_no"]})
    return {
        "kind": KIND_COMMITTED,
        "move_no": record.move_no,
        "status": "cancelled",
        "account": {
            "account_no": account.account_no,
            "status": account.status.code,
            "opened_at": None if account.opened_at is None else str(account.opened_at),
            "closed_at": str(account.closed_at),
            "restored_previous_tenancy": dates["restored"],
        },
        "agreements_ended": len(agreements),
        "called_off": called_off,
        "deposit_released": released,
        "refund": refund,
        "work_orders_cancelled": cancelled_orders,
        "reads_kept": int(record.reads_committed or 0),
        "unit": "vacant",
        "warnings": warnings,
    }

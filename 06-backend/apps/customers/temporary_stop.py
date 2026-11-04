# ── Trace ──────────────────────────────────────────────
# Change:   CR-183-BRC10 — temporary stop (PO rulings B1–B4, 2026-10-14).
# Rules:    BR-CUS-1120 (B1 base charge only during the hold · B2 field visit
#           optional, ticked on approval · B4 the customer may end it early) ·
#           BR-CUS-1121 (B3 at least `temporary_stop_min_days`, at most
#           `temporary_stop_max_months` — S66 settings, defaults 10 and 12) ·
#           BR-CUS-055 (`vacation_hold` is class `billable_base_only`) ·
#           BR-CWP-026 (a portal form creates work and never changes an account
#           — the hold starts only on a clerk's approval) · BR-WRK-055 (a field
#           job that cannot be raised never fails the act that asked for it) ·
#           CLAUDE.md hard rules 1 (tenant scoped), 7 (audit every change)
# Tests:    06-backend/tests/test_cr183_temporary_stop.py
# ───────────────────────────────────────────────────────
"""**The one writer of `temporary_stops`, and the account status a hold moves.**

WHAT A TEMPORARY STOP IS (decision log 2026-10-14, *"TEMPORARY STOP — FOUR PO
RULINGS (B1–B4)"*): the customer is away, the account STAYS OPEN, and from the
stop date to the restart date the account is on `vacation_hold` — BR-CUS-055's
`billable_base_only` class, so the bill carries the base (standing) charge and
no usage (B1). Nothing else on the account moves: no service agreement ends, no
deposit is settled, no meter is removed.

THE FOUR DOORS
--------------
* **Portal ask** (`record_from_portal`) — the customer's *stop my service*
  request is stored with its account and dates (`requested`). It changes no
  account: a clerk decides (BR-CWP-026).
* **Approve** (`approve_request`) — the clerk's decision on that ask, or on a
  *Restart my service now* ask (B4). Refused by name outside the limits (B3).
* **Counter** (`start_from_account`) — a clerk starts one for a customer on the
  phone or at the desk; the clerk is the approver, so it starts `scheduled`.
* **Change / end** (`change_dates`, `end_now`) — move the dates, or end it today.

THE CLOCK
---------
The account moves on the stop date and back on the restart date through
`apply_due(as_of)`, which `temporary_stop_schedule` runs daily per utility. An
approval or a counter stop dated today moves it at once through the same
function. **Idempotent by status**: a hold already `on_hold` is not started
twice and an `ended` one is not ended twice, so a second firing on the same day
writes nothing.
"""

from __future__ import annotations

import calendar
import logging
from datetime import date
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.customers import models, seams
from apps.customers.temporary_stop_models import (
    CHANNEL_PORTAL,
    CHANNEL_STAFF,
    LIVE_STATUSES,
    STATUS_CANCELLED,
    STATUS_ENDED,
    STATUS_ON_HOLD,
    STATUS_REFUSED,
    STATUS_REQUESTED,
    STATUS_SCHEDULED,
    TemporaryStop,
)
from core import audit as core_audit
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

logger = logging.getLogger("smartbillhub.customers.temporary_stop")

BR_STOP = "BR-CUS-1120"
BR_LIMITS = "BR-CUS-1121"

#: The two request TYPES a temporary stop adds (`service_requests.outcome` once
#: approved; the classification a clerk sees from the moment it arrives).
KIND_TEMPORARY_STOP = "temporary_stop"
KIND_RESTART_NOW = "restart_now"
KINDS: tuple[str, ...] = (KIND_TEMPORARY_STOP, KIND_RESTART_NOW)

#: The S66 settings (`tenancy.settings_families.BILLING_DEFAULTS`) and the
#: ruled defaults an unreadable settings row answers.
SETTING_MIN_DAYS = "temporary_stop_min_days"
SETTING_MAX_MONTHS = "temporary_stop_max_months"
DEFAULT_MIN_DAYS = 10
DEFAULT_MAX_MONTHS = 12

#: The account statuses a hold moves between, by CODE (BR-CUS-055 seeds both;
#: `services._seeded_status` refuses when a tenant has lost one).
STATUS_CODE_HOLD = "vacation_hold"
STATUS_CODE_ACTIVE = "active"
#: A hold may start only on an account in this class (an active account).
CLASS_BILLABLE = "billable"

#: The refusal keys (G32 — each is in all eleven catalogues).
_K = "customers.temporaryStop."
KEY_RESTART_REQUIRED = _K + "restartRequired"
KEY_RESTART_BEFORE_STOP = _K + "restartBeforeStop"
KEY_TOO_SHORT = _K + "tooShort"
KEY_TOO_LONG = _K + "tooLong"
KEY_STOP_IN_PAST = _K + "stopInPast"
KEY_ALREADY_ON_HOLD = _K + "alreadyOnHold"
KEY_ACCOUNT_NOT_ACTIVE = _K + "accountNotActive"
KEY_NOT_A_STOP = _K + "notTemporaryStop"
KEY_NOT_ON_HOLD = _K + "notOnHold"
KEY_RESTART_ASKED = _K + "restartAlreadyAsked"
KEY_NOT_LIVE = _K + "notLive"
KEY_USE_OWN_APPROVAL = _K + "useItsOwnApproval"
KEY_DECIDE_STATE = "customers.serviceRequest.decideUnderReviewOnly"

#: What a temporary stop bills while it lasts — B1, served as a CODE.
BILLED_DURING_HOLD = "base_only"


# ═══════════════════════════════════════════════════════════════════════════
# plumbing
# ═══════════════════════════════════════════════════════════════════════════
def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _audit(actor: Any, action: str, entity_type: str, entity_id: Any, **kw: Any) -> None:
    """CLAUDE.md rule 7 — every change a hold makes, who and before → after."""
    core_audit.write_row(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        actor_user_id=core_audit.actor_user_id(actor),
        before=kw.get("before"),
        after=kw.get("after"),
    )


def _day(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            br_ref=BR_STOP,
            message_key="customers.temporaryStop.dateFormat",
            field_errors=[{"field": "stop_from", "code": errors.VAL_FORMAT}],
        ) from None


def today() -> date:
    return seams.tenant_today()


def _months_after(day: date, months: int) -> date:
    """`day` plus `months` calendar months; the 31st lands on the month's last day."""
    month_index = day.month - 1 + months
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


# ═══════════════════════════════════════════════════════════════════════════
# THE LIMITS (B3)
# ═══════════════════════════════════════════════════════════════════════════
def limits() -> dict[str, int]:
    """The two S66 settings, through tenancy's own selector (B1 boundary).
    An unreadable row answers the PO's figures rather than no limit."""
    reader = seams.resolve("tenancy", "settings_family", kind="selectors")
    values = (reader("billing-defaults") or {}) if reader is not None else {}

    def _int(key: str, default: int) -> int:
        try:
            return int(values.get(key)) if values.get(key) is not None else default
        except (TypeError, ValueError):  # pragma: no cover - the family validates it
            return default

    return {
        "min_days": _int(SETTING_MIN_DAYS, DEFAULT_MIN_DAYS),
        "max_months": _int(SETTING_MAX_MONTHS, DEFAULT_MAX_MONTHS),
    }


def date_problems(
    stop_from: date | None,
    restart_on: date | None,
    *,
    on: date | None = None,
    started: bool = False,
) -> list[dict[str, Any]]:
    """Every reason these dates cannot be approved — `[]` when they can.

    ONE list for the Approve window (which draws them before the press) and for
    the refusal (which raises the first) — so the window and the server cannot
    disagree. `started=True` is a hold already on: its stop date is history and
    is not asked to be in the future.
    """
    found: list[dict[str, Any]] = []
    rule = limits()
    on = on or today()
    if stop_from is None:
        found.append({"code": "stop_required", "message_key": KEY_RESTART_REQUIRED, "params": {}})
        return found
    if not started and stop_from < on:
        found.append({"code": "stop_in_past", "message_key": KEY_STOP_IN_PAST, "params": {}})
    if restart_on is None:
        found.append(
            {"code": "restart_required", "message_key": KEY_RESTART_REQUIRED, "params": {}}
        )
        return found
    if restart_on <= stop_from:
        found.append(
            {"code": "restart_before_stop", "message_key": KEY_RESTART_BEFORE_STOP, "params": {}}
        )
        return found
    days = (restart_on - stop_from).days
    if days < rule["min_days"]:
        found.append(
            {
                "code": "too_short",
                "message_key": KEY_TOO_SHORT,
                "params": {"min_days": rule["min_days"], "days": days},
            }
        )
    if restart_on > _months_after(stop_from, rule["max_months"]):
        found.append(
            {
                "code": "too_long",
                "message_key": KEY_TOO_LONG,
                "params": {"max_months": rule["max_months"], "days": days},
            }
        )
    return found


def _refuse_dates(problems: list[dict[str, Any]]) -> None:
    if not problems:
        return
    first = problems[0]
    raise errors.BizError(
        errors.BIZ_WINDOW,
        br_ref=BR_LIMITS,
        message_key=first["message_key"],
        params={**first["params"], "problem": first["code"]},
    )


# ═══════════════════════════════════════════════════════════════════════════
# reads
# ═══════════════════════════════════════════════════════════════════════════
def _account(account_id: Any, *, lock: bool = False) -> models.Account:
    qs = models.Account.objects.select_related("status").filter(
        tenant_id=_tenant_id(), id=account_id
    )
    if lock:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _stop(stop_id: Any, *, lock: bool = False) -> TemporaryStop:
    qs = TemporaryStop.objects.filter(tenant_id=_tenant_id(), id=stop_id)
    if lock:
        qs = qs.select_for_update()
    row = qs.first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def kind_of(request: Any) -> str | None:
    """`temporary_stop`, `restart_now` or None — what this request IS.

    Read from the ROW the ask wrote, never from its sentence. A request already
    approved carries the same word in `outcome`.
    """
    request_id = getattr(request, "id", request)
    rows = TemporaryStop.objects.filter(tenant_id=_tenant_id())
    if rows.filter(request_id=request_id).exists():
        return KIND_TEMPORARY_STOP
    if rows.filter(restart_request_id=request_id).exists():
        return KIND_RESTART_NOW
    return None


def kinds_for(request_ids: list[Any]) -> dict[str, str]:
    """`kind_of` for a page of requests in two queries (the Requests list)."""
    ids = [str(value) for value in request_ids]
    found: dict[str, str] = {}
    rows = TemporaryStop.objects.filter(tenant_id=_tenant_id())
    for value in rows.filter(request_id__in=ids).values_list("request_id", flat=True):
        found[str(value)] = KIND_TEMPORARY_STOP
    for value in rows.filter(restart_request_id__in=ids).values_list(
        "restart_request_id", flat=True
    ):
        found[str(value)] = KIND_RESTART_NOW
    return found


def view(stop: TemporaryStop) -> dict[str, Any]:
    """One hold, as every screen reads it. Numbers, never ids, are what a screen
    PRINTS (B14 rule 31); the ids ride for the controls."""
    request = stop.request
    restart = stop.restart_request
    days = (stop.restart_on - stop.stop_from).days if stop.restart_on else None
    return {
        "id": str(stop.id),
        "account_id": str(stop.account_id),
        "account_no": stop.account.account_no,
        "status": stop.status,
        "channel": stop.channel,
        "stop_from": stop.stop_from.isoformat(),
        "restart_on": stop.restart_on.isoformat() if stop.restart_on else None,
        "days": days,
        "reason": stop.reason,
        "field_visit_needed": stop.field_visit_needed,
        "shutoff_order_no": stop.shutoff_order_no,
        "turnon_order_no": stop.turnon_order_no,
        "ended_early": stop.ended_early,
        "billed_during_hold": BILLED_DURING_HOLD,
        "request_no": request.request_no if request else None,
        "request_id": str(request.id) if request else None,
        "restart_request_no": restart.request_no if restart else None,
        "restart_request_id": str(restart.id) if restart else None,
        "restart_request_state": restart.state if restart else None,
    }


def live_for_account(account_id: Any) -> TemporaryStop | None:
    """The scheduled or running hold on this account, or None."""
    return (
        TemporaryStop.objects.select_related("account", "request", "restart_request")
        .filter(tenant_id=_tenant_id(), account_id=account_id, status__in=LIVE_STATUSES)
        .order_by("stop_from")
        .first()
    )


def for_account(account_id: Any) -> dict[str, Any]:
    """The account page's card: the live hold (or None), the limits, and what a
    hold bills."""
    live = live_for_account(account_id)
    return {
        "current": view(live) if live else None,
        "limits": limits(),
        "billed_during_hold": BILLED_DURING_HOLD,
    }


def for_request(request: Any) -> dict[str, Any] | None:
    """The Approve window's facts for a temporary-stop or restart request, or
    None for any other request."""
    rows = TemporaryStop.objects.select_related("account", "request", "restart_request").filter(
        tenant_id=_tenant_id()
    )
    as_stop = rows.filter(request_id=request.id).first()
    if as_stop is not None:
        started = as_stop.status in (STATUS_ON_HOLD, STATUS_ENDED)
        return {
            "kind": KIND_TEMPORARY_STOP,
            "stop": view(as_stop),
            "limits": limits(),
            "problems": []
            if as_stop.status != STATUS_REQUESTED
            else date_problems(as_stop.stop_from, as_stop.restart_on, started=started)
            + _account_problems(as_stop.account, exclude=as_stop.id),
        }
    as_restart = rows.filter(restart_request_id=request.id).first()
    if as_restart is not None:
        problems = []
        if as_restart.status not in LIVE_STATUSES:
            problems.append({"code": "not_live", "message_key": KEY_NOT_LIVE, "params": {}})
        return {
            "kind": KIND_RESTART_NOW,
            "stop": view(as_restart),
            "limits": limits(),
            "restart_from": today().isoformat(),
            "problems": problems,
        }
    return None


def _account_problems(account: models.Account, *, exclude: Any = None) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if getattr(account.status, "behavior_class", None) != CLASS_BILLABLE:
        found.append(
            {
                "code": "account_not_active",
                "message_key": KEY_ACCOUNT_NOT_ACTIVE,
                "params": {"status": account.status.code},
            }
        )
    other = TemporaryStop.objects.filter(
        tenant_id=_tenant_id(), account_id=account.id, status__in=LIVE_STATUSES
    ).exclude(id=exclude)
    if other.exists():
        found.append({"code": "already_on_hold", "message_key": KEY_ALREADY_ON_HOLD, "params": {}})
    return found


def _refuse_account(account: models.Account, *, exclude: Any = None) -> None:
    problems = _account_problems(account, exclude=exclude)
    if problems:
        first = problems[0]
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR_STOP,
            message_key=first["message_key"],
            params={**first["params"], "problem": first["code"]},
        )


def hold_windows(account_id: Any, period_start: date, period_end: date) -> tuple[tuple[date, date], ...]:
    """The INCLUSIVE `(first day on hold, last day on hold)` pairs inside this
    period — billing's read (`billing.gather`, T5). A hold still running is
    clipped to `period_end`; one with no restart date runs to `period_end`."""
    rows = TemporaryStop.objects.filter(
        tenant_id=_tenant_id(),
        account_id=account_id,
        status__in=(STATUS_ON_HOLD, STATUS_ENDED),
        stop_from__lte=period_end,
    )
    windows: list[tuple[date, date]] = []
    for row in rows.order_by("stop_from"):
        last = period_end
        if row.restart_on is not None:
            last = min(period_end, date.fromordinal(row.restart_on.toordinal() - 1))
        first = max(period_start, row.stop_from)
        if first <= last:
            windows.append((first, last))
    return tuple(windows)


# ═══════════════════════════════════════════════════════════════════════════
# PORTAL — the ask is STORED; nothing on the account moves (BR-CWP-026)
# ═══════════════════════════════════════════════════════════════════════════
def record_from_portal(
    request_id: Any, *, account_id: Any, stop_from: Any, restart_on: Any, reason: Any = None
) -> TemporaryStop:
    """T1 — the portal ask's account, dates and reason, stored with the request.

    No limit is checked here: B3's limits are an APPROVAL rule, and refusing the
    ask at the door would leave the customer no request a clerk could answer.
    The clerk sees the ask, the dates and the verdict, and decides.
    """
    account = _account(account_id)
    stop = TemporaryStop.objects.create(
        tenant_id=_tenant_id(),
        account=account,
        request_id=request_id,
        channel=CHANNEL_PORTAL,
        status=STATUS_REQUESTED,
        stop_from=_day(stop_from),
        restart_on=_day(restart_on),
        reason=(str(reason).strip()[:2000] or None) if reason else None,
    )
    _audit(
        None,
        "temporary_stop.requested",
        "temporary_stop",
        stop.id,
        after={
            "account_no": account.account_no,
            "stop_from": stop.stop_from.isoformat(),
            "restart_on": stop.restart_on.isoformat() if stop.restart_on else None,
            "channel": CHANNEL_PORTAL,
        },
    )
    return stop


def on_request_refused(actor: Any, request: Any) -> None:
    """The clerk refused a temporary-stop ask: its hold is `refused` and can
    never be scheduled. A refused *Restart now* ask changes nothing on the
    hold — it stays on until its own restart date — and frees the button."""
    stop = (
        TemporaryStop.objects.select_for_update()
        .filter(tenant_id=_tenant_id(), request_id=request.id, status=STATUS_REQUESTED)
        .first()
    )
    if stop is None:
        return
    stop.status = STATUS_REFUSED
    stop.save(update_fields=["status", "updated_at"])
    _audit(actor, "temporary_stop.refused", "temporary_stop", stop.id,
           before={"status": STATUS_REQUESTED}, after={"status": STATUS_REFUSED})


def can_ask_restart(account_id: Any) -> dict[str, Any]:
    """Is *Restart my service now* lawful on this account? The portal button's
    answer and the restart ask's own guard — one function."""
    live = live_for_account(account_id)
    if live is None:
        return {"allowed": False, "reason": "not_on_hold", "stop": None}
    restart = live.restart_request
    if restart is not None and restart.state not in models.ServiceRequest.TERMINAL_STATES:
        return {"allowed": False, "reason": "restart_already_asked", "stop": live}
    return {"allowed": True, "reason": None, "stop": live}


def refuse_unless_restart_allowed(account_id: Any) -> TemporaryStop:
    verdict = can_ask_restart(account_id)
    if not verdict["allowed"]:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref=BR_STOP,
            message_key=KEY_NOT_ON_HOLD
            if verdict["reason"] == "not_on_hold"
            else KEY_RESTART_ASKED,
            params={"problem": verdict["reason"]},
        )
    return verdict["stop"]


def record_restart_from_portal(request_id: Any, *, account_id: Any) -> TemporaryStop:
    """B4 — the *Restart my service now* ask, linked to the hold it would end."""
    with transaction.atomic():
        live = refuse_unless_restart_allowed(account_id)
        live = _stop(live.id, lock=True)
        live.restart_request_id = request_id
        live.save(update_fields=["restart_request", "updated_at"])
        _audit(
            None,
            "temporary_stop.restart_requested",
            "temporary_stop",
            live.id,
            after={"restart_request_id": str(request_id)},
        )
    return live


# ═══════════════════════════════════════════════════════════════════════════
# APPROVE (T3) — the clerk's decision on either ask
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def approve_request(
    actor: Any,
    request_id: Any,
    *,
    stop_from: Any = None,
    restart_on: Any = None,
    field_visit_needed: bool = False,
    note: str | None = None,
) -> dict[str, Any]:
    """Approve a *Temporary stop* or a *Restart now* request.

    ⚠ **THE DATES MAY BE CHANGED IN THE WINDOW** — the clerk on the phone agrees
    a different date with the customer — and what is approved is what is
    checked: B3's limits are asked of the dates SENT, falling back to the
    customer's own. Outside them the approval is refused by name and nothing is
    written.

    The request moves `→ approved` through the module's one state door
    (`service_request_service._apply`), carrying the type as its `outcome`; the
    hold moves `requested → scheduled` (or ends, for a restart). Field work
    (B2) is raised AFTER the commit, so a work module that refuses never undoes
    an approval (BR-WRK-055).
    """
    from apps.customers import service_request as rules
    from apps.customers import service_request_service as srs

    stop_from_day = _day(stop_from)
    restart_day = _day(restart_on)
    warnings: list[dict[str, Any]] = []
    with transaction.atomic():
        request = srs.request_row(request_id, lock=True)
        if request.state not in rules.TRANSITIONS[rules.APPROVE][0]:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="CR-031",
                message_key=KEY_DECIDE_STATE,
                params={"state": request.state},
            )
        rows = TemporaryStop.objects.select_for_update().filter(tenant_id=_tenant_id())
        stop = rows.filter(request_id=request.id).first()
        kind = KIND_TEMPORARY_STOP
        if stop is None:
            stop = rows.filter(restart_request_id=request.id).first()
            kind = KIND_RESTART_NOW
        if stop is None:
            raise errors.BizError(
                errors.BIZ_STATE, br_ref=BR_STOP, message_key=KEY_NOT_A_STOP, params={}
            )
        on = today()
        if kind == KIND_TEMPORARY_STOP:
            if stop.status != STATUS_REQUESTED:
                raise errors.BizError(
                    errors.BIZ_STATE, br_ref=BR_STOP, message_key=KEY_NOT_LIVE, params={}
                )
            new_from = stop_from_day or stop.stop_from
            new_restart = restart_day or stop.restart_on
            _refuse_dates(date_problems(new_from, new_restart, on=on))
            account = _account(stop.account_id, lock=True)
            _refuse_account(account, exclude=stop.id)
            before = {
                "status": stop.status,
                "stop_from": stop.stop_from.isoformat(),
                "restart_on": stop.restart_on.isoformat() if stop.restart_on else None,
            }
            stop.stop_from = new_from
            stop.restart_on = new_restart
            stop.status = STATUS_SCHEDULED
            stop.field_visit_needed = bool(field_visit_needed)
            stop.approved_by_id = core_audit.actor_user_id(actor)
            stop.approved_at = timezone.now()
            stop.save()
            _audit(
                actor,
                "temporary_stop.approved",
                "temporary_stop",
                stop.id,
                before=before,
                after={
                    "status": STATUS_SCHEDULED,
                    "stop_from": new_from.isoformat(),
                    "restart_on": new_restart.isoformat(),
                    "field_visit_needed": stop.field_visit_needed,
                },
            )
        else:
            if stop.status not in LIVE_STATUSES:
                raise errors.BizError(
                    errors.BIZ_STATE, br_ref=BR_STOP, message_key=KEY_NOT_LIVE, params={}
                )
        request.outcome = kind
        request.decided_by_id = core_audit.actor_user_id(actor)
        request.decided_at = timezone.now()
        request.save(update_fields=["outcome", "decided_by", "decided_at", "updated_at"])
        srs._apply(
            actor,
            request.id,
            rules.APPROVE,
            reason=note,
            audit_action="service_request.approved",
        )
        if kind == KIND_RESTART_NOW:
            # B4 — *"billing returns to normal from that day"*: the hold ends
            # TODAY, whatever restart date it carried.
            _end_now_locked(actor, stop, on=on)
    if kind == KIND_TEMPORARY_STOP:
        if stop.stop_from <= on:
            apply_due(as_of=on, actor=actor, only=stop.id)
        if stop.field_visit_needed:
            warnings.extend(_raise_field_visits(actor, stop))
    stop.refresh_from_db()
    return {"stop": view(stop), "kind": kind, "warnings": warnings}


# ═══════════════════════════════════════════════════════════════════════════
# COUNTER (T7) — a clerk starts, moves or ends a hold
# ═══════════════════════════════════════════════════════════════════════════
@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def start_from_account(
    actor: Any,
    account_id: Any,
    *,
    stop_from: Any,
    restart_on: Any,
    reason: Any = None,
    field_visit_needed: bool = False,
) -> dict[str, Any]:
    """A clerk starts a temporary stop for a customer on the phone or at the
    counter. The same limits as an approval (B3); the clerk is the approver."""
    stop_day = _day(stop_from)
    restart_day = _day(restart_on)
    on = today()
    with transaction.atomic():
        _refuse_dates(date_problems(stop_day, restart_day, on=on))
        account = _account(account_id, lock=True)
        _refuse_account(account)
        stop = TemporaryStop.objects.create(
            tenant_id=_tenant_id(),
            account=account,
            channel=CHANNEL_STAFF,
            status=STATUS_SCHEDULED,
            stop_from=stop_day,
            restart_on=restart_day,
            reason=(str(reason).strip()[:2000] or None) if reason else None,
            field_visit_needed=bool(field_visit_needed),
            approved_by_id=core_audit.actor_user_id(actor),
            approved_at=timezone.now(),
        )
        _audit(
            actor,
            "temporary_stop.scheduled",
            "temporary_stop",
            stop.id,
            after={
                "account_no": account.account_no,
                "stop_from": stop_day.isoformat(),
                "restart_on": restart_day.isoformat(),
                "field_visit_needed": stop.field_visit_needed,
                "channel": CHANNEL_STAFF,
            },
        )
    warnings: list[dict[str, Any]] = []
    if stop.stop_from <= on:
        apply_due(as_of=on, actor=actor, only=stop.id)
    if stop.field_visit_needed:
        warnings.extend(_raise_field_visits(actor, stop))
    stop.refresh_from_db()
    return {"stop": view(stop), "warnings": warnings}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def change_dates(actor: Any, stop_id: Any, *, stop_from: Any = None, restart_on: Any = None) -> dict[str, Any]:
    """Move a hold's dates. A hold not yet started may move both; a hold already
    on may move only its restart date (its stop date has happened). B3's limits
    apply to the new pair. To end it TODAY use `end_now`."""
    on = today()
    with transaction.atomic():
        stop = _stop(stop_id, lock=True)
        if stop.status not in LIVE_STATUSES:
            raise errors.BizError(errors.BIZ_STATE, br_ref=BR_STOP, message_key=KEY_NOT_LIVE, params={})
        started = stop.status == STATUS_ON_HOLD
        new_from = stop.stop_from if started else (_day(stop_from) or stop.stop_from)
        new_restart = _day(restart_on) or stop.restart_on
        problems = date_problems(new_from, new_restart, on=on, started=started)
        if started and new_restart is not None and new_restart <= on:
            problems.insert(
                0, {"code": "restart_in_past", "message_key": KEY_STOP_IN_PAST, "params": {}}
            )
        _refuse_dates(problems)
        before = {
            "stop_from": stop.stop_from.isoformat(),
            "restart_on": stop.restart_on.isoformat() if stop.restart_on else None,
        }
        stop.stop_from = new_from
        stop.restart_on = new_restart
        stop.save(update_fields=["stop_from", "restart_on", "updated_at"])
        _audit(
            actor,
            "temporary_stop.dates_changed",
            "temporary_stop",
            stop.id,
            before=before,
            after={"stop_from": new_from.isoformat(), "restart_on": new_restart.isoformat()},
        )
    if stop.status == STATUS_SCHEDULED and stop.stop_from <= on:
        apply_due(as_of=on, actor=actor, only=stop.id)
    stop.refresh_from_db()
    return {"stop": view(stop)}


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def end_now(actor: Any, stop_id: Any) -> dict[str, Any]:
    """End a hold today — the clerk's *End now* (the customer rang). A hold not
    yet started is cancelled; one running ends and the account is active from
    today (B4's arithmetic, without a request)."""
    on = today()
    with transaction.atomic():
        stop = _stop(stop_id, lock=True)
        if stop.status not in LIVE_STATUSES:
            raise errors.BizError(errors.BIZ_STATE, br_ref=BR_STOP, message_key=KEY_NOT_LIVE, params={})
        _end_now_locked(actor, stop, on=on)
    stop.refresh_from_db()
    return {"stop": view(stop)}


def _end_now_locked(actor: Any, stop: TemporaryStop, *, on: date) -> None:
    """Inside the caller's transaction, with `stop` locked."""
    if stop.status == STATUS_SCHEDULED or stop.stop_from >= on:
        # Not started, or started TODAY: no day was spent on hold, so the hold
        # is cancelled rather than ended (a restart date on its stop date would
        # be a zero-day hold, which `ck_temporary_stops_restart_after_stop`
        # refuses).
        was_on_hold = stop.status == STATUS_ON_HOLD
        before = {"status": stop.status}
        stop.status = STATUS_CANCELLED
        stop.ended_at = timezone.now()
        stop.save(update_fields=["status", "ended_at", "updated_at"])
        _audit(actor, "temporary_stop.cancelled", "temporary_stop", stop.id, before=before,
               after={"status": STATUS_CANCELLED})
        if was_on_hold:
            _restore_account(actor, stop, on=on)
        return
    early = stop.restart_on is None or on < stop.restart_on
    before = {"restart_on": stop.restart_on.isoformat() if stop.restart_on else None}
    stop.restart_on = on
    stop.ended_early = early
    stop.save(update_fields=["restart_on", "ended_early", "updated_at"])
    _audit(actor, "temporary_stop.ended_early", "temporary_stop", stop.id, before=before,
           after={"restart_on": on.isoformat()})
    _finish(actor, stop, on=on)


# ═══════════════════════════════════════════════════════════════════════════
# THE CLOCK (T4)
# ═══════════════════════════════════════════════════════════════════════════
def apply_due(*, as_of: date | None = None, actor: Any = None, only: Any = None) -> dict[str, Any]:
    """Start every hold due by `as_of` and end every one due back by it.

    Each hold moves in its OWN transaction, so one account that refuses (a
    tenant that lost its `vacation_hold` row) does not hold up the rest; it is
    reported and left for the next firing. Idempotent by status.
    """
    on = as_of or today()
    started: list[str] = []
    ended: list[str] = []
    problems: list[dict[str, Any]] = []
    base = TemporaryStop.objects.filter(tenant_id=_tenant_id())
    if only is not None:
        base = base.filter(id=only)
    due_start = list(
        base.filter(status=STATUS_SCHEDULED, stop_from__lte=on).values_list("id", flat=True)
    )
    for stop_id in due_start:
        try:
            with transaction.atomic():
                stop = _stop(stop_id, lock=True)
                if stop.status != STATUS_SCHEDULED:
                    continue
                _begin(actor, stop, on=on)
                started.append(str(stop.id))
        except errors.BizError as problem:
            problems.append({"stop": str(stop_id), "message_key": problem.message_key})
    due_end = list(
        base.filter(status=STATUS_ON_HOLD, restart_on__isnull=False, restart_on__lte=on).values_list(
            "id", flat=True
        )
    )
    for stop_id in due_end:
        try:
            with transaction.atomic():
                stop = _stop(stop_id, lock=True)
                if stop.status != STATUS_ON_HOLD:
                    continue
                _finish(actor, stop, on=on)
                ended.append(str(stop.id))
        except errors.BizError as problem:
            problems.append({"stop": str(stop_id), "message_key": problem.message_key})
    return {"as_of": on.isoformat(), "started": started, "ended": ended, "problems": problems}


#: The refusal when a tenant has lost a seeded status row (BR-TEN-036 forbids
#: deleting one, so this is a configuration fault named rather than guessed past).
_STATUS_MISSING_KEYS = {
    STATUS_CODE_ACTIVE: "customers.account.active_status_missing",
    STATUS_CODE_HOLD: "customers.temporaryStop.holdStatusMissing",
}


def _seeded_status(code: str) -> models.AccountStatus:
    from apps.customers import services

    return services._seeded_status(code, _STATUS_MISSING_KEYS[code])


def _set_status(actor: Any, account: models.Account, code: str, *, on: date, action: str, stop: TemporaryStop) -> None:
    from apps.customers import attribute_history

    target = _seeded_status(code)
    before = {"status": account.status.code}
    account.status = target
    account.save(update_fields=["status", "updated_at"])
    # A backdate is refused by the history (`CR-142 P0.18`), so the period is
    # opened on the day the change was DUE, else the day it was RECORDED, else
    # — when the open period already starts later (a hold cancelled before its
    # own stop date had arrived in this utility's day) — that period is
    # updated in place, the history's own same-day collapse. The hold row and
    # the audit row keep the exact days either way.
    for day in (on, today()):
        try:
            attribute_history.record(account, on=day, actor=actor)
            break
        except ValueError:
            continue
    else:
        from apps.customers.attribute_history_models import AccountAttributeHistory

        open_row = AccountAttributeHistory.objects.filter(
            tenant_id=account.tenant_id, account_id=account.pk, effective_to__isnull=True
        ).first()
        if open_row is not None:
            attribute_history.record(account, on=open_row.effective_from, actor=actor)
    _audit(
        actor,
        action,
        "account",
        account.id,
        before=before,
        after={"status": code, "temporary_stop_id": str(stop.id), "on": on.isoformat()},
    )


def _begin(actor: Any, stop: TemporaryStop, *, on: date) -> None:
    account = _account(stop.account_id, lock=True)
    if getattr(account.status, "behavior_class", None) != CLASS_BILLABLE:
        # The account left `active` between approval and the stop date (closed,
        # cut). A hold over it would write a status nobody chose; cancelled,
        # named in the audit row.
        stop.status = STATUS_CANCELLED
        stop.ended_at = timezone.now()
        stop.save(update_fields=["status", "ended_at", "updated_at"])
        _audit(actor, "temporary_stop.cancelled", "temporary_stop", stop.id,
               after={"status": STATUS_CANCELLED, "account_status": account.status.code})
        return
    _set_status(actor, account, STATUS_CODE_HOLD, on=stop.stop_from, action="account.temporary_stop_started", stop=stop)
    stop.status = STATUS_ON_HOLD
    stop.started_at = timezone.now()
    stop.save(update_fields=["status", "started_at", "updated_at"])
    _audit(actor, "temporary_stop.started", "temporary_stop", stop.id,
           before={"status": STATUS_SCHEDULED}, after={"status": STATUS_ON_HOLD})


def _restore_account(actor: Any, stop: TemporaryStop, *, on: date) -> None:
    account = _account(stop.account_id, lock=True)
    if account.status.code.lower() == STATUS_CODE_HOLD:
        _set_status(actor, account, STATUS_CODE_ACTIVE, on=on, action="account.temporary_stop_ended", stop=stop)


def _finish(actor: Any, stop: TemporaryStop, *, on: date) -> None:
    _restore_account(actor, stop, on=stop.restart_on or on)
    stop.status = STATUS_ENDED
    stop.ended_at = timezone.now()
    stop.save(update_fields=["status", "ended_at", "updated_at"])
    _audit(actor, "temporary_stop.ended", "temporary_stop", stop.id,
           before={"status": STATUS_ON_HOLD}, after={"status": STATUS_ENDED})


# ═══════════════════════════════════════════════════════════════════════════
# THE FIELD VISIT (T6, B2)
# ═══════════════════════════════════════════════════════════════════════════
def _raise_field_visits(actor: Any, stop: TemporaryStop) -> list[dict[str, Any]]:
    """A shut-off job for the stop date and a turn-on job for the restart date,
    raised by Work through its own seam. A refusal is reported, never raised
    (BR-WRK-055): the hold stands whether or not a crew can be booked."""
    visits = [
        {"flow": "disconnect", "due_on": stop.stop_from.isoformat(), "role": "shutoff"},
    ]
    if stop.restart_on is not None:
        visits.append({"flow": "reconnect", "due_on": stop.restart_on.isoformat(), "role": "turnon"})
    try:
        with transaction.atomic():
            raised = seams.raise_temporary_stop_visits(
                actor, account_id=stop.account_id, visits=visits
            )
    except Exception as exc:  # noqa: BLE001 - BR-WRK-055: one fact, not raised
        logger.warning("temporary stop %s: field visit not raised: %s", stop.id, exc)
        return [seams.flow_work_not_raised(str(exc) or None)]
    numbers = {row.get("role"): row.get("order_no") for row in raised.get("raised", [])}
    with transaction.atomic():
        row = _stop(stop.id, lock=True)
        row.shutoff_order_no = numbers.get("shutoff") or row.shutoff_order_no
        row.turnon_order_no = numbers.get("turnon") or row.turnon_order_no
        row.save(update_fields=["shutoff_order_no", "turnon_order_no", "updated_at"])
        _audit(actor, "temporary_stop.field_visit_raised", "temporary_stop", row.id,
               after={"shutoff_order_no": row.shutoff_order_no, "turnon_order_no": row.turnon_order_no})
    return []

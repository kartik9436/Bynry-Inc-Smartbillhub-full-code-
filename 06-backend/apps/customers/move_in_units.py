# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-CUS-10190 — Move-in step 1 listed only vacant units.
# Ruling:   PO 2026-10-17, decision log *"MOVE-IN SEARCHES ALL UNITS, NOT ONLY
#           VACANT ONES"* and its *"Same day"* confirmation, verbatim there.
# Rules:    BR-CUS-017 (one occupant per unit — still refused at commit) ·
#           BR-CUS-055 (statuses keyed by behaviour CLASS) · BR-CUS-110 (a cut
#           ends occupancy) · BR-CUS-430/431 (a cut account closes through the
#           close-out act, never a move-out) · BR-SHL-048 (a parked wizard is a
#           draft; READ here, never joined) · NFR-3 (paged, sorted in SQL) ·
#           hard rules 1 (tenant scope) and 8 (the address is the premises')
# Tests:    tests/test_move_in_all_units.py
# ───────────────────────────────────────────────────────
"""**THE MOVE-IN UNIT SEARCH — EVERY UNIT, WITH WHAT A MOVE-IN MAY DO ON IT.**

The PO's words, from a utility's real-life feedback: *"people move-out of
perticular unit don'nt report it ; utilty user get to know the move-in needs to
done when new occupants reports … user wants search all units irrespective of
ther tatus and perform the move-in process"*.

So a unit is no longer hidden for being occupied. Each row carries a STATE, a
`selectable` flag, the PATH a move-in takes on it, and — when it is blocked —
the reason, as a catalogue key (B14 rule 33: the fact, never the rationale):

    state                 selectable  path              what happens
    vacant                yes         move_in           nobody has lived here
    closed                yes         move_in           last tenancy finished
                                                        (returning-customer
                                                        reopen rules, CR-181)
    active                yes         move_out_first    left without telling us
    vacation_hold         yes         move_out_first    the hold ends at move-out
    marked_disconnect     yes         move_out_first    the case closes, debt stays
    disconnected          yes         close_out_first   the cut account closes at
                                                        the cut; reconnect job
    move_out_in_progress  NO          —                 *"show the unit; but dont
                                                        allow move in"*
    pending_activation    NO          —                 *"we dont allow this case
                                                        for move in"*
    (removed unit)        not listed                    *"dont allow it"*

⚠ **THE MOVE-IN NEVER CLOSES THE OLD ACCOUNT ITSELF.** PO, verbatim: *"the
move-in won't close their account by itself. It raises a move-out for the old
occupant, and their account is settled by the normal move-out process: closing
reading, final bill, deposit and balance. - this is correct"*. `start_handover`
below writes the move-out's DRAFT (prefilled, the day before the move-in) and
nothing else; the account closes only when a clerk finishes that move-out.

⚠ **A DISCONNECTED ACCOUNT TAKES THE CLOSE-OUT DOOR, NOT THE MOVE-OUT ONE.**
The ruling says *"Disconnected ✔ via move-out first (cut reading prefilled)"*,
and `close_out.py` §1 is a signed ruling that a cut customer is never closed by
a move-out (*"to a regulator those are not the same event"*, BR-CUS-430). The
close-out IS this product's settlement of a cut account — final bill already
raised at the cut, `closed_at` = the cut date, the cut reading the last one on
the meters — so the next occupant opens on the cut reading, which is what
*"cut reading prefilled"* asks for. Decision log, same date.

⚠ **"MOVE-OUT IN PROGRESS" IS READ FROM THE DRAFT STORE.** A move-out has no
state on `accounts` before it commits (`move_reads.py` §2); the one place an
unfinished move-out exists is a `wizard_parks` row with `flow='move_out'` naming
the account. Reading it does not make a draft hold anything (BR-SHL-048 (c)
was about the draft BLOCKING writes); the PO's ruling of 2026-10-17 is that the
move-in, a different act, refuses while one is open.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from uuid import UUID

from django.db.models import Exists, OuterRef, Q

from apps.customers import models, seams, selectors
from core import errors
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

# ── states ─────────────────────────────────────────────────────────────────
STATE_VACANT = "vacant"
STATE_CLOSED = "closed"
STATE_ACTIVE = "active"
STATE_VACATION_HOLD = "vacation_hold"
STATE_MARKED_DISCONNECT = "marked_disconnect"
STATE_DISCONNECTED = "disconnected"
STATE_MOVE_OUT_IN_PROGRESS = "move_out_in_progress"
STATE_PENDING_ACTIVATION = "pending_activation"

PATH_MOVE_IN = "move_in"
PATH_MOVE_OUT_FIRST = "move_out_first"
PATH_CLOSE_OUT_FIRST = "close_out_first"

#: The two blocked states and their reasons (≤ 6 words in every catalogue).
BLOCKED_REASON_KEYS: dict[str, str] = {
    STATE_MOVE_OUT_IN_PROGRESS: "customers.moveIn.unitSearch.blocked.moveOutInProgress",
    STATE_PENDING_ACTIVATION: "customers.moveIn.unitSearch.blocked.pendingActivation",
}
REMOVED_REASON_KEY = "customers.moveIn.unitSearch.blocked.removed"

#: The seeded status codes a non-terminal account can be read as.
_CODE_STATE = {
    "vacation_hold": STATE_VACATION_HOLD,
    "marked_disconnect": STATE_MARKED_DISCONNECT,
    "disconnected": STATE_DISCONNECTED,
    "pending_activation": STATE_PENDING_ACTIVATION,
}

#: The search returns at most this many per page (NFR-3; the screen asks 50, the smallest page `core.pagination` serves).
PER_MAX = 50

FLOW_MOVE_OUT = "move_out"
FLOW_MOVE_IN = "move_in"


def _tenant_id() -> Any:
    return selectors._tenant_id()


def _occupying_classes() -> tuple[str, ...]:
    from apps.customers import services

    return services.OCCUPYING_BEHAVIOR_CLASSES


def _terminal_class() -> str:
    from apps.customers import services

    return services.CLASS_TERMINAL


def _open_accounts_on(unit_ids: list[str]) -> dict[str, list[models.Account]]:
    """Every NON-terminal account on these units (occupying, pending or cut)."""
    out: dict[str, list[models.Account]] = {}
    rows = (
        models.Account.objects.filter(tenant_id=_tenant_id(), unit_id__in=unit_ids)
        .exclude(status__behavior_class=_terminal_class())
        .select_related("status")
        .order_by("-created_at", "-id")
    )
    for account in rows:
        out.setdefault(str(account.unit_id), []).append(account)
    return out


def _move_out_drafts_for(account_ids: list[str]) -> dict[str, Any]:
    """`{account_id: park}` — the open move-out draft naming each account."""
    if not account_ids:
        return {}
    from apps.tenancy.models import WizardPark

    found: dict[str, Any] = {}
    for park in WizardPark.objects.filter(tenant_id=_tenant_id(), flow=FLOW_MOVE_OUT).order_by(
        "-parked_at", "-id"
    ):
        ref = park.subject_ref if isinstance(park.subject_ref, dict) else {}
        values = park.values if isinstance(park.values, dict) else {}
        account_id = str(ref.get("account_id") or values.get("account_id") or "")
        if account_id in account_ids and account_id not in found:
            found[account_id] = park
    return found


def _state_of(open_accounts: list[models.Account], drafts: dict[str, Any]) -> tuple[str, Any]:
    """`(state, the account it is about or None)` for one unit's open accounts."""
    occupying = [a for a in open_accounts if a.status.behavior_class in _occupying_classes()]
    if occupying:
        account = occupying[0]
        if str(account.id) in drafts:
            return STATE_MOVE_OUT_IN_PROGRESS, account
        code = (account.status.code or "").lower()
        if code in _CODE_STATE:
            return _CODE_STATE[code], account
        # A tenant-added occupying status keys off its CLASS (BR-CUS-055).
        from apps.customers import services

        if account.status.behavior_class == services.CLASS_BILLABLE_BASE_ONLY:
            return STATE_VACATION_HOLD, account
        return STATE_ACTIVE, account
    for account in open_accounts:
        if (account.status.code or "").lower() == "pending_activation":
            return STATE_PENDING_ACTIVATION, account
    for account in open_accounts:
        if (account.status.code or "").lower() == "disconnected":
            return STATE_DISCONNECTED, account
    return STATE_VACANT, None


def _path_for(state: str) -> str | None:
    if state in (STATE_VACANT, STATE_CLOSED):
        return PATH_MOVE_IN
    if state == STATE_DISCONNECTED:
        return PATH_CLOSE_OUT_FIRST
    if state in BLOCKED_REASON_KEYS:
        return None
    return PATH_MOVE_OUT_FIRST


def unit_state(unit_id: Any, *, with_build: bool = True) -> dict[str, Any]:
    """The state of ONE unit — what the commit and the handover re-check."""
    opened = _open_accounts_on([str(unit_id)]).get(str(unit_id), [])
    drafts = _move_out_drafts_for([str(a.id) for a in opened])
    state, account = _state_of(opened, drafts)
    if state == STATE_VACANT and selectors.last_closed_account_for_unit(unit_id) is not None:
        state = STATE_CLOSED
    if with_build and state == STATE_VACANT and seams.unit_not_yet_active(unit_id) is not None:
        state = STATE_PENDING_ACTIVATION
    return {
        "state": state,
        "account": account,
        "path": _path_for(state),
        "move_out_draft": drafts.get(str(account.id)) if account is not None else None,
    }


def refuse_if_blocked(unit_id: Any) -> None:
    """`DEF-CUS-10190` task 3 — the move-in's server refusal for a unit that is
    SHOWN but not selectable. Called by `services._move_in` before anything is
    written. An OCCUPIED unit is still refused by BR-CUS-017 inside
    `_make_occupying`; this adds the two the PO ruled on 2026-10-17 and the
    removed unit."""
    if seams.move_in_unit_queryset("") is not None:
        live = seams.move_in_unit_queryset("").filter(pk=unit_id).exists()
        if not live:
            raise errors.BizError(
                errors.BIZ_STATE,
                br_ref="DEF-CUS-10190",
                message_key=REMOVED_REASON_KEY,
                params={"unit_id": str(unit_id)},
            )
    # The New Connection still waiting on approval keeps its OWN refusal
    # (`CR-162-BRC10`, inside `_make_occupying`), so it is not re-asked here.
    found = unit_state(unit_id, with_build=False)
    key = BLOCKED_REASON_KEYS.get(found["state"])
    if key is not None:
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="DEF-CUS-10190",
            message_key=key,
            params={"unit_id": str(unit_id), "state": found["state"]},
        )


def search(
    term: Any, *, page: int = 1, per: int = 10, unit_id: Any = None
) -> tuple[list[dict[str, Any]], int]:
    """`GET /move-ins/units?q=` — one page of units, VACANT FIRST, sorted in SQL.

    Matched on the address, the unit number, the property number, a METER
    number and the OCCUPANT's name (the five the ruling's walk names). The
    first two legs are metering's columns; the meter number is assets'; the
    occupant's name is ours — each handed down as a LAZY id set, so a page is
    a COUNT and one slice whatever the tenant's size (NFR-3, T5's 40,000).
    """
    text = str(term or "").strip()
    per = max(1, min(int(per or 10), PER_MAX))
    page = max(1, int(page or 1))
    extra: Any = None
    if text != "":
        named_accounts = (
            models.CustomerAccount.objects.filter(
                tenant_id=_tenant_id(),
                ended_at__isnull=True,
                customer__display_name__icontains=text,
            ).values("account_id")
        )
        contact_accounts = models.Contact.objects.filter(
            tenant_id=_tenant_id(), full_name__icontains=text, deleted_at__isnull=True
        ).values("account_id")
        by_name = models.Account.objects.filter(
            Q(id__in=named_accounts) | Q(id__in=contact_accounts) | Q(account_no__icontains=text),
            tenant_id=_tenant_id(),
            unit_id__isnull=False,
        ).values("unit_id")
        meter_units = seams.unit_ids_for_asset_search(text)
        extra = Q(pk__in=by_name) | Q(pk__in=meter_units)
    qs = seams.move_in_unit_queryset(text)
    if qs is None:
        return [], 0
    if unit_id:
        try:
            UUID(str(unit_id))
        except ValueError:
            return [], 0
        # `?unit_id=` — ONE unit's row, for a resumed draft that names a unit
        # the clerk chose before (the wizard re-reads its state, BR-SHL-048 (b)).
        units = list(seams.move_in_unit_queryset("").filter(pk=unit_id).select_related("premises"))
        return rows_for(units), len(units)
    if extra is not None:
        base = seams.move_in_unit_queryset("")
        qs = base.filter(Q(pk__in=qs.values("pk")) | extra)
    taken = models.Account.objects.filter(
        tenant_id=_tenant_id(), unit_id=OuterRef("pk")
    ).exclude(status__behavior_class=_terminal_class())
    qs = (
        qs.annotate(taken=Exists(taken))
        .select_related("premises")
        .order_by("taken", "premises__premise_no", "unit_no", "label", "id")
    )
    total = qs.count()
    start = (page - 1) * per
    units = list(qs[start : start + per])
    return rows_for(units), total


def rows_for(units: list[Any]) -> list[dict[str, Any]]:
    """The wire rows for one page of units — a bounded number of queries."""
    ids = [str(unit.id) for unit in units]
    if not ids:
        return []
    opened = _open_accounts_on(ids)
    open_ids = [str(a.id) for rows in opened.values() for a in rows]
    drafts = _move_out_drafts_for(open_ids)
    closed: dict[str, models.Account] = {}
    for account in (
        models.Account.objects.filter(
            tenant_id=_tenant_id(),
            unit_id__in=ids,
            closed_at__isnull=False,
            status__behavior_class=_terminal_class(),
        )
        .order_by("-closed_at", "-created_at", "-id")
    ):
        closed.setdefault(str(account.unit_id), account)
    about_ids = open_ids + [str(a.id) for a in closed.values()]
    names = selectors.customer_names_for(about_ids)
    contacts = selectors.primary_contact_names_for(about_ids)
    assets = seams.assets_on_units(ids)
    out: list[dict[str, Any]] = []
    for unit in units:
        key = str(unit.id)
        state, account = _state_of(opened.get(key, []), drafts)
        last = closed.get(key)
        if state == STATE_VACANT and last is not None:
            state = STATE_CLOSED
        elif state == STATE_VACANT and seams.unit_not_yet_active(key) is not None:
            # A New Connection still waiting on approval (`CR-162-BRC10`) —
            # at most one read per row of a ten-row page.
            state = STATE_PENDING_ACTIVATION
        about = account if account is not None else (last if state == STATE_CLOSED else None)
        occupant = None
        if about is not None:
            name = names.get(str(about.id)) or contacts.get(str(about.id))
            occupant = {
                "account_id": str(about.id),
                "account_no": about.account_no,
                "name": name,
                "status_name": about.status.name if hasattr(about, "status") else None,
                "closed_at": about.closed_at.isoformat() if about.closed_at else None,
            }
        premises = unit.premises
        path = _path_for(state)
        out.append(
            {
                "id": key,
                "unit_no": unit.unit_no,
                "label": unit.label,
                "premise_no": premises.premise_no,
                "premise_name": premises.name,
                "address": {
                    "line1": premises.address_line,
                    "city": premises.city,
                    "state": premises.state,
                    "postal_code": premises.postal_code,
                },
                "meters": [row.get("asset_no") for row in assets.get(key, []) if row.get("asset_no")],
                "state": state,
                "occupant": occupant,
                "selectable": path is not None,
                "path": path,
                "reason_key": BLOCKED_REASON_KEYS.get(state),
            }
        )
    return out


# ═══════════════════════════════════════════════════════════════════════════
# THE HANDOVER — a move-out raised FROM a move-in (task 4)
# ═══════════════════════════════════════════════════════════════════════════
def _day(raw: Any, field: str) -> date:
    try:
        return date.fromisoformat(str(raw)[:10])
    except (TypeError, ValueError):
        raise errors.ValidationError(
            errors.VAL_FORMAT,
            message_key="customers.moveIn.unitSearch.handover.dateRequired",
            field_errors=[
                {"field": field, "code": errors.VAL_REQUIRED,
                 "message_key": "customers.moveIn.unitSearch.handover.dateRequired"}
            ],
        ) from None


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-SHL-025")
def start_handover(actor: Any, payload: Any) -> dict[str, Any]:
    """`POST /move-ins/handover` `{unit_id, opened_at, move_in_park_id?}`.

    Writes ONE `wizard_parks` row — the old occupant's move-out DRAFT, with
    the move-out date the day before the move-in and a link back to the parked
    move-in — and nothing else in the product (BR-SHL-048). From that moment the
    unit reads *Move-out in progress* and the move-in refuses until the
    move-out is finished; the clerk's move-in waits in its own draft.

    A disconnected unit answers `close_out_first` with the account, and writes
    nothing: the close-out is one act on one page, and has no draft to park.
    """
    from apps.tenancy import wizard_parks as tenancy_parks

    body = payload if isinstance(payload, dict) else {}
    unit_id = str(body.get("unit_id") or "")
    if unit_id == "":
        raise errors.ValidationError(
            errors.VAL_REQUIRED, message_key="customers.moveIn.unitSearch.handover.unitRequired"
        )
    seams.unit_row(unit_id)  # 404-never-403 for another tenant's unit (hard rule 1)
    opened_at = _day(body.get("opened_at"), "opened_at")
    found = unit_state(unit_id)
    account = found["account"]
    if found["path"] not in (PATH_MOVE_OUT_FIRST, PATH_CLOSE_OUT_FIRST) or account is None:
        key = BLOCKED_REASON_KEYS.get(found["state"], "customers.moveIn.unitSearch.handover.nothingToSettle")
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="DEF-CUS-10190",
            message_key=key,
            params={"state": found["state"]},
        )
    move_in_park_id = str(body.get("move_in_park_id") or "") or None
    answer: dict[str, Any] = {
        "path": found["path"],
        "account_id": str(account.id),
        "account_no": account.account_no,
        "unit_id": unit_id,
        "move_in_park_id": move_in_park_id,
        "move_out_park_id": None,
        "moved_out_on": None,
    }
    if found["path"] == PATH_CLOSE_OUT_FIRST:
        return answer
    moved_out_on = opened_at - timedelta(days=1)
    label = " · ".join(
        part
        for part in (account.account_no, selectors.customer_names_for([account.id]).get(str(account.id)))
        if part
    )
    row = tenancy_parks.park(
        actor,
        {
            "flow": FLOW_MOVE_OUT,
            "subject_label": label,
            "subject_ref": {"account_id": str(account.id), "unit_id": unit_id},
            "step": 1,
            "values": {
                "account_id": str(account.id),
                "account_term": account.account_no,
                "moved_out_on": moved_out_on.isoformat(),
                "close_reason": "",
                # The parked move-in this move-out was raised from — read by
                # the move-out's done screen for *Back to move-in*.
                "from_move_in": move_in_park_id,
            },
            # A DRAFT, not a park: nobody was asked what they wait for.
            "waiting_on": "",
        },
    )
    answer["move_out_park_id"] = str(row.id)
    answer["moved_out_on"] = moved_out_on.isoformat()
    return answer


# ═══════════════════════════════════════════════════════════════════════════
# WHAT A MOVE-OUT SETTLES ON THE WAY (task 6) — each through its owner
# ═══════════════════════════════════════════════════════════════════════════
def settle_holds_at_move_out(actor: Any, account: Any, moved_out_on: date) -> list[dict[str, Any]]:
    """Inside `services.move_out`'s transaction: the account is leaving, so

      · a LIVE temporary stop ends (PO: *"Vacation hold/Suspended ✔ via
        move-out first (temporary stop ends)"*) and its open shut-off and turn-on jobs are
        cancelled — nobody is coming back to have the service turned on;
      · an OPEN disconnect case short of the cut closes as *customer left*
        (PO: *"Marked disconnect ✔ via move-out first (disconnect case closes as
        customer left; debt stays on old account)"*). The debt and any payment
        plan stay on the old account; nothing here moves money.

    Returns what it did, for the response's `settled` list. Reuses the owning
    services (`temporary_stop._end_now_locked`, `disconnects.stop_for_move_out`).
    """
    from apps.customers import disconnects, temporary_stop

    done: list[dict[str, Any]] = []
    stop = temporary_stop.live_for_account(account.id)
    if stop is not None:
        stop = temporary_stop._stop(stop.id, lock=True)
        jobs = [
            ("shutoff", stop.shutoff_order_no),
            ("restart", stop.turnon_order_no),
        ]
        temporary_stop._end_now_locked(actor, stop, on=moved_out_on)
        account.refresh_from_db()
        done.append({"code": "temporary_stop_ended", "stop_id": str(stop.id)})
        # `DEF-CUS-10194` (walk W5) — BOTH of the hold's jobs, not only the
        # turn-on: a shut-off still queued for a customer who has left would
        # send a crew to cut the service the next occupant just took. A job
        # already done or already off the run is left as it is (Work says so).
        for role, order_no in jobs:
            if not order_no:
                continue
            cancelled = seams.cancel_flow_order(actor, order_no=order_no)
            done.append(
                {"code": f"{role}_job_cancelled" if cancelled else f"{role}_job_not_cancelled",
                 "order_no": order_no}
            )
    case = disconnects.open_case_for(account.id)
    if case is not None and case.state not in (disconnects.STATE_CUT, disconnects.STATE_RECONNECTING):
        disconnects.stop_for_move_out(actor, account.id, on_date=moved_out_on)
        done.append({"code": "disconnect_case_closed_customer_left", "case_no": case.case_no})
    return done


def reconnect_after_cut(actor: Any, *, new_account_id: Any, outgoing: Any, opened_at: date) -> list[dict[str, Any]]:
    """After a move-in commits: when the tenancy it follows ended at a CUT
    (closed out, never restored), the new occupant needs the service turned
    back on — a reconnect job, through Work's own temporary-stop door
    (`seams.raise_temporary_stop_visits`, a *reconnect* visit dated the move-in).
    A refusal is reported, never raised (BR-WRK-055)."""
    if outgoing is None:
        return []
    from apps.customers.disconnects import STATE_CLOSED_OUT, DisconnectCase

    cut = DisconnectCase.objects.filter(
        tenant_id=_tenant_id(), account_id=outgoing.id, state=STATE_CLOSED_OUT
    ).exists()
    if not cut:
        return []
    try:
        from django.db import transaction

        with transaction.atomic():
            raised = seams.raise_temporary_stop_visits(
                actor,
                account_id=new_account_id,
                visits=[{"flow": "reconnect", "due_on": opened_at.isoformat(), "role": "reconnect"}],
            )
    except Exception as exc:  # noqa: BLE001 - BR-WRK-055: reported, never raised
        return [{"code": "reconnect_job_not_raised", "warning": seams.flow_work_not_raised(str(exc) or None)}]
    return [
        {"code": "reconnect_job_raised", "order_no": row.get("order_no")}
        for row in raised.get("raised", [])
    ]

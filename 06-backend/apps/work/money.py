# ── Trace ──────────────────────────────────────────────
# Change:   CR-187-BRC10 · Phase 13 — T-33 (the money freshness read), T-34
#           (a push when money changes), T-35 (freshness on the template step).
#           Screens: FF-25 (customer), FF-26 (restoration), FF-27 (stale money),
#           FF-61 (before you reconnect)
# Rules:    R16 (PO ruled: the field app reads money and never writes it) ·
#           R17 (PO ruled: money older than 5 minutes is WARNED, never blocked;
#           proceeding on stale data is recorded as unverified) · R18 (derived:
#           freshness sits on the template step; no code knows what a
#           disconnect is) · R19 (PO ruled: the server pushes the moment money
#           changes) · R26 (contractors see the customer's name, not their
#           money) · R111 (a reconnect fee is its own question) · BR-WRK-002 /
#           G78 (Work reads payments only through its seam and writes none of
#           its tables) · BR-WRK-008 (a job copies its template) · CLAUDE.md
#           hard rules 1, 2, 7 · hard-won law 14 (a savepoint, never a bare
#           `except IntegrityError`)
# Tests:    06-backend/tests/test_cr187_money_freshness.py ·
#           tests/test_cr187_money_push.py · tests/test_cr187_money_pg.py
# Impacts:  apps/work/api.py (two routes) · apps/work/apps.py (job + beat) ·
#           apps/work/sync.py (`task_tick` records a money proceed) ·
#           apps/work/seams/payments_seam.py · apps/payments/field_money.py
# ───────────────────────────────────────────────────────
"""The field app's money: read it fresh, warn when stale, push when it moves.

════════════════════════════════════════════════════════════════════════════
NO CODE HERE KNOWS WHAT A DISCONNECT IS (R18)
════════════════════════════════════════════════════════════════════════════
A step needs money because its TEMPLATE says so — `wot_tasks.money_fresh_minutes`
(and, for FF-61's fee, `money_charge_code`), copied onto the job like the
title and the photo rule (`BR-WRK-008`). A disconnect template's *Close the
valve* step carries `5`; a restoration's *Open the kerb stop* carries `5`; a
meter exchange carries nothing and this file never reads its account's money.
**Every decision below keys off those two columns and nothing else** — there is
no `type == "disconnect"` anywhere, and a test asserts the push skips a job
whose steps declare no money check even when its account's money moves.

════════════════════════════════════════════════════════════════════════════
T-33 · THE READ, AND WHAT `as_at` IS
════════════════════════════════════════════════════════════════════════════
`GET /work/mobile/jobs/{id}/money` answers the job's account balance, the latest
payment that stands and its state (`posted` / `cleared`, CR-186-BRC10), each
declared charge's bill (paid or not), and **`as_at` — the server's clock at the
moment it read them.** The handset stores the answer with that stamp and says
how old it is (*Balance is 3 days old*, FF-27); `stale_after` is `as_at` plus
the strictest bar among the job's money steps, so the phone compares one
timestamp and does no policy of its own.

⚠ **MONEY IS EMPLOYEE-ONLY (R26).** A contractor's handset gets `withheld:
"employee_only"` and NO figure — not a zero, not a masked string. FF-25 draws
a contractor's customer screen with a name and no money, and a payload that
carried the balance and trusted the phone to hide it would be the leak.

════════════════════════════════════════════════════════════════════════════
T-35 · STALE IS WARNED, NEVER BLOCKED, AND PROCEEDING IS RECORDED (R17)
════════════════════════════════════════════════════════════════════════════
`record_proceed` stores, on the job's own task row, the `as_at` of the figure
the technician proceeded on, when they proceeded, and the verdict — `True`
(unverified: stale, or no figure seen at all) or `False` (fresh). **It never
refuses**: R17 says the technician can always finish the job, and E2E-12 is a
disconnect with no signal. It writes one `audit_log` row either way (hard rule
7 — a money decision taken on a figure is a money action's record).

════════════════════════════════════════════════════════════════════════════
T-34 · THE PUSH, AND WHY IT IS A ONE-MINUTE POLL
════════════════════════════════════════════════════════════════════════════
This repository has **no signal, outbox or event bus between modules** (grepped
again 2026-10-21; `apps/billing/check_staleness.py` records the same finding of
2026-09-30), and payments must not import Work. So Work POLLS payments'
read-only *changed since* seam — the pattern billing's bulk Check already uses —
every `SWEEP_SECONDS`, for exactly the accounts of OPEN jobs whose steps declare
a money check and that have a technician to tell. Each change it finds becomes
ONE `work_money_pushes` row (unique on tenant, account and payments' own
`updated_at`) and one `work.money_push` job per such open job. A second sweep
over the same change inserts nothing and pushes nothing — **once per money
change**, which is what the table is for (see `money_models.py`).

The push carries NO amount (R66's spirit: a notification is shown on a locked
screen). It is the doorbell; the phone then calls the read above.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.work import models
from apps.work import money_flow_facts
from apps.work import push as work_push
from apps.work.seams import customers_seam, metering_seam, payments_seam
from core import audit as core_audit
from core import errors
from core import jobs as core_jobs
from core import permissions as core_permissions
from core import tenancy as core_tenancy

logger = logging.getLogger("smartbillhub.work.money")

#: R17, PO ruled: *"Money older than 5 minutes is warned"*. The DEFAULT a step
#: takes when it says it needs fresh money and names no bar of its own.
MONEY_FRESH_DEFAULT_MINUTES = 5

#: R26 — the one reason a figure is withheld, as a token the catalogue words.
WITHHELD_EMPLOYEE_ONLY = "employee_only"

#: The two audit actions of a proceed, and the one sentence each stands for.
ACTION_PROCEEDED_FRESH = "work_order.task_money_verified"
ACTION_PROCEEDED_UNVERIFIED = "work_order.task_money_unverified"

#: T-34's job, queue and beat. Same `work` queue as `work.push` — its consumer
#: is `celery-work` in `docker-compose.yml`, which `G109` checks.
MONEY_PUSH_JOB = "work.money_push"
MONEY_SWEEP_JOB = "work.money_sweep"
SWEEP_TASK = "work.money_sweep_all"
BEAT_ENTRY = "work-money-sweep"
#: How often the poll runs. R19 says *the moment money changes*; a minute is
#: the closest a poll gets without a broker event, and the phone's own read is
#: live whenever the technician opens the job.
SWEEP_SECONDS = 60
#: The sweep re-reads this far behind its own last mark, so a payment committed
#: a moment after a sweep read the table is never skipped; the unique row makes
#: the overlap free.
SWEEP_OVERLAP = timedelta(minutes=5)
#: How far back the very first sweep of a utility looks.
FIRST_LOOK_BACK = timedelta(hours=24)

ACTION_MONEY_PUSHED = "work.order.money_changed_pushed"
ACTION_MONEY_WAITING = "work.order.money_changed_waiting"


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


# ══════════════════════════════════════════════════════════════════════════
# Which account, and which steps
# ══════════════════════════════════════════════════════════════════════════


def account_id_of(order: Any) -> str | None:
    """The job's own account, else the account in force on its unit.

    The same walk `mobile._customer_contact` makes (`CR-168-BRC10` P1.15), so
    the name on FF-25 and the money on FF-27 are one customer.
    """
    if getattr(order, "account_id", None):
        return str(order.account_id)
    unit_id = getattr(order, "unit_id", None)
    found = customers_seam.current_account_for_unit(unit_id) if unit_id else None
    return found.get("id") if found else None


def money_steps(order_id: Any) -> list[Any]:
    """The job's task rows that declare a money check, in step order."""
    return list(
        models.WorkOrderTask.objects.filter(
            tenant_id=_tenant_id(), work_order_id=order_id, money_fresh_minutes__isnull=False
        ).order_by("seq")
    )


def _is_contractor(technician: Any) -> bool:
    """R26 — a technician on a CONTRACTOR crew sees no money."""
    crew = getattr(technician, "crew", None) if technician is not None else None
    return getattr(crew, "kind", None) == models.Crew.KIND_CONTRACTOR


#: FB-023 F3 — the two words the phone stores on its own roster row.
EMPLOYMENT_EMPLOYEE = "employee"
EMPLOYMENT_CONTRACTOR = "contractor"


def employment_of(technician: Any) -> str:
    """FB-023 F3 (PO 2026-10-31, *"only technicians on a contractor crew (as the
    server does today)"*) — the SAME test the money read applies, sent to the
    phone on the day and change feeds so the handset hides money exactly when
    this file withholds it. Staff on no crew are employees."""
    return EMPLOYMENT_CONTRACTOR if _is_contractor(technician) else EMPLOYMENT_EMPLOYEE


def _job_for(actor: Any, order_id: Any) -> Any:
    """The order — the technician's OWN job for a field login (a 404 otherwise,
    HR-1), or any job of the tenant for an office role (`require_own_job`)."""
    from apps.work import mobile

    if getattr(actor, "role", None) == core_permissions.FIELD_TECHNICIAN:
        return mobile._own_job_or_404(actor, order_id)
    order = metering_seam.work_order_row(order_id)
    if order is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return order


# ══════════════════════════════════════════════════════════════════════════
# T-33 · the read
# ══════════════════════════════════════════════════════════════════════════


def _check_row(task: Any, as_at: Any) -> dict[str, Any]:
    minutes = int(task.money_fresh_minutes)
    return {
        "task_id": str(task.id),
        "seq": task.seq,
        "title": task.title,
        "fresh_minutes": minutes,
        "stale_after": (as_at + timedelta(minutes=minutes)).isoformat(),
        "charge_code": task.money_charge_code or None,
        # What the technician did last time, so a re-opened job still shows
        # *Proceeding is recorded as unverified* against the step it applies to.
        "proceeded": (
            None
            if task.money_unverified is None
            else {
                "unverified": bool(task.money_unverified),
                "money_as_at": task.money_as_at.isoformat() if task.money_as_at else None,
                "proceeded_at": (
                    task.money_proceeded_at.isoformat() if task.money_proceeded_at else None
                ),
            }
        ),
    }


def money_read(actor: Any, order_id: Any, *, now: Any = None) -> dict[str, Any]:
    """`GET /work/mobile/jobs/{id}/money` — the job's money, stamped `as_at`.

    READ-ONLY (R16). Every figure is `{amount (4dp), display (2dp), currency}`
    from `apps/payments/field_money.py`; nothing here adds or rounds money.
    """
    from apps.work import mobile

    order = _job_for(actor, order_id)
    as_at = now or timezone.now()
    steps = money_steps(order.id)
    bar = min((int(step.money_fresh_minutes) for step in steps), default=MONEY_FRESH_DEFAULT_MINUTES)
    answer: dict[str, Any] = {
        "order_no": getattr(order, "order_no", None),
        "as_at": as_at.isoformat(),
        "fresh_minutes": bar,
        "stale_after": (as_at + timedelta(minutes=bar)).isoformat(),
        "checks": [_check_row(step, as_at) for step in steps],
        "withheld": None,
        "account_no": None,
        "owing": None,
        "balance": None,
        "currency": None,
        "latest_payment": None,
        "charges": [],
        # FB-023 F5 — what the job's reason adds (`money_flow_facts`); R18 keeps
        # the name of that reason out of this file.
        **money_flow_facts.empty(),
        "unavailable": [],
    }
    # FB-028 (PO 2026-10-31) — a job RAISED ON SITE carries the facts its
    # steps gate on (`money_flow_facts.field_gate`); before the contractor
    # return, so a contractor's raised reconnect still knows it is gated.
    answer.update(
        money_flow_facts.field_gate(order, account_id_of(order), as_of=timezone.localdate(as_at))
    )
    if _is_contractor(mobile.technician_of(actor)):
        # R26 — no figure at all, not a zero and not a mask.
        answer["withheld"] = WITHHELD_EMPLOYEE_ONLY
        return answer

    account_id = account_id_of(order)
    if account_id is None:
        answer["unavailable"].append({"code": "job_names_no_account", "br_ref": "CR-168-BRC10 P1.15"})
        return answer
    account = customers_seam.account(account_id)
    answer["account_no"] = (account or {}).get("account_no")

    position = payments_seam.money_position(account_id)
    if position is None:
        answer["unavailable"].append({"code": "payments_read_not_published", "br_ref": "R16"})
        return answer
    answer["owing"] = position.get("owing")
    answer["balance"] = position.get("balance")
    answer["currency"] = position.get("currency")
    answer["latest_payment"] = position.get("latest_payment")
    answer["unavailable"].extend(position.get("problems") or ())

    # R111 — each charge a step names is asked on its own, beside the balance.
    codes = sorted({step.money_charge_code for step in steps if step.money_charge_code})
    for code in codes:
        found = payments_seam.charge_position(account_id, code)
        answer["charges"].append(
            found if found is not None else {"charge_code": code, "charged": None, "paid": None}
        )

    # FB-023 F5 (PO 2026-10-31) — the facts the job's REASON adds (a payment
    # plan's status and the latest notice, on one kind of job only), decided
    # and read in `money_flow_facts` through the payments and customers seams.
    answer.update(money_flow_facts.facts_for(order, account_id, as_of=timezone.localdate(as_at)))
    return answer


# ══════════════════════════════════════════════════════════════════════════
# T-35 · proceeding on a figure — recorded, never refused
# ══════════════════════════════════════════════════════════════════════════


def verdict(*, fresh_minutes: int, money_as_at: Any, proceeded_at: Any) -> bool:
    """True when the proceed is UNVERIFIED: no figure seen, or older than the bar.

    A figure stamped AFTER the proceed (a handset clock behind the server's) is
    treated as age zero — fresh — because the figure cannot be older than the
    moment it was read, whatever the phone's clock says.
    """
    if money_as_at is None:
        return True
    age = proceeded_at - money_as_at
    return age > timedelta(minutes=int(fresh_minutes))


def record_proceed(
    actor: Any, order_id: Any, task_id: Any, body: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Record that the technician went ahead on a money step, and on what.

    `body`: `{money_as_at?, proceeded_at?}` — the `as_at` of the figure on the
    screen when they pressed (absent or null = they saw none) and the handset's
    capture time (absent = now). **Never refused for staleness** (R17). A step
    that declares no money check answers `recorded: false` and writes nothing,
    so a phone may send the stamp with every tick without asking first.
    """
    body = dict(body or {})
    order = _job_for(actor, order_id)
    tenant_id = _tenant_id()
    task = models.WorkOrderTask.objects.filter(
        tenant_id=tenant_id, work_order_id=order.id, pk=task_id
    ).first()
    if task is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    if task.money_fresh_minutes is None:
        return {"task_id": str(task.id), "recorded": False}

    raw_as_at = body.get("money_as_at")
    money_as_at = (
        metering_seam.parse_moment(raw_as_at, field="money_as_at") if raw_as_at else None
    )
    raw_at = body.get("proceeded_at")
    proceeded_at = (
        metering_seam.parse_moment(raw_at, field="proceeded_at") if raw_at else timezone.now()
    )
    unverified = verdict(
        fresh_minutes=task.money_fresh_minutes, money_as_at=money_as_at, proceeded_at=proceeded_at
    )
    with transaction.atomic():
        task.money_as_at = money_as_at
        task.money_proceeded_at = proceeded_at
        task.money_unverified = unverified
        task.save(
            update_fields=["money_as_at", "money_proceeded_at", "money_unverified", "updated_at"]
        )
        core_audit.write_row(
            action=ACTION_PROCEEDED_UNVERIFIED if unverified else ACTION_PROCEEDED_FRESH,
            entity_type="work_order",
            entity_id=order.id,
            actor_user_id=_actor_id(actor),
            after={
                "task_seq": task.seq,
                "title": task.title,
                "fresh_minutes": task.money_fresh_minutes,
                "money_as_at": money_as_at.isoformat() if money_as_at else None,
                "proceeded_at": proceeded_at.isoformat(),
                "unverified": unverified,
            },
        )
    return {
        "task_id": str(task.id),
        "recorded": True,
        "unverified": unverified,
        "fresh_minutes": task.money_fresh_minutes,
        "money_as_at": money_as_at.isoformat() if money_as_at else None,
        "proceeded_at": proceeded_at.isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════
# FB-013 · the PAID close — the step stopped because the money was cleared
# ══════════════════════════════════════════════════════════════════════════
#
# PO rulings of 2026-10-28 (decision log *"FB-013: a cleared balance STOPS the
# money-check step"*): (a) a FRESH read showing the balance cleared STOPS the
# step — R17 (stale is warned, never blocked) is unchanged; (b) the technician
# may then close *Not done — payment received*, offered only on a fresh
# cleared read, with the balance and latest payment the phone saw stored with
# the close; (c) R18 stands — this keys off the step's `money_fresh_minutes`.
#
# ⚠ **STRICT, BY OUR JUDGMENT (decision log, judgment 3).** The close is
# REFUSED — back to the technician, nothing stored — unless it carries the
# phone's snapshot proving a fresh, cleared read on a step that declares a
# check. A paid close that could not prove it would be a job left undone on
# the technician's word alone.
#
# ⚠ **AND THE SNAPSHOT IS NEVER TRUSTED BLINDLY.** It is stored as what the
# phone SAW; beside it the server re-reads the account's money at the close and
# stores its OWN figure with its own as-at. The office sees both. Read only
# (R16): nothing here writes a payments table (BR-WRK-002, G78).

#: The four refusals, as catalogue keys (`work.mobile.*` — the phone renders the
#: server's `work.*` sentences, `field-app/src/i18n/catalogues.ts`).
PAID_CLOSE_NEEDS_SNAPSHOT = "work.mobile.paid_close_needs_a_fresh_balance"
PAID_CLOSE_NOT_FRESH = "work.mobile.paid_close_balance_not_fresh"
PAID_CLOSE_NOT_CLEARED = "work.mobile.paid_close_balance_not_cleared"
PAID_CLOSE_NO_CHECK = "work.mobile.paid_close_needs_a_money_check"


def _refuse_paid(message_key: str, **params: Any) -> None:
    raise errors.ValidationError(
        errors.VAL_REQUIRED, message_key=message_key, br_ref="DEF-WRK-10641", params=params or None
    )


def is_cleared(amount: Any) -> bool:
    """Judgment 1: cleared is the owing figure at four places **≤ 0.0000**.

    A credit is cleared. Exact, never rounded: any non-zero digit owes (the
    phone's `isCleared` reads digits the same way). Anything unreadable is NOT
    cleared — a paid close is never accepted on a figure nobody can parse (hard
    rule 2: decimal, never float)."""
    from decimal import Decimal, InvalidOperation

    try:
        return Decimal(str(amount)) <= Decimal("0")
    except (InvalidOperation, ValueError, TypeError):
        return False


def paid_close_record(order_id: Any, seen: Any, captured_at: Any) -> dict[str, Any]:
    """Validate the phone's snapshot of a paid close and return the record to store.

    `seen` is `field_data.money_seen` as the phone sent it: `{task_id?, balance,
    currency, as_at, checked_at?, latest_payment?}` — `as_at` is the SERVER's
    stamp from `money_read` (T-33), `checked_at` the handset's moment the stop
    was shown (absent = the close's own `captured_at`). Raises a refusal unless
    the job has a money step, the figure is cleared and it was fresh at the stop
    by that step's own bar (judgment 2).
    """
    from core import device_clock

    steps = money_steps(order_id)
    if not steps:
        _refuse_paid(PAID_CLOSE_NO_CHECK)
    if not isinstance(seen, dict) or seen.get("as_at") in (None, "") or seen.get("balance") in (None, ""):
        _refuse_paid(PAID_CLOSE_NEEDS_SNAPSHOT)
    step = next((s for s in steps if str(s.id) == str(seen.get("task_id") or "")), None)
    # The stopped step's own bar; a snapshot naming no step (or a step not on
    # this job) is held to the STRICTEST bar of the job's money steps.
    bar = (
        int(step.money_fresh_minutes)
        if step is not None
        else min(int(s.money_fresh_minutes) for s in steps)
    )
    as_at = metering_seam.parse_moment(seen["as_at"], field="money_as_at")
    raw_checked = seen.get("checked_at")
    checked_at = (
        device_clock.correct(metering_seam.parse_moment(raw_checked, field="checked_at"))
        if raw_checked
        else captured_at
    ) or timezone.now()
    if verdict(fresh_minutes=bar, money_as_at=as_at, proceeded_at=checked_at):
        _refuse_paid(PAID_CLOSE_NOT_FRESH, minutes=bar)
    if not is_cleared(seen.get("balance")):
        _refuse_paid(PAID_CLOSE_NOT_CLEARED)

    latest = seen.get("latest_payment") if isinstance(seen.get("latest_payment"), dict) else None
    phone = {
        "balance": str(seen.get("balance")),
        "currency": str(seen.get("currency") or "") or None,
        "as_at": str(seen.get("as_at")),
        "checked_at": checked_at.isoformat(),
        "latest_payment": (
            {
                "amount": None if latest.get("amount") is None else str(latest.get("amount")),
                "at": str(latest.get("at")) if latest.get("at") else None,
                # FB-023 F2 (PO 2026-10-31, *"the step stops, and 'posted, not
                # cleared' is shown and saved"*) — what the phone showed the
                # payment as. Only the two words payments uses; anything else
                # is stored as unknown rather than echoed.
                "state": latest.get("state") if latest.get("state") in ("posted", "cleared") else None,
            }
            if latest
            else None
        ),
    }
    return {
        "phone": phone,
        "server": _server_read(order_id),
        "fresh_minutes": bar,
        "task_seq": step.seq if step is not None else None,
        "task_title": step.title if step is not None else None,
        "br_ref": "DEF-WRK-10641",
    }


def _server_read(order_id: Any) -> dict[str, Any]:
    """The server's OWN read of the job's money at the close (R16: a read)."""
    order = metering_seam.work_order_row(order_id)
    empty: dict[str, Any] = {
        "as_at": timezone.now().isoformat(),
        "owing": None,
        "balance": None,
        "currency": None,
        "latest_payment": None,
        "unavailable": [],
    }
    account_id = account_id_of(order) if order is not None else None
    if account_id is None:
        return {**empty, "unavailable": ["job_names_no_account"]}
    position = payments_seam.money_position(account_id)
    if position is None:
        return {**empty, "unavailable": ["payments_read_not_published"]}
    return {
        **empty,
        "owing": position.get("owing"),
        "balance": position.get("balance"),
        "currency": position.get("currency"),
        "latest_payment": position.get("latest_payment"),
        "unavailable": [row.get("code") for row in position.get("problems") or ()],
    }


# ══════════════════════════════════════════════════════════════════════════
# T-34 · the sweep and the push
# ══════════════════════════════════════════════════════════════════════════


def _qualifying_orders() -> list[Any]:
    """Open jobs with a technician and at least one money step, this tenant."""
    tenant_id = _tenant_id()
    with_money = (
        models.WorkOrderTask.objects.filter(tenant_id=tenant_id, money_fresh_minutes__isnull=False)
        .values_list("work_order_id", flat=True)
        .distinct()
    )
    return list(
        metering_seam.open_work_orders_queryset().filter(
            pk__in=list(with_money), assignee_technician_id__isnull=False
        )
    )


def _since(tenant_id: Any, now: Any) -> Any:
    last = (
        models.WorkMoneyPush.objects.filter(tenant_id=tenant_id)
        .order_by("-change_at")
        .values_list("change_at", flat=True)
        .first()
    )
    return (last - SWEEP_OVERLAP) if last is not None else (now - FIRST_LOOK_BACK)


def push_scope_key(order_id: Any, change_at: Any) -> str:
    """One push per JOB per money change — two jobs on one account ring twice."""
    return f"money:{order_id}:{change_at.isoformat()}"


def sweep(*, now: Any = None) -> dict[str, Any]:
    """One poll of the tenant in context. Returns what it did.

    ⚠ **THE ROW IS INSERTED IN ITS OWN SAVEPOINT** (hard-won law 14). Two
    sweeps racing on the same change both try the insert; on PostgreSQL the
    loser's `IntegrityError` would abort the whole transaction without the
    nested `atomic()`, and every later change in the loop would be lost.
    """
    tenant_id = _tenant_id()
    now = now or timezone.now()
    by_account: dict[str, list[Any]] = {}
    for order in _qualifying_orders():
        account_id = account_id_of(order)
        if account_id:
            by_account.setdefault(str(account_id), []).append(order)
    if not by_account:
        return {"accounts": 0, "changes": 0, "pushed": 0}

    changes = payments_seam.money_changed_since(list(by_account), _since(tenant_id, now))
    pushed = 0
    recorded = 0
    for account_id, change_at in sorted(changes.items(), key=lambda kv: str(kv[0])):
        orders = by_account.get(str(account_id)) or []
        if not orders or change_at is None:
            continue
        if models.WorkMoneyPush.objects.filter(
            tenant_id=tenant_id, account_id=account_id, change_at=change_at
        ).exists():
            continue
        devices = sum(
            len(work_push._active_devices(order.assignee_technician_id)) for order in orders
        )
        try:
            with transaction.atomic():
                models.WorkMoneyPush.objects.create(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    change_at=change_at,
                    orders=[str(order.id) for order in orders],
                    devices=devices,
                )
        except IntegrityError:
            # Another sweep recorded this change first — it pushes, not us.
            continue
        recorded += 1
        for order in orders:
            core_jobs.enqueue(
                MONEY_PUSH_JOB,
                scope_key=push_scope_key(order.id, change_at),
                payload={
                    "work_order_id": str(order.id),
                    "order_no": order.order_no,
                    "technician_id": str(order.assignee_technician_id),
                    "change_at": change_at.isoformat(),
                },
            )
            pushed += 1
    return {"accounts": len(by_account), "changes": recorded, "pushed": pushed}


def run_money_push_job(record: dict[str, Any]) -> None:
    """The BODY: address the technician's devices and write the TRUE audit line.

    `push.py`'s rule, reused rather than restated: the action is derived from a
    COUNT of devices addressed, so the Audit tab never says *pushed* over a
    technician with no phone registered.
    """
    payload = dict(record.get("payload") or {})
    devices = work_push._active_devices(payload.get("technician_id"))
    attempted = (
        work_push._deliver(devices, {**payload, "kind": "money_changed"}) if devices else 0
    )
    core_audit.write_row(
        action=ACTION_MONEY_PUSHED if attempted else ACTION_MONEY_WAITING,
        entity_type="work_order",
        entity_id=payload.get("work_order_id"),
        actor_user_id=None,
        after={
            "order_no": payload.get("order_no"),
            "change_at": payload.get("change_at"),
            "devices": attempted,
            "delivery": "pushed to phone" if attempted else "waiting for the phone",
        },
    )


def run_money_sweep_job(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record.get("payload") or {})
    tenant_id = record.get("tenant_id") or payload.get("tenant_id")
    with core_tenancy.tenant_context(tenant_id):
        return sweep()


def sweep_all_tenants() -> dict[str, Any]:
    """ONE beat firing: enqueue a sweep per live utility (the rules fan-out)."""
    from importlib import import_module

    try:
        listed = import_module("apps.tenancy.selectors").live_tenant_subdomains()
    except Exception:  # noqa: BLE001 — a broken read must not stop the beat
        logger.exception("work.money: the live-utility read failed; no sweep queued this minute")
        return {"tenants": 0}
    queued = 0
    for slug in listed or ():
        tenant_id = core_tenancy.tenant_id_for_slug(str(slug))
        if tenant_id is None:
            continue
        with core_tenancy.tenant_context(tenant_id):
            core_jobs.enqueue(
                MONEY_SWEEP_JOB,
                scope_key=f"{tenant_id}:{MONEY_SWEEP_JOB}",
                payload={"tenant_id": str(tenant_id)},
            )
        queued += 1
    return {"tenants": queued}


def beat_schedule() -> dict[str, dict[str, Any]]:
    """The beat entry, as DATA (the `rules.beat_schedule` shape)."""
    return {
        BEAT_ENTRY: {
            "task": SWEEP_TASK,
            "schedule": float(SWEEP_SECONDS),
            "args": (),
            "options": {"expires": SWEEP_SECONDS},
        }
    }


_SWEEP_ALL_TASK: Any = None


def install(app: Any = None) -> dict[str, Any]:
    """Register the beat entry. Never raises: no celery here → `installed: False`."""
    if app is None:
        try:
            from config.celery import app as celery_app
        except Exception as problem:  # noqa: BLE001 — see `rules.install`
            return {"installed": False, "reason": str(problem)}
        app = celery_app
    global _SWEEP_ALL_TASK
    _SWEEP_ALL_TASK = app.task(name=SWEEP_TASK, bind=False)(sweep_all_tenants)
    existing = dict(getattr(app.conf, "beat_schedule", None) or {})
    existing.update(beat_schedule())
    app.conf.beat_schedule = existing
    return {"installed": True, "entry": BEAT_ENTRY}


def register() -> None:
    """Both job bodies AND their queue, in the module that owns them."""
    core_jobs.set_job_handler(MONEY_PUSH_JOB, run_money_push_job)
    core_jobs.set_job_queue(MONEY_PUSH_JOB, work_push.WORK_QUEUE)
    core_jobs.set_job_handler(MONEY_SWEEP_JOB, run_money_sweep_job)
    core_jobs.set_job_queue(MONEY_SWEEP_JOB, work_push.WORK_QUEUE)


__all__ = [
    "ACTION_MONEY_PUSHED",
    "ACTION_MONEY_WAITING",
    "ACTION_PROCEEDED_FRESH",
    "ACTION_PROCEEDED_UNVERIFIED",
    "MONEY_FRESH_DEFAULT_MINUTES",
    "MONEY_PUSH_JOB",
    "MONEY_SWEEP_JOB",
    "install",
    "money_read",
    "paid_close_record",
    "record_proceed",
    "register",
    "sweep",
    "verdict",
]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-042@3e02d12e (CR-187-BRC10 Phase 13 T-33/T-34/T-35 — R16/R17/R18/R19/R26/R111; sha1[:8] of Rules.txt R16–R19 + WorkToDo.txt T-33..T-35, the design canvas of 2026-10-21)
# generated: 2026-10-21 by the CR-187 Phase 13 lane S-MONEY
# checklist: A✔ B✔ C✔ D✔ E=deferred(n/a — the native app's screens are other lanes') F✔ G✔ H✔ [work/0040 RLS is the 🔒 path]
# gates: pytest tests/test_cr187_money_freshness.py tests/test_cr187_money_push.py · tests/test_cr187_money_pg.py on PostgreSQL 16 · G78 · G109
# exceptions: the push is a one-minute poll of payments' changed-since seam, not an event — the repo has no inter-module event bus (stated in the docstring); `_deliver` addresses no provider, as `push.py` records
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-005 (EP-WRK-01) — the customers seam: an account, and the
#           premises a job on an account stands on.
# Rules:    BR-WRK-002 (read-only; one seam file per module) · BR-WRK-006 (an
#           account is an anchor) · CLAUDE.md hard rule 1
# Tests:    06-backend/tests/test_us_wrk_005_module.py (TC-6 · TC-7)
# Impacts:  apps/work/selectors.py
# ───────────────────────────────────────────────────────
"""work → customers: an account, and the five flow records. READ ONLY.

The Orders tab shows an account number beside a premise (`903 Birch Ln ·
A-10222` on Work-007); the raise from Customers' move-out (wave M) hands an
account id across. Neither writes a customer row: Work's account anchor is a
reviewed cross-module FK on `work_orders` (B2 §2, metering/0044) and the row
it points at is customers' to change.

⚠ **CR-070 WAVE P WIDENS THIS SEAM AND NOT ITS DIRECTION.** `US-WRK-039` asks
five customers-owned flows — an approved service request, a move-out, a move-in,
a transfer, a reconnect — to offer the field job that has to happen. To decide
WHICH job fits, Work has to read three facts about the flow: **the anchor** it
already stands on, **the services** it touches, and **the number** a clerk
quotes. Those are all customers' facts, so they are read here and nowhere else
in `apps/work` (`BR-WRK-002`, `G78`).

**Every reader below is a read, and each one answers `None` for an id belonging
to another utility** — the filter is the tenant in context and RLS `FORCE` sits
under it, which is HR-1 without a line of code (a cross-tenant id reads as
absent, never as forbidden).
"""

from __future__ import annotations

from typing import Any

from core import tenancy as core_tenancy


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def account(account_id: Any) -> dict[str, Any] | None:
    """One account of the tenant in context, or None."""
    from apps.customers import models as customers_models

    row = customers_models.Account.objects.filter(tenant_id=_tenant_id(), pk=account_id).first()
    if row is None:
        return None
    contact = _primary_contact(row.id)
    return {
        "id": str(row.id),
        "account_no": row.account_no,
        # `accounts.status` is a lookup row (B2 r5 #20), so its CODE is what travels.
        "status": getattr(getattr(row, "status", None), "code", None),
        "unit_id": str(row.unit_id) if row.unit_id else None,
        # ⚠ `CR-168-BRC10` P1.15, `DEF-WRK-9529` — *Miller, Sarah · (512)
        # 555-0114* (`US-WRK-042` TC-5). `mobile._customer_contact` asked for
        # these two keys from the day it was written and this seam never
        # served them, so tap-to-call was empty on every job. The account's
        # PRIMARY contact — the one Account detail shows and
        # `update_account_contact` edits — read live, never copied onto the job.
        "name": contact.full_name if contact is not None else None,
        "phone": (contact.phone or None) if contact is not None else None,
        # `DEF-WRK-9678` — OUR customer number (*Ana Alvarez · C-00001*,
        # images 03/04), read through customers' own resolver so the order
        # page and S17's CUSTOMER # column name the same holder (first link).
        "customer_no": _customer_no(row.id),
    }


def _customer_no(account_id: Any) -> str | None:
    from apps.customers import selectors as customers_selectors

    return customers_selectors.customer_nos_for([account_id]).get(str(account_id))


def _primary_contact(account_id: Any) -> Any:
    from apps.customers import models as customers_models

    return (
        customers_models.Contact.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, deleted_at__isnull=True
        )
        .order_by("-is_primary", "created_at", "id")
        .first()
    )


def unit_ids_with_account_no(text: str) -> Any:
    """A SUBQUERY of the units an account whose NUMBER contains `text` stands
    on — the *account number* leg of the field asset search (`CR-187-BRC10`
    T-40; requirement 37: *"Assets search serial, badge, device ID, address and
    account number"*). Any account of any status: a technician holding a
    closed account's letter is still looking for that meter. READ ONLY."""
    from apps.customers import models as customers_models

    return (
        customers_models.Account.objects.filter(
            tenant_id=_tenant_id(), account_no__icontains=text, unit_id__isnull=False
        ).values("unit_id")
    )


def current_account_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """The account IN FORCE on a unit today, or None (`CR-168-BRC10` P1.15).

    A job raised on a unit or a premises names no account, and the person to
    ring is whoever holds the unit now — walked like the address is walked
    (hard rule 8), never typed onto the job. *In force* is any status whose
    behaviour class is not `terminal` (`BR-CUS-055`): a Pending account is
    already the customer a technician will meet, a Closed one is not. The
    newest wins where two overlap (a move-in landing before the move-out).
    """
    from apps.customers import models as customers_models

    if not unit_id:
        return None
    row = (
        customers_models.Account.objects.filter(tenant_id=_tenant_id(), unit_id=unit_id)
        .exclude(status__behavior_class="terminal")
        .order_by("-created_at", "-id")
        .first()
    )
    return account(row.id) if row is not None else None



def account_service_codes(account_id: Any) -> list[str]:
    """The services this account takes RIGHT NOW, as service codes.

    `ended_on IS NULL` is *"still in force"* (`service_agreements`, B2 r5), and
    an agreement that ended is not a service somebody has to attend to. The walk
    is agreement → service point → service, which crosses into metering by
    RELATION and not by import: it is a read, in a seam, which is the one place
    `BR-WRK-002` allows it.

    Ordered by code so the panel offers the same list twice running — a proposal
    that reshuffles between two draws reads as two different answers.
    """
    from apps.customers import models as customers_models

    codes = (
        customers_models.ServiceAgreement.objects.filter(
            tenant_id=_tenant_id(), account_id=account_id, ended_on__isnull=True
        )
        .values_list("service_point__service__code", flat=True)
        .order_by("service_point__service__code")
    )
    return [str(code) for code in codes if code]


def service_request(request_id: Any) -> dict[str, Any] | None:
    """One application, with the two things a raise needs from it.

    ⚠ **`resolved_premises_id` AND `resolved_unit_id` CAN BOTH BE NULL, AND THAT
    IS THE WHOLE OF JUDGMENT 8.** `resolve_address` can leave a request pointing
    at an address that is not in the system yet — a request taken over the phone
    for a building nobody has entered. Such a request has **none of the four
    anchors** `ck_work_orders_has_anchor` accepts, so a job raised from it would
    be refused by the database. `from_flows` refuses it first, on the screen,
    with a sentence a clerk can read.
    """
    from apps.customers import models as customers_models

    row = (
        customers_models.ServiceRequest.objects.filter(tenant_id=_tenant_id(), pk=request_id)
        .only("id", "request_no", "state", "resolved_premises_id", "resolved_unit_id")
        .first()
    )
    if row is None:
        return None
    codes = (
        customers_models.ServiceRequestService.objects.filter(
            tenant_id=_tenant_id(), request_id=row.id
        )
        .values_list("service__code", flat=True)
        .order_by("service__code")
    )
    return {
        "id": str(row.id),
        "request_no": row.request_no,
        "state": row.state,
        "premises_id": str(row.resolved_premises_id) if row.resolved_premises_id else None,
        "unit_id": str(row.resolved_unit_id) if row.resolved_unit_id else None,
        "service_codes": [str(code) for code in codes if code],
    }


def move_record(move_record_id: Any) -> dict[str, Any] | None:
    """One completed move — `MVI-26-0001` or `MVO-26-0001` (`moves.MoveRecord`).

    This is what a move-out and a move-in raise AGAINST, and it exists only
    after the move has committed, which is exactly the posture judgment 7 asks
    for: the flow finishes first and the job is raised from the finished record.
    """
    from apps.customers import moves

    row = moves.MoveRecord.objects.filter(tenant_id=_tenant_id(), pk=move_record_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "move_no": row.move_no,
        "kind": row.kind,
        "account_id": str(row.account_id) if row.account_id else None,
        "from_account_id": str(row.from_account_id) if row.from_account_id else None,
    }


def transfer(transfer_id: Any) -> dict[str, Any] | None:
    """One property sale — `TRF-…`. The account does NOT move (PO 2026-09-01,
    *"dont create new account - we reassing that account"*), so the anchor is
    the account that was reassigned and the reads are done at its own unit."""
    from apps.customers import transfers

    row = transfers.Transfer.objects.filter(tenant_id=_tenant_id(), pk=transfer_id).first()
    if row is None:
        return None
    return {
        "id": str(row.id),
        "transfer_no": row.transfer_no,
        "state": row.state,
        "account_id": str(row.from_account_id) if row.from_account_id else None,
    }


def open_disconnect_case(account_id: Any) -> dict[str, Any] | None:
    """The open disconnect case on this account — `DSC-…` — or None.

    Keyed by ACCOUNT and not by case id because that is what the reconnect
    surface has in its hand: a clerk standing on an account that has paid.
    """
    from apps.customers import disconnects

    row = (
        disconnects.DisconnectCase.objects.filter(tenant_id=_tenant_id(), account_id=account_id)
        .exclude(state__in=disconnects.CLOSED_CASE_STATES)
        .order_by("-opened_on")
        .first()
    )
    if row is None:
        return None
    return {
        "id": str(row.id),
        "case_no": row.case_no,
        "state": row.state,
        "account_id": str(row.account_id) if row.account_id else None,
    }


def latest_disconnect_notice(account_id: Any) -> dict[str, Any] | None:
    """FB-023 F5 — the latest disconnect notice on the account's OPEN case:
    `{tier, issued_on, amount: {amount (4dp), display (2dp), currency}}`, or None.

    The AMOUNT is the case's `amount_owed_at_open` — the figure the ladder's
    letters state; `disconnect_notices` carries no amount of its own, so the
    case is the one source rather than a second guess. A notice on a CLOSED
    case (restored, stopped) is history, not this visit's, and reads as none.
    READ-ONLY.
    """
    from decimal import Decimal

    from apps.customers import disconnects
    from core import money as core_money

    if account_id is None:
        return None
    row = (
        disconnects.DisconnectNotice.objects.filter(
            tenant_id=_tenant_id(), case__account_id=account_id
        )
        .exclude(case__state__in=disconnects.CLOSED_CASE_STATES)
        .select_related("case")
        .order_by("-issued_on", "-created_at")
        .first()
    )
    if row is None:
        return None
    owed = row.case.amount_owed_at_open
    amount = (
        None
        if owed is None
        else {
            "amount": str(Decimal(owed).quantize(Decimal("0.0001"))),
            "display": str(core_money.finalize(Decimal(owed))),
            "currency": row.case.currency,
        }
    )
    return {"tier": row.tier, "issued_on": str(row.issued_on), "amount": amount}


# ── CR-070 wave M · the ACCOUNTS trigger reader (US-WRK-037, BR-WRK-033) ─────
#: FB-028 (PO 2026-10-31) — how long a notice's period runs, by its tier: the
#: tier NAMES the period (*10-day*, *48-hour*). A Reminder (`tier_1`) starts no
#: disconnect period and so ends none — it is not a disconnect notice
#: (decision log FB-028 built, judgment). Read from customers' own vocabulary.
NOTICE_PERIOD_DAYS: dict[str, int] = {"tier_2_10_day": 10, "tier_3_48_hour": 2}


def disconnect_notice_period(account_id: Any) -> dict[str, Any] | None:
    """FB-028 — the latest disconnect notice on the account's OPEN case and the
    day its period ends: `{tier, issued_on, ends_on}` (ISO dates), or None.

    PO 2026-10-31: *"stops if … the notice period isn't over"* — the notice's
    date plus its days (`NOTICE_PERIOD_DAYS`). `ends_on` is the LAST day of the
    period: on and before it the disconnect step stops; the day after, it may
    proceed. Worked: a 10-day notice of 26 Oct ends 5 Nov. A Reminder has no
    period (`ends_on` None). READ-ONLY — the same row
    `latest_disconnect_notice` reads.
    """
    from datetime import date, timedelta

    found = latest_disconnect_notice(account_id)
    if found is None:
        return None
    days = NOTICE_PERIOD_DAYS.get(found["tier"])
    issued = date.fromisoformat(found["issued_on"])
    return {
        "tier": found["tier"],
        "issued_on": found["issued_on"],
        "ends_on": (issued + timedelta(days=days)).isoformat() if days is not None else None,
    }


def protected_account(account_id: Any, *, as_of: Any) -> bool:
    """FB-028 (PO 2026-10-31, *"stops if … the account is protected"*) — True
    when ANY of customers' protections is in force on `as_of`: a medical
    certificate, a kept payment plan, or a weather moratorium
    (`disconnects.protections_for`, B18 §5.8.3's three). Each is a reason the
    ladder itself may not cut; a technician on the kerb is held to the same
    list (decision log FB-028 built, judgment). READ-ONLY."""
    from apps.customers import disconnects

    if account_id is None:
        return False
    return any(row["in_force"] for row in disconnects.protections_for(account_id, as_of=as_of))


def completed_occupancies(*, within_days: int = 7) -> list[dict[str, Any]]:
    """Move-ins that have COMMITTED — occupancy established. READ ONLY.

    Wave M's `occupancy_completed` trigger, and the execution plan's fifth
    reader (*"an occupancy wizard completed"*).

    ⚠ **A `MoveRecord` ROW *IS* THE COMPLETION, WHICH IS WHY THERE IS NO
    `completed` COLUMN TO FILTER ON.** `move_record()` directly above already
    records the posture in its own words: the row *"exists only after the move
    has committed"*. So the existence of a `kind = "move_in"` row is the fact
    the trigger fires on, and a lane looking for a status column here will not
    find one and must not add a guess.

    ⚠ **THE WINDOW IS WHAT STOPS THE FIRST SWEEP RAISING A JOB FOR EVERY MOVE-IN
    IN THE UTILITY'S HISTORY.** Idempotency (`work_order_rule_raises`) means it
    would only happen once — but once is enough to put four hundred jobs on a
    dispatcher's screen on the morning a rule is switched on, which is how a
    utility learns to leave rules off. `within_days` defaults to a week; the
    rule may widen it.
    """
    from datetime import timedelta

    from django.utils import timezone as dj_timezone

    from apps.customers import moves

    since = dj_timezone.now() - timedelta(days=max(1, int(within_days)))
    rows = moves.MoveRecord.objects.filter(
        tenant_id=_tenant_id(),
        kind=moves.KIND_MOVE_IN,
        performed_at__gte=since,
    ).order_by("-performed_at")

    return [
        {
            "id": str(row.id),
            "move_no": row.move_no,
            "account_id": str(row.account_id) if row.account_id else None,
            "effective_on": row.effective_on.isoformat() if row.effective_on else None,
        }
        for row in rows
    ]


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-WRK-005@87b94265 (EP-WRK-01)
# generated: 2026-09-03 by the CR-070 wave A build lane
# checklist: A✔ B✔ C✔ D=n/a E=n/a F✔ G✔ H=n/a
# gates: G78 · pytest tests/test_us_wrk_005_module.py
# exceptions: none
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

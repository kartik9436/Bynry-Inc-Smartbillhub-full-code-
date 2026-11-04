# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-016 (returned mail: mark returned → bad-address flag →
#           needs-attention → paper suppressed)   Screens: S30 · S35 · S32 · S21
# Rules:    BR-PAY-018 (a delivery record marked returned, single or bulk, sets
#           the account's bad-address flag, lands it in a needs-attention queue
#           and — per tenant config — suppresses paper until the address is
#           verified; BALANCES ARE UNAFFECTED; audited) · BR-NOT-005
#           (suppression operates on QUEUE ROWS, held and never deleted;
#           release re-queues) · BR-TEN-043 (event time is an argument) ·
#           CLAUDE.md rule 6 (marking the same piece twice writes one event) ·
#           rule 7 (audit)
# Tests:    06-backend/tests/test_us_pay_016_returned_mail.py ·
#           06-backend/tests/test_def_pay_6342_bad_address.py
# Impacts:  apps/payments/notices.py · apps/payments/collections_models.py ·
#           apps/payments/returned_mail_api.py (the list and the clear) ·
#           apps/customers/bad_address.py (owns `accounts.bad_address` per r12
#           #8 — WRITTEN BY CUSTOMERS, asked for from here by name) ·
#           apps/notifications/selectors.py (where each letter was addressed)
# ───────────────────────────────────────────────────────
"""The Tuesday chore — and the one thing that must not change while it happens.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling
of 2026-08-09; row in 12-governance/09-human-review-ledger.md. It is on the
guarded list for what it must NOT do: J18's invariance row is *"zero money rows
written or changed by the entire day's work"*, and this module is where that is
either true or quietly false.

**MONEY DOES NOT MOVE BECAUSE THE POST OFFICE FAILED.** BR-PAY-018 says
*"balances unaffected"* and J18 asserts it twice — all fourteen balances, due
dates, aging buckets and late-fee eligibility byte-identical before and after the
day's work, and the fourteen bill documents themselves untouched (returned ≠
reissued). There is no import in this file that can reach an invoice, a payment
or a journal line, and the test counts rows rather than reading this paragraph.

════════════════════════════════════════════════════════════════════════════
ONE BAD-ADDRESS FACT: `accounts.bad_address`, WRITTEN BY CUSTOMERS, ASKED FOR
FROM HERE (DEF-PAY-6342, 2026-09-23)
════════════════════════════════════════════════════════════════════════════
⚠ **THIS SECTION SAID THE FLAG WAS DERIVED FROM THIS MODULE'S EVENTS, AND FOR
SIX WEEKS THAT MEANT THERE WERE TWO FLAGS THAT NEVER MET.** `bad_address_for`
derived one from unresolved events; the account page, the unit page, the
collections runbook and the customer portal read the STORED column, which
nothing here wrote. A clerk pressed *Mark returned* and the account page went on
reading **Bad address: No**. Each module was right about its own boundary and
wrong about the others: this file said *"cannot set it"*, notifications said
*"that column is payments'"*, and customers' edit refusal said it was *"set by
returned-mail handling"*.

**The stored column is now the ONE fact** and `apps/customers/bad_address.py`
says why in full — it had five readers and two other legitimate writers, and a
derivation from return events can express neither an imported flag nor a
customer's own correction. This module ASKS customers to raise it
(`mark_returned`) and to lower it (`clear_account`, and `resolve_return` when an
account's last open return closes), by name — the `record_deposit_movement`
shape, because B1 still forbids this module writing `accounts`. The docstring's
old *"one migration in customers plus a call at the two points below"* was the
right ask; the migration already existed, and the two calls are now made.

**The events stay exactly what they were, and that is deliberate.** They are
the HISTORY — which letter, which address, when, and how it was resolved — and
they ARE the needs-attention list. The flag says *this account's post comes
back*; an event says *why we think so*.

════════════════════════════════════════════════════════════════════════════
SUPPRESSION: WHAT IS REAL TODAY AND WHAT IS NOT
════════════════════════════════════════════════════════════════════════════
BR-PAY-018 suppresses PAPER while an address is unverified, and BR-NOT-005 is
explicit that suppression holds the QUEUE ROW rather than dropping it —
*"written, never dispatched, never lost"* — so nothing is lost and everything
releases on verification.

Here is the honest state of that today, stated because a docstring claiming a
guarantee the code does not have is hard-won law 1:

* `paper_suppressed_for` answers the question and `notices.py` records the
  answer, so the DECISION exists and is auditable.
* **The `held` marker the dispatcher would read does not exist.**
  `outbound_messages` has no suppression column and `queue_document` takes no
  suppression argument — and payments may not add either, because that table is
  notifications' and the one cross-module write exception is the queue function
  itself.
* **Nothing dispatches at all in this release** (US-NOT-002 is unbuilt; email
  activation is R4), so no suppressed document can currently be mis-delivered.
  The gap is a future one and it is REPORTED with the exact ask: the dispatcher
  must consult this module — or carry a held marker — before it sends its first
  envelope.

Rows are still WRITTEN for a suppressed account, never skipped. A message that
was never queued leaves no trace anywhere, which is the failure mode
`apps/notifications/services.py` documents at length and refuses.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from importlib import import_module
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.payments.collections_models import DeliveryReturnEvent
from apps.payments.exceptions import PaymentRuleError
from core import audit
from core import tenancy as core_tenancy

#: J18's three outcomes, and they are three different facts. A single boolean
#: would lose the middle one — the address was already right and the carrier was
#: wrong — which is the one that stops a clerk chasing it again next Tuesday.
RESOLUTION_ADDRESS_CORRECTED = "address_corrected"
RESOLUTION_VERIFIED_CURRENT = "verified_current"
RESOLUTIONS = (RESOLUTION_ADDRESS_CORRECTED, RESOLUTION_VERIFIED_CURRENT)

#: Returned mail is a PAPER-channel event (US-PAY-016 TC-5). An email bounce
#: rides the queue's own `bounced` status (BR-BIL-016) and is not this flow —
#: conflating them would flag an account bad-address because a mailbox was full.
PAPER_CHANNEL = "pdf_print"

#: The customers module that owns `accounts.bad_address` and the three things
#: this file asks of it, BY NAME (B1 — named once so the contract is greppable
#: from both sides, the `DEPOSIT_REGISTER_WRITE` precedent).
CUSTOMERS_FLAG_MODULE = "apps.customers.bad_address"
FLAG_WRITE = "flag_bad_address"
FLAG_CLEAR = "clear_bad_address"
FLAGS_READ = "bad_address_flags"
#: Notifications' read of WHERE each returned letter was addressed — the
#: snapshot's `source` (`mailing_address` / `service_address`) is what routes
#: the clerk's clear step (PO ruling 2026-09-23: *"ensure you update correct
#: address - mailing or service"*).
LETTER_ADDRESS_MODULE = "apps.notifications.selectors"
LETTER_ADDRESS_READ = "delivery_addresses_for_messages"
#: Customers' page-wide read of account numbers and names (`DEF-MET-6304`).
ACCOUNT_CELLS_MODULE = "apps.customers.selectors"
ACCOUNT_CELLS_READ = "master_account_numbers"

#: Carried when customers publishes no flag writer. An unwired seam REPORTS; it
#: never answers as if the flag moved.
FLAG_UNWIRED = (
    "the return is recorded and the account's bad-address flag was NOT raised: "
    "apps.customers.bad_address.flag_bad_address is not published on this deployment."
)


def _published(module: str, attribute: str) -> Any:
    """The owning module's callable, or None — resolved at CALL time (B1)."""
    try:
        target = import_module(module)
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


@dataclass(frozen=True)
class ReturnResult:
    """One marked piece: the event, whether THIS call created it, and whether
    THIS call raised the account's flag (False on a second envelope from an
    account already flagged — a normal Tuesday)."""

    event_id: str
    account_id: str
    created: bool
    detail: str = ""
    flag_raised: bool = False


def _tenant_id() -> Any:
    from core import errors

    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def mark_returned(
    *,
    account_id: Any,
    returned_on: date,
    outbound_message_id: Any = None,
    source_type: str = "invoice",
    source_id: Any = None,
    channel: str = PAPER_CHANNEL,
    reason: str | None = None,
    actor: Any = None,
) -> ReturnResult:
    """Mark ONE delivery record returned (PE-16). Idempotent (TC-5).

    Marking the same envelope twice — the obvious accident on a stack of
    fourteen — writes ONE event. The DATABASE is the arbiter (`UNIQUE (tenant,
    outbound_message_id)`), not a SELECT-then-INSERT, because two clerks working
    the same stack is exactly the race a check in Python loses.

    `returned_on` is the business date and is an argument, never a clock
    (BR-TEN-043): Tuesday's stack is marked on Tuesday even when it is worked
    on Wednesday.
    """
    if channel != PAPER_CHANNEL:
        raise PaymentRuleError(
            f"returned mail is a PAPER-channel event and this record is {channel!r} "
            "(US-PAY-016 TC-5). An email that bounced rides the queue's own `bounced` "
            "status (BR-BIL-016); flagging the account bad-address for a full mailbox "
            "would suppress its paper bills for a reason that has nothing to do with "
            "where it lives.",
            br_ref="BR-PAY-018",
        )
    tenant_id = _tenant_id()
    # ⚠ **THE EVENT, ITS AUDIT ROW AND THE FLAG LAND TOGETHER OR NOT AT ALL
    # (`DEF-PAY-6342`).** The outer block is that promise; the inner one is a
    # SAVEPOINT and it is not tidiness — on PostgreSQL a refused INSERT aborts
    # the whole transaction, so the duplicate can only be caught and read back
    # if it is refused inside its own savepoint (hard-won law 14; proved on
    # PostgreSQL, see the lane report).
    with transaction.atomic():
        try:
            with transaction.atomic():
                event = DeliveryReturnEvent.objects.create(
                    tenant_id=tenant_id,
                    account_id=account_id,
                    outbound_message_id=outbound_message_id,
                    source_type=source_type,
                    source_id=source_id,
                    returned_on=returned_on,
                    reason=reason,
                    marked_by_id=getattr(actor, "id", None),
                )
        except IntegrityError:
            existing = DeliveryReturnEvent.objects.get(
                tenant_id=tenant_id, outbound_message_id=outbound_message_id
            )
            return ReturnResult(
                event_id=str(existing.pk),
                account_id=str(existing.account_id),
                created=False,
                detail="this piece was already marked returned; the database refused the "
                "duplicate (CLAUDE.md rule 6). One envelope, one event.",
            )
        audit.money_action(
            actor,
            "delivery.returned",
            "delivery_return_events",
            str(event.pk),
            after={
                "account_id": str(account_id),
                "returned_on": returned_on.isoformat(),
                "source_type": source_type,
                "bad_address": True,
                # J18 step 2 and step 6, recorded on the trail itself so a year-old
                # row states the invariance rather than leaving it to be assumed.
                "balances_affected": False,
                "documents_reissued": False,
            },
        )
        # BR-PAY-018's second arrow — *"→ account bad-address flag"* — asked of
        # the module that owns the column. It does NOT hold paper: that is
        # `notifications.delivery_ops.hold_paper_for_accounts`, out of this
        # release by PO ruling, and nothing here calls it.
        flag = _published(CUSTOMERS_FLAG_MODULE, FLAG_WRITE)
        if flag is None:
            return ReturnResult(
                event_id=str(event.pk),
                account_id=str(account_id),
                created=True,
                detail=FLAG_UNWIRED,
            )
        raised = flag(
            account_id,
            actor=actor,
            context={"delivery_return_event_id": str(event.pk)},
        )
    return ReturnResult(
        event_id=str(event.pk), account_id=str(account_id), created=True, flag_raised=raised
    )


def mark_returned_bulk(
    *,
    pieces: tuple[dict[str, Any], ...],
    returned_on: date,
    actor: Any = None,
) -> tuple[ReturnResult, ...]:
    """J18's 09:00 — **bulk-mark ×14 in one action**, with per-row results.

    Fourteen envelopes across fourteen accounts (or nine, J18's other fixture:
    twelve pieces de-duped to nine accounts) in one pass. Per-row results rather
    than one boolean, because a stack where one piece was already marked is a
    normal Tuesday and must not stop the other thirteen.
    """
    return tuple(
        mark_returned(
            account_id=piece["account_id"],
            returned_on=returned_on,
            outbound_message_id=piece.get("outbound_message_id"),
            source_type=piece.get("source_type", "invoice"),
            source_id=piece.get("source_id"),
            channel=piece.get("channel", PAPER_CHANNEL),
            reason=piece.get("reason"),
            actor=actor,
        )
        for piece in pieces
    )


def bad_address_for(account_id: Any) -> bool:
    """The flag — `accounts.bad_address`, read through customers (DEF-PAY-6342).

    It was DERIVED from this module's events until 2026-09-23 and every other
    screen read the column; see the module docstring. Refuses rather than
    answering False when customers publishes no read: *"not flagged"* and
    *"could not ask"* must never be the same answer.
    """
    read = _published(CUSTOMERS_FLAG_MODULE, FLAGS_READ)
    if read is None:
        raise PaymentRuleError(
            "apps.customers.bad_address.bad_address_flags is not published, so whether "
            "this account's post is coming back cannot be read.",
            br_ref="BR-PAY-018",
        )
    return str(account_id) in read([account_id])


def needs_attention(*, account_id: Any = None) -> QuerySet:
    """The needs-attention list — every UNRESOLVED return, oldest first.

    J18 step 5: *"2 open needs-attention rows that will age visibly — the queue
    never silently drops them."* Oldest-first ordering is what makes that true
    on a screen rather than in a docstring.

    ⚠ **A QUERYSET, NOT A TUPLE — `NFR-3`.** It replaced `needs_attention_queue()`,
    which built every open row of the tenant into a tuple; the caller pages this
    in SQL (`returned_mail_api`) and `needs_attention_rows` fills ONE page.
    """
    rows = DeliveryReturnEvent.objects.filter(tenant_id=_tenant_id(), resolved_on__isnull=True)
    if account_id not in (None, ""):
        rows = rows.filter(account_id=account_id)
    return rows.order_by("returned_on", "created_at", "id")


def needs_attention_rows(events: Any) -> list[dict[str, Any]]:
    """ONE PAGE of needs-attention rows, as a clerk reads them.

    Three reads for the page, whatever its size: this module's own rows (already
    in hand), customers' account numbers and names, and notifications' record of
    WHERE each letter was addressed. `went_to` is the snapshot's own `source` —
    `mailing_address`, `service_address`, or None for a letter queued before the
    service-address fallback existed, which carried no address at all.

    ⚠ `event_id` and `account_id` are the ACTION's keys and are never a visible
    value (B14 rule 31); `account_no` is what a person reads.
    """
    events = list(events or ())
    if not events:
        return []
    cells_read = _published(ACCOUNT_CELLS_MODULE, ACCOUNT_CELLS_READ)
    cells = cells_read([str(e.account_id) for e in events]) if cells_read else {}
    letters_read = _published(LETTER_ADDRESS_MODULE, LETTER_ADDRESS_READ)
    message_ids = [str(e.outbound_message_id) for e in events if e.outbound_message_id]
    letters = letters_read(message_ids) if (letters_read and message_ids) else {}
    rows = []
    for event in events:
        cell = cells.get(str(event.account_id)) or {}
        letter = letters.get(str(event.outbound_message_id)) or {}
        rows.append(
            {
                "event_id": str(event.pk),
                "account_id": str(event.account_id),
                "account_no": cell.get("account_no"),
                "customer_name": cell.get("name"),
                "returned_on": event.returned_on.isoformat(),
                "source_type": event.source_type,
                "went_to": letter.get("source"),
                "address": letter.get("address"),
            }
        )
    return rows


def paper_suppressed_for(account_id: Any, *, suppress_paper_on_bad_address: bool) -> bool:
    """Should paper be HELD for this account (BR-PAY-018, tenant config)?

    The config is an ARGUMENT and is not read here: it is a tenancy setting
    (S66, `suppress_paper_on_bad_address`) and a second reader of a tenant
    setting is a second place for it to be defaulted differently.

    Read the module docstring before relying on this: the decision exists and is
    recorded, and the queue-row marker a dispatcher would obey does not — and
    nothing dispatches in this release.
    """
    return bool(suppress_paper_on_bad_address) and bad_address_for(account_id)


def _resolve_one(
    event: DeliveryReturnEvent,
    *,
    resolution: str,
    resolved_on: date,
    actor: Any,
    context: dict[str, Any] | None = None,
) -> DeliveryReturnEvent:
    """Close ONE locked, open row and audit it — the kernel both doors share."""
    event.resolved_on = resolved_on
    event.resolution = resolution
    event.resolved_by_id = audit.actor_user_id(actor)
    event.save(update_fields=["resolved_on", "resolution", "resolved_by", "updated_at"])
    audit.money_action(
        actor,
        "bad_address.cleared",
        "delivery_return_events",
        str(event.pk),
        before={"resolved_on": None},
        after={
            "account_id": str(event.account_id),
            "resolution": resolution,
            "resolved_on": resolved_on.isoformat(),
            "balances_affected": False,
            **(context or {}),
        },
    )
    return event


def _clear_flag(account_id: Any, *, actor: Any, context: dict[str, Any]) -> bool:
    """Ask customers to lower `accounts.bad_address`. True when it moved."""
    clear = _published(CUSTOMERS_FLAG_MODULE, FLAG_CLEAR)
    if clear is None:
        raise PaymentRuleError(
            "apps.customers.bad_address.clear_bad_address is not published, so the "
            "account's bad-address flag cannot be cleared. Nothing was resolved.",
            br_ref="BR-PAY-018",
        )
    return bool(clear(account_id, actor=actor, context=context))


def _check_resolution(resolution: str) -> None:
    if resolution not in RESOLUTIONS:
        raise PaymentRuleError(
            f"unknown resolution {resolution!r}; J18 records {', '.join(RESOLUTIONS)}. A "
            "row closed with no outcome is a row that will be worked again next Tuesday.",
            br_ref="BR-PAY-018",
        )


def resolve_open_returns(
    *,
    account_id: Any,
    resolution: str,
    resolved_on: date,
    actor: Any = None,
    context: dict[str, Any] | None = None,
) -> tuple[DeliveryReturnEvent, ...]:
    """Close EVERY open return on one account, and nothing else.

    PUBLISHED FOR CUSTOMERS — the portal's *"returned post clears when the
    address is corrected"* (`BR-CWP-086`) resolves them as `address_corrected`
    with the customer named in `context`, and lowers its own flag itself. The
    flag is NOT touched here: the caller that owns it does that.
    """
    _check_resolution(resolution)
    with transaction.atomic():
        rows = list(
            DeliveryReturnEvent.objects.select_for_update()
            .filter(tenant_id=_tenant_id(), account_id=account_id, resolved_on__isnull=True)
            .order_by("returned_on", "created_at", "id")
        )
        return tuple(
            _resolve_one(
                row, resolution=resolution, resolved_on=resolved_on, actor=actor, context=context
            )
            for row in rows
        )


def clear_account(
    *, account_id: Any, resolution: str, resolved_on: date, actor: Any = None
) -> dict[str, Any]:
    """The clerk's clear step — every open return closed, then the flag lowered.

    ONE act from the account's banner, whatever the account holds: an account
    whose flag came from a MIGRATION has no return behind it at all and must
    still be clearable, which is why this is keyed on the account and not on an
    event. `resolution` says what the clerk found — the address was corrected
    (on the MAILING door for a mailing letter, or by ADDING a mailing address
    for a service letter; the edit itself is the owning module's and has
    already happened), or it was already right and the carrier was wrong.

    Refuses when there is nothing to clear, rather than writing an audit row
    that says a flag came down which was never up.
    """
    _check_resolution(resolution)
    with transaction.atomic():
        resolved = resolve_open_returns(
            account_id=account_id, resolution=resolution, resolved_on=resolved_on, actor=actor
        )
        lowered = _clear_flag(
            account_id,
            actor=actor,
            context={"resolution": resolution, "returns_resolved": len(resolved)},
        )
        if not resolved and not lowered:
            raise PaymentRuleError(
                "this account has no returned post open and no bad-address flag to clear.",
                br_ref="BR-PAY-018",
            )
    return {
        "account_id": str(account_id),
        "resolution": resolution,
        "resolved_on": resolved_on.isoformat(),
        "returns_resolved": len(resolved),
        "flag_cleared": lowered,
        "balances_affected": False,
    }


@transaction.atomic
def resolve_return(
    *,
    event_id: Any,
    resolution: str,
    resolved_on: date,
    actor: Any = None,
) -> DeliveryReturnEvent:
    """Close a needs-attention row (J18 steps 3 and 4). Two outcomes, both real.

    `address_corrected` — the address was wrong and the customers-module edit
    fixed it (that edit is NOT performed here; this records that it happened).
    `verified_current` — the address was already right and the carrier was
    wrong; the flag clears with a reason and no address changes.

    Clearing the flag releases the held paper (BR-PAY-018/BR-NOT-005) — see the
    module docstring for exactly how much of that release exists today.

    ⚠ **WHEN THIS CLOSES THE ACCOUNT'S LAST OPEN RETURN, THE FLAG COMES DOWN**
    (`DEF-PAY-6342`) — through customers, which owns it. An account with two
    envelopes out keeps its flag until both are dealt with.
    """
    _check_resolution(resolution)
    tenant_id = _tenant_id()
    event = DeliveryReturnEvent.objects.select_for_update().get(tenant_id=tenant_id, pk=event_id)
    if event.resolved_on is not None:
        raise PaymentRuleError(
            f"this returned piece was already resolved on {event.resolved_on} "
            f"({event.resolution}). Resolving it twice would overwrite the reason the "
            "first clerk recorded.",
            br_ref="BR-PAY-018",
        )
    _resolve_one(event, resolution=resolution, resolved_on=resolved_on, actor=actor)
    still_open = DeliveryReturnEvent.objects.filter(
        tenant_id=tenant_id, account_id=event.account_id, resolved_on__isnull=True
    ).exists()
    if not still_open:
        _clear_flag(event.account_id, actor=actor, context={"resolution": resolution})
    return event


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-016@7b2ce54 (ships with apps/payments/collections_models.py — the same four sources)
# generated: 2026-08-11 by story-coder (W5 corrections + notices lane)
# checklist: A✔ B✔ C✔ D✔(2026-08-16 — the API half is `POST /deliveries/returned`, notifications-owned by contract 11b §2.9 and mounted that morning; it hands every event to THIS module's `mark_returned_bulk` through `apps/notifications/payments_seam.py`, so the writer below is reached over HTTP. The two READS the screens needed landed with it: `apps/billing/selectors._deliveries_for` serves `returned_at` + `held` on a bill's delivery rows, and `f.returned` on `GET /outbound` is the stack still to work) E✔(2026-08-16 — S30's delivery rows carry "Mark returned" and a "Came back" date in BillDetailPage's DeliveryPanel, and S35's bulk mark opens from the S32 returned-mail chip; both are `07-frontend/src/features/payments/returnedMail.tsx`, PROVED IN A BROWSER against a real Django and Postgres — 20 assertions, `e2e/US-PAY-016-returned-mail.spec.ts`) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: see the lane report for the verbatim run · 2026-08-16 surface lane: 6 backend cases (tests/test_us_pay_016_surface.py), 51 frontend cases, both new reads and four screen guards RED-PROVED first
# amended: 2026-09-23 by the BAD-ADDRESS lane (DEF-PAY-6342) — exception (1)
#         below is REVERSED: the flag is `accounts.bad_address`, raised and
#         lowered by customers at this module's request, and the derived read
#         is gone. `needs_attention_queue` (an unpaged tuple) became the
#         paged `needs_attention` + `needs_attention_rows`; `account_banner`
#         (an English sentence with no caller) is DELETED — the banner is a
#         catalogue key on S21, rendered from the stored flag. `clear_account`
#         and `resolve_open_returns` are new.
# exceptions: (1) REVERSED 2026-09-23 — see `amended` above. It read:
#         "`accounts.bad_address` (r12 #8) IS NOT WRITTEN — customers-owned
#         and B1 forbids the cross-module write. The flag is DERIVED from
#         unresolved delivery-return rows." B1 still holds: customers writes
#         the column; this module asks.
#         (2) PAPER SUPPRESSION IS A DECISION, NOT YET AN EFFECT. There is no
#         `held` marker on `outbound_messages` and no suppression argument on
#         `queue_document`, and payments may not add either. Nothing dispatches
#         in this release, so nothing is currently mis-delivered — the gap is
#         named for the dispatcher lane (US-NOT-002).
#         (3) NO MONEY, ANYWHERE. J18's invariance row is the point of the
#         story; this module imports nothing that could reach an invoice, a
#         payment or a journal line.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

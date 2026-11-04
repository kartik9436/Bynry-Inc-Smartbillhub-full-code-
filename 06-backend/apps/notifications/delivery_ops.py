# ── Trace ──────────────────────────────────────────────
# Story:    US-NOT-013 (the platform delivery dashboard + re-queue) ·
#           US-NOT-014 (bounces + returned mail: queue statuses feeding the
#           bad-address flow; paper suppression honoured) ·
#           US-NOT-015 (queue read-models for reports + the W6 email consumers)
#           Screens: S8 · S30 · S35 · S46
# Rules:    BR-NOT-005 (per-run dashboard + re-queue are part of the ratified
#           queue model, platform-wide; statuses are forward-only and the
#           re-queue ACTION is the only reset) · BR-TEN-041 #8 (Settings →
#           Notifications IS the delivery/dispatch home) · BR-PAY-018 (returned
#           mail → bad-address flag → paper suppressed until verified; balances
#           unaffected; audited) · BR-REP-007 (delivery-queue health +
#           returned-mail canned reports are READ-MODELS over the queue) ·
#           BR-REP-017 / BR-LED-020 (scheduled-report and bookkeeper emails ride
#           the queue like every other message) · B1 (cross-module reads via
#           service functions only; notifications EMITS the return event and
#           never writes `accounts.bad_address`) · CLAUDE.md rule 1 (tenant
#           scoping) · rule 7 (every action audited)
# Tests:    06-backend/tests/test_us_not_013_015_delivery_ops.py ·
#           06-backend/tests/test_us_not_013_015_delivery_isolation.py
# Impacts:  apps/notifications/dispatcher.py (skips the rows this holds, and
#           picks up the rows this re-queues) · the S8 dashboard and the S30/S35
#           owner surfaces, which are frontend work NOT in this lane — their
#           US-IDs are in the docstring, because G10 reads any US-ID in this
#           block as a completion claim, Impacts lines included.
# ───────────────────────────────────────────────────────
"""Delivery operations: the platform dashboard, re-queue, returned mail, holds.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — re-queue is the ONE ratified reset of a
forward-only lifecycle (CLAUDE.md rule 6's territory: a re-queue that fired
twice would post a second disconnect notice), and the hold logic decides whether
a letter goes to an address already known to be wrong. AI-authored 2026-08-15
under the PO ruling of 2026-08-09; row required in
12-governance/09-human-review-ledger.md.

╔══════════════════════════════════════════════════════════════════════════╗
║  RE-QUEUE MUST CLEAR `batch_id`. THIS IS THE WHOLE REASON THE FUNCTION    ║
║  EXISTS, AND WITHOUT IT SOME ROWS COULD NEVER MOVE AGAIN.                 ║
╚══════════════════════════════════════════════════════════════════════════╝
`apps/notifications/dispatcher.py` claims a batch with one atomic UPDATE and
then — deliberately, by ruling — never re-selects a row it has claimed:

    Q(batch_id__isnull=True, next_attempt_at__isnull=True) | Q(next_attempt_at__lte=now)

A cycle that CRASHES between the claim and the provider result leaves its rows
`queued` **with a batch id and no next-attempt time**, which matches neither
branch. The dispatcher's own trailer states the trade and names the fix:

    "A CRASHED HAND-OFF LEAVES ITS ROWS CLAIMED AND UNSENT, FOREVER. Rule 6
     outranks liveness: nobody knows whether the provider accepted a batch the
     process died inside, and re-sending on the chance it did not would post a
     second disconnect notice. The recovery is US-NOT-013's re-queue, which is
     NOT built and which **must clear `batch_id`** when it is."

So `requeue` clears `batch_id`, `next_attempt_at` and `last_error` together. A
re-queue that reset only the STATUS would look like it worked on every screen —
the row would read `queued`, the audit row would be written, the toast would say
6 re-queued — and the dispatcher would never select one of them again. That is
the defect this paragraph exists to prevent, and a test asserts the cleared
column rather than the status.

────────────────────────────────────────────────────────────────────────────
WHAT RE-QUEUE MAY AND MAY NOT TOUCH
────────────────────────────────────────────────────────────────────────────
* **failed / bounced rows** — yes. US-NOT-013 TC-3: *"Status → queued; next
  dispatcher batch picks them within normal batch pacing — a re-queue never
  bypasses batching."* It does not send anything itself and it does not dispatch
  out of turn: it returns rows to the pool and the scheduler's next cycle takes
  at most the tenant's batch size, as always.
* **crashed-claim rows** — yes, and this is the case above. They are `queued`
  already; what they need is the batch id cleared.
* **HELD rows** — never. US-NOT-013 TC-4: *"Rejected with reason — held rows
  release only via address verification (BR-PAY-018), not re-queue."* A held row
  is a letter to an address a customer's mail already came back from; re-queueing
  it would post it to that address again.
* **sent / delivered rows** — never. That is not a re-queue, it is a second copy
  of a message the customer already has, and the ratified door for a deliberate
  extra copy is `copy_no` on a NEW row (US-NOT-011's re-send, US-BIL-024 TC-4).

────────────────────────────────────────────────────────────────────────────
⚠ TWO STATUSES ON THE DASHBOARD THAT NOTHING IN THIS REPO CAN PRODUCE
────────────────────────────────────────────────────────────────────────────
`delivered` and `bounced` are **provider facts**. `delivered` arrives on a
provider confirmation and `bounced` on an ESP webhook (US-NOT-014 TC-5, W6).
**No provider adapter exists on any channel** — print included — and none is
coming in this release: the PO ruled on 2026-08-15 that issuing a bill does not
mean the customer receives one, and the chain ends at a rendered document.

⚠ **ONE PRECISION ADDED 2026-08-17 (CR-009 in-app lane), because that sentence
is no longer literally true and its CONCLUSION is unchanged.** `in_app` is a
fourth channel whose adapter is this platform itself (BR-NOT-019), so in-app
rows do reach `sent`. They still never reach `delivered` or `bounced`, and for
exactly the reason above: those two are a CONFIRMATION and a WEBHOOK from a
third party, and a local adapter does not become a third party by delivering
successfully. Whether a person actually READ an in-app message is
`in_app_messages.read_at` — a different fact, in a different table, answering a
different question, and deliberately not folded into a delivery status.

So the counts for both are structurally zero, forever, on this deployment. That
is stated as DATA — `queue_health()["unpopulated_statuses"]` — and not only in
this docstring, because a dashboard showing "delivered: 0" beside "sent: 142"
reads as a delivery failure when the truth is that nobody is reporting. It is
the same lie `apps/billing/release.py` refuses about mandate coverage: *"'0 of
1,122 hold an address' and 'we could not count' must never render the same."*

The COLUMNS and the FLOW are built and tested (a bounce recorded by hand feeds
the same event stream). What is absent is the thing that would call them.

────────────────────────────────────────────────────────────────────────────
THE B1 BOUNDARY ON RETURNED MAIL (BR-PAY-018, r12 #8)
────────────────────────────────────────────────────────────────────────────
04-flows.md §4 routes it precisely: *"delivery-return event → payments consumes
→ accounts.bad_address ON"*. `mark_returned` stamps the queue row, audits it,
and RETURNS the event. It does not write `accounts.bad_address` — that column is
CUSTOMERS' (it said *"payments'/customers'"* until `DEF-PAY-6342`), and payments
asks customers to raise it. ⚠ A caller that ignores the returned event leaves
the account unflagged and nothing here can stop it; `POST /deliveries/returned`
is the caller that does not ignore it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.db import transaction
from django.db.models import Count, Q

from apps.notifications import models, tenancy_seam
from core import audit, errors
from core import tenancy as core_tenancy

#: The re-queue action's audit code — the field map §4 names it verbatim
#: (*"`audit_log` `delivery.requeued`"*).
AUDIT_REQUEUED = "delivery.requeued"
AUDIT_RETURNED = "delivery.returned"
AUDIT_RELEASED = "delivery.released"
AUDIT_HELD = "delivery.held"
AUDIT_ENTITY = "outbound_message"

#: Statuses a re-queue may act on. `sent` and `delivered` are deliberately
#: absent — see the module docstring.
#:
#: ⚠ **THIS TUPLE IS WHERE THE HARD/SOFT BOUNCE SPLIT IS ENFORCED, AND IT IS THE
#: WHOLE REASON THE TWO ARE SEPARATE STATUSES (`DEF-NOT-5626`, 2026-09-17).**
#:
#:   * `bounced_soft` IS here. A full mailbox or a busy server is temporary, so
#:     trying again is the correct thing to do and `BR-NOT-005`'s retry ×3 with
#:     backoff is the product's own answer to it.
#:   * `bounced_hard` is **NOT** here, and neither are `complained` or
#:     `unsubscribed`. The mailbox does not exist, or the person has told their
#:     provider they do not want this mail. Re-queueing any of the three sends
#:     again to an address we have been told in writing not to send to: it cannot
#:     succeed, it degrades the sending reputation every utility on this platform
#:     shares, and for a complaint it is the single fastest way to get a sender
#:     blocked outright.
#:
#: **So a clerk pressing *Re-queue* on a hard bounce is refused by the
#: VOCABULARY rather than by anybody remembering** — `requeue` reads this tuple
#: and returns a named refusal. `bounced` (legacy) stays here: it means *a
#: bounce of unknown kind*, and refusing a re-queue on a row nobody can classify
#: would take away the one action available on it.
REQUEUEABLE_STATUSES = (
    models.STATUS_FAILED,
    models.STATUS_BOUNCED,
    models.STATUS_BOUNCED_SOFT,
    models.STATUS_QUEUED,
)

#: The tenant setting BR-PAY-018 calls "(config)" — r14 #5's own key name, held
#: on the S70 Collections page and read through the seam. Not re-declared as a
#: notifications column: one home per setting.
SUPPRESSION_KEY = "suppress_paper_on_bad_address"

#: Why a row is held. A CODE, because the dashboard groups on it.
HELD_BAD_ADDRESS = "bad_address_paper_suppression"

#: Statuses that exist in the vocabulary and that NOTHING on this deployment can
#: write. Reported as data on every read-model — see the module docstring.
#:
#: ⚠ **THE FOUR NORMALISED OUTCOMES ADDED ON 2026-09-17 (`DEF-NOT-5626`) ARE
#: EQUALLY UNWRITABLE AND ARE DELIBERATELY *NOT* ON THIS TUPLE.** The reason is
#: what this tuple IS: a SCREEN-FACING declaration. Each value on it is paired
#: with a plain sentence in `delivery_counts.NOT_REPORTED` /
#: `NOT_REPORTED_MAILBOX`, it rides `GET /outbound/summary` to a clerk, and
#: `correspondence_reads._LEFT_THE_BUILDING` reads it to decide what a CUSTOMER
#: is told about their own document. Putting `bounced_hard` on it would print a
#: machine word on a clerk's screen with no sentence behind it (B14 rule 33 — a
#: fact is at most six words and rationale is zero words on screen), and would
#: silently make a hard-bounced portal document read *Sent*.
#:
#: **The machine-facing list is `models.PROVIDER_OUTCOME_STATUSES`** — six
#: values, all of them unwritable today for `BR-NOT-013`'s reason, and that is
#: the tuple an adapter maps onto.
#:
#: ⚠ **THE CONSEQUENCE, STATED RATHER THAN LEFT TO BE DISCOVERED (hard-won law
#: 1):** because these four are absent here, a row carrying one falls through
#: `_LEFT_THE_BUILDING` to `could_not_send` on the customer portal. For
#: `bounced_hard`, `bounced_soft` and `complained` that is the honest word. For
#: `unsubscribed` it is WRONG — that message did arrive, the person simply asked
#: for no more — and it is wrong on a screen a consumer reads. **Nothing writes
#: any of the four today, so nothing renders it today**; it becomes live on the
#: day the first adapter lands, which is why it is `DEF-NOT-5627` rather than a
#: comment.
UNPOPULATED_STATUSES = (models.STATUS_DELIVERED, models.STATUS_BOUNCED)


class DeliveryOpsRefused(Exception):
    """This delivery action cannot be performed, and here is why.

    Not a `core.errors` catalog exception for the reason `QueueWriteRefused`
    gives: a bulk re-queue runs over a selection where one refusable row must be
    one named break, not a dead action (BR-BIL-055's shape).
    """


@dataclass(frozen=True)
class RequeueOutcome:
    """One re-queue action: what moved, what refused, and why each refused."""

    requeued: tuple[str, ...] = ()
    refused: tuple[dict[str, Any], ...] = ()

    @property
    def toast(self) -> str:
        return f"Re-queued {len(self.requeued)} ✓" + (
            f" · {len(self.refused)} refused" if self.refused else ""
        )


@dataclass(frozen=True)
class DeliveryReturnEvent:
    """r12 #8's delivery-return event — for PAYMENTS to consume (B1).

    Notifications emits; payments records the needs-attention row and asks
    CUSTOMERS to set `accounts.bad_address`, which the S21 banner reads
    (US-PAY-016, `DEF-PAY-6342`). The field names match
    what a consumer needs and nothing more: no balance, no customer name
    (BR-AUD-006).
    """

    message_id: str
    account_id: Any
    channel: str
    returned_at: datetime


@dataclass(frozen=True)
class QueueHealth:
    """The dashboard's counts, and an honest account of what they cannot say."""

    counts: tuple[dict[str, Any], ...] = ()
    totals: dict[str, int] = field(default_factory=dict)
    held: int = 0
    returned: int = 0
    retry_exhausted: int = 0
    #: ⚠ The statuses nothing on this deployment can write. Carried as DATA so a
    #: screen renders "not reported" rather than a zero that reads as a failure.
    unpopulated_statuses: tuple[str, ...] = UNPOPULATED_STATUSES
    problems: tuple[dict[str, Any], ...] = ()


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def queue_health(*, source_type: str | None = None) -> QueueHealth:
    """US-NOT-013's counts and US-NOT-015's read-model — ONE query, one truth.

    US-NOT-013 §1: *"counts by type × channel × status"* across the WHOLE
    platform's outbound traffic. US-NOT-015 TC-1 asks the same question for the
    canned delivery-queue-health report and requires the same answer — *"the
    report renders what the rows say"* — so there is one function and not two.
    Two counters over one table is how a dashboard and a report come to disagree
    about the same day.

    This is also the B1 interface US-NOT-015 TC-5 demands: *"Reports module
    attempts a direct SELECT on `outbound_messages` → Forbidden — cross-module
    reads via service functions only; the read-model function IS the
    interface."*
    """
    tenant_id = _tenant_id()
    rows = models.OutboundMessage.objects.filter(tenant_id=tenant_id)
    if source_type:
        rows = rows.filter(source_type=source_type)

    counts = tuple(
        {
            "source_type": row["source_type"],
            "channel": row["channel"],
            "status": row["status"],
            "count": row["n"],
        }
        for row in rows.values("source_type", "channel", "status")
        .annotate(n=Count("id"))
        .order_by("source_type", "channel", "status")
    )
    totals: dict[str, int] = {}
    for entry in counts:
        totals[entry["status"]] = totals.get(entry["status"], 0) + entry["count"]

    problems = [
        {
            "code": "provider_statuses_never_written",
            "br_ref": "BR-NOT-005",
            "statuses": list(UNPOPULATED_STATUSES),
            "detail": "`delivered` and `bounced` are PROVIDER facts — a delivery "
            "confirmation and an ESP bounce webhook — and no provider adapter exists on "
            "any channel, print included: delivery is out of this release by PO ruling "
            "(2026-08-15). Their counts are structurally zero here and must be rendered "
            "as NOT REPORTED, never as zero: '0 delivered of 142 sent' reads as a "
            "delivery failure when the truth is that nobody is reporting.",
        }
    ]

    return QueueHealth(
        counts=counts,
        totals=totals,
        held=rows.filter(held=True).count(),
        returned=rows.filter(returned_at__isnull=False).count(),
        # US-NOT-015 TC-1's *"retry-exhausted list"* — rows that used all three
        # attempts and rest failed (BR-NOT-005's retry ×3).
        retry_exhausted=rows.filter(status=models.STATUS_FAILED, attempts__gte=3).count(),
        problems=tuple(problems),
    )


def failures(*, limit: int = 200) -> list[models.OutboundMessage]:
    """US-NOT-013 TC-2's failures/bounces list — *"failed+bounced sorted first"*.

    Carries the provider error text, the attempt count and the last-attempt
    time, because a dashboard that shows a failure without its reason sends an
    operator to the logs the platform exists to replace.
    """
    tenant_id = _tenant_id()
    return list(
        models.OutboundMessage.objects.filter(
            # ⚠ `models.ATTENTION_STATUSES`, not a hand-written pair: the partial
            # index under this query and `selectors._apply_order` read the same
            # tuple, so a new outcome appears on the screen built to show it
            # instead of being excluded by a copy nobody updated.
            tenant_id=tenant_id,
            status__in=models.ATTENTION_STATUSES,
        ).order_by("-created_at")[:limit]
    )


def _refusal(row: models.OutboundMessage, code: str, detail: str) -> dict[str, Any]:
    return {"message_id": str(row.pk), "code": code, "br_ref": "BR-NOT-005", "detail": detail}


@transaction.atomic
def requeue(*, message_ids: tuple[Any, ...], actor: Any) -> RequeueOutcome:
    """Return rows to the pool for the next batch (US-NOT-013 TC-3).

    ⚠ **CLEARS `batch_id`.** Read the module docstring's box before changing
    this: a re-queue that reset only the status would leave every crashed-claim
    row permanently invisible to the dispatcher while every screen said it had
    been re-queued.

    Refuses HELD rows (TC-4) and anything already `sent`/`delivered`. Every row
    that moves writes `delivery.requeued` (rule 7); every row that does not is
    returned with its reason, because a bulk action that silently skipped four
    of eleven rows is a bulk action nobody can trust.

    It does NOT dispatch. The next scheduled cycle takes at most the tenant's
    batch size, as always — *"a re-queue never bypasses batching"* (TC-3).
    """
    tenant_id = _tenant_id()
    rows = list(
        models.OutboundMessage.objects.filter(tenant_id=tenant_id, pk__in=list(message_ids))
    )
    found = {str(row.pk) for row in rows}
    refused: list[dict[str, Any]] = [
        {
            "message_id": str(message_id),
            "code": "not_found_in_this_tenant",
            "br_ref": "BR-TEN-003",
            "detail": "no such queue row in this tenant. Cross-tenant ids are "
            "indistinguishable from absent ones (HR-1) — US-NOT-013 TC-5: *'Re-queue via "
            "forged row ids from another tenant → Rejected, server-validated scope.'*",
        }
        for message_id in message_ids
        if str(message_id) not in found
    ]
    moved: list[str] = []

    for row in rows:
        if row.held:
            refused.append(
                _refusal(
                    row,
                    "held_row_not_requeueable",
                    "this row is HELD because the account's address is known to be bad "
                    "(BR-PAY-018). Held rows are released by ADDRESS VERIFICATION and by "
                    "nothing else — re-queueing one would post the same letter to the "
                    "same wrong address again (US-NOT-013 TC-4).",
                )
            )
            continue
        if row.status in (models.STATUS_SENT, models.STATUS_DELIVERED):
            refused.append(
                _refusal(
                    row,
                    "already_sent_not_requeueable",
                    f"this row is {row.status!r} — the customer already has it. Re-queueing "
                    "it would be a SECOND copy, and the ratified door for a deliberate "
                    "extra copy is a NEW row with `copy_no` > 0 (US-NOT-011's re-send), "
                    "which records that a human asked for it.",
                )
            )
            continue
        if row.status not in REQUEUEABLE_STATUSES:
            # ⚠ **THIS BRANCH WAS `pragma: no cover - defensive` UNTIL
            # 2026-09-17 AND IT IS NOW THE HARD/SOFT BOUNCE GUARD**
            # (`DEF-NOT-5626`). Nothing could reach it while the vocabulary held
            # five values; `bounced_hard`, `complained` and `unsubscribed` reach
            # it, and what happens here is the whole reason those are separate
            # words from `bounced_soft`.
            #
            # The sentence is written for the CLERK who pressed the button, not
            # for a log: they are looking at a message that did not arrive and
            # the obvious next move is to send it again.
            refused.append(
                _refusal(
                    row,
                    "status_not_requeueable",
                    {
                        models.STATUS_BOUNCED_HARD: (
                            "this email HARD bounced — the provider says that mailbox does "
                            "not exist. Sending it again cannot succeed, and enough refused "
                            "messages degrade the sending reputation every utility on this "
                            "platform shares. The customer still gets this document: print "
                            "is the floor on every customer document (BR-NOT-024) and that "
                            "row was never touched. Correct the address and the block on it "
                            "can be released."
                        ),
                        models.STATUS_COMPLAINED: (
                            "this customer marked our email as spam, and their provider told "
                            "ours. Sending again is the fastest way for a sender to be "
                            "blocked outright. Their printed copy is unaffected "
                            "(BR-NOT-024)."
                        ),
                        models.STATUS_UNSUBSCRIBED: (
                            "this customer used the unsubscribe link. Re-queueing would send "
                            "them the thing they asked not to receive. Their printed copy is "
                            "unaffected (BR-NOT-024)."
                        ),
                    }.get(
                        row.status,
                        f"status {row.status!r} cannot re-queue.",
                    ),
                )
            )
            continue

        before = {
            "status": row.status,
            "batch_id": str(row.batch_id) if row.batch_id else None,
            "attempts": row.attempts,
        }
        row.status = models.STATUS_QUEUED
        # THE THREE COLUMNS THAT MATTER. `batch_id` is the one a crashed hand-off
        # left behind; `next_attempt_at` is the one a backoff left behind; and
        # `last_error` is stale the moment the row is eligible again.
        row.batch_id = None
        row.next_attempt_at = None
        row.last_error = None
        row.save(
            update_fields=["status", "batch_id", "next_attempt_at", "last_error", "updated_at"]
        )
        audit.money_action(
            actor,
            AUDIT_REQUEUED,
            AUDIT_ENTITY,
            str(row.pk),
            before=before,
            after={
                "status": models.STATUS_QUEUED,
                "batch_id": None,
                # attempts are NOT reset: BR-NOT-005's retry ×3 counts PROVIDER
                # attempts, and zeroing them would hand a chronically failing
                # address three more tries every time somebody clicked.
                "attempts": row.attempts,
                "dispatched": False,
            },
        )
        moved.append(str(row.pk))

    return RequeueOutcome(requeued=tuple(moved), refused=tuple(refused))


@transaction.atomic
def mark_returned(
    *, message_ids: tuple[Any, ...], at: datetime, actor: Any
) -> tuple[tuple[DeliveryReturnEvent, ...], tuple[dict[str, Any], ...]]:
    """US-NOT-014 TC-1/TC-2: a paper letter came back (single or bulk).

    Returns `(events, refusals)`. The EVENTS are r12 #8's delivery-return
    events, for payments to consume — this module never writes
    `accounts.bad_address` (B1). ⚠ A caller that ignores them leaves the account
    unflagged; REPORTED rather than fixed by crossing the boundary.

    * **Paper rows only** (TC-6): an email row cannot be "returned" — a bounce is
      a provider fact on a webhook, not a staff observation, and letting staff
      mark one would put a hand-typed value where an ESP's answer belongs.
    * **Idempotent** (TC-6): marking the same row twice is a no-op and emits no
      second event, so a double-clicked bulk action does not flag an account
      twice.
    * **The status does not move.** A returned letter WAS sent; overwriting that
      would destroy the fact an auditor needs. `returned_at` stamps it instead.
    * **Balances are unaffected** (BR-PAY-018) — nothing here touches money, and
      the audit action is a delivery action, not a money action.
    """
    tenant_id = _tenant_id()
    rows = list(
        models.OutboundMessage.objects.filter(tenant_id=tenant_id, pk__in=list(message_ids))
    )
    events: list[DeliveryReturnEvent] = []
    refused: list[dict[str, Any]] = []

    for row in rows:
        if row.channel != models.CHANNEL_PRINT:
            refused.append(
                _refusal(
                    row,
                    "not_a_paper_row",
                    f"only PAPER rows can be marked returned; this one is {row.channel!r}. "
                    "An email that did not arrive comes back as a provider BOUNCE on a "
                    "webhook (US-NOT-014 TC-5), which is a fact from the ESP — not "
                    "something a clerk can observe about an envelope.",
                )
            )
            continue
        if row.returned_at is not None:
            # Idempotent by design: no second event, no second flag.
            continue
        row.returned_at = at
        row.returned_by = getattr(actor, "id", None)
        row.save(update_fields=["returned_at", "returned_by", "updated_at"])
        audit.money_action(
            actor,
            AUDIT_RETURNED,
            AUDIT_ENTITY,
            str(row.pk),
            after={
                "channel": row.channel,
                "returned_at": at.isoformat(),
                "balances_affected": False,  # BR-PAY-018, stated on the trail
                "account_id": str(row.account_id) if row.account_id else None,
            },
        )
        events.append(
            DeliveryReturnEvent(
                message_id=str(row.pk),
                account_id=row.account_id,
                channel=row.channel,
                returned_at=at,
            )
        )

    return tuple(events), tuple(refused)


def paper_suppression_active() -> bool:
    """BR-PAY-018's *"(config)"* — the tenant's `suppress_paper_on_bad_address`.

    Read from the S70 Collections page through the tenancy seam. Refuses rather
    than defaulting if the settings read is unpublished: guessing ON would hold
    letters a utility never asked to hold, and guessing OFF would post letters to
    addresses their own mail already came back from.
    """
    config = tenancy_seam.collections_config()
    if SUPPRESSION_KEY not in config:
        raise DeliveryOpsRefused(
            f"this tenant's collections settings carry no {SUPPRESSION_KEY!r}, so whether "
            "paper is suppressed for bad-address accounts cannot be known. Neither default "
            "is safe: ON holds letters nobody asked to hold, OFF posts letters to an "
            "address the customer's own mail already came back from (BR-PAY-018)."
        )
    return bool(config[SUPPRESSION_KEY])


@transaction.atomic
def hold_paper_for_accounts(
    *, account_ids: tuple[Any, ...], actor: Any, reason: str = HELD_BAD_ADDRESS
) -> tuple[str, ...]:
    """US-NOT-014 TC-3: suppression ON → new paper rows are *"written, marked
    held, never dispatched, never lost"*.

    Called when payments flags an account bad-address (US-PAY-016 consumes the
    return event, then calls back here). Only PAPER rows are held — *"email/SMS
    rows unaffected; their own rails"* — and only rows still `queued`: a letter
    already sent cannot be un-sent.

    Refuses outright when suppression is OFF, rather than holding anyway: the
    tenant said not to, and a hold nobody configured is a bill that silently
    never arrives.
    """
    tenant_id = _tenant_id()
    if not paper_suppression_active():
        raise DeliveryOpsRefused(
            "this tenant has `suppress_paper_on_bad_address` OFF, so paper is NOT held for "
            "bad-address accounts (BR-PAY-018 makes the suppression config). Holding anyway "
            "would stop bills reaching customers the utility chose to keep posting to."
        )
    rows = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id,
        account_id__in=list(account_ids),
        channel=models.CHANNEL_PRINT,
        status=models.STATUS_QUEUED,
        held=False,
    )
    held_ids = [str(row.pk) for row in rows]
    rows.update(held=True, held_reason=reason)
    for message_id in held_ids:
        audit.money_action(
            actor, AUDIT_HELD, AUDIT_ENTITY, message_id, after={"held": True, "reason": reason}
        )
    return tuple(held_ids)


@transaction.atomic
def release_held_for_accounts(*, account_ids: tuple[Any, ...], actor: Any) -> tuple[str, ...]:
    """US-NOT-014 TC-4: *"Address verified → Held rows released; next batch
    dispatches them; release audited."*

    This is the ONLY door out of `held` — US-NOT-013 TC-4 refuses the other one
    by name. Nothing is re-rendered and nothing is re-created: the same rows,
    with the same pins and the same recipient snapshots, become selectable again.
    """
    tenant_id = _tenant_id()
    rows = models.OutboundMessage.objects.filter(
        tenant_id=tenant_id, account_id__in=list(account_ids), held=True
    )
    released = [str(row.pk) for row in rows]
    rows.update(held=False, held_reason=None)
    for message_id in released:
        audit.money_action(
            actor,
            AUDIT_RELEASED,
            AUDIT_ENTITY,
            message_id,
            before={"held": True},
            after={"held": False, "released_by": "address_verified"},
        )
    return tuple(released)


def returned_mail_read_model(*, limit: int = 500) -> list[dict[str, Any]]:
    """US-NOT-015 TC-2's returned-mail report feed, through the B1 interface.

    Read-only, tenant-scoped, and it carries the ACCOUNT id rather than the
    customer's name (BR-AUD-006's posture applied to a report feed): the report
    engine joins names through customers' own reads, which is where the
    permission to see them is enforced.
    """
    tenant_id = _tenant_id()
    return [
        {
            "message_id": str(row.pk),
            "account_id": str(row.account_id) if row.account_id else None,
            "channel": row.channel,
            "source_type": row.source_type,
            "template_code": row.template_code,
            "returned_at": row.returned_at,
            "held": row.held,
        }
        for row in models.OutboundMessage.objects.filter(
            tenant_id=tenant_id, returned_at__isnull=False
        ).order_by("-returned_at")[:limit]
    ]


def deferred_backlog() -> dict[str, int]:
    """US-NOT-013 §1's *"deferred channels show their queued backlogs with
    badges"*, and US-NOT-015 TC-6's guarantee in the same numbers: a report or
    bookkeeper email resting `queued` is NEVER shown as sent.

    Counts queued rows per channel. On this deployment every channel's backlog
    is its whole traffic, because nothing dispatches at all (PO ruling
    2026-08-15) — which the dashboard should say plainly rather than badge as
    three separate channel problems.
    """
    tenant_id = _tenant_id()
    return {
        row["channel"]: row["n"]
        for row in models.OutboundMessage.objects.filter(
            tenant_id=tenant_id, status=models.STATUS_QUEUED
        )
        .values("channel")
        .annotate(n=Count("id"))
        .order_by("channel")
    }


def selectable_filter() -> Q:
    """The `held` half of the dispatcher's selection predicate (BR-PAY-018).

    Lives here rather than in `dispatcher.py` so the rule and its reason stay
    with the story that owns them; the dispatcher ANDs it into `_selectable`.
    """
    return Q(held=False)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-NOT-013@6c2a90f (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/05-modules/10-notifications/06-epics/EP-NOT-04-delivery-ops.md — US-NOT-013/014/015 §1/§3/§5 — · 10-notifications/02-business-rules.md — BR-NOT-005 — · 10-notifications/04-flows.md §4 + §6 (the bad-address flow and the dispatch home) · 08-qa/01-e2e/journeys/J18-returned-mail-tuesday.md + J17-delivery-life.md)
# generated: 2026-08-15 by story-coder (W3/W4 notifications CONTENT lane — delivery ops)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
#         CORRECTED 2026-08-16 (surface-debt tails lane), hard-won law 1: both
#         marks read `deferred` and had been FALSE since 2026-08-16 morning.
#         `GET /outbound/summary` (apps/notifications/api.py) serves BOTH
#         `queue_health` and `deferred_backlog` — US-NOT-015's read-models, the
#         B1 interface its TC-5 demands — and the S8 Notifications tab draws
#         them. The stale marks were counting US-NOT-015 as an unreachable
#         story in `10-scripts/gates/surface_debt.txt` over a route and a screen
#         that both exist. What is still absent is NOT this story's surface: the
#         canned S46 report is reports-owned and the W6 bookkeeper/report EMAIL
#         consumers need a dispatcher, which is R3 by PO ruling.
# gates: ruff✔ black✔ · pytest tests/test_us_not_013_015_delivery_ops.py ·
#         THREE guards proved RED before green (hard-won law 7): the `batch_id`
#         clear (a crashed-claim row stayed invisible to the dispatcher), the
#         held-row refusal, and the paper-only mark-returned. Transcripts in the
#         lane report
# exceptions: (1) `delivered` AND `bounced` CANNOT BE WRITTEN BY ANYTHING IN THIS
#         REPO. Both are provider facts and no provider adapter exists on any
#         channel — delivery is out of this release by PO ruling (2026-08-15).
#         The columns and the flow are built and tested; the populating half is
#         absent, and `queue_health().unpopulated_statuses` states it as DATA so
#         a screen renders "not reported" rather than a zero that reads as a
#         delivery failure.
#         (2) NOTHING HERE WRITES `accounts.bad_address` (r12 #8 — CUSTOMERS',
#         at payments' request since DEF-PAY-6342; this line said "payments'").
#         `mark_returned` emits the delivery-return event; a caller that ignores
#         it leaves the account unflagged and nothing here can stop that.
#         REPORTED rather than fixed by a cross-module write.
#         (3) RE-QUEUE DOES NOT RESET `attempts`. BR-NOT-005 counts PROVIDER
#         attempts; zeroing them would give a chronically failing address three
#         fresh tries on every click.
#         (4) NO ENDPOINT AND NO SCREEN. The S8 dashboard is frontend work under
#         `07-frontend/src/features/tenancy/`, which this lane was told not to
#         touch — so these functions are built and NOTHING CALLS THEM from a UI
#         yet (hard-won law 2: built is not wired). REPORTED, loudly, rather than
#         left to look finished.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

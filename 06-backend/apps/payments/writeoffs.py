# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-012 (write-offs: initiated in Payments, approved + reported
#           in Finance)   Screens: S34 · S35 · S36
# Rules:    BR-PAY-020 (INITIATED in payments, APPROVED + reported in finance,
#           Owner/Admin, bad-debt GL) · BR-PAY-002 (append-only — an erroneous
#           write-off is corrected by a new row, never an edit) · BR-PAY-037
#           (the same user may initiate AND approve in v1 — both acts recorded
#           distinctly) · BR-PAY-016 as amended (a write-off CLOSES a payment
#           plan — PO 2026-08-12, OQ-171) · BR-BIL-013 (small-balance final-bill
#           write-offs are BILLING's automatic path, not this one) ·
#           CLAUDE.md rule 1 · rule 2 · rule 4 · rule 5 · rule 7
# Tests:    06-backend/tests/test_us_pay_012_write_offs.py
# Impacts:  apps/payments/collections_models.WriteOff (the row) ·
#           apps/payments/ledger_seam (the DR write-off / CR AR handoff) ·
#           apps/payments/dunning.close_plan_on_write_off (OQ-171) ·
#           apps/payments/summary.py (write-offs YTD) · apps/payments/api.py
# ───────────────────────────────────────────────────────
"""A debt the utility stops chasing — and the approval that gates the money.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this file permanently reduces receivables
and asks the ledger to post bad debt, which is a CLAUDE.md 🔒 path (ledger
posting). AI-authored 2026-08-15 under the PO ruling of 2026-08-09; row in
12-governance/09-human-review-ledger.md.

BR-PAY-020, CONFIRMED: *"Write-offs: INITIATED in Payments (S34/S35
outstandings, operational), APPROVED + reported in Finance (Owner/Admin,
bad-debt GL); payments owns the transaction record, ledger posts, finance
reports"*. Three modules, three verbs, and this file owns exactly one of them.

════════════════════════════════════════════════════════════════════════════
NOTHING MONEY-BEARING HAPPENS AT INITIATION. THAT IS THE WHOLE CONTROL.
════════════════════════════════════════════════════════════════════════════
US-PAY-012 TC-1, verbatim: a request produces a *"pending-approval record; NO
balance/ledger effect yet"*. So `request_write_off` writes ONE row and an audit
entry and asks the ledger for nothing at all. `approve_write_off` is where
**DR write-off / CR accounts receivable** posts — worked, on TC-2's own figures:
**948.20 / 948.20**, balanced.

⚠ **THIS PARAGRAPH ENDED "and the account's outstanding balance falls to 0.00
because the allocation the posting represents settles its bills" UNTIL
2026-09-01, AND THERE IS NO SUCH ALLOCATION (DEF-3121).** Measured on TC-2's own
figures: before the write-off the account owes **948.20** at **91 days late**;
after the approval it owes **948.20** at **91 days late**, while the ledger has
credited receivables by 948.20. `billing_seam.outstanding_positions` is
Σ(bill totals) − Σ(`allocations`), and nothing on this path writes an allocation
row or touches an invoice — so the debt stays on S34 and in the collection
ladder, and the utility keeps chasing a customer it has stopped chasing. Filed,
NOT fixed here: closing it writes money onto the allocation path, which is
another task's. Hard-won law 1 — the sentence is corrected rather than left to
rot, because the next lane would have built on it.

The two acts are recorded separately (BR-PAY-037: *"the SAME user holding the
approver role MAY initiate AND approve in v1 — both acts recorded distinctly"*),
which is why the row carries four columns rather than an `approved` boolean —
the audit trail IS the separation-of-duties control in v1, and half of it would
be missing.

════════════════════════════════════════════════════════════════════════════
A WRITE-OFF CLOSES A PAYMENT PLAN (PO 2026-08-12, OQ-171)
════════════════════════════════════════════════════════════════════════════
Verbatim in the flows document: *"`closed` is reached by paying every instalment
OR by the utility WRITING THE ARREARS OFF … never automatically"*. There is no
`void` and there never was a drop-off (PO 2026-08-11, *"nodrop we chase for
payments until write off"*) — this IS the end of the chase, and it has a human
on it. `dunning.close_plan_on_write_off` is the closure and it is called from
the APPROVAL, not from the request: a plan closed by a request nobody approved
would let an account take a second plan on a debt it still owes.

════════════════════════════════════════════════════════════════════════════
THE QUEUE — WITHOUT IT THE TWO-PERSON SPLIT IS NOMINAL (DEF-100)
════════════════════════════════════════════════════════════════════════════
This file shipped `request_write_off` and `approve_write_off` and **no read at
all**, and `apps/payments/api.py` served `/write-offs` POST-only. The
consequence is not a missing convenience: *"which write-offs are awaiting my
approval?"* had no answer anywhere in the product, so the ONLY write-off id a
browser could hold was the one the requester's own screen had just minted. The
Approve button therefore had to sit beside the request, in the requester's hand,
in the same breath — and BR-PAY-020's whole point is that the approval happens
on a **different screen, in Finance**.

`write_off_queue` is that read, and it is the entire fix. It changes no rule:
**BR-PAY-037 stands unchanged** — *"the SAME user holding the approver role MAY
initiate AND approve in v1 — both acts recorded distinctly; enforced
separation-of-duties = v2"*. Nothing here refuses a self-approval, because a
CONFIRMED rule permits it and an implementing lane does not overturn one. What
the read buys is the SCREEN separation the rule does specify: the queue can be
listed in Finance, so the Approve control lives there and the requester's screen
keeps the request and loses the approval.

The read is a READ. It moves no money, and the money statement it makes is the
one the rows already carry: a **948.20** request sits at `requested` with
`posted_to_ledger` false until an Owner/Admin approves it, and then and only
then does DR write-off / CR AR post.
════════════════════════════════════════════════════════════════════════════
TWO MORE VERBS — CR-059 CS-25 (2026-09-01), AND THEY ARE DIFFERENT SHAPES
════════════════════════════════════════════════════════════════════════════
CS-25: *"Today an approver can only approve it or ignore it, and the queue fills
with requests nobody will action. Worse: once approved, receivables have been
permanently reduced and there is no path back."*

  * **`reject_write_off`** — a STATUS MOVE on the request. It moves no money and
    it is not a deletion, and it is lawful in place precisely because the row it
    lands on has posted nothing: there is nothing to correct, only a decision to
    record.
  * **`reverse_write_off`** — a **NEW ROW**, because the row it corrects HAS
    posted. Hard rule 4 in one sentence, and CS-25 says the same thing:
    *"corrected by a reversing write-off row and a mirrored ledger entry, never
    by editing or deleting the original"*. It asks the ledger for **its own
    mirror** and composes no compensating entry, it reopens the payment plan the
    approval closed, and the debt returns at its **ORIGINAL age** because
    neither path ever moved a due date.

Both are Admin-gated **in the service** (`@require_role(SYSTEM_ADMIN)`), so a
job, a shell or a second endpoint that forgot to gate is refused all the same
(BR-SHL-025), and both write `audit_log` (hard rule 7).

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT DO
════════════════════════════════════════════════════════════════════════════
  * **No allowance for doubtful debts, and that is a live decision elsewhere.**
    Everything here is DIRECT write-off — the debt is recognised as a loss when
    a human says so. Whether that is acceptable at all is `CR-060 C5`, an open
    market-entry question (under IFRS 9 and Ind AS 109 an allowance model is
    required; for the US municipal and submetering customers this product ships
    to today, direct write-off is fine). **CS-25 and CS-26 specify direct
    write-off and that is what is built.** No provision account, no ageing-based
    estimate, no reversal of a provision — an allowance model would pre-empt
    that decision, so it is named here instead.
  * **No agency referral and no future-deposit flag.** Both are prototype
    checkboxes with NO ratified rule (field-map P-4/P-5) and US-PAY-012 §1
    excludes them from v1 by name. The columns do not exist, so no path can
    write them.
  * **No small-balance automatic write-off.** BR-BIL-013 path 5 is billing's
    and settles a final bill under the tenant's threshold; this is the MANUAL
    collections write-off and the two must not be confused in a bad-debt report.
  * **No recovery handling.** US-PAY-012 TC-4: a payment arriving after a
    write-off is recorded normally through US-PAY-001, as a NEW event. This row
    is never edited (BR-PAY-002) and nothing here reopens it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from core import audit as core_audit
from core import permissions
from core import tenancy as core_tenancy

from apps.payments import billing_seam, dunning, ledger_seam, plans, settings_seam
from apps.payments.collections_models import (
    WRITE_OFF_APPROVED,
    WRITE_OFF_REASONS,
    WRITE_OFF_REJECTED,
    WRITE_OFF_REQUESTED,
    WRITE_OFF_REVERSED,
    WRITE_OFF_STATUSES,
    WriteOff,
)
from apps.payments.exceptions import PaymentRuleError

ZERO = Decimal("0")

AUDIT_REQUESTED = "write_off.requested"
AUDIT_APPROVED = "write_off.approved"
#: CR-059 CS-25. Two more money actions, and hard rule 7 wants both: a rejection
#: moves no money but it CLOSES a money decision, and a reversal puts a
#: receivable back on the books.
AUDIT_REJECTED = "write_off.rejected"
AUDIT_REVERSED = "write_off.reversed"

# ══════════════════════════════════════════════════════════════════════════
# CR-048 WAVE B TASK B11 — THE WRITE-OFF LETTER
# ══════════════════════════════════════════════════════════════════════════
# `catalogs.LISTINGS["writeoff_notice"]` has said the same sentence since
# 2026-08-16: *"Not in use yet — approving a write-off does not send a letter."*
# It does now. The wording was seeded on every tenant, editable, and reachable
# by nothing — one of the sixteen the 2026-08-29 teardown counted.
#: The queue, resolved BY NAME (B1) — payments imports nothing of
#: notifications', so both strings below are pinned by a test rather than by an
#: import that would make them symbols.
QUEUE_MODULE = "notifications"
QUEUE_WRITE = "queue_document"

#: The SET-12 event. Checked against `rule_catalog.EVENT_KEYS` before it was
#: written down — `queue_document` REFUSES an event this platform cannot fire.
EVENT_WRITE_OFF_APPROVED = "write_off_approved"

#: The wording. ⚠ NOT the write-off REASON and not the audit action: a template
#: code is not a document type (DEF-2511), and a row pinned to a code no
#: catalogue declares renders as nothing anybody wrote.
WRITE_OFF_TEMPLATE_CODE = "writeoff_notice"

#: ⚠ **PRINT, AND ONLY PRINT.** `catalogs.AUTHORED_CATALOGS["writeoff_notice"]`
#: is `GROUP_PRINTABLE` on `pdf_print`, and its palette carries
#: `{utility_address}` — a token only a posted letter needs. There is no email
#: variant of this class, so asking for one would pin a print body to an email
#: row.
#: `notice` is the source kind CAT_COLLECTIONS selects, and it carries
#: BR-NOT-024's floor. **Floor and ask are therefore the SAME channel here, so
#: this letter cannot be switched off at all** — which is the right outcome for
#: a document telling somebody their balance was removed from active accounts.
SOURCE_NOTICE = "notice"
CHANNEL_PRINT = "pdf_print"

WRITE_OFF_NOTICE_QUEUED = "write_off_notice_queued"
WRITE_OFF_NOTICE_QUEUE_UNAVAILABLE = "write_off_notice_queue_unavailable"
WRITE_OFF_NOTICE_QUEUE_ERROR = "write_off_notice_queue_error"


class _Pin:
    """The template pin, structurally — `notification_templates` is EP-NOT-02
    and unbuilt, so a code is all there is to freeze."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.template_id = None
        self.version = None
        self.language = None


def _queue_write_off_notice(row: WriteOff, *, approved_on: date, actor: Any):
    """ONE letter when a write-off is APPROVED. Outcome rows, never a raise.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE IDEMPOTENCY TUPLE IS (tenant, "notice", WRITE-OFF id, print, 0) ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **The write-off row's own id, and never the account's.** An account can be
    written off more than once — a small balance this year, another after a
    later disconnection — and the same account also owns the collections
    reminders and disconnect notices this module's neighbour queues under this
    very source kind, keyed on the account. Keying this letter on the account
    would collide with one of those and dedupe into it: one row, the wrong
    document, `created=False`, nothing reporting a problem. That is DEF-2512.
    A write-off row is one per act, so two write-offs are two letters and a
    re-approval writes nothing (rule 6).

    **AND THE RE-APPROVAL CASE IS ALREADY HANDLED ABOVE THIS CALL**, which is
    why it is worth saying: `approve_write_off` returns early on an already-
    approved row, so this is not reached twice in the ordinary way. The key is
    what makes that structural rather than a habit — a second call arriving by
    some other route still writes nothing.

    ⚠ **A SAVEPOINT (CLAUDE.md law 14).** The caller may hold a transaction, and
    on PostgreSQL a statement that errors inside one ABORTS it: a bare `try`
    would catch the exception and leave the write-off's own COMMIT doomed with
    *"current transaction is aborted"*. SQLite has no such state, so the broken
    version passes the entire suite. The `except` is broad for
    `receipts._queue_one`'s reason — **a failed letter must never fail the
    money it describes**, and by this point the bad debt has already been
    posted to the books.
    """
    write = _resolve(QUEUE_MODULE, QUEUE_WRITE, "services")
    if write is None:  # pragma: no cover - notifications ships in this repo
        return (
            {
                "code": WRITE_OFF_NOTICE_QUEUE_UNAVAILABLE,
                "br_ref": "BR-PAY-020",
                "detail": f"apps.{QUEUE_MODULE}.services.{QUEUE_WRITE} is not published, so "
                "no write-off letter was queued. The write-off stands and is reported "
                "rather than swallowed.",
            },
        )
    try:
        with transaction.atomic():
            written = write(
                source_type=SOURCE_NOTICE,
                source_id=row.pk,
                channels=(CHANNEL_PRINT,),
                template=_Pin(WRITE_OFF_TEMPLATE_CODE),
                account_id=row.account_id,
                actor=actor,
                event_key=EVENT_WRITE_OFF_APPROVED,
                job=None if actor is not None else "payments.write_off",
                # BR-TEN-043 — the approval date the finance user entered, never
                # a wall clock. The two tokens this class whitelists beyond the
                # shared contact core, and both are read off the row.
                on_date=approved_on,
                render_context={
                    "amount": str(row.amount),
                    "date": approved_on,
                },
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return (
            {
                "code": WRITE_OFF_NOTICE_QUEUE_ERROR,
                "br_ref": "BR-PAY-020",
                "detail": f"the write-off letter could not be queued: {failure} The "
                "write-off stands and the bad debt is posted — a failed notification "
                "must never fail the money it describes.",
            },
        )
    messages = tuple(getattr(written, "messages", ()) or ())
    problems = tuple(getattr(written, "problems", ()) or ())
    if not messages:  # pragma: no cover - the print floor makes this unreachable
        return problems
    return (
        {
            "code": WRITE_OFF_NOTICE_QUEUED,
            "br_ref": "BR-PAY-020",
            "message_id": str(getattr(messages[0], "id", "")) or None,
            "created": bool(getattr(messages[0], "created", False)),
            "event_key": EVENT_WRITE_OFF_APPROVED,
            "detail": "the write-off letter (template 'writeoff_notice') is on the "
            "platform outbound queue for this write-off. Queueing is not sending: "
            "nothing dispatches in this release (BR-NOT-013).",
        },
        *problems,
    )


#: BR-PAY-020 — *"APPROVED + reported in Finance (Owner/Admin)"*. A4's role
#: set is platform-defined and holds THREE roles (SYSTEM_ADMIN, BILLING_CLERK,
#: EXECUTIVE); the rule's *Owner/Admin* is A4's SYSTEM_ADMIN and the mapping is
#: stated rather than assumed, because a fourth role invented here would be a
#: role no permission matrix grants and no screen can show. Server-enforced,
#: because a screen that hides the button is not an authorisation (BR-SHL-025).
APPROVAL_ROLE = permissions.SYSTEM_ADMIN


@dataclass(frozen=True)
class WriteOffResult:
    """One write-off, and whether it has moved any money yet."""

    write_off_id: str
    status: str
    amount: Decimal
    account_id: str
    journal_entry_id: Any = None
    posted_to_ledger: bool = False
    plan_closed: str | None = None
    #: CR-059 CS-25 — set on a REVERSING row and on nothing else. The id of the
    #: approved write-off this row corrects; the pair is the whole record.
    reverses_write_off_id: str | None = None
    #: The plan the reversal put back, or None. `problems` says WHY when a plan
    #: was closed by the approval and is not reopened here — CS-25's *"watch
    #: for"* is a customer left with a debt and no schedule, and silence is
    #: exactly how that happens.
    plan_reopened: str | None = None
    problems: tuple[dict[str, Any], ...] = ()
    #: CR-008 ruling 2 — did THIS amount need an approver under the tenant's own
    #: threshold? Served rather than derived on a screen, because the threshold
    #: is a tenant setting and a screen that re-derived it would be a second
    #: copy of a money policy (the reason `settings_seam` refuses to hold one).
    approval_required: bool = True


def _actor_id(actor: Any) -> Any:
    """WHO acted, from either actor shape — `refunds._actor_id`, verbatim.

    ⚠ **ADDED 2026-09-01, AND IT IS A LATENT BUG CLOSED RATHER THAN A TIDY-UP.**
    This file read the actor's `.pk` directly at four call sites. That works
    for `apps/payments/api.py`, whose `_actor` returns `request.user` — a model
    instance with a `.pk`. It returns **None** for the shape every newer door
    builds (`reversal_api`, `refunds_api` and `writeoffs_api` all construct a
    `SimpleNamespace(id=…, role=…, user=…)`, because the role a route may read is
    the one the server attached to the REQUEST and not a field on the User row).
    So a write-off rejected through the new door would have recorded **no
    rejecter at all** — BR-PAY-037's separation-of-duties control silently half
    missing, on a row that never fails and never complains.

    `id or pk` accepts both and is exactly what `apps/payments/refunds.py` does
    for the same reason.
    """
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _reason(reason: str) -> str:
    if reason not in WRITE_OFF_REASONS:
        raise PaymentRuleError(
            f"{reason!r} is not a write-off reason. US-PAY-012 ships "
            f"{list(WRITE_OFF_REASONS)} — the prototype's own four. *Send to collections agency*"
            " and *flag for a future deposit* are deliberately absent: neither has a ratified "
            "rule (field-map P-4/P-5) and a value the column can hold is a value some path "
            "would write.",
            br_ref="BR-PAY-020",
        )
    return reason


def _note(note: str | None) -> str:
    if not note or not note.strip():
        raise PaymentRuleError(
            "a write-off needs a note (US-PAY-012 §5 marks it *Required*). It is the only place "
            "a human explains a decision that permanently reduces receivables, and a bad-debt "
            "report whose rows say nothing cannot be reviewed by anybody.",
            br_ref="BR-PAY-020",
        )
    return note.strip()


def approval_is_required(amount: Decimal) -> bool:
    """Does a manual write-off of `amount` need a System-Admin approver?

    CR-008 ruling 2 (2026-08-17), the tenant's own
    `write_off_approval_threshold_amount`, seeded **0.00**:

        amount > threshold  →  an approver is required (BR-PAY-020)
        amount ≤ threshold  →  the requester's own act is the decision

    **AT THE SEEDED 0.00 THE SECOND BRANCH CANNOT BE REACHED**, because
    `request_write_off` refuses an amount that is not > 0. That is the whole
    point of the seeded figure: every utility keeps today's behaviour — every
    write-off of any size approved by a System Admin — until one of them types
    a number into the Accounting screen and is seen doing it.

    REFUSES (through the seam) rather than assuming when the setting cannot be
    read: an unreadable approval policy is not "no approval needed".
    """
    return amount > settings_seam.write_off_approval_threshold()


def _outstanding_of(account_id: Any) -> Decimal:
    positions, _ = billing_seam.outstanding_positions(account_ids=[account_id])
    for position in positions:
        if str(position.account_id) == str(account_id):
            return position.balance
    return ZERO


@transaction.atomic
def request_write_off(
    actor: Any,
    *,
    account_id: Any,
    amount: Decimal,
    reason: str,
    note: str,
    requested_on: date,
    currency: str = "USD",
    posted_at: datetime | None = None,
) -> WriteOffResult:
    """S34/S35's *Write off* — a request, and NOTHING money-bearing (TC-1).

    The amount is checked against what the account actually owes, computed from
    bills and allocations rather than from `accounts.balance` (BR-CUS-015: that
    column is a cache). Writing off more than a customer owes would credit the
    bad-debt account with money nobody was ever billed.

    ── THE ONE WAY THIS CAN MOVE MONEY, AND ITS THREE LOCKS (CR-008 ruling 2) ─
    A tenant may set `write_off_approval_threshold_amount` on Settings →
    Accounting. A write-off at or below it needs no separate approver, so this
    call posts it immediately — but only when ALL THREE of these hold, and each
    one is a lock somebody has to open deliberately:

      1. the tenant has typed a threshold ≥ the amount. **Seeded 0.00**, and an
         amount must be > 0, so on an untouched tenant this is never true;
      2. the actor holds `APPROVAL_ROLE` (System Admin) — the SAME role
         `approve_write_off` requires. A clerk whose tenant waived the approval
         still cannot post one, because the threshold decides whether a SECOND
         act is needed, never who may perform the first;
      3. the caller supplied `posted_at`. There is no clock in this module
         (BR-TEN-043): the posting instant is an input, and without one the row
         stays pending and SAYS SO rather than being stamped with a guess.

    Any lock closed leaves exactly the pre-CR-008 behaviour: a pending row, no
    journal entry, no balance movement, and `problems` saying so in words.
    """
    if not isinstance(amount, Decimal):
        raise PaymentRuleError(
            f"amount {amount!r} is not a Decimal — money is NUMERIC(18,6) and never a float "
            "(CLAUDE.md rule 2). Refused rather than converted.",
            br_ref="BR-PAY-020",
        )
    if amount <= ZERO:
        raise PaymentRuleError(
            "a write-off must be for a positive amount. Its SIGN lives in the posting — "
            "DR write-off / CR accounts receivable — and a negative one here would be a credit "
            "to the customer wearing a write-off's clothes.",
            br_ref="BR-PAY-020",
        )
    outstanding = _outstanding_of(account_id)
    if amount > outstanding:
        raise PaymentRuleError(
            f"a write-off of {amount} is more than the {outstanding} this account actually owes "
            "(computed from its issued bills less every allocation against them — NOT from "
            "`accounts.balance`, which is a cache, BR-CUS-015). Writing off more than was billed "
            "would put revenue into bad debt that no customer was ever charged.",
            br_ref="BR-PAY-020",
        )

    row = WriteOff.objects.create(
        tenant_id=_tenant_id(),
        account_id=account_id,
        amount=amount,
        currency=currency,
        reason=_reason(reason),
        note=_note(note),
        status=WRITE_OFF_REQUESTED,
        # `_id`, not the object: the actor a service receives is the ACTOR
        # (a user + their role in this tenant), not the `identity.User` row.
        # The same shape `notices.record_notice` uses for the same reason.
        requested_by_id=_actor_id(actor),
        requested_on=requested_on,
    )
    core_audit.money_action(
        actor,
        AUDIT_REQUESTED,
        "write_off",
        str(row.pk),
        after={
            "account_id": str(account_id),
            "amount": str(amount),
            "currency": currency,
            "reason": row.reason,
            "note": row.note,
            "requested_on": requested_on.isoformat(),
            "status": WRITE_OFF_REQUESTED,
        },
    )
    # ── CR-008 ruling 2 · the tenant's own approval threshold ───────────────
    needs_approval = approval_is_required(amount)
    if not needs_approval and getattr(actor, "role", None) == APPROVAL_ROLE and posted_at:
        approved = approve_write_off(
            actor=actor,
            write_off_id=row.pk,
            approved_on=requested_on,
            posted_at=posted_at,
        )
        return WriteOffResult(
            write_off_id=approved.write_off_id,
            status=approved.status,
            amount=approved.amount,
            account_id=approved.account_id,
            journal_entry_id=approved.journal_entry_id,
            posted_to_ledger=approved.posted_to_ledger,
            plan_closed=approved.plan_closed,
            approval_required=False,
            problems=(
                {
                    "code": "approved_under_tenant_threshold",
                    "br_ref": "BR-PAY-020",
                    "detail": f"this write-off of {amount} is at or below the threshold this "
                    "utility set on Settings → Accounting → Finance controls, so it needed no "
                    "second approver and has POSTED: receivables are reduced and the bad-debt "
                    "entry exists. Both acts are in the audit log under this user's name "
                    "(CR-008 ruling 2, 2026-08-17).",
                },
            ),
        )

    if not needs_approval:
        # The policy waived the approver and one of the other two locks is
        # closed. Reported by NAME — a row that quietly waits while the screen
        # says approval was waived is the worst of the three outcomes.
        return WriteOffResult(
            write_off_id=str(row.pk),
            status=WRITE_OFF_REQUESTED,
            amount=amount,
            account_id=str(account_id),
            approval_required=False,
            problems=(
                {
                    "code": "threshold_waived_approval_but_not_posted",
                    "br_ref": "BR-PAY-020",
                    "detail": "this utility's threshold does not require an approver for this "
                    "amount, and it has NOT been posted anyway: posting needs the System-Admin "
                    "role and a posting instant (there is no clock in this module, BR-TEN-043). "
                    "It is waiting in the approval queue, unchanged, and nothing money-bearing "
                    "has happened.",
                },
            ),
        )

    return WriteOffResult(
        write_off_id=str(row.pk),
        status=WRITE_OFF_REQUESTED,
        amount=amount,
        account_id=str(account_id),
        approval_required=True,
        problems=(
            {
                "code": "awaiting_finance_approval",
                "br_ref": "BR-PAY-020",
                "detail": "nothing money-bearing has happened. The balance is unchanged, no "
                "journal entry exists, and no bad-debt figure has moved — BR-PAY-020 gates all "
                "three behind an Owner/Admin approval in Finance (US-PAY-012 TC-1).",
            },
        ),
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-020")
@transaction.atomic
def approve_write_off(
    actor: Any,
    *,
    write_off_id: Any,
    approved_on: date,
    posted_at: datetime,
) -> WriteOffResult:
    """Finance's act (BR-PAY-020) — where the money actually moves.

    Posts **DR write-off / CR accounts receivable** through the ledger seam,
    because payments may not write journal lines (CLAUDE.md rule 5), and closes
    any live payment plan on the account (PO 2026-08-12, OQ-171).

    Approving twice is a no-op that reports itself: the row is already
    `approved`, its entry already exists, and the second call must not post the
    bad debt again.
    """
    row = (
        WriteOff.objects.select_for_update().filter(tenant_id=_tenant_id(), pk=write_off_id).first()
    )
    if row is None:
        raise PaymentRuleError(
            f"write-off {write_off_id!r} is not one of this tenant's (CLAUDE.md rule 1). "
            "Nothing was written.",
            br_ref="BR-PAY-020",
        )
    # ── CR-059 CS-25 — the two states an approval may NOT be reached from ───
    # A rejected request is finished (BR-PAY-1120): approving it would let one
    # debt be written off twice — once through the resurrected row and once
    # through the fresh request the clerk raised after being refused. A
    # reversing row is itself a correction and has already posted its mirror.
    # The database refuses both (migration 0011); this refuses them on SQLite
    # too, where there are no triggers (CLAUDE.md law 14).
    if row.status in (WRITE_OFF_REJECTED, WRITE_OFF_REVERSED):
        raise PaymentRuleError(
            f"write-off {row.pk} is {row.status} and that is terminal. A rejected request is "
            "re-raised as a NEW request and a reversing row is itself a correction — approving "
            "either would post bad debt a second time against a debt that has one.",
            br_ref="BR-PAY-1120",
        )
    if row.status == WRITE_OFF_APPROVED:
        return WriteOffResult(
            write_off_id=str(row.pk),
            status=row.status,
            amount=row.amount,
            account_id=str(row.account_id),
            journal_entry_id=row.journal_entry_id,
            posted_to_ledger=row.journal_entry_id is not None,
            problems=(
                {
                    "code": "already_approved",
                    "br_ref": "BR-PAY-002",
                    "detail": f"this write-off was already approved on {row.approved_on}. "
                    "Nothing was posted a second time — an approved write-off has already "
                    "reduced receivables, and doing it twice would halve them.",
                },
            ),
        )

    posting = ledger_seam.post_write_off(
        write_off=row,
        entry_date=approved_on,
        posted_at=posted_at,
        actor=actor,
    )
    row.status = WRITE_OFF_APPROVED
    row.approved_by_id = _actor_id(actor)
    row.approved_on = approved_on
    row.gl_account_id = posting.gl_account_id
    row.journal_entry_id = posting.entry_id
    row.save(
        update_fields=[
            "status",
            "approved_by",
            "approved_on",
            "gl_account_id",
            "journal_entry_id",
            "updated_at",
        ]
    )

    # PO 2026-08-12, OQ-171 — a write-off CLOSES the plan. From the approval and
    # never from the request: a plan closed by an unapproved request would free
    # the account to take a second plan on a debt it still owes.
    plan = plans.live_plan_for(row.account_id)
    closed = (
        dunning.close_plan_on_write_off(
            actor=actor,
            plan_id=plan.pk,
            written_off_on=approved_on,
            reason=row.reason,
        )
        if plan is not None
        else None
    )

    core_audit.money_action(
        actor,
        AUDIT_APPROVED,
        "write_off",
        str(row.pk),
        after={
            "account_id": str(row.account_id),
            "amount": str(row.amount),
            "approved_on": approved_on.isoformat(),
            "status": WRITE_OFF_APPROVED,
            "journal_entry_id": str(posting.entry_id) if posting.entry_id else None,
            "plan_closed": closed["id"] if closed else None,
        },
    )
    return WriteOffResult(
        write_off_id=str(row.pk),
        status=WRITE_OFF_APPROVED,
        amount=row.amount,
        account_id=str(row.account_id),
        journal_entry_id=posting.entry_id,
        posted_to_ledger=True,
        plan_closed=closed["id"] if closed else None,
        # CR-048 wave B task B11 — the letter `catalogs.py` has been promising
        # since 2026-08-16. Its outcome rides `problems` for the reason every
        # other queue write in this module does: a customer who was not told is
        # a FACT about this approval, and a fact that is not on the result is a
        # fact nobody sees.
        problems=_queue_write_off_notice(row, approved_on=approved_on, actor=actor),
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-1120")
@transaction.atomic
def reject_write_off(
    actor: Any,
    *,
    write_off_id: Any,
    rejected_on: date,
    reason: str,
) -> WriteOffResult:
    """The approver's OTHER answer — CR-059 CS-25, and it moves no money.

    CS-25's new rule, verbatim: *"A request may be **rejected with a reason** by
    an approver; **rejection moves no money and is not a deletion**."*

    ════════════════════════════════════════════════════════════════════════
    WHY THIS IS A STATUS MOVE AND THE REVERSAL BESIDE IT IS A NEW ROW
    ════════════════════════════════════════════════════════════════════════
    Hard rule 4 makes an issued financial record append-only, and CS-25 honours
    it in both halves — but the halves are not the same shape, because the rows
    are not in the same state. A `requested` write-off **has posted nothing**:
    no journal entry, no balance movement, no plan closed. There is nothing to
    correct, only a decision to record, so the decision is recorded on the row
    that was waiting for it. An APPROVED write-off has reduced receivables, and
    that is corrected by `reverse_write_off` writing a NEW ROW.

    Getting this backwards in either direction is the failure to avoid: a
    rejection written as a new row would put a second write-off on the account's
    history for a debt nobody wrote off, and an approval un-picked in place
    would leave the books saying one thing and the account another.

    **What this call does NOT do, and each is deliberate:**
      * it asks the ledger for **nothing** — the request never reached it;
      * it closes **no payment plan** — the approval is what closes one
        (PO 2026-08-12, OQ-171) and no approval happened;
      * it sends **no letter** — `catalogs.LISTINGS["writeoff_notice"]` is the
        APPROVAL's document, and a customer who was never told a debt was
        written off must not be told it was not;
      * it **deletes nothing**. The row stands, with who refused it, when, and
        why, which is the whole of what "not a deletion" buys.

    Worked, on US-PAY-012's own figure: a **948.20** request against A-10802 is
    rejected — the row reads `rejected`, `journal_entry_id` is still null, the
    account still owes **948.20**, and the Finance queue loses a row it was
    never going to action.
    """
    reason = (reason or "").strip()
    if not reason:
        raise PaymentRuleError(
            "a rejection needs a reason. It is the only thing the requester will be shown, and "
            "an approval queue whose refusals say nothing sends the same request back tomorrow "
            "(CS-25). The reason is free text, exactly like the write-off's own note.",
            br_ref="BR-PAY-1120",
        )
    row = (
        WriteOff.objects.select_for_update().filter(tenant_id=_tenant_id(), pk=write_off_id).first()
    )
    if row is None:
        raise PaymentRuleError(
            f"write-off {write_off_id!r} is not one of this tenant's (CLAUDE.md rule 1). "
            "Nothing was written.",
            br_ref="BR-PAY-020",
        )
    if row.status == WRITE_OFF_REJECTED:
        # A second click is a no-op that reports itself, the shape
        # `approve_write_off` uses for the same double-submit.
        return WriteOffResult(
            write_off_id=str(row.pk),
            status=row.status,
            amount=row.amount,
            account_id=str(row.account_id),
            approval_required=True,
            problems=(
                {
                    "code": "already_rejected",
                    "br_ref": "BR-PAY-1120",
                    "detail": f"this request was already rejected on {row.rejected_on}. Nothing "
                    "moved then and nothing moved now — a rejection is a recorded decision, and "
                    "recording it twice would overwrite the first refusal's reason.",
                },
            ),
        )
    if row.status != WRITE_OFF_REQUESTED:
        raise PaymentRuleError(
            f"write-off {row.pk} is {row.status} and only a REQUESTED write-off can be rejected. "
            "An approved one has already posted DR write-off / CR accounts receivable and is "
            "corrected by a reversing row (CS-25); a reversing row is itself a correction. "
            "Nothing was written.",
            br_ref="BR-PAY-1120",
        )

    row.status = WRITE_OFF_REJECTED
    row.rejected_by_id = _actor_id(actor)
    row.rejected_on = rejected_on
    row.rejection_reason = reason
    row.save(
        update_fields=["status", "rejected_by", "rejected_on", "rejection_reason", "updated_at"]
    )
    core_audit.money_action(
        actor,
        AUDIT_REJECTED,
        "write_off",
        str(row.pk),
        after={
            "account_id": str(row.account_id),
            "amount": str(row.amount),
            "currency": row.currency,
            "rejected_on": rejected_on.isoformat(),
            "rejection_reason": reason,
            "status": WRITE_OFF_REJECTED,
            # Stated on the money action so a year-old trail cannot be misread
            # as a write-off that happened: hard rule 7 records every money
            # ACTION, and "no money moved" is the fact this one carries.
            "journal_entry_id": None,
        },
    )
    return WriteOffResult(
        write_off_id=str(row.pk),
        status=WRITE_OFF_REJECTED,
        amount=row.amount,
        account_id=str(row.account_id),
        posted_to_ledger=False,
        approval_required=True,
        problems=(
            {
                "code": "rejected_no_money_moved",
                "br_ref": "BR-PAY-1120",
                "detail": "nothing money-bearing happened. No journal entry exists, the balance "
                "is unchanged, no payment plan was closed and no letter was queued — the request "
                "never reached the books. The row stands as the record of who refused it and why "
                "(CS-25: a rejection is not a deletion).",
            },
        ),
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-1120")
@transaction.atomic
def reverse_write_off(
    actor: Any,
    *,
    write_off_id: Any,
    reversed_on: date,
    posted_at: datetime,
    reason: str,
) -> WriteOffResult:
    """Put a wrongly-approved write-off BACK — as a NEW ROW (CR-059 CS-25).

    CS-25's new rule, verbatim: *"An approved write-off is corrected by a
    **reversing write-off row and a mirrored ledger entry**, never by editing or
    deleting the original — **and the debt comes back at its ORIGINAL age**,
    exactly as a bounced payment reinstates arrears at the original due date."*

    ════════════════════════════════════════════════════════════════════════
    HARD RULE 4 — THE ORIGINAL IS NEVER TOUCHED. NOT ONE COLUMN.
    ════════════════════════════════════════════════════════════════════════
    This writes a SECOND `write_offs` row carrying status `reversed`, pointing
    at the original through `reverses_write_off`, and it issues **no UPDATE
    against the original at all**. Migration 0011's trigger refuses one anyway,
    and both facts are asserted. *"Has this write-off been reversed?" is a
    question about the existence of another row, never about a flag on this
    one* — payments' own doctrine for a bounced cheque, applied to bad debt.

    `uq_write_offs_reverses` makes a write-off reversible ONCE (hard rule 6),
    and it is the DATABASE's guard rather than the SELECT below: two approvers
    on two screens is exactly the race a check in Python loses, and the loser
    would credit receivables twice for one correction.

    ⚠ **WHAT A LOST RACE DOES, STATED RATHER THAN LEFT TO BE DISCOVERED.** The
    SELECT below turns a *replay* — the same approver clicking twice — into a
    200 carrying the first reversal. It cannot turn a genuine *race* into one:
    two transactions that both pass the SELECT meet the unique index, and the
    loser's INSERT raises. **Nothing here catches that**, so the whole
    transaction rolls back — the mirror included — and the caller sees an error
    rather than a second correction. That is the SAFE outcome and it is the
    reason no savepoint is used: CLAUDE.md law 14 is about code that catches a
    database error and CARRIES ON, and this does not. Returning the winner's row
    to the loser would need one, and would need proving on PostgreSQL, which
    seeding cannot currently support (`DEF-2395`).

    ════════════════════════════════════════════════════════════════════════
    THE ORIGINAL AGE, AND WHY IT IS SAFE HERE BY CONSTRUCTION
    ════════════════════════════════════════════════════════════════════════
    S34's `days_late` is `as_of − the account's OLDEST UNPAID due date`
    (BR-PAY-032), read off billing's own invoices through
    `billing_seam.outstanding_positions`. **Neither the write-off nor this
    reversal writes an allocation row or moves a due date**, so the age cannot
    move: a debt written off at 91 days and reversed four months later comes
    back at its true age, not at one day old, and stays in the 90+ bucket the
    collections ladder reads.

    ⚠ **AND THE REASON IT IS SAFE IS ALSO A DEFECT — `DEF-3121`, FILED NOT
    FIXED.** An approved write-off does not remove the debt from Outstandings
    EITHER, because nothing in the write-off path writes an allocation. Measured
    on TC-2's own figures: before the write-off the account owes **948.20** at
    91 days; after approval it owes **948.20** at 91 days, while the ledger has
    already credited AR by 948.20. So `writeoffs.py`'s own module docstring —
    *"the account's outstanding balance falls to 0.00 because the allocation the
    posting represents settles its bills"* — describes an allocation that does
    not exist, and the collections ladder keeps chasing a customer the utility
    has stopped chasing. Fixing it moves money onto the allocation path, which
    is not this task's, so it is named here rather than patched around.

    ════════════════════════════════════════════════════════════════════════
    THE PLAN — CS-25's OWN "WATCH FOR", AND WHY THIS IS ONE CHANGE
    ════════════════════════════════════════════════════════════════════════
    The approval CLOSED any live payment plan (PO 2026-08-12, OQ-171). The
    reversal reopens it, to **the status it actually held** and never blanket-
    `active` — see `dunning.reopen_plan_on_write_off_reversal`. When a NEWER
    plan has since been agreed the older one stays closed and `problems` says
    so by name: the customer is on the newer schedule, not on none.

    Worked end to end, on US-PAY-012 TC-2's figure. A **948.20** write-off is
    approved: DR write-off 948.20 / CR accounts receivable 948.20, and the
    account's live plan closes. It was raised on the wrong account. This call
    writes a second row for **948.20** at status `reversed`, asks the ledger for
    its own mirror — **DR accounts receivable 948.20 / CR write-off 948.20** —
    so bad debt nets to **0.00** and the receivable is whole, and reopens the
    plan. Three rows survive forever and the net is right.
    """
    reason = (reason or "").strip()
    if not reason:
        raise PaymentRuleError(
            "a write-off reversal needs a reason. It is the only explanation a finance reviewer "
            "will find beside a bad-debt figure that came back, and CS-25 asks for the "
            "correction to be evidence rather than a silent net-off. Free text, like the "
            "write-off's own note.",
            br_ref="BR-PAY-1120",
        )
    original = (
        WriteOff.objects.select_for_update().filter(tenant_id=_tenant_id(), pk=write_off_id).first()
    )
    if original is None:
        raise PaymentRuleError(
            f"write-off {write_off_id!r} is not one of this tenant's (CLAUDE.md rule 1). "
            "Nothing was written.",
            br_ref="BR-PAY-020",
        )
    if original.status != WRITE_OFF_APPROVED:
        raise PaymentRuleError(
            f"write-off {original.pk} is {original.status} and only an APPROVED write-off can be "
            "reversed. A request that has posted nothing is REJECTED, which moves no money; a "
            "rejected row is finished; and a reversing row is itself a correction. Nothing was "
            "written.",
            br_ref="BR-PAY-1120",
        )
    existing = (
        WriteOff.objects.filter(tenant_id=_tenant_id(), reverses_write_off_id=original.pk)
        .order_by("created_at")
        .first()
    )
    if existing is not None:
        # The replay, answered with the FIRST reversal rather than a refusal —
        # `approve_write_off`'s posture, and a double-clicked Reverse is a
        # button that worked (BR-PAY-028's own reasoning for the 200).
        return WriteOffResult(
            write_off_id=str(existing.pk),
            status=existing.status,
            amount=existing.amount,
            account_id=str(existing.account_id),
            journal_entry_id=existing.journal_entry_id,
            posted_to_ledger=existing.journal_entry_id is not None,
            reverses_write_off_id=str(original.pk),
            problems=(
                {
                    "code": "already_reversed",
                    "br_ref": "BR-PAY-1120",
                    "detail": f"write-off {original.pk} was already reversed on "
                    f"{existing.approved_on} by row {existing.pk}. Nothing was posted a second "
                    "time — a second mirror would put the receivable back twice and double the "
                    "customer's debt. `uq_write_offs_reverses` is the database's half of the "
                    "same guarantee (hard rule 6).",
                },
            ),
        )

    # ── the LEDGER'S OWN MIRROR — never a compensating entry composed here ──
    posting = ledger_seam.reverse_write_off_entry(
        write_off=original,
        entry_date=reversed_on,
        posted_at=posted_at,
        actor=actor,
    )
    reversing = WriteOff.objects.create(
        tenant_id=_tenant_id(),
        account_id=original.account_id,
        # The MAGNITUDE the original carried, not its negation:
        # `ck_write_offs_amount_positive` holds, and a write-off's direction
        # lives in its posting. `status` is what says which way this one went.
        amount=original.amount,
        currency=original.currency,
        # The original's own reason, copied. This row is not a new judgment
        # about why the debt was uncollectible — it is the undoing of one — and
        # inventing a fifth reason value here would break the closed set the
        # database checks and the bad-debt report groups on.
        reason=original.reason,
        note=original.note,
        status=WRITE_OFF_REVERSED,
        reverses_write_off_id=original.pk,
        reversal_reason=reason,
        # ONE Admin act, so the same person is both halves of BR-PAY-037's pair
        # on THIS row. Who reversed it is read from here; there is no separate
        # `reversed_by` column and none is needed.
        requested_by_id=_actor_id(actor),
        requested_on=reversed_on,
        approved_by_id=_actor_id(actor),
        approved_on=reversed_on,
        gl_account_id=posting.gl_account_id,
        journal_entry_id=posting.entry_id,
    )

    # CS-25's "⚠ WATCH FOR" — the plan the approval closed.
    plan = _closed_plan_for(original)
    reopened = (
        dunning.reopen_plan_on_write_off_reversal(
            actor=actor,
            plan_id=plan.pk,
            reversed_on=reversed_on,
            reason=reason,
        )
        if plan is not None
        else None
    )
    problems: list[dict[str, Any]] = []
    if plan is not None and not (reopened or {}).get("created"):
        blocker = (reopened or {}).get("blocked_by_plan_id")
        problems.append(
            {
                "code": "plan_not_reopened",
                "br_ref": "BR-CUS-043",
                "detail": (
                    (
                        f"payment plan {plan.pk} was closed by this write-off's approval and was NOT "
                        f"reopened, because the account already holds a live plan ({blocker}). "
                        "BR-CUS-043 allows one live plan per account, so the newer schedule stands "
                        "and the customer is not left without one."
                    )
                    if blocker
                    else (
                        f"payment plan {plan.pk} was closed by this write-off's approval and was NOT "
                        "reopened — it is no longer in the closed state this reversal would restore. "
                        "Check the account's plans before telling the customer what they owe."
                    )
                ),
            }
        )
    problems.append(
        {
            "code": "outstanding_unchanged_by_write_off",
            "br_ref": "BR-PAY-020",
            "detail": "the receivable is back in the BOOKS: this reversal posted the ledger's "
            "own mirror of the bad-debt entry. It is unchanged on the Outstandings screen and "
            "in the collection ladder, because the approval never removed it from either — "
            "neither path writes an allocation (DEF-3121). The debt therefore carries its "
            "ORIGINAL age throughout, which is what CS-25 requires.",
        }
    )

    core_audit.money_action(
        actor,
        AUDIT_REVERSED,
        "write_off",
        str(reversing.pk),
        after={
            "account_id": str(original.account_id),
            "amount": str(original.amount),
            "currency": original.currency,
            "reverses_write_off_id": str(original.pk),
            "reversal_reason": reason,
            "reversed_on": reversed_on.isoformat(),
            "status": WRITE_OFF_REVERSED,
            "journal_entry_id": str(posting.entry_id) if posting.entry_id else None,
            "plan_reopened": (
                (reopened or {}).get("id") if (reopened or {}).get("created") else None
            ),
        },
    )
    return WriteOffResult(
        write_off_id=str(reversing.pk),
        status=WRITE_OFF_REVERSED,
        amount=reversing.amount,
        account_id=str(reversing.account_id),
        journal_entry_id=posting.entry_id,
        posted_to_ledger=True,
        reverses_write_off_id=str(original.pk),
        plan_reopened=(reopened or {}).get("id") if (reopened or {}).get("created") else None,
        problems=tuple(problems),
    )


def _closed_plan_for(write_off: WriteOff) -> Any:
    """The plan this write-off's approval closed, or None.

    Matched on the account and on `closed_on == approved_on`, because that is
    exactly what `dunning.close_plan_on_write_off` wrote — it takes
    `written_off_on=approved_on` and stores it in `closed_on`. Matching on the
    date as well as the account is what stops a reversal reopening a plan that
    was closed by being PAID OFF, which lands in the same status by design
    (*"the books distinguish the two by the write-off entry, not by inventing a
    fifth plan state"*).

    ⚠ **THE MATCH IS A RECONSTRUCTION AND IT IS NOT PERFECT, SO IT SAYS SO.**
    Nothing links a plan to the write-off that closed it, and adding that column
    is a schema change CS-25 does not ask for. Two plans on one account closed
    on one day would be indistinguishable — impossible today, because
    `uq_one_live_plan_per_account` allows only one live plan to close.
    """
    from apps.payments.collections_models import PLAN_CLOSED, PaymentPlan

    if write_off.approved_on is None:
        return None
    return (
        PaymentPlan.objects.filter(
            tenant_id=_tenant_id(),
            account_id=write_off.account_id,
            status=PLAN_CLOSED,
            closed_on=write_off.approved_on,
        )
        .order_by("-created_at")
        .first()
    )


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one.

    The seam idiom this module already uses through `billing_seam` and
    `ledger_seam`: resolved BY NAME at call time, never imported (B1 / G6).
    """
    from importlib import import_module

    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def write_off_pending_count() -> int:
    """**THE WHOLE-POPULATION COUNT OF WHAT IS WAITING — Finance blueprint
    `P2.19`.**

    ⚠ **IT IGNORES EVERY FILTER, AND THAT IS THE ENTIRE POINT.** The blueprint
    states the problem it solves in the code's own words (p038): this queue is
    *"unpaginated, deliberately … a page of an approval queue is a queue that
    lies about what is pending"*. **The objection is real and the ceiling is
    not** — the product now serves utilities up to 40,000 accounts, `NFR-3`
    forbids an unpaginated list, and the answer the blueprint gives is not to
    keep the list whole but to state the true total beside it: *"`Write-offs ·
    2` states the true total on every page, so paging can no longer hide
    anything."*

    So a filtered, searched, paged queue can be served honestly, because the
    badge in the view label does not move when the clerk narrows the list.
    **A count derived from the rows on screen would be the lie this exists to
    end**, which is why it is its own query and not `len(rows)`.

    `COUNT(*)` over `(tenant, status)` — `ix_write_offs_status` is indexed
    `(tenant, status, -requested_on)`, so this is an index-only count and costs
    one statement.
    """
    return WriteOff.objects.filter(tenant_id=_tenant_id(), status="requested").count()


def write_off_queue(
    *,
    status: str | None = None,
    q: str | None = None,
    reason: str | None = None,
    requested_from: date | None = None,
    requested_to: date | None = None,
    requested_by: str | None = None,
) -> tuple[dict[str, Any], ...]:
    """DEF-100 — the rows a second person approves. The read that was missing.

    The status is BR-PAY-020's Finance half — *"what is awaiting approval?"* —
    and `status=None` serves every write-off this tenant has, which is what the
    reported half of the same rule (*"approved + REPORTED in Finance"*) reads.

    ⚠ **IT TOOK ONE ARGUMENT UNTIL 2026-09-24 AND THE SCREEN DECLARED FIVE
    (`P2.19`).** Blueprint p039's criteria table marks **State** SERVED and
    **Reason · Requested (a date range) · Requested by · Search** all NOT
    SERVED — *"only the state filter is supported today"* — over a toolbar the
    drawing puts on the screen. Four controls that narrow nothing is worse than
    four controls that are absent, because a clerk who filters and sees the
    same rows concludes the data is wrong rather than the filter.

    ⚠ **`q` MATCHES THE ACCOUNT NUMBER AND THE SEARCH RUNS AFTER THE ACCOUNT
    JOIN, NOT IN SQL.** p039 says *"Search · `q` · **account number**"*, and the
    account number is `customers`' to know: `_accounts_by_id` resolves it
    through their published queryset BY NAME, because B1 / BR-TEN-013 forbid a
    cross-module ORM query and there is no column here to filter on. That is a
    real cost and it is stated rather than hidden — the other four criteria are
    columns of `write_offs` and DO narrow in SQL. The day the account reference
    is denormalised onto this table, `q` moves down with them.

    ⚠ **THE ACCOUNT NUMBER IS RESOLVED THROUGH CUSTOMERS' OWN QUERYSET**, by
    name, never by importing their models (B1 / BR-TEN-013) — the same shape
    `outstandings._accounts_by_id` uses. When customers publishes nothing the
    number comes back None and the row still serves; a queue that refused to
    list because a display field was unreachable would hide money decisions
    waiting on a human.

    ⚠ **EVERY AMOUNT TRAVELS WITH ITS CHAR(3) CODE** (CLAUDE.md rule 2,
    DEF-099). The code is the ROW's own `currency` and not a tenant default:
    these rows are the utility's record of money it has stopped chasing, and a
    bare number in a Finance queue is half a fact.

    Ordered newest request first — an approval queue is worked from the top and
    `ix_write_offs_status` is indexed `(tenant, status, -requested_on)` for
    exactly this read.
    """
    rows = WriteOff.objects.filter(tenant_id=_tenant_id())
    if status is not None:
        if status not in WRITE_OFF_STATUSES:
            raise PaymentRuleError(
                f"{status!r} is not a write-off status. The four this product has are "
                f"{list(WRITE_OFF_STATUSES)} — a filter naming a fifth would answer an empty "
                "queue, and an empty queue and an unanswerable one look identical on a screen.",
                br_ref="BR-PAY-020",
            )
        rows = rows.filter(status=status)
    if reason:
        # ⚠ **REFUSED BY NAME, LIKE THE STATUS ABOVE, AND FOR ITS REASON.** An
        # unknown reason silently answering an empty queue is indistinguishable
        # on screen from *nothing is waiting* — `write_off_queue`'s own
        # sentence, applied to the second filter it gained.
        if reason not in WRITE_OFF_REASONS:
            raise PaymentRuleError(
                f"{reason!r} is not a write-off reason. The ones this product has are "
                f"{list(WRITE_OFF_REASONS)} — a filter naming another would answer an empty "
                "queue, and an empty queue and an unanswerable one look identical on a screen.",
                br_ref="BR-PAY-020",
            )
        rows = rows.filter(reason=reason)
    if requested_from is not None:
        rows = rows.filter(requested_on__gte=requested_from)
    if requested_to is not None:
        # INCLUSIVE, because a clerk who types the same date in both boxes means
        # *that day* and an exclusive upper bound would answer nothing.
        rows = rows.filter(requested_on__lte=requested_to)
    if requested_by:
        rows = rows.filter(requested_by_id=requested_by)
    rows = list(rows.order_by("-requested_on", "-created_at", "-id"))
    accounts = _accounts_by_id([row.account_id for row in rows])
    people = _people_by_id(
        [row.requested_by_id for row in rows]
        + [row.approved_by_id for row in rows]
        + [row.rejected_by_id for row in rows]
    )
    served = tuple(_queue_row(row, accounts.get(row.account_id), people) for row in rows)
    if q:
        # ⚠ **AFTER THE JOIN, NOT IN SQL — see this function's own header.** The
        # account number lives in `customers` and reaches here through a
        # published queryset, so there is no column to filter on. Case-folded,
        # because `ac-2026-00017` and `AC-2026-00017` are the same account and a
        # clerk typing the first should not be told there is no such row.
        needle = q.strip().casefold()
        if needle:
            served = tuple(
                row
                for row in served
                if needle in str(row.get("account_no") or "").casefold()
            )
    return served


def _accounts_by_id(ids: list[Any]) -> dict[Any, Any]:
    queryset = _resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        return {}
    return {account.pk: account for account in queryset().filter(pk__in=ids)}


def _people_by_id(ids: list[Any]) -> dict[str, str]:
    """WHO asked and WHO approved, by NAME — the two-person control, made visible.

    ⚠ ADDED 2026-08-16 by the payments SURFACE lane. The queue already carried
    `requested_by` and `approved_by` as bare UUIDs, and a Finance approver
    reading `0198c3a1-…` cannot tell whether they are about to approve their own
    request. **BR-PAY-037 permits exactly that in v1** — verbatim: *"the SAME
    user holding the approver role MAY initiate AND approve in v1 — both acts
    recorded distinctly; enforced separation-of-duties = v2"* — so the product
    may not BLOCK it, and the honest alternative is to make it impossible to do
    by accident. The screen renders "Requested by you" beside the Approve
    control; a person who means it still can, and now knows that they are.

    Resolved through identity's published selector BY NAME at call time (B1 /
    G6 — payments never imports another module's models). Identity publishing
    nothing gives an empty map, and the row falls back to its UUID: a queue that
    refused to list because a display name was unreachable would hide money
    decisions waiting on a human, which is the failure this whole read exists to
    fix.
    """
    wanted = {str(value) for value in ids if value}
    if not wanted:
        return {}
    read = _resolve("identity", "user_in_tenant")
    if read is None:  # pragma: no cover - identity publishes it
        return {}
    tenant_id = _tenant_id()
    found: dict[str, str] = {}
    for user_id in wanted:
        user = read(tenant_id, user_id)
        name = getattr(user, "full_name", None) or getattr(user, "email", None)
        if name:
            found[user_id] = name
    return found


def _queue_row(row: WriteOff, account: Any, people: dict[str, str] | None = None) -> dict[str, Any]:
    """One queue row — what a Finance approver needs to decide, and no more.

    `posted_to_ledger` is derived from `journal_entry_id` and NOT from the
    status: the status says what a human decided, the entry id says what the
    books actually carry, and US-PAY-012 TC-1's whole control is that those two
    are different facts until an approval posts.
    """
    return {
        "id": str(row.pk),
        "account_id": str(row.account_id),
        "account_no": getattr(account, "account_no", None),
        "amount": f"{row.amount:.4f}",
        "currency": row.currency,
        "reason": row.reason,
        "note": row.note,
        "status": row.status,
        "requested_on": row.requested_on.isoformat() if row.requested_on else None,
        "requested_by": str(row.requested_by_id) if row.requested_by_id else None,
        # The NAME, so an approver can see whose request they are approving
        # (BR-PAY-037 permits self-approval in v1 and this makes it deliberate
        # rather than accidental). None when identity cannot name the user —
        # never the UUID dressed up as a name.
        "requested_by_name": (people or {}).get(str(row.requested_by_id or "")) or None,
        "approved_on": row.approved_on.isoformat() if row.approved_on else None,
        "approved_by": str(row.approved_by_id) if row.approved_by_id else None,
        "approved_by_name": (people or {}).get(str(row.approved_by_id or "")) or None,
        # ── CR-059 CS-25 ────────────────────────────────────────────────────
        # A refused request must say WHO refused it and WHY on the row a person
        # reads. The alternative is a queue row that says only `rejected` and a
        # requester who raises the same request again tomorrow — which is the
        # queue-fills-with-requests-nobody-actions problem CS-25 opens with,
        # wearing a different hat.
        "rejected_on": row.rejected_on.isoformat() if row.rejected_on else None,
        "rejected_by": str(row.rejected_by_id) if row.rejected_by_id else None,
        "rejected_by_name": (people or {}).get(str(row.rejected_by_id or "")) or None,
        "rejection_reason": row.rejection_reason,
        # On a REVERSING row: which approved write-off it corrects, and why.
        # `null` on every other row, so *"was this reversed?"* stays a question
        # about the existence of another row and never a flag on this one.
        "reverses_write_off_id": (
            str(row.reverses_write_off_id) if row.reverses_write_off_id else None
        ),
        "reversal_reason": row.reversal_reason,
        "posted_to_ledger": row.journal_entry_id is not None,
        "journal_entry_id": str(row.journal_entry_id) if row.journal_entry_id else None,
    }


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-012@3c9f5a1 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-012 · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-020/002/037 · 04-docs/05-modules/08-payments/03-field-map.md §3 + P-4/P-5 · 04-docs/05-modules/08-payments/04-flows.md §6 · 08-qa/01-e2e/journeys/J4-collections.md)
# generated: 2026-08-15 by story-coder (payments visible-half lane)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_012_write_offs.py (the "no ledger effect before approval" assertion and the over-write-off refusal were driven RED first) · pytest tests -m isolation✔
# exceptions: (1) NO AGENCY REFERRAL, NO FUTURE-DEPOSIT FLAG — field-map P-4/P-5, no ratified rule, excluded by US-PAY-012 §1. The columns do not exist so no path can write them
#         (2) THE AMOUNT IS CHECKED AGAINST COMPUTED AR, never `accounts.balance` (BR-CUS-015 — a cache)
#         (3) BULK IS THE CALLER'S LOOP (US-PAY-012 TC-3): one request per account, one approval decision over the reviewed set, per-account results. A single row spanning four accounts could not post four balanced entries or close four plans
#         (4) A WRITE-OFF CLOSES THE PLAN from the APPROVAL (PO 2026-08-12, OQ-171) — never from the request
#         (5) RECOVERY IS NOT HANDLED HERE (TC-4): a later payment is a NEW row through US-PAY-001 and this row is never edited (BR-PAY-002)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

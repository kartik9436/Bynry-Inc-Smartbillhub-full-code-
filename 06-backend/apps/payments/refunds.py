# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-011 (Refunds — TC-1 the PE-9 cheque, TC-3 the clearing,
#           TC-4 the void, TC-5 the over-refund and the zero credit, TC-6
#           self-approval and the card refusal, TC-7 isolation)
#           Screens: S58 · S33
# Rules:    BR-PAY-014 (refunds ONLY from a real credit balance; Admin
#           approval; check/ACH v1 — card waits for rails W7; DR
#           customer-credit / CR cash; immutable row + receipt) · BR-PAY-002
#           (append-only; a void is a status move plus a REVERSING posting,
#           never a delete) · BR-PAY-024 (a receipt is auto-queued) ·
#           BR-PAY-037 (the SAME user holding the approver role may initiate
#           AND approve in v1 — both acts recorded distinctly) · BR-PAY-021
#           (bank rec matches a refund on the side the money moved) ·
#           BR-CUS-054 (a customer holds MANY accounts — which is what makes
#           OQ-135 real) · BR-PAY-1071 (2026-09-01, CR-059 CS-6, AMENDED
#           2026-09-03 by PO ruling "q6 yes Clark can issue refund" — issuing a
#           refund is **Admin or Billing Clerk** and clearing one is Admin or
#           Executive, both enforced in the SERVICE; the APPROVAL is the control
#           and approve_refund stays Admin; clearing is a bank fact, not an
#           approval) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) ·
#           rule 4 (financial immutability) · rule 5 (only the ledger posts) ·
#           rule 6 (idempotency) · rule 7 (every money action writes audit_log)
# Tests:    06-backend/tests/test_us_pay_011_refunds.py ·
#           06-backend/tests/test_cr059_cs6_refund_doors.py (the three routes,
#           the two new service gates and the credit re-tested at issue)
# Impacts:  apps/payments/ledger_seam.post_refund_executed +
#           reverse_refund_entry · apps/payments/selectors
#           .account_credit_position (the "real credit" test, signed) ·
#           apps/payments/reversal (a refunded credit is what lets a bounce
#           drive the position NEGATIVE)
# ───────────────────────────────────────────────────────
"""Money the utility pays BACK (BR-PAY-014, EP-PAY-03 US-PAY-011).

HUMAN-OWNED (CLAUDE.md 🔒 — this file holds an idempotency key, writes money
rows and hands a posting and a reversal to the ledger service).
HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO ruling of 2026-08-09;
row in 12-governance/09-human-review-ledger.md.

════════════════════════════════════════════════════════════════════════════
THE CHAIN, AND WHERE EACH LINK IS SIGNED
════════════════════════════════════════════════════════════════════════════
BR-PAY-014, CONFIRMED (PO PA-3, 2026-08-08): *"Refunds only from a real credit
balance; Admin approval; check/ACH v1 (card refund with rails W7); DR
customer-credit / CR cash; immutable row + receipt"*.

    request   ->  approve   ->  execute        ->  clear   |  void
    requested     approved      issued             cleared |  void

`request_refund` · `approve_refund` · `issue_refund` · `clear_refund` ·
`void_refund`. Four of the five write nothing but a status and its timestamps;
`issue_refund` is the only one that moves money, and that is deliberate —
US-PAY-012's write-off flow makes the same split for the same reason (*"approval
gates money"*).

**WHO MAY DO EACH, ALL FIVE, ENFORCED HERE (BR-SHL-025 — the server IS the
enforcement).** `request_refund` any Admin or Billing Clerk (gated at the route;
the credit test in this file is what actually refuses a request nothing funds) ·
`approve_refund` **Admin** (BR-PAY-014) · `issue_refund` **Admin or Billing
Clerk** · `clear_refund` **Admin or Executive** — *a bank fact, not an
approval* · `void_refund` **Admin** (BR-PAY-014). ⚠ **THE MIDDLE TWO WERE
UNGATED UNTIL 2026-09-01 (BR-PAY-1071, CR-059 CS-6)** and each function's own
docstring says what that cost; the entry stays here rather than vanishing
because the next reader will meet the shape in the register and in the tests.
⚠ **AND `issue_refund` READ *"Admin"* HERE UNTIL 2026-09-03**, when the Product
Owner widened it — *"q6 yes Clark can issue refund"*. `BR-PAY-1071` is AMENDED
with its chain; the line is corrected rather than left to rot (hard-won law 1),
and **the APPROVAL is still the control**: `approve_refund` is unchanged.

════════════════════════════════════════════════════════════════════════════
"ONLY FROM A REAL CREDIT BALANCE" IS A SIGNED TEST, AND IT IS SIGNED
════════════════════════════════════════════════════════════════════════════
The credit position comes from `selectors.account_credit_position`, which returns
a **signed** figure and floors nothing (PO ruling 2026-08-11, OQ-132: *"Yes,
it's a real debt"*). So:

  * credit **57.13**, refund **57.13**  ->  allowed. PE-9, exactly.
  * credit **57.13**, refund **80.00**  ->  refused (US-PAY-011 TC-5).
  * credit **0.00**                     ->  refused (TC-5's second half; J15
    step 5 — the second refund attempt of the same $57.13 is REFUSED and writes
    a security-event attempt row).
  * credit **−57.13** after a bounce    ->  refused, and the refusal says the
    account OWES that money rather than saying "insufficient credit", because a
    negative credit is a debt the utility is chasing.

**The test is evaluated at REQUEST and AGAIN at ISSUE.** A credit that was real
on Tuesday can be gone on Thursday — spent by the auto-apply at the next bill,
or pulled back by a bounce — and the money moves on Thursday. Checking once
would let an approval outlive the credit it approved.

════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE REFUSES TO DECIDE — OQ-135 AND OQ-167
════════════════════════════════════════════════════════════════════════════
**OQ-135 (OPEN): may we refund a customer who owes money on ANOTHER of their
accounts?** BR-CUS-054 made the customer a first-class entity with many accounts
(the landlord case), so this is not hypothetical: the registry's worked fixture
holds **$57.13 credit** on one account and **$948.20 overdue by 91 days** on
another, final notice already sent. Refunding is arguably the legally cleanest
answer where the responsible parties genuinely differ; automatic offset can be
unlawful where the account holders differ; the engineering recommendation is to
WARN and let the clerk decide with the decision recorded. The Product Owner has
not ruled, and the registry's own "buildable meanwhile" note is explicit: *"the
service REFUSES when arrears exist elsewhere, citing OQ-135, rather than
silently paying out"*. `cross_account_check=True` therefore raises
**OFFSET FIRST — PO 2026-08-12, OQ-135 CLOSED.** With `cross_account_check=True`
the refund REFUSES while this customer owes on another of their accounts, and
the offset is applied as a balance transfer rather than netted off the payout:
the figure available here is the CACHED balance (BR-CUS-015), which is good
enough to stop money leaving and not good enough to subtract from it. The
DEFAULT still performs no cross-account check and says so on the result
(`cross_account_arrears_not_checked`), because a check nobody asked for is its
own surprise.

**OQ-167 (raised by this lane): a credit that came from TWO overpayments has no
`payment_id`.** B2 §2 types `refunds.payment_id` NOT NULL, which is exactly
PE-9's shape — ACC-1042's $57.13 came from ONE $350.00 payment. An account whose
credit accumulated from two overpayments has a real credit balance that no
single payment describes, and this table has no account column to say so. The
single-source case is served; the multi-source case is REFUSED by name.

════════════════════════════════════════════════════════════════════════════
WHAT IS NOT BUILT HERE
════════════════════════════════════════════════════════════════════════════
  * **THE RECEIPT/NOTICE IS NOT QUEUED** (BR-PAY-024 / BR-NOT-005, TC-1).
    `outbound_messages` is the platform queue and US-PAY-025 owns the write.
  * **CARD REFUNDS DO NOT EXIST** — BR-PAY-014 puts them behind the payment
    rails (W7). `card` is not a value `refunds.method` can hold, so this is a
    refusal at the door and not a branch that could be flipped by a bad payload.
  * **THE FINAL-BILL HANDOFF** (US-PAY-011 TC-2, US-BIL-011 Case A's $11.20)
    creates a refund REQUEST from billing's side. Billing publishes no call into
    this module and this lane does not edit billing; `request_refund` is the
    function that handoff will call, unchanged.
  * **NO ENDPOINT AND NO SCREEN.** S58's Record-refund modal has no server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.db import IntegrityError, connection, transaction

from core import audit as core_audit
from core import errors
from core import permissions
from core import tenancy as core_tenancy

from apps.payments import ledger_seam, models, selectors
from apps.payments.exceptions import PaymentRuleError

__all__ = [
    "RefundResult",
    "REFUND_UNAVAILABLE",
    "request_refund",
    "approve_refund",
    "issue_refund",
    "clear_refund",
    "void_refund",
    # CR-141-BRC07 — the check number's one named correction (OQ-PAY-12614).
    "correct_refund_reference",
    "AUDIT_REFERENCE_CORRECTED",
    "CORRECTION_WINDOW_GUC",
    # CR-068 `CWP-045` — where the money is going back to (US-CWP-049).
    "destination_of",
    "DESTINATION_ORIGINAL",
    "DESTINATION_FALLBACK",
]

ZERO = Decimal("0")


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, resolved AT CALL TIME, or None.

    Same shape as every other seam in this repo (B1): payments never imports
    another module, and a name that is not there yet is None rather than an
    ImportError — the caller decides what an absence means, and here it means
    REFUSE (see `offset_before_refund`).
    """
    from importlib import import_module

    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(target, attribute, None)
    return fn if callable(fn) else None


def _as_decimal(value: Any) -> Decimal:
    """A served figure as a Decimal, never a float (CLAUDE.md rule 2)."""
    if value is None:
        return ZERO
    return value if isinstance(value, Decimal) else Decimal(str(value))


#: EP-PAY-03 US-PAY-011 §5's own audit codes, verbatim:
#: `refund.requested/approved/issued/voided`. `refund.cleared` completes the set
#: for TC-3, which US-PAY-011 §5 describes but does not name a code for.
AUDIT_REQUESTED = "refund.requested"
AUDIT_APPROVED = "refund.approved"
AUDIT_ISSUED = "refund.issued"
AUDIT_CLEARED = "refund.cleared"
AUDIT_VOIDED = "refund.voided"
#: CR-141-BRC07 — a mistyped check number replaced through the one named door.
#: Its own code rather than `refund.issued` again: a month-end reviewer greps
#: for a correction and must not have to read every payout to find one.
AUDIT_REFERENCE_CORRECTED = "refund.reference_corrected"

#: What a refund does NOT do, carried on EVERY result.
#:
#: ⚠ **`no_refund_receipt_queued` LEFT THIS TUPLE ON 2026-08-30 (CR-048 wave B
#: task B11) BECAUSE IT STOPPED BEING TRUE.** It read: *"BR-PAY-024 auto-queues
#: a refund receipt/notice to the platform outbound queue (print v1). That is
#: US-PAY-025 / EP-PAY-07 and this path does not make it — nothing is queued and
#: nothing is sent."* `issue_refund` makes it now, naming the `refund_issued`
#: event and the `email_refund_issued` wording that has been seeded on every
#: tenant and unreachable since 2026-08-16. The sentence is quoted rather than
#: deleted so a reader diffing an old result against a new one can see WHY a
#: problem row disappeared — the same courtesy `receipts.py` paid
#: `no_nsf_notice_queued` when B3 closed it.
#:
#: It was on EVERY result and the notice is only due at ISSUE, so removing it
#: from the tuple is also the correct scope: `issue_refund` now carries the real
#: outcome (queued, refused, or the utility's own switch) on that step alone,
#: and a request or an approval no longer reports a letter that was never due.
REFUND_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    {
        "code": "cross_account_arrears_not_checked",
        "br_ref": "BR-CUS-054",
        "detail": "Whether a customer who owes money on ANOTHER of their accounts may be "
        "refunded is OQ-135 and it is OPEN — refund, automatic offset and warn-the-clerk are "
        "all live options and two of them can be unlawful where the account holders differ. "
        "This refund was evaluated against THIS account's credit only; no other account of the "
        "customer was consulted, and none was silently offset.",
    },
    {
        "code": "account_balance_cache_not_updated",
        "br_ref": "BR-CUS-015",
        "detail": "`accounts.balance` is customers' CACHED column and payments may not write "
        "another module's table (B1 / DB-16).",
    },
)


# ══════════════════════════════════════════════════════════════════════════
# CR-048 WAVE B TASK B11 — THE REFUND NOTICE
# ══════════════════════════════════════════════════════════════════════════
#: The queue, resolved BY NAME. Payments imports nothing of notifications' (B1),
#: so the event key and the template code are STRINGS — which is exactly why a
#: test pins both against the owner's own constants.
QUEUE_MODULE = "notifications"
QUEUE_WRITE = "queue_document"

#: The SET-12 event this letter is. Checked against `rule_catalog.EVENT_KEYS`
#: before it was written down: `queue_document` REFUSES an event this platform
#: cannot fire, and that refusal would land after the money had already left.
EVENT_REFUND_ISSUED = "refund_issued"

#: The wording it renders from — seeded on every tenant since 2026-08-16, its
#: token whitelist owned by `catalogs.CATALOGS["email_refund_issued"]`. ⚠ It is
#: NOT the string `refund`, and the distinction is DEF-2511: a template code is
#: not a document type, and a queue row pinned to a code no catalogue declares
#: renders as nothing anybody wrote.
REFUND_TEMPLATE_CODE = "email_refund_issued"

#: `payment` — the kind `catalogs.LISTINGS["email_refund_issued"].category`
#: (CAT_PAYMENTS) selects, and one that carries BR-NOT-024's print floor. So a
#: utility that switches the refund email off still leaves a printed row, and
#: the suppression is recorded on it rather than vanishing.
SOURCE_PAYMENT = "payment"
CHANNEL_EMAIL = "email"

REFUND_NOTICE_QUEUED = "refund_notice_queued"
REFUND_NOTICE_QUEUE_UNAVAILABLE = "refund_notice_queue_unavailable"
REFUND_NOTICE_QUEUE_ERROR = "refund_notice_queue_error"


class _Pin:
    """The template pin, structurally. `notification_templates` is EP-NOT-02 and
    unbuilt, so a code is all there is to freeze (`services.TemplatePin`'s own
    shape, duplicated rather than imported for B1's reason)."""

    def __init__(self, code: str) -> None:
        self.code = code
        self.template_id = None
        self.version = None
        self.language = None


def _queue_refund_notice(refund: models.Refund, *, actor: Any) -> tuple[dict[str, Any], ...]:
    """ONE email telling a customer their refund has been paid. Outcome rows.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE IDEMPOTENCY TUPLE IS (tenant, "payment", REFUND id, channel, 0) ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **The REFUND's id, and never the payment's.** The payment this refund came
    out of already owns rows under its own id on this same source kind — its
    print receipt, its emailed receipt and, since B11, its texted one. Keying
    the refund letter on the payment would collide with the emailed receipt and
    **dedupe into it**: one row, the wrong document, `created=False`, and
    nothing anywhere reporting a problem. That is DEF-2512's mechanism exactly
    and `receipts.queue_failed_payment_notice` avoids it the same way, by
    keying the bounce letter on the reversing row rather than the original.
    A refund row is one per refund, so a replayed or re-driven issue writes
    nothing the second time (rule 6). A customer refunded twice gets two
    letters, because there are two refunds.

    ⚠ **A SAVEPOINT, AND IT IS NOT TIDINESS (CLAUDE.md law 14).** This runs
    after `issue_refund`'s transaction, but the caller may hold an outer one —
    and on PostgreSQL a statement that errors inside a transaction ABORTS it, so
    a bare `try` would catch the exception and leave the refund's own COMMIT
    doomed with *"current transaction is aborted"*. SQLite has no such state, so
    the broken version passes the whole suite. The nested `atomic()` is the only
    thing that makes the `except` below mean what it reads as.

    ⚠ **AND THE `except` IS BROAD ON PURPOSE**, for `receipts._queue_one`'s
    stated reason: the queue now reads a tenant rule table before it writes
    (CR-048 A1), which is one more thing standing between a clerk and money that
    has already left the bank. **A failed notification must never fail the money
    it describes** — and here the money is already gone, so raising would report
    a failure over a completed, frozen, unrepeatable act.
    """
    write = _resolve(QUEUE_MODULE, QUEUE_WRITE, "services")
    if write is None:  # pragma: no cover - notifications ships in this repo
        return (
            {
                "code": REFUND_NOTICE_QUEUE_UNAVAILABLE,
                "br_ref": "BR-PAY-024",
                "detail": f"apps.{QUEUE_MODULE}.services.{QUEUE_WRITE} is not published, so "
                "the customer has NOT been told their refund was paid. Reported rather "
                "than swallowed — the refund itself stands.",
            },
        )
    try:
        with transaction.atomic():
            written = write(
                source_type=SOURCE_PAYMENT,
                source_id=refund.pk,
                channels=(CHANNEL_EMAIL,),
                template=_Pin(REFUND_TEMPLATE_CODE),
                account_id=refund.account_id,
                actor=actor,
                # CR-048 wave A's join. Switch *Refund issued* off on Settings →
                # Notifications and no email is written; BR-NOT-024's floor on
                # `payment` keeps a printed row either way.
                event_key=EVENT_REFUND_ISSUED,
                job=None if actor is not None else "payments.refund",
                # The four facts `catalogs.CATALOGS["email_refund_issued"]`
                # whitelists, every one of them read off the refund row this
                # call was handed. `{amount}` is a STRING with its figure
                # already final (CLAUDE.md rule 2 — never a float and never a
                # number this module rounded), and `{reason}` is the clerk's own
                # words off the row rather than a category this module chose.
                render_context={
                    "amount": str(refund.amount),
                    "date": refund.issued_at,
                    "method": refund.method,
                    "reason": refund.reason,
                },
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return (
            {
                "code": REFUND_NOTICE_QUEUE_ERROR,
                "br_ref": "BR-PAY-024",
                "detail": f"the refund notice could not be queued: {failure} The refund "
                "stands and the money has left — a failed notification must never fail "
                "the money it describes.",
            },
        )
    messages = tuple(getattr(written, "messages", ()) or ())
    problems = tuple(getattr(written, "problems", ()) or ())
    if not messages:
        # The utility's rule left no channel. `queue_document` returns an EMPTY
        # write carrying the reason rather than raising (A1), and that reason IS
        # the outcome — a switch somebody chose, not a fault.
        return problems
    return (
        {
            "code": REFUND_NOTICE_QUEUED,
            "br_ref": "BR-PAY-024",
            "message_id": str(getattr(messages[0], "id", "")) or None,
            "created": bool(getattr(messages[0], "created", False)),
            "event_key": EVENT_REFUND_ISSUED,
            "detail": "the refund notice (template 'email_refund_issued') is on the "
            "platform outbound queue for this refund. Queueing is not sending: nothing "
            "dispatches in this release (BR-NOT-013), and the row says so.",
        },
        *problems,
    )


@dataclass(frozen=True)
class RefundResult:
    """One step of one refund's life.

    `created=False` is the idempotent replay of a REQUEST that already exists
    under the same submit token — S58's Record-refund button, double-clicked.

    `credit_position_after` is the SIGNED figure (PO ruling 2026-08-11); a
    caller asserts it rather than recomputing it.
    """

    refund_id: str
    status: str
    created: bool
    amount: Decimal
    currency: str
    #: ⚠ **`None` SINCE 2026-09-03 WHENEVER THE CREDIT CAME FROM MORE THAN ONE
    #: PAYMENT** (CR-059 CS-7, the PO's ruling of 2026-09-01 closing `OQ-195`).
    #: A refund now belongs to the ACCOUNT; naming a single source payment is
    #: still true and still served when there IS one — PE-9's $350.00 → $57.13
    #: — and every caller must survive its absence.
    payment_id: str | None
    #: The refund's address, and it is NEVER None. This is the member a screen
    #: renders, a report groups on, and `issue_refund` draws the credit from.
    account_id: str = ""
    credit_position_after: Decimal = ZERO
    journal_entry_id: str | None = None
    posting_key: str | None = None
    problems: tuple[dict[str, Any], ...] = field(default=REFUND_UNAVAILABLE)


def _account_of(tenant_id: Any, payment_id: Any) -> Any:
    """The account a payment belongs to — the subject of the offset check."""
    return (
        models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id)
        .values_list("account_id", flat=True)
        .first()
    )


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _actor_id(actor: Any) -> Any:
    return getattr(actor, "id", None) or getattr(actor, "pk", None)


def _moment(value: Any, *, what: str) -> datetime:
    """Every timestamp is an INPUT (BR-TEN-043, gate G6). Nothing reads a clock.

    A refund dated by whenever the request happened to be processed would let
    the server's load decide which accounting period the money left in.
    """
    if not isinstance(value, datetime):
        raise PaymentRuleError(
            f"a refund needs the moment it was {what}, and it is the caller's (BR-TEN-043 — the "
            "caller names the moment; gate G6 greps every money path for a clock read). A "
            "defaulted timestamp would let the minute a request was processed decide which "
            "month a cheque left the bank in.",
            br_ref="BR-PAY-021",
        )
    return value


def _amount(value: Any) -> Decimal:
    """A refund amount: a Decimal, strictly positive (hard rule 2)."""
    if isinstance(value, float):
        raise PaymentRuleError(
            f"refund amount {value!r} is a float. Money is NUMERIC(18,6) and never a binary "
            "fraction (CLAUDE.md rule 2). REFUSED rather than converted, because a conversion "
            "hides the place where money became binary.",
            br_ref="BR-PAY-002",
        )
    if not isinstance(value, Decimal):
        raise PaymentRuleError(
            f"refund amount {value!r} is a {type(value).__name__}; money is a Decimal "
            "(CLAUDE.md rule 2).",
            br_ref="BR-PAY-002",
        )
    if value <= ZERO:
        raise PaymentRuleError(
            f"refund amount {value} must be greater than zero. A refund of nothing is not a "
            "refund, and a NEGATIVE refund is money coming IN — which is a payment, recorded "
            "through `record_payment`, never a refund wearing a minus sign.",
            br_ref="BR-PAY-014",
        )
    return value


def _method(method: str) -> str:
    """BR-PAY-014's v1 set. `card` is refused BY NAME with its rails note."""
    if method in ("card", "credit_card", "debit_card"):
        raise PaymentRuleError(
            f"a {method!r} refund is not available in this release. BR-PAY-014 puts card refunds "
            "behind the payment rails (W7) — there is no gateway to send the reversal to, so a "
            "card refund recorded today would draw the customer's credit down and return them "
            "nothing. Cheque and ACH are available now.",
            br_ref="BR-PAY-014",
        )
    if method not in models.REFUND_METHODS:
        raise PaymentRuleError(
            f"{method!r} is not a refund method. BR-PAY-014 ships {list(models.REFUND_METHODS)} "
            "in v1.",
            br_ref="BR-PAY-014",
        )
    return method


def _cheque_number_for_issue(refund: models.Refund, supplied: str | None) -> str | None:
    """The number this refund's cheque will be recorded under — DEF-PAY-6331.

    Three rules, in this order, and each is the service half of a law the
    database also holds (`payments/0041`). Both halves exist deliberately: the
    test database is SQLite and has no triggers, so a Postgres-only guard is a
    guard the suite is structurally unable to execute (hard-won law 14).

      1. **Write-once AT ISSUE.** A row that already names its cheque keeps
         it. A DIFFERENT number is refused BY NAME rather than silently winning
         — `DEF-CUS-3653`'s lesson is that a value that vanishes is invisible to
         every check this repo has. ⚠ **AMENDED 2026-09-23 (`CR-141-BRC07`):**
         this rule read *"never changed"* and the PO has since signed a
         correction (`OQ-PAY-12614`, option b). Issue still refuses to
         overwrite — issuing is not a correction — and the refusal now names
         `correct_refund_reference`, the one door that may replace a number.
      2. **Required for a cheque**, at the act that writes the cheque
         (US-PAY-011 §5, *"required for check"*, whose text names no act).
      3. **Nothing for ACH**, because `BR-PAY-014` is *"check/ACH v1"* and only
         the cheque half has a cheque number. A requirement widened past the
         method it belongs to would block every ACH refund in the product.

    Returns what `refunds.reference` should hold after this issue, which for an
    unchanged row is exactly what it holds now.
    """
    already = (refund.reference or "").strip()
    offered = (supplied or "").strip()

    if already and offered and offered != already:
        # ⚠ The `{id}` below sits in a PLAIN string on purpose: it is the
        # route's own spelling, and inside the f-string it would be formatted.
        raise PaymentRuleError(
            f"this refund already names check #{already}, so #{offered} is not recorded and "
            "nothing is issued. Issuing writes the check number once. A number keyed wrongly "
            "is replaced through Correct check number (POST /refunds/{id}/correct-reference, "
            "OQ-PAY-12614), which asks for a note saying why.",
            br_ref="BR-PAY-014",
        )

    number = already or offered
    if refund.method == models.REFUND_METHOD_CHECK and not number:
        raise PaymentRuleError(
            "a cheque refund needs its cheque number before it can be issued (US-PAY-011 §5: "
            "'required for check'). PE-9's is #10241. Without it the refund cannot be matched "
            "to the bank line when it clears (BR-PAY-021), and a payment out that bank rec can "
            "never find is how a reconciliation stops tying. Nothing was written: the money "
            "has not moved and the refund is still approved and waiting.",
            br_ref="BR-PAY-014",
        )
    return number or None


def _source_payment(tenant_id: Any, payment_id: Any) -> models.Payment:
    """The payment whose overpayment this refund draws back (B2 §2, OQ-167)."""
    try:
        payment = models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).first()
    except (ValueError, TypeError):
        payment = None
    if payment is None:
        raise PaymentRuleError(
            f"payment {payment_id!r} is not one of this tenant's payments, so a refund has "
            "nothing to draw on (CLAUDE.md rule 1). Nothing is written.",
            br_ref="BR-PAY-014",
        )
    if payment.status == models.PAYMENT_PROCESSING:
        raise PaymentRuleError(
            f"payment {payment.payment_no or payment.pk} has not cleared, so there is no money "
            "to give back. A credit exists only once the money has actually arrived "
            "(BR-PAY-021).",
            br_ref="BR-PAY-014",
        )
    return payment


def _address(tenant_id: Any, *, payment_id: Any, account_id: Any) -> tuple[Any, Any]:
    """WHOSE refund this is — `(payment_or_None, account_id)`. CR-059 CS-7.

    The PO ruled on 2026-09-01 (`OQ-195`, option (a)) that a refund belongs to
    the ACCOUNT, so this resolves the address once and every caller downstream
    reads `account_id` rather than walking a payment that may not be there.

    **A refund with neither is REFUSED BY NAME**, not by the NOT NULL constraint
    `payments/0018` puts on the column. The constraint is the guarantee; this is
    the sentence a clerk can act on, and hard-won law 1 is why both exist.

    **NAMING BOTH IS LAWFUL AND THE PAIR IS CHECKED**, which is the same
    reasoning `refunds_api._refuse_a_payment_on_another_account` already applies
    at the door: without it, a refund could be addressed to account A and funded
    by account B's overpayment, and the credit test, the offset and the ledger
    posting would all be B's while the row said A. That check is at the route
    for the request path; this one is in the SERVICE, so a job, a shell or a
    second endpoint that forgot it is refused all the same (BR-SHL-025).
    """
    payment = None if payment_id is None else _source_payment(tenant_id, payment_id)
    if payment is not None:
        owner = str(payment.account_id)
        if account_id is not None and str(account_id) != owner:
            raise PaymentRuleError(
                f"payment {payment.payment_no or payment.pk} belongs to account {owner} and "
                f"this refund is addressed to {account_id}. A refund whose two links disagree "
                "is a row nobody can read: the credit test, the offset check and the ledger "
                "posting would all be one account's while the screen said the other's.",
                br_ref="BR-PAY-014",
            )
        return payment, payment.account_id
    if account_id is None:
        raise PaymentRuleError(
            "a refund names the account it is against — and, when the credit came from ONE "
            "overpayment, the payment behind it as well. Neither was given, so there is no "
            "credit to test and nobody to pay. Nothing is written. (The PO ruled on "
            "2026-09-01 that a refund belongs to the account; a refund with no address is a "
            "cheque with no addressee.)",
            br_ref="BR-PAY-014",
        )
    if not _account_exists(tenant_id, account_id):
        raise PaymentRuleError(
            f"account {account_id!r} is not one of this tenant's, so a refund has nothing to "
            "draw on (CLAUDE.md rule 1). Nothing is written.",
            br_ref="BR-TEN-003",
        )
    return None, account_id


def _account_exists(tenant_id: Any, account_id: Any) -> bool:
    """This tenant's account? — through customers' own published queryset (B1).

    Payments may not walk another module's ORM, so the read is resolved BY NAME,
    the same shape `services._account` and `transfer._account` use. An unwired
    seam REFUSES rather than answering True: a refund addressed to an account
    this process cannot see is money about to leave for somebody nobody checked.
    """
    read = _resolve("customers", "account_queryset")
    if not callable(read):
        raise PaymentRuleError(
            "apps.customers.selectors.account_queryset is not published, so this process "
            "cannot see accounts and cannot tell whose refund this is. Refused rather than "
            "assumed — money is about to leave the building.",
            br_ref="BR-CUS-054",
        )
    try:
        return read().filter(tenant_id=tenant_id, pk=account_id).exists()
    except (ValueError, TypeError):
        return False


def _currency_of(tenant_id: Any, account_id: Any, payment: Any) -> str:
    """The refund's CHAR(3) — hard rule 2's other half (CR-059 CS-7).

    The PAYMENT's code when there is one, because that is what this row has
    always carried and moving it would change a figure on rows already written.
    Otherwise the ACCOUNT's, which is the only other place the fact lives.
    BR-TEN-042 locks a utility to one currency, so the two can never
    legitimately differ; where the account states none, `USD` is the same
    default `Refund.currency` and `Payment.currency` already declare, and it is
    the DEFAULT rather than a conversion.
    """
    if payment is not None:
        return payment.currency
    read = _resolve("customers", "account_queryset")
    if callable(read):
        row = read().filter(tenant_id=tenant_id, pk=account_id).values_list("currency", flat=True)
        found = row.first()
        if found:
            return found
    return "USD"


def _credit_or_refuse(account_id: Any, amount: Decimal, *, at: str) -> Decimal:
    """BR-PAY-014's *"only from a real credit balance"*, checked and named.

    Called at REQUEST and again at ISSUE. See the module docstring for why once
    is not enough — the money moves at issue, and a credit can be spent or
    pulled back by a bounce in between.
    """
    credit = selectors.account_credit_position(account_id)
    if credit < ZERO:
        raise PaymentRuleError(
            f"this account's credit position is {credit}, which is a DEBT and not a credit — the "
            "customer OWES the utility that money (Product Owner ruling 2026-08-11: a credit "
            "may go negative after a bounced cheque and 'Yes, it's a real debt'). A refund pays "
            "money out of a credit; there is none here to pay out of.",
            br_ref="BR-PAY-014",
        )
    if credit == ZERO:
        raise PaymentRuleError(
            "this account holds no credit balance, so there is nothing to refund (BR-PAY-014: "
            "refunds come only from a REAL credit). A refund granted here would be a payment "
            "out with nothing behind it.",
            br_ref="BR-PAY-014",
        )
    if amount > credit:
        raise PaymentRuleError(
            f"a refund of {amount} is more than this account's credit of {credit}. BR-PAY-014 "
            f"allows a refund only out of a real credit balance ({at}), so the most that can be "
            "refunded is what the utility actually holds for this customer.",
            br_ref="BR-PAY-014",
        )
    return credit


#: The customers read this module needs to honour the offset ruling. Named once
#: so the contract is greppable from BOTH sides of the boundary — the same
#: posture `apps/billing/final_bill.py` takes with its two customers reads.
#:
#:     apps.customers.selectors.arrears_on_other_accounts(account_id) -> Decimal
#:
#: The total currently OVERDUE on every OTHER account belonging to the same
#: customer entity (BR-CUS-054). Zero when there are none.
CROSS_ACCOUNT_ARREARS_READ = "arrears_on_other_accounts"


def offset_before_refund(account_id: Any, *, requested: Decimal) -> tuple[Decimal, Decimal]:
    """**OFFSET FIRST** — PO 2026-08-12, OQ-135 CLOSED. Returns `(offset, refundable)`.

    Verbatim: *"offset first"*. A customer holding a credit on one account and
    an arrear on another has the credit applied against the arrear, and only
    what remains is paid out.

    Worked, on the repo fixture: **$57.13** credit on one account, **$948.20**
    overdue by 91 days on another with a final notice already sent. The whole
    $57.13 offsets and **nothing** is refunded — where the refund reading would
    post a cheque to somebody the utility is about to disconnect.

    **THE UNWIRED CASE REFUSES, and that is the ruling rather than caution.**
    "Offset first" is not a thing that can be done blind: a module that cannot
    SEE the other accounts cannot offset against them, and paying out anyway
    would be the exact behaviour the ruling replaced. So when customers has not
    published the read, this refuses and names it — rather than returning
    "no arrears found", which is a claim.

    ⚠ **WHAT THIS FUNCTION DOES NOT DO: MOVE THE MONEY.** It computes the offset
    and hands both figures back. Actually applying a credit from one account
    against another account's debt is a TRANSFER between two financial records,
    and that is `apps/billing/final_bill.py`'s balance-transfer path — one
    reviewed writer, not two. A caller that takes the `offset` figure and does
    nothing with it has not offset anything; the result carries both numbers so
    that cannot happen silently.
    """
    read = _resolve("customers", CROSS_ACCOUNT_ARREARS_READ)
    if not callable(read):
        raise PaymentRuleError(
            f"the PO ruled on 2026-08-12 that a customer owing on ANOTHER account is offset "
            f"first, and `apps.customers.selectors.{CROSS_ACCOUNT_ARREARS_READ}` is not "
            "published — so this process cannot see the other accounts and cannot offset "
            "against them. Refunding anyway would post money to somebody the utility may be "
            "about to disconnect, which is the behaviour the ruling replaced. Nothing was paid.",
            br_ref="BR-CUS-054",
        )
    arrears = _as_decimal(read(account_id))
    if arrears <= ZERO:
        return ZERO, requested
    offset = min(requested, arrears)
    return offset, requested - offset


def request_refund(
    actor: Any,
    *,
    payment_id: Any = None,
    account_id: Any = None,
    amount: Decimal,
    method: str,
    requested_at: datetime,
    reason: str | None = None,
    reference: str | None = None,
    memo: str | None = None,
    cross_account_check: bool = False,
    idempotency_key: str | None = None,
) -> RefundResult:
    """Step 1 — a request. NO MONEY MOVES (BR-PAY-014, r12 #5).

    The row exists from here so J15 step 2's approval queue has something to
    show, and BR-PAY-037's *"both acts recorded distinctly"* has somewhere to
    record the FIRST act.

    ════════════════════════════════════════════════════════════════════════
    A REFUND BELONGS TO THE ACCOUNT — CR-059 CS-7, 2026-09-03
    ════════════════════════════════════════════════════════════════════════
    **The PO ruled the MECHANISM on 2026-08-12** (`OQ-167`), verbatim: *"user
    can do a refund or issue a credit - it will be manula decision, provide a
    mecahnism to complete the tasks"*, worked on an account that overpays
    **$40.00 in June and $17.13 in July** and asks for the **$57.13** back —
    **one cheque, one decision**. **And the SCHEMA half on 2026-09-01**
    (`OQ-195`, option (a)): `refunds.payment_id` becomes nullable and
    `refunds.account_id` sits beside it. `payments/0018` is that ruling.

    **So `payment_id` is now OPTIONAL and `account_id` is what a refund always
    has.** Three shapes are lawful and they are not three code paths:

      * `payment_id` alone — the historic call, unchanged. PE-9's **$350.00 →
        $57.13** goes through exactly as it did; the account is read off the
        payment and stamped on the row.
      * `account_id` alone — **the case this change exists for.** The credit
        came from several payments and no single one of them is *the* source.
      * both — accepted, and the payment is REFUSED if it is not that account's,
        because a refund whose two links disagree is a row nobody can read.

    **What is NOT lawful is neither.** A refund with no address is a cheque with
    no addressee, and it is refused by name rather than by a database constraint
    a clerk would meet as a 500.

    `idempotency_key` is S58's submit token. With none, a double-clicked Record
    button writes two requests — so the caller that owns a submit button must
    pass one, and it is named rather than defaulted to a generated uuid, because
    a key this function invented would differ on the second submit and would
    dedupe nothing while looking like it did (the OQ-127 argument, applied
    outbound).
    """
    tenant_id = _tenant_id()
    amount = _amount(amount)
    payment, account_id = _address(tenant_id, payment_id=payment_id, account_id=account_id)
    if cross_account_check:
        # PO 2026-08-12 (OQ-135): OFFSET FIRST. Money does not leave while this
        # customer owes on another account.
        offset, _refundable = offset_before_refund(account_id, requested=amount)
        if offset > ZERO:
            raise PaymentRuleError(
                f"this customer owes about {offset} on another of their accounts, and the PO "
                f"ruled on 2026-08-12 that the credit is offset against it FIRST. The {amount} "
                "is not refunded here: applying it is a balance TRANSFER between two financial "
                "records, which has one reviewed writer, and the figure above is the cached "
                "balance (BR-CUS-015) — good enough to stop a payout, not good enough to "
                "subtract from one.",
                br_ref="BR-CUS-054",
            )
    method = _method(method)
    requested_at = _moment(requested_at, what="requested")
    # ⚠ **THE CHEQUE-NUMBER REFUSAL USED TO BE HERE AND IT HAS MOVED TO
    # `issue_refund` (DEF-PAY-6331, 2026-09-23).** It read, at this line:
    #
    #     if method == REFUND_METHOD_CHECK and not (reference or "").strip():
    #         raise … "a cheque refund needs its cheque number
    #                  (US-PAY-011 §5: 'required for check')"
    #
    # **It asked for a fact that does not exist yet.** A refund is REQUESTED
    # before Finance approves it and long before anybody writes a cheque, so
    # the only ways to satisfy this were to leave the field blank — after which
    # no surface anywhere could ever record the real number, because the column
    # was frozen from row creation — or to type a guess into a money record.
    #
    # **US-PAY-011 §5 is not weakened: it names no ACT.** *"required for
    # check"* is still enforced, at the act that writes the cheque, where the
    # clerk is holding it. The blueprint draws it there and says why in four
    # words — *"the only record of which cheque this was"* (p078, annotation ②)
    # — and draws 6·3a Raise with Amount, Reason, How and Note and no cheque
    # number at all.
    #
    # ⚠ `reference` STAYS A PARAMETER OF THIS FUNCTION, and that is not a
    # leftover. A refund whose number is genuinely already known — a back-dated
    # import, or the demo fixture recording PE-9's #10241 — has one place to
    # say so, and `payments/0041`'s write-once guard means the two writers can
    # never disagree: whichever one gets there first is the only one that ever
    # writes. **The product's own door no longer sends one**
    # (`POST /accounts/{id}/refunds` refuses it by name), so a clerk has exactly
    # one moment to type it.

    if idempotency_key is not None:
        already = models.Refund.objects.filter(
            tenant_id=tenant_id, idempotency_key=idempotency_key
        ).first()
        if already is not None:
            return _result(already, created=False, extra=_duplicate_problem(already))

    try:
        with transaction.atomic():
            credit = _credit_or_refuse(account_id, amount, at="at request")
            refund = models.Refund.objects.create(
                tenant_id=tenant_id,
                # CR-059 CS-7: the payment is OPTIONAL and the account is not.
                payment=payment,
                account_id=account_id,
                amount=amount,
                # The ACCOUNT's currency, not the payment's — a refund with no
                # payment behind it has no other place to read it from, and
                # BR-TEN-042 locks a utility to one currency so the two can never
                # legitimately differ.
                currency=_currency_of(tenant_id, account_id, payment),
                status=models.REFUND_REQUESTED,
                method=method,
                reference=reference,
                reason=reason,
                memo=memo,
                requested_by_id=_actor_id(actor),
                requested_at=requested_at,
                idempotency_key=idempotency_key,
            )
            core_audit.money_action(
                actor,
                AUDIT_REQUESTED,
                "refund",
                str(refund.pk),
                after={
                    "payment_id": None if payment is None else str(payment.pk),
                    "account_id": str(account_id),
                    "amount": str(amount),
                    "currency": refund.currency,
                    "method": method,
                    "reference": reference,
                    "reason": reason,
                    "credit_at_request": str(credit),
                    "requested_at": requested_at.isoformat(),
                    "idempotency_key": idempotency_key,
                    "job": None if actor is not None else "payments.refund",
                },
            )
            return _result(refund, created=True, credit=credit - amount)
    except IntegrityError:
        winner = models.Refund.objects.filter(
            tenant_id=tenant_id, idempotency_key=idempotency_key
        ).first()
        if winner is None:
            raise
        return _result(winner, created=False, extra=_duplicate_problem(winner))


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-014")
def approve_refund(
    actor: Any, *, refund_id: Any, approved_at: datetime, memo: str | None = None
) -> RefundResult:
    """Step 2 — Admin approval (BR-PAY-014), server-enforced.

    *"Approval is Admin-only, server-enforced"* (US-PAY-011 §6, TC-6). The guard
    is `@require_role` on the SERVICE, not on an endpoint: BR-SHL-025 makes
    server-side enforcement THE enforcement, so a job, a shell or an endpoint
    that forgot to gate is refused all the same.

    **BR-PAY-037 is exercised, not worked around.** The same user holding the
    approver role MAY approve their own request in v1 — J15 step 3 is exactly
    that — and the control is that BOTH acts are recorded distinctly, which is
    why `requested_by_id` and `approved_by_id` are separate columns rather than
    a flag. Enforced separation of duties is v2 and nothing here pre-empts it.
    """
    refund = _refund(_tenant_id(), refund_id)
    approved_at = _moment(approved_at, what="approved")
    if refund.status != models.REFUND_REQUESTED:
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} is {refund.status!r} and only a REQUESTED "
            "refund can be approved. Approval gates the money exactly once (BR-PAY-014).",
            br_ref="BR-PAY-014",
        )
    with transaction.atomic():
        refund.status = models.REFUND_APPROVED
        refund.approved_by_id = _actor_id(actor)
        refund.approved_at = approved_at
        refund.save(update_fields=["status", "approved_by_id", "approved_at", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_APPROVED,
            "refund",
            str(refund.pk),
            after={
                "approved_by": str(_actor_id(actor)),
                "approved_at": approved_at.isoformat(),
                "self_approved": str(_actor_id(actor)) == str(refund.requested_by_id),
                "amount": str(refund.amount),
                "memo": memo,
                "job": None if actor is not None else "payments.refund",
            },
        )
    return _result(refund, created=False)


@permissions.require_role(
    permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-PAY-1071"
)
def issue_refund(
    actor: Any,
    *,
    refund_id: Any,
    issued_at: datetime,
    reference: str | None = None,
    entry_date: date | None = None,
) -> RefundResult:
    """Step 3 — the money leaves. DR customer-credit / CR cash (BR-PAY-014).

    **The only step in this file that moves money**, and the only one that
    posts. The credit test runs AGAIN here (see the module docstring): an
    approval given on Tuesday must not pay out a credit that a Wednesday bounce
    pulled back.

    All of it or none of it: the status move, the audit row and the journal
    entry are one transaction. A refund marked issued with nothing in the books
    is unrepairable — the row is frozen the instant it commits.

    ⚠ **A BILLING CLERK MAY ISSUE, FROM 2026-09-03. THIS GATE WAS ADMIN-ONLY
    FOR TWO DAYS AND THE PRODUCT OWNER WIDENED IT — *"q6 yes Clark can issue
    refund"*.** `BR-PAY-1071` is AMENDED, not replaced, and the chain is stated
    rather than assumed: its 2026-09-01 sentence read *"issuing a refund is
    Admin-only"* and it now reads *"Admin or Billing Clerk"*. **The reading that
    makes it coherent is the PO's own logic: THE APPROVAL IS THE CONTROL.**
    `approve_refund` above stays `@require_role(SYSTEM_ADMIN)` — nothing is
    loosened about who AUTHORISES money leaving — and issuing is the clerical
    act that carries out a decision an Admin has already made. In a two-person
    utility the Admin who approves is often not the person at the counter
    writing the cheque, and the old gate stopped the cheque rather than the
    decision.

    ⚠ **THE GATE IS WIDER; IT IS NOT GONE, AND THAT DISTINCTION IS THE WHOLE
    ORIGINAL FINDING.** CS-6 called it *"a real hole: `issue_refund` and
    `clear_refund` carry no role gate at all, which is why the no-door gate
    never listed them"* — this function drew **$57.13** out of `2400 Customer
    credit` and into a cheque for ANY caller, `actor=None` included, while
    `approve_refund` beside it had been gated since it was written. G52 could
    not see it either: that gate's universe IS the set of `@require_role`
    declarations, so an ungated money-out function is invisible to the check
    written to find doorless money-out functions. **An EXECUTIVE is still
    refused here**, which is what keeps the decorator's presence observable: a
    test that only proved an Admin succeeds would pass with the gate deleted.

    Reachable as an Admin or a Billing Clerk from `refunds_api.refund_issue`,
    which mirrors this gate rather than widening it (BR-SHL-025).

    **WHAT THIS RULING DOES NOT LOOSEN, said here because a rule that names one
    channel is read as permission for every other:** `approve_refund` stays
    Admin, `void_refund` stays Admin, `clear_refund` stays Admin or Executive (a
    bank fact, not an approval), `_credit_or_refuse` below still refuses a
    refund no credit funds — at request AND again here — hard rule 4 still
    forbids editing an issued refund, hard rule 5 still means only the ledger
    posting service moves the money, and hard rule 7 still writes the audit row
    naming who issued it.

    ════════════════════════════════════════════════════════════════════════
    `reference` — THE CHEQUE NUMBER, WRITTEN HERE BECAUSE HERE IS WHERE THE
    CHEQUE IS WRITTEN (DEF-PAY-6331, 2026-09-23)
    ════════════════════════════════════════════════════════════════════════
    **This argument did not exist until today, and that was the defect.** The
    number was collected on the RAISE form — days before Finance approves
    anything and before a cheque exists — and `refunds.reference` was frozen
    from the instant the row was created, so when the real cheque was finally
    written there was **nowhere in the product to record its number**.

    The blueprint puts it here and says why in four words: *"the only record of
    which cheque this was"* (`06 Payments Page Blueprint.pdf` p078, annotation
    ②, read as an image per B14 rule 42).

    **Three rules govern it and they are enforced in that order:**

      1. **Required for a cheque.** US-PAY-011 §5's *"required for check"*,
         unchanged in substance and moved in act: a cheque refund may not be
         issued unless the row ENDS UP with a number, from this argument or
         from one already on it. A payment out that bank rec can never find is
         how a reconciliation stops tying (BR-PAY-021, applied outbound). An
         ACH refund needs none — `BR-PAY-014` is *"check/ACH v1"* and only the
         cheque half has a cheque number.
      2. **Write-once AT ISSUE.** A row that already names its cheque keeps
         it, and a DIFFERENT number is refused rather than silently winning.
         `payments/0041` enforces the same law in the database; this check
         exists as well because the test database is SQLite and has no
         triggers at all (hard-won law 14), so a Postgres-only guard would be
         proved by a suite structurally unable to execute it. ⚠ **FROM
         2026-09-23 THE NUMBER IS CORRECTABLE AFTERWARDS — through
         `correct_refund_reference` and nothing else** (`OQ-PAY-12614`,
         `payments/0043`). Issuing is still not a correction.
      3. **Written in the SAME statement as the status move**, inside the same
         transaction as the posting and the audit row. A refund can never stand
         ISSUED for even an instant with no record of which cheque it was. ~~and
         nothing ever patches the number on afterwards — the trigger would
         refuse that~~ — **struck 2026-09-23 (`CR-141-BRC07`)**: the trigger
         still refuses every OTHER statement that would patch it, and opens for
         exactly one, `correct_refund_reference` below.

    **WHAT A CORRECTION LOOKS LIKE — AMENDED 2026-09-23, AND THE AMENDMENT IS THE
    PO'S.** This paragraph read *"since there is no UPDATE path: a cheque written
    for the wrong amount, or typed wrong, is VOIDED … and raised again."* **Half
    of it still stands and half is reversed.** A check written for the WRONG
    AMOUNT is still voided — a status move plus a reversing posting that
    restores the credit (US-PAY-011 TC-4) — and raised again, because the amount
    is money and nothing corrects money in place. A check number **typed wrong**
    is now corrected through `correct_refund_reference` (`OQ-PAY-12614`, PO
    2026-09-23: *"(b) Allow a correction, the same way you allowed it for
    payments on 2 September"*), with a required note and an audit row carrying
    the old number and the new.
    """
    tenant_id = _tenant_id()
    refund = _refund(tenant_id, refund_id)
    issued_at = _moment(issued_at, what="issued")
    if refund.status != models.REFUND_APPROVED:
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} is {refund.status!r} and only an APPROVED "
            "refund can be issued. BR-PAY-014 requires Admin approval BEFORE the money moves — "
            "the approval is what gates it, so issuing without one would make the gate "
            "decorative.",
            br_ref="BR-PAY-014",
        )
    # ⚠ **`refund.account_id`, NOT `refund.payment.account_id` (CR-059 CS-7).**
    # `payment_id` became NULLABLE on 2026-09-03 under the PO's ruling of
    # 2026-09-01 (`OQ-195`, option (a)) — a refund belongs to the ACCOUNT — so a
    # refund raised against a credit built from two overpayments has no single
    # payment to walk through. Reading it that way would have thrown
    # `AttributeError: 'NoneType' object has no attribute 'account_id'` on the
    # one step of the whole lifecycle that moves a cent.
    account_id = refund.account_id
    with transaction.atomic():
        # ⚠ **THE CREDIT IS TESTED BEFORE THE CHEQUE NUMBER, AND THE ORDER IS THE
        # ANSWER A CLERK GETS.** A refund whose credit has evaporated cannot be
        # issued at all, with or without a cheque number; one with no cheque
        # number is issuable the moment somebody types one. Asking for the
        # number first would send a clerk to find the chequebook and then walk
        # them into the wall that was there all along.
        _credit_or_refuse(account_id, refund.amount, at="at issue")
        cheque_number = _cheque_number_for_issue(refund, reference)
        refund.status = models.REFUND_ISSUED
        refund.issued_at = issued_at
        # The cheque number RIDES the status move — one statement, inside the
        # transaction that posts and audits. A second UPDATE would be a patch on
        # a money record, and `payments/0041`'s write-once guard refuses one.
        refund.reference = cheque_number
        refund.save(update_fields=["status", "issued_at", "reference", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_ISSUED,
            "refund",
            str(refund.pk),
            after={
                "account_id": str(account_id),
                "amount": str(refund.amount),
                "currency": refund.currency,
                "method": refund.method,
                "reference": refund.reference,
                "issued_at": issued_at.isoformat(),
                "job": None if actor is not None else "payments.refund",
            },
        )
        posting = ledger_seam.post_refund_executed(
            refund=refund,
            account_id=account_id,
            entry_date=entry_date or issued_at.date(),
            posted_at=issued_at,
            actor=actor,
        )
        # Write-once stamp, in the same transaction — the entry names the refund
        # as its source and so cannot exist before it. Same shape and same
        # reason as `payments.journal_entry_id`; without it a VOID could not
        # name the entry `reverse_entry` must mirror.
        refund.journal_entry_id = posting.entry_id
        refund.save(update_fields=["journal_entry_id", "updated_at"])
    # ⚠ **OUTSIDE THE TRANSACTION, DELIBERATELY** (CR-048 wave B task B11). The
    # money has moved and the row is frozen; a queue write that failed must not
    # roll back a refund the clerk has been told about, and BR-NOT-005 makes the
    # queue the durable record rather than this call. The outcome travels on
    # `problems` — which is what `no_refund_receipt_queued` used to occupy, and
    # is now a real result instead of a standing apology.
    return _result(
        refund, created=True, posting=posting, extra=_queue_refund_notice(refund, actor=actor)
    )


@permissions.require_role(permissions.SYSTEM_ADMIN, permissions.EXECUTIVE, br_ref="BR-PAY-1071")
def clear_refund(actor: Any, *, refund_id: Any, cleared_at: datetime) -> RefundResult:
    """Step 4 — the cheque cleared the bank (US-PAY-011 TC-3).

    A status move and a date. **It posts nothing**: the money left the books
    when the refund was ISSUED, and posting again on clearing would take it out
    twice. What clearing gives is the date bank rec matches on (BR-PAY-021's
    family, applied outbound).

    ⚠ **ADMIN OR EXECUTIVE, AND THE SECOND ROLE IS THE POINT (BR-PAY-1071,
    CR-059 CS-6, 2026-09-01).** CS-6 names the gate and its reason in one
    breath: *"`POST /refunds/{id}/clear` (Admin or Executive — **it is a bank
    fact, not an approval**)"*. Clearing asserts what the BANK did; it approves
    nothing, moves nothing and posts nothing, and A4 puts the finance/reconcile
    column in the Executive's hands (`AdminOrExecutive` already gates every
    deposit-batch and bank-statement route in `apps/payments/api.py`). Gating it
    to Admin alone would mean the person doing the bank reconciliation cannot
    record that a cheque they can see on the statement has cleared.

    **A Billing Clerk is refused**, which is a narrowing of what this function
    accepted until today: it accepted anybody, including `actor=None`.
    """
    refund = _refund(_tenant_id(), refund_id)
    cleared_at = _moment(cleared_at, what="cleared")
    if refund.status != models.REFUND_ISSUED:
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} is {refund.status!r}; only an ISSUED refund "
            "can clear. A refund that was never issued has no cheque at the bank.",
            br_ref="BR-PAY-021",
        )
    with transaction.atomic():
        refund.status = models.REFUND_CLEARED
        refund.cleared_at = cleared_at
        refund.save(update_fields=["status", "cleared_at", "updated_at"])
        core_audit.money_action(
            actor,
            AUDIT_CLEARED,
            "refund",
            str(refund.pk),
            after={
                "cleared_at": cleared_at.isoformat(),
                "amount": str(refund.amount),
                "job": None if actor is not None else "payments.refund",
            },
        )
    return _result(refund, created=False)


@permissions.require_role(permissions.SYSTEM_ADMIN, br_ref="BR-PAY-014")
def void_refund(
    actor: Any,
    *,
    refund_id: Any,
    voided_at: datetime,
    void_reason: str,
    entry_date: date | None = None,
) -> RefundResult:
    """A cheque lost in the post — VOID with a reversing posting (TC-4).

    *"Status → Void with reversing posting (credit restored 57.13); new refund
    issuable; no row deleted."* Three things that follow and are each asserted:

      * **No row is deleted.** The trigger refuses DELETE in every status; the
        void is a status move plus a NEW mirror entry (hard rule 4).
      * **The credit comes back by exactly what left.** `reverse_refund_entry`
        hands the ledger its own entry and the sides are swapped — nothing here
        recomputes 57.13.
      * **A new refund is then issuable**, because the credit position is
        computed from rows and a voided refund is excluded from it.
    """
    refund = _refund(_tenant_id(), refund_id)
    voided_at = _moment(voided_at, what="voided")
    if not (void_reason or "").strip():
        raise PaymentRuleError(
            "voiding a refund needs a reason. A cheque that left the building and came back is "
            "a fact somebody has to be able to reconstruct in a year (hard rule 7).",
            br_ref="BR-PAY-014",
        )
    if refund.status not in (models.REFUND_ISSUED, models.REFUND_CLEARED):
        raise PaymentRuleError(
            f"refund {refund.reference or refund.pk} is {refund.status!r}. Only a refund that "
            "has actually gone out can be voided — a REQUESTED or APPROVED one has moved no "
            "money and posted nothing, so there is nothing to reverse.",
            br_ref="BR-PAY-014",
        )
    with transaction.atomic():
        posting = ledger_seam.reverse_refund_entry(
            refund=refund,
            entry_date=entry_date or voided_at.date(),
            posted_at=voided_at,
            actor=actor,
        )
        refund.status = models.REFUND_VOID
        refund.voided_at = voided_at
        refund.void_reason = void_reason
        refund.void_journal_entry_id = posting.entry_id
        refund.save(
            update_fields=[
                "status",
                "voided_at",
                "void_reason",
                "void_journal_entry_id",
                "updated_at",
            ]
        )
        core_audit.money_action(
            actor,
            AUDIT_VOIDED,
            "refund",
            str(refund.pk),
            after={
                "voided_at": voided_at.isoformat(),
                "void_reason": void_reason,
                "amount": str(refund.amount),
                "reversing_entry_id": posting.entry_id,
                "job": None if actor is not None else "payments.refund",
            },
        )
    return _result(refund, created=False, posting=posting)


# ══════════════════════════════════════════════════════════════════════════
# CR-141-BRC07 — A MISTYPED CHECK NUMBER, CORRECTED (OQ-PAY-12614)
# ══════════════════════════════════════════════════════════════════════════
#
# PO, verbatim, 2026-09-23: *"One thing needs your sign-off, because it is a
# money record: (b) Allow a correction, the same way you allowed it for payments
# on 2 September"*. What was SHOWN, and so all the signature covers: *Dana sends
# a refund of $91.60 by check #10241 but types #10214; as built it can never be
# changed.* It reverses the *"write-once rather than amendable"* judgment
# `payments/0041`'s review-ledger row named as unsigned — for the check number
# ONLY, and only through the function below.
#
# ⚠ **THE PAYMENT RULE IT MIRRORS IS WIDER, AND THE WIDER HALF IS NOT SIGNED
# HERE.** `amendments.amend_reference` corrects a payment's cheque number, memo
# AND tender. For a refund only the check number was put to the PO, so the memo
# and the method are refused BY NAME below with everything else — a refund's
# money has already left by the method it left by.

#: The correction window `payments/0043`'s trigger reads. Named once here and
#: once in that migration so the fence and the one lawful way through it are
#: greppable from each other — `ledger/0004` and `posting.WRITE_WINDOW_GUC`'s
#: shape. Its VALUE is the refund's id, so it opens one row and not the table.
CORRECTION_WINDOW_GUC = "app.refund_reference_correction"
CORRECTION_WINDOW_SHUT = ""

#: The question that authorises this write, CLOSED 2026-09-23 (option b).
OQ_REFUND_REFERENCE_CORRECTION = "OQ-PAY-12614"

#: What the body may carry: the new number, and the reason. Nothing else.
CORRECTABLE_FIELDS = ("reference",)

#: Refused BY NAME, before anything is read — the payment path's first proof
#: (`amendments.refuse_money_fields`), carried over. The list names what a
#: caller might plausibly send; ANY other key is refused as unknown below, so
#: this list is for the quality of the sentence, not the safety of the door.
#: ⚠ `memo` and `tender_id` are here although the PAYMENT door accepts them:
#: they were not shown to the PO for a refund and are not signed.
NOT_CORRECTABLE_ON_A_REFUND = (
    "amount",
    "currency",
    "account_id",
    "account",
    "payment_id",
    "method",
    "tender_id",
    "memo",
    "reason",
    "status",
    "requested_at",
    "approved_at",
    "issued_at",
    "cleared_at",
    "voided_at",
    "void_reason",
    "journal_entry_id",
    "void_journal_entry_id",
    "idempotency_key",
)


def _set_correction_window(value: str) -> None:
    """Open (the refund's id) or shut (`""`) the correction window — `payments/0043`.

    `set_config(…, true)` is TRANSACTION-LOCAL, so a crash, a rollback or a
    rollback-to-savepoint closes it whatever else happens. On a database without
    the trigger (the SQLite developer database) this is a no-op: the guarantee
    is PostgreSQL's and is not simulated where it does not exist — the checks in
    `correct_refund_reference` are what hold the same law there.
    """
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT set_config(%s, %s, true)", [CORRECTION_WINDOW_GUC, value])


def _refuse_other_fields(body: dict[str, Any]) -> None:
    """Every field but the check number and the note, refused BY NAME, FIRST.

    A body carrying an amount is told about the amount before anything else runs
    — the payment door's order, kept. An unknown key is refused too: silently
    dropping one is how a clerk comes to believe a correction landed.
    """
    offenders = [name for name in NOT_CORRECTABLE_ON_A_REFUND if name in body]
    if offenders:
        raise PaymentRuleError(
            f"a refund's {', '.join(offenders)} cannot be corrected here. Only the check "
            "number can: that is what the Product Owner signed (OQ-PAY-12614). The amount, "
            "the account and the method are money that has already left; a wrong amount is "
            "voided and raised again (US-PAY-011 TC-4), never edited.",
            br_ref="BR-PAY-014",
        )
    unknown = sorted(
        name for name in body if name not in CORRECTABLE_FIELDS and name not in ("note",)
    )
    if unknown:
        raise PaymentRuleError(
            f"this correction does not accept {', '.join(unknown)}. It takes the new check "
            "number and a note saying why — nothing else, so what can be corrected is "
            "visible in the route rather than hidden inside it.",
            br_ref="BR-PAY-014",
        )


@permissions.require_role(
    permissions.SYSTEM_ADMIN, permissions.BILLING_CLERK, br_ref="BR-PAY-1071"
)
def correct_refund_reference(
    actor: Any,
    *,
    refund_id: Any,
    reference: str | None,
    note: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """`POST /refunds/{id}/correct-reference` — a mistyped check number, replaced.

    The refund's twin of `amendments.amend_reference`, narrowed to the one
    column the PO was shown. **Every refusal runs before the write, in this
    order**, and each is also a refusal the database makes on PostgreSQL
    (`payments/0043`) — SQLite has no triggers (hard-won law 14), so this is
    what holds the law on the developer database:

      1. **any other field**, by name (`_refuse_other_fields`);
      2. **a blank note** — the number is what bank reconciliation matches the
         outgoing check on (BR-PAY-021), so changing it changes which bank line
         the refund ties to, and a month later nobody remembers why it moved;
      3. **a blank replacement** — a correction REPLACES a number and never
         erases one; US-PAY-011 §5 makes it required for a check at issue;
      4. **a refund with no check number yet** — the first number is the ISSUE
         act's (`issue_refund`), which tests the credit, posts the money and
         audits the payout. This door is not a second way to write it;
      5. **a voided refund** — `payments/0006`'s VOID guard is untouched and
         nothing about a voided check was put to the PO;
      6. **the same number again** — an audit row saying a number was
         corrected to itself is noise in the one place the old number lives.

    ⚠ **ADMIN OR BILLING CLERK — WHO WRITES THE CHECK, CORRECTS ITS NUMBER.**
    `BR-PAY-1071` as amended 2026-09-03 (*"q6 yes Clark can issue refund"*) puts
    issuing with Admin or Billing Clerk, and this is the same clerk fixing their
    own keying — the payment door's argument (*"the clerk who records a
    payment"*), run on the outbound side. An Executive may mark a refund cleared
    and may not issue one, so may not rewrite what was issued either. Gated
    HERE, in the service, so a job or a second door cannot reach it ungated
    (BR-SHL-025); the route mirrors it.

    ⚠ **THE UPDATE, THE WINDOW AND THE AUDIT ROW ARE ONE TRANSACTION.** The
    window opens only for this refund, only for this statement, and is shut
    again before the function returns — so a later statement in the same request
    cannot ride it. The audit row is written in the same transaction because the
    replaced number now lives ONLY there (hard rule 7), and a corrected row
    without its audit row must not be reachable.

    ⚠ **AND THAT AUDIT ROW IS NOT A PERMANENT RECORD.** `audit_log` has one
    retention rule and no row type is exempt (`OQ-1340`, CLOSED 2026-09-23: *"when
    audit log is delete - it is deleted thats okay"*). The response carries the
    payment path's own machine fact, `amendment_history_is_not_a_permanent_record`,
    for a caller to reason about; it is never copy for a screen (B14 rule 33 puts
    rationale at zero words on screen).
    """
    body = dict(body or {})
    _refuse_other_fields(body)

    if not (note or "").strip():
        raise PaymentRuleError(
            "a correction needs a note saying why. The check number is what bank "
            "reconciliation matches the outgoing check on, so changing it changes which bank "
            "line this refund ties to — and a month later nobody remembers why it moved.",
            br_ref="BR-PAY-014",
        )
    new_number = (reference or "").strip()
    if not new_number:
        raise PaymentRuleError(
            "give the new check number. A correction replaces a check number with the right "
            "one; it never erases it (US-PAY-011 §5: required for check).",
            br_ref="BR-PAY-014",
        )

    refund = _refund(_tenant_id(), refund_id)
    if refund.status == models.REFUND_VOID:
        raise PaymentRuleError(
            "this refund was cancelled, and a cancelled refund is closed: its credit was put "
            "back by a reversing entry. Nothing on it can be corrected; paying it again is a "
            "new refund.",
            br_ref="BR-PAY-014",
        )
    current = (refund.reference or "").strip()
    if not current:
        raise PaymentRuleError(
            "this refund has no check number yet, so there is nothing to correct. The number "
            "is recorded when the refund is issued, which is the act that writes the check "
            f"({OQ_REFUND_REFERENCE_CORRECTION}).",
            br_ref="BR-PAY-014",
        )
    if new_number == current:
        raise PaymentRuleError(
            f"#{current} is already this refund's check number, so nothing would change. "
            "Type the number printed on the check.",
            br_ref="BR-PAY-014",
        )

    # Composed BEFORE the write, because `before` is read off the row as it
    # stands — composing it afterwards would record the new number twice.
    before = {"reference": refund.reference}
    after = {"reference": new_number, "note": note}
    refund.reference = new_number

    with transaction.atomic():
        _set_correction_window(str(refund.pk))
        try:
            # `update_fields` names exactly the two columns the window allows —
            # `updated_at` rides along so the model's `auto_now` stamps it without
            # this money path reading a clock (BR-TEN-043).
            refund.save(update_fields=["reference", "updated_at"])
        finally:
            # Shut on the way out, even through an exception. On an aborted
            # transaction this statement cannot run — and need not, because the
            # rollback discards the setting with everything else — so a failure
            # here is swallowed rather than allowed to mask the real error
            # (`posting.post`'s own pattern, and hard-won law 14's reason).
            try:
                _set_correction_window(CORRECTION_WINDOW_SHUT)
            except Exception:  # noqa: BLE001 — never masks the refusal a caller is owed
                pass
        core_audit.money_action(
            actor,
            AUDIT_REFERENCE_CORRECTED,
            "refund",
            str(refund.pk),
            before=before,
            after=after,
        )

    return {
        # The refund's own row, read back, so the screen shows what is STORED and
        # not what it sent. The id rides for navigation, never as a shown value.
        "refund_id": str(refund.pk),
        "refund": selectors.refund_detail(refund.pk),
        "corrected": {"reference": new_number},
        "previous": dict(before),
        "note": note,
        # The payment path's machine fact, with its own code so a caller has one
        # vocabulary for both directions of money — and this door's question
        # named beside `OQ-1340`. Never a string to render (B14 rule 33).
        "unavailable": [
            {
                **_amendments_retention_gap(),
                "br_ref": f"OQ-1340 · {OQ_REFUND_REFERENCE_CORRECTION}",
            }
        ],
    }


def _amendments_retention_gap() -> dict[str, Any]:
    """`amendments.AMENDMENT_RETENTION_GAP`, one definition for both doors.

    Imported at call time rather than at module load: `amendments` is a sibling
    in this module, and one sentence about retention written twice is two
    sentences that can drift apart — the first to be reworded would be the one
    that stopped being true.
    """
    from apps.payments.amendments import AMENDMENT_RETENTION_GAP

    return dict(AMENDMENT_RETENTION_GAP)


def _refund(tenant_id: Any, refund_id: Any) -> models.Refund:
    try:
        row = models.Refund.objects.filter(tenant_id=tenant_id, pk=refund_id).first()
    except (ValueError, TypeError):
        row = None
    if row is None:
        raise PaymentRuleError(
            f"refund {refund_id!r} is not one of this tenant's refunds (CLAUDE.md rule 1). "
            "Nothing is written.",
            br_ref="BR-PAY-014",
        )
    return row


def _duplicate_problem(refund: models.Refund) -> tuple[dict[str, Any], ...]:
    return (
        {
            "code": "duplicate_refund_request_ignored",
            "br_ref": "BR-PAY-028",
            "detail": f"a refund was already requested under this submit token as "
            f"{refund.reference or refund.pk}. Nothing was written: one request, one approval "
            "to give, one cheque.",
        },
    )


def _result(
    refund: models.Refund,
    *,
    created: bool,
    credit: Decimal | None = None,
    posting: Any = None,
    extra: tuple[dict[str, Any], ...] = (),
) -> RefundResult:
    return RefundResult(
        refund_id=str(refund.pk),
        status=refund.status,
        created=created,
        amount=refund.amount,
        currency=refund.currency,
        # NULL on a refund raised against a CREDIT BALANCE built from several
        # payments — CR-059 CS-7, the PO's ruling of 2026-09-01. `account_id`
        # below is the one that is always there.
        payment_id=None if refund.payment_id is None else str(refund.payment_id),
        account_id=str(refund.account_id),
        credit_position_after=(
            credit if credit is not None else selectors.account_credit_position(refund.account_id)
        ),
        journal_entry_id=None if posting is None else posting.entry_id,
        posting_key=None if posting is None else posting.posting_key,
        problems=REFUND_UNAVAILABLE + extra,
    )


# ══ CR-068 · `CWP-045` — WHERE THE MONEY IS GOING BACK TO (US-CWP-049) ═════
#
# `BR-CWP-060`, CONFIRMED: *"A refund returns to the method the money came in
# on, and the timeline names it."*
#
# ⚠ **AND TODAY IT CANNOT, FOR A CARD, AND SAYING OTHERWISE WOULD BE A LIE ON A
# CUSTOMER'S SCREEN.** `US-CWP-049` TC-1 draws *"Sent · 21 Sep · to the card
# ending 8812"*. `BR-PAY-014` puts card refunds behind the payment rails (W7),
# `REFUND_METHODS` is `("check", "ach")` and `ck_refunds_method` enforces it in
# the database — so money that came in by card goes back out **by cheque or
# ACH**, whatever the drawn copy says. Printing the drawn sentence over a cheque
# in the post is hard-won law 1 pointed at a customer.
#
# **So the screen is given the same fact told truthfully**, which is the shape
# TC-3 already asks for in the expired-card case (*"falls back to a cheque and
# the timeline says so — never silently to a dead card"*): name where the money
# CAME IN, name where it is GOING, and when those differ say WHY. What this lane
# found is that today it is the only shape available — the fallback is signed
# behaviour rather than an invention, and TC-1's exact sentence returns the day
# `REFUND_METHODS` can hold a card.
#
# ⚠ **NOTHING HERE READS AN ADDRESS.** A cheque goes where the post goes, and
# that is `customers.addresses kind='mailing'` (CLAUDE.md hard rule 8's first
# exception). `payments` does not own it; `apps/portal/seams/payments_seam.py`
# attaches it to the row on the way to the screen.

#: The two shapes an answer can take. `original` is `BR-CWP-060` met; `fallback`
#: is `BR-CWP-060` unmet WITH ITS REASON, which TC-3 and TC-4 both require and
#: which a bare *"sent"* would not be.
DESTINATION_ORIGINAL = "original_method"
DESTINATION_FALLBACK = "fallback"

#: Why the money is not going back the way it came. ⚠ **ORDER MATTERS BELOW** —
#: a dead card is reported ahead of absent rails, because it is the reason still
#: true the day rails land.
FALLBACK_CARD_EXPIRED = "card_expired"
FALLBACK_CARD_RAILS_ABSENT = "card_rails_absent"
FALLBACK_SEVERAL_SOURCES = "several_sources"
FALLBACK_SOURCE_UNKNOWN = "source_unknown"


def _tender_code(payment: Any) -> str | None:
    """The tenant's own code for how the money came in, or None.

    `Payment.method` is `tenancy.PaymentMethod` — the seeded tender vocabulary
    (`ach · card · check · cash · lockbox · wire · money_order`) since `OQ-031`
    closed the enum. NULL is lawful: a credit or an adjustment row carries no
    instrument, and that is *unknown*, not *cash*.
    """
    method = getattr(payment, "method", None)
    return getattr(method, "code", None) if method is not None else None


def _saved_card(refund: Any) -> Any:
    """The card this customer saved, when there is exactly ONE to name.

    ⚠ **`Payment` HAS NO LINK TO A STORED INSTRUMENT**, so *"the card ending
    8812"* cannot be read off the payment: the only place a brand and four
    digits live is `stored_payment_instruments`, which hangs off the CUSTOMER
    (`03-field-map.md` §payments) rather than off the payment or the account.
    **So a card is named only when the customer has exactly one**, and where
    they have two the screen says a card without naming which — guessing which
    of two cards a payment came from is a digit on a customer's screen that
    nobody can vouch for.

    ⚠ **AND `accounts` HAS NO CUSTOMER COLUMN EITHER** — `BR-CUS-054` makes the
    link a table (`customer_accounts`), because a landlord holds many accounts
    and an account can change hands. So the walk goes through customers' own
    published `customer_for_account`, and a `None` from it is a REAL answer
    (*"every account created before the BR-CUS-054 entity existed has no
    link"*), not a gap to route around.
    """
    account = getattr(refund, "account", None)
    if account is None:
        return None
    customer_of = _resolve("customers", "customer_for_account")
    if customer_of is None:  # pragma: no cover - customers publishes it
        return None
    customer = customer_of(account.pk)
    customer_id = customer.get("id") if customer else None
    if customer_id is None:
        return None
    rows = list(
        models.StoredPaymentInstrument.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            customer_id=customer_id,
            kind=models.INSTRUMENT_CARD,
            deleted_at__isnull=True,
        ).order_by("created_at", "id")[:2]
    )
    return rows[0] if len(rows) == 1 else None


def destination_of(refund: Any) -> dict[str, Any]:
    """`CWP-045`'s refund line — where it came in, where it is going, and why.

    Worked, `US-CWP-049` §4: a **$89.80** refund of a **card** overpayment on an
    account holding one saved `Visa ••••8812` answers `came_in_by: "card"`,
    `brand: "Visa"`, `last_four: "8812"`, `method: "check"`, `reference:
    "10241"` and `kind: "fallback"` with `fallback_reason:
    "card_rails_absent"` — so the screen reads *the money came in on the card
    ending 8812; we have sent cheque 10241 instead, because we cannot return
    money to a card yet*. The same refund of a **cheque** overpayment answers
    `kind: "original_method"` and NO fallback reason.

    ⚠ **A REFUND WITH NO SOURCE PAYMENT IS `several_sources`, NOT `unknown`**
    (TC-4). Since `OQ-195` (PO 2026-09-01) `payment_id` is nullable precisely
    because the credit came from more than one payment — so its absence is a
    FACT about the credit, not a missing join, and the screen names the rule
    that chose one method rather than printing a bare *sent*.

    ⚠ **AND A DEAD CARD OUTRANKS ABSENT RAILS** (TC-3). Both are true of an
    expired card and only one of them is still true after W7; the customer is
    given the reason that will not evaporate.
    """
    payment = getattr(refund, "payment", None)
    came_in_by = _tender_code(payment) if payment is not None else None
    method = getattr(refund, "method", None)
    answer: dict[str, Any] = {
        "kind": DESTINATION_ORIGINAL,
        "method": method,
        "reference": getattr(refund, "reference", None),
        "came_in_by": came_in_by,
        "brand": None,
        "last_four": None,
        "fallback_reason": None,
    }

    if came_in_by == models.INSTRUMENT_CARD:
        card = _saved_card(refund)
        if card is not None:
            answer["brand"] = card.brand
            answer["last_four"] = card.last_four
        expired = card is not None and card.status == models.INSTRUMENT_EXPIRED
        answer["kind"] = DESTINATION_FALLBACK
        answer["fallback_reason"] = FALLBACK_CARD_EXPIRED if expired else FALLBACK_CARD_RAILS_ABSENT
        return answer

    if payment is None:
        answer["kind"] = DESTINATION_FALLBACK
        answer["fallback_reason"] = FALLBACK_SEVERAL_SOURCES
        return answer

    if came_in_by is None:
        #: The money arrived on a row carrying no instrument — a credit or an
        #: adjustment. *Unknown* is not *cash*, and the screen says so.
        answer["kind"] = DESTINATION_FALLBACK
        answer["fallback_reason"] = FALLBACK_SOURCE_UNKNOWN
        return answer

    if method is not None and came_in_by != method:
        #: Cash in, cheque out — lawful, and still not *the way it came*.
        answer["kind"] = DESTINATION_FALLBACK
        answer["fallback_reason"] = FALLBACK_SOURCE_UNKNOWN
    return answer


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-011@f4d2b18 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 refunds DDL + Addenda r2/r12 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-03-exceptions.md US-PAY-011 · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/07-pre-session-model.md §6 PE-9 · 08-qa/01-e2e/journeys/J15-overpay-refund.md · 12-governance/02-decision-log.md 2026-08-11 OQ-132 closure)
# generated: 2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03)
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — S58 has no server; the modal is unbuilt) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_us_pay_011_refunds.py · PROVED RED BEFORE GREEN, each mutated, RUN and quoted verbatim in the lane report: (1) the credit test floored at zero, so a NEGATIVE position funds a refund · (2) the credit checked only at request, so an approval outlives the credit a bounce pulled back · (3) the void DELETING the row instead of writing a reversing posting · (4) the Admin role guard removed
# exceptions: (1) OQ-135 IS OPEN — refunding a customer who owes on ANOTHER
#         account. `cross_account_check=True` raises `NotImplementedError`; the
#         default performs NO cross-account check and says so on every result,
#         because half of an unruled check is worse than none
#         (2) OQ-167, RAISED BY THIS LANE — B2 types `refunds.payment_id` NOT
#         NULL, so a credit accumulated from TWO overpayments has no home. The
#         single-source case (PE-9's own shape) is served; the multi-source case
#         is refused by name
#         (3) NO RECEIPT IS QUEUED (BR-PAY-024 / BR-NOT-005, US-PAY-025 owns it)
#         and `accounts.balance` IS NOT UPDATED — both ride every result
#         (4) CARD REFUNDS ARE NOT A VALUE THE COLUMN CAN HOLD (BR-PAY-014, W7
#         rails) — refused at the door, not behind a branch that could be flipped
#         (5) THE FINAL-BILL HANDOFF (US-PAY-011 TC-2, US-BIL-011's $11.20) is
#         not wired: billing publishes no call into this module and this lane
#         does not edit billing. `request_refund` is the function it will call
#         (6) THE CREDIT TEST RUNS TWICE — at request and again at issue. A
#         single check would let an approval outlive the credit it approved
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

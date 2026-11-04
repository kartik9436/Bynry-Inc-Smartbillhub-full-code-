# ── Trace ──────────────────────────────────────────────
# Change:   CR-094-BRC01 lane H — the PO ruling of 2026-09-15: *"payemnt should
#           show in payments, in ledge and in fiannce books"*.
# Story:    US-LED-001   Screens: capture step 5 · the request detail
# Rules:    CLAUDE.md hard rule 5 (ONLY the ledger posting service writes
#           journal lines; customers calls a seam and writes no journal line
#           itself) · B1/B8 (customers NEVER touches another module's ORM) ·
#           B2 §2 (cross-module writes are forbidden; the interface is the
#           reviewed set) · hard rule 7 (every money act audits — payments
#           writes the row, because payments owns the act)
# Tests:    06-backend/tests/test_cr094_counter_receipt_posts.py
# Impacts:  apps/customers/service_request_service.py (`collect_fee`, `approve`,
#           `refuse_request` — its only callers) ·
#           apps/payments/counter_receipts.py (the implementation on the far
#           side, resolved BY NAME)
# ───────────────────────────────────────────────────────
"""customers → payments SEAM: **the counter takings door** — and, since
`DEF-PAY-6342` (2026-09-23), the returned-post door beside it.

⚠ **THIS LINE READ *"the counter takings door, and the only one"* UNTIL
2026-09-23.** `resolve_open_returns` below is the second: when a customer
corrects their own address in the portal (`BR-CWP-086`), customers lowers its
own `accounts.bad_address` and asks payments to close the account's open
returned-post rows, which are payments' table. Same shape, same rule — each
module writes its own rows — and it is here rather than in a new file because
this file's own reason for existing is *"one pattern for cross-module access,
not three"*.

B1/B8: customers never touches another module's ORM. Everything it needs from
payments is one of the callables below, resolved AT CALL TIME from
`apps.payments.counter_receipts`. Same shape as `apps/customers/seams.py` and
`notifications_seam.py`, deliberately — one pattern for cross-module access,
not three.

╔══════════════════════════════════════════════════════════════════════════╗
║  CUSTOMERS WRITES NO PAYMENT ROW, NO JOURNAL LINE AND NO LEDGER ENTRY.   ║
║  IT SAYS WHAT HAPPENED AT THE DESK AND PAYMENTS DECIDES WHAT THAT MEANS  ║
║  IN THE BOOKS.                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝

────────────────────────────────────────────────────────────────────────────
WHY THE FEE LINES CROSS THE SEAM AND THE GL ACCOUNT DOES NOT
────────────────────────────────────────────────────────────────────────────
`release_counter_receipt` is handed the QUOTE — the unwaived fee lines with
their charge codes and amounts — and never a ledger account. Which account a
charge code earns into is `rating.charges.gl_account_id`, the tenant's own
mapping (BR-BIL-010), and payments reads it through rating's published read.
Customers picking one would be a third module with an opinion about where money
goes, and the first time a tenant re-pointed a code the two would disagree
silently.

────────────────────────────────────────────────────────────────────────────
WHAT A `None` FROM THIS SEAM MEANS, IN EACH DIRECTION
────────────────────────────────────────────────────────────────────────────
`_resolve` answering None means payments has not published the callable — a
deployment mid-upgrade, or a test importing customers alone. The documented
fallback is the SAME in every function here: **the request's own columns still
record what the clerk did, and nothing posts.** That is exactly the behaviour
this product had until 2026-09-15, so a seam that cannot reach payments degrades
to the old world rather than to a broken one — and `collect_fee` reports it
through the caller's return value rather than swallowing it, so a lane can see
the difference between *not posted* and *posted*.

⚠ **IT DOES NOT SWALLOW A REFUSAL FROM THE FAR SIDE.** A `PaymentRuleError` on
COLLECTION is raised to the clerk: money that cannot be recorded must not be
taken. A refusal on RELEASE is caught by payments itself and recorded on the
receipt, so approving or refusing an application is never blocked by a chart
gap — a clerk stuck at a counter with a person in front of them is the worse
failure. The asymmetry is deliberate and is stated here because it is the kind
of thing a reader would otherwise assume was an oversight.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

PAYMENTS_MODULE = "payments"
COUNTER_RECEIPTS = "counter_receipts"

#: The counter surface this module owns. `apps.payments.counter_receipt_models.
#: SOURCE_SERVICE_REQUEST`, named here so the contract is greppable from BOTH
#: sides of the boundary — the same reason `ledger_seam.GL_DESIGNATION_READ` is
#: a constant rather than a string literal at a call site.
SOURCE_SERVICE_REQUEST = "service_request"


def _counter_receipts() -> Any:
    """`apps.payments.counter_receipts`, or None while payments has not shipped it."""
    try:
        return import_module(f"apps.{PAYMENTS_MODULE}.{COUNTER_RECEIPTS}")
    except ImportError:  # pragma: no cover - defensive
        return None


def payments_can_answer() -> bool:
    """Whether the far side is there. Published so a caller can SAY so.

    Hard-won law 1: a comment claiming a guarantee is not the guarantee. A
    caller that silently took the fallback would look identical to one that
    posted, which is how *"this takes money and posts nothing"* survived a year
    on a screen.
    """
    return _counter_receipts() is not None


def record_counter_receipt(**kwargs: Any) -> dict[str, Any] | None:
    """The counter took money. Payments records it and posts the collection.

    Keyword contract, and it is the PUBLISHED shape a sibling lane builds to:

        source_type      "service_request"
        source_id        the request's uuid
        source_ref       "SR-26-0048" — what a clerk says out loud
        receipt_no       "RCP-26-4471" — the number on the slip
        amount           Decimal, four places. NEVER a float
        currency         CHAR(3)
        method_code      "cash" | "card" | "cheque" (payments maps cheque→check)
        taken_at         a datetime named by the caller (BR-TEN-043)
        taken_by_id      the clerk
        card             {"last4", "brand", "auth_code"}   or None
        cheque           {"number", "bank", "date"}        or None
        posted_on        the business day it counts for — a `date`, the
                         TENANT's day (BR-TEN-081); the ledger entry's date
        confirmation     the instrument's own number, or None
        memo             free text, or None

    Returns the receipt as a dict, or **None** when payments is not there.
    Raises the far side's refusal unchanged — money that cannot be recorded must
    not be taken.
    """
    module = _counter_receipts()
    if module is None:  # pragma: no cover - defensive
        return None
    return module.record_counter_receipt(**kwargs)


def till_refusal(actor: Any, method_code: str | None) -> str | None:
    """**The till rule for money a clerk keys at this door — `DEF-CUS-6374`.**

    PO ruling 2026-09-23 §3.4: cash, checks and money orders are refused until
    the person recording them has a till open (*"(a) Refuse it. \"Start your
    counter first.\""*). Payments owns the rule and its one implementation;
    this returns its SENTENCE when it refuses and None when it does not, so
    customers raises its own catalogue refusal and never imports a payments
    exception. The request's `cheque` is the tender `check` on the far side.

    ⚠ **CALLED AT THE ENDPOINT, NOT IN `collect_fee`** — `P2.23`'s reason: the
    sample data seeds a counter collection for a utility with no clerks.

    None when payments is not there — the file's stated degradation (the old
    world, where nothing posted and no till existed to be refused against).
    """
    module = _counter_receipts()
    if module is None:  # pragma: no cover - defensive
        return None
    return module.till_refusal(actor, method_code)


def is_live_tender(method_code: str | None) -> bool:
    """Whether `method_code` is one of this tenant's active payment methods.

    **`DEF-CUS-6376`.** The fee modal offers the tenant's served list — the one
    Record a payment offers — so `money_order` or a method the tenant added is
    a lawful answer here. Which codes exist is payments' fact (BR-PAY-026), so
    customers asks rather than keeping a list. False when payments is not there,
    which leaves the request's own three as the only accepted answers.
    """
    module = _counter_receipts()
    if module is None:  # pragma: no cover - defensive
        return False
    return bool(module.is_live_tender(method_code))


def release_counter_receipt(**kwargs: Any) -> dict[str, Any] | None:
    """A TERMINAL outcome earns the fee. Approval and refusal, identically.

        source_type      "service_request"
        source_id        the request's uuid
        outcome          "approved" | "refused" | "paid_online" (a portal fee
                         paid by card at submission, `CR-191-BRC10`) — and
                         nothing else. Ask for more is not a terminal outcome
                         and posts NOTHING
        fee_lines        [{"charge_code", "charge_code_id", "amount"}] for every
                         UNWAIVED line, in line order
        released_at      a datetime named by the caller
        released_by_id   the clerk

    Returns the receipt as a dict, or **None** when no money was taken at the
    counter (the ordinary case) or when payments is not there.
    """
    module = _counter_receipts()
    if module is None:  # pragma: no cover - defensive
        return None
    return module.release_counter_receipt(**kwargs)


def counter_receipt_for_request(request_id: Any) -> dict[str, Any] | None:
    """What payments holds against this request, or None. A pure READ.

    Published so the request's own screens can show the tender detail the
    counter captured — the card's last four and its authorisation code, the
    cheque's number, bank and date — without customers holding a second copy of
    facts payments owns.
    """
    module = _counter_receipts()
    if module is None:  # pragma: no cover - defensive
        return None
    return module.receipt_dict(module.receipt_for_source(SOURCE_SERVICE_REQUEST, request_id))


RETURNED_MAIL = "returned_mail"
#: `BR-CWP-086`'s other half, named once so both sides can grep it.
RETURNS_RESOLVE = "resolve_open_returns"
#: The returned-post writer itself — the demo seed marks a piece returned
#: through it rather than stamping `accounts.bad_address` (`DEF-PAY-6342`).
RETURN_MARK = "mark_returned"


def mark_returned(**kwargs: Any) -> Any:
    """Mark one piece of post returned, through payments' own writer.

    Published for `sample_account_flags` and nothing else: a seed must reach a
    flag the way a clerk does, so the demo carries an event, its audit row and
    the flag together — or none of them. None while payments has not published
    it, and the seed then leaves the account unflagged and says so.
    """
    try:
        module = import_module(f"apps.{PAYMENTS_MODULE}.{RETURNED_MAIL}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(module, RETURN_MARK, None)
    return fn(**kwargs) if callable(fn) else None


def resolve_open_returns(**kwargs: Any) -> tuple[Any, ...] | None:
    """Close every open returned-post row on one account (`DEF-PAY-6342`).

    Payments' table, so payments' function — resolved BY NAME. None while
    payments has not published it; the caller has already lowered the flag it
    owns, and an unresolved return then waits on the needs-attention list,
    which is visible, rather than being closed by a module that does not own it.
    """
    try:
        module = import_module(f"apps.{PAYMENTS_MODULE}.{RETURNED_MAIL}")
    except ImportError:  # pragma: no cover - defensive
        return None
    fn = getattr(module, RETURNS_RESOLVE, None)
    return fn(**kwargs) if callable(fn) else None


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-094-BRC01 lane H (the PO ruling of 2026-09-15 · hard rule 5 ·
#         B1/B8 · B2 §2)
# generated: 2026-09-15 by the CR-094-BRC01 counter-fee lane
# checklist: A✔ B✔ C✔ D✔ E=n/a(no UI) F✔ G✔ H=pending(🔒 money path)
# gates: ruff✔ black✔ · pytest tests/test_cr094_counter_receipt_posts.py
# exceptions: none
# status: HUMAN-REVIEW-PENDING
# ──────────────────────────────────────────────────────────

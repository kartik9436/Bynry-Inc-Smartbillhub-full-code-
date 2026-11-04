# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-001 (single payment entry — TC-1 the PE-1 check, TC-5 the
#           negative amounts, TC-6 the double submit + the frozen row, TC-7
#           isolation) · US-PAY-006 (allocation — the `allocations` rows, the
#           oldest-first walk, the carried credit)
#           Screens: S22 · S32 · S33 · S35
# Rules:    BR-PAY-001 (default = oldest open bill; staff options specific /
#           carry credit / split) · BR-PAY-002 (append-only; a correction is a
#           new row) · BR-PAY-010 (allocation order, tenant-configurable) ·
#           BR-PAY-012 (purpose; unapplied → account credit) · BR-PAY-021
#           (posting date ≠ clearing date, always both) · BR-PAY-022 (the
#           single-entry field set) · BR-PAY-026 (method is a tenant lookup) ·
#           BR-PAY-028 (idempotency) · BR-PAY-033 (the posting date is
#           USER-ENTERED, never the system timestamp) · BR-PAY-036 (a payment
#           is ALWAYS accepted, in every account status) · BR-PAY-038 (the
#           fourth allocation class) · BR-TEN-035 (the PMT- series) ·
#           BR-TEN-042 (currency lock) · BR-TEN-043 (event time is an input) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (money) · rule 4
#           (immutability) · rule 5 (only the ledger posts) · rule 6
#           (idempotency) · rule 7 (every money action writes audit_log)
# Golden:   GT-7 — B5 ❄️ FROZEN 2026-08-08 (the allocation figure this write
#           path calls; the calculation itself is allocation.py's)
# Change:   CR-059 CS-23 (2026-09-01) — `record_payment` now meets the account's
#           next payment-plan instalment inside its own transaction. Until then
#           NOTHING linked a payment to an instalment on the running product, so
#           every plan read as behind, the BR-CUS-043 pause never applied, and a
#           customer paying on time was chased.
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py ·
#           06-backend/tests/golden/test_gt07_partial_allocation.py ·
#           06-backend/tests/test_us_pay_006_allocation.py ·
#           06-backend/tests/test_cr059_cs23_installment_link.py
# Impacts:  apps/billing/rating_seam.py (`allocate_payment` resolves here) ·
#           apps/tenancy/seams.py (payment_method_used_by_count +
#           financial_records_exist resolve here — both were documented seams
#           that payments had never authored) · apps/ledger/posting (reached
#           through ledger_seam) · apps/payments/billing_seam (the open bills)
# ───────────────────────────────────────────────────────
"""payments service layer — the ONLY write path into this module's tables (B1).
Other modules call these functions; they never touch this module's ORM directly.

HUMAN-OWNED (CLAUDE.md 🔒 — this file holds the hard-rule-6 idempotency
enforcement for inbound money, the payment write itself, and the call that puts
it in the books). HUMAN-REVIEW-PENDING — AI-authored 2026-08-11 under the PO
ruling of 2026-08-09; row in 12-governance/09-human-review-ledger.md.

⚠ THE MARKER WAS ADDED LATE, AND DEF-058 IS WHY IT MATTERS. This file shipped
without it, so G7 never checked it — and the guard list is what makes a 🔒 file's
review real. In that window a red-proof mutation (`already = None  # RED PROOF —
pre-insert lookup removed`) was COMMITTED in the disabled state, switching off a
hard rule 6 guard on live money. Nothing went red: the database UNIQUE index
covers the same OUTCOME, so all 19 tests passed while the test's own docstring
claimed both guards were asserted. A second guard that silently substitutes for
the first is how the first stops being checked.

Until 2026-08-11 this file held no write path at all, because this module owned
no tables: `apps/payments/models.py` was three lines and `allocation.py` was
1,124 lines of tested arithmetic **with nothing to allocate**. `record_payment`
below is the first code in the product through which a customer's money can
reach a bill and then the books.

════════════════════════════════════════════════════════════════════════════
WHAT `record_payment` IS, AND THE FIVE THINGS IT DOES IN ONE TRANSACTION
════════════════════════════════════════════════════════════════════════════
One service function = one transaction boundary (B1). All of it commits or none
of it does, and the ordering is not incidental:

  1. **the `payments` row** — with BOTH BR-PAY-021 dates and a PMT- number
     allocated from the tenant series inside this transaction (BR-TEN-035);
  2. **`audit_log` `payment.recorded`** — same transaction, hard rule 7. The
     audit writer raises rather than losing a row, which takes the payment with
     it: money recorded with no trail is not a thing to let happen quietly;
  3. **the allocation** — `apps/payments/allocation.allocate_payment`, the pure
     GT-7 calculation, over the open bills `billing_seam` reports. Nothing here
     re-implements any part of it;
  4. **the `allocations` rows + `payment.allocated`** — one row per bill that
     received money, never one for a bill that did not;
  5. **the ledger posting** — `apps/ledger/posting.post` through `ledger_seam`,
     **DR undeposited funds / CR AR** (+ the carried credit), then the payment
     is stamped write-once with the entry id. **A payment that cannot post does
     not get recorded**: rolling back is the only outcome that keeps the books
     and the bank in step, and an immutable payment row with no journal entry
     has no repair path.

     **The debit is UNDEPOSITED FUNDS, not cash, since the PO's ruling of
     2026-08-11 closing OQ-143** — *"Cash is received but undeposted in such
     case payment will say csah but ledger will say undeposited - until bank
     record and reconcilaition confirm it it is not realised"*. The PAYMENT row
     still says cash was received, because that is what the clerk saw; the
     LEDGER says undeposited, because that is what the bank has confirmed, which
     is nothing yet. Reconciliation posts the second step (DR cash / CR
     undeposited) and belongs to the bank-rec lane.

Steps 3–5 happen only for a payment that has CLEARED. A payment recorded with
no clearing date is `processing` — the money has not arrived — and the ledger's
own contract row is *"Payment **cleared** → DR cash/undeposited · CR AR"*. The
result says so explicitly rather than leaving a caller to infer it.

════════════════════════════════════════════════════════════════════════════
WHAT IT REFUSES, AND WHAT IT DELIBERATELY DOES NOT
════════════════════════════════════════════════════════════════════════════
**IT NEVER REFUSES ON THE ACCOUNT'S STANDING.** BR-PAY-036, in the PO's own
words: *"payment is always accepted - even it is disconnected and tagged to
account"*. Nothing in this file reads `accounts.status`, and a test asserts that
absence — a closed, vacation-held or marked-for-disconnect account takes money
exactly like an active one, and acceptance never changes the account's status.

**ALL FOUR PURPOSES ARE NOW RECORDABLE (US-PAY-002, 2026-08-15).** Until this
date only `bill` had a write path and the other three were refused BY NAME —
each for a linkage that did not exist. `apps/payments/purposes.py` is the file
that resolves them and its docstring holds the detail; what changed, in one
line each:

  * `plan_down` — links to its plan through `payments.plan_id` (migration 0009,
    closing field-map P-12) and meets the arrears the plan spreads;
  * `prepay` — carries as account credit exactly as BR-PAY-010's default does
    with money no bill can absorb (US-PAY-007 owns the credit from there);
  * `deposit` — meets NO bill and becomes NO credit: it posts to the deposit
    LIABILITY and is held. ⚠ Its `problems` say what is still owed on the other
    side of the boundary — nothing calls the read that satisfies BR-BIL-012's
    first-bill deposit line, and the rate plan's deposit REQUIREMENT is
    unreadable, so the recording carries `deposit_requirement_not_checked`.

An OVERPAYMENT on a `bill` payment still carries credit (PE-4: open 292.87, pay
350.00 → credit 57.13) — that is not a fourth purpose, it is what BR-PAY-010
does with what no bill can absorb, and it posts to the customer-credit account.

════════════════════════════════════════════════════════════════════════════
WHAT THIS SLICE DOES NOT BUILD — NAMED SO SILENCE IS NOT READ AS "DONE"
════════════════════════════════════════════════════════════════════════════
This is the CLOSED-LOOP FOUNDATION and nothing more.

  * **reapply (BR-PAY-031) · write-offs (BR-PAY-020)** — EP-PAY-03. The schema
    supports both (a correction is a new row) and no service writes one.

**CORRECTED 2026-08-11 (hard-won law 1).** This list used to name NSF
(BR-PAY-013), reversal/void (BR-PAY-011) and refunds (BR-PAY-014) among the
things *"no service writes"*. Three services now do, and they are re-exported
from this module so B1's *"one write path per module"* still reads true from the
outside:

  * `apps/payments/reversal.reverse_payment` — a bounce. A NEW reversing
    `payments` row (PE-7's **−292.87**), reversing `allocations` rows that
    re-open the bills at their OWN due dates, and the LEDGER'S OWN MIRROR of the
    original entry. **It never edits the payment that bounced.**
  * `apps/payments/refunds` — `request_refund` → `approve_refund` →
    `issue_refund` → `clear_refund`, plus `void_refund`. Only the issue step
    moves money.

Each of those files states its OWN remaining gaps — the customer's NSF fee
(billing owns the line write and rating publishes no charge-code read),
`accounts.nsf_count` and the privilege flag (customers' table, no seam, no
column), and the collection ladder (OQ-133) — so one file owns each claim
instead of this docstring going stale about five of them at once.
  * **Collections and the notice ladder** — EP-PAY-04. ⚠ **THIS LINE SAID
    "and payment plans" UNTIL 2026-09-01 AND IT WAS WRONG TWICE OVER** (CR-059
    CS-23, hard-won law 1): the plan write path has been re-exported from this
    file since 2026-08-11, and since today `record_payment` also MEETS the
    account's next instalment. What is genuinely not here is the collection
    ladder's own engine (US-PAY-014).
  * **Budget billing · deposit batches · bank reconciliation** — EP-PAY-06.
  * **The staged bulk import** (US-PAY-003) and the **webhook intake**
    (rails, W7). The idempotency key shape is ready for both
    (`apps/payments/idempotency.py`); no parser and no dispatcher exists.
  * **The receipt** BR-PAY-024 auto-queues on every cleared payment — EP-PAY-07
    (US-PAY-025). It is a queue-write to `outbound_messages` and this path does
    not make it. `RECORD_UNAVAILABLE` says so on every result.
  * **The API endpoints and every screen.** S22/S32/S33/S34/S35 have no server
    here; this is the service the endpoints will call.
  * **`accounts.balance`.** It is customers' cached column and payments may not
    write another module's table (B1 / DB-16). The cache-update seam is in the
    reviewed interface set (B2 r16 #7) and customers publishes nothing to call,
    so the gap is REPORTED on the result rather than closed by reaching across
    the boundary. The LIVE position is derivable today — invoice totals minus
    this module's `allocations` rows — which is what `billing_seam` does.

════════════════════════════════════════════════════════════════════════════
TWO SEAMS THAT WERE DOCUMENTED, UNWIRED AND ARE NOW LIVE
════════════════════════════════════════════════════════════════════════════
`apps/tenancy/seams.py` has named `apps.payments.services.
payment_method_used_by_count` and `financial_records_exist` since W0, with a
fallback that answers 0 / False *"BY CONSTRUCTION: payments stores no payment
rows yet"*. That construction stopped being true the moment this module got
tables, and its own docstring states the consequence: while the count is 0,
**BR-TEN-030** (a code freezes once used) and **BR-TEN-034** (a used row cannot
be deleted) *"cannot bite"* — a tenant could delete a payment method that live
payments reference. Both are authored below. Leaving them unauthored would have
been hard-won law 2 in its purest form: a guard built, wired to nothing, with
every test passing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, date, datetime, time
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db import DatabaseError, IntegrityError, transaction

from core import audit as core_audit
from core import errors
from core import numbering
from core import tenancy as core_tenancy

from apps.payments import billing_seam, idempotency, ledger_seam, models, purposes, reconciliation

# CR-059 CS-35 — the tenant's credit/adjustment approval threshold and the
# System-Admin role the write-off control already names. `writeoffs.
# APPROVAL_ROLE` is imported rather than re-stated so the two money controls
# cannot come to require different roles (hard-won law 5).
from apps.payments import custom_values, settings_seam, writeoffs

# `DEFAULT_CLASS_ORDER` is deliberately NOT imported here any more. It was, as
# `record_payment`'s default `class_order`, which meant every caller that stated
# no order — the S22 form among them — allocated under the SHIPPED sequence and
# no tenant's own answer was ever read. Since the PO's ruling of 2026-08-12 the
# default is `None`, meaning "this tenant's `allocation_class_order` setting",
# and the shipped sequence lives in exactly one place: the seeded value of that
# setting (apps/tenancy/settings_families.py). A second copy imported here would
# be free to drift from the order on the tenant's own screen.
from apps.payments.allocation import (
    ORDER_CARRY_CREDIT,
    ORDER_OLDEST_FIRST,
    AllocationClassNotConfigured,
    allocate_payment,
)
from apps.payments.exceptions import PaymentRuleError

# US-PAY-017 — the plan wizard's two write steps, re-exported HERE because
# `services.py` is this module's published write surface (B1) and S24 calls it.
# The lane that built `plans.py` was excluded from this file and REPORTED the
# gap rather than reaching in; without these two names S24 can propose a plan
# and cannot save one. Built is not wired (hard-won law 2), caught by the lane
# that could not fix it.
from apps.payments import plans
from apps.payments.plans import (
    activate_payment_plan,
    payment_plans_for_account,
    propose_payment_plan,
)
from apps.payments.refunds import (
    approve_refund,
    clear_refund,
    issue_refund,
    request_refund,
    void_refund,
)
from apps.payments.reversal import reverse_payment

__all__ = [
    "sample_record_count",
    "remove_sample_records",
    "seed_sample_records",
    "seed_sample_plan_payments",
    "seed_sample_refund",
    "allocate_payment",
    "record_payment",
    "reverse_payment",
    "request_refund",
    "approve_refund",
    "issue_refund",
    "clear_refund",
    "void_refund",
    "payment_method_used_by_count",
    "financial_records_exist",
    "RecordedPayment",
    # US-PAY-017 — the plan wizard's write steps (see the import note above).
    "propose_payment_plan",
    "activate_payment_plan",
    # US-CUS-018 / US-PAY-017 — the READ half, published 2026-08-16 with the S24
    # endpoints. Without it the wizard could write a plan that nothing could
    # ever show back: `payment_plans` is payments-owned and B1 forbids customers
    # reading this ORM directly, so the seam needs a name to resolve.
    "payment_plans_for_account",
]

ZERO = Decimal("0")

#: The audit action codes. Codes, never prose — the trail is grouped on them.
#: `payment.recorded` is EP-PAY-01 US-PAY-001 §5's own entry; `payment.allocated`
#: is the event `apps/payments/services.py` named as US-PAY-006's before either
#: existed.
AUDIT_RECORDED = "payment.recorded"
AUDIT_ALLOCATED = "payment.allocated"

#: The purposes this slice can honour. See the module docstring for why the
#: other three are refused by name rather than treated as `bill`.
#: What the record path does NOT do, carried on every result — the same
#: discipline as `apps/billing/issue.ISSUE_UNAVAILABLE` and
#: `delivery_seam.DELIVERY_UNAVAILABLE`. A caller must not have to infer an
#: absence and a reviewer must not have to take a docstring's word for it
#: (hard-won law 1).
RECORD_UNAVAILABLE: tuple[dict[str, Any], ...] = (
    # ⚠ THE `no_receipt_queued` ENTRY THAT LED THIS TUPLE IS GONE (2026-08-18,
    # CR-009 C-13). It said BR-PAY-024's receipt queue "is US-PAY-025 … and this
    # path does not make it". The path makes it now: `receipts.
    # queue_receipt_for_recorded_payment` runs on every recorded payment behind
    # the tenant's "receipt on record-payment" election (BR-NOT-022, DEFAULT ON
    # per the PO's C-13 ruling), and the OUTCOME rides `problems` per payment —
    # `receipt_queued`, `receipt_election_off`, or the named failure — because
    # a static sentence cannot state a per-tenant election.
    {
        "code": "account_balance_cache_not_updated",
        "br_ref": "BR-CUS-015",
        "detail": "`accounts.balance` is customers' CACHED column (B2: the ledger is the "
        "source of truth) and payments may not write another module's table (B1 / DB-16). The "
        "cache-update seam is in B2's reviewed interface set (r16 #7) and customers publishes "
        "nothing to call. The LIVE position is derivable — invoice totals minus this module's "
        "`allocations` rows — and that is what the allocation above reads.",
    },
)


@dataclass(frozen=True)
class RecordedPayment:
    """What one `record_payment` call did — and what it did not.

    `created=False` is the idempotent replay (US-PAY-001 TC-6, BR-PAY-028): the
    same key arrived twice, the first payment is returned, and NOTHING was
    written the second time — no second row, no second audit entry, no second
    journal entry, no doubled money. A RESULT rather than an exception, for the
    reason `apps/ledger/posting.PostingResult` gives: a double-clicked Record
    button and a retried request are both doing the right thing.

    `applied` / `credit_carried` are the allocator's own figures, copied. This
    class computes nothing.

    `problems` carries codes a screen can group on, never prose it would have to
    parse — the gaps the seams reported plus `RECORD_UNAVAILABLE`.
    """

    payment_id: str
    payment_no: str | None
    created: bool
    status: str
    amount: Decimal
    currency: str
    applied: Decimal = ZERO
    credit_carried: Decimal = ZERO
    allocations: tuple[dict[str, Any], ...] = ()
    #: The ledger entry this payment left, or None when nothing was posted
    #: (a `processing` payment has not reached the books).
    journal_entry_id: str | None = None
    posting_key: str | None = None
    #: BR-CUS-670 — what the customer deposit REGISTER holds after this payment,
    #: or None when this was not a deposit (or when customers publishes no
    #: writer, in which case `problems` says so by name). Stated as a VALUE for
    #: the reason `posted_to_ledger` is: the S36 tie-out compares this figure
    #: against the 2300 liability, and a caller must be able to assert the move
    #: happened rather than trust a docstring (DEF-177, hard-won law 1).
    deposit_held_after: Decimal | None = None
    problems: tuple[dict[str, Any], ...] = field(default=RECORD_UNAVAILABLE)
    #: Stated as a VALUE so a caller can assert it rather than trust prose.
    posted_to_ledger: bool = False
    # ── CR-059 CS-23 · the payment plan this money met ──────────────────────
    #: The account's live plan, when it has one — so S22/S35 can show the
    #: schedule beside the receipt without a second round trip, which is what
    #: CR-059 CS-23 asks those screens for.
    plan_id: str | None = None
    #: The plan's status AFTER this payment. `closed` here is the customer's
    #: last instalment, and it is the one moment a plan ends by being paid.
    plan_status: str | None = None
    #: WHICH instalment this payment met, or None when it met none. `problems`
    #: always says which case it was — an absence must never have to be read.
    installment_seq: int | None = None
    #: BR-PAY-021, stated as a VALUE: the POSTING date against the due date,
    #: never the clearing date.
    installment_on_time: bool | None = None
    # ── CR-186-BRC10 · THE DEPOSIT BATCH IT WAS STAMPED INTO AT POSTING ─────
    #: PO 2026-10-21: the batch ID *"is stamped the moment the payment is
    #: posted, for every method"*, and Invoice Cloud's make-payment reply
    #: carries it. The batch's id, or None when the payment joined no batch
    #: yet — a credit, a post-dated cheque, or a day whose batch was already
    #: matched; `problems` then names which (`deposit_batch_deferred`).
    deposit_batch_id: str | None = None
    #: The batch's human code — `DEP-261014-0001`, from Settings → Numbering.
    deposit_batch_code: str | None = None


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing touches a tenant table without `app.tenant_id`.

    Refuses rather than defaulting. A payment written with no tenant context
    would be blocked by RLS on Postgres and would land in another tenant's
    ledger on SQLite; neither is a thing to let happen quietly on the table a
    customer's money lands in.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


# ── the tenant's within-invoice class order (PO ruling 2026-08-12) ──────────
#
# The S66 rule page the sequence lives on, and the key it lives under. Named as
# constants so the contract is greppable from BOTH sides of the boundary — the
# same discipline `apps/payments/settings_seam.py` uses for the bank-match
# tolerance, and the same reason: a string typed twice is a setting that
# silently stops being read.
CLASS_ORDER_FAMILY = "billing-defaults"
CLASS_ORDER_KEY = "allocation_class_order"


def tenant_class_order() -> tuple[str, ...]:
    """The order THIS TENANT meets a bill's line classes in (BR-PAY-010/038).

    PO ruling 2026-08-12, verbatim: *"Cant we give option to user to set the
    rule in settings; Im not sure how Utilities are going to set settlement
    rules ; they might differ in case of HOA or SUb metering ; better to let
    user set the sequence; we can give default option and allow them to change
    the order"*.

    Read, never assumed. The engine has taken `class_order` as an ARGUMENT since
    it was written and `allocation.DEFAULT_CLASS_ORDER` has always said it was
    "the shipped DEFAULT of a tenant setting, never a constant" — but until
    2026-08-12 nothing read a tenant's answer, so every utility allocated under
    the shipped order whatever their regulator said. A municipal utility, a
    submetering operator and an HOA are three businesses with three answers.

    Tenant scoping is not added here and cannot be lost here: the values come
    from tenancy's own read, which filters on `app.tenant_id` under RLS FORCE
    (hard rule 1). This module issues no query of its own.

    REFUSES rather than falling back, in both directions (hard-won law 3):
    tenancy publishing no `settings_family` is not "the shipped order", and a
    document with no `allocation_class_order` is not "the shipped order"
    either. A `.get(key, DEFAULT_CLASS_ORDER)` here would be a SECOND copy of
    the default, free to drift from the sequence on the tenant's own screen —
    and the drift would show up as money meeting a late fee before a service
    charge, with every total still footing.

    ⚠ WHERE THIS BELONGS. `apps/payments/settings_seam.py` is this module's
    tenancy-settings seam and this read is the same shape as its
    `match_tolerance_days`. It is here rather than there because that file is
    outside this lane's territory; moving it is one edit with no caller change,
    and it is REPORTED rather than done quietly (hard-won law 1).
    """
    read = _resolve("tenancy", "settings_family")
    if read is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            "apps.tenancy.selectors.settings_family is not published, so this tenant's "
            "allocation class order cannot be read. This does NOT fall back to the shipped "
            "order: an unreachable setting is not a setting, and an allocation written under "
            "an order nobody chose is immutable the instant it commits (hard rule 4).",
            br_ref="BR-PAY-038",
        )
    values = read(CLASS_ORDER_FAMILY)
    if CLASS_ORDER_KEY not in values:
        raise PaymentRuleError(
            f"the tenant's {CLASS_ORDER_FAMILY} settings carry no {CLASS_ORDER_KEY!r}. The "
            "ratified default (usage+base → taxes → the tenant-defined class → fees LAST) "
            "lives once, in apps.tenancy.settings_families, and is merged in by tenancy's own "
            "read — a default substituted HERE would be a second copy of it, free to drift "
            "from the order on the tenant's own screen.",
            br_ref="BR-PAY-038",
        )
    return tuple(values[CLASS_ORDER_KEY])


def _account(account_id: Any) -> Any:
    """The account this payment is tagged to, through customers' own read.

    Resolved BY NAME (B1: cross-module reads via service functions only), and
    customers' queryset is tenant-scoped by its own code — so an account id
    belonging to another tenant resolves to nothing and the payment is refused
    without this module ever learning whether the id was real. On Postgres RLS
    refuses it a second time (US-PAY-001 TC-7).

    **Its STATUS is never read.** BR-PAY-036: a payment is always accepted.
    """
    if account_id is None:
        raise PaymentRuleError(
            "a payment names no account. Every payment is tagged to an account, in every "
            "account status (BR-PAY-036) — there is no unassigned bucket for money to sit in.",
            br_ref="BR-PAY-022",
        )
    read = _resolve("customers", "account_queryset")
    if read is None:  # pragma: no cover - defensive
        raise PaymentRuleError(
            "apps.customers.selectors.account_queryset is not published, so this payment "
            "cannot be tagged to an account. Payments may not read customers' ORM directly "
            "(B1).",
            br_ref="BR-PAY-022",
        )
    try:
        account = read().filter(pk=account_id).first()
    except (ValueError, TypeError):  # a malformed id is a caller mistake, not an account fact
        account = None
    if account is None:
        raise PaymentRuleError(
            f"account {account_id!r} is not an account of this tenant, so the payment has "
            "nowhere to be tagged (CLAUDE.md rule 1). Nothing is written.",
            br_ref="BR-PAY-022",
        )
    return account


def _method(method_code: str | None) -> Any:
    """The tenant's live method row for a code, or None when none was named.

    B2 §2 leaves `payments.method` nullable and BR-PAY-026 makes the value a
    seeded, tenant-extensible LOOKUP rather than an enum (r5 #20, OQ-031
    closed), so a tenant that adds "Bill-pay portal" can use it immediately with
    nothing hardcoded here — US-PAY-001 TC-3 verbatim.

    An unknown or DEACTIVATED code is refused, not ignored: IS-1 deactivates
    rather than deletes, and a tenant that retired a method has said stop using
    it. Recording under a code that resolves to nothing would put a payment on
    S33 with a blank method column and no way to tell which it was.
    """
    if method_code is None:
        return None
    lookup = _resolve("tenancy", "PaymentMethod", "models")
    if lookup is None:  # pragma: no cover - defensive
        return None
    row = lookup.objects.filter(tenant_id=_tenant_id(), code=method_code, active=True).first()
    if row is None:
        raise PaymentRuleError(
            f"payment method {method_code!r} is not one of this tenant's active methods "
            "(BR-PAY-026 seeds cash, check, card, ACH, wire and money order, and the list is "
            "tenant-extensible on the Reference data page). A method that has been "
            "deactivated is one the tenant has said stop using.",
            br_ref="BR-PAY-026",
        )
    return row


# ════════════════════════════════════════════════════════════════════════════
# `P2.13` · WHICH TILL TOOK THIS MONEY — `DEF-PAY-6226`
# ════════════════════════════════════════════════════════════════════════════
#: The three tenders that pass through a person's hands (PO ruling 2026-09-23
#: §3.4). Read from `counters.HAND_TENDERS` rather than re-spelled: one rule,
#: one implementation. `ach`, `card`, `wire` and `lockbox` never reach a
#: drawer and bank under phase 0's system till.
def _counter_session(counter_session_id: Any, *, method: Any) -> Any:
    """The till this money was taken into — resolved, checked, or None.

    **`DEF-PAY-6226`.** `payments.counter_session_id` existed from
    `payments/0035` with its index, its reads and `P2.23`'s refusal, and
    **nothing wrote it**: a clerk could open a till at 08:55, take seventeen
    payments and close an empty drawer at 17:30, because every dollar banked
    under the day's system till — the one that is openly nobody's. That is
    hard-won law 2 on the money path, and it is exactly the outcome the PO's
    ruling exists to prevent: *"It is the only option where every cash dollar
    belongs to somebody"*.

    ⚠ **AN ACH, A CARD, A WIRE OR A LOCKBOX PAYMENT IS REFUSED A TILL BY
    NAME, AND THAT REFUSAL IS THE HALF A TEST WOULD MISS.** A test that
    stamps a till id and then asserts it is there passes just as happily when
    the tender filter is inverted or absent, so the rule is enforced HERE, at
    the write, rather than trusted to the one caller that resolves the till.
    `counters.assert_till_open_for_tender` already answers `None` for those
    four, so the endpoint passes nothing — this is what makes a second caller
    unable to put a card swipe in somebody's drawer. The Close screen counts
    what is physically in a drawer; a card total typed back at the system's
    own figure makes the reconciliation worthless.

    ⚠ **IT IS A READ. THE BATCH IS OPENED INSIDE THE PAYMENT'S OWN
    TRANSACTION** (see `record_payment`), so a replayed payment opens no
    batch and a refused one burns no `DEP-` number.

    Tenant-scoped explicitly (hard rule 1): `counter_session_id` carries no
    referential integrity — `payments/0035` says so in its own words — so a
    till id from another tenant would otherwise resolve, and RLS `FORCE`
    answering zero rows is the false zero hard-won law 7 names.
    """
    if counter_session_id is None:
        return None
    from apps.payments import counter_session_models as tills
    from apps.payments import counters as counter_rules

    code = (getattr(method, "code", None) or "").strip().lower()
    if code not in counter_rules.HAND_TENDERS:
        raise PaymentRuleError(
            f"a {code or 'tenderless'} payment cannot be taken into a counter till. Only "
            "money that passes through a person's hands — cash, cheques and money orders — "
            "belongs to a drawer that gets counted (PO ruling 2026-09-23). ACH, card, wire "
            "and lockbox money never reaches a counter and banks in its provider or channel batch "
            "for the day; putting a card swipe in a drawer would make the close count disagree "
            "with what is physically there.",
            br_ref="BR-PAY-1186",
        )
    session = tills.CounterSession.objects.filter(
        tenant_id=_tenant_id(), pk=counter_session_id
    ).first()
    if session is None:
        raise PaymentRuleError(
            "the counter till this payment names does not exist for this utility, so the "
            "money would belong to nobody. `payments.counter_session_id` carries no "
            "referential integrity (payments/0035), so this service is the only guard "
            "there is.",
            br_ref="BR-PAY-1186",
        )
    if session.closed_at is not None:
        raise PaymentRuleError(
            "that counter till is already closed, so money cannot be taken into it: the "
            "drawer has been counted and its deposit footed, and a payment arriving "
            "afterwards would put a signed-off count permanently out. Start your counter "
            "first.",
            br_ref="BR-PAY-1186",
        )
    return session


def _amount(value: Any) -> Decimal:
    """A payment amount: a Decimal, strictly positive (A2 "> 0", US-PAY-001 TC-5).

    A float is REFUSED rather than converted (hard rule 2) — converting would
    hide the place where money became binary and the books would carry a figure
    nobody can reproduce.

    Negative is refused too, and the reason is BR-PAY-002 rather than taste: a
    reversal is a NEW reversing row, so a negative payment would be a second,
    invisible way to express one, and the S33 totals would agree with themselves
    while the money said something else.
    """
    if isinstance(value, float):
        raise PaymentRuleError(
            f"payment amount {value!r} is a float. Money is NUMERIC(18,6) and never a binary "
            "fraction (CLAUDE.md rule 2). It is REFUSED rather than converted, because a "
            "conversion hides the place where money became binary.",
            br_ref="BR-PAY-002",
        )
    if not isinstance(value, Decimal):
        raise PaymentRuleError(
            f"payment amount {value!r} is a {type(value).__name__}; money is a Decimal "
            "(CLAUDE.md rule 2).",
            br_ref="BR-PAY-002",
        )
    if value <= ZERO:
        raise PaymentRuleError(
            f"payment amount {value} must be greater than zero (A2 §S22 '> 0'). A reversal is "
            "a NEW reversing row (BR-PAY-002 / hard rule 4), never a negative payment — two "
            "ways to express the same movement is how a total comes to disagree with itself.",
            br_ref="BR-PAY-002",
        )
    return value


#: CR-059 CS-35 — the two types that are NOT money received. Named once so the
#: recording path, the batching filter and the approval gate all read the same
#: sentence rather than three copies of `!= "payment"`.
NON_CASH_TYPES = (models.PAYMENT_TYPE_CREDIT, models.PAYMENT_TYPE_ADJUSTMENT)


def _payment_type(value: Any) -> str:
    """`payment` | `credit` | `adjustment` (CR-059 CS-35, B2 §1 `payment_type`).

    Refused by name rather than defaulted: the database's own
    `ck_payments_type` would refuse an unknown value anyway, but as an
    IntegrityError inside the money transaction rather than as a sentence a
    clerk can act on — and on PostgreSQL that aborts the whole transaction
    (hard-won law 14).
    """
    if not isinstance(value, str) or value not in models.PAYMENT_TYPES:
        raise PaymentRuleError(
            # CR-059 CS-35 lives in this COMMENT and not in the sentence: gate
            # G28 counts refusal prose carrying an internal reference, the id is
            # already on `br_ref` for a machine, and the person reading the log
            # line wants the three words, not a register to go and look up.
            f"{value!r} is not a payment type. It is one of "
            f"{', '.join(models.PAYMENT_TYPES)}: a PAYMENT is money received, a "
            "CREDIT is money given back, an ADJUSTMENT is a correction. They are told apart "
            "here because only the first is cash and only the first goes to the bank.",
            br_ref="BR-PAY-012",
        )
    return value


def _reason_code(payment_type: str, value: Any) -> str | None:
    """CS-35's *"a reason from a tenant-maintained list"* — required, or refused.

    REQUIRED on a credit or an adjustment, because the reason is what makes
    *"how much did we give away last year, and why"* a question with an answer,
    and because it is what chooses the GL account (CR-008 ruling 9). Whether the
    code is one of this tenant's live reasons is decided by
    `ledger_seam.credit_adjustment_debit_account_id`, which owns the list read —
    two membership tests would eventually disagree.

    REFUSED on a `payment`, and that is not tidiness: a receipt has no reason,
    somebody handed over money. Accepting one silently would let a screen file
    real cash under a giveaway reason and the reason report would count it.
    """
    if payment_type in NON_CASH_TYPES:
        if not isinstance(value, str) or not value.strip():
            raise PaymentRuleError(
                # CR-059 CS-35, in the comment rather than the sentence (G28).
                f"a {payment_type} carries a reason from this utility's own list and none was "
                "given. The list is Settings → Configure → Reason codes; without it, 'how "
                "much did we give away last year, and why' has no answer and the ledger "
                "account this belongs in cannot be chosen.",
                br_ref="BR-TEN-036",
            )
        return value.strip()
    if value is not None:
        raise PaymentRuleError(
            # CR-059 CS-35, in the comment rather than the sentence (G28).
            "a payment carries no reason code — somebody handed over money. A reason belongs "
            "to a credit or an adjustment, and accepting one here would file real cash under "
            "a giveaway reason where a report would then count it.",
            br_ref="BR-PAY-012",
        )
    return None


def _already_posted_source(payment_type: str, value: Any) -> str | None:
    """CR-059 CS-38's one-posting switch, validated before anything is written.

    A non-empty label names the record that ALREADY carries this amount in the
    books, which makes this row non-posting. Lawful only on a credit or an
    adjustment: a receipt that reached the books somewhere else is not a thing
    this product has, and allowing it would be a way to record cash that never
    reaches the trial balance.
    """
    if value is None:
        return None
    if payment_type not in NON_CASH_TYPES:
        raise PaymentRuleError(
            # CR-059 CS-38, in the comment rather than the sentence (G28).
            "only a credit or an adjustment may name a record that already posted it. A "
            "payment is money received and it posts here, once — a receipt excused from the "
            "books is cash the trial balance would never show.",
            br_ref="BR-PAY-012",
        )
    if not isinstance(value, str) or not value.strip():
        raise PaymentRuleError(
            # CR-059 CS-38, in the comment rather than the sentence (G28).
            "the record that already posted this credit must be named. An empty label would "
            "switch the posting off and leave nobody able to say where the money is in the "
            "books.",
            br_ref="BR-PAY-012",
        )
    return value.strip()


def _refuse_unapproved_credit(actor: Any, *, payment_type: str, amount: Decimal) -> None:
    """CS-35's approval gate: above the tenant's threshold, System Admin only.

    *"requires Admin approval above a tenant-set threshold, matching
    write-offs"* — CS-35 verbatim, and the shape is deliberately the write-off's
    (`writeoffs.approval_is_required`): strictly ABOVE the figure needs the
    role, at or below it does not. Seeded 0.00 and an amount must be > 0, so
    today every credit needs a System Admin until a utility types a figure and
    is seen doing it (hard-won law 3).

    Server-enforced, because a screen that hides the button is not an
    authorisation (BR-SHL-025).
    """
    if payment_type not in NON_CASH_TYPES:
        return
    threshold = settings_seam.credit_adjustment_approval_threshold()
    if amount <= threshold:
        return
    if getattr(actor, "role", None) == writeoffs.APPROVAL_ROLE:
        return
    raise PaymentRuleError(
        # CR-059 CS-35, matching the write-off control BR-PAY-020 — in the
        # comment rather than the sentence (G28); `br_ref` below carries the id.
        f"a {payment_type} of {amount} is above this utility's approval threshold of "
        f"{threshold}, so it needs a System Admin to record it. The threshold is on Settings "
        "→ Accounting → Finance controls; a credit is money given away and the loose setting "
        "is the one somebody has to type.",
        br_ref="BR-PAY-020",
    )


def _dates(posted_at: Any, cleared_at: Any) -> tuple[datetime, datetime | None]:
    """BR-PAY-021's pair, validated. Both are INPUTS; nothing here reads a clock.

    BR-PAY-033 is explicit that the posting date is USER-ENTERED at entry and at
    import — *"never silently the system timestamp"* — with the UI pre-filling a
    default the user may override. So this function refuses a missing posting
    date rather than stamping `now()`: a defaulted posting date is a payment
    whose on-time status was decided by whenever the request happened to arrive
    (BR-TEN-043, and gate G6 greps every money path for the violation).
    """
    if not isinstance(posted_at, datetime):
        raise PaymentRuleError(
            "a payment needs a POSTING date and it is the user's (BR-PAY-021 / BR-PAY-033: "
            "'never silently the system timestamp'). Billing reads exactly this date to decide "
            "whether the payment was on time, so a value taken from the clock would let the "
            "moment a request arrived decide whether a customer owes a late fee.",
            br_ref="BR-PAY-021",
        )
    if cleared_at is not None and not isinstance(cleared_at, datetime):
        raise PaymentRuleError(
            "the CLEARING date must be a datetime or absent (BR-PAY-021). Absent means the "
            "payment is still processing — the money has not arrived — which is a legal state, "
            "not a missing value.",
            br_ref="BR-PAY-021",
        )
    return posted_at, cleared_at


def _currency(account: Any, stated: str | None) -> str:
    """CHAR(3), the account's own unless the caller names the same one.

    BR-TEN-042 locks a tenant's currency once a financial record exists, so a
    payment in a currency the account does not hold is not a conversion problem
    — it is a payment against the wrong account. Refused rather than converted:
    this module holds no FX rate and inventing one would be inventing money.
    """
    account_currency = getattr(account, "currency", None)
    if stated is None:
        if not account_currency:  # pragma: no cover - the column has a default
            raise PaymentRuleError(
                "the account states no currency, so the payment has none (CLAUDE.md rule 2: "
                "money is NUMERIC(18,6) + CHAR(3), and a defaulted currency is how a CAD "
                "tenant's books quietly become USD).",
                br_ref="BR-TEN-042",
            )
        return account_currency
    if len(str(stated)) != 3:
        raise PaymentRuleError(
            f"currency {stated!r} is not a CHAR(3) code (CLAUDE.md rule 2).",
            br_ref="BR-TEN-042",
        )
    if account_currency and str(stated) != account_currency:
        raise PaymentRuleError(
            f"the payment states {stated!r} and the account holds {account_currency!r}. "
            "Nothing here converts between them: this module holds no exchange rate, and "
            "BR-TEN-042 locks a tenant to one currency once a financial record exists.",
            br_ref="BR-TEN-042",
        )
    return str(stated)


def _existing(tenant_id: Any, key: str | None) -> models.Payment | None:
    """The payment already recorded under this idempotency key, if any."""
    if key is None:
        return None
    return models.Payment.objects.filter(tenant_id=tenant_id, webhook_key=key).first()


def _moved_from(tenant_id: Any, payment_id: Any) -> Any:
    """CR-059 CS-32 — the payment this money was recorded against before, or None.

    Validated BEFORE anything is written, like every other linkage on this path
    (BR-PAY-012's purpose resolution does the same, for the same reason): a link
    that cannot be made must leave no orphan row behind it.

    **A CROSS-TENANT ID IS REFUSED BY NAME.** `payments` carries RLS FORCE, so
    the filter below cannot see another tenant's row and the id simply resolves
    to nothing — which would otherwise be indistinguishable from a typo. Saying
    which it is costs one lookup and is what stops a move quietly linking to
    nowhere (CLAUDE.md hard rule 1).
    """
    if payment_id is None:
        return None
    if not models.Payment.objects.filter(tenant_id=tenant_id, pk=payment_id).exists():
        raise PaymentRuleError(
            f"payment {payment_id} was named as the row this money came from, and it is not "
            "this tenant's. Nothing was recorded: a moved payment whose origin cannot be read "
            "is a payment nobody can explain to the customer who holds the receipt.",
            br_ref="BR-TEN-003",
        )
    return payment_id


def _replayed(payment: models.Payment) -> RecordedPayment:
    """The no-op answer for a payment this tenant has already recorded.

    Reports the ORIGINAL payment's figures, read back from its own rows, so a
    caller that lost a race links to the money that actually exists rather than
    to the one it tried to write.
    """
    allocations = tuple(
        {"invoice_id": str(row.invoice_id), "amount": row.amount}
        for row in payment.allocations.all().order_by("created_at", "id")
    )
    applied = sum((row["amount"] for row in allocations), ZERO)
    return RecordedPayment(
        payment_id=str(payment.pk),
        payment_no=payment.payment_no,
        created=False,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        applied=applied,
        credit_carried=payment.amount - applied,
        allocations=allocations,
        journal_entry_id=None if payment.journal_entry_id is None else str(payment.journal_entry_id),
        deposit_batch_id=None if payment.deposit_batch_id is None else str(payment.deposit_batch_id),
        deposit_batch_code=_batch_code(payment.deposit_batch_id),
        problems=RECORD_UNAVAILABLE
        + (
            {
                "code": "duplicate_submit_ignored",
                "br_ref": "BR-PAY-028",
                "detail": f"a payment was already recorded under this idempotency key as "
                f"{payment.payment_no or payment.pk}. Nothing was written: one payment, one "
                "audit row, one journal entry, and the money is not doubled.",
            },
        ),
    )


def _batch_code(batch_id: Any) -> str | None:
    """A deposit batch's human code, read by id (tenant-scoped), or None."""
    if batch_id is None:
        return None
    from apps.payments import bankrec_models

    return (
        bankrec_models.DepositBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id)
        .values_list("code", flat=True)
        .first()
    )


def record_payment(
    actor: Any,
    *,
    account_id: Any,
    amount: Decimal,
    posted_at: datetime,
    cleared_at: datetime | None = None,
    currency: str | None = None,
    method_code: str | None = None,
    confirmation: str | None = None,
    memo: str | None = None,
    purpose: str = models.PURPOSE_BILL,
    plan_id: Any = None,
    installment_seq: int | None = None,
    order: str = ORDER_OLDEST_FIRST,
    targets: tuple[Any, ...] = (),
    class_order: tuple[str, ...] | None = None,
    idempotency_source: str = idempotency.SOURCE_ENTRY,
    idempotency_reference: Any = None,
    payment_type: str = models.PAYMENT_TYPE_PAYMENT,
    reason_code: str | None = None,
    already_posted_source: str | None = None,
    moved_from_payment_id: Any = None,
    cheque_date: Any = None,
    drawer_bank: str | None = None,
    bankable_from: Any = None,
    tender_id: Any = None,
    counter_session_id: Any = None,
    custom_data: Any = None,
    custom_data_screen: str | None = None,
    warn_on_possible_duplicate: bool = False,
    duplicate_confirmed: bool = False,
    channel: str | None = None,
    terminal: str | None = None,
    deposit_channel: str | None = None,
    store_network: str | None = None,
) -> RecordedPayment:
    """Record ONE payment (BR-PAY-022) — all of it, or none of it.

    ════════════════════════════════════════════════════════════════════════
    EVERY PAYMENT IS POSTED AT ENTRY — CR-186-BRC10, PO 2026-10-21
    ════════════════════════════════════════════════════════════════════════
    PO, verbatim: *"whether invoice cloud, or any other payment provider, or
    counter, or lockbox or any payment method - first they will pot the payment
    - so we crete the record and add posting date; then later money is recieved
    in the bank account ; uitlity will reconcile it bank statement that time it
    is cleared with clearing date"*. So, for every caller and every tender:

      * the row is written **`posted`**, with its posting date and **no
        clearing date** — `cleared_at` is still accepted for the callers that
        pass one and is NOT stored; `cleared` is written only by
        `reconciliation.clear_members` when the deposit batch is reconciled;
      * it is **applied to open bills and journalled now** (DR the tender's
        holding account / CR AR, + CR customer credit for an overpayment —
        ruled unchanged the same day), the entry DATED THE POSTING DATE and
        forwarded to the first open period when that one is closed
        (`ledger_seam.entry_date_for_posting`, BR-TEN-038). The payment keeps
        its own posting date, which still decides late fees;
      * it is **stamped into its deposit batch now** — its till's, or its
        provider/channel's for that day (`reconciliation.
        batch_for_new_payment`); `deposit_channel` names the channel outright,
        otherwise it is derived from the origin and the idempotency reference.

    `processing` is no longer written by a new payment. The sections below
    that describe a `processing` payment describe the rows written before
    2026-10-21, which keep their status (PO: *"b - … it is all testing and
    sandbox only"*).

    `store_network` (PO 2026-10-30 Q6) — the store payment network a payments
    file's **Network** column named (`Hy-Vee`). Written by the INSERT and by
    nothing else; it picks the deposit channel (`store:hy-vee`, one batch per
    network per day) and the *Store · Hy-Vee* label. `None` keeps today's
    channel. Only `payments.import_writer` passes it — never a screen field.

    `channel` / `terminal` (`CR-174-BRC10`) — where the customer stood and which
    machine, when a payment AGENT took the money. Written by the INSERT and by
    nothing else; `None` on every other caller, which is every caller but
    `agent_door.post_payment`.

    The field set is BR-PAY-022's, verbatim: *"account → amount, method,
    posting+clearing dates, reference, allocation choice"*, plus BR-PAY-012's
    purpose and r14 #4's memo.

    `order` / `targets` / `class_order` are the allocation instruction and they
    are passed STRAIGHT THROUGH to `allocation.allocate_payment` — the tenant
    setting (BR-PAY-010 "tenant-configurable"), the staff choice on the S22 form
    (BR-PAY-001 specific / carry / split) and the within-invoice class order
    (BR-PAY-038's four classes, fees LAST). Defaults are the shipped defaults
    and are never treated as law: US-PAY-006 TC-5 is a tenant putting fees
    before taxes, and T7-13 is a tenant reversing the bill order.

    **`class_order=None` means "this tenant's own sequence" — PO ruling
    2026-08-12.** It used to default to `allocation.DEFAULT_CLASS_ORDER`, so
    the S22 form, which states no class order, allocated every utility's money
    under the shipped one no matter what their regulator required. It now
    resolves `tenant_class_order()`, which reads the S66 Billing-defaults page
    (`allocation_class_order`) whose seeded value IS that same shipped order —
    so nobody's figure moved and a tenant who wants tax first now has somewhere
    to say so. An explicit `class_order` still wins: US-PAY-006 TC-5 prices a
    preview with one, and the argument was never the problem.

    `idempotency_reference` is the client token the S22 form submits
    (US-PAY-001 TC-6, BR-PAY-028). With none, no key is stored and a double
    submit records two payments — so the caller that owns a submit button must
    pass one, and the API layer will. Named rather than defaulted to a generated
    uuid, because a key this function invented would be different on the second
    submit and would dedupe nothing while looking like it did.

    ════════════════════════════════════════════════════════════════════════
    IT MEETS THE ACCOUNT'S NEXT PLAN INSTALMENT — CR-059 CS-23, 2026-09-01
    ════════════════════════════════════════════════════════════════════════
    **This is the caller `plans.record_installment_payment` never had, and its
    absence was a defect that undid the whole payment-plan feature.** Until
    today this path linked a payment to the PLAN — and only for a `plan_down`
    payment, which is the only purpose the `ck_payments_plan_only_on_plan_down`
    check constraint allows to carry a `plan_id` — and it never touched the
    instalment ROW. So every instalment stayed unmarked: from the day after the
    first one fell due the plan read as BEHIND, BR-CUS-043's dunning pause never
    applied, a customer paying perfectly on time was chased up the collection
    ladder, missed-instalment notices went to customers who had missed nothing,
    and the plan could never close.

    `plans.link_payment_to_installment` runs INSIDE THIS TRANSACTION, beside the
    payment row, its allocations, its journal entry and its audit rows — all of
    it commits or none of it does. A link written afterwards could outlive a
    rolled-back payment and mark an instalment met by money that never existed.

    **`installment_seq` is the clerk's choice on S22/S35** — CR-059 CS-23 puts
    *"the option to change it"* on those screens. `None`, which is what the API
    and every batch caller send today, means the ruled default: the EARLIEST
    UNMET instalment. Which instalment and whether the money covers it are both
    decided by `plans.meets_installment`, out of the PO's *"plan first"* ruling
    of 2026-08-12 (OQ-139) — this file invents neither.

    **THREE KINDS OF MONEY MEET NO INSTALMENT, each for a stated reason:** a
    DEPOSIT, because it is money the utility holds and it meets no bill either
    (US-PAY-002 TC-1); a `plan_down` DOWN PAYMENT, because BR-CUS-043's schedule
    is what remains AFTER the down payment and marking instalment 1 with it
    would have the customer pay the same $36.22 twice; and a PROCESSING payment,
    because the money has not arrived — the same gate that stops it meeting a
    bill. Every one of the three is REPORTED on `problems` by name rather than
    left as a silence a screen would read as a link (hard-won law 1).

    ════════════════════════════════════════════════════════════════════════
    IT ACCEPTS THE TYPE NOW — CR-059 CS-35, 2026-09-02
    ════════════════════════════════════════════════════════════════════════
    **`payment_type` is `payment` | `credit` | `adjustment`.** The column, its
    check constraint and the three values have existed since the first payments
    migration and the frontend has published all three since it shipped;
    **nothing had ever written anything but `payment`, and this function did not
    even take the argument.** So the only way to put a goodwill credit or a
    regulator-ordered adjustment on an account was to record a FAKE PAYMENT —
    money the utility never received, sitting in the day's takings.

    **THREE THINGS BRANCH ON IT, AND EVERY ONE OF THEM IS A RULE:**

      1. **BATCHING.** A credit or adjustment is never swept into a deposit
         batch and never appears on bank reconciliation. `reconciliation.
         cut_deposit_batches` is where that happens and it NAMES the row it
         skipped rather than dropping it. Batching one would make the day's
         takings permanently un-tieable against the drawer.
      2. **THE GL ACCOUNT.** It posts to its own account — the reason's mapped
         one (CR-008 ruling 9) or the ruled `write_off` designation — and never
         to undeposited funds or a tender's clearing account, because no cash
         arrived. `ledger_seam.post_credit_adjustment`.
      3. **APPROVAL.** Above the tenant's
         `credit_adjustment_approval_threshold_amount` (seeded 0.00, so every
         one) the recorder must hold System Admin, matching write-offs.

    **THE ALLOCATION ENGINE NEEDS NO CHANGE AND GETS NONE.** A credit meets open
    bills exactly as a payment does and its remainder carries as account credit.
    That is CS-35's own sentence and it is why this is a branch on three things
    rather than a second recording path.

    **`reason_code` is REQUIRED for a credit or an adjustment and REFUSED for a
    payment.** It is validated against the tenant's own reason list
    (BR-TEN-036) and it is what makes *"how much did we give away last year, and
    why"* answerable — through the GL account the reason maps to, which is the
    stated purpose of the column CR-008 ruling 9 added. A receipt has no reason:
    somebody handed over money.

    ⚠ **`already_posted_source` IS CS-38's ONE-POSTING ANSWER AND IT IS THE ONE
    THING IN THIS FUNCTION THAT CAN INVENT MONEY IF IT IS GOT WRONG.** Naming a
    record that ALREADY carries this amount in the books makes this row
    **non-posting**: no entry is composed, `journal_entry_id` stays NULL, and
    `problems` says which record holds it. It exists because a goodwill
    concession is posted by `apps.billing.corrections.execute_credit_only` (DR
    write-off / CR customer credit balance, PO 2026-08-12) BEFORE payments is
    asked to record the credit row, and a second posting here would be a real
    25.00 of money the utility never gave away. **Lawful only on a `credit` or
    `adjustment` row** — a receipt that reached the books elsewhere is not a
    thing this product has.

    **A NON-POSTING ROW STILL CANNOT BE BOUNCED, AND THAT NEEDS NO NEW GUARD:**
    `ledger_seam.reverse_payment_entry` already refuses a payment with no
    `journal_entry_id`, by name, because there is nothing to mirror. A concession
    is not a cheque and cannot come back from a bank.

    ════════════════════════════════════════════════════════════════════════
    IT CAN SAY WHERE THE MONEY CAME FROM — CR-059 CS-32, 2026-09-03
    ════════════════════════════════════════════════════════════════════════
    **`moved_from_payment_id` is written by the INSERT below and by nothing
    else, and that is the whole reason it is an argument rather than a later
    update.** CS-32's move records the money on the account that should have had
    it and links the new row to the one the customer was actually given a number
    for. Hard rule 4's trigger (`payments/0002`) refuses every column change on a
    row that is not `processing`, so a link written a statement later would be
    refused on every cleared payment — which is nearly all of them. The column is
    therefore set at birth, in the same statement, or not at all.

    It is `None` for every ordinary recording and `apps/payments/transfer.
    move_payment_to_account` is its only caller. A value is REFUSED unless it
    names a payment of THIS tenant, because a link to another tenant's row would
    be a cross-tenant reference on a money path (hard rule 1).

    ════════════════════════════════════════════════════════════════════════
    A CHEQUE IS A THING NOW — CR-059 CS-30, 2026-09-03
    ════════════════════════════════════════════════════════════════════════
    **`cheque_date`, `drawer_bank` and `bankable_from` are written by the INSERT
    below and by nothing else**, for the same reason `moved_from_payment_id` is:
    hard rule 4's trigger refuses every column change on a row that is not
    `processing`, so a cheque fact written a statement later would be refused on
    every cleared payment.

    **The cheque NUMBER is not among them and its absence is considered.** It is
    `confirmation`, which it always was, and which is one of the exactly three
    columns the PO opened to correction on 2026-09-02 — so a mistyped cheque
    number stays fixable. A fourth column would have held a number nobody could
    ever correct.

    `apps/payments/cheques.py` owns the rules: the three facts travel together,
    the number is checked for a duplicate against the same drawer bank, and
    `bankable_from` may not precede the cheque's own date. This function calls
    them and invents none of them — **and the duplicate check runs BEFORE the
    transaction opens**, so a refused cheque leaves no `PMT-` number burnt out of
    the tenant's series behind it.

    ════════════════════════════════════════════════════════════════════════
    IT CAN BE ONE PART OF ONE CHEQUE — CR-059 CS-12 + CS-27, 2026-09-03
    ════════════════════════════════════════════════════════════════════════
    **`tender_id` names the `payment_tenders` row this payment was part of**, and
    it is written by the INSERT below and by nothing else, for the third time on
    this row and for exactly the reason `moved_from_payment_id` and the cheque
    columns give: hard rule 4's trigger refuses every column change on a payment
    that is not `processing`, and the three columns the PO opened on 2026-09-02
    (`payments/0014`) do not include this one.

    `None` for every ordinary recording, which is nearly all of them.
    **`apps/payments/tenders.record_multi_account_payment` is its only caller**,
    and it passes it inside the single transaction that also writes the tender —
    so a payment can never point at a tender that rolled back, and a tender can
    never exist with parts that did not.

    ⚠ **THIS FUNCTION STILL RECORDS EXACTLY ONE PAYMENT AGAINST EXACTLY ONE
    ACCOUNT, AND THAT IS THE POINT.** CS-12's *"one tender row and N payments,
    never N unrelated payments"* is built by WRAPPING this path N times in one
    transaction, not by teaching it about several accounts. A payment carries one
    mandatory account and meets a bill only through an allocation against that
    bill's invoice, so settling three accounts REQUIRES three payment rows —
    which is also why *"three balanced journal entries are not an error"*
    (CS-12): each one settled a different account's receivable.

    ════════════════════════════════════════════════════════════════════════
    `counter_session_id` — WHICH TILL TOOK THIS MONEY (CR-136-BRC07 `P2.13`)
    ════════════════════════════════════════════════════════════════════════
    **`DEF-PAY-6226`: this parameter is the thing phase 2 was missing.** The
    column, its index, its readers and the endpoint's refusal all landed
    without it, so no dollar a clerk took ever belonged to their drawer.

    **It stamps TWO columns in the one INSERT, and both are write-once
    there or never** (hard rule 4 — `trg_payment_immutable` is `BEFORE UPDATE
    OR DELETE`, so an INSERT is free and every later UPDATE of either column
    is refused; `counter_session_id` is in neither the `mutable` nor the
    `stamps` allow list of `payments/0014` and nothing here widens it):

      * `counter_session_id` — the till, straight from the caller;
      * `deposit_batch_id` — the till's batch for THIS tender, from
        `counters.batch_for()`, opened inside this transaction if this is the
        first payment of that tender at that till (`payments/0033` keys a
        batch on `(tenant, session, method)`; a till opens holding only its
        CASH batch, `OQ-PAY-12599`).

    **The batch is stamped WHEN THE MONEY IS TAKEN, never at close**, and the
    blueprint says why in `P2.13`'s own words: *"The id attaches when taken.
    Not at close."* An earlier draft stamped at close; the drawing kept the
    test precisely to stop it drifting back.

    ⚠ **WHAT THAT DOES TO THE NIGHTLY CUT, STATED RATHER THAN LEFT TO BE
    FOUND:** `cut_deposit_batches` selects on `deposit_batch_id IS NULL`, so a
    counter payment is **never a candidate** — not skipped-and-reported,
    filtered out before the loop sees it. It is neither double-counted nor
    re-grouped, and hard rule 6 still holds: a second cut on the same day
    cuts nothing. `close_counter._seal_batches` is what foots the till's
    batches, because the cut never touches them.

    ⚠ **A CHEQUE IS STAMPED WHILE IT IS STILL `processing`, ON PURPOSE.** It
    is physically in the drawer at 17:30 and `_drawer_payments` counts it
    there. The clearing UPDATE that follows days later moves `status` and
    `cleared_at` only, which `payments/0014`'s `processing` branch already
    permits, and it leaves both stamps alone.

    ════════════════════════════════════════════════════════════════════════
    THE UTILITY'S OWN FIELDS — CAPTURED HERE, NEVER READ BY MONEY (CR-161 W5)
    ════════════════════════════════════════════════════════════════════════
    PO 2026-10-02: *"Payments IN as capture-at-entry only"* — *"Can't be
    corrected afterwards; never used to apply the payment to bills"*. The
    answers are validated by `custom_values.capture` (tenancy's one validator,
    through `settings_seam`) BEFORE the transaction opens, so a refused answer
    burns no `PMT-` number, and written by the INSERT below and by nothing
    else: the column is in neither of `payments/0014`'s allow lists, so the
    trigger refuses a later UPDATE in every status. **`_allocate_and_post` is
    never handed them** — the allocation of $120.00 is the same with or
    without *Drawer = 2* (BR-TEN-048; G6 / DB-17 fails a read anywhere else
    in this module). The screen argument names the form they were typed on
    (`S35`) so a required field binds only there; every other caller passes
    neither and stores `{}`.

    ════════════════════════════════════════════════════════════════════════
    "LOOKS LIKE A DUPLICATE" — CARD AND ACH (DEF-PAY-9263, PO 2026-10-03)
    ════════════════════════════════════════════════════════════════════════
    PO, verbatim: *"Same card or ACH payment entered twice - B Warn "Looks like
    a duplicate", and let the clerk confirm"* (`BR-PAY-1199`). Two flags, both
    OFF by default so the portal, webhooks, imports and every batch caller are
    byte-for-byte unchanged:

      * `warn_on_possible_duplicate` — a STAFF door asks. When
        `duplicates.find_possible_duplicate` finds one already recorded on the
        same account, amount and day — ANY tender since 2026-10-30 (Q1 = A;
        until then card/ACH only, with the reference as a fourth fact) — this raises
        `duplicates.PossibleDuplicatePayment` naming it — BEFORE anything is
        written, AFTER the replay check (one form pressed twice is one payment,
        not a duplicate).
      * `duplicate_confirmed` — the clerk pressed *Record anyway*. The payment
        is saved exactly as it would have been, and the `payment.recorded`
        audit row says the warning was overridden and which payment it
        resembled (hard rule 7). Nothing about the amount, the allocation or
        the status changes.

    Raises `PaymentRuleError` for everything a human can act on. Returns
    `RecordedPayment(created=False)` for a replay — never an exception.
    """
    tenant_id = _tenant_id()
    payment_type = _payment_type(payment_type)
    moved_from_payment_id = _moved_from(tenant_id, moved_from_payment_id)
    # CR-059 CS-30, BEFORE anything is written — the same discipline BR-PAY-012's
    # purpose linkage keeps: a cheque whose facts do not hold together must leave
    # no orphan row and no burnt number behind it.
    from apps.payments import cheques as cheque_rules

    cheque_rules.validate_cheque_fields(
        cheque_date=cheque_date,
        drawer_bank=drawer_bank,
        bankable_from=bankable_from,
        confirmation=confirmation,
    )
    if cheque_date is not None:
        cheque_rules.refuse_a_duplicate_cheque(
            tenant_id, confirmation=confirmation or "", drawer_bank=drawer_bank or ""
        )
    reason_code = _reason_code(payment_type, reason_code)
    already_posted_source = _already_posted_source(payment_type, already_posted_source)
    # CR-161-BRC10 W5 — the utility's own answers, refused or cleaned BEFORE
    # anything is written (see the docstring's last section).
    captured_at_entry = custom_values.capture(custom_data, screen=custom_data_screen)
    account = _account(account_id)
    # BR-PAY-012's linkage is resolved BEFORE anything is written, so a purpose
    # whose linkage cannot be made refuses with no orphan row behind it
    # (US-PAY-002 TC-5). `_account` runs first only so a cross-tenant account id
    # is refused by the tenant check rather than by a plan lookup that would
    # find nothing for a different reason.
    linkage = purposes.resolve(account.pk, purpose, plan_id=plan_id)
    purpose = linkage.purpose
    amount = _amount(amount)
    # CS-35's approval gate, BEFORE anything is written and before the tender is
    # resolved — a credit nobody may record must leave no trace of having been
    # attempted, and the refusal must name the policy rather than a method.
    _refuse_unapproved_credit(actor, payment_type=payment_type, amount=amount)
    posted_at, cleared_at = _dates(posted_at, cleared_at)
    currency = _currency(account, currency)
    method = _method(method_code)
    # CR-136-BRC07 `P2.13` / `DEF-PAY-6226`. A READ, before the transaction and
    # before the replay check: resolving a till writes nothing, and a refused
    # or replayed payment must open no batch and burn no `DEP-` number. The
    # tender check lives in the helper so a second caller cannot put a card
    # swipe in somebody's drawer.
    counter_session = _counter_session(counter_session_id, method=method)
    key = (
        idempotency.inbound_payment_key(source=idempotency_source, reference=idempotency_reference)
        if idempotency_reference is not None
        else None
    )

    # Cheap path first: a replay costs one SELECT and opens no transaction.
    # The unique index below is what makes a LOST RACE indistinguishable from a
    # replay — neither writes a second payment.
    #
    # RESTORED 2026-08-11 (DEF-058). This line read
    # `already = None  # RED PROOF — pre-insert lookup removed` — a hard rule 6
    # guard that had been switched off to prove US-PAY-001 TC-6 goes RED, and
    # then committed in that state. The suite stayed green because the UNIQUE
    # index catches the duplicate one layer down, which is exactly why nobody
    # noticed: TC-6's own docstring says *"Two guards stand here and BOTH are
    # asserted"* and only one of them existed. The cost while it was off was
    # real but quiet — every double-click opened a transaction, allocated a
    # PMT- number from the tenant series, wrote an audit row and rolled the lot
    # back on the index violation.
    already = _existing(tenant_id, key)
    if already is not None:
        return _replayed(already)

    # ── DEF-PAY-9263 · BR-PAY-1199 — "Looks like a duplicate", card and ACH ──
    # A READ, after the replay check and before the transaction, so a warned
    # payment burns no `PMT-` number and writes nothing.
    resembles = None
    if warn_on_possible_duplicate:
        from apps.payments import duplicates

        resembles = duplicates.find_possible_duplicate(
            tenant_id,
            account_id=account.pk,
            amount=amount,
            confirmation=confirmation,
            posted_at=posted_at,
            method_code=None if method is None else method.code,
            payment_type=payment_type,
            targets=tuple(targets),
        )
        if resembles is not None and not duplicate_confirmed:
            raise duplicates.PossibleDuplicatePayment(resembles)

    # Q6 — one spelling of the name: whitespace collapsed, 60 characters at
    # most, blank → None (a blank cell is a lockbox row, not a nameless store).
    network_name = " ".join(str(store_network or "").split())[:60] or None
    try:
        with transaction.atomic():
            # ── CR-186-BRC10 · THE BATCH, STAMPED AT POSTING, FOR EVERY METHOD ──
            # INSIDE the transaction, beside the payment row it belongs to:
            # either both exist or neither does. A till's ONE batch (all
            # tenders), or the provider/channel's batch for the posting day.
            stamped = reconciliation.batch_for_new_payment(
                tenant_id=tenant_id,
                posted_on=posted_at.date(),
                payment_type=payment_type,
                amount=amount,
                bankable_from=bankable_from,
                counter_session=counter_session,
                channel=reconciliation.channel_for(
                    origin=idempotency_source,
                    reference=idempotency_reference,
                    explicit=deposit_channel,
                    network=network_name,
                ),
                actor=actor,
                occurred_at=posted_at,
            )
            counter_batch_id = None if stamped.batch is None else stamped.batch.pk
            payment = models.Payment.objects.create(
                tenant_id=tenant_id,
                account=account,
                # BR-TEN-035: allocated INSIDE this transaction, from the tenant's
                # PMT- series, under the payment's OWN posting date — so a
                # backdated entry numbers under its date and a rollback rolls the
                # counter back with the row it would have numbered.
                payment_no=numbering.next_number(numbering.PAYMENT, posted_at.date()),
                # CR-059 CS-35. This read `type=models.PAYMENT_TYPE_PAYMENT`
                # unconditionally from the day the table existed, which is why
                # a goodwill credit could only be recorded as a fake receipt.
                type=payment_type,
                method=method,
                amount=amount,
                currency=currency,
                # CR-186-BRC10 — POSTED, for every method. `cleared` is the
                # bank reconciliation's word and nothing here writes it.
                status=models.PAYMENT_POSTED,
                purpose=purpose,
                plan=linkage.plan,
                confirmation=confirmation,
                memo=memo,
                posted_at=posted_at,
                # CR-186-BRC10 — no clearing date at entry; the reconciliation
                # writes it, once, with the bank's date.
                cleared_at=None,
                webhook_key=key,
                # ── CR-132-BRC07 · WHERE THIS MONEY CAME FROM ──────────────
                # WRITE-ONCE, here or never (hard rule 4). The value is the
                # caller's `idempotency_source`, which is ALREADY the three
                # words this column holds — so the origin is OBSERVED at the
                # one moment anybody knows it, rather than inferred later from
                # a key that is NULL whenever no reference was passed.
                #
                # ⚠ `origin_is_derived=False` is written by this same
                # statement and is the whole point of the pair: `payments/0029`
                # stamped every older row TRUE because its value was guessed
                # from the key prefix. A reader must be able to tell a record
                # from an inference, and after this line it can.
                origin=idempotency_source,
                origin_is_derived=False,
                # CR-059 CS-32 — written HERE or never; see the docstring.
                moved_from_payment_id=moved_from_payment_id,
                # CR-059 CS-30 — the same rule, and the same reason.
                cheque_date=cheque_date,
                drawer_bank=(drawer_bank or None) and drawer_bank.strip(),
                bankable_from=bankable_from,
                # CR-059 CS-12 + CS-27 — the ONE cheque this payment was part
                # of. Written HERE or never, for the third time on this row and
                # for the same reason: hard rule 4's trigger refuses a column
                # change on a payment that is not `processing`, and the three
                # columns the PO opened on 2026-09-02 do not include this one.
                # `tenders.record_multi_account_payment` is its only caller.
                tender_id=tender_id,
                # ── CR-136-BRC07 `P2.13` · WRITTEN HERE OR NEVER ───────────
                # `trg_payment_immutable` is `BEFORE UPDATE OR DELETE`, so an
                # INSERT carries these freely and no later UPDATE can: neither
                # column is in `payments/0014`'s `mutable` list (the
                # `processing` branch) or its `stamps` list (the past-
                # `processing` branch), so both are frozen from the moment the
                # row exists. NULL on every payment that did not pass through
                # a person's hands — which is every ACH, card, wire and
                # lockbox row in the product, and is why `P2.4` stays nullable.
                counter_session_id=(
                    None if counter_session is None else counter_session.pk
                ),
                deposit_batch_id=counter_batch_id,
                # ── CR-161-BRC10 W5 · WRITTEN HERE OR NEVER ─────────────────
                # Not on either allow list, so the trigger refuses any later
                # change (`payments/0046`). Read back only by `custom_values`.
                custom_data=captured_at_entry,
                # CR-174-BRC10 — written HERE or never (hard rule 4).
                channel=channel,
                terminal=terminal,
                # PO 2026-10-30 Q6 — written HERE or never (hard rule 4).
                store_network=network_name,
            )
            # ── hard rule 7, INSIDE the transaction ─────────────────────────
            # `core.audit` raises rather than losing the row, which takes the
            # payment with it. Money recorded with no record of who took it is
            # the one outcome rule 7 exists to prevent.
            core_audit.money_action(
                actor,
                AUDIT_RECORDED,
                "payment",
                str(payment.pk),
                after={
                    "payment_no": payment.payment_no,
                    "account_id": str(account.pk),
                    "amount": str(amount),
                    "currency": currency,
                    "status": payment.status,
                    "purpose": purpose,
                    # CR-059 CS-35 — hard rule 7 owes the trail the fact that
                    # this was NOT money received, and the reason it was given.
                    # The reason has no column on `payments` (CS-35: "Data:
                    # none on payments") and this row is where it is kept.
                    "type": payment_type,
                    "reason_code": reason_code,
                    "already_posted_source": already_posted_source,
                    "plan_id": str(linkage.plan.pk) if linkage.plan is not None else None,
                    "method": method_code,
                    "confirmation": confirmation,
                    "posted_at": posted_at.isoformat(),
                    "cleared_at": None,
                    "idempotency_key": key,
                    # CR-059 CS-32 — the row this money was recorded on before
                    # somebody noticed. NULL on every ordinary recording.
                    "moved_from_payment_id": (
                        None if moved_from_payment_id is None else str(moved_from_payment_id)
                    ),
                    # CR-059 CS-30 — the cheque's own facts on the trail hard
                    # rule 7 already writes. `confirmation` above is its number.
                    "cheque_date": None if cheque_date is None else cheque_date.isoformat(),
                    "drawer_bank": drawer_bank,
                    "bankable_from": (
                        None if bankable_from is None else bankable_from.isoformat()
                    ),
                    # CR-059 CS-12 — hard rule 7 owes the trail the fact that
                    # this money arrived as PART of one tender, because the
                    # tender is what a clerk and an auditor recognise (one
                    # cheque) and the payment on its own is not.
                    "tender_id": None if tender_id is None else str(tender_id),
                    # CR-136-BRC07 `P2.13` — hard rule 7 owes the trail WHOSE
                    # DRAWER this money went into and which deposit it banks
                    # in. Both are what a supervisor asks about a count that
                    # does not tie, and neither can be reconstructed later:
                    # the till is write-once and the batch is sealed at close.
                    "counter_session_id": (
                        None if counter_session is None else str(counter_session.pk)
                    ),
                    "deposit_batch_id": (
                        None if counter_batch_id is None else str(counter_batch_id)
                    ),
                    "job": None if actor is not None else "payments.record",
                    # CR-174-BRC10 — where an agent's customer stood, and which
                    # machine. Absent (None) on every other recording.
                    "channel": channel,
                    "terminal": terminal,
                    # DEF-PAY-9263 · BR-PAY-1199 — the clerk saw "Looks like a
                    # duplicate" naming this earlier payment and pressed
                    # *Record anyway*. Absent on every other recording.
                    **(
                        {
                            "duplicate_warning_overridden": True,
                            "possible_duplicate_of": resembles,
                        }
                        if resembles is not None
                        else {}
                    ),
                },
            )

            # ── CR-186-BRC10 · APPLIED AND JOURNALLED AT POSTING ────────────
            # Dated the POSTING date, forwarded out of a closed period
            # (BR-TEN-038, PO 2026-10-21 ruling 3 "Option B - accept it").
            entry_on, forwarded = ledger_seam.entry_date_for_posting(posted_at.date())
            recorded = _allocate_and_post(
                actor=actor,
                payment=payment,
                account=account,
                linkage=linkage,
                order=order,
                targets=targets,
                class_order=class_order,
                entry_on=entry_on,
                posted_at=posted_at,
                reason_code=reason_code,
                already_posted_source=already_posted_source,
            )
            if stamped.batch is not None:
                # Re-footed under a row lock on the batch, so two payments
                # posting into one channel-day at once both land in its total
                # (READ COMMITTED: the second waits, then sums what committed).
                reconciliation.refresh_batch_total(
                    type(stamped.batch).objects.select_for_update().get(pk=stamped.batch.pk)
                )
            recorded = replace(
                recorded,
                deposit_batch_id=None if stamped.batch is None else str(stamped.batch.pk),
                deposit_batch_code=None if stamped.batch is None else stamped.batch.code,
                problems=recorded.problems
                + (() if forwarded is None else (forwarded,))
                + (
                    ()
                    if stamped.batch is not None or stamped.deferred_reason == "not_bankable_money"
                    else (
                        {
                            "code": "deposit_batch_deferred",
                            "br_ref": "BR-PAY-025",
                            "reason": stamped.deferred_reason,
                            "detail": "this payment joined no deposit batch yet: its day's "
                            "batch is already matched or reconciled, or it is a cheque that "
                            "may not be banked until a later date. The nightly cut banks it.",
                        },
                    )
                ),
            )

            # ── CR-059 CS-23 · the plan instalment, in THIS transaction ─────
            recorded = _meet_installment(
                actor=actor,
                payment=payment,
                account=account,
                linkage=linkage,
                posted_at=posted_at,
                # CR-186-BRC10 — every payment is applied at posting.
                cleared=True,
                installment_seq=installment_seq,
                recorded=recorded,
            )

            # ── BR-PAY-024 behind BR-NOT-022's election (CR-009 C-13,
            # 2026-08-18) — the receipt, queued INSIDE this transaction so it
            # can never point at a payment that rolled back. `receipts` returns
            # outcome rows and never raises through the money path: a failed
            # receipt must never fail the payment it describes.
            from apps.payments import receipts  # local: keeps the seam one-way

            # CR-169-BRC10 §2 row 9 — registered INSIDE the transaction so a
            # payment that rolls back sends nothing, and RUN after it commits so
            # no network call is made while this money transaction holds its
            # locks. The tender's code, the purpose and whether it cleared —
            # never the amount, the account or the confirmation number.
            from config import product_analytics

            product_analytics.capture_after_commit(
                "payment_recorded",
                tenant_id=payment.tenant_id,
                actor_id=product_analytics.actor_id_of(actor),
                properties={
                    "method": None if method is None else str(method.code),
                    "purpose": str(purpose),
                    "payment_type": str(payment_type),
                    "cleared": False,
                    "status": models.PAYMENT_POSTED,
                },
                dedupe_key=str(payment.pk),
            )

            # ⚠ `recorded` AND `account` ADDED 2026-09-07 (`DEF-PAY-4409`).
            # Until today this call passed the payment alone, so the receipt was
            # queued with NO render context and every figure on it printed the
            # named absence `——` — the amount, the date, the method, the
            # confirmation number and both balances. The two facts a receipt
            # needs that the payment row does not carry are the bills this money
            # met and the account's number, and BOTH are already in hand right
            # here: passing them costs no query and is the whole fix.
            return replace(
                recorded,
                problems=recorded.problems
                + receipts.queue_receipt_for_recorded_payment(
                    payment=payment, recorded=recorded, account=account, actor=actor
                ),
            )
    except IntegrityError:
        # The race the unique index exists for (BR-PAY-028): another request
        # recorded this same key between our SELECT and our INSERT. A lost race
        # and a replay are the same fact — one payment exists, ours is not it.
        winner = _existing(tenant_id, key)
        if winner is None:
            raise
        return _replayed(winner)


def _meet_installment(
    *,
    actor: Any,
    payment: models.Payment,
    account: Any,
    linkage: purposes.PurposeLinkage,
    posted_at: datetime,
    cleared: bool,
    installment_seq: int | None,
    recorded: RecordedPayment,
) -> RecordedPayment:
    """CR-059 CS-23 — the plan instalment this payment met, or why it met none.

    Inside `record_payment`'s transaction, exactly like `_allocate_and_post`,
    and split out for readability only. It is NOT a second transaction boundary
    and must never be called from anywhere else.

    **It moves no money.** The allocator has already placed every cent; what
    this records is which dated obligation of the schedule the payment
    discharged and when it POSTED. So it can neither double-count nor change a
    figure — it changes whether a customer is chased and whether their plan is
    finished, which is why it writes an audit row (hard rule 7).

    THREE KINDS OF MONEY ARE EXCLUDED, and each says so on the result rather
    than being quietly skipped:

      * a **DEPOSIT** (`linkage.allocates` False) — money the utility HOLDS. It
        meets no bill (US-PAY-002 TC-1) and it discharges no promise to pay.
      * a **DOWN PAYMENT** (`linkage.plan` set — the only purpose the
        `ck_payments_plan_only_on_plan_down` constraint lets carry a plan). The
        schedule is `(total − down) ÷ n` (BR-CUS-043), i.e. what remains AFTER
        the down payment, so marking instalment 1 with it would take the same
        $36.22 from the customer twice.
      * a **PROCESSING** payment — no clearing date, so the money has not
        arrived. It meets no bill for that reason and it meets no instalment for
        the same one: pausing the collection ladder on an uncleared cheque is
        the shape of mistake this path already refuses one table along. ⚠ Its
        POSTING date would still have counted for on-time-ness (BR-PAY-021), and
        nothing in this product links an instalment when a payment later clears
        — so this case is REPORTED by name and is a live gap, not a silence.

    The exclusions cost one extra plan lookup and only for those three cases:
    an account with no live plan gets no `problems` row at all, because an
    absence reported on every payment of every ordinary account is noise, and
    noise is how a real code stops being read.
    """
    excluded: dict[str, str] | None = None
    if not linkage.allocates:
        excluded = {
            "code": plans.INSTALLMENT_NOT_A_SCHEDULE_PAYMENT,
            "br_ref": "BR-PAY-012",
            "detail": "a DEPOSIT is money the utility holds for the customer, not money they "
            "have paid: it meets no bill (US-PAY-002 TC-1) and it discharges no instalment of "
            "their payment plan either. The schedule is unchanged.",
        }
    elif linkage.plan is not None:
        excluded = {
            "code": plans.INSTALLMENT_NOT_A_SCHEDULE_PAYMENT,
            "br_ref": "BR-CUS-043",
            "detail": "this is the plan's DOWN PAYMENT (purpose `plan_down`, BR-PAY-012). The "
            "instalment schedule is what remains AFTER the down payment — BR-CUS-043 spreads "
            "`(total − down) ÷ n` — so no instalment was marked by it. Marking one would take "
            "the same money from the customer twice.",
        }
    elif not cleared:
        excluded = {
            "code": plans.INSTALLMENT_NOT_CLEARED,
            "br_ref": "BR-PAY-021",
            "detail": "the payment carries no clearing date, so it is `processing`: the money "
            "has not arrived. It meets no bill and no plan instalment — pausing the collection "
            "ladder on an uncleared payment would stop chasing a debt nothing has settled. Its "
            "POSTING date is what will decide on-time-ness (BR-PAY-021) when it clears.",
        }

    if excluded is not None:
        # Only speak up where there is a schedule to speak about.
        if plans.live_plan_for(account.pk) is None:
            return recorded
        return replace(recorded, problems=recorded.problems + (excluded,))

    try:
        # ── CLAUDE.md law 14 — a SAVEPOINT, and it is not the tidy option ────
        # On PostgreSQL one failed statement aborts the WHOLE transaction: every
        # later query raises `InFailedSqlTransaction` and the payment is lost at
        # COMMIT even though it was written. A bare `try/except` here would pass
        # the entire suite — `config/settings/test.py` hardcodes in-memory
        # SQLite, which has no aborted-transaction state — and would lose a
        # customer's money the first time a plan row refused in production. The
        # nested `atomic()` is a SAVEPOINT: the link rolls back to it and the
        # payment, its allocations and its journal entry survive.
        with transaction.atomic():
            link = plans.link_payment_to_installment(
                actor=actor,
                account_id=account.pk,
                amount=payment.amount,
                payment_id=payment.pk,
                # BR-PAY-021 / BR-TEN-043 — the payment's OWN posting date, an
                # argument the caller supplied. No clock is read on this path.
                posted_on=posted_at.date(),
                seq=installment_seq,
            )
    except DatabaseError as failure:
        # A bad INSTRUCTION (an instalment seq that is not on this plan) raises
        # `PaymentRuleError` and is NOT caught here: it rolls the whole payment
        # back with nothing written, because a clerk who named the wrong row
        # must be told before the money is taken. What IS caught is the database
        # refusing the link itself — the payment is real, the customer handed it
        # over, and it must not bounce because a schedule row was unavailable.
        # The failure is REPORTED by name so the gap is visible on the receipt
        # rather than looking like a payment that met no instalment.
        return replace(
            recorded,
            problems=recorded.problems
            + (
                {
                    "code": plans.INSTALLMENT_LINK_FAILED,
                    "br_ref": "BR-CUS-043",
                    "detail": "the payment is recorded, allocated and in the books, and the "
                    f"plan instalment could NOT be marked: {failure}. The plan will read as "
                    "behind until the instalment is linked, so this needs a person.",
                },
            ),
        )

    return replace(
        recorded,
        plan_id=link.plan_id,
        plan_status=link.plan_status,
        installment_seq=link.seq,
        installment_on_time=link.on_time,
        problems=recorded.problems + link.problems,
    )


def record_concession_credit(
    actor: Any,
    *,
    account_id: Any,
    amount: Decimal,
    reason_code: str,
    on_date: date,
    currency: str | None = None,
    memo: str | None = None,
    source_reference: Any = None,
) -> RecordedPayment:
    """CR-059 CS-38 — a goodwill concession becomes VISIBLE account credit.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE CUSTOMER WAS TOLD IN WRITING. THIS IS THE HALF THAT MAKES THE   ║
    ║  BALANCE AGREE WITH THE LETTER.                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    Billing raises a goodwill concession, posts it correctly (DR write-off / CR
    customer credit balance, PO 2026-08-12) and queues an email telling the
    customer they have been given the money. Until this function existed
    **nothing on the payments side knew**: the account's credit position read
    0.00, the next bill was calculated without it and the collection ladder
    chased the whole amount. CS-38 is the only item in CR-059 where the customer
    has been told something in writing that the system then contradicts.

    **NO FIGURE MOVES. ❄️ GT-6's 222.30 IS REACHED, NOT CHANGED.** Worked on its
    own frozen shape — a **25.00** concession against a **247.30** bill:

        credit note      −25.000000, against that bill, unchanged
        ledger           ONE entry: DR write-off 25.00 / CR customer credit 25.00
        payments row     a CREDIT of 25.0000, cleared, posting NOTHING
        account credit   0.00  →  **25.0000**
        the bill         **247.30**, untouched (hard rule 4)
        what is owed     247.30 − 25.00 = **222.30**

    ⚠ **THE CREDIT CARRIES; IT DOES NOT MEET THE BILL IT CAME FROM, AND THAT IS
    `OQ-215` BEING RESPECTED RATHER THAN A PREFERENCE.** That row asks whether a
    class-C concession moves THIS bill's balance to 222.30 or is an
    account-level credit consumed by the NEXT bill, notes that GT-6's 222.30 is
    reached either way, and says in as many words that it *"needs one sentence
    from the PO and is not a thing an implementer may pick"*. `apps/billing/
    corrections.py` implements the second reading — `build_impact` forces the
    class-C bill delta to ZERO — so this function allocates with
    `ORDER_CARRY_CREDIT`, which touches no bill at all. Recording it
    oldest-first would have settled 25.00 of the source bill and quietly decided
    OQ-215 in favour of the first reading, on a money path, with no ruling.

    So the credit sits on the account and billing's **existing** draw-down
    (`credit.apply_credit_at_issue`, called from the issue path) consumes it at
    the next bill — which is exactly the PO's own OQ-105 sentence: *"it is new
    good will credit to be applied in new bill"*.

    **IT POSTS NOTHING** (`already_posted_source="credit_note"`). See the
    one-posting fork in `_allocate_and_post` for why, and for what is asserted.

    **IDEMPOTENCY IS THE CREDIT NOTE'S** (hard rule 6). `source_reference` is
    the credit note's id, so a correction replayed after a crash finds the
    payment row it already wrote and returns it with `created=False`. Passing
    None is lawful and is the caller saying it owns no stable key — then a
    replay writes a second credit row, which is why `corrections.py` always
    passes one.

    Raises `PaymentRuleError` for everything a human can act on.
    """
    return record_payment(
        actor,
        account_id=account_id,
        amount=amount,
        # BOTH dates are the correction's own business date (BR-TEN-043 — no
        # clock on this path). A concession is "cleared" the moment it is
        # granted: there is no bank and nothing to wait for, and a `processing`
        # credit would meet no bill and count toward no credit position, which
        # is the state this whole change exists to end.
        posted_at=_moment(on_date),
        cleared_at=_moment(on_date),
        currency=currency,
        # No tender: a credit carries no instrument (B2 §2 leaves `method`
        # nullable for exactly these rows), and a tenderless row cannot be
        # grouped into a drawer batch even if the type filter were removed.
        method_code=None,
        memo=memo,
        purpose=models.PURPOSE_BILL,
        order=ORDER_CARRY_CREDIT,
        payment_type=models.PAYMENT_TYPE_CREDIT,
        reason_code=reason_code,
        already_posted_source="credit_note",
        idempotency_source=idempotency.SOURCE_ENTRY,
        idempotency_reference=(
            None if source_reference is None else f"credit_note|{source_reference}"
        ),
    )


def _moment(on_date: date) -> datetime:
    """A business DATE as the instant this module stores dates at.

    Midnight UTC, the same convention `apps/payments/api.py` applies to a
    user-entered date, and the same open question rides with it: WHICH instant a
    calendar date becomes, in whose timezone, is `OQ-153` — RAISED, not
    answered. The DATE is preserved either way and that is what BR-PAY-021's
    on-time test reads. Stated here so a reader does not conclude this path
    settled it.
    """
    if isinstance(on_date, datetime):
        return on_date
    return datetime.combine(on_date, time.min, tzinfo=UTC)


def _allocate_and_post(
    *,
    actor: Any,
    payment: models.Payment,
    account: Any,
    linkage: purposes.PurposeLinkage,
    order: str,
    targets: tuple[Any, ...],
    class_order: tuple[str, ...] | None,
    entry_on: date,
    posted_at: datetime,
    reason_code: str | None = None,
    already_posted_source: str | None = None,
) -> RecordedPayment:
    """Steps 3–5, inside `record_payment`'s transaction.

    `entry_on` is the date the journal entry is booked on — the payment's
    posting date, forwarded out of a closed period (`CR-186-BRC10`). It was
    the CLEARING date until 2026-10-21.

    Split out for readability only — it is NOT a second transaction boundary and
    must never be called from anywhere else. If the posting refuses, the payment
    row created above rolls back with it, which is the whole point: money in the
    system that never reached the books is the state nothing can repair, because
    the payment row is immutable the instant it commits.

    The tenant's class order is resolved HERE rather than in `record_payment`,
    so a PROCESSING payment — one that returns before this function, having met
    no bill — never needs the setting at all. It is read once and the sequence
    that was actually used is what the audit row records.
    """
    if not linkage.allocates:
        # BR-PAY-012 / US-PAY-002 TC-1: a DEPOSIT meets no bill and becomes no
        # credit. It is money the utility HOLDS, so the only leg it has is the
        # deposit liability — and it is deliberately posted through the same
        # seam every other payment uses rather than through a second path, so
        # one function remains the only place payments asks the ledger for an
        # entry (CLAUDE.md rule 5).
        return _hold_and_post(
            actor=actor,
            payment=payment,
            linkage=linkage,
            entry_on=entry_on,
            posted_at=posted_at,
        )

    class_order = tenant_class_order() if class_order is None else tuple(class_order)
    position = billing_seam.open_invoices_for_account(account.pk)

    try:
        outcome = allocate_payment(
            payment_amount=payment.amount,
            open_invoices=position.invoices,
            order=order,
            targets=targets,
            class_order=class_order,
        )
    except AllocationClassNotConfigured as refusal:
        # DEF-047's lesson, applied across a boundary inside this module.
        # `allocation.py` is a PUBLISHED PURE CALCULATION with its own error
        # vocabulary — this one says the TENANT has not defined the fourth
        # class the PO ruled in on 2026-08-11 (OQ-109), which is a
        # CONFIGURATION fact and not a bad argument. A caller catching only
        # `PaymentRuleError` would miss it and a bulk import would lose its
        # batch over one bill, so it is translated rather than left to escape.
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-038") from refusal
    except (ValueError, TypeError) as refusal:
        # The allocator's input refusals — a mixed dated/undated list, a partial
        # composition, an unknown order, a split whose rows do not sum to the
        # payment. Every one of them names the rule it is protecting; none of
        # them should reach a clerk as a raw ValueError.
        raise PaymentRuleError(str(refusal), br_ref="BR-PAY-010") from refusal

    by_number = {invoice.number: invoice for invoice in position.invoices}
    rows: list[dict[str, Any]] = []
    for allocation in outcome.allocations:
        invoice = by_number[allocation.invoice_number]
        row = models.Allocation.objects.create(
            tenant_id=payment.tenant_id,
            payment=payment,
            invoice_id=invoice.invoice_id,
            amount=allocation.applied,
        )
        # ⚠ **CR-060 C19 / task T7d — THE BREAKDOWN IS NOW A STORED FACT.**
        # It was computed on every allocation since the PO's ruling of
        # 2026-08-11 and had nowhere to live but the audit payload, which is
        # pruned on a retention schedule — so the *collected* tax basis a tenant
        # may already choose to file on could not be produced, and
        # `ledger.reporting.remittance_by_authority` reported it absent with its
        # reason. `allocation_classes` (payments/0015) is the child row per
        # class, written HERE, inside the same transaction as its parent: a
        # breakdown that could be written a moment later is a breakdown that can
        # be missing, and this is money a tax return is filed from.
        #
        # **ONLY CLASSES THAT RECEIVED MONEY GET A ROW**, which is
        # `Allocation.by_class`'s own rule one level up: a class the payment
        # never reached and a class it paid 0.00 are different facts and only
        # the first one exists.
        #
        # **AND THIS ADJUDICATES NOTHING.** Two signed rulings disagree about
        # how a partial payment meets tax (OQ-174's *"tax first"* against
        # BR-PAY-010's tenant-set order); CR-060 C19 rules that recording the
        # breakdown *"makes the question moot"* rather than picking a winner.
        # Whatever `class_order` this tenant chose is what the allocator walked,
        # and what it met is what lands below.
        models.AllocationClass.objects.bulk_create(
            [
                models.AllocationClass(
                    tenant_id=payment.tenant_id,
                    allocation=row,
                    line_class=entry.line_class,
                    amount=entry.applied,
                )
                for entry in allocation.by_class
            ]
        )
        rows.append(
            {
                "invoice_id": str(invoice.invoice_id),
                "invoice_number": allocation.invoice_number,
                "amount": allocation.applied,
                # The within-invoice breakdown the PO ruled in on 2026-08-11.
                # ⚠ It has a column of its own since 2026-09-02 (CR-060 T7d,
                # `allocation_classes`) and it is STILL written here as well:
                # the audit row is what a person reads on S61 and the table is
                # what a report queries, and the two are written from the one
                # `by_class` tuple in the one transaction, so they cannot
                # disagree. This comment read *"the audit payload is the only
                # place it is recorded"* until the table landed.
                "by_class": {entry.line_class: str(entry.applied) for entry in allocation.by_class},
            }
        )

    applied = sum((row["amount"] for row in rows), ZERO)
    core_audit.money_action(
        actor,
        AUDIT_ALLOCATED,
        "payment",
        str(payment.pk),
        after={
            "payment_no": payment.payment_no,
            "order": order,
            "class_order": list(class_order),
            "applied": str(applied),
            "credit_carried": str(outcome.credit_carried),
            "remaining_balance": str(outcome.remaining_balance),
            "allocations": [
                {**row, "amount": str(row["amount"])} for row in rows  # money as text in the trail
            ],
            "remaining_by_class": {
                entry.line_class: str(entry.balance) for entry in outcome.remaining_by_class
            },
            "job": None if actor is not None else "payments.record",
        },
    )

    # ══════════════════════════════════════════════════════════════════════
    # CR-059 CS-38 · THE ONE-POSTING FORK — SETTLED HERE, ONCE
    # ══════════════════════════════════════════════════════════════════════
    # CS-38 leaves the build one thing to decide and says to write it down:
    # *"either payments' row is marked non-posting, or the concession moves to
    # posting through payments entirely and billing's credit note stays as the
    # document. Decide it once, write it in the docstring, and assert the ledger
    # totals either way; a double post here is a real 25.00 of invented money."*
    #
    # **DECIDED: PAYMENTS' ROW IS NON-POSTING WHEN THE CALLER NAMES THE RECORD
    # THAT ALREADY POSTED IT** (decision log 2026-09-02). Three reasons, in the
    # order they weighed:
    #
    #   1. **Billing's entry is the RULED one and it already exists.** PO
    #      2026-08-12 (OQ-105/OQ-168) put a concession at DR write-off / CR
    #      customer credit balance and `corrections.execute_credit_only` has
    #      emitted exactly that pair ever since. Moving the posting here would
    #      reverse a ruling nobody asked to reverse.
    #   2. **The GL reports read the posting's SOURCE TYPE**, not the credit-note
    #      table (CR-059 §7). Posting here would file new concessions under
    #      `payment` and historic ones under `credit_note` — one event, two
    #      shapes, forever, on rows hard rule 4 forbids anyone from going back
    #      and fixing.
    #   3. **It is the shape this module already has.** `credit.
    #      apply_credit_at_issue` draws a customer's credit down against a new
    #      bill by writing ALLOCATION ROWS AND POSTING NOTHING, because the money
    #      reached the books when it arrived. A concession is the same fact
    #      arriving by a different door.
    #
    # **WHAT IS ASSERTED RATHER THAN PROMISED** (hard-won law 1): the ledger
    # carries a 25.00 concession exactly ONCE — one entry, `source_type
    # credit_note`, two lines, 25.00 either side — and this path adds no
    # `source_type payment` entry at all. `tests/test_cr059_cs35_cs38_credit_
    # rows.py` counts both.
    if already_posted_source is not None:
        return RecordedPayment(
            payment_id=str(payment.pk),
            payment_no=payment.payment_no,
            created=True,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            applied=applied,
            credit_carried=outcome.credit_carried,
            allocations=tuple(rows),
            journal_entry_id=None,
            posted_to_ledger=False,
            problems=RECORD_UNAVAILABLE
            + (
                {
                    "code": "posted_by_another_record",
                    "br_ref": "BR-BIL-011",
                    "detail": f"this {payment.type} posts nothing: the balanced entry for it "
                    f"was already written by the {already_posted_source} it came from, and a "
                    "second entry here would be money the utility never gave away (CR-059 "
                    "CS-38). The row's job is the balance a customer and a clerk read; the "
                    "books already have this amount.",
                },
            ),
        )
    if payment.type in NON_CASH_TYPES:
        # CS-35 branch 2 — its own GL account, never undeposited funds. The
        # credit legs are the same two `post_payment_cleared` writes, because a
        # credit meets bills exactly as a payment does; only the debit differs.
        posting = ledger_seam.post_credit_adjustment(
            payment=payment,
            reason_code=reason_code or "",
            applied_to_bills=applied,
            credit_carried=outcome.credit_carried,
            # A credit has no bank, so there is no bank date to book it on. Both
            # dates are the caller's own and neither is a clock (BR-TEN-043).
            entry_date=entry_on,
            posted_at=posted_at,
            actor=actor,
        )
        payment.journal_entry_id = posting.entry_id
        payment.save(update_fields=["journal_entry_id", "updated_at"])
        return RecordedPayment(
            payment_id=str(payment.pk),
            payment_no=payment.payment_no,
            created=True,
            status=payment.status,
            amount=payment.amount,
            currency=payment.currency,
            applied=applied,
            credit_carried=outcome.credit_carried,
            allocations=tuple(rows),
            journal_entry_id=posting.entry_id,
            posting_key=posting.posting_key,
            posted_to_ledger=True,
        )

    posting = ledger_seam.post_payment_cleared(
        payment=payment,
        applied_to_bills=applied,
        credit_carried=outcome.credit_carried,
        # CR-186-BRC10 (PO 2026-10-21): the POSTING date, forwarded out of a
        # closed period. The bank's date belongs to the reconciliation entry,
        # which moves this money from the holding account to the bank.
        entry_date=entry_on,
        # BR-TEN-043: the caller names the moment. This is the payment's own
        # posting moment — the ledger's `posted_at` word for word — never a clock.
        posted_at=posted_at,
        actor=actor,
        # CR-008 B-10 (OQ-264 CLOSED): a mapped tender's money holds in ITS
        # clearing account until the bank confirms it; unmapped = undeposited,
        # today's behaviour. A dead mapping refuses INSIDE this transaction,
        # so the payment rolls back whole rather than landing unbooked.
        clearing_account_id=ledger_seam.tender_clearing_account_id(payment),
    )

    # ── the WRITE-ONCE ledger stamp (US-PAY-009, migration 0006) ─────────────
    # The entry names this payment as its `source_id`, so it cannot exist until
    # the row does — the stamp therefore lands microseconds later, inside this
    # same transaction, on a row that is already `cleared`.
    #
    # It exists for ONE reason: when this payment bounces, `apps/ledger/posting.
    # reverse_entry` needs an ENTRY ID to mirror, and the ledger publishes no
    # read that turns a posting key or a `(source_type, source_id)` pair back
    # into one. Without it a bounce three weeks later could not name the entry it
    # must unwind, and the only alternatives were hand-composing a compensating
    # entry (BR-LED-003 forbids it) or leaving BR-PAY-013 wired to nothing.
    #
    # The trigger allows NULL -> set and nothing else; a re-point raises. A
    # replay (`created=False`) stamps the SAME id the first call did, so this is
    # idempotent by construction rather than by a branch.
    payment.journal_entry_id = posting.entry_id
    payment.save(update_fields=["journal_entry_id", "updated_at"])

    return RecordedPayment(
        payment_id=str(payment.pk),
        payment_no=payment.payment_no,
        created=True,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        applied=applied,
        credit_carried=outcome.credit_carried,
        allocations=tuple(rows),
        journal_entry_id=posting.entry_id,
        posting_key=posting.posting_key,
        posted_to_ledger=True,
        problems=RECORD_UNAVAILABLE + position.problems + linkage.problems,
    )


def _hold_and_post(
    *,
    actor: Any,
    payment: models.Payment,
    linkage: purposes.PurposeLinkage,
    entry_on: date,
    posted_at: datetime,
) -> RecordedPayment:
    """The DEPOSIT path — money held, not applied (US-PAY-002 TC-1).

    Inside `record_payment`'s transaction, exactly like `_allocate_and_post`,
    and for the same reason: a deposit row that committed without its entry
    would be money in the product and not in the books.

    NO `allocations` ROW IS WRITTEN and none is possible — the money met no
    bill. NO CREDIT IS CARRIED either, which is the half a reader is most
    likely to get wrong: `selectors.account_credit_position` EXCLUDES
    deposit-purpose payments, because a deposit that read as credit would
    auto-apply to the next bill and the utility would spend money it is holding
    for the customer.
    """
    posting = ledger_seam.post_payment_cleared(
        payment=payment,
        applied_to_bills=ZERO,
        credit_carried=ZERO,
        deposit_taken=payment.amount,
        entry_date=entry_on,
        posted_at=posted_at,
        actor=actor,
        # CR-008 B-10: a deposit handed over by a mapped tender holds in that
        # tender's clearing account too — the DEBIT side is the same
        # undeposited/clearing question every receipt has (the OQ-177 caveat
        # in GL_DEPOSIT_LIABILITY's note is about the CREDIT side, untouched).
        clearing_account_id=ledger_seam.tender_clearing_account_id(payment),
    )
    payment.journal_entry_id = posting.entry_id
    payment.save(update_fields=["journal_entry_id", "updated_at"])

    # ── BR-CUS-670 · THE REGISTER, MOVED BY THE SAME CLEARED AMOUNT (DEF-177) ─
    # INSIDE this transaction and AFTER the posting, for the reason the NSF
    # count is (`reversal._record_nsf`): the register states money that is in
    # the books. Before today the 2300 deposit liability rose here and NOTHING
    # wrote `accounts.deposit_on_file`, so the first utility to take a $150.00
    # deposit got *books $150.00 / register $0.00* on the S36 tie-out and
    # BR-LED-007 blocked their release.
    #
    # ⚠ **CUSTOMERS WRITES IT, NOT PAYMENTS** — `accounts` is customers' table
    # and payments may not write another module's (B1 / DB-16), so the writer is
    # resolved BY NAME, exactly as `record_nsf` is.
    register, register_problems = _move_deposit_register(
        account_id=payment.account_id,
        amount=payment.amount,
        received_on=posted_at.date(),
        actor=actor,
    )
    # ── CR-048 wave B task B11 · THE CUSTOMER IS TOLD ───────────────────────
    # `catalogs.LISTINGS["email_deposit"]` has read *"Not in use yet —
    # recording a deposit does not send this."* since 2026-08-16. It sends now.
    # The seam runs its write inside its OWN savepoint and raises nothing, so a
    # letter that cannot be queued can neither roll back this transaction nor
    # abort it (CLAUDE.md law 14 — a `try` alone would do exactly that on
    # PostgreSQL and pass the whole suite on SQLite).
    deposit_notice = _queue_deposit_notice(
        payment=payment,
        received_on=posted_at.date(),
        held_after=None if register is None else register.held_after,
        actor=actor,
    )
    return RecordedPayment(
        payment_id=str(payment.pk),
        payment_no=payment.payment_no,
        created=True,
        status=payment.status,
        amount=payment.amount,
        currency=payment.currency,
        applied=ZERO,
        credit_carried=ZERO,
        deposit_held_after=None if register is None else register.held_after,
        journal_entry_id=posting.entry_id,
        posting_key=posting.posting_key,
        posted_to_ledger=True,
        problems=(RECORD_UNAVAILABLE + linkage.problems + register_problems + deposit_notice),
    )


# ══════════════════════════════════════════════════════════════════════════
# CR-048 WAVE B TASK B11 — THE DEPOSIT CONFIRMATION
# ══════════════════════════════════════════════════════════════════════════
#: The notifications entry point, resolved BY NAME (B1 — payments imports
#: nothing of notifications'). It lives in `customer_events` beside the move
#: letters rather than in this module, because the MESSAGE is account-lifecycle
#: correspondence even though the MOMENT is a payment: `catalogs.LISTINGS
#: ["email_deposit"].category` is CAT_ACCOUNT_LIFECYCLE, and the source kind is
#: chosen from what the document is, not from who wrote it.
DEPOSIT_NOTICE_MODULE = "notifications"
DEPOSIT_NOTICE_KIND = "customer_events"
DEPOSIT_NOTICE_WRITE = "queue_deposit_received"

DEPOSIT_NOTICE_QUEUED = "deposit_notice_queued"
DEPOSIT_NOTICE_ALREADY_QUEUED = "deposit_notice_already_queued"
DEPOSIT_NOTICE_SUPPRESSED = "deposit_notice_suppressed_by_rule"
DEPOSIT_NOTICE_UNAVAILABLE = "deposit_notice_unavailable"
DEPOSIT_NOTICE_ERROR = "deposit_notice_error"


def _queue_deposit_notice(
    *, payment: Any, received_on: Any, held_after: Any, actor: Any
) -> tuple[dict[str, Any], ...]:
    """ONE letter when a deposit clears. Outcome rows, and it raises nothing.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE IDEMPOTENCY TUPLE IS (tenant, "account", PAYMENT id, email, 0)  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    **The payment that cleared, and never the account.** A customer can be asked
    for a second deposit — after a disconnection and reconnection, or when a
    plan is re-cut — and the SAME account also owns the account-closed
    confirmation and every rate-plan letter on this same source kind. Keyed on
    the account, the second deposit letter would find one of those, return
    `created=False`, and the customer would never be told their money arrived.
    That is DEF-2512's mechanism and the reason the kind exists at all.
    A payment row is one per deposit, so a replayed `record_payment` finds its
    own letter and writes nothing (rule 6).

    ⚠ **NO PRINT FLOOR.** `account` is not one of BR-NOT-024's four kinds, so a
    utility that switches *Deposit received* off gets no row — the ruled
    behaviour, and the reason travels back on `problems` rather than the letter
    quietly not existing.

    ⚠ **THE FIGURES ARE THE ONES THAT MOVED THE BOOKS AND THE REGISTER**, as
    strings already finalised (CLAUDE.md rule 2). `amount` is what CLEARED, not
    what any schedule required; `balance` is the register's position after the
    movement, so the letter and the S36 tie-out cannot state different totals.
    """
    from importlib import import_module

    try:
        target = import_module(f"apps.{DEPOSIT_NOTICE_MODULE}.{DEPOSIT_NOTICE_KIND}")
    except ImportError:  # pragma: no cover - notifications ships in this repo
        target = None
    write = getattr(target, DEPOSIT_NOTICE_WRITE, None) if target else None
    if not callable(write):
        return (
            {
                "code": DEPOSIT_NOTICE_UNAVAILABLE,
                "br_ref": "BR-CUS-670",
                "detail": f"apps.{DEPOSIT_NOTICE_MODULE}.{DEPOSIT_NOTICE_KIND}."
                f"{DEPOSIT_NOTICE_WRITE} is not published, so the customer has NOT been "
                "told their deposit was received. The deposit itself stands.",
            },
        )
    try:
        # ⚠ THE SAVEPOINT IS THE POINT (CLAUDE.md law 14). This runs INSIDE the
        # money transaction, and on PostgreSQL a statement that errors inside a
        # transaction aborts it — the `except` would catch the exception, the
        # payment's own INSERT would already be doomed, and the COMMIT would
        # fail afterwards with "current transaction is aborted". SQLite has no
        # such state, so the version without this line passes the whole suite.
        with transaction.atomic():
            # CR-190-BRC10 (DEF-NOT-10441) — money as a VALUE with its currency,
            # never a pre-written string (PO 2026-10-22: *"Callers pass money as
            # a value plus currency"*); `str(payment.amount)` printed `45.0000`.
            # `balance` is what the ACCOUNT owes after this deposit, from the
            # books (`receipts._ar_balance`, DEF-127's one derivation) — the
            # body says *"Your account balance is still {balance}"*, which the
            # deposit register's `held_after` never was.
            from apps.payments import receipts as _receipts

            message = write(
                payment_id=payment.pk,
                account_id=payment.account_id,
                received_on=received_on,
                amount=payment.amount,
                held_after=held_after,
                balance=_receipts._ar_balance(payment.account_id),
                currency=getattr(payment, "currency", None),
                actor=actor,
                job=None if actor is not None else "payments.record",
            )
    except Exception as failure:  # noqa: BLE001 — the one boundary where broad is right
        return (
            {
                "code": DEPOSIT_NOTICE_ERROR,
                "br_ref": "BR-CUS-670",
                "detail": f"the deposit confirmation could not be queued: {failure} The "
                "deposit stands — a failed notification must never fail the money it "
                "describes.",
            },
        )
    problems = tuple(getattr(message, "problems", ()) or ())
    if getattr(message, "message_id", None) is None:
        return (
            {
                "code": DEPOSIT_NOTICE_SUPPRESSED,
                "br_ref": "BR-NOT-017",
                "detail": "no deposit confirmation was queued because this utility's own "
                "notification rule left no channel, and an account-lifecycle message has "
                "no print floor to keep one (BR-NOT-024 names four source kinds and this "
                "is not one). The deposit was recorded normally.",
            },
            *problems,
        )
    created = bool(getattr(message, "created", False))
    return (
        {
            "code": DEPOSIT_NOTICE_QUEUED if created else DEPOSIT_NOTICE_ALREADY_QUEUED,
            "br_ref": "BR-CUS-670",
            "message_id": str(message.message_id),
            "event_key": getattr(message, "event_key", None),
            "detail": "the deposit confirmation is on the platform outbound queue for "
            "this payment. Queueing is not sending: nothing dispatches in this release "
            "(BR-NOT-013).",
        },
        *problems,
    )


#: The customers writer this module asks for the register move, named once so
#: the contract is greppable from BOTH sides of the boundary (BR-TEN-013) — the
#: precedent `purposes.DEPOSIT_POSITION_READ` and `reversal._record_nsf` set.
DEPOSIT_REGISTER_WRITE = "record_deposit_movement"

#: Carried when customers publishes no writer. **An unwired seam REPORTS; it
#: never answers zero** (G20): a silent no-op here would leave the money in the
#: books and out of the register, which is DEF-177 exactly.
DEPOSIT_REGISTER_UNWIRED = {
    "code": "deposit_register_not_moved",
    "br_ref": "BR-CUS-670 · BR-LED-007 · DEF-177",
    "detail": "the deposit is recorded and the 2300 deposit-liability account is credited, "
    "and `apps.customers.services.record_deposit_movement` — the writer that keeps the "
    "customer deposit register in step with it — is not published on this deployment. "
    "`accounts` is CUSTOMERS' table and payments may not write another module's (B1 / DB-16). "
    "The S36 tie-out will report the difference by name rather than hide it.",
}


def _move_deposit_register(
    *, account_id: Any, amount: Decimal, received_on: Any, actor: Any, released: bool = False
) -> tuple[Any, tuple[dict[str, Any], ...]]:
    """Ask customers to move the deposit register — the `record_nsf` shape.

    A refusal from customers is NOT swallowed and NOT translated into a problem
    code: it propagates, inside the caller's transaction, so a deposit whose
    register could not be moved is not committed half-done. That is DEF-047's
    lesson and it is the whole point here — a payment that reached the books and
    not the register is the defect, so it must not be able to commit.
    """
    from importlib import import_module

    try:
        customers_services = import_module("apps.customers.services")
    except ImportError:  # pragma: no cover — the app package always imports
        customers_services = None
    fn = getattr(customers_services, DEPOSIT_REGISTER_WRITE, None) if customers_services else None
    if not callable(fn):
        return None, (DEPOSIT_REGISTER_UNWIRED,)
    movement = fn(account_id, amount, actor=actor, received_on=received_on, released=released)
    return movement, ()


# ── the two tenancy seams this module owes (BR-TEN-029/030/034, BR-TEN-042) ──
def payment_method_used_by_count(code: str) -> int:
    """How many payments reference one method code (BR-TEN-029).

    `apps/tenancy/seams.py` has named this function since W0 and answered 0 with
    the honest note *"payments stores no payment rows yet"*. That is no longer
    true, and its own docstring states what the 0 was costing: while the count
    is 0, **BR-TEN-030** (a code freezes once used) and **BR-TEN-034** (a used
    row cannot be deleted) *"cannot bite"* — a tenant could rename or delete a
    method that live payments point at, and the payments would be left naming a
    code that no longer exists.

    Counts EVERY payment, in every status, including reversed ones: a reversed
    payment is still financial history and still names its method.
    """
    return models.Payment.objects.filter(tenant_id=_tenant_id(), method__code=code).count()


def financial_records_exist() -> bool:
    """BR-TEN-042's currency-lock probe: does this tenant hold any payment?

    Once a payment exists the tenant's currency is locked, because changing it
    afterwards would leave `payments.currency` saying one thing and the setting
    another with no path to reconcile them (both tables are append-only).

    ONE row is enough, so this is an `.exists()` rather than a count — the probe
    runs on the settings screen and must not scan a table that grows forever.
    """
    return models.Payment.objects.filter(tenant_id=_tenant_id()).exists()


# ══════════════════════════════════════════════════════════════════════════
# US-TEN-019 SAMPLE DATA — payments' block (BR-TEN-056 as AMENDED 2026-08-16)
# ══════════════════════════════════════════════════════════════════════════
# Thin forwarders: the seam contract names the path, G20 harvests it, and the
# implementation lives in `sample_data.py` because it drives the same
# `record_payment` a clerk's click uses.


def seed_sample_records(actor: Any) -> int:
    """June ~95% collected, on one busy day (spec §3/§5 as amended 2026-08-17
    — July is READY-TO-RUN and unbilled, CR-010 Part-10.4)."""
    from apps.payments import sample_data

    return sample_data.seed_sample_records(actor)


def seed_sample_cycle_collections(actor: Any) -> int:
    """THE SECOND CYCLE'S MONEY — PO 2026-09-01, *"after second bill is
    generated, I want to add another step which will add - meter reads and
    payment data"*.

    ⚠ **PUBLISHED HERE BECAUSE A BLOCK NOBODY CAN RESOLVE IS A BLOCK THAT DOES
    NOT RUN** — `seams.resolve` looks in `apps.<module>.services` and never in
    `sample_data`, so a seam written only there is SKIPPED as "not wired" and
    the load reports a healthy tenant with no collections in it. Same three
    lines, same reason, as `seed_sample_refund` above.
    """
    from apps.payments import sample_data

    return sample_data.seed_sample_cycle_collections(actor)


def seed_sample_plan_payments(actor: Any) -> int:
    """The live plan's money — down payment + paid instalments (CR-010
    Part-10.4 amendment 3, PO 2026-08-17). See sample_data."""
    from apps.payments import sample_data

    return sample_data.seed_sample_plan_payments(actor)


def seed_sample_refund(actor: Any) -> int:
    """The seeded REFUND — spec §4 case 14 (CR-040 task D12, PO 2026-08-27).

    ⚠ **PUBLISHED HERE BECAUSE A BLOCK NOBODY CAN RESOLVE IS A BLOCK THAT DOES
    NOT RUN.** `apps.tenancy.sample_data` reaches every block through
    `seams.resolve(module, seam)`, which looks in `apps.<module>.SERVICES` —
    never in `sample_data`. A seam written only in `sample_data.py` resolves to
    None, the orchestrator SKIPS the block as "seam not wired", and the load
    reports a healthy tenant with no refund in it. That is hard-won law 2 in
    its seam form, and it is what this three-line function prevents.
    """
    from apps.payments import sample_data

    return sample_data.seed_sample_refund(actor)


def seed_sample_multi_account_tender(actor: Any) -> int:
    """ONE CHEQUE COVERING THREE PROPERTIES — `CR-059` CS-12, task 74.

    ⚠ **PUBLISHED HERE FOR THE REASON `seed_sample_refund` GIVES DIRECTLY
    ABOVE, AND THIS LANE MET IT AS A RED TEST RATHER THAN AS A DOCSTRING.**
    `apps.tenancy.sample_data` reaches every block through `seams.resolve(module,
    seam)`, which looks in `apps.<module>.SERVICES` and never in `sample_data`.
    Written only in `sample_data.py`, this block resolved to None, the
    orchestrator would have SKIPPED it as *"seam not wired"*, and the load would
    have reported a healthy tenant with no multi-property cheque in it —
    hard-won law 2 in its seam form. `test_the_orchestrator_resolves_every_block_
    it_declares` is what caught it (DEF-930's own guard, doing its job).
    """
    from apps.payments import sample_data

    return sample_data.seed_sample_multi_account_tender(actor)


def remove_sample_records() -> dict[str, Any]:
    """0, and WHY — a payment is append-only (hard rule 4)."""
    from apps.payments import sample_data

    return sample_data.remove_sample_records()


def sample_record_count() -> int:
    from apps.payments import sample_data

    return sample_data.sample_record_count()


def seed_reference_list(list_code: str, entries: list[Any], fixture_version: str) -> int:
    """tenancy's BR-TEN-012/013 reference-seed seam — payments' side (CS-18).

    A thin forward to `apps/payments/lookups.py`, which is where this module's
    lookup handlers and their validation already live. It sits HERE and only
    here because `apps.tenancy.seams.resolve` looks the function up by the fixed
    name `apps.payments.services.seed_reference_list` — the seam is a NAME
    contract, so a lane that put the implementation in the right file and never
    exported it would have a seeder tenancy could not find, and a reference list
    that stayed empty on every tenant with nothing reporting it (DEF-016's exact
    shape, and DEF-026's).

    It raises `KeyError` for every list code payments does not own —
    `payment_methods` included, which tenancy HOSTS — and tenancy catches that
    as "not mine yet" and falls through to the hosted handler exactly as before.
    So adding this function changes nothing about how any existing list seeds.
    """
    from apps.payments import lookups

    return lookups.seed_reference_list(list_code, entries, fixture_version)


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (sha1[:7] of the four sources this slice was authored from, concatenated in order: 04-docs/02-decisions/02-database-design-brief.md — §2 payments DDL + Addenda r12/r14/r16 — · 04-docs/05-modules/08-payments/06-epics/EP-PAY-01-record-payments.md · 04-docs/05-modules/08-payments/02-business-rules.md · 04-docs/05-modules/08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments closed-loop lane — the first write path this module has ever had)
# amended:   2026-08-11 — this file used to hold ONE re-export (`allocate_payment`) and said so: "Today this module holds no write path at all, because this module owns no tables yet." That is now false and the sentence is gone rather than left to rot (hard-won law 1). The re-export is unchanged and `apps.billing.rating_seam` still resolves GT-7 here.
# amended:   2026-08-11 by Eng-Lead (NSF + refunds lane, EP-PAY-03) — THREE CHANGES, each named because this file is on the G7 guard list and DEF-058 is why. (1) THE RECEIPT LEG NOW DEBITS UNDEPOSITED FUNDS, not cash — PO ruling 2026-08-11 closing OQ-143; the amount is unchanged and both accounts are in the ❄️ signed chart, so no figure moved. (2) A WRITE-ONCE `journal_entry_id` STAMP is added after the posting, inside the same transaction: `posting.reverse_entry` takes an entry id and the ledger publishes no key→entry read, so without it a bounce cannot name what it must unwind. (3) `reverse_payment` and the five refund functions are RE-EXPORTED here so B1's one-write-path-per-module still reads true. **The hard-rule-6 pre-insert lookup DEF-058 is about was not touched** — it is byte-identical, and this lane's own idempotency guards live in `reversal.py` with their own tests.
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [D and E CLOSED 2026-08-11 by the payments API lane: apps/payments/api.py serves POST /accounts/{id}/payments + GET /payments and 07-frontend/src/features/payments/ ships S33 and the Record modal]
# gates: ruff✔ black✔ · pytest tests/test_us_pay_001_record_payment.py · pytest tests -m golden (GT-7 unmoved) · pytest tests -m isolation on live Postgres · 10-scripts/03-golden-verify.py · run_gates
# exceptions: (1) THREE OF THE FOUR PURPOSES ARE REFUSED BY NAME — deposit,
#         plan_down and prepay each need a linkage that does not exist
#         (BR-BIL-012's first-bill deposit line · `payment_plans` · US-PAY-007's
#         credit read-model). The reason is carried in the refusal a clerk sees,
#         not only in this trailer.
#         (2) A PROCESSING PAYMENT ALLOCATES AND POSTS NOTHING. The ledger
#         contract row is "Payment CLEARED"; a bill must not leave arrears on an
#         uncleared cheque. The result says so with a code.
#         (3) NO RECEIPT IS QUEUED (BR-PAY-024, EP-PAY-07) and
#         `accounts.balance` IS NOT UPDATED (customers' cached column, B1 —
#         the cache seam is in B2's reviewed set and customers publishes
#         nothing). Both ride every result in RECORD_UNAVAILABLE.
#         (4) THE WITHIN-INVOICE BREAKDOWN HAS NOWHERE TO LIVE. B2 §2 gives
#         `allocations` an amount and no class, so the four-class result rides
#         the `payment.allocated` audit payload — a record, not a queryable
#         position. OQ-129, raised.
#         (5) TWO TENANCY SEAMS ARE NOW LIVE — payment_method_used_by_count and
#         financial_records_exist were documented in apps/tenancy/seams.py and
#         had never been authored; while they answered 0/False, BR-TEN-030 and
#         BR-TEN-034 could not bite for the payment-methods list.
#         (6) NOTHING READS THE ACCOUNT'S STATUS (BR-PAY-036 — "payment is
#         always accepted"), and a test asserts that absence.
#         (7) ADDED 2026-08-12 (tenant-settings lane, PO ruling of that date):
#         `record_payment`'s `class_order` defaults to None = "this tenant's
#         `allocation_class_order` setting", resolved by `tenant_class_order()`.
#         It defaulted to `allocation.DEFAULT_CLASS_ORDER`, so the S22 form and
#         `apps/payments/api.record_payment` — neither of which states an order
#         — allocated EVERY utility's money under the shipped sequence and no
#         tenant's own answer was ever read. The seeded setting IS that same
#         sequence, so no figure moved. PROVED RED: with the constant restored,
#         `test_po_20260812__record_payment_follows_the_tenants_own_order` fails
#         `KeyError: 'fees'` — the tenant had put fees before the tenant-defined
#         class and the late fee was still left LAST. The seam read belongs in
#         apps/payments/settings_seam.py beside `match_tolerance_days` and is
#         here because that file was outside this lane — REPORTED, one move.
#         (8) ADDED 2026-09-01 (CR-059 CS-23): `record_payment` MEETS THE
#         ACCOUNT'S NEXT PLAN INSTALMENT, in its own transaction, through
#         `plans.link_payment_to_installment`. Before it, nothing on the running
#         product linked a payment to an instalment — the demo seeder and the
#         tests were the only callers of the writer — so every instalment stayed
#         unmarked, the BR-CUS-043 pause never applied, a customer paying on
#         time was chased, missed notices went to customers who missed nothing,
#         and the plan could never close. PROVED RED FIRST: with the call
#         removed, the proof case fails on `assert None == datetime.date(2026,
#         9, 1)` — instalment 1 was paid on its due date and the row still said
#         nothing met it. NO NEW RULE was invented: the earliest-unmet choice
#         and the covers-in-full test both come from the PO's "plan first"
#         ruling of 2026-08-12 (OQ-139) via `apps/customers/payment_plan.
#         split_payment_between`, resolved BY NAME.
#         (9) WHAT (8) DELIBERATELY DOES NOT DO, so the silence is not read as
#         done. A DEPOSIT, a `plan_down` DOWN PAYMENT and a PROCESSING payment
#         meet no instalment, each reported by its own code. A REVERSED
#         instalment payment does NOT unmark its instalment — `reversal.py`
#         has no plan step and is another lane's file, so the bounce leaves the
#         schedule saying an instalment was met by money that came back.
#         REPORTED, not closed. And the S22/S35 half of CS-23 is server-side
#         only: the outcome rides `problems` (which `selectors.
#         recorded_payment_dict` already passes through verbatim), and no screen
#         draws the schedule or offers the "change it" control yet —
#         `installment_seq` is an argument the API layer does not send.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

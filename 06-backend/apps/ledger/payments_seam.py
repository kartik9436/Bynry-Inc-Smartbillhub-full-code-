# ── Trace ──────────────────────────────────────────────
# Epics:    EP-LED-05 (S41, the dual-basis remittance table — CR-060 C19 /
#           task T7d)   Screens: S41 · S36 (the tax tie-out's collected side)
#           NOTE: no US-ID is cited here ON PURPOSE. G10 reads a Trace-header
#           US-ID as "this file ships that story's TCs"; this file ships one
#           cross-module READ, not a story. Same precedent as
#           apps/ledger/metering_seam.py, billing_seam.py and assets_seam.py.
# Rules:    BR-TEN-013 (a module NEVER touches another module's ORM; a
#           cross-module read resolves the owner's published callable) ·
#           BR-LED-002 (BOTH remittance bases always computed — billed = tax on
#           issued bills, collected = tax inside cleared payments via
#           allocation) · BR-PAY-010 (the within-invoice class order is a TENANT
#           SETTING) · BR-REP-002 (a report never recomputes money) ·
#           CLAUDE.md rule 1 (tenant scoping, inherited from payments' own
#           scoped read and never re-implemented here) · rule 2
# Tests:    06-backend/tests/test_cr060_t7d_allocation_classes.py
# Impacts:  apps/ledger/reporting.py (its only caller — the collected column)
# ───────────────────────────────────────────────────────
"""ledger → payments SEAM: **which charge classes did the money actually meet?**

HUMAN-OWNED · HUMAN-REVIEW-PENDING — a wrong answer here is a wrong figure on a
tax return. AI-authored 2026-09-02 under the PO ruling of 2026-08-09 (*"AI will
do it; we will review it later as human"*); the row is in
`12-governance/09-human-review-ledger.md` under CR-060 task T19.

════════════════════════════════════════════════════════════════════════════
WHAT CHANGED TODAY, AND WHY THE COLLECTED COLUMN WAS ABSENT UNTIL NOW
════════════════════════════════════════════════════════════════════════════
`BR-LED-002` (CONFIRMED) requires BOTH bases always: *"billed = tax on issued
bills; collected = tax inside cleared payments via allocation"*. The billed basis
has been exact since it was built. The collected basis was **reported absent with
its reason**, because an `allocations` row named a payment, an invoice and an
AMOUNT and carried no line class — so *"how much of this bill's tax has actually
been paid"* was not a fact the product held.

`payments/0015` (CR-060 C19 / task T7d) gives it one: `allocation_classes`, a
child row per class, written in the same transaction as its parent. This seam
reads it.

**IT DOES NOT SETTLE THE ARGUMENT AND IT IS NOT MEANT TO.** Two signed rulings
disagree about how a partial payment meets tax — `OQ-174` closed 2026-08-12 with
*"a partial payment covers TAX FIRST"*, and `BR-PAY-010` makes the sequence a
TENANT SETTING whose shipped default puts tax second. CR-060 C19's disposition is
explicit: *"Recording the class breakdown makes the question moot, and THAT is
the disposition to write down rather than choosing a winner."* Whatever order a
tenant set is the order their money walked, and what it met is now written down.

════════════════════════════════════════════════════════════════════════════
BR-LED-794 — HOW ONE BILL'S COLLECTED TAX IS SPLIT ACROSS ITS AUTHORITIES
════════════════════════════════════════════════════════════════════════════
Payments records tax as ONE class — `taxes` — because BR-PAY-010's order is
about classes of charge and not about revenue authorities. S41 reports per
AUTHORITY. So one apportionment is needed and it is stated here rather than
discovered from a figure:

**A BILL'S COLLECTED TAX IS SPLIT ACROSS THE AUTHORITIES THAT BILL CHARGED, IN
PROPORTION TO WHAT EACH WAS BILLED ON THAT SAME BILL.**

Three things make it the honest choice rather than a guess:

  * **It is per BILL, never across bills.** The caller sums each authority's own
    credits per invoice out of `journal_lines` — the same rows the `billed`
    column is summed from — so State's share of WE-1's collected tax is computed
    from WE-1's own 13.87 and nothing else. No month-level blending.
  * **It is EXACT whenever a bill's tax was met in full**, which is the ordinary
    case and the one LE-3's signed **20.97** is: collected equals billed on that
    bill, so every authority receives precisely what it was billed and the
    apportionment is the identity.
  * **It only ever divides money that was genuinely collected**, so the four
    authority figures always sum to the recorded collected total. A rule that
    could not guarantee that would let a return be filed for more than came in.

The alternative — asking payments to record tax per authority — would put a
`journal_lines` dimension into the payments allocator and make BR-PAY-010's class
walk depend on the tax catalogue. That is a bigger change than the question is,
and CR-060 §13 keeps the class walk in one place.

════════════════════════════════════════════════════════════════════════════
THE FLOOR, AND WHY THE CALLER MUST PUBLISH IT
════════════════════════════════════════════════════════════════════════════
Some allocated money carries no breakdown and never will: everything allocated
before 2026-09-02 (the breakdown lived only in the pruned audit payload), plus
applications and releases of an account CREDIT, which do not run through the
class walk at all. Those amounts travel back as
`allocated_without_breakdown` and the caller reports them beside the figure.
**The collected column is therefore a FLOOR** — the tax we can prove was
collected — and a report that hid the unclassified total would be publishing a
tax number with a silent hole in it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

#: Payments' published read layer, named once so the contract is greppable from
#: BOTH sides of the boundary.
PAYMENTS_MODULE = "payments"

#: THE READ, and it IS published (unlike this module's siblings' preferred
#: reads):
#:
#:     apps.payments.selectors.collected_by_class_for_invoices(
#:         invoice_ids, *, line_class: str, start: date, end: date
#:     ) -> {"collected": {invoice_id: Decimal},
#:           "allocated_without_breakdown": Decimal,
#:           "allocations_without_breakdown": int,
#:           "allocations_read": int}
COLLECTED_BY_CLASS_READ = "collected_by_class_for_invoices"

#: THE SECOND READ, added for `CR-060` T15 (the allowance for doubtful debts):
#:
#:     apps.payments.outstandings.outstandings(*, as_of: date) -> OutstandingsView
#:
#: It is on `outstandings`, not on `selectors`, which is why `_resolve` takes a
#: `kind`. Payments already publishes it — S34 is drawn from it — so nothing new
#: is asked of that module and no ledger code reads a payments table.
AGED_RECEIVABLE_MODULE = "outstandings"
AGED_RECEIVABLE_READ = "outstandings"

#: The bands `apps.payments.outstandings.AGEING_BUCKETS` serves, named here
#: rather than imported for BR-TEN-013's reason — the ledger resolves payments'
#: callables by name and imports none of its modules.
BUCKET_CURRENT = "current"
BUCKET_1_30 = "1-30"
BUCKET_31_60 = "31-60"
BUCKET_61_90 = "61-90"
BUCKET_90_PLUS = "90+"
AGEING_BUCKETS: tuple[str, ...] = (
    BUCKET_CURRENT,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
)

#: Reported when payments publishes no ageing this seam can read. The allowance
#: is then UNANSWERABLE and nothing is posted — never estimated at zero, which
#: would release a standing allowance to nil on the strength of a missing read.
AGED_RECEIVABLE_UNAVAILABLE = "aged_receivable_read_is_unavailable"

#: The class a tax line belongs to. `apps/payments/allocation.CLASS_TAXES`, named
#: here rather than imported for BR-TEN-013's reason — the ledger resolves
#: payments' callables by name and imports none of its modules.
CLASS_TAXES = "taxes"

#: Reported when payments publishes nothing this seam can read. The collected
#: column then stays absent WITH ITS REASON, exactly as it did before today —
#: which is the behaviour this whole change replaces, kept as the fallback so a
#: deployment missing the read degrades to the honest answer rather than to a
#: zero.
COLLECTED_UNAVAILABLE = "collected_by_class_read_is_unavailable"

ZERO = Decimal("0")


@dataclass(frozen=True)
class CollectedByInvoice:
    """One class's collected money per bill, and what could not be classified.

    `collected is None` means **unanswerable** and is never conflated with an
    empty mapping: *"payments publishes nothing this seam can read"* and *"no
    tax was collected in this window"* are different facts, and only one of them
    may be printed as 0.00.
    """

    collected: dict[str, Decimal] | None
    allocated_without_breakdown: Decimal = ZERO
    allocations_without_breakdown: int = 0
    allocations_read: int = 0
    problems: tuple[str, ...] = field(default=())


def _resolve(attribute: str, kind: str = "selectors") -> Any:
    """Payments' callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{PAYMENTS_MODULE}.{kind}")
    except ImportError:  # pragma: no cover — defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal:
    """A money figure arrives as a Decimal or not at all.

    Refused rather than coerced, for `billing_seam._as_decimal`'s reason: a float
    that reached here would be a defect upstream, and converting it would hide
    the place where a tax figure became a binary fraction.
    """
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    raise TypeError(
        "a collected figure must be a Decimal — money is never a float "
        f"(CLAUDE.md rule 2); got {type(value).__name__}"
    )


@dataclass(frozen=True)
class AgedReceivable:
    """What each ageing band of this tenant's receivable holds, on one day.

    `buckets is None` means **unanswerable** and is never conflated with an
    empty mapping, for `CollectedByInvoice`'s reason one paragraph up: *"payments
    publishes nothing this seam can read"* and *"this utility is owed nothing"*
    are different facts, and only one of them may be priced at 0.00.
    """

    buckets: dict[str, Decimal] | None
    as_of: Any = None
    accounts: int = 0
    problems: tuple[str, ...] = field(default=())

    @property
    def total(self) -> Decimal:
        return sum((self.buckets or {}).values(), ZERO)


def aged_receivable(*, as_of: date) -> AgedReceivable:
    """This tenant's open receivable, split into the five bands S34 already draws.

    **CR-060 T15.** The allowance is a percentage of AGED debt, so the split is
    the input and not a presentation choice.

    ⚠ **IT COMES FROM PAYMENTS AND NOT FROM THE BOOKS, AND THAT IS FORCED.**
    `reporting.GAP_AGING_NEEDS_DUE_DATES` says why in its own words: *"a journal
    line carries no due date, so the Current/31–60/61–90/90+ split cannot be
    summed out of the books"*. `apps.payments.outstandings` ages each account by
    its OLDEST unpaid bill and is what the collections screen shows a clerk, so
    the allowance is computed on the same ageing the utility acts on — which is
    the property that matters more than which module holds it.

    `as_of` is an argument and never a clock (BR-TEN-043), exactly as it is on
    payments' own side: the allowance a clerk previews at 23:58 and the one the
    close posts at 00:02 must be explainable.

    A band absent from the answer is **0.00 for a tenant that has an ageing at
    all** — payments returns a row per account and a band with no accounts in it
    is genuinely empty. A missing READ is the other case and returns
    `buckets=None`.
    """
    read = _resolve(AGED_RECEIVABLE_READ, kind=AGED_RECEIVABLE_MODULE)
    if read is None:
        return AgedReceivable(buckets=None, as_of=as_of, problems=(AGED_RECEIVABLE_UNAVAILABLE,))
    view = read(as_of=as_of)
    rows = tuple(getattr(view, "rows", ()) or ())
    buckets: dict[str, Decimal] = {bucket: ZERO for bucket in AGEING_BUCKETS}
    for row in rows:
        bucket = getattr(row, "bucket", None)
        if bucket not in buckets:
            # A band payments has and this seam does not is REPORTED, never
            # folded into a neighbour: silently pricing an unknown age at the
            # current-band rate is the shape that under-provides a whole book.
            return AgedReceivable(
                buckets=None,
                as_of=as_of,
                accounts=len(rows),
                problems=(f"ageing_band_{bucket}_is_not_known_to_this_seam",),
            )
        buckets[bucket] += _as_decimal(getattr(row, "balance", None))
    return AgedReceivable(
        buckets=buckets,
        as_of=as_of,
        accounts=len(rows),
        problems=tuple(getattr(view, "problems", ()) or ()),
    )


#: `CR-142-BRC07` `P6.11` wave 3 — the read `reporting.GAP_ALLOCATION_PERIOD`
#: named in its own `wanted_reads` and that payments has now published.
APPLIED_TO_PERIOD_READ = "allocated_to_invoices_issued_between"

#: Reported when payments publishes no such read. COLLECTED then stays NULL
#: with this reason and never 0 — `BR-REP-024`.
APPLIED_UNAVAILABLE = "cash_applied_to_this_periods_bills_read_is_unavailable"


def applied_to_bills_issued_between(*, start: date, end: date) -> Decimal | None:
    """Cash APPLIED to bills issued in the window — `BR-REP-009`'s numerator.

    *"Collection % = cash applied to bills in period ÷ billed in period"* (PO
    RQ-1, 2026-08-08). The denominator is the ledger's own `billed`; this is the
    top half, and it is **not** cash RECEIVED in the window: a payment landing on
    2 July against a bill issued on 28 June belongs to JUNE's rate.

    ⚠ **THIS IS WHY `reporting.GAP_ALLOCATION_PERIOD` EXISTS AND WHY IT STAYS.**
    That gap says the percentage *"is not derivable"* from the BOOKS, which is
    true and unchanged: a payment entry credits AR in one lump with `source_id`
    = the payment, so the journal never records WHICH bill the cash met.
    `allocations` does, and this seam is how the ledger asks. **The gap is not
    deleted and `revenue_and_ar`'s `collection_pct` still answers None** —
    moving a shipped KPI on S36 from *absent with a reason* to a number is a
    behaviour change belonging to that screen's owner, not to a report lane
    passing through.

    `None` means payments publishes no such read; it is never a zero.
    """
    read = _resolve(APPLIED_TO_PERIOD_READ)
    if read is None:
        return None
    return _as_decimal(read(start=start, end=end))


def collected_tax_by_invoice(
    *, invoice_ids: tuple[str, ...], start: date, end: date
) -> CollectedByInvoice:
    """How much TAX each named bill was paid, by counted payments in this window.

    The window is the payment's POSTING date since 2026-10-21 (`DEF-PAY-10321`,
    PO ruling: posted + cleared by posting date) — it was the clearing date
    while `cleared` meant the money arrived. Payments applies it; nothing here
    re-implements a date rule.
    """
    read = _resolve(COLLECTED_BY_CLASS_READ)
    if read is None:
        return CollectedByInvoice(collected=None, problems=(COLLECTED_UNAVAILABLE,))
    answer = read(tuple(invoice_ids), line_class=CLASS_TAXES, start=start, end=end)
    return CollectedByInvoice(
        collected={
            str(key): _as_decimal(value) for key, value in (answer.get("collected") or {}).items()
        },
        allocated_without_breakdown=_as_decimal(answer.get("allocated_without_breakdown")),
        allocations_without_breakdown=int(answer.get("allocations_without_breakdown") or 0),
        allocations_read=int(answer.get("allocations_read") or 0),
    )


# ═══════════════════════════════════════════════════════════════════════════
# Finance blueprint p018 `P5.8` — THE PRINTED PAYMENT NUMBER
# ═══════════════════════════════════════════════════════════════════════════
#: THE THIRD READ, published BY `P5.8`:
#:
#:     apps.payments.selectors.payment_numbers_for(ids) -> {id: payment_no}
#:
#: `apps/ledger/reporting.account_ledger` names it in its own gap block's
#: `wanted_reads`, which is how this contract was agreed before either side of
#: it existed.
PAYMENT_NUMBERS_READ = "payment_numbers_for"

#: The one journal `source_type` this seam answers for.
PAYMENT_DOCUMENT_SOURCE = "payment"


def document_numbers_for(wanted: dict[str, set[str]]) -> dict[tuple[str, str], str]:
    """`{("payment", payment_id): payment_no}` — the payments half of `P5.8`.

    Same shape and same contract as `apps/ledger/billing_seam.document_numbers_
    for`, so `account_ledger` merges two maps and never learns which module
    owns which source type.

    ⚠ **AN UNRESOLVED ID IS ABSENT, NEVER THE UUID.** A payment this tenant
    cannot read, one that does not exist and one with no `payment_no` are the
    same absence, and the caller states it in words rather than printing the
    id `B14` rule 31 forbids.

    No ask, no query.
    """
    ids = wanted.get(PAYMENT_DOCUMENT_SOURCE)
    if not ids:
        return {}
    read = _resolve(PAYMENT_NUMBERS_READ)
    if read is None:  # pragma: no cover — payments publishes it since P5.8
        return {}
    return {
        (PAYMENT_DOCUMENT_SOURCE, str(source_id)): str(number)
        for source_id, number in (read(tuple(sorted(ids))) or {}).items()
        if number
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C19 + task T7d (12-governance/11-change-requests.md §7 · §12 ·
#         §13) · 12-governance/01-open-questions.md OQ-129 (CLOSED 2026-08-16)
#         and OQ-174 (CLOSED 2026-08-12) — the two that disagree ·
#         04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-002 /
#         BR-LED-794 · 04-docs/05-modules/07-payments/02-business-rules.md
#         BR-PAY-010 / BR-PAY-038 · CLAUDE.md hard rules 1, 2
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B=deferred(a seam has no backend surface of its own) C✔
#         D=deferred E=deferred F✔ G✔ H=deferred(PO 2026-08-09 — 🔒
#         HUMAN-REVIEW-PENDING, row written under CR-060 T19)
# gates: see 06-backend/tests/test_cr060_t7d_allocation_classes.py — the seam is
#         driven through the report it feeds, on real PostgreSQL, and the
#         unclassified floor is asserted rather than described
# exceptions: (1) **BR-LED-794's per-authority apportionment is THIS LANE'S
#         JUDGMENT**, recorded in 12-governance/02-decision-log.md with its
#         worked figure, not a PO ruling — it divides one bill's collected tax
#         across the authorities that bill charged, is exact on full coverage,
#         and always sums to the recorded total · (2) the collected column is a
#         FLOOR while any allocated money carries no breakdown, and the amount is
#         published beside it rather than absorbed
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

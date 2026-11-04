# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-006 (allocation — the open bills a payment meets) ·
#           US-PAY-013 (S34 outstandings — every debtor's balance and the
#           BR-PAY-032 days-late anchor, read in bulk)
#           Screens: S34 (the result renders as S33's "Applied to" column)
# Rules:    BR-PAY-001 (default allocation = OLDEST open bill) · BR-PAY-010
#           (oldest-invoice-first; within an invoice usage+base → taxes → fees
#           last; overpayment → account credit) · BR-PAY-038 (the fourth class,
#           whose MEMBERSHIP is tenant configuration in the ledger — PO
#           2026-08-11, OQ-109) · BR-BIL-004 (an issued bill is immutable, so
#           its total is a fact and never a recomputation) · CLAUDE.md rule 1
#           (tenant scoping) · BR-PAY-029 (S34 outstandings: AR high→low) ·
#           BR-PAY-032 (days late = today − the OLDEST UNPAID invoice's due
#           date) · BR-CUS-015 (`accounts.balance` is a CACHE — never the
#           figure a collections ladder runs on)
# Tests:    06-backend/tests/test_us_pay_001_record_payment.py ·
#           06-backend/tests/test_us_pay_013_outstandings.py
# Impacts:  apps/payments/services.record_payment (its only caller) ·
#           apps/billing/selectors (the owner, resolved BY NAME)
# ───────────────────────────────────────────────────────
"""payments → billing SEAM: *which bills are open, and what do they still owe?*

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 this file decides what a customer is reported as
owing, and since `DEF-PAY-6940` (2026-09-27) it also decides WHICH DAY that
question is asked about. AI-authored under the PO ruling of 2026-08-09 (*"AI
will do it; we will review it later as human."*); the row is in
`12-governance/09-human-review-ledger.md`.

Payments must not touch billing's ORM (B1: *"cross-module reads via service
functions only"*), and billing must not import payments (it is the callee). So
this module resolves billing's published read BY NAME at call time — the idiom
`apps/billing/rating_seam.py`, `apps/billing/delivery_seam.py` and
`apps/metering/seams.py` all use. Nothing binds the two modules at import, the
boundary is greppable from both sides (`BILLING_MODULE` / `OPEN_INVOICES_READ`
/ `INVOICE_QUERYSET_READ`), and the day billing publishes the preferred read
this seam starts using it with no edit here.

╔══════════════════════════════════════════════════════════════════════════╗
║  THE SPLIT: BILLING KNOWS WHAT WAS BILLED. PAYMENTS KNOWS WHAT IS OPEN.  ║
╚══════════════════════════════════════════════════════════════════════════╝

This is not a stylistic boundary, it is the answer to OQ-113 — *"the S30
`Past-due` segment cannot be answered … 'unpaid' is the payments/ledger position
and neither module has a table"*. An invoice's OPEN balance is

    invoice.total  −  Σ(this module's own `allocations` rows against it)

Billing owns the first term and cannot compute the second; payments owns the
second and must not invent the first. So billing is asked only what it can
honestly answer — the ISSUED bills of an account with their totals and issue
dates — and the subtraction happens here, over rows this module owns. That also
makes `record_payment` the first code in the product that can say whether a
bill is past due, which is what R2 has been unable to answer all session
(B12 addendum r9).

**Bills whose open balance is zero are dropped**, not returned as zeros: a
settled bill is not an open bill, and handing the allocator a 0.00 balance would
produce an `Allocation` row for money that never moved (`allocation.py`: *"a row
means money moved"*).

────────────────────────────────────────────────────────────────────────────
WHAT THIS SEAM CANNOT ANSWER TODAY, AND WHY IT IS REPORTED RATHER THAN GUESSED
────────────────────────────────────────────────────────────────────────────
**THE WITHIN-INVOICE COMPOSITION.** Since the PO's ruling of 2026-08-11 an
allocation has a shape inside each bill — usage+base → taxes → the
tenant-defined class → fees LAST (BR-PAY-010 as amended by BR-PAY-038) — and
`apps/payments/allocation.py` executes it from a `composition` the CALLER
states. Payments cannot state it, for two independent reasons and neither is
fixable from this side:

  1. **Classifying a line is billing's knowledge, not payments'.** Billing's
     line kinds are `usage · base · tax · fee · minimum_adjustment`
     (`apps/billing/stages/assemble_document.LINE_KINDS`). Four of them map onto
     a class readably; `minimum_adjustment` (BR-RAT-028) maps onto none that any
     signed document names, and picking one decides how much of a customer's tax
     counts as collected. **OQ-128**, raised.
  2. **The fourth class's MEMBERSHIP is the TENANT's, held in the ledger** — the
     PO's own amendment to OQ-109: *"allow tenant user to define it in
     ledge[r]"*. The ledger publishes no such read yet
     (`allocation.tenant_defined_class_members()` answers `None`), so nobody can
     say which fee lines are `tenant_defined` and which are `fees`.

Absence is a LEGAL input, which is what makes reporting it honest rather than a
dodge: B5 GT-7 — ❄️ finance-signed — states no line detail at all, and
`allocation.py` allocates such a bill by amount alone and reports no breakdown.
So a payment recorded today meets the right BILLS in the right order and its
within-bill breakdown is simply not computed, with the gap named on the result
as `invoice_composition_unavailable`. It is never invented from the total, and
a partial breakdown is refused outright by the allocator (*"an outstanding tax
that is short by whatever the silent bills owe"*).

The moment a caller CAN state a composition — a billing read, a test fixture —
this seam passes it through untouched and the four-class walk runs. That path
is exercised, with the PO's own $128.88 figure, in
tests/test_us_pay_001_record_payment.py.

**A THIRD REASON, WHICH OUTLIVES THE OTHER TWO (OQ-129).** Even with a
published kind→class map, a bill that has ALREADY been part-paid cannot state
its open composition, because `allocations` records an amount and not a class
(B2 §2 gives it five columns and no class), so which class last month's money
met is not recorded anywhere. `open_invoices_for_account` therefore states a
composition only for bills with NO prior allocation, and says so.

────────────────────────────────────────────────────────────────────────────
⚠ WHAT THIS SEAM MEASURES A BILL AT — **WHAT IT ASKS FOR, NOT WHAT IT TOTALS**
(DEF-2416, FIXED 2026-09-01; this section said NOT FIXED until then)
────────────────────────────────────────────────────────────────────────────
Every open balance below is **`amount_due − Σ allocations`**, and `amount_due`
is `apps.billing.selectors.amount_due_for` — billing's own published answer to
*"what does this bill ask the customer to pay?"*, resolved BY NAME like every
other read on this seam. For an ordinary bill that IS `invoice.total` and always
was. For a BUDGET BILLING bill it is the **LEVEL**, which is a different number.

**THE RULING AND THE FIGURES, AND NEITHER IS NEW.** The PO ruled on 2026-08-11,
verbatim *"Level is due"* (BR-BIL-072, closing OQ-140 and DEF-062). On the ❄️
WE-8 bill the two figures are **292.87** (what the customer consumed) and
**242.00** (what the bill asks for). Both are WE-8's, unchanged; the level is
read off the bill's OWN FROZEN payload (BR-BIL-030), so a re-level in January
cannot rewrite what a July bill asked for.

**WHAT WAS WRONG UNTIL 2026-09-01.** This seam measured every bill at
`invoice.total` and called billing's function nowhere, so a budget customer who
paid exactly the 242.00 they were asked for was reported as still owing
**50.87**: the S22 picker offered a clerk a bill nobody owed, `outstanding
_positions` added 50.87 to their balance, and `ladder.run_ladder` — which reads
that balance — chased them up the collection ladder every month, for ever. That
is DEF-062's own harm one module along, and DEF-062's fix had never crossed the
boundary. Billing closed it in August; payments called neither that function nor
anything like it, and both modules stayed internally consistent and green.

**WHAT MOVED, STATED PLAINLY, BECAUSE IT IS THE ALLOCATION PATH.** A payment now
settles a budget bill at its LEVEL, so 242.00 closes the month and anything
beyond it is an overpayment that carries as account credit under BR-PAY-010 —
exactly what any other overpayment does. No rounding site was added, no figure
of B4/B5 moved, and the allocator itself is untouched: it still reads `balance`
alone and this seam still owns the subtraction. A short payment still leaves a
real balance (200.00 against the 242.00 ask leaves **42.00**) and the ladder
still runs on it.

**IF BILLING EVER STOPS PUBLISHING `amount_due_for`** the seam falls back to the
issued total and SAYS SO on `problems` (`bill_amount_due_unavailable`). The rule
is not re-implemented here for `apps/customers/payment_plan.py`'s reason about
the $25 late-fee floor: *"a second copy of a ruled figure is how two figures
start disagreeing."*
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Any

from apps.payments import balance_rule
from apps.payments.allocation import ALLOCATION_CLASSES, ClassBalance

#: Billing's published read layer, named once so the contract is greppable from
#: BOTH sides of the boundary — the same discipline as
#: `apps/billing/issue.GL_REVENUE_READ`.
BILLING_MODULE = "billing"

#: `accounts.bad_address` is CUSTOMERS' column (`DEF-PAY-6342`): the Debtors
#: filter composes customers' lazy id queryset rather than deriving the flag
#: from this module's return events. Named once, greppable from both sides.
CUSTOMERS_MODULE = "customers"
BAD_ADDRESS_IDS_READ = "flagged_account_ids"

#: THE PREFERRED READ, and the contract for the lane that publishes it:
#:
#:     apps.billing.selectors.issued_invoices_for_account(account_id)
#:         -> Iterable[Mapping]  with keys:
#:              id            the invoice's uuid
#:              number        `invoice_no` (or the id when a bill has none)
#:              total         Decimal — the issued, immutable total (BR-BIL-004)
#:              issued_on     date — what "oldest" means (BR-PAY-001)
#:              currency      CHAR(3) — the bill's own code (hard rule 2). Its
#:                            absence is REPORTED by the caller and never filled
#:                            in from the tenant's own currency.
#:              composition   OPTIONAL Mapping[str, Decimal] — the BILLED amount
#:                            per allocation class. Absent = not answerable; see
#:                            the module docstring.
#:
#: Billing does not publish it today. Rather than leave the closed loop dead
#: (hard-won law 2 — built is not wired), the seam falls back to billing's OWN
#: published tenant-scoped queryset and reads the four facts along the reviewed
#: cross-module edge B2 §2 already grants this module (*payment N:M invoice via
#: allocations*). No billing model is imported and no billing file is edited.
OPEN_INVOICES_READ = "issued_invoices_for_account"
INVOICE_QUERYSET_READ = "invoice_queryset"

#: ⛔ **WHAT A BILL ASKS FOR — BR-BIL-072, and the read DEF-2416 was about.**
#:
#:     apps.billing.selectors.amount_due_for(invoice) -> Decimal
#:
#: `invoice.total` for an ordinary bill; the **LEVEL** for a budget-billing one,
#: read out of the bill's own frozen payload (BR-BIL-030). On ❄️ WE-8 those are
#: 292.87 and 242.00, and the PO ruled *"Level is due"* on 2026-08-11.
#:
#: It takes an INVOICE and reads exactly two things off it — `total` and
#: `bill_payload` — which is why `outstanding_positions`, whose whole job is to
#: answer in two queries for every debtor a utility has, can hand it a
#: `_BillFacts` built from a `.values()` row instead of a model instance.
#:
#: Resolved BY NAME at call time like every other read here. The rule is NOT
#: copied: a second implementation of "what does this bill ask for" is how the
#: bill a customer holds and the balance a clerk reads come to disagree.
AMOUNT_DUE_READ = "amount_due_for"

#: ⛔ **THE SAME RULE AS `AMOUNT_DUE_READ`, AS A QUERYSET** — billing publishes
#: it so that `outstanding_positions_page` can push the whole debtor
#: computation into SQL without a second copy of BR-BIL-072 living in this
#: module (`CR-138-BRC07` `P4.1`).
#:
#:     apps.billing.selectors.open_invoice_amounts_queryset(statuses) -> QuerySet
#:         values: id · account_id · due_date · amount_due
#:
#: Resolved BY NAME at call time like every other read here.
OPEN_AMOUNTS_QUERYSET_READ = "open_invoice_amounts_queryset"

#: ⛔ **THE SAME READ PLUS THE BILL'S CURRENCY — the AR ageing's footer.**
#:
#:     apps.billing.selectors.open_invoice_aging_queryset(statuses) -> QuerySet
#:         values: id · account_id · due_date · amount_due · currency
#:
#: `P2.21`. A tenant whose open bills are denominated in more than one currency
#: has a footer that is not a number, and this read is how the ageing can say so
#: rather than adding unlike money.
AGING_QUERYSET_READ = "open_invoice_aging_queryset"

#: ⛔ **p035's `f.service`, as LAZY invoice ids** — billing owns `invoice_lines`.
#:
#:     apps.billing.selectors.invoice_ids_for_service(code) -> QuerySet
AGING_SERVICE_IDS_READ = "invoice_ids_for_service"

#: ⛔ **p035's `f.premises` and `q`, as LAZY account ids** — customers owns both
#: columns, and `B1`/`BR-TEN-013` forbid this module joining them.
#:
#:     apps.customers.selectors.account_ids_at_premises(id) -> QuerySet
#:     apps.customers.selectors.account_ids_matching_debtor_search(term) -> QuerySet
AGING_PREMISES_IDS_READ = "account_ids_at_premises"
AGING_SEARCH_IDS_READ = "account_ids_matching_debtor_search"

#: The sentinel band a bill with NO due date takes. It is deliberately not one
#: of `AgeingBands.names()`, so every `Sum(filter=Q(band=<a real band>))` misses
#: it and `Sum("open_balance")` — the row's Total — catches it. `BR-PAY-032`:
#: counted in the total, aged into nothing.
_UNDATED_BAND = "__undated__"

#: The two invoice states that can still owe money. `draft` has not been issued,
#: `void` is no longer owed and `corrected` has been replaced by a rebill
#: (BR-BIL-014) — a payment must never be allocated against any of the three.
#: `paid` stays in because "paid" is billing's own cached view of settlement and
#: this seam recomputes openness from `allocations`; a `paid` bill simply drops
#: out with a zero balance.
OPEN_INVOICE_STATUSES: tuple[str, ...] = ("issued", "paid")

#: The two states a bill can be in TODAY that mean it was issued once and is
#: no longer live — `void` (cancelled) and `corrected` (replaced by a rebill,
#: BR-BIL-014). ⚠ **THE AS-AT READ COUNTS THEM AND CANNOT RESTORE THEM**, and
#: that is a fact about the SCHEMA rather than a choice: `invoices` carries
#: `issued_at`, which is frozen by the `0002` immutability trigger and is
#: therefore a sound clock, and it carries **no `voided_at` and no
#: `corrected_at`** — so nothing in the database records the DAY a live bill
#: stopped being live. A position at a past date can say how many such bills
#: had been issued by that date; it cannot say which of them were still open.
#: `DEF-PAY-7020` carries the gap. Hard-won law 7: a declared blind spot with
#: no NUMBER beside it is indistinguishable from an empty one, so
#: `aging_positions_page` prints the count beside the figures it did serve.
RETIRED_INVOICE_STATUSES: tuple[str, ...] = ("void", "corrected")

ZERO = Decimal("0")


@dataclass(frozen=True)
class OpenInvoice:
    """One open bill, in the shape `apps.payments.allocation` consumes.

    Structurally identical to `apps.billing.rating_seam.OpenInvoice` and defined
    HERE rather than imported from there for the reason that seam gives about
    rating: billing calls payments, so payments must not import billing.

    `composition` is EMPTY when the breakdown is not answerable — never a set of
    zeros. Absence and "all classes are settled" are different facts and only
    the first one is true today (module docstring).
    """

    number: str
    balance: Decimal
    issued_on: date | None = None
    composition: tuple[ClassBalance, ...] = ()
    #: The uuid the `allocations` row is written against. Carried alongside the
    #: NUMBER because the allocator speaks in numbers (B5 GT-7 names bills as
    #: "BL-A") and the database speaks in ids.
    invoice_id: Any = None
    # ── The three facts `GET /accounts/{id}/open-bills` serves beside the
    # balance (CR-059 CS-4, 2026-09-01). They are CARRIED, never recomputed:
    # `balance` is still `total - allocated` and the allocator still reads only
    # `balance`, so adding them cannot move a single figure. `OpenInvoiceLike`
    # is a structural Protocol, which is why three more fields are additive.
    #
    # WHY THE PICKER NEEDS ALL THREE. A clerk aiming money at one bill is shown
    # what it still owes; a clerk reading S21's Bills tab is shown what the bill
    # was ISSUED for beside it, because those are different sentences and the
    # screen could previously only make the first. `allocated` is what closes
    # the gap between them, so no screen has to do the subtraction itself.
    #: The ISSUED, immutable total (BR-BIL-004) — what the bill CHARGED.
    #: ⚠ It used to be described as *"what the bill asked for"* and for a budget
    #: bill those are two different numbers (DEF-2416): WE-8 charges 292.87 and
    #: asks for 242.00. `amount_due` below is the one a payment is measured
    #: against; this one is what S21's Bills tab shows beside it.
    total: Decimal | None = None
    #: ⛔ **WHAT THE BILL ASKS FOR (BR-BIL-072) — the figure `balance` is
    #: computed from.** `amount_due − allocated == balance`, always, which is
    #: what lets a screen show all four without doing arithmetic of its own.
    #: Equal to `total` for every bill that is not budget-billing, which is
    #: almost all of them. `None` only when billing publishes no
    #: `amount_due_for` at all, which is reported on `problems` and never
    #: silently replaced with the total.
    amount_due: Decimal | None = None
    #: Sum of this module's own `allocations` rows against the bill.
    allocated: Decimal | None = None
    #: The bill's own CHAR(3) code. Hard rule 2: a currency rides WITH the
    #: amount and is never assumed. `None` when the read that produced this row
    #: states none — reported by the caller, never defaulted to the tenant's.
    currency: str | None = None
    #: ⚠ **THE DAY THE BILL WAS DUE — ADDED 2026-09-23, `DEF-PAY-6254`.**
    #: `_rows_from_billing` has carried `due_on` since `CR-059` CS-4 under a
    #: comment saying in as many words that *"'days late' and the whole
    #: collection ladder are anchored on the DUE DATE, so it travels with the
    #: row"* — and this dataclass, which that row is copied into, had nowhere
    #: to put it. The date reached the seam and stopped there, so screen 7·2's
    #: drawn **DUE** and **AGE** columns had nothing to fill them.
    #:
    #: ADDITIVE AND DEFAULTED: `OpenInvoiceLike` is a structural Protocol, the
    #: allocator reads only `balance`, and no figure anywhere moves. `None` is
    #: a MEASURED fact — billing declares `due_date` nullable (BR-BIL-024,
    #: derived) and an undated bill is reported on `problems` rather than
    #: placed on a date nobody has (BR-PAY-032). A screen draws a dash for it
    #: and never a zero.
    due_on: date | None = None


@dataclass(frozen=True)
class OpenPosition:
    """Every open bill of one account, plus what could not be answered.

    `problems` carries codes a screen can group on, never prose it would have to
    parse — the same shape `apps/billing/delivery_seam.BillDelivery` uses.
    """

    invoices: tuple[OpenInvoice, ...] = ()
    problems: tuple[dict[str, Any], ...] = field(default=())


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's callable, or None while it has not published one."""
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _as_decimal(value: Any) -> Decimal:
    """Money arrives as a Decimal or not at all (hard rule 2).

    Refused rather than coerced: a float that reached here would be a defect
    upstream, and converting it would hide the place where money became binary.
    """
    if isinstance(value, Decimal):
        return value
    raise TypeError(
        f"an invoice total must be a Decimal — money is NUMERIC(18,6), never a binary "
        f"fraction and never cents (CLAUDE.md rule 2); got {type(value).__name__}"
    )


@dataclass(frozen=True)
class _BillFacts:
    """The two fields `amount_due_for` reads, off a `.values()` row.

    `outstanding_positions` answers for every debtor a utility has in TWO
    queries, so it never holds a model instance — and billing's published
    function takes an invoice. These are exactly the attributes that function
    touches (`invoice.bill_payload`, `invoice.total`) and no others: the point
    is to ASK billing rather than to re-derive its answer from a row, which is
    the copy DEF-2416 exists because nobody made.
    """

    total: Decimal
    bill_payload: Any = None


#: The problem code raised when billing publishes no `amount_due_for`. A CODE
#: plus a sentence, never prose a screen would have to parse.
AMOUNT_DUE_UNAVAILABLE = "bill_amount_due_unavailable"

_AMOUNT_DUE_PROBLEM = {
    "code": AMOUNT_DUE_UNAVAILABLE,
    "br_ref": "BR-BIL-072",
    "detail": f"apps.{BILLING_MODULE}.selectors.{AMOUNT_DUE_READ} is not published, so what "
    "each bill ASKS the customer to pay could not be read and every balance below is measured "
    "at the issued TOTAL instead. For an ordinary bill those are the same number. For a BUDGET "
    "BILLING bill they are not — the PO ruled 'Level is due' on 2026-08-11 (BR-BIL-072) and on "
    "the WE-8 bill the two figures are 292.87 and 242.00 — so a budget customer who paid the "
    "level they were asked for will read as still owing the variance until the read is back. "
    "It is REPORTED rather than re-derived here: the level lives in the bill's own frozen "
    "payload and is billing's to read (DEF-2416).",
}


def _amount_due(invoice: Any, *, total: Decimal) -> tuple[Decimal, bool]:
    """What this bill ASKS for (BR-BIL-072), and whether billing answered.

    Returns `(total, False)` when billing publishes no read — the honest
    fallback, because the issued total IS the answer for every bill that is not
    budget-billing and the alternative is refusing to say what an account owes.
    The caller reports the second element; it is never swallowed.
    """
    published = _resolve(BILLING_MODULE, AMOUNT_DUE_READ)
    if published is None:  # pragma: no cover - billing publishes it
        return total, False
    return _as_decimal(published(invoice)), True


def _composition_from(stated: Any, *, allocated: Decimal) -> tuple[ClassBalance, ...]:
    """The per-class OPEN balances, or () when they cannot be stated.

    Two ways this comes back empty, and both are honest:

      * billing stated no composition (today's state, always);
      * the bill has ALREADY been part-paid. `allocations` records an amount and
        no class (B2 §2), so which class the earlier money met is recorded
        nowhere and the BILLED composition is not the OPEN one. Stating it
        anyway would over-report the tax still outstanding, which is the exact
        figure the PO's ruling of 2026-08-11 built the breakdown for. OQ-129.
    """
    if not stated or allocated != ZERO:
        return ()
    balances = []
    for line_class in ALLOCATION_CLASSES:
        if line_class in stated:
            balances.append(
                ClassBalance(line_class=line_class, balance=_as_decimal(stated[line_class]))
            )
    unknown = sorted(set(stated) - set(ALLOCATION_CLASSES))
    if unknown:
        raise ValueError(
            f"billing stated allocation class(es) {unknown} that BR-PAY-010's order does "
            f"not place — it orders {list(ALLOCATION_CLASSES)} and names nothing else. "
            "Payments does not classify lines and does not silently drop a class it was "
            "handed: money stated under an unplaceable class would vanish from the walk."
        )
    return tuple(balances)


def _composition_unavailable() -> dict[str, Any]:
    """The problem the fallback read states on every answer: no bill states its
    composition. One statement, read by `_rows_from_billing` and by the whole-run
    `open_invoices_for_accounts` (`DEF-BIL-8696`) alike."""
    return {
        "code": "invoice_composition_unavailable",
        "br_ref": "BR-PAY-038",
        "detail": f"apps.{BILLING_MODULE}.selectors.{OPEN_INVOICES_READ} is not published, "
        "so no bill states its usage+base / taxes / tenant-defined / fees balances. The "
        "payment meets the right BILLS in the right order (BR-PAY-001 oldest-first) and its "
        "WITHIN-bill breakdown is not computed — B5 GT-7's own shape, and a legal input to "
        "the allocator. Two facts have to land before it can be: a published kind→class map "
        "(OQ-128, `minimum_adjustment` belongs to no named class) and the tenant's own "
        "definition of the fourth class in the ledger (BR-PAY-038, PO 2026-08-11).",
    }


def _rows_from_billing(
    account_id: Any,
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """The issued bills of one account, as plain facts, and the gaps if any.

    ⚠ **EVERY ROW CARRIES `amount_due` AS WELL AS `total`** (DEF-2416). They are
    the same number for every bill that is not budget-billing, and keeping both
    is what lets a screen say *"issued 292.87, asks 242.00"* without either
    figure being recomputed anywhere downstream.
    """
    problems: list[dict[str, Any]] = []
    published = _resolve(BILLING_MODULE, OPEN_INVOICES_READ)
    if published is not None:
        rows = []
        for stated in published(account_id):
            row = dict(stated)
            if "amount_due" not in row:
                # The preferred read does not state it, so ASK for it — the row
                # carries the facts `_BillFacts` needs and billing owns the
                # rule. Never `row["total"]` by default: that is DEF-2416.
                due, answered = _amount_due(
                    _BillFacts(
                        total=_as_decimal(row["total"]), bill_payload=row.get("bill_payload")
                    ),
                    total=_as_decimal(row["total"]),
                )
                row["amount_due"] = due
                if not answered and not problems:
                    problems.append(dict(_AMOUNT_DUE_PROBLEM))
            rows.append(row)
        return tuple(rows), tuple(problems)

    queryset = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - defensive
        return (), (
            {
                "code": "billing_publishes_no_invoice_read",
                "br_ref": "BR-PAY-010",
                "detail": f"neither apps.{BILLING_MODULE}.selectors.{OPEN_INVOICES_READ} nor "
                f"{INVOICE_QUERYSET_READ} is published, so the open bills this payment should "
                "meet cannot be read. Nothing is allocated on a guess.",
            },
        )

    rows = []
    answered_all = True
    for invoice in (
        queryset()
        .filter(account_id=account_id, status__in=OPEN_INVOICE_STATUSES)
        .order_by("issued_at", "id")
    ):
        # DEF-2416 / BR-BIL-072 — billing's own answer, asked per bill. It reads
        # the level off THIS bill's frozen payload (BR-BIL-030), so a re-level
        # cannot change what an already-issued bill asked for.
        due, answered = _amount_due(invoice, total=invoice.total)
        answered_all = answered_all and answered
        rows.append(
            {
                "id": invoice.pk,
                "number": invoice.invoice_no or str(invoice.pk),
                "total": invoice.total,
                #: What the bill ASKS for — `total` for every bill that is not
                #: budget-billing, and the LEVEL for one that is.
                "amount_due": due,
                "issued_on": invoice.issued_at.date() if invoice.issued_at is not None else None,
                # BR-PAY-032 / BR-PAY-017 — "days late" and the whole collection
                # ladder are anchored on the DUE DATE, so it travels with the row.
                # Nullable exactly as billing declares it (BR-BIL-024, derived).
                "due_on": invoice.due_date,
                # Hard rule 2's CHAR(3) partner, read along the same reviewed edge
                # as the total it belongs to. Without it every amount this seam
                # produces reaches a screen as a bare number (CR-059 CS-4).
                "currency": invoice.currency,
            }
        )

    problems.append(_composition_unavailable())
    if not answered_all and rows:  # pragma: no cover - billing publishes it
        problems.append(dict(_AMOUNT_DUE_PROBLEM))
    return tuple(rows), tuple(problems)


@dataclass(frozen=True)
class OutstandingPosition:
    """What ONE account owes, and since when (US-PAY-013 · US-PAY-014).

    `balance` is Σ(issued bill totals) − Σ(this module's allocation rows) — the
    same arithmetic `open_invoices_for_account` does one bill at a time, done in
    bulk because S34 lists every debtor a utility has and one query per account
    is how a list screen becomes a timeout.

    ⚠ IT IS NOT `accounts.balance`. That column is customers' CACHE (BR-CUS-015)
    and the ledger is the truth; a collections ladder driven off a cache chases
    people for money they have paid. Reported by name rather than substituted.

    `oldest_due_on` is BR-PAY-032's anchor, verbatim: *"days late everywhere =
    today − the OLDEST UNPAID invoice's due date"*. `undated` counts bills that
    are unpaid and carry NO due date — they are EXCLUDED from the anchor and
    reported, never placed by a convention no rule states (the same posture
    `open_invoices_for_account` takes with a missing issue date).

    ⚠ **`balance` IS NET OF WHAT THE UTILITY HOLDS FOR THIS ACCOUNT SINCE
    2026-09-02 (CR-059 CS-38).** `gross_balance` is the old figure — bills less
    allocations — and `credit_applied` is how much of the account's POSITIVE
    credit position came off it. Both are carried rather than derivable, because
    a clerk asked why a notice says 222.30 when the bill says 247.30 needs the
    two halves and not a subtraction they have to guess at.
    """

    account_id: Any
    balance: Decimal
    oldest_due_on: Any = None
    invoice_count: int = 0
    undated: int = 0
    #: What the bills alone say, before any credit came off. Equal to `balance`
    #: on every account holding no credit, which is nearly all of them.
    gross_balance: Decimal | None = None
    #: How much of the account's credit was taken off the chase. Never more than
    #: the gross and never negative (see the comment in `outstanding_positions`
    #: — BR-PAY-041's signed figure is untouched; this is only what reduces a
    #: bill-based chase).
    credit_applied: Decimal = Decimal("0")


def _scoped(queryset: Any, account_ids: list[Any] | None, *, field: str = "account_id") -> Any:
    """Narrow to named accounts, or leave the whole tenant (`P4.1`)."""
    if account_ids is None:
        return queryset
    return queryset.filter(**{f"{field}__in": account_ids})


def _credit_positions(account_ids: list[Any] | None) -> dict[Any, Decimal]:
    """Every listed account's SIGNED credit position, in three queries.

    ⚠ **`None` MEANS THE WHOLE TENANT (`CR-138-BRC07` `P4.1`)**, and an empty
    list still means nothing — the two are different questions and conflating
    them would answer "every account" to a caller who asked about none.

    The same arithmetic `selectors.account_credit_position` states one account
    at a time — Σ payments (deposits excluded; only `balance_rule`'s
    `posted` / `cleared` / `reversed`, CR-186-BRC10) − Σ
    allocations − Σ issued/cleared refunds — done in bulk, because S34 lists
    every debtor a utility has and one query per account is how a list screen
    becomes a timeout. That function stays the single statement of the RULE and
    this is the bulk form of it; a test asserts the two agree on the same
    account, which is the only thing that stops them drifting.

    Signed. Nothing is floored (BR-PAY-041) — the caller decides what a negative
    position may do, and says so where it decides it.
    """
    # A queryset (`DEF-BIL-8696`) is a subquery and is never evaluated here.
    if account_ids is not None and not hasattr(account_ids, "query") and not account_ids:
        return {}
    from django.db.models import Sum

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    # CLAUDE.md rule 1 — explicit, and REFUSED rather than defaulted when no
    # tenant is set. `selectors._tenant_id` is the module's one statement of
    # that refusal and is reused rather than re-typed; RLS FORCE is the second
    # guarantee, never the first.
    tenant_id = payment_selectors._tenant_id()
    totals: dict[Any, Decimal] = {}
    for row in (
        _scoped(payment_models.Payment.objects.filter(tenant_id=tenant_id), account_ids)
        # CR-186-BRC10 (`DEF-PAY-10340`): posted, cleared and reversing rows
        # only — never cancelled, failed or processing. `balance_rule` is the
        # one statement of the set.
        .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)
        .exclude(purpose=payment_models.PURPOSE_DEPOSIT)
        .values("account_id")
        .annotate(total=Sum("amount"))
    ):
        totals[row["account_id"]] = row["total"] or ZERO
    for row in (
        _scoped(
            payment_models.Allocation.objects.filter(tenant_id=tenant_id),
            account_ids,
            field="payment__account_id",
        )
        .values("payment__account_id")
        .annotate(total=Sum("amount"))
    ):
        key = row["payment__account_id"]
        totals[key] = totals.get(key, ZERO) - (row["total"] or ZERO)
    # ⚠ **GROUPED ON `account_id`, NOT THROUGH THE PAYMENT (CR-059 CS-7,
    # 2026-09-03).** This clause used to JOIN THROUGH `payment__account_id`,
    # which was exact while `refunds.payment_id` was NOT NULL and became
    # silently wrong the moment the PO's ruling of 2026-09-01 made it nullable:
    # a refund raised against a credit built from SEVERAL payments has no
    # payment, and an INNER JOIN drops the row. The account's credit would then
    # be overstated by every such refund — on the read S34 and the collection
    # ladder run on, so a customer whose $57.13 had already gone out would be
    # chased for $57.13 less than they owe.
    for row in (
        _scoped(
            payment_models.Refund.objects.filter(
                tenant_id=tenant_id,
                status__in=(payment_models.REFUND_ISSUED, payment_models.REFUND_CLEARED),
            ),
            account_ids,
        )
        .values("account_id")
        .annotate(total=Sum("amount"))
    ):
        key = row["account_id"]
        totals[key] = totals.get(key, ZERO) - (row["total"] or ZERO)
    return totals


def outstanding_positions(
    *, account_ids: Any = None
) -> tuple[tuple[OutstandingPosition, ...], tuple[dict[str, Any], ...]]:
    """Every account of this tenant that still owes money, in TWO queries.

    Returns `(positions, problems)`. An account whose bills are fully allocated
    does not appear: a debtor list with settled accounts on it is not a debtor
    list.

    Tenant scoping is billing's published queryset's own (it filters on
    `app.tenant_id` explicitly and RLS FORCE is the second guarantee) and this
    module's `allocations` sum runs under the same session GUC — so this can
    only ever see one tenant's debts.
    """
    queryset = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - billing publishes it
        return (), (
            {
                "code": "billing_publishes_no_invoice_read",
                "br_ref": "BR-PAY-029",
                "detail": f"apps.{BILLING_MODULE}.selectors.{INVOICE_QUERYSET_READ} is not "
                "published, so the bills behind an outstanding balance cannot be read. The "
                "outstandings list reports that it cannot answer rather than showing an empty "
                "one, which would read as 'nobody owes anything'.",
            },
        )

    rows = queryset().filter(status__in=OPEN_INVOICE_STATUSES)
    if account_ids is not None:
        rows = rows.filter(account_id__in=list(account_ids))
    # ⛔ `bill_payload` rides along for DEF-2416: it is the half of BR-BIL-072
    # that `amount_due_for` reads, and pulling it here keeps this a TWO-query
    # read. Fetching model instances instead would answer the same question at
    # one query per debtor, which is how a list screen becomes a timeout.
    invoices = list(rows.values("id", "account_id", "total", "due_date", "bill_payload"))
    if not invoices:
        return (), ()

    from django.db.models import Sum

    from apps.payments import models as payment_models

    allocated = {
        row["invoice_id"]: row["total"] or ZERO
        for row in payment_models.Allocation.objects.filter(
            invoice_id__in=[invoice["id"] for invoice in invoices]
        )
        .values("invoice_id")
        .annotate(total=Sum("amount"))
    }

    by_account: dict[Any, dict[str, Any]] = {}
    answered_all = True
    for invoice in invoices:
        total = _as_decimal(invoice["total"])
        # ⛔ DEF-2416 / BR-BIL-072 — S34 and `ladder.run_ladder` both run on this
        # balance, so measuring a budget bill at its TOTAL here is what chased a
        # customer who had paid their level in full. Billing's own read decides
        # it, per bill, off that bill's frozen payload.
        due, answered = _amount_due(
            _BillFacts(total=total, bill_payload=invoice.get("bill_payload")), total=total
        )
        answered_all = answered_all and answered
        balance = due - allocated.get(invoice["id"], ZERO)
        if balance <= ZERO:
            continue  # settled — not an outstanding bill
        bucket = by_account.setdefault(
            invoice["account_id"],
            {"balance": ZERO, "oldest_due_on": None, "count": 0, "undated": 0},
        )
        bucket["balance"] += balance
        bucket["count"] += 1
        due_on = invoice["due_date"]
        if due_on is None:
            bucket["undated"] += 1
            continue
        if bucket["oldest_due_on"] is None or due_on < bucket["oldest_due_on"]:
            bucket["oldest_due_on"] = due_on

    # ══════════════════════════════════════════════════════════════════════
    # CR-059 CS-38 · WHAT THE UTILITY IS ALREADY HOLDING COMES OFF THE CHASE
    # ══════════════════════════════════════════════════════════════════════
    # Until 2026-09-02 this balance was bill totals less allocations and NOTHING
    # else, so an account holding real credit was chased for the gross. CS-38
    # is the case that made it visible: a 25.00 goodwill concession on a 247.30
    # bill posts correctly, queues a letter telling the customer about it, and
    # then the ladder sends them a notice for 247.30. CS-38's own words are that
    # *"the balance, the next bill and the collection ladder all agree with the
    # letter"*, and this is the only place all three read.
    #
    # **ONLY A POSITIVE CREDIT COMES OFF, AND BR-PAY-041 IS NOT BEING FLOORED.**
    # That rule says a NEGATIVE credit is a real debt and that no code, screen
    # or report may floor the FIGURE at zero — and nothing here does:
    # `account_credit_position` still returns it signed and every screen still
    # renders it signed. What this decides is narrower, and it is a judgment
    # recorded in the decision log rather than a rule invented here: a negative
    # credit does not INCREASE a bill-based chase. It is a debt with no bill
    # behind it, and a ten-day disconnect notice is not the instrument for it —
    # sending one would state that bills are unpaid which are not. It is
    # reported by name below instead.
    #
    # ⚠ **THIS DOES NOT FIX `DEF-3121` AND MUST NOT LOOK AS IF IT HAD.** An
    # approved write-off reduces receivables in the ledger and writes no payment
    # and no credit row, so an account carrying one has an unchanged credit
    # position and is still chased for the full 948.20 at 91 days late. That
    # defect stays open and stays visible.
    credit_for = _credit_positions(list(by_account))
    positions_list: list[OutstandingPosition] = []
    negative_credits = 0
    for account_id, bucket in by_account.items():
        credit = credit_for.get(account_id, ZERO)
        if credit < ZERO:
            negative_credits += 1
        held = credit if credit > ZERO else ZERO
        gross = bucket["balance"]
        applied = held if held < gross else gross
        net = gross - applied
        if net <= ZERO:
            # The utility holds at least what this account owes. A debtor list
            # with settled accounts on it is not a debtor list — the same test
            # the per-invoice loop above applies, applied once more after the
            # credit is taken off.
            continue
        positions_list.append(
            OutstandingPosition(
                account_id=account_id,
                balance=net,
                oldest_due_on=bucket["oldest_due_on"],
                invoice_count=bucket["count"],
                undated=bucket["undated"],
                gross_balance=gross,
                credit_applied=applied,
            )
        )
    positions = tuple(positions_list)
    undated_total = sum(position.undated for position in positions)
    problems: tuple[dict[str, Any], ...] = ()
    if negative_credits:
        problems += (
            {
                "code": "negative_credit_not_added_to_chase",
                "br_ref": "BR-PAY-041",
                "detail": f"{negative_credits} account(s) here hold a NEGATIVE credit — a real "
                "debt (PO 2026-08-11, 'Yes, it's a real debt'). It is not floored anywhere and "
                "it renders signed wherever it is shown; it is simply not ADDED to this "
                "bill-based balance, because there is no bill behind it and a disconnect "
                "notice would state that bills are unpaid which are not. Chasing it is a "
                "separate act and this list does not pretend to be it.",
            },
        )
    if undated_total:
        # ⛔ **`DEF-PAY-6255` — THIS WAS `problems = (…)` AND IT ERASED THE
        # BRANCH ABOVE IT.** An assignment where every other branch in this
        # function concatenates, so on any tenant holding BOTH an undated bill
        # AND an account in negative credit the `negative_credit_not_added_to_
        # chase` sentence was silently dropped from the body — and S34 said
        # nothing about a real debt it had deliberately left out of the chase
        # (BR-PAY-041). Found by `CR-138-BRC07` `P4.1`: the SQL rewrite
        # reported both and a row-by-row comparison against this function
        # disagreed on exactly one field. **That comparison is the instrument
        # — an absence on the wire is invisible to every check this repo has
        # (hard rule 8's `DEF-CUS-3653`), and a second implementation of a
        # read is the only thing that can see a missing entry.**
        #
        # ⚠ **A DRAFT OF THIS COMMENT CITED `DEF-PAY-6246`, AND THAT NUMBER
        # WAS TAKEN BY ANOTHER LANE** for an unrelated `parse_list_params`
        # defect while this one was stopped — law 11's allocated-id clause,
        # which is exactly why an id is re-derived from the remote AT PUSH
        # TIME rather than when the comment is written.
        problems = (
            {
                "code": "unpaid_bill_without_due_date",
                "br_ref": "BR-PAY-032",
                "detail": f"{undated_total} unpaid bill(s) carry no due date, so BR-PAY-032's "
                '"today − the oldest unpaid invoice\'s due date" cannot place them. Their '
                "BALANCE is counted — the customer owes it — and they are excluded from the "
                "days-late anchor and from every ageing bucket rather than dated by a "
                "convention no rule states.",
            },
        ) + problems
    if not answered_all:  # pragma: no cover - billing publishes the read
        # DEF-2416 — said out loud rather than left as a silently-wrong balance.
        # This is the list a collection ladder runs on, so "we measured every
        # bill at its total because we could not ask what it asks for" is a fact
        # somebody has to see.
        problems = problems + (dict(_AMOUNT_DUE_PROBLEM),)
    return positions, problems


@dataclass(frozen=True)
class OpenInvoicePosition:
    """ONE open bill of this tenant, and what it still owes — CR-075 wave J.

    ⚠ **THE GRAIN IS THE BILL AND THAT IS A PRODUCT OWNER'S RULING, NOT A
    CONVENIENCE.** On 5 September 2026 the PO chose *one line per open invoice*
    over *one balance per account* and *one bucket per age band* for the cutover
    comparison (`US-RBS-008` §8). A legacy trial balance is written at invoice
    grain, so an account-grain comparison would net two errors of opposite sign
    inside one customer and report a tie — the one wrong answer a cutover check
    could give that an implementer would believe.

    `balance` is `amount_due − allocated`, exactly the subtraction
    `open_invoices_for_account` does for one account and `outstanding_positions`
    does rolled up to one. **The three are one derivation at three grains and
    they cannot disagree**, which is the whole reason this is here rather than a
    fourth `SUM` written inside a runbook.

    ⚠ **NOTHING IS NETTED AGAINST ACCOUNT CREDIT HERE, AND `outstanding_positions`
    DOES.** That function serves the collection ladder, where CR-059 CS-38 ruled
    that credit the utility already holds must come off the chase. A cutover
    reconciliation is comparing OUR bill against THEIR bill; account credit is a
    separate line of the legacy trial balance and netting it in here would move
    a difference from the credit line onto the receivables line, where nobody
    could find it. `gross` is therefore the figure and it says so by name.
    """

    account_id: Any
    invoice_id: Any
    number: str
    balance: Decimal
    issued_on: Any = None
    due_on: Any = None
    currency: str | None = None


def open_invoice_positions() -> tuple[
    tuple[OpenInvoicePosition, ...], tuple[dict[str, Any], ...]
]:
    """Every OPEN bill this tenant holds, one row each, in TWO queries.

    Returns `(positions, problems)`. `outstanding_positions` above is this same
    walk rolled up per account; this one keeps the bills apart because the
    cutover comparison is at bill grain (PO ruling, 5 September 2026).

    ⚠ **TWO QUERIES, NOT ONE PER BILL — `NFR-3` AND `NFR-5`.** A T5 utility has
    40,000 accounts and the file it is reconciled against is bigger than its
    account list, so a per-account loop here is the shape CLAUDE.md forbids by
    name. The bills come back as `values()` rows with `bill_payload` riding
    along, exactly as `outstanding_positions` fetches them and for the same
    reason: `amount_due_for` reads the budget level off that payload, and
    fetching model instances instead would answer the same question at one query
    per bill.

    ⚠ **`amount_due`, NEVER `total` (DEF-2416 / `BR-BIL-072`).** A budget-billing
    bill is issued at 292.87 and asks for 242.00; a cutover check measuring it at
    292.87 would report a $50.87 difference on every levelled customer on the
    estate, and an implementer would spend the go-live weekend chasing a
    difference this product invented.

    ⚠ **A BILL WITH NO ISSUE DATE IS KEPT, WITH ITS DATE NULL.**
    `open_invoices_for_account` DROPS one, because an allocator cannot place an
    undated bill in an oldest-first queue and money must never be applied to a
    bill whose position is unknown. A reconciliation has no queue and no money
    moving: dropping it would hide a bill the legacy file lists, and a missing
    bill is exactly what a cutover check exists to find. The two dispositions
    differ because the two questions differ, and that is stated here so the next
    reader does not "fix" one to match the other.
    """
    queryset = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - billing publishes it
        return (), (
            {
                "code": "billing_publishes_no_invoice_read",
                "br_ref": "BR-PAY-010",
                "detail": f"apps.{BILLING_MODULE}.selectors.{INVOICE_QUERYSET_READ} is not "
                "published, so the open bills a cutover is reconciled against cannot be read. "
                "The check reports that it cannot answer rather than comparing against an empty "
                "list, which would read as 'the legacy system holds bills we do not'.",
            },
        )

    invoices = list(
        queryset()
        .filter(status__in=OPEN_INVOICE_STATUSES)
        .values(
            "id",
            "account_id",
            "invoice_no",
            "total",
            "issued_at",
            "due_date",
            "currency",
            "bill_payload",
        )
    )
    if not invoices:
        return (), ()

    from django.db.models import Sum

    from apps.payments import models as payment_models

    allocated = {
        row["invoice_id"]: row["total"] or ZERO
        for row in payment_models.Allocation.objects.filter(
            invoice_id__in=[invoice["id"] for invoice in invoices]
        )
        .values("invoice_id")
        .annotate(total=Sum("amount"))
    }

    positions: list[OpenInvoicePosition] = []
    answered_all = True
    for invoice in invoices:
        total = _as_decimal(invoice["total"])
        due, answered = _amount_due(
            _BillFacts(total=total, bill_payload=invoice.get("bill_payload")), total=total
        )
        answered_all = answered_all and answered
        balance = due - allocated.get(invoice["id"], ZERO)
        if balance <= ZERO:
            continue  # settled — it owes nothing and is not an open bill
        issued_at = invoice["issued_at"]
        positions.append(
            OpenInvoicePosition(
                account_id=invoice["account_id"],
                invoice_id=invoice["id"],
                number=str(invoice["invoice_no"] or invoice["id"]),
                balance=balance,
                issued_on=issued_at.date() if issued_at is not None else None,
                due_on=invoice["due_date"],
                currency=invoice["currency"],
            )
        )

    problems: tuple[dict[str, Any], ...] = ()
    if not answered_all:  # pragma: no cover - billing publishes the read
        problems = (dict(_AMOUNT_DUE_PROBLEM),)
    return tuple(positions), problems


def invoice_numbers(invoice_ids: Any) -> dict[Any, str | None]:
    """`{invoice_id: invoice_no}` for the bills an allocation names.

    The S33 "Applied to" column prints a NUMBER (`BL-2607-018204`) and this
    module stores an id. The number is billing's fact, so it is read through
    billing's own published tenant-scoped queryset BY NAME — the same
    resolution `_rows_from_billing` falls back to — rather than by walking the
    reviewed cross-module FK into billing's ORM from a serializer (B1).

    A bill whose number cannot be read maps to None rather than being dropped:
    the allocation still happened and its AMOUNT is a fact about a customer's
    money, so the row shows what was paid and states that the label is missing.
    An empty input costs no query.
    """
    wanted = [invoice_id for invoice_id in invoice_ids if invoice_id is not None]
    if not wanted:
        return {}
    queryset = _resolve(BILLING_MODULE, INVOICE_QUERYSET_READ)
    if queryset is None:  # pragma: no cover - billing publishes it
        return {}
    return {
        row["id"]: row["invoice_no"]
        for row in queryset().filter(pk__in=wanted).values("id", "invoice_no")
    }


#: ⛔ **WHICH ACCOUNT ONE BILL BELONGS TO — the read that had no publisher, and
#: the reason `gateway.charge_guest_bill` could not be written until now.**
#:
#: `apps/portal/guest_api.bill_pay` takes a bill number off a piece of paper a
#: stranger is holding and asks the rails to charge a card for it. Everything
#: else that call needs already existed; the ONE missing step was **bill number
#: → the account the payment is recorded against**, and `apps/payments` had no
#: published way to take it.
#:
#: ════════════════════════════════════════════════════════════════════════
#: THE DECISION, WRITTEN HERE BECAUSE THIS FILE IS THE RECORD
#: ════════════════════════════════════════════════════════════════════════
#: **The ANSWER was never in doubt and is not a judgment.** `invoices` carries
#: `account_id` and B2 §2 makes it one column: an invoice belongs to exactly
#: ONE account. There is no rule to choose, no rounding, no allocation and no
#: money in it — it is a fact the database already holds.
#:
#: **What WAS a judgment is whether payments may publish that read, and in what
#: shape.** Three ways were open and the third is what is written below:
#:
#:   1. **Let the gateway walk into billing's ORM.** Refused — B1 forbids it,
#:      `G6` fails the merge on a cross-module model import, and it would put a
#:      second understanding of *what counts as a payable bill* in a file whose
#:      whole job is to talk to a card processor.
#:   2. **Let the guest edge pass the account down** — `apps/portal` already
#:      resolves it for the masked name. Refused, and this is the one worth
#:      naming: **it would make the account a REQUEST-SHAPED value on a money
#:      path.** The edge would hand payments an account id derived from an
#:      unauthenticated caller's input, and the rails would have no way to tell
#:      a resolved one from a supplied one. Where a stranger's money lands must
#:      be decided by the module that owns the money, from the database, every
#:      time.
#:   3. **Publish it HERE, narrow, beside the other billing facts payments
#:      already reads.** Chosen. It is the same boundary, the same by-name
#:      resolution and the same reviewed cross-module edge as every other read
#:      on this seam, and it adds no new kind of coupling — only one more fact.
#:
#: **AND IT IS NOT AN ALLOCATION INSTRUCTION.** This answers *whose account*,
#: never *which bill the money settles*. A payment recorded from it meets the
#: account's OLDEST open bill first under `BR-PAY-001`, through the one
#: allocator every other payment in the product goes through — so a guest
#: paying `$142.18` against `BL-2608-0141` while a `$18.00` July bill is still
#: open settles July first and leaves `$124.18` on August. That is the signed
#: rule doing its job; a `targets=` written here for the guest path would be a
#: second answer to *what did this customer pay*, and the two would disagree
#: the day somebody widened one of them.
BILL_OWNER_READ = INVOICE_QUERYSET_READ


@dataclass(frozen=True)
class BillOwner:
    """Whose account one bill number names, and the two facts that travel with it.

    ⚠ **DELIBERATELY NARROW, BECAUSE THE CALLER IS AN UNAUTHENTICATED SURFACE.**
    It carries no total, no balance, no customer, no address and no status word.
    `apps/portal` already has `BR-CWP-019`'s allow-list for what a stranger may
    be TOLD; this is what the RAILS need in order to record a payment, and the
    two lists have no business growing into each other. A field added here that
    a screen wanted would be a disclosure decision taken in the wrong module.
    """

    #: The account the payment is recorded against. B2 §2's own column.
    account_id: Any
    #: The bill the person was looking at — carried so a caller can name it on a
    #: receipt, NOT so it can be aimed at. See `BILL_OWNER_READ` above.
    invoice_id: Any
    #: The number as billing holds it, rather than as the caller typed it.
    number: str
    #: The bill's own CHAR(3) code, or None when it states none. Hard rule 2 —
    #: a currency rides WITH the amount and is never assumed, and least of all
    #: from a request body on a public form.
    currency: str | None = None


def account_for_bill_number(number: Any) -> BillOwner | None:
    """The account one bill number belongs to — or **None for every miss**.

    ⚠ **ONE ANSWER FOR EVERY KIND OF MISS, AND THAT IS THE SECURITY STORY.**
    An unknown number, another utility's number, a DRAFT, a VOID bill and one
    that has been CORRECTED all answer None, indistinguishably. `US-CWP-003`
    TC-2 states the reason for the surface above: *"a different message would
    confirm the bill number exists"* — and a seam that distinguished them would
    hand the edge the very thing the edge is careful not to say.

    ⚠ **A DRAFT CARRIES A NUMBER, SO "IT HAS A NUMBER" IS NOT "SOMEBODY MAY PAY
    IT".** `BR-BIL-063` allocates the number when the DRAFT is created (PO
    2026-08-11, *"Give a running number always even for Draft"*), so the status
    filter is doing real work rather than tidying: without it a stranger could
    pay a bill that was never issued and nobody was ever sent.

    The set is `OPEN_INVOICE_STATUSES` — this module's OWN existing constant for
    *a bill that can still owe money* — rather than a second list written here.
    It already excludes `draft` (never issued), `void` (no longer owed) and
    `corrected` (replaced by a rebill, `BR-BIL-014`), each with its reason
    recorded where the constant is defined. A `paid` bill stays in and simply
    resolves to its account: whether it still owes anything is a payments
    question this seam answers elsewhere, and refusing it here would put two
    different definitions of *settled* in one file.

    ⚠ **THE TENANT IS IN THE QUERY.** `invoice_queryset` filters on
    `app.tenant_id` explicitly and RLS FORCE is the second, independent
    guarantee — which matters because the suite runs on SQLite, where there is
    no row-level security and a read that left the tenant to the database would
    have no test that could ever see it go wrong (hard-won law 14 in its second
    costume).

    `UNIQUE (tenant_id, invoice_no)` — partial, `WHERE invoice_no IS NOT NULL` —
    is what makes *the* account a well-formed phrase: a number resolves to at
    most one bill per tenant, so this never picks between two.
    """
    wanted = str(number or "").strip()
    if not wanted:
        return None
    queryset = _resolve(BILLING_MODULE, BILL_OWNER_READ)
    if queryset is None:  # pragma: no cover - billing publishes it
        return None
    row = (
        queryset()
        .filter(invoice_no=wanted, status__in=OPEN_INVOICE_STATUSES)
        .values("id", "account_id", "invoice_no", "currency")
        .first()
    )
    if row is None:
        return None
    return BillOwner(
        account_id=row["account_id"],
        invoice_id=row["id"],
        number=str(row["invoice_no"]),
        currency=row["currency"],
    )


#: Billing's own read of *which bills went out in this window*. Named as a
#: constant like every other read this seam resolves, so a rename on billing's
#: side fails here loudly rather than silently returning None.
INVOICES_ISSUED_BETWEEN_READ = "invoices_issued_between"


def invoices_issued_between(*, start: date, end: date, bill_type: str | None = None) -> Any:
    """Billing's queryset of the bills ISSUED inside a window, or None.

    ⚠ **THE FILTER IS BILLING'S AND IS NOT RE-COMPOSED HERE.** *Which statuses
    count as issued* and *which column dates the issue* are billing's facts;
    writing them again on this side is how two modules come to disagree about
    one period's revenue (hard-won law 5). This seam resolves
    `apps.billing.selectors.invoices_issued_between` and adds nothing.

    ⚠ **A QUERYSET COMES BACK AND NOTHING IS MATERIALISED** — the caller
    composes it into a subquery, exactly as `OPEN_AMOUNTS_QUERYSET_READ` above
    is used, so a forty-thousand-bill period costs one statement.

    `None` means billing publishes no such read — genuinely unanswerable, and a
    caller must not read it as an empty window.
    """
    read = _resolve(BILLING_MODULE, INVOICES_ISSUED_BETWEEN_READ)
    if read is None:
        return None
    return read(start=start, end=end, bill_type=bill_type)


def allocated_so_far(invoice_id: Any) -> Decimal:
    """Σ of THIS module's allocation rows against one bill.

    Payments' own table, so this is not a cross-module read at all — it is the
    half of "what is still open" that billing structurally cannot answer
    (OQ-113). Reversing rows are negative (BR-PAY-031), so the sum is the net
    position and a reapplied payment correctly re-opens the bill it left.
    """
    from django.db.models import Sum

    from apps.payments import models

    total = models.Allocation.objects.filter(invoice_id=invoice_id).aggregate(total=Sum("amount"))[
        "total"
    ]
    return total if total is not None else ZERO


def allocated_for_invoices(invoice_ids: Any) -> dict[str, Decimal]:
    """Σ of THIS module's allocation rows against EACH of many bills, ONE query.

    `CR-101-BRC03` §06 — the Fix a bill wizard's step 1 draws the bills a scope
    resolves to as `BILL · PERIOD · AMOUNT · PAID · STATE` (p133 of the Billing
    blueprint), and PAID is this module's fact, not billing's (OQ-113). The
    per-bill form is `allocated_so_far` above; this is the same sum grouped by
    bill so a PAGE of bills costs one statement rather than one per row
    (`NFR-3`, the shape `_credit_positions` already takes for S34).

    Keyed by the bill id AS A STRING, because the caller is on the other side
    of a seam and compares ids it received as text. A bill with NO allocation
    row is ABSENT from the map rather than present at zero — the caller reads
    absence as `0.00` (nothing has been paid against it), which is a true
    answer over this module's own append-only table. Reversing rows are
    negative (BR-PAY-031), so each figure is the NET position.

    `invoice_ids` may be a list of ids or a queryset that yields them: Django
    renders a queryset as a subquery, so a whole bill run's paid total crosses
    the boundary as ONE statement and never as a 40,000-id list.
    """
    from django.db.models import Sum

    from apps.payments import models
    from apps.payments import selectors as payment_selectors

    # CLAUDE.md rule 1 — explicit, and REFUSED rather than defaulted when no
    # tenant is set (`selectors._tenant_id` is the module's one statement of
    # that refusal); RLS FORCE is the second guarantee, never the first.
    tenant_id = payment_selectors._tenant_id()
    return {
        str(row["invoice_id"]): row["total"] if row["total"] is not None else ZERO
        for row in (
            models.Allocation.objects.filter(tenant_id=tenant_id, invoice_id__in=invoice_ids)
            .values("invoice_id")
            .annotate(total=Sum("amount"))
        )
    }


def _day_of(moment: Any) -> Any:
    """A stored moment's calendar DAY in the deployment's time zone; None stays None."""
    if moment is None:
        return None
    from django.utils import timezone as dj_timezone

    return dj_timezone.localtime(moment).date() if dj_timezone.is_aware(moment) else moment.date()


def receipts_for_invoices(invoice_ids: Any) -> dict[str, list[dict[str, Any]]]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-10200` — what MET each of many bills,
    and WHEN the money arrived: `{invoice_id: [{amount, arrived_on,
    recorded_on}]}`, one entry per payment, net of its reversing rows
    (BR-PAY-031), payments whose net against the bill is zero or less left out.

    Billing's late fee needs *when* the money reached the utility, not only
    *how much* (BR-BIL-071, PO 2026-08-11: *"you llook at actual date for late
    fees not posting date"*), and both dates are this module's facts:
    `arrived_on` is the payment's `cleared_at` day — the column's own
    definition, *"when the MONEY was actually received"* — and `recorded_on`
    is its `posted_at` day. Billing decides lateness; this only reports.

    ONE statement per call. `invoice_ids` may be a list or a queryset (read as
    a subquery), as `allocated_for_invoices` takes it. Tenant-scoped by name
    first and by RLS second (hard rule 1)."""
    from django.db.models import Sum

    from apps.payments import models
    from apps.payments import selectors as payment_selectors

    tenant_id = payment_selectors._tenant_id()
    rows = (
        models.Allocation.objects.filter(tenant_id=tenant_id, invoice_id__in=invoice_ids)
        .values("invoice_id", "payment_id", "payment__cleared_at", "payment__posted_at")
        .annotate(net=Sum("amount"))
    )
    out: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        net = row["net"] if row["net"] is not None else ZERO
        if net <= ZERO:
            continue
        out.setdefault(str(row["invoice_id"]), []).append(
            {
                "amount": net,
                "arrived_on": _day_of(row["payment__cleared_at"]),
                "recorded_on": _day_of(row["payment__posted_at"]),
            }
        )
    return out


def payment_statuses_after_cutoff(
    account_ids: Any, *, period_end: Any, bill_date: Any
) -> dict[str, list[str]]:
    """`{account_id: [status, ...]}` of the payments posted after a run's
    cut-off, for MANY accounts, ONE query (DEF-BIL-8651).

    The bulk run's *Paid after cut-off* asks billing to put a payment on THIS
    bill, and a bill reads payments only through their allocations. A
    `processing` payment has no clearing date and meets no bill
    (`services.record_payment`: *"allocating money that has not arrived would
    take a bill out of arrears on the strength of an uncleared cheque"*), so
    billing needs this module's own word for whether the money has arrived
    before it lets *Apply to this bill* stand.

    Asked BY ACCOUNT AND WINDOW, the same window and the same exclusions the
    Check's own finding uses (`bill_run_checks.paid_after_cutoff`), and NOT by
    payment number: `payment_no` is nullable, and a payment without one would
    otherwise be unaskable and refused although it had cleared. An account
    with no such payment is ABSENT, never guessed.
    """
    from apps.payments import bill_run_checks, models
    from apps.payments import selectors as payment_selectors

    ids = [str(one) for one in (account_ids or ()) if one]
    if not ids or period_end is None or bill_date is None:
        return {}
    out: dict[str, list[str]] = {}
    for account_id, status in (
        models.Payment.objects.filter(
            tenant_id=payment_selectors._tenant_id(),
            account_id__in=ids,
            type=models.PAYMENT_TYPE_PAYMENT,
            reverses_payment__isnull=True,
            posted_at__date__gt=period_end,
            posted_at__date__lte=bill_date,
        )
        .exclude(status__in=bill_run_checks._NOT_MONEY)
        .values_list("account_id", "status")
    ):
        out.setdefault(str(account_id), []).append(str(status))
    return out


def allocated_total_for_invoices(invoice_ids: Any) -> Decimal:
    """Σ of THIS module's allocation rows against ALL the listed bills, ONE query.

    The totals row of the same step-1 table (*"Six bills · $1,454.10 ·
    $904.50"*): the second figure. Computed in SQL over the whole scope rather
    than summed from the page the clerk is looking at, because a run at T5 is
    40,000 bills and a page is fifty (`NFR-3`). Same tenant scoping, same
    signed-net reading as `allocated_for_invoices`; `0.00` is a true answer
    (no allocation row points at any of these bills).
    """
    from django.db.models import Sum

    from apps.payments import models
    from apps.payments import selectors as payment_selectors

    tenant_id = payment_selectors._tenant_id()
    total = models.Allocation.objects.filter(
        tenant_id=tenant_id, invoice_id__in=invoice_ids
    ).aggregate(total=Sum("amount"))["total"]
    return total if total is not None else ZERO


def open_invoices_for_account(account_id: Any) -> OpenPosition:
    """Every bill of `account_id` that still owes money, oldest first.

    Tenant scoping is billing's published read's own (`invoice_queryset` filters
    on `app.tenant_id` explicitly and RLS FORCE is the second, independent
    guarantee), and this module's `allocations` sum runs under the same session
    GUC — so a cross-tenant account id resolves to no bills rather than to
    somebody else's.

    Bills are returned in ISSUE order and every one of them carries its date, so
    `allocation.py` orders by date rather than by the caller's sequence. A bill
    with no `issued_at` is dropped WITH a problem code rather than placed by a
    convention no rule states — the allocator refuses a mixed dated/undated list
    outright, and one undated bill must not make a whole account unallocatable.
    """
    rows, seam_problems = _rows_from_billing(account_id)
    return _open_position_from(rows, seam_problems, allocated_so_far)


def _open_position_from(rows: Any, seam_problems: Any, allocated_of: Any) -> OpenPosition:
    """`open_invoices_for_account`'s arithmetic over rows already read — the ONE
    statement of it, shared with `open_invoices_for_accounts` (`DEF-BIL-8696`),
    so the per-account read and the whole-run read cannot disagree.
    `allocated_of(invoice_id)` is Σ allocations against that bill."""
    problems: list[dict[str, Any]] = [dict(problem) for problem in seam_problems]

    invoices: list[OpenInvoice] = []
    undated: list[str] = []
    for row in rows:
        total = _as_decimal(row["total"])
        # ⛔ DEF-2416 / BR-BIL-072 — the bill is measured at what it ASKS for,
        # never at what it totals. Identical for every bill that is not
        # budget-billing; the LEVEL for one that is (WE-8: 292.87 → 242.00).
        amount_due = _as_decimal(row["amount_due"])
        allocated = allocated_of(row["id"])
        balance = amount_due - allocated
        if balance <= ZERO:
            continue  # settled: not an open bill, and never a 0.00 allocation row
        if row.get("issued_on") is None:
            undated.append(str(row["number"]))
            continue
        invoices.append(
            OpenInvoice(
                number=str(row["number"]),
                balance=balance,
                issued_on=row["issued_on"],
                composition=_composition_from(row.get("composition"), allocated=allocated),
                invoice_id=row["id"],
                total=total,
                amount_due=amount_due,
                allocated=allocated,
                currency=row.get("currency"),
                # DEF-PAY-6254 — the row has carried this since CR-059 CS-4 and
                # nothing read it. `.get` rather than `[...]`: one caller of
                # this loop supplies its own rows (`_rows_from_billing`'s cached
                # branch), and a KeyError there would refuse a payment over a
                # column a screen wants.
                due_on=row.get("due_on"),
            )
        )

    if undated:
        problems.append(
            {
                "code": "issued_bill_without_issue_date",
                "br_ref": "BR-PAY-001",
                "detail": f"bill(s) {undated} are issued and unpaid but carry no issue date, so "
                '"oldest open bill" cannot place them (BR-PAY-001). They are EXCLUDED from this '
                "allocation rather than ordered by a convention no rule states — one undated bill "
                "must not make the whole account unallocatable, and the money is never applied to "
                "a bill whose position in the queue is unknown.",
            }
        )
    return OpenPosition(invoices=tuple(invoices), problems=tuple(problems))


def _account_batches(account_ids: Any) -> tuple[list[str], list[Any]]:
    """`(keys, filters)` for a read over MANY accounts (`DEF-BIL-8696`).

    `keys` is every account asked about, as text. `filters` is what each
    `account_id__in` takes: the caller's own QUERYSET once, when it handed one
    in — Django renders it as a SUBQUERY, so a whole bill run's accounts cross
    the boundary as one statement rather than as 40,000 bound parameters
    (measured at 40,008 accounts: ~30 µs of Python per parameter, 7 s for one
    Sign off read) — else the listed ids in chunks of `_BATCH_IDS`."""
    if hasattr(account_ids, "query"):
        return [str(account_id) for account_id in account_ids if account_id], [account_ids]
    keys = [str(account_id) for account_id in (account_ids or ()) if account_id]
    return keys, [keys[start : start + _BATCH_IDS] for start in range(0, len(keys), _BATCH_IDS)]


def open_invoices_for_accounts(account_ids: Any) -> dict[str, OpenPosition]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8696` — `open_invoices_for_account` for
    a whole bill run: `{account_id: OpenPosition}`, every account asked about a
    key, in TWO statements per batch whatever the run's size (NFR-3).

    THE SAME ANSWER, NOT A SECOND ARITHMETIC. The rows are the per-account
    read's own (billing's issued and paid bills, oldest first, with what each
    ASKS for), and the open balance, the settled-bill drop and the undated-bill
    problem are `_open_position_from` — the function the per-account read now
    calls too. Two things are read differently, and both are the same fact:

      * what a bill ASKS is billing's `amount_due_expression` in SQL (through
        `open_invoice_amounts_queryset`) rather than `amount_due_for` per bill
        — ONE rule in two renderings that billing's own test holds bill by bill
        (`test_cr138_p41_amount_due_expression.py`), so no bill's payload is
        pulled into Python;
      * Σ allocations is `allocated_for_invoices`, grouped, rather than
        `allocated_so_far` per bill — the same sum over the same rows.

    Where billing publishes the preferred per-account read, or not the amounts
    queryset, each account is asked one by one exactly as before — slower,
    never different. `account_ids` may be a queryset of account ids (see
    `_account_batches`)."""
    keys, filters = _account_batches(account_ids)
    amounts = _resolve(BILLING_MODULE, OPEN_AMOUNTS_QUERYSET_READ)
    if _resolve(BILLING_MODULE, OPEN_INVOICES_READ) is not None or amounts is None:
        return {key: open_invoices_for_account(key) for key in keys}
    rows_by_account: dict[str, list[dict[str, Any]]] = {key: [] for key in keys}
    allocated: dict[str, Decimal] = {}
    for scope in filters:
        bills = amounts(OPEN_INVOICE_STATUSES).filter(account_id__in=scope)
        allocated.update(allocated_for_invoices(bills.values("id")))
        for row in bills.order_by("issued_at", "id").values(
            "id", "account_id", "invoice_no", "total", "amount_due", "issued_at", "due_date",
            "currency",
        ):
            key = str(row["account_id"])
            if key not in rows_by_account:
                continue
            rows_by_account[key].append(
                {
                    "id": row["id"],
                    "number": row["invoice_no"] or str(row["id"]),
                    "total": row["total"],
                    "amount_due": row["amount_due"],
                    "issued_on": row["issued_at"].date() if row["issued_at"] is not None else None,
                    "due_on": row["due_date"],
                    "currency": row["currency"],
                }
            )

    def allocated_of(invoice_id: Any) -> Decimal:
        return allocated.get(str(invoice_id), ZERO)

    return {
        key: _open_position_from(rows, (_composition_unavailable(),), allocated_of)
        for key, rows in rows_by_account.items()
    }


# ══════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 · P4.25 — THE CREDIT-NOTE HALF OF *"EVERYTHING GIVEN BACK"*
# ══════════════════════════════════════════════════════════════════════════
#: ⛔ **PAYMENTS MUST NOT QUERY `credit_notes`, AND THIS IS WHY THE READ IS
#: HERE RATHER THAN IN `refunds_and_credits.py`.** B2 §2 makes cross-module FKs
#: the reviewed interface set and B1 makes cross-module reads service functions
#: only; `credit_notes` is billing's table, billing's sign constraint
#: (`BR-BIL-074`, `amount <= 0`) and billing's immutability trigger. A
#: `CreditNote.objects` anywhere under `apps/payments/` is the boundary drawn on
#: a diagram and not in the code.
#:
#: Resolved BY NAME at call time, like every other read in this file, so nothing
#: binds the two modules at import and the edge is greppable from both sides.
CREDIT_NOTE_PAGE_READ = "credit_note_page"
CREDIT_NOTE_COUNT_READ = "credit_note_count"

#: What the seam says when billing has not published the pair. It is a PROBLEM
#: on the response rather than an exception, for `_AMOUNT_DUE_PROBLEM`'s reason:
#: the refunds half of the list is payments' own and is perfectly answerable, so
#: refusing the whole list would hide rows this module owns behind a neighbour's
#: absence. **A list missing one of its two sources says so, in a sentence, on
#: every page** — an unannounced short list is `G32`'s shape, a true zero over a
#: scope it silently excluded.
CREDIT_NOTES_UNAVAILABLE = "credit_notes_read_unavailable"

_CREDIT_NOTES_PROBLEM = {
    "code": CREDIT_NOTES_UNAVAILABLE,
    "br_ref": "B1 · B2 §2",
    "detail": "billing publishes no `selectors.credit_note_page`/`credit_note_count`, so this "
    "list is REFUNDS ONLY and its total counts refunds only. Payments may not read "
    "`credit_notes` directly to fill the gap — that is the boundary this seam exists to keep.",
}


def credit_notes_count() -> tuple[int, tuple[dict[str, Any], ...]]:
    """How many credit notes this tenant has — billing's `COUNT(*)`, or a problem.

    Returns the pair rather than a bare int so a caller cannot report a total
    that silently excludes a whole source. `0` and *"I could not ask"* are
    different answers to *"how much have we given back?"*, and a screen that
    rendered them the same would tell a clerk a customer got nothing.
    """
    read = _resolve(BILLING_MODULE, CREDIT_NOTE_COUNT_READ)
    if read is None:
        return 0, (dict(_CREDIT_NOTES_PROBLEM),)
    return int(read()), ()


def credit_notes_page(
    *, offset: int = 0, limit: int
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """ONE PAGE of billing's credit notes, taken in BILLING's database.

    ⚠ **THE PAGE IS SQL ON THE FAR SIDE OF THE SEAM, NOT A SLICE ON THIS ONE**
    (`NFR-3`). `offset` and `limit` are passed THROUGH to
    `selectors.credit_note_page`, which applies them as `LIMIT`/`OFFSET`; this
    function never asks for a row it is not going to use. A seam that fetched
    everything and sliced here would move the breach one module along and leave
    it looking fixed.

    Rows are billing's own published dicts, forwarded WHOLE rather than
    re-shaped: a seam that cherry-picked members would silently drop the next
    one billing adds, which is `notice_history_row`'s recorded reason for
    forwarding `detail` intact.
    """
    read = _resolve(BILLING_MODULE, CREDIT_NOTE_PAGE_READ)
    if read is None:
        return (), (dict(_CREDIT_NOTES_PROBLEM),)
    return tuple(dict(row) for row in read(offset=offset, limit=limit)), ()


# ══════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 · P4.12 — A **DOOR** TO THE CREDIT PATH. NOT A COPY OF IT.
# ══════════════════════════════════════════════════════════════════════════
#: ⛔ **PO RULING, 2026-09-22, VERBATIM: *"we can not have two path for 1
#: capabilities wew will confuse user"*.** That sentence is why this block is
#: forty lines of description and NO arithmetic.
#:
#: **THE CREDIT PATH ALREADY EXISTS AND HAS EXACTLY ONE IMPLEMENTATION.**
#: `apps/billing/corrections.execute_credit_only` writes the credit note,
#: allocates its `Credit memo #` and emits the balanced pair
#: (DR write-off / CR customer credit) through the ledger seam. It is reached
#: through billing's correction CASE — open, approve, execute — and that is its
#: only door. **Nothing here re-implements any part of it**, which was checked
#: before a line was written: `execute_credit_only` has one definition and its
#: callers are `bulk_corrections` and `single_correction`, both inside billing.
#:
#: **WHAT WAS MISSING IS THE SECOND PLACE IT IS REACHABLE FROM.** A clerk
#: closing an account in credit stands on the payments Refunds tab and is
#: offered ONE way out — a cheque. The cheaper option is invisible from where
#: the choice is made, which is the blueprint's own finding for 6·1
#: (`P4.10`: *"Credit beside Raise"*).
#:
#: ⚠ **AND THE THING A PAYMENTS SCREEN CANNOT KNOW ON ITS OWN IS THAT A CREDIT
#: IS RAISED AGAINST A BILL, NOT AGAINST AN ACCOUNT.** `execute_credit_only`
#: takes an `invoice`. So *"give them a credit instead"* is not one click from
#: the Refunds tab: the clerk must name a bill. This read answers exactly that —
#: **which of this account's bills a goodwill credit could be raised against,
#: and the address of the one path** — and mints **no write verb whatsoever**.
CREDIT_PATH_REASON = "goodwill"
CREDIT_PATH_CLASS = "credit_only"

#: The one path, as data a screen can route on rather than a sentence it would
#: have to parse. These are billing's OWN mounted routes (`apps/billing/
#: corrections_api.urlpatterns`) and payments neither mirrors nor proxies them:
#: the browser calls billing directly, which is what makes this a DOOR.
CREDIT_PATH_STEPS: tuple[dict[str, str], ...] = (
    {"step": "open", "method": "POST", "path": "corrections"},
    {"step": "approve", "method": "POST", "path": "corrections/{case_id}/approve"},
    {"step": "execute", "method": "POST", "path": "corrections/{case_id}/execute"},
)

CREDIT_PATH_UNAVAILABLE = "credit_path_needs_an_open_bill"


def credit_path_for_account(account_id: Any) -> dict[str, Any]:
    """WHERE the one credit path is, and which bills it can be raised against.

    **A DOOR, NOT A COPY** (`P4.12`; PO 2026-09-22, *"we can not have two path
    for 1 capabilities wew will confuse user"*). This function:

      * computes **no money** — every figure on it is billing's own, forwarded;
      * writes **nothing**, and mints no write verb. The write is
        `POST /corrections…`, billing's, and always was;
      * re-implements **no part** of `execute_credit_only`. A second
        implementation is the thing the ruling forbids, and this lane stopped
        and reported rather than writing one.

    It answers the two questions a payments screen cannot answer for itself:
    **is the credit path available on this account**, and **against which
    bill**. A goodwill credit is raised against a BILL (`execute_credit_only`
    takes an `invoice`), so an account with no open bill has no credit to
    offer — and that is a REFUSAL WITH A REASON rather than a missing button,
    because *"why can I not give them a credit?"* is the question a greyed-out
    control leaves a clerk holding (`BR-SHL-025`).

    ⚠ **`available: false` IS NOT *the feature is unbuilt*.** It means this
    ACCOUNT has nothing to credit today. A screen must print the reason and not
    a shrug.
    """
    position = open_invoices_for_account(account_id)
    problems = [dict(problem) for problem in position.problems]
    bills = [
        {
            # B14 rule 31 — `number` is what a clerk picks from; the id is the
            # value the correction case is opened WITH and is never drawn.
            "invoice_id": str(invoice.invoice_id),
            "number": invoice.number,
            "issued_on": invoice.issued_on.isoformat() if invoice.issued_on else None,
            "total": f"{invoice.total:.6f}",
            "balance": f"{invoice.balance:.6f}",
            "currency": invoice.currency,
        }
        for invoice in position.invoices
    ]
    if not bills:
        problems.append(
            {
                "code": CREDIT_PATH_UNAVAILABLE,
                "br_ref": "BR-BIL-014 · BR-BIL-041",
                "detail": "a goodwill credit is raised against a BILL — "
                "`corrections.execute_credit_only` takes an invoice — and this account has "
                "no open bill to raise one against. The refund path is unaffected.",
            }
        )
    return {
        "account_id": str(account_id),
        "available": bool(bills),
        # The reason code that DERIVES the class (BR-BIL-041). Named here so the
        # screen sends billing's own vocabulary and billing keeps deriving the
        # mechanism — a payments screen that picked the CLASS would be choosing
        # a mechanism, which BR-BIL-041 gives to the reason.
        "reason_code": CREDIT_PATH_REASON,
        "correction_class": CREDIT_PATH_CLASS,
        "steps": [dict(step) for step in CREDIT_PATH_STEPS],
        "bills": bills,
        "problems": problems,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-001@f4d2b18 (the four payments sources — B2 §2 + Addenda r12/r14 · EP-PAY-01-record-payments.md · 08-payments/02-business-rules.md · 08-payments/03-field-map.md)
# generated: 2026-08-11 by Eng-Lead (W4 payments closed-loop lane) · AMENDED 2026-09-01 by the CR-059 task 11 lane (CS-4 — `OpenInvoice` carries `total`, `allocated` and the bill's own CHAR(3) `currency` so `GET /accounts/{id}/open-bills` can serve them; three ADDITIVE fields on a structural Protocol, no figure moves, the allocator still reads `balance` alone)
# checklist: A✔ B✔ C✔ D=deferred(a seam — it serves no route of its own; its callers do) E✔ F✔ G✔ H=deferred(PO 2026-08-09)  [E CLOSED 2026-08-11: `invoice_numbers` feeds S33's "Applied to" column]
# gates: ruff✔ black✔ · tests/test_us_pay_001_record_payment.py — the oldest-first order and the composition path were each driven RED before being trusted green (hard-won law 7)
# exceptions: (1) THE PREFERRED READ IS NOT PUBLISHED. `apps.billing.selectors.
#         issued_invoices_for_account` is the contract stated above and billing
#         does not have it; the seam falls back to billing's own published
#         tenant-scoped `invoice_queryset` and reads four facts along the
#         reviewed cross-module edge (B2 §2). No billing model is imported (G6
#         rule 4) and NO billing file was edited — another lane is in
#         apps/billing right now. REPORTED so the billing lane can publish the
#         read; this seam picks it up with no edit.
#         (2) NO WITHIN-INVOICE COMPOSITION is stated today, and it is reported
#         as `invoice_composition_unavailable` rather than invented: the
#         kind→class map is unpublished and `minimum_adjustment` maps onto no
#         named class (OQ-128), and the fourth class's membership is the
#         tenant's, in the ledger, and unpublished (BR-PAY-038). Absence is a
#         LEGAL input — B5 GT-7's own shape — so the loop stays closed.
#         (3) A PART-PAID BILL CANNOT STATE A COMPOSITION even when billing
#         publishes one, because `allocations` records no class (OQ-129). The
#         seam states one only for bills with no prior allocation.
#         (4) AN ISSUED BILL WITH NO `issued_at` IS EXCLUDED with a problem code
#         rather than ordered by an invented convention.
#         (5) [2026-09-01] ⛔ **EVERY BALANCE HERE IS NOW MEASURED AT WHAT THE
#         BILL ASKS FOR — DEF-2416 FIXED.** This entry said *"measured at
#         `invoice.total` … filed and NOT fixed"* until the same day. Both reads
#         (`open_invoices_for_account` and `outstanding_positions`) call
#         billing's published `selectors.amount_due_for` — the PO's *"Level is
#         due"*, BR-BIL-072, closing OQ-140 and DEF-062 — so a budget bill is
#         measured at its LEVEL. On ❄️ WE-8 that is 242.00 against a 292.87
#         total, and a customer who pays the 242.00 now owes nothing instead of
#         being chased for the 50.87 variance. It DOES move what a payment
#         settles, which CR-059 CS-4 excluded in terms and this defect fix does
#         not: an overpayment beyond the ask carries as account credit under
#         BR-PAY-010, exactly as any other overpayment does. No B4/B5 figure
#         moved, no rounding site was added, and the allocator still reads
#         `balance` alone. Proved RED on the figures first
#         (tests/test_def2416_level_is_due.py quotes the transcript).
#         (6) [2026-09-01] THE RULE IS NOT COPIED HERE. If billing ever stops
#         publishing `amount_due_for`, the seam falls back to the issued total
#         and REPORTS `bill_amount_due_unavailable` rather than re-deriving the
#         level from `bill_payload` itself — a second copy of a ruled figure is
#         how two figures start disagreeing.
#         (7) [2026-09-05] ⛔ **THE BILL-NUMBER → ACCOUNT READ IS PUBLISHED
#         HERE, AND THE REASONING IS IN `BILL_OWNER_READ`'s OWN COMMENT ABOVE
#         RATHER THAN IN THE DECISION LOG** — the CR-068 lane F that added it
#         could not write that file. In one sentence for whoever transcribes it:
#         an invoice belongs to exactly ONE account, so the ANSWER is a fact and
#         not a judgment; what was a judgment is that PAYMENTS publishes the
#         read rather than the guest EDGE passing an account down, because the
#         caller is an unauthenticated form and where a stranger's money lands
#         must be decided by the module that owns the money, from the database,
#         every time. It is NOT an allocation instruction: no `targets=` is
#         passed, so BR-PAY-001's oldest-first walk is untouched and a guest
#         paying $142.18 against BL-2608-0141 with an open $18.00 July bill
#         settles July first and leaves $124.18 on August.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────


# ════════════════════════════════════════════════════════════════════════════
# CR-138-BRC07 `P4.1` — THE DEBTOR LIST, CUT IN SQL
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **WHY A SECOND WAY TO ANSWER THE SAME QUESTION, AND WHY THE FIRST ONE
# STAYS.** `outstanding_positions` above answers *"what does every listed
# account owe?"* by pulling every open bill of the tenant into Python. That is
# the right shape for its other three callers — `ladder.run_ladder`,
# `notices.py` and the cutover comparison all want the WHOLE set, and two of
# them are batch jobs with no page to cut to. It is the WRONG shape for a
# screen, and `CLAUDE.md` names it on its first page: *"Unpaginated ON PURPOSE
# … one row per DEBTOR at a utility under 3,000 connections"*, and it **sorts
# in Python, not SQL** — *"correct at T7, 13× short of T5"* (`DEF-PAY-4221`).
#
# ⚠ **AND THE MEASUREMENT SAYS THE SCREEN DID NOT ANSWER AT ALL AT THE TOP OF
# THE ICP, WHICH IS THE FINDING RATHER THAN THE FIX.** Measured on real
# PostgreSQL 16 (`10-scripts/cr138_p4_debtor_cost.py`, median of 3 after a
# discarded warm-up, 2026-09-23), one page of fifty:
#
#      2,046 debtors    before   3.089 s ·  2,041 statements
#                       after    0.232 s ·     13 statements
#     40,046 debtors    before  61.539 s · 40,041 statements
#                       after    3.746 s ·     12 statements
#
# `docker-entrypoint.sh` gives a web worker **60 seconds**
# (`GUNICORN_TIMEOUT:-60`), and **61.539 s is past it** — so at 40,046
# debtors, the top of T5 and the top of the ICP, this endpoint was not slow,
# it was KILLED. 2,046 debtors is two thirds of the OLD 3,000 ceiling, so
# three seconds of server time was already being spent inside the tier the
# comment called correct.
#
# ⚠ **`NFR-5` — THIS PAGES AND IT DOES NOT CAP.** There is no maximum account
# count, no `[:1000]`, and no per-tenant ceiling anywhere below. `per` clamps
# to `core.pagination.PAGE_SIZES` exactly as every other list does, and asking
# for page 800 of a 40,000-row list is a legal request that is answered.


@dataclass(frozen=True)
class AgeingBands:
    """A2 §S34's ageing bands, PASSED IN rather than restated here.

    `apps/payments/outstandings.py` owns the band names and their day
    boundaries and is the only place they are written down; this seam needs
    them to build the SQL `CASE`, and a second copy is how a tile and a row
    start disagreeing about what "61-90" means.
    """

    current: str
    #: `(bucket name, inclusive upper bound in days)`, ascending.
    thresholds: tuple[tuple[str, int], ...]
    overflow: str

    def names(self) -> tuple[str, ...]:
        return (self.current,) + tuple(name for name, _ in self.thresholds) + (self.overflow,)


@dataclass(frozen=True)
class OutstandingsPage:
    """ONE PAGE of debtors, and the tiles for the WHOLE filtered set.

    ⚠ **THE TILES ARE NOT A FOLD OVER `positions` AND MUST NOT BECOME ONE.**
    US-PAY-013 TC-1 requires the KPI strip to tie to the DEBT, not to the page,
    and the whole argument for leaving this list unpaginated was that a fold
    over the rows was the only way to guarantee it. It is not: `ageing`,
    `total_accounts` and `total_owed` below are SQL aggregates over exactly the
    same filtered set the page is cut from, computed in one more statement.
    """

    positions: tuple[OutstandingPosition, ...]
    #: `bucket -> (amount, account count)` over the whole filtered set.
    ageing: dict[str, tuple[Decimal, int]]
    total_accounts: int
    total_owed: Decimal
    problems: tuple[dict[str, Any], ...]
    #: The page actually served, which is the page ASKED FOR clamped into
    #: `[1, last]` — BR-SHL-011's *"invalid values fall back or clamp, NEVER
    #: error"*. A caller that asks for page 9,999 of a 41-page list is told
    #: which page it got rather than handed an empty body it has to interpret.
    page: int = 1


#: What a caller may order this list by, and what each one means in SQL. ⚠ The
#: set is SHORT ON PURPOSE and the absences are named: `account_no` and
#: `customer_name` live on customers' table, which this query does not join —
#: sorting on them would either join a second module's table inside billing's
#: queryset or sort a page in Python, and the second is the defect being fixed.
#: A screen that needs them is a change to this constant and to the join, not a
#: `rows.sort` anywhere.
OUTSTANDINGS_SORTS: tuple[str, ...] = ("balance", "days_late", "open_bills")

#: How many ids go into one `IN (…)` — a bound on a STATEMENT, never on the
#: answer (`NFR-5`). PostgreSQL's wire protocol caps a query's parameters at
#: 65,535, and a list built from a tenant's own size reaches that at T5.
_IN_CHUNK = 5000


def _debtor_positions(account_ids: Any = None) -> tuple[Any, dict[Any, Decimal]] | None:
    """THE DEBTOR STATEMENT — one lazy, grouped row per account that owes money.

    Values: `account_id` · `gross` · `oldest_due_on` · `invoice_count` ·
    `undated` · `credit_applied` · `net` (always > 0). Returns
    `(queryset, credit_by_account)`, or None when billing publishes no read.

    ⚠ **SPLIT OUT OF `outstanding_positions_page` ON 2026-10-17 SO THAT A
    SECOND SCREEN COULD ASK THE SAME QUESTION WITHOUT A SECOND ANSWER**
    (`DEF-CUS-10181`, PO: *"the band … comes from the oldest unpaid bill's due
    date — the same figure Who owes you uses"*). The Accounts list's Aging
    column composes this queryset as a correlated subquery; Who owes you cuts
    its page and its tiles from it. Every line below is the one that was in
    the page read, moved and not re-typed.
    """
    from django.db.models import (
        Case,
        Count,
        DecimalField,
        F,
        Min,
        OuterRef,
        Q,
        Subquery,
        Sum,
        Value,
        When,
    )
    from django.db.models.functions import Coalesce, Least

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    money = DecimalField(max_digits=18, decimal_places=6)
    published = _resolve(BILLING_MODULE, OPEN_AMOUNTS_QUERYSET_READ)
    if published is None:  # pragma: no cover - billing publishes it
        return None

    tenant_id = payment_selectors._tenant_id()
    bills = published(OPEN_INVOICE_STATUSES)
    if account_ids is not None:
        bills = bills.filter(account_id__in=list(account_ids))

    # ── one bill's OPEN balance ──────────────────────────────────────────
    allocated = Coalesce(
        Subquery(
            payment_models.Allocation.objects.filter(
                tenant_id=tenant_id, invoice_id=OuterRef("id")
            )
            .values("invoice_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1],
            output_field=money,
        ),
        Value(ZERO, output_field=money),
        output_field=money,
    )
    # `balance <= 0` is SETTLED and drops out here, exactly as the per-invoice
    # `continue` does in `outstanding_positions`.
    bills = bills.annotate(open_balance=F("amount_due") - allocated).filter(open_balance__gt=ZERO)

    # ── one account's position ───────────────────────────────────────────
    # `Min` ignores NULLs in SQL, which IS BR-PAY-032's rule rather than a
    # coincidence: a bill with no due date is counted in the balance and
    # excluded from the days-late anchor.
    positions = bills.values("account_id").annotate(
        gross=Sum("open_balance"),
        oldest_due_on=Min("due_date"),
        invoice_count=Count("id"),
        undated=Count("id", filter=Q(due_date__isnull=True)),
    )

    # ══════════════════════════════════════════════════════════════════════
    # CR-059 CS-38's CREDIT — THREE TENANT-WIDE AGGREGATES, NOT A SUBQUERY
    # ══════════════════════════════════════════════════════════════════════
    # ⚠ **THE OBVIOUS SHAPE IS THREE CORRELATED SUBQUERIES ON `account_id`,
    # AND IT IS TWENTY-TWO TIMES SLOWER. MEASURED, NOT ASSERTED.** Both forms
    # were built and timed against each other on real PostgreSQL 16 at 2,046
    # debtors, interleaved in one process, median of 3 after a discarded
    # warm-up (2026-09-23):
    #
    #     credit as three CORRELATED SUBQUERIES      18.522 s
    #     credit as three TENANT-WIDE AGGREGATES      0.823 s
    #
    # The plan says why: Django puts a non-aggregate annotation into the
    # `GROUP BY` key, so PostgreSQL evaluates each subplan **once per INVOICE
    # ROW** for a value that is constant inside the group. An index makes each
    # of those evaluations cheap; nothing makes them rare — which is also why
    # the `P4.5` migration ships one index and not five.
    #
    # ⚠ **AND THE SHAPE OF THE DATA IS WHAT MAKES THE ALTERNATIVE EXACT.** Only
    # a POSITIVE credit comes off a chase (CS-38), and an account in positive
    # credit is one that has OVERPAID: at 2,046 debtors there was **one**, and
    # at 40,046 there was also **one** (both counted, not assumed). So the
    # position is read for the whole tenant in the three grouped queries
    # `_credit_positions` already owns — the SAME statement of the rule rather
    # than a second one — and only the positive ones are carried into the
    # query, as a `CASE` over the group key.
    #
    # ⚠ **`NFR-5` — THE `CASE` HAS NO CEILING AND MUST NOT ACQUIRE ONE.** A
    # tenant where thousands of accounts sit in credit builds a longer `CASE`
    # and the read gets slower; it does not get WRONG, and no account is
    # dropped. A `[:500]` here would be the hard cap `NFR-5` forbids, and it
    # would silently stop taking real credit off real chases.
    credit_by_account = _credit_positions(None)
    positive_credit = {
        account_id: amount for account_id, amount in credit_by_account.items() if amount > ZERO
    }
    if positive_credit:
        held = Case(
            *[
                When(account_id=account_id, then=Value(amount, output_field=money))
                for account_id, amount in positive_credit.items()
            ],
            default=Value(ZERO, output_field=money),
            output_field=money,
        )
    else:
        held = Value(ZERO, output_field=money)
    positions = positions.annotate(
        credit_applied=Least(held, F("gross"), output_field=money)
    ).annotate(net=F("gross") - F("credit_applied"))
    positions = positions.filter(net__gt=ZERO)
    return positions, credit_by_account


#: The read the Accounts list's Aging column resolves BY NAME (`DEF-CUS-10181`).
DEBTOR_POSITIONS_READ = "debtor_positions_queryset"


def debtor_positions_queryset(account_ids: Any = None) -> Any:
    """`_debtor_positions`' queryset alone, LAZY — or None while billing is
    unwired. Who owes you's own statement: an account is in it exactly when
    that screen would list it, and `oldest_due_on` is BR-PAY-032's anchor."""
    built = _debtor_positions(account_ids)
    return None if built is None else built[0]


def live_bills_queryset() -> Any:
    """Every live bill (`OPEN_INVOICE_STATUSES` — issued or paid, never void or
    corrected), LAZY: `id · account_id · due_date · amount_due`. The Aging
    column asks it one thing — which bill was an account's FIRST — because
    that bill carried the migrated opening balance (OQ-530)."""
    published = _resolve(BILLING_MODULE, OPEN_AMOUNTS_QUERYSET_READ)
    return None if published is None else published(OPEN_INVOICE_STATUSES)


def outstanding_positions_page(
    *,
    as_of: date,
    bands: AgeingBands,
    bucket: str | None = None,
    bad_address_only: bool = False,
    account_ids: Any = None,
    page: int = 1,
    per: int | None = 50,
    sort: str = "balance",
    direction: str = "desc",
) -> OutstandingsPage:
    """Every debtor of this tenant, FILTERED, SORTED AND PAGED IN SQL.

    ⚠ **A FIXED NUMBER OF STATEMENTS, WHATEVER THE TENANT'S SIZE — measured
    at TWELVE for a whole page at 40,046 debtors and THIRTEEN at 2,046**,
    against 40,041 and 2,041 for the unpaged read it replaces. They are:
    three tenant-wide credit aggregates, one for the tiles, one for the page,
    one per chunk of negative-credit ids, and the batched reads the caller
    makes over the page's fifty accounts. **It is twelve rather than thirteen
    on the larger tenant because the chunk statement fires only when some
    account holds a NEGATIVE credit — the count follows the DATA's shape and
    never the tenant's SIZE, which is the whole claim.** None of them
    materialises a bill, a debtor or a sort key that is not on the answer.

    **The arithmetic is the same arithmetic** `outstanding_positions` does, and
    it is not re-typed: what a bill ASKS FOR comes from billing's own published
    `amount_due_expression` (BR-BIL-072 / `DEF-2416`), the allocations come off
    this module's own table, and the credit that comes off the chase is
    CR-059 CS-38's rule with BR-PAY-041 unfloored — a negative credit is still
    a real debt, still rendered signed everywhere, and still not ADDED to a
    bill-based chase.

    Tenant scoping is explicit on every leg (hard rule 1) and RLS FORCE is the
    second guarantee rather than the first — which matters here more than
    usual, because a correlated subquery that lost its tenant filter would be
    caught by the policy and by nothing in this file.

    Money stays `NUMERIC` from the column to the `Decimal`. Nothing below is a
    float and nothing is cents (hard rule 2).
    """
    from django.db.models import (
        Case,
        Count,
        DecimalField,
        F,
        IntegerField,
        Q,
        Sum,
        Value,
        When,
    )
    from django.db.models.functions import Coalesce

    from apps.payments.exceptions import PaymentRuleError

    money = DecimalField(max_digits=18, decimal_places=6)
    built = _debtor_positions(account_ids)
    if built is None:  # pragma: no cover - billing publishes it
        return OutstandingsPage(
            positions=(),
            ageing={},
            total_accounts=0,
            total_owed=ZERO,
            problems=(
                {
                    "code": "billing_publishes_no_invoice_read",
                    "br_ref": "BR-PAY-029",
                    "detail": f"apps.{BILLING_MODULE}.selectors.{OPEN_AMOUNTS_QUERYSET_READ} "
                    "is not published, so the bills behind an outstanding balance cannot be "
                    "read. The outstandings list reports that it cannot answer rather than "
                    "showing an empty one, which would read as 'nobody owes anything'.",
                },
            ),
        )
    positions, credit_by_account = built
    negative_credit_ids = [
        account_id for account_id, amount in credit_by_account.items() if amount < ZERO
    ]

    # ── the ageing band, as a date comparison rather than day arithmetic ──
    # `(as_of - oldest_due_on).days <= 30` is `oldest_due_on >= as_of - 30`, and
    # the second form needs no interval type, no cast and no backend-specific
    # day extraction. `oldest_due_on IS NULL` is CURRENT, never 90+, which is
    # `bucket_for`'s first line.
    from datetime import timedelta

    whens = []
    for name, upper in bands.thresholds:
        whens.append(
            When(oldest_due_on__gte=as_of - timedelta(days=upper), then=Value(name))
        )
    band = Case(
        When(oldest_due_on__isnull=True, then=Value(bands.current)),
        When(oldest_due_on__gte=as_of, then=Value(bands.current)),
        *whens,
        default=Value(bands.overflow),
    )
    positions = positions.annotate(band=band)

    if bucket is not None:
        positions = positions.filter(band=bucket)
    # ⚠ **`accounts.bad_address`, NOT this module's return events (`DEF-PAY-6342`,
    # 2026-09-23).** This filter used to derive the flag from unresolved
    # `delivery_return_events` while the account page read the stored column,
    # so the Debtors list and the account could disagree about the same
    # customer. It now asks customers for the column as a LAZY id queryset and
    # composes it into this statement — one `IN (SELECT …)`, no id list in
    # Python, no parameter ceiling at 40,000 accounts (`NFR-3`/`NFR-5`). The
    # per-row cell is read for the page by `outstandings.py`, from the same
    # column.
    if bad_address_only:
        flagged_ids = _resolve(CUSTOMERS_MODULE, BAD_ADDRESS_IDS_READ, "bad_address")
        if flagged_ids is None:  # pragma: no cover - customers publishes it
            raise PaymentRuleError(
                "apps.customers.bad_address.flagged_account_ids is not published, so "
                "the list cannot be narrowed to accounts whose post comes back.",
                br_ref="BR-PAY-018",
            )
        positions = positions.filter(account_id__in=flagged_ids())

    # ── the tiles: ONE statement over the WHOLE filtered set ─────────────
    # Django wraps a grouped queryset as a subquery for `aggregate()`, so these
    # are outer aggregates over the per-account rows — the same fold the old
    # code did in Python, moved to where the rows already are.
    tile_aggregates: dict[str, Any] = {
        "total_accounts": Count("account_id"),
        "total_owed": Coalesce(Sum("net"), Value(ZERO, output_field=money), output_field=money),
        "undated_total": Coalesce(
            Sum("undated"), Value(0), output_field=IntegerField()
        ),
    }
    for name in bands.names():
        tile_aggregates[f"amt__{name}"] = Coalesce(
            Sum("net", filter=Q(band=name)), Value(ZERO, output_field=money), output_field=money
        )
        tile_aggregates[f"cnt__{name}"] = Count("account_id", filter=Q(band=name))
    tiles = positions.aggregate(**tile_aggregates)

    # ── how many DEBTORS hold a negative credit ──────────────────────────
    # BR-PAY-041's sentence needs a count, and the count is over accounts that
    # are in this list at all. It is a separate, chunked statement rather than
    # a fourth correlated subquery, for the reason above — and it is CHUNKED
    # rather than one `IN` list because that list is as long as the tenant's
    # negative positions and an unbounded parameter array is how a read that
    # works at 2,000 fails at 40,000 with a protocol error. `NFR-5`: chunking
    # bounds one STATEMENT, never the answer.
    negative_credits = 0
    if negative_credit_ids:
        for start in range(0, len(negative_credit_ids), _IN_CHUNK):
            chunk = negative_credit_ids[start : start + _IN_CHUNK]
            negative_credits += (
                positions.filter(account_id__in=chunk).values("account_id").count()
            )

    # ── the page ─────────────────────────────────────────────────────────
    # ⚠ `days_late` DESC is `oldest_due_on` ASC — the oldest unpaid bill is the
    # one that has been late longest — and an account with no due date has no
    # days late at all, so it sorts LAST in both directions rather than being
    # given a rank by a NULL's default position.
    descending = str(direction).lower() != "asc"
    if sort == "days_late":
        term = F("oldest_due_on").asc(nulls_last=True) if descending else F(
            "oldest_due_on"
        ).desc(nulls_last=True)
    elif sort == "open_bills":
        term = F("invoice_count").desc() if descending else F("invoice_count").asc()
    else:
        term = F("net").desc() if descending else F("net").asc()
    # A second, total term so a page boundary is STABLE: two debtors owing the
    # same amount must not swap between page 1 and page 2, which is a row a
    # clerk sees twice and a row they never see.
    positions = positions.order_by(term, F("account_id").asc())

    # ⚠ **`per=None` MEANS THE WHOLE FILTERED LIST, AND IT IS NOT A CAP BEING
    # LIFTED — IT IS A CALLER THAT HAS NOT ASKED FOR A PAGE.** Three of this
    # read's consumers are batch jobs with no page to cut to, and screen 7·1
    # cannot ask for one yet: `P4.7` landed a toolbar declaring ten sortable
    # columns, a search over account number and customer name, and four
    # filters, and this query can honour three sorts and two filters. Cutting
    # a page underneath those controls would give a clerk a search box that
    # searches fifty rows — a live screen behind a broken control, which is
    # the shape this repository files most. `DEF-PAY-4221` stays OPEN and
    # `DEF-PAY-6271` names the join that closes it.
    #
    # **Everything that makes the page cheap is already done when `per` is
    # None:** the filter, the band, the tiles and the count are all SQL, and
    # nothing is materialised that is not on the answer. `NFR-5`: there is no
    # ceiling on this branch and there must never be one.
    if per is None:
        page, rows = 1, list(positions)
    else:
        # BR-SHL-011 — clamp, never error, and never silently answer nothing.
        # `StandardPagination.get_page_number` does exactly this for
        # DRF-paginated lists; this read builds its own window, so it does it
        # here rather than leaving the one list in the product where an
        # out-of-range page is an empty screen with no explanation.
        per = max(1, int(per))
        last_page = max(1, -(-(tiles["total_accounts"] or 0) // per))
        page = min(max(1, int(page)), last_page)
        offset = (page - 1) * per
        rows = list(positions[offset : offset + per])

    out: list[OutstandingPosition] = []
    for row in rows:
        out.append(
            OutstandingPosition(
                account_id=row["account_id"],
                balance=row["net"],
                oldest_due_on=row["oldest_due_on"],
                invoice_count=row["invoice_count"],
                undated=row["undated"],
                gross_balance=row["gross"],
                credit_applied=row["credit_applied"],
            )
        )

    problems: tuple[dict[str, Any], ...] = ()
    if negative_credits:
        problems += (
            {
                "code": "negative_credit_not_added_to_chase",
                "br_ref": "BR-PAY-041",
                "detail": f"{negative_credits} account(s) here hold a NEGATIVE credit "
                "— a real debt (PO 2026-08-11, 'Yes, it's a real debt'). It is not floored "
                "anywhere and it renders signed wherever it is shown; it is simply not ADDED "
                "to this bill-based balance, because there is no bill behind it and a "
                "disconnect notice would state that bills are unpaid which are not. Chasing "
                "it is a separate act and this list does not pretend to be it.",
            },
        )
    if tiles.get("undated_total"):
        problems = (
            {
                "code": "unpaid_bill_without_due_date",
                "br_ref": "BR-PAY-032",
                "detail": f"{tiles['undated_total']} unpaid bill(s) carry no due date, so "
                'BR-PAY-032\'s "today − the oldest unpaid invoice\'s due date" cannot place '
                "them. Their BALANCE is counted — the customer owes it — and they are "
                "excluded from the days-late anchor and from every ageing bucket rather than "
                "dated by a convention no rule states.",
            },
        ) + problems
    return OutstandingsPage(
        positions=tuple(out),
        ageing={
            name: (tiles[f"amt__{name}"], tiles[f"cnt__{name}"]) for name in bands.names()
        },
        total_accounts=tiles["total_accounts"] or 0,
        total_owed=tiles["total_owed"] or ZERO,
        problems=problems,
        page=page,
    )


# ════════════════════════════════════════════════════════════════════════════
# `P2.21` (Finance blueprint p035) — THE AR AGEING, CUT IN SQL
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **WHY THIS IS NOT `outstanding_positions_page` WITH MORE COLUMNS.** That
# read answers *"which band is this DEBTOR in?"* — one account, one band, chosen
# by its oldest unpaid due date (`BR-PAY-032`), which is right for a collections
# worklist. A14's ageing asks a different question: **each open BILL is aged on
# ITS OWN due date** and lands in its own column, so a customer with a fresh
# $200 bill and a four-month-old $50 one reads **200 current and 50 in 90+** and
# not 250 in 90+. Both readings are correct, they are deliberately not merged,
# and `apps/payments/reporting.py` has said so since the report was written.
#
# ⚠ **WHAT WAS HERE BEFORE, AND WHY `DEF-REP-6607` REFUSED TO HALF-BUILD IT.**
# `reporting.ar_aging` pulled **every open bill of the tenant** into Python with
# a `list()` and folded them into a dict — so there was no queryset, and none of
# p035's five criteria (`as_of`, band, service, property, search) nor a page
# could be expressed at all. `NFR-3` and `NFR-5` are the deliverable here and
# not the background: the ICP's ceiling is **40,000 accounts** and a web worker
# is given **60 seconds** (`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`).
#
# ⚠⚠ **THE TRAP, WHICH IS THE WHOLE REASON THE TASK WAS HANDED BACK: A FILTER
# MUST NOT BE ABLE TO MAKE THE REPORT ACCUSE THE BOOKS OF NOT FOOTING.** The
# report states whether Σ of its bands equals the ledger's AR control. Narrow
# the rows and fold the totals over them and the two disagree **on every
# filtered page**, so a clerk searching for one customer is told the general
# ledger is broken. Two separate figures answer two separate questions and this
# read returns both:
#
#   * `band_totals` / `total_owed` / `total_accounts` — a SQL aggregate over the
#     **whole FILTERED set**, never a fold over the page. That is what the KPI
#     tiles show, and it is CLAUDE.md's own resolution of the same shape for
#     `/outstandings`: *"the tiles are a SQL aggregate over the whole filtered
#     set whether a page is cut or not"*.
#   * `population_total` / `population_accounts` — the same aggregate with
#     **every filter removed**, which is the only figure the AR control can
#     lawfully be compared against. It does not move when a chip is added, so
#     the tie-out states a fact about the BOOKS and never about the filter.


@dataclass(frozen=True)
class AgingPosition:
    """One account's receivable, split across the bands BY BILL."""

    account_id: Any
    #: band name -> amount. Exactly `bands.names()`, always all of them.
    bands: dict[str, Decimal]
    #: Open balance on bills carrying NO due date — in the TOTAL and in no band
    #: (`BR-PAY-032`). Never folded into `current`: a debt of unknown age shown
    #: as fresh is the one reading a collections officer must not be given.
    undated: Decimal
    total: Decimal
    #: The oldest PAST-DUE due date, or None when nothing is past due.
    oldest_due_on: Any
    invoice_count: int


@dataclass(frozen=True)
class AgingPage:
    """One page of the ageing, its tiles, and the population behind the tie-out."""

    positions: tuple[AgingPosition, ...]
    #: band -> amount over the whole FILTERED set (never the page).
    band_totals: dict[str, Decimal]
    undated_total: Decimal
    total_owed: Decimal
    total_accounts: int
    #: The UNFILTERED receivable — what BR-REP-008's tie-out is struck against.
    population_total: Decimal
    population_accounts: int
    #: Distinct currencies among the filtered open bills, capped at two reads
    #: because "more than one" is all the footer needs to know.
    currencies: tuple[str, ...]
    undated_bills: int
    problems: tuple[dict[str, Any], ...]
    page: int = 1
    filtered: bool = False


#: What the ageing may be ordered by. ⚠ **SHORT, AND THE ABSENCES ARE NAMED.**
#: p035's drawing puts a sort caret on ACCOUNT as well; `account_no` and the
#: customer's name live on CUSTOMERS' table, which this statement does not join
#: (B1 / `BR-TEN-013`), so ordering by them would either reach into another
#: module's ORM or sort a page that was already cut — which is the defect this
#: read exists to fix. `DEF-REP-6660` carries it; the screen does not offer the
#: control (hard-won law 2's mirror: a live screen behind a dead control).
AGING_SORTS: tuple[str, ...] = ("total", "days_late")


def aging_positions_page(
    *,
    as_of: date,
    bands: AgeingBands,
    band: str | None = None,
    service_code: str | None = None,
    premises_id: Any = None,
    search: str | None = None,
    account_ids: Any = None,
    page: int = 1,
    per: int | None = 50,
    sort: str = "total",
    direction: str = "desc",
) -> AgingPage:
    """A14's ageing — **filtered, sorted, paged and totalled in SQL**.

    `as_of` is an ARGUMENT and never a clock (`BR-TEN-043`): an ageing a clerk
    reads at 23:58 and one a job takes at 00:02 must be explainable against the
    same day, and a function reading the system date could not be asked for last
    month-end.

    ════════════════════════════════════════════════════════════════════════
    `as_of` SELECTS THE POPULATION AS WELL AS THE BANDS — `DEF-PAY-6940`
    ════════════════════════════════════════════════════════════════════════
    ⚠ **IT BANDED BY `as_of` AND AGED WHATEVER WAS OUTSTANDING *NOW* UNTIL
    THIS FIX**, so *"the receivable as at last September"* silently meant
    *"what is outstanding today, banded as if it were last September"* — and
    the TOTAL and the debtor count came back byte-identical for every date
    ever asked for. Measured on real PostgreSQL 16 over the sample tenant
    before the fix, at seven dates from `2024-01-31` to `2026-09-30`:
    **`total = 9581.530000` over 30 accounts, ALL SEVEN**, and hand-written
    SQL agreed with it at exactly ONE of them — `2026-09-30`, today. Every
    other date was today's answer wearing another date's label. On
    `2024-01-31` the whole 9,581.53 sat in `current`: the report saying thirty
    customers owed money freshly, eighteen months before the first of those
    bills was issued. An ageing that cannot look back is not an ageing report:
    a finance officer reads it to reconcile a past month-end and to answer an
    auditor. `10-scripts/def_pay_6940_as_at_ageing.py` prints both ladders.

    **The position at `as_of` is now built from two clocks, and both are
    columns this schema already had:**

      * **`invoices.issued_at` ≤ `as_of`** — a bill that had not been issued
        by that day was not receivable on it. `issued_at` is a sound clock
        because it is FROZEN: `billing/migrations/0002`'s immutability trigger
        refuses any UPDATE that moves it once it is set, and treats NULL as
        *not yet issued*.
      * **`payments.posted_at` ≤ `as_of`** on the payment behind each
        allocation — `BR-PAY-021`, *"posting date ≠ clearing date, always
        both"*, and `BR-REP-001` puts this report on the POSTING basis. Money
        that had not been posted by that day had not reduced the bill on it.
        The CLEARING date still drives nothing here.

    ⚠ **TODAY'S FIGURES DO NOT MOVE, AND THAT IS A FINANCE MATTER RATHER THAN
    A HOPE.** Every bill issued and every payment posted before `as_of` means
    the as-at set IS the open set, which is exactly what this read always
    returned; the sample tenant's `2026-09-30` row is byte-identical either
    side of the change, bands included.

    ⚠ **WHAT THIS STILL CANNOT DO, WITH ITS NUMBER BESIDE IT.** A bill that is
    `void` or `corrected` TODAY but was live at `as_of` is missing from a
    past-date read, because `invoices` records `issued_at` and **no
    `voided_at` and no `corrected_at`** — nothing says the day a live bill
    stopped being live. The read counts the bills issued by `as_of` that are
    retired today and publishes that count as the problem
    `retired_bills_cannot_be_restored_to_a_past_date`, so the gap is a number
    on the report rather than a silent understatement. `DEF-PAY-7020`.

    POSTING basis (`BR-REP-001`) — this is receivable, which is billing-side
    money. A payment POSTED by the due date has written its allocation rows, so
    the bill is settled and simply is not here; the CLEARING date never drives
    ageing. That falls out of reading allocations and is a special case nowhere.

    **What a bill asks for is `amount_due_expression()` and never `total`** —
    `BR-BIL-072`, ❄️ *"Level is due"* (PO 2026-08-11). The report this replaces
    read `total`, which over-aged every budget-billing customer by the
    difference between their bill and their level; `DEF-REP-6658` records it.

    ⚠ **`NFR-5` — PAGED, NEVER CAPPED.** No maximum row count, no per-tenant
    ceiling, no `[:N]` anywhere below. `per=None` asks for no page at all and
    is answered; the last page of a 40,000-row list is served like the first.

    Tenant scoping is explicit on every leg (hard rule 1); RLS FORCE is the
    second guarantee and not the first. Money stays `NUMERIC` from the column
    to the `Decimal` (hard rule 2).
    """
    from datetime import timedelta

    from django.db.models import (
        Case,
        Count,
        DecimalField,
        F,
        IntegerField,
        Min,
        OuterRef,
        Q,
        Subquery,
        Sum,
        Value,
        When,
    )
    from django.db.models.functions import Coalesce

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    money = DecimalField(max_digits=18, decimal_places=6)
    published = _resolve(BILLING_MODULE, AGING_QUERYSET_READ)
    if published is None:  # pragma: no cover - billing publishes it
        return AgingPage(
            positions=(),
            band_totals={name: ZERO for name in bands.names()},
            undated_total=ZERO,
            total_owed=ZERO,
            total_accounts=0,
            population_total=ZERO,
            population_accounts=0,
            currencies=(),
            undated_bills=0,
            problems=(
                {
                    "code": "billing_publishes_no_invoice_read",
                    "br_ref": "BR-PAY-029",
                    "detail": f"apps.{BILLING_MODULE}.selectors.{AGING_QUERYSET_READ} is not "
                    "published, so the bills behind a receivable cannot be read. The ageing "
                    "reports that it cannot answer rather than rendering an empty table, "
                    "which would read as 'nobody owes anything'.",
                },
            ),
        )

    tenant_id = payment_selectors._tenant_id()
    bills = published(OPEN_INVOICE_STATUSES)
    if account_ids is not None:
        # A queryset stays LAZY here — `list()` would materialise every account
        # id of a 40,000-account utility to narrow a page of fifty (`NFR-3`).
        bills = bills.filter(account_id__in=account_ids)

    # ── one bill's OPEN balance ──────────────────────────────────────────
    # ⚠ **`posted_at`, AND THE `__date__lte` IS NOT A ROUNDING PREFERENCE**
    # (`DEF-PAY-6940`). `as_of` is a DATE and `posted_at` is a timestamp, so a
    # payment posted at 16:20 on the closing day must be IN the closing day's
    # position; `posted_at <= as_of` on a naive comparison would put it out.
    # `TIME_ZONE` is UTC and storage is UTC (B2), so the `__date` lookup is the
    # same calendar day the rest of the product prints.
    allocated = Coalesce(
        Subquery(
            payment_models.Allocation.objects.filter(
                tenant_id=tenant_id,
                invoice_id=OuterRef("id"),
                payment__posted_at__date__lte=as_of,
            )
            .values("invoice_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1],
            output_field=money,
        ),
        Value(ZERO, output_field=money),
        output_field=money,
    )
    # ── the SET: bills ISSUED by `as_of`, not bills open today ───────────
    # ⚠ **THIS LINE IS `DEF-PAY-6940`.** Without it every figure below is a
    # statement about TODAY wearing a past date's label. A bill with a NULL
    # `issued_at` is not yet issued — `billing/migrations/0002` says so in as
    # many words — so `__date__lte` excluding it is the right reading and not
    # an accident of SQL's NULL semantics.
    bills = bills.filter(issued_at__date__lte=as_of)
    bills = bills.annotate(open_balance=F("amount_due") - allocated).filter(open_balance__gt=ZERO)

    # ── the band of ONE BILL, from its OWN due date ──────────────────────
    # `(as_of - due_date).days <= 30` is `due_date >= as_of - 30`: no interval
    # type, no cast, no backend-specific day extraction. A bill with no due date
    # takes the sentinel band and is summed into the total and into nothing else.
    whens = [
        When(due_date__gte=as_of - timedelta(days=upper), then=Value(name))
        for name, upper in bands.thresholds
    ]
    bill_band = Case(
        When(due_date__isnull=True, then=Value(_UNDATED_BAND)),
        When(due_date__gte=as_of, then=Value(bands.current)),
        *whens,
        default=Value(bands.overflow),
    )
    bills = bills.annotate(band=bill_band)

    # ── the five criteria of p035, each as a nested subquery ─────────────
    # ⚠ Every one of these is a LAZY queryset from the module that owns the
    # column (B1 / `BR-TEN-013` forbid the join), composed into this statement
    # rather than materialised — so a criterion costs no round trip and no
    # parameter array at 40,000 accounts.
    filtered = False
    if service_code:
        service_ids = _resolve(BILLING_MODULE, AGING_SERVICE_IDS_READ)
        if service_ids is not None:  # pragma: no branch - billing publishes it
            bills = bills.filter(id__in=service_ids(service_code))
            filtered = True
    if premises_id is not None:
        at_premises = _resolve(CUSTOMERS_MODULE, AGING_PREMISES_IDS_READ)
        if at_premises is not None:  # pragma: no branch - customers publishes it
            bills = bills.filter(account_id__in=at_premises(premises_id))
            filtered = True
    if search:
        matching = _resolve(CUSTOMERS_MODULE, AGING_SEARCH_IDS_READ)
        if matching is not None:  # pragma: no branch - customers publishes it
            bills = bills.filter(account_id__in=matching(search))
            filtered = True

    # ── `CR-184-BRC10` R5 · THE SERVICE FILTER COUNTS THE SERVICE'S SHARE ──
    # ⚠ **UNTIL 2026-10-14 A SERVICE CHIP SELECTED WHOLE BILLS**, so a bill of
    # water 80.00 + electric 40.00 sat under *water* at 120.00 — every mixed
    # bill overstated by its other services. The PO ruled the sharing that
    # day (decision log, C1 → a): what is still owed is shared across the
    # bill's services in proportion, inside the tenant's class order. The
    # narrowing above still applies (only bills carrying the service can owe
    # it); what each bill CONTRIBUTES is now its share, computed by
    # `receivables_by_service` — which is Python over keyset chunks, three
    # statements a chunk, because the proportion and the exact-cent rounding
    # are not one SQL expression. Tiles, page and sort are cut over the whole
    # filtered set exactly as the SQL path cuts them; the population is the
    # SQL path's, unfiltered.
    if service_code:
        return _aging_page_by_service_share(
            bills=bills.annotate(allocated_sum=allocated),
            as_of=as_of,
            bands=bands,
            band=band,
            service_code=service_code,
            published=published,
            allocated=allocated,
            account_ids=account_ids,
            money=money,
            page=page,
            per=per,
            sort=sort,
            direction=direction,
        )

    # ── one account's row: the bands SIDE BY SIDE ────────────────────────
    band_sums: dict[str, Any] = {}
    for name in bands.names():
        band_sums[f"amt__{name}"] = Coalesce(
            Sum("open_balance", filter=Q(band=name)),
            Value(ZERO, output_field=money),
            output_field=money,
        )
    positions = bills.values("account_id").annotate(
        **band_sums,
        undated=Coalesce(
            Sum("open_balance", filter=Q(band=_UNDATED_BAND)),
            Value(ZERO, output_field=money),
            output_field=money,
        ),
        undated_count=Count("id", filter=Q(band=_UNDATED_BAND)),
        # ⚠ **`owed` AND NOT `total`, AND THAT IS NOT A NAMING PREFERENCE.**
        # `invoices.total` is a real column on the queryset this is grouped
        # from, so an annotation called `total` is a name with two meanings —
        # and the `ORDER BY` picked the COLUMN, which put a 90.00 debtor below
        # a 10.00 one with every figure on the row still correct. Found by
        # `test_the_order_is_the_servers…`, which is the only thing that could
        # have seen it: the totals, the bands and the tie-out are all right.
        owed=Coalesce(Sum("open_balance"), Value(ZERO, output_field=money), output_field=money),
        # `Min` with a filter ignores everything else, which IS `BR-PAY-032`'s
        # rule rather than a coincidence: the anchor is the oldest PAST-DUE
        # bill, and a bill with no due date never becomes one.
        oldest_due_on=Min("due_date", filter=Q(due_date__lt=as_of)),
        invoice_count=Count("id"),
    )

    # ── the BAND filter narrows ACCOUNTS, never their columns ────────────
    # ⚠ A judgment, and it is recorded in the decision log with its figure.
    # Filtering the BILLS to one band would empty the other four columns and
    # the row's Total would stop being what that customer owes — a table whose
    # rows do not add up across. p035's chip reads `90+ ×` on a screen whose
    # job is *"deciding who to chase, and in what order"*, so it selects the
    # DEBTORS who have money in that band and still shows each of them whole.
    if band:
        positions = positions.filter(**{f"amt__{band}__gt": ZERO})
        filtered = True

    # ── the tiles: ONE statement over the WHOLE FILTERED set ─────────────
    tile_aggregates: dict[str, Any] = {
        "total_accounts": Count("account_id"),
        "total_owed": Coalesce(Sum("owed"), Value(ZERO, output_field=money), output_field=money),
        "undated_total": Coalesce(
            Sum("undated"), Value(ZERO, output_field=money), output_field=money
        ),
        "undated_bills": Coalesce(Sum("undated_count"), Value(0), output_field=IntegerField()),
    }
    for name in bands.names():
        tile_aggregates[f"t__{name}"] = Coalesce(
            Sum(f"amt__{name}"), Value(ZERO, output_field=money), output_field=money
        )
    tiles = positions.aggregate(**tile_aggregates)

    # ── the POPULATION behind the tie-out ────────────────────────────────
    # Unfiltered by construction: it is re-derived from `bills` before any
    # criterion touched it, so no chip and no page can move it. When nothing is
    # filtered the two are the same figure and the second statement is skipped.
    if filtered:
        population = _aging_population(
            published=published,
            allocated=allocated,
            account_ids=account_ids,
            money=money,
            as_of=as_of,
        )
    else:
        population = (tiles["total_owed"] or ZERO, tiles["total_accounts"] or 0)

    # ── the currencies present, bounded at two ───────────────────────────
    currencies = tuple(
        sorted(set(bills.order_by().values_list("currency", flat=True).distinct()[:2]))
    )

    # ── the page ─────────────────────────────────────────────────────────
    # ⚠ `days_late` DESC is `oldest_due_on` ASC — the oldest unpaid bill has
    # been late longest — and an account with nothing past due sorts LAST in
    # both directions rather than taking a NULL's default position.
    descending = str(direction).lower() != "asc"
    if sort == "days_late":
        term = (
            F("oldest_due_on").asc(nulls_last=True)
            if descending
            else F("oldest_due_on").desc(nulls_last=True)
        )
    else:
        term = F("owed").desc() if descending else F("owed").asc()
    # A total second term, so a page boundary is STABLE: two debtors owing the
    # same amount must not swap between page 1 and page 2 — a row a clerk sees
    # twice is a row they never see.
    positions = positions.order_by(term, F("account_id").asc())

    if per is None:
        page, rows = 1, list(positions)
    else:
        # `BR-SHL-011` — clamp, never error. A caller asking for page 9,999 of
        # a 41-page list is told which page it got.
        per = max(1, int(per))
        last_page = max(1, -(-(tiles["total_accounts"] or 0) // per))
        page = min(max(1, int(page)), last_page)
        offset = (page - 1) * per
        rows = list(positions[offset : offset + per])

    out = tuple(
        AgingPosition(
            account_id=row["account_id"],
            bands={name: row[f"amt__{name}"] for name in bands.names()},
            undated=row["undated"],
            total=row["owed"],
            oldest_due_on=row["oldest_due_on"],
            invoice_count=row["invoice_count"],
        )
        for row in rows
    )

    problems = _aging_problems(
        published=published,
        as_of=as_of,
        account_ids=account_ids,
        undated_bills=tiles.get("undated_bills") or 0,
    )
    return AgingPage(
        positions=out,
        band_totals={name: tiles[f"t__{name}"] for name in bands.names()},
        undated_total=tiles["undated_total"] or ZERO,
        total_owed=tiles["total_owed"] or ZERO,
        total_accounts=tiles["total_accounts"] or 0,
        population_total=population[0],
        population_accounts=population[1],
        currencies=currencies,
        undated_bills=tiles.get("undated_bills") or 0,
        problems=problems,
        page=page,
        filtered=filtered,
    )


def _aging_page_by_service_share(
    *,
    bills: Any,
    as_of: date,
    bands: AgeingBands,
    band: str | None,
    service_code: str,
    published: Any,
    allocated: Any,
    account_ids: Any,
    money: Any,
    page: int,
    per: int | None,
    sort: str,
    direction: str,
) -> AgingPage:
    """The ageing when a SERVICE is chosen — each bill contributes its share.

    `CR-184-BRC10` R5. Same contract as the SQL path: rows per account, the
    band filter narrows ACCOUNTS and never their columns, tiles over the whole
    filtered set, a stable order (`owed`/`oldest_due_on`, then account id),
    `BR-SHL-011` clamping, `NFR-5` no cap. The population is the SQL path's
    own unfiltered figure, because the tie-out is a statement about the books.
    """
    from core.pagination import filter_values

    from apps.payments import receivables_by_service as shares

    by_account = shares.aging_by_service_share(
        bills, as_of=as_of, bands=bands, service_codes=filter_values(service_code)
    )
    items = list(by_account.items())
    if band:
        items = [(account, pos) for account, pos in items if pos.bands.get(band, ZERO) > ZERO]

    descending = str(direction).lower() != "asc"
    if sort == "days_late":
        dated = [item for item in items if item[1].oldest_due_on is not None]
        undated_rows = [item for item in items if item[1].oldest_due_on is None]
        dated.sort(key=lambda item: str(item[0]))
        dated.sort(key=lambda item: item[1].oldest_due_on, reverse=not descending)
        undated_rows.sort(key=lambda item: str(item[0]))
        items = dated + undated_rows
    else:
        items.sort(key=lambda item: str(item[0]))
        items.sort(key=lambda item: item[1].total, reverse=descending)

    band_totals = {name: sum((pos.bands[name] for _, pos in items), ZERO) for name in bands.names()}
    undated_total = sum((pos.undated for _, pos in items), ZERO)
    total_owed = sum((pos.total for _, pos in items), ZERO)
    undated_bills = 0
    total_accounts = len(items)

    if per is None:
        page, cut = 1, items
    else:
        per = max(1, int(per))
        last_page = max(1, -(-total_accounts // per))
        page = min(max(1, int(page)), last_page)
        cut = items[(page - 1) * per : (page - 1) * per + per]

    out = tuple(
        AgingPosition(
            account_id=account,
            bands=dict(pos.bands),
            undated=pos.undated,
            total=pos.total,
            oldest_due_on=pos.oldest_due_on,
            invoice_count=pos.bills,
        )
        for account, pos in cut
    )
    population = _aging_population(
        published=published, allocated=allocated, account_ids=account_ids, money=money, as_of=as_of
    )
    currencies = tuple(
        sorted(set(bills.order_by().values_list("currency", flat=True).distinct()[:2]))
    )
    undated_bills = sum(pos.undated_bills for _, pos in items)
    return AgingPage(
        positions=out,
        band_totals=band_totals,
        undated_total=undated_total,
        total_owed=total_owed,
        total_accounts=total_accounts,
        population_total=population[0],
        population_accounts=population[1],
        currencies=currencies,
        undated_bills=undated_bills,
        problems=_aging_problems(
            published=published,
            as_of=as_of,
            account_ids=account_ids,
            undated_bills=undated_bills,
        ),
        page=page,
        filtered=True,
    )


def _aging_problems(
    *, published: Any, as_of: date, account_ids: Any, undated_bills: int
) -> tuple[dict[str, Any], ...]:
    """The two scope statements every ageing answer carries — retired bills a
    past date cannot restore (`DEF-PAY-7020`) and undated bills (`BR-PAY-032`).
    One helper so the SQL path and the service-share path (`CR-184-BRC10`)
    cannot state them differently."""
    problems: tuple[dict[str, Any], ...] = ()
    # ── the blind spot, WITH ITS NUMBER (`DEF-PAY-7020`, hard-won law 7) ──
    # Bills that had been ISSUED by `as_of` and are `void` or `corrected`
    # TODAY. Some of them were live on that day and belong in this position;
    # nothing in `invoices` records which, because there is no `voided_at` and
    # no `corrected_at` — only `issued_at`, which says when a bill STARTED.
    # ⚠ It is counted from the same published read with a different status
    # set, so it needs no new billing publication and no cross-module join.
    retired = published(RETIRED_INVOICE_STATUSES).filter(issued_at__date__lte=as_of)
    if account_ids is not None:
        retired = retired.filter(account_id__in=account_ids)
    retired_count = retired.order_by().values("id").count()
    if retired_count:
        problems += (
            {
                "code": "retired_bills_cannot_be_restored_to_a_past_date",
                "br_ref": "DEF-PAY-7020",
                "detail": f"{retired_count} bill(s) issued on or before {as_of.isoformat()} are "
                "void or corrected today. A bill that was still live on that date belongs in "
                "this position, and `invoices` records no date on which a bill was voided or "
                "superseded — only when it was issued. The figures below therefore EXCLUDE all "
                f"{retired_count}, which understates a past-date position by whatever part of "
                "them was still open. At today's date the exclusion is correct and this is a "
                "statement of scope rather than of error.",
            },
        )
    if undated_bills:
        problems += (
            {
                "code": "open_bill_without_a_due_date",
                "br_ref": "BR-PAY-032",
                "detail": f"{undated_bills} open bill(s) carry no due date, so "
                "BR-PAY-032 cannot age them. Their balance IS in each account's Total and in "
                "NO band — a debt of unknown age placed in 'Current' would read as fresh, "
                "which is the one reading a collections officer must never be given.",
            },
        )
    return problems


def _aging_population(
    *, published: Any, allocated: Any, account_ids: Any, money: Any, as_of: date
) -> tuple:
    """The UNFILTERED receivable and debtor count — the tie-out's other side.

    One statement, and it is the same arithmetic as the tiles with every p035
    criterion removed. It exists so that `BR-REP-008`'s comparison against the
    ledger's AR control is a statement about the BOOKS: a clerk who types a
    customer's name into the search box must not be told the general ledger
    does not foot.

    `account_ids` is NOT a p035 criterion and is deliberately still applied —
    it is the caller declaring which accounts the report is ABOUT (the cutover
    comparison passes one), not a control on a screen.
    """
    from django.db.models import Count, F, Sum, Value
    from django.db.models.functions import Coalesce

    bills = published(OPEN_INVOICE_STATUSES)
    if account_ids is not None:
        bills = bills.filter(account_id__in=account_ids)
    # ⚠ **THE SAME AS-AT CUT AS THE TILES** (`DEF-PAY-6940`). The tie-out's two
    # sides have to be struck at ONE date: a population read at today's set and
    # a filtered total read at a past one would accuse the books of not footing
    # for exactly the reason this function exists to prevent.
    bills = bills.filter(issued_at__date__lte=as_of)
    bills = bills.annotate(open_balance=F("amount_due") - allocated).filter(open_balance__gt=ZERO)
    rows = bills.values("account_id").annotate(
        owed=Coalesce(Sum("open_balance"), Value(ZERO, output_field=money), output_field=money)
    )
    whole = rows.aggregate(
        # The alias differs from the annotation's on purpose: an outer
        # aggregate that reuses the inner name is a second meaning for one
        # word, which is exactly what `owed` above exists to avoid.
        population_owed=Coalesce(
            Sum("owed"), Value(ZERO, output_field=money), output_field=money
        ),
        population_debtors=Count("account_id"),
    )
    return (whole["population_owed"] or ZERO, whole["population_debtors"] or 0)



# ══════════════════════════════════════════════════════════════════════════
# 🔒 PO RULINGS 2026-10-01 — WHAT A BILL'S BALANCE FORWARD READS FROM PAYMENTS
# ══════════════════════════════════════════════════════════════════════════
# HUMAN-OWNED · HUMAN-REVIEW-PENDING (money: the figures a bill prints and asks
# for). Two reads billing asks for BY NAME (`billing/payments_seam`), each over
# this module's own rows; billing computes neither.


def payments_received_for_account(
    account_id: Any, *, after: Any = None, through_date: date | None = None
) -> Decimal:
    """`OQ-217` CLOSED (PO 2026-10-01, option A): the money RECEIVED on the
    account in a window — *"last bill $34.00 − paid $120.00 + new charges
    $37.25 = $48.75 credit, nothing to pay"*.

    Every receipt `selectors.account_credit_position` counts (a payment in
    `balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES` — posted or cleared — that
    is not a deposit; the negative reversing row of a bounce included, so a
    bounce nets itself out; never cancelled, failed or processing, CR-186-BRC10)
    POSTED after `after` (a
    datetime; None = from the beginning) and on or before `through_date`
    (None = no end), LESS every refund issued or cleared in the same window.
    Whether it met a bill or sits as credit does not matter: the bill reads the
    whole account (BR-BIL-1065). Same terms as the credit position, so the
    balance forward foots against it by construction.
    """
    from django.db.models import Sum

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    tenant_id = payment_selectors._tenant_id()
    received = (
        payment_models.Payment.objects.filter(tenant_id=tenant_id, account_id=account_id)
        # CR-186-BRC10 (`DEF-PAY-10340`) — `balance_rule`'s counted set.
        .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)
        .exclude(purpose=payment_models.PURPOSE_DEPOSIT)
    )
    refunded = payment_models.Refund.objects.filter(
        tenant_id=tenant_id,
        account_id=account_id,
        status__in=(payment_models.REFUND_ISSUED, payment_models.REFUND_CLEARED),
    )
    if after is not None:
        received = received.filter(posted_at__gt=after)
        refunded = refunded.filter(issued_at__gt=after)
    if through_date is not None:
        received = received.filter(posted_at__date__lte=through_date)
        refunded = refunded.filter(issued_at__date__lte=through_date)
    total_in = received.aggregate(total=Sum("amount"))["total"] or ZERO
    total_out = refunded.aggregate(total=Sum("amount"))["total"] or ZERO
    return total_in - total_out


def credit_positions_for_accounts(account_ids: Any) -> dict[str, Decimal]:
    """`account_credit_position` for MANY accounts — `_credit_positions` above,
    keyed by the account id as text, every account asked about present (0.00
    where it has no row). `DEF-BIL-8682`: the bulk run's Sign off reads the
    whole-account window for every bill of a run, and one statement per
    account is NFR-3's breach at 40,000. `account_ids` may be a queryset of
    account ids, read as a subquery (`DEF-BIL-8696`, `_account_batches`)."""
    keys, filters = _account_batches(account_ids)
    out = {key: ZERO for key in keys}
    for scope in filters:
        for account_id, total in _credit_positions(scope).items():
            if str(account_id) in out:
                out[str(account_id)] = total
    return out


#: Ids per `IN (…)` in the batched reads below.
_BATCH_IDS = 900


def payments_received_by_type_for_accounts(
    windows: dict[str, tuple[Any, date | None]],
    *,
    scope: Any = None,
) -> dict[str, dict[str, Any]]:
    """`payments_received_for_account`, for MANY accounts, PARTED BY TYPE.

    `windows` is `{account_id: (after, through_date)}`, each pair meaning
    exactly what it means to `payments_received_for_account`. Every account
    asked about is answered:

      * `payments` / `payment_count` — `type='payment'` rows received in the
        window, LESS the refunds issued in it (a refund returns cash);
        the count is the receipts, a bounce's negative reversing row not
        counted as a payment of its own;
      * `credits` / `credit_count` — `type` `credit` or `adjustment` (a
        goodwill concession, CR-059 CS-38, or a correction) received in the
        window;
      * `received` = `payments + credits` — **the same figure
        `payments_received_for_account` returns, by construction**, same
        exclusions (a deposit never counts, and only `balance_rule`'s
        posted / cleared / reversed statuses do, CR-186-BRC10);
      * `beyond` — what was received (less refunded) AFTER `through_date`,
        0.00 without one: the *Apply next bill* add-back (`DEF-BIL-8412`).

    `DEF-BIL-8682`: Sign off draws payments apart from credits (D1 25, 28).
    The split is payments' own `type` column — billing reads no payment row.
    ONE query for payments and one for refunds per 900 accounts (NFR-3) — or,
    when `scope` is a queryset of the same accounts' ids, one of each for the
    whole run, the ids read as a subquery (`DEF-BIL-8696`).
    """
    from django.utils import timezone as dj_timezone

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    tenant_id = payment_selectors._tenant_id()
    keys = [str(key) for key in windows]
    out: dict[str, dict[str, Any]] = {
        key: {
            "payments": ZERO,
            "payment_count": 0,
            "credits": ZERO,
            "credit_count": 0,
            "received": ZERO,
            "beyond": ZERO,
        }
        for key in keys
    }

    def place(key: str, moment: Any) -> str | None:
        after, through = windows.get(key, (None, None))
        if after is not None and not moment > after:
            return None
        if through is not None and dj_timezone.localtime(moment).date() > through:
            return "beyond"
        return "window"

    chunks = (
        [scope]
        if scope is not None
        else [keys[start : start + _BATCH_IDS] for start in range(0, len(keys), _BATCH_IDS)]
    )
    for chunk in chunks:
        for account_id, kind, amount, posted_at in (
            payment_models.Payment.objects.filter(tenant_id=tenant_id, account_id__in=chunk)
            # CR-186-BRC10 (`DEF-PAY-10340`) — `balance_rule`'s counted set.
            .filter(status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES)
            .exclude(purpose=payment_models.PURPOSE_DEPOSIT)
            .values_list("account_id", "type", "amount", "posted_at")
        ):
            key = str(account_id)
            where = place(key, posted_at) if key in out else None
            if where is None:
                continue
            row = out[key]
            amount = amount or ZERO
            if where == "beyond":
                row["beyond"] += amount
            elif kind == payment_models.PAYMENT_TYPE_PAYMENT:
                row["payments"] += amount
                row["payment_count"] += 1 if amount > ZERO else 0
            else:
                row["credits"] += amount
                row["credit_count"] += 1 if amount > ZERO else 0
        for account_id, amount, issued_at in (
            payment_models.Refund.objects.filter(
                tenant_id=tenant_id,
                account_id__in=chunk,
                status__in=(payment_models.REFUND_ISSUED, payment_models.REFUND_CLEARED),
            ).values_list("account_id", "amount", "issued_at")
        ):
            key = str(account_id)
            where = place(key, issued_at) if key in out else None
            if where is None:
                continue
            if where == "beyond":
                out[key]["beyond"] -= amount or ZERO
            else:
                out[key]["payments"] -= amount or ZERO
    for row in out.values():
        row["received"] = row["payments"] + row["credits"]
    return out


def plan_instalments_for_bill(account_id: Any, *, due_by: date | None) -> dict[str, Any] | None:
    """🔒 BR-BIL-1061 (PO 2026-10-01): an ACTIVE payment plan's unpaid
    instalments, split for one bill — those due on or before the bill's due
    date (*"this month's instalment"*, the Check's own reading in
    `bill_run_checks.instalments_due`) and the rest, *"not yet due"*.

    Worked: $270 at $45 × 6, none paid, the bill due before the second
    instalment → `due_now` 45.00, `not_yet_due` 225.00, so the bill asks
    $62 + $45 = $107. None when the account has no ACTIVE plan (a proposed plan
    nobody has agreed spreads nothing), and the bill is then untouched.
    """
    from apps.payments import selectors as payment_selectors
    from apps.payments.collections_models import PLAN_ACTIVE, PaymentPlan, PaymentPlanInstallment

    tenant_id = payment_selectors._tenant_id()
    plan_ids = list(
        PaymentPlan.objects.filter(
            tenant_id=tenant_id, account_id=account_id, status=PLAN_ACTIVE
        ).values_list("id", flat=True)
    )
    if not plan_ids:
        return None
    due_now = ZERO
    later = ZERO
    for row in PaymentPlanInstallment.objects.filter(
        tenant_id=tenant_id, plan_id__in=plan_ids, paid_posted_on__isnull=True
    ).values("due_date", "amount"):
        if due_by is not None and row["due_date"] <= due_by:
            due_now += row["amount"]
        else:
            later += row["amount"]
    return {"due_now": due_now, "not_yet_due": later}


def plan_instalments_for_accounts(
    account_ids: Any, *, due_by: date | None
) -> dict[str, dict[str, Any]]:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-BIL-8720` / `DEF-BIL-8696` —
    `plan_instalments_for_bill` for a whole bill run, in two statements per
    batch: `{account_id: {"due_now", "not_yet_due"}}` for every account asked
    about that has an ACTIVE plan, and NO key for one that has none (the
    singular's None). The same split, the same `due_by` for every bill of the
    run, so Sign off's *Amount due* asks what the bills will ask ($62 + $45 =
    $107, the other $225 not yet due)."""
    from apps.payments import selectors as payment_selectors
    from apps.payments.collections_models import PLAN_ACTIVE, PaymentPlan, PaymentPlanInstallment

    tenant_id = payment_selectors._tenant_id()
    keys, filters = _account_batches(account_ids)
    wanted = set(keys)
    out: dict[str, dict[str, Any]] = {}
    for scope in filters:
        plans = PaymentPlan.objects.filter(
            tenant_id=tenant_id, account_id__in=scope, status=PLAN_ACTIVE
        )
        account_by_plan = {
            str(plan_id): str(account_id)
            for plan_id, account_id in plans.values_list("id", "account_id")
            if str(account_id) in wanted
        }
        for account_id in account_by_plan.values():
            out.setdefault(account_id, {"due_now": ZERO, "not_yet_due": ZERO})
        if not account_by_plan:
            continue
        for row in PaymentPlanInstallment.objects.filter(
            tenant_id=tenant_id, plan_id__in=plans.values("id"), paid_posted_on__isnull=True
        ).values("plan_id", "due_date", "amount"):
            account_id = account_by_plan.get(str(row["plan_id"]))
            if account_id is None:
                continue
            key = "due_now" if due_by is not None and row["due_date"] <= due_by else "not_yet_due"
            out[account_id][key] += row["amount"]
    return out


def activity_key_for_accounts(account_ids: Any, *, invoice_ids: Any = None) -> str | None:
    """`DEF-BIL-8696` — a key that MOVES whenever any payments row these
    accounts' money position is read from is written: their payments,
    refunds, payment plans and instalments, and every allocation made by their
    payments or against their bills (`invoice_ids`, billing's own queryset of
    those bills' ids, read as a subquery). `core.row_versions` explains the key.

    Billing's Sign off saves its whole-run summary and rebuilds it when this
    key — one of several — differs from the one it was built under (the OQ-843
    option C shape). It answers nothing about money and decides nothing. None
    where the database cannot say (not PostgreSQL), which the caller reads as
    *cannot tell*."""
    from django.db.models import Q

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors
    from apps.payments.collections_models import PaymentPlan, PaymentPlanInstallment
    from core import row_versions

    if not row_versions.supported():
        return None
    tenant_id = payment_selectors._tenant_id()
    scope = account_ids if hasattr(account_ids, "query") else [str(a) for a in account_ids]
    allocations = Q(payment__account_id__in=scope)
    if invoice_ids is not None:
        allocations |= Q(invoice_id__in=invoice_ids)
    plans = PaymentPlan.objects.filter(tenant_id=tenant_id, account_id__in=scope)
    return row_versions.keys(
        payment_models.Payment.objects.filter(tenant_id=tenant_id, account_id__in=scope),
        payment_models.Refund.objects.filter(tenant_id=tenant_id, account_id__in=scope),
        payment_models.Allocation.objects.filter(allocations, tenant_id=tenant_id),
        plans,
        PaymentPlanInstallment.objects.filter(tenant_id=tenant_id, plan_id__in=plans.values("id")),
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-PAY-10698 — THE NSF PENALTY A BOUNCE CHARGES (PO 2026-10-30)
# ══════════════════════════════════════════════════════════════════════════
# BR-BIL-007 puts the fee LINE in billing, so payments asks by name and writes
# no invoice. The walk (account → unit → plan → the plan's NSF code) is
# billing's — `apps/billing/nsf_fee.py` — and payments never prices a fee.
NSF_FEE_QUOTE = "quote_nsf_fee"
NSF_FEE_RAISE = "raise_nsf_fee"


def nsf_fee_quote(account_id: Any, *, on_date: date) -> dict[str, Any]:
    """The Reverse dialog's "+$30.00 NSF fee" — billing's quote, or a named absence.

    Unwired billing answers `nsf_fee_unavailable`, never an amount.
    """
    fn = _resolve(BILLING_MODULE, NSF_FEE_QUOTE, kind="services")
    if fn is None:
        return {"status": "nsf_fee_unavailable", "code": None, "amount": None}
    return fn(account_id, on_date=on_date)


def raise_nsf_fee(
    actor: Any, *, account_id: Any, on_date: date, payment_id: Any, issued_at: Any = None
) -> dict[str, Any]:
    """Ask billing to charge the NSF penalty. Never raises on a fee it cannot
    charge — the answer names why (see `apps/billing/nsf_fee.raise_nsf_fee`).

    `payment_id` is the BOUNCED payment: one NSF fee per bounced payment
    (`DEF-PAY-10740`, PO 2026-10-30)."""
    fn = _resolve(BILLING_MODULE, NSF_FEE_RAISE, kind="services")
    if fn is None:
        return {"status": "nsf_fee_unavailable", "code": None, "amount": None, "invoice_id": None}
    return fn(
        actor, account_id=account_id, on_date=on_date, payment_id=payment_id, issued_at=issued_at
    )

# ── Trace ──────────────────────────────────────────────
# Epics:    EP-PAY-02 (allocation — how money meets bills · overpayment credit)
#           Screens: — (the result renders as S33's "Applied to" column and the
#           S35 allocation panel; this file draws nothing and writes nothing)
#           NOTE: no US-ID is cited in this header ON PURPOSE. G10 reads a
#           Trace-header US-ID as "this file ships that story's TCs", and this
#           file does NOT ship US-PAY-006: that story writes `allocations` rows,
#           moves the account-balance read-model and audits the event, and none
#           of those tables exist yet. What ships here is the one PURE
#           calculation US-PAY-006 is built on. The story is named in the
#           docstring, where G10 does not read it as a completion claim — the
#           same precedent as apps/billing/late_fee.py and rating_seam.py.
# Rules:    BR-PAY-010 (allocation order: DEFAULT oldest-invoice-first; within
#           an invoice usage+base → taxes → fees last; overpayment → account
#           credit; tenant-configurable) · BR-PAY-038 (the FOURTH class between
#           taxes and fees, and its membership is tenant configuration in the
#           ledger — PO 2026-08-11, OQ-109 closed; amends BR-PAY-010 on the
#           class COUNT only) ·
#           BR-PAY-001 (default = oldest open
#           bill; staff options specific / carry credit / split) · BR-PAY-002
#           (append-only; a correction is a new row, never an edit) ·
#           BR-PAY-012 (unapplied money → account credit — what a `specific`
#           payment larger than the bill it names does with the excess) ·
#           BR-PAY-021 (allocation is evaluated off the POSTING date — a date
#           this pure function is never handed and never reads)
# Golden:   GT-7 — B5 ❄️ FROZEN, finance-signed 2026-08-08: BL-A $100 (oldest)
#           + BL-B $147.30, pay $120 "oldest first" → BL-A 100, BL-B 20,
#           remaining 127.30.
# Tests:    06-backend/tests/golden/test_gt07_partial_allocation.py (the frozen
#           figure) · 06-backend/tests/test_us_pay_006_allocation.py (the order
#           options, the refusals, and the PE-2/3/4 worked scenarios)
# Impacts:  apps/payments/services.py (publishes `allocate_payment`) ·
#           apps/billing/rating_seam.py (its `allocate_payment` resolves here)
# ───────────────────────────────────────────────────────
"""Payment allocation: spreading ONE payment across open bills.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒-adjacent money logic (allocation order
is a money rule under CLAUDE.md's sensitive-path list), AI-authored under the PO
ruling of 2026-08-09 ("AI will do it; we will review it later as human"); row
recorded in 12-governance/09-human-review-ledger.md. This file implements
finance-signed law — BR-PAY-010 (the OQ-010 closure, PO Q&A R6 2026-08-08) and
B5 GT-7 (frozen 2026-08-08) — and never invents it. Changing a signed rule or
figure needs a finance re-sign via HUMAN-GUIDE §6, never an edit here.

    ⚠️ This file is NOT on the G7 guard list (10-scripts/gates/human_owned.txt),
    which names `apps/rating/engine.py`, `apps/ledger/posting.py` and
    `core/idempotency.py` but no payments path. Allocation order is money logic
    and belongs there; that list is outside this lane's ownership and was not
    edited. REPORTED for the PO batch, not self-granted. The two markers above
    and the ledger row exist already, so the entry would pass G7 the moment it
    is added — the same disposition as the `apps/rating/pricing/**` row.

The story this serves is US-PAY-006 (the allocation engine). This module is one
calculation inside it, not the story: nothing here writes an `allocations` row,
touches a balance read-model, reads a clock or emits an audit event. It computes
an allocation; it does not post one.

PURE function contract (B1): (payment amount, open bills, order, staff targets,
within-invoice class order) -> allocation. No ORM, no clock, no writes — which
is what keeps GT-7 meaningful and is asserted directly
(tests/test_us_pay_006_allocation.py).

ONE EXCEPTION TO "NO I/O", ADDED 2026-08-11 AND STATED RATHER THAN BURIED (law
1). The PO's OQ-109 ruling put the MEMBERSHIP of the fourth allocation class in
the tenant's ledger configuration, so this module must ask whether that class is
defined before it will allocate money into it. `tenant_defined_class_members()`
resolves a published ledger read BY NAME and is reached ONLY when an open bill
states a `tenant_defined` balance. Every frozen fixture — GT-7, PE-2/3/4, TC-1 —
states the three signed classes or none, so none of them touches it, and the
repeatability and no-ORM tests still hold.

THE ORDER IS A TENANT SETTING, NOT A CONSTANT
---------------------------------------------
BR-PAY-010 makes the order tenant-configurable and BR-PAY-001 makes the staff
instruction on the entry form part of the same choice, so `order` is an argument
with the shipped default as its default value. Hardcoding "oldest first" would
encode a default as a law (T4-20/T7-13 both exist to prove it is not one).

AND SINCE 2026-08-12 THE SETTING EXISTS, which is worth stating because for one
day it did not (hard-won law 1). This module has always described `class_order`
as "the shipped DEFAULT of a tenant setting, never a constant", and until the
PO's ruling of 2026-08-12 that sentence described a setting nothing stored and
nothing read — every utility allocated under the shipped sequence. The ruling,
verbatim: *"Cant we give option to user to set the rule in settings; Im not sure
how Utilities are going to set settlement rules ; they might differ in case of
HOA or SUb metering ; better to let user set the sequence; we can give default
option and allow them to change the order"*. The sequence is now
`allocation_class_order` on the S66 Billing-defaults page
(`apps/tenancy/settings_families.py`), validated there as a PERMUTATION of the
four classes, and `apps/payments/services.record_payment` resolves it when its
caller states none (`services.tenant_class_order`). **NOTHING IN THIS FILE
CHANGED** — not the arithmetic, not the default, not the PO's figure. What
changed is that the default is now a default of something.

IMPLEMENTED — each with the rule that confirms it
-------------------------------------------------
  `oldest_first`  DEFAULT. BR-PAY-010 "DEFAULT oldest-invoice-first" +
        BR-PAY-001 "default allocation = oldest open bill". The oldest bill is
        settled in FULL before the next is touched; this is the order B5 GT-7
        freezes a figure for, and the only order any frozen figure covers.
  `newest_first`  BR-PAY-010 "tenant-configurable", with the behaviour stated
        by journey T7-13 step 4 (knob "allocation order oldest-invoice-first →
        newest-invoice-first", S66): the newest open bill is settled first and
        the older one stays outstanding. Also the "Newest bill per account"
        target of the US-PAY-008 reapply modal. NO frozen figure pins it — B5
        states none — so its test asserts T7-13's stated outcome, not a B5
        number.
  `carry_credit`  BR-PAY-001 "options: ... carry credit" + BR-PAY-010
        "overpayment → account credit". Nothing is applied to a bill; the whole
        payment carries as an account credit (US-PAY-007's lifecycle owns what
        happens to it next). US-PAY-008 TC-2 states the same shape from the
        reapply side: "reversing rows only + credit carried; no new invoice
        allocation".
  `specific`      BR-PAY-001 "options: specific". The staff member names ONE
        bill and the payment goes there — S22's "Apply to → Specific bill".
        Built 2026-08-11 on the PO's ruling (below); before it this refused.
  `split`         BR-PAY-001 "options: ... split", US-PAY-006 TC-4. The staff
        member names an amount against each of several bills; Σ = the payment.
        Built in the same ruling.

Overpayment is not a fifth mode but a property of the others: when every bill
the instruction can reach is settled, the remainder is reported as
`credit_carried`, never dropped (BR-PAY-010 "overpayment → account credit";
BR-PAY-012 "unapplied → account credit"; US-PAY-006 TC-3 / PE-4: open 292.87,
pay 350 → credit 57.13). US-PAY-007 owns carrying, auto-applying and refunding.

THE TWO PO RULINGS OF 2026-08-11 THAT BUILT THE SECOND HALF OF THIS FILE
------------------------------------------------------------------------
Until 2026-08-11 this file did two things it no longer does, and the reason it
did them is worth keeping: both were CONFIRMED law that the published seam
could not carry, so the file refused rather than inventing an interface.
The PO was shown each in plain English with a figure, and ruled "build it now".

  #5 THE WITHIN-INVOICE COMPOSITION. Shown: *"$110 against a $157.87 bill
     leaves $47.87 outstanding. Correct. But we can't say it's $21.90 usage +
     $20.97 tax + $5.00 fee."* Options: A build the breakdown now (needed for
     tax remittance) / B later. **The PO answered A**, naming tax remittance as
     the driver. So `OpenInvoice` now carries a `composition` — the OPEN
     balance per class — and each `Allocation` reports `by_class`, what the
     payment met inside that bill in the order BR-PAY-010 sets.
  #6 SPECIFIC AND SPLIT. Shown: *"'Pay this specific bill' and 'split across
     bills' refuse. Both are your confirmed staff options; neither can be
     expressed yet. A customer sends $200 and says 'put it on the September
     bill.' Today the system applies oldest-first instead."* Options: A build
     both now / B specific now, split later / C both later. **The PO answered
     A.** So the seam now carries `targets`, and both orders execute.

Neither ruling changed a RULE: BR-PAY-010 and BR-PAY-001 are unchanged and were
already CONFIRMED. What changed is that the contract can now express them.

THE WITHIN-INVOICE CLASS ORDER (BR-PAY-010, second clause) — FOUR CLASSES
--------------------------------------------------------------------------
"within invoice usage+base → taxes → fees last" is executed here as a walk over
`OpenInvoice.composition` in `class_order`, whose default is that sequence with
the fourth class the PO added on 2026-08-11 in its ruled position. It is an
ARGUMENT for the same reason `order` is one: BR-PAY-010 ends "Tenant-configurable"
and US-PAY-006 TC-5 is a tenant putting fees before taxes.

    OQ-109 CLOSED 2026-08-11 — PO ruling, option C AS AMENDED, verbatim:

        *"C Its own class between tax and fees - it can be service fees or it
        can be special fees anything; allow tenant user to define it in
        ledge[r]"*

    Two facts, both rules, and the second was the PO's own addition to the
    option as offered:

    1. **THE ORDER IS FOUR, NOT THREE** — usage+base → taxes → the tenant-defined
       class → fees LAST. The PO's worked figure, asserted in the tests so drift
       goes RED: a bill of usage+base **$100.58** + tax **$8.30** + a
       tenant-defined service fee **$15.00** + a late fee **$5.00** = **$128.88**;
       a payment of **$120.00** meets $100.58, then $8.30, then **$11.12 of the
       $15.00**, and the late fee stays LAST at **$0.00**.
    2. **THE MEMBERSHIP IS TENANT CONFIGURATION IN THE LEDGER, NOT A LIST IN
       CODE.** The PO named two examples — service fees, special fees — and then
       generalised: *"anything"*. So this module owns the class's POSITION and
       the ledger owns WHAT IS IN IT. `CLASS_TENANT_DEFINED` is a slot;
       `tenant_defined_class_members()` is the named read; and a bill that
       states the slot while the tenant has defined nothing is REFUSED
       (`AllocationClassNotConfigured`), never allocated on a default.

    THREE THINGS THE RULING DOES NOT SETTLE, raised rather than chosen:
    **OQ-123** where in the ledger UI the tenant defines it · **OQ-124** whether
    a tenant may define MORE than one such class and how those order among
    themselves (this module allows exactly one slot, which is the ruled minimum)
    · **OQ-119** what happens to bills issued before a tenant defines one.

Two properties worth knowing before reading the code:

* THE COMPOSITION IS AN INPUT, NOT A DERIVATION. The caller states each class's
  OPEN balance. Payments does not read `invoice_lines`, does not decide which
  line kinds are "usage+base", and does not subtract earlier allocations —
  every one of those is billing's knowledge (B4.2's `taxable` flag classifies
  for TAX, which is a different question from which class a payment meets), and
  a bill part-paid last cycle opens this one with class balances that no longer
  match its original lines.
* IT IS OPTIONAL, AND ABSENCE IS NOT ZERO. B5 GT-7 states two bills and no line
  detail at all; it must stay expressible, and it does — a bill with no
  composition is allocated by amount exactly as before and reports no
  breakdown. What never happens is a breakdown invented from a total. A MIXED
  list (some bills composed, some not) refuses, for the same reason a mixed
  dated/undated list does: the account-level tax outstanding would be silently
  short, and tax remittance is the reason the breakdown exists.

WHAT `targets` DOES NOT DO — and the one shape it deliberately cannot express
-----------------------------------------------------------------------------
A `split` states an amount per bill and those amounts must sum to the payment
exactly (US-PAY-006 TC-4: "Σ rows = payment amount"). It therefore performs NO
distribution arithmetic: every figure applied is one a human typed and saw. The
consequence is deliberate — a split can never introduce a rounding event into
money math, because there is nothing here to divide. US-PAY-006 TC-4's phrasing
"$100 to BL-2607-018311, rest oldest" is composed by the CALLER, which can
price the "rest" by calling this same pure function for a preview (it computes
and never posts, so a preview is free) and then submit the amounts the staff
member confirmed. An engine mode that took named amounts AND spread an unnamed
remainder by the tenant order was NOT invented: no signed rule states where an
unnamed remainder of a split goes, and the split's own confirmed invariant says
there is none. See the decision log, 2026-08-11.

A `specific` payment larger than the bill it names carries the excess as an
account credit (BR-PAY-010 "overpayment → account credit" + BR-PAY-012
"unapplied → account credit") — it does NOT roll onto the next bill, because
the customer named one bill and rolling would silently overrule them. A staff
member who wants the rest to meet another bill says so as a `split`.

MONEY
-----
Decimal end to end (`NUMERIC(18,6)`, hard rule 2) — never float, never cents; a
non-Decimal amount is refused rather than coerced. NOTHING here rounds: the
inputs are already-finalized invoice balances and every operation on them is an
exact subtraction or a minimum, so no rounding event exists to place (B4:
round only at finalization/display; US-PAY-008 §7 says the same of a
reapplication — "no rounding events (whole reapplication of existing 2dp
amounts)"). Σ(applied) + credit_carried == the payment, exactly, always; that
identity is asserted before this function returns.

THE CLASS WALK ADDED NO ROUNDING EVENT EITHER, and that is not an accident: it
takes min(what is left of this bill's share, this class's balance), which is a
comparison and a subtraction of two already-finalized figures. Σ(by_class) ==
the invoice's applied amount and Σ(remaining_by_class) == remaining_balance,
both exact, both asserted on the way out. If a future instruction ever needs
money DIVIDED — a percentage split, an "even across N bills" — that is a new
rounding event in 🔒 money math, no signed rule places it, and it must be
routed as an open question rather than solved here (B4 rounds at finalization
and display, and this is neither).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from importlib import import_module
from typing import Protocol

# ── The tenant allocation-order setting (BR-PAY-010 · BR-PAY-001) ───────────

ORDER_OLDEST_FIRST = "oldest_first"
ORDER_NEWEST_FIRST = "newest_first"
ORDER_CARRY_CREDIT = "carry_credit"
ORDER_SPECIFIC = "specific"
ORDER_SPLIT = "split"

#: The two orders that WALK the open bills; the sequence is the only difference.
ORDERED_WALKS: tuple[str, ...] = (ORDER_OLDEST_FIRST, ORDER_NEWEST_FIRST)

#: The two orders driven by a staff instruction naming bills (BR-PAY-001).
#: Both take `targets`; neither walks. Built 2026-08-11 (PO ruling #6).
TARGETED_ORDERS: tuple[str, ...] = (ORDER_SPECIFIC, ORDER_SPLIT)

#: Every order this contract can execute — the four BR-PAY-001 names plus the
#: BR-PAY-010 reconfiguration of the default.
SUPPORTED_ORDERS: tuple[str, ...] = ORDERED_WALKS + (ORDER_CARRY_CREDIT,) + TARGETED_ORDERS

# ── The within-invoice line classes (BR-PAY-010, second clause) ─────────────
#
# Mirrored in `apps.billing.rating_seam` — payments may not import billing, and
# tests/test_us_pay_006_allocation.py asserts the two copies are equal so a
# signed order cannot come to exist twice with two different meanings.

CLASS_USAGE_BASE = "usage_base"
CLASS_TAXES = "taxes"
#: THE FOURTH CLASS — PO ruling 2026-08-11, OQ-109 closed, option C as amended:
#: *"C Its own class between tax and fees - it can be service fees or it can be
#: special fees anything; allow tenant user to define it in ledge[r]"*. A SLOT
#: with a fixed position and a TENANT-DEFINED membership; this module owns the
#: position and never the membership (see `TENANT_CLASS_READ`).
CLASS_TENANT_DEFINED = "tenant_defined"
CLASS_FEES = "fees"

#: Every class BR-PAY-010's order can place, since 2026-08-11 FOUR of them. A
#: composition stating anything else is refused rather than placed: the answer
#: to "which class is this line in?" is the tenant's, held in the ledger, and
#: this module is not where a line kind gets classified.
ALLOCATION_CLASSES: tuple[str, ...] = (
    CLASS_USAGE_BASE,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_FEES,
)

#: BR-PAY-010 as EXTENDED by the PO on 2026-08-11: "within invoice usage+base →
#: taxes → **the tenant-defined class** → fees last". The shipped DEFAULT of a
#: tenant setting, never a constant (US-PAY-006 TC-5). The PO's worked figure:
#: usage+base 100.58 + tax 8.30 + a tenant-defined service fee 15.00 + a late
#: fee 5.00 = 128.88; a 120.00 payment meets 100.58, then 8.30, then 11.12 of
#: the 15.00, and the late fee stays LAST at 0.00.
#:
#: THE SETTING IT IS THE DEFAULT OF, since the PO's ruling of 2026-08-12:
#: `allocation_class_order` on the S66 Billing-defaults page
#: (`apps.tenancy.settings_families.BILLING_DEFAULTS`), seeded with exactly this
#: tuple and validated there as a permutation of `ALLOCATION_CLASSES`. Read by
#: `apps.payments.services.tenant_class_order`, which is what
#: `record_payment` hands this function when its caller states no order. This
#: tuple stays the SHIPPED value and is asserted equal to the setting's seeded
#: default (tests/test_po_20260812_allocation_class_order_setting.py), so the
#: two cannot part company.
DEFAULT_CLASS_ORDER: tuple[str, ...] = (
    CLASS_USAGE_BASE,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_FEES,
)

#: WHERE THE MEMBERSHIP OF THE FOURTH CLASS LIVES — and it is deliberately NOT
#: here. The PO's amendment is as load-bearing as the option: the class "can be
#: service fees or it can be special fees anything", and the tenant defines it
#: "in ledge[r]". A tuple of line kinds in this file would be exactly the
#: hardcoded list the ruling replaced, so the source is NAMED and resolved at
#: call time — the same discipline `apps/billing/release.py` uses for
#: `customers.selectors.mandate_coverage_for_accounts`, and the same outcome
#: today: the ledger has published nothing, so the read comes back absent and
#: the absence is REFUSED rather than filled in.
TENANT_CLASS_MODULE = "ledger"
TENANT_CLASS_READ = "allocation_class_members"

ZERO = Decimal("0")


class AllocationClassNotConfigured(ValueError):
    """A bill states the tenant-defined class and no tenant definition exists.

    Named rather than a bare `ValueError` because it is a CONFIGURATION fact,
    not a bad argument: the caller did nothing wrong, the tenant has not defined
    the class the PO's ruling created, and the honest answer is to say so. Fails
    closed (hard-won law 3) — the alternative is to allocate money against a
    class nobody defined, in a position that decides how much tax the tenant has
    collected.
    """


# ── Value types ─────────────────────────────────────────────────────────────
#
# These mirror `apps.billing.rating_seam.Allocation` / `AllocationOutcome`
# field for field, and are defined HERE rather than imported from there for the
# reason that seam's own `_as_rated_bill` gives about rating: billing calls
# payments, so payments must not import billing. The seam passes this result
# straight back to its caller, so the field names and `applied_to` ARE its
# published contract and may not drift.


@dataclass(frozen=True)
class ClassBalance:
    """One line class's share of an invoice's OPEN balance (BR-PAY-010).

    An INPUT on the way in (what a bill still owes per class) and an OUTPUT on
    the way out (`AllocationOutcome.remaining_by_class`, what the account still
    owes per class once this payment has been applied) — the same fact at two
    moments, so one type says it.
    """

    line_class: str
    balance: Decimal


@dataclass(frozen=True)
class ClassApplication:
    """What one payment put against ONE class of ONE invoice (BR-PAY-010).

    Separate from `ClassBalance` because `applied` and `balance` are different
    facts and naming both "amount" is how a movement gets read as a position.
    """

    line_class: str
    applied: Decimal


@dataclass(frozen=True)
class Allocation:
    """One invoice's share of a payment (BR-PAY-010).

    Frozen because an allocation is financial history: BR-PAY-002 / hard rule 4
    make a correction a new row, never an edit to this one.

    `by_class` is what that share met inside the bill, in the order it met it.
    Empty when the invoice stated no composition. Only classes that RECEIVED
    money appear — an allocation is a row, and a row is written for money that
    moved (the same rule `applied_to` states one level up).
    """

    invoice_number: str
    applied: Decimal
    by_class: tuple[ClassApplication, ...] = ()

    def applied_to_class(self, line_class: str) -> Decimal:
        """What this payment put against ONE class of this invoice.

        Raises when the class received nothing, for the reason `applied_to`
        raises: a class this payment never reached and a class it paid 0.00 are
        different facts, and only the first one exists.
        """
        for entry in self.by_class:
            if entry.line_class == line_class:
                return entry.applied
        raise AssertionError(
            f"no {line_class!r} application recorded on {self.invoice_number!r} — the payment "
            "did not reach that class (BR-PAY-010 orders usage+base → taxes → the "
            "tenant-defined class → fees LAST), "
            "or the bill stated no composition"
        )


@dataclass(frozen=True)
class AllocationOutcome:
    """What one payment did to the open bills it met.

    `remaining_balance` is Σ(open balances) − Σ(applied) — what the account
    still owes after this payment, which is the figure B5 GT-7 freezes as
    "remaining 127.30". `credit_carried` is the overpayment BR-PAY-010 sends to
    the account credit; US-PAY-007 owns its lifecycle from there.

    `remaining_by_class` is that same outstanding figure broken down — the
    number US-PAY-006 TC-1 states as "47.87 = 21.90 + 20.97 + 5.00" and the one
    tax remittance reads (PO ruling 2026-08-11 #5). It reports every class the
    open bills stated INCLUDING zeros, unlike `Allocation.by_class`: a tax
    outstanding of 0.00 means the tax has been collected in full, which a
    remittance report must be able to read, whereas an allocation of 0.00 is a
    row for money that never moved. It is empty only when NO open bill stated a
    composition (B5 GT-7's shape), never as a stand-in for "we did not work it
    out".
    """

    allocations: tuple[Allocation, ...]
    remaining_balance: Decimal
    credit_carried: Decimal
    remaining_by_class: tuple[ClassBalance, ...] = ()

    def applied_to(self, invoice_number: str) -> Decimal:
        """What this payment put against ONE invoice.

        Raises when the invoice received nothing, rather than reporting a zero
        it was never told about — an untouched bill and a bill allocated 0.00
        are different facts, and only the first one exists here (a row is
        written for money that moved, never for money that did not).
        """
        for allocation in self.allocations:
            if allocation.invoice_number == invoice_number:
                return allocation.applied
        raise AssertionError(f"no allocation recorded for {invoice_number!r}")

    def remaining_of(self, line_class: str) -> Decimal:
        """What the account still owes in ONE class, across every open bill."""
        for entry in self.remaining_by_class:
            if entry.line_class == line_class:
                return entry.balance
        raise AssertionError(
            f"no outstanding balance reported for {line_class!r} — the open bills stated no "
            "composition, so no breakdown exists to report (B5 GT-7's shape). A figure here "
            "would be invented, not computed"
        )


class OpenInvoiceLike(Protocol):
    """The facts an open bill contributes to an allocation.

    Structural on purpose: `rating_seam.OpenInvoice` satisfies it without this
    module importing billing, and so will the ORM-backed row when the
    `allocations` write path lands (US-PAY-006 proper).

    `composition` is OPTIONAL on the wire as well as in the rules: it is read
    with a default so a caller written against the pre-2026-08-11 three-field
    contract states no composition instead of crashing. That default is safe
    precisely because absence is a legal state and not an error — B5 GT-7 is
    exactly it — and it can never be mistaken for a computed breakdown, because
    an absent composition reports NO breakdown at all rather than zeros.
    """

    number: str
    balance: Decimal
    issued_on: date | None
    composition: tuple[ClassBalance, ...]


class AllocationTargetLike(Protocol):
    """One invoice the staff member NAMED, and the amount against it.

    `amount is None` = "this bill, up to whatever it owes" (the `specific`
    instruction: the customer named a bill, not a figure). A `split` states an
    amount per target, and every one of them is the staff member's own figure —
    nothing here divides a payment.
    """

    invoice_number: str
    amount: Decimal | None


# ── The tenant-defined class's MEMBERSHIP (PO 2026-08-11, OQ-109) ───────────


def tenant_defined_class_members() -> frozenset[str] | None:
    """What the TENANT has put in the fourth class — read, never held here.

    `None` means the tenant has not defined the class (or the ledger has not
    published the read yet, which is today's state and is the same fact from
    this side of the boundary: there is no definition to honour). An empty set
    means the same and is normalised to `None` by the caller's `if not members`.

    Resolved by NAME at call time — `apps.ledger.selectors.allocation_class_members`
    — rather than imported, so payments carries no import edge into ledger and
    the moment that lane publishes the function this seam starts using it with
    nothing to re-wire. Identical idiom to `apps/billing/release._resolve`.

    ⚠ THIS IS THE ONE READ IN THIS FILE THAT IS NOT PURE, and it is stated
    rather than buried. It happens only when a bill states the tenant-defined
    class; every ruled input in B5 and in EP-PAY-02 §7 states the three signed
    classes or none, so GT-7 and the PE fixtures never reach it. The alternative
    — a tuple of line kinds in this module — is the exact thing the PO's
    amendment replaced.
    """
    try:
        target = import_module(f"apps.{TENANT_CLASS_MODULE}.selectors")
    except ImportError:  # pragma: no cover — the module exists in this repo
        return None
    read = getattr(target, TENANT_CLASS_READ, None)
    if not callable(read):
        return None
    members = read()
    return None if members is None else frozenset(str(member) for member in members)


# ── The allocation ──────────────────────────────────────────────────────────


def allocate_payment(
    *,
    payment_amount: Decimal,
    open_invoices: tuple[OpenInvoiceLike, ...],
    order: str = ORDER_OLDEST_FIRST,
    targets: tuple[AllocationTargetLike, ...] = (),
    class_order: tuple[str, ...] = DEFAULT_CLASS_ORDER,
) -> AllocationOutcome:
    """Spread one payment across open bills (BR-PAY-010). PURE — computes, never posts.

    This is the callable `apps.billing.rating_seam.allocate_payment` resolves.
    The argument names and shapes are that seam's published contract.

    Order — WHICH BILLS the money meets (BR-PAY-010 / BR-PAY-001):
      `oldest_first` (default) — each bill in turn is settled in FULL before the
          next is touched (the order GT-7 freezes).
      `newest_first` — the same walk over the reversed sequence (BR-PAY-010
          tenant-configurable; behaviour per T7-13 step 4).
      `carry_credit` — nothing meets a bill; the payment carries as an account
          credit.
      `specific` — ONE named bill in `targets`, up to what it owes; anything it
          cannot absorb carries as credit.
      `split` — an amount per named bill in `targets`, summing to the payment
          exactly (US-PAY-006 TC-4 "Σ rows = payment amount").

    `class_order` — WHICH PART of a bill the money meets (BR-PAY-010's second
    clause), defaulting to usage+base → taxes → the tenant-defined class → fees
    LAST (the CONFIRMED three, plus the fourth the PO ruled in on 2026-08-11).
    It applies to every order, because how a bill was CHOSEN does not change how
    it is PAID. Bills that state no `composition` are allocated by amount alone
    and report no breakdown. A bill that states a `tenant_defined` balance while
    the tenant has defined no such class is REFUSED, never allocated on a guess.

    Whatever no bill the instruction reaches can absorb is reported as
    `credit_carried` (BR-PAY-010, overpayment → account credit) — never dropped.
    """
    amount = _as_decimal(payment_amount, "payment_amount")
    if amount < ZERO:
        raise ValueError(
            "payment_amount must not be negative — a reversal is a new reversing row "
            "(BR-PAY-002 / hard rule 4), never a negative allocation of the original"
        )

    invoices = tuple(open_invoices)
    _check_invoices(invoices)
    total_open = sum((invoice.balance for invoice in invoices), ZERO)
    stated_classes = _check_composition(invoices)
    _check_class_order(class_order, stated_classes)

    if order not in SUPPORTED_ORDERS:
        raise ValueError(
            f"unknown allocation order {order!r} — this contract executes "
            f"{list(SUPPORTED_ORDERS)} (BR-PAY-010 / BR-PAY-001). A misspelled tenant "
            "setting must not quietly become the default: that would allocate real money "
            "under an order nobody chose"
        )
    directives = _check_targets(order, tuple(targets), invoices, amount)

    if order == ORDER_CARRY_CREDIT:
        # BR-PAY-001 "carry credit": no bill is touched at all. Every open
        # balance stands and the whole payment becomes the account credit
        # US-PAY-007 owns (US-PAY-008 TC-2 states the same shape).
        outcome = AllocationOutcome(
            allocations=(),
            remaining_balance=total_open,
            credit_carried=amount,
            remaining_by_class=_remaining_by_class(invoices, (), class_order, stated_classes),
        )
        _check_conservation(outcome, amount, invoices)
        return outcome

    if order in TARGETED_ORDERS:
        # BR-PAY-001's staff instruction: the bills the human NAMED, in the
        # sequence they named them. Nothing is chosen here — `_check_targets`
        # has already refused anything the instruction could not mean.
        shares = list(directives)
    else:
        shares = []
        unapplied = amount
        for invoice in _ordered(invoices, order):
            if unapplied <= ZERO:
                break
            # The bill is settled in full before the next is touched; a partial
            # payment stops mid-bill and the remainder stays outstanding (GT-7).
            applied = invoice.balance if invoice.balance < unapplied else unapplied
            shares.append((invoice, applied))
            unapplied -= applied

    allocations = tuple(
        Allocation(
            invoice_number=invoice.number,
            applied=applied,
            by_class=_within_invoice(invoice, applied, class_order),
        )
        for invoice, applied in shares
        if applied > ZERO  # a row means money moved
    )
    applied_total = sum((allocation.applied for allocation in allocations), ZERO)

    outcome = AllocationOutcome(
        allocations=allocations,
        remaining_balance=total_open - applied_total,
        # BR-PAY-010: whatever no bill could absorb carries as account credit.
        credit_carried=amount - applied_total,
        remaining_by_class=_remaining_by_class(invoices, allocations, class_order, stated_classes),
    )
    _check_conservation(outcome, amount, invoices)
    return outcome


# ── The within-invoice class walk (BR-PAY-010, second clause) ───────────────


def _within_invoice(
    invoice: OpenInvoiceLike,
    applied: Decimal,
    class_order: tuple[str, ...],
) -> tuple[ClassApplication, ...]:
    """Which classes of ONE bill this payment's share of it met, in order.

    "usage+base → taxes → [the tenant-defined class] → fees LAST" executed
    literally: each class in turn absorbs what it is owed until the share runs
    out. min(what is left, this
    class's balance) — a comparison and a subtraction of two already-finalized
    figures, so no rounding event is introduced (B4; see the module docstring).

    A bill that states no composition returns (), never a fabricated one.
    """
    composition = _composition_of(invoice)
    if not composition:
        return ()

    balances = {entry.line_class: entry.balance for entry in composition}
    unapplied = applied
    met: list[ClassApplication] = []
    for line_class in class_order:
        if unapplied <= ZERO:
            break
        owed = balances.get(line_class, ZERO)
        if owed <= ZERO:
            continue
        share = owed if owed < unapplied else unapplied
        met.append(ClassApplication(line_class=line_class, applied=share))
        unapplied -= share

    if unapplied != ZERO:
        raise AssertionError(
            f"{unapplied} of the {applied} applied to {invoice.number!r} met no class — the "
            "composition foots to the balance and the balance bounds the allocation, so this "
            "is unreachable; if it fires, one of those two guarantees has been removed"
        )
    return tuple(met)


def _remaining_by_class(
    invoices: tuple[OpenInvoiceLike, ...],
    allocations: tuple[Allocation, ...],
    class_order: tuple[str, ...],
    stated_classes: frozenset[str],
) -> tuple[ClassBalance, ...]:
    """What the account still owes per class — US-PAY-006 TC-1's "21.90 + 20.97 + 5.00".

    Reported in `class_order` sequence and INCLUDING zeros, because "tax
    outstanding 0.00" is the fact a remittance report needs and is not the same
    as "no tax on this account". Empty when no bill stated a composition.
    """
    if not stated_classes:
        return ()

    outstanding = {line_class: ZERO for line_class in stated_classes}
    for invoice in invoices:
        for entry in _composition_of(invoice):
            outstanding[entry.line_class] += entry.balance
    for allocation in allocations:
        for entry in allocation.by_class:
            outstanding[entry.line_class] -= entry.applied

    return tuple(
        ClassBalance(line_class=line_class, balance=outstanding[line_class])
        for line_class in class_order
        if line_class in outstanding
    )


# ── Ordering ────────────────────────────────────────────────────────────────


def _ordered(invoices: tuple[OpenInvoiceLike, ...], order: str) -> tuple[OpenInvoiceLike, ...]:
    """The bills in the sequence `order` names — oldest or newest bill first.

    Two ways a caller can state which bill is older, and BOTH are honoured
    because B5 uses one and the database will use the other:

    * BY DATE — every bill carries `issued_on`, and they sort by it. Stable, so
      bills issued the same day keep the caller's sequence.
    * BY SEQUENCE — no bill carries a date, and the caller's own order carries
      the ordering. This is B5 GT-7's case exactly: it names BL-A as "(oldest)"
      and gives no calendar, so the seam's `OpenInvoice` leaves `issued_on`
      None "and the caller's sequence carries the ordering B5 states". The
      sequence therefore reads oldest → newest, and newest-first reverses it.

    A MIXED list refuses. A bill with no date cannot be placed against one that
    has a date without picking a convention (treat None as oldest? newest?
    keep it where it sits?), and picking one silently reorders money.
    """
    dated = [invoice for invoice in invoices if invoice.issued_on is not None]
    if dated and len(dated) != len(invoices):
        undated = [invoice.number for invoice in invoices if invoice.issued_on is None]
        raise ValueError(
            "cannot order open invoices: some carry issued_on and some do not "
            f"(undated: {undated}). Either every bill states its issue date or none does "
            "and the caller's sequence carries the ordering (B5 GT-7) — mixing the two "
            "would place a dated bill against an undated one by a convention no rule states"
        )

    newest_first = order == ORDER_NEWEST_FIRST
    if not dated:
        return tuple(reversed(invoices)) if newest_first else invoices
    return tuple(sorted(invoices, key=lambda invoice: invoice.issued_on, reverse=newest_first))


# ── Input checks and post-conditions ────────────────────────────────────────


def _as_decimal(value: object, what: str) -> Decimal:
    """Refuse anything but a Decimal (hard rule 2) rather than coerce it.

    A binary-fraction amount that arrives here is a defect upstream, and
    accepting one would hide it behind arithmetic that mostly looks right.
    """
    if isinstance(value, Decimal):
        return value
    raise TypeError(
        f"{what} must be a Decimal — money is NUMERIC(18,6), never a binary fraction "
        f"and never cents (hard rule 2); got {type(value).__name__}"
    )


def _composition_of(invoice: OpenInvoiceLike) -> tuple[ClassBalance, ...]:
    """One bill's stated class balances, or () when it states none.

    Read with a default so a caller shaped to the pre-2026-08-11 three-field
    `OpenInvoice` states no composition rather than raising AttributeError.
    Absence is a legal input (B5 GT-7 has no line detail), so it cannot be an
    error — and it is never silently promoted to zeros: a bill with no
    composition reports NO breakdown at all.
    """
    return tuple(getattr(invoice, "composition", ()) or ())


def _check_composition(invoices: tuple[OpenInvoiceLike, ...]) -> frozenset[str]:
    """Every stated composition is well formed, and either all state one or none do.

    Returns the set of classes the open bills actually named — empty when none
    did, which is what switches the whole breakdown off.

    A MIXED list refuses for the same reason a mixed dated/undated list does:
    the account-level outstanding per class would silently omit the bills that
    said nothing, and TAX REMITTANCE — the PO's stated reason for having the
    breakdown at all (ruling 2026-08-11 #5) — reads exactly that figure.
    """
    composed = [invoice for invoice in invoices if _composition_of(invoice)]
    if composed and len(composed) != len(invoices):
        silent = [invoice.number for invoice in invoices if not _composition_of(invoice)]
        raise ValueError(
            "cannot allocate: some open bills state a line composition and some do not "
            f"(no composition: {silent}). Either every bill states its usage+base / taxes / "
            "fees balances or none does — a partial breakdown would report an outstanding "
            "tax that is short by whatever the silent bills owe (BR-PAY-010)"
        )

    stated: set[str] = set()
    for invoice in invoices:
        composition = _composition_of(invoice)
        if not composition:
            continue
        seen: set[str] = set()
        total = ZERO
        for entry in composition:
            balance = _as_decimal(
                entry.balance, f"open invoice {invoice.number!r} {entry.line_class!r} balance"
            )
            if entry.line_class not in ALLOCATION_CLASSES:
                raise ValueError(
                    f"open invoice {invoice.number!r} states line class "
                    f"{entry.line_class!r}, which BR-PAY-010's order does not place — it "
                    f"orders {list(ALLOCATION_CLASSES)} and names nothing else. Since the PO's "
                    "ruling of 2026-08-11 a line that is none of usage+base, tax or fee "
                    f"belongs to {CLASS_TENANT_DEFINED!r}, the class between taxes and fees "
                    "whose MEMBERSHIP the tenant defines in the ledger — so state the balance "
                    f"under {CLASS_TENANT_DEFINED!r}. Payments does not classify lines: the "
                    "composition is an input, and mapping a line kind onto a class is the "
                    "caller's read of the tenant's own definition"
                )
            if entry.line_class in seen:
                raise ValueError(
                    f"open invoice {invoice.number!r} states class {entry.line_class!r} twice "
                    "— the class walk would take from it twice and `applied_to_class` could "
                    "report only one of them"
                )
            if balance < ZERO:
                raise ValueError(
                    f"open invoice {invoice.number!r} states a negative {entry.line_class!r} "
                    f"balance ({balance}) — a credit position is an account credit row "
                    "(US-PAY-007 / BR-PAY-012), never a class of an open bill"
                )
            seen.add(entry.line_class)
            total += balance
        if total != invoice.balance:
            raise ValueError(
                f"open invoice {invoice.number!r} states a balance of {invoice.balance} and a "
                f"composition summing to {total} — the classes must foot to the bill. The "
                f"difference of {invoice.balance - total} is money owed that no class knows "
                "about, and the allocation would leave it unreachable (BR-PAY-010)"
            )
        stated |= seen

    if CLASS_TENANT_DEFINED in stated and not tenant_defined_class_members():
        raise AllocationClassNotConfigured(
            f"an open bill states a {CLASS_TENANT_DEFINED!r} balance, but this tenant has "
            "defined no such class. The PO ruled on 2026-08-11 that the class between taxes "
            'and fees "can be service fees or it can be special fees anything" and that the '
            "tenant defines it IN THE LEDGER; the ledger publishes no "
            f"`apps.{TENANT_CLASS_MODULE}.selectors.{TENANT_CLASS_READ}`, so there is nothing "
            "to honour. Allocating anyway would put money into a class nobody defined, at the "
            "position that decides how much tax the tenant has collected. WHERE the tenant "
            "defines it is OQ-123 and what happens to bills issued before they do is OQ-119 — "
            "neither is answered here"
        )
    return frozenset(stated)


def _check_class_order(class_order: tuple[str, ...], stated_classes: frozenset[str]) -> None:
    """The within-invoice order is a tenant setting, so it is validated like one.

    BR-PAY-010 as extended on 2026-08-11 names FOUR classes and US-PAY-006 TC-5
    lets a tenant reorder them; it never lets one be dropped or invented. A
    misspelt entry that quietly skipped `taxes` would pay fees before taxes —
    the exact inversion the rule forbids — while every per-invoice total stayed
    right.
    """
    ordered = tuple(class_order)
    seen: set[str] = set()
    for line_class in ordered:
        if line_class not in ALLOCATION_CLASSES:
            raise ValueError(
                f"unknown line class {line_class!r} in the allocation class order — "
                f"BR-PAY-010 orders {list(ALLOCATION_CLASSES)} (usage+base → taxes → the "
                "tenant-defined class → fees LAST is the default since the PO's ruling of "
                "2026-08-11; a tenant may reorder those four, and may not add a fifth — "
                "whether more than one tenant-defined class may exist is OQ-124, unanswered)"
            )
        if line_class in seen:
            raise ValueError(
                f"line class {line_class!r} appears twice in the allocation class order — a "
                "sequence that names a class twice is not an order"
            )
        seen.add(line_class)

    missing = sorted(stated_classes - seen)
    if missing:
        raise ValueError(
            f"the allocation class order {list(ordered)} does not place {missing}, which the "
            "open bills state balances for — a class left out of the order would never be "
            "paid and its balance would stand outstanding forever (BR-PAY-010)"
        )


def _check_targets(
    order: str,
    targets: tuple[AllocationTargetLike, ...],
    invoices: tuple[OpenInvoiceLike, ...],
    payment_amount: Decimal,
) -> list[tuple[OpenInvoiceLike, Decimal]]:
    """The staff instruction BR-PAY-001 confirms, checked before a cent moves.

    Returns (invoice, amount) pairs in the order the staff member named them.
    Every refusal here is a case where the instruction cannot mean one thing:
    the engine says so rather than picking the reading that happens to work.
    """
    open_bills = {invoice.number: invoice for invoice in invoices}

    if order not in TARGETED_ORDERS:
        if targets:
            raise ValueError(
                f"allocation order {order!r} takes no targets, but {len(targets)} were named — "
                f"{order!r} decides which bill is paid from the bills themselves, and a named "
                "bill is a different instruction (BR-PAY-001 `specific` / `split`). Ignoring "
                "the target would apply the money somewhere the staff member did not choose "
                "while the screen said otherwise"
            )
        return []

    if not targets:
        raise ValueError(
            f"allocation order {order!r} names no invoice — it is a staff instruction about "
            "WHICH bill (BR-PAY-001), so there is nothing to execute without one. The "
            "orders that need no target are "
            f"{list(ORDERED_WALKS) + [ORDER_CARRY_CREDIT]}"
        )

    if order == ORDER_SPECIFIC:
        if len(targets) != 1:
            raise ValueError(
                f"allocation order 'specific' names exactly one bill; {len(targets)} were "
                "given. A payment divided over several named bills is a 'split', which states "
                "the amount against each (BR-PAY-001 / US-PAY-006 TC-4)"
            )
        if targets[0].amount is not None:
            raise ValueError(
                "allocation order 'specific' carries no amount — it means 'this bill, up to "
                f"what it owes', and the whole {payment_amount} payment goes at it. Naming an "
                "amount against a bill is a 'split' (BR-PAY-001); state it as one so the "
                "Σ = payment check applies"
            )

    seen: set[str] = set()
    directives: list[tuple[OpenInvoiceLike, Decimal]] = []
    for target in targets:
        number = target.invoice_number
        if number not in open_bills:
            raise ValueError(
                f"allocation names invoice {number!r}, which is not in this account's open "
                f"bills ({sorted(open_bills)}) — only an open issued invoice is an allocation "
                "target (US-PAY-006 TC-7; draft and void bills are not), and paying one that "
                "is not open would write a row against a bill with no balance"
            )
        if number in seen:
            raise ValueError(
                f"allocation names invoice {number!r} twice — one bill takes one allocation "
                "row per payment, and `applied_to` could report only one of them"
            )
        seen.add(number)

        invoice = open_bills[number]
        if target.amount is None:
            # `specific`: the named bill absorbs what it owes; BR-PAY-010 /
            # BR-PAY-012 carry the rest as an account credit rather than
            # rolling it onto a bill the customer did not name.
            applied = invoice.balance if invoice.balance < payment_amount else payment_amount
        else:
            applied = _as_decimal(target.amount, f"allocation amount for {number!r}")
            if applied <= ZERO:
                raise ValueError(
                    f"allocation names {applied} against {number!r} — an allocation row is "
                    "money that moved, so an amount must be positive. A reversal is a new "
                    "reversing row (BR-PAY-002 / hard rule 4), never a negative directive"
                )
            if applied > invoice.balance:
                raise ValueError(
                    f"allocation names {applied} against {number!r}, which owes "
                    f"{invoice.balance} — a bill never takes more than its balance "
                    "(US-PAY-006 TC-7). The excess is an overpayment and BR-PAY-010 carries "
                    "it as an account credit; it is not an allocation to this bill"
                )
        directives.append((invoice, applied))

    if order == ORDER_SPLIT:
        named = sum((applied for _invoice, applied in directives), ZERO)
        if named != payment_amount:
            raise ValueError(
                f"a split names {named} of a {payment_amount} payment — US-PAY-006 TC-4 makes "
                "Σ rows = payment amount. Naming less leaves money for the engine to place "
                "somewhere nobody stated; naming more applies money that was never received. "
                "The 'rest oldest' case is composed by the caller, which can price it with a "
                "preview call and submit the amounts the staff member confirmed"
            )
    return directives


def _check_invoices(invoices: tuple[OpenInvoiceLike, ...]) -> None:
    """Every open bill states a Decimal balance that is not negative, once."""
    seen: set[str] = set()
    for invoice in invoices:
        balance = _as_decimal(invoice.balance, f"open invoice {invoice.number!r} balance")
        if balance < ZERO:
            raise ValueError(
                f"open invoice {invoice.number!r} states a negative balance ({balance}) — "
                "a credit position is an account credit row (US-PAY-007 / BR-PAY-012), "
                "not an open bill, and no rule makes it an allocation target"
            )
        if invoice.number in seen:
            raise ValueError(
                f"open invoice {invoice.number!r} appears twice — the allocation for a bill "
                "would be ambiguous and `applied_to` could only report one of them"
            )
        seen.add(invoice.number)


def _check_conservation(
    outcome: AllocationOutcome,
    payment_amount: Decimal,
    invoices: tuple[OpenInvoiceLike, ...],
) -> None:
    """The invariants US-PAY-006 TC-7 states, checked on the way out.

    Σ(applied) ≤ the payment, Σ(applied) + credit == the payment exactly (money
    is neither invented nor lost), and no bill takes more than it was owed.
    Raised, not asserted, so `python -O` cannot switch the guard off.

    Since 2026-08-11 the same three checks run one level down, inside the bill:
    Σ(by_class) == what that bill received, and Σ(remaining_by_class) == what
    the account still owes. A class walk that dropped a cent would still foot
    at invoice level, so the invoice-level checks alone would not see it.
    """
    applied_total = sum((allocation.applied for allocation in outcome.allocations), ZERO)
    if applied_total > payment_amount:
        raise AssertionError(
            f"allocated {applied_total} of a {payment_amount} payment — "
            "Σ allocations ≤ payment amount (US-PAY-006 TC-7)"
        )
    if applied_total + outcome.credit_carried != payment_amount:
        raise AssertionError(
            f"allocated {applied_total} + carried {outcome.credit_carried} != {payment_amount} "
            "— every cent of a payment is either applied or carried (BR-PAY-010)"
        )
    owed = {invoice.number: invoice.balance for invoice in invoices}
    for allocation in outcome.allocations:
        if allocation.applied > owed[allocation.invoice_number]:
            raise AssertionError(
                f"allocated {allocation.applied} to {allocation.invoice_number!r} which owed "
                f"{owed[allocation.invoice_number]} — a bill never takes more than its balance"
            )
        if not allocation.by_class:
            continue
        by_class_total = sum((entry.applied for entry in allocation.by_class), ZERO)
        if by_class_total != allocation.applied:
            raise AssertionError(
                f"{allocation.invoice_number!r} received {allocation.applied} but its classes "
                f"account for {by_class_total} — the within-invoice walk neither invents nor "
                "loses money (BR-PAY-010)"
            )

    if outcome.remaining_by_class:
        remaining_total = sum((entry.balance for entry in outcome.remaining_by_class), ZERO)
        if remaining_total != outcome.remaining_balance:
            raise AssertionError(
                f"outstanding {outcome.remaining_balance} but its classes account for "
                f"{remaining_total} — the breakdown IS the outstanding balance, seen per "
                "class (US-PAY-006 TC-1: 47.87 = 21.90 + 20.97 + 5.00)"
            )
        for entry in outcome.remaining_by_class:
            if entry.balance < ZERO:
                raise AssertionError(
                    f"{entry.line_class!r} is outstanding {entry.balance} — a class cannot be "
                    "paid more than it owed; a credit position is an account credit row "
                    "(US-PAY-007), never a negative class balance"
                )


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-006@ba9a795 (sha1[:7] of the four frozen sources this lane was
#         written from, concatenated in order: 04-docs/02-decisions/05-golden-tests.md ·
#         04-docs/02-decisions/04-money-math-rules.md ·
#         04-docs/05-modules/08-payments/06-epics/EP-PAY-02-allocation.md ·
#         04-docs/05-modules/08-payments/02-business-rules.md)
# generated: 2026-08-11 by story-coder (payments allocation lane — GT-7)
# amended:   2026-08-11 by story-coder (four-class lane) — BR-PAY-010 extended from three
#            classes to FOUR on the PO's OQ-109 ruling; see exception (6) below.
# amended:   2026-08-12 by story-coder (tenant-settings lane) — DOCSTRINGS ONLY, no code line
#            touched: the ARITHMETIC, the DEFAULT and the PO's $128.88/$120.00 figure are
#            byte-for-byte unchanged, and tests/test_us_pay_006_allocation.py + the golden
#            suite were run unchanged to prove it. What was rewritten is the sentence
#            describing `class_order` as "the shipped DEFAULT of a tenant setting" — true as
#            an intention, false as a description, because until the PO's ruling of
#            2026-08-12 no setting existed for it to be the default OF. It now names the
#            setting (`allocation_class_order`, S66) and its reader
#            (`apps.payments.services.tenant_class_order`), in the past tense about the gap.
# amended:   2026-08-11 by story-coder (composition + staff targets lane), implementing
#            PO rulings #5 (build the within-invoice breakdown now — tax remittance) and
#            #6 (build specific and split now) of 2026-08-11. Exceptions (1) and (2) below
#            were the two gaps those rulings closed; they are kept, struck through, because
#            the REASON they existed is the reason the seam has the shape it now has.
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — pure calculation, no endpoint) E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests -m golden → 12 passed / 1 xfailed✔ (GT-7 PASS, figures untouched) · pytest tests/test_us_pay_006_allocation.py → 48 passed✔ (2026-08-11 four-class lane; was 45) · 10-scripts/03-golden-verify.py 33 PASS/0 FAIL✔ · run_gates 15 PASS/0 FAIL/1 SKIP✔
# exceptions: (1) ~~The WITHIN-invoice class order is CONFIRMED law and is NOT implemented~~ CLOSED 2026-08-11
#         by PO ruling #5 ("build it now", driver: tax remittance). `OpenInvoice.composition` states each
#         class's OPEN balance and `Allocation.by_class` reports what the payment met;
#         `AllocationOutcome.remaining_by_class` reports US-PAY-006 TC-1's "47.87 = 21.90 + 20.97 + 5.00".
#         The composition is an INPUT — payments does not read `invoice_lines` and does not classify them
#         — and is OPTIONAL, because B5 GT-7 states no line detail and must stay expressible. (2)
#         ~~`specific` and `split` refuse with NotImplementedError~~ CLOSED 2026-08-11 by PO ruling #6
#         ("build both now"). The seam now carries `targets`. (3) `newest_first` IS implemented;
#         BR-PAY-010 confirms the order is tenant-configurable and journey T7-13 step 4 states the
#         behaviour, but NO frozen figure covers it — its test asserts T7-13's stated outcome, not a B5
#         number. (4) 🔒-adjacent money logic NOT on the G7 guard list (10-scripts/gates/human_owned.txt
#         names no payments path); markers + ledger row are in place, adding the entry is REPORTED for the
#         PO batch, not self-granted. (5) A MIXED dated/undated invoice list refuses rather than picking a
#         placement convention no rule states — and so does a MIXED composed/uncomposed one, for the same
#         reason. (6) ~~NOT DECIDED HERE, routed instead: a line class that is neither usage+base, taxes
#         nor fees has no stated place in BR-PAY-010's order~~ CLOSED 2026-08-11 by PO ruling on OQ-109,
#         option C AS AMENDED — verbatim: *"C Its own class between tax and fees - it can be service fees
#         or it can be special fees anything; allow tenant user to define it in ledge[r]"*. BR-PAY-010 now
#         orders FOUR classes and `DEFAULT_CLASS_ORDER` is usage+base → taxes → `tenant_defined` → fees
#         LAST; the PO's figure ($128.88 bill, $120.00 payment → 100.58 / 8.30 / 11.12, late fee 0.00) is
#         asserted so drift goes RED, and was proved RED by moving the class after fees: `AssertionError:
#         assert Decimal('6.12') == Decimal('11.12')` with `ClassApplication(line_class='fees',
#         applied=Decimal('5.00'))` in the by_class tuple — the late fee paid instead of left LAST. (6b)
#         THE MEMBERSHIP IS NOT IN THIS FILE and that is the amendment, not a shortcut:
#         `TENANT_CLASS_MODULE`/`TENANT_CLASS_READ` name `apps.ledger.selectors.allocation_class_members`,
#         `tenant_defined_class_members()` resolves it at call time, and a bill stating the class while
#         the ledger publishes nothing is REFUSED with `AllocationClassNotConfigured` (proved RED:
#         `Failed: DID NOT RAISE AllocationClassNotConfigured`). Nothing in the repo publishes that read
#         yet, so the ruled ORDER ships and the ruled MEMBERSHIP waits on the ledger — stated, not implied
#         (law 1/2). (6c) THAT RESOLUTION IS THE ONE NON-PURE READ IN THIS FILE. It runs only when a bill
#         states `tenant_defined`; GT-7, PE-2/3/4 and TC-1 state the three signed classes or none and
#         never reach it, so the purity and repeatability tests still hold. (6d) THREE THINGS THE RULING
#         DOES NOT SETTLE, minted rather than chosen: OQ-123 (where in the ledger UI the class is
#         defined), OQ-124 (whether more than one may exist and how they order among themselves — this
#         file allows exactly ONE slot, the ruled minimum), OQ-119 (what happens to bills issued before a
#         tenant defines one). (7) A split states every amount and Σ = payment (US-PAY-006 TC-4's own
#         invariant), so NOTHING here divides money and no new rounding event exists; TC-4's "rest oldest"
#         is composed by the caller from a preview call. A percentage or even split WOULD be a new
#         rounding event in 🔒 money math and is not invented — decision log 2026-08-11.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-184-BRC10 — receivables by service (R1 the sharing · R2's and
#           R3's read model · R5 the ageing Service filter's share)
# Rules:    decision log 2026-10-14 *"RECEIVABLES BY SERVICE: WHAT IS STILL
#           OWED IS SHARED IN PROPORTION — INSIDE THE ALLOCATION ORDER ALREADY
#           SET (C1 → a)"* · BR-PAY-010 / BR-PAY-038 (the within-bill class
#           order, a tenant setting) · BR-PAY-032 (a bill with no due date is
#           in the total and in no band) · BR-BIL-072 (what a bill asks for is
#           `amount_due`, never `total`) · BR-PAY-021 (posting date) ·
#           CLAUDE.md hard rules 1 and 2 · NFR-3 / NFR-5
# Tests:    06-backend/tests/test_cr184_receivables_by_service.py
# Impacts:  apps/payments/billing_seam.aging_positions_page (the Service
#           filter's share) · apps/reports/queries.receivables_dataset ·
#           apps/reports/receivables_by_service (the library report)
# ───────────────────────────────────────────────────────
"""WHAT IS STILL OWED, PER SERVICE — shared in proportion, inside the class order.

HUMAN-REVIEW-PENDING — money-adjacent read logic, AI-authored under the PO
ruling of 2026-08-09 (*"AI will do it; we will review it later as human"*).
It WRITES NOTHING: no allocation, no posting, no stored figure. Every number
here is computed per report run from rows other code wrote.

THE RULE, QUOTED FROM THE DECISION LOG (2026-10-14, PO C1 → a)
──────────────────────────────────────────────────────────────
    "the class order says how much of each class is still owed; what is owed
    in a class is then shared across services in proportion to each service's
    part of that class on the bill. Worked: water 80.00 + sewer 40.00 (usage +
    base 120.00) + tax 8.00 + late fee 5.00 = 133.00; paid 60.00 → usage +
    base receives 60.00, leaving 60.00 owed = water 40.00 + sewer 20.00; tax
    8.00 and fee 5.00 untouched. A tax or fee line that names its service
    follows it; one that names none is reported on its own row, never guessed
    onto a service. The rows foot to the ledger receivable or the report says
    so."

HOW ONE BILL IS SHARED (`share_bill`)
─────────────────────────────────────
1. **Each line lands on a ROW**: the line's own service when it names one;
   otherwise its class's own row — *Taxes*, *Fees*, *Usage & base*, *Other
   charges*. A line is never moved onto a service it does not name.
2. **Each line has a CLASS** — `usage`/`base` → usage + base, `tax` → taxes,
   `fee` → fees. Nothing maps onto the tenant-defined class, because the
   ledger publishes no membership for it (BR-PAY-038) — that class is simply
   empty here rather than guessed. `minimum`, `adjustment`, `discount` and
   `deposit` map onto NO class: which class a `minimum` line is in is
   **OQ-128, OPEN**, and is not decided by this file (see 4c).
3. **An UNPAID bill is owed line for line.** When nothing has been allocated
   and the bill asks exactly the sum of its lines, each row owes exactly its
   lines' sum: no class, no division, no rounding.
4. **A PART-PAID bill** is shared in three steps:
     a. What each class has been paid is READ from `allocation_classes` (the
        stored breakdown, CR-060 C19). Money with no stored breakdown — every
        allocation before `payments/0015`, a credit application, a release —
        is walked through the tenant's OWN `allocation_class_order` (the
        setting on S66, read through `services.tenant_class_order`), oldest
        class first, each class taking what it still owes. That is the
        allocation rule itself (BR-PAY-010), applied to money that did not
        record which class it met; the stored breakdown always wins where it
        exists. ⚠ A tenant who CHANGED its order since such a payment sees it
        walked under today's order — the record holds no other.
     b. A class's remainder is shared across that class's rows in proportion
        to their amounts in that class (the PO's C1 → a). A class whose rows
        do not all carry a positive amount keeps its remainder on its own row.
     c. **A bill carrying a line no class places, once paid in part, cannot be
        walked** (OQ-128): it is shared by plain proportion over all its rows
        and COUNTED (`shared_without_class_order`), so the gap is a number on
        the report and never a silent choice.
5. **A bill whose lines do not add up to what it asks** — budget billing,
   BR-BIL-072 *"Level is due"* — has its remainders scaled in proportion to
   what it asks, so the rows still sum to the bill's owed amount. Counted
   (`shared_against_what_the_bill_asks`).
6. **Rounding — the rule, stated because a reviewer must be able to redo it.**
   Shares are computed EXACTLY (`fractions.Fraction`, never a float and never
   a 28-digit `Decimal` division that can lose the last unit). Each share is
   then cut DOWN to 4 decimal places (6 when the bill's owed amount itself
   carries more); the units that cutting left over — always fewer than the
   number of rows — go ONE AT A TIME to the rows with the LARGEST cut-off
   fraction, ties broken by row order (services by code, then the class rows
   in the order usage + base → taxes → tenant-defined → fees → other). So the
   rows sum to the bill's owed amount EXACTLY, every time, and the same bill
   always shares the same way. Worked: 100.00 over three equal lines →
   33.3334 + 33.3333 + 33.3333 (the first row by order takes the unit).
   Money is DISPLAYED at 2 (hard rule 2) — so those three print as 33.33 each
   beside a total of 100.00; the stored arithmetic is exact and the display is
   a display.

WHAT THE ROWS FOOT TO
─────────────────────
Σ of every row of every bill = Σ of every bill's owed amount = the ageing's
population at the same date (`aging_positions_page`, the same bill set: issued
by `as_of`, money posted by `as_of`, `amount_due − Σ allocations > 0`). That
identity is asserted by the tests rather than believed.

⚠ **A BALANCE MOVED TO THE OWNER (CR-185 D5) MOVES ROWS, NOT THE TOTAL —
`DEF-REP-10159`.** The move is a journal entry and touches no bill, so the
tenant's bills stay open; `apply_balance_moves` settles them oldest first and
hands the settled part to the owner with each bill's own shares and due date.
Σ is unchanged; only the debtor moves (R2 and R3; the ageing's SQL path does
not yet — `DEF-REP-10160`). The comparison with the
ledger's AR control is made by the REPORT, which states a difference and never
adjusts it away (BR-REP-008).

COST (`NFR-3` / `NFR-5`)
────────────────────────
The bills are read in KEYSET chunks of `CHUNK` ordered by id, and each chunk
costs three statements (bills, lines, stored class breakdown) — never one per
bill, which is what made `/outstandings` 40,041 statements at 40,046 debtors.
No cap, no `[:N]` on the population; a page is cut AFTER the whole filtered set
is totalled, so the totals describe the debt and not the page.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import ROUND_FLOOR, Decimal
from fractions import Fraction
from typing import Any

from apps.payments.allocation import (
    ALLOCATION_CLASSES,
    CLASS_FEES,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_USAGE_BASE,
)

ZERO = Decimal("0")
FOUR_DP = Decimal("0.0001")
SIX_DP = Decimal("0.000001")

#: The row a line no class places lands on when it names no service, and the
#: row a bill with no lines at all is owed on. Its own word on screen
#: (*Other charges*), never folded into a service.
CLASS_OTHER = "other"

#: Line kind → allocation class. ⚠ **FOUR KINDS AND NO MORE, DELIBERATELY.**
#: `minimum` and `adjustment` are `LINE_KINDS` with no signed class (OQ-128,
#: OPEN); `discount` and `deposit` are written by the engine and placed by no
#: document. Absent here means *no class* — `share_bill` then refuses to walk
#: a part-paid bill and shares it by plain proportion, counted (step 4c).
CLASS_OF_KIND: dict[str, str] = {
    "usage": CLASS_USAGE_BASE,
    "base": CLASS_USAGE_BASE,
    "tax": CLASS_TAXES,
    "fee": CLASS_FEES,
}

#: The order class ROWS sort in, after every service row. It is a DISPLAY and
#: tie-break order and never the allocation order, which is the tenant's.
CLASS_ROW_ORDER: tuple[str, ...] = (
    CLASS_USAGE_BASE,
    CLASS_TAXES,
    CLASS_TENANT_DEFINED,
    CLASS_FEES,
    CLASS_OTHER,
)

#: How a bill came to be shared — counted per run so the report can say so.
METHOD_UNPAID = "unpaid"
METHOD_CLASS_WALK = "class_walk"
METHOD_PROPORTION = "shared_without_class_order"
METHOD_NO_LINES = "no_lines"

#: Bills per keyset chunk — three statements each, whatever the tenant's size.
CHUNK = 2000

#: The band a bill with no due date takes: in the Total, in no band
#: (BR-PAY-032). Deliberately not one of the band names.
UNDATED = "__undated__"


# ════════════════════════════════════════════════════════════════════════════
# ONE BILL — pure, no ORM, no clock
# ════════════════════════════════════════════════════════════════════════════
#: A row is `(service_code, None)` for a service and `(None, class)` for a
#: class's own row. Exactly one half is set.
Target = tuple[str | None, str | None]


def target_order(target: Target) -> tuple[int, str]:
    """Row order: services by code first, then the class rows in
    `CLASS_ROW_ORDER`. The tie-break of the rounding rule (step 6)."""
    service, line_class = target
    if service is not None:
        return (0, service)
    position = CLASS_ROW_ORDER.index(line_class) if line_class in CLASS_ROW_ORDER else 99
    return (1, f"{position:02d}")


@dataclass(frozen=True)
class BillLine:
    service_code: str | None
    kind: str
    amount: Decimal


@dataclass(frozen=True)
class BillShare:
    """What ONE bill still owes, per row. `shares` sums to `owed` exactly."""

    shares: dict[Target, Decimal]
    method: str
    #: True when the remainders were scaled to what the bill ASKS (step 5).
    scaled: bool = False


def _unit_for(owed: Decimal) -> Decimal:
    """4 dp (hard rule 2), or 6 when the owed figure itself carries more — a
    stored 6-dp container must still share to its own last unit exactly."""
    return FOUR_DP if owed == owed.quantize(FOUR_DP) else SIX_DP


def _cut(exact: dict[Target, Fraction], owed: Decimal) -> dict[Target, Decimal]:
    """Step 6 — cut down, then hand out the leftover units by largest fraction.

    `exact` must sum to `owed` (as a Fraction); asserted, because a share that
    did not would make every row on the report quietly wrong.
    """
    total = Fraction(owed)
    if sum(exact.values(), Fraction(0)) != total:  # pragma: no cover - guarded by callers
        raise ValueError("receivables-by-service: the exact shares do not sum to the bill")
    unit = _unit_for(owed)
    unit_f = Fraction(unit)
    floors: dict[Target, Fraction] = {}
    fractions_left: dict[Target, Fraction] = {}
    for target, value in exact.items():
        units = (value / unit_f).__floor__()
        floors[target] = units * unit_f
        fractions_left[target] = value - floors[target]
    leftover = int((total - sum(floors.values(), Fraction(0))) / unit_f)
    ranked = sorted(exact, key=lambda t: (-fractions_left[t], target_order(t)))
    for target in ranked[:leftover]:
        floors[target] += unit_f
    out = {
        target: (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
            unit, rounding=ROUND_FLOOR
        )
        for target, value in floors.items()
    }
    if sum(out.values(), ZERO) != owed:  # pragma: no cover - the arithmetic above
        raise ValueError("receivables-by-service: the cut shares do not sum to the bill")
    return out


def _proportion(weights: dict[Target, Decimal], owed: Decimal) -> dict[Target, Fraction] | None:
    total = sum(weights.values(), ZERO)
    if total <= ZERO:
        return None
    return {t: Fraction(owed) * Fraction(w) / Fraction(total) for t, w in weights.items()}


def share_bill(
    *,
    owed: Decimal,
    lines: Iterable[BillLine],
    allocated: Decimal,
    paid_by_class: dict[str, Decimal] | None,
    class_order: tuple[str, ...],
) -> BillShare:
    """Share ONE bill's owed amount across its rows. See the module docstring.

    `owed` = what the bill asks (`amount_due`) − every allocation posted by the
    as-of date, and is > 0. `paid_by_class` is the STORED breakdown of those
    allocations (`allocation_classes`), possibly empty. `class_order` is the
    tenant's own setting. Returns shares summing to `owed` exactly.
    """
    if not isinstance(owed, Decimal) or not isinstance(allocated, Decimal):
        raise TypeError("money is Decimal, never float or cents (hard rule 2)")
    by_class: dict[str, dict[Target, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    per_target: dict[Target, Decimal] = defaultdict(lambda: ZERO)
    for line in lines:
        line_class = CLASS_OF_KIND.get(line.kind, CLASS_OTHER)
        target: Target = (
            (line.service_code, None) if line.service_code else (None, line_class)
        )
        by_class[line_class][target] += line.amount
        per_target[target] += line.amount

    if not per_target:
        return BillShare(shares={(None, CLASS_OTHER): owed}, method=METHOD_NO_LINES)

    billed = sum(per_target.values(), ZERO)
    # ── 3 · unpaid and asking exactly its lines: line for line, exact ──────
    if allocated == ZERO and billed == owed:
        return BillShare(
            shares={t: v for t, v in per_target.items() if v != ZERO} or {(None, CLASS_OTHER): owed},
            method=METHOD_UNPAID,
        )

    def proportion_fallback(scaled: bool = False) -> BillShare:
        exact = _proportion(dict(per_target), owed)
        if exact is None:
            return BillShare(shares={(None, CLASS_OTHER): owed}, method=METHOD_PROPORTION)
        return BillShare(shares=_cut(exact, owed), method=METHOD_PROPORTION, scaled=scaled)

    # ── 4c · a class nobody placed, on a bill that is not simply unpaid ────
    if any(v != ZERO for v in by_class.get(CLASS_OTHER, {}).values()):
        return proportion_fallback()

    # ── 4a · what each class still owes, in the tenant's order ─────────────
    billed_by_class = {c: sum(rows.values(), ZERO) for c, rows in by_class.items()}
    stored = {c: v for c, v in (paid_by_class or {}).items() if c in ALLOCATION_CLASSES}
    remaining = {c: billed_by_class.get(c, ZERO) - stored.get(c, ZERO) for c in ALLOCATION_CLASSES}
    left = allocated - sum(stored.values(), ZERO)
    walk = [c for c in class_order if c in ALLOCATION_CLASSES] + [
        c for c in ALLOCATION_CLASSES if c not in class_order
    ]
    if left > ZERO:
        for line_class in walk:
            take = min(max(remaining[line_class], ZERO), left)
            remaining[line_class] -= take
            left -= take
    if left != ZERO:
        # Money the walk could not place (more than the lines, or a net
        # reversal with no stored breakdown) — the order cannot say where it
        # went, so the bill is shared by proportion and counted.
        return proportion_fallback()

    open_classes = {c: r for c, r in remaining.items() if r != ZERO}
    open_total = sum(open_classes.values(), ZERO)
    if open_total <= ZERO or any(r < ZERO for r in open_classes.values()):
        return proportion_fallback()

    # ── 5 · scale to what the bill ASKS when the lines say otherwise ───────
    factor = Fraction(owed) / Fraction(open_total)
    scaled = factor != 1

    # ── 4b · each class's remainder across its rows, in proportion ─────────
    exact: dict[Target, Fraction] = defaultdict(Fraction)
    for line_class, rest in open_classes.items():
        rows = by_class.get(line_class, {})
        class_billed = billed_by_class.get(line_class, ZERO)
        portion = Fraction(rest) * factor
        # A 0.00 row (a zero base, say) takes nothing and decides nothing; a
        # NEGATIVE row inside a class has no proportion that means anything,
        # so the class keeps its remainder on its own row.
        if class_billed <= ZERO or any(v < ZERO for v in rows.values()):
            exact[(None, line_class)] += portion
            continue
        for target, amount in rows.items():
            if amount == ZERO:
                continue
            exact[target] += portion * Fraction(amount) / Fraction(class_billed)
    return BillShare(shares=_cut(dict(exact), owed), method=METHOD_CLASS_WALK, scaled=scaled)


# ════════════════════════════════════════════════════════════════════════════
# MANY BILLS — read in keyset chunks, three statements a chunk
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class SharedBill:
    """One open bill at the as-of date and its rows."""

    invoice_id: Any
    account_id: Any
    due_date: date | None
    currency: str | None
    owed: Decimal
    band: str
    share: BillShare


@dataclass
class ShareRun:
    """Counts a run states on its answer (hard-won law 7: a number beside a
    blind spot)."""

    bills: int = 0
    methods: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    scaled: int = 0
    currencies: set = field(default_factory=set)
    #: DEF-REP-10159 — balances moved tenant → owner that were carried over
    #: open bills, and the part of them no open bill was left to carry.
    moves: int = 0
    moved_without_a_bill: Decimal = ZERO

    def note(self, bill: SharedBill) -> None:
        self.bills += 1
        self.methods[bill.share.method] += 1
        self.scaled += int(bill.share.scaled)
        if bill.currency:
            self.currencies.add(bill.currency)

    def problems(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        proportion = self.methods.get(METHOD_PROPORTION, 0)
        if proportion:
            out.append(
                {
                    "code": "bills_shared_without_class_order",
                    "br_ref": "OQ-128",
                    "bills": proportion,
                    "detail": f"{proportion} part-paid bill(s) carry a line no allocation "
                    "class places (a minimum, adjustment, discount or deposit line — OQ-128 is "
                    "open), or money the class order could not place, so the class order could "
                    "not be walked. Each was shared by plain proportion over its lines; every "
                    "row still sums to what the bill owes.",
                }
            )
        if self.moved_without_a_bill > ZERO:
            out.append(
                {
                    "code": "balance_moved_to_owner_without_an_open_bill",
                    "br_ref": "DEF-REP-10159 · CR-185-BRC10 D5",
                    "amount": f"{self.moved_without_a_bill:f}",
                    "detail": f"{self.moved_without_a_bill:f} moved from tenants to owners had no "
                    "open bill left behind it on the tenant's account (an imported balance, "
                    "say), so no service share could travel with it. It is on no row; the "
                    "foot against the books states the difference.",
                }
            )
        if self.scaled:
            out.append(
                {
                    "code": "bills_shared_against_what_they_ask",
                    "br_ref": "BR-BIL-072",
                    "bills": self.scaled,
                    "detail": f"{self.scaled} bill(s) ask an amount other than the sum of "
                    "their lines (budget billing — 'Level is due'). Their class remainders "
                    "were scaled in proportion to what each bill asks.",
                }
            )
        return out


def band_of(due_date: date | None, as_of: date, bands: Any) -> str:
    """The same `CASE` `aging_positions_page` builds in SQL, in Python: a bill
    ages on its OWN due date; no due date → `UNDATED` (BR-PAY-032)."""
    if due_date is None:
        return UNDATED
    if due_date >= as_of:
        return bands.current
    for name, upper in bands.thresholds:
        if due_date >= as_of - timedelta(days=upper):
            return name
    return bands.overflow


def open_bills_queryset(*, as_of: date, account_ids: Any = None) -> Any:
    """The open bills at `as_of`, EXACTLY the set `aging_positions_page` ages.

    Issued by `as_of` (`DEF-PAY-6940`), money posted by `as_of` (BR-PAY-021),
    measured at what the bill ASKS (BR-BIL-072), owing more than zero. Values:
    `id · account_id · due_date · currency · amount_due · allocated_sum ·
    open_balance`. LAZY.
    """
    from django.db.models import DecimalField, F, OuterRef, Subquery, Sum, Value
    from django.db.models.functions import Coalesce

    from apps.payments import billing_seam
    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    money = DecimalField(max_digits=18, decimal_places=6)
    published = billing_seam._resolve(billing_seam.BILLING_MODULE, billing_seam.AGING_QUERYSET_READ)
    if published is None:  # pragma: no cover - billing publishes it
        raise LookupError("billing publishes no open-invoice read")
    tenant_id = payment_selectors._tenant_id()
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
    bills = published(billing_seam.OPEN_INVOICE_STATUSES).filter(issued_at__date__lte=as_of)
    if account_ids is not None:
        bills = bills.filter(account_id__in=account_ids)
    return bills.annotate(
        allocated_sum=allocated, open_balance=F("amount_due") - allocated
    ).filter(open_balance__gt=ZERO)


def _class_breakdown(invoice_ids: list[Any], as_of: date) -> dict[Any, dict[str, Decimal]]:
    """The STORED class breakdown of each bill's allocations posted by `as_of`."""
    from django.db.models import Sum

    from apps.payments import models as payment_models
    from apps.payments import selectors as payment_selectors

    rows = (
        payment_models.AllocationClass.objects.filter(
            tenant_id=payment_selectors._tenant_id(),
            allocation__invoice_id__in=invoice_ids,
            allocation__payment__posted_at__date__lte=as_of,
        )
        .values("allocation__invoice_id", "line_class")
        .annotate(total=Sum("amount"))
        .order_by()
    )
    out: dict[Any, dict[str, Decimal]] = defaultdict(dict)
    for row in rows:
        out[row["allocation__invoice_id"]][row["line_class"]] = row["total"]
    return out


def _lines_for(invoice_ids: list[Any]) -> tuple[dict[Any, list[BillLine]], dict[str, str]]:
    from apps.payments import billing_seam

    read = billing_seam._resolve(billing_seam.BILLING_MODULE, LINES_READ)
    if read is None:  # pragma: no cover - billing publishes it
        raise LookupError(f"apps.billing.selectors.{LINES_READ} is not published")
    out: dict[Any, list[BillLine]] = defaultdict(list)
    names: dict[str, str] = {}
    for row in read(invoice_ids):
        code = row["service_code"]
        if code and row.get("service_name"):
            names[code] = row["service_name"]
        out[row["invoice_id"]].append(
            BillLine(service_code=code, kind=row["kind"], amount=row["amount"])
        )
    return out, names


#: Billing's published line read (`apps.billing.selectors`), named once.
LINES_READ = "receivable_lines_for_invoices"


def tenant_class_order() -> tuple[str, ...]:
    """The tenant's own within-bill class order — the S66 setting, read through
    the one function the payment path reads it through (never a default here)."""
    from apps.payments import services

    return services.tenant_class_order()


def iter_shared_bills(
    bills: Any,
    *,
    as_of: date,
    bands: Any,
    class_order: tuple[str, ...] | None = None,
    run: ShareRun | None = None,
    service_names: dict[str, str] | None = None,
) -> Iterator[SharedBill]:
    """Every bill of `bills` (an `open_bills_queryset`, possibly narrowed),
    shared. Keyset chunks on `id`; three statements a chunk (`NFR-3`)."""
    order = class_order if class_order is not None else tenant_class_order()
    last = None
    base = bills.order_by("id")
    while True:
        chunk_qs = base if last is None else base.filter(id__gt=last)
        chunk = list(
            chunk_qs.values(
                "id", "account_id", "due_date", "currency", "allocated_sum", "open_balance"
            )[:CHUNK]
        )
        if not chunk:
            return
        last = chunk[-1]["id"]
        ids = [row["id"] for row in chunk]
        lines, names = _lines_for(ids)
        if service_names is not None:
            service_names.update(names)
        stored = _class_breakdown(ids, as_of)
        for row in chunk:
            owed = row["open_balance"]
            share = share_bill(
                owed=owed,
                lines=lines.get(row["id"], ()),
                allocated=row["allocated_sum"],
                paid_by_class=stored.get(row["id"]),
                class_order=order,
            )
            bill = SharedBill(
                invoice_id=row["id"],
                account_id=row["account_id"],
                due_date=row["due_date"],
                currency=row["currency"],
                owed=owed,
                band=band_of(row["due_date"], as_of, bands),
                share=share,
            )
            if run is not None:
                run.note(bill)
            yield bill
        if len(chunk) < CHUNK:
            return


# ════════════════════════════════════════════════════════════════════════════
# A BALANCE MOVED TO THE OWNER — the tenant's open bills travel with it
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class BalanceMove:
    """One CR-185 D5 balance-to-owner, as the books hold it at the as-of date."""

    from_account_id: Any
    to_account_id: Any
    amount: Decimal
    entry_date: date


#: The ledger's published read (`apps.ledger.reporting`), named once.
MOVES_READ = "balance_to_owner_moves"


def balance_moves(*, as_of: date) -> tuple[BalanceMove, ...]:
    """Every balance moved tenant → owner with a BOOK date on or before `as_of`
    — read from the journal entry itself (`ledger.reporting`), never from the
    tie-back promise, so the report and the ledger cannot disagree about it."""
    from uuid import UUID

    from apps.payments import billing_seam

    read = billing_seam._resolve("ledger", MOVES_READ, kind="reporting")
    if read is None:  # pragma: no cover - the ledger publishes it
        return ()
    return tuple(
        BalanceMove(
            from_account_id=UUID(str(row["from_account_id"])),
            to_account_id=UUID(str(row["to_account_id"])),
            amount=row["amount"],
            entry_date=row["entry_date"],
        )
        for row in read(end=as_of)
    )


def split_share(share: BillShare, owed: Decimal, part: Decimal) -> tuple[BillShare, BillShare]:
    """Cut `part` of a bill's rows off, in proportion, and keep the rest.

    `moved` sums to `part` EXACTLY and `kept` to `owed − part` exactly — the
    same rounding rule as every share (step 6), so a moved balance carries the
    bill's service split to the last unit and nothing is created or lost.
    """
    if part >= owed:
        return share, BillShare(shares={}, method=share.method, scaled=share.scaled)
    exact = {
        target: Fraction(value) * Fraction(part) / Fraction(owed)
        for target, value in share.shares.items()
    }
    moved = _cut(exact, part)
    kept = {target: value - moved.get(target, ZERO) for target, value in share.shares.items()}
    return (
        BillShare(shares=moved, method=share.method, scaled=share.scaled),
        BillShare(shares=kept, method=share.method, scaled=share.scaled),
    )


def _oldest_first(bill: SharedBill) -> tuple[int, date, str]:
    """The order a moved balance settles the tenant's bills: oldest due date
    first, undated last, then the bill id — stable, so a re-run moves the same
    shares."""
    if bill.due_date is None:
        return (1, date.max, str(bill.invoice_id))
    return (0, bill.due_date, str(bill.invoice_id))


def apply_balance_moves(
    bills: Iterable[SharedBill],
    moves: tuple[BalanceMove, ...],
    *,
    run: ShareRun | None = None,
) -> Iterator[SharedBill]:
    """`DEF-REP-10159` — the tenant's open bills after a balance moved to the owner.

    A CR-185 D5 balance-to-owner is ONE journal entry, AR (owner) / AR
    (tenant), and it touches no bill: the tenant's bills stay open in
    `invoices`, so a read of open bills went on naming the departed tenant as
    the debtor while the books named the owner. This is where the two meet.

    **THE RULE (decision log 2026-10-14, *"A BALANCE MOVED TO THE OWNER CARRIES
    THE TENANT'S BILL SHARES WITH IT"*):** the move SETTLES the tenant's open
    bills oldest first, as a payment would; whatever part of a bill it settles
    is owed by the OWNER instead, with that bill's own service shares (cut in
    proportion — `split_share`) and that bill's own due date, so the owner's
    debt ages from when the tenant's did. Worked, the walk's own figure: the
    tenant owed $344.26 + a final bill of $20.95; $365.21 moved → the tenant
    owes $0.00 on every service and the owner owes $365.21, split across the
    same services the two bills were.

    A part of the move with no open bill left to carry it (an imported balance,
    which is in the books and in no bill) is on NO row and is COUNTED on `run`
    — never placed on a service it does not name. Σ owed is unchanged by this
    function: shares move between accounts and none is created.
    """
    if not moves:
        yield from bills
        return
    by_source: dict[Any, list[BalanceMove]] = defaultdict(list)
    for move in sorted(moves, key=lambda m: (m.entry_date, str(m.to_account_id))):
        by_source[move.from_account_id].append(move)
    held: dict[Any, list[SharedBill]] = defaultdict(list)
    for bill in bills:
        if bill.account_id in by_source:
            held[bill.account_id].append(bill)
        else:
            yield bill
    for source, source_moves in by_source.items():
        open_bills = sorted(held.get(source, ()), key=_oldest_first)
        for move in source_moves:
            if run is not None:
                run.moves += 1
            left = move.amount
            still_open: list[SharedBill] = []
            for bill in open_bills:
                if left <= ZERO:
                    still_open.append(bill)
                    continue
                part = min(bill.owed, left)
                moved, kept = split_share(bill.share, bill.owed, part)
                left -= part
                yield SharedBill(
                    invoice_id=bill.invoice_id,
                    account_id=move.to_account_id,
                    due_date=bill.due_date,
                    currency=bill.currency,
                    owed=part,
                    band=bill.band,
                    share=moved,
                )
                if bill.owed > part:
                    still_open.append(
                        SharedBill(
                            invoice_id=bill.invoice_id,
                            account_id=bill.account_id,
                            due_date=bill.due_date,
                            currency=bill.currency,
                            owed=bill.owed - part,
                            band=bill.band,
                            share=kept,
                        )
                    )
            open_bills = still_open
            if left > ZERO and run is not None:
                run.moved_without_a_bill += left
        yield from open_bills


# ════════════════════════════════════════════════════════════════════════════
# THE POSITIONS — account × row, and row alone
# ════════════════════════════════════════════════════════════════════════════
@dataclass
class Position:
    """One account's (or one row's) receivable across the bands."""

    bands: dict[str, Decimal]
    undated: Decimal = ZERO
    total: Decimal = ZERO
    oldest_due_on: date | None = None
    bills: int = 0
    undated_bills: int = 0
    accounts: set = field(default_factory=set)
    #: Debtors with money in the OLDEST band on this position (R3's count).
    overflow_accounts: set = field(default_factory=set)

    def add(self, band: str, amount: Decimal, due_date: date | None, as_of: date) -> None:
        if band == UNDATED:
            self.undated += amount
            self.undated_bills += 1
        else:
            self.bands[band] += amount
        self.total += amount
        self.bills += 1
        if due_date is not None and due_date < as_of:
            if self.oldest_due_on is None or due_date < self.oldest_due_on:
                self.oldest_due_on = due_date


def _new_position(bands: Any) -> Position:
    return Position(bands={name: ZERO for name in bands.names()})


def wanted_targets(service_codes: Iterable[str] | None) -> set[str] | None:
    codes = {code for code in (service_codes or ()) if code}
    return codes or None


def account_service_positions(
    *,
    as_of: date,
    bands: Any,
    service_codes: Iterable[str] | None = None,
    account_ids: Any = None,
    class_order: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Every account × row with money owed at `as_of` — R2's population.

    `service_codes` narrows to those services' rows (a class row is never a
    service, so it never matches a service filter). Returns
    `{positions: {(account_id, target): Position}, population: Decimal,
    population_accounts: int, run: ShareRun, service_names: {...}}`.
    `population` is Σ owed over EVERY open bill, unfiltered by service — the
    figure the ledger comparison is struck against.
    """
    wanted = wanted_targets(service_codes)
    run = ShareRun()
    names: dict[str, str] = {}
    positions: dict[tuple[Any, Target], Position] = {}
    population = ZERO
    debtors: set = set()
    bills = open_bills_queryset(as_of=as_of, account_ids=account_ids)
    shared = iter_shared_bills(
        bills, as_of=as_of, bands=bands, class_order=class_order, run=run, service_names=names
    )
    # DEF-REP-10159 — only over the WHOLE population: narrowed to some accounts,
    # the owner a balance moved to may be outside the narrowing.
    if account_ids is None:
        shared = apply_balance_moves(shared, balance_moves(as_of=as_of), run=run)
    for bill in shared:
        population += bill.owed
        debtors.add(bill.account_id)
        for target, amount in bill.share.shares.items():
            if amount == ZERO:
                continue
            if wanted is not None and target[0] not in wanted:
                continue
            key = (bill.account_id, target)
            position = positions.get(key)
            if position is None:
                position = positions[key] = _new_position(bands)
            position.add(bill.band, amount, bill.due_date, as_of)
    return {
        "positions": positions,
        "population": population,
        "population_accounts": len(debtors),
        "run": run,
        "service_names": names,
    }


def service_positions(
    *, as_of: date, bands: Any, class_order: tuple[str, ...] | None = None
) -> dict[str, Any]:
    """One position per ROW (service or class row) — R3's population.

    `positions[target].accounts` is the set of debtors with money on that row.
    """
    run = ShareRun()
    names: dict[str, str] = {}
    positions: dict[Target, Position] = {}
    population = ZERO
    debtors: set = set()
    bills = open_bills_queryset(as_of=as_of)
    shared = apply_balance_moves(
        iter_shared_bills(
            bills, as_of=as_of, bands=bands, class_order=class_order, run=run, service_names=names
        ),
        balance_moves(as_of=as_of),
        run=run,
    )
    for bill in shared:
        population += bill.owed
        debtors.add(bill.account_id)
        for target, amount in bill.share.shares.items():
            if amount == ZERO:
                continue
            position = positions.get(target)
            if position is None:
                position = positions[target] = _new_position(bands)
            position.add(bill.band, amount, bill.due_date, as_of)
            position.accounts.add(bill.account_id)
            if bill.band == bands.overflow:
                position.overflow_accounts.add(bill.account_id)
    return {
        "positions": positions,
        "population": population,
        "population_accounts": len(debtors),
        "run": run,
        "service_names": names,
    }


# ════════════════════════════════════════════════════════════════════════════
# R5 — THE AGEING'S SERVICE FILTER, BY SHARE
# ════════════════════════════════════════════════════════════════════════════
def aging_by_service_share(
    bills: Any,
    *,
    as_of: date,
    bands: Any,
    service_codes: Iterable[str],
) -> dict[Any, Position]:
    """`aging_positions_page`'s per-account rows when a Service is chosen.

    `bills` is the ageing's own bill queryset with every OTHER criterion
    already applied (premises, search, the caller's accounts) and narrowed to
    bills carrying one of the services. Each bill contributes the chosen
    services' SHARE and nothing else — CR-184-BRC10 R5: a water-and-electric
    bill filtered to *water* used to show its whole balance under water.
    """
    wanted = wanted_targets(service_codes) or set()
    out: dict[Any, Position] = {}
    for bill in iter_shared_bills(bills, as_of=as_of, bands=bands):
        amount = sum(
            (v for t, v in bill.share.shares.items() if t[0] in wanted), ZERO
        )
        if amount <= ZERO:
            continue
        position = out.get(bill.account_id)
        if position is None:
            position = out[bill.account_id] = _new_position(bands)
        position.add(bill.band, amount, bill.due_date, as_of)
    return out


# ════════════════════════════════════════════════════════════════════════════
# R2 — THE `receivables` DATASET'S READ MODEL (one row per account × row)
# ════════════════════════════════════════════════════════════════════════════
BASIS_POSTING = "posting"

#: What the dataset may be ordered by. Every one is honoured below.
DATASET_SORTS: tuple[str, ...] = ("total", "d90_plus", "account_no")

#: band name (payments' vocabulary) → the dataset's column name.
BAND_COLUMNS: dict[str, str] = {
    "current": "current",
    "1-30": "d1_30",
    "31-60": "d31_60",
    "61-90": "d61_90",
    "90+": "d90_plus",
}


def _bands() -> Any:
    from apps.payments.outstandings import AGEING_BANDS

    return AGEING_BANDS


def _account_numbers(account_ids: list[Any]) -> dict[Any, str | None]:
    """`account_no` per account through customers' OWN queryset (B1) — in
    batches of 5,000 ids, so 40,000 debtors is eight statements, not 40,000."""
    from apps.payments import billing_seam

    queryset = billing_seam._resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        return {}
    out: dict[Any, str | None] = {}
    for start in range(0, len(account_ids), 5000):
        batch = account_ids[start : start + 5000]
        for account_id, number in queryset().filter(id__in=batch).values_list("id", "account_no"):
            out[account_id] = number
    return out


def _names(account_ids: list[Any]) -> dict[str, str | None]:
    from apps.payments.reporting import _customer_names_for

    return _customer_names_for(account_ids) if account_ids else {}


@dataclass(frozen=True)
class ReceivableRow:
    account_id: Any
    account_no: str | None
    customer_name: str | None
    service_code: str | None
    service_name: str | None
    charge_class: str | None
    bands: dict[str, Decimal]
    undated: Decimal
    total: Decimal


def _sorted_keys(
    positions: dict[tuple[Any, Target], Position],
    numbers: dict[Any, str | None],
    sort: str,
    direction: str,
) -> list[tuple[Any, Target]]:
    """The whole filtered set in a STABLE order — a row seen twice across a
    page boundary is a row never seen. Ties fall to account number, then row
    order (`target_order`), then account id."""
    keys = list(positions)
    keys.sort(key=lambda k: (numbers.get(k[0]) or "", target_order(k[1]), str(k[0])))
    descending = str(direction).lower() != "asc"
    if sort == "account_no":
        if descending:
            keys.reverse()
        return keys
    if sort == "d90_plus":
        keys.sort(key=lambda k: positions[k].bands[_bands().overflow], reverse=descending)
    else:
        keys.sort(key=lambda k: positions[k].total, reverse=descending)
    return keys


def _row(key: tuple[Any, Target], position: Position, numbers: dict, names: dict,
         service_names: dict[str, str]) -> ReceivableRow:
    account_id, (service, line_class) = key
    return ReceivableRow(
        account_id=account_id,
        account_no=numbers.get(account_id),
        customer_name=names.get(str(account_id)),
        service_code=service,
        service_name=service_names.get(service) if service else None,
        charge_class=line_class,
        bands=dict(position.bands),
        undated=position.undated,
        total=position.total,
    )


def _totals(positions: Iterable[Position], bands: Any) -> dict[str, Any]:
    items = list(positions)
    totals: dict[str, Any] = {
        name: sum((p.bands[name] for p in items), ZERO) for name in bands.names()
    }
    totals["undated"] = sum((p.undated for p in items), ZERO)
    totals["total"] = sum((p.total for p in items), ZERO)
    return totals


def receivables_dataset(
    *,
    as_of: date,
    service: str | None = None,
    page: int = 1,
    per: int | None = 50,
    sort: str = "total",
    direction: str = "desc",
) -> dict[str, Any]:
    """THE `receivables` DATASET — one row per account × service (or class row).

    `NFR-3`: the page is cut from the whole filtered set AFTER it is totalled,
    so `totals` describes the debt and not the page; `per=None` is the whole
    set (the export's door), with no ceiling (`NFR-5`).
    `population` is every open bill's owed amount at `as_of` with NO service
    filter — the figure the report foots against the ledger.
    """
    from core.pagination import filter_values

    bands = _bands()
    found = account_service_positions(
        as_of=as_of, bands=bands, service_codes=filter_values(service) if service else None
    )
    positions: dict[tuple[Any, Target], Position] = found["positions"]
    if sort not in DATASET_SORTS:
        sort = DATASET_SORTS[0]
    numbers = _account_numbers(sorted({k[0] for k in positions}, key=str))
    keys = _sorted_keys(positions, numbers, sort, direction)
    total_rows = len(keys)
    if per is None:
        page, cut = 1, keys
        pages = 1
    else:
        per = max(1, int(per))
        pages = max(1, -(-total_rows // per))
        page = min(max(1, int(page)), pages)
        cut = keys[(page - 1) * per : (page - 1) * per + per]
    names = _names(sorted({k[0] for k in cut}, key=str))
    run: ShareRun = found["run"]
    currencies = sorted(run.currencies)
    return {
        "basis": BASIS_POSTING,
        "as_of": as_of,
        "currency": currencies[0] if len(currencies) == 1 else None,
        "currencies": tuple(currencies),
        "rows": tuple(_row(k, positions[k], numbers, names, found["service_names"]) for k in cut),
        "totals": _totals(positions.values(), bands)
        | {"accounts": len({k[0] for k in positions}), "rows": total_rows},
        "population": found["population"],
        "population_accounts": found["population_accounts"],
        "filtered": bool(service),
        "sorts": DATASET_SORTS,
        "sort": sort,
        "page": page,
        "per": per,
        "total": total_rows,
        "pages": pages,
        "problems": tuple(run.problems()),
    }


def receivables_dataset_stream(
    *, as_of: date, service: str | None = None, sort: str = "total", direction: str = "desc"
) -> Iterator[ReceivableRow]:
    """EVERY ROW of the dataset, in the screen's order — the export's path.
    No page and no `per` argument, so a file cannot inherit a screen's fifty
    rows (§8.2 p91). The shares are computed over the whole set either way."""
    found = receivables_dataset(
        as_of=as_of, service=service, page=1, per=None, sort=sort, direction=direction
    )
    yield from found["rows"]


# ════════════════════════════════════════════════════════════════════════════
# R3 — RECEIVABLES OVER 90 DAYS BY SERVICE (one row per service or class row)
# ════════════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class OverdueServiceRow:
    service_code: str | None
    service_name: str | None
    charge_class: str | None
    #: Debtors with money over 90 days on THIS row.
    debtors: int
    over_90: Decimal
    total: Decimal


def over_90_by_service(*, as_of: date) -> dict[str, Any]:
    """R3 — one row per service (and per class row), over 90 days.

    Every row of every open bill is counted, so Σ `total` over the rows is the
    whole receivable at `as_of` EXACTLY (= `population`); `over_90` is the
    oldest band's part of it. `debtors_over_90` is DISTINCT accounts across
    rows — one customer owing water and sewer over 90 days is one debtor, so
    it is not the sum of the rows' counts and is never served as one.
    """
    bands = _bands()
    found = service_positions(as_of=as_of, bands=bands)
    positions: dict[Target, Position] = found["positions"]
    names: dict[str, str] = found["service_names"]
    rows = [
        OverdueServiceRow(
            service_code=target[0],
            service_name=names.get(target[0]) if target[0] else None,
            charge_class=target[1],
            debtors=len(position.overflow_accounts),
            over_90=position.bands[bands.overflow],
            total=position.total,
        )
        for target, position in sorted(positions.items(), key=lambda item: target_order(item[0]))
    ]
    distinct_over_90: set = set()
    for position in positions.values():
        distinct_over_90 |= position.overflow_accounts
    run: ShareRun = found["run"]
    currencies = sorted(run.currencies)
    return {
        "basis": BASIS_POSTING,
        "as_of": as_of,
        "currency": currencies[0] if len(currencies) == 1 else None,
        "currencies": tuple(currencies),
        "rows": tuple(rows),
        "over_90": sum((row.over_90 for row in rows), ZERO),
        "total": sum((row.total for row in rows), ZERO),
        "debtors_over_90": len(distinct_over_90),
        "population": found["population"],
        "population_accounts": found["population_accounts"],
        "problems": tuple(run.problems()),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-184-BRC10 (12-governance/change-requests/CR-184-BRC10-receivables-by-service.md) · decision log 2026-10-14 (C1 → a)
# generated: 2026-10-14 by lane ARSVC
# checklist: A✔ B=n/a C✔ D=n/a(a read model; its routes are the reports') E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — see 06-backend/tests/test_cr184_receivables_by_service.py's module docstring
# exceptions: (1) OQ-128 is OPEN — a part-paid bill with a minimum/adjustment/discount/deposit line is shared by plain proportion and COUNTED, never placed in a class · (2) money with no stored class breakdown is walked under the tenant's CURRENT class order · (3) the tenant-defined class receives no line (the ledger publishes no membership)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

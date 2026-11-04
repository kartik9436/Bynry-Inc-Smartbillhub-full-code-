# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · the `payments` DATASET QUERY (brief §7.1 — "datasets
#           are code, definitions are data"; §7.5 — the read path; §08 — "every
#           arrow into the database passes through a reviewed dataset").
#           Drawings read as IMAGES (B14 rule 42): p051–p052 (R1 Payments,
#           R2 Deposit Batches), p052–p053 (R3 Payment Exceptions), p053 (R9 AR
#           Ageing, R10 Debtor List), p054 (R11 Cut-Off List, R12 Collections
#           Activity), p055 (R14 Closed Account Balances), p057 (R19 Cash
#           Reconciliation), p058 (R20 Deposits), p083–p086 (§7.2/§7.2.1/
#           §7.2.2 the dimension model + additivity), p087 (§7.5 read path +
#           §7.6 scale), p090–p092 (§08 architecture).
# Story:    US-REP-007 (Payments by method) — R1's four group-bys are its
#           drawing's own warning, *"Group by switches this between method,
#           teller, purpose and day. Four reports, one row."*
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `current_tenant_id()` on
#           every queryset, RLS FORCE) · hard rule 2 (money 4 dp, percentages
#           6, DISPLAY 2; Decimal end to end, never float and never cents) ·
#           **hard rule 4 — NO UPDATE OR DELETE ON `payments`; THIS FILE WRITES
#           NOTHING AT ALL** · hard rule 5 (only the posting service writes
#           journal lines — nothing here goes near them) · hard rule 7 (a money
#           ACTION writes `audit_log`; a READ is not an action and writes none)
#           · NFR-3 (universal server pagination — `limit`/`offset`/`sort`
#           applied IN SQL) · NFR-5 (no hard caps anywhere) · BR-REP-001 (a
#           money report names its basis — its CLEARING date for this dataset
#           is SUPERSEDED by the PO ruling of 2026-10-21, decision log "Two
#           CR-186 follow-up rulings" item 2) · BR-REP-002 (read models only) ·
#           BR-REP-014 (collection framings count BILL-purpose payments only) ·
#           BR-REP-024 (never a 0 where a figure could not be computed) ·
#           BR-PAY-012 (purpose) · BR-PAY-021 (both dates) · BR-TEN-043 (the
#           business date is an argument, never a clock)
# Tests:    06-backend/tests/test_rep_payments_dataset.py
#           10-scripts/ds_payments_dataset_cost.py (the PostgreSQL measurement —
#           hard-won law 14: the suite runs on in-memory SQLite)
# Impacts:  apps/reports/report_seams.py (the intended cross-module caller) ·
#           apps/reports/datasets.py (`PAYMENTS.paginates`, `PAYMENTS.grain`) ·
#           apps/payments/reporting.py (`payments_by_method` is the AGGREGATE
#           and stays; this is the FACT underneath it)
# ───────────────────────────────────────────────────────
"""THE `payments` DATASET — **one row per PAYMENT**, paged and sorted in SQL.

🔒 SENSITIVE PATH · HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is a payments read on the money
path and it decides what the Receivables reports SAY the utility took. Row in
`12-governance/09-human-review-ledger.md`, written before the review rather
than after it.

═══════════════════════════════════════════════════════════════════════════════
⚠ THE DECLARED GRAIN WAS WRONG, AND IT WAS WRONG IN A WAY THAT DROPS MONEY
═══════════════════════════════════════════════════════════════════════════════
`apps/reports/datasets.py` declared this dataset's grain as **"one payment
allocation"**. An allocation is the payment→invoice row in `allocations`, and
`apps/payments/services.py` creates **none of them** for a payment whose
purpose does not allocate — `_allocate_and_post` branches on
`if not linkage.allocates:` and a **deposit**, a **prepay** and a **plan-down**
take that branch (`PAYMENT_PURPOSES` = bill · deposit · plan_down · prepay).

So a dataset at allocation grain **silently omits every payment that is not
against a bill**, and R1's own drawing tiles — *Taken today $4,118.55 ·
Payments 61* — are a count and a sum of PAYMENTS. A deposit taken at the
counter is money in the drawer; a report that leaves it out does not read as
wrong, it reads as a smaller day. That is the invisible-wrong-answer §7.2 is
about, filed as `DEF-REP-6853`.

**The grain here is ONE PAYMENT.** Allocation is a child fact with its own
grain and its own reports, and it is not folded in: joining `payments` to
`allocations` fans a two-bill payment into two rows and `Σ amount` then
double-counts the payment.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS WHEN `reporting.payments_by_method` ALREADY SERVES R1
═══════════════════════════════════════════════════════════════════════════════
Two reasons, and both are measured rather than argued.

**① IT IS AN AGGREGATE, AND AN AGGREGATE CANNOT BE UN-AGGREGATED.** R1's row is
a GROUP (method × teller) and §7.2 tier B wants *"drill through — a subtotal
opens the rows behind it"*. There were no rows behind it. This is the missing
fact, exactly as `journal_lines` was the missing fact under nine ledger
aggregates.

**② IT FOLDS EVERY MATCHED PAYMENT IN PYTHON.** `payments_by_method` runs
`for payment in cleared:` over the whole window and accumulates counts, sums,
per-purpose buckets and a `PaymentDetailRow` for every row. There is no
`LIMIT`, no `OFFSET`, no SQL aggregate and no sort a caller can state — an
`NFR-3` breach in a report that is LIVE today, and one `DEF-PAY-4221` does not
name because that defect names `/outstandings`, `/cheques` and the bank-rec
batch list. Filed as `DEF-REP-6854`. **This file does not edit that
function** — it is another lane's surface and law 11 is why — it provides the
paged fact the viewer should read instead.

**③ THE DRAWING ASKS FOR FOUR GROUPINGS AND THE CODE HAS ONE.** p052, verbatim:
*"Group by switches this between method, teller, purpose and day. **Four
reports, one row.**"* `payments_by_method` groups by method. `teller` is a
DECLARED COLUMN of this dataset with no source anywhere in that function.
`payment_groups()` below does all four, in SQL, and `teller` reads
`payments.counter_session_id` → `counter_sessions.owner`.

═══════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND `per=None` IS THE EXPORT'S DOOR
═══════════════════════════════════════════════════════════════════════════════
Brief §7.5 (p087): *"Sync — viewing — page 1 — returns rows with limit/offset/
sort applied in SQL. Never the whole result."*

`per` cuts the page with `[offset:offset+limit]` on a QuerySet — one
`LIMIT/OFFSET` — and `sort` is `order_by(*order_terms(...))`. **Nothing is
sorted or sliced in Python anywhere in this file.**

⚠ **THE EXPORT IS A SEPARATE FUNCTION AND TAKES NO `page` AND NO `per`.**
`payments_dataset_stream()` is a generator with no page argument to pass, so an
export cannot inherit a screen's fifty rows. That is not tidiness: when the
billing register started paging, its export silently inherited the screen's page
and produced a valid-looking file of 50 rows from a 38,000-row report. A flag
would have had the same bug; a missing parameter cannot.

`NFR-5` forbids a ceiling on that branch and there is none — no maximum row
count and no per-tenant cap, here or anywhere below.

═══════════════════════════════════════════════════════════════════════════════
TOTALS ARE A SQL AGGREGATE OVER THE WHOLE FILTERED SET, NEVER OVER THE PAGE
═══════════════════════════════════════════════════════════════════════════════
That is what makes the KPI tiles foot to the report whether a page is cut or
not — the premise `/outstandings`'s withdrawn docstring got backwards, and the
one `billing_register` and `journal_lines` already build on.

`bill_purpose_total` is published SEPARATELY from `total`, so BR-REP-014 is
structural rather than remembered: a caller computing a collection percentage
reaches for the bill-purpose figure and **cannot reach a total with deposits
folded into it**. `reporting.payments_by_method` already splits them for the
same reason and this keeps the two surfaces saying one thing.

═══════════════════════════════════════════════════════════════════════════════
ADDITIVITY (brief §7.2.2, read as an image on p085)
═══════════════════════════════════════════════════════════════════════════════
* `amount` — **fully additive.** A payment amount sums freely, in any
  direction. §7.2.2 names it first: *"Invoiced amount · payment amount · tax
  collected — fully additive — none, sum freely."*
* `payments` (the count) — **fully additive.**
* `share_pct` — **non-additive.** It is recomputed from its components, never
  averaged. A page's shares do not total 100% and are not meant to; R9's own
  drawing says so of its own shares (*"Shares are rounded and need not total
  100%"*).

⚠ **NO SEMI-ADDITIVE MEASURE IS SERVED FROM THIS FILE, AND THAT IS THE POINT.**
The semi-additive measures the dataset declares — `total`, `current`, `d1_30`,
`d31_60`, `d61_90`, `d90_plus`, `deposits_held`, `accounts_active` — are
BALANCES AS AT A DATE, and a balance is not a property of a payment. They are
not computed here and not served null-with-an-excuse either: they belong to a
different grain, which is what `PROBLEMS` says by name. Papering one of them
onto a payment row to make a footer appear is the canonical wrong answer
§7.2.2 opens with.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** Hard rule 4 makes `payments` append-only with exactly
three correctable columns through exactly one endpoint, and that endpoint is
`apps/payments/amendments.py`, not this. There is no INSERT, UPDATE, DELETE or
`save()` below, and nothing here touches `journal_lines` (hard rule 5).

**It never falls back to zero.** BR-REP-024: a figure that cannot be computed
is `None` beside a named reason, in `problems`. A window with no payments has
no currency and a total of `0.00` — which is a real answer and a different
thing from *not derivable*.

**It states no clock.** `start`/`end`/`as_of` are arguments (BR-TEN-043): the
figure a clerk sees at 23:58 and the figure a job takes at 00:02 must be
explainable, and a function that read the system date could not be asked for
yesterday's.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, Q, Sum, Value
from django.db.models.functions import (
    Coalesce,
    TruncDate,
    TruncDay,
    TruncMonth,
    TruncQuarter,
    TruncYear,
)

from apps.payments import balance_rule, billing_seam, counter_session_models, models
from core.pagination import order_terms
from core.tenancy import current_tenant_id

ZERO = Decimal("0")

#: BR-REP-001 — the basis is named on every answer. Every money figure here is
#: dated by `payments.posted_at`, the POSTING basis.
#:
#: ⚠ **IT WAS `cleared_at` — `"clearing"` — UNTIL 2026-10-21 (`DEF-PAY-10321`).**
#: The drawings' eyebrow reads *"Clearing date"*, drawn when *cleared* meant
#: *the money arrived*. `CR-186-BRC10` redefined `cleared` as *its deposit batch
#: was reconciled with the bank*, days later, and the PO, shown *"a card payment
#: taken 14 Oct and reconciled 16 Oct shows in the 16 Oct report"*, chose
#: *"Posting date: the 14 Oct payment appears in the 14 Oct report, the day the
#: money was taken and applied."* `cleared_at` still travels on every row
#: (BR-PAY-021) and is null until the batch is reconciled; the window, the sort
#: default and the time groupings never read it.
BASIS = "posting"

#: The money precision hard rule 2 declares. Stored 4 dp (existing 18,6 columns
#: stay lawful containers), DISPLAYED 2 — and this module displays nothing, so
#: every figure leaves as an exact `Decimal` and the renderer rounds.
_MONEY = DecimalField(max_digits=18, decimal_places=6)

#: What a caller may order by. Five, because five are what the drawings put a
#: sort on, and a sort this query does not honour would be a live caret over a
#: dead control — hard-won law 2's mirror, which `DEF-CWP-3925` is about.
#:
#: ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN.** A page is a window over an ORDER;
#: if that order is not total, two rows that compare equal may swap between
#: page 1 and page 2 and a clerk sees one row twice and another never. `id`
#: closes every tuple — `core.pagination.order_terms` refuses to add a
#: tiebreak silently, precisely so this stays the caller's stated decision.
PAYMENT_SORTS: tuple[str, ...] = (
    "cleared_on",
    "posted_on",
    "amount",
    "account_no",
    "method_name",
)
#: The POSTING date since 2026-10-21 (`DEF-PAY-10321`) — the basis the window
#: reads. A posted payment has no `cleared_at` until its batch is reconciled, so
#: the tie-breaks below read `posted_at` too.
PAYMENT_DEFAULT_SORT = "posted_on"
PAYMENT_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "cleared_on": ("cleared_at", "posted_at", "id"),
    "posted_on": ("posted_at", "id"),
    "amount": ("amount", "posted_at", "id"),
    # ⚠ The ACCOUNT NUMBER, never the account id — B14 rule 31, and a uuid7
    # sorts by mint time, which is not an order any clerk asked for.
    "account_no": ("account__account_no", "posted_at", "id"),
    "method_name": ("method__name", "posted_at", "id"),
}

#: The four groupings R1's drawing declares, and the column each groups on.
#: *"Group by switches this between method, teller, purpose and day. Four
#: reports, one row."* (p052, read as an image.)
GROUP_METHOD = "method"
GROUP_TELLER = "teller"
GROUP_PURPOSE = "purpose"
GROUP_DAY = "day"
PAYMENT_GROUPS: tuple[str, ...] = (GROUP_METHOD, GROUP_TELLER, GROUP_PURPOSE, GROUP_DAY)

#: The filters this dataset accepts. Named here so `apps/reports/datasets.py`
#: and this query cannot drift — a filter the dataset declares and the query
#: drops shows the WHOLE set under a chip that says otherwise, which is the
#: defect `PAYMENTS.filters` already carries a comment about.
PAYMENT_FILTERS: tuple[str, ...] = (
    "from",
    "to",
    "purpose",
    "method",
    "teller",
    "status",
)


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_BALANCES_ARE_NOT_A_PAYMENT_FACT = {
    "code": "a_balance_as_at_a_date_is_not_a_property_of_a_payment",
    "br_ref": "brief §7.2 · §7.2.2",
    "detail": (
        "The dataset declares the ageing columns — current, d1_30, d31_60, d61_90, d90_plus, "
        "total, deposits_held, accounts_active, days_late, dso_days — and this grain cannot "
        "carry them. Each is a BALANCE AS AT A DATE whose grain is one ACCOUNT, not one "
        "payment, and each is semi-additive or non-additive: summing one down a list of "
        "payments is the wrong answer §7.2.2 opens with. "
        "`apps.payments.reporting.ar_aging` and `apps.payments.outstandings.outstandings` "
        "compute them at the grain that owns them; this query serves the payment and leaves "
        "those columns absent rather than serving a plausible number."
    ),
    "wanted_reads": (
        "apps.payments.reporting.ar_aging",
        "apps.payments.outstandings.outstandings",
    ),
}

GAP_TELLER_IS_UNKNOWN_BEFORE_TILLS = {
    "code": "a_payment_banked_before_tills_names_no_teller",
    "br_ref": "payments/0045 · OQ-PAY-12621",
    "detail": (
        "`payments.counter_session_id` is NULL on money that arrived over a wire — ACH, card, "
        "wire, lockbox name the day's SYSTEM till, which has no owner — and on every payment "
        "taken before tills existed. The absence IS the fact and it is served as a null "
        "teller with this reason, never as a teller named 'Unknown' and never as an empty "
        "string, which would read as a person whose name we failed to fetch."
    ),
    "wanted_reads": (),
}


@dataclass(frozen=True)
class PaymentFactRow:
    """One payment, in the dataset's own declared column names.

    ⚠ **BOTH DATES TRAVEL, ALWAYS (BR-PAY-021).** A payment posted on 30 July
    and cleared on 2 August is July's on the posting basis and August's on the
    clearing basis, and a row carrying one of them cannot be re-based by a
    caller. `BASIS` says which one the FILTER used; these two say what the
    payment actually did.

    ⚠ **`confirmation`, `memo` AND `method_name` ARE THE THREE CORRECTABLE
    COLUMNS (hard rule 4, as narrowed by `OQ-1322`).** They are served as they
    read NOW. The value a correction replaced lives only in `audit_log`, which
    is pruned on a retention schedule with no row type exempt (`OQ-1340`,
    closed 2026-09-23) — **so nothing here, and nothing built on this, may
    describe this row as a permanent record of a previous value.** It is not
    described that way and no caveat is rendered either: B14 rule 33 puts
    RATIONALE at zero words on screen, so the honest build is silence, and the
    screen simply never claims permanence.

    ⚠ **`teller` IS A NAME OR IT IS `None` WITH A REASON.** See
    `GAP_TELLER_IS_UNKNOWN_BEFORE_TILLS`.
    """

    payment_id: str
    payment_no: str | None
    posted_on: date
    cleared_on: date | None
    account_id: str
    account_no: str | None
    customer_name: str | None
    method_id: str | None
    method_name: str | None
    purpose: str
    status: str
    type: str
    teller_id: str | None
    teller: str | None
    confirmation: str | None
    memo: str | None
    amount: Decimal
    currency: str


@dataclass(frozen=True)
class PaymentGroupRow:
    """One GROUP of payments — R1's drawn row, at whichever of the four keys.

    `share_pct` is NOT stored and NOT summed: it is recomputed from this group's
    amount over the whole filtered total, every time, because it is
    non-additive (§7.2.2). It is `None` — never `0` — when the filtered total is
    zero, since a share of nothing is not a number (BR-REP-024).
    """

    key: str | None
    label: str | None
    count: int
    amount: Decimal
    share_pct: Decimal | None


def _tenant_id() -> Any:
    return current_tenant_id()


def _base(
    *,
    start: date | None,
    end: date | None,
    purpose: str | None,
    method_id: Any,
    teller_id: Any,
    status: str | None,
) -> Any:
    """The filtered set, every criterion a `WHERE` — hard rule 1 first.

    ⚠ **THE TENANT FILTER IS THE FIRST CLAUSE AND IS NOT OPTIONAL.** RLS FORCE
    is on and would refuse a cross-tenant row anyway, but a queryset that
    relies on the database to be the only guard is a queryset that is wrong the
    day somebody runs it as an owner. Belt and policy, the shape every read in
    this module already uses.

    The window is on `posted_at` because `BASIS` is the posting date (PO
    ruling 2026-10-21, `DEF-PAY-10321`), and the set is the balance's counted
    one — `posted`, `cleared` and the NEGATIVE `reversed` row a bounce writes,
    so a bounced cheque nets on its return day exactly as it did on the
    clearing basis (both legs carried a clearing date then). `cancelled`,
    `failed` and `processing` are never money and are outside every window;
    the `status` filter narrows WITHIN the counted set.
    """
    rows = models.Payment.objects.filter(
        tenant_id=_tenant_id(),
        status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES,
    )
    if start is not None:
        rows = rows.filter(posted_at__date__gte=start)
    if end is not None:
        rows = rows.filter(posted_at__date__lte=end)
    if purpose:
        rows = rows.filter(purpose=str(purpose))
    if method_id is not None:
        rows = rows.filter(method_id=method_id)
    if teller_id is not None:
        rows = rows.filter(counter_session_id=teller_id)
    if status:
        rows = rows.filter(status=str(status))
    return rows


def _sum(expression: str, *, only: Q | None = None) -> Any:
    """Σ as a Decimal, with an empty set reading `0` rather than SQL NULL.

    `Coalesce(..., Value(ZERO))` rather than `or ZERO` in Python: an aggregate
    over no rows returns NULL, and *"no payments"* and *"payments that net to
    nothing"* are both zero money taken. What is NOT zero-filled is a figure
    that could not be DERIVED; that is `None` beside a named reason, in
    `problems` (BR-REP-024).
    """
    return Coalesce(Sum(expression, filter=only, output_field=_MONEY), Value(ZERO, output_field=_MONEY))


def _one_currency(rows: Any) -> tuple[str | None, dict[str, Any] | None]:
    """The single currency of the filtered set, or no figure at all (DEF-081).

    ⚠ **ASKED BEFORE ANY Σ, NEVER AFTER.** Adding 100 USD to 100 CAD produces
    200 of nothing, and the resulting tile is not visibly wrong — it is a
    plausible number in the wrong unit, which is hard rule 2's whole concern
    and `DEF-081`'s recorded lesson. A mixed set gets `None` and a named
    reason; it does not get a total.
    """
    found = sorted({code for code in rows.values_list("currency", flat=True).distinct() if code})
    if len(found) <= 1:
        return (found[0] if found else None), None
    return None, {
        "code": "the_set_holds_more_than_one_currency",
        "br_ref": "CLAUDE.md hard rule 2 · DEF-081",
        "detail": (
            "These payments are denominated in "
            + ", ".join(found)
            + ". A money total across two currencies is a number in no currency at all, so no "
            "total is published. Filter to one currency to get a figure."
        ),
        "wanted_reads": (),
    }


def _teller_names(session_ids: list[Any]) -> dict[str, str | None]:
    """A PAGE's teller names — ONE query, never one per row.

    `payments.counter_session_id` is a plain `UUIDField` and not an FK (its own
    column docstring records why), so there is no `select_related` to reach the
    owner through. It is a bounded batched read over `counter_sessions`, which
    is a PAYMENTS table — no module boundary is crossed and B1 is not bent.

    ⚠ **BOUNDED BY THE PAGE, NOT BY THE TENANT.** `reporting.payments_by_method`
    resolved one contact name per row until `P2.21` and at 40,000 rows that was
    40,000 round trips for one column; the same trap is one `IN (...)` away
    here and this is the shape that avoids it.
    """
    if not session_ids:
        return {}
    rows = counter_session_models.CounterSession.objects.filter(
        tenant_id=_tenant_id(), id__in=session_ids
    ).values_list("id", "owner__full_name")
    return {str(session_id): name for session_id, name in rows}


def _customer_names(account_ids: list[Any]) -> dict[str, str | None]:
    """A PAGE's contact names, through customers' OWN batched read (B1).

    No customers model is imported and no ORM of theirs is walked — the seam
    resolves `primary_contact_names_for`, which has existed since `DEF-2723`
    closed exactly the one-query-per-row defect on the accounts list.
    """
    if not account_ids:
        return {}
    batched = billing_seam._resolve("customers", "primary_contact_names_for")
    if batched is None:  # pragma: no cover — customers publishes it
        return {}
    return {str(key): value for key, value in batched(account_ids).items()}


def _shape(
    payment: Any,
    teller_names: dict[str, str | None],
    customer_names: dict[str, str | None],
) -> PaymentFactRow:
    """One stored payment, in the dataset's declared column names."""
    session_id = str(payment.counter_session_id) if payment.counter_session_id else None
    account_id = str(payment.account_id)
    method = payment.method if payment.method_id else None
    return PaymentFactRow(
        payment_id=str(payment.id),
        # ⚠ The PMT- series number, never the uuid — B14 rule 31: no database
        # id is ever the visible value of a field. It is nullable by design
        # (a legacy import path that cannot reach the series), so the absence
        # travels as an absence and the renderer decides what to draw.
        payment_no=payment.payment_no,
        posted_on=payment.posted_at.date() if payment.posted_at else None,
        cleared_on=payment.cleared_at.date() if payment.cleared_at else None,
        account_id=account_id,
        account_no=getattr(payment.account, "account_no", None),
        customer_name=customer_names.get(account_id),
        method_id=str(payment.method_id) if payment.method_id else None,
        method_name=getattr(method, "name", None),
        purpose=payment.purpose,
        status=payment.status,
        type=payment.type,
        teller_id=session_id,
        teller=teller_names.get(session_id) if session_id else None,
        confirmation=payment.confirmation,
        memo=payment.memo,
        amount=payment.amount,
        currency=payment.currency,
    )


#: ── THE GROUP LEVELS THIS QUERY CAN CUT **IN SQL** (`P2.17`) ────────────────
#:
#: ⚠ **A GROUP LEVEL IS A `GROUP BY` OR IT IS NOTHING.** `apps/reports/slicers.py`
#: can add the served rows up in Python, and the rows it is given are **ONE
#: PAGE** — measured on this branch, 2026-09-27, the billing register grouped by
#: status served subtotals footing to `$14,185.80` under a footer of `$30,750.07`
#: (`DEF-REP-6875`). A level is offered here only when it is a database
#: expression over the SAME filtered queryset `totals` is struck over, so a
#: group's Σ and the footer's Σ cannot disagree.
#:
#: ⚠ **THE TIME LEVELS ARE TRUNCATIONS OF `posted_at`, BECAUSE `BASIS` IS THE
#: POSTING DATE** (since 2026-10-21, `DEF-PAY-10321`; they truncated `cleared_at`
#: before). The grouping must read the same date as the window, or a report
#: would be filtered on one date and subtotalled on another — two months on one
#: screen, both labelled correctly, neither footing.
#:
#: ⚠ **`method` GROUPS BY THE METHOD's `id`, NOT ITS NAME.** Two tenants may name
#: a method the same thing and one tenant may rename one; a group keyed on a
#: label silently merges or splits when somebody edits Settings. The LABEL is
#: resolved for display from the key, exactly as `_shape` already does it.
GROUP_LEVELS: dict[str, Any] = {
    "year": TruncYear("posted_at"),
    "quarter": TruncQuarter("posted_at"),
    "accounting_period": TruncMonth("posted_at"),
    "day": TruncDay("posted_at"),
}

#: ⚠ **`purpose`, `status` AND `method` ARE NOT HERE, AND THEY WERE, FOR AN HOUR.**
#: All three are one `F()` away and all three would have been **unreachable dead
#: controls**: `apps/reports/datasets.py::PAYMENTS` declares its dimensions as
#: `AR_AGEING_DIMENSIONS` — time, consumer class, service, account status,
#: customer type, premises, unit, route/cycle, area, rate schedule, payment plan,
#: collections state, age bucket — and `purpose`, a payment's `status` and a tender
#: are none of them. `slicers.validate_grouping` refuses a level that is not a
#: declared dimension or a level of one, so the grouping was dropped before this
#: query was reached. Measured on this branch, 2026-09-27: `group_by=purpose`
#: returned 50 ungrouped rows and `unavailable` carrying `grouping_not_served`.
#:
#: That is hard-won law 2's mirror one layer down — a capability offered by a read
#: model that nothing upstream can ask for. **Adding a dimension to
#: `datasets.PAYMENTS` is what makes a tender groupable, and this table moves in
#: the same commit as that declaration or not at all.** A payment's `status` is
#: NOT the `account_status` dimension and must never be mapped onto it: one says
#: whether the money cleared and the other whether the account is active.

#: The measures a group row carries. `amount` is FULLY additive (§7.2.2) and
#: `payments` is a count.
#:
#: ⚠ **NOTHING SEMI-ADDITIVE AND NOTHING RECOMPUTED IS HERE, AND THE ABSENCES
#: ARE THE RULE BEING OBEYED.** `total`, `current`, `d1_30`…`d90_plus` and
#: `deposits_held` are one ACCOUNT's position as at a date — a different grain,
#: which this query serves no column for at all; `dso_days`, `collection_rate`,
#: `share_pct` and `days_late` are recomputed from their components and the
#: average of four route DSOs is not the utility's DSO. A group row that carried
#: any of them would be a number with no meaning under a correct-looking label.
GROUP_MEASURES: tuple[str, ...] = ("amount", "payments")


def _grouped(rows: Any, levels: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    """One SQL `GROUP BY` **per prefix** of the levels, over the whole filtered set.

    Three levels means three `SELECT`s and not one: a single `GROUP BY a, b, c`
    returns only the LEAF cells, and deriving the coarser subtotals from them is
    a Python roll-up wearing a SQL hat. Each prefix is its own aggregate over the
    same queryset, so every subtotal at every level is struck by the database
    over the rows it actually covers.
    """
    out: list[dict[str, Any]] = []
    for depth in range(1, len(levels) + 1):
        prefix = levels[:depth]
        aliases = {f"_g{i}": GROUP_LEVELS[name] for i, name in enumerate(prefix)}
        cells = (
            rows.annotate(**aliases)
            .values(*aliases)
            .annotate(_amount=_sum("amount"), _payments=Count("id"))
            .order_by(*aliases)
        )
        for cell in cells:
            out.append(
                {
                    "level": depth - 1,
                    "dimension": prefix[-1],
                    "values": tuple(cell[f"_g{i}"] for i in range(depth)),
                    "rows": int(cell["_payments"]),
                    "measures": {
                        "amount": cell["_amount"],
                        "payments": int(cell["_payments"]),
                    },
                }
            )
    return tuple(out)


def payments_dataset(
    *,
    start: date | None = None,
    end: date | None = None,
    purpose: str | None = None,
    method_id: Any = None,
    teller_id: Any = None,
    status: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
    group_by: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """THE dataset query. One row per payment, paged and sorted in SQL.

    `per=None` is the whole filtered set. `per` is an integer page size; the
    CALLER clamps it (`core.pagination.clamp_page_size`) and this function does
    not invent one, because a cap invented here is a cap nobody can see
    (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `payments_dataset_stream()` INSTEAD** — it takes no
    `page` and no `per`, so an export has no argument through which to inherit a
    screen's fifty rows. `per=None` here would give the same rows and would
    build the whole list in memory first; the generator does not.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER
    THE PAGE**, so the KPI tiles foot to the report whether a page is cut or
    not.
    """
    rows = _base(
        start=start,
        end=end,
        purpose=purpose,
        method_id=method_id,
        teller_id=teller_id,
        status=status,
    )

    currency, currency_problem = _one_currency(rows)

    # ── the totals: ONE aggregate call, so every figure is struck over the
    # same snapshot of the same rows. Two round trips could see two different
    # days if a payment cleared between them, and *"the total and the
    # bill-purpose total were read a millisecond apart"* is not a defect
    # anybody would ever diagnose from a report that does not foot.
    # ⚠ **THE ALIASES DO NOT SHADOW THE FIELD.** `aggregate(amount=Sum("amount"))`
    # makes Django resolve the inner `amount` against the alias it is building
    # and raise *"Cannot compute Sum('amount'): 'amount' is an aggregate"*. It
    # is a real refusal rather than a silent wrong number, but it only shows
    # when the function is actually CALLED — which on this path was the
    # PostgreSQL measurement and not the SQLite suite.
    aggregated = rows.aggregate(
        amount_sum=_sum("amount"),
        # BR-REP-014, STRUCTURAL rather than remembered: a caller computing a
        # collection percentage reaches for this and cannot reach a total with
        # deposits folded into it.
        bill_amount_sum=_sum("amount", only=Q(purpose=models.PURPOSE_BILL)),
        payment_count=Count("id"),
        bill_payment_count=Count("id", filter=Q(purpose=models.PURPOSE_BILL)),
    )
    total_payments = int(aggregated["payment_count"])

    problems: list[dict[str, Any]] = [dict(GAP_BALANCES_ARE_NOT_A_PAYMENT_FACT)]
    if currency_problem is not None:
        problems.append(currency_problem)

    # ⚠ The `payments_posted_in_this_window_cleared_outside_it` problem lived
    # here until 2026-10-21 (DEF-PAY-10321). On the posting basis a counted
    # payment is in the window it was posted in, so it has nothing to count.

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(
            sort,
            direction,
            columns=PAYMENT_SORT_COLUMNS,
            default=PAYMENT_DEFAULT_SORT,
        )
    ).select_related("method", "account")

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_payments // size))
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    shaped = _shape_all(materialised)
    if any(row.teller_id is None for row in shaped):
        problems.append(dict(GAP_TELLER_IS_UNKNOWN_BEFORE_TILLS))

    # ── the group rows, cut in SQL over the WHOLE filtered set (`P2.17`) ─────
    wanted = tuple(str(level) for level in (group_by or ()))
    servable = tuple(level for level in wanted if level in GROUP_LEVELS)
    refused = tuple(level for level in wanted if level not in GROUP_LEVELS)
    groups = _grouped(rows, servable) if servable else ()

    return {
        "basis": BASIS,
        "grain": "one payment",
        "currency": currency,
        "rows": tuple(shaped),
        # `()` when nothing was asked for, so an ungrouped answer is byte-for-byte
        # what it was before this key existed.
        "groups": groups,
        "grouped_by": servable,
        "groups_not_served": refused,
        "group_measures": GROUP_MEASURES,
        "totals": {
            # Fully additive (§7.2.2) — sum freely, in any direction.
            "amount": None if currency_problem else aggregated["amount_sum"],
            "bill_purpose_amount": None if currency_problem else aggregated["bill_amount_sum"],
            "payments": total_payments,
            "bill_purpose_payments": int(aggregated["bill_payment_count"]),
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_payments,
        "problems": tuple(problems),
    }


def _shape_all(materialised: list[Any]) -> list[PaymentFactRow]:
    """Two bounded batched label reads, then the rows. Never one query per row."""
    session_ids = [p.counter_session_id for p in materialised if p.counter_session_id]
    account_ids = [p.account_id for p in materialised if p.account_id]
    teller_names = _teller_names(session_ids)
    customer_names = _customer_names(account_ids)
    return [_shape(p, teller_names, customer_names) for p in materialised]


#: How many rows one round trip of the export fetches. A BUFFER, not a cap
#: (`NFR-5`): the generator goes on until the cursor is exhausted and there is
#: no number any row can be beyond. It exists so a 40,000-row file does not
#: become 40,000 dicts in memory at once.
STREAM_CHUNK = 2_000


def payments_dataset_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    purpose: str | None = None,
    method_id: Any = None,
    teller_id: Any = None,
    status: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> Iterator[PaymentFactRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **THE ABSENCE OF THOSE TWO PARAMETERS IS THE WHOLE DESIGN.** An export
    cannot inherit a screen's fifty rows because there is no argument through
    which to pass them. When the billing register started paging, its export
    inherited the page and shipped a valid-looking file of 50 rows from a
    38,000-row report — a flag would have had the same bug; a missing
    parameter cannot.

    ⚠ **`NFR-5` — NO CAP, ANYWHERE ON THIS PATH.** A 100,000-row export cap was
    deleted from this product this week for breaching exactly that rule, and
    `STREAM_CHUNK` is a fetch buffer rather than a ceiling: the loop runs until
    the cursor is exhausted.

    The order is applied IN SQL, the same `order_terms` the page uses, so the
    file and the screen sort identically. Labels are resolved per chunk —
    bounded, batched, never one query per row.
    """
    rows = _base(
        start=start,
        end=end,
        purpose=purpose,
        method_id=method_id,
        teller_id=teller_id,
        status=status,
    ).order_by(
        *order_terms(
            sort,
            direction,
            columns=PAYMENT_SORT_COLUMNS,
            default=PAYMENT_DEFAULT_SORT,
        )
    ).select_related("method", "account")

    buffer: list[Any] = []
    for payment in rows.iterator(chunk_size=STREAM_CHUNK):
        buffer.append(payment)
        if len(buffer) >= STREAM_CHUNK:
            yield from _shape_all(buffer)
            buffer = []
    if buffer:
        yield from _shape_all(buffer)


def payment_groups(
    *,
    group_by: str = GROUP_METHOD,
    start: date | None = None,
    end: date | None = None,
    purpose: str | None = None,
    method_id: Any = None,
    teller_id: Any = None,
    status: str | None = None,
) -> dict[str, Any]:
    """R1's drawn row, at whichever of the four keys — **grouped in SQL**.

    p052's warning, verbatim and read as an image: *"Group by switches this
    between method, teller, purpose and day. **Four reports, one row.**"*

    ⚠ **`share_pct` IS RECOMPUTED, NEVER AVERAGED AND NEVER SUMMED.** §7.2.2
    puts *"% share"* among the NON-additive measures: it is derived from this
    group's amount over the filtered total, here, on every call. A stored or
    folded share is the second trap that page names.

    ⚠ **IT IS `None`, NOT `0`, WHEN THE TOTAL IS ZERO** (BR-REP-024). A share
    of nothing is not a number, and `0%` on every row of an empty report reads
    as a real measurement.
    """
    if group_by not in PAYMENT_GROUPS:
        raise ValueError(
            f"group_by must be one of {', '.join(PAYMENT_GROUPS)} — the four R1 declares "
            f"(brief p052); got {group_by!r}"
        )

    rows = _base(
        start=start,
        end=end,
        purpose=purpose,
        method_id=method_id,
        teller_id=teller_id,
        status=status,
    )
    currency, currency_problem = _one_currency(rows)

    if group_by == GROUP_METHOD:
        keyed = rows.values("method_id", "method__name")
        key_field, label_field = "method_id", "method__name"
    elif group_by == GROUP_TELLER:
        # The till id groups in SQL; the PERSON is resolved afterwards, once per
        # group, because `counter_session_id` is not an FK. Bounded by the
        # number of tills, which is a staff count and not a tenant size.
        keyed = rows.values("counter_session_id")
        key_field, label_field = "counter_session_id", None
    elif group_by == GROUP_PURPOSE:
        keyed = rows.values("purpose")
        key_field, label_field = "purpose", None
    else:
        keyed = rows.annotate(day=TruncDate("posted_at")).values("day")
        key_field, label_field = "day", None

    aggregated = list(
        keyed.annotate(row_count=Count("id"), amount_sum=_sum("amount")).order_by("-amount_sum")
    )
    grand_total: Decimal = rows.aggregate(amount_sum=_sum("amount"))["amount_sum"]

    teller_names: dict[str, str | None] = {}
    if group_by == GROUP_TELLER:
        teller_names = _teller_names(
            [row["counter_session_id"] for row in aggregated if row["counter_session_id"]]
        )

    shaped: list[PaymentGroupRow] = []
    for row in aggregated:
        raw_key = row[key_field]
        key = None if raw_key is None else str(raw_key)
        if label_field is not None:
            label = row[label_field]
        elif group_by == GROUP_TELLER:
            label = teller_names.get(key) if key else None
        else:
            label = key
        share = None
        if not currency_problem and grand_total and grand_total != ZERO:
            share = (row["amount_sum"] / grand_total) * Decimal(100)
        shaped.append(
            PaymentGroupRow(
                key=key,
                label=label,
                count=int(row["row_count"]),
                amount=row["amount_sum"],
                share_pct=share,
            )
        )

    problems: list[dict[str, Any]] = [dict(GAP_BALANCES_ARE_NOT_A_PAYMENT_FACT)]
    if currency_problem is not None:
        problems.append(currency_problem)
    if group_by == GROUP_TELLER and any(row.key is None for row in shaped):
        problems.append(dict(GAP_TELLER_IS_UNKNOWN_BEFORE_TILLS))

    return {
        "basis": BASIS,
        "grain": f"one group of payments, by {group_by}",
        "group_by": group_by,
        "currency": currency,
        "rows": tuple(shaped),
        "totals": {
            "amount": None if currency_problem else grand_total,
            "payments": sum(row.count for row in shaped),
        },
        "problems": tuple(problems),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `payments` dataset query (05-prototype/09 Reports Build Brief.pdf p051–p058 read as images per B14 rule 42; §7.2/§7.2.1/§7.2.2 p083–p086; §7.5/§7.6 p087; §08 p090–p092)
# screens: S46 (the viewer) — R1's four group-bys
# generated: 2026-09-27 by lane DS-PAYMENTS
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=HUMAN-REVIEW-PENDING (🔒 payments read, money path)
# exceptions: (1) the dataset's declared grain was "one payment allocation" and this serves "one payment" — an allocation-grain query drops every deposit, prepay and plan-down payment, which is DEF-REP-6853 · (2) the eight semi-additive ageing columns are ABSENT rather than null-with-a-value: their grain is one account as at a date, named in `problems` · (3) this file writes nothing: no INSERT, UPDATE, DELETE or save() — hard rules 4, 5 and 7
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

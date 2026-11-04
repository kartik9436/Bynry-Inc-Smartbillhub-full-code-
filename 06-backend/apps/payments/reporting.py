# ── Trace ──────────────────────────────────────────────
# Story:    US-REP-005 (AR aging summary — buckets from open-invoice due-date
#           math, POSTING basis) · US-REP-007 (Payments by method — purpose-
#           aware, POSTING basis since 2026-10-21, capture intents excluded)
#           Screens: S46
# Rules:    BR-REP-001 (every header labels its basis; its clearing-date
#           basis for Payments by method is SUPERSEDED by the PO ruling of
#           2026-10-21, decision log "Two CR-186 follow-up rulings" item 2) ·
#           BR-REP-002 (read-models, never a side-maintained number) ·
#           BR-REP-006 (method and purpose vocabularies are the tenant's LIVE
#           ones) · BR-REP-008 (aging foots to the AR tie-out) · BR-REP-014
#           (collection framings count BILL-purpose payments only) ·
#           BR-PAY-012 (every payment carries a purpose) · BR-PAY-015 (an
#           autopay capture intent is not money and is counted nowhere) ·
#           BR-PAY-021 (posted ≠ cleared; staff always see both dates) ·
#           BR-PAY-032 ("days late" = today − the oldest unpaid due date) ·
#           BR-CUS-015 (`accounts.balance` is a CACHE — not read here) ·
#           CLAUDE.md rule 1 (tenant scoping) · rule 2 (never a float)
# Tests:    06-backend/tests/test_us_rep_canned_reports.py
# Impacts:  apps/reports/report_seams.py (the ONLY caller) · this file writes
#           nothing, anywhere
# ───────────────────────────────────────────────────────
"""Payments' two published REPORT read-models — the AR ageing and the cash mix.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — 🔒 an AR ageing is what a finance officer reconciles a
month-end against and what an auditor is shown. AI-authored under the PO ruling
of 2026-08-09; the row is in `12-governance/09-human-review-ledger.md`.

Both live HERE and not in `apps/reports` because payments is the only module
that can see both halves of each figure:

  * **AR ageing** needs an invoice's DUE DATE (billing's) and the allocations
    against it (payments'). `apps/payments/billing_seam.py` already joins those
    two for S34, along the reviewed `payment N:M invoice` edge B2 §2 grants —
    and it does so WITHOUT importing a billing model, which B1 forbids and G6
    greps for.
  * **Payments by method** is Σ over `payments`, which payments owns outright.

════════════════════════════════════════════════════════════════════════════
WHY THE AGEING IS PER-BILL AND S34's IS PER-ACCOUNT — THEY ANSWER DIFFERENTLY
════════════════════════════════════════════════════════════════════════════
`apps/payments/outstandings.py` puts an account's WHOLE balance in ONE band,
chosen by its oldest unpaid due date (BR-PAY-032). That is right for a
collections worklist: a clerk chasing a customer chases the customer, and the
worst debt sets the priority.

A14's AR ageing table is a different document. Its row reads
*Account · Customer · Class · Current · 31–60 · 61–90 · 90+ · Total*, and its
footer must equal the receivable. So each OPEN BILL is aged on ITS OWN due date
and lands in its own column: a customer with a fresh $200 bill and a 4-month-old
$50 one shows **200 current and 50 in 90+**, not 250 in 90+.

Both readings are correct and they are deliberately not merged. What must never
happen is a THIRD one, so this function reads the same open bills through the
same seam S34 does, and the two foot to the same total by construction.

**THERE ARE FIVE COLUMNS AND EACH IS ONE BAND — `P2.21`, 2026-09-24.**
`current` used to absorb `outstandings`' two youngest bands into one 0–30 day
column. `BR-REP-030` is PO-confirmed at five — *"Current / 1–30 / 31–60 /
61–90 / 90+"* — the Dashboard has shown five since it was built, and the
Finance blueprint p035 draws five and names five as its `f.band` values. So
`current` is now *not yet due*, `1-30` is its own column, and `d1_30` is a new
figure on the wire (`DEF-REP-6659`). The band boundaries are still
`outstandings`' and are written down exactly once, in `AGEING_BANDS`.

════════════════════════════════════════════════════════════════════════════
WHAT THE AGEING CANNOT DO TODAY, AND SAYS SO
════════════════════════════════════════════════════════════════════════════
BR-REP-008 / BR-CUS-048 require imported OPENING BUCKETS to age forward from the
cutover date. **`account_opening_buckets` (B2 r9 #2) is not built** — US-CUS-021
owns it — so a tenant that migrated from another system carries balances this
report cannot see. That is reported as a named gap on every run, with the read
that closes it (`apps.customers.selectors.opening_buckets_as_of`) named exactly
as `apps/ledger/reporting.py` names it. It is NOT silently omitted: a tie-out
that is short by the opening balances looks like a reconciliation failure, and
the person reading it has to know which of the two they are looking at.

════════════════════════════════════════════════════════════════════════════
POSTING BASIS (SINCE 2026-10-21), AND THE THINGS THAT ARE NOT CASH
════════════════════════════════════════════════════════════════════════════
⚠ **THIS READ WAS DATED BY `cleared_at` UNTIL 2026-10-21 (`DEF-PAY-10321`).**
BR-REP-001 put cash-side money on the CLEARING date, signed when *cleared*
meant *the money arrived*. `CR-186-BRC10` redefined `cleared` as *its deposit
batch was reconciled with the bank*, which lags by days, so a card payment
taken and applied on 14 Oct was absent from the 14 Oct report and appeared in
the 16 Oct one. PO ruling 2026-10-21 (decision log *"Two CR-186 follow-up
rulings"*, item 2), shown exactly that case, chose *"Posting date: the 14 Oct
payment appears in the 14 Oct report, the day the money was taken and
applied."* So `payments_by_method` selects on `posted_at`, the basis label is
`posting`, and reconciling a batch moves no payment between windows. Both
dates still ride on every detail row (BR-PAY-021); `cleared_on` is null until
the batch is reconciled. US-REP-007 TC-3's *"posted Jul 31, cleared Aug 2 is
AUGUST's"* is superseded the same way: it is now JULY's.

**WHICH ROWS:** `balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES` — `posted` and
`cleared` (the ruling's own words: *"They count `posted` + `cleared` by posting
date"*), plus the NEGATIVE `reversed` row a bounce writes, dated on its own
posting date (the return day). The reversing row is kept for the reason
`selectors.collected_by_class_for_invoices` TC-5 proved: dropping it leaves a
bounced cheque counted as money taken. The clearing-basis read already netted
it — both legs carried a clearing date — so reversals net exactly as before;
only the date moved.

Excluded, each for its own ruled reason:
  * **a `cancelled` payment** — taken by mistake and undone; the original and
    its reversing row both carry `cancelled`, so the whole pair is outside the
    set rather than netted by luck.
  * **`failed` and `processing`** — not money (`balance_rule`'s own reasons).
  * **an autopay capture INTENT** — BR-PAY-015 / A14 item 10: an intent is not
    money. `autopay_capture_intents` is a different table and is not read here.

The *"posted but not yet cleared in this window"* problem this report carried
is GONE, not reworded: on the posting basis every counted payment IS in the
window it was posted in, so the note had nothing left to count.

**BILL-purpose only in any collection framing** (BR-REP-014). This read model
returns every purpose, each on its OWN line, and publishes `bill_purpose_total`
separately so a caller can never accidentally fold a deposit into a collection
percentage.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from core.tenancy import current_tenant_id

from . import balance_rule, billing_seam, models
from .outstandings import (
    AGEING_BANDS,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
    BUCKET_CURRENT,
)

ZERO = Decimal("0")

#: BR-REP-001's two labels, named once so a report cannot be built with neither.
BASIS_POSTING = "posting"
BASIS_CLEARING = "clearing"

#: A14's ageing COLUMNS — **FIVE since `P2.21`, one per band**. They used to be
#: four, with `current` absorbing `outstandings`' two youngest bands; `BR-REP-030`
#: is PO-confirmed at five (*"Current / 1–30 / 31–60 / 61–90 / 90+"*) and the
#: Finance blueprint p035 draws five and names five in its `f.band` values.
#: `DEF-REP-6659` records the change of a served figure.
AGING_COLUMNS: tuple[str, ...] = (
    BUCKET_CURRENT,
    BUCKET_1_30,
    BUCKET_31_60,
    BUCKET_61_90,
    BUCKET_90_PLUS,
)

#: BR-REP-008 / BR-CUS-048's unbuilt half, in the shape every gap in this
#: product takes: a stable machine `code` the SCREEN keys its own translated
#: sentence on, the rule it comes from, prose for the next agent, and the read
#: that closes it BY NAME so the day it exists the gap closes with no edit here.
GAP_OPENING_BUCKETS = {
    "code": "imported_opening_buckets_are_not_built",
    "br_ref": "BR-REP-008 · BR-CUS-048",
    "detail": (
        "BR-CUS-048 requires balances imported at cutover to age FORWARD by calendar days "
        "from the as-of date, and BR-REP-008 puts them in this table. "
        "`account_opening_buckets` (B2 r9 #2) is not built — US-CUS-021 owns it — so a "
        "tenant that migrated from another system has receivable this report cannot see. "
        "The bands below cover bills this product issued and NOTHING ELSE. Stated rather "
        "than omitted: a tie-out short by exactly the opening balances looks like a "
        "reconciliation failure to the person reading it."
    ),
    "wanted_reads": ("apps.customers.selectors.opening_buckets_as_of",),
}


def _tenant_id() -> Any:
    return current_tenant_id()


def _accounts_by_id(ids: list[Any]) -> dict[Any, Any]:
    """Account rows through customers' OWN published queryset (B1/BR-TEN-013).

    `outstandings._accounts_by_id`'s twin, and deliberately the same shape: no
    customers model is imported and no ORM of theirs is walked.
    """
    queryset = billing_seam._resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover — customers publishes it
        return {}
    return {
        account.id: account
        for account in queryset().filter(id__in=ids).select_related("account_type")
    }


def _customer_name(account: Any) -> str | None:
    read = billing_seam._resolve("customers", "primary_contact_name")
    if read is None or account is None:  # pragma: no cover — customers publishes it
        return None
    return read(account)


def _customer_names_for(ids: list[Any]) -> dict[str, str | None]:
    """A PAGE's contact names — ONE query, through customers' own batched read.

    ⛔ **THIS REPORT CALLED THE SINGULAR ONCE PER ROW UNTIL `P2.21`.**
    `primary_contact_names_for` has been published since `DEF-2723` closed
    exactly this defect on the accounts list, and `outstandings.py` has used it
    since `CR-138-BRC07` `P4.1`; this file went on resolving one name per
    account, which at 40,000 debtors was 40,000 round trips for one column.

    Falls back to the singular when customers publishes no batched read: a Name
    column that silently emptied would be worse than a slow one.
    """
    if not ids:
        return {}
    batched = billing_seam._resolve("customers", "primary_contact_names_for")
    if batched is not None:
        return {str(key): value for key, value in batched(ids).items()}
    accounts = _accounts_by_id(ids)  # pragma: no cover - customers publishes it
    return {str(key): _customer_name(account) for key, account in accounts.items()}


@dataclass(frozen=True)
class AgingRow:
    """One account's receivable, split across A14's four columns."""

    account_id: str
    account_no: str | None
    customer_name: str | None
    account_class: str | None
    account_class_code: str | None
    buckets: dict[str, Decimal]
    total: Decimal
    #: BR-PAY-032, verbatim: today − the OLDEST unpaid invoice's due date. None
    #: when nothing is past due — never 0, which reads as "due today".
    days_late: int | None


def ar_aging(
    *,
    as_of: date,
    account_class: str | None = None,
    band: str | None = None,
    service_code: str | None = None,
    premises_id: Any = None,
    search: str | None = None,
    page: int = 1,
    per: int | None = 50,
    sort: str = "total",
    direction: str = "desc",
) -> dict[str, Any]:
    """A14's *AR aging summary*, aged per open bill on its own due date.

    `as_of` is an ARGUMENT and never a clock (BR-TEN-043): an ageing a clerk
    reads at 23:58 and one a scheduled job takes at 00:02 must be explainable
    against the same day, and a function that read the system date could not be
    asked for last month-end.

    ⚠ **AND SINCE `DEF-PAY-6940` (2026-09-27) IT SELECTS THE POPULATION AS WELL
    AS THE BANDS, WHICH IS THE WHOLE OF THAT DEFECT.** It banded by `as_of` and
    aged whatever was outstanding *at the moment of the query*, so every date
    ever asked for came back with the same total and the same debtor count.
    The position is now built from bills ISSUED by `as_of` (`invoices.issued_at`,
    frozen by `billing/migrations/0002`) and money POSTED by `as_of`
    (`payments.posted_at`, `BR-PAY-021`). **`billing_seam.aging_positions_page`
    is where it is done and its docstring carries the measured figures** — and
    the one thing it still cannot restore, with its count, is a bill that is
    `void` or `corrected` today (`DEF-PAY-7020`).

    POSTING basis (BR-REP-001) — this is receivable, which is billing-side
    money. A payment POSTED by the due date has written its allocation rows, so
    the bill is settled and simply is not here; the CLEARING date never drives
    ageing (BR-PAY-021, US-REP-005 TC-6). That falls out of reading allocations
    and is not a special case anywhere in this file.

    ════════════════════════════════════════════════════════════════════════
    THIS PULLED EVERY OPEN BILL INTO PYTHON UNTIL `P2.21` (`DEF-REP-6607`)
    ════════════════════════════════════════════════════════════════════════
    It `list()`ed the tenant's whole open set and folded it into a dict, so
    there was **no queryset**: none of p035's five criteria (`as_of`, band,
    service, property, search) could be expressed and neither could a page. A
    previous lane measured that and handed the task back rather than
    half-building it, which was the right call — see `DEF-REP-6607`.

    The arithmetic is unchanged and now happens in SQL, in
    `billing_seam.aging_positions_page`. **Two figures, because there are two
    questions:** `totals` is a SQL aggregate over the whole FILTERED set — what
    the KPI tiles show, and they foot to the rows whether a page is cut or not
    — and `population_total` is the same aggregate with every criterion
    removed, which is the only figure BR-REP-008's tie-out may be struck
    against. **A filter must never be able to make this report accuse the books
    of not footing**, and that is what separating the two buys.

    ⚠ **FIVE BANDS, NOT FOUR, SINCE `P2.21`.** `current` and `1-30` used to be
    folded into one column here; `BR-REP-030` is PO-confirmed at five and p035
    names five both in the drawing and in its `f.band` values. `d1_30` is a new
    figure and `current` is narrower than it was — `DEF-REP-6659`.
    """
    problems: list[dict[str, Any]] = [dict(GAP_OPENING_BUCKETS)]
    account_ids = None
    if account_class is not None:
        of_class = billing_seam._resolve("customers", "account_ids_of_class")
        if of_class is not None:  # pragma: no branch - customers publishes it
            account_ids = of_class(account_class)

    view = billing_seam.aging_positions_page(
        as_of=as_of,
        bands=AGEING_BANDS,
        band=band,
        service_code=service_code,
        premises_id=premises_id,
        search=search,
        account_ids=account_ids,
        page=page,
        per=per,
        sort=sort,
        direction=direction,
    )
    problems.extend(view.problems)

    accounts = _accounts_by_id([position.account_id for position in view.positions])
    names = _customer_names_for([position.account_id for position in view.positions])
    rows: list[AgingRow] = []
    for position in view.positions:
        account = accounts.get(position.account_id)
        account_type = getattr(account, "account_type", None)
        oldest = position.oldest_due_on
        rows.append(
            AgingRow(
                account_id=str(position.account_id),
                account_no=getattr(account, "account_no", None),
                customer_name=names.get(str(position.account_id)),
                account_class=getattr(account_type, "name", None),
                account_class_code=getattr(account_type, "code", None),
                buckets=dict(position.bands),
                total=position.total,
                days_late=None if oldest is None else (as_of - oldest).days,
            )
        )
    # ⚠ **NOTHING SORTS HERE.** The order is an `ORDER BY` in the statement
    # above; a `rows.sort` would re-order a page that was already cut, which is
    # `DEF-PAY-4221`'s exact shape one report along.

    currency = view.currencies[0] if len(view.currencies) == 1 else None
    if currency is None and view.currencies:
        problems.append(
            {
                "code": "receivable_holds_more_than_one_currency",
                "br_ref": "CLAUDE.md rule 2",
                "detail": (
                    "Open bills in this tenant are denominated in more than one currency, so "
                    "the ageing footer is not a number. Per-account rows are served; the "
                    "totals are null with this reason rather than a sum of unlike money."
                ),
            }
        )

    totals = dict(view.band_totals)
    return {
        "basis": BASIS_POSTING,
        "as_of": as_of,
        "currency": currency,
        "rows": tuple(rows),
        "totals": totals
        | {
            "total": view.total_owed,
            "accounts": view.total_accounts,
        },
        # ⚠ **THE TIE-OUT'S SIDE OF THE COMPARISON, AND IT DOES NOT MOVE WHEN A
        # CHIP IS ADDED.** `apps/reports/queries.ar_aging` compares THIS against
        # the ledger's AR control, never `totals["total"]`, so a clerk who
        # searches for one customer is not told the general ledger is broken.
        "population_total": view.population_total,
        "population_accounts": view.population_accounts,
        "filtered": view.filtered,
        "page": view.page,
        "per": per,
        "available": True,
        "problems": tuple(problems),
    }


@dataclass(frozen=True)
class MethodRow:
    """One method's slice of the window — A14's *ACH / Card / Check / Cash*."""

    method_id: str | None
    method_code: str | None
    method_name: str | None
    count: int
    amount: Decimal


@dataclass(frozen=True)
class PaymentDetailRow:
    """One counted payment, with BOTH dates and its purpose (BR-PAY-021/012).

    `cleared_on` is None until the payment's deposit batch is reconciled
    (CR-186-BRC10); the window never reads it.
    """

    payment_id: str
    payment_no: str | None
    account_id: str
    account_no: str | None
    customer_name: str | None
    method_name: str | None
    purpose: str
    confirmation: str | None
    posted_on: date
    cleared_on: date | None
    amount: Decimal
    currency: str


def payments_by_method(
    *, start: date, end: date, purpose: str | None = None
) -> dict[str, Any]:
    """A14's *Payments by method*, on the POSTING basis (PO ruling 2026-10-21).

    Every counted payment (`BALANCE_COUNTED_PAYMENT_STATUSES` — posted,
    cleared, and the negative reversing row) whose `posted_at` falls in
    `[start, end]`, grouped by the
    tenant's OWN payment-method rows (BR-REP-006 — a tenant that added "Money
    order" sees Money order; there is no hardcoded four).

    `bill_purpose_total` is published SEPARATELY from `total` so BR-REP-014 is
    structural rather than remembered: a caller computing a collection
    percentage reaches for the bill-purpose figure and cannot reach a total that
    has deposits folded into it.
    """
    tenant_id = _tenant_id()
    # DEF-PAY-10321 — the POSTING date and the counted set; see the module
    # docstring. This read `cleared_at` until 2026-10-21.
    counted = (
        models.Payment.objects.filter(
            tenant_id=tenant_id,
            status__in=balance_rule.BALANCE_COUNTED_PAYMENT_STATUSES,
            posted_at__date__gte=start,
            posted_at__date__lte=end,
        )
        .select_related("method", "account")
        .order_by("-posted_at", "-id")
    )
    if purpose is not None:
        counted = counted.filter(purpose=purpose)

    methods: dict[Any, dict[str, Any]] = {}
    details: list[PaymentDetailRow] = []
    by_purpose: dict[str, dict[str, Any]] = {}
    total = ZERO
    bill_total = ZERO
    currencies: set[str] = set()

    for payment in counted:
        method = payment.method if payment.method_id else None
        bucket = methods.setdefault(
            payment.method_id,
            {
                "method_id": None if payment.method_id is None else str(payment.method_id),
                "method_code": getattr(method, "code", None),
                "method_name": getattr(method, "name", None),
                "count": 0,
                "amount": ZERO,
            },
        )
        bucket["count"] += 1
        bucket["amount"] += payment.amount
        total += payment.amount
        currencies.add(payment.currency)
        purpose_bucket = by_purpose.setdefault(
            payment.purpose, {"purpose": payment.purpose, "count": 0, "amount": ZERO}
        )
        purpose_bucket["count"] += 1
        purpose_bucket["amount"] += payment.amount
        if payment.purpose == models.PURPOSE_BILL:
            bill_total += payment.amount
        details.append(
            PaymentDetailRow(
                payment_id=str(payment.id),
                payment_no=payment.payment_no,
                account_id=str(payment.account_id),
                account_no=getattr(payment.account, "account_no", None),
                customer_name=_customer_name(payment.account),
                method_name=getattr(method, "name", None),
                purpose=payment.purpose,
                confirmation=payment.confirmation,
                posted_on=payment.posted_at.date(),
                cleared_on=payment.cleared_at.date() if payment.cleared_at else None,
                amount=payment.amount,
                currency=payment.currency,
            )
        )

    problems: list[dict[str, Any]] = []
    # ⚠ The `posted_but_not_yet_cleared_in_this_window` problem lived here until
    # 2026-10-21 (DEF-PAY-10321). On the posting basis a counted payment is in
    # the window it was posted in, so there is nothing left to report.

    currency = currencies.pop() if len(currencies) == 1 else None
    if currency is None and currencies:
        problems.append(
            {
                "code": "cash_window_holds_more_than_one_currency",
                "br_ref": "CLAUDE.md rule 2",
                "detail": (
                    "Payments posted in this window are denominated in more than one "
                    "currency, so the method percentages and the total are not numbers. Rows "
                    "are served; the totals are null with this reason."
                ),
            }
        )

    rows = tuple(
        MethodRow(
            method_id=bucket["method_id"],
            method_code=bucket["method_code"],
            method_name=bucket["method_name"],
            count=bucket["count"],
            amount=bucket["amount"],
        )
        for bucket in sorted(methods.values(), key=lambda item: -item["amount"])
    )
    return {
        "basis": BASIS_POSTING,
        "window": {"start": start, "end": end},
        "currency": currency,
        "rows": rows,
        "details": tuple(details),
        # BR-PAY-012's four values, each on its OWN line. BR-REP-014 is why this
        # is a separate list and not a column on the method rows.
        "purposes": tuple(
            sorted(by_purpose.values(), key=lambda item: str(item["purpose"]))
        ),
        "totals": {
            "count": len(details),
            "amount": total if currency is not None else None,
            # BR-REP-014 — the ONLY figure a collection percentage may divide.
            "bill_purpose_amount": bill_total if currency is not None else None,
        },
        "problems": tuple(problems),
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-REP-005@c6c35b2 (co-packet US-REP-007; story+rules snapshot — 04-docs/05-modules/12-reports/06-epics/EP-REP-02-canned-reports.md §US-REP-005 + §US-REP-007 · 12-reports/02-business-rules.md BR-REP-001/002/006/008/011/014 · 08-payments/02-business-rules.md BR-PAY-012/015/021/031/032 · 05-prototype/UtilityBilling.html lines 4159-4180)
# screens: S46
# generated: 2026-08-16 by story-coder (reports lane — 18 of 19 reports stories had no code at all)
# checklist: A✔ B✔ C=deferred(the SCREEN half is apps/reports — this file publishes the read model it renders) D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_rep_canned_reports.py could not import this module before it existed. ruff✔ black✔ pytest✔ run_gates✔
# exceptions: (1) IMPORTED OPENING BUCKETS ARE NOT IN THE AGEING and every run says so by name — `account_opening_buckets` (B2 r9 #2) is unbuilt (US-CUS-021), so BR-CUS-048's forward ageing has nothing to read. Reported rather than omitted · (2) an open bill with NO due date is counted in the account's Total and in NO band, with a named problem — BR-PAY-032 cannot age it and 'Current' would read as fresh · (3) the ageing serves FIVE bands and not four since `P2.21` — `BR-REP-030` is confirmed at five and p035 names five; `current` is narrower than it was and `d1_30` is new (`DEF-REP-6659`) · (4) SINCE 2026-10-21 (DEF-PAY-10321, PO ruling) Payments by method is on the POSTING basis over posted + cleared + the negative reversing row; the posted-but-not-cleared problem is retired · (5) autopay capture intents are read nowhere in this file (BR-PAY-015 — an intent is not money) · (6) this file writes nothing, anywhere
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

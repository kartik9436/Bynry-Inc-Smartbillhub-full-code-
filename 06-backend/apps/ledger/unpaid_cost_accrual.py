# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C17 / task T7b — accrue unpaid supplier costs at close.
#           Screens: S42 (the close checklist item this completes)
#           NOTE: no US-ID is cited ON PURPOSE — G10 reads a Trace-header US-ID
#           as "this file ships that story's TCs", and no story owns C17 yet.
#           The authority is the change request, quoted below.
# Rules:    BR-LED-006 (the close checklist — AMENDED 2026-09-02 by CR-060 C17:
#           it is SEVEN items now, the seventh being `unpaid_cost_accrual`. It
#           is the mirror of the sixth and the two are ONE IDEA — period
#           matching — applied to each side of the books, which is what C17
#           asks for in as many words) · BR-LED-792 (NEW 2026-09-02 — how
#           unpaid supplier cost is measured at a period end) · BR-LED-005 (an
#           accrual auto-reverses on day 1 of the next period, linked both
#           ways) · BR-LED-028 (capture posts nothing and creates no payable —
#           UNTOUCHED, and see "WHY THIS IS NOT THE PAYABLE THE PO REFUSED"
#           below) · BR-LED-025 (the ledger is never a second rounding site) ·
#           BR-LED-001 (source_type + source_id on every line) · BR-TEN-038 (a
#           closed period is never posted into) · BR-TEN-043 (posted_at is an
#           INPUT) · CLAUDE.md rule 1 · rule 2 · rule 4 · rule 5 · rule 6 ·
#           rule 7
# Golden:   LE-11 — the nine July purchases, $51,902.50, of which CI-1 is
#           RS-2607-0141, $1,240.00 of bulk water at 5110. LE-4 — the
#           accrual/mirror pattern this reuses.
# Tests:    06-backend/tests/test_cr060_t7b_unpaid_cost_accrual.py
# Impacts:  apps/ledger/posting.py (the sole writer — `post()` is called from
#           here and nothing in this file touches journal_entries or
#           journal_lines) · apps/ledger/close.py (the date goes through
#           resolve_entry_date; `_unpaid_cost_accrual_item` reads this module's
#           key) · apps/ledger/cost_capture.py (the settlement posting this must
#           never double-count) · apps/ledger/manual_je.py (the day-1 reversal
#           is ITS sweep — this module writes no reversal of its own) ·
#           apps/ledger/services.ensure_period_matching_accounts (the credit)
# ───────────────────────────────────────────────────────
"""The supplier costs a period incurred and has not paid, put into the books.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides a figure that lands in
the trial balance. AI-authored 2026-09-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). The row is in
`12-governance/09-human-review-ledger.md` with the worked figure a reviewer is
approving (CR-060 task T19); nothing here reaches RATIFIED without that
signature.

════════════════════════════════════════════════════════════════════════════
THE GAP THIS CLOSES, IN THE CHANGE REQUEST'S OWN WORDS
════════════════════════════════════════════════════════════════════════════
CR-060 C17: *"Without it, revenue is recognised when BILLED and cost when PAID,
so a commodity sold in one month can have its cost land in the next. Accruing at
close and reversing on day one gives true matching AND creates no standing
payables balance, because the entry undoes itself."*

And its order note, which is why this is not a later task: *"SHIP IT WITH C1,
NOT AFTER. Settlement posting alone puts revenue on an accrual basis and cost on
a paid basis — a defect somebody finds in a signed month."* C1 landed on
2026-09-02, hours before this; the gap it opened is the one this closes.

════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT THE PAYABLE THE PO REFUSED — the load-bearing distinction
════════════════════════════════════════════════════════════════════════════
`BR-LED-028` stands, unamended by this file. The PO's objection of 2026-08-16
(closing `OQ-200`) was that posting `DR cost / CR accounts payable` at CAPTURE
would leave a liability **this product gives nobody a way to drain** — measured
in CR-060's own words at **$37,200.00** standing after twelve months at $3,100 a
month of purchased water, for invoices the utility had actually settled by
cheque, *"and a growing false number is worse than an absent true one"*.

**This accrual drains itself the next morning.** It is posted `type='accrual'`,
which is the type `apps/ledger/manual_je.run_accrual_auto_reversals` sweeps: on
day 1 of the following period the mirror posts `DR accrued / CR cost` and the
liability nets to **0.00**. It is a liability that exists for the length of one
period end, whose entire purpose is to make the month it closes complete.

**So nothing here creates the state the ruling refused**, and the proof is the
one C17 asks for and this module's tests assert: *"settling it afterwards posts
ONCE, not twice"*.

════════════════════════════════════════════════════════════════════════════
THIS FILE WRITES NO JOURNAL ROW. NOT ONE.
════════════════════════════════════════════════════════════════════════════
Every insert on `journal_entries` / `journal_lines` goes through
`apps/ledger/posting.py` (CLAUDE.md rule 5), and `ledger/0004`'s sole-writer
trigger makes that structural rather than a promise. Grep this file: there is no
`objects.create(`, no `.save(` and no `.delete(` on a journal model anywhere.

**AND THERE IS NO SECOND REVERSAL MECHANISM** (hard-won law 5, *one source*).
The mirror is posted by the sweep that already exists, keyed
`journal_entry|<accrual id>|auto_reversed`, one string per accrual forever. This
module does not schedule, compose or key a reversal.

════════════════════════════════════════════════════════════════════════════
BR-LED-792 — WHAT IS ACCRUED, AND THE ONE TEST THAT PREVENTS A DOUBLE COUNT
════════════════════════════════════════════════════════════════════════════
Stated once, here, and written into
`04-docs/05-modules/09-ledger/02-business-rules.md` the same commit.

**MEASURED — every captured supplier invoice this period had incurred and had
not settled BY THE PERIOD END.** Three clauses, and the third is the whole
safety property:

  1. `invoice_date <= period_end` — the cost belongs to this period or an
     earlier one. An invoice dated into the future is not a cost this month
     incurred, whatever day it was typed.
  2. `status != voided` — a voided capture is not a cost at all.
  3. **`paid_on IS NULL` OR `paid_on > period_end`** — unsettled *as at the
     period end*, which is NOT the same question as *unsettled today*.

**CLAUSE 3 IS WHY THE COST IS NEVER COUNTED TWICE, AND IT IS WORTH THE
PARAGRAPH.** The settlement posting (CR-060 C1) books `DR cost / CR cash` on
`paid_on`. So:

  * `paid_on` **on or before** the period end → the settlement entry is already
    in THIS period's books. Accruing it as well would charge the same water
    twice in the same month. It is EXCLUDED and COUNTED
    (`settled_within_the_period`).
  * `paid_on` **after** the period end, or unset → the settlement is in a LATER
    period. Accruing it puts the cost in the month the commodity was sold; the
    day-1 mirror takes it straight back out; the settlement then puts it in the
    later month. Net over the two months: **the cost, once.**

Worked on LE-11's CI-1 — $1,240.00 of bulk water bought 12 July and paid 4
August, closing July:

      31 Jul  accrual     DR 5110 purchased water   1,240.00
                          CR 2100 accrued costs                 1,240.00
       1 Aug  mirror      DR 2100 accrued costs     1,240.00
                          CR 5110 purchased water               1,240.00
       4 Aug  settlement  DR 5110 purchased water   1,240.00
                          CR 1000 cash                          1,240.00

    July 5110: **1,240.00** — the month the water was sold.
    August 5110: −1,240.00 + 1,240.00 = **0.00**.
    2100 at every month end after the mirror: **0.00**.

**DEBITED — the invoice's OWN `ledger_account`, never re-derived.** The account
was chosen at capture (or corrected by hand since, BR-LED-038), and re-resolving
it here would be a second implementation of one mapping rule — CR-060 §13's
third exclusion, in as many words: *"two implementations of one mapping rule
would eventually disagree, and the books would hold the wrong one."* It is the
same account the settlement will debit, which is what makes the pair cancel.

**CREDITED — the `accrued_expenses` DESIGNATION**, resolved through
`selectors`, never a number. `apps/ledger/services.ensure_period_matching_
accounts` places it on `2100 Accrued expenses` for a tenant that has not chosen
otherwise.

**ROUNDED once per journal line, half-up, to 2 dp** (BR-RAT-003's discipline at
this finalization; BR-LED-025 refuses more than 2 dp at posting). The credit is
the SUM OF THE ROUNDED DEBITS, so debits equal credits by construction rather
than by luck.

**ONE CURRENCY OR NOTHING** (DEF-081's rule, and `journal_entries.currency` sits
on the entry rather than the line precisely because a mixed-currency entry
cannot balance). A window holding purchases in two currencies is REFUSED by
name, not summed.

════════════════════════════════════════════════════════════════════════════
WHAT IS DELIBERATELY NOT MEASURED
════════════════════════════════════════════════════════════════════════════
**COST THAT HAS BEEN INCURRED AND NOT CAPTURED.** A load of chemicals delivered
on the 29th whose invoice arrives on the 6th of the next month is a real cost of
this period and this module cannot see it: nothing in the product knows it
exists. That is the mirror of the unread tail on the revenue side (`OQ-1323`)
and it has the same honest consequence — **the accrual is a FLOOR: the unpaid
cost we can prove, never more.** `UNCAPTURED_COST_NOT_ESTIMATED` rides on every
answer this module produces. It is not an open question, because there is
nothing to decide: no rule could estimate a document nobody has.

**CAPITAL SPENDING.** `chart.CAPITAL_CATEGORIES` refuses five names at capture
(CR-060 C15 / T5), so a $40,000 truck never becomes a `supplier_invoices` row
and cannot reach this accrual. Stated rather than left to be inferred from a
figure that looks right.

════════════════════════════════════════════════════════════════════════════
A CLOSED PERIOD IS REFUSED, NOT FORWARDED
════════════════════════════════════════════════════════════════════════════
The same judgment `unbilled_accrual` records, for the same reason and recorded
again in `12-governance/02-decision-log.md`: BR-TEN-038 forwards a late-dated
event into the earliest open period, which is right for a payment that genuinely
arrived late and WRONG here. Forwarded into the next month this accrual would
recognise July's cost in August and reverse it in September — two months wrong,
in a signed period, to avoid saying "no". So `accrue_unpaid_costs` REFUSES a
closed period by name and points at the reopen (System Admin, BR-LED-006).

The closedness is decided by `close.resolve_entry_date` — the ONE implementation
of the fiscal calendar — rather than by a second reading of the period tables.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from django.db.models import Q

from apps.ledger import (
    chart,
    close,
    models,
    posting,
    selectors,
    services,
    tenancy_seam,
)
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: BR-LED-001's mandatory pair, on the entry and on every line. One constant so
#: the write, the close checklist's read and the S42 drill-back all agree.
SOURCE_UNPAID_COST_ACCRUAL = "unpaid_cost_accrual"

#: The event half of the replay key (CLAUDE.md rule 6). One string per period,
#: forever, so pressing the button twice produces the same books.
EVENT_ACCRUED = "accrued"

#: A stable namespace for the period's `source_id`, the twin of
#: `unbilled_accrual.ACCRUAL_NAMESPACE` and for the same reason: an accrual's
#: "document" is a PERIOD, which has no row of its own, so the id is DERIVED
#: from (tenant, period) with uuid5 and is the same every time it is computed. A
#: random uuid here would mint a new posting key on every call and the replay
#: guard would never fire.
ACCRUAL_NAMESPACE = uuid.UUID("2d0c7f61-9b4e-5a3c-8e17-40f2c6b9d158")

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

#: Carried on EVERY result — the preview, the posting and the refusal — because
#: a figure that silently omits cost nobody has invoiced yet reads as the whole
#: answer. It is NOT an open question: see the module docstring.
UNCAPTURED_COST_NOT_ESTIMATED = {
    "code": "unpaid_cost_accrual_covers_only_captured_invoices",
    "br_ref": "BR-LED-792 · BR-LED-028",
    "detail": "this accrual measures supplier invoices the utility has CAPTURED and not yet "
    "settled. A cost that has been incurred and not yet invoiced — a delivery on the 29th "
    "whose invoice arrives on the 6th — is real and is NOT included, because nothing in the "
    "product knows it exists. There is no rule to write here and no question to ask: a "
    "document nobody has cannot be estimated. The figure is therefore a FLOOR: the unpaid "
    "cost we can prove, never more.",
    "wanted_reads": (),
}

#: ⚠ **THIS USED TO ALIAS `close.ROLE_GATE_IS_A_READING`, WHICH WAS RETIRED ON
#: 2026-09-24 WHEN THE PO RULED THE CLOSE GATE.** Posting an unpaid-supplier-cost
#: accrual is NOT closing a month and was never put to them, so this carry stays
#: flagged and returns to the agenda, exactly as `unbilled_accrual.py`,
#: `depreciation.py` and `manual_je.py` do. A signature covers only what was shown.
ROLE_GATE_IS_A_READING = close.ACCRUAL_ROLE_GATE_IS_A_READING


class UnpaidCostAccrualError(RuntimeError):
    """An accrual the ledger refuses, with the reason a human can act on.

    Distinct from `posting.PostingError` for the reason `manual_je.
    ManualJournalError` gives: a caller can tell *"the ledger refused the ACT"*
    (a closed period, nothing to accrue, no credit account) from *"the books
    refused the ENTRY"* (unbalanced, foreign account, a third decimal) without
    matching on prose.
    """


@dataclass(frozen=True)
class CostAccountAccrual:
    """One journal line of the accrual — one cost account's unpaid purchases.

    The line is per GL ACCOUNT and not per invoice, because that is what the
    books hold: `5110 Purchased water` is one figure a finance officer reads,
    and nine debit lines for nine invoices would put the supplier register into
    the general ledger. `invoice_count` and the preview's invoice rows are how a
    clerk gets back to the documents.
    """

    ledger_account_id: str
    code: str
    name: str
    amount: Decimal
    invoice_count: int


@dataclass(frozen=True)
class UnpaidInvoice:
    """One captured purchase inside the figure — C17's *"and the invoices it
    came from"*, the same courtesy C2's preview pays on the revenue side."""

    invoice_id: str
    reference: str | None
    supplier_name: str
    invoice_date: date
    service: str
    amount: Decimal
    ledger_account_id: str
    code: str


@dataclass(frozen=True)
class UnpaidCostPreview:
    """The figure, what it is made of, and everything it leaves out.

    `total is None` means **unanswerable** — the tenant's purchases in this
    window are in more than one currency, so no single entry can carry them —
    and is never conflated with a total of 0.00, which means *"nothing captured
    is unpaid"*. Only one of those two may be posted, and only one of them may
    reassure anybody.
    """

    period_start: date
    period_end: date
    currency: str | None
    total: Decimal | None
    accounts: tuple[CostAccountAccrual, ...]
    invoices: tuple[UnpaidInvoice, ...]
    invoice_rows_total: int
    accrued_expenses_account_id: str | None
    posting_key: str
    already_posted_entry_id: str | None
    period_is_closed: bool
    excluded: dict[str, int]
    problems: tuple[str, ...]
    unavailable: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class UnpaidCostResult:
    """What one `accrue_unpaid_costs` call did — and whether it did anything.

    `created=False` with an `entry_id` is the replay no-op (the same shape
    `posting.PostingResult` uses and for the same reason): a resumed close
    pressing the button twice is the correct outcome, not an error.
    """

    entry_id: str | None
    posting_key: str
    created: bool
    entry_date: date | None
    total: Decimal
    line_count: int
    accounts: tuple[CostAccountAccrual, ...]
    preview: UnpaidCostPreview
    unavailable: tuple[dict[str, Any], ...]


#: How many invoice rows a preview carries before it reports the count alone.
#: The twin of `unbilled_accrual.ACCOUNT_ROWS_SHOWN`, for the same reason: a
#: close over a utility with a thousand open purchases must not put a thousand
#: rows on a screen, and a clerk checking a figure needs a sample plus the
#: total.
INVOICE_ROWS_SHOWN = 200


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def accrual_source_id(*, period_start: date, period_end: date) -> UUID:
    """The period's stable document id. Same inputs ⇒ same uuid, always.

    Pure and total, with no clock and no database read, for the same reason
    `posting.posting_key` is: a caller must be able to ask *"has this period
    already been accrued?"* before doing any work, and be backstopped by
    `uq_journal_entries_posting_key` if it loses a race.
    """
    tenant_id = _tenant_id()
    return uuid.uuid5(
        ACCRUAL_NAMESPACE, f"{tenant_id}|{period_start.isoformat()}|{period_end.isoformat()}"
    )


def accrual_posting_key(*, period_start: date, period_end: date) -> str:
    """`unpaid_cost_accrual|<period uuid>|accrued` — composed, never typed."""
    return posting.posting_key(
        source_type=SOURCE_UNPAID_COST_ACCRUAL,
        source_id=accrual_source_id(period_start=period_start, period_end=period_end),
        event=EVENT_ACCRUED,
    )


def posted_accrual_entry_id(*, period_start: date, period_end: date) -> str | None:
    """The accrual already standing for this period, or None.

    Read by `close._unpaid_cost_accrual_item` so the checklist and this module
    can never disagree about whether the period's costs have been accrued.
    """
    key = accrual_posting_key(period_start=period_start, period_end=period_end)
    entry = (
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), posting_key=key, status=models.JE_POSTED
        )
        .values_list("id", flat=True)
        .first()
    )
    return str(entry) if entry else None


def _quantize(amount: Decimal) -> Decimal:
    """BR-RAT-003's rounding, applied ONCE per journal line at finalization."""
    return amount.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def unpaid_at(*, period_end: date) -> Any:
    """BR-LED-792's three clauses, as ONE queryset, declared ONCE.

    The preview and the exclusion counts are both taken from this, so the figure
    a clerk confirms and the reasons the rest were left out cannot be computed
    over two different selections — the discipline
    `reporting.remittance_by_authority` states for its own two columns.

    Tenant-scoped by construction (`_tenant_id()` refuses with no `app.tenant_id`
    set) and by RLS FORCE underneath it.
    """
    return (
        models.SupplierInvoice.objects.filter(
            tenant_id=_tenant_id(),
            invoice_date__lte=period_end,
        )
        .exclude(status=models.SUPPLIER_INVOICE_VOIDED)
        .filter(Q(paid_on__isnull=True) | Q(paid_on__gt=period_end))
        .select_related("ledger_account")
    )


def _excluded_counts(*, period_end: date) -> dict[str, int]:
    """Why the purchases this window holds and this accrual does not are out.

    A stated absence with a COUNT, never a silence — the posture
    `apps/billing/delivery_seam.BillDelivery` sets and every read in this module
    follows. A clerk who expected nine invoices and sees six needs to know that
    two were settled inside the period and one was voided, which are different
    facts with different remedies.
    """
    tenant_id = _tenant_id()
    in_window = models.SupplierInvoice.objects.filter(
        tenant_id=tenant_id, invoice_date__lte=period_end
    )
    counts: dict[str, int] = {}
    voided = in_window.filter(status=models.SUPPLIER_INVOICE_VOIDED).count()
    if voided:
        counts["invoice_is_voided"] = voided
    settled = (
        in_window.exclude(status=models.SUPPLIER_INVOICE_VOIDED)
        .filter(paid_on__isnull=False, paid_on__lte=period_end)
        .count()
    )
    if settled:
        # THE DOUBLE-COUNT GUARD, COUNTED RATHER THAN SILENT. These are the
        # invoices whose `DR cost / CR cash` is already in this period's books
        # (CR-060 C1). Accruing them as well would charge the same commodity
        # twice in the same month, which is the failure C17's own proof list
        # names last and this module exists to prevent.
        counts["settled_within_the_period"] = settled
    return counts


def preview_unpaid_costs(*, period_start: date, period_end: date) -> UnpaidCostPreview:
    """C17's figure before it is posted — the total, the accounts and the
    invoices behind it.

    Writes nothing. The same computation `accrue_unpaid_costs` posts, so a clerk
    who confirms a figure gets that figure, and a reviewer reading the
    review-ledger row can reproduce it.
    """
    if period_end < period_start:
        raise UnpaidCostAccrualError(
            f"the accrual period ends before it starts ({period_start} → {period_end}). "
            "A window with no days in it measures nothing."
        )

    key = accrual_posting_key(period_start=period_start, period_end=period_end)
    already = posted_accrual_entry_id(period_start=period_start, period_end=period_end)
    _, closed_note = close.resolve_entry_date(period_end)
    accrued_account = selectors.gl_account_id_for_designation(chart.ACCRUED_EXPENSES)
    excluded = _excluded_counts(period_end=period_end)
    problems: list[str] = []

    rows = tuple(unpaid_at(period_end=period_end).order_by("invoice_date", "id"))
    currencies = {str(row.currency) for row in rows}
    tenant_currency = tenancy_seam.tenant_currency()
    currency = currencies.pop() if len(currencies) == 1 else None
    if len(currencies) or (currency is None and rows):
        # DEF-081's rule. `journal_entries.currency` sits on the ENTRY and not
        # on the line precisely because a mixed-currency entry cannot balance,
        # and a total summed across two currencies is a number a finance officer
        # would put in a signed month.
        problems.append("purchases_in_this_window_are_in_more_than_one_currency")

    by_account: dict[str, dict[str, Any]] = {}
    invoices: list[UnpaidInvoice] = []
    for row in rows:
        account = row.ledger_account
        key_id = str(row.ledger_account_id)
        bucket = by_account.setdefault(
            key_id,
            {"code": account.code, "name": account.name, "amount": ZERO, "invoices": 0},
        )
        bucket["amount"] += row.amount
        bucket["invoices"] += 1
        invoices.append(
            UnpaidInvoice(
                invoice_id=str(row.pk),
                reference=row.reference,
                supplier_name=row.supplier_name,
                invoice_date=row.invoice_date,
                service=row.service,
                # Displayed at 2 dp (CLAUDE.md rule 2) — the SUM per account is
                # what gets rounded for posting, never these, so the rows can be
                # added up by hand and land within a cent of the line.
                amount=_quantize(row.amount),
                ledger_account_id=key_id,
                code=account.code,
            )
        )

    accounts: list[CostAccountAccrual] = []
    total = ZERO
    for account_id, bucket in sorted(by_account.items(), key=lambda item: item[1]["code"]):
        amount = _quantize(bucket["amount"])
        if amount <= ZERO:
            # A cost account whose unpaid purchases round to nothing gets no
            # line. A 0.00 debit is noise in a book somebody has to read.
            continue
        accounts.append(
            CostAccountAccrual(
                ledger_account_id=account_id,
                code=bucket["code"],
                name=bucket["name"],
                amount=amount,
                invoice_count=bucket["invoices"],
            )
        )
        total += amount

    return UnpaidCostPreview(
        period_start=period_start,
        period_end=period_end,
        currency=currency or tenant_currency,
        total=None if problems else total,
        accounts=tuple(accounts),
        invoices=tuple(invoices[:INVOICE_ROWS_SHOWN]),
        invoice_rows_total=len(invoices),
        accrued_expenses_account_id=accrued_account,
        posting_key=key,
        already_posted_entry_id=already,
        period_is_closed=closed_note is not None,
        excluded=excluded,
        problems=tuple(problems),
        unavailable=(UNCAPTURED_COST_NOT_ESTIMATED, ROLE_GATE_IS_A_READING),
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-006")
def accrue_unpaid_costs(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    posted_at: datetime,
) -> UnpaidCostResult:
    """Post the period's unpaid supplier cost: DR the cost accounts / CR accrued.

    ONE entry, of `type='accrual'`, dated the period end, keyed once per period
    forever. `apps/ledger/manual_je.run_accrual_auto_reversals` posts its day-1
    mirror on the next sweep — **this module writes no reversal**, because there
    is exactly one auto-reversal mechanism in this product and adding a second
    is how two of them come to disagree (hard-won law 5).

    `posted_at` is an INPUT (BR-TEN-043 / gate G6): a double-submitted close must
    stamp one moment, not two, and nothing in a money path reads a clock.
    """
    if not isinstance(posted_at, datetime):
        raise UnpaidCostAccrualError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043 — nothing in a "
            "money path reads a clock, gate G6)."
        )

    # Hard-won law 4: a tenant provisioned before today has no `accrued_expenses`
    # pointer, because the seed runs at provisioning and nowhere else. This is
    # the top-up, and it is idempotent — a tenant that has already chosen an
    # account keeps it (`services.ensure_period_matching_accounts` rule 1).
    services.ensure_period_matching_accounts(actor)

    preview = preview_unpaid_costs(period_start=period_start, period_end=period_end)

    if preview.already_posted_entry_id is not None:
        # The replay. A RESULT and not an exception, exactly as
        # `posting.PostingResult.created=False` is: a resumed close pressing the
        # button twice is the correct outcome.
        return UnpaidCostResult(
            entry_id=preview.already_posted_entry_id,
            posting_key=preview.posting_key,
            created=False,
            entry_date=period_end,
            total=preview.total or ZERO,
            line_count=0,
            accounts=preview.accounts,
            preview=preview,
            unavailable=preview.unavailable,
        )

    if preview.period_is_closed:
        # See the module docstring. Refused, not forwarded.
        raise UnpaidCostAccrualError(
            f"the fiscal period containing {period_end.isoformat()} is CLOSED, so its unpaid "
            "supplier costs cannot be accrued into it (BR-LED-006). BR-TEN-038 would forward "
            "the entry to the earliest open period, which would recognise this period's cost "
            "in a later month and then reverse it in the month after that — two months wrong "
            "in a signed book. Reopen the period (System Admin) if the accrual belongs in it. "
            "Nothing was posted and the closed period's trial balance is unchanged."
        )

    if preview.total is None:
        raise UnpaidCostAccrualError(
            "the unpaid-cost figure is UNANSWERABLE for this window, so nothing is posted: "
            f"{', '.join(preview.problems)}. A journal entry carries ONE currency (DEF-081), "
            "so purchases in two of them cannot be one accrual — and a total summed across "
            "them is a number a finance officer would put in a signed month."
        )

    if not preview.accounts or preview.total <= ZERO:
        raise UnpaidCostAccrualError(
            f"nothing captured is unpaid for {period_start.isoformat()} → "
            f"{period_end.isoformat()}: every supplier invoice dated on or before the period "
            "end is settled, voided, or rounds to less than a cent. Nothing is posted — an "
            "accrual of 0.00 is a journal entry that says nothing and has to be read anyway. "
            "The named exclusions and their counts are on the preview."
        )

    if preview.accrued_expenses_account_id is None:
        raise UnpaidCostAccrualError(
            "this tenant's chart has no account carrying the `accrued_expenses` designation, "
            "so the month-end cost accrual has nothing to credit. `2100 Accrued expenses` is "
            "the seeded account and a System Admin designates it on the GL mapping page. "
            "Nothing is posted, and no number is hardcoded — the code reads the DESIGNATION "
            "precisely so a tenant may renumber their chart (CR-060 §13's second exclusion). "
            "Crediting anything else would be a guess written into an entry that can never be "
            "edited (hard rule 4)."
        )

    source_id = accrual_source_id(period_start=period_start, period_end=period_end)
    lines: list[posting.PostingLine] = []
    for row in preview.accounts:
        lines.append(
            posting.PostingLine(
                ledger_account_id=row.ledger_account_id,
                side=models.SIDE_DEBIT,
                amount=row.amount,
                source_type=SOURCE_UNPAID_COST_ACCRUAL,
                source_id=source_id,
                # NO `premises_id` and NO `service_id`, and both absences are
                # deliberate. A line here is one COST ACCOUNT's worth of many
                # invoices, which between them may name several buildings and
                # none; stamping one of them would be a claim. The settlement
                # posting stamps `premises_id` because it is ONE invoice
                # (cost_capture.post_settlement_to_journal says so at its own
                # line), and `service_id` is absent there for the reason that
                # applies here too: `SupplierInvoice.service` holds a service
                # code OR one of sixteen cost categories, fourteen of which are
                # not services.
            )
        )
    lines.append(
        posting.PostingLine(
            ledger_account_id=preview.accrued_expenses_account_id,
            side=models.SIDE_CREDIT,
            amount=preview.total,
            source_type=SOURCE_UNPAID_COST_ACCRUAL,
            source_id=source_id,
        )
    )

    result = posting.post(
        posting.PostingRequest(
            posting_key=preview.posting_key,
            entry_date=period_end,
            posted_at=posted_at,
            currency=preview.currency or "USD",
            lines=tuple(lines),
            source_type=SOURCE_UNPAID_COST_ACCRUAL,
            source_id=source_id,
            memo=(
                f"Unpaid supplier cost accrual {period_start.isoformat()} → "
                f"{period_end.isoformat()} (BR-LED-792). Reverses on day 1 of the next "
                "period (BR-LED-005), so no payable is ever carried."
            ),
            entry_type=models.JE_ACCRUAL,
            audit_context={
                "action": "unpaid_cost_accrual",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total": str(preview.total),
                "cost_account_lines": len(preview.accounts),
                "invoice_rows": preview.invoice_rows_total,
                "excluded": dict(preview.excluded),
            },
        ),
        actor=actor,
    )
    return UnpaidCostResult(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        entry_date=period_end,
        total=result.debits,
        line_count=result.line_count,
        accounts=preview.accounts,
        preview=preview,
        unavailable=preview.unavailable,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C17 + task T7b (12-governance/11-change-requests.md §7 · §12 ·
#         §13) · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-005 /
#         006 / 025 / 028 / 001 / 792 · 08-worked-examples.md LE-4, LE-11 ·
#         CLAUDE.md hard rules 1-7 and hard-won laws 1, 2, 4, 5, 7, 14
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D✔(apps/ledger/accruals_api.py) E=deferred(C17 specifies
#         ONE endpoint and NO screen, and no task row in §12 owns one — the S42
#         surface for it is REPORTED rather than invented) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row written under
#         CR-060 T19 with the worked figure)
# gates: PROVED RED BEFORE GREEN — see
#         tests/test_cr060_t7b_unpaid_cost_accrual.py, whose module docstring
#         quotes each failure verbatim.
# exceptions: (1) **COST INCURRED AND NOT YET INVOICED IS NOT ESTIMATED** and
#         every result says so — it is not an open question because a document
#         nobody has cannot be estimated · (2) a CLOSED period is REFUSED rather
#         than forwarded — this lane's judgment, in the decision log with its
#         reasoning, the same one `unbilled_accrual` records · (3) a window
#         holding purchases in two currencies is REFUSED rather than summed
#         (DEF-081) · (4) the role gate is EP-LED-05 §8's flagged READING of
#         OQ-175, carried on every result · (5) the debit lines carry NO
#         premises and NO service dimension, both stated at the line
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

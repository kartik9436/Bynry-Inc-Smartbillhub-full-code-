# ── Trace ──────────────────────────────────────────────
# Story:    US-BIL-005 (issue — an issued bill becomes a fact other modules
#           must be able to ask about) · US-MET-003 (S16 plan panel — the
#           caller) · US-CUS-005 (move-out, the guard of the same shape) ·
#           US-BIL-025 (GET /invoices — the S30 All-bills list, its search,
#           filters, sorts and header roll-up) · US-BIL-026 (GET /invoices/{id}
#           — the bill detail: stamped lines, the A19 summary, the chain)
#           · US-BIL-001/002/003 (the S31 run read model — the run row, the
#           findings, the case tables)
#           Screens: S16 · S20 · S30 · S31 · S31.2 · S31.3 · S21 (Bills tab)
# Rules:    BR-BIL-004 (issued invoices are immutable; corrections are new
#           rows) · BR-BIL-010 (a line shows the GL STAMPED at issue, never a
#           re-resolution) · BR-BIL-024 (the due date is derived at issue) ·
#           BR-BIL-026 (the template version is pinned at issue) · BR-BIL-030
#           (the bill is LOCKED at issue — what it priced is settled) ·
#           BR-BIL-031 (payload_version is a different axis from the template) ·
#           BR-BIL-063 (the number is allocated when the DRAFT is created) ·
#           BR-MET-042 (a staff override travels with a warning and an audit
#           row, never silently) · BR-SHL-011 (list grammar q/sort/dir/page/
#           per/f.<name>) · BR-TEN-003 (cross-tenant reads as absent) ·
#           BR-TEN-043 (event-time law — "today" is the tenant's clock)
# Tests:    06-backend/tests/test_us_met_003_plan_backdating.py ·
#           06-backend/tests/test_us_bil_025_026_bills_read.py ·
#           06-backend/tests/test_us_bil_001_003_run_api.py
# Impacts:  apps/rating/seams.last_issued_bill_for_unit (the only consumer
#           today) → apps/rating/services.record_unit_plan_assignment ·
#           apps/billing/api.py (the two read endpoints) · 07-frontend
#           BillsListPage/BillDetailPage (the field names are their contract)
# ───────────────────────────────────────────────────────
"""billing READ surface — pure selectors, no writes, no side effects.

🔒 **HUMAN-OWNED · HUMAN-REVIEW-PENDING** (12-governance/09-human-review-ledger.md).
**AS OF CR-053 TASK 9 (2026-08-30) THIS FILE PERFORMS MONEY ARITHMETIC.** It was
pure serialization until then — every figure it served came out of a column and
went onto the wire unchanged. `_charges_by_service` ADDS money up: it sums a
bill's line amounts into a subtotal per service, and the way it rounds while
doing so is a signed rule (B4.4 + B4's 2026-08-11 ruling — Σ of the ROUNDED
lines, so the printed lines foot against the printed subtotal). That makes this
a 🔒 money path under CLAUDE.md's sensitive-paths section.

⚠ CORRECTED 2026-08-31 — THE PARAGRAPH BELOW IS HISTORY, NOT THE CURRENT STATE.
A glob in 10-scripts/gates/human_owned.txt DOES match this file now: the PO
ruled on 2026-08-31, having been shown all 62 unguarded files in five groups,
that groups one to four go on the watched list — "56 files" in their own words
— and this file is one of them. G7 checks it from that commit. The paragraph is
kept because WHY it went unguarded is worth knowing (DEF-2790: the check
written to catch exactly this looked for the wrong marker for three days), and
nothing below it should be read as describing today.

⚠ **AND NO GLOB IN `10-scripts/gates/human_owned.txt` MATCHES THIS FILE, SO G7
REPORTS CONFORM OVER IT — `DEF-2437`.** The marker above and the ledger row both
exist; only the guard-list entry is missing, and that file's own header makes the
guarded set the PO's to change (*"who watches the watchers"*), so **a lane may
not add itself** and the addition is REQUESTED in the ledger row instead. This is
the sixth occurrence of that exact escape on a money path — `issue.py`,
`decisions.py` and `read_analysis.py` each record it in their own guard-list
entries, and two sibling lanes reported it again on 2026-08-30.

Why this module exists at all. Two guards in two other modules need one fact
that only billing can answer — *which days of this unit have already been
billed on a bill that went out?* — and neither may touch `invoices`. B1 puts
cross-module reads behind the owning module's selector, so the fact is
published here and the neighbours resolve it BY NAME through their own seam.

WHAT "LATEST" MEANS HERE, because the obvious reading is the wrong one. The
row returned is the one with the greatest `period_end`, not the most recently
issued. The question a caller is asking is "which is the last day already
covered by a bill", and a later-issued correction for an earlier period does
not un-bill the days a previous bill covered. Ordering by issue time would
answer a different question and would answer it wrong exactly when it matters.

WHICH STATUSES COUNT AS ISSUED: `INVOICE_LOCKED_STATUSES` — issued, paid, void
and corrected. All four describe a document that LEFT THE BUILDING; only
`draft` never did. Void is included deliberately: a voided bill was still sent
to a customer, and BR-BIL-004 makes the correction a NEW row rather than an
edit, so the voided one remains part of what the customer was told. The cost of
including it is one extra warning; the cost of excluding it would be a silent
pass on a period the customer has a piece of paper about. For a warn-only
guard, over-inclusion is the safe direction, and it is a choice, not an
accident — stated so a reviewer can overturn it deliberately.

BY UNIT, not by account, and that is stronger. The plan lives on the UNIT
(PO ruling 2026-08-11); occupants come and go. A plan date reaching back into a
PREVIOUS occupant's billed period contradicts that occupant's bill just as
surely as it would the current one, so the read spans every account that has
ever billed on the unit. The join `account__unit_id` travels the reviewed
cross-module FK `invoices.account_id → customers.Account` (B2 §2) — a read
along a reviewed edge, never a model import (G6 forbids those, and rightly).

⚠ REPORTED, NOT FIXED HERE. `apps/customers/seams.last_issued_invoice_period_end`
resolves its billing read from `apps.billing.SERVICES` (its `resolve()` default
kind), so customers' move-out guard is STILL unwired even though `invoices`
now exists — every move-out keeps returning the
`move_out_date_not_checked_against_issued_bills` warning. The fix is one word
in customers' seam (`kind="selectors"`) plus the account-scoped read it names;
customers is another lane's territory, so this is named rather than reached
into. Do not read this paragraph as "handled".

────────────────────────────────────────────────────────────────────────────
THE S30 READ SURFACE (added 2026-08-11 — US-BIL-025 / US-BIL-026)
────────────────────────────────────────────────────────────────────────────
Everything below `INVOICE_SORTS` serves the two endpoints in
`apps/billing/api.py`. The FIELD NAMES are not chosen here: they are the
contract written down in `04-docs/01-spec/11b-api-audit.md` §2.8a and typed in
`07-frontend/src/api/endpoints.ts` (`InvoiceRow` · `InvoicesPage` ·
`InvoiceLineRow` · `InvoiceDetail` · `InvoiceSummary`), with a field-by-field
prose version naming each `models.py` column in
`07-frontend/src/features/billing/README.md`. Renaming one here breaks a
shipped screen; a field this module cannot answer is served NULL under its
contracted name, never dropped and never renamed.

**FOUR THINGS THAT ARE DELIBERATELY NOT ANSWERED**, each because answering
would state something no row in this database supports:

  1. `past_due` — `issued ∧ unpaid ∧ due_date < today`. Served as null on every
     row: "unknown", never "not past due".

     ⚠ **CORRECTED 2026-08-27 (`DEF-1061`), AND THE HALF THAT WAS WRONG IS THE
     HALF A READER WOULD ACT ON.** This entry used to say *"'Unpaid' is the
     payments/ledger position and NEITHER module has a table"*. That was true
     when it was written and has been false since W5: `apps.payments` and
     `apps.ledger` both have tables, and `apps/billing/payments_seam.py` already
     asks payments for an account's position — on this very model, at issue,
     for BR-BIL-035's arrears block. A lane reading the old sentence concluded
     the work was blocked on two missing modules; it is blocked on one thing.

     **THE ONE THING IS THE CLOCK.** "today" is the TENANT's (BR-TEN-043), not
     this process's, and tenancy's regional read does not reach this filter.
     Comparing `due_date` to a wall clock would report a bill as past due a day
     early or a day late for every tenant west of UTC, and gate G6 bans
     `timezone.now()` in a money path for exactly that reason. A wrong past-due
     is a claim about a customer's money, so it stays null until the clock is
     wired rather than being computed nearly right.

     ⚠ **AND A NULL HERE IS ONE FACT ABOUT THE DEPLOYMENT, NOT 47 FACTS ABOUT 47
     BILLS.** The list screen used to print *"Past-due unknown"* in every issued
     row's status cell, where it became the column's content (`DEF-967`). It now
     says it once, above the table. Nothing about this serve changed; the note
     moved.
  2. `rollup.billed_this_cycle` / `billed_currency` — no signed document says
     what "this cycle" means for the S30 header (the prototype calls the same
     $342,180 both "out this cycle" and "billed this month", and a cycle can
     carry a parent run plus catch-up sub-runs). A money KPI computed on a
     guessed definition is a claim about money. Null, and REPORTED.
  3. `document_url` — `GET /invoices/{id}/document` (11b §2.8, BR-BIL-026) is
     not mounted. A URL here would be a link to a 404: built is not wired
     (hard-won law 2). Null, with `has_payload` telling the screen whether a
     stamped instance exists at all.
  4. `deliveries` — null, NOT `[]`. CORRECTED 2026-08-11: this used to say
     BR-BIL-016's queue has no table, and it HAS one — `outbound_messages`
     (r12 #16), which issue now writes one row per bill per channel into. The
     serve stays null because THIS READ is not built: the per-bill delivery
     list is US-BIL-024's (S30), and an empty array would still claim this bill
     was never sent to anyone. REPORTED rather than quietly widened — reading
     another module's rows is a published-selector call notifications has not
     made yet.

**AND ONE THING THAT REFUSES.** `f.status=past_due` is a segment the prototype
draws and the server cannot resolve. Returning the issued rows says "these are
past due"; returning none says "there are none". Both are false. So that one
filter VALUE refuses with a catalog exception naming the rule — a deliberate,
reported deviation from BR-SHL-011's "a list URL never errors over its params",
taken because every silent alternative lies about a customer's money. It is on
the agenda for the PO; nothing here decides it permanently.

**THE INSIDE OF `bill_payload` IS NEVER OPENED.** BR-BIL-030 says what the
frozen instance must contain and BR-BIL-031 versions it, but no signed document
names its JSON keys, and BR-BIL-026 puts the render on the SERVER. So the detail
exposes `has_payload` as a boolean and nothing here parses the JSON — two lanes
guessing one schema is DEF-014 wearing a different hat.
"""

from datetime import date, datetime, time, timedelta, timezone
from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal
from importlib import import_module
from typing import Any
from uuid import UUID

from django.db.models import Count, DecimalField, F, Max, Min, Q, QuerySet, Sum
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Cast, Coalesce

from apps.billing import (
    corrections,
    day_share,
    decisions,
    delivery_seam,
    metering_seam,
    pending,
    read_analysis,
    runs,
)
from apps.billing.models import (
    INVOICE_CORRECTED,
    INVOICE_DRAFT,
    INVOICE_ISSUED,
    INVOICE_LOCKED_STATUSES,
    INVOICE_PAID,
    INVOICE_STATUSES,
    INVOICE_VOID,
    BUDGET_EVENT_BILLED,
    BUDGET_EVENT_SETTLED,
    AccountBudgetEvent,
    Adjustment,
    BillRun,
    BillRunBreak,
    BillRunDecision,
    BillRunExclusion,
    BillRunRelease,
    CreditNote,
    Invoice,
    InvoiceLine,
)
from apps.billing.exceptions import BillingRuleError
from core import errors
from core import batch_reads
from core import money
from core import search as core_search
from core import tenancy as core_tenancy
from core.pagination import ListParams, clamp_page_size, filter_values, parse_list_params

#: DB-3 storage precision. STORAGE only — half-up 2dp is a finalization/display
#: concern that belongs to B4, and nothing in this read path rounds money.
SIX_PLACES = Decimal("0.000001")
MIN_SEARCH_CHARS = 2  # IS-3: server-side search from 2 characters

#: The rule the served-null `past_due` cites. Named once, as a constant, so the
#: reason a bill's past-due state is unknown is greppable from both sides of the
#: wire instead of living in a comment.
PAST_DUE_UNAVAILABLE = "BR-TEN-043"


def _tenant_id() -> Any:
    """Hard rule 1: no tenant table is touched without `app.tenant_id` set.
    Refuse loudly rather than run an unscoped query that RLS would then have
    to be the only thing standing between one tenant and another's bills."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """The owning module's published callable, or None while it has none.

    getattr-at-call-time, the same idiom `apps/billing/gather.py` and
    `apps/billing/tenancy_seam.py` use: no import statement binds billing to
    another module's internals (B1/BR-TEN-013, gate G6), and the moment a lane
    publishes its function every seam call starts using it with no re-wiring.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - defensive
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def last_issued_bill_for_unit(unit_id: Any) -> dict[str, Any] | None:
    """The furthest-billed ISSUED bill covering this unit, or None if none.

    Returned shape (dates as `date` objects — the caller formats):
        {invoice_id, invoice_no, account_id, status,
         service_date, period_start, period_end, issued_at}

    `invoice_no` may be None: BR-BIL-063 mints the number when the draft is
    created, but an older row or a hand-made fixture can carry none, and a
    caller must not assume the bill can be named.
    """
    row = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account__unit_id=unit_id,
            status__in=INVOICE_LOCKED_STATUSES,
        )
        .order_by("-period_end", "-created_at")
        .first()
    )
    if row is None:
        return None
    return {
        "invoice_id": str(row.pk),
        "invoice_no": row.invoice_no,
        "account_id": str(row.account_id),
        "status": row.status,
        "service_date": row.service_date,
        "period_start": row.period_start,
        "period_end": row.period_end,
        "issued_at": row.issued_at,
    }


def unissued_final_bill_for_account(account_id: Any) -> dict[str, Any] | None:
    """`CR-185-BRC10` — this account's FINAL bill still waiting to be sent, or None.

    A move-out drafts the final bill and the clerk sends it later from Billing
    (`DEF-CUS-10093`). Customers asks this to decide whether a tie-back to the
    owner can post NOW or must wait for that issue (coordinator ruling
    2026-10-14: *"the transfer must move only money that is IN THE BOOKS"*).
    A draft that was voided or deleted is not waiting, so it is not returned.

    Shape: `{invoice_id, invoice_no, total, currency}` (`total` a Decimal).
    """
    row = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            bill_type="final",
            status=INVOICE_DRAFT,
        )
        .order_by("-created_at")
        .first()
    )
    if row is None:
        return None
    return {
        "invoice_id": str(row.pk),
        "invoice_no": row.invoice_no,
        "total": row.total,
        "currency": row.currency,
    }


def last_issued_invoice_date(account_id: Any) -> Any:
    """WHEN this account was last billed — the S17 "Last bill" cell (DEF-127).

    Returns the `issued_at` DATE of the account's most recently issued bill, or
    None when it has never been billed.

    **PUBLISHED 2026-08-15, AND THE CELL HAD BEEN WRONG SINCE `invoices`
    LANDED.** `apps/customers/seams.last_issued_invoice_date` has asked for this
    name since before billing had tables; nothing ever answered, so every S17
    row rendered **"Awaits billing"** — including the row for account
    `E2E-10001`, which was holding an ISSUED bill of 108.88 dated 1 July at the
    time DEF-127 was measured in a browser. That is the same shape as DEF-035
    one function below: a seam pointing at the wrong module attribute, a caller
    correctly reporting the absence, and a screen quietly stating something
    untrue about a customer's money.

    A DATE and not a datetime, because the cell is a date cell and the tenant's
    timezone is the frontend's to apply (BR-TEN-020) — handing it a UTC instant
    would put a 19:00 bill on the wrong day for a UTC-07:00 utility. `issued_at`
    can be NULL on a locked row that predates the column being populated, so the
    ordering falls back to `period_end` and the value it returns is None rather
    than a date invented from the period.

    LOCKED statuses, not `issued` alone: a bill that has been paid, is overdue
    or has been corrected was still ISSUED, and "last bill" means the last one
    that reached the customer. Same predicate as
    `last_issued_invoice_period_end` immediately below, for the same reason.
    """
    row = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            status__in=INVOICE_LOCKED_STATUSES,
            issued_at__isnull=False,
        )
        .order_by("-issued_at", "-created_at")
        .values_list("issued_at", flat=True)
        .first()
    )
    return None if row is None else row.date()


def last_issued_invoice_dates(account_ids: Any) -> dict[str, Any]:
    """The same read for a WHOLE PAGE of accounts — `{account_id: date}`.

    ONE query for an S17 page instead of one per row. `apps/customers/api.py`
    builds every row before the paginator slices, so the single-account read
    above would be a query per account on the product's busiest screen — the
    same reason `apps.ledger.reporting.ar_positions` takes a list of ids.

    An account with no issued bill is ABSENT from the mapping rather than
    present with None: absent means the caller's `.get()` gives None either way,
    and a key that exists carries a date. The single-account read stays for the
    S21 detail path, which asks about exactly one.

    Ordered so the LAST row per account wins the dict comprehension — Django
    cannot `DISTINCT ON` portably here and the page is bounded by the tenant's
    account count (<3,000 connections, B12), so the rows are walked and the
    latest kept.
    """
    rows = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id__in=list(account_ids),
            status__in=INVOICE_LOCKED_STATUSES,
            issued_at__isnull=False,
        )
        .order_by("issued_at", "created_at")
        .values_list("account_id", "issued_at")
    )
    return {str(account_id): issued_at.date() for account_id, issued_at in rows}


@batch_reads.memoised
def last_issued_invoice_period_end(account_id: Any) -> Any:
    """The last day covered by an ISSUED bill for ONE account, or None.

    THE READ THAT MAKES A GUARD WRITTEN WEEKS AGO ACTUALLY RUN.
    `apps/customers/services._check_move_out_against_issued_bills` has enforced
    US-CUS-005 TC-6 — a move-out may not be dated behind the last issued bill
    (BR-BIL-004: issued bills are untouched; corrections route through the
    correction workflow, not through backdating a move-out) — since before
    `invoices` existed. Its seam resolved THIS NAME and found nothing, so the
    guard recorded `move_out_date_not_checked_against_issued_bills` and let the
    move-out through. Every move-out, since the day it was written.

    That is hard-won law 2 in its quietest form: the code was correct, the
    tests passed (they monkeypatch the seam), and the check had never once run
    against a real bill. Publishing this function is the whole fix; the refusal
    was already written and correct (DEF-035).

    By ACCOUNT, unlike `last_issued_bill_for_unit` above, because a move-out
    closes an account and the question is what THAT account has been billed
    for. The unit-level read answers the different question the plan-assignment
    guard asks — a previous occupant's bill contradicts a plan change on the
    unit, but it does not constrain when the NEXT occupant may move out.
    """
    row = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            status__in=INVOICE_LOCKED_STATUSES,
        )
        .order_by("-period_end", "-created_at")
        .values_list("period_end", flat=True)
        .first()
    )
    return row


#: `invoices.bill_type` values whose document covers NO SERVICE PERIOD, so its
#: `period_end` says nothing about how far the account has been billed.
#:
#: ⚠ **ONE MEMBER, AND `penalty` IS DELIBERATELY NOT IN IT.** A penalty or
#: catch-up bill is priced per SUB-PERIOD against the tariff version in force
#: then (BR-BIL-018/019), so its window is a real span of days that really were
#: billed. A `fee` bill is the one kind whose *"whole bill IS a charge code"*
#: (`one_time.CHARGE_CODE_KINDS`) — *"a fee has no usage, no reading and no
#: plan"* — and `fee_bill` writes `period_start = period_end = the fee's date`
#: because a row needs a date, not because a day of service was priced.
NON_SERVICE_BILL_TYPES: tuple[str, ...] = ("fee",)

#: The key `final_bill.draft_move_out_final_bill` stamps into a move-out final
#: draft's `bill_payload` (`final_bill.MOVE_OUT_DRAFT_MARKER`, `DEF-CUS-10093`);
#: restated here because `final_bill` imports this module. A test pins the two.
MOVE_OUT_DRAFT_MARKER = "created_by_move_out"


def billed_position_q() -> Q:
    """🔒 HUMAN-REVIEW-PENDING · `DEF-CUS-10154` — WHICH BILLS SAY HOW FAR AN
    ACCOUNT HAS BEEN BILLED: every issued bill (`INVOICE_LOCKED_STATUSES`) AND
    a live move-out final DRAFT.

    A draft is otherwise deliberately not an anchor — a cycle run's draft that
    is discarded and re-run covered nothing (`runs.last_issued_window`). A
    move-out's final draft is a different thing: Complete raised it as the
    final bill of a tenancy that ENDED (`DEF-CUS-10093`, PO 2026-10-13 option
    B), and it stays a valid bill for those days that the clerk may still send.
    **Coordinator decision 2026-10-14 (decision log *"A REOPENED ACCOUNT'S NEXT
    BILL STARTS THE DAY AFTER ITS FINAL BILL"*):** when that account is
    reopened (CR-181), its next bill starts the day AFTER the final bill's
    period end, whether the final bill is still a draft or sent; a final draft
    the clerk CANCELS is deleted (`runs.discard_run`) and then anchors nothing,
    so the next bill opens on its normal cycle start. Worked, Viktor Valdez
    AC-2026-00022: final draft 10/01–10/12 **$205.38**; the October run billed
    10/01–10/31 again (**$292.15**, 1,123 kWh / 15 kgal from the 09/29 reads);
    with this anchor it bills **10/13–10/31**, measured from the 10/12 final
    reads. No day is on two bills.

    Only a FINAL bill a MOVE-OUT created qualifies (`bill_type='final'` and the
    marker), never a cycle run's or a one-time tab's draft.
    """
    return Q(status__in=INVOICE_LOCKED_STATUSES) | Q(
        status=INVOICE_DRAFT,
        bill_type="final",
        bill_payload__has_key=MOVE_OUT_DRAFT_MARKER,
    )


@batch_reads.memoised
def last_issued_service_period_end(account_id: Any) -> Any:
    """The last day covered by an issued bill **THAT BILLED SERVICE** — `DEF-CUS-6086`.

    `last_issued_invoice_period_end` above answers *"what is the newest issued
    document"*, which is the right question for the move-out date guard: a
    document that left the building constrains what may be backdated behind it,
    whatever it charged for. **It is the wrong question for *how far has this
    customer been billed*, and the difference is money.**

    ⚠ **MEASURED, ON THE TWO CUTS THIS PRODUCT HAS PERFORMED.** `commit_cut`
    raises the final metered bill FIRST and the $75.00 reconnection fee second,
    inside one transaction — so on a clean cut the fee cannot interfere. When
    billing REFUSES that final bill (here: the commercial electric base charge
    prices per connection size and the connection had no size recorded), the fee
    is raised anyway with `period_start = period_end = the cut day`, and the
    account now holds an issued invoice whose period ends ON the cut. Every
    later attempt at the same window then answers
    `already_billed_through_the_cut_day` — *"an issued bill already covers this
    account through 2026-09-20"* — **which is false**: on `A-11340` nothing has
    billed 2021-03-15 through 2026-09-20 at all, and the only document on the
    account is a $75.00 fee.

    That answer carries `billed=True`, so a caller trusting it would write
    BR-CUS-107's `Disconnected` over days nobody has billed and drop the account
    out of `accounts_for_bill_run` — which is `OQ-1170`'s **$23.23** exactly,
    restored by a fee raised to record something else.

    So this read asks the same question of the same rows and skips the bill
    types that cover no service period (`NON_SERVICE_BILL_TYPES`). Ordered on
    `period_end` for `last_issued_invoice_period_end`'s stated reason: a bill
    issued late for an early period does not move the billed position forwards.

    ⚠ **AND A LIVE MOVE-OUT FINAL DRAFT COUNTS (`DEF-CUS-10154`,
    `billed_position_q`).** It is the final bill of the tenancy that ended; a
    reopened account's next bill — a cycle bill, a cut bill or a second final
    bill — opens the day after it, never over the same days.
    """
    row = (
        Invoice.objects.filter(
            billed_position_q(),
            tenant_id=_tenant_id(),
            account_id=account_id,
        )
        .exclude(bill_type__in=NON_SERVICE_BILL_TYPES)
        .order_by("-period_end", "-created_at")
        .values_list("period_end", flat=True)
        .first()
    )
    return row


def unbilled_service_window(account_id: Any, *, through: Any) -> dict[str, Any] | None:
    """The days this account has NOT been billed for, up to and including `through`.

    **PO ruling 2026-09-21, ruling 1 — a cut is completed WITHOUT a bill.** A
    clerk may now write BR-CUS-107's `Disconnected` with no final bill at all,
    and the account then leaves `customers.selectors.accounts_for_bill_run`.
    The PO ruled WHO raises the bill; they did not rule that the days stop
    mattering: *"in single bill we have final bill workflow - so if clark want
    to complete the bill he can do it from there"*. **So the days have to stay
    visible to somebody**, and this is the read that keeps them visible.

    ⚠ **IT IS DERIVED AND NOTHING IS STORED, WHICH IS THE WHOLE DESIGN.** A
    column or a flag written at completion would say *unbilled* for ever — it
    would go on saying it the day billing's single-bill workflow raised the
    bill, and nothing would move it (hard-won law 2's mirror: a stated absence
    that outlives its cause). This asks the same question
    `cut_bill.first_unbilled_day` asks at the cut, so the answer **closes
    itself**: the moment an issued bill covers `through`, this returns `None`
    and every surface reading it goes quiet without anybody clearing anything.

    The window is `first_unbilled_day(account) … through`, both ends INCLUSIVE
    (BR-CUS-103 — *"a service is billed base right up to the moment it is
    cut"*), and `days` is the calendar-day count B4.3's numerator uses.

    **`None` means there is nothing unbilled to state**, and it has three
    causes a caller does not need to tell apart: an issued bill already covers
    `through`; a migration's opening receivable already covers it
    (BR-CUS-048/049 — those days were billed by the system this one replaced);
    or the account records no start at all, which `first_unbilled_day` REFUSES
    rather than guesses. That refusal is caught here because this is a READ
    behind a screen: raising would take a record page down over a question it
    was only asking.
    """
    # Imported INSIDE the function: `cut_bill` imports this module (lazily, in
    # `first_unbilled_day`), so a module-level import here would close the cycle.
    from apps.billing import cut_bill

    if through is None:
        return None
    last_day = through if isinstance(through, date) else date.fromisoformat(str(through))
    try:
        opens = cut_bill.first_unbilled_day(account_id)
    except BillingRuleError:
        return None
    if opens is None or opens > last_day:
        return None
    return {
        "start": str(opens),
        "end": str(last_day),
        "days": (last_day - opens).days + 1,
    }


def financial_records_exist() -> bool:
    """BR-TEN-042's currency-lock probe, billing's half — **DEF-075**.

    THE DEFECT THIS CLOSES WAS MEASURED IN A BROWSER, NOT REASONED ABOUT.
    `PUT /api/brazosbend/settings/regional {"currency":"CAD"}` answered **200**
    on a tenant holding issued bill **BL-2606-000001 (108.88 USD)**, and the
    tenant's currency changed. `apps/tenancy/services.py` raises 409 BIZ-LOCKED
    correctly and asks `seams.financial_records_exist()`, which polls the
    `billing` and `payments` modules — and only payments had ever authored it.
    So an issued INVOICE armed no lock, and a tenant with a year of bills and no
    payments could re-denominate its books.

    Every backend test passed over it: the tenancy suite proves the refusal with
    a PAYMENT present, so the billing leg was never the one under test. That is
    hard-won law 2 — the guard was built, correct, and not wired to this half of
    the fact it guards.

    WHAT COUNTS AS A FINANCIAL RECORD HERE:

      · **ANY invoice, INCLUDING A DRAFT** (PO ruling 2026-08-12, OQ-181),
      · a credit note (GT-6 — a correction document a customer holds),
      · an adjustment (a posted movement against an account's balance).

    **DRAFTS COUNT — AND THIS FILE SHIPPED THE OPPOSITE ON 2026-08-11.** The
    original reasoning was that a draft is discarded and re-run as ordinary
    bill-run work, so locking a tenant's currency over one would refuse a
    legitimate setup change on the strength of a row the product is about to
    delete. That was a judgment rather than a rule, which is why it was raised
    as OQ-181 instead of being left as a silent choice, and the PO overturned it
    in one word: *"currency locked"*.

    The PO's reading is the stronger one. **A draft already carries amounts
    stamped `USD`.** If the currency moves under it, the run's own figures and
    the tenant's setting disagree until somebody notices and deletes the draft —
    and nothing in the product forces them to notice. A draft is not a plan to
    compute money; it is money already computed.

    `.exists()` on each, short-circuiting: the probe runs on the settings screen
    and must not scan tables that grow forever (payments' half says the same).
    """
    tenant_id = _tenant_id()
    if Invoice.objects.filter(tenant_id=tenant_id).exists():
        return True
    if CreditNote.objects.filter(tenant_id=tenant_id).exists():
        return True
    return Adjustment.objects.filter(tenant_id=tenant_id).exists()


#: BR-MET-132 — the run statuses that CONSUME a cycle period.
#:
#: ⚠ **THIS SET WAS `{"completed"}` AND MATCHED NOTHING, ON EVERY TENANT, FOR
#: EVER (amended 2026-09-15, `BR-BIL-1045` / `DEF-BIL-5352`).** No writer in
#: this product has ever written `completed`; the word was reasoned about at
#: length in this comment and put into the database by nobody, so the chase-days
#: chip never dropped a period a bill run had billed. It now names the words
#: `runs.record_run_outcome` actually writes.
#:
#: The omissions are the rule rather than an oversight, and the original
#: reasoning survives the rename intact:
#:
#:   · `draft` — nothing has been issued. A draft can be thrown away and
#:     re-prepared, and the reads it is missing still have to be chased, so a
#:     period with only a draft over it is NOT consumed.
#:   · `issuing` — mid-flight. Treating it as consumed would zero the chip in
#:     the seconds a run is most likely to need a human.
#:   · `abandoned` — no bill came out of it. This is the word the old comment
#:     reasoned about as `failed` / `cancelled`, and the argument is unchanged:
#:     a run that billed nobody leaves the period to be chased.
#:
#: `corrected` is in the set because a corrected run ISSUED and was then
#: restated — the reads it consumed were consumed, and a restatement does not
#: hand them back.
#:
#: The direction of the doubt is DEF-046's lesson restated: a chip that stays
#: loud one beat too long costs a clerk a glance, and a chip that goes quiet
#: early costs the utility a period nobody read. Loud is the safe error.
RUN_STATUSES_THAT_CONSUME_A_PERIOD: frozenset[str] = frozenset(
    {runs.RUN_STATUS_ISSUED, runs.RUN_STATUS_CORRECTED}
)


def period_consumed_by_run(cycle_id: Any, period_start: Any, period_end: Any) -> bool:
    """BR-MET-132's load-bearing phrase — *has a bill run consumed this period?*

    THE RULE, QUOTED RATHER THAN SUMMARISED (BR-MET-132, CONFIRMED, PO
    2026-08-26): *"Keep counting until the run consumes the period — those are
    the chase days"*; the S25 Missing chip *"counts missing required records
    for windows that are OPEN or CLOSED-BUT-UNBILLED, and drops a period only
    when its bill run has consumed it."*

    Metering owns the chip and cannot answer this: `bill_runs` is billing's
    table (B1), so billing publishes the predicate and
    `apps.metering.seams.period_consumed_by_run` resolves it late. Nothing is
    written and no invoice is read — this counts RUNS.

    **OVERLAP, NOT EQUALITY, AND THAT IS DELIBERATE.** A run's period is
    proposed from the cycle's own occurrence (`apps.metering.selectors.
    cycle_dict`'s `next_period`, straight off `period_engine.upcoming_windows`),
    so in the ordinary case the two are the same pair of dates. But the wizard
    lets a clerk widen it — a run over 1–31 Aug covers a 16–20 Aug reading
    window — and that run really did bill that window's reads. Keying on
    equality would leave the chip counting a period that has already gone out
    on a bill.

    Worked, on BR-MET-132's own case: CY-001's window is 16–20 Aug, the run is
    prepared for that period and completes on 25 Aug. Asked on **22 Aug** this
    answers **False** (no run has completed) and the chip counts the sixty
    unread meters; asked on **26 Aug** it answers **True** and the chip drops
    the period.
    """
    return BillRun.objects.filter(
        tenant_id=_tenant_id(),
        cycle_id=cycle_id,
        status__in=RUN_STATUSES_THAT_CONSUME_A_PERIOD,
        period_start__lte=period_end,
        period_end__gte=period_start,
    ).exists()


# ══════════════════════════════════════════════════════════════════════════
# DEF-079 — the three counters other modules' delete/edit guards ASK FOR and
# have been answered `0` for as long as those guards have existed
# ══════════════════════════════════════════════════════════════════════════
#
# Each of these is resolved BY NAME from another module's seam, each answer is
# consumed as a FACT by a guard that decides whether something may be deleted or
# edited, and each seam returned 0 while billing published nothing. The seams'
# own docstrings justified the 0 with "billing has no tables in W1" and "none of
# those tables exists yet" — true when written, false since W3, and nothing
# re-reads a sentence like that (hard-won law 1; DEF-075 is the same defect and
# G20 is the gate that found these).
#
# The sharpest is `plan_invoice_count`: `apps/rating/services.delete_plan`
# refuses a HARD DELETE unless "accounts = 0 AND never billed", asks billing the
# never-billed half, gets 0, and therefore lets a plan that HAS been billed be
# deleted together with its rate schedules and every charge, deposit, penalty
# and tax rule. `units.rate_plan_id` is on_delete=PROTECT so a plan LIVE on a
# unit is safe; a RETIRED one is not, and invoices deliberately snapshot rather
# than reference a plan, so nothing else refuses.


def plan_invoice_count(rate_plan_id: Any) -> int:
    """Invoice lines ever raised under any tariff this rate plan carries.

    THE ONLY LINK THAT EXISTS, and it is worth being precise about because the
    obvious one does not. An invoice does NOT name a rate plan: BR-BIL-030 locks
    what a bill priced into the bill itself, so nothing on `invoices` or
    `invoice_lines` points back at a plan. What a line DOES carry is
    `tariff_version_id` — a reviewed cross-module FK into rating — and a plan
    carries its tariffs through `plan_rate_schedules`. So the chain is:

        rate_plan → plan_rate_schedules.tariff_id → tariff_versions.tariff_id
                  → invoice_lines.tariff_version_id

    ⚠ THIS OVER-COUNTS WHEN TWO PLANS SHARE A TARIFF, DELIBERATELY. Nothing
    stops a tenant putting the same tariff in two plans, and a line priced under
    the other plan's copy of it would make this plan read as billed. The error
    therefore runs in ONE direction only: this can say "billed" when it was not,
    and can never say "never billed" when it was. For a guard whose false
    negative is the PERMANENT DELETION of a plan behind real bills, that is the
    safe direction, and it is a choice rather than an oversight — the exact
    reasoning `last_issued_invoice_period_end` records for including voided
    bills. Raised as OQ-185 so it can be overturned deliberately; the refusal
    names the tariff, so a clerk blocked by a shared tariff can see why.

    DRAFTS COUNT. A draft line was priced under this plan, and deleting the plan
    out from under a bill run in flight would leave the run unable to explain
    its own figures.
    """
    from apps.rating import models as rating_models

    tenant_id = _tenant_id()
    tariff_ids = rating_models.PlanRateSchedule.objects.filter(
        tenant_id=tenant_id, rate_plan_id=rate_plan_id
    ).values_list("tariff_id", flat=True)
    if not tariff_ids:
        return 0
    return InvoiceLine.objects.filter(
        tenant_id=tenant_id, tariff_version__tariff_id__in=list(tariff_ids)
    ).count()


def charge_line_count(charge_id: Any) -> int:
    """Invoice lines naming this charge code — BR-RAT-035's audit-lock half.

    While this answered 0, a charge code that appears on bills customers have
    already received stayed freely editable: rename it, or move its amount, and
    the S9 screen offers no warning. The bills themselves are safe — BR-BIL-010
    stamps the description and amount ONTO the line at issue, so history does
    not move under an edit — but the lock exists so a clerk is TOLD they are
    editing something in live use, and it has never once told anybody.

    Every status counts, drafts included: a draft line was priced with this
    code and is about to become a bill.
    """
    return InvoiceLine.objects.filter(tenant_id=_tenant_id(), charge_id=charge_id).count()


def charge_usage_last_month(charge_id: Any, today: date) -> dict[str, Any]:
    """`CR-156-BRC10` · CHG-01's tiles — what one charge code billed in the
    calendar month before `today`: bills, lines and the money on them.

    Counted over SENT bills only (`INVOICE_LOCKED_STATUSES` minus `void`): a
    draft has billed nobody and a voided bill was taken back. The month is the
    bill's ISSUE month, which is what *"bills last month"* means to a clerk.
    Two statements whatever the catalogue size (one aggregate, one distinct
    count folded into it).
    """
    first_this = today.replace(day=1)
    first_last = (first_this - timedelta(days=1)).replace(day=1)
    start = datetime.combine(first_last, time.min, tzinfo=timezone.utc)
    end = datetime.combine(first_this, time.min, tzinfo=timezone.utc)
    sent = [status for status in INVOICE_LOCKED_STATUSES if status != INVOICE_VOID]
    totals = InvoiceLine.objects.filter(
        tenant_id=_tenant_id(),
        charge_id=charge_id,
        invoice__status__in=sent,
        invoice__issued_at__gte=start,
        invoice__issued_at__lt=end,
    ).aggregate(
        lines=Count("id"),
        bills=Count("invoice_id", distinct=True),
        revenue=Coalesce(Sum("amount"), Decimal("0"), output_field=DecimalField()),
    )
    return {
        "bills": int(totals["bills"] or 0),
        "lines": int(totals["lines"] or 0),
        "revenue": totals["revenue"],
    }


def tariff_version_issued_bill_count(tariff_version_id: Any) -> int:
    """DEF-RAT-5715 — how many ISSUED bills this rate-schedule version priced.

    Rating asks this before it corrects a version, so the operator is told what
    the correction cannot reach: hard rule 4 locks a bill at issue, so a
    corrected price does not restate a bill already sent. A number is the
    difference between *"nobody has been billed on this yet"* and *"47 households
    have"*, and those two are the same screen with one figure changed.

    ⚠ **THE STAMP IS REAL, AND IT WAS READ BACK OFF A RUNNING TENANT RATHER THAN
    TAKEN FROM A DOCSTRING (2026-09-17, hard-won law 1).** `DEF-276` put
    `tariff_version_id` on every priced line and `backbill.py` says stage 6
    writes it — which is a comment, and a comment claiming a guarantee is not
    the guarantee. Measured on the seeded utility: **92 issued invoices, 732
    lines; 456/456 `usage` and 184/184 `base` lines carry a version id, 0
    orphans.** The 92 lines carrying none are `tax` lines, which are priced by a
    tax and not by a schedule — an absence that is correct. So this counts
    precisely rather than falling back on *"any issued bill overlapping the
    window"*, which would refuse corrections nobody needed to refuse.

    ⚠ **IT COUNTS INVOICES AND NOT LINES.** A tiered bill carries one line per
    block, so a line count would tell an operator that one month of one schedule
    reached three times as many customers as it did.

    DRAFTS ARE EXCLUDED, deliberately: a draft bill has reached nobody and the
    next run re-prices it from whatever the schedule says then, so counting one
    would overstate what a correction cannot undo.
    """
    return (
        InvoiceLine.objects.filter(
            tenant_id=_tenant_id(),
            tariff_version_id=tariff_version_id,
        )
        .exclude(invoice__status="draft")
        .values("invoice_id")
        .distinct()
        .count()
    )


def reason_code_used_by_count(code: str) -> int:
    """Adjustments and correction cases citing this reason code (BR-TEN-029).

    Tenancy hosts the reason-code list and billing owns what USES it, so
    BR-TEN-030 (a code freezes once used) and BR-TEN-034 (a used row cannot be
    deleted) are only as good as this count. At 0 they could not bite at all: a
    tenant could rename or delete a reason code that live adjustments name, and
    those adjustments would be left citing a code that no longer exists — on
    rows hard rule 4 forbids anyone from going back and fixing.

    BOTH TABLES, because BR-BIL-042 makes a correction case carry SEVERAL reason
    codes in a list rather than one column. A code used only on cases, and not
    yet on any adjustment, is still in use.
    """
    from apps.billing.correction_models import CorrectionCase

    tenant_id = _tenant_id()
    used = Adjustment.objects.filter(tenant_id=tenant_id, reason_code=code).count()
    # THE MEMBERSHIP TEST IS DONE IN PYTHON, DELIBERATELY. `reason_codes` is a
    # JSON list, and Django's `__contains` lookup on a JSONField RAISES
    # `NotSupportedError` on SQLite — the tier this whole suite runs on. A
    # database-side test would therefore work in production and blow up in every
    # developer's test run, which is DEF-064's lesson pointed the other way: a
    # query the test tier cannot execute is not covered by any test we run.
    # The scan is bounded by design — this product is scoped to utilities under
    # 3,000 connections (CLAUDE.md), the probe runs on a settings screen, and it
    # reads one column of one tenant's correction cases.
    used += sum(
        1
        for codes in CorrectionCase.objects.filter(tenant_id=tenant_id).values_list(
            "reason_codes", flat=True
        )
        if code in (codes or [])
    )
    return used


# ══════════════════════════════════════════════════════════════════════════
# S30 — the bills list and the bill detail (US-BIL-025 / US-BIL-026)
# ══════════════════════════════════════════════════════════════════════════

#: The US-BIL-025 capability row's sortable set, verbatim, and the one the
#: frontend declares as `INVOICE_SORTS`. `issue_date` is the KEY, `issued_at`
#: is the column — the screen's vocabulary and the schema's are allowed to
#: differ, and the mapping lives once, in `_ORDER_BY` below.
INVOICE_SORTS: tuple[str, ...] = ("invoice_no", "issue_date", "due_date", "total", "status")
INVOICE_DEFAULT_SORT = "issue_date"
#: IS-2 / the capability row: issue date **desc**. BE-05's parser defaults an
#: absent `dir` to asc, which on a 7,240-row list would put the OLDEST bill on
#: page 1 — so the screen's own default is applied here, in one place, rather
#: than being left to whichever caller remembers to send `dir=desc`.
INVOICE_DEFAULT_DIRECTION = "desc"

#: The US-BIL-025 filter set + 11b §2.6's account scope (the S21 Bills tab is
#: this same list with `f.account_id`). Matches the frontend's
#: `INVOICE_FILTERS` exactly; BE-05 ignores anything outside it (BR-SHL-011).
INVOICE_FILTERS: tuple[str, ...] = (
    "status",
    "bill_type",
    "cycle_id",
    "bill_run_id",
    "issued_from",
    "issued_to",
    "account_id",
)

#: The prototype's segment strip carries this beside the five stored statuses.
#: It is the one value the server must RESOLVE rather than match — and cannot.
PAST_DUE_SEGMENT = "past_due"

#: screen sort key -> (column, is_nullable). Nullable columns get an explicit
#: NULLS FIRST/LAST so the order is the same on PostgreSQL and on the sqlite
#: test tier: the two vendors disagree about where NULLs go, and a page-1 order
#: that changes with the database is a defect, not a detail (IS-2).
_ORDER_BY: dict[str, tuple[str, bool]] = {
    "invoice_no": ("invoice_no", True),
    "issue_date": ("issued_at", True),
    "due_date": ("due_date", True),
    "total": ("total", False),
    "status": ("status", False),
}


def _decimal_str(value: Decimal | None) -> str | None:
    """The NUMERIC(18,6) value as its exact decimal STRING ("247.870000").

    CLAUDE.md rule 2: money is never a float and never a number on the wire —
    it travels as the stored decimal beside its CHAR(3) currency, and nothing
    in this module parses, sums or re-rounds one. The quantize is the COLUMN's
    six places (DB-3 storage precision), not money rounding (that is B4's, at
    finalization/display).
    """
    if value is None:
        return None
    return str(Decimal(value).quantize(SIX_PLACES, rounding=ROUND_HALF_UP))


def _decimal_str_or_none(value: Any) -> str | None:
    """The same, for a figure that arrived from `bill_payload` as TEXT.

    A stamped money figure is stored as a STRING ("108.880000") — a Decimal in
    jsonb reads back a float and CLAUDE.md rule 2 forbids that — so it has to be
    re-entered as a Decimal before the column's own scale can be applied to it.

    **AN UNSTAMPED FIGURE STAYS None AND IS NEVER COERCED TO ZERO.** `""`, None
    and a value that will not parse all answer None, because BR-BIL-035 stamps
    NULLS when the arrears could not be read and *"0.00 would tell a customer in
    arrears that they are square"* (DEF-127 is what the other reading costs).
    """
    if value is None or value == "":
        return None
    try:
        return _decimal_str(Decimal(str(value)))
    except (ArithmeticError, ValueError):  # pragma: no cover — the stamp writes text money
        return None


def _is_uuid(value: Any) -> bool:
    try:
        UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _iso(value: Any) -> str | None:
    return value.isoformat() if value is not None else None


def _customer_name(account: Any) -> str | None:
    """The bill's customer, through customers' OWN published read (B1).

    REFUSES rather than answering None when customers has published no read:
    the screen renders a null as "no customer name recorded", which is a
    different statement from "the name could not be read" and is false whenever
    a contact exists. Hard-won law 2 — a missing seam must not degrade into a
    confident wrong answer.
    """
    read = _resolve("customers", "primary_contact_name")
    if read is None:
        raise errors.SysError(errors.SYS_INTERNAL, message_key="billing.customer_name_unavailable")
    return read(account)


def _cycle_name(run: Any) -> str | None:
    """`CR-105-BRC03` — the cycle a clerk would say out loud, else its code.

    Reads the SAME two columns, in the SAME order, as
    `issue._cycle_label_for` — which has stamped `bill_payload["cycle"]` since
    `DEF-2865`, and is why the printed bill already says *Silver Creek —
    monthly* where this screen said `CY-007`. Two answers to *which cycle* is
    the shape hard-won law 5 names; one fallback, written twice, is the price of
    the module boundary and is why this docstring points at the other copy.

    `None` on a run that belongs to no cycle at all — a one-time bill — which
    must print an absence rather than borrow a label.
    """
    if run is None or not run.cycle_id:
        return None
    for value in (run.cycle.name, run.cycle.code):
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _account_ids_by_customer_name(term: str) -> list[Any]:
    """IS-3's third search leg: the accounts whose CUSTOMER name matches.

    Customers' published `account_list` search is deliberately WIDER than this
    one (BR-CUS-053 also matches service address and meter #), so its rows are
    narrowed here to the ones whose `name` actually contains the term. Bills
    for an account that merely shares an address with the search term are not
    hits on "customer name", and returning them would silently redefine the
    capability row the screen shows.

    REFUSES if the read is unpublished, for the same reason `_customer_name`
    does: skipping the leg returns FEWER bills with a 200, and a clerk who
    searches "Miller" and sees nothing concludes Miller has no bills.
    """
    account_list = _resolve("customers", "account_list")
    if account_list is None:
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="billing.customer_name_search_unavailable"
        )
    needle = term.lower()
    return [
        row["id"]
        for row in account_list(ListParams(q=term))
        if needle in (row.get("name") or "").lower()
    ]


def list_params(query_params: Any) -> ListParams:
    """BR-SHL-011's params for this screen, with the capability row's defaults.

    Wrapped here rather than called straight from `api.py` so the vocabulary
    AND the ratified default direction live in one place. BE-05 has no notion
    of a default direction — `dir` absent means asc — and US-BIL-025's default
    is issue-date DESC, so an absent `dir` takes the screen's default and an
    explicit one is honoured verbatim.
    """
    params = parse_list_params(
        query_params,
        allowed_sorts=INVOICE_SORTS,
        default_sort=INVOICE_DEFAULT_SORT,
        allowed_filters=INVOICE_FILTERS,
    )
    if "dir" in query_params:
        return params
    return ListParams(
        q=params.q,
        sort=params.sort,
        dir=INVOICE_DEFAULT_DIRECTION,
        page=params.page,
        per=params.per,
        filters=params.filters,
    )


def invoice_queryset() -> QuerySet:
    """Every bill of the CURRENT tenant, and only those (hard rule 1).

    The explicit `tenant_id` filter keeps the law true on the sqlite unit tier,
    where there is no RLS to fall back on; on PostgreSQL the FORCE policy is
    the second, independent guarantee (tests/test_us_bil_025_026_bills_read.py
    proves that half under a non-superuser probe role).

    `select_related` travels only the REVIEWED cross-module FK set (B2 §2):
    `invoices.account_id → customers.Account` and `bill_runs.cycle_id →
    metering.Cycle`. A read along a reviewed edge, never a model import.
    """
    return Invoice.objects.filter(tenant_id=_tenant_id()).select_related(
        "account", "bill_run", "bill_run__cycle"
    )


#: ⚠ **THE STATES A BILL IS *ISSUED* IN, AND `draft` IS NOT ONE.** BR-BIL-004
#: makes a draft editable and BR-BIL-023 lets a re-run REPLACE it, so counting a
#: draft as billed would put money into a period that a re-run can take out
#: again. `corrected` and `void` ARE issued — they reached a customer, and a
#: correction is a NEW ROW rather than an edit (CLAUDE.md hard rule 4) — so
#: dropping them would make a closed period's figures move the day somebody
#: raises this year's correction.
ISSUED_INVOICE_STATES: tuple[str, ...] = (
    INVOICE_ISSUED,
    INVOICE_PAID,
    INVOICE_CORRECTED,
    INVOICE_VOID,
)


def invoices_issued_between(
    *, start: date, end: date, bill_type: str | None = None
) -> QuerySet:
    """The bills this tenant ISSUED inside a window — ONE derivation, two seams.

    `CR-142-BRC07` `P6.11` wave 3. Both `apps/payments/billing_seam.py` (for
    `BR-REP-009`'s collection numerator) and `apps/ledger/billing_seam.py` (for
    R43's REBILLS column) resolve THIS function rather than each composing the
    same filter, because two spellings of *what counts as issued* is how two
    reports start disagreeing about one period's revenue (hard-won law 5).

    ⚠ **THE WINDOW IS STRUCK ON `issued_at`'s DATE, NOT ON `service_date`.**
    *Issued* is the act BR-REP-009 dates its denominator by: a bill covering
    12 Aug – 11 Sep that goes out on 12 Sep belongs to September's issue and to
    August's service.

    ⚠ **IT RETURNS A QUERYSET AND MATERIALISES NOTHING.** A caller composes it
    into a subquery (`invoice_id__in=<this>.values("id")`), so a period holding
    forty thousand bills costs one statement rather than a forty-thousand-element
    `IN` clause assembled in Python.
    """
    rows = invoice_queryset().filter(
        status__in=ISSUED_INVOICE_STATES,
        issued_at__date__gte=start,
        issued_at__date__lte=end,
    )
    if bill_type:
        rows = rows.filter(bill_type=str(bill_type))
    return rows


def amount_due_for(invoice: Any) -> Decimal:
    """**WHAT THIS BILL ASKS THE CUSTOMER TO PAY** — PO ruling 2026-08-11.

    For an ordinary bill that is `invoice.total`, and always has been. For a
    BUDGET-BILLING bill it is the **LEVEL**, which is not the same number:
    ❄️ WE-8's July bill totals **292.87** and asks for **242.00**, and paying
    the 242 settles the month in full (PO verbatim, *"Level is due"*).

    THE DEFECT THIS EXISTS TO CLOSE. Every path that asks "does this customer
    owe anything?" reaches for `invoices.total`, so a budget customer paying
    exactly what the utility asked them for is $50.87 short every month: they
    age, they earn `max($5, 1.5% × 50.87)` = **$5.00** of late fee, and they
    enter the collection ladder. Nobody chose that; it is what the code does in
    the absence of this rule (DEF-062).

    READ FROM THE BILL'S OWN FROZEN PAYLOAD, never from today's budget status.
    BR-BIL-030 stamps the level that was in force when the bill was priced, so
    a re-level in January cannot change what a July bill asked for — the same
    reasoning that made the whole payload a snapshot. An issued bill's answer is
    therefore immutable along with the bill.

    A budget bill drafted before this lane shipped has no block and falls back
    to its total. That is stated rather than silently handled: it is the
    honest reading of a bill nobody computed a level for.
    """
    payload = getattr(invoice, "bill_payload", None) or {}
    block = payload.get("budget") if isinstance(payload, dict) else None
    if not isinstance(block, dict) or "amount_due" not in block:
        return invoice.total
    return Decimal(str(block["amount_due"]))


#: The money shape every figure below is measured in — CLAUDE.md rule 2. Four
#: decimals is what is WRITTEN; `NUMERIC(18,6)` is the lawful container these
#: columns already declare, and a cast that narrowed it here would round a
#: stored figure on the way past.
_MONEY = DecimalField(max_digits=18, decimal_places=6)


def amount_due_expression() -> Any:
    """`amount_due_for`, as SQL — **ONE rule, two renderings** (BR-BIL-072).

    ⚠ **THIS EXISTS SO THAT NOBODY ELSE RE-TYPES THE RULE, WHICH IS EXACTLY
    WHAT `DEF-2416` WAS.** The rule above — ❄️ *"Level is due"*, PO
    2026-08-11 — is read one bill at a time by a Python function, and every
    caller that wanted it for a WHOLE TENANT had to pull every open bill into
    Python to call it. `CR-138-BRC07` `P4.1` moves the debtor list's arithmetic
    into SQL, and the only two ways to do that are to publish this or to let
    payments write `bill_payload -> 'budget' ->> 'amount_due'` into its own
    file. The second is a second implementation of a signed finance figure,
    free to disagree with this one, in a module that does not own the rule.

    So it is published HERE, beside the function it mirrors, and
    `tests/test_cr138_p41_amount_due_expression.py` asserts the two agree bill
    by bill. **A change to either must move both or that test goes red, which
    is the point of it.** ⚠ That file runs on SQLite like the rest of the
    suite (hard-won law 14), so the agreement was also walked on real
    PostgreSQL 16 over a seeded tenant's whole open set on 2026-09-23 —
    **80,091 bills, 2,000 of them levelled, 0 disagreements.**

    ⚠ **THE ONE CASE WHERE THEY DIFFER, STATED RATHER THAN HIDDEN:** a payload
    whose `budget.amount_due` is JSON `null`. The Python form reaches
    `Decimal(str(None))` and raises; this returns the bill's total. That is a
    difference between an exception and an answer, not between two answers,
    and no bill in this product is written that way — `BR-BIL-030` stamps a
    number or omits the block.

    Money stays `NUMERIC` the whole way (CLAUDE.md rule 2). Nothing here casts
    to a float, and `->>` hands PostgreSQL text that is cast straight to
    numeric — never through a binary fraction.
    """
    return Coalesce(
        Cast(
            KeyTextTransform("amount_due", KeyTextTransform("budget", "bill_payload")),
            _MONEY,
        ),
        F("total"),
        output_field=_MONEY,
    )


def open_invoice_amounts_queryset(statuses: Sequence[str]) -> QuerySet:
    """Every OPEN bill of this tenant with what it ASKS FOR, as a queryset.

    The published read `apps/payments/billing_seam.py` composes the debtor list
    from (`CR-138-BRC07` `P4.1`). It is deliberately a QUERYSET and not a list:
    the caller adds its own joins, filters, ordering and page ON TOP, and the
    whole thing is cut in SQL.

    ⚠ **IT DOES NOT CALL `invoice_queryset`, AND THAT IS DELIBERATE RATHER
    THAN AN OVERSIGHT.** That read carries a `select_related` along the
    reviewed cross-module FK set for callers that RENDER a bill; this one is
    grouped and summed, so those joins would be three tables read per open
    bill of the tenant for columns nothing selects. What it DOES share is the
    filter that matters: the same explicit `tenant_id=_tenant_id()`, written
    out here rather than inherited, so hard rule 1 holds on the sqlite unit
    tier where there is no RLS to fall back on — and on PostgreSQL the FORCE
    policy is the second, independent guarantee, exactly as it is there.

    `statuses` is the CALLER's set, because what counts as open is the
    caller's question: `billing_seam.OPEN_INVOICE_STATUSES` is payments'
    answer for a debtor list, and the cutover comparison asks a different one.
    """
    return (
        Invoice.objects.filter(tenant_id=_tenant_id(), status__in=list(statuses))
        .annotate(amount_due=amount_due_expression())
        .values("id", "account_id", "due_date", "amount_due")
    )


def open_invoice_aging_queryset(statuses: Sequence[str]) -> QuerySet:
    """`open_invoice_amounts_queryset` PLUS the bill's currency — the AR ageing.

    `CR-136`-era `P2.21` composes A14's ageing table from this: one row per open
    bill, aged on ITS OWN due date, summed per account into five bands in SQL.

    ⚠ **IT CARRIES `currency` AND THAT IS THE WHOLE DIFFERENCE.** The debtor
    list beside it serves ONE tenant's balance and never prints a footer; the
    ageing's footer is a sum that is *not a number at all* when a tenant's open
    bills are denominated in more than one currency, so the read has to be able
    to say which currencies are present. A second read rather than a widened
    one: `open_invoice_amounts_queryset`'s `.values()` tuple is the contract
    `outstanding_positions_page` groups on, and adding a column to a grouped
    read to serve a different caller is how a `GROUP BY` quietly acquires a key.

    **The amount is `amount_due_expression()` and never `total`** — BR-BIL-072,
    ❄️ *"Level is due"*. There is exactly one statement of what a bill asks for
    and this is not a second one.
    """
    return (
        Invoice.objects.filter(tenant_id=_tenant_id(), status__in=list(statuses))
        .annotate(amount_due=amount_due_expression())
        .values("id", "account_id", "due_date", "amount_due", "currency")
    )


def invoice_ids_for_service(service_code: str) -> QuerySet:
    """The tenant's invoices carrying at least one line for this SERVICE, LAZY.

    p035's `f.service` criterion, whose values are the tenant's OWN eleven
    services (`GET /reference/services`) — `fire` included, which is why the
    predicate is the service's CODE and never a hardcoded list here (hard-won
    law 2: the front end typing the eleven out by hand is how the eleventh went
    missing on screen).

    ⚠ **LAZY, AND IT MUST STAY LAZY (`NFR-3`/`NFR-5`).** Handed to
    `Q(id__in=…)` unevaluated it renders as a nested subquery inside the
    ageing's own `WHERE`, so the filter costs no extra round trip and no
    parameter array. Materialising it would ship every invoice id of a
    40,000-account utility through Python to narrow a page of fifty.

    ⚠ **THIS READ SELECTS BILLS; IT NO LONGER DECIDES WHAT THE AGEING SHOWS
    FOR THEM (`CR-184-BRC10`, PO 2026-10-14, C1 → a).** This paragraph read
    *"A BILL IS NOT SPLIT BY SERVICE AND THIS FILTER DOES NOT PRETEND IT IS …
    pro-rating a receivable across the services on it — is a money rule
    nobody has ruled"* until the PO ruled it: what is still owed on a bill is
    shared across its services in proportion, inside the tenant's allocation
    class order. The ageing now narrows to these bills and then counts only
    the chosen services' SHARE of each (`apps/payments/receivables_by_service`
    does the sharing from `receivable_lines_for_invoices` below), so a mixed
    water-and-electric bill no longer shows its whole balance under *water*.
    """
    # OQ-306 (PO 2026-10-02, *"Allow several services at once"*): the filter
    # bar sends `water,sewer`, and a bill matches when it carries ANY of them.
    return (
        InvoiceLine.objects.filter(
            tenant_id=_tenant_id(), service__code__in=filter_values(service_code)
        )
        .values_list("invoice_id", flat=True)
        .distinct()
    )


def receivable_lines_for_invoices(invoice_ids: Any) -> QuerySet:
    """The priced LINES of the named bills — what receivables-by-service shares.

    `CR-184-BRC10`. Values: `invoice_id` · `service_code` · `service_name` ·
    `kind` · `amount`. Billing owns `invoice_lines`, so payments asks for
    these by name (`apps/payments/receivables_by_service`) rather than walking
    the table; it decides nothing about a line except where it is printed.

    `invoice_ids` may be a list or a LAZY queryset; tenant-scoped explicitly
    (hard rule 1) with RLS FORCE as the second guarantee. Money stays the
    column's `Decimal` (hard rule 2). The SERVICE is the line's own column —
    a tax line naming water is water's, a tax line naming none is nobody's,
    which is the ruling's *"never guessed onto a service"* at the source.
    """
    return (
        InvoiceLine.objects.filter(tenant_id=_tenant_id(), invoice_id__in=invoice_ids)
        .annotate(service_code=F("service__code"), service_name=F("service__name"))
        .values("invoice_id", "service_code", "service_name", "kind", "amount")
        .order_by()
    )


def _account_ids_at_address(term: str) -> Any:
    """`CR-089` `PUJ-53` — the accounts AT an address, as a LAZY queryset.

    ⚠ **THE ADDRESS IS NOT A BILLING COLUMN AND MUST NOT BECOME ONE.** Hard
    rule 8 keeps an address on `premises` and nowhere else; a bill reaches one
    by walking *bill → account → property*, and `g85_one_address_home.py` fails
    a fourth home. So this asks customers, which owns the account, and customers
    asks metering, which owns the property.

    ⚠ **LAZY, AND THAT IS THE DIFFERENCE FROM THE LEG ABOVE.**
    `_account_ids_by_customer_name` builds customers' whole `account_list` —
    every matching row, with its ledger, ageing and premise reads — and filters
    it in PYTHON. This hands `Q(account_id__in=…)` an unevaluated queryset,
    which Django renders as a nested subquery: the address leg adds **no round
    trip at all** and the page is still cut in SQL (`NFR-3`).

    REFUSES if the read is unpublished, for the same reason the name leg does:
    skipping it returns FEWER bills with a 200, and a clerk who searches a
    street and sees nothing concludes no bill was ever raised there.
    """
    read = _resolve("customers", "account_ids_at_matching_address")
    if read is None:  # pragma: no cover - customers publishes it
        raise errors.SysError(
            errors.SYS_INTERNAL, message_key="billing.address_search_unavailable"
        )
    return read(term)


def _apply_search(qs: QuerySet, term: str) -> QuerySet:
    """IS-3: bill #, account #, customer name, **address**. Nothing else — the
    capability row is the contract, and a fifth silent leg is a screen that lies
    about what it searched.

    ⚠ **THE ADDRESS LEG ARRIVED WITH `CR-089` `PUJ-53` AND IT WAS THE LARGEST
    OF THE FOUR GAPS THE PO NAMED.** A bill knows its account, the account knows
    its property, and until this line **no search crossed that**: typing *301
    Mill Pond Ln* returned NOTHING while eighteen bills stood against the six
    accounts at that building. The request had already paid for the join —
    the customer-name leg builds customers' address-aware `account_list` and
    throws its address matches away — so the gap cost a round trip to answer
    zero.
    """
    if len(term) < MIN_SEARCH_CHARS:
        return qs
    matches = Q(invoice_no__icontains=term) | Q(account__account_no__icontains=term)
    account_ids = _account_ids_by_customer_name(term)
    if account_ids:
        matches |= Q(account_id__in=account_ids)
    matches |= Q(account_id__in=_account_ids_at_address(term))
    return qs.filter(matches)


def _day_bounds(raw: Any) -> datetime | None:
    """An ISO date from a filter chip as an aware UTC midnight, or None.

    ⚠ REPORTED, not resolved: the boundary is UTC, not the tenant's clock.
    BR-TEN-020/043 make the tenant's timezone the one a date means something
    in, and a bill issued at 19:00 on Aug 8 in UTC-07:00 is an Aug 8 bill to
    the utility. Doing that properly needs tenancy's regional read wired into
    this filter; until it is, the window can be off by one day at its edges and
    that is stated rather than hidden. It affects a FILTER only — no stored
    value and no money figure is computed from it.
    """
    if not raw:
        return None
    try:
        parsed = date.fromisoformat(str(raw))
    except ValueError:
        return None  # BR-SHL-011: an unparseable filter value is ignored, never a 4xx
    return datetime.combine(parsed, time.min, tzinfo=timezone.utc)


def _apply_filters(qs: QuerySet, filters: dict[str, str]) -> QuerySet:
    status = (filters.get("status") or "").strip().lower()
    if status == PAST_DUE_SEGMENT:
        # See the module docstring: the only honest answer here is a refusal.
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref=PAST_DUE_UNAVAILABLE,
            message_key="billing.past_due_not_computable",
        )
    if status and status in INVOICE_STATUSES:
        qs = qs.filter(status=status)
    bill_type = (filters.get("bill_type") or "").strip().lower()
    if bill_type:
        qs = qs.filter(bill_type=bill_type)
    cycle_id = filters.get("cycle_id")
    if cycle_id and _is_uuid(cycle_id):
        qs = qs.filter(bill_run__cycle_id=cycle_id)
    bill_run_id = filters.get("bill_run_id")
    if bill_run_id and _is_uuid(bill_run_id):
        qs = qs.filter(bill_run_id=bill_run_id)
    account_id = filters.get("account_id")
    if account_id and _is_uuid(account_id):
        qs = qs.filter(account_id=account_id)
    issued_from = _day_bounds(filters.get("issued_from"))
    if issued_from is not None:
        qs = qs.filter(issued_at__gte=issued_from)
    issued_to = _day_bounds(filters.get("issued_to"))
    if issued_to is not None:
        # INCLUSIVE of the named day: a chip reading "to Aug 8" that dropped
        # every bill issued during Aug 8 would be read as a data gap.
        qs = qs.filter(issued_at__lt=issued_to + timedelta(days=1))
    return qs


def _apply_order(qs: QuerySet, params: ListParams) -> QuerySet:
    column, nullable = _ORDER_BY[params.sort if params.sort in _ORDER_BY else INVOICE_DEFAULT_SORT]
    descending = params.dir == "desc"
    expression = F(column)
    if descending:
        # NULLS FIRST on desc is not an accident: a DRAFT has no issue date and
        # a draft run is the newest thing on the screen (the S30 default view).
        ordered = expression.desc(nulls_first=True) if nullable else expression.desc()
    else:
        ordered = expression.asc(nulls_last=True) if nullable else expression.asc()
    return qs.order_by(ordered, "id")  # `id` is the stable tiebreak (IS-2)


def invoice_list_queryset(params: ListParams) -> QuerySet:
    """The S30 list, filtered/searched/ordered — paginated by the caller.

    Returns a QUERYSET rather than rows so BE-05 pages in the database: only
    the rows on screen are serialized, and a tenant with 7,240 bills does not
    build 7,240 dicts to show 50.
    """
    qs = _apply_search(invoice_queryset(), (params.q or "").strip())
    qs = _apply_filters(qs, params.filters)
    return _apply_order(qs, params)


def invoice_row(invoice: Invoice) -> dict[str, Any]:
    """One S30 row. Every key is `InvoiceRow` in the frontend's endpoints.ts."""
    run = invoice.bill_run
    return {
        "id": str(invoice.id),
        # BR-BIL-063 (PO 2026-08-11): allocated when the DRAFT is created, so a
        # draft HAS a number. Still nullable, because a row written under the
        # previous reading must still read back (see models.py).
        "invoice_no": invoice.invoice_no,
        "bill_type": invoice.bill_type,
        "status": invoice.status,
        # Served, never derived on the client — and NOT derivable here either.
        # See the module docstring: null is "unknown", not "not past due".
        "past_due": None,
        "account_id": str(invoice.account_id),
        "account_no": invoice.account.account_no,
        "customer_name": _customer_name(invoice.account),
        # `bill_runs.cycle_id` → metering, along the reviewed FK. Null in TWO
        # different situations and they are both real: a bill with no run at
        # all, and a bill from a ONE-TIME run (US-BIL-010..014), whose
        # `cycle_id` is NULL because a first/final/interim/back-bill/penalty
        # bill belongs to no cycle (migration 0021). `run.cycle_id` is tested
        # rather than `run.cycle`, so the null costs no query and cannot raise.
        "cycle_label": run.cycle.code if run is not None and run.cycle_id else None,
        # ⚠ **`CR-105-BRC03` — THE CYCLE BY NAME, BESIDE THE CODE AND NOT
        # INSTEAD OF IT.** The Billing blueprint's bill-detail redesign (p016,
        # annotation 4) reads *"The cycle, by name · the clerk's word for which
        # run was this · NEW (the id CY-001 stays under Origin)"*. `cycle_label`
        # above is the CODE and four screens already render it; changing what it
        # means would move all four on one screen's authority, so the name
        # arrives as its own field.
        #
        # **NAME, ELSE CODE, ELSE NULL — the same fallback `issue._cycle_label_
        # for` already stamps into `bill_payload["cycle"]`**, so the header and
        # the printed bill cannot name one cycle two ways. `Cycle.name` is
        # nullable (metering models) and an empty string is not a name.
        "cycle_name": _cycle_name(run),
        # `DEF-BIL-10068` (PO 2026-10-12) — a bill from a ONE-TIME run (no
        # cycle) is labelled *One-time bill*, never *Cycle bill*: an interim
        # bill is typed `cycle` on purpose (`one_time.BILL_TYPE_BY_KIND`), so
        # the type alone cannot say it. `run.cycle_id`, no query (as above).
        "one_time": run is not None and run.cycle_id is None,
        "bill_run_id": str(invoice.bill_run_id) if invoice.bill_run_id else None,
        "service_date": _iso(invoice.service_date),
        "period_start": _iso(invoice.period_start),
        "period_end": _iso(invoice.period_end),
        "issued_at": _iso(invoice.issued_at),
        # BR-BIL-024: derived AT ISSUE, never typed — a draft has none.
        "due_date": _iso(invoice.due_date),
        "subtotal": _decimal_str(invoice.subtotal),
        "tax_total": _decimal_str(invoice.tax_total),
        "total": _decimal_str(invoice.total),
        "currency": invoice.currency,
        # r10 #3 / BR-BIL-026: the pin. Null before issue.
        "template_version": invoice.template_version,
    }


#: A run that has SETTLED — nothing about it is still in flight.
#:
#: ⚠ **THIS SET WAS `{"completed", "cancelled"}` AND MATCHED NOTHING, WHICH IS
#: WHY THE LEDGER'S MONTH-END *"EVERY RUN FINISHED"* ITEM COULD NEVER GO GREEN
#: ON ANY TENANT (amended 2026-09-15, `BR-BIL-1045` / `DEF-BIL-5352`).**
#: `unissued_run_count` below EXCLUDES this set, so with nothing in the database
#: ever carrying either word, every run in every window counted as unfinished
#: for ever. The 2026-09-07 row that published this seam measured exactly the
#: symptom — three runs reading `draft · issuing · draft` — and read it as the
#: seam being unpublished rather than as the vocabulary being fictional. **A
#: constant is a claim about what some writer writes, and nothing re-checks it.**
#:
#: `RB-109` step 1's own words are *"issued or cancelled — nothing half-done"*
#: and they still govern: the set is the TERMINAL words, the three a run stops
#: on. `issued` and `corrected` are bills that went out; `abandoned` is a run
#: that ended having issued nothing and with nothing left to issue, which is a
#: deliberate end and is what the old comment meant by `cancelled`. `draft` and
#: `issuing` are in flight and are counted as OUTSTANDING on purpose — a month
#: closed over a half-issued run is a month whose bills nobody can account for.
SETTLED_RUN_STATUSES: frozenset[str] = frozenset(
    {runs.RUN_STATUS_ISSUED, runs.RUN_STATUS_CORRECTED, runs.RUN_STATUS_ABANDONED}
)


def unissued_run_count(start: date, end: date) -> int:
    """Bill runs of this window that are neither issued nor cancelled.

    ⚠ **THE LEDGER HAS BEEN ASKING FOR THIS BY EXACT SIGNATURE SINCE `US-LED-006`
    AND NOTHING ANSWERED IT.** `apps/ledger/close.py`'s `WANTED_READS` names
    `apps.billing.selectors.unissued_run_count(start, end) -> int` and its
    `_seam_item` resolves it by that name; with nothing published, the month-end
    checklist's *"every run finished"* item reported **UNKNOWN on every tenant,
    for ever**, and an unknown item counts as incomplete — so no utility could
    ever reach a fully green close. Measured on the seeded utility on
    2026-09-07: three bill runs, `draft` · `issuing` · `draft`, and the
    checklist could not say so.

    It is published here, in billing's own selectors, because the run is
    billing's row and `BR-TEN-013` forbids the ledger from reading this module's
    ORM. The ledger resolves the callable by name and this module owns what
    *finished* means (`SETTLED_RUN_STATUSES` above).

    **THE WINDOW IS THE RUN'S PERIOD, NOT ITS CREATION DATE**, and that is the
    load-bearing choice. A run created on 2 September for the August cycle
    belongs to August's close: dating it by `created_at` would let a clerk close
    August while August's own bills were still half-issued, which is the exact
    thing this item exists to stop. `period_start`/`period_end` are the run's
    declared cycle window, and a run OVERLAPPING the accounting month counts —
    containment would drop a cycle cut on the bank's dates rather than ours,
    for the same reason `unmatched_bank_line_count` takes overlap.

    **IT RETURNS AN `int` AND NEVER `None`.** The ledger's three-answer contract
    reserves `None` for *"I was asked and I cannot count this window"*, and this
    read always can: a tenant with no runs at all has zero unfinished runs,
    which is a measured fact and not an absence. That is the opposite posture
    from `unmatched_bank_line_count`, which genuinely cannot tell a real zero
    from an unasked bank — and the difference is that a bill run only exists
    because this product made it, so there is no outside world to be ignorant
    of.
    """
    return (
        BillRun.objects.filter(tenant_id=_tenant_id())
        .filter(period_start__lte=end, period_end__gte=start)
        .exclude(status__in=SETTLED_RUN_STATUSES)
        .count()
    )


def unfinished_runs(start: date, end: date) -> tuple[dict[str, Any], ...]:
    """The same runs `unissued_run_count` counts, each named so a clerk can act.

    ⚠ **A COUNT IS NOT A FIX ROUTE** (`BR-RBS-011`). The ledger's checklist
    needs an integer and says so; a runbook has to put a row on a screen with
    the run's own number and its state, because *"3 runs unfinished"* with no
    way to reach them is a finding a clerk cannot act on.

    `run_no` is the HUMAN-facing number (`RUN-0814`) and is NULL for a run that
    predates the series — B14 rule 31 forbids showing the uuid instead, so a
    numberless run is described by its period, which is what a clerk would have
    called it before the series existed.
    """
    return tuple(
        {
            "run_no": row["run_no"],
            "status": row["status"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
        }
        for row in BillRun.objects.filter(tenant_id=_tenant_id())
        .filter(period_start__lte=end, period_end__gte=start)
        .exclude(status__in=SETTLED_RUN_STATUSES)
        .order_by("period_start", "run_no", "id")
        .values("run_no", "status", "period_start", "period_end")
    )


def invoices_rollup() -> dict[str, Any]:
    """The S30 header roll-up. A null member means NOT COMPUTED, never zero.

    Over ALL of the tenant's bills, not the current filter — "7,240 bills
    lifetime" is the prototype's own wording, and the same posture
    `GET /accounts` takes with its roll-up.

    `unresolved_from_last_run` is billing's own `bill_run_exclusions` for the
    most recently created run, unresolved (`resolved_at IS NULL`) — the queue
    BR-BIL-015 defines, counted for the run the header names. It is null when
    the tenant has never run a bill run, because "0 unresolved" and "there has
    never been a run" are different facts. The two MONEY members are null and
    say why in the module docstring.
    """
    tenant_id = _tenant_id()
    last_run = (
        BillRun.objects.filter(tenant_id=tenant_id).order_by("-created_at", "-id").values("id")
    ).first()
    unresolved = (
        None
        if last_run is None
        else BillRunExclusion.objects.filter(
            tenant_id=tenant_id, bill_run_id=last_run["id"], resolved_at__isnull=True
        ).count()
    )
    return {
        "bills": invoice_queryset().count(),
        "billed_this_cycle": None,
        "billed_currency": None,
        "unresolved_from_last_run": unresolved,
    }


def invoice_or_404(invoice_id: Any) -> Invoice:
    """A cross-tenant id is indistinguishable from an absent one (HR-1 / G4).

    The malformed-id case takes the same door on purpose: answering 422 for a
    bad uuid and 404 for a good one that belongs to someone else would let a
    caller tell the two apart.
    """
    if not _is_uuid(invoice_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = invoice_queryset().filter(pk=invoice_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


def _labels_for_lines(
    lines: Any,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """`({gl id: {code, name}}, {tariff version id: label})` for a bill's lines.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-937 — TWO COLUMNS PRINTED RAW DATABASE KEYS AT A UTILITY CLERK  ║
    ╚══════════════════════════════════════════════════════════════════════╝
    On the live deployment at v2.61.1 the bill's Charges tab showed ACCOUNTING
    CODE as `01a01d99-d995-7127-aad8-faace1cba6e2` on every line and RATE
    VERSION as another uuid — under the column's own footnote promising *"the
    accounting code … recorded when the bill was issued"*. A clerk cannot check
    a uuid against a chart of accounts, so the promise was unkeepable. DEF-206
    is the standing rule and it is one sentence: never print the raw key at a
    person.

    **BOTH NULLS WERE COMMENTS THAT HAD STOPPED BEING TRUE** (hard-won law 1).
    `gl_account_code` said *"`ledger_accounts` is W5"*; W5 landed and
    `apps.ledger.models.LedgerAccount` has carried `code` and `name` since.
    `tariff_version_label` said rating stores *"no column an ordinal 'v3' could
    honestly be read from"* — still true, and it does not follow that there is
    nothing honest to print: a `tariff_versions` row carries the SCHEDULE it
    belongs to and the DATE it took effect, which is precisely how BR-RAT-007
    identifies which version priced a bill.

    **ASKED ONCE PER BILL, NOT ONCE PER LINE.** A six-line bill would otherwise
    make twelve extra queries to render one table.

    **RESOLVED LIVE, AND THE STAMP IS STILL THE AUTHORITY.** The ids on the row
    are frozen (BR-BIL-010 / DEF-276) and nothing here re-resolves which account
    or which version a line used — this only asks what those two rows are
    CALLED, today, in the chart and the schedule list a clerk has open. A
    renamed account therefore shows its new name beside an old bill, which is
    what makes it findable. An id whose row has been deleted is simply absent
    and the caller falls back to the id (see `invoice_line_row`), because a
    stamped id with no label is still better than a blank in a column headed
    ACCOUNTING CODE.
    """
    gl_ids = {str(line.gl_account_id) for line in lines if line.gl_account_id}
    version_ids = {str(line.tariff_version_id) for line in lines if line.tariff_version_id}
    gl_labels = _resolve("ledger", "account_labels")
    version_labels = _resolve("rating", "tariff_version_labels")
    return (
        gl_labels(gl_ids) if callable(gl_labels) and gl_ids else {},
        version_labels(version_ids) if callable(version_labels) and version_ids else {},
        _tax_authority_labels(lines),
        _charge_labels(lines),
    )


def _tax_authority_labels(lines: Any) -> dict[str, str]:
    """`{tax id: "State of Texas"}` for the tax lines of ONE bill — CR-053 task 7.

    **WHY A LABEL AND NOT THE `tax_id` ALONE.** BR-BIL-069 put `invoice_lines.
    tax_id` on the row so a tax line could say WHOSE tax it is, and the payload
    then served neither the id nor the name: a Charges tab could show
    `kind='tax'`, a wording and an amount, and nothing else. On the reference
    bill the single `$8.30` is really three authorities — State of Texas 6.25%
    = $6.29, Harris County 1.00% = $1.01, City of Katy 1.00% = $1.00 — which is
    three debts and three returns to file. DEF-206's standing rule is that the
    raw key is never printed at a person, so the id travels WITH its label
    rather than instead of it.

    **THE READ IS RATING'S AND ALREADY EXISTED.** `rating.selectors.
    tax_authority_label_for_tax` was published on 2026-08-12 for the PO's
    OQ-146 closure (*"let the run report it"*) and resolves three sources most
    specific first — the jurisdiction's `authority`, then its `name`, then the
    tax's own name. It is reached through the seam (`_resolve`, getattr at call
    time) so no import binds billing to rating (B1/BR-TEN-013, gate G6), and it
    is the SAME function `apps/billing/issue._authority_label` uses for its
    refusal message. One definition of "whose tax this is", not two.

    **ASKED ONCE PER DISTINCT TAX, NOT ONCE PER LINE**, the discipline
    `_labels_for_lines` already sets. A bill carries a handful of tax lines and
    usually fewer authorities.

    **A LABEL, NEVER A KEY** — the read's own docstring says so and it governs
    here too: nothing may map, post or stamp on this string. The money-bearing
    read is `liability_gl_account_id_for_tax`, keyed on the id, and matching a
    tax by its DESCRIPTION was option D of OQ-116 and the PO declined it.

    An id that resolves to nothing — a tax deleted since the bill issued, or
    another tenant's (the read is tenant-scoped, HR-1) — is simply absent, and
    the caller falls back to serving the id with a null label. A stamped id
    with no name is still better than a blank in a column headed AUTHORITY.
    """
    read = _resolve("rating", "tax_authority_label_for_tax")
    if not callable(read):
        return {}
    labels: dict[str, str] = {}
    for tax_id in {str(line.tax_id) for line in lines if line.tax_id}:
        label = read(tax_id)
        if label:
            labels[tax_id] = label
    return labels


def _charge_labels(lines: Any) -> dict[str, dict[str, str]]:
    """`{charge id: {"code": "RECON", "name": "Reconnection fee"}}` — CR-053 task 7.

    ⚠ **THIS RETURNS `{}` TODAY, AND THAT IS A NAMED ABSENCE RATHER THAN AN
    OVERSIGHT — see DEF-2428.** `invoice_lines.charge_id` is real and is
    written (`stages/assemble_document`, DEF-714), so the ID below is served
    and is correct. What does not exist is a read in RATING that turns charge
    ids into their codes: `charge_by_code` goes the other way, `charge_or_404`
    raises rather than answering, and neither is a label map. Billing may not
    query `rating.charges` itself — the catalog has ONE home and a second
    reader inside billing is how a renamed code starts disagreeing with S13.

    So this takes exactly the posture `gl_account_code` and
    `tariff_version_label` took before `ledger.account_labels` and
    `rating.tariff_version_labels` were published: the seam is called BY NAME,
    the key is served under its contracted name as `None`, and the day rating
    publishes `charge_labels(charge_ids)` every fee line starts naming its code
    with no edit here. `api.py`'s own exception list has carried that same
    stated-absence for those two keys since 2026-08-11.
    """
    read = _resolve("rating", "charge_labels")
    charge_ids = {str(line.charge_id) for line in lines if line.charge_id}
    if not callable(read) or not charge_ids:
        return {}
    return read(charge_ids) or {}


def invoice_line_row(
    line: InvoiceLine,
    *,
    gl_labels: dict[str, Any] | None = None,
    version_labels: dict[str, Any] | None = None,
    tax_labels: dict[str, Any] | None = None,
    charge_labels: dict[str, Any] | None = None,
    asset_labels: dict[str, str] | None = None,
) -> dict[str, Any]:
    """One `invoice_lines` row as US-BIL-007 §5 maps it.

    `unit` rides with `quantity` verbatim from the column (CLAUDE.md rule 3 —
    stage 6 refuses to write a quantity without one), and `gl_account_id` is
    the STAMP (BR-BIL-010): issue-time truth, read back, never re-resolved
    against today's mapping.

    `gl_account_code` and `tariff_version_label` are the READABLE halves of
    those two stamps, resolved by `_labels_for_lines` — see DEF-937 there. Both
    stay `None` when the label maps are not supplied (this function is called
    with a bare line from a handful of places) or when the id names a row that
    no longer exists; the contract's shape is unchanged and the client already
    falls back to the id in both cases.

    **CR-053 TASK 7 ADDS THE SAME PAIRING FOR TWO MORE STAMPS** — `tax_id` +
    `tax_authority` (BR-BIL-069) and `charge_id` + `charge_code`/`charge_name`
    (BR-BIL-010). Identical posture and identical failure mode: the ID is the
    stored fact and is always served, the LABEL is resolved live through the
    seam and is null when nobody can answer. `tax_authority` answers today;
    `charge_code` does not, and DEF-2428 says why.
    """
    gl_id = str(line.gl_account_id) if line.gl_account_id else None
    version_id = str(line.tariff_version_id) if line.tariff_version_id else None
    gl = (gl_labels or {}).get(gl_id) if gl_id else None
    tax_id = str(line.tax_id) if line.tax_id else None
    charge_id = str(line.charge_id) if line.charge_id else None
    charge = (charge_labels or {}).get(charge_id) if charge_id else None
    return {
        "id": str(line.id),
        "kind": line.kind,
        "description": line.description,
        "quantity": _decimal_str(line.quantity),
        "unit": line.unit,
        "unit_price": _decimal_str(line.unit_price),
        "amount": _decimal_str(line.amount),
        "taxable": line.taxable,
        "gl_account_id": gl_id,
        "gl_account_code": (gl or {}).get("code"),
        # NEW KEY (DEF-937). `gl_account_code` alone is "4110" — a number a
        # clerk still has to look up. The Settings accounting tab has rendered
        # `${code} — ${name}` since it was built; the bill now carries the same
        # two facts so the screens can agree.
        "gl_account_name": (gl or {}).get("name"),
        "tariff_version_id": version_id,
        "tariff_version_label": (version_labels or {}).get(version_id) if version_id else None,
        "service": line.service.code if line.service_id else None,
        # ── CR-053 task 7 — THE TWO STAMPS THE PAYLOAD NEVER CARRIED ────────
        # Both columns are real, both are WRITTEN, and neither reached the
        # Charges tab: the CR's own audit calls this the cheap half — *"a field
        # that exists and is not serialized"* — against the expensive half a
        # figure nothing computes. Serialization only; nothing here computes,
        # re-resolves or re-prices anything.
        #
        # `tax_id` is BR-BIL-069's *"whose tax this line is"*, the PO's OQ-116
        # closure (*"For each atheority have separate account and tagging"*).
        # `charge_id` is BR-BIL-010's fee key, given its writer by DEF-714.
        # Both are NULL on every line that is not a tax / not a fee, and that
        # absence is by construction rather than a gap: `assemble_document`
        # stamps a tax with its authority and a fee with its code, and a usage
        # line has neither.
        "tax_id": tax_id,
        "tax_authority": (tax_labels or {}).get(tax_id) if tax_id else None,
        "charge_id": charge_id,
        # ⚠ NULL UNTIL RATING PUBLISHES `charge_labels` — DEF-2428, and the id
        # above is served meanwhile so the absence is visible rather than
        # invented. See `_charge_labels`.
        "charge_code": (charge or {}).get("code"),
        "charge_name": (charge or {}).get("name"),
        "period_start": _iso(line.period_start),
        "period_end": _iso(line.period_end),
        # `DEF-BIL-8315` — WHICH METER this line was priced for: the stored id
        # (`billing/0031`) and the meter's NUMBER beside it, so a bill with two
        # water meters says whose line is whose. Both null on a line priced for
        # no meter, which is every line before 2026-09-30.
        "asset_id": str(line.asset_id) if line.asset_id else None,
        "asset_label": (asset_labels or {}).get(str(line.asset_id)) if line.asset_id else None,
        # PO 2026-10-01 — the chain this line was priced from, as stored at
        # draft (`billing/0039`): base code, plan, version, customer type and
        # per size the count, base each and price each. Null on every line
        # written before it, and on tax and fee lines.
        "pricing_trace": getattr(line, "pricing_trace", None),
        # `DEF-BIL-8744` — the days a line's amount was cut down by
        # (`{"days": 19, "of": 30}`), read off that trace, so the Charges tab
        # prints *6 kW · $14.0000 · 19/30 days · $53.20* and it foots. Null on
        # every line that foots as quantity × rate. Display only.
        "day_share": day_share.of_stored_line(line),
    }


#: BR-BIL-035's block inside `bill_payload`, and the three figures it stamps.
#: Named as constants because `apps/billing/issue._stamp_balance_forward` writes
#: them and this reads them: one spelling for a contract that crosses two files,
#: the discipline `apps/ledger/reporting.REMITTING_BASIS_KEY` sets.
BALANCE_FORWARD_KEY = "balance_forward"
BALANCE_FORWARD_FIGURES = ("previous_balance", "payments_credits", "total_due")


def _balance_forward_block(invoice: Invoice) -> dict[str, Any]:
    """BR-BIL-035's stamped arrears, off the bill's own frozen payload.

    READ, never recomputed and never queried live. BR-BIL-030 freezes the
    payload at issue so *"a reprint shows the arrears as they stood on the bill
    date, never as they stand today"* — a live query here would show a customer
    money received AFTER the bill was sent, on a document that is immutable.

    The block is the authority; the three top-level keys the stamp also writes
    are the fallback for a bill stamped by an older shape. Both come from one
    dict at write time, so they cannot disagree.
    """
    payload = getattr(invoice, "bill_payload", None) or {}
    if not isinstance(payload, dict):  # pragma: no cover — jsonb holds an object
        return {}
    block = payload.get(BALANCE_FORWARD_KEY)
    if isinstance(block, dict):
        return block
    return {key: payload.get(key) for key in BALANCE_FORWARD_FIGURES}


def _summary_for(invoice: Invoice) -> dict[str, Any]:
    """A19 / US-BIL-026 §7: previous balance − payments/credits + current
    charges = total due. WE-1 works it as `45.00 − 0.00 + 247.87 = 292.87`.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  DEF-127 — THE BILL THAT COULD NOT STATE ITS OWN TOTAL DUE           ║
    ╚══════════════════════════════════════════════════════════════════════╝
    ⚠ **THIS DOCSTRING USED TO SAY "this module never opens the payload — so
    they are null".** That was written while nothing stamped the figures. Since
    2026-08-15 `apps/billing/issue._stamp_balance_forward` writes them into
    `bill_payload` inside the issue transaction (BR-BIL-035, DEF-116) — and this
    read went on answering `previous_balance null · payments_credits null ·
    total_due null` off a payload that was carrying **108.880000**, so the S30
    bill screen printed an em-dash where TOTAL DUE belongs on a bill that knew
    exactly what it was asking for. The renderer
    (`apps/billing/documents._summary`) had already been wired to the stamp; the
    API had not, and the API is what a human looks at.

    **THE STAMP IS THE ONLY SOURCE. NOTHING HERE ADDS THE THREE UP.** The
    arithmetic is BR-BIL-035's and it was performed once, at issue, over the
    account's still-open earlier bills; recomputing it on read would be a second
    implementation of signed money law living in a read model, and it would
    quietly restate an immutable document every time a payment landed.

    **A BILL WITH NO STAMP STILL ANSWERS NULL, AND THAT IS THE POINT.** Two
    real cases reach it: a draft, which has not been stamped because the stamp
    happens at issue; and an issued bill whose payments seam was unreachable, in
    which case the stamp wrote NULLS rather than zeros on purpose — *"0.00 would
    tell a customer in arrears that they are square"*. The screen shows its
    awaiting state and the run reported the bill by name (OQ-117, PO
    2026-08-12, *"issue and report it"*). Never a total assembled from nulls
    read as zero.

    **OQ-217 IS NOT ANSWERED HERE AND MUST NOT BE** (it was ANSWERED by the PO on
    2026-10-01 — the whole account since the last bill, `whole_account_since_last_bill`,
    BR-BIL-1065 — and answered in `issue.py`, not here). Which window the two middle
    figures were read over is the bill's own stamped `basis`, served below so a
    reader can tell which definition their bill was written under without dating
    the code that wrote it. The build ships
    `open_prior_bills_and_migrated_opening_at_issue` — it read
    `open_prior_bills_at_issue` until 2026-08-27, when BR-BIL-160 (PO ruling,
    OQ-530) added the account's MIGRATED opening balance to the first operand
    and what has been paid against it to the second. `total_due` is identical
    under either window, so nothing this serves is at risk from the ruling.
    """
    block = _balance_forward_block(invoice)
    return {
        "previous_balance": _decimal_str_or_none(block.get("previous_balance")),
        "payments_credits": _decimal_str_or_none(block.get("payments_credits")),
        "current_charges": _decimal_str(invoice.total),
        "total_due": _decimal_str_or_none(block.get("total_due")),
        # DEF-099 / CLAUDE.md rule 2 — the CHAR(3) these four figures are in.
        # The bill's own currency is frozen with it, so the stamped code and the
        # column agree by construction; the column is served because it is the
        # one that cannot be absent.
        "currency": invoice.currency,
        # BR-BIL-035's window (OQ-217, ruled 2026-10-01), stamped as a VALUE on the bill.
        # Null on a bill stamped before the basis was recorded — which is a fact
        # about that bill, not a default to fill in.
        "basis": block.get("basis"),
        "basis_oq": block.get("basis_oq"),
        # PO ruling 2026-08-11 (*"Level is due"*, OQ-140 CLOSED) — WHAT THIS BILL
        # ASKS FOR, which is the total on every ordinary bill and the LEVEL on a
        # budget one. Served rather than derived on the client for the reason
        # `past_due` is: a client that computed it from `current_charges` would
        # ask a budget customer for 292.87 when the utility asked for 242.
        # NOT null, unlike its three neighbours, because this one IS answerable
        # from the bill's own frozen payload.
        "amount_due": _decimal_str(amount_due_for(invoice)),
    }


def _integrity_for(invoice: Invoice) -> dict[str, Any]:
    """US-BIL-030's two terminal-stage guarantees, ANSWERED FOR ONE BILL.

    **WHY THIS EXISTS AND WHY IT IS NOT DECORATION.** BR-BIL-032 says the
    stamped instance ties out to its rows and that *"drift can never be
    silent"*. `pipeline.tie_out_document` and `pipeline.balanced_handoff`
    compute exactly that — and on 2026-08-16 a repo-wide search found **no
    caller for either outside their own test file**. So the rule was enforced
    on fixtures and on nothing else: every bill in the product could carry a
    payload saying one number and rows saying another, each internally
    consistent, and nobody would learn of it until a customer disputed a bill.
    That is DEF-112's shape applied to a guarantee rather than to a screen.

    **IT NEVER RAISES.** `refuse_untied_document` and the posting seam raise, by
    design — they gate an issue. This is a READ on a screen a clerk already has
    open, and a detail endpoint that 500s on a drifted bill would hide the one
    bill somebody needs to look at. So a failure becomes a stated `false` with
    the delta, and a figure that cannot be computed becomes `null` with a
    reason.

    **`None` IS NOT `false`.** A draft has no stamped payload and no GL stamps
    (both are written at issue), so neither question can be asked of it — that
    is `null` plus a reason, never "this bill does not tie out", which is an
    accusation.

    Every money figure travels with the bill's own CHAR(3) (CLAUDE.md rule 2)
    and nothing here rounds, sums or re-derives one: the two figures compared
    are `bill_payload.total` and `invoices.total`, both already final.
    """
    from apps.billing import pipeline

    currency = invoice.currency
    block: dict[str, Any] = {
        "currency": currency,
        "document_ties_out": None,
        "payload_total": None,
        "rows_total": _decimal_str(invoice.total),
        "payload_line_count": None,
        "row_line_count": None,
        "posting_balanced": None,
        "ar_total": None,
        "unavailable": [],
    }

    if invoice.bill_payload is None:
        block["unavailable"].append(
            {
                "field": "document_ties_out",
                "br_ref": "BR-BIL-032 · BR-BIL-030",
                "why": "this bill carries no stamped document instance, so there is nothing "
                "to reconcile against its rows. The instance is stamped at draft with the "
                "rest of the payload, so a bill without one has not been through stage 6.",
            }
        )
    else:
        tie = pipeline.tie_out_document(invoice)
        block.update(
            document_ties_out=tie.ties_out,
            payload_total=_decimal_str(tie.payload_total),
            payload_line_count=tie.payload_line_count,
            row_line_count=tie.row_line_count,
        )
        if tie.line_count_unavailable:
            # DEF-969. A bill stamped before `assemble_document` began writing a
            # line set can have its TOTAL reconciled and not its line count, and
            # those are two different answers. Serving `false` said *"these do
            # not match"* about a bill whose figures agreed to the cent, on all
            # 47 bills of the live deployment — which is how a check that
            # matters gets scrolled past. The verdict above answers what CAN be
            # asked; the gap is stated here, beside `posting_balanced`'s, and
            # the screen renders it as NOT CHECKED with this reason.
            block["unavailable"].append(
                {
                    "field": "payload_line_count",
                    "br_ref": "BR-BIL-032 · BR-BIL-030",
                    "why": "this bill's saved copy was stamped before the charge lines "
                    "were recorded in it, so its total could be checked against the "
                    "charge lines and its line COUNT could not. The saved copy is "
                    "locked at issue and cannot be added to (hard rule 4), so this "
                    "stays true of this bill forever; bills issued from 2026-08-27 "
                    "carry the line set and are checked on both.",
                }
            )

    try:
        handoff = pipeline.balanced_handoff(invoice)
    except Exception as unanswerable:  # noqa: BLE001 — a READ never raises; see docstring
        block["unavailable"].append(
            {
                "field": "posting_balanced",
                "br_ref": "BR-BIL-011 · CLAUDE.md rule 5",
                "why": str(unanswerable),
            }
        )
    else:
        block.update(
            posting_balanced=handoff.balanced,
            ar_total=_decimal_str(handoff.ar_total),
        )
    return block


def _deliveries_for(invoice: Invoice) -> list[dict[str, Any]] | None:
    """The delivery columns S30 draws, or `None` when nobody can say.

    The seam answers notifications' own full queue row; this narrows it to what
    the panel renders. Narrowing here rather than in the seam keeps the queue's
    vocabulary in one module: a seam that reshaped rows would be a second place
    for it to drift.

    `at` is `queued_at`, deliberately, and the label on the screen says so.
    Nothing in R2 sends — no dispatcher (US-NOT-002), no provider adapter
    (US-NOT-003) — so every row's `sent_at` is null on every bill, and a column
    fed from it would read as a delivery that failed rather than one that has
    not been attempted because attempting is not built.

    ⚠ **`returned_at` AND `held` JOINED THE FOUR ON 2026-08-16 (US-PAY-016).**
    Marking a piece of post returned is a per-DELIVERY-ROW act — BR-PAY-018's
    own words are *"a delivery record marked returned"* — and S30's delivery
    rows are the screen the story names for the single mark. A panel that could
    not say WHICH rows had already come back would offer the action on all of
    them, and a clerk working a stack of fourteen would have no way to tell the
    two they marked this morning from the twelve they have not. Both are
    already on notifications' queue row; nothing new is computed here.

    `held` rides with it because it is the OTHER half of the same rule
    (BR-NOT-005: suppression holds the queue row, never deletes it). Its writer
    is the dispatcher lane's and does not exist yet — every row reads `false`
    today — so no screen may present it as proof that anything was suppressed;
    it is served so the panel can state a hold when one finally appears rather
    than needing a schema change to notice.
    """
    rows = delivery_seam.deliveries_for_bill(invoice.pk)
    if rows is None:
        return None
    return [
        {
            "id": str(row.get("id")),
            "channel": row.get("channel"),
            "status": row.get("status"),
            "at": row.get("queued_at"),
            "returned_at": row.get("returned_at"),
            "held": bool(row.get("held")),
        }
        for row in rows
    ]


def _line_rows(lines: Any, *, labels: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
    """A bill's charge lines, with their four stamps rendered readable.

    `labels` lets a caller that has ALREADY resolved the four maps hand them in
    rather than paying for them twice. `invoice_detail` does exactly that, so
    the tax-authority map behind `taxes_by_authority` and the one behind these
    rows are the same object — a bill cannot name an authority one way in its
    line table and another way in its per-authority subtotal. Omitted, this
    resolves them itself and every other caller is unchanged.

    The label maps are resolved ONCE here and handed to every row (DEF-937), so
    a six-line bill costs a handful of extra queries rather than one per line
    per stamp.

    ⚠ **THIS SAID "their TWO stamps … two extra queries" UNTIL CR-053 TASK 7**,
    which added the tax authority and the charge code beside the GL account and
    the rate version. Corrected rather than left standing — a count in a
    docstring that quietly stops matching the code is how the next reader
    budgets the wrong number of queries.

    The tax map costs one query PER DISTINCT AUTHORITY rather than one for the
    set, because `rating.tax_authority_label_for_tax` takes a single id — a
    bill carries a handful of tax lines and usually fewer authorities, so this
    is bounded and small, and it is named here rather than hidden.
    """
    rows = list(lines)
    gl_labels, version_labels, tax_labels, charge_labels = labels or _labels_for_lines(rows)
    # `DEF-BIL-8315` — the meter numbers, in ONE read for the whole bill.
    read_numbers = _resolve("metering", "asset_numbers")
    asset_ids = {str(line.asset_id) for line in rows if getattr(line, "asset_id", None)}
    asset_labels = read_numbers(asset_ids) if callable(read_numbers) and asset_ids else {}
    return [
        invoice_line_row(
            line,
            gl_labels=gl_labels,
            version_labels=version_labels,
            tax_labels=tax_labels,
            charge_labels=charge_labels,
            asset_labels=asset_labels,
        )
        for line in rows
    ]


# ══════════════════════════════════════════════════════════════════════════
# CR-053 TASK 9 — PER-SERVICE SUBTOTALS
# 🔒 MONEY PATH · HUMAN-REVIEW-PENDING (12-governance/09-human-review-ledger.md)
# ══════════════════════════════════════════════════════════════════════════
#: The kinds that carry a `service_id`, mirrored from
#: `stages/assemble_document.SERVICE_BEARING_KINDS`. NOT re-derived and NOT
#: re-decided here: the writer is the authority on which lines name a service,
#: and this read only groups by the column it wrote.
_SERVICE_BEARING_KINDS = ("usage", "base")


def _charges_by_service(invoice: Invoice, lines: list[InvoiceLine]) -> dict[str, Any]:
    """What this bill charged, per service — CR-053 task 9.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE ONE ARITHMETIC CHOICE, AND B4 HAD ALREADY MADE IT               ║
    ╚══════════════════════════════════════════════════════════════════════╝
    A subtotal is a sum over lines and there are exactly two readings:

        Σ finalize(line)   add the amounts the bill PRINTS      <- THIS ONE
        finalize(Σ line)   add what it STORES, then round once

    They differ by up to a cent per bucket. **B4 ruled between them on
    2026-08-11**, for the tax base, and its stated reason is about
    sums-over-lines in general rather than about tax: *"a customer who adds up
    the four printed lines and applies the rate gets $13.66 while the bill says
    $13.67, so the printed document does not foot against itself"* — the ruling
    chose the ROUNDED addends **for reproducibility, not precision**, and said
    so. A per-service subtotal is read by a customer performing exactly that
    addition down a column, so it takes the same reading.

    Worked, on three electric lines of `33.333333`:

        Σ finalize  =  33.33 + 33.33 + 33.33   =   **99.99**
        finalize Σ  =  finalize(99.999999)     =     100.00

    `99.99` is what the printed lines add to. The other reading puts a cent on
    the bill that appears in no line.

    **NO SIGNED FIGURE MOVES.** B4.4 (round per line item, half-up, 2dp) and
    B5's fixtures are untouched; this applies them, and `core.money.finalize`
    is the single signed rounding helper rather than a second `quantize` here.

    ── THE GROUPING IS THE COLUMN, NEVER THE WORDING ────────────────────────
    `invoice_lines.service_id` is written by
    `stages/assemble_document._service_id_for` for `usage` and `base` lines and
    for NOTHING ELSE — a tax is a BILL-level charge (PO ruling 2026-08-11,
    *"Tax rates are for bill not for service"*) and a fee is a fact about the
    ACCOUNT. So the buckets are: one per service actually charged, plus one
    stated `bill_level` bucket for every other kind.

    Nothing here reads a description or a unit to decide which service a line
    belongs to. That writer refuses to guess for a stated reason — *"water and
    sewer are both metered in kgal, so a unit-based guess would post one
    service's revenue to the other's account — silently, permanently"* — and a
    read that guessed would put one service's money under the other's heading
    on screen while the GL stayed right, which is worse than either.

    ⚠ **THIS IS THEREFORE NOT `BR-RAT-047`'s `service_subtotal.<service>` AND
    IS DELIBERATELY NOT CALLED THAT.** That name is a rating FORMULA-vocabulary
    term meaning *"usage + base + minimum adjustment — BR-RAT-028 mode-A
    basis"*, and it is PROPOSED, not ratified (its contents are candidate
    OQ-096). Two differences, both real: it is a PRICING input and this is a
    DISPLAY grouping of an issued bill's own rows; and a `minimum_adjustment`
    line stores `service_id = NULL` today, so it lands in `bill_level` here and
    inside the basis there (DEF-2429). One name for two meanings is how a
    screen and an engine start disagreeing about a customer's money.

    ── WHAT THE BLOCK REFUSES TO DO ─────────────────────────────────────────
    **It never reconciles.** `tie_out` compares Σ of the buckets against
    `invoices.total` and STATES the difference; it does not adjust either side
    and it does not raise. That is `_integrity_for`'s posture two functions up,
    for its reason: a detail endpoint that 500s on a drifted bill hides the one
    bill somebody needs to look at, and a read that silently balanced the books
    would destroy the evidence BR-BIL-032 exists to surface.

    **It writes nothing** (hard rule 4 — an issued bill and its lines are
    immutable). Every figure is derived per read, so two reads of an unchanged
    bill are identical and nothing is stored to drift.

    **A bill with no service-bearing line answers `services: []`.** A zero-
    valued row would claim the bill charged for a service it never touched —
    the same distinction `deposit_rule_for` draws between `None` and `0.00`.

    Money is a STRING at the column's scale beside its CHAR(3) (rule 2 —
    never a float, never a bare number), with the 2dp DISPLAY figure served
    alongside so the screen and the server round once, in one place, the same
    way (`BR-RAT-087`'s `_display_money` posture in rating).
    """
    currency = invoice.currency
    buckets: dict[Any, dict[str, Any]] = {}
    bill_level_total = Decimal("0")
    bill_level_count = 0
    bill_level_kinds: set[str] = set()
    # `DEF-BIL-9346` — the bill-level DISCOUNT lines, summed beside the bucket
    # they already sit in (never taken out of it: `bill_level` keeps its meaning
    # for the portal and the remittance page), so the Document tab can name them
    # *Discounts* as the Charges tab does since `DEF-BIL-9339`.
    discount_total = Decimal("0")
    discount_count = 0

    for line in lines:
        # Σ OF THE ROUNDED LINES — B4.4 + the 2026-08-11 ruling. `finalize` is
        # idempotent at 2dp, so a bill whose lines are already finalized (every
        # bill this engine writes) is unchanged by it; the call is what makes
        # the reading explicit rather than accidental.
        amount = money.finalize(Decimal(line.amount or 0))
        if line.service_id and line.kind in _SERVICE_BEARING_KINDS:
            bucket = buckets.setdefault(
                line.service_id,
                {
                    "service": line.service.code,
                    "name": line.service.name,
                    "total": Decimal("0"),
                    "count": 0,
                    "sort": line.service.sort,
                },
            )
            bucket["total"] += amount
            bucket["count"] += 1
        else:
            bill_level_total += amount
            bill_level_count += 1
            if line.kind:
                bill_level_kinds.add(line.kind)
            if line.kind == "discount":
                discount_total += amount
                discount_count += 1

    # BR-RAT-024's seeded catalog order — `services.sort`, the order every other
    # screen draws the ten services in. Alphabetical would put sewer before
    # water on a bill and after it everywhere else.
    ordered = sorted(buckets.values(), key=lambda row: (row["sort"], row["service"]))
    services = [
        {
            "service": row["service"],
            "service_name": row["name"],
            "line_count": row["count"],
            "subtotal": _decimal_str(row["total"]),
            "subtotal_display": _display_money(row["total"]),
        }
        for row in ordered
    ]

    lines_total = sum((row["total"] for row in ordered), Decimal("0")) + bill_level_total
    invoice_total = Decimal(invoice.total or 0)
    return {
        "currency": currency,
        "services": services,
        "bill_level": {
            "line_count": bill_level_count,
            # WHY THESE KINDS ARE NAMED. A reader seeing money outside every
            # service heading needs to know WHY it is outside — a tax is
            # bill-level by ruling, a fee by nature. Sorted so the key is
            # stable across reads.
            "kinds": sorted(bill_level_kinds),
            "subtotal": _decimal_str(bill_level_total),
            "subtotal_display": _display_money(bill_level_total),
            # `DEF-BIL-9346` — the bucket split in two, each figure Σ of the
            # same finalized lines, so `discounts` + `others` = the bucket to
            # the cent and the screen adds nothing up itself (BR-SHL-023).
            "discounts": {
                "line_count": discount_count,
                "subtotal": _decimal_str(discount_total),
                "subtotal_display": _display_money(discount_total),
            },
            "others": {
                "line_count": bill_level_count - discount_count,
                "kinds": sorted(bill_level_kinds - {"discount"}),
                "subtotal": _decimal_str(bill_level_total - discount_total),
                "subtotal_display": _display_money(bill_level_total - discount_total),
            },
        },
        "tie_out": {
            "ties_out": lines_total == invoice_total,
            "lines_total": _decimal_str(lines_total),
            "invoice_total": _decimal_str(invoice_total),
            # STATED, never corrected. Negative means the rows add to less than
            # the bill claims.
            "delta": _decimal_str(lines_total - invoice_total),
        },
    }


def _display_money(value: Decimal | None) -> str | None:
    """The 2dp DISPLAY figure (CLAUDE.md rule 2 — *"display both 2 decimal"*).

    `core.money.finalize` and not a local `quantize`: rounding constants are
    HUMAN-OWNED (`core/money.py`'s own header) and this file may apply them,
    never restate them.
    """
    if value is None:
        return None
    return str(money.finalize(Decimal(value)))


# ══════════════════════════════════════════════════════════════════════════
# OQ-1190 — PER-AUTHORITY TAX SUBTOTALS
# 🔒 MONEY PATH · HUMAN-REVIEW-PENDING (12-governance/09-human-review-ledger.md)
# ══════════════════════════════════════════════════════════════════════════
#: The one kind that carries a `tax_id`. Mirrored from
#: `stages/assemble_document`, which stamps the tax and nothing else — NOT
#: re-decided here: the writer is the authority on which lines name a tax, and
#: this read only groups by the column it wrote.
_TAX_BEARING_KIND = "tax"


def _taxes_by_authority(
    invoice: Invoice,
    lines: list[InvoiceLine],
    *,
    tax_labels: dict[str, Any] | None = None,
    gl_labels: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What this bill owes, per tax authority — the PO's ruling of 2026-08-31.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  WHY THIS EXISTS: A RETURN IS FILED PER AUTHORITY                    ║
    ╚══════════════════════════════════════════════════════════════════════╝
    PO ruling 2026-08-31, verbatim: *"(a) Add a per-authority subtotal to the
    bill and the finance screens"*. It closes `OQ-1190`, whose worked case is
    that one bill charges Bexar County one figure and Texas State another and
    **the only tax figure this product published was the two added together**.
    A remittance return is filed per authority, monthly, and the number on it
    was the one number nothing computed.

    ⚠ **THE RECOMMENDATION PUT TO THE PO WAS NARROWER AND WAS DECLINED.** We
    argued for the finance screens ONLY, on the grounds that a customer does
    not act on a figure they cannot change. The PO's answer is BOTH surfaces.
    Recorded here because a lane reading only this file would otherwise take
    the bill half for scope creep and quietly drop it.

    ── THE ARITHMETIC IS `_charges_by_service`'s, AND B4 HAD ALREADY RULED ──
    Σ **finalize(line)** — add the amounts the bill PRINTS — never
    finalize(Σ line). B4's 2026-08-11 ruling chose the ROUNDED addends *for
    reproducibility, not precision*, and said why: *"a customer who adds up the
    four printed lines and applies the rate gets $13.66 while the bill says
    $13.67, so the printed document does not foot against itself"*. This is a
    sum over the SAME printed column and takes the SAME reading. The repo's own
    worked pair is three lines of `33.333333` subtotalling to **99.99**, not
    100.00.

    **NO SIGNED FIGURE MOVES.** B4.4 (round per line item, half-up, 2dp) and
    B5's fixtures are untouched; `core.money.finalize` is the single signed
    rounding helper rather than a second `quantize` here. Golden verify read
    33 PASS / 0 FAIL before this function was written and after it.

    ── THE GROUPING IS THE STAMPED COLUMN, NEVER THE WORDING ────────────────
    `invoice_lines.tax_id` is BR-BIL-069's *"whose tax this line is"*, written
    by `stages/assemble_document` and frozen at issue. Nothing here reads a
    DESCRIPTION to decide whose tax a line is: on the reference bill the two
    descriptions are *"Tax Local"* and *"Tax Texas State"*, and neither is an
    authority — "Local" is the Bexar County Tax Office. Matching a tax by its
    description was option D of `OQ-116` and the PO declined it.

    ⚠ **THIS DOES NOT MOVE TAX ONTO SERVICES.** The PO's ruling of 2026-08-11 —
    *"Tax rates are for bill not for service"* — is untouched, and
    `_charges_by_service` still puts every tax line in its one `bill_level`
    bucket. This is a SECOND grouping of the same rows beside that one, on a
    different axis, for a different question. Two groupings of one immutable
    set of lines cannot disagree with each other; a re-attribution would.

    ── SUB-QUESTION (b): THE AUTHORITY'S OWN REMITTANCE ACCOUNT ─────────────
    `OQ-1190` asked whether the authority's 2200-nn account belongs in the
    bucket, because the `OQ-116` closure pairs *"separate account"* with
    *"tagging"*. **It does, and it costs nothing to answer**: the account is
    already STAMPED on each tax line (`invoice_lines.gl_account_id`,
    BR-BIL-010, resolved at issue through `liability_gl_account_id_for_tax`),
    so this reads the stamp rather than resolving anything. It is what lets a
    finance screen join a bill's per-authority figure to the books.

    **It is served ONLY when every line in the bucket names the SAME account.**
    Two accounts under one authority is a posting fault, not a display choice,
    and naming one of them would hide it — so the field goes null and
    `liability_account_conflict` says so.

    ── WHAT THE BLOCK REFUSES TO DO ─────────────────────────────────────────
    **It never reconciles.** `tie_out` compares Σ of the buckets against
    `invoices.tax_total` and STATES the difference; it does not adjust either
    side and it does not raise — `_charges_by_service`'s posture, for its
    reason: a read that silently balanced the books would destroy the evidence
    BR-BIL-032 exists to surface.

    **It writes nothing** (hard rule 4). Every figure is derived per read, so
    two reads of an unchanged bill are identical and nothing is stored to
    drift.

    **A bill with no tax line answers `authorities: []`** — never a zero row,
    which would claim a debt to an authority this bill never charged.

    **The `tax_id` is served and must never be DISPLAYED** (B14 rule 31, PO
    2026-08-30: *"no Databse ID on screen - that is a rule"*). It is the join
    key and the render key; the AUTHORITY is what a person reads, and a bucket
    whose label could not be resolved says so rather than falling back to the
    id (DEF-2432).

    Money is a STRING at the column's scale beside its CHAR(3) (rule 2 — never
    a float, never a bare number), with the 2dp DISPLAY figure served alongside
    so the screen and the server round once, in one place, the same way.
    """
    currency = invoice.currency
    buckets: dict[str, dict[str, Any]] = {}
    unstamped_total = Decimal("0")
    unstamped_count = 0

    for line in lines:
        if line.kind != _TAX_BEARING_KIND:
            continue
        # Σ OF THE ROUNDED LINES — B4.4 + the 2026-08-11 ruling. `finalize` is
        # idempotent at 2dp, so a bill whose lines are already finalized (every
        # bill this engine writes) is unchanged by it; the call is what makes
        # the reading explicit rather than accidental.
        amount = money.finalize(Decimal(line.amount or 0))
        tax_id = str(line.tax_id) if line.tax_id else None
        if tax_id is None:
            # A tax line with no stamp is a real state on a bill issued before
            # BR-BIL-069's column was written. It is COUNTED — its money is on
            # the bill and must reach the tie-out — and it is never folded into
            # a named authority, which would put one authority's debt on
            # another's return.
            unstamped_total += amount
            unstamped_count += 1
            continue
        bucket = buckets.setdefault(
            tax_id,
            {
                "authority": (tax_labels or {}).get(tax_id),
                "total": Decimal("0"),
                "count": 0,
                "accounts": set(),
            },
        )
        bucket["total"] += amount
        bucket["count"] += 1
        if line.gl_account_id:
            bucket["accounts"].add(str(line.gl_account_id))

    # Alphabetical BY THE AUTHORITY'S NAME, which is how a clerk holding a
    # stack of returns reads it. An unresolved label sorts LAST rather than
    # first, so the bill's answerable rows are not pushed down the table by a
    # row that names nobody. `tax_id` breaks ties, so two reads of an unchanged
    # bill come back in the same order.
    ordered = sorted(
        buckets.items(),
        key=lambda item: (item[1]["authority"] is None, item[1]["authority"] or "", item[0]),
    )
    authorities: list[dict[str, Any]] = []
    for tax_id, row in ordered:
        accounts = row["accounts"]
        one_account = next(iter(accounts)) if len(accounts) == 1 else None
        gl = (gl_labels or {}).get(one_account) if one_account else None
        authorities.append(
            {
                # THE JOIN KEY AND THE RENDER KEY, NEVER A VISIBLE VALUE.
                "tax_id": tax_id,
                "authority": row["authority"],
                "line_count": row["count"],
                "subtotal": _decimal_str(row["total"]),
                "subtotal_display": _display_money(row["total"]),
                # BR-BIL-010's stamp, READ BACK — never re-resolved.
                "liability_account_id": one_account,
                "liability_account_code": (gl or {}).get("code"),
                "liability_account_name": (gl or {}).get("name"),
                # STATED rather than hidden: more than one liability account
                # under one authority means the bill posted one debt two ways,
                # and a screen that picked one of them would bury it.
                "liability_account_conflict": len(accounts) > 1,
            }
        )

    authorities_total = (
        sum((Decimal(row["subtotal"]) for row in authorities), Decimal("0")) + unstamped_total
    )
    tax_total = Decimal(invoice.tax_total or 0)
    return {
        "currency": currency,
        "authorities": authorities,
        # The SAME distinction `bill_level` draws in `_charges_by_service`: the
        # money that is on the bill and under no heading.
        "unstamped": {
            "line_count": unstamped_count,
            "subtotal": _decimal_str(unstamped_total),
            "subtotal_display": _display_money(unstamped_total),
        },
        "tie_out": {
            "ties_out": authorities_total == tax_total,
            "authorities_total": _decimal_str(authorities_total),
            "authorities_total_display": _display_money(authorities_total),
            "tax_total": _decimal_str(tax_total),
            "tax_total_display": _display_money(tax_total),
            # STATED, never corrected. Negative means the authority rows add to
            # less than the bill's own tax total claims.
            "delta": _decimal_str(authorities_total - tax_total),
        },
    }


def tax_by_authority_for_invoices(invoice_ids: Any) -> dict[str, Any]:
    """The per-authority tax subtotal over a NAMED SET of bills — for finance.

    ╔══════════════════════════════════════════════════════════════════════╗
    ║  THE CALLER NAMES THE BILLS. THIS FUNCTION INVENTS NO BASIS.         ║
    ╚══════════════════════════════════════════════════════════════════════╝
    The PO's ruling of 2026-08-31 puts the per-authority subtotal on the
    finance screens as well as the bill. The finance screen is S41 Taxes &
    Remittance, which reports a PERIOD — and a period read written here would
    have had to decide, on its own, whether a VOID bill's tax and a CORRECTED
    bill's tax still belong on a return. **That is a money rule nobody has
    signed, and the prime directive forbids a lane choosing a value for one.**

    So this takes the invoice ids and asks nothing about them. **The BOOKS
    decide which bills count** — `apps/ledger/reporting.remittance_by_authority`
    already selects the invoice-sourced journal entries that credited each
    authority's 2200-nn account inside its own window, on its own posting
    basis, and a reversal is a debit that removes itself. This function answers
    only *"of these bills, how much is each authority's?"*, which is the same
    question `_taxes_by_authority` answers for one bill and takes the same
    B4 Σ-of-the-ROUNDED-lines reading.

    **One derivation, two callers.** The per-bill block and this one loop over
    the same rows with the same `money.finalize`, so the figure a clerk reads on
    S41 and the figure they read on the bill cannot disagree.

    Returns `{"currency": …, "authorities": [ … ], "invoice_count": n}` with the
    same per-bucket shape as `_taxes_by_authority`, plus `invoice_count` so a
    caller can state how many bills are behind a figure. An empty id set answers
    an empty list — never a zero row.

    ⚠ **TENANT-SCOPED BY `invoice_queryset()`** (hard rule 1, HR-1). An id from
    another tenant simply is not found; it is never an error and never a leak.
    """
    ids = [str(value) for value in (invoice_ids or []) if value]
    if not ids:
        return {"currency": None, "authorities": [], "invoice_count": 0}
    invoices = list(invoice_queryset().filter(pk__in=ids))
    if not invoices:
        return {"currency": None, "authorities": [], "invoice_count": 0}
    lines = list(
        InvoiceLine.objects.filter(
            tenant_id=core_tenancy.current_tenant_id(),
            invoice_id__in=[row.pk for row in invoices],
            kind=_TAX_BEARING_KIND,
        )
    )
    tax_labels = _tax_authority_labels(lines)
    gl_ids = {str(line.gl_account_id) for line in lines if line.gl_account_id}
    gl_read = _resolve("ledger", "account_labels")
    gl_labels = gl_read(gl_ids) if callable(gl_read) and gl_ids else {}

    buckets: dict[str, dict[str, Any]] = {}
    for line in lines:
        amount = money.finalize(Decimal(line.amount or 0))
        tax_id = str(line.tax_id) if line.tax_id else None
        if tax_id is None:
            continue
        bucket = buckets.setdefault(
            tax_id,
            {
                "authority": tax_labels.get(tax_id),
                "total": Decimal("0"),
                "count": 0,
                "accounts": set(),
            },
        )
        bucket["total"] += amount
        bucket["count"] += 1
        if line.gl_account_id:
            bucket["accounts"].add(str(line.gl_account_id))

    ordered = sorted(
        buckets.items(),
        key=lambda item: (item[1]["authority"] is None, item[1]["authority"] or "", item[0]),
    )
    # DEF-081's discipline: one currency or none. A tax liability summed across
    # two currencies is remitted to a real revenue authority in ONE of them, and
    # the shortfall is discovered by the authority rather than by us. Where the
    # named bills disagree the currency is served as None and the caller states
    # the absence — it is never picked.
    currencies = {row.currency for row in invoices if row.currency}
    return {
        "currency": next(iter(currencies)) if len(currencies) == 1 else None,
        "invoice_count": len(invoices),
        "authorities": [
            {
                "tax_id": tax_id,
                "authority": row["authority"],
                "line_count": row["count"],
                "subtotal": _decimal_str(row["total"]),
                "subtotal_display": _display_money(row["total"]),
                "liability_account_id": (
                    next(iter(row["accounts"])) if len(row["accounts"]) == 1 else None
                ),
                "liability_account_conflict": len(row["accounts"]) > 1,
            }
            for tax_id, row in ordered
        ],
    }


#: CR-059 CS-37 · task 27 — how many credit notes one page of the account tab
#: carries. A page rather than the lot: an account corrected every month for
#: five years has sixty of these, and a tab that loads them all is a tab that
#: eventually stops loading. 200 is a CEILING rather than a pager, because
#: CS-37's screen is a TAB and not a list page — `truncated` tells the reader
#: when the ceiling was reached, so a partial history is never shown as a
#: complete one.
ACCOUNT_CREDIT_NOTE_LIMIT = 200


def account_credit_notes(
    account_id: Any, *, limit: int = ACCOUNT_CREDIT_NOTE_LIMIT
) -> dict[str, Any]:
    """`GET /accounts/{id}/credit-notes` — every credit note on ONE account.

    ════════════════════════════════════════════════════════════════════════
    THE QUESTION THIS ANSWERS, AND WHY IT HAD NO ANSWER UNTIL NOW
    ════════════════════════════════════════════════════════════════════════
    CR-059 §7 puts it plainly: to find every credit note a customer has ever
    been given, somebody had to **open each of their bills one at a time** and
    read the panel on each. There was no list, no filter, no account tab and no
    report — *"and the database index built for exactly that lookup, on utility
    plus account, has never had a query run against it."*

    This is that query. `ix_credit_notes_account` is `(tenant, account)` and the
    filter below is exactly that pair, so the index is used as it was built
    rather than a second one being added beside it.

    ════════════════════════════════════════════════════════════════════════
    B14 RULE 31 — NO ID IS A DISPLAYABLE VALUE ON THIS ROW
    ════════════════════════════════════════════════════════════════════════
    `id` and `invoice_id` travel because a React key and a link to the bill need
    one; the fields a CELL may render are `credit_note_no`, `issued_at`,
    `amount`, `currency`, `reason` and `invoice_no`. A row whose number is
    absent is a historic row — CS-37 does **not** back-fill them, because the
    row freezes at issue — and the screen shows the bill and the date instead.

    **`invoice_no` is normalised: blank becomes null.** `Invoice.invoice_no` can
    be an empty string on a draft, and `""` renders as an EMPTY CELL, which
    `tests/test_cr059_rule31_collections_account_no.py` records as breaching
    rule 31 just as loudly as a uuid did: a person reads a blank as "there is
    nothing here" about a document that exists.

    ════════════════════════════════════════════════════════════════════════
    WHAT IT DOES NOT DO
    ════════════════════════════════════════════════════════════════════════
    **It computes no balance and nets nothing.** CR-059 §7 records that neither
    the outstanding figure nor the account credit reads this table, and making a
    READ start doing so would give the account balance two sources of truth in
    two modules — the smaller alternative CS-38 rejects by name. This read
    reports what exists; CS-38 owns what a concession does to what is owed.
    """
    tenant_id = _tenant_id()
    rows = list(
        CreditNote.objects.filter(tenant_id=tenant_id, account_id=account_id)
        .select_related("original_invoice")
        .order_by("-issued_at", "-created_at", "id")[: limit + 1]
    )
    truncated = len(rows) > limit
    rows = rows[:limit]
    return {
        "account_id": str(account_id),
        "credit_notes": [
            {
                "id": str(note.id),
                "credit_note_no": note.credit_note_no,
                "amount": _decimal_str(note.amount),
                "currency": note.currency,
                "reason": note.reason,
                "issued_at": _iso(note.issued_at),
                "invoice_id": (
                    None if note.original_invoice_id is None else str(note.original_invoice_id)
                ),
                "invoice_no": (
                    (note.original_invoice.invoice_no or None)
                    if note.original_invoice_id is not None
                    else None
                ),
            }
            for note in rows
        ],
        "count": len(rows),
        "truncated": truncated,
    }


def _credit_note_queryset():
    """Every credit note of the tenant in context, ordered — LAZY, sliced by nobody here.

    ⚠ **ADDED 2026-09-23 BY `CR-138-BRC07` `P4.25`.** `account_credit_notes`
    above answers *"show me THIS ACCOUNT's"* and is built on
    `ix_credit_notes_account`; this answers *"show me the TENANT's"*, which is
    the question the payments Refunds tab asks when it puts refunds and credit
    notes in ONE list.

    PRIVATE. It returns billing's own `QuerySet`, and no other module may hold
    one (B1 / BR-TEN-013): `credit_note_page` and `credit_note_count` below are
    what crosses the boundary, and they hand back dicts and an int. That is the
    split `apps/payments/notices.py` made for `notice_history` under
    `DEF-NOT-5750`, for the same reason and in the same shape.

    ⚠ **THE ORDERING IS LOAD-BEARING, AND IT IS `-created_at` RATHER THAN
    `-issued_at`.** `account_credit_notes` orders `-issued_at, -created_at, id`
    and that is right for a short account tab. It is WRONG under a page:
    `issued_at` is NULLABLE, so PostgreSQL sorts every unissued note to the TOP
    (`DESC` puts NULLs first) and SQLite to the bottom — two orders for one
    list. **A page taken in SQL over an unstable order shows the same row on
    page 1 and page 2 and hides another entirely** (`notice_history_page`'s own
    words). `created_at` is `auto_now_add` and never null; `id` breaks its ties.

    Tenant scoping is the manager's (`_tenant_id()` under RLS FORCE, hard rule
    1). There is no tenant parameter, so no caller can widen it.
    """
    return (
        CreditNote.objects.filter(tenant_id=_tenant_id())
        .select_related("original_invoice")
        .order_by("-created_at", "-id")
    )


def credit_note_row(note: Any) -> dict[str, Any]:
    """ONE credit note as the published dict — the shape every reader gets.

    ⚠ **NOT ONE MEMBER IS SPELLED DIFFERENTLY FROM `account_credit_notes`'s
    ROW**, deliberately: two shapes of one row is `DEF-014`'s exact shape, and a
    screen meeting the account tab's spelling and this one's would have to know
    which it was holding. `account_id` and `created_at` are ADDED, because a
    tenant-wide list has to say whose note it is and the page is ordered on the
    second; nothing is renamed and nothing is dropped.

    **B14 rule 31.** `id` and `invoice_id` travel because a React key and a link
    to the bill need one; the fields a CELL may render are `credit_note_no`,
    `issued_at`, `amount`, `currency`, `reason` and `invoice_no`. A note whose
    number is absent is a HISTORIC row — CS-37 does not back-fill, because the
    row freezes at issue — and the screen shows the bill and the date instead.

    `invoice_no` is normalised: a draft's `""` becomes `None`, because an empty
    cell reads as *"there is nothing here"* about a document that exists, which
    `tests/test_cr059_rule31_collections_account_no.py` records as breaching
    rule 31 just as loudly as a uuid did.
    """
    return {
        "id": str(note.id),
        "account_id": str(note.account_id),
        "credit_note_no": note.credit_note_no,
        "amount": _decimal_str(note.amount),
        "currency": note.currency,
        "reason": note.reason,
        "issued_at": _iso(note.issued_at),
        "created_at": _iso(note.created_at),
        "invoice_id": (None if note.original_invoice_id is None else str(note.original_invoice_id)),
        "invoice_no": (
            (note.original_invoice.invoice_no or None)
            if note.original_invoice_id is not None
            else None
        ),
    }


def credit_note_count() -> int:
    """HOW MANY credit notes this tenant has — a `COUNT(*)`, never a built list.

    PUBLISHED: `apps/payments/billing_seam.py` resolves it BY NAME (B1). The
    table is billing's and the count is taken HERE, in the module that owns it,
    under its own tenant scope — payments never holds a `CreditNote` queryset
    and never learns the table's name.

    It exists so a union list's total is a TOTAL. `NFR-5` forbids a number any
    row can be beyond, and a `count` that is the length of what was already
    built is a FLOOR wearing a total's clothes — which is exactly what
    `GET /notices` served until `DEF-NOT-5750`.
    """
    return _credit_note_queryset().count()


def credit_note_page(*, offset: int = 0, limit: int) -> list[dict[str, Any]]:
    """ONE PAGE of the tenant's credit notes, taken in the DATABASE.

    `LIMIT`/`OFFSET`, never a slice in Python (`NFR-3`). PUBLISHED for
    `apps/payments/billing_seam.py` to resolve by name.

    `limit` IS A PAGE SIZE AND NOT A CAP, which is the whole distinction
    `NFR-5` turns on: it is REQUIRED rather than defaulted, it is the size of
    the window the caller asked for, and `offset` reaches every row behind it.
    There is no number here that any row can be beyond.

    ⚠ **A NEGATIVE OR ZERO `limit` RETURNS `[]` AND ISSUES NO QUERY.** Django
    refuses a negative slice bound, and an empty page is a real state rather
    than an error — the same answer `notice_history_page` gives, so the two
    paged reads that cross a seam in this product cannot disagree about it.
    """
    if limit <= 0:
        return []
    start = max(int(offset), 0)
    return [credit_note_row(note) for note in _credit_note_queryset()[start : start + int(limit)]]


def invoice_detail(invoice_id: Any) -> dict[str, Any]:
    """`GET /invoices/{id}` — the row plus the record behind it."""
    invoice = invoice_or_404(invoice_id)
    tenant_id = invoice.tenant_id
    lines = (
        InvoiceLine.objects.filter(tenant_id=tenant_id, invoice=invoice)
        .select_related("service")
        .order_by("created_at", "id")
    )
    credit_notes = CreditNote.objects.filter(
        tenant_id=tenant_id, original_invoice=invoice
    ).order_by("created_at", "id")
    adjustments = Adjustment.objects.filter(tenant_id=tenant_id, invoice=invoice).order_by(
        "created_at", "id"
    )
    # ONE evaluation of the line queryset, shared by both readers below. The
    # grouping reads `line.service.code`/`.name`/`.sort`, which the
    # `select_related("service")` above already fetched — so the block costs no
    # query at all, and a bill's lines cannot be read twice and disagree.
    line_rows = list(lines)
    # THE FOUR LABEL MAPS, RESOLVED ONCE FOR THE WHOLE PAYLOAD. Two blocks now
    # need the tax-authority map — the line table and `taxes_by_authority` — and
    # resolving it twice would let one bill name an authority two ways in one
    # response if a row were renamed between the two reads.
    label_maps = _labels_for_lines(line_rows)
    return {
        **invoice_row(invoice),
        "lines": _line_rows(line_rows, labels=label_maps),
        # CR-053 task 9 — 🔒 money. The CR marks this the expensive half:
        # *"nothing computes these; they are a real backend addition, not a
        # serialization"*. See `_charges_by_service` for the rounding reading
        # and why it is not BR-RAT-047's `service_subtotal`.
        "charges_by_service": _charges_by_service(invoice, line_rows),
        # OQ-1190 — 🔒 money. PO ruling 2026-08-31: *"(a) Add a per-authority
        # subtotal to the bill and the finance screens"*. The SECOND grouping
        # of the same immutable lines, on the axis a remittance return is filed
        # on. See `_taxes_by_authority` for the rounding reading and for why
        # the 2026-08-11 *"Tax rates are for bill not for service"* ruling is
        # untouched by it.
        "taxes_by_authority": _taxes_by_authority(
            invoice,
            line_rows,
            tax_labels=label_maps[2],
            gl_labels=label_maps[0],
        ),
        # BR-BIL-031: the DATA contract version — a different axis from the
        # template version, which is why the screen shows both.
        "payload_version": invoice.payload_version,
        # BR-BIL-030: whether a frozen instance EXISTS. A boolean, never the
        # payload: no signed document names its JSON keys (11b §2.8a point 3).
        "has_payload": invoice.bill_payload is not None,
        # US-BIL-019 — the three columns WE-8 puts on EVERY budget bill (actual ·
        # level · variance movement) plus the running balance, read from the
        # bill's own frozen payload so a re-level never rewrites a past bill.
        # Null on an ordinary bill, which has no level and no variance.
        #
        # ⚠ THIS IS THE ONE PART OF THE PAYLOAD THIS MODULE OPENS, and the
        # exception is deliberate: `_summary_for` says the payload's keys are
        # not named by a signed document, but THIS block's keys are named by
        # US-BIL-019 §5's own field table, and without them S30's Budget Bills
        # tab has nothing to render. Stated rather than done quietly.
        "budget": (invoice.bill_payload or {}).get("budget"),
        # `GET /invoices/{id}/document` IS mounted since 2026-08-16
        # (apps/billing/documents_api.py). ⚠ CORRECTED — this line read
        # `"document_url": None` with the comment *"is not mounted"* beside it,
        # and leaving that standing after the route landed is exactly the stale
        # claim hard-won law 1 is about.
        #
        # It is DERIVED from the pin, not hardcoded to a string: BR-BIL-026
        # stamps `template_version` at issue, so a bill with no pin has no
        # document to render and `documents.render_invoice` says so. Serving a
        # link that answers 422 would put a broken control on the detail screen
        # of every draft; serving null lets the screen state the absence.
        "document_url": (
            f"/invoices/{invoice.pk}/document" if invoice.template_version is not None else None
        ),
        "summary": _summary_for(invoice),
        "credit_notes": [
            {
                "id": str(note.id),
                "credit_note_no": note.credit_note_no,
                "amount": _decimal_str(note.amount),
                "currency": note.currency,
                "reason": note.reason,
                "issued_at": _iso(note.issued_at),
            }
            for note in credit_notes
        ],
        # BR-BIL-004/014's chain, NAVIGABLE BOTH WAYS (US-BIL-015 TC-3) — built
        # 2026-08-12 on the PO's OQ-120 closure, *"Nod to add the link on the
        # new bill"*. ONE column carries both directions and that is the point:
        #
        #   * `rebill_of_invoice_id`     — this bill's own `corrects_invoice_id`,
        #     i.e. what THIS bill replaces. Non-null only on a replacement.
        #   * `corrected_by_invoice_id`  — the reverse read of the same column,
        #     i.e. the bill that replaced THIS one. Non-null only on a superseded
        #     original.
        #
        # These were served null on every row until the column existed, under
        # their contracted names so the screen showed an absence rather than a
        # chain that did not exist. They are real now.
        "rebill_of_invoice_id": (
            str(invoice.corrects_invoice_id) if invoice.corrects_invoice_id else None
        ),
        "corrected_by_invoice_id": (
            str(replacement.pk) if (replacement := corrections.replacement_of(invoice)) else None
        ),
        "adjustments": [
            {
                "id": str(row.id),
                "direction": row.direction,
                "amount": _decimal_str(row.amount),
                "currency": row.currency,
                "reason_code": row.reason_code,
                "created_at": _iso(row.created_at),
            }
            for row in adjustments
        ],
        # US-BIL-024 — where this bill went, per channel (BR-BIL-016).
        #
        # ⚠ THIS SERVED A HARDCODED `None` UNTIL 2026-08-16 and the comment
        # beside it read *"what is missing is this READ"*. It was missing for
        # five days while `issue.py` wrote a delivery row for every bill it
        # issued, so S30's delivery panel — built, and shipped with the detail
        # screen — rendered its absence branch on every bill in the product.
        #
        # `None` IS STILL A REAL ANSWER and is why this goes through a seam
        # rather than a queryset: a deployment whose notifications module
        # publishes no read cannot say where a bill went, and `[]` there would
        # tell a clerk an issued bill was never sent to anyone. `[]` now means
        # what it should mean — the queue was asked and holds nothing, which for
        # a draft is the truth, because queueing happens at issue.
        #
        # Four columns, because four are what the screen draws and what
        # BR-BIL-016 is about. `at` is the QUEUED time and not a sent time:
        # nothing in R2 sends (no dispatcher, no provider adapter), so a row's
        # `sent_at` is null on every bill and a column headed with it would
        # invite the reading that delivery failed.
        "deliveries": _deliveries_for(invoice),
        # US-BIL-030 — BR-BIL-032's tie-out and BR-BIL-011's balanced handoff,
        # asked of THIS bill. Both were computed only inside their own test file
        # until 2026-08-16, so the rule that says drift "can never be silent"
        # was enforced on fixtures and on no bill this product ever produced.
        "integrity": _integrity_for(invoice),
    }


# ══════════════════════════════════════════════════════════════════════════
# S31 THE BILL RUN — the read model behind /billing/runs (US-BIL-001..003)
#
# Phase 1 of the PO's five (BR-BIL-050), as JSON. Three properties hold across
# everything below and each one is a decision, not an accident:
#
#   1. **NOTHING HERE WRITES.** `prepare_run` writes nothing by construction
#      and neither do these; the GETs are re-entrant, so a clerk refreshing
#      S31.2 cannot commit anything by looking. `apply_decisions` — which DOES
#      write, because a hold enters the pending queue — is deliberately NOT
#      called from a read: what step 2 shows is what the run found, and what a
#      decision then does to it is step 3's own act.
#   2. **THE KEY NAMES ARE THE DATACLASS FIELD NAMES.** `PreparedRun`,
#      `AccountBillingData`, `ServiceReading` and `AccountProblem` are carried
#      over verbatim in snake_case — no prettifying, no renaming, no invented
#      members — because `07-frontend/src/api/endpoints.ts` was mirrored off
#      those dataclasses while no body was contracted, and a rename on either
#      side is a blank panel on a clerk's screen. The exact key sets are
#      asserted in tests/test_us_bil_001_003_run_api.py.
#   3. **NO CLOCK.** The run's SERVICE date — the pricing pivot (BR-RAT-007) —
#      is the bill date the CLERK typed, stored on the run (BR-BIL-070, PO
#      ruling 2026-08-11 closing OQ-122), and the CYCLE's `bill_date` only when
#      nobody typed one. Neither present REFUSES rather than falling back to
#      the period's end or to today (BR-TEN-043 / G6). This note used to say
#      the service date "is the cycle's `bill_date`" full stop; that was true
#      until the ruling and is rewritten rather than left standing (law 1).
# ══════════════════════════════════════════════════════════════════════════
def run_or_404(run_id: Any) -> BillRun:
    """One bill run of THIS tenant, or the one answer HR-1 allows.

    Unknown, malformed and another tenant's run are byte-identical refusals for
    the same reason `invoice_or_404` makes them identical: answering 422 for a
    bad uuid and 404 for a good one that belongs to someone else lets a caller
    tell the two apart, which is existence leaking one bit at a time.
    """
    tenant_id = _tenant_id()
    if not _is_uuid(run_id):
        raise errors.deny_as_not_found("BR-TEN-003")
    row = BillRun.objects.filter(tenant_id=tenant_id, pk=run_id).first()
    if row is None:
        raise errors.deny_as_not_found("BR-TEN-003")
    return row


# ══════════════════════════════════════════════════════════════════════════
# CR-029 RC-W4b — SET-07D's **Runs** tab: the run HISTORY (B17 §4)
#
# *"**Runs** (run history, Open in Billing →)"*. The tab has rendered a stated
# absence since it shipped, for the reason its own lifecycle trailer records:
# *"the RUN HISTORY has no endpoint (`GET /billing/runs` does not exist; only
# `POST`)"*. This is that read.
#
# FIVE COLUMNS, AND WHERE EACH ONE COMES FROM:
#
#   Run       `run_no` — **the run's own allocated number** (`bill_runs.run_no`,
#             billing 0023). ⚠ It was served NULL here until 2026-08-23, with a
#             test pinning it, because the screenshot read `RUN-0814` and
#             nothing could produce it: deriving one from `created_at`, from a
#             per-cycle ordinal or from the uuid would have minted a naming
#             grammar by call site. **OQ-342 closed it** — PO verbatim *"A: a
#             real series (RUN-0001, like RT-001)"* — so the number comes from
#             the `bill_run` series like every other document number.
#             **NULL on a run created before the series existed**, and the
#             ruling says those are not retro-numbered; `id` is still served
#             beside it and is what the Open-in-Billing link needs.
#   Period    `period_start` / `period_end`, the run's own columns.
#   Issued    `issued_at` — the EARLIEST `invoices.issued_at` on the run, and
#             null when the run has issued nothing. Earliest rather than latest
#             because the question the column answers is *when did this run's
#             bills go out*, and a resumed release that finished a straggler in
#             September did not put August's bills in a customer's hand in
#             September. `bill_runs` itself carries no issued timestamp; the
#             bills do (`issue.issue_run` stamps them all from the caller's
#             event time, BR-TEN-043), so the evidence is read where it lives.
#   Accounts  distinct `invoices.account_id` on the run, any status — *"how
#             many accounts did this run produce a bill for"*. `bills_issued`
#             rides beside it so a draft run (accounts > 0, issued = 0) cannot
#             be misread as an issued one.
#   Status    ⚠ **`status` IS THE STORED COLUMN AND THE STORED COLUMN NEVER
#             MOVES.** `runs.create_run` writes `"draft"` and *nothing in this
#             module ever updates it* — not issue, not release, not the
#             pipeline (grepped, 2026-08-23). So a screen that rendered this
#             field alone would title every historical run "Draft". It is
#             served because it is the row's own column and hiding it would
#             hide the defect; the tab composes its honest *"Issued · 5 held"*
#             from `issued_at` and `held`, which are facts with evidence
#             behind them. REPORTED — the run-status machine is a defect, not
#             this read's to invent.
#
# **NO MONEY, BY RULE.** BR-MET-078 as hardened by CR-029: *"Money never
# touches these surfaces"* (B17 §2). `bill_run_releases.total_amount` and
# `invoices.total` are each one join away and neither is served, nor is a
# currency. A run's total is a real figure; it is not this tab's, and serving
# it "because it is available" is exactly the D12 mistake (the Balance column
# the PO struck off the route's Accounts tab).
#
# **BATCHED, NOT PER ROW.** Three queries for the whole page, whatever its
# length: the runs, one grouped pass over `invoices`, one over
# `bill_run_exclusions`. A per-row count on a cycle with two years of history
# is 24 round trips for a tab nobody scrolls.
# ══════════════════════════════════════════════════════════════════════════

#: The one page size this product uses everywhere, and the ceiling
#: `route_read_windows` already sets for SET-06D's sibling history tab.
BILL_RUN_LIST_DEFAULT_LIMIT = 50
BILL_RUN_LIST_MAX_LIMIT = 200

#: The `f.<name>` vocabulary screen 27's toolbar drives (BR-SHL-011). The
#: blueprint draws three chips — **Cycle · Status · Year** — and `f.cycle_id`
#: was already served under exactly this name by `GET /invoices`, so nothing is
#: renamed. `+ Filter` is drawn beside them and adds nothing to this list: it is
#: the shared overflow control and has no fourth axis behind it here.
#: `bill_type` (DEF-BIL-10090) — Fix a bill asks for `cycle` runs only, so a
#: correction's one-bill rebill run is not offered as "a billing run".
BILL_RUN_LIST_FILTERS: tuple[str, ...] = ("cycle_id", "status", "year", "bill_type")

#: What the search box searches, and the placeholder says so in the clerk's own
#: words: *"Search run number, cycle or person…"* (blueprint p146). Three
#: things, four columns, because a cycle is quotable by its CODE (`09-A`, what
#: the row shows) and by its NAME. `label` — the run's own name from
#: `BR-BIL-1041` — is deliberately NOT searched: the drawn copy names three
#: things and a search that quietly matched a fourth would make that sentence
#: incomplete. Named here rather than left to be discovered.
BILL_RUN_SEARCH_FIELDS: tuple[str, ...] = (
    "run_no",
    "cycle__code",
    "cycle__name",
    "run_by__full_name",
)


def _bill_counts_by_run(run_ids: list[Any]) -> dict[Any, dict[str, Any]]:
    """Per-run bill facts for the whole page, in ONE grouped query.

    `Min("issued_at")` skips nulls, so a run whose drafts have never issued
    yields None rather than a date borrowed from a sibling row.

    ⚠ **IT GROUPS BY `(run, currency)` AND FOLDS, WHICH IS WHAT MAKES THE VALUE
    COLUMN SAFE** (`DEF-BIL-5353`, 2026-09-15). Money is never summed across
    currencies — the sum would be a number with no name, the same reason kWh is
    never added to kgal — so a run whose bills are in two currencies serves
    `value: null` rather than a total. `release._amount_and_currency` REFUSES in
    that case; a list may not, because BR-SHL-011 says a list URL never errors
    and one odd row must not blank a page of thirty-three good ones.
    BR-TEN-021 makes the tenant currency forward-only, so this should be
    unreachable — which is exactly why it must answer honestly if it is reached.
    """
    rows = (
        Invoice.objects.filter(tenant_id=_tenant_id(), bill_run_id__in=run_ids)
        .values("bill_run_id", "currency")
        .annotate(
            accounts=Count("account_id", distinct=True),
            bills_issued=Count("id", filter=Q(status__in=INVOICE_LOCKED_STATUSES)),
            issued_value=Sum("total", filter=Q(status__in=INVOICE_LOCKED_STATUSES)),
            first_issued_at=Min("issued_at"),
        )
        .order_by()  # clear any default ordering out of the GROUP BY
    )
    folded: dict[Any, dict[str, Any]] = {}
    for row in rows:
        run_id = row["bill_run_id"]
        bucket = folded.setdefault(
            run_id,
            {
                "accounts": 0,
                "bills_issued": 0,
                "first_issued_at": None,
                "by_currency": {},
            },
        )
        bucket["accounts"] += row["accounts"]
        bucket["bills_issued"] += row["bills_issued"]
        earliest = row["first_issued_at"]
        if earliest is not None and (
            bucket["first_issued_at"] is None or earliest < bucket["first_issued_at"]
        ):
            bucket["first_issued_at"] = earliest
        currency = row["currency"]
        if currency and row["issued_value"] is not None:
            bucket["by_currency"][currency] = bucket["by_currency"].get(
                currency, Decimal("0")
            ) + Decimal(row["issued_value"])
    return folded


def _held_counts_by_run(run_ids: list[Any]) -> dict[Any, int]:
    """The *"· 5 held"* half, in ONE grouped query.

    UNRESOLVED exclusions only — the same predicate `pending.held_account_ids`
    and the pending queue's own index use (`resolved_at IS NULL`). A hold a
    catch-up sub-run has since billed is closed (BR-BIL-034) and counting it
    would keep a settled account on the tab for ever.
    """
    rows = (
        BillRunExclusion.objects.filter(
            tenant_id=_tenant_id(), bill_run_id__in=run_ids, resolved_at__isnull=True
        )
        .values("bill_run_id")
        .annotate(held=Count("id"))
        .order_by()
    )
    return {row["bill_run_id"]: row["held"] for row in rows}


def _exception_counts_by_run(run_ids: list[Any]) -> dict[Any, dict[str, int]]:
    """This page's exception counts, in ONE grouped query.

    An EXCEPTION here is a `bill_run_breaks` row — BR-BIL-053's list, the thing
    a clerk works through after a calculate pass, and the only per-run trouble
    the product stores with a resolved/unresolved state on it. `total` and
    `outstanding` are both served for the reason `_break_counts` already gives:
    a run that broke 40 accounts and fixed all 40 is not the same run as one
    that never broke, and the blueprint's own tile sub-line is *"all resolved"*.
    """
    rows = (
        BillRunBreak.objects.filter(tenant_id=_tenant_id(), bill_run_id__in=run_ids)
        .values("bill_run_id")
        .annotate(
            total=Count("id"),
            outstanding=Count("id", filter=Q(resolution__isnull=True)),
        )
        .order_by()
    )
    return {
        row["bill_run_id"]: {"total": row["total"], "outstanding": row["outstanding"]}
        for row in rows
    }


#: The columns every run row is built from, read in ONE pass. The three `cycle__`
#: names travel along the REVIEWED cross-module FK `bill_runs.cycle_id →
#: metering.Cycle` (B2 §2 / DB-16) as plain `values`, so nothing here
#: instantiates a metering model or imports one (B1, gate G6) — the same read
#: `cycle_terms_for` makes for the bill day, and the reason the CYCLE column
#: costs no query per row.
_BILL_RUN_ROW_COLUMNS: tuple[str, ...] = (
    "id",
    "run_no",
    "cycle_id",
    # ⚠ **THE DRAWING SHOWS A CYCLE AS `09-A`, WHICH IS A CODE AND NOT AN ID**
    # (B14 rule 31: no database id is ever the visible value of a field). Before
    # 2026-09-15 this read served `cycle_id` alone, so a screen drawing the
    # drawn column had a uuid and nothing else to put in it.
    "cycle__code",
    "cycle__name",
    "period_start",
    "period_end",
    "status",
    "bill_type",
    "created_at",
    # ── Screen 16's `ALREADY RUN FOR THIS CYCLE` table, entry ⑤ ──────────────
    # ⚠ **THE *no actor column* PANEL UNDER THE OLD PAST-RUNS TABLE WAS REMOVED
    # BY THE BLUEPRINT AS *RULED BY FACT*: its claim is false.** `bill_runs.
    # run_by` exists, is populated and is served — it was served on two REFUSALS
    # and on nothing a clerk could read, which is how a true column came to be
    # documented as absent. The name travels with the id because B14 rule 31
    # forbids a database id being the visible value of a field, and *"Dana Reyes
    # has this cycle open"* is the whole point of the row.
    "run_by_id",
    "run_by__full_name",
    # ⚠ **THIS COLUMN LANDED WHILE THIS READ WAS BEING WRITTEN, AND THE READ
    # SERVED `None` UNDER THIS NAME UNTIL IT DID.** `BR-BIL-1041` (2026-09-14)
    # gave a run the name its clerk types on step 1 — *"September, after the
    # water rate change"* — which is what makes two runs over one period
    # distinguishable to anybody quoting them (`DEF-171` · `DEF-602`).
    "label",
)


def _bill_runs_queryset(
    *,
    q: str = "",
    cycle_id: Any = None,
    status: Any = None,
    year: Any = None,
    bill_type: Any = None,
) -> QuerySet:
    """The tenant's runs, narrowed by screen 27's toolbar. Newest first.

    ⚠ **AN UNREADABLE SCOPE ANSWERS *NOTHING*, NEVER *EVERYTHING*.** A caller
    that sent `f.cycle_id` or `f.year` asked to be narrowed; widening the answer
    because the value could not be parsed would show one cycle's tab every run
    in the utility. BR-SHL-011 says a list URL does not ERROR over its params —
    it does not say it may silently answer a different question. `f.status` needs
    no such guard: it is matched literally against a real column, so an unknown
    word legitimately finds no rows.

    Ordered by period desc, then by creation desc, then by the uuid7 primary key
    — the last two are tiebreakers so a catch-up sub-run sits directly above the
    parent it re-bills, **and so the order is TOTAL**, which is what makes a page
    a stable window over it (`core.pagination.order_terms`' own warning: a page
    over a non-total order shows a clerk one row twice and skips another).

    ⚠ **NO `sort` PARAMETER, AND THAT IS THE DRAWING'S DECISION RATHER THAN A
    GAP.** p146 draws seven plain column headings with no sort affordance on any
    of them, and B14 rule 37 says a drawn figure is an illustration while the
    SHAPE is the specification. Adding sorts nobody drew would be inventing a
    control; `parse_list_params` is called with no `allowed_sorts` so a `?sort=`
    falls back to this order rather than erroring.
    """
    query = BillRun.objects.filter(tenant_id=_tenant_id())
    if cycle_id is not None:
        if not _is_uuid(cycle_id):
            return query.none()
        query = query.filter(cycle_id=cycle_id)
    if year is not None:
        try:
            query = query.filter(period_start__year=int(str(year)))
        except (TypeError, ValueError):
            return query.none()
    if status:
        query = query.filter(status=str(status))
    if bill_type:
        query = query.filter(bill_type=str(bill_type))
    term = str(q or "").strip()
    if term:
        query = query.filter(core_search.matches_any(term, BILL_RUN_SEARCH_FIELDS))
    return query.order_by("-period_start", "-created_at", "-id")


def _bill_run_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compose one page of run rows — THREE grouped queries, whatever its length.

    Nothing here is per run: the counts, the holds and the exceptions each come
    back in one pass keyed by run id, and the cycle's code and the actor's name
    rode in on the row itself along the reviewed FK. A per-row count on a cycle
    with two years of history would be 24 round trips for a tab nobody scrolls,
    and at a T5 tenant's 40,000 accounts it is the difference between a list and
    a timeout (NFR-3 / NFR-5).
    """
    if not rows:
        return []
    run_ids = [row["id"] for row in rows]
    bills = _bill_counts_by_run(run_ids)
    held = _held_counts_by_run(run_ids)
    exceptions = _exception_counts_by_run(run_ids)
    return [
        _bill_run_history_row(
            row,
            bills.get(row["id"], {}),
            held.get(row["id"], 0),
            exceptions.get(row["id"], {}),
        )
        for row in rows
    ]


def bill_runs_list(
    *, cycle_id: Any = None, limit: int = BILL_RUN_LIST_DEFAULT_LIMIT
) -> list[dict[str, Any]]:
    """SET-07D's run history as a bounded LIST — READ ONLY, one tenant.

    ⚠ **THIS IS THE CYCLE DETAIL TAB'S READ AND IT IS NOT SCREEN 27's.** The
    Runs tab on a cycle wants *"the last N for this cycle, newest first"* and
    has no pager to drive one; `bill_runs_page` below is what the Past billing
    runs screen calls, in BR-SHL-011's `page`/`per` grammar with a true total.
    Both compose the same rows through `_bill_run_rows`, so the two can never
    describe a run differently.

    `cycle_id` is the caller: the cycle detail page asks for its own runs. An
    UNREADABLE or unknown id answers the EMPTY list rather than the whole
    tenant's history — see `_bill_runs_queryset` for why.

    ⚠ **Nothing here writes.** `bill_runs`, `invoices`, `bill_run_exclusions`
    and `bill_run_breaks` are read and never touched, which is what makes this
    safe on a GET a clerk may refresh (CLAUDE.md rule 4 / BR-BIL-004: an issued
    bill is immutable, and a read surface that could move one would be the place
    it happened).
    """
    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = BILL_RUN_LIST_DEFAULT_LIMIT
    limit = min(max(limit, 1), BILL_RUN_LIST_MAX_LIMIT)
    rows = list(_bill_runs_queryset(cycle_id=cycle_id).values(*_BILL_RUN_ROW_COLUMNS)[:limit])
    return _bill_run_rows(rows)


def bill_runs_page(
    *,
    q: str = "",
    cycle_id: Any = None,
    status: Any = None,
    year: Any = None,
    page: int = 1,
    per: int = BILL_RUN_LIST_DEFAULT_LIMIT,
    bill_type: Any = None,
) -> dict[str, Any]:
    """Screen 27's table — BR-SHL-011's page grammar with a TRUE total.

    ⚠ **THE OLD READ WAS A CLAMPED `limit` WITH NO TOTAL, AND ITS STATED REASON
    HAS EXPIRED (amended 2026-09-15).** It read: *"a run history grows at the
    TOP, so page 2 of it is not a stable read … there is no pager on the Runs
    tab to drive one either."* The second half was true of the CYCLE tab and is
    still true of `bill_runs_list`; it was never true of screen 27, which draws
    *"Showing 1–34 of 34"* with a rows-per-page control beside it. The first
    half is a real hazard and is answered rather than waved away: the order is
    TOTAL (period, then creation, then the uuid7 key), so a run started between
    two requests shifts rows down by one and nothing is skipped or shown twice
    WITHIN one ordering — the ambiguity a non-total order carries is what makes
    page 2 unstable, and this order has none.

    **`NFR-3` IS THE REASON IT MATTERS AND `NFR-5` IS THE REASON IT CANNOT BE A
    CAP.** `limit` clamped at 200 was correct for a T7 utility and silently
    truncates a T5 one; the drawn pager is how all of a utility's history is
    reachable without a maximum anywhere.

    The envelope the view puts on the wire is `{count, next, previous, results}`
    — `07-frontend/src/api/paginated.ts` is the ONE description of it, and this
    dict is the layer BELOW that boundary, which is the confusion `DEF-WRK-4119`
    was made of. Read that file before typing a client for this.
    """
    per = clamp_page_size(per)
    try:
        page = max(int(str(page)), 1)
    except (TypeError, ValueError):
        page = 1
    query = _bill_runs_queryset(
        q=q, cycle_id=cycle_id, status=status, year=year, bill_type=bill_type
    )
    total = query.count()
    last = max(1, -(-total // per))
    # BR-SHL-011 "never error": a page past the end clamps to the last one
    # rather than 404ing, exactly as `StandardPagination.get_page_number` does
    # for the endpoints DRF pages for us.
    page = min(page, last)
    start = (page - 1) * per
    rows = list(query.values(*_BILL_RUN_ROW_COLUMNS)[start : start + per])
    return {
        "rows": _bill_run_rows(rows),
        "page": page,
        "per": per,
        "total": total,
        "pages": last,
    }


def bill_run_tiles(*, year: Any = None) -> dict[str, Any]:
    """Screen 27's four tiles. Scoped to a YEAR and to nothing else.

    ⚠ **THE YEAR COMES FROM THE REQUEST OR FROM THE DATA, NEVER FROM A CLOCK.**
    The tile reads *"RUNS THIS YEAR"* and billing may not call `timezone.now()`
    at all (BR-TEN-043, gate G6 rule 3). So: `f.year` when the caller chose one,
    otherwise the year of the newest run this tenant has. It is served back as
    `year` so the screen can say which year it is showing rather than asserting
    *this* one — a sentence that states a fact it did not look up is the shape
    six defects were filed for on 2026-09-07.

    ⚠ **THEY DO NOT FOLLOW THE SEARCH OR THE OTHER TWO CHIPS**, which is the
    posture `invoices_rollup` already takes (*"over ALL of the tenant's bills,
    not the current filter"*). A tile that moved when a clerk typed in the
    search box would answer a different question from the one its own label
    asks.

    ⚠ **`longest_run` IS NULL AND THE REASON IS A MISSING COLUMN, NOT A MISSING
    QUERY (`DEF-BIL-5376`).** Nothing in this product records how long a bill run
    took. `bill_runs` carries `created_at` and an `auto_now` `updated_at`; their
    difference is the time until the row was last TOUCHED, which for a run whose
    status now advances gets longer after the run ended. The job record that
    drives a run belongs to `apps.tenancy` and billing may not read it (B1/G6),
    and `invoices.issued_at` is a passed-in business time identical on every bill
    of one pass. A tile filled from any of those would be a figure nobody could
    re-derive, so it is served as an absence and the screen states one.
    """
    tenant_id = _tenant_id()
    chosen: int | None = None
    if year is not None:
        try:
            chosen = int(str(year))
        except (TypeError, ValueError):
            chosen = None
    if chosen is None:
        newest = (
            BillRun.objects.filter(tenant_id=tenant_id)
            .order_by("-period_start")
            .values_list("period_start", flat=True)
            .first()
        )
        chosen = newest.year if newest is not None else None
    if chosen is None:
        return {
            "year": None,
            "runs": {"count": 0, "cycles": 0},
            "bills_issued": {"count": 0, "value": None, "currency": None},
            "exceptions": {"runs": 0, "all_resolved": True},
            "longest_run": None,
        }

    in_year = BillRun.objects.filter(tenant_id=tenant_id, period_start__year=chosen)
    runs_count = in_year.count()
    cycles = in_year.exclude(cycle_id=None).values("cycle_id").distinct().count()

    by_currency = (
        Invoice.objects.filter(
            tenant_id=tenant_id,
            bill_run__period_start__year=chosen,
            status__in=INVOICE_LOCKED_STATUSES,
        )
        .values("currency")
        .annotate(count=Count("id"), value=Sum("total"))
        .order_by()
    )
    bills_count = sum(row["count"] for row in by_currency)
    currencies = {
        row["currency"]: Decimal(row["value"] or 0) for row in by_currency if row["currency"]
    }
    value, currency = _single_currency_total(currencies)

    breaks = (
        BillRunBreak.objects.filter(tenant_id=tenant_id, bill_run__period_start__year=chosen)
        .values("bill_run_id")
        .annotate(outstanding=Count("id", filter=Q(resolution__isnull=True)))
        .order_by()
    )
    exception_runs = list(breaks)
    return {
        "year": chosen,
        "runs": {"count": runs_count, "cycles": cycles},
        "bills_issued": {"count": bills_count, "value": value, "currency": currency},
        "exceptions": {
            "runs": len(exception_runs),
            "all_resolved": not any(row["outstanding"] for row in exception_runs),
        },
        # `DEF-BIL-5376` — no duration is recorded anywhere. See the docstring.
        "longest_run": None,
    }


def _single_currency_total(
    by_currency: dict[str, Decimal],
) -> tuple[str | None, str | None]:
    """A total and its CHAR(3) partner, or two nulls when there is no one name.

    CLAUDE.md rule 2: money travels as the stored decimal string beside its
    currency, never as a float and never as a bare number. Two currencies have
    no single total — `release._amount_and_currency` refuses outright and this
    answers null, because a LIST may not error over one row (BR-SHL-011).
    """
    if len(by_currency) != 1:
        return None, None
    currency, amount = next(iter(by_currency.items()))
    return _decimal_str(amount), currency


def _bill_run_history_row(
    row: dict[str, Any],
    bills: dict[str, Any],
    held: int,
    exceptions: dict[str, int],
) -> dict[str, Any]:
    """One row of screen 27's table (blueprint p146) — RUN · CYCLE · PERIOD ·
    BILLS · VALUE · RUN BY · STATUS, and the facts a clerk's other questions
    need beside them."""
    value, currency = _single_currency_total(bills.get("by_currency", {}))
    return {
        "id": str(row["id"]),
        # OQ-342, CLOSED-RULED 2026-08-23 — *"A: a real series (RUN-0001, like
        # RT-001)"*. ⚠ **THE NOTE SAYING THIS COULD NOT BE PRODUCED IS STALE AND
        # WAS FOR NEARLY A MONTH (`DEF-BIL-5353`)**: `bill_runs.run_no` exists
        # and real runs carry `RUN-0001` upward. NULL only on a run created
        # before the series existed — which the ruling says stays that way (no
        # retro-numbering), and which is why the drawn RUN column must tolerate
        # an absence.
        "run_no": row["run_no"],
        "cycle_id": None if row["cycle_id"] is None else str(row["cycle_id"]),
        # B14 rule 31 — what the drawing actually shows in that column (`09-A`).
        "cycle_code": row.get("cycle__code"),
        "cycle_name": row.get("cycle__name"),
        "period_start": _iso(row["period_start"]),
        "period_end": _iso(row["period_end"]),
        "issued_at": _iso(bills.get("first_issued_at")),
        "accounts": bills.get("accounts", 0),
        "bills_issued": bills.get("bills_issued", 0),
        # ── The drawn VALUE column (`DEF-BIL-5353`, 2026-09-15) ──────────────
        # ⚠ **THE NOTE THAT KEPT MONEY OFF THIS ROW CITED A RULE ABOUT ANOTHER
        # MODULE'S SCREENS.** `BR-MET-078`'s PO wording is *"you dont need late
        # fees in this. so dont have anything related to money when you create
        # route and cycles"* and its subject is r10 SET-07.3, the route and
        # cycle CREATION screens. A billing run's history row is neither, and
        # the blueprint draws the column. The figure is Σ of the run's LOCKED
        # bills — what actually went out — as the stored decimal string beside
        # its CHAR(3) currency (rule 2), null when there is no single currency.
        "value": value,
        "value_currency": currency,
        "held": held,
        # ⚠ **THE STORED COLUMN, AND SINCE 2026-09-15 IT MOVES** — `draft` ·
        # `issuing` · `issued` · `corrected` · `abandoned` (`BR-BIL-1045`,
        # written by `runs.record_run_outcome`). It read `"draft"` on every run
        # this product had ever finished until that day (`DEF-BIL-5352`).
        "status": row["status"],
        "bill_type": row["bill_type"],
        "created_at": _iso(row["created_at"]),
        # The tile's *"runs with exceptions · all resolved"* fact, per row, so a
        # clerk can see WHICH run it was talking about.
        "exceptions": exceptions.get("total", 0),
        "exceptions_outstanding": exceptions.get("outstanding", 0),
        # ── Screen 16's BY column, and the sentence beside the takeover ──────
        "ran_by": None if row.get("run_by_id") is None else str(row["run_by_id"]),
        # Empty while a user is invited and has not named themselves — served
        # as None rather than as "" so a screen can tell *nobody is recorded*
        # from *recorded, and they have no name yet*.
        "ran_by_name": (row.get("run_by__full_name") or None),
        # Screen 16's LABEL column — the run's own name, or null where nobody
        # typed one, which is every run created before `BR-BIL-1041`.
        "label": row.get("label"),
        # ⚠ **NOT `status`, EVEN NOW THAT `status` MOVES.** This answers *is
        # somebody in the middle of this* — the question the takeover control on
        # screen 16 asks — and it is a FACT about the world rather than a column
        # a writer may not have reached yet. A run whose creator crashed before
        # `record_run_outcome` ran is still open, and this says so.
        "is_open": not bills.get("bills_issued", 0),
    }


def run_created_dict(run: BillRun) -> dict[str, Any]:
    """What `POST /billing/runs` answers with.

    11b marks that row **STALE**: A11 promised `{run id, exceptions}` inline and
    B12 r1 requires `202 + job_id` for every ASYNC operation. Creating the row
    is not async — one insert, no work queued — and there is no job runner on
    this deployment at all (TD-17: `celery` is a declared dependency with zero
    `tasks.py`). So the id is answered inline and `job_id` is served **null**
    under its contracted name: "no job was started", which is true, rather than
    an invented id pointing at a poll that would answer nothing.

    `run_id` is NOT also served. `billRunIdOf()` reads `id ?? run_id`, so one of
    them suffices, and two names for one value is the drift DEF-014 is made of.
    """
    return {"id": str(run.pk), "job_id": None, "status": run.status}


# ══════════════════════════════════════════════════════════════════════════
# CR-051 task 1 — `GET /billing/runs/{id}`: ONE RUN, RE-OPENABLE
#
# ⚠ **THIS ROUTE WAS UNMOUNTED AND THE REASON GIVEN FOR IT HAS EXPIRED.**
# `apps/billing/api.py` recorded: *"`GET /billing/runs/{id}` (the status the
# wizard polls, BR-BIL-051) — the poll exists to watch a BACKGROUND batch, and
# there is no background batch (TD-17). A status endpoint whose value can never
# change while the caller watches is a promise of asynchrony this deployment
# does not keep."* CR-051 makes the batch real (`apps/billing/run_jobs.py`), so
# the premise is gone; and the route was ALSO the only way to re-open a finished
# run at all, which was never about asynchrony. Corrected rather than left
# standing (hard-won law 1).
#
# FOUR THINGS, WHICH IS WHAT CR-051 TASK 1 ASKS FOR — *"its phase, its scope,
# its decisions and its counts"*:
#
#   phase     DERIVED FROM EVIDENCE, never from `bill_runs.status`. ⚠ **THE
#             REASON GIVEN HERE — *"the stored column is written draft by
#             create_run and nothing in this module ever moves it"* — WAS TRUE
#             UNTIL 2026-09-15 AND IS NOW HALF TRUE** (`BR-BIL-1045` gives the
#             column five words and one writer, `DEF-BIL-5352`). `phase` STAYS,
#             because it answers a different question: how far through the
#             WIZARD this run got — an issued invoice, a stamped release, an
#             authorised release, a draft — and a run authorised with nothing
#             issued has no status word for that. `status` is served BESIDE it,
#             and serving it beside rather than instead is what made the defect
#             findable in the first place.
#   scope     the run's own columns — cycle, period, bill date, due days, the
#             services it was scoped to, the account for a one-time run.
#   decisions how many `bill_run_decisions` rows this run carries, by case. The
#             CASES, not the choices: *"18 answered"* is what a clerk re-opening
#             a run needs, and the answers themselves are the exceptions
#             endpoint's, which already serves them.
#   counts    accounts, drafts, issued, breaks (outstanding and total) and held,
#             each from the table that owns it.
#
# **NO MONEY, AND THAT IS A RULE HERE, NOT A CHOICE** — BR-MET-078 as hardened
# by CR-029: *"Money never touches these surfaces"*. `bill_run_releases.
# total_amount` and `invoices.total` are each one join away and neither is
# served. The same posture `bill_runs_list` takes, for the same reason.
#
# **BATCHED.** Five queries whatever the run's size: the run, one grouped pass
# over `invoices`, one over `bill_run_exclusions`, one over `bill_run_breaks`,
# one over `bill_run_decisions`. Nothing here is per account.
# ══════════════════════════════════════════════════════════════════════════

#: `phase` — the wizard's own step vocabulary, in the order a run passes through
#: them. Derived; see the block above.
RUN_PHASE_DRAFT = "draft"  # created, nothing calculated
RUN_PHASE_CALCULATED = "calculated"  # drafts exist, nothing authorised
RUN_PHASE_AUTHORISED = "authorised"  # the gate is recorded, nothing issued
RUN_PHASE_ISSUED = "issued"  # at least one bill is out


def _run_phase(*, drafts: int, issued: int, authorised: bool, released: bool) -> str:
    """Which step this run actually reached, from evidence only.

    ORDER MATTERS AND IT RUNS BACKWARDS FROM THE FURTHEST POINT: a run that has
    issued is `issued` even though it also has an authorisation row and drafts,
    because the question a clerk asks on re-opening is *how far did this get*,
    not *what is true about it*.

    `released` and `issued` are asked separately on purpose. A release stamped
    with no bill out is epic TC-13's crash state — authorised, released, and the
    issue pass died — and calling that `issued` would tell a clerk bills went to
    customers who never got one.
    """
    if issued:
        return RUN_PHASE_ISSUED
    if authorised or released:
        return RUN_PHASE_AUTHORISED
    if drafts:
        return RUN_PHASE_CALCULATED
    return RUN_PHASE_DRAFT


def _break_counts(run: BillRun) -> dict[str, Any]:
    """This run's breaks, grouped by stage, in ONE query.

    `outstanding` and `total` are both served because they answer different
    questions: BR-BIL-053 says *"the run cannot enter phase 4 with an unresolved
    break row"*, so `outstanding` is the gate's number — while `total` is what
    happened this morning, and a run that broke 40 accounts and fixed all 40 is
    not the same run as one that never broke.
    """
    rows = (
        BillRunBreak.objects.filter(tenant_id=_tenant_id(), bill_run=run)
        .values("stage")
        .annotate(
            total=Count("id"),
            outstanding=Count("id", filter=Q(resolution__isnull=True)),
        )
        .order_by()  # clear any default ordering out of the GROUP BY
    )
    by_stage = {row["stage"]: row for row in rows}
    return {
        "total": sum(row["total"] for row in by_stage.values()),
        "outstanding": sum(row["outstanding"] for row in by_stage.values()),
        "by_stage": {
            stage: {"total": row["total"], "outstanding": row["outstanding"]}
            for stage, row in sorted(by_stage.items())
        },
    }


def _sent_run_read_lock(run: BillRun) -> dict[str, Any] | None:
    """DEF-BIL-8685 — the BILLED lock over every read this run's sent bills
    priced, as Meter Reads answers it (`metering_seam.read_lock_for_bills`).

    Reads ONLY the `services` key of each bill's frozen snapshot — the one
    `read_ids_on` looks in — never the whole payload, and streams it, so a
    40,000-bill run costs one scan of one key plus one count per 5,000 reads
    (NFR-3). None when Meter Reads cannot answer."""
    from django.db import connection

    from apps.billing import metering_seam

    if connection.vendor == "postgresql":
        # ⛔ `DEF-BIL-8758` — the read ids taken off the snapshots IN SQL (the
        # run's own bills; billing's table): `read_ids_on`'s two places, each
        # service's `read_id` and each meter part's, distinct. Read in Python
        # this was ~2 s of JSON decoding at 40,008 bills, on the bulk run
        # page's first read. Same ids; `read_ids_on` stays the statement of
        # where they live and is what every other caller uses.
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                WITH services AS (
                    SELECT s.value AS entry
                    FROM {Invoice._meta.db_table} i,
                         jsonb_array_elements(
                             CASE WHEN jsonb_typeof(i.bill_payload -> 'services') = 'array'
                                  THEN i.bill_payload -> 'services' ELSE '[]'::jsonb END
                         ) s
                    WHERE i.tenant_id = %s AND i.bill_run_id = %s AND i.status = ANY(%s)
                      AND jsonb_typeof(s.value) = 'object'
                )
                SELECT DISTINCT read_id FROM (
                    SELECT entry ->> 'read_id' AS read_id FROM services
                    UNION ALL
                    SELECT p.value ->> 'read_id'
                    FROM services,
                         jsonb_array_elements(
                             CASE WHEN jsonb_typeof(entry -> 'meter_parts') = 'array'
                                  THEN entry -> 'meter_parts' ELSE '[]'::jsonb END
                         ) p
                    WHERE jsonb_typeof(p.value) = 'object'
                ) ids
                WHERE read_id IS NOT NULL AND read_id <> ''
                """,
                [str(_tenant_id()), str(run.pk), list(INVOICE_LOCKED_STATUSES)],
            )
            read_ids = [row[0] for row in cursor.fetchall()]
        lock = metering_seam.read_lock_for_read_ids(read_ids)
        return None if lock is None else lock.as_dict()
    services = (
        Invoice.objects.filter(
            tenant_id=_tenant_id(), bill_run=run, status__in=INVOICE_LOCKED_STATUSES
        )
        .order_by()
        .values_list("bill_payload__services", flat=True)
        .iterator(chunk_size=2000)
    )
    lock = metering_seam.read_lock_for_bills({"services": entry} for entry in services)
    return None if lock is None else lock.as_dict()


def run_read_lock_dict(run: BillRun) -> dict[str, Any]:
    """`GET /billing/runs/{id}/read-lock` — D1 35's *"Meter reads: Locked"*
    (DEF-BIL-8685): of the reads the SENT bills priced, how many Meter Reads
    holds BILLED.

    ⛔ `DEF-BIL-8809` — taken off `GET /billing/runs/{id}`, where it cost ~1.1 s
    of a 1.2 s read on a sent 40,008-bill run and held up every screen of the
    bulk run page (the run read is what tells the page which step it is on).
    Same answer, same rule for when it is asked: only once the run is released
    and nothing is left to send, so a run in flight never pays for it; null
    before then, or when Meter Reads cannot say."""
    tenant_id = _tenant_id()
    released = BillRunRelease.objects.filter(
        tenant_id=tenant_id, bill_run=run, released_at__isnull=False
    ).exists()
    drafts = Invoice.objects.filter(
        tenant_id=tenant_id, bill_run=run, status=INVOICE_DRAFT
    ).exists()
    return {
        "bill_run_id": str(run.pk),
        "meter_reads": _sent_run_read_lock(run) if released and not drafts else None,
    }


def _active_calculate_dict(run: BillRun) -> dict[str, Any] | None:
    """DEF-BIL-9010 — `{id, status, progress}` of the run's live Calculate job."""
    from apps.billing import run_jobs  # run_jobs imports this module
    from core import jobs as core_jobs

    try:
        job = run_jobs.active_calculate(run)
    except core_jobs.JobsError:
        return None
    if job is None:
        return None
    return {"id": str(job["id"]), "status": job["status"], "progress": job.get("progress")}


def _active_check_dict(run: BillRun) -> dict[str, Any] | None:
    """DEF-BIL-9004 / 9010 — `{id, status, progress}` of the run's whole-run
    Check job while it is queued or running, else None. A Check again on a run
    that already holds drafts read `phase: calculated` and re-opened on Sign
    off with dashes while 40,015 accounts were being re-checked."""
    from core import jobs as core_jobs

    job_id = (run.findings_summary or {}).get("job_id")
    if not job_id:
        return None
    try:
        job = core_jobs.current(job_id)
    except core_jobs.JobsError:
        return None
    if job.get("status") not in (core_jobs.QUEUED, core_jobs.RUNNING):
        return None
    return {"id": str(job["id"]), "status": job["status"], "progress": job.get("progress")}


def run_detail_dict(run: BillRun) -> dict[str, Any]:
    """`GET /billing/runs/{id}` — one run, its phase, its scope and its counts.

    READ ONLY. Nothing here writes, which is what makes it safe on a GET a clerk
    may refresh — and it is the specific thing `GET .../findings` cannot claim
    cheaply, because that one re-runs the whole prepare pass. This is five
    grouped queries over rows that already exist.
    """
    bills = (
        Invoice.objects.filter(tenant_id=_tenant_id(), bill_run=run)
        .values("bill_run_id")
        .annotate(
            accounts=Count("account_id", distinct=True),
            drafts=Count("id", filter=Q(status=INVOICE_DRAFT)),
            issued=Count("id", filter=Q(status__in=INVOICE_LOCKED_STATUSES)),
            first_issued_at=Min("issued_at"),
        )
        # ⚠ THE `order_by` IS LOAD-BEARING, not tidiness, and a BARE
        # `.order_by()` is not enough. Django refuses `.first()` on an
        # aggregating queryset with no ordering outright — *"Cannot use
        # QuerySet.first() on an unordered queryset performing aggregation. Add
        # an ordering with order_by()"* — which tc8 met as a 500 before this
        # line existed. The group is one run, so ordering by the grouped column
        # names the ONE row without letting `Invoice.Meta.ordering` into a GROUP
        # BY it was never meant to be in.
        .order_by("bill_run_id")
        .first()
    ) or {}
    held = BillRunExclusion.objects.filter(
        tenant_id=_tenant_id(), bill_run=run, resolved_at__isnull=True
    ).count()
    breaks = _break_counts(run)
    releases = list(
        BillRunRelease.objects.filter(tenant_id=_tenant_id(), bill_run=run).values_list(
            "released_at", flat=True
        )
    )
    decision_rows = (
        BillRunDecision.objects.filter(tenant_id=_tenant_id(), bill_run=run)
        .values("case")
        .annotate(taken=Count("id"))
        .order_by()  # clear any default ordering out of the GROUP BY
    )
    decisions_by_case = {row["case"]: row["taken"] for row in decision_rows}
    # DEF-BIL-8685 — who signed the run off and when, from the newest release
    # row (BR-BIL-005's record of the five confirmations). A re-opened run knew
    # neither, so Send dropped its "Signed off by … · …" line (D1 32).
    signed = (
        BillRunRelease.objects.filter(tenant_id=_tenant_id(), bill_run=run)
        .select_related("confirmed_by")
        .order_by("-confirmed_at", "-created_at")
        .first()
    )
    return {
        "id": str(run.pk),
        "run_no": run.run_no,
        # DEF-BIL-8680 — the name the clerk typed on Scope, so a run opened from
        # its address shows it on every step (D1 25–36); null when none was typed.
        "label": run.label,
        "signed_off": (
            None
            if signed is None
            else {
                "by": (getattr(signed.confirmed_by, "full_name", None) or None)
                if signed.confirmed_by_id
                else None,
                "at": _iso(signed.confirmed_at),
            }
        ),
        "phase": _run_phase(
            drafts=bills.get("drafts", 0),
            issued=bills.get("issued", 0),
            authorised=bool(releases),
            released=any(stamp is not None for stamp in releases),
        ),
        # DEF-BIL-9010 — a Calculate job still queued or running. `phase` says
        # `calculated` as soon as ONE draft exists, so a run re-opened mid-way
        # opened on Sign off over half its drafts; the page shows the job's
        # progress while this is set. One indexed lookup.
        "calculating": _active_calculate_dict(run),
        # DEF-BIL-9004 / 9010 — the same for a whole-run Check (incl. Check again).
        "checking": _active_check_dict(run),
        # ⛔ `DEF-BIL-8809` — `meter_reads` (D1 35's "Meter reads: Locked",
        # DEF-BIL-8685) is NOT on this read any more: it is
        # `GET …/read-lock` (`run_read_lock_dict`). On a sent 40,008-bill run
        # it was ~1.1 s of this read's 1.2 s — every read id off 40,008
        # frozen snapshots, then one count in Meter Reads — and this read is
        # the one every screen of the bulk run page waits for, and the one a
        # running batch polls. The Sent card is the only screen that draws it.
        # ⚠ **THIS COMMENT READ *"THE STORED COLUMN, WHICH NOTHING IN THIS
        # MODULE EVER MOVES OFF draft"* UNTIL 2026-09-15 AND IT WAS TRUE**
        # (`DEF-BIL-5352`). `BR-BIL-1045` gives the column five words and one
        # writer, so it now says what happened to the run. It is still served
        # BESIDE `phase` rather than instead of it: `phase` answers *how far did
        # this get through the wizard* and `status` answers *what became of it*,
        # and a run authorised with nothing issued needs both to be described.
        "status": run.status,
        "scope": {
            "cycle_id": None if run.cycle_id is None else str(run.cycle_id),
            "period_start": _iso(run.period_start),
            "period_end": _iso(run.period_end),
            "bill_date": _iso(run.bill_date),
            "due_days": run.due_days,
            "bill_type": run.bill_type,
            "services": run.scope_services,
            "account_id": None if run.scope_account_id is None else str(run.scope_account_id),
            "parent_run_id": None if run.parent_run_id is None else str(run.parent_run_id),
        },
        "decisions": {"taken": sum(decisions_by_case.values()), "by_case": decisions_by_case},
        "counts": {
            "accounts": bills.get("accounts", 0),
            "drafts": bills.get("drafts", 0),
            "bills_issued": bills.get("issued", 0),
            "breaks": breaks["outstanding"],
            "breaks_total": breaks["total"],
            "breaks_by_stage": breaks["by_stage"],
            "held": held,
        },
        # CR-051 task 9 — what the last BACKGROUND findings pass counted, or
        # null when none has run. NOT a cache of the case lists; see the
        # column's own comment in models.py and OQ-843.
        "findings_summary": run.findings_summary,
        "issued_at": _iso(bills.get("first_issued_at")),
        "created_at": _iso(run.created_at),
    }


def run_breaks_dict(run: BillRun, *, include_resolved: bool = False) -> dict[str, Any]:
    """`GET /billing/runs/{id}/breaks` — BR-BIL-053's list, from the TABLE.

    ⚠ **THIS READ WAS IMPOSSIBLE UNTIL CR-051 AND THE REASON IS WORTH KEEPING.**
    `apps/billing/api.py` recorded it: *"there is no `GET /billing/runs/{id}/
    breaks`, because serving one would mean CALCULATING inside a read, which
    writes drafts."* That was exactly right while the breaks lived only in
    `CalculatedRun.breaks`. Migration 0026 gives them a table, so this reads
    rows and writes nothing — and the clerk who navigates away, logs out or
    hands over at the end of a shift comes back to the same list.

    **TWO PEOPLE CAN WORK IT** for the same structural reason: the list is
    SERVER-SIDE, so both see the same rows and the same resolutions, and neither
    is looking at a copy that went stale when the other fixed something. There
    is no claim or assignment on a row — that would be a rule nobody has given —
    and this endpoint does not invent one.

    OUTSTANDING BY DEFAULT (BR-BIL-053's own word), because that is the work
    list. `?f.resolved=all` includes the ones a later pass drafted, which is how
    a supervisor answers *"what did this run struggle with?"* after it is over.

    Ordered by stage then account number, so a clerk fixing every missing read
    at once finds them together — BR-BIL-040's whole purpose in naming stages.
    """
    rows = BillRunBreak.objects.filter(tenant_id=_tenant_id(), bill_run=run)
    if not include_resolved:
        rows = rows.filter(resolution__isnull=True)
    listed = list(rows.order_by("stage", "account_no").values())
    return {
        "bill_run_id": str(run.pk),
        "breaks": [
            {
                "id": str(row["id"]),
                "account_id": str(row["account_id"]),
                "account_no": row["account_no"],
                "stage": row["stage"],
                "reason": row["reason"],
                "detail": row["detail"],
                "retryable": row["retryable"],
                # NULL means OUTSTANDING — the clerk's work list.
                "resolution": row["resolution"],
                "job_id": None if row["job_id"] is None else str(row["job_id"]),
                "raised_at": _iso(row["created_at"]),
                "updated_at": _iso(row["updated_at"]),
            }
            for row in listed
        ],
        "break_count": len(listed),
        "breaks_by_stage": {
            stage: [row["account_no"] for row in listed if row["stage"] == stage]
            for stage in sorted({row["stage"] for row in listed})
        },
        "includes_resolved": include_resolved,
    }


def cycle_terms_for(run: BillRun) -> tuple[int | None, int | None]:
    """The run's cycle's `(bill_day, due_days)` DEFAULTS, or `(None, None)`.

    ⚠ **IT ANSWERED A `bill_date` UNTIL 2026-08-23 AND NOW ANSWERS A `bill_day`
    (OQ-344).** `cycles.bill_date` was a stored calendar date from the previous
    column generation and metering 0023 dropped it; D9's surviving default is a
    DAY-OF-MONTH, and `runs.effective_bill_date` turns it into this run's date
    by the ruled rule — *"the bill day, in the month after the period ends"*.

    Read along the REVIEWED cross-module FK `bill_runs.cycle_id → metering.Cycle`
    (B2 §2 / DB-16) as a `values_list`, so nothing here instantiates a metering
    model or imports one (G6). `apps/billing/issue.py` holds the same read
    privately for the due-date derivation — REPORTED rather than reached into,
    because that file is 🔒 and a published metering selector taking a cycle id
    (which metering has not got) is the shape that should replace both.
    """
    row = (
        BillRun.objects.filter(tenant_id=_tenant_id(), pk=run.pk)
        .values_list("cycle__bill_day", "cycle__due_days")
        .first()
    )
    return row if row else (None, None)


def prepared_for(
    run: BillRun,
    *,
    resume_skip: Any = None,
    only_accounts: Any = None,
    on_account: Any = None,
    check_categories: Any = None,
    quiet_account_ids: Any = None,
) -> Any:
    """`runs.PreparedRun` for this run — the whole of what S31.2 and S31.3 show.

    `resume_skip` is CR-051 task 11's checkpoint predicate and is None on every
    call but one: a re-delivered calculate JOB, which has already finished some
    of these accounts and must not pay the gather for them twice. It is passed
    straight through to `runs.prepare_run`, which is where its contract lives.
    **`GET /billing/runs/{id}/findings` never sets it** — a findings screen that
    quietly omitted the accounts a previous pass had drafted would show a clerk
    a run that had shrunk.

    Recomputed on every call and cached nowhere. A prepare pass reads meters,
    plans and accounts as they stand, and a clerk who fixes a plan and reloads
    must see the fix; a cached findings set would show them the world as it was
    when they first opened the wizard.

    The SERVICE date is **the bill date the clerk typed on S31 step 1**, and the
    cycle's own DEFAULT only when nobody typed one — BR-BIL-070, PO ruling
    2026-08-11 closing OQ-122 option A, verbatim *"A Store what they type and use
    it"*. `runs.effective_bill_date` is the one place that resolution lives; this
    function does not re-implement it.

    ⚠ **THE DEFAULT IS DERIVED SINCE OQ-344 (PO 2026-08-23)**: the cycle's bill
    DAY placed in the month after the period ends, because `cycles.bill_date` no
    longer exists (metering 0023). Worked: bill day 5, period 1–31 Aug → 5 Sep.

    **Worked, and it changes what the run prices at:** cycle 08-A is dated
    1 Aug, the clerk types 3 Aug, and a tariff version effective 2 Aug exists.
    The run now prices against the 2-Aug version. Before the ruling it priced
    against whatever was in force on 1 Aug and the typed date vanished.

    NEITHER date present refuses here, and refusing is the whole point:
    BR-RAT-007 prices on the service date, so a guessed one silently selects a
    different tariff version, and there is no clock in this path to guess with
    anyway (BR-TEN-043 / gate G6).
    """
    if run.cycle_id is None:
        # A ONE-TIME run (US-BIL-010..014, migration 0021) has no cycle and
        # therefore no population to prepare: `prepare_run` scopes on
        # `units_in_cycle`, and asking it for the units of cycle NULL would
        # return an empty run rather than an error — a findings screen showing
        # "0 accounts ready" for a bill that is really about ONE named customer.
        # Its own preview is `POST /billing/one-time/preview`.
        raise errors.BizError(
            errors.BIZ_STATE,
            br_ref="BR-BIL-020",
            message_key="billing.oneTime.notACycleRun",
            params={"run_id": str(run.pk), "bill_type": run.bill_type},
        )
    cycle_bill_day, _due_days = cycle_terms_for(run)
    bill_date = runs.effective_bill_date(run.bill_date, cycle_bill_day, run.period_end)
    if bill_date is None:
        raise errors.BizError(
            errors.BIZ_COMPLETENESS,
            br_ref="BR-BIL-024",
            message_key="billing.run.cycle_has_no_bill_date",
            params={"run_id": str(run.pk)},
        )
    scope = run.scope_services
    # BR-BIL-1053 — the payment checks need the run's due date too; None when
    # neither the run nor its cycle says how many days to pay (no guess).
    due_days = runs.effective_due_days(run.due_days, _due_days)
    due_date = bill_date + timedelta(days=due_days) if due_days is not None else None
    # PO 2026-09-30 (changes rows 45–46) — a clerk's accepted suggestion for a
    # possible rollover or a ×1 multiplier is fed to THIS pass, and only an
    # accepted one: `runs._ANSWERS` is empty on every other caller.
    from apps.billing import decisions

    answers = decisions.anchor_answers_for(run)
    answers.update(
        {("*", "", case): choice for case, choice in decisions.standing_anchor_answers(run).items()}
    )
    token = runs.open_answers(answers)
    try:
        return _prepared(
            run,
            bill_date,
            due_date,
            scope,
            resume_skip,
            only_accounts,
            on_account,
            check_categories,
            quiet_account_ids,
        )
    finally:
        runs.close_answers(token)


def _prepared(
    run,
    bill_date,
    due_date,
    scope,
    resume_skip,
    only_accounts,
    on_account,
    check_categories=None,
    quiet_account_ids=None,
):
    """`prepared_for`'s pass, with the run's recorded answers open around it."""
    return runs.prepare_run(
        cycle_id=run.cycle_id,
        period_start=run.period_start,
        period_end=run.period_end,
        service_date=bill_date,
        # None means "no scope was recorded"; an EMPTY list means "the clerk
        # chose no services", which is a different run and must not widen.
        scope_services=None if scope is None else tuple(scope),
        resume_skip=resume_skip,
        # 🔒 BR-BIL-1055 (PO 2026-09-30, *"this si correct"* to *"The period
        # end: $3.25"*) — the rate VERSION is the one in force at the PERIOD
        # END; the bill date above stays the documents' date and drives the
        # due date. SUPERSEDES the pricing half of BR-BIL-070 (`DEF-BIL-8214`).
        # Worked: $3.25 until Oct 1, $3.50 from Oct 1; period ends Sep 30,
        # bill date Oct 1 → $3.25. HUMAN-REVIEW-PENDING — ledger row
        # 2026-09-30 *"B16"*.
        price_date=run.period_end,
        only_accounts=only_accounts,
        payment_window=(bill_date, due_date),
        on_account=on_account,
        check_categories=check_categories,
        quiet_account_ids=quiet_account_ids,
    )


def reading_dict(reading: Any) -> dict[str, Any]:
    """`contracts.ServiceReading`, as S31.2 renders it (CLAUDE.md rule 3).

    `consumption` is `{amount, unit}` or null — NEVER a bare number and never a
    zero standing in for a missing read. `prior_read` / `current_read` are on
    the dataclass and are deliberately not serialised: no screen consumes them
    yet, and a key nothing reads is a contract nobody agreed to. Adding them
    later is additive; guessing what a screen wants to do with them is not.
    """
    consumption = reading.consumption
    return {
        "service_code": reading.service_code,
        "service_id": reading.service_id,
        "consumption": (
            None
            if consumption is None
            else {"amount": _decimal_str(consumption.amount), "unit": consumption.unit}
        ),
        "estimated": bool(reading.estimated),
        "absent_reason": reading.absent_reason,
    }


def ready_account_dict(data: Any) -> dict[str, Any]:
    """One READY account — the `contracts.AccountBillingData` members S31.2
    renders, under their own names.

    The dataclass carries more than this (`tax_exempt`, the tariffs, the taxes,
    the fees, the print snapshot). They are not served because no screen reads
    them and two of them are money-shaped: a fee list on a preview panel would
    read as "this is what they will be charged", which phase 1 does not know.
    """
    return {
        "account_id": data.account_id,
        "account_no": data.account_no,
        "behavior_class": data.behavior_class,
        "currency": data.currency,
        "rate_plan_id": data.rate_plan_id,
        "rate_plan_name": data.rate_plan_name,
        "rate_plan_version": data.rate_plan_version,
        "service_days": data.service_days,
        "cycle_days": data.cycle_days,
        "readings": [reading_dict(reading) for reading in data.readings],
    }


def account_problem_dict(problem: Any) -> dict[str, Any]:
    """`runs.AccountProblem`, including the `stage` added 2026-08-11.

    BR-BIL-040 puts a finding in the tab that owns its stage's inputs, and the
    reason→stage map (`runs.STAGE_BY_REASON`) is the SERVER's. Serving `stage`
    is what let S31.2 delete its own copy of that map. A null stage is a real
    answer — the problem is not a stage failure — and the screen renders those
    on the Consumers tab where the epic puts them.
    """
    return {
        "reason": problem.reason,
        "detail": problem.detail,
        "account_id": problem.account_id,
        "account_no": problem.account_no,
        "unit_id": problem.unit_id,
        "service_code": problem.service_code,
        "stage": problem.stage,
    }


def findings_dict(run: BillRun) -> dict[str, Any]:
    """`GET /billing/runs/{id}/findings` — `runs.PreparedRun`, whole.

    NOT PAGINATED, deliberately, where every list endpoint in this API is
    (11b G5). `PreparedRun` is not a queryset: it is one in-memory pass over
    the run's accounts, and its three lists are the DENOMINATOR the S31.2 KPI
    strip counts ("480 of 500"). A page of it would make `ready.length` a page
    size, and the screen would confidently report the wrong number of accounts.
    The set is bounded by the cycle's own size, which is the same bound the
    prepare pass already works within.

    ⚠ **THIS SCREEN IS THE PREPARE PASS, MEASURED, AND THAT IS WHAT IT COSTS.**
    At 1,000 accounts the pass is 66,053 SQL statements and this endpoint is
    66,054 — one apart (CR-051 task 26). So a clerk pays for the whole pass on
    every refresh, and at that size waits about two minutes.

    **It may not be fixed by storing the answer.** PO ruling, verbatim: *"it is
    dyanmic, so at the time of compute if data is changed, process will
    dynamically use it becuase it will collect data at that instansce"* — a
    clerk who fixes a plan and reloads must see the fix. `OQ-843` is CLOSED on
    that ruling — RECOMPUTE — and it ends *"A lane may not reopen this by
    proposing a cache."*

    What it DID get is task 22's within-pass memo, which is a different thing
    (it dies before the request returns) and which cut the pass by 26% here as
    everywhere. The same ruling asked for exactly that: *"make the pass FASTER
    (plural seams, bulk write), never cache it."* `apps/billing/seam_batch.py`
    states the boundary and `tc18` guards both halves of it.
    """
    prepared = prepared_for(run)
    return {
        "cycle_id": prepared.cycle_id,
        "period_start": prepared.period_start.isoformat(),
        "period_end": prepared.period_end.isoformat(),
        "service_date": prepared.service_date.isoformat(),
        "cycle_days": prepared.cycle_days,
        "scope_services": (
            None if prepared.scope_services is None else list(prepared.scope_services)
        ),
        # The honest denominator: ready plus blocked, deduplicated on account.
        "account_count": prepared.account_count,
        "ready": [ready_account_dict(data) for data in prepared.ready],
        "blocked": [account_problem_dict(problem) for problem in prepared.blocked],
        "decisions": [account_problem_dict(problem) for problem in prepared.decisions],
        # `BR-BIL-1025` — the FOURTH list, and it is deliberately not folded
        # into `blocked`. These accounts were examined and had nothing to
        # charge; the screen says so in words (*nothing to bill this period*)
        # rather than showing an empty table or, worse, an exception row for
        # the correct state. `account_count` counts them, so the denominator
        # stays honest.
        "silent": [account_problem_dict(problem) for problem in prepared.silent],
    }


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN 16 · SCOPE — the resolver and its counts card
# (blueprint §03 entry 16, `CR-105-BRC03-s03-element-inventory.md` §5.1)
# ═══════════════════════════════════════════════════════════════════════════
#
# The drawing's *Which accounts* dropdown reads `Every account in the cycle`
# with the helper *"Or a route, an area, or a named set."* — and the card
# beneath it (`WHAT THIS COVERS`) answers five figures. The drawing's own note
# on that card is the contract this section is written to: **every figure is a
# COUNT. No money, and no forecast.** Resolving scope FOR REAL costs the
# measured 137 ms per account (§03 p034), so a card that previewed money would
# pay for the whole run to draw a header.
#
# ⚠ **THIS RESOLVES; IT DOES NOT SCOPE A RUN.** Nothing here creates, stores or
# narrows a `bill_runs` row. The run-creation path is another file, and until
# its idempotency key carries the scope a NARROWED run is refused here BY
# STATEMENT rather than offered — see `SCOPE_KEY_LIMIT` below.

#: The scope kinds screen 16 draws. `cycle` is the drawn default (*"Every
#: account in the cycle"*) and the other three are the helper's own list.
SCOPE_CYCLE = "cycle"
SCOPE_ROUTE = "route"
SCOPE_AREA = "area"
#: Drawn, and there is NO STORED CONCEPT OF ONE anywhere in this product — no
#: table, no seam, no screen. It is declared so the surface is honest about the
#: gap instead of silently offering three of four; asking for it answers the
#: absence rather than an empty set, which would read as *"that named set has
#: nobody in it"*. `DEF-BIL-5295`.
SCOPE_NAMED_SET = "named_set"
SCOPE_KINDS: tuple[str, ...] = (SCOPE_CYCLE, SCOPE_ROUTE, SCOPE_AREA, SCOPE_NAMED_SET)

#: `accounts.kind` for a master account — BR-CUS-068's own vocabulary, read off
#: the queryset `customers.accounts_for_bill_run` publishes FOR THIS POPULATION.
#: ⚠ It is one filter on a seam's own answer and not a join, but it is still
#: this module naming another module's column value: the durable shape is
#: customers publishing a population count and it is REPORTED, not invented
#: here (`DEF-BIL-5296`).
CUSTOMERS_MASTER_KIND = "master"


def _unavailable(code: str, br_ref: str, detail: str) -> dict[str, Any]:
    """One stated absence, in the shape every billing read already serves.

    ⚠ **`detail` IS CLERK-FACING AND CARRIES NO PROVENANCE** — no route, no
    rule id, no defect id, no module path (CR-016 / G28). The provenance goes
    in `br_ref` and in the comment beside the call, where support can still
    reach it and a clerk never does.
    """
    return {"code": code, "br_ref": br_ref, "detail": detail}


#: Why a run narrowed to a ROUTE, an AREA or a NAMED SET still cannot be
#: COMMITTED, stated once. ⚠ **AMENDED 2026-09-14 (`DEF-BIL-5283` fixed for
#: SERVICES only) — AND THE REASONING IT REPLACES IS KEPT, BECAUSE IT IS STILL
#: TRUE OF THREE OF THE FOUR SCOPE KINDS.**
#:
#: It read: *"`runs.create_run` composes its idempotency key from cycle + period
#: and NOTHING ELSE, so a run narrowed to a route, an area or a subset of
#: services consumes the whole cycle-period key. The second narrowed run over
#: the same period is then refused as a duplicate, no exclusion row is written
#: for the accounts it never reached, they never enter the held queue, and no
#: catch-up ever bills them."* Every clause of that is still the consequence;
#: what changed is WHICH narrowings reach it.
#:
#: **SERVICES ARE NOW IN THE KEY** — `idempotency.bill_run_key(scope_services=…)`
#: appends `|scope|<sorted codes>`, under BR-BIL-005's signed *"key = parent key
#: + scope"* — so a Water-only September run and a Sewer-only September run are
#: two keys and both bill.
#:
#: ⚠ **ROUTE, AREA AND NAMED SET ARE NOT, AND FLIPPING THEM TOO WOULD RE-OPEN
#: THE HOLE.** The reason is a column rather than a key: `bill_runs` persists
#: `scope_services` and `scope_account` and NOTHING for a route, an area or a
#: named set, and `create_run` takes no such argument — so there is nothing for
#: a key to carry and nothing a later reader could use to tell two of them
#: apart. The scope chooser may SHOW them; the run may not be committed on one.
SCOPE_KEY_LIMIT = "run_key_does_not_carry_the_scope"


def _scope_key_refusal() -> dict[str, Any]:
    return _unavailable(
        SCOPE_KEY_LIMIT,
        "BR-BIL-005",
        # ⚠ SIX WORDS A SENTENCE, TWO SENTENCES, AND NO RATIONALE — B14 rule 33.
        # The reasoning a support engineer needs is in `SCOPE_KEY_LIMIT` above,
        # where it belongs: *why the product works this way* is zero words on
        # screen, and *what it costs to ignore this* is a paragraph.
        "Routes and areas cannot be billed alone. Bill the whole cycle.",
    )


def _scope_units(
    *,
    cycle_id: Any,
    kind: str,
    scope_ids: Sequence[Any],
    scope_services: tuple[str, ...] | None,
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """`(cycle units, scoped units, absences)` — the two populations screen 16
    draws side by side, and every seam that could not be reached.

    ⚠ **THE CYCLE'S UNITS ARE ASKED FOR FIRST AND THE SCOPE INTERSECTS THEM,
    NEVER THE OTHER WAY ROUND.** A route can hold a unit this cycle does not
    bill (a route serves reads, a cycle serves bills, and BR-MET-033 lets them
    diverge). Resolving route-first would put that unit in a run the cycle
    never covered, which is a bill nobody asked for; intersecting means the
    cycle is always the ceiling and the scope can only ever take rows away.
    """
    absences: list[dict[str, Any]] = []
    units_in_cycle = _resolve("metering", "units_in_cycle")
    if units_in_cycle is None:
        # ⚠ **A PLAIN `BillingRuleError`, WITH NO `message_key` OF ITS OWN, AND
        # THAT IS THE POINT.** The first draft named two brand-new catalogue
        # keys and `G32` and `G18` both went red on them: a raised key with no
        # catalogue entry renders to a clerk as SILENCE, because server detail
        # text has not reached a screen since the 2026-08-19 ruling. Writing the
        # sentence would have meant a new key in all ELEVEN catalogues for a
        # refusal that can only fire if a whole module has stopped publishing.
        # `_as_catalog_refusal` already renders this as `billing.run.refused`,
        # which is the same sentence `runs.scope_account_count` gives the same
        # condition four lines from where it resolves the same two seams.
        raise BillingRuleError(
            "metering has not published units_in_cycle, so the run's scope "
            "cannot be resolved. A run over an unknown scope is not a run."
        )
    cycle_units = [
        str(unit_id)
        for unit_id in units_in_cycle(
            cycle_id,
            service_codes=None if scope_services is None else list(scope_services),
        )
    ]
    if kind == SCOPE_CYCLE:
        return cycle_units, cycle_units, absences

    if kind == SCOPE_NAMED_SET:
        # Declared on the drawing, modelled nowhere. Answering the cycle's own
        # units would be a silent widening; answering none would read as an
        # empty named set. So: the cycle's units are NOT narrowed and the
        # surface says the narrowing did not happen. `DEF-BIL-5295`.
        absences.append(
            _unavailable(
                "named_sets_do_not_exist",
                "BR-BIL-015",
                "Named sets are not built yet.",
            )
        )
        return cycle_units, cycle_units, absences

    wanted = {str(value) for value in scope_ids if str(value)}
    if not wanted:
        absences.append(
            _unavailable(
                "no_scope_chosen",
                "BR-SHL-011",
                "Nothing was chosen to narrow to.",
            )
        )
        return cycle_units, cycle_units, absences

    route_ids: list[str] = list(wanted)
    if kind == SCOPE_AREA:
        routes_list = _resolve("metering", "routes_list")
        if routes_list is None:
            absences.append(
                _unavailable(
                    "areas_cannot_be_resolved",
                    "BR-MET-072",
                    "Areas cannot be read now.",
                )
            )
            return cycle_units, cycle_units, absences
        # One call for the whole area selection — the routes seam takes a
        # multi-select area filter (BR-MET-072, OR-combined, child areas
        # included) and a cycle filter, which is exactly this question.
        route_ids = [
            str(row["id"])
            for row in routes_list(filters={"cycle": str(cycle_id), "area": sorted(wanted)})
            if row.get("id")
        ]
        if not route_ids:
            return cycle_units, [], absences

    members_of = _resolve("metering", "route_members")
    if members_of is None:
        absences.append(
            _unavailable(
                "routes_cannot_be_resolved",
                "BR-MET-033",
                "Routes cannot be read now.",
            )
        )
        return cycle_units, cycle_units, absences

    in_cycle = set(cycle_units)
    scoped: set[str] = set()
    for route_id in route_ids:
        for member in members_of(route_id) or ():
            unit_id = str(member.get("unit_id") or "")
            if unit_id and unit_id in in_cycle:
                scoped.add(unit_id)
    # Sorted for the same reason `units_in_cycle` sorts: a scope resolved twice
    # answers the same population in the same order, so a clerk who re-opens
    # the card is reading the same run they were reading a minute ago.
    return cycle_units, sorted(scoped), absences


def scope_resolution(
    *,
    cycle_id: Any,
    kind: str = SCOPE_CYCLE,
    scope_ids: Sequence[Any] = (),
    scope_services: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Screen 16's `SCOPE` group and its `WHAT THIS COVERS` card. READ ONLY.

    **EVERY FIGURE IS A COUNT.** The drawing's own note — *"no money, and no
    forecast"* — is the rule, and it is a cost rule before it is a taste rule:
    the prepare pass measures 137 ms per account, so a card that showed what a
    scope was WORTH would pay for the run to draw its header (§03 p034: 40,000
    accounts ≈ 91 minutes). Nothing here prices, drafts or writes.

    **TWO UNIT NUMBERS, NOT ONE**, exactly as the card draws them: the units the
    cycle covers and the accounts that would be billed. The gap between them is
    where every master-account failure lives (§03 p091–p094) and no screen in
    this product has ever shown both.

    ⚠ **`committable` IS FALSE FOR A ROUTE, AN AREA OR A NAMED SET, AND THAT IS
    A REAL REFUSAL RATHER THAN A TODO — amended 2026-09-14.** It was false for
    EVERY narrowing until `DEF-BIL-5283` was fixed: the run's idempotency key
    was cycle + period and carried no scope, so a Water-only or route-only run
    CONSUMED the key for that period and the rest of the cycle was then refused
    as a duplicate — with no exclusion rows written, so those accounts never
    reached the held queue and no catch-up ever billed them. A scope chooser
    offered over that key is a revenue hole with a dropdown on it.

    **A SERVICE SCOPE IS NOW KEYED** (`bill_run_key(scope_services=…)`, under
    BR-BIL-005's signed *"key = parent key + scope"*) and is committable. **The
    other three are not**, and the reason is a COLUMN rather than a key:
    `bill_runs` persists nothing for a route, an area or a named set. Closing
    those needs the schema, and it is REPORTED rather than assumed.

    THREE COUNTS ARE SERVED NULL AND SAY SO — meters this cycle, sub-meters, and
    points with no meter. Every one needs *"which meters stand on these service
    points"* for a page of points at once, and the assets seam answers that one
    service point at a time (`asset_ids_for_service_point`). A 1,502-unit cycle
    would pay ~1,600 round trips to draw three numbers on a header, which is the
    N+1 this card exists to avoid. A null with a reason beside it is honest; a
    number bought at that price is not, and a ZERO would be a claim. Serving the
    figure needs a bulk seam from assets and that is REPORTED (`DEF-BIL-5297`).
    """
    kind = kind if kind in SCOPE_KINDS else SCOPE_CYCLE
    services = (
        None
        if scope_services is None
        else tuple(str(code) for code in scope_services if str(code))
    )
    cycle_units, scoped_units, absences = _scope_units(
        cycle_id=cycle_id, kind=kind, scope_ids=scope_ids, scope_services=services
    )

    accounts_for = _resolve("customers", "accounts_for_bill_run")
    if accounts_for is None:
        raise BillingRuleError(
            "customers has not published accounts_for_bill_run, so the run "
            "cannot resolve who is billed."
        )
    population = accounts_for(scoped_units) if scoped_units else None
    accounts_to_bill = 0 if population is None else int(population.count())
    master_accounts = (
        0 if population is None else int(population.filter(kind=CUSTOMERS_MASTER_KIND).count())
    )

    # The service chips the card draws are READ-ONLY and are NOT a chooser
    # (§03 p047, and the red band on p092 says why). One query for the whole
    # population, never one per unit.
    points_for = _resolve("metering", "service_points_for_units")
    service_units: dict[str, set[str]] = {}
    service_points = None
    if points_for is None:
        absences.append(
            _unavailable(
                "services_cannot_be_read",
                "BR-MET-033",
                "Services cannot be read now.",
            )
        )
    else:
        by_unit = points_for(scoped_units) or {}
        service_points = 0
        for unit_id, points in by_unit.items():
            for point in points:
                code = point.get("service")
                if not code:
                    continue
                service_points += 1
                service_units.setdefault(str(code), set()).add(str(unit_id))

    # ⚠ THE THREE METER FIGURES. Null, with the reason stated, rather than an
    # N+1 or a zero — see the docstring. `DEF-BIL-5297`.
    absences.append(
        _unavailable(
            "meter_counts_not_available_here",
            "BR-AST-004",
            "Meter counts are not shown yet.",
        )
    )

    # ⚠ **`DEF-BIL-5283`, HALF-CLOSED ON PURPOSE.** A SERVICE narrowing is now
    # carried by the run's idempotency key, so it is committable; a route, an
    # area or a named set is not, because `bill_runs` has no column to persist
    # one and `create_run` takes no argument for it. Flipping all four together
    # would have re-opened the revenue hole for three of them — which would have
    # looked exactly like the fix working, because the SERVICE case (the one
    # anybody would test) bills correctly either way.
    # ⚠ **AND FROM 2026-09-30 A SERVICE NARROWING IS NOT COMMITTABLE EITHER**
    # (bulk bill run plan B3). The PO removed the services filter — *"which
    # servcies to be billed in unit /account is decied at run time"* — and
    # `runs.create_run` no longer takes one, so a run created after this card
    # said "committable" for Water-only would bill the whole cycle.
    unkeyable = kind != SCOPE_CYCLE
    narrowed_to_services = services is not None
    if unkeyable:
        absences.append(_scope_key_refusal())

    return {
        "cycle_id": None if cycle_id is None else str(cycle_id),
        "scope": {
            "kind": kind,
            "ids": [str(value) for value in scope_ids if str(value)],
            "services": None if services is None else list(services),
        },
        # Named `counts` and holding nothing else, so a later lane cannot fold a
        # money figure in beside them without moving it out of a key that says
        # what it is.
        "counts": {
            "units_in_cycle": len(cycle_units),
            "units_in_scope": len(scoped_units),
            "accounts_to_bill": accounts_to_bill,
            "master_accounts": master_accounts,
            "service_points": service_points,
            "meters_this_cycle": None,
            "sub_meters": None,
            "points_with_no_meter": None,
        },
        "services": [
            {"code": code, "units": len(units)}
            for code, units in sorted(service_units.items(), key=lambda item: item[0])
        ],
        #: FALSE while the run's key could not tell this narrowing from the
        #: whole cycle — see `SCOPE_KEY_LIMIT`. A SERVICE scope is keyed since
        #: `DEF-BIL-5283`; a route, an area and a named set are not.
        "committable": not unkeyable and not narrowed_to_services,
        "unavailable": absences,
    }


# ═══════════════════════════════════════════════════════════════════════════
# SCREEN 17 · CHECK — the band strip and the KPI strip, COUNTED ON THE SERVER
# (blueprint §03 entries 17.L2 and 17.L3, inventory §3)
# ═══════════════════════════════════════════════════════════════════════════
#
# ⚠ **WHY THIS EXISTS: EVERY CHIP ON THAT SCREEN IS `.length` OF AN ARRAY THE
# BROWSER WAS SENT** (`DEF-BIL-5258`). The findings read is unpaginated by
# declared design because its three lists are the DENOMINATOR the strip counts,
# so the whole population travels on every refresh — measured at 66,053 SQL
# statements and ten thousand rows on the wire at 10,000 accounts. Serving the
# counts SEPARATELY is what dissolves that argument: once the numbers arrive as
# numbers, the row list is free to page (B14 rule 16) and the browser stops
# being the thing that adds up a utility's billing run.
#
# ⛔ **AND IT IS NOT A CACHE.** `OQ-843` is CLOSED on a PO ruling — *"it is
# dyanmic, so at the time of compute if data is changed, process will
# dynamically use it"* — and ends *"A lane may not reopen this by proposing a
# cache."* This recomputes, exactly like the findings read beside it. What it
# saves is the WIRE and the browser's arithmetic, not the pass.
#
# ── THE ARITHMETIC RULE, AND IT IS COUNTER-INTUITIVE ────────────────────────
# **A TAG COUNTS CASES. A BAND COUNTS ACCOUNTS.** One account needing two
# actions appears in two chips, because a chip is an ACTION and both actions
# have to be taken. So the tags under a band sum to MORE than the band, on
# purpose (§03 p041/p046: twelve accounts raise nineteen case rows), while the
# BAND ties to the cycle — *"Nobody is missing"*. Every check written against
# this asserts **sum(tags) ≥ band, NEVER equality**; a tag row summing exactly
# to its band has been misread (`DEF-BIL-5273`).

#: The seven bands, in the drawn order — *ordered by obligation, so a clerk is
#: finished when the first band is empty* (§03 p040). The three indented ones
#: are sub-partitions of Held and say so in `partitions`.
BAND_NEEDS_YOU = "needs_you"
BAND_BY_DEFAULT = "answered_by_your_default"
BAND_HELD = "held"
BAND_WHERE_THE_FIX_IS = "where_the_fix_is"
BAND_THE_REASON = "the_reason"
BAND_HOW_LONG = "how_long_it_has_waited"
BAND_EVERYTHING_ELSE = "everything_else"

BAND_ORDER: tuple[str, ...] = (
    BAND_NEEDS_YOU,
    BAND_BY_DEFAULT,
    BAND_HELD,
    BAND_WHERE_THE_FIX_IS,
    BAND_THE_REASON,
    BAND_HOW_LONG,
    BAND_EVERYTHING_ELSE,
)

#: The two decision cases a step-1 DEFAULT answers rather than a clerk. Every
#: other decision case the engine raises lands in *Needs you*.
#:
#: ⚠ **THE SET IS DERIVED FROM THE ENGINE, NOT DECLARED AT TWENTY-SIX.** §03
#: p041 is explicit — *"A case kind the engine did not raise gets no chip"* —
#: and the as-built screen's own failure is the opposite: it declares fifteen
#: tabs where nine cases are emitted, so three of them exist only to explain
#: that a feature is not built. A tag here appears because a row carries it.
BY_DEFAULT_CASES: frozenset[str] = frozenset({read_analysis.CASE_ESTIMATED, "base_only_billing"})

#: Held splits in two, and the two mean opposite things to a clerk: *we never
#: got as far as pricing this* and *we priced it and it fell over*.
TAG_NEVER_CALCULATED = "never_calculated"
TAG_CALCULATED_AND_BROKE = "calculated_and_broke"

#: *Everything else* — three tags, and the third is NOT A FACT ABOUT THE RUN.
TAG_READY = "ready"
TAG_MASTERS = "masters"
TAG_IN_ARREARS = "in_arrears"

#: The three waiting-time tags. Their BOUNDARIES are served beside them as
#: numbers — never baked into these names — because the labels the screen draws
#: (*Under 14 days*, *Over 60 days*) contain the boundary, and the boundary is
#: derived per cycle. See `waiting_bands_for`.
TAG_WAITING_UNDER = "under_escalation"
TAG_WAITING_ESCALATED = "escalated"
TAG_WAITING_LONG = "long_wait"

#: The DEFAULT waiting-time boundaries, expressed as MULTIPLES OF THE CYCLE'S
#: OWN PERIOD rather than as days — which is the whole of the ruling: the bands
#: derive from the cycle's frequency and are settable at cycle level.
#:
#: ⚠ **THESE ARE NOT THE DRAWN NUMBERS AND MUST NOT BE.** The drawing says
#: *Under 14 days* and *Over 60 days*; B14 rule 37 makes a drawn figure an
#: illustration, never a fact to build to. One cycle length (escalate) and two
#: (long wait) is what reproduces the drawn pair on the MONTHLY cycle they were
#: drawn for — 31 and 62 against a 31-day August — and, unlike 14 and 60, it
#: still means something on a 15-day cycle (15 / 30) and on a quarterly one
#: (92 / 184). A fixed 14 would escalate a quarterly cycle's every account
#: before its first bill was due.
ESCALATE_AFTER_PERIODS = 1
LONG_WAIT_AFTER_PERIODS = 2


def waiting_bands_for(run: BillRun) -> dict[str, Any]:
    """The two waiting-time boundaries for THIS cycle, in days, derived.

    **DERIVED FROM THE CYCLE'S FREQUENCY, NEVER TYPED.** `metering
    .cycle_expected_span_days` is the published answer to *how many days does
    one period of this cycle cover*, taken at this run's own `period_start` so
    a 28-day February and a 31-day August each answer for themselves. The two
    boundaries are whole multiples of that span.

    **A CYCLE-LEVEL OVERRIDE IS OWED AND IS NOT HERE.** The ruling says these
    are settable at cycle level with a default we supply; the COLUMN belongs to
    another file and does not exist yet. This read asks the seam for it first
    and falls back to the derived default, so the day the column lands nothing
    here changes (`DEF-BIL-5298`).

    `None` boundaries are a real answer, not a gap: a cycle carrying no
    frequency the vocabulary holds has no period to take a multiple of, and
    guessing thirty days would escalate a quarterly cycle's whole queue. The
    caller states the absence and serves no age tags at all.
    """
    span_for = _resolve("metering", "cycle_expected_span_days")
    span = None
    if span_for is not None and run.cycle_id is not None:
        span = span_for(run.cycle_id, period_start=run.period_start)
    override = _resolve("metering", "cycle_waiting_bands")
    if override is not None and run.cycle_id is not None:
        # The cycle-level setting, the moment metering publishes one. Asked for
        # by name so wiring it is nothing at all, per the ruling.
        stated = override(run.cycle_id) or {}
        if stated.get("escalate_after_days") and stated.get("long_wait_after_days"):
            return {
                "escalate_after_days": int(stated["escalate_after_days"]),
                "long_wait_after_days": int(stated["long_wait_after_days"]),
                "period_days": span,
                "source": "cycle_setting",
            }
    if not span:
        return {
            "escalate_after_days": None,
            "long_wait_after_days": None,
            "period_days": None,
            "source": "unavailable",
        }
    return {
        "escalate_after_days": int(span) * ESCALATE_AFTER_PERIODS,
        "long_wait_after_days": int(span) * LONG_WAIT_AFTER_PERIODS,
        "period_days": int(span),
        "source": "derived_from_cycle_frequency",
    }


#: Which cycle's waiting-time bands govern an account HELD ACROSS CYCLES — the
#: one it was held from, or the one being run now? **THIS IS OPEN AND MUST NOT
#: BE GUESSED** (`OQ-BIL-12358`). It is a parameter so the answer is one
#: argument away; until it is ruled, a cross-cycle hold is counted on its own
#: and kept OUT of the three age tags, because banding it either way would be
#: choosing the answer silently.
AGE_BANDS_FROM_RUN_CYCLE = "run_cycle"
AGE_BANDS_FROM_HELD_CYCLE = "held_cycle"
AGE_BANDS_FROM: tuple[str, ...] = (AGE_BANDS_FROM_RUN_CYCLE, AGE_BANDS_FROM_HELD_CYCLE)


def _held_since(run: BillRun) -> dict[str, dict[str, Any]]:
    """`{account_id: {held_since, from_cycle_id}}` for every UNRESOLVED hold
    this account carries anywhere — ONE query, not one per account.

    **THE OLDEST UNRESOLVED HOLD WINS**, which is the whole point of the age
    band: an account held in July, again in August and again in September has
    waited since July, and reading only this run's own row would report it as
    new every month — *"An account held month after month is the thing that
    quietly loses revenue"* (§03 p040).

    `resolved_at IS NULL` is the same predicate the pending queue and its index
    use: a hold a catch-up has since billed is closed and is not waiting.
    """
    rows = (
        BillRunExclusion.objects.filter(tenant_id=_tenant_id(), resolved_at__isnull=True)
        .order_by("account_id", "created_at", "id")
        .values_list("account_id", "created_at", "bill_run__cycle_id")
    )
    out: dict[str, dict[str, Any]] = {}
    for account_id, created_at, from_cycle_id in rows:
        key = str(account_id)
        if key in out:  # already holding the oldest — the order_by decides it
            continue
        out[key] = {
            "held_since": created_at,
            "from_cycle_id": None if from_cycle_id is None else str(from_cycle_id),
        }
    return out


def _tag(tag_id: str, band: str, count: int) -> dict[str, Any]:
    """One chip. `count` is CASES for a tag and ACCOUNTS for a band total —
    the two are named differently in the envelope so nothing can add them up
    without noticing which it has."""
    return {"id": tag_id, "band": band, "cases": count}


def finding_counts(
    run: BillRun,
    *,
    as_of: date,
    age_bands_from: str | None = None,
) -> dict[str, Any]:
    """`GET /billing/runs/{id}/findings/counts` — the strip, without the rows.

    Serves the four KPI cells and the seven bands with their generated tags,
    and NOTHING ELSE: no account rows, no readings, no case detail. That is the
    contract — the table beside it pages (B14 rule 16) and asks for the page it
    is showing.

    `as_of` is REQUIRED and is never a server clock (BR-TEN-043 / gate G6):
    *today* belongs to the tenant, and a waiting-time band computed from the
    process's own date ages a queue by a day the moment somebody opens it from
    another timezone.

    ── THE FOUR KPI CELLS, AND THE MONEY HALF IS NULL ON PURPOSE ─────────────
    The drawn strip carries money beside three of the four counts. **Phase 1
    computes no money at all** — the PO's own framing, *"between step 1 and
    step 2 we are basically running pre bill checks and it is not actual bill
    generation"* — so those halves are served null under their contracted names
    with the reason beside them, never as a Σ of zero. A zero here would be a
    claim about a utility's revenue.

    ── THE RECONCILIATION ───────────────────────────────────────────────────
    `ready + needs_you + held + nothing_to_bill = accounts_in_scope`, and it
    ties BY CONSTRUCTION rather than by luck: the four sets are built by
    subtraction from one population, in that order, so no account can be in two
    of them and none can be in none of them. The screen's own sentence — *"All
    1,284 accounts in the cycle are accounted for"* — is generated from these
    four numbers, not typed (`DEF-BIL-5280`).
    """
    prepared = prepared_for(run)
    analysis = read_analysis.analysis_rows(prepared, cycle_id=run.cycle_id)
    absences: list[dict[str, Any]] = [dict(gap) for gap in analysis.gaps]

    # ── the four populations, by subtraction from one set ────────────────────
    ready_ids = {str(data.account_id) for data in prepared.ready if data.account_id}
    blocked_ids = {str(p.account_id) for p in prepared.blocked if p.account_id}
    silent_ids = {str(p.account_id) for p in prepared.silent if p.account_id}
    held_here = set(pending.held_account_ids(run))
    held_ids = blocked_ids | held_here
    all_ids = ready_ids | blocked_ids | silent_ids | held_ids

    # A CASE row per (account, case) — decisions from the prepare pass and the
    # read analysis, which is exactly the pair `exceptions_dict` joins. Counted
    # as CASES, deduplicated only on the pair, never on the account.
    case_rows: list[tuple[str, str]] = [
        (str(problem.account_id), problem.reason)
        for problem in prepared.decisions
        if problem.account_id
    ]
    case_rows += [
        (str(row["account_id"]), row["case"]) for row in analysis.rows if row.get("account_id")
    ]

    needs_ids = {
        account_id
        for account_id, case in case_rows
        if case not in BY_DEFAULT_CASES and account_id not in held_ids
    }
    remaining_ready = ready_ids - held_ids - needs_ids - silent_ids

    tags: list[dict[str, Any]] = []
    cases_by_kind: dict[str, int] = {}
    for _account_id, case in case_rows:
        cases_by_kind[case] = cases_by_kind.get(case, 0) + 1
    for case, count in sorted(cases_by_kind.items()):
        band = BAND_BY_DEFAULT if case in BY_DEFAULT_CASES else BAND_NEEDS_YOU
        tags.append(_tag(case, band, count))

    # ── Held, and its three sub-partitions ───────────────────────────────────
    tags.append(_tag(TAG_NEVER_CALCULATED, BAND_HELD, len(held_here)))
    tags.append(_tag(TAG_CALCULATED_AND_BROKE, BAND_HELD, len(blocked_ids)))

    by_stage: dict[str, int] = {}
    by_reason: dict[str, int] = {}
    # ⚠ **THE ACCOUNTS WITH A STAGE ARE TRACKED SEPARATELY FROM THE BLOCKED SET
    # AND THAT IS NOT TIDINESS — IT IS THE BAND'S OWN ARITHMETIC.** A stage of
    # None is a real answer (BR-BIL-040: some problems are facts about the run's
    # shape, not stage failures), so *where the fix is* cannot count every
    # blocked account: a band claiming an account its own tags do not hold
    # breaks `sum(tags) ≥ band` in the one direction that hides work. Found by
    # a probe on a `ruled_path_refused` block, which carries no stage at all.
    staged_ids: set[str] = set()
    for problem in prepared.blocked:
        if problem.stage:
            by_stage[problem.stage] = by_stage.get(problem.stage, 0) + 1
            if problem.account_id:
                staged_ids.add(str(problem.account_id))
        by_reason[problem.reason] = by_reason.get(problem.reason, 0) + 1
    for stage, count in sorted(by_stage.items()):
        tags.append(_tag(stage, BAND_WHERE_THE_FIX_IS, count))
    for reason, count in sorted(by_reason.items()):
        tags.append(_tag(reason, BAND_THE_REASON, count))

    # ── how long it has waited ───────────────────────────────────────────────
    bands = waiting_bands_for(run)
    waiting = _waiting_counts(
        run,
        as_of=as_of,
        held_ids=held_ids,
        bands=bands,
        age_bands_from=age_bands_from,
        absences=absences,
    )
    for tag_id in (TAG_WAITING_UNDER, TAG_WAITING_ESCALATED, TAG_WAITING_LONG):
        if waiting["counts"].get(tag_id) is not None:
            tags.append(_tag(tag_id, BAND_HOW_LONG, waiting["counts"][tag_id]))

    # ── everything else ──────────────────────────────────────────────────────
    tags.append(_tag(TAG_READY, BAND_EVERYTHING_ELSE, len(remaining_ready)))
    masters, master_absence = _master_count(run)
    if master_absence is not None:
        absences.append(master_absence)
    else:
        tags.append(_tag(TAG_MASTERS, BAND_EVERYTHING_ELSE, masters))
    # ⚠ **`In arrears` IS NOT A FACT ABOUT THIS RUN** and is deliberately not
    # folded into the pass that produces every other number here. It is a read
    # of what each account OWED BEFORE this bill, measured at a date the clerk
    # chooses — a different question, a different source and a different clock.
    # Folding it in would make a balance read part of the billing pass and give
    # the run a number that changes when somebody pays. It is served as a
    # declared absence until an account-balance read at population scale
    # exists; per-account is the N+1 this endpoint was written to kill, and
    # `past due` cannot be computed at all while the tenant's business-day
    # clock does not reach it (`DEF-BIL-5299`).
    absences.append(
        _unavailable(
            "arrears_not_counted_here",
            PAST_DUE_UNAVAILABLE,
            "Arrears are not counted here yet.",
        )
    )

    band_accounts = {
        BAND_NEEDS_YOU: len(needs_ids),
        BAND_BY_DEFAULT: len(
            {account_id for account_id, case in case_rows if case in BY_DEFAULT_CASES}
        ),
        BAND_HELD: len(held_ids),
        BAND_WHERE_THE_FIX_IS: len(staged_ids),
        BAND_THE_REASON: len(blocked_ids),
        BAND_HOW_LONG: waiting["banded_accounts"],
        BAND_EVERYTHING_ELSE: len(remaining_ready),
    }

    return {
        "run_id": str(run.pk),
        "cycle_id": prepared.cycle_id,
        "as_of": as_of.isoformat(),
        # THE FOUR CELLS OF 17.L2. *"A filter changes the list and never these
        # four cells"* — they describe the RUN, so nothing a clerk types into
        # the toolbar may be allowed to move them.
        "kpi": {
            "ready_to_bill": {"accounts": len(remaining_ready), "amount": None},
            "needs_you": {"accounts": len(needs_ids), "amount": None},
            "held": {
                "accounts": len(held_ids),
                "never_calculated": len(held_here),
                "calculated_and_broke": len(blocked_ids),
            },
            "run_total": {"amount": None},
        },
        "bands": [
            {
                "id": band,
                "accounts": band_accounts[band],
                # WHAT THIS BAND PARTITIONS — the arithmetic a reader can check
                # without opening the drawing (§03 p040's partition rule).
                "partitions": (
                    BAND_HELD
                    if band in (BAND_WHERE_THE_FIX_IS, BAND_THE_REASON, BAND_HOW_LONG)
                    else None
                ),
            }
            for band in BAND_ORDER
        ],
        "tags": tags,
        "waiting_bands": bands,
        "waiting": waiting["reported"],
        "reconciliation": {
            "accounts_in_scope": len(all_ids),
            "ready": len(remaining_ready),
            "needs_you": len(needs_ids),
            "held": len(held_ids),
            "nothing_to_bill": len(silent_ids - held_ids - needs_ids),
            "account_count": prepared.account_count,
        },
        "unavailable": absences,
    }


def _master_count(run: BillRun) -> tuple[int, dict[str, Any] | None]:
    """How many accounts in this run are MASTERS — *"a view, not a case"*, and
    it cuts across every band (§03 entry 17.15)."""
    units_in_cycle = _resolve("metering", "units_in_cycle")
    accounts_for = _resolve("customers", "accounts_for_bill_run")
    if units_in_cycle is None or accounts_for is None:
        return 0, _unavailable(
            "masters_cannot_be_counted",
            "BR-CUS-068",
            "Master accounts cannot be counted.",
        )
    scope = run.scope_services
    unit_ids = units_in_cycle(
        run.cycle_id, service_codes=None if scope is None else list(scope)
    )
    if not unit_ids:
        return 0, None
    return int(accounts_for(unit_ids).filter(kind=CUSTOMERS_MASTER_KIND).count()), None


def _waiting_counts(
    run: BillRun,
    *,
    as_of: date,
    held_ids: set[str],
    bands: dict[str, Any],
    age_bands_from: str | None,
    absences: list[dict[str, Any]],
) -> dict[str, Any]:
    """The three age tags over the held population — and everything they could
    not band, counted rather than dropped.

    ⚠ **THREE ACCOUNTS ARE KEPT OUT OF THE THREE TAGS AND EACH IS COUNTED ON
    ITS OWN**, because a check that reports what it could not see as a zero is
    indistinguishable from one that looked and found nothing:

    * `without_a_held_date` — blocked in this run and never held, so there is
      no *held since* anywhere to measure from. Not zero days: no date.
    * `bands_not_derivable` — the cycle carries no frequency the vocabulary
      holds, so there is no period to take a multiple of.
    * `cross_cycle_unsettled` — held from a DIFFERENT cycle from the one being
      run, and WHICH CYCLE'S BANDS APPLY IS AN OPEN QUESTION. Banding it either
      way would answer that question silently, so it is counted and named.
    """
    escalate = bands.get("escalate_after_days")
    long_wait = bands.get("long_wait_after_days")
    if not escalate or not long_wait:
        absences.append(
            _unavailable(
                "waiting_bands_not_derivable",
                "BR-MET-121",
                "Waiting times cannot be grouped.",
            )
        )
        return {
            "counts": {},
            "banded_accounts": 0,
            "reported": {
                "banded": 0,
                "without_a_held_date": len(held_ids),
                "bands_not_derivable": len(held_ids),
                "cross_cycle_unsettled": 0,
            },
        }

    since = _held_since(run)
    run_cycle = None if run.cycle_id is None else str(run.cycle_id)
    counts = {TAG_WAITING_UNDER: 0, TAG_WAITING_ESCALATED: 0, TAG_WAITING_LONG: 0}
    no_date = 0
    cross = 0
    for account_id in sorted(held_ids):
        entry = since.get(account_id)
        if entry is None or entry["held_since"] is None:
            no_date += 1
            continue
        if entry["from_cycle_id"] != run_cycle and age_bands_from not in AGE_BANDS_FROM:
            # OPEN — see `AGE_BANDS_FROM`. Counted, never banded.
            cross += 1
            continue
        waited = (as_of - entry["held_since"].date()).days
        if waited >= long_wait:
            counts[TAG_WAITING_LONG] += 1
        elif waited >= escalate:
            counts[TAG_WAITING_ESCALATED] += 1
        else:
            counts[TAG_WAITING_UNDER] += 1
    if cross:
        absences.append(
            _unavailable(
                "held_across_cycles_not_grouped",
                "BR-BIL-015",
                "Some holds span several periods. They are not grouped yet.",
            )
        )
    banded = sum(counts.values())
    return {
        "counts": counts,
        "banded_accounts": banded,
        "reported": {
            "banded": banded,
            "without_a_held_date": no_date,
            "bands_not_derivable": 0,
            "cross_cycle_unsettled": cross,
        },
    }


def calculated_run_dict(calculated: Any) -> dict[str, Any]:
    """What `POST /billing/runs/{id}/calculate` answers with — PHASE 2, whole.

    `runs.CalculatedRun` field for field: the drafts it wrote and **the breaks
    it could not**, in one body, because BR-BIL-053 puts the breaks BEFORE the
    totals and a clerk needs the count that worked and the list that did not in
    the same place. A response that carried only `drafted` would make a run of
    1,122 out of 1,124 look like a run of 1,122 out of 1,122.

    ⚠ **THIS IS THE ONLY PLACE THE BREAK LIST EXISTS.** `apps/billing/api.py`
    records why there is no `GET .../breaks`: `calculate_run` returns the breaks
    and nothing persists them, so a GET would have to CALCULATE inside a read,
    which writes drafts. The write returns what it just computed — the same
    discipline `POST .../release` follows with its summary — and a caller that
    navigates away loses the list until it calculates again. Stated rather than
    implied; a durable per-account break row is owed and is BR-BIL-053's story.

    `account_count` is the honest denominator (drafts + breaks), because
    *"1,122 of 1,124"* is only true if the 1,124 counts the two that broke.
    """
    return {
        "bill_run_id": calculated.bill_run_id,
        "drafted": list(calculated.drafted),
        "draft_count": calculated.drafted_count,
        "account_count": calculated.account_count,
        "breaks": [
            {
                "account_id": item.account_id,
                "account_no": item.account_no,
                "stage": item.stage,
                "reason": item.reason,
                "detail": item.detail,
                "retryable": item.retryable,
            }
            for item in calculated.breaks
        ],
        "break_count": len(calculated.breaks),
        "breaks_by_stage": {
            stage: [item.account_no for item in items]
            for stage, items in calculated.breaks_by_stage().items()
        },
        # `BR-BIL-1024`/`BR-BIL-1025` — accounts that priced no lines, so no
        # document was written. Served beside the drafts and the breaks for the
        # reason those two are served together: a clerk needs the count that
        # worked, the list that did not, and the list that correctly produced
        # nothing, in one place.
        "silent": [account_problem_dict(problem) for problem in calculated.silent],
        "silent_count": len(calculated.silent),
    }


def _service_id_by_code(prepared: Any) -> dict[tuple[str, str], str]:
    """(account_id, service_code) → service_id, from what the run already read.

    A decision is recorded against a SERVICE (`bill_run_decisions.service_id`),
    and `AccountProblem` carries the service CODE because that is what a human
    reads. The id is not looked up in another module's table — billing may not
    query `tenancy.services` (B1/G6) — it is taken from the readings metering
    already returned, which carry both.
    """
    return {
        (data.account_id, reading.service_code): reading.service_id
        for data in prepared.ready
        for reading in data.readings
        if reading.service_id
    }


class _UsageBasisMemo:
    """One `usage_payload` read per ACCOUNT for the whole exceptions pass.

    ⚠ **IT DIES WITH THE REQUEST, AND THAT IS THE WHOLE POINT.** `OQ-843` is
    CLOSED on the PO's own ruling — *"it is dyanmic, so at the time of compute
    if data is changed, process will dynamically use it becuase it will collect
    data at that instansce"* — and that ruling ends *"A lane may not reopen this
    by proposing a cache."* This is the same within-pass memo CR-051 task 22
    used, not a cache: a clerk who fixes a read and reloads sees the fix,
    because the next request builds a new one.

    **THE BOUND IS THE MISSING READS, NOT THE RUN.** Only a `missing_read` row
    asks, and only once per account however many services it has waiting. A run
    where nothing is missing makes no metering call at all.
    """

    def __init__(self, as_of: Any) -> None:
        self._as_of = as_of
        self._by_account: dict[Any, Any] = {}
        self.problems: list[dict[str, Any]] = []

    def basis_for(self, account_id: Any, service_code: str | None) -> dict[str, Any] | None:
        if not service_code:
            return None
        key = (str(account_id), service_code)
        if key not in self._by_account:
            outcome = metering_seam.usage_basis_for(account_id, service_code, as_of=self._as_of)
            if outcome.problem is not None:
                # "no history" and "could not look" are different facts, and the
                # second one belongs where every other unreachable seam on this
                # payload is named rather than being flattened into a null.
                self.problems.append(dict(outcome.problem))
            self._by_account[key] = outcome
        outcome = self._by_account[key]
        if not outcome.known:
            return None
        return {
            "quantity": outcome.quantity,
            "unit": outcome.unit,
            "high": outcome.high,
            "low": outcome.low,
            "months": outcome.months,
        }


def _recorded_decision_dict(row: Any) -> dict[str, Any]:
    """The decision that STANDS on this case row, whole — DEF-2857.

    ⚠ **THIS USED TO SERVE THE CHOICE AND NOTHING ELSE, AND THAT IS THE DEFECT
    A CUSTOMER FOUND.** `chosen` was `row.choice` — the word — while the
    quantity the clerk had typed sat in `bill_run_decisions.amount` with its
    unit beside it and reached no screen. The Product Owner, working the
    deployed run, 2026-08-31: *"i add the estamate and submit - nothing
    happened - ony estaimated wrritern - this UI is not helping user"*. The
    write had always worked; the round trip had never been closed.

    **`chosen_quantity` IS SERVED ONLY WITH `chosen_unit`, AND THE PAIR IS THE
    POINT** (CLAUDE.md rule 3). `BillRunDecision.amount` is a bare NUMERIC that
    can hold either a quantity or money — its own column comment says so — and
    the row carries no currency at all. So a stored amount whose `unit` is NULL
    is a figure this module cannot name: serving it as a quantity would invent
    a unit and serving it as money would invent a currency. It is served as
    NEITHER, and the absence is the honest answer. Today only *estimate*
    supplies an amount, and `record_decision` refuses that one without its
    unit, so the unnameable case does not arise from any screen — this branch
    exists so that the day a second choice starts carrying a figure, it has to
    bring the unit rather than quietly arriving as a bare number.

    A STRING at the column's own scale, like every other quantity on this
    payload: a browser that parses a decimal has become a money path
    (CLAUDE.md rule 2).
    """
    if row is None:
        return {"chosen": None, "chosen_quantity": None, "chosen_unit": None}
    has_quantity = row.amount is not None and bool(row.unit)
    return {
        "chosen": row.choice,
        "chosen_quantity": str(row.amount) if has_quantity else None,
        "chosen_unit": row.unit if has_quantity else None,
    }


def exceptions_dict(run: BillRun) -> dict[str, Any]:
    """`GET /billing/runs/{id}/exceptions` — S31.3's case tables.

    A case row is `prepare_run`'s DECISION list rendered as a question, joined
    to the decision already recorded for it (`chosen`, null while undecided —
    BR-BIL-015/061 forbid a pre-committed default and a select showing its
    first option IS a default). Its `id` is the decision's natural key, so the
    id a clerk selected still names the same case on the next viewing.

    ⚠ **THE JOIN CARRIES THE WHOLE DECISION SINCE DEF-2857, NOT JUST ITS WORD**
    — `chosen_quantity` and `chosen_unit` travel beside `chosen`, so the figure
    a clerk typed into the estimate window comes back to the row they typed it
    on. See `_recorded_decision_dict` for why the quantity is never served
    without its unit. The three are the ONLY members the recorded decision
    writes; `amount`, `currency`, `quantity`, `unit` and `facts` below continue
    to describe the CASE, which is a different fact and stays untouched by
    anybody's answer to it.

    **FOUR MEMBERS ARE NULL ON EVERY ROW AND `totals` IS EMPTY, because phase 1
    computes no money at all.** `PreparedRun` carries `ready`, `blocked` and
    `decisions` and not one amount: the late-fee assessment, the guardrail
    average and the unallocated credits are all US-BIL-002 surfaces that no
    endpoint serves. So `amount`, `currency`, `quantity` and `unit` are served
    null under their contracted names, and `totals` is `{}` — which the bulk
    dialog renders as "the total is not served" rather than as a Σ of zero.

    `customer_name` is null for a different reason worth naming separately: the
    only published customers read is `primary_contact_name(account)` and it
    takes an Account INSTANCE, which billing cannot build without importing
    another module's model (B1 / G6 rule 4). REPORTED — customers publishing a
    by-id read closes it — and null here means "not read", never "no name".

    ── CR-038 W8 (2026-08-26) — the READ-ANALYSIS rows ride the same surface ──
    The seven read categories (`read_analysis.READ_ANALYSIS_CASES`) join `rows`
    with the same envelope plus two additive members every row now carries:
    `suggested` — the rule-grounded recommendation rendered as a visible chip,
    NEVER a pre-selection (PO 2026-08-26 reaffirming BR-BIL-015/061: *"speed
    comes from the bulk button, not from decisions nobody made"*) — and `facts`,
    the STORED figures each case table draws as columns (BR-MET-022/056). One
    endpoint, one resolve door, so bulk (BR-BIL-060) and the per-row actor
    recording work for the new cases with nothing else built. `analysis_gaps`
    names any seam the analysis could not reach — "no rows" and "could not
    look" are different facts.
    """
    prepared = prepared_for(run)
    service_ids = _service_id_by_code(prepared)
    standing_by_key = {
        (str(row.account_id), row.case, str(row.service_id) if row.service_id else None): row
        for row in decisions.current_decisions(run)
    }

    # DEF-2859 — the account's OWN average month, for the estimate window to
    # offer as a starting figure. Asked for only where a read is MISSING, which
    # is the only case BR-BIL-015 offers *estimate* on.
    basis_memo = _UsageBasisMemo(prepared.period_end)

    rows: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for problem in prepared.decisions:
        case = problem.reason
        service_id = (
            service_ids.get((problem.account_id, problem.service_code))
            if problem.service_code
            else None
        )
        rows.append(
            {
                "id": decisions.case_row_id(case, problem.account_id, service_id),
                "case": case,
                "account_id": problem.account_id,
                "account_no": problem.account_no,
                "customer_name": None,
                "service_code": problem.service_code,
                "detail": problem.detail,
                # The dispositions THE SERVER offers — BR-BIL-015's three and
                # BR-BIL-003's manual-only waiver are rules this module owns.
                "choices": list(decisions.CHOICES_BY_CASE.get(case, ())),
                "amount": None,
                "currency": None,
                "quantity": None,
                "unit": None,
                "suggested": None,
                "facts": None,
                # A VALUE the estimate window offers, never a CHOICE it makes —
                # the reasoning is in the decision log, 2026-08-31. Null on
                # every case but `missing_read`, and on a missing read whose
                # account metering holds no stored months for.
                "basis": (
                    basis_memo.basis_for(problem.account_id, problem.service_code)
                    if case == "missing_read"
                    else None
                ),
                **_recorded_decision_dict(
                    standing_by_key.get((problem.account_id, case, service_id))
                ),
            }
        )
        counts[case] = counts.get(case, 0) + 1

    analysis = read_analysis.analysis_rows(prepared, cycle_id=run.cycle_id)
    for row in analysis.rows:
        service_id = row.pop("service_id", None)
        # ONE ROW SHAPE ACROSS BOTH LOOPS. A read-analysis row is never a
        # missing read — it is a reading the run DID gather and flagged — so it
        # offers no estimate basis and says so with a null rather than by
        # lacking the member, which a client would read as an older server.
        row["basis"] = None
        row.update(
            _recorded_decision_dict(
                standing_by_key.get(
                    (row["account_id"], row["case"], str(service_id) if service_id else None)
                )
            )
        )
        rows.append(row)
        counts[row["case"]] = counts.get(row["case"], 0) + 1
    return {
        "rows": rows,
        "counts": counts,
        "totals": {},
        # A seam the usage basis could not reach is named beside the ones the
        # read analysis could not reach — same list, same reason: "no rows" and
        # "could not look" are different facts.
        "analysis_gaps": [dict(gap) for gap in analysis.gaps] + basis_memo.problems,
    }


def pending_row_dict(row: Any) -> dict[str, Any]:
    """One Pending-billing queue row, as US-BIL-006 §5 maps it (S30's list).

    `origin` and `stage` are the two columns the story exists for: a clerk must
    read *"we never calculated this"* differently from *"we calculated it and it
    broke at measure-consumption"*, because the first is fixed by entering a
    read and the second usually by fixing configuration (BR-BIL-055).

    `age_days` and `escalated` were computed against the caller's `as_of`, never
    a clock (BR-TEN-043) — the date they were computed against travels on the
    envelope beside them, so a screen can never show an age without showing what
    it is an age AT.

    No money member is served and none is null-as-a-placeholder: a queue row is
    an account that has NOT been billed, so there is no amount to state and a
    zero would be a claim.
    """
    return {
        "id": row.exclusion_id,
        "account_id": row.account_id,
        "account_no": row.account_no,
        "bill_run_id": row.bill_run_id,
        "parent_run_id": row.parent_run_id,
        "period_start": row.period_start.isoformat(),
        "period_end": row.period_end.isoformat(),
        "reason_code": row.reason_code,
        "detail": row.detail,
        "origin": row.origin,
        "stage": row.stage,
        "held_on": row.held_on.isoformat(),
        "age_days": row.age_days,
        "escalated": row.escalated,
        "resolved_by_run_id": row.resolved_by_run_id,
        "resolved_on": None if row.resolved_on is None else row.resolved_on.isoformat(),
    }


def run_summary_dict(summary: Any) -> dict[str, Any]:
    """What `GET /billing/runs/{id}/summary` answers with — BR-BIL-056's panel.

    THE LIVE PANEL, not the stored row. `release_dict` above serves
    `bill_run_releases` — *"what did I authorise?"* — and this serves
    `release.summary_for`, which is *"what do these bills add up to TODAY"*.
    The PO ruled option B on 2026-08-11 over their own worked figure (approve
    480 at $52,847.19, void two, the screen reads 478), so the two answers are
    different questions and neither is derived from the other. A serializer that
    tried to reuse the other one would rebuild the confusion that ruling exists
    to prevent.

    THREE CONTRACTS THIS SHAPE KEEPS, AND EACH IS A HARD RULE.

    * **Money is TEXT with its currency beside it** (rule 2 / DEF-099).
      `currency` is null on a run with no bills — there is no currency to name
      when nothing was billed, and "USD" there would be an invented fact.
    * **Every quantity carries its explicit unit** (rule 3). `consumption` is a
      list of `{service, quantity, unit}` and never a map keyed by service, so
      one service metered in two units stays two rows rather than one of them
      overwriting the other. `service` is null when the line does not say which
      service the quantity belongs to — *not attributed*, never *no service*,
      and never inferred from the unit (water and sewer both meter in kgal).
    * **Coverage keeps the difference between zero and unknown** (BR-BIL-059).
      `covered: null` with an `unavailable_reason` is *"we could not count"*;
      `covered: 0` is *"nobody holds one"*. A screen that rendered them the same
      would put a figure under a clerk's signature that nobody computed.

    `problems` is a list of CODES with a `br_ref` and a sentence. Codes, because
    the panel groups on them and a screen cannot group on prose; the sentence,
    because the reader of a stated absence is a person.
    """
    return {
        "bill_run_id": summary.bill_run_id,
        "accounts": summary.accounts,
        "bills": summary.bills,
        "consumption": [
            {
                "service": figure.service_code,
                "quantity": _decimal_str(figure.quantity),
                "unit": figure.unit,
            }
            for figure in summary.consumption
        ],
        "amount": _decimal_str(summary.amount),
        "currency": summary.currency,
        "gross_amount": _decimal_str(summary.gross_amount),
        "credits_applied": _decimal_str(summary.credits_applied),
        # CR-059 CS-37 — the credit notes behind `credits_applied`, NAMED, so
        # S31's sign-off sentence can name them without the screen having to
        # parse the prose in `problems`. Each entry is a `CM-` number, or the
        # bill and date of a historic row that has none. **Never an id**: that
        # fallback was a live breach of B14 rule 31 and is gone.
        "credit_count": summary.credit_count,
        "credits_named": list(summary.credits_named),
        # PO 2026-09-30 (fixed-charge case 2) — *"Waived $26"* on Sign off.
        "waived": [
            {
                "account_no": row["account_no"],
                # Record links (PO 2026-10-19) — an address ingredient only.
                "account_id": row.get("account_id"),
                "amount": _decimal_str(row["amount"]),
                "currency": row["currency"],
            }
            for row in summary.waived
        ],
        "waived_total": _decimal_str(summary.waived_total),
        "by_category": [
            {
                "axis": figure.axis,
                "key": figure.key,
                "bills": figure.bills,
                "amount": _decimal_str(figure.amount),
                "currency": figure.currency,
            }
            for figure in summary.by_category
        ],
        "axes_status": summary.axes_status,
        "coverage": [
            {
                "mandate": row.mandate,
                "covered": row.covered,
                "not_covered": row.not_covered,
                "accounts": row.accounts,
                "amount": _decimal_str(row.amount),
                "unavailable_reason": row.unavailable_reason,
            }
            for row in summary.coverage
        ],
        "problems": [dict(entry) for entry in summary.problems],
    }


def run_totals_dict(totals: dict[str, Any]) -> dict[str, Any]:
    """What `GET /billing/runs/{id}/totals` answers with — `release.totals_for`,
    the panel's headline in `run_summary_dict`'s own spelling (money as text
    with its currency beside it, rule 2), so a figure reads the same on both."""
    return {
        "bill_run_id": totals["bill_run_id"],
        "bills": totals["bills"],
        "amount": _decimal_str(totals["amount"]),
        "currency": totals["currency"],
        "gross_amount": _decimal_str(totals["gross_amount"]),
        "credits_applied": _decimal_str(totals["credits_applied"]),
        "credit_count": totals["credit_count"],
    }


def release_dict(row: Any, *, created: bool) -> dict[str, Any]:
    """What `POST /billing/runs/{id}/release` answers with (US-BIL-005, phase 4).

    THE STORED ROW, not the live panel. Since the PO's option-B ruling of
    2026-08-11 the phase-4 SCREEN recalculates and this ROW does not, and after
    that ruling the row is the ONLY answer to *"what did I authorise?"*
    (`models.BillRunRelease`'s docstring argues it at length). So the response
    serves the row's own frozen columns — and the payload it stored — rather
    than recomputing anything, because recomputing here would rebuild exactly
    the confusion the two-answers design exists to avoid.

    `created` is the hard-rule-6 fork and it is served rather than inferred: a
    double-clicked Confirm answers **200 `created: false`** carrying the release
    that already exists, the same shape `POST /accounts/{id}/payments` gives a
    replayed payment (11b §2.9b). A second row would be a second authorisation
    for one signature.

    Money keeps its currency beside it (CLAUDE.md rule 2, DEF-099) and is served
    as TEXT at the column's own six-decimal scale — a JSON number is a float the
    moment anything parses it.
    """
    return {
        "id": str(row.pk),
        "created": created,
        "bill_run_id": str(row.bill_run_id),
        "confirmations": {
            "compliance": row.compliance_confirmed,
            "email_mandate": row.email_mandate_confirmed,
            "sms_mandate": row.sms_mandate_confirmed,
            "autopay_mandate": row.autopay_mandate_confirmed,
            # BR-BIL-058's fifth fact has no boolean column BY DESIGN: it is
            # recorded as WHO confirmed and WHEN, which is stronger than a tick.
            # Served as `true` because the row exists, with the two facts beside
            # it, so a screen never has to know that asymmetry.
            "final": True,
        },
        "confirmed_by": None if row.confirmed_by_id is None else str(row.confirmed_by_id),
        "confirmed_at": _iso(row.confirmed_at),
        "released_at": _iso(row.released_at),
        "account_count": row.account_count,
        "bill_count": row.bill_count,
        "total_amount": _decimal_str(row.total_amount),
        "currency": row.currency,
        "summary": row.summary,
    }


def issued_run_dict(outcome: Any, *, created: bool) -> dict[str, Any]:
    """What `POST /billing/runs/{id}/issue` answers with (US-BIL-005, phase 5).

    `release.ReleaseOutcome` field for field, with `issue.IssuedRun` nested
    under `issued` rather than flattened: the issue lane's own result is passed
    THROUGH by the release module for the stated reason that re-summarising it
    would create a second version of *"how many bills went out"*, and flattening
    it here would do exactly that one layer further out.

    **`unavailable` AND THE THREE PROBLEM LISTS ARE SERVED, ALWAYS.** A caller
    reading `issued: 480` must not have to infer that nothing was dispatched,
    that the print floor is the only channel, or that a tax bucket had no
    authority. `handoffs` is the same discipline at the release level: `ran:
    true` on the render and the queue write means the work happened, never that
    a customer received a bill.

    Money is text with its currency (rule 2 / DEF-099), and `credit_applied` is
    NULL rather than `"0.000000"` when no bill could reach the payments seam —
    *nobody asked* and *these customers had no credit* are different facts.
    """
    issued = outcome.issued
    return {
        "created": created,
        "bill_run_id": outcome.bill_run_id,
        "release_id": outcome.release_id,
        "released_at": _iso(outcome.released_at),
        "issued": {
            "issued": list(issued.issued),
            "issued_count": len(issued.issued),
            "already_issued": list(issued.already_issued),
            "broken": [
                {
                    "reason": entry.reason,
                    "detail": entry.detail,
                    "invoice_id": entry.invoice_id,
                    "invoice_no": entry.invoice_no,
                    "account_id": entry.account_id,
                }
                for entry in issued.broken
            ],
            "posted": issued.posted,
            "already_posted": issued.already_posted,
            "posting_problems": [dict(entry) for entry in issued.posting_problems],
            "delivery_queued": issued.delivery_queued,
            "delivery_already_queued": issued.delivery_already_queued,
            "delivery_problems": [dict(entry) for entry in issued.delivery_problems],
            "credit_applied": _decimal_str(issued.credit_applied),
            "credit_bills": issued.credit_bills,
            "autopay_intents": issued.autopay_intents,
            "autopay_already_recorded": issued.autopay_already_recorded,
            "payment_problems": [dict(entry) for entry in issued.payment_problems],
            "queue_rows_resolved": issued.queue_rows_resolved,
            # ── BR-BIL-025 PER ACCOUNT (CR-052 tasks 12 and 13) ────────────
            # These three REPLACE the `one_template_pin_for_the_whole_run`
            # notice that used to ride on `unavailable`. Withdrawing a stated
            # absence without serving the fact it stood in for would leave a
            # caller with less than it had, so the counters go in the same
            # commit: how many bills resolved their OWN template, how many took
            # the run's, and the distinct reasons any could not be read.
            # `getattr` with a default because `IssuedRun` is also built by the
            # correction and fee paths' own callers in tests written before
            # these fields existed.
            "template_resolved_per_account": getattr(issued, "template_resolved_per_account", 0),
            "template_pinned_by_run": getattr(issued, "template_pinned_by_run", 0),
            "template_problems": [
                dict(entry) for entry in getattr(issued, "template_problems", ())
            ],
            "unavailable": [dict(entry) for entry in issued.unavailable],
        },
        "handoffs": [dict(entry) for entry in outcome.handoffs],
    }


# ══════════════════════════════════════════════════════════════════════════
# S30 FIX A BILL — the read model behind /corrections (US-BIL-015/016/031)
#
# Added 2026-08-16 by the billing SURFACE lane. Until this commit the whole
# correction engine — `corrections.py`, `bulk_corrections.py`,
# `single_correction.py`, `document_correction.py`, 170KB of it — had no read
# model at all, because it had no caller that was not a test. Four properties,
# each deliberate:
#
#   1. **NOTHING HERE WRITES, INCLUDING THE PREVIEW.** `open_case` writes the
#      case, its pinned bills and their impacts, and that is a SERVICE call the
#      API makes on a POST. A GET on this surface can never open a case: a
#      clerk refreshing the list must not mint a correction.
#   2. **MONEY IS SERVED AS STRINGS BESIDE ITS CHAR(3).** Every figure below
#      travels as the stored decimal string with `currency` on the same object.
#      A correction's delta is the number a customer's balance moves by; a bare
#      `-19.92` in a response is half a fact (CLAUDE.md rule 2).
#   3. **AN UNKNOWN, MALFORMED AND CROSS-TENANT CASE ID ARE ONE ANSWER** (HR-1),
#      the same posture `invoice_or_404` takes and for the same reason.
#   4. **THE ROWS ARE SERVED IN THE SERVICE LAYER'S ORDER.** `case_bills`
#      sorts warned-first then largest-delta-first and says why (BR-BIL-046,
#      TC-10); re-sorting here by invoice number is the order that hides a
#      systematic error in the middle of page four.
# ══════════════════════════════════════════════════════════════════════════


def correction_case_queryset() -> QuerySet:
    """Every correction case of THIS tenant, newest first.

    Hard rule 1: the explicit `tenant_id` filter, with RLS FORCE as the second
    and independent guarantee. Newest first because a correction list is worked
    from the top — a case opened this morning is the one somebody is waiting to
    approve.
    """
    from apps.billing.correction_models import CorrectionCase

    return CorrectionCase.objects.filter(tenant_id=_tenant_id()).order_by("-created_at", "-id")


def correction_case_or_404(case_id: Any) -> Any:
    """One case of THIS tenant, or the one answer HR-1 allows."""
    from apps.billing.correction_models import CorrectionCase

    if not _is_uuid(case_id):
        raise errors.NotFoundError()
    try:
        return CorrectionCase.objects.get(tenant_id=_tenant_id(), pk=case_id)
    except CorrectionCase.DoesNotExist as missing:
        raise errors.NotFoundError() from missing


def correction_case_row(case: Any) -> dict[str, Any]:
    """One case as the S30 Fix-a-bill list draws it.

    `bills`, `net_delta` and `currency` come off the PERSISTED aggregate the
    preview stored, not off a fresh sum: BR-BIL-044 makes the preview the
    artifact approval binds, and a list re-summing the rows could show a total
    the approver never saw. When a case has no stored aggregate — which cannot
    happen through `open_case` and can happen to a row written by an older
    build — the figures are served NULL rather than 0.00. A zero here would say
    "this correction moves no money", which is a class-D claim about a case that
    may be restating four hundred bills.
    """
    aggregate = dict((case.preview or {}).get("aggregate") or {})
    return {
        "id": str(case.pk),
        "case_no": case.case_no,
        "status": case.status,
        "correction_class": case.correction_class,
        "reason_codes": list(case.reason_codes or []),
        "scope_kind": case.scope_kind,
        "scope": dict(case.scope or {}),
        "bills": aggregate.get("bills"),
        "net_delta": aggregate.get("net_delta"),
        "currency": aggregate.get("currency"),
        # `CR-180-BRC10` A3/A4 — a case sent with correction rows names its
        # posting MONTH (`2026-10`), the form the revamped screen reads; an
        # older case keeps the date it always served.
        "posting_period": (
            None
            if case.posting_period is None
            else case.posting_period.strftime("%Y-%m")
            if (case.scope or {}).get("correction_items")
            else case.posting_period.isoformat()
        ),
        "preview_hash": case.preview_hash,
        "initiated_by": None if case.initiated_by_id is None else str(case.initiated_by_id),
        "approved_by": None if case.approved_by_id is None else str(case.approved_by_id),
        # `CR-180-BRC10` B9 / `DEF-BIL-5357` — WHO, by NAME (B14 rule 31: no
        # database id is the visible value of a field). Null when nobody, and
        # null for a user whose name is still blank (an invited user), never "".
        "initiated_by_name": _user_name(case, "initiated_by"),
        "approved_by_name": _user_name(case, "approved_by"),
        "approved_on": None if case.approved_on is None else case.approved_on.isoformat(),
        "executed_on": None if case.executed_on is None else case.executed_on.isoformat(),
        "closed_reason": case.closed_reason,
        # DEF-BIL-10100 — closed with a reason and no bill corrected: the list
        # says "Closed" and shows no net change, never "Done" and the preview's.
        "closed_without_correcting": _closed_without_correcting(case),
        "created_at": _iso(case.created_at),
    }


def _closed_without_correcting(case: Any) -> bool:
    if not case.closed_reason:
        return False
    from apps.billing.correction_models import CorrectionCaseBill

    return not CorrectionCaseBill.objects.filter(
        tenant_id=case.tenant_id, case=case, status="done"
    ).exists()


def _user_name(case: Any, relation: str) -> str | None:
    """A correction case's actor, by name — `CR-180-BRC10` B9. The FK is the
    case's own (`correction_cases.initiated_by` / `approved_by`), so this
    follows billing's own relation and imports nothing of identity's."""
    if getattr(case, f"{relation}_id", None) is None:
        return None
    user = getattr(case, relation, None)
    return (getattr(user, "full_name", "") or "").strip() or None


def correction_bill_row(row: Any) -> dict[str, Any]:
    """One pinned bill inside a case — its impact, its result, its artifacts.

    `impact` is served WHOLE and un-reshaped. It is what `build_impact`
    produced, it is what the content hash covers, and it is what the approver
    read; picking members out of it here would give the screen a different
    artifact from the one BR-BIL-044 binds.
    """
    return {
        "invoice_id": str(row.invoice_id),
        # `CR-180-BRC10` A5 — the NUMBERS a person reads, beside the ids the
        # screen keys on (B14 rule 31: an id is never the visible value).
        "invoice_no": getattr(row.invoice, "invoice_no", None),
        "credit_note_no": (
            None if row.credit_note_id is None else getattr(row.credit_note, "credit_note_no", None)
        ),
        "rebill_invoice_no": (
            None
            if row.rebill_invoice_id is None
            else getattr(row.rebill_invoice, "invoice_no", None)
        ),
        "account_id": None if row.account_id is None else str(row.account_id),
        "delta_amount": _decimal_str(row.delta_amount),
        "currency": row.currency,
        "direction": row.direction,
        "status": row.status,
        "failure_reason": row.failure_reason,
        "warnings": [dict(entry) for entry in (row.warnings or [])],
        "impact": dict(row.impact or {}),
        "credit_note_id": None if row.credit_note_id is None else str(row.credit_note_id),
        "rebill_invoice_id": (
            None if row.rebill_invoice_id is None else str(row.rebill_invoice_id)
        ),
        "document_instance_id": (
            None if row.document_instance_id is None else str(row.document_instance_id)
        ),
    }


# ══════════════════════════════════════════════════════════════════════════
# S30 BUDGET BILLS — the read model behind /budget-billing (US-BIL-018..020)
# ══════════════════════════════════════════════════════════════════════════


def budget_status_row(status: Any, *, effective_level: Decimal) -> dict[str, Any]:
    """One account on the budget programme, as S30's Budget Bills tab draws it.

    `level` and `level_override` are served SEPARATELY and `effective_level` is
    the third member rather than a replacement for either. BR-BIL-017 (OQ-068)
    keeps both, because the ±30% override bound is measured against the COMPUTED
    level — collapsing them here would make the screen unable to say what the
    next override will be validated against, and a clerk typing 200 needs to
    know the bound is 169.40–314.60 and not something derived from 200.

    `variance_balance` is a POSITION and travels signed with its currency: a
    negative balance is money the customer has under-paid against their actuals
    and a positive one is money they are ahead. Never rendered as an absolute.
    """
    return {
        "account_id": str(status.account_id),
        # ⛔ B14 rule 31 / DEF-3158 (2026-09-02). S30's Budget Bills tab printed
        # `account_id.slice(0, 8)` in its first column — with NO fallback, so the
        # truncated database id was the visible value on EVERY row, every time.
        # The rule's own answer is *"where the reference is genuinely what a user
        # needs it has a HUMAN-FACING number and that is what is shown"*, and the
        # account has one; nothing served it. `account` is the reviewed
        # cross-module FK this table already carries (B2 §2), read for its number
        # exactly as `apps/billing/pending.py:300` reads it for the pending
        # queue. Nullable in the schema, so the screen states the absence rather
        # than falling back to the id (which is the breach again, one branch on).
        "account_no": getattr(status.account, "account_no", None),
        # §05 screen 25 draws the CUSTOMER'S NAME under the account number, and
        # it is the half a clerk reads: *"100412 / Navarro, P."*. Through
        # customers' own published read (B1), which REFUSES rather than
        # answering None when it is unpublished — the same posture
        # `_customer_name` already takes for a bill, and for the same reason:
        # "no name recorded" and "the name could not be read" are different
        # statements and only one of them is ever true.
        "customer_name": _customer_name(status.account),
        "status": status.status,
        "level": _decimal_str(status.level),
        "level_override": _decimal_str_or_none(status.level_override),
        "level_override_reason": status.level_override_reason,
        "effective_level": _decimal_str(effective_level),
        "variance_balance": _decimal_str(status.variance_balance),
        "currency": status.currency,
        "settle_up_month": status.settle_up_month,
        "enrolled_on": None if status.enrolled_on is None else status.enrolled_on.isoformat(),
        "last_leveled_at": (
            None if status.last_leveled_at is None else status.last_leveled_at.isoformat()
        ),
    }


def budget_event_row(event: Any) -> dict[str, Any]:
    """One append-only `account_budget_events` row (US-BIL-019 TC-6's trail).

    Every money member carries the row's own currency. `movement` is signed and
    `balance_after` is the running total AFTER it — served rather than derived
    on the client, because the client would have to know the order.
    """
    return {
        "id": str(event.pk),
        "event": event.event,
        "occurred_on": event.occurred_on.isoformat(),
        "level": _decimal_str_or_none(event.level),
        "actual": _decimal_str_or_none(event.actual),
        "movement": _decimal_str(event.movement),
        "balance_after": _decimal_str(event.balance_after),
        "currency": event.currency,
        "reason": event.reason,
        "invoice_id": None if event.invoice_id is None else str(event.invoice_id),
    }


def budget_programme_overview() -> dict[str, Any]:
    """EVERY account on the budget programme, with the tenant's own S69 rules.

    Added for `CR-075` runbook 33, *Budget billing re-level*. The runbook needs
    two things before it can walk anybody — the enrolled accounts and the drift,
    cadence and averaging window a re-level is decided by — and asking for them
    separately would be two reads that can disagree about which settings the
    levels in front of them were computed under.

    ⚠ **THE SETTINGS ARE READ, NEVER DEFAULTED, AND AN UNREACHABLE ONE
    REFUSES.** `budget_service._params` records the reasoning and this call goes
    through it rather than round it: an unreachable `relevel_drift_pct` is not
    twenty, and re-levelling a customer's monthly payment against an invented
    band is a change to what they pay that their own settings forbid
    (`BR-BIL-021`).

    ⚠ **`level` AND `level_override` BOTH TRAVEL AND NEITHER REPLACES THE
    OTHER** (`BR-BIL-017` as `OQ-068` closed it). The ±30% override bound is
    measured against the COMPUTED level, so a caller handed only the effective
    one could not say what the next override would be validated against — the
    same reason `budget_status_row` serves all three.

    ⚠ **`enrolled_on` AND `last_leveled_at` ARE BOTH HERE BECAUSE A NULL
    `last_leveled_at` IS NOT AGE ZERO.** An account enrolled six months ago and
    never re-levelled since is DUE; one enrolled yesterday is not, and only the
    enrolment date tells them apart.
    """
    from apps.billing import budget, budget_service

    rows = list(
        budget_service.status_queryset()
        .filter(status=budget.STATUS_ENROLLED)
        .select_related("account")
        .order_by("account__account_no", "id")
    )
    return {
        "settings": dict(budget_service._params()),
        "accounts": [
            budget_status_row(
                status, effective_level=budget_service.effective_level(status)
            )
            for status in rows
        ],
    }


def budget_history_for(account_id: Any, *, months: int = 12) -> dict[str, Any]:
    """The trailing actuals `budget_service.enroll` and `relevel` need, READ.

    ⚠ **THE MONTHS OF HISTORY AND THE ACTUALS ARE FACTS ABOUT BILLING'S OWN
    TABLE, so billing reads them — and it reads ISSUED bills only.** A draft is
    not an actual: enrolling an account on a level computed from bills nobody
    has sent would set what a customer pays for a year off numbers that can
    still change. Void bills are excluded for the same reason and corrected
    originals are excluded because their rebill is in the set instead (only the
    latest in a chain carries `issued`/`paid`).

    `months_of_history` is the count of DISTINCT billed periods, not the count
    of bills: two bills in one month (a cycle bill and a back-bill) are one
    month of history, and counting them as two would let an account enrol on
    six months of data that BR-BIL-017's eligibility rule says is not enough.

    Returns the actuals NEWEST FIRST and their currency. When the account has
    never been billed the actuals are empty and `currency` is None — never
    "USD", which would be this module inventing a tenant's currency.
    """
    rows = list(
        Invoice.objects.filter(
            tenant_id=_tenant_id(),
            account_id=account_id,
            status__in=(INVOICE_ISSUED, INVOICE_PAID),
        )
        .order_by("-period_end", "-id")
        .values("total", "currency", "period_start", "period_end")[: max(months * 2, months)]
    )
    actuals = [str(row["total"]) for row in rows[:months]]
    periods = {(row["period_start"].year, row["period_start"].month) for row in rows}
    currencies = {row["currency"] for row in rows if row["currency"]}
    return {
        "actuals": actuals,
        "months_of_history": len(periods),
        "currency": next(iter(sorted(currencies)), None) if len(currencies) == 1 else None,
        "mixed_currency": len(currencies) > 1,
        "bills_read": len(rows),
        # `CR-085` `CPB-18` — WHICH months are missing, newest first, as
        # `(year, month)` pairs. See `missing_billed_months` for why the window
        # ends at the newest bill and not at today's date.
        "missing_months": missing_billed_months(periods, months=months),
        # The FIRST month this account was ever billed, so a caller can tell
        # *you have not been with us long enough* from *one of your bills is
        # missing* — two different answers that a bare count cannot separate.
        "first_billed_month": (min(periods) if periods else None),
    }


def budget_apply_search(qs: QuerySet, term: str) -> QuerySet:
    """§05 screen 25's toolbar: *"Search account #, customer or address…"*.

    THREE LEGS AND EXACTLY THREE, because the drawn placeholder is the contract
    (B14 rule 19) and a fourth silent leg is a screen that lies about what it
    searched. They are the SAME three the bills list already uses
    (`_apply_search`), reached through the SAME published customers reads, so
    one term means one thing on both screens.

    ⚠ **THE ADDRESS LEG IS LAZY AND THE NAME LEG IS NOT**, which is
    `_apply_search`'s own split and its reasoning carries over unchanged: the
    address read hands back an unevaluated queryset Django renders as a nested
    subquery, so the page is still cut in SQL (`NFR-3`); the name read builds
    customers' `account_list` and is filtered in Python.

    REFUSES when either read is unpublished rather than dropping its leg: a
    clerk who searches *Navarro* and sees nothing concludes Navarro is not on a
    level.
    """
    if len(term) < MIN_SEARCH_CHARS:
        return qs
    matches = Q(account__account_no__icontains=term)
    account_ids = _account_ids_by_customer_name(term)
    if account_ids:
        matches |= Q(account_id__in=account_ids)
    matches |= Q(account_id__in=_account_ids_at_address(term))
    return qs.filter(matches)


def budget_actuals_to_date(status_ids: Sequence[Any]) -> dict[Any, tuple[str, int]]:
    """§05 screen 25's `ACTUAL TO DATE` column, for a WHOLE PAGE in one query.

    The figure is what the meter has actually said since the account was put on
    its level — the sum of `actual` across its budget events — and it is the
    number the drawn table puts beside `THEY PAY` so a clerk can see the two
    diverge before the settle-up does it for them.

    ⚠ **ONE QUERY FOR THE PAGE, NOT ONE PER ROW.** `budget_history_for` is a
    per-account read and fifty of them is the N+1 that `select_related("account")`
    was added to this very screen to avoid (`budget_status_row`'s own note).
    This groups in SQL instead, so the column costs one round trip however many
    rows the page holds — which is what `NFR-3`'s pagination is for.

    ⚠ **IT COUNTS `billed` EVENTS, NOT "EVENTS THAT CARRY AN ACTUAL" —
    `DEF-BIL-5327`.** Those two read as the same set and are not. A settle-up
    month writes TWO rows for one bill: the `billed` row that moves the variance
    and the `settled` row that resets it, and `budget_service._record_event`
    copies `level` and `actual` onto the second one so a year-end row can
    reproduce what the customer was shown. Filtering on `actual__isnull=False`
    therefore added the settle-up month's actual TWICE and counted it as an
    extra month. Measured on the ❄️ frozen WE-8 chain driven through its
    settle-up: **$921.77 over 4 months served where $723.02 over 3 is true** —
    overstated by **$198.75**, which is September's actual counted a second
    time. The month count inflated with it, so the row looked internally
    consistent and the column was wrong on every account that had ever settled.
    **The event kind is the fact being asked for; "has an actual" was a proxy
    for it that stopped being true the moment a second event kind carried one.**

    Returns `{status_id: (summed actual as a decimal string, months counted)}`.
    An account with no billed month yet is ABSENT from the map, and the caller
    renders that as the absence it is — never as `0.00`, which would say the
    meter read zero.
    """
    if not status_ids:
        return {}
    rows = (
        AccountBudgetEvent.objects.filter(
            tenant_id=_tenant_id(),
            budget_status_id__in=list(status_ids),
            event=BUDGET_EVENT_BILLED,
        )
        .values("budget_status_id")
        .annotate(total=Sum("actual"), months=Count("id"))
    )
    return {row["budget_status_id"]: (str(row["total"]), int(row["months"])) for row in rows}


def budget_settle_up_windows(status_ids: Sequence[Any]) -> dict[Any, dict[str, Any]]:
    """§05 entry 25.2's two money columns, for a WHOLE PAGE in two queries.

    The drawing puts `PAID ON THE LEVEL` beside `ACTUAL SO FAR` — *"what they
    paid on the level beside what the year has actually cost"* — and this is
    both sums, over the settle-up period each account is currently inside.

    ⚠ **THE PERIOD STARTS AT THE LAST SETTLE-UP, NOT AT ENROLMENT.** A settle-up
    resets the variance balance to zero (`budget_service.record_bill` writes a
    `settled` row whose movement is the negation of the balance), so summing
    from enrolment would report two or three years against a balance that only
    covers the current one — and the drawn table's three money columns would
    stop tying out. Accounts that have never settled are summed from enrolment,
    which is the same rule with an empty left edge.

    ⚠ **THE BOUNDARY IS STRICTLY AFTER, AND THAT IS NOT AN OFF-BY-ONE.** The
    `billed` row and the `settled` row of a settle-up month share an
    `occurred_on`, and `record_bill`'s own comment says why the bill belongs to
    the year being closed: *"the balance to true up is the position AFTER this
    month's movement: this bill's own variance belongs to the year being
    settled."* So `occurred_on > last_settled_on` excludes that bill from the
    NEW period, which is exactly where the balance says it is.

    ⚠ **IT FILTERS ON THE EVENT KIND, NEVER ON "HAS A LEVEL"** — `DEF-BIL-5327`
    is that mistake made once already. Five of the six event kinds carry a
    `level` (enrolment, a re-level, an override and a removal all stamp one), so
    a `level__isnull=False` sum here would add a decision to a year of bills.

    **THE THREE COLUMNS TIE OUT BY CONSTRUCTION, and that is what lets the
    screen render the sign without doing arithmetic.** A `billed` row's movement
    is `level − actual`, so over this window `Σlevel − Σactual` IS the account's
    variance balance — the same figure `budget.settle_up` turns into a direction
    and a positive amount. The caller serves all three and the browser adds
    nothing.

    Returns `{status_id: {"paid_on_level", "actual_so_far", "months",
    "last_settled_on"}}`, the two sums as decimal STRINGS (never floats — rule
    2). A status with no billed month inside its current period is ABSENT from
    the map, and the caller renders the absence rather than `0.00`.
    """
    if not status_ids:
        return {}
    ids = list(status_ids)
    settled = (
        AccountBudgetEvent.objects.filter(
            tenant_id=_tenant_id(),
            budget_status_id__in=ids,
            event=BUDGET_EVENT_SETTLED,
        )
        .values("budget_status_id")
        .annotate(last_settled_on=Max("occurred_on"))
    )
    last_settled = {row["budget_status_id"]: row["last_settled_on"] for row in settled}

    billed = AccountBudgetEvent.objects.filter(
        tenant_id=_tenant_id(), budget_status_id__in=ids, event=BUDGET_EVENT_BILLED
    )
    # One query for the page, and the window is per account — so the left edge
    # is an OR of per-status conditions rather than one date. `NFR-3` is about
    # not reading the TENANT per page; this reads the page's own bills, which is
    # bounded by the page size however many accounts a utility has.
    window = Q(pk__in=[])
    for status_id in ids:
        cut = last_settled.get(status_id)
        leg = Q(budget_status_id=status_id)
        if cut is not None:
            leg &= Q(occurred_on__gt=cut)
        window |= leg
    rows = (
        billed.filter(window)
        .values("budget_status_id")
        .annotate(paid=Sum("level"), actual=Sum("actual"), months=Count("id"))
    )
    return {
        row["budget_status_id"]: {
            "paid_on_level": None if row["paid"] is None else str(row["paid"]),
            "actual_so_far": None if row["actual"] is None else str(row["actual"]),
            "months": int(row["months"]),
            "last_settled_on": last_settled.get(row["budget_status_id"]),
        }
        for row in rows
    }


def missing_billed_months(
    periods: set[tuple[int, int]], *, months: int
) -> list[tuple[int, int]]:
    """The months in the averaging window that carry no issued bill.

    ⚠ **WHY THIS EXISTS.** `budget_history_for` could already say *8 of 12*,
    and `CWP-044` said exactly that: *"You have 8 months of bills with us and
    we average 12."* A customer reading it cannot tell whether they simply
    have not been with the utility for a year or whether one of their bills is
    missing, and they cannot act on either — which is `CR-085` `CPB-18`'s
    whole complaint (*"or says precisely which month is missing"*).

    ⚠ **THE WINDOW ENDS AT THE NEWEST BILLED MONTH, NOT AT TODAY.** Reading a
    clock here would make this answer change on the first of every month for
    an account nobody had billed yet, and would count the CURRENT month —
    which is not late, it is simply not billed yet — as missing. The newest
    bill is a fact in the same table as the rest of the answer, so the whole
    read stays a read (`BR-TEN-043`: a business date is the caller's, and this
    function is given none on purpose).

    ⚠ **AN ACCOUNT WITH NO BILLS AT ALL HAS NO MISSING MONTHS, IT HAS NO
    HISTORY.** Returning twelve months of absences for somebody who joined
    last week would be true and useless; `CWP-044` already has a sentence for
    *we have not billed you yet* and this must not displace it.

    Newest first, matching `actuals`.
    """
    if not periods:
        return []
    newest = max(periods)
    window: list[tuple[int, int]] = []
    year, month = newest
    for _ in range(months):
        window.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return [pair for pair in window if pair not in periods]


# ═══════════════════════════════════════════════════════════════════════════
# P5.8 — THE PRINTED DOCUMENT NUMBERS, PUBLISHED FOR THE LEDGER TO ASK FOR
# ═══════════════════════════════════════════════════════════════════════════
# Finance blueprint p018 `P5.8` — *"They publish the document numbers … P5.3
# cannot be done inside Finance. This is the dependency that gates the phase"*.
#
# `apps/ledger/reporting.account_ledger` draws a **Reference** column that
# should read `BL-2607-018204` and reads a UUID instead, because a journal line
# carries the source document's id and nothing else. Turning one into the other
# is a read of BILLING's own tables, and `apps/ledger` may not touch them
# (`BR-TEN-013`, gate `G6`). So billing publishes the read and the ledger
# resolves it BY NAME through `apps/ledger/billing_seam.py`.
#
# ⚠ **A MISS IS AN ABSENT KEY AND NEVER THE UUID.** The whole task is *document
# number, not internal id*; falling back to the id would put the exact value
# this function exists to remove under the name of its replacement, where it
# would read as an answer. `apps/integrations/seams/ledger._document_numbers`
# states the same rule for the WIRE half and these two must not disagree.
#
# ⚠ **THERE ARE TWO FUNCTIONS HERE AND THE TASK'S OWN WANTED-READ NAMES ONE.**
# `apps/ledger/reporting.py` asks for `invoice_numbers_for` and
# `payment_numbers_for`, and MEASURED on the demo tenant those two reach 146 of
# the 147 entries that have a printed number — the 147th is a CREDIT NOTE, whose
# `CM-0001` lives in `credit_notes` and in no invoice row. The feed half already
# resolves all three source kinds (`_DOCUMENT_SOURCES` names `credit_note`
# explicitly), so building only the two named reads would have left the SCREEN
# strictly weaker than the wire over the identical gap, with a uuid still on a
# row and every test green. See `DEF-LED-6653`.
def invoice_numbers_for(ids: Any) -> dict[str, str]:
    """`{invoice_id: invoice_no}` for the bills this tenant can read.

    One query for the whole ask, `{}` for an empty one and no query for it.

    **THREE KINDS OF MISS, AND ALL THREE ARE THE SAME ABSENT KEY.** An id
    belonging to another tenant (`BR-TEN-003` — a cross-tenant read is an
    ABSENCE, never a refusal, because a refusal is a membership oracle), an id
    that names no invoice at all, and an invoice whose `invoice_no` is NULL.
    The caller cannot tell them apart and must not: each means *this product
    cannot print a number for that row*, and each is answered by leaving the
    key out rather than by mapping it to `None`, so a caller writing
    `numbers.get(id)` gets `None` either way and a caller writing
    `numbers[id]` fails loudly rather than rendering the word "None".
    """
    wanted = _document_ids(ids)
    if not wanted:
        return {}
    rows = Invoice.objects.filter(tenant_id=_tenant_id(), id__in=wanted).values_list(
        "id", "invoice_no"
    )
    return {str(row_id): str(number) for row_id, number in rows if number}


def credit_note_numbers_for(ids: Any) -> dict[str, str]:
    """`{credit_note_id: credit_note_no}` — the same contract, the other table.

    ⚠ **`credit_note_no` IS GENUINELY NULLABLE AND THAT IS NOT A DATA FAULT.**
    `CreditNote`'s own model comment records that the column was null while the
    tenant's *Credit memo #* series was unset; `corrections._allocate_credit_
    note_no` fills it now. An unnumbered credit note therefore exists, is
    lawful, and answers as an absent key — which is the honest answer and the
    same one the wire gives.
    """
    wanted = _document_ids(ids)
    if not wanted:
        return {}
    rows = CreditNote.objects.filter(tenant_id=_tenant_id(), id__in=wanted).values_list(
        "id", "credit_note_no"
    )
    return {str(row_id): str(number) for row_id, number in rows if number}


def _document_ids(ids: Any) -> list[str]:
    """The ask, de-duplicated and ordered, as strings.

    SORTED on purpose: an `IN` list built from a set comes out in whatever
    order the hash gave it, so two identical asks produce two different SQL
    strings and neither the query log nor a plan cache can tell they are the
    same read. Empty strings and `None` are dropped here rather than in each
    caller — a journal line with no `source_id` is an ordinary row, not an
    error, and asking the database about an empty id is a query nobody needs.
    """
    if not ids:
        return []
    return sorted({str(one) for one in ids if one})


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-BIL-005@808e015 (sha1[:7] of the two rule sources this read was authored from, concatenated in order: 04-docs/05-modules/07-billing/02-business-rules.md · 04-docs/05-modules/04-metering/02-business-rules.md — so a later change to either makes this stamp findable as stale in one grep)
# generated: 2026-08-11 by story-coder (rating plan-assignment backdating lane — PO ruling 2026-08-11 item 7, "warn and allow with a reason recorded") · AMENDED 2026-08-11 by story-coder (W3 billing read lane — the S30 list/detail read surface below `INVOICE_SORTS`, co-packet US-BIL-025@e4b0504 / US-BIL-026, the same three sources stamped in apps/billing/api.py)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half — S30's list, detail and the S21 tab already ship and already call these two paths) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: [W3 read lane 2026-08-11] ruff✔ black✔ · pytest tests/test_us_bil_025_026_bills_read.py 17 passed / 3 skipped✔ (RED-proved first: 17/17 failed with `AttributeError: module 'apps.billing.api' has no attribute 'invoices'`) · live-Postgres `-m isolation` 69 passed / 12 skipped✔ (the three new invoices cases RED-proved by removing the `invoices` policy from db/rls_billing_w3.sql) · pytest tests -m golden 12 passed✔ · openapi/schema.json regenerated✔ · [backdating lane] ruff✔ black✔ · pytest tests/test_us_met_003_plan_backdating.py 6 passed✔ (the first five RED first — the verbatim failures are in the trailer of apps/rating/services.py; TC-13 red-proved separately) · pytest tests -m golden✔ · run_gates 15-PASS/0-FAIL/1-SKIP✔
# exceptions: [W3 read lane] `past_due` is served NULL on every row and `f.status=past_due` REFUSES rather than falling back — a reported deviation from BR-SHL-011's "a list URL never errors over its params", because neither payments nor ledger has a table to answer "unpaid" and every silent alternative states something false about a customer's money · `rollup.billed_this_cycle`/`billed_currency`, `document_url`, `deliveries`, `lines[].gl_account_code`, `lines[].tariff_version_label`, `rebill_of_invoice_id` and `corrected_by_invoice_id` are all served NULL under their CONTRACTED names — none is renamed, none is omitted, and each names its reason in the docstring · `f.issued_from`/`f.issued_to` bound the window in UTC rather than the tenant's clock (BR-TEN-020/043) — a filter only; REPORTED · the full exception list is in apps/billing/api.py's trailer · [backdating lane] VOID invoices are counted as issued — a voided bill was still sent, and BR-BIL-004 makes the correction a new row; a deliberate over-inclusion for a warn-only guard, stated in the docstring so it can be overturned deliberately · "latest" is by greatest `period_end`, NOT by issue time (the question is which days are billed) · customers' move-out guard resolves its billing read from apps.billing.SERVICES and is therefore STILL unwired — REPORTED in the docstring and the lane report, not reached into (another lane's territory)
# [run-API lane 2026-08-11] AMENDED: the S31 run read model — `run_or_404`,
#         `run_created_dict`, `cycle_terms_for`, `prepared_for`, `findings_dict`,
#         `exceptions_dict` and their row serializers. Three properties, each a
#         decision: NOTHING here writes (a GET a clerk refreshes cannot commit —
#         `apply_decisions` DOES write and is deliberately not called from a
#         read); the key names are the DATACLASS field names, verbatim, because
#         07-frontend was mirrored off them while no body was contracted; and no
#         clock is read — ~~the run's service date is the CYCLE's bill date~~
#         SUPERSEDED 2026-08-11, see the next entry. `cycle_terms_for` duplicates
#         a private read in apps/billing/issue.py — REPORTED rather than reached
#         into (that file is 🔒), and the shape that should replace both is a
#         published metering selector taking a cycle id, which metering has not
#         got.
# [typed-bill-date lane 2026-08-11] AMENDED: `prepared_for` takes the run's
#         SERVICE date from `runs.effective_bill_date(run.bill_date, cycle
#         bill date)` — the CLERK's typed date wins, the cycle's is the fallback,
#         neither present still REFUSES. BR-BIL-070, PO ruling closing OQ-122
#         option A (*"A Store what they type and use it"*). Worked: cycle 1 Aug,
#         clerk types 3 Aug, a tariff version effective 2 Aug — the run now
#         prices against the 2-Aug version. `cycle_terms_for` is UNCHANGED and
#         still reads the cycle only; it is the fallback source, not the answer.
# [CR-029 RC-W4b lane 2026-08-23] ADDED: `bill_runs_list` + its two batched
#         count helpers — SET-07D's **Runs** tab (B17 §4), the run history the
#         cycle detail had no endpoint for. Three queries for the whole page
#         whatever its length (measured: 6 runs × 5 accounts = 3 queries).
#         FOUR THINGS IT DOES NOT ANSWER, each stated rather than invented:
#         `run_no` NULL (no bill-run number series exists; D5 ruled the grammar
#         for routes and cycles only — ROUTED to the PO) · NO MONEY of any kind
#         (BR-MET-078 hardened by this CR) · `status` is the STORED column and
#         nothing in this module ever advances it off "draft" (REPORTED as a
#         defect; the tab's honest composite comes from `issued_at` + `held`) ·
#         `issued_at` is the EARLIEST invoice issue on the run, a judgment where
#         no rule spoke, argued in the block above the selector.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

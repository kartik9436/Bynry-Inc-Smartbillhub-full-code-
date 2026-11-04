# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 3 — the JOINING READ behind R43 Trend
#           Pack, and the fix for `DEF-REP-6937`. Drawing read as an IMAGE
#           (B14 rule 42): p059 of `05-prototype/09 Reports Build Brief.pdf`,
#           rendered at 2.0x by `10-scripts/pdf/pdf_render.py`.
# Story:    R43 `trend_pack` — Finance › Performance · **Posting date**
#           (`reports/migrations/0003_seed_catalogue.py` line 228).
# Rules:    `BR-REP-034` (the target is TYPED and empty on every tenant today,
#           so the tile degrades to the figure alone; day-prorated comparisons
#           are FORBIDDEN) · `BR-REP-009` (collection % = cash applied to bills
#           in period ÷ billed in period) · `BR-REP-011` (DSO = (AR ÷ billed
#           last 12 months) × 365, rolling, posting basis) · `BR-REP-022` (the
#           DSO target is a tenant setting, default 15) · `BR-REP-001` (a money
#           report names its basis) · `BR-REP-024` (a figure that cannot be
#           produced is NULL with its reason, never a 0 and never a plausible
#           number) · `BR-TEN-022` (the period card is COMPUTED, never stored) ·
#           `BR-TEN-043` (the business date is an argument, never a clock) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 2 (money 4
#           decimals, percentages 6, both DISPLAY 2) · hard rules 4 and 5 (this
#           file writes nothing and posts nothing) · B14 rule 35 (a catalogue is
#           written in its own language, never composed in English here)
# Tests:    06-backend/tests/test_rep_p6w3_trend_pack.py
#           06-backend/tests/test_rep_p6w3_trend_pack_grain.py (DEF-REP-6937)
#           10-scripts/p6w3_cost.py (the PostgreSQL measurement)
# Impacts:  apps/ledger/tenancy_seam.py · apps/ledger/payments_seam.py ·
#           apps/ledger/billing_seam.py · apps/ledger/dimension_seam.py
#           (four seam reads, one per foreign module) ·
#           apps/billing/selectors.invoices_issued_between (ONE derivation of
#           *which bills went out*, resolved by two seams) ·
#           apps/payments/selectors.allocated_to_invoices_issued_between (the
#           read `reporting.GAP_ALLOCATION_PERIOD` named in its `wanted_reads`) ·
#           apps/customers/accounts_dataset.accounts_on_the_books ·
#           apps/reports/queries.py (the per-key viewer and its stream) ·
#           apps/reports/exports.py (the export resource — otherwise a live
#           Download button over a 404)
# ───────────────────────────────────────────────────────
"""**R43 TREND PACK — one row per FISCAL PERIOD**, twelve of them, four aggregates.

═══════════════════════════════════════════════════════════════════════════════
WHAT WAS HERE BEFORE, AND WHY IT IS THE POINT — `DEF-REP-6937`
═══════════════════════════════════════════════════════════════════════════════
`runner.run("trend_pack")` returned **one row per JOURNAL LINE**: thirty-six
rows of `posted_on / account_code / debit / credit`, raw ledger lines, under the
title *Trend Pack*, to a clerk. R42 Operational Dashboard — its neighbour in the
same section, on the same dataset, with the same by-period shape — was refused
by name; R43 was not, because a hand-kept refusal map was missing one key.

**A key missing from a hand-kept map is indistinguishable from a deliberately
absent one.** Every gate passed, the viewer drew real rows and the footer
footed. That is hard-won law 7's *looking at the wrong thing*, and it is why
`queries.JOURNAL_LINES_DEFINITIONS_NOT_SERVED` now names `trend_pack` **and
keeps naming it after this file exists** — `runner.queries_for` checks `VIEWERS`
first, so the per-key viewer bypasses the refusal without deleting it, exactly
as `BR-REP-039` left `work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN`
standing.

═══════════════════════════════════════════════════════════════════════════════
ONE ROW IS ONE FISCAL PERIOD — AND THE PERIODS ARE COMPUTED, NOT STORED
═══════════════════════════════════════════════════════════════════════════════
p059 draws `P10 · Jul`, `P11 · Aug`, `P12 · Sep` under a **Periods 12** control.
`BR-TEN-022` makes the period card a COMPUTATION over the tenant's fiscal-year
fields, so the spine is walked rather than selected: the period containing
`as_of`, then the period containing the day before its start, twelve times.

⚠ **A TENANT WITH NO FISCAL YEAR START HAS NO PERIODS AND GETS NONE.**
`tenancy.current_period()` answers `None` there, and this read publishes an
empty set of rows with `GAP_NO_FISCAL_CALENDAR` rather than falling back to
twelve calendar months. A trend keyed on a calendar the utility does not keep
its books by is a confident wrong answer, which is the whole of `BR-REP-024`.

⚠ **THE `· Jul` HALF OF THE DRAWN LABEL IS NOT COMPOSED HERE.** `period` is
`"P10"` — a fiscal ordinal, which is language-free — and `period_start` /
`period_end` travel beside it. B14 rule 35 puts a catalogue in its own language
rather than translated from English, and a server that emitted `Jul` would have
decided for eleven of them. The screen composes what it needs from the two
dates it already knows how to render regionally.

⚠ **THERE IS NO TOTAL ROW, AND THE DRAWING IS RIGHT ABOUT THAT.** `totals` is
empty on purpose, which is what makes the viewer draw no footer. Summing this
report is meaningless in three different ways at once and it is worth naming
each, because the next lane's instinct will be to add one:

  * **RATE and DSO are RATIOS.** Σ of twelve percentages is not a percentage,
    and Σ of twelve DSO figures is not a number of days.
  * **ACCOUNTS is AS-OF.** The same account is counted in all twelve rows, so a
    column sum reports a utility twelve times its own size.
  * **TARGET is PER PERIOD.** Adding twelve monthly targets produces an annual
    one the utility never typed.

REVENUE, COLLECTED and REBILLS *are* additive down the column — and a footer
holding three figures under a table of eight, three of which are silently
wrong, is worse than no footer. p059 draws none.

═══════════════════════════════════════════════════════════════════════════════
THE FOUR AGGREGATES, AND THE TWO RATIOS DERIVED FROM THEM
═══════════════════════════════════════════════════════════════════════════════
**REVENUE** — billed in the period, POSTING basis: debits to the designated AR
account whose entry's `source_type` is a bill (`reporting.BILL_SOURCE_TYPES`).
It is the ledger's own `billed`, struck over one period, by one derivation.

**COLLECTED** — `BR-REP-009`'s numerator, and it is **not** cash received in the
window. *"Cash applied to bills IN PERIOD"*: a payment landing on 2 July against
a bill issued on 28 June belongs to JUNE. The attribution lives in payments'
`allocations`, which is exactly what `reporting.GAP_ALLOCATION_PERIOD` has named
in its `wanted_reads` since August. **That gap stays where it is** — it is true
of `revenue_and_ar`, whose `collection_pct` still answers None, and moving a
shipped KPI on S36 is that screen's owner's decision rather than a report lane's.

**ACCOUNTS** — how many accounts were on the books at the period END, counted by
R22 Account Census's own membership rule through one seam. Not re-derived here:
two spellings of *as at a date* is how two screens report two sizes for one
utility on one day, both plausible, neither showing the other.

**REBILLS** — corrections issued in the period, `invoices.bill_type='rebill'`.

**RATE** = COLLECTED ÷ REVENUE × 100, to six decimal places (hard rule 2),
**NULL with a reason in a period that billed nothing** — a rate over a zero
denominator is not 0%, it is undefined, and a quiet period printing `0.00%`
reads as a collections failure that did not happen.

**DSO** = (AR at the period end ÷ billed in the **twelve months ending there**)
× 365, `BR-REP-011` word for word. ⚠ **IT IS NULL UNTIL TWELVE MONTHS OF BOOKS
EXIST**, with `GAP_DSO_NEEDS_TWELVE_MONTHS`, and `reporting.py` already made
exactly this call in its own words: *"a tenant three months into the product
would get a DSO computed on three months and labelled as twelve, which reads as
a collections crisis that is not happening."* The test asserts the NULL first,
because that is the state every new tenant is in.

═══════════════════════════════════════════════════════════════════════════════
`BR-REP-034` — THE TARGET IS TYPED, AND IT IS EMPTY EVERYWHERE TODAY
═══════════════════════════════════════════════════════════════════════════════
The PO ruled option B on 2026-08-18 and ruled the fallback in the same breath:
*"With no target typed, the tile degrades to … the figure alone, no sub-line."*
`tenancy.monthly_revenue_target` is DARK on this deployment, so TARGET is NULL
on every row and REVENUE VS TARGET is NULL with its reason. **That is the
ruling, not a stub**, and it is the state proved first.

⚠ **DAY-PRORATED COMPARISONS ARE FORBIDDEN AND NOTHING HERE PRORATES.** Every
figure is struck over a WHOLE period. `BR-REP-034` records the cost of the other
reading with its worked figure: straight-lining reads 58% where the real billed
share is 842/1,247 = 68%, ten points out, because billing is lumpy by cycle.

⚠ **`BR-REP-034` SIGNED A **MONTHLY** TARGET AND THIS DRAWS ONE PER ACCOUNTING
PERIOD.** On a tenant closing monthly those are the same thing; on one closing
QUARTERLY (`close_cadence`) they are not, and comparing a quarter's revenue
against a monthly target would read as 300% of target. That sits inside
`BR-REP-034`'s own *"what the signature does not cover"* clause, it is already
on the agenda in the R43 register row, and this file does **not** decide it:
`GAP_TARGET_CADENCE_UNRULED` is published on every quarterly tenant and the
TARGET column stays NULL there rather than being divided by three.

═══════════════════════════════════════════════════════════════════════════════
COST — WHY THIS REPORT DOES NOT PAGE
═══════════════════════════════════════════════════════════════════════════════
The row count is the **Periods** control, not the tenant. Twelve rows at a
40,000-account utility and twelve rows at a 300-account one, so `page` is
deliberately ABSENT from the payload — `queries._report` publishes it only for a
report bounded by tenant size, and an absent key says *this is all of it*
without claiming *this is page one*. `NFR-3` is untouched: there is nothing to
page. What DOES grow with the tenant is the cost of each row, and that is
measured on real PostgreSQL in `10-scripts/p6w3_cost.py`.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from apps.ledger import (
    billing_seam,
    chart,
    dimension_seam,
    models,
    payments_seam,
    reporting,
    tenancy_seam,
)
from core.tenancy import current_tenant_id

ZERO = Decimal("0")

#: `BR-REP-001`'s basis. The seeded row is POSTING · *"Posting date"*, and every
#: money figure below comes off `journal_entries.entry_date` — the BOOK date.
BASIS_POSTING = "posting"

#: ⚠ **THE REBILLS COLUMN IS DATED BY ISSUE AND THE REPORT SAYS SO.** It counts
#: an ACT — *how many corrections went out in this period* — and the act is the
#: issue. `BR-REP-001` governs what basis a MONEY figure states; this is a
#: count. Published on the wire rather than left to be inferred, because
#: `BR-REP-003` is explicit that unlabelled money is a contract failure and the
#: same courtesy costs one key here.
REBILLS_BASIS_ISSUE = "issue"

#: p059's **Periods** control. Twelve is the drawn default and the number
#: `BR-REP-011`'s rolling DSO window happens to need; they are separate facts
#: and this constant is the first one.
DEFAULT_PERIODS = 12

#: ⚠ **A CEILING ON THE CONTROL, NOT ON THE TENANT.** `NFR-5` forbids a cap that
#: would have to be removed when T4 arrives — a cap on ACCOUNTS, ROWS or a
#: tenant's size. This bounds how many times a caller may ask the fiscal
#: calendar to step backwards in one request, which no tenant's growth ever
#: reaches: at 120 periods a monthly utility is asking for ten years. A request
#: for more is CLAMPED and never refused (`BR-SHL-011`).
MAX_PERIODS = 120

#: `BR-REP-011`'s denominator window, in days. Named because it appears twice —
#: once as the denominator and once as the *have we got this much history* test
#: — and two spellings of one window is how the two come to disagree.
DSO_WINDOW_DAYS = 365

#: Hard rule 2: a percentage is STORED to six places and DISPLAYED at two. The
#: screen does the rounding; this file rounds nothing (*round only at
#: finalization/display*).
PERCENT_PLACES = Decimal("0.000001")

#: The close cadence that makes `BR-REP-034`'s MONTHLY target comparable to a
#: period at all. Read from tenancy's own card rather than typed at a call site.
MONTHLY_PERIOD_MONTHS = 1


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_NO_FISCAL_CALENDAR = {
    "code": "this_tenant_keeps_no_fiscal_calendar",
    "br_ref": "BR-REP-024 · BR-TEN-022 · p059",
    "detail": (
        "R43 is one row per FISCAL PERIOD and `tenancy.current_period()` answers None for a "
        "tenant that has not set a fiscal year start — the period card is COMPUTED from those "
        "fields and never stored (BR-TEN-022). Twelve calendar months are served INSTEAD of "
        "nothing on no tenant: a trend keyed on a calendar the utility does not close its "
        "books by would put a bill run in the wrong row and read as real. Set the fiscal year "
        "start on the Finance controls page and every figure below appears."
    ),
    "wanted_reads": ("apps.tenancy.selectors.current_period",),
}

GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED = {
    "code": "no_revenue_target_is_typed_for_this_tenant",
    "br_ref": "BR-REP-034 · p059",
    "detail": (
        "p059 draws REVENUE VS TARGET 104% over `$124.9k of $120k`. The PO ruled on "
        "2026-08-18 (option B) that the target is a figure the utility TYPES, and ruled the "
        "fallback in the same breath: with no target typed the tile degrades to the figure "
        "alone, no sub-line, no percentage and no bar. Every tenant on this deployment is in "
        "that state — `apps.tenancy.selectors.monthly_revenue_target` is not published — so "
        "the TARGET column and this tile are NULL with this reason rather than measured "
        "against a denominator nobody chose."
    ),
    "wanted_reads": ("apps.tenancy.selectors.monthly_revenue_target",),
}

GAP_TARGET_CADENCE_UNRULED = {
    "code": "a_monthly_target_does_not_price_a_quarterly_period",
    "br_ref": "BR-REP-034 · BR-TEN-022",
    "detail": (
        "BR-REP-034 signed a MONTHLY revenue target and this report draws one row per "
        "ACCOUNTING PERIOD. On a tenant that closes monthly those are the same figure; on one "
        "whose `close_cadence` is quarterly they are not, and a quarter's revenue measured "
        "against a monthly target reads as about 300% of target. That is inside BR-REP-034's "
        "own *what the signature does not cover* clause — whether the field is per-service or "
        "whole-tenant, and now at what cadence — so the TARGET column stays NULL on a "
        "quarterly tenant rather than being multiplied or divided by a number nobody signed."
    ),
    "wanted_reads": (),
}

GAP_DSO_NEEDS_TWELVE_MONTHS = {
    "code": "dso_needs_twelve_months_of_billed",
    "br_ref": "BR-REP-011 · BR-REP-024",
    "detail": (
        "DSO = (AR ÷ billed last 12 months) × 365, rolling, posting basis. The formula is "
        "derivable here and is left NULL for any period whose twelve-month window reaches "
        "back past this tenant's earliest posted entry, because a DSO computed on three "
        "months of books and labelled as twelve reads as a collections crisis that is not "
        "happening. `apps/ledger/reporting.py` made the same call in the same words on the "
        "S36 strip; this report answers it per ROW, so the periods that CAN carry the figure "
        "carry it and the early ones state their absence."
    ),
    "wanted_reads": (),
}

GAP_RATE_HAS_NO_DENOMINATOR = {
    "code": "a_period_that_billed_nothing_has_no_collection_rate",
    "br_ref": "BR-REP-009 · BR-REP-024",
    "detail": (
        "BR-REP-009 makes the collection rate *cash applied to bills in period ÷ billed in "
        "period*. A period that issued no bills has a zero denominator, so the rate is "
        "UNDEFINED and not 0% — and 0% on a quiet month reads as a collections failure that "
        "did not happen. Such a period carries a dash."
    ),
    "wanted_reads": (),
}

GAP_COLLECTED_READ_UNAVAILABLE = {
    "code": "cash_applied_to_this_periods_bills_read_is_unavailable",
    "br_ref": "BR-REP-009 · BR-REP-024 · B1",
    "detail": (
        "COLLECTED is `apps.payments.selectors.allocated_to_invoices_issued_between`, reached "
        "through `apps/ledger/payments_seam.py`. When payments publishes no such read the "
        "column is NULL with this reason and the RATE column goes with it: a collection rate "
        "whose numerator could not be read is not 0%, and the books alone cannot supply it — "
        "a journal entry credits AR in one lump and never records WHICH bill the cash met."
    ),
    "wanted_reads": ("apps.payments.selectors.allocated_to_invoices_issued_between",),
}

GAP_ACCOUNT_COUNT_UNAVAILABLE = {
    "code": "account_census_count_read_is_unavailable",
    "br_ref": "BR-REP-024 · B1",
    "detail": (
        "ACCOUNTS is R22 Account Census's own membership rule, counted through "
        "`apps/ledger/dimension_seam.py`. When customers publishes no such count the column "
        "is NULL with this reason rather than 0 — a utility with no accounts and a utility we "
        "could not ask about are different facts, and only the first is a zero."
    ),
    "wanted_reads": ("apps.customers.accounts_dataset.accounts_on_the_books",),
}

GAP_REBILL_COUNT_UNAVAILABLE = {
    "code": "billing_issued_invoices_read_is_unavailable",
    "br_ref": "BR-REP-024 · B1",
    "detail": (
        "REBILLS is `apps.billing.selectors.invoices_issued_between`, reached through "
        "`apps/ledger/billing_seam.py`. When billing publishes no such read the column is "
        "NULL with this reason and never 0 — *no corrections went out* and *we could not ask* "
        "are different facts."
    ),
    "wanted_reads": ("apps.billing.selectors.invoices_issued_between",),
}


@dataclass(frozen=True)
class TrendPackRow:
    """One FISCAL PERIOD, with p059's eight drawn columns.

    ⚠ **EVERY NULLABLE FIELD HERE IS NULL FOR A NAMED REASON** and the reason
    travels in the read's `problems`, never as an em-dash the reader has to
    interpret. `target` is null on every tenant that exists (`BR-REP-034`);
    `dso` is null until twelve months of books exist (`BR-REP-011`); `rate` is
    null in a period that billed nothing; `accounts` and `rebills` are null only
    when their seam cannot be reached.

    ⚠ **`period_start` AND `period_end` ARE NOT DRAWN COLUMNS.** They travel so
    the screen can render the period's dates regionally and so a drill-through
    has a window to carry. B14 rule 31 is untouched — no database id is here.
    """

    period: str
    period_no: int
    fy_label: str | None
    period_start: date
    period_end: date
    revenue: Decimal
    target: Decimal | None
    target_absence: str | None
    collected: Decimal | None
    collected_absence: str | None
    rate: Decimal | None
    rate_absence: str | None
    dso: Decimal | None
    dso_absence: str | None
    accounts: int | None
    accounts_absence: str | None
    rebills: int | None
    rebills_absence: str | None


def _tenant_id() -> Any:
    return current_tenant_id()


# ── the spine: the fiscal calendar, walked backwards ────────────────────────


def _as_day(value: Any) -> date | None:
    """A period card's `start`/`end` as a `date`. Tenancy publishes ISO strings."""
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        return date.fromisoformat(value[:10])
    return None


def periods_back_from(anchor: date, *, periods: int) -> tuple[dict[str, Any], ...]:
    """`periods` fiscal periods ending with the one containing `anchor`, OLDEST FIRST.

    ⚠ **IT WALKS BY ASKING FOR THE DAY BEFORE EACH START, WHICH IS THE ONLY
    PORTABLE WAY.** `BR-TEN-022` makes the period card a COMPUTATION over the
    fiscal-year fields — there is no `fiscal_periods` table to select from and
    deliberately none. Stepping back a fixed number of months here instead would
    be a second implementation of tenancy's `close_cadence`, `fy_start_day` and
    month-length clamp, and it would disagree with the Settings screen on
    February.

    ⚠ **THE LOOP HAS A FLOOR THAT IS NOT `periods`.** A tenancy card that failed
    to step backwards — for any reason, now or later — would spin, so the walk
    stops the moment a step does not produce an EARLIER period than the one
    before it. A short answer is honest; a hung web worker is not.

    Empty when this tenant keeps no fiscal calendar. See `GAP_NO_FISCAL_CALENDAR`.
    """
    wanted = max(1, min(int(periods or DEFAULT_PERIODS), MAX_PERIODS))
    card = tenancy_seam.current_period(reference_date=anchor)
    if not card:
        return ()
    walked: list[dict[str, Any]] = []
    while card and len(walked) < wanted:
        start = _as_day(card.get("start"))
        end = _as_day(card.get("end"))
        if start is None or end is None:
            break
        walked.append({**card, "start": start, "end": end})
        card = tenancy_seam.current_period(reference_date=start - timedelta(days=1))
        if card and _as_day(card.get("start")) is not None:
            # The floor: a step that did not go BACKWARDS ends the walk.
            if _as_day(card.get("start")) >= start:
                break
    return tuple(reversed(walked))


# ── the four aggregates ─────────────────────────────────────────────────────


def _ar_account_id() -> str | None:
    return reporting._designated_account_id(chart.AR)  # noqa: SLF001 — same module


def billed_between(*, start: date, end: date, ar_account_id: str | None) -> Decimal:
    """What this utility BILLED in a window — AR debits from bill sources.

    ⚠ **IT IS `reporting.revenue_and_ar`'s OWN `billed`, STRUCK OVER ONE PERIOD.**
    The predicate is that module's two constants — the designated AR account and
    `BILL_SOURCE_TYPES` — read rather than re-typed, so a source type added to
    billing cannot silently fall out of this column while staying in the S36
    strip (hard-won law 5).

    ⚠ **IT SUMS IN SQL.** `revenue_and_ar` walks its rows in Python because it
    is also splitting cash by source in the same pass; this needs one number
    twelve times, and forty thousand bills a period walked in Python twelve
    times over is the whole of this report's cost.

    Zero for a period that billed nothing, which is a real answer and the one
    case where a zero is honest here.
    """
    if ar_account_id is None:
        return ZERO
    from django.db.models import Sum

    rows = reporting._posted_lines(start=start, end=end).filter(  # noqa: SLF001
        ledger_account_id=ar_account_id,
        side=models.SIDE_DEBIT,
        journal_entry__source_type__in=reporting.BILL_SOURCE_TYPES,
    )
    total = rows.aggregate(total=Sum("amount"))["total"]
    return total if total is not None else ZERO


def _earliest_entry_date() -> date | None:
    """The first day this tenant's books hold anything, or None for empty books.

    It is what decides whether `BR-REP-011`'s twelve-month denominator is a real
    twelve months or three months wearing a twelve-month label.
    """
    from django.db.models import Min

    return (
        models.JournalEntry.objects.filter(
            tenant_id=_tenant_id(), status=models.JE_POSTED
        ).aggregate(first=Min("entry_date"))["first"]
    )


def _rate(collected: Decimal | None, revenue: Decimal) -> tuple[Decimal | None, str | None]:
    """`BR-REP-009` as a percentage, or NULL with the reason it is not one."""
    if collected is None:
        return None, GAP_COLLECTED_READ_UNAVAILABLE["code"]
    if revenue == ZERO:
        return None, GAP_RATE_HAS_NO_DENOMINATOR["code"]
    return (collected / revenue * Decimal(100)).quantize(PERCENT_PLACES), None


def _dso(
    *, period_end: date, ar_account_id: str | None, earliest: date | None
) -> tuple[Decimal | None, str | None]:
    """`BR-REP-011` — (AR ÷ billed last 12 months) × 365, or NULL with its reason.

    ⚠ **THE HISTORY TEST COMES FIRST AND IS NOT `billed > 0`.** A utility that
    billed nothing last August has twelve months of books and a legitimate
    denominator; a utility three months old has neither. The question is whether
    the BOOKS reach back twelve months, and `_earliest_entry_date` is what
    answers it.
    """
    window_start = period_end - timedelta(days=DSO_WINDOW_DAYS - 1)
    if earliest is None or earliest > window_start:
        return None, GAP_DSO_NEEDS_TWELVE_MONTHS["code"]
    billed = billed_between(start=window_start, end=period_end, ar_account_id=ar_account_id)
    if billed == ZERO:
        return None, GAP_DSO_NEEDS_TWELVE_MONTHS["code"]
    receivable = reporting.ar_control(as_of=period_end)
    return (receivable / billed * Decimal(DSO_WINDOW_DAYS)).quantize(PERCENT_PLACES), None


def _target_for(card: dict[str, Any], typed: Any) -> tuple[Decimal | None, str | None]:
    """`BR-REP-034`'s typed target for ONE period, or NULL with its reason.

    Two different absences and they are NOT the same sentence: nothing typed
    (every tenant today), and a typed MONTHLY target over a period that is not a
    month (`GAP_TARGET_CADENCE_UNRULED`). Collapsing them would tell a quarterly
    utility that had typed a target that they had not.
    """
    if typed is None:
        return None, GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED["code"]
    if _months_in(card) != MONTHLY_PERIOD_MONTHS:
        return None, GAP_TARGET_CADENCE_UNRULED["code"]
    return Decimal(typed), None


def _months_in(card: dict[str, Any]) -> int:
    """How many calendar months this period spans — 1 monthly, 3 quarterly.

    Derived from the card's own two dates rather than from `close_cadence`, so
    it stays right if tenancy ever grows a third cadence.
    """
    start, end = card["start"], card["end"]
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


# ── the read ────────────────────────────────────────────────────────────────


def trend_pack(
    *,
    as_of: date | None = None,
    periods: int = DEFAULT_PERIODS,
) -> dict[str, Any]:
    """R43 — one row per fiscal period, OLDEST FIRST, exactly as p059 draws it.

    ⚠ **`as_of` IS AN ARGUMENT AND NEVER A CLOCK** (`BR-TEN-043`). The caller
    supplies the tenant's own today; nothing here reads a machine clock, so the
    report a clerk runs at 23:58 and the one a scheduled job runs at 00:02 can
    be explained to each other.

    ⚠ **THERE IS NO `page` AND NO `per`.** The row count is the `periods`
    control, not the tenant, so there is nothing to page — and an absent `page`
    key on the wire says *this is all of it* without claiming *this is page
    one*. `NFR-3` is untouched.
    """
    # ⚠ **THE TENANT'S TODAY IS READ ONCE, HERE, AND ONLY WHEN THE CALLER NAMED
    # NO DATE** (`BR-TEN-043`). Everything below takes the date as an argument,
    # so the report a clerk runs at 23:58 and the one a scheduled job runs at
    # 00:02 can be explained to each other.
    anchor = as_of or tenancy_seam.tenant_today()
    if anchor is None:
        # Tenancy unreachable AND no date given: there is no honest anchor, so
        # the calendar is reported absent rather than pinned to this process's
        # clock, which would be some other timezone's yesterday.
        return _no_calendar()

    cards = periods_back_from(anchor, periods=periods)
    problems: list[dict[str, Any]] = []
    if not cards:
        return _no_calendar()

    ar_account_id = _ar_account_id()
    earliest = _earliest_entry_date()
    typed_target = tenancy_seam.monthly_revenue_target()

    seen_absences: set[str] = set()
    rows: list[TrendPackRow] = []
    for card in cards:
        rows.append(
            _shape(
                card,
                ar_account_id=ar_account_id,
                earliest=earliest,
                typed_target=typed_target,
                seen=seen_absences,
            )
        )

    for gap in (
        GAP_TARGET_IS_TYPED_AND_NONE_IS_TYPED,
        GAP_TARGET_CADENCE_UNRULED,
        GAP_DSO_NEEDS_TWELVE_MONTHS,
        GAP_RATE_HAS_NO_DENOMINATOR,
        GAP_COLLECTED_READ_UNAVAILABLE,
        GAP_ACCOUNT_COUNT_UNAVAILABLE,
        GAP_REBILL_COUNT_UNAVAILABLE,
    ):
        if gap["code"] in seen_absences:
            problems.append(dict(gap))

    return {
        "basis": BASIS_POSTING,
        # See `REBILLS_BASIS_ISSUE` — the one column dated by the ACT rather
        # than by the book, stated rather than left to be inferred.
        "rebills_basis": REBILLS_BASIS_ISSUE,
        "window": {"start": cards[0]["start"], "end": cards[-1]["end"]},
        "currency": tenancy_seam.tenant_currency(),
        "grain": "one accounting period",
        "rows": tuple(rows),
        # ⚠ **EMPTY ON PURPOSE — p059 DRAWS NO TOTAL ROW.** See the module
        # docstring for the three separate ways a footer here would be wrong.
        "totals": {},
        "tiles": _tiles(rows, typed_target=typed_target),
        "dso_target_days": tenancy_seam.dso_target_days(),
        "problems": tuple(problems),
    }


def _shape(
    card: dict[str, Any],
    *,
    ar_account_id: str | None,
    earliest: date | None,
    typed_target: Any,
    seen: set[str],
) -> TrendPackRow:
    """One period's row. Four aggregates and the two ratios derived from them."""
    start, end = card["start"], card["end"]
    revenue = billed_between(start=start, end=end, ar_account_id=ar_account_id)

    collected = payments_seam.applied_to_bills_issued_between(start=start, end=end)
    collected_absence = None if collected is not None else GAP_COLLECTED_READ_UNAVAILABLE["code"]

    rate, rate_absence = _rate(collected, revenue)
    dso, dso_absence = _dso(period_end=end, ar_account_id=ar_account_id, earliest=earliest)
    target, target_absence = _target_for(card, typed_target)

    accounts = dimension_seam.accounts_on_the_books(as_of=end)
    accounts_absence = None if accounts is not None else GAP_ACCOUNT_COUNT_UNAVAILABLE["code"]

    rebills = billing_seam.rebills_issued_between(start=start, end=end)
    rebills_absence = None if rebills is not None else GAP_REBILL_COUNT_UNAVAILABLE["code"]

    for code in (
        target_absence,
        collected_absence,
        rate_absence,
        dso_absence,
        accounts_absence,
        rebills_absence,
    ):
        if code:
            seen.add(code)

    return TrendPackRow(
        # B14 rule 35 — a fiscal ordinal, language-free. The drawn `· Jul` is
        # the screen's to compose from `period_start`.
        period=f"P{int(card.get('period') or 0)}",
        period_no=int(card.get("period") or 0),
        fy_label=card.get("fy_label"),
        period_start=start,
        period_end=end,
        revenue=revenue,
        target=target,
        target_absence=target_absence,
        collected=collected,
        collected_absence=collected_absence,
        rate=rate,
        rate_absence=rate_absence,
        dso=dso,
        dso_absence=dso_absence,
        accounts=accounts,
        accounts_absence=accounts_absence,
        rebills=rebills,
        rebills_absence=rebills_absence,
    )


def _no_calendar() -> dict[str, Any]:
    """The whole answer for a tenant that keeps no fiscal calendar.

    ⚠ **NO ROWS AND NO SUBSTITUTE.** Twelve calendar months over a utility that
    closes its books on some other calendar would put a bill run in the wrong
    row and read as real. `GAP_NO_FISCAL_CALENDAR` says what to do about it in
    one sentence a clerk can act on.
    """
    return {
        "basis": BASIS_POSTING,
        "rebills_basis": REBILLS_BASIS_ISSUE,
        "window": {"start": None, "end": None},
        "currency": tenancy_seam.tenant_currency(),
        "grain": "one accounting period",
        "rows": (),
        "totals": {},
        "tiles": _empty_tiles(),
        "dso_target_days": tenancy_seam.dso_target_days(),
        "problems": (dict(GAP_NO_FISCAL_CALENDAR),),
    }


def _empty_tiles() -> dict[str, Any]:
    return {
        "revenue_vs_target": None,
        "revenue_vs_target_absence": GAP_NO_FISCAL_CALENDAR["code"],
        "revenue_latest": None,
        "target_latest": None,
        "collection_rate": None,
        "collection_rate_absence": GAP_NO_FISCAL_CALENDAR["code"],
        "dso": None,
        "dso_absence": GAP_NO_FISCAL_CALENDAR["code"],
        "accounts_change": None,
        "accounts_change_absence": GAP_NO_FISCAL_CALENDAR["code"],
        "periods": 0,
    }


def _tiles(rows: list[TrendPackRow], *, typed_target: Any) -> dict[str, Any]:
    """p059's four tiles — and each is read off the ROWS, never re-queried.

    ⚠ **THEY DESCRIBE THE SAME POPULATION AS THE TABLE BECAUSE THEY ARE THE
    TABLE.** The drawn tiles are *the latest period's* rate and DSO and *the
    window's* growth, so every one of them is arithmetic over rows already in
    hand. Re-querying would be a second derivation of a figure sitting on the
    screen underneath it, and the two would drift the first time a filter moved.

    ⚠ **ACCOUNTS GROWTH IS FIRST-TO-LAST AND NOT A Σ.** p059's tile reads
    `+1.8% · 12 months`, which is `(last − first) ÷ first`: the column is AS-OF,
    so adding it would report the utility twelve times over.
    """
    latest = rows[-1]
    oldest = rows[0]
    revenue_vs_target: Decimal | None = None
    revenue_absence: str | None = latest.target_absence
    if latest.target is not None and latest.target != ZERO:
        revenue_vs_target = (latest.revenue / latest.target * Decimal(100)).quantize(
            PERCENT_PLACES
        )
        revenue_absence = None

    accounts_change: Decimal | None = None
    accounts_absence: str | None = latest.accounts_absence or oldest.accounts_absence
    if (
        oldest.accounts is not None
        and latest.accounts is not None
        and oldest.accounts > 0
    ):
        accounts_change = (
            Decimal(latest.accounts - oldest.accounts) / Decimal(oldest.accounts) * Decimal(100)
        ).quantize(PERCENT_PLACES)
        accounts_absence = None
    elif accounts_absence is None:
        # Known counts, but the oldest period held no accounts: a growth
        # percentage from zero is not infinity, it is undefined.
        accounts_absence = "the_first_period_held_no_accounts_so_growth_has_no_base"

    return {
        "revenue_vs_target": revenue_vs_target,
        "revenue_vs_target_absence": revenue_absence,
        "revenue_latest": latest.revenue,
        "target_latest": latest.target,
        "collection_rate": latest.rate,
        "collection_rate_absence": latest.rate_absence,
        "dso": latest.dso,
        "dso_absence": latest.dso_absence,
        "accounts_change": accounts_change,
        "accounts_change_absence": accounts_absence,
        "periods": len(rows),
    }


def trend_pack_stream(
    *,
    as_of: date | None = None,
    periods: int = DEFAULT_PERIODS,
) -> Iterator[TrendPackRow]:
    """EVERY row of R43, for the export — **no `page`, no `per`.**

    ⚠ **IT IS A GENERATOR OVER A BOUNDED SET AND THAT IS NOT A CONTRADICTION.**
    The export path asks `runner.stream_for` for a generator and would otherwise
    fall through to the DATASET's stream and write the ledger's own lines into a
    file headed *Trend Pack* — which is `DEF-REP-6937` again, on the path nobody
    looks at. Twelve rows through a generator costs nothing; the wrong report in
    a file costs a finance officer's afternoon.
    """
    for row in trend_pack(as_of=as_of, periods=periods)["rows"]:
        yield row


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 3 (R43 trend_pack; DEF-REP-6937 · BR-REP-034 / BR-REP-009 / BR-REP-011 / BR-REP-022 · 05-prototype/09 Reports Build Brief.pdf p059 read as an image per B14 rule 42)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-W3
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `runner.run("trend_pack")` served the journal_lines dataset's own columns (`posted_on`, `account_code`, `debit`, `credit`) before this module existed; `tests/test_rep_p6w3_trend_pack_grain.py` fails on the shipped code with `assert None is not None`.
# exceptions: (0) the fiscal calendar is WALKED, not selected — BR-TEN-022 makes the period card a computation and there is no periods table · (1) TARGET is NULL on every tenant (BR-REP-034's ruled degrade) and NULL again on a QUARTERLY tenant, which is inside that rule's own uncovered clause and is not decided here · (2) DSO is NULL until twelve months of books exist (BR-REP-011), which is the state a new tenant is in and the one proved first · (3) RATE is NULL rather than 0% in a period that billed nothing · (4) there is NO totals row — p059 draws none and three of the eight columns cannot lawfully be summed · (5) no `page` key: the row count is the Periods control, not the tenant · (6) the REBILLS column is dated by ISSUE while the money is dated by POSTING, published as `rebills_basis` rather than hidden · (7) this file writes nothing, posts nothing and declares no address column
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C2 / task T7 — unbilled revenue accrual at close.
#           Screens: S42 (the close checklist item this completes)
#           NOTE: no US-ID is cited ON PURPOSE — G10 reads a Trace-header US-ID
#           as "this file ships that story's TCs", and no story owns C2 yet.
#           The authority is the change request, quoted below.
# Rules:    BR-LED-006 (the close checklist — AMENDED 2026-09-02 by CR-060 C2:
#           it is SIX items now, the sixth being `unbilled_accrual`, which asks
#           whether THIS period's unbilled revenue has been recognised. It is a
#           separate item and not a widening of `accruals_posted`, which asks
#           whether an OLDER accrual's day-1 mirror is overdue — a different
#           question) · BR-LED-791 (NEW 2026-09-02 —
#           how unbilled revenue is measured and priced) · BR-LED-005 (an
#           accrual auto-reverses on day 1 of the next period, linked both
#           ways) · BR-LED-025 (the ledger is never a second rounding site;
#           nothing over 2 dp posts) · BR-LED-001 (source_type + source_id on
#           every line; the other dimensions where they apply) · BR-TEN-038
#           (a closed period is never posted into) · BR-REP-002 (a report never
#           recomputes money) · BR-RAT-003 (round per line, half-up, 2 dp, at
#           finalization only) · CLAUDE.md rule 1 · rule 2 · rule 3 · rule 4 ·
#           rule 5 · rule 6 · rule 7
# Golden:   LE-4 — the accrual/mirror pattern this reuses: a Sep 30 accrual
#           DR 1210 Unbilled AR / CR 4100 takes an Oct 1 mirror, linked both
#           ways, 1210 nets 0.00. This module produces the SAME shape from
#           measured reads instead of from a clerk's typing.
# Tests:    06-backend/tests/test_cr060_t7_unbilled_accrual.py
# Impacts:  apps/ledger/posting.py (the sole writer — `post()` is called from
#           here and nothing in this file touches journal_entries or
#           journal_lines) · apps/ledger/close.py (the date goes through
#           resolve_entry_date; `_accruals_item` reads this module's key) ·
#           apps/ledger/manual_je.py (the day-1 reversal is ITS sweep — this
#           module writes no reversal of its own)
# ───────────────────────────────────────────────────────
"""Unbilled revenue, measured from the reads and posted as an accrual.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides a figure that lands in
the trial balance. AI-authored 2026-09-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). The row is in
`12-governance/09-human-review-ledger.md` with the worked figure a reviewer is
approving (CR-060 task T19); nothing here reaches RATIFIED without that
signature.

════════════════════════════════════════════════════════════════════════════
THE GAP THIS CLOSES, IN THE CHANGE REQUEST'S OWN WORDS
════════════════════════════════════════════════════════════════════════════
CR-060 C2: *"`1210 Unbilled AR` is seeded in every chart and nothing has ever
posted to it. Consumption between the last read and period end is real revenue
absent from the books. It is the first thing any reviewer finds."*

`1210` has a designation (`unbilled_ar`, PO ruling 2026-08-11 closing OQ-110),
it is in the finance-signed chart, and until today the only thing that could
reach it was a human typing a manual journal entry. This module is the automatic
path, and it deliberately produces the **same entry shape** a human would type —
because the day-1 reversal that makes an accrual safe is `apps/ledger/
manual_je.run_accrual_auto_reversals`, and it finds an accrual by its TYPE, not
by who wrote it.

════════════════════════════════════════════════════════════════════════════
THIS FILE WRITES NO JOURNAL ROW. NOT ONE.
════════════════════════════════════════════════════════════════════════════
Every insert on `journal_entries` / `journal_lines` goes through
`apps/ledger/posting.py` (CLAUDE.md rule 5), and `ledger/0004`'s sole-writer
trigger makes that structural rather than a promise. Grep this file: there is no
`objects.create(`, no `.save(` and no `.delete(` on a journal model anywhere.

**AND THERE IS NO SECOND REVERSAL MECHANISM** (hard-won law 5, *one source*).
The mirror is posted by the sweep that already exists — `run_accrual_auto_
reversals`, keyed `journal_entry|<accrual id>|auto_reversed`, one string per
accrual forever. This module does not schedule, compose or key a reversal. It
posts an entry of `type='accrual'` and the existing rule takes it from there.

════════════════════════════════════════════════════════════════════════════
BR-LED-791 — HOW UNBILLED REVENUE IS MEASURED AND PRICED
════════════════════════════════════════════════════════════════════════════
CR-060 C2 asks for *"a new rule for how unbilled revenue is measured and
priced"*. This is that rule, stated once, here, and written into
`04-docs/05-modules/09-ledger/02-business-rules.md` the same commit.

**MEASURED — the reads that exist and no bill has priced.** For every service
the tenant sells, every committed lineage head dated on or before the period end
whose consumption no issued bill has taken. A read counts as unbilled only when
BOTH hold: `meter_reads.lifecycle` is `committed` (BR-MET-053's BILLED lock,
wired at issue since DEF-098), **and** the read falls after the last issued
service period of its own account. Requiring both can only UNDER-count, and
under-stating an entry that reverses itself on day one is the safe direction.

**PRICED — at what that account was last charged for that service.** The
per-unit price comes off the most recent ISSUED invoice's `kind='usage'` line
for the same (account, service): a figure the rating engine produced and froze.
**Nothing is re-rated here** (BR-REP-002; CR-060 §13's third exclusion — one
implementation of a money rule, upstream, read downstream). A pair with no such
line, or one whose unit differs from the read's, is EXCLUDED AND COUNTED —
never priced at zero, because a zero-priced read puts consumption into the
quantity and nothing into the money, and the entry would understate revenue
while looking complete.

**ROUNDED once per journal line, half-up, to 2 dp** (BR-RAT-003's discipline at
this finalization; BR-LED-025 refuses more than 2 dp at posting). The debit to
`1210` is the SUM OF THE ROUNDED CREDITS, so debits equal credits by
construction rather than by luck.

**⚠ WHAT IS NOT MEASURED, AND IT IS `OQ-1323`, OPEN.** C2's *"why"* sentence
also names the consumption between the **last read** and period end — the
unread tail. That is not a read; it is an ESTIMATE of one, and estimating it
needs a rule nobody has signed (straight-line on the last read's daily rate? the
same month last year? the cycle's own estimation ladder, BR-MET-026?). Each
gives a different number on the same meter. **The prime directive forbids a lane
resolving an open question by choosing a value**, so the tail is NOT estimated,
`UNREAD_TAIL_NOT_ESTIMATED` rides on every answer this module produces, and
`OQ-1323` carries the question to the PO. The accrual is therefore a floor: it
is the revenue we can PROVE is unbilled, never more.

**AND IT IS A USAGE ACCRUAL, DELIBERATELY.** Base charges, fees and taxes of an
unbilled period are not accrued: none of them is measured by a read, and pricing
them would mean re-deriving a tariff in the ledger — which is the second
implementation §13 exists to forbid. Stated here rather than discovered from a
figure that looks low.

════════════════════════════════════════════════════════════════════════════
A CLOSED PERIOD IS REFUSED, NOT FORWARDED
════════════════════════════════════════════════════════════════════════════
BR-TEN-038 forwards a late-dated event into the earliest open period, and that
is right for a payment that genuinely arrived late. It is WRONG here, and the
refusal is this lane's judgment, recorded in `12-governance/02-decision-log.md`:
an accrual exists to complete the books for a period **before** it closes.
Forwarded into the next month it would recognise July's revenue in August and
then reverse it in September — two months wrong, in a signed period, to avoid
saying "no". So `accrue_unbilled_revenue` REFUSES a closed period by name and
points at the reopen (System Admin, BR-LED-006). C2's proof that *"a closed
period is byte-identical before and after"* holds trivially and is asserted.

The closedness is decided by `close.resolve_entry_date` — the ONE implementation
of the fiscal calendar — rather than by a second reading of the period tables.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from apps.ledger import (
    billing_seam,
    chart,
    close,
    metering_seam,
    models,
    posting,
    selectors,
    tenancy_seam,
)
from core import errors
from core import tenancy as core_tenancy
from core.permissions import BILLING_CLERK, SYSTEM_ADMIN, require_role

#: BR-LED-001's mandatory pair, on the entry and on every line. One constant so
#: the write, the close checklist's read and the S42 drill-back all agree.
SOURCE_UNBILLED_ACCRUAL = "unbilled_revenue_accrual"

#: The event half of the replay key (CLAUDE.md rule 6). One string per period,
#: forever, so pressing the button twice produces the same books.
EVENT_ACCRUED = "accrued"

#: A stable namespace for the period's `source_id`. `journal_entries.source_id`
#: is a UUID column and an accrual's "document" is a PERIOD, which has no row of
#: its own — so the id is DERIVED from (tenant, period) with uuid5 and is
#: therefore the same every time it is computed. A random uuid here would mint a
#: new posting key on every call and the replay guard would never fire.
ACCRUAL_NAMESPACE = uuid.UUID("6f9f4d8a-1c2b-5e4d-9a3f-7c1e0b5d2a64")

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

#: ⚠ OQ-1323, OPEN. See the module docstring. Carried on EVERY result — the
#: preview, the posting and the refusal — because a figure that silently omits
#: the unread tail reads as the whole answer.
UNREAD_TAIL_NOT_ESTIMATED = {
    "code": "unbilled_accrual_excludes_the_unread_tail",
    "br_ref": "BR-LED-791 · OQ-1323",
    "detail": "this accrual measures consumption that has been READ and not yet billed. "
    "Consumption between the LAST READ and the period end is real and is NOT included: "
    "estimating it needs a signed rule (straight-line on the last read's daily rate, the "
    "same month last year, or the cycle's own estimation ladder under BR-MET-026 — each "
    "gives a different number on the same meter), and the prime directive forbids a lane "
    "choosing one. OQ-1323 carries the question. The figure is therefore a FLOOR: the "
    "unbilled revenue we can prove, never more.",
    "wanted_reads": (),
}

#: ⚠ **THIS USED TO ALIAS `close.ROLE_GATE_IS_A_READING`, WHICH WAS RETIRED ON
#: 2026-09-24 WHEN THE PO RULED THE CLOSE GATE.** Posting an unbilled-revenue
#: accrual is NOT closing a month and was never put to them, so this carry stays
#: flagged and returns to the agenda. `manual_je.py` keeps its own marker for the
#: same reason. EP-LED-05 §8 holds the flag; a signature covers only what was shown.
ROLE_GATE_IS_A_READING = close.ACCRUAL_ROLE_GATE_IS_A_READING


class UnbilledAccrualError(RuntimeError):
    """An accrual the ledger refuses, with the reason a human can act on.

    Distinct from `posting.PostingError` for the reason `manual_je.
    ManualJournalError` gives: a caller can tell *"the ledger refused the ACT"*
    (a closed period, nothing to accrue, no readable price basis) from *"the
    books refused the ENTRY"* (unbalanced, foreign account, a third decimal)
    without matching on prose.
    """


@dataclass(frozen=True)
class AccountAccrual:
    """One (account, service) pair's unbilled consumption and what it prices at.

    This is the *"and the reads it came from"* half of C2's preview: a clerk
    looking at a figure they are about to post can see which accounts it is
    made of and at what price, without exporting anything.
    """

    account_id: str
    service_code: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal
    read_count: int
    estimated_read_count: int


@dataclass(frozen=True)
class ServiceAccrual:
    """One journal line of the accrual — one service's revenue, rounded once."""

    service_code: str
    quantity: Decimal
    unit: str | None
    amount: Decimal
    ledger_account_id: str | None
    account_count: int
    read_count: int
    distinct_unit_prices: int
    problems: tuple[str, ...] = field(default=())


@dataclass(frozen=True)
class UnbilledAccrualPreview:
    """The figure, what it is made of, and everything it deliberately leaves out.

    `total is None` means **unanswerable** — a read this module depends on is
    not published — and is never conflated with a total of 0.00, which means
    *"nothing measured is unbilled"*. Only one of those two may be posted, and
    only one of them may reassure anybody.
    """

    period_start: date
    period_end: date
    currency: str | None
    total: Decimal | None
    services: tuple[ServiceAccrual, ...]
    accounts: tuple[AccountAccrual, ...]
    account_rows_total: int
    unbilled_ar_account_id: str | None
    posting_key: str
    already_posted_entry_id: str | None
    period_is_closed: bool
    excluded: dict[str, int]
    problems: tuple[str, ...]
    unavailable: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class UnbilledAccrualResult:
    """What one `accrue_unbilled_revenue` call did — and whether it did anything.

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
    services: tuple[ServiceAccrual, ...]
    preview: UnbilledAccrualPreview
    unavailable: tuple[dict[str, Any], ...]


#: How many (account, service) rows a preview carries before it stops listing
#: them and reports the count alone. A close over 80,000 accounts must not put
#: 80,000 rows on a screen (CR-060 §6's scale note), and a clerk checking a
#: figure needs a sample plus the total, not the whole ledger.
ACCOUNT_ROWS_SHOWN = 200


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
    """`unbilled_revenue_accrual|<period uuid>|accrued` — composed, never typed."""
    return posting.posting_key(
        source_type=SOURCE_UNBILLED_ACCRUAL,
        source_id=accrual_source_id(period_start=period_start, period_end=period_end),
        event=EVENT_ACCRUED,
    )


def posted_accrual_entry_id(*, period_start: date, period_end: date) -> str | None:
    """The accrual already standing for this period, or None.

    Read by `close._accruals_item` so the checklist and this module can never
    disagree about whether the period has been accrued — the same discipline
    `manual_je.pending_accrual_reversals` and `close._accruals_item` already
    share about overdue mirrors.
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


def preview_unbilled_revenue(
    *, period_start: date, period_end: date
) -> UnbilledAccrualPreview:
    """C2's *"preview before posting — the figure, and the reads it came from"*.

    Writes nothing. The same computation `accrue_unbilled_revenue` posts, so a
    clerk who confirms a figure gets that figure, and a reviewer reading the
    review-ledger row can reproduce it.
    """
    if period_end < period_start:
        raise UnbilledAccrualError(
            f"the accrual period ends before it starts ({period_start} → {period_end}). "
            "A window with no days in it measures nothing."
        )

    currency = tenancy_seam.tenant_currency()
    key = accrual_posting_key(period_start=period_start, period_end=period_end)
    already = posted_accrual_entry_id(period_start=period_start, period_end=period_end)
    _, closed_note = close.resolve_entry_date(period_end)
    unbilled_ar = selectors.gl_account_id_for_designation(chart.UNBILLED_AR)

    services = tenancy_seam.enabled_service_codes()
    problems: list[str] = []
    excluded: dict[str, int] = {}

    reads = metering_seam.unbilled_reads(as_of=period_end, service_codes=services)
    problems.extend(reads.problems)
    for code, count in reads.excluded.items():
        excluded[code] = excluded.get(code, 0) + count

    if reads.reads is None:
        # Metering publishes nothing this seam can read. UNANSWERABLE — and a
        # zero would read as "nothing is unbilled", which is a claim.
        return UnbilledAccrualPreview(
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            total=None,
            services=(),
            accounts=(),
            account_rows_total=0,
            unbilled_ar_account_id=unbilled_ar,
            posting_key=key,
            already_posted_entry_id=already,
            period_is_closed=closed_note is not None,
            excluded=excluded,
            problems=tuple(problems),
            unavailable=(UNREAD_TAIL_NOT_ESTIMATED, ROLE_GATE_IS_A_READING),
        )

    account_ids = tuple({row.account_id for row in reads.reads})
    basis = billing_seam.last_priced_usage(
        account_ids=account_ids, service_codes=services
    )
    problems.extend(basis.problems)
    if basis.prices is None:
        return UnbilledAccrualPreview(
            period_start=period_start,
            period_end=period_end,
            currency=currency,
            total=None,
            services=(),
            accounts=(),
            account_rows_total=0,
            unbilled_ar_account_id=unbilled_ar,
            posting_key=key,
            already_posted_entry_id=already,
            period_is_closed=closed_note is not None,
            excluded=excluded,
            problems=tuple(problems),
            unavailable=(UNREAD_TAIL_NOT_ESTIMATED, ROLE_GATE_IS_A_READING),
        )

    # ── the belt-and-braces half of BR-LED-791 ──────────────────────────────
    # A read on or before the account's last issued SERVICE PERIOD has been
    # billed, whatever its lifecycle column says. See the module docstring.
    per_pair: dict[tuple[str, str], dict[str, Any]] = {}
    for read in reads.reads:
        last_billed = basis.last_billed_period_end.get(read.account_id)
        if last_billed is not None and read.read_on <= last_billed:
            excluded["read_is_inside_a_billed_service_period"] = (
                excluded.get("read_is_inside_a_billed_service_period", 0) + 1
            )
            continue
        pair = (read.account_id, read.service_code)
        priced = basis.prices.get(pair)
        if priced is None:
            excluded[billing_seam.NO_PRIOR_PRICED_USAGE_LINE] = (
                excluded.get(billing_seam.NO_PRIOR_PRICED_USAGE_LINE, 0) + 1
            )
            continue
        if priced.unit and priced.unit != read.unit:
            # Rule 3 and BR-LED-033's discipline: gallons are not kgal and a
            # silent factor is how a figure becomes 1,000× wrong.
            excluded[billing_seam.PRICED_UNIT_MISMATCH] = (
                excluded.get(billing_seam.PRICED_UNIT_MISMATCH, 0) + 1
            )
            continue
        bucket = per_pair.setdefault(
            pair,
            {
                "quantity": ZERO,
                "unit": read.unit,
                "unit_price": priced.unit_price,
                "reads": 0,
                "estimated": 0,
            },
        )
        bucket["quantity"] += read.consumption
        bucket["reads"] += 1
        if read.estimated:
            bucket["estimated"] += 1

    accounts: list[AccountAccrual] = []
    by_service: dict[str, dict[str, Any]] = {}
    for (account_id, service_code), bucket in sorted(per_pair.items()):
        amount = bucket["quantity"] * bucket["unit_price"]
        accounts.append(
            AccountAccrual(
                account_id=account_id,
                service_code=service_code,
                quantity=bucket["quantity"],
                unit=bucket["unit"],
                unit_price=bucket["unit_price"],
                # Displayed at 2 dp (CLAUDE.md rule 2) — the SUM is what gets
                # rounded for posting, never these, so the rows can be added up
                # by hand and land within a cent of the line.
                amount=_quantize(amount),
                read_count=bucket["reads"],
                estimated_read_count=bucket["estimated"],
            )
        )
        service = by_service.setdefault(
            service_code,
            {
                "quantity": ZERO,
                "amount": ZERO,
                "units": set(),
                "prices": set(),
                "accounts": 0,
                "reads": 0,
            },
        )
        service["quantity"] += bucket["quantity"]
        service["amount"] += amount
        service["units"].add(bucket["unit"])
        service["prices"].add(bucket["unit_price"])
        service["accounts"] += 1
        service["reads"] += bucket["reads"]

    lines: list[ServiceAccrual] = []
    total = ZERO
    for service_code in sorted(by_service):
        service = by_service[service_code]
        amount = _quantize(service["amount"])
        if amount <= ZERO:
            # A service whose measured revenue rounds to nothing gets no line.
            # A 0.00 credit is noise in a book somebody has to read.
            continue
        account_id = selectors.revenue_account_id_for_service(service_code)
        service_problems: list[str] = []
        if account_id is None:
            # Nothing to credit. Named and excluded — never folded into another
            # service's revenue, and never posted to a hardcoded 4100.
            service_problems.append("service_has_no_revenue_account")
        units = service["units"]
        lines.append(
            ServiceAccrual(
                service_code=service_code,
                quantity=service["quantity"],
                unit=next(iter(units)) if len(units) == 1 else None,
                amount=amount,
                ledger_account_id=account_id,
                account_count=service["accounts"],
                read_count=service["reads"],
                distinct_unit_prices=len(service["prices"]),
                problems=tuple(service_problems),
            )
        )
        if account_id is not None:
            total += amount

    postable = tuple(line for line in lines if line.ledger_account_id is not None)
    unpostable = len(lines) - len(postable)
    if unpostable:
        excluded["service_has_no_revenue_account"] = unpostable

    return UnbilledAccrualPreview(
        period_start=period_start,
        period_end=period_end,
        currency=currency,
        total=total,
        services=tuple(lines),
        accounts=tuple(accounts[:ACCOUNT_ROWS_SHOWN]),
        account_rows_total=len(accounts),
        unbilled_ar_account_id=unbilled_ar,
        posting_key=key,
        already_posted_entry_id=already,
        period_is_closed=closed_note is not None,
        excluded=excluded,
        problems=tuple(problems),
        unavailable=(UNREAD_TAIL_NOT_ESTIMATED, ROLE_GATE_IS_A_READING),
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-006")
def accrue_unbilled_revenue(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    posted_at: datetime,
) -> UnbilledAccrualResult:
    """Post the period's unbilled revenue: DR 1210 Unbilled AR / CR the services.

    ONE entry, of `type='accrual'`, dated the period end, keyed once per period
    forever. `apps/ledger/manual_je.run_accrual_auto_reversals` posts its day-1
    mirror on the next sweep — **this module writes no reversal**, because there
    is exactly one auto-reversal mechanism in this product and adding a second
    is how two of them come to disagree (hard-won law 5).

    `posted_at` is an INPUT (BR-TEN-043 / gate G6): a double-submitted close must
    stamp one moment, not two, and nothing in a money path reads a clock.
    """
    if not isinstance(posted_at, datetime):
        raise UnbilledAccrualError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043 — nothing in a "
            "money path reads a clock, gate G6)."
        )

    preview = preview_unbilled_revenue(period_start=period_start, period_end=period_end)

    if preview.already_posted_entry_id is not None:
        # The replay. A RESULT and not an exception, exactly as
        # `posting.PostingResult.created=False` is: a resumed close pressing the
        # button twice is the correct outcome.
        return UnbilledAccrualResult(
            entry_id=preview.already_posted_entry_id,
            posting_key=preview.posting_key,
            created=False,
            entry_date=period_end,
            total=preview.total or ZERO,
            line_count=0,
            services=preview.services,
            preview=preview,
            unavailable=preview.unavailable,
        )

    if preview.period_is_closed:
        # See the module docstring. Refused, not forwarded — BR-TEN-038's
        # forward is right for an event that genuinely arrived late and wrong
        # for an entry whose whole purpose is to complete the period it names.
        raise UnbilledAccrualError(
            f"the fiscal period containing {period_end.isoformat()} is CLOSED, so its unbilled "
            "revenue cannot be accrued into it (BR-LED-006). BR-TEN-038 would forward the entry "
            "to the earliest open period, which would recognise this period's revenue in a later "
            "month and then reverse it in the month after that — two months wrong in a signed "
            "book. Reopen the period (System Admin) if the accrual belongs in it. Nothing was "
            "posted and the closed period's trial balance is unchanged."
        )

    if preview.total is None:
        raise UnbilledAccrualError(
            "the unbilled figure is UNANSWERABLE on this deployment, so nothing is posted: "
            f"{', '.join(preview.problems) or 'a read this accrual depends on is not published'}. "
            "A zero accrual would say *nothing is unbilled*, which is a claim about money, over "
            "books that may hold a month of it."
        )

    postable = tuple(line for line in preview.services if line.ledger_account_id is not None)
    if not postable or preview.total <= ZERO:
        raise UnbilledAccrualError(
            f"nothing measured is unbilled for {period_start.isoformat()} → "
            f"{period_end.isoformat()}: every committed read in the window is inside a billed "
            "service period, or has no price basis, or prices to less than a cent. Nothing is "
            "posted — an accrual of 0.00 is a journal entry that says nothing and has to be "
            "read anyway. The named exclusions are on the preview."
        )

    if preview.unbilled_ar_account_id is None:
        raise UnbilledAccrualError(
            "this tenant's chart has no account carrying the `unbilled_ar` designation, so the "
            "accrual has no receivable to debit (OQ-110's eleven designations, PO 2026-08-11; "
            "`1210 Unbilled AR (accruals)` is the seeded account). Nothing is posted, and no "
            "number is hardcoded — the code reads the DESIGNATION precisely so a tenant may "
            "renumber their chart (CR-060 §13's second exclusion)."
        )

    source_id = accrual_source_id(period_start=period_start, period_end=period_end)
    lines: list[posting.PostingLine] = [
        posting.PostingLine(
            ledger_account_id=preview.unbilled_ar_account_id,
            side=models.SIDE_DEBIT,
            amount=preview.total,
            source_type=SOURCE_UNBILLED_ACCRUAL,
            source_id=source_id,
        )
    ]
    for line in postable:
        lines.append(
            posting.PostingLine(
                ledger_account_id=line.ledger_account_id,
                side=models.SIDE_CREDIT,
                amount=line.amount,
                source_type=SOURCE_UNBILLED_ACCRUAL,
                source_id=source_id,
                # The SERVICE dimension and no other. BR-LED-001 wants the
                # dimensions *where they apply*: this line is one service's
                # revenue across many customers, so it names no account — and
                # therefore, correctly, no premises and no unit either
                # (`posting._stamped` leaves a line with no account alone).
                service_id=tenancy_seam.service_id_for_code(line.service_code),
            )
        )

    result = posting.post(
        posting.PostingRequest(
            posting_key=preview.posting_key,
            entry_date=period_end,
            posted_at=posted_at,
            currency=preview.currency or "USD",
            lines=tuple(lines),
            source_type=SOURCE_UNBILLED_ACCRUAL,
            source_id=source_id,
            memo=(
                f"Unbilled revenue accrual {period_start.isoformat()} → "
                f"{period_end.isoformat()} (BR-LED-791). Reverses on day 1 of the next "
                "period (BR-LED-005)."
            ),
            entry_type=models.JE_ACCRUAL,
            audit_context={
                "action": "unbilled_revenue_accrual",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total": str(preview.total),
                "service_lines": len(postable),
                "account_rows": preview.account_rows_total,
                "excluded": dict(preview.excluded),
            },
        ),
        actor=actor,
    )
    return UnbilledAccrualResult(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        entry_date=period_end,
        total=result.debits,
        line_count=result.line_count,
        services=postable,
        preview=preview,
        unavailable=preview.unavailable,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C2 + task T7 (12-governance/11-change-requests.md §7 · §12 ·
#         §13) · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-005 /
#         006 / 025 / 001 · 08-worked-examples.md LE-4 · CLAUDE.md hard rules
#         1-7 and hard-won laws 1, 2, 5, 7, 14
# generated: 2026-09-02 by the CR-060 T7 lane
# checklist: A✔ B✔ C✔ D✔(apps/ledger/accruals_api.py) E=deferred(C2 specifies
#         two endpoints and NO screen, and no task row in §12 owns one — the
#         S42 surface for it is REPORTED rather than invented) F✔ G✔
#         H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row written under
#         CR-060 T19 with the worked figure)
# gates: PROVED RED BEFORE GREEN, three guards, each through `monkeypatch` so
#         NO LIVE FILE WAS MUTATED (DEF-3101). MEASURED, not reasoned:
#         (1) the closed-period refusal removed → the entry posted **dated
#         2026-08-31, INSIDE the closed August**, not forwarded into September
#         as the proof first predicted. `posting.post()` does not resolve or
#         refuse a closed-period date at all — the CALLER does. That is a
#         defect in its own right and is FILED as `DEF-3202`, with CR-060 §6's
#         sentence *"resolves the entry date to an OPEN fiscal period"* named
#         as the claim it contradicts. ✅ **DEF-3202 IS FIXED (2026-09-02) and
#         this module's own refusal is NOT redundant.** `posting.post()` now
#         REFUSES a closed-period `entry_date` — so the sabotage above would
#         raise instead of posting — but it refuses; it does not forward. This
#         module refuses one step earlier and for a different reason: the
#         accrual must not be forwarded EITHER, and it says so to the closer
#         naming the period and the reopen, where the writer can only say "not
#         this date". Keep both. (2) the period-scoped posting key replaced with
#         a per-press one → `1210` went **68.04 → 136.08**, the utility owed
#         twice for the same water. (3) the unit check removed → 10,000 gallons
#         priced at the kgal rate produced **$31,000.00** of water revenue
#         instead of **$31.00**. See tests/test_cr060_t7_unbilled_accrual.py.
#         ⚠ **AND THE SUITE ITSELF WAS 16/16 ON SQLITE AND 14/16 ON REAL
#         POSTGRESQL** the first time it met one (hard-won law 14): two FIXTURES
#         reached their state by editing a committed read and by deleting an
#         issued invoice, which triggers refuse on PostgreSQL and nothing
#         refuses on SQLite. Both are built rather than edited now — a fixture
#         that must break a hard rule to reach a state is describing a state the
#         product cannot be in.
# exceptions: (1) **THE UNREAD TAIL IS `OQ-1323`, OPEN, AND IS NOT ESTIMATED.**
#         Every result carries `unbilled_accrual_excludes_the_unread_tail`; the
#         figure is a floor · (2) BASE CHARGES, FEES AND TAXES ARE NOT ACCRUED —
#         none is measured by a read and pricing them would re-derive a tariff
#         in the ledger, which CR-060 §13 forbids · (3) neither metering nor
#         billing publishes the preferred read; both seams fall back to a
#         published queryset and both gaps are PARKED in seam_known_gaps.txt ·
#         (4) a CLOSED period is REFUSED rather than forwarded — this lane's
#         judgment, in the decision log with its reasoning · (5) the role gate
#         is EP-LED-05 §8's flagged READING of OQ-175, carried on every result
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

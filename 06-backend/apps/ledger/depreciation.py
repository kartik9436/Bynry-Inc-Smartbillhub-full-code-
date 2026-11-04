# ── Trace ──────────────────────────────────────────────
# Story:    CR-060 C20 / task T7f — post depreciation from the asset's own
#           figures. Screens: S49 (the registry the figures come from), S56
#           (the trial balance they now reach)
#           NOTE: no US-ID is cited ON PURPOSE — G10 reads a Trace-header US-ID
#           as "this file ships that story's TCs", and no story owns C20 yet.
# Rules:    BR-LED-793 (NEW 2026-09-02 — how depreciation is posted: the
#           PERIOD'S MOVEMENT, from the asset module's own figures, DR the
#           depreciation expense / CR accumulated depreciation, and it does NOT
#           reverse) · BR-AST-047 (straight-line book value — the ONE
#           computation, in assets, borrowed and never re-implemented) ·
#           BR-LED-025 (nothing over 2 dp posts) · BR-LED-001 (source_type +
#           source_id on every line) · BR-TEN-038 (a closed period is never
#           posted into) · BR-TEN-043 (posted_at is an INPUT) · BR-REP-002 (a
#           report never recomputes money) · CLAUDE.md rule 1 · rule 2 · rule 4 ·
#           rule 5 · rule 6 · rule 7
# Tests:    06-backend/tests/test_cr060_t7f_depreciation.py
# Impacts:  apps/ledger/posting.py (the sole writer) · apps/ledger/assets_seam.py
#           (the figures) · apps/ledger/close.py (the date goes through
#           resolve_entry_date) · apps/ledger/services.ensure_period_matching_
#           accounts (the two accounts)
# ───────────────────────────────────────────────────────
"""Depreciation, taken from the asset register and put into the books.

HUMAN-OWNED · HUMAN-REVIEW-PENDING — this module decides a figure that lands in
the trial balance. AI-authored 2026-09-02 under the PO ruling of 2026-08-09
(*"AI will do it; we will review it later as human"*). The row is in
`12-governance/09-human-review-ledger.md` with the worked figure a reviewer is
approving (CR-060 task T19); nothing here reaches RATIFIED without that
signature.

════════════════════════════════════════════════════════════════════════════
THE GAP THIS CLOSES, IN THE CHANGE REQUEST'S OWN WORDS
════════════════════════════════════════════════════════════════════════════
CR-060 §4: *"Depreciation is computed and shown on screen and posts nowhere."*
C20: *"The assets module already computes accumulated depreciation and book
value from the purchase cost, method and expected life, and shows them on
screen. Nothing posts them. Once C1 puts cost in the books, this is the last
piece of a real operating statement."*

And its order note, honoured: *"After C1 — depreciation in books that carry no
cost is an odd half-picture."* C1 landed 2026-09-02, hours before this.

════════════════════════════════════════════════════════════════════════════
BR-LED-793 — WHAT IS POSTED, AND WHAT IS NOT COMPUTED HERE
════════════════════════════════════════════════════════════════════════════
Stated once, here, and written into
`04-docs/05-modules/09-ledger/02-business-rules.md` the same commit.

**THE AMOUNT IS THE PERIOD'S MOVEMENT, AND NOTHING IN THIS PRODUCT'S LEDGER
COMPUTES DEPRECIATION.** `apps/ledger/assets_seam.py` subtracts two of the
assets module's own answers —
`accumulated(period_end) − accumulated(day before period_start)` — both from
`apps.assets.selectors.asset_book_value`, which is BR-AST-047's single
implementation. C20 asks for *"a posting path and a period trigger, not a
calculation"* and that is exactly what this is. A second implementation of
straight-line depreciation in the ledger is what BR-REP-002 and CR-060 §13's
third exclusion forbid, and it is how the S49 panel and the trial balance would
come to disagree about the same meter.

**THE ENTRY.** One entry per period, `type='standard'`:

    DR  <depreciation_expense>        the period's charge
    CR  <accumulated_depreciation>    the same figure

**IT IS NOT AN ACCRUAL AND IT MUST NEVER BE ONE.** `models.JE_ACCRUAL` is the
type `apps/ledger/manual_je.run_accrual_auto_reversals` sweeps, and a
depreciation entry that reversed itself on day 1 would leave the plant at its
purchase cost forever — the exact error CR-060 §5 measures at **$40,000** on a
truck. The two month-end postings this lane built are deliberately different
types for deliberately different reasons, and the test suite asserts the
difference rather than describing it.

**BOTH ACCOUNTS BY DESIGNATION, NEVER BY NUMBER.** `depreciation_expense` and
`accumulated_depreciation` are resolved through `selectors`, and
`services.ensure_period_matching_accounts` places them on `5700 Depreciation
expense` (minted by this change, `signed=False`) and `1730 Accumulated
depreciation — meters` (a `UTILITY_BOOKS_CHART` row the PO ruled in on
2026-09-01/02). A utility with water plant moves the second pointer to `1700` on
the GL mapping page and not one line of this file changes.

**ROUNDED ONCE, HALF-UP, TO 2 dp**, on the single pair of lines (BR-RAT-003's
discipline at this finalization; BR-LED-025 refuses more than 2 dp at posting).
The credit IS the debit, so the entry balances by construction.

**ONE CURRENCY.** The entry takes the tenant's currency, because a depreciation
charge is derived from purchase costs the asset register holds in one place;
there is no per-asset currency in this product to disagree about.

════════════════════════════════════════════════════════════════════════════
WHAT A FIRST RUN DOES NOT DO, AND IT IS THE THING TO KNOW ABOUT THIS FEATURE
════════════════════════════════════════════════════════════════════════════
**A PERIOD POSTS ITS OWN MOVEMENT AND NOTHING ELSE.** A utility whose meters
have been depreciating for two years and who runs this for the first time in
September gets **September's slice**, not two years of catch-up. The months
before it stay unposted, permanently, unless somebody runs those periods.

That is deliberate and it is the safe direction: posting two years of charge
into one month on the first press would misstate that month by everything it
absorbed, in an entry that hard rule 4 gives nobody a way to edit. The
alternative — an opening catch-up entry — is a real thing a utility going live
needs, it is what `3000 Opening balance clearing` and `apps/ledger/
opening_balances.py` exist for, and it is a decision about a tenant's history
rather than about this month. **`OPENING_DEPRECIATION_NOT_POSTED` rides on every
answer this module produces**, so nobody reads a first month's figure as the
whole of the plant's accumulated depreciation.

════════════════════════════════════════════════════════════════════════════
A CLOSED PERIOD IS REFUSED, NOT FORWARDED
════════════════════════════════════════════════════════════════════════════
The same judgment `unbilled_accrual` and `unpaid_cost_accrual` record, and for
the same reason: forwarding July's depreciation into August would charge August
twice and July never. Recorded in `12-governance/02-decision-log.md`. The
closedness is decided by `close.resolve_entry_date` — the ONE implementation of
the fiscal calendar.

════════════════════════════════════════════════════════════════════════════
THIS FILE WRITES NO JOURNAL ROW. NOT ONE.
════════════════════════════════════════════════════════════════════════════
Every insert on `journal_entries` / `journal_lines` goes through
`apps/ledger/posting.py` (CLAUDE.md rule 5), and `ledger/0004`'s sole-writer
trigger makes that structural rather than a promise.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from uuid import UUID

from apps.ledger import (
    assets_seam,
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

#: BR-LED-001's mandatory pair, on the entry and on every line.
SOURCE_DEPRECIATION = "depreciation"

#: The event half of the replay key (CLAUDE.md rule 6). One string per period,
#: forever, so pressing the button twice produces the same books.
EVENT_CHARGED = "charged"

#: A stable namespace for the period's `source_id` — the twin of the two
#: accruals' namespaces and for the same reason: a period has no row of its own,
#: so the id is DERIVED from (tenant, period) with uuid5 and is the same every
#: time it is computed.
DEPRECIATION_NAMESPACE = uuid.UUID("b41e8c72-5d06-5f19-a2b8-936e4f0c7d25")

ZERO = Decimal("0")
TWO_PLACES = Decimal("0.01")

#: Carried on EVERY result. See the module docstring — a first run posts one
#: period's movement, and a reader who took the figure for the plant's whole
#: accumulated depreciation would be wrong by however long the utility has been
#: running.
OPENING_DEPRECIATION_NOT_POSTED = {
    "code": "depreciation_before_the_first_posted_period_is_not_in_the_books",
    "br_ref": "BR-LED-793 · BR-LED-021",
    "detail": "each period posts its OWN depreciation movement and nothing else, so a utility "
    "running this for the first time gets that period's charge — not the years of charge its "
    "plant accumulated before the product started posting any. Those months stay unposted "
    "unless somebody runs them. Bringing a going-live utility's accumulated depreciation onto "
    "the books is an OPENING BALANCE (3000 Opening balance clearing, "
    "apps/ledger/opening_balances.py), which is a decision about that tenant's history and "
    "not about this month. The asset register's own figures are unaffected either way — they "
    "are computed from purchase cost and life and have always been complete.",
    "wanted_reads": (),
}

#: ⚠ **THIS USED TO ALIAS `close.ROLE_GATE_IS_A_READING`, WHICH WAS RETIRED ON
#: 2026-09-24 WHEN THE PO RULED THE CLOSE GATE.** Posting a depreciation entry is
#: NOT closing a month and was never put to them, so this carry stays flagged and
#: returns to the agenda — it now names its own act instead of borrowing the
#: close's sentence. EP-LED-05 §8 holds the flag.
ROLE_GATE_IS_A_READING = close.ACCRUAL_ROLE_GATE_IS_A_READING


class DepreciationError(RuntimeError):
    """A depreciation charge the ledger refuses, with a reason a human can act on.

    Distinct from `posting.PostingError` for `manual_je.ManualJournalError`'s
    reason: a caller can tell *"the ledger refused the ACT"* from *"the books
    refused the ENTRY"* without matching on prose.
    """


@dataclass(frozen=True)
class DepreciationPreview:
    """The charge, the assets behind it, and everything left out.

    `total is None` means **unanswerable** — assets publishes nothing this
    period's figure can be taken from — and is never conflated with 0.00, which
    means *"the plant did not depreciate"*. Only one of those may be posted, and
    in fact neither is.
    """

    period_start: date
    period_end: date
    currency: str | None
    total: Decimal | None
    asset_count: int
    assets_considered: int
    expense_account_id: str | None
    accumulated_account_id: str | None
    posting_key: str
    already_posted_entry_id: str | None
    period_is_closed: bool
    excluded: dict[str, int]
    problems: tuple[str, ...]
    unavailable: tuple[dict[str, Any], ...]


@dataclass(frozen=True)
class DepreciationResult:
    """What one `post_depreciation` call did — and whether it did anything.

    `created=False` with an `entry_id` is the replay no-op, the shape
    `posting.PostingResult` uses: a resumed close pressing the button twice is
    the correct outcome, not an error.
    """

    entry_id: str | None
    posting_key: str
    created: bool
    entry_date: date | None
    total: Decimal
    line_count: int
    asset_count: int
    preview: DepreciationPreview
    unavailable: tuple[dict[str, Any], ...]


def _tenant_id() -> UUID:
    """CLAUDE.md rule 1 — no tenant table is touched without `app.tenant_id`."""
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def depreciation_source_id(*, period_start: date, period_end: date) -> UUID:
    """The period's stable document id. Same inputs ⇒ same uuid, always."""
    tenant_id = _tenant_id()
    return uuid.uuid5(
        DEPRECIATION_NAMESPACE,
        f"{tenant_id}|{period_start.isoformat()}|{period_end.isoformat()}",
    )


def depreciation_posting_key(*, period_start: date, period_end: date) -> str:
    """`depreciation|<period uuid>|charged` — composed, never typed."""
    return posting.posting_key(
        source_type=SOURCE_DEPRECIATION,
        source_id=depreciation_source_id(period_start=period_start, period_end=period_end),
        event=EVENT_CHARGED,
    )


def posted_depreciation_entry_id(*, period_start: date, period_end: date) -> str | None:
    """The depreciation entry already standing for this period, or None."""
    key = depreciation_posting_key(period_start=period_start, period_end=period_end)
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


def preview_depreciation(*, period_start: date, period_end: date) -> DepreciationPreview:
    """The period's charge before it is posted. Writes nothing.

    The same computation `post_depreciation` posts, so the figure a clerk
    confirms is the figure that lands, and a reviewer reading the review-ledger
    row can reproduce it.
    """
    if period_end < period_start:
        raise DepreciationError(
            f"the depreciation period ends before it starts ({period_start} → {period_end}). "
            "A window with no days in it depreciates nothing."
        )

    key = depreciation_posting_key(period_start=period_start, period_end=period_end)
    already = posted_depreciation_entry_id(period_start=period_start, period_end=period_end)
    _, closed_note = close.resolve_entry_date(period_end)
    expense = selectors.gl_account_id_for_designation(chart.DEPRECIATION_EXPENSE)
    accumulated = selectors.gl_account_id_for_designation(chart.ACCUMULATED_DEPRECIATION)

    outcome = assets_seam.depreciation_movement(
        period_start=period_start, period_end=period_end
    )
    if outcome.charges is None:
        return DepreciationPreview(
            period_start=period_start,
            period_end=period_end,
            currency=tenancy_seam.tenant_currency(),
            total=None,
            asset_count=0,
            assets_considered=outcome.considered,
            expense_account_id=expense,
            accumulated_account_id=accumulated,
            posting_key=key,
            already_posted_entry_id=already,
            period_is_closed=closed_note is not None,
            excluded=dict(outcome.excluded),
            problems=tuple(outcome.problems),
            unavailable=(OPENING_DEPRECIATION_NOT_POSTED, ROLE_GATE_IS_A_READING),
        )

    charging = tuple(row for row in outcome.charges if row.charge > ZERO)
    # ONE rounding, on the sum, because the entry has ONE debit line. Rounding
    # each asset and adding would round the same figure as many times as the
    # utility owns meters, which is BR-RAT-003's own reason for rounding at
    # finalization and not before.
    total = _quantize(sum((row.charge for row in charging), ZERO))

    return DepreciationPreview(
        period_start=period_start,
        period_end=period_end,
        currency=tenancy_seam.tenant_currency(),
        total=total,
        asset_count=len(charging),
        assets_considered=outcome.considered,
        expense_account_id=expense,
        accumulated_account_id=accumulated,
        posting_key=key,
        already_posted_entry_id=already,
        period_is_closed=closed_note is not None,
        excluded=dict(outcome.excluded),
        problems=tuple(outcome.problems),
        unavailable=(OPENING_DEPRECIATION_NOT_POSTED, ROLE_GATE_IS_A_READING),
    )


@require_role(SYSTEM_ADMIN, BILLING_CLERK, br_ref="BR-LED-006")
def post_depreciation(
    actor: Any,
    *,
    period_start: date,
    period_end: date,
    posted_at: datetime,
) -> DepreciationResult:
    """Post the period's depreciation: DR the expense / CR accumulated.

    ONE entry, of `type='standard'` — **never `accrual`**, because an accrual
    is swept into a day-1 reversal and depreciation does not come back (see the
    module docstring). Keyed once per period forever.

    `posted_at` is an INPUT (BR-TEN-043 / gate G6): a double-submitted close must
    stamp one moment, not two, and nothing in a money path reads a clock.
    """
    if not isinstance(posted_at, datetime):
        raise DepreciationError(
            "posted_at must be a datetime supplied by the caller (BR-TEN-043 — nothing in a "
            "money path reads a clock, gate G6)."
        )

    # Hard-won law 4 — a tenant provisioned before today has neither pointer,
    # because the seed runs at provisioning and nowhere else. Idempotent: a
    # tenant that has already chosen its accounts keeps them.
    services.ensure_period_matching_accounts(actor)

    preview = preview_depreciation(period_start=period_start, period_end=period_end)

    if preview.already_posted_entry_id is not None:
        return DepreciationResult(
            entry_id=preview.already_posted_entry_id,
            posting_key=preview.posting_key,
            created=False,
            entry_date=period_end,
            total=preview.total or ZERO,
            line_count=0,
            asset_count=preview.asset_count,
            preview=preview,
            unavailable=preview.unavailable,
        )

    if preview.period_is_closed:
        raise DepreciationError(
            f"the fiscal period containing {period_end.isoformat()} is CLOSED, so its "
            "depreciation cannot be charged into it (BR-LED-006). BR-TEN-038 would forward "
            "the entry to the earliest open period, which would charge that month twice and "
            "this one never — and unlike an accrual there is no day-1 mirror to take it back "
            "out. Reopen the period (System Admin) if the charge belongs in it. Nothing was "
            "posted and the closed period's trial balance is unchanged."
        )

    if preview.total is None:
        why = ", ".join(preview.problems) or (
            "the asset register publishes no read this charge can be taken from"
        )
        raise DepreciationError(
            "the depreciation charge is UNANSWERABLE on this deployment, so nothing is "
            f"posted: {why}. A zero charge would say *the plant did not depreciate*, which "
            "is a claim about a balance sheet."
        )

    if preview.total <= ZERO:
        raise DepreciationError(
            f"nothing depreciated between {period_start.isoformat()} and "
            f"{period_end.isoformat()}: every asset in service is fully depreciated, was "
            "bought after the period ended, or has no purchase cost and expected life "
            "recorded. Nothing is posted — a depreciation entry of 0.00 is a journal entry "
            "that says nothing and has to be read anyway. The named exclusions and their "
            "counts are on the preview."
        )

    missing = [
        name
        for name, value in (
            ("depreciation_expense", preview.expense_account_id),
            ("accumulated_depreciation", preview.accumulated_account_id),
        )
        if value is None
    ]
    if missing:
        raise DepreciationError(
            "this tenant's chart has no account carrying "
            f"{' and no account carrying '.join(repr(name) for name in missing)}, so the "
            "depreciation charge has nowhere to post. `5700 Depreciation expense` and `1730 "
            "Accumulated depreciation — meters` are the seeded accounts and a System Admin "
            "designates them on the GL mapping page. Nothing is posted, and no number is "
            "hardcoded — the code reads the DESIGNATION precisely so a tenant may renumber "
            "their chart, and a utility with water plant points the second one at `1700` "
            "instead. Posting to a guessed account would be a guess written into an entry "
            "that can never be edited (hard rule 4)."
        )

    source_id = depreciation_source_id(period_start=period_start, period_end=period_end)
    dimensions = {"source_type": SOURCE_DEPRECIATION, "source_id": source_id}
    result = posting.post(
        posting.PostingRequest(
            posting_key=preview.posting_key,
            entry_date=period_end,
            posted_at=posted_at,
            currency=preview.currency or "USD",
            source_type=SOURCE_DEPRECIATION,
            source_id=source_id,
            memo=(
                f"Depreciation {period_start.isoformat()} → {period_end.isoformat()} "
                f"across {preview.asset_count} asset(s) (BR-LED-793). Straight-line, from "
                "the asset register's own figures; this entry does NOT reverse."
            ),
            # STANDARD, never ACCRUAL. See the module docstring — the type is
            # what `manual_je.run_accrual_auto_reversals` sweeps on, and a
            # depreciation entry that reversed itself would leave the plant at
            # its purchase cost forever.
            entry_type=models.JE_STANDARD,
            lines=(
                posting.PostingLine(
                    ledger_account_id=preview.expense_account_id,
                    side=models.SIDE_DEBIT,
                    amount=preview.total,
                    **dimensions,
                ),
                posting.PostingLine(
                    ledger_account_id=preview.accumulated_account_id,
                    side=models.SIDE_CREDIT,
                    amount=preview.total,
                    **dimensions,
                ),
            ),
            audit_context={
                "action": "depreciation_charged",
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "total": str(preview.total),
                "assets_charged": preview.asset_count,
                "assets_considered": preview.assets_considered,
                "excluded": dict(preview.excluded),
            },
        ),
        actor=actor,
    )
    return DepreciationResult(
        entry_id=result.entry_id,
        posting_key=result.posting_key,
        created=result.created,
        entry_date=period_end,
        total=result.debits,
        line_count=result.line_count,
        asset_count=preview.asset_count,
        preview=preview,
        unavailable=preview.unavailable,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-060 C20 + task T7f (12-governance/11-change-requests.md §7 · §12 ·
#         §13) · 04-docs/05-modules/09-ledger/02-business-rules.md BR-LED-793 ·
#         04-docs/05-modules/03-assets/02-business-rules.md BR-AST-047 ·
#         CLAUDE.md hard rules 1-7 and hard-won laws 1, 2, 4, 5, 7, 14
# generated: 2026-09-02 by the CR-060 T7b/T7d/T7f lane
# checklist: A✔ B✔ C✔ D✔(apps/ledger/accruals_api.py) E=deferred(C20 names NO
#           endpoint and NO screen — *"a posting path and a period trigger"* —
#           and no §12 task row owns one; the two endpoints here are the trigger
#           and the S42 surface is REPORTED rather than invented) F✔ G✔
#           H=deferred(PO 2026-08-09 — 🔒 HUMAN-REVIEW-PENDING, row written
#           under CR-060 T19 with the worked figure)
# gates: PROVED RED BEFORE GREEN — see
#         tests/test_cr060_t7f_depreciation.py, whose module docstring quotes
#         each failure verbatim.
# exceptions: (1) **A FIRST RUN POSTS ONE PERIOD'S MOVEMENT, NEVER A CATCH-UP**,
#         and every result says so — bringing a going-live utility's accumulated
#         depreciation onto the books is an opening balance, not this · (2) a
#         CLOSED period is REFUSED rather than forwarded, this lane's judgment,
#         in the decision log · (3) RETIRED assets are not depreciated and the
#         part-month a mid-period retirement loses is under-stated, counted on
#         every answer (apps/ledger/assets_seam.py) · (4) only straight-line is
#         computed — BR-AST-047's own stated limit, in assets, not widened here ·
#         (5) the role gate is EP-LED-05 §8's flagged READING of OQ-175
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

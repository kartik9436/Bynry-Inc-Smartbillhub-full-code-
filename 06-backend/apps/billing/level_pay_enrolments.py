# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — billing's ONE THIRD of R27 Plans &
#           Discounts. Drawing read as an IMAGE (B14 rule 42): p060–p061.
# Rules:    `BR-REP-040` (ONE report, a k-way merge of three SQL-sorted,
#           SQL-limited streams, each fetching `offset + per` rows) · `NFR-3`
#           (pagination in SQL) · `NFR-5` (no caps) · CLAUDE.md hard rule 1
#           (tenant scoping) · hard rule 2 (money 4dp, percentages 6dp, both
#           DISPLAY 2) · hard rule 4 (this file writes nothing) · B1 (billing
#           publishes ITS OWN table and reads nobody else's).
# ───────────────────────────────────────────────────────
"""**LEVEL PAY**, R27's first programme — one row per ENROLMENT.

⚠ **THIS FILE IS ONE THIRD OF A REPORT AND KNOWS NOTHING ABOUT THE OTHER TWO.**
`BR-REP-040` makes R27 a k-way merge of three streams owned by three modules.
B1 forbids the cross-module query, so each module publishes its own slice,
already SORTED and already LIMITED, and `apps/reports/plans_and_discounts.py`
merges them. Putting the merge here would mean billing reading payments' and
rating's tables.

⚠ **SQL-SORTED AND SQL-LIMITED, AND THE LIMIT IS `offset + per`.** That is
`BR-REP-040`'s ruled exception, published in the rule with its measured cost: a
k-way merge cannot know which stream a page's rows come from without fetching
`offset + per` from each, so the LAST page costs more than the first. `NFR-3`
and `NFR-5` are untouched — there is no Python slice of an unbounded read and no
cap anywhere.

**`remaining` IS NULL ON EVERY ROW AND IS NOT A GAP.** p061 draws an em-dash
there for the level-pay line, and it is right: level pay has no end and no
balance to run down. An account pays the level every month until it comes off
budget. `variance_balance` is a DIFFERENT fact — how far the levelled payments
have drifted from real consumption — and printing it under REMAINING would put a
number a customer could read as *"what I still owe on my plan"* in a column
where two other programmes mean exactly that.
"""

from __future__ import annotations

from typing import Any

from apps.billing import budget
from apps.billing.models import AccountBudgetStatus
from core import tenancy as core_tenancy

#: R27's programme code for this stream. The SCREEN renders it into its own
#: language (B14 rule 35); nothing here composes English.
PROGRAMME_LEVEL_PAY = "level_pay"

#: What `status` must be for an enrolment to be LIVE. p061's `Status` parameter
#: defaults to `Active`, and an account that has come off budget is not enrolled.
LIVE_STATUSES: tuple[str, ...] = (budget.STATUS_ENROLLED,)


def level_pay_enrolments(
    *, as_of: Any = None, limit: int | None = None, status: str | None = None
) -> list[dict[str, Any]]:
    """Level-pay enrolments, SORTED BY `enrolled_on` DESC and LIMITED in SQL.

    `limit=None` is the whole set — for the export. The CALLER decides; this
    function invents no cap (`NFR-5`).

    ⚠ **THE ORDER IS TOTAL.** `id` breaks a tie on `enrolled_on`, because two
    accounts enrolled on one day would otherwise make the k-way merge's choice
    of which row comes first a coin toss — and a coin toss at a page boundary
    repeats one row and drops another.
    """
    rows = AccountBudgetStatus.objects.filter(tenant_id=core_tenancy.current_tenant_id())
    if as_of is not None:
        rows = rows.filter(enrolled_on__lte=as_of)
    if status != "all":
        rows = rows.filter(status__in=LIVE_STATUSES)
    rows = rows.select_related("account").order_by("-enrolled_on", "-id")
    if limit is not None:
        rows = rows[: max(0, int(limit))]
    return [_shape(row) for row in rows]


def _shape(row: AccountBudgetStatus) -> dict[str, Any]:
    """One enrolment in R27's own column vocabulary (p061).

    `terms` is the settle-up month expressed as a CYCLE COUNT, because p061
    draws `12 months` against level pay and the rule that governs the figure is
    the budget's own settle-up. Where no settle-up month is set the term is NULL
    rather than a guessed twelve (`BR-REP-024`).
    """
    return {
        "programme": PROGRAMME_LEVEL_PAY,
        "account": row.account.account_no,
        "account_id": str(row.account_id),
        "since": row.enrolled_on,
        "terms_months": row.settle_up_month,
        "terms_percent": None,
        "instalment": row.level_override if row.level_override is not None else row.level,
        # See the module docstring — an em-dash by right, not by omission.
        "remaining": None,
        "currency": row.currency,
        "status": row.status,
    }

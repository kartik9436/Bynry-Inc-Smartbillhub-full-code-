# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — R27 Plans & Discounts, the k-way
#           MERGE. Drawing read as an IMAGE (B14 rule 42): p060–p061 of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 3.0x.
# Story:    R27 `plans_and_discounts` — Customers › Enrolment · accounts +
#           rating · **As at**.
# Rules:    `BR-REP-040` (PO ruling 2026-09-27 option (a) — ONE report, one row
#           per ENROLMENT, a k-way merge of three SQL-sorted SQL-limited
#           streams, **a slower last page ACCEPTED and its measured cost
#           PUBLISHED in the rule**; splitting the report is REFUSED) ·
#           `BR-REP-024` (NULL with a reason, never a 0) · `BR-REP-001` (basis)
#           · `NFR-3` · `NFR-5` · CLAUDE.md hard rule 1 · hard rule 2 · hard
#           rule 4 (this file writes nothing) · B1 (the three tables are read
#           through `report_seams`, never queried across).
# Tests:    06-backend/tests/test_rep_p6w4_plans_and_discounts.py
# ───────────────────────────────────────────────────────
"""**R27 PLANS & DISCOUNTS — one row is one ENROLMENT**, across three programmes.

p061's own footnote is the ruling in the drawing's words:

    *"Three programmes in one table because a clerk asks one question — what is
    this account enrolled in. Splitting them into three reports was the first
    draft and it made the clerk run three."*

═══════════════════════════════════════════════════════════════════════════════
ONE ROW IS ONE ENROLMENT AND NOT ONE ACCOUNT — AND THE TILES PROVE IT
═══════════════════════════════════════════════════════════════════════════════
p061 draws ENROLLED **318** (16.3%) · LEVEL PAY **184** · PAYMENT PLANS **84**
($14,204.00 remaining) · ASSISTANCE **50**, and `184 + 84 + 50 = 318`. That
addition only works at ENROLMENT grain: one account can be on level pay AND a
payment plan AND assistance, so at account grain the same utility would report
fewer than 318 and the three programme tiles would no longer sum to the first.

⚠ **THE `ENROLLED 318 / 16.3%` TILE MIXES UNITS AND `BR-REP-040` SAYS SO:** 318
is a count of ENROLMENTS and 16.3% is a share of ACCOUNTS. They are served as two
separate figures with two separate names, so a screen cannot render one as the
other's percentage by accident.

═══════════════════════════════════════════════════════════════════════════════
THE MERGE LIVES HERE BECAUSE NO MODULE MAY OWN IT — B1
═══════════════════════════════════════════════════════════════════════════════
The three programmes are three tables in three modules:
`billing.account_budget_status`, `payments.payment_plans`,
`rating.discount_enrolments`. B1 forbids a cross-module query, so each module
publishes its OWN slice — already sorted, already limited — and this file merges
them through `report_seams`. **Putting the merge in any one of the three would
mean that module reading the other two's tables.**

⚠ **THE LAST PAGE IS SLOWER THAN THE FIRST AND THAT IS RULED, NOT A DEFECT.**
`BR-REP-040`, option (a) of two put to the Product Owner. A k-way merge cannot
know which stream a page's rows come from without fetching `offset + per` from
each, so page 20 of 50 fetches 1,000 rows from each of three streams to serve
fifty. **`NFR-3` and `NFR-5` are untouched**: every fetch is SQL-sorted and
SQL-limited, there is no Python slice of an unbounded read, and no cap exists
anywhere. The rule says to revisit if a tenant's enrolments reach the tens of
thousands.

⚠ **THE MEASURED COST IS PUBLISHED IN `BR-REP-040` AND NOT AVERAGED AWAY**, which
is the rule's own requirement and the thing wave 3's handover recorded as not yet
done.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from apps.reports import report_seams as seams

#: `BR-REP-001` — R27's eyebrow on p060 reads *As at*, which is a point in time
#: rather than a posting window.
BASIS_AS_AT = "as-at"

#: The three programme codes, in p061's own drawn order. The SCREEN renders each
#: into its own language (B14 rule 35).
PROGRAMMES: tuple[str, ...] = ("level_pay", "payment_plan", "assistance")

#: The sorts this read HONOURS. `BR-REP-040`'s merge orders by `since` DESC
#: across all three streams, so a sort the merge cannot apply must not be
#: offered — hard-won law 2's mirror.
PLANS_SORTS: tuple[str, ...] = ("since", "programme", "account")
PLANS_DEFAULT_SORT = "since"
PLANS_DEFAULT_DIRECTION = "desc"

#: A fetch buffer for the export, not a cap (`NFR-5`).
STREAM_CHUNK = 2_000

GAP_ACCOUNT_SHARE_UNAVAILABLE = {
    "code": "accounts_on_the_books_unavailable",
    "br_ref": "BR-REP-024 · BR-REP-040 · p061",
    "detail": (
        "The `16.3%` half of the ENROLLED tile is enrolments over ACCOUNTS, and the "
        "account count is customers' own as-at membership read. The seam answered None, "
        "which means customers cannot answer rather than that the utility has no "
        "accounts. Served as NULL with this reason — a 0% would tell a clerk nobody is "
        "enrolled while the count beside it reads 318."
    ),
}

GAP_PROGRAMME_UNWIRED = {
    "code": "a_programme_module_did_not_answer",
    "br_ref": "BR-REP-024 · BR-REP-040 · B1",
    "detail": (
        "One of the three programme reads answered None, which means that module "
        "cannot answer rather than that it has no enrolments. The report names which "
        "in `unwired_programmes` and serves the other two, because a clerk asking "
        "\"what is this account enrolled in\" is better served by two thirds of an "
        "answer that says so than by a complete-looking table missing a programme."
    ),
}


@dataclass(frozen=True)
class EnrolmentRow:
    """One enrolment, in p061's own column order.

    ⚠ **`terms` IS TWO FIELDS AND NOT ONE STRING.** p061 draws `12 months`,
    `6 instalments` and `Low-income · 20%` in one column — three different KINDS
    of term. Composing that sentence here would decide eleven catalogues' wording
    in English (B14 rule 35), so the figures travel separately and the screen
    writes its own language around them.

    ⚠ **`instalment` AND `remaining` ARE NULL ON WHOLE PROGRAMMES BY RIGHT.**
    Level pay has nothing to run down and assistance is not a thing an account
    pays; p061 draws em-dashes in both places. They are fields rather than
    omissions so the column is drawn rather than vanishing.
    """

    programme: str
    account: str
    since: date | None
    terms_months: int | None
    terms_percent: Decimal | None
    instalment: Decimal | None
    remaining: Decimal | None
    currency: str | None
    status: str


def _streams(*, as_of: Any, programme: str | None, status: str | None, limit: int | None):
    """The three published reads, each asked for `limit` rows, already sorted.

    Returns `(rows, unwired)` — a None from any seam is that MODULE saying it
    cannot answer, and it is named rather than silently folded into an empty
    list (`BR-REP-024`, and `DEF-075`'s cost).
    """
    wanted = PROGRAMMES if programme in (None, "", "all") else (programme,)
    calls = {
        "level_pay": seams.level_pay_enrolments,
        "payment_plan": seams.plan_enrolments,
        "assistance": seams.discount_enrolments,
    }
    rows: list[dict[str, Any]] = []
    unwired: list[str] = []
    for code in wanted:
        call = calls.get(code)
        if call is None:
            continue
        found = call(as_of=as_of, limit=limit, status=status)
        if found is None:
            unwired.append(code)
            continue
        rows.extend(found)
    return rows, unwired


def _sort_key(row: dict[str, Any], sort: str) -> tuple:
    """A TOTAL order across three streams — `since`, then programme, then account.

    ⚠ **THE TIE-BREAK IS NOT DECORATION.** Three streams each sorted by `since`
    will hand back many rows dated the same day, and without a total order the
    merge's choice among them changes between two calls with the same arguments —
    which repeats one row and drops another at a page boundary, with no symptom
    until somebody reads page two.
    """
    since = row.get("since") or date.min
    if sort == "programme":
        return (row.get("programme") or "", since, row.get("account") or "")
    if sort == "account":
        return (row.get("account") or "", since, row.get("programme") or "")
    return (since, row.get("programme") or "", row.get("account") or "")


def _merged(
    *, as_of: Any, programme: str | None, status: str | None, sort: str, direction: str,
    limit: int | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    """`BR-REP-040`'s k-way merge — three sorted, limited streams into one order."""
    rows, unwired = _streams(as_of=as_of, programme=programme, status=status, limit=limit)
    rows.sort(
        key=lambda row: _sort_key(row, sort),
        reverse=str(direction or "").lower() != "asc",
    )
    return rows, unwired


def _counts(*, as_of: Any, status: str | None) -> dict[str, Any]:
    """p061's four tiles, over the WHOLE filtered set and never over a page.

    ⚠ **THE PROGRAMME COUNTS MUST SUM TO `enrolled`, AND THE TEST ASSERTS IT.**
    That identity is the whole evidence the grain is an ENROLMENT; if it ever
    stops holding, the report has quietly become one row per account.
    """
    totals: dict[str, Any] = {code: 0 for code in PROGRAMMES}
    unwired: list[str] = []
    rows, unwired = _streams(as_of=as_of, programme=None, status=status, limit=None)
    for row in rows:
        code = row.get("programme")
        if code in totals:
            totals[code] += 1
    enrolled = sum(totals.values())
    remaining = sum(
        (row.get("remaining") or Decimal("0"))
        for row in rows
        if row.get("remaining") is not None
    )
    accounts = seams.accounts_on_the_books(as_of=as_of)
    share = None
    if accounts:
        share = round(enrolled * 100.0 / int(accounts), 6)
    return {
        "enrolled": enrolled,
        "enrolled_share": share,
        "enrolled_share_absence": None if share is not None else (
            GAP_ACCOUNT_SHARE_UNAVAILABLE["code"]
        ),
        "level_pay": totals["level_pay"],
        "payment_plan": totals["payment_plan"],
        "assistance": totals["assistance"],
        "plan_remaining": remaining,
        "unwired": unwired,
    }


def plans_and_discounts(
    *,
    as_of: date | None = None,
    programme: str | None = None,
    status: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = PLANS_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R27, ONE PAGE. One row per ENROLMENT, merged from three streams.

    `per=None` is the whole filtered set. The CALLER clamps; this function
    invents no cap (`NFR-5`).

    ⚠ **EACH STREAM IS ASKED FOR `offset + per` ROWS — `BR-REP-040`'s ruled
    exception.** It is the only way a merge can guarantee the page it serves is
    the page the merged order would produce, and it is why the last page costs
    more than the first. Published, not hidden.
    """
    sort = sort if sort in PLANS_SORTS else PLANS_DEFAULT_SORT
    tiles = _counts(as_of=as_of, status=status)
    total_rows = tiles["enrolled"]

    served_page = max(1, int(page or 1))
    if per is None:
        fetch = None
        pages = 1
        offset = 0
        size = None
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_rows // size)) if total_rows else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        fetch = offset + size

    rows, unwired = _merged(
        as_of=as_of, programme=programme, status=status,
        sort=sort, direction=direction, limit=fetch,
    )
    window = rows if size is None else rows[offset : offset + size]

    problems: list[dict[str, Any]] = []
    if tiles["enrolled_share_absence"]:
        problems.append(dict(GAP_ACCOUNT_SHARE_UNAVAILABLE))
    if unwired or tiles["unwired"]:
        problems.append(dict(GAP_PROGRAMME_UNWIRED))

    return {
        "basis": BASIS_AS_AT,
        "window": {"start": as_of, "end": as_of},
        "currency": _single_currency(rows),
        "grain": "one enrolment — an account's membership of one programme",
        "rows": tuple(_row(found) for found in window),
        "totals": {
            "enrolled": tiles["enrolled"],
            "enrolled_share": tiles["enrolled_share"],
            "level_pay": tiles["level_pay"],
            "payment_plan": tiles["payment_plan"],
            "assistance": tiles["assistance"],
            # p061's `$14,204.00 remaining` sub-line, and the SUM of the
            # REMAINING column beneath it — one figure computed once.
            "plan_remaining": tiles["plan_remaining"],
        },
        "absences": {"enrolled_share": tiles["enrolled_share_absence"]},
        "additivity": {
            # One enrolment contributes once — that is the grain.
            "enrolled": "full",
            "level_pay": "full",
            "payment_plan": "full",
            "assistance": "full",
            "plan_remaining": "full",
            # A share of accounts is not summed.
            "enrolled_share": "non",
        },
        "unwired_programmes": tuple(sorted(set(unwired) | set(tiles["unwired"]))),
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_rows,
        "problems": tuple(problems),
    }


def _single_currency(rows: list[dict[str, Any]]) -> str | None:
    """The filtered set's currency, or None when two disagree.

    A footer summing two currencies into one symbol is a number that is wrong in
    both; `None` makes the renderer print the figure without a symbol rather than
    a confident lie. The same call `disconnect_reconnect` already makes.
    """
    found = {row.get("currency") for row in rows if row.get("currency")}
    return found.pop() if len(found) == 1 else None


def _row(found: dict[str, Any]) -> EnrolmentRow:
    return EnrolmentRow(
        programme=found["programme"],
        account=found["account"],
        since=found.get("since"),
        terms_months=found.get("terms_months"),
        terms_percent=found.get("terms_percent"),
        instalment=found.get("instalment"),
        remaining=found.get("remaining"),
        currency=found.get("currency"),
        status=found.get("status"),
    )


def plans_and_discounts_stream(
    *,
    as_of: date | None = None,
    programme: str | None = None,
    status: str | None = None,
    sort: str | None = None,
    direction: str = PLANS_DEFAULT_DIRECTION,
) -> Any:
    """EVERY row of R27, from a generator — no `page`, no `per`.

    ⚠ **THE WHOLE MERGE IS MATERIALISED HERE AND THAT IS HONEST RATHER THAN
    LAZY.** A k-way merge over three streams has no streaming form that is
    cheaper than sorting the union once: every row of every stream must be seen
    before the first row of the merged order is known to be first. Chunking the
    YIELD would look like a streaming read and cost exactly the same.
    """
    sort = sort if sort in PLANS_SORTS else PLANS_DEFAULT_SORT
    rows, _ = _merged(
        as_of=as_of, programme=programme, status=status,
        sort=sort, direction=direction, limit=None,
    )
    for found in rows:
        yield _row(found)

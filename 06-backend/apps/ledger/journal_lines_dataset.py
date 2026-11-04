# ── Trace ──────────────────────────────────────────────
# Story:    CR-142-BRC07 · the `journal_lines` DATASET QUERY (brief §7.1 —
#           "datasets are code, definitions are data"; §08 — "every arrow into
#           the database passes through a reviewed dataset").  It is the query
#           behind R15 Trial Balance, R16 Journal Export, R17 Revenue Analysis,
#           R18 Tax Remittance, R21 Close Pack, R25 Ledger, R39 Regulatory
#           Filing, R40 External Reconciliation and R43 Trend Pack — nine of the
#           ten definitions seeded against this dataset.
#           Drawings read as IMAGES (B14 rule 42): p055 (R15), p056 (R16/R17),
#           p057 (R18), p058 (R21/R42), p059 (R43), p067–p068 (R39/R40),
#           p071–p072 (R25a/b/c), p085 (§7.2.2 additivity), p087 (§7.5 read path
#           + §7.6 scale), p090–p092 (§08 architecture).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `_tenant_id()` and RLS
#           FORCE) · hard rule 2 (money 4 dp, percentages 6, DISPLAY 2; Decimal
#           end to end, never float and never cents) · hard rule 4 (reads only)
#           · **hard rule 5 — ONLY THE POSTING SERVICE WRITES JOURNAL LINES;
#           THIS FILE WRITES NOTHING AT ALL** · NFR-3 (universal server
#           pagination — `limit`/`offset`/`sort` applied IN SQL) · NFR-5 (no
#           hard caps anywhere) · BR-REP-001 (a money report names its basis) ·
#           BR-REP-002 (read models only) · BR-REP-024 (never a 0 where a figure
#           could not be computed) · BR-LED-007 (a difference is the posting
#           service's defect, never the report's to plug)
# Tests:    06-backend/tests/test_rep_journal_lines_dataset.py
#           06-backend/tests/test_rep_journal_lines_dataset_pg.py (PostgreSQL)
# Impacts:  apps/reports/report_seams.py (the ONLY cross-module caller) ·
#           apps/reports/queries.py (the viewers) · apps/reports/datasets.py
#           (`JOURNAL_LINES.paginates`)
# ───────────────────────────────────────────────────────
"""THE `journal_lines` DATASET — one row per journal line, paged and sorted in SQL.

🔒 SENSITIVE PATH · HUMAN-OWNED · HUMAN-REVIEW-PENDING — this is a ledger read
on the money path, and it decides what nine finance reports SAY the books
contain. Row in `12-governance/09-human-review-ledger.md`, written before the
review rather than after it.

⚠ **AND IT IS NOT ON `G7`'s GLOB LIST, WHICH IS REPORTED HERE RATHER THAN
SILENTLY ACCEPTED.** `10-scripts/gates/human_owned.txt` names ledger's five
WRITERS — `posting`, `chart`, `close`, `manual_je`, `exports` — and no read.
`apps/ledger/reporting.py` carries exactly the same three markers and exactly
the same absence, and says so in its own header for exactly this reason: **a
marker no gate reads is hard-won law 1 written into a money path.** Adding a
file to that list is a process event and the PO's call, not a lane's, so it is
put to them in the review ledger instead of taken here.

════════════════════════════════════════════════════════════════════════════
WHY THIS FILE EXISTS WHEN `reporting.py` ALREADY HOLDS NINE LEDGER READS
════════════════════════════════════════════════════════════════════════════
`apps/reports/datasets.py` DECLARES a dataset called `journal_lines` whose grain
is *"one journal line"* and whose columns are `posted_on · account_code ·
account_name · reference · narrative · debit · credit · balance`. Ten seeded
definitions name it. **Nothing implemented it**, so `runner.run()` raised
`DatasetNotExecutable` for every one of them and their catalogue cards read
*"This report cannot be produced yet."*

`reporting.py`'s reads are AGGREGATES over journal lines — a trial balance is Σ
per GL account, a remittance table is Σ per authority. Not one of them returns
the LINE. R16 Journal Export and R25a Ledger·by·account are drawn as line
listings, and an aggregate cannot be un-aggregated. So this is the missing
primitive rather than a tenth summary, and every aggregate in `reporting.py`
stays exactly where it is — reused, never re-derived here.

════════════════════════════════════════════════════════════════════════════
IT PAGES AND SORTS IN SQL, AND THE COST IS MEASURED RATHER THAN ASSERTED
════════════════════════════════════════════════════════════════════════════
Brief §7.5: *"Sync viewing — page 1 — returns rows with limit/offset/sort
applied in SQL. Never the whole result."* §7.6 puts the biggest report at T5 at
about 480,000 rows against a worker given sixty seconds
(`docker-entrypoint.sh`, `GUNICORN_TIMEOUT:-60`).

So `per` cuts the page with `[offset:offset+limit]` on a QuerySet — one
`LIMIT/OFFSET` — and `sort` is `order_by(*order_terms(...))`. **Nothing is
sorted or sliced in Python anywhere in this file.** The measured figures are in
`10-scripts/ds_ledger_journal_lines_cost.py` and quoted in the lane report.

**`per=None` IS THE WHOLE FILTERED SET AND IS THE EXPORT'S DOOR.** Brief §7.5
again: exporting *"streams every row and never holds a page"*. `NFR-5` forbids a
ceiling on that branch and there must never be one.

════════════════════════════════════════════════════════════════════════════
⚠ THE BALANCED PAIR — A DATABASE GUARANTEE, NOT A REPORT'S OPINION
════════════════════════════════════════════════════════════════════════════
R15's drawing (p055) carries the warning verbatim: *"Balanced pairs are a
database guarantee, not a report's opinion. A difference other than zero here
means the posting service has a defect, not that the report needs tuning."*

`totals["difference"]` is therefore Σ debits − Σ credits over the whole
FILTERED set, as two SQL aggregates, and it is published on every answer. It is
never plugged, never rounded into agreement and never suppressed.

⚠ **AND `balanced` IS `None` — NOT `False` — THE MOMENT A LINE-NARROWING FILTER
IS APPLIED.** Balance is a property of an ENTRY. A filter on `service`,
`premises`, `account` or a GL account range keeps SOME of each entry's lines, so
the residue does not foot and a `False` there would accuse the posting service
of a defect it does not have. That is `trial_balance`'s own C24 reasoning, one
level down, and it is the difference between a check that fires on a real
BR-LED-007 breach and one that cries wolf on every chip a clerk clicks. The
window (`start`/`end`) and the entry-level filters (`source_type`, `search` on
the entry's own number/memo) do NOT narrow within an entry, so they leave the
verdict standing.

════════════════════════════════════════════════════════════════════════════
ADDITIVITY (brief §7.2.2, read as an image on p085)
════════════════════════════════════════════════════════════════════════════
`debit`, `credit` and `lines` are FULLY additive — sum them in any direction.
`balance` is a POSITION and is SEMI-additive: it sums across accounts and never
across time, for the reason an AR balance does. `apps/reports/datasets.py`
already declares exactly that, and `REP-P2-MODEL`'s footer refusal reads that
declaration — so this file does not re-state it, it RESPECTS it: the running
`balance` is never totalled here, and `totals` carries debit, credit, difference
and a count and nothing else.

════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
════════════════════════════════════════════════════════════════════════════
**It writes nothing.** Hard rule 5 gives journal lines one writer and it is
`apps/ledger/posting.py`; hard rule 4 forbids UPDATE and DELETE outright. There
is no INSERT, UPDATE, DELETE or `save()` below, and `ledger_sole_writer_guard()`
would raise by name if one arrived.

**It never falls back to zero.** BR-REP-024: a figure that cannot be computed is
`None` beside a named reason, in `problems`. An empty book has no currency and
no total to get wrong — that is `0.00` and always was, which is a different
thing from *not derivable* and is reported as such.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, DecimalField, F, Q, Sum, Value
from django.db.models.functions import (
    Coalesce,
    TruncDay,
    TruncMonth,
    TruncQuarter,
    TruncYear,
)

from apps.ledger import dimension_seam, models

# ⚠ **IMPORTED FROM `reporting.py` RATHER THAN REIMPLEMENTED, AND THAT IS
# LOAD-BEARING.** `_posted_lines` carries the tenant filter AND the
# `status='posted'` definition of what the books ARE; `_one_currency` is
# DEF-081's guard, asked before any Σ. A second copy of either would be a
# second answer to *"whose books, and in what currency"*, which is the exact
# failure BR-REP-002 exists to prevent.
from apps.ledger.reporting import ZERO, _one_currency, _posted_lines
from core.pagination import order_terms

#: BR-REP-001. Every figure here is dated by `journal_entries.entry_date` — the
#: BOOK date — which is the POSTING basis and is what all ten drawings name in
#: their eyebrow. `posted_at`, the wall-clock moment, is deliberately never the
#: filter: LE-9's payment dated Jul 30 arriving Aug 7 belongs to the period its
#: entry_date says, and a report keyed on `posted_at` moves July's total every
#: time a late entry lands.
BASIS = "posting"

#: What a caller may order by. Four, because four are what the drawings put a
#: sort on, and a sort this query does not honour would be a live caret over a
#: dead control — hard-won law 2's mirror, which `DEF-CWP-3925` is about.
#:
#: ⚠ **EVERY TUPLE ENDS IN A UNIQUE COLUMN.** A page is a window over an ORDER;
#: if that order is not total, two rows that compare equal may swap between page
#: 1 and page 2 and a clerk sees one row twice and another never. `id` closes
#: every tuple — `core.pagination.order_terms` refuses to add a tiebreak
#: silently, precisely so this stays the caller's stated decision.
#:
#: ⚠ **`reference` DOES NOT ORDER BY THE RENDERED STRING**, for the reason
#: `reporting.JOURNAL_SORT_COLUMNS` already records: the PO ruled the entry
#: number `JE-MMDDYY-nnnn` on 2026-09-23, and `MMDDYY` does not sort
#: chronologically as text — `JE-011526-0001` precedes `JE-020325-0001` and is
#: eleven months older. So it orders by the book date first, exactly as the
#: journal list does, and the two screens cannot disagree about sequence.
LINE_SORTS: tuple[str, ...] = ("posted_on", "account_code", "amount", "reference")
LINE_DEFAULT_SORT = "posted_on"
LINE_SORT_COLUMNS: dict[str, tuple[str, ...]] = {
    "posted_on": ("journal_entry__entry_date", "journal_entry__created_at", "id"),
    "account_code": ("ledger_account__code", "journal_entry__entry_date", "id"),
    "amount": ("amount", "journal_entry__entry_date", "id"),
    "reference": ("journal_entry__entry_date", "journal_entry__created_at", "id"),
}

#: The filters this dataset accepts, and the ones `apps/reports/datasets.py`
#: declares for it. Named here so the two cannot drift — `P2.12`'s test reads
#: both and fails when they do.
LINE_FILTERS: tuple[str, ...] = (
    "from",
    "to",
    "account_from",
    "account_to",
    "service",
    "basis",
)

#: Filters that keep only SOME of an entry's lines, so the residue cannot be
#: expected to foot. Listed rather than inferred, because the balanced-pair
#: verdict keys on this set and a reader has to be able to see which ones they
#: are without tracing the code. See the module docstring.
_NARROWING: tuple[str, ...] = (
    "account_from",
    "account_to",
    "service_code",
    "account_id",
    "premises_id",
    "tax_authority_id",
)

_MONEY = DecimalField(max_digits=18, decimal_places=6)


def _side_sum(side: str) -> Any:
    """Σ of one SIDE's amounts, as a Decimal, with an empty set reading `0`.

    ⚠ **IT IS A FILTERED AGGREGATE AND NOT A SECOND QUERY.** Both sides come
    back from ONE `aggregate()` call — one `SELECT`, two `SUM(...) FILTER
    (WHERE side = …)` expressions — so the debit total and the credit total are
    struck over the same snapshot of the same rows. Two round trips could see
    two different books if a posting landed between them, and *"the debits and
    the credits were read a millisecond apart"* is not a defect anybody would
    ever diagnose from an unbalanced trial balance.

    `Coalesce(..., Value(ZERO))` rather than `or ZERO` in Python: an aggregate
    over no rows returns SQL NULL, and *"no lines"* and *"lines that net to
    nothing"* are both zero movement. What is NOT zero-filled is a figure that
    could not be DERIVED; that is `None` beside a named reason, in `problems`
    (BR-REP-024).
    """
    return Coalesce(
        Sum("amount", filter=Q(side=side), output_field=_MONEY),
        Value(ZERO, output_field=_MONEY),
    )


@dataclass(frozen=True)
class JournalLineRow:
    """One journal line, in the dataset's own declared column names.

    ⚠ **`debit` AND `credit` ARE TWO COLUMNS AND THE STORED SHAPE IS ONE.**
    `journal_lines` holds a non-negative `amount` beside a `side`, because B2 §2
    wants exactly one way to express a credit. Every drawing — R15's table, R16's
    export, R25a's ledger — draws two money columns. The split happens HERE,
    once, so eleven catalogues and one CSV writer cannot each invent their own,
    and the un-split `side`/`amount` pair travels beside them for a caller that
    wants the stored fact.

    ⚠ **`balance` IS A RUNNING POSITION AND IS `None` ON THIS ROW.** A running
    balance depends on the rows BEFORE it in one total order, which is a
    different question from *"what does this line say"* — and it is
    SEMI-ADDITIVE, so a footer that summed it would be the canonical wrong
    answer §7.2.2 names. `apps/ledger/reporting.account_ledger` computes it, for
    one account, with the carry-forward that survives a page. This dataset does
    not, and says so rather than serving a plausible number.
    """

    line_id: str
    posted_on: date
    entry_id: str
    entry_number: str | None
    account_code: str | None
    account_name: str | None
    reference: str | None
    narrative: str | None
    side: str
    amount: Decimal
    debit: Decimal
    credit: Decimal
    balance: None
    service_id: str | None
    service_label: str | None
    customer_account_id: str | None
    customer_account_label: str | None
    premises_id: str | None
    premises_label: str | None
    source_type: str | None
    currency: str | None


#: BR-REP-024 — named, never a silent zero and never a plausible number.
GAP_BALANCE_IS_NOT_A_LINE_FACT = {
    "code": "running_balance_is_not_a_property_of_one_line",
    "br_ref": "brief §7.2.2 · NFR-3",
    "detail": (
        "The dataset declares a `balance` column and this grain cannot carry it. A running "
        "balance is cumulative over the rows before it in one total order, so it is a property "
        "of an ordered SEQUENCE and not of a line — and it is semi-additive, so a footer that "
        "summed it would be the wrong answer this brief names first. "
        "`apps.ledger.reporting.account_ledger` computes it for ONE account with a carry-forward "
        "that survives a page; this query serves the line and leaves the column null."
    ),
    "wanted_reads": (),
}

GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT = {
    "code": "a_narrowed_set_cannot_state_whether_the_books_foot",
    "br_ref": "BR-LED-007 · hard rule 5",
    "detail": (
        "Balance is a property of an ENTRY. This answer was narrowed by a filter that keeps "
        "only some of each entry's lines, so the residue is not expected to foot and no verdict "
        "is stated. The difference is still published, because it is a real figure about the "
        "rows in front of you; what it is NOT is evidence about the posting service. Remove the "
        "narrowing filters to get the verdict BR-LED-007 is about."
    ),
    "wanted_reads": (),
}


#: ── THE GROUP LEVELS THIS QUERY CAN CUT **IN SQL** (`P2.17`) ────────────────
#:
#: ⚠ **A GROUP LEVEL IS A `GROUP BY` OR IT IS NOTHING, AND THAT IS NOT A STYLE
#: PREFERENCE — IT IS THE ONLY WAY THE SUBTOTAL CAN FOOT.** `apps/reports/slicers.py`
#: could add the served rows up in Python, and until this table existed that is
#: what happened. The rows it was given are **ONE PAGE**: measured on this
#: branch, 2026-09-27, the billing register grouped by status served subtotals
#: of `$14,048.10 + $137.70 = $14,185.80` over 50 rows, under a footer of
#: `$30,750.07` over 92 bills — two figures on one screen that do not foot, with
#: nothing saying the groups covered half the report (`DEF-REP-6875`).
#:
#: So a level is offered here only when it can be expressed as a database
#: expression over the SAME filtered queryset the totals are struck over. Then
#: a group's Σ and the footer's Σ are two aggregates over one set and cannot
#: disagree. A level absent from this table is not grouped by this query, and
#: `slicers` refuses it by name rather than rolling up a page.
#:
#: ⚠ **`year`, `quarter`, `accounting_period` AND `day` ARE THE CALENDAR
#: HIERARCHY AND ARE DATED BY `entry_date`** — the BOOK date, which is `BASIS`.
#: Truncating `posted_at` instead would move July's subtotal every time a late
#: entry landed, which is the reason this module never filters on it either.
GROUP_LEVELS: dict[str, Any] = {
    "year": TruncYear("journal_entry__entry_date"),
    "quarter": TruncQuarter("journal_entry__entry_date"),
    "accounting_period": TruncMonth("journal_entry__entry_date"),
    "day": TruncDay("journal_entry__entry_date"),
    "service": F("service__code"),
}

#: ⚠ **`account_code` AND `source_type` ARE NOT HERE, AND THEY WERE, FOR AN HOUR.**
#: Both are one `F()` away and both would have been **unreachable dead controls**:
#: `apps/reports/datasets.py::JOURNAL_LINES` declares its dimensions as time,
#: service, consumer class, account status, customer type, premises, unit and area
#: — a GL account code and an entry's source are neither a dimension nor a level of
#: one — and `slicers.validate_grouping` drops a level that is not. Measured on
#: this branch, 2026-09-27: `group_by=accounting_period,account_code` returned 50
#: ungrouped rows and `unavailable` carrying `grouping_not_served`, so the second
#: level took the first down with it.
#:
#: **A group level becomes reachable when `datasets.py` declares the dimension, and
#: this table moves in the same commit as that declaration or not at all.**
#:
#: ⚠ **`premises` IS A DECLARED DIMENSION AND IS STILL NOT HERE**, for a different
#: reason: the column is `premises_id`, and B14 rule 31 says no database id is ever
#: the visible value of a field. Grouping on it would need
#: `dimension_seam.premises_labels` resolved per group, which is a bounded batched
#: read this function does not do for group cells yet. Named rather than served
#: wrong: a group row labelled with a UUID is a rule break a footer would not catch.

#: The measures a group row carries, and every one is FULLY ADDITIVE (§7.2.2).
#: `balance` is deliberately absent: it is null on every row of this grain
#: (`GAP_BALANCE_IS_NOT_A_LINE_FACT`) and semi-additive besides, so a subtotal
#: of it would be the canonical wrong answer the brief names first.
GROUP_MEASURES: tuple[str, ...] = ("debit", "credit", "lines")


def _grouped(rows: Any, levels: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    """One SQL `GROUP BY` **per prefix** of the levels, over the whole filtered set.

    Three levels means three `SELECT`s and not one, and the reason is arithmetic
    rather than taste: a single `GROUP BY a, b, c` returns only the LEAF cells,
    and deriving the level-0 and level-1 subtotals from them is a Python roll-up
    wearing a SQL hat — the same page-scoped addition this table exists to
    remove, just one step later. Each prefix is its own aggregate over the same
    queryset, so every subtotal at every level is struck by the database over
    the rows it actually covers.

    ⚠ **THE COUNT IS `lines` AND NOT `len(rows)`.** A group's `rows` figure is
    what the group HOLDS in the filtered set, which is the number `P2.24` opens
    and the number a clerk compares against the footer. A length of whatever
    page happened to be fetched is the defect above.
    """
    out: list[dict[str, Any]] = []
    for depth in range(1, len(levels) + 1):
        prefix = levels[:depth]
        aliases = {f"_g{i}": GROUP_LEVELS[name] for i, name in enumerate(prefix)}
        cells = (
            rows.annotate(**aliases)
            .values(*aliases)
            .annotate(
                _debit=_side_sum(models.SIDE_DEBIT),
                _credit=_side_sum(models.SIDE_CREDIT),
                _lines=Count("id"),
            )
            .order_by(*aliases)
        )
        for cell in cells:
            out.append(
                {
                    "level": depth - 1,
                    "dimension": prefix[-1],
                    "values": tuple(cell[f"_g{i}"] for i in range(depth)),
                    "rows": int(cell["_lines"]),
                    "measures": {
                        "debit": cell["_debit"],
                        "credit": cell["_credit"],
                        "lines": int(cell["_lines"]),
                    },
                }
            )
    return tuple(out)


def journal_lines(
    *,
    start: date | None = None,
    end: date | None = None,
    account_from: str | None = None,
    account_to: str | None = None,
    service_code: str | None = None,
    account_id: Any = None,
    premises_id: Any = None,
    tax_authority_id: Any = None,
    source_type: str | None = None,
    search: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = "desc",
    group_by: tuple[str, ...] | list[str] = (),
) -> dict[str, Any]:
    """THE dataset query. One row per posted journal line, paged and sorted in SQL.

    `per=None` is the whole filtered set — the EXPORT's branch (§7.5), and
    `NFR-5` forbids a ceiling on it. `per` is an integer page size; the caller
    clamps it (`core.pagination.clamp_page_size`) and this function does not
    invent one, because a cap invented here is a cap nobody can see.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE.** That is what makes the KPI tiles foot to the report whether a page
    is cut or not — the premise `/outstandings`'s withdrawn docstring got
    backwards and the one `billing_register` already builds on.

    Refuses `start > end` at the caller; an inverted window here would answer an
    empty-but-plausible report, which US-LED-009 TC-6 forbids by name.
    """
    rows = _posted_lines(start=start, end=end, premises_id=premises_id)

    # ── the filters, every one of them in SQL ───────────────────────────────
    # ⚠ An account RANGE is on the GL account's CODE and is INCLUSIVE at both
    # ends, which is what R15's `Account range` control means and what a finance
    # officer reads "1200 to 1299" as. It is a string comparison because a chart
    # of accounts is not numeric — `1200-01` is a lawful code on this product.
    if account_from:
        rows = rows.filter(ledger_account__code__gte=str(account_from))
    if account_to:
        rows = rows.filter(ledger_account__code__lte=str(account_to))
    if service_code:
        rows = rows.filter(service__code=str(service_code))
    if account_id is not None:
        rows = rows.filter(account_id=account_id)
    if tax_authority_id is not None:
        rows = rows.filter(tax_authority_id=tax_authority_id)
    if source_type:
        # The ENTRY's source, not the line's: R16 exports a batch of entries and
        # R21 ties out against what produced them.
        rows = rows.filter(journal_entry__source_type=str(source_type))
    if search:
        needle = str(search).strip()
        if needle:
            rows = rows.filter(
                Q(journal_entry__number__icontains=needle)
                | Q(journal_entry__memo__icontains=needle)
                | Q(ledger_account__code__icontains=needle)
                | Q(ledger_account__name__icontains=needle)
            )

    # ── DEF-081: one currency, or no number — asked BEFORE any Σ ────────────
    currency = _one_currency(rows, figure="journal lines")

    # ── the totals: two SQL aggregates over the WHOLE filtered set ──────────
    aggregated = rows.aggregate(
        debit=_side_sum(models.SIDE_DEBIT),
        credit=_side_sum(models.SIDE_CREDIT),
    )
    total_debit: Decimal = aggregated["debit"]
    total_credit: Decimal = aggregated["credit"]
    total_lines = rows.count()

    narrowed = any(
        value not in (None, "")
        for value in (
            account_from,
            account_to,
            service_code,
            account_id,
            premises_id,
            tax_authority_id,
        )
    )

    problems: list[dict[str, Any]] = [dict(GAP_BALANCE_IS_NOT_A_LINE_FACT)]
    if narrowed:
        problems.append(dict(GAP_FILTERED_BALANCE_IS_NOT_A_VERDICT))

    # ── the page, cut in SQL ────────────────────────────────────────────────
    ordered = rows.order_by(
        *order_terms(
            sort,
            direction,
            columns=LINE_SORT_COLUMNS,
            default=LINE_DEFAULT_SORT,
        )
    ).select_related("journal_entry", "ledger_account", "service")

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_lines // size))
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    premises_ids = {str(line.premises_id) for line in materialised if line.premises_id}
    account_ids = {str(line.account_id) for line in materialised if line.account_id}
    premises_names = dimension_seam.premises_labels(premises_ids) if premises_ids else {}
    account_names = dimension_seam.account_labels(account_ids) if account_ids else {}

    shaped = [_row(line, premises_names, account_names) for line in materialised]

    # ── the group rows, cut in SQL over the WHOLE filtered set (`P2.17`) ─────
    # ⚠ **A LEVEL THIS QUERY CANNOT EXPRESS IS NOT GROUPED AND IS NOT FAKED.**
    # `GROUP_LEVELS` is the whole vocabulary; anything else comes back in
    # `groups_not_served` and `apps/reports/slicers.py` refuses it by name. The
    # alternative — adding the served page up in Python — is `DEF-REP-6875`.
    wanted = tuple(str(level) for level in (group_by or ()))
    servable = tuple(level for level in wanted if level in GROUP_LEVELS)
    refused = tuple(level for level in wanted if level not in GROUP_LEVELS)
    groups = _grouped(rows, servable) if servable else ()

    return {
        "basis": BASIS,
        "currency": currency,
        "rows": tuple(shaped),
        # `()` when nothing was asked for, so an ungrouped answer is byte-for-byte
        # what it was before this key existed.
        "groups": groups,
        "grouped_by": servable,
        "groups_not_served": refused,
        "group_measures": GROUP_MEASURES,
        "totals": {
            "debit": total_debit,
            "credit": total_credit,
            # ⚠ NEVER PLUGGED, NEVER ROUNDED INTO AGREEMENT. R15's warning,
            # verbatim: a difference other than zero means the posting service
            # has a defect, not that the report needs tuning.
            "difference": total_debit - total_credit,
            "lines": total_lines,
        },
        # `None` rather than `False` on a narrowed set — see the module
        # docstring. `True` is a statement about the BOOKS and is only
        # available when every line of every matched entry is in the set.
        "balanced": None if narrowed else (total_debit == total_credit),
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_lines,
        "filtered": narrowed or bool(source_type) or bool(search),
        "problems": tuple(problems),
    }


def _row(
    line: Any,
    premises_names: dict[str, str],
    account_names: dict[str, str],
) -> JournalLineRow:
    """One stored line, split into the dataset's declared columns."""
    entry = line.journal_entry
    gl = line.ledger_account
    debit = line.amount if line.side == models.SIDE_DEBIT else ZERO
    credit = line.amount if line.side == models.SIDE_CREDIT else ZERO
    premises_id = str(line.premises_id) if line.premises_id else None
    customer_account_id = str(line.account_id) if line.account_id else None
    return JournalLineRow(
        line_id=str(line.id),
        posted_on=entry.entry_date,
        entry_id=str(entry.id),
        entry_number=entry.number,
        account_code=gl.code if gl else None,
        account_name=gl.name if gl else None,
        # The drawing's REFERENCE column is what a finance officer matches
        # against: the entry's own number where it has one, and its source
        # otherwise. Never the database id — B14 rule 31.
        reference=entry.number or (entry.source_type or None),
        narrative=entry.memo,
        side=line.side,
        amount=line.amount,
        debit=debit,
        credit=credit,
        balance=None,
        service_id=str(line.service_id) if line.service_id else None,
        service_label=line.service.code if line.service_id and line.service else None,
        customer_account_id=customer_account_id,
        customer_account_label=(
            account_names.get(customer_account_id) if customer_account_id else None
        ),
        premises_id=premises_id,
        premises_label=premises_names.get(premises_id) if premises_id else None,
        source_type=line.source_type or entry.source_type,
        currency=entry.currency,
    )


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 · the `journal_lines` dataset query (05-prototype/09 Reports Build Brief.pdf p049–p073 read as images per B14 rule 42; §7.2.2 p085; §7.5/§7.6 p087; §08 p090–p092)
# screens: S44 (the catalogue card goes available) · S46 (the viewer)
# generated: 2026-09-26 by lane DS-LEDGER
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=HUMAN-REVIEW-PENDING (🔒 ledger read, money path)
# exceptions: (1) `balance` is served null on every row with a named reason — the grain cannot carry a cumulative figure and the declared measure is semi-additive · (2) `balanced` is null rather than false on a narrowed set, because a filter that keeps part of an entry cannot accuse the posting service of anything · (3) this file writes nothing: no INSERT, UPDATE, DELETE or save() — hard rules 4 and 5
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

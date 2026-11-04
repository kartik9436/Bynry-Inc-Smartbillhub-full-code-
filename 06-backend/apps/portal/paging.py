# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CWP-5747 — *"every customer-portal list holds ALL its rows in
#          the browser"*. Six portal edge endpoints served an unbounded array
#          and `PortalListTable` searched, sorted and sliced it client-side.
# Rules:   NFR-3 (universal server pagination) · NFR-5 (no hard caps anywhere —
#          nothing here refuses a row that exists) · BR-SHL-011 (the URL
#          grammar q/sort/dir/page/per/f.<name>; invalid values FALL BACK or
#          CLAMP and never 4xx) · IS-2 (the one page-size vocabulary,
#          50/100/200/500/1000, default 50) · BR-CWP-010 (the session's account
#          set is intersected in the QUERY and this file never widens it)
# Screens: CWP-023 · CWP-027 · CWP-031 · CWP-034 · CWP-041
# Tests:   06-backend/tests/test_def_cwp_5747_portal_lists_page_on_the_server.py
# ───────────────────────────────────────────────────────
"""The portal edge's list window — **one grammar, one envelope, five lists.**

⚠ **THE GRAMMAR IS THE HOUSE ONE AND IS NOT A PORTAL DIALECT.**
`core.pagination.parse_list_params` already parses `q/sort/dir/page/per/f.<name>`
with `BR-SHL-011`'s fall-back-or-clamp semantics for every staff list in the
product, and a second spelling of *what a page number is* is how two surfaces
start disagreeing about `?page=0`. This module adds the two things the portal
needs on top of it and nothing else.

⚠ **THE ENVELOPE IS NOT DRF'S, AND THAT IS DELIBERATE.** Every staff list
serves `count / next / previous / results`; every portal list has always served
its rows under a NAMED key — `{"bills": […]}`, `{"readings": […], "next_read":
…}` — and eleven screens, forty test files and the front-end client read that
key. Converting them to `results` would be a rename of the whole edge in the
commit whose subject is paging, so the rows stay where they are and `count`,
`page` and `per` are ADDED beside them. `next`/`previous` are not built: the
portal client sends a page NUMBER and has no use for a link, and a link nobody
follows is surface with no caller (hard-won law 2).

⚠ **`count` IS THE WHOLE SEARCHED SET AND NEVER THE PAGE.** `DEF-NOT-5746`
records what the other answer costs: a tab that counted its own page read
*"1–50 of 50"* over four thousand rows, and the next-page arrow reached
nothing.

⚠ **WHY THE CLAMP IS HERE RATHER THAN IN `StandardPagination`.** That class
clamps by asking a `Paginator` how many pages there are, which needs the whole
result set — the exact `NFR-3` breach this file exists to remove. The count is
known only AFTER the selector has taken its page, so the clamp is applied by
re-asking with the last page number, which is one extra query on the one
request where a person typed a page that does not exist.
"""

from __future__ import annotations

import math
from typing import Any, Callable

from core.pagination import ListParams, clamp_page_size, parse_list_params

#: Re-exported so a caller declaring a list's vocabulary imports one module.
__all__ = [
    "ListParams",
    "SQL_PAGED",
    "clamp_page_size",
    "on_the_server",
    "portal_params",
    "windowed",
]

#: ⚠ **WHICH PORTAL LISTS TAKE THEIR PAGE IN SQL, AND WHICH TAKE IT IN PYTHON
#: ON THE SERVER — NAMED SO THE EXCEPTION CAN BE COUNTED.** `DEF-RAT-5742` set
#: this precedent two days earlier on Plans & Rates and gave the reason:
#: a derived predicate re-implemented in SQL is a SECOND implementation of one
#: derivation, and two implementations one screen apart is how a list and a
#: detail start disagreeing about the same row (`DEF-387`).
#:
#: ⚠ **BOTH ANSWERS FIX THE DEFECT AND ONLY ONE FIXES THE COST**, which is why
#: the split is written down rather than left to be inferred. `DEF-CWP-5747` is
#: two faults: a PAYLOAD of every row a customer has, and — the one that would
#: have been manufactured by a careless fix — a SEARCH that sees only the page.
#: Applying search, filter and sort on the server over the whole ordered set
#: fixes both; taking the page in SQL as well is what makes the WORK constant.
#:
#: **`readings` is the only one that needed the third**, and the register row
#: says why in one sentence: *"a customer has a dozen bills, and an AMI
#: deployment writes an interval reading per meter per hour"*. The other four
#: are bounded by ONE CUSTOMER'S OWN HISTORY and each has a derived predicate
#: SQL cannot reach without a second implementation:
#:   * `bills` — the *unpaid* chip is `owing > 0`, and owing comes from
#:     `payments.open_bill_position`, never from subtraction here
#:     (`BR-CWP-043`); the search matches the MONTH NAME the browser prints.
#:   * `payments` — a bounce is TWO ROWS anchored at the reversal's date
#:     (`BR-CWP-061`), which is a pairing pass over the whole list.
#:   * `documents` — the rows come from the notifications queue through a
#:     published seam, and may be `None` (unreachable) rather than empty.
#:   * `my-accounts` — every row carries a live balance from the ledger.
SQL_PAGED: dict[str, bool] = {
    "readings": True,
    "bills": False,
    "payments": False,
    "documents": False,
    "my-accounts": False,
}


def portal_params(
    request: Any,
    *,
    allowed_sorts: tuple[str, ...] = (),
    default_sort: str | None = None,
    default_dir: str = "desc",
    allowed_filters: tuple[str, ...] = (),
) -> ListParams:
    """The request's `q/sort/dir/page/per/f.<name>`, parsed by the house parser.

    ⚠ **`default_dir` IS `desc` FOR THIS EDGE, WHICH IS THE OPPOSITE OF THE
    STAFF DEFAULT AND IS RIGHT FOR THE OPPOSITE REASON.** Every portal list
    opens NEWEST FIRST — the bill you just got, the payment you just made, the
    reading taken this morning — and `listTable.tsx` says so in its own words:
    *"clearing returns the list to the order the server sent, which for every
    portal list is newest-first"*. A list whose default is newest-first needs
    `dir` to fall back to `desc`, or `?sort=taken` with no direction opens on
    the OLDEST row (`BR-CUS-1046`, PO 2026-09-10 as extended 2026-09-12).

    ⚠ **IT APPLIES ONLY WHERE THE SORT ITSELF FELL BACK.** An explicit
    `?sort=meter` with no `dir` still opens `asc`, because A→Z is what somebody
    who pressed a name column meant. That is the house parser's rule and this
    function does not re-implement it.
    """
    return parse_list_params(
        request.query_params,
        allowed_sorts=allowed_sorts,
        default_sort=default_sort,
        default_dir=default_dir,
        allowed_filters=allowed_filters,
    )


def windowed(
    key: str,
    params: ListParams,
    fetch: Callable[[ListParams], tuple[list[dict[str, Any]], int]],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The portal list body: `{<key>: [one page], count, page, per, **extra}`.

    `fetch` takes the params and answers `(rows, total)` — it is the SELECTOR
    that takes the page, never this function, which slices nothing and could
    not: it never sees more than one page.

    ⚠ **`BR-SHL-011`'S CLAMP, APPLIED BY RE-ASKING.** A person who types
    `?page=999` into a nine-page list is shown the LAST page, never a blank
    table and never a 4xx. It is one extra `fetch` on that one request, which
    is the price of not knowing the count until the page has been taken.

    ⚠ **AND IT CANNOT LOOP.** The second ask is for a page that the count just
    proved exists, so the clamp is applied once and the result is returned
    whatever it holds — a set that shrank under the reader between the two
    queries gives a short last page rather than a third query.

    ⚠ **NO CAP (`NFR-5`).** Nothing here refuses a page, a size or a row: the
    only bound is `per`, which `clamp_page_size` fits to the IS-2 vocabulary,
    and its top step is 1,000 because that is the vocabulary rather than
    because a list was decided to end there.
    """
    rows, total = fetch(params)
    pages = max(1, math.ceil(total / params.per)) if params.per else 1
    if params.page > pages:
        params = ListParams(
            q=params.q,
            sort=params.sort,
            dir=params.dir,
            page=pages,
            per=params.per,
            filters=params.filters,
        )
        rows, total = fetch(params)
    body: dict[str, Any] = {
        key: rows,
        "count": total,
        "page": params.page,
        "per": params.per,
    }
    for name, value in (extra or {}).items():
        body[name] = value
    return body


def on_the_server(
    rows: list[dict[str, Any]],
    params: ListParams,
    *,
    search: Callable[[dict[str, Any], str], bool] | None = None,
    sorts: dict[str, Callable[[dict[str, Any]], Any]] | None = None,
    filters: dict[str, Callable[[dict[str, Any], str], bool]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Search, filter, sort and slice a whole ordered set **on the server**.

    ⚠ **THIS IS THE PREDICATE THAT USED TO RUN IN THE BROWSER, MOVED ACROSS THE
    WIRE — AND MOVING IT IS THE HALF OF `DEF-CWP-5747` THAT IS NOT ABOUT
    SPEED.** `portal/components/listTable.tsx` held every row and searched,
    chipped, sorted and sliced it. Take the page from the server and leave the
    other three in the browser and each of them silently searches ONE PAGE OF
    N: a customer typing a bill number that is on page 7 is told they have no
    such bill. So all four arrive together, and for these four lists they
    arrive here.

    ⚠ **THE COST IS `O(this customer's own history)` AND THAT IS STATED RATHER
    THAN HIDDEN** — see `SQL_PAGED` above for which lists this is true of and
    why each one's predicate cannot reach SQL without a second implementation
    of a derivation the product already has one of. What it is NOT is
    `O(tenant)`: every one of these reads is already intersected with the
    session's own flat account set in the QUERY (`BR-CWP-010`), so a utility
    with 40,000 accounts costs a customer's page exactly what a utility with
    thirty does.

    ⚠ **`NFR-5` — NOTHING HERE REFUSES A ROW.** No cap, no maximum, no *first
    N*; the only bound is `per`, and a `page` past the end returns empty for
    `windowed` above to clamp.

    ⚠ **THE SORT IS STABLE AND THE UNSORTED ORDER IS THE SELECTOR'S.** Python's
    `sorted` is stable, so rows the key cannot tell apart keep the order the
    selector put them in — which for `payments` is what keeps a bounced payment
    and the row it undoes adjacent (`BR-CWP-061`), and no page boundary can
    separate a pair the sort never separated.
    """
    out = rows
    for name, predicate in (filters or {}).items():
        chosen = params.filters.get(name)
        # `all` is the *no narrowing* chip and never reaches the wire; an
        # unknown value is ignored rather than refused (`BR-SHL-011`).
        if chosen and chosen != "all":
            out = [row for row in out if predicate(row, chosen)]
    needle = (params.q or "").strip().lower()
    if needle and search is not None:
        out = [row for row in out if search(row, needle)]
    key = (sorts or {}).get(params.sort or "")
    if key is not None:
        # ⚠ **`None` SORTS LAST IN BOTH DIRECTIONS, WHICH IS THE BROWSER'S OWN
        # RULE MOVED RATHER THAN CHANGED.** `compareValues` in
        # `portal/components/listTable.tsx` says why: *"a missing date is not
        # 'earliest', it is unknown, and burying it under a descending sort
        # would hide the row"*.
        reverse = params.dir == "desc"
        # ⚠ **`reverse` GOES TO BOTH, AND THE KEY IS WHY.** `sorted(reverse=True)`
        # inverts the WHOLE tuple, absent flag included, so a key that always
        # marked absence with `1` would put every empty cell FIRST under a
        # descending sort. `_sort_key` flips the flag to match, and the two
        # arguments have to agree — which is the one thing a test of this
        # function must pin in BOTH directions.
        out = sorted(out, key=lambda row: _sort_key(key(row), reverse=reverse), reverse=reverse)
    total = len(out)
    start = max(params.page - 1, 0) * params.per
    return out[start : start + params.per], total


def _sort_key(value: Any, *, reverse: bool) -> tuple[int, Any]:
    """`(absent?, comparable)` — so `None` lands last whichever way the list is
    ordered, and numbers compare as numbers while text compares as text."""
    if value is None or value == "":
        # Under `reverse=True` the whole tuple is inverted, so the absent flag
        # has to be inverted with it for `None` to stay at the bottom.
        return (0 if reverse else 1, "")
    if isinstance(value, bool):
        value = int(value)
    if isinstance(value, (int, float)):
        return (1 if reverse else 0, value)
    return (1 if reverse else 0, str(value).lower())


# ── Lifecycle ─────────────────────────────────────────────
# packet: DEF-CWP-5747 — the portal pagination lane, 2026-09-19
# generated: 2026-09-19
# exceptions: the envelope is the portal's NAMED key rather than DRF's
#   `results`, stated above; `next`/`previous` are deliberately not built.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

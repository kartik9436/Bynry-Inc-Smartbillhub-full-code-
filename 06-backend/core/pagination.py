# ── Trace ──────────────────────────────────────────────
# Component: BE-05 list plumbing — pagination + param grammar (B13 §3, W0 kernel lane)
# Contract:  IS-2 as amended (PO 2026-08-09: sizes 50/100/200/500/1000, default 50) ·
#            A11 Addendum r2 item 1 (`per` clamps to the set) · 11b §3 G5 (grammar,
#            pagination mandatory on every list) · B8 layering (selectors read path)
# Rules:     BR-SHL-011 (URL grammar q/sort/dir/page/per/f.‹name›; invalid values fall
#            back or clamp, NEVER error)
# Tests:     06-backend/tests/test_be05_pagination.py
# Impacts:   every list endpoint (DRF DEFAULT_PAGINATION_CLASS) · FE-02 DataTable params
# ───────────────────────────────────────────────────────
"""BE-05 — the ONE pagination class + list-param parser every list endpoint uses.

Grammar (BR-SHL-011, shared with the frontend URL state):
    q / sort / dir / page / per / f.<name>
Unknown or invalid values FALL BACK or CLAMP — a list URL can never 4xx over
its params. Page sizes on screen and API are the same set: 50 / 100 / 200 /
500 / 1000, default 50 (PO ruling 2026-08-09, IS-2 as amended).

Registered as REST_FRAMEWORK["DEFAULT_PAGINATION_CLASS"], so pagination is on
by default for every list (checklist D / 11b G5) — an endpoint has to go out
of its way to be unbounded, and none may.

ETag/304 plumbing for lookup GETs (11b G6) is NOT here — it lands with the
lookup/reference-data endpoints that serve cacheable vocabularies.
"""

from dataclasses import dataclass, field
from typing import Any

from rest_framework.pagination import PageNumberPagination

# IS-2 as amended: the one page-size vocabulary, smallest first.
PAGE_SIZES: tuple[int, ...] = (50, 100, 200, 500, 1000)
DEFAULT_PAGE_SIZE = 50
SORT_DIRECTIONS = ("asc", "desc")
DEFAULT_SORT_DIRECTION = "asc"
FILTER_PREFIX = "f."


def clamp_page_size(raw: Any) -> int:
    """`per` clamps to the PAGE_SIZES set (A11 r2 item 1), never errors.

    Non-numeric/absent → default 50. A number between steps clamps DOWN to the
    largest allowed size not above it (75→50, 300→200); above the top → 1000;
    below the bottom → 50. Clamping never grants more rows than asked for.
    """
    try:
        requested = int(str(raw))
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    if requested < PAGE_SIZES[0]:
        return PAGE_SIZES[0]
    chosen = PAGE_SIZES[0]
    for size in PAGE_SIZES:
        if size <= requested:
            chosen = size
    return chosen


class StandardPagination(PageNumberPagination):
    """THE list pagination: ?page=N&per=SIZE, DRF envelope (count/next/previous/results)."""

    page_size = DEFAULT_PAGE_SIZE
    page_query_param = "page"
    page_size_query_param = "per"
    max_page_size = PAGE_SIZES[-1]

    def get_page_size(self, request: Any) -> int:
        return clamp_page_size(request.query_params.get(self.page_size_query_param))

    def get_page_number(self, request: Any, paginator: Any) -> int:
        # BR-SHL-011 "never error": a garbage or out-of-range page clamps into
        # [1, last] instead of DRF's default 404-on-invalid-page.
        raw = request.query_params.get(self.page_query_param)
        try:
            number = int(str(raw))
        except (TypeError, ValueError):
            number = 1
        last = max(paginator.num_pages, 1)
        return min(max(number, 1), last)


#: OQ-306 CLOSED (PO 2026-10-02, verbatim: *"Allow several services at
#: once."*) — a filter that may carry SEVERAL values carries them as ONE
#: comma-joined string: `f.service=water,sewer`. The string shape is what
#: `ListParams.filters` and the front end's `TableRequestState.filters` already
#: hold, so nothing typed as `dict[str, str]` changes; a row matches when its
#: value is ANY of the listed ones (OR within the dimension, AND across them).
MULTI_VALUE_SEPARATOR = ","


def _one_filter_string(query_params: Any, key: str) -> str:
    """The value of one `f.<name>` param, REPEATS folded into the comma list.

    `f.service=water&f.service=sewer` (the repeatable form `billing/api.py`
    already reads for a run's scope) and `f.service=water,sewer` (the form the
    shared filter bar sends) mean the same thing here. A plain mapping in a unit
    test has no `getlist`, and its single value is taken as it is.
    """
    getlist = getattr(query_params, "getlist", None)
    values = [str(v) for v in getlist(key)] if callable(getlist) else []
    if len(values) > 1:
        return MULTI_VALUE_SEPARATOR.join(values)
    return str(query_params.get(key))


def filter_values(raw: Any) -> list[str]:
    """OQ-306 — the values ONE filter asked for, in order, de-duplicated.

    `"water,sewer"` -> `["water", "sewer"]` · `"water"` -> `["water"]` ·
    `""` / `None` -> `[]` (no filter — the All chip). Blank pieces from a
    stray comma are dropped rather than matched against an empty code.

    A list or tuple is accepted as well, so a caller that already holds several
    values (`getlist`) and one that holds the comma string ask one question.
    The caller applies `__in` (or `in`) to what comes back; an EMPTY result
    means *not filtered*, never *match nothing*.
    """
    if raw is None:
        return []
    pieces = (
        [str(one) for one in raw]
        if isinstance(raw, (list, tuple, set))
        else str(raw).split(MULTI_VALUE_SEPARATOR)
    )
    out: list[str] = []
    for piece in pieces:
        for part in piece.split(MULTI_VALUE_SEPARATOR):
            value = part.strip()
            if value and value not in out:
                out.append(value)
    return out


@dataclass(frozen=True)
class ListParams:
    """Parsed BR-SHL-011 params, ready for a selector. Filters hold only
    declared names — an undeclared f.* param is silently ignored, never an
    error and never a query column a client picked."""

    q: str = ""
    sort: str | None = None
    dir: str = DEFAULT_SORT_DIRECTION
    page: int = 1
    per: int = DEFAULT_PAGE_SIZE
    filters: dict[str, str] = field(default_factory=dict)


def parse_list_params(
    query_params: Any,
    *,
    allowed_sorts: tuple[str, ...] = (),
    default_sort: str | None = None,
    default_dir: str = DEFAULT_SORT_DIRECTION,
    allowed_filters: tuple[str, ...] = (),
) -> ListParams:
    """Parse q/sort/dir/page/per/f.<name> with fall-back-or-clamp semantics.

    Per-screen vocabulary comes from the screen's capability-matrix row
    (BR-SHL-010): the endpoint declares allowed_sorts / allowed_filters and
    its default sort; everything outside that vocabulary falls back.

    ⚠ **`default_dir` BELONGS TO `default_sort` AND TO NOTHING ELSE
    (`BR-CUS-1046`, PO 2026-09-10 as extended 2026-09-12).** A list whose
    default is *newest first* needs `dir` to fall back to `desc` when nobody
    has chosen — otherwise `?sort=created` with no `dir` opens on the OLDEST
    row, which is the exact inversion the ruling exists to remove.

    It applies **only when the sort itself fell back**, which is the case where
    no choice was made at all. An explicit, recognised `?sort=name` with no
    `dir` still opens `asc`: A→Z is what a clerk who picked a name column
    meant, and a screen-wide `desc` would hand them Z→A. So the pair that
    travels together is (default sort, default direction), exactly as the pair
    a clerk clicks travels together.

    An explicitly supplied `dir` always wins, in both cases — it is the clerk's
    choice, and `BR-CUS-1046`'s second clause is that it must.
    """
    q = str(query_params.get("q", "") or "").strip()

    raw_sort = query_params.get("sort")
    sort_given = raw_sort in allowed_sorts
    sort = raw_sort if sort_given else default_sort  # unknown sort → default

    raw_dir = str(query_params.get("dir", "") or "").lower()
    if raw_dir in SORT_DIRECTIONS:
        direction = raw_dir
    elif sort_given:
        direction = DEFAULT_SORT_DIRECTION
    else:
        direction = default_dir if default_dir in SORT_DIRECTIONS else DEFAULT_SORT_DIRECTION

    try:
        page = max(int(str(query_params.get("page"))), 1)
    except (TypeError, ValueError):
        page = 1

    per = clamp_page_size(query_params.get("per"))

    filters: dict[str, str] = {}
    for key in query_params:
        if not key.startswith(FILTER_PREFIX):
            continue
        name = key[len(FILTER_PREFIX) :]
        if name in allowed_filters:  # undeclared filter names are ignored
            filters[name] = _one_filter_string(query_params, key)

    return ListParams(q=q, sort=sort, dir=direction, page=page, per=per, filters=filters)


# ── The ORDER BY a (sort, dir) pair means (BR-CUS-1046 · NFR-3) ────────────
#: A sort name → the model fields it orders by, each written ASCENDING.
#: `desc` flips every term, so a list's two directions cannot drift apart.
SortColumns = dict[str, tuple[Any, ...]]


def _flip(term: Any) -> Any:
    """One order term, reversed — strings by their `-` prefix, expressions by
    rebuilding the `OrderBy` with the opposite direction.

    ⚠ **NULLS STAY AT THE SAME END IN BOTH DIRECTIONS, ON PURPOSE.** A row with
    no date is not the most urgent thing on a worklist and it is not the least
    either: it is the one blocked on a human. `connection_reads` puts it last
    and says why; flipping the direction must not quietly move it to the top.
    """
    from django.db.models.expressions import OrderBy

    if isinstance(term, str):
        return term[1:] if term.startswith("-") else "-" + term
    if isinstance(term, OrderBy):
        return OrderBy(
            term.expression,
            descending=not term.descending,
            nulls_first=term.nulls_first,
            nulls_last=term.nulls_last,
        )
    raise TypeError(f"cannot reverse order term {term!r}")  # pragma: no cover


def order_terms(sort: str | None, direction: str, *, columns: SortColumns, default: str) -> list:
    """THE `order_by(*…)` args for a list's (sort, dir) pair — one implementation.

    ⚠ **WHY THIS IS SHARED PLUMBING AND NOT SIX COPIES (`BR-CUS-1046`, PO
    2026-09-12: *"All eight open newest-first and the six gain a sort
    control"*).** Six worklists gained a server-side sort in one commit. Six
    hand-rolled `if sort == …` ladders is six places for the descending branch
    to disagree with the ascending one, and the standing PO instruction of
    2026-09-12 is *"dont create duplcate code"*.

    ⚠ **EVERY SORT CARRIES A TIEBREAK AND THAT IS THE CALLER'S JOB.** A page is
    a window over an ORDER; if the order is not total, two rows that compare
    equal may swap between page 1 and page 2 and a clerk sees one row twice and
    another never. So every tuple in `columns` ends with a unique column —
    `id` on every list here — and this function never adds one, because a
    silent tiebreak is a guarantee nobody can read.

    An unknown sort falls back to `default` rather than erroring (BR-SHL-011).
    """
    name = sort if sort in columns else default
    terms = columns[name]
    if str(direction).lower() != "desc":
        return list(terms)
    return [_flip(term) for term in terms]


def prepaged(
    request: Any,
    params: ListParams,
    fetch: Any,
    extra: dict[str, Any] | None = None,
) -> Any:
    """The DRF envelope over a page the SELECTOR or READ MODEL already took.

    `fetch(params) -> (rows, total)`. `NFR-3`.

    ⚠ **THIS FUNCTION IS HERE BECAUSE `apps/rating/api._prepaged`'S OWN
    DOCSTRING SAID IT SHOULD BE, AND NAMED THE TRIGGER.** Verbatim: *"THIS IS A
    SECOND COPY OF `customers._prepaged` AND THAT IS DELIBERATE BUT NOT
    DESIRABLE. Its home is `core/pagination.py`, beside `StandardPagination`
    and `order_terms` … a third copy should trigger it instead of being
    written."* `DEF-LED-6493` is that third caller, so the move is taken rather
    than the copy.

    ⚠ **THE THREE EXISTING COPIES ARE NOT CONVERTED BY THIS COMMIT, AND THAT IS
    A DECISION RATHER THAN AN OMISSION.** They carry THREE different signatures
    — `customers` takes `(request, rows, total, params, extra, refetch)`,
    `metering` takes `(request, rows, total, params, refetch, extra)` and
    `rating` takes `(request, params, fetch, extra)` — so converting them is a
    change to three other modules' endpoints with three other modules' suites to
    re-prove, inside a phase whose own plan says *"one team does not silently do
    another's migration"* (`P1.13`). The decision log of 2026-09-24 records it,
    and this docstring is the pointer the next lane reads.

    ⚠ **THE ENVELOPE IS BYTE-FOR-BYTE THE ONE EVERY OTHER LIST SERVES** —
    `count` / `next` / `previous` / `results`, in that order, with the page
    links built by DRF's own `replace_query_param` / `remove_query_param`, so
    `?page=2` is formed here exactly as it is on the thirty endpoints that still
    hand the paginator a queryset. `extra` is appended AFTER the four keys.

    ⚠ **`page` IS RE-CLAMPED HERE AND NOT ONLY IN THE PARSER (`BR-SHL-011`).**
    `parse_list_params` clamps `page` to >= 1 but cannot know the LAST page — it
    has counted nothing yet — and `StandardPagination.get_page_number`, which
    does that clamp for the queryset path, is not in this path at all. So it is
    done here, and the page is FETCHED AGAIN when the clamp moved it: serving
    the rows we were already handed would answer `?page=999` on a three-page
    list with a blank table and a `previous` link to page 998. Clamp, never
    error.
    """
    import math
    from dataclasses import replace

    from rest_framework.response import Response
    from rest_framework.utils.urls import remove_query_param, replace_query_param

    rows, total = fetch(params)
    per = max(params.per, 1)
    pages = max(1, math.ceil(total / per)) if total else 1
    number = min(max(params.page, 1), pages)
    if number != params.page:
        rows, total = fetch(replace(params, page=number))
        pages = max(1, math.ceil(total / per)) if total else 1
    url = request.build_absolute_uri()
    following = replace_query_param(url, "page", number + 1) if number < pages and total else None
    if number > 2:
        preceding = replace_query_param(url, "page", number - 1)
    elif number == 2:
        preceding = remove_query_param(url, "page")
    else:
        preceding = None
    body: dict[str, Any] = {
        "count": total,
        "next": following,
        "previous": preceding,
        "results": rows,
    }
    for key, value in (extra or {}).items():
        body[key] = value
    return Response(body)


# ── Lifecycle ─────────────────────────────────────────────
# packet: BE-05@87ece49 (component packet — B13 §3 row + signed contracts; hash = sha256/7 of B12)
# generated: 2026-08-09 by story-coder v1 (W0 kernel lane, B13 rows BE-01..BE-05)
# checklist: A✔ B✔ C✔ D✔ E=deferred(no-frontend-half) F✔ G✔ H=deferred(PO 2026-08-08)
# gates: ruff✔ black✔ pytest tests/test_be05_pagination.py 26/26✔ · suite 92/92✔ · run_gates 10-PASS/0-FAIL✔ · trace_lint✔ · mypy NOT run — B8 strict scope is services/engines
# exceptions: none stubbed; E2-candidates reported to the PO batch via the build report (404/40x codes absent from the B12 §3 catalog · BR-AUD-018 attempt-row event code pending SC-3 · G7 guard list lacks core/tenancy.py)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` wave 4 — the JOINING READ behind R4 Bill Run
#           Readiness. Drawing read as an IMAGE (B14 rule 42): p049 (and the
#           three rows that spill onto p050) of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 3.0x by
#           `10-scripts/pdf/pdf_render.py`.
# Story:    R4 `bill_run_readiness` — Billing › Readiness · bills + reads ·
#           **Posting date** (`reports/migrations/0003_seed_catalogue.py`).
# Rules:    `BR-REP-041` (the LATEST PREPARED RUN for the cycle; where none
#           exists the absence is STATED, never substituted) · `BR-REP-060`
#           (ROUTE and USAGE are drawn and NULL with their reason, and the Route
#           FILTER is not offered — `OQ-REP-12768`) · `BR-REP-061` (HELD counts
#           OUTSTANDING breaks; NO READ is counted by STAGE) · `BR-REP-024` (a
#           figure that cannot be produced is NULL with its reason, never a 0) ·
#           `BR-REP-001` (a money report names its basis) · `BR-BIL-053` /
#           `BR-BIL-037` / `BR-BIL-040` (a break's stage vocabulary) ·
#           `BR-TEN-043` (the business date is an argument, never a clock) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · hard rule 3 (consumption
#           always with an explicit unit) · hard rule 4 (this file writes
#           nothing) · B14 rule 31 (no database id is ever a visible value).
# Tests:    06-backend/tests/test_rep_p6w4_bill_run_readiness.py
# Impacts:  apps/billing/customers_seam.primary_contact_names_for (the CUSTOMER
#           column, ONE batched read for the whole page) ·
#           apps/reports/report_seams.py (the seam) ·
#           apps/reports/queries.py (the per-key viewer, its stream and its
#           column_meta) · apps/reports/exports.py (the export resource —
#           otherwise a live Download button over a 404)
# ───────────────────────────────────────────────────────
"""**R4 BILL RUN READINESS — one row is one HELD ACCOUNT**, before the run.

p049's own footnote is the specification of what this report is for:

    *"Run before the bill run, not after. The 49 held accounts are the whole
    point of the screen — they are what a clerk fixes in the twenty minutes
    before issuing 1,198 bills."*

So the ROWS are the accounts that are stuck, and the TILES are the population
they were drawn from. A report that listed all 1,247 accounts in the cycle
would bury the 49 that need a person.

═══════════════════════════════════════════════════════════════════════════════
THE SPINE IS `bill_run_breaks`, WHICH IS PERSISTED — `BR-REP-041`
═══════════════════════════════════════════════════════════════════════════════
⚠ **NOT `selectors.prepared_for`, AND ITS OWN DOCSTRING SAYS WHY**: that is
*"recomputed on every call and cached nowhere"*. Recomputing a prepare pass
inside a READ would make opening a report re-read every meter, plan and account
in the cycle — the cost of the bill run itself, paid by a clerk pressing a
report card. `bill_run_breaks` exists precisely because the break list did not
survive a refresh (`CR-051` task 5), and it is indexed on `(tenant, bill_run)`.

**PREPARED means the pass has left something behind.** A run is prepared when it
carries a `findings_summary` (the background findings job counted it) or when it
has break rows (calculate ran, inline or as a job). The LATEST such run for the
cycle is the one shown. **Where no run for the cycle is prepared, the absence is
STATED** — `BR-REP-041`, and nothing is substituted: no empty table reading as a
clean result, no invented run.

═══════════════════════════════════════════════════════════════════════════════
TWO OF p049's SIX COLUMNS ARE DRAWN AND EMPTY — `BR-REP-060`
═══════════════════════════════════════════════════════════════════════════════
⚠ **AND IT IS ONE REASON RATHER THAN TWO: AN ACCOUNT HAS NO SINGLE ROUTE AND NO
SINGLE USAGE FIGURE.** `metering.RouteMembership`'s own docstring:

    *"CR-006 gives a route one [service], and a house on water AND gas is on two
    routes"*

— the table carries two partial unique constraints so that it can. USAGE is the
same fact in the other unit: hard rule 3 puts an explicit unit on every
consumption figure and the brief's own p062 note forbids summing quantities
across services, *"because gallons plus kilowatt-hours is not a number"*.

**So this is not a missing read; it is a missing DECISION** — which service's
route wins — and that is `OQ-REP-12768`, open, recommendation recorded, nothing
blocked. Building a `routes_for_accounts` seam would not have answered it: it
would have forced a lane to choose in a helper function.

⚠ **THE COLUMNS STAY AND THE FILTER GOES, AND THE ASYMMETRY IS DELIBERATE.**
`BR-REP-024` keeps a drawn figure and states its absence — the same posture R34
gives `paid` and R43 gives `target`. A FILTER over a column that is NULL on
every row is a live control that cannot work: hard-won law 2's mirror, on a
brand-new screen. A column that states its own absence is honest; a chip that
offers to act on that absence is a lie.

═══════════════════════════════════════════════════════════════════════════════
WHAT THIS FILE DOES NOT DO
═══════════════════════════════════════════════════════════════════════════════
* **It writes nothing.** Hard rule 4 — a break's `resolution` is a clerk's act on
  the run screen, never a report's.
* **It caps nothing.** `per=None` is the whole filtered set; the CALLER clamps.
  `NFR-5`.
* **It counts the tiles in SQL over the WHOLE filtered set**, never over the
  page, so the tiles foot to the report whether a page is cut or not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Count, Q

from apps.billing import customers_seam
from apps.billing.models import BillRun, BillRunBreak
from core import tenancy as core_tenancy

#: `BR-REP-001` — R4's eyebrow on p049 reads *Posting date*.
BASIS_POSTING = "posting"

#: `BR-REP-061` — the stage every read-shaped failure already maps onto
#: (`runs.STAGE_BY_REASON`). Counted by STAGE and never by a hand-kept list of
#: reason codes: a second copy of that map would drift the day a reason moved
#: stage, and a key missing from a hand-kept map is indistinguishable from a
#: deliberately absent one. That is `DEF-REP-6937` exactly.
NO_READ_STAGE = "measure-consumption"

#: The sorts this read HONOURS. Offering a caret this query will not reorder is
#: hard-won law 2's mirror, so the viewer publishes this tuple rather than
#: typing its own.
READINESS_SORTS: tuple[str, ...] = ("account", "customer", "check", "detail")
READINESS_DEFAULT_SORT = "account"
READINESS_DEFAULT_DIRECTION = "asc"

#: A fetch buffer for the export, not a cap (`NFR-5`). It also bounds the
#: batched customer-name read per chunk, which is why the export is chunked.
STREAM_CHUNK = 2_000

#: ── THE NAMED ABSENCES, `BR-REP-024` ───────────────────────────────────────
GAP_ROUTE_IS_NOT_SINGLE_VALUED = {
    "code": "route_is_not_single_valued_per_account",
    "br_ref": "BR-REP-060 · OQ-REP-12768 · p049",
    "detail": (
        "p049 draws one ROUTE cell per account. A route belongs to ONE SERVICE "
        "(`metering.RouteMembership`: \"a house on water AND gas is on two routes\"), "
        "so a multi-service account has one route per service and no single route. "
        "Which service's route is *the* route is OQ-REP-12768 and is the Product "
        "Owner's to rule; a lane choosing one in a helper would be minting a product "
        "rule. Served as NULL with this reason, and the drawn Route FILTER is NOT "
        "offered — a chip over a column empty on every row is a control that cannot work."
    ),
}

GAP_USAGE_IS_NOT_SUMMABLE = {
    "code": "usage_is_not_summable_across_services",
    "br_ref": "BR-REP-060 · OQ-REP-12768 · CLAUDE.md hard rule 3 · p049 · p062",
    "detail": (
        "p049 draws one USAGE cell per account (`14,900 gal`). Hard rule 3 puts an "
        "explicit unit on every consumption figure and the brief's own p062 note says "
        "quantities are never summed across services, \"because gallons plus "
        "kilowatt-hours is not a number\". A held account taking water and gas has no "
        "single usage figure, and the account is held precisely because a read is "
        "missing or unusable. Served as NULL with this reason."
    ),
}

GAP_FINDINGS_PASS_HAS_NOT_RUN = {
    "code": "findings_pass_has_not_run_on_this_run",
    "br_ref": "BR-REP-061 · BR-REP-024 · p049",
    "detail": (
        "ACCOUNTS IN CYCLE and READY TO BILL are `bill_runs.findings_summary`, which "
        "only the background findings job writes. A run calculated inline carries none, "
        "so both tiles are NULL with this reason rather than 0. A `0` would say the "
        "cycle is empty; the truth is that nobody counted."
    ),
}

GAP_NO_PREPARED_RUN = {
    "code": "no_bill_run_prepared_for_this_cycle",
    "br_ref": "BR-REP-041 · p049",
    "detail": (
        "The report is opened for a CYCLE and readiness belongs to a RUN. No run for "
        "this cycle has been prepared, so there is nothing to report — stated rather "
        "than substituted, because an empty table reads as a clean result and this "
        "screen's whole purpose is the accounts that are NOT clean."
    ),
}

GAP_CUSTOMER_NAMES_UNWIRED = {
    "code": "customer_names_unwired",
    "br_ref": "BR-REP-024 · B1",
    "detail": (
        "The CUSTOMER column is read through `billing.customers_seam."
        "primary_contact_names_for`, one batched call for the page. The seam answered "
        "None, which means customers cannot answer rather than that the accounts have "
        "no holder. Names are NULL with this reason; the ACCOUNT column is unaffected "
        "because `bill_run_breaks.account_no` is stored as the run saw it."
    ),
}


@dataclass(frozen=True)
class ReadinessRow:
    """One HELD account, in p049's own column order.

    ⚠ **`route` AND `usage` ARE FIELDS RATHER THAN OMISSIONS**, so the column can
    be drawn with an em-dash and its reason rather than vanishing from a report
    the drawing shows it on (`BR-REP-060`). Each carries its own `_absence`
    beside it, because a NULL with no reason beside it is indistinguishable from
    a value nobody wrote.

    ⚠ **`account` IS `bill_run_breaks.account_no`, STORED AND NOT JOINED** — the
    model's own docstring: it is the label the clerk reads, stored AS THE RUN SAW
    IT, so a renumbered account does not silently retitle a break raised against
    the old number. It is also why B14 rule 31 is satisfied structurally here:
    the visible value is a business number and never a database id.
    """

    account: str
    customer: str | None
    customer_absence: str | None
    route: None
    route_absence: str
    check: str
    detail: str | None
    usage: None
    usage_absence: str
    unit: None
    retryable: bool


def _tenant_id() -> Any:
    return core_tenancy.current_tenant_id()


def prepared_run_for_cycle(cycle: Any) -> BillRun | None:
    """`BR-REP-041`'s own sentence, in SQL: the LATEST PREPARED run for a cycle.

    **PREPARED = the pass left something behind** — a `findings_summary` the
    background job wrote, or break rows a calculate wrote. A `draft` run nobody
    has calculated is not prepared and is correctly skipped: reporting readiness
    from it would print four zeroes and 0 held over a cycle nobody has looked at.

    ⚠ **THE ORDER IS TOTAL.** Two runs created in the same microsecond would
    otherwise make *latest* a coin toss, and a coin toss decides which HELD count
    a clerk acts on before issuing bills. `id` breaks the tie — uuid7, so it is
    time-ordered and the tie-break agrees with the timestamp rather than fighting
    it.
    """
    if cycle in (None, ""):
        return None
    runs = BillRun.objects.filter(tenant_id=_tenant_id(), cycle_id=cycle)
    prepared = runs.filter(
        Q(findings_summary__isnull=False) | Q(id__in=_run_ids_with_breaks(cycle))
    )
    return prepared.order_by("-created_at", "-id").first()


def _run_ids_with_breaks(cycle: Any) -> Any:
    """Run ids for this cycle that have at least one break row.

    A values-list subquery rather than a Python set: the breaks table is per
    (run, account) and a tenant's history of one cycle can hold many runs, so
    pulling ids into Python would be a read that grows with the tenant for a
    membership test SQL already answers.
    """
    return BillRunBreak.objects.filter(
        tenant_id=_tenant_id(), bill_run__cycle_id=cycle
    ).values("bill_run_id")


def _outstanding(run: BillRun, *, check: str | None = None) -> Any:
    """The HELD accounts of a run — `BR-REP-061`.

    `resolution IS NULL` is `BillRunBreak`'s own vocabulary (*"NULL =
    outstanding"*). A break a clerk has already resolved is not held, and
    counting it would put a stale number on the one screen whose whole purpose is
    the twenty minutes before the run.
    """
    qs = BillRunBreak.objects.filter(
        tenant_id=_tenant_id(), bill_run_id=run.id, resolution__isnull=True
    )
    if check:
        qs = qs.filter(Q(stage=check) | Q(reason=check))
    return qs


def _ordered(qs: Any, sort: str | None, direction: str) -> Any:
    """p049's sorts, in SQL. An unknown sort falls back; it never raises.

    The column names are the READ's, not the screen's: `account` is
    `account_no`, `check` is the stage the clerk reads. `id` is appended to every
    ordering so a page boundary cannot repeat or drop a row when two breaks share
    a sort value — the paging fault that has no symptom until the second page.
    """
    column = {
        "account": "account_no",
        "customer": "account_no",  # the name is not a column here; see `_names_for`
        "check": "stage",
        "detail": "detail",
    }.get(sort or READINESS_DEFAULT_SORT, "account_no")
    prefix = "-" if str(direction or "").lower() == "desc" else ""
    return qs.order_by(f"{prefix}{column}", f"{prefix}id")


def _names_for(rows: list[BillRunBreak]) -> tuple[dict[str, str | None], bool]:
    """CUSTOMER for the whole page in ONE batched seam call (B1).

    ⚠ **`None` FROM THE SEAM MEANS *CUSTOMERS CANNOT ANSWER*, NEVER *THERE ARE NO
    HOLDERS*** — `BR-REP-024`'s exact distinction, and `DEF-075`'s: a null read
    as "nothing" once re-denominated a tenant's books.
    """
    ids = [str(row.account_id) for row in rows if row.account_id]
    if not ids:
        return {}, True
    found = customers_seam.primary_contact_names_for(ids)
    if found is None:
        return {}, False
    return {str(key): value for key, value in found.items()}, True


def _shape(row: BillRunBreak, names: dict[str, str | None], wired: bool) -> ReadinessRow:
    """One break as p049 draws it.

    ⚠ **`check` IS THE STAGE AND `detail` IS THE SENTENCE, UNEDITED** —
    `BR-SHL-020`. p049 draws *No read* over *Last read 12 Aug*: the first is what
    kind of problem it is and the second is the fact a clerk acts on. The stage is
    billing's own vocabulary, so the screen renders it into its own language
    (B14 rule 35) and this file composes no English.
    """
    key = str(row.account_id) if row.account_id else ""
    return ReadinessRow(
        account=row.account_no,
        customer=names.get(key) if wired else None,
        customer_absence=None if wired else GAP_CUSTOMER_NAMES_UNWIRED["code"],
        route=None,
        route_absence=GAP_ROUTE_IS_NOT_SINGLE_VALUED["code"],
        check=row.stage or row.reason,
        detail=row.detail,
        usage=None,
        usage_absence=GAP_USAGE_IS_NOT_SUMMABLE["code"],
        unit=None,
        retryable=bool(row.retryable),
    )


def _tiles(run: BillRun | None, *, check: str | None) -> dict[str, Any]:
    """p049's four tiles — `BR-REP-061`.

    ⚠ **HELD AND NO READ ARE COUNTED IN ONE QUERY OVER THE WHOLE FILTERED SET**,
    never over the page, so the tiles foot to the report whether a page is cut or
    not. ⚠ **ACCOUNTS IN CYCLE AND READY TO BILL COME FROM `findings_summary`
    AND ARE NULL WHERE IT IS ABSENT** — a `0` there would say the cycle is empty
    when the truth is that nobody counted.
    """
    if run is None:
        return {
            "accounts_in_cycle": None,
            "accounts_in_cycle_absence": GAP_NO_PREPARED_RUN["code"],
            "ready_to_bill": None,
            "ready_to_bill_absence": GAP_NO_PREPARED_RUN["code"],
            "ready_pct": None,
            "ready_pct_absence": GAP_NO_PREPARED_RUN["code"],
            "held": None,
            "held_absence": GAP_NO_PREPARED_RUN["code"],
            "no_read": None,
            "no_read_absence": GAP_NO_PREPARED_RUN["code"],
        }
    counted = _outstanding(run, check=check).aggregate(
        held=Count("id"),
        no_read=Count("id", filter=Q(stage=NO_READ_STAGE)),
    )
    summary = run.findings_summary or {}
    accounts = summary.get("accounts")
    ready = summary.get("ready")
    absent = None if summary else GAP_FINDINGS_PASS_HAS_NOT_RUN["code"]
    return {
        "accounts_in_cycle": accounts,
        "accounts_in_cycle_absence": absent,
        "ready_to_bill": ready,
        "ready_to_bill_absence": absent,
        "ready_pct": _ready_pct(ready, accounts),
        "ready_pct_absence": absent,
        "held": counted["held"],
        "held_absence": None,
        "no_read": counted["no_read"],
        "no_read_absence": None,
    }


def _ready_pct(ready: Any, accounts: Any) -> float | None:
    """p049's `96%` sub-line under READY TO BILL.

    Returns None rather than 0 on a cycle of no accounts: a divide by zero is
    not `0%`, it is *no answer*, and `BR-REP-024` forbids the plausible number.
    """
    try:
        total = int(accounts)
        done = int(ready)
    except (TypeError, ValueError):
        return None
    if total <= 0:
        return None
    return round(done * 100.0 / total, 6)


def bill_run_readiness(
    *,
    cycle: Any = None,
    check: str | None = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = READINESS_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R4, ONE PAGE. One row per HELD ACCOUNT, paged and sorted in SQL.

    `per=None` is the whole filtered set. The CALLER clamps `per`; this function
    invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `bill_run_readiness_stream()`** — no `page`, no
    `per`. Two functions and never a flag.
    """
    run = prepared_run_for_cycle(cycle)
    tiles = _tiles(run, check=check)

    problems: list[dict[str, Any]] = [
        dict(GAP_ROUTE_IS_NOT_SINGLE_VALUED),
        dict(GAP_USAGE_IS_NOT_SUMMABLE),
    ]
    if run is None:
        problems.append(dict(GAP_NO_PREPARED_RUN))
        return _payload(run, tiles, (), problems, page=1, per=per, pages=1, total=0)

    if not (run.findings_summary or {}):
        problems.append(dict(GAP_FINDINGS_PASS_HAS_NOT_RUN))

    held = _outstanding(run, check=check)
    ordered = _ordered(held, sort, direction)
    total_rows = tiles["held"] or 0

    served_page = max(1, int(page or 1))
    if per is None:
        window = ordered
        pages = 1
    else:
        size = max(1, int(per))
        pages = max(1, -(-total_rows // size)) if total_rows else 1
        served_page = min(served_page, pages)
        offset = (served_page - 1) * size
        window = ordered[offset : offset + size]

    materialised = list(window)
    names, wired = _names_for(materialised)
    if materialised and not wired:
        problems.append(dict(GAP_CUSTOMER_NAMES_UNWIRED))
    shaped = tuple(_shape(row, names, wired) for row in materialised)
    return _payload(
        run, tiles, shaped, problems, page=served_page, per=per, pages=pages, total=total_rows
    )


def _payload(
    run: BillRun | None,
    tiles: dict[str, Any],
    rows: tuple[ReadinessRow, ...],
    problems: list[dict[str, Any]],
    *,
    page: int,
    per: int | None,
    pages: int,
    total: int,
) -> dict[str, Any]:
    """The wire shape, built once so the page and the stream cannot disagree."""
    return {
        "basis": BASIS_POSTING,
        # The report is opened for a CYCLE and not a date range (p049), so the
        # window is the RUN's period rather than something a clerk typed.
        "window": {
            "start": getattr(run, "period_start", None),
            "end": getattr(run, "period_end", None),
        },
        # ⚠ **NO CURRENCY, AND THAT IS NOT AN OVERSIGHT.** R4 carries no money
        # column at all — it is a list of accounts that could not be drafted. A
        # currency on a report with nothing to denominate is payload nothing
        # draws (hard-won law 2), and a renderer that found one would be entitled
        # to print a symbol beside a count.
        "currency": None,
        "grain": "one held account of the latest prepared run for the cycle",
        "run_no": getattr(run, "run_no", None),
        "rows": rows,
        "totals": {
            "accounts_in_cycle": tiles["accounts_in_cycle"],
            "ready_to_bill": tiles["ready_to_bill"],
            "ready_pct": tiles["ready_pct"],
            "held": tiles["held"],
            "no_read": tiles["no_read"],
        },
        "absences": {
            "accounts_in_cycle": tiles["accounts_in_cycle_absence"],
            "ready_to_bill": tiles["ready_to_bill_absence"],
            "ready_pct": tiles["ready_pct_absence"],
            "held": tiles["held_absence"],
            "no_read": tiles["no_read_absence"],
        },
        "additivity": {
            # One account contributes once — a break is unique on (run, account)
            # by `uq_bill_run_breaks_once`, so HELD is a true count of accounts.
            "held": "full",
            "no_read": "full",
            # As-of counts of a POPULATION, not of this report's rows.
            "accounts_in_cycle": "non",
            "ready_to_bill": "non",
            # A percentage is never summed.
            "ready_pct": "non",
        },
        "page": page,
        "per": per,
        "pages": pages,
        "total": total,
        "problems": tuple(problems),
    }


def bill_run_readiness_stream(
    *,
    cycle: Any = None,
    check: str | None = None,
    sort: str | None = None,
    direction: str = READINESS_DEFAULT_DIRECTION,
) -> Any:
    """EVERY row of R4, from a generator — no `page`, no `per`.

    ⚠ **CHUNKED, AND THE CHUNK IS WHAT MAKES THE NAME READ BATCHED.** Without it
    the export would either hold every break row in memory or ask customers for
    one name per row, which is the N+1 that only shows up on the tenant nobody
    tested on.
    """
    run = prepared_run_for_cycle(cycle)
    if run is None:
        return
    ordered = _ordered(_outstanding(run, check=check), sort, direction)
    offset = 0
    while True:
        chunk = list(ordered[offset : offset + STREAM_CHUNK])
        if not chunk:
            return
        names, wired = _names_for(chunk)
        for row in chunk:
            yield _shape(row, names, wired)
        offset += STREAM_CHUNK

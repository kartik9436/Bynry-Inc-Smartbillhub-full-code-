# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — the JOINING READ behind R23 Account
#           Activity. Drawings read as IMAGES (B14 rule 42): p059 (the heading
#           and eyebrow) and p060 (the table, the tiles and the warning),
#           rendered at 2.6x by `10-scripts/pdf/pdf_render.py`.
# Story:    R23 `account_activity` — Customers › Accounts · **Event date**
#           (`reports/migrations/0003_seed_catalogue.py` line 231).
# Rules:    CLAUDE.md hard rule 1 (tenant scoping — `tenant_id` on every
#           queryset, RLS FORCE underneath) · hard rule 8 (an address is
#           walked to `premises`; no entity here declares one of its own) ·
#           NFR-3 (server pagination applied IN SQL) · NFR-5 (no hard caps) ·
#           BR-CUS-054 (the customer is read from `customer_accounts`) ·
#           BR-REP-001 (a report states its basis) · BR-REP-002 (read models
#           only) · BR-REP-024 (never a 0 where a figure could not be computed)
#           · BR-TEN-043 (the business date is an argument, never a clock) ·
#           B14 rule 31 (no database id is ever a visible value)
# Tests:    06-backend/tests/test_rep_p6_account_activity.py
#           10-scripts/p6_join_cost.py (the PostgreSQL measurement)
# Impacts:  apps/reports/report_seams.py (the cross-module caller) ·
#           apps/reports/queries.py (the per-key viewer) ·
#           apps/reports/datasets.py (`ACCOUNTS.filters` gains `event`) ·
#           apps/customers/accounts_dataset.py (its refusal row now names this
#           module as the read model it was asking for)
# ───────────────────────────────────────────────────────
"""**R23 ACCOUNT ACTIVITY — one row per ACCOUNT-LIFECYCLE EVENT**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
WHY THIS IS NOT THE `accounts` DATASET, IN THAT DATASET'S OWN WORDS
═══════════════════════════════════════════════════════════════════════════════
`apps/customers/accounts_dataset.py` refuses R23 by name and its reasoning is
exactly right, so it is quoted rather than restated:

    *"This dataset's grain is one ACCOUNT. R23's tiles are OPENED 38 · CLOSED
    14 · TRANSFERRED 6 · NET +24 over a window — four counts of EVENTS, and one
    account can produce several. Serving it from account rows would report the
    accounts that exist, not the moves that happened, and a NET of +24 would be
    unobtainable from either."*

Its `needs_read_model` names two tables — `apps.customers.moves.MoveRecord` and
`apps.customers.transfers.Transfer` — and **this module is that read model.**
An account opened in March and closed in September is TWO rows here and one row
there, and both are correct about their own grain.

═══════════════════════════════════════════════════════════════════════════════
TWO TABLES, ONE GRAIN, AND THE UNION IS CUT IN SQL
═══════════════════════════════════════════════════════════════════════════════
`moves.KINDS` is a two-tuple — `move_in` and `move_out` — so the drawn
`Transferred in` row **is not a MoveRecord at all**: it is
`apps/customers/transfers.py`'s own table, which B18 §5.7 calls *"one job, not
a move-out followed by a move-in"*.

The two are brought together as a **SQL `UNION`** of two `values()` querysets
with identical column shapes, ordered and sliced by the database. That matters
for `NFR-3`: a Python merge of two lists would make the last page slower than
the first, and at a top-of-ICP tenant — 40,000 accounts, years of moves — the
last page is exactly the page an auditor asks for.

⚠ **A `UNION` QUERYSET CANNOT `select_related`, SO THE LABELS ARE BATCHED PER
PAGE.** Account number, customer name and premises address are resolved for the
page's account ids in **two** further queries, never one per row. That is the
trap `DEF-324` measured at 40,000 round trips and `P2.21` measured again at 56
statements for one page of the billing register; here the cost is bounded by
`per` on the page path and by `STREAM_CHUNK` on the export path, which is
`NFR-3`'s actual requirement — a cost that does not move with the tenant.

═══════════════════════════════════════════════════════════════════════════════
TWO DATE COLUMNS BECAUSE TWO DATES EXIST — AND THE BASIS IS THE EVENT DATE
═══════════════════════════════════════════════════════════════════════════════
p060, verbatim: *"**Two date columns because two dates exist** — when the clerk
did it, and when it takes effect. A move-in dated 1 October appears in
September's activity and in October's census, and both are right."*

So this report serves BOTH, and it is struck on the first:

  * `occurred_at` — when the clerk did it (`MoveRecord.performed_at`,
    `Transfer.committed_at`). **This is the window.**
  * `effective_on` — when it takes effect (`MoveRecord.effective_on`,
    `Transfer.in_date`).

⚠ **THAT SENTENCE IS ALSO WHY R22 AND R23 CANNOT SHARE A DATASET.** R22 Account
Census is dated by MEMBERSHIP and R23 by the EVENT; they are two bases, and
`§7.2` says a dataset states one grain and `BR-REP-001` says a report states one
basis. A single source cannot carry both without lying about one of them.

═══════════════════════════════════════════════════════════════════════════════
`NET` IS NON-ADDITIVE AND THE FOUR TILES DO NOT ALL ADD THE SAME WAY
═══════════════════════════════════════════════════════════════════════════════
`OPENED 38 · CLOSED 14 · TRANSFERRED 6 · NET +24`.

`OPENED`, `CLOSED` and `TRANSFERRED` are **fully additive**: they count events,
no event happens twice, and they sum across time, class and route alike.

**`NET` is `opened − closed` and is DERIVED, never summed.** It sums correctly
across a partition only because both of its components do; a renderer that
totalled a `net` column of group subtotals would get the right answer by
accident and the wrong one the first time a group was filtered. It is declared
`non` and both components travel beside it, which is the same posture
`assets_dataset` takes for its percentage.

⚠ **A TRANSFER IS NOT COUNTED IN `opened` OR `closed`.** It is one job and one
event, and folding it into both would move `NET` by zero while inflating two
tiles — the double-count `work_orders` refuses R34 for, in a smaller place.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT WILL NOT DO
═══════════════════════════════════════════════════════════════════════════════
**It writes nothing.** No INSERT, UPDATE, DELETE or `save()`, on any table.

**It declares no address column.** The premises address is WALKED —
account → unit → premises, through `apps/customers/seams.py` — per hard rule 8,
and this report holds no copy of one.

**It serves no uuid as a visible value** (B14 rule 31). `event_id` and
`account_id` travel for drill-through; `account_no` is what a clerk reads.

**It does not invent an actor for a transfer.** `transfers` carries no
performed-by column at all, so the BY cell is `None` with
`actor_absence="unknown"` and a named gap — never the account's owner, never
the word *System*, and never a blank that reads as *nobody did this*.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from django.db.models import Case, F, Q, Value, When
from django.db.models.fields import CharField

from apps.customers import seams
from apps.customers.models import Account, CustomerAccount
from apps.customers.moves import KIND_MOVE_IN, KIND_MOVE_OUT, MoveRecord
from apps.customers.transfers import Transfer
from core.tenancy import current_tenant_id

#: `BR-REP-001`'s date label. R23 serves no money column, so there is no
#: posting/clearing basis to name; the seeded basis is `EVENT · "Event date"`
#: and `occurred_at` is what the window is struck on.
BASIS_EVENT = "event"

#: The three drawn event words, as CODES. ⚠ **A CODE AND NEVER THE ENGLISH** —
#: B14 rule 35 puts a catalogue in its own language, so `Opened` is the eleven
#: catalogues' job and `opened` is this file's.
EVENT_OPENED = "opened"
EVENT_CLOSED = "closed"
EVENT_TRANSFERRED_IN = "transferred_in"
EVENTS: tuple[str, ...] = (EVENT_OPENED, EVENT_CLOSED, EVENT_TRANSFERRED_IN)

#: `Transfer.STATE_DONE`, read from the model rather than typed — a transfer
#: that is scheduled or in progress has not happened yet and is not activity.
STATE_DONE = Transfer.STATE_DONE

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN A UNIQUE TERM.** A page
#: is a window over an ORDER, and an overnight import writes many moves inside
#: one second; a non-total order would show one event twice and another never.
#:
#: These are the aliases of the UNION's own output columns, which is the only
#: thing a combined queryset can be ordered by — a term naming a base-table
#: column would raise at SQL time rather than fall back.
ACTIVITY_SORTS: tuple[str, ...] = ("occurred_at", "effective_on", "account_no", "event")
ACTIVITY_DEFAULT_SORT = "occurred_at"
ACTIVITY_DEFAULT_DIRECTION = "desc"
_ACTIVITY_ORDER: dict[str, tuple[str, ...]] = {
    "occurred_at": ("occurred_at", "event_id"),
    "effective_on": ("effective_on", "occurred_at", "event_id"),
    "account_no": ("account_no_sort", "occurred_at", "event_id"),
    "event": ("event", "occurred_at", "event_id"),
}

#: The filters this report accepts, and every one of them is applied below.
ACTIVITY_FILTERS: tuple[str, ...] = ("from", "to", "event", "account")


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_TRANSFER_HAS_NO_ACTOR = {
    "code": "a_transfer_records_nobody_who_performed_it",
    "br_ref": "BR-REP-024 · B18 §5.7",
    "detail": (
        "The drawn BY column is `MoveRecord.performed_by` for a move and NOTHING for a "
        "transfer: `transfers` carries no performed-by, actor or clerk column at all. So a "
        "`transferred_in` row serves `actor=None` with `actor_absence='unknown'`, never the "
        "account's owner, never the word System and never a blank — a blank in that column "
        "reads as `nobody did this`, which on a lifecycle report is a different and worse "
        "claim than `we did not record who`."
    ),
    "wanted_reads": ("a performed-by column on `transfers`",),
}

GAP_ACCOUNT_LABELS_UNWIRED = {
    "code": "the_account_labels_could_not_be_resolved",
    "br_ref": "B1 · hard rule 8 · BR-REP-024",
    "detail": (
        "ACCOUNT, CUSTOMER and PREMISES are resolved for the page's account ids in two "
        "batched reads. When the premises seam does not answer, every row's premises is "
        "`None` with `premises_absence='unknown'` rather than an em-dash: `this account is "
        "at no premises` and `we could not ask where it is` are opposite facts and only the "
        "first earns the dash (DEF-475's posture, and the one `assets_dataset` draws)."
    ),
    "wanted_reads": ("apps.customers.seams.unit_refs", "apps.customers.seams.premises_refs"),
}

ABSENCE_NOT_APPLICABLE = "not_applicable"
ABSENCE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class AccountActivityRow:
    """One lifecycle event on one account.

    ⚠ **`occurred_at` AND `effective_on` ARE BOTH SERVED, ALWAYS** — p060's
    *two date columns because two dates exist*. A report carrying one of them
    would put a move-in dated 1 October in the wrong month for one of its two
    legitimate readers.

    ⚠ **`actor_absence` IS A WORD AND NOT A `None`.** See
    `GAP_TRANSFER_HAS_NO_ACTOR`: a transfer records nobody, and that is a
    different fact from a move whose actor we failed to resolve.

    ⚠ **NO UUID IS A DRAWN COLUMN** (B14 rule 31). `event_id` and `account_id`
    travel for drill-through only.
    """

    event_id: str
    event: str
    occurred_at: datetime | None
    effective_on: date | None
    account_id: str | None
    account_no: str | None
    customer_name: str | None
    premises_address: str | None
    unit_label: str | None
    premises_absence: str | None
    reference: str | None
    actor: str | None
    actor_absence: str | None


def _tenant_id() -> Any:
    return current_tenant_id()


#: The UNION's column list, in ONE place. ⚠ **BOTH LEGS MUST PRODUCE THESE
#: NAMES IN THIS ORDER** — a `UNION` matches columns by POSITION, so a leg that
#: listed them differently would silently pair an account id with a date and
#: every row would be wrong with no error anywhere. Naming the order once is
#: what stops that; the two `values(*_UNION_COLUMNS)` calls below are the only
#: two callers.
_UNION_COLUMNS: tuple[str, ...] = (
    "event_id",
    "event",
    "occurred_at",
    "effective_on",
    "account_id",
    "account_no_sort",
    "reference",
    "actor",
)


def _moves_leg(*, start: date | None, end: date | None, event: str | None, account: Any) -> Any:
    """The `move_records` leg of the union — move-in and move-out.

    Hard rule 1: `tenant_id=_tenant_id()`, RLS FORCE underneath.
    """
    rows = MoveRecord.objects.filter(tenant_id=_tenant_id())
    if event == EVENT_OPENED:
        rows = rows.filter(kind=KIND_MOVE_IN)
    elif event == EVENT_CLOSED:
        rows = rows.filter(kind=KIND_MOVE_OUT)
    elif event == EVENT_TRANSFERRED_IN:
        rows = rows.none()
    else:
        rows = rows.filter(kind__in=(KIND_MOVE_IN, KIND_MOVE_OUT))
    if start is not None:
        rows = rows.filter(performed_at__date__gte=start)
    if end is not None:
        rows = rows.filter(performed_at__date__lte=end)
    if account:
        rows = rows.filter(account_id=account)
    return rows.annotate(
        event_id=F("id"),
        # The drawn word, derived from the stored kind rather than stored twice.
        event=_event_word(),
        occurred_at=F("performed_at"),
        # `effective_on` is already this table's own column name.
        account_no_sort=F("account__account_no"),
        reference=F("move_no"),
        actor=F("performed_by__full_name"),
    ).values(*_UNION_COLUMNS)


def _event_word() -> Any:
    """`opened` for a move-in, `closed` for a move-out — decided IN SQL.

    ⚠ **IT IS A `CASE` AND NOT A PYTHON MAP FOR ONE REASON:** the `event`
    FILTER is a `WHERE` on `kind` and the `event` COLUMN is this expression, and
    if the second lived in Python the two would be two rules. A row that
    filtered as `opened` could then render as `closed` and nothing would say so.

    `moves.KINDS` is a two-tuple with a CHECK constraint behind it, so `default`
    is exhaustive rather than a guess — a third kind cannot arrive without the
    database refusing it first.
    """
    return Case(
        When(kind=KIND_MOVE_IN, then=Value(EVENT_OPENED)),
        default=Value(EVENT_CLOSED),
        output_field=CharField(),
    )


def _transfers_leg(*, start: date | None, end: date | None, event: str | None, account: Any) -> Any:
    """The `transfers` leg of the union — one committed transfer, one event.

    ⚠ **ONLY A `done` TRANSFER IS ACTIVITY.** A scheduled or in-progress job
    has not happened, and a cancelled one did not happen; counting either would
    put a future event in a past window.

    ⚠ **IT ATTACHES TO THE `to_account`** — the drawn word is *Transferred IN*,
    so the row is about the account that received the service, which is also the
    account whose premises the drawing prints.

    ⚠ **`actor` IS A TYPED NULL AND NOT A COLUMN.** `transfers` has no
    performed-by; see `GAP_TRANSFER_HAS_NO_ACTOR`.
    """
    rows = Transfer.objects.filter(tenant_id=_tenant_id(), state=STATE_DONE)
    if event in (EVENT_OPENED, EVENT_CLOSED):
        rows = rows.none()
    if start is not None:
        rows = rows.filter(committed_at__date__gte=start)
    if end is not None:
        rows = rows.filter(committed_at__date__lte=end)
    if account:
        rows = rows.filter(Q(to_account_id=account) | Q(from_account_id=account))
    return rows.annotate(
        event_id=F("id"),
        event=Value(EVENT_TRANSFERRED_IN, output_field=CharField()),
        occurred_at=F("committed_at"),
        # B18 §5.7.2 — the date the service actually moves.
        effective_on=F("in_date"),
        account_id=F("to_account_id"),
        account_no_sort=F("to_account__account_no"),
        reference=F("transfer_no"),
        actor=Value(None, output_field=CharField()),
    ).values(*_UNION_COLUMNS)


def _combined(*, start: date | None, end: date | None, event: str | None, account: Any) -> Any:
    """Both legs, as ONE queryset the database orders and slices.

    `QuerySet.union()` emits `(SELECT …) UNION (SELECT …)`, and the `ORDER BY`
    and `LIMIT`/`OFFSET` that follow are applied by PostgreSQL to the combined
    result — which is what makes the last page cost the same as the first.
    """
    return _moves_leg(start=start, end=end, event=event, account=account).union(
        _transfers_leg(start=start, end=end, event=event, account=account),
        all=True,
    )


def _ordered(combined: Any, sort: str | None, direction: str) -> Any:
    """The combined queryset, ordered IN SQL by one of its own output aliases.

    ⚠ **`core.pagination.order_terms` IS NOT USED HERE AND THE REASON IS
    STRUCTURAL.** Its `columns` map names BASE-TABLE paths — `user__full_name`,
    `service_point__route_id` — and a combined queryset has no base table: only
    the union's own output aliases can be ordered by, and naming anything else
    raises at SQL time rather than falling back (`BR-SHL-011` says a bad value
    falls back and never errors). So the fallback happens HERE, on the alias
    map, and the descending flip is spelled out rather than borrowed.
    """
    name = sort if sort in _ACTIVITY_ORDER else ACTIVITY_DEFAULT_SORT
    terms = _ACTIVITY_ORDER[name]
    if str(direction).lower() == "desc":
        return combined.order_by(*(f"-{term}" for term in terms))
    return combined.order_by(*terms)


def _labels_for(rows: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], bool]:
    """A PAGE's account labels — TWO batched reads, never one per row.

    Returns the map and whether the premises walk answered, because an unwired
    seam and an account genuinely at no premises are opposite facts and only one
    of them earns the em-dash.
    """
    ids = [row["account_id"] for row in rows if row.get("account_id")]
    if not ids:
        return {}, True
    accounts = {
        str(account.id): account
        for account in Account.objects.filter(tenant_id=_tenant_id(), id__in=ids)
    }
    # ⚠ **THE CUSTOMER IS READ FROM `customer_accounts` (`BR-CUS-054`) AND NOT
    # FROM THE ACCOUNT.** An account holds no name column; the holder is the
    # PRIMARY link that has not ended, which is the same rule the account
    # header applies. ONE query for the whole page, never one per row.
    holders = {
        str(link.account_id): link.customer.display_name
        for link in CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, is_primary=True, ended_at__isnull=True
        ).select_related("customer")
    }
    unit_ids = [
        str(account.unit_id) for account in accounts.values() if getattr(account, "unit_id", None)
    ]
    refs = seams.unit_refs(unit_ids) if unit_ids else {}
    wired = bool(refs) or not unit_ids
    labels: dict[str, dict[str, Any]] = {}
    for account_id, account in accounts.items():
        ref = refs.get(str(account.unit_id) or "") or {} if account.unit_id else {}
        labels[account_id] = {
            "account_no": account.account_no,
            "customer_name": holders.get(account_id),
            "premises_address": ref.get("premise_address"),
            "unit_label": ref.get("label"),
            # Hard rule 8's walk: an account with no unit is at no premises YET,
            # which is a lawful state and the em-dash; a unit we could not
            # resolve is a gap and the blank.
            "premises_absence": (
                ABSENCE_NOT_APPLICABLE
                if not account.unit_id
                else (None if ref else ABSENCE_UNKNOWN)
            ),
        }
    return labels, wired


def _shape(row: dict[str, Any], labels: dict[str, dict[str, Any]]) -> AccountActivityRow:
    """One union row plus its batched labels. No query."""
    account_id = row.get("account_id")
    label = labels.get(str(account_id)) if account_id else None
    label = label or {}
    return AccountActivityRow(
        event_id=str(row["event_id"]),
        event=row["event"],
        occurred_at=row.get("occurred_at"),
        effective_on=row.get("effective_on"),
        account_id=str(account_id) if account_id else None,
        # B14 rule 31 — the account number, never the uuid.
        account_no=label.get("account_no"),
        customer_name=label.get("customer_name"),
        premises_address=label.get("premises_address"),
        unit_label=label.get("unit_label"),
        premises_absence=label.get("premises_absence"),
        reference=row.get("reference"),
        actor=row.get("actor"),
        # ⚠ A transfer records NOBODY — never the owner, never `System`. A move
        # whose actor we failed to resolve is the SAME word here on purpose:
        # both are `unknown`, because neither is a lawful absence and neither
        # earns the em-dash. `is_transfer` decides only which gap is reported.
        actor_absence=None if row.get("actor") else ABSENCE_UNKNOWN,
    )


def _counts(*, start: date | None, end: date | None, account: Any) -> dict[str, int]:
    """The four tiles, as SQL counts over the WHOLE filtered set.

    ⚠ **THEY ARE STRUCK PER EVENT KIND AND NEVER OVER THE UNION.** A `COUNT`
    over a combined queryset is one number; the drawing needs three, and asking
    the two base tables directly is both cheaper and the only way `opened` and
    `closed` can be counted separately.
    """
    moves = MoveRecord.objects.filter(tenant_id=_tenant_id())
    transfers = Transfer.objects.filter(tenant_id=_tenant_id(), state=STATE_DONE)
    if start is not None:
        moves = moves.filter(performed_at__date__gte=start)
        transfers = transfers.filter(committed_at__date__gte=start)
    if end is not None:
        moves = moves.filter(performed_at__date__lte=end)
        transfers = transfers.filter(committed_at__date__lte=end)
    if account:
        moves = moves.filter(account_id=account)
        transfers = transfers.filter(Q(to_account_id=account) | Q(from_account_id=account))
    opened = moves.filter(kind=KIND_MOVE_IN).count()
    closed = moves.filter(kind=KIND_MOVE_OUT).count()
    transferred = transfers.count()
    return {
        "opened": opened,
        "closed": closed,
        "transferred": transferred,
        # DERIVED, never summed — see the module docstring.
        "net": opened - closed,
        "events": opened + closed + transferred,
    }


def account_activity(
    *,
    start: date | None = None,
    end: date | None = None,
    event: str | None = None,
    account: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = ACTIVITY_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R23, ONE PAGE. One row per lifecycle event, paged and sorted in SQL.

    `per=None` is the whole filtered set. The CALLER clamps `per`; this function
    invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `account_activity_stream()`** — no `page`, no `per`.

    **`totals` IS A SQL COUNT OVER THE WHOLE FILTERED SET AND NEVER OVER THE
    PAGE**, so the four tiles foot to the report whether a page is cut or not.
    """
    chosen = event if event in EVENTS else None
    combined = _combined(start=start, end=end, event=chosen, account=account)
    ordered = _ordered(combined, sort, direction)

    totals = _counts(start=start, end=end, account=account)
    # The row count for THIS filtered set, which narrows when `event` is chosen.
    if chosen == EVENT_OPENED:
        total_rows = totals["opened"]
    elif chosen == EVENT_CLOSED:
        total_rows = totals["closed"]
    elif chosen == EVENT_TRANSFERRED_IN:
        total_rows = totals["transferred"]
    else:
        total_rows = totals["events"]

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
    labels, wired = _labels_for(materialised)
    shaped = tuple(_shape(row, labels) for row in materialised)

    problems: list[dict[str, Any]] = []
    if any(row.event == EVENT_TRANSFERRED_IN for row in shaped):
        problems.append(dict(GAP_TRANSFER_HAS_NO_ACTOR))
    if materialised and not wired:
        problems.append(dict(GAP_ACCOUNT_LABELS_UNWIRED))

    return {
        "basis": BASIS_EVENT,
        "window": {"start": start, "end": end},
        "grain": "one account-lifecycle event",
        "rows": shaped,
        "totals": {
            # FULLY ADDITIVE — an event happens once and in one month.
            "opened": totals["opened"],
            "closed": totals["closed"],
            "transferred": totals["transferred"],
            "events": totals["events"],
            # DERIVED. It sums across a partition only because both of its
            # components do, which is a different guarantee from being additive.
            "net": totals["net"],
        },
        "additivity": {
            "opened": "full",
            "closed": "full",
            "transferred": "full",
            "events": "full",
            "net": "non",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_rows,
        "problems": tuple(problems),
    }


#: A fetch buffer, not a cap (`NFR-5`). It also bounds the two batched label
#: reads per chunk, which is the whole reason the export is chunked at all.
STREAM_CHUNK = 2_000


def account_activity_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    event: str | None = None,
    account: Any = None,
    sort: str | None = None,
    direction: str = ACTIVITY_DEFAULT_DIRECTION,
) -> Iterator[AccountActivityRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    ⚠ **A COMBINED QUERYSET HAS NO `.iterator()` WORTH THE NAME** — a `UNION`
    is materialised by the database before the first row is returned — so this
    walks the ordered result in SQL-sliced chunks, which keeps the label reads
    batched and keeps a 40,000-row file out of memory. The ORDER is total (every
    tuple in `_ACTIVITY_ORDER` ends in `event_id`), so consecutive slices cannot
    repeat or skip a row, which is the property a non-total order would destroy.
    """
    chosen = event if event in EVENTS else None
    ordered = _ordered(
        _combined(start=start, end=end, event=chosen, account=account), sort, direction
    )
    offset = 0
    while True:
        chunk = list(ordered[offset : offset + STREAM_CHUNK])
        if not chunk:
            return
        labels, _wired = _labels_for(chunk)
        for row in chunk:
            yield _shape(row, labels)
        offset += STREAM_CHUNK


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 (R23 account_activity; 12-governance/change-requests/CR-142-BRC07-reports-framework.md §9.2 · 05-prototype/09 Reports Build Brief.pdf p059-p060 read as images per B14 rule 42 · 04-docs/05-modules/12-reports/02-business-rules.md BR-REP-001/002/024)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-JOIN
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `tests/test_rep_p6_account_activity.py` could not import this module before it existed, and `GET /reports/account_activity` answered `accounts_dataset`'s named refusal.
# exceptions: (0) the UNION is cut, ordered and sliced IN SQL; a Python merge would make the last page slower than the first · (1) a combined queryset cannot `select_related`, so account/customer/premises labels are TWO batched reads per page, bounded by `per` · (2) `order_terms` is deliberately NOT used — a combined queryset can only be ordered by its own output aliases, so the BR-SHL-011 fallback lives here · (3) a transfer records NO actor and the BY cell is null with `actor_absence`, never the owner and never `System` · (4) `net` is DERIVED and declared non-additive; a transfer is counted in neither `opened` nor `closed` · (5) this file writes nothing and declares no address column — the premises is walked (hard rule 8)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Change:   CR-142-BRC07 · `P6.11` — the JOINING READ behind R34 Disconnect &
#           Reconnect. Drawing read as an IMAGE (B14 rule 42): p065 of
#           `05-prototype/09 Reports Build Brief.pdf`, rendered at 2.0x by
#           `10-scripts/pdf/pdf_render.py`.
# Story:    R34 `disconnect_reconnect` — Operations › Field · **Event date**
#           (`reports/migrations/0003_seed_catalogue.py` line 251).
# Rules:    `BR-REP-039` (PO ruling 2026-09-27, option (a) — ONE ROW PER
#           ACCOUNT, latest case; earlier cases underneath, never as sibling
#           rows; the spine is `customers.disconnect_cases`) · CLAUDE.md hard
#           rule 1 (tenant scoping) · hard rule 2 (money stored 4 decimals,
#           displayed 2) · hard rule 4 (this file writes nothing) · NFR-3
#           (server pagination applied IN SQL) · NFR-5 (no hard caps) ·
#           BR-CUS-054 (the customer is read from `customer_accounts`) ·
#           BR-REP-001 (a report states its basis) · BR-REP-024 (a figure that
#           could not be computed is NULL with its reason, never a 0) ·
#           BR-TEN-043 (the business date is an argument, never a clock) ·
#           B14 rule 31 (no database id is a visible value)
# Tests:    06-backend/tests/test_rep_p6w2_disconnect_reconnect.py
#           10-scripts/p6w2_cost.py (the PostgreSQL measurement)
# Impacts:  apps/reports/report_seams.py (the cross-module caller) ·
#           apps/reports/queries.py (the per-key viewer and its stream) ·
#           apps/reports/exports.py (the export resource — a live Download
#           button over a 404 otherwise) ·
#           apps/work/work_orders_dataset.py (its refusal is UNCHANGED and
#           stays true of THAT dataset — `BR-REP-039` supersedes it only as a
#           statement about this REPORT)
# ───────────────────────────────────────────────────────
"""**R34 DISCONNECT & RECONNECT — one row per ACCOUNT**, paged and sorted in SQL.

═══════════════════════════════════════════════════════════════════════════════
ONE ROW IS ONE ACCOUNT, SHOWING ITS LATEST CASE — `BR-REP-039`
═══════════════════════════════════════════════════════════════════════════════
PO ruling 2026-09-27, option (a) of two. The worked case the PO was shown:

    *"Alia is cut off on 3 June for `$210` owed and restored on 11 June when
    she pays. She falls behind again and is cut off on 9 September for `$185`.
    Under one row per account she is one line, showing where she stands today.
    Under one row per case she is two lines, and the total at the bottom reads
    `$395` owed — money she never owed all at once."*

So the BALANCE column foots honestly: each account contributes its current
position ONCE. `tests/test_rep_p6w2_disconnect_reconnect.py` builds exactly
that account and asserts the total is **`$185.00` and never `$395.00`**.

⚠ **EARLIER CASES ARE COUNTED, NEVER SERVED AS SIBLING ROWS.** Each row carries
`earlier_cases` — how many CLOSED cases this account has behind the one shown —
so a supervisor can see there is history without the history entering the
arithmetic. It is declared **non-additive**: summing a column of "how many
previous times" answers no question anybody asks.

═══════════════════════════════════════════════════════════════════════════════
WHY NOT `work_orders`, AND WHY THAT REFUSAL STAYS WHERE IT IS
═══════════════════════════════════════════════════════════════════════════════
`apps/work/work_orders_dataset.GAP_R34_IS_A_DIFFERENT_GRAIN` refuses this
report and is **right about that dataset**:

    *"an account cut and restored inside the window has TWO orders, so it would
    appear twice and the balance column would double-count the debt."*

`BR-REP-039` supersedes it as a statement about the REPORT and leaves it
standing as a statement about the DATASET. It is not deleted here: a refusal
removed the day its read model lands is a refusal nobody can read when the
wiring rots, which is exactly the posture lane REP-P6-JOIN took over its own
three.

═══════════════════════════════════════════════════════════════════════════════
THE LATEST CASE IS CHOSEN IN SQL, AND THE PORTABLE FORM IS THE ONLY FORM
═══════════════════════════════════════════════════════════════════════════════
PostgreSQL's `DISTINCT ON (account_id)` is the obvious way to pick one case per
account and **it is not available here**: the test suite runs on in-memory
SQLite (`config/settings/test.py` hardcodes it and ignores `DATABASE_URL` —
CLAUDE.md hard-won law 14), where `DISTINCT ON` does not exist, and Django also
forbids ordering a `distinct('account_id')` queryset by anything that does not
start with that field, which is every sort this report offers.

So the pick is a **correlated `Subquery` on the case id**, which both backends
execute and which leaves the outer queryset freely orderable, sliceable and
countable. It is measured rather than assumed — see `10-scripts/p6w2_cost.py`.

⚠ **THE SUBQUERY'S ORDER IS TOTAL.** `-opened_on, -created_at, -id`: two cases
opened on one day by an overnight job would otherwise make *latest* a coin
toss, and a coin toss decides which BALANCE the account contributes.

⚠ **THE WINDOW IS APPLIED INSIDE THE SUBQUERY AS WELL AS OUTSIDE.** The latest
case *in the window* is what the report is about; picking the latest case
overall and then filtering would drop an account whose newest case is outside
the window while it still has an older one inside it, and the tiles would then
disagree with the rows.

═══════════════════════════════════════════════════════════════════════════════
WHAT IS DRAWN AND CANNOT BE SERVED, STATED RATHER THAN INVENTED
═══════════════════════════════════════════════════════════════════════════════
Two of p065's figures are **not in this product** and each is NULL with a named
reason rather than a plausible number (`BR-REP-024`):

  **`ELIGIBLE`** — the drawn `84 / $22,104.80` tile counts accounts the tenant's
  eligibility rules WOULD select and on which no case has been opened. The
  drawing's own caption says *"Eligibility rules are the tenant's and live in
  Settings — this report shows who the rule selected, never decides it."*
  **Nothing in this repository evaluates that rule.** `disconnect_cases` holds
  cases that were OPENED; an eligible account has no row. Counting the accounts
  that already have a case and calling them eligible would report the opposite
  of what the tile means.

  **`PAID`** — the drawn column and the `$4,118.00 collected` half of the
  RECONNECTED tile. `disconnect_cases` records what was OWED at the cut
  (`amount_owed_at_open`) and never what was RECEIVED; money received is
  payments' own table, which this module does not read and may not (B1 —
  cross-module writes forbidden, cross-module reads through a reviewed seam,
  and `customers` publishes no payments seam). `BR-REP-039` itself says the
  case table holds *"every drawn column except Paid"*.

Both are reported in `problems` on every response, so the absence travels to
the screen as an absence rather than as a zero a supervisor would act on.

═══════════════════════════════════════════════════════════════════════════════
HARD RULE 8 — THE ADDRESS IS WALKED
═══════════════════════════════════════════════════════════════════════════════
This file declares no address column. The premises is reached through
`apps.customers.seams.unit_refs`, batched once per page, exactly as
`account_activity.py` does it and for the same reason.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from django.db.models import Count, OuterRef, Q, Subquery, Sum

from apps.customers import seams
from apps.customers.disconnects import (
    CLOSED_CASE_STATES,
    STATE_CUT,
    STATE_ON_HOLD,
    STATE_RECONNECTING,
    STATE_RESTORED,
    STATE_SCHEDULED,
    DisconnectCase,
)
from apps.customers.models import CustomerAccount
from core.tenancy import current_tenant_id

#: `BR-REP-001`'s basis. The seeded row is `EVENT · "Event date"` and the
#: window is struck on `opened_on` — the day the sequence started, which is the
#: drawn NOTICE column and the only date every case has.
BASIS_EVENT = "event"

#: ⚠ **THE WINDOW IS STRUCK ON `opened_on` AND THIS IS WHY.** `cut_on` is NULL
#: on every case that has not reached a cut, and those are the rows a supervisor
#: opens this report to find — an account on notice with nothing done about it.
#: A window on `cut_on` would show only the accounts already dealt with.
WINDOW_COLUMN = "opened_on"

#: What a caller may order by. ⚠ **EVERY TUPLE ENDS IN A UNIQUE TERM** — `id` —
#: because a page is a window over an ORDER and a collections run opens many
#: cases on one date; a non-total order shows one account twice and another
#: never.
DISCONNECT_SORTS: tuple[str, ...] = (
    "account_no",
    "balance",
    "notice_on",
    "cut_on",
    "reconnected_on",
    "status",
)
DISCONNECT_DEFAULT_SORT = "notice_on"
DISCONNECT_DEFAULT_DIRECTION = "desc"
_DISCONNECT_ORDER: dict[str, tuple[str, ...]] = {
    "account_no": ("account__account_no", "id"),
    "balance": ("amount_owed_at_open", "id"),
    "notice_on": ("opened_on", "id"),
    "cut_on": ("cut_on", "opened_on", "id"),
    "reconnected_on": ("reconnected_on", "opened_on", "id"),
    "status": ("state", "opened_on", "id"),
}

#: The filters this report accepts, and every one of them is applied below.
#: p065 draws THREE — From, To and Reason — and `reason` is the case's own
#: `cut_reason`, which is free text on the model and therefore served as an
#: exact match on whatever the tenant writes rather than as a vocabulary this
#: file invents.
DISCONNECT_FILTERS: tuple[str, ...] = ("from", "to", "reason", "account")

#: The case states that mean **service is off right now**. Read from
#: `apps/customers/disconnects.py` rather than typed, so a state added there
#: cannot silently fall out of this count.
CUT_STATES: tuple[str, ...] = (STATE_CUT, STATE_RECONNECTING)

#: The states that mean **a notice has gone out and nothing has been cut**.
NOTICE_STATES: tuple[str, ...] = (STATE_SCHEDULED, STATE_ON_HOLD)


# ── BR-REP-024: named gaps, never a silent zero and never a plausible number ──

GAP_ELIGIBLE_IS_NOT_EVALUATED_ANYWHERE = {
    "code": "no_rule_in_this_product_selects_an_eligible_account",
    "br_ref": "BR-REP-024 · BR-REP-039 · p065",
    "detail": (
        "p065 draws ELIGIBLE 84 / $22,104.80 and captions it *Eligibility rules are the "
        "tenant's and live in Settings — this report shows who the rule selected, never "
        "decides it*. Nothing in this repository evaluates that rule. `disconnect_cases` "
        "holds cases that were OPENED, and an eligible account is by definition one that "
        "has no case yet — so the tile is served as NULL with this reason rather than as a "
        "count of the accounts that already have a case, which is the opposite population."
    ),
    "wanted_reads": (
        "a tenant disconnection-eligibility rule evaluated over accounts with arrears",
    ),
}

GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN = {
    "code": "the_case_records_what_was_owed_never_what_was_received",
    "br_ref": "BR-REP-024 · BR-REP-039 · B1 · p065",
    "detail": (
        "p065 draws a PAID column and a `$4,118.00 collected` half on the RECONNECTED "
        "tile. `disconnect_cases.amount_owed_at_open` is what was OWED when the case "
        "opened and never changes again; money RECEIVED lives in payments' own tables, "
        "which customers does not read and may not — B1 forbids the cross-module query and "
        "this module publishes no payments seam. BR-REP-039 states it directly: the case "
        "table holds every drawn column except Paid. Served as NULL with this reason."
    ),
    "wanted_reads": ("a payments seam answering `received against this account since <date>`",),
}

GAP_ACCOUNT_LABELS_UNWIRED = {
    "code": "the_account_labels_could_not_be_resolved",
    "br_ref": "B1 · hard rule 8 · BR-REP-024",
    "detail": (
        "CUSTOMER and the premises walk are resolved for the page's account ids in batched "
        "reads. When the premises seam does not answer, a row's premises is None with "
        "`premises_absence='unknown'` rather than an em-dash: *this account is at no "
        "premises* and *we could not ask where it is* are opposite facts and only the first "
        "earns the dash."
    ),
    "wanted_reads": ("apps.customers.seams.unit_refs",),
}

ABSENCE_NOT_APPLICABLE = "not_applicable"
ABSENCE_UNKNOWN = "unknown"

#: The drawn STATUS words, as CODES. ⚠ **A CODE AND NEVER THE ENGLISH** — B14
#: rule 35 puts a catalogue in its own language, so `Restored` is the eleven
#: catalogues' job and `restored` is this file's.
STATUS_NOTICE_SENT = "notice_sent"
STATUS_SCHEDULED = "scheduled"
STATUS_ON_HOLD = "on_hold"
STATUS_DISCONNECTED = "disconnected"
STATUS_RECONNECTING = "reconnecting"
STATUS_RESTORED = "restored"
STATUS_STOPPED = "stopped"
STATUS_CLOSED_OUT = "closed_out"


@dataclass(frozen=True)
class DisconnectReconnectRow:
    """One ACCOUNT, showing its latest disconnect case in the window.

    ⚠ **`balance` IS `amount_owed_at_open` AND IS A RECORD, NOT A LIVE
    BALANCE.** The model says so in its own words: *"what was outstanding at
    the moment of the cut and it never changes again"*. The live balance is AR's
    and a report that mixed the two would foot to neither.

    ⚠ **`paid` IS ALWAYS `None`** — see `GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN`.
    It is a field rather than an omission so the column can be drawn with an
    em-dash and a named reason instead of silently disappearing from a drawn
    table.

    ⚠ **NO UUID IS A DRAWN COLUMN** (B14 rule 31). `case_id` and `account_id`
    travel for drill-through only.
    """

    case_id: str
    account_id: str | None
    account_no: str | None
    customer_name: str | None
    premises_address: str | None
    premises_absence: str | None
    balance: Decimal | None
    currency: str | None
    notice_on: date | None
    cut_on: date | None
    paid: None
    paid_absence: str
    reconnected_on: date | None
    status: str
    reason: str | None
    earlier_cases: int


def _tenant_id() -> Any:
    return current_tenant_id()


def _window(qs: Any, *, start: date | None, end: date | None) -> Any:
    """The date window, struck on `opened_on`. See `WINDOW_COLUMN`."""
    if start is not None:
        qs = qs.filter(opened_on__gte=start)
    if end is not None:
        qs = qs.filter(opened_on__lte=end)
    return qs


def _filtered(
    *, start: date | None, end: date | None, reason: str | None, account: Any
) -> Any:
    """Every case in the window, before the latest-per-account pick."""
    qs = DisconnectCase.objects.filter(tenant_id=_tenant_id())
    qs = _window(qs, start=start, end=end)
    if reason:
        qs = qs.filter(cut_reason=reason)
    if account:
        qs = qs.filter(account_id=account)
    return qs


def _latest_per_account(
    *, start: date | None, end: date | None, reason: str | None, account: Any
) -> Any:
    """ONE case per account — the latest in the window — chosen IN SQL.

    ⚠ **THE SUBQUERY REPEATS THE WINDOW AND THE FILTERS.** Picking the newest
    case overall and filtering afterwards would drop an account whose newest
    case is outside the window although an older one is inside it, and the
    tiles — which are struck over this same queryset — would then disagree with
    the rows they are meant to foot to.
    """
    inner = (
        _filtered(start=start, end=end, reason=reason, account=account)
        .filter(account_id=OuterRef("account_id"))
        .order_by("-opened_on", "-created_at", "-id")
        .values("id")[:1]
    )
    return _filtered(start=start, end=end, reason=reason, account=account).filter(
        id=Subquery(inner)
    )


def _ordered(qs: Any, sort: str | None, direction: str) -> Any:
    """BR-SHL-011's fallback, and every order is TOTAL — see `_DISCONNECT_ORDER`."""
    terms = _DISCONNECT_ORDER.get(sort or "") or _DISCONNECT_ORDER[DISCONNECT_DEFAULT_SORT]
    if direction == "desc":
        terms = tuple(f"-{term}" for term in terms)
    return qs.order_by(*terms)


def _status_of(case: DisconnectCase) -> str:
    """The drawn STATUS word for a case, from its own state.

    ⚠ **IT IS THE CASE'S STATE AND NOT A DERIVATION FROM THE DATES.** A case
    that was STOPPED by hand has a `cut_on` and no `reconnected_on`, and reading
    the dates would report it as still disconnected — which is the one thing the
    stop exists to say is not true.
    """
    return str(case.state)


def _labels_for(rows: list[DisconnectCase]) -> tuple[dict[str, dict[str, Any]], bool]:
    """A PAGE's account labels — batched reads, never one per row."""
    ids = [str(case.account_id) for case in rows if case.account_id]
    if not ids:
        return {}, True
    # ⚠ **THE CUSTOMER IS READ FROM `customer_accounts` (`BR-CUS-054`)** — an
    # account holds no name column; the holder is the PRIMARY link that has not
    # ended. ONE query for the whole page.
    holders = {
        str(link.account_id): link.customer.display_name
        for link in CustomerAccount.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, is_primary=True, ended_at__isnull=True
        ).select_related("customer")
    }
    unit_ids = [
        str(case.account.unit_id)
        for case in rows
        if case.account_id and getattr(case.account, "unit_id", None)
    ]
    refs = seams.unit_refs(unit_ids) if unit_ids else {}
    wired = bool(refs) or not unit_ids
    labels: dict[str, dict[str, Any]] = {}
    for case in rows:
        if not case.account_id:
            continue
        account = case.account
        unit_id = getattr(account, "unit_id", None)
        ref = (refs.get(str(unit_id)) or {}) if unit_id else {}
        labels[str(case.account_id)] = {
            "account_no": account.account_no,
            "customer_name": holders.get(str(case.account_id)),
            "premises_address": ref.get("premise_address"),
            "premises_absence": (
                ABSENCE_NOT_APPLICABLE if not unit_id else (None if ref else ABSENCE_UNKNOWN)
            ),
        }
    return labels, wired


def _earlier_counts(rows: list[DisconnectCase]) -> dict[str, int]:
    """How many CLOSED cases sit behind each shown case — ONE grouped query.

    ⚠ **IT IS NOT *every other case*.** A case that is still running behind the
    one shown cannot exist — `uq_one_open_disconnect_case_per_account` permits
    exactly one open case per account — so *earlier* and *closed* are the same
    set, and saying `closed` is what makes the count reproducible.
    """
    ids = [str(case.account_id) for case in rows if case.account_id]
    if not ids:
        return {}
    shown = {str(case.account_id): case.opened_on for case in rows if case.account_id}
    counted = (
        DisconnectCase.objects.filter(
            tenant_id=_tenant_id(), account_id__in=ids, state__in=CLOSED_CASE_STATES
        )
        .values("account_id", "opened_on")
        .annotate(n=Count("id"))
    )
    out: dict[str, int] = {}
    for row in counted:
        account_id = str(row["account_id"])
        edge = shown.get(account_id)
        if edge is not None and row["opened_on"] is not None and row["opened_on"] >= edge:
            continue
        out[account_id] = out.get(account_id, 0) + int(row["n"])
    return out


def _shape(
    case: DisconnectCase, labels: dict[str, dict[str, Any]], earlier: dict[str, int]
) -> DisconnectReconnectRow:
    """One case plus its batched labels. No query."""
    account_id = str(case.account_id) if case.account_id else None
    label = (labels.get(account_id) or {}) if account_id else {}
    return DisconnectReconnectRow(
        case_id=str(case.id),
        account_id=account_id,
        account_no=label.get("account_no"),
        customer_name=label.get("customer_name"),
        premises_address=label.get("premises_address"),
        premises_absence=label.get("premises_absence"),
        balance=case.amount_owed_at_open,
        currency=case.currency,
        notice_on=case.opened_on,
        cut_on=case.cut_on,
        # ⚠ ALWAYS NULL, ALWAYS WITH ITS REASON — see the module docstring.
        paid=None,
        paid_absence=GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN["code"],
        reconnected_on=case.reconnected_on,
        status=_status_of(case),
        reason=case.cut_reason,
        earlier_cases=int(earlier.get(account_id or "", 0)),
    )


def _single_currency(latest: Any) -> str | None:
    """`CHF` when every shown case is in one currency, else `None`.

    ⚠ **TWO ROWS, NEVER A WALK OVER THE SET.** `values_list(...).distinct()[:2]`
    asks the database the only question that matters — *is there more than
    one* — and stops. Reading every row to find out would make the answer cost
    grow with the tenant, on a figure that is one word long.
    """
    found = list(latest.values_list("currency", flat=True).distinct()[:2])
    return str(found[0]) if len(found) == 1 and found[0] else None


def _tiles(
    *, start: date | None, end: date | None, reason: str | None, account: Any
) -> dict[str, Any]:
    """p065's four tiles, as SQL aggregates over the WHOLE filtered set.

    ⚠ **THEY ARE STRUCK OVER THE LATEST-PER-ACCOUNT SET, WHICH IS THE ROWS.**
    That is the whole of `BR-REP-039`: the tiles and the rows describe one
    population, so `balance` foots and `$395` cannot appear.
    """
    latest = _latest_per_account(start=start, end=end, reason=reason, account=account)
    aggregates = latest.aggregate(
        accounts=Count("id"),
        owed=Sum("amount_owed_at_open"),
        notices=Count("id", filter=Q(state__in=(*NOTICE_STATES, "notice_sent"))),
        disconnected=Count("id", filter=Q(state__in=CUT_STATES)),
        reconnected=Count("id", filter=Q(state=STATE_RESTORED)),
    )
    return {
        # ⚠ NULL, NEVER 0 — `GAP_ELIGIBLE_IS_NOT_EVALUATED_ANYWHERE`.
        "eligible": None,
        "eligible_value": None,
        "accounts": int(aggregates["accounts"] or 0),
        "owed": aggregates["owed"] if aggregates["owed"] is not None else Decimal("0"),
        "notices_sent": int(aggregates["notices"] or 0),
        "disconnected": int(aggregates["disconnected"] or 0),
        "reconnected": int(aggregates["reconnected"] or 0),
        # ⚠ NULL, NEVER 0 — `GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN`.
        "collected": None,
    }


def disconnect_reconnect(
    *,
    start: date | None = None,
    end: date | None = None,
    reason: str | None = None,
    account: Any = None,
    page: int = 1,
    per: int | None = None,
    sort: str | None = None,
    direction: str = DISCONNECT_DEFAULT_DIRECTION,
) -> dict[str, Any]:
    """R34, ONE PAGE. One row per ACCOUNT, paged and sorted in SQL.

    `per=None` is the whole filtered set. The CALLER clamps `per`; this function
    invents no cap (`NFR-5`).

    ⚠ **FOR AN EXPORT, CALL `disconnect_reconnect_stream()`** — no `page`, no
    `per`. Two functions and never a flag.

    **`totals` IS A SQL AGGREGATE OVER THE WHOLE FILTERED SET AND NEVER OVER
    THE PAGE**, so the tiles foot to the report whether a page is cut or not.
    """
    latest = _latest_per_account(start=start, end=end, reason=reason, account=account)
    ordered = _ordered(latest, sort, direction).select_related("account")

    tiles = _tiles(start=start, end=end, reason=reason, account=account)
    total_rows = tiles["accounts"]

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
    earlier = _earlier_counts(materialised)
    shaped = tuple(_shape(case, labels, earlier) for case in materialised)

    problems: list[dict[str, Any]] = [
        dict(GAP_ELIGIBLE_IS_NOT_EVALUATED_ANYWHERE),
        dict(GAP_PAID_IS_PAYMENTS_AND_NOT_A_CASE_COLUMN),
    ]
    if materialised and not wired:
        problems.append(dict(GAP_ACCOUNT_LABELS_UNWIRED))

    return {
        "basis": BASIS_EVENT,
        "window": {"start": start, "end": end},
        # ⚠ **THE CURRENCY IS THE FILTERED SET'S AND NOT THE PAGE'S, AND IT IS
        # NULL WHEN THEY DISAGREE.** A footer summing two currencies into one
        # symbol is a number that is wrong in both; `None` makes the renderer
        # print the figure without a symbol rather than a confident lie.
        "currency": _single_currency(latest),
        "grain": "one account, showing its latest disconnect case",
        "rows": shaped,
        "totals": {
            # FULLY ADDITIVE — one account contributes once (`BR-REP-039`).
            "accounts": tiles["accounts"],
            "owed": tiles["owed"],
            "notices_sent": tiles["notices_sent"],
            "disconnected": tiles["disconnected"],
            "reconnected": tiles["reconnected"],
            # NULL WITH A REASON, never 0 — both gaps above.
            "eligible": tiles["eligible"],
            "eligible_value": tiles["eligible_value"],
            "collected": tiles["collected"],
        },
        "additivity": {
            "accounts": "full",
            "owed": "full",
            "notices_sent": "full",
            "disconnected": "full",
            "reconnected": "full",
            "eligible": "unavailable",
            "eligible_value": "unavailable",
            "collected": "unavailable",
            # A count of *how many previous times* answers no question when
            # summed down a column.
            "earlier_cases": "non",
        },
        "page": served_page,
        "per": per,
        "pages": pages,
        "total": total_rows,
        "problems": tuple(problems),
    }


#: A fetch buffer, not a cap (`NFR-5`). It also bounds the batched label reads
#: per chunk, which is the whole reason the export is chunked at all.
STREAM_CHUNK = 2_000


def disconnect_reconnect_stream(
    *,
    start: date | None = None,
    end: date | None = None,
    reason: str | None = None,
    account: Any = None,
    sort: str | None = None,
    direction: str = DISCONNECT_DEFAULT_DIRECTION,
) -> Iterator[DisconnectReconnectRow]:
    """EVERY row of the filtered set, streamed — **no `page`, no `per`.**

    The ORDER is total (every tuple in `_DISCONNECT_ORDER` ends in `id`), so
    consecutive SQL slices cannot repeat or skip a row.
    """
    ordered = _ordered(
        _latest_per_account(start=start, end=end, reason=reason, account=account),
        sort,
        direction,
    ).select_related("account")
    offset = 0
    while True:
        chunk = list(ordered[offset : offset + STREAM_CHUNK])
        if not chunk:
            return
        labels, _wired = _labels_for(chunk)
        earlier = _earlier_counts(chunk)
        for case in chunk:
            yield _shape(case, labels, earlier)
        offset += STREAM_CHUNK


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-142-BRC07 P6.11 wave 2 (R34 disconnect_reconnect; BR-REP-039 PO ruling 2026-09-27 · 12-governance/02-decision-log.md 2026-09-27 §1 · 05-prototype/09 Reports Build Brief.pdf p065 read as an image per B14 rule 42)
# screens: S46
# generated: 2026-09-27 by lane REP-P6-W2
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — `tests/test_rep_p6w2_disconnect_reconnect.py` could not import this module before it existed, and `GET /reports/disconnect_reconnect` answered `work_orders_dataset`'s named refusal.
# exceptions: (0) the latest case per account is picked by a correlated Subquery, not DISTINCT ON — the suite runs on SQLite (law 14) and Django forbids ordering a distinct('account_id') queryset by anything else · (1) the window is repeated INSIDE the subquery so the tiles and the rows describe one population · (2) ELIGIBLE and PAID are NULL with named reasons; neither is computable in this product and BR-REP-039 says so of PAID · (3) `earlier_cases` is declared non-additive · (4) this file writes nothing and declares no address column — the premises is walked (hard rule 8)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Story:    US-PAY-020 (S37 — the batch list and its KPI strip) · US-PAY-021
#           (S38 — the statement import's step-2 review table) · US-PAY-022
#           (S40 — the three tiles a difference is explained against) ·
#           US-PAY-023 (S39 — batch detail: members, bank side, trail)
#           Screens: S37 · S38 · S39 · S40
# Rules:    BR-PAY-004 (a reconciled batch LOCKS — this read says so on every
#           row so a screen never offers a control the service refuses) ·
#           BR-PAY-019 (bank rec in FINANCE; every difference carries a reason
#           AND a GL) · BR-PAY-025 (batches group day × method; the day is the
#           POSTING day) · BR-SHL-011 (list grammar) · BR-TEN-042 (one currency
#           per tenant) · BR-TEN-043 (a business date is an input, never a
#           clock) · CLAUDE.md rule 1 (tenant scoping) · rule 2 (money is
#           NUMERIC(18,6) + CHAR(3) — every amount here travels with its code)
# Tests:    06-backend/tests/test_us_pay_020_023_bankrec_surface.py
# Impacts:  apps/payments/api.py (the eight routes that serve these reads) ·
#           07-frontend/src/features/payments/DepositsPage.tsx (S37) ·
#           BankImportWizard.tsx (S38) · DepositBatchPage.tsx (S39 + the S40
#           modal)
# ───────────────────────────────────────────────────────
"""The READ half of deposits and bank reconciliation — S37 · S38 · S39 · S40.

WHY THIS FILE EXISTS. `apps/payments/reconciliation.py` is a complete,
tested, correct engine that cuts deposit batches, imports a bank statement,
auto-matches it, explains every difference with a reason and a GL, reconciles,
locks and unreconciles — and its own docstring said, in as many words:

    "**NO HTTP SURFACE AND NO SCREEN.** S37 (the batch list), S38 (the import
     wizard), S39 (batch detail) and S40 (the reconcile modal) do not exist,
     and neither does an endpoint. Everything below is reachable only from a
     test or a shell today — *built is not wired* (hard-won law 2)."

Every WRITE that engine offers already had a callable. What nothing had was a
way to SEE the position: which batches exist, what the bank said about each,
what is still unexplained, and what the trail records. A write path with no read
path is a screen that can act and cannot report, so this module is the read and
`apps/payments/api.py` is the door.

════════════════════════════════════════════════════════════════════════════
A ZERO THAT MEANS "I DON'T KNOW" IS NOT WRITTEN HERE
════════════════════════════════════════════════════════════════════════════
`deposit_batches.bank_total` is NULL until a statement line is tied to the
batch, and NULL means *the bank has not shown us this money yet* — the exact
state the prototype's S37 draws as the word "pending" in the Bank-shows column
and "—" in Difference. This module serves `bank_total: None` and
`difference: None` for that row and NEVER `"0.00"`, because a batch in transit
and a batch the bank matched to the penny are different facts and a zero
renders them identically. The KPI strip counts the same way: `in_transit_total`
is its own tile precisely so that money is never added into "matched".

Every amount is a decimal STRING at NUMERIC(18,6) with its CHAR(3) code beside
it (CLAUDE.md rule 2). Nothing here rounds, sums in a float, or formats — the
screen's ONE money formatter does the display rounding (BR-SHL-023).

════════════════════════════════════════════════════════════════════════════
THE KPI STRIP IS COMPUTED OVER THE ROWS IT SHOWS — NOT OVER A CACHE
════════════════════════════════════════════════════════════════════════════
DEF-127's lesson, applied before it could happen again here: an account screen
showed $0.00 while the ledger held an issued, unpaid $108.88, because a cache
nothing filled read as "owes nothing". The tiles are folded over the batches the
list DESCRIBES — never over a stored aggregate and never over a cache
(US-PAY-020 TC-2: *"KPI tiles tie to batch rows exactly"*). The fold is over
`Decimal` on the NUMERIC(18,6) grid and never over a float.

⚠ **"THE ROWS IT SHOWS" MEANS THE FILTERED SET AND NOT THE PAGE, SINCE
2026-09-24 (`DEF-PAY-6554` · `NFR-3` · `P1.2`) — AND THIS PARAGRAPH RECORDED THE
OPPOSITE.** It read *"`batch_kpis` therefore folds the SAME ALREADY-MATERIALISED
list of batches the rows are drawn from — not a second `aggregate()` query — so
the tiles cannot disagree with the rows beneath them"*, and it named its danger
correctly for the world it was written in: at T7 the list WAS the filtered set,
so folding the list folded everything. **Paging pulls the two apart**, and
folding the PAGE would make *In transit* shrink as a clerk walked forward —
four tiles arithmetically right about fifty rows and wrong about the screen.
So `batch_kpis_of` folds the filtered QUERYSET in one grouped `aggregate()`,
`batch_kpis` goes on folding a list for the callers that hand it one, and the
drift the old paragraph feared is answered by building the rows and the tiles
from the SAME queryset object in `batch_list`, two lines apart.

════════════════════════════════════════════════════════════════════════════
WHAT THIS MODULE DOES NOT DO
════════════════════════════════════════════════════════════════════════════
  · **It writes nothing.** Not a status, not a trail row, not an audit row.
    Every write is `reconciliation.py`'s, and this module is imported by the API
    beside it rather than in front of it.
  · **It resolves no GL account by number.** The S40 default account is
    `reconciliation.bank_fees_account_id()` — by DESIGNATION (`bank_fees`),
    which is OQ-106's closure. 6800 is a number in the ❄️ signed chart and not a
    constant in this repo, and the prototype's "6200 Merchant Fees" and
    "1020 Undeposited" are in NO signed chart at all (DEF-067).
  · **It does not name the member payments' customers.** The account NUMBER is
    resolved through customers' own published queryset, by name, never by
    importing their models (B1 / BR-TEN-013) — the shape
    `writeoffs._accounts_by_id` already uses. When customers publishes nothing
    the number comes back None and the row still serves: a batch that refused to
    open because a display field was unreachable would hide a money position.
"""

from __future__ import annotations

import re
from decimal import Decimal
from importlib import import_module
from typing import Any

from django.db.models import Count, Sum

from core import errors
from core import tenancy as core_tenancy

from apps.payments import bankrec_models as bankrec
from apps.payments import models
# `reversed_so_far_by_payment` — the ONE implementation of BR-PAY-884's
# "how much came back" Σ. Imported rather than re-written here (DEF-PAY-6651).
from apps.payments import reconciliation, reversal

ZERO = Decimal("0")

#: What this READ cannot answer, carried on every body so a screen never has to
#: infer an absence (`reconciliation.RECONCILE_UNAVAILABLE`'s discipline, and the
#: same shape `apps/ledger/reporting.py` uses for its four null figures).
#: ⚠ **`grouped_bank_credits_not_matchable` CAME OUT ON 2026-09-01, AND IT WAS
#: ON SCREEN IN ELEVEN LANGUAGES.** It told a clerk *"When your bank posts two of
#: your deposits as one credit, we cannot match them yet. Those deposits will
#: stay unmatched"* (`payments.problem.grouped_bank_credits_not_matchable`), and
#: CR-059 task 45 built exactly that matching — so the panel would have sat on
#: S37/S38 contradicting the Match-set control beside it. The sentence is
#: removed HERE, at the only place that decides whether the screen renders it;
#: ⚠ **and the eleven locale strings, handed to the FRONTEND by this note, were
#: NOT deleted until 2026-09-23 — twenty-two days of a sentence no server could
#: produce (`DEF-PAY-6330`).** They are gone now. The lesson is the handoff
#: rather than the delay: a comment naming another surface's work is a claim
#: nothing re-checks, and catalogue parity stays green over a key the server can
#: never send, so nothing went red for three weeks.
#: ⚠ `unmatched_bank_lines_are_counted_only` came out on 2026-10-30 with its
#: eleven catalogue keys (`DEF-PAY-10694`): G3 was ruled A that day, so a
#: returned line matches its reversal and a fee line posts — see
#: `reconciliation.RECONCILE_UNAVAILABLE`'s note.
BANKREC_UNAVAILABLE: tuple[dict[str, Any], ...] = ()

# ⚠ **`no_deposit_slip_export` WAS THE SECOND ENTRY IN THAT TUPLE UNTIL
# 2026-09-24 AND IS DELETED, NOT REWORDED (`P4.6`).** It read: *"the 'Deposit
# slip for bookkeeper' CSV rides the platform export pipeline (US-SHL-008 /
# IS-9) and `deposit_batches` is not a registered exportable resource. The
# control renders disabled with this reason rather than as a second download
# path."*
#
# Every clause of that was true and the last one is why it goes rather than
# changes: `apps/payments/exports.py` registers `deposits` against that very
# pipeline now, so the reason has stopped being a reason. A gap that outlives
# the gap it describes is CLAUDE.md hard-won law 2's mirror — a refusal over a
# thing that works — and B14 rule 33 removes rationale rather than shortening
# it. Its catalogue key `payments.problem.no_deposit_slip_export` is retired
# from all eleven catalogues in the same commit.


def _tenant_id() -> Any:
    """CLAUDE.md rule 1 — nothing reads a tenant table without `app.tenant_id`.

    Refuses rather than defaulting, exactly as `reconciliation._tenant_id` does:
    a batch list computed with no tenant in scope is blocked by RLS on Postgres
    and would list another utility's banking on SQLite.
    """
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _resolve(module: str, attribute: str, kind: str = "selectors") -> Any:
    """A neighbour's published callable, or None while it has not published one.

    THE SEAM PATTERN, and it is here rather than an import for the reason B1
    gives and DEF-127 paid for: resolved BY NAME AT CALL TIME, so a neighbour
    that has not published yet is an honest None this module reports, never a
    zero it invents.
    """
    try:
        target = import_module(f"apps.{module}.{kind}")
    except ImportError:  # pragma: no cover - the app package always imports
        return None
    found = getattr(target, attribute, None)
    return found if callable(found) else None


def _decimal_str(value: Any) -> str | None:
    """A `NUMERIC(18,6)` as the wire carries it, or None. NEVER a float, never 0.

    None in, None out — and that is the whole rule of this file. `bank_total` is
    NULL for a batch the bank has not shown, and turning that into `"0.00"` is
    the DEF-127 defect: a figure nobody filled rendering as a figure somebody
    counted.
    """
    return None if value is None else f"{Decimal(value):.6f}"


def _iso(value: Any) -> str | None:
    return None if value is None else value.isoformat()


# ── S37 · the batch list ────────────────────────────────────────────────────
#: IS-3's floor, the cost register's own constant (`cost_capture.MIN_SEARCH_CHARS`)
#: written again here rather than imported across a module boundary (B1). One
#: character scans every row of the table to return most of them, which is the
#: opposite of what a search is for.
MIN_SEARCH_CHARS = 2

#: The (sort, dir) vocabulary this list accepts — `core.pagination.order_terms`'
#: shape, every term written ASCENDING and flipped for `desc` so the two
#: directions cannot drift apart.
#:
#: ⚠ **EVERY TUPLE ENDS IN `id`, AND THAT IS THE CALLER'S JOB RATHER THAN THE
#: HELPER'S.** A page is a window over an ORDER; if the order is not total, two
#: batches banked on one day may swap between page 1 and page 2 and a clerk sees
#: one twice and another never.
BATCH_SORTS: dict[str, tuple[Any, ...]] = {
    "deposited_on": ("deposited_on", "created_at", "id"),
    "code": ("code", "id"),
    "recorded_total": ("recorded_total", "id"),
}
#: p048's drawing puts the `⇅` on DATE and draws the newest day first.
BATCH_DEFAULT_SORT = "deposited_on"


def batch_queryset(
    *,
    status: str | None = None,
    method_code: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
) -> Any:
    """The tenant's batches, newest banking day first (US-PAY-020 §capability).

    `deposited_on desc` is the capability matrix's own default sort, and the id
    breaks its ties so two batches on one day never swap places between reads.

    ⚠ **`q` IS `P1.7` AND IT ASKS THREE POPULATIONS, BECAUSE A CLERK HOLDS A
    DEPOSIT SLIP RATHER THAN A BATCH CODE.** p048's filter table names them:
    *"batch code, bank reference, cheque"*. The code is this table's own column;
    the bank reference is the tied `BankLine`'s; the cheque is a member
    payment's `confirmation`. A search that matched only the code would answer
    *"no deposits"* to the number actually in the clerk's hand — which is the
    whole reason the task exists, and why the blueprint records that it
    *"absorbs P3.13, which was the same search"*.

    **The two off-table legs are `IN` subqueries and not joins**, so this stays
    ONE statement and a batch cannot be returned twice by matching two of its
    members. Django renders each as a nested SELECT; neither adds a round trip,
    and the page is still cut in SQL (`NFR-3`).

    An unrecognised `status` REFUSES rather than filtering to nothing: an empty
    list and an unanswerable one look identical on a screen, and a clerk who
    typed a wrong filter would read "no deposits" over a full drawer. **A short
    `q` refuses for the opposite reason** — it is answerable and the answer is
    the whole table.

    An unrecognised `status` REFUSES rather than filtering to nothing: an empty
    list and an unanswerable one look identical on a screen, and a clerk who
    typed a wrong filter would read "no deposits" over a full drawer.

    ⚠ **`P2.10` · ONLY BANKABLE BATCHES — THE TILL BEHIND ONE MAY STILL BE
    OPEN.** `bankrec.BANKABLE` is the condition and `bankrec_models` argues it
    at length; the short form is that since `P0.6` a batch exists from the
    moment its till opens, so filtering on `tenant_id` alone put a drawer that
    is still taking money on Finance → Deposits, indistinguishable from a
    sealed one. **The count it holds back is served beside the rows** by
    `batch_list` and is never a silent zero (hard-won law 7 — *"a declared
    blind spot with no NUMBER attached is indistinguishable from an empty
    one"*).
    """
    from core.pagination import order_terms

    rows = bankrec.bankable(bankrec.DepositBatch.objects.filter(tenant_id=_tenant_id()))
    if status:
        if status not in bankrec.BATCH_STATUSES:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.deposits.status_invalid",
                params={"field": "f.status"},
            )
        rows = rows.filter(status=status)
    if method_code:
        # CR-186-BRC10 — a batch made since 2026-10-21 holds every tender
        # (`method` NULL), so the tender filter also asks its MEMBERS.
        from django.db.models import Q as AnyOf

        rows = rows.filter(
            AnyOf(method__code=method_code)
            | AnyOf(
                method__isnull=True,
                pk__in=models.Payment.objects.filter(
                    tenant_id=_tenant_id(), method__code=method_code
                ).values("deposit_batch_id"),
            )
        )
    term = str(q or "").strip()
    if term:
        if len(term) < MIN_SEARCH_CHARS:
            raise errors.ValidationError(
                errors.VAL_FORMAT,
                message_key="payments.deposits.search_too_short",
                params={"field": "q", "minimum": MIN_SEARCH_CHARS},
            )
        from django.db.models import Q

        rows = rows.filter(
            Q(code__icontains=term)
            | Q(
                pk__in=bankrec.BankLine.objects.filter(
                    tenant_id=_tenant_id(), reference__icontains=term
                ).values("deposit_batch_id")
            )
            | Q(
                pk__in=models.Payment.objects.filter(
                    tenant_id=_tenant_id(), confirmation__icontains=term
                ).values("deposit_batch_id")
            )
        )
    return rows.select_related("method", "session").order_by(
        *order_terms(sort, direction, columns=BATCH_SORTS, default=BATCH_DEFAULT_SORT)
    )


def batch_row(
    batch: bankrec.DepositBatch,
    *,
    payment_count: int | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    """One S37 row — the prototype's nine columns, and the lock state.

    `difference` is None (not zero) whenever `bank_total` is None, because the
    bank has not spoken yet. The prototype draws that cell as "—" beside the
    word "pending" and this row is what lets a screen do the same without
    guessing which of the two absences it is looking at.

    `locked` is served rather than derived on the client from `status ==
    'reconciled'`: BR-PAY-004's lock is the SERVER's fact and a screen that
    computed it would be a second copy of the rule, free to drift the day a
    fifth status arrives.

    ⚠ **`currency` IS RESOLVED ONCE PER LIST AND PASSED IN, AND IT USED TO BE
    ONE ROUND TRIP PER ROW** (`DEF-PAY-6554`, 2026-09-24). `_currency()` reads
    tenancy through the settings seam, and calling it inside the row builder
    cost ~5 statements × 50 rows: **measured at 265 statements to draw one page
    of 50.** BR-TEN-042 locks a tenant to ONE code, so a body cannot span two —
    which is exactly what makes resolving it once correct rather than merely
    cheaper.

    ⚠ **IT IS OPTIONAL AND DEFAULTS TO THE SEAM, SO NOTHING EXISTING MOVES.**
    The other two callers hand this function one batch each and pay one round
    trip, which is what they always paid.
    """
    recorded = batch.recorded_total
    bank_total = batch.bank_total
    return {
        "id": str(batch.pk),
        "code": batch.code,
        # None on a batch made since 2026-10-21 (`CR-186-BRC10`): it holds
        # every tender, and its per-tender totals are on the detail.
        "method_code": getattr(batch.method, "code", None),
        "method_name": getattr(batch.method, "name", None),
        "all_tenders": batch.method_id is None,
        # The provider or channel a system till banks (`invoice_cloud`,
        # `paymentus`, `lockbox`, `office`); None for a person's till.
        "channel": (getattr(batch.session, "channel", None) if batch.session_id else None),
        "deposited_on": _iso(batch.deposited_on),
        "recorded_total": _decimal_str(recorded),
        "bank_total": _decimal_str(bank_total),
        "difference": None if bank_total is None else _decimal_str(bank_total - recorded),
        "currency": currency if currency is not None else _currency(),
        "payment_count": payment_count,
        "status": batch.status,
        "locked": batch.status == bankrec.BATCH_RECONCILED,
    }


def _currency() -> str:
    """The tenant's ONE currency (BR-TEN-042), resolved through the settings seam.

    `deposit_batches` carries no `currency` column — B2 gives it to the payments
    that compose it, and BR-TEN-042 locks a tenant to one code — so a batch
    total's CHAR(3) is the tenant's. Read through the seam and never defaulted to
    "USD" here: a wrong symbol on a Canadian utility's banking is a money defect
    wearing a formatting costume.
    """
    from apps.payments import settings_seam

    return settings_seam.tenant_currency()


def _payment_counts(batch_ids: list[Any]) -> dict[Any, int]:
    """How many payments each batch holds — one grouped query, never N+1.

    Counted from `payments.deposit_batch_id`, which migration 0005 makes
    WRITE-ONCE, so this is the membership itself rather than a cached number
    that could disagree with it.
    """
    if not batch_ids:
        return {}
    rows = (
        models.Payment.objects.filter(tenant_id=_tenant_id(), deposit_batch_id__in=batch_ids)
        .values("deposit_batch_id")
        .annotate(n=Count("id"))
    )
    return {row["deposit_batch_id"]: row["n"] for row in rows}


def batch_kpis(batches: list[bankrec.DepositBatch]) -> dict[str, Any]:
    """S37's four tiles, folded over the EXACT rows the list serves.

    US-PAY-020 TC-2, verbatim: *"KPI tiles (deposited MTD / matched / unmatched
    / in transit) tie to batch rows exactly"*. They tie because this takes an
    ALREADY-MATERIALISED list and folds it in Python. Nothing is stored
    anywhere, which is the discipline `apps/payments/summary.py` keeps for S32
    (*"no stored aggregate anywhere"*) and the answer to DEF-127's cache.

    ⚠ **THE LIST SCREEN NO LONGER CALLS THIS ONE — IT CALLS `batch_kpis_of`
    (`DEF-PAY-6554` · `P1.2`).** This function is kept, unchanged in behaviour,
    for the callers that legitimately hold every batch they care about (the
    reconciliation statement's own set, and the tests that plant a handful).
    Handing it `batch_list`'s PAGE would produce four tiles that are
    arithmetically correct about fifty rows and wrong about the screen.

    **The fold is over `Decimal`, never a float** (CLAUDE.md rule 2). Python's
    `Decimal` addition on the NUMERIC(18,6) grid is exact; `sum()` over floats
    is the shape of every money defect this repo has logged.

    **In-transit money is its own tile and is never folded into "deposited".**
    A batch the bank has not shown is money we believe we banked; a matched one
    is money the bank agrees we banked. Adding them would produce one confident
    figure out of two different facts.
    """

    def _recorded(status: str) -> str:
        total = sum((batch.recorded_total for batch in batches if batch.status == status), ZERO)
        return _decimal_str(total) or "0.000000"

    def _count(status: str) -> int:
        return sum(1 for batch in batches if batch.status == status)

    return {
        "deposited_total": _decimal_str(sum((batch.recorded_total for batch in batches), ZERO)),
        "batch_count": len(batches),
        "matched_total": _recorded(bankrec.BATCH_MATCHED),
        "matched_count": _count(bankrec.BATCH_MATCHED),
        "reconciled_total": _recorded(bankrec.BATCH_RECONCILED),
        "reconciled_count": _count(bankrec.BATCH_RECONCILED),
        "unmatched_total": _recorded(bankrec.BATCH_UNMATCHED),
        "unmatched_count": _count(bankrec.BATCH_UNMATCHED),
        "in_transit_total": _recorded(bankrec.BATCH_IN_TRANSIT),
        "in_transit_count": _count(bankrec.BATCH_IN_TRANSIT),
        "currency": _currency(),
    }


def batch_kpis_of(queryset: Any) -> dict[str, Any]:
    """S37's four tiles over a FILTERED QUERYSET — one grouped statement.

    ⚠ **THIS EXISTS BECAUSE THE LIST IS PAGED (`DEF-PAY-6554` · `NFR-3` ·
    `P1.2`).** The tiles describe the set the clerk has narrowed to, and the
    rows are a window onto that same set. Folding the WINDOW would make *In
    transit* shrink as they walked forward — *"money we believe we banked"*
    changing because somebody turned a page.

    ⚠ **ONE `aggregate()` AND NOT FIVE.** Four statuses × (Σ, count) plus the
    whole-set total is nine figures, and nine round trips is `NFR-3` traded for
    `NFR-3`. `Sum(..., filter=Q(status=…))` is a conditional aggregate the
    database evaluates in one pass, and every `Sum` carries `Coalesce` so an
    empty bucket is `0` rather than `NULL` — which matters, because a `None`
    here would reach a money cell as the word *pending* and claim the bank had
    not shown us money we never banked.

    ⚠ **IT IS BUILT FROM THE SAME QUERYSET OBJECT THE ROWS COME FROM**, which
    is what answers `batch_kpis`' old warning that a second query *"could differ
    the moment a filter, a slice or a race put them out of step"*. The filters
    cannot differ because there is one queryset; the SLICE is applied after this
    call and never before it.

    Every total is a decimal STRING at NUMERIC(18,6) with the tenant's CHAR(3)
    beside it (CLAUDE.md rule 2). The database sums on the NUMERIC grid, which
    is exact — this never sees a float.
    """
    from django.db.models import Q
    from django.db.models.functions import Coalesce

    def _sum(*, status: str | None = None) -> Any:
        where = {} if status is None else {"filter": Q(status=status)}
        return Coalesce(
            Sum("recorded_total", **where),
            ZERO,
            output_field=bankrec.DepositBatch._meta.get_field("recorded_total"),
        )

    def _count(status: str) -> Any:
        return Count("id", filter=Q(status=status))

    # `.order_by()` strips the list's ORDER BY: an aggregate does not need it,
    # and on PostgreSQL an ordering term that is not in the GROUP BY is a cost
    # for nothing.
    folded = queryset.order_by().aggregate(
        deposited_total=_sum(),
        batch_count=Count("id"),
        matched_total=_sum(status=bankrec.BATCH_MATCHED),
        matched_count=_count(bankrec.BATCH_MATCHED),
        reconciled_total=_sum(status=bankrec.BATCH_RECONCILED),
        reconciled_count=_count(bankrec.BATCH_RECONCILED),
        unmatched_total=_sum(status=bankrec.BATCH_UNMATCHED),
        unmatched_count=_count(bankrec.BATCH_UNMATCHED),
        in_transit_total=_sum(status=bankrec.BATCH_IN_TRANSIT),
        in_transit_count=_count(bankrec.BATCH_IN_TRANSIT),
    )
    out: dict[str, Any] = {}
    for key, value in folded.items():
        out[key] = _decimal_str(value) or "0.000000" if key.endswith("_total") else value
    out["currency"] = _currency()
    return out


#: The chips screen 3·1 draws above its table, served rather than typed out in
#: the browser (`P1.4` · `DEF-PAY-6556`).
#:
#: ⚠ **THE SCREEN HELD ITS OWN COPY OF THIS AND THAT IS THE DEFECT.**
#: `DepositsPage.tsx` listed the four statuses as literals, so a fifth added
#: here would be served, filterable and invisible — the row exists, the API
#: answers `f.status` for it, `tsc` and every test pass, and no chip appears.
#: That is hard-won law 2's silent shape, the one `SignupWizard.tsx`'s tick-list
#: taught the repo. The VALUES are the enum itself; the LABEL is a catalogue key
#: the browser resolves, because a server does not speak a clerk's language
#: (BR-SHL-023).
def batch_status_chips() -> list[dict[str, Any]]:
    return [
        {"value": value, "label_key": f"payments.deposits.filter.{_CHIP_KEYS[value]}"}
        for value in bankrec.BATCH_STATUSES
    ]


#: status → the catalogue key's last segment. Spelled out rather than derived by
#: camel-casing, so a status whose key is not a mechanical transform of its
#: value fails HERE — visibly, in one place — instead of resolving to a missing
#: string on screen.
_CHIP_KEYS = {
    bankrec.BATCH_UNMATCHED: "unmatched",
    bankrec.BATCH_IN_TRANSIT: "inTransit",
    bankrec.BATCH_MATCHED: "matched",
    bankrec.BATCH_RECONCILED: "reconciled",
}


def batch_method_chips() -> list[dict[str, Any]]:
    """The tenant's own tenders — `f.method`'s vocabulary (`P1.4`).

    ⚠ **`f.method` HAS BEEN ACCEPTED BY THE QUERY AND TYPED ON THE CLIENT SINCE
    2026-08-16 AND NOTHING EVER PASSED IT** — a dead parameter on a live read,
    which `G13` cannot see because it asks about component props. p048 note 3
    names it: *"+ Filter exposes `f.method`, already accepted by the endpoint
    and the typed client, **with no control**"*.

    These are ROWS and not an enum, so the label is the tenant's own name for
    the tender and travels as text; there is no catalogue key for *Cheque* on a
    utility that calls it something else.
    """
    from apps.tenancy import models as tenancy_models

    return [
        {"value": row.code, "label": row.name}
        for row in tenancy_models.PaymentMethod.objects.filter(
            tenant_id=_tenant_id()
        ).order_by("name", "code")
    ]


def batch_list(
    *,
    status: str | None = None,
    method_code: str | None = None,
    q: str | None = None,
    sort: str | None = None,
    direction: str = "desc",
    offset: int = 0,
    limit: int | None = None,
) -> dict[str, Any]:
    """S37 whole: one page of rows, the tiles over the whole filtered set, and
    the named gaps. ONE queryset behind all three.

    ⚠ **THE PAGE IS TAKEN IN THE DATABASE SINCE 2026-09-24 (`DEF-PAY-6554` ·
    `NFR-3` · `P1.2`), AND THIS DOCSTRING RECORDED THE OPPOSITE AS A DECISION.**
    It read *"Unpaginated for the reason `/outstandings` and `/write-offs` are:
    a utility under 3,000 connections cuts at most a handful of batches a day,
    and a page of a reconciliation list is a list that lies about how much is
    unmatched."* **The ceiling moved to 40,000 on 2026-09-06** and the first
    half stopped being true; the second half is answered rather than overruled —
    the tiles are folded over the FILTERED SET, so the four figures a clerk
    reads say what is unmatched in the whole register whatever page they are on.
    `/outstandings` is the same sentence and was measured at **61.5 seconds
    against a 60-second worker timeout** at the top of T5: not slow, killed
    before it answered.

    `limit=None` serves everything, which is what the callers that are not a
    screen want — the reconciliation statement reads `statement_imports` off
    this body and the tests plant a handful. The VIEW always passes one.
    """
    queryset = batch_queryset(
        status=status, method_code=method_code, q=q, sort=sort, direction=direction
    )
    # The tiles BEFORE the slice, over the same object. See `batch_kpis_of`.
    kpis = batch_kpis_of(queryset)
    total = kpis["batch_count"]
    # ONE currency for the whole body — BR-TEN-042 locks a tenant to one code,
    # so a response cannot span two. See `batch_row`.
    code = kpis["currency"]
    page = queryset[offset : offset + limit] if limit is not None else queryset
    rows = list(page)
    counts = _payment_counts([batch.pk for batch in rows])
    return {
        "rows": [
            batch_row(batch, payment_count=counts.get(batch.pk, 0), currency=code)
            for batch in rows
        ],
        "total": total,
        "kpis": kpis,
        "statuses": batch_status_chips(),
        "methods": batch_method_chips(),
        "still_open": still_open_counters(),
        "unavailable": [dict(gap) for gap in BANKREC_UNAVAILABLE],
    }


def still_open_counters() -> dict[str, Any]:
    """What `batch_queryset` is HOLDING BACK, as a number — never a silence.

    `P2.10` narrowed the Deposits list to bankable batches, which means this
    read now has a blind spot on purpose: the money in tills that are still
    open. **Hard-won law 7's hardest shape is a check reporting zero over a
    scope it silently excludes** — *"a declared blind spot with no NUMBER
    attached is indistinguishable from an empty one, so a check that cannot
    cover its whole subject must print what it skipped beside what it
    checked"*. This is that number, and `DepositsPage` renders it as one line.

    It is deliberately NOT a fifth KPI tile. The four tiles tie to the rows
    beneath them (US-PAY-020 TC-2) and this figure by definition does not —
    it is the money those rows do not contain.

    **It ignores `status` and `method`.** A clerk narrowing the list to
    `matched` is asking about matching, and an open drawer is outside every
    one of those filters; a figure that moved with the filter would read as
    part of the filtered set.

    ⚠ **IT IS ONE AGGREGATE AND IT USED TO BE A PYTHON LOOP** (`DEF-PAY-6554`,
    2026-09-24). The loop read `for batch in held: total += batch.recorded_total`
    — every held batch materialised to produce two integers, on a body whose
    whole point was that the list beside it no longer does that. It was correct
    and it was the same cost in the same response, so paging the rows and
    leaving this would have moved the breach rather than closed it. `Coalesce`
    keeps an empty result at `0` rather than `NULL`: a `None` here would reach a
    money cell and read as *"the bank has not shown this"* over money nobody has
    banked.
    """
    from django.db.models.functions import Coalesce

    held = bankrec.DepositBatch.objects.filter(tenant_id=_tenant_id()).exclude(bankrec.BANKABLE)
    folded = held.order_by().aggregate(
        batch_count=Count("id"),
        recorded_total=Coalesce(
            Sum("recorded_total"),
            ZERO,
            output_field=bankrec.DepositBatch._meta.get_field("recorded_total"),
        ),
    )
    return {
        "batch_count": folded["batch_count"],
        "recorded_total": _decimal_str(folded["recorded_total"]) or "0.000000",
        "currency": _currency(),
    }


# ── S39 · the batch detail ──────────────────────────────────────────────────
def batch_detail(batch_id: Any) -> dict[str, Any]:
    """S39: the header, the members, the bank side, the trail and the resolutions.

    A batch id belonging to another tenant answers ABSENT (BR-TEN-003 / HR-1 —
    a cross-tenant read is a 404, never a 403 that confirms the row exists), and
    that is `_batch`'s refusal below rather than a filter that would have
    returned an empty detail.

    US-PAY-023 TC-1's four panels are the four keys: `members` (Σ =
    recorded_total, asserted by the tests), `bank_line` (the panel that is None
    for an unmatched batch — an absence, not an empty row), `trail` (append-only,
    never truncated, oldest FIRST because a trail is read forwards) and
    `resolutions` (what was explained, with the reason and the GL BR-PAY-019
    requires on every one).

    ══════════════════════════════════════════════════════════════════════════
    `live_total` — WHAT THE MEMBERS STILL STAND FOR (`P3.11`, `DEF-PAY-6651`)
    ══════════════════════════════════════════════════════════════════════════
    A reversal inside a LOCKED batch is lawful — `reversal._refuse_if_batch_locked`
    permits it, because *"the bank statement the batch was agreed against did
    not change"* (PO 2026-08-12, OQ-134) — so `recorded_total` stays frozen while
    the money behind it comes back. The Finance blueprint p049 names the
    consequence: *"a locked batch can end up differing from the sum of its live
    payments — and no screen says so."*

    ⚠ **AND IT CANNOT BE COMPUTED FROM `members` ON THE CLIENT, WHICH IS WHAT
    `DEF-PAY-6651` IS.** The reversing row is created with **no
    `deposit_batch_id`** (`reversal._write_reversal`), and hard rule 4 forbids
    moving the original's `amount` or `status`, so **no member row changes when
    a member is reversed**. Σ`members[].amount` is therefore identically
    `recorded_total` for ever, and a drift computed that way is always `0.00` —
    a tile that would affirm nothing is wrong on a batch that is short.
    Measured: `DEP-260808-0002`, recorded **2,388.84**, one member of **501.33**
    reversed, Σ members still **2,388.84**, live **1,887.51**.

    So the figure is SERVED, summed over `amount − reversed_so_far` in `Decimal`
    on the `NUMERIC(18,6)` grid, and each member carries its own
    `reversed_amount` so a clerk can see WHICH line moved rather than only that
    one did. **This read changes no rule and writes nothing** — p016's own
    words for `P3.11` are *"Show the difference; change no rule"*.
    """
    batch = _batch(batch_id)
    members = list(
        models.Payment.objects.filter(tenant_id=batch.tenant_id, deposit_batch_id=batch.pk)
        .select_related("method")
        .order_by("posted_at", "id")
    )
    accounts = _accounts_by_id([payment.account_id for payment in members])
    # ONE query for every member's reversals, not one per member: a busy till-day
    # batch holds hundreds of payments and `reversed_so_far` per row is the N+1
    # `DEF-PAY-6554` had just taken out of `batch_row`.
    reversed_by_payment = reversal.reversed_so_far_by_payment(
        batch.tenant_id, [payment.pk for payment in members]
    )
    live_total = sum(
        (
            (payment.amount or Decimal("0"))
            - reversed_by_payment.get(str(payment.pk), Decimal("0"))
            for payment in members
        ),
        Decimal("0"),
    )
    line = (
        bankrec.BankLine.objects.filter(tenant_id=batch.tenant_id, deposit_batch=batch)
        .select_related("statement_import", "statement_import__bank_account")
        .first()
    )
    return {
        "batch": batch_row(batch, payment_count=len(members)),
        # NOT folded into `batch_row`: that builder is shared with the LIST and
        # the dashboard, where one aggregate per row is the round trip
        # `DEF-PAY-6554` measured at 265 statements for one page of 50.
        "live_total": _decimal_str(live_total),
        # CR-186-BRC10 ruling 3 — "A batch carries a total per tender". Dana ·
        # 14 Oct: cash 300.00 + cheques 500.00 = 800.00. A cancelled member is
        # not in it (`reconciliation.banked_members`).
        "tender_totals": [
            {**row, "amount": _decimal_str(row["amount"])}
            for row in reconciliation.tender_totals(batch)
        ],
        "members": [
            _member_row(
                payment,
                accounts.get(payment.account_id),
                reversed_amount=reversed_by_payment.get(str(payment.pk), Decimal("0")),
            )
            for payment in members
        ],
        "bank_line": _bank_line_row(line),
        # CS-17 — S39 must show ALL the lines that make up the match, or a batch
        # tied inside a set renders with an empty bank panel and reads as
        # unmatched (the screen contradicting the service, again).
        "match_set": _match_set_panel(batch),
        "trail": _trail_rows(batch),
        "resolutions": _resolution_rows(batch),
        "unavailable": [dict(gap) for gap in BANKREC_UNAVAILABLE],
    }


def _match_set_panel(batch: bankrec.DepositBatch) -> dict[str, Any] | None:
    """The set this batch is tied inside, with every line and every sibling.

    None — never an empty dict — for a batch that is unmatched or tied 1:1: an
    absent panel is the truth, and `{}` renders as a panel that failed to load.
    """
    member = (
        bankrec.BankRecMatchMember.objects.filter(tenant_id=batch.tenant_id, batch=batch)
        .select_related("match_set")
        .first()
    )
    if member is None:
        return None
    record = member.match_set
    lines = list(
        bankrec.BankLine.objects.filter(
            tenant_id=batch.tenant_id, match_members__match_set_id=record.pk
        ).order_by("posted_on", "id")
    )
    siblings = list(
        bankrec.DepositBatch.objects.filter(
            tenant_id=batch.tenant_id, match_members__match_set_id=record.pk
        ).order_by("deposited_on", "id")
    )
    return {
        "match_set_id": str(record.pk),
        "matched_total": _decimal_str(record.matched_total),
        "matched_at": _iso(record.matched_at),
        "note": record.note,
        "currency": _currency(),
        "bank_lines": [
            {
                "bank_line_id": str(row.pk),
                "posted_on": _iso(row.posted_on),
                "reference": row.reference,
                "amount": _decimal_str(row.amount),
                "line_no": row.line_no,
            }
            for row in lines
        ],
        # Every batch in the tie, this one included — S39's *"show all the lines
        # that make up the match"* needs both sides to be readable as one event.
        "batches": [
            {
                "batch_id": str(row.pk),
                "code": row.code,
                "deposited_on": _iso(row.deposited_on),
                "recorded_total": _decimal_str(row.recorded_total),
                "status": row.status,
                "is_this_batch": row.pk == batch.pk,
            }
            for row in siblings
        ],
    }


def _batch(batch_id: Any) -> bankrec.DepositBatch:
    batch = (
        bankrec.DepositBatch.objects.filter(tenant_id=_tenant_id(), pk=batch_id)
        .select_related("method", "session")
        .first()
    )
    if batch is None:
        raise errors.deny_as_not_found()
    return batch


def _accounts_by_id(ids: list[Any]) -> dict[Any, Any]:
    """Customers' own queryset, resolved BY NAME (B1) — never their models."""
    queryset = _resolve("customers", "account_queryset")
    if queryset is None:  # pragma: no cover - customers publishes it
        return {}
    return {account.pk: account for account in queryset().filter(pk__in=ids)}


#: A cheque number standing on its own in the bank's text — three or more
#: digits with no letter or digit glued to either side. `RET1029-01 CHK 4102`
#: gives 4102; `RET1029-01` gives nothing (1029 is part of a word, 01 is two
#: digits), so a reference code is never mistaken for a cheque.
_CHEQUE_IN_TEXT = re.compile(r"(?<![A-Za-z0-9])\d{3,}(?![A-Za-z0-9])")


def cheque_number_in(text: str | None) -> str | None:
    """P1 a2-3 (PO 2026-10-31) — what Match to payment's search opens on.

    The LAST standalone number in the line's own words, or None. It only
    pre-fills a search box the clerk can clear; it matches nothing by itself,
    and `return_candidates` still filters on amount, date and the deposit.
    """
    found = _CHEQUE_IN_TEXT.findall(text or "")
    return found[-1] if found else None


def _money_out_offer(line: bankrec.BankLine) -> dict[str, Any]:
    """LBX-05 / P2 — what an unexplained line the bank took OUT offers, on BOTH
    screens that list it (the import review and Reconciliation): the two
    actions and the search the Match to payment form opens on."""
    out = line.amount < ZERO
    return {
        "actions": ["match_return", "bank_fee"] if out else [],
        "search_hint": cheque_number_in(line.reference) if out else None,
    }


def _payees(originals: list[Any]) -> dict[str, tuple[str | None, str | None]]:
    """P1 a1-3 — `{payment_id: (account NUMBER, customer name)}` for matched returns.

    The account number through customers' own queryset and the name through
    their batched `primary_contact_names_for` — never a customers model, and
    never the account's uuid (B14 rule 31). One query each, whatever the count.
    """
    found = [row for row in originals if row is not None]
    if not found:
        return {}
    account_ids = [row.account_id for row in found]
    accounts = {str(key): value for key, value in _accounts_by_id(account_ids).items()}
    names_for = _resolve("customers", "primary_contact_names_for")
    names = {} if names_for is None else {str(k): v for k, v in names_for(account_ids).items()}
    return {
        str(row.pk): (
            getattr(accounts.get(str(row.account_id)), "account_no", None),
            names.get(str(row.account_id)),
        )
        for row in found
    }


def _member_row(
    payment: models.Payment, account: Any, *, reversed_amount: Decimal | None = None
) -> dict[str, Any]:
    """One payment in the batch — the prototype's five columns.

    `confirmation` is the cheque number the prototype prints as "#4021"; it is
    NULL for cash, and the screen renders that absence rather than an empty
    string that would read as a missing cheque number.

    The payment's OWN `currency` travels with its amount and the batch's
    tenant-level code is not substituted for it: BR-TEN-042 locks a tenant to
    one currency today, and a row that quietly relabelled a figure would be the
    place that lie started.

    ── `memo` AND `reversed_amount` — `P3.10` · `P3.11` ────────────────────
    **`memo` is here because the row is a correction's SOURCE, not only its
    subject.** p049 puts *correct the reference* on this table, and
    `POST /payments/{id}/correct-reference` takes `confirmation` AND `memo`
    (hard rule 4 as narrowed by the PO on 2026-09-02). A form that pre-filled
    the cheque number and left the memo box empty would show a clerk a blank
    where a sentence exists, and the first thing they typed would replace it.

    **`reversed_amount` is POSITIVE and is how much of this payment has come
    back** — `BR-PAY-884`'s Σ, read once for the whole batch. It is what tells
    the reverse row-action whether anything still stands (BR-SHL-025: a control
    that cannot act is disabled WITH its reason), and it is what makes the
    batch's drift attributable to a line instead of only to a total.

    It is `"0.000000"` and never absent: unlike `reversed_so_far_by_payment`'s
    own result, every member here WAS looked at, so zero is a measurement.
    """
    return {
        "payment_id": str(payment.pk),
        "payment_no": payment.payment_no,
        "confirmation": payment.confirmation,
        "memo": payment.memo,
        "account_id": str(payment.account_id),
        "account_no": getattr(account, "account_no", None),
        "amount": _decimal_str(payment.amount),
        "reversed_amount": _decimal_str(
            Decimal("0") if reversed_amount is None else reversed_amount
        ),
        "currency": payment.currency,
        "status": payment.status,
        "posted_at": _iso(payment.posted_at),
        "cleared_at": _iso(payment.cleared_at),
    }


def _bank_line_row(line: Any) -> dict[str, Any] | None:
    """The S39 bank-side panel, or None when no statement line is tied yet.

    None, deliberately, rather than a dict of nulls: "the bank has not shown us
    this deposit" is a STATE the screen draws as its own sentence, and a panel
    of empty fields reads as data that failed to load.
    """
    if line is None:
        return None
    statement = line.statement_import
    account = getattr(statement, "bank_account", None)
    return {
        "bank_line_id": str(line.pk),
        "posted_on": _iso(line.posted_on),
        "reference": line.reference,
        "amount": _decimal_str(line.amount),
        "currency": _currency(),
        "line_no": line.line_no,
        "bank_account_name": getattr(account, "name", None),
        "bank_account_mask": getattr(account, "mask", None),
        "statement_import_id": str(statement.pk) if statement else None,
        "period_start": _iso(getattr(statement, "period_start", None)),
        "period_end": _iso(getattr(statement, "period_end", None)),
    }


def _trail_rows(batch: bankrec.DepositBatch) -> list[dict[str, Any]]:
    """The append-only reconciliation trail (US-PAY-023 TC-4 — kept forever).

    OLDEST FIRST. A trail answers *"what happened to this money, in order?"* and
    a reversed one makes a reader reconstruct the sequence in their head. The
    write side (`reconciliation._trail`) never updates or deletes a row, so this
    is the whole history and not a window on it.

    `detail` is forwarded WHOLE rather than cherry-picked: the writer puts
    `bank_total`, `difference`, `reason_code`, `gl_account_id` and
    `journal_entry_id` in it depending on the event, and a read that picked four
    of the five would silently drop the fifth the day a new event carried it.
    """
    return [
        {
            "id": str(row.pk),
            "event": row.event,
            "occurred_at": _iso(row.occurred_at),
            "actor_id": str(row.actor_id) if row.actor_id else None,
            "detail": dict(row.detail or {}),
        }
        for row in bankrec.DepositBatchEvent.objects.filter(
            tenant_id=batch.tenant_id, batch=batch
        ).order_by("occurred_at", "created_at", "id")
    ]


def _resolution_rows(batch: bankrec.DepositBatch) -> list[dict[str, Any]]:
    """Every explained difference — BR-PAY-019's *reason AND GL*, as written."""
    return [
        {
            "id": str(row.pk),
            "reason_code": row.reason_code,
            "gl_account_id": str(row.gl_account_id) if row.gl_account_id else None,
            "amount": _decimal_str(row.amount),
            "currency": _currency(),
            "note": row.note,
            "journal_entry_id": str(row.journal_entry_id) if row.journal_entry_id else None,
            "actor_id": str(row.actor_id) if row.actor_id else None,
        }
        for row in bankrec.BankRecResolution.objects.filter(
            tenant_id=batch.tenant_id, batch=batch
        ).order_by("created_at", "id")
    ]


# ── S38 · the import wizard's own reads ─────────────────────────────────────
def bank_accounts() -> list[dict[str, Any]]:
    """S38 step 1's picker — the tenant's LIVE bank accounts (B2 r14 #1).

    Only `active=True`, because `import_bank_statement` refuses an inactive one
    by name and a picker that offered it would be a control that fails on
    submit (BR-SHL-025's whole point).
    """
    return [
        {"id": str(row.pk), "name": row.name, "mask": row.mask}
        for row in bankrec.BankAccount.objects.filter(tenant_id=_tenant_id(), active=True).order_by(
            "name", "id"
        )
    ]


def statement_review(statement_import_id: Any) -> dict[str, Any]:
    """S38 step 2 — every bank line with the batch it was tied to, or why not.

    Recomputed from the PERSISTED link (`bank_lines.deposit_batch_id`) rather
    than replayed through `auto_match`: a screen re-opened an hour later, or
    after a human named a pairing by hand, must show what is true NOW. Replaying
    the matcher would re-derive the state the file arrived in and quietly
    contradict the database.

    The four states are the prototype's four KPI tiles:
      `auto`             an amount-equal line linked to its batch, difference 0
      `matched_off_by`   linked by a human, and the difference is still owed an
                         explanation — the prototype's "Off by $100" / "Fees?"
      `needs_a_look`     unlinked, and a batch of ours could plausibly be it
      `not_in_our_system` unlinked, and nothing of ours is close
    """
    statement = (
        bankrec.BankStatementImport.objects.filter(tenant_id=_tenant_id(), pk=statement_import_id)
        .select_related("bank_account")
        .first()
    )
    if statement is None:
        raise errors.deny_as_not_found()
    lines = list(
        bankrec.BankLine.objects.filter(tenant_id=statement.tenant_id, statement_import=statement)
        .select_related("deposit_batch", "deposit_batch__method")
        .order_by("line_no", "id")
    )
    # ⚠ `P2.10` — BANKABLE ONLY. This list is what S38 step 2 offers a human to
    # tie a bank line to BY HAND, and `match_bank_line` refuses an open till's
    # batch by name at the endpoint (`_refuse_if_the_till_is_open`). Without
    # this narrowing the picker offers a choice the service then rejects, which
    # is precisely what this module's own header forbids: *"this read says so on
    # every row so a screen never offers a control the service refuses"*. It is
    # the same `BANKABLE` the Deposits list uses — one expression, every reader.
    open_batches = list(
        bankrec.bankable(
            bankrec.DepositBatch.objects.filter(
                tenant_id=statement.tenant_id,
                status__in=(bankrec.BATCH_IN_TRANSIT, bankrec.BATCH_UNMATCHED),
            )
        )
        .select_related("method")
        .order_by("-deposited_on", "id")
    )
    rows = [_statement_line_row(line) for line in lines]
    return {
        "statement": {
            "id": str(statement.pk),
            "bank_account_name": getattr(statement.bank_account, "name", None),
            "bank_account_mask": getattr(statement.bank_account, "mask", None),
            "period_start": _iso(statement.period_start),
            "period_end": _iso(statement.period_end),
            "file_name": statement.file_name,
            "line_count": statement.line_count,
            "imported_at": _iso(statement.imported_at),
            "imported_by": str(statement.imported_by_id) if statement.imported_by_id else None,
            # CS-14 — the bank's OWN figures, or None. `_decimal_str` returns
            # None for a NULL and never "0.00": a statement imported before
            # 2026-09-01 carries no balances and the screen must say so, not
            # print a bank balance of zero for a live account.
            "opening_balance": _decimal_str(statement.opening_balance),
            "closing_balance": _decimal_str(statement.closing_balance),
        },
        "rows": rows,
        "tiles": {
            "lines": len(rows),
            "auto": sum(1 for row in rows if row["state"] == "auto"),
            "matched_off_by": sum(1 for row in rows if row["state"] == "matched_off_by"),
            "needs_a_look": sum(1 for row in rows if row["state"] == "needs_a_look"),
            "not_in_our_system": sum(1 for row in rows if row["state"] == "not_in_our_system"),
            # CR-059 W8 — two more states, each its own tile so neither is
            # folded into a count that already meant something else.
            "set_matched": sum(1 for row in rows if row["state"] == "set_matched"),
            "explained": sum(1 for row in rows if row["state"] == "explained"),
        },
        # The candidate batches a human picks from when they name a pairing the
        # exact rule could not make (`reconciliation.match_bank_line`). Served
        # with the review so the S38 "Resolve" control has something to offer;
        # an empty list is an honest "there is nothing of ours left to tie".
        "open_batches": [batch_row(batch) for batch in open_batches],
        "currency": _currency(),
        "unavailable": [dict(gap) for gap in BANKREC_UNAVAILABLE],
    }


def _statement_line_row(line: bankrec.BankLine) -> dict[str, Any]:
    batch = line.deposit_batch
    if batch is None:
        # ── CS-17 · a line tied inside a match SET is MATCHED ──────────────
        # Checked BEFORE the near-candidate test, or a line the bank posted as
        # one combined credit would keep rendering as "needs a look" after a
        # clerk had already tied it — the screen contradicting the database.
        member = (
            bankrec.BankRecMatchMember.objects.filter(tenant_id=line.tenant_id, bank_line=line)
            .select_related("match_set")
            .first()
        )
        if member is not None:
            partners = list(
                bankrec.DepositBatch.objects.filter(
                    tenant_id=line.tenant_id, match_members__match_set_id=member.match_set_id
                ).order_by("deposited_on", "id")
            )
            return {
                "bank_line_id": str(line.pk),
                "posted_on": _iso(line.posted_on),
                "reference": line.reference,
                "amount": _decimal_str(line.amount),
                "currency": _currency(),
                "line_no": line.line_no,
                # A set has no single batch, so `batch_id`/`batch_code` stay
                # None and the SET is what the row names. Serving one of the
                # several batches here would be a half-truth the screen would
                # render as the whole answer (B14 rule 31's cousin).
                "batch_id": None,
                "batch_code": None,
                "match_set_id": str(member.match_set_id),
                "match_set_batch_codes": [row.code for row in partners],
                "match_set_total": _decimal_str(member.match_set.matched_total),
                "recorded_total": None,
                # A set ties EXACTLY by rule, so there is no difference to
                # explain — 0.00 here is a computed fact, not a missing figure.
                "difference": "0.000000",
                "state": "set_matched",
            }
        # ── CS-16 · an unmatched line may now be EXPLAINED ─────────────────
        explanation = (
            bankrec.BankRecResolution.objects.filter(tenant_id=line.tenant_id, bank_line=line)
            .select_related("reversal_payment", "reversal_payment__reverses_payment")
            .first()
        )
        if explanation is not None:
            returned = explanation.reversal_payment
            original = None if returned is None else returned.reverses_payment
            payee = _payees([original]).get(str(getattr(original, "pk", "")), (None, None))
            return {
                "bank_line_id": str(line.pk),
                "posted_on": _iso(line.posted_on),
                "reference": line.reference,
                "amount": _decimal_str(line.amount),
                "currency": _currency(),
                "line_no": line.line_no,
                "batch_id": None,
                "batch_code": None,
                "recorded_total": None,
                "difference": None,
                "reason_code": explanation.reason_code,
                "gl_account_id": str(explanation.gl_account_id),
                "explained_amount": _decimal_str(explanation.amount),
                "note": explanation.note,
                # LBX-05 (G3 ruled 2026-10-30) — a matched return and a bank fee
                # are in the books; an ordinary explanation still is not. The
                # row says which rather than leaving a screen to assume.
                "posted": explanation.journal_entry_id is not None,
                "returned_payment_no": None if original is None else original.payment_no,
                "returned_cheque": None if original is None else original.confirmation,
                # P1 a1-3 (PO 2026-10-31) — whose cheque came back:
                # "RET1029-01 → Clara Castillo · AC-2026-00003".
                "returned_account_no": payee[0],
                "returned_customer_name": payee[1],
                "actions": [],
                "state": "explained",
            }
        return {
            "bank_line_id": str(line.pk),
            "posted_on": _iso(line.posted_on),
            "reference": line.reference,
            "amount": _decimal_str(line.amount),
            "currency": _currency(),
            "line_no": line.line_no,
            "batch_id": None,
            "batch_code": None,
            "recorded_total": None,
            "difference": None,
            # LBX-05 — money the bank took OUT always needs a look, and offers
            # its two actions; a credit keeps the near-candidate test.
            **_money_out_offer(line),
            "state": "needs_a_look"
            if line.amount < ZERO or _has_near_candidate(line)
            else "not_in_our_system",
        }
    difference = line.amount - batch.recorded_total
    return {
        "bank_line_id": str(line.pk),
        "posted_on": _iso(line.posted_on),
        "reference": line.reference,
        "amount": _decimal_str(line.amount),
        "currency": _currency(),
        "line_no": line.line_no,
        "batch_id": str(batch.pk),
        "batch_code": batch.code,
        "recorded_total": _decimal_str(batch.recorded_total),
        "difference": _decimal_str(difference),
        "state": "auto" if difference == ZERO else "matched_off_by",
    }


def _has_near_candidate(line: bankrec.BankLine) -> bool:
    """Is there an open batch of OURS this unlinked line could plausibly be?

    The same evidence `reconciliation.auto_match` uses to tell "needs a look"
    from "not in our system", and for the same reason: a batch of the SAME
    AMOUNT four days away is a candidate a human should see, while a credit
    matching nothing of ours at all is the fourth tile. Neither is a match and
    nothing here links anything.
    """
    from datetime import timedelta

    from apps.payments import settings_seam

    tolerance = timedelta(days=settings_seam.match_tolerance_days())
    # ⚠ `P2.10` — BANKABLE ONLY, and this one decides a WORD on the screen. An
    # unlinked line whose only near candidate is a drawer still taking money
    # would be labelled `needs_a_look`, sending a clerk to match it against a
    # batch `match_bank_line` refuses. `not_in_our_system` is the truthful
    # answer until that till is closed. Same expression as the picker above.
    return any(
        batch.recorded_total == line.amount or abs(line.posted_on - batch.deposited_on) <= tolerance
        for batch in bankrec.bankable(
            bankrec.DepositBatch.objects.filter(
                tenant_id=line.tenant_id,
                status__in=(bankrec.BATCH_IN_TRANSIT, bankrec.BATCH_UNMATCHED),
            )
        )
    )


# ════════════════════════════════════════════════════════════════════════════
# CS-14 (CR-059 task 43) — THE RECONCILIATION STATEMENT, AND ITS TIE-OUT
# ════════════════════════════════════════════════════════════════════════════
# ⚠ **THERE IS NO SIGN VECTOR IN THIS MODULE ANY MORE, AND ITS ABSENCE IS THE
# RULING (`OQ-1310` CLOSED, PO 2026-09-02).** `_CS14_SIGNS` lived here until
# that day and carried CS-14's own three signs, with a textbook reading (and,
# on checking the arithmetic to put the question, a third reading nobody had
# named) disagreeing with it by up to 2,244.56 on the one report that decides
# whether a month's reconciliation is proved.
#
# **PO RULING, VERBATIM:** *"we need to go on factual basis, if bank as report
# we count if bank did not report we dont count, and if clark wants to balance
# the book they can always make journal entries on their own - that is
# allowed"*.
#
# **IT DISSOLVES THE QUESTION RATHER THAN PICKING A SIGN.** Deposits in transit
# and outstanding cheques are, by definition, precisely what the bank has NOT
# reported — so on a factual basis neither is counted, and the bank's figure is
# simply the bank's figure. The statement below states TWO FACTS, the bank's
# closing balance (**48,112.40** on CS-14's own example, which already contains
# its 88.00 unexplained line) and the books' cash (**46,946.12**), and lists
# the reconciling items as the EXPLANATION of the **1,166.28** between them —
# never as addends. `1,122.78 − 44.50 + 88.00` is exactly that difference, so
# the items do explain it; a clerk who wants the books moved journals it
# themselves, which the PO's second sentence allows.
#
# **SO NOTHING HERE APPLIES A SIGN TO A RECONCILING ITEM, AND THE WRONG-SIGN
# FAILURE `OQ-1310` WAS ABOUT CANNOT HAPPEN.** A lane re-introducing a `sign`
# or `signed_amount` key, or an adjusted balance, would be re-opening a closed
# question — and would be adjusting a balance toward agreement, which is what
# the ruling forbids (`BR-MET-052`'s posture, *nothing is ever auto-fixed*,
# applied to the books).
#
# **WHAT THIS SUPERSEDES:** `CR-059` CS-14's stated arithmetic (*"…→ adjusted
# bank balance 46,946.12"*) and the `adjusted_bank_balance` figure this module
# served until 2026-09-02.


def _statement(statement_import_id: Any) -> bankrec.BankStatementImport:
    row = (
        bankrec.BankStatementImport.objects.filter(tenant_id=_tenant_id(), pk=statement_import_id)
        .select_related("bank_account")
        .first()
    )
    if row is None:
        raise errors.deny_as_not_found()
    return row


def _book_cash_balance(as_of: Any) -> tuple[str | None, dict[str, Any] | None]:
    """Cash per the BOOKS at `as_of` — the ledger's own answer, or None + why.

    Resolved by NAME through the ledger's published `reporting.cash_position`
    (B1 — payments never reads another module's ORM), and the `cash` DESIGNATION
    is checked FIRST because `cash_position` answers **ZERO** for a tenant that
    has designated no cash account. That zero is DEF-127's exact shape: a figure
    nobody could compute rendering as a figure somebody counted, on the one line
    of the one report that is supposed to prove the bank rec. So an undesignated
    chart returns None with its reason, and the difference below returns None
    too rather than accusing the books of being out by the whole bank balance.

    `realised` is Σ movement on 1000 Cash up to `as_of`, which for an account
    with no opening balance IS the balance. `undeposited` is deliberately not
    added to it — the PO's OQ-143 ruling keeps the two apart and this read is not
    the place to put them back together.
    """
    designation = _resolve("ledger", "gl_account_id_for_designation")
    position = _resolve("ledger", "cash_position", "reporting")
    if not callable(designation) or not callable(position):
        return None, {
            "code": "book_cash_unreadable",
            "br_ref": "B1 · CS-14",
            "detail": "the ledger publishes no cash position, so the books' side of this "
            "statement cannot be read and the tie-out is not computed. Nothing is assumed to be "
            "zero.",
        }
    if designation("cash") is None:
        return None, {
            "code": "no_cash_account_designated",
            "br_ref": "OQ-110 · CS-14",
            "detail": "this utility's chart of accounts designates no `cash` account, so there "
            "is no book balance to compare the bank against. The figure is served as UNKNOWN "
            "rather than 0.00 — a chart nobody mapped is not a bank account holding nothing.",
        }
    answer = position(end=as_of)
    return _decimal_str(answer.get("realised")), None


def _age_days(as_of: Any, when: Any) -> int | None:
    """How old a reconciling item is AT THE STATEMENT'S OWN PERIOD END.

    ⚠ **`as_of` IS THE STATEMENT'S `period_end` AND NEVER A CLOCK** (BR-TEN-043
    — a business date is an input). A statement proves one month, and an age
    measured from today would make the same proved month read differently every
    time it is re-opened; re-printing March's reconciliation in June would show
    every item ninety days older than the person who signed it saw.

    None when either date is missing, which is the module's rule everywhere: an
    age nobody can compute is not zero days old.
    """
    if as_of is None or when is None:
        return None
    return (as_of - when).days


def _in_transit_row(batch: bankrec.DepositBatch, *, as_of: Any) -> dict[str, Any]:
    """One deposit the bank has not shown, with its age — S37's own row, aged.

    `code` (`DEP-260808-CHK`) is the LABEL a clerk reads; `id` rides alongside so
    a screen can link to S39, and B14 rule 31 is satisfied because the id is
    never the VALUE of a displayed field.
    """
    return {
        "id": str(batch.pk),
        "code": batch.code,
        "deposited_on": _iso(batch.deposited_on),
        "amount": _decimal_str(batch.recorded_total),
        "age_days": _age_days(as_of, batch.deposited_on),
    }


def _outstanding_refund_row(refund: Any, *, as_of: Any) -> dict[str, Any]:
    """One issued refund cheque the bank has not paid, with its age.

    `issued_at` can be NULL on a refund issued before that column was filled, so
    `age_days` is None there rather than measured from a date nobody recorded.
    """
    issued_on = None if refund.issued_at is None else refund.issued_at.date()
    return {
        "id": str(refund.pk),
        "reference": refund.reference,
        "issued_on": _iso(issued_on),
        "amount": _decimal_str(refund.amount),
        "age_days": _age_days(as_of, issued_on),
    }


def _unexplained_line_row(line: bankrec.BankLine, *, as_of: Any) -> dict[str, Any]:
    """One statement line neither matched nor explained, with its age."""
    return {
        "bank_line_id": str(line.pk),
        "line_no": line.line_no,
        "posted_on": _iso(line.posted_on),
        "reference": line.reference,
        "amount": _decimal_str(line.amount),
        "age_days": _age_days(as_of, line.posted_on),
        # P2 = A (PO 2026-10-31) — a returned or fee line still unexplained
        # after the import offers Match to payment and Bank fee HERE too.
        **_money_out_offer(line),
    }


def _reconciling_item(
    code: str, rows: list[dict[str, Any]], total: Decimal, *, as_of: Any
) -> dict[str, Any]:
    """One EXPLANATION of the gap — a total, a count, and every row's own age.

    ⚠ **NO `sign` AND NO `signed_amount`.** The PO's 2026-09-02 ruling on
    `OQ-1310` makes these items the explanation of the difference and never
    addends to either side, so nothing here says which way an item would move a
    balance — because nothing here moves one.

    **AGED AND ACTIONABLE IS THE OTHER HALF OF THE RULING'S SAFETY.** A deposit
    in transit that never arrives is a real problem and the only thing that says
    so is its age, so every row carries one and the group carries the oldest.
    Rows are OLDEST FIRST for the same reason a trail is: the item that needs
    acting on is the one at the top.

    Every row is served, with no cap — a statement's unexplained lines are
    bounded by its own import, and `statement_review` beside this already serves
    all of them. A truncated list on a reconciliation would hide exactly the
    stale item this is for.
    """
    ages = [row["age_days"] for row in rows if row["age_days"] is not None]
    return {
        "code": code,
        "amount": _decimal_str(total),
        "count": len(rows),
        "as_of": _iso(as_of),
        "oldest_age_days": max(ages) if ages else None,
        "rows": sorted(
            rows,
            key=lambda row: (row["age_days"] is None, -(row["age_days"] or 0)),
        ),
    }


def _posted_lines(resolutions: Any, lines: list[Any]) -> dict[str, Any]:
    """LBX-05 — this statement's lines that were matched to a return or posted as a fee."""
    by_id = {line.pk: line for line in lines}
    resolutions = list(resolutions)
    payees = _payees(
        [
            row.reversal_payment.reverses_payment
            for row in resolutions
            if row.reversal_payment is not None and row.bank_line_id in by_id
        ]
    )
    rows: list[dict[str, Any]] = []
    total = ZERO
    for row in resolutions:
        line = by_id.get(row.bank_line_id)
        if line is None or row.journal_entry_id is None:
            continue
        returned = row.reversal_payment
        original = None if returned is None else returned.reverses_payment
        total += row.amount
        rows.append(
            {
                "bank_line_id": str(line.pk),
                "line_no": line.line_no,
                "posted_on": _iso(line.posted_on),
                "reference": line.reference,
                "amount": _decimal_str(row.amount),
                "kind": "returned_item" if returned is not None else "bank_fee",
                "payment_no": None if original is None else original.payment_no,
                "cheque": None if original is None else original.confirmation,
                # P1 a1-3 — the account NUMBER and the customer's name.
                "account_no": payees.get(str(getattr(original, "pk", "")), (None, None))[0],
                "customer_name": payees.get(str(getattr(original, "pk", "")), (None, None))[1],
            }
        )
    rows.sort(key=lambda item: (item["line_no"] is None, item["line_no"] or 0))
    return {"amount": _decimal_str(total), "count": len(rows), "rows": rows}


def reconciliation_statement(statement_import_id: Any) -> dict[str, Any]:
    """CS-14 — *"the tie-out that cannot be done today"*, for one statement.

    **Why it is keyed on the STATEMENT IMPORT and not on (account, period).**
    The two balances live on the import row, and a corrected statement is a
    SECOND import of the same account and period (BR-PAY-028 blocks only the
    same bytes). Keyed on the period, this read would have to pick one of two
    imports and would pick silently; keyed on the import, the caller says which
    statement it is proving and the answer is about that statement.

    **IT STATES TWO FACTS AND EXPLAINS WHAT LIES BETWEEN THEM — it does not
    adjust either one.** PO ruling 2026-09-02, `OQ-1310` CLOSED, verbatim: *"we
    need to go on factual basis, if bank as report we count if bank did not
    report we dont count, and if clark wants to balance the book they can always
    make journal entries on their own - that is allowed"*.

    So the body carries `bank_closing_balance` — the bank's own figure, counted
    exactly as reported — and `book_cash_balance`, the ledger's own answer, and
    `difference_bank_less_books` between them. **The reconciling items are the
    EXPLANATION of that difference and are never added to either side**, because
    a deposit in transit and an outstanding cheque are by definition precisely
    what the bank has NOT reported. On CS-14's own example the bank says
    48,112.40, the books say 46,946.12, and the 1,166.28 between them is exactly
    the three items (`1,122.78 − 44.50 + 88.00`) — listed, aged and actionable,
    with the clerk free to journal the difference themselves.

    ⚠ **NOTHING IS SILENTLY MOVED TOWARD AGREEMENT.** There is no adjusted
    balance on this body and no sign on any item; a product that quietly nudged
    one side until it matched the other would be auto-fixing the books, which is
    `BR-MET-052`'s posture on a meter read applied to money. **This supersedes
    `CR-059` CS-14's stated arithmetic**, which this read reproduced to the cent
    until 2026-09-02.

    **Every figure is assembled from rows that ALREADY EXIST** — CS-14's own
    sentence. Nothing here is stored, cached or recomputed on a schedule:
    deposits in transit are the S37 tile's own batches, the unexplained lines are
    this import's own lines, and the outstanding refund cheques are refunds in
    `issued`. So the statement cannot disagree with the screens it sits beside.

    **UNKNOWN IS NOT ZERO, ANYWHERE ON THIS BODY.** A statement with no closing
    balance serves `bank_closing_balance: null` and
    `difference_bank_less_books: null`, not `0.00`; a chart with no designated
    cash account serves `book_cash_balance:
    null`. Every one of those absences carries its reason in `unavailable`,
    because a reconciliation that reads as "difference 0.00" when it means "we
    could not do the sum" is worse than no report at all (DEF-127, and CS-13
    shipped the same lesson a fortnight ago).
    """
    statement = _statement(statement_import_id)
    tenant_id = statement.tenant_id
    period_end = statement.period_end
    gaps: list[dict[str, Any]] = []

    # ── deposits in transit — money WE banked that the bank has not shown ──
    # The S37 tile's own definition (`batch_kpis.in_transit_total`), narrowed to
    # the period so a statement proves its own month.
    # ⚠ `P2.10` — BANKABLE ONLY, because this figure CITES the S37 tile as its
    # definition and that tile now folds bankable rows alone. Money still in a
    # clerk's drawer was never banked, so it is not "money WE banked that the
    # bank has not shown" by this figure's own words — and counting it here
    # would make the statement disagree with the screen it sits beside, which
    # the docstring above forbids in as many words.
    in_transit = list(
        bankrec.bankable(
            bankrec.DepositBatch.objects.filter(
                tenant_id=tenant_id,
                status=bankrec.BATCH_IN_TRANSIT,
                deposited_on__lte=period_end,
            )
        )
    )
    deposits_in_transit = sum((batch.recorded_total for batch in in_transit), ZERO)

    # ── outstanding refund cheques — issued, and the bank has not paid them ──
    # `issued` is the ONE refund state in which money has left the books and not
    # the bank (`cleared` is the bank confirming it; `void` never left).
    #
    # ⚠ **ONE LIST, USED FOR BOTH THE TOTAL AND THE COUNT (DEF-3200).** Until
    # 2026-09-02 the amount was summed over refunds issued ON OR BEFORE
    # `period_end` and the count was `.count()` over EVERY issued refund, so a
    # cheque written after the period end raised the count and not the money and
    # the statement showed "4 cheques · 44.50" where three of them were 44.50.
    # Two figures from two sets is DEF-127's shape again; they come off one list
    # now and cannot disagree.
    outstanding = [
        row
        for row in models.Refund.objects.filter(tenant_id=tenant_id, status=models.REFUND_ISSUED)
        if row.issued_at is None or row.issued_at.date() <= period_end
    ]
    outstanding_refunds = sum((row.amount for row in outstanding), ZERO)

    # ── unexplained lines — this statement's own lines that are neither
    # matched (1:1 or in a set) nor explained. CS-16 is what makes this figure
    # able to fall to zero at all: before it, no line could be explained.
    lines = list(
        bankrec.BankLine.objects.filter(tenant_id=tenant_id, statement_import=statement)
        .select_related("deposit_batch")
        .order_by("line_no", "id")
    )
    in_a_set = set(
        bankrec.BankRecMatchMember.objects.filter(
            tenant_id=tenant_id, bank_line__in=[row.pk for row in lines]
        ).values_list("bank_line_id", flat=True)
    )
    explained_rows = {
        row.bank_line_id: row
        for row in bankrec.BankRecResolution.objects.filter(
            tenant_id=tenant_id, bank_line__in=[row.pk for row in lines]
        ).select_related("reversal_payment", "reversal_payment__reverses_payment")
    }
    unexplained = [
        row
        for row in lines
        if row.deposit_batch_id is None and row.pk not in in_a_set and row.pk not in explained_rows
    ]
    unexplained_lines = sum((row.amount for row in unexplained), ZERO)

    # ── explained but NOT POSTED (batch decision G3) — its own line, never
    # folded into the tie-out. An explanation records WHY the bank moved money
    # we did not; until G3 rules whether that writes a journal entry, the books
    # have not caught up and pretending otherwise would hide a real difference.
    explained_unposted = sum(
        (
            row.amount
            for row in explained_rows.values()
            if row.journal_entry_id is None and row.bank_line_id in {one.pk for one in lines}
        ),
        ZERO,
    )
    if explained_unposted != ZERO:
        gaps.append(
            {
                "code": "explained_lines_are_not_posted",
                "br_ref": "batch decision G3 · CS-16",
                "detail": "these lines carry a reason and a GL account and NOTHING was posted "
                "from them — only a matched return and a bank fee post (G3, ruled 2026-10-30; "
                "an ordinary explanation stays recorded, lane judgment LBX-05). They are a "
                "real difference between the bank and the books and are shown on their own line "
                "rather than inside the tie-out.",
            }
        )

    closing = statement.closing_balance
    if closing is None:
        gaps.append(
            {
                "code": "no_closing_balance_captured",
                "br_ref": "CS-14",
                "detail": "this statement was imported without the bank's opening and closing "
                "balances — every import made before 2026-09-01 was, and nothing backfills them. "
                "The reconciling items below are real; the bank's own figure and the difference "
                "are served as UNKNOWN rather than as 0.00, and re-importing the same file is "
                "refused by BR-PAY-028, so the balances arrive with the next statement.",
            }
        )

    book_cash, book_gap = _book_cash_balance(period_end)
    if book_gap is not None:
        gaps.append(book_gap)

    # ⚠ **TWO FACTS SUBTRACTED, AND NOTHING ELSE (PO ruling 2026-09-02).** No
    # reconciling item is added to either side; the key SAYS which way round the
    # subtraction runs so a screen cannot render it with the sign reversed —
    # which is the failure `OQ-1310` was raised about.
    difference = (
        None
        if closing is None or book_cash is None
        else _decimal_str(Decimal(closing) - Decimal(book_cash))
    )

    return {
        "statement": {
            "id": str(statement.pk),
            "bank_account_name": getattr(statement.bank_account, "name", None),
            "bank_account_mask": getattr(statement.bank_account, "mask", None),
            "period_start": _iso(statement.period_start),
            "period_end": _iso(statement.period_end),
            "opening_balance": _decimal_str(statement.opening_balance),
            "closing_balance": _decimal_str(statement.closing_balance),
        },
        # Each reconciling item as a RAW total, its count and every row's own
        # age. No sign and no signed amount: these EXPLAIN the difference, they
        # are not addends to either side (PO ruling 2026-09-02, OQ-1310).
        "reconciling_items": [
            _reconciling_item(
                "deposits_in_transit",
                [_in_transit_row(batch, as_of=period_end) for batch in in_transit],
                deposits_in_transit,
                as_of=period_end,
            ),
            _reconciling_item(
                "outstanding_refunds",
                [_outstanding_refund_row(row, as_of=period_end) for row in outstanding],
                outstanding_refunds,
                as_of=period_end,
            ),
            _reconciling_item(
                "unexplained_lines",
                [_unexplained_line_row(row, as_of=period_end) for row in unexplained],
                unexplained_lines,
                as_of=period_end,
            ),
        ],
        "explained_not_posted": {
            "amount": _decimal_str(explained_unposted),
            "count": sum(1 for row in explained_rows.values() if row.journal_entry_id is None),
        },
        # LBX-05 (G3 RULED 2026-10-30) — lines that ARE in the books: a returned
        # cheque matched to its reversal (holding → cash) and the bank's fee
        # (Bank fees ← cash). Already inside `book_cash_balance`, so listed as
        # what was settled and never as a reconciling item.
        "posted_lines": _posted_lines(explained_rows.values(), lines),
        # THE BANK'S OWN FIGURE, COUNTED AS REPORTED — the same number as
        # `statement.closing_balance` beside it, served on the tie-out line too
        # so a screen reads both facts off the same level of the body and cannot
        # take one of them from somewhere else.
        "bank_closing_balance": _decimal_str(closing),
        "book_cash_balance": book_cash,
        "difference_bank_less_books": difference,
        # ⚠ **A FACT, NOT A VERDICT — and it REPLACED `reconciled` on
        # 2026-09-02.** The old key meant *"book + reconciling items = the
        # bank's closing figure"*, which is the arithmetic the PO's ruling
        # dissolved. This one says only whether the two facts are the same
        # number. A period with legitimate deposits in transit is properly
        # reconciled and will read False here, so a screen must never label it
        # "not reconciled" — the reconciling items beside it are the answer, and
        # a clerk decides. None — never False — when the comparison could not be
        # made, because "we cannot say" and "they differ" are different answers.
        "bank_equals_books": None if difference is None else Decimal(difference) == ZERO,
        "currency": _currency(),
        "unavailable": [dict(gap) for gap in (*BANKREC_UNAVAILABLE, *gaps)],
    }


# ════════════════════════════════════════════════════════════════════════════
# CS-18 (CR-059 task 46) — DIFFERENCES BY REASON AND GL ACCOUNT
# ════════════════════════════════════════════════════════════════════════════
def difference_reasons() -> list[dict[str, Any]]:
    """The tenant's own reconciliation difference reasons — S40's picker.

    Active rows only: a deactivated reason must not be offered for a NEW
    explanation, and every explanation already written under it still reads
    correctly because `bank_rec_resolutions.reason_code` stores the code as text
    (BR-TEN-034's shape, applied to a money vocabulary).
    """
    return [
        {
            "code": row.code,
            "name": row.name,
            "default_gl_account_id": (
                str(row.default_gl_account_id) if row.default_gl_account_id else None
            ),
            "is_system": row.is_system,
        }
        for row in bankrec.BankRecDifferenceReason.objects.filter(
            tenant_id=_tenant_id(), active=True
        ).order_by("name", "id")
    ]


def difference_report(*, start: Any, end: Any) -> dict[str, Any]:
    """CS-18's report — *how much was processor fees this quarter, how much error*.

    Grouped by **reason AND GL account together**, because BR-PAY-019 makes that
    PAIR the control: the same reason posted to two accounts is two different
    facts about the books, and collapsing them would hide the one a finance user
    is looking for.

    **The date each row is counted under is the MONEY's date, not the keying
    date** — a batch resolution takes its batch's banking day and a line
    resolution takes the bank line's posted day. `created_at` would answer "when
    did somebody type this", which is a different question and the wrong one for
    a quarter's totals: an explanation keyed in October about September's
    statement belongs in September.

    Every amount is SIGNED, exactly as the stored column is: a processor fee is
    negative (the bank credited less than we recorded) and a bank interest
    credit is positive. Nothing here takes an absolute value — a report that
    added a −147.50 fee to a +12.00 interest credit as 159.50 would describe a
    difference nobody had.
    """
    tenant_id = _tenant_id()
    rows = list(
        bankrec.BankRecResolution.objects.filter(tenant_id=tenant_id)
        .select_related("batch", "bank_line")
        .order_by("reason_code", "id")
    )
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    counted = 0
    for row in rows:
        when = (
            row.batch.deposited_on
            if row.batch_id is not None
            else (row.bank_line.posted_on if row.bank_line_id is not None else None)
        )
        if when is None or when < start or when > end:
            continue
        counted += 1
        key = (row.reason_code, str(row.gl_account_id))
        bucket = groups.setdefault(
            key,
            {
                "reason_code": row.reason_code,
                "gl_account_id": str(row.gl_account_id),
                "total": ZERO,
                "count": 0,
                "batch_count": 0,
                "line_count": 0,
                "posted_count": 0,
            },
        )
        bucket["total"] += row.amount
        bucket["count"] += 1
        bucket["batch_count"] += 1 if row.batch_id is not None else 0
        bucket["line_count"] += 1 if row.bank_line_id is not None else 0
        bucket["posted_count"] += 1 if row.journal_entry_id is not None else 0

    ordered = sorted(groups.values(), key=lambda item: (item["reason_code"], item["gl_account_id"]))
    labels = _account_labels([item["gl_account_id"] for item in ordered])
    return {
        "period_start": _iso(start),
        "period_end": _iso(end),
        "rows": [
            {
                **item,
                "total": _decimal_str(item["total"]),
                "gl_account_code": labels.get(item["gl_account_id"], {}).get("code"),
                "gl_account_name": labels.get(item["gl_account_id"], {}).get("name"),
            }
            for item in ordered
        ],
        "total": _decimal_str(sum((item["total"] for item in ordered), ZERO)),
        "resolution_count": counted,
        "currency": _currency(),
        "unavailable": [dict(gap) for gap in BANKREC_UNAVAILABLE],
    }


def _account_labels(account_ids: list[str]) -> dict[str, dict[str, str]]:
    """The ledger's own code and name per account — B14 rule 31's requirement.

    *"No database id is ever the visible value of a field."* A difference report
    whose only account column was a uuid would breach that rule on every row, so
    the labels are resolved by NAME through the ledger's published selector and
    an unresolvable id simply comes back without a label rather than failing the
    report (the `_accounts_by_id` posture already in this file).
    """
    if not account_ids:
        return {}
    read = _resolve("ledger", "account_labels")
    if not callable(read):
        return {}
    return {str(key): value for key, value in (read(account_ids) or {}).items()}


def statement_imports(limit: int = 50) -> list[dict[str, Any]]:
    """The statements already loaded — S38 step 1's "or open a past import".

    Newest first, and it exists so a clerk who uploaded a file yesterday can
    reopen its review instead of re-uploading it into BR-PAY-028's refusal.
    """
    return [
        {
            "id": str(row.pk),
            "bank_account_name": getattr(row.bank_account, "name", None),
            "period_start": _iso(row.period_start),
            "period_end": _iso(row.period_end),
            "file_name": row.file_name,
            "line_count": row.line_count,
            "imported_at": _iso(row.imported_at),
        }
        for row in bankrec.BankStatementImport.objects.filter(tenant_id=_tenant_id())
        .select_related("bank_account")
        .order_by("-imported_at", "-id")[:limit]
    ]


def cuttable_days(limit: int = 14) -> list[dict[str, Any]]:
    """Drawer days with cleared money nobody has banked yet (US-PAY-020 entry).

    S37's "Cut today's deposits" needs a DAY, and BR-TEN-043 forbids this
    product reading a clock to pick one. So the days are computed from the
    payments themselves — every POSTING day (BR-PAY-025 / PO ruling RQ-5, never
    the clearing day) that still holds cleared, positive, unbatched money — and
    the clerk chooses from what is actually there.

    That is also why the control can be honest when there is nothing to do: an
    empty list means every day's takings are already in a batch, which is a
    different sentence from "we could not work out what today is".
    """
    rows = (
        models.Payment.objects.filter(
            tenant_id=_tenant_id(),
            # CR-186-BRC10 — new payments are `posted` and are banked at
            # posting; what is left here is the cut's stragglers.
            status__in=(models.PAYMENT_POSTED, models.PAYMENT_CLEARED),
            type=models.PAYMENT_TYPE_PAYMENT,
            deposit_batch_id__isnull=True,
            amount__gt=ZERO,
        )
        .annotate(day=_posting_day())
        .values("day")
        .annotate(amount=Sum("amount"))
        .order_by("-day")[:limit]
    )
    return [
        {
            "day": _iso(row["day"]),
            "unbatched_total": _decimal_str(row["amount"]),
            "currency": _currency(),
        }
        for row in rows
        if row["day"] is not None
    ]


def _posting_day() -> Any:
    """`posted_at::date` — the POSTING day, in UTC, which is what B2 stores.

    BR-PAY-025 and the PO's RQ-5 ruling make the batch day the physical drawer
    day, and `reconciliation.cut_deposit_batches` filters on `posted_at__date`.
    This annotation must agree with that filter exactly or the screen would
    offer a day the cutter then finds empty. **A tenant west of UTC banking at
    6pm local lands on the next UTC day — that is OQ-153, already open**, named
    here rather than papered over with an invented conversion.
    """
    from django.db.models.functions import TruncDate

    return TruncDate("posted_at")


def default_fee_account() -> dict[str, Any]:
    """The GL account S40 pre-selects for a processor fee — BY DESIGNATION.

    `reconciliation.bank_fees_account_id()` reads the tenant's `bank_fees`
    designation (OQ-106's closure), which is **6800 Bank fees** in the ❄️
    finance-signed chart. The NUMBER is never written here and never sent to the
    client as a default: the chart is tenant-customisable (US-LED-005), and the
    prototype's "6200 Merchant Fees" and "1020 Undeposited" are in NO signed
    chart at all — B5 line 74 has 6800 Bank fees, 1000 Cash and 1010 Undeposited
    funds and no 6200 (DEF-067).

    `available: false` when the tenant has designated none. The screen then
    refuses to pre-fill and asks for an account — it does not substitute one,
    because a difference posted to a bucket finance did not designate is exactly
    what BR-PAY-019's reason-AND-GL rule exists to prevent.
    """
    from apps.payments import reconciliation

    account_id = reconciliation.bank_fees_account_id()
    return {
        "available": account_id is not None,
        "gl_account_id": str(account_id) if account_id is not None else None,
        "designation": "bank_fees",
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-PAY-020@5b2e814 (sha1[:7] of the sources this slice was authored from, concatenated in order: 04-docs/05-modules/08-payments/06-epics/EP-PAY-06-deposits-bank-rec.md — US-PAY-020 §1/§3/§5, US-PAY-021, US-PAY-022, US-PAY-023 — · 04-docs/05-modules/08-payments/02-business-rules.md BR-PAY-004/019/025/035/040 · 08-qa/01-e2e/journeys/J14-lockbox-day.md + J5-month-end.md · 05-prototype/UtilityBilling.html lines 3802-3830, 4021-4090, 5568-5600; co-packets US-PAY-021, US-PAY-022, US-PAY-023, same sources)
# generated: 2026-08-16 by story-coder (payments SURFACE lane — the read half a complete bank-rec engine had never had)
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: RED PROVED FIRST — tests/test_us_pay_020_023_bankrec_surface.py failed with ModuleNotFoundError: No module named 'apps.payments.bankrec_read' and Resolver404 on every one of the eight paths before this file and the routes existed; verbatim in the lane report. ruff✔ black✔ · pytest tests -m isolation✔ · run_gates✔
# exceptions: (1) `bank_total` and `difference` are served NULL for a batch the bank has not shown and NEVER "0.00" — DEF-127's defect is a figure nobody filled reading as one somebody counted, and "in transit" is its own KPI tile for the same reason · (2) the KPI strip is computed over the SAME queryset the rows come from, stored nowhere, so US-PAY-020 TC-2's tie-out cannot drift · (3) `default_fee_account` answers by DESIGNATION and serves `available:false` rather than substituting an account — the prototype's 6200/1020 are in no signed chart (DEF-067) · (4) OQ-161's many-to-one matching is CONFIRMED law and unbuilt in the engine; every body carries the gap so a clerk is told before they open a batch that can never tie · (5) `cuttable_days` reads `posted_at::date` in UTC to agree exactly with `cut_deposit_batches`' own filter — the tenant-timezone half is OQ-153, open, and is named rather than converted
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

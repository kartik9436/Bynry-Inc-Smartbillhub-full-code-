# ── Trace ──────────────────────────────────────────────
# Rules:   BR-RAT-1048 (a flat amount is ONE *All sizes* row) · BR-RAT-1049
#          (price rows dated, logically killed, never deleted) · BR-RAT-1050
#          (ONE lookup: exactly one row, or a named refusal; class beats every
#          class) · BR-RAT-088 (the charge code owns the base) · BR-RAT-690
#          (the three states of a size row — validation half, unchanged)
# Change:  CR-156-BRC10 (PO 2026-10-01 — decision log rows whose last column
#          reads "charge-code redesign")
# Tests:   06-backend/tests/test_cr156_charge_prices.py (sqlite + PostgreSQL)
# Gate:    10-scripts/gates/ — fails any `ChargeCodeAmount.objects` or
#          `legacy_amount` outside this file and the migrations
# ───────────────────────────────────────────────────────
"""🔒 HUMAN-OWNED · HUMAN-REVIEW-PENDING — rating math (B4 implementation, not a signed
figure). Row in `12-governance/09-human-review-ledger.md`
(*"2026-10-01 · CHARGE-CODE PRICES DATED"*).

**THE ONE PLACE A CHARGE CODE'S PRICE IS READ OR WRITTEN.**

PO 2026-10-01, the GO for the build: **19 read places must return exactly one
price row**, guaranteed by three locks — *"a database rule refusing overlapping
live rows, ONE shared lookup price on date (code, size, class, date) that all 19
call, and a repo gate failing any direct query of the price table"*. This file
is the second lock and the writer the third lock allows.

WHAT A PRICE ROW IS NOW
-----------------------
`charge_code_amounts` holds every price a code has ever stated:

  * a SIZED price — `size_class` is a `service_size_classes` code;
  * the FLAT price — `size_class` is `constants.ALL_SIZES` (PO, option A:
    *"BASE-S $9.00 is stored as one row in charge_code_amounts with size \"All
    sizes\""*); one per customer class where the code is priced by class;
  * each with `effective_from` / `effective_to` (NULL = no end), and a
    `killed_at` mark once a later edit closed it.

A row is IN FORCE on day D when `effective_from ≤ D ≤ effective_to`. A killed
row is still in force on its own dates — *"A past bill reads the row in force on
its dates"* — which is why the reads below never filter on `killed_at`.

THE RULES THE LOOKUP APPLIES (all of them older than this file, moved here)
--------------------------------------------------------------------------
1. **A class-specific row beats the every-class row** for the same size
   (`CR-087` A1; it lived in `resolution_catalogue` and `selectors.base_charge_
   from_charge_code` — two copies, now one). A row for ANOTHER class is not a
   candidate at all.
2. **Flat OR sized, never both** (`CR-013` part 2). An *All sizes* row and a
   sized row in force for the same class on the same day is refused by name —
   choosing one would decide what a customer pays.
3. **NULL is not zero** (`DEF-277`, `BR-RAT-690`): a sized row with a NULL
   amount says *this size is not served* and refuses; `0.0000` is a price.
4. **Exactly one row.** The exclusion constraint `ex_charge_code_amounts_no_
   overlap` (`rating/0052`) makes two rows for one (code, size, class) in force
   on one day impossible on PostgreSQL; `_one` below refuses loudly if a
   database without the constraint (SQLite) ever holds two.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import F, Min, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.rating import models
from apps.rating.constants import ALL_SIZES, PRICE_HISTORY_EPOCH
from core import tenancy as core_tenancy

#: The four named refusals. Billing and the screens key on these strings.
NO_PRICE = "no_price"
SIZE_NOT_RECORDED = "size_not_recorded"
SIZE_NOT_PRICED = "size_not_priced"
FLAT_AND_SIZES = "amount_and_size_table"

ONE_DAY = timedelta(days=1)


@dataclass(frozen=True)
class ClassTerms:
    """🔒 A PENALTY'S TERMS FOR ONE CUSTOMER CLASS (`DEF-RAT-8753`).

    The PO-approved mock-up prices `LATE` by class (images 31, 61, 67, 77):
    Residential **1.50% minimum $5.00**, Commercial **2.00% minimum $10.00**.
    Stored as an *All sizes* row naming the class with `percent` (a FRACTION,
    `0.015`) and `min_amount` (None = no floor) and `amount` NULL — dated and
    logically killed by `save_prices` exactly as an amount is. A value of this
    type in a save target says *this (size, class) is a terms row*."""

    percent: Decimal
    minimum: Decimal | None = None

    def same_as(self, other: Any) -> bool:
        if not isinstance(other, ClassTerms):
            return False
        if Decimal(self.percent) != Decimal(other.percent):
            return False
        if self.minimum is None or other.minimum is None:
            return self.minimum is None and other.minimum is None
        return Decimal(self.minimum) == Decimal(other.minimum)


class TwoRowsInForce(RuntimeError):
    """Two rows for one (code, size, class) are in force on one day.

    Impossible on PostgreSQL (`ex_charge_code_amounts_no_overlap`). Raised
    rather than choosing one, because choosing would bill by row order."""


@dataclass(frozen=True)
class PriceRow:
    id: Any
    charge_id: Any
    size_class: str
    customer_class: str | None
    amount: Decimal | None
    currency: str
    effective_from: date
    effective_to: date | None
    killed_at: Any
    #: ── THE VERSION, COUNTED — NOT STORED (PO 2026-10-01) ─────────────────
    #: Decision log *"BASE CHARGES SHOWS EACH SIZE'S BASE-PRICE VERSION AND ITS
    #: EFFECTIVE DATES"*: the rate-schedule screen shows, per size, *v1, v2 …*
    #: beside Effective from / to, and reads the number rather than working it
    #: out. `v1` is the earliest-starting row of this (code, size, class), `v2`
    #: the next, in DATE order. An EMPTY row (superseded before it began) prices
    #: no day and is no version: `None`. Counted on read (`_versions`), because
    #: a back-dated edit can start a row BEFORE an existing one, and a stored
    #: number would then contradict the date order the PO asked for.
    version: int | None = None
    #: DEF-RAT-8753 — a TERMS row (a penalty's percent and minimum for one
    #: class) carries these and no `amount`; every other row has both None.
    percent: Decimal | None = None
    min_amount: Decimal | None = None

    @property
    def is_terms(self) -> bool:
        return self.percent is not None

    @property
    def is_flat(self) -> bool:
        return self.size_class == ALL_SIZES

    @property
    def is_empty(self) -> bool:
        """Closed before it ever started — superseded the same day it was
        meant to begin. Kept (never deleted), prices no day."""
        return self.effective_to is not None and self.effective_to < self.effective_from

    def in_force_on(self, day: date) -> bool:
        return self.effective_from <= day and (self.effective_to is None or day <= self.effective_to)


@dataclass(frozen=True)
class PriceAnswer:
    """`price_on_date`'s answer: exactly one row, or a named refusal."""

    amount: Decimal | None
    row: PriceRow | None
    per_size: bool
    refusal: str | None
    size_class: str | None = None

    @property
    def priced(self) -> bool:
        return self.refusal is None


@dataclass(frozen=True)
class PriceChange:
    """What one save did to a code's price rows — the record `rate_change_log`
    carries beside the before/after projection."""

    killed: tuple[Any, ...] = ()
    added: tuple[Any, ...] = ()
    unchanged: int = 0

    @property
    def moved(self) -> bool:
        return bool(self.killed or self.added)


# ── internals ───────────────────────────────────────────────────────────────


def _tenant_id() -> Any:
    tenant_id = core_tenancy.current_tenant_id()
    if tenant_id is None:
        from core import errors

        raise errors.AuthError(errors.AUTH_TENANT_UNRESOLVABLE, br_ref="BR-TEN-003")
    return tenant_id


def _today() -> date:
    from apps.rating import seams

    return seams.tenant_today()


def _row(model_row: Any) -> PriceRow:
    return PriceRow(
        id=model_row.id,
        charge_id=model_row.charge_id,
        size_class=model_row.size_class,
        customer_class=model_row.customer_class,
        amount=model_row.amount,
        currency=model_row.currency,
        effective_from=model_row.effective_from,
        effective_to=model_row.effective_to,
        killed_at=model_row.killed_at,
        percent=model_row.percent,
        min_amount=model_row.min_amount,
    )


def _versions(charge_ids: list[Any]) -> dict[Any, int | None]:
    """`{row_id: version}` over these codes' WHOLE history — one query.

    Per (code, size, class), the non-empty rows in `effective_from` order
    (ties broken by creation, i.e. id) are v1, v2, …; an empty row is `None`.
    """
    if not charge_ids:
        return {}
    keyed: dict[tuple[Any, str, str | None], list[Any]] = {}
    for model_row in models.ChargeCodeAmount.objects.filter(
        tenant_id=_tenant_id(), charge_id__in=charge_ids
    ).order_by("effective_from", "id"):
        keyed.setdefault(
            (model_row.charge_id, model_row.size_class, model_row.customer_class), []
        ).append(model_row)
    out: dict[Any, int | None] = {}
    for rows in keyed.values():
        number = 0
        for model_row in rows:
            empty = (
                model_row.effective_to is not None
                and model_row.effective_to < model_row.effective_from
            )
            if empty:
                out[model_row.id] = None
                continue
            number += 1
            out[model_row.id] = number
    return out


def _numbered(grouped: dict[Any, list[PriceRow]], charge_ids: list[Any]) -> dict[Any, list[PriceRow]]:
    versions = _versions(charge_ids)
    return {
        charge_id: [replace(row, version=versions.get(row.id)) for row in rows]
        for charge_id, rows in grouped.items()
    }


def _in_force(day: date) -> Q:
    return Q(effective_from__lte=day) & (Q(effective_to__isnull=True) | Q(effective_to__gte=day))


def _ids(charges: Iterable[Any]) -> list[Any]:
    out = []
    for item in charges:
        out.append(getattr(item, "id", item))
    return out


def _ordered(qs: Any) -> Any:
    #: the every-class row first within a size; NULLs sort LAST in PostgreSQL
    #: by default, which is the wrong way round for rule 1.
    return qs.order_by("size_class", F("customer_class").asc(nulls_first=True), "effective_from", "id")


# ── READS ───────────────────────────────────────────────────────────────────


def rows_in_force(
    charges: Iterable[Any],
    on_date: date | None = None,
    *,
    with_versions: bool = False,
    terms: bool = False,
) -> dict[Any, list[PriceRow]]:
    """Every row of these codes in force on `on_date` (default: the tenant's
    today), BOTH every-class and class rows, unresolved — what a screen lists.
    One query for any number of codes (DEF-324's rule). A code with no row is
    absent from the mapping. `with_versions=True` numbers each row (one more
    query) — a screen asks for it; billing never needs it.

    ⚠ **AMOUNT ROWS ONLY BY DEFAULT (`DEF-RAT-8753`).** A penalty's per-class
    TERMS rows (`percent` set, `amount` NULL) are not prices of an amount, and
    every amount reader below — the lookup, the flat amount, the sized tables —
    would read their NULL amount as *not priced*. `terms=True` asks for the
    terms rows INSTEAD (`terms_in_force`, `class_terms_on`)."""
    ids = _ids(charges)
    if not ids:
        return {}
    day = on_date or _today()
    grouped: dict[Any, list[PriceRow]] = {}
    for model_row in _ordered(
        models.ChargeCodeAmount.objects.filter(tenant_id=_tenant_id(), charge_id__in=ids)
        .filter(_in_force(day))
        .filter(percent__isnull=not terms)
    ):
        grouped.setdefault(model_row.charge_id, []).append(_row(model_row))
    return _numbered(grouped, ids) if with_versions else grouped


def terms_in_force(
    charges: Iterable[Any], on_date: date | None = None, *, with_versions: bool = False
) -> dict[Any, list[PriceRow]]:
    """`DEF-RAT-8753` — every per-class TERMS row of these codes in force on
    the day (default: the tenant's today). What a penalty's screen lists."""
    return rows_in_force(charges, on_date, with_versions=with_versions, terms=True)


def class_terms_on(
    charge: Any, customer_class: str | None, on_date: date | None = None
) -> ClassTerms | None:
    """🔒 `DEF-RAT-8753` — the penalty terms THIS class pays on this day, or
    None when the code states none for it.

    Rule 1 of this module applies: a row naming the class beats an every-class
    terms row; a row naming ANOTHER class is not a candidate. The caller
    (`selectors.plan_late_fee_terms`) decides what None means — it falls back
    to the code's own single percent where one is stated and refuses where
    none is, because a silent zero late fee is the failure `CR-078` exists to
    prevent. Worked (the mock-up's `LATE`): Residential on 11/01 → 0.015 /
    $5.00; Commercial → 0.020 / $10.00."""
    day = on_date or _today()
    charge_id = getattr(charge, "id", charge)
    # One code asked for, so every row returned is its own — read the values
    # rather than `.get(charge_id)`: the mapping is keyed by the row's UUID and
    # a caller may hand the id in as a string.
    rows = [
        row for found in rows_in_force([charge_id], day, terms=True).values() for row in found
    ]
    chosen = resolve_for_class(rows, customer_class).get(ALL_SIZES)
    if chosen is None or chosen.percent is None:
        return None
    return ClassTerms(percent=chosen.percent, minimum=chosen.min_amount)


def history(charges: Iterable[Any]) -> dict[Any, list[PriceRow]]:
    """EVERY row these codes have ever stated — killed and closed rows
    included, in (size, class, start) order, each numbered (`version`). What
    *View details → Prices* and the audit before/after read."""
    ids = _ids(charges)
    if not ids:
        return {}
    grouped: dict[Any, list[PriceRow]] = {}
    for model_row in _ordered(
        models.ChargeCodeAmount.objects.filter(tenant_id=_tenant_id(), charge_id__in=ids)
    ):
        grouped.setdefault(model_row.charge_id, []).append(_row(model_row))
    return _numbered(grouped, ids)


def _one(rows: list[PriceRow], key: tuple[str, str | None]) -> PriceRow | None:
    hits = [row for row in rows if (row.size_class, row.customer_class) == key]
    if len(hits) > 1:
        raise TwoRowsInForce(
            f"charge {hits[0].charge_id}: {len(hits)} rows for size {key[0]!r}, class "
            f"{key[1]!r} are in force on one day. The no-overlap constraint makes this "
            "impossible on PostgreSQL; nothing is chosen."
        )
    return hits[0] if hits else None


def resolve_for_class(rows: list[PriceRow], customer_class: str | None) -> dict[str, PriceRow]:
    """`{size_class: row}` for ONE customer class — rule 1: a row naming this
    class beats the every-class row for the same size, and a row naming
    another class is not a candidate. `rows` must already be one day's rows."""
    sizes = sorted({row.size_class for row in rows})
    out: dict[str, PriceRow] = {}
    for size in sizes:
        general = _one(rows, (size, None))
        specific = _one(rows, (size, customer_class)) if customer_class is not None else None
        chosen = specific or general
        if chosen is not None:
            out[size] = chosen
    return out


def answer_from_rows(
    rows: list[PriceRow], *, size_class: str | None, customer_class: str | None
) -> PriceAnswer:
    """Rules 1–3 over one day's rows of ONE code. Pure — no query."""
    resolved = resolve_for_class(rows, customer_class)
    flat = resolved.pop(ALL_SIZES, None)
    if resolved and flat is not None:
        return PriceAnswer(None, None, False, FLAT_AND_SIZES, size_class)
    if resolved:
        if size_class is None:
            return PriceAnswer(None, None, True, SIZE_NOT_RECORDED, None)
        row = resolved.get(size_class)
        if row is None or row.amount is None:
            return PriceAnswer(None, row, True, SIZE_NOT_PRICED, size_class)
        return PriceAnswer(row.amount, row, True, None, size_class)
    if flat is None or flat.amount is None:
        return PriceAnswer(None, flat, False, NO_PRICE, size_class)
    return PriceAnswer(flat.amount, flat, False, None, size_class)


def price_on_date(
    charge: Any,
    size_class: str | None = None,
    customer_class: str | None = None,
    on_date: date | None = None,
) -> PriceAnswer:
    """**THE lookup** — the one price row of `charge` for this size and class
    on this day, or a named refusal (`NO_PRICE`, `SIZE_NOT_RECORDED`,
    `SIZE_NOT_PRICED`, `FLAT_AND_SIZES`). `on_date` defaults to the tenant's
    today; a bill passes its own dates and never today."""
    day = on_date or _today()
    rows = rows_in_force([charge], day).get(getattr(charge, "id", charge), [])
    return answer_from_rows(rows, size_class=size_class, customer_class=customer_class)


def resolved_tables(
    charges: Iterable[Any], on_date: date | None = None, customer_class: str | None = None
) -> dict[Any, dict[str, PriceRow]]:
    """`{charge_id: {size_class: row}}` for one class on one day — rule 1
    applied, *All sizes* included under its own key. One query."""
    day = on_date or _today()
    return {
        charge_id: resolve_for_class(rows, customer_class)
        for charge_id, rows in rows_in_force(charges, day).items()
    }


def flat_amounts(
    charges: Iterable[Any], on_date: date | None = None, customer_class: str | None = None
) -> dict[Any, Decimal | None]:
    """`{charge_id: flat amount}` — the *All sizes* row for this class (or
    every class) in force on the day. A code with no such row maps to None."""
    tables = resolved_tables(charges, on_date, customer_class)
    out: dict[Any, Decimal | None] = {}
    for charge_id in _ids(charges):
        row = tables.get(charge_id, {}).get(ALL_SIZES)
        out[charge_id] = row.amount if row is not None else None
    return out


def flat_amount(
    charge: Any, on_date: date | None = None, customer_class: str | None = None
) -> Decimal | None:
    """The code's FLAT amount on the day — what `charges.amount` used to
    answer. None when the code states no flat amount (it is sized, priced by
    percent, priced per case, or unpriced).

    Handed a loaded `Charge` with no tenant context set, it reads in the
    CHARGE'S OWN tenant — the door `write_flat_amount_directly` uses, for the
    same reason: the old column was read off a row already in hand."""
    if core_tenancy.current_tenant_id() is None and getattr(charge, "tenant_id", None):
        with core_tenancy.tenant_context(charge.tenant_id):
            return flat_amount(charge, on_date, customer_class)
    charge_id = getattr(charge, "id", charge)
    return flat_amounts([charge_id], on_date, customer_class).get(charge_id)


def sized_charge_ids(charges: Iterable[Any], on_date: date | None = None) -> set[Any]:
    """The codes among these that state at least one SIZED row in force on the
    day (any class)."""
    return {
        charge_id
        for charge_id, rows in rows_in_force(charges, on_date).items()
        if any(not row.is_flat for row in rows)
    }


def stated_sizes(charges: Iterable[Any], on_date: date | None = None) -> set[str]:
    """Every real size these codes price on the day — *All sizes* excluded,
    because a flat code makes no statement about which sizes exist."""
    return {
        row.size_class
        for rows in rows_in_force(charges, on_date).values()
        for row in rows
        if not row.is_flat and row.size_class
    }


def boundaries(charges: Iterable[Any], period_start: date, period_end: date) -> set[date]:
    """Every day in (period_start, period_end] on which one of these codes'
    prices changes — a row starting, or the day after a row ends. A bill
    period is cut at each (PO 2026-10-01: *"a period crossing a change is split
    by days"*). Empty rows (closed before they started) cut nothing."""
    ids = _ids(charges)
    if not ids:
        return set()
    cuts: set[date] = set()
    qs = models.ChargeCodeAmount.objects.filter(tenant_id=_tenant_id(), charge_id__in=ids).filter(
        Q(effective_from__gt=period_start, effective_from__lte=period_end)
        | Q(effective_to__gte=period_start, effective_to__lt=period_end)
    )
    for model_row in qs:
        row = _row(model_row)
        if row.is_empty:
            continue
        if period_start < row.effective_from <= period_end:
            cuts.add(row.effective_from)
        if row.effective_to is not None:
            after = row.effective_to + ONE_DAY
            if period_start < after <= period_end:
                cuts.add(after)
    return cuts


def amount_sort_expression(on_date: date | None = None) -> Any:
    """A queryset expression for sorting `charges` by price: the every-class
    *All sizes* amount in force on the day, else the smallest sized amount.
    Used by the charge-code list's *Amount* sort (`selectors.charge_list_
    queryset`) so the sort stays in SQL (`NFR-3`)."""
    day = on_date or _today()
    base = models.ChargeCodeAmount.objects.filter(charge_id=OuterRef("pk")).filter(_in_force(day))
    flat = base.filter(size_class=ALL_SIZES, customer_class__isnull=True).values("amount")[:1]
    smallest = (
        base.exclude(size_class=ALL_SIZES)
        .values("charge_id")
        .annotate(low=Min("amount"))
        .values("low")[:1]
    )
    return Coalesce(Subquery(flat), Subquery(smallest))


def has_rows(charge: Any) -> bool:
    return models.ChargeCodeAmount.objects.filter(
        tenant_id=_tenant_id(), charge_id=getattr(charge, "id", charge)
    ).exists()


# ── WRITES ──────────────────────────────────────────────────────────────────


def live_prices(charge: Any) -> dict[tuple[str, str | None], Any]:
    """The code's CURRENT statement — every un-killed row, keyed (size,
    class). What a save is compared against, and what PATCH semantics keep
    when a payload leaves a key out. A terms row's value is its `ClassTerms`
    (`DEF-RAT-8753`); every other row's is its amount."""
    return {
        (row.size_class, row.customer_class): (
            ClassTerms(percent=row.percent, minimum=row.min_amount)
            if row.percent is not None
            else row.amount
        )
        for row in models.ChargeCodeAmount.objects.filter(
            tenant_id=_tenant_id(), charge_id=getattr(charge, "id", charge), killed_at__isnull=True
        )
    }


def live_effective_to(charge: Any) -> dict[tuple[str, str | None], date | None]:
    return {
        (row.size_class, row.customer_class): row.effective_to
        for row in models.ChargeCodeAmount.objects.filter(
            tenant_id=_tenant_id(), charge_id=getattr(charge, "id", charge), killed_at__isnull=True
        )
    }


def _same(left: Any, right: Any) -> bool:
    if isinstance(left, ClassTerms) or isinstance(right, ClassTerms):
        return isinstance(left, ClassTerms) and left.same_as(right)
    if left is None or right is None:
        return left is None and right is None
    return Decimal(left) == Decimal(right)


def save_prices(
    charge: Any,
    target: dict[tuple[str, str | None], Decimal | None],
    *,
    effective_from: date,
    effective_to: date | None,
    currency: str | None = None,
) -> PriceChange:
    """🔒 Make `target` the code's price statement from `effective_from`.

    PO 2026-10-01: *"logical kill"* — **an edit never deletes a row**:

      * a (size, class) whose amount is unchanged (and whose end date is
        unchanged) is **left untouched** — same row, same id;
      * a (size, class) whose amount changes, or that is absent from
        `target`, is **closed**: every row of it that reaches `effective_from`
        gets `effective_to = effective_from − 1 day` (never earlier than the
        day before it started, which leaves an EMPTY row that prices nothing)
        and the live one is stamped `killed_at`;
      * every changed or new (size, class) in `target` gets a **new row**
        `[effective_from, effective_to]`.

    Worked (decision log 2026-10-01): BASE-T on 10/15 for 11/01, CART-64 $12.00
    → $13.00 and CART-96 newly $15.00 — the $12.00 row is kept and closed
    10/31; a $13.00 and a $15.00 row start 11/01; CART-35 $9.00 and DUMP-2
    $40.00 keep their rows and their ids.

    Called inside the caller's `transaction.atomic()`. Closes BEFORE it
    inserts, so the live-row unique indexes and the no-overlap constraint are
    satisfied statement by statement.
    """
    tenant_id = _tenant_id()
    charge_id = getattr(charge, "id", charge)
    rows = list(
        models.ChargeCodeAmount.objects.select_for_update()
        .filter(tenant_id=tenant_id, charge_id=charge_id)
        .order_by("effective_from", "id")
    )
    live = {(row.size_class, row.customer_class): row for row in rows if row.killed_at is None}
    changed: set[tuple[str, str | None]] = set()
    unchanged = 0
    for key, row in live.items():
        stated = (
            ClassTerms(percent=row.percent, minimum=row.min_amount)
            if row.percent is not None
            else row.amount
        )
        if key in target and _same(stated, target[key]) and row.effective_to == effective_to:
            unchanged += 1
            continue
        changed.add(key)
    changed |= {key for key in target if key not in live}

    now = timezone.now()
    closed_to = effective_from - ONE_DAY
    killed: list[Any] = []
    for row in rows:
        key = (row.size_class, row.customer_class)
        if key not in changed:
            continue
        fields: list[str] = []
        if row.effective_to is None or row.effective_to >= effective_from:
            row.effective_to = max(closed_to, row.effective_from - ONE_DAY)
            fields.append("effective_to")
        if row.killed_at is None:
            row.killed_at = now
            fields.append("killed_at")
            killed.append(row.id)
        if fields:
            row.save(update_fields=[*fields, "updated_at"])

    added: list[Any] = []
    for key in sorted(changed, key=lambda item: (item[0], item[1] or "")):
        if key not in target:
            continue
        size_class, customer_class = key
        value = target[key]
        # DEF-RAT-8753 — a `ClassTerms` value is a TERMS row: percent and
        # minimum, no amount (`ck_charge_code_amounts_amount_or_terms`).
        terms = value if isinstance(value, ClassTerms) else None
        created = models.ChargeCodeAmount.objects.create(
            tenant_id=tenant_id,
            charge_id=charge_id,
            size_class=size_class,
            customer_class=customer_class,
            amount=None if terms is not None else value,
            percent=terms.percent if terms is not None else None,
            min_amount=terms.minimum if terms is not None else None,
            effective_from=effective_from,
            effective_to=effective_to,
            **({"currency": currency} if currency else {}),
        )
        added.append(created.id)
    return PriceChange(killed=tuple(killed), added=tuple(added), unchanged=unchanged)


def write_flat_amount_directly(charge: Any, amount: Decimal | None) -> PriceChange:
    """The door `Charge.amount = x; charge.save()` comes through — seeds and
    tests building a catalogue row in one call. States the flat every-class
    price from `PRICE_HISTORY_EPOCH`: *this is the price*, which is what a
    direct catalogue write has always meant. A clerk's edit never comes here
    (`services.update_charge` states its own dates).

    A seed or fixture that saves a `Charge` with no tenant context set wrote
    the old `charges.amount` column happily (it is on the row it already
    holds); the price rows are a separate tenant table, so the write is
    scoped explicitly to the CHARGE'S OWN tenant — never to a guessed one."""
    if core_tenancy.current_tenant_id() is None and getattr(charge, "tenant_id", None):
        with core_tenancy.tenant_context(charge.tenant_id):
            return write_flat_amount_directly(charge, amount)
    target = dict(live_prices(charge))
    if amount is None:
        target.pop((ALL_SIZES, None), None)
    else:
        target[(ALL_SIZES, None)] = Decimal(amount)
    return save_prices(charge, target, effective_from=PRICE_HISTORY_EPOCH, effective_to=None)


def remove_all(charge: Any) -> int:
    """PHYSICALLY delete every row of a code — ONLY for `delete_charge`, which
    refuses any code a plan names, a schedule reads or a bill carries
    (BR-RAT-035). Nothing was ever billed from these rows (decision log
    2026-10-01, judgment (b)); a code that WAS used is retired, never deleted."""
    deleted, _ = models.ChargeCodeAmount.objects.filter(
        tenant_id=_tenant_id(), charge_id=getattr(charge, "id", charge)
    ).delete()
    return deleted

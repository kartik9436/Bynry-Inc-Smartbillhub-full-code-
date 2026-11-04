# ── Trace ──────────────────────────────────────────────
# Change:   CR-157-BRC10 wave B — the API reads the rebuilt rate-schedule screens
#           need (List · View details: Rates / Plans tabs · the four tiles).
# Drawing:  05-prototype/rate-schedules-2026-10-01/images/01–39 (read as IMAGES,
#           B14 rule 42) — the list's Customer class / Base code / Sizes columns,
#           the Units and Sizes priced tiles, the Rates tab's Base charges table
#           (# · Size · Base charge · Minimum · Units · Version · From · To) and
#           the Plans tab (Plan · Code · Customer class · Status · Units, with
#           *Class differs*).
# Rules:    BR-RAT-088 (the charge code owns the base) · BR-RAT-1025 (the named
#           code first, the declared base second) · NFR-3 (the Plans tab pages in
#           SQL) · NFR-5 (no cap) · B14 rule 31 (no database id is a visible
#           value) · hard rule 2 (money displays 2, served by the server)
# Ruling:   the MINIMUM is per meter size (PO 2026-10-01, option A) — `_row_minimum`.
# ───────────────────────────────────────────────────────
"""Read-only projections for the rate-schedule screens (CR-157-BRC10 wave B).

⚠ **A SEPARATE FILE ON PURPOSE.** `selectors.py` is 8,700 lines that three lanes
edit this week (charge-code wave B, rate-schedule wave A's save paths and this
one); everything here is new, reads only, and is called from two places
(`selectors.schedule_card` and the two new endpoints), so it lives on its own and
cannot collide with a sibling's hunk.

⚠ **NO `TariffVersion` QUERY LIVES HERE** (`G142`, CR-157-BRC10 wave A). Every
version this file reads comes from `selectors.in_force_version` /
`latest_version` / `draft_version`, the one lookup billing also asks.

**Nothing here prices a bill.** The base figures are the charge code's own rows
(`charge_prices.rows_in_force`, the one price-on-date lookup), projected for a
screen; the arithmetic that bills them is untouched.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from django.db.models import Count, QuerySet

from apps.rating import charge_prices, models, seams
from apps.rating.constants import ALL_SIZES, PRICE_HISTORY_EPOCH

_VULGAR = {"¼": 0.25, "½": 0.5, "¾": 0.75}
_SIZE_NUMBER = re.compile(r"(\d[\d,]*(?:\.\d+)?)(?:\s*/\s*(\d+))?([¼½¾])?|([¼½¾])")


def size_numbers(name: str) -> list[float]:
    """The numbers a size NAME states, in order — `sizeOrder.ts::sizeNumbers`,
    the same reading on the server (`DEF-RAT-8741`'s judgment (b)): `5/8"` is
    0.625, `1½"` is 1.5, `1φ 200A` is (1, 200). Used to ORDER rows only; never
    shown, never posted."""
    out: list[float] = []
    for whole, denominator, vulgar, alone in _SIZE_NUMBER.findall(name or ""):
        if alone:
            out.append(_VULGAR[alone])
            continue
        value = float(whole.replace(",", ""))
        if denominator and float(denominator) != 0:
            value = value / float(denominator)
        if vulgar:
            value += _VULGAR[vulgar]
        out.append(value)
    return out


def _size_key(name: str, index: int) -> tuple[int, list[float], int]:
    numbers = size_numbers(name)
    # Numbered before un-numbered; two un-numbered keep their arrival order.
    return (0 if numbers else 1, numbers, index)


def _base_code_for(tariff: models.Tariff, version: Any) -> models.Charge | None:
    """BR-RAT-1025's order: the code the version NAMES, else the service's
    declared base (`is_base`) that reaches this schedule's customer class.

    A screen reading — billing resolves through `resolution` and is untouched.
    Where two declared bases could both reach the class the first by code is
    shown; the activation gate (`_guard_bound_base_charge_code`) is what
    refuses an ambiguous binding, not this projection.
    """
    if version is not None and getattr(version, "base_charge_code_id", None):
        return version.base_charge_code
    # `DEF-RAT-9832` (PO 2026-10-06) — the "else the service's declared base"
    # half above is SUPERSEDED: a schedule naming none bills `$0.00`, so no
    # code is inferred for it here either.
    return None


def _class_code(tariff: models.Tariff) -> str | None:
    if not tariff.account_type_id:
        return None
    return seams.account_type_code_by_id(tariff.account_type_id)


def _price_for(rows: list[Any], size_class: str, class_code: str | None) -> Any | None:
    """The in-force row of ONE size for this schedule's class: the class's own
    row first, the every-class row second (CR-087 A1 — NULL means EVERY class).
    An empty row (closed before it began) prices no day and is skipped."""
    live = [r for r in rows if not r.is_empty]
    # A code with ONLY a flat row prices every size at it — billing's rule 3
    # (`charge_prices.answer_from_rows`). The seeded `BASE-W` is exactly that,
    # and reading only the size's own row drew all nine sizes *Not priced*.
    sized = any(r.size_class != ALL_SIZES for r in live)
    own = [r for r in live if r.size_class == (size_class if sized else ALL_SIZES)]
    if class_code is not None:
        for row in own:
            if row.customer_class == class_code:
                return row
    for row in own:
        if row.customer_class is None:
            return row
    return None


def _schedule_size_codes(version: Any) -> list[str]:
    if version is None:
        return []
    return list(
        models.RateSizeRow.objects.filter(
            tenant_id=version.tenant_id, tariff_version=version
        ).values_list("size_class", flat=True)
    )


def _size_names(codes: list[str]) -> dict[str, str]:
    return seams.size_class_names(codes) if codes else {}


def sizes_priced(tariff: models.Tariff, version: Any, on_date: date | None = None) -> dict[str, Any]:
    """The *Sizes priced* figure: `{priced, total, base_code}`.

    **`total` is the sizes THIS SCHEDULE prices** — its `rate_size_rows` — and
    `priced` is how many of them the base code has a price for on `on_date`.
    That is what every drawing shows: Water — Residential *5 of 5*, Trash *6 of
    7* with CART-96 *Not priced*, the wizard's aside *3 of 3* after three rows
    are added. A schedule with no size rows (`DEF-360`: one row prices every
    size) reads off the base code instead — its sized rows, all of them priced
    by construction — and a code priced only *All sizes* is `0 of 0`, which
    the screen draws as *One amount*.
    """
    charge = _base_code_for(tariff, version)
    codes = _schedule_size_codes(version)
    class_code = _class_code(tariff)
    rows = (
        charge_prices.rows_in_force([charge], on_date).get(charge.id, [])
        if charge is not None
        else []
    )
    if codes:
        priced = sum(1 for code in codes if _price_for(rows, code, class_code) is not None)
        return {"priced": priced, "total": len(codes), "base_code": charge}
    sized = {row.size_class for row in rows if not row.is_flat and not row.is_empty}
    return {"priced": len(sized), "total": len(sized), "base_code": charge}


def _needs_a_named_base(tariff: models.Tariff, version: Any) -> bool:
    from apps.rating import selectors  # late: selectors imports this module

    return selectors.schedule_needs_a_named_base(tariff, version)


def card_extras(tariff: models.Tariff, version: Any, today: date) -> dict[str, Any]:
    """The four list columns the drawing adds (`01-list-all.png`): Customer
    class · Base code · Sizes (`5 of 5`). Names, never ids (B14 rule 31)."""
    names = (
        seams.account_type_names([tariff.account_type_id]) if tariff.account_type_id else {}
    )
    sizes = sizes_priced(tariff, version, today)
    charge = sizes["base_code"]
    return {
        # `null` = every class — the screen says *Every class*.
        "customer_class_name": names.get(str(tariff.account_type_id))
        if tariff.account_type_id
        else None,
        "base_code": charge.code if charge is not None else None,
        # `DEF-RAT-9797` — live, names no base code, and its service has one:
        # the list says *Choose a base code* on this row.
        "base_code_to_choose": _needs_a_named_base(tariff, version),
        "sizes_priced": sizes["priced"],
        "sizes_total": sizes["total"],
    }


def _units_by_size(tariff: models.Tariff, today: date) -> tuple[dict[str | None, int], int]:
    """Units on this schedule per connection size, and the total.

    A unit is on the schedule through a CURRENT `unit_plan_assignments` row
    whose plan attaches it — `selectors.schedule_applied_to_accounts`' own
    predicate, so the column and the *Units* tile cannot disagree about the
    population. The size is the size class of the unit's in-service asset for
    this service on `today` (`seams.unit_counts_by_size_class`)."""
    plan_ids = models.PlanRateSchedule.objects.filter(
        tenant_id=tariff.tenant_id, tariff=tariff
    ).values_list("rate_plan_id", flat=True)
    units = models.UnitPlanAssignment.objects.filter(
        tenant_id=tariff.tenant_id,
        rate_plan_id__in=list(plan_ids),
        assigned_to__isnull=True,
    ).values_list("unit_id", flat=True)
    unit_ids = list(dict.fromkeys(units))
    counts = seams.unit_counts_by_size_class(unit_ids, tariff.service.code, today)
    return counts, len(unit_ids)


def _row_minimum(version: Any, size_code: str | None) -> dict[str, Any]:
    """The size's minimum — **PO ruling 2026-10-01, option A** (decision log
    *"RATE SCHEDULES: THE MINIMUM IS SET PER METER SIZE AND BILLING CHARGES
    IT"*): the per-size `rate_size_rows.minimum_bill` IS the service minimum,
    and the per-version *Minimum rate on this version* is removed from screen.
    So this reads the size row and nothing else; a size with none — and the
    *All sizes* row, which has no size row — is `null`, which the screen reads
    as *No minimum*. **Nothing here touches billing**; the lane that makes
    billing read this column and migrates the old version minimums owns that."""
    if version is None or size_code is None:
        return {"minimum": None, "minimum_display": None}
    row = (
        models.RateSizeRow.objects.filter(
            tenant_id=version.tenant_id, tariff_version=version, size_class=size_code
        )
        .values("minimum_bill")
        .first()
    )
    value = row["minimum_bill"] if row else None
    from apps.rating import selectors  # late: selectors imports this module

    return {"minimum": selectors._money(value), "minimum_display": selectors._display_money(value)}


def _price_cells(row: Any) -> dict[str, Any]:
    from apps.rating import selectors

    if row is None:
        return {
            "priced": False,
            "amount": None,
            "amount_display": None,
            "version": None,
            "effective_from": None,
            "effective_to": None,
        }
    return {
        "priced": True,
        "amount": selectors._money(row.amount),
        "amount_display": selectors._display_money(row.amount),
        "version": row.version,
        # `PRICE_HISTORY_EPOCH` (2000-01-01) is not a date anyone chose: charge
        # codes wave A backfilled every legacy flat amount from it so a catch-up
        # bill is never refused. A clerk reads `01/01/2000` as real, so the
        # stored row is left alone and the From cell says nothing (`—`).
        "effective_from": (
            None
            if row.effective_from == PRICE_HISTORY_EPOCH
            else row.effective_from.isoformat()
        ),
        "effective_to": row.effective_to.isoformat() if row.effective_to else None,
    }


def schedule_rates(tariff_id: Any) -> dict[str, Any]:
    """`GET /rate-schedules/{id}/rates` — the Rates tab's *Base charges* table.

    Columns as the PO ordered them (decision log 2026-10-01, *"order should be
    - # Size Base charge Minimum Units Version From To and give link for From
    BASE-W"*): one row per size this schedule prices, in SIZE order
    (`DEF-RAT-8741`), each with the base code's in-force price for the
    schedule's class, its counted version and its own dates, the stored minimum
    and the units on that size. A size the code does not price is
    `priced: false` with every price cell null — the screen draws *Not priced*
    and `—`. A schedule with no size rows lists the code's own rows; a code
    priced *All sizes* is one row whose Units is every unit on the schedule.

    The USAGE table needs nothing new: `structure` is already on the version the
    detail serves, and the PO removed the usage version strip (decision log
    2026-10-01, Version 12).

    The version read is the one IN FORCE today, else the latest, else the
    draft — the schedule as a clerk opening the screen today sees it.
    """
    from apps.rating import selectors

    tariff = selectors.tariff_or_404(tariff_id)
    today = seams.tenant_today()
    version = (
        selectors.in_force_version(tariff, today)
        or selectors.latest_version(tariff)
        or selectors.draft_version(tariff)
    )
    shown = _base_codes_shown(tariff, version)
    unit_counts, unit_total = _units_by_size(tariff, today)
    codes = _schedule_size_codes(version)
    base_rows: list[dict[str, Any]] = []
    next_changes: list[dict[str, Any]] = []
    for charge, class_code in shown:
        rows = charge_prices.rows_in_force([charge], today, with_versions=True).get(charge.id, [])
        future = _future_rows(charge, today)
        size_codes = codes or sorted(
            {row.size_class for row in rows if not row.is_flat and not row.is_empty}
        )
        names = _size_names(size_codes)
        ordered = sorted(
            enumerate(size_codes), key=lambda pair: _size_key(names.get(pair[1], pair[1]), pair[0])
        )
        wanted: list[tuple[str | None, str]] = [(code, code) for _, code in ordered] or [
            (None, ALL_SIZES)
        ]
        for size_code, price_key in wanted:
            nxt = _next_price(future, price_key, class_code)
            row = {
                "size_class": size_code,
                # B14 rule 31 — the NAME a clerk reads; the code is the key.
                "size_name": names.get(size_code, size_code) if size_code is not None else None,
                **_price_cells(_price_for(rows, price_key, class_code)),
                **_row_minimum(version, size_code),
                "units": unit_counts.get(size_code, 0) if size_code is not None else unit_total,
                # DEF-RAT-8833 — WHICH base code and class this row is priced from.
                "code": charge.code,
                "customer_class": class_code,
                # DEF-RAT-8846 — the scheduled price, if one starts after today.
                **_next_cells(nxt),
            }
            base_rows.append(row)
            if nxt is not None:
                next_changes.append(
                    {
                        "code": charge.code,
                        "customer_class": class_code,
                        "size_name": row["size_name"],
                        "amount": row["next_amount"],
                        "amount_display": row["next_amount_display"],
                        "effective_from": row["next_effective_from"],
                    }
                )
    for index, row in enumerate(base_rows, start=1):
        row["seq"] = index
    sized = [row for row in base_rows if row["size_class"] is not None]
    first = shown[0][0] if shown else None
    next_changes.sort(key=lambda item: (item["effective_from"], item["code"]))
    return {
        "base_code": (
            {"id": str(first.id), "code": first.code, "name": first.name} if first is not None else None
        ),
        # DEF-RAT-8833 — every base code the tab shows, one per class it prices.
        "base_codes": [
            {"id": str(charge.id), "code": charge.code, "name": charge.name, "customer_class": class_code}
            for charge, class_code in shown
        ],
        "sizes_priced": sum(1 for row in sized if row["priced"]),
        "sizes_total": len(sized),
        "units_total": unit_total,
        "base_rows": base_rows,
        # DEF-RAT-8846 — the earliest scheduled base price, for the Next change tile.
        "base_next_change": next_changes[0] if next_changes else None,
    }


def _base_codes_shown(tariff: models.Tariff, version: Any) -> list[tuple[Any, str | None]]:
    """`DEF-RAT-8833` — the base codes the Rates tab shows, each with the class
    it is read for.

    A schedule that NAMES a code, or names a customer class, shows that one code
    as before. A schedule that names neither prices EVERY class, and billing
    finds each account's base by the account's class (`resolution` R4), so the
    tab shows every live base code of the service, one block per code, in code
    order — the industrial electric schedule then reads *BASE-E $12.00
    Residential · BASE-E-COM … Commercial · BASE-E-IND $180.00 Industrial*
    instead of *From BASE-E* alone while its industrial account bills $180.00.
    A display read only; billing is untouched.

    ⚠ **SUPERSEDED 2026-10-06 (`DEF-RAT-9832`, PO ruling):** a schedule naming
    no code bills a `$0.00` base for every class, so no code is shown for it —
    showing the pool would show figures nobody is billed. Its row in the list
    says *Choose a base code* instead (`base_code_to_choose`)."""
    charge = _base_code_for(tariff, version)
    return [] if charge is None else [(charge, _class_code(tariff))]


def _future_rows(charge: Any, today: date) -> list[Any]:
    """The code's AMOUNT rows that start after today — a scheduled price."""
    return [
        row
        for row in charge_prices.history([charge]).get(charge.id, [])
        if row.effective_from > today and not row.is_empty and not row.is_terms
    ]


def _next_price(future: list[Any], price_key: str, class_code: str | None) -> Any | None:
    """The earliest scheduled row for this size (or the code's flat row) and class."""
    if not future:
        return None
    by_day: dict[date, list[Any]] = {}
    for row in future:
        by_day.setdefault(row.effective_from, []).append(row)
    for day in sorted(by_day):
        found = _price_for(by_day[day], price_key, class_code)
        if found is not None:
            return found
    return None


def _next_cells(row: Any | None) -> dict[str, Any]:
    from apps.rating import selectors

    if row is None:
        return {"next_amount": None, "next_amount_display": None, "next_effective_from": None}
    return {
        "next_amount": selectors._money(row.amount),
        "next_amount_display": selectors._display_money(row.amount),
        "next_effective_from": row.effective_from.isoformat(),
    }


def schedule_plans_queryset(tariff: models.Tariff) -> QuerySet:
    """Every plan that attaches this schedule, as a QUERYSET (`NFR-3`): the
    paginator's `count` is a SQL COUNT and the page a LIMIT/OFFSET. Ordered by
    plan NAME, id last (IS-2's stable secondary). Nothing caps it (`NFR-5`).

    It replaces the Plans tab's client-side scan of `GET /plans?per=200`, which
    could only see the first two hundred plans of a tenant."""
    plan_ids = models.PlanRateSchedule.objects.filter(
        tenant_id=tariff.tenant_id, tariff=tariff
    ).values_list("rate_plan_id", flat=True)
    return models.RatePlan.objects.filter(
        tenant_id=tariff.tenant_id, pk__in=plan_ids
    ).order_by("name", "id")


def schedule_plan_rows(tariff: models.Tariff, plans: list[Any]) -> list[dict[str, Any]]:
    """ONE PAGE of plans as the drawn table: Plan · Code · Customer class ·
    Status · Units, with *Class differs* (`10-view-W-RES-plans.png`).

    **Class differs** is `RateScheduleDetail.planClassMismatch`'s rule on the
    server: a schedule with no class prices every class and a plan with no
    class takes whatever prices it, so only a NAMED schedule class that the
    plan's NAMED classes do not include is the fault. One grouped count for
    the page's units, one name lookup for the page's classes."""
    if not plans:
        return []
    plan_ids = [plan.id for plan in plans]
    counts: dict[Any, int] = {
        row["rate_plan_id"]: row["n"]
        for row in models.UnitPlanAssignment.objects.filter(
            tenant_id=tariff.tenant_id, rate_plan_id__in=plan_ids, assigned_to__isnull=True
        )
        .values("rate_plan_id")
        .annotate(n=Count("id"))
    }
    class_ids: list[Any] = []
    for plan in plans:
        class_ids.extend(plan.account_type_ids or [])
    names = seams.account_type_names(class_ids)
    schedule_class = str(tariff.account_type_id) if tariff.account_type_id else None
    out: list[dict[str, Any]] = []
    for plan in plans:
        ids = [str(one) for one in (plan.account_type_ids or [])]
        out.append(
            {
                "plan_id": str(plan.id),
                "plan_name": plan.name,
                "plan_code": plan.code,
                # `[]` = every class; a class this tenant cannot name is left
                # out rather than printed as its id (B14 rule 31).
                "customer_classes": [names[one] for one in ids if one in names],
                "class_differs": bool(schedule_class and ids and schedule_class not in ids),
                "status": plan.status,
                "units": counts.get(plan.id, 0),
            }
        )
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-RAT-004@0b56fac (CR-157-BRC10 wave B — the rate-schedule screens' reads; co-story US-RAT-010@f69a661)
# generated: 2026-10-01 by the CR-157-BRC10 wave B lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr157_wave_b_schedule_reads.py 8 passed (one proved red first: size order by code) · G142 (no TariffVersion query here) · OpenAPI regenerated
# exceptions: E3 the Units column reads assets through a seam (rating.seams.unit_counts_by_size_class) — assets publishes no grouped count
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

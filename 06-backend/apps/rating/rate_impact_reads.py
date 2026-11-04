# ── Trace ──────────────────────────────────────────────
# Change:   CR-179-BRC10 — the Rate Impact report (Billing · Readiness), the
#           Plans & Rates half of its INPUT and of process steps 1–2.
# Drawing:  05-prototype/rate-impact-2026-10-12/ (read as images, B14 rule 42)
# Rules:    CR-179 §1 rows 6–11 (items, versions, capacities, the now figures)
#           · §2 steps 1–2 (accounts on a schedule / carrying a charge code)
#           · §4 confirmed rule 3 (an older version changes only the now
#           figures) · BR-RAT-031 (a draft is not a version) · BR-RAT-1025 +
#           DEF-RAT-9832 (the base is the code the version NAMES, else $0.00)
#           · BR-RAT-028 mode A (the minimum is per size) · hard rule 1
# Tests:    06-backend/tests/test_cr179_rate_impact.py
# Impacts:  apps/reports/report_seams.py (the only caller) — reads, writes nothing
# ───────────────────────────────────────────────────────
"""Plans & Rates' published reads for the RATE IMPACT report (CR-179-BRC10).

⚠ **A SEPARATE FILE, FOR `schedule_reads.py`'s REASON.** `selectors.py` is an
8,700-line human-owned file several lanes edit; everything here is new and
read-only, so it lives on its own and cannot collide with a sibling's hunk.

⚠ **NO `TariffVersion` QUERY LIVES HERE (`G142`).** Every version is found
through `selectors.activated_versions` / `in_force_version` / `version_or_404`
— the lookups billing also asks — and projected through
`selectors.pricing_inputs_for_version`, the ONE projection of a stored version
(`DEF-434`). The base is `schedule_reads`' reading of the named code and the
charge price is `charge_prices`' one lookup. **Nothing here prices a bill and
nothing here multiplies anything**: the report's flat arithmetic is in
`apps/reports/rate_impact.py`, and these functions only say what is ON FILE.

WHAT EACH "NOW" FIGURE IS
─────────────────────────
* `base` — the price the version's NAMED base charge code states for this size
  and the schedule's class (`BR-RAT-1025`). A version naming no code bills a
  `$0.00` base (`DEF-RAT-9832`, PO 2026-10-06) and reads `0`. ⚠ The CR's input
  table lists `tariff_versions.base_charge` as a source; that column is retired
  from billing (`CR-013` part 2 / `BR-RAT-088`) and no bill charges it, so a
  "now" figure read from it would be a starting point no bill ever charged.
* `price` — the flat unit price (`rate_tiers.unit_price`) for the size; `None`
  where the version is not `flat`, which the screen prints as *Billed*.
* `min` — the size's own minimum (`rate_size_rows.minimum_bill`, `BR-RAT-028`
  mode A, no fallback to the version's retired figure — `_size_minimum`).
* A charge code's `base` is its price row for the size (`charge_prices`).

WHICH DAY THE NOW FIGURES ARE READ ON (confirmed rule 3)
────────────────────────────────────────────────────────
The version in force today reads today's prices; any other version (older or
scheduled) reads the prices in force on its own first day. So picking an older
version changes only the now figures and the boxes' starting point — the
billed revenue is billing's and does not move.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Iterable

from django.db.models import Q

from apps.rating import charge_prices, models, plan_versioning, schedule_reads, seams, selectors
from apps.rating.constants import ALL_SIZES

ZERO = Decimal("0")
TYPE_RATE = "rate"
TYPE_CHARGE = "charge"


def _tenant_id() -> Any:
    return selectors._tenant_id()


def _ids(values: Iterable[Any]) -> list[str]:
    return [str(one) for one in values or () if one not in (None, "")]


def _size_order(codes: Iterable[str], names: dict[str, str]) -> list[str]:
    distinct = list(dict.fromkeys(code for code in codes if code))
    return [
        code
        for _, code in sorted(
            (schedule_reads._size_key(names.get(code, code), index), code)
            for index, code in enumerate(distinct)
        )
    ]


# ── ITEMS ────────────────────────────────────────────────────────────────────
def items(service_codes: Iterable[str]) -> list[dict[str, Any]]:
    """The rate schedules and recurring charge codes of these services.

    `[{id, name, type, service_code, unit}]`. A schedule is offered once it
    has ANY version out of draft (BR-RAT-031) — *"allow all schedule"*, PO
    2026-10-12 — and `unit` is the billed unit of the version in force today,
    or of the newest one. A charge code is offered when it is `recurring`,
    belongs to one of these services and is not a schedule's BASE code: a base
    is part of what the schedule bills (`BR-RAT-088`) and is counted there, so
    offering it again would put the same dollars in two groups.
    """
    codes = [code for code in dict.fromkeys(service_codes or ()) if code]
    if not codes:
        return []
    tenant_id = _tenant_id()
    today = seams.tenant_today()
    out: list[dict[str, Any]] = []
    tariffs = (
        models.Tariff.objects.filter(
            tenant_id=tenant_id, service__code__in=codes, deleted_at__isnull=True
        )
        .select_related("service")
        .order_by("service__code", "name", "id")
    )
    for tariff in tariffs:
        version = selectors.in_force_version(tariff, today) or selectors.latest_version(tariff)
        if version is None:
            continue
        out.append(
            {
                "id": str(tariff.id),
                "name": tariff.name,
                "type": TYPE_RATE,
                "service_code": tariff.service.code,
                "unit": version.uom,
            }
        )
    charges = (
        models.Charge.objects.filter(
            tenant_id=tenant_id,
            service__code__in=codes,
            charge_type="recurring",
            deleted_at__isnull=True,
            is_base=False,
        )
        .select_related("service")
        .order_by("service__code", "name", "id")
    )
    for charge in charges:
        out.append(
            {
                "id": str(charge.id),
                "name": charge.name,
                "type": TYPE_CHARGE,
                "service_code": charge.service.code if charge.service_id else None,
                "unit": None,
            }
        )
    return out


def _tariffs(tariff_ids: Iterable[Any]) -> list[models.Tariff]:
    ids = _ids(tariff_ids)
    if not ids:
        return []
    return list(
        models.Tariff.objects.filter(
            tenant_id=_tenant_id(), id__in=ids, deleted_at__isnull=True
        ).select_related("service")
    )


def _charges(charge_ids: Iterable[Any]) -> list[models.Charge]:
    ids = _ids(charge_ids)
    if not ids:
        return []
    return list(
        models.Charge.objects.filter(
            tenant_id=_tenant_id(), id__in=ids, deleted_at__isnull=True
        ).select_related("service")
    )


# ── VERSIONS ─────────────────────────────────────────────────────────────────
def _charge_starts(charge: models.Charge) -> list[tuple[date, list[Any]]]:
    """A charge code's PRICE VERSIONS: the rows that start on one day
    (`selectors.charge_versions`' own definition), terms rows and empty rows
    left out. Oldest first."""
    rows = [
        row
        for row in charge_prices.history([charge]).get(charge.id, [])
        if not row.is_empty and not row.is_terms
    ]
    starts = sorted({row.effective_from for row in rows})
    return [
        (
            start,
            sorted(
                (row for row in rows if row.effective_from == start),
                key=lambda r: (r.size_class, r.customer_class or "", str(r.id)),
            ),
        )
        for start in starts
    ]


def versions(tariff_ids: Iterable[Any], charge_ids: Iterable[Any]) -> list[dict[str, Any]]:
    """Every version of these items, the one in force first, then newest first.

    `[{id, item, effective_from, effective_to, in_force, label}]`.

    * A schedule's versions are its activated rows (drafts excluded,
      BR-RAT-031); `label` is the utility's own version label, or None.
    * A charge code's version is the set of price rows that START on one day,
      and its `id` is the FIRST row of that set (by size, then class) — the
      contract's *"the charge price row id"*. Any row of the set names the
      same version; `charge_version_rows` resolves it back.
    """
    today = seams.tenant_today()
    out: list[dict[str, Any]] = []
    for tariff in _tariffs(tariff_ids):
        rows = selectors.tariff_versions(tariff)
        if not rows:
            continue
        live = selectors.in_force_version(tariff, today)
        # `DEF-RAT-9003`'s ONE numbering, the one the schedule's own Audit tab
        # prints (`RateScheduleDetail.versionOrdinal`): a version is numbered in
        # the order it was SAVED, the served (effective-date) order breaking a
        # tie — so `v3` here is the `v3` a clerk sees on Plans & Rates. Walk of
        # 2026-10-12: the picker read bare ISO dates (`2026-09-20`).
        saved = sorted(enumerate(rows), key=lambda pair: (pair[1].created_at, pair[0]))
        numbered = {row.id: at + 1 for at, (_index, row) in enumerate(saved)}
        ordered = sorted(
            rows,
            key=lambda row: (
                0 if live is not None and row.id == live.id else 1,
                -row.effective_from.toordinal(),
                str(row.id),
            ),
        )
        for row in ordered:
            out.append(
                {
                    "id": str(row.id),
                    "item": str(tariff.id),
                    "effective_from": row.effective_from,
                    "effective_to": row.effective_to,
                    "in_force": live is not None and row.id == live.id,
                    # The utility's own FILED label where it typed one, else
                    # the saved-order ordinal above — `v3`, never a bare date.
                    "label": (row.version_label or "").strip() or f"v{numbered[row.id]}",
                }
            )
    for charge in _charges(charge_ids):
        starts = _charge_starts(charge)
        if not starts:
            continue
        live_start = max((start for start, _ in starts if start <= today), default=None)
        numbered = {start: index + 1 for index, (start, _) in enumerate(starts)}
        ordered = sorted(
            starts,
            key=lambda pair: (0 if pair[0] == live_start else 1, -pair[0].toordinal()),
        )
        for index, (start, group) in enumerate(ordered):
            nxt = [s for s, _ in starts if s > start]
            ends = [row.effective_to for row in group]
            end = None
            if nxt:
                end = date.fromordinal(min(nxt).toordinal() - 1)
            elif ends and all(one is not None for one in ends):
                end = max(one for one in ends if one is not None)
            out.append(
                {
                    "id": str(group[0].id),
                    "item": str(charge.id),
                    "effective_from": start,
                    "effective_to": end,
                    "in_force": start == live_start and (end is None or end >= today),
                    # Counted, never stored — the charge code's Audit tab
                    # numbers its price versions the same way (PO 2026-10-01).
                    "label": f"v{numbered[start]}",
                }
            )
    return out


def charge_version_rows(charge: models.Charge, version_id: Any) -> tuple[date, list[Any]] | None:
    """The `(start, rows)` of the charge price version that row `version_id`
    belongs to, or None when the id is no row of this code."""
    wanted = str(version_id or "")
    for start, group in _charge_starts(charge):
        if any(str(row.id) == wanted for row in group):
            return start, group
    return None


def _figure_day(start: date, end: date | None, today: date) -> date:
    """Confirmed rule 3: the version in force today reads TODAY's prices; any
    other version reads the prices of its own first day."""
    if start <= today and (end is None or end >= today):
        return today
    return start


# ── CAPACITIES AND THE NOW FIGURES ───────────────────────────────────────────
def _flat_price(version: Any, inputs: dict[str, Any]) -> Decimal | None:
    """The ONE price per unit this version states for the size, or None.

    A `flat` version's `unit_price`. A ladder of exactly ONE open-ended tier
    (from nothing to no upper bound) is flat in effect and reads its price —
    that is how fire's six per-size prices are stored (`sample_data
    .fire_schedule_payload`: *"each of fire's six bands gets ONE unbounded
    tier"*). Anything else — two tiers, seasons, time of use, demand — has no
    single price and is None, which the screen prints as *Billed*.
    """
    if version.model == "flat":
        return inputs.get("unit_price")
    tiers = inputs.get("tiers") or []
    if (
        version.model == "tiered"
        and len(tiers) == 1
        and tiers[0].get("upper") is None
        and not inputs.get("season_tiers")
    ):
        return tiers[0].get("unit_price")
    return None


def _schedule_capacities(tariff: models.Tariff, version: Any, today: date) -> list[dict[str, Any]]:
    day = _figure_day(version.effective_from, version.effective_to, today)
    class_code = schedule_reads._class_code(tariff)
    base_code = schedule_reads._base_code_for(tariff, version)
    base_rows = (
        charge_prices.rows_in_force([base_code], day).get(base_code.id, [])
        if base_code is not None
        else []
    )
    probe = selectors.pricing_inputs_for_version(version, day, None)
    sizes = list(schedule_reads._schedule_size_codes(version))
    sizes.extend(probe.get("size_groups") or ())
    if not sizes:
        sizes.extend(
            row.size_class for row in base_rows if not row.is_flat and not row.is_empty
        )
    names = seams.size_class_names(list(sizes)) if sizes else {}
    ordered = _size_order(sizes, names)

    def _now(size: str | None) -> dict[str, Any]:
        inputs = selectors.pricing_inputs_for_version(version, day, size)
        if base_code is None:
            base: Decimal | None = ZERO
        else:
            row = schedule_reads._price_for(base_rows, size or ALL_SIZES, class_code)
            base = row.amount if row is not None else None
        return {"base": base, "price": _flat_price(version, inputs), "min": inputs.get("minimum_bill")}

    if not ordered:
        return [{"value": "", "label": None, "now": _now(None)}]
    return [{"value": code, "label": names.get(code, code), "now": _now(code)} for code in ordered]


def _charge_capacities(charge: models.Charge, start: date, group: list[Any], today: date) -> list[dict[str, Any]]:
    nxt_end = None
    for other_start, _ in _charge_starts(charge):
        if other_start > start:
            nxt_end = date.fromordinal(other_start.toordinal() - 1)
            break
    day = _figure_day(start, nxt_end, today)
    sizes = [row.size_class for row in group if not row.is_flat]
    names = seams.size_class_names(sizes) if sizes else {}
    ordered = _size_order(sizes, names)
    if not ordered:
        answer = charge_prices.price_on_date(charge, None, None, day)
        return [{"value": "", "label": None, "now": {"base": answer.amount, "price": None, "min": None}}]
    out = []
    for code in ordered:
        answer = charge_prices.price_on_date(charge, code, None, day)
        out.append(
            {
                "value": code,
                "label": names.get(code, code),
                "now": {"base": answer.amount, "price": None, "min": None},
            }
        )
    return out


def capacities(refs: Iterable[tuple[str, str, str]]) -> dict[str, list[dict[str, Any]]]:
    """`{version id: [{value, label, now: {base, price, min}}]}` for these
    `(type, item id, version id)` triples.

    `value` is the size code, or `""` with `label` None when the version
    prices no size apart from another (the screen says *All sizes*). Sizes are
    the ones the version USES — its size rows, its per-size price groups, else
    its base code's sized rows (CR-179 §1 row 10) — in size order.

    A triple naming an item or a version this tenant does not hold is simply
    absent (hard rule 1): the caller refuses it by name.
    """
    today = seams.tenant_today()
    wanted = list(refs or ())
    tariffs = {str(t.id): t for t in _tariffs(i for kind, i, _ in wanted if kind == TYPE_RATE)}
    charges = {str(c.id): c for c in _charges(i for kind, i, _ in wanted if kind == TYPE_CHARGE)}
    out: dict[str, list[dict[str, Any]]] = {}
    for kind, item_id, version_id in wanted:
        key = str(version_id)
        if key in out:
            continue
        if kind == TYPE_RATE and str(item_id) in tariffs:
            tariff = tariffs[str(item_id)]
            version = _version_of(tariff, version_id)
            if version is None:
                continue
            out[key] = _schedule_capacities(tariff, version, today)
        elif kind == TYPE_CHARGE and str(item_id) in charges:
            charge = charges[str(item_id)]
            found = charge_version_rows(charge, version_id)
            if found is None:
                continue
            out[key] = _charge_capacities(charge, found[0], found[1], today)
    return out


def _version_of(tariff: models.Tariff, version_id: Any) -> Any | None:
    """An ACTIVATED version of this schedule, or None — never a draft and never
    another schedule's row (`version_or_404` scopes it to the tariff)."""
    from core import errors

    try:
        version = selectors.version_or_404(tariff, version_id)
    except (errors.ApiError, ValueError, TypeError):
        return None
    except Exception:  # noqa: BLE001 — a malformed id is "no such version", never a 500
        return None
    return version if getattr(version, "effective_from", None) is not None else None


def version_model(tariff_id: Any, version_id: Any) -> dict[str, Any] | None:
    """`{model, unit, effective_from}` of one activated schedule version, or None."""
    found = _tariffs([tariff_id])
    if not found:
        return None
    version = _version_of(found[0], version_id)
    if version is None:
        return None
    return {"model": version.model, "unit": version.uom, "effective_from": version.effective_from}


# ── WHO IS ON IT (process steps 1–2) ─────────────────────────────────────────
def units_on_items(
    tariff_ids: Iterable[Any], charge_ids: Iterable[Any], start: date, end: date
) -> dict[str, list[str]]:
    """`{item id: [unit id, ...]}` — the units whose plan carried each schedule
    (`plan_rate_schedules`) or charge code (`plan_charge_rules`) at some point
    in `[start, end]`.

    A unit is on a plan through a `unit_plan_assignments` row overlapping the
    window. The plan's BINDINGS are read as the plan stated them on the
    window's last day (`plan_versioning.pricing_day(end)` — the same rule a bill
    for that day reads), so a schedule a plan dropped mid-year is the plan's
    current statement and not every statement it ever made.
    """
    tenant_id = _tenant_id()
    tariff_list = _ids(tariff_ids)
    charge_list = _ids(charge_ids)
    plans_by_item: dict[str, set[str]] = {}
    with plan_versioning.pricing_day(end):
        if tariff_list:
            for plan_id, tariff_id in models.PlanRateSchedule.objects.filter(
                tenant_id=tenant_id, tariff_id__in=tariff_list
            ).values_list("rate_plan_id", "tariff_id"):
                plans_by_item.setdefault(str(tariff_id), set()).add(str(plan_id))
        if charge_list:
            for plan_id, charge_id in models.PlanChargeRule.objects.filter(
                tenant_id=tenant_id, charge_id__in=charge_list
            ).values_list("rate_plan_id", "charge_id"):
                plans_by_item.setdefault(str(charge_id), set()).add(str(plan_id))
    plan_ids = {plan for plans in plans_by_item.values() for plan in plans}
    units_by_plan: dict[str, list[str]] = {}
    if plan_ids:
        for unit_id, plan_id in (
            models.UnitPlanAssignment.objects.filter(
                tenant_id=tenant_id,
                rate_plan_id__in=list(plan_ids),
                assigned_from__lte=end,
            )
            .filter(Q(assigned_to__isnull=True) | Q(assigned_to__gte=start))
            .order_by("unit_id", "assigned_from", "id")
            .values_list("unit_id", "rate_plan_id")
        ):
            units_by_plan.setdefault(str(plan_id), []).append(str(unit_id))
    out: dict[str, list[str]] = {}
    for item_id in tariff_list + charge_list:
        units: list[str] = []
        for plan_id in sorted(plans_by_item.get(item_id, ())):
            units.extend(units_by_plan.get(plan_id, ()))
        out[item_id] = list(dict.fromkeys(units))
    return out


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-179-BRC10 (12-governance/change-requests/CR-179-BRC10-rate-impact-report.md — §1 rows 6–11, §2 steps 1–2, §4 rule 3)
# screens: the standard report viewer at /reports/rate_impact (no screen of its own)
# generated: 2026-10-12 by lane RI-SERVER
# checklist: A✔ B=n/a C✔ D✔ E=n/a F✔ G✔ H=deferred(PO 2026-08-09)
# gates: G142 — no `TariffVersion` query in this file; every version comes through `selectors`
# exceptions: (1) the CR names `tariff_versions.base_charge` as a now-figure source; it is retired from billing and the base is read from the version's NAMED code (else $0.00, DEF-RAT-9832) — see the docstring · (2) a schedule's charge-code BASE is not offered as a charge item (it is counted inside the schedule's revenue)
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

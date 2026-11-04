# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 W6 (2026-08-26) — sub-meters: the unaccounted gap
#           Screens: S14 (PRM-02 Overview — the premises-level report)
# Rules:    BR-MET-125 (the gap is STORED per premises per period AND
#           REPORTED — PO verbatim *"(a) store + report — keeps the door
#           open"*) · BR-MET-025 (the mismatch flag and its tolerance) ·
#           BR-AST-003 (a sub-meter is an asset with a meter PARENT) ·
#           BR-MET-020 (no threshold is ever hardcoded) · BR-MET-016/053
#           (lineage heads only) · CLAUDE.md hard rule 1 (tenant scoping) ·
#           hard rule 3 (an explicit unit, always)
# Tests:    06-backend/tests/test_cr038_w6_submeters_devices.py
# Impacts:  apps/metering/validation.py (`submeter_mismatch`, the ONE rule
#           body) · apps/metering/services.py (`validate_read_batch` group
#           loop, `commit_read_batch` store) · apps/metering/selectors.py
#           (the premises report) · apps/metering/api.py (the endpoint)
# ───────────────────────────────────────────────────────
"""**BR-MET-125 — master vs Σ sub-meters, resolved, judged and STORED.**

DEF-791 is the reason this file exists. The mismatch rule (BR-MET-025), its
tenant config column and its unit tests all shipped — and `_build_context`
hardcoded `submeter_consumption_sum=None` with a comment claiming the rule
*"runs on the committed group, below"*. There was no group, below or anywhere.
The rule was green forever and never once ran on a real reading.

**WHAT MAKES A METER A SUB-METER: STRUCTURE, NEVER A COLUMN IN A FILE.**
`assets.parent_asset_id` (BR-AST-003) is the whole answer. No CSV row is ever
asked whether it is a sub-meter, and nothing here reads `meter_types.code` or
`asset_types.category` to decide it either — those are labels a tenant may
rename (BR-TEN-036/BR-AST-031), and a renamed label must not silently empty a
reconciliation. The FK is the fact.

**WHAT "THE SAME PERIOD" MEANS.** The master and its subs are rarely read on
the same DAY — a walk-by route takes the building's master on the 1st and the
tenant meters over the following week. So the period is the master read's
CALENDAR MONTH, which is also what `read_import_batches.period_month` and
`meter_read_monthly_usage.period_month` already mean in this module: one word
for one thing. Within the month the sub's LATEST lineage head on the same
register wins (BR-MET-016/053), exactly as billing pickup resolves a read.

**WHAT IS NOT BUILT, DELIBERATELY.** Nothing here bills the gap to anybody.
BR-MET-125 says so in as many words — *"Billing common areas FROM it is
deliberately not built — the stored figure keeps that door open for a future
ruling"*. There is no rate, no account and no charge in this file, and adding
one is a new PO ruling, not a lane's call.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.metering import models, seams, validation

# The registers a master/sub reconciliation is meaningful on.
#
# `total` only, and each exclusion is a reason rather than an omission:
#   · the TOU windows are SLICES of the same total — reconciling each one
#     separately would flag a building whose subs are flat-metered while its
#     master is TOU, which is a tariff difference and not a loss;
#   · `demand` is a kW MAXIMUM, not a kWh quantity: maxima do not add, so
#     Σ subs is not a number that means anything;
#   · `export` and `generation` are not consumption at all (BR-AST-029,
#     BR-MET-135) and are never summed with it.
#
# A tenant that later needs per-window reconciliation is a PO ruling, and this
# tuple is where it lands.
RECONCILED_CHANNELS: tuple[str, ...] = (models.CHANNEL_TOTAL,)

# Why one sub-meter's figure could not be taken. Each is NAMED on the stored
# row and on the report — a short Σ is never reported as a bigger gap.
UNRESOLVED_NO_READ = "no_read_in_period"
UNRESOLVED_NO_CONSUMPTION = "read_has_no_consumption"
UNRESOLVED_UNIT_MISMATCH = "unit_differs_from_master"


def period_month_of(moment: datetime | date) -> date:
    """The reading month, stamped to its first day."""
    day = moment.date() if isinstance(moment, datetime) else moment
    return day.replace(day=1)


def _month_bounds(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return start, end


@dataclass(frozen=True)
class SubmeterResolution:
    """Σ subs for one master, one register, one period — with its shortfalls.

    `total` is None whenever the Σ is INCOMPLETE. It is never a partial sum:
    `resolved < expected` and a number in `total` together would let the caller
    quietly treat a missing reading as a loss.
    """

    expected: int
    resolved: int
    total: Decimal | None
    unit: str | None
    unresolved: list[dict[str, Any]] = field(default_factory=list)
    source_read_ids: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return self.expected > 0 and self.resolved == self.expected


def live_submeters(master: Any, period_start: date) -> list[Any]:
    """The master's sub-meters that were IN SERVICE for the period.

    A sub retired before the period started cannot have a reading in it, and
    counting it would make every later period permanently `not_evaluated`. A
    sub retired DURING the period is still expected — it was live for part of
    it and its final read (BR-AST-022) is a real figure.
    """
    live: list[Any] = []
    for sub in seams.submeters_of(getattr(master, "id", None)):
        retire_date = getattr(sub, "retire_date", None)
        if retire_date is not None and retire_date < period_start:
            continue
        live.append(sub)
    return live


def _staged_figure(
    staged: dict[tuple[Any, Any, str], Decimal | None] | None,
    asset_id: Any,
    channel: str,
    period_start: date,
    period_end: date,
) -> tuple[Decimal | None, bool]:
    """This batch's own consumption for a sub-meter, when the batch carries it.

    Returns `(consumption, was_in_batch)`. A sub-meter read staged in the SAME
    batch as its master has no committed row yet, so the committed-head lookup
    below would report it missing and the whole group would skip — which is the
    ordinary case (one route file carries the building's master and all its
    tenant meters), and skipping it would make this rule as dead as DEF-791
    found it.
    """
    if not staged:
        return None, False
    for (staged_asset_id, read_at, staged_channel), consumption in staged.items():
        if str(staged_asset_id) != str(asset_id) or staged_channel != channel:
            continue
        if read_at is None:
            continue
        day = read_at.date() if isinstance(read_at, datetime) else read_at
        if period_start <= day < period_end:
            return consumption, True
    return None, False


def resolve_submeter_sum(
    *,
    master: Any,
    period_month: date,
    channel: str = models.CHANNEL_TOTAL,
    staged: dict[tuple[Any, Any, str], Decimal | None] | None = None,
    subs: list[Any] | None = None,
) -> SubmeterResolution:
    """Σ of this master's sub-meters for one register in one month.

    Sources, in order, per sub-meter:
      1. the SAME batch's staged consumption (`staged`), when the caller is
         validating a batch that carries both halves;
      2. the sub's latest committed lineage head in the month.

    **Units are never converted** (OQ-004, hard rule 3). A sub reading in a
    different UoM from its master is excluded and NAMED — the sum stays in the
    master's unit or it is not a sum.
    """
    period_start, period_end = _month_bounds(period_month)
    master_unit = (getattr(master, "unit", None) or "") or None
    sub_list = live_submeters(master, period_start) if subs is None else subs

    total = Decimal("0")
    resolved = 0
    unresolved: list[dict[str, Any]] = []
    source_read_ids: list[str] = []

    for sub in sub_list:
        named = {"asset_no": getattr(sub, "asset_no", None), "asset_id": str(sub.id)}
        consumption, in_batch = _staged_figure(staged, sub.id, channel, period_start, period_end)
        sub_unit = (getattr(sub, "unit", None) or "") or None
        head = None
        if not in_batch:
            # BR-MET-1189: the reading that COUNTS on a same-day pair, never
            # merely the later-written one.
            from apps.metering import counted_reading

            head = (
                counted_reading.only_counted(
                    models.MeterRead.objects.filter(
                        tenant_id=sub.tenant_id,
                        asset_id=sub.id,
                        channel=channel,
                        superseded_by_id__isnull=True,
                        read_at__date__gte=period_start,
                        read_at__date__lt=period_end,
                    )
                )
                .order_by("-read_at", "-id")
                .first()
            )
            if head is None:
                unresolved.append({**named, "reason": UNRESOLVED_NO_READ})
                continue
            consumption = head.consumption
            sub_unit = head.unit or sub_unit
        if consumption is None:
            unresolved.append({**named, "reason": UNRESOLVED_NO_CONSUMPTION})
            continue
        if master_unit and sub_unit and sub_unit.strip().lower() != master_unit.strip().lower():
            unresolved.append({**named, "reason": UNRESOLVED_UNIT_MISMATCH, "unit": sub_unit})
            continue
        total += Decimal(consumption)
        resolved += 1
        if head is not None:
            source_read_ids.append(str(head.id))

    complete = len(sub_list) > 0 and resolved == len(sub_list)
    return SubmeterResolution(
        expected=len(sub_list),
        resolved=resolved,
        total=total if complete else None,
        unit=master_unit,
        unresolved=unresolved,
        source_read_ids=source_read_ids,
    )


def mismatch_outcome(
    *,
    master: Any,
    resolution: SubmeterResolution,
    master_consumption: Decimal | None,
    config: Any,
    service_code: str | None = None,
) -> validation.Outcome:
    """The BR-MET-025 verdict for one resolved group — the engine decides.

    The tolerance PRECEDENCE is BR-MET-025's own: the master asset's
    `loss_tolerance_pct` beats the tenant/service `mismatch_pct`. Neither is
    written here (BR-MET-020) — a missing figure is reported, never defaulted.
    """
    return validation.submeter_mismatch(
        master_consumption=master_consumption,
        submeter_sum=resolution.total,
        unit=resolution.unit,
        tolerance_pct=getattr(master, "loss_tolerance_pct", None),
        config=config,
        service_code=service_code,
        expected_submeters=resolution.expected,
        resolved_submeters=resolution.resolved,
        unresolved=resolution.unresolved,
    )


def store_reconciliation(
    *,
    master: Any,
    premises_id: Any,
    period_month: date,
    channel: str,
    outcome: validation.Outcome,
    resolution: SubmeterResolution,
    master_consumption: Decimal | None,
    master_read_id: Any = None,
    service_id: Any = None,
    is_sample: bool = False,
) -> Any:
    """**BR-MET-125's stored row** — the gap survives the post.

    ⚠ **A DERIVED FIGURE IS WRITTEN TO A TABLE HERE, AND THAT IS THE RULING,
    NOT A SHORTCUT.** This module's standing posture is to derive rather than
    store (BR-MET-011 progress, BR-MET-036 occupancy, the S26/S27 counters all
    refuse a stored counter so no copy can drift). The PO overrode it for this
    one figure on 2026-08-26, choosing option (a) over report-only with the
    reason attached: *"(a) store + report — keeps the door open"*. The door is
    billing common areas from the unaccounted quantity, which is NOT built.

    Recompute-in-place, keyed (tenant, premises, master, channel, period) —
    see the model docstring's law 5 for why there is no supersede chain here
    and what would have to change if this figure ever became money.

    The row states its own ABSENCES: a `not_evaluated` outcome writes NULL
    quantities and the reason, never a zero. A zero gap and an uncomputable one
    are opposite facts and the report draws them differently.
    """
    detail = outcome.detail or {}
    computed = outcome.severity != validation.NOT_EVALUATED
    values: dict[str, Any] = {
        "service_id": service_id,
        "master_consumption": master_consumption if computed else None,
        "submeter_sum": resolution.total if computed else None,
        "gap_quantity": Decimal(detail["gap"]) if computed and "gap" in detail else None,
        "gap_pct": Decimal(detail["gap_pct"]) if computed and "gap_pct" in detail else None,
        "tolerance_pct": (
            Decimal(detail["tolerance_pct"]) if computed and "tolerance_pct" in detail else None
        ),
        "within_tolerance": detail.get("within_tolerance") if computed else None,
        # Hard rule 3: the unit is stamped on every row, including a row that
        # holds no quantity — the report still has to say WHICH kWh are missing.
        "unit": resolution.unit or (getattr(master, "unit", None) or ""),
        "status": (
            models.PremisesSubmeterReconciliation.STATUS_COMPUTED
            if computed
            else models.PremisesSubmeterReconciliation.STATUS_NOT_EVALUATED
        ),
        "reason": None if computed else detail.get("reason"),
        "submeter_count": resolution.expected,
        "submeters_resolved": resolution.resolved,
        "unresolved_submeters": resolution.unresolved,
        "source_read_ids": (
            ([str(master_read_id)] if master_read_id else []) + resolution.source_read_ids
        ),
        "computed_at": timezone.now(),
        "is_sample": bool(is_sample),
    }
    row, _created = models.PremisesSubmeterReconciliation.objects.update_or_create(
        tenant_id=master.tenant_id,
        premises_id=premises_id,
        master_asset_id=master.id,
        channel=channel,
        period_month=period_month,
        defaults=values,
    )
    return row


def premises_of(asset: Any) -> Any | None:
    """The premises a meter stands on, through its service point's unit.

    None when the asset carries no service point — a meter in inventory. The
    caller stores nothing in that case rather than inventing a premises, which
    is why this returns None instead of raising.
    """
    service_point = getattr(asset, "service_point", None)
    unit = getattr(service_point, "unit", None)
    return getattr(unit, "premises_id", None)

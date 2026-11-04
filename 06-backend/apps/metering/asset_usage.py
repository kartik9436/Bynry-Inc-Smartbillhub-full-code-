# ── Trace ──────────────────────────────────────────────
# Change:   CR-038 · ADDITION 2026-08-26 — **W5 task 8, the METER half** of
#           trailing-12-month consumption. PO verbatim: *"We ahve to calcualet
#           last 12 month consumption from these readings and display it on
#           account and meters"*. The ACCOUNT half shipped with CR-030 W3 T3.8
#           (`monthly_usage_reads.usage_payload`, S21's Usage tab); this is the
#           half the CR measured as the gap.
#           Screens: S50 (asset detail — the Reads tab's rollup strip)
# Story:    US-AST-005 (the S50 Reads tab) · US-CUS-011 (the shape reused)
# Rules:    BR-MET-106 (a month is computed from reads, an unread month is
#           ABSENT never 0, estimates count and are MARKED) · BR-MET-059 (the
#           channel model — a register is a channel) · BR-MET-135 (`generation`
#           is never summed with consumption) · BR-AST-029 (`export` likewise) ·
#           BR-RAT-014 (the demand register measures kW, not kWh) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 3 (an explicit unit,
#           ALWAYS — this file's whole reason for existing per register)
# Defects:  DEF-798 (the monthly figure summed across channels unit-blind —
#           684 + 14 = 698 kWh where the truth is 684 kWh)
# Questions: OQ-421 **CLOSED 2026-08-27** — PO: *"(b) Store it per meter too -
#           otherwise we will ahve to calculate it again and again"*. The
#           answer is BR-MET-141's `meter_read_asset_monthly_usage`, and this
#           module now READS it (falling back to computing when nothing has
#           been stated yet). OQ-358 stays open for a mixed-unit month.
# Tests:    06-backend/tests/test_def_798_register_blind_usage.py
# Impacts:  apps/metering/api.py (`GET /assets/{id}/usage`) ·
#           07-frontend/src/features/assets/AssetUsageStrip.tsx
# ───────────────────────────────────────────────────────
"""The trailing-12-month strip for ONE METER, register by register.

────────────────────────────────────────────────────────────────────────────
ONE SOURCE OF TRUTH — AND OQ-421 IS NOW CLOSED
────────────────────────────────────────────────────────────────────────────
The CR's own words for this task are *"read from the SAME stored monthly-usage
source the account tab uses — one source of truth, never recomputed by a
screen"*. Until 2026-08-27 only the first half of that was true here, because
`monthly_usage` is keyed `(tenant, account, service, period_month)` and a meter
is neither of its keys. **The PO closed the gap by ruling for the schema
change**, verbatim: *"(b) Store it per meter too - otherwise we will ahve to
calculate it again and again"* — and the reason they gave IS the requirement.

Both halves now hold, and they are different claims, so both are stated:

  * **The RULES are literally the same code.** Every judgment on this page —
    what a month is, what an absent month is, the average, the peak, the low,
    the year-over-year — is `apps.metering.monthly_usage`, the same module
    `monthly_usage_reads` calls for the account tab. Not a copy, not a
    reimplementation: the same functions. The read FACTS come from
    `monthly_usage_service.asset_channel_facts`, which is the same query and
    the same `ReadFact` construction the account writer uses. A change to
    BR-MET-106's arithmetic reaches both surfaces in one edit, and
    `test_def_798_register_blind_usage::…tc10` pins the two against each other
    on the single-meter account so a drift goes RED.

  * **The stored ROW now exists at this grain** — `meter_read_asset_monthly_
    usage`, BR-MET-141, one row per (meter, register, month), written by the
    SAME `recompute_account` call in the SAME transaction as the account row,
    so the two grains can never be stale relative to each other.

**AND IT IS A CACHE, NOT A FACT — DELIBERATELY.** The payload reads a stored
row when one exists (`source: "stored"`) and COMPUTES the identical figure from
the meter's own committed reads when nothing has been stated yet
(`source: "computed_from_reads"`). OQ-421 warned that this direction is the
less reversible one — adding the dimension is a migration, removing it drops a
column with data in it — and the PO ruled with that stated. The fallback is the
answer to it: drop the table and the product returns to the behaviour it
shipped with on 2026-08-26, having lost no statement about any customer.
`test_oq_421_per_meter_monthly_usage` deletes every row and asserts exactly
that.

**Nothing here is recomputed BY A SCREEN**, in either mode — the computation is
server-side, in this module.

────────────────────────────────────────────────────────────────────────────
ONE SERIES PER REGISTER, AND NOTHING IS EVER BLENDED
────────────────────────────────────────────────────────────────────────────
CR-038 asks for this *"per register where the meter has several (a TOU meter's
windows are not blended)"*, and DEF-798 is the measured proof that blending is
not a theoretical hazard:

    monthly_usage.month_figure adds consumption over every usable read for the
    account … a demand peak-delta lands in the ENERGY total and TOU window
    reads are double-counted against total. **Measured: 684 + 14 = 698 kWh
    where the truth is 684 kWh.**

**A meter chart is where that defect is most visible, because a meter is
exactly where several registers live.** So this payload never produces a
"meter total": it produces one series per channel the meter actually reported,
each carrying its own unit (hard rule 3), each labelled with whether it counts
as consumption at all. A demand series is drawn in kW next to an energy series
in kWh, and the two are never added anywhere in this file — there is no code
path that could.

The mixed-unit guard the account tab leans on (OQ-358) would not have caught
DEF-798 and cannot catch it here either: every register on one meter is stamped
with the SAME asset UoM (`MeterRead` docstring law 3), so a kW peak and a kWh
total are the same string to a unit comparison. **The register, not the unit,
is the fact that separates them.**
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Sequence

from core import errors
from core import tenancy as core_tenancy

from apps.metering import models, monthly_usage as rules, seams
from apps.metering.monthly_usage_reads import (
    ALLOWED_WINDOWS,
    METRIC_WINDOW_MONTHS,
    _display,
    _month_label,
    _today_month,
)
from apps.metering.monthly_usage_service import (
    NEVER_CONSUMPTION,
    asset_channel_facts,
    asset_heads_for,
)

#: The task is *"trailing-12-month"* in the PO's own words, so 12 is the
#: default here where the account tab defaults to r10's 24. The 24 option is
#: still offered, because a meter's second year is the comparison a clerk
#: reaches for and the axis is free.
DEFAULT_WINDOW_MONTHS = 12

#: What `source` on the wire may say. Two values and no third: either a row
#: stated this month or it was derived on the spot.
SOURCE_STORED = "stored"
SOURCE_COMPUTED = "computed_from_reads"


@dataclass
class _ChannelFigures:
    """One register's months, however they were obtained.

    The join point of the two paths: `_stored_figures` fills it from rows and
    `_computed_figures` fills it from reads, and `_series_for` below cannot
    tell them apart. That is the whole mechanism behind *"the same functions,
    never a second implementation"* — there is one serialiser and one set of
    metric functions, so a drift between the stored figure and the computed one
    has nowhere to hide except in the figure itself, which is what
    `test_oq_421_per_meter_monthly_usage` asserts.
    """

    figures: dict[date, rules.MonthFigure]
    mixed_units: bool


def _asset_or_refuse(asset_id: Any) -> Any:
    """The meter, WITHIN this tenant (hard rule 1), or a named 404.

    `seams.meter_by_id` is the reviewed metering→assets READ probe — the same
    one `estimate_missing_read` and the validation context already use. No
    write ever crosses the boundary and none is attempted here.
    """
    core_tenancy.current_tenant_id()
    asset = seams.meter_by_id(asset_id)
    if asset is None:
        # A bare 404, exactly as `services._read_row` raises it: HR-1/G4 say a
        # cross-tenant id and a genuinely absent one must be indistinguishable,
        # so no message and no reason travel back.
        raise errors.NotFoundError()
    return asset


def _computed_figures(asset: Any, axis: Sequence[date]) -> dict[str, _ChannelFigures]:
    """Compute this meter's months from its own reads — the FALLBACK path.

    `asset_channel_facts` is `monthly_usage_service`'s, and it is the SAME
    query and the SAME `ReadFact` construction the account grain uses; the
    arithmetic is `rules.summarise`, the same function again. There is one
    derivation in this repo and this is a caller of it, not a copy.

    ⚠ `select_consumption_facts` is deliberately NOT applied — see that
    function's counterpart note in `monthly_usage_service.asset_channel_facts`.
    Nothing at this grain sums across registers, so there is nothing to
    protect from a cross-register sum; every register is published on its own
    terms and LABELLED, so a demand meter shows its peak instead of an empty
    chart.
    """
    out: dict[str, _ChannelFigures] = {}
    for bucket in asset_channel_facts(asset_id=asset.id).values():
        by_month = rules.group_by_month(bucket.facts)
        figures: dict[date, rules.MonthFigure] = {}
        mixed_units = False
        for month in axis:
            month_facts = by_month.get(month, [])
            if not month_facts:
                continue
            try:
                figure = rules.summarise(month, month_facts)
            except rules.MixedUnitMonth:
                # OQ-358, one register down. Two units on ONE register in ONE
                # month is a rarer shape than the account-level case (a
                # re-registered meter mid-month) and the answer is the same
                # one: state the absence and name the question, never convert.
                mixed_units = True
                continue
            if figure is not None:
                figures[month] = figure
        out[bucket.channel] = _ChannelFigures(figures=figures, mixed_units=mixed_units)
    return out


def _stored_figures(asset: Any) -> dict[str, _ChannelFigures]:
    """The STORED per-register months — BR-MET-141, OQ-421 ruled 2026-08-27.

    PO verbatim: *"(b) Store it per meter too - otherwise we will ahve to
    calculate it again and again"*. This is the half that spends the ruling: a
    head row per (register, month), read back with no arithmetic at all.

    ⚠ **A STORED ROW IS REHYDRATED INTO THE SAME `MonthFigure` THE COMPUTED
    PATH PRODUCES**, and both are handed to the SAME `_series_for`. That is why
    the two can be asserted equal figure-for-figure rather than merely
    "similar": below this line the payload cannot tell which produced it.

    An OQ-358 month never reaches this table — the writer's `summarise` raises
    before anything is stored — so a stored series carries `mixed_units=False`
    and its absence for that month is the ordinary "no row" absence.
    """
    out: dict[str, _ChannelFigures] = {}
    for row in asset_heads_for(asset.id):
        figures = out.setdefault(row.channel, _ChannelFigures(figures={}, mixed_units=False))
        figures.figures[row.period_month] = rules.MonthFigure(
            period_month=row.period_month,
            quantity=row.quantity,
            unit=row.unit,
            read_count=row.read_count,
            estimated_read_count=row.estimated_read_count,
            source_read_ids=tuple(str(rid) for rid in row.source_read_ids),
        )
    return out


def _channel_sort_key(channel: str) -> tuple[int, str]:
    """Registers in the vocabulary's own order — `total` first, always."""
    try:
        return (models.CHANNELS.index(channel), channel)
    except ValueError:  # a register minted after this deploy; last, never dropped
        return (len(models.CHANNELS), channel)


def asset_usage_payload(
    asset_id: Any,
    *,
    months: int = DEFAULT_WINDOW_MONTHS,
    today: date | None = None,
) -> dict[str, Any]:
    """Everything the S50 strip draws, for one meter.

    `months` is clamped to the offered vocabulary rather than 4xx'd — the same
    BR-SHL-011 posture `usage_payload` takes: a list URL never refuses over a
    param it does not know, it falls back.
    """
    asset = _asset_or_refuse(asset_id)
    window = months if months in ALLOWED_WINDOWS else DEFAULT_WINDOW_MONTHS
    latest = date(today.year, today.month, 1) if today else _today_month()
    axis = rules.window_months(latest, window)

    # ⚠ **STORED FIRST, COMPUTED ONLY IF NOTHING IS STORED — AND THE PAYLOAD
    # SAYS WHICH.** OQ-421 is CLOSED (PO 2026-08-27): *"(b) Store it per meter
    # too - otherwise we will ahve to calculate it again and again"*, and the
    # reason they gave is the requirement, so the stored row is what a normal
    # request costs. The fallback is not a hedge — it is what makes this table
    # a CACHE rather than a FACT: drop it and the product returns to the
    # behaviour it shipped with on 2026-08-26, having lost no statement about
    # any customer. `test_oq_421_per_meter_monthly_usage` deletes every row and
    # asserts the identical figures come back.
    stored = _stored_figures(asset)
    if stored:
        by_channel, source, absence = stored, SOURCE_STORED, None
    else:
        by_channel = _computed_figures(asset, axis)
        source = SOURCE_COMPUTED
        absence = {"reason": "not_recomputed_yet", "tracks": "BR-MET-141"}

    series = [
        _series_for(channel, figures, axis)
        for channel, figures in sorted(by_channel.items(), key=lambda kv: _channel_sort_key(kv[0]))
    ]

    return {
        "asset_id": str(asset.id),
        "asset_no": asset.asset_no,
        "window": {
            "months": window,
            "from": _month_label(axis[0]),
            "to": _month_label(axis[-1]),
            "options": list(ALLOWED_WINDOWS),
        },
        "series": series,
        # BR-MET-106 is the rule behind every figure and BR-MET-141 is the rule
        # behind storing it per meter; the screen carries no id, so the payload
        # does and a reader can find them.
        "rule_ref": "BR-MET-106",
        "grain_rule_ref": "BR-MET-141",
        # ⚠ SAID OUT LOUD, ON THE WIRE (hard-won law 1 — a comment claiming a
        # guarantee is not the guarantee, so the claim travels). `stored` means
        # a row said so; `computed_from_reads` means nothing had been stated for
        # this meter yet and the figure was derived on the spot.
        "source": source,
        "stored_source_absent": absence,
    }


def _series_for(channel: str, source: _ChannelFigures, axis: Sequence[date]) -> dict[str, Any]:
    """One REGISTER's points across the axis, its metrics and its absences.

    ⚠ **THE ONE SERIALISER FOR BOTH PATHS.** It is handed `MonthFigure`s and
    never reads a row or a read, so a stored month and a computed month cannot
    be rendered differently, carry different metrics or round differently. The
    agreement between the S21 account tab and the S50 meter strip is held by a
    test; the agreement between the stored figure and the computed one is held
    by construction, here.
    """
    points: list[rules.MonthPoint] = []
    drawn: list[dict[str, Any]] = []
    mixed_units = source.mixed_units

    for month in axis:
        figure = source.figures.get(month)
        if figure is None:
            # BR-MET-106: ABSENT, never 0. No bar is drawn for this month.
            points.append(rules.MonthPoint(period_month=month, quantity=None, unit=None))
            drawn.append(
                {
                    "month": _month_label(month),
                    "quantity": None,
                    "quantity_display": None,
                    "unit": None,
                    "absent": True,
                    "read_count": 0,
                    "estimated_read_count": 0,
                    "estimated": False,
                }
            )
            continue
        points.append(
            rules.MonthPoint(
                period_month=month,
                quantity=figure.quantity,
                unit=figure.unit,
                estimated_read_count=figure.estimated_read_count,
                read_count=figure.read_count,
            )
        )
        drawn.append(
            {
                "month": _month_label(month),
                "quantity": str(figure.quantity),
                "quantity_display": _display(figure.quantity),
                "unit": figure.unit,  # hard rule 3 — on every point, not once
                "absent": False,
                "read_count": figure.read_count,
                "estimated_read_count": figure.estimated_read_count,
                # BR-MET-106: *"estimates count and are marked"*.
                "estimated": figure.has_estimate,
            }
        )

    units = {p.unit for p in points if p.present}
    return {
        "channel": channel,
        # ⚠ **WHETHER THIS REGISTER IS CONSUMPTION AT ALL — DEF-798's fact, on
        # the wire.** `export` (BR-AST-029), `generation` (BR-MET-135) and
        # `demand` (BR-RAT-014) are measurements of this meter that nobody
        # consumed. They are DRAWN, because a clerk looking at a demand meter
        # must see its peak — and they are LABELLED, so no screen and no reader
        # can total them into a usage figure.
        #
        # ✅ **AMENDED 2026-08-27 (BR-MET-141 / DEF-797).** This note called the
        # demand series *"a kW delta between two maxima"*, which is what the
        # product committed until the PO ruled: `_post_row` ran BR-MET-019's
        # `(current − prior) × multiplier` on every channel. A maximum register
        # now commits BR-MET-051's own figure — the register VALUE at the cycle
        # read — in the REGISTER's own unit, so this series draws PEAKS in kW
        # rather than differences of peaks in kWh. `is_consumption` is unchanged
        # and still False: a peak is still not a quantity anybody consumed, and
        # that is the whole reason this flag exists.
        "is_consumption": channel not in NEVER_CONSUMPTION,
        "unit": next(iter(units)) if len(units) == 1 else None,
        "unit_absence": (
            {"reason": "mixed_units_across_months", "tracks": "OQ-358"}
            if mixed_units or len(units) > 1
            else None
        ),
        "points": drawn,
        "months_present": sum(1 for p in points if p.present),
        "months_absent": sum(1 for p in points if not p.present),
        "metrics": _metrics(points),
    }


def _metrics(points: Sequence[rules.MonthPoint]) -> dict[str, Any]:
    """Avg · peak · low · YoY for ONE register, over the SAME rules the account
    tab uses. Peak and low read the whole window; the average and the
    year-over-year read the trailing twelve, which is r10's own KPI copy and
    the PO's own words for this task."""
    recent = list(points[-METRIC_WINDOW_MONTHS:])
    prior = list(points[-(2 * METRIC_WINDOW_MONTHS) : -METRIC_WINDOW_MONTHS])

    average = rules.average_over(recent)
    peak = rules.peak_of(points)
    low = rules.low_of(points)
    yoy = rules.yoy_change(recent, prior)

    return {
        "avg_per_month": {
            "value": str(average.quantity) if average.quantity is not None else None,
            "display": _display(average.quantity),
            "unit": average.unit,
            "months_counted": average.months_counted,
            "months_absent": average.months_absent,
            "absent_reason": None if average.quantity is not None else "no_months_with_reads",
            "description": "last_12_months",
        },
        "peak": _extreme(peak),
        "low": _extreme(low),
        "yoy": {
            # CLAUDE.md hard rule 2: percentages carried at 6, displayed at 2.
            "value": str(yoy.percent) if yoy.percent is not None else None,
            "display": (
                None if yoy.percent is None else format(yoy.percent.quantize(Decimal("0.01")), "+f")
            ),
            "absent_reason": yoy.absent_reason,
            "description": "vs_prior_year",
        },
    }


def _extreme(point: rules.MonthPoint | None) -> dict[str, Any]:
    if point is None:
        return {
            "value": None,
            "display": None,
            "unit": None,
            "month": None,
            "absent_reason": "no_months_with_reads",
        }
    return {
        "value": str(point.quantity),
        "display": _display(point.quantity),
        "unit": point.unit,
        "month": _month_label(point.period_month),
        "absent_reason": None,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-038 ADDITION 2026-08-26 (W5 task 8, meter half) + BR-MET-106 + DEF-798; AMENDED 2026-08-27 for OQ-421 as ruled (BR-MET-141, the stored per-meter grain)
# generated: 2026-08-26 by the CR-038 W5 tasks 6/7/8 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint is in apps/metering/api.py) E=deferred(no-frontend-half — AssetUsageStrip.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_def_798_register_blind_usage.py tests/test_oq_421_per_meter_monthly_usage.py
# exceptions: E3 this payload reads the STORED per-register rows (BR-MET-141) and FALLS BACK to computing from the meter's own reads when none has been stated yet — the mode is published on the wire as `source`, which is what makes the table a cache rather than a fact; OQ-421 ruled the storage on 2026-08-27 · E3 a NON-consumption register (export/generation/demand) is DRAWN and LABELLED rather than hidden: hiding a demand meter's only register would leave a clerk an empty chart, and labelling is what stops anything totalling it · E3 the default window is 12 where the account tab's is 24 — the PO's words for this task are "last 12 month consumption"
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

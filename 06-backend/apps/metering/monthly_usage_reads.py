# ── Trace ──────────────────────────────────────────────
# Change:   CR-030 W3 task 3.8 — the ACC-01 **Usage** tab: r10's segments
#           (`Electric` `Water` `All`), the 24-month chart and the 5-metric
#           strip. Design: 18-cr030-onboarding-design.md §5.2.2 Usage row.
#           Screens: S21 (Usage tab)
# Story:    US-CUS-011 (the S21 operational tabs)
# Rules:    BR-MET-106 (an unread month is ABSENT, never 0; estimates are
#           counted and MARKED; the chart reads the latest statement) ·
#           BR-SHL-010 (an undeclared capability is not rendered) ·
#           CLAUDE.md hard rule 1 (tenant scoping) · rule 2 (percentages to 6,
#           display 2) · rule 3 (an explicit unit, always)
# Questions: OQ-358 (a month whose reads disagree about the unit — and its
#           sibling across months, which this module serves as an absence)
# Tests:    06-backend/tests/test_br_met_106_monthly_usage.py
# Impacts:  apps/metering/api.py (`GET /accounts/{id}/usage`) ·
#           07-frontend/src/features/customers/AccountUsageTab.tsx
# ───────────────────────────────────────────────────────
"""BR-MET-106 — the READ MODEL the Usage tab is built against.

READ-ONLY by law (B8/LAW 0): no writes, no ORM outside metering's own tables
plus the two reviewed cross-module ids it already holds, and every absence
served AS an absence.

────────────────────────────────────────────────────────────────────────────
FOUR THINGS THIS READ MODEL SERVES AS AN ABSENCE, EACH NAMING ITS ROW
────────────────────────────────────────────────────────────────────────────
Same discipline G38 enforces on the frontend — *a stated absence cites the row
that will kill it* — applied to the payload, so the screen does not invent the
sentence and cannot outlive the reason:

  * **A month with no reads has `quantity: null` and `absent: true`.** It is
    never `0`. BR-MET-106 is explicit and the reason is that zero usage and no
    read are different claims about a customer.
  * **`metrics.*` are `null` with an `absent_reason`** when no month in the
    window carries a figure — an average over nothing is not 0.
  * **`metrics.yoy` carries `no_current_reads` / `no_prior_reads` /
    `prior_year_zero`** rather than 0.0%, because "no change" and "we cannot
    say" are different claims.
  * **`water_avg` is absent with `no_water_months`** when the account has no
    stored water month. r10 draws the fifth KPI unconditionally; an account
    with no water service has no water average, and printing `0.00 kgal` would
    tell a customer they used no water.

────────────────────────────────────────────────────────────────────────────
WHY THERE IS NO SINGLE `All` SERIES
────────────────────────────────────────────────────────────────────────────
r10's segment control offers `Electric` `Water` `All`, and **`All` cannot be
one line**: CLAUDE.md hard rule 3 and BR-MET-106 both say kWh, kgal and therms
are never added together. So this payload always carries ONE SERIES PER
SERVICE, each with its own unit and its own metrics, and the segment control
chooses which of them the chart draws. `All` draws them all, side by side.
That is a consequence of rule 3 rather than a decision this module made.

────────────────────────────────────────────────────────────────────────────
`Compare to neighbors →` IS NOT IN THIS PAYLOAD, ON PURPOSE
────────────────────────────────────────────────────────────────────────────
r10 draws that link in the chart header and **B18 §5.2.2 records it as `D3`, a
feature nobody has specified**. BR-MET-106 rules the chart and the strip and
says nothing about it. Nothing here serves a neighbour comparison, nothing
stubs one, and the screen does not draw the link — the same posture the read
log's `Export` control already has on this page (BR-SHL-010: an undeclared
capability is not rendered).

────────────────────────────────────────────────────────────────────────────
THE READINGS BEHIND A MONTH (`reading`, PO 2026-10-15, DEF-CUS-10162)
────────────────────────────────────────────────────────────────────────────
The Month by month table shows, per service per month, the previous and
current reading, the read date, the source and a High/Low check. Each present
point carries a `reading` block built from the month's own `source_read_ids`
(the reads the figure summed), fetched in ONE tenant-scoped query for the
whole window — see `_reads_behind`, `_reading_block` and `check_of`, whose
docstrings carry the latest/earliest, two-register and status-mapping
decisions. An absent month carries `reading: null`. Served only when the
caller asks (`include_reads=True`, the staff endpoint).

────────────────────────────────────────────────────────────────────────────
DISPLAY PRECISION IS AN ENG DISPOSITION AND IS REPORTED
────────────────────────────────────────────────────────────────────────────
CLAUDE.md rule 2 fixes the display of MONEY and PERCENTAGES at 2. **No signed
rule anywhere gives a display precision for a CONSUMPTION**, and r10 draws
`628 kWh` (none) beside `3.42 kgal` (two). So `*_display` quantizes to 2 and
then strips trailing zeros, which reproduces both of r10's figures without
inventing a rule wider than that. REPORTED, not resolved here — a signed
answer belongs in the metering rules, not in a serialiser.
"""

from __future__ import annotations

from datetime import date, datetime
from datetime import timezone as dt_timezone
from decimal import Decimal
from typing import Any, Sequence

from core import tenancy as core_tenancy

from apps.metering import models, monthly_usage as rules
from apps.metering import monthly_usage_service as writes

#: r10's chart header reads `Electric usage · 24 months (kWh)`, and its filter
#: control is titled `Filter by: 12 months, 24 months`.
DEFAULT_WINDOW_MONTHS = 24
ALLOWED_WINDOWS = (12, 24)

#: The 12-month sub-window the average and the YoY are measured over — r10's
#: own `last 12 months` description on the Avg and Water KPIs.
METRIC_WINDOW_MONTHS = 12

#: r10's fifth KPI is a different service from the selected segment.
WATER_SERVICE_CODE = "water"


def _display(quantity: Decimal | None) -> str | None:
    """Two decimal places, then trailing zeros stripped. See the docstring."""
    if quantity is None:
        return None
    fixed = quantity.quantize(Decimal("0.01"))
    text = format(fixed, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def _month_label(month: date) -> str:
    return f"{month:%Y-%m}"


def _today_month() -> date:
    from django.utils import timezone

    now = timezone.now()
    return date(now.year, now.month, 1)


def _service_rows(service_ids: Sequence[Any]) -> dict[Any, Any]:
    """The 10-service platform catalog rows these months name.

    A cross-module READ of `tenancy.services` — the same one
    `MonthlyUsage.service` is a reviewed FK to (B2 §2). Reads across the
    boundary are allowed; only WRITES are forbidden, and this module writes
    nothing anywhere. Imported inside the function, as `derivation.py` and
    `import_runs.py` already do, so the app registry is warm.
    """
    from apps.tenancy import models as tenancy_models

    return {s.id: s for s in tenancy_models.Service.objects.filter(id__in=list(service_ids))}


def usage_payload(
    account_id: Any,
    *,
    months: int = DEFAULT_WINDOW_MONTHS,
    today: date | None = None,
    include_reads: bool = False,
) -> dict[str, Any]:
    """Everything the Usage tab draws, for one account.

    `months` is clamped to the vocabulary r10's own filter offers (12 or 24) —
    BR-SHL-011's posture: a list URL never 4xxs over a param it does not know,
    it falls back.

    `include_reads=True` adds each present point's `reading` block — the
    readings behind the month (see `_reading_block`). Only the staff Usage tab
    asks for it (`GET /accounts/{id}/usage`); the billing seam and the portal
    read this same payload for its figures alone and are not charged the extra
    query.
    """
    core_tenancy.current_tenant_id()  # hard rule 1: the head query refuses without it
    window = months if months in ALLOWED_WINDOWS else DEFAULT_WINDOW_MONTHS
    latest = date(today.year, today.month, 1) if today else _today_month()
    axis = rules.window_months(latest, window)

    heads = writes.heads_for(account_id)
    by_service: dict[Any, list[models.MonthlyUsage]] = {}
    for row in heads:
        by_service.setdefault(row.service_id, []).append(row)

    services = _service_rows(list(by_service))
    reads_by_id = _reads_behind(heads, axis) if include_reads else None

    series = []
    for service_id, rows in by_service.items():
        service = services.get(service_id)
        if service is None:  # pragma: no cover — PROTECTed FK; cannot happen
            continue
        series.append(_series_for(service, rows, axis, reads_by_id))
    series.sort(key=lambda entry: entry["service"]["code"] or "")

    return {
        "account_id": str(account_id),
        "window": {
            "months": window,
            "from": _month_label(axis[0]),
            "to": _month_label(axis[-1]),
            "options": list(ALLOWED_WINDOWS),
        },
        # The segment control's vocabulary: the services this account actually
        # has stored months for. An account with only electric gets one chip
        # and `All`, never a `Water` chip that draws an empty chart.
        "services": [entry["service"] for entry in series],
        "series": series,
        "water_avg": _water_average(series),
        # BR-MET-106 is what makes the whole tab possible; the screen carries
        # no id, but the payload does, so a reader can find the rule.
        "rule_ref": "BR-MET-106",
    }


def _series_for(
    service: Any,
    rows: Sequence[models.MonthlyUsage],
    axis: Sequence[date],
    reads_by_id: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """One service's points across the axis, its metrics, and its absences."""
    stated = {row.period_month: row for row in rows}
    points: list[rules.MonthPoint] = []
    drawn: list[dict[str, Any]] = []

    for month in axis:
        row = stated.get(month)
        if row is None:
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
                    "computed_at": None,
                    # An unread month has no readings to describe — the screen
                    # says *No reading* and leaves the other cells empty.
                    **({} if reads_by_id is None else {"reading": None}),
                }
            )
            continue
        points.append(
            rules.MonthPoint(
                period_month=month,
                quantity=row.quantity,
                unit=row.unit,
                estimated_read_count=row.estimated_read_count,
                read_count=row.read_count,
            )
        )
        drawn.append(
            {
                "month": _month_label(month),
                "quantity": str(row.quantity),
                "quantity_display": _display(row.quantity),
                "unit": row.unit,
                "absent": False,
                "read_count": row.read_count,
                "estimated_read_count": row.estimated_read_count,
                # BR-MET-106: *"estimates count and are marked"*. The month is
                # drawn at full height and carries the mark — a customer
                # looking at a 628 kWh month is entitled to know part of it was
                # estimated.
                "estimated": row.estimated_read_count > 0,
                "computed_at": row.computed_at.isoformat(),
                **(
                    {}
                    if reads_by_id is None
                    else {"reading": _reading_block(row.source_read_ids, reads_by_id)}
                ),
            }
        )

    units = {p.unit for p in points if p.present}
    return {
        "service": {"id": str(service.id), "code": service.code, "name": service.name},
        "unit": next(iter(units)) if len(units) == 1 else None,
        "unit_absence": (
            None if len(units) <= 1 else {"reason": "mixed_units_across_months", "tracks": "OQ-358"}
        ),
        "points": drawn,
        "months_present": sum(1 for p in points if p.present),
        "months_absent": sum(1 for p in points if not p.present),
        "metrics": _metrics(points),
    }


#: The `check` vocabulary the Month by month table draws as a chip, worst
#: first. The PO's five words (decision log 2026-10-15, step 3) plus `flagged`.
#: See `check_of` for how every other READ_STATUSES value lands here.
CHECK_RANK: tuple[str, ...] = ("high", "low", "flagged", "zero", "estimated", "ok")

#: The read statuses that ARE one of the PO's five words, verbatim.
_CHECK_AS_IS = frozenset({"high", "low", "zero", "estimated", "ok"})


def check_of(status: str | None) -> str:
    """One read's stored `status` (BR-MET-021) as a `check` code.

    ⚠ **THE PO RULED FIVE WORDS AND `READ_STATUSES` HOLDS MANY MORE.** `high`,
    `low`, `zero`, `estimated` and `ok` map to themselves. Every OTHER status —
    `negative_usage`, `rollover`, `days_threshold`, `factor_flag`, `mismatch`,
    `duplicate`, `stale_prior`, `cycle_membership`, `service_coherence` and the
    rest — is a validation flag that is NOT a consumption judgement, so it is
    served as `flagged` rather than squeezed into High or Low (a rollover is
    not high usage, and calling it so would send a clerk to the customer about
    a meter fault). `flagged` ranks just under High and Low: it is a reading
    somebody should look at, which `zero` and `estimated` are not necessarily.
    A NULL or empty status is `ok`, the column's own default.

    The raw status is served beside it (`status`) so nothing is lost by the
    grouping, and adding a status to READ_STATUSES needs no change here.
    """
    if not status:
        return "ok"
    return status if status in _CHECK_AS_IS else "flagged"


def _reads_behind(
    heads: Sequence[models.MonthlyUsage], axis: Sequence[date]
) -> dict[str, dict[str, Any]]:
    """Every reading the window's months summed — ONE query for the whole tab.

    The ids are each in-window head's `source_read_ids` (BR-MET-106's
    provenance: exactly the reads the figure summed, see `rules.summarise`).
    Tenant-scoped explicitly (hard rule 1) as well as by RLS — a stored id list
    is data, and the filter makes sure no id in it can surface another
    tenant's reading. The `read_at` bounds let PostgreSQL prune
    `meter_reads`' monthly partitions to the window instead of probing all of
    them for each id.
    """
    window = set(axis)
    wanted: set[str] = set()
    for head in heads:
        if head.period_month in window:
            wanted.update(str(i) for i in (head.source_read_ids or []))
    if not wanted:
        return {}
    first = axis[0]
    last = axis[-1]
    after_last = date(last.year + (last.month // 12), (last.month % 12) + 1, 1)
    rows = models.MeterRead.objects.filter(
        tenant_id=core_tenancy.current_tenant_id(),
        id__in=sorted(wanted),
        read_at__gte=datetime(first.year, first.month, 1, tzinfo=dt_timezone.utc),
        read_at__lt=datetime(after_last.year, after_last.month, 1, tzinfo=dt_timezone.utc),
    ).values(
        "id",
        "asset_id",
        "channel",
        "read_at",
        "created_at",
        "prior_value",
        "current_value",
        "unit",
        "source",
        "source_detail",
        "read_method",
        "status",
    )
    return {str(row["id"]): row for row in rows}


def _reading_block(
    source_read_ids: Sequence[Any], reads_by_id: dict[str, dict[str, Any]]
) -> dict[str, Any] | None:
    """What the readings behind ONE present month say — the PO's 2026-10-15 row.

    Worked row shown to the PO: *Sep 2026 · 204,207 gal · 1,240,310 ·
    1,444,517 · 09/28/2026 · Manual (walk-by) · High*.

      * `read_on` — the LATEST reading's date (`read_at` is stamped 00:00Z of
        the read date, so its UTC date IS the date; see `rules.month_of`).
      * `source` + `read_method` — the latest reading's transport and its
        method, the read log's own two codes; `read_method_origin` says whether
        the method was recorded or derived from a legacy tag
        (`selectors._read_method_of`, the one place that decides it).
      * `previous_reading` — the EARLIEST reading's `prior_value`;
        `current_reading` — the LATEST reading's `current_value`. Either is
        `null` when that reading carries none: an estimate has no register
        value (BR-MET-028) and an opening read no prior.
      * ⚠ **A MONTH SUMMED OVER TWO REGISTERS SERVES NO READINGS AT ALL**
        (`readings_absent_reason: "several_registers"`). Two meters on one
        service, or a TOU meter's windows, each run their own register; the
        first one's prior beside the second one's current is two different
        dials printed as a pair, and the subtraction a customer would do on
        them is meaningless (hard rule 3's spirit — never put two measures in
        one figure).
      * `check` — the WORST `check_of(status)` over the month's readings, by
        `CHECK_RANK`; `status` is that reading's raw status.
      * `read_count` — how many readings were found (the screen's *2 readings*
        note). It equals the point's own `read_count`; the tenant filter can
        only make it fall short, never exceed it.

    Returns `None` when none of the ids resolve, which the screen treats as a
    month with a figure and no reading detail.
    """
    from apps.metering import selectors as metering_selectors

    reads = [reads_by_id[str(i)] for i in source_read_ids if str(i) in reads_by_id]
    if not reads:
        return None
    reads.sort(key=lambda r: (r["read_at"], r["created_at"]))
    earliest = reads[0]
    latest = reads[-1]
    registers = {(str(r["asset_id"]), r["channel"]) for r in reads}
    one_register = len(registers) == 1

    previous = earliest["prior_value"] if one_register else None
    current = latest["current_value"] if one_register else None

    worst = min(reads, key=lambda r: CHECK_RANK.index(check_of(r["status"])))
    method = metering_selectors._read_method_of(_ReadLike(latest))
    return {
        "read_count": len(reads),
        "read_on": latest["read_at"].date().isoformat(),
        "source": latest["source"],
        "read_method": method["read_method"],
        "read_method_origin": method["read_method_origin"],
        "previous_reading": None if previous is None else str(previous),
        "previous_reading_display": _display(previous),
        "current_reading": None if current is None else str(current),
        "current_reading_display": _display(current),
        # The REGISTER's unit (BR-MET-143), served with the readings so the
        # pair never travels without it (hard rule 3). `None` only when no
        # reading figure is served.
        "reading_unit": latest["unit"] if one_register else None,
        "readings_absent_reason": None if one_register else "several_registers",
        "check": check_of(worst["status"]),
        "status": worst["status"] or "ok",
    }


class _ReadLike:
    """A `.values()` row seen through attributes, for `_read_method_of`."""

    def __init__(self, row: dict[str, Any]) -> None:
        self.read_method = row.get("read_method")
        self.source = row.get("source")
        self.source_detail = row.get("source_detail")


def _metrics(points: Sequence[rules.MonthPoint]) -> dict[str, Any]:
    """r10's four per-service KPIs. The fifth (`Water avg`) is served beside.

    ⚠ **Peak and low are over the WHOLE window; the average and the YoY are
    over the last twelve months.** That is r10's own copy — the Avg KPI is
    described `last 12 months` and the peak/low carry a month name with no
    qualifier, on a chart titled `24 months`.
    """
    recent = list(points[-METRIC_WINDOW_MONTHS:])
    prior = list(points[-(2 * METRIC_WINDOW_MONTHS) : -METRIC_WINDOW_MONTHS])

    # A window whose present months disagree about the unit has no summable
    # figure at all (hard rule 3). Same question as OQ-358, one level up.
    units = {p.unit for p in points if p.present}
    if len(units) > 1:
        absent = {
            "value": None,
            "display": None,
            "unit": None,
            "absent_reason": "mixed_units_across_months",
            "tracks": "OQ-358",
        }
        # ⚠ **EVERY BRANCH RETURNS EVERY KEY.** A screen reading
        # `metrics.vs_last_month.absent_reason` to state an absence in words
        # would crash on a payload where the key is simply missing, which is
        # the one case it exists to describe (CPB-06/07, `BR-CWP-093`).
        mixed_change = dict(
            absent,
            difference=None,
            difference_display=None,
            against_month=None,
            direction=None,
        )
        return {
            "avg_per_month": dict(absent, description="last_12_months"),
            "peak": dict(absent, month=None),
            "low": dict(absent, month=None),
            "yoy": dict(absent, description="vs_prior_year"),
            "vs_last_month": dict(mixed_change, description="vs_previous_month"),
            "same_month_last_year": dict(mixed_change, description="vs_same_month_last_year"),
        }

    average = rules.average_over(recent)
    peak = rules.peak_of(points)
    low = rules.low_of(points)
    yoy = rules.yoy_change(recent, prior)
    #: ⚠ **BOTH COMPARISONS READ THE WHOLE WINDOW, NOT `recent`** (`CPB-06`).
    #: `same_month_last_year` needs the month TWELVE BEFORE the latest stated
    #: one, and the last twelve points cannot contain it by construction —
    #: slicing to `recent` here would make this metric answer
    #: `no_same_month_last_year` on every account in the product, forever, and
    #: no test that fed it twelve months could ever see it (the same shape as
    #: `DEF-CWP-4510`, a lookup that could only ever return the absent answer).
    #: `usage_payload`'s caller already asks for the wider payload for exactly
    #: this reason and reads only `metrics` from it.
    last_month = rules.month_on_month(points)
    last_year_month = rules.same_month_last_year(points)

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
            # CLAUDE.md rule 2: percentages carried at 6, displayed at 2.
            "value": str(yoy.percent) if yoy.percent is not None else None,
            "display": (
                None if yoy.percent is None else format(yoy.percent.quantize(Decimal("0.01")), "+f")
            ),
            "this_year_total": (
                str(yoy.this_year_total) if yoy.this_year_total is not None else None
            ),
            "prior_year_total": (
                str(yoy.prior_year_total) if yoy.prior_year_total is not None else None
            ),
            "absent_reason": yoy.absent_reason,
            "description": "vs_prior_year",
        },
        #: `CPB-07` — *"5% less than July"*, under the big number.
        "vs_last_month": _change(last_month, "vs_previous_month"),
        #: `CPB-06` — *"800 kWh · 86 kWh more than August 2025"*, beside the chart.
        "same_month_last_year": _change(last_year_month, "vs_same_month_last_year"),
    }


def _change(change: rules.PeriodChange, description: str) -> dict[str, Any]:
    """One month against one other month, on the wire.

    ⚠ **THE PERCENTAGE IS CARRIED AT SIX PLACES AND DISPLAYED AT TWO**, exactly
    as `yoy` above — CLAUDE.md hard rule 2, and the rounding happens ONCE, on
    the server, so the staff tab and the portal cannot round differently.

    ⚠ **THE DIFFERENCE CARRIES ITS UNIT OR IT IS NOT SERVED** (hard rule 3).
    `difference_display` and `unit` travel together and are `None` together;
    there is no state in which a screen has the number and not the unit, which
    is the *"Monthly average 800"* defect this whole wave exists to not repeat.

    ⚠ **`direction` AND `absent_reason` ARE CODES, NEVER SENTENCES** (B14 rule
    35). Eleven catalogues write the words; a server that shipped *"less than"*
    would make ten of them impossible.
    """
    return {
        "value": str(change.percent) if change.percent is not None else None,
        "display": (
            None
            if change.percent is None
            else format(change.percent.quantize(Decimal("0.01")), "f")
        ),
        "difference": str(change.difference) if change.difference is not None else None,
        "difference_display": _display(change.difference),
        "unit": change.unit,
        "direction": change.direction,
        "month": None if change.this_month is None else _month_label(change.this_month),
        "against_month": (
            None if change.against_month is None else _month_label(change.against_month)
        ),
        "absent_reason": change.absent_reason,
        "description": description,
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


def _water_average(series: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """r10's fifth KPI — `Water avg 3.42 kgal · last 12 months`.

    It is the WATER series' own average, not a conversion of anything, and it
    is ABSENT when the account has no stored water month. Printing `0.00 kgal`
    would tell a customer they used no water, which is a different claim from
    "this account has no water service".
    """
    for entry in series:
        if entry["service"]["code"] == WATER_SERVICE_CODE:
            average = entry["metrics"]["avg_per_month"]
            return {
                "value": average.get("value"),
                "display": average.get("display"),
                "unit": average.get("unit"),
                "absent_reason": average.get("absent_reason"),
                "description": "last_12_months",
                # ⚠ **WHICH SERVICE THIS FIGURE IS ABOUT, SAID BY THE SERVER**
                # (`DEF-CUS-4626`). The screen shows this figure only when
                # that service is the one on screen, and it must not decide
                # WHICH service that is by typing `"water"` into a component:
                # the front end already types the service list out by hand in
                # two places and an eleventh service silently never appeared
                # on screen (CLAUDE.md hard-won law 2). One field here costs
                # nothing and removes the guess.
                "service_code": entry["service"]["code"],
            }
    return {
        "value": None,
        "display": None,
        "unit": None,
        "absent_reason": "no_water_months",
        "description": "last_12_months",
        "service_code": WATER_SERVICE_CODE,
    }


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-CUS-011@a1fbf3f (the S21 operational tabs; BR-MET-106 snapshot 2026-08-24)
# generated: 2026-08-24 by the CR-030 W3 task 3.8 lane
# checklist: A✔ B✔ C✔ D=deferred(no-API-half — the endpoint lives in apps/metering/api.py) E=deferred(no-frontend-half — AccountUsageTab.tsx is the same lane's separate file) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: ruff✔ black✔ · pytest tests/test_br_met_106_monthly_usage.py · run_gates no new failure
# exceptions: E3 `All` is not a single series — hard rule 3 forbids adding kWh to kgal, so the payload carries one series per service and the segment control chooses · E3 `Compare to neighbors →` (B18 D3) is NOT served and NOT stubbed: unspecified, and BR-SHL-010 says an undeclared capability is not rendered · E3 consumption DISPLAY precision has no signed rule anywhere; `_display` quantizes to 2 and strips trailing zeros, which reproduces r10's own `628 kWh` and `3.42 kgal` — REPORTED for a rules answer · E3 peak/low are over the full 24-month window while avg and YoY are over 12, which is r10's own KPI copy
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

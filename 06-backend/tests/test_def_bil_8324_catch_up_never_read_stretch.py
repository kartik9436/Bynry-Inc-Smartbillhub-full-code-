# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-BIL-8324 (a catch-up could not be priced where a meter was never
#           read in a stretch of it) — RULED 2026-09-30, PO option A
# Rules:    BR-BIL-018 (as ruled) · OQ-191 (B default, C as the fallback) ·
#           BR-MET-026 (metering's estimate) · CLAUDE.md rule 3
# Tests:    this file · J70 E4 and P5 (the browser walk, real seed, PostgreSQL)
# Impacts:  apps/billing/backbill.py 🔒 · apps/metering/selectors.py
# ───────────────────────────────────────────────────────
"""A catch-up stretch nobody read: the reading first, then the meter's estimate.

PO, 2026-09-30, verbatim: *"A for catch-up estimate"*. Where a meter was NEVER
read in a stretch of a catch-up, so there is nothing to day-weight, the stretch
is priced on the meter's OWN estimate from its reading history (OQ-191's option
C, as the fallback), marked estimated, with a warning on the line.

And a reading that covers the stretch is used FIRST. A read taken after a month
nobody read measures that month too, so it is SHARED by days across the months
it measured — never billed whole in its own month while the empty month is
estimated again (that bills the same water twice). A reading the clerk types on
step 2 reaches the pass as exactly such a read.

⚠ **WHY THE PASS IS DRIVEN WITH READINGS RATHER THAN THROUGH `prepare_back_bill`.**
`tests/test_us_bil_013_backbill.py`'s fixture plan prices no connection size, so
every `prepare_back_bill` on it refuses `R3: connection size 'W-58' has no row`
on this branch before any of this code runs (measured 2026-09-30; the whole
back-bill suite is red on it). The metering half below runs on real reads, and
the J70 walk (E4, P5) drives the whole path on the real seed on PostgreSQL.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from apps.billing import backbill, rating_seam
from apps.billing.contracts import AccountBillingData, ServiceReading
from apps.metering import selectors as metering_selectors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx
from tests.test_us_met_reads_helpers import a_meter, commit_read

SIX = Decimal("6.000000")
Q6 = Decimal("0.000001")
WATER = rating_seam.TariffConfig(
    service="water", model="flat", billed_unit="kgal", unit_price=Decimal("3.2500")
)
MONTHS = [
    (date(2026, 1, 1), date(2026, 1, 31)),
    (date(2026, 2, 1), date(2026, 2, 28)),
    (date(2026, 3, 1), date(2026, 3, 31)),
    (date(2026, 4, 1), date(2026, 4, 30)),
]


def _read(amount=None, *, measured_from=None, reason=None):
    return ServiceReading(
        service_code="water",
        consumption=None if amount is None else rating_seam.Quantity(Decimal(amount), "kgal"),
        absent_reason=reason,
        prior_read=None if amount is None else Decimal("1000"),
        current_read=None if amount is None else Decimal("1006"),
        read_id=None if amount is None else "read-1",
        measured_from=measured_from,
    )


def _data(start, end, reading):
    days = (end - start).days + 1
    return AccountBillingData(
        account_id="acc-8324",
        account_no="A-8324",
        behavior_class="billable",
        currency="USD",
        tax_exempt=False,
        period_start=start,
        period_end=end,
        cycle_days=days,
        service_days=days,
        tariffs=(WATER,),
        readings=(reading,),
    )


def _gathered(readings):
    return [
        [start, end, {}, _data(start, end, reading), (end - start).days + 1]
        for (start, end), reading in zip(MONTHS, readings)
    ]


def _water(gathered, index):
    return gathered[index][3].readings[0]


def test_8324_a__a_later_read_that_measured_the_empty_month_is_shared_by_days():
    """No read in March; April's read counts up from Feb 28, so it measured 61
    days: March carries 6 × 31/61 and April 6 × 30/61, both estimated."""
    gathered = _gathered(
        [
            _read("6", measured_from=date(2025, 12, 31)),
            _read("6", measured_from=date(2026, 1, 31)),
            _read(reason="no_read"),
            _read("6", measured_from=date(2026, 2, 28)),
        ]
    )
    made = backbill._fill_never_read_stretches(SimpleNamespace(unit_id="u"), gathered)

    march, april = _water(gathered, 2), _water(gathered, 3)
    assert march.consumption.amount == (SIX * 31 / 61).quantize(Q6)
    assert april.consumption.amount == (SIX * 30 / 61).quantize(Q6)
    assert march.consumption.unit == "kgal"  # rule 3 — the read's own unit
    assert march.estimated and april.estimated
    # The share keeps the read's identity (the BILLED lock) and drops the
    # register pair, which measured the whole stretch and would not foot.
    assert april.read_id == "read-1" and april.prior_read is None
    assert [(e.period_start, e.source) for e in made] == [
        (date(2026, 3, 1), backbill.ESTIMATE_DAY_WEIGHTED),
        (date(2026, 4, 1), backbill.ESTIMATE_DAY_WEIGHTED),
    ]
    # January and February are their own reads, untouched.
    assert not _water(gathered, 0).estimated and _water(gathered, 0).consumption.amount == 6


def test_8324_b__a_stretch_no_read_measured_takes_the_meters_own_estimate(monkeypatch):
    """Reads Jan–Feb only: March and April have no later read to share, so each
    is metering's estimate, marked estimated and recorded as metering's."""
    asked = []

    def estimate(unit_id, *, service_code, period_start, period_end, asset_id=None):
        asked.append((period_start, period_end))
        days = (period_end - period_start).days + 1
        return {"estimated": True, "consumption": str(Decimal("0.2") * days), "unit": "kgal"}

    monkeypatch.setattr(metering_selectors, "back_bill_segment_estimate", estimate, raising=False)
    gathered = _gathered(
        [
            _read("6", measured_from=date(2025, 12, 31)),
            _read("6", measured_from=date(2026, 1, 31)),
            _read(reason="no_read"),
            _read(reason="no_read"),
        ]
    )
    made = backbill._fill_never_read_stretches(SimpleNamespace(unit_id="u"), gathered)

    assert asked == [MONTHS[2], MONTHS[3]]
    assert _water(gathered, 2).consumption.amount == Decimal("6.2")
    assert _water(gathered, 3).consumption.amount == Decimal("6.0")
    assert _water(gathered, 2).estimated
    assert {e.source for e in made} == {backbill.ESTIMATE_METERING}


def test_8324_c__with_neither_it_still_refuses_and_names_metering_reason(monkeypatch):
    monkeypatch.setattr(
        metering_selectors,
        "back_bill_segment_estimate",
        lambda *a, **k: {"estimated": False, "reason": "no_history"},
        raising=False,
    )
    gathered = _gathered([_read(reason="no_read")] * 2)
    with pytest.raises(Exception) as raised:
        backbill._fill_never_read_stretches(SimpleNamespace(unit_id="u"), gathered)
    assert "no_history" in str(raised.value)
    assert "2026-01-01..2026-01-31" in str(raised.value)


def test_8324_d__a_reading_the_clerk_typed_is_used_first(monkeypatch):
    """Step 2's typed reading arrives on the LAST segment, counting up from the
    last read (Jan 31): it measured Feb–Apr and is shared, and metering is never
    asked for an estimate."""
    monkeypatch.setattr(
        metering_selectors,
        "back_bill_segment_estimate",
        lambda *a, **k: pytest.fail("a typed reading must be used before any estimate"),
        raising=False,
    )
    gathered = _gathered(
        [
            _read("6", measured_from=date(2025, 12, 31)),
            _read(reason="no_read"),
            _read(reason="no_read"),
            _read("12", measured_from=date(2026, 1, 31)),
        ]
    )
    backbill._fill_never_read_stretches(SimpleNamespace(unit_id="u"), gathered)
    total = Decimal(28 + 31 + 30)
    assert [_water(gathered, i).consumption.amount for i in (1, 2, 3)] == [
        (Decimal(12) * 28 / total).quantize(Q6),
        (Decimal(12) * 31 / total).quantize(Q6),
        (Decimal(12) * 30 / total).quantize(Q6),
    ]


def test_8324_h__in_the_preview_a_stretch_nothing_can_price_waits_for_step_2(monkeypatch):
    """The one-time PREVIEW must not refuse at step 1 over a stretch that only
    the reading typed on step 2 can price (DEF-BIL-8300's shape): it is left
    WAITING. The draft (no `waiting_ok`) still refuses."""
    monkeypatch.setattr(
        metering_selectors,
        "back_bill_segment_estimate",
        lambda *a, **k: {"estimated": False, "reason": "trailing_day_count_zero"},
        raising=False,
    )
    gathered = _gathered([_read(reason="no_read")] * 2)
    made = backbill._fill_never_read_stretches(
        SimpleNamespace(unit_id="u"), gathered, waiting_ok=True
    )
    assert made == ()
    assert _water(gathered, 0).consumption is None
    assert _water(gathered, 0).absent_reason == "no_read"
    with pytest.raises(Exception):
        backbill._fill_never_read_stretches(
            SimpleNamespace(unit_id="u"), _gathered([_read(reason="no_read")])
        )


def test_8324_e__a_flagged_read_is_left_for_a_human_not_estimated():
    """`read_flagged` is a read that exists and needs a person's judgment
    (BR-BIL-015) — never papered over by an estimate."""
    gathered = _gathered([_read(reason="read_flagged")])
    assert backbill._fill_never_read_stretches(SimpleNamespace(unit_id="u"), gathered) == ()
    assert _water(gathered, 0).consumption is None


# ── the metering half, on real reads ─────────────────────────────────────────


def _a_read_meter(actor, asset_no, days):
    premises = make_premises(actor, address_line=f"{asset_no} Mesquite Rd")
    unit = make_unit(actor, premises["id"], label="Unit 8324", services=["water"])
    asset = a_meter(actor, asset_no=asset_no, unit_id=unit["id"], service="water", uom="kgal")
    previous = date(2025, 12, 31)
    for index, day in enumerate(days):
        commit_read(
            actor,
            asset["id"],
            day=day.isoformat(),
            value=str(1000 + 6 * (index + 1)),
            prior_value=str(1000 + 6 * index),
            consumption=str(SIX),
            days_since_prior=(day - previous).days,
            unit="kgal",
        )
        previous = day
    return unit, asset


@pytest.mark.django_db
def test_8324_f__metering_estimates_a_window_from_history_and_writes_nothing(brazos, dana):
    """BR-MET-026's trailing-3 daily average: 18 kgal over 28 + 31 + 30 days,
    times May's 31 days — and no `meter_reads` row is written."""
    from apps.metering import models as metering_models

    with tenant_ctx(brazos):
        unit, asset = _a_read_meter(dana, "W-8324F", [end for _s, end in MONTHS])
        before = metering_models.MeterRead.objects.count()
        answer = metering_selectors.back_bill_segment_estimate(
            unit["id"],
            service_code="water",
            period_start=date(2026, 5, 1),
            period_end=date(2026, 5, 31),
        )
        assert answer["estimated"] is True, answer
        daily = Decimal(18) / Decimal(28 + 31 + 30)
        assert Decimal(answer["consumption"]) == (daily * 31).quantize(Q6)
        assert answer["unit"] == "kgal"
        assert metering_models.MeterRead.objects.count() == before

        # No history before the window: metering's own refusal, as data.
        none = metering_selectors.back_bill_segment_estimate(
            unit["id"],
            service_code="water",
            period_start=date(2025, 6, 1),
            period_end=date(2025, 6, 30),
        )
        assert none["estimated"] is False and none["reason"] == "no_history"


@pytest.mark.django_db
def test_8324_g__a_read_publishes_the_day_it_measures_from(brazos, dana):
    """Metering's billing seam says where each read counts up from — the prior
    read's day, even for a history row that stored no `period_start`."""
    with tenant_ctx(brazos):
        unit, _asset = _a_read_meter(dana, "W-8324G", [MONTHS[0][1], MONTHS[3][1]])
        rows = metering_selectors.billing_reads_for_unit(
            unit["id"], period_start=MONTHS[3][0], period_end=MONTHS[3][1]
        )
        water = next(row for row in rows if row["service_code"] == "water")
        assert water["measured_from"] == MONTHS[0][1]

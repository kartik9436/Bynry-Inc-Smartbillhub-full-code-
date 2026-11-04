# ── Trace ──────────────────────────────────────────────
# Change:  CR-157-BRC10 wave A — the rate-schedule save contract wave B builds
#          its screens on: the time-of-use window name sets its meter register,
#          a season is a month and a day, Structure is chosen on step 1, and a
#          bill period crossing a version change is split by days.
# Rules:   BR-RAT-067 (a TOU window names its register — unchanged for a
#          tenant's own window names) · BR-RAT-033/034 (seasons cover the year)
#          · BR-RAT-031 (a draft is resumable and carries its structure) ·
#          BR-RAT-114 (an ordinary bill splits at a mid-period rate change —
#          the PO's $21.00) · BR-RAT-007 (the version in force on the service
#          date)
# Sibling: tests/test_cr157_rate_schedule_saves_pg.py — the concurrency half,
#          which can only run on PostgreSQL.
# ───────────────────────────────────────────────────────
"""What wave B's screens send and what billing reads back, asserted on the
default suite (none of this is transaction-shaped)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.billing import models as billing_models
from apps.rating import models, selectors, services
from core import errors

from tests.test_br_rat_114_midperiod_split import (
    BOUNDARY,
    PERIOD_END,
    PERIOD_START,
    _amounts,
    a_cycle,
    a_cycled_water_unit,
    an_ordinary_bill,
    serve_the_ratified_size,
    state_the_water_base_as_zero,
)
from tests.test_us_bil_001_prepare import an_account
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_plan
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env
from tests.test_us_rat_helpers import SUMMER, WINTER, tenant_ctx

pytestmark = pytest.mark.django_db


def _tou(windows):
    return {
        "name": "Res Electric · TOU",
        "service": "electric",
        "model": "time_of_use",
        "uom": "kWh",
        "structure": {"seasons": [dict(SUMMER), dict(WINTER)], "windows": windows},
    }


def _window(label, season, start, end, price, **extra):
    return {"label": label, "season": season, "day_type": "weekday",
            "start_time": start, "end_time": end, "unit_price": price, **extra}


# ── Time of use: the window name sets the register ─────────────────────────


def test_cr157_tou__on_peak_and_off_peak_derive_their_registers(env):
    """The redesign draws *Window* as a picker of On-peak · Mid-peak · Off-peak
    and *Register* read-only beside it, so the screen sends the NAME and the
    register is derived: On-peak → `tou_on`, Off-peak → `tou_off`."""
    windows = [
        _window("On-peak", "Summer", "14:00", "19:00", "0.2100"),
        _window("Off-peak", "Summer", "19:00", "14:00", "0.0900"),
        _window("Off-peak", "Winter", "00:00", "00:00", "0.0900"),
    ]
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(env.admin, _tou(windows))
        version = selectors.draft_version(models.Tariff.objects.get(pk=draft["id"]))
        stored = {
            (w.label, w.season.label if w.season_id else None): w.channel
            for w in models.TimeOfUseWindow.objects.filter(tariff_version=version)
        }
    assert stored == {
        ("On-peak", "Summer"): "tou_on",
        ("Off-peak", "Summer"): "tou_off",
        ("Off-peak", "Winter"): "tou_off",
    }


def test_cr157_tou__mid_peak_and_spelling_variants(env):
    assert services.tou_register_for_window("Mid-peak") == "tou_mid"
    assert services.tou_register_for_window("on peak") == "tou_on"
    assert services.tou_register_for_window("OFFPEAK") == "tou_off"
    assert services.tou_register_for_window("Punta") is None
    assert services.tou_register_for_window(None) is None


def test_cr157_tou__a_register_that_contradicts_the_window_is_refused_by_name(env):
    """On-peak sent with the off-peak register would bill one register at the
    other's price — refused, never silently 'corrected' either way."""
    windows = [
        _window("On-peak", "Summer", "14:00", "19:00", "0.2100", channel="tou_off"),
        _window("Off-peak", "Summer", "19:00", "14:00", "0.0900"),
        _window("Off-peak", "Winter", "00:00", "00:00", "0.0900"),
    ]
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as refused:
        services.create_rate_schedule(env.admin, _tou(windows))
    keys = [(e["field"], e["message_key"]) for e in refused.value.field_errors]
    assert ("structure.windows[0].channel", "rating.tou.window_register_mismatch") in keys


def test_cr157_tou__a_tenants_own_window_name_still_needs_its_register(env):
    """BR-RAT-067 unchanged outside the three names: "Punta" says nothing about
    which register it is, so the register is still required."""
    windows = [
        _window("Punta", "Summer", "14:00", "19:00", "0.2100"),
        _window("Off-peak", "Summer", "19:00", "14:00", "0.0900"),
        _window("Off-peak", "Winter", "00:00", "00:00", "0.0900"),
    ]
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as refused:
        services.create_rate_schedule(env.admin, _tou(windows))
    fields = [e["field"] for e in refused.value.field_errors]
    assert "structure.windows[0].channel" in fields


# ── Seasonal: a month and a day, every year ────────────────────────────────


def test_cr157_seasonal__stored_as_month_and_day_and_repeat_every_year(env):
    """The redesign's date picker carries a year; the schedule stores only the
    month and day (`rate_seasons.start_month/start_day/end_month/end_day`), so
    *Summer 05/01–09/30* prices July 2026 and July 2031 alike, and *Winter
    10/01–04/30* wraps the year end. A season sent as a full date is refused —
    the screen sends month and day."""
    payload = {
        "name": "Irrigation · Seasonal",
        "service": "water",
        "model": "seasonal",
        "uom": "kgal",
        "structure": {"seasons": [
            {"label": "Summer", "start_month": 5, "start_day": 1, "end_month": 9,
             "end_day": 30, "unit_price": "5.8000"},
            {"label": "Winter", "start_month": 10, "start_day": 1, "end_month": 4,
             "end_day": 30, "unit_price": "4.2000"},
        ]},
    }
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(env.admin, payload)
        version = selectors.draft_version(models.Tariff.objects.get(pk=draft["id"]))
        rows = sorted(
            (s.label, s.start_month, s.start_day, s.end_month, s.end_day)
            for s in models.RateSeason.objects.filter(tariff_version=version)
        )
        assert rows == [("Summer", 5, 1, 9, 30), ("Winter", 10, 1, 4, 30)]
        assert selectors._season_label_on(version, date(2026, 7, 15)) == "Summer"
        assert selectors._season_label_on(version, date(2031, 7, 15)) == "Summer"
        assert selectors._season_label_on(version, date(2027, 1, 10)) == "Winter"

        dated = dict(payload, name="Irrigation · Dated")
        dated["structure"] = {"seasons": [
            dict(payload["structure"]["seasons"][0], start="2026-05-01"),
            payload["structure"]["seasons"][1],
        ]}
        with pytest.raises(errors.ValidationError):
            services.create_rate_schedule(env.admin, dated)


# ── Structure on step 1 ─────────────────────────────────────────────────────


def test_cr157_step_one__the_basics_and_the_structure_save_a_resumable_draft(env):
    """The three-step wizard chooses Structure on Details (step 1). Saving
    there sends the basics and the model only; the schedule is created with a
    DRAFT version carrying that model, so step 2 reopens on the right table."""
    with tenant_ctx(env.tenant):
        draft = services.create_rate_schedule(
            env.admin,
            {"name": "Res Water · Step one", "service": "water", "model": "tiered",
             "uom": "kgal"},
        )
        tariff = models.Tariff.objects.get(pk=draft["id"])
        version = selectors.draft_version(tariff)
        assert version is not None and version.model == "tiered"
        assert version.effective_from is None
        assert selectors.in_force_version(tariff, date(2026, 6, 1)) is None


# ── A bill period crossing a version change, through the real save paths ───


def test_cr157_split__a_june_bill_across_a_rate_change_filed_through_the_service(
    brazos, dana
):
    """BR-RAT-114, with the versions written the way a clerk writes them — not
    planted rows. $2.00/kgal activated from 01/01/2025, the change to $2.20
    filed through `create_rate_schedule_version` from 06/16/2026, which stamps
    the old version's end 06/15/2026 by itself. June's 10 kgal (one read at
    period end) splits evenly by day — 15 days each side — so the bill is
    **5 × $2.00 + 5 × $2.20 = $10.00 + $11.00 = $21.00**, one bill, two usage
    lines, each naming its own version. Never $20.00 or $22.00."""
    with tenant_ctx(brazos):
        plan = make_plan(brazos, name="Wave A Water", services=("water",))
        state_the_water_base_as_zero(brazos)
        tariff = models.PlanRateSchedule.objects.get(rate_plan=plan).tariff
        one_tier = lambda price: [{"from_qty": "0", "to_qty": None, "unit_price": price}]  # noqa: E731
        services.activate_rate_schedule(
            dana, tariff.id,
            {"model": "tiered", "uom": "kgal", "effective_from": "2025-01-01",
             "structure": {"tiers": one_tier("2.00")}},
        )
        services.create_rate_schedule_version(
            dana, tariff.id,
            {"model": "tiered", "uom": "kgal", "effective_from": BOUNDARY.isoformat(),
             "reason": "Council order 2026-31", "structure": {"tiers": one_tier("2.20")}},
        )
        old, new = selectors.tariff_versions(tariff)
        assert old.effective_to == date(2026, 6, 15)  # stamped by the save path
        for version in (old, new):
            serve_the_ratified_size(brazos, version)

        cycle = a_cycle(brazos, "CR157-1")
        unit = a_cycled_water_unit(
            dana, brazos, cycle, plan, asset_no="W-15701", reads=[(PERIOD_END, "10.000000")]
        )
        account = an_account(brazos, unit["id"], "A-15701")
        invoice = an_ordinary_bill(brazos, cycle, "cr157-split")

        assert _amounts(invoice, "usage") == [Decimal("10.00"), Decimal("11.00")]
        assert invoice.subtotal == Decimal("21.00")
        assert billing_models.Invoice.objects.filter(account_id=account.id).count() == 1
        assert (invoice.period_start, invoice.period_end) == (PERIOD_START, PERIOD_END)
        stamped = {
            str(line.tariff_version_id): line.amount
            for line in invoice.lines.all()
            if line.kind == "usage"
        }
        assert stamped == {str(old.id): Decimal("10.00"), str(new.id): Decimal("11.00")}

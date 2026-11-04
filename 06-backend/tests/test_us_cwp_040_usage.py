# ── Trace ──────────────────────────────────────────────
# Story:    US-CWP-040 (EP-CWP-08) — *Usage, and the services that are not
#           measured say so*. Screen: CWP-033 (blueprint `P19`)
# Rules:    BR-CWP-073 (unmeasured services say what they are billed on — **no
#           empty chart**) · BR-CWP-093 (nothing empty ever appears) ·
#           BR-CWP-095 (one tip, on and in season, or no slot) · BR-CWP-010 ·
#           BR-MET-106 (an unread month is ABSENT, never 0) · BR-TEN-1180
#           (`billing_basis` is three values) · CLAUDE.md hard rule 3
# Tests:    this file — `US-CWP-040` §3 TC-1 … TC-8, and the home tile's move
# Impacts:  apps/portal/selectors.py `account_usage`, `home` ·
#           apps/portal/seams/metering_seam.py · seams/tenancy_seam.py
# ───────────────────────────────────────────────────────
"""`US-CWP-040`'s cases — and **three of the eight are about an absence**.

TC-3, TC-4 and TC-5 all assert that a service which produces no reading gets a
SENTENCE and not a chart, because *"a portal that pretends otherwise will be
asked where the missing graph is"*.

⚠ **THIS FILE ALSO PINS THE HOME TILE'S MOVE (PO ruling 2026-09-04).** The tile
used to sum `invoice_lines`; it reads the stored months now, and the test that
matters is the one that proves an unread month is not a zero — which a bill-line
read could never answer, because a bill line has no row for a month nobody read.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from apps.portal import selectors
from apps.portal.seams import tenancy_seam
from core.tenancy import tenant_context

from tests.test_us_cwp_usage_helpers import *  # noqa: F401,F403
from tests.test_us_cwp_usage_helpers import (
    HIGHEST,
    LOWEST,
    MONTHLY_GALLONS,
    YEAR_TOTAL,
    a_read,
    a_refuse_cart,
    a_water_meter,
    elm_unit_with_services,
    state_the_months,
    twelve_months_of_water,
)

pytestmark = pytest.mark.django_db

TODAY = date(2026, 9, 2)


class _Principal:
    def __init__(self, tenant_id, account_ids):
        self.tenant_id = tenant_id
        self.account_ids = tuple(str(one) for one in account_ids)
        self.accounts = ()


def a_year_of_water(tenant, actor, *, codes=("water", "sewer", "trash")):
    account = elm_unit_with_services(tenant, actor, codes=codes)
    meter = None
    if "water" in codes:
        meter = a_water_meter(tenant, actor, account.unit_id)
        twelve_months_of_water(tenant, actor, account, meter["id"])
    if "trash" in codes:
        a_refuse_cart(tenant, actor, account.unit_id)
    state_the_months(tenant, actor, account)
    return account, meter


def read(tenant, account, *, months=12):
    with tenant_context(tenant.id):
        return selectors.account_usage(
            _Principal(tenant.id, [account.pk]), account, months=months, today=TODAY
        )


def service(view, code):
    return next(row for row in view["services"] if row["code"] == code)


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · A WATER ACCOUNT WITH TWELVE MONTHS OF READS
# ══════════════════════════════════════════════════════════════════════════
def test_tc1__the_water_panel_carries_its_figures_and_its_unit(pine_hill, sarah):
    """⚠ **READ OVER TWENTY-FOUR MONTHS, AND THE REASON IS THE CALENDAR RATHER
    THAN THE FIXTURE.** The twelve stated months run September 2025 to August
    2026; the clock is **2 September 2026**, so a twelve-month window is
    October 2025 to September 2026 and September 2025 falls off the front of
    it. The wider window is where all twelve of the story's figures are, and
    the narrower one is asserted in TC-8 — including the September that has not
    been read yet, which is `BR-MET-106` happening for real rather than in a
    contrived case."""
    account, _meter = a_year_of_water(pine_hill, sarah)
    water = service(read(pine_hill, account, months=24), "water")

    assert water["measured"] is True
    assert water["basis"] == tenancy_seam.BASIS_METERED
    series = water["series"]
    assert series["unit"] == "gal", "hard rule 3 — the unit rides with the figures"
    assert series["months_present"] == len(MONTHLY_GALLONS)

    drawn = [point for point in series["points"] if not point["absent"]]
    assert [Decimal(point["quantity"]) for point in drawn] == [
        Decimal(gallons) for gallons in MONTHLY_GALLONS
    ]
    assert drawn[-1]["quantity_display"] == str(HIGHEST)
    #: `US-CWP-040` §4's own totals, reproduced from the fixture.
    assert sum(int(point["quantity_display"]) for point in drawn) == YEAR_TOTAL
    assert min(int(point["quantity_display"]) for point in drawn) == LOWEST


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · THE CHART'S SOURCE — TWELVE POINTS, ONE UNIT, NOTHING SUMMED
# ══════════════════════════════════════════════════════════════════════════
def test_tc2__twelve_points_and_no_total_across_services(pine_hill, sarah):
    """⚠ **THERE IS NO TOTAL KEY AND THERE NEVER WILL BE.** Gallons and therms
    share a month and nothing else (hard rule 3); the screen draws one chart per
    service because the read is shaped that way."""
    view = read(pine_hill, a_year_of_water(pine_hill, sarah)[0])
    assert "total" not in view
    for row in view["services"]:
        assert "total" not in row
    assert len(service(view, "water")["series"]["points"]) == 12


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · negative — THE SEWER PANEL SAYS *billed on water used*, NO CHART
# ══════════════════════════════════════════════════════════════════════════
def test_tc3__sewer_is_a_share_of_water_and_draws_nothing(pine_hill, sarah):
    """`BR-CWP-073`, and `BR-TEN-1180`'s `share` basis is the column that says
    so. ⚠ **`series` IS `None` AND NOT AN EMPTY SERIES** — an empty series is a
    chart with no bars, which is the empty chart the rule forbids."""
    account, _meter = a_year_of_water(pine_hill, sarah)
    sewer = service(read(pine_hill, account), "sewer")

    assert sewer["measured"] is False
    assert sewer["basis"] == tenancy_seam.BASIS_SHARE
    assert sewer["series"] is None
    assert sewer["billed_on"] == {"kind": "share", "of": "water"}


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · negative — THE TRASH PANEL NAMES THE CART
# ══════════════════════════════════════════════════════════════════════════
def test_tc4__trash_is_billed_on_the_cart_at_the_kerb(pine_hill, sarah):
    """`BR-RAT-090` — an unmetered service's quantity is a COUNT OF ITS ASSETS
    ON THE UNIT, observed and never typed. One cart reads *your 96 gal cart*."""
    account, _meter = a_year_of_water(pine_hill, sarah)
    trash = service(read(pine_hill, account), "trash")

    assert trash["measured"] is False
    assert trash["basis"] == tenancy_seam.BASIS_CAPACITY
    assert trash["series"] is None
    assert trash["billed_on"]["kind"] == "equipment"
    assert trash["billed_on"]["count"] == 1
    #: ⚠ **THE SIZE CLASS AS A PERSON READS IT, NEVER `T-96`** — the ratified
    #: vocabulary's own name.
    assert trash["billed_on"]["size"] and "96" in trash["billed_on"]["size"]


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · negative — A TRASH-ONLY ACCOUNT HAS NO CHART AT ALL
# ══════════════════════════════════════════════════════════════════════════
def test_tc5__a_trash_only_account_has_no_series_anywhere(pine_hill, sarah):
    """…and the screen still makes sense: the one panel it draws says what the
    charge is FOR."""
    account, _meter = a_year_of_water(pine_hill, sarah, codes=("trash",))
    view = read(pine_hill, account)

    assert [row["code"] for row in view["services"]] == ["trash"]
    assert all(row["series"] is None for row in view["services"])
    assert view["services"][0]["billed_on"]["kind"] == "equipment"


# ══════════════════════════════════════════════════════════════════════════
# TC-6 · negative — ONE MONTH OF HISTORY OFFERS NO YEAR-ON-YEAR COMPARISON
# ══════════════════════════════════════════════════════════════════════════
def test_tc6__no_comparison_is_offered_against_nothing(pine_hill, sarah):
    """⚠ **`absent_reason`, NOT `0.0%`.** *"No change"* and *"we cannot say"*
    are different claims, and `BR-MET-106` refuses to make the first one."""
    account = elm_unit_with_services(pine_hill, sarah, codes=("water",))
    meter = a_water_meter(pine_hill, sarah, account.unit_id)
    a_read(pine_hill, account, meter["id"], day=date(2026, 8, 31),
           current="153040", consumption="4820")
    state_the_months(pine_hill, sarah, account)

    yoy = service(read(pine_hill, account), "water")["series"]["metrics"]["yoy"]
    assert yoy["value"] is None
    assert yoy["absent_reason"] is not None


# ══════════════════════════════════════════════════════════════════════════
# TC-7 · tenant isolation
# ══════════════════════════════════════════════════════════════════════════
def test_tc7__an_oak_ridge_session_cannot_read_pine_hills_usage(
    pine_hill, sarah, oak_ridge, elena
):
    account, _meter = a_year_of_water(pine_hill, sarah)
    with tenant_context(oak_ridge.id):
        with pytest.raises(RuntimeError, match="BR-CWP-005"):
            selectors.account_usage(
                _Principal(pine_hill.id, [account.pk]), account, months=12, today=TODAY
            )


# ══════════════════════════════════════════════════════════════════════════
# TC-8 · TWENTY-FOUR MONTHS FROM THE SAME SOURCE, NO RE-COMPUTED UNIT
# ══════════════════════════════════════════════════════════════════════════
def test_tc8__the_wider_window_is_the_same_read_with_the_same_unit(pine_hill, sarah):
    account, _meter = a_year_of_water(pine_hill, sarah)
    twelve = read(pine_hill, account, months=12)
    twenty_four = read(pine_hill, account, months=24)

    assert len(service(twelve, "water")["series"]["points"]) == 12
    assert len(service(twenty_four, "water")["series"]["points"]) == 24
    assert (
        service(twelve, "water")["series"]["unit"]
        == service(twenty_four, "water")["series"]["unit"]
        == "gal"
    )
    #: ⚠ **THE TWELVE-MONTH WINDOW ENDS ON THE CURRENT MONTH, AND SEPTEMBER HAS
    #: NOT BEEN READ ON 2 SEPTEMBER.** That month is `absent: true` with a null
    #: quantity — never a `0`, which would tell Maria she has used no water this
    #: month. September 2025 falls off the front of the same window, so eleven
    #: of the twelve stated months are drawn here and all twelve in the wider
    #: one.
    narrow_absent = [p for p in service(twelve, "water")["series"]["points"] if p["absent"]]
    assert len(narrow_absent) == 1
    assert narrow_absent[0]["month"] == "2026-09"
    assert narrow_absent[0]["quantity"] is None
    assert service(twelve, "water")["series"]["months_present"] == 11

    #: The wider window carries all twelve stated months and twelve ABSENT
    #: ones — never twelve zeros (`BR-MET-106`).
    absent = [p for p in service(twenty_four, "water")["series"]["points"] if p["absent"]]
    assert len(absent) == 12
    assert all(point["quantity"] is None for point in absent)


# ══════════════════════════════════════════════════════════════════════════
# THE READ WINDOW — `CWP-033`'s third tile, and `None` closes it up
# ══════════════════════════════════════════════════════════════════════════
def test_no_open_window_closes_the_tile_rather_than_dashing_it(pine_hill, sarah):
    account, _meter = a_year_of_water(pine_hill, sarah)
    assert read(pine_hill, account)["next_reading"] is None


def test_an_open_window_is_served_with_both_of_its_dates(pine_hill, sarah):
    """⚠ **THE READ `billing_seam.reading_window_open` SAID DID NOT EXIST.**
    `ReadWindow` is a metering table with the period on it; the tile draws
    *2–6 Sep* from these two dates and the catalogue writes the sentence."""
    from apps.metering import models as metering_models

    account, _meter = a_year_of_water(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        point = metering_models.ServicePoint.objects.filter(
            tenant_id=pine_hill.id, unit_id=account.unit_id
        ).first()
        route = metering_models.Route.objects.create(
            tenant_id=pine_hill.id, code="R-1", name="Route 1"
        )
        metering_models.ServicePoint.objects.filter(pk=point.pk).update(route_id=route.id)
        metering_models.ReadWindow.objects.create(
            tenant_id=pine_hill.id, route_id=route.id,
            period_start=date(2026, 9, 2), period_end=date(2026, 9, 6),
        )

    window = read(pine_hill, account)["next_reading"]
    # ⚠ **`days_until` JOINED THE ANSWER ON 2026-09-08** (`CR-085` `CPB-09`) —
    # the Readings screen asks *"Next read: Sep 30 · in 22 days"* and the count
    # is the server's, not a screen's, so `today` decides it and no browser can
    # disagree with a clerk. It is clamped at zero: a crew already walking the
    # route is not *"in −3 days"*, which is why an OPEN window reads `0` here.
    assert window == {
        "from": "2026-09-02",
        "to": "2026-09-06",
        "open_now": True,
        "days_until": 0,
    }


# ══════════════════════════════════════════════════════════════════════════
# THE HOME TILE'S MOVE — PO ruling 2026-09-04
# ══════════════════════════════════════════════════════════════════════════
def test_the_home_tile_reads_the_stored_months_and_carries_its_unit(pine_hill, sarah):
    """⚠ **THIS IS THE FIGURE THE BILL-LINE READ COULD NOT PRODUCE.** The tile
    is *the last month STATED*, `4,820 gal`, and it comes from `monthly_usage`
    — not from what happens to have been billed."""
    account, _meter = a_year_of_water(pine_hill, sarah)
    with tenant_context(pine_hill.id):
        view = selectors.home(_Principal(pine_hill.id, [account.pk]), today=TODAY)

    assert len(view["usage"]) == 1
    row = view["usage"][0]
    assert row["service"] == "water"
    assert row["unit"] == "gal"
    #: `BR-MET-144` — two decimals, trailing zeros trimmed. The stored figure is
    #: `NUMERIC(18,6)`, so a screen printing `quantity` would read
    #: `4820.000000 gal` (`DEF-CWP-3770`).
    assert row["quantity_display"] == "4820"
    #: …and the STORED figure keeps its `NUMERIC(18,6)` shape, which is exactly
    #: why the display string has to be composed by the server: a screen that
    #: printed this one would read `4820.000000 gal`.
    assert row["quantity"] == "4820.000000"
    #: Eleven, not twelve: the tile's window ends on the CURRENT month and
    #: September 2025 falls off the front of it. See TC-8.
    assert len(view["usage_series"]) == 11


def test_the_home_tile_is_absent_for_an_account_with_no_stated_month(pine_hill, sarah):
    """`US-CWP-025` TC-5 — a trash-only account has no meter, so there is no
    tile and **no empty chart**. `[]` is the honest answer, and it is also the
    answer for *nobody has read this meter yet*."""
    account, _meter = a_year_of_water(pine_hill, sarah, codes=("trash",))
    with tenant_context(pine_hill.id):
        view = selectors.home(_Principal(pine_hill.id, [account.pk]), today=TODAY)
    assert view["usage"] == []
    assert view["usage_series"] == []

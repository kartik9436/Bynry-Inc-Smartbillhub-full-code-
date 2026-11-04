"""OQ-RBS-1757 — the clerk states today's weather, and the run uses it.

PO ruling 2026-09-07, verbatim: *"when you run this runbook, ask user to check
temp range from ddropdown and use that details in logic"*.

⚠ **WHY EACH CASE IS SHAPED THE WAY IT IS.** The failure that matters here is
one-directional: disconnecting somebody in a heatwave is unrecoverable, and
declining to disconnect them is a day's delay. So every case below asks whether
the run HOLDS when it should, and the unknown-band case asks whether an absent
answer holds rather than clears — a guard that fails open is not a guard.
"""

from __future__ import annotations

import pytest

from apps.runbooks.definitions import disconnect_eligibility as rb


class _Ctx:
    def __init__(self, band):
        self.params = {"weather_today": band} if band is not None else {}
        self.set_results = {"_protections": {}}


def _run(band):
    ctx = _Ctx(band)
    out = rb.step_check_the_weather_moratorium(ctx, [])
    return ctx, out


@pytest.mark.parametrize(
    "band", [rb.WEATHER_BAND_BELOW_FREEZING, rb.WEATHER_BAND_ABOVE_100]
)
def test_the_two_bands_the_card_names_hold_the_whole_run(band):
    """`RB-112`'s own thresholds: below 32°F and above 100°F."""
    ctx, out = _run(band)
    assert ctx.set_results["_weather_holds"] is True
    assert out["checked"]["area_wide_moratorium_in_force"] is True
    assert out["checked"]["weather_band_the_clerk_reported"] == band


def test_a_mild_day_does_not_hold_and_is_a_JUDGMENT_not_a_silence():
    """⚠ THE CASE THE OLD BEHAVIOUR COULD NOT PASS.

    Until today this step reported `area_wide_forecast_checked: False` for every
    run and the tile read *Not checked*, never a green *No* — deliberately,
    because *we looked and it is fine* and *nobody looked* send a crew to
    opposite places. A person answering is what earns the true `No`, so this
    asserts BOTH: the run does not hold, and the check is recorded as made.
    """
    ctx, out = _run(rb.WEATHER_BAND_MILD)
    assert ctx.set_results["_weather_holds"] is False
    assert out["checked"]["area_wide_moratorium_in_force"] is False
    assert out["checked"]["area_wide_forecast_checked"] is True


@pytest.mark.parametrize("band", [None, "", "sunny", "below_0f"])
def test_an_absent_or_unknown_band_HOLDS_rather_than_clears(band):
    """A guard that fails open is not a guard. The parameter is required, so
    this should be unreachable through `run_parameters` — which is exactly why
    it is asserted here rather than assumed."""
    ctx, _ = _run(band)
    assert ctx.set_results["_weather_holds"] is True


def test_the_dropdown_offers_exactly_the_three_bands_and_is_required():
    """⚠ THE CASE THAT CATCHES A DRIFT BETWEEN THE CONTROL AND THE LOGIC.

    Everything above tests the step against constants. If the PARAMETER stopped
    offering a band, or stopped being required, every assertion above would
    still pass while a clerk was handed a control that no longer matches the
    rule — so this asks the definition itself.
    """
    param = {p.name: p for p in rb.RUNBOOK.parameters}["weather_today"]
    assert param.choices == rb.WEATHER_BANDS
    assert param.required is True, (
        "a default here would be a plausible wrong answer — a clerk who has not "
        "looked out of the window must say so"
    )
    assert param.default is None


def test_the_per_account_moratorium_is_untouched_by_the_ruling():
    """A regulator's order on one account outlives today's temperature, so the
    per-ACCOUNT window still gathers and still removes on a mild day."""
    ctx = _Ctx(rb.WEATHER_BAND_MILD)
    ctx.set_results["_protections"] = {"A-1": {"weather_moratorium": True}, "A-2": {}}
    out = rb.step_check_the_weather_moratorium(ctx, [])
    assert out["found"]["held_by_a_moratorium"] == ["A-1"]
    assert out["checked"]["accounts_held_by_a_recorded_moratorium"] == 1

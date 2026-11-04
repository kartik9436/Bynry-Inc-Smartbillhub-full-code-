"""CR-079 — THE ESTIMATION METHOD IS A CHOICE, AND EVERY CHOICE IS REAL.

PO ruling 2026-09-07, verbatim: *"this should be drop down options - give 4 to
5 options here"*, then *"we are good with these + add last 6 month avg + Use
avg from plan"*. Until that day `est_method` accepted exactly one value
(BR-MET-026) and the S64 screen drew it as a read-only box.

WHAT THESE CASES EXIST TO STOP:
  1. **THE DEFAULT MOVING.** Changing how a missing reading is estimated
     changes what a customer is billed. `trailing_3_daily_avg` must compute
     precisely what it computed before this change — GT-9's own figures — and
     nothing may migrate a stored row onto a different method.
  2. **A DROPDOWN OVER ONE IMPLEMENTATION.** Hard-won law 2: a control that
     looks live and does nothing. Every method the screen lets you STORE has
     to change the arithmetic.
  3. **A METHOD QUIETLY BECOMING ANOTHER METHOD.** `same_period_last_year` on
     a customer with four months of history must REFUSE, not fall back to an
     average of those four — the fallback bills a customer under a rule
     nobody chose, which is the worst outcome available here.
"""

from decimal import Decimal

from apps.metering import estimation


class _Config:
    def __init__(self, method: str, cap: int = 5) -> None:
        self.est_method = method
        self.est_max_consecutive = cap


def _reads(n: int, per_period: str = "300", days: int = 30):
    """`n` actual periods, newest first, each `per_period` over `days` days."""
    return [(Decimal(per_period), days) for _ in range(n)]


# ── 1 · the default does not move ──────────────────────────────────────────
def test_gt9_figures_reproduce_exactly_on_the_default_method():
    """GT-9 ❄️: 612 + 618 + 624 over 90 days → 20.600000/day → × 30 = 618.000000."""
    spec = estimation.EstimationInput(
        channel="consumption",
        unit="kWh",
        days_in_period=30,
        trailing_actuals=[(Decimal("612"), 30), (Decimal("618"), 30), (Decimal("624"), 30)],
    )
    out = estimation.estimate(spec, _Config(estimation.METHOD_TRAILING_3_DAILY_AVG))
    assert out.estimated is True
    assert out.consumption == Decimal("618.000000")
    assert out.daily_average == Decimal("20.600000000000000000000000000")
    # BR-MET-028's short label is untouched for the signed method.
    assert out.method == estimation.METHOD_LABEL


def test_the_seeded_default_is_still_the_trailing_three():
    assert estimation.EST_METHODS[0] == estimation.METHOD_TRAILING_3_DAILY_AVG


# ── 2 · every storable method actually changes the arithmetic ──────────────
def test_a_longer_window_reaches_further_back_and_says_so():
    """Six periods of 100 then six of 400. Three-period looks at 100 only;
    twelve-period sees both and lands halfway. A dropdown over one
    implementation returns the same figure for both, which is the defect."""
    trailing = _reads(6, "100") + _reads(6, "400")
    spec = estimation.EstimationInput(
        channel="consumption", unit="kWh", days_in_period=30, trailing_actuals=trailing
    )
    three = estimation.estimate(spec, _Config(estimation.METHOD_TRAILING_3_DAILY_AVG))
    six = estimation.estimate(spec, _Config(estimation.METHOD_TRAILING_6_DAILY_AVG))
    twelve = estimation.estimate(spec, _Config(estimation.METHOD_TRAILING_12_DAILY_AVG))
    assert three.consumption == Decimal("100.000000")
    assert six.consumption == Decimal("100.000000")
    assert twelve.consumption == Decimal("250.000000")
    assert twelve.detail["trailing_reads"] == 12
    # the row says WHICH rule made it, so two methods cannot be confused later
    assert twelve.method == estimation.METHOD_TRAILING_12_DAILY_AVG


def test_repeat_the_last_actual_uses_that_period_and_nothing_else():
    trailing = [(Decimal("900"), 30), (Decimal("100"), 30), (Decimal("100"), 30)]
    spec = estimation.EstimationInput(
        channel="consumption", unit="kWh", days_in_period=30, trailing_actuals=trailing
    )
    out = estimation.estimate(spec, _Config(estimation.METHOD_REPEAT_LAST_ACTUAL))
    assert out.consumption == Decimal("900.000000")
    assert out.detail["trailing_reads"] == 1


def test_same_period_last_year_takes_the_twelfth_period_back_on_its_own():
    """Eleven quiet periods and one big one a year ago. A trailing average of
    any length is dominated by the quiet ones; the seasonal method is not."""
    trailing = _reads(11, "100") + [(Decimal("1200"), 30)]
    spec = estimation.EstimationInput(
        channel="consumption", unit="kWh", days_in_period=30, trailing_actuals=trailing
    )
    out = estimation.estimate(spec, _Config(estimation.METHOD_SAME_PERIOD_LAST_YEAR))
    assert out.consumption == Decimal("1200.000000")
    assert out.detail["trailing_reads"] == 1


# ── 3 · a method never quietly becomes a different method ──────────────────
def test_same_period_last_year_REFUSES_rather_than_averaging_what_it_has():
    """Four months of history and a seasonal method chosen. The estimate must
    not silently become a four-month average — it bills a customer under a
    rule nobody chose. No estimate, send somebody out."""
    spec = estimation.EstimationInput(
        channel="consumption", unit="kWh", days_in_period=30, trailing_actuals=_reads(4)
    )
    out = estimation.estimate(spec, _Config(estimation.METHOD_SAME_PERIOD_LAST_YEAR))
    assert out.estimated is False
    assert out.reason == estimation.REASON_NO_HISTORY
    assert out.detail["forced_disposition"] == "field_visit"


def test_the_two_methods_with_no_input_are_refused_by_name():
    """`route_peer_average` has no definition of a peer group (OQ-MET-1761) and
    `plan_average` has no plan-held average to read (OQ-MET-1762). Offered on
    screen because the PO ruled them in; never run, and never guessed."""
    for method in (estimation.METHOD_ROUTE_PEER_AVERAGE, estimation.METHOD_PLAN_AVERAGE):
        assert method in estimation.EST_METHODS
        assert method not in estimation.RUNNABLE_EST_METHODS
        spec = estimation.EstimationInput(
            channel="consumption", unit="kWh", days_in_period=30, trailing_actuals=_reads(12)
        )
        out = estimation.estimate(spec, _Config(method))
        assert out.estimated is False
        assert out.reason == estimation.REASON_UNKNOWN_METHOD
        assert out.detail["configured_method"] == method


def test_a_method_that_cannot_run_cannot_be_STORED_either():
    """Defense in depth: the `<option>` is disabled, the form refuses, and the
    server refuses. Storing one would stop every estimate on the tenant."""
    from apps.metering import services

    assert set(services.EST_METHODS) == set(estimation.RUNNABLE_EST_METHODS)
    assert estimation.METHOD_ROUTE_PEER_AVERAGE not in services.EST_METHODS
    assert estimation.METHOD_PLAN_AVERAGE not in services.EST_METHODS


# ── DEF-MET-4489 · every rule the ENGINE serves has a name a clerk can read ──
def test_every_rule_the_engine_serves_has_wording_in_the_catalogue():
    """DEF-MET-4489's PREVENTION, as a check rather than a paragraph.

    The read-validation screen renders the rule list the ENGINE serves and
    falls back to the raw code when the catalogue has no entry — which is the
    right fail-open for an unknown rule and is INDISTINGUISHABLE from a missing
    translation. `row_key` and `unit_mismatch` were added to
    `validation.JUDGMENT_RULES` without their wording and rendered as bare
    snake_case among thirteen English names for as long as they existed.

    **NOTHING COULD HAVE SEEN IT.** `tsc` passes, every DOM assertion passes,
    and G15 — the only gate that reads catalogues — compares the eleven WITH
    EACH OTHER, so a key absent from all eleven is parity-perfect.

    RED FIRST, verbatim, against the catalogue before this lane's fix:
        AssertionError: 2 rule(s) the engine serves have no wording in
        en.json: ['metering.reads.status.row_key',
                  'metering.reads.status.unit_mismatch']

    ⚠ It asserts over `validation.ALL_RULES`, so a rule added tomorrow without
    its name fails HERE, at the moment it is added, rather than on a screen
    nobody is measuring.
    """
    import json
    import pathlib

    from apps.metering import validation

    catalogue = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2]
            / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    missing = [
        f"metering.reads.status.{rule}"
        for rule in validation.ALL_RULES
        if f"metering.reads.status.{rule}" not in catalogue
    ]
    assert not missing, f"{len(missing)} rule(s) the engine serves have no wording in en.json: {missing}"


def test_every_estimation_method_offered_says_when_to_pick_it():
    """Seven methods with no guidance is a worse screen than one method.

    The screen renders `metering.readValidation.estMethodWhen.<code>` with an
    empty `defaultValue`, so a method added without its line draws an EMPTY
    paragraph — a silence, which is the whole shape of DEF-MET-4480. This is
    the check that makes the silence impossible.
    """
    import json
    import pathlib

    from apps.metering import estimation

    catalogue = json.loads(
        (
            pathlib.Path(__file__).resolve().parents[2]
            / "07-frontend/src/i18n/locales/en.json"
        ).read_text(encoding="utf-8")
    )
    for code in estimation.EST_METHODS:
        for key in (
            f"settings.rules.choice.est_method.{code}",
            f"metering.readValidation.estMethodWhen.{code}",
        ):
            assert key in catalogue, f"{code} has no {key}"
            assert catalogue[key].strip(), f"{key} is empty — the screen would draw a blank line"

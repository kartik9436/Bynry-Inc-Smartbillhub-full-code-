# ── Trace ──────────────────────────────────────────────
# Change:  CR-087 task D1 (`PRB-16` / `PRB-24`) — the plan wizard's step 2 asks
#          for the outside-city surcharge as a PERCENTAGE and the server
#          converts it once. PO ruling 2026-09-08, recorded in the decision
#          log: *"The outside-city surcharge stopped asking for arithmetic.
#          'Type 1.15 to charge 15% more' is a multiplier a clerk computes, in
#          a product where a neighbouring field takes a percentage and another
#          takes a fraction — 15 typed into it would have charged fifteen
#          times the bill."*
# Rules:   BR-RAT-102 (the two gates and the factor) · BR-RAT-092 (a RATE is
#          stored at SIX places, because a multiplier is multiplied by
#          something before it becomes money) · CLAUDE.md hard rule 2 (money 4,
#          percentages 6, both DISPLAY 2)
# Judgment: decision log 2026-09-08, "CR-087 LANE D", item 1 — the API accepts
#          a percent and the COLUMN does not move. Four readers already agree
#          on `rate_plans.outside_city_factor`; changing the column to save one
#          conversion on one screen would move a 🔒 money path for a layout
#          reason.
# ───────────────────────────────────────────────────────
"""The percent goes in, the multiplier is stored, and nothing rounds on a screen.

⚠ **THE FIGURE THIS FILE EXISTS FOR IS THE ONE IN THE CR:** a clerk types `15`,
the stored multiplier is `1.150000`, and a `$100.00` bill outside the city
becomes `$115.00`. The old field asked for `1.15`, and `15` typed into THAT
would have multiplied every line by fifteen — a `$100.00` bill billing
`$1,500.00`. That is the defect this conversion removes, and the reason the
conversion may not live in the browser: two screens would eventually disagree
about which scale they were sending.
"""

from decimal import Decimal

import pytest

from apps.rating import models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _seed(env):
    from tests.test_us_rat_plans import _wizard_payload, _wizard_seed

    return _wizard_seed(env), _wizard_payload


def test_cr087_d1__fifteen_percent_in_stores_one_point_one_five(env):
    """The CR's own worked figure, end to end."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="15")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        row = models.RatePlan.objects.get(pk=plan["id"])
    # SIX places — BR-RAT-092. A multiplier is multiplied by something before it
    # becomes money, so truncating it moves the bill.
    assert row.outside_city_factor == Decimal("1.150000"), row.outside_city_factor
    # And the arithmetic a clerk was promised: $100.00 outside the city.
    assert (Decimal("100.00") * row.outside_city_factor).quantize(
        Decimal("0.01")
    ) == Decimal("115.00")


def test_cr087_d1__the_percent_and_its_display_come_back_on_the_read(env):
    """The screen re-opens on what was typed, and never scales anything itself."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="15")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        detail = selectors.plan_detail(plan["id"])
    assert detail["outside_city_factor"] == "1.150000"
    # Percentages store to SIX places (CLAUDE.md hard rule 2)...
    assert detail["outside_city_percent"] == "15.000000"
    # ...and DISPLAY two. The string a screen prints is the server's, and it
    # carries the symbol like every other percent this module serves
    # (`rate_display` "6.25%", `percent_display` "1.50%") — one convention, so a
    # screen showing a tax rate and a surcharge side by side cannot show two.
    assert detail["outside_city_percent_display"] == "15.00%"


def test_cr087_d1__no_surcharge_serves_null_and_not_zero(env):
    """`None` is *this plan does not surcharge*; `0` is *somebody typed nothing
    extra*. `plan_detail` already refuses to collapse the two for the factor, so
    the percent it derives must not collapse them either."""
    seed, payload_for = _seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload_for(env, seed))
        detail = selectors.plan_detail(plan["id"])
    assert detail["outside_city_factor"] is None
    assert detail["outside_city_percent"] is None
    assert detail["outside_city_percent_display"] is None


def test_cr087_d1__zero_percent_stores_the_identity_and_reads_back_as_zero(env):
    """A clerk who answers *yes* and then types 0 has said something, and the
    form must re-open on it rather than on an empty box."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="0")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        detail = selectors.plan_detail(plan["id"])
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.outside_city_factor == Decimal("1.000000")
    assert detail["outside_city_percent"] == "0.000000"


def test_cr087_d1__a_fractional_percent_keeps_all_six_places(env):
    """`7.25%` is a real utility rate. 1 + 7.25/100 = 1.072500 exactly."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="7.25")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.outside_city_factor == Decimal("1.072500")


def test_cr087_d1__a_negative_percent_is_refused(env):
    """A negative multiplier would invert every line of the bill, which is not a
    surcharge in any reading. The floor on the factor is 0; on the percent it is
    −100, and below that the factor itself goes negative."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="-150")
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_plan(env.admin, payload)
    # ⚠ NOT merely "some error names the field". Before the key was accepted at
    # all, `_reject_unknown` refused it with `rating.unknown_field` — so a test
    # asserting only the field name PASSED on unbuilt code, which is law 7's
    # *what would make this check pass wrongly*. It must be a RANGE refusal.
    assert any(
        error["field"] == "outside_city_percent"
        and error["message_key"] == "rating.below_minimum"
        for error in raised.value.field_errors
    ), raised.value.field_errors


def test_cr087_d1__naming_both_the_percent_and_the_factor_is_refused(env):
    """Two answers to one question. Reconciling them by precedence would make one
    of them lose silently, so the refusal names both fields."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_percent="15", outside_city_factor="1.5")
    with tenant_ctx(env.tenant), pytest.raises(errors.ValidationError) as raised:
        services.create_plan(env.admin, payload)
    # Same guard as above: `rating.unknown_field` would satisfy a bare field-name
    # assertion and prove nothing about the conflict this test is named for.
    assert any(
        error["field"] == "outside_city_percent"
        and error["message_key"] == "rating.plans.surcharge_stated_twice"
        for error in raised.value.field_errors
    ), raised.value.field_errors


def test_cr087_d1__the_multiplier_is_still_accepted_on_its_own(env):
    """Additive, not a replacement: the seeder, the sample fixture and every
    integration that already writes a multiplier keep working."""
    seed, payload_for = _seed(env)
    payload = payload_for(env, seed, outside_city_factor="1.5")
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload)
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.outside_city_factor == Decimal("1.500000")


def test_cr087_d1__an_edit_can_change_the_percent(env):
    """PATCH carries it too — the wizard edits a draft as often as it creates one."""
    seed, payload_for = _seed(env)
    with tenant_ctx(env.tenant):
        plan = services.create_plan(env.admin, payload_for(env, seed, outside_city_percent="15"))
        services.update_plan(env.admin, plan["id"], {"outside_city_percent": "8"})
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.outside_city_factor == Decimal("1.080000")

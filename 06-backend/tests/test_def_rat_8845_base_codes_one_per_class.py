"""Base charge codes: one live per service and class, a default GL, and the Rates tab shows them all.

Found by the charge-code walk of 2026-10-01 (`10-scripts/charge_codes_walk33.mjs`)
and decided for fixing by the coordinator (law 13 — no signed rule moves):

  * `DEF-RAT-8845` — a second LIVE base code for the same service and customer
    class was accepted at save; every bill for it then stopped with *"2 base
    charge codes for water. Scope them on Charge codes."* The save now refuses,
    naming the live code (`rating.charges.base_already_covered`). An EMPTY class
    list is every class, so it meets any other.
  * `DEF-RAT-8847` — a base configured through Add had no GL account; it now
    starts on its service's base revenue account, as the seeded ones do.
  * `DEF-RAT-8833` — a schedule that names no class showed only the first base
    code by code on its Rates tab; it now shows every class's code, row by row.
  * `DEF-RAT-8846` — a base price scheduled after today now reaches the tab
    (`base_next_change`, and each row's `next_*`), so *Next change* can say it.

RED FIRST (law 7): on the tip before the fix, the 8845 cases created the second
base (no refusal), the 8847 case read `gl_account_id is None`, the 8833 case
found one code in a payload with no `base_codes`, and the 8846 case found no
`base_next_change`.

WHAT WOULD PASS WRONGLY: a refusal of EVERY second base would pass the overlap
case — `tc2` saves a commercial base beside a residential one and expects it to
be ACCEPTED.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import transaction

from apps.rating import charge_prices, models, schedule_reads, seams, services

from tests.test_cr157_wave_b_schedule_reads import _water_schedule
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos, dana
from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures (env)
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _base(env, code, classes, amount="15.00"):
    return services.create_charge(
        env.admin,
        {
            "code": code,
            "name": f"{code} base",
            "service": "water",
            "charge_type": "recurring",
            "amount_rule": "flat",
            "is_base": True,
            "applies_to_customer_classes": classes,
            "amount": amount,
            "effective_from": "2026-01-01",
        },
    )


# ⚠ AMENDED 2026-10-09 (`DEF-RAT-10026`, PO ruling *"yes please do it"*): the
# `DEF-RAT-8845` refusal is REMOVED — a service may hold two or more base codes
# for the same customer class and the rate schedule names which one bills. tc1
# and tc2 asserted the refusal; they now assert the codes save.
def test_def_rat_8845_tc1__a_second_base_beside_an_every_class_one_now_saves(env):
    _water_schedule(env)  # BASE-W, every class
    with tenant_ctx(env.tenant):
        _base(env, "BASE-W2", ["commercial"])
        assert models.Charge.objects.filter(code="BASE-W2").exists()


def test_def_rat_8845_tc2__classes_that_meet_now_save_too(env):
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        base_w = models.Charge.objects.get(code="BASE-W")
        services.update_charge(env.admin, base_w.id, {"applies_to_customer_classes": ["residential"]})
        _base(env, "BASE-W-COM", ["commercial"])
        _base(env, "BASE-W-RES2", ["residential"])
        assert models.Charge.objects.filter(code="BASE-W-RES2", is_base=True).exists()


def test_def_rat_8847_a_base_made_without_a_gl_starts_on_its_services_base_revenue_account(env):
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        base_w = models.Charge.objects.get(code="BASE-W")
        services.update_charge(env.admin, base_w.id, {"applies_to_customer_classes": ["residential"]})
        row = _base(env, "BASE-W-COM", ["commercial"])
        expected = seams.ledger_default_gl_account_id_for_charge("BASE-W-COM", service="water", is_base=True)
    assert expected is not None, "the ledger names a water base revenue account in this fixture"
    assert row["gl_account_id"] == str(expected)


def test_def_rat_8833_a_schedule_naming_no_class_shows_every_classs_base_code(env):
    schedule = _water_schedule(env)
    with tenant_ctx(env.tenant):
        base_w = models.Charge.objects.get(code="BASE-W")
        services.update_charge(env.admin, base_w.id, {"applies_to_customer_classes": ["residential"]})
        _base(env, "BASE-W-COM", ["commercial"], amount="15.00")
        rates = schedule_reads.schedule_rates(schedule["id"])
        named = models.TariffVersion.objects.filter(tariff_id=schedule["id"]).values_list(
            "base_charge_code__code", flat=True
        )
    # ⚠ AMENDED 2026-10-06 (`DEF-RAT-9832`, PO ruling): this asserted every
    # class's base code (`BASE-W`, `BASE-W-COM`) on a schedule naming none — the
    # pool. The bill now reads ONLY the code the schedule names, so the tab
    # shows only that one: activation named `BASE-W` (the one code that could
    # serve then), and `BASE-W-COM`, added later, is not this schedule's base.
    assert set(named) == {"BASE-W"}
    assert [code["code"] for code in rates["base_codes"]] == ["BASE-W"]
    assert {row["code"] for row in rates["base_rows"]} == {"BASE-W"}
    assert [row["seq"] for row in rates["base_rows"]] == list(range(1, len(rates["base_rows"]) + 1))


def test_def_rat_8846_a_scheduled_base_price_reaches_the_rates_tab(env):
    schedule = _water_schedule(env)
    with tenant_ctx(env.tenant):
        base_w = models.Charge.objects.get(code="BASE-W")
        start = seams.tenant_today() + timedelta(days=31)
        live = charge_prices.live_prices(base_w)
        live[("W-58", None)] = Decimal("9.00")
        with transaction.atomic():
            charge_prices.save_prices(base_w, live, effective_from=start, effective_to=None)
        rates = schedule_reads.schedule_rates(schedule["id"])
    nxt = rates["base_next_change"]
    assert nxt is not None
    assert (nxt["code"], nxt["amount_display"], nxt["effective_from"]) == ("BASE-W", "9.00", start.isoformat())
    w58 = next(row for row in rates["base_rows"] if row["size_class"] == "W-58")
    assert (w58["amount_display"], w58["next_amount_display"]) == ("8.00", "9.00")

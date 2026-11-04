# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-RAT-8752 — three facts the charge-code view draws and no read
#           served (CR-156-BRC10 wave C): (1) the base code's per-size Minimum
#           (images 11, 51), (3) the Plans tab's customer class and accounts
#           (image 20). (2) the deposit Held tile stays open: no read of
#           deposits held BY CODE exists (accounts.deposit_on_file names no code).
# ───────────────────────────────────────────────────────
"""The schedules' minimum per size, and the Plans tab's class and accounts.

THE MINIMUM RULE, per size, over the version of every schedule on the base
code's service in force today:
  * all state the same figure → that figure (`one`) — the BASE-W case, $4.24;
  * all state one and they differ → `low – high` (`range`);
  * none states one → no figure (`none`);
  * some do and some do not → no figure (`mixed`): one schedule's connections
    are not floored, so any single number would be untrue of them.
WHAT WOULD MAKE IT PASS WRONGLY: reading only the FIRST schedule — so the
second schedule here states a different figure and the answer must be a range.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.rating import models, selectors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _set_minimums(env, schedule_id, figures):
    with tenant_ctx(env.tenant):
        version = models.TariffVersion.objects.filter(tariff_id=schedule_id).order_by("-effective_from").first()
        models.RateSizeRow.objects.filter(tariff_version=version).delete()
        for size_class, minimum in figures.items():
            models.RateSizeRow.objects.create(
                tenant=env.tenant,
                tariff_version=version,
                size_class=size_class,
                minimum_bill=None if minimum is None else Decimal(minimum),
            )


def test_the_minimum_column_reads_one_figure_a_range_or_nothing(env):
    env.enable("water")
    first = env.flat_schedule("Water residential", "water")
    second = env.flat_schedule("Water commercial", "water")
    _set_minimums(env, first["id"], {"5/8": "4.24", "1": "6.00", "2": "40.00", "3": None})
    _set_minimums(env, second["id"], {"5/8": "4.24", "1": "7.50", "2": None, "3": None})
    with tenant_ctx(env.tenant):
        base = models.Charge.objects.get(tenant=env.tenant, service__code="water", is_base=True, deleted_at__isnull=True)
        minimums = selectors.charge_detail(base)["size_minimums"]
    assert minimums["5/8"]["state"] == "one" and minimums["5/8"]["low_display"] == "4.24"
    assert minimums["1"]["state"] == "range"
    assert (minimums["1"]["low_display"], minimums["1"]["high_display"]) == ("6.00", "7.50")
    assert minimums["2"]["state"] == "mixed" and minimums["2"]["low"] is None
    assert minimums["3"]["state"] == "none"
    assert minimums["5/8"]["schedules"] == 2
    # The Add wizard reads the same answer by SERVICE, before any code is its base.
    with tenant_ctx(env.tenant):
        assert selectors.service_size_minimums(service_code="water") == minimums


def test_a_code_that_is_not_a_base_has_no_minimums(env):
    with tenant_ctx(env.tenant):
        from apps.rating import services

        row = services.create_charge(
            env.admin,
            {"code": "PAPER-X", "name": "Paper bill", "amount_rule": "flat", "amount": "2.00"},
        )
        detail = selectors.charge_detail(models.Charge.objects.get(pk=row["id"]))
    assert detail["size_minimums"] == {}


def test_the_plans_tab_rows_carry_customer_class_and_accounts(env):
    env.enable("water")
    env.flat_schedule("Water residential", "water")
    plan = env.plan("Residential standard", "RES-STD", [{"service": "water"}])
    with tenant_ctx(env.tenant):
        base = models.Charge.objects.get(tenant=env.tenant, service__code="water", is_base=True, deleted_at__isnull=True)
        rows = selectors.charge_reach_rows(base, [models.RatePlan.objects.get(pk=plan["id"])])
    assert rows[0]["plan_name"] == "Residential standard"
    # `[]` = every class; the plan names none here.
    assert rows[0]["customer_classes"] == []
    # No unit is assigned the plan, so no account is on it — 0, not None.
    assert rows[0]["accounts"] == 0

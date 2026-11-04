# ── Trace ──────────────────────────────────────────────
# Change:  CR-167-BRC10 round 4 task 10 (lane PLAN-WALK) — the full web walk.
# Defect:  DEF-RAT-9517 — once a rate schedule's UPCOMING version is corrected
#          (BR-RAT-1016 verb 2, same window), the plans read stopped naming it:
#          `schedule_ref` looked for the next version among ORIGINAL rows not
#          superseded, and after a correction the original is superseded and the
#          correction is not an original.
# Rules:   BR-RAT-1016 (correct over the same window) · CR-167 ruling 13 (a
#          banner names an upcoming version) · J6 (a correction keeps the number)
# ───────────────────────────────────────────────────────
"""Written RED against the tip before the fix (quoted in `CR-167-BRC10` §18)."""

from datetime import date

import pytest

from apps.rating import models, plan_reads, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _file(env, schedule_id):
    with tenant_ctx(env.tenant):
        return services.create_rate_schedule_version(
            env.admin,
            schedule_id,
            {
                "name": "Res Water",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2027-01-01",
                "structure": {"tiers": RES_WATER_TIERS},
                "reason": "New year",
            },
        )


def test_def_rat_9517__a_corrected_upcoming_version_is_still_next(env):
    env.enable("water")
    schedule = env.tiered_schedule("Res Water", "water", RES_WATER_TIERS)
    _file(env, schedule["id"])
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=schedule["id"])
        before = plan_reads.schedule_ref(tariff, date(2026, 10, 3))
        later = models.TariffVersion.objects.get(tariff=tariff, effective_from=date(2027, 1, 1))
        tiers = [dict(row, unit_price=str(round(float(row["unit_price"]) * 1.1, 4))) for row in RES_WATER_TIERS]
        services.correct_rate_schedule_version(
            env.admin,
            tariff.id,
            later.id,
            {"name": "Res Water", "service": "water", "model": "tiered", "uom": "kgal",
             "structure": {"tiers": tiers}, "reason": "Typed the wrong prices"},
        )
        after = plan_reads.schedule_ref(tariff, date(2026, 10, 3))
    assert before["next"] == {"version": 2, "effective_from": "2027-01-01"}
    # The correction keeps v2's number and its window, and is still the next one.
    assert after["next"] == {"version": 2, "effective_from": "2027-01-01"}

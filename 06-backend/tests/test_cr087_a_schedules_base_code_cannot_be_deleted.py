# ── Trace ──────────────────────────────────────────────
# Change:   CR-087 — the rate-schedule conformance lane. PO ruling 2026-09-10,
#           relayed with the work: *"a charge code that is a schedule's base
#           counts as used by zero plans … Fix the count or refuse the delete —
#           do not leave it."*
# Rules:    BR-RAT-088 (PO 2026-08-20: *"the CHARGE CODE owns the base amount;
#           a plan displays it, never defines it"*, and PO 2026-08-31: *"plan ->
#           charges code -> base scharges"*) · BR-RAT-035 (the audit lock:
#           hard removal only at zero references)
# Tests:    this file
# Impacts:  apps/rating/selectors.charge_used_by gains `schedules` ·
#           apps/rating/services.delete_charge fails closed on it
# ───────────────────────────────────────────────────────
"""A code that is a service's BASE is referenced by every schedule on it.

`charge_used_by` counted `plan_charge_rules` alone — the codes a plan attaches
BY NAME. `BR-RAT-088` created a second and much larger kind of reference that
has no row anywhere: a code declaring `is_base` for a service is read by every
schedule and every plan on that service, and names nobody. So `BASE-W`, the code
every water connection's base comes from, reported **zero** references and the
audit lock let it be deleted.

**What that costs is `apps.billing.gather._base_charge_for`'s own order rather
than a guess:** the charge code states the base *"Full stop"*; remove it and the
resolution falls through to the plan, then to the schedule, then REFUSES — so
every water bill either silently re-prices from a superseded column or stops.
`BR-RAT-088`'s worked figure for getting one service's base wrong is
**$23,069.50 a month across 1,247 connections**.

── PROVED RED FIRST (hard-won law 7), through `pytest`, the harness that runs
── them. At HEAD, with the `schedules` key absent:

    test_a_code_that_is_a_services_base_counts_the_schedules_reading_it
        KeyError: 'schedules'

  and with `_charge_is_base_for_schedules` present but the lock left as it was
  (`if used["plans"] or used["invoice_lines"] …`):

    test_the_delete_is_refused_while_a_schedule_reads_it
        Failed: DID NOT RAISE <class 'apps.core.errors.BizError'>

── AND THE THIRD CASE IS THE ONE THAT KEEPS THE LOCK HONEST. Widening a lock is
── how a lock stops being usable, so `test_an_ordinary_code_is_still_deletable`
── asserts the OTHER direction: a code that is nobody's base still deletes at
── zero references, exactly as it did yesterday.
"""

from __future__ import annotations

import pytest

from core import errors
from apps.rating import models, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — env fixture
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db


def _base_code(env, **overrides):
    payload = {
        "code": "BASE-W",
        "name": "Water base service",
        "charge_type": "recurring",
        "service": "water",
        "amount_rule": "flat",
        "amount": "12.00",
        "is_base": True,
    }
    payload.update(overrides)
    with tenant_ctx(env.tenant):
        return services.create_charge(env.admin, {**(payload), "effective_from": "2000-01-01"})


def _water_schedule(env):
    with tenant_ctx(env.tenant):
        return services.create_rate_schedule(
            env.admin,
            {
                "name": "Residential water",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "structure": {"tiers": [dict(row) for row in RES_WATER_TIERS]},
            },
        )


def test_a_code_that_is_a_services_base_counts_the_schedules_reading_it(env):
    """`schedules` is a count of REFERENCES, not of rows in a join table.

    ⚠ **THE FIGURE IS THIS FILE'S OWN AND NOT A DRAWN ONE** (B14 rule 37).
    One schedule is enough to state the rule; the blueprint's numbers say a
    count goes here and nothing about what any real utility holds.
    """
    charge = _base_code(env)
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        used = selectors.charge_used_by(models.Charge.objects.get(id=charge["id"]))
    # No plan names this code, and that was the whole of the old answer.
    assert used["plans"] == 0
    assert used["schedules"] == 1


def test_a_code_that_is_nobodys_base_counts_no_schedules(env):
    """The OFF side, stated rather than inherited: an ordinary code is not
    suddenly referenced by every schedule on its service."""
    charge = _base_code(env, code="LATE-W", name="Late fee", is_base=False)
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        used = selectors.charge_used_by(models.Charge.objects.get(id=charge["id"]))
    assert used["schedules"] == 0


def test_the_delete_is_refused_while_a_schedule_reads_it(env):
    """BR-RAT-035's lock, now reaching the reference BR-RAT-088 created."""
    charge = _base_code(env)
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as raised:
            services.delete_charge(env.admin, charge["id"])
    assert raised.value.br_ref == "BR-RAT-035"
    # The row is still there — a refused delete deletes nothing.
    with tenant_ctx(env.tenant):
        assert models.Charge.objects.filter(id=charge["id"]).exists()


def test_an_ordinary_code_is_still_deletable_at_zero_references(env):
    """⚠ THE OTHER DIRECTION, AND IT IS WHY THIS CASE EXISTS. Widening a lock
    until nothing can ever be removed is the failure mode of widening a lock,
    so a code nothing references still goes, exactly as it did yesterday."""
    charge = _base_code(env, code="NSF", name="Returned payment", service=None, is_base=False)
    _water_schedule(env)
    with tenant_ctx(env.tenant):
        services.delete_charge(env.admin, charge["id"])
        assert not models.Charge.objects.filter(id=charge["id"]).exists()

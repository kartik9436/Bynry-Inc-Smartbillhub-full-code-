# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 unit wizard — the default-plan panel carries the
#           lock control)   Screens: S16
# Rules:    BR-MET-007 (plan lock gates changes BY PERMISSION) · BR-MET-035
#           (service-layer role guard) · A4 role matrix (roles are platform-
#           defined and closed: System Admin · Billing Clerk · Executive)
# Defect:   the PO's "gap 3", 2026-08-11 — plan_locked was written, read back
#           and asserted, and consulted by NOTHING. Hard-won law 2.
# ───────────────────────────────────────────────────────
"""The plan lock actually locks the plan.

`units.plan_locked` has existed since the unit wizard shipped. The wizard set
it, the selector returned it, `test_us_met_003_wizard` asserted it came back
True — and no code anywhere read it to decide anything. A "locked" plan could
be changed by any caller the endpoint already admitted. That is the exact
shape of hard-won law 2: built, tested, and not wired, so every test passed
while the feature did not exist.

WHAT THE LOCK MEANS. BR-MET-007 says it "gates changes by permission" without
naming the permission. The roles are closed (A4 CONFIRMED) and this surface
already admits System Admin and Billing Clerk only — Executive cannot reach it
at all. So inside that pair the rule has exactly one reading that gates
anybody: Admin passes, Clerk does not. That reading is recorded for PO
ratification in 12-governance/09-human-review-ledger.md rather than being
treated as settled by the fact that it is now code.

TC-4 IS THE ONE THAT MATTERS. A lock that guards only the plan id is not a
lock: a Clerk sends {"tariff_id": <new plan>, "plan_locked": false} and the payload
unlocks itself on the way past. The guard runs before ANY field of the plan
panel is touched, so that call refuses and the unit comes back still locked,
still on its original plan.
"""

import pytest

from apps.metering import models, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def locked_unit(actor, tenant, *, label="Suite 220"):
    """A unit carrying a plan with the lock ON, exactly as the wizard leaves it."""
    original = make_plan(tenant, name="Residential")
    premise = make_premises(actor, address_line="500 Mason Rd Plaza")
    unit = make_unit(actor, premise["id"], label=label, services=["electric"])
    services.assign_unit_plan(
        actor,
        unit["id"],
        {"tariff_id": str(original.id), "effective_from": "2026-09-01", "plan_locked": True},
    )
    return unit, original


def unit_row(unit_id):
    return models.Unit.objects.get(pk=unit_id)


def test_us_met_003_tc1__clerk_cannot_change_a_locked_plan(brazos, dana, marcus):
    """The defect itself: before the guard, this call SUCCEEDED."""
    with tenant_ctx(brazos):
        unit, original = locked_unit(dana, brazos)
        replacement = make_plan(brazos, name="Small Commercial")

        with pytest.raises(errors.BizError) as raised:
            services.assign_unit_plan(marcus, unit["id"], {"tariff_id": str(replacement.id)})

        assert raised.value.code == errors.BIZ_LOCKED
        assert raised.value.br_ref == "BR-MET-007"  # B8: every BIZ refusal names its rule
        # The refusal is only worth anything if nothing moved.
        assert unit_row(unit["id"]).rate_plan_id == original.id


def test_us_met_003_tc2__system_admin_can_change_a_locked_plan(brazos, dana):
    """The lock gates by permission — it does not freeze the unit outright."""
    with tenant_ctx(brazos):
        unit, _original = locked_unit(dana, brazos)
        replacement = make_plan(brazos, name="Small Commercial")

        result = services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(replacement.id)})

        assert result["rate_plan_id"] == str(replacement.id)
        assert unit_row(unit["id"]).rate_plan_id == replacement.id
        assert unit_row(unit["id"]).plan_locked is True  # still locked afterwards


def test_us_met_003_tc3__clerk_may_still_change_an_unlocked_plan(brazos, dana, marcus):
    """The guard must not over-reach: without the lock, a Clerk is unaffected."""
    with tenant_ctx(brazos):
        original = make_plan(brazos, name="Residential")
        premise = make_premises(dana, address_line="1901 Bluestem Ln")
        unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(original.id)})
        replacement = make_plan(brazos, name="Small Commercial")

        result = services.assign_unit_plan(marcus, unit["id"], {"tariff_id": str(replacement.id)})

        assert result["rate_plan_id"] == str(replacement.id)


def test_us_met_003_tc4__clerk_cannot_unlock_on_the_way_past(brazos, dana, marcus):
    """A lock a Clerk can clear in the same payload is not a lock.

    This is the bypass the guard placement exists to close: it runs BEFORE any
    field of the plan panel is read, so `plan_locked: false` never lands.
    """
    with tenant_ctx(brazos):
        unit, original = locked_unit(dana, brazos)
        replacement = make_plan(brazos, name="Small Commercial")

        with pytest.raises(errors.BizError) as raised:
            services.assign_unit_plan(
                marcus,
                unit["id"],
                {"tariff_id": str(replacement.id), "plan_locked": False},
            )

        assert raised.value.code == errors.BIZ_LOCKED
        after = unit_row(unit["id"])
        assert after.plan_locked is True  # the lock survived the attempt
        assert after.rate_plan_id == original.id


def test_us_met_003_tc5__bulk_assign_honours_the_lock_per_unit(brazos, dana, marcus):
    """Bulk is the same code path, so a locked unit fails while the rest land.

    BR-MET-041's bulk assign loops `_apply_unit_plan`, which is where the guard
    sits — so bulk cannot become the way around it. The unlocked unit still
    gets its plan: one refusal must not roll back the others.
    """
    with tenant_ctx(brazos):
        locked, locked_original = locked_unit(dana, brazos, label="Suite 220")
        premise = make_premises(dana, address_line="1901 Bluestem Ln")
        open_unit = make_unit(dana, premise["id"], label="Unit A", services=["electric"])
        replacement = make_plan(brazos, name="Small Commercial")

        result = services.bulk_assign_unit_plans(
            marcus,
            {
                "unit_ids": [str(locked["id"]), str(open_unit["id"])],
                "tariff_id": str(replacement.id),
            },
        )

        assert result["assigned"] == 1 and result["failed"] == 1
        assert result["errors"][0]["unit_id"] == str(locked["id"])
        assert unit_row(locked["id"]).rate_plan_id == locked_original.id
        assert unit_row(open_unit["id"]).rate_plan_id == replacement.id


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003 (EP-MET-01) — PO gap-3 remediation 2026-08-11
# generated: 2026-08-11 by Eng-Lead
# checklist: A✔ B✔ C✔ D=deferred(service-layer — the API inherits the guard) E=deferred(no UI change) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green — with the `_guard_plan_lock` call removed,
#         TC-1, TC-4 and TC-5 fail; TC-5's message IS the defect stated as a
#         number ("assert (2 == 1)" — both units re-planned, none refused).
#         TC-2 and TC-3 stay GREEN under the removal, correctly: TC-2 is the
#         System Admin path, which the guard lets through either way, and TC-3
#         is the over-reach check, which must not bite when no lock is set.
#         A red-proof that flipped all five would mean the tests were asserting
#         the guard's presence rather than the behaviour it produces.
# exceptions: the `metering.plan.locked` message key is NOT yet in the five
#         i18n catalogues — the frontend account-screens lane holds those files
#         in the working tree this minute and rewrites them wholesale, so
#         adding it here would be two writers on one file. Owed, and named in
#         the commit rather than implied done.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6932 — a rate schedule's NAMED base charge code is dropped
#          by every write that does not repeat it in its payload, so a "new
#          price, from a date" silently unbinds the schedule.
# Rules:   BR-RAT-1025 (the schedule NAMES its base charge code) · BR-RAT-037
#          (versions are append-only; a fix may never rewrite one) ·
#          BR-RAT-040 (the bulk rate-change batch) · CLAUDE.md hard-won law 1
#          (a comment claiming a guarantee is not the guarantee).
# Impacts: apps/rating/services.py (_validate_version_fields · _write_version ·
#          _apply_batch_to_schedule)
# ───────────────────────────────────────────────────────
"""**CLEARED ON PURPOSE AND NOT MENTIONED ARE DIFFERENT INTENTIONS.**

`_validate_base_charge_code` collapses them: it returns `None` both for
`{"base_charge_code": null}` — a person emptying the picker — and for a payload
with no `base_charge_code` key at all. `_write_version` then writes that `None`
onto the new version, so a save that simply did not mention the binding erases
it. Nothing refuses, nothing warns, and the schedule's own screen goes on
showing a base charge code until the page is reloaded.

Three tests here, and the middle one is the one that must stay green BOTH
before and after the fix — a carry-forward that also swallowed a deliberate
clear would be the same defect wearing the other face.

The fourth test is the bulk batch, which never carried the binding at all:
`_apply_batch_to_schedule` clones a version field by field (it carries the
regulator's filing details, by name, on purpose) and the FK is simply absent
from the list.
"""

from __future__ import annotations

import pytest

from apps.rating import api, models, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db

NEXT_TIERS = [
    {**tier, "unit_price": str(round(float(tier["unit_price"]) * 1.02, 4))}
    for tier in RES_WATER_TIERS
]


def _bound_water_schedule(env):
    """A live water schedule that NAMES its base charge code, exactly as a
    clerk leaves it after step 1 of RAT-03."""
    code = env.declare_base_charge_code("water")
    schedule = env.tiered_schedule(
        "Res Water · Inclining",
        "water",
        RES_WATER_TIERS,
        base_charge_code=str(code.id),
    )
    with tenant_ctx(env.tenant):
        version = models.TariffVersion.objects.get(pk=schedule["current_version"]["id"])
    assert version.base_charge_code_id == code.id, (
        "fixture precondition: the schedule must start out BOUND, or the "
        "assertions below would pass over a binding that was never made"
    )
    return schedule, code


def _latest(env, schedule):
    with tenant_ctx(env.tenant):
        return (
            models.TariffVersion.objects.filter(tariff_id=schedule["id"])
            .order_by("-effective_from", "-created_at")
            .first()
        )


def test_def_rat_6932__a_new_price_from_a_date_keeps_the_binding(env):
    """THE PO'S PATH. A live schedule, a new price from a date, and a payload
    that does not mention the base charge code — because step 1's picker is not
    what the clerk came to change.

    The binding must be CARRIED FORWARD onto the new version. Before the fix
    the new version's `base_charge_code_id` is NULL and the schedule quietly
    stops naming anything.
    """
    schedule, code = _bound_water_schedule(env)
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            schedule["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-10-01",
                "reason": "Board-approved 2% uplift, 2026",
                "structure": {"tiers": NEXT_TIERS},
            },
        )
    assert _latest(env, schedule).base_charge_code_id == code.id


def test_def_rat_6932__an_explicit_null_still_clears_it(env):
    """THE OTHER INTENTION, AND IT MUST SURVIVE THE FIX.

    A clerk who empties the picker posts `base_charge_code: null` — the front
    end sends the key even when it is empty, on purpose. That is a person
    saying *this schedule names nothing*, and the new version must hold NULL.
    Green before the fix and green after it; a carry-forward that could not
    tell this from silence would be the same bug in the mirror.

    ⚠ **AMENDED 2026-10-06 (`DEF-RAT-9797`, PO ruling: *"base charges will be
    atatched to rate schedule"* — a schedule names EXACTLY ONE base code).**
    *"This schedule names nothing"* is no longer a state a billing version can
    hold while its service has a base code: with ONE code that could serve it,
    the emptied picker is answered by naming that code (the same code the
    declared base would have answered with — the bill does not move); with two
    or more the save refuses *"Choose a base charge code."* The carry-forward
    this test guards is still told apart from the explicit null: the null is
    resolved to the only candidate, never to a stale binding.
    """
    schedule, code = _bound_water_schedule(env)
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            schedule["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "base_charge_code": None,
                "effective_from": "2026-10-01",
                "reason": "Let the service's declared base answer",
                "structure": {"tiers": NEXT_TIERS},
            },
        )
    assert _latest(env, schedule).base_charge_code_id == code.id  # DEF-RAT-9797


def test_def_rat_6932__a_correction_keeps_the_binding(env):
    """BR-RAT-104 — a CORRECTION restates the SAME window, and `_write_version`
    says in its own words that a correction *"builds its `cleaned` from the row
    it is restating"*. It does not: only the dates and the change note are
    copied. Hard-won law 1, inside the money path it describes.
    """
    schedule, code = _bound_water_schedule(env)
    with tenant_ctx(env.tenant):
        services.correct_rate_schedule_version(
            env.admin,
            schedule["id"],
            schedule["current_version"]["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Typed 3.10 for the second tier; the filing says 3.01",
                "structure": {"tiers": NEXT_TIERS},
            },
        )
    with tenant_ctx(env.tenant):
        correction = (
            models.TariffVersion.objects.filter(tariff_id=schedule["id"])
            .exclude(corrects__isnull=True)
            .first()
        )
    assert correction is not None
    assert correction.base_charge_code_id == code.id


def test_def_rat_6932__the_bulk_rate_change_batch_carries_the_binding(env, job_store, audit_rows):
    """THE SIXTH WRITER, AND IT LOSES THE BINDING WHATEVER THE PAYLOAD SAYS.

    `_apply_batch_to_schedule` is the one writer of `tariff_versions` that does
    not go through `_write_version` (`DEF-499` named it). It clones the version
    field by field and carries the regulator's filing details BY NAME, on
    purpose — the FK is simply not in the list. So one clerk, one uplift, and
    every schedule a utility has stops naming its base charge code at once.
    """
    schedule, code = _bound_water_schedule(env)
    with tenant_ctx(env.tenant):
        accepted = services.request_rate_change_batch(
            env.admin,
            {
                "entities": [{"type": "schedule", "id": schedule["id"]}],
                "change": {"kind": "percent", "value": "3.0"},
                "effective_from": "2027-01-01",
                "reason": "Board order 2026-12 annual adjustment",
            },
        )
    services.run_rate_change_job(accepted["job_id"])
    assert _latest(env, schedule).base_charge_code_id == code.id


# ── THE SAME QUESTION THROUGH THE ROUTE THE SCREEN ACTUALLY POSTS TO ────────
def test_def_rat_6932__the_endpoint_keeps_the_binding_when_the_body_omits_it(env):
    """`POST /rate-schedules/{id}/versions`, because the payload SHAPE is the
    whole question and a service-layer test can pass while the product still
    loses the binding.

    ⚠ **THE FRONT END IS NOT THE CULPRIT HERE AND THAT IS WORTH ASSERTING
    RATHER THAN ASSUMING.** `RateScheduleWizard.draftPayload` posts
    `base_charge_code` on EVERY save, even when it is empty, on purpose — and
    `draftFromSchedule` reloads it from the version being replaced, so the
    wizard's own body carries the binding round the trip. What this case covers
    is every OTHER writer of this route: a client filing a rate change, an
    import, a script. They have no reason to repeat a field they are not
    changing, and until `DEF-RAT-6932` that silently unbound the schedule.
    """
    schedule, code = _bound_water_schedule(env)
    response = api_call(
        api.rate_schedule_versions,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={
            "model": "tiered",
            "uom": "kgal",
            "effective_from": "2026-10-01",
            "reason": "Board-approved 2% uplift, 2026",
            "structure": {"tiers": NEXT_TIERS},
        },
        tariff_id=str(schedule["id"]),
    )
    assert response.status_code == 201, response.data
    written = _latest(env, schedule)
    assert written.base_charge_code_id == code.id
    # And the row the screen reads back says so too, by id and by label — a
    # stored binding the serializer does not publish is hard-won law 2.
    #
    # ⚠ **READ THROUGH `version_row` AND NOT THROUGH THE RESPONSE'S
    # `current_version`, WHICH IS A FALSE PASS HERE.** `current_version` is the
    # version IN FORCE TODAY, and this one opens on 2026-10-01 — so that key
    # still describes the row being REPLACED, which carries the binding whether
    # the new one does or not. The first draft of this test asserted it and
    # passed for that reason; its mirror below is what exposed it.
    with tenant_ctx(env.tenant):
        served = selectors.version_row(written)
    assert served["base_charge_code"] == str(code.id)
    assert served["base_charge_code_ref"]["code"] == code.code


def test_def_rat_6932__the_endpoint_still_clears_it_when_the_body_says_null(env):
    """The mirror through the same route: an empty picker reaches the server as
    `base_charge_code: null` and must still mean *this schedule names nothing*.

    ⚠ AMENDED 2026-10-06 (`DEF-RAT-9797`) — see the case above: with one code
    that could serve the schedule, the null is answered by naming that code.
    """
    schedule, code = _bound_water_schedule(env)
    response = api_call(
        api.rate_schedule_versions,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={
            "model": "tiered",
            "uom": "kgal",
            "base_charge_code": None,
            "effective_from": "2026-10-01",
            "reason": "Let the service's declared base answer",
            "structure": {"tiers": NEXT_TIERS},
        },
        tariff_id=str(schedule["id"]),
    )
    assert response.status_code == 201, response.data
    written = _latest(env, schedule)
    assert written.base_charge_code_id == code.id  # DEF-RAT-9797
    with tenant_ctx(env.tenant):
        served = selectors.version_row(written)
    assert served["base_charge_code"] == str(code.id)

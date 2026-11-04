# ── Trace ──────────────────────────────────────────────
# Defect: DEF-RAT-8002 — `resolution_catalogue.schedule_version_facts` read
#         `TariffVersion.objects.filter(tenant_id, tariff_id)` with NO
#         `superseded_by` filter, while the live bill run's read
#         (`selectors.in_force_version`) has carried
#         `.filter(superseded_by__isnull=True)` since DEF-RAT-5715. So a
#         corrected schedule bills fine on the nightly run and REFUSES with
#         `AmbiguousSchedule` on every path built on the resolution chain —
#         the one-time bill and the move-out final bill.
# Rules:  BR-RAT-007 (a period prices on the version in force AT THE SERVICE
#         DATE) · BR-RAT-104 / BR-RAT-1016 verb 2 (a CORRECTION restates the
#         SAME window) · BR-RAT-031 (a dateless draft prices nothing)
# ───────────────────────────────────────────────────────
"""Wave C2 — **the two readers of `tariff_versions` must answer the same.**

⚠ **PROVED RED FIRST, in a clean worktree at the commit before the fix
(`31ce6115a`) — hard-won law 7.** Two of this file's four cases failed there
and two passed. The refusal case failed with the very exception the live
tenant's clerks see, verbatim:

    apps.rating.resolution.AmbiguousSchedule: R2: 2 versions of schedule
    '01a0ed33-c4dd-…' are in force for 'water' on 2026-08-15
    (01a0ed33-c4de-…, 01a0ed33-c514-…). Exactly one prices a service; there
    is no best match and this chain never picks.

and the parity case failed with the two ids side by side:

    assert ['01a0ed33-be3e-…', '01a0ed33-be71-…'] == ['01a0ed33-be71-…']
      Left contains one more item

while `selectors.in_force_version` returned exactly ONE row — the correction —
for the same schedule on the same date. Two readers, one table, one service
date, two answers; and the disagreement was invisible to every test in the
repo, because each reader had its own suite and nothing asked them the same
question.

⚠ **THIS TEST IS THE THING THAT KEEPS THEM TOGETHER, AND IT IS WHY IT ASKS
BOTH RATHER THAN ASSERTING THE FIX.** A test of the new filter alone would go
green the day somebody adds a THIRD predicate to `in_force_version` and
forgets this file. Asking both the same question fails on that day instead.
"""

from datetime import date

import pytest

from apps.rating import models, resolution, resolution_catalogue, selectors, services

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import RES_WATER_TIERS, tenant_ctx

pytestmark = pytest.mark.django_db

FIXED = [{"from_qty": "0", "to_qty": None, "unit_price": "3.20"}]


def _both_readers(env, tariff_id, service_date):
    """The same question, asked of both paths. Returns `(live, chain)` ids."""
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=tariff_id)
        live = selectors.in_force_version(tariff, service_date)
        facts = resolution_catalogue.schedule_version_facts(tariff_id)
        in_force = [f for f in facts if f.in_force_on(service_date)]
    return (str(live.id) if live else None), [f.version_id for f in in_force]


def test_def_rat_8002__both_readers_pick_one_version_after_a_correction(env):
    """⚠ THE MONEY CASE — the shape that refuses a move-out final bill.

    After a correction the schedule holds TWO rows containing the service
    date. The live run answers with the correction; the chain used to answer
    with both and then refuse.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    service_date = date(2026, 8, 15)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        original = selectors.latest_version(tariff)
        services.correct_rate_schedule_version(
            env.admin,
            water["id"],
            str(original.id),
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Tier 1 was typed as 32.00 and the board approved 3.20",
                "structure": {"tiers": FIXED},
            },
        )
        correction_id = str(models.TariffVersion.objects.get(corrects=original).id)

    live, chain = _both_readers(env, water["id"], service_date)
    assert chain == [correction_id], chain
    assert live == correction_id
    assert live == chain[0], (
        "the live bill run and the resolution chain disagree about which version "
        "prices this date — that is how a move-out final bill refuses while the "
        "ordinary run bills"
    )


def test_def_rat_8002__r2_does_not_refuse_a_corrected_schedule(env):
    """The refusal path itself, end to end through R2.

    `resolve_schedule` raises `AmbiguousSchedule` when more than one version is
    in force. That refusal is RIGHT about what it sees; before the fix it was
    seeing rows the pricing rule had already removed.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        original = selectors.latest_version(tariff)
        services.correct_rate_schedule_version(
            env.admin,
            water["id"],
            str(original.id),
            {
                "model": "tiered",
                "uom": "kgal",
                "reason": "Tier 1 was typed as 32.00 and the board approved 3.20",
                "structure": {"tiers": FIXED},
            },
        )
        facts = resolution_catalogue.schedule_version_facts(water["id"])
    plan = resolution.PlanVersion(
        plan_id="p", version=1, services=("water",),
        effective_from=date(2026, 1, 1), effective_to=None,
        schedules={"water": str(water["id"])},
    )
    catalogue = resolution.Catalogue(plan_versions=(plan,), schedule_versions=facts)
    chosen = resolution.resolve_schedule(catalogue, plan, "water", date(2026, 8, 15))
    assert chosen.version_id == facts[0].version_id
    assert len(facts) == 1, [f.version_id for f in facts]


def test_def_rat_8002__both_readers_agree_across_a_plain_rate_change(env):
    """The ordinary case, asserted so the parity claim is not only about
    corrections: three windows, three dates, both readers, same answers."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin, water["id"],
            {"model": "tiered", "uom": "kgal", "reason": "Board rate change 2026-10-01",
             "effective_from": "2026-10-01", "structure": {"tiers": FIXED}},
        )
        services.create_rate_schedule_version(
            env.admin, water["id"],
            {"model": "tiered", "uom": "kgal", "reason": "Board rate change 2027-01-01",
             "effective_from": "2027-01-01", "structure": {"tiers": FIXED}},
        )
    for service_date in (date(2026, 8, 15), date(2026, 11, 1), date(2027, 3, 1)):
        live, chain = _both_readers(env, water["id"], service_date)
        assert len(chain) == 1, (service_date, chain)
        assert live == chain[0], (service_date, live, chain)


def test_def_rat_8002__a_draft_is_invisible_to_both(env):
    """BR-RAT-031 — `DEF-RAT-5680`'s parked draft. Neither reader may see it,
    and the two exclude it in different places (the chain drops a NULL
    `effective_from` in its loop; the selector filters
    `effective_from__isnull=False`), so it is worth one assertion that they
    still agree about it."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        # `DEF-RAT-5680`'s parked draft: a PATCH with structure and NO dates.
        services.update_rate_schedule(
            env.admin, water["id"],
            {"model": "tiered", "uom": "kgal", "structure": {"tiers": FIXED}},
        )
        assert selectors.draft_version(models.Tariff.objects.get(pk=water["id"])) is not None
    live, chain = _both_readers(env, water["id"], date(2026, 8, 15))
    assert len(chain) == 1 and live == chain[0]

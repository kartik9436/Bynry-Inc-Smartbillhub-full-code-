# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-6447 — a live rate schedule offered NO way to save an
#          unfinished edit. PO, beta, verbatim: *"when user want to save draft
#          version you are refusing it - we need to solve this deadlock. - we
#          need to save edits"*.
# Rules:   BR-RAT-037 (CONFIRMED, PO R5-9) — *"In-force plan/tariff versions are
#          never edited in place: every change = new version row … + append-only
#          `rate_change_log` row"*. **IT BINDS A ROW THAT HAS BEEN IN FORCE.**
#          BR-RAT-031 (CONFIRMED-AS-MODIFIED, PO R5-1) — *"Save-draft
#          resumable; activation needs complete structure + effective_from"*.
#          A dateless row is what that rule stores and it prices nothing:
#          `selectors.in_force_version` excludes it BY NAME.
# Note:    the guard this replaces asked `latest_version(tariff) is not None` —
#          a property of the SCHEDULE, never of the row being written. That is
#          why it refused a write that touches no activated version at all.
#          US-RAT-010 TC-7 froze the over-broad reading; its substance (the
#          version in force is not edited) is asserted here and is UNCHANGED.
# ───────────────────────────────────────────────────────
"""DEF-RAT-6447 — parking a draft on a schedule that is already live.

⚠ **THE POINT OF EVERY CASE BELOW IS THE SECOND ASSERTION, NOT THE FIRST.**
That the save is accepted is one line. What makes it lawful is that the
activated version is byte-identical afterwards, is still what `in_force_version`
answers, and is still what the engine prices from. A test that only asserted
the 200 would pass over a fix that quietly rewrote the live rate.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import api, models, selectors, services
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import (
    RES_WATER_TIERS,
    FakeUser,
    api_call,
    audit_actions,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

# The clerk's half-finished edit: a third block at a price nobody has approved.
PARKED_TIERS = [
    {"from_qty": "0", "to_qty": "5", "unit_price": "9.99"},
    {"from_qty": "5", "to_qty": None, "unit_price": "11.11"},
]


def _live_version_fingerprint(tariff_id):
    """Everything about the version in force that a wrong fix could move."""
    tariff = models.Tariff.objects.get(pk=tariff_id)
    version = selectors.latest_version(tariff)
    tiers = list(
        models.RateTier.objects.filter(tariff_version=version)
        .order_by("seq")
        .values_list("from_qty", "to_qty", "unit_price", "size_class"),
    )
    return {
        "id": str(version.id),
        "effective_from": version.effective_from,
        "effective_to": version.effective_to,
        "model": version.model,
        "base_charge": version.base_charge,
        "minimum_bill": version.minimum_bill,
        "uom": version.uom,
        "tiers": tiers,
    }


def _park(env, tariff_id, tiers=PARKED_TIERS):
    return api_call(
        api.rate_schedule_item,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"model": "tiered", "uom": "kgal", "structure": {"tiers": tiers}},
        tariff_id=tariff_id,
    )


def test_def_rat_5680__a_live_schedule_accepts_a_parked_draft(env):
    """The deadlock itself. RED before the fix with
    `assert 409 == 200` — `errors.BIZ_IMMUTABLE`, BR-RAT-037.
    """
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    response = _park(env, water["id"])
    assert response.status_code == 200, response.data
    with tenant_ctx(env.tenant):
        draft = selectors.draft_version(models.Tariff.objects.get(pk=water["id"]))
    assert draft is not None, "the save reported success and stored nothing"
    assert draft.effective_from is None, "a parked draft must carry NO window"


def test_def_rat_5680__the_live_version_is_byte_identical_after_the_save(env):
    """BR-RAT-037, asserted rather than assumed. This is US-RAT-010 TC-7's
    substance and it is the reason the fix is lawful."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        before = _live_version_fingerprint(water["id"])
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        after = _live_version_fingerprint(water["id"])
    assert after == before, "parking a draft moved the version that is in force"
    # The seeded live price, named, so a diff that changed it cannot read as
    # merely a reordering.
    assert before["tiers"][0][2] == Decimal("3.200000")


def test_def_rat_5680__the_parked_draft_never_prices_anything(env):
    """`in_force_version` is what the engine consumes (BR-RAT-007). A dateless
    row has no window and must never be the answer."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        draft = selectors.draft_version(tariff)
        for service_date in (date(2026, 8, 1), date(2099, 12, 31)):
            in_force = selectors.in_force_version(tariff, service_date)
            assert in_force is None or in_force.id != draft.id, (
                f"the dateless draft answered in_force_version on {service_date}"
            )
        # ... and the history a filings table reads excludes it too.
        assert draft.id not in {version.id for version in selectors.tariff_versions(tariff)}
        assert len(selectors.tariff_versions(tariff)) == 1


def test_def_rat_5680__the_engine_still_prices_from_the_live_version(env):
    """The money half. `pricing_inputs` is what a bill run reads; parking a
    draft must not reach it."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        service_date = selectors.latest_version(tariff).effective_from
        before = selectors.pricing_inputs_for_version(
            selectors.latest_version(tariff), service_date
        )
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        in_force = selectors.in_force_version(tariff, service_date)
        after = selectors.pricing_inputs_for_version(in_force, service_date)
    assert after == before, "the priced configuration changed when a draft was parked"


def test_def_rat_5680__re_parking_replaces_the_one_draft_and_still_leaves_the_live_row(env):
    """`uq_tariff_versions_one_draft` says ONE draft, not NO draft once live."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    assert _park(env, water["id"]).status_code == 200
    assert (
        _park(
            env,
            water["id"],
            [{"from_qty": "0", "to_qty": None, "unit_price": "5.55"}],
        ).status_code
        == 200
    )
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        assert (
            models.TariffVersion.objects.filter(
                tariff=tariff, effective_from__isnull=True
            ).count()
            == 1
        )
        draft = selectors.draft_version(tariff)
        prices = list(
            models.RateTier.objects.filter(tariff_version=draft)
            .order_by("seq")
            .values_list("unit_price", flat=True),
        )
        assert prices == [Decimal("5.550000")]
        assert _live_version_fingerprint(water["id"])["tiers"][0][2] == Decimal("3.200000")


def test_def_rat_5680__the_parked_draft_is_served_to_the_screen(env):
    """DEF-RAT-6448's server half: the detail a reopened wizard reads must
    carry the parked draft AND the live version, told apart."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        detail = selectors.schedule_detail(water["id"])
    assert detail["draft_version"] is not None, "the draft was stored and is not served"
    assert detail["current_version"] is not None, "the live version stopped being served"
    assert detail["draft_version"]["effective_from"] is None
    assert detail["draft_version"]["id"] != detail["current_version"]["id"]
    # The status pill is derived from what is IN FORCE, so a parked draft
    # cannot make a live schedule read as a draft (BR-RAT-031).
    assert detail["status"] == "active"


def test_def_rat_5680__a_dated_content_patch_is_still_refused_and_audited(env, audit_rows):
    """US-RAT-010 TC-7's OTHER half, kept: a DATE is the only content write
    that can reach an activated version, and it is still 409 + audited."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    audit_rows.clear()
    response = api_call(
        api.rate_schedule_item,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"structure": {"tiers": PARKED_TIERS}, "effective_from": "2026-12-01"},
        tariff_id=water["id"],
    )
    assert response.status_code == 409
    assert response.data["code"] == errors.BIZ_IMMUTABLE
    assert "security.attempt_refused" in audit_actions(audit_rows)
    with tenant_ctx(env.tenant):
        assert selectors.draft_version(models.Tariff.objects.get(pk=water["id"])) is None


def test_def_rat_5680__a_never_activated_schedule_still_refuses_a_date(env):
    """BR-RAT-031: the dates land at activation, where the completeness check
    is. Unchanged, and the message is still the one that says so."""
    with tenant_ctx(env.tenant):
        water = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Draft",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "structure": {"tiers": RES_WATER_TIERS},
            },
        )
    response = api_call(
        api.rate_schedule_item,
        "patch",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={"structure": {"tiers": PARKED_TIERS}, "effective_from": "2026-12-01"},
        tariff_id=water["id"],
    )
    assert response.status_code == 422
    assert response.data["message_key"] == "rating.schedules.dates_land_at_activation"


def test_def_rat_5680__discarding_a_parked_draft_leaves_the_live_version(env):
    """1.6 — the one-draft constraint would otherwise trap stale work."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        before = _live_version_fingerprint(water["id"])
    response = api_call(
        api.rate_schedule_discard_draft,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={},
        tariff_id=water["id"],
    )
    assert response.status_code == 200, response.data
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        assert selectors.draft_version(tariff) is None
        assert _live_version_fingerprint(water["id"]) == before


def test_def_rat_5680__discarding_when_there_is_no_draft_is_refused_by_name(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    response = api_call(
        api.rate_schedule_discard_draft,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={},
        tariff_id=water["id"],
    )
    assert response.status_code == 404


def test_def_rat_5680__activating_the_parked_draft_is_still_a_new_version_with_a_reason(env):
    """The draft is the new version BEFORE it goes live (BR-RAT-037 kept
    whole): activating it writes a NEW row, a reason and a change-log entry —
    exactly as a filing does today."""
    water = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    assert _park(env, water["id"]).status_code == 200
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            water["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-09-01",
                "reason": "Board approved 2026 schedule",
                "structure": {"tiers": PARKED_TIERS},
            },
        )
        tariff = models.Tariff.objects.get(pk=water["id"])
        versions = selectors.tariff_versions(tariff)
        log = models.RateChangeLog.objects.get(entity_id=water["id"])
    assert len(versions) == 2
    assert versions[-1].change_reason == "Board approved 2026 schedule"
    assert log.reason == "Board approved 2026 schedule"
    # The old window closed exactly as it does today — nothing about parking a
    # draft changed the filing path.
    assert versions[0].effective_to is not None

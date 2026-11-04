# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-RAT-5715 — BR-RAT-104's SHARED rule was built for taxes only, so
#          a typo in a live rate schedule had no correction path at all. PO,
#          beta, verbatim: *"if user make an error while creating the rate
#          schedule and they want to rectify that error using edit - how are
#          they going to do it; it is not a new rate or it is not a change in
#          rate - it is just an error handling"*.
# Rules:   BR-RAT-104 (CONFIRMED) — *"a historic typo is fixed by a documented
#          correction version with a reason"*, and **the difference between a
#          correction and a change is the WINDOW** · BR-RAT-037 (a CHANGE is a
#          new row with a NEW window — untouched) · BR-RAT-007 / BR-RAT-017 (a
#          June bill re-prices on June's terms, for seven years) · hard rule 4
#          (a bill locks at issue and a correction cannot reach it)
# Note:    modelled on `correct_tax` and its suite deliberately, because one
#          signed rule answered two ways is worse than either answer.
# ───────────────────────────────────────────────────────
"""DEF-RAT-5715 — correcting a rate-schedule version that is already live.

⚠ **THE TEST THAT MATTERS IS `the_corrected_row_stops_pricing_and_keeps_
everything_else`.** Every other case here describes the shape of the feature.
That one is the money: two rows now claim the same window, and if the wrong one
prices, every bill on that service is wrong in a way no screen would show.
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

# The typo: 32.00 per kgal where 3.20 was meant — a factor of ten, which is the
# shape of mistake this whole path exists for.
TYPO_TIERS = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "32.00"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "4.80"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.20"},
]
FIXED_TIERS = [
    {"from_qty": "0", "to_qty": "4", "unit_price": "3.20"},
    {"from_qty": "4", "to_qty": "10", "unit_price": "4.80"},
    {"from_qty": "10", "to_qty": None, "unit_price": "7.20"},
]
REASON = "Tier 1 was typed as 32.00 and the board approved 3.20"


def _correct(env, tariff_id, version_id, tiers=FIXED_TIERS, reason=REASON, **extra):
    return api_call(
        api.rate_schedule_version_corrections,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={
            "model": "tiered",
            "uom": "kgal",
            "reason": reason,
            "structure": {"tiers": tiers},
            **extra,
        },
        tariff_id=tariff_id,
        version_id=version_id,
    )


def _live(env, tariff_id):
    with tenant_ctx(env.tenant):
        return selectors.latest_version(models.Tariff.objects.get(pk=tariff_id))


def test_def_rat_5715__a_live_version_is_corrected_over_the_same_window(env):
    """RED before the fix: `AttributeError: module 'apps.rating.api' has no
    attribute 'rate_schedule_version_correct'`."""
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    response = _correct(env, water["id"], str(original.id))
    assert response.status_code == 200, response.data
    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        original.refresh_from_db()
        correction = models.TariffVersion.objects.get(corrects=original)
    # THE defining property of a correction: the window is the corrected row's.
    assert correction.effective_from == original.effective_from
    # ⚠ **THIS LINE READ `correction.effective_to == original.effective_to`
    # UNTIL `BR-RAT-1044` (PO ruling 2026-09-29).** It was a true statement of
    # the rule as it stood — a correction copied BOTH ends — and it is now
    # true of the START only. The corrected row's OPEN end is stamped with
    # `max(the correction date, its effective_from)` so the register shows
    # when the wrong version stopped being used, while the correction inherits
    # the open end and goes on pricing. Written out rather than deleted,
    # because the pair of dates is what makes this a correction and the next
    # reader is entitled to see which half moved.
    #
    # ⚠ **A STATED end is NOT moved**, which is why this is still an equality
    # on a schedule whose window was open: `original.effective_to` is the
    # stamp, `correction.effective_to` is `None`, and the case that covers a
    # CLOSED original is
    # `test_br_rat_1044__a_stated_end_is_never_moved`.
    assert correction.effective_to is None
    assert original.effective_to is not None
    assert original.effective_to >= original.effective_from
    assert original.superseded_by_id == correction.id
    assert correction.correction_reason == REASON
    assert correction.corrected_by_id == env.owner.id


def test_def_rat_5715__the_corrected_row_stops_pricing_and_keeps_everything_else(env):
    """⚠ THE MONEY CASE. Two rows now contain the same service date, and the
    one that prices must be the correction. Without the `superseded_by__isnull`
    filter in `in_force_version` the order-by decides, on a column that is
    IDENTICAL on both rows — a coin toss on a money path."""
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    service_date = original.effective_from
    with tenant_ctx(env.tenant):
        priced_before = selectors.in_force_version(
            models.Tariff.objects.get(pk=water["id"]), service_date
        )
        assert priced_before.id == original.id
        before_price = (
            models.RateTier.objects.filter(tariff_version=original)
            .order_by("seq")
            .first()
            .unit_price
        )
    assert before_price == Decimal("32.000000")

    assert _correct(env, water["id"], str(original.id)).status_code == 200

    with tenant_ctx(env.tenant):
        tariff = models.Tariff.objects.get(pk=water["id"])
        priced_after = selectors.in_force_version(tariff, service_date)
        original.refresh_from_db()
        # The correction prices …
        assert priced_after.id != original.id
        assert priced_after.corrects_id == original.id
        assert models.RateTier.objects.filter(tariff_version=priced_after).order_by(
            "seq"
        ).first().unit_price == Decimal("3.200000")
        # … and the corrected row is UNCHANGED in every field of its own.
        assert original.effective_from == service_date
        assert models.RateTier.objects.filter(tariff_version=original).order_by(
            "seq"
        ).first().unit_price == Decimal("32.000000")
        # … and it is still HISTORY: a regulator asking what this schedule has
        # ever said still sees it (BR-RAT-104, BR-RAT-017).
        history = [v.id for v in selectors.tariff_versions(tariff)]
        assert original.id in history and priced_after.id in history


def test_def_rat_5715__a_correction_never_reads_a_date_from_the_payload(env):
    """The one property that separates a correction from a change. A caller who
    sent a date believed it would be used, so it is refused BY NAME rather than
    overridden in silence."""
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    response = _correct(env, water["id"], str(original.id), effective_from="2027-01-01")
    assert response.status_code == 422
    assert any(
        err["message_key"] == "rating.schedules.correction_keeps_the_window"
        for err in response.data["field_errors"]
    ), response.data
    with tenant_ctx(env.tenant):
        original.refresh_from_db()
        assert original.superseded_by_id is None, "a refused correction still superseded the row"


def test_def_rat_5715__a_correction_needs_a_reason(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    response = _correct(env, water["id"], str(original.id), reason="oops")
    assert response.status_code == 422
    assert any(
        err["message_key"] == "rating.schedules.correction_reason"
        for err in response.data["field_errors"]
    ), response.data


def test_def_rat_5715__a_draft_is_edited_in_place_and_never_corrected(env):
    """2.3 — a draft has never priced anything, so there is nothing to preserve
    and nothing to explain. It routes to the wave-1 draft save instead."""
    with tenant_ctx(env.tenant):
        water = services.create_rate_schedule(
            env.admin,
            {
                "name": "Res Water · Draft",
                "service": "water",
                "model": "tiered",
                "uom": "kgal",
                "structure": {"tiers": TYPO_TIERS},
            },
        )
        draft = selectors.draft_version(models.Tariff.objects.get(pk=water["id"]))
    response = _correct(env, water["id"], str(draft.id))
    assert response.status_code == 409
    assert response.data["message_key"] == "rating.schedules.correct_draft"


def test_def_rat_5715__correcting_a_correction_is_refused(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    assert _correct(env, water["id"], str(original.id)).status_code == 200
    response = _correct(env, water["id"], str(original.id), reason="and again, wrongly")
    assert response.status_code == 409
    assert response.data["message_key"] == "rating.schedules.already_corrected"


def test_def_rat_5715__the_answer_names_the_bills_it_cannot_reach(env):
    """Hard rule 4: a bill locks at issue. An operator who has just fixed a
    price will believe the money is fixed, so the answer says it is not."""
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    response = _correct(env, water["id"], str(original.id))
    assert response.data["issued_bills_unchanged"] is True
    # 0 here (no bills in this fixture) — what matters is that the key is
    # SERVED, and that `None` is possible and means "billing could not answer".
    assert "issued_bills" in response.data


def test_def_rat_5715__a_version_of_another_schedule_is_a_404(env):
    """Hard rule 1's shape at the route: the version is looked up BY TARIFF, so
    naming another schedule's version cannot reach it."""
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    other = env.tiered_schedule("Res Water · Second", "water", FIXED_TIERS)
    other_version = _live(env, other["id"])
    response = _correct(env, water["id"], str(other_version.id))
    assert response.status_code == 404


def test_def_rat_5715__the_correction_is_audited_on_both_rows(env, audit_rows):
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    audit_rows.clear()
    assert _correct(env, water["id"], str(original.id)).status_code == 200
    actions = audit_actions(audit_rows)
    assert "tariff.version_corrected" in actions
    assert "tariff.correction_created" in actions
    with tenant_ctx(env.tenant):
        log = models.RateChangeLog.objects.filter(entity_id=water["id"]).order_by("-id").first()
    assert log.reason == REASON


def test_def_rat_5715__a_change_is_still_a_change(env):
    """BR-RAT-037 is untouched: filing a NEW price still closes the old window
    and opens a new one, and nothing about it is a correction."""
    water = env.tiered_schedule("Res Water · Inclining", "water", FIXED_TIERS)
    with tenant_ctx(env.tenant):
        services.create_rate_schedule_version(
            env.admin,
            water["id"],
            {
                "model": "tiered",
                "uom": "kgal",
                "effective_from": "2026-09-01",
                "reason": "Board approved 2026 schedule",
                "structure": {"tiers": TYPO_TIERS},
            },
        )
        tariff = models.Tariff.objects.get(pk=water["id"])
        versions = selectors.tariff_versions(tariff)
    assert len(versions) == 2
    assert versions[0].effective_to == date(2026, 8, 31)   # closed, not superseded
    assert versions[0].superseded_by_id is None
    assert versions[1].corrects_id is None


def test_def_rat_5715__the_chain_is_served_to_the_screen(env):
    water = env.tiered_schedule("Res Water · Inclining", "water", TYPO_TIERS)
    original = _live(env, water["id"])
    assert _correct(env, water["id"], str(original.id)).status_code == 200
    with tenant_ctx(env.tenant):
        detail = selectors.schedule_detail(water["id"])
    rows = {row["id"]: row for row in detail["versions"]}
    corrected = rows[str(original.id)]
    correction = next(row for row in detail["versions"] if row["corrects"] == str(original.id))
    assert corrected["superseded_by"] == correction["id"]
    assert correction["correction_reason"] == REASON
    assert correction["corrected_by"] is not None
    # The two share a window, which is what a screen must be able to SAY.
    assert corrected["effective_from"] == correction["effective_from"]

# ── Trace ──────────────────────────────────────────────
# Question: OQ-RAT-12409 — CLOSED by PO ruling 2026-09-18, verbatim: *"The plan
#           correction — A, B or C - option A pls"*.
# Defect:   DEF-RAT-5710 — a typo in a published plan mints a new version, so
#           the record says the price changed when it did not.
# Rules:    BR-RAT-1016 (the three verbs are the same for every priced object) ·
#           BR-RAT-104 (a correction restates; it never re-files) ·
#           BR-RAT-037 (a CHANGE bumps the counter — untouched) ·
#           BR-RAT-111 (`plan_versions`, append-only) ·
#           BR-CUS-013 (`unit_plan_assignments.plan_version` snapshots the
#           counter at assignment and outlives the plan) ·
#           CLAUDE.md hard rule 4
# Note:     modelled on `tests/test_def_rat_5715_correct_a_version.py`
#           deliberately — one signed rule answered two ways is worse than
#           either answer.
# ───────────────────────────────────────────────────────
"""OQ-RAT-12409 option A — correcting a plan version that is already filed.

⚠ **THE TWO TESTS THAT MATTER ARE `the_counter_never_moves` AND
`the_version_number_is_never_read_from_the_payload`.** Every other case here
describes the shape of the feature. Those two are the RULING: a bound object
being re-pointed by mistake must not mint a version number that 75 unit rows
will point at for ever (`BR-CUS-013`), and the property that makes this a
correction rather than a version bump is that `version_no` comes from the row
being corrected and from nowhere else.
"""

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

REASON = "The water service was pointed at the commercial schedule by mistake"


def _published_plan(env):
    """A published plan bound to a water schedule — the seeded estate's shape.

    `SCW-RES` binds `Sample — Residential water (inclining tiers)` and is on v1
    with 75 units recorded against `plan_version = 1`. This is that, in the two
    rows a test needs.
    """
    right = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    wrong = env.tiered_schedule("Com Water · Flat", "water", RES_WATER_TIERS)
    plan = env.plan(
        "Sample — Residential",
        "SCW-RES",
        [{"service": "water", "base_charge": "8.00", "tariff": right["id"]}],
        publish=True,
    )
    return plan, right, wrong


def _correct(env, plan_id, tariff_id, reason=REASON, **extra):
    return api_call(
        api.plan_corrections,
        "post",
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
        data={
            "services": [
                {"service": "water", "base_charge": "8.00", "tariff": str(tariff_id)}
            ],
            "reason": reason,
            **extra,
        },
        plan_id=plan_id,
    )


def _versions(env, plan_id):
    with tenant_ctx(env.tenant):
        return list(
            models.PlanVersion.objects.filter(rate_plan_id=plan_id).order_by("created_at")
        )


# ── THE RULING ──────────────────────────────────────────────────────────────


def test_oq_rat_12409__the_counter_never_moves(env):
    """⚠ **THE RULING.** A correction is a NEW ROW at the SAME `version_no`, and
    `rate_plans.version` does not move — which is what stops a mis-click from
    minting a number `unit_plan_assignments.plan_version` will point at for ever
    (`BR-CUS-013`).

    RED before the fix: `AttributeError: module 'apps.rating.api' has no
    attribute 'plan_corrections'`.
    """
    plan, _right, wrong = _published_plan(env)
    response = _correct(env, plan["id"], wrong["id"])
    assert response.status_code == 200, response.data

    with tenant_ctx(env.tenant):
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.version == 1, "a correction is not a new version of the plan"

    versions = _versions(env, plan["id"])
    assert len(versions) == 2, "the correction is a row, not an edit"
    original, correction = versions
    assert correction.version_no == original.version_no == 1
    assert correction.corrects_id == original.id
    assert correction.correction_reason == REASON
    assert correction.corrected_by_id == env.owner.id


def test_oq_rat_12409__the_version_number_is_never_read_from_the_payload(env):
    """⚠ **THE DEFINING PROPERTY.** For a tax and a schedule version it is the
    WINDOW that is copied from the corrected row; a plan version has no window
    (`OQ-324` — CLOSED 2026-10-03 (B): it has one now, and a correction copies it too), so here it is the COUNTER. A payload that states one is refused
    BY NAME rather than ignored — a caller that sent it believed it would be
    used (`correct_rate_schedule_version`'s recorded posture)."""
    plan, _right, wrong = _published_plan(env)
    response = _correct(env, plan["id"], wrong["id"], version=9)
    # 422 is this product's validation status (BE-02), not 400.
    assert response.status_code == 422, response.data
    assert any(
        one["message_key"] == "rating.plans.correction_keeps_the_version"
        for one in response.data["field_errors"]
    ), response.data
    assert _versions(env, plan["id"]) and len(_versions(env, plan["id"])) == 1


def test_oq_rat_12409__the_corrected_row_keeps_its_snapshot_for_ever(env):
    """`BR-RAT-111` append-only, and hard rule 4's spirit. The corrected row is
    never rewritten and never deleted: `superseded_by` is the ONLY column that
    moves on it, so what was filed stays readable beside what replaced it."""
    plan, right, wrong = _published_plan(env)
    original_before = _versions(env, plan["id"])[0]
    kept = {
        "snapshot": original_before.snapshot,
        "change_reason": original_before.change_reason,
        "submitted_by_id": original_before.submitted_by_id,
        "created_at": original_before.created_at,
        "version_no": original_before.version_no,
    }
    _correct(env, plan["id"], wrong["id"])
    original_after, correction = _versions(env, plan["id"])
    for field, value in kept.items():
        assert getattr(original_after, field) == value, f"{field} moved on the corrected row"
    assert original_after.superseded_by_id == correction.id
    # The correction carries the NEW content and the corrected row the OLD one:
    # the two snapshots differ, which is what makes the pair readable at all.
    assert original_after.snapshot != correction.snapshot
    assert str(right["id"]) != str(wrong["id"])


def test_oq_rat_12409__a_second_correction_of_the_same_row_is_refused_by_name(env):
    """Correcting a correction would leave two rows claiming to restate one
    version with nothing saying which is current — `correct_tax`'s own refusal,
    in the same place and the same shape."""
    plan, right, wrong = _published_plan(env)
    assert _correct(env, plan["id"], wrong["id"]).status_code == 200
    second = _correct(env, plan["id"], right["id"])
    assert second.status_code == 409, second.data
    assert second.data["message_key"] == "rating.plans.already_corrected"


def test_oq_rat_12409__a_draft_is_edited_not_corrected(env):
    """A draft has priced nothing, so there is nothing to preserve and nothing
    to explain. The refusal NAMES the road (`PATCH /plans/{id}`) rather than
    ending it — `DEF-384`'s shape."""
    right = env.tiered_schedule("Res Water · Inclining", "water", RES_WATER_TIERS)
    draft = env.plan(
        "Draft plan",
        "DRAFT-1",
        [{"service": "water", "base_charge": "8.00", "tariff": right["id"]}],
    )
    response = _correct(env, draft["id"], right["id"])
    assert response.status_code == 409, response.data
    assert response.data["message_key"] == "rating.plans.correct_draft"


def test_oq_rat_12409__a_reason_is_required_and_is_not_the_change_reason(env):
    """`correction_reason` answers *what was recorded wrongly*; `change_reason`
    answers *why the plan changed*. The corrected row's filing note TRAVELS to
    the correction, because the filing did not change — only what it says did.
    Showing one where the other belongs would file a typo as a plan change."""
    plan, _right, wrong = _published_plan(env)
    short = _correct(env, plan["id"], wrong["id"], reason="oops")
    assert short.status_code == 422, short.data
    assert any(
        one["message_key"] == "rating.plans.correction_reason"
        for one in short.data["field_errors"]
    ), short.data

    assert _correct(env, plan["id"], wrong["id"]).status_code == 200
    original, correction = _versions(env, plan["id"])
    assert correction.correction_reason == REASON
    assert correction.change_reason == original.change_reason


def test_oq_rat_12409__a_correction_that_changes_nothing_is_refused(env):
    """It would supersede a live filing for no content — a break in the chain
    with nothing in it."""
    plan, right, _wrong = _published_plan(env)
    response = _correct(env, plan["id"], right["id"])
    assert response.status_code == 422, response.data
    assert response.data["message_key"] == "rating.plans.correction_empty"
    assert len(_versions(env, plan["id"])) == 1


def test_oq_rat_12409__the_compliance_trail_and_the_audit_row_are_written(env, audit_rows):
    """`entity_type="plan"` with BOTH before and after, permanently, beside the
    audit row — the table `OQ-RAT-12409`'s own analysis names as where the wrong
    binding survives in full. The audit action is its OWN name, so a reader can
    tell a correction from a version bump without diffing two blobs."""
    plan, _right, wrong = _published_plan(env)
    audit_rows.clear()
    _correct(env, plan["id"], wrong["id"])
    with tenant_ctx(env.tenant):
        rows = list(
            models.RateChangeLog.objects.filter(entity_type="plan", entity_id=plan["id"])
        )
    assert len(rows) == 1, rows
    assert rows[0].reason == REASON
    assert rows[0].before != rows[0].after
    assert "plan.version_corrected" in audit_actions(audit_rows)


def test_oq_rat_12409__a_change_still_bumps_the_counter(env):
    """`BR-RAT-037` is UNTOUCHED, and this is the test that says so. Verb 3 is
    still verb 3: a real change to a published plan mints a version, writes a
    `rate_change_log` row and files a `PlanVersion`. The correction path exists
    beside it, not instead of it."""
    plan, _right, wrong = _published_plan(env)
    with tenant_ctx(env.tenant):
        services.update_plan(
            env.admin,
            plan["id"],
            {
                "services": [
                    {"service": "water", "base_charge": "8.00", "tariff": str(wrong["id"])}
                ],
                "reason": "the board approved the commercial schedule for this plan",
            },
        )
        row = models.RatePlan.objects.get(pk=plan["id"])
    assert row.version == 2
    versions = _versions(env, plan["id"])
    assert [one.version_no for one in versions] == [1, 2]
    assert all(one.corrects_id is None for one in versions)


# ── THE MIGRATION ───────────────────────────────────────────────────────────


def test_oq_rat_12409__the_partial_key_covers_every_existing_row(env):
    """🔒 **THE MIGRATION ARITHMETIC, ASSERTED RATHER THAN DESCRIBED.**

    `uq_plan_versions_plan_version_no` went from UNIQUE `(rate_plan, version_no)`
    to the same key `WHERE corrects IS NULL`. A partial unique is strictly weaker
    than the total one it replaces, so no existing row can fail it — and the
    claim is worth an assertion rather than a paragraph, because it is the whole
    reason `rating/0036` moves no data.

    Every row written by any path other than `correct_plan_version` reads
    `corrects IS NULL`, so the constraint still refuses a second ORIGINAL filing
    for one version number, which is what `plan_versions` was built for.
    """
    plan, _right, wrong = _published_plan(env)
    with tenant_ctx(env.tenant):
        rows = list(models.PlanVersion.objects.all())
        assert rows, "the fixture must file at least one version"
        assert all(one.corrects_id is None for one in rows)
        pairs = {(one.rate_plan_id, one.version_no) for one in rows}
        assert len(pairs) == len(rows), "non-corrections are still unique per (plan, version)"

    _correct(env, plan["id"], wrong["id"])

    with tenant_ctx(env.tenant):
        after = list(models.PlanVersion.objects.filter(rate_plan_id=plan["id"]))
        originals = [one for one in after if one.corrects_id is None]
        corrections = [one for one in after if one.corrects_id is not None]
        assert len(originals) == 1 and len(corrections) == 1
        # The pair a TOTAL unique would have refused, and the partial one allows.
        assert originals[0].version_no == corrections[0].version_no


def test_oq_rat_12409__a_second_original_filing_for_one_version_is_still_refused(env):
    """The half the partial key KEEPS. Two rows both claiming to be version 1's
    original filing would make the history unreadable in exactly the way the
    integer counter alone already was (`BR-RAT-111`)."""
    from django.db import IntegrityError, transaction

    plan, _right, _wrong = _published_plan(env)
    original = _versions(env, plan["id"])[0]
    with tenant_ctx(env.tenant):
        with pytest.raises(IntegrityError):
            # SAVEPOINT — hard-won law 14: a failed statement poisons the whole
            # PostgreSQL transaction, and this suite runs on sqlite where it
            # does not, so the nested atomic is the only thing that makes this
            # case survivable on a real database.
            with transaction.atomic():
                models.PlanVersion.objects.create(
                    tenant=env.tenant,
                    rate_plan_id=plan["id"],
                    version_no=original.version_no,
                    snapshot={"a": 1},
                )


# ── HARD RULE 4, SAID WHERE A USER MIGHT ASSUME OTHERWISE ───────────────────


def test_oq_rat_12409__the_answer_says_issued_bills_are_unchanged(env):
    """An operator who has just fixed a plan will reasonably believe the money
    is fixed. It is not: a bill locks at issue (hard rule 4) and is reproduced
    from what it stored (`BR-RAT-007`, `BR-RAT-017`). The ANSWER carries that,
    not only a docstring — `correct_tax`'s own precedent."""
    plan, _right, wrong = _published_plan(env)
    response = _correct(env, plan["id"], wrong["id"])
    assert response.data["issued_bills_unchanged"] is True
    # ⚠ **AND NO COUNT, ASSERTED RATHER THAN LEFT TO DRIFT.** `correct_tax` and
    # `correct_rate_schedule_version` both serve one; this deliberately does
    # not, because the only plan→bill link counts LINES and over-counts a shared
    # tariff (`billing.selectors.plan_invoice_count`, `OQ-185`) — 640 against
    # 135 real invoices on the seeded estate. A wrong figure beside the word
    # *bills* is worse than none, so the absence is the design and a later lane
    # adding an approximate count should have to delete this line to do it.
    assert "issued_bills" not in response.data


def test_oq_rat_12409__another_tenants_plan_is_absent_not_forbidden(env, other_env):
    """Hard rule 1 / HR-1: a cross-tenant id is ABSENT, so the body equals a
    plain not-found and nothing leaks the fact that the row exists."""
    plan, _right, wrong = _published_plan(env)
    response = api_call(
        api.plan_corrections,
        "post",
        user=FakeUser(other_env.owner.id),
        role="system_admin",
        tenant=other_env.tenant,
        data={"reason": REASON, "name": "Renamed"},
        plan_id=plan["id"],
    )
    assert response.status_code == 404, response.data

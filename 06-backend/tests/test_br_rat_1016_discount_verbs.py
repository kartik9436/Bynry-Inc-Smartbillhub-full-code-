# ── Trace ──────────────────────────────────────────────
# Change:   the uniform correction verbs. PO ruling 2026-09-17, verbatim, shown
#           a table of what each of the five priced objects does today:
#           *"please fix all these"*.
# Defects:  DEF-RAT-5709 — a discount cannot be edited at all, not even a draft
#           nobody has submitted.
# Rules:    BR-RAT-1016 (the three verbs — GENERALISING BR-RAT-104 from CR-013
#           part 4's *shared rules*) · BR-RAT-104 (the shape) · BR-RAT-077 (the
#           second approval, computed at SUBMIT) · BR-RAT-109 (warn, allow,
#           RECORD) · BR-RAT-078 (enrolments survive versioning) · CLAUDE.md
#           hard rule 4 · hard rule 7
# Tests:    this file
# Impacts:  apps/rating/discount_services.{update_discount,
#           update_discount_version,correct_discount_version,
#           _version_payload_of} · apps/rating/discounts.DiscountVersion
#           (corrects · superseded_by · correction_reason · corrected_by) ·
#           rating/0034 · PATCH /discounts/{id} · PATCH
#           /discounts/{id}/versions/{vid} · POST
#           /discounts/{id}/versions/{vid}/corrections
# ───────────────────────────────────────────────────────
"""THE DISCOUNT GETS THE TWO VERBS IT HAD NEITHER OF.

── WHAT WAS THERE BEFORE THIS FILE ──────────────────────────────────────────

`discount_services` held `create_discount`, `create_discount_version`,
`submit_discount_version`, `approve_discount_version`,
`activate_discount_version`, `retire_discount` and
`suspend_discount_for_funding` — and **no update function of any kind**. So a
clerk who typed `15` where they meant `1.5` on a version that had never been
submitted, never been approved and had priced nothing had exactly one route
out: draft a SECOND version carrying a `change_reason` and walk it through
submit, approve and activate. Three acts, and above the tenant's threshold a
second person's signature, to fix a typo in something no customer had ever
seen.

Meanwhile the module's own docstring already named the function that did not
exist — `DISCOUNT_FIELDS`' comment reads *"Every field `create_discount` /
`update_discount_version` accept"*. Hard-won law 1: a comment claiming a
guarantee is not the guarantee.

── PROVED RED FIRST (hard-won law 7), through `pytest`, the harness that runs
── them. What the first run printed against the module as it stood ──────────

* every test in the first two groups —

      AttributeError: module 'apps.rating.discount_services' has no attribute
      'update_discount_version'

  and, for the third group,

      AttributeError: module 'apps.rating.discount_services' has no attribute
      'correct_discount_version'

  which is `DEF-RAT-5709` in one line: the verb did not exist to be refused.

* `test_a_correction_keeps_the_window_it_corrects` — with the correction built
  the obvious way, taking `effective_from` from the payload as every other
  write in this module does:

      AssertionError: assert datetime.date(2027, 1, 1) == datetime.date(2026, 8, 1)

  **That one assertion is the whole rule.** A correction that moved the window
  would be a backdated change wearing a correction's clothes, and it would
  silently rewrite which bills the old figure was ever right for.

* `test_the_correction_does_not_forge_an_approval` — with the corrected row's
  `submitted_by` / `approved_by` copied onto the correction, which is the
  tempting way to keep the chain looking complete:

      AssertionError: assert UUID('01a0…') is None
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.rating import discount_services
from apps.rating import discounts as discount_models
from core import errors

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import audit_actions, tenant_ctx

pytestmark = pytest.mark.django_db


def _a_discount(env, code="SENIOR", value="1.5", **overrides):
    """A discount and its v1 DRAFT — what `create_discount` lands."""
    payload = {
        "code": code,
        "name": f"{code} programme",
        "discount_type": "percentage",
        "value": value,
        "applies_to": "whole_bill",
        "effective_from": date(2026, 8, 1),
        "budget_cap": "500",
    }
    payload.update(overrides)
    with tenant_ctx(env.tenant):
        row = discount_services.create_discount(env.admin, payload)
        version = discount_models.DiscountVersion.objects.get(
            tenant=env.tenant, discount_id=row["id"]
        )
    return row, version


def _live(env, version):
    """Put a version in force the ONLY way the product does — submit, approve
    (since PO ruling 2026-10-03 (1), approval is the last act; there is no
    Activate). Nothing here shortcuts `BR-RAT-077`'s workflow."""
    with tenant_ctx(env.tenant):
        discount_services.submit_discount_version(env.admin, version.id)
        discount_services.approve_discount_version(env.admin, version.id)
        version.refresh_from_db()
    return version


# ══════════════════════════════════════════════════════════════════════════
# VERB 1 · a draft edits in place
# ══════════════════════════════════════════════════════════════════════════


def test_a_never_submitted_draft_edits_in_place(env):
    """`correct_tax`'s own words, applied to a second object: *a draft is not
    history. It has never priced anything, so there is nothing to preserve and
    nothing to explain.*

    **Worked:** `15` typed where the programme is `1.5` reduces a `$196.37`
    bill by `$29.46` instead of `$2.95`. On a DRAFT nobody has submitted, that
    is a typo in a form — and until today it took three acts and a second
    signature to fix.
    """
    _row, version = _a_discount(env, value="15")
    with tenant_ctx(env.tenant):
        out = discount_services.update_discount_version(
            env.admin, version.id, {"value": "1.5"}
        )
        version.refresh_from_db()
    # The SERVED string is what a screen renders and what the next GET returns:
    # `NUMERIC(18,6)`, so `1.500000` and never `1.5` (hard rule 2's display half
    # is the screen's, not this layer's).
    assert out["value"] == "1.500000"
    assert version.value == Decimal("1.5")
    # No new version, no reason, no approval — one row, edited.
    assert discount_models.DiscountVersion.objects.filter(discount_id=version.discount_id).count() == 1
    assert version.status == discount_models.VERSION_DRAFT


def test_editing_a_draft_writes_one_audit_row(env, audit_rows):
    """Hard rule 7 — a draft's VALUE is still a money field, and the one audit
    row is what makes a draft edited five times readable."""
    _row, version = _a_discount(env, value="15")
    with tenant_ctx(env.tenant):
        discount_services.update_discount_version(env.admin, version.id, {"value": "1.5"})
    assert "discount.version_updated" in audit_actions(audit_rows)


def test_an_edit_that_changes_nothing_writes_no_audit_row(env, audit_rows):
    _row, version = _a_discount(env, value="1.5")
    with tenant_ctx(env.tenant):
        discount_services.update_discount_version(env.admin, version.id, {"value": "1.5"})
    assert "discount.version_updated" not in audit_actions(audit_rows)


def test_a_live_version_refuses_the_in_place_edit_and_names_the_way_out(env):
    """The refusal NAMES the correction route. A refusal that does not say what
    to do instead is the road ending — the shape `DEF-384` was filed for."""
    _row, version = _a_discount(env)
    _live(env, version)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.update_discount_version(env.admin, version.id, {"value": "2"})
    assert excinfo.value.message_key == "rating.discounts.edit_not_a_draft"
    assert excinfo.value.params["correction_path"].endswith("/corrections")


def test_a_submitted_version_refuses_the_in_place_edit(env):
    """⚠ **THE CHECK THAT IS REDUNDANT TODAY AND IS THE POINT.** Nothing returns
    a version to DRAFT, so a draft always has a null `submitted_at`. The rule is
    *never been submitted*, and asserting `submitted_at` as well as the status
    is the test that fires the day somebody adds *send back for changes* — a
    status check alone would silently re-open in-place editing on content an
    approver had already read, and `BR-RAT-077`'s stored requirement would then
    describe content that has since moved.
    """
    _row, version = _a_discount(env)
    with tenant_ctx(env.tenant):
        discount_services.submit_discount_version(env.admin, version.id)
        # Put it back to DRAFT the way a future *send back* would, WITHOUT
        # clearing `submitted_at` — which is exactly the state this guards.
        discount_models.DiscountVersion.objects.filter(pk=version.pk).update(
            status=discount_models.VERSION_DRAFT
        )
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.update_discount_version(env.admin, version.id, {"value": "2"})
    assert excinfo.value.message_key == "rating.discounts.edit_already_submitted"


# ══════════════════════════════════════════════════════════════════════════
# VERB 1 · the identity
# ══════════════════════════════════════════════════════════════════════════


def test_the_programme_name_can_be_fixed_at_any_time(env):
    """The likeliest typo of all, and it had no route at all. The IDENTITY is
    not the priced agreement — the boundary the tax lane drew at
    `TAX_RATE_HISTORY_FIELDS` and recorded in the decision log."""
    row, version = _a_discount(env)
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.update_discount(
            env.admin, row["id"], {"name": "Senior citizen programme"}
        )
    assert out["name"] == "Senior citizen programme"


def test_the_identity_refuses_a_duplicate_code(env):
    row, _version = _a_discount(env, code="SENIOR")
    other, _v2 = _a_discount(env, code="CAP")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            discount_services.update_discount(env.admin, other["id"], {"code": "senior"})
    assert excinfo.value.field_errors[0]["message_key"] == "rating.discounts.duplicate_code"
    assert row["code"] == "SENIOR"


def test_the_identity_refuses_a_field_that_belongs_to_the_version(env):
    """`value` is priced content and goes through a version, never here. The
    refusal is `_reject_unknown`'s and is by NAME, so a caller is told rather
    than having its figure accepted and dropped."""
    row, _version = _a_discount(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError):
            discount_services.update_discount(env.admin, row["id"], {"value": "99"})


# ══════════════════════════════════════════════════════════════════════════
# VERB 2 · a live version is corrected over the SAME window
# ══════════════════════════════════════════════════════════════════════════


def test_a_correction_keeps_the_window_it_corrects(env):
    """⚠ **THE ONE ASSERTION THAT IS THE WHOLE RULE.** `correct_tax` copies the
    corrected row's window VERBATIM rather than taking it from the payload, and
    this copies that property exactly. A correction that moved the window would
    be a backdated change wearing a correction's clothes.

    The payload below asks for `2027-01-01` on purpose, and is ignored.
    """
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {
                "value": "1.5",
                "effective_from": "2027-01-01",
                "reason": "Typed 15 where the programme is 1.5 per cent.",
            },
        )
        correction = discount_models.DiscountVersion.objects.get(pk=out["id"])
    assert correction.effective_from == date(2026, 8, 1)
    assert correction.effective_to == version.effective_to
    assert correction.value == Decimal("1.5")


def test_the_corrected_row_stops_pricing_and_keeps_its_figure_for_ever(env):
    """Hard rule 4's posture on a version table: the original is never
    rewritten and never deleted."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        version.refresh_from_db()
        correction = discount_models.DiscountVersion.objects.get(pk=out["id"])
    assert version.status == discount_models.VERSION_SUPERSEDED
    assert version.value == Decimal("15")  # its own figure, kept
    assert version.superseded_by_id == correction.id
    assert correction.corrects_id == version.id
    assert correction.status == discount_models.VERSION_ACTIVE


def test_the_correction_carries_its_reason_and_its_author(env):
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        correction = discount_models.DiscountVersion.objects.get(pk=out["id"])
    assert correction.correction_reason == "Typed 15 where the programme is 1.5 per cent."
    # r10's version table renders `change_reason` on every row, so neither
    # table has a blank cell for a correction.
    assert correction.change_reason == correction.correction_reason
    # WHO, on the version's own row — never read back out of `audit_log`, which
    # is pruned on a retention schedule.
    assert correction.corrected_by_id == env.admin.id


def test_the_correction_does_not_forge_an_approval(env):
    """⚠ **`BR-RAT-077` COMPUTES THE SECOND APPROVAL AT SUBMIT, AND A
    CORRECTION DOES NOT SUBMIT.** Copying the corrected row's signatures onto
    content those people never read would be inventing a signature. The
    requirement is RECOMPUTED from the correction's own budget cap instead, so
    an auditor can see whether the figure NOW in force would itself have needed
    a second pair of eyes."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        correction = discount_models.DiscountVersion.objects.get(pk=out["id"])
    assert correction.submitted_by_id is None and correction.submitted_at is None
    assert correction.approved_by_id is None and correction.approved_at is None
    assert correction.self_approved is False


def test_the_absence_of_a_second_approval_check_is_recorded(env, audit_rows):
    """`BR-RAT-109`'s ruled posture — warn, allow, and RECORD. The warning names
    what was SKIPPED and never a figure nobody computed."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
    actions = audit_actions(audit_rows)
    assert "discount.version_corrected" in actions
    assert "discount.correction_created" in actions
    created = next(
        row for row in audit_rows if row["action"] == "discount.correction_created"
    )
    assert created["after"]["corrected_without_submission"] is True


def test_a_correction_restating_one_field_keeps_every_other(env):
    """`_version_payload_of`'s reason: a correction that blanked the caps or the
    verification rules because the client did not know to send them would be a
    silent policy change."""
    # `accepted_proof_kinds` is REQUIRED beside `proof_required` — BR-RAT-076's
    # contradiction gate, which refuses the pair rather than resolving it.
    _row, version = _a_discount(
        env,
        value="15",
        cap_per_bill="20",
        proof_required=True,
        accepted_proof_kinds=["government_id"],
    )
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        correction = discount_models.DiscountVersion.objects.get(pk=out["id"])
    assert correction.cap_per_bill == Decimal("20")
    assert correction.proof_required is True


def test_a_reason_of_two_words_is_not_a_reason(env):
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            discount_services.correct_discount_version(
                env.admin, version.id, {"value": "1.5", "reason": "typo"}
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.discounts.correction_reason"


def test_a_correction_that_corrects_nothing_is_refused(env):
    """It would mint an identical row and supersede a live version for no
    reason — a break in the chain with no content."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.ValidationError) as excinfo:
            discount_services.correct_discount_version(
                env.admin, version.id, {"reason": "Nothing at all is changing here."}
            )
    assert excinfo.value.field_errors[0]["message_key"] == "rating.discounts.correction_empty"


def test_a_draft_is_edited_not_corrected(env):
    _row, version = _a_discount(env, value="15")
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.correct_discount_version(
                env.admin, version.id, {"value": "1.5", "reason": "It is only a draft after all."}
            )
    assert excinfo.value.message_key == "rating.discounts.correct_draft"


def test_a_version_that_never_went_live_cannot_be_corrected(env):
    """A pending or scheduled version has priced nothing, so there is no
    recorded figure to correct: it is withdrawn and re-filed."""
    _row, version = _a_discount(env, value="15")
    with tenant_ctx(env.tenant):
        discount_services.submit_discount_version(env.admin, version.id)
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.correct_discount_version(
                env.admin, version.id, {"value": "1.5", "reason": "Not in force, so not this."}
            )
    assert excinfo.value.message_key == "rating.discounts.correct_not_in_force"


def test_a_row_already_corrected_sends_you_to_its_replacement(env):
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.correct_discount_version(
                env.admin, version.id, {"value": "2", "reason": "Correcting the corrected row."}
            )
    assert excinfo.value.message_key == "rating.discounts.already_corrected"


def test_the_response_says_issued_bills_are_untouched(env):
    """CLAUDE.md hard rule 4, and `OQ-310` named in the response so an operator
    who has just fixed a value is not left believing the money is fixed."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
    assert out["issued_bills_unchanged"] is True
    assert out["open_question"] == "OQ-310"


def test_the_chain_is_served_on_the_row(env):
    """A screen must be able to draw a superseded row as CORRECTED rather than
    as merely old, and that needs both ends of the link."""
    _row, version = _a_discount(env, value="15")
    _live(env, version)
    with tenant_ctx(env.tenant):
        out = discount_services.correct_discount_version(
            env.admin,
            version.id,
            {"value": "1.5", "reason": "Typed 15 where the programme is 1.5 per cent."},
        )
        original = discount_services.version_row(
            discount_models.DiscountVersion.objects.get(pk=version.pk)
        )
    assert out["corrects"] == str(version.id)
    assert original["superseded_by"] == out["id"]
    assert out["correction_reason"].startswith("Typed 15")


# ══════════════════════════════════════════════════════════════════════════
# What this deliberately does NOT change
# ══════════════════════════════════════════════════════════════════════════


def test_the_submit_approve_activate_workflow_is_untouched(env):
    """`BR-RAT-077` and `BR-RAT-109` are ratified and this change is required
    not to touch them. A version still cannot be approved without being
    submitted first."""
    _row, version = _a_discount(env)
    with tenant_ctx(env.tenant):
        with pytest.raises(errors.BizError) as excinfo:
            discount_services.approve_discount_version(env.admin, version.id)
    assert excinfo.value.message_key == "rating.discounts.not_pending"

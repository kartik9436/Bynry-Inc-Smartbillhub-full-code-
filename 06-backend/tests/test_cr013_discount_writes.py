# ── Trace ──────────────────────────────────────────────
# Change:   CR-013 part 3 — the DISCOUNT WRITE API, mounted with DIS-02.
#           `POST /discounts` (create) and `POST /discounts/{id}/versions`
#           (edit — a NEW DATED VERSION, never a PATCH).
#           Screens: DIS-02 (`09-screen-inventory.md` §18 row 12)
# Rules:    BR-RAT-076 (the named contradiction: automatic enrolment with
#           mandatory proof is REFUSED, never resolved) · BR-RAT-078 (enrolments
#           survive versioning, so an edit is a new dated version) · BR-RAT-083
#           (anyone drafts, Owner/Admin activates) · A4 (Plans & Rates writes
#           are System-Admin-only, server-enforced)
# Tests:    this file
# Impacts:  apps/rating/api.py (two handlers). ⚠ `apps/rating/discount_services`
#           is NOT touched by this lane — it is 🔒 HUMAN-REVIEW-PENDING and every
#           rule these routes enforce is already its own and already tested in
#           tests/test_cr013_discounts.py.
# ───────────────────────────────────────────────────────
"""The write half, proved at the ROUTE.

⚠ **THIS FILE ASSERTS WIRING, NOT RULES.** Every gate, refusal and money
decision below belongs to `discount_services` and is asserted at length in
`tests/test_cr013_discounts.py`; duplicating those assertions here would create
a second place for a rule to be stated and a second place for it to drift. What
this file checks is the one thing that file cannot: that a browser can reach
them. `test_cr013_discount_reads.py` opens with the same argument for the same
reason — six discount tables shipped with every write service built and no route
to any of them, and a person could not see a row.

⚠ **AND ONE ABSENCE IS ASSERTED ON PURPOSE: THERE IS NO `PATCH /discounts/{id}`.**
BR-RAT-078 makes an edit a NEW DATED VERSION — `discount_enrolments` carries an
FK to the DISCOUNT and never to a version, and r10's SENIOR went v1 −10% → v2
−15% on 1 Jan 2026 without its 72 accounts re-enrolling. A PATCH route would be
an invitation to the in-place overwrite the rule forbids, so its absence is part
of the design and goes RED if somebody adds one without reading this.
"""

import pytest

from apps.rating import api, discount_sample_data
from apps.rating import discounts as discount_models

from tests.test_us_rat_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_rat_helpers import FakeUser, api_call, tenant_ctx

pytestmark = pytest.mark.django_db


def _verbs(view):
    """The HTTP methods a DRF function-view accepts, uppercased. `@api_view`
    hangs the generated class on `.cls`, and DRF adds OPTIONS to every view —
    which is why the assertions below test membership rather than equality on
    the routes that also answer GET."""
    return {verb.upper() for verb in view.cls().allowed_methods} - {"OPTIONS", "HEAD"}


def _draft_body(**overrides):
    """The smallest body `create_discount` accepts. No money literal beyond the
    value itself, which is the thing under test: `value` is PERCENTAGE POINTS on
    a discount (`15` is 15%), not the fraction `charges.percent` stores."""
    body = {
        "code": "SENIORTEST",
        "name": "Senior discount",
        "discount_type": discount_models.DISCOUNT_PERCENTAGE,
        "value": "15",
        "applies_to": discount_models.SCOPE_WHOLE_BILL,
    }
    body.update(overrides)
    return body


# ══════════════════════════════════════════════════════════════════════════
# 1 · THE ROUTES THEMSELVES
# ══════════════════════════════════════════════════════════════════════════


def test_the_write_routes_are_registered_and_the_forbidden_verbs_are_not():
    """RED before DIS-02: `discounts` was GET-only and `discounts/{id}/versions`
    did not exist, so the wizard's commit had nowhere to post.

    ⚠ **THIS TEST WAS NAMED `…_and_patch_is_not` AND ASSERTED THAT THE OBJECT
    ROUTE TOOK NO `PATCH` AT ALL, UNTIL 2026-09-17 (`BR-RAT-1016` ·
    `DEF-RAT-5709`).** It was RIGHT for the rule it was written for and it is
    NOT weakened here — the absence it was protecting is narrowed to what the
    rule actually forbids, and the two verbs it could not have known about are
    asserted positively.

    **What `BR-RAT-078` forbids is an in-place overwrite of the PRICED
    AGREEMENT**, and that is still forbidden: what a discount is WORTH goes
    through `POST /discounts/{id}/versions` and nothing else. What the object
    route now takes is the IDENTITY — code, name, programme owner, funding
    source, the assistance-filing flag — which is what the programme is CALLED
    rather than what it is worth, and is the same class of fact as the GL
    account on its own narrow door beside it. Before that route existed a
    misspelt programme name could not be fixed at all.

    **The absence still asserted, and it is the one that matters:** no `PUT`,
    no `DELETE` and no `POST` on the object route. The danger this test was
    written for is a route being ADDED, so the shape is kept and only the
    membership moves.
    """
    routes = {str(entry.pattern) for entry in api.urlpatterns}
    assert "discounts" in routes
    assert "discounts/<str:discount_id>/versions" in routes
    # BR-RAT-1016 — the two doors a discount had neither of.
    assert "discounts/<str:discount_id>/versions/<str:version_id>" in routes
    assert "discounts/<str:discount_id>/versions/<str:version_id>/corrections" in routes
    # The list route answers BOTH now — DIS-01 reads it and DIS-02 posts to it.
    assert {"GET", "POST"} <= _verbs(api.discounts)
    assert _verbs(api.discount_item) & {"PUT", "DELETE", "POST"} == set()
    assert {"GET", "PATCH"} <= _verbs(api.discount_item)
    assert _verbs(api.discount_versions) == {"POST"}
    # A DRAFT is edited in place and a LIVE version is corrected — one verb
    # each, so neither route can be reached by the act the other one refuses.
    assert _verbs(api.discount_version_item) == {"PATCH"}
    assert _verbs(api.discount_version_corrections) == {"POST"}


# ══════════════════════════════════════════════════════════════════════════
# 2 · CREATE — one call lands the identity AND version 1, both DRAFT
# ══════════════════════════════════════════════════════════════════════════


def test_a_post_creates_the_discount_and_its_first_version_as_drafts(env):
    """BR-RAT-083's *"anyone may DRAFT, Owner/Admin ACTIVATE"* is expressible on
    this object in a way it was not on a charge code (DEF-375): the create lands
    a draft, and nothing bills from a draft."""
    response = api_call(
        api.discounts,
        "post",
        data=_draft_body(),
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert response.status_code == 201
    assert response.data["code"] == "SENIORTEST"
    assert response.data["status"] == discount_models.DISCOUNT_DRAFT
    with tenant_ctx(env.tenant):
        discount = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIORTEST")
        versions = list(discount_models.DiscountVersion.objects.filter(discount=discount))
    assert len(versions) == 1
    assert versions[0].version_no == 1
    assert versions[0].status == discount_models.VERSION_DRAFT
    # ⚠ PERCENTAGE POINTS, ROUND-TRIPPED. `15` stays fifteen — a route that
    # scaled it would store 0.15 (a 0.15% discount) or 1500 (refused), and both
    # would be well-formed rows.
    assert versions[0].value == pytest.approx(15, abs=1e-9)


def test_the_named_contradiction_is_refused_at_the_route(env):
    """CR-013 part 3, verbatim: *"validation gates including automatic enrolment
    with mandatory proof (contradictory)"*. DIS-02 blocks it at the step that
    raises it; this proves the server still refuses a caller that did not."""
    response = api_call(
        api.discounts,
        "post",
        data=_draft_body(
            enrolment_mode=discount_models.ENROLMENT_AUTOMATIC,
            proof_required=True,
            accepted_proof_kinds=["government_id"],
        ),
        user=FakeUser(env.owner.id),
        role="system_admin",
        tenant=env.tenant,
    )
    assert response.status_code == 422
    # 11b §3 G1's envelope is FLAT — {code, message_key, params, field_errors,
    # br_ref, trace_id} — and the field-level refusal is what a screen maps onto
    # the control that caused it.
    fields = {error["field"] for error in response.data["field_errors"]}
    assert "proof_required" in fields
    assert any(
        error["message_key"] == "rating.discounts.automatic_with_mandatory_proof"
        for error in response.data["field_errors"]
    )


def test_a_read_only_role_cannot_create_a_discount(env):
    """A4: Plans & Rates writes are System-Admin-only and the SERVER enforces it
    — BR-SHL-025's disabled button is the courtesy, not the control."""
    response = api_call(
        api.discounts,
        "post",
        data=_draft_body(code="CLERKTEST"),
        user=FakeUser(env.owner.id),
        role="billing_clerk",
        tenant=env.tenant,
    )
    assert response.status_code in (401, 403)
    with tenant_ctx(env.tenant):
        assert not discount_models.Discount.objects.filter(
            tenant=env.tenant, code="CLERKTEST"
        ).exists()


# ══════════════════════════════════════════════════════════════════════════
# 3 · EDIT — a NEW DATED VERSION, and the enrolments do not move
# ══════════════════════════════════════════════════════════════════════════


def test_the_edit_door_drafts_version_2_and_requires_a_reason(env):
    """BR-RAT-037's discipline at the route: *"a version history where every row
    says nothing is a history nobody can use."*"""
    with tenant_ctx(env.tenant):
        discount_sample_data.seed_sample_discounts(env.admin)
        senior = discount_models.Discount.objects.get(tenant=env.tenant, code="SENIOR")
        before = discount_models.DiscountVersion.objects.filter(discount=senior).count()

    user = FakeUser(env.owner.id)
    refused = api_call(
        api.discount_versions,
        "post",
        data={
            "discount_type": discount_models.DISCOUNT_PERCENTAGE,
            "value": "20",
            "applies_to": discount_models.SCOPE_WHOLE_BILL,
        },
        user=user,
        role="system_admin",
        tenant=env.tenant,
        discount_id=str(senior.id),
    )
    assert refused.status_code == 422

    accepted = api_call(
        api.discount_versions,
        "post",
        data={
            "discount_type": discount_models.DISCOUNT_PERCENTAGE,
            "value": "20",
            "applies_to": discount_models.SCOPE_WHOLE_BILL,
            "change_reason": "Raised from -15% to -20% for the 2027 programme year",
        },
        user=user,
        role="system_admin",
        tenant=env.tenant,
        discount_id=str(senior.id),
    )
    assert accepted.status_code == 201
    with tenant_ctx(env.tenant):
        after = discount_models.DiscountVersion.objects.filter(discount=senior).count()
        # ⚠ THE OLD VERSION IS STILL THERE. An edit APPENDS; nothing overwrites
        # a priced state a bill can still resolve to.
        assert after == before + 1


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-013 part 3 VERBATIM · `09-screen-inventory.md` §18 row 12 ·
#         BR-RAT-076/078/083 · A4
# generated: 2026-08-21 by the CR-013 DIS-02 lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_cr013_discount_writes.py✔ ·
#        pytest tests/test_cr013_discount_reads.py 20 passed (unchanged)✔
# exceptions: this file asserts WIRING only — every rule these routes enforce is
#            `discount_services`', is 🔒 HUMAN-REVIEW-PENDING, and is already
#            asserted in tests/test_cr013_discounts.py. A second statement of a
#            rule is a second place for it to drift.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

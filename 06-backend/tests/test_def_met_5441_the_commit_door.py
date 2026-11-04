# ── Trace ──────────────────────────────────────────────
# Defects: DEF-MET-5441 (the connect wizard's Create-connection button posts
#          to POST /connections/commit, which answered 404 — so no build made
#          through that screen had ever reached the database) ·
#          DEF-2961 (the manifest reported a premises the commit never made)
# Rules:   BR-MET-112 (nothing is written until the last button; ONE
#          transaction, both or neither) · BR-MET-1024 (New Connect may create
#          the address it builds on) · BR-SHL-019 (exactly one transactional
#          commit) · BR-INT-048 (a premises' parcel key IS external_ref)
# Screens: S87 step 8 — **Create connection**
# ───────────────────────────────────────────────────────
"""**Does the address the button posts to exist, and does pressing it build?**

`DEF-MET-5441`'s own escape reason names the missing test: *"a screen's primary
action must have one test that resolves its real URL against the mounted
urlpatterns. The repo has 42 portal test files and 391 cases and not one asks
whether the address a button posts to is served."*

Both halves of this feature were green for weeks over a wire that was not
connected — the front-end suite MOCKS this endpoint module, and every backend
case calls `commit_connection` directly with an id the browser never has. So
the first case below asks Django's own router, and the rest drive the payload
the BROWSER assembles rather than one written for the service's signature.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY.** `resolve()` on a path the router does
not serve raises `Resolver404`, so case 1 cannot pass over an unmounted route —
but it WOULD pass over a route mounted onto the wrong view, which is why it
asserts the view function by name too. The build cases could pass wrongly if
they asserted the manifest alone (a dict the service returns), so each one asks
the DATABASE what exists instead.
"""

import pytest
from django.urls import Resolver404, resolve

from apps.metering import api as metering_api
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    make_premises,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _wizard_plan(**over):
    """**The payload `commitPlanOf` actually emits** — keys and spellings both.

    Copied from `NewConnectWizard.tsx:374-437`, not from `commit_connection`'s
    parameter list. That difference is the whole point: three defects in a row
    on this one call (`DEF-MET-5428`, `DEF-MET-5093`, `DEF-MET-5437`) were the
    payload and the reader disagreeing about a key, with both sides tested on
    their own half.
    """
    plan = {
        "premises": {
            "id": None,
            "address": "1400 Brazos Bend Drive",
            "premise_type": None,
            "parcel_ref": "R-99001",
            "read_route": None,
            # `DEF-MET-5465` — step 4's ticks. Without them the property is
            # created with `services_available` NULL and `BR-MET-003`'s inner
            # bound refuses EVERY meter with "nobody has been asked which
            # services this address offers" (`DEF-772`).
            "services_available": ["electric"],
        },
        "mode": "our_crew",
        "scope": "new_premise",
        "units_prefix": "Apt",
        "target_activation": None,
        "service_request_id": None,
        "units": [{"label": "Apt 1", "is_common_area": False}],
        "meters": [],
        "plan_assignments": [],
        "create_owner_account": False,
        "owner": {},
        "quote_total": None,
        "occupancy": "vacant_service_off",
        "work_orders": [],
    }
    plan.update(over)
    return plan


# ════════════════════════════════════════════════════════════════════════════
# 1 · THE ADDRESS THE BUTTON POSTS TO IS SERVED
# ════════════════════════════════════════════════════════════════════════════
def test_the_button_s_address_resolves_to_the_commit_view():
    """**`POST /connections/commit` — no id in the path, because there is no
    connection row before the last button (`BR-MET-112`).**

    Measured live on 2026-09-16 before this door existed: this address answered
    **404** while `/connections` and `/connections/<uuid>/commit` each answered
    401. A 404 and a 401 look the same to a browser that shows *"something went
    wrong"*, which is how eight finished steps shipped over a dead wire.

    ⚠ **THE VIEW IS COMPARED BY IDENTITY AND NOT BY `__name__`.** Every view in
    this product is a DRF `@api_view` over Django's `as_view`, whose closure is
    called `view` — so `match.func.__name__ == "view"` is TRUE of all of them
    and would have been a check that cannot fail.
    """
    match = resolve("/api/brazosbend/connections/commit")
    assert match.func is metering_api.connection_commit_new, (
        "the wizard's Create-connection button must reach the orchestrating "
        "commit, not some other view that happens to sit on this path"
    )


def test_the_id_bearing_commit_still_has_its_own_door():
    """The new literal must not have swallowed the route beside it."""
    match = resolve("/api/brazosbend/connections/11111111-1111-1111-1111-111111111111/commit")
    assert match.func is metering_api.connection_commit


def test_a_path_the_router_does_not_serve_still_raises():
    """**What makes case 1 a check rather than a decoration.** If `resolve()`
    answered for anything, the two cases above would prove nothing at all."""
    with pytest.raises(Resolver404):
        resolve("/api/brazosbend/connections/commit-the-typo")


# ════════════════════════════════════════════════════════════════════════════
# 2 · PRESSING IT BUILDS — AND THE DATABASE IS WHAT IS ASKED
# ════════════════════════════════════════════════════════════════════════════
def test_one_press_creates_the_address_the_draft_and_the_build(dana, brazos):
    """**The whole build from one payload, with no id and no premises on file.**

    This is the case that could not be written before: `create_connection`
    needed a premises and `commit_connection` needed a draft, so the browser's
    payload — which is neither — had nowhere to go.
    """
    with tenant_ctx(brazos):
        before = metering_models.Premises.objects.count()
        built = w6.commit_new_connect(dana, _wizard_plan())

        assert built["connection_no"], "a build with no CON- number is not a build"
        connection = work_tables.Connection.objects.get(pk=built["id"])
        assert connection.state != "draft", "the commit submits the build it made"

        # THE ADDRESS — created by this door, on the wizard's own spelling.
        assert metering_models.Premises.objects.count() == before + 1
        premises = metering_models.Premises.objects.get(pk=connection.premises_id)
        assert premises.address_line == "1400 Brazos Bend Drive"
        # `BR-INT-048` — a premises' parcel key IS `external_ref`. There is no
        # `parcel_ref` column and this door does not invent one.
        assert premises.external_ref == "R-99001"

        # THE UNITS — asked of the table, never of the manifest.
        assert metering_models.Unit.objects.filter(premises_id=premises.id).count() == 1

        # AND THE MANIFEST'S `premises` COUNT IS ANSWERABLE NOW (`DEF-2961`).
        assert built["manifest"]["premises"] == 1
        assert built["premises_created"] is True
        assert not [a for a in built["unavailable"] if a["field"] == "premises"]


def test_a_named_address_is_used_and_no_second_one_is_made(dana, brazos):
    """**The other branch: the clerk chose an address already on file.**

    `premises_created` is `False` and the manifest says `0` — *"we made none"*,
    which is a different fact from *"this cannot be answered here"*.
    """
    with tenant_ctx(brazos):
        existing = make_premises(dana)
        before = metering_models.Premises.objects.count()
        plan = _wizard_plan()
        plan["premises"] = {**plan["premises"], "id": existing["id"], "address": ""}

        built = w6.commit_new_connect(dana, plan)

        assert metering_models.Premises.objects.count() == before
        assert str(work_tables.Connection.objects.get(pk=built["id"]).premises_id) == str(existing["id"])
        assert built["premises_created"] is False
        assert built["manifest"]["premises"] == 0


# ════════════════════════════════════════════════════════════════════════════
# 3 · BOTH OR NEITHER — AND THE ADDRESS IS INSIDE THE PROMISE
# ════════════════════════════════════════════════════════════════════════════
def test_a_refused_build_leaves_no_address_behind(dana, brazos):
    """**`BR-MET-112` across BOTH calls, which is why this is one door.**

    Two round trips could not give this answer: the premises and the draft
    would already be committed when the second call refused, and no screen in
    this product can find a Draft connection on an address nobody has heard of.

    The refusal used here is a real one a clerk meets — a work-order template
    that was never published (`BR-WRK-011`) — raised at the far end of the
    commit, long after the address was written.
    """
    with tenant_ctx(brazos):
        draft_template = w6.create_work_order_template(
            dana, {"name": "Not published yet", "service": "electric", "sequence": 0}
        )
        premises_before = metering_models.Premises.objects.count()
        units_before = metering_models.Unit.objects.count()
        connections_before = work_tables.Connection.objects.count()

        with pytest.raises(errors.BizError) as refused:
            w6.commit_new_connect(
                dana,
                _wizard_plan(
                    units=[{"label": "Apt 1"}, {"label": "Apt 2"}],
                    work_orders=[{"template_id": draft_template["id"], "template_version": 0}],
                ),
            )
        assert "template_not_published" in str(refused.value)

        # NOT ONE ROW SURVIVED — including the address, which the OLD shape
        # would have left standing with a Draft connection attached to it.
        assert metering_models.Premises.objects.count() == premises_before
        assert metering_models.Unit.objects.count() == units_before
        assert work_tables.Connection.objects.count() == connections_before


def test_a_blank_address_is_refused_by_the_premises_door_s_own_words(dana, brazos):
    """One rule, one message. This door emits `address_line` even when blank so
    the clerk meets `create_premises`'s refusal and not a copy of it."""
    with tenant_ctx(brazos):
        plan = _wizard_plan()
        plan["premises"] = {**plan["premises"], "address": "   "}
        with pytest.raises(errors.ValidationError) as refused:
            w6.commit_new_connect(dana, plan)
        assert "address_required" in str(refused.value)


def test_a_premises_key_nobody_reads_is_refused_by_name(dana, brazos):
    """**`DEF-MET-4715` — a tolerated key with no consumer is a silent hole.**

    `route` sat on `create_premises`'s payload for weeks refused by nothing and
    read by nothing, so a request naming a route that did not exist answered
    201 and dropped it. The next person who adds a field to the wizard's
    premises block meets a red door instead.
    """
    with tenant_ctx(brazos):
        plan = _wizard_plan()
        plan["premises"] = {**plan["premises"], "lot_number": "17"}
        with pytest.raises(errors.ValidationError) as refused:
            w6.commit_new_connect(dana, plan)
        assert "premises_field_unknown" in str(refused.value)


# ════════════════════════════════════════════════════════════════════════════
# 4 · `DEF-MET-5437` — EVERY METER LANDED ON UNIT 1
# ════════════════════════════════════════════════════════════════════════════
def test_each_meter_lands_on_the_unit_whose_label_it_names(dana, brazos):
    """**A 26-unit build, and the last meter is on `Apt 26`, not on `Apt 1`.**

    The wizard can only send LABELS — `BR-MET-112` means the units do not exist
    until this commit creates them — and the commit read `unit_id`, found
    nothing and fell back to `units[0].id`. So **every meter on a 26-unit build
    attached to the first unit**, with a manifest that said 26 and was right
    about the count and wrong about every single placement.

    ⚠ **WHAT WOULD MAKE THIS PASS WRONGLY:** asserting the meter COUNT, which
    was correct on the defect. So it asks which unit each asset stands on.
    """
    with tenant_ctx(brazos):
        labels = [f"Apt {n}" for n in range(1, 27)]
        built = w6.commit_new_connect(
            dana,
            _wizard_plan(
                units=[{"label": label, "is_common_area": False} for label in labels],
                meters=[
                    {"unit_label": label, "service": "electric", "asset_no": None}
                    for label in labels
                ],
            ),
        )
        assert built["manifest"]["units"] == 26

        connection = work_tables.Connection.objects.get(pk=built["id"])
        units = {
            unit.label: unit
            for unit in metering_models.Unit.objects.filter(premises_id=connection.premises_id)
        }
        assert set(units) == set(labels)

        assert built["manifest"]["meters"] == 26
        placed = w6.seams.asset_counts_for_units([str(unit.id) for unit in units.values()])
        if not placed:
            pytest.skip("the assets seam is unpublished here; placement cannot be read back")
        # ⚠ **ONE METER ON EACH UNIT, AND THE COUNT ABOVE IS NOT THE CHECK.**
        # On the defect `manifest["meters"]` read 26 and was RIGHT, while all
        # 26 stood on `Apt 1`. A test that stopped at the count would have
        # passed on it, which is why this asserts the SPREAD.
        assert sorted(placed.values()) == [1] * 26, (
            f"every meter landed on one unit — DEF-MET-5437; got {sorted(placed.items())}"
        )


def test_a_meter_naming_a_unit_this_build_never_made_is_refused(dana, brazos):
    """**A guess that looks like an answer is what this defect WAS.**

    The old fallback re-pointed an unmatched meter at unit 1 and said nothing.
    `BR-MET-112` is both-or-neither, so a build naming a unit it never created
    takes the whole build down and names the labels it does have.
    """
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            w6.commit_new_connect(
                dana,
                _wizard_plan(
                    units=[{"label": "Apt 1"}],
                    meters=[{"unit_label": "Apt 9", "service": "electric", "asset_no": None}],
                ),
            )
        assert "unit_label_unknown" in str(refused.value)
        assert metering_models.Unit.objects.filter(label="Apt 1").count() == 0, (
            "both or neither — the unit the build DID name must not survive"
        )

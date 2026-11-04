# ── Trace ──────────────────────────────────────────────
# Change:   OQ-422 CLOSED 2026-08-27 — PO verbatim: *"(b) Accept and warn"*.
#           Screens: S25 (the "Add reading" action) · S28 (the full path)
# Story:    US-MET-012 (S25) · US-MET-007 (S28 steps 1–2)
# Rules:    BR-MET-140 (a counter reading on a meter with NO cycle is ACCEPTED
#           and WARNED) · BR-MET-129 (a collected reading is STORED — *"we can
#           give the warning, but we cannot reject the reading"*) ·
#           BR-MET-122 (an OFF-cycle meter warns with a reason — the
#           neighbouring case whose shape this borrows) · BR-MET-014 (batch
#           tags inherit to every row) · CLAUDE.md hard rule 1
# ───────────────────────────────────────────────────────
"""BR-MET-140 — the counter reading on a meter that belongs to no cycle.

**THE CASE, WORKED, AND IT IS THE ONE THE PO RULED ON.** A clerk at the counter
has meter **M-5002** in front of them and a reading of **1,300 kWh** taken
today. The meter resolves to no route — or to a route that is on no cycle: a
new connection not yet on a walk, or a meter whose route membership moved.
**The customer is standing there.**

The PO ruled *"(b) Accept and warn"*. So three things must all be true at once,
and each has its own case below:

  1. **The reading POSTS.** Refusing was never offered (BR-MET-129).
  2. **The absence is a WARNING with a reason a clerk can act on** — which
     reason, and which fix, depends on WHICH of the two shapes it is.
  3. **It is not an error.** Nothing is wrong with the reading; the
     configuration fault is ours, so the tier is `warning` and never `error`.

⚠ **AND THE BATCH STILL CARRIES NO `cycle_id` FIELD AT ALL**, rather than an
empty one. That predates the ruling and the ruling does not change it: an empty
tag is a claim about which cycle a reading belongs to, and an absence is not.
TC-4 pins it, because "accept and warn" reads like permission to tag it with
something.
"""

from datetime import date

import pytest

from apps.metering import models as metering_models
from apps.metering import quick_read
from apps.metering import services as metering_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    FakeUser,
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)
from tests.test_cr038_w5_bulk_and_quick import _planned_meter
from tests.test_us_met_reads_helpers import seed_config

pytestmark = pytest.mark.django_db

READ_DAY = "2026-07-15"


def _route_without_cycle(tenant, asset, *, code="RT-NO-CYCLE"):
    """Put the meter's service point on a route that is on NO cycle.

    The SECOND of BR-MET-140's two shapes, and it is a different fault from the
    first: the meter IS on a walk, so a clerk told *"it is on no route"* would
    go and look in the wrong place. `services.collection_route_id` resolves
    `asset → service_point → route`, so the route is attached where that chain
    reads it.
    """
    route = metering_models.Route.objects.create(
        tenant=tenant,
        code=code,
        name="Not yet on a cycle",
        route_type="walk",
        cycle=None,  # ⚠ the whole point of the fixture
        status="active",
    )
    point_id = getattr(asset, "service_point_id", None)
    assert point_id is not None, "the fixture meter must hang off a service point"
    metering_models.ServicePoint.objects.filter(pk=point_id).update(route_id=route.id)
    return route


# ══════════════════════════════════════════════════════════════════════════
# TC-1 · NO ROUTE — the reading is accepted, and the warning says why
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_140_tc1__a_meter_on_no_route_warns_and_still_accepts(brazos, marcus):
    """PO verbatim: *"(b) Accept and warn"*.

    `accepted: True` is on the wire beside the reason because it is the FIRST
    thing the clerk needs to know — a warning that does not say the reading
    still posts reads as a refusal to somebody with a customer in front of
    them, and refusing is answer (c), which was never offered."""
    with tenant_ctx(brazos):
        seed_config()
        _planned_meter(marcus, brazos, asset_no="M-5002")

        ctx = quick_read.quick_entry_context(meter_no="M-5002", read_at=READ_DAY)

        assert ctx["cycle"]["cycle"] is None
        absent = ctx["cycle"]["cycle_absent"]
        assert absent["reason"] == "no_route"
        assert absent["accepted"] is True, "the reading POSTS — refusing was never offered"
        assert absent["action"] == "add_meter_to_route", "a warning must name its own fix"
        assert absent["rule_ref"] == "BR-MET-140"
        # The period is still DERIVED and still shown — the ruling changed the
        # warning, not the derivation (CR-038's clause 4).
        assert ctx["cycle"]["period_month"] == "2026-07-01"


# ══════════════════════════════════════════════════════════════════════════
# TC-2 · A ROUTE ON NO CYCLE IS A DIFFERENT FAULT WITH A DIFFERENT FIX
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_140_tc2__a_route_with_no_cycle_names_its_own_fix(brazos, marcus):
    """Two shapes, two remedies. A clerk told *"this meter is on no route"* when
    the truth is *"its route is on no cycle"* goes to the route screen, finds
    the meter there, and concludes the product is wrong. So the reason picks the
    action, in ONE declaration (`quick_read.CYCLE_ABSENT_ACTIONS`), and a screen
    can never pair a reason with somebody else's fix."""
    with tenant_ctx(brazos):
        seed_config()
        meter = _planned_meter(marcus, brazos, asset_no="M-5003")
        asset = metering_services.seams.meter_by_id(meter["id"])
        route = _route_without_cycle(brazos, asset)

        ctx = quick_read.quick_entry_context(meter_no="M-5003", read_at=READ_DAY)

        assert ctx["cycle"]["cycle"] is None
        absent = ctx["cycle"]["cycle_absent"]
        assert absent["reason"] == "route_has_no_cycle"
        assert absent["action"] == "assign_route_to_cycle"
        assert absent["accepted"] is True
        # ⚠ AND THE ROUTE IS NAMED. The clerk is being asked to go and fix
        # something; not saying WHICH route would be a warning they cannot act
        # on, which is the whole difference between answers (a) and (b).
        assert ctx["cycle"]["route"] == {"id": str(route.id), "code": route.code}


# ══════════════════════════════════════════════════════════════════════════
# TC-3 · IT IS A WARNING AND NOT AN ERROR — the tier IS the ruling
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_140_tc3__the_absence_is_a_warning_tier_never_an_error(brazos, marcus):
    """⚠ Nothing is wrong with the reading. The configuration fault is OURS, and
    a danger tier would tell a clerk that the number they just read off a meter
    is bad — the opposite of what the PO ruled. Asserted on the SERVED severity
    so a screen cannot quietly promote it, and asserted here rather than only on
    the frontend because the payload is where the tier is decided."""
    with tenant_ctx(brazos):
        seed_config()
        _planned_meter(marcus, brazos, asset_no="M-5004")

        absent = quick_read.quick_entry_context(meter_no="M-5004", read_at=READ_DAY)["cycle"][
            "cycle_absent"
        ]

        assert absent["severity"] == "warning"
        assert absent["severity"] != "error"
        # And the question it used to track is CLOSED, so it is gone rather
        # than re-worded — a stated absence may not outlive its reason.
        assert "tracks" not in absent


# ══════════════════════════════════════════════════════════════════════════
# TC-4 · THE BATCH STILL CARRIES NO `cycle_id` FIELD AT ALL
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_140_tc4__accepting_does_not_invent_a_cycle_tag(brazos, marcus):
    """*"Accept and warn"* reads like permission to tag the reading with
    something so it stops being invisible. It is not. An empty or defaulted
    `cycle_id` is a CLAIM about which cycle a reading belongs to; the absence is
    the truth, and BR-MET-014's inheritance would push a wrong tag onto the row.

    The staged batch is therefore built with the field ABSENT — not null, not
    empty — which is what `quickReadBatchRequest` does on the frontend and what
    the stage endpoint sees."""
    with tenant_ctx(brazos):
        seed_config()
        _planned_meter(marcus, brazos, asset_no="M-5005")

        ctx = quick_read.quick_entry_context(meter_no="M-5005", read_at=READ_DAY)

        assert ctx["cycle"]["cycle"] is None
        # Nothing anywhere in the payload offers a cycle to tag with.
        assert ctx["cycle"]["read_window"] is None
        assert ctx["cycle"]["in_window"] is None
        assert "cycle_id" not in ctx["cycle"]
        # BR-MET-140 is named on the wire so a reader of the payload can find
        # the rule without reading this test.
        assert "BR-MET-140" in ctx["rule_refs"]


# ══════════════════════════════════════════════════════════════════════════
# TC-5 · A METER THAT IS ON A CYCLE CARRIES NO WARNING AT ALL
# ══════════════════════════════════════════════════════════════════════════
def test_br_met_140_tc5__a_meter_on_a_cycle_has_no_absence_to_warn_about(brazos, marcus):
    """The mirror, so the warning cannot become unconditional furniture: a
    payload that always carried `cycle_absent` would train a clerk to ignore
    it, which is how a warning stops being one."""
    with tenant_ctx(brazos):
        seed_config()
        meter = _planned_meter(marcus, brazos, asset_no="M-5006")
        asset = metering_services.seams.meter_by_id(meter["id"])
        route = _route_without_cycle(brazos, asset, code="RT-ON-CYCLE")
        cycle = metering_models.Cycle.objects.create(
            tenant=brazos,
            code="CY-140",
            name="Counter cycle",
            frequency="Monthly",
            first_run_date=date(2026, 7, 1),
            bill_day=8,
            due_days=20,
        )
        metering_models.Route.objects.filter(pk=route.pk).update(cycle_id=cycle.id)

        ctx = quick_read.quick_entry_context(meter_no="M-5006", read_at=READ_DAY)

        assert ctx["cycle"]["cycle"]["code"] == "CY-140"
        assert ctx["cycle"]["cycle_absent"] is None

# ── Trace ──────────────────────────────────────────────
# Story:    the Reads→Work door — `from_flows`' SIXTH caller. PO ruling
#           2026-09-14, verbatim *"please build this"*, reversing that
#           morning's `Q2` deferral.
#           Screens: the upload wizard's stage-3 shortfall (*Send someone out*)
# Rules:    BR-WRK-024 (every order carries its source; `meter_read` is the
#           sixteenth token and `metering/0056` puts it in the database) ·
#           BR-WRK-055 (a failed raise never fails the flow) · BR-WRK-006 (an
#           order stands on an anchor) · BR-WRK-016 (the offer is the utility's
#           own PUBLISHED templates) · BR-MET-023 / BR-MET-027 / BR-MET-062 (a
#           missing reading's answer is a field visit) · BR-MET-1161 / hard
#           rule 8 (the address is WALKED to) · B14 rule 31 (no id on screen —
#           `source_ref` is the meter NUMBER)
# Tests:    this file (SQLite, the ordinary suite) · test_reads_field_work_pg.py
#           (the two cases SQLite structurally cannot fail)
# Impacts:  apps/work/from_flows.py · apps/work/api.py · apps/work/seams/
#           {assets,metering}_seam.py · apps/metering/connections.py
# ───────────────────────────────────────────────────────
"""The sixth caller, proved on the ordinary suite.

⚠ **WHAT THIS FILE CANNOT PROVE, SAID FIRST SO NOBODY READS MORE INTO IT
(hard-won law 7's *reporting zero over a scope it silently excludes*).**
`config/settings/test.py` hardcodes in-memory SQLite. Two of this door's
guarantees are invisible here and BOTH have their case in
`test_reads_field_work_pg.py` instead:

  1. **`ck_work_orders_source` actually refuses an unknown token.** A CHECK over
     a text column is a claim about the DEPLOYED database, and `metering/0056`
     exists precisely because a Python tuple and a database constraint can
     disagree — *"Python accepts the raise and PostgreSQL refuses the INSERT"*.
  2. **A failed raise on one meter does not poison the loop** (hard-won law 14).
     SQLite has no aborted-transaction state, so the broken version passes here.

What IS proved here is everything else: the offer, the stamp, the refusal, the
anchor walk, and that nothing ticked writes nothing.
"""

from __future__ import annotations

import pytest

from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from apps.work import from_flows

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, make_premises, make_unit, tenant_ctx


def _published_template(actor, name: str, service: str = "electric") -> dict:
    """One template the utility has PUBLISHED — `BR-WRK-016`'s whole point.

    `sequence=0` on purpose: `_IN_CONNECTION_SEQUENCE[meter_read]` is False
    because the meter is already standing there, so the offer is the jobs you do
    to a service that EXISTS — a re-read, an exchange, a leak investigation —
    and never the jobs that build one.
    """
    header = w6.create_work_order_template(actor, {"name": name, "service": service, "sequence": 0})
    w6.publish_work_order_template(actor, header["id"])
    return header


def _meter_on_a_unit(actor, tenant, asset_no: str = "MTR-0463"):
    """A meter standing at an address, built the way the product builds one."""
    premises = make_premises(actor, address_line="22 Cypress Row")
    unit = make_unit(actor, premises["id"])
    service = tenancy_models.Service.objects.get(code="electric")
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name="Residential Standard",
        defaults={"code": "residential-standard", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name="Residential Standard — electric", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(plan.id)})
    meter = make_asset(
        actor,
        asset_no=asset_no,
        service="electric",
        unit="kWh",
        unit_id=str(unit["id"]),
        # `assets.install_date_required` — a meter fitted to a service point has
        # a date it went in. The refusal is the assets module's and is right.
        install_date="2024-01-15",
    )
    return premises, unit, meter


@pytest.mark.django_db
def test_the_offer_is_the_utilitys_own_published_templates_and_writes_nothing(dana, brazos):
    """`propose` answers the meter's own service, by its own NUMBER, and WRITES
    NOTHING — `from_flows` rule 1, the whole reason this door is safe."""
    with tenant_ctx(brazos):
        _premises, _unit, meter = _meter_on_a_unit(dana, brazos)
        _published_template(dana, "Re-read the meter")
        before = work_tables.WorkOrder.objects.count()

        offer = from_flows.propose(from_flows.FLOW_METER_READ, meter["id"])

        assert offer["refusal"] is None
        assert offer["count"] >= 1
        assert "Re-read the meter" in [row["name"] for row in offer["proposed"]]
        # B14 rule 31 — the flow's reference is the METER NUMBER a clerk quotes,
        # never the uuid. This is what `source_ref` will stamp.
        assert offer["flow"]["ref"] == "MTR-0463"
        # Rule 1, asserted rather than trusted: a proposal is a READ.
        assert work_tables.WorkOrder.objects.count() == before


@pytest.mark.django_db
def test_a_raise_stamps_meter_read_as_the_source_and_the_meter_number_as_the_ref(dana, brazos):
    """`BR-WRK-024` — the order says WHY it exists and WHICH meter asked.

    ⚠ **THE SOURCE IS ASSERTED AS A LITERAL, NOT AS THE CONSTANT.** Reading
    `work_tables.SOURCE_METER_READ` here would pass if somebody renamed the token to
    `dispatcher` — which is the one value `connections.py:544` forbids by name,
    because a visit filed that way vanishes from `EP-WRK-10`'s first-time-fix
    report. A literal is what makes that rename go red.
    """
    with tenant_ctx(brazos):
        _premises, _unit, meter = _meter_on_a_unit(dana, brazos)
        template = _published_template(dana, "Re-read the meter")

        result = from_flows.raise_for(
            from_flows.FLOW_METER_READ, meter["id"], [template["id"]], dana
        )

        assert result["count"] == 1
        raised = result["raised"][0]
        assert raised["source"] == "meter_read"
        assert raised["source_ref"] == "MTR-0463"
        assert raised["order_no"].startswith("WO-")


@pytest.mark.django_db
def test_the_order_is_anchored_on_the_premises_the_meter_stands_at(dana, brazos):
    """Hard rule 8 — the address is WALKED to (meter → point → unit → premises),
    and `BR-WRK-006`'s anchor is that premises rather than a column of its own.

    The unit and the asset travel too, so a crew is told which meter at which
    door; neither is a second copy of the address.
    """
    with tenant_ctx(brazos):
        premises, unit, meter = _meter_on_a_unit(dana, brazos)
        template = _published_template(dana, "Re-read the meter")

        result = from_flows.raise_for(
            from_flows.FLOW_METER_READ, meter["id"], [template["id"]], dana
        )

        order = work_tables.WorkOrder.objects.get(pk=result["raised"][0]["id"])
        assert str(order.premises_id) == str(premises["id"])
        assert str(order.unit_id) == str(unit["id"])
        assert str(order.asset_id) == str(meter["id"])


@pytest.mark.django_db
def test_a_meter_standing_at_no_address_is_refused_before_anything_is_written(dana, brazos):
    """Judgment 8 — a spare in inventory is on no service point, so a job raised
    from it would stand on nothing and nobody could be dispatched to it.

    ⚠ **`ck_work_orders_has_anchor` WOULD ACCEPT THIS ROW on `asset_id` alone,
    and `_require_anchor` deliberately does not.** A job with a meter and no
    address is a job a crew cannot be sent to, and the honest place to say so is
    the screen the clerk is standing on.
    """
    with tenant_ctx(brazos):
        # No `unit_id` — a spare left in INVENTORY, which is `make_asset`'s own
        # default and the state this case is about: on no service point at all.
        spare = make_asset(dana, asset_no="MTR-SPARE", service="electric", unit="kWh")
        template = _published_template(dana, "Re-read the meter")
        before = work_tables.WorkOrder.objects.count()

        offer = from_flows.propose(from_flows.FLOW_METER_READ, spare["id"])
        assert offer["refusal"] is not None
        assert offer["refusal"]["code"] == from_flows.NO_ANCHOR_CODE
        assert offer["proposed"] == []

        with pytest.raises(from_flows.FlowRaiseRefused):
            from_flows.raise_for(from_flows.FLOW_METER_READ, spare["id"], [template["id"]], dana)
        assert work_tables.WorkOrder.objects.count() == before


@pytest.mark.django_db
def test_nothing_ticked_raises_nothing_and_is_not_an_error(dana, brazos):
    """`from_flows` rule 1 — the raise is OFFERED. A clerk who ticks nothing has
    ANSWERED the question, so this is a recorded choice and not a failure."""
    with tenant_ctx(brazos):
        _premises, _unit, meter = _meter_on_a_unit(dana, brazos)
        before = work_tables.WorkOrder.objects.count()

        result = from_flows.raise_for(from_flows.FLOW_METER_READ, meter["id"], [], dana)

        assert result["count"] == 0
        assert result["raised"] == []
        assert work_tables.WorkOrder.objects.count() == before


@pytest.mark.django_db
def test_an_unknown_meter_reads_as_absent_rather_than_as_forbidden(dana, brazos):
    """HR-1 — existence must not leak. A cross-tenant or made-up id answers the
    404-shaped refusal every other flow answers, never a 403."""
    from core import errors

    with tenant_ctx(brazos):
        with pytest.raises(errors.NotFoundError):
            from_flows.propose(
                from_flows.FLOW_METER_READ, "00000000-0000-0000-0000-000000000000"
            )


def test_the_token_and_the_flow_kind_are_one_string_not_two():
    """⚠ **THE CHEAPEST GUARD IN THIS FILE AND THE ONE MOST LIKELY TO EARN ITS
    KEEP.** `from_flows` stamps `source = flow_kind`, so if these two ever drift
    the raise is accepted by Python and refused by PostgreSQL inside the
    transaction — `metering/0052`'s *"the one outcome nobody could debug"*.

    It also pins the token INTO the vocabulary the database's CHECK is built
    from: drop `SOURCE_METER_READ` out of `WORK_ORDER_SOURCES` and this goes red
    here, in the ordinary suite, rather than on a customer's meter.
    """
    assert from_flows.FLOW_METER_READ == work_tables.SOURCE_METER_READ == "meter_read"
    assert work_tables.SOURCE_METER_READ in work_tables.WORK_ORDER_SOURCES
    assert from_flows.FLOW_METER_READ in from_flows.FLOW_KINDS
    # And the offer is the *service already exists* half of the template list —
    # a meter that cannot be read does not need a Meter set.
    assert from_flows._IN_CONNECTION_SEQUENCE[from_flows.FLOW_METER_READ] is False


# ── Lifecycle ─────────────────────────────────────────────
# packet: the Reads→Work door (decision log 2026-09-14) · from_flows judgments 4, 7, 8
# generated: 2026-09-14 by the Meter Reads field-visit lane
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=n/a
# gates: pytest tests/test_reads_field_work.py · G78 · the PostgreSQL half is
#   tests/test_reads_field_work_pg.py and is NOT run by the ordinary suite
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

"""CR-094-BRC01 step 2 wave G — the Complaints and Services queues.

`DEF-WRK-5106` — **the dispatcher's job-type filter matched the heading row and
nothing beneath it.**

`work_order_types` became a two-level catalogue on 2026-09-07 (`BR-WRK-058`, PO
ruling: *"this is not correct - you will ahve to think from all Utilty services
point of view"*), and `dispatch._apply_filters` was written when it was flat. So
`type=<the Consumer Complaint row>` returned only jobs whose `type_ref` IS that
row — and **every job a clerk actually files is under one of its fifteen
kinds**: *Billing Issues*, *Odour complaint*, *Low Pressure*, *Missed
collection*.

⚠ **WHY NO EXISTING CASE COULD SEE IT.** `test_us_wrk_026_tc4_each_of_the_five_
chips_narrows_the_list` exercises the type chip with two TOP-LEVEL types, so
nothing in the repository ever picked a heading that HAS children. The wrong
answer is an empty list, which on this route is indistinguishable from a utility
that has no such jobs — the `absence is invisible to every check this repo has`
shape `CLAUDE.md` hard rule 8 records for a retired lookup value.

⚠ **`BR-WRK-026` DOES NOT MOVE.** *"The dispatcher list has exactly six filters
— search, type, status, priority, technician, area"*, and a seventh bare name is
still refused. This widens what the SECOND of the six matches; it adds none.
"""

from __future__ import annotations

import pytest

from apps.customers import services as customers_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch
from apps.work import models as work_models
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_ten_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


def _reference(actor):
    """The utility's own priorities and job types, in the ONE order that works:
    a seeded type names its default priority BY CODE, so priorities must be rows
    first or every type lands with a NULL default and `due_at` is never
    stamped."""
    work_services.seed_reference_list("work_priorities", [], "test")
    work_services.seed_reference_list("work_order_types", [], "test")


def _order(actor, address, **payload):
    premises = make_premises(  # noqa: F405
        actor, address_line=address, services_available=["water"]
    )
    body = {"service": "water", "premises_id": premises["id"], **payload}
    return w6.create_work_order(actor, None, body)


def test_cr094_wave_g_type_filter_includes_its_kinds(dana, brazos):
    """Filtering by a HEADING returns the jobs filed under its kinds.

    This is the case the Complaints tab is: the drawing's own four rows are all
    sub-types, so a queue pinned to *Consumer Complaint* that matched only the
    heading row would be EMPTY on a utility doing exactly what the blueprint
    shows — with every test in the repository green.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        heading = work_models.WorkOrderType.objects.get(
            tenant_id=brazos.id, code="COMPLAINT"
        )
        kind = work_models.WorkOrderType.objects.filter(
            tenant_id=brazos.id, parent_id=heading.id
        ).first()
        assert kind is not None, "the seeded catalogue has kinds under COMPLAINT"

        # The job a clerk files: the KIND, never the heading.
        filed = _order(dana, "142 Bakers Row", type=kind.name, type_id=str(kind.id))
        # A job of another heading entirely, which must NOT appear.
        other = work_models.WorkOrderType.objects.get(
            tenant_id=brazos.id, code="CONSUMER_SVC"
        )
        _order(dana, "88 Quarry Lane", type=other.name, type_id=str(other.id))

        complaints = dispatch.dispatch_page(filters={"type": str(heading.id)})
        assert complaints["total"] == 1
        assert complaints["rows"][0]["order_no"] == filed["order_no"]
        # ⚠ AND THE ROW SHOWS THE KIND'S OWN WORDS, not the heading's — that is
        # the `WHAT ABOUT` column, and `_dispatch_row` sends the catalogue name.
        assert complaints["rows"][0]["type"] == kind.name

        # The SERVICE heading's own queue is a different list, which is the
        # mechanical half of *"two tabs rather than one filter"*.
        services = dispatch.dispatch_page(filters={"type": str(other.id)})
        assert services["total"] == 1
        assert services["rows"][0]["order_no"] != filed["order_no"]


def test_cr094_wave_g_a_kind_filter_still_returns_only_its_own(dana, brazos):
    """⚠ **THE WIDENING IS ONE LEVEL DEEP AND NOT A PREFIX MATCH.**

    Picking a KIND must still narrow to that kind. A first draft that matched
    `type_ref__parent_id` alone would have made every sub-type filter return its
    siblings — the opposite defect, and the one a reader of the fix would
    naturally not think to check (law 7's *"ask what would make this check pass
    wrongly"*).
    """
    with tenant_ctx(brazos):
        _reference(dana)
        heading = work_models.WorkOrderType.objects.get(
            tenant_id=brazos.id, code="COMPLAINT"
        )
        kinds = list(
            work_models.WorkOrderType.objects.filter(
                tenant_id=brazos.id, parent_id=heading.id
            ).order_by("code")[:2]
        )
        assert len(kinds) == 2, "two kinds are needed to tell siblings apart"
        first = _order(dana, "1 Elm St", type=kinds[0].name, type_id=str(kinds[0].id))
        _order(dana, "2 Elm St", type=kinds[1].name, type_id=str(kinds[1].id))

        narrowed = dispatch.dispatch_page(filters={"type": str(kinds[0].id)})
        assert narrowed["total"] == 1
        assert narrowed["rows"][0]["order_no"] == first["order_no"]

        # And the heading still holds both.
        assert dispatch.dispatch_page(filters={"type": str(heading.id)})["total"] == 2


def test_cr094_wave_g_a_job_on_an_account_carries_its_promise(dana, brazos):
    """`BR-WRK-006` + `BR-WRK-018` — what the two intake forms write.

    The forms send an ACCOUNT as the anchor and the KIND as `type_id`, and every
    other field the drawing asks for is the server's own: the priority comes
    from the type, and `due_at` comes from the priority's `sla_hours`. This is
    the case that says *the form needs to build nothing*.

    ⚠ **THE `type_id` IS WHAT MAKES THE PROMISE EXIST.** With no type resolved,
    `_resolve_priority` has no default to read and the order gets NO `due_at` at
    all — so a form that could only send words would be one rename away from
    raising complaints with no response time, silently. That is why
    `raiseWorkOrderFromDispatcher` grew a `type_id` field in this wave.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        # ⚠ **A KIND WITH NO RESPONSE TIME OF ITS OWN, ON PURPOSE
        # (`DEF-WRK-5109`).** Twelve of the seeded sub-types carry none, and
        # `Billing Issues` is the one the blueprint's own table draws first. A
        # case that picked `Odour complaint` — which carries `URGENT` itself —
        # would pass on a resolver that never looks at the parent at all.
        kind = work_models.WorkOrderType.objects.get(
            tenant_id=brazos.id, code="BILLING_ISSUES"
        )
        assert kind.default_priority_id is None, "this case needs a kind with no own default"
        unit = make_unit(  # noqa: F405
            dana, make_premises(dana, address_line="142 Bakers Row")["id"], label="Suite 1"  # noqa: F405
        )
        account = customers_services.create_account(
            dana, {"unit_id": unit["id"], "account_type": "commercial"}
        )
        raised = w6.create_work_order(
            dana,
            None,
            {"account_id": account["id"], "type": kind.name, "type_id": str(kind.id)},
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert str(order.account_id) == str(account["id"])
        assert order.type_ref_id == kind.id
        # The promise, stamped rather than derived on read.
        assert order.priority_id is not None
        assert order.due_at is not None


def test_cr094_wave_g_a_kind_with_its_own_urgency_still_beats_its_heading(dana, brazos):
    """`models.URGENT_BEATS_ITS_PARENT` — the four that beat their heading.

    ⚠ **THIS IS THE FALSE PASS THE FIX ABOVE COULD PRODUCE.** A parent walk
    written as *"always take the heading's"* would answer **8 hours** for a gas
    leak, which is the exact figure `OQ-WRK-1765` exists to prevent —
    *"arriving by accident, with nothing on any screen showing that a choice had
    been skipped"*. The inheritance is a FALLBACK, never an override.
    """
    with tenant_ctx(brazos):
        _reference(dana)
        # ⚠ **A SUB-TYPE THIS TENANT ACTUALLY HAS.** Sub-types follow their
        # SERVICE (`DEF-WRK-4512`, PO 2026-09-07: *"gas onlyutility carry only
        # gas meters"*), and the fixture utility sells water — so the gas
        # leak's sibling is the right case here and `GAS_ODOUR` is simply not a
        # row on this tenant.
        urgent_kind = work_models.WorkOrderType.objects.get(
            tenant_id=brazos.id, code="NO_WATER_SUPPLY"
        )
        assert urgent_kind.default_priority is not None
        assert urgent_kind.default_priority.code == "URGENT"
        raised = _order(
            dana, "88 Quarry Lane", type=urgent_kind.name, type_id=str(urgent_kind.id)
        )
        order = work_tables.WorkOrder.objects.get(pk=raised["id"])
        assert order.priority.code == "URGENT"
        # And its heading is High, so the two are genuinely different answers.
        heading = work_models.WorkOrderType.objects.get(tenant_id=brazos.id, code="COMPLAINT")
        assert heading.default_priority.code == "HIGH"

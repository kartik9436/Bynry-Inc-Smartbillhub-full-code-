# ── Trace ──────────────────────────────────────────────
# Change:  CR-168-BRC10 lane FLOW-FIX — the PO's question, verbatim: "when work
#          orders are completed is clerk able to see the status update in
#          those requests". §F measured it on 2.503.2: mostly not.
# Defects: DEF-CUS-9628 (move records' visit) · DEF-CUS-9629 (transfer counts
#          by the wrong key) · DEF-CUS-9630 (reconnect rows never show their
#          job) · DEF-WRK-9621 (raw Raised-by keys) · DEF-WRK-9622 (Premise —
#          on account-anchored jobs) · DEF-WRK-9624 (failed job ↔ follow-up) ·
#          DEF-WRK-9626 (every flow offered Meter exchange) · DEF-WRK-9638
#          ("unspecified" stored as a job's name) · DEF-MET-9633 (a build that
#          does not move when its last job is accepted)
# Rules:   BR-WRK-024 (every order carries its source) · BR-WRK-055 · BR-MET-110
#          (the field sends, a person accepts) · hard rule 8 (an address is
#          walked to the premises) · B14 rule 31 (no id as a visible value)
# ───────────────────────────────────────────────────────
"""Each case here was run RED on the tip before its fix (hard-won law 7); the
failure each one printed is quoted in its docstring.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2): a test that stamps
the order's `source_ref` with the same expression the read uses would agree
with any key. So every case stamps the order the way the REAL raise stamps it
— the flow's NUMBER (`from_flows` puts `flow["ref"]` there) — and asks the read
with the record the screen opens.
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.customers import move_record_reads, reconnect_read, transfer_reads
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import dispatch, from_flows
from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_premises, tenant_ctx
from tests.test_us_wrk_039_from_flows import (
    _move_out,
    _occupant,
    _published_template,
    _unit_with_plan,
)

pytestmark = pytest.mark.django_db

REPO = Path(__file__).resolve().parents[2]


def _accept(order_id) -> None:
    """The two facts the reads count — the field closed it, a person accepted
    it. Written as columns because what is under test is the READ; the close
    and the accept are proved by their own suites (`test_def_wrk_9569_…`)."""
    work_tables.WorkOrder.objects.filter(pk=order_id).update(
        state=work_tables.WO_COMPLETED, completed_at=timezone.now(), accepted_at=timezone.now()
    )


def _account_job(actor, account_id, *, source, source_ref, service="electric"):
    return w6.create_work_order(
        actor,
        None,
        {
            "type": "Changeover read",
            "service": service,
            "account_id": str(account_id),
            "source": source,
            "source_ref": source_ref,
        },
    )


# ── DEF-CUS-9628 · the move record shows its visit ──────────────────────────
def test_def_cus_9628_a_move_out_record_counts_its_visit_and_names_the_order(dana, brazos):
    """RED on the tip: ``visit`` was ``{'value': None, 'unavailable': {'code':
    'visit_not_readable_from_customers', …}}`` over a raised job."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _published_template(dana, name="Final read")
        result = _move_out(dana, account["id"], template_ids=[template["id"]])
        order_no = work_tables.WorkOrder.objects.get(pk=result["work_orders"][0]["id"]).order_no

        visit = move_record_reads.record_detail(result["move_no"])["still_owed"]["visit"]
        assert visit["unavailable"] is None
        assert visit["value"]["raised"] == 1
        assert visit["value"]["done"] == 0
        assert visit["value"]["accepted"] == 0
        assert [o["order_no"] for o in visit["value"]["orders"]] == [order_no]

        _accept(result["work_orders"][0]["id"])
        visit = move_record_reads.record_detail(result["move_no"])["still_owed"]["visit"]
        assert (visit["value"]["done"], visit["value"]["accepted"]) == (1, 1)


def test_def_cus_9628_a_move_that_raised_nothing_says_not_raised_not_unreadable(dana, brazos):
    """The absence is now TRUE: nothing was raised, and Work CAN answer."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        result = _move_out(dana, account["id"])

        visit = move_record_reads.record_detail(result["move_no"])["still_owed"]["visit"]
        assert visit["value"] is None
        assert visit["unavailable"]["code"] == "no_visit_raised"


# ── DEF-CUS-9629 · the transfer counts by the NUMBER the job carries ────────
def test_def_cus_9629_the_changeover_is_counted_by_the_transfer_number(dana, brazos):
    """RED on the tip: ``assert 0 == 1`` — the read asked by the row's uuid and
    the job carries ``TRF-26-0099``."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        raised = _account_job(dana, account["id"], source="transfer", source_ref="TRF-26-0099")
        _accept(raised["id"])

        row = SimpleNamespace(id=uuid.uuid4(), transfer_no="TRF-26-0099")
        changeover = transfer_reads._changeover(row)
        assert changeover["raised"] == 1
        assert changeover["completed"] == 1


# ── DEF-CUS-9630 · the reconnect row carries the job raised for it ──────────
def test_def_cus_9630_a_reconnect_row_shows_the_job_raised_for_its_service(dana, brazos):
    """RED on the tip: ``assert None == {'reference': 'WO-…', …}`` — every row
    served ``work_order: None``."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account_row = _occupant(dana, unit)
        from apps.customers import models as cmodels

        account = cmodels.Account.objects.get(pk=account_row["id"])
        raised = _account_job(
            dana, account.pk, source="reconnect", source_ref="DSC-26-0099", service="electric"
        )
        order_no = work_tables.WorkOrder.objects.get(pk=raised["id"]).order_no
        case = SimpleNamespace(services_cut=["electric", "water"], case_no="DSC-26-0099")

        rows = reconnect_read._services(case, account, is_master=False)["rows"]
        by_service = {row["service"]: row for row in rows}
        assert by_service["electric"]["work_order"] == {
            "reference": order_no,
            "assignee": None,
            "done": False,
            "accepted": False,
        }
        assert by_service["water"]["work_order"] is None


# ── DEF-WRK-9622 · a job on an ACCOUNT still names its premises ─────────────
def test_def_wrk_9622_an_account_anchored_job_walks_to_its_premises(dana, brazos):
    """RED on the tip: ``assert None is not None`` — the list walked three
    anchors and the account was not one of them."""
    with tenant_ctx(brazos):
        premises, unit = _unit_with_plan(dana, brazos, address_line="18 Wren Lane")
        account = _occupant(dana, unit)
        raised = _account_job(dana, account["id"], source="move_out", source_ref="MVO-26-0099")
        order = work_tables.WorkOrder.objects.select_related("account__unit__premises").get(pk=raised["id"])

        cell = work_selectors._premise_of(order)
        assert cell is not None
        assert cell["address"] == "18 Wren Lane"


# ── DEF-WRK-9624 · a failed job and its follow-up point at each other ───────
def test_def_wrk_9624_the_failed_job_and_its_follow_up_link_both_ways(dana, brazos):
    """RED on the tip: ``KeyError: 'follow_ups'``."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        premises = make_premises(dana, address_line="7 Fen Road", services_available=["water"])
        failed = w6.create_work_order(
            dana, None, {"type": "Meter set", "service": "water", "premises_id": premises["id"]}
        )
        follow = w6.create_work_order(
            dana,
            None,
            {
                "type": "Meter set",
                "service": "water",
                "premises_id": premises["id"],
                "source": "failed_outcome",
                "follows_order_id": failed["id"],
            },
        )
        failed_no = work_tables.WorkOrder.objects.get(pk=failed["id"]).order_no
        follow_no = work_tables.WorkOrder.objects.get(pk=follow["id"]).order_no

        assert dispatch.order_row(failed["id"])["follow_ups"] == [{"order_no": follow_no}]
        assert dispatch.order_row(follow["id"])["follows"] == {"order_no": failed_no}
        assert dispatch.order_row(failed["id"])["follows"] is None


# ── DEF-WRK-9638 · no placeholder word is stored as a job's name ────────────
def test_def_wrk_9638_a_template_raise_is_named_by_its_template_never_unspecified(dana, brazos):
    """RED on the tip: ``assert 'unspecified' == 'Leak investigation'``."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="9 Moor Close", services_available=["electric"])
        template = _published_template(dana, name="Leak investigation")
        raised = w6.create_work_order(
            dana,
            None,
            {"service": "electric", "premises_id": premises["id"], "template_id": template["id"]},
        )
        assert work_tables.WorkOrder.objects.get(pk=raised["id"]).type == "Leak investigation"

        bare = w6.create_work_order(
            dana, None, {"service": "electric", "premises_id": premises["id"]}
        )
        assert work_tables.WorkOrder.objects.get(pk=bare["id"]).type != "unspecified"


# ── DEF-WRK-9621 · every source token reads as a word in every catalogue ────
def test_def_wrk_9621_every_work_order_source_has_a_label_in_all_eleven_catalogues():
    """RED on the tip: ``meter_read`` and ``failed_outcome`` missing in 11 of 11."""
    missing: list[str] = []
    locales = REPO / "07-frontend" / "src" / "i18n" / "locales"
    files = sorted(locales.glob("*.json"))
    assert len(files) == 11, f"expected the eleven catalogues, found {len(files)}"
    for path in files:
        catalogue = json.loads(path.read_text(encoding="utf-8"))
        for token in work_tables.WORK_ORDER_SOURCES:
            if f"work.orders.source.{token}" not in catalogue:
                missing.append(f"{path.name}:{token}")
    assert missing == []


# ── DEF-WRK-9626 · a flow is offered the job type that fits it ──────────────
def test_def_wrk_9626_a_move_out_is_offered_its_reading_job_not_a_meter_exchange(dana, brazos):
    """RED on the tip: the proposal was ``['Final read', 'Meter exchange —
    residential']`` — both, unordered by fit."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_order_types", [], "test")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        _published_template(dana, name="Meter exchange — residential")
        reading = work_models.WorkOrderType.objects.get(code="RE_READ")
        final = w6.create_work_order_template(
            dana,
            {"name": "Final read", "service": "electric", "sequence": 0, "type_id": str(reading.id)},
        )
        w6.publish_work_order_template(dana, final["id"])

        offer = from_flows.propose("move_out", account["id"])
        names = [row["name"] for row in offer["proposed"]]
        assert names == ["Final read"]


def test_def_wrk_9626_a_flow_with_no_fitting_template_still_gets_the_general_offer(
    dana, brazos
):
    """The narrowing never empties an offer that had something in it."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        _published_template(dana, name="Meter exchange — residential")

        offer = from_flows.propose("move_out", account["id"])
        assert [row["name"] for row in offer["proposed"]] == ["Meter exchange — residential"]


# ── DEF-MET-9633 · a build moves on when its last job is accepted ───────────
def _technician(email: str, name: str):
    from apps.identity import models as identity_models
    from core import tenancy as core_tenancy

    tenant_id = core_tenancy.current_tenant_id()
    user = identity_models.User.objects.create(tenant_id=tenant_id, email=email, full_name=name)
    return work_models.Technician.objects.create(tenant_id=tenant_id, user=user)


def test_def_met_9633_the_last_accepted_job_clears_waiting_on_and_names_the_next_act(
    dana, brazos
):
    """RED on the tip: ``assert 'inspection' is None`` — the build went on
    saying it waited on a job that was finished and accepted."""
    from apps.work import dispatch as work_dispatch

    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_priorities", [], "test")
        premises = make_premises(dana, address_line="12 Heron Way", services_available=["water"])
        build = w6.create_connection(dana, {"premises_id": str(premises["id"])})
        w6.set_waiting_on(dana, build["id"], waiting_on="inspection")
        tech = _technician("r-patel@brazos.test", "R. Patel")
        first = w6.create_work_order(dana, build["id"], {"type": "Site inspection", "service": "water"})
        second = w6.create_work_order(dana, build["id"], {"type": "Meter set", "service": "water"})
        for raised in (first, second):
            work_dispatch.record_act(dana, raised["id"], {"act": "assign", "technician_id": str(tech.id)})
            w6.submit_field_result(tech.user, raised["id"], field_data={"ok": True}, outcome="passed")

        w6.accept_field_result(dana, first["id"])
        assert work_tables.Connection.objects.get(pk=build["id"]).waiting_on == "inspection"

        w6.accept_field_result(dana, second["id"])
        assert not work_tables.Connection.objects.get(pk=build["id"]).waiting_on


def test_def_cus_9630_the_rows_raise_names_a_service_and_gets_the_reconnect_template(
    dana, brazos
):
    """RED on the tip: the screen posted ``template_ids: ['electric']`` — a
    service code where a template id belongs — so every press raised nothing.
    The row now posts ``{service}`` and the server picks the utility's own
    reconnect template for it (``DEF-WRK-9626``'s fitting type first)."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_order_types", [], "test")
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        _published_template(dana, name="Meter exchange — residential")
        kind = work_models.WorkOrderType.objects.get(code="DISCONNECT_RECONNECT")
        visit = w6.create_work_order_template(
            dana,
            {"name": "Reconnect visit", "service": "electric", "sequence": 0, "type_id": str(kind.id)},
        )
        w6.publish_work_order_template(dana, visit["id"])

        assert reconnect_read._reconnect_template_for(account["id"], "electric") == [str(visit["id"])]
        assert reconnect_read._reconnect_template_for(account["id"], "gas") == []


def test_def_wrk_9626_the_add_row_door_names_each_flows_job_type(dana, brazos):
    """The wizards' *+ Add work order* row (`FieldVisitOrders`) offered the
    whole list with nothing chosen. RED on the tip: ``KeyError: 'flow_types'``."""
    with tenant_ctx(brazos):
        work_services.seed_reference_list("work_order_types", [], "test")
        options = from_flows.raise_options()
        reading = str(work_models.WorkOrderType.objects.get(code="RE_READ").id)
        reconnect = str(work_models.WorkOrderType.objects.get(code="DISCONNECT_RECONNECT").id)
        assert options["flow_types"]["move_out"] == reading
        assert options["flow_types"]["move_in"] == reading
        assert options["flow_types"]["transfer"] == reading
        assert options["flow_types"]["reconnect"] == reconnect
        assert "service_request" not in options["flow_types"]

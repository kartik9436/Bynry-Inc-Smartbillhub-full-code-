# ── Trace ──────────────────────────────────────────────
# Change:   CR-171-BRC10 (move-in redesign) · lane MVI-WIZ-UNIT · P1.19 · P1.27
#           (meter half) · E47 (meter facts on expand, image 31)
# Defects:  DEF-AST-9712 (a meter fitted by a move-in visit never left In stock)
# Rules:    image 30 (Field visit: Work order · For · Window · Assign to with
#           best-fit advice) · image 31 (the meter's facts on expand) ·
#           BR-WRK-055 (the flow never waits on the visit) · BR-AST-020
#           (inventory → active is the lawful step) · BR-MET-110 (acceptance
#           is the human act that confirms an installation)
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**Step 1's server leftovers — the meter's facts, the one Work order field,
and the meter a move-in visit fits.**

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):

  * **A template that is honoured because it is the default anyway.** The
    template case publishes TWO move-in templates of the same job type and
    names the one `_default_template` would NOT pick (it sorts by number).
  * **An install that happens because the meter was already installed.** The
    acceptance case creates the meter in the `inventory` stage and asserts it
    was `inventory` before the acceptance.
  * **One `_raise_flow_work` that is "reconciled" by being two that agree.**
    The reconcile case asserts IDENTITY, not equal answers.
"""

from __future__ import annotations

import pytest

from apps.customers import move_in_unit_read
from apps.customers import service_request_service
from apps.customers import services as customer_services
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.work import checklist, from_flows, templates_svc
from apps.work import models as work_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import field_actor, make_asset, tenant_ctx
from tests.test_us_wrk_039_from_flows import _occupant, _unit_with_plan
from tests.test_us_wrk_047_049_evidence import _satisfy_required_photos

pytestmark = pytest.mark.django_db


def _spare_on_unit(actor, unit, asset_no):
    """A meter EARMARKED to the unit and not yet fitted — stage `inventory`, no
    install date — the shape a build's commit writes (`installed=False`,
    `DEF-AST-5443`) and the only lawful way an uninstalled meter stands on a
    unit."""
    from django.db import transaction

    from apps.assets import services as asset_services
    from tests.test_us_met_helpers import _smallest_ratified_band

    with transaction.atomic():
        return asset_services._create_asset_inner(
            actor,
            {
                "type": "meter",
                "asset_no": asset_no,
                "service": "electric",
                "unit": "kWh",
                "read_method": "ami",
                "multiplier": "1",
                "size_class": _smallest_ratified_band("electric"),
                "unit_id": str(unit["id"]),
            },
            installed=False,
        )


def _move_in_type(tenant):
    """An active job type the move-in rows can name."""
    kind = work_models.WorkOrderType.objects.filter(tenant_id=tenant.id, active=True).order_by(
        "name"
    ).first()
    assert kind is not None, "the seeded tenant carries job types"
    return kind


def _template(actor, *, name, type_id, scope="per_premise"):
    header = templates_svc.create_draft(
        actor,
        {"name": name, "service": "electric", "scope": scope, "sequence": 0, "type_id": str(type_id)},
    )
    tid = header["id"]
    templates_svc.replace_collection(
        actor, tid, "tasks", [{"title": "Check the meter", "est_minutes": 15}]
    )
    templates_svc.publish(actor, tid)
    return tid


# ═══════════════════════════════════════════════════════════════════════════
# E47 · image 31 — the meter's facts on expand
# ═══════════════════════════════════════════════════════════════════════════
def test_a_meter_row_carries_its_facts_for_the_expand_row(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        make_asset(
            dana,
            asset_no="E-77123",
            serial_no="SN 77123",
            manufacturer="Badger",
            model="M25",
            seal_no="S-0912",
            install_date="2026-01-12",
            certification_due="2027-03-03",
            unit_id=str(unit["id"]),
            status="active",
        )
        table = move_in_unit_read.services_and_meters(unit["id"])
    rows = [m for s in table["services"] for m in s["meters"]] + table["unplaced"]
    row = next(r for r in rows if r["asset_no"] == "E-77123")
    facts = row["facts"]
    assert facts["serial_no"] == "SN 77123"
    assert facts["manufacturer"] == "Badger"
    assert facts["model"] == "M25"
    assert facts["seal_no"] == "S-0912"
    assert facts["installed_on"] == "2026-01-12"
    assert facts["certified_to"] == "2027-03-03"
    # A catalogue name, never a code and never an id (B14 rule 31).
    assert "read_method_name" in facts and "meter_type_name" in facts
    # The Size column prints the tenant's NAME for the size, never its code.
    assert row["size_class"] and row["size_name"]
    assert row["size_name"] != row["size_class"]


# ═══════════════════════════════════════════════════════════════════════════
# P1.19 · one Work order field naming a template; For; Window
# ═══════════════════════════════════════════════════════════════════════════
def test_a_row_may_name_its_template_meter_and_window():
    rows = from_flows.clean_order_rows(
        [
            {
                "type_id": "t-1",
                "template_id": "tpl-1",
                "asset_no": "W-5000",
                "window_start": "2026-10-10T08:00:00-05:00",
                "window_end": "2026-10-10T12:00:00-05:00",
            }
        ]
    )
    assert rows[0]["template_id"] == "tpl-1"
    assert rows[0]["asset_no"] == "W-5000"
    assert rows[0]["window_start"] == "2026-10-10T08:00:00-05:00"
    assert rows[0]["window_end"] == "2026-10-10T12:00:00-05:00"


def test_the_named_template_is_the_one_raised_not_the_default(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        first = _template(dana, name="Aaa first by number", type_id=kind.id)
        wanted = _template(dana, name="Zzz move-in read", type_id=kind.id)
        answer = from_flows.raise_orders_for(
            "move_in", account["id"], [{"type_id": str(kind.id), "template_id": wanted}], dana
        )
        order = work_tables.WorkOrder.objects.get(pk=answer["raised"][0]["id"])
    assert str(order.template_id) == str(wanted) != str(first)


def test_a_template_of_another_job_type_is_refused_by_name(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        kinds = list(
            work_models.WorkOrderType.objects.filter(tenant_id=brazos.id, active=True).order_by("name")[:2]
        )
        tid = _template(dana, name="Typed one way", type_id=kinds[0].id)
        with pytest.raises(errors.ValidationError) as caught:
            from_flows.raise_orders_for(
                "move_in", account["id"], [{"type_id": str(kinds[1].id), "template_id": tid}], dana
            )
    assert caught.value.message_key == "work.fromFlows.templateNotOffered"


def test_the_for_column_puts_the_job_on_that_meter(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        meter = make_asset(dana, asset_no="E-41001", unit_id=str(unit["id"]), install_date="2024-01-15")
        make_asset(dana, asset_no="E-41002", unit_id=str(unit["id"]), install_date="2024-01-15")
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        answer = from_flows.raise_orders_for(
            "move_in", account["id"], [{"type_id": str(kind.id), "asset_no": "E-41001"}], dana
        )
        order = work_tables.WorkOrder.objects.get(pk=answer["raised"][0]["id"])
    assert str(order.asset_id) == str(meter["id"])
    assert str(order.account_id) == str(account["id"])


def test_a_meter_not_on_the_flows_unit_is_refused_as_absent(brazos, dana):
    from core import errors

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        make_asset(dana, asset_no="E-49999")  # a spare in stock, on no unit
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        with pytest.raises(errors.ValidationError) as caught:
            from_flows.raise_orders_for(
                "move_in", account["id"], [{"type_id": str(kind.id), "asset_no": "E-49999"}], dana
            )
    assert caught.value.message_key == "work.fromFlows.assetNotOnUnit"


def test_a_window_is_written_on_the_job(brazos, dana):
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        answer = from_flows.raise_orders_for(
            "move_in",
            account["id"],
            [
                {
                    "type_id": str(kind.id),
                    "due_on": "2026-10-10",
                    "window_start": "2026-10-10T08:00:00-05:00",
                    "window_end": "2026-10-10T12:00:00-05:00",
                }
            ],
            dana,
        )
        order = work_tables.WorkOrder.objects.get(pk=answer["raised"][0]["id"])
    assert order.window_start is not None and order.window_end is not None
    assert order.window_start.isoformat().startswith("2026-10-10T13:00")  # 08:00 CDT in UTC
    assert answer["warnings"] == []


def test_the_move_in_offer_is_the_sequence_zero_templates(brazos, dana):
    """`GET /connections/proposed-work-orders?services=…&flow=move_in` — the
    move-in's Work order list is the jobs done to a LIVE service (sequence 0),
    where the bare read (New Connect step 6) offers only the BUILD jobs."""
    from apps.work import api as work_api
    from tests.test_us_ten_helpers import api_call

    with tenant_ctx(brazos):
        kind = _move_in_type(brazos)
        tid = _template(dana, name="Move-in read", type_id=kind.id)

    def ask(query):
        answer = api_call(
            work_api.proposed_work_orders, "get",
            f"/api/{brazos.subdomain}/connections/proposed-work-orders",
            user=dana.user, role="billing_clerk", tenant=brazos, query=query,
        )
        assert answer.status_code == 200, answer.data
        return [row["template_id"] for row in answer.data["proposed"]]

    assert str(tid) in ask({"services": "electric", "flow": "move_in"})
    assert str(tid) not in ask({"services": "electric"})


# ═══════════════════════════════════════════════════════════════════════════
# P1.19 · ONE `_raise_flow_work`
# ═══════════════════════════════════════════════════════════════════════════
def test_there_is_one_raise_flow_work(monkeypatch):
    """The request module's name stays (its approve door calls it) and its BODY
    is `services`' — it carries the typed rows too, which the copy could not."""
    seen = {}

    def the_one(actor, **kwargs):
        seen.update(kwargs)
        return {"work_orders": ["WO-1"], "warnings": []}

    monkeypatch.setattr(customer_services, "_raise_flow_work", the_one)
    answer = service_request_service._raise_flow_work(
        None, flow_kind="service_request", flow_id="r", template_ids=["t"], orders=[{"type_id": "x"}]
    )
    assert answer == {"work_orders": ["WO-1"], "warnings": []}
    assert seen["orders"] == [{"type_id": "x"}] and seen["template_ids"] == ["t"]


# ═══════════════════════════════════════════════════════════════════════════
# DEF-AST-9712 · a move-in visit that fits a meter installs it at acceptance
# ═══════════════════════════════════════════════════════════════════════════
def _accept(dana, oid):
    tech = field_actor(oid, dana)
    for row in work_models.WorkOrderTask.objects.filter(work_order_id=oid):
        checklist.tick_task(tech, oid, row.id)
    _satisfy_required_photos(tech, oid)
    w6.submit_field_result(tech, oid, outcome="passed")
    w6.accept_field_result(dana, oid)


def test_9712_accepting_a_move_in_visit_installs_the_meter_it_fitted(brazos, dana):
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        meter = _spare_on_unit(dana, unit, "E-97120")
        assert asset_models.Asset.objects.get(pk=meter["id"]).status.code == "inventory"
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        tid = _template(dana, name="Meter set at move-in", type_id=kind.id)
        oid = from_flows.raise_orders_for(
            "move_in",
            account["id"],
            [{"type_id": str(kind.id), "template_id": tid, "asset_no": "E-97120"}],
            dana,
        )["raised"][0]["id"]
        _accept(dana, oid)
        fitted = asset_models.Asset.objects.select_related("status").get(pk=meter["id"])
        order = work_tables.WorkOrder.objects.get(pk=oid)
    assert fitted.status.code == "active"
    assert fitted.install_date == order.completed_at.date()


def test_the_statement_the_po_signed_on_2026_10_06(brazos, dana):
    """⚖️ THE HUMAN SIGN-OFF, ASSERTED SO DRIFT GOES RED (PO 2026-10-06,
    decision log *"SIX MOVE-IN MONEY FILES SIGNED"*, verbatim: *"Money-file
    review: approve these six? - all good - go ahead"*). Statement 6 of six,
    exactly as shown, for `metering/connections.py` (`DEF-AST-9712`):

    *"When a technician accepts the move-in read job on meter W-5000, the meter
    is marked Installed that day if it was still in stock. No money moves."*

    "That day" is the day the field completed the visit (BR-TEN-043), which is
    the date the acceptance stamps. "No money moves": payments, refunds and
    journal entries are counted before and after the acceptance.
    """
    from apps.assets import models as asset_models
    from apps.ledger import models as ledger_models
    from apps.payments import models as payment_models

    def _money():
        return (
            payment_models.Payment.objects.count(),
            payment_models.Refund.objects.count(),
            ledger_models.JournalEntry.objects.count(),
            ledger_models.JournalLine.objects.count(),
        )

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        meter = _spare_on_unit(dana, unit, "W-5000")
        in_stock = asset_models.Asset.objects.get(pk=meter["id"]).status.code
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        tid = _template(dana, name="Move-in read W-5000", type_id=kind.id)
        oid = from_flows.raise_orders_for(
            "move_in",
            account["id"],
            [{"type_id": str(kind.id), "template_id": tid, "asset_no": "W-5000"}],
            dana,
        )["raised"][0]["id"]
        money_before = _money()
        _accept(dana, oid)
        money_after = _money()
        fitted = asset_models.Asset.objects.select_related("status").get(pk=meter["id"])
        order = work_tables.WorkOrder.objects.get(pk=oid)

    assert in_stock == "inventory"
    assert fitted.status.code == "active"
    assert fitted.install_date == order.completed_at.date()
    assert money_after == money_before


def test_9712_a_move_out_visit_installs_nothing(brazos, dana):
    """Only a MOVE-IN fits a meter; a move-out's final read on a spare does not."""
    from apps.assets import models as asset_models

    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        meter = _spare_on_unit(dana, unit, "E-97121")
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        oid = from_flows.raise_orders_for(
            "move_out", account["id"], [{"type_id": str(kind.id), "asset_no": "E-97121"}], dana
        )["raised"][0]["id"]
        _accept(dana, oid)
        stage = asset_models.Asset.objects.select_related("status").get(pk=meter["id"]).status.code
    assert stage == "inventory"


def test_a_refused_window_leaves_the_order_raised_and_says_so(brazos, dana):
    """Law 14: the schedule act is refused INSIDE the raise's transaction. On
    PostgreSQL that poisons the transaction unless it runs in its own
    SAVEPOINT — so the order must still be readable afterwards, and the next
    row must still raise."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        kind = _move_in_type(brazos)
        answer = from_flows.raise_orders_for(
            "move_in",
            account["id"],
            [
                {
                    "type_id": str(kind.id),
                    "window_start": "2026-10-10T12:00:00-05:00",
                    "window_end": "2026-10-10T08:00:00-05:00",
                },
                {"type_id": str(kind.id)},
            ],
            dana,
        )
        orders = list(work_tables.WorkOrder.objects.filter(pk__in=[r["id"] for r in answer["raised"]]))
    assert len(orders) == 2
    assert [w["code"] for w in answer["warnings"]] == ["work_order_not_scheduled"]
    assert answer["warnings"][0]["message_key"] == "work.fromFlows.notScheduled"

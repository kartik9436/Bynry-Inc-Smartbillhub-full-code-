# ── Trace ──────────────────────────────────────────────
# Change:   CR-162-BRC10 — the New Connection lifecycle (lane NC-A).
# Ruling:   decision log 2026-10-02, "NEW CONNECTION — THE PO'S SCREEN-BY-SCREEN
#           REVIEW BECOMES ONE PROGRAMME" (commit 56eb54ba9): Q1 master account
#           by premises type, Q2 the gate, Q3 the To-do tab, the approval /
#           activation items; and the same day's refinements — the premises
#           type carries *Can hold several units* as a setting, the To-do tab
#           keeps notes.
# Law 14:   the activation is one transaction; run on PostgreSQL with
#           `--ds=config.settings.pgtest` as well as the default suite.
# ───────────────────────────────────────────────────────
"""**What Create makes, and how a New Connection is approved and activated.**

The worked case the PO was shown (review ledger, `CR-162-BRC10`): *G Trade
Tower* — an apartment complex, two units, battery and solar on each. Create →
the premises and the owner's master account are PENDING. Unit 1's two orders
complete, Unit 2's open → *Activate what is ready* → Unit 1's battery and solar
are Activated, their two assets Installed today, the premises and the master
account Active, the request *Partly activated*. Unit 2's orders complete →
activate the rest → *Activated*.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY** (law 7, habit 2):
  * reading the RESPONSE instead of the tables — every state is read back from
    its row;
  * a refusal for some other reason — each refusal asserts its message key;
  * a gate test passing because the unit's ordinary orders are open — the gate
    case completes every ordinary order first, so only the gate can hold it;
  * an idempotency test passing because nothing was activated the first time —
    it asserts the first press's effects before pressing again.
"""

from __future__ import annotations

from uuid import UUID

import pytest

from apps.assets import models as asset_models
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import connection_activation as activation
from apps.metering import connections as w6
from apps.work import connection_models as work_tables
from apps.metering import lookups as metering_lookups
from apps.metering import models as metering_models
from apps.metering import premises_capacity
from core import errors

from tests.test_portal_request_to_active import (  # noqa: F401 — fixtures
    EQUIPMENT_TYPE,
    SIZES,
    _ctx,
    _plan,
    cedar,
    clerk,
)
from tests.test_us_cwp_helpers import *  # noqa: F401,F403 — growth_plan · identity_seam
from tests.test_us_met_helpers import audit_rows, staff_actor  # noqa: F401 — fixture

pytestmark = pytest.mark.django_db

OWNER = {
    "name": "G Trade Tower LLC",
    "email": "office@gtrade.test",
    "phone": "(512) 555-0162",
    "party_kind": "company",
    "identity": {"tax_id": "99-0001620"},
}


def _create(
    clerk,
    tenant,
    *,
    address,
    premise_type,
    labels,
    services=("battery", "solar"),
    owner=OWNER,
    unit_type=None,
):
    """The wizard's one press, from scratch: a NEW address of `premise_type`,
    `labels` units, the sized equipment of each capacity service, the plan, and
    the owner's master account when one is asked for."""
    plan = _plan(tenant)
    with _ctx(tenant):
        return w6.commit_new_connect(
            clerk,
            {
                "premises": {
                    "id": None,
                    "address": address,
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "premise_type": premise_type,
                    "parcel_ref": None,
                    "read_route": None,
                    "services_available": list(services),
                },
                "mode": "our_crew",
                "scope": "new_premise",
                "units_prefix": "Unit",
                "target_activation": None,
                "service_request_id": None,
                "units": [
                    {
                        "label": label,
                        "is_common_area": False,
                        **({"unit_type": unit_type} if unit_type else {}),
                    }
                    for label in labels
                ],
                "meters": [],
                "unit_services": [
                    {
                        "unit_label": label,
                        "service": code,
                        "equipment": [
                            {"type": EQUIPMENT_TYPE[code], "size_class": SIZES[code], "count": 1}
                        ],
                    }
                    for label in labels
                    for code in services
                ],
                "plan_assignments": [
                    {"unit_label": label, "tariff_id": str(plan.id)} for label in labels
                ],
                "create_owner_account": owner is not None,
                "owner": owner or {},
                "quote_total": None,
                "occupancy": "vacant_service_off",
                "work_orders": [],
            },
        )


def _orders(clerk, tenant, connection_id, unit_label, *, services=("battery", "solar"), gate=False):
    """One installation order per service at one unit (a gate when asked)."""
    with _ctx(tenant):
        unit = _unit(tenant, connection_id, unit_label)
        made = []
        for code in services:
            made.append(
                w6.create_work_order(
                    clerk,
                    connection_id,
                    {
                        "type": "installation",
                        "scope": work_tables.SCOPE_UNIT,
                        "unit_id": str(unit.id),
                        "service": code,
                        "is_gate": gate,
                    },
                )
            )
        return made


def _unit(tenant, connection_id, label):
    connection = work_tables.Connection.objects.get(pk=connection_id)
    return metering_models.Unit.objects.get(premises_id=connection.premises_id, label=label)


def _complete(tenant, order_ids, *, outcome=work_tables.OUTCOME_PASSED):
    with _ctx(tenant):
        work_tables.WorkOrder.objects.filter(pk__in=order_ids).update(
            state=work_tables.WO_COMPLETED, outcome=outcome
        )


def _audited(rows, action):
    return sum(1 for row in rows if row.get("action") == action)


def _rows(tenant, connection_id):
    with _ctx(tenant):
        return activation.activation_readiness(connection_id)


def _premises(tenant, connection_id):
    with _ctx(tenant):
        connection = work_tables.Connection.objects.get(pk=connection_id)
        return metering_models.Premises.objects.get(pk=connection.premises_id)


def _master(tenant, connection_id):
    with _ctx(tenant):
        connection = work_tables.Connection.objects.get(pk=connection_id)
        if connection.owner_account_id is None:
            return None
        return customers_models.Account.objects.select_related("status").get(
            pk=connection.owner_account_id
        )


# ── Q1 · the master account by premises TYPE, created PENDING ────────────────
def test_an_apartment_complex_with_one_unit_gets_a_pending_master_and_a_pending_premises(
    cedar, clerk
):
    """Haustin Towers' case: one unit typed in, an apartment complex."""
    built = _create(clerk, cedar, address="135 Haustin Way", premise_type="apartment_complex", labels=("Unit 1",))
    premises = _premises(cedar, built["id"])
    assert premises.status == "pending"
    master = _master(cedar, built["id"])
    assert master is not None and master.kind == "master"
    assert master.status.code == customers_services.PENDING_STATUS_CODE
    # `DEF-MET-9201`: the property names its master account (`BR-MET-1181`),
    # or its page reads *Master a/c: Needs an owner* beside a live account.
    assert str(premises.master_account_id) == str(master.pk)


def test_a_single_family_home_with_two_units_gets_no_master(cedar, clerk):
    """The type decides, not the count: two units on a single-family type."""
    with pytest.raises(errors.BizError) as refusal:
        _create(clerk, cedar, address="7 Wren Lane", premise_type="single_family", labels=("Unit 1", "Unit 2"))
    assert refusal.value.br_ref == "BR-CUS-1114"
    assert refusal.value.message_key == "customers.account.master_not_for_single_family"
    with _ctx(cedar):
        assert not customers_models.Account.objects.filter(kind="master").exists()
        # BR-MET-112: both or neither — the refused build left no address behind.
        assert not metering_models.Premises.objects.filter(address_line="7 Wren Lane").exists()
    built = _create(clerk, cedar, address="7 Wren Lane", premise_type="single_family", labels=("Unit 1",), owner=None)
    assert _master(cedar, built["id"]) is None
    assert _premises(cedar, built["id"]).status == "pending"


def test_an_unanswered_type_falls_back_to_counting_homes(cedar, clerk):
    """A utility's own type from before 0066 (`account_kind` NULL)."""
    with _ctx(cedar):
        metering_models.PremisesType.objects.create(
            tenant_id=cedar.id, code="townhouse_row", name="Townhouse row", is_system=False
        )
    with pytest.raises(errors.BizError) as refusal:
        _create(clerk, cedar, address="9 Row Ct", premise_type="townhouse_row", labels=("Unit 1",))
    assert refusal.value.message_key == "customers.account.master_needs_two_units"
    built = _create(clerk, cedar, address="9 Row Ct", premise_type="townhouse_row", labels=("Unit 1", "Unit 2"))
    assert _master(cedar, built["id"]) is not None


def test_the_seeded_answers_and_the_migration_mirror_agree(cedar):
    from importlib import import_module

    mirror = import_module("apps.metering.migrations.0066_cr162_premises_type_account_kind").SEEDED
    assert mirror == premises_capacity.SEED_ACCOUNT_KIND
    with _ctx(cedar):
        from apps.metering import services as metering_services

        metering_services.ensure_reference_catalogs()
        seeded = dict(
            metering_models.PremisesType.objects.filter(tenant_id=cedar.id, is_system=True)
            .values_list("code", "account_kind")
        )
    assert seeded["apartment_complex"] == "master"
    assert seeded["mixed_use"] == "master"
    assert seeded["single_family"] == "regular"


def test_a_new_premises_type_must_name_its_account_type(cedar):
    handler = metering_lookups.PremisesTypeLookupHandler()
    with _ctx(cedar):
        with pytest.raises(errors.ValidationError) as refusal:
            handler.create({"code": "duplex_court", "name": "Duplex court"})
        assert refusal.value.message_key == "metering.lookups.account_kind_required"
        with pytest.raises(errors.ValidationError):
            handler.create({"code": "duplex_court", "name": "Duplex court", "account_kind": ""})
        with pytest.raises(errors.ValidationError):
            handler.create({"code": "duplex_court", "name": "Duplex court", "account_kind": "both"})
        row = handler.create({"code": "duplex_court", "name": "Duplex court", "account_kind": "master"})
        assert handler.serialize(row)["account_kind"] == "master"
        # An edit may leave it out, never blank it.
        handler.update(row, {"name": "Duplex courts"})
        with pytest.raises(errors.ValidationError):
            handler.update(row, {"account_kind": None})
        handler.update(row, {"account_kind": "regular"})
        row.refresh_from_db()
        assert row.account_kind == "regular"
        # The unit-type list, which shares the handler, has no such field.
        unit_handler = metering_lookups.UnitTypeLookupHandler()
        made = unit_handler.create({"code": "loft", "name": "Loft"})
        assert "account_kind" not in unit_handler.serialize(made)
        with pytest.raises(errors.ValidationError):
            unit_handler.create({"code": "loft2", "name": "Loft 2", "account_kind": "master"})


def test_changing_the_type_answer_moves_only_what_is_created_afterwards(cedar, clerk):
    first = _create(clerk, cedar, address="10 Before St", premise_type="apartment_complex", labels=("Unit 1",))
    with _ctx(cedar):
        metering_models.PremisesType.objects.filter(
            tenant_id=cedar.id, code="apartment_complex"
        ).update(account_kind="regular")
    assert _master(cedar, first["id"]) is not None  # never removed retroactively
    # ⊕ **AMENDED 2026-10-02 (`DEF-CUS-9228`, PO ruling item 1: *"The owner
    # asked for the work, so the owner pays"*).** A Regular-type build with ONE
    # home and an owner used to refuse here; it now opens the OWNER's own
    # regular account on that home. The type answer still moves only what is
    # created afterwards — and the second build gets no master account.
    after = _create(clerk, cedar, address="11 After St", premise_type="apartment_complex", labels=("Unit 1",))
    owner = _master(cedar, after["id"])
    assert owner is not None and owner.kind == "regular"
    with pytest.raises(errors.BizError) as refusal:
        _create(clerk, cedar, address="12 After St", premise_type="apartment_complex", labels=("Unit 1", "Unit 2"))
    assert refusal.value.message_key == "customers.account.master_not_for_single_family"


# ── Q2 + the activation — the G Trade Tower walk ─────────────────────────────
def test_g_trade_tower_activates_what_is_ready_then_the_rest(cedar, clerk, audit_rows):
    built = _create(clerk, cedar, address="1 G Trade Tower", premise_type="apartment_complex", labels=("Unit 1", "Unit 2"))
    cid = built["id"]
    unit1 = _orders(clerk, cedar, cid, "Unit 1")
    unit2 = _orders(clerk, cedar, cid, "Unit 2")
    _complete(cedar, [o["id"] for o in unit1])

    read = _rows(cedar, cid)
    by_unit = {}
    for row in read["rows"]:
        by_unit.setdefault(row["unit_label"], []).append(row)
    assert {r["service"] for r in by_unit["Unit 1"]} == {"battery", "solar"}
    assert all(r["ready"] for r in by_unit["Unit 1"])
    assert not any(r["ready"] for r in by_unit["Unit 2"])
    assert all(r["qty"] == 1 and r["assets"][0]["status"] == "inventory" for r in read["rows"])
    assert len(read["open_orders"]) == 2 and read["orders_total"] == 4

    # The warning: open orders exist, so an unacknowledged press is refused.
    with _ctx(cedar), pytest.raises(errors.BizError) as warned:
        activation.activate(clerk, cid, service_ids=read["ready_ids"])
    assert warned.value.message_key == "metering.activation.open_orders_unacknowledged"
    assert warned.value.params["open"] == 2 and warned.value.params["total"] == 4

    # A row that is not ready is refused by name, even acknowledged.
    not_ready = by_unit["Unit 2"][0]["id"]
    with _ctx(cedar), pytest.raises(errors.BizError) as held:
        activation.activate(clerk, cid, service_ids=[not_ready], acknowledge_open_orders=True)
    assert held.value.message_key == "metering.activation.unit_orders_open"
    assert held.value.params["unit"] == "Unit 2"

    with _ctx(cedar):
        result = activation.activate(
            clerk, cid, service_ids=read["ready_ids"], acknowledge_open_orders=True
        )
    assert result["connection_state"] == work_tables.PARTLY_ACTIVATED
    assert len(result["assets_installed"]) == 2
    with _ctx(cedar):
        connection = work_tables.Connection.objects.get(pk=cid)
        assert connection.state == work_tables.PARTLY_ACTIVATED
        states = dict(
            work_tables.ConnectionService.objects.filter(connection_id=cid).values_list("id", "state")
        )
        for row in by_unit["Unit 1"]:
            assert states[UUID(row["id"])] == work_tables.SVC_ACTIVATED
        for row in by_unit["Unit 2"]:
            assert states[UUID(row["id"])] == work_tables.SVC_PENDING
        u1 = _unit(cedar, cid, "Unit 1")
        installed = asset_models.Asset.objects.filter(service_point__unit=u1).select_related("status")
        assert {a.status.code for a in installed} == {"active"}
        assert all(a.install_date is not None for a in installed)
        u2 = _unit(cedar, cid, "Unit 2")
        assert {
            a.status.code
            for a in asset_models.Asset.objects.filter(service_point__unit=u2).select_related("status")
        } == {"inventory"}
        assert _audited(audit_rows, "asset.installed") == 2
        assert _audited(audit_rows, "connection.activated") == 1
        assert _audited(audit_rows, "premises.activated") == 1
        assert _audited(audit_rows, "account.activated") == 1
    assert _premises(cedar, cid).status == "active"
    assert _master(cedar, cid).status.code == "active"
    # The messages fired on approval, and say truthfully what happened to each.
    assert result["messages"]["decided_count"] >= 1
    assert all(m["state"] in ("queued", "not_sent", "not_asked") for m in result["messages"]["messages"])

    read = _rows(cedar, cid)
    assert {r["unit_state"] for r in read["rows"] if r["unit_label"] == "Unit 1"} == {"activated"}

    # Pressing Unit 1 again writes nothing twice.
    with _ctx(cedar):
        again = activation.activate(
            clerk, cid, service_ids=[r["id"] for r in by_unit["Unit 1"]], acknowledge_open_orders=True
        )
        assert again["activated"] == [] and len(again["already_activated"]) == 2
        assert _audited(audit_rows, "asset.installed") == 2

    _complete(cedar, [o["id"] for o in unit2])
    read = _rows(cedar, cid)
    assert read["open_orders"] == []
    with _ctx(cedar):
        done = activation.activate(clerk, cid, service_ids=read["ready_ids"])
    assert done["connection_state"] == work_tables.ACTIVATED
    with _ctx(cedar):
        assert work_tables.Connection.objects.get(pk=cid).activated_at is not None


def test_a_gate_that_has_not_passed_blocks_its_unit(cedar, clerk):
    built = _create(clerk, cedar, address="2 Gate Street", premise_type="apartment_complex", labels=("Unit 1", "Unit 2"))
    cid = built["id"]
    ordinary = _orders(clerk, cedar, cid, "Unit 1")
    gate = _orders(clerk, cedar, cid, "Unit 1", services=("battery",), gate=True)
    _complete(cedar, [o["id"] for o in ordinary])
    read = _rows(cedar, cid)
    battery = next(r for r in read["rows"] if r["unit_label"] == "Unit 1" and r["service"] == "battery")
    solar = next(r for r in read["rows"] if r["unit_label"] == "Unit 1" and r["service"] == "solar")
    # The gate is the only open order on Unit 1's battery, and it holds it.
    assert battery["blocked_by_gate"] == gate[0]["order_no"]
    assert battery["ready"] is False
    with _ctx(cedar), pytest.raises(errors.BizError) as blocked:
        activation.activate(clerk, cid, service_ids=[battery["id"]], acknowledge_open_orders=True)
    assert blocked.value.message_key == "metering.activation.gate_not_passed"
    # Completed but FAILED is not passed.
    _complete(cedar, [gate[0]["id"]], outcome=work_tables.OUTCOME_FAILED)
    assert next(r for r in _rows(cedar, cid)["rows"] if r["id"] == battery["id"])["ready"] is False
    _complete(cedar, [gate[0]["id"]], outcome=work_tables.OUTCOME_PASSED)
    read = _rows(cedar, cid)
    assert {r["id"] for r in read["rows"] if r["ready"] and r["unit_label"] == "Unit 1"} == {
        battery["id"],
        solar["id"],
    }


def test_a_build_with_no_gate_order_has_nothing_that_blocks(cedar, clerk):
    built = _create(clerk, cedar, address="3 Open Road", premise_type="apartment_complex", labels=("Unit 1",))
    read = _rows(cedar, built["id"])
    assert read["orders_total"] == 0
    assert all(r["ready"] and r["blocked_by_gate"] is None for r in read["rows"])


def test_an_open_whole_build_order_warns_and_never_holds_a_unit(cedar, clerk):
    built = _create(clerk, cedar, address="4 Survey Hill", premise_type="apartment_complex", labels=("Unit 1",))
    with _ctx(cedar):
        survey = w6.create_work_order(
            clerk, built["id"], {"type": "site_survey", "scope": work_tables.SCOPE_PREMISE}
        )
    read = _rows(cedar, built["id"])
    assert all(r["ready"] for r in read["rows"])
    assert [o["order_no"] for o in read["open_orders"]] == [survey["order_no"]]


def test_a_build_on_hold_cannot_activate(cedar, clerk):
    built = _create(clerk, cedar, address="5 Paused Pl", premise_type="apartment_complex", labels=("Unit 1",))
    with _ctx(cedar):
        w6.hold_connection(clerk, built["id"], reason="permit")
        read = activation.activation_readiness(built["id"])
        assert read["can_activate"] is False
        with pytest.raises(errors.BizError) as refused:
            activation.activate(clerk, built["id"], service_ids=[read["rows"][0]["id"]])
    assert refused.value.message_key == "metering.activation.build_on_hold"


# ── Q3 + notes: the To-do tab ────────────────────────────────────────────────
def test_the_todo_tab_holds_todos_and_notes_newest_first(cedar, clerk, audit_rows):
    built = _create(clerk, cedar, address="6 Notes Ave", premise_type="apartment_complex", labels=("Unit 1",))
    cid = built["id"]
    other = staff_actor(cedar, "billing_clerk", "other@cedarfork.test")
    with _ctx(cedar):
        todo = w6.mark_outstanding(clerk, cid, title="Meter numbers")
        note = w6.mark_outstanding(clerk, cid, title="Owner prefers mornings", kind="note")
        listed = w6.todo_list(cid, viewer=clerk)
        assert [r["kind"] for r in listed["rows"]] == ["note", "todo"]
        assert listed["todos_open"] == 1 and listed["notes"] == 1
        assert listed["rows"][0]["mine"] is True
        assert w6.todo_list(cid, viewer=other)["rows"][0]["mine"] is False
        # A note never closes and never appears among the outstanding work.
        with pytest.raises(errors.BizError):
            w6.close_outstanding(clerk, note["id"])
        assert [r["title"] for r in w6.outstanding_work(cid)] == ["Meter numbers"]
        # Done, then reopened.
        w6.close_outstanding(clerk, todo["id"])
        assert w6.todo_list(cid)["todos_open"] == 0
        assert w6.reopen_outstanding(clerk, todo["id"])["reopened"] is True
        assert w6.todo_list(cid)["todos_open"] == 1
        # Only the author edits a note; nobody deletes one.
        with pytest.raises(errors.BizError) as not_mine:
            w6.update_note(other, note["id"], title="changed")
        assert not_mine.value.message_key == "metering.todo.only_the_author_edits"
        w6.update_note(clerk, note["id"], title="Owner prefers afternoons")
        assert w6.todo_list(cid)["rows"][0]["title"] == "Owner prefers afternoons"
        assert _audited(audit_rows, "connection_note.updated") == 1
        # Open to-dos are listed on the Approve warning and never block.
        read = activation.activation_readiness(cid)
        assert [t["title"] for t in read["open_todos"]] == ["Meter numbers"]
        assert all(r["ready"] for r in read["rows"])


def test_add_unit_with_its_services_reopens_an_activated_build(cedar, clerk):
    built = _create(clerk, cedar, address="8 Annex Rd", premise_type="apartment_complex", labels=("Unit 1",))
    cid = built["id"]
    with _ctx(cedar):
        ready = activation.activation_readiness(cid)["ready_ids"]
        assert activation.activate(clerk, cid, service_ids=ready)["connection_state"] == work_tables.ACTIVATED
        added = w6.add_unit_to_build(clerk, cid, {"label": "Unit 2", "services": ["battery"]})
    assert added["services"] == ["battery"]
    assert added["connection_state"] == work_tables.PARTLY_ACTIVATED
    read = _rows(cedar, cid)
    assert {(r["unit_label"], r["state"]) for r in read["rows"]} >= {("Unit 2", "pending")}


# ── Move-in before approval — RULED B: allowed, billing waits ───────────────
def _maria_moves_in(tenant, clerk, unit_id, opened):
    from tests.test_portal_request_to_active import _unit_move_in

    return _unit_move_in(
        tenant,
        clerk,
        unit_id,
        {
            "opened_at": opened,
            "account_type": "residential",
            "contact": {
                "full_name": "Maria Ortega",
                "email": "maria@example.test",
                "phone": "(512) 555-0199",
            },
            "customer": {
                "display_name": "Maria Ortega",
                "kind": "person",
                "identity": {"phone": "(512) 555-0199"},
            },
        },
    )


def test_a_move_in_before_approval_opens_and_bills_from_activation(cedar, clerk):
    """Maria moves in on 5 Oct; the unit is activated on 8 Oct. Nothing is
    charged for 5–7 Oct and the first bill runs from 8 Oct (PO, ruled B)."""
    from datetime import date, datetime, timezone as dt_timezone

    from apps.billing import gather
    from apps.customers import selectors as customers_selectors

    built = _create(clerk, cedar, address="12 Maria Way", premise_type="apartment_complex", labels=("Unit 1", "Unit 2"))
    cid = built["id"]
    with _ctx(cedar):
        unit = _unit(cedar, cid, "Unit 1")
    moved = _maria_moves_in(cedar, clerk, unit.id, "2026-10-05")
    assert moved.status_code == 201, moved.data
    # The premises and the unit stay pending until approval.
    assert _premises(cedar, cid).status == "pending"
    with _ctx(cedar):
        account = customers_models.Account.objects.get(pk=moved.data["id"])
        windows = customers_selectors.service_off_windows(account.id)
        assert [(w["off_from"], w["off_through"], w["services"]) for w in windows] == [
            (date(2026, 10, 5), None, ["battery", "solar"])
        ]
        # A bill over October before approval: no day is served.
        dark = tuple((w["off_from"], w["off_through"] or date(2026, 10, 31)) for w in windows)
        assert gather._service_days(account, date(2026, 10, 1), date(2026, 10, 31), 31, dark) == 0
        # The cancel warning lists Maria's account; nothing is closed.
        listed = activation.accounts_on_build_units(cid)
        assert [row["account_no"] for row in listed] == [account.account_no]

    # The unit is activated on 8 Oct.
    with _ctx(cedar):
        ready = [r["id"] for r in activation.activation_readiness(cid)["rows"] if r["unit_label"] == "Unit 1"]
        activation.activate(clerk, cid, service_ids=ready)
        stamped = datetime(2026, 10, 8, 15, 0, tzinfo=dt_timezone.utc)
        work_tables.ConnectionService.objects.filter(pk__in=ready).update(activated_at=stamped)
        windows = customers_selectors.service_off_windows(account.id)
        assert [(w["off_from"], w["off_through"]) for w in windows] == [
            (date(2026, 10, 5), date(2026, 10, 7))
        ]
        dark = tuple((w["off_from"], w["off_through"]) for w in windows)
        # 31-day October, opened 5 Oct: served 8–31 Oct = 24 days, not 27.
        assert gather._service_days(account, date(2026, 10, 1), date(2026, 10, 31), 31, dark) == 24


def test_an_account_on_a_unit_no_build_touched_has_no_activation_window(cedar, clerk):
    from apps.customers import selectors as customers_selectors
    from tests.test_portal_request_to_active import _served_premises

    with _ctx(cedar):
        premises, units, _ = _served_premises(clerk, cedar, address="14 Old Road", postal_code="78701")
    moved = _maria_moves_in(cedar, clerk, units[0]["id"], "2026-10-05")
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        assert customers_selectors.service_off_windows(moved.data["id"]) == ()


def test_cancelling_a_build_with_an_account_open_lists_it_and_closes_nothing(cedar, clerk):
    built = _create(clerk, cedar, address="15 Cancel Ct", premise_type="apartment_complex", labels=("Unit 1",))
    cid = built["id"]
    with _ctx(cedar):
        unit = _unit(cedar, cid, "Unit 1")
    moved = _maria_moves_in(cedar, clerk, unit.id, "2026-10-05")
    assert moved.status_code == 201, moved.data
    with _ctx(cedar):
        result = w6.cancel_connection(clerk, cid, reason="owner withdrew")
        assert [row["account_no"] for row in result["accounts_to_close"]] == [moved.data["account_no"]]
        account = customers_models.Account.objects.select_related("status").get(pk=moved.data["id"])
        assert account.closed_at is None and account.status.code == "active"


def test_the_unit_type_chosen_at_create_reaches_the_units_tab(cedar, clerk):
    """Item 36: the commit dropped the wizard's unit type, so the Units tab's
    *Unit type* column was empty on every build."""
    built = _create(
        clerk, cedar, address="16 Typed Row", premise_type="apartment_complex",
        labels=("Unit 1",), unit_type="residential",
    )
    read = _rows(cedar, built["id"])
    assert {r["unit_type"] for r in read["rows"]} == {"residential"}
    with pytest.raises(errors.ValidationError):
        _create(
            clerk, cedar, address="17 Typed Row", premise_type="apartment_complex",
            labels=("Unit 1",), unit_type="spaceship",
        )

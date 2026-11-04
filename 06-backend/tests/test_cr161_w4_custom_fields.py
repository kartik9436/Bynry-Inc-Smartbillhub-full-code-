# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 wave W4 — customers, work orders, readings, routes and
#           areas carry the utility's own fields
# Rules:    BR-TEN-046 (as amended 2026-10-02) · BR-TEN-048 (never a charge;
#           readings *"Never used in the bill calculation"*) · BR-TEN-052
#           (required only where typed in) · CLAUDE.md hard rules 1 and 8 ·
#           hard-won law 14 (the PostgreSQL cases)
# ───────────────────────────────────────────────────────
"""W4's guards, one per sentence of the PO's Part 2 rows 2 and 10–13.

| Record type | Typed in (Input) on | Shown read-only on |
|---|---|---|
| Customer | New Account wizard · Customer edit (New Connection Step 1 waits) | Account detail header |
| Work orders | New work order · Edit work order | Work order detail |
| Readings | Manual reading entry · Reading import (column mapping) | Reading detail |
| Routes | Add / edit route | Route page |
| Areas | Add / edit area | the Areas list (there is no Area page) |

Each record type is proved the same five ways: the answer is stored and served;
an edit MERGES; a required field binds only on the screen it is typed in; an
unknown key is refused and nothing is written; a utility with no fields is
unchanged. Isolation and the database defaults are proved on PostgreSQL.
"""

from __future__ import annotations

import pytest
from django.db import connection

from apps.customers import customer_edit
from apps.customers import selectors as customers_selectors
from apps.work import connection_models as work_tables
from apps.metering import models as metering_models
from apps.metering import read_import
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from apps.tenancy import custom_fields as cf_law
from apps.tenancy import models as tenancy_models
from apps.tenancy import selectors as tenancy_selectors
from apps.tenancy import services as tenancy_services
from apps.work import dispatch as work_dispatch
from apps.work import edit as work_edit
from apps.work import services as work_services
from core import errors
from tests.isolation_helpers import requires_postgres, rls, rls_probe_role  # noqa: F401 — fixtures
from tests.test_br_cus_1054_customer_edit import _customer_row, _open, _person
from tests.test_cr038_w5_bulk_and_quick import _planned_meter
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx
from tests.test_us_met_reads_helpers import commit_read, seed_config

pytestmark = pytest.mark.django_db

W4_ENTITIES = ("customers", "work_orders", "meter_reads", "routes", "areas")


def _field(actor, entity, placement, *, label="Seal number", required=False, **extra):
    field = tenancy_services.create_custom_field(
        actor,
        {"label": label, "entity": entity, "data_type": "text", "is_required": required, **extra},
    )
    tenancy_services.save_custom_field_placement(actor, field["id"], placement)
    return field


def _field_errors(exc) -> list[str]:
    return [item["field"] for item in exc.value.field_errors]


# ══════════════════════════════════════════════════════════════════════════
# 0 · the slot list
# ══════════════════════════════════════════════════════════════════════════
def test_w4__the_five_record_types_are_addressable():
    for entity in W4_ENTITIES:
        assert entity in cf_law.ENTITIES, entity
        assert entity in tenancy_models.CUSTOM_FIELD_ENTITIES, entity


def test_w4__each_record_type_offers_the_pos_screens_and_no_invented_page():
    declared = {
        entity: {(s.key, s.screen, s.modes, s.rendered) for s in cf_law.declared_slots(entity)}
        for entity in W4_ENTITIES
    }
    assert declared == {
        "customers": {
            ("S18", "new_account_customer", ("input",), True),
            # `CR-164-BRC10` wave 2 — rendered on New Connection Step 1 now.
            ("NEW_CONNECTION_OWNER", "new_connection_owner", ("input",), True),
            ("CUSTOMER_EDIT", "customer_edit", ("input",), True),
            ("S21", "account_header_customer", ("view",), True),
            # ⚠ `DEF-TEN-9246` (2026-10-03): W6 (`d8d753d76`) put the
            # customer's fields on Staff New Request and Request detail, and
            # W7 (`16bc09376`) rendered the portal's new-service form — three
            # real screens this pin did not know about, so it read red on a
            # correct product from 2026-10-02 22:19.
            ("REQUEST_NEW", "staff_new_request", ("input",), True),
            ("REQUEST_DETAIL", "request_detail", ("view",), True),
            ("PORTAL_NEW_SERVICE", "portal_new_service", ("input",), True),
        },
        "work_orders": {
            ("WORK_NEW", "new_work_order", ("input",), True),
            ("WORK_EDIT", "edit_work_order", ("input",), True),
            ("WORK_DETAIL", "work_order_detail", ("view",), True),
        },
        "meter_reads": {
            ("READ_ENTRY", "manual_reading", ("input",), True),
            ("S29", "reading_detail", ("view",), True),
        },
        "routes": {
            ("ROUTE_FORM", "route_form", ("input",), True),
            ("ROUTE_PAGE", "route_page", ("view",), True),
        },
        "areas": {
            ("AREA_FORM", "area_form", ("input",), True),
            ("AREA_LIST", "areas_list", ("view",), True),
        },
    }
    # *"do not invent pages"* — there is no Customer page and no Area page.
    screens = {s.screen for s in cf_law.SLOTS}
    assert "customer_page" not in screens and "area_page" not in screens


def test_w4__readings_are_import_fed_and_offered():
    assert "meter_reads" in cf_law.IMPORT_FED_ENTITIES
    offered = {row["entity"]: row["offered"] for row in cf_law.slot_catalogue()}
    for entity in W4_ENTITIES:
        assert offered[entity] is True, entity


# ══════════════════════════════════════════════════════════════════════════
# 1 · Routes — Add / edit route · Route page
# ══════════════════════════════════════════════════════════════════════════
def test_w4_routes__typed_on_the_wizard_and_served_on_the_route_page(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "routes", {"ROUTE_FORM": "input", "ROUTE_PAGE": "view"}, label="Patrol day")
        route = metering_services.create_route(
            dana, {"code": "RT-CF", "name": "North walk", "custom_data": {"patrol_day": "Tuesday"}}
        )
        assert route["custom_data"] == {"patrol_day": "Tuesday"}
        assert metering_selectors.route_detail(route["id"])["custom_data"] == {"patrol_day": "Tuesday"}
        assert metering_models.Route.objects.get(pk=route["id"]).custom_data == {"patrol_day": "Tuesday"}


def test_w4_routes__an_edit_merges_and_a_blank_clears(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "routes", {"ROUTE_FORM": "input"}, label="Patrol day")
        _field(dana, "routes", {"ROUTE_FORM": "input"}, label="Gate key")
        route = metering_services.create_route(
            dana,
            {"code": "RT-CF2", "custom_data": {"patrol_day": "Tuesday", "gate_key": "K-7"}},
        )
        edited = metering_services.update_route(
            dana, route["id"], {"custom_data": {"patrol_day": "Friday"}}
        )
        assert edited["custom_data"] == {"patrol_day": "Friday", "gate_key": "K-7"}
        cleared = metering_services.update_route(
            dana, route["id"], {"custom_data": {"gate_key": ""}}
        )
        assert cleared["custom_data"] == {"patrol_day": "Friday"}


def test_w4_routes__required_binds_on_the_wizard_only(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "routes", {"ROUTE_FORM": "input"}, label="Patrol day", required=True)
        before = metering_models.Route.objects.count()
        with pytest.raises(errors.ValidationError) as refused:
            metering_services.create_route(dana, {"code": "RT-CF3", "custom_data": {}})
        assert _field_errors(refused) == ["custom_data.patrol_day"]
        assert metering_models.Route.objects.count() == before, "a refusal writes nothing"
        # A door that draws no fields (the seeder, the sample data) is not bound.
        plain = metering_services.create_route(dana, {"code": "RT-CF4"})
        assert plain["custom_data"] == {}


def test_w4_routes__an_unknown_key_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as refused:
            metering_services.create_route(dana, {"code": "RT-CF5", "custom_data": {"nope": "x"}})
        assert _field_errors(refused) == ["custom_data.nope"]
        assert not metering_models.Route.objects.filter(code="RT-CF5").exists()


# ══════════════════════════════════════════════════════════════════════════
# 2 · Areas — Add / edit area · the Areas list column
# ══════════════════════════════════════════════════════════════════════════
def test_w4_areas__typed_on_the_dialog_and_served_on_the_list(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "areas", {"AREA_FORM": "input", "AREA_LIST": "view"}, label="Patrol day")
        created = tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "CF-N", "name": "North", "custom_data": {"patrol_day": "Tuesday"}}
        )
        assert created["custom_data"] == {"patrol_day": "Tuesday"}
        edited = tenancy_services.update_lookup_entry(
            dana, "areas", created["id"], {"custom_data": {"patrol_day": "Monday"}}
        )
        assert edited["custom_data"] == {"patrol_day": "Monday"}
        assert tenancy_models.Area.objects.get(pk=created["id"]).custom_data == {"patrol_day": "Monday"}


def test_w4_areas__required_binds_on_the_dialog_and_never_on_the_seeder(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "areas", {"AREA_FORM": "input"}, label="Patrol day", required=True)
        with pytest.raises(errors.ValidationError) as refused:
            tenancy_services.create_lookup_entry(
                dana, "areas", {"code": "CF-S", "name": "South", "custom_data": {}}
            )
        assert _field_errors(refused) == ["custom_data.patrol_day"]
        assert not tenancy_models.Area.objects.filter(code="CF-S").exists()
        plain = tenancy_services.create_lookup_entry(dana, "areas", {"code": "CF-E", "name": "East"})
        assert plain["custom_data"] == {}


# ══════════════════════════════════════════════════════════════════════════
# 3 · Work orders — New work order · Edit work order · Work order detail
# ══════════════════════════════════════════════════════════════════════════
def _premises(actor):
    return make_premises(actor, address_line="12 Seal Ct", services_available=["water"])


def test_w4_work_orders__typed_on_new_and_served_on_detail(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "work_orders", {"WORK_NEW": "input", "WORK_DETAIL": "view"}, label="Crew radio")
        premises = _premises(dana)
        raised = work_services.raise_work_order(
            dana,
            {"premises_id": premises["id"], "type": "leak", "custom_data": {"crew_radio": "Ch 4"}},
        )
        assert work_tables.WorkOrder.objects.get(pk=raised["id"]).custom_data == {"crew_radio": "Ch 4"}
        assert work_dispatch.order_row(raised["id"])["custom_data"] == {"crew_radio": "Ch 4"}


def test_w4_work_orders__required_binds_on_new_only_and_burns_no_number(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "work_orders", {"WORK_NEW": "input"}, label="Crew radio", required=True)
        premises = _premises(dana)
        before = work_tables.WorkOrder.objects.count()
        with pytest.raises(errors.ValidationError) as refused:
            work_services.raise_work_order(
                dana, {"premises_id": premises["id"], "type": "leak", "custom_data": {}}
            )
        assert _field_errors(refused) == ["custom_data.crew_radio"]
        assert work_tables.WorkOrder.objects.count() == before
        # The build commit, the flows and the rules engine send no fields.
        other_door = work_services.raise_work_order(
            dana, {"premises_id": premises["id"], "type": "leak"}
        )
        assert work_tables.WorkOrder.objects.get(pk=other_door["id"]).custom_data == {}


def test_w4_work_orders__the_edit_merges_and_audits_one_row(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        _field(dana, "work_orders", {"WORK_NEW": "input", "WORK_EDIT": "input"}, label="Crew radio")
        _field(dana, "work_orders", {"WORK_NEW": "input"}, label="Gate key")
        premises = _premises(dana)
        raised = work_services.raise_work_order(
            dana,
            {
                "premises_id": premises["id"],
                "type": "leak",
                "custom_data": {"crew_radio": "Ch 4", "gate_key": "K-7"},
            },
        )
        assert work_edit.form_values(raised["id"])["custom_data"] == {
            "crew_radio": "Ch 4",
            "gate_key": "K-7",
        }
        changed = lambda: [r for r in audit_rows if r["action"] == "work.order.field_changed"]  # noqa: E731
        before = len(changed())
        saved = work_edit.save_order_edit(dana, raised["id"], {"custom_data": {"crew_radio": "Ch 9"}})
        assert saved["changed"] == ["custom_data"]
        assert len(changed()) == before + 1
        # The Gate key typed on New work order is not on the edit form, and is kept.
        assert work_tables.WorkOrder.objects.get(pk=raised["id"]).custom_data == {
            "crew_radio": "Ch 9",
            "gate_key": "K-7",
        }
        unchanged = work_edit.save_order_edit(
            dana, raised["id"], {"custom_data": {"crew_radio": "Ch 9"}}
        )
        assert unchanged["changed"] == [], "a Save that moved nothing writes nothing"


# ══════════════════════════════════════════════════════════════════════════
# 4 · Readings — Manual reading entry · Reading import · Reading detail
# ══════════════════════════════════════════════════════════════════════════
def _post_manual(actor, asset_no, day, value, **row_extra):
    batch = metering_services.stage_read_batch(
        actor,
        {
            "source_kind": "manual",
            "period_month": f"{day[:7]}-01",
            "rows": [
                {"meter_id": asset_no, "read_date": day, "reading": value, "channel": "total", **row_extra}
            ],
        },
    )
    metering_services.validate_read_batch(actor, batch["id"])
    return batch, metering_services.commit_read_batch(actor, batch["id"], {"certified": True})


def _head(asset_id, day):
    from datetime import date

    return metering_models.MeterRead.objects.get(
        asset_id=asset_id, read_at__date=date.fromisoformat(day), superseded_by_id__isnull=True
    )


def test_w4_readings__typed_on_the_manual_entry_and_served_on_the_detail(brazos, marcus, dana):
    with tenant_ctx(brazos):
        seed_config()
        _field(dana, "meter_reads", {"READ_ENTRY": "input", "S29": "view"})
        meter = _planned_meter(marcus, brazos, asset_no="M-CF1")
        commit_read(marcus, meter["id"], day="2026-06-05", value=1000, consumption="300.000000")
        batch, posted = _post_manual(
            marcus, "M-CF1", "2026-07-05", "1284", custom_data={"seal_number": "S-2207"}
        )
        assert posted["posted_reads"] == 1, posted
        staged = metering_models.ReadImportRow.objects.get(batch_id=batch["id"])
        assert staged.custom_data == {"seal_number": "S-2207"}
        read = _head(meter["id"], "2026-07-05")
        assert read.custom_data == {"seal_number": "S-2207"}
        assert metering_selectors.read_dict(read)["custom_data"] == {"seal_number": "S-2207"}


def test_w4_readings__the_answer_never_moves_the_consumption(brazos, marcus, dana):
    """Part 2 row 11: *"Never used in the bill calculation"*. Two meters, the
    same history and the same reading; one carries an answer. The quantity a
    bill is computed from is identical to the sixth decimal."""
    with tenant_ctx(brazos):
        seed_config()
        _field(dana, "meter_reads", {"READ_ENTRY": "input"})
        plain = _planned_meter(marcus, brazos, asset_no="M-CF2")
        tagged = _planned_meter(marcus, brazos, asset_no="M-CF3")
        for meter in (plain, tagged):
            commit_read(marcus, meter["id"], day="2026-06-05", value=1000, consumption="300.000000")
        _post_manual(marcus, "M-CF2", "2026-07-05", "1284", custom_data={})
        _post_manual(marcus, "M-CF3", "2026-07-05", "1284", custom_data={"seal_number": "S-1"})
        a, b = _head(plain["id"], "2026-07-05"), _head(tagged["id"], "2026-07-05")
        assert (a.consumption, a.unit, a.status) == (b.consumption, b.unit, b.status)
        assert a.consumption is not None


def test_w4_readings__required_binds_on_the_manual_entry_and_stages_nothing(brazos, marcus, dana):
    with tenant_ctx(brazos):
        seed_config()
        _field(dana, "meter_reads", {"READ_ENTRY": "input"}, required=True)
        _planned_meter(marcus, brazos, asset_no="M-CF4")
        before = metering_models.ReadImportBatch.objects.count()
        with pytest.raises(errors.ValidationError) as refused:
            metering_services.stage_read_batch(
                marcus,
                {
                    "source_kind": "manual",
                    "period_month": "2026-07-01",
                    "rows": [
                        {"meter_id": "M-CF4", "read_date": "2026-07-05", "reading": "10", "custom_data": {}}
                    ],
                },
            )
        assert _field_errors(refused) == ["custom_data.seal_number"]
        assert metering_models.ReadImportBatch.objects.count() == before
        # The S28 manual grid draws no fields and is not bound by them.
        grid = metering_services.stage_read_batch(
            marcus,
            {
                "source_kind": "manual",
                "period_month": "2026-07-01",
                "rows": [{"meter_id": "M-CF4", "read_date": "2026-07-05", "reading": "10"}],
            },
        )
        assert grid["status"] == "staged"


def _upload(actor, content):
    return metering_services.stage_read_batch(
        actor,
        {
            "source_kind": "csv",
            "source_detail": "walk_by",
            "period_month": "2026-07-01",
            "file_name": "cf4_reads.csv",
            "file_content": content,
        },
    )


def test_w4_readings__the_import_maps_a_column_by_label_and_posts_it(brazos, marcus, dana):
    with tenant_ctx(brazos):
        seed_config()
        _field(dana, "meter_reads", {"S29": "view"})  # view-only: the import fills it
        meter = _planned_meter(marcus, brazos, asset_no="M-CF5")
        commit_read(marcus, meter["id"], day="2026-06-05", value=1000, consumption="300.000000")
        batch = _upload(
            marcus,
            "meter_id,read_date,reading,channel,Seal Number\nM-CF5,2026-07-05,1284,total,S-2207\n",
        )
        assert batch["mapping"]["custom_data.seal_number"] == "Seal Number"
        metering_services.validate_read_batch(marcus, batch["id"])
        posted = metering_services.commit_read_batch(marcus, batch["id"], {"certified": True})
        assert posted["posted_reads"] == 1, posted
        assert _head(meter["id"], "2026-07-05").custom_data == {"seal_number": "S-2207"}


def test_w4_readings__a_refused_cell_is_a_row_error_not_a_refused_file(brazos, marcus, dana):
    with tenant_ctx(brazos):
        seed_config()
        tenancy_services.create_custom_field(
            dana,
            {
                "label": "Seal colour",
                "entity": "meter_reads",
                "data_type": "select",
                "options": ["Red", "Blue"],
            },
        )
        _planned_meter(marcus, brazos, asset_no="M-CF6")
        _planned_meter(marcus, brazos, asset_no="M-CF7")
        batch = _upload(
            marcus,
            "meter_id,read_date,reading,seal_colour\n"
            "M-CF6,2026-07-05,10,Green\n"
            "M-CF7,2026-07-05,11,Red\n",
        )
        rows = {
            row.meter_no_raw: row
            for row in metering_models.ReadImportRow.objects.filter(batch_id=batch["id"])
        }
        assert rows["M-CF6"].severity == "error"
        assert rows["M-CF6"].custom_data == {}
        codes = [o["detail"]["code"] for o in rows["M-CF6"].rule_outcomes if o["rule"] == "parse"]
        assert codes == [metering_services.ERR_CUSTOM_FIELD]
        assert rows["M-CF7"].custom_data == {"seal_colour": "Red"}
        assert rows["M-CF7"].severity == "ok"


def test_w4_readings__the_template_gains_a_column_only_when_a_field_exists(brazos, dana):
    published = read_import.template_csv()
    with tenant_ctx(brazos):
        assert read_import.with_custom_columns(published, []) == published
        _field(dana, "meter_reads", {"READ_ENTRY": "input"})
        from apps.metering import seams as metering_seams

        body = read_import.with_custom_columns(
            published, metering_seams.custom_field_import_columns("meter_reads")
        )
    header, *rows = body.strip("\n").split("\n")
    assert header == published.split("\n")[0] + ",seal_number"
    assert all(row.endswith(",") for row in rows)


def test_w4_readings__a_utility_with_no_fields_maps_nothing_extra(brazos, marcus):
    with tenant_ctx(brazos):
        seed_config()
        _planned_meter(marcus, brazos, asset_no="M-CF8")
        batch = _upload(marcus, "meter_id,read_date,reading,Seal Number\nM-CF8,2026-07-05,10,S-1\n")
        assert not any(key.startswith("custom_data.") for key in batch["mapping"])
        row = metering_models.ReadImportRow.objects.get(batch_id=batch["id"])
        assert row.custom_data == {} and row.severity == "ok"


# ══════════════════════════════════════════════════════════════════════════
# 5 · Customers — New Account wizard · Customer edit · Account detail header
# ══════════════════════════════════════════════════════════════════════════
def test_w4_customers__typed_on_new_account_and_served_on_the_account_header(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "customers", {"S18": "input", "S21": "view"}, label="Preferred language")
        opened = _open(
            dana,
            brazos,
            label="Unit CF1",
            customer={**_person(), "custom_data": {"preferred_language": "Spanish"}},
        )
        customer = _customer_row(opened)
        assert customer.custom_data == {"preferred_language": "Spanish"}
        header = customers_selectors.customer_for_account(opened["id"])
        assert header["custom_data"] == {"preferred_language": "Spanish"}


def test_w4_customers__required_binds_on_new_account_only(brazos, dana):
    with tenant_ctx(brazos):
        _field(dana, "customers", {"S18": "input"}, label="Preferred language", required=True)
        with pytest.raises(errors.ValidationError) as refused:
            _open(dana, brazos, label="Unit CF2", customer={**_person(), "custom_data": {}})
        assert "custom_data.preferred_language" in _field_errors(refused)
        # A door that draws no customer fields (an import, the master door) is not bound.
        opened = _open(dana, brazos, label="Unit CF3", customer=_person(name="Ng, Lee"))
        assert _customer_row(opened).custom_data == {}


def test_w4_customers__the_edit_merges_and_is_audited(brazos, dana, audit_rows):
    with tenant_ctx(brazos):
        _field(dana, "customers", {"S18": "input", "CUSTOMER_EDIT": "input"}, label="Preferred language")
        _field(dana, "customers", {"S18": "input"}, label="Loyalty tier")
        opened = _open(
            dana,
            brazos,
            label="Unit CF4",
            customer={
                **_person(),
                "custom_data": {"preferred_language": "Spanish", "loyalty_tier": "Gold"},
            },
        )
        customer = _customer_row(opened)
        assert customers_selectors.customer_detail(customer.pk)["custom_data"] == {
            "preferred_language": "Spanish",
            "loyalty_tier": "Gold",
        }
        updated = lambda: [r for r in audit_rows if r["action"] == "customer.updated"]  # noqa: E731
        before = len(updated())
        customer_edit.update_customer(
            dana, str(customer.pk), {"custom_data": {"preferred_language": "French"}}
        )
        customer.refresh_from_db()
        assert customer.custom_data == {"preferred_language": "French", "loyalty_tier": "Gold"}
        rows = updated()
        assert len(rows) == before + 1
        assert rows[-1]["after"]["custom_data"]["preferred_language"] == "French"


def test_w4_customers__required_binds_on_customer_edit(brazos, dana):
    with tenant_ctx(brazos):
        opened = _open(dana, brazos, label="Unit CF5", customer=_person(name="Ito, Ken"))
        _field(dana, "customers", {"CUSTOMER_EDIT": "input"}, label="Preferred language", required=True)
        customer = _customer_row(opened)
        with pytest.raises(errors.ValidationError) as refused:
            customer_edit.update_customer(dana, str(customer.pk), {"custom_data": {}})
        assert _field_errors(refused) == ["custom_data.preferred_language"]
        # An edit that does not open the custom section (a phone fix) is not bound.
        customer_edit.update_customer(dana, str(customer.pk), {"phone": "512-555-0100"})


# ══════════════════════════════════════════════════════════════════════════
# 6 · one utility only, and the zero-field utility
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.isolation
def test_w4__another_utility_sees_no_definition(brazos, lonestar, dana):
    with tenant_ctx(brazos):
        _field(dana, "routes", {"ROUTE_FORM": "input"}, label="Patrol day")
        _field(dana, "areas", {"AREA_FORM": "input"}, label="Patrol day")
        _field(dana, "work_orders", {"WORK_NEW": "input"}, label="Crew radio")
        _field(dana, "meter_reads", {"READ_ENTRY": "input"})
        _field(dana, "customers", {"S18": "input"}, label="Preferred language")
    with tenant_ctx(lonestar):
        for entity in W4_ENTITIES:
            assert tenancy_selectors.custom_field_registry(entity) == [], entity


def test_w4__a_utility_with_no_fields_writes_empty_answers_everywhere(brazos, dana, marcus):
    with tenant_ctx(brazos):
        route = metering_services.create_route(dana, {"code": "RT-Z", "custom_data": {}})
        area = tenancy_services.create_lookup_entry(
            dana, "areas", {"code": "Z-A", "name": "Zed", "custom_data": {}}
        )
        order = work_services.raise_work_order(
            dana, {"premises_id": _premises(dana)["id"], "type": "leak", "custom_data": {}}
        )
        opened = _open(dana, brazos, label="Unit Z", customer={**_person(name="Zed, Ann"), "custom_data": {}})
    assert route["custom_data"] == {} and area["custom_data"] == {}
    assert work_tables.WorkOrder.objects.get(pk=order["id"]).custom_data == {}
    assert _customer_row(opened).custom_data == {}


# ══════════════════════════════════════════════════════════════════════════
# 7 · PostgreSQL — the columns, their defaults and RLS (law 14)
# ══════════════════════════════════════════════════════════════════════════
@requires_postgres
@pytest.mark.parametrize(
    # `customers.custom_data` is r17.2's column (`customers/0004`), not this
    # wave's, and carries no database default — W4 adds no migration there.
    "table", ["areas", "routes", "work_orders", "read_import_rows", "meter_reads"]
)
def test_w4__each_column_is_not_null_and_defaults_to_an_empty_object(table):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT column_default, is_nullable FROM information_schema.columns "
            "WHERE table_name = %s AND column_name = 'custom_data'",
            [table],
        )
        default, nullable = cursor.fetchone()
    assert nullable == "NO"
    assert default is not None and default.startswith("'{}'::jsonb")


@requires_postgres
def test_w4__the_check_admits_the_five_and_refuses_an_invoice(brazos):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = 'ck_custom_field_entity'"
        )
        definition = cursor.fetchone()[0]
    for entity in W4_ENTITIES:
        assert f"'{entity}'" in definition, entity
    assert "'invoices'" not in definition


@requires_postgres
@pytest.mark.isolation
def test_w4__rls_hides_a_routes_answers_from_another_utility(brazos, lonestar, dana, rls):
    with tenant_ctx(brazos):
        _field(dana, "routes", {"ROUTE_FORM": "input"}, label="Patrol day")
        route = metering_services.create_route(
            dana, {"code": "RT-RLS", "custom_data": {"patrol_day": "Tuesday"}}
        )
    sql = "SELECT count(*) FROM routes WHERE custom_data ->> 'patrol_day' = 'Tuesday' AND id = %s"
    with rls.under(brazos):
        assert rls.scalar(sql, [route["id"]]) == 1
    with rls.under(lonestar):
        assert rls.scalar(sql, [route["id"]]) == 0

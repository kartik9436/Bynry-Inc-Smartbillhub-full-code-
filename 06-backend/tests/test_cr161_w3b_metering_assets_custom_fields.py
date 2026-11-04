# ── Trace ──────────────────────────────────────────────
# Change:   CR-161-BRC10 waves W2 + W3, lane CF-W3b — tenant custom fields on
#           premises, units, service points and assets, every input route
# Defects:  DEF-MET-9226 (premises) · DEF-MET-9227 (units) · DEF-MET-9173
#           (service points) · DEF-AST-9171 (assets) · DEF-MET-9172 (the
#           premises/units import wrote custom cells unchecked, and a required
#           field refused the whole mapping)
# Rules:    BR-TEN-052 as amended 2026-10-02 (required binds only where typed
#           in; an import is not a screen) · BR-TEN-048 · US-SHL-015/016 ·
#           CLAUDE.md hard rule 1 (one utility only) and hard-won law 14
# ───────────────────────────────────────────────────────
"""Every door a premises, unit, service point or asset is written through now
validates `custom_data` with tenancy's ONE validator, naming its screen:

* Add Premises (`S16`, both `POST /premises` and the City's door) — the
  premises, the FIRST unit and that unit's service points;
* New Connection Step 2 (`NEW_CONNECTION_PREMISE`);
* Edit premise (`PREMISE_EDIT`), Edit unit (`UNIT_EDIT`), Edit asset
  (`ASSET_EDIT`) — merged into the stored answers;
* Add units (`UNIT_ADD`, the pattern generator) and Add asset (`S51`);
* every import (`None`) — so a required field never blocks one, while a bad
  cell is still judged by the field's own rules.

The PostgreSQL proof of the import path (law 14) is the same file run under
`config.settings.local`; see the lane report.
"""

import pytest

from apps.assets import models as asset_models
from apps.assets import selectors as asset_selectors
from apps.assets import services as asset_services
from apps.metering import connections, importers, import_runs, models, selectors, services
from apps.tenancy import models as tenancy_models
from apps.tenancy import services as tenancy_services
from core import errors
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    dana,
    lonestar,
    make_asset,
    make_premises,
    make_unit,
    marcus,
    owner_for,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _field(actor, **over):
    payload = {"label": "Roof Material", "entity": "premises", "data_type": "text"}
    payload.update(over)
    return tenancy_services.create_custom_field(actor, payload)


def _place(actor, field, placement):
    return tenancy_services.save_custom_field_placement(actor, field["id"], placement)


def _roof(actor, *, required=False, placement=None):
    roof = _field(
        actor,
        data_type="select",
        options=["Metal", "Tile", "Shingle"],
        is_required=required,
    )
    _place(actor, roof, placement or {"S16": "input", "PREMISE_EDIT": "input", "PREMISE_PAGE": "view"})
    return roof


def _premises_payload(actor, **over):
    payload = {
        "address_line": "77 Roofline Dr",
        "city": "Katy",
        "state": "TX",
        "postal_code": "77494",
        "services_available": ["electric", "water"],
        "owner_id": owner_for(actor),
    }
    payload.update(over)
    return payload


# ── 1 · premises (DEF-MET-9226) ─────────────────────────────────────────────
def test_def_met_9168__add_premises_saves_the_answer_and_the_page_serves_it(brazos, dana):
    """The reproduction: `POST /premises {custom_data: {roof_material: Metal}}`
    answered 422 `metering.unknown_field`."""
    with tenant_ctx(brazos):
        _roof(dana)
        created = services.create_premises(
            dana,
            _premises_payload(dana, custom_data={"roof_material": "Metal"}),
            custom_fields_screen="S16",
        )
        detail = selectors.premises_detail(created["id"])
    assert created["custom_data"] == {"roof_material": "Metal"}
    assert detail["custom_data"] == {"roof_material": "Metal"}


def test_def_met_9168__a_wrong_option_is_refused_by_the_one_validator(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana)
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                dana,
                _premises_payload(dana, custom_data={"roof_material": "Purple"}),
                custom_fields_screen="S16",
            )
    assert caught.value.field_errors[0]["field"] == "custom_data.roof_material"
    assert caught.value.field_errors[0]["message_key"] == "customFields.option_unknown"


def test_def_met_9168__required_binds_on_add_premises_only(brazos, dana):
    """Required means required where it is typed in: Add Premises (S16) is
    refused without it; the same create through an import (`None`) and through
    New Connection (where it is not placed) is not."""
    with tenant_ctx(brazos):
        _roof(dana, required=True, placement={"S16": "input"})
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                dana, _premises_payload(dana, custom_data={}), custom_fields_screen="S16"
            )
        imported = services.create_premises(dana, _premises_payload(dana, address_line="1 Import Way"))
        connected = services.create_premises(
            dana,
            _premises_payload(dana, address_line="2 Connect Way"),
            custom_fields_screen="NEW_CONNECTION_PREMISE",
        )
    assert caught.value.field_errors[0]["field"] == "custom_data.roof_material"
    assert caught.value.field_errors[0]["message_key"] == "customFields.required"
    assert imported["custom_data"] == {} and connected["custom_data"] == {}


def test_def_met_9168__edit_premise_merges_clears_and_counts_a_stored_answer(brazos, dana):
    with tenant_ctx(brazos):
        _roof(dana, required=True, placement={"S16": "input", "PREMISE_EDIT": "input"})
        storeys = _field(dana, label="Storeys", data_type="number")
        _place(dana, storeys, {"S16": "input", "PREMISE_EDIT": "input"})
        created = services.create_premises(
            dana,
            _premises_payload(dana, custom_data={"roof_material": "Metal", "storeys": "2"}),
            custom_fields_screen="S16",
        )
        # A changed answer only — the required Roof Material counts as answered.
        edited = services.update_premises(
            dana, created["id"], {"custom_data": {"storeys": "3"}}, custom_fields_screen="PREMISE_EDIT"
        )
        cleared = services.update_premises(
            dana, created["id"], {"custom_data": {"storeys": None}}, custom_fields_screen="PREMISE_EDIT"
        )
        # A form that does not send custom_data (the owner link, the GIS run)
        # leaves the answers untouched.
        untouched = services.update_premises(dana, created["id"], {"city": "Fulshear"})
    assert edited["custom_data"] == {"roof_material": "Metal", "storeys": "3"}
    assert cleared["custom_data"] == {"roof_material": "Metal"}
    assert untouched["custom_data"] == {"roof_material": "Metal"}


def test_def_met_9168__new_connection_carries_the_answer_through_its_door(brazos, dana):
    """The door translates its block key by key and refuses an unknown one, so
    `custom_data` has to be NAMED in it — and the create runs with step 2's
    screen."""
    assert connections.PREMISES_BLOCK_FIELDS["custom_data"] == "custom_data"
    translated = connections._premises_block_in_the_doors_language(
        {"address": "5 Door St", "custom_data": {"roof_material": "Tile"}}
    )
    assert translated["custom_data"] == {"roof_material": "Tile"}
    with tenant_ctx(brazos):
        _roof(dana, required=True, placement={"NEW_CONNECTION_PREMISE": "input"})
        with pytest.raises(errors.ValidationError) as caught:
            connections._premises_made_for_the_wizard(dana, _premises_payload(dana))  # noqa: SLF001
    assert caught.value.field_errors[0]["field"] == "custom_data.roof_material"
    # …and the refusal still says which step to go back to.
    assert caught.value.params["step"] == connections.STEP_OF_THE_PREMISE


# ── 2 · units and service points (DEF-MET-9227, DEF-MET-9173) ───────────────
def _unit_fields(actor, *, required_point=False):
    gate = _field(actor, label="Gate code", entity="units")
    _place(actor, gate, {"S16": "input", "UNIT_ADD": "input", "UNIT_EDIT": "input", "PREMISE_UNITS": "view"})
    valve = _field(actor, label="Valve location", entity="service_points", is_required=required_point)
    _place(actor, valve, {"S16": "input", "UNIT_ADD": "input", "PREMISE_UNITS": "view"})


def test_def_met_9169_9173__the_first_unit_and_its_service_points_keep_their_answers(brazos, dana):
    with tenant_ctx(brazos):
        _unit_fields(dana)
        created = services.create_premises(
            dana,
            _premises_payload(
                dana,
                units=[
                    {
                        "label": "1",
                        "custom_data": {"gate_code": "4471"},
                        "service_point_custom_data": {"water": {"valve_location": "Front curb"}},
                    },
                    {"label": "2"},
                ],
            ),
            custom_fields_screen="S16",
        )
        detail = selectors.premises_detail(created["id"])
    rows = {row["label"]: row for row in detail["unit_rows"]}
    assert rows["1"]["custom_data"] == {"gate_code": "4471"}
    assert rows["1"]["service_point_custom_data"] == {"water": {"valve_location": "Front curb"}}
    assert rows["2"]["custom_data"] == {} and rows["2"]["service_point_custom_data"] == {}


def test_def_met_9173__a_required_service_point_field_binds_on_the_first_unit_only(brazos, dana):
    """The second unit is created with no screen (the form drew no box for it),
    so a required valve location is asked of the first unit's points alone."""
    with tenant_ctx(brazos):
        _unit_fields(dana, required_point=True)
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                dana,
                _premises_payload(dana, units=[{"label": "1"}, {"label": "2"}]),
                custom_fields_screen="S16",
            )
        ok = services.create_premises(
            dana,
            _premises_payload(
                dana,
                address_line="9 Valve Rd",
                units=[
                    {
                        "label": "1",
                        "service_point_custom_data": {
                            "water": {"valve_location": "Curb"},
                            "electric": {"valve_location": "Pole"},
                        },
                    },
                    {"label": "2"},
                ],
            ),
            custom_fields_screen="S16",
        )
    assert caught.value.field_errors[0]["field"] == "custom_data.valve_location"
    assert len(ok["units"]) == 2


def test_def_met_9173__an_answer_for_a_service_the_unit_does_not_take_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        _unit_fields(dana)
        premises = make_premises(dana, services_available=["water"])
        with pytest.raises(errors.ValidationError) as caught:
            services.create_unit(
                dana,
                {
                    "premises_id": premises["id"],
                    "label": "Stray",
                    "service_point_custom_data": {"electric": {"valve_location": "Pole"}},
                },
                custom_fields_screen="UNIT_ADD",
            )
    assert caught.value.field_errors[0]["field"] == "service_point_custom_data.electric"
    assert caught.value.field_errors[0]["message_key"] == "metering.unit.service_not_taken"


def test_def_met_9169__edit_unit_merges_and_a_service_point_answer_is_not_editable_there(
    brazos, dana
):
    with tenant_ctx(brazos):
        _unit_fields(dana)
        premises = make_premises(dana)
        unit = make_unit(dana, premises["id"], custom_data={"gate_code": "1111"})
        edited = services.update_unit(
            dana, unit["id"], {"custom_data": {"gate_code": "2222"}}, custom_fields_screen="UNIT_EDIT"
        )
        with pytest.raises(errors.ValidationError) as caught:
            services.update_unit(
                dana,
                unit["id"],
                {"service_point_custom_data": {"water": {"valve_location": "x"}}},
                custom_fields_screen="UNIT_EDIT",
            )
    assert unit["custom_data"] == {"gate_code": "1111"}
    assert edited["custom_data"] == {"gate_code": "2222"}
    assert caught.value.field_errors[0]["field"] == "service_point_custom_data"


def test_def_met_9169__add_units_writes_the_answers_onto_every_unit_it_makes(brazos, dana):
    """The Add units wizard is the pattern generator: one set of answers,
    validated ONCE at the review (a wrong option is refused there, before any
    row is staged), then carried onto every generated unit as `UNIT_ADD`."""
    with tenant_ctx(brazos):
        _unit_fields(dana)
        premises = make_premises(dana, services_available=["water"])
        pattern = {
            "premises_id": premises["id"],
            "floors": 1,
            "units_per_floor": 2,
            "label_pattern": "Flat {seq}",
            "custom_data": {"gate_code": "9090"},
            "service_point_custom_data": {"water": {"valve_location": "Basement"}},
        }
        request = {"kind": "units_pattern", "pattern": pattern, "options": {}}
        staged = importers.stage(request)
        result = importers.commit(dana, request, staged)
        units = models.Unit.objects.filter(premises_id=premises["id"]).order_by("label")
        points = models.ServicePoint.objects.filter(unit__in=units)
    assert result["summary"] == {"created": 2, "failed": 0}
    assert [unit.custom_data for unit in units] == [{"gate_code": "9090"}] * 2
    assert [point.custom_data for point in points] == [{"valve_location": "Basement"}] * 2


def test_def_met_9169__add_units_refuses_a_blank_required_field_at_the_review(brazos, dana):
    with tenant_ctx(brazos):
        gate = _field(dana, label="Gate code", entity="units", is_required=True)
        _place(dana, gate, {"UNIT_ADD": "input"})
        premises = make_premises(dana)
        with pytest.raises(errors.ValidationError) as caught:
            importers.stage(
                {
                    "kind": "units_pattern",
                    "pattern": {
                        "premises_id": premises["id"],
                        "floors": 1,
                        "units_per_floor": 1,
                        "label_pattern": "Flat {seq}",
                    },
                }
            )
    assert caught.value.field_errors[0]["field"] == "custom_data.gate_code"


# ── 3 · assets (DEF-AST-9171) ───────────────────────────────────────────────
def test_def_ast_9171__add_and_edit_asset_save_merge_and_serve_the_answers(brazos, dana):
    with tenant_ctx(brazos):
        warranty = _field(dana, label="Warranty provider", entity="assets")
        _place(dana, warranty, {"S51": "input", "ASSET_EDIT": "input", "S50": "view", "S49": "view"})
        bay = _field(dana, label="Bay", entity="assets")
        _place(dana, bay, {"S51": "input", "ASSET_EDIT": "input"})
        created = asset_services.create_asset(
            dana,
            {
                "type": "meter",
                "service": "electric",
                "unit": "kWh",
                "custom_data": {"warranty_provider": "Acme", "bay": "3"},
            },
            custom_fields_screen="S51",
        )
        edited = asset_services.update_asset(
            dana, created["id"], {"custom_data": {"bay": "4"}}, custom_fields_screen="ASSET_EDIT"
        )
        # A panel edit that sends no custom_data leaves them alone.
        panel = asset_services.update_asset(dana, created["id"], {"location_note": "Shed"})
        row = asset_selectors.asset_dict(asset_models.Asset.objects.get(pk=created["id"]))
    assert created["custom_data"] == {"warranty_provider": "Acme", "bay": "3"}
    assert edited["custom_data"] == {"warranty_provider": "Acme", "bay": "4"}
    assert panel["custom_data"] == {"warranty_provider": "Acme", "bay": "4"}
    assert row["custom_data"] == {"warranty_provider": "Acme", "bay": "4"}


def test_def_ast_9171__required_binds_on_add_asset_and_not_on_the_seed_door(brazos, dana):
    with tenant_ctx(brazos):
        warranty = _field(dana, label="Warranty provider", entity="assets", is_required=True)
        _place(dana, warranty, {"S51": "input"})
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.create_asset(
                dana,
                {"type": "meter", "service": "electric", "unit": "kWh"},
                custom_fields_screen="S51",
            )
        seeded = make_asset(dana, asset_no="M-5101")
    assert caught.value.field_errors[0]["field"] == "custom_data.warranty_provider"
    assert seeded["custom_data"] == {}


# ── 4 · imports (DEF-MET-9172, DEF-AST-9171) ────────────────────────────────
ROOF_CSV = (
    "ADDR1,CITY,ROOF\n"
    "10 Import Ave,Katy,Metal\n"
    "11 Import Ave,Katy,Purple\n"
    "12 Import Ave,Katy,\n"
)
ROOF_MAPPING = {"ADDR1": "address_line", "CITY": "city", "ROOF": "custom_data.roof_material"}
ROW_HANDLING = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}


def _premises_run(actor, content, mapping):
    run = import_runs.extract(
        actor,
        {"target": "premises", "source_kind": "file", "file_name": "roof.csv", "content": content},
    )
    import_runs.transform(actor, run["id"], {"mapping": mapping, "row_handling": ROW_HANDLING})
    return run["id"]


def test_def_met_9172__a_custom_cell_is_judged_by_the_fields_own_rules(brazos, dana):
    """Until this fix the three rows staged as Metal, Purple and nothing, and
    Purple loaded. Now Purple is the row's parse problem, in the field's own
    words, and Metal is stored exactly as the option is spelled."""
    with tenant_ctx(brazos):
        _roof(dana, required=True)
        run_id = _premises_run(dana, ROOF_CSV, ROOF_MAPPING)
        rows = {
            row.raw.get("ADDR1"): row
            for row in models.ImportRunRow.objects.filter(run_id=run_id)
        }
    assert rows["10 Import Ave"].mapped["custom_data"] == {"roof_material": "Metal"}
    assert import_runs.PARSE_PROBLEMS not in rows["10 Import Ave"].mapped
    problem = rows["11 Import Ave"].mapped[import_runs.PARSE_PROBLEMS]["parse"]["problem"]
    assert problem == "Purple is not one of the choices for Roof Material."
    # A blank cell is not in the blob — and the REQUIRED field never blocked it.
    assert "custom_data" not in rows["12 Import Ave"].mapped


def test_def_met_9172__a_required_field_never_blocks_a_file_without_its_column(brazos, dana):
    """`required` on a custom column refused the whole mapping as
    `required_column_unmapped`. An import is not a screen."""
    with tenant_ctx(brazos):
        _roof(dana, required=True)
        columns = {c["target"]: c for c in import_runs.target_columns("premises")}
        run_id = _premises_run(
            dana, "ADDR1,CITY\n20 Plain St,Katy\n", {"ADDR1": "address_line", "CITY": "city"}
        )
    assert columns["custom_data.roof_material"]["required"] is False
    assert models.ImportRunRow.objects.filter(run_id=run_id).count() == 1


def test_def_ast_9171__every_asset_sheet_offers_one_column_per_assets_field(brazos, dana):
    with tenant_ctx(brazos):
        warranty = _field(dana, label="Warranty provider", entity="assets")
        _place(dana, warranty, {"S51": "input"})
        offered = {
            target: {c["target"] for c in import_runs.target_columns(target)}
            for target in import_runs.ASSETS_TARGETS
        }
        payload = import_runs._asset_payload_from(  # noqa: SLF001 — the one builder
            "assets_meters", {"custom_data": {"warranty_provider": "Acme"}, "service": "electric"}
        )
    for target, columns in offered.items():
        assert "custom_data.warranty_provider" in columns, target
    assert payload["custom_data"] == {"warranty_provider": "Acme"}


def test_def_ast_9171__an_import_row_merges_into_an_assets_stored_answers(brazos, dana):
    """`update_from_import` — the file's column is ADDED to the answers a clerk
    typed, never a replacement of them, and no screen's required field binds."""
    with tenant_ctx(brazos):
        warranty = _field(dana, label="Warranty provider", entity="assets", is_required=True)
        bay = _field(dana, label="Bay", entity="assets")
        _place(dana, warranty, {"S51": "input"})
        _place(dana, bay, {"S51": "input"})
        created = make_asset(dana, asset_no="M-5102", custom_data={"bay": "7"})
        asset_services.update_from_import(
            dana, "M-5102", {"custom_data": {"warranty_provider": "Acme"}}
        )
        stored = asset_models.Asset.objects.get(pk=created["id"]).custom_data
    assert stored == {"bay": "7", "warranty_provider": "Acme"}


# ── 5 · one utility only; a tenant with no fields is unchanged ──────────────
def test_cr161_w3b_isolation__another_utilitys_field_is_unknown_here(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        _roof(dana)
    erin = staff_actor(lonestar, "system_admin", "erin.w3b@lsrwater.test")  # noqa: F405
    with tenant_ctx(lonestar):
        with pytest.raises(errors.ValidationError) as caught:
            services.create_premises(
                erin,
                _premises_payload(
                    erin, services_available=["water"], custom_data={"roof_material": "Metal"}
                ),
                custom_fields_screen="S16",
            )
        assert (
            tenancy_models.CustomField.objects.filter(
                tenant_id=lonestar.id, key="roof_material"
            ).count()
            == 0
        )
    assert caught.value.field_errors[0]["message_key"] == "customFields.unknown_key"


def test_cr161_w3b_zero_fields__every_door_writes_what_it_always_did(brazos, dana):
    with tenant_ctx(brazos):
        premises = services.create_premises(
            dana, _premises_payload(dana, units=[{"label": "A"}]), custom_fields_screen="S16"
        )
        unit = models.Unit.objects.get(premises_id=premises["id"])
        points = list(models.ServicePoint.objects.filter(unit=unit))
    assert premises["custom_data"] == {}
    assert unit.custom_data == {}
    assert points and all(point.custom_data == {} for point in points)

# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 4, lane PARTS — Work › Parts redrawn (images
#           35–42; rulings 29, 32, 33).
# Defects:  DEF-WRK-9579 (a part cannot be switched off) · DEF-WRK-9580 (the
#           register has no filters) · DEF-WRK-9587 (the parts import drops the
#           category) · DEF-WRK-9588 (the parts import speaks about something
#           else: blank samples, a description rule, a premises fix, a blank
#           Key) · DEF-521 (stage 2's sample column is empty on every target)
# Rules:    BR-WRK-019 · NFR-3 / NFR-5 (filters applied in SQL before paging,
#           no cap) · CLAUDE.md hard rule 2 (the cost stays a 4-dp string) ·
#           hard-won law 14 (the row-writing half re-run on PostgreSQL)
# ───────────────────────────────────────────────────────
"""The Parts register and its import, as round 4 of CR-168 left them.

Every case here was run RED against the tree before its fix (hard-won law 7);
the red text is quoted in the CR-168 §16 record. The import cases drive the
real runner — extract, transform, validate, dry run, load — with the file the
round-1 walk used (`08-qa/work-2026-10-04/parts-import-walk.csv`), because the
category defect was invisible to every test that stopped at Validate.
"""

from __future__ import annotations

import pytest

from apps.metering import import_runs
from apps.work import models as work_models
from apps.work import selectors as work_selectors
from apps.work import services as work_services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx
from tests.test_cr023_import_stages import ALL_ON

pytestmark = pytest.mark.django_db

#: The round-1 walk's file, byte for byte (`parts-import-walk.csv`).
WALK_FILE = (
    "part_no,name,category,unit,unit_cost\n"
    'MTR-W34,"Water meter 3/4"" positive displacement",Meters,each,118.00\n'
    "GSKT-STD,Standard meter gasket,Consumables,each,1.10\n"
    "SEAL-01,Tamper seal,Consumables,each,0.40\n"
    'MTR-W58,"Water meter 5/8"" positive displacement",Meters,each,92.40\n'
    "TAPE-XL,PTFE tape extra long,Consumables,,3.10\n"
)
MAPPING = {
    "part_no": "part_no",
    "name": "name",
    "category": "category",
    "unit": "unit_of_measure",
    "unit_cost": "unit_cost",
}


def _add(part_no, name, cost, *, category=None, unit="each"):
    payload = {"part_no": part_no, "name": name, "unit_of_measure": unit, "unit_cost": cost}
    if category is not None:
        payload["category"] = category
    return work_services.create_part(None, payload)


def _extract(actor, content=WALK_FILE):
    return import_runs.extract(
        actor,
        {
            "target": "parts",
            "source_kind": "file",
            "file_name": "parts-import-walk.csv",
            "content": content,
        },
    )


def _to_validated(actor, content=WALK_FILE):
    run = _extract(actor, content)
    import_runs.transform(actor, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
    return run["id"], import_runs.validate(actor, run["id"], "insert")


def _rejects(run_id):
    from apps.metering import models as metering_models

    return {r["row_no"]: r for r in import_runs.rejects(metering_models.ImportRun.objects.get(pk=run_id))}


# ═══ DEF-WRK-9587 · the import keeps the category ═══════════════════════════


def test_def_wrk_9587_the_load_keeps_the_category_named_in_the_file(brazos, dana):
    """Round 1 measured it on a real file: *Meters* in the cell, `category`
    null on MTR-W34 after the load. The cell is resolved by NAME."""
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000", category="Meters")
        run_id, _checked = _to_validated(dana)
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        loaded = {
            p.part_no: (p.category.name if p.category_id else None)
            for p in work_models.Part.objects.filter(tenant=brazos).select_related("category")
        }
    assert loaded.get("MTR-W34") == "Meters", loaded
    assert loaded.get("GSKT-STD") == "Consumables", loaded
    assert loaded.get("SEAL-01") == "Consumables", loaded


def test_def_wrk_9587_a_category_named_by_its_code_loads_too(brazos, dana):
    """The writer resolves name-then-code, so the import must carry either."""
    with tenant_ctx(brazos):
        meters = work_models.PartCategory.objects.get(tenant=brazos, name="Meters")
        content = (
            "part_no,name,category,unit,unit_cost\n"
            f"MTR-X1,Water meter 1 inch,{meters.code.upper()},each,140.00\n"
        )
        run_id, _checked = _to_validated(dana, content)
        import_runs.load(dana, run_id, {"write_mode": "insert", "approved": True})
        part = work_models.Part.objects.select_related("category").get(tenant=brazos, part_no="MTR-X1")
    assert part.category is not None and part.category.name == "Meters"


def test_def_wrk_9587_validate_no_longer_warns_the_category_is_blank(brazos, dana):
    """Stage 3 said *Category — mapped from category, and blank in all 5 rows*
    over a file whose every row names one."""
    with tenant_ctx(brazos):
        run = _extract(dana)
        shaped = import_runs.transform(dana, run["id"], {"mapping": MAPPING, "row_handling": ALL_ON})
    empty = (shaped.get("mapping_spec") or {}).get("empty_columns") or []
    assert not any("category" in str(entry) for entry in empty), empty


def test_def_wrk_9587_an_unknown_category_is_rejected_at_validate_not_loaded_blank(brazos, dana):
    """With the lookup resolving, an unknown cell must not quietly become a
    part with no category — the stage-3 rule judges the operator's own cell."""
    content = "part_no,name,category,unit,unit_cost\nVLV-9,Gate valve,Valves,each,40.00\n"
    with tenant_ctx(brazos):
        run_id, checked = _to_validated(dana, content)
        rejects = _rejects(run_id)
    hits = {rule["code"]: rule["hits"] for rule in checked["rules"]}
    assert hits["PRT.CATEGORY_IN_LOOKUP"] == 1
    assert rejects[1]["problem"] == "Valves is not one of your parts categories."


def test_the_dry_run_writes_nothing(brazos, dana):
    """Stage 4's rehearsal: *Will create 3* and not one row on the register."""
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000", category="Meters")
        run_id, _checked = _to_validated(dana)
        before = work_models.Part.objects.filter(tenant=brazos).count()
        rehearsed = import_runs.dry_run(dana, run_id, "insert")
        after = work_models.Part.objects.filter(tenant=brazos).count()
    assert before == after == 1
    assert rehearsed["will_create"] == 3, rehearsed


# ═══ DEF-WRK-9588 · the import speaks about parts ═══════════════════════════


def test_def_wrk_9588_stage_two_shows_a_sample_value_per_column(brazos, dana):
    """DEF-521 on every target, and the drawing's MTR-W34 on this one."""
    with tenant_ctx(brazos):
        run = _extract(dana)
    assert run.get("samples") == {
        "part_no": "MTR-W34",
        "name": 'Water meter 3/4" positive displacement',
        "category": "Meters",
        "unit": "each",
        "unit_cost": "118.00",
    }


def test_def_wrk_9588_the_name_rule_says_name(brazos, dana):
    """Ruling 32 — the part has a Name; the rule read *description*."""
    with tenant_ctx(brazos):
        _run_id, checked = _to_validated(dana)
    sentences = {rule["code"]: rule["sentence"] for rule in checked["rules"]}
    assert sentences["PRT.NAME_REQUIRED"] == "Every part needs a name."


def test_def_wrk_9588_a_row_with_no_unit_is_told_how_to_fix_it_and_carries_its_key(brazos, dana):
    """Image 42: row 5 · TAPE-XL · *This row has no unit.* · *Add how it is
    counted — each, ft, roll.* — never *…on every premises.*"""
    with tenant_ctx(brazos):
        run_id, _checked = _to_validated(dana)
        rejects = _rejects(run_id)
    assert rejects[5]["source_key"] == "TAPE-XL"
    assert rejects[5]["problem"] == "This row has no unit."
    assert rejects[5]["fix_hint"] == "Add how it is counted — each, ft, roll."


def test_def_wrk_9588_a_part_on_file_names_its_key_and_the_drawn_fix(brazos, dana):
    """Image 42: row 4 · MTR-W58 · *Import it as Insert & update. Or take the
    row out.* — a part number comes off the file, never from numbering."""
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000", category="Meters")
        run_id, _checked = _to_validated(dana)
        rejects = _rejects(run_id)
    assert rejects[4]["source_key"] == "MTR-W58"
    assert rejects[4]["problem"] == "MTR-W58 is already on file."
    assert rejects[4]["fix_hint"] == "Import it as Insert & update. Or take the row out."


# ═══ DEF-WRK-9579 · a part is switched off and on ═══════════════════════════


def test_def_wrk_9579_a_part_is_retired_and_brought_back(brazos):
    with tenant_ctx(brazos):
        row = _add("SEAL-01", "Tamper seal", "0.4000", category="Consumables")
        off = work_services.update_part(None, row["id"], {"active": False})
        on = work_services.update_part(None, row["id"], {"active": True})
    assert off["active"] is False
    assert on["active"] is True


def test_def_wrk_9579_active_must_be_a_yes_or_no(brazos):
    from core import errors

    with tenant_ctx(brazos):
        row = _add("SEAL-01", "Tamper seal", "0.4000")
        with pytest.raises(errors.ValidationError):
            work_services.update_part(None, row["id"], {"active": "maybe"})


def test_def_wrk_9579_an_edit_changes_the_name_and_the_cost(brazos):
    with tenant_ctx(brazos):
        row = _add("SEAL-01", "Tamper seal", "0.4000")
        edited = work_services.update_part(
            None, row["id"], {"name": "Tamper seal, wire", "unit_cost": "0.4500"}
        )
    assert (edited["name"], edited["unit_cost"]) == ("Tamper seal, wire", "0.4500")


# ═══ DEF-WRK-9580 · the register filters, in SQL, before paging ═════════════


def test_def_wrk_9580_the_register_filters_by_category_unit_and_status(brazos):
    with tenant_ctx(brazos):
        meters = work_models.PartCategory.objects.get(tenant=brazos, name="Meters")
        _add("MTR-W58", 'Water meter 5/8"', "92.4000", category="Meters")
        _add("PIPE-CU34", 'Copper pipe 3/4"', "3.1500", category="Fittings", unit="ft")
        seal = _add("SEAL-01", "Tamper seal", "0.4000", category="Consumables")
        work_services.update_part(None, seal["id"], {"active": False})

        by_category = work_selectors.parts_page(category=meters.code)
        by_unit = work_selectors.parts_page(unit="ft")
        inactive = work_selectors.parts_page(status="inactive")
        active = work_selectors.parts_page(status="active")
    assert [r["part_no"] for r in by_category["rows"]] == ["MTR-W58"]
    assert [r["part_no"] for r in by_unit["rows"]] == ["PIPE-CU34"]
    assert [r["part_no"] for r in inactive["rows"]] == ["SEAL-01"]
    assert active["total"] == 2
    with tenant_ctx(brazos):
        both = work_selectors.parts_page(category=f"{meters.code},fittings")
        none = work_selectors.parts_page(category="none")
    assert sorted(r["part_no"] for r in both["rows"]) == ["MTR-W58", "PIPE-CU34"]
    assert none["total"] == 0


def test_def_wrk_9580_the_filter_counts_before_it_pages(brazos):
    """NFR-3: the total is the filtered set's, not the page's."""
    with tenant_ctx(brazos):
        # 52 fittings and a meter: the smallest page is 50, so page 2 of the
        # filtered set holds exactly the last two — and the total is 52, not 53.
        for index in range(1, 53):
            _add(f"FT-{index:02d}", f"Fitting {index}", "1.0000", category="Fittings")
        _add("MTR-W58", 'Water meter 5/8"', "92.4000", category="Meters")
        fittings = work_models.PartCategory.objects.get(tenant=brazos, name="Fittings")
        page = work_selectors.parts_page(category=fittings.code, page=2, per=50)
    assert page["total"] == 52
    assert [r["part_no"] for r in page["rows"]] == ["FT-51", "FT-52"]


def test_def_wrk_9580_the_unit_choices_are_the_registers_own(brazos):
    with tenant_ctx(brazos):
        _add("MTR-W58", 'Water meter 5/8"', "92.4000")
        _add("PIPE-CU34", 'Copper pipe 3/4"', "3.1500", unit="ft")
        _add("TAPE-PTFE", "PTFE thread tape", "2.2000", unit="roll")
        units = work_selectors.part_units()
    assert units == ["each", "ft", "roll"]

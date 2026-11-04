# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-1900 — NO HUMAN-FACING SURFACE CAN RECORD A CONNECTION SIZE.
#          BR-AST-500's column landed 2026-08-27 with an API writer and NO
#          CONTROL AND NO IMPORT COLUMN, so a real utility could type a
#          per-size rate ladder and never tell the product which rung any of
#          its meters sits on. CLOSED here (the backend half; the two screen
#          halves are proved in 07-frontend/src/features/assets/*.test.tsx).
# Ruling:  PO 2026-08-28, verbatim *"Please do both"* — a size column on the
#          meters import target AND a size control on the asset screens.
#          12-governance/02-decision-log.md, "THE CONNECTION SIZE GETS BOTH
#          DOORS", which also records the four judgments this file asserts.
# Rules:   BR-MET-530 (the meters import carries the size, through the five
#          stages, and REFUSES an unknown code at stage 3) · BR-AST-530 (the
#          asset screens offer the tenant's ratified list) · BR-AST-500 (the
#          column; NULL is a real answer and is never defaulted) ·
#          BR-AST-501 (the size is billing-affecting) · BR-TEN-170/171 (the
#          forty ratified codes) · BR-TEN-078 (the list is NOT service-scoped)
#          · CR-025 (the sample is header + ONE WORKED ROW) · DEF-616 (the
#          shipped sample must survive its own import)
# Tests:   this file
# Impacts: apps/metering/import_runs.py (_assets_meter_columns with_size ·
#          _ASSETS_METER_ALIASES · LOOKUP_INDEX_BUILDERS · _asset_payload_from
#          · sample_csv) · apps/metering/import_rules.py
#          (AST.SIZE_CLASS_IN_LOOKUP + _eval_size_class_in_lookup) ·
#          apps/metering/seams.py · apps/tenancy/selectors.py
# ───────────────────────────────────────────────────────
"""The two doors, measured on a utility that is not ours.

**WHAT WAS ACTUALLY WRONG, IN ONE SENTENCE.** The product could store a
connection size and no person could put one there. `assets.services` accepted
`size_class` on create and on update, `assets_on_unit` published it, `gather`
read it, and the only caller able to set it was a programmer with an API
client — so a utility loading 1,847 meters loaded 1,847 meters with the field
NULL, and `rating.selectors.pricing_inputs` priced every one of them off the
NULL "every size" tier group.

**THE FIGURE, AND IT IS NOT THIS LANE'S — IT IS THE METERING LANE'S OWN WORKED
CASE, QUOTED IN BR-AST-501.** A 2" water connection re-tagged from `W-58` to
`W-2` moves the ladder from `3.20 / 4.80 / 7.20` to `3.45 / 5.10 / 7.70`. On
1,847 meters that is every bill on the tenant, in the direction nobody checks.

RED-FIRST PROOF (r11 step 2d), taken in a clean `git worktree` pinned to the
branch base `db84bc6`, BEFORE this lane's change — each case run against the
tree as it stood:

  TC-1 · the meters template's own header row, downloaded on Ottumwa Water
  Works and printed in full:

      asset_no,serial_no,meter_type,service,read_method,multiplier,unit_ref,
      manufacturer,model,install_date,certification_due,warranty_end,supplier,
      purchase_cost,external_ref

  Fifteen columns and no size among them. `'size_class' in header` → False.

  TC-4 · a file naming `W-99`, driven through all five stages:

      VALIDATE: {'in': 1, 'forward': 1, 'checked': 1, 'clean': 1, 'errors': 0}
      DRY RUN:  {'will_create': 1, 'rejected': 0}

  A clean rehearsal, because the column did not exist and the cell was
  therefore an UNMAPPED extra header the run ignored in silence. That is the
  outcome judgment 3 of the ruling names by hand: *"a silently-blank size is
  what produced the every-size ladder in the first place"*.

⚠ **WHAT THIS FILE DELIBERATELY DOES NOT DO.** It does not widen the boundary
to sub-meters or devices (ruling judgment 4 — `DEF-1901`'s call), and TC-6
asserts that boundary rather than assuming it. It does not touch
`apps/rating/**` or `apps/billing/resolution*.py`. And it never invents a size:
every code it names is read out of `apps.tenancy.service_size_classes`, the
PO-ratified list, so a case here cannot teach a reader a code that does not
exist.
"""

from __future__ import annotations

import csv
import io

import pytest

from apps.metering import import_rules, import_runs
from apps.tenancy import service_size_classes

from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    ALL_OFF,
    _cells,
    _drive,
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

#: BR-TEN-171's ratified water codes, read from the vocabulary rather than
#: typed here — the discipline `test_def_1900_connection_size.py` states at its
#: own constant: the PRODUCT's vocabulary is the tenancy list, and a test that
#: retypes a code can go green against a list that no longer holds it.
WATER_CODES = [code for code, _name in service_size_classes.size_classes_for_service("water")]
WATER_5_8 = WATER_CODES[0]  # `W-58`
#: A code of the RIGHT SHAPE that the ratified list does not hold — the typo
#: judgment 1 exists to catch. Asserted absent so this constant cannot rot into
#: a real code the day somebody ratifies a ninth water size.
UNKNOWN_SIZE = "W-99"
assert UNKNOWN_SIZE not in WATER_CODES


def _meters_file(header: list[str], rows: list[list[str]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


# ══════════════════════════════════════════════════════════════════════════
# TC-1..3 — DOOR ONE: THE COLUMN IS ON THE FILE, AND IT ROUND-TRIPS
# ══════════════════════════════════════════════════════════════════════════


def test_TC1_the_meters_template_offers_a_connection_size_column(ottumwa, ottumwa_admin):
    """The header a first-time operator downloads names the size.

    This is the whole of DEF-1900's import half stated as one assertion: before
    today the fifteen columns quoted in this file's docstring did not include
    one, so the ONLY way to record a size was an API client.
    """
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        header = list(_cells("assets_meters"))
        assert "size_class" in header, header


def test_TC2_the_sample_cell_is_a_size_THIS_TENANT_HAS_for_the_service_it_names(
    ottumwa, ottumwa_admin
):
    """CR-025's worked row, and `DEF-963`'s lesson applied one column along.

    A literal `W-58` would be a template the product's own import rejects on a
    utility that does not sell water — exactly what the hardcoded `electric`
    service cell did. The cell is the intersection of two facts the tenant
    already stated: the sizes BR-TEN-171 ratified for the service the row
    names, and the rows this tenant actually has active.
    """
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        cells = _cells("assets_meters")
        service, size = cells["service"], cells["size_class"]
        ratified = [code for code, _name in service_size_classes.size_classes_for_service(service)]
        assert size in ratified, (service, size, ratified)


def test_TC3_the_shipped_meters_sample_still_survives_its_own_import(ottumwa, ottumwa_admin):
    """`DEF-616`'s property, re-proved with the new column on the file.

    DEF-616 is an OPEN row about a sample that stopped round-tripping through
    its own import the moment a column was added to the offered set and not to
    the file. This lane adds a column to BOTH — the sample IS the offered set
    (`sample_csv` builds its header from `target_columns`) — and this case is
    what refuses the other outcome.
    """
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        _filename, body = import_runs.sample_csv("assets_meters")
        run, checked, problems, figures = _drive(ottumwa_admin, "assets_meters", body)
        assert checked["counts"]["errors"] == 0, problems
        assert figures["will_create"] == 1, figures
        receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
        assert receipt["counts"]["created"] == 1, receipt["counts"]


# ══════════════════════════════════════════════════════════════════════════
# TC-4..5 — THE TWO ANSWERS AN OPERATOR CAN GIVE, AND THEY DIFFER
# ══════════════════════════════════════════════════════════════════════════


def test_TC4_an_unknown_size_is_REFUSED_at_stage_3_with_its_own_reason(ottumwa, ottumwa_admin):
    """Ruling judgment 3: refused at VALIDATE, not silently dropped at LOAD.

    ⚠ **THE SENTENCE MATTERS AS MUCH AS THE REJECTION.** An operator who is
    told *"W-99 is not a connection size on this tenant's list"* knows what to
    fix; a row that loads with the field unset bills off the every-size rung
    and tells nobody.
    """
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        cells = _cells("assets_meters")
        header = list(cells)
        good = [cells[name] for name in header]
        bad = list(good)
        bad[header.index("size_class")] = UNKNOWN_SIZE
        bad[header.index("unit_ref")] = units[0][1]["unit_no"]
        _run, checked, problems, figures = _drive(
            ottumwa_admin, "assets_meters", _meters_file(header, [bad])
        )
        assert checked["counts"]["errors"] == 1, (checked["counts"], problems)
        assert figures["will_create"] == 0, figures
        assert any(UNKNOWN_SIZE in (problem or "") for _row_no, problem in problems), problems


def test_TC5_a_BLANK_size_stays_lawful_and_loads(ottumwa, ottumwa_admin):
    """Ruling judgment 2, and it is the case the whole ruling exists to serve.

    A utility mid-migration legitimately does not know every size yet. A
    REQUIRED column would refuse the very 1,847-meter load this door was built
    for, so a blank cell must load — and must load with the column NULL rather
    than with a default nobody chose (BR-AST-500).
    """
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        cells = _cells("assets_meters")
        header = list(cells)
        row = [cells[name] for name in header]
        row[header.index("size_class")] = ""
        row[header.index("unit_ref")] = units[0][1]["unit_no"]
        run, checked, problems, figures = _drive(
            ottumwa_admin, "assets_meters", _meters_file(header, [row])
        )
        assert checked["counts"]["errors"] == 0, problems
        receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
        assert receipt["counts"]["created"] == 1, receipt["counts"]


def test_TC6_a_named_size_REACHES_THE_COLUMN_on_the_loaded_meter(ottumwa, ottumwa_admin):
    """The end of the rail: EXTRACT → TRANSFORM → VALIDATE → LOAD → the row.

    ⚠ **THIS IS THE ASSERTION DEF-1900's ESCAPE REASON SAYS NOBODY MADE.** The
    existing DEF-514 cases write through `assets.services.update_asset` — the
    API's own function — so they prove the CAPABILITY and cannot prove the
    SURFACE. This one starts from a CSV a person could have typed.
    """
    from apps.assets import selectors as asset_selectors

    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        cells = _cells("assets_meters")
        header = list(cells)
        row = [cells[name] for name in header]
        row[header.index("size_class")] = WATER_5_8
        row[header.index("service")] = "water"
        row[header.index("unit_ref")] = units[0][1]["unit_no"]
        run, checked, problems, _figures = _drive(
            ottumwa_admin, "assets_meters", _meters_file(header, [row])
        )
        assert checked["counts"]["errors"] == 0, problems
        receipt = import_runs.load(ottumwa_admin, run["id"], {"write_mode": "insert"})
        assert receipt["counts"]["created"] == 1, receipt["counts"]
        loaded = [
            asset
            for asset in asset_selectors.assets_on_unit(units[0][1]["id"])
            if asset.get("size_class") == WATER_5_8
        ]
        assert loaded, "the size the file named did not reach the column"


# ══════════════════════════════════════════════════════════════════════════
# TC-7..8 — THE BOUNDARY THE RULING DREW, ASSERTED RATHER THAN ASSUMED
# ══════════════════════════════════════════════════════════════════════════


def test_TC7_sub_meters_and_devices_do_NOT_get_the_column(ottumwa, ottumwa_admin):
    """Ruling judgment 4, verbatim: *"Sub-meters and devices are OUT."*

    ⛔ **SUPERSEDED FOR DEVICES ON 2026-09-30, KEPT FOR SUB-METERS.** PO: the
    devices sheet gains *"Service · Size (cart size, fire-line size, panel
    size) · Unit of measure / capacity unit · Parent / linked meter"*. So this
    now asserts the half that still stands (sub-meters carry no size) AND the
    half that moved (devices do), so neither can drift back unnoticed.

    A connection size describes the SERVICE CONNECTION a meter sits on, and a
    sub-meter sits behind one. Widening it is `DEF-1901`'s call, and inventing
    it here would seed a vocabulary onto asset kinds nobody has ruled it for.

    ⚠ **ASSERTED ON THE OFFERED SET, WHICH IS ALSO THE AUTO-MAPPER'S
    WHITELIST.** `_auto_map` skips any alias whose field is not offered, so
    this one assertion is what stops a sub-meter file with a `size` header from
    quietly mapping it — even though the sub-meters alias table inherits the
    entry from the meters one.
    """
    with tenant_ctx(ottumwa):
        header = list(_cells("assets_submeters"))
        assert "size_class" not in header, header
        assert "size_class" in list(_cells("assets_devices"))


def test_TC8_the_stage_3_rule_is_declared_on_METERS_and_only_meters(ottumwa, ottumwa_admin):
    """The rule half of the same boundary, and it is a different fact.

    A column can be absent while a rule is still declared for the target — the
    rule would then evaluate every row against a field nothing maps and report
    nothing forever, which is a check that cannot fail and is worse than none
    (the `--stat` lesson, one layer down).
    """
    with tenant_ctx(ottumwa):
        codes = {
            target: {rule.code for rule in import_rules.resolve(target, ottumwa.id)}
            for target in ("assets_meters", "assets_submeters", "assets_devices")
        }
        assert "AST.SIZE_CLASS_IN_LOOKUP" in codes["assets_meters"]
        assert "AST.SIZE_CLASS_IN_LOOKUP" not in codes["assets_submeters"]
        # ⛔ Devices carry the column since 2026-09-30 (PO ruling), so they
        # carry the rule too — the rule half of TC-7's moved boundary.
        assert "AST.SIZE_CLASS_IN_LOOKUP" in codes["assets_devices"]


def test_TC9_the_rule_is_STRUCTURAL_so_a_tenant_cannot_switch_the_refusal_off(
    ottumwa, ottumwa_admin
):
    """TIER 1, and the reason is money.

    A tenant switching this rule off would be switching ON the silent
    mispricing DEF-514 and DEF-1900 were both filed for: an unknown size that
    merely flags loads a meter that then bills off the every-size rung, at
    `3.20 / 4.80 / 7.20` where a 2" connection should read
    `3.45 / 5.10 / 7.70`.
    """
    with tenant_ctx(ottumwa):
        rule = next(
            rule
            for rule in import_rules.resolve("assets_meters", ottumwa.id)
            if rule.code == "AST.SIZE_CLASS_IN_LOOKUP"
        )
        assert rule.tier == import_rules.TIER_STRUCTURAL, rule.tier
        assert rule.severity == import_rules.ERROR, rule.severity
        assert rule.action == import_rules.REJECT_ROW, rule.action

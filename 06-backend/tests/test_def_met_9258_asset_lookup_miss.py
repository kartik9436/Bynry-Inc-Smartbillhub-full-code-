# ── Trace ──────────────────────────────────────────────
# Defect:   DEF-MET-9258 — four asset-import lookup columns (meters and
#           sub-meters `Unit of measure`, devices `Service` and `Unit of
#           measure`) read to the DEF-618 guard as having no rule for a miss
# Rules:    AST.UOM_FOR_SERVICE · AST.SERVICE_ENABLED (both TIER 1, ERROR,
#           reject_row — apps/metering/import_rules.py) · DEF-618 (a lookup
#           miss is refused on its ROW at stage 3, never inside the load)
# Tests:    this file · tests/test_cr030_w1_accounts_import.py::
#           test_w1_e2e__every_lookup_column_is_spoken_FOR_by_a_rule
# ───────────────────────────────────────────────────────
"""**DEF-MET-9258 — an unknown code in an asset lookup column refuses its ROW.**

The DEF-618 guard reported `assets_meters.unit`, `assets_submeters.unit`,
`assets_devices.service` and `assets_devices.unit` as columns with no rule
saying what a miss means. It reads one naming convention —
`<column>_in_lookup` — and the four columns ARE covered, by rules named for
their question rather than their column: `AST.UOM_FOR_SERVICE`
(`uom_for_service`, every asset sheet) and `AST.SERVICE_ENABLED`
(`asset_service_enabled`, the devices sheet). That is `DEF-619`'s finding for
the meters' `service` column again, on four more columns.

⚠ **SO THE CLAIM IS PROVED BY RUNNING A FILE, NOT BY READING A CATALOGUE.**
Each case below sends a file with one GOOD row and one row carrying an
unknown code, through all four stages, and asserts three things: the bad row
is refused at stage 3 in words naming the column and the value; the good row
is not; and the load writes the good row and only it — so the bad code never
reaches the stage that writes, and cannot fail the file there.

RED PROOF (law 7): with `uom_for_service` and `asset_service_enabled` removed
from `import_rules.EVALUATORS`, the unit cases fail on the stage-3 problem
being absent, and the devices-service case fails the same way (`AssertionError:
{}` at the first assertion, all four). PostgreSQL 16 (law 14): all four pass with
`JOBS_EAGER` on and off, so a refused row poisons nothing the good row needs; quoted in the
defect's close.
"""

from __future__ import annotations

import pytest

from apps.assets import models as asset_models
from apps.metering import import_runs

from tests.test_ast_upload_fix_u12 import _file, _load, _problems, _stages
from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db


# ⚠ The rows name each unit by its NUMBER, never its label: with the sample
# utility seeded (`JOBS_EAGER=true`, the PostgreSQL run) `Unit 1` is carried by
# several units and refuses as ambiguous, which would test the unit resolver
# rather than the lookup miss.


def _refused_one_loaded_one(actor, target, good, bad, words):
    run_id = _stages(actor, target, _file(target, [good, bad]))
    problems = _problems(run_id)
    assert set(problems) == {2}, problems
    for phrase in words:
        assert phrase in problems[2], problems[2]
    receipt = _load(actor, run_id)
    assert receipt["counts"]["created"] == 1, receipt
    assert asset_models.Asset.objects.filter(external_ref=good["external_ref"]).exists()
    assert not asset_models.Asset.objects.filter(external_ref=bad["external_ref"]).exists()


def test_meters_an_unknown_unit_of_measure_refuses_only_its_row(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        good = {"external_ref": "M-GOOD", "service": "water", "unit_ref": units[0][1]["unit_no"]}
        bad = {
            "external_ref": "M-BAD",
            "service": "water",
            "unit_ref": units[1][1]["unit_no"],
            "unit": "furlongs",
        }
        _refused_one_loaded_one(
            ottumwa_admin,
            import_runs.TARGET_ASSETS_METERS,
            good,
            bad,
            ("furlongs", "is not a unit of measure"),
        )


def test_submeters_an_unknown_unit_of_measure_refuses_only_its_row(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        master_run = _stages(
            ottumwa_admin,
            import_runs.TARGET_ASSETS_METERS,
            _file(
                import_runs.TARGET_ASSETS_METERS,
                [
                    {
                        "external_ref": "MASTER",
                        "service": "water",
                        "unit_ref": units[0][1]["unit_no"],
                    }
                ],
            ),
        )
        assert _problems(master_run) == {}
        _load(ottumwa_admin, master_run)
        good = {
            "external_ref": "SM-GOOD",
            "service": "water",
            "unit_ref": units[1][1]["unit_no"],
            "parent_asset_no": "MASTER",
        }
        bad = {
            **good,
            "external_ref": "SM-BAD",
            "unit_ref": units[2][1]["unit_no"],
            "unit": "furlongs",
        }
        _refused_one_loaded_one(
            ottumwa_admin,
            import_runs.TARGET_ASSETS_SUBMETERS,
            good,
            bad,
            ("furlongs", "is not a unit of measure"),
        )


def test_devices_an_unknown_unit_of_measure_refuses_only_its_row(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        good = {
            "type": "container_cart",
            "external_ref": "CART-GOOD",
            "service": "trash",
            "unit_ref": units[0][1]["unit_no"],
        }
        bad = {**good, "external_ref": "CART-BAD", "unit": "furlongs"}
        _refused_one_loaded_one(
            ottumwa_admin,
            import_runs.TARGET_ASSETS_DEVICES,
            good,
            bad,
            ("furlongs", "is not a unit of measure"),
        )


def test_devices_an_unknown_service_refuses_only_its_row(ottumwa, ottumwa_admin):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        good = {
            "type": "container_cart",
            "external_ref": "CART-OK",
            "service": "trash",
            "unit_ref": units[0][1]["unit_no"],
        }
        bad = {**good, "external_ref": "CART-ELEC", "service": "ELEC"}
        _refused_one_loaded_one(
            ottumwa_admin,
            import_runs.TARGET_ASSETS_DEVICES,
            good,
            bad,
            ("does not sell ELEC",),
        )

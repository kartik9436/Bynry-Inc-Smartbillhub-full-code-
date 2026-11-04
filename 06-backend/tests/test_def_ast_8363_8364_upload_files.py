# ── Trace ──────────────────────────────────────────────
# Defects: DEF-AST-8363 (the asset upload RESULT file heads its columns with
#          internal field names — asset_number, unit_assigned — while the
#          template, the sample and the rejected-rows file use the labels) ·
#          DEF-AST-8364 (the devices SAMPLE pairs a backflow preventer with
#          Electric and size E-1P-100)
# Journey: 08-qa/01-e2e/journeys/J71-asset-upload-carts-and-fire-lines-to-the-bill.md
# Ruling:  PO 2026-09-30 — every downloaded asset file follows the plan
#          tables (the six-group order); "fix it if there is a bug"
# ───────────────────────────────────────────────────────
"""The two files an operator downloads beside an asset upload must read like
the template they filled in.

⚠ **WHAT WOULD MAKE THESE PASS WRONGLY (hard-won law 7(2)).**

  · *"the result header follows the plan order"* already passed on the
    defect — `test_ast_upload_fix_u12` maps each internal name BACK to a
    field and asserts the order, so it was blind to the text. These cases
    assert the header TEXT against the template's own header row.
  · *"the devices sample survives its own import"* passed on the defect too:
    Electric is enabled and `E-1P-100` is a ratified Electric size, so the
    nonsense row loads. These cases assert the TYPE and the SERVICE belong
    together, and that the size and the unit are that service's own — on
    two tenants, because `ottumwa` (water · sewer · trash) and `brazosbend`
    (electric first) each drew a different wrong pairing.
"""

from __future__ import annotations

import csv

import pytest

from apps.metering import import_runs
from apps.metering import seams as metering_seams

from tests.test_ast_upload_fix_u12 import _file, _labels, _load, _problems, _read_csv, _stages
from tests.test_def962_def963_assets_template import (  # noqa: F401 — fixtures
    _estate,
    ottumwa,
    ottumwa_admin,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import tenant_ctx

pytestmark = pytest.mark.django_db

DEVICES = import_runs.TARGET_ASSETS_DEVICES

#: The device kinds the plan names and the ONE service each is billed under.
DEVICE_SERVICE = {"backflow": "water", "container_cart": "trash", "fire_line": "fire"}


def _sample_row(target):
    _name, body = import_runs.sample_csv(target)
    rows = list(csv.reader(body.splitlines()))
    by_label = {v: k for k, v in _labels(target).items()}
    return {by_label.get(h, h): cell for h, cell in zip(rows[0], rows[1])}, rows[0]


# ══════════════════════════════════════════════════════════════════════════
# DEF-AST-8363 — the result file speaks the template's language
# ══════════════════════════════════════════════════════════════════════════


def test_the_result_file_headers_are_the_template_labels_in_template_order(
    ottumwa, ottumwa_admin
):
    with tenant_ctx(ottumwa):
        units = _estate(ottumwa_admin)
        row = {
            "type": "container_cart",
            "external_ref": "CART-8363",
            "unit_ref": units[0][1]["label"],
            "service": "trash",
            "size_class": "CART-64",
        }
        run_id = _stages(ottumwa_admin, DEVICES, _file(DEVICES, [row]))
        assert _problems(run_id) == {}, _problems(run_id)
        _load(ottumwa_admin, run_id)
        rows = _read_csv(run_id, "successes")
        _sample, template_header = _sample_row(DEVICES)

    header = rows[0]
    # The walk's two examples, by name.
    assert "asset_number" not in header
    assert "unit_assigned" not in header
    labels = _labels(DEVICES)
    assert header[:2] == [labels["asset_no"], labels["type"]]
    assert labels["unit_ref"] in header
    # Every column but the result-only last one IS a template column, and they
    # run in the template's own order.
    assert header[-1] == "Billing changes"
    positions = [template_header.index(h) for h in header[:-1]]
    assert positions == sorted(positions), header
    # The cells did not move: the cart is under `Unit`, its service under `Service`.
    cells = dict(zip(header, rows[1]))
    assert cells[labels["unit_ref"]] == units[0][1]["label"]
    assert cells[labels["service"]] == "trash"


@pytest.mark.parametrize(
    "target", [import_runs.TARGET_ASSETS_METERS, import_runs.TARGET_ASSETS_SUBMETERS]
)
def test_every_asset_sheets_result_header_is_a_template_label(target):
    header = import_runs.success_headers(target)
    labels = set(_labels(target).values())
    assert header[-1] == "Billing changes"
    # The two RESULT-ONLY columns: what the change moved, and — on the two
    # sheets that carry no type column — what kind of asset landed.
    result_only = {"Billing changes", "Asset type"}
    missing = [h for h in header if h not in labels | result_only]
    assert missing == [], missing
    assert len(header) == len(import_runs.SUCCESS_COLUMNS_BY_TARGET[target])


# ══════════════════════════════════════════════════════════════════════════
# DEF-AST-8364 — the devices sample is a device that belongs to its service
# ══════════════════════════════════════════════════════════════════════════


def _assert_coherent(sample):
    kind, service = sample["type"], sample["service"]
    assert kind in DEVICE_SERVICE, f"{kind!r} is not one of the plan's device kinds"
    assert service == DEVICE_SERVICE[kind], f"a {kind} is not billed under {service}"
    sizes = metering_seams.ratified_size_class_codes(service)
    assert sample["size_class"] == "" or sample["size_class"] in sizes, (
        f"{sample['size_class']!r} is not a {service} size"
    )
    units = metering_seams.service_default_uoms()
    assert sample["unit"] == (units.get(service) or "")


def test_the_devices_sample_on_a_water_trash_tenant_pairs_a_device_with_its_own_service(
    ottumwa, ottumwa_admin
):
    with tenant_ctx(ottumwa):
        _estate(ottumwa_admin)
        sample, _header = _sample_row(DEVICES)
        _assert_coherent(sample)
    # Ottumwa sells water, so the worked device is the backflow preventer.
    assert (sample["type"], sample["service"]) == ("backflow", "water")


def test_the_devices_sample_on_an_electric_tenant_never_puts_a_backflow_on_electric(brazos):
    """The walk's own tenant shape: Electric sorts first among the services
    that carry a unit, and the fixed `backflow` sat beside it."""
    with tenant_ctx(brazos):
        sample, _header = _sample_row(DEVICES)
        _assert_coherent(sample)
    assert sample["service"] != "electric"
    assert not sample["size_class"].startswith("E-")

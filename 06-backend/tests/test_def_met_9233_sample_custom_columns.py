# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-9233 — the downloadable sample CSV for the premises, units
#          and asset imports left out the utility's own custom fields, so a
#          clerk filling in the template never saw a column for them. Found by
#          the custom-fields end-to-end walk (`10-scripts/cf_e2e_walk.mjs`
#          phase 6). The readings template already carried them (W4).
# Rules:   CR-161-BRC10 Part 2, added in discussion (PO 2026-10-02): *"every
#          import includes one column per custom field (premises, units,
#          assets, accounts, readings)"* · the Rules table: *"One utility
#          only"* (another utility's sample never names this one's field).
# ───────────────────────────────────────────────────────
"""The sample is built per tenant at request time, so it CAN know the tenant's
own fields — the old docstring's reason (*"a sample cannot know a tenant's own
field keys"*) was never true. Each one is a column headed with its LABEL and an
empty example cell (a field's values are the utility's own), and the file still
maps itself and is still recognised as the system template."""

import csv
import io

import pytest

from apps.metering import import_runs
from apps.tenancy import services as tenancy_services
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import brazos, dana, lonestar, tenant_ctx  # noqa: F401

pytestmark = pytest.mark.django_db


def _define(actor, label, entity, placement):
    field = tenancy_services.create_custom_field(actor, {"label": label, "entity": entity, "data_type": "text"})
    tenancy_services.save_custom_field_placement(actor, field["id"], placement)
    return field


def _sample(target):
    _name, body = import_runs.sample_csv(target)
    rows = list(csv.reader(io.StringIO(body)))
    return rows[0], rows[1]


@pytest.mark.parametrize(
    ("target", "entity", "label", "placement"),
    [
        ("premises", "premises", "Roof Material", {"S16": "input"}),
        ("units", "units", "Gate code", {"S16": "input"}),
        ("assets_meters", "assets", "Warranty provider", {"S51": "input"}),
        ("assets_submeters", "assets", "Warranty provider", {"S51": "input"}),
        ("assets_devices", "assets", "Warranty provider", {"S51": "input"}),
    ],
)
def test_def_met_9233__the_sample_carries_one_column_per_own_field(brazos, dana, target, entity, label, placement):
    with tenant_ctx(brazos):
        _define(dana, label, entity, placement)
        header, example = _sample(target)
        mapped = import_runs._auto_map(header, target)  # noqa: SLF001 — the stage-1 suggestion
    assert label in header, header
    assert example[header.index(label)] == ""  # the utility's own values: never invented
    assert mapped.get(label) == f"custom_data.{label.lower().replace(' ', '_')}"


def test_def_met_9233__a_switched_off_field_leaves_the_sample(brazos, dana):
    with tenant_ctx(brazos):
        field = _define(dana, "Gate code", "units", {"S16": "input"})
        tenancy_services.set_custom_field_active(dana, field["id"], False)
        header, _ = _sample("units")
    assert "Gate code" not in header


def test_def_met_9233__another_utilitys_sample_never_names_this_ones_field(brazos, dana, lonestar):
    with tenant_ctx(brazos):
        _define(dana, "Roof Material", "premises", {"S16": "input"})
    with tenant_ctx(lonestar):
        header, _ = _sample("premises")
    assert "Roof Material" not in header


def test_def_met_9233__the_sample_is_still_recognised_as_the_system_template(brazos, dana):
    """`_match_mapping_template` matched the EXACT header set, so a sample
    carrying a custom column would stop being recognised as the system default
    it was generated from. The utility's own columns are set aside for that
    comparison only; they are still mapped by label."""
    with tenant_ctx(brazos):
        before_header, _ = _sample("premises")
        before = import_runs._match_mapping_template("premises", before_header)  # noqa: SLF001
        _define(dana, "Roof Material", "premises", {"S16": "input"})
        header, _ = _sample("premises")
        after = import_runs._match_mapping_template("premises", header)  # noqa: SLF001
    assert "Roof Material" in header
    assert (before is None) == (after is None)
    if before is not None:
        assert after.id == before.id

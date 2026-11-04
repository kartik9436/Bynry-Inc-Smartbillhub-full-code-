# ── Trace ──────────────────────────────────────────────
# Change:   CR-168-BRC10 round 6 · lane FIX-7 — DEF-WRK-9671 (a job the
#           certification rule raises on a meter in the warehouse says only a
#           dash for where it is, even when the meter carries a location note).
# Rules:    CLAUDE.md hard rule 8 (an address is the PREMISES'; the note is the
#           ASSET's own free text, read at use and never stored on the job) ·
#           B14 rule 31 · DEF-WRK-9660 (the walk follows the device)
# ───────────────────────────────────────────────────────
"""Where a job on a warehouse meter is, in the asset's own words or a dash.

The behaviour — that the rule raises on a meter standing on no premises — is
NOT changed here: whether it should is the PO's open question. Only what the
row SAYS about where the job is: `stored_at` carries `assets.location_note`
when, and only when, the job stands on no premises.
"""

from __future__ import annotations

import pytest

from apps.assets import models as assets_models
from apps.work import connection_models as work_tables
from apps.work import dispatch, rules

from tests.test_def_wrk_9660_9661_rule_raise import (
    YESTERDAY,
    _installed_backflow,
    _rule,
    _template,
)
from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import make_asset, tenant_ctx

pytestmark = pytest.mark.django_db


def _warehouse_job(actor, *, note):
    template = _template(actor, name="Bench test", service="electric")
    spare = make_asset(actor, asset_no="M-9671")
    assets_models.Asset.objects.filter(pk=spare["id"]).update(
        certification_due=YESTERDAY, location_note=note
    )
    rule = _rule(actor, template["id"], "Bench test due")
    assert rules.sweep(actor, rule_ids=[rule["id"]])["rules"][0]["raised"] == 1
    return work_tables.WorkOrder.objects.get(rule_id=rule["id"])


def test_9671_a_warehouse_meter_with_a_note_says_where_it_is_stored(brazos, dana):
    """RED on the tip: ``KeyError: 'stored_at'``."""
    with tenant_ctx(brazos):
        order = _warehouse_job(dana, note="Warehouse bay 3")
        row = dispatch.order_row(order.id)
        listed = dispatch.dispatch_page(q=order.order_no)["rows"]
    assert row["premise"] is None
    assert row["stored_at"] == "Warehouse bay 3"
    assert [r["stored_at"] for r in listed] == ["Warehouse bay 3"]


def test_9671_a_warehouse_meter_with_no_note_carries_nothing_and_the_screen_dashes(brazos, dana):
    with tenant_ctx(brazos):
        order = _warehouse_job(dana, note=None)
        row = dispatch.order_row(order.id)
    assert row["premise"] is None
    assert row["stored_at"] is None


def test_9671_an_installed_device_names_its_premises_and_never_its_note(brazos, dana):
    """The note is the answer only for a job on NO premises — hard rule 8."""
    with tenant_ctx(brazos):
        _premises, _unit, asset = _installed_backflow(dana, asset_no="BF-9671")
        assets_models.Asset.objects.filter(pk=asset["id"]).update(location_note="Basement")
        template = _template(dana, name="Backflow test")
        rule = _rule(dana, template["id"], "Backflow test due")
        rules.sweep(dana, rule_ids=[rule["id"]])
        order = work_tables.WorkOrder.objects.get(rule_id=rule["id"])
        row = dispatch.order_row(order.id)
    assert row["premise"] is not None
    assert row["stored_at"] is None


def _texts(rows):
    return [" ".join(cell.text for cell in row.cells) for row in rows]


def test_9671_the_printed_sheet_says_where_the_meter_is_stored(brazos, dana):
    """The paper reads the same row the screen does: *Stored at Warehouse bay 3*
    under a dashed Address, never the note written as an address."""
    from apps.work import print_docs

    with tenant_ctx(brazos):
        order = _warehouse_job(dana, note="Warehouse bay 3")
        rows, _ = print_docs.order_rows(order.id)
    texts = _texts(rows)
    assert "Stored at Warehouse bay 3" in texts
    assert not any(text.startswith("Address Warehouse") for text in texts)

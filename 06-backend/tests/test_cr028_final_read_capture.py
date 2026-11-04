# ── Trace ──────────────────────────────────────────────
# Change:   CR-028 debt sweep D5 (PO 2026-08-22: "resolve any open technical
#           debt related to assets") — BR-AST-022's final-read capture seam,
#           WIRED. From W1 to this sweep, every reassign/retire that asked
#           for a final read refused BIZ-COMPLETENESS because
#           apps.metering.services.capture_final_read did not exist.
# Screens:  S55 / AST-06 (reassign) · S54 / AST-08 (retire, step 1)
# Rules:    BR-AST-022 (the read and the move are ONE transaction) ·
#           BR-AST-021 (retire closes the assignment; final_read_id lands on
#           the closing row) · BR-MET-016/053 (lineage: one head per
#           (asset, date, channel); corrections supersede) · BR-MET-015 (an
#           ERROR outcome is resolved by a human, never by this form — so it
#           refuses the whole move) · BR-MET-056 (the row stores the math it
#           was computed with) · CLAUDE.md rule 3 (explicit unit) · rule 7
#           (the capture is audited, metering-side and assets-side)
# Tests:    this file (updates the two refusal-era tests' law:
#           test_us_ast_007_009_lifecycle.py::tc1 · test_cr028_valuation.py)
# Impacts:  apps/metering/services.py (capture_final_read) ·
#           apps/assets/services.py (reassign/retire wiring + the child-move
#           final-read strip) · asset_assignments.final_read_id (B11 F-3)
# ───────────────────────────────────────────────────────
"""CR-028 debt sweep D5 — the final-read capture, end to end.

RED-FIRST: this file was run against the tree as the sweep found it
(capture_final_read unwired) — the end-to-end cases failed with
`BizError: BIZ-COMPLETENESS (assets.final_read_capture_unavailable)`,
quoted in the lane report. The refusal is GONE on the wired tree.
"""

from datetime import date
from decimal import Decimal

import pytest

from apps.assets import selectors as asset_selectors
from apps.assets import services as asset_services
from core import errors

from tests.test_us_met_reads_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_reads_helpers import (  # noqa: F401
    a_meter,
    at,
    commit_read,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def _unit(actor, label="224", address="2200 Riverside"):
    from tests.test_us_met_helpers import make_premises, make_unit

    premise = make_premises(actor, address_line=address, services_available=["electric", "water"])
    return make_unit(actor, premise["id"], label=label, services=["electric", "water"])


def _read_row(read_id):
    from apps.metering import models

    return models.MeterRead.objects.get(id=read_id)


def _closing_assignment(asset_id):
    from apps.assets import models

    return (
        models.AssetAssignment.objects.filter(asset_id=asset_id, to_date__isnull=False)
        .order_by("-to_date")
        .first()
    )


def test_d5__reassign_with_final_read_captures_and_links_it_end_to_end(brazos, dana, audit_rows):
    """THE REFUSAL IS GONE: the move commits WITH its read, one transaction.

    RED on the unwired tree: BizError BIZ-COMPLETENESS
    (assets.final_read_capture_unavailable) — nothing moved.
    """
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-4022")
        target = _unit(dana)
        commit_read(dana, asset["id"], day="2026-08-03", value="42864", consumption="684")

        result = asset_services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": target["id"],
                "effective_date": "2026-09-01",
                "final_read_value": "43566",
            },
        )

        # The committed read: metering's own lineage row, manual, final_read.
        final = result["final_read"]
        row = _read_row(final["id"])
        assert row.current_value == Decimal("43566.000000")
        assert row.prior_value == Decimal("42864.000000")
        assert row.consumption == Decimal("702.000000")  # (43566−42864)×1, BR-MET-056
        assert row.unit == "kWh"  # rule 3 — the ASSET's own UoM
        assert row.source == "manual" and row.source_detail == "final_read"
        assert row.lifecycle == "committed"
        assert row.read_at == at("2026-09-01")  # defaults to the effective date

        # BR-AST-022/021: the CLOSING assignment carries the read's id.
        closed = _closing_assignment(asset["id"])
        assert closed is not None and closed.to_date == date(2026, 9, 1)
        assert str(closed.final_read_id) == final["id"]

        # The move itself happened — the new assignment is open on the target.
        assert result["assigned_unit_id"] == target["id"]

    # Rule 7, both sides: metering audits the capture, assets audits the link.
    actions = [r["action"] for r in audit_rows]
    assert "read.final_read_captured" in actions
    assert "asset.final_read_captured" in actions


def test_d5__the_final_read_date_input_is_honored(brazos, dana):
    """AST-06's value+date pair: the read lands on ITS date, the move on the
    effective date — two different days, both stored."""
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-4023", unit_label="Unit B", address="12 Oak")
        target = _unit(dana, label="B2", address="14 Oak")
        commit_read(dana, asset["id"], day="2026-08-03", value="100", consumption="10")
        result = asset_services.reassign_asset(
            dana,
            asset["id"],
            {
                "unit_id": target["id"],
                "effective_date": "2026-09-02",
                "final_read_value": "130",
                "final_read_date": "2026-08-31",
            },
        )
        row = _read_row(result["final_read"]["id"])
        assert row.read_at == at("2026-08-31")
        closed = _closing_assignment(asset["id"])
        assert closed.to_date == date(2026, 9, 2)


def test_d5__retire_with_final_read_captures_and_links_it(brazos, dana):
    """AST-08 step 1 — the retire takes the read, closes the assignment with
    its id, and the asset ends terminal.

    RED on the unwired tree: assets.final_read_capture_unavailable and the
    retire did not happen.
    """
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-7008")
        commit_read(dana, asset["id"], day="2026-08-03", value="42864", consumption="684")
        result = asset_services.retire_asset(
            dana,
            asset["id"],
            {
                "reason": "failed",
                "retire_date": "2026-09-01",
                "final_read_value": "43566",
            },
        )
        assert result["status"] == "retired"
        closed = _closing_assignment(asset["id"])
        assert closed is not None and closed.to_date == date(2026, 9, 1)
        row = _read_row(str(closed.final_read_id))
        assert row.consumption == Decimal("702.000000")
        assert row.source == "manual" and row.source_detail == "final_read"


def test_d5__a_requested_capture_with_no_value_refuses_and_nothing_moves(brazos, dana):
    """`record_final_read` ON with no reading refuses VAL-REQUIRED — silence
    would claim a read was taken (BR-AST-022's honesty, kept)."""
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-4024", unit_label="Unit C", address="9 Elm")
        target = _unit(dana, label="C2", address="11 Elm")
        with pytest.raises(errors.ValidationError) as caught:
            asset_services.reassign_asset(
                dana,
                asset["id"],
                {"unit_id": target["id"], "effective_date": "2026-09-01"},
            )
        assert caught.value.field_errors[0]["message_key"] == "assets.final_read_value_required"
        history = asset_selectors.assignments(asset["id"])
        assert len(history) == 1 and history[0]["to_date"] is None  # nothing moved


def test_d5__a_standing_head_on_the_same_date_refuses_the_whole_move(brazos, dana):
    """BR-MET-016/053: one head per (asset, date, channel). A second 'final'
    read on a read day is a CORRECTION (S29 supersede), never a second head —
    and the refusal rolls the move back with it (one transaction)."""
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-4025", unit_label="Unit D", address="5 Pine")
        target = _unit(dana, label="D2", address="7 Pine")
        commit_read(dana, asset["id"], day="2026-09-01", value="500", consumption="50")
        with pytest.raises(errors.BizError) as caught:
            asset_services.reassign_asset(
                dana,
                asset["id"],
                {
                    "unit_id": target["id"],
                    "effective_date": "2026-09-01",
                    "final_read_value": "510",
                },
            )
        assert caught.value.message_key == "metering.read.final_read_already_exists"
        history = asset_selectors.assignments(asset["id"])
        assert len(history) == 1 and history[0]["to_date"] is None


def test_d5__an_error_severity_outcome_refuses_capture_and_move(brazos, dana):
    """BR-MET-015: an ERROR is resolved by a human's override/reject/field
    visit — this form offers none, so the whole move refuses. A register far
    BELOW the prior (no rollover shape) is negative usage, the engine's own
    error."""
    with tenant_ctx(brazos):
        asset = a_meter(dana, asset_no="M-4026", unit_label="Unit E", address="3 Fir")
        target = _unit(dana, label="E2", address="4 Fir")
        commit_read(dana, asset["id"], day="2026-08-03", value="42864", consumption="684")
        with pytest.raises(errors.BizError) as caught:
            asset_services.reassign_asset(
                dana,
                asset["id"],
                {
                    "unit_id": target["id"],
                    "effective_date": "2026-09-01",
                    "final_read_value": "40000",
                },
            )
        assert caught.value.message_key == "metering.read.final_read_failed_validation"
        history = asset_selectors.assignments(asset["id"])
        assert len(history) == 1 and history[0]["to_date"] is None


def test_d5__children_moved_with_a_parent_take_no_final_read(brazos, dana):
    """The final-read fields are the PARENT register's. Copied onto a child
    they would commit the parent's value as the child's reading — so a child
    moved with its parent takes NO read here; its register travels through
    S28 like any collection."""
    from apps.metering import models as met_models

    with tenant_ctx(brazos):
        home = _unit(dana, label="102", address="Vega Apts")
        target = _unit(dana, label="105", address="Vega Apts 105")
        from tests.test_us_met_helpers import make_asset

        master = make_asset(
            dana,
            asset_no="M-MASTER-12",
            service="electric",
            unit_id=home["id"],
            install_date="2026-01-01",
        )
        child = make_asset(
            dana,
            asset_no="SM-8801",
            type="sub_meter",
            service="electric",
            parent_asset_no=master["asset_no"],
            unit_id=home["id"],
            install_date="2026-01-01",
        )
        commit_read(dana, master["id"], day="2026-08-03", value="42864", consumption="684")
        result = asset_services.reassign_asset(
            dana,
            master["id"],
            {
                "unit_id": target["id"],
                "effective_date": "2026-09-01",
                "final_read_value": "43566",
            },
        )
        assert {c["asset_no"] for c in result["children_moved"]} == {"SM-8801"}
        # Exactly ONE read was captured — the master's. The child has none.
        assert met_models.MeterRead.objects.filter(asset_id=master["id"]).count() == 2
        assert met_models.MeterRead.objects.filter(asset_id=child["id"]).count() == 0
        child_closed = _closing_assignment(child["id"])
        assert child_closed is not None and child_closed.final_read_id is None

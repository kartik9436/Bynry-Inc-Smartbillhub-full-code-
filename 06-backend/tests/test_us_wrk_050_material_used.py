# ── Trace ──────────────────────────────────────────────
# Story:    US-WRK-050 (a part issued against a job, used-of-planned, with no
#           count moving).  Screens: Work-012, Work-008
# Rules:    BR-WRK-049 (used-of-planned) · OQ-WRK-1490 CLOSED 2026-09-04 to
#           option (a) — no stock, ever · hard rule 1 (tenant scope) ·
#           hard rule 7 (every money action writes audit_log)
# Endpoint: 07-endpoints.md §6 row 75 — `PUT /work-orders/{id}/materials/{mid}/used`
# Tests:    this file
# ───────────────────────────────────────────────────────
"""**#75, the route wave `N` left unwritten — and the second writer it retires.**

WHY THIS FILE EXISTS AT ALL
===========================
Wave `N` shipped with a stamp reading *"WHAT IS NOT DONE, AND IT IS NOT A
DEFERRAL A LATER LANE SHOULD GUESS AT: `PUT …/materials/{mid}/used` (wave `H`'s
table landed mid-build and the route was not written)"*. That is an OMISSION
and not an open question, and the evidence is all in the repository rather than
in anybody's memory: `07-endpoints.md` row 75 has specified the route since the
contract was written, `work_order_materials` exists (`work/0012`), `costing.py`
reads `used_qty`, and `sync._apply_material` had been writing that one column
from the handset since wave `L` — with a docstring naming this route and asking
to be replaced by it.

THE ONE THING THE DELEGATION FIXED THAT NOBODY WAS LOOKING FOR
==============================================================
`work_order_materials` carries `issued_by` and `issued_at` — the *who* and
*when* `N1` asks #75 for. **The handset's inline writer set neither**, so every
part reported from the field landed with a quantity and no attribution, and
nothing anywhere went red. `test_the_phone_records_who_and_when_too` is the
clause that would have caught it, and it is written against the SYNC door on
purpose: the bug was never in the route, it was in the copy of the route.

NULL IS NOT ZERO, AND IT IS A MONEY DISTINCTION
===============================================
`costing.py`: NULL means *nobody has said* and contributes no cost line; `0`
means *asked for and not used* and also contributes none — but the two read
differently to a supervisor (`US-WRK-050` TC-2, *0 of 1 · not used*). A route
that defaulted a missing `used_qty` to zero would silently convert one into the
other, so a missing quantity is REFUSED.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.work import checklist
from apps.work import models as work_models
from apps.work import sync
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · lonestar · dana · erin
from tests.test_us_met_helpers import tenant_ctx
from tests.test_us_wrk_032_copies import _published_template, _raise

pytestmark = pytest.mark.django_db


def _order_with_materials(actor, tenant):
    tid = _published_template(actor, tenant)
    oid = _raise(actor, tenant, tid)["id"]
    rows = list(
        work_models.WorkOrderMaterial.objects.filter(work_order_id=oid).order_by("part__part_no")
    )
    assert rows, "the fixture template plans three parts"
    return oid, rows


# ══════════════════════════════════════════════════════════════════════════
# The route writes what the endpoint contract says it writes
# ══════════════════════════════════════════════════════════════════════════
def test_used_of_planned_is_recorded_with_who_and_when(brazos, dana):
    """Row 75 — *used-of-planned, who, when*. All four, in one write."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        row = rows[0]
        assert row.used_qty is None, "nobody has said yet"

        answer = checklist.set_material_used(dana, oid, row.id, {"used_qty": "1"})

        row.refresh_from_db()
        assert row.used_qty == Decimal("1.0000")
        assert row.issued_by_id == dana.id
        assert row.issued_at is not None
        assert answer["used_qty"] == "1"
        assert answer["part_no"] == row.part.part_no


def test_a_second_report_supersedes_the_first_rather_than_adding_to_it(brazos, dana):
    """PUT, not PATCH — *how many did this job use* has ONE current answer, which
    is what makes the route safe to retry from a handset that lost its signal."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "1"})
        checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "2"})
        rows[0].refresh_from_db()
        assert rows[0].used_qty == Decimal("2.0000"), "the second report replaces the first"


def test_zero_used_is_a_real_answer_and_is_not_null(brazos, dana):
    """`US-WRK-050` TC-2 — *0 of 1 · not used* is an OUTCOME. It must be
    distinguishable from *nobody has said*, or the screen cannot show it."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "0"})
        rows[0].refresh_from_db()
        assert rows[0].used_qty == Decimal("0.0000")
        assert rows[0].used_qty is not None


def test_a_missing_quantity_is_refused_and_not_defaulted_to_zero(brazos, dana):
    """The clause that keeps the line above true. A default of zero would
    convert *unreported* into *reported as unused* with nothing to notice it."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            checklist.set_material_used(dana, oid, rows[0].id, {})
        assert raised.value.code == errors.VAL_REQUIRED
        rows[0].refresh_from_db()
        assert rows[0].used_qty is None, "nothing was written"


def test_a_quantity_that_is_not_a_number_is_refused(brazos, dana):
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "two"})
        assert raised.value.code == errors.VAL_FORMAT


def test_a_negative_quantity_is_refused_before_it_reaches_a_frozen_report(brazos, dana):
    """The column has no CHECK and `work_order_cost_lines` would price it. A
    report is frozen at acceptance, so a negative line is money that cannot be
    corrected in place (hard rule 4) — the door is the only place to stop it."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "-1"})
        assert raised.value.code == errors.VAL_RANGE
        rows[0].refresh_from_db()
        assert rows[0].used_qty is None


def test_no_on_hand_count_moves_because_there_is_nowhere_for_one_to_move(brazos, dana):
    """`OQ-WRK-1490`, closed 2026-09-04 to option (a): *"stock control is an
    inventory system"*. Asserted as an ABSENCE OF COLUMNS rather than as an
    unchanged number — a count that never existed cannot be observed to hold
    still, and a test that pretended to watch one would be a check that cannot
    fail."""
    fields = {f.name for f in work_models.Part._meta.get_fields()}
    assert not fields & {"on_hand", "on_hand_qty", "reorder_at", "location", "stock"}
    material_fields = {f.name for f in work_models.WorkOrderMaterial._meta.get_fields()}
    assert not material_fields & {"on_hand", "stock", "reorder_at"}


# ══════════════════════════════════════════════════════════════════════════
# ONE writer — the sync door and the route door are the same code
# ══════════════════════════════════════════════════════════════════════════
def test_the_phone_records_who_and_when_too(brazos, dana):
    """**THE REGRESSION THIS WHOLE CHANGE EXISTS FOR.** `sync._apply_material`
    was a second writer of `used_qty` and set neither `issued_by` nor
    `issued_at`; a part reported from a handset arrived with no attribution and
    every check in the repository stayed green over it. Delete the delegation in
    `sync.py` and this clause goes red."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        sync._apply_material(dana, oid, {"material_id": str(rows[0].id), "used_qty": "3"})
        rows[0].refresh_from_db()
        assert rows[0].used_qty == Decimal("3.0000")
        assert rows[0].issued_by_id == dana.id, "the phone's writer records WHO"
        assert rows[0].issued_at is not None, "the phone's writer records WHEN"


def test_the_phone_door_refuses_exactly_what_the_route_door_refuses(brazos, dana):
    """One evaluator, the argument `checklist.safety_lock()` already makes for
    the safety rule: two doors that disagree about a rule is how one of them
    keeps an old answer."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        with pytest.raises(errors.ValidationError) as raised:
            sync._apply_material(dana, oid, {"material_id": str(rows[0].id)})
        assert raised.value.code == errors.VAL_REQUIRED


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 1 — another utility's part is a 404, byte-identical to absent
# ══════════════════════════════════════════════════════════════════════════
def test_another_utilitys_material_row_is_not_found(brazos, lonestar, dana, erin):
    """HR-1 — Lone Star asking for a Brazos Bend part gets the same answer as
    for a part that does not exist. Not 403, which would confirm it is there."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        theirs = rows[0].id
        their_order = oid
    with tenant_ctx(lonestar):
        with pytest.raises(Exception) as raised:
            checklist.set_material_used(erin, their_order, theirs, {"used_qty": "1"})
        assert "404" in str(type(raised.value)) or getattr(raised.value, "status", 404) == 404
    with tenant_ctx(brazos):
        rows[0].refresh_from_db()
        assert rows[0].used_qty is None, "and nothing was written across the boundary"


def test_a_material_row_of_another_order_is_not_found(brazos, dana):
    """The check a foreign key could not make: the row must belong to THIS
    order, not merely to this tenant."""
    with tenant_ctx(brazos):
        # ⚠ ONE template, raised TWICE. `_published_template` creates the parts
        # catalogue with fixed part numbers, so calling it a second time in one
        # test collides on `uq_parts_tenant_part_no_ci` — a fixture failure that
        # reads exactly like a product failure.
        tid = _published_template(dana, brazos)
        oid_a = _raise(dana, brazos, tid)["id"]
        oid_b = _raise(dana, brazos, tid)["id"]
        rows_a = list(
            work_models.WorkOrderMaterial.objects.filter(work_order_id=oid_a).order_by(
                "part__part_no"
            )
        )
        assert rows_a and oid_a != oid_b
        with pytest.raises(Exception):
            checklist.set_material_used(dana, oid_b, rows_a[0].id, {"used_qty": "1"})
        rows_a[0].refresh_from_db()
        assert rows_a[0].used_qty is None


# ══════════════════════════════════════════════════════════════════════════
# Hard rule 7 — the write is in the audit log
# ══════════════════════════════════════════════════════════════════════════
def test_the_write_is_audited(brazos, dana, audit_rows):
    """Hard rule 7. Asserted through the capture sink `test_us_met_helpers`
    installs `autouse` — in this test family `core_audit.write_row` never
    reaches `audit_log` itself, so a query against the table is a check that
    cannot pass and would read as a missing audit row."""
    with tenant_ctx(brazos):
        oid, rows = _order_with_materials(dana, brazos)
        before = len(audit_rows)
        checklist.set_material_used(dana, oid, rows[0].id, {"used_qty": "1"})
        written = [r for r in audit_rows[before:] if r["action"] == "work.material.used"]
        assert len(written) == 1, [r["action"] for r in audit_rows[before:]]
        assert written[0]["entity_type"] == "work_order_material"
        assert written[0]["entity_id"] == rows[0].id
        assert written[0]["after"] == {"used_qty": "1"}
        # The value it replaced, which is what makes the row worth keeping.
        assert written[0]["before"] == {"used_qty": None}

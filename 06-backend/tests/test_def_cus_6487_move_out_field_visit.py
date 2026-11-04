# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-CUS-6487 — `POST /accounts/{id}/move-out` read ONLY
#          `field_visit.template_ids`. The ROWS a clerk adds in the approved
#          field-visit table, and the *No visit needed* answer, were parsed out
#          of the payload and silently dropped.
# Rules:   BR-WRK-055 (a flow completes whether or not the visit was raised) ·
#          BR-WRK-024 (every order carries its source) · BR-WRK-006 (an order
#          stands on an anchor) · CLAUDE.md hard-won law 2 (built is not wired,
#          and its mirror — a live control over a door that ignores it)
# Tests:   this file
# ───────────────────────────────────────────────────────
"""DEF-CUS-6487 — the move-out door reads the WHOLE field-visit election.

**WHY THIS EXISTS.** The PO approved `FieldVisitOrders.tsx` for the move-out on
2026-09-24 — *"this si correct - use it"* — the same seven-column table the
move-in and the transfer already mount. That component emits
`{none: bool, orders: [...]}`. The move-out's door called
`_field_visit_templates()`, which returns `template_ids` and nothing else, so
mounting the approved table would have given a clerk seven columns and an
*Add work order* button over a door that threw every row away.

⚠ **THE SHAPE IS HARD-WON LAW 2's MIRROR AND IT IS WORSE THAN A DEAD PROP.**
A dead prop renders nothing and is visible. Here the control renders, accepts
input, the flow SUCCEEDS, the account closes — and no crew is ever sent. There
is no error anywhere for anybody to read.

⚠ **AND IT WAS INVISIBLE TO THE SUITE FOR A STRUCTURAL REASON, NOT A LAZY ONE:**
the move-out is the one flow that never mounted the table, so no caller had ever
sent it `orders`. **A door that ignores a key nobody sends is indistinguishable
from a door that handles it.** `DEF-CUS-6363` taught `_move_in` and the transfer
to read the whole election in `2.351.0` and did not re-read the third door.

**THE FIX IS TO MIRROR `_move_in`, NOT TO INVENT ANYTHING.** `_field_visit()`
already parses all three parts, `_raise_flow_work()` already takes `orders=`,
and `field_visit_declined` is already the answer's own key. The move-out was
simply calling the narrower of two parsers that were written together.
"""

from __future__ import annotations

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.work import connection_models as work_tables
from apps.work import models as work_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — brazos · dana
from tests.test_us_met_helpers import tenant_ctx

from tests.test_us_wrk_039_from_flows import (  # noqa: F401 — the fixtures this door needs
    MOVE_OUT_DAY,
    _occupant,
    _published_template,
    _unit_with_plan,
)
from tests.move_out_draft_isolation import move_out_draft_isolated  # noqa: F401

# DEF-CUS-10093 (PO 2026-10-13, option B): the final-bill draft is isolated
# here — this suite tests the field visit; see tests/move_out_draft_isolation.py.
pytestmark = pytest.mark.usefixtures("move_out_draft_isolated")


def _catalogue(tenant):
    """One priority, two job types and a crew — the smallest catalogue a row
    can name. Mirrors `test_def_cus_6353`'s helper rather than inventing a
    second shape for the same three tables."""
    high = work_models.WorkPriority.objects.create(
        tenant=tenant, code="high-6487", name="High (test)", rank=901, sla_hours=8
    )
    final_read = work_models.WorkOrderType.objects.create(
        tenant=tenant, code="FR-6487", name="Final read", default_priority=high
    )
    pull = work_models.WorkOrderType.objects.create(tenant=tenant, code="PM-6487", name="Pull meter")
    crew = work_models.Crew.objects.create(tenant=tenant, name="Crew B — West", kind="crew")
    return high, final_read, pull, crew


# ── 1 · the rows a clerk adds are actually raised ───────────────────────────
@pytest.mark.django_db
def test_the_rows_added_on_step_2_are_raised_when_the_account_closes(dana, brazos):
    """**THE CASE THE DEFECT IS.** Two rows with a note, a crew and a due date;
    before the fix `result["work_orders"]` came back EMPTY and the move-out
    reported success."""
    with tenant_ctx(brazos):
        high, final_read, pull, crew = _catalogue(brazos)
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)

        result = customers_services.move_out(
            dana,
            account["id"],
            {
                "moved_out_on": MOVE_OUT_DAY,
                "field_visit": {
                    "orders": [
                        {
                            "type_id": str(final_read.id),
                            "due_on": "2026-03-29",
                            "crew_id": str(crew.id),
                            "note": "Final read",
                        },
                        {"type_id": str(pull.id), "note": "Pull the meter"},
                    ]
                },
            },
        )

        raised = result["work_orders"]
        assert [row["name"] for row in raised] == ["Final read", "Pull meter"], (
            "the rows a clerk added on step 2 were dropped by the door"
        )
        # Read back out of `work_orders`, never off the response (DEF-CUS-6363).
        first = work_tables.WorkOrder.objects.get(pk=raised[0]["id"])
        second = work_tables.WorkOrder.objects.get(pk=raised[1]["id"])
        assert first.priority_id == high.id  # the type's own default, BR-WRK-018
        assert first.technician_notes == "Final read"
        assert first.assignee_crew_id == crew.id
        assert second.assignee_crew_id is None
        # BR-WRK-006 / BR-WRK-024 — the anchor and the provenance the move-out
        # already gave a TEMPLATE-raised order, now given to a ROW-raised one.
        assert str(first.account_id) == str(account["id"])
        assert first.source == "move_out"
        assert first.source_ref == result["move_no"]
        assert first.source_ref.startswith("MVO-")


# ── 2 · *No visit needed* is an ANSWER and it is kept ───────────────────────
@pytest.mark.django_db
def test_no_visit_needed_is_recorded_rather_than_discarded(dana, brazos):
    """`DEF-CUS-6363`'s rule, which the move-out never got: a clerk who said
    nobody has to attend is a DIFFERENT fact from a clerk who was never asked,
    and the PO kept the control on this screen for that reason on 2026-09-24
    (*"(a) Keep 'No visit needed'"*)."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)

        result = customers_services.move_out(
            dana, account["id"], {"moved_out_on": MOVE_OUT_DAY, "field_visit": {"none": True}}
        )

        assert result["field_visit_declined"] is True
        assert result["work_orders"] == []


# ── 3 · a row with no job type is refused BEFORE anything is written ────────
@pytest.mark.django_db
def test_a_row_with_no_job_type_is_refused_and_the_account_stays_open(dana, brazos):
    """The validation runs before the transaction opens, so the refusal costs
    the clerk nothing and the account is untouched — which is what makes it safe
    to validate at all on a money path."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)

        with pytest.raises(errors.ValidationError):
            customers_services.move_out(
                dana,
                account["id"],
                {"moved_out_on": MOVE_OUT_DAY, "field_visit": {"orders": [{"note": "no type"}]}},
            )

        # Read the ROW, not a response — the point of the case is that nothing
        # was written, and only the table can say that.
        row = customers_models.Account.objects.get(pk=account["id"])
        assert row.closed_at is None, "the account closed over a refused row"
        assert work_tables.WorkOrder.objects.filter(account_id=account["id"]).count() == 0


# ── 4 · the old shape still works, because a contract only ever widens ──────
@pytest.mark.django_db
def test_the_template_tick_still_raises_its_job(dana, brazos):
    """`{"template_ids": [...]}` is what every existing caller sends and what
    `CR-070` wave P built. Widening the parser must not cost it — this is the
    case that says the change is additive rather than a swap."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)
        template = _published_template(dana, name="Final read & deactivate")

        result = customers_services.move_out(
            dana,
            account["id"],
            {"moved_out_on": MOVE_OUT_DAY, "field_visit": {"template_ids": [template["id"]]}},
        )

        assert result["work_orders"], "the ticked template stopped being raised"
        assert result["field_visit_declined"] is False


# ── 5 · the two answers are exclusive, on this door as on the others ────────
@pytest.mark.django_db
def test_no_visit_needed_and_a_row_together_are_refused(dana, brazos):
    """`_field_visit` refuses the contradiction for every flow that uses it.
    Asserted HERE so the move-out's door cannot quietly go back to the parser
    that has no opinion about it."""
    with tenant_ctx(brazos):
        _premises, unit = _unit_with_plan(dana, brazos)
        account = _occupant(dana, unit)

        with pytest.raises(errors.ValidationError):
            customers_services.move_out(
                dana,
                account["id"],
                {
                    "moved_out_on": MOVE_OUT_DAY,
                    "field_visit": {"none": True, "orders": [{"type_id": "x"}]},
                },
            )

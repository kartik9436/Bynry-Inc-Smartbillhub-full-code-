# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (S16 default-plan panel) · US-CUS-003 (the account reads
#           its plan THROUGH the unit)   Screens: S16 · S21 · S23
# Rules:    BR-CUS-010 (one current plan per unit) · BR-CUS-011 (history rows
#           carry who/when/from→to/reason/source) · BR-CUS-013 (plan_version is
#           SNAPSHOT at assignment) · BR-CUS-014 (the unit plan is binding and
#           the account derives from it) · BR-MET-041 (bulk assignment writes a
#           row per unit) · BR-RAT-030 (only a published plan is assignable)
# Defect:   the PO's "gap 1", 2026-08-11 — `unit_plan_assignments` had existed
#           since W1 and was NEVER WRITTEN.
# ───────────────────────────────────────────────────────
"""The unit's plan history is actually written.

WHAT WAS BROKEN. `unit_plan_assignments` shipped in W1. Metering resolved a
writer for it through its seam; rating had never authored one; so the seam
returned None and every plan assignment came back `history_recorded: false`.
Honestly reported on every call — and still a hole, because the unit knew only
its CURRENT plan. A mid-cycle change could not be priced: billing needs "plan A
from the 1st to the 14th, plan B from the 15th", and an audit row carrying
before/after values is not something a bill run can calculate from.

WHY IT COULD NOT BE FIXED EARLIER, which is the part worth remembering. It was
not an oversight or a missing afternoon's work. This table stores a
`rate_plan_id`; `units.default_tariff_id` stored a TARIFF — one service's rate
schedule. Writing one into the other fails on the foreign key. The two halves
of the product disagreed about what a unit even holds, and no amount of care in
the writer could have reconciled them. The PO settled it on 2026-08-11 (a unit
holds a PLAN), and the writer became possible in the same change that repointed
the column.

WHAT THESE TESTS PIN. That a row is written at all (TC-1); that the previous
row is CLOSED so coverage has no gap and no overlap (TC-2) — the property
billing actually depends on; that the version is frozen at assignment so
editing the plan next year cannot restate what this unit was given (TC-3); that
bulk writes one row per unit (TC-4); that a superseded-before-it-started row is
kept as evidence rather than deleted (TC-5); and that a missing writer is now a
FAILURE rather than a status field (TC-6).
"""

from datetime import date

import pytest

from apps.metering import services
from apps.rating import models as rating_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db


def history_for(unit_id):
    """Every assignment row for a unit, oldest first."""
    return list(
        rating_models.UnitPlanAssignment.objects.filter(unit_id=unit_id).order_by(
            "assigned_from", "created_at"
        )
    )


def a_unit(actor, tenant, *, label="Unit A"):
    premises = make_premises(actor, address_line="1901 Bluestem Ln")
    return make_unit(actor, premises["id"], label=label, services=["electric"])


def test_us_met_003_tc1__assigning_a_plan_writes_the_history_row(brazos, dana):
    """The defect itself. Before this change, ZERO rows were ever written."""
    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        plan = make_plan(brazos, name="Residential")

        result = services.assign_unit_plan(
            dana,
            unit["id"],
            {"tariff_id": str(plan.id), "effective_from": "2026-06-01", "reason": "new build"},
        )

        assert result["history_recorded"] is True
        rows = history_for(unit["id"])
        assert len(rows) == 1
        row = rows[0]
        assert row.rate_plan_id == plan.id
        assert row.assigned_from == date(2026, 6, 1)
        assert row.assigned_to is None  # the CURRENT row (BR-CUS-010)
        # BR-CUS-011 — who, when, why, and by which path.
        assert row.source == "change_plan"
        assert row.reason == "new build"
        assert str(row.actor_id) == str(dana.id)


def test_us_met_003_tc2__the_previous_row_is_closed_the_day_before(brazos, dana):
    """The property billing depends on: coverage with no gap and no overlap.

    Sarah is on Residential from 1 Jun. On 15 Jun she qualifies for Senior.
    Her June bill must be 14 days of one plan and 16 of the other, so the
    history has to say Residential ran 1-14 Jun and Senior from the 15th. A
    single current-plan column can only ever say "Senior", which is what made
    a mid-cycle change unbillable.
    """
    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        residential = make_plan(brazos, name="Residential")
        senior = make_plan(brazos, name="Senior")

        services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(residential.id), "effective_from": "2026-06-01"}
        )
        services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(senior.id), "effective_from": "2026-06-15"}
        )

        rows = history_for(unit["id"])
        assert len(rows) == 2
        assert (rows[0].rate_plan_id, rows[0].assigned_from, rows[0].assigned_to) == (
            residential.id,
            date(2026, 6, 1),
            date(2026, 6, 14),  # the day BEFORE the successor starts
        )
        assert (rows[1].rate_plan_id, rows[1].assigned_from, rows[1].assigned_to) == (
            senior.id,
            date(2026, 6, 15),
            None,
        )
        # Exactly one open row per unit — the partial unique index in force.
        assert sum(1 for row in rows if row.assigned_to is None) == 1


def test_us_met_003_tc3__the_plan_version_is_frozen_at_assignment(brazos, dana):
    """BR-CUS-013 — editing the plan later must not restate history.

    A bill reprinted in two years has to resolve the prices this unit actually
    had, not whatever the plan says by then.
    """
    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        plan = make_plan(brazos, name="Residential")
        assert plan.version == 1

        services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-06-01"}
        )

        # The plan is edited afterwards — a new version of the same plan.
        plan.version = 7
        plan.save(update_fields=["version"])

        row = history_for(unit["id"])[0]
        assert row.plan_version == 1  # SNAPSHOT, not a live read
        assert row.rate_plan_id == plan.id  # still the same plan


def test_us_met_003_tc4__bulk_assignment_writes_a_row_for_every_unit(brazos, dana):
    """BR-MET-041 — bulk is not a shortcut past the history."""
    with tenant_ctx(brazos):
        first = a_unit(dana, brazos, label="Unit A")
        second = a_unit(dana, brazos, label="Unit B")
        plan = make_plan(brazos, name="Residential")

        result = services.bulk_assign_unit_plans(
            dana,
            {
                "unit_ids": [str(first["id"]), str(second["id"])],
                "tariff_id": str(plan.id),
                "effective_from": "2026-06-01",
            },
        )

        assert result["assigned"] == 2 and result["failed"] == 0
        for unit in (first, second):
            rows = history_for(unit["id"])
            assert len(rows) == 1
            assert rows[0].source == "bulk_update"


def test_us_met_003_tc5__a_plan_replaced_before_it_started_is_kept_as_evidence(brazos, dana):
    """Correcting a plan on the day it was set is ordinary, not an error.

    An earlier draft of the writer REFUSED this, and its own tests caught it
    within a minute: it rejected same-day corrections and the replacement of a
    future-dated assignment, which are the two commonest reasons staff touch
    this screen at all. Both are now allowed.

    The withdrawn row is CLOSED, never deleted — the table is append-only and
    the row is the evidence that the assignment was made and withdrawn, with
    its actor. It carries `assigned_to < assigned_from`, which is how a reader
    tells "never in force" from "in force and ended".
    """
    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        wrong = make_plan(brazos, name="Residential")
        right = make_plan(brazos, name="Senior")

        services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(wrong.id), "effective_from": "2026-06-01"}
        )
        services.assign_unit_plan(
            dana, unit["id"], {"tariff_id": str(right.id), "effective_from": "2026-06-01"}
        )

        rows = history_for(unit["id"])
        assert len(rows) == 2  # the mistake is not erased
        withdrawn = next(row for row in rows if row.rate_plan_id == wrong.id)
        assert withdrawn.assigned_to < withdrawn.assigned_from  # never in force
        in_force = [row for row in rows if row.assigned_to is None]
        assert len(in_force) == 1 and in_force[0].rate_plan_id == right.id


def test_us_met_003_tc6__a_missing_history_writer_is_a_failure_not_a_status(
    brazos, dana, monkeypatch
):
    """`history_recorded: false` must never come back again.

    For months that field reported, accurately, that no row had been written —
    and the assignment committed anyway. The unit's plan column moved while its
    coverage did not, which is a hole that only surfaces months later inside a
    bill. Now the two move together or neither does.
    """
    from apps.metering import seams

    monkeypatch.setattr(seams, "record_unit_plan_assignment", lambda **kwargs: None)

    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        plan = make_plan(brazos, name="Residential")

        with pytest.raises(errors.BizError) as raised:
            services.assign_unit_plan(
                dana, unit["id"], {"tariff_id": str(plan.id), "effective_from": "2026-06-01"}
            )
        assert raised.value.br_ref == "BR-CUS-013"


def test_us_met_003_tc7__an_unpublished_plan_cannot_be_assigned(brazos, dana):
    """BR-RAT-030 — a draft plan has no prices a bill could be produced from."""
    with tenant_ctx(brazos):
        unit = a_unit(dana, brazos)
        draft = make_plan(brazos, name="Residential")
        draft.status = "draft"
        draft.save(update_fields=["status"])

        with pytest.raises(errors.ValidationError):
            services.assign_unit_plan(dana, unit["id"], {"tariff_id": str(draft.id)})

        assert history_for(unit["id"]) == []  # nothing written on a refusal


# ── Lifecycle ─────────────────────────────────────────────
# packet: US-MET-003 (EP-MET-01) — PO gap-1 remediation 2026-08-11, enabled by
#         the same day's ruling that a unit holds a PLAN
# generated: 2026-08-11 by Eng-Lead
# checklist: A✔ B✔ C✔ D=deferred(service-layer — the API inherits it) E=deferred(no UI change) F✔ G✔ H=deferred(PO 2026-08-09)
# gates: proved RED before green, twice.
#         (1) Restoring the pre-2026-08-11 state — no history writer called —
#             fails TC-1..TC-6. Only TC-7 survives, correctly: it asserts a
#             REFUSAL leaves no row behind, which an empty table also satisfies.
#             That one is carried by the other six, not by itself.
#         (2) Removing the row-closing line fails TC-2 and TC-5 — but NOT by
#             the assertion I wrote. The database gets there first: the partial
#             unique index (one open row per unit) raises IntegrityError before
#             any assertion runs. Recorded exactly as observed rather than as
#             intended, because it says something better than the assertion
#             would have — the schema itself refuses two open rows, so the
#             un-billable "no coverage end date" state cannot be reached even
#             if this service logic were rewritten wrongly.
# exceptions: backdating behind an ALREADY-ISSUED bill is NOT guarded — the
#         same guard move-out carries belongs on this path, and cannot be
#         written until billing has an `invoices` table to ask. REPORTED in
#         apps/rating/services.record_unit_plan_assignment, not implied safe.
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

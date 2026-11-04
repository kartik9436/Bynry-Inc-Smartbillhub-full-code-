# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-002 (S15 units)   Change: CR-024 (PO 2026-08-21)
# Rules:    BR-MET-095 (a unit MAY move, and the move is a DATED EVENT —
#           SUPERSEDES-REFINES BR-MET-046) · BR-MET-035 (create/edit = System
#           Admin + Billing Clerk) · BR-MET-002 (a unit label is unique within
#           its premise) · BR-MET-048 / hard rule 7 (every change is audited)
# Note:     BR-MET-046 used to REFUSE this outright, and the refusal is still
#           tested next door — `update_unit` still raises BIZ-IMMUTABLE on a
#           `premises_id` in an ordinary PATCH. The move is its own service,
#           its own route and its own set of refusals, which is the whole
#           point: a move is a deliberate act with a date and a reason, never
#           a field somebody can set by accident.
# ───────────────────────────────────────────────────────
"""BR-MET-095 — moving a unit to another premise."""

import pytest

from apps.metering import services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, make_unit, tenant_ctx

pytestmark = pytest.mark.django_db

TODAY = "2026-08-21"


def _two_premises(actor):
    first = make_premises(actor, address_line="1408 Bluestem Ln")
    second = make_premises(actor, address_line="2201 Cane Island Pkwy")
    return first, second


def test_br_met_095_tc1__a_never_billed_unit_moves_and_the_audit_row_names_both_premises(
    brazos, dana, audit_rows
):
    """The correction case: a unit that has never had an account just moves."""
    with tenant_ctx(brazos):
        source, target = _two_premises(dana)
        unit = make_unit(dana, source["id"], label="Unit A")

        moved = services.move_unit(
            dana,
            unit["id"],
            {
                "premises_id": target["id"],
                "effective_date": TODAY,
                "reason": "Loaded against the wrong address in the migration.",
            },
        )

        assert moved["premises_id"] == target["id"]
        # ⚠ THE AUDIT ROW IS THE ONLY RECORD OF THE MOVE — `units` has no dated
        # move history — so it must carry BOTH premises, the date and the
        # reason. A move whose row named only the destination would be
        # unreadable six months later, which is the thing the rule is about.
        rows = [row for row in audit_rows if row["action"] == "unit.moved"]
        assert len(rows) == 1
        move = rows[0]["after"]["move"]
        assert move["from_premises_id"] == source["id"]
        assert move["to_premises_id"] == target["id"]
        assert move["effective_date"] == TODAY
        assert move["reason"].startswith("Loaded against the wrong address")
        assert move["br_ref"] == "BR-MET-095"


def test_br_met_095_tc2__the_three_required_fields_are_each_refused_by_name(brazos, dana):
    """A move with no reason, no date, or no destination is refused — and each
    refusal names its own field rather than a generic 'invalid payload'."""
    with tenant_ctx(brazos):
        source, target = _two_premises(dana)
        unit = make_unit(dana, source["id"])

        cases = [
            ({"effective_date": TODAY, "reason": "x"}, "metering.unit.premises_required"),
            (
                {"premises_id": target["id"], "reason": "x"},
                "metering.unit.move_date_required",
            ),
            (
                {"premises_id": target["id"], "effective_date": TODAY},
                "metering.unit.move_reason_required",
            ),
        ]
        for payload, key in cases:
            with pytest.raises(errors.ValidationError) as caught:
                services.move_unit(dana, unit["id"], payload)
            assert caught.value.message_key == key


def test_br_met_095_tc3__a_future_effective_date_is_refused_rather_than_applied(brazos, dana):
    """⚠ THE ONE REFUSAL THAT IS ABOUT WHAT THIS PRODUCT CANNOT DO.

    `units` holds ONE `premises_id` and no dated move history, so a future date
    would be accepted, applied immediately, and then read by everyone as
    scheduled. Refusing it by name is the honest shape until a dated move
    history is a story somebody owns.
    """
    with tenant_ctx(brazos):
        source, target = _two_premises(dana)
        unit = make_unit(dana, source["id"])
        with pytest.raises(errors.ValidationError) as caught:
            services.move_unit(
                dana,
                unit["id"],
                {
                    "premises_id": target["id"],
                    "effective_date": "2099-01-01",
                    "reason": "next year",
                },
            )
        assert caught.value.message_key == "metering.unit.move_date_future"
        # …and nothing moved.
        from apps.metering import selectors

        assert selectors.unit_detail_dict(services._unit_row(unit["id"]))[  # noqa: SLF001
            "premises_id"
        ] == source["id"]


def test_br_met_095_tc4__moving_onto_the_same_premise_is_refused_as_a_non_event(brazos, dana):
    """A no-op in the audit trail is worse than no row at all."""
    with tenant_ctx(brazos):
        source, _target = _two_premises(dana)
        unit = make_unit(dana, source["id"])
        with pytest.raises(errors.BizError) as caught:
            services.move_unit(
                dana,
                unit["id"],
                {"premises_id": source["id"], "effective_date": TODAY, "reason": "x"},
            )
        assert caught.value.message_key == "metering.unit.move_same_premises"


def test_br_met_095_tc5__a_label_collision_on_the_destination_is_refused_before_the_write(
    brazos, dana
):
    """BR-MET-002 / `uq_units_tenant_premises_label`. Caught in the service so
    the caller gets a sentence naming the premise, not an IntegrityError."""
    with tenant_ctx(brazos):
        source, target = _two_premises(dana)
        unit = make_unit(dana, source["id"], label="Unit A")
        make_unit(dana, target["id"], label="Unit A")
        with pytest.raises(errors.ValidationError) as caught:
            services.move_unit(
                dana,
                unit["id"],
                {"premises_id": target["id"], "effective_date": TODAY, "reason": "x"},
            )
        assert caught.value.message_key == "metering.unit.label_duplicate"


def test_br_met_095_tc6__an_ordinary_patch_still_refuses_a_premises_change(brazos, dana):
    """⚠ THE HALF OF BR-MET-046 THAT DID NOT CHANGE, ASSERTED SO IT CANNOT DRIFT.

    The rule was SUPERSEDED-REFINED, not deleted: a unit may move, but only
    through the move service, with a date and a reason. `PATCH /units/{id}` must
    still refuse a `premises_id`, or the deliberate act becomes a field.
    """
    with tenant_ctx(brazos):
        source, target = _two_premises(dana)
        unit = make_unit(dana, source["id"])
        with pytest.raises(errors.BizError) as caught:
            services.update_unit(dana, unit["id"], {"premises_id": target["id"]})
        assert caught.value.message_key == "metering.unit.premises_immutable"
        assert caught.value.br_ref == "BR-MET-046"


# ── Lifecycle ─────────────────────────────────────────────
# packet: CR-024 (PO 2026-08-21) · BR-MET-095 · BR-MET-042's override precedent
# generated: 2026-08-21 by the CR-023 P0-P2 lane, taking CR-024 as an addition
# checklist: A✔ B✔ C✔ D✔ E✔ F✔ G✔ H=deferred(PO 2026-08-09)
# gates: pytest tests/test_br_met_095_unit_move.py✔
# exceptions: E3 **THE OVERRIDE PATH IS NOT ASSERTED HERE AND THE REASON IS
#         MEASURABLE.** `accounts_ever_attached` comes from
#         `seams.account_reference_count`, which resolves into the CUSTOMERS
#         module; these fixtures provision metering only, so the count is 0 by
#         construction and the BIZ-APPROVAL branch cannot be reached without
#         seeding an account through another module's services. The branch is
#         covered on the SCREEN side instead (UnitsPage.test.tsx asserts the
#         refusal copy and that the acknowledgement panel is drawn only from the
#         server's own answer), and the gap is stated rather than faked with a
#         monkeypatched seam that would assert this test's own stub
# status: VERIFIED-UNRATIFIED
# ──────────────────────────────────────────────────────────

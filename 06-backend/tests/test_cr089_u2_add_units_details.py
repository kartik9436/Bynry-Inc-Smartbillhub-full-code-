# ── Trace ──────────────────────────────────────────────
# Change:   CR-089 U2 — the Add units · Details step against its drawn frame.
# Drawn:    04-docs/05-modules/04-metering/conformance/CR-089-p053-add-units-details.md
#           §4 (`Floor`, `Or add a common area instead`) · §8 (the states)
# Story:    US-MET-003 (guided add)   Screens: S16 (the add-units half)
# Rules:    BR-MET-101 (a common area is a unit with a FLAG, and the flag is a
#           STRICT boolean) · BR-MET-005/031 (the pattern generator) ·
#           BR-MET-007 (a unit's default plan, at creation, optional)
# ───────────────────────────────────────────────────────
"""What the units PATTERN generator carries into the units it creates.

**WHY THIS FILE EXISTS.** The frame draws `Floor` and `Or add a common area
instead` on the Details step, and neither could be built: `create_unit` has
accepted `floor_label` and `is_common_area` since `_validate_unit` was written,
and `_stage_pattern` simply never put them in the staged row. Every unit the
wizard made had an empty floor and no wizard could make a common area at all.

**WHAT COULD PASS WRONGLY, so it is what the cases below ask about.** A staging
assertion alone would be worth nothing: the row is a dict, and putting a key in
a dict proves nothing about the unit that comes out the other end. Each case
therefore STAGES AND COMMITS, and reads the created row back out of the
database — which is the only form that can tell a forwarded field from one
`create_unit` silently ignores.
"""

import pytest

from apps.metering import importers, models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_premises, tenant_ctx

pytestmark = pytest.mark.django_db


def _spec(premises, **over):
    spec = {
        "premises_id": str(premises["id"]),
        "floors": 1,
        "units_per_floor": 2,
        "label_pattern": "{seq}",
    }
    spec.update(over)
    return {"kind": "units_pattern", "pattern": spec, "options": {"skip_errors": False}}


def _run(actor, payload):
    staged = importers.stage(payload)
    return importers.commit(actor, payload, staged)


def test_the_floor_the_clerk_chose_is_on_every_unit_the_run_creates(dana, brazos):
    """§4 row 4 — `Floor`, the floor LABEL for the units being made."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        result = _run(dana, _spec(premises, floor_label="3"))
        assert result["summary"]["created"] == 2
        made = models.Unit.objects.filter(tenant_id=brazos.id, premises_id=premises["id"])
        assert sorted(u.floor_label for u in made) == ["3", "3"]


def test_no_floor_chosen_leaves_it_UNRECORDED_rather_than_blank_string(dana, brazos):
    """The drawn default is `Not recorded`, and the review draws it as an
    ABSENCE. An empty string would be a floor label that is the empty string —
    a different fact from *nobody said*, and one no screen can draw as absent."""
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _run(dana, _spec(premises))
        made = models.Unit.objects.filter(tenant_id=brazos.id, premises_id=premises["id"])
        assert [u.floor_label for u in made] == [None, None]
        # …and the same for a control the clerk cleared rather than never touched.
        premises2 = make_premises(dana, address_line="9 Mill Race")
        _run(dana, _spec(premises2, floor_label="   "))
        made2 = models.Unit.objects.filter(tenant_id=brazos.id, premises_id=premises2["id"])
        assert [u.floor_label for u in made2] == [None, None]


def test_a_common_area_made_here_carries_the_FLAG_and_not_only_the_type(dana, brazos):
    """§4 row 6 — `Or add a common area instead`.

    `BR-MET-101` makes `is_common_area` the fact and `unit_type` the legacy
    typing, so a run that set only the type would produce a laundry room that
    every screen reads as somebody's flat — and bills to a resident who does not
    exist.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _run(
            dana,
            _spec(
                premises,
                units_per_floor=1,
                label_pattern="Laundry",
                unit_type="common_area",
                is_common_area=True,
            ),
        )
        made = models.Unit.objects.get(tenant_id=brazos.id, premises_id=premises["id"])
        assert made.label == "Laundry"
        assert made.is_common_area is True


def test_a_run_that_says_nothing_about_common_areas_flags_nothing(dana, brazos):
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        _run(dana, _spec(premises))
        made = models.Unit.objects.filter(tenant_id=brazos.id, premises_id=premises["id"])
        assert [u.is_common_area for u in made] == [False, False]


def test_a_NON_BOOLEAN_flag_is_refused_by_name_rather_than_read_as_truthy(dana, brazos):
    """`BR-MET-101`'s strict-boolean guard, reached through the GENERATOR.

    The string `"false"` is truthy in Python. A generator that coerced here
    would flag a unit somebody lives in as shared space and bill it to the
    owner, and the refusal that exists to stop that would never run.
    """
    with tenant_ctx(brazos):
        premises = make_premises(dana)
        result = _run(dana, _spec(premises, is_common_area="false"))
        assert result["summary"]["created"] == 0
        assert models.Unit.objects.filter(tenant_id=brazos.id, premises_id=premises["id"]).count() == 0

# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave E task 23 — "fill the fields the import takes and the
#          seed skips". PO 2026-08-26, verbatim: *"when we add premises - we
#          ahve to capture few more details - as we did in import today - is
#          you data align with import - same is the case with Units"*
# Rules:   BR-MET-139 (the measurement, the `state` fill and the six stated
#          refusals) · BR-MET-088 (the importer's offered set IS the model's
#          columns, never a hand-kept list) · DEF-444 (`tenants.state`)
# Defects: DEF-838 (a hardcoded `"state": None` on every seeded premises)
# Questions: OQ-429 (floor / square feet) · OQ-430 (building name / legacy
#          key) · OQ-431 (plan lock / vacant standby) — MINTED, not answered
# ───────────────────────────────────────────────────────
"""**THE MEASUREMENT IS THE DELIVERABLE, so it is a test rather than a report.**

A report saying *"the seeder fills 13 of 16 premises columns"* is true on the
day it is written and silently wrong the day somebody adds a seventeenth. This
file pins the comparison itself: which columns the IMPORTER offers, which ones
the SEEDER writes, and — for each of the six it does NOT write — that leaving it
blank is a recorded decision with a question behind it rather than an oversight.

⚠ **THE FILLED / REFUSED SPLIT IS DELIBERATELY ASSERTED IN BOTH DIRECTIONS.**
A test that only checked the filled ones would go green the day a lane quietly
seeds `square_feet: 1200` to "finish the job", which is exactly the failure
`sample_fixture`'s spec rule 7 exists to prevent: *"Where a rule is unsigned,
the seeder stubs and mints a question rather than choosing a number that then
looks official."* A seeded value nobody chose is worse than a blank, because a
demo makes it look decided.
"""

from __future__ import annotations

import pytest

from apps.metering import import_runs
from apps.metering import models as met_models
from apps.metering import sample_data as met_sample
from apps.metering import selectors as met_selectors
from apps.tenancy import sample_data as ten_sample
from apps.tenancy import services as ten_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    brazosbend_payload,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


# ═══════════════════════════════════════════════════════════════════════════
# THE MEASUREMENT — BR-MET-139's table, as code
# ═══════════════════════════════════════════════════════════════════════════

#: Premises columns the SEEDER writes. `premise_no` is absent on purpose: it is
#: allocated from the number series, which is its source, not a gap.
#: `lat` / `lng` are written by `apply_premises_geo` rather than in the payload —
#: they count, because the question is what the ROW ends up holding.
PREMISES_FILLED = {
    "address_line",
    "city",
    "state",  # ← DEF-838, closed by this wave
    "postal_code",
    "premises_type",
    "services_available",
    "area",
    "owner_manager",
    # ⚠ **ADDED 2026-08-30 — `owner` IS A COLUMN NOW AND THE SEEDER FILLS IT.**
    # `DEF-650` (PO 2026-08-27, *"Bascially Premises -> owner = Master
    # account"*) added the TYPED owner party as a real FK on `premises`, and
    # `sample_data._sample_owner_id` links one per seeded address — reusing the
    # party by name, and creating none where the fixture states no category
    # (`test_cr039_c14__no_seeded_owner_has_an_INVENTED_category`). The legacy
    # free text `owner_manager` stays beside it under BR-MET-151 clause 4, so
    # both are filled and neither is the other's replacement.
    "owner",
    "lat",
    "lng",
    "status",
}

#: Premises columns the seeder deliberately does NOT write, each with the
#: sentence that says why. ⚠ A field moving out of this dict without its
#: question being CLOSED first is the thing this file is here to catch.
PREMISES_REFUSED = {
    "name": (
        "the fixture names no BUILDING. Its three names — Mill Pond Apartments LP, "
        "Creekside Laundromat, Quarry Hill Diner — are OWNER/MANAGER entities, and "
        "copying an owner's legal name into a building-name column states something "
        "nobody said. OQ-430"
    ),
    "external_ref": (
        "a legacy key ASSERTS a prior system, and nothing in the fixture names one. "
        "B15 §4.2A #12 makes this column load-bearing for reconciliation, which is "
        "why it is a QUESTION rather than a shrug. OQ-430"
    ),
    "inside_city_limits": (
        "CR-039 WAVE C, not this one. Jurisdiction decides an outside-city surcharge "
        "on every bill at an address (CR-039 finding 3) and a lane is building the "
        "write side now; seeding a value here would collide with it."
    ),
    "custom_data": (
        "NOT A GAP. These are the TENANT's own defined fields (B15 §4.2A #14) and a "
        "fresh tenant has none, so there is nothing to fill."
    ),
    "premise_no": ("NOT A GAP. Allocated from the `premises` number series, which IS its source."),
}

#: Unit columns the seeder writes. `premises` is the parent link, carried by the
#: nested payload rather than as a field.
UNITS_FILLED = {
    "premises",
    "unit_no",
    "label",
    "unit_type",
    "rate_plan",
    "plan_effective_from",
    "is_common_area",  # the W6 common area, DEF-709 — one unit, deliberately
}

UNITS_REFUSED = {
    "floor_label": (
        "no source states a floor for any of the 48 units. Deriving one from the "
        "apartment numbering (Apt 101–106 → floor 1) asserts a single-storey building "
        "nobody described. OQ-429"
    ),
    "square_feet": (
        "the demo-tenant spec §2 declares the 44/48 mix and no dimensions, and r10's "
        "980 / 920 / 1,480 sq ft belong to r10's OWN addresses. OQ-429"
    ),
    "plan_locked": (
        "a lock is a STAFF DECISION about a specific unit, not a figure that can be "
        "derived. The fixture has no such story. OQ-431"
    ),
    "vacant_standby_auto": ("as above — a policy nobody has stated for this demo utility. OQ-431"),
    "custom_data": ("NOT A GAP — the tenant's own defined fields; a fresh tenant has none."),
    # ⚠ **ADDED 2026-08-30.** `units.external_ref` did not exist when this file
    # was written; CR-046 C5 added it (migration metering 0042, BR-MET-404) and
    # the offered set is derived from the model, so the column arrived offered
    # and unaccounted. The refusal is the SAME one premises' `external_ref`
    # already carries, for the same reason and under the same question.
    "external_ref": (
        "a legacy key ASSERTS a prior system, and nothing in the fixture names one. "
        "B15 §4.2A #12 makes this column load-bearing for reconciliation, which is "
        "why it is a QUESTION rather than a shrug. OQ-430"
    ),
}


def _offered(target: str) -> set[str]:
    """The importer's own offered set, read the way the PICKER reads it.

    ⚠ Derived from `Premises._meta` / `Unit._meta` under BR-MET-088, so this
    measurement cannot go stale against a column added tomorrow — a new column
    is offerable the day it exists and lands in neither set below, which is
    what makes the two assertions in `test_every_offered_column_is_accounted_for`
    fail rather than quietly under-report.
    """
    model = import_runs._model_for(target)
    return {
        field.name
        for field in model._meta.get_fields()
        if getattr(field, "concrete", False) and field.name not in import_runs.NEVER_IMPORTABLE
    }


def test_the_premises_importer_offers_seventeen_columns() -> None:
    """The headline figure BR-MET-139 records, so a change to it is visible.

    ⚠ **SIXTEEN BECAME SEVENTEEN ON 2026-08-30, AND THAT IS THIS TEST WORKING.**
    `DEF-650` gave `premises` its typed `owner` FK (PO 2026-08-27, *"Bascially
    Premises -> owner = Master account"*), the offered set is DERIVED from the
    model under BR-MET-088, and the column therefore arrived offered before
    anybody came here. It is now in `PREMISES_FILLED` — the seeder writes it.
    """
    assert len(_offered(import_runs.TARGET_PREMISES)) == 17


def test_the_units_importer_offers_thirteen_columns() -> None:
    """⚠ **TWELVE BECAME THIRTEEN ON 2026-08-30**, for the same mechanism one
    noun along: CR-046 C5 added `units.external_ref` (metering 0042,
    BR-MET-404). It is in `UNITS_REFUSED`, under OQ-430 — the same open question
    premises' own `external_ref` waits on.
    """
    assert len(_offered(import_runs.TARGET_UNITS)) == 13


def test_every_offered_column_is_accounted_for() -> None:
    """**THE WHOLE POINT.** Every column the importer offers is either written
    by the seeder or refused BY NAME with a reason — there is no third state,
    and a column nobody has considered is what this asserts cannot exist.

    A seventeenth premises column added tomorrow lands in neither set and this
    goes RED naming it, which is the DEF-616 shape (the shipped sample gained
    `lat`/`lng` and the hand-kept alias table did not move) applied to the
    seeder instead of to the header detector.
    """
    for target, filled, refused in (
        (import_runs.TARGET_PREMISES, PREMISES_FILLED, PREMISES_REFUSED),
        (import_runs.TARGET_UNITS, UNITS_FILLED, UNITS_REFUSED),
    ):
        offered = _offered(target)
        accounted = filled | set(refused)
        assert offered - accounted == set(), (
            f"{target}: the importer offers a column the seeder neither writes nor "
            f"refuses by name — {sorted(offered - accounted)}"
        )
        assert accounted - offered == set(), (
            f"{target}: this file names a column the importer does not offer — "
            f"{sorted(accounted - offered)}"
        )
        # A refusal with no sentence is the DEF-016 shape: a gap nobody wrote down.
        for column, reason in refused.items():
            assert len(reason.split()) >= 8, f"{target}.{column}: refusal says too little"


def test_every_refused_field_names_its_question_or_says_why_it_is_not_a_gap() -> None:
    """Spec rule 7, enforced. A field left blank is a DECISION with a question
    behind it, or it is an oversight — and the two must not read alike."""
    for refused in (PREMISES_REFUSED, UNITS_REFUSED):
        for column, reason in refused.items():
            assert (
                "OQ-" in reason or "NOT A GAP" in reason or "WAVE C" in reason
            ), f"{column}: blank with no question and no reason is an oversight"


# ═══════════════════════════════════════════════════════════════════════════
# DEF-838 — `state` is the tenant's own, or nothing
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture()
def seeded(identity_seam, settings):
    settings.JOBS_EAGER = True
    tenant, _ = provisioned_tenant(brazosbend_payload())
    with tenant_ctx(tenant):
        ten_sample.seed_sample_data(admin_actor())
        yield tenant


def test_a_seeded_premises_carries_the_tenants_own_state(seeded) -> None:
    """DEF-838. `brazosbend_payload` declares a state, so every seeded premises
    must carry THAT one — never a literal from this fixture."""
    declared = ten_services.selectors.regional_settings()["state"]
    assert declared, "the test tenant declares no state; this assertion proves nothing"
    rows = list(met_selectors.premises_list())
    assert rows
    assert {row.state for row in rows} == {declared}


def test_a_tenant_with_no_state_gets_premises_with_no_state(identity_seam, settings) -> None:
    """**THE HALF THAT KEEPS THIS HONEST.** `tenants.state` is not required at
    signup (DEF-444 is the whole story of what happens when it is missing), so
    a tenant that never named one must get blank premises — not a plausible
    `TX` picked because the fixture's map anchors happen to sit in Austin."""
    settings.JOBS_EAGER = True
    payload = brazosbend_payload(subdomain="stateless-demo")
    payload.pop("state", None)
    tenant, _ = provisioned_tenant(payload)
    with tenant_ctx(tenant):
        assert not tenant.state, "this tenant was supposed to declare no state"
        ten_sample.seed_sample_data(admin_actor())
        rows = list(met_selectors.premises_list())
        assert rows
        assert {row.state for row in rows} == {None} or {row.state for row in rows} == {""}


def test_the_seeder_holds_no_hardcoded_state_literal() -> None:
    """The mechanism, not only the outcome. All THREE seeding paths carried
    `"state": None` — the 44-premises estate, the CR-030 estate and the W6/W7
    seats — and fixing one would have left a demo that is right on 44 rows and
    blank on the rest."""
    import inspect

    source = inspect.getsource(met_sample)
    assert '"state": None' not in source, "a seeding path still hardcodes a null state"
    assert (
        source.count("seams.tenant_state()") == 3
    ), "all three seeding paths must read the tenant's own state"


def test_the_six_refused_columns_really_are_empty_on_the_demo(seeded) -> None:
    """The refusals, on real rows rather than in a dict. If a later lane seeds
    `square_feet` without closing OQ-429, this is what says so."""
    premises = list(met_selectors.premises_list())
    assert premises
    assert {row.name for row in premises} == {None} or {row.name for row in premises} == {""}
    assert {row.external_ref for row in premises} in ({None}, {""})

    units = met_models.Unit.objects.filter(tenant_id=seeded.id)
    assert units.exists()
    assert not units.exclude(floor_label__isnull=True).exclude(floor_label="").exists()
    assert not units.filter(square_feet__isnull=False).exists()
    assert not units.filter(plan_locked=True).exists()
    assert not units.filter(vacant_standby_auto=True).exists()

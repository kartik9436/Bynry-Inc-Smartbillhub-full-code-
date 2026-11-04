# ── Trace ──────────────────────────────────────────────
# Story:    US-MET-003 (the meter grid on the guided add) · US-AST-010's
#           successor, the WFL-01 assets_meters target (CR-028 AST-W3)
# Rules:    BR-MET-119 (PREMISES → UNITS → METERS: a premises DECLARES the
#           services available at the address, a unit INHERITS that list, and a
#           meter may only attach against one of them — PO 2026-08-26, CR-036,
#           verbatim *"Refuse it ; if they want that servcie then they ahve to
#           provision it on that unit or premise first"*) ·
#           BR-MET-003 (⊆ the tenant's enabled services — the OUTER bound,
#           unchanged and still asked FIRST)
# Defects:  DEF-772 (the third link was unenforced: a gas meter attached to a
#           unit at a water/sewer/trash address whenever the utility sold gas
#           somewhere) · DEF-756 (no screen could write a premises' services
#           until 2026-08-26, so every premises built through the product holds
#           NULL — the never-asked case is the COMMON case on day one)
# ───────────────────────────────────────────────────────
"""BR-MET-119 — the third link of the chain REFUSES.

⚠ **THE FIXTURE IS THE POINT OF THIS FILE.** Every asset fixture in the repo
sits at a premises whose `services_available` already covers the meter, so the
tenant-enabled check and the premises check are INDISTINGUISHABLE across the
whole suite (DEF-772's `escape_reason`). `water_only_address` below is the first
fixture in the tree that separates them: Brazos Bend SELLS electric (so
`BR-MET-003` passes), and the address at 77 Cypress Way offers WATER ONLY (so
`BR-MET-119` refuses). A test written on any other fixture proves nothing about
which of the two checks fired.
"""

import pytest

from apps.metering import models, seams, services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    make_premises,
    make_unit,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def water_only_address(brazos, dana):
    """THE SEPARATING FIXTURE: a water-only address under a utility that sells
    electric. Returns (premises, unit)."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="77 Cypress Way", services_available=["water"]
        )
        unit = make_unit(dana, premises["id"], label="Unit W")
    return premises, unit


@pytest.fixture()
def never_asked_address(brazos, dana):
    """The DEF-756 state: a premises nobody has been asked about — `NULL`, not
    an empty list. Returns (premises, unit)."""
    with tenant_ctx(brazos):
        premises = make_premises(
            dana, address_line="12 Anhinga Trail", services_available=None
        )
        unit = make_unit(dana, premises["id"], label="Unit N")
    return premises, unit


def test_the_fixture_actually_separates_the_two_checks(brazos, water_only_address):
    """Without this, nothing below proves anything (DEF-772)."""
    premises, _unit = water_only_address
    with tenant_ctx(brazos):
        assert "electric" in seams.enabled_service_codes(), "the utility DOES sell electric"
    assert premises["services_available"] == ["water"], "the ADDRESS does not offer it"


def test_tc1_a_meter_for_a_service_the_address_does_not_offer_is_refused(
    brazos, water_only_address
):
    """BR-MET-119 — REFUSE, and say what the address does offer."""
    premises, unit = water_only_address
    with tenant_ctx(brazos):
        before = models.ServicePoint.objects.filter(unit_id=unit["id"]).count()
        with pytest.raises(errors.ValidationError) as caught:
            services.ensure_service_point(unit["id"], "electric")
        assert caught.value.message_key == "metering.service_not_at_premises"
        assert caught.value.params["service"] == "electric"
        assert caught.value.params["offered"] == "water"
        assert caught.value.params["premises"] == premises["premise_no"]
        assert caught.value.field_errors[0]["field"] == "service"
        assert models.ServicePoint.objects.filter(unit_id=unit["id"]).count() == before


def test_tc2_an_address_nobody_has_been_asked_about_is_refused_too(
    brazos, never_asked_address
):
    """The never-asked case REFUSES as well (PO 2026-08-26) — and the sentence
    says so rather than claiming the address offers nothing."""
    premises, unit = never_asked_address
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError) as caught:
            services.ensure_service_point(unit["id"], "electric")
        assert caught.value.message_key == "metering.premises_services_unknown"
        assert caught.value.params["service"] == "electric"
        assert caught.value.params["premises"] == premises["premise_no"]
        assert "offered" not in caught.value.params
        assert models.ServicePoint.objects.filter(unit_id=unit["id"]).count() == 0


def test_tc3_a_service_the_address_does_offer_still_passes(brazos, water_only_address):
    """The check must not over-refuse: water at a water address is the whole
    point of the chain."""
    _premises, unit = water_only_address
    with tenant_ctx(brazos):
        point_id = services.ensure_service_point(unit["id"], "water")
        assert models.ServicePoint.objects.filter(pk=point_id, unit_id=unit["id"]).exists()


def test_tc4_the_tenant_bound_is_still_asked_first(brazos, dana):
    """BR-MET-003 stays the OUTER bound. A premises row carrying a service the
    utility does not sell (only reachable by writing round the validator) is
    still refused for the ORIGINAL reason — the utility does not sell it."""
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="4 Egret Row", services_available=["water"])
        models.Premises.objects.filter(pk=premises["id"]).update(
            services_available=["water", "gas"]
        )
        unit = make_unit(dana, premises["id"], label="Unit G")
        assert "gas" not in seams.enabled_service_codes()
        with pytest.raises(errors.ValidationError) as caught:
            services.ensure_service_point(unit["id"], "gas")
        assert caught.value.message_key == "metering.service_not_enabled"


def test_tc5_the_premises_read_is_tenant_scoped(brazos, lonestar, dana):
    """CLAUDE.md hard rule 1. The premises behind a unit is read WITH the
    tenant filter: a row belonging to another tenant is not visible, and its
    service list may not decide what this tenant's meter may attach to.

    Built by pointing a Brazos unit at a Lone Star premises row — the FK
    carries no tenant, so only the filter stands between the two.
    """
    from tests.test_us_met_helpers import staff_actor

    with tenant_ctx(lonestar):
        lsr_actor = staff_actor(lonestar, "system_admin", "admin@lonestarridge.test")
        foreign = make_premises(
            lsr_actor, address_line="9 Ridge Rd", services_available=["water"]
        )
    with tenant_ctx(brazos):
        premises = make_premises(dana, address_line="5 Heron Ct", services_available=["water"])
        # ⚠ **`services=[]` IS A DELIBERATE UNTICK AND IT IS WHAT KEEPS THE
        # ASSERTION BELOW ABOUT THE TENANT FILTER (`DEF-MET-6796`, 2026-09-25).**
        # Since `BR-MET-119` was amended, a unit created without a `services`
        # key INHERITS its premises' offer — so this unit would arrive already
        # holding the water point, and `count() == 0` would fail over a point
        # that has nothing to do with the foreign read. An explicit empty list
        # is the ruling's own *a clerk may untick*, and it leaves the unit at
        # zero points the way this test has always assumed.
        unit = make_unit(dana, premises["id"], label="Unit X", services=[])
        assert models.ServicePoint.objects.filter(unit_id=unit["id"]).count() == 0
        models.Unit.objects.filter(pk=unit["id"]).update(premises_id=foreign["id"])
        with pytest.raises(errors.NotFoundError):
            services.ensure_service_point(unit["id"], "water")
        assert models.ServicePoint.objects.filter(unit_id=unit["id"]).count() == 0


# ══════════════════════════════════════════════════════════════════════════
# STAGE 3 · the operator sees it BEFORE loading, not as a wall at commit
# ══════════════════════════════════════════════════════════════════════════

ALL_OFF = {
    "drop_exact_duplicates": False,
    "keep_latest_on_key": False,
    "skip_rows_missing_required": False,
}
METERS_MAPPING = {"METER_NO": "asset_no", "SERVICE": "service", "UNIT_REF": "unit_ref"}


def _rejects(actor, content: str) -> dict[int, tuple[str, str | None]]:
    from apps.metering import import_runs

    run = import_runs.extract(
        actor,
        {
            "target": "assets_meters",
            "source_kind": "file",
            "file_name": "br-met-119.csv",
            "content": content,
            "session_ref": "sess_br_met_119",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": METERS_MAPPING, "row_handling": ALL_OFF})
    import_runs.validate(actor, run["id"])
    return {
        row["row_no"]: (row["problem"], row["fix_hint"])
        for row in import_runs.rejects(models.ImportRun.objects.get(pk=run["id"]))
    }


def test_tc6_stage_3_rejects_the_row_and_names_all_three_things(
    brazos, dana, water_only_address
):
    """BR-MET-119's third clause: the service asked for, what the address DOES
    offer, and WHERE to change it — the premises, the only place there is."""
    premises, unit = water_only_address
    content = (
        "METER_NO,SERVICE,UNIT_REF\n"
        f"M-9001,electric,{unit['unit_no']}\n"
        f"M-9002,water,{unit['unit_no']}\n"
    )
    with tenant_ctx(brazos):
        rejects = _rejects(dana, content)
    assert 2 not in rejects, "water at a water address must load"
    problem, fix_hint = rejects[1]
    assert problem == f"{premises['premise_no']} offers water, not electric."
    assert fix_hint == "Add electric on the premises first, then load again."


def test_tc7_stage_3_says_NEVER_ASKED_rather_than_offers_nothing(
    brazos, dana, never_asked_address
):
    """DEF-756's day-one state. `NULL` is not `[]`, and the sentence a clerk
    reads must not tell them to remove a service from the row."""
    premises, unit = never_asked_address
    content = "METER_NO,SERVICE,UNIT_REF\n" f"M-9003,electric,{unit['unit_no']}\n"
    with tenant_ctx(brazos):
        rejects = _rejects(dana, content)
    problem, fix_hint = rejects[1]
    assert problem == f"Nobody has said which services {premises['premise_no']} offers."
    assert fix_hint == "Add electric on the premises first, then load again."


def test_tc8_a_blank_unit_still_loads_to_inventory(brazos, dana, water_only_address):
    """BR-AST-045: a meter with no unit has no address, so this rule has
    nothing to ask it. Over-refusing here would break the inventory path."""
    content = "METER_NO,SERVICE,UNIT_REF\nM-9004,electric,\n"
    with tenant_ctx(brazos):
        rejects = _rejects(dana, content)
    assert rejects == {}


def test_tc9_the_rule_is_declared_on_both_measuring_targets():
    """BR-MET-090: a rule is a DECLARED ROW an operator can read, never an
    `if`. Tier 1, because the loader refuses the row whatever the table says."""
    from apps.metering import import_rules

    for target in ("assets_meters", "assets_submeters"):
        rule = {
            row.code: row for row in import_rules.PLATFORM_CATALOG[target]
        }["AST.SERVICE_AT_PREMISES"]
        assert rule.tier == import_rules.TIER_STRUCTURAL
        assert rule.severity == import_rules.ERROR
        assert rule.action == import_rules.REJECT_ROW

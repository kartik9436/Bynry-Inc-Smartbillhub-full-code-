# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave E task 22 — "seed sub-areas"
#          PO 2026-08-26, verbatim, looking at a provisioned tenant:
#          *"Why you dont have sub areas below - Areas metering 4 North
#          district · Downtown · East district · Industrial corridor"*
# Rules:   BR-MET-066b (ONE list, one nullable parent, depth exactly TWO — as
#          AMENDED 2026-08-26 by BR-MET-066c, which supersedes its closing
#          clause *"The four seeded rows stay top-level and no sub-area is
#          seeded"*) · BR-MET-071 (a premises carries an area; a sub-area tag
#          answers both levels) · BR-MET-072 (a parent matches its sub-areas)
#          · BR-TEN-012 (insert-missing seeding) · BR-TEN-063 (idempotent)
#          · BR-TEN-077 (fixture content and version move together)
# Defects: DEF-836 (the premises list has no area filter and the test written
#          to prove DEF-220 closed passed vacuously against it) ·
#          DEF-837 (a `parent_code` in the platform fixture was discarded by
#          the flat seeder, so no tenant ever received a sub-area)
# Screens: S8 (Areas & sub-areas card) · S14 (premises list) · S16 (add
#          premises)
# ───────────────────────────────────────────────────────
"""Hard-won law 2, on a field that had been sitting there for nine days.

`areas.parent_id` shipped on 2026-08-16 with BR-MET-066b. By 2026-08-17 the
column had two refusals, a Parent picker on S8, a two-select tag on S16/S14, a
`"South · SE"` path string on every premises row and a filter predicate that
walks a parent down to its children. **Every one of those was reachable only if
somebody first typed a sub-area into Settings by hand**, and no seed, fixture or
migration ever created one — so on every tenant in existence the second level
was dead weight that all the tests passed over.

The assertions here are therefore about the SEEDED ESTATE and about RENDERED
FACTS, not about the helpers: a fixture that declares a parent must produce a
parented row, the demo estate must actually be tagged into one, and the filter
a person clicks must return the rows underneath it.
"""

from __future__ import annotations

import pytest

from apps.metering import sample_data as met_sample
from apps.metering import selectors as met_selectors
from apps.tenancy import models as ten_models
from apps.tenancy import reference_sweep
from apps.tenancy import sample_data as ten_sample
from apps.tenancy import services as ten_services

from tests.test_us_ten_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_ten_helpers import (
    admin_actor,
    provisioned_tenant,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def fresh_tenant():
    """A provisioned tenant, INSIDE its own context — hard rule 1."""
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        yield tenant


@pytest.fixture()
def seeded_estate(identity_seam, settings):
    """The demo estate, planted through the real seam the S8 panel uses.

    Not a hand-built fixture: the whole point of these assertions is that a
    tenant a person PROVISIONS comes out with a two-level hierarchy, and a
    test that assembled the rows itself would prove only that the assembler
    works — which is the shape of the bug it is written for.
    """
    settings.JOBS_EAGER = True
    tenant, _ = provisioned_tenant()
    with tenant_ctx(tenant):
        actor = admin_actor()
        ten_sample.seed_sample_data(actor)
        yield {"tenant": tenant, "actor": actor}


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE FIXTURE DECLARES A SECOND LEVEL
# ═══════════════════════════════════════════════════════════════════════════


def test_the_platform_fixture_declares_three_sub_areas() -> None:
    """The rows, by name, so a silent deletion of one is a RED test and not a
    demo that quietly went flat again."""
    fixture = ten_services._load_seed_fixture()
    areas = fixture["areas"]
    parented = {entry["code"]: entry["parent_code"] for entry in areas if entry.get("parent_code")}
    assert parented == {"NORTH-NE": "NORTH", "NORTH-NW": "NORTH", "EAST-SE": "EAST"}
    # …and the four districts the PO named are untouched. BR-MET-066b's
    # superseded clause kept them top-level and BR-MET-066c keeps them there;
    # what changed is that three CHILDREN join them, never that a district moved.
    tops = [entry["code"] for entry in areas if not entry.get("parent_code")]
    assert tops == ["NORTH", "DTWN", "EAST", "IND"]


def test_two_districts_deliberately_have_no_sub_area() -> None:
    """BR-MET-066c's stated restraint, pinned so a later lane cannot "finish
    the job" by giving Downtown and Industrial corridor children nobody named.

    A tenant needs at least one childless district or two shipped behaviours
    are undemonstrable on seeded data: the Sub-area box's *"this area has no
    sub-areas"* help text, and a premises whose `area_path` is a bare district
    with no `·` in it.
    """
    fixture = ten_services._load_seed_fixture()
    parents = {entry["parent_code"] for entry in fixture["areas"] if entry.get("parent_code")}
    assert "DTWN" not in parents
    assert "IND" not in parents


def test_the_fixture_version_moved_with_its_content() -> None:
    """BR-TEN-077. The bump IS the delivery — a tenant sitting at V2.48.0.0
    would never be revisited and the three sub-areas would reach new tenants
    only, which is the 2026.08.2 failure recorded twice in `reference_sweep`.

    ⚠ **THIS PINNED `V2.48.0.1` UNTIL 2026-08-27 AND NOW PINS THE CURRENT
    SERIAL, WHICH IS A DIFFERENT AND SMALLER CLAIM.** BR-MET-142 grew
    `read_methods` 5 → 8 and moved the serial to `V2.48.0.2`, and this
    assertion went RED — correctly, because the guard it calls is the one that
    forces a bump and its digest into ONE commit:

        FixtureVersionError: fixture version 'V2.48.0.2' has no ratified
        content digest. The content currently hashes to b0e8985422a6…

    A literal here would go red on every future bump, and this test is not about
    the sub-areas' serial number — it is about *"the version moved with its
    content"*, which is exactly what `assert_fixture_version_matches_content()`
    raises on. So it now asserts the FIXTURE's own version rather than a frozen
    string: the guard still fires on an unbumped edit and on an unpinned bump,
    and it stops being a fourth hand-pinned place (DEF-807).

    ⚠ **AND IT IS NOT LEFT VACUOUS.** `assert_fixture_version_matches_content()`
    returns the version it just validated, so comparing it to
    `fixture_version()` would assert nothing at all — the RAISE is the check.
    The second assertion is what keeps a real claim about THIS wave: the serial
    may only move FORWARD from `V2.48.0.1`, so a later lane cannot deliver its
    own bump by rewinding past the sub-areas."""
    validated = reference_sweep.assert_fixture_version_matches_content()
    assert reference_sweep.version_key(validated) >= reference_sweep.version_key("V2.48.0.1"), (
        f"the fixture serial went BACKWARDS to {validated!r}; every tenant already "
        "seeded at V2.48.0.1 would then never be revisited again"
    )


# ═══════════════════════════════════════════════════════════════════════════
# 2 · THE SEEDER PRODUCES IT — DEF-837
# ═══════════════════════════════════════════════════════════════════════════


def test_seed_writes_the_parent_link_rather_than_discarding_it(fresh_tenant) -> None:
    """DEF-837, at its exact mechanism.

    `HostedFlatLookupHandler.seed` reads `code` and `name` and DISCARDS every
    other key. So the fixture could declare `parent_code` all day and the row
    landed top-level with nothing raised — a fixture stating a fact the seeder
    could not carry. Nothing in the suite could see it because every test that
    exercised the hierarchy built its rows through the settings handler.
    """
    tenant = fresh_tenant
    handler = ten_services.AreaLookupHandler()
    created = handler.seed(
        tenant,
        [
            {"code": "Z-TOP", "name": "Top"},
            {"code": "Z-SUB", "name": "Sub", "parent_code": "Z-TOP"},
        ],
    )
    assert created == 2
    sub = ten_models.Area.objects.get(tenant=tenant, code="Z-SUB")
    assert sub.parent is not None, "the fixture's parent_code was discarded"
    assert sub.parent.code == "Z-TOP"


def test_seed_orders_itself_so_a_child_may_be_declared_first(fresh_tenant) -> None:
    """A fixture is a LIST, and a list has no guaranteed order. The two-pass
    shape is what makes the file's ordering irrelevant rather than load-bearing.
    """
    ten_services.AreaLookupHandler().seed(
        fresh_tenant,
        [
            {"code": "Y-SUB", "name": "Sub", "parent_code": "Y-TOP"},
            {"code": "Y-TOP", "name": "Top"},
        ],
    )
    assert ten_models.Area.objects.get(tenant=fresh_tenant, code="Y-SUB").parent.code == "Y-TOP"


def test_seed_refuses_a_third_level_rather_than_flattening_it(fresh_tenant) -> None:
    """BR-MET-066b's depth cap is stated ONCE, in `_resolve_parent`, and the
    seeder goes through it — so a fixture that tried to declare a grandchild is
    refused by the same sentence a person would meet on S8, instead of quietly
    landing as a top-level row (which is what discarding the key did)."""
    from core import errors

    tenant = fresh_tenant
    handler = ten_services.AreaLookupHandler()
    handler.seed(tenant, [{"code": "X-TOP", "name": "Top"}])
    handler.seed(tenant, [{"code": "X-SUB", "name": "Sub", "parent_code": "X-TOP"}])
    with pytest.raises(errors.ValidationError):
        handler.seed(tenant, [{"code": "X-DEEP", "name": "Deeper", "parent_code": "X-SUB"}])


def test_a_replay_writes_nothing_and_never_re_parents(fresh_tenant) -> None:
    """BR-TEN-012 / BR-TEN-063. And the second half is the one worth pinning:
    a tenant who PROMOTED a sub-area to a district has made a decision, and a
    version bump re-delivering the fixture must not silently undo it."""
    tenant = fresh_tenant
    handler = ten_services.AreaLookupHandler()
    entries = [
        {"code": "W-TOP", "name": "Top"},
        {"code": "W-SUB", "name": "Sub", "parent_code": "W-TOP"},
    ]
    assert handler.seed(tenant, entries) == 2
    promoted = ten_models.Area.objects.get(tenant=tenant, code="W-SUB")
    promoted.parent = None
    promoted.save(update_fields=["parent"])
    assert handler.seed(tenant, entries) == 0
    promoted.refresh_from_db()
    assert promoted.parent_id is None, "a replay re-parented a row the tenant had promoted"


def test_the_card_counts_its_sub_areas(fresh_tenant) -> None:
    """r10 SET-04 draws `North district · 3 sub-areas`. CR-010 stripped those
    counts out of the seeded NAMES because they *"claimed sub-areas no tenant
    has"* — correctly. Now the rows exist, so the count comes back as a
    COUNTED FIELD the screen reads, never as words baked into a name.
    """
    tenant = fresh_tenant
    handler = ten_services.AreaLookupHandler()
    handler.seed(
        tenant,
        [
            {"code": "V-TOP", "name": "Top"},
            {"code": "V-A", "name": "A", "parent_code": "V-TOP"},
            {"code": "V-B", "name": "B", "parent_code": "V-TOP"},
            {"code": "V-FLAT", "name": "Flat"},
        ],
    )
    rows = {
        row.code: handler.serialize(row)
        for row in ten_models.Area.objects.filter(tenant=tenant, code__startswith="V-")
    }
    assert rows["V-TOP"]["sub_area_count"] == 2
    # 0, not absent: "no sub-areas" and "we did not ask" must not read alike.
    assert rows["V-FLAT"]["sub_area_count"] == 0
    assert rows["V-A"]["sub_area_count"] == 0
    assert rows["V-A"]["is_sub_area"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 3 · THE STREET MAP TAKES THE FINEST AREA THE TENANT HOLDS
# ═══════════════════════════════════════════════════════════════════════════


def test_a_tenant_with_sub_areas_is_tagged_into_them() -> None:
    """Pure — no database. The seeded estate's own street map."""
    held = {"NORTH", "NORTH-NE", "NORTH-NW", "DTWN", "EAST", "EAST-SE", "IND"}
    assert met_sample._area_code_for("101 Silver Creek Rd", held) == "NORTH-NW"
    assert met_sample._area_code_for("103 Willow Bend Dr", held) == "NORTH-NE"
    assert met_sample._area_code_for("105 Cedar Ridge Way", held) == "EAST-SE"
    # The two districts with no children stay exactly where they were.
    assert met_sample._area_code_for("107 Mill Pond Ln", held) == "DTWN"
    assert met_sample._area_code_for("109 Quarry Hill Ct", held) == "IND"


def test_a_tenant_seeded_before_the_bump_still_gets_its_district() -> None:
    """THE REGRESSION THIS CHAIN EXISTS TO PREVENT. Every tenant provisioned
    before fixture V2.48.0.1 holds four districts and no sub-area. A lookup
    that insisted on the sub-area would have left those premises UNTAGGED —
    DEF-256 reintroduced on every existing tenant by an improvement."""
    only_districts = {"NORTH", "DTWN", "EAST", "IND"}
    assert met_sample._area_code_for("101 Silver Creek Rd", only_districts) == "NORTH"
    assert met_sample._area_code_for("105 Cedar Ridge Way", only_districts) == "EAST"


def test_a_tenant_holding_neither_level_gets_no_tag_not_a_refusal() -> None:
    """`None` is a real answer (see `_area_code_for`'s own docstring): a tenant
    who deleted a district must not make the whole premises block fail."""
    assert met_sample._area_code_for("101 Silver Creek Rd", set()) is None


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE FILTER A PERSON CLICKS — DEF-836
# ═══════════════════════════════════════════════════════════════════════════


def test_the_premises_list_has_an_area_filter_at_all(seeded_estate) -> None:
    """DEF-836.

    `selectors.premises_list` read `type` and `status` and NOTHING ELSE, and
    `parse_list_params` documents that *"undeclared filter names are ignored"*.
    So `premises_list(filters={"area_codes": [...]})` — which is exactly what
    `test_cr029_w0_seed.py` called to prove DEF-220 was closed — returned the
    WHOLE LIST for every input, and its assertion `assert list(matched)` was
    true for `NORTH`, for `IND` and for `NOT-AN-AREA` alike.

    The check that could not have passed vacuously is the one below: a filter
    that returns FEWER rows than no filter, and nothing at all for a code the
    tenant does not have.
    """
    everything = met_selectors.premises_list().count()
    assert everything > 0
    nonsense = met_selectors.premises_list(filters={"area": "NOT-AN-AREA"})
    assert list(nonsense) == [], "an unknown area returned rows — the filter is not wired"
    north = met_selectors.premises_list(filters={"area": "NORTH"})
    assert 0 < north.count() < everything


def test_picking_a_district_returns_the_premises_in_its_sub_areas(seeded_estate) -> None:
    """BR-MET-072, on the seeded estate rather than in a unit test.

    *"A utility that has divided South into two halves still thinks of it as
    South."* On the demo the 44-premises estate's NORTH addresses are tagged to
    NORTH-NW or NORTH-NE, so a NORTH filter that matched only rows literally
    tagged NORTH would return far fewer than it should — DEF-220's symptom
    wearing a different hat.

    ⚠ **NORTH IS A STRICT SUPERSET OF ITS TWO HALVES, NOT THEIR UNION, AND THAT
    IS THE SEED BEING RIGHT RATHER THAN THIS TEST BEING LOOSE.** The first draft
    asserted `len(nw) + len(ne) == len(north)` and measured **12 + 13 == 30**.
    The missing five are the CR-030 estate and the W6/W7 seats, whose addresses
    are the DESIGN's (1408 Elm Street, 500 Main St…) and match no fixture
    street, so `_cr030_area_for` spreads them deterministically across every
    area the tenant holds — top-level rows included. **That is a better demo
    than a clean partition**: it means a reviewer sees premises tagged AT a
    district and premises tagged BELOW one, on the same tenant, which is
    exactly the pair of states BR-MET-066c exists to make visible.
    """
    north = list(met_selectors.premises_list(filters={"area": "NORTH"}))
    assert north, "the parent district matched none of its own sub-areas' premises"
    nw = list(met_selectors.premises_list(filters={"area": "NORTH-NW"}))
    ne = list(met_selectors.premises_list(filters={"area": "NORTH-NE"}))
    assert nw and ne
    # A sub-area matches ONLY itself — the two halves never overlap…
    assert {row.id for row in nw}.isdisjoint({row.id for row in ne})
    # …and both are wholly INSIDE the parent, which is the direction BR-MET-072
    # actually rules. A `>` rather than a `>=` would be the accidental
    # assertion; `issubset` is the one that goes red if the walk breaks.
    assert {row.id for row in nw} <= {row.id for row in north}
    assert {row.id for row in ne} <= {row.id for row in north}
    assert len(north) >= len(nw) + len(ne)


def test_every_seeded_area_that_has_premises_can_be_filtered_to(seeded_estate) -> None:
    """The DEF-220 assertion, re-stated so it can FAIL. Every area code the
    seeded estate tags something with must return at least one row, and the
    two childless districts must still work."""
    for code in ("NORTH", "NORTH-NW", "NORTH-NE", "EAST", "EAST-SE", "DTWN", "IND"):
        assert list(
            met_selectors.premises_list(filters={"area": code})
        ), f"the area filter returns nothing for {code}"


def test_the_seeded_estate_is_actually_tagged_two_levels_deep(seeded_estate) -> None:
    """The finding that started this task: r10's card was titled *"Areas &
    sub-areas"*, the shape was ruled, and **all four seeded rows were
    top-level**. A premises whose `area_path` carries no `·` is a premises in a
    district; the demo must contain both kinds, or half of BR-MET-066b is
    invisible to anyone reviewing the product."""
    rows = [met_selectors.premises_detail_dict(row) for row in met_selectors.premises_list()]
    paths = {row["area_path"] for row in rows if row["area_path"]}
    assert any(" · " in path for path in paths), "no seeded premises is in a sub-area"
    assert any(" · " not in path for path in paths), "no seeded premises is at top level"
    assert "North district · NW" in paths


def test_the_area_tag_survives_a_replay_of_the_premises_block(seeded_estate) -> None:
    """BR-TEN-063. A second plant must not move a premises between districts —
    the tag is derived from the address, so this is really pinning that the
    idempotence check happens before the tag is recomputed."""
    before = {row.id: row.area_id for row in met_selectors.premises_list().select_related("area")}
    met_sample.seed_sample_records(seeded_estate["actor"])
    after = {row.id: row.area_id for row in met_selectors.premises_list().select_related("area")}
    assert after == before

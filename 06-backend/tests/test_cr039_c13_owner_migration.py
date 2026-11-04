# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C tasks 13-14 — *"migrate the free-text names"* and
#          *"seed several owner kinds"*. PO ruling 2026-08-27, verbatim:
#          *"category is okay, no richer text"*, whose second unsettled caveat
#          is this file's whole subject: *"What happens to the twelve existing
#          free-text names on migration. They are real data on a live tenant. A
#          flagged migration that offers each name for matching is the shape;
#          silently guessing which string is which party is not."*
# Rules:   BR-MET-151 (matching, never guessing) · BR-MET-152 (which seeded
#          categories are stated and which two are refused) · BR-MET-150
# Defect:  DEF-828 (the guard SHAPE this file borrows — *is anything EXPOSED*,
#          never *did my rows land*) · DEF-466 (a guard that can pass vacuously)
# Question: OQ-500 · OQ-501
# ───────────────────────────────────────────────────────
"""The free text migrates by MATCHING, and the seed proves both halves.

⚠ **THE TWO TESTS THAT MATTER MOST BOTH ASSERT AN ABSENCE**, which is why they
are worth reading before the others:

  1. `…the_migration_creates_no_owner_row` — the backfill that was NOT written.
     A migration that guessed would look like progress, would pass every test
     that asks *did my rows land*, and would put a claim about a real party into
     a real customer's database permanently, with nobody's name on it.
  2. `…no_seeded_owner_has_an_INVENTED_category` — DEF-828's guard shape applied
     to a category: it asks *is anything stated that nothing supports*, not
     *did the five rows I wrote arrive*, and it refuses to pass vacuously by
     also requiring the seeded set to be non-empty.
"""

import pytest

from apps.metering import models as metering_models
from apps.metering import owner_selectors, premises_owners
from apps.metering import sample_data as metering_sample
from apps.metering import services as metering_services
from apps.rating import sample_data as rating_sample
from core import errors
from core import sample_fixture as fixture

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    seed_physical_series,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


def make_unmatched_premises_payload(actor, payload):
    """One premises in the PRE-RULING state — free-text owner, no typed party.

    ⚠ **THESE CALLS USED TO BE `create_premises` AND CANNOT BE ANY MORE.**
    `BR-MET-401` (PO 2026-08-27, `DEF-650`) makes the owner REQUIRED at
    creation, so the state this whole file is about — a name in a box and no
    party behind it — can no longer be reached through the front door. That is
    the rule working rather than a gap: it is still a real state on every live
    tenant, because `metering 0041` backfills nothing, and BR-MET-151's matching
    surface exists entirely to work through it.

    So the row is created lawfully and then put back into the old state, which is
    what a live tenant's rows already look like. Nothing about what this file
    asserts changes.
    """
    from apps.metering import models as _models
    from tests.test_us_met_helpers import owner_for

    row = metering_services.create_premises(
        actor,
        {**payload, "owner_id": owner_for(actor, "Fixture Party (unmatched premises)")},
    )
    _models.Premises.objects.filter(pk=row["id"]).update(owner=None)
    return {**row, "owner_id": None, "owner": None}



@pytest.fixture()
def silver_creek(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    """A water · sewer · trash tenant — the estate the fixture describes."""
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Owner Matching Water",
            subdomain="ownermatchingwater",
            services=["water", "sewer", "trash"],
        )
    )
    seed_physical_series(tenant)
    return tenant


@pytest.fixture()
def seeded(silver_creek):
    """Rating then metering, in the orchestrator's own order, through each
    module's REAL seam — so this file cannot drift from what a tenant gets."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        rating_sample.seed_sample_records(actor)
        metering_sample.seed_sample_records(actor)
    return silver_creek, actor


# ── BR-MET-151 · the migration writes NOTHING ───────────────────────────────


def test_cr039_c13__the_migration_creates_no_owner_row(growth_plan, identity_seam):  # noqa: F405
    """⚠ **THE WORKED FIGURE IS A ZERO, AND IT IS THE POINT OF TASK 13.**

    `metering 0040` adds `premises_owners` and `premises.owner_id` and
    **backfills nothing**. A freshly provisioned tenant — which has run every
    migration in the graph and no sample data — holds **0** owner rows and
    **0** matched premises.

    The PO's caveat is the reason, verbatim: *"They are real data on a live
    tenant. A flagged migration that offers each name for matching is the shape;
    silently guessing which string is which party is not."*
    """
    tenant, _ = provisioned_tenant(
        brazosbend_payload(name="Bare Water", subdomain="barewater", services=["water"])
    )
    with tenant_ctx(tenant):
        owners = metering_models.PremisesOwner.objects.filter(tenant_id=tenant.id).count()
        matched = metering_models.Premises.objects.filter(
            tenant_id=tenant.id, owner_id__isnull=False
        ).count()
    assert (owners, matched) == (0, 0), (
        "CR-039 C13: the migration must create no owner row and match no premises — "
        f"got {owners} owner(s) and {matched} matched premises. A backfill here is the "
        "silent guess BR-MET-151 forbids."
    )


def test_cr039_c13__unmatched_is_COMPUTED_from_the_two_columns(silver_creek):
    """BR-MET-151 clause 2. Text and no link ⇒ unmatched; a third
    `migration_status` column would be a second copy of a fact the two existing
    columns already answer, which is how two numbers come to disagree."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        make_unmatched_premises_payload(actor, {"address_line": "9 Legacy Row", "owner_manager": "Legacy Holdings LLC"})
        make_unmatched_premises_payload(actor, {"address_line": "11 Legacy Row"})
        addresses = sorted(
            premises_owners.unmatched_premises_qs().values_list("address_line", flat=True)
        )
    # The premises with no owner name at all is NOT unmatched — there is
    # nothing to match. Only text-with-no-link is.
    assert addresses == ["9 Legacy Row"]


def test_cr039_c13__the_review_surface_groups_by_NAME_not_by_address(silver_creek):
    """⚠ **TWELVE ADDRESSES SHARING ONE LANDLORD ARE ONE DECISION.**

    A list of twelve identical rows invites twelve separate parties — the exact
    outcome `uq_premises_owners_tenant_name_ci` exists to make impossible, and
    the exact opposite of the ruling's *"one party rather than twelve unrelated
    strings"*.
    """
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        for street in ("21 Elm", "23 Elm", "25 Elm"):
            make_unmatched_premises_payload(actor, {"address_line": street, "owner_manager": "Whitfield Rentals LLC"})
        rows = owner_selectors.unmatched_owner_rows()
    assert [row["owner_manager"] for row in rows] == ["Whitfield Rentals LLC"]
    assert rows[0]["premises_count"] == 3
    assert len(rows[0]["premises"]) == 3
    # Nothing typed exists yet, so nothing is offered.
    assert rows[0]["suggested_owner_ids"] == []


def test_cr039_c13__the_review_surface_offers_an_EXACT_match_and_never_a_category(silver_creek):
    """It offers CANDIDATES, never a kind. A fuzzy suggestion is a guess wearing
    a suggestion's clothes, and a clerk working down a list will accept it."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        owner = premises_owners.create_premises_owner(
            actor, {"name": "Whitfield Rentals LLC", "category": "landlord"}
        )
        make_unmatched_premises_payload(actor, {"address_line": "31 Elm", "owner_manager": "whitfield rentals llc"})
        make_unmatched_premises_payload(actor, {"address_line": "33 Elm", "owner_manager": "Whitfield Rentals Ltd"})
        rows = {row["owner_manager"]: row for row in owner_selectors.unmatched_owner_rows()}
    assert rows["whitfield rentals llc"]["suggested_owner_ids"] == [owner["id"]]
    # A DIFFERENT legal form is a DIFFERENT party until a person says otherwise.
    assert rows["Whitfield Rentals Ltd"]["suggested_owner_ids"] == []
    # And no row anywhere carries a category — the surface never suggests one.
    assert all("category" not in row and "category_code" not in row for row in rows.values())


def test_cr039_c13__matching_creates_the_party_and_KEEPS_the_free_text(silver_creek):
    """BR-MET-151 clause 4 / `OQ-500`.

    `premises.owner_manager` is the provenance of the match AND what
    `customers.services.open_account` reads for the default payer. Clearing it
    here would take a money decision nobody has made, on a screen a clerk opened
    to tidy up a name.
    """
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        premises = make_unmatched_premises_payload(actor, {"address_line": "41 Elm", "owner_manager": "Riverbend Apts LP"})
        result = premises_owners.match_premises_owner(
            actor, premises["id"], {"category": "landlord"}
        )
    assert result["owner"]["name"] == "Riverbend Apts LP"
    assert result["owner"]["category_code"] == "landlord"
    assert result["owner"]["source_owner_manager"] == "Riverbend Apts LP"
    assert result["premises"]["owner_manager"] == "Riverbend Apts LP"
    assert result["premises"]["owner_unmatched"] is False


def test_cr039_c13__matching_without_a_category_is_REFUSED(silver_creek):
    """The whole of BR-MET-151 clause 3 in one assertion: the free text is
    offered as the default NAME and never as a default KIND."""
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        premises = make_unmatched_premises_payload(actor, {"address_line": "51 Elm", "owner_manager": "Mason Rd Holdings"})
        with pytest.raises(errors.ValidationError) as caught:
            premises_owners.match_premises_owner(actor, premises["id"], {})
    assert caught.value.message_key == "metering.premises_owner.category_required"


def test_cr039_c13__matching_twelve_addresses_to_one_party_leaves_ONE_party(silver_creek):
    actor = staff_actor(silver_creek)
    with tenant_ctx(silver_creek):
        ids = [
            make_unmatched_premises_payload(
                actor,
                {"address_line": f"{n} Whitfield Way", "owner_manager": "Whitfield Rentals LLC"},
            )["id"]
            for n in range(1, 13)
        ]
        first = premises_owners.match_premises_owner(actor, ids[0], {"category": "landlord"})
        for premises_id in ids[1:]:
            premises_owners.match_premises_owner(
                actor, premises_id, {"owner_id": first["owner"]["id"]}
            )
        parties = metering_models.PremisesOwner.objects.filter(
            tenant_id=silver_creek.id, name="Whitfield Rentals LLC"
        ).count()
        remaining = owner_selectors.unmatched_owner_rows()
    assert parties == 1
    assert remaining == []


# ── BR-MET-152 · task 14, and the guard that has DEF-828's shape ────────────


def test_cr039_c14__the_seed_states_several_owner_KINDS(seeded):
    """Task 14 — *"seed several owner kinds"*.

    THE WORKED FIGURE: the seeded estate carries **three** kinds —
    `builder`, `owner_occupier` and `landlord` — each from a fact the corpus
    already holds (BR-MET-152 clause 1, and the decision log's table of bases).
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        kinds = sorted(
            {
                row.category.code
                for row in metering_models.PremisesOwner.objects.filter(
                    tenant_id=tenant.id
                ).select_related("category")
            }
        )
    assert kinds == ["builder", "landlord", "owner_occupier"], (
        "CR-039 C14: the seed must exercise several kinds and only the ones the corpus "
        f"supports — got {kinds}. `property_manager` and `hoa` are REFUSED by name "
        "(BR-MET-152 clause 2); adding either here states a party nobody has mentioned."
    )


#: The five stated pairs, written out HERE as literals rather than read from
#: `sample_fixture`. ⚠ **THIS DUPLICATION IS THE GUARD, NOT AN OVERSIGHT.** The
#: first version of the test below compared the seeder's output to
#: `fixture.owner_category_for(...)` — the same function the seeder itself calls
#: — so both sides moved together and a suffix heuristic added INSIDE the
#: fixture passed it. Measured, not assumed: with
#: `if name.endswith(("LLC", "LP", "Ltd")): return "landlord"` spliced into
#: `owner_category_for`, that version reported **4 passed**. A pinned literal is
#: what makes a new claim about a party go RED and reach a person.
STATED_OWNER_CATEGORIES = {
    "Ridge Property LLC": "builder",
    "Creekside Laundromat": "owner_occupier",
    "Quarry Hill Diner": "owner_occupier",
    "Mill Pond Apartments LP": "landlord",
    "Silver Creek Duplex Holdings": "landlord",
}


def test_cr039_c14__the_fixture_states_these_five_and_no_others():
    """⚠ **THE PINNED FIGURE (BR-MET-152 clause 1).**

    Five names, five bases, each one a fact the corpus already holds — and the
    decision log's table of bases is what a sixth entry has to earn. A lane that
    adds one, or adds a rule that DERIVES one, fails here and has to write down
    why before it can go green.
    """
    assert fixture.OWNER_CATEGORY_BY_NAME == STATED_OWNER_CATEGORIES


def test_cr039_c14__a_name_the_fixture_does_not_state_gets_NO_category():
    """⚠ **THE ONE ASSERTION A STRING HEURISTIC CANNOT SURVIVE (BR-MET-151
    clause 3).**

    *Whitfield Rentals LLC* is not evidence of a landlord and *Chen, David* is
    not evidence of an owner-occupier. Both are real names on a real seeded
    tenant and both must answer `None` — which is what puts them on the review
    list where a person decides.

    Proved RED: splicing `if name.endswith(("LLC", "LP", "Ltd")): return
    "landlord"` into `owner_category_for` fails this case by name, where the
    earlier data-level guard passed straight over it.
    """
    for name in ("Whitfield Rentals LLC", "Chen, David", "Northwind Mfg.", "Riverbend Apts LP"):
        assert fixture.owner_category_for(name) is None, (
            f"CR-039 C14 / BR-MET-151 clause 3: the fixture states a category for {name!r} that "
            "no fact in the corpus supports. A category is a claim about a real party — state "
            "its basis in `OWNER_CATEGORY_BY_NAME` with the quote that backs it, or return None "
            "and let a person decide on the review surface."
        )


def test_cr039_c14__no_seeded_owner_has_an_INVENTED_category(seeded):
    """⚠ **DEF-828's GUARD SHAPE, APPLIED TO A CATEGORY.**

    That defect's lesson was that a guard must ask *is anything EXPOSED* rather
    than *did my rows land* — and must refuse to pass vacuously. So this asks
    the question the other way round from the test above: **every** typed owner
    on a seeded tenant must trace back to a name `sample_fixture` explicitly
    states a category for. A future lane that "helpfully" types the remaining
    names by guessing a suffix fails HERE, not in review.

    It cannot pass vacuously: it requires the seeded set to be NON-EMPTY first.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        seeded_owners = list(
            metering_models.PremisesOwner.objects.filter(tenant_id=tenant.id).select_related(
                "category"
            )
        )
    assert seeded_owners, (
        "CR-039 C14: no owner was seeded at all, so this guard is vacuous — DEF-466's own "
        "shape and the reason this line exists"
    )
    # ⚠ COMPARED AGAINST THE PINNED LITERAL ABOVE, never against
    # `fixture.owner_category_for` — the seeder's own source. See
    # `STATED_OWNER_CATEGORIES` for the run that proved why.
    invented = sorted(
        f"{owner.name} -> {owner.category.code}"
        for owner in seeded_owners
        if STATED_OWNER_CATEGORIES.get(owner.name) != owner.category.code
    )
    assert invented == [], (
        "CR-039 C14 / BR-MET-151 clause 3: these seeded owners carry a category that "
        f"`core.sample_fixture.OWNER_CATEGORY_BY_NAME` does not state: {invented}. A "
        "category is a claim about a real party; state its basis in the fixture or leave "
        "the premises unmatched."
    )


def test_cr039_c14__the_demo_keeps_UNMATCHED_names_so_the_review_surface_is_demonstrable(seeded):
    """⚠ **THE UNMATCHED ROWS ARE DELIBERATE (BR-MET-152 clause 4).**

    BR-MET-151 says the free-text names migrate on a review surface, one at a
    time — and a review surface with nothing on it is a promise nobody checks.
    Same reasoning task 11 used to leave the sample COMMERCIAL plan deliberately
    stating no outside-city factor: the demo shows BOTH halves.
    """
    tenant, _ = seeded
    with tenant_ctx(tenant):
        rows = owner_selectors.unmatched_owner_rows()
        names = {row["owner_manager"] for row in rows}
    assert rows, (
        "CR-039 C14: a fresh demo must still carry free-text owner names nobody has "
        "typed, or BR-MET-151's review surface has nothing to show and nobody discovers "
        "it works"
    )
    stated = set(fixture.OWNER_CATEGORY_BY_NAME)
    assert not (names & stated), (
        f"CR-039 C14: these names have a stated category and were left unmatched anyway: "
        f"{sorted(names & stated)}"
    )


def test_cr039_c14__seeding_twice_writes_no_second_party(seeded):
    """BR-TEN-063 — a replay writes nothing."""
    tenant, actor = seeded
    with tenant_ctx(tenant):
        before = metering_models.PremisesOwner.objects.filter(tenant_id=tenant.id).count()
        metering_sample.seed_sample_records(actor)
        after = metering_models.PremisesOwner.objects.filter(tenant_id=tenant.id).count()
    assert before == after and before > 0


def test_cr039_c14__the_seeded_parties_are_tagged_sample_so_remove_takes_them(seeded):
    """BR-TEN-057/061. An owner left behind by `--remove` would be a named party
    with contact details surviving the removal of the demo it belongs to."""
    tenant, _ = seeded
    with tenant_ctx(tenant):
        untagged = list(
            metering_models.PremisesOwner.objects.filter(
                tenant_id=tenant.id, is_sample=False
            ).values_list("name", flat=True)
        )
    assert untagged == []

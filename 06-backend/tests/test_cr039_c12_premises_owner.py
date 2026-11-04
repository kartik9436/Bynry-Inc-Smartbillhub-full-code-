# ── Trace ──────────────────────────────────────────────
# Change:  CR-039 wave C task 12 — *"an owner as a typed record (kind · contact
#          · linked to the customer they already are)"*. PO ruling 2026-08-27,
#          verbatim: *"category is okay, no richer text"*.
# Rules:   BR-MET-150 (the typed record) · BR-TEN-150 (the vocabulary) ·
#          BR-MET-035 (server-enforced roles)
# Question: OQ-500 (does the typed owner become the default payer?) ·
#          OQ-502 (are the five closed or extensible?)
# ───────────────────────────────────────────────────────
"""The typed premises owner: the vocabulary, the record, and what it REFUSES.

⚠ **THE REFUSALS ARE THE POINT OF THIS FILE.** A record with a category is easy
to build and easy to test; what the PO actually ruled out was *keep the box and
make it longer*, and the two tests that hold that line are the one asserting a
categoryless payload is REFUSED and the one asserting no free-text description
column exists anywhere on the record.
"""

import pytest

from apps.metering import models as metering_models
from apps.metering import owner_selectors, premises_owners
from apps.metering import services as metering_services
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    provisioned_tenant,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def owner_tenant(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Owner Records Water",
            subdomain="ownerrecordswater",
            services=["water", "sewer", "trash"],
        )
    )
    return tenant, staff_actor(tenant)


# ── BR-TEN-150 · the vocabulary ─────────────────────────────────────────────


def test_cr039_c12__a_new_tenant_holds_the_five_categories_the_po_ratified(owner_tenant):
    """**THE WORKED FIGURE: 5 rows, and these five words.**

    PO 2026-08-27: *"category is okay, no richer text"*, answering whether an
    owner is a typed party record — owner-occupier · landlord · property
    manager · HOA · builder — or richer free text. The five put to them ARE the
    seeded rows, so this test is the ratified figure asserted (CLAUDE.md 🔒
    sign-off part 2: *a test asserts the ratified figure so drift goes RED*).
    """
    tenant, _ = owner_tenant
    with tenant_ctx(tenant):
        codes = list(
            tenancy_models.PremisesOwnerCategory.objects.filter(tenant_id=tenant.id)
            .order_by("created_at")
            .values_list("code", flat=True)
        )
    assert codes == [
        "owner_occupier",
        "landlord",
        "property_manager",
        "hoa",
        "builder",
    ], f"CR-039 C12: a new tenant must hold exactly the five the PO ratified, got {codes}"


def test_cr039_c12__the_category_list_is_structural_so_the_toggle_cannot_empty_it():
    """BR-TEN-150 clause 3 / BR-TEN-067.

    `premises_owners.category_id` is NOT NULL, so a tenant whose S111 *"load
    standard reference data"* toggle emptied this list could not record a single
    owner — the exact state BR-TEN-067 exists to prevent. If this list were
    discretionary the count on such a tenant would be **0** instead of **5**.
    """
    from apps.tenancy import services as tenancy_services

    assert "owner_categories" in tenancy_services.STRUCTURAL_REFERENCE_LISTS


def test_cr039_c12__the_vocabulary_is_tenant_extensible_which_is_the_house_pattern(owner_tenant):
    """`OQ-502` — the build follows DB-14 / BR-TEN-036 and the row says so.

    Nothing was put to the PO about whether a tenant may add a sixth, so this
    asserts the HOUSE PATTERN rather than a ruling. The day the PO closes the
    list, this test is what goes red and names the place to change.
    """
    from apps.tenancy import services as tenancy_services

    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        row = tenancy_services.create_lookup_entry(
            actor, "owner_categories", {"code": "executor_of_estate", "name": "Executor of estate"}
        )
    assert row["code"] == "executor_of_estate"


# ── BR-MET-150 · the record, and what it refuses ────────────────────────────


def test_cr039_c12__an_owner_with_no_category_is_REFUSED_never_defaulted(owner_tenant):
    """⚠ **THE CENTRAL REFUSAL OF THE WHOLE TASK.**

    A record with no category IS the free-text box the PO ruled against. Picking
    `landlord` because it is the commonest would be this product answering a
    question about a real party on the utility's behalf — the same class of
    silent decision BR-RAT-101 refuses for the jurisdiction flag.
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as caught:
            premises_owners.create_premises_owner(actor, {"name": "Whitfield Rentals LLC"})
    assert caught.value.code == errors.VAL_REQUIRED
    assert caught.value.message_key == "metering.premises_owner.category_required"


def test_cr039_c12__there_is_no_free_text_description_column_anywhere_on_the_record():
    """⚠ **"NO RICHER TEXT" IS HALF THE RULING AND THIS IS THE HALF NOBODY WOULD
    NOTICE BREAKING.**

    The option the PO rejected was *keep the free-text box and make it longer*.
    A `notes` column added here later — for the best of reasons, by a lane that
    never read the ruling — would be that option arriving one row lower down,
    and every other test in this file would still pass.
    """
    columns = {field.name for field in metering_models.PremisesOwner._meta.get_fields()}
    forbidden = columns & {"notes", "description", "comment", "comments", "remarks", "details"}
    assert forbidden == set(), (
        "CR-039 C12: PO 2026-08-27 ruled *'category is okay, no richer text'*, rejecting "
        f"a longer free-text box. These columns re-introduce it: {sorted(forbidden)}"
    )
    # And the write path refuses the key even if a column were smuggled in.
    assert not premises_owners.OWNER_FIELDS & {"notes", "description", "comment"}


def test_cr039_c12__the_customer_link_is_OPTIONAL_because_a_builder_may_not_be_one(owner_tenant):
    """The ruling's own caveat, verbatim: *"a builder holding a site before
    handover may not be [a customer], so the link is optional and its absence is
    a stated fact rather than a gap."*"""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        row = premises_owners.create_premises_owner(
            actor, {"name": "Ridge Property LLC", "category": "builder"}
        )
    assert row["customer_id"] is None
    assert row["category_code"] == "builder"


def test_cr039_c12__contact_details_are_carried_and_are_optional(owner_tenant):
    """The ruling asks for *"contact details, so there is a way to reach whoever
    is named when a unit is vacant or a bill bounces"*. Whether the category
    that PAYS must carry at least one is `OQ-503` and is NOT decided here."""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        row = premises_owners.create_premises_owner(
            actor,
            {
                "name": "Mill Pond Apartments LP",
                "category": "landlord",
                "contact_name": "A. Okafor",
                "email": "ap@millpond.example",
                "phone": "555-0142",
            },
        )
    assert (row["contact_name"], row["email"], row["phone"]) == (
        "A. Okafor",
        "ap@millpond.example",
        "555-0142",
    )


def test_cr039_c12__one_party_not_twelve_strings__a_duplicate_name_is_refused(owner_tenant):
    """⚠ **THE RULING'S OWN REASON FOR THE TABLE, MADE STRUCTURAL.**

    *"The same landlord across twelve addresses is one party rather than twelve
    unrelated strings."* Matching happens one premises at a time, so without
    `uq_premises_owners_tenant_name_ci` a clerk working down the review list
    creates twelve parties named *Whitfield Rentals LLC* and the change achieves
    nothing while appearing to work. The refusal NAMES the party that exists so
    the clerk can link to it.
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        first = premises_owners.create_premises_owner(
            actor, {"name": "Whitfield Rentals LLC", "category": "landlord"}
        )
        with pytest.raises(errors.BizError) as caught:
            premises_owners.create_premises_owner(
                actor, {"name": "whitfield rentals llc", "category": "property_manager"}
            )
    assert caught.value.params["owner_id"] == first["id"]


def test_cr039_c12__a_premises_points_at_the_owner_and_keeps_its_free_text(owner_tenant):
    """BR-MET-151 clause 4 — the two facts live side by side and neither
    substitutes for the other, because `open_account` reads the string
    (`OQ-500`)."""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        owner = premises_owners.create_premises_owner(
            actor, {"name": "Silver Creek Duplex Holdings", "category": "landlord"}
        )
        premises = metering_services.create_premises(
            actor,
            {"owner_id": owner_for(actor), 
                "address_line": "181 Silver Creek Rd",
                "owner_manager": "Silver Creek Duplex Holdings",
                "owner_id": owner["id"],
            },
        )
    assert premises["owner"]["category_code"] == "landlord"
    assert premises["owner_manager"] == "Silver Creek Duplex Holdings"
    assert premises["owner_unmatched"] is False


def test_cr039_c12__an_owner_that_addresses_point_at_cannot_be_retired(owner_tenant):
    """IS-1 deactivate-first, and the blockers are NAMED — *"it is in use"* is
    not an answer a clerk can act on."""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        owner = premises_owners.create_premises_owner(
            actor, {"name": "Quarry Hill Diner", "category": "owner_occupier"}
        )
        metering_services.create_premises(
            actor, {"owner_id": owner_for(actor), "address_line": "701 Quarry Hill Rd", "owner_id": owner["id"]}
        )
        with pytest.raises(errors.BizError) as caught:
            premises_owners.deactivate_premises_owner(actor, owner["id"])
    assert caught.value.params["blockers"] == ["701 Quarry Hill Rd"]


def test_cr039_c12__an_unknown_category_is_refused_by_name_and_lists_what_is_allowed(owner_tenant):
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        with pytest.raises(errors.ValidationError) as caught:
            premises_owners.create_premises_owner(
                actor, {"name": "Northwind Mfg.", "category": "freeholder"}
            )
    assert caught.value.code == errors.VAL_UNKNOWN_LOOKUP
    assert "landlord" in caught.value.params["allowed"]


def test_cr039_c12__the_owner_row_counts_the_addresses_that_point_at_it(owner_tenant):
    """The ruling's *"one party rather than twelve unrelated strings"* made
    visible — it is what a clerk needs before renaming or retiring a party."""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        owner = premises_owners.create_premises_owner(
            actor, {"name": "Mason Rd Holdings", "category": "property_manager"}
        )
        for street in ("11 Mason Rd", "13 Mason Rd", "15 Mason Rd"):
            metering_services.create_premises(
                actor, {"owner_id": owner_for(actor), "address_line": street, "owner_id": owner["id"]}
            )
        row = owner_selectors.owner_detail_dict(premises_owners._owner_row(owner["id"]))
    assert row["premises_count"] == 3


# ── OQ-500 · the money path is UNTOUCHED, and that is asserted ──────────────


def test_oq_500__open_account_still_reads_the_free_text(owner_tenant):
    """⚠ **THIS TEST EXISTS TO GO RED THE DAY `OQ-500` IS RULED.**

    `customers.services.open_account` falls back to `premises.owner_manager` for
    the default payer (PO 2026-08-22: *"payer = the premises' owner/manager"*).
    After this change a premises can hold BOTH that string and a typed party
    carrying an email and a customer link — and which one the money path reads
    is a decision nobody has taken.

    So the assertion is about the CODE rather than about a bill: the fallback
    still names the free-text column and nothing else. When the PO rules B or C
    on `OQ-500`, this is the line that fails and names the place to build.
    """
    import inspect

    from apps.customers import services as customers_services

    source = inspect.getsource(customers_services)
    assert 'premises.get("owner_manager")' in source, (
        "OQ-500 is OPEN and this lane deliberately left the payer path alone. If the "
        "fallback has changed, OQ-500 has been answered somewhere — record the ruling in "
        "12-governance/02-decision-log.md and amend BR-MET-150 clause 6 before changing "
        "this test."
    )

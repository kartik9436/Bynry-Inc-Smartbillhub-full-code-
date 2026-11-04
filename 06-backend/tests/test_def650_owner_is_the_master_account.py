# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-650 (critical) — *"Owner is free text on the premise record, not
#          an account. That limits where a shortfall can be sent."* ·
#          DEF-1088 (high) — the premises import writes the owner as free text ·
#          DEF-1247 (high) — the `Owner` header feeds the FREE-TEXT column
# Rules:   BR-MET-400 (the premises names a real master account) ·
#          BR-MET-401 (the check at premises creation: exact reuses, near
#          OFFERS, neither creates) · BR-MET-150/151 (the typed record and its
#          provenance) · BR-CUS-171 as superseded (geometry retired)
# Ruling:  PO 2026-08-27, verbatim: *"so premises owner is master accountin
#          system. you ahve to showall details form account - Bascially Premises
#          -> owner = Master account - it can be existing master account also so
#          at the time of premises creation we should check - how you will
#          handle this"*, and the four decisions that answer its second half.
# Question: OQ-790 (when the owner's ACCOUNT is created, and of which kind) —
#          minted, stubbed, and NOT answered by this lane
# ───────────────────────────────────────────────────────
"""The premises owner IS the master account — the RED proofs, then the green.

⚠ **EVERY TEST IN THE FIRST SECTION WAS WRITTEN TO FAIL FIRST** (r11 step 2d,
hard-won law 7). Their failure text is quoted in the defect rows, so a lane
reading this file can see what the product did before the fix rather than
taking a commit message's word for it.
"""

import pytest

from apps.customers import selectors as customers_selectors
from apps.metering import import_runs, models as metering_models
from apps.metering import owner_selectors, premises_owners
from apps.metering import selectors as metering_selectors
from apps.metering import services as metering_services
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (
    brazosbend_payload,
    make_unmatched_premises,
    provisioned_tenant,
    staff_actor,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db


@pytest.fixture()
def owner_tenant(growth_plan, identity_seam):  # noqa: F405 — W0 helper fixtures
    tenant, _ = provisioned_tenant(
        brazosbend_payload(
            name="Ridge Property Water",
            subdomain="ridgepropertywater",
            services=["water", "sewer", "trash"],
        )
    )
    return tenant, staff_actor(tenant)


# ══════════════════════════════════════════════════════════════════════════
# DEF-650 — a charge cannot be posted to free text
# ══════════════════════════════════════════════════════════════════════════


def test_def650__the_owner_record_carries_a_REAL_ACCOUNT_not_a_string():
    """⛔ **THE DEFECT, IN ONE ASSERTION.**

    BR-MET-105 (PO 2026-08-24) sends the empty-unit base charge — worked at
    **$30.50/month** — to *"the owner / landlord"*, and the move-out wizard says
    in its own shipped copy that it cannot: *"Owner is free text on the premise
    record, not an account. That limits where a shortfall can be sent."*

    The 2026-08-27 ruling names the missing piece exactly: *"THE ONE MISSING
    LINK is `owner → master ACCOUNT`. Today nothing joins a `premises_owners`
    row to an `accounts` row of kind `master`."* This is that link.
    """
    columns = {field.name for field in metering_models.PremisesOwner._meta.get_fields()}
    assert "master_account" in columns, (
        "DEF-650: the premises owner still has nowhere to send a charge. PO 2026-08-27: "
        "'Premises -> owner = Master account'. premises_owners has no account column."
    )


def test_cr089_b1__a_premises_created_with_no_owner_is_ACCEPTED(owner_tenant):
    """⚠ **THIS TEST ASSERTED THE OPPOSITE UNTIL 2026-09-09, AND THE REVERSAL IS
    A PO RULING RATHER THAN A BUG FIX.**

    It used to be `test_def650__a_premises_created_with_no_owner_is_REFUSED`,
    holding **DECISION 1 of 2026-08-27**: *"when presmies are created you have
    owner for it, without owner how you can create premsies = owner = master
    account"*. That is **SUPERSEDED** by the PO on **2026-09-08**, verbatim:

        *"Owner = search ( it should be optional)"*

    CR-089 §2.1 carries the chain in full and `B1` is the task. The old name is
    left in this docstring on purpose: a `git log -S` for it lands here, on the
    ruling that moved it, rather than on a deletion.

    ⚠ **WHAT DID NOT CHANGE, AND IS THE REST OF THIS FILE.** The owner is still
    the master account (`BR-MET-400`), still where an empty unit's base charge
    goes and still the only thing a shortfall can be sent to. What moved is
    WHEN it has to be answered.

    ⚠ **AND THE COST IS ASSERTED HERE RATHER THAN TRUSTED**: the row this create
    now makes is on the **Needs an owner** list the same moment it exists. A
    reversal that produced a row no list could find would be a hole; CR-089 §2.1
    says the two ship together, so the two are tested together.
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        created = metering_services.create_premises(actor, {"address_line": "1408 Elm Street"})
        assert created["owner"] is None
        assert created["premise_no"], "a property with no owner still takes its number"
        found = metering_selectors.premises_list(filters={"owner": "needs_owner"})
        assert str(created["id"]) in {str(row.id) for row in found}, (
            "CR-089 B1/B2: an owner-less create MUST land on the Needs an owner list — "
            "the reversal without that list is an orphan nobody can find (CR-089 §2.1)"
        )
        # …and it is NOT on the other half of the group, which is what makes the
        # filter a filter rather than a label.
        assert str(created["id"]) not in {
            str(row.id) for row in metering_selectors.premises_list(filters={"owner": "has_owner"})
        }


def test_def650__an_EXISTING_owner_is_reused_at_premises_creation_never_duplicated(owner_tenant):
    """**THE HEADLINE OF THE RULING:** *"it can be existing master account also
    so at the time of premises creation we should check"*.

    The match key already exists — `uq_premises_owners_tenant_name_ci` makes an
    owner name unique per tenant in the DATABASE — so the check is a lookup and
    not a heuristic. Twelve addresses for one landlord are ONE party.
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        first = premises_owners.create_premises_owner(
            actor, {"name": "Ridge Property LLC", "category": "landlord"}
        )
        found = premises_owners.resolve_owner_name("ridge property llc")
    assert found["match"] == "exact"
    assert found["owner"]["id"] == first["id"], (
        "DEF-650: the check at premises creation must FIND the party that exists. "
        f"got {found}"
    )


def test_def650__a_NEAR_match_is_OFFERED_and_never_merged(owner_tenant):
    """**DECISION 3, verbatim:** *"Near match on the name - (b) offer the match,
    clerk decides"*, and the decision log's reason: *"Never auto-merge. Two
    landlords with similar names are two parties, and merging them bills the
    wrong one."*
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        existing = premises_owners.create_premises_owner(
            actor, {"name": "Ridge Property LLC", "category": "landlord"}
        )
        offered = premises_owners.resolve_owner_name("Ridge Property, L.L.C.")
    assert offered["match"] == "near", f"DEF-650: expected a near match, got {offered['match']}"
    assert [row["id"] for row in offered["candidates"]] == [existing["id"]]
    assert offered["owner"] is None, (
        "DEF-650: a near match must OFFER and never resolve — the clerk decides (PO decision 3)."
    )


def test_def650__the_owners_DETAILS_come_from_the_ACCOUNT_not_from_a_copied_string(owner_tenant):
    """**PO verbatim:** *"you ahve to showall details form account"*.

    The owner detail read must carry the ACCOUNT's own facts — its number, its
    status, its balance — read through the seam at the moment of asking, never
    a string copied onto the premises row that drifts the day somebody edits
    one (`OQ-501`'s two-writable-copies problem).
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        owner = premises_owners.create_premises_owner(
            actor, {"name": "Mill Pond Apartments LP", "category": "landlord"}
        )
        detail = owner_selectors.owner_detail_dict(
            metering_models.PremisesOwner.objects.get(pk=owner["id"])
        )
    assert "master_account" in detail, (
        "DEF-650: the owner detail must carry the ACCOUNT block. PO: 'you ahve to showall "
        f"details form account'. got keys {sorted(detail)}"
    )
    # No account linked yet is a REAL state and it says so rather than being absent.
    assert detail["master_account"] is None
    assert detail["master_account_id"] is None
    # ⚠ AND THE DETAIL SAYS IT ASKED. `master_account: null` means two things —
    # *nobody has linked one* and *this row did not expand it* — so the list
    # endpoint serves `False` here and every expanding path serves `True`
    # (DEF-324: expanding 200 owners is one account read and one ledger
    # derivation each). A screen that cannot tell them apart renders "no
    # account" over a fact the server never stated.
    assert detail["master_account_expanded"] is True
    light = owner_selectors.owner_detail_dict(
        metering_models.PremisesOwner.objects.get(pk=owner["id"]), with_account=False
    )
    assert light["master_account_expanded"] is False


# ══════════════════════════════════════════════════════════════════════════
# BR-CUS-171 — the geometric derivation is RETIRED
# ══════════════════════════════════════════════════════════════════════════


def test_def650__the_master_is_DECLARED_and_geometry_is_gone():
    """**DECISION 4:** *"The ruling replaces all of it: the premises names its
    owner, the owner is the master, and nothing is inferred from hallways. The
    old path is retired rather than kept as a fallback, because a fallback that
    disagrees with the declared owner would silently bill a different party."*

    So the two weaknesses the ruling names are gone by construction: a premises
    with no common area still has a master, and two masters over one premises no
    longer make `master_account_for` answer `None`.
    """
    import inspect

    source = inspect.getsource(customers_selectors.master_account_for)
    assert "common_area_units_for_premises" not in source, (
        "DEF-650: BR-CUS-171's geometric derivation is RETIRED by the PO ruling of "
        "2026-08-27 (decision 4) and must not remain as a fallback."
    )
    assert "owner_master_account_for_premises" in source, (
        "DEF-650: the master must be read from the DECLARED link."
    )


# ══════════════════════════════════════════════════════════════════════════
# DEF-1247 — the `Owner` header must reach the TYPED owner
# ══════════════════════════════════════════════════════════════════════════


def test_def1247__the_Owner_header_maps_to_the_TYPED_owner_not_the_free_text(owner_tenant):
    """⛔ **MEASURED BY THE METERING LANE, REPRODUCED HERE.**

    `PREMISES_ALIASES['owner_manager']` listed `'owner'` FIRST, and the offered
    set is derived from the model (BR-MET-088), so the shipped sample carries
    BOTH headers: the alias loop claimed `owner` for the FREE-TEXT field and the
    `owner_manager` header was never claimed at all.

    Under the ruling the operator's `Owner` column is the OWNER, which is now an
    account — so it resolves to the typed field. Nothing is lost: the string
    still lands in `owner_manager` as BR-MET-151 provenance (asserted below).

    ⛔ **AMENDED 2026-09-19 — `DEF-MET-5802` RETIRED THE FREE-TEXT COLUMN FROM
    THE PREMISES TEMPLATE, SO THIS CASE'S SECOND HEADER NOW MAPS TO NOTHING.**
    This assertion used to read `{"Owner": "owner", "Owner / manager":
    "owner_manager"}` — *"both headers must be claimed, one each"* — and that
    was the right assertion while BOTH columns were offered. The PO reviewed the
    template on 2026-09-19 and retired `owner_manager` from it, because two
    name-shaped columns where only ONE creates an owner account is what made the
    template look as though it could not name an owner at all.

    ⚠ **WHAT `DEF-1247` WAS PROTECTING IS UNCHANGED AND IS STILL ASSERTED
    FIRST**: the free-text column must never claim the `owner` HEADER, or the
    typed owner gets nothing. That danger is the reason this test exists and it
    does not go away — `PREMISES_ALIASES["owner_manager"]` is still a live
    table, and a lane re-offering the column would revive the exact bug. **The
    weaker outcome would have been deleting this test with the column**; it is
    kept, and its second half now pins the retirement instead.
    """
    assert "owner" not in import_runs.PREMISES_ALIASES["owner_manager"], (
        "DEF-1247: the free-text column still claims the 'owner' header, so the typed "
        "owner field gets nothing."
    )
    assert "owner" in import_runs.PREMISES_ALIASES["owner"]
    # `_auto_map` reads the OFFERED set, which includes the tenant's custom
    # fields — so it needs a tenant, exactly like the picker it feeds.
    tenant, _ = owner_tenant
    with tenant_ctx(tenant):
        mapping = import_runs._auto_map(
            ["Owner", "Owner / manager"], import_runs.TARGET_PREMISES
        )
    assert mapping == {"Owner": "owner"}, (
        "DEF-1247 + DEF-MET-5802: the `Owner` header must still reach the TYPED owner, "
        f"and `Owner / manager` must now reach nothing at all. got {mapping}"
    )
    # ⚠ **ASSERTED AS A CAUSE, NOT INFERRED FROM THE ABSENCE.** A header can go
    # unclaimed because the alias was deleted, which would be a different and
    # much worse change — it would take the `owner` header's own protection with
    # it. The alias is intact; the COLUMN is withheld, and `_auto_map` skips an
    # alias whose column is not offered.
    assert "owner / manager" in import_runs.PREMISES_ALIASES["owner_manager"]
    assert "owner_manager" in import_runs.PREMISES_COLUMNS_NOT_OFFERED
    assert "owner_manager" not in import_runs.PREMISES_COLUMNS


def test_def1247__no_model_column_name_is_claimed_as_ANOTHER_fields_alias():
    """⚠ **THE DURABLE FIX, NOT ANOTHER ALIAS EDIT** (DEF-1247's own
    recommendation, and DEF-616's mechanism recurring).

    An alias table hand-kept beside a model-derived offered set drifts every
    time a column is added. A MODEL column's own name claimed as some OTHER
    field's alias is the shape both defects took, and it is detectable at the
    moment it is introduced rather than two waves later.
    """
    offenders: list[str] = []
    for target, aliases in import_runs.ALIASES_BY_TARGET.items():
        # The MODEL's own column names, read straight off `_meta` — the same
        # source `target_columns` derives the offered set from, but with no
        # tenant context needed (custom fields are per tenant; a real column is
        # not, and it is real columns this rule is about).
        try:
            model = import_runs._model_for(target)
        except Exception:
            # The assets targets are written through the assets seam and have no
            # model in this module; their alias tables are that module's to check.
            continue
        offered = {
            field.name for field in model._meta.get_fields() if getattr(field, "concrete", False)
        } - set(import_runs.NEVER_IMPORTABLE)
        for field_name, alias_tuple in aliases.items():
            for alias in alias_tuple:
                if alias in offered and alias != field_name:
                    offenders.append(f"{target}: '{alias}' is a real column but aliases {field_name}")
    assert offenders == [], (
        "DEF-1247/DEF-616: a model column's own name is claimed as another field's alias, "
        f"so its header can never be mapped to it: {offenders}"
    )


# ══════════════════════════════════════════════════════════════════════════
# BR-MET-402 — the import resolves a PARTY, and refuses an ambiguity
# ══════════════════════════════════════════════════════════════════════════


def test_def1088__an_exact_owner_resolves_AND_the_string_is_kept_as_provenance():
    """⚠ **THIS IS THE ASSERTION THAT MAKES THE ALIAS RE-POINTING SAFE.**

    `DEF-1247` objected that moving the `Owner` header to the typed column
    *"silently re-points every existing customer template at a different
    column"*. It does not, and this is why: the load writes **both** — the typed
    link AND the operator's own string into `owner_manager`, which is BR-MET-151
    clause 4's provenance and what `unmatched_premises_qs()` reads.

    A utility whose CSV has always carried an `Owner` column therefore keeps
    everything it recorded before and gains a resolved party. Strict addition.
    """
    record = import_runs._resolve_owner_ref(
        {}, {"owner_ref": "Ridge Property LLC"}, {"ridge property llc": "own-1"}
    )
    assert record["owner_id"] == "own-1"
    assert record["owner_manager"] == "Ridge Property LLC", (
        "DEF-1247: the operator's own string must still reach owner_manager, or "
        "re-pointing the header WOULD lose what their file used to record."
    )


def test_def1088__an_explicit_legacy_column_wins_over_the_derived_one():
    """A file that maps BOTH columns means them separately, and a derived value
    must never overwrite one the operator actually supplied."""
    record = import_runs._resolve_owner_ref(
        {"owner_manager": "Typed by the operator"},
        {"owner_ref": "Ridge Property LLC"},
        {"ridge property llc": "own-1"},
    )
    assert record["owner_manager"] == "Typed by the operator"
    assert record["owner_id"] == "own-1"


def test_def1088__an_unresolved_owner_writes_NO_link_and_still_keeps_the_name():
    """The first-upload case, and the reason it is a WARNING and not an ERROR:
    a new tenant holds no typed owners at all, so every row lands here."""
    record = import_runs._resolve_owner_ref({}, {"owner_ref": "Nobody Ltd"}, {})
    assert "owner_id" not in record
    assert record["owner_manager"] == "Nobody Ltd"


def _world_with(exact, near):
    from apps.metering import import_rules

    return import_rules.World(
        enabled_services=set(),
        premises_type_codes=set(),
        area_names=set(),
        existing_premise_nos=set(),
        existing_addresses=set(),
        owner_exact=exact,
        owner_near=near,
    )


def test_def1088__a_NEAR_match_LOADS_OWNERLESS_and_names_the_candidate():
    """PO decision 3 still enforced — and CR-055 changed what it COSTS.

    ⛔ **THIS CASE ASSERTED THE OPPOSITE UNTIL 2026-08-31 AND ITS OLD FAILURE IS
    QUOTED HERE ON PURPOSE**, because a test that flips is the one place a
    reader can see a ruling actually moved rather than take a commit message's
    word for it (hard-won law 1). Under the new rule row it reported:

        E       AssertionError: assert False is True
        E        +  where False = DeclaredRule(code='PRM.OWNER_NEAR_MATCH', …,
                    action='flag_only', rule_kind='owner_near_match', …).blocks

    **PO ruling 2026-08-31 (CR-055):** an owner name that matches no party
    exactly but resembles two or more of them LOADS THE PREMISES WITH NO OWNER,
    flagged, exactly as a blank Owner column already does.

    ⚠ **DECISION 3 IS INTACT AND THIS CASE IS WHERE THAT IS VISIBLE.** *"Offer
    the match, clerk decides"* says the import may not PICK. It still does not:
    the hit NAMES the candidate and resolves nothing, and
    `test_cr055__a_near_match_row_writes_NO_owner_id` proves no `owner_id`
    is written. What changed is that refusing to choose no longer costs the
    operator the address.
    """
    from apps.metering import import_rules

    rows = [{"row_no": 7, "mapped": {"owner_ref": "Ridge Property, L.L.C."}}]
    world = _world_with({}, {"ridge property": [{"id": "own-1", "name": "Ridge Property LLC"}]})
    hits = import_rules._eval_owner_near_match(rows, world, None)
    assert [hit.row_no for hit in hits] == [7]
    assert "Ridge Property LLC" in hits[0].problem, (
        "CR-055: the candidate name must stay in the sentence — the person settling "
        "this row is choosing between named parties, not re-running the search."
    )
    # And the rule that owns it NO LONGER BLOCKS the load.
    rule = next(r for r in import_rules.PREMISES_RULES if r.code == "PRM.OWNER_NEAR_MATCH")
    assert rule.blocks is False, (
        "CR-055 (PO 2026-08-31): a near owner match must not reject the row. "
        "A big migration cannot stall on a spelling."
    )
    assert rule.action == import_rules.FLAG_ONLY
    assert rule.severity == import_rules.WARNING


def test_def1088__an_UNKNOWN_owner_FLAGS_and_LOADS__or_a_first_upload_refuses_every_row():
    """⚠ **THE SEVERITY IS THE DESIGN, AND `DEF-1088` STATES IT IN AS MANY
    WORDS:** *"the ruling makes the owner MANDATORY, so this must ship BEFORE the
    mandatory field, or a utility's first upload refuses every row it carries."*
    """
    from apps.metering import import_rules

    rows = [{"row_no": 3, "mapped": {"owner_ref": "Nobody Ltd"}}]
    hits = import_rules._eval_owner_not_on_file(rows, _world_with({}, {}), None)
    assert [hit.row_no for hit in hits] == [3]
    rule = next(r for r in import_rules.PREMISES_RULES if r.code == "PRM.OWNER_NOT_ON_FILE")
    assert rule.blocks is False, (
        "DEF-1088: an unknown owner must NOT block. On a first upload every row is unknown, "
        "so an ERROR here refuses the whole file."
    )
    assert rule.action == import_rules.FLAG_ONLY


def test_def1088__an_EXACT_name_fires_NEITHER_rule():
    """The reuse path is silent, because it is a fact and not a question."""
    from apps.metering import import_rules

    rows = [{"row_no": 1, "mapped": {"owner_ref": "Ridge Property LLC"}}]
    world = _world_with(
        {"ridge property llc": "own-1"},
        {"ridge property": [{"id": "own-1", "name": "Ridge Property LLC"}]},
    )
    assert import_rules._eval_owner_near_match(rows, world, None) == []
    assert import_rules._eval_owner_not_on_file(rows, world, None) == []


def test_def1088__a_file_with_no_owner_column_fires_NEITHER_rule():
    """A column nobody mapped is not a problem with the data."""
    from apps.metering import import_rules

    rows = [{"row_no": 1, "mapped": {"address_line": "12 Oak St"}}]
    world = _world_with({}, {})
    assert import_rules._eval_owner_near_match(rows, world, None) == []
    assert import_rules._eval_owner_not_on_file(rows, world, None) == []


# ══════════════════════════════════════════════════════════════════════════
# Existing data — kept, never dropped and never invented
# ══════════════════════════════════════════════════════════════════════════


def test_def650__migration_0041_writes_NO_DATA(owner_tenant):
    """⚠ **THE EXISTING-DATA DECISION, ASSERTED RATHER THAN PROMISED IN A
    DOCSTRING** (hard-won law 1: a comment claiming a guarantee is not the
    guarantee).

    Two wrong answers were available and both are refused: dropping the free text
    loses a utility's own record of who owns an address, and inventing parties
    from strings invents customers — *Whitfield Rentals LLC* and *Whitfield
    Rentals, L.L.C.* are one party or two and no algorithm knows which
    (BR-MET-151 clause 3). So the text is KEPT and the link is required going
    FORWARD, which is the same call `metering 0040` made for the same rows.
    """
    import importlib

    module = importlib.import_module("apps.metering.migrations.0041_def650_owner_master_account")
    kinds = {type(op).__name__ for op in module.Migration.operations}
    assert kinds == {"AddField"}, (
        f"DEF-650: metering 0041 must add a column and touch no row, got {sorted(kinds)}"
    )


def test_def650__a_premises_that_ALREADY_has_free_text_and_no_party_still_saves(owner_tenant):
    """The pre-ruling state is still a real state, and the matching surface still
    finds it. `create_premises` refuses to CREATE one — that is BR-MET-401 — but
    a row already on disk is untouched and is listed for a person to work."""
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        # `services_available` is named because this tenant sells water, sewer
        # and trash — the helper's default names electric, which BR-MET-003
        # refuses here and which would fail this test for a reason that has
        # nothing to do with owners.
        row = make_unmatched_premises(  # noqa: F405
            actor,
            owner_manager="Ridge Property LLC",
            services_available=["water"],
        )
        unmatched = list(premises_owners.unmatched_premises_qs().values_list("id", flat=True))
        # It saves, it keeps its name, and it is FINDABLE.
        assert str(row["id"]) in {str(value) for value in unmatched}
        stored = metering_models.Premises.objects.get(pk=row["id"])
        assert stored.owner_manager == "Ridge Property LLC"
        assert stored.owner_id is None


def test_cr089_b1__an_explicitly_EMPTY_owner_is_accepted_like_an_absent_one(owner_tenant):
    """The mirror of the case above, and it is kept for the reason it was
    written: `{"owner_id": None}` and `{"owner_id": ""}` state the same fact as
    sending no key at all — *this address names no owner*.

    ⚠ **IT USED TO PROVE A HOLE WAS CLOSED; IT NOW PROVES THE THREE SHAPES STILL
    AGREE.** The original guard asked `"owner_id" in payload`, so an explicit
    clear satisfied a MANDATORY field. `B1` removed the requirement, so there is
    no longer a hole to fall through — but the three spellings must still mean
    ONE thing, or a client sending `""` would get a different row from a client
    sending nothing, and nobody would notice for months.

    ⚠ **A NONSENSE owner_id IS STILL REFUSED BY NAME**, asserted last, because
    that is the half of `_resolve_owner` the reversal did NOT touch and the
    easiest thing to delete by accident while removing the requirement above it.
    """
    tenant, actor = owner_tenant
    with tenant_ctx(tenant):
        for index, empty in enumerate((None, "")):
            created = metering_services.create_premises(
                actor, {"address_line": f"3 Quarry Rd #{index}", "owner_id": empty}
            )
            assert created["owner"] is None

        with pytest.raises(errors.ValidationError) as caught:
            metering_services.create_premises(
                actor,
                {"address_line": "5 Quarry Rd", "owner_id": "01a08246-0000-7000-8000-000000000000"},
            )
        assert caught.value.message_key == "metering.premises.owner_unknown", (
            "B1 relaxes SAYING NOTHING; it must not relax saying something wrong"
        )

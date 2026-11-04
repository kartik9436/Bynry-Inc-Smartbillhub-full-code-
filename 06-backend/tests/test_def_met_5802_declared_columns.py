# ── Trace ──────────────────────────────────────────────
# Change:  DEF-MET-5802 (the premises and units import templates carry columns
#          nobody chose) + DEF-MET-5803 (the owner-name question), PO
#          2026-09-19: *"okay I want updated CSV file"*.
# Rules:   BR-MET-088 (the picker may not offer a column with nothing behind it
#          and may not omit one that exists) · BR-MET-096 (one runner, every
#          target, no branch on the target name) · BR-MET-151 clause 4 (the
#          operator's owner string is kept as provenance) · BR-CUS-1022 /
#          BR-CUS-1023 + PO 2026-09-01 (*"If owner name is given and one
#          identify given - DL, SSN, Phone or Tax ID - then you create master
#          account and Customer ID - otherwise dont create anything"*) ·
#          CLAUDE.md hard-won law 2 (built is not wired) · law 7 (prove it RED,
#          and ask what would make it pass wrongly).
# Screens: WFL-01.premises.1 (the sample download) · .2 (the mapping picker).
# ───────────────────────────────────────────────────────
"""The premises and units import columns are DECLARED, and this file is the
protection that declaration owes back.

WHY THIS FILE EXISTS AT ALL
---------------------------
Until 2026-09-19 these two targets DERIVED their offered columns from the
model's own `_meta`. That bought one guarantee for free, and `target_columns`'
own docstring stated it exactly: *"the picker cannot offer a target with no
column behind it and cannot omit one that exists."*

`DEF-MET-5802` takes derivation away, for a reason derivation cannot answer:
`_meta` knows a column EXISTS, and cannot know whether it is a **utility's to
supply**. So nine premises fields and five unit fields written by the
address-matching process were published to every customer's template with
labels generated from their field names — *"Gis parcel id was"*, *"Gis verified
at"*.

**A declared list keeps the first half of that guarantee and loses the second.**
It cannot offer a column that does not exist — the model lookup below refuses
that — but it CAN silently omit one that does, which is precisely what
derivation was protecting against. `test_every_model_column_is_classified` is
that protection, rebuilt: add a field to `premises` or `units` and it goes RED
naming the field until somebody DECIDES whether a utility supplies it.

WHAT WOULD MAKE THESE CHECKS PASS WRONGLY (law 7, habit 2)
----------------------------------------------------------
**Counting.** *"The premises template has 23 columns"* passes on the wrong 23 —
it would pass if `owner` were dropped and a GIS field left in. So every
assertion here names COLUMNS, and the two places a count appears it is stated
beside the names rather than instead of them.

**Asserting only removals.** A check that the nine GIS fields are gone passes
happily on a template that has lost `owner` as well. `test_the_premises_
contract_still_names_the_owner` exists for exactly that, and is the check that
would have caught the mis-diagnosis that produced `DEF-MET-5803`: the owner
name column was reported missing, and it was present all along — supplied by
the very derivation this change replaces.

RED-FIRST PROOF (r11 step 2d, hard-won law 7)
----------------------------------------------
Run against the tree BEFORE this change, in the harness that runs it (pytest),
these failed — quoted verbatim in the decision log of 2026-09-19:

    test_no_machine_written_gis_column_is_offered
    E   AssertionError: premises offers columns the address-matching process
        writes: ['gis_checked_at', 'gis_checked_by', 'gis_key_changed_at',
        'gis_parcel_id_was', 'gis_status', 'gis_unchecked', 'gis_verified',
        'gis_verified_at']

    test_every_model_column_is_classified
    E   AttributeError: module 'apps.metering.import_runs' has no attribute
        'DECLARED_COLUMNS_BY_TARGET'
"""

import csv
import io
import pathlib

import pytest

from apps.metering import import_runs
from apps.metering import models as metering_models

from tests.test_cr028_seed import seeded, silvercreek  # noqa: F401 — fixture chain
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures

#: target -> (its model, its declared tuple, its not-offered table).
CONTRACTS = {
    import_runs.TARGET_PREMISES: (
        metering_models.Premises,
        import_runs.PREMISES_COLUMNS,
        import_runs.PREMISES_COLUMNS_NOT_OFFERED,
    ),
    import_runs.TARGET_UNITS: (
        metering_models.Unit,
        import_runs.UNITS_COLUMNS,
        import_runs.UNITS_COLUMNS_NOT_OFFERED,
    ),
}

#: The columns `DEF-MET-5802` retired, BY NAME and per target. The PO approved
#: this list on 2026-09-19; it is repeated here rather than derived from the
#: not-offered table so that a lane quietly deleting a row from that table
#: cannot make this test agree with it.
RETIRED = {
    import_runs.TARGET_PREMISES: (
        "gis_unchecked",
        "gis_checked_by",
        "gis_checked_at",
        "gis_parcel_id_was",
        "gis_key_changed_at",
        "gis_status",
        "gis_verified",
        "gis_verified_at",
        "owner_manager",
    ),
    import_runs.TARGET_UNITS: (
        "gis_point_id_was",
        "gis_key_changed_at",
        "gis_status",
        "gis_verified",
        "gis_verified_at",
    ),
}

#: The GIS keys a CITY GIVES A UTILITY. These STAY — they are the dividing line
#: the whole defect turns on, so they are asserted present, not merely
#: un-asserted.
CITY_GIVEN_KEYS = {
    import_runs.TARGET_PREMISES: "gis_parcel_id",
    import_runs.TARGET_UNITS: "gis_point_id",
}

#: … and the headings they wear. A kept column with a heading generated from
#: its field name (*"Gis parcel id"*) is the PO's complaint one size smaller.
CITY_GIVEN_LABELS = {
    import_runs.TARGET_PREMISES: "GIS parcel ID",
    import_runs.TARGET_UNITS: "GIS point ID",
}


def _concrete(model):
    return {f.name for f in model._meta.get_fields() if getattr(f, "concrete", False)}


# ═══════════════════════════════════════════════════════════════════════════
# THE DECLARATION CANNOT DRIFT FROM THE SCHEMA — BR-MET-088, BOTH HALVES
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_every_declared_column_is_a_real_model_column(target):
    """Half one: the picker may not offer a column with nothing behind it.

    This is what the assets targets already do — *"the test suite pins every
    column-named entry to a real `Asset` column so the declaration cannot
    drift from the schema"* — and it is the half a declaration keeps cheaply.
    """
    model, declared, _ = CONTRACTS[target]
    real = _concrete(model)
    missing = [name for name in declared if name not in real]
    assert not missing, (
        f"{target} declares columns that {model.__name__} does not have: {missing}. "
        "A declared column with nothing behind it is BR-MET-088's first failure."
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_every_not_offered_column_is_a_real_model_column(target):
    """A withheld column has to be a real one too, or the table is a note about
    a field that no longer exists — which is how an allow-list rots into
    fiction while still looking maintained."""
    model, _, withheld = CONTRACTS[target]
    real = _concrete(model)
    missing = sorted(name for name in withheld if name not in real)
    assert not missing, (
        f"{target} withholds columns that {model.__name__} does not have: {missing}. "
        "Remove the entry — it is describing a field that is gone."
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_every_model_column_is_classified(target):
    """⛔ **HALF TWO, AND THE WHOLE REASON THIS FILE EXISTS: a declaration may
    not silently OMIT a real column.**

    Derivation gave this for free. Declaring takes it away, so it is asserted:
    every concrete field on the model is either DECLARED (a utility supplies
    it), deliberately NOT OFFERED with a written reason, or NEVER_IMPORTABLE
    (the primary key, the tenant, the timestamps, the sample flag).

    **A new field on `premises` fails here, by name, until somebody decides.**
    That decision — is this a utility's to supply? — is the feature
    `DEF-MET-5802` bought, and it is exactly the one that cannot be automated:
    the previous mechanism made it silently, every time, and always answered
    yes.
    """
    model, declared, withheld = CONTRACTS[target]
    classified = set(declared) | set(withheld) | set(import_runs.NEVER_IMPORTABLE)
    unclassified = sorted(_concrete(model) - classified)
    assert not unclassified, (
        f"{model.__name__} has fields nobody has classified: {unclassified}. "
        f"Add each to {target}'s declared tuple if a utility supplies it, or to its "
        "NOT_OFFERED table with the reason it does not. Do not leave it out of both — "
        "that is the silent omission this test exists to prevent."
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_a_withheld_column_is_never_also_declared(target):
    """The two tables must not overlap, or the answer depends on which one a
    reader happens to open."""
    _, declared, withheld = CONTRACTS[target]
    both = sorted(set(declared) & set(withheld))
    assert not both, f"{target} both offers and withholds: {both}"


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_every_withheld_column_states_its_reason(target):
    """⚠ **A NAMED ALLOW-LIST WITH NO REASONS IS A DUMPING GROUND.** The next
    lane has to be able to tell a considered exclusion from one somebody added
    to make this file green."""
    _, _, withheld = CONTRACTS[target]
    unexplained = sorted(name for name, why in withheld.items() if not str(why).strip())
    assert not unexplained, f"{target} withholds without saying why: {unexplained}"


# ═══════════════════════════════════════════════════════════════════════════
# WHAT THE PO ACTUALLY ASKED FOR — BY NAME, NEVER BY COUNT
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_no_machine_written_gis_column_is_offered(target):
    """The nine and the five, by name (`DEF-MET-5802`).

    ⚠ Asserted against the DECLARED tuple rather than only against
    `target_columns`, because the tuple is what a lane edits.
    """
    _, declared, _ = CONTRACTS[target]
    still_offered = [name for name in RETIRED[target] if name in declared]
    assert not still_offered, (
        f"{target} still offers columns the address-matching process writes "
        f"(or the legacy owner box): {still_offered}"
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_the_city_given_gis_key_is_still_offered(target):
    """⛔ **THE MIRROR OF THE TEST ABOVE, AND IT IS NOT SYMMETRY FOR ITS OWN
    SAKE.** `gis_parcel_id` and `gis_point_id` are what a CITY GIVES A UTILITY
    and are in the file being migrated. A lane cleaning up "the GIS columns"
    by prefix would take these two with the other thirteen, and every check
    that only asserts removals would stay green.
    """
    _, declared, withheld = CONTRACTS[target]
    key = CITY_GIVEN_KEYS[target]
    assert key in declared, f"{target} must still offer {key} — the city gives a utility this key"
    assert key not in withheld


def test_the_premises_contract_still_names_the_owner():
    """⛔ **THE CHECK THAT WOULD HAVE CAUGHT `DEF-MET-5803`'s MIS-DIAGNOSIS.**

    That defect was filed saying the premises template carries *"no name
    field"*. It was not true. `owner` is a real FK on `Premises`, it is the
    column `owner_account_verdict` reads as the owner's NAME (through
    `mapped["owner_ref"]`), and a row with no value in it creates nobody at
    all. The report came from reading `PREMISES_OWNER_COLUMNS` — the six
    VIRTUAL identity columns — where the name is legitimately absent, because
    it was being supplied by the DERIVED set this change replaces.

    ⚠ **WHICH MAKES IT THE RISKIEST COLUMN IN THE WHOLE CONTRACT.** Moving
    from derived to declared is exactly the moment `owner` could be dropped by
    hand, and every other test in this file would stay green: the removals
    still pass, the classification still passes (it would be withheld), the
    sample still writes. **Nothing else here asserts that the template can
    name an owner at all.**
    """
    assert "owner" in import_runs.PREMISES_COLUMNS, (
        "premises must offer `owner` — it is the owner's NAME, it is what "
        "owner_account_verdict reads, and without it no owner account is ever created "
        "from an import."
    )
    assert "owner" not in import_runs.PREMISES_COLUMNS_NOT_OFFERED
    label = import_runs.PREMISES_FIELD_OVERRIDES["owner"]["label"]
    assert label == "Owner name", label
    # DEF-1077: a label is only lawful if it is already one of the column's
    # aliases, or the sample stops mapping itself. Asserted, not assumed.
    assert label.lower() in import_runs.PREMISES_ALIASES["owner"], (
        f"{label!r} is not one of `owner`'s aliases, so the sample CSV would no longer "
        "auto-detect its own header (DEF-1077)."
    )


def test_the_owner_name_and_the_retired_legacy_box_cannot_be_confused():
    """`DEF-MET-5803`'s real fault was AMBIGUITY, not absence: two name-shaped
    columns on one template, only one of which created anybody. The legacy box
    is gone from the template; this pins that the two headers are still
    distinct strings, so no file auto-detects the wrong one."""
    owner_label = import_runs.PREMISES_FIELD_OVERRIDES["owner"]["label"].lower()
    legacy_label = import_runs.PREMISES_FIELD_OVERRIDES["owner_manager"]["label"].lower()
    assert owner_label != legacy_label
    assert legacy_label not in import_runs.PREMISES_ALIASES["owner"]


def test_the_load_still_writes_the_owner_string_as_provenance():
    """⛔ **THE STOP-CONDITION ON RETIRING `owner_manager`.**

    The column leaves the TEMPLATE and the FIELD stays, written by
    `_resolve_owner_ref` from the `Owner name` cell (BR-MET-151 clause 4). That
    write is what `unmatched_premises_qs()` reads, what PRM-04 offers a person,
    and what `customers.create_master_account` falls back to for the contact's
    name. Deleting it would strip the name off every imported owner account —
    an ABSENCE, which CLAUDE.md records as invisible to every check this repo
    has. So it is checked here, on the branch that matters.

    ⚠ **`owner_exact` IS EMPTY ON PURPOSE.** That is the FIRST-MIGRATION case:
    nobody is on file yet, no party can be matched, and this write is the only
    place the operator's name survives.
    """
    out = import_runs._resolve_owner_ref(
        {"address_line": "2205 Cedar Ln"},
        {"owner_ref": "Balcones Development LLC"},
        {},
    )
    assert out["owner_manager"] == "Balcones Development LLC"
    assert out.get("owner_id") is None


# ═══════════════════════════════════════════════════════════════════════════
# THE OWNER EMAIL — WIRED, AND NOT AN IDENTIFIER
# ═══════════════════════════════════════════════════════════════════════════


def test_the_owner_email_is_offered_and_is_contact_not_identity():
    """⛔ **THE GUARD ON A SIGNED RULING.** The PO ruled on 2026-09-01 that a
    party is created from *"DL, SSN, Phone or Tax ID"*. An email is not on that
    list, so adding `owner_email` to `OWNER_IDENTIFIER_COLUMNS` — a one-line
    edit that would look like a tidy-up — would let a name-and-email row mint a
    Customer #, reversing a signed ruling without anybody noticing.
    """
    assert "owner_email" in import_runs.PREMISES_OWNER_COLUMN_NAMES
    assert "owner_email" not in import_runs.OWNER_IDENTIFIER_COLUMNS
    assert "owner_email" not in import_runs.OWNER_IDENTIFIER_FIELD
    for kind, columns in import_runs.OWNER_IDENTIFIER_COLUMNS_BY_KIND.items():
        assert "owner_email" not in columns, kind
    # It is virtual, so it may never reach `Premises(**record)`.
    assert "owner_email" in import_runs._NOT_A_COLUMN

    verdict = import_runs.owner_account_verdict(
        {
            "owner_ref": "Balcones Development LLC",
            "owner_kind": "company",
            "owner_email": "ap@balcones.test",
            "owner_account_type": "commercial",
        }
    )
    assert verdict["verdict"] == import_runs.OWNER_ACCOUNT_AWAITING_IDENTITY, (
        "a name and an EMAIL is not an identity — PO 2026-09-01 names DL, SSN, "
        "Phone or Tax ID and nothing else"
    )


def test_the_owner_email_reaches_the_account_door():
    """⛔ **HARD-WON LAW 2 — BUILT IS NOT WIRED.** A column offered on the
    picker, written into the sample CSV and read by nothing renders fine, tests
    green and does not exist. This asserts the block the load actually hands to
    `create_master_account`.
    """
    mapped = {
        "owner_ref": "Balcones Development LLC",
        "owner_kind": "company",
        "owner_tax_id": "75-1234567",
        "owner_account_type": "commercial",
        "owner_email": "ap@balcones.test",
    }
    verdict = import_runs.owner_account_verdict(dict(mapped))
    assert verdict["verdict"] == import_runs.OWNER_ACCOUNT_ELIGIBLE
    contact = import_runs.owner_contact_block(dict(mapped), verdict)
    assert contact["email"] == "ap@balcones.test"
    # `_validate_contact` refuses a contact block with no `full_name` BY NAME,
    # so the email alone would turn a good row into a refused owner account.
    assert contact["full_name"] == "Balcones Development LLC"


def test_a_row_with_no_email_sends_no_contact_block_at_all():
    """⚠ **THE DELIBERATE NON-CHANGE.** With no email this answers `{}`,
    `_validate_contact` reads `{}` as `None`, and the account door falls back
    to the premises' own `owner_manager` — which `_resolve_owner_ref` has
    already written from the same `Owner name` cell. A file with no email
    therefore behaves EXACTLY as it did before this column existed, down to the
    contact's name, and only rows with something new to say move."""
    mapped = {
        "owner_ref": "Balcones Development LLC",
        "owner_kind": "company",
        "owner_tax_id": "75-1234567",
        "owner_account_type": "commercial",
    }
    verdict = import_runs.owner_account_verdict(dict(mapped))
    assert import_runs.owner_contact_block(dict(mapped), verdict) == {}


def test_every_owner_column_says_what_a_blank_cell_means():
    """And the email's sentence is NOT the identity columns' sentence. They all
    used to read *"no owner account is created from this row"*, which is true
    of the six and false of the email — a blank email still creates the
    account. A sentence that is wrong on one column is worse than none, because
    the operator acts on it."""
    by_name = {entry["target"]: entry for entry in import_runs.PREMISES_OWNER_COLUMNS}
    for name, entry in by_name.items():
        assert entry.get("blank_means"), name
    assert by_name["owner_email"]["blank_means"] != by_name["owner_ssn"]["blank_means"]
    assert "still created" in by_name["owner_email"]["blank_means"]


# ═══════════════════════════════════════════════════════════════════════════
# WHAT THE PO WILL READ — THE SAMPLE CSV HEADER
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_the_sample_header_carries_no_retired_column(target, silvercreek):
    """`sample_columns` is the ONE source the sample CSV writes from, so the
    file the PO downloads is asserted here rather than trusted to follow."""
    with tenant_ctx(silvercreek):  # noqa: F405
        labels = [entry["label"] for entry in import_runs.sample_columns(target)]
        names = [entry["target"] for entry in import_runs.sample_columns(target)]
    for retired in RETIRED[target]:
        assert retired not in names, f"{retired} is still written to the {target} sample"
        # ⚠ **AND ITS GENERATED HEADING IS GONE FROM THE FILE.** The PO's
        # complaint was about the HEADING a utility reads — *"Gis parcel id
        # was"*, *"Gis verified at"* — so the header row is checked in the
        # words it actually carries, not only by field name.
        generated = import_runs._label_from(retired)
        assert generated not in labels, f"{generated!r} is still a {target} heading"
    # ⚠ **THIS CHECK WAS WRONG ON ITS FIRST RUN AND THE MISTAKE IS WORTH
    # LEAVING RECORDED.** It read `not any(label.lower().startswith("gis "))`,
    # which is a check that cannot pass: `GIS parcel ID` is a KEPT column with
    # a deliberately curated heading and starts with exactly that prefix. It
    # went red on the correct build — law 7's habit 2 arriving the other way
    # round, where asking *"what would make this pass wrongly"* would also have
    # caught *"what makes it fail rightly"*. The real requirement is that the
    # kept key carries a heading somebody WROTE, so that is asserted by value.
    assert CITY_GIVEN_KEYS[target] in names
    kept_label = dict(zip(names, labels))[CITY_GIVEN_KEYS[target]]
    assert kept_label == CITY_GIVEN_LABELS[target], kept_label
    assert kept_label != import_runs._label_from(CITY_GIVEN_KEYS[target]), (
        "the kept GIS key is still wearing a heading generated from its field name"
    )


def test_the_premises_sample_header_names_the_owner_and_the_email(silvercreek):
    """The columns the two owner defects are about, in the file itself."""
    with tenant_ctx(silvercreek):  # noqa: F405
        _, body = import_runs.sample_csv(import_runs.TARGET_PREMISES)
    header = next(csv.reader(io.StringIO(body)))
    assert "Owner name" in header
    assert "Owner email" in header
    # PO ruling 2026-09-19 — *"Yes add owner category column in csv template"*.
    assert "Owner category" in header
    assert "Owner name (legacy)" not in header
    assert "GIS parcel ID" in header


def test_the_owner_category_is_offered_and_never_guessed():
    """⛔ **PO RULING 2026-09-19 — THE COLUMN EXISTS, AND IT IS A LOOKUP.**

    ⚠ **THE FIVE ARE NOT NAMED IN `import_runs`, AND THAT IS ASSERTED.**
    `owner_occupier`, `landlord`, `property_manager`, `hoa` and `builder` are
    SEEDED into an editable Settings lookup. Hardcoding them in the import
    would be a second opinion about a list `tenancy` owns, and it would go
    stale the first time a utility renamed one — `_account_type_code`'s lesson
    on the column beside it.
    """
    assert "owner_category" in import_runs.PREMISES_OWNER_COLUMN_NAMES
    entry = next(
        e for e in import_runs.PREMISES_OWNER_COLUMNS if e["target"] == "owner_category"
    )
    assert entry["kind"] == import_runs.KIND_LOOKUP
    assert entry["required"] is False, (
        "a required category would refuse the first upload a utility ever sends"
    )
    # It is virtual, so it may never reach `Premises(**record)`.
    assert "owner_category" in import_runs._NOT_A_COLUMN
    assert "owner_category" not in import_runs.PREMISES_COLUMNS

    # ⚠ **THIS CHECK WAS A GREP OF THE SOURCE ON ITS FIRST RUN AND WENT RED ON
    # THE CORRECT BUILD.** It refused the strings `owner_occupier` and
    # `property_manager` anywhere in `import_runs.py` — and they ARE there, in
    # the comment that explains why they must not be hardcoded. **A check that
    # cannot tell a value from a sentence about a value cannot pass**, which is
    # law 7's *what would make this pass wrongly* answered from the other end.
    #
    # The real requirement is that no module-level constant ENUMERATES the
    # categories, because that is the thing that would go stale the first time a
    # utility renamed one. So it looks at the module's values, not its text.
    enumerating = [
        name
        for name, value in vars(import_runs).items()
        if isinstance(value, (list, tuple, set, frozenset, dict))
        and any(
            isinstance(item, str) and item in {"owner_occupier", "property_manager", "hoa"}
            for item in value
        )
    ]
    assert not enumerating, (
        f"{enumerating} enumerate the owner categories inside import_runs — the "
        "list is the tenant's to edit and must be read from the lookup, which is "
        "`premises_owners._resolve_category`'s job"
    )
    # … and the column does NOT ship a fixed option list either, which is the
    # same mistake one layer along: the picker reads the tenant's lookup.
    assert "options" not in entry


def test_every_lookup_owner_column_has_its_raw_twin_stripped():
    """⛔ **THE 500 THIS CHANGE ACTUALLY CAUSED, PINNED SO IT CANNOT RETURN.**

    A `KIND_LOOKUP` column writes `<target>_raw` into `mapped` beside the
    resolved code — the operator's own cell, kept for the receipt. `mapped` is
    then splatted into `Premises(**record)`, so every reserved key has to be in
    `_NOT_A_COLUMN` or the row raises.

    That list spread the owner column NAMES from one declaration and then
    hand-typed `"owner_account_type_raw"` as a single literal. Adding
    `owner_category` produced, on every row that stated a category:

        TypeError: Premises() got unexpected keyword arguments: 'owner_category_raw'

    ⚠ **AND THE COMMENT FOUR LINES ABOVE THAT LITERAL HAD PREDICTED IT** —
    *"a seventh owner column added above and forgotten below would be a 500 on
    every row of somebody's migration"*. It was right, it was read, and it was
    not a guard (hard-won law 1). This is the guard.
    """
    lookups = [
        entry["target"]
        for entry in import_runs.PREMISES_OWNER_COLUMNS
        if entry["kind"] == import_runs.KIND_LOOKUP
    ]
    assert lookups, "the premises owner block has no lookup column, so this test is vacuous"
    missing = [name for name in lookups if f"{name}_raw" not in import_runs._NOT_A_COLUMN]
    assert not missing, (
        f"{missing} would reach `Premises(**record)` as `<name>_raw` and raise on "
        "every row that fills the column in"
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_every_lookup_column_has_a_lookup_index(target, silvercreek):
    """⛔ **A `KIND_LOOKUP` COLUMN WITH NO INDEX RESOLVES TO `None` AND SAYS
    NOTHING ABOUT IT — AND THIS CHANGE SHIPPED ONE FOR EXACTLY ONE TEST RUN.**

    `_map_row`'s lookup branch reads `lookup_indexes.get(target) or {}`, so a
    column whose target is absent from `LOOKUP_INDEX_BUILDERS` resolves every
    cell to `None`. The column still appears on the picker, still writes into
    the sample CSV, still maps cleanly and still shows **Matched**. Nothing
    errors anywhere.

    ⚠ **THAT IS `DEF-771`'s EXACT SHAPE** — *"a utility's 9,881-row file said
    `city customer plan` in every cell, mapped clean, showed Matched, and
    loaded 9,881 units with no plan"* — and `owner_category` reproduced it on
    the first end-to-end run: the party was never created because the code
    never resolved. The failure is invisible to every check that reads the
    column contract, which is what this file otherwise does.
    """
    with tenant_ctx(silvercreek):  # noqa: F405
        offered = import_runs.target_columns(target)
        indexes = import_runs._lookup_indexes_for(target)
    lookups = [
        entry["target"]
        for entry in offered
        if entry["kind"] == import_runs.KIND_LOOKUP
    ]
    missing = [name for name in lookups if name not in indexes]
    assert not missing, (
        f"{target} offers lookup columns with no index: {missing}. Every cell in "
        "them resolves to None, silently — the picker still says Matched."
    )
    # ⚠ **AND THE INDEX MUST NOT BE EMPTY**, or the column is offered over a
    # list this tenant has nothing in, which reads identically to the operator.
    for name in lookups:
        assert indexes[name], f"{target}.{name} has an EMPTY lookup index"


def test_a_blank_category_is_not_a_verdict_and_changes_no_outcome():
    """⛔ **THE RULING ADDS A WAY TO STATE A CATEGORY. IT DOES NOT MAKE ONE
    REQUIRED.**

    `BR-MET-151` clause 3 forbids reading a category off a name, and the
    2026-08-27 ruling that an ownerless address still LOADS is untouched. So a
    row with everything but a category must still earn its account — a utility
    that has not set its categories up yet has to be able to load its
    addresses, which is `DEF-1088`'s lesson.

    ⚠ **THE MIRROR IS ASSERTED TOO.** A test that only checked the blank case
    would pass on an implementation that ignored the column entirely.
    """
    base = {
        "owner_ref": "Told You Holdings",
        "owner_kind": "company",
        "owner_tax_id": "84-7654321",
        "owner_account_type": "commercial",
    }
    blank = import_runs.owner_account_verdict(dict(base))
    assert blank["verdict"] == import_runs.OWNER_ACCOUNT_ELIGIBLE
    assert blank["category"] is None

    stated = import_runs.owner_account_verdict({**base, "owner_category": "landlord"})
    assert stated["verdict"] == import_runs.OWNER_ACCOUNT_ELIGIBLE
    assert stated["category"] == "landlord"


def test_the_fifth_verdict_has_a_stage_three_rule_and_a_receipt_key():
    """⛔ **LAW 7'S *REPORTING ZERO OVER A SCOPE IT SILENTLY EXCLUDES*, IN A
    RECEIPT.** `owner_account_verdict` answers five ways; the loader's chain had
    a branch for four, so a row naming nobody was warned at rehearsal and
    counted nowhere, and `premises_owner_blank` read 0 over it.

    ⚠ **ASSERTED AGAINST THE SOURCE OF THE CHAIN, NOT A RUN.** Reaching the
    fifth branch through a real load needs a row that maps an Owner column and
    leaves it empty, which several other rules also fire on; pinning the branch
    itself is what says the verdict can never again fall off the end.
    """
    source = io.open(import_runs.__file__, encoding="utf-8").read()
    for verdict in (
        "OWNER_ACCOUNT_AWAITING_IDENTITY",
        "OWNER_ACCOUNT_NO_ACCOUNT_TYPE",
        "OWNER_ACCOUNT_IDENTITY_MISMATCH",
        "OWNER_ACCOUNT_NO_OWNER",
    ):
        assert f'verdict["verdict"] == {verdict}' in source, (
            f"{verdict} has no branch in the loader's chain, so rows earning it "
            "are counted nowhere"
        )


@pytest.mark.parametrize(
    "code", ["PRM.OWNER_CATEGORY_MISSING", "PRM.OWNER_CATEGORY_IN_LOOKUP"]
)
def test_the_category_rules_are_declared_evaluated_and_never_block(code):
    """A `DeclaredRule` nobody evaluates is a row that does nothing (law 2, one
    layer below the UI), and an ERROR here would refuse a first upload —
    `DEF-1088`: on a first upload every row is unknown.

    ⚠ **BOTH RULES, BECAUSE THEY ARE A PAIR AND ONLY ONE MAY FIRE.** One says
    *the row did not say what kind of owner this is*; the other says *what it
    said is not on your list*. Asserting only the first would leave the second
    registered-by-hope.
    """
    from apps.metering import import_rules

    rule = next(r for r in import_rules.PREMISES_RULES if r.code == code)
    assert rule.rule_kind in import_rules.EVALUATORS, (
        f"{code} is declared and nothing evaluates it, so it can never fire"
    )
    assert rule.action == import_rules.FLAG_ONLY
    assert rule.blocks is False


def test_only_one_of_the_two_category_rules_can_fire_on_a_row():
    """⛔ **TWO WARNINGS ON ONE ROW LEAD TO TWO DIFFERENT NEXT ACTIONS**, which
    is the exact fault the owner rules' three-way split exists to avoid
    (`DEF-771` clause 3). A blank cell is `MISSING`'s row; an unrecognised value
    is `IN_LOOKUP`'s, and `MISSING` stands down on it — without that, an
    operator who typed a typo is told BOTH that they said nothing and that what
    they said is wrong.
    """
    from apps.metering import import_rules

    class _World:
        owner_exact: dict = {}
        owner_near: dict = {}

    eligible = {
        "owner_ref": "Told You Holdings",
        "owner_kind": "company",
        "owner_tax_id": "84-7654321",
        "owner_account_type": "commercial",
    }
    blank = [{"row_no": 1, "mapped": dict(eligible)}]
    typo = [
        {
            "row_no": 2,
            "mapped": {**eligible, "owner_category_raw": "not_a_real_category"},
        }
    ]
    world = _World()
    missing = import_rules.EVALUATORS["owner_category_missing"]
    in_lookup = import_rules.EVALUATORS["owner_category_in_lookup"]

    assert [h.row_no for h in missing(blank, world, None)] == [1]
    assert in_lookup(blank, world, None) == []
    assert [h.row_no for h in in_lookup(typo, world, None)] == [2]
    assert missing(typo, world, None) == []


def test_the_shipped_sample_row_EARNS_an_owner_account(silvercreek):
    """⛔ **THE FILE WE HAND A UTILITY TO COPY MUST NOT MODEL THE FAILURE THEY
    REPORTED.**

    Until this test the premises sample said **`person`** in the owner-kind cell
    and left the other eight owner columns empty — no name, no identifier, no
    account type, no category. Run through the loader that row answers
    `no_owner`: no party, no master account, nothing. **That is the complaint
    that started this work** — *"we import premises, provide owner details, and
    no Master Account is generated"* — shipped as the worked example.

    ⚠ **A BLANK CELL IS NOT NEUTRAL IN A SAMPLE, IT IS INSTRUCTION.** An
    operator opens it to learn what goes in each column, and one committing
    value beside eight blanks teaches that the rest are decorative. The lone
    `person` made it worse than all-blank, because the section looked
    demonstrated.

    ⚠ **THIS IS THE ONE CHECK HERE THAT CANNOT PASS WHILE THE SAMPLE IS
    WRONG**, and it is why it asserts the VERDICT rather than the cells: a test
    that listed the nine expected values would pass on a row that is
    self-consistent and still earns nothing — a Tax ID under a `person`, say,
    or a category this tenant does not hold.
    """
    with tenant_ctx(silvercreek):  # noqa: F405
        _, body = import_runs.sample_csv(import_runs.TARGET_PREMISES)
        rows = list(csv.DictReader(io.StringIO(body)))
        assert len(rows) == 1, "the premises sample is header plus ONE worked row"
        row = rows[0]
        by_label = {
            entry["label"]: entry["target"]
            for entry in import_runs.sample_columns(import_runs.TARGET_PREMISES)
        }
        # The sample's own header row, mapped by the product's own detector —
        # so this reads the file exactly as an operator uploading it would.
        mapped = {by_label[label]: value for label, value in row.items() if label in by_label}
        mapped["owner_ref"] = mapped.pop("owner", "")
        verdict = import_runs.owner_account_verdict(dict(mapped))

    assert verdict["verdict"] == import_runs.OWNER_ACCOUNT_ELIGIBLE, (
        "the shipped sample's owner row earns NOTHING — it is the reported "
        f"defect handed over as an example. verdict={verdict['verdict']}, "
        f"kind={verdict['kind']}, identifiers={sorted(verdict['identifiers'])}, "
        f"account_type={verdict['account_type']!r}, category={verdict['category']!r}"
    )
    # … and it earns an OWNER RECORD too, which is the half the account count
    # never showed (`DEF-MET-5838`).
    assert verdict["category"], "no category, so the row makes an account nobody owns"
    # ⚠ **NO GOVERNMENT IDENTIFIER IS INVENTED** — `DEF-962`'s reason, honoured
    # rather than overridden. The person is created from the PHONE.
    assert verdict["identifiers"] == {"phone": "555-0142"}, verdict["identifiers"]
    assert not row["Owner Social Security number"]
    assert not row["Owner driving licence"]
    # ⚠ **AND THE TWO LOOKUP CELLS RESOLVED**, which is the bug this lane
    # shipped for one test run: a `KIND_LOOKUP` cell that resolves to `None`
    # still maps and still reads `Matched`.
    assert row["Owner account type"] and row["Owner category"]
    assert row["Owner name"] and row["Owner email"]

    # ⛔ **THE ROW MUST BE INTERNALLY COHERENT, NOT MERELY ELIGIBLE.**
    # `eligible` is a weaker statement than it looks: the first version of this
    # sample read `Creekside Laundromat` — a BUSINESS — filed as a `person` and
    # an `owner_occupier`, and it passed **only** because a phone is a valid
    # identifier for a person. The same row with a Tax ID answers
    # `identity_mismatch`. So the file a utility is handed to copy demonstrated
    # a business filed as an individual, which is the exact mistake
    # `PRM.OWNER_IDENTITY_MISMATCH` exists to catch.
    kind = str(row["Owner is a person or a company"]).strip().lower()
    allowed = import_runs.OWNER_IDENTIFIER_COLUMNS_BY_KIND[kind]
    presented = [
        column
        for column in import_runs.OWNER_IDENTIFIER_COLUMNS
        if str(mapped.get(column) or "").strip()
    ]
    assert presented, "the sample states a kind and presents no identifier for it"
    borrowed = [column for column in presented if column not in allowed]
    assert not borrowed, (
        f"the sample says the owner is a {kind} and fills in {borrowed} — an "
        "identifier belonging to the other kind. The sample may not teach the "
        "mistake PRM.OWNER_IDENTITY_MISMATCH exists to catch."
    )


@pytest.mark.django_db
def test_the_shipped_sample_names_NOBODY_REAL(silvercreek):
    """⛔ **A SAMPLE MUST NOT CARRY A CUSTOMER'S OWN DATA, AND THIS ONE DID.**

    The owner-name cell briefly read *the tenant's own first typed owner* — on
    the reasoning that a row this tenant already has is not a guess, which is
    correct for a REFERENCE and wrong for a NAME. On the beta tenant it came out
    `Creekside Laundromat`, a live `premises_owners` row, **in a file any
    operator can download**; and an operator who loads the sample unmodified
    attaches a property to a real owner record.

    ⚠ **THE DISTINCTION IS WHETHER ANYTHING HAS TO RESOLVE.** The account type
    and the category are LOOKUPS and must come from the tenant, or the sample
    ships the resolve-to-nothing bug as an instruction. A name resolves against
    nothing — `owner_account_verdict` reads it as free text — so it can be, and
    must be, fiction like every other invented cell in the row.

    ⚠ **THIS IS THE CHECK THAT WOULD HAVE CAUGHT IT**, and it is cheap: the
    name in the shipped file is not the name of any party on this tenant.
    """
    from apps.metering import models as metering_models

    with tenant_ctx(silvercreek):  # noqa: F405
        _, body = import_runs.sample_csv(import_runs.TARGET_PREMISES)
        row = next(csv.DictReader(io.StringIO(body)))
        name = str(row["Owner name"]).strip()
        real = set(
            metering_models.PremisesOwner.objects.filter(tenant_id=silvercreek.id)
            .values_list("name", flat=True)
        )
    assert name, "the sample names no owner at all"
    assert name not in real, (
        f"the shipped sample names {name!r}, which is a REAL owner on this tenant — "
        "a downloadable template must not carry a customer's own data, and loading "
        "it unmodified would attach a property to that party"
    )
    # … and it is recognisably a placeholder, in the same register as the rest
    # of the row (`Sample Building`, `12 Sample Street`).
    assert "sample" in name.lower(), name


@pytest.mark.parametrize(
    ("target", "committed"),
    [("premises", "premises-sample.csv"), ("units", "units-sample.csv")],
)
def test_the_COMMITTED_sample_matches_what_the_product_SERVES(target, committed, silvercreek):
    """⛔ **TWO ARTEFACTS CLAIMING TO BE THE SAME FILE, AND THEY HAD ALREADY
    DISAGREED** — hard-won law 5, *"one generated file, committed once"*.

    `12-governance/24-import-templates/` holds the corrected samples because the
    PO asked to SEE them (*"okay I want updated CSV file"*). They are evidence,
    not a source — nothing reads them, and the product generates the real file
    from `sample_columns` every time it is asked. **So they can rot, and one
    already had**: the committed premises file said `Sample Owner` while the
    served file on the beta tenant said `Creekside Laundromat`. Neither was
    wrong about itself; nothing compared them.

    ⚠ **THE SAMPLE IS PER-TENANT BY DESIGN, SO THIS PINS IT TO ONE.** The
    services are the tenant's enablement, the account type and the owner
    category are its own lookups, and a units row names its own first premises.
    A committed capture can therefore only ever be *"what this file looks like
    for THIS utility"* — the fixture tenant — and that is what is asserted. A
    change to the contract, or to what the fixture seeds, turns this red and
    somebody regenerates, which is the whole point: drift becomes visible
    instead of silent.
    """
    root = pathlib.Path(__file__).resolve().parents[2]
    path = root / "12-governance" / "24-import-templates" / committed
    assert path.exists(), f"the committed evidence file is missing: {path}"
    with tenant_ctx(silvercreek):  # noqa: F405
        _, served = import_runs.sample_csv(target)
    assert path.read_text(encoding="utf-8") == served, (
        f"{committed} no longer matches what the product serves for the fixture "
        "tenant. Regenerate it from `import_runs.sample_csv` rather than editing "
        "it by hand — it is a capture, not a source."
    )


@pytest.mark.parametrize("target", sorted(CONTRACTS))
def test_the_sample_still_maps_itself(target, silvercreek):
    """⛔ **`DEF-616`'s PROPERTY, RE-ASSERTED BECAUSE THIS CHANGE MOVES TWO
    LABELS.** The one file a first-time operator is told to start from has to
    auto-detect every one of its own headers. Renaming `Owner` to `Owner name`
    and `Gis parcel id` to `GIS parcel ID` is exactly the edit that breaks it.
    """
    with tenant_ctx(silvercreek):  # noqa: F405
        _, body = import_runs.sample_csv(target)
        header = next(csv.reader(io.StringIO(body)))
        detected = import_runs._auto_map(header, target)
    unmapped = sorted(set(header) - set(detected))
    assert not unmapped, f"the {target} sample ships headers it cannot detect: {unmapped}"


# ═══════════════════════════════════════════════════════════════════════════
# A SAVED MAPPING THAT NAMES A RETIRED COLUMN — DEGRADE, NEVER CRASH
# ═══════════════════════════════════════════════════════════════════════════


def test_a_saved_template_naming_a_retired_column_degrades_instead_of_refusing(silvercreek):
    """⛔ **THE BLAST RADIUS OF `DEF-MET-5802`, AND IT IS NOT HYPOTHETICAL.**

    An `ImportMapping` is a tenant's own row written months ago; retiring a
    column does not go back and edit it. The suggestion used to be returned
    VERBATIM, so a saved template naming `owner_manager` would pre-fill the
    picker with a column that no longer exists, the operator would confirm it,
    and `_transform_locked` would refuse the whole run with
    `metering.import.unknown_mapping_target`. **A run that cannot be mapped at
    all is not an honest degradation — it is a crash with a message key.**

    The retired entry is DROPPED, so its source column arrives UNMAPPED and the
    operator is asked to decide about it. ⚠ **And the surviving entries are
    asserted too**: a filter that dropped everything would also pass a test
    that only checked the retired one was gone.
    """

    class _StaleTemplate:
        mapping = {
            "ADDR1": {"target": "address_line"},
            "OWNER/MANAGER": {"target": "owner_manager"},
            "GIS_VERIFIED_AT": {"target": "gis_verified_at"},
            "LEGACY_KEY": {"target": "external_ref"},
            "NOTES": {"target": import_runs.IGNORE},
        }

    with tenant_ctx(silvercreek):  # noqa: F405
        suggestion = import_runs._detected_mapping(
            _StaleTemplate(),
            ["ADDR1", "OWNER/MANAGER", "GIS_VERIFIED_AT", "LEGACY_KEY", "NOTES"],
            import_runs.TARGET_PREMISES,
        )

    assert "OWNER/MANAGER" not in suggestion
    assert "GIS_VERIFIED_AT" not in suggestion
    # The rest of the tenant's map survives — including an explicit ignore,
    # which is a mapping CHOICE and not a column.
    assert suggestion["ADDR1"] == "address_line"
    assert suggestion["LEGACY_KEY"] == "external_ref"
    assert suggestion["NOTES"] == import_runs.IGNORE


def test_a_confirmed_mapping_naming_a_retired_column_is_ignored_not_refused():
    """⛔ **THE OTHER HALF OF THE BLAST RADIUS, AND THE ONE THAT MATTERS MOST.**

    Dropping a retired target from the SUGGESTION protects an operator who
    clicks through the picker. It does nothing for the mapping a client
    actually POSTs — a saved `ImportMapping` the UI loaded, a script, a retry,
    a spreadsheet built from last year's sample — and `_transform_locked`
    refused every one of those with `metering.import.unknown_mapping_target`,
    **failing the whole run over a column WE withdrew.** The operator cannot
    map their way out of that: the target they are refused for no longer
    exists to be re-pointed.

    ⚠ **MEASURED, NOT PREDICTED.** The shared premises MAPPING in
    `test_cr023_import_stages.py` points a header at `owner_manager`, which is
    exactly what a tenant's saved mapping does — and `DEF-MET-5802` turned 51
    passing tests across six files into failures in one stroke. That count was
    the product defect showing up in a suite, not a fixture problem.

    ⚠ **AND A TARGET THAT NEVER EXISTED STILL REFUSES.** The forgiveness is
    scoped to `NOT_OFFERED_COLUMNS_BY_TARGET` — a declared list of columns
    withdrawn on purpose — so a typo is still an error. Widening it to
    *"anything unrecognised"* would turn every misspelled target into silently
    unloaded data, which is `DEF-632`'s shape.
    """
    # The retired set and the refusing set are asserted as two DIFFERENT
    # answers; a test naming only the first passes on a build that forgives
    # everything.
    assert "owner_manager" in import_runs.PREMISES_COLUMNS_NOT_OFFERED
    assert "gis_verified_at" in import_runs.PREMISES_COLUMNS_NOT_OFFERED
    assert "not_a_column_anybody_ever_had" not in import_runs.PREMISES_COLUMNS_NOT_OFFERED

    source = io.open(import_runs.__file__, encoding="utf-8").read()
    branch = "if target_name in NOT_OFFERED_COLUMNS_BY_TARGET.get(run.target, {}):"
    assert branch in source, (
        "`_transform_locked` no longer forgives a RETIRED target, so every saved "
        "mapping naming one fails the whole run"
    )
    # … and it resolves to an explicit ignore rather than being dropped, so the
    # operator's column is accounted for rather than quietly absent.
    after = source.split(branch, 1)[1][:400]
    assert "retired_targets[source] = target_name" in after
    assert '"target": IGNORE' in after


def test_the_generated_system_defaults_carry_no_retired_column(silvercreek):
    """The two system rows are GENERATED from `sample_columns`, so they follow
    this change by construction. ⚠ **Existing tenants' rows do not** — they
    were written at provisioning and are refreshed by a reference-data replay
    (`import_mappings` is in `RERUN_REFERENCE_LISTS`, and the handler updates an
    existing system row's mapping). Until that replay runs, the test above is
    what keeps a stale default from refusing a run."""
    with tenant_ctx(silvercreek):  # noqa: F405
        entries = {entry["target"]: entry for entry in import_runs.default_import_mapping_entries()}
    for target in CONTRACTS:
        targets = {spec["target"] for spec in entries[target]["mapping"].values()}
        for retired in RETIRED[target]:
            assert retired not in targets, f"{target} default still maps {retired}"
    premises_sources = set(entries[import_runs.TARGET_PREMISES]["mapping"])
    assert "Owner name" in premises_sources
    assert "Owner email" in premises_sources
    assert "Owner category" in premises_sources

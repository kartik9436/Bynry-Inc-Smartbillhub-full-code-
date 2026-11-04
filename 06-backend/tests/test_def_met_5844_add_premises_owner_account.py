# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-5844 — the Add Premises form creates no Master Account. PO,
#          from the live product: *"when user add propery from add new premise
#          form - user provides owner type, name, managed by input but system
#          does not create master account"*.
# Story:   US-MET-003 (S16 guided add)
# Rules:   BR-MET-1010 (the owner's account at an address) · BR-MET-151 clause 3
#          (never read a category off a name) · BR-MET-112 (a wizard does not
#          mint an account because a field was filled in) · BR-CUS-1024 (no
#          identifier, no account)
# Question: OQ-MET-12472 (the owner nobody has identified — CR-056's *every
#          address gets its owner a Master Account* against BR-CUS-1024)
# ───────────────────────────────────────────────────────
"""The Add Premises form's owner account: the two gates, and what each reports.

⚠ **WHY THIS FILE EXISTS AT ALL, AND IT IS HARD-WON LAW 2 RATHER THAN A MISSING
BRANCH.** `ensure_owner_master_account` has worked since `CR-056` W1 and has its
own suite. New Connect calls it and the premises import calls its sibling.
**`create_premises` called neither**, and no test anywhere asked whether it did
— every existing premises-create test asserts what was written to `premises`, so
all of them passed over an account that was never opened. *A door that works is
not a door somebody walks through*, and the check that was missing is the one
that asks whether anybody walked through it.

⚠ **PROVED RED FIRST (hard-won law 7), against `apps/metering/services.py` as it
stood at `ca3050616`.** With the call site deleted and `owner_master_account`
taken off the response, the whole file was run: **6 failed, 1 passed, 17.47s**.
The one that passed is `the_account_type_is_not_written_onto_the_premises`, and
it passes because the RED version keeps the tolerated payload key and removes
only the call — which is the honest shape of the defect and is why that case is
in this file at all. The failures, quoted from that run:

    tests/test_def_met_5844_add_premises_owner_account.py:100: KeyError
    E   KeyError: 'owner_master_account'

and, on the warning assertion that does not read that key:

    E   AssertionError: assert [] == ['no_account_type']

⚠ **THE SAVEPOINT THIS FILE CANNOT TEST, SAID OUT LOUD (CLAUDE.md law 14).**
`config/settings/test.py` hardcodes in-memory SQLite, which has **no aborted-
transaction state**, so `test_a_refused_account_leaves_the_address_standing`
below passes with or without the nested `transaction.atomic()` in
`_ensure_owner_master_account`. **It is not proof of the savepoint and must
never be cited as such.** The savepoint was proved on real PostgreSQL 16, by
running the same refusal twice with and without it:

    WITH savepoint    -> the address SURVIVED the refusal: True
    WITHOUT savepoint -> InternalError: current transaction is aborted,
                         commands ignored until end of transaction block

The script is `10-scripts/def_met_5844_owner_account_readback.py`. A lane that
"simplifies" the savepoint away will see this file stay green.
"""

import pytest

from apps.customers import models as cus
from apps.metering import models, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import owner_for, tenant_ctx

pytestmark = pytest.mark.django_db


def _account_id(created):
    """The ACCOUNT ID out of `owner_master_account`, whatever shape it is in.

    ⛔ **THAT SHAPE CHANGED ON 2026-09-22 (`BR-MET-1181`) AND BOTH ARE READ HERE
    ON PURPOSE.** It used to be an OWNER dict — `owner_detail_dict(...)`, whole
    party, `premises_count` and all — because the door took an owner id. The
    door now takes the ADDRESS, and the key carries that door's own RECEIPT:
    `{created, account_id, account_no, owner_id, owner_linked, reason}`. Reading
    both keys means this helper says nothing about which era a caller is in, so
    a case about an ACCOUNT stays a case about an account.

    ⚠ **THE OLD WARNING IS STILL TRUE AND IS WHY THIS HELPER EXISTS AT ALL —
    THIS LANE MADE THE MISTAKE AND A RED TEST CAUGHT IT.** The value is NOT an
    id, and **comparing two of these dicts for idempotency does not work**: the
    owner's property count moved between two saves, so the second answer
    differed from the first on a field with nothing to do with the account.
    Compare the id.

    ⚠ **AND IT IS NOW THE PREMISES ROW'S `master_account_id` THAT A SCREEN
    READS.** This receipt says what the PRESS did; the row says who owns the
    address. Two different questions, and `test_br_met_1181_premises_master_account.py`
    is where the row's answer is pinned.
    """
    answer = created.get("owner_master_account")
    if answer is None:
        return None
    return answer.get("account_id") or answer.get("master_account_id")


def _reasons(created):
    """The `reason` of every *no owner account* warning, in order."""
    return [
        warning.get("reason")
        for warning in created["warnings"]
        if warning.get("code") == services.OWNER_ACCOUNT_NOT_CREATED
    ]


# ── GATE 1 · NO TYPED OWNER — and a name in a box is not a party ────────────


def test_def_met_5844__an_address_with_no_typed_owner_opens_nothing(brazos, dana):
    """`BR-MET-112` — a wizard does not mint an account because a field was
    filled in.

    ⛔ **THIS CASE ASSERTED THE OPPOSITE OF ITS OWN NAME UNTIL 2026-09-22, AND
    THE PO REVERSED THE RULE IT RESTED ON (`BR-MET-1181`, `DEF-MET-6139`).** It
    used to expect `no_typed_owner` here, and its docstring read: *"The clerk
    typed a name into `Managed by` and picked nobody. There is no party to open
    an account FOR."* **That is exactly the behaviour the PO called a bug** —
    *"why you are point is at owner id - why not directly at master accoutn Id
    … owner IDs are not required hence no screens or fucntionality for it"* —
    because no screen in this product can create an owner record, so the gate
    this case asserted could never be satisfied from the product at all. The old
    text is quoted rather than deleted (hard-won law 1).

    **What it asserts now is the half of the old rule that SURVIVED**, and it is
    the half worth having: a NAME alone still opens nothing. The clerk has named
    a party and chosen an account type and has given no identifier, so the answer
    is `awaiting_identity` — `BR-CUS-1024`, *"Without identifier we cannot create
    Customer ID or master account ot regular account"*, which `OQ-MET-12472`
    settled on 2026-09-19 and which this change does not touch.

    **`BR-MET-151` clause 3 is still not crossed, and that is now asserted
    directly rather than implied by the refusal:** the owner table does not grow.
    No category is read off any name, because **no party record is created on
    this path at all**.
    """
    with tenant_ctx(brazos):
        before = cus.Account.objects.filter(kind="master").count()
        owners_before = models.PremisesOwner.objects.count()
        created = services.create_premises(
            dana,
            {
                "address_line": "8801 Reproduce Way",
                "owner_manager": "Ridge Property LLC",
                "owner_account_type": "residential",
            },
        )
        after = cus.Account.objects.filter(kind="master").count()
        owners_after = models.PremisesOwner.objects.count()
    assert created["owner_master_account"] is None
    assert after == before
    assert owners_after == owners_before, "no party may be invented (BR-MET-151 c3)"
    assert _reasons(created) == ["awaiting_identity"]


def test_br_met_1181__an_address_that_names_nobody_at_all_says_so(brazos, dana):
    """The absence `OWNER_ACCOUNT_OWNER_NOT_NAMED` now describes, kept in THIS
    file because this is where a lane looking for `no_typed_owner` will come.

    Nobody was named — no owner record and no free text. That is the one
    remaining case where there is no party to open an account FOR.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8802 Reproduce Way",
                "owner_kind": "person",
                "owner_ssn": "412558899",
                "owner_account_type": "residential",
            },
        )
    assert created["owner_master_account"] is None
    assert _reasons(created) == [services.OWNER_ACCOUNT_OWNER_NOT_NAMED]


# ── GATE 2 · NO ACCOUNT TYPE — the fact nothing may guess ───────────────────


#: `OQ-MET-12472` — an identified company, as the form now sends it. Named once
#: so a case about the ACCOUNT TYPE cannot accidentally also be a case about the
#: identity.
IDENTIFIED = {"owner_kind": "company", "owner_tax_id": "74-3182640"}


def test_def_met_5844__a_typed_owner_with_no_account_type_opens_nothing(brazos, dana):
    """The import's `OWNER_ACCOUNT_NO_ACCOUNT_TYPE`, one door along.

    `customers.create_master_account` refuses a missing account type by name and
    is right to: it is the consumer category the bill is priced and reported by.
    The premises' own `premises_type` is a PROPERTY type — deriving one from the
    other is a money-bearing default wearing a mapping's clothes.

    ⚠ **THE OWNER IS IDENTIFIED HERE AND THAT IS THE POINT OF THE CHANGE
    (`OQ-MET-12472`).** `owner_account_verdict` asks for an identifier BEFORE it
    asks for an account type, so a row missing both now reports
    `awaiting_identity` — the first thing a clerk has to go and find. This case
    is about the account type, so it supplies the identity and leaves only the
    type missing. **The order is the import's and is not chosen here**: the
    screen and the spreadsheet must name the same missing fact.
    """
    with tenant_ctx(brazos):
        before = cus.Account.objects.filter(kind="master").count()
        created = services.create_premises(
            dana,
            {"address_line": "8803 Reproduce Way", "owner_id": owner_for(dana), **IDENTIFIED},
        )
        after = cus.Account.objects.filter(kind="master").count()
    assert created["owner_master_account"] is None
    assert after == before
    assert _reasons(created) == [services.OWNER_ACCOUNT_NO_ACCOUNT_TYPE]


def test_def_met_5844__a_blank_account_type_is_the_same_as_an_absent_one(brazos, dana):
    """A form that sends `""` and a form that omits the key mean one thing.

    The wizard omits it, and this asserts the OTHER caller — the integrations
    seam, a hand-made request, a lane sending its whole form back — cannot get a
    different answer out of a blank string.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8805 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_account_type": "   ",
                **IDENTIFIED,
            },
        )
    assert _reasons(created) == [services.OWNER_ACCOUNT_NO_ACCOUNT_TYPE]


# ── THE DOOR IS WALKED THROUGH, AND ITS REFUSAL IS CARRIED ─────────────────


def test_def_met_5844__the_door_is_reached_and_its_own_refusal_is_reported(brazos, dana):
    """⚠ **THE TEST THAT WOULD HAVE CAUGHT THE DEFECT, AND IT IS NOT ABOUT AN
    ACCOUNT BEING CREATED.**

    Before `DEF-MET-5844` was fixed there was no call and therefore no answer —
    `warnings` was empty and the form was silent, which is the whole of what the
    PO reported. **So the assertion is that something was SAID.**

    ⛔ **WHAT IT SAYS CHANGED ON 2026-09-19 AND THE OLD TEXT IS KEPT HERE ON
    PURPOSE (`OQ-MET-12472`).** This case used to assert
    `customers.account.identity_kind_required` with `br_ref` `BR-CUS-1024` —
    the ACCOUNT DOOR refusing, at the far end of the seam, because
    `premises_owners` carried no kind and no identifier and the form had no
    boxes for them. The PO settled it: *"The Add Premises form must collect an
    identifier … and no account exists until they're supplied."* — **"this is
    correct"**.

    So the form asks, and a row that still declines is now stopped EARLIER and
    more cheaply — by `owner_account_verdict`, on this side of the seam, before
    a transaction is opened. That is not a weaker answer: it is the same rule
    named in the import's own words, and it is the answer the review step can
    show a clerk BEFORE they press Create rather than after.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8807 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_manager": "Whitfield Rentals LLC",
                "owner_account_type": "residential",
            },
        )
    assert created["owner_master_account"] is None
    # The IMPORT'S own verdict string, so a receipt and this screen read alike.
    assert _reasons(created) == ["awaiting_identity"]


def test_oq_met_12472__an_identified_owner_gets_the_account_and_the_link(brazos, dana):
    """⛔ **THE RULING, BUILT (PO 2026-09-19).** With a kind and one identifier
    the door opens, the account is created on THIS address, and
    `premises_owners.master_account_id` — the declared link `DEF-2902`/
    `DEF-2903` report missing from every master account in the product — is
    written.

    ⚠ **THE DELTA, NEVER THE PRESENCE.** `before`/`after` rather than *an
    account exists*: the beta holds an orphaned master account already, and a
    presence check passes on a property nobody touched (hard-won law 7).
    """
    with tenant_ctx(brazos):
        owner = owner_for(dana)
        before = cus.Account.objects.filter(kind="master").count()
        created = services.create_premises(
            dana,
            {
                "address_line": "8815 Reproduce Way",
                # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
                # building of two or more homes, so the address is added with two.
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "owner_id": owner,
                "owner_account_type": "commercial",
                **IDENTIFIED,
            },
        )
        after = cus.Account.objects.filter(kind="master").count()
        row = models.PremisesOwner.objects.get(pk=owner)
        account = cus.Account.objects.get(premises_id=created["id"])
    assert after - before == 1
    assert _account_id(created) == str(account.id)
    assert str(row.master_account_id) == str(account.id)
    # The warning says CREATED rather than declining, and says it exactly once.
    assert [w["code"] for w in created["warnings"]] == [services.OWNER_ACCOUNT_CREATED]
    assert _reasons(created) == []
    # `OQ-790`, closed 2026-08-27 and asserted rather than re-asked (law 13):
    # the number comes from the tenant's series and is never invented.
    assert account.account_no
    assert account.kind == "master"


def test_oq_met_12472__a_person_is_identified_by_any_one_of_three(brazos, dana):
    """PO 2026-09-01: *"DL, SSN, Phone or Tax ID"*. Any ONE of the three is
    enough for a person — a rule that holds for the first identifier and not the
    third is a rule that holds by accident."""
    for index, identity in enumerate(
        (
            {"owner_kind": "person", "owner_ssn": "123-45-6789"},
            {"owner_kind": "person", "owner_driving_licence": "TX-99481"},
            {"owner_kind": "person", "owner_phone": "555-0142"},
        )
    ):
        with tenant_ctx(brazos):
            created = services.create_premises(
                dana,
                {
                    "address_line": f"882{index} Reproduce Way",
                    # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
                    # building of two or more homes, so the address is added with two.
                    "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                    "owner_id": owner_for(dana),
                    "owner_account_type": "residential",
                    **identity,
                },
            )
        assert _account_id(created) is not None, identity


def test_oq_met_12472__a_companys_phone_is_refused_as_the_other_kinds(brazos, dana):
    """⛔ **`BR-CUS-1022`, AND THE SCREEN MAKES THIS UNREACHABLE — THE SERVER
    STILL REFUSES IT.** A phone filed under a company is stored where the
    company matcher never looks, so `owner_account_verdict` names the fault
    rather than silently dropping the cell. The form draws no phone box once
    Company is picked, which is where the guarantee is comfortable; this is
    where it is ENFORCED, for the seam, a hand-made request and any caller that
    is not the form.
    """
    with tenant_ctx(brazos):
        before = cus.Account.objects.filter(kind="master").count()
        created = services.create_premises(
            dana,
            {
                "address_line": "8831 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_account_type": "commercial",
                "owner_kind": "company",
                "owner_phone": "555-0142",
            },
        )
        after = cus.Account.objects.filter(kind="master").count()
    assert after == before
    assert _reasons(created) == ["identity_mismatch"]
    mismatch = created["warnings"][0]
    assert mismatch["identity_reason"] == "identifier_belongs_to_the_other_kind"
    assert mismatch["borrowed"] == ["owner_phone"]


def test_oq_met_12472__an_identifier_with_no_kind_cannot_be_judged(brazos, dana):
    """`BR-CUS-1022` again, from the other side. Evidence presented against an
    unstated kind cannot be assessed at all, and defaulting to `person` would
    judge a developer by a Social Security number it has not got."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8833 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_account_type": "residential",
                "owner_ssn": "123-45-6789",
            },
        )
    assert _reasons(created) == ["identity_mismatch"]
    assert created["warnings"][0]["identity_reason"] == "kind_not_stated"


def test_def_met_5847__the_owners_own_contact_details_reach_the_account_door(brazos, dana):
    """⛔ **`DEF-MET-5847` — THE BLOCKAGE NOBODY WAS LOOKING AT, AND IT WAS NOT
    THE IDENTITY GATE.** Measured on `brazosbend`, real PostgreSQL, 2026-09-19: an owner
    picked from the list with `Managed by` left empty answered
    `customers.contact.name_required`.

    `create_master_account` falls back to the premises' own free-text
    `owner_manager` when no contact block arrives, and after `CR-089` `p008`
    split the picker from `Managed by` that box is ordinarily EMPTY — so the
    door refused every owner picked properly, and only a clerk who ALSO retyped
    the name into the free-text box got past it.

    ⚠ **THIS ASSERTS THE OUTCOME AND NOT THE CALL.** With no `owner_manager` at
    all the account must open, which it can only do if the owner row's own name
    travelled. A mock-the-door test would pass on a contact block containing the
    wrong key — `{"name": …}` is refused as `customers.account.unknown_field`,
    which is a mistake this lane made once before reading `_validate_contact`.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8835 Reproduce Way",
                # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
                # building of two or more homes, so the address is added with two.
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "owner_id": owner_for(dana),
                "owner_account_type": "commercial",
                **IDENTIFIED,
            },
        )
        assert not (created.get("owner_manager") or "")
    assert _account_id(created) is not None, created["warnings"]


def test_def_met_5844__a_refused_account_leaves_the_address_standing(brazos, dana):
    """PO 2026-08-27 — an address is a real address whether or not anybody can be
    billed for it. The refusal above must not cost the property.

    ⚠ **THIS PASSES WITHOUT THE SAVEPOINT ON SQLITE.** See the module docstring:
    the guarantee is PostgreSQL's and is proved there. This case asserts the
    OUTCOME (the row survives and is readable) so that a regression in the
    catch — swallowing the wrong thing, or re-raising — goes red here.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8809 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_manager": "Whitfield Rentals LLC",
                "owner_account_type": "residential",
            },
        )
        row = models.Premises.objects.get(pk=created["id"])
    assert row.address_line == "8809 Reproduce Way"
    assert row.premise_no
    assert created["owner_master_account"] is None


# ── SAVED TWICE — the claim nobody ever walks ──────────────────────────────


def test_def_met_5844__saving_twice_opens_no_second_account(brazos, dana):
    """`ensure_owner_master_account` is *ensure*, not *create a second one*, and
    `BR-CUS-1011` — one owner account per address — would refuse the second
    anyway. A clerk who double-presses Create makes two ADDRESSES (two distinct
    street numbers here, because that is what two saves of a form are) and must
    never make two owner accounts.
    """
    with tenant_ctx(brazos):
        owner = owner_for(dana)
        before = cus.Account.objects.filter(kind="master").count()
        first = services.create_premises(
            dana,
            {
                "address_line": "8811 Reproduce Way",
                # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
                # building of two or more homes, so the address is added with two.
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "owner_id": owner,
                "owner_account_type": "residential",
                **IDENTIFIED,
            },
        )
        second = services.create_premises(
            dana,
            {
                "address_line": "8811 Reproduce Way",
                # `BR-CUS-1114` (PO 2026-10-02) — an owner's master account needs a
                # building of two or more homes, so the address is added with two.
                "units": [{"label": "Unit 1"}, {"label": "Unit 2"}],
                "owner_id": owner,
                "owner_account_type": "residential",
                **IDENTIFIED,
            },
        )
        after = cus.Account.objects.filter(kind="master").count()
    # ⛔ **THIS CASE COULD NOT PROVE ANYTHING UNTIL `OQ-MET-12472` CLOSED, AND
    # THE PREVIOUS LANE SAID SO RATHER THAN CLAIMING IT.** With no identity the
    # door refused both times, so `after - before` was 0 and
    # `first == second` was `None == None` — a check that passes wrongly
    # (CLAUDE.md hard-won law 7) over a feature that did not exist.
    #
    # ⚠ **SO THE FIRST ASSERTION IS THAT ONE WAS ACTUALLY MADE.** Without it
    # `<= 1` is satisfied by zero and the whole case goes hollow again the next
    # time something upstream declines.
    assert after - before == 1, "the first save did not open an owner account at all"
    assert _account_id(first) is not None
    assert _account_id(first) == _account_id(second)
    assert any(
        warning.get("code") == services.OWNER_ACCOUNT_ALREADY_LINKED
        for warning in second["warnings"]
    ), second["warnings"]


# ── THE KEY IS NOT A PREMISES COLUMN ───────────────────────────────────────


def test_def_met_5844__the_account_type_is_not_written_onto_the_premises(brazos, dana):
    """It is a fact about the owner's ACCOUNT, not about the address.

    `_validate_premises` tolerates the key without returning it, exactly as it
    tolerates `units`, `unit`, `auto_create_unit` and `route`. A key that reached
    `known` would try to write a column that does not exist; a key that reached
    neither would answer `metering.unknown_field` and refuse the whole save,
    which is how `DEF-517` reached a clerk.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {
                "address_line": "8813 Reproduce Way",
                "owner_id": owner_for(dana),
                "owner_account_type": "commercial",
            },
        )
        row = models.Premises.objects.get(pk=created["id"])
    assert not hasattr(row, "owner_account_type")
    assert created["address_line"] == "8813 Reproduce Way"

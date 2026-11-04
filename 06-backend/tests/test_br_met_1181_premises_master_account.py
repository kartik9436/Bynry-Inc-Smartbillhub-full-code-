# ── Trace ──────────────────────────────────────────────
# Defect:  DEF-MET-6139 — the Add Premises form collects an owner's name, kind,
#          identifier and account type and opens no master account, because the
#          code required an owner RECORD first.
# Change:  CR-130-BRC07 §9 part three, lane C1
# Rules:   BR-MET-1181 (a premises names its master account directly, and the
#          ruled precedence) · BR-MET-400 (declared, never inferred — narrowed
#          in its chain, not weakened) · BR-MET-1010 · BR-MET-112 (nothing is
#          written until the last button) · BR-MET-151 clause 3 (never read a
#          category off a name) · BR-CUS-1010 · BR-CUS-1011 · B14 rule 31 (no
#          database id is ever the visible value of a field)
# Question: OQ-790 (CLOSED 2026-08-27, option (c) — this is its mechanism,
#          finally built) · OQ-MET-12573 (should a party's SECOND address find
#          the first one's account? OPEN, and nothing here guesses)
# Screens: S14 premises list · S16 guided add · PRM-01 edit modal
# ───────────────────────────────────────────────────────
"""A premises names its master account directly — the precedence, and the door.

⛔ **PROVED RED FIRST, IN THE HARNESS THAT RUNS IT (hard-won law 7).** Every
case below was run against `apps/metering/services.py` as it stood at
`7ef0b53f1` — the tip this lane started from — before a line of the fix existed.
The failures are quoted on each case that has a distinctive one.

⚠ **AND THE ORIGINAL WAS REPRODUCED ON REAL POSTGRESQL BEFORE ANY OF THIS WAS
WRITTEN**, which is what `22-product-maintenance-process.md` step 1 asks for and
what no gate can ask for. On a clone of the `brazosbend` beta, 2026-09-22:

    name + kind + SSN + account type  -> masters 1->1  account on the address []
                                         warnings ['no_typed_owner']
    the same, for a company + Tax ID  -> masters 1->1  warnings ['no_typed_owner']
    0 of 79 properties had an owner account the money path could find

`10-scripts/br_met_1181_premises_master_account_readback.py` is that script, and
it is the one that proves the two things this file structurally CANNOT:

  1. **The savepoint (CLAUDE.md hard-won law 14).** `config/settings/test.py`
     hardcodes in-memory SQLite, which has **no aborted-transaction state**, so
     the version WITHOUT the nested `transaction.atomic()` passes this whole
     file and destroys a real save. Nothing here is proof of it.
  2. **That the column reaches a real database.** A migration that applies on
     SQLite is not a migration that applied on PostgreSQL 16.
"""

import json
import pathlib

import pytest

from apps.customers import models as cus
from apps.metering import models, premises_owners, selectors, services

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_unit, owner_for, tenant_ctx

#: `BR-CUS-1114` (PO 2026-10-02) — an owner's master account is raised only on
#: a building of two or more homes, so every address this file saves with an
#: owner is saved with two. The single-home refusal is tested by name in
#: `tests/test_br_cus_1114_master_only_multi_unit.py`.
TWO_HOMES = [{"label": "Unit 1"}, {"label": "Unit 2"}]

pytestmark = pytest.mark.django_db

REPO = pathlib.Path(__file__).resolve().parents[2]

#: The form's own answers for an identified person, as `AddPremisesWizard`
#: sends them. Named once so a case about the ACCOUNT cannot accidentally also
#: be a case about the identity.
IDENTIFIED_PERSON = {
    "owner_kind": "person",
    "owner_ssn": "412558899",
    "owner_account_type": "residential",
}
IDENTIFIED_COMPANY = {
    "owner_kind": "company",
    "owner_tax_id": "74-3182640",
    "owner_account_type": "commercial",
}


def _warnings(created, code=None):
    return [
        warning
        for warning in created["warnings"]
        if code is None or warning.get("code") == code
    ]


def _reasons(created):
    return [
        warning.get("reason")
        for warning in created["warnings"]
        if warning.get("code") == services.OWNER_ACCOUNT_NOT_CREATED
    ]


# ── 1 · THE REPRODUCTION, AS THE REPORTER SAW IT ───────────────────────────


def test_br_met_1181__a_named_identified_owner_opens_an_account_with_no_owner_record(
    brazos, dana
):
    """⛔ **THE DEFECT, AND THE ONE CASE THAT COULD NOT HAVE PASSED BEFORE.**

    A clerk types a name, picks *person*, gives a Social Security number and
    chooses an account type. **No owner record exists and none is created** —
    `createPremisesOwner` is called by no screen, which is why the old gate could
    never be satisfied from the product at all.

    RED at `7ef0b53f1`::

        assert 0 == 1
         +  where 0 = <the master accounts created>
        assert ['no_typed_owner'] == []

    ⚠ **THE ASSERTION THAT NO PARTY RECORD APPEARS IS NOT DECORATION.**
    `BR-MET-151` clause 3 forbids reading a party's category off a name, and the
    cheapest way to "fix" this defect wrongly is to invent a `premises_owners`
    row with a guessed category. Counting the table before and after is what
    makes that impossible to do quietly.
    """
    with tenant_ctx(brazos):
        owners_before = models.PremisesOwner.objects.count()
        masters_before = cus.Account.objects.filter(kind="master").count()
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9601 Reproduction Row",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        masters_after = cus.Account.objects.filter(kind="master").count()
        owners_after = models.PremisesOwner.objects.count()
        row = models.Premises.objects.get(pk=created["id"])

    assert masters_after == masters_before + 1
    assert owners_after == owners_before, "no party record may be invented (BR-MET-151 c3)"
    assert row.master_account_id is not None
    assert str(row.master_account_id) == created["master_account_id"]
    assert created["master_account_source"] == "premises"
    # B14 rule 31 — the NUMBER a clerk reads, beside the id a machine uses.
    assert created["master_account_no"]
    assert _reasons(created) == []
    assert _warnings(created, services.OWNER_ACCOUNT_CREATED)


def test_br_met_1181__a_company_with_a_tax_id_opens_one_too(brazos, dana):
    """The other half of the reproduction. A company's evidence is a Tax ID and
    nothing else, and the verdict is the import's own — one definition of
    *enough* for the spreadsheet and the screen."""
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9603 Reproduction Row",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
    assert created["master_account_id"]
    assert created["master_account_source"] == "premises"


def test_br_met_1181__saving_the_same_address_twice_opens_one_account(brazos, dana):
    """`ensure` means what it says. `BR-CUS-1011` — one owner account per
    address — would refuse the second anyway; this asserts the door hands the
    first one back rather than meeting that refusal."""
    with tenant_ctx(brazos):
        payload = {
            "address_line": "9605 Reproduction Row",
            "owner_manager": "Harriet Vane",
            **IDENTIFIED_PERSON,
        }
        first = services.create_premises(dana, {**payload, "units": TWO_HOMES})
        masters = cus.Account.objects.filter(kind="master").count()
        again = services.update_premises(dana, first["id"], dict(payload))
        after = cus.Account.objects.filter(kind="master").count()

    assert after == masters
    assert again["master_account_id"] == first["master_account_id"]
    assert [w["code"] for w in _warnings(again)] == [
        services.OWNER_ACCOUNT_ALREADY_LINKED
    ]


# ── 2 · THE PRECEDENCE, RULED 2026-09-22 ───────────────────────────────────


def test_br_met_1181__the_premises_declaration_wins_over_the_owner_record(brazos, dana):
    """⛔ **THE RULED ORDER, AND THE REASON IT IS RULED AT ALL.** Two columns can
    answer *who is the master account for this address*. If they disagree, one
    of them is who gets billed — so the order is declared in the decision log
    and asserted here rather than left to the reading order of a function.

    The owner record is pointed at a DIFFERENT account, and the premises' own
    declaration still wins.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9607 Reproduction Row",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        declared = created["master_account_id"]
        other = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9609 Reproduction Row",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )["master_account_id"]

        # A pre-ruling owner record, pointed at the OTHER account.
        owner_id = owner_for(dana, "Harriet Vane Holdings")
        models.PremisesOwner.objects.filter(pk=owner_id).update(master_account_id=other)
        models.Premises.objects.filter(pk=created["id"]).update(owner_id=owner_id)

        answer = premises_owners.owner_master_account_for_premises(created["id"])
        account_id, source = premises_owners.premises_master_account_link(created["id"])

    assert str(answer) == declared != other
    assert source == "premises"
    assert str(account_id) == declared


def test_br_met_1181__the_owner_record_answers_for_a_row_that_predates_the_ruling(
    brazos, dana
):
    """Precedence 2. Nothing is backfilled, so a premises written before
    2026-09-22 declares nothing of its own — and the link it DOES have must go
    on answering, or every pre-ruling address silently loses its owner.

    RED at `7ef0b53f1` on the `master_account_source` assertion only: the value
    did not exist.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9611 Reproduction Row",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
        account_id = created["master_account_id"]
        owner_id = owner_for(dana, "Ridge Property Holdings")
        models.PremisesOwner.objects.filter(pk=owner_id).update(master_account_id=account_id)
        # The pre-ruling shape: the OWNER declares, the premises does not.
        models.Premises.objects.filter(pk=created["id"]).update(
            owner_id=owner_id, master_account_id=None
        )
        answer, source = premises_owners.premises_master_account_link(created["id"])
        row = selectors.premises_detail_dict(models.Premises.objects.get(pk=created["id"]))

    assert str(answer) == account_id
    assert source == "owner_record"
    assert row["master_account_source"] == "owner_record"
    assert row["master_account_id"] == account_id


def test_br_met_1181__an_account_that_merely_covers_the_premises_never_answers(
    brazos, dana
):
    """⛔ **PRECEDENCE 3 IS NEVER PROMOTED, AND THIS IS THE CASE THAT HOLDS IT.**

    `accounts.premises_id` says *which premises this account covers*. **Both
    master AND regular accounts carry it**, so promoting it would make every
    tenant at an address a candidate owner of it — and the owner is who a
    `BR-MET-105` empty-unit base charge and a move-out shortfall are POSTED TO.

    Here a `kind='master'` account names the premises through that column and
    NEITHER declaration does. The answer must still be `None`.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9613 Reproduction Row",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
        # Take BOTH declarations away and leave `accounts.premises_id` standing.
        models.Premises.objects.filter(pk=created["id"]).update(master_account_id=None)
        assert cus.Account.objects.filter(
            premises_id=created["id"], kind="master"
        ).exists(), "the fixture must leave the third column set, or it proves nothing"

        answer, source = premises_owners.premises_master_account_link(created["id"])

    assert answer is None
    assert source is None


def test_br_met_1181__the_reverse_reading_finds_both_shapes_once_each(brazos, dana):
    """`premises_ids_owned_by_account`, the inverse, over BOTH declarations.

    ⚠ **THE `distinct()` IS LOAD-BEARING AND THIS IS WHERE IT IS ASSERTED.** A
    premises that names the account AND whose owner record names the same
    account matches both halves of the OR; a duplicated id double-counts a
    building in the sub-account list and in the move-out shortfall.
    """
    with tenant_ctx(brazos):
        first = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9615 Reproduction Row",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        account_id = first["master_account_id"]

        # A second address whose OWNER RECORD names the same account, and whose
        # own column does not — the pre-ruling shape.
        second = services.create_premises(
            dana,
            {"units": TWO_HOMES, "address_line": "9617 Reproduction Row", "owner_manager": "Harriet Vane"},
        )
        owner_id = owner_for(dana, "Vane Estates")
        models.PremisesOwner.objects.filter(pk=owner_id).update(master_account_id=account_id)
        models.Premises.objects.filter(pk=second["id"]).update(owner_id=owner_id)
        # And the FIRST one declares it twice over — both columns, one account.
        models.Premises.objects.filter(pk=first["id"]).update(owner_id=owner_id)

        owned = premises_owners.premises_ids_owned_by_account(account_id)

    assert sorted(owned) == sorted({first["id"], second["id"]})
    assert len(owned) == len(set(owned)), "a premises counted twice double-bills it"


# ── 3 · WHAT A CLERK IS TOLD ───────────────────────────────────────────────


def test_br_met_1181__an_address_with_nobody_named_says_so(brazos, dana):
    """The one absence left. **The condition is no longer *no typed owner* —
    there is no typed owner in the chain — it is that nobody was named at all.**

    RED at `7ef0b53f1`: `assert 'no_typed_owner' == 'owner_not_named'`.
    """
    with tenant_ctx(brazos):
        before = cus.Account.objects.filter(kind="master").count()
        created = services.create_premises(
            dana, {"units": TWO_HOMES, "address_line": "9619 Reproduction Row", **IDENTIFIED_PERSON}
        )
        after = cus.Account.objects.filter(kind="master").count()

    assert after == before
    assert _reasons(created) == [services.OWNER_ACCOUNT_OWNER_NOT_NAMED]
    assert created["master_account_id"] is None


@pytest.mark.parametrize(
    "extra,expected",
    [
        ({}, "awaiting_identity"),
        ({"owner_ssn": "412558899"}, "identity_mismatch"),
        ({"owner_kind": "person", "owner_tax_id": "74-3182640"}, "identity_mismatch"),
        ({"owner_kind": "person", "owner_ssn": "412558899"}, "no_account_type"),
    ],
)
def test_br_met_1181__every_verdict_reaches_the_screen_with_its_own_sentence(
    brazos, dana, extra, expected
):
    """⛔ **THE HALF OF THE DEFECT THAT IS NOT ABOUT AN ACCOUNT BEING OPENED.**

    The server has computed five distinct answers since `DEF-MET-5844` and **a
    whole-front-end grep found zero occurrences of any of them outside the
    import receipt** — the wizard fired one toast, *"Premise created"*, and threw
    the array away. So the assertion is that each outcome carries a SENTENCE, and
    that the sentence resolves.

    RED at `7ef0b53f1`: `assert None` — no warning carried a `message_key` at
    all, on any branch.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": f"96{len(extra)}1 Verdict Way",
                "owner_manager": "Harriet Vane",
                **extra,
            },
        )
    assert _reasons(created) == [expected]
    warning = _warnings(created, services.OWNER_ACCOUNT_NOT_CREATED)[0]
    assert warning["message_key"], "an outcome nothing can render is an outcome nobody sees"


def test_br_met_1181__every_message_key_this_door_raises_resolves(brazos):
    """G32's question, asked here as well as there — and it is not a duplicate.

    G32 walks the WHOLE backend and is a ratchet; this asserts the one map, so a
    lane adding a sixth outcome to `OWNER_ACCOUNT_MESSAGE_KEYS` and forgetting
    its sentence is told by the file it is editing rather than by a merge.

    ⚠ **IT READS `en.json` AND NOT A LIST WRITTEN HERE.** A test that restated
    the nine keys would pass over a catalogue that never got them, which is the
    check-that-cannot-fail shape (law 7).
    """
    catalogue = json.loads(
        (REPO / "07-frontend/src/i18n/locales/en.json").read_text(encoding="utf-8")
    )
    missing = [
        key
        for key in sorted(set(services.OWNER_ACCOUNT_MESSAGE_KEYS.values()))
        if key not in catalogue
    ]
    assert missing == []
    assert "metering.premises.master_account_unknown" in catalogue
    # `refused` carries the refusing door's OWN key and must never gain one here.
    assert services.OWNER_ACCOUNT_REFUSED not in services.OWNER_ACCOUNT_MESSAGE_KEYS


# ── 4 · NAMING AN ACCOUNT THAT ALREADY EXISTS ──────────────────────────────


def test_br_met_1181__an_existing_master_account_can_be_attached_on_edit(brazos, dana):
    """⛔ **THE REPORTER'S OWN SENTENCE:** *"we are unabel to find and map master
    account to premises LATER"*. `BR-MET-400` has said since 2026-08-27 that the
    account *"can be existing master account also"* and until today no door
    accepted one.

    RED at `7ef0b53f1`: `metering.unknown_field` on `master_account_id`.
    """
    with tenant_ctx(brazos):
        holder = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9621 Attach Way",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
        account_id = holder["master_account_id"]
        plain = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9623 Attach Way"})
        masters = cus.Account.objects.filter(kind="master").count()

        attached = services.update_premises(
            dana, plain["id"], {"master_account_id": account_id}
        )
        after = cus.Account.objects.filter(kind="master").count()

    assert after == masters, "attaching opens nothing"
    assert attached["master_account_id"] == account_id
    assert attached["master_account_source"] == "premises"
    assert [w["code"] for w in _warnings(attached)] == [services.OWNER_ACCOUNT_ATTACHED]
    assert _warnings(attached)[0]["account_no"], "B14 rule 31 — the number, not the id"


def test_br_met_1181__an_ordinary_account_is_refused_by_name(brazos, dana):
    """⛔ **PRECEDENCE 3, REFUSED AT THE DOOR RATHER THAN IN A READ.** An
    ordinary account at an address belongs to a TENANT. Declaring one as the
    owner would post the landlord's empty-unit charges to the tenant.
    """
    with tenant_ctx(brazos):
        # The ordinary account is BUILT HERE rather than taken from the fixture,
        # and the reason is worth a line: this suite's tenant has none, so a
        # `first()` over `exclude(kind="master")` answers `None` and the case
        # passes its own setup while asserting nothing (law 7 — *ask what would
        # make this check pass wrongly*). It was written that way first and the
        # red run said `the fixture needs a non-master account`.
        holder = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9624 Attach Way",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
        master = cus.Account.objects.get(pk=holder["master_account_id"])
        # ⚠ **IT NEEDS A UNIT, AND THE DATABASE SAYS SO** —
        # `ck_accounts_regular_has_unit`. That constraint is itself the reason
        # this case matters: an ordinary account is a TENANT's, it hangs off a
        # flat, and declaring one as the owner of the building would post the
        # landlord's charges to whoever lives in that flat.
        unit = make_unit(dana, holder["id"])
        ordinary = cus.Account.objects.create(
            tenant_id=master.tenant_id,
            premises_id=master.premises_id,
            unit_id=unit["id"],
            account_no=f"{master.account_no}-T",
            status=master.status,
            account_type=master.account_type,
            kind="regular",
            currency=master.currency,
            opened_at=master.opened_at,
        )
        premises = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9625 Attach Way"})
        answer = services.update_premises(
            dana, premises["id"], {"master_account_id": str(ordinary.id)}
        )

    assert answer["master_account_id"] is None
    warning = _warnings(answer)[0]
    assert warning["message_key"] == "metering.premises.master_account_unknown"
    assert warning["br_ref"] == "BR-MET-1181"
    assert warning["named_account_id"] == str(ordinary.id)


def test_br_met_1181__an_account_this_tenant_does_not_hold_is_refused_too(brazos, dana):
    """The other half of the same door: an id that resolves to nothing.

    404-never-403 is the product's posture for every cross-tenant read, so a
    clerk who pastes another utility's account id is told the same thing as one
    who pastes nonsense — and **the address is still saved**, which is the
    2026-08-27 ruling that an address is a real address whether or not anybody
    can be billed for it.
    """
    with tenant_ctx(brazos):
        premises = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9626 Attach Way"})
        answer = services.update_premises(
            dana,
            premises["id"],
            {"master_account_id": "01a0c7f5-0000-7000-8000-000000000000"},
        )

    assert answer["master_account_id"] is None
    assert _warnings(answer)[0]["message_key"] == "metering.premises.master_account_unknown"
    assert models.Premises.objects.filter(pk=premises["id"]).exists()


def test_br_met_1181__an_explicit_null_takes_the_declaration_back(brazos, dana):
    """`{"master_account_id": null}` is a clerk withdrawing a claim, and it is a
    DIFFERENT fact from saying nothing — which is why the door reads the KEY and
    not the value. **Reading the value would open a NEW account** for an address
    whose owner a clerk had just said they were unsure about.

    The ACCOUNT is untouched; what is withdrawn is a metering row's claim.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9627 Attach Way",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        account_id = created["master_account_id"]
        cleared = services.update_premises(dana, created["id"], {"master_account_id": None})

    assert cleared["master_account_id"] is None
    assert cus.Account.objects.filter(pk=account_id).exists(), "the account is not deleted"


def test_br_met_1181__an_edit_that_says_nothing_about_the_owner_says_nothing(
    brazos, dana
):
    """⚠ **THE CASE THAT KEEPS THIS OFF EVERY OTHER EDIT IN THE PRODUCT.**
    A clerk correcting a postal code must not be handed a warning about an owner
    they never mentioned. Absent is this API's documented *leave it alone*.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana, {"units": TWO_HOMES, "address_line": "9629 Attach Way", "owner_manager": "Harriet Vane"}
        )
        edited = services.update_premises(dana, created["id"], {"postal_code": "77494"})

    assert edited["warnings"] == []
    assert edited["owner_master_account"] is None


# ── 5 · THE SEAM, AND WHAT RIDES FREE ──────────────────────────────────────


def test_br_met_1181__the_money_path_still_joins_through_two_seam_functions(brazos):
    """⛔ **THE STRUCTURAL CLAIM THIS WHOLE CHANGE RESTS ON, ASSERTED RATHER THAN
    BELIEVED** (hard-won law 1 — a comment claiming a guarantee is not the
    guarantee).

    The decision log says the empty-unit base charge, the move-out shortfall, the
    sub-account list and the account header all follow from two functions with
    **four call sites in the entire backend**. If a fifth appears without anyone
    noticing, a consumer has started reading the chain some other way — which is
    exactly how `BR-CUS-171`'s geometric derivation came to disagree with the
    declared owner.

    Counting SOURCE is this check's declared limit: a call assembled at run time
    is invisible to it, and so is one written in a module this glob does not
    reach.

    ⚠ **A CALL SITE IS NAMED BY ITS FILE AND ITS ENCLOSING FUNCTION, NOT BY ITS
    LINE NUMBER (re-keyed 2026-10-02).** This set held `selectors.py:884`-style
    line numbers, so ANY insertion above them turned it red with no new consumer
    at all — `fcf871c99` (2026-09-23 13:42, 34 lines at line 647) did exactly
    that, and from then on the red said nothing about the claim it guards. The
    function is what a reviewer needs to judge a new consumer, and it does not
    move when a sibling adds code above it.

    ⚠ **AND THE FIFTH SITE IS A KNOWN ONE, NOT A LEAK.** `f40a857b8`
    (2026-09-23, `BR-CUS-1094` — *a master account shows every unit at its
    address and who each unit's bill goes to*) added `_master_premises_ids`,
    which reads ownership through `seams.premises_ids_owned_by_account` — the
    seam this test exists to keep everyone on — and whose docstring says it
    keeps *"the SAME order as `sub_accounts_for_master` and
    `premises_scope_for_account`, deliberately"*. It is enrolled here by name; a
    sixth still goes red.
    """
    import ast

    call_sites = set()
    for path in sorted((REPO / "06-backend" / "apps").rglob("*.py")):
        if "/tests/" in str(path) or "premises_owners.py" in path.name:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if (
            "seams.owner_master_account_for_premises(" not in text
            and "seams.premises_ids_owned_by_account(" not in text
        ):
            continue
        functions = [
            node
            for node in ast.walk(ast.parse(text))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        for number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if (
                "seams.owner_master_account_for_premises(" in line
                or "seams.premises_ids_owned_by_account(" in line
            ):
                enclosing = [
                    fn for fn in functions if fn.lineno <= number <= (fn.end_lineno or fn.lineno)
                ]
                # the INNERMOST function: the one that starts last
                name = max(enclosing, key=lambda fn: fn.lineno).name if enclosing else "<module>"
                call_sites.add(f"{path.relative_to(REPO)}::{name}")
    assert call_sites == {
        "06-backend/apps/customers/move_out_settlement.py::owner_target_for",
        "06-backend/apps/customers/selectors.py::master_account_for",
        "06-backend/apps/customers/selectors.py::premises_scope_for_account",
        "06-backend/apps/customers/selectors.py::sub_accounts_for_master",
        "06-backend/apps/customers/selectors.py::_master_premises_ids",
    }, sorted(call_sites)


def test_br_met_1181__the_list_prints_the_number_and_does_not_expand_the_account(
    brazos, dana
):
    """`DEF-324`'s discipline, kept — and B14 rule 31 satisfied anyway.

    The LIST may not expand an account (one account read plus one ledger
    derivation per row), and it may not draw the id it holds. So the page's ids
    are asked ONCE, as numbers only.

    ⚠ **THE ASSERTION THAT `master_account` IS STILL `None` IS THE HALF THAT
    PROTECTS THE MEASUREMENT.** A lane that "helpfully" expanded it would make
    this file green on the number and re-buy `DEF-324` in the same commit.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9631 Listing Way",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        rows = list(selectors.premises_list().filter(pk=created["id"]))
        numbers = selectors.premises_master_account_numbers(rows)
        served = selectors.premises_detail_dict(
            rows[0], with_owner_account=False, master_account_numbers=numbers
        )

    assert served["master_account_id"] == created["master_account_id"]
    assert served["master_account_no"] == created["master_account_no"]
    assert served["master_account"] is None
    assert served["master_account_expanded"] is False


def test_br_met_1181__the_detail_says_how_many_OTHER_properties_the_account_owns(
    brazos, dana
):
    """⛔ **THE BLUEPRINT DRAWS *Already owns N other properties* AND NO SERVER
    FACT FED IT** — the screens read `owner.premises_count`, which counts the
    addresses pointing at the OWNER RECORD, and the owner record is out of the
    chain under this ruling. On an address with no owner record that line would
    have read zero for ever with every test green, which is `DEF-CUS-3653`
    exactly.

    **OTHER properties, so this one is not counted.** *"Already owns 1 other
    property"* on a building's own page, counting that building, is a sentence
    that sends a clerk looking for an address that does not exist.
    """
    with tenant_ctx(brazos):
        first = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9639 Listing Way",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        account_id = first["master_account_id"]
        second = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9641 Listing Way"})
        third = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9643 Listing Way"})
        for other in (second, third):
            services.update_premises(dana, other["id"], {"master_account_id": account_id})

        served = selectors.premises_detail_dict(
            models.Premises.objects.get(pk=first["id"])
        )
        from_a_sibling = selectors.premises_detail_dict(
            models.Premises.objects.get(pk=second["id"])
        )

    assert served["master_account"]["owns_premises_count"] == 2
    assert from_a_sibling["master_account"]["owns_premises_count"] == 2


def test_br_met_1181__a_list_row_is_not_told_how_many_properties(brazos, dana):
    """The other half, and it is the half that protects the measurement: the
    count is ONE MORE STATEMENT per call, which is exactly what a list may not
    spend (`DEF-324`). A list row carries no expansion at all, so there is
    nothing to count it on — and `master_account_expanded: false` says nobody
    asked, rather than leaving a zero that reads like an answer.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9645 Listing Way",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        rows = list(selectors.premises_list().filter(pk=created["id"]))
        served = selectors.premises_detail_dict(
            rows[0],
            with_owner_account=False,
            master_account_numbers=selectors.premises_master_account_numbers(rows),
        )

    assert served["master_account"] is None
    assert served["master_account_expanded"] is False
    assert served["master_account_no"]


def test_br_met_1181__an_export_row_asks_for_no_account_at_all(brazos, dana):
    """⚠ **THE EXPORT HAS NO PAGE TO BATCH OVER, SO IT GETS `None` RATHER THAN A
    PER-ROW QUERY.** `exports.PREMISES` serialises every premises the tenant has,
    one row at a time; a per-row fallback would put one statement per property
    into a file that runs over the whole register — `DEF-324` re-created in the
    one place `NFR-3` cares about most. An opt-in batch is the only shape that
    cannot be reached by accident, and this is what pins it.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9633 Listing Way",
                "owner_manager": "Harriet Vane",
                **IDENTIFIED_PERSON,
            },
        )
        row = models.Premises.objects.get(pk=created["id"])
        served = selectors.premises_detail_dict(row, with_owner_account=False)

    assert served["master_account_id"] == created["master_account_id"]
    assert served["master_account_no"] is None
    assert served["master_account_expanded"] is False


def test_br_met_1181__the_two_readings_of_the_precedence_agree(brazos, dana):
    """⛔ **TWO IMPLEMENTATIONS OF ONE ORDER EXIST AND THIS IS WHY THAT IS SAFE.**

    `premises_master_account_link` takes an id and issues a query; a list holding
    200 rows must not issue 200 of them, so `premises_master_account_from_row`
    reads a row already in memory. **If they ever disagree, the money path is
    right and the serialiser is wrong** — and nothing but this case would say so.
    """
    with tenant_ctx(brazos):
        created = services.create_premises(
            dana,
            {"units": TWO_HOMES, 
                "address_line": "9635 Listing Way",
                "owner_manager": "Ridge Property LLC",
                **IDENTIFIED_COMPANY,
            },
        )
        bare = services.create_premises(dana, {"units": TWO_HOMES, "address_line": "9637 Listing Way"})
        for premises_id in (created["id"], bare["id"]):
            row = models.Premises.objects.get(pk=premises_id)
            by_query = premises_owners.premises_master_account_link(premises_id)
            by_row = selectors.premises_master_account_from_row(row)
            assert (str(by_query[0] or ""), by_query[1]) == (
                str(by_row[0] or ""),
                by_row[1],
            ), premises_id


# ── 6 · THE COLUMN ITSELF ──────────────────────────────────────────────────


def test_br_met_1181__the_column_is_nullable_and_protects_its_account(brazos):
    """The two properties the migration's docstring claims, asserted against the
    MODEL rather than against the migration's prose (hard-won law 1).

    PROTECT and not CASCADE: an account twelve addresses are billed through must
    refuse deletion and say so, never silently un-own twelve buildings.
    """
    field = models.Premises._meta.get_field("master_account")
    assert field.null is True
    assert field.db_column == "master_account_id"
    assert field.remote_field.on_delete.__name__ == "PROTECT"
    assert field.related_model._meta.label == "customers.Account"

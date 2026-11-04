# ── Trace ──────────────────────────────────────────────
# Change:  CR-058 tasks 10–13 — the premises import learns who the owner is.
#          ALSO CLOSES **CR-056 task 24** (*"Premises import creates the Master
#          Account — ruled once, never built"*), which is the missing CALLER
#          `apps/metering/premises_owners.py` names in its own docstring.
# Ruling:  PO 2026-09-01, verbatim: *"If owner name is given and one identify
#          given - DL, SSN, Phone or Tax ID - then you create master account
#          and Customer ID - otherwise dont create anything"*.
# Rules:   BR-MET-1030 (this rule) · BR-CUS-1010 (the account hangs off the
#          ADDRESS) · BR-CUS-1011 (one owner account per address) ·
#          BR-CUS-1022 (identity is per kind) · BR-CUS-1023 (a name AND one
#          identifier) · BR-MET-151 clause 3 (no category off a name) ·
#          BR-MET-402 clause 5 (the import creates no PARTY from a NAME —
#          NARROWED 2026-09-19: a row that STATES a category creates and links
#          one; reading a category OFF a name is still forbidden) ·
#          CLAUDE.md hard-won law 14 (Postgres aborts a transaction; SQLite
#          does not) · law 7 (prove the guard RED first)
# Screens: WFL-01.premises.2 (the mapping) · .3 (validation) · .5 (the receipt)
# ───────────────────────────────────────────────────────
"""CR-058 W3 — an owner with an identifier gets an account; a name alone gets none.

WHAT THIS FILE MEASURES
-----------------------
The ruling has three outcomes and every one of them is a COUNT on a receipt,
because that is what `CR-058` task 12 asks for in as many words: *"the receipt
must say which rows got an owner account and which are waiting for someone to
identify the owner."*

    owner name + at least one identifier  ->  an owner account and a Customer #
    owner name alone                      ->  the address loads, NOTHING created
    no owner                              ->  unchanged

Each case asserts the count is RIGHT **and** that it is non-zero in the case
that produces it. A count that reads zero because nothing was measured satisfies
every relational assertion — `CR-055`'s own lesson, one rule later.

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
⚠ **THE FOUR BELOW ARE FAILURES THIS SUITE ACTUALLY PRODUCED WHILE THE FEATURE
WAS BEING BUILT, QUOTED VERBATIM RATHER THAN RECONSTRUCTED.** Two of them were
defects in the TEST and two in the CODE, and both kinds are recorded, because a
suite that only lists the bugs it caught in the product implies it never had any
of its own.

* **A row with an owner and an identifier reached the account door and the door
  refused it**, because the fixture's unit carried no plan (`BR-MET-040`). It
  failed on a refusal that has nothing to do with owning a property, which is
  exactly how a green-looking suite ends up not exercising its own subject:

      E       core.errors.BizError: BIZ-COMPLETENESS
              (customers.account.plan_required_at_activation)

* **`link_customer`'s answer was read under the wrong key.** The not-created
  branch and the created branch return the same SHAPE, and the customer's id is
  `id`, not `customer_id` — so `link.get("customer_id")` was `None` on every
  successful resolution and the reassignment refused every buyer it had just
  created a number for:

      E       core.errors.BizError: BIZ-COMPLETENESS
              (customers.customer.identity_required_person)

  ⚠ **This is the one worth reading twice.** The refusal it produced is a real,
  correct, well-worded refusal — *"this person needs an identifier"* — raised
  over a person who had just presented one. Nothing about the message said
  *"the caller looked in the wrong place"*.

* **The landlord case asserted a behaviour the SIGNED RULES do not produce**, and
  the suite is what found the contradiction rather than the code:

      E       AssertionError: three buildings, ONE Customer #. A second number
              here is the duplicate-landlord defect CR-058's ruling 0 exists to
              close.
      E       assert 3 == 1

  `BR-CUS-089` needs a date of birth for a person to match strongly and the PO's
  four identifiers do not include one. **Nothing was reconciled**; the case was
  split in two — one for a COMPANY, which does resolve to one number, and one
  pinning the PERSON limit with its reasoning.

* **The idempotency case passed for the wrong reason and then failed for the
  right one.** Re-uploading a byte-identical file is refused as a duplicate
  UPLOAD before any owner logic runs:

      E       sqlite3.IntegrityError: UNIQUE constraint failed:
              import_runs.tenant_id, import_runs.target, import_runs.file_hash

  so the second run now differs by a cell, which is what an operator correcting a
  spreadsheet actually does.

**AND ONE GUARD WAS BROKEN DELIBERATELY TO SEE IT BITE.** The
`OWNER_ACCOUNT_ELIGIBLE` branch in `_load_locked` was removed — the state of the
product yesterday — and the two figures the ruling turns on both went red:

      E       AssertionError: CR-058 task 11: a row with a name and an
              identifier must get the address an owner account
      E       assert 0 == 1

⚠ **THE POSTGRES CASE BELOW IS SKIPPED ON THE DEFAULT SUITE AND THAT IS THE
POINT.** `config/settings/test.py` hardcodes in-memory SQLite, which has no
aborted-transaction state, so the version WITHOUT the savepoint passes every
test on every machine and loses a real migration the first time a row is
refused. CLAUDE.md hard-won law 14 in one paragraph.

WHAT IS DELIBERATELY *NOT* CHANGED, ASSERTED SO NOBODY BUILDS IT
-----------------------------------------------------------------
* **The import still creates no PARTY.** `BR-MET-402` clause 5 stands:
  `premises_owners.category_id` is NOT NULL and `BR-MET-151` clause 3 forbids
  reading a category off a name. `test_cr058_w3__the_import_still_creates_no_
  premises_owner_row` is the assertion that would go red if a lane "finished
  the job" by inventing a category.
* **No row is REJECTED on owner grounds.** `CR-055`'s ruling is untouched: all
  three new rules are `WARNING` + `FLAG_ONLY`, and the address loads.
* **Nothing may guess the account type.** A row with identity and no category
  creates nothing rather than defaulting to `residential`.
"""

import pytest
from django.db import connection

from apps.customers import models as customer_models
from apps.metering import import_rules, import_runs
from apps.metering import models as metering_models

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    brazos,
    marcus,
    owner_for,
    tenant_ctx,
)
from tests.test_cr023_import_stages import ALL_ON, HEADERS, MAPPING, _csv, _row

pytestmark = pytest.mark.django_db


@pytest.fixture()
def homes_present(monkeypatch):
    """⛔ `BR-CUS-1114` (PO 2026-10-02) — a master account only on a building of
    two or more homes. A PREMISES import cannot carry homes (units are their own
    import), so on an INSERT the owner's account is now refused by that rule —
    `test_cr058_w3__a_new_address_from_the_sheet_has_no_homes_so_no_owner_account`
    below proves exactly that. The cases that take this fixture are about WHO
    the owner is (identity, customer matching, idempotency), so the home count
    is answered as two for them and they go on testing that."""
    from apps.customers import services as customer_services

    monkeypatch.setattr(customer_services, "dwelling_units_at_premises", lambda _premises: 2)


def test_cr058_w3__a_new_address_from_the_sheet_has_no_homes_so_no_owner_account(brazos, marcus):
    """`BR-CUS-1114` on the import door: a name, an identifier and a type, on a
    NEW address with no homes yet — no master account, the run still loads,
    and the receipt does not claim one."""
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    51,
                    "Marisol Alvarez",
                    OWNER_KIND="person",
                    **{"OWNER PHONE": "555-0140", "OWNER ACCOUNT TYPE": code},
                )
            ],
        )["receipt"]
        assert receipt["loaded"] == 1
        assert receipt["premises_owner_accounts_created"] == 0
        premises = metering_models.Premises.objects.get(address_line="51 Bluestem Ln")
        assert not customer_models.Account.objects.filter(
            premises_id=premises.id, kind="master"
        ).exists()

POSTGRES_ONLY = pytest.mark.skipif(
    connection.vendor != "postgresql",
    reason=(
        "law 14 has no failure mode on SQLite — an aborted transaction does not "
        "exist there, which is exactly why the unguarded code passes green. Run "
        "with DJANGO_SETTINGS_MODULE=config.settings.local and a Postgres "
        "DATABASE_URL."
    ),
)

# ── the file, with the six columns the ruling needs ─────────────────────────
#
# ⚠ **THE HEADERS ARE THE OPERATOR'S, NOT OURS.** They are spelled the way a
# utility's export actually spells them, and the mapping below is what stage 1's
# auto-detect is expected to produce — so a change to `PREMISES_ALIASES` that
# stopped recognising `SSN` would go red here rather than silently offering the
# column unmapped.
OWNER_HEADERS = HEADERS + [
    "OWNER_KIND",
    "SSN",
    "DRIVING LICENCE",
    "OWNER PHONE",
    "TAX ID",
    "OWNER ACCOUNT TYPE",
    # PO ruling 2026-09-19 — *"Yes add owner category column in csv template"*.
    "OWNER CATEGORY",
]

#: r10's mapping with `OWNER` re-pointed at the TYPED owner column (DEF-1247)
#: plus the six new ones. `OWNER` must reach `owner`, not `owner_manager`:
#: every owner rule and `_resolve_owner_ref` read `owner_ref`.
OWNER_MAPPING = {
    **MAPPING,
    "OWNER": "owner",
    "OWNER_KIND": "owner_kind",
    "SSN": "owner_ssn",
    "DRIVING LICENCE": "owner_driving_licence",
    "OWNER PHONE": "owner_phone",
    "TAX ID": "owner_tax_id",
    "OWNER ACCOUNT TYPE": "owner_account_type",
    "OWNER CATEGORY": "owner_category",
}

BLANKS = {
    "OWNER_KIND": "",
    "SSN": "",
    "DRIVING LICENCE": "",
    "OWNER PHONE": "",
    "TAX ID": "",
    "OWNER ACCOUNT TYPE": "",
    "OWNER CATEGORY": "",
}


def _owner_row(index: int, owner: str, **overrides) -> dict:
    """One premises row naming `owner`, with every identity cell blank unless
    the case fills it in.

    ⚠ `PREMISE_ID` and `PROP_TYPE` stay blank for `CR-055`'s stated reasons: a
    premise number not already on file is a tier-2 ERROR under the 2026-08-27
    numbering ruling, and a resolving `PROP_TYPE` is `DEF-540`. Either would
    reject rows for a reason that has nothing to do with owners, which would
    make every count below unmeasurable.
    """
    return _row(index, PREMISE_ID="", PROP_TYPE="", OWNER=owner, **{**BLANKS, **overrides})


def _run_the_file(actor, rows: list[dict], mode: str = "insert") -> dict:
    """Extract → transform → validate → load, through the SAME four functions a
    screen calls. Never a hand-built row (`test_cr023_load_stage`'s posture): a
    test that assembled `ImportRunRow`s itself would prove nothing about the
    four stages this CR moves behaviour between."""
    run = import_runs.extract(
        actor,
        {
            "target": "premises",
            "source_kind": "file",
            "file_name": "cr058_owner_identity.csv",
            "content": _csv(rows, OWNER_HEADERS),
            "session_ref": "sess_cr058",
            "ip": "71.42.108.14",
        },
    )
    import_runs.transform(actor, run["id"], {"mapping": OWNER_MAPPING, "row_handling": ALL_ON})
    import_runs.validate(actor, run["id"])
    return import_runs.load(actor, run["id"], {"write_mode": mode})


def _account_type_code(actor) -> str:
    """A real, active, non-legacy account type of THIS tenant.

    Read rather than hardcoded: `customers` seeds its own vocabulary per tenant
    and a literal `residential` here would be this file inventing the value the
    rule exists to stop anyone inventing.
    """
    row = (
        customer_models.AccountType.objects.filter(active=True)
        .exclude(legacy=True)
        .order_by("code")
        .first()
    )
    assert row is not None, "the tenant seeds at least one account type"
    return row.code


# ═══════════════════════════════════════════════════════════════════════════
# TASK 10 — THE COLUMNS EXIST, ON THE TEMPLATE AND ON THE MAPPING
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w3__the_premises_template_offers_the_owners_identity(brazos, marcus):
    """`BR-MET-1030` — the ruling cannot fire on a single row without them.

    ⚠ **AND THEY ARE OFFERED ON PREMISES AND NOWHERE ELSE.** A units file has no
    owner and no business gaining one; `VIRTUAL_COLUMNS_BY_TARGET` is keyed by
    target for exactly that reason.
    """
    with tenant_ctx(brazos):
        offered = {entry["target"] for entry in import_runs.target_columns("premises")}
        for column in (
            "owner_kind",
            "owner_ssn",
            "owner_driving_licence",
            "owner_phone",
            "owner_tax_id",
            "owner_account_type",
        ):
            assert column in offered, (
                "CR-058: the premises template must offer the owner's identity "
                f"columns, or the ruling cannot fire on a single row — {column} missing"
            )
        units = {entry["target"] for entry in import_runs.target_columns("units")}
        assert not (units & set(import_runs.PREMISES_OWNER_COLUMN_NAMES)), (
            "CR-058: a units file has no owner. BR-MET-1031 confirms that door "
            "unchanged, and an owner column on it would be the widening the "
            "pinning test exists to stop."
        )


def test_cr058_w3__every_new_column_is_optional_so_yesterdays_file_still_loads(brazos, marcus):
    """Adding a column to a published template is something the utility SEES.

    A file saved before today carries none of these headers, and it must behave
    exactly as it did — which is only true while every one of them is optional.
    """
    with tenant_ctx(brazos):
        offered = {entry["target"]: entry for entry in import_runs.target_columns("premises")}
        for column in import_runs.PREMISES_OWNER_COLUMN_NAMES:
            assert offered[column]["required"] is False, (
                f"CR-058: {column} must be optional — a required one would refuse "
                "every premises file every utility already holds"
            )


def test_cr058_w3__no_GOVERNMENT_identifier_ships_a_worked_cell(brazos, marcus):
    """`DEF-962`, on the columns `DEF-962` could not have reached.

    ⛔ **NARROWED 2026-09-19, AND THE REASON IS KEPT WHILE THE BLANKET GOES.**
    This case asserted that EVERY identity column plus `owner_account_type`
    ships `sample == ""`, under `DEF-962`'s reason: *"a worked cell here would
    put an invented Social Security number in the file a utility hands its
    staff."* **That reason is exactly right and it does not reach all six.**

    The blanket had a measured cost. The shipped sample said `person` in the
    owner-kind cell and left the other eight owner columns empty, so the file a
    utility is handed to copy **modelled the failure the PO reported** — owner
    details supplied, no master account generated. An operator reads a sample
    to learn what goes in each column; one committing value beside eight blanks
    teaches that the rest are decorative.

    **So the rule is now the reason rather than the blanket:**

      * a **GOVERNMENT IDENTIFIER** ships blank, always — `owner_ssn`,
        `owner_driving_licence`, `owner_tax_id`. There is no way to write one
        that is not somebody's, and this half is asserted more strictly than
        before because it is now asserted for its own sake;
      * the **PHONE** may carry a number from the `555-01xx` range reserved for
        fiction, which cannot be anybody's and is what lets the shipped row
        earn an account without inventing a government number;
      * the two **LOOKUPS** carry this tenant's OWN code, which is not an
        invention by any reading — it is what `premises_type` has always done
        with `apartment_complex`. A declared `""` there would SHADOW the
        tenant's lookup (`sample_csv`'s `cell()` tests `"sample" in entry`
        first), and did: both shipped empty while the indexes held eight codes
        and five.
    """
    with tenant_ctx(brazos):
        offered = {entry["target"]: entry for entry in import_runs.target_columns("premises")}

        # ⚠ **THE HALF THAT IS ABSOLUTE.** Named explicitly rather than derived
        # from `OWNER_IDENTIFIER_COLUMNS`, because the point is *government
        # identifier*, not *identifier* — and a lane adding a seventh one must
        # come here and say which kind it is.
        for column in ("owner_ssn", "owner_driving_licence", "owner_tax_id"):
            assert offered[column].get("sample") == "", (
                f"CR-058/DEF-962: {column} must ship its worked cell BLANK — a "
                "value here is a government identifier this product invented"
            )

        # The kind is the product's own vocabulary, not somebody's data.
        assert offered["owner_kind"].get("sample") == "person"

        # ⚠ **THE PHONE, AND THE RESERVED RANGE IS THE ASSERTION.** `555-01xx`
        # is set aside for fiction; anything outside it in this cell is a
        # number that could ring somebody.
        phone = offered["owner_phone"].get("sample") or ""
        assert phone.startswith("555-01"), (
            f"the sample phone {phone!r} is not in the 555-01xx range reserved for "
            "fiction — a worked cell here must be incapable of being anybody's"
        )

        # ⚠ **AND THE LOOKUPS DECLARE NOTHING**, so the tenant's own code
        # reaches the file. A declared value — even `""` — shadows it.
        for column in ("owner_account_type", "owner_category"):
            assert "sample" not in offered[column], (
                f"{column} declares a sample, which shadows this tenant's own "
                "lookup and ships the cell empty"
            )


def test_cr058_w3__the_identity_columns_never_reach_the_premises_model(brazos, marcus):
    """None of the six is a column of `premises`, so `Premises(**record)` with
    one in raises on a field that does not exist — the same reason
    `PARSE_PROBLEMS` is stripped."""
    for column in import_runs.PREMISES_OWNER_COLUMN_NAMES:
        assert column in import_runs._NOT_A_COLUMN, (
            f"CR-058: {column} must be stripped before the row is built, or "
            "every row of every premises file raises"
        )
    model_fields = {field.name for field in metering_models.Premises._meta.get_fields()}
    assert not (model_fields & set(import_runs.PREMISES_OWNER_COLUMN_NAMES))


# ═══════════════════════════════════════════════════════════════════════════
# THE VERDICT — one function, three readers (stage 3, stage 4, the receipt)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    ("mapped", "expected"),
    [
        ({}, import_runs.OWNER_ACCOUNT_NO_OWNER),
        # ⚠ An identifier with NO NAME is still nothing. The ruling's first word
        # is *"If owner name is given"*, and a government identifier with no
        # party attached is a cell nobody can act on.
        ({"owner_ssn": "111-22-3333"}, import_runs.OWNER_ACCOUNT_NO_OWNER),
        ({"owner_ref": "Alvarez"}, import_runs.OWNER_ACCOUNT_AWAITING_IDENTITY),
        (
            {"owner_ref": "Alvarez", "owner_ssn": "111-22-3333"},
            import_runs.OWNER_ACCOUNT_IDENTITY_MISMATCH,  # no kind stated
        ),
        (
            {"owner_ref": "Ridge LLC", "owner_kind": "company", "owner_ssn": "111-22-3333"},
            import_runs.OWNER_ACCOUNT_IDENTITY_MISMATCH,  # borrowed from the other kind
        ),
        (
            {"owner_ref": "Alvarez", "owner_kind": "person", "owner_phone": "555-0140"},
            import_runs.OWNER_ACCOUNT_NO_ACCOUNT_TYPE,
        ),
        (
            {
                "owner_ref": "Alvarez",
                "owner_kind": "person",
                "owner_phone": "555-0140",
                "owner_account_type": "residential",
            },
            import_runs.OWNER_ACCOUNT_ELIGIBLE,
        ),
        (
            {
                "owner_ref": "Ridge LLC",
                "owner_kind": "company",
                "owner_tax_id": "84-1234567",
                "owner_account_type": "commercial",
            },
            import_runs.OWNER_ACCOUNT_ELIGIBLE,
        ),
    ],
)
def test_cr058_w3__the_verdict_reads_the_ruling(mapped, expected):
    """One table, every corner of *"name AND one identifier, otherwise nothing"*.

    ⚠ **A PHONE ALONE IS ENOUGH FOR A PERSON AND A PHONE ALONE IS NOT ENOUGH
    FOR A COMPANY**, and both are deliberate: the PO's list for a business names
    the Tax ID and nothing else (`BR-CUS-1023`). A lane that "unified" the two
    tables would either refuse a customer the PO said to create or file a
    business under a telephone number.
    """
    assert import_runs.owner_account_verdict(mapped)["verdict"] == expected


def test_cr058_w3__the_verdict_hands_over_customers_own_field_names():
    """The block handed to the account door speaks CUSTOMERS' vocabulary, not the
    spreadsheet's — one translation table, so the two cannot drift."""
    verdict = import_runs.owner_account_verdict(
        {
            "owner_ref": "Marisol Alvarez",
            "owner_kind": "person",
            "owner_ssn": "111-22-3333",
            "owner_driving_licence": "TX-9910",
            "owner_account_type": "residential",
        }
    )
    block = import_runs.owner_customer_block({"owner_ref": "Marisol Alvarez"}, verdict)
    assert block["display_name"] == "Marisol Alvarez"
    assert block["kind"] == "person"
    assert block["identity"] == {"ssn": "111-22-3333", "driving_licence": "TX-9910"}


# ═══════════════════════════════════════════════════════════════════════════
# TASKS 11 + 12 — THE THREE OUTCOMES, END TO END, THROUGH THE FOUR STAGES
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w3__a_name_and_an_identifier_gets_the_address_an_owner_account(brazos, marcus, homes_present):
    """Task 11, and it is `CR-056` task 24 as well — the caller that never existed.

    ⚠ **THE ACCOUNT HANGS OFF THE ADDRESS** (`BR-CUS-1010`): `premises_id` set,
    `unit_id` NULL. That is asserted rather than assumed, because a master
    account anchored on a unit is the shape `CR-056` W1 retired and a regression
    to it would bill the wrong thing.
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    1,
                    "Marisol Alvarez",
                    OWNER_KIND="person",
                    **{"OWNER PHONE": "555-0140", "OWNER ACCOUNT TYPE": code},
                )
            ],
        )["receipt"]
        assert receipt["premises_owner_accounts_created"] == 1, (
            "CR-058 task 11: a row with a name and an identifier must get the "
            "address an owner account"
        )
        premises = metering_models.Premises.objects.get(address_line="1 Bluestem Ln")
        account = customer_models.Account.objects.get(premises_id=premises.id)
        assert account.unit_id is None, (
            "BR-CUS-1010: the owner's account hangs off the ADDRESS. A unit "
            "anchor is the shape CR-056 W1 retired."
        )
        assert customer_models.CustomerAccount.objects.filter(account_id=account.id).exists(), (
            "CR-058 ruling 0: the door resolves the customer — match first, "
            "create on no match — so an eligible row ends with a Customer #"
        )


def test_cr058_w3__a_name_alone_creates_nothing_and_the_receipt_says_so(brazos, marcus):
    """Task 12 — the PO's own *"otherwise dont create anything"*.

    ⚠ **AND THE ADDRESS STILL LOADS.** `CR-055`'s ruling is untouched: the row
    is FLAGGED, never rejected. Both halves are asserted, because a build that
    refused the row would satisfy *"create nothing"* and break the ruling it
    sits beside.
    """
    with tenant_ctx(brazos):
        receipt = _run_the_file(marcus, [_owner_row(2, "Bluestem Holdings Trust")])["receipt"]
        assert receipt["premises_owner_accounts_created"] == 0, (
            "CR-058 task 12: a name with no identifier creates NOTHING — the "
            'PO\'s own "otherwise dont create anything"'
        )
        assert receipt["premises_owner_awaiting_identity"] == 1, (
            "CR-058 task 12: the receipt must say which rows are WAITING for "
            "someone to identify the owner, or a half-identified migration "
            "looks exactly like a finished one"
        )
        assert metering_models.Premises.objects.filter(address_line="2 Bluestem Ln").exists(), (
            "CR-055 stands: the address loads with no owner, flagged. Refusing "
            "it would reverse a ruling this one only narrows."
        )
        assert not customer_models.Account.objects.filter(kind="master").exists()


def test_cr058_w3__a_row_with_no_owner_at_all_is_unchanged(brazos, marcus):
    """The third outcome, and it is the one that must not move: no owner column
    value means exactly what it meant yesterday."""
    with tenant_ctx(brazos):
        receipt = _run_the_file(marcus, [_owner_row(3, "")])["receipt"]
        assert receipt["premises_owner_accounts_created"] == 0
        assert receipt["premises_owner_awaiting_identity"] == 0, (
            "an EMPTY owner column is not an owner waiting to be identified — "
            "it is the pre-existing ownerless case, counted by "
            "premises_owner_blank, and merging the two would inflate the new "
            "figure with rows the ruling never touched"
        )
        assert receipt["premises_owner_blank"] == 1


def test_cr058_w3__a_company_presenting_a_persons_identifier_creates_nothing(brazos, marcus):
    """`BR-CUS-1022` — a company is identified by its Tax ID and by nothing else.

    An SSN filed under a company is stored where the company matcher never
    looks, which is worse than an empty column because the matcher reads it.
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    4,
                    "Ridge Property LLC",
                    OWNER_KIND="company",
                    SSN="111-22-3333",
                    **{"OWNER ACCOUNT TYPE": code},
                )
            ],
        )["receipt"]
        assert receipt["premises_owner_accounts_created"] == 0, (
            "CR-058: a company is identified by its Tax ID, and an SSN filed "
            "under one is stored where the company matcher never looks"
        )
        assert receipt["premises_owner_identity_mismatch"] == 1


def test_cr058_w3__identity_without_an_account_type_creates_nothing(brazos, marcus):
    """Nothing may guess what a customer is charged as.

    The consumer category is what the bill is priced and reported by; defaulting
    it would be a money decision taken by a shrug. Counted APART from the
    missing-identifier case because the work it asks of a person is different.
    """
    with tenant_ctx(brazos):
        receipt = _run_the_file(
            marcus,
            [_owner_row(5, "Marisol Alvarez", OWNER_KIND="person", **{"OWNER PHONE": "555-0140"})],
        )["receipt"]
        assert receipt["premises_owner_accounts_created"] == 0
        assert receipt["premises_owner_no_account_type"] == 1, (
            "CR-058: a row that can be identified and does not say how the "
            "account is charged creates nothing, and is told WHICH cell is "
            "missing — a different job from finding an identifier"
        )
        assert receipt["premises_owner_awaiting_identity"] == 0


def test_cr058_w3__one_COMPANY_landlord_across_three_addresses_is_ONE_customer(brazos, marcus, homes_present):
    """The duplicate-landlord defect, closed on the import path.

    `CR-058`'s governing ruling: *"we check whether we ahve mathicng customer
    ID, if yes, we use it if no we create it"*. Three buildings, ONE Customer #
    — and three ACCOUNTS, because an account is per address (`BR-CUS-1010`)
    while a customer is a party.

    ⚠ **A COMPANY, AND THE KIND IS LOAD-BEARING RATHER THAN INCIDENTAL — READ
    THE CASE BELOW BEFORE CHANGING THIS ONE.** `BR-CUS-1022` / `tier_for` makes
    a company a `strong` match on **name + Tax ID**, which the premises file
    carries; a PERSON needs **name + date of birth + one government ID**
    (`BR-CUS-089`, PO 2026-08-25 closing `OQ-364`) and there is no date of birth
    anywhere in the PO's four identifiers. So this is the landlord case that
    resolves to one number today, and it is also the common one — a landlord
    with three buildings is usually a company.
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        cells = {
            "OWNER_KIND": "company",
            "TAX ID": "84-1234567",
            "OWNER ACCOUNT TYPE": code,
        }
        receipt = _run_the_file(
            marcus,
            [_owner_row(index, "Whitfield Rentals LLC", **cells) for index in (11, 12, 13)],
        )["receipt"]
        assert receipt["premises_owner_accounts_created"] == 3
        customers = {
            link.customer_id
            for link in customer_models.CustomerAccount.objects.filter(account__kind="master")
        }
        assert len(customers) == 1, (
            "three buildings, ONE Customer #. A second number here is the "
            "duplicate-landlord defect CR-058's ruling 0 exists to close."
        )
        assert customer_models.Account.objects.filter(kind="master").count() == 3, (
            "an account is per ADDRESS (BR-CUS-1010) and a customer is a party "
            "— one landlord, one number, three accounts"
        )


def test_cr058_w3__a_PERSON_landlord_gets_one_number_per_address_and_that_is_the_signed_rules(
    brazos, marcus, homes_present
):
    """⛔ **REVERSED ON 2026-09-01 BY `BR-CUS-1024`, AND THE OBJECTION THIS CASE
    RAISED IS ANSWERED RATHER THAN DELETED.** (`DEF-2585`, fixed in 450af92b —
    the row that recorded this case going red, and two more in
    `test_cr047_per_record_load.py`, when the rule landed and the lane that
    landed it updated neither suite.)

    It used to assert **three** numbers and its message said, correctly for the
    rules as they then stood: *"a lane that 'fixes' this by linking on an SSN
    alone has reversed `BR-CUS-089` on a money path."* **That objection is the
    right one and `BR-CUS-1024` is built so that it does not apply.**

    **WHAT THE OLD CASE PINNED, and it was true when written.** `CR-058` task 5
    says a landlord with three buildings must end with ONE Customer #. For a
    COMPANY the case above proves it. For a PERSON it was unreachable, because:

      * `BR-CUS-1023` — a **phone alone CREATES** a Customer #. The PO named it.
      * `BR-CUS-089` — a person is a `strong` match on **name + date of birth +
        one government ID**, and the premises template carries no date of birth,
        so every address opened its own number.

    **WHY THAT IS NO LONGER THE ANSWER.** The PO ruled the governing sentence of
    `CR-058` on 2026-09-01: *"During regular and master account creation process
    - we check whether we ahve mathicng customer ID, if yes, we use it if no we
    create it, given we have identify atleast 1"*. `BR-CUS-1024` is that ruling
    written down, and it is a **THIRD** test rather than a loosening of the
    second: name + one GOVERNMENT identifier decides **how many rows exist**,
    and `BR-CUS-089`'s signed test still decides **whether money moves**.

    **SO `BR-CUS-089` IS NOT REVERSED, AND THE ASSERTION BELOW PROVES BOTH
    HALVES ON THE SAME THREE ADDRESSES.** The landlord now holds ONE number, and
    that link carries **no match tier and no confirmer** — so
    `discounts.carry_forward_offer` still refuses and **$0.00** moves. The
    **$153.50** of `WE-7`/`GT-23` still needs the date of birth this file does
    not collect. What changed is that the database no longer states, as fact,
    that three different people share one Social Security number.

    Measured before the rule: `C-00001`, `C-00002`, `C-00003`, one SSN
    (`DEF-2587`).
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        cells = {
            "OWNER_KIND": "person",
            "SSN": "111-22-3333",
            "OWNER ACCOUNT TYPE": code,
        }
        receipt = _run_the_file(
            marcus,
            [_owner_row(index, "Marisol Alvarez", **cells) for index in (14, 15, 16)],
        )["receipt"]
        assert receipt["premises_owner_accounts_created"] == 3
        customers = {
            link.customer_id
            for link in customer_models.CustomerAccount.objects.filter(account__kind="master")
        }
        assert len(customers) == 1, (
            "BR-CUS-1024 (PO 2026-09-01): a name and one government identifier "
            "REUSE the customer number already on file, so one landlord at "
            "three addresses holds ONE number. Three numbers means the reuse "
            "test has been removed or narrowed."
        )

        # ⚠ **AND `BR-CUS-089` IS STILL WHOLE — THIS IS THE HALF THE OLD CASE
        # WAS RIGHT TO WORRY ABOUT.** Reusing a number is a statement about how
        # many rows exist; it may not become a statement about whose money may
        # move. No link here carries a tier or a confirmer, so the deposit
        # carry-forward still refuses and $0.00 follows the reuse.
        links = customer_models.CustomerAccount.objects.filter(account__kind="master")
        assert links.count() == 3, "three addresses, three accounts, one customer"
        assert {link.match_tier for link in links} == {None}, (
            "a reuse may never store a match tier: BR-CUS-089 still needs the "
            "name, the date of birth AND one government ID before money moves"
        )
        assert {link.match_confirmed_by_id for link in links} == {None}


def test_cr058_w3__the_run_is_idempotent_on_the_owner_account(brazos, marcus, homes_present):
    """*Ensure*, not *create a second one*. `BR-CUS-1011` would refuse the second
    anyway, and this asserts the second run does not report one as created."""
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        cells = {
            "OWNER_KIND": "person",
            "OWNER PHONE": "555-0140",
            "OWNER ACCOUNT TYPE": code,
        }
        first = _run_the_file(marcus, [_owner_row(21, "Marisol Alvarez", **cells)])["receipt"]
        assert first["premises_owner_accounts_created"] == 1
        # ⚠ **THE SECOND FILE MUST DIFFER BY A BYTE, AND THAT IS THE PRODUCT'S
        # OWN RULE RATHER THAN A TEST TRICK.** `import_runs` is unique on
        # `(tenant, target, file_hash)`, so re-uploading the IDENTICAL file is
        # refused as a duplicate UPLOAD before any owner logic runs — which
        # would make this case pass for the wrong reason. A changed CITY is a
        # different file carrying the same premises key, which is what an
        # operator correcting a spreadsheet and uploading again actually does.
        second = _run_the_file(
            marcus,
            [_owner_row(21, "Marisol Alvarez", CITY="Fulshear", **cells)],
            mode="upsert",
        )["receipt"]
        assert second["premises_owner_accounts_created"] == 0, (
            "the address already has an owner account; a second one is two "
            "owners of one building (BR-CUS-1011)"
        )
        assert customer_models.Account.objects.filter(kind="master").count() == 1


# ═══════════════════════════════════════════════════════════════════════════
# STAGE 3 — THE OPERATOR IS TOLD ON THEIR OWN FILE, BEFORE THEY COMMIT
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w3__the_three_new_rules_all_flag_and_never_reject(brazos, marcus):
    """`CR-055` stands: a premises upload rejects no row on owner grounds.

    An ERROR here would refuse every row of the first file a utility ever sends,
    which is `DEF-1088`'s own warning about ordering a mandatory field.
    """
    declared = {rule.code: rule for rule in import_rules.PREMISES_RULES}
    for code in (
        "PRM.OWNER_AWAITING_IDENTITY",
        "PRM.OWNER_ACCOUNT_TYPE_MISSING",
        "PRM.OWNER_IDENTITY_MISMATCH",
    ):
        assert code in declared, f"CR-058: {code} must be declared for stage 3 to draw it"
        assert declared[code].severity == import_rules.WARNING
        assert declared[code].action == import_rules.FLAG_ONLY
        assert declared[code].blocks is False, (
            "CR-055's ruling is not reversed: the address loads. A blocking "
            "rule here refuses the whole file over a column nobody filled in."
        )


def test_cr058_w3__no_sentence_shown_to_a_clerk_carries_a_rule_id(brazos, marcus):
    """B14 rule 32 clause 4 — no rule id and no internal code in clerk-facing copy.

    The sentences below are read by an operator standing in front of a
    spreadsheet; `BR-MET-1030` means nothing to them and `premises_owner_id`
    means less.
    """
    declared = {rule.code: rule for rule in import_rules.PREMISES_RULES}
    for code in (
        "PRM.OWNER_AWAITING_IDENTITY",
        "PRM.OWNER_ACCOUNT_TYPE_MISSING",
        "PRM.OWNER_IDENTITY_MISMATCH",
    ):
        sentence = declared[code].sentence
        for forbidden in ("BR-", "PRM.", "OQ-", "_id", "uuid"):
            assert forbidden not in sentence, (
                f"B14 rule 32: {code}'s sentence is read by a clerk and carries "
                f"{forbidden!r}"
            )


# ═══════════════════════════════════════════════════════════════════════════
# WHAT MUST NOT CHANGE
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w3__the_import_still_creates_no_premises_owner_row(brazos, marcus):
    """`BR-MET-402` clause 5 — the import never creates a PARTY **from a name
    alone**, and no ruling has reversed that.

    ⛔ **AMENDED 2026-09-19. THIS DOCSTRING USED TO SAY *"the template offers
    no category column"* AND TO READ CLAUSE 5 AS UNCONDITIONAL.** Neither is
    true now: the PO ruled *"Yes add owner category column in csv template"*,
    and a row that STATES a category does create and link the party — see the
    sibling test below.

    ⚠ **THE ASSERTION ITSELF DID NOT MOVE, AND THAT IS THE POINT.** The row
    here carries no category, so nothing may be created from it, exactly as
    before. What clause 5 forbids is READING a category off a name
    (`BR-MET-151` clause 3) — *Nobody On File Holdings* is not proof of a
    landlord — and being TOLD one was never the same act. **This is still the
    assertion that goes red if a lane "finishes the job" by inventing a
    category**, and it is now load-bearing in a way it was not yesterday:
    yesterday the code could not create a party at all, so it could only ever
    pass. Today it can, and this is what says it must not without being told.
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        before = metering_models.PremisesOwner.objects.count()
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    31,
                    "Nobody On File Holdings",
                    OWNER_KIND="company",
                    **{"TAX ID": "84-1234567", "OWNER ACCOUNT TYPE": code},
                )
            ],
        )
        assert metering_models.PremisesOwner.objects.count() == before, (
            "BR-MET-402 clause 5: the import never creates a party from a NAME. "
            "Inventing a category to force one would supersede a signed rule."
        )
        # ⚠ **AND THE GAP IS NOW COUNTED RATHER THAN SILENT (PO 2026-09-19).**
        # This row still gets an account, so without this figure the receipt
        # reports a clean migration over an address with nobody named on it —
        # which is the defect the ruling was about.
        assert receipt["counts"]["premises_owner_no_category"] == 1
        assert receipt["counts"]["premises_owner_parties_created"] == 0


def test_cr058_w3__a_stated_category_creates_the_party_and_links_the_account(brazos, marcus, homes_present):
    """⛔ **PO RULING 2026-09-19, VERBATIM: *"Yes add owner category column in
    csv template"*.**

    The reported symptom was *"when we import premsies -> provide owner deetails
    -> in thos ec ases Master Account is not getting generated"*. The account
    WAS generated; what was missing is that nobody owned it —
    `premises.owner_id` NULL and no `premises_owners` row, on every row of a
    first migration, because the branch that writes the link is the one only an
    owner ALREADY ON FILE can take.

    ⚠ **THIS ASSERTS THE LINK, NOT THE COUNT, AND THAT DISTINCTION IS THE
    WHOLE DEFECT.** `premises_owner_accounts_created == 1` was TRUE throughout
    and is what kept this green for weeks: the receipt was telling the truth
    about the account and nothing asked whether the account had an owner. So
    the three assertions that matter here read the DATABASE —
    `premises.owner_id`, the party's category, and
    `premises_owners.master_account_id`, which is the declared link
    `DEF-2902`/`DEF-2903` report missing from every master account.
    """
    with tenant_ctx(brazos):
        code = _account_type_code(marcus)
        category = _owner_category_code()
        before = metering_models.PremisesOwner.objects.count()
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    32,
                    "Told You Holdings",
                    OWNER_KIND="company",
                    **{
                        "TAX ID": "84-7654321",
                        "OWNER ACCOUNT TYPE": code,
                        "OWNER CATEGORY": category,
                    },
                )
            ],
        )
        assert metering_models.PremisesOwner.objects.count() == before + 1
        assert receipt["counts"]["premises_owner_parties_created"] == 1
        assert receipt["counts"]["premises_owner_no_category"] == 0

        owner = metering_models.PremisesOwner.objects.get(name="Told You Holdings")
        assert owner.category.code == category
        premises = metering_models.Premises.objects.get(owner_id=owner.id)
        # The address is joined to the party — the half that was NULL.
        assert premises.owner_id == owner.id
        # … and the party is joined to the account, which is the declared link.
        assert owner.master_account_id is not None
        # ⚠ **BR-MET-151 clause 4 — the provenance is NOT cleared.** The
        # operator's own string stays in the legacy box; whether the typed owner
        # should supersede it is `OQ-500`, a money decision nobody has taken.
        assert premises.owner_manager == "Told You Holdings"


def _owner_category_code() -> str:
    """A real, active owner category of THIS tenant — read, never hardcoded.

    ⚠ The five (`owner_occupier`, `landlord`, `property_manager`, `hoa`,
    `builder`) are SEEDED into an editable Settings lookup, so a literal here
    would be this file inventing the value the rule exists to stop anyone
    inventing — and would go stale the first time a utility renamed one.
    `_account_type_code` above takes the same posture for the same reason.
    """
    from apps.tenancy import models as tenancy_models

    row = (
        tenancy_models.PremisesOwnerCategory.objects.filter(active=True)
        .order_by("code")
        .first()
    )
    assert row is not None, "the tenant seeds at least one owner category"
    return row.code


@POSTGRES_ONLY
def test_cr058_w3__a_refused_owner_account_does_not_destroy_the_run(brazos, marcus):
    """CLAUDE.md hard-won law 14 — the savepoint is the ONLY option, not the tidy one.

    In PostgreSQL a failed statement poisons the whole transaction: without the
    nested `atomic()` around the owner-account call, one refusal makes every
    later query raise `InFailedSqlTransaction` and **every premises row already
    written is lost at COMMIT**. The bad account type below is refused by the
    account door; the addresses must still land.
    """
    with tenant_ctx(brazos):
        receipt = _run_the_file(
            marcus,
            [
                _owner_row(
                    41,
                    "Marisol Alvarez",
                    OWNER_KIND="person",
                    **{"OWNER PHONE": "555-0140", "OWNER ACCOUNT TYPE": "no-such-category"},
                ),
                _owner_row(42, ""),
            ],
        )["receipt"]
        assert metering_models.Premises.objects.filter(address_line="42 Bluestem Ln").exists(), (
            "law 14: a refused owner account must not take the rows written "
            "after it. On PostgreSQL an unguarded except loses the whole run."
        )
        assert receipt["loaded"] == 2

# ── Trace ──────────────────────────────────────────────
# Change:   CR-058 W1 tasks 3, 4, 5 and 6 — ONE resolver, every account door.
#           Match first, create only where nothing matches, and refuse where
#           there is nothing to match on.
# Defect:   DEF-2587 — one landlord, one Social Security number, THREE customer
#           numbers. Measured on the master door before this lane.
# Rules:    BR-CUS-1024 (match first; an exact name + government identifier
#           REUSES the number on file; a phone does not; ambiguity refuses and
#           still saves; no identifier means no account — PO 2026-09-01) ·
#           BR-CUS-1023 (the creation minimum, and its "an account may still be
#           opened" clause SUPERSEDED the same day) · BR-CUS-1022 (identity is
#           per kind) · BR-CUS-089 (the MONEY test — deliberately untouched) ·
#           BR-CUS-019 (advisory) · BR-CUS-054 · CLAUDE.md hard rule 1 (tenant
#           scoping) · hard rule 7 (audit_log) · law 7 (prove a guard RED first)
# Impacts:  apps/customers/identity_match.reuse_candidate ·
#           apps/customers/services.resolve_customer_for_account ·
#           apps/customers/services.refuse_account_without_identity ·
#           the four doors: create_account · create_master_account · move_in ·
#           New Connect and the premises-owner door (through the seam)
# ───────────────────────────────────────────────────────
"""**A landlord with three buildings has ONE customer number.**

WHAT THIS FILE COUNTS, AND WHY COUNTING IS THE POINT
====================================================
Every test that already existed asserted the TIER of a match and the money that
did or did not follow it, and every one of them was correct and passed. **None
of them asked how many customer rows were left behind.** That is the whole of
`DEF-2587`: the product had a test suite that could not see one landlord being
written down three times over one Social Security number.

    before this lane   C-00001 · C-00002 · C-00003   one landlord, one SSN
    after it           C-00001                       three buildings, one number

THE THREE QUESTIONS, WHICH ARE NOT ONE QUESTION
===============================================
| question | the test | what it decides |
|---|---|---|
| may a number be MINTED? | `BR-CUS-1023` — name + one identifier, phone included | whether a row exists |
| is one ALREADY ON FILE? | `BR-CUS-1024` — name + one GOVERNMENT identifier | how many rows exist |
| may MONEY follow it? | `BR-CUS-089` — the signed `strong` tier | whether a deposit moves |

**Collapse any two of them and one assertion below goes red.** `tc7` is the one
that holds the third apart from the other two: a reused number carries **no
tier**, so **$0.00** of anybody's deposit moves, and the **$153.50** of
`WE-7`/`GT-23` still needs the full signed test with its date of birth.

AND THE HALF THAT ARRIVED MID-BUILD
===================================
The PO ruled, hours after `CR-058` was written, that **without an identifier
there is no account either** — superseding that morning's *"a person standing at
the counter who will not give an identifier still gets their water"*. So the
door refuses, and `tc8` asserts that it refuses BEFORE writing anything: not
that an exception was raised, but that **no account row exists afterwards**. An
assertion about an exception passes on a silent half-write.
"""

from __future__ import annotations

import pytest

from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — W1 shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: One landlord, three buildings. The name is compared exactly (case-folded),
#: the Social Security number through its keyed blind index.
LANDLORD = "Okonkwo, Adaeze"
LANDLORD_SSN = "555-44-3333"
LANDLORD_LICENCE = "TX-88213904"
LANDLORD_PHONE = "+1 (512) 555-0198"
LANDLORD_DOB = "1979-04-02"
COMPANY = "Rio Verde Property Holdings LLC"
COMPANY_TAX_ID = "12-3456789"


# ═══════════════════════════════════════════════════════════════════════════
# FIXTURE PLUMBING — real rows through the real doors (DEF-658: never the ORM)
# ═══════════════════════════════════════════════════════════════════════════
def _plan(tenant, service_code="electric"):
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant, name="Small Commercial",
        defaults={"code": "small-commercial", "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"Small Commercial — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _building(actor, tenant, *, address, owner=LANDLORD):
    """A premises with one common area, priced and metered — the shape the
    master-account door needs."""
    premises = make_premises(actor, address_line=address, owner_manager=owner)
    unit = make_unit(
        actor, premises["id"], label="Hallway lighting",
        unit_type="common_area", is_common_area=True,
    )
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant).id)}
    )
    metering_services.ensure_service_point(unit["id"], "electric")
    # `BR-CUS-1114` (PO 2026-10-02) — and two or more homes, since a master
    # account is raised only on a multi-unit building.
    for label in ("Unit 1", "Unit 2"):
        make_unit(actor, premises["id"], label=label)
    return premises


def _ordinary_unit(actor, tenant, *, address, label="Unit A"):
    premises = make_premises(actor, address_line=address)
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant).id)}
    )
    metering_services.ensure_service_point(unit["id"], "electric")
    return unit


def _person_block(**identity):
    return {
        "display_name": LANDLORD,
        "kind": identity_match.KIND_PERSON,
        "identity": dict(identity),
    }


def _open_master(actor, premises, *, customer=None):
    payload = {
        "premises_id": str(premises["id"]),
        "account_type": "commercial",
        "opened_at": "2026-07-01",
    }
    if customer is not None:
        payload["customer"] = customer
    return customers_services.create_master_account(actor, payload)


def _numbers():
    return sorted(
        customers_models.Customer.objects.filter(display_name=LANDLORD).values_list(
            "customer_no", flat=True
        )
    )


# ═══════════════════════════════════════════════════════════════════════════
# TC-1 · **THE ONE THE DEFECT IS ABOUT** — three buildings, ONE number
# ═══════════════════════════════════════════════════════════════════════════
def test_tc1_a_landlord_with_three_buildings_has_one_customer_number(brazos, marcus):
    """`DEF-2587`, in the terms `CR-058` states it.

    The landlord gives a name, says they are a person, and gives a Social
    Security number — one identifier, which is exactly what ruling 0 asks for.
    They do it at three buildings. **Before this lane the product wrote
    `C-00001`, `C-00002` and `C-00003`.**
    """
    with tenant_ctx(brazos):
        results = [
            _open_master(
                marcus,
                _building(marcus, brazos, address=f"{100 + n} Elm St"),
                customer=_person_block(ssn=LANDLORD_SSN),
            )
            for n in range(3)
        ]

        assert _numbers() == ["C-00001"], "three buildings must leave ONE customer"
        assert customers_models.Customer.objects.count() == 1

        # All three accounts exist and all three carry the same number.
        assert len({row["id"] for row in results}) == 3
        assert [row["customer_no"] for row in results] == ["C-00001"] * 3

        # And the clerk is told which of the three things happened, each time.
        assert results[0]["customer_outcome"] == customers_services.OUTCOME_CREATED
        assert results[1]["customer_outcome"] == customers_services.OUTCOME_LINKED
        assert results[2]["customer_outcome"] == customers_services.OUTCOME_LINKED
        assert results[0]["customer_reused"] is False
        assert results[1]["customer_reused"] is True


# ═══════════════════════════════════════════════════════════════════════════
# TC-2 · the ordinary door and the move-in door reach the SAME customer
# ═══════════════════════════════════════════════════════════════════════════
def test_tc2_every_door_resolves_to_the_same_customer(brazos, marcus):
    """`POST /accounts`, `POST /accounts/master` and `POST /accounts/{id}/move-in`
    all call one function, so the landlord who owns a building and rents a flat
    is ONE customer and not three."""
    with tenant_ctx(brazos):
        _open_master(
            marcus,
            _building(marcus, brazos, address="1408 Elm St"),
            customer=_person_block(ssn=LANDLORD_SSN),
        )
        assert _numbers() == ["C-00001"]

        unit = _ordinary_unit(marcus, brazos, address="22 Oak St")
        opened = customers_services.create_account(
            marcus,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
                "contact": {"full_name": LANDLORD},
                "customer": _person_block(driving_licence=LANDLORD_LICENCE, ssn=LANDLORD_SSN),
            },
        )
        assert opened["customer_no"] == "C-00001"
        assert opened["customer_outcome"] == customers_services.OUTCOME_LINKED

        customers_services.move_out(
            marcus, opened["id"], {"moved_out_on": "2026-07-31"}
        )
        moved = customers_services.move_in(
            marcus,
            opened["id"],
            {
                "account_type": "residential",
                "opened_at": "2026-08-01",
                "contact": {"full_name": LANDLORD},
                "customer": _person_block(ssn=LANDLORD_SSN),
            },
        )
        assert moved["customer_no"] == "C-00001"
        assert moved["customer_outcome"] == customers_services.OUTCOME_LINKED
        assert _numbers() == ["C-00001"], "one landlord, one number, three doors"


# ═══════════════════════════════════════════════════════════════════════════
# TC-3 · a phone CREATES and may never REUSE
# ═══════════════════════════════════════════════════════════════════════════
def test_tc3_a_phone_creates_a_number_and_can_never_reuse_one(brazos, marcus):
    """The asymmetry `BR-CUS-1024` exists to hold down.

    A phone is on the CREATE list (the PO named it) and on no government-id
    list. Minting a spare row on a shared household line costs a merge; REUSING
    one hands a stranger an existing customer's file.
    """
    with tenant_ctx(brazos):
        first = _open_master(
            marcus,
            _building(marcus, brazos, address="30 Pine St"),
            customer=_person_block(phone=LANDLORD_PHONE),
        )
        assert first["customer_no"] == "C-00001"
        assert first["customer_outcome"] == customers_services.OUTCOME_CREATED

        second = _open_master(
            marcus,
            _building(marcus, brazos, address="31 Pine St"),
            customer=_person_block(phone=LANDLORD_PHONE),
        )
        assert second["customer_outcome"] == customers_services.OUTCOME_CREATED
        assert second["customer_reused"] is False
        assert _numbers() == ["C-00001", "C-00002"], "a phone must not reuse a number"

    # And the unit-level rule says the same thing without a database.
    phone_only = identity_match.IdentityEvidence(
        name=LANDLORD, kind=identity_match.KIND_PERSON, phone=LANDLORD_PHONE
    )
    assert identity_match.creation_minimum(phone_only) is None, "a phone CREATES"
    assert "phone" not in identity_match.REUSE_ID_FIELDS[identity_match.KIND_PERSON]


# ═══════════════════════════════════════════════════════════════════════════
# TC-4 · a company reuses on its Tax ID, and neither kind borrows the other's
# ═══════════════════════════════════════════════════════════════════════════
def test_tc4_a_company_reuses_on_its_tax_id(brazos, marcus):
    with tenant_ctx(brazos):
        block = {
            "display_name": COMPANY,
            "kind": identity_match.KIND_COMPANY,
            "identity": {"tax_id": COMPANY_TAX_ID},
        }
        first = _open_master(
            marcus, _building(marcus, brazos, address="7 Rio Verde Way", owner=COMPANY),
            customer=block,
        )
        second = _open_master(
            marcus, _building(marcus, brazos, address="9 Rio Verde Way", owner=COMPANY),
            customer=block,
        )
        assert first["customer_no"] == second["customer_no"] == "C-00001"
        assert second["customer_outcome"] == customers_services.OUTCOME_LINKED
        assert customers_models.Customer.objects.filter(display_name=COMPANY).count() == 1

    assert identity_match.REUSE_ID_FIELDS[identity_match.KIND_COMPANY] == ("tax_id",)
    assert "tax_id" not in identity_match.REUSE_ID_FIELDS[identity_match.KIND_PERSON]


# ═══════════════════════════════════════════════════════════════════════════
# TC-5 · a name alone never reuses — `A. Kulkarni` is not `Ajinkya Kulkarni`
# ═══════════════════════════════════════════════════════════════════════════
def test_tc5_a_name_alone_never_reuses_a_number():
    """`CR-056` §4's own paragraph, asserted rather than described."""
    name_only = identity_match.IdentityEvidence(
        name=LANDLORD, kind=identity_match.KIND_PERSON
    )
    assert identity_match.reuse_candidate(name_only)["customer"] is None
    no_kind = identity_match.IdentityEvidence(name=LANDLORD, ssn=LANDLORD_SSN)
    assert identity_match.reuse_candidate(no_kind)["customer"] is None


# ═══════════════════════════════════════════════════════════════════════════
# TC-6 · TWO customers agreeing refuses to pick, and still saves
# ═══════════════════════════════════════════════════════════════════════════
def test_tc6_two_matching_customers_refuse_to_be_picked_between(brazos, marcus):
    """PO 2026-09-01: *a duplicate identifier refuses to LINK and never refuses
    to SAVE*. There is deliberately no unique index on `ssn_bidx`, so two rows
    CAN hold one identifier — a clerk who mistypes a digit must still be able to
    open the account. Choosing the older one would be a coin toss."""
    with tenant_ctx(brazos):
        # Two rows reach one identifier the only way they can: a phone creates
        # the second, and the Social Security number is filled onto it after.
        _open_master(
            marcus, _building(marcus, brazos, address="40 Cedar St"),
            customer=_person_block(ssn=LANDLORD_SSN),
        )
        duplicate = customers_models.Customer.objects.create(
            tenant_id=customers_models.Customer.objects.first().tenant_id,
            customer_no="C-09999",
            kind=identity_match.KIND_PERSON,
            display_name=LANDLORD,
        )
        identity_match.set_identifier(duplicate, "ssn", LANDLORD_SSN)
        duplicate.save()

        evidence = identity_match.IdentityEvidence(
            name=LANDLORD, kind=identity_match.KIND_PERSON, ssn=LANDLORD_SSN
        )
        answer = identity_match.reuse_candidate(evidence)
        assert answer["customer"] is None, "two agreeing rows must not be picked between"
        assert answer["ambiguous"] is True
        assert len(answer["candidates"]) == 2

        # ...and the account still opens, under a number of its own.
        opened = _open_master(
            marcus, _building(marcus, brazos, address="41 Cedar St"),
            customer=_person_block(ssn=LANDLORD_SSN),
        )
        assert opened["customer_outcome"] == customers_services.OUTCOME_CREATED
        assert opened["customer_no"] not in ("C-00001", "C-09999")


# ═══════════════════════════════════════════════════════════════════════════
# TC-7 · **A REUSED NUMBER CARRIES NO TIER AND MOVES NO MONEY**
# ═══════════════════════════════════════════════════════════════════════════
def test_tc7_a_reused_number_carries_no_tier_and_moves_no_money(brazos, marcus):
    """The assertion that goes RED on the tidy-up this rule invites.

    Reuse and recognition now both answer *this is the same party*, so unifying
    them reads like housekeeping. It is not: `BR-CUS-089` is signed and needs a
    date of birth for a person, and the **$153.50** of `WE-7`/`GT-23` — $150.00
    principal plus $3.50 interest — may not follow a name and an SSN alone.
    """
    with tenant_ctx(brazos):
        _open_master(
            marcus, _building(marcus, brazos, address="50 Birch St"),
            customer=_person_block(ssn=LANDLORD_SSN),
        )
        second = _open_master(
            marcus, _building(marcus, brazos, address="51 Birch St"),
            customer=_person_block(ssn=LANDLORD_SSN),
        )
        assert second["customer_outcome"] == customers_services.OUTCOME_LINKED

        links = customers_models.CustomerAccount.objects.filter(
            account_id=second["id"]
        )
        assert links.count() == 1
        assert links.first().match_tier is None, "a reuse may never store a tier"
        assert links.first().match_confirmed_by_id is None

        # With the date of birth as well it IS strong, and THAT is the signed
        # test — the difference is one fact and it is the fact that moves money.
        third = _open_master(
            marcus, _building(marcus, brazos, address="52 Birch St"),
            customer=_person_block(ssn=LANDLORD_SSN, date_of_birth=LANDLORD_DOB),
        )
        assert third["customer_no"] == second["customer_no"]


# ═══════════════════════════════════════════════════════════════════════════
# TC-8 · **NO IDENTIFIER, NO ACCOUNT** — and nothing is written
# ═══════════════════════════════════════════════════════════════════════════
def test_tc8_a_name_with_no_identifier_opens_no_account_at_all(brazos, marcus):
    """PO 2026-09-01: *"Without identifier we cannot create Customer ID or
    master account ot regular account"*, superseding that morning's *"a person
    standing at the counter who will not give an identifier still gets their
    water"*.

    ⚠ **THE ASSERTION IS THAT NO ACCOUNT ROW EXISTS, not that an exception was
    raised.** An assertion about an exception passes on a silent half-write, and
    a half-written account with no customer is the exact state `CR-056` §4 found
    on every Master Account in the product.
    """
    with tenant_ctx(brazos):
        before = customers_models.Account.objects.count()
        premises = _building(marcus, brazos, address="60 Walnut St")

        with pytest.raises(errors.BizError) as caught:
            _open_master(marcus, premises)  # the free-text owner name, alone
        assert caught.value.br_ref == "BR-CUS-1024"
        assert customers_models.Account.objects.count() == before
        assert customers_models.Customer.objects.count() == 0

        # The ordinary door too, and the name arrives in the CONTACT — which is
        # where both wizards put it, and would otherwise have been the way past.
        unit = _ordinary_unit(marcus, brazos, address="61 Walnut St")
        with pytest.raises(errors.BizError):
            customers_services.create_account(
                marcus,
                {
                    "unit_id": str(unit["id"]),
                    "account_type": "residential",
                    "status": "active",
                    "opened_at": "2026-07-01",
                    "contact": {"full_name": LANDLORD},
                },
            )
        assert customers_models.Account.objects.count() == before

        # A phone is enough, and that is what keeps the counter workable.
        opened = customers_services.create_account(
            marcus,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
                "contact": {"full_name": LANDLORD},
                "customer": _person_block(phone=LANDLORD_PHONE),
            },
        )
        assert opened["customer_no"] == "C-00001"


# ═══════════════════════════════════════════════════════════════════════════
# TC-9 · the refusal names what is missing, in a clerk's words
# ═══════════════════════════════════════════════════════════════════════════
def test_tc9_the_refusal_names_the_missing_thing_and_carries_no_rule_id(brazos, marcus):
    """B14 rule 32 clause 4 — no rule id and no internal code in clerk copy.
    The rule id rides in `br_ref`, which is where a payload's machinery goes."""
    cases = {
        identity_match.MISSING_KIND: {"display_name": LANDLORD},
        identity_match.MISSING_IDENTIFIER: {
            "display_name": LANDLORD, "kind": identity_match.KIND_PERSON
        },
    }
    for missing, block in cases.items():
        with pytest.raises(errors.BizError) as caught:
            customers_services.refuse_account_without_identity(block)
        exc = caught.value
        assert exc.params["missing"] == missing
        assert "BR-" not in exc.message_key
        assert exc.message_key.startswith("customers.account.")

    # A company is told about its Tax ID and never about a driving licence.
    with pytest.raises(errors.BizError) as caught:
        customers_services.refuse_account_without_identity(
            {"display_name": COMPANY, "kind": identity_match.KIND_COMPANY}
        )
    assert caught.value.message_key == "customers.account.identity_required_company"

    # NO name presented at all is the PO's third row and raises nothing.
    assert customers_services.refuse_account_without_identity({}) is None
    assert customers_services.refuse_account_without_identity(None) is None
    # ── the legacy-reference carve-out, BOTH ways round ────────────────────
    # ⛔ **A REFERENCE ONLY CARVES OUT WHERE IT RESOLVES, AND THIS CASE USED TO
    # ASSERT THE OPPOSITE.** It passed any `external_ref` — including one this
    # tenant has never seen — because the check read *was a reference sent*
    # while its own comment claimed *a reference that resolves* (hard-won law 1).
    # Found by putting the tenant seed through the rule instead of around it:
    # every seeded row carries a customer key, so all 48 would have taken the
    # exit and proved nothing.
    with tenant_ctx(brazos):
        unknown = customers_models.Customer.objects.filter(external_ref="CUST-118").count()
        assert unknown == 0, "the fixture must not already hold this reference"
        with pytest.raises(errors.BizError) as caught:
            customers_services.refuse_account_without_identity(
                {"display_name": LANDLORD, "external_ref": "CUST-118"}
            )
        assert caught.value.br_ref == "BR-CUS-1024"

        # The same reference, once it names a row that EXISTS, is an
        # identification and passes — which is the carve-out doing its job.
        unit = _ordinary_unit(marcus, brazos, address="70 Sycamore St")
        customers_services.create_account(
            marcus,
            {
                "unit_id": str(unit["id"]),
                "account_type": "residential",
                "status": "active",
                "opened_at": "2026-07-01",
                "contact": {"full_name": LANDLORD},
                "customer": {
                    "display_name": LANDLORD,
                    "kind": identity_match.KIND_PERSON,
                    "external_ref": "CUST-118",
                    "identity": {"phone": LANDLORD_PHONE},
                },
            },
        )
        assert customers_models.Customer.objects.filter(external_ref="CUST-118").exists()
        assert (
            customers_services.refuse_account_without_identity(
                {"display_name": LANDLORD, "external_ref": "CUST-118"}
            )
            is None
        )


# ═══════════════════════════════════════════════════════════════════════════
# TC-10 · what is already on file stays lawful
# ═══════════════════════════════════════════════════════════════════════════
def test_tc10_customers_already_on_file_with_no_identifier_stay_readable(brazos, marcus):
    """The ruling governs what is WRITTEN from now on and invalidates nothing —
    no migration, no backfill, and no read path refuses to serve one."""
    from apps.customers import selectors

    with tenant_ctx(brazos):
        # The only way such a row can be made now is before the rule can see it
        # — which is exactly the state every customer created before 2026-09-01
        # is in, and the state the ruling says stays lawful.
        legacy = customers_models.Customer.objects.create(
            tenant_id=brazos.id,
            customer_no="C-00404",
            kind=identity_match.KIND_PERSON,
            display_name="Pre-ruling Persson",
        )
        detail = selectors.customer_detail(legacy.id)
        assert detail is not None, "a customer with no identifier must still be readable"
        assert detail["customer_no"] == "C-00404"

        # ...and it is invisible to the reuse test rather than refused by it:
        # nothing to agree about is not the same as a row that may not be used.
        evidence = identity_match.IdentityEvidence(
            name="Pre-ruling Persson", kind=identity_match.KIND_PERSON, ssn=LANDLORD_SSN
        )
        assert identity_match.reuse_candidate(evidence)["customer"] is None

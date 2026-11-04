# ── Trace ──────────────────────────────────────────────
# Change:  `BR-CUS-1081` — the transfer's buyer carries what an account needs.
# Ruling:  PO 2026-09-20, having walked the wizard in the live product, verbatim:
#          *"step 2 dont allow to take kYC documents - DOB, all detaisl we need
#          to create account - Similar to Move in request we will need all
#          details for account"* — and, when told a backend lane would be
#          needed, *"we have it - we have created it for service request move
#          in - use it"*.
# Rules:   BR-CUS-1081 (this) · BR-CUS-1030 (the reassignment; the buyer must be
#          identifiable) · BR-CUS-1023 (name + one identifier is the MINIMUM) ·
#          BR-CUS-1022 (a company is not asked a person's questions) ·
#          BR-CUS-1020 (identity lives in ONE place) · BR-CUS-089 (money moves
#          only on a `strong` match: name + date of birth + one government ID) ·
#          BR-CUS-019 (the duplicate check is ADVISORY) · BR-CUS-045 (contacts
#          are PII) · CLAUDE.md hard rule 1 (tenant scoping) · hard rule 7
#          (every money action audits) · hard rule 8 (an address lives on
#          `premises`; `customers.addresses` `kind='mailing'` is the ONE named
#          exception) · law 2 (built is not wired) · law 7 (prove it RED first)
# Screens: S89 — the Transfers tab and its five-step wizard, `TRF-02.2`.
# ───────────────────────────────────────────────────────
"""`BR-CUS-1081` — what the buyer carries, and where each piece of it lands.

WHY THIS FILE IS WRITTEN AS A DIFFERENCE
-----------------------------------------
Until 2026-09-20 a transfer's buyer carried **a name, a kind and one
identifier** and nothing else. A buyer became the customer of record on a
telephone number: no date of birth, so no match could ever be `strong`; no
mailing address, so a landlord's bill had nowhere to go; and an email the wizard
had been putting on the wire since the step was built, which the validator
silently dropped.

So the strongest cases here are the ones that would have passed on yesterday's
code and must fail on it:

  * `date_of_birth` reaches `customers` and makes a returning buyer a MATCH
    instead of a second customer number;
  * the buyer's email and phone reach `contacts` instead of the floor;
  * a mailing address reaches `customers.addresses` `kind='mailing'` **and no
    other table**;
  * the clerk is told, BEFORE the commit, whether they are about to reuse a
    customer or create one.

THE REUSE IS ITSELF UNDER TEST, AND THAT IS THE POINT OF §1
------------------------------------------------------------
The PO's second sentence — *"we have it … use it"* — is a requirement about
HOW, not only about what. `transfers.BUYER_CAPTURE_FIELDS` is derived from
`service_request_service.CAPTURE_FIELDS` and `_capture_vocabulary()` refuses to
answer if the two have drifted. §1 asserts the derivation, and asserts the guard
FIRES — a guard that cannot fail is hard-won law 7's second shape and is worth
less than no guard at all.

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
⚠ **QUOTED FROM RUNS THIS SUITE ACTUALLY PRODUCED, NOT RECONSTRUCTED.**

* The drift guard was shown red by removing `date_of_birth` from
  `CAPTURE_FIELDS` in a live interpreter before the suite existed::

      RuntimeError: transfers.BUYER_CAPTURE_NAMES has drifted from
      service_request_service.CAPTURE_FIELDS: date_of_birth is no longer
      captured there.

* Every case in §3 and §4 was run against the PRE-CHANGE `_validated_buyer` by
  calling it with the new block; it returned a dict with no `capture` key::

      KeyError: 'capture'

  which is the honest failure — the field did not exist rather than arriving
  empty.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from apps.customers import identity_match
from apps.customers import models as customers_models
from apps.customers import selectors as customers_selectors
from apps.customers import service_request_service as sr
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,
    brazos,
    lonestar,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

SELLER_NAME = "Alvarez, Marisol"
SELLER_PHONE = "+1-555-0101"
BUYER_NAME = "Okafor, Chidi"
BUYER_DOB = "1984-03-11"
BUYER_SSN = "111-22-3333"

#: The buyer as the SHIPPED wizard sends them — the shape four sibling lanes are
#: live on today. Every case that uses this proves the widening did not break it.
BUYER_AS_SHIPPED = {
    "display_name": BUYER_NAME,
    "kind": "person",
    "identity": {"phone": "+1-555-0188"},
    "email": "chidi.okafor@example.invalid",
}

#: The buyer as `BR-CUS-1081` allows — the capture set's own spelling.
BUYER_FULL = {
    "applicant_name": BUYER_NAME,
    "applicant_kind": "person",
    "applicant_email": "chidi.okafor@example.invalid",
    "applicant_phone": "+1-555-0188",
    "preferred_language": "es",
    "ssn": BUYER_SSN,
    "date_of_birth": BUYER_DOB,
    "mailing_address": {
        "line1": "PO Box 4120",
        "city": "Austin",
        "state": "TX",
        "postal_code": "78704",
    },
}


def _plan(tenant, name="Residential Standard", service_code="electric"):
    """`test_cr058_w4`'s helper verbatim — a second spelling of *what a billable
    unit needs* is how two suites start disagreeing about it."""
    service = tenancy_models.Service.objects.get(code=service_code)
    plan, _ = rating_models.RatePlan.objects.get_or_create(
        tenant=tenant,
        name=name,
        defaults={"code": name.lower().replace(" ", "-"), "status": "published"},
    )
    tariff, _ = rating_models.Tariff.objects.get_or_create(
        tenant=tenant, name=f"{name} — {service_code}", service=service
    )
    rating_models.PlanRateSchedule.objects.get_or_create(
        tenant=tenant, rate_plan=plan, service=service, defaults={"tariff": tariff}
    )
    return plan


def _sold_account(actor, tenant, *, label="1408 Elm Street", with_contact=True):
    """The account about to be sold, with the SELLER's contact and mailing row.

    ⚠ **THE SELLER HAS A MAILING ADDRESS, AND THAT IS NOT DECORATION.** The case
    that matters is a buyer's bill going to the person who sold the house, and it
    can only be proved on an account that already has somewhere for a bill to go.
    """
    premises = make_premises(actor, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label=label)
    metering_services.assign_unit_plan(actor, unit["id"], {"tariff_id": str(_plan(tenant).id)})
    metering_services.ensure_service_point(unit["id"], "electric")
    payload = {
        "unit_id": str(unit["id"]),
        "account_type": "residential",
        "status": "active",
        "opened_at": "2026-07-01",
        "customer": {
            "display_name": SELLER_NAME,
            "kind": "person",
            "identity": {"phone": SELLER_PHONE},
        },
        "addresses": [
            {
                "kind": "mailing",
                "line1": "77 Seller Lane",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
            }
        ],
    }
    if with_contact:
        payload["contact"] = {
            "full_name": SELLER_NAME,
            "email": "marisol.alvarez@example.invalid",
            "phone": SELLER_PHONE,
        }
    account = customers_services.create_account(actor, payload)
    return customers_models.Account.objects.get(id=account["id"])


def _sell(actor, account, *, buyer, sold_on="2026-09-01"):
    """The five steps, through the same functions the wizard's one POST runs."""
    started = transfers.start_transfer(actor, {"from_account_id": str(account.id)})
    transfers.set_new_customer(actor, started["id"], {"customer": buyer})
    transfers.set_sale_date(actor, started["id"], {"sold_on": sold_on})
    transfers.acknowledge_money(actor, started["id"])
    return transfers.reassign_account(actor, started["id"], {"customer": buyer})


# ═══════════════════════════════════════════════════════════════════════════
# 1 · THE REUSE ITSELF — *"we have it … use it"* IS A REQUIREMENT ABOUT HOW
# ═══════════════════════════════════════════════════════════════════════════


def test_the_buyers_set_is_a_subset_of_the_requests_and_not_a_second_list():
    """`BR-CUS-1081` — the PO named the move-in request as the source.

    ⚠ **THIS IS THE ASSERTION THAT WOULD HAVE CAUGHT A COPY-PASTE.** A lane that
    typed eleven field names into `transfers.py` would pass every behavioural
    case in this file and fail only here — and would then drift the first time
    `CAPTURE_FIELDS` gained or lost one.
    """
    assert transfers.BUYER_CAPTURE_FIELDS <= sr.CAPTURE_FIELDS
    assert transfers.BUYER_CAPTURE_FIELDS == frozenset(transfers.BUYER_CAPTURE_NAMES)
    # The eleven, named, so a silent shrink is visible in the diff of this file.
    assert sorted(transfers.BUYER_CAPTURE_FIELDS) == [
        "applicant_email",
        "applicant_kind",
        "applicant_name",
        "applicant_phone",
        "co_applicant_email",
        "co_applicant_name",
        "co_applicant_phone",
        "date_of_birth",
        "drivers_licence",
        "preferred_language",
        "ssn",
    ]


def test_the_drift_guard_actually_fires(monkeypatch):
    """Hard-won law 7 — **prove a guard RED before trusting it green**, and
    law 7's habit 2: *ask what would make this check pass wrongly.*

    The obvious spelling of `BUYER_CAPTURE_FIELDS` is
    `CAPTURE_FIELDS & <names>`, and it is the wrong one: an intersection
    SHRINKS SILENTLY. A capture set that quietly stops carrying a date of birth
    is a match that quietly stops being strong, and **every other case in this
    file would still pass.** So the guard raises, and this asserts it does.
    """
    monkeypatch.setattr(sr, "CAPTURE_FIELDS", sr.CAPTURE_FIELDS - {"date_of_birth"})
    with pytest.raises(RuntimeError) as caught:
        transfers._capture_vocabulary()
    assert "date_of_birth" in str(caught.value)
    assert "CAPTURE_FIELDS" in str(caught.value)


def test_the_clerks_set_is_the_parent_and_not_the_guests():
    """The load-bearing distinction the capture file warns about twice.

    `PORTAL_CAPTURE_FIELDS` deliberately omits `ssn`, `date_of_birth` and
    `drivers_licence` — *"a guest on the portal is not a clerk at a counter"*.
    **A transfer buyer is captured by a CLERK**: every door onto a sale is
    `@require_role(SYSTEM_ADMIN, BILLING_CLERK)` and there is no guest path onto
    one anywhere in this product. So the identity three are IN.

    ⚠ **THE GUEST HALF WAS NARROWED ON 2026-10-02 FROM THREE FIELDS TO TWO,
    AND THIS IS NOT A PRIVACY WIDENING.** `c669697ff` (`DEF-CWP-9046`) put
    `date_of_birth` in `PORTAL_CAPTURE_FIELDS`, and this case went red. It was
    checked as a possible privacy defect and is not one, on three signed facts:

      * the portal application ASKS for a date of birth by design —
        `US-CWP-013` §1 (*"Name, person or business, email, mobile, **date of
        birth**, and the date service should start"*) and `BR-CWP-031`
        (CONFIRMED: *"Enrolment must not match on date of birth; application
        matching may, because a person decides"*). Before `c669697ff` the
        portal already took it onto the draft and threw it away at Send;
      * a date of birth is NOT a government identifier — `BR-CUS-1020`: *"The
        date of birth is a plain `date` and deliberately so"*, and `BR-CUS-092`
        names two identifiers, of which it is not one;
      * it is stored once, on the request, read by the clerk's Applicant tab;
        the draft's copy is still blanked at Send and the applicant is told
        nothing about a match (`US-CWP-013` TC-2).

    **The two GOVERNMENT identifiers stay out of the guest's set**, and that is
    the half of this distinction that protects anybody: a public form must
    never accept a Social Security number or a driving licence.
    """
    assert {"ssn", "date_of_birth", "drivers_licence"} <= transfers.BUYER_CAPTURE_FIELDS
    assert not ({"ssn", "drivers_licence"} & sr.PORTAL_CAPTURE_FIELDS)
    # Asserted, not merely tolerated: the day it leaves, the portal is throwing
    # away what US-CWP-013 asks the applicant to type (DEF-CWP-9046 again).
    assert "date_of_birth" in sr.PORTAL_CAPTURE_FIELDS


def test_the_pick_fields_are_refused_because_a_sale_already_knows_its_premises():
    """`PICK_FIELDS`' own note, applied. A transfer's premises is the one the
    account sits on and never moves (`BR-CUS-1030`); accepting a pick would let
    a caller point a sale at a building it is not about."""
    assert not (sr.PICK_FIELDS & transfers.BUYER_CAPTURE_FIELDS)


def test_the_mailing_vocabulary_is_the_write_doors_own():
    """Derived from `services.ADDRESS_FIELDS`, never retyped — so the buyer's
    block and the door that writes it cannot disagree about a column.

    ⚠ **`line2` AND `country` ARE ABSENT AND THAT IS THE DOOR'S GAP, CARRIED
    HONESTLY** (`DEF-CUS-5942`): both are real columns since `customers 0039`
    and `ADDRESS_FIELDS` was never widened, so the only write door for a mailing
    address cannot set either. This asserts the gap rather than papering over
    it, and it goes green the day the door gains them.
    """
    assert transfers._mailing_vocabulary() == frozenset(customers_services.ADDRESS_FIELDS) - {
        "kind"
    }
    assert "kind" not in transfers._mailing_vocabulary()


# ═══════════════════════════════════════════════════════════════════════════
# 2 · WHAT IS REQUIRED — THREE, AND THE RULING ADDED NONE
# ═══════════════════════════════════════════════════════════════════════════


def test_the_three_required_facts_are_still_exactly_three(brazos, marcus):
    """`BR-CUS-1030` — a name, a kind, one identifier. Nothing the 2026-09-20
    ruling added is compulsory, because the PO named the move-in request as the
    benchmark and every added field is optional there."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ApiError):
            transfers._validated_buyer({"applicant_kind": "person", "ssn": BUYER_SSN})
        with pytest.raises(errors.ApiError):
            transfers._validated_buyer({"applicant_name": BUYER_NAME, "ssn": BUYER_SSN})
        with pytest.raises(errors.BizError):
            transfers._validated_buyer(
                {"applicant_name": BUYER_NAME, "applicant_kind": "person"}
            )
        # …and the minimum still passes, with nothing else at all.
        block = transfers._validated_buyer(
            {"applicant_name": BUYER_NAME, "applicant_kind": "person", "ssn": BUYER_SSN}
        )
        assert block["capture"] == {}
        assert block["mailing_address"] is None
        assert block["date_of_birth"] is None


def test_a_buyer_with_no_date_of_birth_is_accepted_and_told_what_it_costs(brazos, marcus):
    """**The judgment, asserted rather than described.**

    A date of birth is what makes `BR-CUS-089`'s match `strong`, and a strong
    match is what lets a deposit carry. Requiring one would refuse a genuine
    first-time buyer who has nothing on file to match against — so it is
    optional, and the shortfall is NAMED instead.
    """
    with tenant_ctx(brazos):
        seller = _sold_account(marcus, brazos)
        # Somebody on file who looks related: same name, no shared government id.
        customers_services.link_customer(
            account_id=seller.id,
            display_name=BUYER_NAME,
            kind="person",
            identity={"ssn": BUYER_SSN},
            actor=marcus,
        )
        preview = transfers.preview_buyer(
            marcus,
            {
                "customer": {
                    "applicant_name": BUYER_NAME,
                    "applicant_kind": "person",
                    "ssn": BUYER_SSN,
                }
            },
        )
        match = preview["buyer_match"]
        assert match["verdict"] in ("matched", "candidates")
        if match["verdict"] == "candidates":
            # ⛔ THE HALF THAT MAKES IT ACTIONABLE: the clerk is one question
            # away from a reuse instead of a duplicate, and is told which one.
            assert "date_of_birth" in match["missing_for_strong"]


def test_a_company_is_not_asked_a_persons_questions(brazos, marcus):
    """`BR-CUS-1022`, through the REQUEST's own guard rather than a copy of its
    table — so the sale and the application refuse the same field on the same
    day and in the same words."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError) as caught:
            transfers._validated_buyer(
                {
                    "applicant_name": "Ridge Coffee Co.",
                    "applicant_kind": "company",
                    "identity": {"tax_id": "88-7654321"},
                    "date_of_birth": "1984-03-11",
                }
            )
        assert caught.value.br_ref == "BR-CUS-1022"


# ═══════════════════════════════════════════════════════════════════════════
# 3 · WHERE EACH CAPTURED FACT LANDS — AND ON WHAT IT DOES **NOT**
# ═══════════════════════════════════════════════════════════════════════════


def test_the_transfers_row_gains_no_column_for_any_of_it(brazos, marcus):
    """`BR-CUS-1020` — identity lives in ONE place, and a workflow table is not
    it. The `set_new_customer` docstring's *"validates and stores nothing"* now
    covers eleven fields rather than five, so this asserts the absence.

    ⚠ **AND NO ADDRESS COLUMN ANYWHERE** — CLAUDE.md hard rule 8. `G85` fails a
    fourth home; this proves the sale gives it nothing to find.
    """
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        _sell(marcus, account, buyer=BUYER_FULL)
        columns = {
            field.attname
            for field in transfers.Transfer._meta.get_fields()
            if hasattr(field, "attname")
        }
        # ⚠ **`state` IS DELIBERATELY NOT IN THIS LIST, AND THE FIRST DRAFT PUT
        # IT THERE AND WENT RED.** `transfers.state` is the job's own
        # `scheduled | in_progress | done | cancelled` and has nothing to do
        # with an address. A guard that fails on a legitimate column is a guard
        # somebody deletes, so the names below are the ones that could ONLY
        # mean a second home for an address or an identity.
        for forbidden in (
            "ssn",
            "date_of_birth",
            "drivers_licence",
            "applicant_email",
            "applicant_phone",
            "preferred_language",
            "line1",
            "line2",
            "city",
            "postal_code",
            "country",
            "mailing_address",
        ):
            assert forbidden not in columns, f"transfers grew a {forbidden} column"


def test_the_date_of_birth_reaches_the_customer_and_makes_a_match_possible(
    brazos, marcus
):
    """`BR-CUS-089`'s MIDDLE CLAUSE, which a sale could not supply until today.

    ⚠ **THIS IS THE CASE THAT WOULD HAVE PASSED ON YESTERDAY'S CODE IF IT ONLY
    ASSERTED "a customer exists".** It asserts the DATE, on the customer row,
    because that is the fact that was being thrown away.
    """
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        row = _sell(marcus, account, buyer=BUYER_FULL)
        buyer = customers_models.Customer.objects.get(
            id=row["reassignment"]["to_customer_id"]
        )
        assert buyer.date_of_birth == date.fromisoformat(BUYER_DOB)


def test_the_buyers_email_and_phone_reach_the_contact_row(brazos, marcus):
    """`DEF-CUS-5941` — the wizard has sent `customer.email` since the step was
    built and `_validated_buyer` dropped it on the floor.

    ⚠ **AND THE CONTACT WAS THE SELLER'S.** `TransferWizard.tsx`'s own review
    step says *"Autopay and the bill email stay the seller's"* — an accurate
    description of a product that hands over a house and goes on emailing the
    bill to the person who sold it.
    """
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        before = customers_models.Contact.objects.get(account=account, deleted_at__isnull=True)
        assert before.email == "marisol.alvarez@example.invalid"  # the seller's
        row = _sell(marcus, account, buyer=BUYER_FULL)
        after = customers_models.Contact.objects.get(account=account, deleted_at__isnull=True)
        assert after.email == BUYER_FULL["applicant_email"]
        assert after.phone == BUYER_FULL["applicant_phone"]
        assert after.full_name == BUYER_NAME
        assert after.dob == date.fromisoformat(BUYER_DOB)
        assert "contact" in row["buyer_carried"]["written"]


def test_a_sale_is_not_refused_because_the_account_never_had_a_contact(brazos, marcus):
    """`update_account_contact` is a CORRECTION path and refuses an account with
    no contact row — right for a PATCH, and **wrong as a reason to roll back a
    property sale.** A buyer must not lose a house because a row nobody ever
    created is missing, so the absence is reported and the sale completes."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos, with_contact=False)
        customers_models.Contact.objects.filter(account=account).delete()
        row = _sell(marcus, account, buyer=BUYER_FULL)
        assert row["reassignment"]["to_customer_name"] == BUYER_NAME
        assert transfers.GAP_CONTACT_NOT_WRITTEN in row["buyer_carried"]["not_written"]


def test_the_preferred_language_reaches_the_account(brazos, marcus):
    """`BR-CUS-064` — the account's own column, written through
    `services.update_account` rather than by this module."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        _sell(marcus, account, buyer=BUYER_FULL)
        account.refresh_from_db()
        assert account.preferred_language == "es"


# ═══════════════════════════════════════════════════════════════════════════
# 4 · THE MAILING ADDRESS — HARD RULE 8's ONE NAMED EXCEPTION
# ═══════════════════════════════════════════════════════════════════════════


def test_the_buyers_mailing_address_lands_on_addresses_and_nowhere_else(brazos, marcus):
    """CLAUDE.md hard rule 8: an address lives on `premises` **except**
    `customers.addresses` `kind='mailing'` — *"where the BILL goes, which for a
    landlord is another building"*.

    ⚠ **READ BACK THROUGH THE PRINT SEAM, NOT OFF THE ROW.**
    `selectors.mailing_address_for_account` is what a print vendor is actually
    handed (`BR-NOT-029`(a)), so asserting there proves the envelope changed
    rather than that a row exists somewhere.
    """
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        before = customers_selectors.mailing_address_for_account(account.id)
        assert before["line1"] == "77 Seller Lane"  # the seller's
        row = _sell(marcus, account, buyer=BUYER_FULL)
        after = customers_selectors.mailing_address_for_account(account.id)
        assert after["line1"] == "PO Box 4120"
        assert after["city"] == "Austin"
        assert after["missing"] == []
        assert "mailing_address" in row["buyer_carried"]["written"]
        # ⛔ NOT A FOURTH HOME: the RETIRED `kind='service'` cannot arrive here.
        assert not customers_models.Address.objects.filter(
            account=account, kind="service"
        ).exists()


def test_no_mailing_address_means_the_service_address_and_the_sellers_row_goes(brazos, marcus):
    """⊕ **T3, PO 2026-09-23 (`DEF-CUS-6393`) — THIS CASE READ THE OPPOSITE.**
    It asserted *"without a buyer's address the account keeps the one it had —
    the SELLER's"*, with `mailing_address_unchanged` stated. The PO ruled the
    seller's mailing row does not survive the sale: with no buyer's mailing
    address the row is REMOVED and bills go to the service address. Nothing is
    guessed (`BR-NOT-029`(a)) — the service address is the premises', walked
    to, never copied (hard rule 8)."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        row = _sell(marcus, account, buyer=BUYER_AS_SHIPPED)
        assert "mailing_address_removed" in row["buyer_carried"]["written"]
        assert "mailing_address_unchanged" not in {gap["code"] for gap in row["unavailable"]}
        assert not customers_models.Address.objects.filter(
            account=account, kind="mailing", deleted_at__isnull=True
        ).exists()
        assert (
            customers_selectors.mailing_address_for_account(account.id)["line1"]
            != "77 Seller Lane"
        )


def test_a_mailing_block_with_no_first_line_is_refused(brazos, marcus):
    """An address with no first line is not a place — and the write door reads
    an empty `line1` as *remove the row*, which is not what a clerk who typed a
    town meant."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            transfers._validated_buyer(
                {**BUYER_FULL, "mailing_address": {"city": "Austin", "state": "TX"}}
            )


def test_an_unknown_mailing_field_is_refused_by_name(brazos, marcus):
    """The door's vocabulary, and no wider. A caller sending `kind` is refused
    — `kind='service'` is RETIRED (`BR-MET-1161`) and cannot arrive even as a
    typo."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.ValidationError):
            transfers._validated_buyer(
                {**BUYER_FULL, "mailing_address": {"line1": "X", "kind": "service"}}
            )


# ═══════════════════════════════════════════════════════════════════════════
# 5 · THE MATCH, TOLD BEFORE THE COMMIT AND NOT AFTER IT
# ═══════════════════════════════════════════════════════════════════════════


def test_the_preview_tells_a_clerk_they_are_about_to_create_a_customer(brazos, marcus):
    """The conformance walk of 2026-09-20: *"the match happens on the server at
    commit and the clerk is never told whether they are about to create a new
    customer or reuse one."*"""
    with tenant_ctx(brazos):
        preview = transfers.preview_buyer(marcus, {"customer": BUYER_FULL})
        assert preview["buyer_match"]["verdict"] == "none"
        assert preview["buyer_match"]["will_create"] is True
        assert preview["buyer_match"]["matched"] is None


def test_the_preview_tells_a_clerk_they_are_about_to_reuse_one(brazos, marcus):
    """`BR-CUS-1024` — *match first, created only on no match* — stated back
    about THIS buyer before the sale rather than discovered after it."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        customers_services.link_customer(
            account_id=account.id,
            display_name=BUYER_NAME,
            kind="person",
            identity={"ssn": BUYER_SSN, "date_of_birth": BUYER_DOB},
            actor=marcus,
        )
        preview = transfers.preview_buyer(marcus, {"customer": BUYER_FULL})
        assert preview["buyer_match"]["verdict"] == "matched"
        assert preview["buyer_match"]["will_create"] is False
        assert preview["buyer_match"]["tier"] == "strong"
        assert preview["buyer_match"]["basis"]


def test_the_preview_never_says_create_about_a_customer_the_clerk_named(brazos, marcus):
    """`DEF-CUS-5974` — **the preview must model `link_customer`, not the
    matcher.**

    `link_customer` resolves, in this order: a customer the caller NAMED, then a
    quoted customer number, then `identity_match.recognise`, then a legacy
    `external_ref`. A preview that ran only the third step answered
    `will_create: true` about a buyer the commit was about to REUSE — the exact
    wrong answer this door exists to prevent, told with confidence.

    ⚠ **IT WAS FOUND BY ASKING *WHAT WOULD MAKE THIS PASS WRONGLY*, NOT BY A
    FAILING TEST** (hard-won law 7, habit 2): the shipped wizard sends neither
    key, so every case written against that screen was green and stayed green.

    ⚠ **AND THE VERDICT IS `named`, NOT `matched`.** Nothing was recognised —
    the clerk pointed. Reporting a `strong` tier here would claim evidence
    agreed when none was weighed, and `BR-CUS-089`'s tier is what moves money.
    """
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        link = customers_services.link_customer(
            account_id=account.id,
            display_name="Ferraro, L.",
            kind="person",
            identity={"phone": "+1-555-0177"},
            external_ref="LEGACY-4471",
            actor=marcus,
        )
        # Named by id — a buyer whose evidence matches NOTHING, so the matcher
        # alone would say "create". The fixture is only meaningful that way.
        by_id = transfers.preview_buyer(
            marcus, {"customer": {**BUYER_FULL, "customer_id": link["id"]}}
        )
        assert by_id["buyer_match"]["will_create"] is False
        assert by_id["buyer_match"]["verdict"] == "named"
        assert by_id["buyer_match"]["matched"] == str(link["id"])
        # ⛔ NOT A TIER. Nothing was weighed.
        assert by_id["buyer_match"]["tier"] is None

        # Named by the legacy reference — the fourth branch, same conclusion.
        by_ref = transfers.preview_buyer(
            marcus, {"customer": {**BUYER_FULL, "external_ref": "LEGACY-4471"}}
        )
        assert by_ref["buyer_match"]["will_create"] is False
        assert by_ref["buyer_match"]["matched"] == str(link["id"])

        # …and a reference belonging to NOBODY falls through to the matcher
        # rather than claiming a reuse — the mirror error.
        unknown = transfers.preview_buyer(
            marcus, {"customer": {**BUYER_FULL, "external_ref": "LEGACY-NOBODY"}}
        )
        assert unknown["buyer_match"]["will_create"] is True

        # ⚠ **A HALF-TYPED ID IS NOT RECOGNISED, NEVER A 500.** A screen may
        # call this on every keystroke, so an id that is not yet a UUID must
        # fall through to the matcher instead of breaking the step. Django
        # raises before the query runs, so without the guard this is a crash.
        half_typed = transfers.preview_buyer(
            marcus, {"customer": {**BUYER_FULL, "customer_id": "01a0bca6-b8a3"}}
        )
        assert half_typed["buyer_match"]["will_create"] is True


def test_the_preview_writes_absolutely_nothing(brazos, marcus):
    """⚠ **THE PROPERTY THAT MAKES IT SAFE TO CALL ON EVERY KEYSTROKE.** A
    preview that started a transfer would leave an `in_progress` row that
    `uq_transfers_open_from` then uses to refuse every future sale of that
    account — and no screen lists a transfer in flight, so nobody could find it
    to cancel.

    Counted before and after: transfers, customers, accounts and audit rows.
    """
    with tenant_ctx(brazos):
        _sold_account(marcus, brazos)
        counts = (
            transfers.Transfer.objects.count(),
            customers_models.Customer.objects.count(),
            customers_models.CustomerAccount.objects.count(),
            customers_models.Address.objects.count(),
        )
        transfers.preview_buyer(marcus, {"customer": BUYER_FULL})
        transfers.preview_buyer(marcus, {"customer": BUYER_AS_SHIPPED})
        assert (
            transfers.Transfer.objects.count(),
            customers_models.Customer.objects.count(),
            customers_models.CustomerAccount.objects.count(),
            customers_models.Address.objects.count(),
        ) == counts


def test_the_preview_refuses_exactly_what_the_commit_refuses(brazos, marcus):
    """**A preview that accepted a block the commit rejects is worse than no
    preview**, because a clerk would trust it. Both run `_validated_buyer`."""
    with tenant_ctx(brazos):
        with pytest.raises(errors.BizError):
            transfers.preview_buyer(
                marcus,
                {"customer": {"applicant_name": BUYER_NAME, "applicant_kind": "person"}},
            )


def test_step_two_carries_the_match_as_well(brazos, marcus):
    """`set_new_customer` answers it too, for the service-layer caller that does
    not go through the preview door."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        row = transfers.set_new_customer(marcus, started["id"], {"customer": BUYER_FULL})
        assert row["buyer_match"]["verdict"] == "none"
        assert row["buyer_capture_presented"] == [
            "applicant_email",
            "applicant_phone",
            "date_of_birth",
            "preferred_language",
        ]
        assert row["buyer_mailing_presented"] is True


# ═══════════════════════════════════════════════════════════════════════════
# 6 · WHAT STILL WORKS, AND WHAT IS STATED RATHER THAN DROPPED
# ═══════════════════════════════════════════════════════════════════════════


def test_the_shipped_wizard_payload_still_sells_a_property(brazos, marcus):
    """⚠ **FOUR SIBLING LANES ARE LIVE ON `TransferWizard.tsx` TODAY.** A door
    that stopped taking `display_name` would break a screen in the middle of
    their work for a cosmetic gain, so both spellings are accepted and the
    capture one is canonical."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        row = _sell(marcus, account, buyer=BUYER_AS_SHIPPED)
        assert row["reassignment"]["to_customer_name"] == BUYER_NAME
        assert row["reassignment"]["account_no"] == account.account_no
        # …and the email it has always sent is no longer dropped.
        contact = customers_models.Contact.objects.get(
            account=account, deleted_at__isnull=True
        )
        assert contact.email == BUYER_AS_SHIPPED["email"]


def test_a_co_applicant_is_stored_as_the_accounts_second_contact(brazos, marcus):
    """⊕ **T4, PO 2026-09-23 (`DEF-CUS-6391`) — THIS CASE READ THE OPPOSITE.**
    It asserted the co-applicant was *"captured, refused, and NAMED"* under
    `OQ-CUS-12514`. The PO answered it: *"a) Store a second person on the
    account (name, email, phone), shown on the account page"*. So it lands as
    the account's non-primary contact, and the account page shows it."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        row = _sell(
            marcus,
            account,
            buyer={**BUYER_FULL, "co_applicant_name": "Okafor, Ada"},
        )
        assert "co_applicant" in row["buyer_carried"]["written"]
        second = customers_models.Contact.objects.get(
            account=account, is_primary=False, deleted_at__isnull=True
        )
        assert second.full_name == "Okafor, Ada"


def test_none_of_it_crosses_a_tenant(brazos, lonestar, marcus):
    """CLAUDE.md hard rule 1. A buyer who is a customer of ANOTHER tenant is a
    stranger here — and the preview is a search of the customer register, so a
    leak would be an identity oracle rather than a stray row."""
    # ⚠ **THE CUSTOMER IS BUILT DIRECTLY AND NOT THROUGH AN ACCOUNT, ON
    # PURPOSE.** The question is about the CUSTOMER REGISTER — a preview is a
    # search of it — so the other tenant needs a customer and needs nothing
    # else. Opening an account there would also need `electric` enabled on
    # `lonestar`, which it is not, and a scoping case that fails in SETUP on a
    # service lookup proves nothing about scoping.
    with tenant_ctx(lonestar):
        stranger = customers_models.Customer.objects.create(
            tenant=lonestar,
            display_name=BUYER_NAME,
            kind="person",
            date_of_birth=date.fromisoformat(BUYER_DOB),
        )
        # `set_identifier` writes the keyed BLIND INDEX as well as the
        # ciphertext — a row written without it is invisible to the matcher for
        # the wrong reason, and the case would pass while proving nothing.
        identity_match.set_identifier(stranger, "ssn", BUYER_SSN)
        stranger.save()
        # The fixture is only worth anything if the matcher CAN see this row
        # from inside its own tenant. Proved here, so a green case in `brazos`
        # means scoping and not an unfindable row.
        assert identity_match.recognise(
            identity_match.from_payload(
                {"name": BUYER_NAME, "ssn": BUYER_SSN, "date_of_birth": BUYER_DOB},
                kind="person",
            )
        )["matched"] == str(stranger.id)
    with tenant_ctx(brazos):
        preview = transfers.preview_buyer(marcus, {"customer": BUYER_FULL})
        assert preview["buyer_match"]["verdict"] == "none"
        assert preview["buyer_match"]["candidates"] == []


def test_every_write_on_this_path_leaves_an_audit_row(brazos, marcus):
    """CLAUDE.md hard rule 7. The doors audit themselves; this asserts the sale
    as a whole leaves the trail, and that **no identifier is in it**
    (`BR-CUS-092`(c): the full value is never in an audit `details` blob)."""
    with tenant_ctx(brazos):
        account = _sold_account(marcus, brazos)
        row = _sell(marcus, account, buyer=BUYER_FULL)
        blob = str(row)
        assert BUYER_SSN not in blob
        assert row["buyer_carried"]["written"]

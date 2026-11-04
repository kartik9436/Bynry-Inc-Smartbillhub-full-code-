# ── Trace ──────────────────────────────────────────────
# Change:   CR-059 · CS-27 (task 51) — *"Let a master pay its units' bills —
#           the sub-metering core case"*. Built SECOND, on CS-12: *"Build CS-12
#           first; this extends it rather than repeating it."*
# Story:    US-PAY-001 · US-PAY-006   Screens: S22 · S35 · S21 · S33 · P6
# Rules:    BR-PAY-1129 (a master may pay a bill on a unit of its own premises,
#           and the authority is recorded on the payment; a payer who is not the
#           account holder is never assumed) · BR-PAY-1130 (money a master pays
#           that no unit bill absorbs returns to the MASTER's credit, never to a
#           unit account's) · BR-PAY-1126..1128 (CS-12's three, which this
#           inherits unchanged) · BR-CUS-068 · BR-CUS-171 · BR-CUS-055 ·
#           CLAUDE.md rule 1 · rule 4 · rule 5 · rule 7
# Ruling:   PO 2026-09-01 — a master **may always** pay a unit's bill (*"anyone
#           may pay any bill; the tenant's agreement is not required"*), and
#           paying it gives the master sight of that bill. So the authority
#           check is a RELATIONSHIP check, not a consent check.
#           PO 2026-09-01 — a bounced master tender is chased on the TENANT's
#           own account: *"If acocunt is will Utility , utility will chase it
#           and apply penalty"*.
# Tests:    this file
# ───────────────────────────────────────────────────────
"""A LANDLORD PAYS FOR THE BLOCK — CR-059 CS-27, shape C.

THE FIGURES, WHICH ARE THE CHANGE REQUEST'S OWN
================================================
    owner's cheque #9931, master ACC-9001 (A. Rowe)               742.60
      ACC-1042  J. Ilori                                          184.20
      ACC-1043  M. Okonjo                                         156.90
      ACC-1044  R. Vance                                          212.60
      ACC-1045  D. Chaudhry                                       188.90
                                                                  ------
                                                                  742.60
    and the master's OWN hallway bill, untouched by it              69.60

THE THREE SHAPES, AND ONLY ONE IS NEW
======================================
  **A** the master's own bill (hallway light, car park) — **already works**.
  **B** the owner holds every unit account — **that is CS-12's problem**.
  **C** the master pays its TENANTS' bills — **had NO CONCEPT AT ALL**, and it
        is what this file tests. C looks like B and behaves quite differently,
        because the landlord and the tenants are not the same customer.

WHERE THE PAYMENT ENTRY LANDS IS NOT A MATTER OF TASTE
=======================================================
Model 1: a real payment entry on **each unit account**, annotated with the
payer; the **master carries the TENDER and NO payment entry**, except money
deliberately left as its own credit. Three signed rules force it and
`test_cs27__the_master_carries_the_tender_and_no_payment_entry` is where that is
pinned, so the next lane cannot "simplify" the payment onto the master and
credit a debt the master never had while four bills stay open.

THE RED PROOF, RUN BEFORE ANY OF THIS WAS TRUSTED GREEN (hard-won law 7)
=========================================================================
  * With `_refuse_unless_the_payer_may_pay` made a no-op,
    `test_cs27__a_unit_on_another_building_is_refused` fails with
    `DID NOT RAISE PaymentRuleError` — and a landlord pays a stranger's bill on
    a building they have nothing to do with, which is the *"nobody checks the
    payer may pay"* CS-27 lists as the worst of what goes wrong today.
  * With `_refuse_a_tenant_holding_the_landlords_money` made a no-op,
    `test_cs27__a_part_bigger_than_the_unit_owes_is_refused` fails the same way
    and **15.80 of the landlord's money lands as J. Ilori's credit**, where it
    auto-applies to that tenant's next bill.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from apps.customers import models as customer_models
from apps.customers import selectors as customer_selectors
from apps.customers import services as customer_services
from apps.metering import services as metering_services
from apps.payments import models, premises_position, tender_models, tenders
from apps.payments.exceptions import PaymentRuleError

from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import make_plan, make_premises, make_unit, tenant_ctx
from tests.test_us_pay_001_record_payment import an_issued_bill, journal_legs

pytestmark = pytest.mark.django_db

# ── CS-27's own worked scenario ────────────────────────────────────────────
CHEQUE = Decimal("742.60")
ILORI = Decimal("184.20")
OKONJO = Decimal("156.90")
VANCE = Decimal("212.60")
CHAUDHRY = Decimal("188.90")
HALLWAY = Decimal("41.20")
IRRIGATION = Decimal("28.40")
MASTERS_OWN_BILL = HALLWAY + IRRIGATION  # 69.60

CHEQUE_NO = "9931"
PAID_ON = datetime(2026, 8, 8, 10, 0, tzinfo=UTC)
ISSUED_ON = date(2026, 8, 1)
OPENED = date(2026, 8, 1)

TENANTS = (
    ("J. Ilori", ILORI),
    ("M. Okonjo", OKONJO),
    ("R. Vance", VANCE),
    ("D. Chaudhry", CHAUDHRY),
)


#: `BR-CUS-1024` (PO 2026-09-01) — *"Customer ID - minimum name and one ID"*.
#: A person needs a name AND one of SSN, driving licence or phone before an
#: account will open at all, so every tenant below carries a distinct phone.
#: Without it `create_account` refuses with `customers.account.identity_kind_
#: required` and this file's nine money cases never reach the rule under test.
_PHONES = {
    "J. Ilori": "+1 (402) 555-1042",
    "M. Okonjo": "+1 (402) 555-1043",
    "R. Vance": "+1 (402) 555-1044",
    "D. Chaudhry": "+1 (402) 555-1045",
    "P. Nwosu": "+1 (402) 555-1099",
}


def _occupying_account(actor, unit, *, name):
    """An ACTIVE ordinary account on `unit` — a tenant, not a draft.

    `create_account` opens a DRAFT and BR-CUS-018 says a draft derives no
    occupancy, so activation is a deliberate second step here exactly as it is
    in the product.
    """
    created = customer_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "opened_at": OPENED.isoformat(),
            "contact": {"full_name": name},
            # BR-CUS-1024's creation minimum — see `_PHONES` above. It is a
            # NESTED `customer` block and not two top-level keys, which is the
            # shape `customers.sample_data._account_payload` sends and therefore
            # the shape the product itself uses.
            "customer": {
                "display_name": name,
                "kind": "person",
                "identity": {"phone": _PHONES[name]},
            },
            "addresses": [{"kind": "mailing", "line1": "12 Oak St", "city": "Katy", "state": "TX"}],
        },
    )
    customer_services.activate_account(actor, created["id"])
    return customer_models.Account.objects.get(pk=created["id"])


def a_building_with_four_let_units_and_a_master(actor, tenant):
    """CS-27's fixture: one premises, one master, four let units, one bill each.

    The owner is DECLARED (`link_owner_master_account`, BR-MET-400) rather than
    inferred from who pays for the hallway — the geometric derivation was
    retired by the PO's ruling of 2026-08-27 (*"Premises -> owner = Master
    account"*, DEF-650), and a fixture built the old way would test a path the
    product no longer has.
    """
    from apps.metering import premises_owners

    plan = make_plan(tenant, name="Small Commercial", services=["water"])
    premises = make_premises(
        actor,
        address_line="12 Oak St",
        premises_type="apartment_complex",
        owner_manager="Rowe Property LLC",
        services_available=["water"],
    )
    common = make_unit(
        actor,
        premises["id"],
        label="Hallway",
        unit_type="common_area",
        is_common_area=True,
        services=["water"],
    )
    metering_services.assign_unit_plan(
        actor, common["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
    )
    # `BR-CUS-1114` (PO 2026-10-02) — a master account needs a building of two
    # or more HOMES at the moment it is raised, so the four flats are made
    # first and let below (the order used to be master, then flats).
    homes = []
    for index in range(1, len(TENANTS) + 1):
        home = make_unit(actor, premises["id"], label=f"Unit {index}", services=["water"])
        metering_services.assign_unit_plan(
            actor, home["id"], {"tariff_id": str(plan.id), "effective_from": "2025-01-01"}
        )
        homes.append(home)
    master = customer_services.create_master_account(
        actor,
        {
            "premises_id": premises["id"],
            "account_type": "commercial",
            "opened_at": OPENED.isoformat(),
            # `BR-CUS-1024` again, and the COMPANY half of it: a landlord is a
            # company, so the creation minimum is a name AND its Tax ID (a
            # phone is enough only for a person). ⚠ **A free-text
            # `owner_manager` on the premises is a NAME and not an identity** —
            # that is the exact case the PO was asked about and closed on
            # 2026-09-01, so the master door refuses without this block and
            # every money case in this file would never reach its own rule.
            "customer": {
                "display_name": "Rowe Property LLC",
                "kind": "company",
                "identity": {"tax_id": "84-2201993"},
            },
        },
    )
    # ⚠ `create_master_account` answers a DICT, not a model — it is the API
    # door's own payload. Everything below wants the ACCOUNT (a bill hangs off
    # it, and the payments seam takes its pk), so it is read back once here
    # rather than being juggled as two shapes through the rest of the fixture.
    master = customer_models.Account.objects.get(pk=master["id"])
    premises_owners.link_owner_master_account(actor, premises["owner"]["id"], master.id)

    units, accounts = [], []
    for index, (name, owed) in enumerate(TENANTS, start=1):
        unit = homes[index - 1]
        account = _occupying_account(actor, unit, name=name)
        an_issued_bill(
            tenant, account, number=f"BL-2608-00104{index}", total=owed, issued_on=ISSUED_ON
        )
        units.append(unit)
        accounts.append(account)

    # Shape A, so the tests can prove it is untouched: the master's OWN bill.
    an_issued_bill(
        tenant, master, number="BL-2608-009001", total=MASTERS_OWN_BILL, issued_on=ISSUED_ON
    )
    return premises, master, accounts


def the_owners_cheque(accounts, *, amounts=None, total=CHEQUE, token=None):
    amounts = amounts or [owed for _, owed in TENANTS]
    return dict(
        parts=tuple(
            tenders.TenderPart(account_id=account.pk, amount=amount)
            for account, amount in zip(accounts, amounts, strict=True)
        ),
        amount=total,
        posted_at=PAID_ON,
        cleared_at=PAID_ON,
        method_code="check",
        reference=CHEQUE_NO,
        submission_key=token or str(uuid.uuid4()),
    )


# ══ THE HEADLINE · MODEL 1, AND THE THREE RULES THAT FORCE IT ══════════════


def test_cs27__the_master_carries_the_tender_and_no_payment_entry(brazos, dana):
    """**742.60 settles FOUR TENANTS' bills. The master's balance does not move.**

    CS-27's three reasons, each visible as an assertion below:
      (i)  a payment carries one mandatory account, so settling a unit's bill
           REQUIRES a payment row on the unit's account — four payments;
      (ii) the receivable that falls is the UNIT's — put the payment on the
           master and you credit a debt the master never had while four bills
           stay open;
      (iii) the master genuinely does not owe this money — a payment there would
           create a credit balance beside four unpaid bills.
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana, payer_account_id=str(master.id), **the_owners_cheque(accounts)
        )

        assert result.created is True
        assert result.scope == tender_models.TENDER_SCOPE_PREMISES
        assert result.authority == tender_models.AUTHORITY_PREMISES_OWNER_MASTER
        assert result.payer_account_id == str(master.id)

        # (i) FOUR payments, one per tenant account.
        recorded = models.Payment.objects.filter(tender_id=result.tender_id)
        assert recorded.count() == 4
        assert set(recorded.values_list("account_id", flat=True)) == {a.id for a in accounts}
        assert sum(p.amount for p in recorded) == CHEQUE

        # (iii) NO payment entry on the master. This is the assertion the next
        # lane's "simplification" would break, and it is why it is here.
        assert not models.Payment.objects.filter(account_id=master.id).exists(), (
            "CS-27 Model 1: the master carries the TENDER record and NO payment entry. A "
            "payment there would create a credit balance beside four unpaid bills."
        )

        # …and the master's own hallway bill is exactly where it was.
        from apps.payments import billing_seam

        own = billing_seam.open_invoices_for_account(master.id)
        assert sum(invoice.balance for invoice in own.invoices) == MASTERS_OWN_BILL

        # (ii) the receivables that FALL are the units'. One balanced pair per
        # part, and their debits sum to the cheque (CS-12's own ruling that
        # three — here four — balanced entries are not an error).
        legs = journal_legs(brazos)
        debits = sum(amount for _, side, amount in legs if side == "debit")
        credits = sum(amount for _, side, amount in legs if side == "credit")
        assert debits == credits == CHEQUE


def test_cs27__each_tenants_payment_is_annotated_with_the_payer(brazos, dana):
    """*"a real payment entry against their bill, annotated with who paid it,
    which is exactly what a tenant asking 'has my landlord paid my water?' needs
    to see."*

    The annotation is ONE join from the row the tenant's own account carries —
    the payer and the authority live on the tender and are not copied onto
    `payments`, so the two can never drift (hard-won law 5).
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        result = tenders.record_multi_account_payment(
            dana, payer_account_id=str(master.id), **the_owners_cheque(accounts)
        )
        payment = models.Payment.objects.filter(account_id=accounts[0].id).get()
        assert payment.tender_id is not None
        assert str(payment.tender.payer_account_id) == str(master.id)
        assert payment.tender.authority == tender_models.AUTHORITY_PREMISES_OWNER_MASTER
        assert payment.tender.premises_id is not None
        assert payment.confirmation == CHEQUE_NO
        assert result.parts[0].credit_carried == Decimal("0")


# ══ BR-PAY-1129 · THE AUTHORITY CHECK NOBODY HAD ═══════════════════════════


def test_cs27__a_unit_on_another_building_is_refused(brazos, dana):
    """⛔ **Today *"nobody checks the payer may pay — there is no bill-to and no
    responsible party anywhere."*** This is that check.

    It is a RELATIONSHIP check (PO 2026-09-01): the master may always pay a unit
    of its OWN building, and this account is not in it.
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        elsewhere = make_premises(
            actor=dana,
            address_line="40 Cedar Ave",
            premises_type="single_family",
            owner_manager="Somebody Else LLC",
            services_available=["water"],
        )
        other_unit = make_unit(dana, elsewhere["id"], label="House", services=["water"])
        # `BR-CUS-019` — activation refuses a unit with no plan
        # (`customers.account.plan_required_at_activation`), so the stranger's
        # house needs one exactly as the four flats do. Without it this case
        # dies in its own setup and never reaches the authority rule.
        other_plan = make_plan(brazos, name="House Water", services=["water"])
        metering_services.assign_unit_plan(
            dana,
            other_unit["id"],
            {"tariff_id": str(other_plan.id), "effective_from": "2025-01-01"},
        )
        stranger = _occupying_account(dana, other_unit, name="P. Nwosu")
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                payer_account_id=str(master.id),
                parts=(tenders.TenderPart(account_id=stranger.pk, amount=Decimal("50.00")),),
                amount=Decimal("50.00"),
                posted_at=PAID_ON,
                cleared_at=PAID_ON,
                submission_key=str(uuid.uuid4()),
            )
    assert caught.value.br_ref == "BR-PAY-1129"
    assert str(stranger.pk) in str(caught.value)
    assert models.Payment.objects.count() == 0


def test_cs27__an_ordinary_account_is_not_a_payer_for_a_building(brazos, dana):
    """An ordinary account pays its own bills. A landlord paying a block is a
    MASTER account holding the building's common areas (BR-CUS-068), and the
    refusal says so rather than reporting an empty premises."""
    with tenant_ctx(brazos):
        _premises, _master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                payer_account_id=str(accounts[0].id),
                parts=(tenders.TenderPart(account_id=accounts[1].pk, amount=Decimal("10.00")),),
                amount=Decimal("10.00"),
                posted_at=PAID_ON,
                cleared_at=PAID_ON,
                submission_key=str(uuid.uuid4()),
            )
    assert caught.value.br_ref == "BR-PAY-1129"
    assert "master account" in str(caught.value)


# ══ BR-PAY-1130 · A TENANT MUST NOT HOLD THEIR LANDLORD'S MONEY ═══════════


def test_cs27__a_part_bigger_than_the_unit_owes_is_refused_whole(brazos, dana):
    """⛔ **CS-27's second-worst thing: *"An overpayment becomes a TENANT's
    credit — the landlord's money, on a different person's account, and it will
    auto-apply to their next bill."***

    Worked: **200.00 against `ACC-1042`, which owes 184.20 → 15.80 of the
    landlord's money would sit as J. Ilori's credit.** Refused whole, with the
    figure named and the lawful home stated.
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        with pytest.raises(PaymentRuleError) as caught:
            tenders.record_multi_account_payment(
                dana,
                payer_account_id=str(master.id),
                parts=(tenders.TenderPart(account_id=accounts[0].pk, amount=Decimal("200.00")),),
                amount=Decimal("200.00"),
                posted_at=PAID_ON,
                cleared_at=PAID_ON,
                submission_key=str(uuid.uuid4()),
            )
        message = str(caught.value)
        assert caught.value.br_ref == "BR-PAY-1130"
        assert "15.80" in message and "master" in message
        # Nothing partial commits — not even the allocation that DID meet the bill.
        assert models.Payment.objects.count() == 0
        assert tender_models.PaymentTender.objects.count() == 0


# ⚠ **THE `xfail(strict=True)` THAT STOOD HERE IS RETIRED — THE HOLD EXPIRED ON
# 2026-09-16 AND THIS TEST IS WHAT NOTICED (`DEF-2334`, CLOSED).**
#
# It read: *"DEF-2334 — a payment on a MASTER account cannot post at all. `CR-056`
# W1 changed `create_master_account` to write `premises_id` and leave `unit_id`
# NULL, and `apps/ledger/dimension_seam._unit_of` resolves the UNIT first and the
# premises FROM the unit — so it answers `account_is_not_in_the_customer_register`
# for every master and `posting.post()` refuses atomically. Nothing had ever paid a
# master, so no suite went red."* It then named its own expiry condition: **"it is
# `strict` on purpose: it turns GREEN the day the seam reads `accounts.premises_id`
# directly, and it fails loudly if anybody 'fixes' it by moving the leftover onto a
# tenant instead."**
#
# That day is today. `dimension_seam._anchor_of` (the renamed `_unit_of`) now reads
# both anchors and `location_for_account` returns the premises directly for an
# address-anchored account (`DEF-LED-5459`, lane C wave 1), so this case passes on
# its own terms — the leftover lives on the master, which is what `CS-27` requires.
# The marker is REMOVED rather than flipped to non-strict: a strict xfail that
# XPASSes is a failing suite, and leaving it would have made the repair look like a
# regression to the next lane.
#
# ⚠ **THIS IS HARD-WON LAW 2'S SECOND HALF WORKING EXACTLY AS WRITTEN** — *"when you
# write a hold, write the test that fires when the hold expires, in the same commit"*.
# Nobody went looking for `DEF-2334`; a money path in another module was repaired for
# an unrelated reason and this test put its hand up in the same run. It is the only
# thing in the suite that did.
def test_cs27__the_leftover_lives_on_the_master_and_that_is_lawful(brazos, dana):
    """*"one payment entry only for money deliberately left over, carried as the
    master's own credit, because a leftover has to live somewhere and the only
    lawful home is the payer's account."*

    ⛔ **XFAIL ON `DEF-2334`, WHICH THIS CASE FOUND.** See the marker above: the
    master cannot take a payment at all today, for a reason that has nothing to
    do with this rule and everything to do with a master having no unit.

    The landlord hands over 762.60 for 742.60 of tenants' bills and puts the
    extra 20.00 on their own account. Five payments: four tenants and one on the
    master, which is the ONE exception to *"no payment entry on the master"*.
    """
    extra = Decimal("20.00")
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        parts = tuple(
            tenders.TenderPart(account_id=account.pk, amount=owed)
            for account, (_name, owed) in zip(accounts, TENANTS, strict=True)
        ) + (
            tenders.TenderPart(
                account_id=master.pk, amount=MASTERS_OWN_BILL + extra, order="oldest_first"
            ),
        )
        result = tenders.record_multi_account_payment(
            dana,
            payer_account_id=str(master.id),
            parts=parts,
            amount=CHEQUE + MASTERS_OWN_BILL + extra,
            posted_at=PAID_ON,
            cleared_at=PAID_ON,
            reference=CHEQUE_NO,
            submission_key=str(uuid.uuid4()),
        )
        assert len(result.parts) == 5
        masters_payment = models.Payment.objects.get(account_id=master.id)
        assert masters_payment.amount == MASTERS_OWN_BILL + extra
        # Its own hallway bill is settled and the 20.00 is the MASTER's credit —
        # never a tenant's.
        assert result.parts[4].credit_carried == extra


# ══ THE PREMISES READ A CLERK AIMS AT ══════════════════════════════════════


def test_cs27__the_premises_read_shows_the_building_unit_by_unit(brazos, dana):
    """The list `GET /accounts/{id}/premises-position` serves — four let units,
    who occupies each, what each owes, and `may_pay` on every row.

    The master's own 69.60 is served BESIDE the units and never summed into
    them: they are two different people's money, and adding them would tell a
    clerk the tenants owe more than they do.
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        body = premises_position.premises_payment_position(payer_account_id=str(master.id))

    assert Decimal(body["units_total_open"]) == CHEQUE
    assert Decimal(body["payer"]["own_total_open"]) == MASTERS_OWN_BILL
    occupied = [unit for unit in body["units"] if unit["accounts"]]
    assert len(occupied) == 4
    assert all(row["may_pay"] is True for unit in occupied for row in unit["accounts"])
    assert {row["customer_name"] for unit in occupied for row in unit["accounts"]} == {
        name for name, _ in TENANTS
    }
    # The hallway is listed with no occupant — a real measured fact, and CS-27's
    # case B: an empty or common unit is on the OWNER's own bill, not nobody's.
    assert any(unit["is_common_area"] and not unit["accounts"] for unit in body["units"])


def test_cs27__the_tenant_is_owed_a_sentence_and_the_read_says_so(brazos, dana):
    """⚠ **FOLLOWS FROM THE PO's RULING OF 2026-09-01 AND IS OWED TO A PERSON.**

    Paying a unit's bill gives the master sight of that bill including its
    usage. CS-27: *"Tell the tenant it happens — at sign-up or on the bill — so
    it is a policy rather than a discovery."* No screen exists yet, so the fact
    rides on `problems` where a surface cannot silently drop it.
    """
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        body = premises_position.premises_payment_position(payer_account_id=str(master.id))
        assert "master_can_see_the_units_bills" in {p["code"] for p in body["problems"]}
        result = tenders.record_multi_account_payment(
            dana, payer_account_id=str(master.id), **the_owners_cheque(accounts)
        )
        assert "master_can_see_the_units_bills" in {p["code"] for p in result.problems}


def test_cs27__the_customers_seam_answers_none_for_an_ordinary_account(brazos, dana):
    """`premises_scope_for_account` is the published B1 seam, and its two
    absences are different returns on purpose: `None` means *not a master*, and
    an empty `units` list means *a master with nothing occupied*. A caller that
    could not tell them apart would refuse a lawful payment for the wrong
    reason."""
    with tenant_ctx(brazos):
        _premises, master, accounts = a_building_with_four_let_units_and_a_master(dana, brazos)
        assert customer_selectors.premises_scope_for_account(accounts[0].id) is None
        scope = customer_selectors.premises_scope_for_account(master.id)
        assert scope is not None
        assert set(scope["account_ids"]) == {str(a.id) for a in accounts}


# ══ THE ROUTES RESOLVE ═════════════════════════════════════════════════════


def test_cs27__the_two_premises_routes_resolve_through_config_urls():
    """Hard-won law 2 with a URL. An endpoint no router mounts is a feature that
    does not exist, and every test that calls the SERVICE would still pass."""
    from django.urls import resolve

    from apps.payments import tenders_api

    assert resolve("/api/v1/accounts/abc/premises-payments").func is tenders_api.premises_payments
    assert (
        resolve("/api/v1/accounts/abc/premises-position").func is tenders_api.premises_position_view
    )

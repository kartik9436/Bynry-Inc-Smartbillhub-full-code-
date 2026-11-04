# ── Trace ──────────────────────────────────────────────
# Change:  CR-058 tasks 14–18 — a transfer REASSIGNS the account. This REVERSES
#          shipped behaviour, and the cases below are written as the difference
#          rather than as a fresh contract, so a reader can see what moved.
# Ruling:  PO 2026-09-01, verbatim: *"dont create new account - we reassing that
#          account - bascailly I have sold my property - so account get transfer
#          to new person or business; if I move to new location then it is new
#          Service request and we follow the process"* — and, the same day,
#          *"money follow property - new owner boutght everything property +
#          debt also"* (`OQ-1252`, raised and CLOSED within the hour).
# Rules:   BR-CUS-1030 (the reassignment — SUPERSEDES CR-030 W7's built
#          behaviour) · BR-CUS-1031 (a customer MOVING is a new Service
#          Request) · BR-CUS-1011 (one owner account per address — task 17) ·
#          BR-CUS-1023 / BR-CUS-1022 (the buyer must be identifiable) ·
#          BR-CUS-054 (the customer link) · CLAUDE.md hard rule 4
#          (financial immutability) · hard rule 5 (only the ledger posts) ·
#          hard rule 7 (every money action audits) · law 7 (prove it RED first)
# Screens: S89 — the Transfers tab and its wizard
# ───────────────────────────────────────────────────────
"""CR-058 W4 — the same account, a new owner, an unbroken ledger.

WHAT THIS FILE MEASURES, AND WHY IT IS WRITTEN AS A DIFFERENCE
--------------------------------------------------------------
`apps/customers/transfers.py` did the OPPOSITE of the ruling on both halves
until 2026-09-01: it ran `move_out` on one account and `create_account` at a new
unit, in one commit. So the strongest cases here are the NEGATIVE ones —

    the account is not closed · no second account exists · the account number is
    unchanged · the unit is unchanged · no journal line is written · no refund
    is raised

— because each of those was TRUE of the product yesterday and must be false
today. A test that only asserted *"the customer changed"* would pass on the old
code too, which had a `CustomerAccount` write in it.

⚖️ **AND THE MONEY: THE DEBT FOLLOWS THE PROPERTY.** The buyer takes the
property and what it owes. That is nearly free here precisely BECAUSE the
account is reassigned: an account carries its own ledger, so **the balance never
moves, because the thing it sits on never moves.** `balance_at_sale` is asserted
to be the figure that was there before AND still there after — one number, two
readings, no movement.

WHAT WAS PROVED RED FIRST (r11 step 2d, hard-won law 7)
--------------------------------------------------------
⚠ **QUOTED FROM RUNS THIS SUITE ACTUALLY PRODUCED, NOT RECONSTRUCTED.**

* **Seventeen of these cases failed at once** on the first full run, all with the
  same refusal, because the fixture's unit carried no plan (`BR-MET-040`) and an
  account cannot go active on it:

      E       core.errors.BizError: BIZ-COMPLETENESS
              (customers.account.plan_required_at_activation)

  A suite that had been written to skip that would have proved nothing about
  selling a property.

* **Nine cases then failed on the reassignment's own read of `link_customer`.**
  The customer's id comes back as `id`; `customer_id` is `None` on every
  successful resolution, so the door refused every buyer it had just minted a
  number for:

      E       core.errors.BizError: BIZ-COMPLETENESS
              (customers.customer.identity_required_person)

  ⚠ **Worth reading twice: the refusal it produced was correct, well-worded and
  about the right subject** — *this person needs an identifier* — raised over a
  person who had just presented one. Nothing in the message said *the caller
  looked in the wrong place*.

* **Selling to the current owner was NOT refused**, and the reason is a signed
  rule rather than a bug:

      E       Failed: DID NOT RAISE BizError

  Typing the seller's own name and phone again creates a SECOND customer
  (`BR-CUS-089`: a phone alone is a weak match), so buyer and seller are
  different rows and there is nothing to detect. The case now passes the
  clerk's own `customer_id`, which is the only way this can be recognised for a
  person — and that limit is pinned in
  `test_cr058_w4__a_returning_PERSON_buyer_gets_a_second_number_and_that_is_the_signed_rules`.

* **The audit case read the capture sink as a function:**

      E       TypeError: 'list' object is not callable

**AND THE REVERSAL ITSELF WAS BROKEN DELIBERATELY.** With `reassign_account`
restored to the old `move_out` + `create_account` pair — the product as it stood
yesterday — the negative assertions are what bite, which is why they are written
as the strongest ones here:

      E       AssertionError: BR-CUS-1030: a sale reassigns ONE account. A
              second account is the behaviour the PO reversed.
      E       assert 2 == 1

**AND THE SCREEN HALF WAS PROVED RED IN A REAL BROWSER**, because no vitest
assertion can tell a rendered utility from a class name in the DOM (B14 rule 21 /
`DEF-974`). With `data-moving-is-a-service-request` removed from `TransfersTab`,
`10-scripts/render-checks/cr058-owner-import-and-sale.mjs` fails on the sentence
`CR-058` task 16 exists to put there.

WHAT IS DELIBERATELY *NOT* CHANGED, ASSERTED SO NOBODY BUILDS IT
-----------------------------------------------------------------
* **`premises.owner_id` does not move.** It is metering's typed party record and
  a separate fact from any account (B1). The response says so out loud rather
  than being silent, and `test_cr058_w4__the_premises_owner_record_is_named_as_
  not_updated` pins the sentence.
* **Nothing is prorated.** One unbroken account, one service agreement, one
  period. There is no split bill at a sale.
"""

from decimal import Decimal as D

import pytest

from apps.customers import models as customers_models
from apps.customers import services as customers_services
from apps.customers import transfers
from apps.metering import services as metering_services
from apps.rating import models as rating_models
from apps.tenancy import models as tenancy_models
from core import errors

from tests.br_cus_1114_fixtures import top_up_homes
from tests import identity_fixtures
from tests.test_us_met_helpers import *  # noqa: F401,F403 — shared fixtures
from tests.test_us_met_helpers import (  # noqa: F401
    audit_rows,  # noqa: F401 — autouse BE-03 capture sink
    brazos,
    make_premises,
    make_unit,
    marcus,
    tenant_ctx,
)

pytestmark = pytest.mark.django_db

#: The two parties, and the buyer's evidence. **A phone is enough for a person**
#: — the PO named it (`BR-CUS-1023`) — and it is deliberately the WEAKEST
#: identifier the rule accepts, so these cases prove the boundary rather than a
#: comfortable case well inside it.
SELLER_NAME = "Alvarez, Marisol"
#: The seller's own number, lifted out of `_sold_account` when the identity
#: moved into the account door (`BR-CUS-1024`). A `555-` line, reserved for
#: fiction, and the same posture `tests/identity_fixtures.py` takes.
SELLER_PHONE = "+1-555-0101"
BUYER_NAME = "Okafor, Chidi"
BUYER = {
    "display_name": BUYER_NAME,
    "kind": "person",
    "identity": {"phone": "+1-555-0188"},
}
#: What the seller still owes on the day of the sale. One figure, asserted
#: before and after, because *"the debt follows the property"* is exactly the
#: claim that it does not change.
ARREAR = D("284.6000")
DEPOSIT = D("150.0000")


def _plan(tenant, name="Residential Standard", service_code="electric"):
    """A published plan with a tariff for the service, `get_or_create`d.

    `test_w7_transfers`'s own helper, reused verbatim: a second spelling of
    "what a billable unit needs" is how two suites start disagreeing about it.
    """
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


def _sold_account(actor, tenant, *, arrear=ARREAR, deposit=DEPOSIT, label="1408 Elm Street"):
    """The account about to be sold, with a customer linked and money on it.

    ⚠ `deposit_on_file` and `balance` are written through the ORM and NOT
    through a service door, and that is the point rather than a shortcut:
    `services.REFUSED_FIELDS` refuses both on every client-facing path
    (`BR-CUS-023` — the deposit is a lookup; `BR-CUS-015` — the balance is the
    ledger's cache). A fixture that could set them through a door would mean the
    product had one.

    ⚠ **THE SELLER IS LINKED WITH AN IDENTIFIER, NOT WITH A NAME.** Since
    `BR-CUS-1023` a name alone mints no Customer #, so a fixture that passed
    only a name would produce an account with no customer and every case here
    would fail on `from_account_has_no_customer` rather than on its own subject.
    """
    premises = make_premises(actor, services_available=["electric"])
    unit = make_unit(actor, premises["id"], label=label)
    # ⚠ **THE UNIT NEEDS A PLAN AND A SERVICE POINT BEFORE AN ACCOUNT CAN GO
    # ACTIVE ON IT** — `BR-MET-040`, `customers.account.plan_required_at_
    # activation`. Without them every case here fails on a refusal that has
    # nothing to do with selling a property. `test_w7_transfers._unit`'s own
    # shape, reused rather than re-invented.
    metering_services.assign_unit_plan(
        actor, unit["id"], {"tariff_id": str(_plan(tenant).id)}
    )
    metering_services.ensure_service_point(unit["id"], "electric")
    account = customers_services.create_account(
        actor,
        {
            "unit_id": str(unit["id"]),
            "account_type": "residential",
            "status": "active",
            "opened_at": "2026-07-01",
            "contact": {"full_name": SELLER_NAME},
            # ⛔ **`BR-CUS-1024` (PO 2026-09-01) — THE SELLER IS IDENTIFIED AT
            # THE DOOR NOW, AND THE SEPARATE `link_customer` BELOW IS GONE
            # BECAUSE IT WAS THE SAME ACT DONE TWICE.** This fixture opened the
            # account with a name and no identifier — a refusal since that
            # ruling, in the SETUP of all eighteen cases — and then linked the
            # seller on the next line with exactly the block below. The door
            # does that link itself, so moving the identity INTO the payload
            # produces the identical row and one customer instead of two.
            #
            # The identifier is the phone this fixture already chose. It is
            # enough to mint a number, it is NOT one of `BR-CUS-1024`'s reuse
            # identifiers and NOT `BR-CUS-089`'s money test — so
            # `…a_returning_PERSON_buyer_gets_a_second_number…` still gets its
            # second number and `…a_returning_COMPANY_buyer…` still matches on
            # the Tax ID. Not one assertion in this file moved.
            "customer": {
                "display_name": SELLER_NAME,
                "kind": "person",
                "identity": {"phone": SELLER_PHONE},
            },
        },
    )
    customers_models.Account.objects.filter(id=account["id"]).update(
        deposit_on_file=deposit, balance=arrear
    )
    return (
        premises,
        unit,
        customers_models.Account.objects.get(id=account["id"]),
    )


def _sell(actor, account, *, buyer=None, sold_on="2026-09-01"):
    """The five steps, through the same functions the wizard's one POST runs."""
    started = transfers.start_transfer(actor, {"from_account_id": str(account.id)})
    transfers.set_new_customer(actor, started["id"], {"customer": buyer or BUYER})
    transfers.set_sale_date(actor, started["id"], {"sold_on": sold_on})
    transfers.acknowledge_money(actor, started["id"])
    return transfers.reassign_account(actor, started["id"], {"customer": buyer or BUYER})


# ═══════════════════════════════════════════════════════════════════════════
# TASK 14 — THE REVERSAL, ASSERTED AS THE DIFFERENCE IT IS
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w4__the_same_account_survives_the_sale(brazos, marcus):
    """`BR-CUS-1030` — one account before, the same one after.

    ⚠ **THE COUNT IS THE ASSERTION.** Yesterday this flow ended with TWO
    accounts; a test that only checked the customer had changed would have
    passed on that code too.
    """
    with tenant_ctx(brazos):
        _premises, unit, account = _sold_account(marcus, brazos)
        before = customers_models.Account.objects.count()
        row = _sell(marcus, account)
        assert customers_models.Account.objects.count() == before, (
            "BR-CUS-1030: a sale reassigns ONE account. A second account is the "
            "behaviour the PO reversed."
        )
        account.refresh_from_db()
        assert account.status.code == "active", (
            "BR-CUS-1030: the seller's account is not closed — the property was "
            "sold, the service was not stopped"
        )
        assert row["reassignment"]["account_no"] == account.account_no, (
            "BR-CUS-1030: the account number survives the sale. That is what a "
            'utility means by "the account transferred".'
        )
        assert str(account.unit_id) == str(unit["id"]), (
            "BR-CUS-1030: the UNIT does not change. A customer moving to a new "
            "address is a new Service Request (BR-CUS-1031), not this door."
        )
        assert row["reassignment"]["accounts_created"] == 0
        assert row["reassignment"]["account_closed"] is False


def test_cr058_w4__the_customer_is_the_thing_that_changes(brazos, marcus):
    """`BR-CUS-054` — one account, exactly one customer, and it is the buyer."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        seller_links = list(
            customers_models.CustomerAccount.objects.filter(account_id=account.id).values_list(
                "customer_id", flat=True
            )
        )
        assert len(seller_links) == 1
        row = _sell(marcus, account)
        # ⚠ **LIVE LINKS ONLY — `DEF-CUS-6428`.** Since `customers/0060` a sale
        # ENDS the seller's link rather than deleting it, so a bare `objects`
        # read counts the ended row too and this case had been red since
        # 927f82bb4 (2026-09-20) with nobody reading it.
        after = list(
            customers_models.CustomerAccount.objects.filter(
                account_id=account.id, ended_at__isnull=True
            ).values_list("customer_id", flat=True)
        )
        assert len(after) == 1, (
            "an account with two customers makes 'who owns this' ambiguous on "
            "every read. The seller's link is removed as part of the sale."
        )
        assert str(after[0]) != str(seller_links[0])
        assert str(after[0]) == row["reassignment"]["to_customer_id"]
        buyer = customers_models.Customer.objects.get(id=after[0])
        assert buyer.display_name == BUYER_NAME


def test_cr058_w4__a_returning_COMPANY_buyer_is_matched_and_gets_no_second_number(brazos, marcus):
    """`CR-058`'s governing ruling: *"we check whether we ahve mathicng customer
    ID, if yes, we use it if no we create it"*.

    A buyer the utility already knows becomes the account's customer under their
    EXISTING number. This module matches nothing itself; the assertion is that
    it goes through the door that does.

    ⚠ **A COMPANY, AND THE KIND IS LOAD-BEARING — READ THE CASE BELOW.**
    `tier_for` makes a company a `strong` match on **name + Tax ID**, which is
    what a buyer presents at a sale. A **person** needs **name + date of birth +
    one government ID** (`BR-CUS-089`), and no sale collects a date of birth.
    """
    with tenant_ctx(brazos):
        _p1, _u1, first = _sold_account(marcus, brazos, label="1408 Elm Street")
        _p2, _u2, second = _sold_account(marcus, brazos, label="22 Cedar Lane")
        company = {
            "display_name": "Okafor Holdings LLC",
            "kind": "company",
            "identity": {"tax_id": "84-7654321"},
        }
        _sell(marcus, first, buyer=company)
        _sell(marcus, second, buyer=company)
        buyers = {
            link.customer_id
            for link in customers_models.CustomerAccount.objects.filter(
                account_id__in=[first.id, second.id], ended_at__isnull=True
            )
        }
        assert len(buyers) == 1, (
            "one buyer, one Customer #, two properties. A second number here is "
            "the duplicate-party defect ruling 0 exists to close."
        )


def test_cr058_w4__a_returning_PERSON_buyer_gets_a_second_number_and_that_is_the_signed_rules(
    brazos, marcus
):
    """⚠ **THIS PINS A KNOWN LIMIT RATHER THAN A DESIRED BEHAVIOUR**, and it is
    here so the next lane finds it instead of discovering it.

    Two signed rules meet, and both are deliberate:

      * `BR-CUS-1023` — a **phone alone CREATES** a Customer #. The PO named it.
      * `BR-CUS-089` — a person is a `strong` match on **name + date of birth +
        one government ID** (PO 2026-08-25, closing `OQ-364`). A phone or an SSN
        **without a date of birth is a WEAK match**, and a weak match opens its
        own number rather than linking.

    CLAUDE.md states the trap in as many words: *"a lane that reconciles them
    either refuses a customer the PO said to create or moves **$150.00** on a
    telephone number."* **So Mr Okafor buying two properties ends with two
    Customer #s, and that is correct under the rules as signed.** A lane that
    "fixes" it by linking on a phone has reversed `BR-CUS-089` on a money path.

    What would change it: a date of birth collected at the sale. That is not
    ruled, so nothing here invents one. Recorded in the decision log of
    2026-09-01 with the same reasoning.
    """
    with tenant_ctx(brazos):
        _p1, _u1, first = _sold_account(marcus, brazos, label="1408 Elm Street")
        _p2, _u2, second = _sold_account(marcus, brazos, label="22 Cedar Lane")
        _sell(marcus, first)
        _sell(marcus, second)
        buyers = {
            link.customer_id
            for link in customers_models.CustomerAccount.objects.filter(
                account_id__in=[first.id, second.id], ended_at__isnull=True
            )
        }
        assert len(buyers) == 2, (
            "BR-CUS-089 needs a date of birth for a person to match strongly, "
            "and no sale collects one. Two numbers is what the signed rules "
            "produce."
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE MONEY — ⚖️ THE DEBT FOLLOWS THE PROPERTY (OQ-1252, PO 2026-09-01)
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w4__the_buyer_takes_on_the_balance_and_nothing_moves(brazos, marcus):
    """⚖️ *"money follow property - new owner boutght everything property + debt
    also"*.

    **The strongest form of "the debt followed" is that nothing happened to it.**
    The account carries its own ledger and the account did not move, so the
    balance is the same number before and after — and the figure the buyer took
    on is recorded at the moment of sale, which is the only moment it can be
    captured.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell(marcus, account)
        account.refresh_from_db()
        assert account.balance == ARREAR, (
            "the balance never moves, because the thing it sits on never moves"
        )
        assert account.deposit_on_file == DEPOSIT
        assert row["reassignment"]["balance_at_sale"]["stored"] == "284.6000", (
            "the buyer took on the balance as it stood at the moment of sale"
        )
        assert row["reassignment"]["balance_at_sale"]["display"] == "284.60"
        assert row["reassignment"]["deposit_at_sale"]["stored"] == "150.0000"
        assert row["reassignment"]["journal_lines_written"] == 0, (
            "hard rule 5: only the ledger posting service writes a journal "
            "line, and a sale asks it to write none"
        )
        assert row["reassignment"]["refund_raised"] is False


def test_cr058_w4__nothing_issued_to_the_seller_is_rewritten(brazos, marcus, audit_rows):
    """⛔ **CLAUDE.md HARD RULE 4, AND IT IS THE ONE WAY A LANE COULD STILL GET
    THE DEBT RULING WRONG.**

    A bill posted to a named person is a record of what was SENT, not a
    statement of who owes it today. The debt following the property is about the
    ACCOUNT's balance; it is not a licence to re-address the seller's documents.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        invoices_before = list(
            customers_models.Account.objects.filter(id=account.id).values_list(
                "account_no", flat=True
            )
        )
        row = _sell(marcus, account)
        # The reassignment reports, as a fact rather than a promise, that it
        # wrote no money row at all.
        assert row["reassignment"]["journal_lines_written"] == 0
        assert (
            list(
                customers_models.Account.objects.filter(id=account.id).values_list(
                    "account_no", flat=True
                )
            )
            == invoices_before
        ), (
            "hard rule 4: an invoice issued to the seller is a record of what "
            "was SENT. A sale does not rewrite it."
        )


def test_cr058_w4__the_money_sentences_say_what_actually_happens(brazos, marcus):
    """The clerk-facing wording moved with the act.

    *"deposit carried"* described a deposit travelling between two accounts.
    Nothing travels at a sale, and a sentence that says otherwise is a lie in
    the accent colour.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        statement = transfers.money_statement(marcus, started["id"])
        assert "the buyer takes on $284.60" in statement["money"]["sentences"]
        for sentence in statement["money"]["sentences"]:
            assert "carried" not in sentence, (
                "nothing is carried at a sale — the account stays and the money "
                "stays on it"
            )


def test_cr058_w4__the_unruled_money_absence_is_gone(brazos, marcus):
    """Hard-won law 1 — a stated absence whose question has been answered is a
    lie with a rule id on it.

    `transfer_money_rule_does_not_exist` rode EVERY transfer statement and said
    *"nobody has ruled what happens to this money"*. `OQ-1252` closed on
    2026-09-01. A screen still drawing it would tell a clerk the product is
    waiting for a decision that has been made.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        statement = transfers.money_statement(marcus, started["id"])
        codes = {entry["code"] for entry in statement["money"]["unavailable"]}
        assert "transfer_money_rule_does_not_exist" not in codes
        assert "deposit_carry_has_no_transfer_path" not in codes
        assert "arrears_follow_has_no_posting_path" not in codes
        assert not hasattr(transfers, "GAP_TRANSFER_MONEY_UNRULED"), (
            "the constant is DELETED rather than left unused — an unused "
            "absence reads as an absence that still applies"
        )


# ═══════════════════════════════════════════════════════════════════════════
# THE BUYER MUST BE IDENTIFIABLE — PO 2026-09-01
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "buyer",
    [
        pytest.param({}, id="nothing at all"),
        pytest.param({"display_name": BUYER_NAME}, id="a name and no kind"),
        pytest.param(
            {"display_name": BUYER_NAME, "kind": "person", "identity": {}},
            id="a name, a kind and no identifier",
        ),
        pytest.param(
            {"display_name": BUYER_NAME, "kind": "company", "identity": {"ssn": "111-22-3333"}},
            id="a company presenting a person's identifier",
        ),
    ],
)
def test_cr058_w4__a_buyer_who_cannot_be_identified_is_refused(brazos, marcus, buyer):
    """*"Without identifier we cannot create Customer ID or master account ot
    regular account"* (PO 2026-09-01), read onto a live ledger.

    A reassignment CREATES no account, so the letter of that rule does not reach
    it. Its POINT does: no account may exist with nobody identifiable behind it,
    and handing a live account to an unidentified party produces exactly that.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        with pytest.raises((errors.BizError, errors.ValidationError)):
            transfers.set_new_customer(marcus, started["id"], {"customer": buyer})
        assert (
            customers_models.CustomerAccount.objects.filter(account_id=account.id).count() == 1
        ), "CR-058: a buyer with no identifier may not be handed a live account"


def test_cr058_w4__the_refusal_is_repeated_at_the_commit_for_a_service_layer_caller(
    brazos, marcus
):
    """Defence in depth (`BR-SHL-025`'s posture): a management command, another
    module or the next lane does not have to pass through step 2."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        transfers.set_new_customer(marcus, started["id"], {"customer": BUYER})
        transfers.set_sale_date(marcus, started["id"], {"sold_on": "2026-09-01"})
        transfers.acknowledge_money(marcus, started["id"])
        with pytest.raises((errors.BizError, errors.ValidationError)):
            transfers.reassign_account(
                marcus, started["id"], {"customer": {"display_name": BUYER_NAME}}
            )


def test_cr058_w4__selling_to_the_current_owner_is_refused(brazos, marcus):
    """Nothing to reassign. Writing the link to itself would produce an audit
    row about a non-event, and a clerk would read it as a completed sale.

    ⚠ **THE CLERK NAMES THE CUSTOMER, AND THAT IS THE ONLY WAY THIS CASE CAN
    BE DETECTED FOR A PERSON.** `BR-CUS-019` is advisory — staff decides, and a
    match resolves by LINKING — so `customer_id` is the clerk picking the
    existing party out of the list. Typing the seller's name and phone again
    would create a SECOND customer under `BR-CUS-089` (a phone alone is a weak
    match), and the product genuinely cannot tell that apart from a different
    person with the same phone. That limit is pinned two cases up.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        current = customers_models.CustomerAccount.objects.get(account_id=account.id)
        seller = {
            "display_name": SELLER_NAME,
            "kind": "person",
            "identity": {"phone": "+1-555-0101"},
            "customer_id": str(current.customer_id),
        }
        with pytest.raises(errors.BizError) as caught:
            _sell(marcus, account, buyer=seller)
        assert caught.value.params["reason"] == transfers.REFUSAL_BUYER_IS_THE_SELLER


# ═══════════════════════════════════════════════════════════════════════════
# TASK 17 — THE ONE-OWNER-PER-ADDRESS GUARD, SETTLED BY THE DESIGN
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w4__selling_a_premises_with_a_master_account_never_meets_the_one_owner_guard(
    brazos, marcus
):
    """`BR-CUS-1011` — task 17, and it is settled rather than worked around.

    The guard fires on CREATING a second Master Account at an address that
    already has one. **A sale creates no account**, so the obstacle does not
    arise — and the only thing that can prove the guard was never REACHED,
    rather than merely not raised today, is that the account count at the
    premises is unchanged.
    """
    with tenant_ctx(brazos):
        premises, _unit, account = _sold_account(marcus, brazos)
        # `BR-CUS-1114` (PO 2026-10-02) — two or more homes before a master.
        top_up_homes(marcus, premises["id"])
        master = customers_services.create_master_account(
            marcus,
            {
                "premises_id": str(premises["id"]),
                "account_type": "residential",
                "opened_at": "2026-07-01",
                "contact": {"full_name": SELLER_NAME},
                # `BR-CUS-1024` (PO 2026-09-01) — the master door refuses an
                # account whose customer identifies nobody, and the seller is
                # named above. One shape for every fixture:
                # tests/identity_fixtures.py.
                "customer": identity_fixtures.customer_block(
                    SELLER_NAME, account_type="residential"
                ),
            },
        )
        before = customers_models.Account.objects.filter(premises_id=premises["id"]).count()
        _sell(marcus, account)
        after = customers_models.Account.objects.filter(premises_id=premises["id"]).count()
        assert after == before, (
            "BR-CUS-1011 refuses a SECOND owner account at an address. A sale "
            "creates none, so the guard cannot be reached — and it cannot be "
            "reintroduced without reintroducing the second account the ruling "
            "removed."
        )
        assert customers_models.Account.objects.filter(id=master["id"]).exists()


# ═══════════════════════════════════════════════════════════════════════════
# STATED ABSENCES AND THE AUDIT ROW
# ═══════════════════════════════════════════════════════════════════════════


def test_cr058_w4__a_regular_sale_leaves_the_premises_owner_and_states_no_gap(brazos, marcus):
    """⊕ **FLIPPED 2026-09-23 — T2 (`DEF-CUS-6394`).** This case asserted that
    every sale stated `premises_owner_record_not_updated`. PO, verbatim: *"in
    case of master account - not in case of regualr account - (a) The sale makes
    the buyer the property's owner."* A REGULAR account's sale leaves the owner
    as it is — that is the ruling, not a gap — so nothing is stated. The master
    case is `tests/test_def_cus_6387_transfer_po_list.py`.
    """
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        row = _sell(marcus, account)
        codes = {entry["code"] for entry in row["unavailable"]}
        assert "premises_owner_record_not_updated" not in codes
        assert row["premises_owner"]["state"] == "unchanged"


def test_cr058_w4__hard_rule_7_the_reassignment_writes_audit_log(brazos, marcus, audit_rows):
    """A reassignment is a money action — it decides who owes a balance — so it
    writes `audit_log` with both figures as they stood."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        _sell(marcus, account)
        # ⚠ `audit_rows` is the capture SINK's list, not a callable, and each
        # row is a dict — `audit_actions` is the shared reader for exactly this.
        actions = {row["action"] for row in audit_rows}
        assert "transfer.reassigned" in actions
        assert "transfer.money_acknowledged" in actions


def test_cr058_w4__the_five_steps_describe_a_sale(brazos, marcus):
    """The vocabulary moved with the job. Steps that still said *"Find the new
    unit"* would describe a product that no longer exists — worse than saying
    nothing, because a clerk would believe them."""
    assert transfers.STEP_COUNT == 5
    labels = [label for _n, label in transfers.STEPS]
    assert labels == [
        "Find the account and confirm who is selling",
        "Who is buying it — name, person or company, and one identifier",
        "The date of sale",
        "What the buyer takes on — the balance and the deposit as they stand",
        "Review — one account, one new owner, one commit",
    ]
    for name in ("set_target_unit", "set_dates", "elect_money", "commit_transfer"):
        assert not hasattr(transfers, name), (
            f"CR-058 task 15: {name} belonged to the job that created a second "
            "account. It is REMOVED rather than left beside its replacement — "
            "two doors to one act is how the reversal gets undone by accident."
        )


def test_cr058_w4__the_review_draws_one_consequence_not_two(brazos, marcus):
    """The old review listed an outgoing half (*closed*) and an incoming half
    (*opened at a new unit*). There is one account and it changes hands."""
    with tenant_ctx(brazos):
        _premises, _unit, account = _sold_account(marcus, brazos)
        started = transfers.start_transfer(marcus, {"from_account_id": str(account.id)})
        transfers.set_new_customer(marcus, started["id"], {"customer": BUYER})
        transfers.set_sale_date(marcus, started["id"], {"sold_on": "2026-09-01"})
        transfers.acknowledge_money(marcus, started["id"])
        review = transfers.review(marcus, started["id"])
        assert len(review["consequences"]) == 1
        only = review["consequences"][0]
        assert only["effect"] == "customer_changes"
        assert only["unit_changes"] is False
        assert only["account_number_changes"] is False
        assert review["ready"] is True
